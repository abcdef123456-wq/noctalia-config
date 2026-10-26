"""Moteurs du runner JARVIS. L'AGY d'origine reste intact ; les autres CLI
reçoivent un contexte textuel borné, indépendant de leurs sessions personnelles.
Aucun shell ni contournement d'approbation n'est ajouté.
"""
import asyncio
import contextlib
import functools
import inspect
import json
import logging
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import tempfile
import time
import uuid

ENGINES = {'agy': 'Antigravity', 'codex': 'Codex', 'claude': 'Claude Code', 'opencode': 'OpenCode'}
# Modes de permission permis partout (choose, restauration, /run) : la liste de 94a3a93, comme PERMISSION_MODES de
# nc_management (un test vérifie qu'elles sont égales) ; 4ecc57a accepte encore yolo, bypass et always-proceed
MODES_PERMIS = frozenset({'default', 'request-review', 'plan', 'ask', 'auto_edit', 'auto'})
_PERMISSION_MODE_AGY = None


def agy_accepte_permission_mode():
    """Vrai si `agy --help` cite --permission-mode. Regardé une seule fois par processus (5 s au plus, sans shell) ;
    agy introuvable ou --help en échec : l'option est considérée absente. L'agy 1.4.7 ne l'a pas : il sort avec le code 2
    (« flags provided but not defined »), donc tout mode autre que default ferait échouer chaque tour."""
    global _PERMISSION_MODE_AGY
    if _PERMISSION_MODE_AGY is None:
        trouve = False
        chemin = executable('agy')
        if chemin:
            try:
                r = subprocess.run([chemin, '--help'], stdin=subprocess.DEVNULL, capture_output=True, timeout=5,
                                   text=True, errors='replace')
                trouve = r.returncode == 0 and '--permission-mode' in (r.stdout or '') + (r.stderr or '')
            except (OSError, subprocess.SubprocessError, ValueError):
                trouve = False
        _PERMISSION_MODE_AGY = trouve
    return _PERMISSION_MODE_AGY


def modes_permis(engine):
    """Modes de permission proposés pour un moteur (annoncés à l'île dans le snapshot)."""
    if engine == 'agy' and not agy_accepte_permission_mode(): return ['default']
    return sorted(MODES_PERMIS) if engine == 'agy' else []


EFFORTS = {'', 'low', 'medium', 'high', 'xhigh', 'max', 'ultra'}


def executable(engine):
    found = shutil.which(engine)
    if found: return found
    candidates = [Path.home()/'.local/bin'/engine, Path.home()/'.cargo/bin'/engine]
    if engine == 'agy': candidates += [Path.home()/'.gemini/antigravity-cli/agy']
    return next((str(p) for p in candidates if p.is_file() and os.access(p, os.X_OK)), None)


def _signature(fn):
    try: params = inspect.signature(fn).parameters.values()
    except (TypeError, ValueError): return frozenset()
    if any(p.kind == p.VAR_KEYWORD for p in params): return None
    return frozenset(p.name for p in params if p.kind in (p.POSITIONAL_OR_KEYWORD, p.KEYWORD_ONLY))


_signature_en_cache = functools.lru_cache(maxsize=64)(_signature)


def _parametres(fn):
    """Noms acceptés par une fonction upstream (None : tous, elle a **kwargs). Mis en cache."""
    try: return _signature_en_cache(fn)
    except TypeError: return _signature(fn)  # objet non hachable : pas de cache


def compatibles(fn, **valeurs):
    """Garde les mots-clés (non nuls) que fn connaît. JARVIS-BIS ajoute session_key depuis 1ae55f3 ;
    3d1c6b6 ne le connaît pas : on l'omet au lieu de faire échouer la requête."""
    connus = _parametres(fn)
    return {k: v for k, v in valeurs.items() if v is not None and (connus is None or k in connus)}


def atomique(path, data):
    if path.is_symlink(): raise ValueError('Fichier moteur symbolique : aucune écriture.')
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as f:
        name = f.name
        try:
            f.write(json.dumps(data, ensure_ascii=False).encode()); f.flush(); os.fsync(f.fileno())
            os.chmod(name, 0o600); os.replace(name, path)
        finally:
            if os.path.exists(name): os.unlink(name)


# Ce qu'un moteur reçoit de l'environnement du serveur JARVIS : une liste blanche, comme ENV_COMMUN et ENV_MOTEUR de nc-ia.
# Le serveur porte TELEGRAM_TOKEN, DISCORD_TOKEN, SECRET_KEY… (EnvironmentFile du .env) : un moteur n'en a pas besoin.
# Chaque moteur ne reçoit que SA clé (ou celle des fournisseurs dont il parle) et les dossiers où il cherche sa session
# (~/.claude, ~/.codex, ~/.config/opencode : par HOME, ou CLAUDE_CONFIG_DIR, CODEX_HOME, XDG_*).
ENV_COMMUN = frozenset({'PATH', 'HOME', 'USER', 'LOGNAME', 'SHELL', 'LANG', 'LANGUAGE', 'TZ', 'XDG_CONFIG_HOME', 'XDG_DATA_HOME',
    'XDG_STATE_HOME', 'XDG_CACHE_HOME', 'HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY', 'NO_PROXY', 'http_proxy', 'https_proxy',
    'all_proxy', 'no_proxy', 'SSL_CERT_FILE', 'SSL_CERT_DIR', 'NODE_EXTRA_CA_CERTS'})
ENV_MOTEUR = {
    'claude': frozenset({'ANTHROPIC_API_KEY', 'ANTHROPIC_AUTH_TOKEN', 'ANTHROPIC_BASE_URL', 'CLAUDE_CODE_OAUTH_TOKEN', 'CLAUDE_CONFIG_DIR'}),
    'codex': frozenset({'OPENAI_API_KEY', 'CODEX_API_KEY', 'OPENAI_BASE_URL', 'CODEX_HOME'}),
    'opencode': frozenset({'OPENCODE_API_KEY', 'ANTHROPIC_API_KEY', 'OPENAI_API_KEY', 'GEMINI_API_KEY', 'GOOGLE_GENERATIVE_AI_API_KEY',
        'OPENROUTER_API_KEY', 'GROQ_API_KEY', 'MISTRAL_API_KEY', 'DEEPSEEK_API_KEY', 'XAI_API_KEY'}),
}


def env_moteur(engine):
    gardes = ENV_COMMUN | ENV_MOTEUR.get(engine, frozenset())
    env = {k: v for k, v in os.environ.items() if k in gardes or k.startswith('LC_')}
    env.update(TERM='dumb', NO_COLOR='1', FORCE_COLOR='0')
    return env


# Garde-fou de sortie : un moteur (ou une injection de prompt) peut recopier un secret du serveur dans sa réponse, qui
# part ensuite vers Telegram, Discord ou le cockpit. Toute ligne qui contient la valeur EXACTE d'un secret (jeton,
# SECRET_KEY, clé d'API, mot de passe ; 8 caractères au moins) du .env ou de l'environnement est remplacée.
SECRET_CLE = re.compile(r'TOKEN|SECRET|PASSW|API_?KEY|_KEY$|^KEY$|CREDENTIAL|PRIVATE', re.I)
SECRET_RETIRE = '[secret retiré]'


def valeurs_secretes(dossier):
    """Valeurs (8 caractères au moins) des clés secrètes de l'environnement et des .env autour du runner (dossier)."""
    trouvees = {v for k, v in os.environ.items() if SECRET_CLE.search(k) and len(v) >= 8}
    for chemin in (dossier/'.env', dossier.parent/'.env', dossier.parent/'gateway/.env', dossier.parent/'render-gateway/.env'):
        try: lignes = chemin.read_text(encoding='utf-8', errors='replace').splitlines()
        except OSError: continue
        for ligne in lignes:
            cle, sep, v = ligne.partition('=')
            cle = cle.strip().removeprefix('export ').strip()
            if not sep or not SECRET_CLE.search(cle): continue
            v = v.strip()
            if v[:1] in '"\'' and v[-1:] == v[:1] and len(v) >= 2:
                try: v = json.loads(v) if v[0] == '"' else v[1:-1]
                except ValueError: v = v[1:-1]
            if len(v) >= 8: trouvees.add(v)
    return trouvees


def dossier_runner(up):
    return Path(up.__file__).resolve().parent


def sans_secrets(texte, dossier):
    """Le texte sans les lignes qui contiennent un secret exact ; remplacées par « [secret retiré] »."""
    if not isinstance(texte, str): return texte
    secrets = valeurs_secretes(dossier)
    if not any(v in texte for v in secrets): return texte
    return '\n'.join(SECRET_RETIRE if any(v in l for v in secrets) else l for l in texte.split('\n'))


def ia_coupee():
    """Vrai si IA_MODE=non dans ~/.config/nc/reglages.conf (dernière valeur, espaces et guillemets tolérés), comme nc-ia.
    Seulement en déploiement local (DEPLOY_MODE différent de server) : le serveur de l'hébergeur n'a pas les réglages
    du PC de l'utilisateur, et ses moteurs sont ceux de l'hébergeur."""
    if os.environ.get('DEPLOY_MODE', 'local').strip().lower() == 'server': return False
    return reglage_nc('IA_MODE', '') == 'non'


def reglage_nc(nom, defaut=''):
    """Dernière valeur de nom dans ~/.config/nc/reglages.conf (espaces et guillemets tolérés), sinon defaut."""
    valeur = None
    try:
        for ligne in (Path.home()/'.config/nc/reglages.conf').read_text(encoding='utf-8').splitlines():
            cle, sep, v = ligne.partition('=')
            if sep and cle.strip() == nom: valeur = v.strip().strip('"')
    except (OSError, ValueError): pass
    return defaut if valeur is None else valeur


# Isolation des moteurs (déploiement local) : un moteur « en lecture seule » lit pourtant tout le disque avec le vrai HOME,
# donc le .env du serveur (TELEGRAM_TOKEN, SECRET_KEY…) par un chemin absolu, et peut le recopier dans sa réponse. Chaque
# moteur tourne donc dans une unité systemd --user TRANSITOIRE (comme nc-bac) où le dossier du backend et les .env sont
# inaccessibles (InaccessiblePaths), ainsi que tout ce que nc-bac protège déjà (liste de nc-bac : ~/.ssh, navigateurs,
# assistant.conf, noeud-totp.json, ~/.local/state/nc-jarvis…). Le vrai HOME reste visible, SAUF ces chemins : seuls les
# dossiers de session du moteur lancé restent lisibles (LIBRES_MOTEUR : ~/.claude, ~/.codex, ~/.config/opencode…).
#   ReadOnlyPaths : ce qui s'exécute ou se relit plus tard HORS de l'unité (~/.local/bin, ~/.local/share/nc-jarvis, hypr, systemd,
#     autostart, applications, shells, pipewire, ~/.config/nc, copie du dépôt… : listes de nc-bac et de nc-noeud, lues sur place)
#     et les réglages et consignes des CLI (settings.json, CLAUDE.md, hooks, plugins, config.toml…, CONSIGNES_MOTEUR) ;
#     le lanceur vérifie qu'on n'y écrit pas. Le reste du HOME reste inscriptible : LIMITE CONNUE, le moteur peut écrire la
#     config de son CLI (~/.claude.json et ses serveurs MCP, un fichier de consignes ABSENT qu'il créerait, le reste des
#     dossiers d'état), exécutée plus tard ; un prochain lot donnera aux moteurs un faux HOME ;
#   TemporaryFileSystem (JETABLES_MOTEUR) : transcriptions, mémoire et scripts de shell de l'utilisateur (~/.claude/projects,
#     ~/.codex/memories, shell-snapshots…) vides et jetés avec l'unité : le moteur ne les lit pas, n'y écrit rien de durable
#     (JARVIS lance déjà claude --no-session-persistence et codex --ephemeral) ;
#   PrivateTmp : /tmp à lui (pas de socket X11, tmux ou ssh-agent de /tmp) ;
#   RestrictAddressFamilies=AF_INET AF_INET6 : aucun socket Unix, comme dans le bac où nc-ia lance ces mêmes moteurs ;
#   PrivateUsers + NoNewPrivileges : mise en place sans root, pas d'élévation ;
#   PrivatePIDs (systemd 257) : un /proc à lui ; sans lui, /proc/<pid>/environ du runner (qui a le .env en EnvironmentFile)
#     resterait lisible ; sur un systemd plus ancien la sonde échoue et le moteur n'est pas lancé (comme nc-bac) ;
#   $XDG_RUNTIME_DIR vide (TemporaryFileSystem) : pas de bus, donc pas de « systemd-run --user » qui sortirait de l'unité.
# Le lanceur Python (-I) efface l'environnement de l'unité (celui du gestionnaire, avec ses clés exportées) et ne remet que
# la liste blanche ; ses valeurs passent par --setenv=NOM (jamais dans la ligne de commande). Il VÉRIFIE aussi, dans
# l'unité, que chaque chemin caché refuse l'accès (code 97 sinon) : la protection est contrôlée à chaque lancement.
# Aucun repli : en local, pas de systemd-run ou protection absente = pas de moteur. Sur le serveur de l'hébergeur
# (DEPLOY_MODE=server) la même mesure est prise si systemd est là ; sinon pas de moteur non plus, sauf si le .env du
# serveur (jamais modifiable à distance : hors de CONFIG_PERMIS) contient NC_MOTEURS_SANS_ISOLATION=oui.
CODE_REFUS_ISOLATION = 97
LANCEUR_ISOLE = ("import os,sys\n"
    "a=sys.argv\n"
    "garde=set(a[1].split(',')) if a[1] else set()\n"
    "cwd=a[2]; i=4; n=int(a[3]); caches=a[i:i+n]; i+=n\n"
    "n=int(a[i]); temoins=a[i+1:i+1+n]; i+=1+n\n"
    "n=int(a[i]); lectures=a[i+1:i+1+n]; i+=1+n; argv=a[i:]\n"
    "for p in caches:\n"
    "    try:\n"
    "        os.listdir(p) if os.path.isdir(p) else open(p,'rb').close()\n"
    "    except OSError: continue\n"
    "    sys.exit(%d)\n"
    "for d in temoins:\n"
    "    f=os.path.join(d,'.nc-temoin-%%d'%%os.getpid())\n"
    "    try: os.close(os.open(f,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600))\n"
    "    except OSError: continue\n"
    "    try: os.unlink(f)\n"
    "    except OSError: pass\n"
    "    sys.exit(%d)\n"
    "for p in lectures:\n"
    "    if os.access(p,os.W_OK): sys.exit(%d)\n"
    "env={k:os.environ[k] for k in garde if k in os.environ}\n"
    "os.chdir(cwd)\n"
    "os.execvpe(argv[0],argv,env)\n") % (CODE_REFUS_ISOLATION, CODE_REFUS_ISOLATION, CODE_REFUS_ISOLATION)
MESSAGE_NON_ISOLE = ('L’IA de JARVIS n’est pas isolée ici (systemd 257 ou plus requis, avec systemd-run --user ; '
                     'sinon la protection du .env est absente) : aucun moteur n’est lancé.')
MESSAGE_DISTANT = (MESSAGE_NON_ISOLE[:-1] + ' Pour l’accepter quand même (le moteur pourra lire les jetons du bot), mets '
                   'NC_MOTEURS_SANS_ISOLATION=oui dans le .env du serveur.')
# En plus des listes de nc-bac et nc-noeud, en LECTURE SEULE (relatifs à ~, motifs permis, seulement s'ils existent) : ce qui
# s'exécute ou se charge plus tard (un .pth de site-packages s'exécute dans tout python3 ; le CLI codex est dans
# ~/.local/lib/node_modules), pour tous les moteurs
LECTURE_SEULE_EN_PLUS = ('.local/lib', '.local/share/noctalia', '.config/fastfetch', '.local/share/nc', '.config/user-tmpfiles.d',
                         '.local/share/dbus-1', '.config/environment.d', '.local/share/systemd', '.config/go',
                         '.local/share/flatpak/exports', '.vim', '.local/share/kio', '.local/share/nautilus', '.local/share/nemo',
                         'CLAUDE.md')
# En plus de ceux de nc-bac, ILLISIBLES (noms génériques : profils et identifiants d'autres programmes)
CACHES_EN_PLUS = ('.pki', '.config/torbrowser', '.local/share/torbrowser', '.config/google-chrome-for-testing', '.config/Proton',
                  '.config/Mullvad VPN')
# Jetables : vides dans l'unité, jetés avec elle (relatifs à ~ ; seulement s'ils existent)
JETABLES_MOTEUR = {
    'claude': ('.claude/projects', '.claude/shell-snapshots'),
    'codex': ('.codex/memories', '.codex/shell_snapshots'),
    'opencode': (),
}
# Réglages, consignes, hooks et plugins des CLI (relatifs à ~, motifs permis) : lus mais jamais écrits pendant une question
CONSIGNES_MOTEUR = {
    'claude': ('.claude/settings*.json', '.claude/CLAUDE.md', '.claude/hooks', '.claude/commands', '.claude/agents',
               '.claude/skills', '.claude/plugins', '.claude/output-styles'),
    'codex': ('.codex/config.toml', '.codex/AGENTS.md', '.codex/AGENTS.override.md', '.codex/prompts', '.codex/rules',
              '.codex/skills', '.codex/hooks*'),
    'opencode': ('.config/opencode/opencode.json', '.config/opencode/opencode.jsonc', '.config/opencode/plugin',
                 '.config/opencode/plugins', '.config/opencode/agent', '.config/opencode/agents', '.config/opencode/command',
                 '.config/opencode/commands'),
}
# Dossiers de session que chaque moteur garde lisibles (relatifs à ~) ; les autres moteurs restent cachés (nc-ia fait de même)
LIBRES_MOTEUR = {
    'claude': ('.claude', '.claude.json', '.cache/claude-cli-nodejs', '.local/state/claude'),
    'codex': ('.codex',),
    'opencode': ('.config/opencode', '.local/share/opencode', '.local/state/opencode', '.cache/opencode'),
}
_sonde_isolation = {'ok': 0.0}


class IsolationImpossible(Exception):
    """Le moteur ne peut pas être lancé à l'abri du .env du serveur."""


def deploiement_distant():
    return os.environ.get('DEPLOY_MODE', 'local').strip().lower() == 'server'


def dossier_travail():
    """Dossier de travail vide du moteur, sous le cache de l'utilisateur : le runner (PrivateTmp) et l'unité du moteur
    y voient la même chose, pas dans /tmp (qui est différent pour chacun). Seul le serveur de l'hébergeur retombe sur /tmp."""
    try:
        base = Path(os.environ.get('XDG_CACHE_HOME') or Path.home()/'.cache')/'nc-jarvis-travail'
        base.mkdir(mode=0o700, parents=True, exist_ok=True)
        return tempfile.mkdtemp(prefix='moteur-', dir=str(base))
    except OSError:
        if not deploiement_distant(): raise
        return tempfile.mkdtemp(prefix='nc-jarvis-')


def _dans(chemin, dossier):
    return chemin == dossier or dossier in chemin.parents


_NC_BAC = {}


def module_bac():
    """Le module nc-bac (~/.local/bin/nc-bac, chargé par son chemin comme le fait nc-ia), ou None s'il manque."""
    import importlib.machinery
    import importlib.util
    chemin = Path.home()/'.local/bin/nc-bac'
    if chemin not in _NC_BAC:
        try:
            ld = importlib.machinery.SourceFileLoader('nc_bac_moteurs', str(chemin))
            m = importlib.util.module_from_spec(importlib.util.spec_from_loader(ld.name, ld))
            ld.exec_module(m)
        except (OSError, SyntaxError, ImportError): m = None
        _NC_BAC[chemin] = m
    return _NC_BAC[chemin]


def chemins_caches(dossier, engine=None):
    """Chemins (réels, et tels quels) que le moteur ne doit pas voir, ceux qui existent :
      - le dossier du runner, le backend (s'il ne contient pas le HOME), leurs .env* (.env.backup-… compris), gateway,
        render-gateway, ~/.env*, ~/.local/share/jarvis-bis ;
      - tout ce que nc-bac rend illisible (inaccessibles() : .ssh, .gnupg, navigateurs, assistant.conf, noeud-totp.json,
        ~/.local/state/nc-jarvis, Noctalia…), sauf les dossiers de session du moteur lancé (LIBRES_MOTEUR).
    IsolationImpossible si un chemin obligatoire contient le HOME, ou si nc-bac manque / ne sait pas protéger (en local ;
    sur le serveur de l'hébergeur, sans nc-bac, il ne reste que les .env)."""
    d = dossier.resolve()
    maison = Path.home().resolve()
    candidats = [(d, True), (d.parent/'gateway', True), (d.parent/'render-gateway', True), (d.parent, False),
                 (Path.home()/'.local/share/jarvis-bis', False)]
    for dossier_env in dict.fromkeys((d, d.parent, d.parent/'gateway', d.parent/'render-gateway', Path.home(), maison)):
        try: candidats += [(q, True) for q in sorted(dossier_env.glob('.env*'))]
        except OSError: pass
    sortie = []
    def ajoute(chemin):
        for x in (str(chemin.resolve()), str(chemin)):
            if x not in sortie: sortie.append(x)
    for chemin, obligatoire in candidats:
        if not os.path.lexists(chemin): continue
        if _dans(maison, chemin.resolve()):
            if obligatoire: raise IsolationImpossible(MESSAGE_NON_ISOLE)
            continue
        ajoute(chemin)
    bac = module_bac()
    if bac is None:
        if not deploiement_distant(): raise IsolationImpossible(MESSAGE_NON_ISOLE)
        return sortie
    run = os.path.realpath(os.environ.get('XDG_RUNTIME_DIR') or '/run/user/%d' % os.getuid())
    try: protege = bac.inaccessibles(Path.home(), reglage_nc, libres=LIBRES_MOTEUR.get(engine, ()), environ=os.environ)
    except (OSError, ValueError): protege = None
    if protege is None: raise IsolationImpossible(MESSAGE_NON_ISOLE)
    for x in protege:
        if os.path.realpath(x) == run: continue            # déjà un tmpfs vide (TemporaryFileSystem)
        if _dans(maison, Path(os.path.realpath(x))): continue   # un dossier qui contient le HOME ne peut pas être caché
        ajoute(Path(x))
    for rel in CACHES_EN_PLUS:
        chemin = Path.home()/rel
        if os.path.lexists(chemin) and not _dans(maison, chemin.resolve()) and not any(_dans(chemin.resolve(), Path(c)) for c in sortie):
            ajoute(chemin)
    return sortie


def liste_noeud(nom):
    """La liste NOM (de chaînes) de nc-noeud (~/.local/bin/nc-noeud), lue dans son source sans l'exécuter ; None si absente."""
    import ast
    try:
        arbre = ast.parse((Path.home()/'.local/bin/nc-noeud').read_text(encoding='utf-8'))
        for n in arbre.body:
            if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == nom for t in n.targets):
                v = ast.literal_eval(n.value)
                return [x for x in v if isinstance(x, str)] if isinstance(v, list) else None
    except (OSError, SyntaxError, ValueError): pass
    return None


def chemins_jetables(engine):
    """Dossiers existants (réels) à remplacer par un tmpfs vide dans l'unité. Le dossier de config du moteur existe : le
    sous-dossier manquant est créé (0700, vide) pour que le moteur ne le crée pas, durable, dans le vrai HOME."""
    home = Path.home()
    sortie = []
    for rel in JETABLES_MOTEUR.get(engine, ()):
        chemin = home/rel
        if not os.path.lexists(chemin) and chemin.parent.is_dir():
            with contextlib.suppress(OSError): os.mkdir(chemin, 0o700)
        if chemin.is_dir():
            r = str(Path(os.path.realpath(chemin)))
            if r not in sortie: sortie.append(r)
    return sortie


def chemins_lecture_seule(engine, caches):
    """Chemins (réels) que le moteur peut lire mais pas modifier : ce qui s'exécute plus tard hors de l'unité (~/.local/bin,
    ~/.local/share/nc-jarvis, hypr, systemd, autostart, applications, shells, pipewire, wireplumber, ~/.config/nc, la copie du
    dépôt…). Une seule source, celle de nc-noeud : PROTEGES (= nc-bac) et ECRITURE_SEULEMENT, plus ~/.config/nc/depot. Seuls ceux
    qui existent ; sans ceux déjà cachés, ni les dossiers de session du moteur (~/.claude, ~/.codex… restent inscriptibles :
    limite connue). En local sans nc-bac ou nc-noeud lisible : IsolationImpossible ; sur le serveur de l'hébergeur : rien."""
    home = Path.home()
    bac = module_bac()
    ecriture_seulement = liste_noeud('ECRITURE_SEULEMENT')
    if bac is None or ecriture_seulement is None:
        if deploiement_distant(): return []
        raise IsolationImpossible(MESSAGE_NON_ISOLE)
    try: depl = bac.deplacements(home, os.environ)
    except ValueError: raise IsolationImpossible(MESSAGE_NON_ISOLE)
    libres = LIBRES_MOTEUR.get(engine, ())
    sortie = []
    for rel in list(bac.PROTEGES) + ecriture_seulement + list(LECTURE_SEULE_EN_PLUS) + list(CONSIGNES_MOTEUR.get(engine, ())):
        if rel not in CONSIGNES_MOTEUR.get(engine, ()) and (rel in libres or any(rel.startswith(l + '/') for l in libres)): continue
        for base in dict.fromkeys([home/rel, bac.emplacement(home, rel, depl)]):
            motif = any(c in base.name for c in '*?[') or any(c in str(base.parent) for c in '*?[')
            try: trouves = sorted(Path(base.anchor).glob(str(base.relative_to(base.anchor)))) if motif else [base]
            except (OSError, ValueError): trouves = []
            for q in trouves:
                if os.path.lexists(q):
                    r = str(Path(os.path.realpath(q)))
                    if r not in sortie: sortie.append(r)
    # La copie du dépôt (~/.config/nc/depot, une ligne), comme depot_dotfiles() de nc-noeud
    try:
        brut = (home/'.config/nc/depot').read_bytes()[:4096].decode('utf-8', 'replace').strip()
        depot = Path(brut).expanduser() if brut and '\0' not in brut and '\n' not in brut else None
        if depot and depot.is_absolute() and depot != Path('/') and depot != home and depot not in home.parents and depot.exists():
            sortie.append(str(depot.resolve()))
    except OSError: pass
    ouverts = [Path(os.path.realpath(x)) for x in sortie]
    return [str(q) for q in ouverts if not any(_dans(q, Path(c)) for c in caches)
            and not any(_dans(Path(os.path.realpath(l)), q) and Path(os.path.realpath(l)) != q for l in [str(home/x) for x in libres])]


async def isoler(engine, args, travail, timeout, dossier):
    """(commande systemd-run, environnement du client, unité, chemins cachés) pour lancer args dans l'unité isolée.
    None si l'isolation n'est pas exigée ici (serveur de l'hébergeur sans systemd). IsolationImpossible sinon."""
    distant = deploiement_distant()
    try:
        sr = shutil.which('systemd-run')
        env = env_moteur(engine)
        py = shutil.which('python3', path=env.get('PATH'))
        run = os.environ.get('XDG_RUNTIME_DIR') or '/run/user/%d' % os.getuid()
        if not sr or not py or not os.path.isabs(run) or not os.path.isdir(run): raise IsolationImpossible(MESSAGE_NON_ISOLE)
        run = os.path.realpath(run)
        caches = chemins_caches(dossier, engine)
        lecture = chemins_lecture_seule(engine, caches)
        jetables = chemins_jetables(engine)
        if any(c in x for x in jetables for c in '"\\%:\n\0 '): raise IsolationImpossible(MESSAGE_NON_ISOLE)
        # Le lanceur essaie de créer un fichier témoin dans chaque dossier en lecture seule (et d'ouvrir en écriture chaque
        # fichier) : si ça réussit, la protection ne tient pas, code 97
        temoins = [x for x in lecture if os.path.isdir(x)]
        fichiers = [x for x in lecture if not os.path.isdir(x)]
        if any(c in x for x in lecture for c in '"\\%:\n\0'): raise IsolationImpossible(MESSAGE_NON_ISOLE)
        if any(_dans(Path(os.path.realpath(travail)), Path(x)) for x in lecture): raise IsolationImpossible(MESSAGE_NON_ISOLE)
        # L'exécutable, le python du lanceur et le dossier de travail doivent rester visibles
        for x in (args[0], py, travail):
            reel = Path(os.path.realpath(x))
            if any(_dans(reel, Path(c)) for c in caches): raise IsolationImpossible(MESSAGE_NON_ISOLE)
        # Guillemets, barre oblique inverse, « % » (spécificateur), saut de ligne ou « : » : pas d'unité plutôt qu'une mal lue
        if any(c in x for x in caches + [run] for c in '"\\%:\n\0'): raise IsolationImpossible(MESSAGE_NON_ISOLE)
        unite = 'nc-jarvis-moteur-' + uuid.uuid4().hex[:12]
        cmd = [sr, '--user', '--pipe', '--wait', '--collect', '--quiet', '--expand-environment=no', '--unit=' + unite,
               '--description=nc-jarvis-moteur-' + re.sub(r'[^a-z]', '', engine.lower())]
        props = ['PrivateUsers=yes', 'NoNewPrivileges=yes', 'PrivatePIDs=yes', 'PrivateDevices=yes', 'PrivateIPC=yes',
                 'PrivateTmp=yes', 'RestrictAddressFamilies=AF_INET AF_INET6', 'KillSignal=SIGKILL', 'TimeoutStopSec=1s', 'OnFailure=', 'RuntimeMaxSec=%d' % (int(timeout) + 5),
                 'TemporaryFileSystem=' + run + ':ro', 'KeyringMode=private',
                 'SystemCallFilter=~@debug @keyring', 'ReadOnlyPaths=-/dev/shm']
        for p in props: cmd += ['-p', p]
        for c in caches: cmd += ['-p', 'InaccessiblePaths="-' + c + '"']
        # /dev/shm est en lecture seule (partagé entre comptes) ; un HOME ou un dossier de travail qui y vit reste inscriptible
        for c in (os.path.realpath(Path.home()), os.path.realpath(travail)):
            if _dans(Path(c), Path('/dev/shm')): cmd += ['-p', 'ReadWritePaths="-' + c + '"']
        for c in lecture: cmd += ['-p', 'ReadOnlyPaths="-' + c + '"']
        for c in jetables: cmd += ['-p', 'TemporaryFileSystem=' + c + ':mode=1777']
        noms = sorted(env)
        for n in noms: cmd.append('--setenv=' + n)
        def lanceur(garde, reste):
            return ['--', py, '-I', '-c', LANCEUR_ISOLE, garde, str(travail), str(len(caches)), *caches,
                    str(len(temoins)), *temoins, str(len(fichiers)), *fichiers, *reste]
        cmd += lanceur(','.join(noms), args)
        # Le client systemd-run a besoin du bus, pas l'unité (--setenv ne reprend que les noms ci-dessus)
        client = dict(env, XDG_RUNTIME_DIR=run)
        if os.environ.get('DBUS_SESSION_BUS_ADDRESS'): client['DBUS_SESSION_BUS_ADDRESS'] = os.environ['DBUS_SESSION_BUS_ADDRESS']
        # Sonde : la même unité avec « true » au lieu du moteur ; positive gardée 60 s
        if time.monotonic() - _sonde_isolation['ok'] > 60:
            sonde = cmd[:cmd.index('--')] + lanceur('', ['/bin/true'])
            sonde = [x if not x.startswith('--unit=') else '--unit=' + unite + '-sonde' for x in sonde]
            p = await asyncio.create_subprocess_exec(*sonde, env=client, cwd=str(travail), stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL, start_new_session=True)
            try: code = await asyncio.wait_for(p.wait(), 15)
            except asyncio.TimeoutError:
                with contextlib.suppress(ProcessLookupError): os.killpg(p.pid, signal.SIGKILL)
                await p.wait(); code = -1
            if code != 0: raise IsolationImpossible(MESSAGE_NON_ISOLE)
            _sonde_isolation['ok'] = time.monotonic()
        return cmd, client, unite
    except (IsolationImpossible, OSError, ValueError):
        if not distant: raise IsolationImpossible(MESSAGE_NON_ISOLE)
        # Serveur de l'hébergeur : seulement si l'administrateur l'a écrit dans le .env du serveur
        if os.environ.get('NC_MOTEURS_SANS_ISOLATION', '').strip().lower() == 'oui': return None
        raise IsolationImpossible(MESSAGE_DISTANT)


async def arreter_unite(unite, env):
    """Arrête l'unité du moteur (le client systemd-run tué la laisserait tourner jusqu'à RuntimeMaxSec)."""
    with contextlib.suppress(Exception):
        sc = shutil.which('systemctl')
        if not sc: return
        p = await asyncio.create_subprocess_exec(sc, '--user', 'stop', '--no-block', unite, env=env, stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
        await asyncio.wait_for(p.wait(), 5)


async def process(args, prompt, timeout, cwd, env=None, unite=None, erreurs=None):
    """Sorties bornées, groupe entier tué sur timeout/annulation/débordement (et l'unité systemd, si le moteur en a une)."""
    p = await asyncio.create_subprocess_exec(*args, cwd=cwd, start_new_session=True,
        stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        env=env if env is not None else env_moteur(None))
    async def read(stream):
        data = bytearray()
        while True:
            chunk = await stream.read(65536)
            if not chunk: return bytes(data)
            data.extend(chunk)
            if len(data) > 2*1024*1024: raise ValueError('Sortie moteur trop volumineuse.')
    async def write():
        try:
            p.stdin.write(prompt.encode()); await p.stdin.drain()
        except (BrokenPipeError, ConnectionResetError): pass
        finally: p.stdin.close()
    tasks = [asyncio.create_task(read(p.stdout)), asyncio.create_task(read(p.stderr)), asyncio.create_task(write())]
    try:
        out, err, _ = await asyncio.wait_for(asyncio.gather(*tasks), timeout)
        if erreurs is not None: erreurs.append(err[-8192:].decode(errors='replace'))
        await asyncio.wait_for(p.wait(), 2)
        return p.returncode, out.decode(errors='replace')
    finally:
        # Un enfant peut encore détenir les tubes même si son parent vient de sortir.
        with contextlib.suppress(ProcessLookupError): os.killpg(p.pid, signal.SIGKILL)
        for task in tasks: task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        await p.wait()
        if unite: await arreter_unite(unite, env)


ECRITURE_REFUSEE = re.compile(r'Read-only file system|\bEROFS\b|\bEACCES\b|Permission denied|Permission non accordée|accessible en lecture seulement')


def ecriture_refusee(texte):
    """Le message clair (FR/EN) si la sortie d'erreur du moteur montre une écriture refusée par l'isolation, sinon None."""
    m = ECRITURE_REFUSEE.search(texte or '')
    if not m: return None
    chemin = next(iter(re.findall(r'(/[^\s\'"`:,;()]+)', texte)), '?')
    return ('isolation de JARVIS : écriture refusée dans ' + chemin + ', signale-le / '
            'JARVIS isolation: write denied in ' + chemin + ', please report it.')


def commande(engine, path, model, effort):
    if not isinstance(model, str) or len(model)>200 or any(ord(c)<33 for c in model):
        if model != '': raise ValueError('Identifiant de modèle invalide.')
    if model.startswith('-'): raise ValueError('Identifiant de modèle invalide.')
    if effort not in EFFORTS: raise ValueError('Niveau de réflexion invalide.')
    if engine == 'codex':
        cmd = [path, 'exec', '--skip-git-repo-check', '--ephemeral', '--sandbox', 'read-only', '--json']
        if model: cmd += ['--model', model]
        if effort: cmd += ['-c', 'model_reasoning_effort='+json.dumps(effort)]
        return cmd + ['-']
    if engine == 'claude':
        if effort == 'ultra': raise ValueError('Claude Code ne propose pas le niveau ultra.')
        cmd = [path, '--print', '--output-format', 'json', '--permission-mode', 'plan', '--no-session-persistence']
        if model: cmd += ['--model', model]
        if effort: cmd += ['--effort', effort]
        return cmd
    if engine == 'opencode':
        if effort and not model: raise ValueError('OpenCode demande provider/modèle pour choisir une variante.')
        return [path, 'run', '--format', 'json', '--agent', 'plan'] + (['--model', model+('#'+effort if effort else '')] if model else [])
    raise ValueError('Moteur inconnu.')


def reponse(engine, output):
    if engine == 'claude':
        data = json.loads(output)
        if not isinstance(data,dict): raise ValueError('Réponse Claude invalide.')
        if data.get('is_error'): raise ValueError('Claude Code a refusé la requête.')
        text = data.get('result', '')
    else:
        texts = []
        for line in output.splitlines():
            try: event = json.loads(line)
            except ValueError: continue
            if not isinstance(event,dict): continue
            if engine == 'codex':
                if event.get('type') in ('error', 'turn.failed'): raise ValueError('Codex a refusé la requête.')
                item = event.get('item', {})
                if not isinstance(item,dict): continue
                if event.get('type') == 'item.completed' and item.get('type') == 'agent_message': texts.append(item.get('text', ''))
            else:
                if event.get('type') == 'error': raise ValueError('OpenCode a refusé la requête.')
                part=event.get('part', {})
                if event.get('type') == 'text' and isinstance(part,dict): texts.append(part.get('text', ''))
        text = '\n\n'.join(t for t in texts if isinstance(t, str))
    if not isinstance(text, str) or not text.strip(): raise ValueError('Le moteur n’a renvoyé aucune réponse exploitable.')
    return text.strip()[:64000]


class Engines:
    def __init__(self, upstream):
        self.up = upstream
        names = ('run_agy','get_session_info','update_session','reset_session_async','list_recent_conversations',
                 'get_conversation_history','resume_conversation','delete_conversation','delete_all_conversations','get_token_usage')
        self.original = {n:getattr(upstream,n) for n in names}
        self.should_inject = upstream._should_inject_memory
        self.agy_models = list(upstream.KNOWN_MODELS)
        self.path = Path(upstream.__file__).resolve().parent/'.nc-jarvis-engines.json'
        self.lock = asyncio.Lock()
        self.agy_en_cours = 0  # requêtes AGY en vol : chaque PC a sa session, l'upstream a ses propres verrous
        initial=os.getenv('NC_JARVIS_ENGINE','agy')
        if initial not in ENGINES: raise ValueError('NC_JARVIS_ENGINE invalide.')
        self.state = dict(engine=initial, settings={}, conversations=[], active={})
        if self.path.exists():
            st = self.path.lstat()
            if self.path.is_symlink() or st.st_mode & 0o077 or st.st_size > 8*1024*1024:
                raise ValueError('État privé des moteurs à vérifier.')
            # Fichier illisible ou de forme inattendue (édition à la main, disque) : état par défaut, sans le réécrire,
            # plutôt qu'un runner qui ne démarre plus et redémarre en boucle
            try:
                data = json.loads(self.path.read_text())
            except (ValueError, UnicodeDecodeError, RecursionError):
                data = None
            if isinstance(data,dict) and data.get('engine') in ENGINES:
                self.state.update(data)
                if not isinstance(self.state.get('settings'), dict): self.state['settings'] = {}
            else:
                logging.getLogger('nc_engines').warning('État des moteurs illisible : ignoré, état par défaut.')
        if self.state['engine']=='agy' and self.state['settings'].get('agy'):
            self.restaure_agy()

    def restaure_agy(self):
        """Réapplique les réglages AGY enregistrés, un par un. Un réglage que le serveur n'accepte plus (« always-proceed »
        écrit par 4ecc57a) est ignoré avec une ligne de journal, sans valeur : jamais d'exception au démarrage."""
        agy = self.state['settings']['agy']
        if not isinstance(agy, dict): return
        for cle in ('model','effort','mode','permission_mode'):
            if not isinstance(agy.get(cle), str) or not agy[cle]: continue
            if cle == 'permission_mode' and agy[cle] not in MODES_PERMIS:
                # 4ecc57a accepte encore yolo, bypass et always-proceed : notre liste les refuse quand même
                logging.getLogger('nc_engines').warning('Réglage AGY enregistré refusé (%s) : ignoré, valeur par défaut.', cle)
                agy.pop(cle, None)
                continue
            if cle == 'permission_mode' and agy[cle] != 'default' and not agy_accepte_permission_mode():
                # cet agy n'a pas --permission-mode : tout autre mode ferait échouer chaque tour
                logging.getLogger('nc_engines').warning('Réglage AGY enregistré refusé (%s) : cet agy n\'a qu\'un mode, ignoré.', cle)
                agy.pop(cle, None)
                continue
            try:
                self.original['update_session'](**{cle:agy[cle]})
            except (ValueError, TypeError):
                logging.getLogger('nc_engines').warning('Réglage AGY enregistré refusé (%s) : ignoré, valeur par défaut.', cle)
                agy.pop(cle, None)

    def occupe(self):
        return self.lock.locked() or self.agy_en_cours > 0

    def par_pc(self):
        """Vrai si l'AGY upstream isole une session par PC (session_key, depuis 1ae55f3)."""
        return bool(compatibles(self.original['run_agy'], session_key='default'))

    def appel(self, nom, *args, session_key=None, **valeurs):
        fn = self.original[nom]
        return fn(*args, **valeurs, **compatibles(fn, session_key=session_key))

    def oublie_memoire(self, session_key=None, tout=False):
        versions = getattr(self.up, '_LAST_INJECTED_MEMORY_VERSIONS', None)
        if tout and isinstance(versions, dict): versions.clear()
        fn = self.up._reset_memory_injection
        fn(**compatibles(fn, session_key=session_key))

    def inject(self, version, session_key=None, **_futurs):
        # Nos CLI reçoivent la mémoire dans run() ; seul AGY passe par l'injection upstream.
        if self.state['engine'] != 'agy': return False
        return self.should_inject(version, **compatibles(self.should_inject, session_key=session_key))

    def session(self, session_key=None, **_futurs):
        # Nos CLI : une seule session partagée par tous les PC, la clé est ignorée.
        engine = self.state['engine']
        if engine == 'agy': return dict(self.appel('get_session_info', session_key=session_key), engine='agy')
        settings = self.state['settings'].get(engine, {})
        ident = self.state['active'].get(engine)
        conv = next((c for c in self.state['conversations'] if c['id']==ident), {})
        return dict(engine=engine, model=settings.get('model',''), effort=settings.get('effort',''),
                    mode='plan', permission_mode='request-review', conversation_id=ident,
                    has_active_session=bool(conv.get('history')), turns=len(conv.get('history',[])))

    def models(self, engine=None):
        engine = engine or self.state['engine']
        if engine == 'agy': return self.agy_models
        if engine == 'codex':
            path = Path.home()/'.codex/models_cache.json'
            if path.is_file() and path.stat().st_size < 8*1024*1024:
                try:
                    data = json.loads(path.read_text())
                    return [dict(id=m['slug'],name=m.get('display_name',m['slug']),efforts=[e['effort'] for e in m.get('supported_reasoning_levels',[])])
                            for m in data.get('models',[])[:100] if isinstance(m,dict) and isinstance(m.get('slug'),str)]
                except (ValueError, KeyError, TypeError, OSError): pass
        return []  # Ne pas présenter une liste inventée comme celle du compte distant.

    def snapshot(self, session_key=None):
        return dict(session=self.session(session_key), engines=[dict(id=k,name=v,installed=bool(executable(k)),models=self.models(k),
            permission_modes=modes_permis(k),
            efforts=(['low','medium','high'] if k=='agy' else ['low','medium','high','xhigh','max'] if k=='claude' else ['low','medium','high','xhigh','max','ultra'] if k=='codex' else [])) for k,v in ENGINES.items()],
            shared_session=self.state['engine'] != 'agy' or not self.par_pc(), context_limit=32000)

    def choose(self, session_key=None, **values):
        if self.occupe(): raise ValueError('Une réponse est en cours ; attends avant de changer de moteur.')
        if set(values)-{'engine','model','effort','mode','permission_mode'}: raise ValueError('Réglage inconnu.')
        engine = values.get('engine',self.state['engine'])
        if engine not in ENGINES: raise ValueError('Moteur inconnu.')
        if engine != self.state['engine'] and not executable(engine): raise ValueError('Installe et authentifie ce CLI sur la machine du runner.')
        if values.get('permission_mode') not in (None,'') and values['permission_mode'] not in MODES_PERMIS:
            raise ValueError('Mode de permission refusé.')
        if engine == 'agy' and values.get('permission_mode') not in (None,'','default') and not agy_accepte_permission_mode():
            raise ValueError('Cette version d\'agy n\'a qu\'un mode de permission (par défaut).')
        if engine == 'agy':
            donnes = {k:v for k,v in values.items() if k!='engine'}
            self.appel('update_session', session_key=session_key, **donnes)
            # Seulement ce que l'utilisateur a donné, fusionné aux anciens réglages : jamais le dict de session du serveur
            # (permission_mode par défaut, session_token), que 94a3a93 refuserait ou qui n'a rien à faire dans ce fichier
            result = {k:v for k,v in self.state['settings'].get('agy',{}).items() if k in ('model','effort','mode','permission_mode')}
            result.update({k:v for k,v in donnes.items() if v})
        else:
            if any(values.get(k) not in (None,'',v) for k,v in (('mode','plan'),('permission_mode','request-review'))):
                raise ValueError('Ce moteur utilise le mode plan avec ses protections habituelles.')
            result = dict(self.state['settings'].get(engine,{}))
            result.update({k:v for k,v in values.items() if k in ('model','effort') and v is not None})
            commande(engine, executable(engine) or engine, result.get('model',''), result.get('effort',''))
        change = engine != self.state['engine']
        state = dict(self.state, engine=engine, settings=dict(self.state['settings'], **{engine:result}))
        atomique(self.path,state); self.state = state
        self.up.KNOWN_MODELS = self.models()
        self.oublie_memoire(session_key, tout=change)
        return self.session(session_key)

    async def reset(self, session_key=None, **_futurs):
        if self.occupe(): raise ValueError('Une réponse est en cours.')
        async with self.lock:
            if self.state['engine']=='agy': return await self.appel('reset_session_async', session_key=session_key)
            active=dict(self.state['active']); active.pop(self.state['engine'],None)
            state=dict(self.state,active=active); atomique(self.path,state); self.state=state
            return self.session()

    def conversations(self, limit=8):
        if self.state['engine']=='agy': return self.original['list_recent_conversations'](limit=limit)
        return [dict(id=c['id'],title=c['title'],engine=c['engine']) for c in reversed(self.state['conversations']) if c['engine']==self.state['engine']][:max(0,min(limit,30))]

    def history(self, ident, max_turns=15):
        if self.state['engine']=='agy': return self.original['get_conversation_history'](ident,max_turns=max_turns)
        return next((c['history'][-max(1,min(max_turns,20)):] for c in self.state['conversations'] if c['id']==ident and c['engine']==self.state['engine']), [])

    def resume(self, ident, session_key=None, **_futurs):
        if self.occupe(): raise ValueError('Une réponse est en cours.')
        if self.state['engine']=='agy': return self.appel('resume_conversation', ident, session_key=session_key)
        if not any(c['id']==ident and c['engine']==self.state['engine'] for c in self.state['conversations']): raise ValueError('Conversation inconnue pour ce moteur.')
        state=dict(self.state,active=dict(self.state['active'],**{self.state['engine']:ident}))
        atomique(self.path,state); self.state=state; self.up._reset_memory_injection()
        return dict(session=self.session(),history=self.history(ident))

    def delete(self, ident):
        if self.occupe(): return dict(success=False,error='Une réponse est en cours.')
        if self.state['engine']=='agy': return self.original['delete_all_conversations']() if ident=='all' else self.original['delete_conversation'](ident)
        engine=self.state['engine']
        before=len(self.state['conversations'])
        conversations=[c for c in self.state['conversations'] if c['engine']!=engine or (ident!='all' and c['id']!=ident)]
        active=dict(self.state['active'])
        if ident=='all' or active.get(engine)==ident: active.pop(engine,None)
        state=dict(self.state,active=active,conversations=conversations); atomique(self.path,state); self.state=state
        return dict(success=before!=len(self.state['conversations']))

    def usage(self):
        if self.state['engine']=='agy': return self.original['get_token_usage']()
        return dict(engine=self.state['engine'],tokens_available=False,message='Les tokens de ce CLI ne sont pas agrégés par JARVIS.')

    async def run(self, prompt, timeout=120, model=None, effort=None, mode=None,
                  continue_session=True, reset_session_flag=False, permission_mode=None, session_key=None, **futurs):
        def failure(message): return dict(success=False,output='',error=message,session=self.session(session_key))
        if ia_coupee(): return failure('L’IA est coupée sur ce PC (réglage IA_MODE=non) : aucun moteur n’est lancé.')
        if self.lock.locked(): return failure('Une autre requête JARVIS est déjà en cours.')
        # /run n'est jamais contrôlé par l'upstream (P2-2 de 94a3a93) : un agent qui a SECRET_KEY y demandait
        # bypassPermissions. Hors de notre liste : le mode de la session (aucun de nos clients n'envoie ce champ).
        if permission_mode not in MODES_PERMIS: permission_mode = None
        if self.state['engine']=='agy':
            # Pas de verrou commun : chaque PC a sa session et l'upstream refuse lui-même deux requêtes sur la même.
            # Le compteur empêche seulement de changer de moteur ou de réinitialiser pendant ce temps.
            fn=self.original['run_agy']
            if not agy_accepte_permission_mode(): permission_mode = 'default'
            self.agy_en_cours+=1
            try:
                resultat=await fn(prompt=prompt,timeout=timeout,model=model,effort=effort,mode=mode,
                    continue_session=continue_session,reset_session_flag=reset_session_flag,permission_mode=permission_mode,
                    **compatibles(fn,session_key=session_key,**futurs))
                if isinstance(resultat,dict):
                    for champ in ('output','error'):
                        if isinstance(resultat.get(champ),str): resultat[champ]=sans_secrets(resultat[champ],dossier_runner(self.up))
                return resultat
            finally: self.agy_en_cours-=1
        if self.agy_en_cours: return failure('Une autre requête JARVIS est déjà en cours.')
        # Nos CLI : session partagée par tous les PC, un seul verrou ; session_key et mots-clés futurs ignorés.
        async with self.lock:
            engine=self.state['engine']
            path=executable(engine)
            if not path: return failure('CLI '+ENGINES[engine]+' absent sur la machine du runner.')
            if prompt.lstrip().startswith('/'):
                return failure('Les commandes / d’AGY ne sont pas disponibles avec ce moteur. Utilise les réglages JARVIS.')
            settings=self.state['settings'].get(engine,{})
            ident=self.state['active'].get(engine) if continue_session and not reset_session_flag else None
            conv=next((c for c in self.state['conversations'] if c['id']==ident),None)
            history=list(conv['history']) if conv else []
            while sum(len(h['prompt'])+len(h['response']) for h in history)>12000 or len(history)>10: history.pop(0)
            context='\n\n'.join('Utilisateur : '+h['prompt']+'\nAssistant : '+h['response'] for h in history)
            # Choix cliquables (issue #7) : le gateway retire ce marqueur et en fait des boutons (nc_choix)
            directive=("Consigne : sois direct, concis et précis. Utilise Markdown et LaTeX si pertinent. Pas de bavardage superflu. "
                       "Seulement si l'utilisateur doit choisir parmi quelques options (2 à 5), ajoute en toute dernière ligne "
                       "[CHOIX: Option A | Option B], avec des options courtes.")
            full=directive+'\n\n'+(('Historique récent de cette conversation JARVIS :\n'+context+'\n\nNouvelle demande :\n' if context else '')+prompt)
            memory=self.up.render_memory_prompt()
            if memory: full=memory+'\n\n'+full
            try:
                args=commande(engine,path,model if model is not None else settings.get('model',''),effort if effort is not None else settings.get('effort',''))
                # Dossier de travail : un dossier vide jeté après la demande, jamais celui du serveur (où se trouve .env)
                # En local le moteur tourne dans une unité où le dossier du backend (.env) est inaccessible (voir isoler)
                travail=await asyncio.to_thread(dossier_travail)
                try:
                    iso=await isoler(engine,args,travail,timeout,dossier_runner(self.up))
                    erreurs=[]
                    if iso: code,out=await process(iso[0],full,timeout,travail,iso[1],iso[2],erreurs)
                    else: code,out=await process(args,full,timeout,travail,env_moteur(engine),None,erreurs)
                finally: shutil.rmtree(travail,ignore_errors=True)
                if code==CODE_REFUS_ISOLATION and iso: return failure(MESSAGE_NON_ISOLE)
                if code and iso and (refus:=ecriture_refusee(''.join(erreurs))): return failure(refus)
                if code: return failure(ENGINES[engine]+' a échoué (code '+str(code)+'). Vérifie son authentification et le modèle sur le runner.')
                answer=sans_secrets(reponse(engine,out),dossier_runner(self.up))
                if continue_session:
                    if not conv:
                        conv=dict(id='nc-'+uuid.uuid4().hex,engine=engine,title=prompt[:100],history=[])
                    history.append(dict(prompt=prompt[:16000],response=answer[:16000]))
                    while sum(len(h['prompt'])+len(h['response']) for h in history)>12000 or len(history)>10: history.pop(0)
                    conversations=[c for c in self.state['conversations'] if c['id']!=conv['id']]+[dict(conv,history=history)]
                    state=dict(self.state,conversations=conversations[-30:],active=dict(self.state['active'],**{engine:conv['id']}))
                    await asyncio.to_thread(atomique,self.path,state); self.state=state
                return dict(success=True,output=answer,error=None,session=self.session())
            except IsolationImpossible as e: return failure(str(e))
            except asyncio.TimeoutError: return failure('Délai dépassé ; le processus moteur a été arrêté.')
            except (ValueError,OSError): return failure('Réponse moteur invalide ou indisponible. Vérifie le modèle, la réflexion et l’authentification du CLI.')


def install(upstream):
    engines=Engines(upstream)
    upstream.run_agy=engines.run; upstream.get_session_info=engines.session; upstream.update_session=engines.choose
    upstream.reset_session_async=engines.reset; upstream.list_recent_conversations=engines.conversations
    upstream.get_conversation_history=engines.history; upstream.resume_conversation=engines.resume
    upstream.delete_conversation=engines.delete; upstream.delete_all_conversations=lambda:engines.delete('all')
    upstream.get_token_usage=engines.usage; upstream.KNOWN_MODELS=engines.models()
    upstream._should_inject_memory=engines.inject
    return engines

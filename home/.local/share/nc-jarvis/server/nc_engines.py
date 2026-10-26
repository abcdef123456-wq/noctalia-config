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
    valeur = None
    try:
        for ligne in (Path.home()/'.config/nc/reglages.conf').read_text(encoding='utf-8').splitlines():
            cle, sep, v = ligne.partition('=')
            if sep and cle.strip() == 'IA_MODE': valeur = v.strip().strip('"')
    except (OSError, ValueError): pass
    return valeur == 'non'


async def process(args, prompt, timeout, cwd, env=None):
    """Sorties bornées, groupe entier tué sur timeout/annulation/débordement."""
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
        out, _, _ = await asyncio.wait_for(asyncio.gather(*tasks), timeout)
        await asyncio.wait_for(p.wait(), 2)
        return p.returncode, out.decode(errors='replace')
    finally:
        # Un enfant peut encore détenir les tubes même si son parent vient de sortir.
        with contextlib.suppress(ProcessLookupError): os.killpg(p.pid, signal.SIGKILL)
        for task in tasks: task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        await p.wait()


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
                travail=tempfile.mkdtemp(prefix='nc-jarvis-')
                try: code,out=await process(args,full,timeout,travail,env_moteur(engine))
                finally: shutil.rmtree(travail,ignore_errors=True)
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

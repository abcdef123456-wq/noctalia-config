"""Le bac commun des IA en ligne de commande (nc-bac, utilisé par nc-noeud ET nc-ia) : Claude Code, Codex, Gemini CLI,
Qwen Code et OpenCode sont lancés avec les mêmes propriétés systemd, chacun voit ses propres identifiants et pas ceux
des autres. Deux étages :
  - un FAUX systemd-run qui note ses arguments puis exécute la commande (aucun vrai bac, aucun bus) ;
  - le VRAI bac (systemd-run --user, faux HOME sous /dev/shm comme BacReel de test_noeud) : un faux moteur lit son faux
    jeton, ne lit ni ~/.ssh factice ni le jeton d'un autre, n'écrit pas dans ~, et sa sortie arrive ligne par ligne.
Aucune vraie IA n'est lancée : les « moteurs » sont des scripts shell."""
import base64
import contextlib
import fcntl
import importlib.machinery
import importlib.util
import json
import os
import re
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import unittest
import unittest.mock

from tests.test_noeud import _bus_utilisateur, HOME_BAC

# Le bac met /dev/shm en lecture seule (ProtectSystem=strict + ReadOnlyPaths) : les faux HOME des tests vont donc sous
# $XDG_RUNTIME_DIR réel (/run/user/<uid>, un tmpfs à soi), jamais /dev/shm ni /tmp (que PrivateTmp masque). Repli sur
# HOME_BAC seulement si /run/user/<uid> n'existe pas.
_RUNDIR = os.environ.get("NC_TEST_VRAI_RUNTIME") or f"/run/user/{os.getuid()}"
RACINE_BAC = _RUNDIR if os.path.isdir(_RUNDIR) and os.access(_RUNDIR, os.W_OK) else HOME_BAC


def _racine_executable():
    """Les faux moteurs sont des scripts écrits sous RACINE_BAC : le dossier doit exister et permettre l'exécution
    (conteneur : /dev/shm est monté noexec)."""
    try:
        return os.path.isdir(RACINE_BAC) and not os.statvfs(RACINE_BAC).f_flag & os.ST_NOEXEC
    except OSError:
        return False


SANS_RACINE = unittest.skipUnless(_racine_executable(), "dossier des faux HOME absent ou monté sans exécution (noexec)")


def _purge_restes(prefixe):
    """P3-6 : efface les dossiers de tests laissés par un run précédent interrompu (même préfixe, à nous, vieux de plus
    de 10 min), sous /dev/shm comme sous /run/user/<uid>. Jamais rien d'autre."""
    import time as _t
    for base in ("/dev/shm", f"/run/user/{os.getuid()}", RACINE_BAC):
        with __import__("contextlib").suppress(OSError):
            for n in os.listdir(base):
                p = os.path.join(base, n)
                try:
                    st = os.lstat(p)
                    if (n.startswith(prefixe) and stat_module.S_ISDIR(st.st_mode) and st.st_uid == os.getuid()
                            and _t.time() - st.st_mtime > 600):
                        shutil.rmtree(p, ignore_errors=True)
                except OSError:
                    continue


import stat as stat_module


def _rmtree_force(d):
    """Supprime le faux HOME d'un test, même après un chmod 000, et même si le faux notify-send (lancé détaché par nc-ia)
    écrit notifs.log APRÈS le début du nettoyage : on recommence jusqu'à ce que le dossier ait vraiment disparu."""
    def _ch(f, p, _):
        with __import__("contextlib").suppress(OSError):
            os.chmod(os.path.dirname(p), 0o700)
            os.chmod(p, 0o700)
            f(p)
    import time as _t
    for _ in range(50):                                     # au plus ~5 s
        with __import__("contextlib").suppress(OSError):
            if sys.version_info >= (3, 12):
                shutil.rmtree(d, onexc=_ch)
            else:
                shutil.rmtree(d, onerror=_ch)
        if not os.path.lexists(d):
            return
        _t.sleep(0.1)


import sys

REPO = Path(__file__).resolve().parents[1]
BIN = REPO / "home/.local/bin"
IDENTS = {"claude": "claude", "codex": "codex", "gemini-cli": "gemini", "qwen": "qwen", "opencode": "opencode"}
# Le dossier (relatif à ~) où chaque moteur range ses identifiants, et le fichier-jeton FACTICE qu'on y met
JETONS = {"claude": ".claude/.credentials.json", "codex": ".codex/auth.json", "gemini-cli": ".gemini/oauth_creds.json",
          "qwen": ".qwen/oauth_creds.json", "opencode": ".local/share/opencode/auth.json"}
CONFIGS = {"claude": ".claude/settings.json", "codex": ".codex/config.toml", "gemini-cli": ".gemini/settings.json",
           "qwen": ".qwen/settings.json", "opencode": ".config/opencode/opencode.json"}


def jwt(payload, marque=None):
    """Un JWT FACTICE (signature bidon, jamais vérifiée) : header.payload.sig en base64url. Codex range chatgpt_account_id
    dans un claim imbriqué ; on y glisse aussi la marque, pour la relire côté test."""
    import base64
    corps = dict(payload)
    if marque is not None:
        corps["marque"] = marque
    def b(o):
        return base64.urlsafe_b64encode(json.dumps(o).encode()).rstrip(b"=").decode()
    return b({"alg": "none"}) + "." + b(corps) + ".sig"


EXP_CODEX = int(time.time()) + 10 * 86400                    # échéance fixe (pour retrouver le JWT exact en sortie)
_CODEX_CLAIMS = {"sub": "user-1", "email": "u@example.org", "https://api.openai.com/auth": {"chatgpt_account_id": "compte-1"}}


def contenu_jeton(ident, marque=None):
    """Un fichier d'identifiants FACTICE de la forme du vrai (noms de champs des moteurs), avec la marque JETON-<ident>
    dans le jeton d'accès, et des champs qui ne doivent JAMAIS entrer dans le bac (SECRET-…). Codex : jetons en JWT
    valides (chatgpt_account_id == account_id, sub/email stables)."""
    m = marque or f"JETON-{ident}"
    fin_ms = EXP_CODEX * 1000                                 # valide dix jours : la demande peut partir
    acces_codex = dict(_CODEX_CLAIMS, exp=EXP_CODEX)
    return {
        "claude": {"claudeAiOauth": {"accessToken": m, "refreshToken": "SECRET-REFRESH", "expiresAt": fin_ms, "scopes": ["user:inference"],
                                     "subscriptionType": "pro"},
                   "mcpOAuth": {"serveur": {"accessToken": "SECRET-MCP"}}},
        "codex": {"tokens": {"access_token": jwt(acces_codex, m), "refresh_token": "SECRET-REFRESH",
                             "id_token": jwt(_CODEX_CLAIMS), "account_id": "compte-1"},
                  "last_refresh": "2026-01-01T00:00:00Z", "OPENAI_API_KEY": "SECRET-CLE-CODEX"},
        "gemini-cli": {"access_token": m, "refresh_token": "SECRET-REFRESH", "expiry_date": fin_ms, "token_type": "Bearer"},
        "qwen": {"access_token": m, "refresh_token": "SECRET-REFRESH", "expiry_date": fin_ms, "token_type": "Bearer",
                 "resource_url": "portal.qwen.ai"},
        "opencode": {"anthropic": {"type": "oauth", "access": m, "refresh": "SECRET-REFRESH", "expires": fin_ms},
                     "openai": {"type": "api", "key": "SECRET-CLE-OPENCODE"},
                     "distant": {"type": "wellknown", "key": "k", "token": "SECRET-WELLKNOWN"}},
    }[ident]


def rafraichi(ident, marque="RAFRAICHI"):
    """Ce qu'un moteur écrit après un rafraîchissement normal : seul le jeton d'accès (et sa date) change."""
    j = contenu_jeton(ident, marque)
    for k in ("mcpOAuth", "OPENAI_API_KEY", "openai", "distant"):
        j.pop(k, None)
    return j


def marqueur(ident, marque):
    """La chaîne EXACTE qui doit apparaître dans la sortie d'un faux moteur qui lit sa copie du jeton (Codex : le JWT
    complet, puisque la marque y est encodée en base64 ; les autres : la marque telle quelle)."""
    return jwt(dict(_CODEX_CLAIMS, exp=EXP_CODEX), marque) if ident == "codex" else marque


def jeton_acces(ident, objet):
    def codex(o):                                           # la marque est un claim du JWT access_token
        import base64
        seg = o["tokens"]["access_token"].split(".")[1]
        seg += "=" * (-len(seg) % 4)
        return json.loads(base64.urlsafe_b64decode(seg)).get("marque")
    return {"claude": lambda o: o["claudeAiOauth"]["accessToken"], "codex": codex,
            "gemini-cli": lambda o: o["access_token"], "qwen": lambda o: o["access_token"],
            "opencode": lambda o: o["anthropic"]["access"]}[ident](objet)

# Le faux systemd-run : une ligne par argument dans le journal, puis exécute ce qui suit « -- » (sans bac)
FAUX_SYSTEMD_RUN = """#!/bin/sh
{ echo "--LANCEMENT--"; printf '%s\\n' "$@"; } >> "@REEL@/sr.journal"
while [ "$1" != "--" ]; do shift; done; shift
exec "$@"
"""

# Un faux moteur : montre ce qu'il lit et écrit. Argument 1 de l'environnement : MOTEUR_JETON = son jeton
MOTEUR = r"""#!/bin/sh
[ "$1" = "--version" ] && { echo "opencode v2.1.2"; exit 0; }
# Claude Code répond en JSON (stream-json), les autres en texte
out() { case "$0" in */claude) printf '{"type":"stream_event","event":{"delta":{"type":"text_delta","text":"%s\\n"}}}\n' "$(printf %s "$1" | tr '"' "'")";; *) echo "$1";; esac; }
[ -f "@REEL@/nc-test.env" ] && . "@REEL@/nc-test.env"
{ echo "ARGS $*"; echo "ENTREE $(cat)"; } >> "@REEL@/moteur.log" 2>/dev/null
out "debut"
lire() { if c=$(cat "$1" 2>/dev/null); then out "LU $1 $c"; else out "REFUSE $1"; fi; }
for f in $NC_TEST_FICHIERS; do lire "$f"; done
for f in $NC_TEST_RELATIFS; do lire "$HOME/$f"; done
for f in $NC_TEST_RAFRAICHIR; do printf '%s\n' "$NC_TEST_CONTENU" > "$HOME/$f"; done
for f in $NC_TEST_RENOMMER; do printf '%s\n' "$NC_TEST_CONTENU" > "$HOME/$f.tmp" && mv "$HOME/$f.tmp" "$HOME/$f"; done
for f in $NC_TEST_CASSER; do echo 'pas du json' > "$HOME/$f"; done
[ -n "$NC_TEST_EXPORTER" ] && cp -r "$HOME" "$NC_TEST_EXPORTER"
for f in $NC_TEST_IMBRIQUER; do yes '[' | head -n 200000 | tr -d '\n' > "$HOME/$f"; done
for f in $NC_TEST_LIEN; do rm -rf "$HOME/$f" && ln -s "$NC_TEST_CIBLE" "$HOME/$f" && out "LIEN $f"; done
for f in $NC_TEST_LIEN_DUR; do rm -f "$HOME/$f" && ln "$NC_TEST_CIBLE" "$HOME/$f" && out "LIEN-DUR $f"; done
for d in $NC_TEST_LISTER; do if l=$(ls -A "$d" 2>/dev/null); then out "LISTE $d [$(echo $l)]"; else out "PASLISTE $d"; fi; done
for f in $NC_TEST_CREER_CHEZ_MOI; do mkdir -p "$(dirname "$HOME/$f")" && echo x > "$HOME/$f" && out "CREE-CHEZ-MOI $f"; done
ecrire() { if ( echo x > "$1" ) 2>/dev/null; then out "ECRIT $1"; else out "NONECRIT $1"; fi; }
for f in $NC_TEST_ECRIRE; do ecrire "$f"; done
out "CWD $(pwd -P)"
trap 'exit 0' TERM        # arrêté proprement : l'unité ne reste pas « en échec » (une notification de panne sur le bureau)
sleep ${NC_TEST_PAUSE:-0} & wait $!
out "fin"
"""


def charger_ia(home, path):
    env = {"HOME": str(home), "XDG_RUNTIME_DIR": str(home / "run"), "XDG_STATE_HOME": str(home / ".local/state"),
           "XDG_CONFIG_HOME": str(home / ".config"), "XDG_DATA_HOME": str(home / ".local/share"),
           "XDG_CACHE_HOME": str(home / ".cache"), "PATH": path, "NC_LANGUE": "fr", "NC_IA_EN_LIGNE": "1"}
    with unittest.mock.patch.dict(os.environ, env):
        l = importlib.machinery.SourceFileLoader("nc_ia_bac", str(BIN / "nc-ia"))
        m = importlib.util.module_from_spec(importlib.util.spec_from_loader("nc_ia_bac", l))
        avant = os.environ["PATH"]
        l.exec_module(m)
        os.environ["PATH"] = avant
    m.HOME = home
    return m


class Base(unittest.TestCase):
    racine = RACINE_BAC

    def faux_home(self):
        _purge_restes("nc-bac-ia-")                              # P3-6 : restes d'un run interrompu (vieux, à nous)
        d = tempfile.mkdtemp(prefix="nc-bac-ia-", dir=self.racine)
        # Nettoyage même si le moteur a retiré des droits (chmod 000) sur un sous-dossier
        self.addCleanup(lambda: _rmtree_force(d))
        home = Path(d)
        (home / ".local/bin").mkdir(parents=True)
        (home / "run").mkdir(mode=0o700)
        (home / ".ssh").mkdir(mode=0o700)
        (home / ".ssh/id_ed25519").write_text("FAUSSE-CLE-SSH")
        (home / ".config/nc").mkdir(parents=True)
        (home / ".config/nc/ia.conf").write_text("ANTHROPIC_API_KEY=FAUSSE-CLE-API")
        for ident, rel in JETONS.items():
            f = home / rel
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(json.dumps(contenu_jeton(ident)))
        for ident, rel in CONFIGS.items():
            f = home / rel
            f.parent.mkdir(parents=True, exist_ok=True)
            # Claude Code : un JSON dont seules quelques clés passent (jamais hooks, env, apiKeyHelper)
            f.write_text(json.dumps({"language": "CONFIG-claude", "hooks": {"Stop": "SECRET-HOOK"}, "env": {"K": "SECRET-ENV"},
                                     "apiKeyHelper": "SECRET-AIDE"}) if ident == "claude" else "CONFIG-" + ident)
        for prog in IDENTS.values():
            f = home / ".local/bin" / prog
            f.write_text(MOTEUR.replace("@REEL@", str(home)))
            f.chmod(0o755)
        # Jamais une vraie notification sur le bureau : un faux notify-send devant
        f = home / ".local/bin/notify-send"
        f.write_text(f'#!/bin/sh\nprintf "%s\\n" "$*" >> "{home}/notifs.log"\n')
        f.chmod(0o755)
        return home

    def env_hote(self, path, **plus):
        """L'environnement de nc-ia pendant le test : faux HOME, runtime et état dans le faux HOME."""
        env = {"HOME": str(self.home), "XDG_RUNTIME_DIR": str(self.home / "run"), "XDG_STATE_HOME": str(self.home / ".local/state"),
               "XDG_CONFIG_HOME": str(self.home / ".config"), "XDG_DATA_HOME": str(self.home / ".local/share"),
               "XDG_CACHE_HOME": str(self.home / ".cache"), "PATH": path, "NC_IA_BAC": ""}
        for k in ("CLAUDE_CONFIG_DIR", "CODEX_HOME"):
            env[k] = ""
        # Aucune vraie clé d'API de la session ne doit changer le comportement (une clé fait passer un jeton expiré)
        for k in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "CLAUDE_CODE_OAUTH_TOKEN", "OPENAI_API_KEY", "CODEX_API_KEY",
                  "GEMINI_API_KEY", "GOOGLE_API_KEY", "DASHSCOPE_API_KEY", "QWEN_API_KEY", "OPENCODE_API_KEY",
                  "GOOGLE_GENERATIVE_AI_API_KEY", "OPENROUTER_API_KEY", "GROQ_API_KEY", "MISTRAL_API_KEY",
                  "DEEPSEEK_API_KEY", "XAI_API_KEY"):
            env[k] = ""
        env.update(plus)
        p = unittest.mock.patch.dict(os.environ, env)
        p.start()
        self.addCleanup(p.stop)

    def oublier_sonde(self):
        self.m._BAC["tient"] = None
        (self.home / "run/nc-ia-bac").unlink(missing_ok=True)

    def base(self):
        return self.home / "run/nc-ia/bac"

    def notifs(self, attente=3):
        """Les notifications (le faux notify-send est lancé sans attendre : on lui laisse le temps). attente courte pour
        vérifier l'ABSENCE de notification."""
        f = self.home / "notifs.log"
        fin = time.monotonic() + attente
        while not f.exists() and time.monotonic() < fin:
            time.sleep(0.05)
        if attente <= 0.5:                                       # on veut voir si une notification apparaît : on patiente
            time.sleep(attente)
        return f.read_text() if f.exists() else ""

    def journal_ia(self):
        f = self.home / ".local/state/nc-ia/journal"
        return f.read_text() if f.exists() else ""

    def lancer_moteur(self, m, ident, **env):
        """Lance le moteur par le chemin de nc-ia (appel_programme, ou appel_claude) : les lignes de sa sortie."""
        # La liste blanche ne transmet pas NC_TEST_* au moteur : un fichier de son faux HOME les lui donne
        (self.home / "nc-test.env").write_text("".join(f"export {k}='{v}'\n" for k, v in env.items()))
        with unittest.mock.patch.dict(os.environ):
            if ident == "claude":
                gen = m.appel_claude("c", "t", None, "question")
            else:
                gen = m.appel_programme(ident, "c", "t", None, "question")
            return list(gen)


@SANS_RACINE
class AvecFauxSystemdRun(Base):
    def setUp(self):
        self.home = self.faux_home()
        fb = self.home / "faux"
        fb.mkdir()
        sr = fb / "systemd-run"
        sr.write_text(FAUX_SYSTEMD_RUN.replace("@REEL@", str(self.home)))
        sr.chmod(0o755)
        sc = fb / "systemctl"
        # Le faux systemd-run exécute le moteur directement (pas de vraie unité) : is-active répond « inactive » pour
        # que finir() nettoie et rapporte. kill/reset-failed : sans effet.
        sc.write_text('#!/bin/sh\ncase "$*" in *is-active*) for u in "$@"; do case "$u" in *.service) echo inactive;; '
                      'esac; done;; esac\nexit 0\n')
        sc.chmod(0o755)
        self.journal = self.home / "sr.journal"
        self.fb = fb
        self.m = charger_ia(self.home, f"{fb}:{self.home}/.local/bin:/usr/bin:/bin")
        self.env_hote(f"{fb}:{self.home}/.local/bin:/usr/bin:/bin")
        self.oublier_sonde()

    def lancements(self):
        if not self.journal.exists():
            return []
        blocs, cur = [], None
        for l in self.journal.read_text().splitlines():
            if l == "--LANCEMENT--":
                cur = []
                blocs.append(cur)
            else:
                cur.append(l)
        return blocs

    def props(self, bloc):
        avant = bloc[:bloc.index("--")]                       # les -p du programme lancé (-p de gemini…) viennent après
        return [avant[i + 1] for i, a in enumerate(avant) if a == "-p" and i + 1 < len(avant)]

    def test_chaque_moteur_dans_le_meme_bac(self):
        communes = {"PrivateUsers=yes", "NoNewPrivileges=yes", "PrivatePIDs=yes", "PrivateDevices=yes", "PrivateIPC=yes",
                    "ProtectControlGroups=yes", "SystemCallFilter=~@debug @keyring", "ProtectHome=read-only", "PrivateTmp=yes", "RestrictAddressFamilies=AF_INET AF_INET6",
                    "ReadOnlyPaths=" + str(self.home)}
        for ident in IDENTS:
            with self.subTest(ident):
                self.journal.unlink(missing_ok=True)
                self.oublier_sonde()
                self.lancer_moteur(self.m, ident, NC_TEST_FICHIERS="")
                blocs = self.lancements()
                # la sonde, (pour OpenCode : « opencode --version », dans le bac aussi), puis le vrai lancement
                self.assertEqual(len(blocs), 3 if ident == "opencode" else 2, blocs)
                reel = blocs[-1]
                props = set(self.props(reel))
                self.assertTrue(communes <= props, communes - props)
                for sonde_prop in self.props(blocs[0]):
                    if sonde_prop.startswith(("PrivateUsers", "NoNewPrivileges", "PrivatePIDs", "PrivateDevices", "PrivateIPC", "SystemCallFilter", "ProtectHome")):
                        self.assertIn(sonde_prop, props)
                self.assertTrue(any(p.startswith("RuntimeMaxSec=") and int(p.split("=")[1]) >= 180 for p in props), props)
                self.assertTrue(any(a.startswith("--unit=nc-ia-") for a in reel))
                self.assertIn("--pipe", reel)
                self.assertIn("--setenv=PATH", reel)
                # le réseau reste ouvert : pas de PrivateNetwork, AF_INET et AF_INET6 seulement (pas d'AF_UNIX)
                self.assertNotIn("PrivateNetwork=yes", props)
                self.assertNotIn("AF_UNIX", " ".join(props))
                self.assertIn(f'InaccessiblePaths="{self.home}/.ssh"', props)
                self.assertIn(f'InaccessiblePaths="{self.home}/.config/nc"', props)
                # $XDG_RUNTIME_DIR : un tmpfs vide en lecture seule, où seuls les dossiers de CETTE demande sont remontés
                self.assertIn(f"TemporaryFileSystem={self.home}/run:ro", props)
                self.assertNotIn(f'InaccessiblePaths="{self.home}/run"', props)
                lies = sorted(p for p in props if p.startswith("BindPaths="))
                unite = [a for a in reel if a.startswith("--unit=")][0][len("--unit=nc-ia-"):]
                self.assertEqual(lies, [f"BindPaths={self.base()}/nc-ia-home-{unite}", f"BindPaths={self.base()}/nc-ia-travail-{unite}"])
                lecture = [p for p in props if p.startswith("BindReadOnlyPaths=")]
                self.assertEqual(lecture, [f"BindReadOnlyPaths={self.base()}/nc-ia-conf-{unite}"] if ident in ("gemini-cli", "qwen") else [])

    def test_aucun_vrai_dossier_de_moteur_lisible_ni_inscriptible(self):
        """Ni le sien ni ceux des autres : le moteur travaille dans un faux dossier personnel (copie jetable)."""
        (self.home / ".claude.json").write_text("{}")
        tous = [".claude", ".claude.json", ".codex", ".gemini", ".qwen", ".config/opencode", ".local/share/opencode"]
        for ident in IDENTS:
            with self.subTest(ident):
                self.journal.unlink(missing_ok=True)
                self.oublier_sonde()
                self.lancer_moteur(self.m, ident, NC_TEST_FICHIERS="")
                props = self.props(self.lancements()[-1])
                inacc = {p[len('InaccessiblePaths="'):-1] for p in props if p.startswith("InaccessiblePaths=")}
                for rel in tous:
                    self.assertIn(str(self.home / rel), inacc, f"{ident} ne doit pas lire le vrai {rel}")
                self.assertFalse([p for p in props if p.startswith("ReadWritePaths=")])
                rw = sorted(p[len("BindPaths="):] for p in props if p.startswith("BindPaths="))
                self.assertEqual(len(rw), 2, rw)
                self.assertIn("/run/nc-ia/bac/nc-ia-home-", rw[0])    # le faux dossier personnel
                self.assertIn("/run/nc-ia/bac/nc-ia-travail-", rw[1])  # le dossier de travail vide
                for rel in tous:
                    self.assertFalse(any(r.startswith(str(self.home / rel)) for r in rw), f"{ident} n'écrit pas dans {rel}")
                # seul ReadOnlyPaths attendu : le faux home et /dev/shm (ProtectSystem=strict + ReadOnlyPaths=-/dev/shm)
                autorises = {f"ReadOnlyPaths={self.home}", "ReadOnlyPaths=-/dev/shm"}
                self.assertFalse([p for p in props if p.startswith("ReadOnlyPaths=") and p not in autorises])

    def test_home_du_moteur_et_copie_de_ses_fichiers(self):
        (self.home / ".claude.json").write_text('{"c": 1}')
        for ident, rel in JETONS.items():
            with self.subTest(ident):
                sortie = "".join(self.lancer_moteur(self.m, ident, NC_TEST_RELATIFS=f"{rel} {CONFIGS[ident]}"))
                self.assertIn(marqueur(ident, f"JETON-{ident}"), sortie)  # sa copie du jeton
                for autre in JETONS:
                    if autre != ident:
                        self.assertNotIn(marqueur(autre, f"JETON-{autre}"), sortie)
                self.assertNotIn("SECRET-", sortie)                      # ni mcpOAuth, ni entrées api/wellknown, ni hooks
                self.assertIn("/run/nc-ia/bac/nc-ia-home-", sortie)      # le chemin lu est celui du faux dossier personnel

    def test_sortie_et_dossier_de_travail(self):
        sortie = self.lancer_moteur(self.m, "qwen", NC_TEST_FICHIERS="")
        cwd = [l for l in sortie if l.startswith("CWD")][0]
        self.assertIn("/run/nc-ia/bac/nc-ia-travail-", cwd)               # /tmp est privé dans le bac
        self.assertFalse(os.path.exists(cwd.split(" ", 1)[1].strip()), "dossier supprimé après la demande")
        self.assertEqual(sorted(os.listdir(self.base())), [], "travail, réglages et faux dossier personnel supprimés")

    def regler(self, texte):
        conf = self.home / ".config/nc/reglages.conf"
        conf.write_text(texte)
        self.m._reglages = None

    def test_sans_bac_les_moteurs_sont_refuses(self):
        """Le bac ne tient pas : par défaut, aucun moteur en ligne de commande n'est lancé (plus de repli silencieux)."""
        (self.fb / "systemd-run").write_text("#!/bin/sh\nexit 1\n")
        for ident in IDENTS:
            with self.subTest(ident):
                self.journal.unlink(missing_ok=True)
                self.oublier_sonde()
                with self.assertRaises(self.m.ErreurIA) as e:
                    self.lancer_moteur(self.m, ident, NC_TEST_FICHIERS="")
                self.assertIn("le bac des IA n'est pas disponible ici", str(e.exception))
                self.assertIn("IA_BAC_REPLI", str(e.exception))
        self.assertFalse((self.home / "moteur.log").exists(), "aucun moteur n'a tourné")
        self.assertFalse(self.m.bac_disponible())

    def test_repli_autorise_explicitement(self):
        (self.fb / "systemd-run").write_text("#!/bin/sh\nexit 1\n")
        self.regler("IA_BAC_REPLI=oui\n")
        for ident in IDENTS:
            with self.subTest(ident):
                self.oublier_sonde()
                sortie = self.lancer_moteur(self.m, ident, NC_TEST_FICHIERS="")
                self.assertIn("fin\n", sortie)

    def test_un_echec_de_sonde_n_est_pas_garde(self):
        """Seul le succès est gardé 5 minutes : un échec passager ne retire pas le bac aux moteurs suivants."""
        (self.fb / "systemd-run").write_text("#!/bin/sh\nexit 1\n")
        self.oublier_sonde()
        self.assertFalse(self.m.bac_disponible())
        self.assertFalse((self.home / "run/nc-ia-bac").exists())
        (self.fb / "systemd-run").write_text(FAUX_SYSTEMD_RUN.replace("@REEL@", str(self.home)))
        self.oublier_sonde()
        self.assertTrue(self.m.bac_disponible())
        self.assertEqual((self.home / "run/nc-ia-bac").read_text(), "1")
        # un vieux « 0 » écrit par une version précédente ne compte pas
        self.m._BAC["tient"] = None
        (self.home / "run/nc-ia-bac").write_text("0")
        self.assertTrue(self.m.bac_disponible())

    def test_bac_qui_ne_se_construit_pas_refuse(self):
        """La sonde dit « disponible » mais argv_bac renvoie None (module illisible, chemin avec guillemet) : jamais hors du bac."""
        self.oublier_sonde()
        self.assertTrue(self.m.bac_disponible())
        self.regler("IA_BAC_REPLI=oui\n")                      # même avec le repli permis : le bac « tient », il doit servir
        with unittest.mock.patch.object(self.m, "argv_bac", return_value=None):
            with self.assertRaises(self.m.ErreurIA):
                self.lancer_moteur(self.m, "codex", NC_TEST_FICHIERS="")
        self.assertFalse((self.home / "moteur.log").exists())

    def test_interdits_invalides_refuse_meme_avec_repli(self):
        self.regler("IA_BAC_REPLI=oui\nNOEUD_BAC_INTERDITS=/etc\n")
        self.oublier_sonde()
        with self.assertRaises(self.m.ErreurIA) as e:
            self.lancer_moteur(self.m, "codex", NC_TEST_FICHIERS="")
        self.assertIn("NOEUD_BAC_INTERDITS", str(e.exception))
        self.assertFalse((self.home / "moteur.log").exists())

    def test_nouveaux_chemins_secrets_interdits(self):
        crees = [".config/github-copilot", ".config/JetBrains", ".config/sops", ".vault-token", ".continue", ".config/aichat",
                 ".cache/huggingface", ".config/Cursor/User/globalStorage",
                 # P2-3 : états et caches des moteurs, et l'état de nc-ia
                 ".local/state/opencode", ".cache/opencode", ".cache/claude-cli-nodejs", ".local/state/claude",
                 ".local/state/nc-ia", ".omp", ".local/share/omp", ".local/state/omp", ".cache/omp"]
        for r in crees:
            f = self.home / r
            f.parent.mkdir(parents=True, exist_ok=True)
            f.mkdir(exist_ok=True) if not r.endswith("token") else f.write_text("x")
        self.oublier_sonde()
        self.lancer_moteur(self.m, "codex", NC_TEST_FICHIERS="")
        inacc = {p[len('InaccessiblePaths="'):-1] for p in self.props(self.lancements()[-1]) if p.startswith("InaccessiblePaths=")}
        for r in crees:
            self.assertIn(str(self.home / r), inacc, r)

    def test_lanceur_python_noms_et_valeurs_litterales(self):
        """nc-bac : « NOM » passe par --setenv (valeur HORS de la ligne de commande : clés d'API), « NOM=valeur » est un
        argument littéral (valeur non secrète : TERM=dumb) ; le lanceur est python3 -I ; sans python, pas de bac."""
        bac = self.m.module_bac()
        commun = dict(home=self.home, reglage=lambda k, d="": d, env=["OPENAI_API_KEY", "TERM=dumb"])
        argv = bac.argv(["true"], str(self.home), 10, programme=shutil.which, **commun)
        self.assertIn("--setenv=OPENAI_API_KEY", argv)                   # valeur transmise par l'unité
        self.assertNotIn("--setenv=TERM=dumb", argv)
        tail = argv[argv.index("--") + 1:]
        self.assertEqual(Path(tail[0]).name.startswith("python"), True, tail[0])
        self.assertIn("-I", tail[:2])
        self.assertIn("os.execvpe", tail[3])                             # le code du lanceur
        self.assertEqual(tail[4], "OPENAI_API_KEY")                      # noms à garder de os.environ (pas de valeur)
        self.assertIn("TERM=dumb", tail)                                 # littéral non secret
        self.assertNotIn("OPENAI_API_KEY=", " ".join(a for a in tail if a != "OPENAI_API_KEY"))  # jamais la valeur
        self.assertEqual(tail[-1], "true")                              # la commande
        self.assertIsNone(bac.argv(["true"], str(self.home), 10,
                                   programme=lambda n: None if n.startswith("python") else shutil.which(n), **commun))
        self.assertIsNone(bac.argv(["true"], str(self.home), 10, programme=shutil.which,
                                   **dict(commun, env=["MAUVAIS NOM"])))

    # ── P2-1 : le jeton revenu du bac ne revient plus : voir les tests « rien ne revient » plus bas ──────────
    def _codex(self, exp_delta, marque="A"):
        claims = dict(_CODEX_CLAIMS, exp=int(time.time()) + exp_delta)
        return {"tokens": {"access_token": jwt(claims, marque), "refresh_token": "RT", "id_token": jwt(_CODEX_CLAIMS),
                           "account_id": "compte-1"}, "last_refresh": "2026-01-01T00:00:00Z"}

    # ── P3-4 : le dossier de travail de nc-noeud est illisible pour le bac des IA ─────────────────────────────────
    def test_dossier_travail_noeud_interdit(self):
        (self.home / ".local/state/nc-noeud/travail").mkdir(parents=True)
        self.lancer_moteur(self.m, "codex", NC_TEST_FICHIERS="")
        inacc = {p[len('InaccessiblePaths="'):-1] for p in self.props(self.lancements()[-1]) if p.startswith("InaccessiblePaths=")}
        self.assertIn(str(self.home / ".local/state/nc-noeud/travail"), inacc)

    # ── P2-2 : effacer un arbre très profond, sans récursion ni fds qui s'accumulent ──────────────────────────────
    def _creuser(self, racine, niveaux):
        """Crée racine puis `niveaux` sous-dossiers « n » imbriqués, par descripteurs (os.makedirs récurse en Python
        et planterait à ~1000)."""
        os.mkdir(racine)
        fd = os.open(racine, os.O_RDONLY | os.O_DIRECTORY)
        try:
            for _ in range(niveaux):
                os.mkdir("n", dir_fd=fd)
                nfd = os.open("n", os.O_RDONLY | os.O_DIRECTORY, dir_fd=fd)
                os.close(fd)
                fd = nfd
            ffd = os.open("secret", os.O_WRONLY | os.O_CREAT, 0o600, dir_fd=fd)
            os.close(ffd)
        finally:
            os.close(fd)

    def test_effacer_arbre_tres_profond(self):
        racine = self.home / "profond"
        self._creuser(racine, 1500)                             # 1500 niveaux : une récursion planterait (RecursionError)
        (racine / "n" / "fichier").write_text("y")             # un fichier en cours de route
        self.m.effacer(str(racine))
        self.assertFalse(racine.exists(), "tout l'arbre est supprimé")

    def test_effacer_sous_peu_de_descripteurs(self):
        """Avec RLIMIT_NOFILE bas, effacer ne boucle pas sans fin (fds bornés) : il finit, et vide l'arbre."""
        racine = Path(tempfile.mkdtemp(prefix="nc-bac-ia-fds-", dir=self.racine))
        self.addCleanup(lambda: _rmtree_force(str(racine)))
        self._creuser(racine / "a", 200)
        code = ("import os,sys,resource,importlib.machinery as M,importlib.util as U\n"
                "resource.setrlimit(resource.RLIMIT_NOFILE,(24,24))\n"
                "l=M.SourceFileLoader('x', sys.argv[1]); m=U.module_from_spec(U.spec_from_loader('x',l))\n"
                "# n'exécute que ce qu'il faut : on recharge le module entier (effet de bord lu env), HOME temporaire\n"
                "l.exec_module(m)\n"
                "m.effacer(sys.argv[2])\n"
                "sys.exit(0 if not os.path.lexists(sys.argv[2]) else 2)\n")
        env = dict(os.environ, HOME=str(self.home), XDG_RUNTIME_DIR=str(self.home / "run"),
                   XDG_STATE_HOME=str(self.home / ".local/state"), XDG_CONFIG_HOME=str(self.home / ".config"),
                   XDG_DATA_HOME=str(self.home / ".local/share"), XDG_CACHE_HOME=str(self.home / ".cache"))
        r = subprocess.run(["python3", "-I", "-c", code, str(BIN / "nc-ia"), str(racine / "a")],
                           capture_output=True, text=True, timeout=30, env=env)
        self.assertEqual(r.returncode, 0, r.stderr[-800:])
        self.assertFalse((racine / "a").exists())

    def test_on_failure_vide(self):
        """Un greffon global OnFailure= (notification de panne) ne doit pas se déclencher pour une unité du bac."""
        self.oublier_sonde()
        self.lancer_moteur(self.m, "codex", NC_TEST_FICHIERS="")
        for bloc in self.lancements():
            self.assertIn("OnFailure=", self.props(bloc))
            self.assertIn("--collect", bloc)

    def test_options_du_bac_et_invite_par_l_entree_standard(self):
        for ident in ("claude", "codex"):
            with self.subTest(ident):
                self.journal.unlink(missing_ok=True)
                (self.home / "moteur.log").unlink(missing_ok=True)
                self.oublier_sonde()
                self.lancer_moteur(self.m, ident, NC_TEST_FICHIERS="")
                for bloc in self.lancements():
                    self.assertIn("--expand-environment=no", bloc)
                    self.assertIn("--description=nc-ia", bloc)
                reel = self.lancements()[-1]
                log = (self.home / "moteur.log").read_text()
                self.assertIn("ENTREE c\n\nt", log, "l'invite arrive par l'entrée standard")
                self.assertNotIn("c\n\nt", "\n".join(reel).replace("ENTREE", ""))
                self.assertEqual(len([l for l in reel if l == "c"]), 0)
        # Gemini, Qwen, OpenCode : l'invite reste en argument, mais la description masque le journal
        self.journal.unlink(missing_ok=True)
        self.oublier_sonde()
        self.lancer_moteur(self.m, "qwen", NC_TEST_FICHIERS="")
        self.assertIn("--description=nc-ia", self.lancements()[-1])

    def test_environnement_liste_blanche(self):
        """Un moteur ne reçoit que sa propre clé : ni GITHUB_TOKEN, ni les clés des autres."""
        env = {"GITHUB_TOKEN": "g", "OPENAI_API_KEY": "o", "ANTHROPIC_API_KEY": "a", "GEMINI_API_KEY": "m", "AWS_SECRET_ACCESS_KEY": "w",
               "SSH_AUTH_SOCK": "/x", "LC_ALL": "C.UTF-8", "LANG": "fr_FR.UTF-8"}
        attendu = {"claude": {"ANTHROPIC_API_KEY"}, "codex": {"OPENAI_API_KEY"}, "gemini-cli": {"GEMINI_API_KEY"},
                   "qwen": {"OPENAI_API_KEY"}, "opencode": {"OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY"}}
        for ident, ok in attendu.items():
            with self.subTest(ident):
                self.journal.unlink(missing_ok=True)
                self.oublier_sonde()
                with unittest.mock.patch.dict(os.environ, env):
                    self.lancer_moteur(self.m, ident, NC_TEST_FICHIERS="")
                setenv = {a.split("=", 1)[1] for a in self.lancements()[-1] if a.startswith("--setenv=")}
                for k in ("GITHUB_TOKEN", "AWS_SECRET_ACCESS_KEY", "SSH_AUTH_SOCK", "XDG_RUNTIME_DIR", "DBUS_SESSION_BUS_ADDRESS"):
                    self.assertNotIn(k, setenv)
                for k in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY"):
                    self.assertEqual(k in setenv, k in ok, (ident, k, setenv))
                self.assertTrue({"PATH", "HOME", "LC_ALL", "LANG", "NO_COLOR"} <= setenv, setenv)
                if ident == "claude":
                    self.assertIn("DISABLE_AUTOUPDATER", setenv)

    def test_claude_avec_image_ne_lit_que_son_dossier_de_travail(self):
        img = self.home / "photo.png"
        img.write_bytes(b"x")
        with unittest.mock.patch.dict(os.environ):
            list(self.m.appel_claude("c", "t", str(img), "image"))
        reel = self.lancements()[-1]
        regle = [a for a in reel if a.startswith("Read(")]
        self.assertEqual(len(regle), 1, reel)
        self.assertRegex(regle[0], r"^Read\(//.+/nc-bac-ia-[^/]+/run/nc-ia/bac/nc-ia-travail-[0-9a-f]{12}/\*\*\)$")
        self.assertNotIn("Read", [a for a in reel if a == "Read"][1:], "pas de « Read » seul dans --allowedTools")
        i = reel.index("--allowedTools")
        self.assertTrue(reel[i + 1].startswith("Read("))

    def test_dossier_de_travail_dans_le_runtime_meme_sans_bac(self):
        (self.fb / "systemd-run").write_text("#!/bin/sh\nexit 1\n")
        self.regler("IA_BAC_REPLI=oui\n")
        self.oublier_sonde()
        sortie = self.lancer_moteur(self.m, "codex", NC_TEST_FICHIERS="")
        cwd = [l for l in sortie if l.startswith("CWD")][0]
        self.assertIn("/run/nc-ia/bac/nc-ia-travail-", cwd)
        self.assertNotIn("/tmp/", cwd)

    def test_etat(self):
        (self.fb / "systemd-run").write_text("#!/bin/sh\nexit 1\n")
        self.oublier_sonde()
        self.assertFalse(self.m.etat()["bac"])
        self.oublier_sonde()
        (self.fb / "systemd-run").write_text(FAUX_SYSTEMD_RUN.replace("@REEL@", str(self.home)))
        self.assertTrue(self.m.etat()["bac"])
        import io, contextlib
        for bac, repli, attendu in ((True, False, "bac des IA : actif"), (False, False, "indisponible ici : Claude Code, Codex"),
                                    (False, True, "sans bac, Codex peut lire tes fichiers")):
            e = self.m.etat()
            e["bac"], e["repli"] = bac, repli
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                self.m.afficher_etat(e)
            self.assertIn(attendu, buf.getvalue())

    def test_claude_json_et_reglages_filtres(self):
        """P3-c : de ~/.claude.json et ~/.claude/settings.json, seules les clés utiles à une question non interactive."""
        (self.home / ".claude.json").write_text(json.dumps({
            "hasCompletedOnboarding": True, "oauthAccount": {"emailAddress": "x@example.org"},
            "mcpServers": {"s": {"command": "SECRET-MCP-SERVEUR"}}, "projects": {"/p": {"SECRET-PROJET": 1}},
            "env": {"K": "SECRET-ENV"}}))
        sortie = "".join(self.lancer_moteur(self.m, "claude", NC_TEST_RELATIFS=".claude.json .claude/settings.json"))
        self.assertIn("hasCompletedOnboarding", sortie)
        self.assertIn("oauthAccount", sortie)
        self.assertIn("CONFIG-claude", sortie)                        # « language » passe
        self.assertNotIn("SECRET-", sortie)                           # ni mcpServers, ni projects, ni env, ni hooks…

    # ── P2-1 : faux dossiers personnels en tmpfs, purgés ─────────────────────────────────────────────────────────
    def test_sans_xdg_runtime_dir_refus_propre(self):
        for valeur in ("", "relatif", str(self.home / "absent")):
            with self.subTest(valeur):
                with unittest.mock.patch.dict(os.environ, {"XDG_RUNTIME_DIR": valeur}):
                    with self.assertRaises(self.m.ErreurIA) as e:
                        list(self.m.appel_programme("codex", "c", "t", None, "question"))
                self.assertIn("XDG_RUNTIME_DIR", str(e.exception))
        self.assertFalse((self.home / "moteur.log").exists())

    def test_purge_des_demandes_plantees(self):
        """Ce qu'une demande plantée laisse est supprimé au lancement suivant, sauf si son unité tourne encore, si une
        demande en cours le tient (verrou), ou s'il vient d'être créé."""
        (self.fb / "systemctl").write_text('#!/bin/sh\nfor u; do case "$u" in *bbbbbbbbbbbb*) echo active;; '
                                           '*.service) echo inactive;; esac; done\n')
        base = self.base()
        base.mkdir(parents=True)
        vieux = time.time() - 120
        for i in ("aaaaaaaaaaaa", "bbbbbbbbbbbb", "cccccccccccc", "dddddddddddd"):
            for sorte in ("home", "travail"):
                d = base / f"nc-ia-{sorte}-{i}"
                d.mkdir()
                (d / "f").write_text("x")
                if i != "dddddddddddd":
                    os.utime(d, (vieux, vieux))
        (base / "nc-ia-travail-eeeeeeeeeeee").mkdir()                  # orphelin (son faux dossier déjà parti)
        os.utime(base / "nc-ia-travail-eeeeeeeeeeee", (vieux, vieux))
        verrou = os.open(base / "nc-ia-home-cccccccccccc", os.O_RDONLY | os.O_DIRECTORY)
        fcntl.flock(verrou, fcntl.LOCK_EX)
        self.addCleanup(os.close, verrou)
        ancien = self.home / ".local/state/nc-ia/etat/nc-ia-home-x"     # version précédente, dans ~/.local/state
        ancien.mkdir(parents=True)
        os.utime(ancien, (time.time() - 3600,) * 2)
        self.lancer_moteur(self.m, "codex", NC_TEST_FICHIERS="")
        reste = sorted(os.listdir(base))
        self.assertEqual(reste, sorted(f"nc-ia-{s}-{i}" for i in ("bbbbbbbbbbbb", "cccccccccccc", "dddddddddddd")
                                       for s in ("home", "travail")))
        self.assertFalse(ancien.exists())

    def test_purge_rien_si_systemctl_ne_repond_pas(self):
        (self.fb / "systemctl").write_text("#!/bin/sh\nexit 1\n")
        d = self.base() / "nc-ia-home-aaaaaaaaaaaa"
        d.mkdir(parents=True)
        os.utime(d, (time.time() - 120,) * 2)
        self.lancer_moteur(self.m, "codex", NC_TEST_FICHIERS="")
        self.assertTrue(d.exists(), "on ne sait pas si son unité tourne : gardé")

    def test_purge_home_a_000_et_mtime_futur(self):
        """La purge ne cale ni sur un faux dossier personnel à 000 (verrou pris par /proc), ni sur un mtime dans le
        futur (traité comme ancien)."""
        self.fb.joinpath("systemctl").write_text('#!/bin/sh\ncase "$*" in *is-active*) for u in "$@"; do '
                                                 'case "$u" in *.service) echo inactive;; esac; done;; esac\n')
        base = self.base()
        base.mkdir(parents=True)
        futur = time.time() + 10000
        for sorte in ("home", "travail"):                       # mtime dans le futur
            d = base / f"nc-ia-{sorte}-aaaaaaaaaaaa"
            d.mkdir()
            os.utime(d, (futur, futur))
        zero = base / "nc-ia-home-bbbbbbbbbbbb"                  # faux dossier personnel à 000
        (base / "nc-ia-travail-bbbbbbbbbbbb").mkdir()
        zero.mkdir()
        (zero / "jeton").write_text("x")
        os.utime(base / "nc-ia-travail-bbbbbbbbbbbb", (time.time() - 120,) * 2)
        os.chmod(zero, 0)
        self.addCleanup(lambda: os.chmod(zero, 0o700) if zero.exists() else None)
        os.utime(zero, (time.time() - 120,) * 2)
        self.lancer_moteur(self.m, "codex", NC_TEST_FICHIERS="")
        for n in ("nc-ia-home-aaaaaaaaaaaa", "nc-ia-travail-aaaaaaaaaaaa", "nc-ia-home-bbbbbbbbbbbb",
                  "nc-ia-travail-bbbbbbbbbbbb"):
            self.assertFalse((base / n).exists(), f"{n} aurait dû être purgé")

    # ── P2-2 : CLAUDE_CONFIG_DIR, CODEX_HOME, XDG_CONFIG_HOME, XDG_DATA_HOME ──────────────────────────────────────
    def test_dossiers_deplaces_dans_le_home(self):
        h = self.home
        place = {"CLAUDE_CONFIG_DIR": h / "ailleurs/claude", "CODEX_HOME": h / "ailleurs/codex",
                 "XDG_CONFIG_HOME": h / "ailleurs/config", "XDG_DATA_HOME": h / "ailleurs/data"}
        fichiers = {"claude": place["CLAUDE_CONFIG_DIR"] / ".credentials.json", "codex": place["CODEX_HOME"] / "auth.json",
                    "opencode": place["XDG_DATA_HOME"] / "opencode/auth.json"}
        for ident, f in fichiers.items():
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(json.dumps(contenu_jeton(ident, f"DEPLACE-{ident}")))
        (place["XDG_CONFIG_HOME"] / "opencode").mkdir(parents=True)
        (place["XDG_CONFIG_HOME"] / "gh").mkdir()
        (place["CLAUDE_CONFIG_DIR"] / ".claude.json").write_text('{"hasCompletedOnboarding": true, "mcpServers": "SECRET-X"}')
        env = {k: str(v) for k, v in place.items()}
        with unittest.mock.patch.dict(os.environ, env):
            for ident, f in fichiers.items():
                with self.subTest(ident):
                    self.journal.unlink(missing_ok=True)
                    self.oublier_sonde()
                    sortie = "".join(self.lancer_moteur(self.m, ident, NC_TEST_RELATIFS=JETONS[ident] + " .claude.json",
                                                        NC_TEST_RAFRAICHIR=JETONS[ident],
                                                        NC_TEST_CONTENU=json.dumps(rafraichi(ident, f"RETOUR-{ident}"))))
                    self.assertIn(marqueur(ident, f"DEPLACE-{ident}"), sortie, "copié depuis le dossier déplacé")
                    self.assertNotIn(marqueur(ident, f"JETON-{ident}"), sortie, "pas depuis l'emplacement par défaut")
                    # rien ne revient du bac : le vrai fichier (au dossier déplacé) garde son jeton d'origine
                    self.assertEqual(jeton_acces(ident, json.loads(f.read_text())), f"DEPLACE-{ident}", "rien ne revient")
                    self.assertEqual(json.loads((self.home / JETONS[ident]).read_text()), contenu_jeton(ident))
                    if ident == "claude":
                        self.assertIn("hasCompletedOnboarding", sortie)
                        self.assertNotIn("SECRET-X", sortie)
                    props = self.props(self.lancements()[-1])
                    inacc = {p[len('InaccessiblePaths="'):-1] for p in props if p.startswith("InaccessiblePaths=")}
                    for d in (place["CLAUDE_CONFIG_DIR"], place["CODEX_HOME"], place["XDG_CONFIG_HOME"] / "opencode",
                              place["XDG_DATA_HOME"] / "opencode", place["XDG_CONFIG_HOME"] / "gh"):
                        self.assertIn(str(d), inacc)
                    for rel in (".claude", ".codex", ".config/opencode", ".local/share/opencode"):
                        self.assertIn(str(self.home / rel), inacc, "l'emplacement par défaut reste interdit aussi")

    def test_dossier_deplace_hors_du_home_refuse(self):
        dehors = tempfile.mkdtemp(prefix="nc-bac-ia-dehors-", dir=self.racine)
        self.addCleanup(shutil.rmtree, dehors, True)
        bac = self.m.module_bac()
        for var in ("CLAUDE_CONFIG_DIR", "CODEX_HOME", "XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_STATE_HOME", "XDG_CACHE_HOME"):
            for valeur in (dehors, "relatif/dossier"):
                with self.subTest(var=var, valeur=valeur):
                    with unittest.mock.patch.dict(os.environ, {var: valeur}):
                        with self.assertRaises(self.m.ErreurIA) as e:
                            list(self.m.appel_programme("codex", "c", "t", None, "question"))
                        self.assertIn(var, str(e.exception))
                        # et nc-noeud (même module) : pas de bac du tout
                        self.assertIsNone(bac.inaccessibles(self.home, lambda k, d: d))
        self.assertFalse((self.home / "moteur.log").exists(), "aucun moteur n'a tourné")
        # sous /tmp (masqué par PrivateTmp) : géré
        with unittest.mock.patch.dict(os.environ, {"XDG_CACHE_HOME": "/tmp/nc-essai-cache"}):
            self.assertIsNotNone(bac.inaccessibles(self.home, lambda k, d: d))

    # ── P3-b : « opencode --version » dans le bac, gardé en mémoire ──────────────────────────────────────────────
    def test_version_opencode_dans_le_bac_et_gardee(self):
        self.lancer_moteur(self.m, "opencode", NC_TEST_FICHIERS="")
        blocs = self.lancements()
        version = [b for b in blocs if b[-2:] == ["opencode", "--version"]]
        self.assertEqual(len(version), 1, blocs)
        v = version[0]
        self.assertTrue(any(p.startswith("TemporaryFileSystem=") for p in self.props(v)))
        cd = v[-3]                                                    # lanceur python … <cwd> opencode --version
        self.assertIn("/run/nc-ia/bac/nc-ia-travail-", cd, "dans le dossier de travail vide, jamais dans ~")
        self.journal.unlink()
        self.lancer_moteur(self.m, "opencode", NC_TEST_FICHIERS="")      # la sonde est gardée, la version aussi
        self.assertEqual([b for b in self.lancements() if b[-2:] == ["opencode", "--version"]], [])
        (self.home / ".local/bin/opencode").write_text((self.home / ".local/bin/opencode").read_text() + "\n# v2\n")
        self.lancer_moteur(self.m, "opencode", NC_TEST_FICHIERS="")      # le programme a changé : relue
        self.assertEqual(len([b for b in self.lancements() if b[-2:] == ["opencode", "--version"]]), 1)

    # ── Rien ne revient du bac (4e relecture) ───────────────────────────────────────────────────────────────────────
    def _cles_json(self, dossier):
        """Tous les noms de clé de tous les JSON sous dossier, récursivement (objets imbriqués et listes). Une clé dont
        la valeur est une simple date RFC 3339 (last_refresh de Codex : un horodatage, pas un jeton) ou une chaîne vide
        (refresh_token de Codex, exigé par son lecteur, laissé vide) n'est pas un jeton."""
        noms = set()

        def parcourir(o):
            if isinstance(o, dict):
                for k, v in o.items():
                    if not (isinstance(v, str) and (v == "" or re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", v))):
                        noms.add(k)
                    parcourir(v)
            elif isinstance(o, list):
                for v in o:
                    parcourir(v)
        for f in Path(dossier).rglob("*"):
            if f.is_file():
                with contextlib.suppress(ValueError, OSError, UnicodeDecodeError):
                    parcourir(json.loads(f.read_text()))
        return noms

    def test_aucun_jeton_de_rafraichissement_dans_le_home_jetable(self):
        for ident in IDENTS:
            with self.subTest(ident):
                export = self.home / f"export-{ident}"
                sortie = "".join(self.lancer_moteur(self.m, ident, NC_TEST_EXPORTER=str(export),
                                                    NC_TEST_RELATIFS=JETONS[ident]))
                self.assertIn(marqueur(ident, f"JETON-{ident}"), sortie, "le jeton d'accès, lui, est copié")
                cles = self._cles_json(export)
                self.assertTrue(cles, "des JSON ont bien été copiés")
                suspects = {k for k in cles if re.search(r"refresh|^rt$|_rt$|^rt_", k, re.I)}
                self.assertEqual(suspects, set(), f"{ident} : clé de rafraîchissement dans le HOME jetable")
                self.assertNotIn("SECRET-REFRESH", "".join(f.read_text() for f in export.rglob("*.json")))
                if ident == "codex":
                    # Codex 0.164 ne lit pas un auth.json sans ce champ (« missing field refresh_token ») : présent, vide
                    copie = json.loads((export / JETONS[ident]).read_text())
                    self.assertEqual(copie["tokens"]["refresh_token"], "")

    def _empreintes(self):
        """Contenu, mtime et inode de chaque vrai fichier d'identifiants et de config."""
        out = {}
        for rel in list(JETONS.values()) + list(CONFIGS.values()) + [".claude.json"]:
            f = self.home / rel
            if f.exists():
                st = f.stat()
                out[rel] = (f.read_bytes(), st.st_mtime_ns, st.st_ino)
        return out

    def test_vrais_fichiers_intacts_apres_une_demande(self):
        (self.home / ".claude.json").write_text('{"hasCompletedOnboarding": true}')
        avant = self._empreintes()
        for ident in IDENTS:
            with self.subTest(ident):
                self.lancer_moteur(self.m, ident, NC_TEST_FICHIERS="")              # demande réussie
                self.assertEqual(self._empreintes(), avant)
                self.lancer_moteur(self.m, ident, NC_TEST_RAFRAICHIR=f"{JETONS[ident]} {CONFIGS[ident]}",
                                   NC_TEST_CONTENU=json.dumps(rafraichi(ident, "MODIFIE")))   # le moteur modifie ses copies
                self.assertEqual(self._empreintes(), avant)
                self.lancer_moteur(self.m, ident, NC_TEST_RENOMMER=JETONS[ident],
                                   NC_TEST_CONTENU=json.dumps(rafraichi(ident, "RENOMME")))
                self.lancer_moteur(self.m, ident, NC_TEST_CASSER=JETONS[ident])
                self.assertEqual(self._empreintes(), avant)

    def test_jeton_codex_forge_ne_change_rien(self):
        """Le cas de la 4e relecture : un JWT forgé (non signé) au compte de la victime, exp à +10 jours, et
        refresh_token="RT-ATTAQUANT", écrit par le moteur dans sa copie. Le vrai auth.json ne bouge pas, ni quand le vrai
        jeton est valide, ni quand il est presque expiré (alors la demande n'est même pas lancée)."""
        reel = self.home / JETONS["codex"]
        forge = {"tokens": {"access_token": jwt(dict(_CODEX_CLAIMS, exp=int(time.time()) + 864000), "FORGE"),
                            "refresh_token": "RT-ATTAQUANT", "id_token": jwt(_CODEX_CLAIMS), "account_id": "compte-1"},
                 "last_refresh": "2026-01-01T00:00:00Z"}
        avant = reel.read_bytes(), reel.stat().st_mtime_ns, reel.stat().st_ino
        self.lancer_moteur(self.m, "codex", NC_TEST_RAFRAICHIR=JETONS["codex"], NC_TEST_CONTENU=json.dumps(forge))
        self.assertEqual((reel.read_bytes(), reel.stat().st_mtime_ns, reel.stat().st_ino), avant)
        presque = contenu_jeton("codex")
        presque["tokens"]["access_token"] = jwt(dict(_CODEX_CLAIMS, exp=int(time.time()) + 30), "PRESQUE")
        reel.write_text(json.dumps(presque))
        avant = reel.read_bytes(), reel.stat().st_mtime_ns, reel.stat().st_ino
        with self.assertRaises(self.m.ErreurIA):
            self.lancer_moteur(self.m, "codex", NC_TEST_RAFRAICHIR=JETONS["codex"], NC_TEST_CONTENU=json.dumps(forge))
        self.assertEqual((reel.read_bytes(), reel.stat().st_mtime_ns, reel.stat().st_ino), avant)
        self.assertNotIn("RT-ATTAQUANT", reel.read_text())

    # ── Jeton expiré ou trop court : pas lancé, message clair, notification limitée ─────────────────────────────────
    def _avec_echeance(self, ident, ms):
        o = contenu_jeton(ident)
        if ident == "claude":
            o["claudeAiOauth"]["expiresAt"] = ms
        elif ident == "codex":
            o["tokens"]["access_token"] = jwt(dict(_CODEX_CLAIMS, exp=ms / 1000 if isinstance(ms, (int, float)) else ms))
        elif ident == "opencode":
            o["anthropic"]["expires"] = ms
        else:
            o["expiry_date"] = ms
        (self.home / JETONS[ident]).write_text(json.dumps(o))

    def test_jeton_expire_pas_lance(self):
        duree = self.m.duree_bac(self.m.DELAI_CLI)              # durée maximale réelle (RuntimeMaxSec)
        marge = self.m.MARGE_JETON
        for ident in IDENTS:
            for delta, lance in ((-10, False), (duree + marge - 60, False), (duree + marge + 60, True)):
                with self.subTest(ident=ident, delta=delta):
                    (self.home / "moteur.log").unlink(missing_ok=True)
                    self._avec_echeance(ident, int((time.time() + delta) * 1000))
                    if ident in self.m.JETON_ACCES and shutil.which(self.m.BINAIRES[ident]):
                        # nc-diag le signale (nc-ia etat --json) : seulement un jeton déjà expiré
                        self.assertEqual(self.m.jeton_a_renouveler(ident), delta < 0)
                    if lance:
                        self.assertIn("fin\n", self.lancer_moteur(self.m, ident, NC_TEST_FICHIERS=""))
                        continue
                    with self.assertRaises(self.m.ErreurIA) as e:
                        self.lancer_moteur(self.m, ident, NC_TEST_FICHIERS="")
                    attendu = "doit renouveler sa connexion" if delta < 0 else "expire dans"
                    self.assertIn(attendu, str(e.exception))
                    self.assertIn(f"({self.m.BINAIRES[ident]})", str(e.exception))
                    self.assertFalse((self.home / "moteur.log").exists(), "le moteur n'a pas été lancé")
                    self.assertEqual(os.listdir(self.base()), [], "rien ne reste dans la base")

    def test_echeance_illisible_refus_propre(self):
        """1e400 (inf), NaN, une chaîne, exp absent : échéance inconnue → refus propre (ErreurIA), jamais d'exception."""
        m = self.m
        for brut in ('{"exp": 1e400}', '{"exp": NaN}', '{"exp": "demain"}', '{}', '{"exp": true}'):
            with self.subTest(brut):
                charge = base64.urlsafe_b64encode(brut.encode()).rstrip(b"=").decode()
                o = contenu_jeton("codex")
                o["tokens"]["access_token"] = "eyJhbGciOiJub25lIn0." + charge + ".sig"
                self.assertIsNone(m.echeance_ms("codex", o))
                (self.home / JETONS["codex"]).write_text(json.dumps(o))
                with self.assertRaises(m.ErreurIA):
                    self.lancer_moteur(m, "codex", NC_TEST_FICHIERS="")
        for v in (float("inf"), float("nan"), "x", None, True, 10 ** 40, -5):
            with self.subTest(v=v):
                self.assertIsNone(m.ms_plausible(v))
                self.assertIsNone(m.echeance_ms("claude", {"claudeAiOauth": {"accessToken": "a", "expiresAt": v}}))

    def test_opencode_sans_echeance_copie_seul(self):
        o = contenu_jeton("opencode")
        del o["anthropic"]["expires"]                           # jeton opaque sans date : copié seul
        o["vieux"] = {"type": "oauth", "access": "PERIME", "refresh": "r", "expires": 5}
        (self.home / JETONS["opencode"]).write_text(json.dumps(o))
        sortie = "".join(self.lancer_moteur(self.m, "opencode", NC_TEST_RELATIFS=JETONS["opencode"]))
        self.assertIn("JETON-opencode", sortie)
        self.assertNotIn("PERIME", sortie, "une entrée expirée n'est pas copiée")
        self.assertNotIn("SECRET-", sortie)

    def _faux_programme(self, nom, corps):
        f = self.fb / nom
        f.write_text("#!/bin/sh\n" + corps + "\n")
        f.chmod(0o755)

    def test_notification_une_par_heure_avec_action_ouvrir(self):
        self._faux_programme("notify-send", f'[ "$1" = "--help" ] && {{ echo "  -A, --action=[NAME=]Text"; exit 0; }}\n'
                                            f'printf "%s\\n" "$*" >> "{self.home}/notifs.log"')
        self._faux_programme("kitty", f'echo kitty "$@" >> "{self.home}/terminal.log"')
        self._avec_echeance("codex", int((time.time() - 10) * 1000))
        for _ in range(2):
            with self.assertRaises(self.m.ErreurIA):
                self.lancer_moteur(self.m, "codex", NC_TEST_FICHIERS="")
        notifs = [l for l in self.notifs().splitlines() if "renouveler" in l]
        self.assertEqual(len(notifs), 1, "au plus une notification par heure et par moteur")
        self.assertIn("-A ouvrir=Ouvrir", notifs[0])
        time.sleep(0.3)
        self.assertFalse((self.home / "terminal.log").exists(), "rien ne s'ouvre tout seul")

    def test_notification_texte_seul_sans_terminal_ni_action(self):
        self._faux_programme("notify-send", f'[ "$1" = "--help" ] && exit 0\nprintf "%s\\n" "$*" >> "{self.home}/notifs.log"')   # pas d'--action
        self._avec_echeance("qwen", int((time.time() - 10) * 1000))
        with self.assertRaises(self.m.ErreurIA):
            self.lancer_moteur(self.m, "qwen", NC_TEST_FICHIERS="")
        notifs = [l for l in self.notifs().splitlines() if "renouveler" in l]
        self.assertEqual(len(notifs), 1)
        self.assertNotIn("-A", notifs[0])

    def test_inaccessibles_sans_xdg_runtime_dir(self):
        """nc-bac : sans XDG_RUNTIME_DIR, plus de ValueError (realpath("/\\0")) ; /run/user/<uid> est alors masqué."""
        env = {k: v for k, v in os.environ.items() if k != "XDG_RUNTIME_DIR"}
        r = self.m.module_bac().inaccessibles(self.home, lambda k, d="": d, environ=env)
        self.assertIsNotNone(r)
        if os.path.isdir(f"/run/user/{os.getuid()}"):
            self.assertIn(f"/run/user/{os.getuid()}", r)

    def test_lire_sans_lien_refuse_les_liens(self):
        d = self.home / "lecture"
        (d / "a").mkdir(parents=True)
        (d / "a/f").write_text("ok")
        cible = self.home / ".ssh/id_ed25519"
        (d / "lien").symlink_to(cible)
        self.assertEqual(self.m.lire_sans_lien(str(d), "a/f", 100), b"ok")
        with self.assertRaises(ValueError):
            self.m.lire_sans_lien(str(d), "lien", 100)

    # ── Effacement : droits retirés, arbre large, lien, borne ───────────────────────────────────────────────────────
    def _arbre(self, nom):
        r = self.home / nom
        (r / "a/b").mkdir(parents=True)
        (r / "a/b/auth.json").write_text("{}")
        (r / "jeton.json").write_text("{}")
        return r

    def test_effacer_dossiers_en_0500_et_0400(self):
        for mode, ou in ((0o500, "a"), (0o500, ""), (0o400, ""), (0o400, "a")):
            with self.subTest(mode=oct(mode), ou=ou or "racine"):
                r = self._arbre(f"droits-{mode:o}-{ou or 'r'}")
                os.chmod(r / ou if ou else r, mode)
                self.addCleanup(lambda r=r: _rmtree_force(str(r)) if r.exists() else None)
                debut = time.monotonic()
                self.m.effacer(str(r))
                self.assertLess(time.monotonic() - debut, 5)
                self.assertFalse(r.exists())

    def test_effacer_arbre_large(self):
        r = self.home / "large"
        r.mkdir()
        for i in range(4000):                                   # 4000 × 2 niveaux
            (r / f"d{i}" / "s").mkdir(parents=True)
        (r / "d3999/s/auth.json").write_text("{}")
        debut = time.monotonic()
        self.m.effacer(str(r))
        self.assertLess(time.monotonic() - debut, 10)
        self.assertFalse(r.exists())

    def test_effacer_ne_suit_pas_un_lien_vers_home(self):
        r = self._arbre("avec-lien")
        (r / "a/vers-home").symlink_to(self.home)
        (r / "vers-ssh").symlink_to(self.home / ".ssh")
        self.m.effacer(str(r))
        self.assertFalse(r.exists())
        self.assertEqual((self.home / ".ssh/id_ed25519").read_text(), "FAUSSE-CLE-SSH", "~ intact")
        self.assertTrue((self.home / JETONS["codex"]).exists())

    def test_effacer_borne_atteinte_met_en_000(self):
        r = self._arbre("borne")
        for i in range(50):
            (r / f"x{i}").mkdir()
        self.addCleanup(lambda: (os.chmod(r, 0o700), _rmtree_force(str(r))) if r.exists() else None)
        with unittest.mock.patch.object(self.m, "EFFACER_MAX", 5):
            self.m.effacer(str(r))
        self.assertTrue(r.exists())
        self.assertEqual(r.stat().st_mode & 0o777, 0, "jamais lisible avec un jeton dedans")
        self.assertIn("effacement de borne borné", self.journal_ia())
        self.m.effacer(str(r))                                  # la purge suivante le reprend (000 rouvert par /proc)
        self.assertFalse(r.exists())
    # ── 5e relecture ────────────────────────────────────────────────────────────────────────────────────────────────
    def _arbre_droits(self, nom, modes):
        """r/a/b/c avec auth.json au fond ; modes : {chemin relatif: mode} appliqués du plus profond au moins profond."""
        r = self.home / nom
        (r / "a/b/c").mkdir(parents=True)
        (r / "a/b/c/auth.json").write_text("{}")
        (r / "a/b/f").write_text("x")
        for rel in sorted(modes, key=len, reverse=True):
            os.chmod(r / rel, modes[rel])
        return r

    def test_effacer_sous_dossiers_sans_droit_d_ecriture(self):
        """Déplacer un dossier exige w sur lui : a/b en 0500, a/b/c en 0500, a/b en 000 s'effacent quand même."""
        for nom, modes in (("b500", {"a/b": 0o500}), ("c500", {"a/b": 0o500, "a/b/c": 0o500}), ("b000", {"a/b": 0}),
                           ("c400", {"a/b/c": 0o400})):
            with self.subTest(nom):
                r = self._arbre_droits(nom, modes)
                self.addCleanup(lambda r=r: _rmtree_force(str(r)) if r.exists() else None)
                debut = time.monotonic()
                self.m.effacer(str(r))
                self.assertLess(time.monotonic() - debut, 5)
                self.assertFalse(r.exists(), f"{nom} : il reste {sorted(str(x) for x in r.rglob('*')) if r.exists() else ''}")
                self.assertNotIn("borné", self.journal_ia())

    def test_purge_reprend_un_reste_sans_droits(self):
        """Un faux dossier personnel laissé par une version précédente, en 000, avec a/b et a/b/c en 0500 : repris."""
        self.fb.joinpath("systemctl").write_text('#!/bin/sh\ncase "$*" in *is-active*) for u in "$@"; do '
                                                 'case "$u" in *.service) echo inactive;; esac; done;; esac\n')
        base = self.base()
        base.mkdir(parents=True)
        reste = base / "nc-ia-home-aaaaaaaaaaaa"
        (reste / "a/b/c").mkdir(parents=True)
        (reste / "a/b/c/auth.json").write_text('{"access_token": "VIEUX"}')
        for rel, mode in (("a/b/c", 0o500), ("a/b", 0o500)):
            os.chmod(reste / rel, mode)
        os.chmod(reste, 0)
        os.utime(reste, (time.time() - 120,) * 2)
        self.addCleanup(lambda: _rmtree_force(str(reste)) if reste.exists() else None)
        self.lancer_moteur(self.m, "codex", NC_TEST_FICHIERS="")
        self.assertFalse(reste.exists(), "le reste est repris par la purge")
        self.assertEqual(os.listdir(base), [])

    def test_attente_du_clic_bornee_et_notify_send_tue(self):
        """L'assistant détaché tue notify-send à l'échéance (pas de processus qui reste) ; un clic lance la commande."""
        temoin = self.home / "lance"
        for clic, attendu in (("", False), ("ouvrir", True)):
            with self.subTest(clic=clic or "aucun"):
                temoin.unlink(missing_ok=True)
                pid = self.home / "pid"
                faux = self.fb / "notify-attente"
                faux.write_text(f'#!/bin/sh\necho $$ > "{pid}"\n' + (f'echo {clic}\n' if clic else 'exec sleep 30\n'))
                faux.chmod(0o755)
                notif = subprocess.Popen([str(faux)], stdout=subprocess.PIPE, stdin=subprocess.DEVNULL)
                fd = notif.stdout.fileno()
                r = subprocess.run([sys.executable, "-I", "-c", self.m._ATTENDRE_CLIC, "ouvrir", str(notif.pid), str(fd),
                                    json.dumps(["touch", str(temoin)]), "1"], pass_fds=(fd,), timeout=20)
                notif.stdout.close()
                self.assertEqual(r.returncode, 0)
                self.assertIsNotNone(notif.wait(timeout=5), "notify-send est terminé (tué à l'échéance s'il attendait)")
                time.sleep(0.3)
                self.assertEqual(temoin.exists(), attendu)

    def test_cle_d_api_jeton_expire_non_copie_sans_refus(self):
        """Une clé d'API du moteur dans l'environnement : le jeton OAuth expiré n'est pas copié, la demande part."""
        self._avec_echeance("codex", int((time.time() - 10) * 1000))
        with unittest.mock.patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}):
            sortie = "".join(self.lancer_moteur(self.m, "codex", NC_TEST_RELATIFS=JETONS["codex"]))
        self.assertIn("fin\n", sortie)
        self.assertRegex(sortie, rf"REFUSE {re.escape(str(self.base()))}/nc-ia-home-[0-9a-f]{{12}}/\.codex/auth\.json")
        self.assertNotIn("JETON-codex", sortie)
        self.assertIn("la clé d'API de l'environnement sert", self.journal_ia())

    def test_fichier_jeton_illisible_refuse(self):
        for brut in ('{"claudeAiOauth": {"accessToken": "a", "expiresAt": NaN}}', "{cassé", "[1, 2]"):
            with self.subTest(brut):
                (self.home / "moteur.log").unlink(missing_ok=True)
                (self.home / JETONS["claude"]).write_text(brut)
                with self.assertRaises(self.m.ErreurIA) as e:
                    self.lancer_moteur(self.m, "claude", NC_TEST_FICHIERS="")
                self.assertIn("doit renouveler sa connexion", str(e.exception))
                self.assertFalse((self.home / "moteur.log").exists(), "pas de lancement sans identifiants")
        with unittest.mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-test"}):
            self.assertIn("fin\n", self.lancer_moteur(self.m, "claude", NC_TEST_FICHIERS=""))

    def test_fichier_jeton_present_mais_illisible_refuse(self):
        """Droits 000, plus gros que JETON_MAX, un dossier à la place : refus, pas un lancement sans identifiants."""
        f = self.home / JETONS["claude"]
        def droits_000():
            f.write_text(json.dumps(contenu_jeton("claude"))); f.chmod(0o000)
        def trop_gros():
            f.write_text(" " * (self.m.JETON_MAX + 1) + "{}")
        def dossier():
            f.mkdir()
        for nom, preparer in (("000", droits_000), ("gros", trop_gros), ("dossier", dossier)):
            with self.subTest(nom):
                (self.home / "moteur.log").unlink(missing_ok=True)
                if f.is_dir():
                    f.rmdir()
                elif f.exists():
                    f.chmod(0o600); f.unlink()
                preparer()
                try:
                    with self.assertRaises(self.m.ErreurIA) as e:
                        self.lancer_moteur(self.m, "claude", NC_TEST_FICHIERS="")
                    self.assertIn("doit renouveler sa connexion", str(e.exception))
                    self.assertFalse((self.home / "moteur.log").exists(), "pas de lancement sans identifiants")
                finally:
                    if f.is_file():
                        f.chmod(0o600)
        if f.is_dir():
            f.rmdir()

    def test_opencode_echeance_illisible_refusee(self):
        """projeter retire une échéance qui n'est pas une valeur simple : elle se lit dans le fichier d'origine."""
        for brut in ("1e400", "[1, 2]", '{"a": 1}'):
            with self.subTest(brut):
                (self.home / "moteur.log").unlink(missing_ok=True)
                o = contenu_jeton("opencode")
                o["anthropic"]["expires"] = "@ECHEANCE@"
                (self.home / JETONS["opencode"]).write_text(json.dumps(o).replace('"@ECHEANCE@"', brut))
                with self.assertRaises(self.m.ErreurIA):
                    self.lancer_moteur(self.m, "opencode", NC_TEST_FICHIERS="")
                self.assertFalse((self.home / "moteur.log").exists(), "le moteur n'a pas été lancé")

    def test_deux_messages_expire_ou_bientot(self):
        m = self.m
        self.assertIn("doit renouveler sa connexion", m.message_jeton_expire("gemini-cli", None))
        self.assertIn("doit renouveler sa connexion", m.message_jeton_expire("gemini-cli", int((time.time() - 5) * 1000)))
        bientot = m.message_jeton_expire("gemini-cli", int((time.time() + 150) * 1000))
        self.assertIn("expire dans 3 min", bientot)
        self.assertIn("une fois qu'il aura expiré", bientot)
        self._avec_echeance("qwen", int((time.time() + 120) * 1000))
        with self.assertRaises(m.ErreurIA) as e:
            self.lancer_moteur(m, "qwen", NC_TEST_FICHIERS="")
        self.assertIn("expire dans 2 min", str(e.exception))

    def test_duree_bac_et_marge(self):
        self.assertEqual(self.m.duree_bac(180), 190)
        self.assertGreaterEqual(self.m.MARGE_JETON, 300, "au moins les 5 min d'avance de Claude Code et google-auth")
        self.lancer_moteur(self.m, "codex", NC_TEST_FICHIERS="")
        props = self.props(self.lancements()[-1])
        delais = [int(p.split("=")[1]) for p in props if p.startswith("RuntimeMaxSec=")]
        self.assertEqual(delais, [self.m.duree_bac(self.m.DELAI_CLI)])

    def test_champs_copies_valeurs_simples(self):
        m = self.m
        o = {"claudeAiOauth": {"accessToken": "a", "expiresAt": 5, "scopes": {"x": {"objet": 1}},
                               "subscriptionType": ["ok"], "rateLimitTier": float("nan")}}
        copie = m.projeter(o, m.COPIES["claude"])["claudeAiOauth"]
        self.assertNotIn("scopes", copie)
        self.assertNotIn("rateLimitTier", copie)
        self.assertEqual(copie["subscriptionType"], ["ok"])

@unittest.skipUnless(_bus_utilisateur() and os.path.isdir(RACINE_BAC),
                     "systemd-run, un bus utilisateur joignable et /dev/shm requis")
class BacReelIA(Base):
    """Le VRAI bac : faux HOME sous /dev/shm (jamais /tmp, que PrivateTmp masque), faux jetons, faux moteurs."""
    racine = RACINE_BAC

    def setUp(self):
        self.home = self.faux_home()
        self.m = charger_ia(self.home, f"{self.home}/.local/bin:/usr/bin:/bin")
        self.m.UNITE_PREFIXE = "nc-ia-test-"
        self.addCleanup(self.nettoyer_unites)
        self.env_hote(f"{self.home}/.local/bin:/usr/bin:/bin")
        self.oublier_sonde()

    def nettoyer_unites(self):
        """Une unité de test en échec (délai, commande qui échoue) ne doit rien laisser : seulement notre préfixe."""
        env = dict(os.environ)
        vrai = os.environ.get("NC_TEST_VRAI_RUNTIME")
        if vrai:
            env["XDG_RUNTIME_DIR"] = vrai
        subprocess.run(["systemctl", "--user", "reset-failed", "nc-ia-test-*"], capture_output=True, env=env)

    def fichiers(self):
        return " ".join(str(self.home / r) for r in list(JETONS.values()) + list(CONFIGS.values()) +
                        [".ssh/id_ed25519", ".config/nc/ia.conf"])

    def test_le_bac_tient(self):
        self.assertTrue(self.m.bac_disponible(), "la sonde doit réussir ici")

    def test_chaque_moteur_lit_sa_copie_seulement(self):
        """Dans le vrai bac : sa copie de ses jetons (faux dossier personnel), jamais les vrais fichiers ni ceux des autres."""
        for ident in IDENTS:
            with self.subTest(ident):
                sortie = self.lancer_moteur(self.m, ident, NC_TEST_FICHIERS=self.fichiers(),
                                            NC_TEST_RELATIFS=" ".join(list(JETONS.values()) + list(CONFIGS.values())),
                                            NC_TEST_ECRIRE=f"{self.home}/ecrit-par-le-bac")
                texte = "".join(sortie).replace('"', "'")
                self.assertRegex(texte, rf"LU {re.escape(str(self.base()))}/nc-ia-home-[0-9a-f]{{12}}/{re.escape(JETONS[ident])} "
                                        rf"[^\n]*{re.escape(marqueur(ident, f'JETON-{ident}'))}")
                self.assertNotIn("SECRET-", texte)                    # ni mcpOAuth, ni entrées api/wellknown, ni hooks…
                for autre in JETONS:
                    if autre != ident:
                        self.assertNotIn(f"JETON-{autre}", texte, f"{ident} lit le jeton de {autre}")
                        self.assertNotIn(f"CONFIG-{autre}", texte)
                # les VRAIS fichiers, le sien compris : illisibles
                for rel in list(JETONS.values()) + list(CONFIGS.values()) + [".ssh/id_ed25519", ".config/nc/ia.conf"]:
                    self.assertIn(f"REFUSE {self.home}/{rel}", texte)
                self.assertNotIn("FAUSSE-CLE", texte)
                self.assertIn(f"NONECRIT {self.home}/ecrit-par-le-bac", texte)
                self.assertFalse((self.home / "ecrit-par-le-bac").exists())

    def test_rien_ne_peut_etre_cree_dans_les_vrais_dossiers_de_moteur(self):
        """P1-a : ce qu'un moteur créerait dans ~/.claude, ~/.codex… (hooks, règles, commandes, shell-snapshots, mémoire,
        ~/.claude.json) pour être exécuté plus tard HORS du bac n'existe nulle part après la demande."""
        (self.home / ".claude.json").write_text('{"mcpServers": {}}')
        cibles = [".claude/hooks/x", ".claude/settings.local.json", ".claude/commands/x.md", ".claude/agents/x.md",
                  ".claude/shell-snapshots/s.sh", ".claude/projects/p/memory/MEMORY.md", ".claude.json", ".claude/CLAUDE.md",
                  ".codex/rules/x", ".codex/AGENTS.md", ".codex/shell_snapshots/s.sh", ".codex/tmp/arg0/x", ".codex/packages/x",
                  ".codex/config.toml", ".gemini/extensions/x", ".qwen/commands/x", ".config/opencode/plugin/x.js",
                  ".cache/opencode/bin/x", ".local/share/opencode/bin/x", ".local/state/claude/x", ".bashrc", ".config/systemd/user/x.service"]
        avant = {c: (self.home / c).read_text() if (self.home / c).is_file() else None for c in cibles}
        for ident in IDENTS:
            with self.subTest(ident):
                sortie = "".join(self.lancer_moteur(self.m, ident, NC_TEST_ECRIRE=" ".join(str(self.home / c) for c in cibles),
                                                    NC_TEST_CREER_CHEZ_MOI=".claude/hooks/x .codex/rules/x"))
                for c in cibles:
                    self.assertIn(f"NONECRIT {self.home}/{c}", sortie)
                self.assertIn("CREE-CHEZ-MOI", sortie)               # il écrit dans son faux dossier personnel…
        for c, v in avant.items():                                   # …et rien d'autre ne bouge
            f = self.home / c
            self.assertEqual(f.read_text() if f.is_file() else None, v, c)
        self.assertEqual(os.listdir(self.base()), [], "faux dossiers personnels jetés")
        self.assertFalse((self.home / ".claude/hooks").exists())
        self.assertFalse((self.home / ".codex/rules").exists())

    def test_les_autres_demandes_sont_invisibles(self):
        """P2-1 : dans l'unité, la base des faux dossiers personnels est un tmpfs vide où seuls les SIENS sont remontés ;
        ni le reste de $XDG_RUNTIME_DIR, ni l'état de nc-ia (~/.local/state/nc-ia) ne se lisent."""
        autre = self.base() / "nc-ia-home-aaaaaaaaaaaa"
        autre.mkdir(parents=True)
        (autre / "jeton").write_text("SECRET-AUTRE-DEMANDE")
        (self.home / "run/bus").write_text("x")
        etat = self.home / ".local/state/nc-ia"
        etat.mkdir(parents=True, exist_ok=True)
        (etat / "journal").write_text("SECRET-JOURNAL")
        sortie = "".join(self.lancer_moteur(self.m, "qwen", NC_TEST_LISTER=f"{self.base()} {self.home / 'run'}",
                                            NC_TEST_FICHIERS=f"{autre}/jeton {self.home}/run/bus {etat}/journal"))
        self.assertNotIn("SECRET-", sortie)
        self.assertIn(f"REFUSE {autre}/jeton", sortie)
        self.assertIn(f"REFUSE {etat}/journal", sortie)
        liste = re.search(rf"LISTE {re.escape(str(self.base()))} \[(.*)\]", sortie)[1].split()
        self.assertEqual(sorted(x.rsplit("-", 1)[0] for x in liste), ["nc-ia-conf", "nc-ia-home", "nc-ia-travail"], liste)
        self.assertNotIn("aaaaaaaaaaaa", " ".join(liste))
        self.assertIn(f"LISTE {self.home / 'run'} [nc-ia]", sortie)
        # et l'écriture : seulement dans les siens (la base elle-même est en lecture seule)
        sortie = "".join(self.lancer_moteur(self.m, "codex", NC_TEST_ECRIRE=f"{self.base()}/nouveau {self.home}/run/x"))
        self.assertIn(f"NONECRIT {self.base()}/nouveau", sortie)
        self.assertIn(f"NONECRIT {self.home}/run/x", sortie)

    def test_la_sortie_arrive_ligne_par_ligne(self):
        """Pas de tampon jusqu'à la fin : la première ligne arrive bien avant la fin du moteur (qui dort 2 s)."""
        (self.home / "nc-test.env").write_text("export NC_TEST_PAUSE=2\n")
        with unittest.mock.patch.dict(os.environ):
            debut = time.monotonic()
            gen = self.m.appel_programme("codex", "c", "t", None, "question")
            premiere = next(gen)
            t1 = time.monotonic() - debut
            reste = list(gen)
            total = time.monotonic() - debut
        self.assertEqual(premiere.strip(), "debut")
        self.assertIn("fin\n", reste)
        self.assertGreater(total, 1.8)
        self.assertLess(t1, total - 1.5, f"première ligne à {t1:.1f} s sur {total:.1f} s : sortie mise en tampon")

    def test_delai_arrete_l_unite(self):
        """Le délai de nc-ia arrête aussi l'unité systemd (pas seulement systemd-run)."""
        self.m.DELAI_CLI = 2
        (self.home / "nc-test.env").write_text("export NC_TEST_PAUSE=30\n")
        # « systemctl --user stop » doit joindre le vrai gestionnaire (le garde-fou des tests a dérouté XDG_RUNTIME_DIR) ;
        # la sonde est déjà faite : le vrai runtime n'est pas touché par le mémo de la sonde
        self.assertTrue(self.m.bac_disponible())
        vrai = os.environ.get("NC_TEST_VRAI_RUNTIME")
        with unittest.mock.patch.dict(os.environ, {"XDG_RUNTIME_DIR": vrai} if vrai else {}):
            debut = time.monotonic()
            with self.assertRaises(Exception):
                list(self.m.appel_programme("qwen", "c", "t", None, "question"))
            self.assertLess(time.monotonic() - debut, 8, "arrêtée au délai, pas à RuntimeMaxSec (délai + 10 s)")
            # l'arrêt de l'unité est asynchrone : on attend qu'elle tombe, mais avant RuntimeMaxSec (12 s depuis le début)
            while True:
                r = subprocess.run(["systemctl", "--user", "list-units", "--no-legend", "nc-ia-test-*"], capture_output=True, text=True)
                if "running" not in r.stdout or time.monotonic() - debut > 10:
                    break
                time.sleep(0.2)
            self.assertNotIn("running", r.stdout)

    def test_les_dollars_arrivent_tels_quels(self):
        """systemd-run ne remplace plus ${VAR} ni $VAR dans la commande (une question pouvait y mettre une clé)."""
        argv = self.m.argv_bac("codex", "echo '${HOME}' '$$' '$HOME'", str(self.home), 10, env=["PATH"])
        self.assertIn("--expand-environment=no", argv)
        r = subprocess.run(argv, capture_output=True, text=True, timeout=20, env=dict(os.environ))
        self.assertEqual(r.stdout.strip(), "${HOME} $$ $HOME", (r.stdout, r.stderr))

    def test_dns_sans_socket_unix(self):
        """La résolution des noms marche sans AF_UNIX (localhost ; example.com seulement si le réseau est là)."""
        f = self.home / ".local/bin/codex"
        f.write_text("#!/bin/sh\ngetent hosts localhost | head -1\n")
        sortie = "".join(self.lancer_moteur(self.m, "codex"))
        self.assertIn("localhost", sortie)

    def test_environnement_du_gestionnaire_invisible(self):
        """P2-C : « env -i » efface tout ; l'unité ne garde que la liste blanche. Les variables du gestionnaire systemd
        (bus, Wayland, Hyprland, vrais XDG_*_HOME, clés exportées) n'arrivent PAS au moteur, même si --setenv ne les
        retire pas."""
        f = self.home / ".local/bin/codex"
        f.write_text("#!/bin/sh\nenv | sort\n")
        sortie = "".join(self.lancer_moteur(self.m, "codex"))
        noms = {l.split("=", 1)[0] for l in sortie.splitlines() if "=" in l}
        for fuite in ("DBUS_SESSION_BUS_ADDRESS", "WAYLAND_DISPLAY", "HYPRLAND_INSTANCE_SIGNATURE", "XDG_CONFIG_HOME",
                      "XDG_DATA_HOME", "XDG_RUNTIME_DIR", "DISPLAY"):
            self.assertNotIn(fuite, noms, f"{fuite} ne doit pas fuir dans le bac")
        self.assertIn("HOME", noms)
        self.assertIn("PATH", noms)
        self.assertIn(str(self.base()), sortie)                 # HOME pointe bien dans le faux dossier personnel du bac

    def test_ecriture_hors_du_bac_impossible(self):
        """P2-D : ProtectSystem=strict + /dev/shm en lecture seule : le bac n'écrit que dans ses dossiers, nulle part
        ailleurs (ni /dev/shm, partagé entre comptes, ni /var/spool/mail)."""
        f = self.home / ".local/bin/codex"
        f.write_text("#!/bin/sh\n"
                     'for p in /dev/shm/nc-evasion /var/spool/mail/nc-evasion /run/user/'
                     + str(os.getuid()) + '/nc-evasion; do\n'
                     '  if echo x > "$p" 2>/dev/null; then echo "ECRIT $p"; rm -f "$p"; else echo "BLOQUE $p"; fi\n'
                     'done\n')
        sortie = "".join(self.lancer_moteur(self.m, "codex"))
        self.assertNotIn("ECRIT", sortie, sortie)
        self.assertEqual(sortie.count("BLOQUE"), 3, sortie)
        self.assertFalse(os.path.exists("/dev/shm/nc-evasion"))



# ── Oh My Pi (omp) : ses connexions sont dans une base SQLite (~/.omp/agent/agent.db), filtrée à l'entrée du bac ──
FAUX_OMP = r"""#!/usr/bin/env python3
import json, os, sqlite3, sys, time
REEL = "@REEL@"
entree = sys.stdin.read()
try:
    cfg = json.load(open(REEL + "/nc-omp.json"))
except (OSError, ValueError):
    cfg = {}
ev = lambda o: print(json.dumps(o), flush=True)
delta = lambda t: ev({"type": "message_update", "assistantMessageEvent": {"type": "text_delta", "contentIndex": 0, "delta": t + "\n"}})
try:
    open(REEL + "/omp.log", "a").write("ARGS " + " ".join(sys.argv[1:]) + "\n")
except OSError:
    pass
ev({"type": "session", "id": "x"})
delta("debut")
delta("ARGS " + " ".join(sys.argv[1:]))
delta("ENTREE " + entree)
delta("HOME " + os.environ["HOME"])
delta("CWD " + os.getcwd())
base = os.environ["HOME"] + "/.omp/agent/agent.db"
if os.path.exists(base):
    c = sqlite3.connect(base)
    for (t,) in c.execute("select name from sqlite_master where type = 'table' order by name"):
        delta("TABLE " + t)
    delta("COLONNES " + " ".join(r[1] for r in c.execute("pragma table_info(auth_credentials)")))
    for l in c.execute("select version from auth_schema_version"):
        delta("VERSION %s" % l)
    for l in c.execute("select id, provider, credential_type, data, disabled_cause from auth_credentials order by id"):
        delta("LIGNE " + json.dumps(l))
    c.close()
else:
    delta("PASDEBASE")
for chemin in cfg.get("lire", []):
    try:
        delta("LU %s %s" % (chemin, open(chemin, "rb").read()[:200]))
    except OSError:
        delta("REFUSE " + chemin)
for chemin in cfg.get("ecrire", []):
    try:
        open(chemin, "w").write("x")
        delta("ECRIT " + chemin)
    except OSError:
        delta("NONECRIT " + chemin)
if cfg.get("exporter"):
    os.system("cp -r %s %s" % (os.environ["HOME"], cfg["exporter"]))
if cfg.get("outil"):
    ev({"type": "tool_execution_start", "toolCallId": "c", "toolName": "bash", "args": {}})
    time.sleep(30)
ev({"type": "message_end", "message": {"role": "assistant", "content": [], "stopReason": "stop"}})
"""
BASE_OMP = ".omp/agent/agent.db"


def faire_base_omp(home, lignes=None, version=8, chemin=BASE_OMP, colonne_en_plus=False):
    """Un agent.db FACTICE de la forme du vrai (auth_credentials et auth_schema_version de omp 18.12), avec ce qui ne doit
    jamais entrer dans le bac : jeton de rafraîchissement, clé d'API, ligne désactivée, réglages, cache."""
    import sqlite3
    f = home / chemin
    f.parent.mkdir(parents=True, exist_ok=True)
    f.unlink(missing_ok=True)
    fin = int((time.time() + 10 * 86400) * 1000)
    if lignes is None:
        lignes = [("anthropic", "oauth", {"access": "JETON-omp", "refresh": "SECRET-REFRESH", "expires": fin,
                                          "email": "u@example.org", "accountId": "compte-1", "inconnu": "SECRET-INCONNU"}, None),
                  ("openai", "api_key", {"key": "SECRET-CLE-OMP"}, None),
                  ("google", "oauth", {"access": "SECRET-DESACTIVE", "refresh": "SECRET-REFRESH", "expires": fin}, "revoked"),
                  ("copilot", "oauth", {"access": "SECRET-EXPIRE", "refresh": "SECRET-REFRESH",
                                        "expires": int((time.time() - 3600) * 1000)}, None)]
    c = sqlite3.connect(f)
    c.executescript("""
        CREATE TABLE auth_schema_version (id INTEGER PRIMARY KEY CHECK (id = 1), version INTEGER NOT NULL);
        CREATE TABLE auth_credentials (id INTEGER PRIMARY KEY AUTOINCREMENT, provider TEXT NOT NULL,
            credential_type TEXT NOT NULL, data TEXT NOT NULL, disabled_cause TEXT DEFAULT NULL, identity_key TEXT DEFAULT NULL,
            created_at INTEGER NOT NULL DEFAULT (strftime('%s','now')), updated_at INTEGER NOT NULL DEFAULT (strftime('%s','now')));
        CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT);
        CREATE TABLE cache (key TEXT PRIMARY KEY, value TEXT NOT NULL, expires_at INTEGER NOT NULL);
        INSERT INTO settings VALUES ('k', 'SECRET-REGLAGE');
        INSERT INTO cache VALUES ('k', 'SECRET-CACHE', 9999999999);""")
    if colonne_en_plus:
        c.execute("ALTER TABLE auth_credentials ADD COLUMN secret_en_plus TEXT DEFAULT 'SECRET-COLONNE'")
    c.execute("INSERT INTO auth_schema_version VALUES (1, ?)", (version,))
    for prov, type_, data, off in lignes:
        c.execute("INSERT INTO auth_credentials (provider, credential_type, data, disabled_cause, identity_key) VALUES (?,?,?,?,?)",
                  (prov, type_, json.dumps(data), off, f"email:{prov}"))
    c.commit()
    c.close()
    return f


class OmpTests:
    """Les essais d'Oh My Pi, communs au faux systemd-run et au vrai bac (voir les deux classes ci-dessous)."""
    exporte = True

    def installer_faux_omp(self):
        f = self.home / ".local/bin/omp"
        f.write_text(FAUX_OMP.replace("@REEL@", str(self.home)))
        f.chmod(0o755)
        faire_base_omp(self.home)

    def lancer_omp(self, **cfg):
        """Le chemin de nc-ia (appel_omp) : le texte de la réponse. cfg : ce que le faux omp fait en plus (nc-omp.json)."""
        (self.home / "nc-omp.json").write_text(json.dumps(cfg))
        with unittest.mock.patch.dict(os.environ):
            return "".join(self.m.appel_omp("c", "t", None, "question"))

    def base_source(self):
        f = self.home / BASE_OMP
        st = f.stat()
        return f.read_bytes(), st.st_mtime_ns, st.st_ino, sorted(os.listdir(f.parent))

    def test_omp_connexion_filtree_sans_jeton_de_rafraichissement(self):
        export = self.home / "export-omp"
        sortie = self.lancer_omp(**({"exporter": str(export)} if self.exporte else {}))
        self.assertIn("JETON-omp", sortie, "le jeton d'accès, lui, est copié")
        self.assertIn("u@example.org", sortie)
        self.assertIn("TABLE auth_credentials", sortie)
        self.assertIn("VERSION 8", sortie, "la version du schéma est gardée : omp recrée seul le reste")
        self.assertEqual(sortie.count("LIGNE"), 1, "une seule connexion oauth valable")
        for secret in ("SECRET-", "openai", "api_key", "revoked", "inconnu"):
            self.assertNotIn(secret, sortie)
        # « refresh » existe (omp lit refresh.trim() sans test d'absence) mais VIDE : jamais un jeton
        donnee = json.loads(json.loads(re.search(r"^LIGNE (.*)$", sortie, re.M)[1])[3])
        self.assertEqual(donnee["refresh"], "")
        self.assertEqual(donnee["access"], "JETON-omp")
        self.assertNotIn("TABLE settings", sortie)
        self.assertNotIn("TABLE cache", sortie)
        if not self.exporte:                          # le vrai bac n'écrit pas dans ~ : pas de copie du faux dossier
            return
        # et dans les fichiers du faux dossier personnel, octet par octet (pages libres comprises)
        octets = b"".join(f.read_bytes() for f in export.rglob("*") if f.is_file())
        self.assertIn(b"JETON-omp", octets)
        self.assertNotIn(b"SECRET", octets)
        self.assertIn(b'\\"refresh\\": \\"\\"', octets.replace(b'"refresh": ""', b'\\"refresh\\": \\"\\"'))
        self.assertEqual(octets.lower().count(b"refresh"), 1, "une seule fois : la clé, vide")
        bases = [f for f in export.rglob("*") if f.is_file()]
        self.assertEqual([f.name for f in bases], ["agent.db"], "ni -wal, ni -shm, ni autre fichier")
        self.assertEqual(oct(bases[0].stat().st_mode & 0o777), "0o600")

    def test_omp_vraie_base_intacte(self):
        avant = self.base_source()
        self.lancer_omp()
        self.lancer_omp()
        self.assertEqual(self.base_source(), avant)
        self.assertEqual(os.listdir(self.base()), [], "faux dossiers personnels jetés")

    def test_omp_jeton_expire_ou_trop_court_refuse(self):
        duree = self.m.duree_bac(self.m.DELAI_CLI)
        marge = self.m.MARGE_JETON
        for delta, lance in ((-10, False), (duree + marge - 60, False), (duree + marge + 60, True)):
            with self.subTest(delta=delta):
                (self.home / "omp.log").unlink(missing_ok=True)
                faire_base_omp(self.home, [("anthropic", "oauth", {"access": "JETON-omp", "refresh": "SECRET-REFRESH",
                                                                   "expires": int((time.time() + delta) * 1000)}, None)])
                if lance:
                    self.assertIn("JETON-omp", self.lancer_omp())
                    continue
                with self.assertRaises(self.m.ErreurIA) as e:
                    self.lancer_omp()
                self.assertIn("doit renouveler sa connexion" if delta < 0 else "expire dans", str(e.exception))
                self.assertIn("(omp)", str(e.exception))
                self.assertFalse((self.home / "omp.log").exists(), "omp n'a pas été lancé")
                self.assertEqual(os.listdir(self.base()), [], "rien ne reste dans la base")

    def test_omp_base_illisible_refusee_sauf_cle_d_api(self):
        (self.home / BASE_OMP).write_bytes(b"pas une base sqlite du tout, mais assez long pour ressembler a un fichier" * 3)
        (self.home / "omp.log").unlink(missing_ok=True)
        with self.assertRaises(self.m.ErreurIA) as e:
            self.lancer_omp()
        self.assertIn("doit renouveler sa connexion", str(e.exception))
        self.assertFalse((self.home / "omp.log").exists())
        with unittest.mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-test"}):
            self.assertIn("PASDEBASE", self.lancer_omp(), "avec une clé d'API de l'environnement, la base n'est pas copiée")
        self.assertIn("la clé d'API de l'environnement sert", self.journal_ia())

    def test_omp_cle_d_api_seule_ou_pas_de_base(self):
        # Clés d'API enregistrées seulement (aucune connexion oauth) : rien n'est copié, omp est lancé (il vivra de l'environnement)
        faire_base_omp(self.home, [("openai", "api_key", {"key": "SECRET-CLE-OMP"}, None)])
        sortie = self.lancer_omp()
        self.assertIn("PASDEBASE", sortie)
        self.assertNotIn("SECRET", sortie)
        (self.home / BASE_OMP).unlink()
        self.assertIn("PASDEBASE", self.lancer_omp())
        # La clé d'API de l'environnement est transmise (liste blanche d'omp), pas celle d'un autre moteur
        (self.home / ".local/bin/omp").write_text((self.home / ".local/bin/omp").read_text().replace(
            'delta("CWD "', 'delta("CLES " + json.dumps(sorted(k for k, v in os.environ.items() if v and k.endswith(("_KEY", "_TOKEN")))))\ndelta("CWD "'))
        with unittest.mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-a", "DASHSCOPE_API_KEY": "sk-d", "GITHUB_TOKEN": "gh"}):
            self.assertIn('CLES ["ANTHROPIC_API_KEY"]', self.lancer_omp())

    def test_omp_base_en_mode_wal_lue_sans_rien_ecrire_a_cote(self):
        """omp ferme : base en mode WAL sans journal, omp ouvert : un journal -wal avec les dernières écritures. Dans les
        deux cas, rien n'apparaît près de la vraie base (-shm, -wal) et le journal en cours est pris en compte."""
        import sqlite3
        f = self.home / BASE_OMP
        c = sqlite3.connect(f)
        c.execute("PRAGMA journal_mode=WAL")
        c.close()
        avant = self.base_source()
        self.assertIn("JETON-omp", self.lancer_omp())
        self.assertEqual(self.base_source(), avant, "ni -shm ni -wal laissés près de la vraie base")
        # omp ouvert : une connexion tient le journal avec une écriture non encore reportée dans la base
        w = sqlite3.connect(f)
        w.execute("PRAGMA wal_autocheckpoint=0")
        w.execute("UPDATE auth_credentials SET data = replace(data, 'JETON-omp', 'JETON-RECENT') WHERE provider = 'anthropic'")
        w.commit()
        try:
            self.assertGreater(os.path.getsize(str(f) + "-wal"), 0)
            sortie = self.lancer_omp()
        finally:
            w.close()
        self.assertIn("JETON-RECENT", sortie)
        self.assertEqual([n for n in os.listdir(self.base().parent) if n.startswith("omp-lecture-")], [], "copie temporaire effacée")

    def test_omp_base_deplacee_par_xdg(self):
        """Une fois « omp config migrate » fait, omp vit sous $XDG_DATA_HOME/omp : c'est cette base-là qu'on filtre."""
        faire_base_omp(self.home, chemin=".local/share/omp/agent.db", lignes=[
            ("anthropic", "oauth", {"access": "JETON-XDG", "refresh": "SECRET-REFRESH", "expires": int((time.time() + 86400) * 1000)}, None)])
        sortie = self.lancer_omp()
        self.assertIn("JETON-XDG", sortie)
        self.assertNotIn("JETON-omp", sortie, "pas l'ancienne base")

    def test_omp_schema_fixe_colonne_inconnue_non_copiee(self):
        faire_base_omp(self.home, colonne_en_plus=True)
        sortie = self.lancer_omp()
        self.assertIn("JETON-omp", sortie)
        self.assertIn("COLONNES id provider credential_type data disabled_cause identity_key created_at updated_at\n", sortie)
        self.assertNotIn("secret_en_plus", sortie)
        self.assertNotIn("SECRET", sortie)

    def test_omp_version_du_schema_toujours_8(self):
        """La table copiée est celle du schéma 8 : une vraie base en version 9 ne doit pas la marquer 9 (omp ne la
        migrerait pas)."""
        for version in (7, 9):
            with self.subTest(version=version):
                (self.home / BASE_OMP).unlink(missing_ok=True)
                faire_base_omp(self.home, version=version)
                sortie = self.lancer_omp()
                self.assertIn("JETON-omp", sortie)
                self.assertIn("VERSION 8\n", sortie)

    def test_omp_liens_symboliques_refuses(self):
        autre = self.home / "base-ailleurs.db"
        faire_base_omp(self.home, chemin="base-ailleurs.db")
        (self.home / BASE_OMP).unlink()
        (self.home / BASE_OMP).symlink_to(autre)
        (self.home / "omp.log").unlink(missing_ok=True)
        with self.assertRaises(self.m.ErreurIA):
            self.lancer_omp()
        self.assertFalse((self.home / "omp.log").exists(), "omp n'a pas été lancé")
        # le journal -wal en lien aussi
        (self.home / BASE_OMP).unlink()
        faire_base_omp(self.home)
        (self.home / (BASE_OMP + "-wal")).symlink_to(autre)
        with self.assertRaises(self.m.ErreurIA):
            self.lancer_omp()
        (self.home / (BASE_OMP + "-wal")).unlink()
        # un dossier $XDG_DATA_HOME/omp qui est un lien n'est pas suivi : la base habituelle sert
        (self.home / ".local/share").mkdir(parents=True, exist_ok=True)
        (self.home / ".local/share/omp").symlink_to(self.home / ".omp")
        self.assertIn("JETON-omp", self.lancer_omp())

    def test_omp_trop_gros_refuse(self):
        f = self.home / (BASE_OMP + "-wal")
        with open(f, "wb") as h:
            h.truncate(self.m.OMP_COPIE_MAX + 1)
        (self.home / "omp.log").unlink(missing_ok=True)
        with self.assertRaises(self.m.ErreurIA):
            self.lancer_omp()
        self.assertFalse((self.home / "omp.log").exists())
        f.unlink()
        # une donnée plus grosse que JETON_MAX n'est pas lue : refus s'il ne reste rien
        faire_base_omp(self.home, [("anthropic", "oauth", {"access": "JETON-omp", "refresh": "x", "expires": int((time.time() + 86400) * 1000),
                                                           "gras": "x" * (self.m.JETON_MAX + 10)}, None)])
        with self.assertRaises(self.m.ErreurIA):
            self.lancer_omp()
        self.assertFalse((self.home / "omp.log").exists())

    def test_omp_invite_ne_commence_jamais_par_une_barre(self):
        for consigne, texte in (("", "/mcp reauth serveur"), ("  ", "\n/commande perso"), ("c", "/x")):
            sortie = self.m.invite_omp(consigne, texte)
            self.assertFalse(sortie.lstrip().startswith("/"), sortie)
            self.assertIn(texte, sortie)
        with unittest.mock.patch.dict(os.environ):
            (self.home / "nc-omp.json").write_text("{}")
            sortie = "".join(self.m.appel_omp("", "/mcp reauth serveur", None, "question"))
        entree = sortie.split("ENTREE ", 1)[1]
        self.assertFalse(entree.lstrip().startswith("/"), entree)
        self.assertIn("/mcp reauth serveur", entree)

    def test_omp_dossiers_deplaces_par_pi_coding_agent_dir_et_pi_config_dir(self):
        bac = self.m.module_bac()
        home = self.home
        # PI_CODING_AGENT_DIR : comme CODEX_HOME (absolu, dans ~ ou /tmp ; sinon refus)
        self.assertEqual(bac.deplacements(home, {"PI_CODING_AGENT_DIR": str(home / "ailleurs")}), {".omp/agent": home / "ailleurs"})
        for mauvais in ("relatif/agent", "/etc/omp"):
            with self.assertRaises(ValueError):
                bac.deplacements(home, {"PI_CODING_AGENT_DIR": mauvais})
        # PI_CONFIG_DIR : un nom relatif à ~ ; « .. » ou une sortie de ~ : refus
        self.assertEqual(bac.deplacements(home, {"PI_CONFIG_DIR": ".pi"}), {".omp": home / ".pi"})
        self.assertEqual(bac.deplacements(home, {"PI_CONFIG_DIR": "/.pi"}), {".omp": home / ".pi"}, "barre de tête retirée")
        self.assertEqual(bac.deplacements(home, {"PI_CONFIG_DIR": ".omp"}), {})
        for mauvais in ("../x", "a/../../x", "..", "a:b"):
            with self.assertRaises(ValueError):
                bac.deplacements(home, {"PI_CONFIG_DIR": mauvais})
        # le plus précis d'abord
        depl = bac.deplacements(home, {"PI_CONFIG_DIR": ".pi", "PI_CODING_AGENT_DIR": str(home / "ailleurs")})
        self.assertEqual(bac.emplacement(home, ".omp/agent/agent.db", depl), home / "ailleurs/agent.db")
        self.assertEqual(bac.emplacement(home, ".omp/mcp.json", depl), home / ".pi/mcp.json")
        # nc-ia lit les identifiants là où omp les met
        (home / BASE_OMP).unlink()
        faire_base_omp(home, chemin="ailleurs/agent.db", lignes=[("anthropic", "oauth", {
            "access": "JETON-AILLEURS", "expires": int((time.time() + 86400) * 1000)}, None)])
        faire_base_omp(home, chemin=".pi/agent/agent.db", lignes=[("anthropic", "oauth", {
            "access": "JETON-PI", "expires": int((time.time() + 86400) * 1000)}, None)])
        with unittest.mock.patch.dict(os.environ, {"PI_CODING_AGENT_DIR": str(home / "ailleurs")}):
            self.assertIn("JETON-AILLEURS", self.lancer_omp())
        with unittest.mock.patch.dict(os.environ, {"PI_CONFIG_DIR": ".pi"}):
            self.assertIn("JETON-PI", self.lancer_omp())
        # une valeur refusée : rien n'est lancé
        (home / "omp.log").unlink(missing_ok=True)
        with unittest.mock.patch.dict(os.environ, {"PI_CONFIG_DIR": "../dehors"}):
            with self.assertRaises(self.m.ErreurIA):
                self.lancer_omp()
        self.assertFalse((home / "omp.log").exists())

    def test_omp_arguments_et_entree_standard(self):
        sortie = self.lancer_omp()
        ligne = re.search(r"^ARGS (.*)$", sortie, re.M)[1]
        args = ligne.split()
        self.assertEqual(args[:2], ["launch", "-p"])
        for o in ("--no-tools", "--no-extensions", "--no-session", "--no-title"):
            self.assertIn(o, args)
        self.assertEqual(args[args.index("--approval-mode") + 1], "always-ask")
        cwd = re.search(r"^CWD (.*)$", sortie, re.M)[1]
        self.assertEqual(args[args.index("--cwd") + 1], cwd)
        self.assertTrue(cwd.startswith(str(self.base())), "le dossier de travail vide de la demande")
        for interdit in ("--yolo", "--auto-approve", "--allow-home"):
            self.assertNotIn(interdit, args)
        self.assertIn("ENTREE c\n\nt", sortie, "l'invite arrive par l'entrée standard")
        self.assertTrue(re.search(r"^HOME " + re.escape(str(self.base())), sortie, re.M), "HOME : le faux dossier personnel")

    def test_omp_appel_d_outil_arrete_le_bac(self):
        debut = time.monotonic()
        with self.assertRaises(self.m.ErreurOutils):
            self.lancer_omp(outil=True)
        self.assertLess(time.monotonic() - debut, 15, "arrêté à l'appel d'outil, pas à la fin du programme (30 s)")
        time.sleep(0.5)
        self.assertEqual(os.listdir(self.base()), [])


@SANS_RACINE
class OmpFauxSystemdRun(OmpTests, Base):
    def setUp(self):
        AvecFauxSystemdRun.setUp(self)
        self.installer_faux_omp()

    lancements = AvecFauxSystemdRun.lancements

    def test_omp_options_du_bac_et_invite_hors_de_la_ligne_de_commande(self):
        self.oublier_sonde()
        self.lancer_omp()
        for bloc in self.lancements():
            self.assertIn("--expand-environment=no", bloc)
            self.assertIn("--description=nc-ia", bloc)
        reel = self.lancements()[-1]
        self.assertIn("--no-tools", reel)
        self.assertIn("always-ask", reel)
        for interdit in ("--yolo", "--auto-approve", "--allow-home", "c\n\nt"):
            self.assertNotIn(interdit, reel)
        self.assertFalse([l for l in reel if "question" in l or l == "t"])
        self.assertIn(str(self.home / ".local/bin/omp"), " ".join(reel) + shutil.which("omp", path=f"{self.home}/.local/bin"))


@unittest.skipUnless(_bus_utilisateur() and _racine_executable(),
                     "systemd-run, un bus utilisateur joignable et un dossier exécutable requis")
class OmpBacReel(OmpTests, Base):
    racine = RACINE_BAC
    exporte = False

    def setUp(self):
        BacReelIA.setUp(self)
        self.installer_faux_omp()

    nettoyer_unites = BacReelIA.nettoyer_unites

    def test_omp_ne_lit_que_sa_copie(self):
        """Dans le vrai bac : sa base filtrée (faux dossier personnel), jamais le vrai ~/.omp, ni ~/.ssh, ni la clé de nc-ia ;
        rien n'est écrit dans ~."""
        vrais = [str(self.home / BASE_OMP), str(self.home / ".ssh/id_ed25519"), str(self.home / ".config/nc/ia.conf")]
        sortie = self.lancer_omp(lire=vrais, ecrire=[str(self.home / "ecrit-par-le-bac"), str(self.home / ".omp/agent/x")])
        for v in vrais:
            self.assertIn(f"REFUSE {v}", sortie)
        self.assertIn("NONECRIT " + str(self.home / "ecrit-par-le-bac"), sortie)
        self.assertIn("NONECRIT " + str(self.home / ".omp/agent/x"), sortie)
        self.assertIn("JETON-omp", sortie)
        self.assertNotIn("SECRET", sortie)
        self.assertNotIn("FAUSSE-CLE", sortie)
        self.assertFalse((self.home / "ecrit-par-le-bac").exists())

    def test_omp_vraie_base_deplacee_illisible(self):
        """PI_CODING_AGENT_DIR et PI_CONFIG_DIR déplacent la vraie base : elle reste illisible dans le bac."""
        faire_base_omp(self.home, chemin="ailleurs/agent.db")
        faire_base_omp(self.home, chemin=".pi/agent/agent.db")
        for var, val, base in (("PI_CODING_AGENT_DIR", str(self.home / "ailleurs"), "ailleurs/agent.db"),
                               ("PI_CONFIG_DIR", ".pi", ".pi/agent/agent.db")):
            with self.subTest(var=var):
                with unittest.mock.patch.dict(os.environ, {var: val}):
                    sortie = self.lancer_omp(lire=[str(self.home / base)])
                self.assertIn(f"REFUSE {self.home / base}", sortie)

    def test_omp_dossiers_d_etat_et_de_cache_interdits(self):
        crees = [".omp", ".local/share/omp", ".local/state/omp", ".cache/omp"]
        for r in crees:
            (self.home / r).mkdir(parents=True, exist_ok=True)
            (self.home / r / "secret").write_text("SECRET-OMP")
        sortie = self.lancer_omp(lire=[str(self.home / r / "secret") for r in crees])
        self.assertNotIn("SECRET-OMP", sortie)
        for r in crees:
            self.assertIn(f"REFUSE {self.home / r / 'secret'}", sortie)


if __name__ == "__main__":
    unittest.main()

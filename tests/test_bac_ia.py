"""Le bac commun des IA en ligne de commande (nc-bac, utilisé par nc-noeud ET nc-ia) : Claude Code, Codex, Gemini CLI,
Qwen Code et OpenCode sont lancés avec les mêmes propriétés systemd, chacun voit ses propres identifiants et pas ceux
des autres. Deux étages :
  - un FAUX systemd-run qui note ses arguments puis exécute la commande (aucun vrai bac, aucun bus) ;
  - le VRAI bac (systemd-run --user, faux HOME sous /dev/shm comme BacReel de test_noeud) : un faux moteur lit son faux
    jeton, ne lit ni ~/.ssh factice ni le jeton d'un autre, n'écrit pas dans ~, et sa sortie arrive ligne par ligne.
Aucune vraie IA n'est lancée : les « moteurs » sont des scripts shell."""
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
import threading
import time
import unittest
import unittest.mock

from tests.test_noeud import _bus_utilisateur, HOME_BAC

# Le bac met /dev/shm en lecture seule (ProtectSystem=strict + ReadOnlyPaths) : les faux HOME des tests vont donc sous
# $XDG_RUNTIME_DIR réel (/run/user/<uid>, un tmpfs à soi), jamais /dev/shm ni /tmp (que PrivateTmp masque). Repli sur
# HOME_BAC seulement si /run/user/<uid> n'existe pas.
_RUNDIR = os.environ.get("NC_TEST_VRAI_RUNTIME") or f"/run/user/{os.getuid()}"
RACINE_BAC = _RUNDIR if os.path.isdir(_RUNDIR) and os.access(_RUNDIR, os.W_OK) else HOME_BAC


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


_CODEX_CLAIMS = {"sub": "user-1", "email": "u@example.org", "https://api.openai.com/auth": {"chatgpt_account_id": "compte-1"}}


def contenu_jeton(ident, marque=None):
    """Un fichier d'identifiants FACTICE de la forme du vrai (noms de champs des moteurs), avec la marque JETON-<ident>
    dans le jeton d'accès, et des champs qui ne doivent JAMAIS entrer dans le bac (SECRET-…). Codex : jetons en JWT
    valides (chatgpt_account_id == account_id, sub/email stables)."""
    m = marque or f"JETON-{ident}"
    return {
        "claude": {"claudeAiOauth": {"accessToken": m, "refreshToken": "r0", "expiresAt": 1, "scopes": ["user:inference"],
                                     "subscriptionType": "pro"},
                   "mcpOAuth": {"serveur": {"accessToken": "SECRET-MCP"}}},
        "codex": {"tokens": {"access_token": jwt(_CODEX_CLAIMS, m), "refresh_token": "r0",
                             "id_token": jwt(_CODEX_CLAIMS), "account_id": "compte-1"},
                  "last_refresh": "2026-01-01T00:00:00Z", "OPENAI_API_KEY": "SECRET-CLE-CODEX"},
        "gemini-cli": {"access_token": m, "refresh_token": "r0", "expiry_date": 1, "token_type": "Bearer"},
        "qwen": {"access_token": m, "refresh_token": "r0", "expiry_date": 1, "token_type": "Bearer",
                 "resource_url": "portal.qwen.ai"},
        "opencode": {"anthropic": {"type": "oauth", "access": m, "refresh": "r0", "expires": 1},
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
    return jwt(_CODEX_CLAIMS, marque) if ident == "codex" else marque


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
        communes = {"PrivateUsers=yes", "NoNewPrivileges=yes", "PrivatePIDs=yes", "SystemCallFilter=~@debug @keyring",
                    "ProtectHome=read-only", "PrivateTmp=yes", "RestrictAddressFamilies=AF_INET AF_INET6",
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
                    if sonde_prop.startswith(("PrivateUsers", "NoNewPrivileges", "PrivatePIDs", "SystemCallFilter", "ProtectHome")):
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
                 ".local/state/nc-ia"]
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

    # ── P2-1 : Codex (date dans le JWT, access_token forcément JWT) et Gemini (refresh non copié si valide) ──────────
    def _codex(self, exp_delta, marque="A"):
        claims = dict(_CODEX_CLAIMS, exp=int(time.time()) + exp_delta)
        return {"tokens": {"access_token": jwt(claims, marque), "refresh_token": "RT", "id_token": jwt(_CODEX_CLAIMS),
                           "account_id": "compte-1"}, "last_refresh": "2026-01-01T00:00:00Z"}

    def test_codex_date_dans_le_jwt_refresh_et_opaque(self):
        m = self.m
        proj = lambda o: m.projeter(o, m.SCHEMAS["codex"])
        # jeton valide longtemps : son refresh n'est PAS copié dans le bac, et un retour est refusé (rien à rafraîchir)
        donne_valide = proj(self._codex(3600))
        self.assertNotIn("refresh_token", m.sans_refresh_si_valide("codex", donne_valide).get("tokens", {}))
        with self.assertRaises(ValueError):
            m.verifier_retour("codex", donne_valide, proj(self._codex(3600, "B")))
        # jeton expiré : refresh copié, et un rafraîchissement normal est accepté
        donne_exp = proj(self._codex(-10))
        self.assertIn("refresh_token", m.sans_refresh_si_valide("codex", donne_exp).get("tokens", {}))
        m.verifier_retour("codex", donne_exp, proj(self._codex(-10, "B")))        # ne lève pas
        # access_token opaque (pas un JWT) : refusé au retour
        opaque = proj(self._codex(-10, "B"))
        opaque["tokens"]["access_token"] = "opaque-ATTAQUANT"
        with self.assertRaises(ValueError):
            m.verifier_retour("codex", donne_exp, opaque)

    def test_gemini_refresh_non_copie_si_valide(self):
        m = self.m
        futur = {"access_token": "a", "refresh_token": "RT", "expiry_date": int((time.time() + 3600) * 1000)}
        self.assertNotIn("refresh_token", m.sans_refresh_si_valide("gemini-cli", futur))
        passe = {"access_token": "a", "refresh_token": "RT", "expiry_date": int((time.time() - 10) * 1000)}
        self.assertIn("refresh_token", m.sans_refresh_si_valide("gemini-cli", passe))

    def test_codex_access_opaque_pas_copie(self):
        """Un access_token opaque dans le vrai fichier : le jeton n'est pas copié dans le bac (ni refresh), journalisé."""
        reel = self.home / JETONS["codex"]
        o = self._codex(-10)
        o["tokens"]["access_token"] = "opaque"
        reel.write_text(json.dumps(o))
        sortie = "".join(self.lancer_moteur(self.m, "codex", NC_TEST_RELATIFS=JETONS["codex"]))
        self.assertIn("REFUSE", sortie)                         # le faux dossier personnel n'a pas le fichier
        self.assertNotIn("opaque", sortie)
        self.assertIn("access_token du vrai fichier n'est pas un JWT", self.journal_ia())

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

    # ── P1-2 : retour champ par champ ─────────────────────────────────────────────────────────────────────────────
    def retour_refuse(self, ident, neuf, raison):
        """Le moteur laisse neuf (un objet) à la place de son jeton : le vrai fichier ne bouge pas, le journal dit
        pourquoi, sans jamais écrire le jeton."""
        reel = self.home / JETONS[ident]
        avant = reel.read_text()
        (self.home / "notifs.log").unlink(missing_ok=True)
        self.lancer_moteur(self.m, ident, NC_TEST_RAFRAICHIR=JETONS[ident], NC_TEST_CONTENU=json.dumps(neuf))
        self.assertEqual(reel.read_text(), avant, f"{ident} : {raison}")
        j = self.journal_ia()
        self.assertIn(f"{ident} : retour de {JETONS[ident]} refusé", j)
        self.assertIn(raison, j)
        self.assertNotIn("JETON-", j)
        self.assertNotIn("VOLE", j)
        # P3-2a : un retour refusé (inattendu) se voit par une notification — mais jamais la valeur du jeton
        notifs = self.notifs()
        self.assertIn(f"retour de jeton de {self.m.nom(ident)} refusé", notifs)
        self.assertNotIn("VOLE", notifs)

    def test_retour_refuse_changement_de_serveur_ou_de_compte(self):
        cas = []
        n = rafraichi("qwen", "VOLE")
        n["resource_url"] = "attaquant.example"
        cas.append(("qwen", n, "resource_url a changé"))
        n = rafraichi("codex", "VOLE")
        n["tokens"]["account_id"] = "autre-compte"
        cas.append(("codex", n, "tokens.account_id a changé"))
        n = rafraichi("claude", "VOLE")
        n["mcpOAuth"] = {"x": {"accessToken": "VOLE"}}
        cas.append(("claude", n, "nouvelle clé mcpOAuth"))
        n = rafraichi("claude", "VOLE")
        n["claudeAiOauth"]["baseUrl"] = "https://attaquant.example"
        cas.append(("claude", n, "nouvelle clé claudeAiOauth.baseUrl"))
        n = rafraichi("opencode", "VOLE")
        n["distant2"] = {"type": "wellknown", "key": "https://attaquant.example", "token": "t"}
        cas.append(("opencode", n, "nouvelle entrée distant2"))
        n = rafraichi("opencode", "VOLE")
        n["anthropic"]["type"] = "wellknown"
        cas.append(("opencode", n, "anthropic.type a changé"))
        n = rafraichi("opencode", "VOLE")
        n["anthropic"]["accountId"] = "autre"
        cas.append(("opencode", n, "anthropic.accountId a changé"))
        n = rafraichi("gemini-cli", "VOLE")
        n["access_token"] = {"objet": "VOLE"}
        cas.append(("gemini-cli", n, "access_token : valeur de jeton invalide"))
        n = rafraichi("gemini-cli", "VOLE")
        n["refresh_token"] = "autre-refresh"               # refresh_token « fixe » pour Gemini : tout refusé
        cas.append(("gemini-cli", n, "refresh_token a changé"))
        n = rafraichi("codex", "VOLE")
        n["OPENAI_API_KEY"] = "VOLE"
        cas.append(("codex", n, "OPENAI_API_KEY est apparu"))
        for ident, neuf, raison in cas:
            with self.subTest(raison):
                (self.home / ".local/state/nc-ia/journal").unlink(missing_ok=True)
                self.retour_refuse(ident, neuf, raison)

    def test_retour_seulement_les_champs_de_jeton(self):
        """Un rafraîchissement normal revient, champ par champ : le reste du vrai fichier (mcpOAuth, entrées api et
        wellknown d'OpenCode, clé de Codex) est gardé tel quel, un champ « copie » changé n'est pas rapporté."""
        for ident in IDENTS:
            with self.subTest(ident):
                reel = self.home / JETONS[ident]
                (self.home / "notifs.log").unlink(missing_ok=True)
                neuf = rafraichi(ident)
                if ident == "claude":
                    neuf["claudeAiOauth"]["scopes"] = ["autre"]               # « copie » : ignoré
                    neuf["claudeAiOauth"]["refreshTokenExpiresAt"] = 99       # écrit par Claude Code au rafraîchissement
                self.lancer_moteur(self.m, ident, NC_TEST_RAFRAICHIR=JETONS[ident], NC_TEST_CONTENU=json.dumps(neuf))
                o = json.loads(reel.read_text())
                self.assertEqual(jeton_acces(ident, o), "RAFRAICHI")
                attendu = contenu_jeton(ident)
                if ident == "claude":
                    self.assertEqual(o["mcpOAuth"], attendu["mcpOAuth"])
                    self.assertEqual(o["claudeAiOauth"]["scopes"], ["user:inference"])
                    self.assertEqual(o["claudeAiOauth"]["refreshTokenExpiresAt"], 99)
                if ident == "codex":
                    self.assertEqual(o["OPENAI_API_KEY"], "SECRET-CLE-CODEX")
                if ident == "opencode":
                    self.assertEqual((o["openai"], o["distant"]), (attendu["openai"], attendu["distant"]))
                self.assertIn(f"{ident} : jeton de {JETONS[ident]} mis à jour par le bac", self.journal_ia())
                self.assertNotIn("RAFRAICHI", self.journal_ia())
                # P3-2b : un rafraîchissement normal ne notifie pas (seulement le journal) ; la notification est réservée
                # aux retours inattendus (refusés/abandonnés)
                self.assertEqual(self.notifs(0.3), "", "pas de notification pour un rafraîchissement normal")
                # (P3-a) aucun fichier temporaire laissé à côté du vrai fichier
                self.assertEqual([x for x in os.listdir(reel.parent) if ".nc-ia-" in x], [])

    def test_lien_physique_jamais_rapporte(self):
        """Sans bac (même système de fichiers) : un lien physique vers un secret n'est pas lu (st_nlink != 1)."""
        (self.fb / "systemd-run").write_text("#!/bin/sh\nexit 1\n")
        self.regler("IA_BAC_REPLI=oui\n")
        self.oublier_sonde()
        secret = self.base().parent.parent / "secret.json"            # même système de fichiers que le faux dossier
        secret.write_text(json.dumps(rafraichi("codex", "SECRET-DUR")))
        reel = self.home / JETONS["codex"]
        avant = reel.read_text()
        sortie = "".join(self.lancer_moteur(self.m, "codex", NC_TEST_LIEN_DUR=JETONS["codex"], NC_TEST_CIBLE=str(secret)))
        self.assertIn("LIEN-DUR", sortie)
        self.assertEqual(reel.read_text(), avant)
        self.assertIn("lien physique", self.journal_ia())

    def test_json_trop_imbrique_et_dossiers_supprimes(self):
        """json.loads lève RecursionError sur [[[[… : la demande se termine, rien n'est rapporté, tout est supprimé."""
        reel = self.home / JETONS["gemini-cli"]
        avant = reel.read_text()
        sortie = self.lancer_moteur(self.m, "gemini-cli", NC_TEST_IMBRIQUER=JETONS["gemini-cli"])
        self.assertIn("fin\n", sortie)
        self.assertEqual(reel.read_text(), avant)
        self.assertEqual(os.listdir(self.base()), [])
        self.assertIn("gemini-cli : retour de", self.journal_ia())

    def test_retour_qui_plante_supprime_quand_meme(self):
        with unittest.mock.patch.object(self.m, "lire_sans_lien", side_effect=RuntimeError("panne")):
            self.lancer_moteur(self.m, "codex", NC_TEST_RAFRAICHIR=JETONS["codex"],
                               NC_TEST_CONTENU=json.dumps(rafraichi("codex")))
        self.assertEqual(os.listdir(self.base()), [])
        self.assertIn("codex : retour de .codex/auth.json abandonné (RuntimeError)", self.journal_ia())

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
                    self.assertEqual(jeton_acces(ident, json.loads(f.read_text())), f"RETOUR-{ident}", "rapporté au bon endroit")
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

    # ── P3-a : verrou du vrai fichier ──────────────────────────────────────────────────────────────────────────────
    def test_vrai_fichier_verrouille_pas_de_retour(self):
        reel = self.home / JETONS["qwen"]
        avant = reel.read_text()
        fd = os.open(reel, os.O_RDONLY)
        self.addCleanup(os.close, fd)
        fcntl.flock(fd, fcntl.LOCK_EX)
        self.m.VERROU_ATTENTE = 0.3
        self.lancer_moteur(self.m, "qwen", NC_TEST_RAFRAICHIR=JETONS["qwen"], NC_TEST_CONTENU=json.dumps(rafraichi("qwen")))
        self.assertEqual(reel.read_text(), avant)
        self.assertIn("vrai fichier verrouillé", self.journal_ia())

    def test_vrai_fichier_verrouille_un_instant_attend(self):
        reel = self.home / JETONS["qwen"]
        fd = os.open(reel, os.O_RDONLY)
        self.addCleanup(os.close, fd)
        fcntl.flock(fd, fcntl.LOCK_EX)
        threading.Timer(0.5, fcntl.flock, (fd, fcntl.LOCK_UN)).start()
        self.lancer_moteur(self.m, "qwen", NC_TEST_RAFRAICHIR=JETONS["qwen"], NC_TEST_CONTENU=json.dumps(rafraichi("qwen")))
        self.assertEqual(jeton_acces("qwen", json.loads(reel.read_text())), "RAFRAICHI")

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

    def test_jeton_rafraichi_garde_le_reste_jete(self):
        for ident, rel in JETONS.items():
            with self.subTest(ident):
                reel = self.home / rel
                config = (self.home / CONFIGS[ident]).read_text()
                self.lancer_moteur(self.m, ident, NC_TEST_RAFRAICHIR=f"{rel} {CONFIGS[ident]}",
                                   NC_TEST_CONTENU=json.dumps(rafraichi(ident)))
                self.assertEqual(jeton_acces(ident, json.loads(reel.read_text())), "RAFRAICHI", "le jeton rafraîchi est gardé")
                self.assertEqual((self.home / CONFIGS[ident]).read_text(), config, "la config n'est jamais rapportée")
                # un moteur qui REMPLACE le fichier (écriture dans un temporaire puis mv) marche aussi
                self.lancer_moteur(self.m, ident, NC_TEST_RENOMMER=rel, NC_TEST_CONTENU=json.dumps(rafraichi(ident, "RENOMME")))
                self.assertEqual(jeton_acces(ident, json.loads(reel.read_text())), "RENOMME")
                # un jeton cassé (plus du JSON) n'est pas rapporté, et ce retour inattendu notifie (refusé)
                (self.home / "notifs.log").unlink(missing_ok=True)
                self.lancer_moteur(self.m, ident, NC_TEST_CASSER=rel)
                self.assertEqual(jeton_acces(ident, json.loads(reel.read_text())), "RENOMME")
                self.assertIn(f"{ident} : retour de {rel} refusé (plus du JSON)", self.journal_ia())
                self.assertIn(f"retour de jeton de {self.m.nom(ident)} refusé", self.notifs())

    def test_jeton_change_entre_temps_pas_ecrase(self):
        """Une session à toi a rafraîchi le jeton pendant la demande : on ne l'écrase pas."""
        reel = self.home / JETONS["codex"]
        d = self.m.Demande("codex")
        try:
            (d.home / JETONS["codex"]).write_text(json.dumps(rafraichi("codex", "DU-MOTEUR")))
            reel.write_text(json.dumps(rafraichi("codex", "DE-TA-SESSION")))
        finally:
            d.finir()
        self.assertEqual(jeton_acces("codex", json.loads(reel.read_text())), "DE-TA-SESSION")
        self.assertIn("a changé de ton côté", self.journal_ia())
        self.assertEqual(os.listdir(self.base()), [])

    def test_lien_vers_un_secret_jamais_rapporte(self):
        """P1-1 : le moteur remplace son jeton (ou son dossier) par un lien vers un secret lisible HORS du bac (docker,
        gcloud…) : nc-ia ne suit aucun lien, le vrai fichier ne change pas, le secret ne revient jamais au bac."""
        secret = self.home / ".docker/config.json"
        secret.parent.mkdir()
        secret.write_text(json.dumps(rafraichi("claude", "SECRET-DOCKER")))
        dossier = self.home / ".config/gcloud"
        dossier.mkdir(parents=True)
        (dossier / "auth.json").write_text(json.dumps(rafraichi("codex", "SECRET-GCLOUD")))
        for ident, lien, cible in (("claude", JETONS["claude"], secret), ("codex", ".codex", dossier)):
            with self.subTest(ident):
                reel = self.home / JETONS[ident]
                avant = reel.read_text()
                sortie = "".join(self.lancer_moteur(self.m, ident, NC_TEST_LIEN=lien, NC_TEST_CIBLE=str(cible)))
                self.assertIn(f"LIEN {lien}", sortie)
                self.assertEqual(reel.read_text(), avant, "le vrai jeton n'a pas bougé")
                self.assertIn(f"{ident} : retour de {JETONS[ident]} refusé (lien symbolique", self.journal_ia())
                # et la demande suivante ne voit pas le secret
                sortie = "".join(self.lancer_moteur(self.m, ident, NC_TEST_RELATIFS=JETONS[ident]))
                self.assertNotIn("SECRET-", sortie)
                self.assertIn(marqueur(ident, f"JETON-{ident}"), sortie)

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
            time.sleep(0.5)
            r = subprocess.run(["systemctl", "--user", "list-units", "--no-legend", "nc-ia-test-*"], capture_output=True, text=True)
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


if __name__ == "__main__":
    unittest.main()

"""Le bac commun des IA en ligne de commande (nc-bac, utilisé par nc-noeud ET nc-ia) : Claude Code, Codex, Gemini CLI,
Qwen Code et OpenCode sont lancés avec les mêmes propriétés systemd, chacun voit ses propres identifiants et pas ceux
des autres. Deux étages :
  - un FAUX systemd-run qui note ses arguments puis exécute la commande (aucun vrai bac, aucun bus) ;
  - le VRAI bac (systemd-run --user, faux HOME sous /dev/shm comme BacReel de test_noeud) : un faux moteur lit son faux
    jeton, ne lit ni ~/.ssh factice ni le jeton d'un autre, n'écrit pas dans ~, et sa sortie arrive ligne par ligne.
Aucune vraie IA n'est lancée : les « moteurs » sont des scripts shell."""
import importlib.machinery
import importlib.util
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

REPO = Path(__file__).resolve().parents[1]
BIN = REPO / "home/.local/bin"
IDENTS = {"claude": "claude", "codex": "codex", "gemini-cli": "gemini", "qwen": "qwen", "opencode": "opencode"}
# Le dossier (relatif à ~) où chaque moteur range ses identifiants, et le fichier-jeton FACTICE qu'on y met
JETONS = {"claude": ".claude/.credentials.json", "codex": ".codex/auth.json", "gemini-cli": ".gemini/oauth_creds.json",
          "qwen": ".qwen/oauth_creds.json", "opencode": ".local/share/opencode/auth.json"}
CONFIGS = {"claude": ".claude/settings.json", "codex": ".codex/config.toml", "gemini-cli": ".gemini/settings.json",
           "qwen": ".qwen/settings.json", "opencode": ".config/opencode/opencode.json"}

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
for f in $NC_TEST_RAFRAICHIR; do echo '{"t": "RAFRAICHI"}' > "$HOME/$f"; done
for f in $NC_TEST_RENOMMER; do echo '{"t": "RENOMME"}' > "$HOME/$f.tmp" && mv "$HOME/$f.tmp" "$HOME/$f"; done
for f in $NC_TEST_CASSER; do echo 'pas du json' > "$HOME/$f"; done
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
           "XDG_CONFIG_HOME": str(home / ".config"), "PATH": path, "NC_LANGUE": "fr", "NC_IA_EN_LIGNE": "1"}
    with unittest.mock.patch.dict(os.environ, env):
        l = importlib.machinery.SourceFileLoader("nc_ia_bac", str(BIN / "nc-ia"))
        m = importlib.util.module_from_spec(importlib.util.spec_from_loader("nc_ia_bac", l))
        avant = os.environ["PATH"]
        l.exec_module(m)
        os.environ["PATH"] = avant
    m.HOME = home
    return m


class Base(unittest.TestCase):
    racine = HOME_BAC if os.path.isdir(HOME_BAC) else None      # /dev/shm : jamais /tmp (PrivateTmp le masque)

    def faux_home(self):
        d = tempfile.mkdtemp(prefix="nc-bac-ia-", dir=self.racine)
        self.addCleanup(lambda: shutil.rmtree(d, ignore_errors=True))
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
            f.write_text('{"t": "JETON-%s"}' % ident)
        for ident, rel in CONFIGS.items():
            f = home / rel
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text("CONFIG-" + ident)
        for prog in IDENTS.values():
            f = home / ".local/bin" / prog
            f.write_text(MOTEUR.replace("@REEL@", str(home)))
            f.chmod(0o755)
        return home

    def env_hote(self, path, **plus):
        """L'environnement de nc-ia pendant le test : faux HOME, runtime et état dans le faux HOME."""
        env = {"HOME": str(self.home), "XDG_RUNTIME_DIR": str(self.home / "run"), "XDG_STATE_HOME": str(self.home / ".local/state"),
               "XDG_CONFIG_HOME": str(self.home / ".config"), "PATH": path, "NC_IA_BAC": ""}
        env.update(plus)
        p = unittest.mock.patch.dict(os.environ, env)
        p.start()
        self.addCleanup(p.stop)

    def oublier_sonde(self):
        self.m._BAC["tient"] = None
        (self.home / "run/nc-ia-bac").unlink(missing_ok=True)

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
        sc.write_text("#!/bin/sh\nexit 0\n")
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
                self.assertEqual(len(blocs), 2, "la sonde, puis le vrai lancement")
                reel = blocs[1]
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
                self.assertIn(f'InaccessiblePaths="{self.home}/run"', props)

    def test_aucun_vrai_dossier_de_moteur_lisible_ni_inscriptible(self):
        """Ni le sien ni ceux des autres : le moteur travaille dans un faux dossier personnel (copie jetable)."""
        (self.home / ".claude.json").write_text("{}")
        tous = [".claude", ".claude.json", ".codex", ".gemini", ".qwen", ".config/opencode", ".local/share/opencode"]
        for ident in IDENTS:
            with self.subTest(ident):
                self.journal.unlink(missing_ok=True)
                self.oublier_sonde()
                self.lancer_moteur(self.m, ident, NC_TEST_FICHIERS="")
                props = self.props(self.lancements()[1])
                inacc = {p[len('InaccessiblePaths="'):-1] for p in props if p.startswith("InaccessiblePaths=")}
                for rel in tous:
                    self.assertIn(str(self.home / rel), inacc, f"{ident} ne doit pas lire le vrai {rel}")
                rw = [p[len("ReadWritePaths="):] for p in props if p.startswith("ReadWritePaths=")]
                self.assertEqual(len(rw), 2, rw)
                self.assertIn("/travail/nc-ia-", rw[0])               # le dossier de travail vide
                self.assertIn("/etat/nc-ia-home-", rw[1])             # le faux dossier personnel
                for rel in tous:
                    self.assertFalse(any(r.startswith(str(self.home / rel)) for r in rw), f"{ident} n'écrit pas dans {rel}")
                self.assertFalse(any(p.startswith("ReadOnlyPaths=") and p != f"ReadOnlyPaths={self.home}" for p in props))

    def test_home_du_moteur_et_copie_de_ses_fichiers(self):
        (self.home / ".claude.json").write_text('{"c": 1}')
        for ident, rel in JETONS.items():
            with self.subTest(ident):
                sortie = "".join(self.lancer_moteur(self.m, ident, NC_TEST_RELATIFS=f"{rel} {CONFIGS[ident]}"))
                self.assertIn(f"JETON-{ident}", sortie)                  # sa copie du jeton
                for autre in JETONS:
                    if autre != ident:
                        self.assertNotIn(f"JETON-{autre}", sortie)
                self.assertIn("/etat/nc-ia-home-", sortie)               # le chemin lu est celui du faux dossier personnel

    def test_sortie_et_dossier_de_travail(self):
        sortie = self.lancer_moteur(self.m, "qwen", NC_TEST_FICHIERS="")
        cwd = [l for l in sortie if l.startswith("CWD")][0]
        self.assertIn(".local/state/nc-ia/travail/nc-ia-", cwd)             # /tmp est privé dans le bac
        self.assertFalse(os.path.exists(cwd.split(" ", 1)[1].strip()), "dossier supprimé après la demande")
        self.assertEqual(list((self.home / ".local/state/nc-ia/conf").glob("*")), [], "dossier de réglages supprimé")
        self.assertEqual(list((self.home / ".local/state/nc-ia/etat").glob("*")), [], "faux dossier personnel supprimé")

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
                 ".cache/huggingface", ".config/Cursor/User/globalStorage"]
        for r in crees:
            f = self.home / r
            f.parent.mkdir(parents=True, exist_ok=True)
            f.mkdir() if not r.endswith("token") else f.write_text("x")
        self.oublier_sonde()
        self.lancer_moteur(self.m, "codex", NC_TEST_FICHIERS="")
        inacc = {p[len('InaccessiblePaths="'):-1] for p in self.props(self.lancements()[1]) if p.startswith("InaccessiblePaths=")}
        for r in crees:
            self.assertIn(str(self.home / r), inacc, r)

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
                reel = self.lancements()[1]
                log = (self.home / "moteur.log").read_text()
                self.assertIn("ENTREE c\n\nt", log, "l'invite arrive par l'entrée standard")
                self.assertNotIn("c\n\nt", "\n".join(reel).replace("ENTREE", ""))
                self.assertEqual(len([l for l in reel if l == "c"]), 0)
        # Gemini, Qwen, OpenCode : l'invite reste en argument, mais la description masque le journal
        self.journal.unlink(missing_ok=True)
        self.oublier_sonde()
        self.lancer_moteur(self.m, "qwen", NC_TEST_FICHIERS="")
        self.assertIn("--description=nc-ia", self.lancements()[1])

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
                setenv = {a.split("=", 1)[1] for a in self.lancements()[1] if a.startswith("--setenv=")}
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
        reel = self.lancements()[1]
        regle = [a for a in reel if a.startswith("Read(")]
        self.assertEqual(len(regle), 1, reel)
        self.assertRegex(regle[0], r"^Read\(//dev/shm/nc-bac-ia-[^/]+/\.local/state/nc-ia/travail/nc-ia-[^/]+/\*\*\)$")
        self.assertNotIn("Read", [a for a in reel if a == "Read"][1:], "pas de « Read » seul dans --allowedTools")
        i = reel.index("--allowedTools")
        self.assertTrue(reel[i + 1].startswith("Read("))

    def test_dossier_de_travail_dans_l_etat_meme_sans_bac(self):
        (self.fb / "systemd-run").write_text("#!/bin/sh\nexit 1\n")
        self.regler("IA_BAC_REPLI=oui\n")
        self.oublier_sonde()
        sortie = self.lancer_moteur(self.m, "codex", NC_TEST_FICHIERS="")
        cwd = [l for l in sortie if l.startswith("CWD")][0]
        self.assertIn(".local/state/nc-ia/travail/nc-ia-", cwd)
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


@unittest.skipUnless(_bus_utilisateur() and os.path.isdir(HOME_BAC),
                     "systemd-run, un bus utilisateur joignable et /dev/shm requis")
class BacReelIA(Base):
    """Le VRAI bac : faux HOME sous /dev/shm (jamais /tmp, que PrivateTmp masque), faux jetons, faux moteurs."""
    racine = HOME_BAC

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
                copie = f"/etat/nc-ia-home-"
                self.assertRegex(texte, rf"LU \S+{re.escape(copie)}\S+/{re.escape(JETONS[ident])} \{{'t': 'JETON-{re.escape(ident)}'\}}")
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
        self.assertEqual(list((self.home / ".local/state/nc-ia/etat").glob("*")), [], "faux dossiers personnels jetés")
        self.assertFalse((self.home / ".claude/hooks").exists())
        self.assertFalse((self.home / ".codex/rules").exists())

    def test_jeton_rafraichi_garde_le_reste_jete(self):
        for ident, rel in JETONS.items():
            with self.subTest(ident):
                reel = self.home / rel
                reel.write_text('{"t": "JETON-' + ident + '"}')
                self.lancer_moteur(self.m, ident, NC_TEST_RAFRAICHIR=f"{rel} {CONFIGS[ident]}")
                self.assertEqual(reel.read_text().strip(), '{"t": "RAFRAICHI"}', "le jeton rafraîchi est gardé")
                self.assertEqual((self.home / CONFIGS[ident]).read_text(), "CONFIG-" + ident, "la config n'est jamais rapportée")
                # un moteur qui REMPLACE le fichier (écriture dans un temporaire puis mv) marche aussi
                self.lancer_moteur(self.m, ident, NC_TEST_RENOMMER=rel)
                self.assertEqual(reel.read_text().strip(), '{"t": "RENOMME"}')
                # un jeton cassé (plus du JSON) n'est pas rapporté
                self.lancer_moteur(self.m, ident, NC_TEST_CASSER=rel)
                self.assertEqual(reel.read_text().strip(), '{"t": "RENOMME"}')

    def test_jeton_change_entre_temps_pas_ecrase(self):
        """Une session à toi a rafraîchi le jeton pendant la demande : on ne l'écrase pas."""
        reel = self.home / JETONS["codex"]
        home_moteur, retour = self.m.preparer_etat("codex")
        try:
            (Path(home_moteur) / JETONS["codex"]).write_text('{"t": "DU-MOTEUR"}')
            reel.write_text('{"t": "DE-TA-SESSION"}')
            retour()
        finally:
            shutil.rmtree(home_moteur, ignore_errors=True)
        self.assertEqual(reel.read_text(), '{"t": "DE-TA-SESSION"}')

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
        bac = self.m.module_bac()
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


if __name__ == "__main__":
    unittest.main()

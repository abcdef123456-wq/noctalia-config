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
{ echo "--LANCEMENT--"; printf '%s\\n' "$@"; } >> "$NC_TEST_SR_JOURNAL"
while [ "$1" != "--" ]; do shift; done; shift
exec "$@"
"""

# Un faux moteur : montre ce qu'il lit et écrit. Argument 1 de l'environnement : MOTEUR_JETON = son jeton
MOTEUR = r"""#!/bin/sh
[ "$1" = "--version" ] && { echo "opencode v2.1.2"; exit 0; }
# Claude Code répond en JSON (stream-json), les autres en texte
out() { case "$0" in */claude) printf '{"type":"stream_event","event":{"delta":{"type":"text_delta","text":"%s\\n"}}}\n' "$1";; *) echo "$1";; esac; }
out "debut"
lire() { if c=$(cat "$1" 2>/dev/null); then out "LU $1 $c"; else out "REFUSE $1"; fi; }
for f in $NC_TEST_FICHIERS; do lire "$f"; done
ecrire() { if ( echo x > "$1" ) 2>/dev/null; then out "ECRIT $1"; else out "NONECRIT $1"; fi; }
for f in $NC_TEST_ECRIRE; do ecrire "$f"; done
out "CWD $(pwd -P)"
sleep ${NC_TEST_PAUSE:-0}
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
            f.write_text("JETON-" + ident)
        for ident, rel in CONFIGS.items():
            f = home / rel
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text("CONFIG-" + ident)
        for prog in IDENTS.values():
            f = home / ".local/bin" / prog
            f.write_text(MOTEUR)
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
        with unittest.mock.patch.dict(os.environ, env):
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
        sr.write_text(FAUX_SYSTEMD_RUN)
        sr.chmod(0o755)
        sc = fb / "systemctl"
        sc.write_text("#!/bin/sh\nexit 0\n")
        sc.chmod(0o755)
        self.journal = self.home / "sr.journal"
        self.fb = fb
        self.m = charger_ia(self.home, f"{fb}:{self.home}/.local/bin:/usr/bin:/bin")
        self.env_hote(f"{fb}:{self.home}/.local/bin:/usr/bin:/bin", NC_TEST_SR_JOURNAL=str(self.journal))
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

    def test_ses_identifiants_lisibles_pas_ceux_des_autres(self):
        interdits_moteur = {"claude": [".claude", ".claude.json"], "codex": [".codex"], "gemini-cli": [".gemini"],
                            "qwen": [".qwen"], "opencode": [".config/opencode", ".local/share/opencode"]}
        (self.home / ".claude.json").write_text("{}")
        tous = {r for l in interdits_moteur.values() for r in l}
        for ident in IDENTS:
            with self.subTest(ident):
                self.journal.unlink(missing_ok=True)
                self.oublier_sonde()
                self.lancer_moteur(self.m, ident, NC_TEST_FICHIERS="")
                props = self.props(self.lancements()[1])
                inacc = {p[len('InaccessiblePaths="'):-1] for p in props if p.startswith("InaccessiblePaths=")}
                for rel in interdits_moteur[ident]:
                    self.assertNotIn(str(self.home / rel), inacc, f"{ident} doit lire {rel}")
                for rel in tous - set(interdits_moteur[ident]):
                    self.assertIn(str(self.home / rel), inacc, f"{ident} ne doit pas lire {rel}")
                rw = [p for p in props if p.startswith("ReadWritePaths=")]
                self.assertTrue(any("/nc-ia-" in p for p in rw), "le dossier de travail vide est inscriptible")
                for rel in ({".claude", ".claude.json"} | {".codex", ".gemini", ".qwen", ".local/share/opencode"}) - set(interdits_moteur[ident]):
                    self.assertFalse(any(str(self.home / rel) in p for p in rw), f"{ident} n'écrit pas dans {rel}")

    def test_config_du_moteur_en_lecture_seule(self):
        self.lancer_moteur(self.m, "codex", NC_TEST_FICHIERS="")
        props = self.props(self.lancements()[1])
        self.assertIn(f"ReadOnlyPaths={self.home}/.codex/config.toml", props)
        self.assertIn(f"ReadWritePaths={self.home}/.codex", props)

    def test_sortie_et_dossier_de_travail(self):
        sortie = self.lancer_moteur(self.m, "qwen", NC_TEST_FICHIERS="")
        cwd = [l for l in sortie if l.startswith("CWD")][0]
        self.assertIn(".local/state/nc-ia/travail/nc-ia-", cwd)             # /tmp est privé dans le bac
        self.assertFalse(os.path.exists(cwd.split(" ", 1)[1].strip()), "dossier supprimé après la demande")
        self.assertEqual(list((self.home / ".local/state/nc-ia/conf").glob("*")), [], "dossier de réglages supprimé")

    def test_repli_sans_systemd_run(self):
        (self.fb / "systemd-run").write_text("#!/bin/sh\nexit 1\n")
        for ident in IDENTS:
            with self.subTest(ident):
                self.journal.unlink(missing_ok=True)
                self.oublier_sonde()
                sortie = self.lancer_moteur(self.m, ident, NC_TEST_FICHIERS="")
                self.assertIn("fin\n", sortie)
                self.assertEqual(self.lancements(), [], "le faux systemd-run n'a rien noté (il échoue avant)")
        self.assertFalse(self.m.bac_disponible())

    def test_repli_et_etat(self):
        (self.fb / "systemd-run").write_text("#!/bin/sh\nexit 1\n")
        self.oublier_sonde()
        self.assertFalse(self.m.etat()["bac"])
        self.oublier_sonde()
        (self.fb / "systemd-run").write_text(FAUX_SYSTEMD_RUN)
        self.assertTrue(self.m.etat()["bac"])
        import io, contextlib
        for bac, attendu in ((True, "bac des IA : actif"), (False, "bac des IA : indisponible ici : Codex peut lire tes fichiers")):
            e = self.m.etat()
            e["bac"] = bac
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
        self.env_hote(f"{self.home}/.local/bin:/usr/bin:/bin")
        self.oublier_sonde()

    def fichiers(self):
        return " ".join(str(self.home / r) for r in list(JETONS.values()) + list(CONFIGS.values()) +
                        [".ssh/id_ed25519", ".config/nc/ia.conf"])

    def test_le_bac_tient(self):
        self.assertTrue(self.m.bac_disponible(), "la sonde doit réussir ici")

    def test_chaque_moteur_lit_ses_jetons_seulement(self):
        for ident in IDENTS:
            with self.subTest(ident):
                sortie = self.lancer_moteur(self.m, ident, NC_TEST_FICHIERS=self.fichiers(),
                                            NC_TEST_ECRIRE=f"{self.home}/ecrit-par-le-bac {self.home}/.codex/sessions-test "
                                                           f"{self.home}/.claude/projects-test {self.home}/.local/share/opencode/x "
                                                           f"{self.home}/.gemini/tmp-test {self.home}/.qwen/tmp-test")
                texte = "".join(sortie)
                self.assertIn(f"LU {self.home / JETONS[ident]} JETON-{ident}", texte)
                self.assertIn(f"LU {self.home / CONFIGS[ident]}", texte) if ident != "opencode" else None
                for autre, rel in JETONS.items():
                    if autre != ident and not (ident == "opencode" and autre == "opencode"):
                        self.assertNotIn(f"JETON-{autre}", texte, f"{ident} lit le jeton de {autre}")
                for autre, rel in CONFIGS.items():
                    if autre != ident:
                        self.assertNotIn(f"CONFIG-{autre}", texte)
                self.assertNotIn("FAUSSE-CLE-SSH", texte)
                self.assertNotIn("FAUSSE-CLE-API", texte)
                self.assertIn(f"REFUSE {self.home}/.ssh/id_ed25519", texte)
                self.assertIn(f"NONECRIT {self.home}/ecrit-par-le-bac", texte)
                self.assertFalse((self.home / "ecrit-par-le-bac").exists())

    def test_ecriture_dans_son_dossier_seulement_et_config_figee(self):
        # codex écrit dans ~/.codex (sessions) mais pas dans config.toml ni dans le dossier d'un autre
        (self.home / ".codex/sessions").mkdir()
        (self.home / ".claude/projects").mkdir()
        sortie = "".join(self.lancer_moteur(self.m, "codex", NC_TEST_FICHIERS="",
                         NC_TEST_ECRIRE=f"{self.home}/.codex/sessions/s1 {self.home}/.codex/config.toml "
                                        f"{self.home}/.claude/projects/p1 {self.home}/.gemini/g1"))
        self.assertIn(f"ECRIT {self.home}/.codex/sessions/s1", sortie)
        self.assertIn(f"NONECRIT {self.home}/.codex/config.toml", sortie)
        self.assertIn(f"NONECRIT {self.home}/.claude/projects/p1", sortie)
        self.assertIn(f"NONECRIT {self.home}/.gemini/g1", sortie)
        self.assertEqual((self.home / ".codex/config.toml").read_text(), "CONFIG-codex")
        self.assertTrue((self.home / ".codex/sessions/s1").exists())

    def test_la_sortie_arrive_ligne_par_ligne(self):
        """Pas de tampon jusqu'à la fin : la première ligne arrive bien avant la fin du moteur (qui dort 2 s)."""
        with unittest.mock.patch.dict(os.environ, {"NC_TEST_FICHIERS": "", "NC_TEST_PAUSE": "2"}):
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
        with unittest.mock.patch.dict(os.environ, {"NC_TEST_FICHIERS": "", "NC_TEST_PAUSE": "30"}):
            debut = time.monotonic()
            with self.assertRaises(Exception):
                list(self.m.appel_programme("qwen", "c", "t", None, "question"))
            self.assertLess(time.monotonic() - debut, 15)
        time.sleep(0.5)
        r = subprocess.run(["systemctl", "--user", "list-units", "--no-legend", "nc-ia-*"], capture_output=True, text=True,
                           env=dict(os.environ, XDG_RUNTIME_DIR=os.environ.get("NC_TEST_VRAI_RUNTIME", "")))
        self.assertNotIn("running", r.stdout)

    def test_dns_sans_socket_unix(self):
        """La résolution des noms marche sans AF_UNIX (localhost ; example.com seulement si le réseau est là)."""
        f = self.home / ".local/bin/codex"
        f.write_text("#!/bin/sh\ngetent hosts localhost | head -1\n")
        sortie = "".join(self.lancer_moteur(self.m, "codex"))
        self.assertIn("localhost", sortie)


if __name__ == "__main__":
    unittest.main()

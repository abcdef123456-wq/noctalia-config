"""Audit E4 : nc-verrou-media (pochette en échec, tabulations), nc-touches (nom de pavé piégé), nc-launch (options
d'env, liste vide), nc-brightness (aide complète). Faux programmes seulement, HOME temporaire."""
import os
from pathlib import Path
import subprocess
import tempfile
import time
import unittest

RACINE = Path(__file__).resolve().parents[1]
BIN = RACINE / "home/.local/bin"


def faux(dossier, nom, corps):
    p = Path(dossier) / nom
    p.write_text("#!/bin/sh\n" + corps)
    p.chmod(0o755)
    return p


class VerrouMedia(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="nc-vm-")
        d = Path(self.tmp.name)
        self.home = d / "home"; (self.home / ".local/bin").mkdir(parents=True)
        self.fb = d / "fb"; self.fb.mkdir()
        self.curls = d / "curls"
        faux(self.fb, "busctl", "echo 'as 1 \"org.mpris.MediaPlayer2.test\"'\n")
        faux(self.fb, "curl", f'echo x >> {self.curls}\nexit 22\n')
        faux(self.home / ".local/bin", "nc-apps", "exit 0\n")
        self.titre = "Titre"

    def tearDown(self):
        self.tmp.cleanup()

    def lancer(self):
        faux(self.fb, "playerctl", "printf '%s\\037%s\\037%s\\037%s\\037%s\\037%s\\037%s\\n' Playing "
             f"'{self.titre}' 'Art\tiste' https://exemple.invalid/a.jpg 1000 5 test\n")
        env = dict(os.environ, HOME=str(self.home), XDG_CACHE_HOME=str(self.home / ".cache"),
                   PATH=f"{self.fb}:{os.environ['PATH']}")
        return subprocess.run([str(BIN / "nc-verrou-media")], env=env, capture_output=True, text=True, timeout=10).stdout

    def nb_curl(self):
        return len(self.curls.read_text().split()) if self.curls.exists() else 0

    def test_pochette_en_echec_pas_relancee(self):
        self.lancer()
        for _ in range(50):                       # le téléchargement est en arrière-plan
            if (self.home / ".cache/nc/pochettes").is_dir() and list((self.home / ".cache/nc/pochettes").glob("*.echec")):
                break
            time.sleep(0.1)
        self.lancer(); self.lancer()
        time.sleep(0.3)
        self.assertEqual(self.nb_curl(), 1)

    def test_pochette_telechargee_au_prochain_appel(self):
        faux(self.fb, "curl", 'o=""; while [ $# -gt 0 ]; do [ "$1" = -o ] && o=$2; shift; done; echo img > "$o"\n')
        premier = self.lancer().split("\t")
        self.assertEqual(premier[3], "")           # cet appel-ci : sans pochette
        for _ in range(50):
            suite = self.lancer().split("\t")
            if suite[3]:
                break
            time.sleep(0.1)
        self.assertTrue(suite[3] and Path(suite[3]).is_file())

    def test_tabulation_dans_le_titre(self):
        self.titre = "A\tB"
        champs = self.lancer().rstrip("\n").split("\t")
        self.assertEqual(len(champs), 9)
        self.assertEqual((champs[1], champs[2]), ("A B", "Art iste"))


class Touches(unittest.TestCase):
    def test_nom_de_pave_piege(self):
        with tempfile.TemporaryDirectory(prefix="nc-touches-") as d:
            d = Path(d); fb = d / "fb"; fb.mkdir(); journal = d / "j"
            noms = ["synps/2-synaptics-touchpad", "it's a touchpad", "x') os.execute('touch /tmp/pwn') -- touchpad",
                    "a\\' touchpad"]
            import json
            faux(fb, "hyprctl", f'''case "$*" in *devices*) cat <<'FIN'
{json.dumps({"mice": [{"name": n} for n in noms]})}
FIN
;; *) printf '%s\\n' "$*" >> {journal} ;; esac\n''')
            faux(fb, "notify-send", "exit 0\n")
            run = d / "run"; run.mkdir()
            env = dict(os.environ, HOME=str(d), XDG_RUNTIME_DIR=str(run), PATH=f"{fb}:{os.environ['PATH']}")
            subprocess.run([str(BIN / "nc-touches"), "pave", "off"], env=env, capture_output=True, timeout=10)
            appels = journal.read_text().splitlines()
            self.assertEqual(len(appels), 1)
            self.assertIn("'synps/2-synaptics-touchpad'", appels[0])      # le pavé PS/2 courant, avec « / »
            self.assertFalse(any("os.execute" in a or "it's" in a for a in appels))


class Launch(unittest.TestCase):
    def lancer(self, *cmd, reglage=None):
        with tempfile.TemporaryDirectory(prefix="nc-launch-") as d:
            h = Path(d); b = h / ".local/bin"; b.mkdir(parents=True); run = h / "run"; run.mkdir()
            (run / "nc-gpu-default").write_text("nvidia\n")
            faux(b, "nvidia-run", 'echo "RTX $*"\n')
            kitty = faux(h, "kitty", 'echo "integree $*"\n')
            if reglage is not None:
                (h / ".config/nc").mkdir(parents=True)
                (h / ".config/nc/reglages.conf").write_text(f'GPU_JAMAIS_RTX="{reglage}"\n')
            cmd = [str(kitty) if c == "KITTY" else c for c in cmd]
            env = dict(os.environ, HOME=d, XDG_RUNTIME_DIR=str(run))
            return subprocess.run([str(BIN / "nc-launch"), *cmd], env=env, capture_output=True, text=True, timeout=10).stdout.strip()

    def test_options_de_env(self):
        for opts in (["-u", "VAR"], ["-i"], ["-"], ["--"], ["--unset=VAR"], ["-C", "/tmp"],
                     ["--chdir=/tmp"], ["-uVAR"]):
            with self.subTest(opts=opts):
                self.assertEqual(self.lancer("env", *opts, "KITTY", "-1"), "integree -1")

    def test_env_sans_exclu_va_sur_la_rtx(self):
        self.assertTrue(self.lancer("env", "-u", "VAR", "echo", "x").startswith("RTX env -u VAR echo x"))

    def test_liste_vide_voulue(self):
        self.assertTrue(self.lancer("KITTY", reglage="").startswith("RTX "))       # ligne présente, vide : aucune exception
        self.assertEqual(self.lancer("KITTY"), "integree")                           # pas de ligne : liste par défaut


class Brightness(unittest.TestCase):
    def test_aide_complete(self):
        env = dict(os.environ, NC_LANGUE="fr")
        sortie = subprocess.run([str(BIN / "nc-brightness"), "--help"], env=env, capture_output=True, text=True, timeout=10).stdout
        self.assertIn("nc-brightness set N", sortie)
        self.assertNotIn("set -u", sortie)


if __name__ == "__main__":
    unittest.main()

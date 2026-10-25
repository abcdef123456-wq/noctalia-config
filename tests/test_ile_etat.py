"""nc-ile-etat : la partie media (titre sans artiste, séparateur de playerctl) et la fréquence des écrans (arrondie)."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "home/.local/bin/nc-ile-etat"


class IleEtat(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="nc-ile-etat-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.bin = self.tmp / "bin"
        self.bin.mkdir()
        (self.tmp / "home/.cache").mkdir(parents=True)

    def faux(self, nom, corps):
        f = self.bin / nom
        f.write_text("#!/bin/sh\n" + corps)
        f.chmod(0o755)

    def lancer(self, *args):
        env = dict(os.environ, HOME=str(self.tmp / "home"), PATH=f"{self.bin}:{os.environ['PATH']}")
        r = subprocess.run(["bash", str(SCRIPT), *args], env=env, capture_output=True, text=True, timeout=30)
        return r.stdout

    @staticmethod
    def cles(sortie):
        return dict(l.split("=", 1) for l in sortie.splitlines() if "=" in l)

    def test_titre_sans_artiste_ni_pochette(self):
        # playerctl sépare les champs par \x1f (le format demandé) ; l'artiste et la pochette sont vides
        self.faux("playerctl", 'case "$1" in metadata) printf "Playing\\037Mon titre\\037\\037\\0371000\\037firefox\\n" ;; esac\n')
        c = self.cles(self.lancer("media"))
        self.assertEqual(c["media"], "1")
        self.assertEqual(c["media_titre"], "Mon titre")
        self.assertEqual(c["media_artiste"], "")
        self.assertEqual(c["media_pochette"], "")
        self.assertEqual(c["media_duree"], "1000")
        self.assertEqual(c["media_joueur"], "firefox")

    def test_pochette_locale_et_artiste(self):
        img = self.tmp / "a b.png"
        img.write_bytes(b"x")
        self.faux("playerctl", f'case "$1" in metadata) printf "Paused\\037T\\037Moi\\037file://{self.tmp}/a%%20b.png\\037500\\037mpv\\n" ;; esac\n')
        c = self.cles(self.lancer("media"))
        self.assertEqual((c["media_artiste"], c["media_duree"], c["media_joueur"]), ("Moi", "500", "mpv"))
        self.assertEqual(c["media_pochette"], str(img))

    def test_le_format_demande_utilise_le_separateur_non_blanc(self):
        self.faux("playerctl", 'case "$1" in metadata) printf "%s" "$*" > "$HOME/args" ;; esac\n')
        self.lancer("media")
        args = (self.tmp / "home/args").read_text()
        self.assertIn("\x1f", args)
        self.assertNotIn("\t", args)

    @unittest.skipUnless(shutil.which("jq"), "jq manque")
    def test_frequence_arrondie(self):
        self.faux("hyprctl", """case "$*" in *monitors*)
  echo '[{"name":"eDP-1","width":2560,"height":1600,"refreshRate":164.99899,"scale":1.5},{"name":"HDMI-A-1","width":3840,"height":2160,"refreshRate":59.94,"scale":1}]' ;;
esac
""")
        lignes = [l for l in self.lancer("systeme").splitlines() if l.startswith("ecran=")]
        self.assertIn("ecran=eDP-1\t2560x1600\t165 Hz\t1.5", lignes)
        self.assertIn("ecran=HDMI-A-1\t3840x2160\t60 Hz\t1", lignes)


if __name__ == "__main__":
    unittest.main()

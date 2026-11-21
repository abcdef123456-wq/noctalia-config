"""nc-pipette : couleur d'un point de l'écran, copiée en #rrggbb. Faux grim, slurp, wl-copy, notify-send dans un HOME
temporaire : jamais la vraie session. Le PATH ne contient que les faux et les outils de base."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
BIN = REPO / "home/.local/bin"
OUTILS = ("bash", "sh", "sed", "tr", "od", "cat", "grep", "head", "printf", "env", "dirname", "basename")
PPM = r"printf 'P6\n1 1\n255\n\252\273\314'"       # 0xaa 0xbb 0xcc


class Pipette(unittest.TestCase):
    def setUp(self):
        d = tempfile.TemporaryDirectory(prefix="nc-pipette-")
        self.addCleanup(d.cleanup)
        self.home = Path(d.name)
        self.faux = self.home / "faux"
        self.faux.mkdir()
        for nom in OUTILS:
            chemin = shutil.which(nom)
            if chemin:
                (self.faux / nom).symlink_to(chemin)
        self.journal = self.home / "journal"
        self.copie = self.home / "copie"
        self.faux_prog("slurp", 'echo "10,20 1x1"')
        self.faux_prog("grim", 'echo "grim $*" >> "$JOURNAL"; ' + PPM)
        self.faux_prog("wl-copy", 'cat > "$COPIE"')
        self.faux_prog("notify-send", 'echo "notif $*" >> "$JOURNAL"')

    def faux_prog(self, nom, corps):
        f = self.faux / nom
        if f.is_symlink() or f.exists():
            f.unlink()
        f.write_text("#!/bin/sh\n" + corps + "\n")
        f.chmod(0o755)

    def lancer(self):
        env = dict(HOME=str(self.home), PATH=str(self.faux), NC_LANGUE="fr", JOURNAL=str(self.journal),
                   COPIE=str(self.copie), XDG_RUNTIME_DIR=str(self.home / "run"),
                   XDG_CONFIG_HOME=str(self.home / ".config"), XDG_STATE_HOME=str(self.home / ".state"))
        (self.home / ".local").mkdir(exist_ok=True)
        if not (self.home / ".local/bin").exists():
            (self.home / ".local/bin").symlink_to(BIN)
        return subprocess.run(["bash", str(BIN / "nc-pipette")], env=env, capture_output=True, text=True, timeout=20)

    def notifs(self):
        return self.journal.read_text() if self.journal.exists() else ""

    def test_couleur_copiee_en_minuscules(self):
        r = self.lancer()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.copie.read_text(), "#aabbcc")
        self.assertIn("grim -g 10,20 1x1 -t ppm -", self.notifs())
        self.assertIn("#aabbcc", self.notifs())

    def test_annulation_de_slurp(self):
        self.faux_prog("slurp", "exit 1")
        r = self.lancer()
        self.assertEqual(r.returncode, 0)
        self.assertFalse(self.copie.exists())
        self.assertEqual(self.notifs(), "")

    def test_outil_manquant(self):
        for outil, paquet in (("grim", "grim"), ("slurp", "slurp"), ("wl-copy", "wl-clipboard")):
            with self.subTest(outil=outil):
                sauve = (self.faux / outil).read_text()
                (self.faux / outil).unlink()
                r = self.lancer()
                self.assertNotEqual(r.returncode, 0)
                self.assertIn(paquet, self.notifs())
                self.assertFalse(self.copie.exists())
                self.faux_prog(outil, sauve.split("\n", 1)[1])
                self.journal.unlink(missing_ok=True)

    def test_sortie_de_grim_invalide(self):
        for corps in ("echo pas-un-ppm", "printf 'P6\\n2 2\\n255\\n123456789012'", "printf 'P6\\n1 1\\n255\\n\\1'", "exit 1"):
            with self.subTest(corps=corps):
                self.faux_prog("grim", corps)
                r = self.lancer()
                self.assertNotEqual(r.returncode, 0)
                self.assertFalse(self.copie.exists())
                self.assertIn("illisible", self.notifs())
                self.journal.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()

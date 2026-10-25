"""Île : aucun titre de fenêtre en dur (tout passe par Reglages.t), et la couleur rose lit sa propre clé."""
import re
import unittest
from pathlib import Path

ILE = Path(__file__).resolve().parent.parent / "home/.config/quickshell/nc-ile"


class Titres(unittest.TestCase):
    def test_titres_traduits(self):
        for f in sorted(ILE.glob("*.qml")):
            for n, l in enumerate(f.read_text().splitlines(), 1):
                with self.subTest(fichier=f.name, ligne=n):
                    self.assertIsNone(re.match(r'\s*title:\s*"', l), l)

    def test_rose_lit_sa_cle(self):
        self.assertIn('rose: v("rose",', (ILE / "Couleurs.qml").read_text())

    def test_ecrans_vides_gardes(self):
        shell = (ILE / "shell.qml").read_text()
        self.assertNotIn("Quickshell.screens[0].name, ", shell)
        self.assertEqual(len(re.findall(r"screens\[0\]\.name", shell)), shell.count("Quickshell.screens.length ? Quickshell.screens[0].name"))


if __name__ == "__main__":
    unittest.main()

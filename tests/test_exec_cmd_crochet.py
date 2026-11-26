"""Hyprland lit un « [ … ] » en tête d'une commande lancée (hl.exec_cmd) comme des règles de lancement : un test shell
« [ -e f ] && … » écrit en premier casse donc toute la commande, sans erreur visible. Aucune commande ne doit commencer
par « [ »."""
import re
import unittest
from pathlib import Path

HYPR = Path(__file__).resolve().parent.parent / "home/.config/hypr"


class CommandeSansCrochet(unittest.TestCase):
    def test_aucune_commande_ne_commence_par_un_crochet(self):
        fautes = []
        for f in sorted(HYPR.rglob("*.lua")):
            for n, ligne in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
                if re.search(r"""exec_cmd\(\s*["']\s*\[""", ligne):
                    fautes.append(f"{f.relative_to(HYPR)}:{n}")
        self.assertEqual(fautes, [], "commande qui commence par « [ » (mettre « : ; » devant)")


if __name__ == "__main__":
    unittest.main()

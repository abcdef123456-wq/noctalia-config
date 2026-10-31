"""Le calque de l'île (nc-ile) n'a pas d'animation de Hyprland : à chaque changement de taille de la surface (Spotlight,
ouverture, fermeture), Hyprland animait sa place et sa taille (layersIn) et l'île glissait de côté, étirée, pendant
environ 270 ms. La règle no_anim est posée sans condition, pour le nom exact du calque de Ile.qml."""
import json
import re
import shutil
import subprocess
import unittest
from pathlib import Path

DEPOT = Path(__file__).resolve().parents[1]
REGLES = DEPOT / "home/.config/hypr/nc/regles.lua"
ILE = DEPOT / "home/.config/quickshell/nc-ile/Ile.qml"


class CalqueSansAnim(unittest.TestCase):
    def regles(self, valeur):
        harnais = r'''
hl = setmetatable({ layer_rule = function(r) if r.no_anim then print(r.name .. "\t" .. r.match.namespace) end end },
                  { __index = function() return function() end end })
nc = setmetatable({ reglage = function(c, d) return VALEUR or d end },
                  { __index = function() return function() return "" end end })
dofile(FICHIER)
'''.replace("FICHIER", json.dumps(str(REGLES))).replace("VALEUR", json.dumps(valeur) if valeur is not None else "nil")
        r = subprocess.run(["lua", "-"], input=harnais, text=True, capture_output=True, timeout=10, env=dict(PATH="/usr/bin:/bin"))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return dict(l.split("\t", 1) for l in r.stdout.splitlines())

    def namespace_ile(self):
        m = re.search(r'WlrLayershell\.namespace:\s*"([^"]+)"', ILE.read_text())
        self.assertIsNotNone(m, "Ile.qml sans namespace de calque")
        return m.group(1)

    @unittest.skipUnless(shutil.which("lua"), "lua absent")
    def test_regle_sans_condition_pour_le_calque_de_l_ile(self):
        ns = self.namespace_ile()
        # Quel que soit un réglage (aucun, oui, non) : la règle est là, et son motif vise exactement ce calque
        for valeur in (None, "oui", "non"):
            with self.subTest(reglage=valeur):
                regles = self.regles(valeur)
                self.assertIn("nc-ile-sans-anim", regles)
                motif = regles["nc-ile-sans-anim"]
                self.assertRegex(ns, motif)
                for autre in ("nc-ile-test", "x-nc-ile", "nc-fiche", "nc-code", "noctalia-bar-eDP-1"):
                    self.assertNotRegex(autre, motif)

    def test_l_ile_reste_centree_dans_sa_surface(self):
        # La surface est ancrée en haut seulement (Hyprland la centre) et l'île au centre de la surface : avec un calque
        # sans animation, son centre reste celui de l'écran à chaque changement de largeur de la surface
        texte = ILE.read_text()
        self.assertRegex(texte, r"(?m)^\s*anchors\.top:\s*true\s*$")
        self.assertNotRegex(texte, r"(?m)^\s*anchors\.(left|right|bottom):\s*true")
        bloc = texte[texte.index("id: ile\n"):]
        self.assertRegex(bloc[:300], r"anchors\.horizontalCenter:\s*parent\.horizontalCenter")


if __name__ == "__main__":
    unittest.main()

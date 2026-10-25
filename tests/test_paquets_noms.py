"""install.sh : des noms de paquets vérifiés dans des conteneurs des 4 distributions (Compat-2).
- openSUSE Tumbleweed : qt6-svg-imports n'existe pas ; le module SVG de Qt 6 (imageformats/libqsvg.so) est dans libQt6Svg6.
- Debian 13 : gitui n'existe ni dans trixie ni dans les backports ; l'extra LazyVim util.gitui le fait installer par Mason."""
import json
from pathlib import Path
import re
import unittest

RACINE = Path(__file__).resolve().parents[1]
INSTALL = (RACINE / "install.sh").read_text(encoding="utf-8")


def lignes(famille, motif):
    return [l for l in INSTALL.splitlines() if re.match(rf"\s*{famille}\)\s+pkg_try\b", l) and motif in l]


class NomsDePaquets(unittest.TestCase):
    def test_svg_qt6_opensuse(self):
        self.assertFalse(lignes("suse", "qt6-svg-imports"), "nom absent de Tumbleweed")
        self.assertTrue(lignes("suse", "libQt6Svg6"), "le module SVG de Qt 6 sur openSUSE")

    def test_gitui_pas_demande_a_debian(self):
        neovim = lignes("debian", "neovim")
        self.assertTrue(neovim)
        for l in neovim:
            self.assertNotRegex(l, r"\bgitui\b", "gitui n'est pas un paquet de Debian 13")

    def test_gitui_installe_par_mason(self):
        # Sans paquet Debian, c'est l'extra LazyVim qui fournit gitui (Mason) : il doit rester activé
        extras = json.loads((RACINE / "home/.config/nvim/lazyvim.json").read_text(encoding="utf-8"))["extras"]
        self.assertIn("lazyvim.plugins.extras.util.gitui", extras)


if __name__ == "__main__":
    unittest.main()

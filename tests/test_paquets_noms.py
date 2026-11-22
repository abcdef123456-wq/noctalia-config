"""install.sh : des noms de paquets vérifiés dans des conteneurs des 4 distributions (Compat-2).
- openSUSE Tumbleweed : qt6-svg-imports n'existe pas ; le module SVG de Qt 6 (imageformats/libqsvg.so) est dans libQt6Svg6.
- Debian 13 : gitui n'existe ni dans trixie ni dans les backports ; l'extra LazyVim util.gitui le fait installer par Mason."""
import json
from pathlib import Path
import re
import subprocess
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


class PolicesDesThemes(unittest.TestCase):
    """Inter (Apple) et JetBrains Mono (Rétro) : noms vérifiés dans le dépôt par défaut de chaque distribution
    (sources dans install.sh) ; autre famille : rien (l'île prend sa police de repli) ; facultatives sur Arch."""
    def test_paquet_par_famille(self):
        debut = INSTALL.index("pname() {")
        fonction = INSTALL[debut:INSTALL.index("\n}\n", debut) + 3]
        attendu = {"inter": {"arch": "inter-font", "debian": "fonts-inter", "fedora": "rsms-inter-fonts", "suse": "inter-fonts",
                             "other": "", "nixos": ""},
                   "jetbrains-mono": {"arch": "ttf-jetbrains-mono", "debian": "fonts-jetbrains-mono", "fedora": "jetbrains-mono-fonts",
                                      "suse": "jetbrains-mono-fonts", "other": "", "nixos": ""}}
        for nom, familles in attendu.items():
            for famille, paquet in familles.items():
                r = subprocess.run(["bash", "-c", fonction + f"FAMILY={famille}; pname {nom}"], capture_output=True, text=True)
                self.assertEqual(r.stdout.strip(), paquet, (nom, famille))

    def test_dans_les_listes_et_facultatives_sur_arch(self):
        for liste in ("GENERIC=(", "FACULTATIFS=("):
            debut = INSTALL.index(liste)
            self.assertIn("noto-fonts inter jetbrains-mono", INSTALL[debut:INSTALL.index(")", debut)], liste)


if __name__ == "__main__":
    unittest.main()

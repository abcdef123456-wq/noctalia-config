"""Raccourcis ajoutés à Neovim (lua/config/keymaps.lua) : Ctrl + C copie la sélection dans le presse-papiers du système en
mode visuel, et reste une interruption en mode normal."""
from pathlib import Path
import re
import unittest

REPO = Path(__file__).resolve().parents[1]
KEYMAPS = REPO / "home/.config/nvim/lua/config/keymaps.lua"


class Keymaps(unittest.TestCase):
    def test_ctrl_c_copie_en_visuel(self):
        src = KEYMAPS.read_text()
        self.assertIn('''map("x", "<C-c>", '"+y', { desc = "Copier (presse-papiers)" })''', src)
        # en mode normal, Ctrl + C n'est pas remplacé (interruption)
        for m in re.finditer(r'map\((\{[^}]*\}|"[a-z]+"),\s*"<C-c>"', src):
            self.assertNotRegex(m.group(1), r'"n"', "Ctrl + C ne doit pas être remplacé en mode normal")

    def test_documente(self):
        self.assertRegex((REPO / "RACCOURCIS.md").read_text(), r"`Ctrl` \+ `C` en mode visuel \(Neovim\)")


if __name__ == "__main__":
    unittest.main()

"""Terminal et Neovim : chsh installé si absent (Fedora), zsh sans nc-greeting, oh-my-zsh en rappel, verrou Neovim propre.

Tests statiques : rien ne touche au vrai HOME (le zsh d'essai tourne dans un HOME temporaire).
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
NVIM = REPO / "home/.config/nvim"
GREETING = REPO / "home/.config/nc/greeting.zsh"


class ShellNvim(unittest.TestCase):
    def test_install_cherche_chsh(self):
        s = (REPO / "install.sh").read_text()
        self.assertIn("have chsh || case", s)
        self.assertIn("pkg_try util-linux-user", s)

    def test_omz_en_rappel_avant_le_source(self):
        z = (REPO / "home/.zshrc").read_text()
        self.assertLess(z.index("zstyle ':omz:update' mode reminder"), z.index('source "$ZSH/oh-my-zsh.sh"'))

    @unittest.skipUnless(shutil.which("zsh"), "zsh absent")
    def test_ctrl_l_intact_sans_nc_greeting(self):
        with tempfile.TemporaryDirectory() as h:
            env = {"PATH": "/usr/bin:/bin", "HOME": h, "ZDOTDIR": h, "TMPDIR": h}
            r = subprocess.run(["zsh", "-fic", f"source {GREETING}; zle -lL"], env=env, capture_output=True, text=True)
            self.assertNotIn("clear-screen", r.stdout)
            bin_ = Path(h, ".local/bin"); bin_.mkdir(parents=True)
            (bin_ / "nc-greeting").write_text("#!/bin/sh\n")
            (bin_ / "nc-greeting").chmod(0o755)
            r = subprocess.run(["zsh", "-fic", f"source {GREETING}; zle -lL"], env=env, capture_output=True, text=True)
            self.assertIn("zle -N clear-screen _nc_clear_screen", r.stdout)

    def test_verrou_sans_plugin_orphelin(self):
        verrou = json.loads((NVIM / "lazy-lock.json").read_text())
        lua = "".join(p.read_text() for p in (NVIM / "lua").rglob("*.lua")) + (NVIM / "lazyvim.json").read_text()
        self.assertNotIn("gitsigns.nvim", verrou)
        self.assertNotIn("gitsigns", lua)

    def test_motifs_et_texte_nvim(self):
        self.assertNotIn("/home/%.config", (NVIM / "lua/plugins/bureau.lua").read_text())
        self.assertNotIn("Neovim 0.10 au moins", (NVIM / "lua/config/ia.lua").read_text())


if __name__ == "__main__":
    unittest.main()

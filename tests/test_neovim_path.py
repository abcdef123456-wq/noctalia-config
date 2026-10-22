"""Neovim trop ancien (Debian 13 : 0.10.4, LazyVim demande la 0.11.2) : nc-diag l'annonce, et ~/.local/bin (où
install.sh met la version officielle) passe devant /usr/bin, une seule fois, dans zsh, bash et toute la session uwsm.

Rien ne touche au vrai HOME : faux nvim dans un dossier temporaire, HOME temporaire pour les shells.
"""
import importlib.machinery
import importlib.util
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock

REPO = Path(__file__).resolve().parents[1]
DIAG = REPO / "home/.local/bin/nc-diag"
ZSHRC = REPO / "home/.zshrc"
UWSM_ENV = REPO / "home/.config/uwsm/env"
INSTALL = (REPO / "install.sh").read_text()


def charger_diag():
    with mock.patch.dict(os.environ, NC_LANGUE="fr"):
        chargeur = importlib.machinery.SourceFileLoader("nc_diag_nvim", str(DIAG))
        spec = importlib.util.spec_from_loader("nc_diag_nvim", chargeur)
        m = importlib.util.module_from_spec(spec)
        chargeur.exec_module(m)
    return m


class DiagNeovim(unittest.TestCase):
    def setUp(self):
        d = tempfile.TemporaryDirectory(prefix="nc-nvim-")
        self.addCleanup(d.cleanup)
        self.dossier = Path(d.name)
        self.m = charger_diag()

    def bilan(self, version=None):
        if version:
            f = self.dossier / "nvim"
            f.write_text(f'#!/bin/sh\necho "NVIM v{version}"\necho "Build type: Release"\n')
            f.chmod(0o755)
        b = self.m.Bilan(couleurs=False)
        with mock.patch.dict(os.environ, PATH=str(self.dossier)):
            self.m.neovim(b)
        return b

    def test_trop_ancien(self):
        b = self.bilan("0.10.4")
        self.assertEqual(b.attention, 1)
        texte = b.texte()
        self.assertIn("Neovim trop ancien pour la config (0.10.4 < 0.11.2)", texte)
        self.assertIn("relance install.sh, qui propose la version officielle", texte)

    def test_assez_recent(self):
        for v in ("0.11.2", "0.11.4", "0.12.0"):
            self.assertEqual(self.bilan(v).lignes, [], v)

    def test_absent(self):
        self.assertEqual(self.bilan().lignes, [])


class LocalBinEnTete(unittest.TestCase):
    """~/.local/bin devant /usr/bin, une seule fois, même s'il était déjà dans le PATH plus loin (en double)."""

    def setUp(self):
        d = tempfile.TemporaryDirectory(prefix="nc-path-")
        self.addCleanup(d.cleanup)
        self.home = Path(d.name).resolve()
        self.lb = str(self.home / ".local/bin")
        self.depart = f"/usr/bin:{self.lb}:/bin:{self.lb}"
        self.attendu = f"{self.lb}:/usr/bin:/bin"

    def lancer(self, shell, script):
        if not shutil.which(shell):
            self.skipTest(f"{shell} absent")
        env = {"HOME": str(self.home), "PATH": self.depart, "ZDOTDIR": str(self.home)}
        r = subprocess.run([shutil.which(shell), "-c", script], env=env, capture_output=True, text=True, timeout=20)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout.strip().splitlines()[-1]

    def test_zshrc(self):
        self.assertEqual(self.lancer("zsh", f'source "{ZSHRC}"; print -r -- "$PATH"'), self.attendu)
        # Relu dans un zsh imbriqué : toujours une seule entrée
        self.assertEqual(self.lancer("zsh", f'source "{ZSHRC}"; source "{ZSHRC}"; print -r -- "$PATH"'), self.attendu)

    def test_uwsm_env(self):
        for sh in ("sh", "bash", "dash"):
            if shutil.which(sh):
                self.assertEqual(self.lancer(sh, f'. "{UWSM_ENV}"; echo "$PATH"'), self.attendu, sh)

    def test_bashrc_d_install(self):
        m = re.search(r"<<'BASHRC_EOF'\n(.*?)\nBASHRC_EOF", INSTALL, re.S)
        self.assertIsNotNone(m, "bloc .bashrc introuvable dans install.sh")
        bloc = m.group(1)
        self.assertIn("noctalia-config : ~/.local/bin en tête du PATH", bloc)
        f = self.home / "bashrc"
        f.write_text(bloc + "\n")
        self.assertEqual(self.lancer("bash", f'. "{f}"; . "{f}"; echo "$PATH"'), self.attendu)
        # L'ancienne ligne (ajoutée seulement si absent) est remplacée chez ceux qui l'ont
        self.assertIn('grep -vxF -e "$nc_bash_ancien"', INSTALL)

    def test_profils_livres(self):
        """Aucun profil livré ne remet ~/.local/bin derrière le PATH existant."""
        for p in (ZSHRC, UWSM_ENV, REPO / "home/.config/uwsm/env-hyprland"):
            for ligne in p.read_text().splitlines():
                if ligne.lstrip().startswith("#"):
                    continue
                self.assertNotRegex(ligne, r'PATH="\$PATH:[^"]*\.local/bin', f"{p.name} : {ligne}")


if __name__ == "__main__":
    unittest.main()

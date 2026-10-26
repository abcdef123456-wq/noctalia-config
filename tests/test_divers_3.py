"""Lot Divers-3 : nc-logiciels (droits, terminal, messages), nc-video, nc-navigateurs, nc-alertes, nc-anim.
De faux outils dans un PATH réduit (ils notent leurs arguments, ne lancent jamais le vrai) ; HOME et XDG_* temporaires."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
BIN = REPO / "home/.local/bin"


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        self.bin = self.home / "bin"
        self.bin.mkdir()
        for outil in ("sh", "env", "python3", "cat", "printf", "tr", "mkdir", "dirname", "basename", "true", "false"):
            if shutil.which(outil):
                (self.bin / outil).symlink_to(shutil.which(outil))
        for d in (".config/nc", "cache", "state", "data", "run", "tmp"):
            (self.home / d).mkdir(parents=True, exist_ok=True)
        (self.home / "run").chmod(0o700)
        self.env = dict(HOME=str(self.home), PATH=str(self.bin), NC_LANGUE="fr", XDG_CACHE_HOME=str(self.home / "cache"),
                        XDG_CONFIG_HOME=str(self.home / ".config"), XDG_STATE_HOME=str(self.home / "state"),
                        XDG_DATA_HOME=str(self.home / "data"), XDG_RUNTIME_DIR=str(self.home / "run"), TMPDIR=str(self.home / "tmp"))

    def faux(self, nom, corps="", code=0, sortie=""):
        """Un faux outil : note « nom arguments » dans $HOME/appels."""
        f = self.bin / nom
        f.write_text(f'#!/bin/sh\necho "{nom} $*" >> "$HOME/appels"\n{corps}\n' + (f"printf '%s' '{sortie}'\n" if sortie else "") + f"exit {code}\n")
        f.chmod(0o755)

    def appels(self):
        f = self.home / "appels"
        return f.read_text() if f.exists() else ""

    def lancer(self, script, *args, env=None):
        return subprocess.run([str(BIN / script), *args], env=dict(self.env, **(env or {})), capture_output=True, text=True,
                              timeout=30, stdin=subprocess.DEVNULL)


class LogicielsDroits(Base):
    def test_sudo_present_arch_mot_de_passe_le_tien(self):
        self.faux("pacman")
        self.faux("sudo")
        r = self.lancer("nc-logiciels", "terminal", "depot", "vlc")
        self.assertIn("sudo pacman -S --needed -- vlc", self.appels() + r.stdout)
        self.assertIn("le tien", r.stdout)

    def test_sudo_absent_debian_utilise_su(self):
        self.faux("apt-get")
        self.faux("su")
        r = self.lancer("nc-logiciels", "terminal", "depot", "vlc")
        self.assertIn("su -c apt install -- vlc", self.appels())
        self.assertIn("root", r.stdout)

    def test_ni_sudo_ni_su_pkexec(self):
        self.faux("apt-get")
        self.faux("pkexec")
        self.lancer("nc-logiciels", "terminal", "depot", "vlc")
        self.assertIn("pkexec apt install -- vlc", self.appels())

    def test_aucun_moyen_message_clair(self):
        self.faux("apt-get")
        r = self.lancer("nc-logiciels", "terminal", "depot", "vlc")
        self.assertEqual(r.returncode, 1)
        self.assertIn("ni sudo, ni su, ni pkexec", r.stderr)

    def test_opensuse_sudo_dit_root(self):
        self.faux("zypper")
        self.faux("sudo")
        r = self.lancer("nc-logiciels", "terminal", "depot", "vlc")
        self.assertIn("sudo zypper install -- vlc", self.appels())
        self.assertIn("root", r.stdout)
        self.assertNotIn("le tien", r.stdout)

    def test_en_tete_dit_les_deux_cas(self):
        t = (BIN / "nc-logiciels").read_text()
        self.assertIn("celui de root sur openSUSE", t)


class LogicielsTerminal(Base):
    def test_wezterm_start_et_pas_dash_e(self):
        self.faux("pacman")
        self.faux("sudo")
        self.faux("wezterm", code=0, corps="sleep 0 2>/dev/null")
        r = self.lancer("nc-logiciels", "installer", "depot", "vlc")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("wezterm start -- ", self.appels())
        self.assertNotIn("wezterm -e", self.appels())

    def test_ptyxis_connu(self):
        self.faux("pacman")
        self.faux("ptyxis")
        self.lancer("nc-logiciels", "installer", "depot", "vlc")
        self.faux("sudo")
        self.lancer("nc-logiciels", "installer", "depot", "vlc")
        self.assertIn("ptyxis -- ", self.appels())

    def test_echec_du_terminal_notifie_et_sort_non_nul(self):
        self.faux("pacman")
        self.faux("sudo")
        self.faux("kitty", code=3)
        self.faux("notify-send")
        r = self.lancer("nc-logiciels", "installer", "depot", "vlc")
        self.assertEqual(r.returncode, 1)
        self.assertIn("notify-send", self.appels())
        self.assertIn("ne s'est pas ouvert", r.stderr)

    def test_pas_de_liste_de_terminaux_dupliquee(self):
        t = (BIN / "nc-logiciels").read_text()
        self.assertNotIn('"xterm")', t)
        self.assertIn("commande_terminal", t)


class LogicielsMessages(Base):
    def test_dnf_sans_cache_dit_quoi_faire(self):
        self.faux("dnf", code=1)
        r = self.lancer("nc-logiciels", "chercher", "vlc", "--rapide")
        self.assertEqual(r.returncode, 0)
        self.assertEqual(json.loads(r.stdout), [])
        self.assertIn("makecache", r.stderr)

    def test_pacman_base_vide_dit_quoi_faire(self):
        self.faux("pacman")
        (self.home / "sync").mkdir()
        r = self.lancer("nc-logiciels", "chercher", "vlc", "--rapide", env={"NC_PACMAN_SYNC": str(self.home / "sync")})
        self.assertEqual(json.loads(r.stdout), [])
        self.assertIn("pacman -Sy", r.stderr)

    def test_dnf_qui_marche_reste_muet(self):
        self.faux("dnf", sortie="vlc.x86_64 : lecteur\n")
        self.faux("rpm")
        r = self.lancer("nc-logiciels", "chercher", "vlc", "--rapide")
        self.assertNotIn("makecache", r.stderr)


if __name__ == "__main__":
    unittest.main()

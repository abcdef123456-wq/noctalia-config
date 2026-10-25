"""nc-brightness : quel rétroéclairage ? firmware > platform > raw ; celui du pilote NVIDIA (nvidia_0) seulement en
dernier recours, si l'écran interne branché est sur cette même carte (mode carte dédiée). Faux /sys par NC_SYSFS."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

BIN = Path(__file__).resolve().parent.parent / "home/.local/bin"


class Choix(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="nc-lum-"); self.addCleanup(self.tmp.cleanup)
        self.sys = Path(self.tmp.name) / "sys"
        for d in ("class/backlight", "class/drm", "devices"):
            (self.sys / d).mkdir(parents=True)

    def carte(self, nom, pci, edp=None):
        """Carte DRM nom (card0…) sur le périphérique PCI pci ; edp : état de son connecteur eDP (ou aucun)."""
        dev = self.sys / "devices" / pci
        dev.mkdir(exist_ok=True)
        c = self.sys / "class/drm" / nom
        c.mkdir()
        (c / "device").symlink_to(dev)
        if edp:
            e = self.sys / "class/drm" / f"{nom}-eDP-1"
            e.mkdir()
            (e / "status").write_text(edp + "\n")

    def retro(self, nom, type_, pci=None):
        d = self.sys / "class/backlight" / nom
        d.mkdir()
        (d / "type").write_text(type_ + "\n")
        if pci:
            (d / "device").symlink_to(self.sys / "devices" / pci)

    def choisi(self):
        env = dict(os.environ, NC_SYSFS=str(self.sys))
        return subprocess.run([str(BIN / "nc-brightness"), "appareil"], env=env, capture_output=True, text=True,
                              timeout=10).stdout.strip()

    def test_hybride_intel_et_nvidia_ecran_sur_intel(self):
        self.carte("card0", "0000:00:02.0", edp="connected")
        self.carte("card1", "0000:01:00.0")
        self.retro("intel_backlight", "raw", "0000:00:02.0")
        self.retro("nvidia_0", "raw", "0000:01:00.0")
        self.assertEqual(self.choisi(), "intel_backlight")

    def test_dediee_nvidia_seul_ecran_sur_la_meme_carte(self):
        self.carte("card0", "0000:00:02.0", edp="disconnected")
        self.carte("card1", "0000:01:00.0", edp="connected")
        self.retro("nvidia_0", "raw", "0000:01:00.0")
        self.assertEqual(self.choisi(), "nvidia_0")

    def test_nvidia_seul_ecran_sur_une_autre_carte(self):
        self.carte("card0", "0000:00:02.0", edp="connected")
        self.carte("card1", "0000:01:00.0")
        self.retro("nvidia_0", "raw", "0000:01:00.0")
        self.assertEqual(self.choisi(), "")

    def test_firmware_passe_devant(self):
        self.carte("card1", "0000:01:00.0", edp="connected")
        self.retro("nvidia_0", "raw", "0000:01:00.0")
        self.retro("nvidia_wmi_ec_backlight", "firmware")
        self.assertEqual(self.choisi(), "nvidia_wmi_ec_backlight")

    def regler(self, message):
        """nc-brightness set 45 avec un faux brightnessctl qui sort en 1 avec ce message."""
        fb = Path(self.tmp.name) / "fb"; fb.mkdir(exist_ok=True)
        (fb / "brightnessctl").write_text(f"#!/bin/sh\necho '{message}' >&2\nexit 1\n")
        (fb / "brightnessctl").chmod(0o755)
        env = dict(os.environ, NC_SYSFS=str(self.sys), PATH=f"{fb}:{os.environ['PATH']}")
        return subprocess.run([str(BIN / "nc-brightness"), "set", "45"], env=env, capture_output=True, text=True, timeout=10)

    def test_faux_echec_du_pilote_nvidia(self):
        # Le pilote NVIDIA écrit la valeur puis répond « Protocol error » : pas un échec
        self.carte("card1", "0000:01:00.0", edp="connected")
        self.retro("nvidia_0", "raw", "0000:01:00.0")
        r = self.regler("Failed to set brightness: Protocol error")
        self.assertEqual((r.returncode, r.stderr), (0, ""))

    def test_vraie_erreur_reste_visible(self):
        self.carte("card0", "0000:00:02.0", edp="connected")
        self.retro("intel_backlight", "raw", "0000:00:02.0")
        r = self.regler("Failed to set brightness: Protocol error")
        self.assertEqual(r.returncode, 1)
        self.assertIn("Protocol error", r.stderr)            # ailleurs que sur nvidia_N : une vraie erreur


if __name__ == "__main__":
    unittest.main()

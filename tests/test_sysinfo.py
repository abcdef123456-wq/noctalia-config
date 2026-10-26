"""nc-sysinfo : profil d'énergie (choix réels d'une Legion, repli D-Bus) et nom de la carte (pci.ids de hwdata ou de pciutils)."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "home/.local/bin/nc-sysinfo"

PCI_IDS = """# faux pci.ids
10de  NVIDIA Corporation
\t2d59  GB206M [GeForce RTX 5060 Max-Q / Mobile]
1002  Advanced Micro Devices, Inc. [AMD/ATI]
\t1638  Cezanne [Radeon Vega Series]
"""


class Sysinfo(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="nc-sysinfo-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.bin = self.tmp / "bin"
        self.bin.mkdir()
        self.sys = self.tmp / "sys"
        (self.sys / "firmware/acpi").mkdir(parents=True)

    def faux(self, nom, corps):
        f = self.bin / nom
        f.write_text("#!/bin/sh\n" + corps)
        f.chmod(0o755)

    def lancer(self, *args, **env_sup):
        env = dict(os.environ, HOME=str(self.tmp), NC_SYSFS=str(self.sys), NC_LANGUE="fr",
                   PATH=f"{self.bin}:{os.environ['PATH']}", **env_sup)
        r = subprocess.run(["bash", str(SCRIPT), *args], env=env, capture_output=True, text=True, timeout=30)
        return r.stdout.strip()

    def profil(self, valeur, dbus=None):
        (self.sys / "firmware/acpi/platform_profile").write_text(valeur + "\n")
        # busctl : seul le profil nous intéresse (UPower ne répond rien)
        if dbus:
            self.faux("busctl", f'case "$*" in *PowerProfiles*) echo \'s "{dbus}"\' ;; esac\n')
        else:
            self.faux("busctl", "exit 1\n")
        return self.lancer("power")

    def test_profils_connus(self):
        self.assertTrue(self.profil("max-power").endswith("Performance"))
        self.assertTrue(self.profil("balanced-performance").endswith("Performance"))
        self.assertTrue(self.profil("performance").endswith("Performance"))
        self.assertTrue(self.profil("balanced").endswith("Équilibré"))
        self.assertTrue(self.profil("low-power").endswith("Économie"))
        self.assertTrue(self.profil("quiet").endswith("Économie"))

    def test_custom_demande_dbus_puis_perso(self):
        self.assertTrue(self.profil("custom", dbus="power-saver").endswith("Économie"))
        self.assertTrue(self.profil("custom").endswith("Perso"))

    def test_valeur_inconnue_demande_dbus(self):
        self.assertTrue(self.profil("bizarre", dbus="performance").endswith("Performance"))
        self.assertNotIn("Perso", self.profil("bizarre"))

    def alimentation(self, chargeurs):
        """Une batterie à 80 % et ces chargeurs [(type, online)] dans un faux power_supply ; la vraie règle du bureau
        (nc-gpu-regle) est copiée dans le HOME du test."""
        ps = self.sys / "class/power_supply"
        shutil.rmtree(ps, ignore_errors=True)
        (ps / "BAT0").mkdir(parents=True)
        (ps / "BAT0/type").write_text("Battery\n")
        (ps / "BAT0/capacity").write_text("80\n")
        for i, (type_, online) in enumerate(chargeurs):
            (ps / f"AC{i}").mkdir()
            (ps / f"AC{i}/type").write_text(type_ + "\n")
            (ps / f"AC{i}/online").write_text(online + "\n")
        (self.tmp / ".local/bin").mkdir(parents=True, exist_ok=True)
        shutil.copy2(REPO / "home/.local/bin/nc-gpu-regle", self.tmp / ".local/bin/nc-gpu-regle")
        self.faux("busctl", "exit 1\n")

    def test_secteur_usb_c_compte_comme_le_secteur(self):
        # Un chargeur USB-C (type USB ou USB_C) branché : « sur secteur », pas « sur batterie »
        for type_ in ("Mains", "USB", "USB_C"):
            self.alimentation([(type_, "1")])
            self.assertIn("sur secteur", self.lancer("power"), type_)
            self.alimentation([(type_, "0")])
            self.assertIn("sur batterie", self.lancer("power"), type_)

    def test_aide_francaise_complete(self):
        env = dict(os.environ, HOME=str(self.tmp), NC_LANGUE="fr")
        r = subprocess.run(["bash", str(SCRIPT), "inconnu"], env=env, capture_output=True, text=True, timeout=30)
        for mot in ("modele", "gpu", "ecrans", "disques", "power", "sante", "uptime"):
            self.assertIn(f"nc-sysinfo {mot}", r.stdout)
        self.assertNotIn("Une ligne vide", r.stdout)

    def carte(self, vendor, device, **env_sup):
        d = self.sys / "bus/pci/devices/0000:01:00.0"
        d.mkdir(parents=True, exist_ok=True)
        (d / "class").write_text("0x030000\n")
        (d / "vendor").write_text(f"0x{vendor}\n")
        (d / "device").write_text(f"0x{device}\n")
        (d / "revision").write_text("0xa1\n")
        return self.lancer("gpu", **env_sup)

    def test_pci_ids_injecte(self):
        ids = self.tmp / "pci.ids"
        ids.write_text(PCI_IDS)
        self.assertEqual(self.carte("10de", "2d59", NC_PCI_IDS=str(ids)), "RTX 5060")
        self.assertEqual(self.carte("1002", "1638", NC_PCI_IDS=str(ids)), "Radeon Vega Series")

    def test_pci_ids_absent_repli_sur_le_code(self):
        # un NC_PCI_IDS illisible n'empêche pas les chemins du système ; une carte inconnue donne son code
        r = self.carte("10de", "ffff", NC_PCI_IDS=str(self.tmp / "absent"))
        self.assertTrue(r.endswith("10de:ffff"), r)


if __name__ == "__main__":
    unittest.main()

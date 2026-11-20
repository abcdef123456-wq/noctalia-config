"""nc-ile-etat : filaire= (sans NetworkManager, route par défaut) et ppd=0 (sans démon de profils d'énergie)."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "home/.local/bin/nc-ile-etat"
ROUTE = "Iface\tDestination\tGateway\tFlags\neth0\t00000000\t0100A8C0\t0003\n"


class IleEtatPoste(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="nc-ile-etat-poste-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.bin = self.tmp / "bin"
        self.bin.mkdir()
        (self.tmp / "home/.cache").mkdir(parents=True)
        (self.tmp / "route").write_text(ROUTE)

    def faux(self, nom, corps):
        f = self.bin / nom
        f.write_text("#!/bin/sh\n" + corps)
        f.chmod(0o755)

    def cles(self, *args, path=None):
        # Aucun bus de la session ni écran : rien de la vraie session n'est lu ; faux outils devant ceux du système
        env = {"HOME": str(self.tmp / "home"), "PATH": path or f"{self.bin}:/usr/bin:/bin", "LANG": "C",
               "NC_ROUTE_FILE": str(self.tmp / "route"), "XDG_RUNTIME_DIR": str(self.tmp), "NC_SYSFS": str(self.tmp / "sys"),
               "DBUS_SESSION_BUS_ADDRESS": "unix:path=" + str(self.tmp / "pas-de-bus"),
               "DBUS_SYSTEM_BUS_ADDRESS": "unix:path=" + str(self.tmp / "pas-de-bus")}
        r = subprocess.run([shutil.which("bash"), str(SCRIPT), *args], env=env, capture_output=True, text=True, timeout=60)
        return dict(l.split("=", 1) for l in r.stdout.splitlines() if "=" in l)

    def gdbus(self, proprietaire, activables):
        self.faux("gdbus", f'case "$*" in *NameHasOwner*) echo "({proprietaire},)" ;; '
                           f'*ListActivatableNames*) echo "([{activables}],)" ;; esac\n')

    def nmcli(self, code, sortie=""):
        # faux nmcli qui note chaque appel ; code 8 : NetworkManager arrêté (man nmcli, « Exit status »)
        self.faux("nmcli", f'echo "$*" >> "{self.tmp}/appels-nmcli"\nprintf "{sortie}"\nexit {code}\n')

    def appels_nmcli(self):
        f = self.tmp / "appels-nmcli"
        return f.read_text().splitlines() if f.exists() else []

    def test_networkmanager_arrete_avec_route_filaire_1(self):
        self.nmcli(8)
        self.assertEqual(self.cles()["filaire"], "1")

    def test_nmcli_absent_avec_route_filaire_1(self):
        # PATH réduit à quelques outils, sans nmcli : timeout répond 127 (commande introuvable)
        for n in ("timeout", "awk", "grep", "head", "cut", "cat", "sed"):
            w = shutil.which(n)
            if w:
                os.symlink(w, self.bin / n)
        self.assertEqual(self.cles(path=str(self.bin))["filaire"], "1")

    def test_sans_route_filaire_0(self):
        self.nmcli(8)
        (self.tmp / "route").write_text("Iface\tDestination\n")
        self.assertEqual(self.cles()["filaire"], "0")

    def test_route_par_le_wifi_rien(self):
        # iwd seul, sans NetworkManager : la route passe par une carte Wi-Fi, l'île reste comme avant
        self.nmcli(8)
        (self.tmp / "sys/class/net/eth0/wireless").mkdir(parents=True)
        self.assertNotIn("filaire", self.cles())

    def test_avec_networkmanager_un_seul_appel_et_rien_de_nouveau(self):
        self.nmcli(0, "Maison:802-11-wireless\\nlo:loopback\\n")
        c = self.cles()
        self.assertNotIn("filaire", c)
        self.assertEqual(c["reseau"], "Maison")
        self.assertEqual(self.appels_nmcli(), ["-t -f NAME,TYPE con show --active"], "un seul nmcli, comme avant")

    def test_sans_demon_de_profils_ppd_0(self):
        self.gdbus("false", "'org.freedesktop.DBus', 'org.freedesktop.NetworkManager'")
        self.assertEqual(self.cles("profils"), {"ppd": "0"})

    def test_avec_demon_ppd_1(self):
        self.gdbus("true", "'net.hadess.PowerProfiles'")
        self.assertEqual(self.cles("profils"), {"ppd": "1"})

    def test_demon_activable_ppd_1(self):
        self.gdbus("false", "'org.freedesktop.DBus', 'net.hadess.PowerProfiles'")
        self.assertEqual(self.cles("profils"), {"ppd": "1"})

    def test_bus_illisible_ppd_1(self):
        self.faux("gdbus", "exit 1\n")
        self.assertEqual(self.cles("profils"), {"ppd": "1"})

    def test_lecture_generale_sans_cle_ppd(self):
        # les profils sont lus une fois au démarrage, pas à chaque relecture du centre (2 appels D-Bus de moins)
        self.gdbus("false", "")
        self.assertNotIn("ppd", self.cles())

    def test_qml_branche(self):
        ile = REPO / "home/.config/quickshell/nc-ile"
        etat = (ile / "Etat.qml").read_text()
        self.assertIn('"nc-ile-etat", "profils"]', etat)
        self.assertIn('etat.profilsAbsents = text.trim() === "ppd=0"', etat)
        self.assertIn("!Etat.profilsAbsents", (ile / "EnergieProfils.qml").read_text())
        self.assertIn("!Etat.profilsAbsents", (ile / "Systeme.qml").read_text())
        centre = (ile / "Centre.qml").read_text()
        self.assertIn('id === "energie" && Etat.profilsAbsents', centre)
        self.assertIn('centre.filaire ? { cle: "filaire", icone: "lan", nom: "Ethernet", page: "" }', centre)


if __name__ == "__main__":
    unittest.main()

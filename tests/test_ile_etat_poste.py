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

    def cles(self, *args):
        # Aucun bus de la session ni écran : rien de la vraie session n'est lu ; faux outils devant ceux du système
        env = {"HOME": str(self.tmp / "home"), "PATH": f"{self.bin}:/usr/bin:/bin", "LANG": "C",
               "NC_ROUTE_FILE": str(self.tmp / "route"), "XDG_RUNTIME_DIR": str(self.tmp),
               "DBUS_SESSION_BUS_ADDRESS": "unix:path=" + str(self.tmp / "pas-de-bus"),
               "DBUS_SYSTEM_BUS_ADDRESS": "unix:path=" + str(self.tmp / "pas-de-bus")}
        r = subprocess.run(["bash", str(SCRIPT), *args], env=env, capture_output=True, text=True, timeout=60)
        return dict(l.split("=", 1) for l in r.stdout.splitlines() if "=" in l)

    def gdbus(self, proprietaire, activables):
        self.faux("gdbus", f'case "$*" in *NameHasOwner*) echo "({proprietaire},)" ;; '
                           f'*ListActivatableNames*) echo "([{activables}],)" ;; esac\n')

    def test_sans_nmcli_avec_route_filaire_1(self):
        self.faux("nmcli", "exit 1\n")                      # NetworkManager absent ou arrêté
        self.assertEqual(self.cles()["filaire"], "1")

    def test_sans_nmcli_sans_route_filaire_0(self):
        self.faux("nmcli", "exit 1\n")
        (self.tmp / "route").write_text("Iface\tDestination\n")
        self.assertEqual(self.cles()["filaire"], "0")

    def test_avec_nmcli_pas_de_cle_filaire(self):
        self.faux("nmcli", 'case "$*" in *RUNNING*) echo running ;; esac\n')
        self.assertNotIn("filaire", self.cles())

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

"""Batterie des casques et écouteurs Bluetooth dans l'île (CasqueBatterie.qml, Etat.qml, Son.qml, réglage ILE_CASQUE_BATTERIE).

- Source : UPower de Quickshell (types Headset et Headphones), aucun processus, aucun minuteur, plus de bluetoothctl.
- Hors écran, avec le vrai qs lancé par « qs -p » (jamais l'île réelle) : les appareils UPower sont remplacés par une liste
  du test (même filtre, même calcul) ; niveau en pourcentage, 0 ou rien pour un casque sans batterie, choix du bon casque
  par son nom, réglage coupé.
HOME et XDG_* isolés, sans Wayland."""
from pathlib import Path
import re
import shutil
import tempfile
import textwrap
import unittest

from tests import _ile_hors_ecran as H

REPO = Path(__file__).resolve().parents[1]
QML = REPO / "home/.config/quickshell/nc-ile"


class Source(unittest.TestCase):
    def setUp(self):
        self.cb = (QML / "CasqueBatterie.qml").read_text()
        self.code = re.sub(r"//.*", "", self.cb)
        self.etat = (QML / "Etat.qml").read_text()

    def test_upower_headset_headphones(self):
        self.assertIn("import Quickshell.Services.UPower", self.cb)
        self.assertIn("UPowerDeviceType.Headset", self.cb)
        self.assertIn("UPowerDeviceType.Headphones", self.cb)

    def test_aucun_sondage_aucun_processus(self):
        self.assertNotRegex(self.code, r"\bProcess\b|\bTimer\b|bluetoothctl|execDetached|repeat: true")
        self.assertNotIn("bluetoothctl", self.etat)
        self.assertNotIn("lireBatterieBt", self.etat)

    def test_peripheriques_page_bluetooth(self):
        self.assertRegex(self.code, r"UPowerDeviceType\.Mouse[\s\S]*UPowerDeviceType\.Keyboard[\s\S]*UPowerDeviceType\.GamingInput")
        self.assertIn("function niveauAppareil(nom, adresse)", self.cb)
        liste = (QML / "PageListe.qml").read_text()
        self.assertIn("CasqueBatterie.niveauAppareil(f[1], f[0])", liste)
        self.assertIn("<= 20", liste)
        self.assertIn("Couleurs.orange", (QML / "Ligne.qml").read_text())

    def test_reaction_de_3_secondes_et_page_son(self):
        self.assertIn('activite("casque", 3000)', self.etat)
        self.assertIn("CasqueBatterie.niveauPour(casqueNom)", self.etat)
        self.assertIn("CasqueBatterie.niveauPour", (QML / "Son.qml").read_text())

    def test_reglage_et_readme(self):
        import os
        import runpy
        import warnings
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as d, patch.dict(os.environ, HOME=d), warnings.catch_warnings():
            warnings.simplefilter("ignore", ResourceWarning)
            cles = runpy.run_path(str(REPO / "home/.local/bin/nc-reglages"))["PAR_CLE"]
        self.assertEqual(cles["ILE_CASQUE_BATTERIE"].defaut, "oui")
        self.assertEqual(cles["ILE_CASQUE_BATTERIE"].section, "Île")
        self.assertIn("`ILE_CASQUE_BATTERIE`", (REPO / "README.md").read_text())


@unittest.skipUnless(shutil.which("qs"), "Quickshell requis")
class HorsEcran(unittest.TestCase):
    def lancer(self, corps):
        with tempfile.TemporaryDirectory(prefix="nc-casque-") as d:
            texte = (QML / "CasqueBatterie.qml").read_text().replace("UPower.devices.values", "Reglages.faux")
            root = H.preparer(d, ("Couleurs",), extra={"CasqueBatterie.qml": texte}, singletons=("CasqueBatterie",))
            (root / "shell.qml").write_text(H.ENTETE + "import Quickshell.Services.UPower\nShellRoot {\n" + H.OUTILS
                                            + textwrap.dedent(corps) + "\n}\n")
            code, sortie = H.lancer(root)
            for e in H.ERREURS:
                self.assertNotIn(e, sortie, sortie)
            self.assertIn("FINI", sortie, sortie)

    def test_niveaux(self):
        self.lancer('''
            Timer { interval: 200; running: true; onTriggered: {
                Reglages.faux = [
                    { type: UPowerDeviceType.Headset, isPresent: true, model: "AirPods Pro", percentage: 0.8 },
                    { type: UPowerDeviceType.Battery, isPresent: true, model: "BAT0", percentage: 0.5 },
                    { type: UPowerDeviceType.Headphones, isPresent: true, model: "Casque sans niveau", percentage: 0 },
                    { type: UPowerDeviceType.Headphones, isPresent: false, model: "Absent", percentage: 0.9 },
                    { type: UPowerDeviceType.Mouse, isPresent: true, model: "Souris", percentage: 0.4 }]
                verifier(CasqueBatterie.appareils.length === 1, "un seul casque attendu : " + JSON.stringify(CasqueBatterie.appareils))
                verifier(CasqueBatterie.niveauPour("AirPods Pro") === 80, "80 % attendu")
                verifier(CasqueBatterie.niveauPour("Autre nom") === 80, "seul casque connu : son niveau")
                verifier(CasqueBatterie.niveauPour("") === 80, "sans nom : le seul casque")
                // Deux casques : le nom décide ; un nom inconnu ne devine pas
                Reglages.faux = [
                    { type: UPowerDeviceType.Headset, isPresent: true, model: "AirPods Pro", percentage: 0.8 },
                    { type: UPowerDeviceType.Headphones, isPresent: true, model: "WH-1000XM5", percentage: 45 }]
                verifier(CasqueBatterie.niveauPour("WH-1000XM5") === 45, "45 % attendu (pourcentage déjà sur 100)")
                verifier(CasqueBatterie.niveauPour("Inconnu") === 0, "deux casques et un nom inconnu : rien")
                // Aucun casque ou casque sans niveau : rien
                Reglages.faux = [{ type: UPowerDeviceType.Headset, isPresent: true, model: "Casque", percentage: 0 }]
                verifier(CasqueBatterie.niveauPour("Casque") === 0, "casque sans niveau : 0")
                Reglages.faux = []
                verifier(CasqueBatterie.niveauPour("Casque") === 0, "aucun casque : 0")
                console.log("FINI")
                Qt.exit(0)
            } }
        ''')

    def test_peripheriques(self):
        self.lancer('''
            Timer { interval: 200; running: true; onTriggered: {
                Reglages.faux = [
                    { type: UPowerDeviceType.Mouse, isPresent: true, model: "MX Master", percentage: 0.4, nativePath: "/org/bluez/hci0/dev_AA_BB_CC_DD_EE_01" },
                    { type: UPowerDeviceType.Keyboard, isPresent: true, model: "K380", percentage: 15, nativePath: "/org/bluez/hci0/dev_AA_BB_CC_DD_EE_02" },
                    { type: UPowerDeviceType.GamingInput, isPresent: true, model: "Pad", percentage: 0.9, nativePath: "" },
                    { type: UPowerDeviceType.Mouse, isPresent: true, model: "Sans niveau", percentage: 0 },
                    { type: UPowerDeviceType.Battery, isPresent: true, model: "BAT0", percentage: 0.5 }]
                verifier(CasqueBatterie.niveauAppareil("MX Master", "AA:BB:CC:DD:EE:01") === 40, "souris par adresse")
                verifier(CasqueBatterie.niveauAppareil("Autre", "aa:bb:cc:dd:ee:02") === 15, "clavier par adresse, nom différent")
                verifier(CasqueBatterie.niveauAppareil("Pad", "11:22:33:44:55:66") === 90, "manette par nom unique")
                verifier(CasqueBatterie.niveauAppareil("Sans niveau", "") === 0, "sans niveau : rien")
                verifier(CasqueBatterie.niveauAppareil("BAT0", "") === 0, "la batterie du PC n'est pas un périphérique")
                verifier(CasqueBatterie.niveauAppareil("Inconnu", "11:22:33:44:55:66") === 0, "inconnu : rien")
                // Deux appareils de même nom : l'adresse décide, sans adresse connue on ne devine pas
                Reglages.faux = [
                    { type: UPowerDeviceType.Mouse, isPresent: true, model: "Souris BT", percentage: 0.3, nativePath: "/org/bluez/hci0/dev_AA_BB_CC_DD_EE_01" },
                    { type: UPowerDeviceType.Mouse, isPresent: true, model: "Souris BT", percentage: 0.7, nativePath: "/org/bluez/hci0/dev_AA_BB_CC_DD_EE_02" }]
                verifier(CasqueBatterie.niveauAppareil("Souris BT", "AA:BB:CC:DD:EE:02") === 70, "même nom : par adresse")
                verifier(CasqueBatterie.niveauAppareil("Souris BT", "AA:BB:CC:DD:EE:09") === 0, "même nom, adresse inconnue : rien")
                Reglages.faux = []
                verifier(CasqueBatterie.niveauAppareil("Souris BT", "AA:BB:CC:DD:EE:02") === 0, "UPower vide : rien")
                Reglages.faux = [{ type: UPowerDeviceType.Mouse, isPresent: true, model: "M", percentage: 0.5 }]
                Reglages.valeurs = { ILE_CASQUE_BATTERIE: "non" }
                verifier(CasqueBatterie.niveauAppareil("M", "") === 0, "réglage coupé : rien")
                console.log("FINI")
                Qt.exit(0)
            } }
        ''')

    def test_reglage_coupe(self):
        self.lancer('''
            Timer { interval: 200; running: true; onTriggered: {
                Reglages.faux = [{ type: UPowerDeviceType.Headset, isPresent: true, model: "AirPods", percentage: 0.8 }]
                verifier(CasqueBatterie.niveauPour("AirPods") === 80, "niveau attendu réglage actif")
                Reglages.valeurs = { ILE_CASQUE_BATTERIE: "non" }
                verifier(CasqueBatterie.niveauPour("AirPods") === 0, "réglage coupé : rien")
                console.log("FINI")
                Qt.exit(0)
            } }
        ''')


if __name__ == "__main__":
    unittest.main()

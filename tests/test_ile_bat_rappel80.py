"""Rappel « Batterie à 80 % : tu peux débrancher » (BatRappel80.qml, réglages BAT_RAPPEL_80 et BAT_RAPPEL_SEUIL).

Hors écran, avec le vrai qs lancé par « qs -p » (jamais l'île réelle), un Etat de remplacement dont le test change
pourcent / enCharge / branche / aBatterie (comme le ferait UPower), un Partage de remplacement (retient), et de faux
« notify-send » et « nc-conso » qui notent leurs arguments sans lancer les vrais. HOME et XDG_* isolés, sans Wayland."""
from pathlib import Path
import re
import shutil
import tempfile
import textwrap
import unittest

from tests import _ile_hors_ecran as H

REPO = Path(__file__).resolve().parents[1]
QML = REPO / "home/.config/quickshell/nc-ile"
ETAT = """  property int pourcent: %d
  property bool aBatterie: true
  property bool branche: true
  property bool enCharge: true
"""
PARTAGE = "pragma Singleton\nimport QtQuick\nQtObject { property bool retient: false }\n"


class Source(unittest.TestCase):
    def setUp(self):
        self.src = (QML / "BatRappel80.qml").read_text()
        self.code = re.sub(r"//.*", "", self.src)

    def test_pas_de_sondage_ni_minuteur(self):
        self.assertNotRegex(self.code, r"\bTimer\b|repeat: true|running: true")
        self.assertEqual(len(re.findall(r"(?m)^\s*component ", self.code)), 0)
        self.assertEqual(len(re.findall(r"Component\.onCompleted", self.code)), 1)

    def test_signaux_upower_et_partage(self):
        for m in ("onPourcentChanged", "onEnChargeChanged", "onBrancheChanged", "Partage.retient", "Etat.aBatterie"):
            self.assertIn(m, self.src)
        self.assertIn("BatRappel80 {}", (QML / "shell.qml").read_text())

    def test_reglages_et_readme(self):
        import os, runpy, warnings
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as d, patch.dict(os.environ, HOME=d), warnings.catch_warnings():
            warnings.simplefilter("ignore", ResourceWarning)
            nc = runpy.run_path(str(REPO / "home/.local/bin/nc-reglages"))
        c = nc["PAR_CLE"]
        self.assertEqual(c["BAT_RAPPEL_80"].defaut, "non")
        self.assertEqual(c["BAT_RAPPEL_SEUIL"].defaut, "80")
        with self.assertRaises(ValueError):                                 # borné de 50 à 100
            c["BAT_RAPPEL_SEUIL"].valider("40")
        self.assertEqual(c["BAT_RAPPEL_SEUIL"].valider("100"), "100")
        self.assertEqual(nc["MATERIEL"]["BAT_RAPPEL_80"], "batterie")
        self.assertIn("`BAT_RAPPEL_80`", (REPO / "README.md").read_text())


@unittest.skipUnless(shutil.which("qs"), "Quickshell requis")
class HorsEcran(unittest.TestCase):
    def lancer(self, corps, depart=70, reglages='{ BAT_RAPPEL_80: "oui" }', limite=False):
        with tempfile.TemporaryDirectory(prefix="nc-bat80-") as d:
            root = H.preparer(d, ("BatRappel80",), etat=ETAT % depart, extra={"Partage.qml": PARTAGE}, singletons=("Partage",))
            H.faux(root, "notify-send")
            H.faux(root, "nc-conso", "echo '{\"sante\":{\"limite\":{\"active\":%s}}}'" % ("true" if limite else "false"))
            (root / "shell.qml").write_text(H.ENTETE + textwrap.dedent('''\
                ShellRoot {
                    BatRappel80 { id: rappel }
                    function pas(p) { Etat.pourcent = p }
                    Component.onCompleted: Reglages.valeurs = %s
                ''' % reglages) + H.OUTILS + textwrap.dedent(corps) + "\n}\n")
            code, sortie = H.lancer(root)
            for e in H.ERREURS:
                self.assertNotIn(e, sortie, sortie)
            self.assertIn("FINI", sortie, sortie)
            return H.journal(root).count("notify-send ")

    # Les étapes sont espacées de 400 ms : le temps au faux nc-conso de répondre
    SUITE = '''
        property int i: 0
        property var etapes: %s
        Timer { interval: 400; running: true; repeat: true; onTriggered: {
            if (i < etapes.length) etapes[i++](); else { console.log("FINI"); Qt.exit(0) }
        } }
    '''

    def test_une_fois_au_seuil_puis_encore_apres_rebranchement(self):
        n = self.lancer(self.SUITE % '''[
            () => pas(78), () => pas(79), () => pas(80), () => pas(81), () => pas(80), () => pas(82), () => pas(84),
            () => { Etat.branche = false; Etat.enCharge = false }, () => pas(60),
            () => { Etat.branche = true; Etat.enCharge = true }, () => pas(79), () => pas(80), () => pas(95)]''')
        self.assertEqual(n, 2)

    def test_sous_le_seuil_rien(self):
        self.assertEqual(self.lancer(self.SUITE % "[() => pas(72), () => pas(75), () => pas(79)]"), 0)

    def test_deja_au_dessus_au_demarrage_ou_au_branchement_rien(self):
        self.assertEqual(self.lancer(self.SUITE % "[() => pas(91), () => pas(95)]", depart=90), 0)
        self.assertEqual(self.lancer(self.SUITE % '''[() => { Etat.branche = false; Etat.enCharge = false }, () => pas(85),
                                                       () => { Etat.branche = true; Etat.enCharge = true }, () => pas(90)]''', depart=70), 0)

    def test_limite_materielle_active_rien(self):
        self.assertEqual(self.lancer(self.SUITE % "[() => pas(79), () => pas(80), () => pas(81)]", limite=True), 0)

    def test_pas_de_rappel_hors_charge(self):
        self.assertEqual(self.lancer(self.SUITE % '''[() => pas(79), () => { Etat.enCharge = false }, () => pas(80), () => pas(81)]'''), 0)

    def test_partage_ou_jeu_reporte_jusqu_a_la_fin(self):
        n = self.lancer(self.SUITE % '''[() => Partage.retient = true, () => pas(79), () => pas(80), () => pas(82),
                                          () => { verifier(true, "rien encore") }, () => Partage.retient = false, () => pas(83)]''')
        self.assertEqual(n, 1)

    def test_partage_fini_apres_debranchement_rien(self):
        n = self.lancer(self.SUITE % '''[() => Partage.retient = true, () => pas(79), () => pas(80),
                                          () => { Etat.branche = false; Etat.enCharge = false }, () => Partage.retient = false]''')
        self.assertEqual(n, 0)

    def test_sans_batterie_rien(self):
        n = self.lancer(self.SUITE % '''[() => { Etat.aBatterie = false }, () => pas(79), () => pas(80), () => pas(95)]''')
        self.assertEqual(n, 0)

    def test_reglage_non_rien(self):
        self.assertEqual(self.lancer(self.SUITE % "[() => pas(79), () => pas(80)]", reglages='{ BAT_RAPPEL_80: "non" }'), 0)
        self.assertEqual(self.lancer(self.SUITE % "[() => pas(79), () => pas(80)]", reglages="({})"), 0)

    def test_seuil_reglable(self):
        self.assertEqual(self.lancer(self.SUITE % "[() => pas(85), () => pas(89), () => pas(90), () => pas(95)]", reglages='{ BAT_RAPPEL_80: "oui", BAT_RAPPEL_SEUIL: "90" }'), 1)
        self.assertEqual(self.lancer(self.SUITE % "[() => pas(60), () => pas(64), () => pas(65)]", depart=50,
                                     reglages='{ BAT_RAPPEL_80: "oui", BAT_RAPPEL_SEUIL: "65" }'), 1)


if __name__ == "__main__":
    unittest.main()

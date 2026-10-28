"""L'île ne travaille pas pour rien quand personne ne la voit (écran éteint ou session verrouillée).
- Un petit banc QML, avec le vrai qs hors écran, charge le VRAI bloc « pendule » copié de Etat.qml (marques
  nc-ecran-eteint et nc-verrouille, minuteur) : la pendule s'arrête quand une marque est posée, l'heure est juste
  tout de suite au retour, et un minuteur en cours la garde allumée. Etat.qml entier est trop lié au reste de l'île
  (MPRIS, PipeWire, UPower, Agents…) pour être chargé seul.
- Les conditions de running du spectre (onde de repli et cava), des webcams et du filet d'Agents.qml sont lues dans le source.
HOME et XDG_RUNTIME_DIR isolés, jamais les vrais."""
from pathlib import Path
import re
import shutil
import tempfile
import textwrap
import unittest

from tests.test_conso_pourquoi import ENTETE_QML, OUTILS_QML, lancer_qs

QML = Path(__file__).resolve().parents[1] / "home/.config/quickshell/nc-ile"


def bloc_pendule():
    src = (QML / "Etat.qml").read_text()
    debut = src.index("    property bool ecranEteint: false")
    fin = src.index("onTriggered: etat.majHeure() }", debut) + len("onTriggered: etat.majHeure() }")
    bloc = src[debut:fin]
    assert "Timer { interval: 1000; running:" in bloc
    return bloc.replace("Timer { interval: 1000; running:", "Timer { id: pendule; interval: 1000; running:")


class Source(unittest.TestCase):
    def setUp(self):
        self.etat = (QML / "Etat.qml").read_text()
        self.agents = (QML / "Agents.qml").read_text()

    def test_signal_ecran(self):
        self.assertIn('path: etat.dossierSession + "/nc-ecran-eteint"', self.etat)
        self.assertIn('path: etat.dossierSession + "/nc-verrouille"', self.etat)
        self.assertIn("readonly property bool ecranVu: !ecranEteint && !verrouille", self.etat)

    def test_pendule(self):
        self.assertRegex(self.etat, r"Timer \{ interval: 1000; running: etat\.ecranVu \|\| etat\.minuteurFin > 0;"
                                    r" repeat: true; triggeredOnStart: true; onTriggered: etat\.majHeure\(\) \}")

    def test_spectre(self):
        m = re.search(r"readonly property bool barresAffichees: (.*?)\n    // 30 images/s", self.etat, re.S)
        self.assertTrue(m)
        self.assertIn("joue && ecranVu", m.group(1))
        self.assertIn('vueActive === "musique"', m.group(1))
        self.assertIn("running: etat.barresAffichees && etat.maintenant.getTime() - etat.dernierSon > 1500 && !Reglages.sobre", self.etat)
        self.assertIn("running: etat.joue && etat.ecranVu && !Reglages.sobre", self.etat)

    def test_webcams_et_agents(self):
        self.assertRegex(self.etat, r"interval: 5000; repeat: true; running: etat\.ecranVu;")
        self.assertIn("a.demande !== null ? 1200 : 10000; repeat: true; running: Etat.ecranVu;", self.agents)

    def test_releve_des_telechargements_suspendu(self):
        # find du dossier Téléchargements : suspendu écran éteint ou verrouillé, relevé dès le réveil
        self.assertRegex(self.etat, r'running: etat\.ecranVu && Reglages\.val\("ILE_TELECHARGEMENTS", "oui"\) !== "non" && \(etat\.telechargements\.length > 0 \|\| !etat\.surveillance\); '
                                    r'triggeredOnStart: true; onTriggered: if \(!lecteurTel\.running\)')

    def test_pas_de_composant_neuf(self):
        # Règle de l'île : jamais de « component » inline neuf dans un .qml existant
        self.assertEqual(len(re.findall(r"(?m)^\s*component ", self.etat)), 0)


@unittest.skipUnless(shutil.which("qs"), "Quickshell requis")
class Banc(unittest.TestCase):
    def test_pendule_arretee_et_reveil(self):
        with tempfile.TemporaryDirectory(prefix="nc-energie-") as d:
            root = Path(d)
            (root / "run").mkdir(mode=0o700)
            (root / "shell.qml").write_text(ENTETE_QML + "import Quickshell.Io\n" + textwrap.dedent('''\
                ShellRoot {
                    Scope {
                        id: etat
                        property string dossierSession: "%s"
                        property real minuteurFin: 0
                        property date maintenant: new Date()
                        property date minute: new Date()
''') % (root / "run") + bloc_pendule() + textwrap.dedent('''\
                    }
                    property int etape: 0
                    property int tours: 0
                    function marque(nom, pose) { Quickshell.execDetached(pose ? ["touch", etat.dossierSession + "/" + nom] : ["rm", "-f", etat.dossierSession + "/" + nom]) }
''') + OUTILS_QML + textwrap.dedent('''\
                    Timer { interval: 100; running: true; repeat: true; onTriggered: {
                        tours++
                        if (etape === 0) {
                            verifier(etat.ecranVu && pendule.running, "départ : pendule allumée")
                            marque("nc-ecran-eteint", true); etape = 1; tours = 0 }
                        else if (etape === 1) {
                            if (etat.ecranVu) { verifier(tours < 40, "marque d'extinction jamais vue"); return }
                            verifier(!pendule.running, "écran éteint : pendule arrêtée")
                            etat.maintenant = new Date(0); etape = 2; tours = 0 }
                        else if (etape === 2) {
                            if (tours < 25) return
                            verifier(etat.maintenant.getTime() === 0, "pendule arrêtée : l'heure ne bouge pas")
                            etat.minuteurFin = Date.now() + 60000
                            etape = 3; tours = 0 }
                        else if (etape === 3) {
                            if (tours < 15) return
                            verifier(pendule.running && etat.maintenant.getTime() > 0, "un minuteur en cours garde la pendule")
                            etat.minuteurFin = 0; etat.maintenant = new Date(0); etape = 4; tours = 0 }
                        else if (etape === 4) {
                            verifier(!pendule.running, "minuteur fini et écran éteint : pendule arrêtée")
                            marque("nc-ecran-eteint", false); marque("nc-verrouille", true); etape = 5; tours = 0 }
                        else if (etape === 5) {
                            if (tours < 10) return
                            verifier(!etat.ecranEteint && etat.verrouille && !pendule.running, "verrouillé : pendule arrêtée, écran compté éteint à tort")
                            etat.maintenant = new Date(0); marque("nc-verrouille", false); etape = 6; tours = 0 }
                        else if (etape === 6) {
                            if (!etat.ecranVu) { verifier(tours < 40, "marque de verrou jamais retirée"); return }
                            // Au réveil : heure juste dans la foulée, sans attendre le tour d'une seconde
                            verifier(pendule.running, "réveil : pendule reprise")
                            verifier(Math.abs(Date.now() - etat.maintenant.getTime()) < 700, "réveil : heure fausse " + etat.maintenant.getTime())
                            console.log("BANC OK")
                            Qt.quit() } } }
                    Timer { interval: 20000; running: true; onTriggered: Qt.exit(9) }
                }'''))
            r, sortie = lancer_qs(root, d, delai=30)
            self.assertEqual(r.returncode, 0, sortie)
            self.assertIn("BANC OK", sortie)


if __name__ == "__main__":
    unittest.main()

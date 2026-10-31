"""Aperçu d'aimantation de l'île (AimantApercu.qml, IPC « aimant » de shell.qml, règle de calque de regles.lua) : lu depuis
les sources (calque, namespace, pas de clavier ni de clic, rien en boucle, aucun component inline) et hors écran avec le vrai qs
lancé par « qs -p » (jamais l'île réelle), HOME et XDG_* isolés : zone hors liste ignorée, AIMANT_APERCU=non ignoré, chargeur
inactif sans zone puis déchargé après le fondu, cadre placé sur le rectangle, arrondi borné à 20."""
import re
import shutil
import tempfile
import textwrap
import unittest
from pathlib import Path

from tests import _ile_hors_ecran as H

REPO = Path(__file__).resolve().parents[1]
QML = REPO / "home/.config/quickshell/nc-ile"
REGLES = REPO / "home/.config/hypr/nc/regles.lua"


def bloc_shell():
    """Le morceau de shell.qml de l'aperçu (propriétés, minuteur, chargeur) et la fonction IPC aimant, tels quels."""
    source = (QML / "shell.qml").read_text()
    debut = source.index("    readonly property var aimantZones")
    fin = source.index("    // Fiche des raccourcis (Super + /), éditable")
    m = re.search(r"        function aimant\(zone: string.*?\n        }\n", source, re.S)
    assert m, "fonction IPC aimant introuvable"
    return source[debut:fin], m.group(0)


def apercu_hors_fenetre():
    """AimantApercu.qml avec une fenêtre ordinaire à la place de la PanelWindow de Quickshell (qui n'existe pas hors de
    Quickshell) ; ce qui est propre à Quickshell est retiré, et vérifié à part dans les sources."""
    source = (QML / "AimantApercu.qml").read_text()
    source = source.replace("import Quickshell.Wayland\n", "").replace("PanelWindow {", "Window {")
    for l in ("    anchors { top: true; bottom: true; left: true; right: true }\n", "    exclusionMode: ExclusionMode.Ignore\n",
              "    WlrLayershell.layer: WlrLayer.Overlay\n", '    WlrLayershell.namespace: "nc-aimant"\n',
              "    WlrLayershell.keyboardFocus: WlrKeyboardFocus.None\n", "    mask: Region {}\n"):
        assert l in source, l
        source = source.replace(l, "")
    source = source.replace("ap.screen ? ap.screen.x : 0", "0").replace("ap.screen ? ap.screen.y : 0", "0")
    return source.replace('    color: "transparent"\n', '    color: "transparent"; width: 1600; height: 900; visible: true\n')


STUB = "import QtQuick\nimport Quickshell\nQtObject {\n property var screen\n property bool montre: false\n property real rx\n property real ry\n property real rw\n property real rh\n}\n"


class Sources(unittest.TestCase):
    def setUp(self):
        self.apercu = (QML / "AimantApercu.qml").read_text()
        self.shell = (QML / "shell.qml").read_text()

    def test_calque_sans_clavier_ni_clic(self):
        a = self.apercu
        self.assertIn("WlrLayershell.layer: WlrLayer.Overlay", a)
        self.assertIn('WlrLayershell.namespace: "nc-aimant"', a)
        self.assertIn("WlrLayershell.keyboardFocus: WlrKeyboardFocus.None", a)
        self.assertIn("mask: Region {}", a)
        self.assertIn("anchors { top: true; bottom: true; left: true; right: true }", a)
        self.assertNotIn("MouseArea", a)

    def test_rien_en_boucle_ni_component_inline(self):
        for nom, texte in (("AimantApercu.qml", self.apercu), ("shell.qml", self.shell)):
            self.assertIsNone(re.search(r"^\s*component\s+\w+\s*:", texte, re.M), nom + " : component inline")
        for interdit in ("Timer", "loops", "running: true", "repeat", "Animation on", "Qt.callLater"):
            self.assertNotIn(interdit, self.apercu)
        self.assertEqual(self.apercu.count("Component.onCompleted"), 1)

    def test_ipc_et_chargeur(self):
        self.assertEqual(len(re.findall(r"function aimant\(", self.shell)), 1)
        self.assertIn("function aimant(zone: string, x: int, y: int, w: int, h: int): void", self.shell)
        self.assertIn('Reglages.val("AIMANT_APERCU", "oui") === "non"', self.shell)
        self.assertIn("active: racine.aimantCharge", self.shell)
        self.assertEqual(self.shell.count("AimantApercu {"), 1)
        for p in ("aimantZone", "aimantX", "aimantCharge", "aimantEcran"):
            self.assertEqual(len(re.findall(r"property \w+ " + p + r"\b", self.shell)), 1, p)

    def test_regle_de_calque(self):
        r = REGLES.read_text()
        self.assertIn('hl.layer_rule({ name = "nc-aimant-sans-anim", match = { namespace = "^nc-aimant$" }, no_anim = true })', r)


@unittest.skipUnless(shutil.which("qs"), "Quickshell requis")
class HorsEcran(unittest.TestCase):
    def lancer(self, corps, reglages=None, delai=30):
        with tempfile.TemporaryDirectory(prefix="nc-aimant-") as d:
            root = H.preparer(d, ("Couleurs", "Texte", "Ico"), extra={"AimantApercu.qml": apercu_hors_fenetre()})
            proprietes, fonction = bloc_shell()
            reg = ("Reglages.valeurs = " + __import__("json").dumps(reglages) + "\n") if reglages else ""
            # Le chargeur de shell.qml, avec un objet vide à la place de la fenêtre (le vrai fichier est essayé plus bas)
            (root / "Chargee.qml").write_text(STUB)
            proprietes = proprietes.replace("AimantApercu {", "Chargee {")
            (root / "qmldir").write_text((root / "qmldir").read_text() + "Chargee 1.0 Chargee.qml\n")
            (root / "shell.qml").write_text(H.ENTETE + "import QtTest\nShellRoot {\n id: racine\n property int etape: 0\n property int ticks: 0\n"
                                            + proprietes + "\n QtObject { id: ipc\n" + fonction + " }\n" + H.OUTILS
                                            + " Component.onCompleted: { " + reg + "}\n"
                                            + textwrap.dedent(corps) + "\n Timer { interval: 15000; running: true; onTriggered: { console.error(\"ECHEC délai\"); Qt.exit(3) } }\n}\n")
            code, sortie = H.lancer(root, delai=delai)
            for e in H.ERREURS:
                self.assertNotIn(e, sortie, sortie)
            self.assertIn("FINI", sortie, sortie)
            return sortie

    def test_zone_hors_liste_et_chargeur(self):
        self.lancer('''
            Timer { interval: 60; running: true; repeat: true; onTriggered: {
                ticks++
                if (etape === 0) {
                    verifier(aimantChargeur.item === null && !aimantCharge, "inactif sans zone")
                    ipc.aimant("n'importe quoi", 0, 0, 800, 400); ipc.aimant("haut'; os.exit() --", 0, 0, 800, 400)
                    ipc.aimant("haut", 0, 0, 0, 400); ipc.aimant("haut", 0, 0, 800, -4)
                    verifier(!aimantCharge && aimantZone === "", "zone hors liste ou rectangle vide ignorés")
                    ipc.aimant("gauche", 10, 20, 800, 400)
                    verifier(aimantCharge && aimantZone === "gauche" && aimantW === 800, "zone valide prise")
                    etape++; ticks = 0; return }
                if (etape === 1) {
                    if (!aimantChargeur.item) return
                    var o = aimantChargeur.item
                    verifier(o.montre && o.rx === 10 && o.ry === 20 && o.rw === 800 && o.rh === 400, "le cadre reçoit le rectangle")
                    ipc.aimant("haut-droite", 800, 0, 800, 400)
                    verifier(aimantChargeur.item === o && o.rx === 800, "la zone change : même cadre, nouveau rectangle")
                    ipc.aimant("", 0, 0, 0, 0)
                    verifier(!o.montre && aimantCharge, "zone vide : le cadre se fond, encore chargé")
                    etape++; ticks = 0; return }
                if (etape === 2) {
                    if (aimantCharge) { if (ticks > 15) verifier(false, "jamais déchargé"); return }
                    verifier(aimantChargeur.item === null, "déchargé après le fondu")
                    console.log("FINI"); Qt.exit(0) }
            } }
        ''')

    def test_reglage_non_ignore_tout(self):
        self.lancer('''
            Timer { interval: 60; running: true; repeat: true; onTriggered: {
                ticks++
                if (ticks < 2) return
                ipc.aimant("haut", 0, 0, 800, 400)
                verifier(!aimantCharge && aimantZone === "" && aimantChargeur.item === null, "AIMANT_APERCU=non : appel ignoré")
                console.log("FINI"); Qt.exit(0)
            } }
        ''', reglages={"AIMANT_APERCU": "non"})

    def test_cadre_place_arrondi_et_fondu(self):
        with tempfile.TemporaryDirectory(prefix="nc-aimant-") as d:
            root = H.preparer(d, ("Couleurs", "Texte", "Ico"), extra={"AimantApercu.qml": apercu_hors_fenetre()})
            (root / "shell.qml").write_text(H.ENTETE + "ShellRoot {\n id: racine\n property var fen: null\n property int ticks: 0\n" + H.OUTILS
                                            + ' Component.onCompleted: { Reglages.valeurs = ({"FENETRES_ARRONDI": 50}) }\n'
                                            + ''' Timer { interval: 80; running: true; repeat: true; onTriggered: {
                ticks++
                if (ticks === 1) { var c = Qt.createComponent("AimantApercu.qml"); verifier(c.status === Component.Ready, c.errorString())
                                   fen = c.createObject(racine, { rx: 24, ry: 60, rw: 700, rh: 500 }); return }
                if (ticks === 3) {
                    var cadre = trouver(fen.contentItem, "cadre")
                    verifier(cadre && cadre.x === 24 && cadre.y === 60 && cadre.width === 700 && cadre.height === 500, "cadre à sa place dès le départ : " + cadre.x + " " + cadre.y)
                    verifier(cadre.radius === 20, "arrondi borné à 20 : " + cadre.radius)
                    verifier(cadre.opacity > 0.99, "visible")
                    fen.rx = 800; fen.rw = 400; fen.montre = false; return }
                if (ticks === 40) {
                    var c2 = trouver(fen.contentItem, "cadre")
                    verifier(Math.abs(c2.x - 800) < 1 && Math.abs(c2.width - 400) < 1, "ressort arrivé : " + c2.x + " " + c2.width)
                    verifier(c2.opacity < 0.01, "fondu fini : " + c2.opacity)
                    console.log("FINI"); Qt.exit(0) }
            } }
            Timer { interval: 15000; running: true; onTriggered: { console.error("ECHEC délai"); Qt.exit(3) } }
}
''')
            code, sortie = H.lancer(root)
            for e in H.ERREURS:
                self.assertNotIn(e, sortie, sortie)
            self.assertIn("FINI", sortie, sortie)


if __name__ == "__main__":
    unittest.main()

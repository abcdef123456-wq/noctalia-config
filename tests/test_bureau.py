"""Widgets du bureau (Bureau.qml ; nc-reglages WIDGETS_BUREAU, « non » par défaut).

- Source : aucun nouveau `component` inline dans les .qml existants ; un seul minuteur, pas d'animation ni de souris.
- Hors écran (qs -p, offscreen) : à « non » aucune fenêtre n'est créée ; à « oui » un seul minuteur, au plus 60 s, arrêté
  écran éteint et quand « Tout masquer » a caché les widgets ; police et majuscules du thème appliquées.
Tout se passe dans un dossier temporaire."""
import re
import shutil
import tempfile
import unittest

from tests import _ile_hors_ecran as H

QML = H.QML
BIN = H.REPO / "home/.local/bin"


def lire(nom):
    return (QML / nom).read_text(encoding="utf-8")


COULEURS = ('pragma Singleton\nimport QtQuick\nQtObject { property string police: "Mono"; property bool majuscules: false\n'
            ' function rayon(b, w, h) { return b } property real verre: 1; property real epaisseur: 0; property bool aContour: false\n'
            ' readonly property color carte: "#1c1c1e"; readonly property color accent: "#0a84ff"\n'
            ' readonly property color texte: "#ffffff"; readonly property color texteSec: "#98989d" }\n')
ETAT = (' property bool widgetsCaches: false; property int majs: 0; property string heure: "12:34"; property string dateLongue: "lundi 1 janvier"\n'
        ' function majHeure() { majs++ }\n')
REMPLACEMENTS = (("import Quickshell.Wayland\n", "import QtQuick.Window\n"), ("PanelWindow {", "Window {"),
                 ("    required property var modelData\n", ""), ("    screen: modelData\n", ""),
                 ("    anchors { top: true; left: true }\n", ""), ("    margins { top: 96; left: 48 }\n", ""),
                 ("    implicitWidth: plaque.width\n", "    width: plaque.width\n"),
                 ("    implicitHeight: plaque.height\n", "    height: plaque.height\n"),
                 ("    exclusionMode: ExclusionMode.Ignore\n", ""), ("    WlrLayershell.layer: WlrLayer.Bottom\n", ""),
                 ('    WlrLayershell.namespace: "nc-bureau"\n', ""), ("    mask: Region {}\n", ""))


class BureauSource(unittest.TestCase):
    def test_aucun_nouveau_component_dans_les_fichiers_existants(self):
        for nom in ("shell.qml", "Fenetres.qml", "Etat.qml", "Bureau.qml"):
            self.assertNotRegex(lire(nom), r"(?m)^\s*component\s+\w+\s*:", nom)

    def test_un_seul_minuteur_arrete_ecran_eteint_ou_widgets_caches_sans_souris(self):
        b = lire("Bureau.qml")
        self.assertEqual(len(re.findall(r"\bTimer\s*\{", b)), 1)
        self.assertRegex(b, r"readonly property bool vu:\s*Etat\.ecranVu\s*&&\s*!Etat\.widgetsCaches")
        self.assertRegex(b, r"running:\s*b\.vu")
        self.assertRegex(b, r"Math\.min\(60000,\s*60000 - Date\.now\(\) % 60000")
        self.assertIn("mask: Region {}", b)
        self.assertIn("WlrLayer.Bottom", b)
        for interdit in ("MouseArea", "Behavior", "Animation"):
            self.assertNotIn(interdit, b)

    def test_instance_par_ecran_seulement_a_oui(self):
        self.assertRegex(lire("shell.qml"), r'model:\s*Reglages\.val\("WIDGETS_BUREAU",\s*"non"\)\s*===\s*"oui"\s*\?\s*Quickshell\.screens\s*:\s*\[\]\s*\n\s*Bureau \{\}')

    def test_masquer_et_afficher_touchent_les_widgets(self):
        f = lire("Fenetres.qml")
        self.assertRegex(f, r"Etat\.widgetsCaches = true")
        self.assertRegex(f, r"Etat\.widgetsCaches = false")
        self.assertRegex(f, r"Etat\.widgetsCaches = !Etat\.widgetsCaches")
        self.assertRegex(lire("Etat.qml"), r"property bool widgetsCaches:\s*false")

    def test_reglage_ouinon_non_par_defaut_dans_la_section_ile_et_le_groupe_ile(self):
        r = (BIN / "nc-reglages").read_text(encoding="utf-8")
        self.assertRegex(r, r'R\("WIDGETS_BUREAU",\s*"Île",\s*L\([^\n]*\),\s*"ouinon",\s*"non",')
        self.assertRegex(r, r'"PAUSE_YEUX",\s*"WIDGETS_BUREAU"')


@unittest.skipUnless(shutil.which("qs"), "Quickshell requis")
class BureauHorsEcran(unittest.TestCase):
    CREER = ('if (etape === 0) { var c = Qt.createComponent("Bureau.qml"); verifier(c.status === Component.Ready, c.errorString());'
             ' b = c.createObject(racine); etape++; return }\n')

    def executer(self, scenario):
        source = lire("Bureau.qml")
        for avant, apres in REMPLACEMENTS:
            self.assertIn(avant, source)
            source = source.replace(avant, apres)
        with tempfile.TemporaryDirectory(prefix="nc-bur-") as d:
            root = H.preparer(d, ["Texte"], etat=ETAT, extra={"Couleurs.qml": COULEURS, "Bureau.qml": source})
            (root / "shell.qml").write_text(H.ENTETE + "ShellRoot {\n id: racine\n property int etape: 0\n property var b: null\n" + H.OUTILS + """
 function minuteurs() { var l = []; for (var i = 0; i < b.data.length; i++) { var o = b.data[i]; if (o.interval !== undefined && o.repeat !== undefined) l.push(o) } return l }
 Timer { interval: 150; running: true; repeat: true; onTriggered: {
""" + self.CREER + scenario + """
 } }
 Timer { interval: 15000; running: true; onTriggered: { console.error("ECHEC délai"); Qt.exit(3) } }
}
""")
            code, sortie = H.lancer(root, delai=40)
        echecs = [x for x in sortie.splitlines() if any(e in x for e in H.ERREURS)]
        self.assertEqual(code, 0, sortie[-1500:])
        self.assertEqual(echecs, [], sortie[-1500:])

    def test_a_oui_un_seul_minuteur_a_la_minute_arrete_ecran_eteint_et_widgets_caches(self):
        self.executer("""
  var m = minuteurs()
  if (etape === 1) {
    verifier(m.length === 1, "un seul minuteur : " + m.length)
    verifier(m[0].running && m[0].interval <= 60000 && m[0].interval > 0, "minuteur actif, au plus 60 s : " + m[0].interval)
    verifier(Etat.majs >= 1, "heure relue au départ")
    verifier(trouver(b.contentItem, "bureauHeure").text === "12:34", "heure affichée")
    verifier(trouver(b.contentItem, "bureauDate").text === "lundi 1 janvier", "date affichée")
    Etat.ecranVu = false; etape++; return }
  if (etape === 2) { verifier(!m[0].running, "arrêté écran éteint")
    Etat.ecranVu = true; etape++; return }
  if (etape === 3) { verifier(m[0].running, "reprise écran allumé")
    Etat.widgetsCaches = true; etape++; return }
  if (etape === 4) { verifier(!m[0].running && !b.visible, "arrêté et caché par Tout masquer")
    Etat.widgetsCaches = false; etape++; return }
  if (etape === 5) { verifier(m[0].running && b.visible, "revenu avec Tout afficher"); Qt.quit() }
""")

    def test_police_et_majuscules_du_theme(self):
        self.executer("""
  if (etape === 1) { var h = trouver(b.contentItem, "bureauHeure")
    verifier(h.font.family === "Mono" && h.font.capitalization === Font.MixedCase, "police du thème")
    Couleurs.majuscules = true; Couleurs.police = "Serif"; etape++; return }
  if (etape === 2) { var d = trouver(b.contentItem, "bureauDate")
    verifier(d.font.capitalization === Font.AllUppercase && d.font.family === "Serif", "majuscules et police suivent le thème"); Qt.quit() }
""")

    def test_sans_plaque_date_au_dessus_heure_fine_et_ombre(self):
        self.executer("""
  if (etape === 1) { var p = b.cible
    verifier(p.color.a > 0.8 && p.color.a < 0.9, "plaque au verre du thème : " + p.color.a)
    verifier(trouver(b.contentItem, "bureauDate").visible && !trouver(b.contentItem, "bureauDateHaut").visible, "date sous l'heure")
    Reglages.valeurs = { WIDGETS_PLAQUE: "non" }; etape++; return }
  if (etape === 2) { var h = trouver(b.contentItem, "bureauHeure"), haut = trouver(b.contentItem, "bureauDateHaut")
    verifier(b.cible.color.a === 0 && b.cible.border.width === 0, "ni fond ni filet")
    verifier(haut.visible && !trouver(b.contentItem, "bureauDate").visible && haut.y < h.y, "date au-dessus de l'heure")
    verifier(h.font.pixelSize > 88 && h.font.weight === Font.Light && h.style === Text.Raised, "heure très grande, fine, ombrée"); Qt.quit() }
""")

    @unittest.skipUnless(shutil.which("qs"), "Quickshell requis")
    def test_le_modele_de_shell_est_vide_a_non_et_un_ecran_a_oui(self):
        m = re.search(r'model:\s*(Reglages\.val\("WIDGETS_BUREAU".*?)\n\s*Bureau \{\}', lire("shell.qml"), re.S)
        self.assertIsNotNone(m)
        modele = m.group(1).replace("Quickshell.screens", '["ecran"]')
        for valeurs, attendu in (("({})", 0), ('({ WIDGETS_BUREAU: "non" })', 0), ('({ WIDGETS_BUREAU: "oui" })', 1)):
            with tempfile.TemporaryDirectory(prefix="nc-bur-") as d:
                root = H.preparer(d, [])
                (root / "Reglages.qml").write_text(H.REGLAGES.replace("property var valeurs: ({})", "property var valeurs: " + valeurs))
                (root / "shell.qml").write_text(H.ENTETE + 'ShellRoot { Timer { interval: 100; running: true; onTriggered: { var n = (%s).length; '
                                                'if (n !== %d) { console.error("ECHEC n=" + n); Qt.exit(2) } Qt.exit(0) } } }\n' % (modele, attendu))
                code, sortie = H.lancer(root)
            self.assertEqual(code, 0, valeurs + sortie[-800:])


if __name__ == "__main__":
    unittest.main()

"""Widgets de bureau choisis par le thème (champ « widgets » ; WidgetsTheme.qml ; style.conf WIDGETS_THEME).

- Validation fermée dans nc-reglages (types, coins, tailles, 4 au plus), refus sans rien changer, en français et en anglais.
- style.conf : sans « widgets » rien de nouveau ; avec, une ligne WIDGETS_THEME=type:coin:taille,…
- Hors écran (qs -p, offscreen) : un contenu par type, coupé à WIDGETS_BUREAU=non, caché par « Tout masquer », rien écran
  éteint ; citation du jour (4 Kio, 200 caractères, une par jour) ; un seul minuteur (2 s, jauges vues seulement).
Tout se passe dans un dossier temporaire."""
import json
import re
import shutil
import tempfile
import unittest

from tests import _ile_hors_ecran as H
from tests.test_themes import Base

QML = H.QML
OK = {"type": "horloge-fine", "coin": "haut-gauche", "taille": "grand"}


def lire(nom):
    return (QML / nom).read_text(encoding="utf-8")


COULEURS = ('pragma Singleton\nimport QtQuick\nQtObject { property string police: "Mono"; property bool majuscules: false\n'
            ' readonly property color texte: "#ffffff"; readonly property color texteSec: "#98989d" }\n')
ETAT = (' property bool widgetsCaches: false; property bool aMusique: false; property string titre: ""; property string artiste: ""\n'
        ' property var minute: new Date(2026, 10, 22, 9, 5)\n'
        ' property var mois: ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"]\n')
REMPLACEMENTS = (("import Quickshell.Wayland\n", "import QtQuick.Window\n"), ("PanelWindow {", "Window {"),
                 ("            required property var modelData\n            screen: modelData\n", ""),
                 ("            anchors { top: true; bottom: true; left: true; right: true }\n", ""),
                 ("            margins { top: 96; left: 48; right: 48; bottom: 48 }\n", ""),
                 ("            exclusionMode: ExclusionMode.Ignore\n", ""), ("            WlrLayershell.layer: WlrLayer.Bottom\n", ""),
                 ('            WlrLayershell.namespace: "nc-bureau-theme"\n', ""), ("            mask: Region {}\n", ""),
                 ("            visible: w.vu\n", "            width: 800; height: 600; visible: w.vu\n"),
                 ("Quickshell.screens", '["ecran"]'))


class Source(unittest.TestCase):
    def test_aucun_nouveau_component_et_widgets_theme_cree_par_shell(self):
        for nom in ("shell.qml", "Bureau.qml", "WidgetsTheme.qml"):
            self.assertNotRegex(lire(nom), r"(?m)^\s*component\s+\w+\s*:", nom)
        # Créé seulement si WIDGETS_BUREAU=oui ET un thème a des widgets : rien en mémoire sinon
        self.assertRegex(lire("shell.qml"), r'LazyLoader \{\s*active: Reglages\.val\("WIDGETS_BUREAU", "non"\) === "oui" '
                         r'&& Reglages\.val\("WIDGETS_THEME", ""\) !== ""\s*WidgetsTheme \{\}')

    def test_un_seul_minuteur_de_2_s_seulement_pour_les_jauges_vues(self):
        w = lire("WidgetsTheme.qml")
        self.assertEqual(re.findall(r"\bTimer\s*\{[^}]*\}", w), ["Timer { id: echantillonneur; interval: 2000; repeat: true; running: w.vu && w.aJauges; onTriggered: w.echantillon() }"])
        self.assertIn("readonly property bool vu: Etat.ecranVu && !Etat.widgetsCaches", w)
        self.assertIn('Reglages.val("WIDGETS_BUREAU", "non") === "oui"', w)
        self.assertIn("slice(0, 4096)", w)
        self.assertIn("slice(0, 200)", w)
        for interdit in ("MouseArea", "Behavior", "Animation"):
            self.assertNotIn(interdit, w)

    def test_bureau_se_tait_quand_le_theme_a_des_widgets(self):
        b = lire("Bureau.qml")
        self.assertIn('readonly property bool remplace: Reglages.val("WIDGETS_THEME", "") !== ""', b)
        self.assertIn("!remplace", b)


class Validation(Base):
    def refuse(self, widgets, attendu="widgets"):
        self.ecrire_theme("mauvais", widgets=widgets)
        self.nc("set", "STYLE", "nord")
        avant = self.style_conf()
        r = self.nc("set", "STYLE", "mauvais")
        self.assertNotEqual(r.returncode, 0, r.stdout)
        self.assertIn(attendu, r.stdout + r.stderr)
        self.assertEqual(self.style_conf(), avant)

    def test_listes_fermees(self):
        self.refuse("horloge-fine")
        self.refuse([dict(OK, type="meteo")])
        self.refuse([dict(OK, coin="milieu")])
        self.refuse([dict(OK, taille="enorme")])
        self.refuse([{"type": "citation", "coin": "centre"}])
        self.refuse([dict(OK, extra=1)])
        self.refuse(["horloge-fine"])

    def test_quatre_au_plus(self):
        self.refuse([OK] * 5)
        self.ecrire_theme("bon", widgets=[OK] * 4)
        self.assertEqual(self.nc("set", "STYLE", "bon").returncode, 0)

    def test_message_francais_et_anglais(self):
        self.ecrire_theme("mauvais", widgets=[dict(OK, type="meteo")])
        fr = self.nc("set", "STYLE", "mauvais")
        self.env["NC_LANGUE"] = "en"
        en = self.nc("set", "STYLE", "mauvais")
        self.assertNotEqual(fr.stdout + fr.stderr, en.stdout + en.stderr)

    def test_style_conf_sans_widgets_et_avec(self):
        self.assertEqual(self.nc("set", "STYLE", "nord").returncode, 0)
        self.assertNotIn("WIDGETS_THEME", self.lignes_style())
        self.ecrire_theme("expl", widgets=[OK, {"type": "citation", "coin": "bas-droite", "taille": "petit"}])
        self.assertEqual(self.nc("set", "STYLE", "expl").returncode, 0)
        self.assertEqual(self.lignes_style()["WIDGETS_THEME"], "horloge-fine:haut-gauche:grand,citation:bas-droite:petit")
        self.assertEqual(self.nc("set", "STYLE", "nord").returncode, 0)
        self.assertNotIn("WIDGETS_THEME", self.lignes_style())


@unittest.skipUnless(shutil.which("qs"), "Quickshell requis")
class HorsEcran(unittest.TestCase):
    def executer(self, valeurs, scenario, citations=None):
        source = lire("WidgetsTheme.qml")
        for avant, apres in REMPLACEMENTS:
            self.assertIn(avant, source)
            source = source.replace(avant, apres)
        with tempfile.TemporaryDirectory(prefix="nc-wt-") as d:
            root = H.preparer(d, ["Texte"], etat=ETAT, extra={"Couleurs.qml": COULEURS, "WidgetsTheme.qml": source})
            if citations is not None:
                (root / "config/nc").mkdir(parents=True)
                (root / "config/nc/citations.txt").write_text(citations, encoding="utf-8")
            (root / "shell.qml").write_text(H.ENTETE + "ShellRoot {\n id: racine\n property int etape: 0\n property var w: null\n" + H.OUTILS + """
 function minuteurs() { return [w.minuteur] }
 Timer { interval: 150; running: true; repeat: true; onTriggered: {
  if (etape === 0) { Reglages.valeurs = %s; var c = Qt.createComponent("WidgetsTheme.qml"); verifier(c.status === Component.Ready, c.errorString())
    w = c.createObject(racine); etape++; return }
""" % json.dumps(valeurs) + scenario + """
 } }
 Timer { interval: 15000; running: true; onTriggered: { console.error("ECHEC délai"); Qt.exit(3) } }
}
""")
            code, sortie = H.lancer(root, delai=40)
        echecs = [x for x in sortie.splitlines() if any(e in x for e in H.ERREURS)]
        self.assertEqual(code, 0, sortie[-1500:])
        self.assertEqual(echecs, [], sortie[-1500:])

    def test_un_contenu_par_type(self):
        self.executer({"WIDGETS_BUREAU": "oui", "WIDGETS_THEME": "horloge-fine:haut-gauche:grand,horloge-mots:centre:moyen,calendrier:bas-droite:petit,jauges:bas-gauche:petit,citation:haut-droite:petit"}, """
  if (etape === 1) {
    verifier(w.liste.length === 4, "quatre au plus : " + w.liste.length)
    verifier(w.lignes("horloge-fine")[0] === "09:05", "fine : " + w.lignes("horloge-fine"))
    verifier(w.lignes("horloge-segments")[0] === "09 : 05", "segments")
    verifier(w.lignes("horloge-mots").join(" ") === "Il est neuf heures et cinq", "mots : " + w.lignes("horloge-mots"))
    var c = w.lignes("calendrier")
    verifier(c[0] === "novembre 2026" && c.join("|").indexOf("[22]") >= 0 && c.length === 8, "calendrier : " + c.join("|"))
    verifier(w.lignes("musique").length === 0, "pas de musique")
    Etat.aMusique = true; Etat.titre = "T"; Etat.artiste = "A"; etape++; return }
  if (etape === 2) {
    verifier(w.lignes("musique").join("|") === "T|A", "musique")
    var j = w.lignes("jauges")
    verifier(j.length === 3 && j[0].indexOf("CPU") === 0 && j[1].indexOf("RAM") === 0 && j[2].indexOf("DSK") === 0, "jauges")
    verifier(w.lignes("citation").length === 0, "sans fichier, pas de citation")
    verifier(w.fenetres.length === 1 && w.fenetres[0].visible, "une fenêtre visible"); Qt.quit() }
""")

    def test_coupe_a_non_et_sans_widgets(self):
        for valeurs in ({"WIDGETS_THEME": "jauges:centre:petit"}, {"WIDGETS_BUREAU": "non", "WIDGETS_THEME": "jauges:centre:petit"},
                        {"WIDGETS_BUREAU": "oui"}):
            with self.subTest(valeurs=valeurs):
                self.executer(valeurs, """
  if (etape === 1) {
    verifier(w.liste.length === 0 && w.fenetres.length === 0, "aucune fenêtre")
    for (var i = 0, m = minuteurs(); i < m.length; i++) verifier(!m[i].running, "aucun minuteur actif")
    Qt.quit() }
""")

    def test_jauges_cachees_ou_ecran_eteint_ne_tournent_pas(self):
        self.executer({"WIDGETS_BUREAU": "oui", "WIDGETS_THEME": "jauges:centre:petit"}, """
  var m = minuteurs()
  if (etape === 1) {
    verifier(m.length === 1 && m[0].interval === 2000 && m[0].repeat, "un seul minuteur de 2 s : " + m.length)
    verifier(m[0].running && w.fenetres[0].visible, "actif quand vu")
    Etat.widgetsCaches = true; etape++; return }
  if (etape === 2) { verifier(!m[0].running && !w.fenetres[0].visible, "arrêté et caché par Tout masquer")
    Etat.widgetsCaches = false; Etat.ecranVu = false; etape++; return }
  if (etape === 3) { verifier(!m[0].running && !w.fenetres[0].visible, "rien écran éteint")
    Etat.ecranVu = true; etape++; return }
  if (etape === 4) { verifier(m[0].running && w.fenetres[0].visible, "reprise"); Qt.quit() }
""")

    def test_sans_jauges_le_minuteur_dort(self):
        self.executer({"WIDGETS_BUREAU": "oui", "WIDGETS_THEME": "horloge-fine:centre:moyen"}, """
  if (etape === 1) { var m = minuteurs()
    verifier(m.length === 1 && !m[0].running, "minuteur arrêté sans jauges"); Qt.quit() }
""")

    def test_citation_du_jour_4_kio_200_caracteres_une_par_jour(self):
        theme = {"WIDGETS_BUREAU": "oui", "WIDGETS_THEME": "citation:bas-gauche:moyen"}
        self.executer(theme, """
  if (etape === 1 || etape === 2) { etape++; return }
  if (etape === 3) { var a = w.lignes("citation")[0]
    verifier(["un", "deux", "trois"].indexOf(a) >= 0, "une ligne du fichier : " + a)
    Etat.minute = new Date(2026, 10, 23, 9, 5); etape++; return }
  if (etape === 4) { var b = w.lignes("citation")[0]
    verifier(["un", "deux", "trois"].indexOf(b) >= 0, "le lendemain : " + b)
    var vus = {}; vus[b] = 1; Etat.minute = new Date(2026, 10, 24, 9, 5); etape++; return }
  if (etape === 5) { var c = w.lignes("citation")[0]
    Etat.minute = new Date(2026, 10, 22, 17, 0); etape++; return }
  if (etape === 6) { Qt.quit() }
""", citations="un\n\n  deux  \ntrois\n")
        self.executer(theme, """
  if (etape === 1 || etape === 2) { etape++; return }
  if (etape === 3) {
    verifier(w.citations.length === 1 && w.citations[0].length === 200, "200 caractères au plus : " + w.citations.map(x => x.length))
    Qt.quit() }
""", citations="x" * 500 + "\n")
        self.executer(theme, """
  if (etape === 1 || etape === 2) { etape++; return }
  if (etape === 3) {
    verifier(w.citations.length > 0 && w.citations.length <= 41, "4 Kio au plus : " + w.citations.length)
    Qt.quit() }
""", citations=("y" * 99 + "\n") * 100)
        self.executer(theme, """
  if (etape === 1 || etape === 2) { etape++; return }
  if (etape === 3) { verifier(w.lignes("citation").length === 0 && w.citations.length === 0, "sans fichier, rien"); Qt.quit() }
""")

    def test_une_citation_par_jour(self):
        self.executer({"WIDGETS_BUREAU": "oui", "WIDGETS_THEME": "citation:bas-gauche:moyen"}, """
  if (etape === 1 || etape === 2) { etape++; return }
  if (etape === 3) { var j0 = w.lignes("citation")[0]; var h = Etat.minute
    Etat.minute = new Date(2026, 10, 22, 21, 40); etape++; return }
  if (etape === 4) { verifier(w.lignes("citation")[0] === "c" + (w.jour % 3), "même jour, même citation")
    var j = w.jour; Etat.minute = new Date(2026, 10, 23, 0, 5); etape++; return }
  if (etape === 5) { verifier(w.lignes("citation")[0] === "c" + (w.jour % 3), "le lendemain, la suivante : " + w.lignes("citation")); Qt.quit() }
""", citations="c0\nc1\nc2\n")


if __name__ == "__main__":
    unittest.main()

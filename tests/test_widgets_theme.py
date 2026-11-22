"""Widgets de bureau choisis par le thème (champ « widgets » ; WidgetsTheme.qml ; style.conf WIDGETS_THEME).

- Validation fermée dans nc-reglages (types, coins, tailles, style facultatif, 8 au plus), refus sans rien changer, en
  français et en anglais.
- style.conf : sans « widgets » rien de nouveau ; avec, une ligne WIDGETS_THEME=type:coin:taille[:style],…
- Hors écran (qs -p, offscreen) : un contenu par type, coupé à WIDGETS_BUREAU=non, caché par « Tout masquer », rien écran
  éteint ; citation du jour (4 Kio, 200 caractères, une par jour) ; un seul minuteur (2 s, jauges ou anneau vus seulement)
  dans tous les fichiers du widget ; cartes (brutal : contour et ombre dure ; ronde : coins transparents), horloge géante,
  météo absente = rien, widgets d'un même coin empilés sans se toucher ni sortir de l'écran.
Tout se passe dans un dossier temporaire."""
import json
import re
import shutil
import tempfile
import unittest
from importlib.machinery import SourceFileLoader
from importlib.util import module_from_spec, spec_from_loader

from tests import _ile_hors_ecran as H
from tests.test_themes import Base

QML = H.QML
OK = {"type": "horloge-fine", "coin": "haut-gauche", "taille": "grand"}
FICHIERS = ("WidgetsTheme.qml", "CarteWidget.qml", "Anneau.qml")
_chargeur = SourceFileLoader("rendu_ile", str(H.REPO / "outils/rendu-ile.py"))
RENDU = module_from_spec(spec_from_loader("rendu_ile", _chargeur))
_chargeur.exec_module(RENDU)


def lire(nom):
    return (QML / nom).read_text(encoding="utf-8")


COULEURS = ('pragma Singleton\nimport QtQuick\nQtObject { property string police: "Mono"; property bool majuscules: false\n'
            ' readonly property color texte: "#ffffff"; readonly property color texteSec: "#98989d"\n'
            ' readonly property color carte: "#203040"; readonly property color gris2: "#2c2c2e"; readonly property color gris3: "#3a3a3c"\n'
            ' readonly property color accent: "#0a84ff"; readonly property color surAccent: "#ffffff"; readonly property color jauge: "#ffffff"\n'
            ' readonly property string contour: "degrade"; readonly property real verre: 1\n'
            ' function rayon(base, w, h) { return Math.min(base, Math.min(w, h) / 2) } }\n')
ETAT = (' property bool widgetsCaches: false; property bool aMusique: false; property string titre: ""; property string artiste: ""\n'
        ' property string pochette: ""; property string iconeLecteur: ""\n'
        ' property var meteo: ({}); property bool meteoPilule: false\n'
        ' property var minute: new Date(2026, 10, 22, 9, 5)\n'
        ' property var jours: ["dimanche", "lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi"]\n'
        ' property var mois: ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"]\n')
REMPLACEMENTS = (("import Quickshell.Wayland\n", "import QtQuick.Window\n"), ("PanelWindow {", "Window {"),
                 ("            required property var modelData\n            screen: modelData\n", ""),
                 ("            anchors { top: true; bottom: true; left: true; right: true }\n", ""),
                 ("            margins { top: 96; left: 48; right: 48; bottom: 48 }\n", ""),
                 ("            exclusionMode: ExclusionMode.Ignore\n", ""), ("            WlrLayershell.layer: WlrLayer.Bottom\n", ""),
                 ('            WlrLayershell.namespace: "nc-bureau-theme"\n', ""), ("            mask: Region {}\n", ""),
                 ("            visible: w.vu\n", "            width: LARGEUR; height: HAUTEUR; visible: w.vu\n"),
                 ("Quickshell.screens", '["ecran"]'))


class Source(unittest.TestCase):
    def test_aucun_nouveau_component_et_widgets_theme_cree_par_shell(self):
        for nom in ("shell.qml", "Bureau.qml") + FICHIERS:
            self.assertNotRegex(lire(nom), r"(?m)^\s*component\s+\w+\s*:", nom)
        # Créé seulement si WIDGETS_BUREAU=oui ET un thème a des widgets : rien en mémoire sinon
        self.assertRegex(lire("shell.qml"), r'LazyLoader \{\s*active: Reglages\.val\("WIDGETS_BUREAU", "non"\) === "oui" '
                         r'&& Reglages\.val\("WIDGETS_THEME", ""\) !== ""\s*WidgetsTheme \{\}')

    def test_un_seul_minuteur_de_2_s_seulement_pour_les_jauges_vues(self):
        w = lire("WidgetsTheme.qml")
        tous = [m for nom in FICHIERS for m in re.findall(r"\bTimer\s*\{[^}]*\}", lire(nom))]
        self.assertEqual(tous, ["Timer { id: echantillonneur; interval: 2000; repeat: true; running: w.vu && w.aJauges; onTriggered: w.echantillon() }"])
        self.assertIn('liste[i].type === "jauges" || liste[i].type === "anneau"', w)
        self.assertIn("readonly property bool vu: Etat.ecranVu && !Etat.widgetsCaches", w)
        self.assertIn('Reglages.val("WIDGETS_BUREAU", "non") === "oui"', w)
        self.assertIn("slice(0, 4096)", w)
        self.assertIn("slice(0, 200)", w)
        for nom in FICHIERS:
            for interdit in ("MouseArea", "Behavior", "Animation", "layer.effect", "MultiEffect", "Blur", "Canvas", "Process {"):
                if not (nom == "WidgetsTheme.qml" and interdit == "Process {"):      # df, toutes les 30 s, jauges vues seulement
                    self.assertNotIn(interdit, lire(nom), nom)
        # Météo et musique : ce qu'Etat lit déjà (nc-meteo, MPRIS), aucun processus de plus
        self.assertNotIn('"nc-meteo"', lire("CarteWidget.qml"))
        self.assertIn("Etat.meteoPilule", lire("CarteWidget.qml"))

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
        self.refuse([dict(OK, type="meteorologie")])
        self.refuse([dict(OK, style="ombre")])
        self.refuse([dict(OK, style=["carte"])])
        self.refuse([dict(OK, coin="milieu")])
        self.refuse([dict(OK, taille="enorme")])
        self.refuse([{"type": "citation", "coin": "centre"}])
        self.refuse([dict(OK, extra=1)])
        self.refuse(["horloge-fine"])

    def test_huit_au_plus_et_nouveaux_types_et_styles(self):
        self.refuse([OK] * 9)
        bons = [{"type": t, "coin": "haut-droite", "taille": "moyen", "style": s} for t, s in
                (("horloge-geante", "texte"), ("date", "carte-ronde"), ("meteo", "carte-ronde"), ("anneau", "carte-ronde"),
                 ("accueil", "carte"), ("musique", "brutal"), ("jauges", "carte"), ("calendrier", "brutal"))]
        self.ecrire_theme("bon", widgets=bons)
        self.assertEqual(self.nc("set", "STYLE", "bon").returncode, 0)
        self.assertTrue(self.lignes_style()["WIDGETS_THEME"].startswith("horloge-geante:haut-droite:moyen:texte,date:haut-droite:moyen:carte-ronde,"))

    def test_message_francais_et_anglais(self):
        self.ecrire_theme("mauvais", widgets=[dict(OK, style="ombre")])
        fr = self.nc("set", "STYLE", "mauvais")
        self.env["NC_LANGUE"] = "en"
        en = self.nc("set", "STYLE", "mauvais")
        self.assertNotEqual(fr.stdout + fr.stderr, en.stdout + en.stderr)
        self.assertIn("widgets.style", fr.stdout + fr.stderr)
        self.assertIn("widgets.style", en.stdout + en.stderr)

    def test_style_conf_sans_widgets_et_avec(self):
        self.assertEqual(self.nc("set", "STYLE", "nord").returncode, 0)
        self.assertNotIn("WIDGETS_THEME", self.lignes_style())
        self.ecrire_theme("expl", widgets=[OK, {"type": "citation", "coin": "bas-droite", "taille": "petit"},
                                           {"type": "meteo", "coin": "bas-droite", "taille": "petit", "style": "carte-ronde"}])
        self.assertEqual(self.nc("set", "STYLE", "expl").returncode, 0)
        # sans style : la ligne d'avant, à l'identique ; avec : un 4e champ
        self.assertEqual(self.lignes_style()["WIDGETS_THEME"],
                         "horloge-fine:haut-gauche:grand,citation:bas-droite:petit,meteo:bas-droite:petit:carte-ronde")
        self.assertEqual(self.nc("set", "STYLE", "nord").returncode, 0)
        self.assertNotIn("WIDGETS_THEME", self.lignes_style())


@unittest.skipUnless(shutil.which("qs"), "Quickshell requis")
class HorsEcran(unittest.TestCase):
    def executer(self, valeurs, scenario, citations=None, taille=(800, 600), captures=None):
        source = lire("WidgetsTheme.qml")
        for avant, apres in REMPLACEMENTS:
            self.assertIn(avant, source)
            source = source.replace(avant, apres.replace("LARGEUR", str(taille[0])).replace("HAUTEUR", str(taille[1])))
        with tempfile.TemporaryDirectory(prefix="nc-wt-") as d:
            root = H.preparer(d, ["Texte", "Ico", "CarteWidget", "Anneau"], etat=ETAT,
                              extra={"Couleurs.qml": COULEURS, "WidgetsTheme.qml": source})
            scenario = scenario.replace("DOSSIER", str(root))
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
            images = {n: RENDU.lire_png(root / (n + ".png")) for n in (captures or ()) if (root / (n + ".png")).exists()}
        self.images = images
        echecs = [x for x in sortie.splitlines() if any(e in x for e in H.ERREURS)]
        self.assertEqual(code, 0, sortie[-1500:])
        self.assertEqual(echecs, [], sortie[-1500:])

    def test_un_contenu_par_type(self):
        self.executer({"WIDGETS_BUREAU": "oui", "WIDGETS_THEME": "horloge-fine:haut-gauche:grand,horloge-mots:centre:moyen,calendrier:bas-droite:petit,jauges:bas-gauche:petit,citation:haut-droite:petit"}, """
  if (etape === 1) {
    verifier(w.liste.length === 5 && w.liste[0].style === "texte", "cinq, style texte par défaut : " + w.liste.length)
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


    def test_huit_au_plus(self):
        self.executer({"WIDGETS_BUREAU": "oui", "WIDGETS_THEME": ",".join(["accueil:centre:petit:bizarre"] * 9)}, """
  if (etape === 1) { verifier(w.liste.length === 8 && w.liste[0].style === "texte", "huit au plus, style inconnu = texte"); Qt.quit() }
""")

    def test_disposer_empile_sans_chevauchement_ni_sortie(self):
        self.executer({"WIDGETS_BUREAU": "oui", "WIDGETS_THEME": "accueil:centre:petit"}, """
  if (etape === 1) {
    function c(coin, style) { return { type: "accueil", coin: coin, taille: "moyen", style: style || "texte" } }
    function touche(a, b) { return a.x < b.x + b.l && b.x < a.x + a.l && a.y < b.y + b.h && b.y < a.y + a.h }
    // même coin : en colonne, l'un sous l'autre, ancrés au coin
    var p = w.disposer([c("haut-gauche"), c("haut-gauche")], [[300, 100], [200, 80]], 1000, 800, 20)
    verifier(p[0].v && p[1].v && !touche(p[0], p[1]), "colonne : " + JSON.stringify(p))
    verifier(p[0].x === 0 && p[0].y === 0 && p[1].x === 0 && p[1].y === 120, "colonne en haut à gauche : " + JSON.stringify(p))
    // bas-droite : ancrée en bas à droite
    p = w.disposer([c("bas-droite"), c("bas-droite")], [[300, 100], [200, 80]], 1000, 800, 20)
    verifier(p[1].y + p[1].h === 800 && p[0].x + 300 === 1000 && !touche(p[0], p[1]), "bas droite : " + JSON.stringify(p))
    // cartes rondes à la suite : côte à côte, à la taille de la plus grande ; la carte suivante dessous, à la largeur de la colonne
    p = w.disposer([c("haut-droite", "carte-ronde"), c("haut-droite", "carte-ronde"), c("haut-droite", "carte")], [[100, 100], [120, 120], [90, 50]], 1000, 800, 20)
    verifier(p[0].y === p[1].y && p[0].l === 120 && p[1].x === p[0].x + 140 && !touche(p[0], p[1]), "rangée ronde : " + JSON.stringify(p))
    verifier(p[2].y === 140 && p[2].l === 260 && p[2].x === p[0].x && p.every(x => x.v), "carte dessous, colonne nette : " + JSON.stringify(p))
    // trop haut : les derniers ne sont pas montrés, jamais hors de l'écran
    p = w.disposer([c("bas-gauche"), c("bas-gauche"), c("bas-gauche")], [[100, 300], [100, 300], [100, 300]], 1000, 700, 20)
    verifier(p[0].v && p[1].v && !p[2].v && p[0].y === 0, "débordement : " + JSON.stringify(p))
    // deux coins qui se rencontrent : le second n'est pas montré
    p = w.disposer([c("haut-gauche"), c("bas-gauche")], [[100, 500], [100, 400]], 1000, 800, 20)
    verifier(p[0].v && !p[1].v, "coins qui se touchent : " + JSON.stringify(p))
    // rien à montrer (taille nulle) : pas de place gardée
    p = w.disposer([c("haut-gauche"), c("haut-gauche")], [[0, 0], [100, 50]], 1000, 800, 20)
    verifier(p[0] === undefined && p[1].y === 0, "vide sans place : " + JSON.stringify(p))
    Qt.quit() }
""")

    def test_cartes_du_meme_coin_ne_se_chevauchent_pas(self):
        self.executer({"WIDGETS_BUREAU": "oui", "WIDGETS_THEME": "horloge-fine:haut-gauche:moyen:carte,calendrier:haut-gauche:moyen:carte,"
                       "date:haut-droite:moyen:carte-ronde,anneau:haut-droite:moyen:carte-ronde,accueil:haut-droite:moyen:brutal"}, """
  if (etape === 1 || etape === 2) { etape++; return }
  if (etape === 3) {
    var f = w.fenetres[0].contentItem, noms = ["horloge-fine", "calendrier", "date", "anneau", "accueil"], b = []
    for (var i = 0; i < noms.length; i++) { var it = trouver(f, "nc-widget-" + noms[i])
      verifier(it && it.visible && it.width > 0 && it.height > 0, "montré : " + noms[i])
      verifier(it.x >= 0 && it.y >= 0 && it.x + it.width <= f.width && it.y + it.height <= f.height, "dans l'écran : " + noms[i])
      b.push([it.x, it.y, it.width, it.height]) }
    for (var a = 0; a < b.length; a++) for (var z = a + 1; z < b.length; z++)
      verifier(!(b[a][0] < b[z][0] + b[z][2] && b[z][0] < b[a][0] + b[a][2] && b[a][1] < b[z][1] + b[z][3] && b[z][1] < b[a][1] + b[a][3]),
               "chevauchement " + noms[a] + " / " + noms[z] + " : " + JSON.stringify(b))
    verifier(b[1][1] > b[0][1] && b[0][2] === b[1][2], "colonne de cartes de même largeur : " + JSON.stringify(b))
    verifier(b[2][1] === b[3][1] && b[2][2] === b[2][3] && b[2][2] === b[3][2], "cartes rondes côte à côte, égales : " + JSON.stringify(b))
    Qt.quit() }
""", taille=(2464, 1456))

    def test_carte_brutale_et_carte_ronde(self):
        self.executer({"WIDGETS_BUREAU": "oui", "WIDGETS_THEME": "accueil:haut-gauche:moyen:brutal,date:bas-droite:moyen:carte-ronde"}, """
  if (etape === 1 || etape === 2) { etape++; return }
  if (etape === 3) { etape = 10
    trouver(w.fenetres[0].contentItem, "nc-widget-accueil").grabToImage(function (r) { verifier(r.saveToFile("DOSSIER/brutal.png"), "capture"); etape = 4 }) }
  if (etape === 4) { etape = 10
    trouver(w.fenetres[0].contentItem, "nc-widget-date").grabToImage(function (r) { verifier(r.saveToFile("DOSSIER/ronde.png"), "capture"); Qt.quit() }) }
""", taille=(1600, 1000), captures=("brutal", "ronde"))
        def px(img, x, y):
            bpp, lignes = img[2], img[3]
            return tuple(lignes[y][x * bpp:(x + 1) * bpp])
        blanc = (255, 255, 255)
        w, h, bpp, _ = self.images["brutal"]
        self.assertGreater(w, 60)
        self.assertEqual(px(self.images["brutal"], 1, h // 2)[:3], blanc, "contour de 3 px, couleur du texte")
        self.assertEqual(px(self.images["brutal"], w - 2, h - 2)[:3], blanc, "ombre dure décalée en bas à droite")
        self.assertEqual(px(self.images["brutal"], w - 2, 3)[:3], (0, 0, 0), "rien au-dessus de l'ombre (décalée de 6 px)")
        self.assertEqual(px(self.images["brutal"], 6, h // 2)[:3], (0x20, 0x30, 0x40), "fond de la carte, couleur de la palette")
        w, h, bpp, _ = self.images["ronde"]
        self.assertEqual(w, h, "carte ronde : un carré englobant")
        coin = px(self.images["ronde"], 2, 2)
        self.assertTrue(coin[3] == 0 if bpp == 4 else coin == (0, 0, 0), f"coin du carré : le fond d'écran (transparent) : {coin!r}")
        self.assertEqual(px(self.images["ronde"], w // 2, 6)[:3], (0x20, 0x30, 0x40), "haut du cercle : la carte")

    def test_horloge_geante_et_accueil(self):
        self.executer({"WIDGETS_BUREAU": "oui", "WIDGETS_THEME": "horloge-geante:haut-gauche:grand,accueil:haut-gauche:moyen"}, """
  if (etape === 1 || etape === 2) { etape++; return }
  if (etape === 3) { var f = w.fenetres[0].contentItem, g = trouver(f, "nc-widget-horloge-geante"), a = trouver(f, "nc-widget-accueil")
    verifier(g.visible && g.height > 1600 / 6, "horloge géante : plus d'un sixième de l'écran : " + g.height)
    verifier(a.visible && a.y >= g.y + g.height, "accueil sous l'horloge")
    verifier(w.heure(Etat.minute) === "09:05" && w.accueil(Etat.minute) === "Bonjour", "09:05, Bonjour")
    verifier(w.accueil(new Date(2026, 10, 22, 19, 0)) === "Bonsoir" && w.accueil(new Date(2026, 10, 22, 3, 0)) === "Bonsoir", "Bonsoir")
    Qt.quit() }
""", taille=(2464, 1456))

    def test_meteo_absente_ne_montre_rien(self):
        self.executer({"WIDGETS_BUREAU": "oui", "WIDGETS_THEME": "meteo:haut-gauche:moyen:carte-ronde,musique:haut-gauche:moyen:carte"}, """
  if (etape === 1 || etape === 2) { etape++; return }
  if (etape === 3) { var f = w.fenetres[0].contentItem, m = trouver(f, "nc-widget-meteo"), u = trouver(f, "nc-widget-musique")
    verifier(m.implicitWidth === 0 && !m.visible, "sans météo, rien")
    verifier(u.implicitWidth === 0 && !u.visible, "sans musique, rien")
    Etat.meteo = { temp: 13, icone: "cloud", texte: "Nuageux", min: 8, max: 13 }; Etat.meteoPilule = true
    Etat.aMusique = true; Etat.titre = "T"; Etat.artiste = "A"; etape++; return }
  if (etape === 4) { var f2 = w.fenetres[0].contentItem, m2 = trouver(f2, "nc-widget-meteo"), u2 = trouver(f2, "nc-widget-musique")
    verifier(m2.visible && m2.width > 0 && m2.width === m2.height, "météo dans une carte ronde")
    verifier(u2.visible && u2.y >= m2.y + m2.height, "musique dessous")
    Qt.quit() }
""", taille=(2464, 1456))


if __name__ == "__main__":
    unittest.main()

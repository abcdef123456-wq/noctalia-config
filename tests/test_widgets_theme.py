"""Widgets de bureau choisis par le thème (champ « widgets » ; WidgetsTheme.qml ; style.conf WIDGETS_THEME).

- Validation fermée dans nc-reglages (types, coins, tailles, style facultatif, 8 au plus), refus sans rien changer, en
  français et en anglais.
- style.conf : sans « widgets » rien de nouveau ; avec, une ligne WIDGETS_THEME=type:coin:taille[:style],…
- Hors écran (qs -p, offscreen) : un contenu par type, coupé à WIDGETS_BUREAU=non, caché par « Tout masquer », rien écran
  éteint ; citation du jour (4 Kio, 200 caractères, une par jour) ; jauges relevées à la minute (un seul minuteur de 2 s, une fois, jauges vues seulement)
  dans tous les fichiers du widget ; cartes (brutal : contour et ombre dure ; ronde : coins transparents), horloge géante,
  météo absente = rien, widgets d'un même coin empilés sans se toucher ni sortir de l'écran.
- Chiffres d'une horloge : un fichier Chiffres<Nom>.qml par valeur de WIDGETS_CHIFFRES, ni plus ni moins ; séparateur de
  « points » en deux disques (aucun glyphe « : ») ; aiguilles justes à 3 h et 6 h ; jauge à aiguille sur le même minuteur.
- Lisibilité mesurée sur des rendus hors écran (échelle 1,6, taille « petit ») : chaque texte a 4,5:1 sur le fond réel
  derrière lui (carte, ou voile du style « texte » sur un fond d'écran clair ET sombre) et 11 px au moins.
- Musique cachée quand rien ne joue ; WIDGETS_POLICE (liste avec repli, petits textes : la suivante ; accepté par un thème).
Tout se passe dans un dossier temporaire."""
import hashlib
import json
import re
import shutil
import subprocess
import tempfile
import unittest
from importlib.machinery import SourceFileLoader
from importlib.util import module_from_spec, spec_from_loader
from pathlib import Path

from tests import _ile_hors_ecran as H
from tests.test_themes import Base

QML = H.QML
OK = {"type": "horloge-fine", "coin": "haut-gauche", "taille": "grand"}
CHIFFRES = sorted(f.name for f in H.QML.glob("Chiffres*.qml"))
FICHIERS = ("WidgetsTheme.qml", "CarteWidget.qml", "Anneau.qml", "JaugeAiguille.qml", *CHIFFRES)
COMPOSANTS = ["Texte", "Ico", "CarteWidget", "Anneau", "JaugeAiguille"] + [Path(f).stem for f in CHIFFRES]
_chargeur = SourceFileLoader("rendu_ile", str(H.REPO / "outils/rendu-ile.py"))
RENDU = module_from_spec(spec_from_loader("rendu_ile", _chargeur))
_chargeur.exec_module(RENDU)
_chargeur = SourceFileLoader("nc_reglages_widgets", str(H.REPO / "home/.local/bin/nc-reglages"))
NC = module_from_spec(spec_from_loader("nc_reglages_widgets", _chargeur))
_chargeur.exec_module(NC)


def lire(nom):
    return (QML / nom).read_text(encoding="utf-8")


COULEURS = ('pragma Singleton\nimport QtQuick\nQtObject { property string police: "Mono"; property bool majuscules: false\n'
            ' readonly property color texte: "#ffffff"; readonly property color texteSec: "#686868"\n'
            ' readonly property color fond: "#000000"\n'
            ' readonly property color carte: "#203040"; readonly property color gris2: "#2c2c2e"; readonly property color gris3: "#3a3a3c"\n'
            ' readonly property color accent: "#0a84ff"; readonly property color surAccent: "#ffffff"; readonly property color jauge: "#ffffff"\n'
            ' readonly property string contour: "degrade"; readonly property real verre: 1\n'
            ' function rayon(base, w, h) { return Math.min(base, Math.min(w, h) / 2) } }\n')
ETAT = (' property bool widgetsCaches: false; property bool aMusique: false; property bool joue: false\n'
        ' property string titre: ""; property string artiste: ""\n'
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
        self.assertEqual(tous, ["Timer { id: echantillonneur; interval: 2000; running: w.vu && w.aJauges; onTriggered: w.echantillon() }"])
        self.assertIn("onMinuteChanged: if (vu && aJauges) echantillon()", w)
        self.assertIn('["jauges", "anneau", "jauge-aiguille"].indexOf(liste[i].type) >= 0', w)
        self.assertIn("readonly property bool vu: Etat.ecranVu && !Etat.widgetsCaches", w)
        self.assertIn('Reglages.val("WIDGETS_BUREAU", "non") === "oui"', w)
        self.assertIn("slice(0, 4096)", w)
        self.assertIn("slice(0, 200)", w)
        for nom in FICHIERS:
            for interdit in ("MouseArea", "Behavior", "Animation", "layer.effect", "MultiEffect", "Blur", "Canvas", "Shape", "Process {"):
                if not (nom == "WidgetsTheme.qml" and interdit == "Process {"):      # df, un relevé sur quinze, jauges vues seulement
                    self.assertNotIn(interdit, lire(nom), nom)
        # Météo et musique : ce qu'Etat lit déjà (nc-meteo, MPRIS), aucun processus de plus
        self.assertNotIn('"nc-meteo"', lire("CarteWidget.qml"))
        self.assertIn("Etat.meteoPilule", lire("CarteWidget.qml"))

    def test_un_fichier_chiffres_par_valeur_de_la_liste_fermee(self):
        # Un nouveau style (volets, nixie…) = un fichier Chiffres<Nom>.qml ET son nom dans la liste, ni l'un sans l'autre
        self.assertEqual(sorted(f[len("Chiffres"):-len(".qml")].lower() for f in CHIFFRES), sorted(NC.WIDGETS_CHIFFRES))
        for f in CHIFFRES:
            self.assertIn("required property var carte", lire(f), f)
        self.assertTrue(set(NC.WIDGETS_VARIANTES) <= set(NC.WIDGETS_TYPES))
        self.assertIn('Qt.resolvedUrl("Chiffres" + chiffres.charAt(0).toUpperCase() + chiffres.slice(1) + ".qml")', lire("CarteWidget.qml"))

    def test_separateur_des_points_dessine(self):
        # Le « : » de Doto sort en croix : deux disques, jamais un glyphe
        p = lire("ChiffresPoints.qml")
        self.assertNotRegex(p, r"(?s)Texte|Text \{|font\.")
        self.assertIn('model: signe.modelData === ":" ? [2, 4] : []', p)

    def test_widgets_police_declaree(self):
        r = NC.PAR_CLE["WIDGETS_POLICE"]
        self.assertEqual((r.section, r.genre, r.defaut), ("Île", "texte", ""))
        self.assertTrue(r._aide.fr and r._aide.en and r._nom.fr and r._nom.en)
        self.assertIn('Reglages.val("WIDGETS_POLICE", "")', lire("WidgetsTheme.qml"))

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

    def test_chiffres_et_variantes(self):
        self.refuse([dict(OK, chiffres="nixie")])
        self.refuse([{"type": "date", "coin": "centre", "taille": "petit", "chiffres": "points"}])     # pas une horloge
        self.refuse([{"type": "musique", "coin": "centre", "taille": "petit", "variante": "ligne"}])  # pas sa variante
        self.refuse([dict(OK, variante="quart")])
        bons = [{"type": "horloge-geante", "coin": "haut-gauche", "taille": "grand", "chiffres": "points"},
                {"type": "horloge-geante", "coin": "bas-gauche", "taille": "petit", "style": "carte", "chiffres": "aiguille", "variante": "quart"},
                {"type": "calendrier", "coin": "bas-droite", "taille": "petit", "variante": "ligne"},
                {"type": "jauge-aiguille", "coin": "haut-droite", "taille": "petit", "style": "carte-ronde"}]
        self.ecrire_theme("bon", widgets=bons, reglages={"WIDGETS_POLICE": "Doto, JetBrains Mono"})
        r = self.nc("set", "STYLE", "bon")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.lignes_style()["WIDGETS_THEME"],
                         "horloge-geante:haut-gauche:grand::points,horloge-geante:bas-gauche:petit:carte:aiguille:quart,"
                         "calendrier:bas-droite:petit:::ligne,jauge-aiguille:haut-droite:petit:carte-ronde")
        self.assertEqual(self.lignes_style()["WIDGETS_POLICE"], "Doto, JetBrains Mono")

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
    def executer(self, valeurs, scenario, citations=None, taille=(800, 600), captures=None, fond=None):
        source = lire("WidgetsTheme.qml")
        for avant, apres in REMPLACEMENTS:
            self.assertIn(avant, source)
            source = source.replace(avant, apres.replace("LARGEUR", str(taille[0])).replace("HAUTEUR", str(taille[1])))
        if fond:            # un fond d'écran uni sous les widgets
            source = source.replace("visible: w.vu\n", 'visible: w.vu\n            Rectangle { anchors.fill: parent; color: "%s" }\n' % fond)
        with tempfile.TemporaryDirectory(prefix="nc-wt-") as d:
            root = H.preparer(d, COMPOSANTS, etat=ETAT,
                              extra={"Couleurs.qml": COULEURS, "WidgetsTheme.qml": source})
            scenario = scenario.replace("DOSSIER", str(root))
            if citations is not None:
                (root / "config/nc").mkdir(parents=True)
                (root / "config/nc/citations.txt").write_text(citations, encoding="utf-8")
            (root / "shell.qml").write_text(H.ENTETE + "ShellRoot {\n id: racine\n property int etape: 0\n property var w: null\n property var tic0: null\n" + H.OUTILS + """
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
        self.sortie = sortie
        echecs = [x for x in sortie.splitlines() if any(e in x for e in H.ERREURS)]
        self.assertEqual(code, 0, sortie[-1500:])
        self.assertEqual(echecs, [], sortie[-1500:])

    def test_un_contenu_par_type(self):
        self.executer({"WIDGETS_BUREAU": "oui", "WIDGETS_THEME": "horloge-fine:haut-gauche:grand,horloge-mots:centre:moyen,calendrier:bas-droite:petit,jauges:bas-gauche:petit,citation:haut-droite:petit"}, """
  if (etape === 1) {
    verifier(w.liste.length === 5 && w.liste[0].style === "texte", "cinq, style texte par défaut : " + w.liste.length)
    verifier(w.lignes("horloge-fine")[0] === "09:05", "fine : " + w.lignes("horloge-fine"))
    verifier(w.lignes("horloge-mots").join(" ") === "Il est neuf heures et cinq", "mots : " + w.lignes("horloge-mots"))
    var c = w.lignes("calendrier")
    verifier(c[0] === "novembre 2026" && c.join("|").indexOf("[22]") >= 0 && c.length === 8, "calendrier : " + c.join("|"))
    verifier(w.lignes("musique").length === 0, "pas de musique")
    Etat.aMusique = true; Etat.joue = true; Etat.titre = "T"; Etat.artiste = "A"; etape++; return }
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
    verifier(m.length === 1 && m[0].interval === 2000 && !m[0].repeat, "un seul minuteur de 2 s, une fois : " + m.length)
    verifier(m[0].running && w.fenetres[0].visible, "actif quand vu")
    Etat.widgetsCaches = true; etape++; return }
  if (etape === 2) { verifier(!m[0].running && !w.fenetres[0].visible, "arrêté et caché par Tout masquer")
    Etat.widgetsCaches = false; Etat.ecranVu = false; etape++; return }
  if (etape === 3) { verifier(!m[0].running && !w.fenetres[0].visible, "rien écran éteint")
    Etat.ecranVu = true; etape++; return }
  if (etape === 4) { verifier(m[0].running && w.fenetres[0].visible, "reprise"); Qt.quit() }
""")

    def test_jauges_immobiles_entre_deux_minutes(self):
        # Rien ne bouge au repos : après le relevé de départ, plus rien jusqu'à la minute suivante, comme l'heure
        self.executer({"WIDGETS_BUREAU": "oui", "WIDGETS_THEME": "jauges:centre:petit:carte"}, """
  if (etape === 1) { racine.tic0 = w.tic; etape++; return }
  if (etape < 20) { etape++; return }
  if (etape === 20) { verifier(!w.minuteur.running && w.tic === racine.tic0 + 1, "un seul relevé de plus, puis rien : " + (w.tic - racine.tic0))
    racine.tic0 = w.tic; Etat.minute = new Date(2026, 10, 22, 9, 6); etape++; return }
  if (etape === 21) { verifier(w.tic === racine.tic0 + 1, "un relevé à la minute"); Qt.quit() }
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
    Etat.aMusique = true; Etat.joue = true; Etat.titre = "T"; Etat.artiste = "A"; etape++; return }
  if (etape === 4) { var f2 = w.fenetres[0].contentItem, m2 = trouver(f2, "nc-widget-meteo"), u2 = trouver(f2, "nc-widget-musique")
    verifier(m2.visible && m2.width > 0 && m2.width === m2.height, "météo dans une carte ronde")
    verifier(u2.visible && u2.y >= m2.y + m2.height, "musique dessous")
    Qt.quit() }
""", taille=(2464, 1456))

    def test_points_separateur_en_deux_disques(self):
        self.executer({"WIDGETS_BUREAU": "oui", "WIDGETS_THEME": "horloge-geante:haut-gauche:grand::points"}, """
  if (etape === 1 || etape === 2) { etape++; return }
  if (etape === 3) { var g = trouver(w.fenetres[0].contentItem, "nc-widget-horloge-geante"), s = tous(g, "nc-chiffres-separateur")
    verifier(g.visible && s.length === 2, "deux points : " + s.length)
    for (var i = 0; i < 2; i++) verifier(s[i].visible && s[i].width > 4 && s[i].width === s[i].height && s[i].radius === s[i].width / 2, "un disque")
    verifier(Math.abs(s[1].y - s[0].y - 2 * s[0].parent.height / 7) < 2, "rangées 2 et 4 : " + s[0].y + " " + s[1].y)
    function texte(it) { if (it.text !== undefined && String(it.text).indexOf(":") >= 0) return true
      for (var j = 0; j < it.children.length; j++) if (texte(it.children[j])) return true; return false }
    verifier(!texte(g), "aucun glyphe « : »")
    Qt.quit() }
""", taille=(2464, 1456))

    def test_aiguilles_a_3_h_et_6_h_et_jauge_a_aiguille(self):
        self.executer({"WIDGETS_BUREAU": "oui", "WIDGETS_THEME": "horloge-fine:haut-gauche:moyen:carte:aiguille,jauge-aiguille:haut-droite:moyen:carte-ronde"}, """
  function pointe(nom) { var c = trouver(w.fenetres[0].contentItem, "nc-widget-horloge-fine"), a = trouver(c, nom), o = a.parent
    var p = a.mapToItem(o, a.width / 2, 0); return [p.x - o.width / 2, p.y - o.height / 2, a.height] }
  if (etape === 1) { Etat.minute = new Date(2026, 10, 22, 15, 0); etape++; return }
  if (etape === 2) { etape++; return }
  if (etape === 3) { var h = pointe("nc-aiguille-heures"), m = pointe("nc-aiguille-minutes")
    verifier(Math.abs(h[0] - h[2]) < 1.5 && Math.abs(h[1]) < 1.5, "3 h : heures à l'horizontale, à droite : " + h)
    verifier(Math.abs(m[0]) < 1.5 && Math.abs(m[1] + m[2]) < 1.5, "3 h : minutes vers le haut : " + m)
    var j = trouver(w.fenetres[0].contentItem, "nc-jauge-aiguille")
    verifier(j && j.visible && w.minuteur.running, "jauge à aiguille vue, minuteur partagé actif")
    w.cpu = 0.5; etape++; return }
  if (etape === 4) { var a = trouver(w.fenetres[0].contentItem, "nc-jauge-aiguille")
    verifier(Math.abs(a.rotation) < 0.01, "jauge à 50 % : aiguille droite : " + a.rotation)
    Etat.minute = new Date(2026, 10, 22, 18, 0); etape++; return }
  if (etape === 5) { w.cpu = 0; etape++; return }          // après le relevé de la minute
  if (etape === 6) { var h2 = pointe("nc-aiguille-heures")
    verifier(Math.abs(h2[0]) < 1.5 && Math.abs(h2[1] - h2[2]) < 1.5, "6 h : heures vers le bas : " + h2)
    verifier(Math.abs(trouver(w.fenetres[0].contentItem, "nc-jauge-aiguille").rotation + 90) < 0.01, "jauge à 0 : à gauche")
    Qt.quit() }
""", taille=(2464, 1456))

    def test_musique_cachee_quand_rien_ne_joue(self):
        self.executer({"WIDGETS_BUREAU": "oui", "WIDGETS_THEME": "musique:haut-gauche:moyen:carte,musique:bas-gauche:moyen:carte::bandeau"}, """
  function vus() { return tous(w.fenetres[0].contentItem, "nc-widget-musique").filter(m => m.visible && m.implicitWidth > 0).length }
  if (etape === 1) { verifier(vus() === 0, "rien en lecture : aucune carte")
    Etat.aMusique = true; Etat.titre = "T"; Etat.joue = false; etape++; return }
  if (etape === 2) { verifier(vus() === 0, "en pause : aucune carte (jamais de pochette vide)"); Etat.joue = true; etape++; return }
  if (etape === 3) { etape++; return }
  if (etape === 4) { verifier(vus() === 2, "en lecture : les deux cartes : " + vus()); Etat.aMusique = false; etape++; return }
  if (etape === 5) { verifier(vus() === 0, "fini : plus rien"); Qt.quit() }
""", taille=(2464, 1456))

    def test_widgets_police_repli_et_petits_textes(self):
        self.executer({"WIDGETS_BUREAU": "oui", "WIDGETS_THEME": "date:centre:moyen"}, """
  var f = Qt.fontFamilies()
  if (etape === 1) { verifier(w.police === "Mono" && w.policePetite === "Mono", "vide : la police de l'île : " + w.police)
    Reglages.valeurs = { WIDGETS_BUREAU: "oui", WIDGETS_THEME: "date:centre:moyen", WIDGETS_POLICE: "Absente, " + f[0] }; etape++; return }
  if (etape === 2) { verifier(w.police === f[0] && w.policePetite === f[0], "repli : la première installée : " + w.police)
    Reglages.valeurs = { WIDGETS_BUREAU: "oui", WIDGETS_THEME: "date:centre:moyen", WIDGETS_POLICE: f[0] + ", Absente, " + f[1] }; etape++; return }
  if (etape === 3) { verifier(w.police === f[0] && w.policePetite === f[1], "petits textes : la suivante installée : " + w.policePetite)
    Reglages.valeurs = { WIDGETS_BUREAU: "oui", WIDGETS_THEME: "date:centre:moyen", WIDGETS_POLICE: "Absente, Autre" }; etape++; return }
  if (etape === 4) { verifier(w.police === "Mono", "aucune installée : la police de l'île"); Qt.quit() }
""")

    # ── Lisibilité : rendu hors écran à l'échelle 1,6 (2560 × 1600 → 1600 × 1000 logiques, marges ôtées), taille « petit » ──
    def mesurer(self, theme, fond):
        self.executer({"WIDGETS_BUREAU": "oui", "WIDGETS_THEME": theme}, """
  if (etape === 1) { Etat.meteo = { temp: 13, icone: "cloud", texte: "Nuageux", min: 8, max: 13 }; Etat.meteoPilule = true
    Etat.aMusique = true; Etat.joue = true; Etat.titre = "Titre"; Etat.artiste = "Artiste"; w.cpu = 0.42; etape++; return }
  if (etape === 2 || etape === 3) { etape++; return }
  if (etape === 4) { etape = 10
    var f = w.fenetres[0].contentItem, textes = [], objets = [], widgets = 0
    function parcourir(it) { if (!it.visible) return
      if (it.widget !== undefined && it.width > 0) widgets++
      if (it.font !== undefined && it.text !== undefined && String(it.text) !== "" && it.width > 0) { var p = it.mapToItem(f, 0, 0)
        textes.push({ x: p.x, y: p.y, l: it.width, h: it.height, c: String(it.color), px: it.font.pixelSize, t: String(it.text) }); objets.push(it) }
      for (var i = 0; i < it.children.length; i++) parcourir(it.children[i]) }
    parcourir(f)
    console.log("MESURE " + JSON.stringify({ widgets: widgets, textes: textes }))
    for (var j = 0; j < objets.length; j++) objets[j].opacity = 0       // le fond seul, sous chaque texte
    f.grabToImage(function (r) { verifier(r.saveToFile("DOSSIER/fond.png"), "capture"); Qt.quit() }) }
""", taille=(1504, 856), captures=("fond",), fond=fond)
        ligne = [l for l in self.sortie.splitlines() if "MESURE " in l][-1]
        return json.loads(ligne[ligne.index("MESURE ") + 7:]), self.images["fond"]

    def verifier_lisible(self, theme, fond, nombre):
        mesure, img = self.mesurer(theme, fond)
        self.assertEqual(mesure["widgets"], nombre, "tous les widgets montrés")
        largeur, hauteur, bpp, lignes = img

        def lum(c):
            f = [(x / 255 / 12.92 if x / 255 <= 0.04045 else ((x / 255 + 0.055) / 1.055) ** 2.4) for x in c[:3]]
            return 0.2126 * f[0] + 0.7152 * f[1] + 0.0722 * f[2]
        self.assertGreater(len(mesure["textes"]), nombre)
        for t in mesure["textes"]:
            couleur = tuple(int(t["c"][i:i + 2], 16) for i in (len(t["c"]) - 6, len(t["c"]) - 4, len(t["c"]) - 2))
            pires = []
            for fx, fy in ((0.5, 0.5), (0.3, 0.35), (0.7, 0.65)):
                x, y = min(largeur - 1, int(t["x"] + t["l"] * fx)), min(hauteur - 1, int(t["y"] + t["h"] * fy))
                px = lignes[y][x * bpp:(x + 1) * bpp]
                a, b = lum(couleur), lum(px)
                pires.append((max(a, b) + 0.05) / (min(a, b) + 0.05))
            with self.subTest(texte=t["t"], fond=fond):
                self.assertGreaterEqual(min(pires), 4.5, f"{t['t']!r} {t['c']} : contraste {min(pires):.2f}")
                self.assertGreaterEqual(t["px"], 11, f"{t['t']!r} : {t['px']} px")

    def test_lisible_sur_les_cartes(self):
        self.verifier_lisible("horloge-geante:haut-gauche:petit:carte,date:haut-droite:petit:carte-ronde,meteo:haut-droite:petit:carte-ronde,"
                              "anneau:haut-droite:petit:carte-ronde,jauge-aiguille:bas-droite:petit:carte-ronde,musique:bas-droite:petit:carte,"
                              "jauges:bas-gauche:petit:carte,calendrier:bas-gauche:petit:carte", "#101010", 8)

    def test_lisible_sans_carte_sur_fond_clair_et_sombre(self):
        theme = ("horloge-geante:haut-gauche:petit,accueil:haut-gauche:petit,date:haut-droite:petit,meteo:haut-droite:petit,"
                 "anneau:bas-droite:petit,musique:bas-gauche:petit,calendrier:bas-gauche:petit:texte::ligne,horloge-mots:centre:petit")
        for fond in ("#f4f4f4", "#ffffff", "#0b0b0b", "#808080"):
            self.verifier_lisible(theme, fond, 8)


class Doto(unittest.TestCase):
    """install.sh : la police Doto téléchargée comme Material Symbols (question, ~/.local/share/fonts, fc-cache), à un
    commit figé du dépôt google/fonts, gardée seulement avec la bonne empreinte. Le bloc est lancé seul, faux curl."""
    def bloc(self):
        s = (H.REPO / "install.sh").read_text(encoding="utf-8")
        return s[s.index("  # Police à points Doto"):s.index("\nelif have qs; then")]

    def test_url_figee_et_empreinte(self):
        b = self.bloc()
        self.assertRegex(b, r"DOTO_URL='https://raw\.githubusercontent\.com/google/fonts/[0-9a-f]{40}/ofl/doto/Doto%5BROND,wght%5D\.ttf'")
        self.assertRegex(b, r"\n  DOTO_SHA256=[0-9a-f]{64}\n")
        self.assertIn("Open Font License", b)
        self.assertIn('fc-cache -f "$(dirname "$POLICE_DOTO")"', b)

    def lancer(self, reponse, curl_code=0, bon=True):
        with tempfile.TemporaryDirectory(prefix="nc-doto-") as d:
            racine = Path(d)
            (racine / "bin").mkdir(); (racine / "home").mkdir()
            for nom, corps in (("curl", 'o=""; while [ $# -gt 0 ]; do [ "$1" = -o ] && o="$2"; shift; done\n'
                                        '[ %d -eq 0 ] || exit %d\nprintf "faux-doto" > "$o"' % (curl_code, curl_code)),
                               ("fc-list", "exit 0"), ("fc-cache", 'echo "fc-cache $*" >> "$HOME/journal"')):
                (racine / "bin" / nom).write_text("#!/bin/sh\n" + corps + "\n"); (racine / "bin" / nom).chmod(0o755)
            bloc = self.bloc()
            if bon:     # la même logique, avec l'empreinte du faux fichier
                bloc = re.sub(r"DOTO_SHA256=[0-9a-f]{64}", "DOTO_SHA256=" + hashlib.sha256(b"faux-doto").hexdigest(), bloc)
            script = ('t() { printf "%s" "$1"; }; info() { echo "INFO $*"; }; ok() { echo "OK $*"; }; warn() { echo "WARN $*"; }\n'
                      'have() { command -v "$1" >/dev/null 2>&1; }; ask() { [ "$REPONSE" = o ]; }\n'
                      "ILE=quickshell; FAMILY=arch; MODE=full\nif true; then\n" + bloc + "\nfi\n")
            env = {"PATH": f"{racine}/bin:/usr/bin:/bin", "HOME": str(racine / "home"), "TMPDIR": str(racine), "REPONSE": reponse}
            r = subprocess.run(["bash", "-c", script], env=env, capture_output=True, text=True, timeout=30, check=False)
            police = racine / "home/.local/share/fonts/Doto.ttf"
            restes = sorted(x.name for x in police.parent.iterdir()) if police.parent.exists() else []
            journal = (racine / "home/journal").read_text() if (racine / "home/journal").exists() else ""
            return r, police.exists(), restes, journal

    def test_oui_installe_puis_fc_cache(self):
        r, ok, restes, journal = self.lancer("o")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(ok, r.stdout + r.stderr)
        self.assertEqual(restes, ["Doto.ttf"])
        self.assertIn("fc-cache -f", journal)

    def test_mauvaise_empreinte_sans_reseau_ou_refus_rien_ne_casse(self):
        for cas in ({"reponse": "o", "bon": False}, {"reponse": "o", "curl_code": 6}, {"reponse": "n"}):
            with self.subTest(**cas):
                r, ok, restes, journal = self.lancer(**cas)
                self.assertEqual(r.returncode, 0, r.stderr)
                self.assertFalse(ok)
                self.assertEqual(restes, [], "aucun fichier à moitié téléchargé")
                self.assertEqual(journal, "")
                if cas["reponse"] == "o":
                    self.assertIn("WARN", r.stdout)


if __name__ == "__main__":
    unittest.main()

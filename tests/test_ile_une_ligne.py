"""Île Émail sur une seule ligne (décisions du 24/11, docs/superpowers/specs/2026-11-25-refonte-ile-lanceur-goutte-decisions.md,
points 2 à 4) : au repos, une ligne à la hauteur des pastilles de la barre (pochette, titre, lecture / pause) ; le volume
remplace un instant ce contenu puis le rend ; au survol, l'île grandit un peu (loupe, progression du morceau) et se replie
quand le curseur sort, sans jamais ouvrir ni les pages ni la recherche.
Les essais de comportement tournent hors écran dans une copie de l'île (outils/rendu-ile.py), jamais à l'écran."""
from tests import _isolation  # noqa: F401  (HOME, XDG_*, langue : avant tout le reste)
import importlib.util
import json
from pathlib import Path
import re
import shutil
import tempfile
import unittest

DEPOT = Path(__file__).resolve().parents[1]
QML = DEPOT / "home/.config/quickshell/nc-ile"


def charger_rendu():
    spec = importlib.util.spec_from_file_location("rendu_ile_une_ligne", DEPOT / "outils/rendu-ile.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


# Pilote : des étapes à heure fixe, chacune note l'île (taille, contenu, ouverte ou non) dans le journal
ETAPES = """
    var f = vs.instances[0], i = f.ilot, k = i.children, c = null, s = null
    for (var n = 0; n < k.length; n++) {
        if (k[n].largeur !== undefined && k[n].actif !== undefined) c = k[n]
        if (k[n].largeurEnPlus !== undefined) s = k[n]
    }
    function note(nom) {
        console.log("ETAPE " + JSON.stringify({ nom: nom, h: i.height, w: i.width, ligne: f.ligne, mode: c.mode,
            ouverte: Etat.ecranOuvert, recherche: Etat.recherche, survol: s.opacity, loupe: s.surLoupe(i.width - 20, f.ligne / 2),
            ancre: f._ancreGestes, largeur: c.largeur, ecran: f.modelData.width }))
    }
    function plus(ms, fn) { Qt.createQmlObject('import QtQuick; Timer { interval: ' + ms + '; running: true }', racine).triggered.connect(fn) }
    note("repos")
    f.survolTenu = true
    note("survol-tout-de-suite")
    plus(1300, function() { note("survol") })
    plus(1400, function() { f.survolTenu = false; note("sortie-tout-de-suite") })
    plus(2600, function() { note("replie"); Etat.pret = true; Etat.activite("volume", 900) })
    plus(2700, function() { note("volume") })
    plus(4200, function() { note("apres-volume") })
"""


@unittest.skipUnless(shutil.which("qs"), "Quickshell (qs) absent")
class UneLigne(unittest.TestCase):
    def setUp(self):
        self.t = Path(tempfile.mkdtemp(prefix="nct-ligne-"))
        self.addCleanup(shutil.rmtree, str(self.t), True)

    def etapes(self, reglages):
        m = charger_rendu()
        m.ACTIONS["musique"] = ETAPES
        m.ATTENTE = 4600
        conf = self.t / "reglages.conf"
        conf.write_text(reglages)
        png, journal = m.rendre("musique", str(self.t), str(conf), None)
        self.assertIsNotNone(png, journal[-1500:])
        e = {d["nom"]: d for d in (json.loads(x) for x in re.findall(r"ETAPE (\{.*?\})\n", journal))}
        self.assertEqual(len(e), 7, journal[-1500:])
        return e

    def test_repos_survol_et_volume(self):
        e = self.etapes("")
        repos = e["repos"]
        # au repos : une ligne de la barre de base (30), la musique dedans
        self.assertEqual(repos["ligne"], 30)
        self.assertEqual(repos["h"], 30)
        self.assertEqual(repos["mode"], "musique")
        self.assertFalse(repos["loupe"], "la loupe n'existe pas hors survol")
        # ancre de la goutte (plugin nc-gestes) : la ligne au repos, centrée ; le survol ne la change pas
        self.assertEqual(repos["ancre"].split()[1:], ["%d" % round((repos["ecran"] - repos["largeur"]) / 2), "9", "%d" % round(repos["largeur"]), "30"])
        self.assertEqual(e["survol"]["ancre"], repos["ancre"])
        # survol : l'île grandit un peu (progression dessous, loupe au bout de la ligne), avec ses ressorts
        self.assertLess(e["survol-tout-de-suite"]["h"], 40, "le ressort part de la ligne, pas d'un saut")
        s = e["survol"]
        self.assertGreater(s["h"], repos["h"] + 20)
        self.assertLess(s["h"], 90, "un peu plus grande, pas une page")
        self.assertGreater(s["w"], repos["w"] + 30)
        self.assertEqual(s["survol"], 1)
        self.assertTrue(s["loupe"], "la loupe est au bout de la ligne")
        # le survol seul n'ouvre rien : ni les pages ni la recherche
        for nom in ("survol-tout-de-suite", "survol", "replie"):
            self.assertEqual(e[nom]["ouverte"], "", nom)
            self.assertFalse(e[nom]["recherche"], nom)
        # sortie : l'île se replie sur sa ligne
        self.assertEqual(e["replie"]["h"], 30)
        self.assertAlmostEqual(e["replie"]["w"], repos["w"], delta=0.5)
        self.assertEqual(e["replie"]["survol"], 0)
        # le volume remplace la musique un instant, sur la même ligne, puis la rend
        self.assertEqual(e["volume"]["mode"], "volume")
        self.assertEqual(e["volume"]["h"], 30)
        self.assertEqual(e["apres-volume"]["mode"], "musique")
        self.assertEqual(e["apres-volume"]["h"], 30)

    def test_ligne_de_la_barre_et_aucune_animation(self):
        """ILE_LIGNE (nc-reglages, pastilles de la barre du haut) donne la hauteur au repos ; sans animation pour cet
        écran (ILE_ANIM_ECRANS … :aucun), le survol agrandit et replie l'île tout de suite, sans ressort."""
        e = self.etapes("ILE_LIGNE=34\nILE_ANIM_ECRANS=ecran-rendu:aucun\n")
        self.assertEqual(e["repos"]["ligne"], 34)
        self.assertEqual(e["repos"]["h"], 34)
        self.assertTrue(e["repos"]["ancre"].endswith(" 34"), e["repos"]["ancre"])
        self.assertGreater(e["survol-tout-de-suite"]["h"], 34 + 20)
        self.assertEqual(e["survol-tout-de-suite"]["survol"], 1)
        self.assertEqual(e["sortie-tout-de-suite"]["h"], 34)
        self.assertEqual(e["volume"]["h"], 34)

    def test_la_bande_garde_30(self):
        e = self.etapes("ILE_LIGNE=34\nILE_BANDE=oui\n")
        self.assertEqual(e["repos"]["h"], 30)


# Pilote du repos sans musique : la pilule, ses textes visibles, puis un point de notification, puis un clic
REPOS = """
    var f = vs.instances[0], i = f.ilot, k = i.children, c = null
    for (var n = 0; n < k.length; n++) if (k[n].largeur !== undefined && k[n].actif !== undefined) c = k[n]
    function textes(item, l) {
        l = l || []
        if (!item.visible || item.opacity <= 0.01) return l
        if (item.text !== undefined && item.font !== undefined && item.font.family !== "Material Symbols Rounded" && item.text !== "") l.push(item.text)
        for (var j = 0; j < item.children.length; j++) textes(item.children[j], l)
        return l
    }
    function point() { var r = trouver(c, "nc-notifs-pill-point"); return r !== null && r.visible }
    function note(nom) {
        console.log("ETAPE " + JSON.stringify({ nom: nom, mode: c.mode, largeur: c.largeur, h: i.height, ligne: f.ligne,
            textes: textes(c.actif), heure: Etat.heure, date: Etat.dateCourte, point: point(),
            ouverte: Etat.ecranOuvert, recherche: Etat.recherche, vue: Etat.vueActive }))
    }
    function trouver(item, nom) { if (item.objectName === nom) return item; for (var j = 0; j < item.children.length; j++) { var r = trouver(item.children[j], nom); if (r) return r } return null }
    function plus(ms, fn) { Qt.createQmlObject('import QtQuick; Timer { interval: ' + ms + '; running: true }', racine).triggered.connect(fn) }
    note("repos")
    Notifs.revenues = [{ id: "essai-1", synthetique: true, appName: "Essai", summary: "Bonjour", body: "" }]
    plus(400, function() { note("notification") })
    plus(500, function() { f.clicPilule(); plus(1200, function() { note("clic") }) })
"""
# Clic sur la ligne musique : la page Musique si elle est affichée, sinon (lecteur factice sans « raise ») le lanceur
CLIC_MUSIQUE = """
    var f = vs.instances[0]
    f.clicPilule()
    Qt.createQmlObject('import QtQuick; Timer { interval: 1200; running: true }', racine).triggered.connect(function() {
        console.log("ETAPE " + JSON.stringify({ nom: "clic-musique", ouverte: Etat.ecranOuvert, recherche: Etat.recherche, vue: Etat.vueActive }))
    })
"""


@unittest.skipUnless(shutil.which("qs"), "Quickshell (qs) absent")
class ReposMinimal(unittest.TestCase):
    """Retour de Théo le 26/11 : sans musique, la pilule montrait encore nuage, heure, date et météo, et un clic ouvrait
    le centre de contrôle dans l'île. Au repos : une ligne courte des seuls indicateurs actifs ; un clic : le lanceur."""
    def setUp(self):
        self.t = Path(tempfile.mkdtemp(prefix="nct-repos-"))
        self.addCleanup(shutil.rmtree, str(self.t), True)

    def etapes(self, etat, pilote, attente, reglages=""):
        m = charger_rendu()
        m.ACTIONS[etat] = pilote
        m.ATTENTE = attente
        conf = self.t / "reglages.conf"
        conf.write_text(reglages)
        png, journal = m.rendre(etat, str(self.t), str(conf), None)
        self.assertIsNotNone(png, journal[-1500:])
        return {d["nom"]: d for d in (json.loads(x) for x in re.findall(r"ETAPE (\{.*?\})\n", journal))}, journal

    def test_repos_sans_heure_ni_date_ni_meteo_et_clic_vers_le_lanceur(self):
        e, journal = self.etapes("fermee", REPOS, 2400)
        self.assertEqual(set(e), {"repos", "notification", "clic"}, journal[-1500:])
        r = e["repos"]
        self.assertEqual(r["mode"], "repos")
        self.assertEqual(r["h"], r["ligne"], "une seule ligne")
        self.assertNotEqual(r["heure"], "")
        # rien de ce que la barre montre déjà : ni l'heure, ni la date, ni de température
        self.assertEqual(r["textes"], [], r)
        self.assertEqual(r["largeur"], 64, "sans indicateur : une petite pilule")
        self.assertFalse(r["point"])
        # une notification non lue : un point discret, la pilule reste courte
        n = e["notification"]
        self.assertTrue(n["point"])
        self.assertEqual(n["textes"], [])
        self.assertLessEqual(n["largeur"], 64)
        # clic sur la pilule au repos : le lanceur depuis l'île, jamais une page ni le centre de contrôle
        c = e["clic"]
        self.assertNotEqual(c["ouverte"], "")
        self.assertTrue(c["recherche"], c)

    def test_clic_musique_page_si_affichee_sinon_lanceur(self):
        e, journal = self.etapes("musique", CLIC_MUSIQUE, 1600)
        self.assertEqual(e["clic-musique"]["vue"], "musique", journal[-1500:])
        self.assertFalse(e["clic-musique"]["recherche"])
        self.assertNotEqual(e["clic-musique"]["ouverte"], "")
        e, journal = self.etapes("musique", CLIC_MUSIQUE, 1600, "ILE_PAGE_MUSIQUE=non\n")
        self.assertTrue(e["clic-musique"]["recherche"], journal[-1500:])


class Source(unittest.TestCase):
    def setUp(self):
        self.ile = (QML / "Ile.qml").read_text(encoding="utf-8")
        self.survol = (QML / "SurvolIle.qml").read_text(encoding="utf-8")

    def test_le_survol_n_ouvre_rien(self):
        bloc = self.ile[self.ile.index("HoverHandler {"):self.ile.index("Behavior on color")]
        for appel in ("Etat.basculer", "Etat.chercher", "Etat.aller"):
            self.assertNotIn(appel, bloc)
        self.assertNotIn("parSurvol", self.ile)
        # seul le clic sur la loupe ouvre la recherche, depuis l'île (même chemin que Super + R)
        self.assertIn("(survolIle.surLoupe(e.x, e.y) ? Etat.chercher(fen.modelData.name)", self.ile)

    def test_le_clic_n_ouvre_plus_le_centre_de_controle(self):
        clic = self.ile[self.ile.index("onClicked: e => e.button === Qt.RightButton"):self.ile.index("onWheel: w => Etat.reglerVolume")]
        self.assertNotRegex(clic, r"\bEtat\.basculer\(")
        self.assertNotRegex(self.ile, r"\bEtat\.basculer\(", "ni la pilule ni sa bulle n'ouvrent le centre de contrôle")
        self.assertIn("(Agents.ouvrirAttente(fen.modelData.name) || fen.clicPilule())", clic)
        f = self.ile[self.ile.index("function clicPilule()"):]
        f = f[:f.index("\n    }\n")]
        self.assertNotIn("basculer", f)
        self.assertIn("Etat.chercher(modelData.name)", f)
        # Super + C et l'IPC « ouvrir » / « page » restent, en attendant le panneau de #60
        shell = (QML / "shell.qml").read_text(encoding="utf-8")
        self.assertIn("function basculer(): void { Etat.basculer(", shell)
        self.assertIn("function page(nom: string): void {", shell)

    def test_repos_sans_doublon_de_la_barre(self):
        compact = (QML / "Compact.qml").read_text(encoding="utf-8")
        repos = compact[compact.index("        id: repos\n"):compact.index("    // ── Musique")]
        for absent in ("Etat.heure", "Etat.dateCourte", "Etat.meteo", "ILE_DATE"):
            self.assertNotIn(absent, repos)
        for present in ('objectName: "nc-vpn-pill"', 'objectName: "nc-mode-pill"', 'objectName: "nc-notifs-pill-point"'):
            self.assertIn(present, repos)

    def test_surface_assez_haute_au_survol(self):
        # la progression dépasse la bande de 56 px : la surface grandit comme pour une bannière
        self.assertIn("readonly property bool grandeVoulue: ouverte || banniere || enCarte || hauteurSurvol > 0", self.ile)

    def test_fondu_du_survol_suit_mouvement(self):
        self.assertIn("Behavior on opacity { enabled: s.mouv.actif; NumberAnimation { duration: s.mouv.dureeCourte", self.survol)
        self.assertIn("mouv: fen.mouv", self.ile)
        # rien d'image par image : ni Timer rapide, ni animation sans fin
        self.assertNotIn("Animation.Infinite", self.survol)
        self.assertEqual(re.findall(r"interval: (\d+)", self.survol), ["1000"])

    def test_email_par_les_couleurs_du_theme(self):
        couleurs = (QML / "Couleurs.qml").read_text(encoding="utf-8")
        self.assertIn("readonly property color emailLumiere:", couleurs)
        self.assertIn("readonly property color emailReflet: Qt.tint(fond,", couleurs)
        self.assertIn("GradientStop { position: 0.46; color: Couleurs.emailReflet }", self.ile)
        self.assertIn("opacity: fen.ouverte ? 0 : 1", self.ile)     # pages ouvertes : leur fond d'avant


if __name__ == "__main__":
    unittest.main()

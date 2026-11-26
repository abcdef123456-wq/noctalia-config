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
        # ancre de la goutte (plugin nc-gestes) : la ligne au repos, centrée, puis l'émail dont la goutte est faite
        # (surface de la pilule, accent) ; le survol ne la change pas
        self.assertEqual(repos["ancre"].split()[1:5], ["%d" % round((repos["ecran"] - repos["largeur"]) / 2), "9", "%d" % round(repos["largeur"]), "30"])
        self.assertRegex(" ".join(repos["ancre"].split()[5:]), r"^#[0-9a-f]{6} #[0-9a-f]{6}$")
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
        self.assertEqual(e["repos"]["ancre"].split()[4], "34", e["repos"]["ancre"])
        self.assertGreater(e["survol-tout-de-suite"]["h"], 34 + 20)
        self.assertEqual(e["survol-tout-de-suite"]["survol"], 1)
        self.assertEqual(e["sortie-tout-de-suite"]["h"], 34)
        self.assertEqual(e["volume"]["h"], 34)

    def test_la_bande_garde_30(self):
        e = self.etapes("ILE_LIGNE=34\nILE_BANDE=oui\n")
        self.assertEqual(e["repos"]["h"], 30)


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

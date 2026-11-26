"""Ouverture et fermeture du Spotlight (Ile.qml) : l'île n'est jamais une forme vide pendant que le ressort l'étire.
Le contenu de la recherche apparaît avec la largeur de l'île et la pilule (Compact) ne s'efface qu'à mesure, image par
image, sans animation de plus (rien de plus lent). Les formules sont lues dans Ile.qml puis évaluées largeur par largeur."""
from pathlib import Path
import re
import unittest

ILE = Path(__file__).resolve().parents[1] / "home/.config/quickshell/nc-ile/Ile.qml"


class Spotlight(unittest.TestCase):
    def setUp(self):
        self.src = ILE.read_text()
        m = re.search(r"readonly property real etirementRecherche: Math\.max\(0, Math\.min\(1, \(width - (\d+)\) / (\d+)\)\)", self.src)
        self.assertIsNotNone(m, "formule de l'étirement introuvable")
        self.debut, self.etendue = int(m.group(1)), int(m.group(2))

    def etirement(self, largeur):
        return max(0.0, min(1.0, (largeur - self.debut) / self.etendue))

    def compact(self, largeur, recherche=False, retour_spot=False, depuis_pilule=True, repos=1):
        """Opacité de la pilule, selon la formule de Ile.qml (repos : ce qu'elle vaut hors Spotlight)."""
        if recherche:
            return 1 - self.etirement(largeur) if depuis_pilule else 0.0
        return 1 - self.etirement(largeur) if retour_spot else repos

    def contenu(self, largeur, recherche=False, retour_spot=False):
        return self.etirement(largeur) if recherche or retour_spot else 0.0

    def test_formules_exactes(self):
        self.assertIn("opacity: fen.recherche ? (fen.spotDepuisPilule ? 1 - ile.etirementRecherche : 0)", self.src)
        self.assertIn("(ile.retourSpot ? 1 - ile.etirementRecherche : (fen.ouverte || fen.banniere || fen.enCarte ? 0 : 1))", self.src)
        self.assertIn("Behavior on opacity { enabled: !Notifs.enPause && !fen.recherche && !ile.retourSpot; NumberAnimation", self.src)
        # D-A : le contenu est multiplié par fonduSpot (1 hors entrée depuis une page) ; les valeurs d'étirement sont inchangées
        self.assertIn("opacity: fen.recherche || ile.retourSpot ? ile.etirementRecherche * fen.fonduSpot : 0", self.src)
        self.assertIn("NumberAnimation { duration: fen.ouverte || fen.banniere || fen.enCarte ? 90 : 220; easing.type: Easing.OutCubic", self.src)
        self.assertNotIn("apparitionRecherche", self.src)
        self.assertNotIn("ile.width > 560", self.src)

    def test_ouverture_jamais_vide(self):
        # Le ressort part de la pilule (110 à 260 px), dépasse la cible de 438 px puis y revient
        for largeur in list(range(110, 481, 5)) + list(range(480, 437, -2)):
            compact, recherche = self.compact(largeur, recherche=True), self.contenu(largeur, recherche=True)
            self.assertAlmostEqual(compact + recherche, 1.0, msg=f"{largeur} px")
            self.assertGreaterEqual(max(compact, recherche), 0.5, f"{largeur} px : forme presque vide")
        self.assertEqual(self.contenu(438, recherche=True), 1.0, "lanceur entier à sa taille")
        self.assertEqual(self.contenu(200, recherche=True), 0.0, "pilule entière au départ")
        self.assertLessEqual(self.debut + self.etendue, 420, "le lanceur est entier avant sa taille finale (438 px)")
        self.assertIn("Qt.size(438, spot.hauteurVoulue)", self.src)

    def test_fermeture_jamais_vide(self):
        # Fermeture : l'île rétrécit de 438 vers la pilule ; pilule et lanceur suivent la largeur, comme à l'ouverture
        for largeur in list(range(438, 109, -2)) + list(range(110, 261, 5)):
            compact, recherche = self.compact(largeur, retour_spot=True), self.contenu(largeur, retour_spot=True)
            self.assertGreaterEqual(max(compact, recherche), 0.5, f"{largeur} px : capsule noire vide")
        self.assertEqual(self.compact(200, retour_spot=True), 1.0, "pilule entière à l'arrivée (aucun saut au repos)")
        self.assertEqual(self.compact(438, retour_spot=True), 0.0)

    def test_retour_spot_seulement_vers_la_pilule(self):
        self.assertIn("readonly property bool retourSpot: retourRecherche.running && !fen.ouverte", self.src)
        # Une page choisie depuis le Spotlight : l'île reste ouverte, pas de pilule par-dessus la page
        self.assertEqual(self.compact(500, retour_spot=False, repos=0), 0.0)

    def test_super_r_sur_une_page_ouverte_pas_de_clignotement(self):
        # Comparée à la largeur de la pilule : une pilule à titre et artiste dépasse 300 px, et reste une pilule
        self.assertIn("spotDepuisPilule = ile.width <= compact.largeur + 1", self.src)
        for largeur in (432, 440, 460):
            for l in range(largeur, 481, 10):
                self.assertEqual(self.compact(l, recherche=True, depuis_pilule=False), 0.0, f"{l} px : l'heure ne revient pas")

    @staticmethod
    def sortie_cubique(x):
        x = max(0.0, min(1.0, x))
        return 1 - (1 - x) ** 3

    def lire_duree(self, motif):
        m = re.search(motif, self.src)
        self.assertIsNotNone(m, motif)
        return int(m.group(1))

    def test_entree_depuis_une_page_le_contenu_part_de_zero(self):
        """D-A : page -> Spotlight. La page sort en 80 ms, le contenu monte en 170 ms depuis 0 ; calcul image par image."""
        sortie_page = self.lire_duree(r"duration: fen\.ouverte && !fen\.recherche \? 200 : (\d+);")
        self.assertRegex(self.src, r"id: entreeSpot;[^\n]*duration: fen\.mouv\.dureeSpot;")   # 170 ms par défaut (Mouvement)
        entree = 170
        self.assertIn("if (!spotDepuisPilule && !Notifs.enPause && fen.mouv.actif) { fonduSpot = 0; entreeSpot.start() }", self.src)
        self.assertIn("entreeSpot.stop(); fonduSpot = 1", self.src)   # Échap, Super + R deux fois, pilule : retour à 1
        self.assertIn('id: entreeSpot;', self.src)
        self.assertRegex(self.src, r"id: entreeSpot;[^\n]*easing\.type: Easing\.InOutQuad")
        quad = lambda x: (lambda x: 2 * x * x if x < 0.5 else 1 - (-2 * x + 2) ** 2 / 2)(max(0.0, min(1.0, x)))
        # 432 px, bannière ou carte (0,6), page de 560 px ou plus (1)
        for etir in (self.etirement(432), 0.6, self.etirement(560), 1.0):
            spot = lambda t: etir * quad(t / entree)
            page = lambda t: 1 - self.sortie_cubique(t / sortie_page)
            self.assertEqual(spot(0), 0.0, "le contenu part de 0 à t = 0")
            self.assertLessEqual(page(0), 1.0)
            for t in (0, 50, 100, 200):
                self.assertLessEqual(spot(t) + page(t) - 1.0, 0.35 + 1e-9, f"{t} ms : empilement page + Spotlight")
            premier = next(t for t in range(0, 300) if spot(t) > 0.5 or t == 299)
            self.assertLess(page(min(premier, 299)), 0.1, "la page est presque partie avant que le Spotlight dépasse 0,5")

    def test_sortie_vers_une_page_le_contenu_se_fond(self):
        """D-C et D-B : Spotlight -> page, bannière ou carte. 120 ms au lieu d'un saut, sans toucher au retour pilule."""
        duree = self.lire_duree(r"Behavior on opacity \{ enabled: !Notifs\.enPause && !fen\.recherche && !ile\.retourSpot; NumberAnimation \{ duration: (\d+);")
        self.assertEqual(duree, 120)
        etir = 0.6
        valeurs = [etir * (1 - self.sortie_cubique(t / duree)) for t in (0, 50, 100, 200)]
        self.assertAlmostEqual(valeurs[0], etir)
        self.assertEqual(valeurs[3], 0.0)
        self.assertTrue(all(a > b for a, b in zip(valeurs, valeurs[1:3])), "baisse continue")
        # Le chargeur reste actif pendant le fondu (pleinEcran tient 900 ms), le Behavior se coupe pendant retourSpot
        self.assertIn("active: fen.recherche || fen.pleinEcran || occupe", self.src)
        self.assertIn("readonly property bool pleinEcran: recherche || retourRecherche.running", self.src)

    def test_contour_fondu_de_fermeture(self):
        m = re.search(r"id: cadre\n(.*?)gradient:", self.src, re.S)
        self.assertIsNotNone(m)
        cadre = m.group(1)
        self.assertNotIn("visible: e > 0", cadre)
        # Sans contour : rien de dessiné, sinon le dégradé reste sous l'île, de sa taille exacte
        # (pilule fermée : seulement avec ILE_CONTOUR_FERMEE=oui, et pas quand le lanceur part d'elle)
        self.assertIn("opacity: Couleurs.aContour && e > 0 && (fen.ouverte || fen.banniere || fen.enCarte"
                      " || (Couleurs.contourFermee && !fen.pilCachee)) ? 1 : 0", cadre)
        self.assertIn("visible: opacity > 0.01", cadre)
        self.assertIn("readonly property real e: Couleurs.aContour ? Couleurs.epaisseur : 0", cadre)
        self.assertIn("Behavior on opacity { enabled: !Notifs.enPause && fen.mouv.actif; NumberAnimation { duration: fen.mouv.dureeContour } }", cadre)

    def test_point_et_bulle_attendent_la_fin_du_retour(self):
        for nom in ("pointPrive", "bulle"):
            m = re.search(r"id: " + nom + r"\n(.*?)\n        x:", self.src, re.S)
            self.assertIsNotNone(m, nom)
            montre = m.group(1)[m.group(1).index("readonly property bool montre"):]
            self.assertIn("!retour.running && !retourRecherche.running", montre, nom)
            self.assertIn("!fen.ouverte", montre, nom)


if __name__ == "__main__":
    unittest.main()

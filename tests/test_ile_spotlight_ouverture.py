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
        self.assertIn("opacity: fen.recherche || ile.retourSpot ? ile.etirementRecherche : 0", self.src)
        self.assertIn("NumberAnimation { duration: fen.ouverte || fen.banniere || fen.enCarte ? 90 : 220; easing.type: Easing.OutCubic", self.src)
        self.assertNotIn("apparitionRecherche", self.src)
        self.assertNotIn("ile.width > 560", self.src)

    def test_ouverture_jamais_vide(self):
        # Le ressort part de la pilule (110 à 260 px), dépasse la cible de 680 px puis y revient
        for largeur in list(range(110, 721, 5)) + list(range(720, 679, -5)):
            compact, recherche = self.compact(largeur, recherche=True), self.contenu(largeur, recherche=True)
            self.assertAlmostEqual(compact + recherche, 1.0, msg=f"{largeur} px")
            self.assertGreaterEqual(max(compact, recherche), 0.5, f"{largeur} px : forme presque vide")
        self.assertEqual(self.contenu(680, recherche=True), 1.0, "Spotlight entier à sa taille")
        self.assertEqual(self.contenu(200, recherche=True), 0.0, "pilule entière au départ")
        self.assertLessEqual(self.debut + self.etendue, 600, "le Spotlight est entier avant sa taille finale")

    def test_fermeture_jamais_vide(self):
        # Fermeture : l'île rétrécit de 680 vers la pilule ; pilule et Spotlight suivent la largeur, comme à l'ouverture
        for largeur in list(range(680, 109, -5)) + list(range(110, 261, 5)):
            compact, recherche = self.compact(largeur, retour_spot=True), self.contenu(largeur, retour_spot=True)
            self.assertGreaterEqual(max(compact, recherche), 0.5, f"{largeur} px : capsule noire vide")
        self.assertEqual(self.compact(200, retour_spot=True), 1.0, "pilule entière à l'arrivée (aucun saut au repos)")
        self.assertEqual(self.compact(680, retour_spot=True), 0.0)

    def test_retour_spot_seulement_vers_la_pilule(self):
        self.assertIn("readonly property bool retourSpot: retourRecherche.running && !fen.ouverte", self.src)
        # Une page choisie depuis le Spotlight : l'île reste ouverte, pas de pilule par-dessus la page
        self.assertEqual(self.compact(500, retour_spot=False, repos=0), 0.0)

    def test_super_r_sur_une_page_ouverte_pas_de_clignotement(self):
        self.assertIn("spotDepuisPilule = ile.etirementRecherche === 0", self.src)
        for largeur in (110, 200, 260):
            self.assertEqual(self.etirement(largeur), 0.0, "départ de la pilule : détecté")
        for largeur in (432, 440, 460):
            self.assertGreater(self.etirement(largeur), 0.0, "départ d'une page ou d'une bannière : pas la pilule")
            for l in range(largeur, 721, 10):
                self.assertEqual(self.compact(l, recherche=True, depuis_pilule=False), 0.0, f"{l} px : l'heure ne revient pas")

    def test_contour_fondu_de_fermeture(self):
        m = re.search(r"id: cadre\n(.*?)gradient:", self.src, re.S)
        self.assertIsNotNone(m)
        cadre = m.group(1)
        self.assertNotIn("visible: e > 0", cadre)
        self.assertIn("opacity: fen.ouverte || fen.banniere || fen.enCarte ? 1 : 0", cadre)
        self.assertIn("visible: opacity > 0.01", cadre)
        self.assertIn("readonly property real e: Couleurs.aContour ? 2 : 0", cadre)
        self.assertIn("Behavior on opacity { NumberAnimation { duration: 220 } }", cadre)

    def test_point_et_bulle_attendent_la_fin_du_retour(self):
        for nom in ("pointPrive", "bulle"):
            m = re.search(r"id: " + nom + r"\n(.*?)\n        x:", self.src, re.S)
            self.assertIsNotNone(m, nom)
            montre = m.group(1)[m.group(1).index("readonly property bool montre"):]
            self.assertIn("!retour.running && !retourRecherche.running", montre, nom)
            self.assertIn("!fen.ouverte", montre, nom)


if __name__ == "__main__":
    unittest.main()

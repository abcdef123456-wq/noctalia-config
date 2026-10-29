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
        m = re.search(r"readonly property real apparitionRecherche: fen\.recherche \? Math\.max\(0, Math\.min\(1, \(width - (\d+)\) / (\d+)\)\) : 0", self.src)
        self.assertIsNotNone(m, "formule de l'apparition introuvable")
        self.debut, self.etendue = int(m.group(1)), int(m.group(2))

    def apparition(self, recherche, largeur):
        return max(0.0, min(1.0, (largeur - self.debut) / self.etendue)) if recherche else 0.0

    def test_formules_exactes(self):
        self.assertIn("opacity: fen.recherche ? 1 - ile.apparitionRecherche : (fen.ouverte || fen.banniere || fen.enCarte ? 0 : 1)", self.src)
        self.assertIn("Behavior on opacity { enabled: !Notifs.enPause && !fen.recherche; NumberAnimation", self.src)
        self.assertIn("opacity: ile.apparitionRecherche", self.src)
        self.assertIn("Behavior on opacity { enabled: !fen.recherche; NumberAnimation { duration: 70;", self.src)
        self.assertNotIn("ile.width > 560", self.src)

    def test_ouverture_jamais_vide(self):
        # Le ressort part de la pilule (110 à 260 px), dépasse la cible de 680 px puis y revient
        for largeur in list(range(110, 721, 5)) + list(range(720, 679, -5)):
            a = self.apparition(True, largeur)
            compact, recherche = 1 - a, a
            self.assertAlmostEqual(compact + recherche, 1.0, msg=f"{largeur} px")
            self.assertGreaterEqual(max(compact, recherche), 0.5, f"{largeur} px : forme presque vide")
        self.assertEqual(self.apparition(True, 680), 1.0, "Spotlight entier à sa taille")
        self.assertEqual(self.apparition(True, 200), 0.0, "pilule entière au départ")
        self.assertLessEqual(self.debut + self.etendue, 600, "le Spotlight est entier avant sa taille finale")

    def test_fermeture_la_pilule_revient_aussitot(self):
        # recherche faux : la Recherche s'efface en 70 ms, la pilule revient en 220 ms (OutCubic : la moitié en ~30 ms)
        self.assertEqual(self.apparition(False, 680), 0.0)
        self.assertRegex(self.src, r"opacity \{ enabled: !Notifs\.enPause && !fen\.recherche; NumberAnimation \{ duration: fen\.ouverte \|\| fen\.banniere \|\| fen\.enCarte \? 90 : 220; easing\.type: Easing\.OutCubic")


if __name__ == "__main__":
    unittest.main()

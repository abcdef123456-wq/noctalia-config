"""L'île ne fait pas travailler le GPU pour rien (ILE-GPU, mesuré sur une Radeon 610M à 165 Hz).
- Chaque image de l'île coûte presque autant, quelle que soit la taille de ce qui bouge (une étincelle de 16 px qui
  tournait à 165 images/s : 19 % de l'iGPU pour Quickshell, plus la recomposition de Hyprland). Les mouvements sans fin
  de la pilule, toujours affichée, suivent donc Pas.qml (30 images/s) : pas d'animation infinie, pas d'animation entre
  deux pas de l'onde sonore.
- La surface de l'île suit sa taille utile : pilule seule, une bande de 56 de haut ; ouverte, 800 x 700 ; plein écran
  seulement pour le Spotlight."""
from pathlib import Path
import re
import unittest

QML = Path(__file__).resolve().parents[1] / "home/.config/quickshell/nc-ile"


class Cadence(unittest.TestCase):
    def test_pas_a_30_images(self):
        pas = (QML / "Pas.qml").read_text()
        self.assertIn("interval: 33", pas)

    def test_pilule_sans_animation_infinie(self):
        # La pilule et ce qu'elle affiche toujours (étincelle, logos des IA)
        for nom in ("Compact.qml", "Etincelle.qml", "Ile.qml"):
            with self.subTest(nom):
                self.assertNotIn("Animation.Infinite", (QML / nom).read_text(),
                                 nom + " : un mouvement sans fin à 165 images/s ; passe par Pas.qml (30 images/s)")

    def test_onde_sans_animation_entre_deux_pas(self):
        for nom in ("Compact.qml", "Musique.qml"):
            with self.subTest(nom):
                source = (QML / nom).read_text()
                bloc = source[source.index("Etat.bandes[index]"):][:400]
                self.assertNotIn("Behavior on height", bloc, nom + " : l'onde redessinerait l'île à 165 Hz")
        etat = (QML / "Etat.qml").read_text()
        repli = etat[etat.index("property real dernierSon"):][:600]
        self.assertRegex(repli, r"interval: 33\b", "onde de repli à 30 images/s")


class Surface(unittest.TestCase):
    def setUp(self):
        self.ile = (QML / "Ile.qml").read_text()

    def test_ancrage(self):
        self.assertIn("anchors { top: true; left: fen.recherche; right: fen.recherche; bottom: fen.recherche }", self.ile)

    def test_tailles(self):
        self.assertIn("implicitHeight: grande ? 700 : 56", self.ile)
        self.assertRegex(self.ile, r"implicitWidth: Math\.min\(modelData\.width, grande \? Math\.max\(800, largeurUtile\)")
        # enCarte : demande de Claude Code ou confirmation du mode graphique (île fermée étirée en carte)
        self.assertIn("readonly property bool grandeVoulue: ouverte || banniere || enCarte", self.ile)
        self.assertIn("readonly property bool enCarte: demandeClaude || confirmGpu", self.ile)
        self.assertIn("readonly property bool grande: grandeVoulue || retour.running", self.ile)

    def test_retour_apres_le_ressort(self):
        # La surface ne rapetisse qu'une fois l'île revenue à la pilule (900 ms au plus) : sinon elle serait coupée
        self.assertIn("Timer { id: retour; interval: 900 }", self.ile)
        self.assertRegex(self.ile, r"ile\.height <= 31 && ile\.width <= compact\.largeur \+ 1\) retour\.stop\(\)")
        self.assertEqual(len(re.findall(r"on(Width|Height)Changed: fen\.revenue\(\)", self.ile)), 2)

    def test_tout_tient_dans_la_surface(self):
        # Pages les plus grandes (assistant 620, système 600, adaptées 580) + y 9 + le rebond du ressort (10 %)
        for h in re.findall(r"Math\.min\((\d+), \(Etat\.hauteurs|Math\.min\((\d+), modelData\.height", self.ile):
            hauteur = int(next(x for x in h if x))
            self.assertLessEqual(hauteur * 1.1 + 9, 700, hauteur)
        # Bulle (7 + 30) et point du micro (44 + 8) à droite de la pilule : 70 de marge de chaque côté
        self.assertIn("Math.max(ile.width, compact.largeur) + 140", self.ile)


class Batterie(unittest.TestCase):
    """Sur batterie, l'île réveille moins souvent le processeur : météo toutes les 30 min (10 sur secteur), dossier des
    téléchargements toutes les 30 s (6 sur secteur, 2 pendant un téléchargement). Sans FolderListModel : un paquet de
    plus sous Debian, et l'île entière ne se chargerait plus chez qui ne l'a pas (DEB-03)."""
    def test_releves(self):
        etat = (QML / "Etat.qml").read_text()
        self.assertIn("interval: (UPower.onBattery ? 30 : 10) * 60000", etat)
        self.assertIn("interval: etat.telechargements.length ? 2000 : (UPower.onBattery ? 30000 : 6000)", etat)
        for f in QML.glob("*.qml"):
            self.assertNotRegex(f.read_text(), r"import\s+Qt\.labs\.folderlistmodel", f.name)


if __name__ == "__main__":
    unittest.main()

"""Rayon des cartes des pages de l'île : elles suivent ILE_RAYON via Couleurs.rayon, comme les composants communs.

- Source : plus aucun « radius: <nombre> » en dur dans les pages, sauf les cercles listés ci-dessous.
- Rendu : au réglage par défaut (100 %), le rendu hors écran est identique à l'octet à celui des mêmes pages
  où chaque Couleurs.rayon(N, width, height) est remis en « radius: N » (donc au rendu d'avant le changement)."""
from tests import _isolation  # noqa: F401  (HOME, XDG_*, langue : avant tout le reste)
import importlib.util
import re
import shutil
import tempfile
import unittest
from pathlib import Path

DEPOT = Path(__file__).resolve().parents[1]
QML = DEPOT / "home/.config/quickshell/nc-ile"
LITTERAL = re.compile(r"radius: *[0-9]+(?:\.[0-9]+)?(?![0-9.]|\s*[/*+\-?])")

# Cercles et pastilles rondes (largeur = hauteur = 2 x rayon) : volontairement laissés en dur, ils doivent rester ronds
# quel que soit le réglage. fichier : nombre de cercles.
CERCLES = {
    "Assistant.qml": 3, "AssistantOrbe.qml": 1, "Calendrier.qml": 3, "Centre.qml": 3, "Charge.qml": 1, "ChoixTheme.qml": 1,
    "Claude.qml": 2, "CodeApercu.qml": 1, "CodeProjet.qml": 1, "Compact.qml": 2, "Fenetres.qml": 1, "Fiche.qml": 2,
    "GarminTiroir.qml": 2, "Ile.qml": 2, "Jarvis.qml": 1, "Jeu.qml": 1, "PageAppel.qml": 1, "PageListe.qml": 2,
    "PageNotifs.qml": 2, "PageResume.qml": 1, "PageTerminal.qml": 1, "Parametres.qml": 2, "PresseAction.qml": 1,
    "Projection.qml": 2, "Recherche.qml": 1, "Son.qml": 2, "Systeme.qml": 3, "VpnCarte.qml": 1, "VpnPastille.qml": 1,
    "Vue.qml": 2,
}


class Source(unittest.TestCase):
    def test_plus_de_rayon_en_dur(self):
        reste = {}
        for f in sorted(QML.glob("*.qml")):
            n = sum(len(LITTERAL.findall(l)) for l in f.read_text().split("\n"))
            if n:
                reste[f.name] = n
        self.assertEqual(reste, CERCLES)


@unittest.skipUnless(shutil.which("qs"), "Quickshell requis")
class Rendu(unittest.TestCase):
    def test_defaut_identique(self):
        spec = importlib.util.spec_from_file_location("rendu_ile", DEPOT / "outils/rendu-ile.py")
        outil = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(outil)
        with tempfile.TemporaryDirectory(prefix="nc-rpages-") as d:
            avant = Path(d) / "avant-qml"
            shutil.copytree(str(QML), str(avant))
            for f in avant.glob("*.qml"):
                f.write_text(re.sub(r"Couleurs\.rayon\(([0-9.]+), width, height\)", r"\1", f.read_text()))
            for etat in ("page", "recherche", "bureau"):
                png = {}
                for nom, qml in (("apres", QML), ("avant", avant)):
                    outil.QML = qml
                    sortie = Path(d) / nom
                    sortie.mkdir(exist_ok=True)
                    p, journal = outil.rendre(etat, str(sortie), None, None)
                    self.assertTrue(p, journal)
                    png[nom] = Path(p).read_bytes()
                self.assertEqual(png["avant"], png["apres"], etat)


if __name__ == "__main__":
    unittest.main()

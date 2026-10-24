"""L'avertissement sur la session de confiance (l'origine ne lie rien côté serveur) est bien écrit partout."""
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


class TestAvertissementSession(unittest.TestCase):
    def test_doc_jarvis(self):
        t = (REPO / "docs/jarvis.md").read_text()
        self.assertIn("jusqu’à `4ecc57a` compris", t)
        self.assertNotIn("062d1a1", t)
        self.assertIn("TOUTE entrée du serveur", t)
        self.assertIn("la laisser à 0", t)

    def test_reglage_nc_reglages(self):
        t = (REPO / "home/.local/bin/nc-reglages").read_text()
        self.assertIn("jusqu'à 4ecc57a compris", t)
        self.assertNotIn("062d1a1", t)
        self.assertIn("toute entrée du serveur (tout détenteur de SECRET_KEY)", t)
        self.assertIn("any server entry point (anyone holding SECRET_KEY)", t)


if __name__ == "__main__":
    unittest.main()

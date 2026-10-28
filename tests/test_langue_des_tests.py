"""Langue des tests : celle de la CI (anglais, tests/_isolation.py), et les versions françaises restent testées.
Sur un PC en français, un test qui lisait une phrase française sans fixer la langue passait ici et cassait en CI."""
import os
from pathlib import Path
import re
import unittest

TESTS = Path(__file__).resolve().parent
FIXE_FR = re.compile(r"""NC_LANGUE["']?\s*[:=,]\s*["']?fr|LANGUE=fr|\bEN = False""")


class LangueDesTests(unittest.TestCase):
    def test_anglais_comme_la_ci(self):
        self.assertEqual(os.environ.get("LANG"), "C.UTF-8")
        for cle in ("NC_LANGUE", "LC_ALL", "LC_MESSAGES", "LANGUAGE"):
            self.assertNotIn(cle, os.environ, cle)

    def test_le_francais_reste_teste(self):
        # au moins un test qui fixe le français pour chaque grande partie : île (qs -p hors écran), nc-reglages, nc-ia
        fichiers = [f.read_text(errors="replace") for f in TESTS.glob("test_*.py") if f.name != Path(__file__).name]
        fr = [t for t in fichiers if FIXE_FR.search(t)]
        for partie, motif in (("île", r"_ile_hors_ecran|\"qs\", \"-p\""), ("nc-reglages", r"nc-reglages"), ("nc-ia", r"nc-ia\b")):
            self.assertTrue(any(re.search(motif, t) for t in fr), f"aucun test en français pour {partie}")


if __name__ == "__main__":
    unittest.main()

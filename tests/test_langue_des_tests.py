"""Langue des tests : celle de la CI (anglais, tests/_isolation.py), et les versions françaises restent testées.
Sur un PC en français, un test qui lisait une phrase française sans fixer la langue passait ici et cassait en CI."""
import ast
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


def environ_change_a_l_import(source):
    """Lignes où le module change os.environ hors de toute fonction ou classe (donc à l'import)."""
    lignes = []
    for noeud in ast.parse(source).body:
        if isinstance(noeud, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        for n in ast.walk(noeud):
            cible = None
            if isinstance(n, (ast.Assign, ast.AugAssign, ast.Delete)):
                cibles = n.targets if isinstance(n, (ast.Assign, ast.Delete)) else [n.target]
                cible = next((c for c in cibles if isinstance(c, ast.Subscript)), None)
                cible = cible.value if cible is not None else None
            elif isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute):
                if n.func.attr in ("setdefault", "update", "pop", "clear", "popitem"):
                    cible = n.func.value
                elif n.func.attr == "dict" and ast.unparse(n.func).endswith("patch.dict"):
                    cible = next(iter(n.args), None)   # un patch de os.environ créé à l'import (puis .start())
            if cible is not None and ast.unparse(cible) == "os.environ":
                lignes.append(n.lineno)
    return lignes


class EnvironnementALImport(unittest.TestCase):
    def test_aucun_module_ne_change_l_environnement_a_l_import(self):
        # La découverte importe TOUS les modules avant le premier test : un changement à l'import fuit dans les autres
        # (revue IG1-B, puis test_diag_plateforme). L'isolation commune (_isolation.py) est la seule exception.
        fautes = {}
        for f in sorted(TESTS.glob("test_*.py")):
            l = environ_change_a_l_import(f.read_text())
            if l:
                fautes[f.name] = l
        self.assertEqual(fautes, {})

    def test_le_detecteur_voit_les_formes_connues(self):
        for code in ('import os\nos.environ["X"] = "1"\n', 'import os\nos.environ.setdefault("X", "1")\n',
                     'import os\nfrom unittest import mock\nmock.patch.dict(os.environ, X="1").start()\n',
                     'import os\nfrom unittest import mock\nP = mock.patch.dict(os.environ, X="1")\nP.start()\n',
                     'import os\nif True:\n    os.environ.update(X="1")\n'):
            self.assertTrue(environ_change_a_l_import(code), code)
        self.assertFalse(environ_change_a_l_import('import os\ndef f():\n    os.environ["X"] = "1"\n'))
        self.assertFalse(environ_change_a_l_import('import os\nE = dict(os.environ, X="1")\n'))


if __name__ == "__main__":
    unittest.main()

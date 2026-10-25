"""nc-memoire : nom lisible d'un programme (python3 -u script.py) et décimale selon la langue."""
from importlib.machinery import SourceFileLoader
import importlib.util
import os
from pathlib import Path
import unittest
from unittest import mock

BIN = Path(__file__).resolve().parents[1] / "home/.local/bin/nc-memoire"


def charge(langue):
    with mock.patch.dict(os.environ, {"NC_LANGUE": langue}):
        loader = SourceFileLoader("nc_memoire_" + langue, str(BIN))
        spec = importlib.util.spec_from_loader(loader.name, loader)
        mod = importlib.util.module_from_spec(spec)
        loader.exec_module(mod)
    return mod


def cmd(*args):
    return [a.encode() for a in args]


class TestNom(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = charge("fr")

    def test_options_python_ignorees(self):
        n = self.m.nom_cmdline
        self.assertEqual(n(cmd("python3", "-u", "/opt/x/script.py", "a"), "python3"), "script.py")
        self.assertEqual(n(cmd("/usr/bin/python3", "-I", "-u", "s.py"), "python3"), "s.py")
        self.assertEqual(n(cmd("python3.12", "-u", "s.py"), "python3.12"), "s.py")
        self.assertEqual(n(cmd("bash", "-x", "/a/run.sh"), "bash"), "run.sh")

    def test_module_et_code(self):
        n = self.m.nom_cmdline
        self.assertEqual(n(cmd("python3", "-u", "-m", "http.server", "8000"), "python3"), "http")
        self.assertEqual(n(cmd("python3", "-m", "pip", "install"), "python3"), "pip")
        self.assertEqual(n(cmd("python3", "-c", "print(1)"), "python3"), "python3")
        self.assertEqual(n(cmd("python3"), "python3"), "python3")

    def test_autres_programmes(self):
        self.assertEqual(self.m.nom_cmdline(cmd("/usr/bin/firefox", "-u", "x"), "firefox"), "firefox")
        self.assertEqual(self.m.nom_cmdline([b""], "kworker"), "kworker")


class TestTaille(unittest.TestCase):
    def test_virgule_en_francais(self):
        self.assertIn("31,1 Go", charge("fr").mo(int(31.1 * 1073741824)))

    def test_point_en_anglais(self):
        self.assertIn("31.1 GB", charge("en").mo(int(31.1 * 1073741824)))

    def test_petite_taille_sans_decimale(self):
        self.assertIn("512 Mo", charge("fr").mo(512 * 1048576))


if __name__ == "__main__":
    unittest.main()

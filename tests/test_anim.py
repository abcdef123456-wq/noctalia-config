"""nc-anim : seules les vraies animations perso comptent, et pas de plantage hors terminal."""
from importlib.machinery import SourceFileLoader
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

BIN = Path(__file__).resolve().parents[1] / "home/.local/bin/nc-anim"


def charge(home):
    with mock.patch.dict(os.environ, {"HOME": home, "NC_LANGUE": "fr"}):
        loader = SourceFileLoader("nc_anim_test", str(BIN))
        spec = importlib.util.spec_from_loader(loader.name, loader)
        mod = importlib.util.module_from_spec(spec)
        loader.exec_module(mod)
    return mod


class TestPerso(unittest.TestCase):
    def test_sauvegardes_ignorees(self):
        with tempfile.TemporaryDirectory() as home:
            d = Path(home) / ".config/nc/animations"
            d.mkdir(parents=True)
            for f in ("demo.py", "demo.py~", "demo.py.bak", "demo.py.swp", "demo.py.orig", ".cache.py", "notes.txt"):
                (d / f).write_text("x")
            sh = d / "lueur"
            sh.write_text("#!/bin/sh\n")
            sh.chmod(0o755)
            m = charge(home)
            self.assertEqual(m.perso(), {"demo": str(d / "demo.py"), "lueur": str(sh)})


class TestHorsTerminal(unittest.TestCase):
    def test_sortie_redirigee(self):
        with tempfile.TemporaryDirectory() as home:
            env = dict(os.environ, HOME=home, NC_LANGUE="fr", NC_ANIM_DEDANS="1")
            env.pop("WAYLAND_DISPLAY", None)
            p = subprocess.run([sys.executable, str(BIN), "neige"], env=env, stdin=subprocess.DEVNULL,
                               stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, universal_newlines=True)
            self.assertNotEqual(p.returncode, 0)
            self.assertIn("terminal", p.stderr)
            self.assertNotIn("Traceback", p.stderr)


if __name__ == "__main__":
    unittest.main()

"""Plugin Hyprland nc-gestes (plugins/nc-gestes) : il se compile contre les en-têtes installés et exporte les trois
points d'entrée qu'Hyprland cherche au chargement. Sauté sans en-têtes d'Hyprland (pkg-config hyprland), g++, make
ou nm : c'est le cas des distributions où le plugin n'est pas proposé et où l'animation native sert de repli."""
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

RACINE = Path(__file__).resolve().parents[1]
PLUGIN = RACINE / "plugins/nc-gestes"


def entetes_hyprland():
    if not shutil.which("pkg-config"):
        return False
    return subprocess.run(["pkg-config", "--exists", "hyprland"]).returncode == 0


OUTILS = entetes_hyprland() and all(shutil.which(o) for o in ("g++", "make", "nm"))


@unittest.skipUnless(OUTILS, "en-têtes d'Hyprland, g++, make ou nm absents")
class CompilationNcGestes(unittest.TestCase):
    def test_compile_et_exporte_les_points_d_entree(self):
        with tempfile.TemporaryDirectory() as tmp:
            sortie = Path(tmp) / "nc-gestes.so"
            r = subprocess.run(["make", "-s", "-C", str(PLUGIN), "SORTIE=" + str(sortie)],
                               capture_output=True, text=True, timeout=600)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertNotIn("warning", r.stderr, r.stderr)
            lignes = subprocess.run(["nm", "-D", "--defined-only", str(sortie)],
                                    capture_output=True, text=True, check=True).stdout.splitlines()
            types = {l.split()[2]: l.split()[1] for l in lignes if len(l.split()) == 3}
            for nom in ("pluginAPIVersion", "pluginInit", "pluginExit"):
                self.assertEqual(types.get(nom), "T", nom)
            # Un symbole « u » (GNU unique) empêche glibc de décharger le .so : « plugin unload » ne libérerait rien.
            self.assertNotIn("u", types.values())


@unittest.skipUnless(shutil.which("glslangValidator"), "glslangValidator absent")
class ShaderNcGestes(unittest.TestCase):
    def test_glsl_es_300_valide(self):
        """Le programme n'est compilé par Hyprland qu'à la première ouverture : une erreur y passerait inaperçue."""
        src = (PLUGIN / "src/Shaders.cpp").read_text(encoding="utf-8")
        with tempfile.TemporaryDirectory() as tmp:
            for nom, ext in (("VERT", "vert"), ("FRAG", "frag")):
                m = re.search(r'const std::string ' + nom + r' = R"GLSL\((.*?)\)GLSL";', src, re.S)
                self.assertIsNotNone(m, nom)
                f = Path(tmp) / ("geste." + ext)
                f.write_text(m.group(1), encoding="utf-8")
                r = subprocess.run(["glslangValidator", str(f)], capture_output=True, text=True, timeout=60)
                self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


if __name__ == "__main__":
    unittest.main()

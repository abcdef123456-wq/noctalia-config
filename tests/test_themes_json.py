"""nc-reglages themes --json : la liste des thèmes pour le carrousel de l'île (lecture seule, aucun réseau).
Faux HOME, jamais le vrai ; un thème refusé n'est pas dans la liste ; une palette custom est lue dans son fichier."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

REPO = Path(__file__).resolve().parent.parent
BIN = REPO / "home/.local/bin/nc-reglages"
THEMES = REPO / "home/.local/share/nc/themes"
PALETTE = {"dark": {"mPrimary": "#33ff66", "mSecondary": "#ffb000", "mTertiary": "#66ffcc", "mSurface": "#0a0f0a",
                    "mOnSurface": "#b8ffc8"}}


class ThemesJson(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp(prefix="nc-thj-")
        self.addCleanup(shutil.rmtree, self.d, True)
        self.themes = Path(self.d) / "themes"
        shutil.copytree(str(THEMES), str(self.themes))
        pal = Path(self.d) / ".config/noctalia/palettes"
        pal.mkdir(parents=True)
        (pal / "Retro.json").write_text(json.dumps(PALETTE))

    def lancer(self, *args):
        env = {k: v for k, v in os.environ.items() if k in ("PATH", "LANG")}
        env.update(HOME=self.d, XDG_CONFIG_HOME=self.d + "/.config", XDG_DATA_HOME=self.d + "/.local/share",
                   XDG_CACHE_HOME=self.d + "/.cache", XDG_STATE_HOME=self.d + "/.state", XDG_RUNTIME_DIR=self.d,
                   TMPDIR=self.d, NC_THEMES_DIR=str(self.themes), NC_LANGUE="fr",
                   http_proxy="http://127.0.0.1:9", https_proxy="http://127.0.0.1:9")  # un accès réseau échouerait
        return subprocess.run([sys.executable, str(BIN)] + list(args), env=env, capture_output=True, text=True,
                              timeout=60)

    def liste(self):
        r = self.lancer("themes", "--json")
        self.assertEqual(r.returncode, 0, r.stderr)
        return {t["nom"]: t for t in json.loads(r.stdout)}

    def test_contenu(self):
        t = self.liste()
        self.assertEqual(set(t), {p.stem for p in THEMES.glob("*.json")})
        for nom, x in t.items():
            self.assertEqual(set(x), {"nom", "libelle", "actif", "palette", "couleurs", "palette_approximative",
                                      "reglages", "miniature"}, nom)
            self.assertIsInstance(x["libelle"], str)
        self.assertEqual([n for n in t if t[n]["actif"]], ["noctalia"])  # sans réglage : le défaut est actif
        self.assertTrue(t["tokyo"]["palette_approximative"])  # builtin : couleurs neutres, dites approximatives

    def test_palette_custom_lue(self):
        x = self.liste()["retro"]
        self.assertFalse(x["palette_approximative"])
        self.assertEqual(x["couleurs"]["primary"], "#33ff66")
        self.assertEqual(x["couleurs"]["surface"], "#0a0f0a")

    def test_palette_custom_mauvaise(self):
        (Path(self.d) / ".config/noctalia/palettes/Retro.json").write_text("pas du json")
        self.assertTrue(self.liste()["retro"]["palette_approximative"])

    def test_theme_refuse_absent(self):
        p = self.themes / "nord.json"
        j = json.loads(p.read_text())
        j["palette"]["source"] = "inconnue"
        p.write_text(json.dumps(j))
        (self.themes / "casse.json").write_text("{pas du json")
        t = self.liste()
        self.assertNotIn("nord", t)
        self.assertNotIn("casse", t)
        self.assertIn("dracula", t)


if __name__ == "__main__":
    unittest.main()

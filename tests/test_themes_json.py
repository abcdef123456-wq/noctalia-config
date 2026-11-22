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
                   XDG_CONFIG_DIRS=self.d + "/xdg", XDG_DATA_DIRS=self.d + "/share",   # schémas de Noctalia : ceux du test seulement
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
                                      "reglages", "miniature", "disposition"}, nom)
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

    def test_palette_builtin_lue_dans_les_schemas_de_noctalia(self):
        """Builtin : lue dans quickshell/noctalia-shell/Assets/ColorScheme d'un dossier XDG ; absente : neutre."""
        self.assertTrue(self.liste()["tokyo"]["palette_approximative"])
        d = Path(self.d) / "share/quickshell/noctalia-shell/Assets/ColorScheme/Tokyo-Night"
        d.mkdir(parents=True)
        (d / "Tokyo-Night.json").write_text(json.dumps({"dark": {"mPrimary": "#7aa2f7", "mSecondary": "#bb9af7", "mTertiary": "#9ece6a",
                                                                 "mSurface": "#1a1b26", "mOnSurface": "#c0caf5"}}))
        x = self.liste()["tokyo"]
        self.assertFalse(x["palette_approximative"])
        self.assertEqual((x["couleurs"]["primary"], x["couleurs"]["surface"]), ("#7aa2f7", "#1a1b26"))

    def test_miniature_cache_sinon_fond_de_depart(self):
        self.assertEqual(self.liste()["retro"]["miniature"], "")
        fond = Path(self.d) / "Pictures/Wallpapers/retro/retro-grille.jpg"
        fond.parent.mkdir(parents=True)
        fond.write_bytes(b"x")
        self.assertEqual(self.liste()["retro"]["miniature"], str(fond))
        cache = Path(self.d) / ".cache/nc/carousel/retro-grille.jpg.W.webp"
        cache.parent.mkdir(parents=True)
        cache.write_bytes(b"x")
        self.assertEqual(self.liste()["retro"]["miniature"], str(cache))

    def test_palette_enorme_lien_ou_profonde_couleurs_neutres(self):
        """Lecture bornée (1 Mo), fichier ordinaire seulement : sinon couleurs neutres, sans erreur."""
        d = Path(self.d) / "share/quickshell/noctalia-shell/Assets/ColorScheme/Tokyo-Night"
        d.mkdir(parents=True)
        f = d / "Tokyo-Night.json"
        vraie = Path(self.d) / "vraie.json"
        vraie.write_text(json.dumps({"dark": {"mPrimary": "#7aa2f7", "mSecondary": "#bb9af7", "mTertiary": "#9ece6a",
                                              "mSurface": "#1a1b26", "mOnSurface": "#c0caf5"}}))
        # énorme : une vraie palette, complétée au-delà de 1 Mo (sans borne, elle serait lue)
        enorme = json.loads(vraie.read_text())
        enorme["dark"]["remplissage"] = "a" * (2 * 1024 ** 2)
        cas = {"énorme": lambda: f.write_text(json.dumps(enorme)),
               "lien": lambda: f.symlink_to(vraie),
               "profond": lambda: f.write_text("[" * 200000 + "]" * 200000),
               "pas du json": lambda: f.write_bytes(b"\xff\xfe")}
        for nom, faire in cas.items():
            with self.subTest(cas=nom):
                if f.is_symlink() or f.exists():
                    f.unlink()
                faire()
                self.assertTrue(self.liste()["tokyo"]["palette_approximative"])
        f.unlink()
        f.write_text(vraie.read_text())
        self.assertFalse(self.liste()["tokyo"]["palette_approximative"])   # le même contenu, en vrai fichier : lu

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

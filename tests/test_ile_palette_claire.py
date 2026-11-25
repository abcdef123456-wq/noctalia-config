"""Île : palette claire (« sombre » de palette-ile.json) et palettes sombres / par défaut : lisibilité et contraste."""
from tests import _isolation
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests.test_rendu_ile import est_unie, lire_png

DEPOT = Path(__file__).resolve().parents[1]
QML = DEPOT / "home/.config/quickshell/nc-ile"
ETATS = ("page", "recherche", "bureau")  # bureau : le filet de Couleurs.voile

SOMBRE = {"sombre": True, "fond": "#0a0f0a", "texte": "#b8ffc8", "texteSec": "#5fa872", "texteDoux": "#98dea8",
          "carte": "#121712", "carteSurvol": "#151a15", "gris2": "#181e18", "gris3": "#232823", "gris4": "#2d322d",
          "gris5": "#3e453e", "accent": "#33ff66", "surAccent": "#0a0f0a", "surCouleur": "#0a0f0a", "rouge": "#ee8f63",
          "vert": "#71c177", "jaune": "#c9cb61", "orange": "#eba42c", "bleu": "#2ebbe8", "violet": "#ed86a7",
          "rose": "#fdb2c8", "cyan": "#41c59b", "fondVert": "#213622", "fondOrange": "#3c3011",
          "bordure": ["#c1e3a9", "#5e7a60", "#aaefca"]}
CLAIR = dict(SOMBRE, sombre=False, fond="#f5f1e8", texte="#2a2a2a", texteSec="#5a5650", texteDoux="#444444",
             carte="#e9e5dc", carteSurvol="#e4e0d8", gris2="#dfdcd3", gris3="#d1cdc4", gris4="#c4c0b7", gris5="#aeaaa2",
             accent="#b4637a", surAccent="#000000", surCouleur="#ffffff", rouge="#aa3f50", vert="#587505",
             jaune="#905c0b", orange="#aa4603", bleu="#6359b5", violet="#a73f62", rose="#90204b", cyan="#147b5d",
             fondVert="#d2d6b6", fondOrange="#e5cbb6", bordure=["#a66b88", "#d0aeb2", "#b37074"])


def luminance(rgb):
    def c(v):
        v /= 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    return 0.2126 * c(rgb[0]) + 0.7152 * c(rgb[1]) + 0.0722 * c(rgb[2])


def contraste(a, b):
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def pixel(png, x, y):
    w, h, lignes = lire_png(png)
    n = len(lignes[0]) // w
    return tuple(lignes[y][x * n:x * n + 3])


class Source(unittest.TestCase):
    def test_couleurs_lit_sombre_de_la_palette(self):
        t = (QML / "Couleurs.qml").read_text()
        self.assertIn("readonly property bool sombre: !(terminal && p.sombre === false)", t)
        self.assertIn("readonly property color voile: sombre", t)

    def test_blancs_traites_ne_sont_plus_en_dur(self):
        for f in ("Code.qml", "Fiche.qml", "Bureau.qml"):
            self.assertIn("Couleurs.voile", (QML / f).read_text(), f)
        self.assertNotIn("Qt.rgba(1, 1, 1, 0.14)", (QML / "Bureau.qml").read_text())
        l181 = (QML / "Claude.qml").read_text().splitlines()[180]
        self.assertIn("Couleurs.sombre", l181)


@unittest.skipUnless(shutil.which("qs"), "Quickshell (qs) absent")
class Rendu(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.t = Path(tempfile.mkdtemp(prefix="nct-", dir=_isolation.dossier_court()))
        (cls.t / "sombre.json").write_text(json.dumps(SOMBRE))
        (cls.t / "clair.json").write_text(json.dumps(CLAIR))
        (cls.t / "sans-contour.conf").write_text("ILE_CONTOUR=aucun\n")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(str(cls.t), ignore_errors=True)

    @classmethod
    def rendre(cls, nom, palette, sans_contour=False):
        sortie = cls.t / ("png-%s" % nom)
        cmd = [sys.executable, str(DEPOT / "outils/rendu-ile.py"), "--sortie", str(sortie)]
        if palette:
            cmd += ["--palette", str(cls.t / (palette + ".json"))]
        if sans_contour:
            cmd += ["--reglages", str(cls.t / "sans-contour.conf")]
        env = {k: v for k, v in os.environ.items() if k in ("PATH", "LANG", "LC_ALL", "HOME", "XDG_CONFIG_HOME",
                                                           "XDG_DATA_HOME", "XDG_CACHE_HOME", "TMPDIR", "NC_LANGUE")}
        r = subprocess.run(cmd + list(ETATS), capture_output=True, text=True, env=env, timeout=240)
        assert r.returncode == 0, r.stderr[-800:]
        return sortie

    def verifier_palette_sombre(self, nom, palette, sans_contour=False):
        d = self.rendre(nom, palette, sans_contour=sans_contour)
        for e in ETATS:
            w, h, lignes = lire_png(d / (e + ".png"))
            self.assertGreater(w, 0, e)
            self.assertGreater(h, 0, e)
            self.assertFalse(est_unie(w, lignes), e)
        w, h, lignes = lire_png(d / "page.png")
        n = len(lignes[0]) // w
        px = [tuple(l[x * n:x * n + 3]) for l in lignes[60:min(h - 20, 180)] for x in range(40, min(w - 40, 260))]
        fond = max(set(px), key=px.count)
        texte = max(px, key=luminance)
        self.assertLess(luminance(fond), 0.35, "fond sombre attendu")
        self.assertGreaterEqual(contraste(fond, texte), 4.5, "contraste insuffisant en sombre")

    def test_sans_palette_lisible(self):
        self.verifier_palette_sombre("defaut", None)

    def test_palette_sombre_lisible(self):
        self.verifier_palette_sombre("sombre", "sombre")

    def test_palette_sombre_sans_contour_lisible(self):
        self.verifier_palette_sombre("sombre-nc", "sombre", sans_contour=True)

    def test_palette_claire_texte_lisible_sur_carte(self):
        d = self.rendre("clair", "clair")
        png = d / "page.png"
        w, h, lignes = lire_png(png)
        n = len(lignes[0]) // w
        px = [tuple(l[x * n:x * n + 3]) for l in lignes[60:min(h - 20, 180)] for x in range(40, min(w - 40, 260))]
        fond = max(set(px), key=px.count)
        texte = min(px, key=luminance)
        self.assertGreater(luminance(fond), 0.5, "fond de carte clair")
        self.assertGreaterEqual(contraste(fond, texte), 4.5)

if __name__ == "__main__":
    unittest.main()

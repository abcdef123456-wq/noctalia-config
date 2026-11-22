"""Vignette du carrousel de thèmes : MiniDisposition.qml dessine la disposition du thème.
- `nc-reglages themes --json` donne un objet « disposition » (valeurs effectives) pour chaque thème.
- Cohérence : cet objet égale ce que calcule schema-theme.py (une seule règle, celle de nc-reglages).
- Hors écran (sauté sans Quickshell) : barre à droite = pixel de la barre au bord droit ; barre en bas = au bord du bas.
- Source : MiniDisposition.qml n'a ni component inline, ni Timer, ni import en plus de QtQuick."""
import importlib.util
import json
import re
import shutil
import subprocess
import tempfile
import unittest
from importlib.machinery import SourceFileLoader
from pathlib import Path

from tests import _ile_hors_ecran as H
from tests import _isolation

REPO = Path(__file__).resolve().parents[1]
THEMES = REPO / "home/.local/share/nc/themes"
BIN = REPO / "home/.local/bin/nc-reglages"
QML = REPO / "home/.config/quickshell/nc-ile/MiniDisposition.qml"


def themes_json(tmp):
    t = Path(tmp)
    for d in ("config", "data", "cache", "state", "home"):
        (t / d).mkdir(exist_ok=True)
    env = {"PATH": "/usr/bin:/bin", "HOME": str(t / "home"), "XDG_CONFIG_HOME": str(t / "config"), "XDG_DATA_HOME": str(t / "data"),
           "XDG_CACHE_HOME": str(t / "cache"), "XDG_STATE_HOME": str(t / "state"), "TMPDIR": str(t),
           "NC_THEMES_DIR": str(THEMES), "NC_LANGUE": "fr"}
    r = subprocess.run(["python3", str(BIN), "themes", "--json"], env=env, capture_output=True, text=True, timeout=60, stdin=subprocess.DEVNULL)
    assert r.returncode == 0, r.stderr
    return {x["nom"]: x for x in json.loads(r.stdout)}


class Donnees(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(dir=_isolation.dossier_court())
        cls.t = themes_json(cls.tmp.name)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_chaque_theme_a_une_disposition(self):
        self.assertTrue(self.t)
        for nom, x in self.t.items():
            d = x["disposition"]
            self.assertEqual(set(d), {"barre", "fenetres", "dock", "ile"}, nom)
            self.assertIn(d["barre"]["position"], ("top", "bottom", "left", "right"), nom)
            self.assertTrue(16 <= d["barre"]["epaisseur"] <= 120, nom)
            self.assertIn(d["fenetres"]["disposition"], ("dwindle", "master", "scrolling"), nom)

    def test_kanagawa(self):
        d = self.t["kanagawa"]["disposition"]
        self.assertEqual(d["barre"]["position"], "top")          # bandeau d'encre en haut (recette)
        self.assertEqual(d["fenetres"]["disposition"], "scrolling")

    def test_nord(self):
        d = self.t["nord"]["disposition"]
        self.assertEqual(d["barre"]["position"], "bottom")          # pilule unique en bas (plus de barre de côté)
        self.assertEqual(d["fenetres"]["disposition"], "master")
        self.assertEqual(d["fenetres"]["orientation"], "gauche")

    def test_noctalia_defauts(self):
        d = self.t["noctalia"]["disposition"]
        self.assertEqual(d["barre"]["position"], "top")
        self.assertEqual(d["fenetres"]["disposition"], "dwindle")
        self.assertEqual((d["fenetres"]["espace"], d["fenetres"]["marge"], d["fenetres"]["bordure"], d["fenetres"]["arrondi"]), (4, 10, 2, 14))
        self.assertEqual(d["ile"]["rayon"], 100)

    def test_coherent_avec_schema_theme(self):
        spec = importlib.util.spec_from_loader("schema_theme", SourceFileLoader("schema_theme", str(REPO / "outils/schema-theme.py")))
        st = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(st)
        with tempfile.TemporaryDirectory(dir=_isolation.dossier_court()) as d:
            mod, themes, _ = st.charger_reglages(THEMES, Path(d))
            noct = st.lire_noctalia_defaut()
            for nom in ("kanagawa", "nord", "noctalia"):
                reg, n = st.valeurs_effectives(mod, themes[nom], noct)
                disp = self.t[nom]["disposition"]
                self.assertEqual(disp["barre"]["position"], n["bar"].get("position", "top"), nom)
                self.assertEqual(disp["barre"]["epaisseur"], int(n["bar"].get("thickness", 36)), nom)
                self.assertEqual(disp["fenetres"]["disposition"], reg.get("FENETRES_DISPOSITION", "dwindle"), nom)
                self.assertEqual(disp, mod.disposition_theme(themes[nom], mod.noctalia_defaut()), nom)


class Source(unittest.TestCase):
    def test_pas_de_component_timer_ni_import_en_plus(self):
        s = QML.read_text()
        self.assertIsNone(re.search(r"^\s*component\s+\w+\s*:", s, re.M))
        self.assertNotIn("Timer", s)
        self.assertEqual(re.findall(r"^import .*$", s, re.M), ["import QtQuick"])


def disposition(pos, marge=0):
    return {"barre": {"position": pos, "epaisseur": 40, "marge": marge, "capsules": True},
            "fenetres": {"disposition": "dwindle", "orientation": "auto", "espace": 4, "marge": 10, "bordure": 2, "arrondi": 14},
            "dock": {"actif": False, "position": "bottom", "cache": True}, "ile": {"rayon": 100}}


SHELL = """
ShellRoot {
%s
    Window { id: fen; width: 320; height: 200; visible: true; color: "#ff00ff"
        MiniDisposition { id: md; objectName: "md"; width: 320; height: 200; couleurBarre: "#00ff00"; surface: "#333333"
            primaire: "#ff0000"; secondaire: "#0000ff"; disp: %s }
    }
    property int n: 0
    Timer { interval: 150; running: true; repeat: true; onTriggered: {
        if (++n < 4) return
        running = false
        md.grabToImage(function (r) { if (!r.saveToFile("%s/rendu.ppm")) { console.error("ECHEC sauvegarde"); Qt.exit(2) } console.log("FINI"); Qt.exit(0) })
    } }
    Timer { interval: 15000; running: true; onTriggered: { console.error("ECHEC délai"); Qt.exit(3) } }
}
"""


def lire_ppm(chemin):
    m = re.match(rb"P6\s+(\d+)\s+(\d+)\s+255\s", chemin.read_bytes())
    w, h = int(m.group(1)), int(m.group(2))
    data = chemin.read_bytes()[m.end():]
    return w, h, lambda x, y: "#%02x%02x%02x" % tuple(data[(y * w + x) * 3:(y * w + x) * 3 + 3])


@unittest.skipUnless(shutil.which("qs"), "Quickshell requis")
class HorsEcran(unittest.TestCase):
    def rendre(self, disp):
        with tempfile.TemporaryDirectory(prefix="nc-minidisp-", dir=_isolation.dossier_court()) as d:
            root = H.preparer(d, ("MiniDisposition",), extra={})
            (root / "shell.qml").write_text(H.ENTETE + SHELL % (H.OUTILS, json.dumps(disp), root / "tmp"))
            _, sortie = H.lancer(root, delai=40)
            for e in H.ERREURS:
                self.assertNotIn(e, sortie, sortie)
            self.assertIn("FINI", sortie, sortie)
            return lire_ppm(root / "tmp" / "rendu.ppm")

    def test_barre_a_droite(self):
        w, h, px = self.rendre(disposition("right"))
        self.assertEqual(px(w - 1, h // 2), "#00ff00")
        self.assertNotEqual(px(0, h // 2), "#00ff00")

    def test_barre_en_bas(self):
        w, h, px = self.rendre(disposition("bottom"))
        self.assertEqual(px(w // 2, h - 1), "#00ff00")
        self.assertNotEqual(px(w // 2, 0), "#00ff00")


if __name__ == "__main__":
    unittest.main()

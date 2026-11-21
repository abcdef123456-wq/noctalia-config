"""Rappels du Spotlight (Rappels.js, Rappels.qml) : l'analyse pure passe par node, le singleton par un vrai qs hors écran.
Aucun test ne touche la vraie île : tout est dans un dossier temporaire, avec de faux Memo, Notifs et Reglages."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
QML = REPO / "home/.config/quickshell/nc-ile"
NODE = shutil.which("node")
QS = shutil.which("qs")

# Le .js est une bibliothèque Quickshell (« .pragma library ») : on retire cette ligne pour l'évaluer sous node
PILOTE = """
const fs = require("fs"), vm = require("vm")
const src = fs.readFileSync(process.argv[2], "utf8").replace(/^\\.pragma library$/m, "")
const ctx = vm.createContext({ Array, Math, Date, String, JSON, isFinite, parseInt })
vm.runInContext(src, ctx)
console.log(JSON.stringify(vm.runInContext(process.argv[3], ctx)))
"""
# Mardi 10 novembre 2026, 14:00 locale (TZ=UTC pour l'essai)
NOW = "Date.UTC(2026, 10, 10, 14, 0, 0)"


def js(expr):
    with tempfile.TemporaryDirectory() as t:
        p = Path(t) / "pilote.js"; p.write_text(PILOTE)
        r = subprocess.run([NODE, str(p), str(QML / "Rappels.js"), expr], capture_output=True, text=True,
                           env={"PATH": os.environ["PATH"], "TZ": "UTC"}, timeout=30)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def analyse(phrase):
    return js(f"analyser({json.dumps(phrase)}, {NOW})")


def minutes(a):
    """Écart en minutes entre l'échéance trouvée et 14:00."""
    return (a["due"] - js(NOW)) / 60000


@unittest.skipUnless(NODE, "node absent")
class Analyse(unittest.TestCase):
    def test_heures_de_la_journee(self):
        for phrase, attendu in (("15h appeler le garage", 60), ("15h30 x", 90), ("15:30 x", 90), ("à 15h x", 60),
                                ("3pm call", 60), ("3:30pm call", 90), ("at 3pm call", 60)):
            with self.subTest(phrase):
                a = analyse(phrase)
                self.assertTrue(a["ok"], a)
                self.assertEqual(minutes(a), attendu)

    def test_durees(self):
        for phrase, attendu in (("20 min sortir le linge", 20), ("2 h x", 120), ("dans 1h30 x", 90), ("in 2 hours x", 120),
                                ("90 s x", 1.5), ("20min x", 20)):
            with self.subTest(phrase):
                a = analyse(phrase)
                self.assertTrue(a["ok"], a)
                self.assertEqual(minutes(a), attendu)

    def test_texte_garde_brut(self):
        a = analyse("15h appeler $(rm -rf ~) ; `x` « é »")
        self.assertEqual(a["texte"], "appeler $(rm -rf ~) ; `x` « é »")

    def test_1h30_colle_est_une_heure(self):
        self.assertEqual(minutes(analyse("1h30 x")), 11 * 60 + 30)    # 01:30 est passée : demain

    def test_demain_fr_en(self):
        self.assertEqual(minutes(analyse("demain 9h x")), 19 * 60)
        self.assertEqual(minutes(analyse("tomorrow 9am x")), 19 * 60)

    def test_heure_passee_va_a_demain(self):
        self.assertEqual(minutes(analyse("13h x")), 23 * 60)
        self.assertEqual(minutes(analyse("14h x")), 24 * 60)           # pile maintenant : demain

    def test_heure_non_comprise(self):
        for phrase in ("bientôt appeler", "25h x", "15h61 x", "13pm x", "0am x", "999999 min x", ""):
            with self.subTest(phrase):
                self.assertEqual(analyse(phrase), {"ok": False, "raison": "heure"})

    def test_texte_manquant(self):
        self.assertEqual(analyse("15h"), {"ok": False, "raison": "texte"})
        self.assertEqual(analyse("15h    "), {"ok": False, "raison": "texte"})

    def test_texte_trop_long_coupe_a_200(self):
        self.assertEqual(len(analyse("15h " + "é" * 500)["texte"]), 200)
        self.assertEqual(len(js('Array.from(nettoyer("😀".repeat(300)))')), 200)

    def test_quand(self):
        self.assertEqual(js(f"quand({NOW} + 3600000, {NOW}, false)"), "15:00")
        self.assertEqual(js(f"quand({NOW} + 19*3600000, {NOW}, false)"), "demain 09:00")
        self.assertEqual(js(f"quand({NOW} + 19*3600000, {NOW}, true)"), "tomorrow 09:00")


@unittest.skipUnless(NODE, "node absent")
class Liste(unittest.TestCase):
    def test_51e_refuse(self):
        r = js(f"""(function () {{ var l = []; for (var i = 0; i < 50; i++) l = ajouter(l, "x", {NOW} + 1000 + i, {NOW} + i).liste
                  var a = ajouter(l, "de trop", {NOW} + 99999, {NOW} + 99); return [l.length, a.ok, a.raison, a.liste.length] }})()""")
        self.assertEqual(r, [50, False, "plein", 50])

    def test_suppression(self):
        r = js(f"""(function () {{ var l = ajouter([], "a", {NOW} + 5, {NOW}).liste; l = ajouter(l, "b", {NOW} + 9, {NOW}).liste
                  var sans = retirer(l, l[0].id); return [l.length, sans.length, sans[0].texte] }})()""")
        self.assertEqual(r, [2, 1, "b"])

    def test_echus_et_prochaine(self):
        r = js(f"partager([{{id:'a',texte:'a',due:{NOW}-5}},{{id:'b',texte:'b',due:{NOW}+7}},{{id:'c',texte:'c',due:{NOW}+3}}], {NOW})")
        self.assertEqual([x["id"] for x in r["dus"]], ["a"])
        self.assertEqual(len(r["restants"]), 2)
        self.assertEqual(r["prochaine"] - js(NOW), 3)
        self.assertIsNone(js("partager([], 5)")["prochaine"])

    def test_delai_borne(self):
        self.assertEqual(js("delai(10, 20)"), 1)
        self.assertEqual(js("delai(1e13, 0)"), 2147483647)

    def test_valider_ignore_les_intrus(self):
        r = js("valider([{id:'a',texte:'t',due:1},{id:'a',texte:'doublon',due:2},{id:3},null,'x',{id:'b',texte:'u',due:'1'}])")
        self.assertEqual(r, [{"id": "a", "texte": "t", "due": 1}])
        self.assertEqual(js("valider('nimporte quoi')"), [])


QMLDIR = """module nc
singleton Rappels 1.0 Rappels.qml
singleton Memo 1.0 Memo.qml
singleton Notifs 1.0 Notifs.qml
singleton Reglages 1.0 Reglages.qml
singleton Etat 1.0 Etat.qml
"""
FAUX = {
    "Memo.qml": """pragma Singleton
import QtQuick
QtObject {
    property var disque: null
    function lire(nom, cb) { cb(disque) }
    function ecrire(nom, valeur) { console.log("ECRIT " + JSON.stringify(valeur)) }
}""",
    "Notifs.qml": """pragma Singleton
import QtQuick
QtObject { function rappeler(texte) { console.log("RAPPEL " + texte) } }""",
    "Etat.qml": """pragma Singleton
import QtQuick
QtObject { property bool ecranVu: false }""",
    "Reglages.qml": """pragma Singleton
import QtQuick
QtObject { property bool en: false }""",
}
SHELL = """import QtQuick
import Quickshell
ShellRoot {
    Timer {
        interval: 50; running: true
        onTriggered: {
            var due = Date.now() - 60000, futur = Date.now() + 3600000
            Memo.disque = [{ id: "a", texte: "echu pendant l'arret", due: due }, { id: "b", texte: "plus tard", due: futur }, { id: 7 }]
            Rappels.demarrer(); Rappels.demarrer()
            console.log("NOMBRE " + Rappels.nombre)
            var a = Rappels.analyser("dans 2 h sortir")
            console.log("ANALYSE " + a.ok + " " + a.texte)
            console.log("CREE " + Rappels.creer(a.texte, a.due) + " " + Rappels.nombre)
            Rappels.supprimer("b")
            console.log("APRES " + Rappels.nombre + " " + Rappels.liste.map(x => x.texte).join("|"))
            // veille simulée : l'échu reste dans la liste (minuteur non tiré) ; au retour de l'écran il est montré une seule fois
            Rappels.liste = [{ id: "v", texte: "echu en veille", due: Date.now() - 1000 }]
            console.log("AVANT " + Rappels.nombre)
            Etat.ecranVu = true; Etat.ecranVu = false; Etat.ecranVu = true
            console.log("APRESVEILLE " + Rappels.nombre)
            Qt.quit()
        }
    }
}"""


@unittest.skipUnless(QS, "qs absent")
class Singleton(unittest.TestCase):
    def test_echu_montre_une_fois_creation_suppression(self):
        with tempfile.TemporaryDirectory(dir="/tmp") as t:
            q = Path(t) / "q"; q.mkdir()
            shutil.copy2(QML / "Rappels.qml", q); shutil.copy2(QML / "Rappels.js", q)
            for n, c in FAUX.items():
                (q / n).write_text(c)
            (q / "qmldir").write_text(QMLDIR); (q / "shell.qml").write_text(SHELL)
            home = Path(t) / "h"; run = home / "run"; run.mkdir(parents=True, mode=0o700)
            env = {"PATH": os.environ["PATH"], "HOME": str(home), "XDG_CONFIG_HOME": str(home / "c"),
                   "XDG_STATE_HOME": str(home / "s"), "XDG_CACHE_HOME": str(home / "k"), "XDG_RUNTIME_DIR": str(run),
                   "QT_QPA_PLATFORM": "offscreen"}
            r = subprocess.run([QS, "--no-color", "-p", str(q / "shell.qml")], env=env, capture_output=True, text=True, timeout=60)
            sortie = r.stdout + r.stderr
        self.assertEqual(sortie.count("RAPPEL echu pendant l'arret"), 1, sortie)   # affiché une seule fois (2 appels de demarrer)
        self.assertNotIn("RAPPEL plus tard", sortie)
        self.assertIn("NOMBRE 1", sortie)                                             # l'échu est retiré, l'intrus ignoré
        self.assertIn("ANALYSE true sortir", sortie)
        self.assertIn("CREE true 2", sortie)
        self.assertIn("APRES 1 sortir", sortie)
        self.assertIn("AVANT 1", sortie)                                              # échu avec l'écran éteint : pas perdu
        self.assertEqual(sortie.count("RAPPEL echu en veille"), 1, sortie)            # montré une seule fois au retour de l'écran
        self.assertIn("APRESVEILLE 0", sortie)


if __name__ == "__main__":
    unittest.main()

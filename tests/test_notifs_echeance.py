"""Prochaine échéance de Notifs (NotifsEcheance.js) : fonctions pures, évaluées sous node, fuseau UTC."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

QML = Path(__file__).resolve().parents[1] / "home/.config/quickshell/nc-ile"
NODE = shutil.which("node")

# Le .js est une bibliothèque Quickshell (« .pragma library ») : on retire cette ligne pour l'évaluer sous node
PILOTE = """
const fs = require("fs"), vm = require("vm")
const src = fs.readFileSync(process.argv[2], "utf8").replace(/^\\.pragma library$/m, "")
const ctx = vm.createContext({ Array, Math, Date, String, JSON, isFinite, parseInt })
vm.runInContext(src, ctx)
console.log(JSON.stringify(vm.runInContext(process.argv[3], ctx)))
"""


def js(expr):
    with tempfile.TemporaryDirectory() as t:
        p = Path(t) / "pilote.js"; p.write_text(PILOTE)
        r = subprocess.run([NODE, str(p), str(QML / "NotifsEcheance.js"), expr], capture_output=True, text=True,
                           env={"PATH": os.environ["PATH"], "TZ": "UTC"}, timeout=30)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def h(jour, heure, minute=0):
    return f"Date.UTC(2026, 10, {jour}, {heure}, {minute}, 0)"


def prochaine(actif, debut, fin, dues, maintenant):
    return js(f"prochaine({json.dumps(actif)}, {json.dumps(debut)}, {json.dumps(fin)}, [{','.join(dues)}], {maintenant})")


@unittest.skipUnless(NODE, "node absent")
class Echeance(unittest.TestCase):
    def test_rien_donne_aucune_echeance(self):
        self.assertIsNone(prochaine(False, "22:00", "07:00", [], h(10, 12)))
        self.assertIsNone(prochaine(True, "22:00", "22:00", [], h(10, 12)))       # plage vide

    def test_plage_de_nuit(self):
        soir, matin = js(h(10, 22)), js(h(11, 7))
        for maintenant, attendu in ((h(10, 21, 59), soir), (h(10, 23), matin), (h(11, 6, 59), matin), (h(10, 12), soir)):
            with self.subTest(maintenant):
                self.assertEqual(prochaine(True, "22:00", "07:00", [], maintenant), attendu)

    def test_plage_de_jour(self):
        self.assertEqual(prochaine(True, "09:00", "17:00", [], h(10, 12)), js(h(10, 17)))
        self.assertEqual(prochaine(True, "09:00", "17:00", [], h(10, 18)), js(h(11, 9)))

    def test_pile_a_la_limite_va_a_la_suivante(self):
        self.assertEqual(prochaine(True, "22:00", "07:00", [], h(10, 22)), js(h(11, 7)))

    def test_report_proche_devant_plage_lointaine(self):
        self.assertEqual(prochaine(True, "22:00", "07:00", [f"{h(10, 12)} + 15 * 60000"], h(10, 12)), js(h(10, 12, 15)))

    def test_report_seul_et_valeurs_invalides(self):
        self.assertEqual(prochaine(False, "22:00", "07:00", [h(10, 13), "NaN", "'x'"], h(10, 12)), js(h(10, 13)))

    def test_echeance_passee_tire_une_fois_apres_une_seconde(self):
        self.assertEqual(js(f"delai({h(10, 11)}, {h(10, 12)})"), 1000)
        self.assertEqual(js(f"delai({h(10, 12)}, {h(10, 12)})"), 1000)

    def test_delai_normal(self):
        self.assertEqual(js(f"delai({h(10, 13)}, {h(10, 12)})"), 3600000)

    def test_delai_borne_a_2_puissance_31(self):
        self.assertEqual(js(f"delai({h(10, 12)} + 40 * 86400000, {h(10, 12)})"), 2147483647)


if __name__ == "__main__":
    unittest.main()

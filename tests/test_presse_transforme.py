"""Coller transformé (page Presse-papiers) : les fonctions pures de PresseTransforme.js (évaluées par node, saut si node
manque), puis leur branchement : copie par recopier(), jamais sur une entrée hors de l'historique (un secret n'y entre pas)."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from tests import _isolation  # noqa: F401

REPO = Path(__file__).resolve().parents[1]
QML = REPO / "home/.config/quickshell/nc-ile"
PRESSE = (QML / "Presse.qml").read_text()
PAPIERS = (QML / "PressePapiers.qml").read_text()
NODE = shutil.which("node")
PILOTE = """
const fs = require("fs"), vm = require("vm")
const src = fs.readFileSync(process.argv[2], "utf8").replace(/^\\.pragma library$/m, "")
const ctx = vm.createContext({})
vm.runInContext(src, ctx)
console.log(JSON.stringify([vm.runInContext(process.argv[3], ctx)]))
"""


def js(expr):
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "pilote.js"
        p.write_text(PILOTE)
        r = subprocess.run([NODE, str(p), str(QML / "PresseTransforme.js"), expr], capture_output=True, text=True,
                           env={"PATH": os.environ["PATH"]}, timeout=30)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)[0]


@unittest.skipUnless(NODE, "node absent")
class Fonctions(unittest.TestCase):
    def test_minuscules_majuscules_accents(self):
        self.assertEqual(js('[appliquer("min", "ÉCOLE Été"), appliquer("maj", "école été")]'), ["école été", "ÉCOLE ÉTÉ"])
        self.assertEqual(js('appliquer("maj", "straße")'), "STRASSE")

    def test_sans_effet_pas_propose(self):
        self.assertEqual(js('[proposees("abc"), proposees("ABC"), proposees("Ab c")]'), [["maj"], ["min"], ["min", "maj"]])
        self.assertEqual(js('proposees("123")'), [])

    def test_json_objet_et_tableau(self):
        self.assertEqual(js('appliquer("json", \'{"1":[1,2]}\')'), '{\n  "1": [\n    1,\n    2\n  ]\n}')
        self.assertEqual(js('appliquer("json", "[1]")'), "[\n  1\n]")
        self.assertEqual(js('proposees(\'{"1":1}\')'), ["json"])

    def test_json_invalide_ou_scalaire_non_propose(self):
        for t in ('{a:1}', '', '42', '1e3', ' 42 ', '"\\u0041"', '"x"', 'null', 'true', '{"1":1', "[1,]"):
            self.assertIsNone(js("appliquer('json', %s)" % json.dumps(t)), t)

    def test_json_deja_mis_en_forme_non_propose(self):
        self.assertIsNone(js('appliquer("json", "{\\n  \\"1\\": 1\\n}")'))

    def test_texte_vide_ou_trop_long(self):
        self.assertEqual(js('[appliquer("min", ""), appliquer("maj", null), appliquer("zzz", "a")]'), [None, None, None])
        self.assertEqual(js('appliquer("maj", "a".repeat(100000)).length'), 100000)
        self.assertIsNone(js('appliquer("maj", "a".repeat(100001))'))
        self.assertEqual(js('proposees("{\\"a\\":\\"" + "x".repeat(100000) + "\\"}")'), [])


class Branchement(unittest.TestCase):
    def test_copie_par_recopier(self):
        corps = PAPIERS.split("function transformer(e, mode)")[1].split("\n    }")[0]
        self.assertIn("recopier({ genre: \"texte\", texte: r })", corps)
        self.assertNotIn("execDetached", corps)

    def test_seulement_les_entrees_de_l_historique(self):
        ligne = [l for l in PAPIERS.splitlines() if "function transformations(e)" in l][0]
        self.assertIn('e.genre === "texte"', ligne)
        self.assertIn("entrees.some(x => x.id === e.id", ligne)

    def test_boutons_gardes_dans_la_page(self):
        self.assertIn("PressePapiers.transformations(modelData)", PRESSE)
        self.assertIn("image || p.masque ?", PRESSE)
        for m in ("min", "maj", "json"):
            self.assertIn('visible: el.transfos.indexOf("%s") >= 0' % m, PRESSE)
        self.assertIn("PressePapiers.transformer(el.modelData, action.modelData.id)", PRESSE)

    def test_documente(self):
        self.assertIn("Coller transformé", (REPO / "README.md").read_text())


if __name__ == "__main__":
    unittest.main()

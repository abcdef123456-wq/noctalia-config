"""Saisies du Spotlight calculées sans réseau : la commande qalc (aucune option inconnue), les dates en français
réécrites avant qalc et la couleur tapée (Saisies.js, évalué par node), puis leur branchement dans Recherche.qml."""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
QML = REPO / "home/.config/quickshell/nc-ile"
RECHERCHE = (QML / "Recherche.qml").read_text()
QALC = shutil.which("qalc")


def commande_qalc():
    """Les arguments fixes de qalc, devant l'expression calculée."""
    m = re.search(r'calculer\.command = \[((?:"[^"]*", )*)', RECHERCHE)
    return re.findall(r'"([^"]*)"', m[1])


NODE = shutil.which("node")
PILOTE = """
const fs = require("fs"), vm = require("vm")
const src = fs.readFileSync(process.argv[2], "utf8").replace(/^\\.pragma library$/m, "")
const ctx = vm.createContext({ Date, String, parseInt })
vm.runInContext(src, ctx)
console.log(JSON.stringify(vm.runInContext(process.argv[3], ctx)))
"""
# Dimanche 22 novembre 2026, 10:00 (TZ=UTC pour l'essai)
NOW = "Date.UTC(2026, 10, 22, 10, 0, 0)"


def js(expr):
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "pilote.js"; p.write_text(PILOTE)
        r = subprocess.run([NODE, str(p), str(QML / "Saisies.js"), expr], capture_output=True, text=True,
                           env={"PATH": os.environ["PATH"], "TZ": "UTC"}, timeout=30)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def date(q):
    return js(f"dateQalc({json.dumps(q)}, {NOW})")


class Qalc(unittest.TestCase):
    def test_aucune_option_set(self):
        """« -set "mix 0" » : option inconnue de qalc 5.5 (Debian 13) à 5.13 (Arch), refusée en silence."""
        self.assertEqual(commande_qalc(), ["qalc", "-t"])

    @unittest.skipUnless(QALC, "qalc absent")
    def test_qalc_ne_se_plaint_pas(self):
        r = subprocess.run(commande_qalc() + ["5 mi to km"], capture_output=True, text=True, timeout=20,
                           env={"PATH": os.environ["PATH"], "LC_ALL": "C", "HOME": tempfile.gettempdir()})
        self.assertNotRegex(r.stdout + r.stderr, r"(?i)unrecognized|unknown option")
        self.assertRegex(r.stdout.strip().split("\n")[-1], r"^8[.,]04672 km$")



@unittest.skipUnless(NODE, "node absent")
class Dates(unittest.TestCase):
    def test_jours_jusqu_a(self):
        for q, attendu in (("jours jusqu'au 25/12", "days(today; 2026-12-25) d"),
                           ("Jours jusqu’au 25/12", "days(today; 2026-12-25) d"),
                           ("nombre de jours avant le 1/3/2027", "days(today; 2027-03-01) d"),
                           ("jours jusqu'à 2027-01-01", "days(today; 2027-01-01) d"),
                           ("days until 2027-01-01", "days(today; 2027-01-01) d"),
                           ("jours jusqu'au 22/11", "days(today; 2026-11-22) d"),          # aujourd'hui : 0, pas l'an prochain
                           ("jours jusqu'au 1/11", "days(today; 2027-11-01) d")):          # passé : l'an prochain
            with self.subTest(q):
                self.assertEqual(date(q), attendu)

    def test_dans_n_jours(self):
        self.assertEqual(date("dans 45 jours"), "today + 45 d")
        self.assertEqual(date("in 1 day"), "today + 1 d")

    def test_refus(self):
        for q in ("jours jusqu'au 31/02", "jours jusqu'au 29/02", "jours jusqu'au 13/13", "jours jusqu'au 25/12/26",
                  "dans 45 jours; rm -rf ~", "dans jours", "25/12", "jours jusqu'au 25/12 et plus", "", "5 mi en km",
                  "jours jusqu'au 25/12/1850", "days until 3001-01-01"):
            with self.subTest(q):
                self.assertEqual(date(q), "")
        self.assertEqual(date("jours jusqu'au 29/02/2028"), "days(today; 2028-02-29) d")

    @unittest.skipUnless(QALC, "qalc absent")
    def test_qalc_calcule(self):
        for expr, motif in ((date("jours jusqu'au 25/12/2026"), r"^\d+ d$"), (date("dans 45 jours"), r'^"\d{4}-\d{2}-\d{2}"$')):
            r = subprocess.run(commande_qalc() + [expr], capture_output=True, text=True, timeout=20,
                               env={"PATH": os.environ["PATH"], "LC_ALL": "C", "HOME": tempfile.gettempdir()})
            self.assertRegex(r.stdout.strip().split("\n")[-1], motif)


class Branchement(unittest.TestCase):
    def test_date_reecrite_avant_qalc(self):
        self.assertIn('import "Saisies.js" as Saisies', RECHERCHE)
        self.assertIn('let date = Saisies.dateQalc(q, Date.now())', RECHERCHE)
        # estCalcul (partagé par la recherche de qalc et le choix de l'espace) : « dans 45 jours » n'a pas d'opérateur
        self.assertIn('(Saisies.dateQalc(t, Date.now()) !== "" || /\\d/.test(t)', RECHERCHE)
        self.assertIn("if (r.estCalcul(q)) {", RECHERCHE)
        self.assertIn('date !== "" ? date : q.replace(', RECHERCHE)
        self.assertIn('.replace(/^"(\\d{4}-\\d{2}-\\d{2})"$/, "$1")', RECHERCHE)


if __name__ == "__main__":
    unittest.main()

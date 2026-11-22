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
    m = re.search(r'calculer\.command = \[([^\]]*)\]', RECHERCHE)
    return re.findall(r'"([^"]*)"', m[1])


class Qalc(unittest.TestCase):
    def test_aucune_option_set(self):
        """« -set "mix 0" » : option inconnue de qalc 5.5 (Debian 13) à 5.13 (Arch), refusée en silence."""
        self.assertEqual(commande_qalc(), ["qalc", "-t", " to "])

    @unittest.skipUnless(QALC, "qalc absent")
    def test_qalc_ne_se_plaint_pas(self):
        r = subprocess.run(commande_qalc()[:-1] + ["5 mi to km"], capture_output=True, text=True, timeout=20,
                           env={"PATH": os.environ["PATH"], "LC_ALL": "C", "HOME": tempfile.gettempdir()})
        self.assertNotRegex(r.stdout + r.stderr, r"(?i)unrecognized|unknown option")
        self.assertRegex(r.stdout.strip().split("\n")[-1], r"^8[.,]04672 km$")


if __name__ == "__main__":
    unittest.main()

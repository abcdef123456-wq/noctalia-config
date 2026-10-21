"""export.sh reconstruit home/ depuis la seule liste HOME_FILES : un fichier de home/ qui n'y est pas serait supprimé
du dépôt au prochain export (revue EXP-01 : nc-ia, nc-session et 11 autres l'étaient)."""
from pathlib import Path
import re
import subprocess
import unittest

REPO = Path(__file__).resolve().parents[1]


class Export(unittest.TestCase):
    def test_tout_home_est_dans_home_files(self):
        liste = re.search(r"HOME_FILES=\((.*?)\n\)", (REPO / "export.sh").read_text(), re.S)[1].split()
        r = subprocess.run(["git", "-C", str(REPO), "ls-files", "-z", "--cached", "--others", "--exclude-standard", "home"],
                           capture_output=True, text=True)
        if r.returncode != 0:
            self.skipTest("pas un dépôt git")
        couvert = lambda f: any(f == e or f.startswith(e.rstrip("/") + "/") for e in liste)
        manque = [f[5:] for f in r.stdout.split("\0") if f and not couvert(f[5:])]
        self.assertEqual(manque, [], "à ajouter à HOME_FILES dans export.sh")

"""install.sh : la règle sudo de « Protéger la batterie » autorise trois commandes exactes (on, off, etat) de
nc-limite-charge, jamais n'importe quel argument. La ligne est lue dans install.sh lui-même ; visudo (lecture d'un
fichier temporaire, sans sudo) en vérifie la syntaxe quand il est installé."""
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
INSTALL = (REPO / "install.sh").read_text(encoding="utf-8")


def regle():
    lim = re.search(r"^\s*lim=(\S+)$", INSTALL, re.M).group(1)
    ligne = re.search(r'^\s*ligne="(.*NOPASSWD:.*)"$', INSTALL, re.M).group(1)
    return ligne.replace("$(id -un)", "alice").replace("$lim", lim), lim


class RegleSudo(unittest.TestCase):
    def test_trois_commandes_exactes(self):
        ligne, lim = regle()
        self.assertEqual(lim, "/usr/local/bin/nc-limite-charge")
        liste = ligne.split("NOPASSWD:", 1)[1]
        commandes = [c.strip() for c in liste.split(",")]
        self.assertEqual(commandes, [f"{lim} on", f"{lim} off", f"{lim} etat"])
        self.assertNotRegex(ligne, r"nc-limite-charge\s*(,|$)", "pas de commande sans argument (tout serait permis)")
        self.assertNotIn("*", ligne)
        self.assertNotIn("ALL, ", ligne)

    def test_arguments_acceptes_par_l_utilitaire(self):
        # Les trois arguments existent bien dans nc-limite-charge
        source = (REPO / "system/nc-limite-charge").read_text(encoding="utf-8")
        self.assertRegex(source, r"etat\|state\|status\)")
        self.assertRegex(source, r"on\|1\)")
        self.assertRegex(source, r"off\|0\)")

    @unittest.skipUnless(shutil.which("visudo"), "visudo requis")
    def test_syntaxe_validee_par_visudo(self):
        ligne, _ = regle()
        with tempfile.TemporaryDirectory(prefix="nc-sudoers-") as d:
            f = Path(d) / "regle"
            f.write_text("# test\n" + ligne + "\n")
            f.chmod(0o440)
            r = subprocess.run(["visudo", "-cf", str(f)], capture_output=True, text=True, timeout=20)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            f.unlink()
            f.write_text("alice ALL=(root) NOPASSWD: /usr/local/bin/nc-limite-charge on,, off\n")
            r = subprocess.run(["visudo", "-cf", str(f)], capture_output=True, text=True, timeout=20)
            self.assertNotEqual(r.returncode, 0)


if __name__ == "__main__":
    unittest.main()

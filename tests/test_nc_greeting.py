"""nc-greeting dans un panneau étroit : jamais de mot coupé en deux. Faux fastfetch (il imprime des lignes fixes) et
HOME temporaire."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

BIN = Path(__file__).resolve().parents[1] / "home/.local/bin"


class Accueil(unittest.TestCase):
    def lancer(self, cols, lignes, texte):
        with tempfile.TemporaryDirectory(prefix="nc-greeting-") as d:
            home = Path(d).resolve()
            faux = home / "faux"
            faux.mkdir()
            f = faux / "fastfetch"
            f.write_text("#!/bin/sh\ncat <<'EOT'\n" + texte + "EOT\n")
            f.chmod(0o755)
            env = dict(HOME=str(home), XDG_CONFIG_HOME=str(home / ".config"), XDG_CACHE_HOME=str(home / ".cache"),
                       TMPDIR=str(home), PATH=f"{faux}:/usr/bin:/bin")
            r = subprocess.run([str(BIN / "nc-greeting"), str(cols), str(lignes)], env=env, capture_output=True,
                               text=True, timeout=30, stdin=subprocess.DEVNULL)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout.replace("\033[0m", "").splitlines()

    def test_aucun_mot_coupe_dans_un_panneau_etroit(self):
        texte = "CPU: Intel Core Ultra Performance cores\nRAM: 16 Go\nSystème: Arch Linux Performance\n"
        for cols in range(34, 60):
            for l in self.lancer(cols, 20, texte):
                self.assertLessEqual(len(l), cols - 1, l)
                self.assertNotIn(l.split(" ")[-1], ("Perfor", "Performan"), l)
                self.assertTrue(l in texte.splitlines() or any(t.startswith(l + " ") for t in texte.splitlines()), repr(l))

    def test_ligne_qui_tient_reste_entiere(self):
        self.assertEqual(self.lancer(80, 20, "RAM: 16 Go\n")[:1], ["RAM: 16 Go"])

    def test_trop_petit_rien(self):
        self.assertEqual(self.lancer(30, 20, "RAM: 16 Go\n"), [])


if __name__ == "__main__":
    unittest.main()

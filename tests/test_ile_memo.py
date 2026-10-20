"""nc-ile-memo : fichiers privés (0600) écrits d'un bloc, JSON seulement, images PNG, rien du contenu sur stderr."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "home/.local/bin/nc-ile-memo"
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


class Memo(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.etat = Path(self.tmp.name) / "state"
        self.env = dict(HOME=self.tmp.name, XDG_STATE_HOME=str(self.etat), PATH="/usr/bin:/bin")

    def lancer(self, *args, entree=b""):
        return subprocess.run([str(SCRIPT), *args], input=entree, env=self.env, capture_output=True, timeout=10)

    def test_ecrire_lire_oublier(self):
        self.assertEqual(self.lancer("lire", "centre").stdout, b"null\n")
        valeur = {"ordre": ["musique", "connexions"], "masques": ["jeu"], "secret": "ne pas journaliser $(x)"}
        r = self.lancer("ecrire", "centre", entree=json.dumps(valeur).encode())
        self.assertEqual((r.returncode, r.stderr), (0, b""))
        f = self.etat / "nc/ile/centre.json"
        self.assertEqual(f.stat().st_mode & 0o777, 0o600)
        self.assertEqual((self.etat / "nc/ile").stat().st_mode & 0o777, 0o700)
        self.assertEqual(json.loads(self.lancer("lire", "centre").stdout), valeur)
        self.assertEqual(sorted(p.name for p in f.parent.iterdir()), ["centre.json"], "pas de temporaire")
        r = self.lancer("ecrire", "centre", entree=b"{pas du json")
        self.assertEqual(r.returncode, 1)
        self.assertNotIn(b"pas du json", r.stderr)
        self.assertEqual(json.loads(self.lancer("lire", "centre").stdout), valeur, "une écriture refusée garde l'ancien")
        self.assertEqual(self.lancer("oublier", "centre").returncode, 0)
        self.assertEqual(self.lancer("lire", "centre").stdout, b"null\n")
        for mauvais in ("../x", "A", "a b", ""):
            self.assertEqual(self.lancer("lire", mauvais).returncode, 1)

    def test_images(self):
        r = self.lancer("image", "abc123", entree=PNG)
        self.assertEqual(r.returncode, 0, r.stderr)
        chemin = Path(r.stdout.decode().strip())
        self.assertEqual(chemin, self.etat / "nc/ile/images/abc123.png")
        self.assertEqual(chemin.stat().st_mode & 0o777, 0o600)
        self.assertEqual(chemin.read_bytes(), PNG)
        self.assertEqual(self.lancer("image", "pasimage", entree=b"GIF89a").returncode, 1)
        self.lancer("image", "def456", entree=PNG)
        self.assertEqual(self.lancer("images-garder", "def456").returncode, 0)
        self.assertEqual(sorted(p.name for p in chemin.parent.iterdir()), ["abc123.png", "def456.png"], "une image toute fraîche n'est jamais purgée")
        vieux = os.stat(chemin).st_mtime - 600
        os.utime(chemin, (vieux, vieux))
        self.assertEqual(self.lancer("images-garder", "def456").returncode, 0)
        self.assertEqual(sorted(p.name for p in chemin.parent.iterdir()), ["def456.png"], "une orpheline d'il y a dix minutes est purgée")
        self.assertEqual(self.lancer("images-supprimer", "def456", "../x").returncode, 0)
        self.assertEqual(list(chemin.parent.iterdir()), [])


if __name__ == "__main__":
    unittest.main()

"""NX2-b : dépôt installé sans .git (NixOS : /nix/store, lecture seule). Un fichier VERSION à la racine
(« sha court AAAA-MM-JJ », écrit à la construction) donne la version à nc-diag ; nc-maj dit que le gestionnaire du système
met à jour, sans erreur. Une ligne piégée est refusée ; sans VERSION, rien ne change. Tout dans un dossier temporaire,
HOME isolé, aucune modification de os.environ."""
from importlib.machinery import SourceFileLoader
from importlib.util import module_from_spec, spec_from_loader
from pathlib import Path
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock

REPO = Path(__file__).resolve().parents[1]
DIAG = REPO / "home/.local/bin/nc-diag"
NC_MAJ = REPO / "home/.local/bin/nc-maj"

PIEGES = ["$(id) 2026-01-01\n", "abc1234 2026-01-01\nabc1234 2026-01-02\n", "abc1234 2026-01-01\x1b[31m\n",
          "abc1234\n", "abc123 2026-01-01\n", "ABC1234 2026-01-01\n", "abc1234 2026-1-1\n", "abc1234 2026-01-01 x\n",
          "a" * 41 + " 2026-01-01\n", "a" * 100 + " 2026-01-01\n", "", "\n"]


def motif(source, nom):
    m = re.search(nom + r"""\s*=\s*r?(["'])(.+?)\1""", source.read_text())
    return m.group(2) if m else None


class Base(unittest.TestCase):
    def setUp(self):
        d = tempfile.TemporaryDirectory(prefix="nc-version-")
        self.addCleanup(d.cleanup)
        self.d = Path(d.name)
        self.depot = self.d / "depot"
        self.depot.mkdir()
        self.home = self.d / "home"
        (self.home / ".config/nc").mkdir(parents=True)
        (self.home / ".config/nc/depot").write_text(str(self.depot))
        (self.home / ".local/bin").mkdir(parents=True)  # nc-maj charge nc-langue depuis le HOME
        shutil.copy(REPO / "home/.local/bin/nc-langue", self.home / ".local/bin/nc-langue")

    def version(self, texte):
        (self.depot / "VERSION").write_text(texte)


class Diag(Base):
    def setUp(self):
        super().setUp()
        p = mock.patch.dict(os.environ, NC_LANGUE="fr")
        p.start()
        self.addCleanup(p.stop)
        spec = spec_from_loader("nc_diag_v", SourceFileLoader("nc_diag_v", str(DIAG)))
        self.mod = module_from_spec(spec)
        spec.loader.exec_module(self.mod)
        self.mod.EN = False
        self.mod.T = lambda fr, en: fr

    def bilan(self):
        b = self.mod.Bilan(False)
        self.mod.ligne_depot(b, str(self.depot))
        return b

    def test_avec_git_inchange(self):
        env = dict(os.environ, HOME=str(self.home), GIT_AUTHOR_NAME="T", GIT_AUTHOR_EMAIL="t@exemple.invalid",
                   GIT_COMMITTER_NAME="T", GIT_COMMITTER_EMAIL="t@exemple.invalid")
        for a in (["init", "-q"], ["commit", "-q", "--allow-empty", "-m", "x"]):
            subprocess.run(["git", "-C", str(self.depot), *a], env=env, check=True, capture_output=True)
        self.version("abc1234 2026-01-01\n")  # ignoré : le .git passe avant
        b = self.bilan()
        self.assertEqual(b.nb_ok, 1)
        self.assertNotIn("abc1234", b.lignes[0][1])
        self.assertIn("version", b.lignes[0][1])

    def test_sans_git_avec_version(self):
        self.version("0a1b2c3d 2026-11-17\n")
        b = self.bilan()
        self.assertEqual((b.nb_ok, b.attention), (1, 0))
        self.assertIn("0a1b2c3d 2026-11-17", b.lignes[0][1])

    def test_sans_git_ni_version(self):
        b = self.bilan()
        self.assertEqual((b.nb_ok, b.attention), (0, 1))
        self.assertIn("introuvable", b.lignes[0][1])

    def test_lignes_piegees_refusees(self):
        for texte in PIEGES:
            with self.subTest(texte=texte[:30]):
                self.version(texte)
                b = self.bilan()
                self.assertEqual((b.nb_ok, b.attention), (0, 1))
                self.assertNotIn("$(id)", "".join(l[1] for l in b.lignes))


class Maj(Base):
    def maj(self, *a):
        env = {"PATH": os.environ["PATH"], "HOME": str(self.home), "XDG_CONFIG_HOME": str(self.home / ".config"),
               "XDG_CACHE_HOME": str(self.home / ".cache"), "TMPDIR": str(self.d), "NC_LANGUE": "fr"}
        return subprocess.run(["bash", str(NC_MAJ), *a], env=env, capture_output=True, text=True, timeout=60,
                              stdin=subprocess.DEVNULL)

    def test_sans_git_avec_version_sort_sans_erreur(self):
        self.version("0a1b2c3d 2026-11-17\n")
        r = self.maj("--no-system")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("gestionnaire du système", r.stdout + r.stderr)
        self.assertNotIn("introuvable", r.stdout + r.stderr)

    def test_anglais(self):
        self.version("0a1b2c3d 2026-11-17\n")
        env = {"PATH": os.environ["PATH"], "HOME": str(self.home), "NC_LANGUE": "en"}
        r = subprocess.run(["bash", str(NC_MAJ)], env=env, capture_output=True, text=True, timeout=60,
                           stdin=subprocess.DEVNULL)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("system package manager", r.stdout + r.stderr)

    def test_sans_version_inchange(self):
        r = self.maj("--no-system")
        self.assertEqual(r.returncode, 1)
        self.assertIn("introuvable", r.stdout + r.stderr)

    def test_version_piegee_refusee(self):
        for texte in PIEGES:
            with self.subTest(texte=texte[:30]):
                self.version(texte)
                r = self.maj("--no-system")
                self.assertEqual(r.returncode, 1, r.stdout + r.stderr)

    def test_verifier_sans_git_silencieux(self):
        self.version("0a1b2c3d 2026-11-17\n")
        r = self.maj("verifier")
        self.assertEqual((r.returncode, r.stdout), (0, ""))


class MotifIdentique(unittest.TestCase):
    def test_meme_regex_dans_les_deux_sources(self):
        a, b = motif(DIAG, "MOTIF_VERSION"), motif(NC_MAJ, "motif_version")
        self.assertTrue(a, "motif absent de nc-diag")
        self.assertEqual(a, b)


if __name__ == "__main__":
    unittest.main()

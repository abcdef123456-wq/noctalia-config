"""Le workflow GitHub Actions (.github/workflows/tests.yml) garde ses garanties.

Aucun réseau : le fichier est lu sur le disque (module yaml s'il existe, sinon lecture par motifs).
"""
import re
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
FICHIER = RACINE / ".github" / "workflows" / "tests.yml"
IMAGES = {"archlinux:latest", "debian:trixie", "fedora:44", "opensuse/tumbleweed"}

try:
    import yaml
except ImportError:  # pas de PyYAML : on se rabat sur les motifs
    yaml = None


def charge():
    return yaml.safe_load(FICHIER.read_text(encoding="utf-8")) if yaml else None


class WorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not FICHIER.is_file():
            raise unittest.SkipTest("pas de .github/workflows/tests.yml (export sans CI)")
        cls.texte = FICHIER.read_text(encoding="utf-8")
        cls.doc = charge()

    def test_permissions_lecture_seule(self):
        if self.doc is not None:
            self.assertEqual(self.doc.get("permissions"), {"contents": "read"})
            for job in self.doc["jobs"].values():
                self.assertNotIn("permissions", job)
        else:
            self.assertRegex(self.texte, r"(?m)^permissions:\n  contents: read\n(?!  )")

    def test_declencheurs(self):
        if self.doc is not None:
            on = self.doc.get("on", self.doc.get(True))
            self.assertEqual(set(on), {"push", "pull_request", "workflow_dispatch"})
            self.assertEqual(on["push"]["branches"], ["main"])
            self.assertEqual(on["pull_request"]["branches"], ["main"])
        else:
            for mot in ("push:", "pull_request:", "workflow_dispatch:", "branches: [main]"):
                self.assertIn(mot, self.texte)

    def test_actions_uniquement_checkout_epingle(self):
        usages = re.findall(r"(?m)^\s*(?:-\s*)?uses:\s*(\S+)", self.texte)
        self.assertTrue(usages, "le checkout est attendu")
        for u in usages:
            self.assertRegex(u, r"^actions/checkout@[0-9a-f]{40}$", f"action non épinglée ou tierce : {u}")
        for ligne in self.texte.splitlines():
            if "uses:" in ligne:
                self.assertRegex(ligne, r"#\s*v\d", "la version doit figurer en commentaire")

    def test_images(self):
        if self.doc is not None:
            images = {m["image"] for job in self.doc["jobs"].values() for m in job["strategy"]["matrix"]["include"]}
            self.assertEqual(images, IMAGES)
            for job in self.doc["jobs"].values():
                self.assertEqual(job["container"]["image"], "${{ matrix.image }}")
                self.assertEqual(job["runs-on"], "ubuntu-latest")
        else:
            for i in IMAGES:
                self.assertIn(f"image: {i}", self.texte)

    def test_delais_et_matrice(self):
        if self.doc is not None:
            for job in self.doc["jobs"].values():
                self.assertEqual(job["timeout-minutes"], 60)
                self.assertIs(job["strategy"]["fail-fast"], False)
        else:
            self.assertIn("timeout-minutes: 60", self.texte)
            self.assertIn("fail-fast: false", self.texte)

    def test_concurrence(self):
        if self.doc is not None:
            c = self.doc["concurrency"]
            self.assertEqual(c["group"], "tests-${{ github.ref }}")
            self.assertIs(c["cancel-in-progress"], True)
        else:
            self.assertIn("group: tests-${{ github.ref }}", self.texte)
            self.assertIn("cancel-in-progress: true", self.texte)

    def test_aucun_secret(self):
        sans_commentaires = "\n".join(re.sub(r"(^|\s)#.*", "", l) for l in self.texte.splitlines())
        self.assertNotIn("secrets.", sans_commentaires)
        self.assertNotIn("github.token", sans_commentaires)
        self.assertNotIn("GITHUB_TOKEN", sans_commentaires)

    def test_commande_de_test_et_git_avant_checkout(self):
        self.assertIn("python3 -m unittest discover -s tests -t .", self.texte)
        self.assertIn("git config --global --add safe.directory", self.texte)
        self.assertLess(self.texte.index("matrix.install"), self.texte.index("actions/checkout@"))
        self.assertRegex(self.texte, r"install:.*\bgit\b")

    def test_jeton_pas_garde_par_checkout(self):
        # persist-credentials: false : le jeton du checkout ne reste pas dans .git/config, que les tests pourraient lire
        self.assertRegex(self.texte, r"uses: actions/checkout@[0-9a-f]{40}[^\n]*\n\s+with:\n\s+persist-credentials: false")

    def test_nom_lisible(self):
        self.assertIn("name: Tests (${{ matrix.image }})", self.texte)


if __name__ == "__main__":
    unittest.main()

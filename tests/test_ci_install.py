"""Le workflow .github/workflows/install.yml (installation réelle en conteneur) garde ses garanties.

Aucun réseau : le fichier est lu sur le disque (module yaml s'il existe, sinon lecture par motifs).
"""
import re
import subprocess
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
FICHIER = RACINE / ".github" / "workflows" / "install.yml"
VERIF = RACINE / "tests" / "verifier_installation.sh"
IMAGES = {"archlinux:latest", "debian:trixie", "fedora:44", "opensuse/tumbleweed"}
CHECKOUT = "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1"   # le même que tests.yml

try:
    import yaml
except ImportError:  # pas de PyYAML : on se rabat sur les motifs
    yaml = None


class InstallWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not FICHIER.is_file():
            raise unittest.SkipTest("pas de .github/workflows/install.yml (export sans CI)")
        cls.texte = FICHIER.read_text(encoding="utf-8")
        cls.doc = yaml.safe_load(cls.texte) if yaml else None

    def test_bash_partout(self):
        # sh est dash dans l'image Debian : l'étape des secrets (<<<) et les autres tournent sous bash
        if self.doc is not None:
            self.assertEqual(self.doc["jobs"]["installation"].get("defaults", {}).get("run", {}).get("shell"), "bash")
        else:
            self.assertRegex(self.texte, r"defaults:\n\s+run:\n\s+shell: bash")

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
            self.assertEqual(set(on), {"schedule", "workflow_dispatch", "push"})
            self.assertEqual(on["push"]["branches"], ["main"])
            self.assertEqual(set(on["push"]["paths"]),
                             {"install.sh", ".github/workflows/install.yml", "tests/verifier_installation.sh"})
            self.assertEqual(len(on["schedule"]), 1)
            cron = on["schedule"][0]["cron"].split()
            self.assertEqual(len(cron), 5)
            # une fois par semaine : jour de la semaine fixe, heure fixe, ni "*" ni liste
            self.assertRegex(cron[4], r"^[0-6]$")
            self.assertRegex(cron[1], r"^\d+$")
            self.assertRegex(cron[2] + cron[3], r"^\*\*$")
        else:
            for mot in ("schedule:", "workflow_dispatch:", "push:", "branches: [main]", "paths:",
                        "- install.sh", "- tests/verifier_installation.sh"):
                self.assertIn(mot, self.texte)
            self.assertRegex(self.texte, r'cron: "\d+ \d+ \* \* [0-6]"')
        self.assertNotIn("pull_request", self.texte.replace("pull_request_target", "X"))   # jamais sur une PR

    def test_actions_epinglees(self):
        usages = re.findall(r"(?m)^\s*(?:-\s*)?uses:\s*(\S+)", self.texte)
        self.assertEqual(len([u for u in usages if u.startswith("actions/checkout@")]), 1)
        for u in usages:
            self.assertRegex(u, r"^actions/(checkout|upload-artifact)@[0-9a-f]{40}$", f"action non épinglée ou tierce : {u}")
        self.assertIn(CHECKOUT, self.texte, "même checkout épinglé que tests.yml")
        self.assertIn(CHECKOUT, (RACINE / ".github" / "workflows" / "tests.yml").read_text(encoding="utf-8"))
        for ligne in self.texte.splitlines():
            if "uses:" in ligne:
                self.assertRegex(ligne, r"#\s*v\d", "la version doit figurer en commentaire")

    def test_images_matrice_delai(self):
        if self.doc is not None:
            job = self.doc["jobs"]["installation"]
            self.assertEqual({m["image"] for m in job["strategy"]["matrix"]["include"]}, IMAGES)
            self.assertEqual(job["container"]["image"], "${{ matrix.image }}")
            self.assertEqual(job["runs-on"], "ubuntu-latest")
            self.assertIs(job["strategy"]["fail-fast"], False)
            self.assertLessEqual(job["timeout-minutes"], 90)
            self.assertGreaterEqual(job["timeout-minutes"], 30)
            for m in job["strategy"]["matrix"]["include"]:
                self.assertRegex(m["install"], r"\bgit\b")
                self.assertRegex(m["install"], r"\bsudo\b")
        else:
            for i in IMAGES:
                self.assertIn(f"image: {i}", self.texte)
            self.assertIn("fail-fast: false", self.texte)
            self.assertRegex(self.texte, r"timeout-minutes: \d+")

    def test_concurrence(self):
        if self.doc is not None:
            c = self.doc["concurrency"]
            self.assertEqual(c["group"], "install-${{ github.ref }}")
            self.assertIs(c["cancel-in-progress"], True)
        else:
            self.assertIn("group: install-${{ github.ref }}", self.texte)
            self.assertIn("cancel-in-progress: true", self.texte)

    def test_aucun_secret(self):
        sans_commentaires = "\n".join(re.sub(r"(^|\s)#.*", "", l) for l in self.texte.splitlines())
        self.assertNotIn("secrets.", sans_commentaires)
        self.assertNotIn("github.token", sans_commentaires)
        self.assertNotIn("GITHUB_TOKEN", sans_commentaires)

    def test_jeton_pas_garde_par_checkout(self):
        m = re.search(r"uses: actions/checkout@[0-9a-f]{40}[^\n]*\n\s+with:\n\s+persist-credentials: false", self.texte)
        self.assertTrue(m, "le checkout garde son jeton")

    def test_etapes_dans_l_ordre(self):
        t = self.texte
        marques = ["matrix.install", "actions/checkout@", "useradd -m ci", "NOPASSWD:ALL", "cp -a \"$GITHUB_WORKSPACE\"",
                   "./install.sh --oui </dev/null", "bash tests/verifier_installation.sh", "BEGIN [A-Z ]*PRIVATE KEY",
                   "actions/upload-artifact@"]
        pos = [t.index(m) for m in marques]
        self.assertEqual(pos, sorted(pos), "ordre : paquets, checkout, utilisateur, install, vérification, grep, téléversement")
        self.assertIn("NC_INSTALL_ARGS=--oui", t)
        self.assertNotIn("/usr/local/bin/pacman", t.replace("# ", ""), "plus de contournement pacman/zypper")
        self.assertNotIn("/usr/local/bin/zypper", t)
        self.assertIn("setsid", t)
        self.assertIn("timeout ", t)

    def test_journal_controle_avant_televersement(self):
        t = self.texte
        for mot in ("token", "jeton", "password", "key=", "PRIVATE KEY", "@[A-Za-z0-9-]+"):
            self.assertIn(mot, t, f"motif manquant dans le contrôle du journal : {mot}")
        if self.doc is not None:
            etapes = self.doc["jobs"]["installation"]["steps"]
            noms = [e.get("uses", "") for e in etapes]
            i = next(k for k, u in enumerate(noms) if u.startswith("actions/upload-artifact@"))
            controle = etapes[i - 1]
            self.assertEqual(controle.get("id"), "scan")
            self.assertTrue(controle["run"].strip().endswith("}"), "le contrôle doit pouvoir échouer")
            self.assertEqual(etapes[i]["if"], "always() && steps.scan.outcome == 'success'")
            self.assertEqual(etapes[i]["with"]["retention-days"], 14)
        else:
            self.assertIn("steps.scan.outcome == 'success'", t)

    def test_nom_lisible(self):
        self.assertIn("name: Installation (${{ matrix.image }})", self.texte)

    def test_verificateur_present_et_syntaxe(self):
        self.assertTrue(VERIF.is_file())
        r = subprocess.run(["bash", "-n", str(VERIF)], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        v = VERIF.read_text(encoding="utf-8")
        # ce que le script doit vérifier, d'après la demande du lot
        for mot in ("@[A-Z][A-Z0-9_]*@", "DEFAULT_(AUDIO_)?(SINK|SOURCE)", "nc-diag --json --rapide", "nc-reglages appliquer",
                    "luac -p", "hyprland.lua", "Traceback", "install.sh", "HYPR_MIN", "0.3"):
            self.assertIn(mot, v)
        self.assertNotRegex(v, r"/home/[a-z]+/(?!ci\b)", "pas de chemin personnel")


if __name__ == "__main__":
    unittest.main()

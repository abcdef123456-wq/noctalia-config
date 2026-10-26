"""nc-ia commit : le message d'un commit pour le diff INDEXÉ. Un faux dépôt git dans un dossier jetable et une IA factice
(le faux serveur Anthropic de test_ia) : codes 0 / 2 / 3 / 4, diff borné, sujets des derniers commits donnés en exemple,
binaires et lockfiles résumés par leur nom, et aucun secret envoyé."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from tests.test_ia import Faux

import http.server
import threading

REPO = Path(__file__).resolve().parents[1]
BIN = REPO / "home/.local/bin"
CLE_A = "sk-ant-test-0123456789abcdef"


@unittest.skipUnless(shutil.which("git"), "git absent")
class IACommit(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.serveur = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Faux)
        cls.port = cls.serveur.server_address[1]
        threading.Thread(target=cls.serveur.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.serveur.shutdown()
        cls.serveur.server_close()

    def setUp(self):
        Faux.requetes.clear()
        Faux.anthropic_refuse = False
        Faux.pendant = None
        Faux.goutte = None
        Faux.texte_ant = "Zone : ce qui change"
        d = tempfile.TemporaryDirectory(prefix="nc-ia-commit-")
        self.addCleanup(d.cleanup)
        self.home = Path(d.name)
        (self.home / ".config/nc").mkdir(parents=True)
        (self.home / "run").mkdir(mode=0o700)
        (self.home / ".local/bin").mkdir(parents=True)
        os.symlink(BIN / "nc-ia", self.home / ".local/bin/nc-ia")
        self.faux = self.home / "faux"
        self.faux.mkdir()
        for p in ("claude", "codex", "opencode", "gemini", "qwen", "omp", "systemd-run"):
            f = self.faux / p
            f.write_text("#!/bin/sh\nexit 1\n")
            f.chmod(0o755)
        u = f"http://127.0.0.1:{self.port}"
        f = self.home / ".config/nc/ia.conf"
        f.write_text(f"ANTHROPIC_API_KEY={CLE_A}\nURL_ANTHROPIC={u}/ant\nOLLAMA_HOST=http://127.0.0.1:1\n")
        f.chmod(0o600)
        self.reglages("")
        self.depot = self.home / "depot"
        self.depot.mkdir()
        self.git("init", "-q", "-b", "main")
        for i, s in enumerate(("Barre : l'heure suit le fuseau", "Île : la dictée s'arrête seule", "Thème : fond plus clair")):
            (self.depot / f"f{i}.txt").write_text(f"{i}\n")
            self.git("add", f"f{i}.txt")
            self.git("commit", "-q", "-m", s)

    def reglages(self, texte):
        (self.home / ".config/nc/reglages.conf").write_text("LANGUE=fr\nIA_BAC_REPLI=oui\n" + texte)

    def env(self):
        return dict(HOME=str(self.home), XDG_CONFIG_HOME=str(self.home / ".config"), XDG_CACHE_HOME=str(self.home / "cache"),
                    XDG_RUNTIME_DIR=str(self.home / "run"), TMPDIR=str(self.home), PATH=f"{self.faux}:/usr/bin:/bin",
                    NC_LANGUE="fr", NC_POWER_SUPPLY="secteur", NC_PROFIL="balanced", NC_IA_EN_LIGNE="1",
                    GIT_CONFIG_GLOBAL="/dev/null", GIT_CONFIG_SYSTEM="/dev/null", GIT_AUTHOR_NAME="Test",
                    GIT_AUTHOR_EMAIL="t@example.org", GIT_COMMITTER_NAME="Test", GIT_COMMITTER_EMAIL="t@example.org")

    def git(self, *args):
        subprocess.run(["git", "-C", str(self.depot), *args], env=self.env(), check=True, capture_output=True)

    def commit(self):
        return subprocess.run([str(self.home / ".local/bin/nc-ia"), "commit", "--dossier", str(self.depot)], env=self.env(),
                              capture_output=True, text=True, timeout=30)

    def envoye(self):
        return json.dumps(Faux.requetes[-1]["corps"], ensure_ascii=False) if Faux.requetes else ""

    def requetes_ia(self):
        return [q for q in Faux.requetes if q["chemin"] == "/ant/messages"]

    def test_message_et_sujets_en_exemple(self):
        (self.depot / "a.txt").write_text("bonjour\n")
        self.git("add", "a.txt")
        r = self.commit()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), "Zone : ce qui change")
        e = self.envoye()
        for s in ("Barre : l'heure suit le fuseau", "Île : la dictée s'arrête seule", "Thème : fond plus clair"):
            self.assertIn(s, e)
        self.assertIn("+bonjour", e)
        self.assertIn("a.txt", e)

    def test_rien_d_indexe_code_2(self):
        (self.depot / "a.txt").write_text("pas indexé\n")
        r = self.commit()
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertEqual(r.stdout, "")
        self.assertEqual(self.requetes_ia(), [])

    def test_ia_coupee_code_3(self):
        self.reglages("IA_MODE=non\n")
        (self.depot / "a.txt").write_text("bonjour\n")
        self.git("add", "a.txt")
        r = self.commit()
        self.assertEqual(r.returncode, 3, r.stderr)
        self.assertEqual(self.requetes_ia(), [])

    def test_secret_code_4_rien_n_est_envoye(self):
        cle = "sk-proj-AbCdEf0123456789AbCdEf0123"
        (self.depot / "conf.py").write_text(f'CLE = "{cle}"\n')
        self.git("add", "conf.py")
        r = self.commit()
        self.assertEqual(r.returncode, 4, r.stderr)
        self.assertIn("conf.py", r.stderr)
        self.assertNotIn(cle, r.stderr + r.stdout)
        self.assertEqual(self.requetes_ia(), [])

    def test_fichiers_de_secrets_et_mot_de_passe_code_4(self):
        for nom, contenu in ((".env", "A=1\n"), ("deploy/id_rsa", "x\n"), ("cert.pem", "x\n"),
                             ("app.ini", 'password = "hunter2hunter2hunter2"\n'),
                             ("net.txt", "url: https://moi:motdepasse@exemple.org/x\n")):
            with self.subTest(nom=nom):
                self.git("reset", "-q")
                f = self.depot / nom
                f.parent.mkdir(exist_ok=True)
                f.write_text(contenu)
                self.git("add", "-f", nom)
                r = self.commit()
                self.assertEqual(r.returncode, 4, r.stderr)
                self.assertIn(nom, r.stderr)
                self.assertNotIn("hunter2", r.stderr)
                self.assertNotIn("motdepasse", r.stderr)
        self.assertEqual(self.requetes_ia(), [])

    def test_exemple_d_env_et_code_ordinaire_passent(self):
        (self.depot / ".env.example").write_text("CLE=\n")
        (self.depot / "m.py").write_text("token = lire_le_jeton()\npassword = None\n")
        self.git("add", ".env.example", "m.py")
        r = self.commit()
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_diff_borne_liste_puis_debut_de_chaque_fichier(self):
        for i in range(6):
            (self.depot / f"gros{i}.txt").write_text("".join(f"ligne {i} numero {n} avec du texte\n" for n in range(4000)))
        self.git("add", ".")
        r = self.commit()
        self.assertEqual(r.returncode, 0, r.stderr)
        c = Faux.requetes[-1]["corps"]["messages"][0]["content"]
        e = c if isinstance(c, str) else "".join(x.get("text", "") for x in c)
        self.assertLess(len(e), 70000)
        self.assertIn("trop gros", e)
        for i in range(6):
            self.assertIn(f"gros{i}.txt", e)
            self.assertIn(f"ligne {i} numero 0 ", e)
        self.assertNotIn(f"ligne 0 numero 3999 ", e)

    def test_binaires_et_lockfiles_par_leur_nom(self):
        (self.depot / "image.bin").write_bytes(bytes(range(256)) * 4)
        (self.depot / "package-lock.json").write_text('{"lockfileVersion": 3, "x": "CONTENU_DU_LOCK"}\n')
        (self.depot / "code.py").write_text("print('ok')\n")
        self.git("add", ".")
        r = self.commit()
        self.assertEqual(r.returncode, 0, r.stderr)
        e = self.envoye()
        self.assertIn("image.bin", e)
        self.assertIn("package-lock.json", e)
        self.assertNotIn("CONTENU_DU_LOCK", e)
        self.assertIn("print('ok')", e)

    def test_reponse_nettoyee(self):
        Faux.texte_ant = "```\n« Barre : un titre propre »\n\nCo-Authored-By: Machine <m@example.org>\n```"
        (self.depot / "a.txt").write_text("bonjour\n")
        self.git("add", "a.txt")
        r = self.commit()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), "Barre : un titre propre")


if __name__ == "__main__":
    unittest.main()

"""Oh My Pi (omp) suivi par nc-claude, par son extension (~/.omp/agent/extensions/nc-ile.js) : installer et retirer sont
idempotents (sauvegarde du fichier d'un autre, jamais de secret), les événements de l'extension donnent travail / fini /
« t'attend », omp apparaît dans « etat --json » avec son agent et « ecrire », il est reconnu par son processus, et la réponse à
distance reste réservée aux états fini / prêt (repli : pas de certitude d'événement à chaque autorisation).
Rien dans le vrai HOME : dossier temporaire ; faux notify ; jamais le vrai omp."""
import contextlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import types
import unittest
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[1]
BIN = REPO / "home/.local/bin"


class Omp(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="nc-omp-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        m = self.m = types.ModuleType("nc_omp")
        m.__file__ = str(BIN / "nc-claude")
        exec(compile((BIN / "nc-claude").read_text(), m.__file__, "exec"), m.__dict__)
        m.HOME = str(self.root)
        m.RUN = str(self.root / "run")
        m.ETAT, m.VERROU, m.REPONSES = (str(Path(m.RUN) / n) for n in ["etat.json", "etat.lock", "reponses"])
        m.JOURNAL = str(Path(m.RUN) / "agents.log")
        m.reglage = lambda k, defaut: defaut
        m.ile_active = lambda: True
        m.terminal_actif = lambda pid: False
        m.reperer_terminal = lambda s: s.update(terminal=50, shell=60, classe="kitty", ecrire=True)
        self.notifs = []
        m.notifier = lambda s, titre, texte, voir=False: self.notifs.append((s["id"], titre, texte, voir))
        env = patch.dict(os.environ, HOME=str(self.root))
        env.start()
        self.addCleanup(env.stop)

    def evenement(self, nom, **ev):
        self.m.lire_entree = lambda: dict(ev, session_id="o1", cwd="/home/user/site")
        with contextlib.redirect_stdout(io.StringIO()):
            self.m.hook_ia("omp", nom)

    def etat_json(self):
        with contextlib.redirect_stdout(io.StringIO()) as s:
            self.m.montrer_json()
        return json.loads(s.getvalue())["sessions"]

    def test_omp_est_dans_la_liste_des_ia(self):
        self.assertIn("omp", self.m.IAS)
        self.assertEqual(self.m.NOMS["omp"], "Oh My Pi")
        self.assertEqual(self.m.FICHIERS["omp"], "~/.omp/agent/extensions/nc-ile.js")

    def test_installer_est_idempotent_et_retirer_nettoie(self):
        f = Path(self.m.chemin("omp"))
        self.assertFalse(self.m.installe("omp"))
        with contextlib.redirect_stdout(io.StringIO()):
            self.m.installer_ia("omp")
            premier = f.read_text()
            self.m.installer_ia("omp")
        self.assertEqual(f.read_text(), premier)
        self.assertTrue(self.m.installe("omp"))
        self.assertFalse(Path(str(f) + ".avant-nc-claude").exists())
        self.assertIn('"ia", "omp"', premier)
        for evt in ("agent_start", "tool_execution_end", "agent_end", "session_shutdown"):
            self.assertIn(evt, premier)
        self.assertNotIn(str(self.root), premier.replace(self.m.NC, ""))
        with contextlib.redirect_stdout(io.StringIO()):
            self.m.retirer_ia("omp")
        self.assertFalse(f.exists())
        self.assertFalse(self.m.installe("omp"))

    def test_fichier_d_un_autre_sauvegarde_une_fois(self):
        f = Path(self.m.chemin("omp"))
        f.parent.mkdir(parents=True)
        f.write_text("// mon extension\n")
        with contextlib.redirect_stdout(io.StringIO()):
            self.m.installer_ia("omp")
            self.m.installer_ia("omp")
        self.assertEqual(Path(str(f) + ".avant-nc-claude").read_text(), "// mon extension\n")

    @unittest.skipUnless(shutil.which("node"), "node absent")
    def test_extension_syntaxe_valide(self):
        with contextlib.redirect_stdout(io.StringIO()):
            self.m.installer_ia("omp")
        copie = self.root / "ext.mjs"
        copie.write_text(Path(self.m.chemin("omp")).read_text())
        r = subprocess.run(["node", "--check", str(copie)], capture_output=True, text=True, timeout=20)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_travail_fini_attente_et_reprise(self):
        self.evenement("prompt")
        self.assertEqual(self.etat_json()[0]["etat"], "travail")
        self.evenement("tool", tool_name="read", tool_input={"path": "a.txt"})
        self.assertEqual(self.etat_json()[0]["etat"], "travail")
        self.evenement("stop")
        self.assertEqual(self.etat_json()[0]["etat"], "fini")
        self.evenement("prompt")
        self.evenement("permission")
        s = self.etat_json()[0]
        self.assertEqual(s["etat"], "terminal")
        self.assertEqual(len(self.notifs), 1)
        self.assertIn("Oh My Pi", self.notifs[0][1])
        self.evenement("reprise")
        self.assertEqual(self.etat_json()[0]["etat"], "travail")
        self.evenement("fin")
        self.assertEqual(self.etat_json(), [])

    def test_etat_json_agent_omp_ecrire_et_repli(self):
        self.evenement("prompt")
        self.evenement("stop")
        (s,) = self.etat_json()
        self.assertEqual((s["agent"], s["etat"], s["ecrire"]), ("omp", "fini", True))
        self.assertFalse(s["signale_autorisation"], "omp reste en repli : réponse permise seulement fini / prêt")

    def test_reconnu_par_son_processus(self):
        self.assertTrue(self.m.cmdline_est_agent(["/usr/bin/omp"], "omp"))
        self.assertTrue(self.m.cmdline_est_agent(["bun", "/x/node_modules/.bin/omp", "--flag"], "omp"))
        self.assertFalse(self.m.cmdline_est_agent(["/usr/bin/ompx"], "omp"))
        self.assertFalse(self.m.cmdline_est_agent(["zsh"], "omp"))

    def test_gemini_et_antigravity_branches_et_reconnus(self):
        """État des lieux : Gemini CLI et agy sont dans IAS, ont leur fichier de hooks et leur processus."""
        for ia in ("gemini", "antigravity"):
            self.assertIn(ia, self.m.IAS)
            self.assertIn(ia, self.m.FICHIERS)
            with contextlib.redirect_stdout(io.StringIO()):
                self.m.installer_ia(ia)
            self.assertTrue(self.m.installe(ia), ia)
        self.assertTrue(self.m.cmdline_est_agent(["node", "/usr/lib/node_modules/@google/gemini-cli/dist/index.js"], "gemini"))
        self.assertTrue(self.m.cmdline_est_agent(["/usr/bin/agy"], "antigravity"))
        self.assertIn("gemini", self.m.SIGNALENT_AUTORISATION)
        self.assertNotIn("antigravity", self.m.SIGNALENT_AUTORISATION)


if __name__ == "__main__":
    unittest.main()

"""nc-claude statusline : la ligne d'état de Claude Code aux couleurs du bureau (palette de l'île), son rendu avec
plusieurs JSON (complet, minimal, null, vide, invalide), la branche lue dans .git/HEAD sans lancer git, et son
installation (seulement s'il n'y en a pas déjà une) et son retrait (seulement si elle est à nous), dans un faux HOME."""
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
import unittest

REPO = Path(__file__).resolve().parents[1]
NC_CLAUDE = REPO / "home/.local/bin/nc-claude"
ANSI = re.compile(r"\033\[[0-9;]*m")
PALETTE = {"accent": "#102030", "texteSec": "#405060", "vert": "#00ff00", "orange": "#ff8800", "rouge": "#ff0000",
           "bleu": "#0000ff", "violet": "#aa00aa"}
COMPLET = {"model": {"display_name": "Opus 5.5"}, "effort": {"level": "high"},
           "workspace": {"current_dir": "", "project_dir": "/work/mon-projet"},
           "cost": {"total_cost_usd": 1.2345, "total_lines_added": 120, "total_lines_removed": 8},
           "context_window": {"used_percentage": 42}, "rate_limits": {"five_hour": {"used_percentage": 37, "resets_at": 1790000000}}}


class LigneEtat(unittest.TestCase):
    def setUp(self):
        d = tempfile.TemporaryDirectory(prefix="nc-ligne-")
        self.addCleanup(d.cleanup)
        self.home = Path(d.name)
        (self.home / ".config/nc").mkdir(parents=True)
        (self.home / ".claude").mkdir()
        self.settings = self.home / ".claude/settings.json"

    def palette(self, oui=True):
        f = self.home / ".config/nc/palette-ile.json"
        if oui:
            f.write_text(json.dumps(PALETTE))
        elif f.exists():
            f.unlink()

    def lancer(self, *args, entree="", colonnes=None):
        env = dict(HOME=str(self.home), XDG_RUNTIME_DIR=str(self.home / "run"), XDG_CONFIG_HOME=str(self.home / ".config"),
                   XDG_CACHE_HOME=str(self.home / "cache"), TMPDIR=str(self.home), PATH="/usr/bin:/bin", NC_LANGUE="fr")
        if colonnes:
            env["COLUMNS"] = str(colonnes)
        return subprocess.run([sys.executable, str(NC_CLAUDE), *args], env=env, input=entree, capture_output=True, text=True,
                              timeout=30)

    def ligne(self, d, **kw):
        r = self.lancer("statusline", entree=d if isinstance(d, str) else json.dumps(d), **kw)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stderr, "")
        return r.stdout

    def test_rendu_complet_en_vraies_couleurs(self):
        self.palette()
        (self.home / "projet/.git").mkdir(parents=True)
        (self.home / "projet/.git/HEAD").write_text("ref: refs/heads/ma-branche\n")
        d = json.loads(json.dumps(COMPLET))
        d["workspace"]["current_dir"] = str(self.home / "projet")
        brut = self.ligne(d)
        clair = ANSI.sub("", brut)
        for morceau in ("Opus 5.5", "high", "mon-projet", "ma-branche", "▰▰▱▱▱ 42 %", "1,23 $", "+120", "−8", "5 h 37 %"):
            self.assertIn(morceau, clair)
        self.assertNotIn("/work", clair)                        # le nom du dossier seul
        self.assertEqual(brut.count("\n"), 1)
        self.assertIn("\033[38;2;16;32;48m", brut)              # l'accent de la palette en 24 bits
        self.assertIn("\033[38;2;0;255;0m", brut)               # le vert (contexte bas)

    def test_sans_palette_couleurs_de_base(self):
        self.palette(False)
        brut = self.ligne(COMPLET)
        self.assertNotIn("38;2;", brut)
        self.assertIn("\033[32m", brut)
        self.assertIn("Opus 5.5", ANSI.sub("", brut))

    def test_jauge_orange_puis_rouge(self):
        self.palette()
        for pct, seq in ((71, "38;2;255;136;0m"), (95, "38;2;255;0;0m"), (10, "38;2;0;255;0m")):
            d = dict(COMPLET, context_window={"used_percentage": pct})
            brut = self.ligne(d)
            m = re.search(r"\033\[([0-9;]*m)(▰+▱*) " + str(pct) + " %", brut)
            self.assertIsNotNone(m, brut)
            self.assertEqual(m[1], seq, pct)

    def test_json_minimal_null_vide_invalide(self):
        self.palette()
        self.assertIn("Opus", ANSI.sub("", self.ligne({"model": {"display_name": "Opus"}})))
        for entree in ({"context_window": {"used_percentage": None}, "cost": None, "model": None, "workspace": []},
                       {}, "", "   ", "{pas du json", "null", "[]", "42", '"texte"'):
            with self.subTest(entree=entree):
                clair = ANSI.sub("", self.ligne(entree))
                self.assertIn("Claude", clair)
                self.assertNotIn("%", clair)
                self.assertNotIn("Traceback", clair)
        sans = ANSI.sub("", self.ligne({"context_window": {"used_percentage": None}, "model": {"display_name": "X"}}))
        self.assertNotIn("▰", sans)

    def test_deux_lignes_si_etroit(self):
        self.palette()
        brut = self.ligne(COMPLET, colonnes=40)
        l = brut.rstrip("\n").split("\n")
        self.assertEqual(len(l), 2)
        self.assertIn("Opus 5.5", l[0])
        self.assertIn("42 %", l[1])
        self.assertEqual(self.ligne(COMPLET, colonnes=400).count("\n"), 1)

    def test_branche_worktree_et_tete_detachee(self):
        self.palette()
        # worktree : .git est un fichier qui pointe vers le vrai dossier de la branche
        (self.home / "depot/.git/worktrees/wt").mkdir(parents=True)
        (self.home / "depot/.git/worktrees/wt/HEAD").write_text("ref: refs/heads/essai\n")
        (self.home / "wt").mkdir()
        (self.home / "wt/.git").write_text(f"gitdir: {self.home}/depot/.git/worktrees/wt\n")
        (self.home / "wt/sous").mkdir()
        d = {"workspace": {"current_dir": str(self.home / "wt/sous"), "git_worktree": "wt"}}
        clair = ANSI.sub("", self.ligne(d))
        self.assertIn("essai", clair)
        self.assertIn("(wt)", clair)
        (self.home / "depot/.git/HEAD").write_text("0123456789abcdef0123456789abcdef01234567\n")
        clair = ANSI.sub("", self.ligne({"workspace": {"current_dir": str(self.home / "depot")}}))
        self.assertIn("0123456", clair)
        self.assertNotIn("0123456789", clair)

    def test_rapide(self):
        self.palette()
        self.ligne(COMPLET)
        debut = time.perf_counter()
        for _ in range(5):
            self.ligne(COMPLET)
        self.assertLess((time.perf_counter() - debut) / 5, 0.5)   # large : la machine de test peut être chargée

    # ── installer / retirer ──
    def lire(self):
        return json.loads(self.settings.read_text())

    def test_installer_ajoute_la_ligne_quand_il_n_y_en_a_pas(self):
        self.settings.write_text(json.dumps({"model": "opus"}))
        r = self.lancer("installer")
        self.assertEqual(r.returncode, 0, r.stderr)
        s = self.lire()
        self.assertEqual(s["statusLine"], {"type": "command", "command": "$HOME/.local/bin/nc-claude statusline", "padding": 0})
        self.assertEqual(s["model"], "opus")
        self.assertIn("nc-claude hook", json.dumps(s["hooks"]))
        copie = self.home / ".claude/settings.json.avant-nc-claude"
        self.assertEqual(json.loads(copie.read_text()), {"model": "opus"})
        # une seconde fois : rien ne change
        avant = self.settings.read_text()
        self.lancer("installer")
        self.assertEqual(self.settings.read_text(), avant)

    def test_installer_ne_remplace_jamais_la_ligne_de_l_utilisateur(self):
        perso = {"type": "command", "command": "~/ma-ligne.sh", "padding": 2}
        self.settings.write_text(json.dumps({"statusLine": perso}))
        self.lancer("installer")
        self.assertEqual(self.lire()["statusLine"], perso)
        self.lancer("retirer")
        self.assertEqual(self.lire()["statusLine"], perso)           # pas la nôtre : gardée
        self.assertNotIn("hooks", self.lire())

    def test_retirer_enleve_la_notre(self):
        self.lancer("installer")
        self.assertIn("statusLine", self.lire())
        r = self.lancer("retirer")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn("statusLine", self.lire())

    def test_installer_sans_ligne_si_reglage_non(self):
        (self.home / ".config/nc/reglages.conf").write_text("CLAUDE_LIGNE=non\n")
        self.lancer("installer")
        self.assertNotIn("statusLine", self.lire())

    def test_diag_la_mentionne(self):
        self.lancer("installer")
        r = self.lancer("diag")
        self.assertIn("Ligne d'état", r.stdout)
        self.assertIn("aux couleurs du bureau", r.stdout)
        self.settings.write_text(json.dumps({"statusLine": {"type": "command", "command": "x"}}))
        self.assertIn("la tienne", self.lancer("diag").stdout)


if __name__ == "__main__":
    unittest.main()

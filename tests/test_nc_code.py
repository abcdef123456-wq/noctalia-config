"""nc-code (Super + X) : la liste des projets dans un faux HOME avec de faux dépôts (noctalia-config, zoxide, project.nvim,
sessions de Claude Code décodées sans rien deviner, balayage de ~/*/.git), la session kitty produite sans la lancer
(Neovim à gauche, l'agent à droite, lazygit, shell), l'IA coupée (pas d'agent : un shell), le raccourci et la règle de
fenêtre."""
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
import unittest.mock

REPO = Path(__file__).resolve().parents[1]
BIN = REPO / "home/.local/bin"


class NcCode(unittest.TestCase):
    def setUp(self):
        d = tempfile.TemporaryDirectory(prefix="nc-code-")
        self.addCleanup(d.cleanup)
        self.home = Path(d.name).resolve()
        (self.home / ".local/bin").mkdir(parents=True)
        for f in ("nc-code", "nc-ia"):
            os.symlink(BIN / f, self.home / ".local/bin" / f)
        (self.home / ".config/nc").mkdir(parents=True)
        self.faux = self.home / "faux"
        self.faux.mkdir()

    def depot(self, rel):
        p = self.home / rel
        (p / ".git").mkdir(parents=True)
        return p

    def programme(self, nom, corps="exit 0"):
        f = self.faux / nom
        f.write_text("#!/bin/sh\n" + corps + "\n")
        f.chmod(0o755)

    def reglages(self, texte):
        (self.home / ".config/nc/reglages.conf").write_text("LANGUE=fr\n" + texte)

    def lancer(self, *args):
        env = dict(HOME=str(self.home), XDG_CONFIG_HOME=str(self.home / ".config"), XDG_CACHE_HOME=str(self.home / "cache"),
                   XDG_RUNTIME_DIR=str(self.home / "run"), TMPDIR=str(self.home), NC_LANGUE="fr", NC_IA_EN_LIGNE="1",
                   NC_POWER_SUPPLY="secteur", NC_PROFIL="balanced", PATH=f"{self.faux}:/usr/bin:/bin")
        (self.home / "run").mkdir(mode=0o700, exist_ok=True)
        return subprocess.run([sys.executable, str(self.home / ".local/bin/nc-code"), *args], env=env, capture_output=True,
                              text=True, timeout=30)

    def liste(self):
        r = self.lancer("--liste")
        self.assertEqual(r.returncode, 0, r.stderr)
        return [l.split("\t")[1] for l in r.stdout.splitlines()]

    # ── la liste des projets ──
    def test_projets_de_toutes_les_sources_sans_doublon(self):
        a = self.depot("noctalia-config")
        b = self.depot("dev/zox")
        c = self.depot("dev/neo")
        d = self.depot("balayage")
        e = self.depot("autre/profond")
        (self.home / "pas-un-depot/.git").parent.mkdir()
        self.depot("a/b/c/trop-profond")
        self.depot(".cache/cache-cache")
        (self.home / ".config/nc/depot").write_text(f"{a}\n")
        self.programme("zoxide", f'printf "%s\\n" "{b}" "{self.home}/pas-un-depot" "{a}"')
        hist = self.home / ".local/share/nvim/project_nvim"
        hist.mkdir(parents=True)
        (hist / "project_history").write_text(f"{self.home}/inexistant\n{c}\n")
        l = self.liste()
        self.assertEqual(l[0], str(a))                                     # noctalia-config d'abord
        for p in (b, c, d, e):
            self.assertIn(str(p), l)
        self.assertEqual(len(l), len(set(l)))                              # chacun une fois
        self.assertNotIn(str(self.home / "pas-un-depot"), l)               # pas de .git : écarté
        self.assertNotIn(str(self.home / "a/b/c/trop-profond"), l)         # profondeur 2 au plus
        self.assertFalse([x for x in l if "/.cache/" in x])                # dossiers cachés ignorés
        self.assertLess(l.index(str(c)), l.index(str(d)))                  # project.nvim avant le balayage

    def test_copies_de_travail_des_agents_ecartees(self):
        a = self.depot("dev/vrai")
        w = self.depot("dev/vrai/.claude/worktrees/agent-1")
        self.programme("zoxide", f'printf "%s\\n" "{w}" "{a}"')
        l = self.liste()
        self.assertIn(str(a), l)
        self.assertNotIn(str(w), l)

    def test_sessions_de_claude_decodees_prudemment(self):
        p = self.depot("dev/mon-projet.v2")
        q = self.depot("dev/mon")                                          # « mon » ne doit pas avaler « mon-projet.v2 »
        sessions = self.home / ".claude/projects"
        sessions.mkdir(parents=True)
        (sessions / re.sub(r"[^A-Za-z0-9]", "-", str(p))).mkdir()
        (sessions / re.sub(r"[^A-Za-z0-9]", "-", str(self.home / "n-existe-pas"))).mkdir()
        (sessions / "pas-encode").mkdir()
        (sessions / (re.sub(r"[^A-Za-z0-9]", "-", str(self.home / "dev")))).mkdir()    # un dossier sans .git
        l = self.liste()
        self.assertIn(str(p), l)
        self.assertIn(str(q), l)                                           # trouvé par le balayage
        self.assertFalse([x for x in l if "existe" in x])
        # le décodage lui-même, sur le module
        import importlib.machinery
        import importlib.util
        ld = importlib.machinery.SourceFileLoader("nc_code_t", str(BIN / "nc-code"))
        m = importlib.util.module_from_spec(importlib.util.spec_from_loader("nc_code_t", ld))
        with unittest.mock.patch.dict(os.environ, {"HOME": str(self.home)}):       # jamais le vrai HOME
            ld.exec_module(m)
        self.assertEqual(m.decoder_claude(re.sub(r"[^A-Za-z0-9]", "-", str(p))), str(p))
        self.assertEqual(m.decoder_claude("-inexistant-quelque-part"), "")
        self.assertEqual(m.decoder_claude("sans-tiret-de-tete"), "")

    # ── la session kitty ──
    def test_session_nvim_a_gauche_agent_a_droite(self):
        p = self.depot("dev/projet")
        self.programme("claude")
        self.programme("nvim")
        self.programme("lazygit")
        self.reglages("IA_MODE=manuel\nIA_CHOIX=claude\n")
        r = self.lancer("--session-seule", str(p))
        self.assertEqual(r.returncode, 0, r.stderr)
        s = r.stdout
        self.assertIn("layout splits", s)
        self.assertIn(f"cd {p}", s)
        lignes = s.splitlines()
        self.assertTrue(any(l.startswith("launch") and l.endswith("nvim") for l in lignes))
        droite = next(l for l in lignes if "--location=vsplit" in l)
        self.assertIn("--bias=38", droite)                                 # Neovim garde 62 %
        self.assertIn("--keep-focus", droite)
        self.assertIn("--lancer-agent claude", droite)
        self.assertLess(s.index("nvim"), s.index("--location=vsplit"))
        tabs = [l for l in lignes if l.startswith("new_tab")]
        self.assertEqual(tabs, ["new_tab Code", "new_tab Git", "new_tab Terminal"])
        self.assertIn("launch --title lazygit lazygit", s)

    def test_sans_lazygit_pas_d_onglet_lazygit(self):
        p = self.depot("dev/projet")
        self.programme("nvim")
        self.reglages("IA_MODE=manuel\nIA_CHOIX=claude\n")
        s = self.lancer("--session-seule", str(p)).stdout
        self.assertNotIn("lazygit", s)

    def test_ia_coupee_un_shell_a_la_place_de_l_agent(self):
        p = self.depot("dev/projet")
        self.programme("claude")
        self.programme("nvim")
        self.reglages("IA_MODE=non\n")
        s = self.lancer("--session-seule", str(p)).stdout
        self.assertNotIn("--lancer-agent", s)
        self.assertNotIn("claude", s)
        self.assertIn("--location=vsplit --bias=38 --keep-focus --title shell", s)

    def test_agent_force_neovim_seul_et_sans_agent(self):
        p = self.depot("dev/projet")
        self.programme("nvim")
        self.reglages("IA_MODE=non\n")
        self.assertIn("--lancer-agent codex", self.lancer("--session-seule", str(p), "--agent", "codex").stdout)
        seul = self.lancer("--session-seule", str(p), "--nvim").stdout
        self.assertNotIn("vsplit", seul)
        self.assertEqual([l for l in seul.splitlines() if l.startswith("new_tab")], ["new_tab Code"])
        self.assertNotIn("--lancer-agent", self.lancer("--session-seule", str(p), "--sans-agent").stdout)

    def test_dossier_invalide_et_chemin_a_espaces(self):
        r = self.lancer("--session-seule", str(self.home / "rien"))
        self.assertEqual(r.returncode, 1)
        self.assertIn("pas un dossier", r.stderr)
        p = self.depot("dev/mon projet")
        self.reglages("IA_MODE=non\n")
        self.assertIn(f"cd {p}\n", self.lancer("--session-seule", str(p)).stdout)

    def test_apercu(self):
        p = self.depot("dev/projet")
        (p / "README.md").write_text("# Titre du projet\nUne ligne\n")
        r = self.lancer("--apercu", str(p))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("projet", r.stdout)
        self.assertIn("Titre du projet", r.stdout)

    def test_selecteur_numerote_ouvre_kitty_avec_la_session(self):
        p = self.depot("dev/projet")
        self.programme("nvim")
        self.reglages("IA_MODE=non\n")
        (self.home / ".config/nc/depot").write_text(f"{p}\n")
        self.programme("kitty", f'echo "$@" > "{self.home}/kitty-args"; cat > "{self.home}/kitty-session"')
        env = dict(HOME=str(self.home), XDG_CONFIG_HOME=str(self.home / ".config"), TMPDIR=str(self.home), NC_LANGUE="fr",
                   PATH=f"{self.faux}:/usr/bin:/bin")
        r = subprocess.run([sys.executable, str(self.home / ".local/bin/nc-code"), "--selecteur"], env=env, input="1 n\n",
                           capture_output=True, text=True, timeout=30)
        self.assertEqual(r.returncode, 0, r.stderr)
        for _ in range(50):
            if (self.home / "kitty-session").exists() and (self.home / "kitty-session").stat().st_size:
                break
            time.sleep(0.1)
        self.assertIn("--session -", (self.home / "kitty-args").read_text())
        self.assertIn(f"--directory {p}", (self.home / "kitty-args").read_text())
        s = (self.home / "kitty-session").read_text()
        self.assertIn("launch --title nvim nvim", s)
        self.assertNotIn("vsplit", s)                                      # « 1 n » : Neovim seul

    # ── l'interface plein terminal (dans un vrai pseudo-terminal) ──
    def pty_selecteur(self, touches):
        import fcntl
        import pty
        import struct
        import termios
        env = dict(HOME=str(self.home), XDG_CONFIG_HOME=str(self.home / ".config"), TMPDIR=str(self.home), NC_LANGUE="fr",
                   PATH=f"{self.faux}:/usr/bin:/bin", TERM="xterm-256color")
        pid, fd = pty.fork()
        if pid == 0:
            os.execve(sys.executable, [sys.executable, str(self.home / ".local/bin/nc-code"), "--selecteur"], env)
        self.addCleanup(lambda: os.close(fd))
        fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack("HHHH", 30, 100, 0, 0))
        vu = b""

        def lire(jusque, delai=10):
            nonlocal vu
            fin = time.time() + delai
            while jusque not in vu and time.time() < fin:
                import select
                if select.select([fd], [], [], 0.1)[0]:
                    try:
                        vu += os.read(fd, 65536)
                    except OSError:
                        break
            return jusque in vu
        self.assertTrue(lire("Espace de code".encode()), vu[-500:])
        for t in touches:
            os.write(fd, t)
            time.sleep(0.15)
        lire(b"\x1b[?1049l", 5)
        _, statut = os.waitpid(pid, 0)
        self.assertEqual(os.waitstatus_to_exitcode(statut), 0, vu[-800:])
        return vu.decode("utf-8", "replace")

    def test_interface_recherche_puis_entree(self):
        a = self.depot("dev/alpha")
        b = self.depot("dev/neovim-conf")
        (b / ".git/HEAD").write_text("ref: refs/heads/essai\n")
        (b / ".git/logs").mkdir()
        (b / ".git/logs/HEAD").write_text("0 1 X <x@y> 1700000000 +0100\tcommit: Un message de commit\n")
        (self.home / ".config/nc/depot").write_text(f"{a}\n")
        self.programme("nvim")
        self.reglages("IA_MODE=non\n")
        self.programme("kitty", f'echo "$@" > "{self.home}/kitty-args"; cat > "{self.home}/kitty-session"')
        vu = self.pty_selecteur([b"neo", b"\r"])
        self.assertIn("Rechercher un projet", vu)
        self.assertIn("essai  ·  ", vu)                                      # branche lue dans .git, sans lancer git
        self.assertIn("Un message de commit", vu)
        self.assertIn("38;2;", vu)                                         # couleurs de la palette (24 bits)
        for _ in range(50):
            if (self.home / "kitty-session").exists() and (self.home / "kitty-session").stat().st_size:
                break
            time.sleep(0.1)
        self.assertIn(f"cd {b}", (self.home / "kitty-session").read_text())
        args = (self.home / "kitty-args").read_text()
        self.assertIn("tab_powerline_style=round", args)                  # onglets arrondis
        self.assertIn("--title neovim-conf", args)

    def test_interface_echap_ferme_sans_rien_ouvrir(self):
        a = self.depot("dev/alpha")
        (self.home / ".config/nc/depot").write_text(f"{a}\n")
        self.programme("kitty", f'touch "{self.home}/kitty-lance"')
        self.pty_selecteur([b"zz", b"\x1b", b"\x1b"])                   # 1er Échap : vide la recherche ; 2e : ferme
        time.sleep(0.3)
        self.assertFalse((self.home / "kitty-lance").exists())

    def test_interface_tab_choisit_l_agent(self):
        a = self.depot("dev/alpha")
        (self.home / ".config/nc/depot").write_text(f"{a}\n")
        self.programme("nvim")
        self.reglages("IA_MODE=non\n")
        self.programme("kitty", f'cat > "{self.home}/kitty-session"')
        vu = self.pty_selecteur([b"\t", b"\r"])                         # Tab, puis « Un terminal, sans agent »
        self.assertIn("Quel agent", vu)
        for _ in range(50):
            if (self.home / "kitty-session").exists() and (self.home / "kitty-session").stat().st_size:
                break
            time.sleep(0.1)
        self.assertNotIn("--lancer-agent", (self.home / "kitty-session").read_text())

    def test_heure_relative_et_recherche(self):
        import importlib.machinery
        import importlib.util
        ld = importlib.machinery.SourceFileLoader("nc_code_u", str(BIN / "nc-code"))
        m = importlib.util.module_from_spec(importlib.util.spec_from_loader("nc_code_u", ld))
        with unittest.mock.patch.dict(os.environ, {"HOME": str(self.home), "XDG_CONFIG_HOME": str(self.home / ".config"),
                                                   "NC_LANGUE": "fr"}):
            ld.exec_module(m)
            t = 1_800_000_000
            self.assertEqual(m.il_y_a(t - 10, t), "à l'instant")
            self.assertEqual(m.il_y_a(t - 300, t), "il y a 5 min")
            self.assertEqual(m.il_y_a(t - 3 * 3600, t), "il y a 3 h")
            self.assertEqual(m.il_y_a(t - 86400 - 5, t), "hier")
            self.assertEqual(m.il_y_a(t - 20 * 86400, t), "il y a 2 sem")
            self.assertEqual(m.il_y_a(0, t), "")
            self.assertLess(m.correspond("neo", "neovim"), m.correspond("neo", "mon-neo"))
            self.assertIsNotNone(m.correspond("nc", "noctalia-config"))
            self.assertIsNone(m.correspond("zz", "noctalia"))
            self.assertEqual(m.palette()["fond"], "#1c1c1e")                # sans palette de l'île : noir Apple
            (self.home / ".config/nc/palette-ile.json").write_text('{"fond": "#291417", "accent": "pas une couleur"}')
            self.assertEqual(m.palette()["fond"], "#291417")
            self.assertEqual(m.palette()["accent"], "#0a84ff")
            w = self.depot("dev/vrai")
            (w / ".git").rmdir()
            (w / ".git").write_text("gitdir: ../gd\n")
            (self.home / "dev/gd").mkdir()
            (self.home / "dev/gd/HEAD").write_text("ref: refs/heads/branche-w\n")
            self.assertEqual(m.infos_projet(str(w))["branche"], "branche-w")

    # ── Hyprland ──
    def test_raccourci_et_regle_de_fenetre(self):
        rac = (REPO / "home/.config/hypr/nc/raccourcis.lua").read_text()
        self.assertEqual(len(re.findall(r'"\s*\+ code:53"', rac)), 1)       # la touche est libre et prise une fois
        self.assertIn('SUPER .. " + code:53", cmd("~/.local/bin/nc-code")', rac)
        regles = (REPO / "home/.config/hypr/nc/regles.lua").read_text()
        self.assertRegex(regles, r'class = "\^\(nc-code\)\$"')
        auto = (REPO / "home/.config/hypr/nc/automatismes.lua").read_text()
        self.assertIn('c == "nc-code"', auto)                                # hors de la mémoire des fenêtres flottantes
        self.assertIn("`Super` + `X`", (REPO / "RACCOURCIS.md").read_text())
        self.assertTrue(os.access(BIN / "nc-code", os.X_OK))


if __name__ == "__main__":
    unittest.main()

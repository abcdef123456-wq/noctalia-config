"""nc-code (Super + X) : la liste des projets dans un faux HOME avec de faux dépôts (noctalia-config, zoxide, project.nvim,
sessions de Claude Code décodées sans rien deviner, balayage de ~/*/.git), la session kitty produite sans la lancer
(Neovim à gauche, l'agent à droite, lazygit, shell), l'IA coupée (pas d'agent : un shell), le raccourci et la règle de
fenêtre."""
import json
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
                   NC_POWER_SUPPLY="secteur", NC_PROFIL="balanced", PATH=getattr(self, "chemin", f"{self.faux}:/usr/bin:/bin"))
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
        self.assertIn("launch --title lazygit lazygit", s)                  # sans ~/.config/nc/lazygit.yml : lazygit nu
        (self.home / ".config/nc/lazygit.yml").write_text("gui: {}\n")
        (self.home / ".config/lazygit").mkdir()
        (self.home / ".config/lazygit/config.yml").write_text("gui: {}\n")
        s = self.lancer("--session-seule", str(p)).stdout
        attendu = f"{self.home}/.config/nc/lazygit.yml,{self.home}/.config/lazygit/config.yml"
        self.assertIn(f"launch --title lazygit --env LG_CONFIG_FILE={attendu} lazygit", s)   # comme lg : la nôtre, puis la tienne

    def test_sans_lazygit_pas_d_onglet_lazygit(self):
        p = self.depot("dev/projet")
        self.programme("nvim")
        # jamais le vrai lazygit de la machine : un PATH avec seulement les faux et python3, sh, env
        mini = self.home / "bin-min"
        mini.mkdir()
        for prog in ("python3", "sh", "env"):
            vrai = shutil.which(prog)
            if vrai:
                (mini / prog).symlink_to(vrai)
        self.chemin = f"{self.faux}:{mini}"
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
        self.reglages("IA_MODE=manuel\n")
        self.assertIn("--lancer-agent codex", self.lancer("--session-seule", str(p), "--agent", "codex").stdout)
        self.reglages("IA_MODE=non\n")
        self.assertNotIn("--lancer-agent", self.lancer("--session-seule", str(p), "--agent", "codex").stdout)   # IA coupée
        seul = self.lancer("--session-seule", str(p), "--nvim").stdout
        self.assertNotIn("vsplit", seul)
        self.assertEqual([l for l in seul.splitlines() if l.startswith("new_tab")], ["new_tab Code"])
        self.assertNotIn("--lancer-agent", self.lancer("--session-seule", str(p), "--sans-agent").stdout)

    def test_un_dossier_piege_n_injecte_rien_dans_la_session(self):
        """kitty découpe la session avec splitlines (\\r, \\x0b, U+2028…) et développe $VAR dans cd : un dossier trouvé
        par le balayage ne doit ajouter aucune ligne. Refusé (et absent de la liste) ; « $ » doublé."""
        self.reglages("IA_MODE=non\n")
        for nom in ("x\rlaunch sh -c 'touch /tmp/pirate'", "x\x0blaunch sh", "x\u2028launch sh", "x\x1claunch sh", "x "):
            with self.subTest(nom=repr(nom)):
                d = self.depot("dev/" + nom)
                r = self.lancer("--session-seule", str(d))
                self.assertEqual(r.returncode, 1, r.stdout)
                self.assertNotIn("launch sh", r.stdout)
                self.assertNotIn(str(d), self.liste())
        d = self.depot("dev/prix$HOME")
        s = self.lancer("--session-seule", str(d)).stdout
        self.assertIn("cd " + str(d).replace("$", "$$") + "\n", s)

    def test_lancer_agent_ia_coupee_seulement_le_shell(self):
        self.programme("claude", f'touch "{self.home}/agent-lance"')
        (self.faux / "sh").symlink_to("/bin/true")                       # le shell qui suit : sort tout de suite
        self.reglages("IA_MODE=non\n")
        env = dict(HOME=str(self.home), XDG_CONFIG_HOME=str(self.home / ".config"), PATH=f"{self.faux}:/usr/bin:/bin",
                   SHELL=str(self.faux / "sh"), NC_LANGUE="fr")
        subprocess.run([sys.executable, str(self.home / ".local/bin/nc-code"), "--lancer-agent", "claude"], env=env,
                       capture_output=True, timeout=30)
        self.assertFalse((self.home / "agent-lance").exists())

    def test_dossier_invalide_et_chemin_a_espaces(self):
        r = self.lancer("--session-seule", str(self.home / "rien"))
        self.assertEqual(r.returncode, 1)
        self.assertIn("pas un dossier", r.stderr)
        p = self.depot("dev/mon projet")
        self.reglages("IA_MODE=non\n")
        self.assertIn(f"cd {p}\n", self.lancer("--session-seule", str(p)).stdout)

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
        self.assertIn("launch --title nvim --env NC_CODE=1 nvim", s)
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
        (b / "pyproject.toml").write_text("")
        (b / ".git/HEAD").write_text("ref: refs/heads/essai\n")
        (b / ".git/logs").mkdir()
        (b / ".git/logs/HEAD").write_text("0 1 X <x@y> 1700000000 +0100\tcommit: Un message de commit\n")
        (self.home / ".config/nc/depot").write_text(f"{a}\n")
        self.programme("nvim")
        self.reglages("IA_MODE=non\n")
        self.programme("kitty", f'echo "$@" > "{self.home}/kitty-args"; cat > "{self.home}/kitty-session"')
        vu = self.pty_selecteur([b"neo", b"\r"])
        self.assertIn("Rechercher un projet", vu)
        self.assertIn("Python  ·  essai  ·  ", vu)                                      # branche lue dans .git, sans lancer git
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
            r = self.depot("dev/rouille")
            (r / "Cargo.toml").write_text("")
            self.assertEqual(m.langage(str(r)), ("Rust", "orange"))
            (w / "package.json").write_text("{}")
            (w / "tsconfig.json").write_text("{}")
            self.assertEqual(m.langage(str(w))[0], "TypeScript")
            self.assertEqual(m.langage(str(self.home)), ("", "gris4"))           # rien de reconnu : pastille neutre
            self.assertEqual(m.melange("#ff0000", "#000000", 0.5), "#800000")

    # ── Le panneau de l'île : les sorties JSON (sans git pour la liste), l'aperçu, GitHub, le repli ──
    def faux_git(self):
        self.programme("git", f'echo "git $*" >> "{self.home}/git-appels"; exit 1')

    def test_liste_json_sans_lancer_git(self):
        a = self.depot("dev/alpha")
        b = self.depot("dev/neovim-conf")
        (b / "pyproject.toml").write_text("")
        (b / ".git/HEAD").write_text("ref: refs/heads/essai\n")
        (b / ".git/logs").mkdir()
        (b / ".git/logs/HEAD").write_text("0 1 X <x@y> 1700000000 +0100\tcommit: Un message de commit\n")
        (b / ".git/config").write_text('[core]\n\tbare = false\n[remote "origin"]\n\turl = git@github.com:moi/neovim-conf.git\n')
        (self.home / ".config/nc/depot").write_text(f"{a}\n")
        self.faux_git()
        r = self.lancer("--liste-json")
        self.assertEqual(r.returncode, 0, r.stderr)
        l = json.loads(r.stdout)
        self.assertEqual([p["nom"] for p in l], ["neovim-conf", "alpha"], "le plus récent en tête")
        neo = l[0]
        for cle in ("nom", "chemin", "court", "branche", "quand", "date", "message", "langage", "couleur", "github"):
            self.assertIn(cle, neo)
        self.assertEqual((neo["chemin"], neo["court"]), (str(b), "~/dev/neovim-conf"))
        self.assertEqual((neo["branche"], neo["message"], neo["langage"], neo["couleur"]), ("essai", "Un message de commit", "Python", "bleu"))
        self.assertEqual(neo["github"], "https://github.com/moi/neovim-conf")
        self.assertEqual(l[1]["github"], "")
        self.assertFalse((self.home / "git-appels").exists(), "la liste ne lance jamais git")

    def test_agents_json(self):
        self.programme("claude")
        self.reglages("IA_MODE=manuel\nIA_CHOIX=claude\n")
        d = json.loads(self.lancer("--agents-json").stdout)
        self.assertFalse(d["coupee"])
        self.assertEqual(d["defaut"], "claude")
        self.assertIn("claude", [x["prog"] for x in d["agents"]])
        self.assertTrue(all(set(x) == {"prog", "nom"} for x in d["agents"]))
        self.reglages("IA_MODE=non\n")
        self.assertEqual(json.loads(self.lancer("--agents-json").stdout), dict(coupee=True, defaut="", agents=[]))

    def module_nc_code(self):
        import importlib.machinery
        import importlib.util
        ld = importlib.machinery.SourceFileLoader("nc_code_ag", str(BIN / "nc-code"))
        m = importlib.util.module_from_spec(importlib.util.spec_from_loader("nc_code_ag", ld))
        with unittest.mock.patch.dict(os.environ, {"HOME": str(self.home), "PATH": f"{self.faux}:/usr/bin:/bin"}):
            ld.exec_module(m)
        return m

    def env_faux(self):
        return unittest.mock.patch.dict(os.environ, {"HOME": str(self.home), "PATH": f"{self.faux}:/usr/bin:/bin"})

    def test_agent_par_defaut_question_sans_cli_prend_l_ia_choisie(self):
        for p in ("claude", "codex", "opencode"):
            self.programme(p)
        m = self.module_nc_code()
        ias = [dict(id=p, nom=p, cli=p, cli_disponible=True, disponible=True) for p in ("claude", "codex", "opencode")]
        e = dict(mode="manuel", coupee=False,
                 usages=dict(question=dict(id="jarvis", nom="JARVIS", cli="", cli_disponible=False)),
                 choisie=dict(id="codex", nom="Codex", cli="codex", cli_disponible=True), ias=ias)
        with self.env_faux():
            self.assertEqual(m.agent_par_defaut(e), "codex")               # l'IA choisie (question = jarvis sans cli)
            e["choisie"] = dict(id="claude", nom="Claude", cli="claude", cli_disponible=True)
            self.assertEqual(m.agent_par_defaut(e), "claude")
            e["choisie"] = {}                                              # pas d'IA choisie : le premier installé
            self.assertEqual(m.agent_par_defaut(e), "claude")
            e["usages"]["question"] = dict(cli="codex", cli_disponible=True)      # l'usage question gagne s'il a un agent
            self.assertEqual(m.agent_par_defaut(e), "codex")
            e["ias"] = []                                                  # aucun agent installé : un shell
            e["usages"]["question"] = {}
            self.assertEqual(m.agent_par_defaut(e), "")
            e["ias"] = ias
            e["coupee"] = True                                             # IA coupée : aucun agent
            self.assertEqual(m.agent_par_defaut(e), "")

    def test_ordre_des_agents_claude_agy_puis_les_autres(self):
        for p in ("claude", "codex", "opencode", "agy"):
            self.programme(p)
        m = self.module_nc_code()
        ias = [dict(id=p, nom=n, cli=p, cli_disponible=True, disponible=True) for p, n in (("codex", "Codex"), ("opencode", "OpenCode"), ("claude", "Claude Code"))]
        e = dict(mode="manuel", coupee=False, usages={}, choisie=dict(id="jarvis", cli="", cli_disponible=False), ias=ias)
        with self.env_faux():
            self.assertEqual([p for p, _ in m.agents_disponibles(e)], ["claude", "agy", "codex", "opencode"])
            self.assertIn(("agy", "Antigravity"), m.agents_disponibles(e))
            self.assertEqual(m.agent_par_defaut(e), "claude")
            e["ias"] = ias[:2]                                             # sans Claude : Antigravity d'abord
            self.assertEqual(m.agent_par_defaut(e), "agy")
            e["coupee"] = True
            self.assertEqual(m.agents_disponibles(e), [])

    def test_shells_de_l_espace_de_code_sans_accueil(self):
        p = self.depot("dev/projet")
        self.programme("nvim")
        self.reglages("IA_MODE=non\n")
        s = self.lancer("--session-seule", str(p)).stdout
        self.assertIn("--location=vsplit --bias=38 --keep-focus --title shell --env FASTFETCH_SHOWN=1", s)
        self.assertIn("--env NC_CODE=1 nvim", s)
        self.assertIn("launch --title shell\n", s)                         # l'onglet Terminal, large : garde l'accueil

    # ── un nouveau projet ──
    def faux_git_init(self):
        self.programme("git", f'echo "git $*" >> "{self.home}/git-appels"; for d; do :; done; mkdir -p "$d/.git"')

    def test_nouveau_projet_cree_dossier_readme_git_init(self):
        self.faux_git_init()
        self.programme("nvim")
        self.reglages("IA_MODE=non\n")
        r = self.lancer("--nouveau", "Mon Projet é!/..", "--modele", "python", "--session-seule")
        self.assertEqual(r.returncode, 0, r.stderr)
        d = self.home / "Projets/Mon-Projet-e"                             # filtré : lettres, chiffres, - et _
        self.assertTrue(d.is_dir(), r.stdout)
        self.assertEqual(r.stdout.splitlines()[0], str(d))
        self.assertTrue((d / "README.md").read_text().startswith("# Mon-Projet-e"))
        self.assertTrue((d / "main.py").exists())
        appels = (self.home / "git-appels").read_text().splitlines()
        self.assertEqual(appels, [f"git -c core.hooksPath=/dev/null init -q --template= {d}"])
        self.assertIn(f"cd {d}", r.stdout)
        self.assertIn(str(d), (self.home / ".local/state/nc/code-projets").read_text())
        l = json.loads(self.lancer("--liste-json").stdout)
        self.assertFalse([p for p in l if p["chemin"] == str(d)][0]["disque"], "un projet voulu n'est pas « trouvé sur le disque »")

    def test_nouveau_projet_modeles_et_refus(self):
        self.faux_git_init()
        for modele, fichier in (("vide", "README.md"), ("c", "main.c"), ("web", "index.html")):
            r = self.lancer("--nouveau", "p-" + modele, "--modele", modele, "--session-seule")
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertTrue((self.home / "Projets" / ("p-" + modele) / fichier).exists())
        self.assertEqual(self.lancer("--nouveau", "x", "--modele", "rust", "--session-seule").returncode, 1)
        self.assertEqual(self.lancer("--nouveau", "../..", "--session-seule").returncode, 1)        # rien de gardé
        self.assertEqual(self.lancer("--nouveau", "***", "--session-seule").returncode, 1)
        self.assertEqual(self.lancer("--nouveau", "--session-seule").returncode, 1)                 # pas de nom
        self.assertFalse((self.home / "Projets/x").exists())
        # déjà pris : refusé, rien d'écrasé
        (self.home / "Projets/p-c/main.c").write_text("MON CODE")
        r = self.lancer("--nouveau", "p-c", "--modele", "c", "--session-seule")
        self.assertEqual(r.returncode, 1)
        self.assertIn("déjà pris", r.stderr)
        self.assertEqual((self.home / "Projets/p-c/main.c").read_text(), "MON CODE")
        (self.home / "Projets/fichier").write_text("x")                    # un fichier de ce nom : refusé aussi
        self.assertEqual(self.lancer("--nouveau", "fichier", "--session-seule").returncode, 1)

    def test_nouveau_projet_dossier_reglable(self):
        self.faux_git_init()
        self.reglages(f"CODE_DOSSIER={self.home}/mes-codes\n")
        r = self.lancer("--nouveau", "essai", "--session-seule")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue((self.home / "mes-codes/essai/README.md").exists())

    # ── cloner depuis GitHub (faux git et faux gh : ils notent leurs arguments, aucun réseau) ──
    def faux_clone(self, gh=False, code_git=0, erreur=""):
        """git : note ses arguments, crée le dernier argument/.git (le clone). gh : connecté ou non, liste, clone."""
        self.programme("git", f'echo "git $*" >> "{self.home}/appels"; [ {code_git} -ne 0 ] && {{ echo "{erreur}" >&2; exit {code_git}; }}\n'
                              f'for d; do :; done; mkdir -p "$d/.git"')
        if gh:
            self.programme("gh", f'echo "gh $*" >> "{self.home}/appels"\n'
                                 'case "$1 $2" in\n'
                                 '  "auth status") exit 0;;\n'
                                 '  "repo list") echo \'[{"name":"mien","url":"https://github.com/moi/mien"},{"name":"x","url":"https://evil.example/moi/x"},'
                                 '{"name":"y","url":"https://github.com/..//y"}]\';;\n'
                                 '  "repo clone") mkdir -p "$4/.git";;\n'
                                 'esac')

    def appels(self):
        f = self.home / "appels"
        return f.read_text().splitlines() if f.exists() else []

    def test_source_github_entrees_acceptees_et_refusees(self):
        m = self.module_nc_code()
        for src, attendu in (("https://github.com/moi/depot", ("moi", "depot")), ("https://github.com/moi/depot.git", ("moi", "depot")),
                             ("https://github.com/moi/depot/", ("moi", "depot")), ("git@github.com:moi/depot.git", ("moi", "depot")),
                             ("git@github.com:moi/depot", ("moi", "depot")), ("moi/depot", ("moi", "depot")),
                             ("a.b-c_d/e.f-g_h", ("a.b-c_d", "e.f-g_h")), ("moi/.github", ("moi", ".github"))):
            self.assertEqual(m.source_github(src), attendu, src)
        for src in ("", " moi/depot", "moi/depot ", "moi/depot\n", "http://github.com/moi/depot", "HTTPS://github.com/moi/depot",
                    "https://github.com@evil.example/moi/depot", "https://moi@github.com/moi/depot", "https://user:pw@github.com/moi/depot",
                    "https://github.com.evil.example/moi/depot", "https://evil.example/github.com/moi/depot", "https://github.com:443/moi/depot",
                    "https://github.com/moi/depot?x=1", "https://github.com/moi/depot#f", "https://github.com/moi/depot/tree/main",
                    "https://github.com/moi", "https://github.com//depot", "ssh://git@github.com/moi/depot", "git@evil.example:moi/depot.git",
                    "git@github.com:moi/depot/extra", "file:///etc/passwd", "/etc/passwd", "../depot", "./moi/depot", "moi/../depot",
                    "./depot", "../..", "moi/..", "../depot", "./.", "moi/.", "./moi", "-x/depot", "moi/-depot", "--upload-pack=x/y",
                    "moi/dépôt", "moi/de pot", "moi/de;pot", "moi/$(x)", "moi/`x`", "moi/dep\x00ot", "moi/a\\b", "a/b/c", "moi/.git", "moi/" + "a" * 101,
                    "a" * 40 + "/depot", "https://github.com/moi/depot\n--upload-pack=x", "https://github.com/%2e%2e/depot"):
            self.assertIsNone(m.source_github(src), repr(src))

    def test_cloner_sans_gh_git_clone_https_en_argv(self):
        self.faux_clone()
        r = self.lancer("--cloner", "git@github.com:moi/depot.git", "--session-seule")
        self.assertEqual(r.returncode, 0, r.stderr)
        d = self.home / "Projets/depot"
        self.assertEqual(self.appels(), [f"git -c core.hooksPath=/dev/null -c protocol.allow=never -c protocol.https.allow=always "
                                          f"clone --progress --template= -- https://github.com/moi/depot.git {d}"])
        self.assertEqual(r.stdout.splitlines()[0], str(d))
        self.assertIn(f"cd {d}", r.stdout)
        l = json.loads(self.lancer("--liste-json").stdout)
        self.assertFalse([p for p in l if p["chemin"] == str(d)][0]["disque"], "un dépôt cloné à la demande n'est pas « trouvé sur le disque »")

    def test_cloner_avec_gh_connecte(self):
        self.faux_clone(gh=True)
        r = self.lancer("--cloner", "https://github.com/moi/depot", "--session-seule")
        self.assertEqual(r.returncode, 0, r.stderr)
        d = self.home / "Projets/depot"
        self.assertEqual(self.appels(), ["gh auth status", f"gh repo clone moi/depot {d} -- --template= --progress"])

    def test_cloner_liste_de_ses_depots_gh(self):
        self.faux_clone(gh=True)
        m = self.module_nc_code()
        with self.env_faux():
            self.assertEqual(m.depots_gh(), [("moi", "mien")])             # les URL d'ailleurs ou piégées sont écartées
        self.assertIn("gh repo list --json name,url --limit 50", self.appels())

    def test_cloner_dossier_existant_rien_n_est_lance(self):
        self.faux_clone(gh=True)
        d = self.home / "Projets/depot"
        (d / ".git").mkdir(parents=True)
        (d / "mon-fichier").write_text("à moi")
        r = self.lancer("--cloner", "moi/depot", "--session-seule")
        self.assertEqual(r.returncode, 1)
        self.assertIn("existe déjà", r.stderr)
        self.assertEqual(self.appels(), [], "ni git ni gh, même pas gh auth status")
        self.assertEqual((d / "mon-fichier").read_text(), "à moi")

    def test_cloner_source_refusee_rien_n_est_lance(self):
        self.faux_clone(gh=True)
        for src in ("https://evil.example/moi/depot", "http://github.com/moi/depot", "https://github.com@evil.example/a/b", "../x", "-x/y",
                    "https://github.com/moi/depot?x=1"):
            r = self.lancer("--cloner", src, "--session-seule")
            self.assertEqual(r.returncode, 1, src)
            self.assertIn("Source refusée", r.stderr)
        self.assertEqual(self.appels(), [])
        self.assertFalse((self.home / "Projets").exists())

    def test_cloner_erreurs_claires(self):
        for erreur, mot in (("fatal: repository 'https://github.com/moi/depot.git/' not found", "introuvable"),
                            ("fatal: unable to access 'x': Could not resolve host: github.com", "hors ligne")):
            self.faux_clone(code_git=128, erreur=erreur)
            r = self.lancer("--cloner", "moi/depot", "--session-seule")
            self.assertEqual(r.returncode, 1)
            self.assertIn(mot, r.stderr)
            self.assertFalse((self.home / "Projets/depot").exists())

    def test_cloner_depuis_le_panneau_s_ouvre_dans_kitty(self):
        self.faux_clone()
        self.programme("kitty", f'echo "$*" > "{self.home}/kitty-args"')
        env = dict(HOME=str(self.home), XDG_CONFIG_HOME=str(self.home / ".config"), TMPDIR=str(self.home), NC_LANGUE="fr",
                   PATH=f"{self.faux}:/usr/bin:/bin")
        r = subprocess.run([sys.executable, str(self.home / ".local/bin/nc-code"), "--cloner", "moi/depot"], env=env, capture_output=True,
                           text=True, timeout=30, stdin=subprocess.DEVNULL)
        self.assertEqual(r.returncode, 0, r.stderr)
        for _ in range(50):
            if (self.home / "kitty-args").exists() and (self.home / "kitty-args").stat().st_size:
                break
            time.sleep(0.1)
        self.assertIn("--cloner --ici moi/depot", (self.home / "kitty-args").read_text())
        self.assertEqual(self.appels(), [], "le clone se fait dans la fenêtre kitty, pas ici")

    def test_apercu_json_reflog_readme_sans_jamais_lancer_git(self):
        b = self.depot("dev/neo")
        (b / ".git/HEAD").write_text("ref: refs/heads/essai\n")
        (b / ".git/logs").mkdir()
        (b / ".git/logs/HEAD").write_text("0 1 X <x@y> 1700000000 +0100\tclone: from x\n0 2 X <x@y> 1700000100 +0100\tcommit (initial): Premier\n"
                                          "2 3 X <x@y> 1700000200 +0100\tcommit: Deuxième <b>gras</b>\n3 4 X <x@y> 1700000300 +0100\tcheckout: moving\n")
        (b / "README.md").write_text("# Neo\n\n![logo](x.png)\nUn **outil** pour [coder](https://x).\n\n| a | b |\n<p>html</p>\n")
        (b / ".git/config").write_text('[remote "origin"]\n\turl = https://github.com/moi/neo\n')
        # Un dépôt cloné d'ailleurs peut imposer des commandes à git (core.fsmonitor et filtres clean pour status,
        # log.showSignature et gpg.program pour log) : l'aperçu ne lance JAMAIS git, même avec une config piégée
        (b / ".git/config").write_text('[core]\n\tfsmonitor = touch PIEGE\n[log]\n\tshowSignature = true\n[gpg]\n\tprogram = touch PIEGE\n'
                                      '[remote "origin"]\n\turl = https://github.com/moi/neo\n')
        self.programme("git", f'echo "git $*" >> "{self.home}/git-appels"; exit 0')
        r = self.lancer("--apercu-json", str(b))
        self.assertEqual(r.returncode, 0, r.stderr)
        d = json.loads(r.stdout)
        self.assertEqual(d["branche"], "essai")
        self.assertEqual([c["message"] for c in d["commits"]], ["Deuxième <b>gras</b>", "Premier"], "commits du reflog, du plus récent au plus ancien, tels quels")
        self.assertEqual(d["commits"][0]["quand"], 1700000200)
        self.assertTrue(d["commits"][0]["date"])
        self.assertEqual(d["etat"], "")
        self.assertEqual(d["readme"], "Neo\nUn outil pour coder.\nhtml")
        self.assertEqual(d["github"], "https://github.com/moi/neo")
        # Sans reflog : pas de commits, toujours sans git
        (b / ".git/logs/HEAD").unlink()
        d = json.loads(self.lancer("--apercu-json", str(b)).stdout)
        self.assertEqual((d["commits"], d["etat"]), ([], ""))
        self.assertFalse((self.home / "git-appels").exists(), "git n'a jamais été lancé")
        self.assertFalse((b / "PIEGE").exists())
        # Pas un dépôt, ou un dossier refusé par la session kitty : {} et code 1
        r = self.lancer("--apercu-json", str(self.home))
        self.assertEqual((r.returncode, r.stdout.strip()), (1, "{}"))
        piege = self.depot("dev/x\rlaunch sh")
        self.assertEqual(self.lancer("--apercu-json", str(piege)).stdout.strip(), "{}")

    def test_depot_piege_lu_borne_sans_bloquer(self):
        """Relecture : une archive extraite peut avoir .git/logs/HEAD en lien vers /dev/zero (lu sans fin : la mémoire
        y passe), un FIFO à la place de HEAD ou de config (open() bloqué), un README en lien vers ~/.ssh. Tout est lu
        borné, sans suivre de lien ni bloquer ; rien d'autre n'est montré."""
        b = self.depot("dev/piege")
        (b / ".git/logs").mkdir()
        os.symlink("/dev/zero", b / ".git/logs/HEAD")
        os.mkfifo(b / ".git/HEAD")
        os.mkfifo(b / ".git/config")
        secret = self.home / ".ssh/id_test"
        secret.parent.mkdir()
        secret.write_text("CLE-PRIVEE-FACTICE\n")
        os.symlink(secret, b / "README.md")
        (self.home / ".config/nc/depot").write_text(f"{b}\n")
        debut = time.time()
        r = self.lancer("--apercu-json", str(b))
        self.assertEqual(r.returncode, 0, r.stderr)
        d = json.loads(r.stdout)
        self.assertEqual((d["branche"], d["commits"], d["readme"], d["github"]), ("", [], "", ""))
        r = self.lancer("--liste-json")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn("CLE-PRIVEE", r.stdout)
        self.assertLess(time.time() - debut, 20)

    def test_date_future_ignoree_et_depot_du_disque_marque(self):
        """Une archive datée dans le futur ne passe pas en tête ; un dépôt seulement trouvé par le balayage est marqué
        « disque » (le panneau ne le choisit jamais d'avance)."""
        connu = self.depot("dev/connu")
        trouve = self.depot("dev/archive")
        (trouve / ".git/HEAD").write_text("ref: refs/heads/main\u202egnp.exe\n")
        futur = time.time() + 10 * 365 * 86400
        for f in ("HEAD",):
            os.utime(trouve / ".git" / f, (futur, futur))
        (connu / ".git/HEAD").write_text("ref: refs/heads/main\n")
        (self.home / ".config/nc/depot").write_text(f"{connu}\n")
        l = json.loads(self.lancer("--liste-json").stdout)
        par_nom = {p["nom"]: p for p in l}
        self.assertLess(par_nom["archive"]["quand"], time.time() + 61)
        self.assertTrue(par_nom["archive"]["disque"])
        self.assertFalse(par_nom["connu"]["disque"])
        self.assertNotIn("\u202e", par_nom["archive"]["branche"])                # pas d'inversion du sens d'écriture
        self.assertIn("premierSur()", (BIN.parent.parent / ".config/quickshell/nc-ile/Code.qml").read_text())

    def test_clone_muet_arrete_au_bout_du_delai(self):
        """Un clone bloqué sans rien écrire (réseau suspendu) est arrêté au bout du délai, pas attendu sans fin."""
        import importlib.machinery
        import importlib.util
        ld = importlib.machinery.SourceFileLoader("nc_code_clone", str(BIN / "nc-code"))
        m = importlib.util.module_from_spec(importlib.util.spec_from_loader("nc_code_clone", ld))
        with unittest.mock.patch.dict(os.environ, {"HOME": str(self.home), "XDG_CONFIG_HOME": str(self.home / ".config")}):
            ld.exec_module(m)
        debut = time.monotonic()
        code, _ = m.lancer_clone([sys.executable, "-c", "import time; time.sleep(60)"], dict(os.environ), delai=1)
        self.assertLess(time.monotonic() - debut, 20)
        self.assertNotEqual(code, 0)

    def test_url_github_https_seulement(self):
        import importlib.machinery
        import importlib.util
        ld = importlib.machinery.SourceFileLoader("nc_code_g", str(BIN / "nc-code"))
        m = importlib.util.module_from_spec(importlib.util.spec_from_loader("nc_code_g", ld))
        with unittest.mock.patch.dict(os.environ, {"HOME": str(self.home), "XDG_CONFIG_HOME": str(self.home / ".config"), "NC_LANGUE": "fr"}):
            ld.exec_module(m)
        attendu = "https://github.com/moi/neo"
        for u in ("https://github.com/moi/neo", "https://github.com/moi/neo.git", "http://github.com/moi/neo/", "git@github.com:moi/neo.git",
                  "ssh://git@github.com/moi/neo", "https://x@github.com/moi/neo"):
            self.assertEqual(m.url_github(u), attendu, u)
        for u in ("https://gitlab.com/moi/neo", "https://github.com.evil.io/moi/neo", "https://evil.io/github.com/moi/neo", "git@github.com.evil:moi/neo",
                  "https://github.com/moi", "https://github.com/moi/neo/x", "https://github.com/../neo", "https://github.com/moi/neo?x=1",
                  "https://github.com/moi/neo#f", "https://github.com/moi/a b", "", "javascript:alert(1)", "ftp://github.com/moi/neo"):
            self.assertEqual(m.url_github(u), "", u)
        d = self.depot("dev/neo")
        (d / ".git/config").write_text('[remote "origin"]\n\turl = https://gitlab.com/moi/neo\n[remote "github"]\n\turl = https://github.com/moi/neo\n')
        self.assertEqual(m.origine_github(str(d)), "", "seule l'origine compte")
        self.assertEqual(m.texte_brut("# T\n`a` **b** [c](u) ![i](p)\n\n---\n| t |\n<b>x</b>\n"), "T\na b c\nx")

    def test_super_x_ile_sinon_kitty(self):
        """Sans terminal (Super + X) : le panneau de l'île si « qs -c nc-ile ipc call ile code » répond ; sinon le
        sélecteur kitty d'avant. Le faux qs note ses arguments et ne lance jamais la vraie île."""
        self.programme("qs", f'echo "qs $*" >> "{self.home}/qs-appels"; exit "${{QS_CODE:-0}}"')
        self.programme("kitty", f'echo "kitty $*" >> "{self.home}/kitty-appels"')
        env = dict(HOME=str(self.home), XDG_CONFIG_HOME=str(self.home / ".config"), TMPDIR=str(self.home), NC_LANGUE="fr",
                   PATH=f"{self.faux}:/usr/bin:/bin")
        r = subprocess.run([sys.executable, str(self.home / ".local/bin/nc-code")], env=env, capture_output=True, text=True, timeout=30,
                           stdin=subprocess.DEVNULL)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual((self.home / "qs-appels").read_text(), "qs -c nc-ile ipc call ile code\n")
        self.assertFalse((self.home / "kitty-appels").exists(), "l'île a répondu : pas de fenêtre kitty")
        r = subprocess.run([sys.executable, str(self.home / ".local/bin/nc-code")], env=dict(env, QS_CODE="1"), capture_output=True, text=True,
                           timeout=30, stdin=subprocess.DEVNULL)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("kitty --class nc-code ", (self.home / "kitty-appels").read_text(), "île absente : repli sur le sélecteur kitty")
        self.assertIn("--selecteur", (self.home / "kitty-appels").read_text())
        (self.home / "kitty-appels").unlink()
        subprocess.run([sys.executable, str(self.home / ".local/bin/nc-code")], env=dict(env, NC_CODE_ILE="non"), capture_output=True, timeout=30,
                       stdin=subprocess.DEVNULL)
        self.assertTrue((self.home / "kitty-appels").exists(), "NC_CODE_ILE=non : toujours kitty")
        self.assertEqual((self.home / "qs-appels").read_text().count("\n"), 2, "NC_CODE_ILE=non : qs n'est pas appelé")

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

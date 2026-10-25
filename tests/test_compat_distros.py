"""Compatibilité entre distributions : ce qui marchait sur Arch (jq 1.8) et cassait ailleurs.

1. jq 1.7 (Debian 13) veut UN terme comme valeur d'objet : `{mw: (a) / (b)}` est une erreur de syntaxe,
   `{mw: ((a) / (b))}` passe partout. Contrôle statique de cette forme dans tous les programmes jq des scripts,
   puis, si un jq 1.7 est disponible (NC_TEST_JQ17 ou jq 1.7 dans le PATH), analyse réelle avec `jq -n`.
2. Sans le module curses (openSUSE sans python3XY-curses), nc-reglages garde ses commandes et explique quoi installer.
"""
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
BIN = REPO / "home/.local/bin"
OPS = (" / ", " * ", " + ", " - ", " // ", " % ", " and ", " or ", " == ", " != ", " < ", " > ", " <= ", " >= ", " | ", " as ")


def scripts_jq():
    """Les scripts shell du dépôt qui appellent jq."""
    fichiers = [REPO / "install.sh", REPO / "export.sh"] + sorted(p for p in BIN.iterdir() if p.is_file())
    for f in fichiers:
        try:
            t = f.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        if not t.startswith("#!") or not re.search(r"\bjq\b", t):
            continue
        if "python" in t.splitlines()[0]:
            continue
        yield f, t


def programmes(texte):
    """(numéro de ligne, programme) pour chaque 'programme' entre apostrophes qui suit un appel à jq."""
    for m in re.finditer(r"\bjq\b[^'\n|;]*'([^']*)'", texte):
        yield texte.count("\n", 0, m.start(1)) + 1, m.group(1)


def valeurs_sans_parentheses(programme):
    """Les valeurs d'objet `clé: valeur` qui ont un opérateur hors de toute parenthèse (refusé par jq 1.7)."""
    trouves = []
    for m in re.finditer(r"(?:^|[{,])\s*(\$?[A-Za-z_][A-Za-z_0-9]*|\"[^\"]*\")\s*:\s*", programme, re.M):
        i, prof, v = m.end(), 0, ""
        # on ne s'intéresse qu'aux accolades d'objet : la valeur s'arrête à la virgule ou } de niveau 0
        chaine = False
        while i < len(programme):
            c = programme[i]
            if chaine:
                v += c
                if c == "\\":
                    v += programme[i + 1:i + 2]
                    i += 1
                elif c == '"':
                    chaine = False
            elif c == '"':
                chaine = True
                v += c
            elif c in "([{":
                prof += 1
                v += c
            elif c in ")]}":
                if prof == 0:
                    break
                prof -= 1
                v += c
            elif c == "," and prof == 0:
                break
            else:
                v += c if prof == 0 else "_"
            i += 1
        # au niveau 0, les mots-clés if/reduce/foreach/try/label forment un terme à eux seuls
        if re.match(r"\s*(if|reduce|foreach|try|label|def)\b", v):
            continue
        if any(o in v for o in OPS):
            trouves.append((m.group(1), " ".join(v.split())))
    return trouves


def jq17():
    """Un jq 1.7.x : NC_TEST_JQ17, sinon celui du PATH s'il est en 1.7."""
    for c in (os.environ.get("NC_TEST_JQ17"), shutil.which("jq")):
        if not c:
            continue
        try:
            v = subprocess.run([c, "--version"], capture_output=True, text=True, timeout=10).stdout.strip()
        except (OSError, subprocess.SubprocessError):
            continue
        if v.startswith("jq-1.7"):
            return c
    return None


class JqSeptSyntaxe(unittest.TestCase):
    def test_aucune_valeur_d_objet_sans_parentheses(self):
        vus = 0
        for f, t in scripts_jq():
            for ligne, p in programmes(t):
                vus += 1
                for cle, v in valeurs_sans_parentheses(p):
                    self.fail(f"{f.name}:{ligne} : valeur d'objet « {cle}: {v} » sans parenthèses (jq 1.7 la refuse)")
        self.assertGreater(vus, 10, "aucun programme jq trouvé : l'extraction est cassée")

    def test_le_detecteur_voit_la_forme_fautive(self):
        self.assertTrue(valeurs_sans_parentheses("{mw: (.a // 0) / ($m.scale // 1)}"))
        self.assertTrue(valeurs_sans_parentheses("{a: 1,\n b: .x + 1}"))
        self.assertFalse(valeurs_sans_parentheses("{mw: ((.a // 0) / ($m.scale // 1)), b: (.x | f), c: if .a then 1 else 2 end}"))

    @unittest.skipUnless(jq17(), "pas de jq 1.7 (NC_TEST_JQ17 ou jq 1.7 dans le PATH)")
    def test_syntaxe_avec_jq_17(self):
        jq = jq17()
        for f, t in scripts_jq():
            for ligne, p in programmes(t):
                r = subprocess.run([jq, "-n", p], capture_output=True, text=True, timeout=30, stdin=subprocess.DEVNULL)
                # variables ou entrées absentes : d'autres erreurs, sans lien ; seule la syntaxe compte
                self.assertNotIn("syntax error", r.stderr, f"{f.name}:{ligne} : {r.stderr.strip()[:300]}")


class ReglagesSansCurses(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="nc-sanscurses-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        stub = Path(self.tmp) / "stub"
        stub.mkdir()
        (stub / "curses.py").write_text("raise ImportError('curses absent (test)')\n")
        home = Path(self.tmp) / "home"
        home.mkdir()
        self.env = dict(os.environ, HOME=str(home), XDG_CONFIG_HOME=str(home / ".config"),
                        XDG_STATE_HOME=str(home / ".state"), XDG_CACHE_HOME=str(home / ".cache"),
                        PYTHONPATH=str(stub), NC_LANGUE="fr")
        for k in ("SSH_CONNECTION", "SSH_CLIENT", "SSH_TTY", "WAYLAND_DISPLAY", "HYPRLAND_INSTANCE_SIGNATURE"):
            self.env.pop(k, None)

    def lancer(self, *args, **env):
        return subprocess.run([sys.executable, str(BIN / "nc-reglages"), *args], env=dict(self.env, **env),
                              capture_output=True, text=True, timeout=60, stdin=subprocess.DEVNULL)

    def test_get_set_list_sans_curses(self):
        r = self.lancer("get", "HZ_ECO")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(r.stdout.strip())
        r = self.lancer("set", "HZ_ECO", "60")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.lancer("get", "HZ_ECO").stdout.strip(), "60")
        self.assertIn("HZ_ECO", self.lancer("list").stdout)

    def test_ecran_texte_dit_quoi_installer(self):
        """Le script chargé comme un module, curses introuvable : tui() explique et sort avec 1."""
        code = (
            "import sys, importlib.machinery, importlib.util\n"
            "sys.modules['curses'] = None\n"
            "l = importlib.machinery.SourceFileLoader('nc_reglages', sys.argv[1])\n"
            "m = importlib.util.module_from_spec(importlib.util.spec_from_loader('nc_reglages', l))\n"
            "l.exec_module(m)\n"
            "assert m.curses is None\n"
            "m.tui()\n")
        env = {k: v for k, v in self.env.items() if k != "PYTHONPATH"}
        for langue, mot in (("fr", "Installe-le"), ("en", "Install it")):
            r = subprocess.run([sys.executable, "-c", code, str(BIN / "nc-reglages")], env=dict(env, NC_LANGUE=langue),
                               capture_output=True, text=True, timeout=60, stdin=subprocess.DEVNULL)
            self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
            self.assertIn("curses", r.stderr)
            self.assertIn(mot, r.stderr)
            self.assertIn("python3-curses", r.stderr)

    def test_sans_argument_dans_un_terminal_message_clair(self):
        """Sans île ni curses, `nc-reglages` seul dans un vrai terminal : le message, pas une trace d'erreur."""
        import pty
        maitre, esclave = pty.openpty()
        try:
            r = subprocess.run([sys.executable, str(BIN / "nc-reglages")], env=self.env, stdin=esclave, stdout=esclave,
                               stderr=subprocess.PIPE, text=True, timeout=60)
        finally:
            os.close(esclave)
            os.close(maitre)
        self.assertEqual(r.returncode, 1, r.stderr)
        self.assertIn("Installe-le", r.stderr)
        self.assertNotIn("Traceback", r.stderr)

    def test_catalogue_sans_curses(self):
        r = self.lancer("catalogue")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn("Traceback", r.stderr)


if __name__ == "__main__":
    unittest.main()

"""Compatibilité Python 3.8 : install.sh promet « Python 3.8 ou plus ». Tous les scripts Python du dépôt (hors le
serveur JARVIS, qui exige 3.11) sont parcourus par l'AST : aucune API apparue en 3.9 ou plus, sauf si elle est
protégée (try/except ImportError ou AttributeError, ou test sur sys.version_info) ou listée dans EXCEPTIONS avec
sa raison. Si python3.8 existe sur la machine, chaque script est aussi compilé avec lui."""
import ast
import subprocess
import shutil
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
HOME = REPO / "home"
SERVEUR_JARVIS = HOME / ".local/share/nc-jarvis/server"

# (fichier relatif, règle) -> raison. Vide tant que rien n'est justifié.
EXCEPTIONS = {}

PROTEGE = {"ImportError", "ModuleNotFoundError", "AttributeError"}
MODULES_RECENTS = {"zoneinfo": "3.9", "graphlib": "3.9", "tomllib": "3.11"}
METHODES = {"removeprefix": "3.9", "removesuffix": "3.9", "is_relative_to": "3.9", "with_stem": "3.9",
            "bit_count": "3.10"}
APPELS = {("asyncio", "to_thread"): "3.9", ("functools", "cache"): "3.9", ("math", "lcm"): "3.9",
          ("random", "randbytes"): "3.9", ("ast", "unparse"): "3.9", ("os", "waitstatus_to_exitcode"): "3.9",
          ("itertools", "pairwise"): "3.10", ("sys", "orig_argv"): "3.10", ("math", "cbrt"): "3.11",
          ("argparse", "BooleanOptionalAction"): "3.9", ("asyncio", "TaskGroup"): "3.11",
          ("asyncio", "timeout"): "3.11", ("datetime", "UTC"): "3.11", ("contextlib", "chdir"): "3.11"}
NOMS_TYPING = {"TypeAlias": "3.10", "ParamSpec": "3.10", "Concatenate": "3.10", "TypeGuard": "3.10",
               "Self": "3.11", "LiteralString": "3.11", "Never": "3.11", "Annotated": "3.9",
               "override": "3.12", "TypeVarTuple": "3.11", "Unpack": "3.11", "Required": "3.11"}
GENERIQUES = {"list", "dict", "set", "frozenset", "tuple", "type"}
CLES_GARDE = {"version_info"}


def scripts():
    """Fichiers Python du dépôt : sous home/, shebang python ou extension .py ; hors serveur JARVIS."""
    for p in sorted(HOME.rglob("*")):
        if not p.is_file() or p.is_symlink() or SERVEUR_JARVIS in p.parents:
            continue
        if ".git" in p.parts:
            continue
        if p.suffix == ".py":
            yield p
            continue
        try:
            with open(p, "rb") as f:
                debut = f.readline(200)
        except OSError:
            continue
        if debut.startswith(b"#!") and b"python" in debut:
            yield p
    for nom in ("install", "export"):
        p = REPO / nom
        if p.is_file() and not p.is_symlink():
            with open(p, "rb") as f:
                if b"python" in f.readline(200):
                    yield p


def _noms_exceptions(t):
    if t is None:
        return {"*"}
    if isinstance(t, ast.Tuple):
        return set().union(*[_noms_exceptions(e) for e in t.elts])
    if isinstance(t, ast.Name):
        return {t.id}
    if isinstance(t, ast.Attribute):
        return {t.attr}
    return set()


class Analyseur(ast.NodeVisitor):
    def __init__(self, source):
        self.trouves = []          # (ligne, règle, détail)
        self.protege = 0
        self.annotation = 0
        self.avenir = False        # from __future__ import annotations
        self.fonctions = 0
        self.source = source

    def ajoute(self, n, regle, detail=""):
        if not self.protege:
            self.trouves.append((getattr(n, "lineno", 0), regle, detail))

    # -- protections
    def visit_Try(self, n):
        garde = any(_noms_exceptions(h.type) & PROTEGE for h in n.handlers)
        self.protege += garde
        for s in n.body:
            self.visit(s)
        self.protege -= garde
        for h in n.handlers:
            self.visit(h)
        for s in n.orelse + n.finalbody:
            self.visit(s)

    def visit_TryStar(self, n):
        self.ajoute(n, "except*", "3.11")
        self.generic_visit(n)

    def visit_If(self, n):
        garde = any(isinstance(x, ast.Attribute) and x.attr in CLES_GARDE for x in ast.walk(n.test))
        self.visit(n.test)
        self.protege += garde
        for s in n.body:
            self.visit(s)
        self.protege -= garde
        for s in n.orelse:
            self.visit(s)

    # -- imports
    def visit_Import(self, n):
        for a in n.names:
            base = a.name.split(".")[0]
            if base in MODULES_RECENTS:
                self.ajoute(n, "import " + base, MODULES_RECENTS[base])

    def visit_ImportFrom(self, n):
        base = (n.module or "").split(".")[0]
        if base == "__future__" and any(a.name == "annotations" for a in n.names):
            self.avenir = True
        if base in MODULES_RECENTS:
            self.ajoute(n, "import " + base, MODULES_RECENTS[base])
        for a in n.names:
            if base == "typing" or base == "typing_extensions":
                if base == "typing" and a.name in NOMS_TYPING:
                    self.ajoute(n, "typing." + a.name, NOMS_TYPING[a.name])
            elif (base, a.name) in APPELS:
                self.ajoute(n, f"{base}.{a.name}", APPELS[(base, a.name)])

    # -- attributs et appels
    def visit_Attribute(self, n):
        v = n.value
        if isinstance(v, ast.Name):
            if (v.id, n.attr) in APPELS:
                self.ajoute(n, f"{v.id}.{n.attr}", APPELS[(v.id, n.attr)])
            if v.id in ("typing", "t") and n.attr in NOMS_TYPING and v.id == "typing":
                self.ajoute(n, "typing." + n.attr, NOMS_TYPING[n.attr])
        if n.attr in METHODES and not isinstance(n.ctx, ast.Store):
            self.ajoute(n, "." + n.attr, METHODES[n.attr])
        if n.attr == "readlink" and not (isinstance(v, ast.Name) and v.id == "os"):
            self.ajoute(n, "Path.readlink", "3.9")
        self.generic_visit(n)

    def visit_Call(self, n):
        if isinstance(n.func, ast.Name) and n.func.id == "zip" and any(k.arg == "strict" for k in n.keywords):
            self.ajoute(n, "zip(strict=)", "3.10")
        if isinstance(n.func, ast.Name) and n.func.id in ("isinstance", "issubclass") and len(n.args) > 1 \
                and isinstance(n.args[1], ast.BinOp) and isinstance(n.args[1].op, ast.BitOr):
            self.ajoute(n, "isinstance(x, A | B)", "3.10")
        if isinstance(n.func, ast.Name) and n.func.id == "dataclass" or (
                isinstance(n.func, ast.Attribute) and n.func.attr == "dataclass"):
            for k in n.keywords:
                if k.arg in ("slots", "kw_only", "match_args"):
                    self.ajoute(n, f"dataclass({k.arg}=)", "3.10")
        self.generic_visit(n)

    # -- syntaxe
    def visit_Match(self, n):
        self.ajoute(n, "match/case", "3.10")
        self.generic_visit(n)

    def _est_dict(self, x):
        return isinstance(x, (ast.Dict, ast.DictComp)) or (
            isinstance(x, ast.Call) and isinstance(x.func, ast.Name) and x.func.id == "dict")

    def visit_BinOp(self, n):
        if isinstance(n.op, ast.BitOr):
            if self._est_dict(n.left) or self._est_dict(n.right):
                self.ajoute(n, "dict | dict", "3.9")
            elif self.annotation and not self.avenir:
                self.ajoute(n, "X | Y en annotation évaluée", "3.10")
        self.generic_visit(n)

    def visit_AugAssign(self, n):
        if isinstance(n.op, ast.BitOr) and self._est_dict(n.value):
            self.ajoute(n, "dict |= dict", "3.9")
        self.generic_visit(n)

    def visit_Subscript(self, n):
        if self.annotation and not self.avenir and isinstance(n.value, ast.Name) and n.value.id in GENERIQUES:
            self.ajoute(n, f"{n.value.id}[...] en annotation évaluée", "3.9")
        self.generic_visit(n)

    # -- annotations évaluées (arguments, retour, variable de module ou de classe)
    def _fonction(self, n):
        for a in n.args.posonlyargs + n.args.args + n.args.kwonlyargs + [n.args.vararg, n.args.kwarg]:
            if a is not None and a.annotation is not None:
                self._annote(a.annotation)
        if n.returns is not None:
            self._annote(n.returns)
        for d in n.args.defaults + n.args.kw_defaults + n.decorator_list:
            if d is not None:
                self.visit(d)
        self.fonctions += 1
        for s in n.body:
            self.visit(s)
        self.fonctions -= 1

    visit_FunctionDef = visit_AsyncFunctionDef = _fonction

    def _annote(self, a):
        self.annotation += 1
        self.visit(a)
        self.annotation -= 1

    def visit_AnnAssign(self, n):
        if not self.fonctions:        # dans une fonction, l'annotation d'une variable n'est pas évaluée
            self._annote(n.annotation)
        if n.value is not None:
            self.visit(n.value)
        self.visit(n.target)


def analyser(chemin):
    source = chemin.read_text(encoding="utf-8")
    arbre = ast.parse(source, str(chemin))
    a = Analyseur(source)
    a.visit(arbre)
    return a.trouves


class Python38(unittest.TestCase):
    def test_il_y_a_des_scripts(self):
        self.assertGreater(len(list(scripts())), 20)

    def test_aucune_api_recente(self):
        problemes = []
        for p in scripts():
            rel = str(p.relative_to(REPO))
            for ligne, regle, detail in analyser(p):
                if (rel, regle) in EXCEPTIONS:
                    continue
                problemes.append(f"{rel}:{ligne}: {regle} (Python {detail})")
        self.assertEqual(problemes, [], "API de Python 3.9 ou plus, sans protection :\n" + "\n".join(problemes))

    def test_exceptions_utiles(self):
        trouves = {(str(p.relative_to(REPO)), r) for p in scripts() for _, r, _ in analyser(p)}
        for cle, raison in EXCEPTIONS.items():
            self.assertTrue(raison.strip(), f"exception sans raison : {cle}")
            self.assertIn(cle, trouves, f"exception qui ne sert plus : {cle}")

    def test_le_detecteur_voit_les_cas(self):
        """Le détecteur lui-même : chaque cas doit être vu, et la protection doit marcher."""
        def regles(code):
            a = Analyseur(code)
            a.visit(ast.parse(code))
            return {r for _, r, _ in a.trouves}
        self.assertIn(".removeprefix", regles("x.removeprefix('a')"))
        self.assertIn("import zoneinfo", regles("from zoneinfo import ZoneInfo"))
        self.assertIn("zip(strict=)", regles("zip(a, b, strict=True)"))
        self.assertIn("dict | dict", regles("c = {**a} | b\nd = dict(a) | b"))
        self.assertIn("match/case", regles("match x:\n    case 1:\n        pass"))
        self.assertIn("list[...] en annotation évaluée", regles("def f(a: list[int]): pass"))
        self.assertIn("X | Y en annotation évaluée", regles("def f(a: str | None): pass"))
        self.assertIn("Path.readlink", regles("p.readlink()"))
        self.assertIn("functools.cache", regles("import functools\n@functools.cache\ndef f(): pass"))
        self.assertEqual(regles("def f(a: 'list[int]'): pass"), set())
        self.assertEqual(regles("from __future__ import annotations\ndef f(a: list[int] | None): pass"), set())
        self.assertEqual(regles("def f():\n    x: list[int] = []"), set())
        self.assertEqual(regles("import os\nos.readlink('x')"), set())
        self.assertEqual(regles("try:\n    from zoneinfo import ZoneInfo\nexcept ImportError:\n    pass"), set())
        self.assertEqual(regles("try:\n    x.removeprefix('a')\nexcept AttributeError:\n    pass"), set())
        self.assertIn("import zoneinfo", regles("try:\n    from zoneinfo import ZoneInfo\nexcept ValueError:\n    pass"))

    def test_aide_sans_hyprland_et_chargement_depuis_le_depot(self):
        """nc-keys --help n'appelle pas hyprctl ; nc-raccourci charge nc-keys depuis son propre dossier."""
        import os, sys
        env = dict(os.environ, PATH=str(Path(sys.executable).parent))      # aucun hyprctl, vrai ni faux
        for cmd in ("nc-keys", "nc-raccourci"):
            r = subprocess.run([sys.executable, str(HOME / ".local/bin" / cmd), "--help"], capture_output=True,
                               text=True, env=env, cwd="/")
            self.assertEqual(r.returncode, 0, f"{cmd} --help : {r.stderr}")
            self.assertTrue(r.stdout.strip())

    @unittest.skipUnless(shutil.which("python3.8"), "python3.8 absent de cette machine")
    def test_compile_avec_python38(self):
        py = shutil.which("python3.8")
        for p in scripts():
            r = subprocess.run([py, "-c", "import sys; compile(open(sys.argv[1], encoding='utf-8').read(), sys.argv[1], 'exec')",
                                str(p)], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, f"{p.relative_to(REPO)} ne compile pas en 3.8 :\n{r.stderr}")


if __name__ == "__main__":
    unittest.main()

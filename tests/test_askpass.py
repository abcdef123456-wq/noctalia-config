"""nc-askpass : sortie du mot de passe, Annuler, absence de GTK. Un faux module gi simule la fenêtre."""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(os.environ.get("NC_ASKPASS_SCRIPT") or Path(__file__).resolve().parent.parent / "installeur" / "nc-askpass")
MDP = "mdp-secret-42"

FAUX_GI = '''
import os
class Faux:
    boutons = []
    def __init__(self, **kw):
        self.kw = kw; self.gestionnaires = {}
        if "label" in kw and type(self).__name__ == "Button": Faux.boutons.append(self)
    def connect(self, nom, fn): self.gestionnaires[nom] = fn
    def get_text(self): return %r
    def __getattr__(self, nom): return lambda *a, **k: None
class Button(Faux): pass
class Application(Faux):
    def run(self, argv):
        self.gestionnaires["activate"](self)
        for b in Faux.boutons:
            if b.kw["label"] == os.environ["FAUX_BOUTON"]: b.gestionnaires["clicked"](b)
class Gtk:
    Box = Label = PasswordEntry = Faux
    Button = Button
    class Orientation: VERTICAL = 1
    class Align: END = 1
    @staticmethod
    def init_check(): return True
class Adw:
    ApplicationWindow = Faux
    Application = Application
'''


def lancer(bouton, avec_gi=True, **extra):
    with tempfile.TemporaryDirectory() as d:
        env = {"PATH": os.environ["PATH"], "FAUX_BOUTON": bouton, "PYTHONPATH": d}
        if avec_gi:
            Path(d, "gi").mkdir()
            Path(d, "gi", "__init__.py").write_text("def require_version(*a): pass\n")
            Path(d, "gi", "repository.py").write_text(FAUX_GI % MDP)
        return subprocess.run([sys.executable, "-S", str(SCRIPT), "[sudo] mot de passe : "],
                              env=env, capture_output=True, text=True, timeout=30, stdin=subprocess.DEVNULL)


class TestAskpass(unittest.TestCase):
    def test_valider(self):
        r = lancer("Valider")
        self.assertEqual((r.returncode, r.stdout), (0, MDP + "\n"))
        self.assertNotIn(MDP, r.stderr)

    def test_annuler(self):
        r = lancer("Annuler")
        self.assertEqual((r.returncode, r.stdout), (1, ""))
        self.assertNotIn(MDP, r.stderr)

    def test_sans_gi(self):
        r = lancer("Valider", avec_gi=False)
        self.assertEqual((r.returncode, r.stdout), (1, ""))
        self.assertTrue(r.stderr.strip())

    def test_invite(self):
        ns = {}
        exec(compile(SCRIPT.read_text(), "nc-askpass", "exec"), {"__name__": "x"}, ns)
        self.assertEqual(ns["texte_invite"](["x", " Salut "]), "Salut")
        self.assertEqual(ns["texte_invite"](["x"]), "Mot de passe")


if __name__ == "__main__":
    unittest.main()

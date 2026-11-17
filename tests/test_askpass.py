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
import os, sys
class Faux:
    boutons = []
    touches = []
    langues = []
    def __init__(self, **kw):
        self.kw = kw; self.gestionnaires = {}
        if "label" in kw and type(self).__name__ == "Button": Faux.boutons.append(self)
        if type(self).__name__ == "Touches": Faux.touches.append(self)
    def connect(self, nom, fn): self.gestionnaires[nom] = fn
    def get_text(self): return %r
    def __getattr__(self, nom): return lambda *a, **k: None
class Button(Faux): pass
class Touches(Faux): pass
class Application(Faux):
    def run(self, argv):
        # NON_UNIQUE : sans lui, une 2e instance rend la main aussitôt et sudo croit à un refus
        print("FLAGS=" + str(self.kw.get("flags")), file=sys.stderr)
        self.gestionnaires["activate"](self)
        if os.environ["FAUX_BOUTON"] == "ECHAP":
            print("ECHAP=" + str(Faux.touches[0].gestionnaires["key-pressed"](None, Gdk.KEY_Escape, 0, 0)), file=sys.stderr)
            return
        for b in Faux.boutons:
            if b.kw["label"] == os.environ["FAUX_BOUTON"]: b.gestionnaires["clicked"](b)
class Gtk:
    Box = Label = PasswordEntry = Faux
    Button = Button
    EventControllerKey = Touches
    class Orientation: VERTICAL = 1
    class Align: END = 1
    @staticmethod
    def init_check(): return True
class Gdk:
    KEY_Escape = 65307
class Gio:
    class ApplicationFlags: NON_UNIQUE = "NON_UNIQUE"
class Adw:
    ApplicationWindow = Faux
    Application = Application
'''


def lancer(bouton, avec_gi=True, langue="fr"):
    with tempfile.TemporaryDirectory() as d:
        env = {"PATH": os.environ["PATH"], "FAUX_BOUTON": bouton, "PYTHONPATH": d, "NC_LANGUE": langue}
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

    def test_non_unique(self):
        r = lancer("Valider")
        self.assertIn("FLAGS=NON_UNIQUE", r.stderr)
        self.assertIn("NON_UNIQUE", SCRIPT.read_text())

    def test_echap_vaut_annuler(self):
        r = lancer("ECHAP")
        self.assertEqual((r.returncode, r.stdout), (1, ""))
        self.assertIn("ECHAP=True", r.stderr)

    def test_textes_en(self):
        r = lancer("Cancel", langue="en")
        self.assertEqual((r.returncode, r.stdout), (1, ""))
        r = lancer("OK", langue="en")
        self.assertEqual((r.returncode, r.stdout), (0, MDP + "\n"))

    def test_sans_gi(self):
        r = lancer("Valider", avec_gi=False)
        self.assertEqual((r.returncode, r.stdout), (1, ""))
        self.assertTrue(r.stderr.strip())

    def test_invite(self):
        exec(compile(SCRIPT.read_text(), "nc-askpass", "exec"), ns := {"__name__": "x"})
        self.assertEqual(ns["texte_invite"](["x", " Salut "]), "Salut")
        self.assertEqual(ns["texte_invite"](["x"], {"NC_LANGUE": "fr"}), "Mot de passe")
        self.assertEqual(ns["texte_invite"](["x"], {"LANG": "en_US.UTF-8"}), "Password")
        self.assertEqual(ns["texte_invite"](["x"], {"LANG": "fr_FR.UTF-8"}), "Mot de passe")


if __name__ == "__main__":
    unittest.main()

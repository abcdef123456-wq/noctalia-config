"""Un argument inconnu (--help, faute de frappe) ne doit pas lancer l'action par défaut : usage sur stderr, code 2, rien n'est fait.
Les outils dont l'action a un effet (fond, réseau, énergie, notification, minuteur, fenêtre, fichiers, processus arrêtés…) sont lancés
avec « --zzz-inconnu » dans un HOME, des XDG_* et un TMPDIR jetables, avec de FAUX outils (hyprctl, noctalia, curl, systemctl, swaybg,
kitty, notify-send, sleep, pkill…) qui notent seulement leurs arguments : le journal doit rester vide et le HOME intact."""
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
BIN = REPO / "home/.local/bin"
FAUX = ("hyprctl", "noctalia", "curl", "systemctl", "swaybg", "kitty", "notify-send", "sleep", "pkill", "pgrep", "kill", "magick", "convert",
        "wl-paste", "playerctl", "busctl", "gdbus", "nmcli", "flock", "nc-ia", "xdg-open", "update-desktop-database")
# nom -> (interpréteur, arguments inconnus essayés)
BASH = {"nc-boot-wallpaper": ["--zzz-inconnu", "x"], "nc-finger": ["--zzz-inconnu"], "nc-verrou-media": ["--zzz-inconnu"],
        "nc-presse-capture": ["--zzz-inconnu"], "nc-carousel-thumbs": ["--zzz-inconnu", "surveillance"],
        "nc-session-propre": ["--zzz-inconnu", "abc", "6 7"]}
PYTHON = {"nc-theme-sync": ["--zzz-inconnu"], "nc-verrou-place": ["--zzz-inconnu"], "nc-noctalia-avant": ["--zzz-inconnu"],
          "nc-icones": ["--zzz-inconnu"], "nc-meteo": ["--zzz-inconnu", "texte x"], "nc-demander": ["--zzz-inconnu"],
          "nc-code": ["--zzz-inconnu"]}


class Base(unittest.TestCase):
    def setUp(self):
        parent = "/tmp/claude-1000"
        os.makedirs(parent, exist_ok=True)
        self._tmp = tempfile.TemporaryDirectory(prefix="nc-arg-", dir=parent)
        self.addCleanup(self._tmp.cleanup)
        self.r = Path(self._tmp.name)
        self.home = self.r / "home"
        self.home.mkdir()
        (self.r / "bin").mkdir()
        self.journal = self.r / "journal"
        for nom in FAUX:
            f = self.r / "bin" / nom
            f.write_text('#!/bin/sh\necho "%s $*" >> "%s"\n' % (nom, self.journal))
            f.chmod(f.stat().st_mode | stat.S_IEXEC)
        (self.r / "run").mkdir()
        self.env = {"HOME": str(self.home), "XDG_CONFIG_HOME": str(self.home / ".config"), "XDG_DATA_HOME": str(self.home / ".local/share"),
                    "XDG_STATE_HOME": str(self.home / ".local/state"), "XDG_CACHE_HOME": str(self.home / ".cache"),
                    "XDG_RUNTIME_DIR": str(self.r / "run"), "TMPDIR": str(self.r), "PATH": str(self.r / "bin"), "NC_LANGUE": "fr"}

    def lancer(self, nom, *args):
        interp = [sys.executable] if nom in PYTHON else ["/bin/bash"]
        return subprocess.run(interp + [str(BIN / nom), *args], env=self.env, capture_output=True, text=True, timeout=30,
                              stdin=subprocess.DEVNULL, start_new_session=True)

    def intact(self, nom):
        self.assertFalse(self.journal.exists(), nom + " : un outil a été appelé : " + (self.journal.read_text() if self.journal.exists() else ""))
        self.assertEqual(list(self.home.rglob("*")), [], nom + " : des fichiers ont été écrits dans le HOME")
        self.assertEqual(list((self.r / "run").iterdir()), [], nom + " : rien dans le dossier d'exécution")


class ArgumentInconnu(Base):
    def test_usage_code_2_et_rien_n_est_fait(self):
        for nom, essais in {**BASH, **PYTHON}.items():
            for arg in essais:
                with self.subTest(nom=nom, arg=arg):
                    self.journal.unlink(missing_ok=True)
                    r = self.lancer(nom, *arg.split(" ")) if nom != "nc-session-propre" or arg != "6 7" else self.lancer(nom, "6", "7")
                    self.assertEqual(r.returncode, 2, (nom, arg, r.stdout, r.stderr))
                    self.assertIn("nc-", r.stderr + "x", (nom, arg))
                    self.assertNotEqual(r.stderr.strip(), "", (nom, arg, "l'usage doit être écrit sur stderr"))
                    self.intact(nom)

    def test_aide_code_0_et_rien_n_est_fait(self):
        for nom in list(BASH) + list(PYTHON):
            if nom == "nc-demander":
                continue          # nc-demander charge nc-ia avant tout ; son --help est testé à part
            with self.subTest(nom=nom):
                self.journal.unlink(missing_ok=True)
                r = self.lancer(nom, "--help")
                self.assertEqual(r.returncode, 0, (nom, r.stdout, r.stderr))
                self.assertNotEqual(r.stdout.strip(), "", nom)
                self.intact(nom)

    def test_demander_aide_et_option_inconnue_ne_posent_pas_de_question(self):
        r = self.lancer("nc-demander", "-h")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("nc-demander", r.stdout)
        self.assertFalse(self.journal.exists())

    def test_session_propre_accepte_toujours_un_nombre_de_secondes(self):
        r = self.lancer("nc-session-propre", "0")
        self.assertNotEqual(r.returncode, 2, r.stderr)          # l'usage normal n'est pas refusé (il agit : faux outils seulement)
        self.assertNotIn("usage", r.stderr)


class DemanderFlux(unittest.TestCase):
    def test_question_du_spotlight_qui_commence_par_deux_tirets(self):
        # avec --flux (Spotlight), tout le reste est la question tapée : même « --version … » part à l'IA
        import importlib.machinery
        import importlib.util
        l = importlib.machinery.SourceFileLoader("nc_demander_flux", str(BIN / "nc-demander"))
        spec = importlib.util.spec_from_loader("nc_demander_flux", l)
        m = importlib.util.module_from_spec(spec)
        l.exec_module(m)
        recu = []

        class FausseIA:
            FOURNISSEURS, ANCIENS = {}, {}
            def reglage(self, c, d): return d
            def coupee(self): return False
            def T(self, fr, en): return fr
            def main(self, args): recu.append(args); return 0

        ancien = sys.argv
        try:
            sys.argv = ["nc-demander", "--flux", "--version de python ?"]
            self.assertEqual(m.main(FausseIA()), 0)
            sys.argv = ["nc-demander", "--zzz-inconnu"]
            self.assertEqual(m.main(FausseIA()), 2)
        finally:
            sys.argv = ancien
        self.assertEqual(recu, [["demander", "--flux", "--", "--version de python ?"]])


if __name__ == "__main__":
    unittest.main()

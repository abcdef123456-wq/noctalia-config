"""nc-reglages sans argument (aussi nc-settings), nc-reglages raccourcis et nc-reglages assistant : la fenêtre des
réglages de l'île, sur leur section, quand on est devant le bureau graphique (WAYLAND_DISPLAY ou
HYPRLAND_INSTANCE_SIGNATURE, pas de SSH) et que l'île répond, après la réparation de nc-reglages fenetre s'il le faut ;
sinon l'écran texte comme avant (SSH, console, sans île, île muette). nc-reglages terminal (ou tui) : l'écran texte
exprès. Le script est chargé comme un module : tui, cli et configurer_assistant sont remplacés par des témoins, curses
n'est jamais lancé. HOME temporaire ; faux qs, systemctl, kitty et notify-send seuls dans le PATH."""
import functools
import importlib.machinery
import importlib.util
import io
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock
import warnings

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_reglages_fenetre import FAUX_JOURNAL, FAUX_QS, FAUX_SYSTEMCTL  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
BIN = REPO / "home/.local/bin"
BUREAU = dict(WAYLAND_DISPLAY="wayland-1", HYPRLAND_INSTANCE_SIGNATURE="test", SSH_CONNECTION="", SSH_TTY="")


class Tty(io.StringIO):
    """Un terminal : l'écran texte (tui) plutôt que la liste."""
    def isatty(self):
        return True


class Base(unittest.TestCase):
    def setUp(self):
        d = tempfile.TemporaryDirectory(prefix="nc-reglages-porte-")
        self.addCleanup(d.cleanup)
        self.home = Path(d.name)
        (self.home / ".config/nc").mkdir(parents=True)
        b = self.home / ".local/bin"; b.mkdir(parents=True)
        (b / "nc-reglages").symlink_to(BIN / "nc-reglages")
        self.faux = self.home / "faux"; self.faux.mkdir()
        (self.faux / "python3").symlink_to(sys.executable)          # pour « #!/usr/bin/env python3 »
        for nom, texte in (("qs", FAUX_QS), ("systemctl", FAUX_SYSTEMCTL), ("kitty", FAUX_JOURNAL.format(nom="kitty")),
                           ("notify-send", FAUX_JOURNAL.format(nom="notify-send"))):
            (self.faux / nom).write_text(texte); (self.faux / nom).chmod(0o755)
        # Seuls les faux : le vrai qs (/usr/bin/qs) ne doit jamais être joint
        self.env = dict(os.environ, HOME=str(self.home), PATH=str(self.faux), NC_LANGUE="fr",
                        XDG_CONFIG_HOME=str(self.home / ".config"), **BUREAU)

    def mode(self, m):
        (self.home / "qs-mode").write_text(m + "\n")

    def appels(self):
        f = self.home / "appels"
        return f.read_text().splitlines() if f.exists() else []


class Module(Base):
    """Le choix entre fenêtre et écran texte, vu de l'intérieur : quel témoin est appelé, avec quelle section."""
    def setUp(self):
        super().setUp()
        env = mock.patch.dict(os.environ, self.env)
        env.start()
        self.addCleanup(env.stop)
        self.charger()

    def charger(self, langue="fr"):
        """Le script comme module ; la langue est lue au chargement."""
        os.environ["NC_LANGUE"] = langue
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", ResourceWarning)              # lectures de /sys au chargement
            chargeur = importlib.machinery.SourceFileLoader("nc_reglages_porte", str(BIN / "nc-reglages"))
            self.m = importlib.util.module_from_spec(importlib.util.spec_from_loader(chargeur.name, chargeur))
            chargeur.exec_module(self.m)
        self.temoins = []
        self.m.tui = lambda section=0: self.temoins.append(("tui", self.m.SECTIONS[section]))
        self.m.cli = lambda a: self.temoins.append(("cli", a))
        self.m.configurer_assistant = lambda terminal=False: self.temoins.append(("assistant", terminal)) or 0
        self.m.ile_reparer = functools.partial(self.m.ile_reparer, attente=0.5)   # île muette : test plus court

    def lancer(self, *args, **env):
        os.environ.update(env)
        sortie, erreur = Tty(), io.StringIO()
        with mock.patch.object(sys, "stdin", Tty()), mock.patch.object(sys, "stdout", sortie), \
                mock.patch.object(sys, "stderr", erreur):
            code = self.m.main(list(args))
        return code, sortie.getvalue(), erreur.getvalue()

    def test_sans_argument_la_fenetre(self):
        self.mode("ok")
        code, sortie, _ = self.lancer()
        self.assertEqual(code, 0)
        self.assertEqual(sortie.strip(), "Réglages ouverts dans la fenêtre")
        self.assertEqual(self.temoins, [])                                # curses jamais lancé
        self.assertEqual(self.appels(), ["qs -c nc-ile ipc call ile reglages"])

    def test_hyprland_seul_suffit(self):
        self.mode("ok")
        self.lancer(WAYLAND_DISPLAY="")
        self.assertEqual(self.temoins, [])
        self.assertEqual(self.appels(), ["qs -c nc-ile ipc call ile reglages"])

    def test_en_anglais(self):
        self.mode("ok")
        self.charger("en")
        _, sortie, _ = self.lancer()
        self.assertEqual(sortie.strip(), "Settings opened in the window")

    def test_ssh_ecran_texte(self):
        self.mode("ok")
        for var in ("SSH_CONNECTION", "SSH_TTY"):
            with self.subTest(var):
                self.temoins.clear()
                self.lancer(**{var: "x"})
                os.environ[var] = ""
                self.assertEqual(self.temoins, [("tui", self.m.SECTIONS[0])])
        self.assertEqual(self.appels(), [])                               # l'île n'est même pas appelée

    def test_sans_session_graphique_ecran_texte(self):
        self.mode("ok")
        self.lancer(WAYLAND_DISPLAY="", HYPRLAND_INSTANCE_SIGNATURE="")
        self.assertEqual(self.temoins, [("tui", self.m.SECTIONS[0])])
        self.assertEqual(self.appels(), [])

    def test_sans_ile_ecran_texte(self):
        (self.faux / "qs").unlink()                                       # openSUSE, Debian sans qs compilé
        self.lancer()
        self.assertEqual(self.temoins, [("tui", self.m.SECTIONS[0])])
        self.assertEqual(self.appels(), [])                               # ni redémarrage ni notification

    def test_ile_muette_apres_reparation_ecran_texte(self):
        self.mode("cassee")
        _, sortie, erreur = self.lancer()
        a = self.appels()
        self.assertEqual(a.count("systemctl --user restart nc-ile.service"), 1, a)   # la réparation a été tentée
        self.assertEqual(a.count("qs -c nc-ile ipc call ile reglages"), 2, a)
        self.assertFalse(any(l.startswith(("kitty", "notify-send")) for l in a), a)  # on est déjà dans un terminal
        self.assertEqual(self.temoins, [("tui", self.m.SECTIONS[0])])
        self.assertEqual(sortie, "")
        self.assertIn("L'île ne répond pas : réglages dans le terminal. Diagnostic : nc-diag", erreur)

    def test_ile_reparee_la_fenetre(self):
        self.mode("ancienne")
        _, sortie, _ = self.lancer()
        self.assertEqual(sortie.strip(), "Réglages ouverts dans la fenêtre")
        self.assertEqual(self.temoins, [])

    def test_terminal_et_tui_ecran_texte(self):
        self.mode("ok")
        for nom in ("terminal", "tui"):
            with self.subTest(nom):
                self.temoins.clear()
                self.assertEqual(self.lancer(nom)[0], 0)
                self.assertEqual(self.temoins, [("tui", self.m.SECTIONS[0])])
        self.lancer("terminal", "Shortcuts")
        self.assertEqual(self.temoins[-1], ("tui", "Raccourcis"))
        self.assertEqual(self.appels(), [])                               # l'île n'est jamais appelée

    def test_terminal_section_inconnue(self):
        with self.assertRaises(SystemExit) as e:
            self.lancer("terminal", "Nulle part")
        self.assertIn("section inconnue : Nulle part", str(e.exception.code))
        self.assertEqual(self.temoins, [])

    def test_raccourcis_la_fenetre_sur_sa_section(self):
        self.mode("ok")
        for nom in ("raccourcis", "shortcuts"):
            self.lancer(nom)
        self.assertEqual(self.temoins, [])
        self.assertEqual(self.appels(), ["qs -c nc-ile ipc call ile reglagesSection Raccourcis"] * 2)

    def test_assistant_la_fenetre_sur_sa_section(self):
        self.mode("ok")
        _, sortie, _ = self.lancer("assistant")
        self.assertEqual(sortie.strip(), "Réglages ouverts dans la fenêtre")
        self.assertEqual(self.temoins, [])
        self.assertEqual(self.appels(), ["qs -c nc-ile ipc call ile reglagesSection Agents IA (coucou)"])
        # La connexion à JARVIS est en tête de cette section dans la fenêtre (catalogue qu'elle lit)
        tete = next(x for x in self.m.catalogue({}) if x["section"] == "Agents IA (coucou)")
        self.assertEqual(tete["cle"], "action:jarvis-connexion")

    def test_assistant_en_anglais(self):
        self.mode("ok")
        self.charger("en")
        self.lancer("assistant")
        self.assertEqual(self.appels(), ["qs -c nc-ile ipc call ile reglagesSection AI Agents (coucou)"])

    def test_raccourcis_et_assistant_en_ssh_ecran_texte(self):
        self.mode("ok")
        self.lancer("raccourcis", SSH_CONNECTION="x")
        self.lancer("assistant", SSH_CONNECTION="x")
        self.assertEqual(self.temoins, [("tui", "Raccourcis"), ("assistant", True)])   # questions dans le terminal
        self.assertEqual(self.appels(), [])

    def test_raccourcis_et_assistant_sans_ile_ecran_texte(self):
        (self.faux / "qs").unlink()
        self.lancer("raccourcis")
        self.lancer("assistant")
        self.assertEqual(self.temoins, [("tui", "Raccourcis"), ("assistant", True)])

    def test_autres_commandes_inchangees(self):
        self.mode("ok")
        self.lancer("liste")
        self.lancer("assistant", "verifier")
        self.assertEqual(self.temoins, [("cli", ["liste"]), ("cli", ["assistant", "verifier"])])
        self.assertEqual(self.appels(), [])


class Commande(Base):
    """Le vrai script, lancé comme le ferait l'utilisateur (sortie hors terminal : la liste au lieu de curses)."""
    def lancer(self, *args, **env):
        r = subprocess.run([str(self.home / ".local/bin/nc-reglages"), *args], env=dict(self.env, **env),
                           capture_output=True, text=True, timeout=30)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r

    def test_sans_argument_la_fenetre(self):
        self.mode("ok")
        r = self.lancer()
        time.sleep(0.3)                                                   # un éventuel kitty détaché
        self.assertEqual(r.stdout.strip(), "Réglages ouverts dans la fenêtre")
        self.assertEqual(self.appels(), ["qs -c nc-ile ipc call ile reglages"])

    def test_en_ssh_l_ecran_texte(self):
        self.mode("ok")
        r = self.lancer(SSH_CONNECTION="192.0.2.1 50000 192.0.2.2 22")
        self.assertNotIn("Réglages ouverts dans la fenêtre", r.stdout)
        self.assertIn("HZ_ECO", r.stdout)                                 # hors terminal, l'écran texte donne la liste
        self.assertEqual(self.appels(), [])

    def test_aide(self):
        r = self.lancer("--help")
        for t in ("nc-reglages terminal [SECTION]", "aussi : tui", "nc-settings", "par SSH"):
            self.assertIn(t, r.stdout)
        r = self.lancer("--help", NC_LANGUE="en")
        for t in ("nc-settings terminal [SECTION]", "also: tui", "over SSH", "nc-settings window [SECTION]"):
            self.assertIn(t, r.stdout)


if __name__ == "__main__":
    unittest.main()

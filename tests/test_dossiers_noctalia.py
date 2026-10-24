"""Lot C-3 : les dossiers de Noctalia, cherchés comme lui (configDir, stateDir de src/util/file_utils.h) :
NOCTALIA_*_HOME, puis XDG_*_HOME, puis ~/.config et ~/.local/state (une valeur vide compte comme absente).
nc-verrou-place, nc-noctalia-avant, l'état lu par la vue des fenêtres (Vue.qml) et l'historique du Spotlight
(Recherche.qml) suivent cet ordre ; nc-diag avertit si XDG_CONFIG_HOME ou XDG_STATE_HOME pointe ailleurs (install.sh
copie tout sous ~/.config et ~/.local/state, ce cas n'est pas pris en charge).

Rien ne touche au vrai HOME : HOME, XDG_*, PATH temporaires, faux hyprctl et faux noctalia.
"""
import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

REPO = Path(__file__).resolve().parents[1]
BIN = REPO / "home/.local/bin"
QML = REPO / "home/.config/quickshell/nc-ile"
VARIABLES = ("NOCTALIA_CONFIG_HOME", "NOCTALIA_STATE_HOME", "XDG_CONFIG_HOME", "XDG_STATE_HOME")

CONFIG = """[lockscreen_widgets]
enabled = true
widget_order = ["nc-heure"]

[lockscreen_widgets.widget.nc-heure]
type = "nc/verrou:heure"
output = "eDP-1"
cx = 1.0
cy = 1.0
"""
ETAT = """[theme]
mode = "dark"

[lockscreen_widgets.widget.nc-heure]
type = "nc/verrou:heure"
output = "eDP-1"
cx = 1.0
cy = 1.0
"""


class Dossiers(unittest.TestCase):
    def setUp(self):
        d = tempfile.TemporaryDirectory(prefix="nc-dossiers-")
        self.addCleanup(d.cleanup)
        self.racine = Path(d.name)
        self.home = self.racine / "home"
        self.home.mkdir()
        self.bin = self.racine / "bin"
        self.bin.mkdir()
        self.journal = self.racine / "appels"
        ecrans = json.dumps([{"name": "eDP-1", "width": 2000, "height": 1000, "scale": 1.0, "transform": 0}])
        for nom, corps in (("hyprctl", f"echo '{ecrans}'"), ("noctalia", "")):
            f = self.bin / nom
            f.write_text(f'#!/bin/sh\necho "{nom} $*" >> "{self.journal}"\n{corps}\n')
            f.chmod(0o755)

    def env(self, **valeurs):
        env = dict(os.environ, HOME=str(self.home), PATH=f"{self.bin}:{os.environ['PATH']}")
        for cle in VARIABLES:
            env.pop(cle, None)
        env.update({k: str(v) for k, v in valeurs.items()})
        return env

    def lancer(self, script, **valeurs):
        r = subprocess.run([sys.executable, str(BIN / script)], env=self.env(**valeurs), capture_output=True,
                           text=True, timeout=20)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return r

    def poser(self, config, etat):
        (config / "noctalia").mkdir(parents=True)
        (config / "noctalia/config.toml").write_text(CONFIG)
        (etat / "noctalia").mkdir(parents=True)
        (etat / "noctalia/settings.toml").write_text(ETAT)

    # ── nc-verrou-place ──
    @unittest.skipIf(sys.version_info < (3, 11), "tomllib (Python 3.11) requis par nc-verrou-place")
    def test_verrou_place_dans_les_dossiers_xdg(self):
        config, etat = self.racine / "cfg", self.racine / "st"
        self.poser(config, etat)
        self.lancer("nc-verrou-place", XDG_CONFIG_HOME=config, XDG_STATE_HOME=etat)
        place = (config / "noctalia/zx-verrou.toml").read_text()
        self.assertIn("cx = 1000.0", place)
        self.assertIn("cy = 300.0", place)
        recentre = (etat / "noctalia/settings.toml").read_text()
        self.assertIn("cx = 1000.0", recentre)
        self.assertIn('mode = "dark"', recentre)
        self.assertFalse((self.home / ".config").exists())
        self.assertFalse((self.home / ".local").exists())
        self.assertIn("noctalia msg config-reload", self.journal.read_text())

    @unittest.skipIf(sys.version_info < (3, 11), "tomllib (Python 3.11) requis par nc-verrou-place")
    def test_verrou_place_noctalia_passe_avant_xdg_et_vide_compte_absent(self):
        config, etat = self.racine / "nc-cfg", self.racine / "nc-st"
        self.poser(config, etat)
        self.lancer("nc-verrou-place", NOCTALIA_CONFIG_HOME=config, NOCTALIA_STATE_HOME=etat,
                    XDG_CONFIG_HOME=self.racine / "xdg-cfg", XDG_STATE_HOME=self.racine / "xdg-st")
        self.assertTrue((config / "noctalia/zx-verrou.toml").exists())
        self.assertIn("cx = 1000.0", (etat / "noctalia/settings.toml").read_text())
        self.assertFalse((self.racine / "xdg-cfg").exists())
        # Valeurs vides : comme absentes, donc ~/.config et ~/.local/state
        self.poser(self.home / ".config", self.home / ".local/state")
        self.lancer("nc-verrou-place", NOCTALIA_CONFIG_HOME="", NOCTALIA_STATE_HOME="", XDG_CONFIG_HOME="",
                    XDG_STATE_HOME="")
        self.assertTrue((self.home / ".config/noctalia/zx-verrou.toml").exists())
        self.assertIn("cx = 1000.0", (self.home / ".local/state/noctalia/settings.toml").read_text())

    # ── nc-noctalia-avant ──
    def test_noctalia_avant_nettoie_l_etat_xdg(self):
        etat = self.racine / "st"
        (etat / "noctalia").mkdir(parents=True)
        (etat / "noctalia/settings.toml").write_text(ETAT)
        leurre = self.home / ".local/state/noctalia/settings.toml"
        leurre.parent.mkdir(parents=True)
        leurre.write_text(ETAT)
        self.lancer("nc-noctalia-avant", XDG_STATE_HOME=etat)
        self.assertEqual((etat / "noctalia/settings.toml").read_text(), '[theme]\nmode = "dark"\n\n')
        self.assertEqual(leurre.read_text(), ETAT)

    def test_noctalia_avant_noctalia_state_home_passe_devant(self):
        etat = self.racine / "nc-st"
        (etat / "noctalia").mkdir(parents=True)
        (etat / "noctalia/settings.toml").write_text(ETAT)
        xdg = self.racine / "xdg-st"
        (xdg / "noctalia").mkdir(parents=True)
        (xdg / "noctalia/settings.toml").write_text(ETAT)
        self.lancer("nc-noctalia-avant", NOCTALIA_STATE_HOME=etat, XDG_STATE_HOME=xdg)
        self.assertNotIn("lockscreen_widgets", (etat / "noctalia/settings.toml").read_text())
        self.assertEqual((xdg / "noctalia/settings.toml").read_text(), ETAT)

    # ── Vue.qml et Recherche.qml : la vraie expression du chemin, évaluée par Quickshell hors écran ──
    @unittest.skipUnless(shutil.which("qs"), "Quickshell requis")
    def test_chemins_qml(self):
        sources = {
            "vue": (re.search(r'id: etatNoctalia; path: (.+?); blockLoading', (QML / "Vue.qml").read_text()).group(1),
                    "/noctalia/settings.toml"),
            "usage": (re.search(r'id: fichierUsage\n(?:\s*//.*\n)*\s*path: (.+)\n', (QML / "Recherche.qml").read_text()).group(1),
                      "/noctalia/plugins/data/nc/launcher/usage.json"),
        }
        cas = (({}, str(self.home) + "/.local/state"),
               ({"XDG_STATE_HOME": ""}, str(self.home) + "/.local/state"),
               ({"XDG_STATE_HOME": "/srv/etat"}, "/srv/etat"),
               ({"XDG_STATE_HOME": "/srv/etat", "NOCTALIA_STATE_HOME": "/srv/noctalia"}, "/srv/noctalia"))
        lignes = "".join(f' console.error("CHEMIN {nom}=" + ({expr}));\n' for nom, (expr, _) in sources.items())
        qml = ("import QtQuick\nimport Quickshell\nShellRoot {\n Timer {\n  interval: 10; running: true\n  onTriggered: {\n"
               + lignes + "  Qt.exit(0)\n  }\n }\n}\n")
        (self.racine / "shell.qml").write_text(qml)
        (self.racine / "runtime").mkdir(mode=0o700)
        for valeurs, base in cas:
            with self.subTest(valeurs=valeurs):
                env = self.env(**valeurs)
                env.update(QT_QPA_PLATFORM="offscreen", QT_QUICK_BACKEND="software",
                           XDG_RUNTIME_DIR=str(self.racine / "runtime"), XDG_CACHE_HOME=str(self.racine / "cache"))
                env.pop("WAYLAND_DISPLAY", None)
                r = subprocess.run(["qs", "--no-color", "-p", str(self.racine / "shell.qml")], env=env,
                                   capture_output=True, text=True, timeout=10)
                sortie = r.stdout + r.stderr
                self.assertEqual(r.returncode, 0, sortie)
                for nom, (_, fin) in sources.items():
                    self.assertIn(f"CHEMIN {nom}={base}{fin}\n", sortie)


def charger_diag():
    with mock.patch.dict(os.environ, NC_LANGUE="fr"):
        chargeur = importlib.machinery.SourceFileLoader("nc_diag_xdg", str(BIN / "nc-diag"))
        spec = importlib.util.spec_from_loader("nc_diag_xdg", chargeur)
        m = importlib.util.module_from_spec(spec)
        chargeur.exec_module(m)
    return m


class DiagXdg(unittest.TestCase):
    def setUp(self):
        d = tempfile.TemporaryDirectory(prefix="nc-diag-xdg-")
        self.addCleanup(d.cleanup)
        self.home = d.name
        self.m = charger_diag()

    def bilan(self, **valeurs):
        b = self.m.Bilan(couleurs=False)
        env = {k: v for k, v in os.environ.items() if k not in VARIABLES}
        env.update(HOME=self.home, **{k: v.replace("{HOME}", self.home) for k, v in valeurs.items()})
        with mock.patch.dict(os.environ, env, clear=True):
            self.m.dossiers_xdg(b)
        return b

    def test_ailleurs_averti(self):
        b = self.bilan(XDG_CONFIG_HOME="/srv/reglages", XDG_STATE_HOME="~/etat")
        self.assertEqual(b.attention, 2)
        texte = b.texte()
        self.assertIn("XDG_CONFIG_HOME pointe ailleurs (/srv/reglages) : noctalia-config s'installe dans ~/.config, "
                      "que Noctalia, Hyprland et l'île ne liront pas ; ce cas n'est pas pris en charge", texte)
        self.assertIn("XDG_STATE_HOME pointe ailleurs (~/etat) : noctalia-config s'installe dans ~/.local/state, "
                      "que Noctalia ne lira pas ; ce cas n'est pas pris en charge", texte)
        self.assertIn("retire XDG_CONFIG_HOME de ton environnement", texte)
        # Lues par Noctalia avant XDG_* : le même avertissement
        b = self.bilan(NOCTALIA_CONFIG_HOME="/srv/noctalia", NOCTALIA_STATE_HOME="{HOME}/etat-noctalia")
        self.assertEqual(b.attention, 2)
        self.assertIn("NOCTALIA_CONFIG_HOME pointe ailleurs (/srv/noctalia) : noctalia-config s'installe dans "
                      "~/.config, que Noctalia ne lira pas", b.texte())
        self.assertIn("NOCTALIA_STATE_HOME pointe ailleurs", b.texte())

    def test_absent_vide_ou_par_defaut_rien(self):
        for valeurs in ({}, {"XDG_CONFIG_HOME": "", "XDG_STATE_HOME": ""},
                        {"XDG_CONFIG_HOME": "{HOME}/.config/", "XDG_STATE_HOME": "{HOME}/.local/state//"},
                        {"XDG_CONFIG_HOME": "~/.config", "XDG_STATE_HOME": "~/.local/state/"},
                        {"NOCTALIA_CONFIG_HOME": "", "NOCTALIA_STATE_HOME": "{HOME}/.local/state"}):
            with self.subTest(valeurs=valeurs):
                self.assertEqual(self.bilan(**valeurs).lignes, [])

    def test_constat_dans_la_section_systeme(self):
        source = (BIN / "nc-diag").read_text()
        systeme = source[source.index('b.titre(T("Système", "System"))'):source.index("# ── Hyprland ──")]
        self.assertIn("dossiers_xdg(b)", systeme)


if __name__ == "__main__":
    unittest.main()

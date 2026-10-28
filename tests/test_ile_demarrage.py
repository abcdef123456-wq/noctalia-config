"""Démarrage du shell.qml de l'île en entier, hors écran, pour attraper toute erreur de chargement (« Property value set multiple
times », import cassé, type manquant, TypeError…) que ni qmllint ni les tests page par page ne voient.

Trois essais, tous dans un dossier temporaire avec une COPIE des .qml, lancés par « qs -p » (jamais « qs -c nc-ile », aucun IPC vers
la vraie île), avec WAYLAND_DISPLAY et HYPRLAND_INSTANCE_SIGNATURE retirés, QT_QPA_PLATFORM=offscreen, HOME, XDG_* et TMPDIR isolés,
et aucun bus D-Bus réel (session et système pointent vers rien : ni vrai serveur de notifications, ni vrai UPower). Le qs lancé est
arrêté par son pid, jamais par son nom.

1. Le VRAI shell.qml sous un compositeur Wayland sans écran, s'il est installé (cage, avec WLR_BACKENDS=headless). Sans lui, SAUTÉ :
   Quickshell refuse de démarrer sans Wayland (« No PanelWindow backend loaded »), car l'île est une fenêtre layer-shell. Aucun
   compositeur sans écran n'est installé sur la machine du codeur : cet essai n'y a jamais tourné (non vérifié).
2. Le même shell.qml et tous les autres fichiers, AVEC LES FENÊTRES REMPLACÉES : chaque PanelWindow devient une FloatingWindow et les
   propriétés que seule une fenêtre layer-shell connaît (ancres, calque, zone exclusive, masque, écran) sont retirées de la copie.
   Tout le reste est le vrai code : les singletons, l'île, les chargeurs. Les fenêtres chargées à la demande (LazyLoader : code, fiche,
   projection…) ne sont pas chargées au démarrage et ne sont donc pas couvertes ici.
3. Le vrai shell.qml sans compositeur : l'échec doit être exactement « No PanelWindow backend loaded » (le fichier et l'île se lisent).
Le journal doit être sans « Failed to load configuration », « ERROR », « TypeError », « ReferenceError », « Property value set multiple
times » ; seules exceptions : les deux ERROR dus à l'absence de serveur de son (pipewire) et de bus D-Bus (réseau)."""
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

from tests import _ile_hors_ecran as H

QML = H.QML
ECHECS = ("Failed to load configuration", "TypeError", "ReferenceError", "Property value set multiple times", "is not a type",
          "Cannot assign", "Binding loop", "Unable to assign", "non-existent property", "unavailable")
ATTENDUS = re.compile(r"pipewire.*Failed to connect|quickshell.network: Network will not work")
PROPRIETES_COUCHE = re.compile(r"^\s*(exclusionMode|WlrLayershell\.\w+|mask|aboveWindows|screen|focusable|exclusiveZone)\s*:")
ANCRE_BOOLEEN = re.compile(r"^\s*anchors\.(top|bottom|left|right)\s*:\s*(true|false)\s*$")


def copie(d):
    root = Path(d)
    for sous in ("run", "bin", "home", "cache", "state", "data", "config", "tmp"):
        (root / sous).mkdir(mode=0o700, exist_ok=True)
    for f in QML.iterdir():
        if f.is_dir():
            shutil.copytree(f, root / f.name)
        else:
            shutil.copy2(f, root)
    return root


def sans_couche(texte):
    """Une fenêtre layer-shell devient une fenêtre ordinaire : mêmes enfants, mêmes bindings, sans les propriétés de couche."""
    sortie, bloc, retrait = [], 0, -1
    for l in texte.splitlines():
        if retrait >= 0:                                         # suite d'une valeur sur plusieurs lignes
            if l.strip() == "" or len(l) - len(l.lstrip()) > retrait:
                continue
            retrait = -1
        if bloc > 0:                                             # « anchors { … } » sur plusieurs lignes
            bloc += l.count("{") - l.count("}")
            continue
        if re.match(r"^\s*anchors \{", l):
            bloc = l.count("{") - l.count("}")
            continue
        if ANCRE_BOOLEEN.match(l):
            continue
        if PROPRIETES_COUCHE.match(l):
            retrait = len(l) - len(l.lstrip())
            continue
        sortie.append(l.replace("PanelWindow {", "FloatingWindow {"))
    return "\n".join(sortie) + "\n"


def environnement(root, **plus):
    env = H.environnement(root, **plus)
    env["DBUS_SESSION_BUS_ADDRESS"] = "unix:path=" + str(root / "run/pas-de-bus")
    env["DBUS_SYSTEM_BUS_ADDRESS"] = "unix:path=" + str(root / "run/pas-de-bus-systeme")
    for k in ("XDG_SESSION_TYPE", "XDG_CURRENT_DESKTOP", "XDG_SESSION_ID", "SWAYSOCK", "I3SOCK"):
        env.pop(k, None)
    return env


def demarrer(root, env, duree, avant=()):
    """Lance « qs -p root/shell.qml » (derrière « avant », par exemple cage) ; au bout de « duree » s., l'arrête par son pid."""
    p = subprocess.Popen([*avant, "qs", "--no-color", "-p", str(root / "shell.qml")], env=env, stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT, text=True, stdin=subprocess.DEVNULL)
    try:
        sortie, _ = p.communicate(timeout=duree)
    except subprocess.TimeoutExpired:
        p.terminate()
        try:
            sortie, _ = p.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            p.kill()
            sortie, _ = p.communicate()
    return sortie or ""


def lignes_en_erreur(sortie):
    return [l for l in sortie.splitlines() if any(e in l for e in ECHECS) or (re.search(r"\bERROR\b", l) and not ATTENDUS.search(l))]


@unittest.skipUnless(shutil.which("qs"), "Quickshell requis")
class Demarrage(unittest.TestCase):
    def test_fenetres_remplacees_tout_le_reste_est_le_vrai_code(self):
        with tempfile.TemporaryDirectory(prefix="nc-demarrage-") as d:
            root = copie(d)
            for f in root.glob("*.qml"):
                if "PanelWindow {" in f.read_text():
                    f.write_text(sans_couche(f.read_text()))
            self.assertNotIn("PanelWindow {", (root / "Ile.qml").read_text())
            sortie = demarrer(root, environnement(root), 8)
            self.assertIn("Configuration Loaded", sortie, sortie)
            self.assertEqual(lignes_en_erreur(sortie), [], sortie)
            self.assertNotIn("Launching config: \"" + str(Path.home()), sortie)          # jamais la vraie config

    def test_vrai_shell_sans_wayland_echoue_proprement(self):
        with tempfile.TemporaryDirectory(prefix="nc-demarrage-") as d:
            root = copie(d)
            sortie = demarrer(root, environnement(root), 10)
            self.assertIn("No PanelWindow backend loaded", sortie, sortie)
            # shell.qml et Ile.qml se lisent : l'échec est celui de la fenêtre, pas une erreur du code de l'île
            self.assertNotRegex(sortie, r"TypeError|ReferenceError|multiple times|is not a type|non-existent property")

    @unittest.skipUnless(shutil.which("cage"), "compositeur sans écran (cage) absent : le vrai shell.qml ne peut pas démarrer sans Wayland")
    def test_vrai_shell_sous_cage_sans_ecran(self):
        with tempfile.TemporaryDirectory(prefix="nc-demarrage-") as d:
            root = copie(d)
            env = environnement(root, WLR_BACKENDS="headless", WLR_LIBINPUT_NO_DEVICES="1", WLR_RENDERER="pixman")
            env.pop("QT_QPA_PLATFORM", None)
            sortie = demarrer(root, env, 12, avant=("cage", "--"))
            self.assertIn("Configuration Loaded", sortie, sortie)
            self.assertEqual(lignes_en_erreur(sortie), [], sortie)

    def test_remplacement_des_fenetres(self):
        src = "PanelWindow {\n    id: w\n    anchors { top: true; bottom: true }\n    anchors.top: true\n    exclusionMode: X\n" \
              "    WlrLayershell.layer: a\n                         && b ? c : d\n    color: \"red\"\n    Item {}\n}\n"
        out = sans_couche(src)
        self.assertEqual(out, "FloatingWindow {\n    id: w\n    color: \"red\"\n    Item {}\n}\n")


if __name__ == "__main__":
    unittest.main()

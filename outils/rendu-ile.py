#!/usr/bin/env python3
"""Rendu hors écran de l'île : des PNG pour relire l'allure d'un thème, sans rien afficher sur le vrai bureau.

  outils/rendu-ile.py --sortie DOSSIER [--reglages FICHIER.conf] [--palette palette-ile.json] ETAT...

ETAT : fermee (pilule fermée), musique (pilule avec une musique factice), page (la page Système ouverte),
recherche (Spotlight avec un texte tapé). Un PNG par état : DOSSIER/ETAT.png.
--reglages / --palette : un reglages.conf (lignes CLE=valeur) et un palette-ile.json posés dans le HOME factice, là où
l'île les lit : l'outil ne connaît aucune clé, il simule un thème tel quel.

Comment : une COPIE de nc-ile dans un dossier temporaire court (HOME, XDG_* et TMPDIR dedans, aucun bus D-Bus), la fenêtre
layer-shell devient une fenêtre ordinaire, un petit pilote ajouté à la copie ouvre l'état voulu, attend que les ressorts se
posent, capture la fenêtre en PNG et quitte. Seule la copie est modifiée. Le qs lancé est arrêté par son pid, jamais par nom.
Python 3.8 compatible."""
import argparse
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

DEPOT = Path(__file__).resolve().parents[1]
QML = DEPOT / "home/.config/quickshell/nc-ile"
ETATS = ("fermee", "musique", "page", "recherche")
ATTENTE = 3000                     # ms laissées aux ressorts (ouverture, fondus) avant la capture
LIMITE = 40                        # s : au-delà, qs est arrêté
PROPRIETES_COUCHE = re.compile(r"^\s*(exclusionMode|WlrLayershell\.\w+|mask|aboveWindows|screen|focusable|exclusiveZone)\s*:")
ANCRE_BOOLEEN = re.compile(r"^\s*anchors\.(top|bottom|left|right)\s*:\s*(true|false)\s*$")

FAUX_LECTEUR = """readonly property var lecteurs: [fauxLecteur]
    readonly property var fauxLecteur: QtObject {
        property string trackTitle: "Midnight City"
        property string trackArtist: "M83"
        property string trackArtUrl: ""
        property string identity: "Musique"
        property string desktopEntry: ""
        property string dbusName: "faux"
        property bool isPlaying: true
        property real position: 83
        property real length: 244
        property bool canSeek: true
        property bool canRaise: false
        property bool canTogglePlaying: true
        function togglePlaying() {}
        function raise() {}
        function previous() {}
        function next() {}
    }"""

# Ce que fait le pilote pour chaque état (« etat » est le singleton de l'île).
ACTIONS = {
    "fermee": "",
    "musique": "",
    "page": 'Etat.basculer(nom, true); Etat.aller("systeme")',
    "recherche": 'Etat.saisie = "fir"; Etat.chercher(nom)',
}
PILOTE = """
    Timer {
        interval: 1500; running: true
        onTriggered: {
            var nom = vs.instances[0].modelData.name || "ecran-rendu"
            %(action)s
            grab.start()
        }
    }
    Timer {
        id: grab; interval: %(attente)d
        onTriggered: vs.instances[0].cible.grabToImage(function(r) {
            console.log("RENDU " + (r.saveToFile(Quickshell.env("NCR_PNG")) ? "ok" : "echec"))
            Qt.quit()
        })
    }
"""


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


def dans_le_depot(chemin):
    c = Path(os.path.realpath(str(chemin)))
    return c == DEPOT or DEPOT in c.parents


def preparer(root, etat, reglages, palette):
    for sous in ("run", "home/.config/nc", "cache", "state", "data", "config", "tmp"):
        (root / sous).mkdir(mode=0o700, parents=True, exist_ok=True)
    ile = root / "ile"
    shutil.copytree(str(QML), str(ile))
    for f in ile.glob("*.qml"):
        t = f.read_text()
        if "PanelWindow {" in t:
            # « cible » : la fenêtre ne se capture pas (pas de moteur QML), on capture l'île elle-même
            t = sans_couche(t).replace("id: fen\n", "id: fen\n    readonly property Item cible: ile\n", 1)
            if f.name == "Ile.qml":    # hors écran l'écran n'a pas de nom : « "" === "" » ouvrirait l'île
                t = re.sub(r"\b((?:fen\.)?modelData\.name)\b", r'(\1 || "ecran-rendu")', t)
        f.write_text(t)
    if etat == "musique":
        f = ile / "Etat.qml"
        t, n = re.subn(r"readonly property var lecteurs:.*", lambda m: FAUX_LECTEUR, f.read_text(), count=1)
        if n != 1:
            raise SystemExit("rendu-ile : la ligne « lecteurs » d'Etat.qml a changé, le faux lecteur ne se pose plus")
        f.write_text(t)
    f = ile / "shell.qml"
    t = f.read_text().replace("Variants {", "Variants {\n        id: vs", 1)
    i = t.rindex("}")                                            # fin du ShellRoot
    f.write_text(t[:i] + PILOTE % {"action": ACTIONS[etat], "attente": ATTENTE} + t[i:])
    if reglages:
        shutil.copy2(reglages, str(root / "home/.config/nc/reglages.conf"))
    if palette:
        shutil.copy2(palette, str(root / "home/.config/nc/palette-ile.json"))
    return ile


def environnement(root, png):
    env = {k: v for k, v in os.environ.items() if k in ("PATH", "LANG", "LC_ALL")}
    env.update(HOME=str(root / "home"), XDG_CONFIG_HOME=str(root / "config"), XDG_DATA_HOME=str(root / "data"),
               XDG_CACHE_HOME=str(root / "cache"), XDG_STATE_HOME=str(root / "state"), XDG_RUNTIME_DIR=str(root / "run"),
               TMPDIR=str(root / "tmp"), QT_QPA_PLATFORM="offscreen", QT_QUICK_BACKEND="software", NCR_PNG=str(png),
               DBUS_SESSION_BUS_ADDRESS="unix:path=" + str(root / "run/pas-de-bus"),
               DBUS_SYSTEM_BUS_ADDRESS="unix:path=" + str(root / "run/pas-de-bus-systeme"), NC_LANGUE="fr")
    return env


def rendre(etat, sortie, reglages, palette):
    """Un qs par état. Retourne (chemin du PNG ou None, journal)."""
    racine = Path(tempfile.mkdtemp(prefix="nci-", dir="/tmp"))
    png = Path(sortie) / (etat + ".png")
    try:
        ile = preparer(racine, etat, reglages, palette)
        p = subprocess.Popen(["qs", "--no-color", "-p", str(ile / "shell.qml")], env=environnement(racine, png),
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, stdin=subprocess.DEVNULL)
        try:
            journal, _ = p.communicate(timeout=LIMITE)
        except subprocess.TimeoutExpired:
            p.terminate()
            try:
                journal, _ = p.communicate(timeout=10)
            except subprocess.TimeoutExpired:
                p.kill()
                journal, _ = p.communicate()
        return (png if png.exists() and "RENDU ok" in (journal or "") else None), journal or ""
    finally:
        shutil.rmtree(str(racine), ignore_errors=True)


def main(argv=None):
    a = argparse.ArgumentParser(description="PNG hors écran de l'île, pour relire l'allure d'un thème.")
    a.add_argument("--sortie", required=True, help="dossier des PNG (hors du dépôt)")
    a.add_argument("--reglages", help="reglages.conf à simuler (CLE=valeur)")
    a.add_argument("--palette", help="palette-ile.json à simuler")
    a.add_argument("etats", nargs="+", choices=ETATS, metavar="ETAT", help="un ou plusieurs de : " + ", ".join(ETATS))
    o = a.parse_args(argv)
    if dans_le_depot(o.sortie):
        print("rendu-ile : le dossier de sortie ne doit pas être dans le dépôt", file=sys.stderr)
        return 2
    for f in (o.reglages, o.palette):
        if f and not os.path.isfile(f):
            print("rendu-ile : fichier introuvable : " + f, file=sys.stderr)
            return 2
    if not shutil.which("qs"):
        print("rendu-ile : Quickshell (qs) est absent", file=sys.stderr)
        return 2
    os.makedirs(o.sortie, exist_ok=True)
    code = 0
    for etat in o.etats:
        png, journal = rendre(etat, o.sortie, o.reglages, o.palette)
        if png:
            print(png)
        else:
            code = 1
            print("rendu-ile : échec pour « %s »\n%s" % (etat, journal[-1500:]), file=sys.stderr)
    return code


if __name__ == "__main__":
    sys.exit(main())

"""Aide des tests de l'île hors écran : un dossier temporaire avec une COPIE des vrais .qml demandés, des singletons
Reglages (réglages réglables par le test) et Etat (fourni par le test) de remplacement, puis le vrai qs lancé par
« qs -p » (jamais « qs -c nc-ile ») sans Wayland, avec HOME, XDG_* et TMPDIR dans le dossier temporaire.
Les erreurs de chargement et d'exécution du journal font échouer le test."""
import os
from pathlib import Path
import shutil
import subprocess

REPO = Path(__file__).resolve().parents[1]
QML = REPO / "home/.config/quickshell/nc-ile"

REGLAGES = """pragma Singleton
import QtQuick
QtObject {
    property var valeurs: ({})
    property var faux: []
    readonly property bool en: false
    readonly property bool sobre: false
    readonly property bool iaCoupee: true
    function t(fr, en) { return fr }
    function val(k, d) { return valeurs[k] !== undefined ? valeurs[k] : d }
}
"""
ENTETE = "import QtQuick\nimport QtQuick.Window\nimport Quickshell\n"
OUTILS = """
    function verifier(ok, message) { if (!ok) { console.error("ECHEC: " + message); Qt.exit(2) } return ok }
    function trouver(item, nom) { if (item.objectName === nom) return item; for (var i = 0; i < item.children.length; i++) { var r = trouver(item.children[i], nom); if (r) return r } return null }
    function tous(item, nom, l) { l = l || []; if (item.objectName === nom) l.push(item); for (var i = 0; i < item.children.length; i++) tous(item.children[i], nom, l); return l }
"""
ERREURS = ("ECHEC", "ReferenceError", "TypeError", "Cannot assign", "Binding loop", "is not a type", "Unable to assign",
           "Property value set multiple times", "Failed to load configuration", "ERROR")


def preparer(d, noms, etat="", extra=None, singletons=()):
    """Copie les .qml « noms » (sans extension) dans d ; Reglages et Etat de remplacement ; extra : {nom: texte} de fichiers
    écrits tels quels (singletons « singletons » déclarés dans le qmldir)."""
    root = Path(d)
    for sous in ("run", "bin", "home", "cache", "state", "data", "config", "tmp"):
        (root / sous).mkdir(mode=0o700, exist_ok=True)
    for nom in noms:
        shutil.copy2(QML / (nom + ".qml"), root)
    (root / "Reglages.qml").write_text(REGLAGES)
    (root / "Etat.qml").write_text("pragma Singleton\nimport QtQuick\nQtObject {\n  readonly property string bin: \"%s/bin/\"\n"
                                   "  property bool ecranVu: true\n  property bool jeu: false\n"
                                   "  property var hauteurs: ({})\n"
                                   "  function annoncerHauteur(nom, h) { var t = Object.assign({}, hauteurs); t[nom] = Math.round(h); hauteurs = t }\n"
                                   "%s\n}\n" % (root, etat))
    for nom, texte in (extra or {}).items():
        (root / nom).write_text(texte)
    lignes = []
    tous = list(noms) + ["Reglages", "Etat"] + [Path(n).stem for n in (extra or {}) if n.endswith(".qml") and n not in ("Reglages.qml", "Etat.qml")]
    for n in dict.fromkeys(tous):
        lignes.append(("singleton " if n in ("Couleurs", "Reglages", "Etat") or n in singletons else "") + n + " 1.0 " + n + ".qml")
    (root / "qmldir").write_text("\n".join(lignes) + "\n")
    return root


def environnement(root, **plus):
    env = dict(os.environ, HOME=str(root / "home"), XDG_CONFIG_HOME=str(root / "config"), XDG_CACHE_HOME=str(root / "cache"),
               XDG_STATE_HOME=str(root / "state"), XDG_DATA_HOME=str(root / "data"), XDG_RUNTIME_DIR=str(root / "run"),
               TMPDIR=str(root / "tmp"), QT_QPA_PLATFORM="offscreen", QT_QUICK_BACKEND="software", **plus)
    env["PATH"] = str(root / "bin") + ":" + env.get("PATH", "")
    for k in ("WAYLAND_DISPLAY", "HYPRLAND_INSTANCE_SIGNATURE", "DISPLAY"):
        env.pop(k, None)
    return env


def lancer(root, delai=30, **plus):
    """Lance « qs -p root/shell.qml » ; rend (code, journal). Le shell.qml du test se termine par Qt.exit."""
    r = subprocess.run(["qs", "--no-color", "-p", str(root / "shell.qml")], env=environnement(root, **plus), capture_output=True,
                       text=True, timeout=delai, stdin=subprocess.DEVNULL)
    return r.returncode, r.stdout + r.stderr


def faux(root, nom, corps="exit 0"):
    """Faux outil dans root/bin : il note « nom arguments » dans root/journal et ne lance jamais le vrai."""
    f = root / "bin" / nom
    f.write_text('#!/bin/sh\necho "%s $*" >> "%s/journal"\n%s\n' % (nom, root, corps))
    f.chmod(0o755)
    return f


def journal(root):
    p = root / "journal"
    return p.read_text() if p.exists() else ""

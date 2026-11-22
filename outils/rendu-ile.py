#!/usr/bin/env python3
"""Rendu hors écran de l'île : des PNG pour relire l'allure d'un thème, sans rien afficher sur le vrai bureau.

  outils/rendu-ile.py --sortie DOSSIER [--reglages FICHIER.conf] [--palette palette-ile.json] ETAT...

ETAT : fermee (pilule fermée), musique (pilule avec une musique factice), page (la page Système ouverte),
recherche (Spotlight avec un texte tapé). Un PNG par état : DOSSIER/ETAT.png.
--polices : dossier de polices lu en plus, en lecture seule (défaut : $XDG_DATA_HOME/fonts ou ~/.local/share/fonts).
--echelle N : 1 (défaut), 2 ou 3 ; l'image est N fois plus grande, dessinée à cette taille (pas agrandie après coup).
Le système est factice (Processeur, 8 cœurs, 16 Go, 45 °C, disque 40 %, batterie 80 %, ni Wi-Fi ni météo ni musique réels) :
les images ne montrent rien de la machine. Les faux scripts vivent dans le HOME temporaire, jamais dans le dépôt.
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
import zlib
import struct
import json

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
MARGE = 24
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
            var i = vs.instances[0].ilot
            console.log("CADRE " + JSON.stringify([i.x, i.y, i.width, i.height, i.parent.width, i.parent.height]))
            console.log("RENDU " + (r.saveToFile(Quickshell.env("NCR_PNG")) ? "ok" : "echec"))
            Qt.quit()
        })
    }
"""

# Faux scripts posés dans le HOME temporaire à la place de ceux du dépôt : valeurs neutres, rien de la vraie machine.
FAUX_ETAT = """#!/bin/sh
case "$1" in
  systeme|system) printf '%s\n' cpu=12 'cpu_nom=Processeur 8 coeurs' ram=40 ram_utilisee=6.4 ram_totale=16.0 temperature=45 \
    disque=40 disque_libre=300 'allume=2 h 05' sante=95 cycles=120 ;;
  jeu|game) printf '%s\n' cpu=12 cpu_temp=45 ;;
  profils|profiles) echo ppd=1 ;;
  sante|health|capteurs|sensors|limite-bin|charge-limit-path|wifi|bt|bluetooth|son|sound|audio|media|sans-media) ;;
  *) printf '%s\n' volume=60 muet=0 micro_muet=0 luminosite=70 jeu=0 halo=0 batterie=80 batterie_etat=Discharging ;;
esac
"""
FAUX_APPS = """#!/bin/sh
[ "$1" = list ] && echo '[{"id":"firefox.desktop","name":"Firefox","generic":"Navigateur web","comment":"","keywords":"","exe":"firefox","icon":"","wmclass":""},{"id":"firmware.desktop","name":"Firmware","generic":"Mises à jour","comment":"","keywords":"","exe":"firmware","icon":"","wmclass":""}]'
exit 0
"""
FAUX = {"nc-apps": FAUX_APPS, "nc-logiciels": "#!/bin/sh\necho '[]'\n", "nc-gpu-mode": "#!/bin/sh\necho '{}'\n", "nc-ile-etat": FAUX_ETAT, "nc-meteo": "#!/bin/sh\nexit 1\n", "nc-brightness": "#!/bin/sh\necho 70\n"}


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
    for sous in ("run", "home/.config/nc", "home/.local", "cache", "state", "data", "config", "tmp"):
        (root / sous).mkdir(mode=0o700, parents=True, exist_ok=True)
    # l'île lance $HOME/.local/bin/nc-apps (recherche) : liens vers les scripts du dépôt (lus seulement), sauf les faux
    bin_ = root / "home/.local/bin"
    bin_.mkdir()
    for f in (DEPOT / "home/.local/bin").iterdir():
        if f.name not in FAUX:
            (bin_ / f.name).symlink_to(f)
    for nom, texte in FAUX.items():
        (bin_ / nom).write_text(texte)
        (bin_ / nom).chmod(0o755)
    ile = root / "ile"
    shutil.copytree(str(QML), str(ile))
    for f in ile.glob("*.qml"):
        t = f.read_text()
        if "PanelWindow {" in t:
            # « cible » : le contenu de la fenêtre (contour et lueur y sont dessinés derrière l'île), « ilot » : l'île
            t = sans_couche(t).replace("id: fen\n", "id: fen\n    readonly property Item cible: racine\n    readonly property Item ilot: ile\n", 1)
            if f.name == "Ile.qml":    # tout le dessin dans un Item de la scène : seul un Item se capture (la fenêtre, non)
                t = t.replace("    Item {\n        id: fondClic", "    Item {\n    id: racine\n    anchors.fill: parent\n    Item {\n        id: fondClic", 1)
                t = t.rstrip()
                t = t[:t.rindex("}")] + "}\n}\n"
                t = re.sub(r"(implicitHeight:).*", r"\1 700", t, count=1)    # fenêtre assez haute pour les pages ouvertes
                t = re.sub(r"(implicitWidth:).*", r"\1 800", t, count=1)     # et assez large, même quand l'échelle réduit l'écran
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


def polices_par_defaut():
    """Polices de l'utilisateur (Material Symbols y est d'ordinaire), lues seulement ; None si absent."""
    d = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
    d = os.path.join(d, "fonts")
    return d if os.path.isdir(d) else None


def config_polices(root, polices):
    """fonts.conf temporaire : celui du système + le dossier de polices ; le cache va dans le dossier temporaire."""
    f = root / "fonts.conf"
    f.write_text('<?xml version="1.0"?>\n<fontconfig>\n<include ignore_missing="yes">/etc/fonts/fonts.conf</include>\n'
                 "<dir>%s</dir>\n<cachedir>%s</cachedir>\n</fontconfig>\n" % (polices, root / "cache/fontconfig"))
    return f


def environnement(root, png, polices=None, echelle=1):
    env = {k: v for k, v in os.environ.items() if k in ("PATH", "LANG", "LC_ALL")}
    env.update(HOME=str(root / "home"), XDG_CONFIG_HOME=str(root / "config"), XDG_DATA_HOME=str(root / "data"),
               XDG_CACHE_HOME=str(root / "cache"), XDG_STATE_HOME=str(root / "state"), XDG_RUNTIME_DIR=str(root / "run"),
               TMPDIR=str(root / "tmp"), QT_QPA_PLATFORM="offscreen", QT_QUICK_BACKEND="software", NCR_PNG=str(png),
               DBUS_SESSION_BUS_ADDRESS="unix:path=" + str(root / "run/pas-de-bus"),
               DBUS_SYSTEM_BUS_ADDRESS="unix:path=" + str(root / "run/pas-de-bus-systeme"), NC_LANGUE="fr")
    if echelle != 1:
        env["QT_SCALE_FACTOR"] = str(echelle)
    if polices:
        env["FONTCONFIG_FILE"] = str(config_polices(root, polices))
    return env


def lire_png(chemin):
    """PNG 8 bits RGB ou RGBA (ce que Qt écrit) -> (largeur, hauteur, octets par pixel, lignes d'octets)."""
    d = Path(chemin).read_bytes()
    i, idat, w = 8, b"", None
    while i < len(d):
        n, k = struct.unpack(">I4s", d[i:i + 8])
        c = d[i + 8:i + 8 + n]
        if k == b"IHDR":
            w, h, prof, typ = struct.unpack(">IIBB", c[:10])
            if prof != 8 or typ not in (2, 6):
                raise ValueError("PNG inattendu")
        elif k == b"IDAT":
            idat += c
        i += 12 + n
    bpp = 3 if typ == 2 else 4
    brut, ligne, lignes = zlib.decompress(idat), w * bpp, []
    prec = bytearray(ligne)
    for y in range(h):
        f, cur = brut[y * (ligne + 1)], bytearray(brut[y * (ligne + 1) + 1:(y + 1) * (ligne + 1)])
        for x in range(ligne):
            a = cur[x - bpp] if x >= bpp else 0
            b = prec[x]
            c = prec[x - bpp] if x >= bpp else 0
            if f == 1:
                cur[x] = (cur[x] + a) & 255
            elif f == 2:
                cur[x] = (cur[x] + b) & 255
            elif f == 3:
                cur[x] = (cur[x] + (a + b) // 2) & 255
            elif f == 4:
                pa, pb, pc = abs(b - c), abs(a - c), abs(a + b - 2 * c)
                cur[x] = (cur[x] + (a if pa <= pb and pa <= pc else (b if pb <= pc else c))) & 255
        lignes.append(bytes(cur))
        prec = cur
    return w, h, bpp, lignes


def ecrire_png(chemin, w, h, bpp, lignes):
    def bloc(k, c):
        return struct.pack(">I", len(c)) + k + c + struct.pack(">I", zlib.crc32(k + c) & 0xffffffff)
    brut = b"".join(b"\0" + l for l in lignes)
    Path(chemin).write_bytes(b"\x89PNG\r\n\x1a\n" + bloc(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2 if bpp == 3 else 6, 0, 0, 0))
                             + bloc(b"IDAT", zlib.compress(brut)) + bloc(b"IEND", b""))


def recadrer(png, cadre):
    """Ne garde de la fenêtre que l'île et MARGE px autour (contour, lueur) ; hors fenêtre : noir."""
    x, y, ew, eh, pw, ph = cadre
    w, h, bpp, lignes = lire_png(png)
    e = w / pw if pw else 1
    x0, y0 = int(round((x - MARGE) * e)), int(round((y - MARGE) * e))
    lw, lh = int(round((ew + 2 * MARGE) * e)), int(round((eh + 2 * MARGE) * e))
    noir = bytes(bpp) * lw
    sortie = []
    for j in range(y0, y0 + lh):
        if not 0 <= j < h:
            sortie.append(noir)
            continue
        a, b = max(x0, 0), min(x0 + lw, w)
        sortie.append(bytes(bpp) * (a - x0) + lignes[j][a * bpp:b * bpp] + bytes(bpp) * max(0, x0 + lw - b))
    ecrire_png(png, lw, lh, bpp, sortie)


def png_valide(chemin):
    """Vrai si le PNG est en RGBA (type 6, octet 25 de l'en-tête) et si son coin haut gauche (la marge) est transparent."""
    try:
        with open(str(chemin), "rb") as f:
            if f.read(8) != b"\x89PNG\r\n\x1a\n":
                return False
            f.seek(25)
            if f.read(1) != b"\x06":
                return False
        _, _, bpp, lignes = lire_png(chemin)
        return bpp == 4 and lignes[0][3] == 0
    except (OSError, ValueError, IndexError, zlib.error):
        return False


def rendre(etat, sortie, reglages, palette, polices=None, echelle=1):
    """Un qs par état ; Qt sort parfois du RGB (coins noirs) : jusqu'à 3 essais. Retourne (chemin du PNG ou None, journal)."""
    journal = ""
    for _ in range(3):
        png, journal = essai(etat, sortie, reglages, palette, polices, echelle)
        if png and png_valide(png):
            return png, journal
    return None, "PNG sans transparence (RGB au lieu de RGBA) après 3 essais\n" + journal


def essai(etat, sortie, reglages, palette, polices, echelle):
    racine = Path(tempfile.mkdtemp(prefix="nci-", dir="/tmp"))
    png = Path(sortie) / (etat + ".png")
    try:
        ile = preparer(racine, etat, reglages, palette)
        p = subprocess.Popen(["qs", "--no-color", "-p", str(ile / "shell.qml")], env=environnement(racine, png, polices, echelle),
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
        m = re.search(r"CADRE (\[.*?\])", journal or "")
        if not (png.exists() and "RENDU ok" in (journal or "") and m):
            return None, journal or ""
        recadrer(png, json.loads(m.group(1)))
        return png, journal
    finally:
        shutil.rmtree(str(racine), ignore_errors=True)


def main(argv=None):
    a = argparse.ArgumentParser(description="PNG hors écran de l'île, pour relire l'allure d'un thème.")
    a.add_argument("--sortie", required=True, help="dossier des PNG (hors du dépôt)")
    a.add_argument("--reglages", help="reglages.conf à simuler (CLE=valeur)")
    a.add_argument("--palette", help="palette-ile.json à simuler")
    a.add_argument("--polices", help="dossier de polices lu en plus (défaut : le dossier fonts de l'utilisateur)")
    a.add_argument("--echelle", type=int, default=1, help="1 (défaut), 2 ou 3 : taille de l'image")
    a.add_argument("etats", nargs="+", choices=ETATS, metavar="ETAT", help="un ou plusieurs de : " + ", ".join(ETATS))
    o = a.parse_args(argv)
    if dans_le_depot(o.sortie):
        print("rendu-ile : le dossier de sortie ne doit pas être dans le dépôt", file=sys.stderr)
        return 2
    if o.polices and not os.path.isdir(o.polices):
        print("rendu-ile : dossier de polices introuvable : " + o.polices, file=sys.stderr)
        return 2
    if o.echelle not in (1, 2, 3):
        print("rendu-ile : l'échelle doit être 1, 2 ou 3", file=sys.stderr)
        return 2
    polices = o.polices or polices_par_defaut()
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
        png, journal = rendre(etat, o.sortie, o.reglages, o.palette, polices, o.echelle)
        if png:
            print(png)
        else:
            code = 1
            print("rendu-ile : échec pour « %s »\n%s" % (etat, journal[-1500:]), file=sys.stderr)
    return code


if __name__ == "__main__":
    sys.exit(main())

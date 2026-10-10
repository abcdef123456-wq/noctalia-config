#!/usr/bin/env python3
"""Correctif de compatibilité Qt 6.12 pour Noctalia 4.4.3 (branche legacy-v4, non maintenue).

Problème : Qt 6.12 ajoute un type QtQuick `Color` qui masque le singleton `Color` de
qs.Commons. Toutes les couleurs de Noctalia deviennent `undefined` (barre et panneaux illisibles).
Correctif repris d'omarchy PR #14553 : importer `qs.Commons as Commons` et écrire `Commons.Color`.

Le paquet système (/etc/xdg/quickshell/noctalia-shell) n'est pas modifié. Une copie corrigée
est créée dans ~/.config/quickshell/noctalia-shell, que Quickshell charge en priorité pour
`qs -c noctalia-shell`.
Retour arrière : supprimer ~/.config/quickshell/noctalia-shell, puis
systemctl --user restart noctalia.

Usage : noctalia-qt612-patch.py [--force]
"""
import re
import shutil
import subprocess
import sys
from pathlib import Path

SRC = Path("/etc/xdg/quickshell/noctalia-shell")
DST = Path.home() / ".config/quickshell/noctalia-shell"
EXPECTED = "4.4.3"

ver = subprocess.run(["pacman", "-Q", "noctalia-shell"], capture_output=True, text=True).stdout.split()
if len(ver) < 2 or not ver[1].startswith(EXPECTED):
    sys.exit(f"Version de noctalia-shell inattendue : {ver}. Correctif écrit pour {EXPECTED}.")

if DST.exists():
    if "--force" not in sys.argv:
        sys.exit(f"{DST} existe déjà. Relancer avec --force pour le régénérer.")
    # Arrêt de Noctalia pendant la régénération (sinon il réagit à la disparition de ses fichiers).
    subprocess.run(["systemctl", "--user", "stop", "noctalia.service"], check=False)
    shutil.rmtree(DST)

shutil.copytree(SRC, DST, symlinks=True)

use_re = re.compile(r"(?<![\w.$])Color(?=\s*\.)")
target_re = re.compile(r"(\btarget:\s*)Color\b")
import_commons_re = re.compile(r"^import qs\.Commons\s*$", re.M)
import_any_re = re.compile(r"^import .*$", re.M)
alias_line = "import qs.Commons as Commons"

changed = 0
for f in DST.rglob("*.qml"):
    text = f.read_text(encoding="utf-8")
    new = use_re.sub("Commons.Color", text)
    new = target_re.sub(r"\1Commons.Color", new)
    if new == text:
        continue
    if alias_line not in new:
        m = import_commons_re.search(new)
        if m is None:
            imports = list(import_any_re.finditer(new))
            if not imports:
                sys.exit(f"Aucune ligne import dans {f}")
            m = imports[-1]
        new = new[: m.end()] + "\n" + alias_line + new[m.end():]
    f.write_text(new, encoding="utf-8")
    changed += 1

# Correctif 2 : la barre affichait les espaces de travail Hyprland dans l'ordre de création (3 1 4 2).
# On trie par numéro, comme le font déjà les services Niri et Mango.
hs = DST / "Services/Compositor/HyprlandService.qml"
old = "const hlWorkspaces = Hyprland.workspaces.values;"
src = hs.read_text(encoding="utf-8")
if old not in src:
    sys.exit("Ligne attendue introuvable dans HyprlandService.qml")
hs.write_text(src.replace(old, "const hlWorkspaces = Array.from(Hyprland.workspaces.values).sort((a, b) => a.id - b.id);"), encoding="utf-8")

# Ajout 3 : grande horloge centrale sur l'écran de verrouillage (heure fine + date dans la couleur principale).
ls = DST / "Modules/LockScreen/LockScreen.qml"
anchor = """                LockScreenHeader {
                  id: headerComponent
                }
"""
big_clock = anchor + """
                // Grande horloge centrale (ajout agent-linux)
                Column {
                  id: legionBigClock
                  property date now: new Date()
                  anchors.horizontalCenter: parent.horizontalCenter
                  anchors.verticalCenter: parent.verticalCenter
                  anchors.verticalCenterOffset: -parent.height * 0.10
                  spacing: 2 * Style.uiScaleRatio

                  Timer {
                    interval: 1000
                    running: true
                    repeat: true
                    onTriggered: legionBigClock.now = new Date()
                  }

                  Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: I18n.locale.toString(legionBigClock.now, "HH:mm")
                    font.family: Settings.data.ui.fontDefault
                    font.pointSize: 104 * Style.uiScaleRatio
                    font.weight: Font.Light
                    font.letterSpacing: -2
                    color: Commons.Color.mOnSurface
                  }

                  Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: I18n.locale.toString(legionBigClock.now, "dddd d MMMM")
                    font.family: Settings.data.ui.fontDefault
                    font.pointSize: 22 * Style.uiScaleRatio
                    font.weight: Font.Medium
                    font.capitalization: Font.Capitalize
                    color: Commons.Color.mPrimary
                  }
                }
"""
src = ls.read_text(encoding="utf-8")
if anchor not in src:
    sys.exit("Point d'insertion introuvable dans LockScreen.qml")
ls.write_text(src.replace(anchor, big_clock, 1), encoding="utf-8")

# Ajout 4 : cava (visualiseur audio) ne tourne que pendant une lecture. Sinon, le widget média de la barre et
# celui du bureau le gardent actif en permanence : capture audio continue, PipeWire et CPU sollicités sans musique.
for rel, old, new in [
    ("Modules/Bar/Widgets/MediaMini.qml",
     'readonly property bool needsCava: root.showVisualizer && root.visualizerType !== "" && root.visualizerType !== "none"',
     'readonly property bool needsCava: root.showVisualizer && root.visualizerType !== "" && root.visualizerType !== "none" && MediaService.isPlaying'),
    ("Modules/DesktopWidgets/Widgets/DesktopMediaPlayer.qml",
     """    if (!root.showVisualizer)
      return false;""",
     """    if (!root.showVisualizer || !root.isPlaying)
      return false;"""),
]:
    f = DST / rel
    src = f.read_text(encoding="utf-8")
    if old not in src:
        sys.exit(f"Ligne attendue introuvable dans {rel}")
    f.write_text(src.replace(old, new, 1), encoding="utf-8")

(DST / "QT612_PATCH.txt").write_text(
    f"Copie corrigée de noctalia-shell {EXPECTED} pour Qt 6.12, générée par tools/noctalia-qt612-patch.py (legion-dotfiles)\n"
    f"Fichiers modifiés : {changed}\n"
)
print(f"Copie corrigée : {DST} ({changed} fichiers QML modifiés)")
subprocess.run(["systemctl", "--user", "start", "noctalia.service"], check=False)

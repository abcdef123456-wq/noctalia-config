// Bouton Masquer de la fenêtre active (nc-reglages → Clavier et souris → « Bouton Masquer sur les fenêtres ») :
// Hyprland n'a pas de barre de titre ; un petit rond discret en haut à gauche de la fenêtre active, comme le bouton
// jaune de macOS. Au survol, il grandit et montre « − » ; un clic masque la fenêtre (comme Super + H, nc-fenetre).
// Elle revient d'un clic dans la vue des fenêtres. Caché en plein écran, en mode jeu, dans la vue et sur un bureau caché.
import QtQuick
import Quickshell
import Quickshell.Wayland
import Quickshell.Hyprland

PanelWindow {
    id: b
    required property var modelData
    screen: modelData

    readonly property var moniteur: Hyprland.monitorFor(modelData)
    readonly property var fen: Hyprland.activeToplevel
    readonly property var ipc: fen && fen.lastIpcObject ? fen.lastIpcObject : ({})
    readonly property var mon: moniteur && moniteur.lastIpcObject ? moniteur.lastIpcObject : ({})
    readonly property bool montre: !!fen && !!ipc.at && !!ipc.size && fen.monitor === moniteur
        && (ipc.fullscreen || 0) === 0 && !String(ipc.workspace ? ipc.workspace.name : "").startsWith("special")
        && ipc.size[0] >= 200 && ipc.size[1] >= 120 && !Etat.jeu && !Etat.vueFenetres

    // Le rond se pose à 9 px du coin, à l'intérieur de l'arrondi de la fenêtre
    anchors { top: true; left: true }
    margins.left: montre ? ipc.at[0] - (mon.x || 0) + 5 : 0
    margins.top: montre ? ipc.at[1] - (mon.y || 0) + 5 : 0
    implicitWidth: 30; implicitHeight: 30
    visible: montre
    exclusionMode: ExclusionMode.Ignore
    WlrLayershell.layer: WlrLayer.Top
    WlrLayershell.namespace: "nc-masquer"
    WlrLayershell.keyboardFocus: WlrKeyboardFocus.None
    color: "transparent"

    // Hyprland ne dit pas quand une fenêtre bouge : relire après chaque changement, et souvent pour une fenêtre flottante
    // (qu'on peut traîner) ; une seconde fois après l'animation
    function relire() { Hyprland.refreshToplevels(); Hyprland.refreshMonitors(); apres.restart() }
    Timer { id: apres; interval: 400; onTriggered: { Hyprland.refreshToplevels() } }
    Connections {
        target: Hyprland
        function onRawEvent(e) {
            if (["openwindow", "closewindow", "movewindowv2", "activewindowv2", "changefloatingmode", "fullscreen",
                 "workspacev2", "focusedmonv2", "monitoraddedv2", "monitorremovedv2", "configreloaded"].indexOf(e.name) >= 0) b.relire()
        }
    }
    Timer { interval: 300; repeat: true; running: !!b.fen && b.ipc.floating === true; onTriggered: Hyprland.refreshToplevels() }

    Rectangle {
        id: rond
        anchors.centerIn: parent
        readonly property bool survol: zone.containsMouse
        width: survol ? 22 : 13; height: width; radius: width / 2
        color: Couleurs.jaune
        border.width: 1; border.color: Qt.darker(Couleurs.jaune, 1.35)
        opacity: survol ? 1 : 0.7
        scale: zone.pressed ? 0.88 : 1
        Behavior on width { NumberAnimation { duration: 120; easing.type: Easing.OutCubic } }
        Behavior on opacity { NumberAnimation { duration: 120 } }
        Ico { anchors.centerIn: parent; nom: "remove"; taille: 16; color: "#3d2f00"; opacity: rond.survol ? 1 : 0 }
    }
    MouseArea {
        id: zone
        anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
        onClicked: if (b.fen) {
            var a = String(b.fen.address)
            Quickshell.execDetached([Etat.bin + "nc-fenetre", "reduire", a.startsWith("0x") ? a : "0x" + a])
        }
    }
}

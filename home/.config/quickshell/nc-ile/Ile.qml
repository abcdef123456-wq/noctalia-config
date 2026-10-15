// Une île par écran : pilule noire posée sur la barre de Noctalia (couche au-dessus), qui se déploie en centre de
// contrôle avec un ressort, comme l'île dynamique de l'iPhone. Seule la forme de l'île capte la souris ; un clic
// ailleurs, Échap, Super + C ou un clic sur la pilule la referment.
import QtQuick
import Quickshell
import Quickshell.Wayland
import Quickshell.Hyprland

PanelWindow {
    id: fen
    required property var modelData
    screen: modelData
    readonly property bool ouverte: Etat.ecranOuvert === modelData.name

    anchors { top: true; left: true; right: true }
    implicitHeight: 640
    color: "transparent"
    exclusionMode: ExclusionMode.Ignore
    WlrLayershell.layer: WlrLayer.Overlay
    WlrLayershell.namespace: "nc-ile"
    WlrLayershell.keyboardFocus: ouverte ? WlrKeyboardFocus.OnDemand : WlrKeyboardFocus.None
    mask: Region { item: ile }

    HyprlandFocusGrab {
        windows: [fen]
        active: fen.ouverte
        onCleared: Etat.fermer()
    }

    Rectangle {
        id: ile
        readonly property real largeurOuverte: 432
        readonly property real hauteurOuverte: 546
        anchors.horizontalCenter: parent.horizontalCenter
        y: 9                                        // centrée dans la barre (barre à 6 du bord, 36 de haut)
        width: fen.ouverte ? largeurOuverte : compact.largeur
        height: fen.ouverte ? hauteurOuverte : 30
        radius: fen.ouverte ? 42 : 15
        color: "#000000"
        clip: true

        // Ressort façon iOS : rapide, avec un léger rebond ; le rayon suit sans à-coup
        Behavior on width { SpringAnimation { spring: 3.4; damping: 0.34; epsilon: 0.25 } }
        Behavior on height { SpringAnimation { spring: 3.4; damping: 0.36; epsilon: 0.25 } }
        Behavior on radius { NumberAnimation { duration: 280; easing.type: Easing.OutCubic } }

        Compact {
            id: compact
            anchors.centerIn: parent
            width: parent.width
            opacity: fen.ouverte ? 0 : 1
            Behavior on opacity { NumberAnimation { duration: fen.ouverte ? 90 : 220; easing.type: Easing.OutCubic } }
        }

        MouseArea {
            anchors.fill: parent
            enabled: !fen.ouverte
            acceptedButtons: Qt.LeftButton | Qt.RightButton
            onClicked: e => e.button === Qt.RightButton ? Etat.lecturePause() : Etat.basculer(fen.modelData.name)
            onWheel: w => Etat.reglerVolume(Etat.volume + (w.angleDelta.y > 0 ? 0.05 : -0.05))
        }

        Centre {
            x: 16; y: 16
            width: ile.largeurOuverte - 32
            height: ile.hauteurOuverte - 32
            // Le contenu apparaît quand l'île est presque déployée, et s'efface dès qu'elle se referme
            opacity: fen.ouverte && ile.height > ile.hauteurOuverte * 0.7 ? 1 : 0
            visible: opacity > 0.01
            Behavior on opacity { NumberAnimation { duration: fen.ouverte ? 200 : 80; easing.type: Easing.OutCubic } }
            focus: fen.ouverte
            Keys.onEscapePressed: Etat.fermer()
        }
    }
}

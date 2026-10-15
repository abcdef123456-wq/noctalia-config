// Une île par écran : pilule noire posée sur la barre de Noctalia (couche au-dessus), qui se déploie avec un ressort,
// comme l'île dynamique de l'iPhone. Une fois ouverte, ses pages se suivent verticalement : d'abord ce qui se passe
// (la musique), puis le centre de contrôle ; points sur le bord droit, molette ou glisser à deux doigts pour passer
// de l'une à l'autre ; l'île prend la taille de chaque page. Seule la forme de l'île capte la souris ; un clic
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

    // Taille de chaque page
    readonly property var tailles: ({ musique: Qt.size(430, 214), centre: Qt.size(432, 552) })
    readonly property bool points: Etat.vues.length > 1          // marge à droite pour les points de page
    readonly property size taille: tailles[Etat.vueActive] || tailles.centre

    Rectangle {
        id: ile
        anchors.horizontalCenter: parent.horizontalCenter
        y: 9                                        // centrée dans la barre (barre à 6 du bord, 36 de haut)
        width: fen.ouverte ? fen.taille.width : compact.largeur
        height: fen.ouverte ? fen.taille.height : 30
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
            onClicked: e => e.button === Qt.RightButton ? Etat.lecturePause() : Etat.basculer(fen.modelData.name, false)
            onWheel: w => Etat.reglerVolume(Etat.volume + (w.angleDelta.y > 0 ? 0.05 : -0.05))
        }

        // Glisser entre les pages : molette ou deux doigts (les curseurs gardent la molette pour eux)
        MouseArea {
            id: glisse
            anchors.fill: parent
            enabled: fen.ouverte && Etat.vues.length > 1
            acceptedButtons: Qt.NoButton
            property real cumul: 0
            onWheel: w => {
                cumul += w.pixelDelta.y !== 0 ? w.pixelDelta.y : w.angleDelta.y / 2
                if (Math.abs(cumul) >= 60 && !verrou.running) {
                    Etat.changerVue(cumul > 0 ? -1 : 1)
                    cumul = 0
                    verrou.restart()
                }
            }
            Timer { id: verrou; interval: 450 }
        }

        // Pages, empilées verticalement : celle de la vue active est à sa place, les autres glissent hors de l'île
        Repeater {
            model: Etat.vues
            Item {
                id: pageIle
                required property string modelData
                required property int index
                readonly property size t: fen.tailles[modelData]
                x: (ile.width - t.width) / 2 + 16
                width: t.width - 32 - (fen.points && modelData === "musique" ? 16 : 0)
                height: t.height - 32
                y: 16 + (index - Etat.vue) * (ile.height * 0.6)
                Behavior on y { SpringAnimation { spring: 3.6; damping: 0.4 } }
                readonly property bool active: index === Etat.vue
                // Le contenu apparaît quand l'île a presque sa taille, s'efface dès qu'elle se referme ou change de page
                opacity: fen.ouverte && active && ile.height > t.height * 0.72 ? 1 : 0
                visible: opacity > 0.01
                Behavior on opacity { NumberAnimation { duration: fen.ouverte ? 200 : 80; easing.type: Easing.OutCubic } }
                Loader {
                    anchors.fill: parent
                    sourceComponent: pageIle.modelData === "musique" ? pageMusique : pageCentre
                }
            }
        }
        Component { id: pageMusique; Musique {} }
        Component { id: pageCentre; Centre { focus: fen.ouverte; Keys.onEscapePressed: Etat.fermer() } }

        // Points de page, sur le bord droit (comme le Centre de contrôle de l'iPhone)
        Column {
            anchors.right: parent.right; anchors.rightMargin: 9
            anchors.verticalCenter: parent.verticalCenter
            spacing: 6
            visible: fen.ouverte && Etat.vues.length > 1
            opacity: visible ? 1 : 0
            Behavior on opacity { NumberAnimation { duration: 200 } }
            Repeater {
                model: Etat.vues.length
                Rectangle {
                    required property int index
                    width: 6; height: index === Etat.vue ? 14 : 6; radius: 3
                    color: index === Etat.vue ? "white" : "#5a5a5e"
                    Behavior on height { SpringAnimation { spring: 5; damping: 0.5 } }
                    MouseArea { anchors.fill: parent; anchors.margins: -6; onClicked: { Etat.vue = index; Etat.page = "accueil" } }
                }
            }
        }

        Keys.onEscapePressed: Etat.fermer()
        Keys.onUpPressed: Etat.changerVue(-1)
        Keys.onDownPressed: Etat.changerVue(1)
        focus: fen.ouverte
    }
}

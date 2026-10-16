// Curseur horizontal façon macOS : capsule qui se remplit de blanc, icône à gauche dedans.
// Glisser ou cliquer (la molette et le pavé tactile servent à changer de page).
import QtQuick
import Quickshell.Widgets

ClippingRectangle {
    id: c
    property real valeur: 0
    property string icone: ""
    signal change(real v)
    height: 28; radius: 14
    color: Couleurs.gris3
    Rectangle {
        height: parent.height; color: Couleurs.texte
        width: Math.max(parent.height, parent.width * Math.max(0, Math.min(1, c.valeur)))
        radius: parent.height / 2
        Behavior on width { enabled: !zone.pressed; SpringAnimation { spring: 5; damping: 0.5 } }
    }
    Ico {
        anchors.left: parent.left; anchors.leftMargin: Math.round(c.height * 0.27); anchors.verticalCenter: parent.verticalCenter
        nom: c.icone; taille: Math.round(c.height * 0.55); color: Couleurs.gris3
    }
    MouseArea {
        id: zone
        anchors.fill: parent
        preventStealing: true
        function regler(x) { c.change(Math.max(0, Math.min(1, x / width))) }
        onPressed: e => regler(e.x)
        onPositionChanged: e => { if (pressed) regler(e.x) }
    }
}

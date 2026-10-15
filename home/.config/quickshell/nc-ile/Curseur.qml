// Curseur horizontal façon macOS : capsule qui se remplit de blanc, icône à gauche dedans.
// Glisser, cliquer ou molette.
import QtQuick
import Quickshell.Widgets

ClippingRectangle {
    id: c
    property real valeur: 0
    property string icone: ""
    signal change(real v)
    height: 28; radius: 14
    color: "#3a3a3c"
    Rectangle {
        height: parent.height; color: "white"
        width: Math.max(parent.height, parent.width * Math.max(0, Math.min(1, c.valeur)))
        radius: parent.height / 2
        Behavior on width { enabled: !zone.pressed; SpringAnimation { spring: 5; damping: 0.5 } }
    }
    Ico {
        anchors.left: parent.left; anchors.leftMargin: 7; anchors.verticalCenter: parent.verticalCenter
        nom: c.icone; taille: 16; color: "#3a3a3c"
    }
    MouseArea {
        id: zone
        anchors.fill: parent
        preventStealing: true
        function regler(x) { c.change(Math.max(0, Math.min(1, x / width))) }
        onPressed: e => regler(e.x)
        onPositionChanged: e => { if (pressed) regler(e.x) }
        onWheel: w => c.change(Math.max(0, Math.min(1, c.valeur + (w.angleDelta.y > 0 ? 0.05 : -0.05))))
    }
}

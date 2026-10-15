// Curseur vertical façon iOS : capsule qui se remplit de blanc par le bas, icône en bas.
// Glisser ou cliquer pour régler, molette aussi ; appui long ou clic droit : détails.
import QtQuick
import Quickshell.Widgets

ClippingRectangle {
    id: g
    property real valeur: 0
    property string icone: ""
    signal change(real v)
    signal appuiLong()
    color: "#2c2c2e"
    radius: 26
    scale: zone.pressed ? 1.03 : 1
    Behavior on scale { SpringAnimation { spring: 5; damping: 0.4 } }

    Rectangle {
        anchors.bottom: parent.bottom
        width: parent.width
        height: parent.height * Math.max(0, Math.min(1, g.valeur))
        color: "white"
        Behavior on height { enabled: !zone.pressed; SpringAnimation { spring: 5; damping: 0.5 } }
    }
    Ico {
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 14
        anchors.horizontalCenter: parent.horizontalCenter
        nom: g.icone
        taille: 26
        color: g.valeur > 0.16 ? "#3a3a3c" : "white"
    }
    MouseArea {
        id: zone
        anchors.fill: parent
        preventStealing: true
        acceptedButtons: Qt.LeftButton | Qt.RightButton
        function regler(y) { g.change(Math.max(0, Math.min(1, 1 - y / height))) }
        onPressed: e => { if (e.button === Qt.LeftButton) regler(e.y) }
        onPositionChanged: e => { if (pressed && (e.buttons & Qt.LeftButton)) regler(e.y) }
        onClicked: e => { if (e.button === Qt.RightButton) g.appuiLong() }
        onPressAndHold: g.appuiLong()
    }
}

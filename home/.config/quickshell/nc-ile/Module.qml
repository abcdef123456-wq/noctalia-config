// Module du centre de contrôle : gris foncé d'Apple, très arrondi ; léger enfoncement au clic
import QtQuick

Rectangle {
    id: m
    property bool cliquable: false
    signal clic()
    signal appuiLong()
    color: Couleurs.carte
    radius: 24
    scale: zone.pressed && cliquable ? 0.97 : 1
    Behavior on scale { SpringAnimation { spring: 6; damping: 0.45 } }
    MouseArea {
        id: zone
        anchors.fill: parent
        enabled: m.cliquable
        acceptedButtons: Qt.LeftButton | Qt.RightButton
        onClicked: e => e.button === Qt.RightButton ? m.appuiLong() : m.clic()
        onPressAndHold: m.appuiLong()
    }
}

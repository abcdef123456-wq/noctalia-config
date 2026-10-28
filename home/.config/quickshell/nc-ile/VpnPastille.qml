// Une pastille arrondie de la fenêtre VPN : un texte (brut), un petit point de couleur facultatif, un état « choisi ». Sert aux
// filtres (VpnFiltres.qml) et au kill switch (VpnBarre.qml). Un clic émet clic().
import QtQuick

Rectangle {
    id: p
    property string texte: ""
    property bool choisi: false
    property color point: "transparent"           // transparent : pas de point
    signal clic()
    height: 32; radius: 16
    width: rangee.implicitWidth + 28
    color: choisi ? Qt.alpha(Couleurs.accent, 0.32) : (zone.containsMouse ? Qt.alpha(Couleurs.accent, 0.16) : Qt.alpha(Couleurs.carte, 0.6))
    border.width: 1; border.color: choisi ? Qt.alpha(Couleurs.accent, 0.7) : Qt.alpha(Couleurs.texte, 0.1)
    Behavior on color { enabled: !Reglages.sobre; ColorAnimation { duration: 120 } }
    Accessible.role: Accessible.Button
    Accessible.name: p.texte
    Row {
        id: rangee
        anchors.centerIn: parent; spacing: 7
        Rectangle { visible: p.point.a > 0; anchors.verticalCenter: parent.verticalCenter; width: 8; height: 8; radius: 4; color: p.point }
        Texte { anchors.verticalCenter: parent.verticalCenter; text: p.texte; font.pixelSize: 12; font.weight: p.choisi ? Font.DemiBold : Font.Normal }
    }
    MouseArea { id: zone; anchors.fill: parent; hoverEnabled: true; onClicked: p.clic() }
}

// Bouton du cockpit JARVIS : une pastille comme dans l'île (coins ronds, gris qui s'éclaire au survol, accent si principal)
import QtQuick
Rectangle {
    id: b
    property string texte
    property bool primaire: false
    signal clic()
    implicitWidth: label.implicitWidth + 26; implicitHeight: 32
    radius: 16
    color: primaire ? (z.containsMouse ? Couleurs.accentClair : Couleurs.accent) : (z.containsMouse ? Couleurs.gris3 : Couleurs.gris2)
    Behavior on color { ColorAnimation { duration: 120 } }
    opacity: enabled ? 1 : 0.4
    scale: z.pressed ? 0.97 : 1
    Behavior on scale { SpringAnimation { spring: 6; damping: 0.45 } }
    border.width: activeFocus ? 1 : 0; border.color: Couleurs.texte
    activeFocusOnTab: true
    Texte { id: label; anchors.centerIn: parent; text: b.texte; color: b.primaire ? Couleurs.surAccent : Couleurs.texte; font.weight: Font.DemiBold; font.pixelSize: 13 }
    MouseArea { id: z; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: b.clic() }
    Keys.onReturnPressed: clic()
    Keys.onSpacePressed: clic()
    Accessible.role: Accessible.Button
    Accessible.name: texte
    Accessible.onPressAction: clic()
}

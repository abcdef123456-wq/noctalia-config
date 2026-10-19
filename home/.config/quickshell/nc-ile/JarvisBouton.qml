import QtQuick
Rectangle {
    id: b
    property string texte
    property bool primaire: false
    signal clic()
    implicitWidth: label.implicitWidth + 28; implicitHeight: 38
    radius: 12
    color: primaire ? Couleurs.accent : (z.containsMouse ? Couleurs.gris3 : Couleurs.gris2)
    opacity: enabled ? 1 : 0.4
    border.width: activeFocus ? 1 : 0; border.color: Couleurs.texte
    activeFocusOnTab: true
    Texte { id: label; anchors.centerIn: parent; text: b.texte; color: b.primaire ? Couleurs.surAccent : Couleurs.texte; font.weight: Font.DemiBold }
    MouseArea { id: z; anchors.fill: parent; hoverEnabled: true; onClicked: b.clic() }
    Keys.onReturnPressed: clic()
    Keys.onSpacePressed: clic()
    Accessible.role: Accessible.Button
    Accessible.name: texte
    Accessible.onPressAction: clic()
}

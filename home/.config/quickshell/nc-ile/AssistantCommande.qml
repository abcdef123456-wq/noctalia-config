import QtQuick

Rectangle {
    id: bouton
    property string texte: ""
    property string icone: ""
    property string aide: texte
    property color accent: Couleurs.accent
    property bool choisi: false
    property bool contour: false
    property bool alerte: false
    property bool rond: false
    signal clic()
    implicitWidth: rond ? 36 : libelle.implicitWidth + 24
    implicitHeight: rond ? 36 : 30
    radius: rond ? width / 2 : 10
    color: alerte ? Couleurs.rouge : (choisi ? accent : (contour ? Qt.alpha(accent, zone.containsMouse ? 0.28 : 0.18) : (zone.containsMouse ? Couleurs.gris3 : Couleurs.gris2)))
    border.width: activeFocus || choisi || contour || alerte ? (contour ? 1.5 : 1) : 1
    border.color: alerte ? Qt.lighter(Couleurs.rouge, 1.15) : (activeFocus || choisi || contour ? accent : Couleurs.gris3)
    opacity: enabled ? 1 : 0.45
    activeFocusOnTab: true
    Row {
        id: libelle
        anchors.centerIn: parent; spacing: 5
        Ico {
            visible: bouton.icone !== ""; nom: bouton.icone; taille: bouton.rond && bouton.width >= 42 ? 20 : 16
            color: bouton.alerte ? Couleurs.surCouleur : (bouton.choisi ? Couleurs.surAccent : (bouton.contour ? bouton.accent : (bouton.icone === "volume_off" ? Couleurs.texteSec : bouton.accent)))
        }
        Text {
            visible: bouton.texte !== ""; text: bouton.texte
            font.family: "Adwaita Sans"; font.pixelSize: 12; font.weight: Font.DemiBold
            color: bouton.alerte ? Couleurs.surCouleur : (bouton.choisi ? Couleurs.surAccent : Couleurs.texte)
        }
    }
    MouseArea { id: zone; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: bouton.clic() }
    Keys.onReturnPressed: clic()
    Keys.onSpacePressed: clic()
    Accessible.role: Accessible.Button
    Accessible.name: aide
    Accessible.onPressAction: clic()
}

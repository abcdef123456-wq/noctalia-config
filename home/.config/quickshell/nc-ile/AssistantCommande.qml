import QtQuick

Rectangle {
    id: bouton
    property string texte: ""
    property string icone: ""
    property string aide: texte
    property color accent: "#72def5"
    property bool choisi: false
    property bool contour: false
    property bool alerte: false
    property bool rond: false
    signal clic()
    implicitWidth: rond ? 36 : libelle.implicitWidth + 24
    implicitHeight: rond ? 36 : 30
    radius: rond ? width / 2 : 10
    color: alerte ? "#eb9f93" : (choisi ? accent : (contour ? Qt.alpha(accent, zone.containsMouse ? 0.3 : 0.2) : (zone.containsMouse ? "#344555" : "#273644")))
    border.width: activeFocus || choisi || contour || alerte ? (contour ? 1.5 : 1) : 1
    border.color: alerte ? "#f5b8ae" : (activeFocus || choisi || contour ? accent : "#384c5c")
    opacity: enabled ? 1 : 0.45
    activeFocusOnTab: true
    Row {
        id: libelle
        anchors.centerIn: parent; spacing: 5
        Ico {
            visible: bouton.icone !== ""; nom: bouton.icone; taille: bouton.rond && bouton.width >= 42 ? 20 : 16
            color: bouton.alerte ? "#ffffff" : (bouton.choisi ? "#102735" : (bouton.contour ? bouton.accent : (bouton.icone === "volume_off" ? "#9ab0bf" : bouton.accent)))
        }
        Text {
            visible: bouton.texte !== ""; text: bouton.texte
            font.family: "Adwaita Sans"; font.pixelSize: 12; font.weight: Font.DemiBold
            color: bouton.alerte ? "#ffffff" : (bouton.choisi ? "#102735" : "#edf7fc")
        }
    }
    MouseArea { id: zone; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: bouton.clic() }
    Keys.onReturnPressed: clic()
    Keys.onSpacePressed: clic()
    Accessible.role: Accessible.Button
    Accessible.name: aide
    Accessible.onPressAction: clic()
}

// Un bouton du panneau Cloud JARVIS : pilule arrondie, texte, couleur d'accent ou rouge (action définitive)
import QtQuick

Rectangle {
    id: b
    property string texte: ""
    property string icone: ""
    property bool danger: false
    property bool principal: false
    signal clic()
    implicitWidth: t.implicitWidth + (icone === "" ? 0 : 22) + 24
    width: implicitWidth; height: 30; radius: Couleurs.rayon(15, width, height)
    activeFocusOnTab: true
    opacity: enabled ? 1 : 0.45
    color: danger ? Couleurs.rouge : (principal ? Couleurs.accent : (zone.containsMouse || activeFocus ? Couleurs.carteSurvol : Couleurs.carte))
    readonly property color encre: danger || principal ? Couleurs.surAccent : Couleurs.texte
    Row {
        anchors.centerIn: parent
        spacing: 6
        Ico { visible: b.icone !== ""; nom: b.icone; taille: 16; width: 16; clip: true
              anchors.verticalCenter: parent.verticalCenter; color: b.danger || b.principal ? b.encre : Couleurs.accent }
        Texte { id: t; visible: b.texte !== ""; width: Math.max(0, Math.min(implicitWidth, b.width - (b.icone === "" ? 0 : 22) - 24))
                text: b.texte; color: b.encre; elide: Text.ElideMiddle }
    }
    MouseArea { id: zone; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                onClicked: { b.forceActiveFocus(Qt.MouseFocusReason); b.clic() } }
    Keys.onSpacePressed: if (enabled) clic()
    Keys.onReturnPressed: if (enabled) clic()
    Accessible.role: Accessible.Button
    Accessible.name: b.texte
    Accessible.onPressAction: if (enabled) clic()
}

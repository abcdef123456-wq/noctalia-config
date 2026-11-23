// Bouton pilule de l'en-tête Garmin et des actions d'hydratation.
import QtQuick

Rectangle {
    id: bouton
    required property string texte
    property string icone: ""
    property bool choisi: false
    signal clic()

    implicitWidth: libelle.implicitWidth + 26
    implicitHeight: 32
    radius: Couleurs.rayon(16, width, height)
    color: choisi ? Qt.alpha(Couleurs.accent, 0.28)
           : zone.containsMouse ? Qt.alpha(Couleurs.accent, 0.20) : Qt.alpha(Couleurs.carte, 0.65)
    border.width: 1
    border.color: activeFocus || choisi ? Couleurs.accent : Qt.alpha(Couleurs.texte, 0.1)
    opacity: enabled ? 1 : 0.45
    Behavior on color { enabled: !Reglages.sobre; ColorAnimation { duration: 120 } }
    activeFocusOnTab: true
    Accessible.role: Accessible.Button
    Accessible.name: texte
    Accessible.onPressAction: if (enabled) clic()
    Keys.onReturnPressed: clic()
    Keys.onSpacePressed: clic()

    Row {
        id: libelle
        anchors.centerIn: parent
        spacing: 6
        Ico {
            visible: bouton.icone !== ""
            anchors.verticalCenter: parent.verticalCenter
            nom: bouton.icone; taille: 15
            color: bouton.choisi || zone.containsMouse ? Couleurs.accent : Couleurs.texteSec
        }
        Texte {
            anchors.verticalCenter: parent.verticalCenter
            text: bouton.texte; font.pixelSize: 12
        }
    }
    MouseArea {
        id: zone
        anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
        onClicked: bouton.clic()
    }
}

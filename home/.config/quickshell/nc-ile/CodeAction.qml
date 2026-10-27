// Un bouton d'action rapide de l'espace de code (Code.qml, en bas à droite) : icône, libellé et touche, en verre ;
// l'accent au survol. Ouvrir le dossier, copier le chemin, la page GitHub.
import QtQuick

Rectangle {
    id: bouton
    property string glyphe: ""
    property string libelle: ""
    property string touche: ""
    signal clic()
    width: rangee.implicitWidth + 22; height: 30; radius: 15
    color: zone.containsMouse ? Qt.alpha(Couleurs.accent, 0.25) : Qt.alpha(Couleurs.carte, 0.6)
    border.width: 1; border.color: Qt.alpha(Couleurs.texte, 0.1)
    Behavior on color { enabled: !Reglages.sobre; ColorAnimation { duration: 120 } }
    Row {
        id: rangee
        anchors.centerIn: parent; spacing: 7
        Ico { anchors.verticalCenter: parent.verticalCenter; nom: bouton.glyphe; taille: 16; color: zone.containsMouse ? Couleurs.accent : Couleurs.texteSec }
        Texte { anchors.verticalCenter: parent.verticalCenter; text: bouton.libelle; font.pixelSize: 12 }
        Rectangle {
            visible: bouton.touche !== ""
            anchors.verticalCenter: parent.verticalCenter
            width: libTouche.implicitWidth + 10; height: 18; radius: 5
            color: Qt.alpha(Couleurs.fond, 0.5); border.width: 1; border.color: Qt.alpha(Couleurs.texte, 0.1)
            Texte { id: libTouche; anchors.centerIn: parent; text: bouton.touche; font.pixelSize: 10; secondaire: true }
        }
    }
    MouseArea { id: zone; anchors.fill: parent; hoverEnabled: true; onClicked: bouton.clic() }
}

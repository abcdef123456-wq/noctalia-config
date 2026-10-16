// Bouton rond façon Centre de contrôle iOS : gris éteint, couleur système quand il est actif.
// Clic : action ; appui long ou clic droit : détails (page).
import QtQuick

Rectangle {
    id: r
    property string icone: ""
    property bool actif: false
    property color couleur: Couleurs.accent
    property real taille: 52
    // Icône : couleur du fond sur un bouton allumé (comme l'onglet actif du terminal)
    property color couleurIcone: actif ? Couleurs.surCouleur : Couleurs.texte
    signal clic()
    signal appuiLong()
    width: taille; height: taille; radius: taille / 2
    color: actif ? couleur : (zone.containsMouse ? Couleurs.gris4 : Couleurs.gris3)
    Behavior on color { ColorAnimation { duration: 160 } }
    scale: zone.pressed ? 0.9 : 1
    Behavior on scale { SpringAnimation { spring: 6; damping: 0.4 } }
    Ico { anchors.centerIn: parent; nom: r.icone; taille: r.taille * 0.48; color: r.couleurIcone }
    MouseArea {
        id: zone
        anchors.fill: parent
        hoverEnabled: true
        acceptedButtons: Qt.LeftButton | Qt.RightButton
        onClicked: e => e.button === Qt.RightButton ? r.appuiLong() : r.clic()
        onPressAndHold: r.appuiLong()
    }
}

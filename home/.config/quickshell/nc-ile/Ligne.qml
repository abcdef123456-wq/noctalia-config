// Ligne de liste façon macOS : petite icône dans un rond (bleu si actif), titre, sous-titre, élément à droite
// (coche, cadenas, texte) ; fond qui s'éclaire au survol, léger enfoncement au clic. Clic droit : action secondaire.
import QtQuick

Rectangle {
    id: l
    property string icone: ""
    property string titre: ""
    property string sous: ""
    property bool actif: false
    property string droite: ""          // nom d'icône à droite (check, lock…)
    property color couleurDroite: Couleurs.texteSec
    property bool attente: false        // connexion en cours : petit cercle qui tourne
    signal clic()
    signal clicDroit()
    width: parent ? parent.width : 300
    height: sous !== "" ? 50 : 42
    radius: 12
    color: zone.containsMouse ? Couleurs.gris2 : "transparent"
    Behavior on color { ColorAnimation { duration: 120 } }
    scale: zone.pressed ? 0.98 : 1
    Behavior on scale { SpringAnimation { spring: 6; damping: 0.45 } }

    Row {
        anchors.verticalCenter: parent.verticalCenter; anchors.left: parent.left; anchors.leftMargin: 8; spacing: 11
        Rectangle {
            width: 28; height: 28; radius: 14
            color: l.actif ? Couleurs.accent : Couleurs.gris3
            Behavior on color { ColorAnimation { duration: 160 } }
            Ico { anchors.centerIn: parent; nom: l.icone; taille: 16 }
        }
        Column {
            anchors.verticalCenter: parent.verticalCenter
            Texte { text: l.titre; font.pixelSize: 14; font.weight: Font.Medium; width: Math.min(implicitWidth, l.width - 110) }
            Texte { text: l.sous; secondaire: true; font.pixelSize: 12; visible: l.sous !== ""; width: Math.min(implicitWidth, l.width - 110) }
        }
    }
    Ico {
        anchors.right: parent.right; anchors.rightMargin: 12; anchors.verticalCenter: parent.verticalCenter
        nom: l.attente ? "progress_activity" : l.droite; taille: 18; color: l.attente ? Couleurs.accent : l.couleurDroite
        visible: l.attente || l.droite !== ""
        RotationAnimation on rotation { running: l.attente; from: 0; to: 360; duration: 900; loops: Animation.Infinite }
    }
    MouseArea {
        id: zone
        anchors.fill: parent
        hoverEnabled: true
        acceptedButtons: Qt.LeftButton | Qt.RightButton
        onClicked: e => e.button === Qt.RightButton ? l.clicDroit() : l.clic()
    }
}

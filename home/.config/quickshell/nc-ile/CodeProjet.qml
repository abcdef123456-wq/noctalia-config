// Une ligne de la liste des projets de l'espace de code (Code.qml) : pastille de la couleur du langage, nom, date
// relative à droite ; dessous le chemin court, le langage et la branche (texte brut : Texte.qml). Le survol en fait la
// ligne choisie, un clic l'ouvre. La couleur est un nom de la palette (Couleurs.qml), donné par nc-code.
import QtQuick

Item {
    id: ligne
    property var projet: ({})
    property bool actif: false
    property string badge: ""                       // « Claude travaille » : un agent est déjà au travail dans ce projet
    property color badgeCouleur: Couleurs.accent
    signal survol()
    signal ouvrir()
    width: 300; height: 54
    readonly property color teinte: projet && projet.couleur && Couleurs[projet.couleur] !== undefined ? Couleurs[projet.couleur] : Couleurs.gris4

    Rectangle { id: pastille; x: 16; anchors.verticalCenter: parent.verticalCenter; width: 10; height: 10; radius: 5; color: ligne.teinte }
    Texte {
        id: nom
        anchors.left: pastille.right; anchors.leftMargin: 12; anchors.right: date.left; anchors.rightMargin: 16     // la date garde sa place : un long nom est coupé avant elle
        y: 9; height: 18
        text: ligne.projet && ligne.projet.nom ? ligne.projet.nom : ""
        font.pixelSize: 14; font.weight: Font.DemiBold
    }
    Texte {
        id: date
        anchors.right: parent.right; anchors.rightMargin: 14; y: 10; height: 16
        text: ligne.projet && ligne.projet.date ? ligne.projet.date : ""
        secondaire: true; font.pixelSize: 11
    }
    Texte {
        anchors.left: nom.left; anchors.right: pastilleIA.visible ? pastilleIA.left : parent.right; anchors.rightMargin: pastilleIA.visible ? 8 : 14
        y: 29; height: 16
        secondaire: true; font.pixelSize: 12
        text: ligne.projet ? [ligne.projet.court, ligne.projet.langage, ligne.projet.branche,
                              ligne.projet.disque ? Reglages.t("trouvé sur le disque", "found on disk") : ""].filter(x => x).join("  ·  ") : ""
    }
    Rectangle {
        id: pastilleIA
        objectName: "nc-code-badge"
        visible: ligne.badge !== ""
        anchors.right: parent.right; anchors.rightMargin: 14; y: 28
        width: texteBadge.implicitWidth + 16; height: 18; radius: 9
        color: Qt.alpha(ligne.badgeCouleur, 0.2); border.width: 1; border.color: Qt.alpha(ligne.badgeCouleur, 0.5)
        Texte { id: texteBadge; anchors.centerIn: parent; text: ligne.badge; font.pixelSize: 10; color: ligne.badgeCouleur }
    }
    MouseArea {
        anchors.fill: parent; hoverEnabled: true
        onEntered: ligne.survol()
        onPositionChanged: ligne.survol()
        onClicked: ligne.ouvrir()
    }
}

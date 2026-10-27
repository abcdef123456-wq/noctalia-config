// Une ligne de la liste des projets de l'espace de code (Code.qml) : pastille de la couleur du langage, nom, date
// relative à droite ; dessous le chemin court, le langage et la branche (texte brut : Texte.qml). Le survol en fait la
// ligne choisie, un clic l'ouvre. La couleur est un nom de la palette (Couleurs.qml), donné par nc-code.
import QtQuick

Item {
    id: ligne
    property var projet: ({})
    property bool actif: false
    signal survol()
    signal ouvrir()
    width: 300; height: 54
    readonly property color teinte: projet && projet.couleur && Couleurs[projet.couleur] !== undefined ? Couleurs[projet.couleur] : Couleurs.gris4

    Rectangle { id: pastille; x: 16; anchors.verticalCenter: parent.verticalCenter; width: 10; height: 10; radius: 5; color: ligne.teinte }
    Texte {
        id: nom
        anchors.left: pastille.right; anchors.leftMargin: 12; anchors.right: date.left; anchors.rightMargin: 8
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
        anchors.left: nom.left; anchors.right: parent.right; anchors.rightMargin: 14
        y: 29; height: 16
        secondaire: true; font.pixelSize: 12
        text: ligne.projet ? [ligne.projet.court, ligne.projet.langage, ligne.projet.branche,
                              ligne.projet.disque ? Reglages.t("trouvé sur le disque", "found on disk") : ""].filter(x => x).join("  ·  ") : ""
    }
    MouseArea {
        anchors.fill: parent; hoverEnabled: true
        onEntered: ligne.survol()
        onPositionChanged: ligne.survol()
        onClicked: ligne.ouvrir()
    }
}

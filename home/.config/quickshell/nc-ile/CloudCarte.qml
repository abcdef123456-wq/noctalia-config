import QtQuick

Rectangle {
    default property alias contenuCarte: colonne.data
    property int marge: 18
    property alias spacing: colonne.spacing
    implicitHeight: colonne.implicitHeight + marge * 2
    height: implicitHeight
    radius: Couleurs.rayon(24, width, height)
    color: Qt.alpha(Couleurs.carte, Reglages.sobre ? 1 : 0.86)
    border.width: 1; border.color: Qt.alpha(Couleurs.texte, 0.09)

    Column {
        id: colonne
        anchors.top: parent.top; anchors.left: parent.left; anchors.right: parent.right
        anchors.margins: parent.marge
        spacing: 12
    }
}

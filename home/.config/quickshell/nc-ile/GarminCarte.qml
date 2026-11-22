// Une carte d'indicateur de Garmin.qml : titre, grande valeur, ligne du bas, jauge OU courbe facultatives, et des boutons en plus
import QtQuick

Rectangle {
    id: c
    property string titre: ""
    property string valeur: ""
    property string sous: ""
    property color couleur: Couleurs.accent
    property real jauge: -1                       // 0..1 ; négatif = pas de jauge
    property var courbe: []                       // liste de nombres ; vide = pas de courbe
    default property alias extra: reste.data
    radius: Couleurs.rayon(22, width, height)
    color: Qt.alpha(Couleurs.carte, 0.7)
    implicitHeight: col.implicitHeight + 28

    Row {
        id: ligne
        x: 16; y: 14; width: parent.width - 32; spacing: 12
        GarminJauge {
            visible: c.jauge >= 0
            valeur: c.jauge; couleur: c.couleur; texte: c.valeur
            width: visible ? 84 : 0
        }
        Column {
            id: col
            width: parent.width - (c.jauge >= 0 ? 96 : 0)
            spacing: 4
            Texte { width: parent.width; text: c.titre; secondaire: true }
            Texte {
                visible: c.jauge < 0
                width: parent.width; text: c.valeur
                font.pixelSize: 26; font.weight: Font.DemiBold
            }
            GarminCourbe { visible: c.courbe.length > 1; points: c.courbe; couleur: c.couleur; width: parent.width; height: 34 }
            Texte { visible: c.sous !== ""; width: parent.width; text: c.sous; secondaire: true; font.pixelSize: 12 }
            Row { id: reste; spacing: 8 }
        }
    }
}

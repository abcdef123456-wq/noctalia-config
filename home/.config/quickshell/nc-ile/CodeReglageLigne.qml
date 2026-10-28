// Une ligne de la page « Réglages du code » (CodeReglages.qml) : le nom et l'aide à gauche, le contrôle (pastilles, champ…)
// à droite, dans `contenu`. `choisie` = la ligne du clavier (Haut / Bas).
import QtQuick

Item {
    id: ligne
    property string titre: ""
    property string aide: ""
    property bool choisie: false
    signal survol()
    default property alias contenu: zone.data
    width: 400; height: Math.max(56, zone.childrenRect.height + 18)
    Rectangle {
        anchors.fill: parent; radius: 12
        color: ligne.choisie ? Qt.alpha(Couleurs.accent, 0.14) : "transparent"
        Behavior on color { enabled: !Reglages.sobre; ColorAnimation { duration: 120 } }
    }
    MouseArea { anchors.fill: parent; hoverEnabled: true; onEntered: ligne.survol(); acceptedButtons: Qt.NoButton }
    Column {
        x: 14; y: 9; width: Math.round(parent.width * 0.36); spacing: 2
        Texte { width: parent.width; text: ligne.titre; font.pixelSize: 13; font.weight: Font.DemiBold }
        Texte { width: parent.width; text: ligne.aide; secondaire: true; font.pixelSize: 11; wrapMode: Text.Wrap; maximumLineCount: 2 }
    }
    Item {
        id: zone
        x: Math.round(parent.width * 0.40); y: 9; width: parent.width - x - 14; height: childrenRect.height
    }
}

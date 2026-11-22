// Chiffres « aiguille » : un cadran rond, 12 graduations, l'aiguille des heures et celle des minutes. Rien que des
// Rectangle tournés autour du centre (rotation, pied de l'aiguille au centre) : ni toile ni tracé vectoriel. Pas de trotteuse :
// l'heure suit Etat.minute, rien ne bouge entre deux minutes. Chargé par CarteWidget.qml d'après le champ « chiffres ».
import QtQuick

Item {
    id: cadran
    required property var carte
    readonly property real cote: Math.round(carte.tailleHeure * 0.72 * 1.4)
    readonly property real r: cote / 2
    readonly property int heures: carte.d.getHours() % 12
    readonly property int minutes: carte.d.getMinutes()
    implicitWidth: cote
    implicitHeight: cote

    Rectangle {
        anchors.fill: parent
        radius: width / 2
        color: "transparent"
        border.width: Math.max(1, Math.round(cadran.cote / 90))
        border.color: cadran.carte.sec
    }
    Repeater {
        model: 12
        Item {
            required property int index
            x: cadran.r - width / 2
            width: Math.max(2, Math.round(cadran.cote / (index % 3 === 0 ? 50 : 80))); height: cadran.r
            transformOrigin: Item.Bottom
            rotation: index * 30
            Rectangle {
                y: Math.round(cadran.cote * 0.05)
                width: parent.width; height: Math.round(cadran.cote * (parent.index % 3 === 0 ? 0.09 : 0.05))
                radius: width / 2
                color: parent.index % 3 === 0 ? cadran.carte.pri : cadran.carte.sec
            }
        }
    }
    // Aiguilles : rotation en degrés depuis midi, dans le sens des aiguilles d'une montre (3 h : 90°, vers la droite)
    Rectangle {
        objectName: "nc-aiguille-heures"
        width: Math.max(3, Math.round(cadran.cote / 28)); height: Math.round(cadran.r * 0.55)
        x: cadran.r - width / 2; y: cadran.r - height
        radius: width / 2
        transformOrigin: Item.Bottom
        rotation: (cadran.heures + cadran.minutes / 60) * 30
        color: cadran.carte.pri
    }
    Rectangle {
        objectName: "nc-aiguille-minutes"
        width: Math.max(2, Math.round(cadran.cote / 45)); height: Math.round(cadran.r * 0.8)
        x: cadran.r - width / 2; y: cadran.r - height
        radius: width / 2
        transformOrigin: Item.Bottom
        rotation: cadran.minutes * 6
        color: cadran.carte.pri
    }
    Rectangle {
        width: Math.max(6, Math.round(cadran.cote / 14)); height: width; radius: width / 2
        x: cadran.r - width / 2; y: cadran.r - height / 2
        color: cadran.carte.accent
    }
}

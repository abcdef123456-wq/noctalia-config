// Jauge à aiguille (widget « jauge-aiguille », CarteWidget.qml) : un demi-cercle gradué, une aiguille tournée selon la
// valeur (0 : à gauche, 1 : à droite), le pourcentage et le libellé dessous. Rien que des Rectangle (le demi-cercle : un
// cercle à bord, coupé à mi-hauteur) : ni toile ni tracé vectoriel. Aucun minuteur ici : la valeur vient de l'échantillonnage
// partagé de WidgetsTheme.qml.
import QtQuick

Item {
    id: jauge
    property real valeur: 0
    property string libelle: ""
    property real diametre: 200
    property color couleur: Couleurs.texte       // couleurs lisibles sur le fond du widget (CarteWidget : pri, sec)
    property color couleurSec: Couleurs.texteSec
    property string police: Couleurs.police          // le pourcentage ; policePetite : le libellé
    property string policePetite: Couleurs.police
    property int taillePetite: 11
    readonly property real v: Math.max(0, Math.min(1, valeur))
    readonly property real r: diametre / 2
    implicitWidth: diametre
    implicitHeight: r + Math.round(diametre / 16) + textes.implicitHeight

    Item {
        width: jauge.diametre; height: jauge.r
        clip: true
        Rectangle {
            width: jauge.diametre; height: width; radius: width / 2
            color: "transparent"
            border.width: Math.max(2, Math.round(jauge.diametre / 60))
            border.color: Couleurs.gris3
        }
    }
    // 11 graduations, allumées jusqu'à la valeur ; chacune tourne autour du centre (son pied)
    Repeater {
        model: 11
        Item {
            required property int index
            x: jauge.r - width / 2
            width: Math.max(2, Math.round(jauge.diametre / 70)); height: jauge.r
            transformOrigin: Item.Bottom
            rotation: -90 + index * 18
            Rectangle {
                y: Math.round(jauge.diametre / 30)
                width: parent.width; height: Math.round(jauge.diametre / (parent.index % 5 === 0 ? 9 : 14))
                radius: width / 2
                color: parent.index / 10 <= jauge.v + 0.001 ? Couleurs.jauge : Couleurs.gris3
            }
        }
    }
    Rectangle {
        visible: Number.isFinite(jauge.v)
        objectName: "nc-jauge-aiguille"
        width: Math.max(3, Math.round(jauge.diametre / 45)); height: Math.round(jauge.r * 0.78)
        x: jauge.r - width / 2; y: jauge.r - height
        radius: width / 2
        transformOrigin: Item.Bottom
        rotation: visible ? -90 + 180 * jauge.v : 0
        color: jauge.couleur
    }
    Rectangle {
        width: Math.round(jauge.diametre / 12); height: width; radius: width / 2
        x: jauge.r - width / 2; y: jauge.r - height / 2
        color: jauge.couleur
    }
    Column {
        id: textes
        anchors.horizontalCenter: parent.horizontalCenter
        y: jauge.r + Math.round(jauge.diametre / 16)
        Texte {
            anchors.horizontalCenter: parent.horizontalCenter
            text: Number.isFinite(jauge.v) ? Math.round(jauge.v * 100) + "%" : "—"
            color: jauge.couleur
            font.family: jauge.police
            font.pixelSize: Math.round(jauge.diametre * 0.2)
            font.weight: Font.Bold
        }
        Texte {
            anchors.horizontalCenter: parent.horizontalCenter
            text: jauge.libelle
            color: jauge.couleurSec
            font.family: jauge.policePetite
            font.pixelSize: jauge.taillePetite
            font.capitalization: Font.AllUppercase
            font.letterSpacing: Math.round(jauge.diametre / 60)
        }
    }
}

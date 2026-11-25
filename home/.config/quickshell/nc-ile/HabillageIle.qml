import QtQuick
import QtQuick.Shapes

// Un seul jeu de tracés, celui du thème actif. Pas de texture ni de boucle de dessin au repos.
Item {
    id: habillage
    required property var plan
    required property bool page
    required property bool dessinerFond
    required property color fond
    required property real contour
    required property bool lueur
    readonly property string silhouette: dessinerFond ? (page ? plan.page(width, height) : plan.repos(width, height)) : ""
    readonly property var cartouche: page ? plan.carte(width) : null
    readonly property bool pointille: plan.dessin === "afficheur"
    objectName: "nc-ile-habillage-" + plan.dessin

    Shape {
        anchors.fill: parent
        ShapePath {
            fillColor: "transparent"
            strokeColor: Qt.alpha(Couleurs.accent, 0.18)
            strokeWidth: habillage.lueur && habillage.dessinerFond ? 8 : -1
            joinStyle: ShapePath.RoundJoin
            PathSvg { path: habillage.silhouette }
        }
        ShapePath {
            fillColor: habillage.dessinerFond ? habillage.fond : "transparent"
            strokeColor: Couleurs.contour === "discret" ? Qt.alpha(Couleurs.accent, 0.45) : Couleurs.degrade[1]
            strokeWidth: habillage.contour > 0 && habillage.dessinerFond ? habillage.contour : -1
            joinStyle: ShapePath.RoundJoin
            PathSvg { path: habillage.silhouette }
        }
        ShapePath {
            fillRule: ShapePath.OddEvenFill
            fillColor: Qt.alpha(Couleurs.accent, Couleurs.sombre ? 0.29 : 0.22)
            strokeWidth: -1
            PathSvg { path: habillage.cartouche ? habillage.cartouche.aplat : "" }
        }
        ShapePath {
            fillColor: habillage.pointille ? Qt.alpha(Couleurs.accent, 0.80) : "transparent"
            strokeColor: Qt.alpha(Couleurs.accent, 0.58)
            strokeWidth: habillage.pointille ? -1 : 1.5
            capStyle: ShapePath.RoundCap
            joinStyle: ShapePath.RoundJoin
            PathSvg { path: habillage.cartouche ? habillage.cartouche.traits : "" }
        }
    }

    Texte {
        visible: habillage.page
        x: habillage.width * (habillage.plan.titre === "gauche" ? 0.23 : habillage.plan.titre === "droite" ? 0.75 : 0.5) - width / 2
        y: 19 - height / 2
        width: Math.min(implicitWidth, habillage.width * 0.39)
        text: Couleurs.nomThemeAffiche
        font.pixelSize: habillage.pointille ? 11 : 10
        font.weight: Font.Bold
        font.letterSpacing: habillage.pointille ? 2.4 : 1.6
        font.capitalization: Font.AllUppercase
        horizontalAlignment: Text.AlignHCenter
    }
}

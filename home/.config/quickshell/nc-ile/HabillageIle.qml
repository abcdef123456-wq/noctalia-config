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
    property color pigment: Couleurs.accent
    property color encre: Couleurs.texte
    readonly property bool estNocturne: plan.dessin === "nocturne"
    readonly property string silhouette: dessinerFond ? (page ? plan.page(width, height) : plan.repos(width, height)) : ""
    readonly property var cartouche: page ? plan.carte(width) : null
    readonly property bool pointille: plan.dessin === "afficheur"
    readonly property real epaisseur: dessinerFond ? Math.max(0, contour) : 0
    readonly property color discret: Qt.alpha(Couleurs.accent, 0.45)
    readonly property bool degrade: Couleurs.contour !== "discret"
    objectName: "nc-ile-habillage-" + plan.dessin

    // Les sous-tracés évidés laissent le fond transparent, même avec ILE_VERRE.
    Shape {
        id: filet
        anchors.fill: parent
        visible: habillage.estNocturne && habillage.dessinerFond
        preferredRendererType: Shape.CurveRenderer
        readonly property real bord: habillage.epaisseur
        readonly property string exterieur: visible && bord > 0 ? habillage.plan.continu(width, height, bord) : habillage.silhouette
        ShapePath {
            fillRule: ShapePath.OddEvenFill
            fillColor: Qt.alpha(Couleurs.accent, 0.09)
            strokeWidth: -1
            PathSvg {
                path: filet.visible && habillage.lueur
                    ? habillage.plan.continu(habillage.width, habillage.height, Math.max(4, filet.bord + 1)) + " " + filet.exterieur
                    : ""
            }
        }
        ShapePath {
            fillRule: ShapePath.OddEvenFill
            strokeWidth: -1
            fillGradient: LinearGradient {
                x1: 0; y1: 0
                x2: habillage.width; y2: 0
                GradientStop { position: 0.0; color: habillage.degrade ? Couleurs.degrade[0] : habillage.discret }
                GradientStop { position: 0.5; color: habillage.degrade ? Couleurs.degrade[1] : habillage.discret }
                GradientStop { position: 1.0; color: habillage.degrade ? Qt.tint(Couleurs.degrade[2], Qt.alpha(Couleurs.rose, 0.30)) : habillage.discret }
            }
            PathSvg { path: filet.visible && filet.bord > 0 ? filet.exterieur + " " + habillage.silhouette : "" }
        }
    }

    Shape {
        anchors.fill: parent
        preferredRendererType: habillage.estNocturne ? Shape.CurveRenderer : Shape.UnknownRenderer
        ShapePath {
            fillColor: "transparent"
            strokeColor: Qt.alpha(Couleurs.accent, 0.18)
            strokeWidth: !habillage.estNocturne && habillage.lueur && habillage.dessinerFond ? 8 : -1
            joinStyle: ShapePath.RoundJoin
            PathSvg { path: habillage.estNocturne ? "" : habillage.silhouette }
        }
        ShapePath {
            fillColor: habillage.dessinerFond ? habillage.fond : "transparent"
            strokeColor: habillage.estNocturne ? Qt.alpha(Couleurs.voile, 0.10)
                : (habillage.degrade ? Couleurs.degrade[1] : habillage.discret)
            strokeWidth: habillage.estNocturne ? (habillage.dessinerFond ? 1 : -1) : (habillage.epaisseur > 0 ? habillage.epaisseur : -1)
            joinStyle: ShapePath.RoundJoin
            PathSvg { path: habillage.silhouette }
        }
        ShapePath {
            fillRule: ShapePath.OddEvenFill
            fillColor: Qt.alpha(habillage.pigment, habillage.estNocturne ? 0.16 : (Couleurs.sombre ? 0.29 : 0.22))
            strokeColor: habillage.estNocturne ? Qt.alpha(habillage.pigment, 0.36) : "transparent"
            strokeWidth: habillage.estNocturne ? 1 : -1
            joinStyle: ShapePath.RoundJoin
            PathSvg { path: habillage.cartouche ? habillage.cartouche.aplat : "" }
        }
        ShapePath {
            fillColor: habillage.pointille ? Qt.alpha(habillage.pigment, 0.80) : "transparent"
            strokeColor: Qt.alpha(habillage.pigment, habillage.estNocturne ? 0.45 : 0.58)
            strokeWidth: habillage.pointille ? -1 : (habillage.estNocturne ? 1.2 : 1.5)
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
        color: habillage.encre
        font.pixelSize: habillage.pointille ? 11 : 10
        font.weight: Font.Bold
        font.letterSpacing: habillage.pointille ? 2.4 : 1.6
        font.capitalization: Font.AllUppercase
        horizontalAlignment: Text.AlignHCenter
    }
}

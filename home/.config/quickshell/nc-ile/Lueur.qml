// Une lueur du fond animé (Lueurs.qml) : un dégradé radial d'une couleur du thème qui couvre tout l'écran, centre et
// rayon en proportion de l'écran. La force module sa transparence (nuit, ciel couvert : plus discrète).
import QtQuick
import QtQuick.Shapes

ShapePath {
    id: l
    property color teinte: "white"
    property real cx: 0.5
    property real cy: 0.5
    property real r: 0.5
    property real force: 1
    property real largeur: 0
    property real hauteur: 0
    strokeWidth: -1
    fillGradient: RadialGradient {
        centerX: l.cx * l.largeur; centerY: l.cy * l.hauteur; centerRadius: l.r * Math.max(l.largeur, l.hauteur)
        focalX: centerX; focalY: centerY
        GradientStop { position: 0; color: Qt.alpha(l.teinte, 0.42 * l.force) }
        GradientStop { position: 0.55; color: Qt.alpha(l.teinte, 0.14 * l.force) }
        GradientStop { position: 1; color: "transparent" }
    }
    startX: 0; startY: 0
    PathLine { x: l.largeur; y: 0 }
    PathLine { x: l.largeur; y: l.hauteur }
    PathLine { x: 0; y: l.hauteur }
    PathLine { x: 0; y: 0 }
}

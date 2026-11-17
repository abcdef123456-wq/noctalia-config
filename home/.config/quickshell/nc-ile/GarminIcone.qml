// Icône maison de Garmin.qml : un cœur avec une pulsation (aucun logo de marque)
import QtQuick

Canvas {
    id: ic
    property color color: Couleurs.rose
    property real taille: 22
    width: taille; height: taille
    onColorChanged: requestPaint()
    onPaint: {
        var c = getContext("2d"); c.reset()
        var s = width
        c.lineWidth = Math.max(1.6, s * 0.09); c.lineCap = "round"; c.lineJoin = "round"; c.strokeStyle = ic.color
        c.beginPath()
        c.moveTo(s * 0.5, s * 0.88)
        c.bezierCurveTo(s * 0.05, s * 0.55, s * 0.08, s * 0.14, s * 0.3, s * 0.14)
        c.bezierCurveTo(s * 0.42, s * 0.14, s * 0.5, s * 0.24, s * 0.5, s * 0.3)
        c.bezierCurveTo(s * 0.5, s * 0.24, s * 0.58, s * 0.14, s * 0.7, s * 0.14)
        c.bezierCurveTo(s * 0.92, s * 0.14, s * 0.95, s * 0.55, s * 0.5, s * 0.88)
        c.stroke()
        c.beginPath()
        c.moveTo(s * 0.22, s * 0.5); c.lineTo(s * 0.4, s * 0.5); c.lineTo(s * 0.47, s * 0.36)
        c.lineTo(s * 0.55, s * 0.62); c.lineTo(s * 0.61, s * 0.5); c.lineTo(s * 0.78, s * 0.5)
        c.stroke()
    }
}

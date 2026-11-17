// Courbe lissée de Garmin.qml : `points` est une liste de nombres (au moins deux), tracée du plus bas au plus haut de la plage
import QtQuick

Canvas {
    id: cb
    property var points: []
    property color couleur: Couleurs.rose
    width: 120; height: 34
    onPointsChanged: requestPaint()
    onCouleurChanged: requestPaint()
    onPaint: {
        var c = getContext("2d"); c.reset()
        var p = cb.points
        if (!p || p.length < 2) return
        var mn = Math.min.apply(null, p), mx = Math.max.apply(null, p)
        var d = mx - mn > 0 ? mx - mn : 1
        c.lineWidth = 2.5; c.lineCap = "round"; c.lineJoin = "round"; c.strokeStyle = cb.couleur
        c.beginPath()
        var py = 0
        for (var i = 0; i < p.length; i++) {
            var x = 3 + (width - 6) * i / (p.length - 1)
            var y = height - 3 - (height - 6) * (p[i] - mn) / d
            if (i === 0) c.moveTo(x, y)
            else { var px = 3 + (width - 6) * (i - 1) / (p.length - 1); c.bezierCurveTo((px + x) / 2, py, (px + x) / 2, y, x, y) }
            py = y
        }
        c.stroke()
    }
}

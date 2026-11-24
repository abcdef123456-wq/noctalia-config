// Courbe lissée de Garmin.qml : `points` est une liste de nombres (au moins deux), tracée du plus bas au plus haut de la plage
import QtQuick

Canvas {
    id: cb
    property var points: []
    property color couleur: Couleurs.rose
    property real echelle: 0
    width: 120; height: 34
    property int peintures: 0                     // compté pour les tests : rien n'est peint tant que la courbe est cachée
    property int demandes: 0                      // demandes de peinture : comptées pour les tests, aucune tant que la courbe est cachée
    function demander() { demandes++; requestPaint() }
    onPointsChanged: if (visible) demander()
    onCouleurChanged: if (visible) demander()
    onEchelleChanged: if (visible) demander()
    onWidthChanged: if (visible) demander()
    onHeightChanged: if (visible) demander()
    onVisibleChanged: if (visible) demander()
    onPaint: {
        peintures++
        var c = getContext("2d"); c.reset()
        var p = cb.points
        if (!p || p.length < 2 || width <= 10 || height <= 12) return
        var mn = echelle > 0 ? 0 : Math.min.apply(null, p)
        var mx = echelle > 0 ? echelle : Math.max.apply(null, p)
        var d = mx - mn || 1
        var pas = (width - 10) / (p.length - 1)
        c.lineWidth = 2.5; c.lineCap = "round"; c.lineJoin = "round"; c.strokeStyle = cb.couleur
        c.beginPath()
        var px = 5, py = 0
        for (var i = 0; i < p.length; i++) {
            var x = 5 + pas * i
            var y = height - 6 - (height - 12) * Math.max(0, Math.min(1, (p[i] - mn) / d))
            if (i === 0) c.moveTo(x, y)
            else c.bezierCurveTo((px + x) / 2, py, (px + x) / 2, y, x, y)
            px = x; py = y
        }
        c.stroke()
        c.lineTo(px, height); c.lineTo(5, height); c.closePath()
        var gradient = c.createLinearGradient(0, 0, 0, height)
        gradient.addColorStop(0, Qt.alpha(cb.couleur, 0.35))
        gradient.addColorStop(1, Qt.alpha(cb.couleur, 0))
        c.fillStyle = gradient; c.fill()
        c.fillStyle = cb.couleur; c.beginPath(); c.arc(px, py, 4, 0, 2 * Math.PI); c.fill()
    }
}

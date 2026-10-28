// Mini-courbe de la page Santé : les dernières mesures (tableau en mémoire, tenu par Sante.qml) en trait lisse et
// arrondi, avec un léger dégradé dessous. Le Canvas n'est redessiné que quand le tableau, la couleur ou la taille
// changent (donc seulement quand la page reçoit un relevé) ; aucune animation continue, rien écrit sur le disque.
import QtQuick

Item {
    id: c
    property var valeurs: []               // mesures les plus anciennes d'abord
    property color teinte: Couleurs.vert
    property real mini: 0                  // échelle verticale fixe (charge : 0 à 100)
    property real maxi: 100
    property bool echelleAuto: false       // température : l'échelle suit les mesures (écart d'au moins 20 °C)
    readonly property int nombre: valeurs.length
    height: 44

    Canvas {
        id: toile
        anchors.fill: parent
        readonly property color t: c.teinte
        onTChanged: requestPaint()
        onWidthChanged: requestPaint()
        onHeightChanged: requestPaint()
        Connections { target: c; function onValeursChanged() { toile.requestPaint() } }
        onPaint: {
            var g = getContext("2d"); g.reset()
            var v = c.valeurs, n = v.length
            if (n < 2 || width < 4 || height < 4) return
            var lo = c.mini, hi = c.maxi
            if (c.echelleAuto) {
                lo = Math.min.apply(null, v); hi = Math.max.apply(null, v)
                if (hi - lo < 20) { var mid = (hi + lo) / 2; lo = mid - 10; hi = mid + 10 }
            }
            var m = 3, w = width - 2 * m, h = height - 2 * m
            var px = i => m + w * i / (n - 1)
            var py = x => m + h * (1 - (Math.max(lo, Math.min(hi, x)) - lo) / (hi - lo))
            // Courbe lisse : quadratiques entre les milieux des points
            g.beginPath(); g.moveTo(px(0), py(v[0]))
            for (var i = 1; i < n - 1; i++) g.quadraticCurveTo(px(i), py(v[i]), (px(i) + px(i + 1)) / 2, (py(v[i]) + py(v[i + 1])) / 2)
            g.lineTo(px(n - 1), py(v[n - 1]))
            g.lineWidth = 2; g.lineCap = "round"; g.lineJoin = "round"; g.strokeStyle = String(t); g.stroke()
            g.lineTo(px(n - 1), height - m); g.lineTo(px(0), height - m); g.closePath()
            var d = g.createLinearGradient(0, 0, 0, height)
            d.addColorStop(0, Qt.rgba(t.r, t.g, t.b, 0.28)); d.addColorStop(1, Qt.rgba(t.r, t.g, t.b, 0))
            g.fillStyle = d; g.fill()
        }
    }
}

// L'étincelle de Claude (huit rayons arrondis, orange de Claude) ; tourne doucement pendant qu'il travaille
import QtQuick

Canvas {
    id: e
    property real taille: 18
    property bool tourne: false
    property color couleur: Agents.couleur
    width: taille; height: taille
    onCouleurChanged: requestPaint()
    onPaint: {
        var c = getContext("2d"); c.reset()
        var r = width / 2
        c.translate(r, r)
        c.strokeStyle = String(couleur); c.lineCap = "round"; c.lineWidth = Math.max(1.6, width * 0.13)
        for (var i = 0; i < 8; i++) {
            var a = i * Math.PI / 4, l = i % 2 ? r * 0.62 : r * 0.92     // rayons alternés, comme le logo
            c.beginPath(); c.moveTo(Math.cos(a) * r * 0.18, Math.sin(a) * r * 0.18); c.lineTo(Math.cos(a) * l, Math.sin(a) * l); c.stroke()
        }
    }
    RotationAnimation on rotation { running: e.tourne && e.visible; from: 0; to: 360; duration: 2600; loops: Animation.Infinite }
    Behavior on rotation { enabled: !e.tourne; NumberAnimation { duration: 300 } }
    onTourneChanged: if (!tourne) rotation = 0
}

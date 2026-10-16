// Logo de l'agent : l'étincelle de Claude (huit rayons arrondis, orange de Claude), qui tourne doucement pendant qu'il
// travaille ; ou l'arche d'Antigravity (dégradé bleu, violet, corail), qui flotte doucement pendant qu'il travaille.
import QtQuick

Canvas {
    id: e
    property real taille: 18
    property bool tourne: false
    property string agent: "claude"                       // claude, antigravity
    readonly property bool arche: agent === "antigravity"
    property color couleur: arche ? Agents.couleurAgy : Agents.couleur
    width: taille; height: taille
    onCouleurChanged: requestPaint()
    onAgentChanged: { rotation = 0; requestPaint() }      // l'arche ne garde pas l'angle de l'étincelle
    onPaint: {
        var c = getContext("2d"); c.reset()
        var r = width / 2
        c.lineCap = "round"
        if (arche) {
            var g = c.createLinearGradient(0, 0, width, 0)
            g.addColorStop(0, String(couleur)); g.addColorStop(0.5, "#a374f0"); g.addColorStop(1, "#f0736d")
            c.strokeStyle = g; c.lineWidth = Math.max(2, width * 0.2)
            c.beginPath(); c.moveTo(width * 0.14, height * 0.86)
            c.bezierCurveTo(width * 0.2, height * 0.1, width * 0.8, height * 0.1, width * 0.86, height * 0.86)
            c.stroke()
            return
        }
        c.translate(r, r)
        c.strokeStyle = String(couleur); c.lineWidth = Math.max(1.6, width * 0.13)
        for (var i = 0; i < 8; i++) {
            var a = i * Math.PI / 4, l = i % 2 ? r * 0.62 : r * 0.92     // rayons alternés, comme le logo
            c.beginPath(); c.moveTo(Math.cos(a) * r * 0.18, Math.sin(a) * r * 0.18); c.lineTo(Math.cos(a) * l, Math.sin(a) * l); c.stroke()
        }
    }
    RotationAnimation on rotation { running: e.tourne && e.visible && !e.arche; from: 0; to: 360; duration: 2600; loops: Animation.Infinite }
    Behavior on rotation { enabled: !e.tourne; NumberAnimation { duration: 300 } }
    onTourneChanged: if (!tourne) { rotation = 0; flotte = 0 }

    // Antigravity : flotte (monte et redescend) pendant le travail
    property real flotte: 0
    transform: Translate { y: -e.flotte * e.taille * 0.16 }
    SequentialAnimation on flotte {
        running: e.tourne && e.visible && e.arche; loops: Animation.Infinite
        NumberAnimation { to: 1; duration: 900; easing.type: Easing.InOutSine }
        NumberAnimation { to: 0; duration: 900; easing.type: Easing.InOutSine }
    }
}

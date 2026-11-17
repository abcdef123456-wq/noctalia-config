// Jauge en arc (270°) de Garmin.qml : valeur de 0 à 1
import QtQuick

Item {
    id: j
    property real valeur: 0
    property color couleur: Couleurs.accent
    property string texte: ""
    width: 84; height: 84
    property int peintures: 0
    property int demandes: 0
    function demander() { demandes++; arc.requestPaint() }
    onValeurChanged: if (visible) demander()
    onCouleurChanged: if (visible) demander()
    onVisibleChanged: if (visible) demander()
    Canvas {
        id: arc
        anchors.fill: parent
        onPaint: {
            j.peintures++
            var c = getContext("2d"); c.reset()
            var r = width / 2 - 7, cx = width / 2, cy = height / 2
            var a0 = Math.PI * 0.75, tout = Math.PI * 1.5
            c.lineWidth = 8; c.lineCap = "round"
            c.strokeStyle = Qt.alpha(Couleurs.texte, 0.12)
            c.beginPath(); c.arc(cx, cy, r, a0, a0 + tout); c.stroke()
            var v = Math.max(0, Math.min(1, j.valeur))
            if (v > 0) {
                c.strokeStyle = j.couleur
                c.beginPath(); c.arc(cx, cy, r, a0, a0 + tout * v); c.stroke()
            }
        }
    }
    Texte { anchors.centerIn: parent; text: j.texte; font.pixelSize: 17; font.weight: Font.DemiBold }
}

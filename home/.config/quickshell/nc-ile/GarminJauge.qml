// Jauge en arc (270°) de Garmin.qml : valeur de 0 à 1
import QtQuick

Item {
    id: j
    property real valeur: 0
    property color couleur: Couleurs.accent
    property string texte: ""
    property string sousTexte: ""
    property string objetSousTexte: ""
    readonly property color couleurPiste: Qt.alpha(Couleurs.texte, 0.12)
    width: 84; height: 84
    property int peintures: 0
    property int demandes: 0
    function demander() { demandes++; arc.requestPaint() }
    onValeurChanged: if (visible) demander()
    onCouleurChanged: if (visible) demander()
    onCouleurPisteChanged: if (visible) demander()
    onWidthChanged: if (visible) demander()
    onVisibleChanged: if (visible) demander()
    Canvas {
        id: arc
        anchors.fill: parent
        onPaint: {
            j.peintures++
            var c = getContext("2d"); c.reset()
            if (width <= 14) return
            var r = width / 2 - 7, cx = width / 2, cy = height / 2
            var a0 = Math.PI * 0.75, tout = Math.PI * 1.5
            c.lineWidth = width < 70 ? 6 : 8; c.lineCap = "round"
            c.strokeStyle = j.couleurPiste
            c.beginPath(); c.arc(cx, cy, r, a0, a0 + tout); c.stroke()
            var v = Math.max(0, Math.min(1, j.valeur))
            if (v > 0) {
                c.strokeStyle = j.couleur
                c.beginPath(); c.arc(cx, cy, r, a0, a0 + tout * v); c.stroke()
            }
        }
    }
    Column {
        anchors.centerIn: parent
        width: Math.max(0, parent.width - 16)
        Texte {
            width: parent.width; horizontalAlignment: Text.AlignHCenter
            text: j.texte; color: text === "—" ? Couleurs.texteSec : j.couleur
            font.pixelSize: j.width < 74 || text.length > 5 ? 13 : 16
            font.weight: Font.Bold; font.features: { "tnum": 1 }
        }
        Texte {
            objectName: j.objetSousTexte
            visible: j.sousTexte !== ""; width: parent.width; horizontalAlignment: Text.AlignHCenter
            text: j.sousTexte; font.pixelSize: 9; secondaire: true
        }
    }
}

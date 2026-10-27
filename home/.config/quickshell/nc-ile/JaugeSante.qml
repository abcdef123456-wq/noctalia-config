// Jauge en arc de la page Santé : grande valeur au centre d'un arc arrondi (trois quarts de cercle) qui se remplit en
// douceur et prend la couleur de l'état (vert, orange, rouge) ; titre et petite icône dessous. Le Canvas n'est redessiné
// que lorsque la valeur ou la couleur change (rien en continu) ; pas d'animation en Économie ni sans effets (Reglages.sobre).
import QtQuick

Rectangle {
    id: j
    property string titre: ""
    property string valeur: "–"
    property string icone: ""
    property real taux: 0                  // 0 à 1 : remplissage de l'arc
    property color teinte: Couleurs.vert
    property bool sans: false              // pas de mesure (carte graphique endormie) : arc vide, valeur grisée
    width: 118; height: 118; radius: 20; color: Couleurs.carte

    readonly property real plein: sans ? 0 : Math.max(0, Math.min(1, taux))
    property real anime: plein
    Behavior on anime { enabled: !Reglages.sobre; NumberAnimation { duration: 650; easing.type: Easing.OutCubic } }
    property color couleur: sans ? Couleurs.gris4 : teinte
    Behavior on couleur { enabled: !Reglages.sobre; ColorAnimation { duration: 300 } }

    Canvas {
        id: arc
        anchors.horizontalCenter: parent.horizontalCenter; y: 8
        width: 74; height: 74
        readonly property real f: j.anime
        readonly property color t: j.couleur
        readonly property color fondArc: Couleurs.gris3
        onFChanged: requestPaint()
        onTChanged: requestPaint()
        onFondArcChanged: requestPaint()
        onPaint: {
            var c = getContext("2d"); c.reset()
            c.lineWidth = 7; c.lineCap = "round"
            var a0 = Math.PI * 0.75, a1 = Math.PI * 2.25
            c.strokeStyle = String(fondArc); c.beginPath(); c.arc(37, 37, 31, a0, a1); c.stroke()
            if (f > 0.004) { c.strokeStyle = String(t); c.beginPath(); c.arc(37, 37, 31, a0, a0 + (a1 - a0) * f); c.stroke() }
        }
        Texte {
            anchors.centerIn: parent; anchors.verticalCenterOffset: 2
            text: j.valeur; font.pixelSize: j.valeur.length > 5 ? 13 : 17; font.weight: Font.DemiBold; font.features: { "tnum": 1 }
            color: j.sans ? Couleurs.texteSec : j.teinte
            width: 58; horizontalAlignment: Text.AlignHCenter
        }
    }
    Row {
        anchors.horizontalCenter: parent.horizontalCenter; anchors.bottom: parent.bottom; anchors.bottomMargin: 10; spacing: 5
        Ico { nom: j.icone; taille: 14; color: Couleurs.texteSec; anchors.verticalCenter: parent.verticalCenter }
        Texte { text: j.titre; secondaire: true; font.pixelSize: 12; anchors.verticalCenter: parent.verticalCenter; width: Math.min(implicitWidth, j.width - 40) }
    }
}

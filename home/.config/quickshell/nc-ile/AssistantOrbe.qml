// Emblème de pfp.mp4 sur noir ; couleurs liées à la palette du terminal (Couleurs).
import QtQuick

Item {
    id: orbe
    property bool anime: false
    property bool occupe: false
    property bool erreur: false
    property bool ecoute: false
    signal clic()
    property color accent: (erreur || ecoute) ? Couleurs.rouge : Couleurs.accent
    readonly property bool mouvement: anime && visible && !Reglages.sobre
    objectName: "nc-jarvis-visual"
    Rectangle { anchors.fill: parent; radius: width / 2; color: "transparent"; border.width: 8; border.color: Qt.alpha(orbe.accent, 0.12) }
    Rectangle { anchors.fill: parent; anchors.margins: 4; radius: width / 2; color: "transparent"; border.width: 2.5; border.color: Qt.alpha(orbe.accent, 0.88) }
    Rectangle { anchors.fill: parent; anchors.margins: 8; radius: width / 2; color: "transparent"; border.width: 1.5; border.color: Qt.alpha(orbe.accent, 0.35) }
    Rectangle {
        anchors.fill: parent; anchors.margins: 12; radius: width / 2
        color: orbe.ecoute ? Qt.tint(Couleurs.fond, Qt.alpha(Couleurs.rouge, 0.38)) : Couleurs.fond
        border.width: 1.5; border.color: Qt.alpha(orbe.accent, 0.78)
        Behavior on color { ColorAnimation { duration: 180 } }
        LogoAssistant {
            objectName: "nc-jarvis-hero"; grand: true
            anchors.centerIn: parent; width: parent.width * 0.68; height: width
            anime: orbe.mouvement
        }
        Text {
            visible: orbe.ecoute
            anchors.horizontalCenter: parent.horizontalCenter
            y: parent.height * 0.62
            text: Reglages.t("En écoute...", "Listening...")
            font.family: "Adwaita Sans"; font.pixelSize: 15; font.weight: Font.Bold
            color: Couleurs.texte
        }
    }
    // Tracés peints seulement au redimensionnement/changement d'état ; rotation par la scène QtQuick.
    Canvas {
        id: anneau
        anchors.fill: parent
        onWidthChanged: requestPaint()
        onHeightChanged: requestPaint()
        Connections { target: orbe; function onAccentChanged() { anneau.requestPaint() } }
        onPaint: {
            var c = getContext("2d"); c.reset()
            var r = Math.max(0, width / 2 - 8)
            c.strokeStyle = String(orbe.accent); c.lineWidth = 2; c.lineCap = "round"
            for (var i = 0; i < 3; i++) {
                var a = i * Math.PI * 2 / 3
                c.beginPath(); c.arc(width / 2, height / 2, r, a, a + 0.75); c.stroke()
            }
        }
        RotationAnimation on rotation { from: 0; to: 360; duration: orbe.occupe ? 4500 : 18000; loops: Animation.Infinite; running: orbe.mouvement }
    }
    Rectangle {
        width: 34; height: 34; radius: 17
        x: parent.width * 0.81 - width / 2; y: parent.height * 0.82 - height / 2
        color: Couleurs.fond; border.width: 2; border.color: Qt.alpha(orbe.accent, 0.45)
        Rectangle { anchors.fill: parent; anchors.margins: 4; radius: width / 2; color: orbe.accent }
        Ico {
            anchors.centerIn: parent; taille: 15
            color: (orbe.erreur || orbe.ecoute) ? Couleurs.surCouleur : Couleurs.surAccent
            nom: orbe.ecoute ? "mic" : (orbe.erreur ? "priority_high" : (orbe.occupe ? "psychology" : "check"))
        }
    }
    MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: orbe.clic() }
}

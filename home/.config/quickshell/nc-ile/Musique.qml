pragma ComponentBehavior: Bound
import QtQuick
import Quickshell.Services.Mpris

Item {
    id: m
    required property var planche
    readonly property color encre: planche?.ink ?? Couleurs.texte
    readonly property color accent: planche?.accent ?? Couleurs.accent

    readonly property var lecteur: Etat.lecteur
    readonly property string source: lecteur ? lecteur.identity : ""
    readonly property string etatLecture: Etat.joue ? Reglages.t("En lecture", "Playing")
        : (lecteur && lecteur.playbackState === MprisPlaybackState.Paused ? Reglages.t("En pause", "Paused")
        : (lecteur ? Reglages.t("À l’arrêt", "Stopped") : Reglages.t("Aucun lecteur", "No player")))
    // MPRIS peut exposer une position sans durée : ne pas la prendre pour une progression à 100 %.
    readonly property bool positionConnue: !!lecteur && lecteur.positionSupported
    readonly property real duree: lecteur && lecteur.lengthSupported ? Math.max(0, lecteur.length) : 0
    readonly property real position: positionConnue ? borner(lecteur.position) : 0
    readonly property bool peutChercher: positionConnue && duree > 0 && lecteur.canSeek

    function borner(s) { return Math.max(0, duree > 0 ? Math.min(duree, s) : s) }
    function chercher(s) { if (peutChercher) lecteur.position = borner(s) }
    function temps(s) {
        s = Math.max(0, Math.floor(s))
        return Math.floor(s / 60) + ":" + String(s % 60).padStart(2, "0")
    }

    // La scène porte la pochette cliquable et le transport ; cette bande complète le lecteur.
    Texte {
        x: 12; y: 4; width: Math.max(0, parent.width - 64)
        text: m.planche ? (m.source || m.etatLecture) : Reglages.t("Progression", "Progress")
        color: m.planche ? m.encre : Couleurs.texteDoux; font.pixelSize: 11
        font.family: m.planche?.font ?? Couleurs.police
    }
    Onde { anchors.right: parent.right; anchors.rightMargin: 12; y: 2 }
    Progression { x: 12; y: 23; width: Math.max(0, parent.width - 24) }

    component Onde: Row {
        id: onde
        visible: Etat.joue
        height: 21; spacing: 3
        Repeater {
            model: 5
            Rectangle {
                required property int index
                anchors.verticalCenter: onde.verticalCenter
                width: 3; height: 4 + Etat.bandes[index] * 16
                radius: width / 2; color: m.planche?.paper ? m.accent : Couleurs.jauge
            }
        }
    }


    component Glissiere: Item {
        id: glissiere
        property bool segmentee: false
        readonly property real value: zoneSeek.pressed && zoneSeek.memePiste ? zoneSeek.apercu : m.position
        readonly property real minimumValue: 0
        readonly property real maximumValue: m.duree
        readonly property real stepSize: 5
        readonly property real fraction: m.duree > 0 ? value / m.duree : 0
        enabled: m.peutChercher
        activeFocusOnTab: enabled
        Accessible.role: enabled ? Accessible.Slider : Accessible.ProgressBar
        Accessible.name: Reglages.t("Position de lecture", "Playback position")
        Accessible.focusable: enabled
        Accessible.ignored: !m.positionConnue || m.duree <= 0
        Accessible.onIncreaseAction: m.chercher(value + stepSize)
        Accessible.onDecreaseAction: m.chercher(value - stepSize)
        Keys.onRightPressed: m.chercher(value + stepSize)
        Keys.onLeftPressed: m.chercher(value - stepSize)
        Keys.onPressed: e => {
            if (e.key === Qt.Key_Home) m.chercher(0)
            else if (e.key === Qt.Key_End) m.chercher(m.duree)
            else return
            e.accepted = true
        }

        Rectangle {
            id: rail
            width: parent.width; height: glissiere.segmentee ? 9 : 4
            anchors.verticalCenter: parent.verticalCenter
            radius: glissiere.segmentee ? 0 : 2
            color: Qt.alpha(m.encre, .22)
            Rectangle { width: parent.width * glissiere.fraction; height: parent.height; radius: parent.radius; color: m.planche?.paper ? m.accent : Couleurs.jauge }
            Repeater {
                model: glissiere.segmentee ? 19 : 0
                Rectangle {
                    required property int index
                    x: Math.round(rail.width * (index + 1) / 20)
                    width: 2; height: rail.height; color: m.planche?.paper ?? Couleurs.carte
                }
            }
        }
        Rectangle {
            visible: glissiere.enabled && (zoneSeek.containsMouse || glissiere.activeFocus)
            width: 8; height: width; radius: width / 2
            x: Math.min(parent.width - width, Math.max(0, parent.width * glissiere.fraction - width / 2))
            anchors.verticalCenter: parent.verticalCenter; color: m.encre
        }
        MouseArea {
            id: zoneSeek
            anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
            property var lecteurDepart: null
            property var pisteDepart
            property real apercu: 0
            readonly property bool memePiste: !!m.lecteur && lecteurDepart === m.lecteur && pisteDepart === m.lecteur.uniqueId
            function valeur(x) { return m.borner(m.duree * x / Math.max(1, width)) }
            onPressed: e => {
                glissiere.forceActiveFocus(Qt.MouseFocusReason)
                lecteurDepart = m.lecteur
                pisteDepart = m.lecteur.uniqueId
                apercu = valeur(e.x)
            }
            onPositionChanged: e => { if (pressed) apercu = valeur(e.x) }
            onReleased: e => { if (memePiste) m.chercher(valeur(e.x)); lecteurDepart = null }
            onCanceled: lecteurDepart = null
        }
    }

    component Progression: Item {
        id: progression
        readonly property bool modeConsole: m.planche?.font === "monospace"
        readonly property real fraction: glissiere.fraction
        readonly property string ecoule: m.positionConnue ? m.temps(glissiere.value) : "—:—"
        readonly property string restant: m.positionConnue && m.duree > 0 ? "−" + m.temps(m.duree - glissiere.value) : "—:—"
        objectName: "nc-musique-progression"
        height: 32
        Glissiere { id: glissiere; width: parent.width; height: 22; segmentee: progression.modeConsole }
        Texte { anchors.bottom: parent.bottom; text: progression.ecoule; color: m.encre; font.pixelSize: 10 }
        Texte { anchors.bottom: parent.bottom; anchors.right: parent.right; text: progression.restant; color: m.encre; font.pixelSize: 10 }
    }

}

pragma ComponentBehavior: Bound
import QtQuick
import Quickshell.Services.Mpris
import Quickshell.Widgets

Item {
    id: m
    property string motif: "music_note"
    property string dessin: ""

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

    // Le transport et les métadonnées sont intégrés à la scène du thème.
    Pochette {
        width: 54; height: 54; anchors.verticalCenter: parent.verticalCenter
    }
    Texte {
        x: 66; y: 2; width: Math.max(0, parent.width - 111)
        text: m.source || m.etatLecture; secondaire: true; font.pixelSize: 11
    }
    Onde { anchors.right: parent.right; y: 0 }
    Progression { x: 66; y: 23; width: Math.max(0, parent.width - 68) }

    component Cible: Item {
        id: cible
        required property string libelle
        readonly property bool survol: zone.containsMouse
        readonly property bool appuye: zone.pressed
        signal activer()
        activeFocusOnTab: enabled
        Accessible.role: Accessible.Button
        Accessible.name: libelle
        Accessible.onPressAction: if (enabled) activer()
        Keys.onReturnPressed: activer()
        Keys.onEnterPressed: activer()
        Keys.onSpacePressed: activer()
        MouseArea {
            id: zone
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: { cible.forceActiveFocus(Qt.MouseFocusReason); cible.activer() }
        }
    }


    component Sceau: Loader {
        sourceComponent: m.dessin !== "" ? vectoriel : glyphe
        Component { id: vectoriel; MotifIle { dessin: m.dessin } }
        Component {
            id: glyphe
            Ico { nom: m.motif || "music_note"; taille: Math.min(width, height) * 0.66; color: Couleurs.accent; Accessible.ignored: true }
        }
    }

    component Pochette: Cible {
        id: cadre
        property real arrondi: Couleurs.rayon(Couleurs.rayonBloc, width, height)
        readonly property bool imagePresente: art.status === Image.Ready || icone.status === Image.Ready
        enabled: !!m.lecteur && m.lecteur.canRaise
        libelle: Reglages.t("Ouvrir le lecteur", "Open player")
        Accessible.ignored: !enabled
        onActiver: if (enabled) { m.lecteur.raise(); Etat.fermer() }
        Rectangle {
            anchors.fill: parent
            radius: cadre.arrondi
            color: Couleurs.carte
        }
        ClippingRectangle {
            anchors.fill: parent; radius: cadre.arrondi; color: "transparent"
            visible: art.status === Image.Ready
            Image {
                id: art
                anchors.fill: parent; fillMode: Image.PreserveAspectCrop
                // Etat applique la politique d’images (notamment ECO_IMAGES) avant tout chargement.
                source: Etat.pochette; asynchronous: true
                sourceSize: Qt.size(128, 128)
            }
        }
        Image {
            id: icone
            anchors.centerIn: parent
            width: Math.min(50, parent.width * 0.52); height: width
            source: art.status !== Image.Ready ? Etat.iconeLecteur : ""
            sourceSize: Qt.size(100, 100)
            visible: art.status !== Image.Ready && status === Image.Ready
        }
        Sceau {
            anchors.centerIn: parent
            width: parent.width * 0.65
            height: width
            active: !cadre.imagePresente
        }
        Rectangle {
            anchors.fill: parent; radius: cadre.arrondi; color: "transparent"
            border.width: cadre.activeFocus ? 2 : 1
            border.color: cadre.survol || cadre.activeFocus ? Couleurs.accent : Couleurs.bordureSubtile
        }
    }

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
                radius: width / 2; color: Couleurs.jauge
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
            color: Couleurs.separateur
            Rectangle { width: parent.width * glissiere.fraction; height: parent.height; radius: parent.radius; color: Couleurs.jauge }
            Repeater {
                model: glissiere.segmentee ? 19 : 0
                Rectangle {
                    required property int index
                    x: Math.round(rail.width * (index + 1) / 20)
                    width: 2; height: rail.height; color: Couleurs.carte
                }
            }
        }
        Rectangle {
            visible: glissiere.enabled && (zoneSeek.containsMouse || glissiere.activeFocus)
            width: 8; height: width; radius: width / 2
            x: Math.min(parent.width - width, Math.max(0, parent.width * glissiere.fraction - width / 2))
            anchors.verticalCenter: parent.verticalCenter; color: Couleurs.accent
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
        property bool modeConsole: false
        readonly property real fraction: glissiere.fraction
        readonly property string ecoule: m.positionConnue ? m.temps(glissiere.value) : "—:—"
        readonly property string restant: m.positionConnue && m.duree > 0 ? "−" + m.temps(m.duree - glissiere.value) : "—:—"
        objectName: "nc-musique-progression"
        height: modeConsole ? 22 : 32
        Glissiere { id: glissiere; width: parent.width; height: 22; segmentee: progression.modeConsole }
        Texte { visible: !progression.modeConsole; anchors.bottom: parent.bottom; text: progression.ecoule; secondaire: true; font.pixelSize: 10 }
        Texte { visible: !progression.modeConsole; anchors.bottom: parent.bottom; anchors.right: parent.right; text: progression.restant; secondaire: true; font.pixelSize: 10 }
    }

}

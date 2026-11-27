pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Shapes
import Quickshell.Widgets

Item {
    id: racine
    required property string variante
    required property string page

    objectName: "nc-sakura-contenu"
    implicitHeight: corps.item?.implicitHeight ?? 0

    readonly property bool ticket: variante === "ticket"
    readonly property bool petale: variante === "petale"
    readonly property color encre: "#4A1F2C"
    readonly property color encreDouce: "#74505A"
    readonly property color accent: "#A32F57"
    readonly property color rose: "#FDE4EC"
    readonly property color rosePale: "#FBEBEB"

    Loader {
        id: corps
        width: racine.width
        sourceComponent: racine.page === "notifications" ? reception : racine.page === "musique" ? musique : null
    }

    component Libelle: Texte {
        color: racine.encre
        font.capitalization: Font.MixedCase
    }

    component Vignette: Rectangle {
        id: vignette
        required property string illustration
        required property string symbole
        property string repli: ""
        property int resolution: 64
        color: racine.rose
        radius: Math.min(10, width / 3)
        Accessible.ignored: true
        ClippingRectangle {
            anchors.fill: parent; radius: vignette.radius; color: "transparent"
            visible: image.status === Image.Ready
            Image {
                id: image
                anchors.fill: parent
                source: vignette.illustration
                sourceSize: Qt.size(vignette.resolution, vignette.resolution)
                fillMode: Image.PreserveAspectCrop
                asynchronous: true
            }
        }
        Image {
            id: imageRepli
            anchors.centerIn: parent
            width: parent.width * .6; height: width
            source: image.status === Image.Ready ? "" : vignette.repli
            sourceSize: Qt.size(40, 40)
            visible: status === Image.Ready
        }
        Ico {
            anchors.centerIn: parent
            nom: vignette.symbole
            taille: Math.max(1, Math.min(23, vignette.width * .58))
            color: racine.accent
            visible: image.status !== Image.Ready && !imageRepli.visible
        }
    }

    Component {
        id: reception
        ColumnLayout {
            spacing: 6
            GridLayout {
                Layout.fillWidth: true
                columns: width >= 235 ? 2 : 1
                columnSpacing: 8; rowSpacing: 2
                Libelle {
                    Layout.fillWidth: true
                    text: Reglages.t("Notifications", "Notifications")
                    font.pixelSize: 17
                    font.weight: Font.DemiBold
                    Accessible.role: Accessible.Heading
                }
                ControleAction {
                    id: toutLire
                    objectName: "nc-sakura-notifs-tout-lire"
                    visible: !Partage.silence && Notifs.liste.length > 0
                    enabled: Notifs.nonLues > 0
                    opacity: enabled ? 1 : .58
                    Layout.alignment: Qt.AlignRight
                    Layout.preferredWidth: Math.min(implicitWidth, racine.width)
                    implicitWidth: contentItem.implicitWidth + 14
                    implicitHeight: 27
                    padding: 0
                    text: Reglages.t("Marquer comme lues", "Mark as read")
                    Accessible.name: text
                    onClicked: if (!Partage.silence) Notifs.toutLire()
                    background: Rectangle {
                        color: toutLire.contientPointeur ? racine.rose : "transparent"
                        radius: height / 2
                    }
                    contentItem: Libelle {
                        text: toutLire.text
                        color: racine.accent
                        font.pixelSize: 11
                        font.weight: Font.DemiBold
                        horizontalAlignment: Text.AlignHCenter
                    }
                }
            }
            ListView {
                id: liste
                objectName: "nc-sakura-notifs-liste"
                readonly property int hauteurLigne: 44
                readonly property bool aDesNotifications: count > 0 && !Partage.silence
                Layout.fillWidth: true
                Layout.preferredHeight: Math.min(count, 2) * hauteurLigne + (count > 1 ? spacing : 0)
                visible: aDesNotifications
                model: Partage.silence ? null : Notifs.liste
                spacing: racine.ticket ? 0 : 4
                clip: true
                boundsBehavior: Flickable.StopAtBounds
                activeFocusOnTab: true
                keyNavigationEnabled: true
                Accessible.role: Accessible.List
                Accessible.name: Reglages.t("Notifications", "Notifications")
                Keys.onReturnPressed: event => ouvrirCourante(event)
                Keys.onEnterPressed: event => ouvrirCourante(event)

                function ouvrirCourante(event) {
                    if (!event.isAutoRepeat && !Partage.silence && currentItem) Notifs.ouvrir(currentItem.modelData)
                }

                ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded; width: 6 }
                delegate: ControleAction {
                    id: carte
                    required property var modelData
                    required property int index
                    readonly property bool nonLue: !Notifs.lus[modelData.id]
                    readonly property string appli: Notifs.nomAppli(modelData)
                    readonly property string quand: Notifs.quand(modelData, Etat.minute.getTime())
                    readonly property bool surlignee: contientPointeur || (liste.activeFocus && ListView.isCurrentItem)

                    objectName: "nc-sakura-notif-" + modelData.id
                    width: Math.max(0, liste.width - (liste.count > 2 ? 8 : 0))
                    height: liste.hauteurLigne
                    padding: 0
                    text: modelData.summary || appli
                    Accessible.name: text
                    Accessible.description: appli + (quand ? ", " + quand : "")
                        + (nonLue ? Reglages.t(", non lue", ", unread") : "")
                    onClicked: if (!Partage.silence) Notifs.ouvrir(modelData)
                    background: Rectangle {
                        radius: racine.ticket ? 0 : 10
                        color: carte.surlignee ? racine.rose : (racine.ticket ? "transparent" : racine.rosePale)
                        Shape {
                            anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom
                            anchors.margins: 3
                            height: 1
                            visible: racine.ticket && carte.index < liste.count - 1
                            ShapePath {
                                fillColor: "transparent"
                                strokeColor: Qt.alpha(racine.accent, .32)
                                strokeStyle: ShapePath.DashLine
                                dashPattern: [3, 3]
                                capStyle: ShapePath.FlatCap
                                startX: 0; startY: .5
                                PathLine { x: Math.max(0, carte.width - 6); y: .5 }
                            }
                        }
                    }
                    contentItem: RowLayout {
                        spacing: 6
                        Vignette {
                            Layout.leftMargin: 6
                            Layout.preferredWidth: Math.min(30, carte.width * .25)
                            Layout.preferredHeight: Layout.preferredWidth
                            illustration: Notifs.icone(carte.modelData)
                            symbole: "notifications"
                        }
                        ColumnLayout {
                            Layout.fillWidth: true
                            Layout.minimumWidth: 0
                            spacing: 1
                            Libelle {
                                Layout.fillWidth: true
                                Layout.minimumWidth: 0
                                text: carte.text
                                font.pixelSize: 13
                                font.weight: carte.nonLue ? Font.DemiBold : Font.Normal
                            }
                            Libelle {
                                Layout.fillWidth: true
                                Layout.minimumWidth: 0
                                text: carte.quand ? carte.quand + " · " + carte.appli : carte.appli
                                font.pixelSize: 10
                                color: racine.encreDouce
                            }
                        }
                        Item {
                            Layout.preferredWidth: 7
                            Layout.preferredHeight: 7
                            Layout.rightMargin: 8
                            Rectangle { anchors.fill: parent; radius: width / 2; color: racine.accent; visible: carte.nonLue }
                        }
                    }
                }
            }
            Libelle {
                objectName: "nc-sakura-notifs-vide"
                Layout.fillWidth: true
                Layout.preferredHeight: 36
                visible: !liste.aDesNotifications
                text: Partage.silence ? Reglages.t("Notifications masquées", "Notifications hidden")
                    : Reglages.t("Aucune notification", "No notifications")
                color: racine.encreDouce
                horizontalAlignment: Text.AlignHCenter
            }
        }
    }

    Component {
        id: musique
        GridLayout {
            id: lecteurSakura
            readonly property var lecteur: Etat.lecteur
            readonly property bool coteACote: !racine.petale && width >= 220
            readonly property bool positionConnue: !!lecteur && lecteur.positionSupported
            readonly property real duree: lecteur && lecteur.lengthSupported ? Math.max(0, lecteur.length) : 0
            readonly property real position: positionConnue ? borner(lecteur.position) : 0
            readonly property bool peutChercher: positionConnue && duree > 0 && lecteur.canSeek
            columns: 3
            columnSpacing: 8; rowSpacing: 7

            function borner(s) { return Math.max(0, duree > 0 ? Math.min(duree, s) : s) }
            function chercher(s) { if (peutChercher) lecteur.position = borner(s) }
            function temps(s) {
                const secondes = Math.floor(s)
                return Math.floor(secondes / 60) + ":" + String(secondes % 60).padStart(2, "0")
            }

            Vignette {
                objectName: "nc-sakura-musique-pochette"
                Layout.row: 0; Layout.column: 0
                Layout.preferredWidth: Math.min(racine.petale ? 54 : 42, racine.width * .28)
                Layout.preferredHeight: Layout.preferredWidth
                illustration: Etat.pochette
                repli: Etat.iconeLecteur
                symbole: "music_note"
                resolution: 160
            }
            ColumnLayout {
                Layout.row: 0; Layout.column: 1
                Layout.columnSpan: lecteurSakura.coteACote ? 1 : 2
                Layout.fillWidth: true; Layout.minimumWidth: 0
                spacing: 2
                Libelle {
                    objectName: "nc-sakura-musique-titre"
                    Layout.fillWidth: true; Layout.minimumWidth: 0
                    text: Etat.titre || (lecteurSakura.lecteur ? Reglages.t("Sans titre", "Untitled") : Reglages.t("Aucun lecteur", "No player"))
                    font.pixelSize: racine.petale ? 17 : 14
                    font.weight: Font.DemiBold
                }
                Libelle {
                    objectName: "nc-sakura-musique-artiste"
                    Layout.fillWidth: true; Layout.minimumWidth: 0
                    text: Etat.artiste || (lecteurSakura.lecteur?.identity ?? "")
                    visible: text !== ""
                    font.pixelSize: 11
                    color: racine.encreDouce
                }
            }
            ColumnLayout {
                Layout.row: 1; Layout.column: 0; Layout.columnSpan: 3
                Layout.fillWidth: true
                spacing: 0
                Item {
                    id: progression
                    readonly property real value: geste.pressed && geste.memePiste ? geste.apercu : lecteurSakura.position
                    readonly property real minimumValue: 0
                    readonly property real maximumValue: lecteurSakura.duree
                    readonly property real stepSize: 5
                    readonly property real fraction: maximumValue > 0 ? value / maximumValue : 0
                    objectName: "nc-sakura-musique-progression"
                    Layout.fillWidth: true
                    Layout.preferredHeight: 17
                    enabled: lecteurSakura.peutChercher
                    activeFocusOnTab: enabled
                    Accessible.role: enabled ? Accessible.Slider : Accessible.ProgressBar
                    Accessible.name: Reglages.t("Position de lecture", "Playback position")
                    Accessible.focusable: enabled
                    Accessible.ignored: !lecteurSakura.positionConnue || maximumValue <= 0
                    Accessible.onIncreaseAction: lecteurSakura.chercher(value + stepSize)
                    Accessible.onDecreaseAction: lecteurSakura.chercher(value - stepSize)
                    Keys.onRightPressed: lecteurSakura.chercher(value + stepSize)
                    Keys.onLeftPressed: lecteurSakura.chercher(value - stepSize)
                    Keys.onPressed: event => {
                        if (event.key === Qt.Key_Home) lecteurSakura.chercher(0)
                        else if (event.key === Qt.Key_End) lecteurSakura.chercher(maximumValue)
                        else return
                        event.accepted = true
                    }

                    Rectangle {
                        anchors.verticalCenter: parent.verticalCenter
                        width: parent.width; height: 4; radius: 2
                        color: Qt.alpha(racine.accent, .22)
                        Rectangle { width: parent.width * progression.fraction; height: parent.height; radius: 2; color: racine.accent }
                    }
                    Rectangle {
                        visible: progression.enabled && (geste.containsMouse || progression.activeFocus || geste.pressed)
                        width: Math.min(9, parent.width); height: width; radius: width / 2
                        x: Math.min(parent.width - width, Math.max(0, parent.width * progression.fraction - width / 2))
                        anchors.verticalCenter: parent.verticalCenter
                        color: racine.accent
                    }
                    MouseArea {
                        id: geste
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        property var lecteurDepart: null
                        property var pisteDepart
                        property real apercu: 0
                        readonly property bool memePiste: !!lecteurSakura.lecteur && lecteurDepart === lecteurSakura.lecteur
                            && pisteDepart === lecteurSakura.lecteur.uniqueId
                        function valeur(x) { return lecteurSakura.borner(lecteurSakura.duree * x / Math.max(1, width)) }
                        onPressed: event => {
                            progression.forceActiveFocus(Qt.MouseFocusReason)
                            lecteurDepart = lecteurSakura.lecteur
                            pisteDepart = lecteurSakura.lecteur.uniqueId
                            apercu = valeur(event.x)
                        }
                        onPositionChanged: event => { if (pressed) apercu = valeur(event.x) }
                        onReleased: event => {
                            if (memePiste) lecteurSakura.chercher(valeur(event.x))
                            lecteurDepart = null
                        }
                        onCanceled: lecteurDepart = null
                    }
                }
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 4
                    Libelle {
                        Layout.fillWidth: true
                        Layout.minimumWidth: 0
                        text: lecteurSakura.positionConnue ? lecteurSakura.temps(progression.value) : "—:—"
                        font.pixelSize: 10
                        color: racine.encreDouce
                    }
                    Libelle {
                        text: lecteurSakura.positionConnue && lecteurSakura.duree > 0
                            ? "−" + lecteurSakura.temps(lecteurSakura.duree - progression.value) : "—:—"
                        font.pixelSize: 10
                        color: racine.encreDouce
                    }
                }
            }
            RowLayout {
                id: transport
                Layout.row: lecteurSakura.coteACote ? 0 : 2
                Layout.column: lecteurSakura.coteACote ? 2 : 0
                Layout.columnSpan: lecteurSakura.coteACote ? 1 : 3
                Layout.alignment: Qt.AlignHCenter
                spacing: racine.petale ? 9 : 2
                Repeater {
                    model: 3
                    delegate: ControleAction {
                        id: touche
                        required property int index
                        objectName: "nc-sakura-transport-" + ["precedent", "lecture", "suivant"][index]
                        readonly property bool lecture: index === 1
                        enabled: !!lecteurSakura.lecteur && (index === 0 ? lecteurSakura.lecteur.canGoPrevious
                            : lecture ? lecteurSakura.lecteur.canTogglePlaying : lecteurSakura.lecteur.canGoNext)
                        opacity: enabled ? 1 : .45
                        implicitWidth: Math.min(racine.petale ? (lecture ? 40 : 34) : 30,
                            Math.max(0, (racine.width - 2 * transport.spacing) / 3))
                        implicitHeight: implicitWidth
                        padding: 0
                        text: index === 0 ? Reglages.t("Précédent", "Previous")
                            : lecture ? (Etat.joue ? "Pause" : Reglages.t("Lecture", "Play")) : Reglages.t("Suivant", "Next")
                        Accessible.name: text
                        background: Rectangle {
                            radius: height / 2
                            color: touche.lecture ? racine.accent : (touche.contientPointeur || racine.petale ? racine.rose : "transparent")
                        }
                        contentItem: Ico {
                            nom: touche.index === 0 ? "skip_previous"
                                : touche.lecture ? (Etat.joue ? "pause" : "play_arrow") : "skip_next"
                            taille: Math.max(1, Math.min(touche.lecture ? 22 : 19, touche.width - 4))
                            color: touche.lecture ? "#FFF8F5" : racine.accent
                        }
                        onClicked: {
                            if (index === 0 && lecteurSakura.lecteur?.canGoPrevious) lecteurSakura.lecteur.previous()
                            else if (index === 1) Etat.lecturePause()
                            else if (index === 2 && lecteurSakura.lecteur?.canGoNext) lecteurSakura.lecteur.next()
                        }
                    }
                }
            }
        }
    }
}

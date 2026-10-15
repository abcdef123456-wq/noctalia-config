// Une île par écran : pilule noire posée sur la barre de Noctalia (couche au-dessus), qui se déploie avec un ressort,
// comme l'île dynamique de l'iPhone. Ouverte, ses pages se suivent verticalement : d'abord les activités en cours
// (musique, minuteur, recharge, mode jeu), puis le centre de contrôle, Son, Wi-Fi, Bluetooth, Système, Calendrier.
// Points sur le bord droit, molette ou deux doigts pour descendre ; l'île prend la taille de chaque page.
// Deux activités en même temps (musique + minuteur) : la seconde dans une petite bulle à côté de la pilule.
// Seule la forme de l'île capte la souris ; un clic ailleurs, Échap, Super + C ou un clic sur la pilule la referment.
import QtQuick
import Quickshell
import Quickshell.Wayland
import Quickshell.Hyprland

PanelWindow {
    id: fen
    required property var modelData
    screen: modelData
    readonly property bool ouverte: Etat.ecranOuvert === modelData.name

    anchors { top: true; left: true; right: true }
    implicitHeight: 700
    color: "transparent"
    exclusionMode: ExclusionMode.Ignore
    WlrLayershell.layer: WlrLayer.Overlay
    WlrLayershell.namespace: "nc-ile"
    WlrLayershell.keyboardFocus: ouverte ? WlrKeyboardFocus.OnDemand : WlrKeyboardFocus.None
    mask: Region { item: ile; Region { item: bulle } }

    HyprlandFocusGrab {
        windows: [fen]
        active: fen.ouverte
        onCleared: Etat.fermer()
    }

    // Taille de chaque page
    function adaptee(nom, mini) { return Qt.size(432, Math.max(mini, Math.min(580, (Etat.hauteurs[nom] || mini) + 32))) }
    readonly property var tailles: ({
        musique: Qt.size(430, 214), minuteur: Qt.size(430, Etat.minuteurFin > 0 ? 150 : 268), charge: Qt.size(400, 140),
        jeu: Qt.size(400, 140), centre: Qt.size(432, 494), son: adaptee("son", 300), reseau: adaptee("reseau", 260),
        bluetooth: adaptee("bluetooth", 220), notifications: adaptee("notifications", 200), systeme: Qt.size(432, 600), calendrier: Qt.size(432, 410)
    })
    readonly property size taille: tailles[Etat.vueActive] || tailles.centre
    readonly property bool points: Etat.vues.length > 1
    // Notification en cours : l'île fermée s'étire en bannière (sur l'écran actif seulement)
    readonly property bool banniere: !ouverte && Notifs.banniere !== null
        && (!Hyprland.focusedMonitor || Hyprland.focusedMonitor.name === modelData.name)
    readonly property int hauteurBanniere: Notifs.banniere && Notifs.banniere.body !== "" ? 92 : 74

    // Bulle de la seconde activité (minuteur pendant la musique), comme l'île scindée de l'iPhone
    Rectangle {
        id: bulle
        readonly property bool montre: !fen.ouverte && !fen.banniere && Etat.aMusique && Etat.minuteurFin > 0 && Etat.activiteType === ""
        x: ile.x + ile.width + (montre ? 7 : -30)
        y: 9; width: 30; height: 30; radius: 15
        color: "#000000"
        opacity: montre ? 1 : 0
        visible: opacity > 0.01
        Behavior on x { SpringAnimation { spring: 3.4; damping: 0.36 } }
        Behavior on opacity { NumberAnimation { duration: 200 } }
        Canvas {
            anchors.fill: parent
            property real f: Etat.minuteurDuree > 0 ? Etat.minuteurReste * 1000 / Etat.minuteurDuree : 0
            onFChanged: requestPaint()
            onPaint: {
                var c = getContext("2d"); c.reset(); c.lineWidth = 2.5; c.lineCap = "round"
                c.strokeStyle = "#ff9f0a"; c.beginPath(); c.arc(15, 15, 11, -Math.PI / 2, -Math.PI / 2 + 2 * Math.PI * f); c.stroke()
            }
        }
        Ico { anchors.centerIn: parent; nom: "timer"; taille: 13; color: "#ff9f0a" }
        MouseArea { anchors.fill: parent; onClicked: { Etat.basculer(fen.modelData.name, false); Etat.aller("minuteur") } }
    }

    Rectangle {
        id: ile
        anchors.horizontalCenter: parent.horizontalCenter
        y: 9                                        // centrée dans la barre (barre à 6 du bord, 36 de haut)
        width: fen.ouverte ? fen.taille.width : (fen.banniere ? 440 : compact.largeur)
        height: fen.ouverte ? fen.taille.height : (fen.banniere ? fen.hauteurBanniere : 30)
        radius: fen.ouverte ? 42 : (fen.banniere ? 32 : 15)
        color: "#000000"
        clip: true

        // Ressort façon iOS : rapide, avec un léger rebond ; le rayon suit sans à-coup
        Behavior on width { SpringAnimation { spring: 3.4; damping: 0.34; epsilon: 0.25 } }
        Behavior on height { SpringAnimation { spring: 3.4; damping: 0.36; epsilon: 0.25 } }
        Behavior on radius { NumberAnimation { duration: 280; easing.type: Easing.OutCubic } }

        Compact {
            id: compact
            anchors.centerIn: parent
            width: parent.width
            opacity: fen.ouverte || fen.banniere ? 0 : 1
            Behavior on opacity { NumberAnimation { duration: fen.ouverte || fen.banniere ? 90 : 220; easing.type: Easing.OutCubic } }
        }

        Banniere {
            anchors.fill: parent
            opacity: fen.banniere && ile.height > fen.hauteurBanniere * 0.7 ? 1 : 0
            visible: opacity > 0.01
            Behavior on opacity { NumberAnimation { duration: fen.banniere ? 180 : 90; easing.type: Easing.OutCubic } }
        }

        MouseArea {
            anchors.fill: parent
            enabled: !fen.ouverte && !fen.banniere
            acceptedButtons: Qt.LeftButton | Qt.RightButton
            onClicked: e => e.button === Qt.RightButton ? Etat.lecturePause() : Etat.basculer(fen.modelData.name, false)
            onWheel: w => Etat.reglerVolume(Etat.volume + (w.angleDelta.y > 0 ? 0.05 : -0.05))
        }

        // Glisser entre les pages : molette ou deux doigts, partout dans l'île (les curseurs ne prennent pas la molette)
        MouseArea {
            anchors.fill: parent
            enabled: fen.ouverte && fen.points
            acceptedButtons: Qt.NoButton
            property real cumul: 0
            property real dernier: 0         // heure du dernier événement : un trou de 200 ms = nouveau geste
            property bool geste: false       // le geste en cours a déjà servi (liste défilée ou page changée)
            onWheel: w => {
                var t = Date.now()
                if (t - dernier > 200) { geste = false; cumul = 0 }
                dernier = t
                var dy = w.pixelDelta.y !== 0 ? w.pixelDelta.y : w.angleDelta.y / 2
                // Un geste ne sert qu'une fois : il fait défiler la liste de la page d'un grand coup, ou, si la liste
                // est déjà au bout (ou qu'il n'y en a pas), change de page. L'élan du pavé tactile ne compte pas.
                if (verrou.running || geste) return
                cumul += dy
                if (Math.abs(cumul) < 30) return
                var page = pages.itemAt(Etat.vue), contenu = page ? page.contenu : null
                if (contenu && contenu.defiler && contenu.defiler(cumul)) { cumul = 0; geste = true; return }
                if (Math.abs(cumul) >= 60) {
                    Etat.changerVue(cumul > 0 ? -1 : 1)
                    cumul = 0
                    geste = true
                    verrou.restart()
                }
            }
            Timer { id: verrou; interval: 300 }
        }

        // Pages empilées : celle de la vue active est à sa place, les autres glissent hors de l'île
        Repeater {
            id: pages
            model: Etat.vues
            Item {
                id: pageIle
                readonly property var contenu: chargeur.item
                required property string modelData
                required property int index
                readonly property size t: fen.tailles[modelData] || fen.tailles.centre
                readonly property bool active: modelData === Etat.vueActive
                x: (ile.width - t.width) / 2 + 16
                width: t.width - 32 - (fen.points ? 14 : 0)
                height: t.height - 32
                y: 16 + (index - Etat.vue) * (ile.height * 0.6)
                Behavior on y { SpringAnimation { spring: 3.6; damping: 0.4 } }
                // Le contenu apparaît quand l'île a presque sa taille ; s'efface dès qu'elle se referme ou change de page
                opacity: fen.ouverte && active && ile.height > t.height * 0.72 ? 1 : 0
                visible: opacity > 0.01
                Behavior on opacity { NumberAnimation { duration: fen.ouverte ? 200 : 80; easing.type: Easing.OutCubic } }
                Loader {
                    id: chargeur
                    anchors.fill: parent
                    active: pageIle.visible || pageIle.active
                    sourceComponent: ({ musique: pMusique, minuteur: pMinuteur, charge: pCharge, jeu: pJeu, centre: pCentre,
                                        son: pSon, notifications: pNotifs, reseau: pReseau, bluetooth: pBluetooth, systeme: pSysteme,
                                        calendrier: pCalendrier })[pageIle.modelData] || pCentre
                }
            }
        }
        Component { id: pMusique; Musique {} }
        Component { id: pMinuteur; Minuteur {} }
        Component { id: pCharge; Charge {} }
        Component { id: pJeu; Jeu {} }
        Component { id: pCentre; Centre {} }
        Component { id: pSon; Son {} }
        Component { id: pNotifs; PageNotifs {} }
        Component { id: pReseau; PageListe { mode: "wifi" } }
        Component { id: pBluetooth; PageListe { mode: "bluetooth" } }
        Component { id: pSysteme; Systeme {} }
        Component { id: pCalendrier; Calendrier {} }

        // Points de page sur le bord droit (comme le Centre de contrôle de l'iPhone)
        Column {
            anchors.right: parent.right; anchors.rightMargin: 9
            anchors.verticalCenter: parent.verticalCenter
            spacing: 6
            visible: fen.ouverte && fen.points
            Repeater {
                model: Etat.vues
                Rectangle {
                    required property string modelData
                    required property int index
                    readonly property bool active: modelData === Etat.vueActive
                    width: 6; height: active ? 14 : 6; radius: 3
                    color: active ? "white" : "#5a5a5e"
                    Behavior on height { SpringAnimation { spring: 5; damping: 0.5 } }
                    MouseArea { anchors.fill: parent; anchors.margins: -5; onClicked: Etat.aller(parent.modelData) }
                }
            }
        }

        focus: fen.ouverte
        Keys.onEscapePressed: Etat.fermer()
        Keys.onUpPressed: Etat.changerVue(-1)
        Keys.onDownPressed: Etat.changerVue(1)
    }
}

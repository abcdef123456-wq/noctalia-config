// Navigation persistante de l'île ouverte : bandeau, galerie ou rail de pages.
import QtQuick
import QtQuick.Controls

Item {
    id: entete
    property var papier: null
    readonly property color encre: papier ? papier.ink : Couleurs.texte
    readonly property color pigment: papier ? papier.accent : Couleurs.accent
    readonly property color surPigment: papier ? papier.paper : Couleurs.surAccent
    property var pages: []
    property string active: ""
    property int nonLues: 0
    signal choisir(string nom)
    signal ouvrirControle(Item bouton)

    property bool lateral: false
    property string style: "capsules"
    readonly property bool galerie: style === "galerie"
    readonly property bool icones: style === "icones"
    readonly property bool plein: style === "blocs"
    readonly property bool ligne: style === "filets" || galerie
    implicitHeight: galerie ? 50 : 36
    visible: pages.length > 1

    function meta(nom) {
        var m = ({
            essentiel:     { ico: "schedule",              fr: "Essentiel", en: "Now" },
            musique:       { ico: "music_note",            fr: "Musique",   en: "Music" },
            notifications: { ico: "notifications",         fr: "Notifs",    en: "Alerts" },
            minuteur:      { ico: "timer",                 fr: "Minuteur",  en: "Timer" },
            appel:         { ico: "call",                  fr: "Appel",     en: "Call" },
            charge:        { ico: "battery_charging_full", fr: "Batterie",  en: "Battery" },
            centre:        { ico: "tune",                  fr: "Contrôle",  en: "Control" },
            son:           { ico: "volume_up",             fr: "Son",       en: "Sound" },
            reseau:        { ico: "wifi",                  fr: "Réseau",    en: "Network" },
            bluetooth:     { ico: "bluetooth",             fr: "Bluetooth", en: "Bluetooth" },
            systeme:       { ico: "monitoring",            fr: "Système",   en: "System" },
            sante:         { ico: "thermostat",            fr: "Santé",     en: "Health" },
            calendrier:    { ico: "calendar_month",        fr: "Agenda",    en: "Calendar" },
            meteo:         { ico: "partly_cloudy_day",     fr: "Météo",     en: "Weather" },
            presse:        { ico: "content_paste",         fr: "Presse",    en: "Clipboard" },
            fenetres:      { ico: "view_agenda",           fr: "Fenêtres",  en: "Windows" },
            jeu:           { ico: "sports_esports",        fr: "Jeu",       en: "Game" },
            claude:        { ico: "auto_awesome",          fr: "Agents",    en: "Agents" },
            assistant:     { ico: "smart_toy",             fr: "JARVIS",    en: "JARVIS" },
            terminal:      { ico: "terminal",              fr: "Terminal",  en: "Terminal" },
            resume:        { ico: "wb_sunny",              fr: "Résumé",    en: "Summary" },
            concentration: { ico: "do_not_disturb_on",     fr: "Focus",     en: "Focus" }
        })[nom]
        return m ? { ico: m.ico, nom: Reglages.t(m.fr, m.en) } : { ico: "circle", nom: nom }
    }

    function montrerActive() {
        const index = pages.indexOf(active)
        if (index >= 0) onglets.positionViewAtIndex(index, ListView.Contain)
    }
    onActiveChanged: Qt.callLater(montrerActive)
    onPagesChanged: Qt.callLater(montrerActive)
    onWidthChanged: Qt.callLater(montrerActive)
    onHeightChanged: Qt.callLater(montrerActive)

    Rectangle {
        anchors.fill: parent
        visible: entete.style === "capsules" || entete.lateral
        radius: Couleurs.rayon(entete.style === "capsules" ? 18 : Couleurs.rayonBloc, width, height)
        color: entete.papier ? Qt.alpha(entete.encre, .055) : entete.plein ? Couleurs.surfaceDouce : Qt.alpha(Couleurs.voile, Couleurs.sombre ? .045 : .06)
        border.width: entete.style === "index" || entete.plein ? 1 : 0
        border.color: Couleurs.bordureSubtile
    }
    ListView {
        id: onglets
        x: 4; y: 3
        width: Math.max(0, entete.width - (entete.lateral ? 8 : boutonControle.width + 14))
        height: Math.max(0, entete.height - (entete.lateral ? boutonControle.height + 14 : 6))
        orientation: entete.lateral ? ListView.Vertical : ListView.Horizontal
        model: entete.pages
        spacing: entete.plein ? 3 : 2
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        readonly property real largeurOnglet: Math.max(76, Math.min(140, (width - spacing * (count - 1)) / Math.max(1, count)))
        delegate: Rectangle {
            id: tab
            required property string modelData
            required property int index
            readonly property var info: entete.meta(modelData)
            readonly property bool choisi: modelData === entete.active
            readonly property bool empile: entete.galerie && !entete.lateral
            readonly property bool symbole: entete.style !== "index"
            readonly property bool badge: modelData === "notifications" && entete.nonLues > 0
            objectName: "nc-ile-onglet-" + modelData
            width: entete.lateral ? onglets.width : (entete.icones ? 38 : onglets.largeurOnglet)
            height: entete.lateral ? (entete.icones ? 31 : 34) : onglets.height
            radius: Couleurs.rayon(entete.style === "capsules" ? 16 : entete.plein ? 1 : 6, width, height)
            readonly property bool capsuleNeon: entete.style === "capsules" && Couleurs.themeActif === "dracula"
            color: choisi && entete.plein ? entete.encre
                 : choisi && capsuleNeon ? Qt.alpha(entete.pigment, .20)
                 : choisi && !entete.ligne ? Qt.alpha(entete.encre, .16)
                 : action.contientPointeur ? Qt.alpha(entete.encre, .10) : "transparent"
            border.width: (entete.plein && !choisi) || (capsuleNeon && choisi) ? 1 : 0
            border.color: capsuleNeon && choisi ? Qt.alpha(entete.pigment, .48) : Couleurs.bordureSubtile

            Rectangle {
                visible: tab.choisi && entete.ligne
                x: entete.lateral ? 0 : 5
                y: entete.lateral ? 5 : parent.height - height
                width: entete.lateral ? 2 : parent.width - 10
                height: entete.lateral ? parent.height - 10 : 2
                color: entete.pigment
            }
            Ico {
                visible: tab.symbole
                x: entete.icones || tab.empile ? (parent.width - width) / 2 : 7
                y: tab.empile ? 4 : (parent.height - height) / 2
                nom: tab.info.ico
                taille: 15
                color: tab.choisi && entete.plein ? entete.surPigment : entete.encre
            }
            Texte {
                id: titre
                visible: !entete.icones
                x: tab.symbole && !tab.empile ? 27 : 5
                y: tab.empile ? 21 : 0
                width: Math.max(0, parent.width - x - (tab.badge ? 10 : 5))
                height: tab.empile ? parent.height - y - 3 : parent.height
                horizontalAlignment: tab.empile ? Text.AlignHCenter : Text.AlignLeft
                text: (entete.style === "index" ? String(tab.index + 1).padStart(2, "0") + "  " : "") + tab.info.nom
                font.pixelSize: entete.lateral || entete.plein ? 10 : 11
                font.weight: tab.choisi ? Font.DemiBold : Font.Medium
                color: tab.choisi && entete.plein ? entete.surPigment : entete.encre
            }
            Rectangle {
                visible: tab.badge
                x: parent.width - width - 4; y: 5
                width: 5; height: 5; radius: width / 2
                color: tab.choisi && entete.plein ? entete.surPigment : entete.pigment
            }
            ControleAction {
                id: action
                anchors.fill: parent
                text: tab.info.nom
                Accessible.checkable: true
                Accessible.checked: tab.choisi
                ToolTip.visible: hovered && (!titre.visible || titre.truncated)
                ToolTip.delay: 550
                ToolTip.text: text
                onClicked: entete.choisir(tab.modelData)
            }
        }
    }
    Rectangle {
        id: boutonControle
        objectName: "nc-ile-vers-controle"
        x: entete.lateral ? (parent.width - width) / 2 : parent.width - width - 4
        y: entete.lateral ? parent.height - height - 4 : (parent.height - height) / 2
        width: 28; height: 28
        radius: Couleurs.rayon(entete.plein ? 1 : 14, width, height)
        color: Qt.alpha(entete.encre, zc.contientPointeur ? .18 : .08)
        Ico {
            anchors.centerIn: parent
            nom: "tune"; taille: 15
            color: entete.encre
        }
        ControleAction {
            id: zc
            anchors.fill: parent
            text: Reglages.t("Centre de contrôle", "Control Center")
            onClicked: entete.ouvrirControle(boutonControle)
        }
    }
}

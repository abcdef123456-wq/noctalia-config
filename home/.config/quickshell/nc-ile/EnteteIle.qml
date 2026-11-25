// Bandeau d'en-tête de l'île ouverte : onglets lisibles (icône + libellé court) pour les vues essentielles,
// adapté au style du thème actif, avec accès direct au panneau Centre de contrôle.
import QtQuick

Item {
    id: entete
    property var pages: []
    property string active: ""
    property int nonLues: 0
    signal choisir(string nom)
    signal ouvrirControle()

    implicitHeight: 34

    function meta(nom) {
        var m = ({
            essentiel:     { ico: "schedule",             fr: "Essentiel",     en: "Essentials" },
            musique:       { ico: "music_note",           fr: "Musique",       en: "Music" },
            notifications: { ico: "notifications",        fr: "Notifs",        en: "Alerts" },
            minuteur:      { ico: "timer",                fr: "Minuteur",      en: "Timer" },
            appel:         { ico: "call",                 fr: "Appel",         en: "Call" },
            charge:        { ico: "battery_charging_full", fr: "Batterie",     en: "Battery" },
            centre:        { ico: "tune",                 fr: "Contrôle",      en: "Control" },
            son:           { ico: "volume_up",            fr: "Son",           en: "Sound" },
            reseau:        { ico: "wifi",                 fr: "Réseau",        en: "Network" },
            bluetooth:     { ico: "bluetooth",            fr: "Bluetooth",     en: "Bluetooth" },
            systeme:       { ico: "monitoring",           fr: "Système",       en: "System" },
            sante:         { ico: "thermostat",           fr: "Santé",         en: "Health" },
            calendrier:    { ico: "calendar_month",       fr: "Agenda",        en: "Calendar" },
            meteo:         { ico: "partly_cloudy_day",    fr: "Météo",         en: "Weather" },
            presse:        { ico: "content_paste",        fr: "Presse",        en: "Clipboard" },
            fenetres:      { ico: "view_agenda",          fr: "Fenêtres",      en: "Windows" },
            jeu:           { ico: "sports_esports",       fr: "Jeu",           en: "Game" },
            claude:        { ico: "auto_awesome",         fr: "Agents",        en: "Agents" },
            assistant:     { ico: "smart_toy",            fr: "JARVIS",        en: "JARVIS" },
            terminal:      { ico: "terminal",             fr: "Terminal",      en: "Terminal" },
            resume:        { ico: "wb_sunny",             fr: "Résumé",        en: "Summary" },
            concentration: { ico: "do_not_disturb_on",    fr: "Focus",         en: "Focus" }
        })[nom]
        return m ? { ico: m.ico, nom: Reglages.t(m.fr, m.en) } : { ico: "circle", nom: nom }
    }

    // Fenêtre d'onglets : si <= 4 pages, toutes sont montrées ; au-delà, 3 autour de la page active
    readonly property var pagesMontrees: {
        if (!pages || pages.length <= 4) return pages || []
        var idx = Math.max(0, pages.indexOf(active))
        var debut = Math.max(0, Math.min(pages.length - 3, idx - 1))
        return pages.slice(debut, debut + 3)
    }

    Row {
        id: onglets
        anchors.left: parent.left
        anchors.verticalCenter: parent.verticalCenter
        spacing: 5

        Repeater {
            model: entete.pagesMontrees
            Rectangle {
                id: tab
                required property string modelData
                readonly property bool estActif: modelData === entete.active
                readonly property var info: entete.meta(modelData)
                readonly property bool avecBadge: modelData === "notifications" && entete.nonLues > 0
                objectName: "nc-ile-onglet-" + modelData
                width: Math.min(130, contenuTab.implicitWidth + 18)
                height: 28
                radius: Couleurs.rayon(14, width, height)
                color: estActif ? Couleurs.accentDoux : (zt.containsMouse ? Couleurs.gris2 : "transparent")
                border.width: estActif ? 1 : 0
                border.color: estActif ? Couleurs.accentBord : "transparent"
                Behavior on color { enabled: !Reglages.sobre; ColorAnimation { duration: 120 } }

                Row {
                    id: contenuTab
                    anchors.centerIn: parent
                    spacing: 5
                    Ico {
                        anchors.verticalCenter: parent.verticalCenter
                        nom: tab.info.ico
                        taille: 14
                        color: tab.estActif ? Couleurs.accent : Couleurs.texteSec
                    }
                    Texte {
                        anchors.verticalCenter: parent.verticalCenter
                        text: tab.info.nom
                        font.pixelSize: 12
                        font.weight: tab.estActif ? Font.DemiBold : Font.Medium
                        color: tab.estActif ? Couleurs.texte : Couleurs.texteSec
                    }
                    Rectangle {
                        visible: tab.avecBadge
                        anchors.verticalCenter: parent.verticalCenter
                        width: 6; height: 6; radius: width / 2
                        color: Couleurs.accent
                    }
                }
                MouseArea {
                    id: zt
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: entete.choisir(tab.modelData)
                }
                Accessible.role: Accessible.Button
                Accessible.name: tab.info.nom
                Accessible.checkable: true
                Accessible.checked: tab.estActif
            }
        }
    }

    // Bouton d'accès rapide au Centre de contrôle (toujours visible à droite de l'en-tête)
    Rectangle {
        id: boutonControle
        objectName: "nc-ile-vers-controle"
        anchors.right: parent.right
        anchors.verticalCenter: parent.verticalCenter
        width: 28; height: 28
        radius: Couleurs.rayon(14, width, height)
        color: zc.containsMouse ? Couleurs.accentDoux : Couleurs.gris2
        border.width: 1
        border.color: zc.containsMouse ? Couleurs.accentBord : Couleurs.bordureSubtile
        Behavior on color { enabled: !Reglages.sobre; ColorAnimation { duration: 120 } }
        Ico {
            anchors.centerIn: parent
            nom: "tune"; taille: 15
            color: zc.containsMouse ? Couleurs.accent : Couleurs.texteSec
        }
        MouseArea {
            id: zc
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: entete.ouvrirControle()
        }
        Accessible.role: Accessible.Button
        Accessible.name: Reglages.t("Centre de contrôle", "Control Center")
    }

    // Séparateur discret sous l'en-tête
    Rectangle {
        anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom
        height: 1
        color: Couleurs.separateur
    }
}

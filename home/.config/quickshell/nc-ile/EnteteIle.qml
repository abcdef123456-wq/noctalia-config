// Bandeau d'en-tête minimal de l'île ouverte : s'efface automatiquement lorsqu'une seule vue existe,
// et adapte entièrement son dessin à l'archétype du thème actif (Apple, Brutaliste, Terminal, Éditorial, Néon, Noctalia).
import QtQuick

Item {
    id: entete
    property var pages: []
    property string active: ""
    property int nonLues: 0
    signal choisir(string nom)
    signal ouvrirControle(Item bouton)

    readonly property bool multiPages: (pages ? pages.length : 0) > 1
    implicitHeight: multiPages ? 34 : 0
    visible: multiPages

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

    readonly property var pagesMontrees: {
        if (!pages || pages.length <= 3) return pages || []
        const idx = Math.max(0, pages.indexOf(active))
        const debut = Math.max(0, Math.min(pages.length - 3, idx - 1))
        return pages.slice(debut, debut + 3)
    }

    // Fond segmenté discret uniquement pour Apple / Noctalia
    Rectangle {
        visible: Couleurs.styleApple || Couleurs.styleModerne
        x: onglets.x - 3; y: 2
        width: onglets.implicitWidth + 6; height: 28
        radius: Couleurs.rayon(14, width, height)
        color: Couleurs.surfaceDouce
        border.width: 1; border.color: Qt.alpha(Couleurs.voile, Couleurs.sombre ? 0.05 : 0.08)
    }

    Row {
        id: onglets
        anchors.left: parent.left
        anchors.leftMargin: (Couleurs.styleApple || Couleurs.styleModerne) ? 3 : 0
        anchors.verticalCenter: parent.verticalCenter
        spacing: (Couleurs.styleEditorial || Couleurs.styleNeon) ? 14 : (Couleurs.styleBrut || Couleurs.styleTerminal ? 4 : 2)
        readonly property real largeurOnglet: entete.pagesMontrees.length === 0 ? 0 : Math.max(0,
            (entete.width - boutonControle.width - 12 - spacing * (entete.pagesMontrees.length - 1)) / entete.pagesMontrees.length)

        Repeater {
            model: entete.pagesMontrees
            Item {
                id: tab
                required property string modelData
                required property int index
                readonly property bool estActif: modelData === entete.active
                readonly property var info: entete.meta(modelData)
                readonly property bool avecBadge: modelData === "notifications" && entete.nonLues > 0
                readonly property bool estSouligne: Couleurs.styleEditorial || Couleurs.styleNeon
                readonly property bool estBloc: Couleurs.styleBrut || Couleurs.styleTerminal
                objectName: "nc-ile-onglet-" + modelData
                width: Math.min(126, onglets.largeurOnglet, titreOnglet.implicitWidth + largeurAccessoires + (estSouligne ? 6 : 16))
                readonly property real largeurAccessoires: (iconeOnglet.visible ? iconeOnglet.width + contenuTab.spacing : 0)
                    + (avecBadge ? 5 + contenuTab.spacing : 0)
                height: 26

                // Fond d'onglet selon l'archétype
                Rectangle {
                    anchors.fill: parent
                    visible: !tab.estSouligne
                    radius: Couleurs.rayon(tab.estBloc ? 2 : 12, width, height)
                    color: tab.estActif
                           ? (tab.estBloc ? Couleurs.accent : (Couleurs.sombre ? Couleurs.gris3 : Couleurs.fond))
                           : (zt.containsMouse ? Qt.alpha(Couleurs.voile, 0.08) : "transparent")
                    border.width: tab.estBloc && !tab.estActif ? 1 : 0
                    border.color: Couleurs.bordureSubtile
                    Behavior on color { enabled: !Reglages.sobre; ColorAnimation { duration: 110 } }
                }

                // Soulignement raffiné pour Éditorial & Néon
                Rectangle {
                    visible: tab.estSouligne && tab.estActif
                    anchors.bottom: parent.bottom
                    anchors.horizontalCenter: parent.horizontalCenter
                    width: parent.width; height: 2
                    radius: Couleurs.rayon(1, width, height)
                    color: Couleurs.accent
                }

                Row {
                    id: contenuTab
                    anchors.centerIn: parent
                    spacing: 5
                    Ico {
                        id: iconeOnglet
                        visible: !Couleurs.styleTerminal && !Couleurs.styleEditorial
                        anchors.verticalCenter: parent.verticalCenter
                        nom: tab.info.ico
                        taille: 13
                        color: tab.estActif
                               ? (tab.estBloc ? Couleurs.surAccent : Couleurs.accent)
                               : Couleurs.texteSec
                    }
                    Texte {
                        id: titreOnglet
                        width: Math.max(0, Math.min(implicitWidth, tab.width - tab.largeurAccessoires - 6))
                        anchors.verticalCenter: parent.verticalCenter
                        text: Couleurs.styleTerminal
                              ? ("[" + tab.info.nom.toUpperCase() + "]")
                              : (Couleurs.styleBrut
                                 ? ("0" + (tab.index + 1) + " " + tab.info.nom.toUpperCase())
                                 : tab.info.nom)
                        font.pixelSize: (Couleurs.styleTerminal || Couleurs.styleBrut) ? 10 : 12
                        font.weight: tab.estActif ? Font.DemiBold : Font.Medium
                        font.letterSpacing: (Couleurs.styleTerminal || Couleurs.styleBrut) ? 0.6 : 0
                        color: tab.estActif
                               ? (tab.estBloc ? Couleurs.surAccent : Couleurs.texte)
                               : (zt.containsMouse ? Couleurs.texteDoux : Couleurs.texteSec)
                    }
                    Rectangle {
                        visible: tab.avecBadge
                        anchors.verticalCenter: parent.verticalCenter
                        width: 5; height: 5; radius: width / 2
                        color: tab.estActif && tab.estBloc ? Couleurs.surAccent : Couleurs.accent
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

    // Accès rapide au Centre de contrôle à droite de l'en-tête
    Rectangle {
        id: boutonControle
        objectName: "nc-ile-vers-controle"
        anchors.right: parent.right
        anchors.verticalCenter: parent.verticalCenter
        width: 26; height: 26
        radius: Couleurs.rayon((Couleurs.styleBrut || Couleurs.styleTerminal) ? 2 : 13, width, height)
        color: zc.containsMouse ? Couleurs.surfaceActive : Couleurs.surfaceDouce
        border.width: (Couleurs.styleBrut || Couleurs.styleTerminal || Couleurs.styleNeon) ? 1 : 0
        border.color: zc.containsMouse ? Couleurs.accent : Couleurs.bordureSubtile
        Behavior on color { enabled: !Reglages.sobre; ColorAnimation { duration: 110 } }
        Ico {
            anchors.centerIn: parent
            nom: "tune"; taille: 14
            color: zc.containsMouse ? Couleurs.texteSurSurfaceActive : Couleurs.texteSec
        }
        MouseArea {
            id: zc
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: entete.ouvrirControle(boutonControle)
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

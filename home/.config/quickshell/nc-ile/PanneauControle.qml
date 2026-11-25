// Panneau Centre de contrôle dédié (Super + C ; icônes de la barre ; bouton « Centre de contrôle » de l'île).
// Regroupe tous les réglages rapides et panneaux de détails retirés de l'île pour garder l'île sur l'extrême essentiel :
// connexions (Wi-Fi/Ethernet, Bluetooth, VPN, Concentration), options rapides (Nuit, Café, Mode jeu, Cloud/IA),
// glissières (Volume, Luminosité), profils d'énergie, et sous-vues intégrées (Réseau, Bluetooth, Son, Système,
// Batterie, Santé, Météo, Agenda, Presse-papiers, Minuteur, Fenêtres).
// Entièrement adapté au thème actif (Couleurs, Mouvement, flou Hyprland nc-controle).
import QtQuick
import QtQuick.Controls
import Quickshell
import Quickshell.Wayland
import Quickshell.Hyprland
import Quickshell.Services.UPower

PanelWindow {
    id: fen
    property real hautReserve: Gabarit.barre
    signal fermer()
    signal ouvrirThemes()

    readonly property var mouv: Mouvement.pourEcran(screen ? screen.name : "")
    readonly property string section: Etat.controleSection || "accueil"
    readonly property bool surAccueil: section === "accueil"
    readonly property var s: Etat.sys || ({})
    readonly property bool filaire: s.filaire !== undefined
    readonly property bool wifiActif: filaire ? s.filaire === "1" : Etat.valeur("wifi", s.wifi) === "on"
    readonly property bool btActif: Etat.valeur("bluetooth", s.bluetooth) === "on"
    readonly property bool cloudDispo: CloudEtat.actif && CloudEtat.associe

    anchors { top: true; bottom: true; left: true; right: true }
    exclusionMode: ExclusionMode.Ignore
    color: "transparent"
    WlrLayershell.namespace: "nc-controle"
    WlrLayershell.layer: WlrLayer.Overlay
    WlrLayershell.keyboardFocus: WlrKeyboardFocus.OnDemand

    // Métadonnées des sous-vues intégrées (titre, icône, section correspondante dans Parametres.qml)
    function metaSection(id) {
        var m = ({
            reseau:        { ico: "wifi",                  fr: "Réseau",          en: "Network",       reglage: "Île" },
            bluetooth:     { ico: "bluetooth",             fr: "Bluetooth",       en: "Bluetooth",     reglage: "Son et luminosité" },
            son:           { ico: "volume_up",             fr: "Son",             en: "Sound",         reglage: "Son et luminosité" },
            systeme:       { ico: "monitoring",            fr: "Système",         en: "System",        reglage: "Mises à jour" },
            charge:        { ico: "battery_charging_full", fr: "Batterie",        en: "Battery",       reglage: "Énergie" },
            sante:         { ico: "thermostat",            fr: "Santé matérielle",en: "System Health", reglage: "Île" },
            concentration: { ico: "do_not_disturb_on",     fr: "Concentration",   en: "Focus",         reglage: "Notifications" },
            meteo:         { ico: "partly_cloudy_day",     fr: "Météo",           en: "Weather",       reglage: "Île" },
            calendrier:    { ico: "calendar_month",        fr: "Calendrier",      en: "Calendar",      reglage: "Intégration Google" },
            presse:        { ico: "content_paste",         fr: "Presse-papiers",  en: "Clipboard",     reglage: "Île" },
            minuteur:      { ico: "timer",                 fr: "Minuteur",        en: "Timer",         reglage: "Île" },
            fenetres:      { ico: "view_agenda",           fr: "Fenêtres",        en: "Windows",       reglage: "Fenêtres" },
            jeu:           { ico: "sports_esports",        fr: "Mode jeu",        en: "Game Mode",     reglage: "Énergie" }
        })[id]
        return m ? { ico: m.ico, nom: Reglages.t(m.fr, m.en), reglage: m.reglage }
                 : { ico: "tune", nom: Reglages.t("Centre de contrôle", "Control Center"), reglage: "Île" }
    }

    // Liste des outils rapides en bas du panneau (dynamique selon le matériel)
    readonly property var outils: {
        var o = [
            { id: "systeme", ico: "monitoring", fr: "Système", en: "System" }
        ]
        if (Etat.batteriePc) o.push({ id: "charge", ico: Etat.enCharge ? "bolt" : "battery_full", fr: "Batterie", en: "Battery" })
        if (Etat.capteursSante) o.push({ id: "sante", ico: "thermostat", fr: "Santé", en: "Health" })
        o.push({ id: "meteo", ico: Etat.meteo.icone || "partly_cloudy_day", fr: "Météo", en: "Weather" })
        o.push({ id: "calendrier", ico: "calendar_month", fr: "Agenda", en: "Calendar" })
        o.push({ id: "presse", ico: "content_paste", fr: "Presse", en: "Clipboard" })
        o.push({ id: "minuteur", ico: "timer", fr: "Minuteur", en: "Timer" })
        o.push({ id: "fenetres", ico: "view_agenda", fr: "Fenêtres", en: "Windows" })
        return o
    }

    // Entrée animée légère
    property real progres: 0
    Component.onCompleted: {
        progres = 1
        Etat.lire()
        Etat.lireLuminosite(false)
        Etat.lirePage()
        if (cloudDispo) CloudEtat.lireQuota()
    }
    Behavior on progres { enabled: fen.mouv.actif; NumberAnimation { duration: Math.max(120, fen.mouv.duree * 0.78); easing.type: Easing.OutCubic } }

    // Fond transparent cliquable pour fermer le panneau au clic à l'extérieur
    Item {
        id: racineControle
        objectName: "nc-controle-racine"
        anchors.fill: parent
        focus: true
        Keys.onEscapePressed: {
            if (!fen.surAccueil) Etat.allerControle("accueil")
            else fen.fermer()
        }

        MouseArea {
            anchors.fill: parent
            acceptedButtons: Qt.AllButtons
            onClicked: fen.fermer()
        }

        // Lueur douce optionnelle autour du panneau (quand ILE_LUEUR=oui)
        Repeater {
            model: Couleurs.lueur ? [10, 6, 3] : []
            Rectangle {
                required property int modelData
                x: carte.x - modelData; y: carte.y - modelData
                width: carte.width + 2 * modelData; height: carte.height + 2 * modelData
                radius: carte.radius + modelData
                color: Qt.alpha(Couleurs.accent, 0.06 + (10 - modelData) * 0.01)
                opacity: fen.progres
            }
        }

        // Contour dégradé / discret adapté au thème
        Rectangle {
            id: contourPanneau
            readonly property real e: Couleurs.aContour ? Math.max(1, Couleurs.epaisseur) : 0
            visible: e > 0
            x: carte.x - e; y: carte.y - e
            width: carte.width + 2 * e; height: carte.height + 2 * e
            radius: carte.radius + e
            opacity: fen.progres
            gradient: Gradient {
                orientation: Gradient.Horizontal
                GradientStop { position: 0; color: Couleurs.contour === "discret" ? Qt.alpha(Couleurs.accent, 0.45) : Couleurs.degrade[0] }
                GradientStop { position: 0.5; color: Couleurs.contour === "discret" ? Qt.alpha(Couleurs.accent, 0.45) : Couleurs.degrade[1] }
                GradientStop { position: 1; color: Couleurs.contour === "discret" ? Qt.alpha(Couleurs.accent, 0.45) : Couleurs.degrade[2] }
            }
        }

        // Carte principale du Centre de contrôle (ancrée en haut à droite sous la barre)
        Rectangle {
            id: carte
            objectName: "nc-controle-carte"
            readonly property real hauteurMax: Math.max(360, racineControle.height - fen.hautReserve - 24)
            readonly property real hauteurContenu: fen.surAccueil ? (blocAccueil.implicitHeight + 82) : Math.max(320, Math.min(580, (chargeurSousVue.item ? (chargeurSousVue.item.implicitHeight || 420) : 420) + 86))
            width: Math.min(432, racineControle.width - 24)
            height: Math.min(hauteurMax, hauteurContenu)
            x: racineControle.width - width - 12
            y: fen.hautReserve + 8 - (1 - fen.progres) * 14
            opacity: fen.progres
            radius: Couleurs.rayon(24, width, height)
            color: Qt.alpha(Couleurs.fond, Couleurs.opacitePanneau)
            border.width: contourPanneau.visible ? 0 : 1
            border.color: Couleurs.bordureSubtile
            clip: true

            Behavior on height { enabled: fen.mouv.actif; NumberAnimation { duration: 180; easing.type: Easing.OutCubic } }

            // Absorbe les clics à l'intérieur pour ne pas fermer le panneau
            MouseArea { anchors.fill: parent; z: -1 }

            // Bandeau d'en-tête
            Item {
                id: entete
                objectName: "nc-controle-entete"
                x: 16; y: 12; width: parent.width - 32; height: 38

                // Retour + titre de sous-vue (hors accueil)
                Row {
                    visible: !fen.surAccueil
                    anchors.left: parent.left; anchors.verticalCenter: parent.verticalCenter
                    spacing: 8

                    Rectangle {
                        objectName: "nc-controle-retour"
                        width: 30; height: 30
                        radius: Couleurs.rayon(10, width, height)
                        color: zRet.containsMouse ? Couleurs.gris3 : Couleurs.gris2
                        Ico { anchors.centerIn: parent; nom: "arrow_back"; taille: 17; color: Couleurs.texte }
                        MouseArea {
                            id: zRet
                            anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                            onClicked: Etat.allerControle("accueil")
                        }
                        Accessible.role: Accessible.Button
                        Accessible.name: Reglages.t("Retour au centre de contrôle", "Back to Control Center")
                    }
                    Ico {
                        anchors.verticalCenter: parent.verticalCenter
                        nom: fen.metaSection(fen.section).ico
                        taille: 18; color: Couleurs.accent
                    }
                    Texte {
                        objectName: "nc-controle-titre-section"
                        anchors.verticalCenter: parent.verticalCenter
                        text: fen.metaSection(fen.section).nom
                        font.pixelSize: 15; font.weight: Font.Bold
                    }
                }

                // En-tête de l'accueil : icône + titre + pastille batterie
                Row {
                    visible: fen.surAccueil
                    anchors.left: parent.left; anchors.verticalCenter: parent.verticalCenter
                    spacing: 8

                    Rectangle {
                        width: 30; height: 30
                        radius: Couleurs.rayon(10, width, height)
                        color: Couleurs.accentDoux
                        border.width: 1; border.color: Couleurs.accentBord
                        Ico { anchors.centerIn: parent; nom: "tune"; taille: 17; color: Couleurs.accent }
                    }
                    Texte {
                        objectName: "nc-controle-titre"
                        anchors.verticalCenter: parent.verticalCenter
                        text: Reglages.t("Centre de contrôle", "Control Center")
                        font.pixelSize: 15; font.weight: Font.Bold
                    }
                    Rectangle {
                        visible: Etat.batteriePc
                        anchors.verticalCenter: parent.verticalCenter
                        width: rowBat.implicitWidth + 14; height: 24
                        radius: height / 2
                        color: zBat.containsMouse ? Couleurs.gris3 : Couleurs.gris2
                        Row {
                            id: rowBat
                            anchors.centerIn: parent; spacing: 4
                            Ico {
                                anchors.verticalCenter: parent.verticalCenter
                                nom: Etat.enCharge ? "bolt" : "battery_full"; taille: 13
                                color: Etat.enCharge ? Couleurs.vert : (Etat.pourcent <= 20 ? Couleurs.rouge : Couleurs.texteSec)
                            }
                            Texte {
                                anchors.verticalCenter: parent.verticalCenter
                                text: Etat.pourcent + Reglages.t(" %", "%")
                                font.pixelSize: 11; font.weight: Font.DemiBold
                                font.features: ({ "tnum": 1 })
                            }
                        }
                        MouseArea {
                            id: zBat
                            anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                            onClicked: Etat.allerControle("charge")
                        }
                    }
                }

                // Actions rapides en haut à droite : Thèmes, Réglages, Session/Verrou
                Row {
                    anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter
                    spacing: 6

                    Rectangle {
                        objectName: "nc-controle-themes"
                        width: 30; height: 30; radius: width / 2
                        color: zTh.containsMouse ? Couleurs.accentDoux : Qt.alpha(Couleurs.carte, 0.7)
                        border.width: 1; border.color: Couleurs.bordureSubtile
                        Ico { anchors.centerIn: parent; nom: "palette"; taille: 16; color: zTh.containsMouse ? Couleurs.accent : Couleurs.texteSec }
                        MouseArea {
                            id: zTh; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                            onClicked: { fen.fermer(); fen.ouvrirThemes() }
                        }
                        Accessible.role: Accessible.Button
                        Accessible.name: Reglages.t("Thèmes du bureau", "Desktop themes")
                    }

                    BoutonReglages {
                        objectName: "nc-controle-reglages"
                        taille: 30
                        section: fen.metaSection(fen.section).reglage
                        aide: Reglages.t("Réglages du bureau", "Desktop settings")
                        onOuvert: fen.fermer()
                    }

                    Rectangle {
                        objectName: "nc-controle-session"
                        width: 30; height: 30; radius: width / 2
                        color: zPow.containsMouse ? Qt.alpha(Couleurs.rouge, 0.2) : Qt.alpha(Couleurs.carte, 0.7)
                        border.width: 1; border.color: Couleurs.bordureSubtile
                        Ico { anchors.centerIn: parent; nom: "power_settings_new"; taille: 16; color: zPow.containsMouse ? Couleurs.rouge : Couleurs.texteSec }
                        MouseArea {
                            id: zPow; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                            onClicked: { fen.fermer(); Quickshell.execDetached([Etat.bin + "nc-shell-msg", "session"]) }
                        }
                        Accessible.role: Accessible.Button
                        Accessible.name: Reglages.t("Verrouiller et veille", "Lock and sleep")
                    }
                }
            }

            Rectangle {
                id: ligneEntete
                anchors.top: entete.bottom; anchors.topMargin: 8
                anchors.left: parent.left; anchors.right: parent.right
                anchors.leftMargin: 16; anchors.rightMargin: 16
                height: 1; color: Couleurs.separateur
            }

            // ── Contenu principal : Tableau de bord (accueil) ──
            Flickable {
                id: defileAccueil
                visible: fen.surAccueil
                anchors.top: ligneEntete.bottom; anchors.topMargin: 10
                anchors.left: parent.left; anchors.right: parent.right
                anchors.bottom: parent.bottom
                anchors.leftMargin: 16; anchors.rightMargin: 16; anchors.bottomMargin: 14
                contentWidth: width
                contentHeight: blocAccueil.implicitHeight
                clip: true
                boundsBehavior: Flickable.StopAtBounds
                flickableDirection: Flickable.VerticalFlick
                ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

                Column {
                    id: blocAccueil
                    objectName: "nc-controle-accueil"
                    width: defileAccueil.width
                    spacing: 12

                    // 1. Grille Connexions & Modes (2 x 2)
                    Grid {
                        width: parent.width
                        columns: 2; spacing: 8
                        readonly property real largeurTuile: Math.floor((width - spacing) / 2)

                        ControleTuile {
                            objectName: "nc-controle-tuile-reseau"
                            width: parent.largeurTuile
                            icone: fen.filaire ? "lan" : (fen.wifiActif ? "wifi" : "wifi_off")
                            titre: fen.filaire ? "Ethernet" : "Wi-Fi"
                            sousTitre: fen.filaire
                                ? (fen.wifiActif ? Reglages.t("Connecté", "Connected") : Reglages.t("Débranché", "Unplugged"))
                                : (fen.wifiActif ? (fen.s.reseau || Reglages.t("Activé", "On")) : Reglages.t("Désactivé", "Off"))
                            actif: fen.wifiActif
                            aDetails: !fen.filaire
                            onBasculer: if (!fen.filaire) Etat.inverser("wifi", ["noctalia", "msg", "wifi-toggle"])
                            onOuvrirDetails: Etat.allerControle("reseau")
                        }

                        ControleTuile {
                            objectName: "nc-controle-tuile-bluetooth"
                            width: parent.largeurTuile
                            icone: fen.btActif ? "bluetooth" : "bluetooth_disabled"
                            titre: "Bluetooth"
                            sousTitre: fen.btActif ? Reglages.t("Activé", "On") : Reglages.t("Désactivé", "Off")
                            actif: fen.btActif
                            aDetails: true
                            onBasculer: Etat.inverser("bluetooth", ["noctalia", "msg", "bluetooth-toggle"])
                            onOuvrirDetails: Etat.allerControle("bluetooth")
                        }

                        ControleTuile {
                            objectName: "nc-controle-tuile-concentration"
                            width: parent.largeurTuile
                            icone: Modes.pastille ? Modes.actifIcone : (Notifs.concentration ? "do_not_disturb_on" : "notifications")
                            titre: Reglages.t("Concentration", "Focus")
                            sousTitre: Modes.pastille ? (Modes.nomVisible || Reglages.t("Actif", "Active"))
                                                      : (Notifs.concentration ? Reglages.t("Ne pas déranger", "Do Not Disturb") : Reglages.t("Normal", "Off"))
                            actif: Notifs.concentration || Modes.pastille
                            couleurActive: Couleurs.violet
                            aDetails: true
                            onBasculer: Notifs.basculerConcentration()
                            onOuvrirDetails: Etat.allerControle("concentration")
                        }

                        ControleTuile {
                            objectName: "nc-controle-tuile-vpn"
                            width: parent.largeurTuile
                            icone: VpnEtat.indicateur ? "shield_lock" : "vpn_lock"
                            titre: "VPN"
                            sousTitre: VpnEtat.indicateur ? (VpnEtat.libelle || Reglages.t("Connecté", "Connected")) : Reglages.t("Inactif", "Off")
                            actif: VpnEtat.indicateur
                            couleurActive: Couleurs.vert
                            aDetails: true
                            onBasculer: { fen.fermer(); VpnEtat.ouvrirPanneau() }
                            onOuvrirDetails: { fen.fermer(); VpnEtat.ouvrirPanneau() }
                        }
                    }

                    // 2. Options rapides compactes (2 x 2)
                    Grid {
                        width: parent.width
                        columns: 2; spacing: 8
                        readonly property real largeurTuile: Math.floor((width - spacing) / 2)

                        ControleTuile {
                            objectName: "nc-controle-tuile-nuit"
                            width: parent.largeurTuile
                            compact: true
                            icone: "wb_twilight"
                            titre: Reglages.t("Nuit", "Night Shift")
                            sousTitre: Etat.nuit ? Reglages.t("Activée", "On") : Reglages.t("Arrêt", "Off")
                            actif: Etat.nuit
                            couleurActive: Couleurs.orange
                            onBasculer: { Etat.nuit = !Etat.nuit; Etat.faire(["noctalia", "msg", "nightlight-force-toggle"]) }
                        }

                        ControleTuile {
                            objectName: "nc-controle-tuile-cafe"
                            width: parent.largeurTuile
                            compact: true
                            icone: Etat.cafe ? "coffee" : "coffee_maker"
                            titre: Reglages.t("Caféine", "Caffeine")
                            sousTitre: Etat.cafe ? Reglages.t("Écran actif", "Awake") : Reglages.t("Veille auto", "Auto sleep")
                            actif: Etat.cafe
                            couleurActive: Couleurs.orange
                            onBasculer: Etat.basculerCafe()
                        }

                        ControleTuile {
                            objectName: "nc-controle-tuile-jeu"
                            width: parent.largeurTuile
                            compact: true
                            icone: "sports_esports"
                            titre: Reglages.t("Mode jeu", "Game Mode")
                            sousTitre: Etat.jeu ? Reglages.t("Performances", "Active") : Reglages.t("Arrêt", "Off")
                            actif: Etat.jeu
                            couleurActive: Couleurs.rose
                            aDetails: true
                            onBasculer: Etat.faire(["hyprctl", "eval", "nc.mode_jeu()"])
                            onOuvrirDetails: Etat.allerControle("jeu")
                        }

                        ControleTuile {
                            objectName: "nc-controle-tuile-cloud"
                            width: parent.largeurTuile
                            compact: true
                            icone: fen.cloudDispo ? (CloudEtat.envoie ? "cloud_upload" : "cloud") : "auto_awesome"
                            titre: fen.cloudDispo ? "Cloud JARVIS" : Reglages.t("IA du bureau", "Desktop AI")
                            sousTitre: fen.cloudDispo
                                ? (CloudEtat.envoie ? Reglages.t("Envoi…", "Uploading…") : (CloudEtat.quotaTexte || Reglages.t("Ouvrir", "Open")))
                                : (Reglages.iaCoupee ? Reglages.t("Coupée", "Off") : Reglages.t("Active", "Active"))
                            actif: fen.cloudDispo ? (CloudEtat.envoie || (CloudEtat.quotaTexte !== "" && !CloudEtat.quotaVieux)) : !Reglages.iaCoupee
                            onBasculer: {
                                if (fen.cloudDispo) { fen.fermer(); CloudEtat.ouvrirPanneau() }
                                else {
                                    fen.fermer()
                                    Quickshell.execDetached([Etat.bin + "nc-reglages", "fenetre", "Intelligence artificielle"])
                                }
                            }
                        }
                    }

                    // 3. Carte Glissières (Volume & Luminosité)
                    Rectangle {
                        width: parent.width
                        height: colGlissieres.implicitHeight + 20
                        radius: Couleurs.rayon(16, width, height)
                        color: Couleurs.carte
                        border.width: 1; border.color: Couleurs.bordureSubtile

                        Column {
                            id: colGlissieres
                            anchors.left: parent.left; anchors.right: parent.right
                            anchors.verticalCenter: parent.verticalCenter
                            anchors.margins: 12
                            spacing: 6

                            ControleGlissiere {
                                objectName: "nc-controle-volume"
                                width: parent.width
                                icone: Etat.muet ? "volume_off" : (Etat.volume < 0.34 ? "volume_mute" : (Etat.volume < 0.67 ? "volume_down" : "volume_up"))
                                titre: Reglages.t("Volume", "Volume")
                                valeur: Etat.volume
                                muet: Etat.muet
                                aDetails: true
                                onChanger: v => Etat.reglerVolume(v)
                                onBasculerMuet: Etat.basculerMuet()
                                onOuvrirDetails: Etat.allerControle("son")
                            }

                            Rectangle { width: parent.width; height: 1; color: Couleurs.separateur }

                            ControleGlissiere {
                                objectName: "nc-controle-luminosite"
                                width: parent.width
                                icone: "light_mode"
                                titre: Reglages.t("Luminosité", "Brightness")
                                valeur: Etat.luminosite
                                onChanger: v => Etat.reglerLuminosite(v)
                                onBasculerMuet: Etat.reglerLuminosite(Etat.luminosite > 0.5 ? 0.3 : 0.85)
                            }
                        }
                    }

                    // 4. Profils d'énergie (bandeau segmenté)
                    Rectangle {
                        objectName: "nc-controle-energie"
                        visible: !Etat.profilsAbsents
                        width: parent.width; height: 44
                        radius: Couleurs.rayon(14, width, height)
                        color: Couleurs.carte
                        border.width: 1; border.color: Couleurs.bordureSubtile

                        Row {
                            anchors.fill: parent; anchors.margins: 4
                            spacing: 4
                            readonly property var listeProfils: Etat.performanceDisponible
                                ? [{ p: PowerProfile.PowerSaver, ico: "eco", fr: "Économie", en: "Saver", c: Couleurs.vert },
                                   { p: PowerProfile.Balanced,   ico: "balance", fr: "Équilibré", en: "Balanced", c: Couleurs.accent },
                                   { p: PowerProfile.Performance,ico: "bolt", fr: "Perf", en: "Perf", c: Couleurs.orange }]
                                : [{ p: PowerProfile.PowerSaver, ico: "eco", fr: "Économie", en: "Saver", c: Couleurs.vert },
                                   { p: PowerProfile.Balanced,   ico: "balance", fr: "Équilibré", en: "Balanced", c: Couleurs.accent }]

                            Repeater {
                                model: parent.listeProfils
                                Rectangle {
                                    id: segProfil
                                    required property var modelData
                                    readonly property bool estActif: Etat.profil === modelData.p
                                    width: Math.floor((parent.width - parent.spacing * (parent.listeProfils.length - 1)) / parent.listeProfils.length)
                                    height: parent.height
                                    radius: Couleurs.rayon(10, width, height)
                                    color: estActif ? modelData.c : (zP.containsMouse ? Couleurs.gris2 : "transparent")
                                    Behavior on color { enabled: !Reglages.sobre; ColorAnimation { duration: 120 } }

                                    Row {
                                        anchors.centerIn: parent; spacing: 5
                                        Ico {
                                            anchors.verticalCenter: parent.verticalCenter
                                            nom: segProfil.modelData.ico; taille: 15
                                            color: segProfil.estActif ? Couleurs.surCouleur : Couleurs.texteSec
                                        }
                                        Texte {
                                            anchors.verticalCenter: parent.verticalCenter
                                            text: Reglages.t(segProfil.modelData.fr, segProfil.modelData.en)
                                            font.pixelSize: 12; font.weight: segProfil.estActif ? Font.DemiBold : Font.Medium
                                            color: segProfil.estActif ? Couleurs.surCouleur : Couleurs.texte
                                        }
                                    }
                                    MouseArea {
                                        id: zP; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                                        onClicked: Etat.choisirProfil(segProfil.modelData.p)
                                    }
                                    Accessible.role: Accessible.Button
                                    Accessible.name: Reglages.t(segProfil.modelData.fr, segProfil.modelData.en)
                                }
                            }
                        }
                    }

                    // 5. Outils & panneaux détaillés (Système, Batterie, Santé, Météo, Agenda, Presse, Minuteur, Fenêtres)
                    Column {
                        width: parent.width; spacing: 6

                        Texte {
                            text: Reglages.t("Panneaux & outils", "Panels & tools")
                            secondaire: true; font.pixelSize: 11; font.weight: Font.DemiBold
                        }

                        Flow {
                            width: parent.width; spacing: 6
                            Repeater {
                                model: fen.outils
                                Rectangle {
                                    id: puceOutil
                                    required property var modelData
                                    objectName: "nc-controle-outil-" + modelData.id
                                    width: Math.floor((parent.width - 18) / 4)
                                    height: 48
                                    radius: Couleurs.rayon(12, width, height)
                                    color: zO.containsMouse ? Couleurs.carteSurvol : Couleurs.carte
                                    border.width: 1; border.color: zO.containsMouse ? Couleurs.accentBord : Couleurs.bordureSubtile
                                    Behavior on color { enabled: !Reglages.sobre; ColorAnimation { duration: 110 } }

                                    Column {
                                        anchors.centerIn: parent; spacing: 2
                                        Ico {
                                            anchors.horizontalCenter: parent.horizontalCenter
                                            nom: puceOutil.modelData.ico; taille: 17
                                            color: zO.containsMouse ? Couleurs.accent : Couleurs.texte
                                        }
                                        Texte {
                                            anchors.horizontalCenter: parent.horizontalCenter
                                            text: puceOutil.modelData.id === "meteo" && Etat.meteo.temp !== undefined
                                                  ? Etat.meteo.temp + "°"
                                                  : (puceOutil.modelData.id === "minuteur" && Etat.minuteurFin > 0
                                                     ? Etat.duree(Etat.minuteurReste)
                                                     : Reglages.t(puceOutil.modelData.fr, puceOutil.modelData.en))
                                            font.pixelSize: 10; font.weight: Font.Medium
                                            secondaire: !zO.containsMouse
                                        }
                                    }
                                    MouseArea {
                                        id: zO; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                                        onClicked: Etat.allerControle(puceOutil.modelData.id)
                                    }
                                    Accessible.role: Accessible.Button
                                    Accessible.name: Reglages.t(puceOutil.modelData.fr, puceOutil.modelData.en)
                                }
                            }
                        }
                    }
                }
            }

            // ── Sous-vue détaillée intégrée (Wi-Fi, Bluetooth, Son, Système, Batterie, Santé, Météo, Presse, Minuteur…) ──
            Item {
                id: zoneSousVue
                objectName: "nc-controle-sousvue"
                visible: !fen.surAccueil
                anchors.top: ligneEntete.bottom; anchors.topMargin: 10
                anchors.left: parent.left; anchors.right: parent.right
                anchors.bottom: parent.bottom
                anchors.leftMargin: 16; anchors.rightMargin: 16; anchors.bottomMargin: 14

                Loader {
                    id: chargeurSousVue
                    anchors.fill: parent
                    active: !fen.surAccueil
                    sourceComponent: ({
                        reseau: sReseau,
                        bluetooth: sBluetooth,
                        son: sSon,
                        systeme: sSysteme,
                        charge: sCharge,
                        sante: sSante,
                        concentration: sConcentration,
                        meteo: sMeteo,
                        calendrier: sCalendrier,
                        presse: sPresse,
                        minuteur: sMinuteur,
                        fenetres: sFenetres,
                        jeu: sJeu
                    })[fen.section] || null
                }
            }

            Component { id: sReseau; PageListe { mode: "wifi" } }
            Component { id: sBluetooth; PageListe { mode: "bluetooth" } }
            Component { id: sSon; Son {} }
            Component { id: sSysteme; Systeme {} }
            Component { id: sCharge; Charge {} }
            Component { id: sSante; Sante {} }
            Component { id: sConcentration; PageConcentration {} }
            Component { id: sMeteo; Meteo {} }
            Component { id: sCalendrier; Calendrier {} }
            Component { id: sPresse; Presse {} }
            Component { id: sMinuteur; Minuteur {} }
            Component { id: sFenetres; Fenetres {} }
            Component { id: sJeu; Jeu {} }
        }
    }
}

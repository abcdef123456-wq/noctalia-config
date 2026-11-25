// Centre de contrôle : tableau de bord et tiroirs indépendants de l'île.
import QtQuick
import QtQuick.Controls
import Quickshell
import Quickshell.Wayland
import Quickshell.Hyprland
import Quickshell.Widgets
import Quickshell.Services.UPower
import "DispositionPanneaux.js" as Disposition

PanelWindow {
    id: fen
    property string bord: "top"          // "top" | "bottom" | "left" | "right"
    property real gaucheReserve: 0
    property real hautReserve: Gabarit.barre
    property real droiteReserve: 0
    property real basReserve: 0
    property var ancre: null
    property var ancreInterne: null
    property Item boutonRetour: null
    signal fermer()
    signal ouvrirThemes()

    readonly property var mouv: Mouvement.pourEcran(screen ? screen.name : "")
    readonly property string section: Etat.controleSection || "accueil"
    readonly property bool surAccueil: section === "accueil"
    readonly property var s: Etat.sys || ({})
    readonly property real progresMedia: Etat.lecteur && Etat.lecteur.length > 0
        ? Math.max(0, Math.min(1, Etat.lecteur.position / Etat.lecteur.length)) : 0
    readonly property bool filaire: s.filaire !== undefined
    readonly property bool wifiActif: filaire ? s.filaire === "1" : Etat.valeur("wifi", s.wifi) === "on"
    readonly property bool btActif: Etat.valeur("bluetooth", s.bluetooth) === "on"
    readonly property bool cloudDispo: CloudEtat.actif && CloudEtat.associe
    readonly property bool estBrut: Couleurs.styleBrut || Couleurs.styleTerminal
    readonly property bool estEditorial: Couleurs.styleEditorial
    readonly property bool estNeon: Couleurs.styleNeon
    readonly property bool estApple: Couleurs.styleApple

    anchors { top: true; bottom: true; left: true; right: true }
    exclusionMode: ExclusionMode.Ignore
    color: "transparent"
    WlrLayershell.namespace: "nc-controle"
    WlrLayershell.layer: WlrLayer.Overlay
    WlrLayershell.keyboardFocus: WlrKeyboardFocus.Exclusive

    function metaSection(id) {
        var m = ({
            reseau:        { ico: "wifi",                  fr: "Réseau",           en: "Network",       reglage: "Île" },
            bluetooth:     { ico: "bluetooth",             fr: "Bluetooth",        en: "Bluetooth",     reglage: "Son et luminosité" },
            son:           { ico: "volume_up",             fr: "Audio & mixeur",   en: "Audio & mixer", reglage: "Son et luminosité" },
            systeme:       { ico: "monitoring",            fr: "Système",          en: "System",        reglage: "Mises à jour" },
            charge:        { ico: "battery_charging_full", fr: "Batterie",         en: "Battery",       reglage: "Énergie" },
            sante:         { ico: "thermostat",            fr: "Santé matérielle", en: "System Health", reglage: "Île" },
            concentration: { ico: "do_not_disturb_on",     fr: "Concentration",    en: "Focus",         reglage: "Notifications" },
            meteo:         { ico: "partly_cloudy_day",     fr: "Météo",            en: "Weather",       reglage: "Île" },
            calendrier:    { ico: "calendar_month",        fr: "Agenda",           en: "Calendar",      reglage: "Intégration Google" },
            presse:        { ico: "content_paste",         fr: "Presse-papiers",   en: "Clipboard",     reglage: "Île" },
            minuteur:      { ico: "timer",                 fr: "Minuteur",         en: "Timer",         reglage: "Île" },
            fenetres:      { ico: "view_agenda",           fr: "Fenêtres",         en: "Windows",       reglage: "Fenêtres" },
            jeu:           { ico: "sports_esports",        fr: "Mode jeu",         en: "Game Mode",     reglage: "Énergie" }
        })[id]
        return m ? { ico: m.ico, nom: Reglages.t(m.fr, m.en), reglage: m.reglage }
                 : { ico: "tune", nom: Reglages.t("Centre de contrôle", "Control Center"), reglage: "" }
    }

    readonly property var outils: {
        var o = [{ id: "systeme", ico: "monitoring", fr: "Système", en: "System" }]
        if (Etat.batteriePc) o.push({ id: "charge", ico: Etat.enCharge ? "bolt" : "battery_full", fr: "Batterie", en: "Battery" })
        if (Etat.capteursSante) o.push({ id: "sante", ico: "thermostat", fr: "Santé", en: "Health" })
        o.push({ id: "meteo", ico: Etat.meteo.icone || "partly_cloudy_day", fr: "Météo", en: "Weather" })
        o.push({ id: "calendrier", ico: "calendar_month", fr: "Agenda", en: "Calendar" })
        if (PressePapiers.active && !Partage.silence)
            o.push({ id: "presse", ico: "content_paste", fr: "Presse-papiers", en: "Clipboard" })
        o.push({ id: "minuteur", ico: "timer", fr: "Minuteur", en: "Timer" })
        o.push({ id: "fenetres", ico: "view_agenda", fr: "Fenêtres", en: "Windows" })
        return o
    }

    // Clic à l'extérieur : referme le panneau
    MouseArea {
        anchors.fill: parent
        onClicked: fen.fermer()
    }

    // Animation d'apparition fluide orientée depuis le bord actif
    property real entree: 0
    Component.onCompleted: {
        entree = 1
        panneau.forceActiveFocus()
    }
    onAncreChanged: { ancreInterne = null; boutonRetour = null }
    onSectionChanged: {
        if (section === "accueil") {
            ancreInterne = null
            const bouton = boutonRetour
            boutonRetour = null
            if (bouton) {
                Qt.callLater(() => { if (fen.surAccueil && bouton && bouton.visible) bouton.forceActiveFocus() })
                return
            }
        }
        panneau.forceActiveFocus()
    }
    function ouvrirWidget(section, bouton) {
        boutonRetour = bouton
        ancreInterne = Etat.ancreControle(bouton)
        Etat.allerControle(section)
    }
    Behavior on entree {
        enabled: !Reglages.sobre && fen.mouv.actif
        NumberAnimation { duration: Math.min(220, fen.mouv.duree); easing.type: Easing.OutCubic }
    }

    // ── Carte principale du Centre de contrôle ancrée dynamiquement au bord actif ──
    Item {
        id: panneau
        objectName: "nc-controle-panneau"
        focus: true
        readonly property real margeGauche: Math.max(0, fen.gaucheReserve) + 12
        readonly property real margeDroite: Math.max(0, fen.droiteReserve) + 12
        readonly property real margeHaute: Math.max(0, fen.hautReserve) + 12
        readonly property real margeBasse: Math.max(0, fen.basReserve) + 12
        readonly property real largeurCible: Math.max(0, Math.min(392, fen.width - margeGauche - margeDroite))
        readonly property real hauteurMax: Math.max(0, fen.height - margeHaute - margeBasse)
        readonly property real hauteurVoulue: fen.surAccueil
            ? Math.min(hauteurMax, Math.max(410, blocAccueil.implicitHeight + entete.height + 44))
            : Math.min(hauteurMax, 520)

        readonly property var placement: Disposition.placerControle(
            fen.surAccueil ? fen.ancre : fen.ancreInterne ?? fen.ancre,
            !fen.surAccueil && fen.ancreInterne ? "" : fen.bord, largeurCible, hauteurVoulue,
            margeGauche, margeHaute, fen.width - margeDroite, fen.height - margeBasse, fen.surAccueil)
        // La hauteur naturelle du tableau de bord dépend de sa grille ; ne pas reboucler via sa largeur.
        width: fen.surAccueil ? largeurCible : placement.largeur
        height: placement.hauteur

        readonly property real decalage: (1 - fen.entree) * 16

        x: placement.x + (placement.bord === "left" ? -decalage : (placement.bord === "right" ? decalage : 0))
        y: placement.y + (placement.bord === "bottom" ? decalage : (placement.bord === "top" ? -decalage : 0))
        opacity: fen.entree

        // Raccourcis clavier immédiats (focus exclusif Wayland)
        Keys.priority: Keys.AfterItem
        Keys.onPressed: event => {
            if (event.modifiers !== Qt.NoModifier) return
            if (event.key === Qt.Key_Escape) {
                if (!fen.surAccueil) Etat.allerControle("accueil")
                else fen.fermer()
                event.accepted = true
            } else if (event.key === Qt.Key_Backspace && !fen.surAccueil) {
                Etat.allerControle("accueil")
                event.accepted = true
            } else if (fen.surAccueil && event.key === Qt.Key_Left) {
                Etat.reglerVolume(Math.max(0, Etat.volume - 0.05))
                event.accepted = true
            } else if (fen.surAccueil && event.key === Qt.Key_Right) {
                Etat.reglerVolume(Math.min(1, Etat.volume + 0.05))
                event.accepted = true
            } else if (fen.surAccueil && event.key === Qt.Key_M) {
                Etat.basculerMuet()
                event.accepted = true
            }
        }

        // Ombre portée douce derrière la carte (sauf Brutaliste/Terminal qui jouent sur la bordure nette)
        Rectangle {
            visible: !fen.estBrut
            anchors.fill: fond
            anchors.margins: -3
            radius: fond.radius + 3
            color: Qt.alpha("#000000", Couleurs.sombre ? 0.34 : 0.14)
        }

        // Contour dégradé / néon / accent extérieur
        Rectangle {
            visible: Couleurs.aContour || fen.estNeon
            anchors.fill: fond
            anchors.margins: -Couleurs.epaisseurBordureCarte
            radius: fond.radius + Couleurs.epaisseurBordureCarte
            gradient: Gradient {
                orientation: Gradient.Horizontal
                GradientStop { position: 0; color: Couleurs.contour === "discret" || fen.estNeon ? Qt.alpha(Couleurs.accent, 0.55) : Couleurs.degrade[0] }
                GradientStop { position: 0.5; color: Couleurs.contour === "discret" || fen.estNeon ? Qt.alpha(Couleurs.accent, 0.35) : Couleurs.degrade[1] }
                GradientStop { position: 1; color: Couleurs.contour === "discret" || fen.estNeon ? Qt.alpha(Couleurs.accent, 0.55) : Couleurs.degrade[2] }
            }
            opacity: fen.estNeon ? 0.85 : 0.72
        }

        // Surface principale adaptée à l'archétype du thème actif
        Rectangle {
            id: fond
            anchors.fill: parent
            radius: Couleurs.rayon(Couleurs.rayonPanneau, width, height)
            color: Qt.alpha(Couleurs.fond, Couleurs.opacitePanneau)
            border.width: (fen.estBrut || fen.estEditorial || !Couleurs.aContour) ? Couleurs.epaisseurBordureCarte : 1
            border.color: fen.estBrut ? Couleurs.accent : Couleurs.bordureSubtile
            clip: true

            // Finition supérieure par archétype (reflet verre Apple/Noctalia, ligne néon, sceau éditorial)
            Rectangle {
                visible: !fen.estBrut
                anchors.top: parent.top
                anchors.horizontalCenter: parent.horizontalCenter
                width: fen.estEditorial ? 44 : (fen.estNeon ? parent.width : Math.max(0, parent.width - parent.radius * 2))
                height: (fen.estNeon || fen.estEditorial) ? 2 : 1
                opacity: (fen.estApple || Couleurs.styleModerne) ? (Couleurs.sombre ? 0.18 : 0.30) : 0.90
                color: (fen.estApple || Couleurs.styleModerne) ? Couleurs.voile : Couleurs.accent
            }

            // Repères d'angle CRT / Terminal
            Repeater {
                model: Couleurs.styleTerminal ? 4 : 0
                Item {
                    required property int index
                    readonly property bool droite: index % 2 === 1
                    readonly property bool bas: index >= 2
                    x: droite ? parent.width - 14 : 4
                    y: bas ? parent.height - 14 : 4
                    width: 10; height: 10
                    Rectangle { width: 10; height: 2; y: bas ? 8 : 0; color: Couleurs.accent }
                    Rectangle { width: 2; height: 10; x: droite ? 8 : 0; color: Couleurs.accent }
                }
            }

            // Absorbe les clics dans le panneau pour ne pas déclencher le fond extérieur
            MouseArea { anchors.fill: parent }

            // ── En-tête du Centre de contrôle ──
            Item {
                id: entete
                anchors.top: parent.top; anchors.topMargin: 14
                anchors.left: parent.left; anchors.right: parent.right
                anchors.leftMargin: 16; anchors.rightMargin: 16
                height: 36

                Row {
                    width: actionsEntete.x - 8
                    anchors.left: parent.left; anchors.verticalCenter: parent.verticalCenter
                    spacing: 8

                    // Bouton retour quand on est dans un tiroir natif
                    Rectangle {
                        objectName: "nc-controle-retour"
                        visible: !fen.surAccueil
                        anchors.verticalCenter: parent.verticalCenter
                        width: 28; height: 28
                        radius: Couleurs.rayon(fen.estBrut ? 2 : 14, width, height)
                        color: zRet.contientPointeur ? Couleurs.surfaceActive : Couleurs.surfaceDouce
                        border.width: (fen.estBrut || fen.estEditorial) ? 1 : 0
                        border.color: Couleurs.bordureSubtile
                        Ico {
                            anchors.centerIn: parent; nom: "arrow_back"; taille: 16
                            color: zRet.contientPointeur ? Couleurs.texteSurSurfaceActive : Couleurs.texte
                        }
                        ControleAction {
                            id: zRet; anchors.fill: parent
                            text: Reglages.t("Retour", "Back")
                            onClicked: Etat.allerControle("accueil")
                        }
                    }

                    Column {
                        width: parent.width - (fen.surAccueil ? 0 : 36)
                        anchors.verticalCenter: parent.verticalCenter
                        spacing: 1
                        Texte {
                            width: parent.width
                            text: fen.surAccueil
                                  ? (fen.estBrut ? (Couleurs.styleTerminal ? "> CTRL // " + Couleurs.nomThemeAffiche.toUpperCase() : "CTRL // " + Couleurs.nomThemeAffiche.toUpperCase())
                                                 : Reglages.t("Centre de contrôle", "Control Center"))
                                  : (fen.estBrut ? fen.metaSection(fen.section).nom.toUpperCase() : fen.metaSection(fen.section).nom)
                            font.pixelSize: fen.estBrut ? 11 : 15
                            font.weight: Font.Bold
                            font.letterSpacing: fen.estBrut ? 1.0 : -0.2
                            color: Couleurs.styleTerminal ? Couleurs.accent : Couleurs.texte
                        }
                        Texte {
                            width: parent.width
                            visible: fen.surAccueil && !fen.estBrut
                            text: Etat.heure + " · " + Couleurs.nomThemeAffiche
                            secondaire: true; font.pixelSize: 10
                            font.features: ({ "tnum": 1 })
                        }
                    }

                }

                // Actions rapides en haut à droite : Thèmes, Réglages, Session
                Row {
                    id: actionsEntete
                    anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter
                    spacing: 6

                    Rectangle {
                        objectName: "nc-controle-themes"
                        width: 30; height: 30
                        radius: Couleurs.rayon(fen.estBrut ? 2 : 15, width, height)
                        color: zTh.contientPointeur ? Couleurs.surfaceActive : Couleurs.surfaceDouce
                        border.width: (fen.estBrut || fen.estEditorial) ? 1 : 0
                        border.color: Couleurs.bordureSubtile
                        Ico { anchors.centerIn: parent; nom: "palette"; taille: 16; color: zTh.contientPointeur ? Couleurs.texteSurSurfaceActive : Couleurs.texteSec }
                        ControleAction {
                            id: zTh; anchors.fill: parent
                            text: Reglages.t("Thèmes du bureau", "Desktop themes")
                            onClicked: fen.ouvrirThemes()
                        }
                    }

                    BoutonReglages {
                        objectName: "nc-controle-reglages"
                        taille: 30
                        section: fen.metaSection(fen.section).reglage
                        aide: Reglages.t("Réglages du bureau", "Desktop settings")
                        onOuvert: fen.fermer()
                        activeFocusOnTab: true
                        Keys.onReturnPressed: ouvrir()
                        Keys.onEnterPressed: ouvrir()
                        Keys.onSpacePressed: ouvrir()
                        border.color: activeFocus ? Couleurs.accent : Couleurs.bordureSubtile
                    }

                    Rectangle {
                        objectName: "nc-controle-session"
                        width: 30; height: 30
                        radius: Couleurs.rayon(fen.estBrut ? 2 : 15, width, height)
                        color: zPow.contientPointeur ? Qt.alpha(Couleurs.rouge, 0.22) : Couleurs.surfaceDouce
                        border.width: (fen.estBrut || fen.estEditorial) ? 1 : 0
                        border.color: zPow.contientPointeur ? Couleurs.rouge : Couleurs.bordureSubtile
                        Ico { anchors.centerIn: parent; nom: "power_settings_new"; taille: 16; color: zPow.contientPointeur ? Couleurs.rouge : Couleurs.texteSec }
                        ControleAction {
                            id: zPow; anchors.fill: parent
                            text: Reglages.t("Verrouiller et mettre en veille", "Lock and suspend")
                            onClicked: { fen.fermer(); Quickshell.execDetached([Etat.bin + "nc-shell-msg", "session"]) }
                        }
                    }
                }
            }

            Rectangle {
                id: ligneEntete
                anchors.top: entete.bottom; anchors.topMargin: 10
                anchors.left: parent.left; anchors.right: parent.right
                anchors.leftMargin: 16; anchors.rightMargin: 16
                height: 1; color: Couleurs.separateur
            }

            // ── Tableau de bord principal (accueil) ──
            Flickable {
                id: defileAccueil
                visible: fen.surAccueil
                anchors.top: ligneEntete.bottom; anchors.topMargin: 12
                anchors.left: parent.left; anchors.right: parent.right
                anchors.bottom: parent.bottom
                anchors.leftMargin: 16; anchors.rightMargin: 16; anchors.bottomMargin: 14
                contentWidth: width
                contentHeight: blocAccueil.implicitHeight
                clip: true
                boundsBehavior: Flickable.StopAtBounds

                Column {
                    id: blocAccueil
                    width: parent.width
                    spacing: 10

                    // 1. Grille Connexions & Modes (2 x 2 Bento)
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
                            onBasculer: bouton => {
                                if (fen.filaire) fen.ouvrirWidget("reseau", bouton)
                                else Etat.inverser("wifi", ["noctalia", "msg", "wifi-toggle"])
                            }
                            onOuvrirDetails: bouton => fen.ouvrirWidget("reseau", bouton)
                        }

                        ControleTuile {
                            objectName: "nc-controle-tuile-bluetooth"
                            width: parent.largeurTuile
                            icone: fen.btActif ? "bluetooth" : "bluetooth_disabled"
                            titre: "Bluetooth"
                            sousTitre: fen.btActif ? Reglages.t("Activé", "On") : Reglages.t("Désactivé", "Off")
                            actif: fen.btActif
                            couleurActive: Couleurs.bleu
                            aDetails: true
                            onBasculer: Etat.inverser("bluetooth", ["noctalia", "msg", "bluetooth-toggle"])
                            onOuvrirDetails: bouton => fen.ouvrirWidget("bluetooth", bouton)
                        }

                        ControleTuile {
                            objectName: "nc-controle-tuile-concentration"
                            width: parent.largeurTuile
                            icone: Modes.pastille ? Modes.actifIcone : (Notifs.concentration ? "do_not_disturb_on" : "notifications")
                            titre: Reglages.t("Concentration", "Focus")
                            sousTitre: Modes.pastille ? (Modes.nomVisible || Reglages.t("Actif", "Active"))
                                                      : (Notifs.concentration ? Reglages.t("Silence", "DND") : Reglages.t("Normal", "Off"))
                            actif: Notifs.concentration || Modes.pastille
                            couleurActive: Couleurs.violet
                            aDetails: true
                            onBasculer: Notifs.basculerConcentration()
                            onOuvrirDetails: bouton => fen.ouvrirWidget("concentration", bouton)
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
                            onBasculer: { fen.fermer(); VpnEtat.demanderPanneau() }
                            onOuvrirDetails: { fen.fermer(); VpnEtat.demanderPanneau() }
                        }
                    }

                    // 2. Rangée compacte de 4 bascules rapides (Nuit, Caféine, Jeu, Cloud/IA)
                    Row {
                        width: parent.width; spacing: 8
                        readonly property real largeurPil: Math.floor((width - 24) / 4)

                        component PiluleRapide: Rectangle {
                            id: pr
                            property string icone: "tune"
                            property string libelle: ""
                            property bool actif: false
                            property color couleur: Couleurs.accent
                            signal clic()
                            readonly property bool plein: actif && fen.estBrut
                            height: 52
                            radius: Couleurs.rayon(Couleurs.rayonBloc, width, height)
                            color: plein ? couleur
                                 : (actif ? Qt.alpha(couleur, Couleurs.sombre ? 0.20 : 0.14)
                                          : (zPr.contientPointeur ? Couleurs.carteSurvol : (fen.estEditorial ? "transparent" : Couleurs.surfaceDouce)))
                            border.width: (fen.estBrut || fen.estEditorial || fen.estNeon || actif) ? 1 : 0
                            border.color: actif ? (fen.estBrut || fen.estNeon ? couleur : Qt.alpha(couleur, 0.45)) : Couleurs.bordureSubtile
                            Behavior on color { enabled: !Reglages.sobre; ColorAnimation { duration: 110 } }
                            Column {
                                anchors.centerIn: parent; spacing: 3
                                Ico {
                                    anchors.horizontalCenter: parent.horizontalCenter
                                    nom: pr.icone; taille: 17; plein: pr.actif
                                    color: pr.plein ? Couleurs.surAccent : (pr.actif ? pr.couleur : Couleurs.texteSec)
                                }
                                Texte {
                                    anchors.horizontalCenter: parent.horizontalCenter
                                    text: fen.estBrut ? pr.libelle.toUpperCase() : pr.libelle
                                    font.pixelSize: fen.estBrut ? 8 : 10; font.weight: Font.DemiBold
                                    color: pr.plein ? Couleurs.surAccent : (pr.actif ? Couleurs.texte : Couleurs.texteSec)
                                }
                            }
                            ControleAction {
                                id: zPr; anchors.fill: parent; text: pr.libelle
                                onClicked: pr.clic()
                            }
                        }

                        PiluleRapide {
                            objectName: "nc-controle-tuile-nuit"
                            width: parent.largeurPil
                            icone: "wb_twilight"; libelle: Reglages.t("Nuit", "Night")
                            actif: Etat.nuit; couleur: Couleurs.orange
                            onClic: { Etat.nuit = !Etat.nuit; Etat.faire(["noctalia", "msg", "nightlight-force-toggle"]) }
                        }
                        PiluleRapide {
                            objectName: "nc-controle-tuile-cafe"
                            width: parent.largeurPil
                            icone: Etat.cafe ? "coffee" : "coffee_maker"; libelle: Reglages.t("Caféine", "Awake")
                            actif: Etat.cafe; couleur: Couleurs.orange
                            onClic: Etat.basculerCafe()
                        }
                        PiluleRapide {
                            objectName: "nc-controle-tuile-jeu"
                            width: parent.largeurPil
                            icone: "sports_esports"; libelle: Reglages.t("Jeu", "Game")
                            actif: Etat.jeu; couleur: Couleurs.rose
                            onClic: Etat.faire(["hyprctl", "eval", "nc.mode_jeu()"])
                        }
                        PiluleRapide {
                            objectName: "nc-controle-tuile-cloud"
                            width: parent.largeurPil
                            icone: fen.cloudDispo ? (CloudEtat.envoie ? "cloud_upload" : "cloud") : "auto_awesome"
                            libelle: fen.cloudDispo ? "Cloud" : "IA"
                            actif: fen.cloudDispo ? CloudEtat.envoie : !Reglages.iaCoupee
                            couleur: Couleurs.accent
                            onClic: {
                                if (fen.cloudDispo) { fen.fermer(); CloudEtat.ouvrirPanneau() }
                                else { fen.fermer(); Etat.chercher(fen.screen ? fen.screen.name : "") }
                            }
                        }
                    }

                    // 3. Carte Média en direct (apparaît uniquement si un lecteur est actif)
                    Rectangle {
                        visible: Etat.aMusique
                        width: parent.width; height: 64
                        radius: Couleurs.rayon(Couleurs.rayonBloc, width, height)
                        color: fen.estEditorial ? "transparent" : Couleurs.surfaceDouce
                        border.width: 1; border.color: fen.estNeon ? Couleurs.accentBord : Couleurs.bordureSubtile

                        ClippingRectangle {
                            id: pochetteCtrl
                            x: 10; anchors.verticalCenter: parent.verticalCenter
                            width: 44; height: 44
                            radius: Couleurs.rayon(Couleurs.rayonBouton, width, height)
                            color: Couleurs.gris2
                            Image {
                                anchors.fill: parent
                                source: Reglages.imagesLegeres ? "" : Etat.pochette
                                fillMode: Image.PreserveAspectCrop; visible: status === Image.Ready
                            }
                            Ico { anchors.centerIn: parent; nom: "music_note"; taille: 20; color: Couleurs.accent; visible: Reglages.imagesLegeres || Etat.pochette === "" }
                        }
                        Column {
                            anchors.left: pochetteCtrl.right; anchors.leftMargin: 10
                            anchors.right: btnsMedia.left; anchors.rightMargin: 8
                            anchors.verticalCenter: parent.verticalCenter; spacing: 2
                            Texte { width: parent.width; text: Etat.titre; font.pixelSize: 12; font.weight: Font.DemiBold }
                            Texte { width: parent.width; visible: Etat.artiste !== ""; text: Etat.artiste; secondaire: true; font.pixelSize: 10 }
                            Rectangle {
                                visible: !!Etat.lecteur && Etat.lecteur.length > 0
                                width: parent.width; height: 3; radius: Couleurs.rayon(2, width, height)
                                color: Qt.alpha(Couleurs.voile, 0.12)
                                Rectangle {
                                    width: parent.width * fen.progresMedia
                                    height: parent.height; radius: parent.radius; color: Couleurs.accent
                                }
                            }
                        }
                        Row {
                            id: btnsMedia
                            anchors.right: parent.right; anchors.rightMargin: 8
                            anchors.verticalCenter: parent.verticalCenter; spacing: 2
                            Rectangle {
                                width: 26; height: 26; radius: Couleurs.rayon(Couleurs.rayonBouton, width, height)
                                color: zMp.contientPointeur ? Couleurs.accentDoux : "transparent"
                                Ico { anchors.centerIn: parent; nom: "skip_previous"; taille: 16; color: Couleurs.texteSec }
                                ControleAction {
                                    id: zMp; anchors.fill: parent
                                    enabled: !!Etat.lecteur && Etat.lecteur.canGoPrevious
                                    text: Reglages.t("Piste précédente", "Previous track")
                                    onClicked: Etat.lecteur.previous()
                                }
                            }
                            Rectangle {
                                width: 30; height: 30; radius: Couleurs.rayon(fen.estBrut ? 2 : 15, width, height)
                                color: Couleurs.accent
                                Ico { anchors.centerIn: parent; nom: Etat.joue ? "pause" : "play_arrow"; taille: 17; color: Couleurs.surAccent }
                                ControleAction {
                                    anchors.fill: parent
                                    text: Etat.joue ? Reglages.t("Pause", "Pause") : Reglages.t("Lecture", "Play")
                                    onClicked: Etat.lecturePause()
                                }
                            }
                            Rectangle {
                                width: 26; height: 26; radius: Couleurs.rayon(Couleurs.rayonBouton, width, height)
                                color: zMn.contientPointeur ? Couleurs.accentDoux : "transparent"
                                Ico { anchors.centerIn: parent; nom: "skip_next"; taille: 16; color: Couleurs.texteSec }
                                ControleAction {
                                    id: zMn; anchors.fill: parent
                                    enabled: !!Etat.lecteur && Etat.lecteur.canGoNext
                                    text: Reglages.t("Piste suivante", "Next track")
                                    onClicked: Etat.lecteur.next()
                                }
                            }
                        }
                    }

                    // 4. Carte Glissières groupées (Volume + Luminosité)
                    Rectangle {
                        width: parent.width
                        height: colGliss.implicitHeight + 18
                        radius: Couleurs.rayon(Couleurs.rayonBloc, width, height)
                        color: fen.estEditorial ? "transparent" : Couleurs.surfaceDouce
                        border.width: 1; border.color: Couleurs.bordureSubtile

                        Column {
                            id: colGliss
                            x: 12; y: 9; width: parent.width - 24; spacing: 6

                            ControleGlissiere {
                                objectName: "nc-controle-glissiere-volume"
                                width: parent.width
                                icone: Etat.muet ? "volume_off" : (Etat.volume > 0.55 ? "volume_up" : "volume_down")
                                titre: Reglages.t("Volume", "Volume")
                                valeur: Etat.volume
                                muet: Etat.muet
                                aDetails: true
                                onChanger: v => Etat.reglerVolume(v)
                                onBasculerMuet: Etat.basculerMuet()
                                onOuvrirDetails: bouton => fen.ouvrirWidget("son", bouton)
                            }

                            Rectangle {
                                visible: Etat.aLuminosite
                                width: parent.width; height: 1; color: Couleurs.separateur
                            }

                            ControleGlissiere {
                                objectName: "nc-controle-glissiere-luminosite"
                                visible: Etat.aLuminosite
                                width: parent.width
                                icone: "brightness_6"
                                titre: Reglages.t("Luminosité", "Brightness")
                                valeur: Etat.luminosite
                                onChanger: v => Etat.reglerLuminosite(v)
                                onBasculerMuet: Etat.reglerLuminosite(Etat.luminosite > 0.5 ? 0.25 : 0.8)
                            }
                        }
                    }

                    // 5. Sélecteur segmenté Profils d'énergie
                    Rectangle {
                        visible: !Etat.profilsAbsents
                        width: parent.width; height: 38
                        radius: Couleurs.rayon(Couleurs.rayonBloc, width, height)
                        color: fen.estEditorial ? "transparent" : Couleurs.surfaceDouce
                        border.width: 1; border.color: Couleurs.bordureSubtile

                        Row {
                            anchors.fill: parent; anchors.margins: 3; spacing: 3
                            readonly property var choixProfils: Etat.performanceDisponible
                                ? [{ p: PowerProfile.PowerSaver, ico: "eco", fr: "Éco", en: "Saver" },
                                   { p: PowerProfile.Balanced, ico: "balance", fr: "Équilibré", en: "Balanced" },
                                   { p: PowerProfile.Performance, ico: "bolt", fr: "Perf", en: "Perf" }]
                                : [{ p: PowerProfile.PowerSaver, ico: "eco", fr: "Économie", en: "Saver" },
                                   { p: PowerProfile.Balanced, ico: "balance", fr: "Équilibré", en: "Balanced" }]

                            Repeater {
                                model: parent.choixProfils
                                Rectangle {
                                    required property var modelData
                                    readonly property bool sel: Etat.profil === modelData.p
                                    width: (parent.width - (parent.choixProfils.length - 1) * 3) / parent.choixProfils.length
                                    height: parent.height
                                    radius: Couleurs.rayon(Couleurs.rayonBouton, width, height)
                                    color: sel ? Couleurs.surfaceActive : (zPrf.contientPointeur ? Couleurs.carteSurvol : "transparent")
                                    border.width: sel && (fen.estNeon || fen.estEditorial) ? 1 : 0
                                    border.color: Couleurs.accent
                                    Behavior on color { enabled: !Reglages.sobre; ColorAnimation { duration: 110 } }
                                    Row {
                                        anchors.centerIn: parent; spacing: 5
                                        Ico {
                                            anchors.verticalCenter: parent.verticalCenter
                                            nom: modelData.ico; taille: 14
                                            color: parent.parent.sel ? Couleurs.texteSurSurfaceActive : Couleurs.texteSec
                                        }
                                        Texte {
                                            anchors.verticalCenter: parent.verticalCenter
                                            text: fen.estBrut ? Reglages.t(modelData.fr, modelData.en).toUpperCase() : Reglages.t(modelData.fr, modelData.en)
                                            font.pixelSize: fen.estBrut ? 9 : 11
                                            font.weight: parent.parent.sel ? Font.DemiBold : Font.Medium
                                            color: parent.parent.sel ? Couleurs.texteSurSurfaceActive : Couleurs.texteSec
                                        }
                                    }
                                    ControleAction {
                                        id: zPrf; anchors.fill: parent; text: Reglages.t(modelData.fr, modelData.en)
                                        onClicked: Etat.choisirProfil(modelData.p)
                                    }
                                }
                            }
                        }
                    }

                    // 6. Barre d'outils & tiroirs rapides
                    Flow {
                        width: parent.width; spacing: 6
                        Repeater {
                            model: fen.outils
                            Rectangle {
                                required property var modelData
                                width: rowO.implicitWidth + 16; height: 28
                                radius: Couleurs.rayon(Couleurs.rayonBouton, width, height)
                                color: zO.contientPointeur ? Couleurs.accentDoux : (fen.estEditorial ? "transparent" : Couleurs.surfaceDouce)
                                border.width: 1; border.color: zO.contientPointeur ? Couleurs.accentBord : Couleurs.bordureSubtile
                                Behavior on color { enabled: !Reglages.sobre; ColorAnimation { duration: 100 } }
                                Row {
                                    id: rowO; anchors.centerIn: parent; spacing: 5
                                    Ico { anchors.verticalCenter: parent.verticalCenter; nom: modelData.ico; taille: 13; color: zO.contientPointeur ? Couleurs.accent : Couleurs.texteSec }
                                    Texte {
                                        anchors.verticalCenter: parent.verticalCenter
                                        text: fen.estBrut ? Reglages.t(modelData.fr, modelData.en).toUpperCase() : Reglages.t(modelData.fr, modelData.en)
                                        font.pixelSize: fen.estBrut ? 9 : 11; font.weight: Font.Medium
                                        color: zO.contientPointeur ? Couleurs.texte : Couleurs.texteDoux
                                    }
                                }
                                ControleAction {
                                    id: zO; anchors.fill: parent; text: Reglages.t(modelData.fr, modelData.en)
                                    onClicked: fen.ouvrirWidget(modelData.id, zO)
                                }
                            }
                        }
                    }
                }
            }

            // ── Tiroirs natifs dédiés (Zéro recyclage d'anciennes pages de l'île) ──
            Item {
                visible: !fen.surAccueil
                anchors.top: ligneEntete.bottom; anchors.topMargin: 10
                anchors.left: parent.left; anchors.right: parent.right
                anchors.bottom: parent.bottom
                anchors.leftMargin: 16; anchors.rightMargin: 16; anchors.bottomMargin: 14

                Loader {
                    objectName: "nc-controle-tiroir"
                    anchors.fill: parent
                    active: !fen.surAccueil
                    sourceComponent: {
                        if (fen.section === "reseau") return tReseau
                        if (fen.section === "bluetooth") return tBluetooth
                        if (fen.section === "son") return tAudio
                        return tOutils
                    }
                }
            }

            Component { id: tReseau; ControleReseau { onFermerPanneau: fen.fermer() } }
            Component { id: tBluetooth; ControleBluetooth {} }
            Component { id: tAudio; ControleAudio {} }
            Component { id: tOutils; ControleOutils { section: fen.section; onFermerPanneau: fen.fermer() } }
        }
    }
}

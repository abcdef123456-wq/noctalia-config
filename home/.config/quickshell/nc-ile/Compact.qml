// Contenu de la pilule (île fermée) :
//   repos   : heure et date ;  musique : pochette, heure, onde sonore (en pause : symbole lecture et titre)
//   réactions (2 à 3 s) : volume, luminosité, nouveau morceau, chargeur, profil d'énergie, mode jeu
//   Claude Code et Antigravity (nc-claude) : ce qu'il fait (son logo qui bouge), « t'attend dans le terminal », « a terminé »
// largeur : largeur voulue de la pilule ; l'île s'y ajuste avec un ressort.
import QtQuick
import Quickshell.Widgets
import Quickshell.Services.UPower

Item {
    id: c
    readonly property string mode: Etat.activiteType !== "" ? Etat.activiteType
                                   : Etat.enregistre ? "video"
                                   : Partage.indicateur ? "partage"
                                   : AssistantEtat.activitePilule !== "" ? AssistantEtat.activitePilule
                                   : Appel.enCours ? "appel"
                                   : Resume.actif ? "resume"
                                   : Etat.telecharge && !Etat.aMusique && !Agents.travaille ? "telechargement"
                                   : (Agents.attendTerminal ? "claude"
                                   : (Etat.aMusique ? "musique" : (Agents.travaille ? "claude" : (Etat.minuteurFin > 0 ? "minuteur"
                                   : (Terminal.enCours ? "terminal" : "repos")))))
    readonly property real largeur: Math.max(110, actif.implicitWidth + 32)
    implicitHeight: 30
    // Le point (x, y) de l'île tombe-t-il sur l'indicateur VPN de la pilule au repos ? (le clic ouvre alors le panneau VPN)
    function surVpn(x, y) {
        if (!VpnEtat.indicateur || mode !== "repos") return false
        var p = c.mapToItem(pastilleVpn, x, y)
        return p.x >= -4 && p.x <= pastilleVpn.width + 4 && p.y >= -6 && p.y <= pastilleVpn.height + 6
    }

    readonly property Item actif: ({ repos: repos, musique: musique, volume: jauge, luminosite: jauge,
                                      piste: piste, charge: charge, profil: profil, jeu: jeu,
                                      minuteur: minuteur, "minuteur-fini": fini, micro: micro, casque: casque,
                                      claude: claude, "claude-fini": claudeFini, jarvis: jarvis, "jarvis-fini": jarvis, video: video, partage: partage,
                                      telechargement: telechargement, "telechargement-fini": telechargementFini, chaleur: chaleur,
                                      appel: appel, "appel-muet": appelMuet, "appel-fini": appelFini,
                                      terminal: terminal, "terminal-fini": terminalFini, resume: resume })[mode] || repos

    component Fondu: Row {
        property bool montre: false
        anchors.centerIn: parent
        spacing: 9
        opacity: montre ? 1 : 0
        visible: opacity > 0.01
        Behavior on opacity { NumberAnimation { duration: 160; easing.type: Easing.OutCubic } }
    }

    Fondu {
        id: jarvis
        objectName: "nc-jarvis-pill"
        montre: c.mode === "jarvis" || c.mode === "jarvis-fini"
        // Créé seulement quand la pilule JARVIS se montre (comme dans Etincelle.qml) : l'atlas PNG décodé coûtait
        // de 10 à 35 Mo de mémoire dès le démarrage (selon les arènes de jemalloc, voir nc-ile.service), même pilule
        // cachée. À l'arrivée, l'image est lue en même temps
        // que le fondu commence.
        Loader {
            anchors.verticalCenter: parent.verticalCenter; width: 22; height: 22
            active: jarvis.montre || jarvis.opacity > 0.01
            sourceComponent: LogoAssistant {
                anime: jarvis.montre && c.visible && c.opacity > 0.01 && AssistantEtat.enCours
                    && !Reglages.sobre
            }
        }
        Texte {
            anchors.verticalCenter: parent.verticalCenter; font.weight: Font.DemiBold
            text: AssistantEtat.enCours ? Reglages.t("JARVIS réfléchit…", "JARVIS is thinking…")
                : Reglages.t("JARVIS a répondu", "JARVIS replied")
        }
    }

    // ── Repos : heure et date ──
    Fondu {
        id: repos
        montre: c.mode === "repos"
        // Un tunnel VPN RÉELLEMENT monté (VpnEtat.qml, nc-vpn indicateur) : notre bouclier à cadenas (shield_lock, pas l'icône de tray d'un client) et « Fournisseur · 🇫🇷 FR » (+1 si plusieurs) ;
        // pendant un partage d'écran : « VPN » seul. Un clic ouvre le panneau VPN complet.
        Row {
            id: pastilleVpn
            objectName: "nc-vpn-pill"
            anchors.verticalCenter: parent.verticalCenter; spacing: 4
            visible: VpnEtat.indicateur
            Ico { objectName: "nc-vpn-pill-glyphe"; anchors.verticalCenter: parent.verticalCenter; nom: "shield_lock"; taille: 15; color: Couleurs.vert }
            Texte { objectName: "nc-vpn-pill-texte"; anchors.verticalCenter: parent.verticalCenter; text: VpnEtat.libelle; secondaire: true
                    font.pixelSize: 12; elide: Text.ElideRight; width: Math.min(implicitWidth, 150) }
            Accessible.role: Accessible.StaticText; Accessible.name: VpnEtat.libelle
        }
        // Un mode Concentration actif (Modes.qml) : son icône et son nom court ; le nom est caché pendant un partage d'écran
        Row {
            objectName: "nc-mode-pill"
            anchors.verticalCenter: parent.verticalCenter; spacing: 4
            visible: Modes.pastille
            Ico { anchors.verticalCenter: parent.verticalCenter; nom: Modes.actifIcone; taille: 15; color: Couleurs.accentClair }
            Texte { anchors.verticalCenter: parent.verticalCenter; visible: Modes.nomVisible !== ""; text: Modes.nomVisible; secondaire: true
                    font.pixelSize: 12; width: Math.min(implicitWidth, 90) }
            Accessible.role: Accessible.StaticText
            Accessible.name: Reglages.t("Mode Concentration actif", "Focus mode on")
        }
        Texte { anchors.verticalCenter: parent.verticalCenter; text: Etat.heure; font.weight: Font.DemiBold }
        Texte { anchors.verticalCenter: parent.verticalCenter; text: Etat.dateCourte; secondaire: true
                visible: Reglages.val("ILE_DATE", "oui") !== "non" }       // nc-reglages
        // Météo (nc-reglages, ILE_METEO)
        Row {
            anchors.verticalCenter: parent.verticalCenter; spacing: 3
            visible: Etat.meteoPilule
            Ico { anchors.verticalCenter: parent.verticalCenter; nom: Etat.meteo.icone || "cloud"; taille: 15; color: Couleurs.texteSec }
            Texte { anchors.verticalCenter: parent.verticalCenter; text: (Etat.meteo.temp !== undefined ? Etat.meteo.temp : "") + "°"; secondaire: true }
        }
    }

    // ── Musique : pochette | heure (et titre en pause) | onde ──
    Fondu {
        id: musique
        montre: c.mode === "musique"
        ClippingRectangle {
            width: 20; height: 20; radius: 6; color: Etat.pochette === "" && Etat.iconeLecteur !== "" ? "transparent" : Couleurs.gris2
            anchors.verticalCenter: parent.verticalCenter
            Image { anchors.fill: parent; source: Etat.pochette; fillMode: Image.PreserveAspectCrop; asynchronous: true; sourceSize: Qt.size(144, 144) }
            Image { anchors.fill: parent; source: Etat.pochette === "" ? Etat.iconeLecteur : ""; sourceSize: Qt.size(40, 40); visible: Etat.pochette === "" }
            Ico { anchors.centerIn: parent; nom: "music_note"; taille: 14; visible: Etat.pochette === "" && Etat.iconeLecteur === "" }
        }
        Texte { anchors.verticalCenter: parent.verticalCenter; text: Etat.heure; font.weight: Font.DemiBold }
        Texte { anchors.verticalCenter: parent.verticalCenter; text: Etat.titre; secondaire: true; visible: !Etat.joue; width: Math.min(implicitWidth, 150) }
        Row {
            visible: Etat.joue
            spacing: 2
            anchors.verticalCenter: parent.verticalCenter
            Repeater {
                model: 5
                Rectangle {
                    required property int index
                    width: 3; radius: 1.5
                    height: 6 + Etat.bandes[index] * 10
                    anchors.verticalCenter: parent.verticalCenter
                    color: Couleurs.texte
                }
            }
        }
        Ico { anchors.verticalCenter: parent.verticalCenter; nom: "play_arrow"; taille: 16; color: Couleurs.texteSec; visible: !Etat.joue }
    }

    // ── Minuteur en cours : décompte orange ──
    Fondu {
        id: minuteur
        montre: c.mode === "minuteur"
        readonly property color teinte: Etat.pomodoro ? (Etat.pomoPause ? Couleurs.vert : "#ff6347") : Couleurs.orange
        Texte { anchors.verticalCenter: parent.verticalCenter; text: Etat.heure; font.weight: Font.DemiBold }
        Ico { anchors.verticalCenter: parent.verticalCenter; nom: Etat.pomodoro ? (Etat.pomoPause ? "coffee" : "psychology") : "timer"; taille: 17; color: minuteur.teinte }
        Texte { anchors.verticalCenter: parent.verticalCenter; text: Etat.duree(Etat.minuteurReste); font.weight: Font.DemiBold; color: minuteur.teinte; font.features: { "tnum": 1 } }
    }
    Fondu {
        id: fini
        montre: c.mode === "minuteur-fini"
        Ico { anchors.verticalCenter: parent.verticalCenter; nom: "alarm"; taille: 18; color: Couleurs.orange }
        Texte { anchors.verticalCenter: parent.verticalCenter; text: Reglages.t("Minuteur terminé", "Timer Done"); font.weight: Font.DemiBold }
    }

    // ── Volume / luminosité : jauge blanche ──
    Fondu {
        id: jauge
        readonly property bool vol: c.mode === "volume"
        readonly property real valeur: vol ? (Etat.muet ? 0 : Etat.volume) : Etat.luminosite
        montre: c.mode === "volume" || c.mode === "luminosite"
        Ico {
            anchors.verticalCenter: parent.verticalCenter
            nom: jauge.vol ? (Etat.muet ? "volume_off" : (Etat.volume < 0.34 ? "volume_mute" : (Etat.volume < 0.67 ? "volume_down" : "volume_up"))) : "light_mode"
            taille: 18; color: jauge.vol && Etat.muet ? Couleurs.texteSec : Couleurs.texte
        }
        Rectangle {
            width: 130; height: 6; radius: 3; color: Couleurs.gris3
            anchors.verticalCenter: parent.verticalCenter
            Rectangle {
                width: parent.width * Math.max(0, Math.min(1, jauge.valeur)); height: parent.height; radius: 3; color: Couleurs.texte
                Behavior on width { SpringAnimation { spring: 5; damping: 0.5 } }
            }
        }
        Texte { anchors.verticalCenter: parent.verticalCenter; text: Math.round(jauge.valeur * 100) + Reglages.t(" %", "%"); font.weight: Font.DemiBold; width: 42; horizontalAlignment: Text.AlignRight }
    }

    // ── Nouveau morceau ──
    Fondu {
        id: piste
        montre: c.mode === "piste"
        ClippingRectangle {
            width: 22; height: 22; radius: 6; color: Etat.pochette === "" && Etat.iconeLecteur !== "" ? "transparent" : Couleurs.gris2
            anchors.verticalCenter: parent.verticalCenter
            Image { anchors.fill: parent; source: Etat.pochette !== "" ? Etat.pochette : Etat.iconeLecteur; sourceSize: Qt.size(44, 44); fillMode: Image.PreserveAspectCrop
                    asynchronous: Etat.pochette !== "" }   // icônes du thème : jamais hors du fil principal (plantage de Qt)
        }
        Texte { anchors.verticalCenter: parent.verticalCenter; text: Etat.titre; font.weight: Font.DemiBold; width: Math.min(implicitWidth, 200) }
        Texte { anchors.verticalCenter: parent.verticalCenter; text: Etat.artiste; secondaire: true; width: Math.min(implicitWidth, 140); visible: Etat.artiste !== "" }
    }

    // ── Chargeur ──
    Fondu {
        id: charge
        montre: c.mode === "charge"
        Ico { anchors.verticalCenter: parent.verticalCenter; nom: Etat.branche ? "bolt" : "battery_full"; taille: 18; color: Etat.branche ? Couleurs.vert : Couleurs.texte }
        Texte {
            anchors.verticalCenter: parent.verticalCenter
            text: (Etat.branche ? Reglages.t("En charge · ", "Charging · ") : Reglages.t("Sur batterie · ", "On battery · ")) + Etat.pourcent + Reglages.t(" %", "%")
            font.weight: Font.DemiBold; color: Etat.branche ? Couleurs.vert : Couleurs.texte
        }
    }

    // ── Profil d'énergie ──
    Fondu {
        id: profil
        montre: c.mode === "profil"
        Ico {
            anchors.verticalCenter: parent.verticalCenter
            nom: Etat.profil === PowerProfile.PowerSaver ? "eco" : (Etat.profil === PowerProfile.Performance ? "bolt" : "balance")
            taille: 18
            color: Etat.profil === PowerProfile.PowerSaver ? Couleurs.vert : (Etat.profil === PowerProfile.Performance ? Couleurs.orange : Couleurs.texte)
        }
        Texte {
            anchors.verticalCenter: parent.verticalCenter
            text: Etat.profil === PowerProfile.PowerSaver ? Reglages.t("Économie", "Power saver") : (Etat.profil === PowerProfile.Performance ? "Performance" : Reglages.t("Équilibré", "Balanced"))
            font.weight: Font.DemiBold
        }
    }

    // ── Micro / caméra : « Discord utilise le micro » ──
    Fondu {
        id: micro
        montre: c.mode === "micro"
        Ico {
            anchors.verticalCenter: parent.verticalCenter
            nom: Etat.cameraActive ? "videocam" : "mic"; taille: 18
            color: Etat.cameraActive ? Couleurs.vert : Couleurs.orange
        }
        Texte {
            anchors.verticalCenter: parent.verticalCenter
            text: Etat.cameraActive ? Etat.nomJoli(Etat.appliCamera) + Reglages.t(" utilise la caméra", " is using the camera")
                                     : Etat.nomJoli(Etat.appliMicro) + Reglages.t(" utilise le micro", " is using the microphone")
            font.weight: Font.DemiBold
        }
    }

    // ── Casque Bluetooth connecté : nom et batterie ──
    Fondu {
        id: casque
        montre: c.mode === "casque"
        Ico { anchors.verticalCenter: parent.verticalCenter; nom: "headphones"; taille: 18; color: Couleurs.accent }
        Texte { anchors.verticalCenter: parent.verticalCenter; text: Etat.casqueNom; font.weight: Font.DemiBold; width: Math.min(implicitWidth, 220) }
        Row {
            anchors.verticalCenter: parent.verticalCenter; spacing: 3
            visible: Etat.casqueBatterie !== ""
            Ico {
                anchors.verticalCenter: parent.verticalCenter; taille: 16; color: Couleurs.vert
                nom: parseInt(Etat.casqueBatterie) > 60 ? "battery_full" : (parseInt(Etat.casqueBatterie) > 25 ? "battery_4_bar" : "battery_1_bar")
            }
            Texte { anchors.verticalCenter: parent.verticalCenter; text: Etat.casqueBatterie + Reglages.t(" %", "%"); secondaire: true }
        }
    }

    // ── Claude Code : étincelle qui tourne, l'étape en cours, lignes ajoutées / retirées ──
    Fondu {
        id: claude
        readonly property var s: Agents.principale
        readonly property bool terminal: Agents.attendTerminal
        montre: c.mode === "claude"
        Texte { anchors.verticalCenter: parent.verticalCenter; text: Etat.heure; font.weight: Font.DemiBold }
        Etincelle { anchors.verticalCenter: parent.verticalCenter; taille: 16; tourne: !claude.terminal; visible: claude.montre || opacity > 0
                    agent: Agents.agent(claude.terminal ? Agents.attend : claude.s) }
        Texte {
            anchors.verticalCenter: parent.verticalCenter
            text: claude.terminal ? Agents.nom(Agents.attend) + Reglages.t(" t'attend dans le terminal", " is waiting in the terminal")
                                  : (claude.s ? (claude.s.etape || Reglages.t("Travaille…", "Working…")) : "")
            font.weight: Font.DemiBold; color: claude.terminal ? Couleurs.orange : Couleurs.texte
            width: Math.min(implicitWidth, 200)
        }
        Texte {
            anchors.verticalCenter: parent.verticalCenter
            visible: !claude.terminal && claude.s !== null && (claude.s.ajouts || 0) + (claude.s.retraits || 0) > 0
            text: claude.s ? "+" + (claude.s.ajouts || 0) : ""; color: Couleurs.vert; font.pixelSize: 12
        }
        Texte {
            anchors.verticalCenter: parent.verticalCenter
            visible: !claude.terminal && claude.s !== null && (claude.s.retraits || 0) > 0
            text: claude.s ? "−" + (claude.s.retraits || 0) : ""; color: Couleurs.rouge; font.pixelSize: 12
        }
    }
    Fondu {
        id: claudeFini
        montre: c.mode === "claude-fini"
        Texte { anchors.verticalCenter: parent.verticalCenter; text: Etat.heure; font.weight: Font.DemiBold }
        Etincelle { anchors.verticalCenter: parent.verticalCenter; taille: 16; agent: Agents.dernierFiniAgent }
        Texte { anchors.verticalCenter: parent.verticalCenter; font.weight: Font.DemiBold
                text: Agents.ias[Agents.dernierFiniAgent].nom + Reglages.t(" a terminé", " is done") }
        Texte { anchors.verticalCenter: parent.verticalCenter; text: Agents.dernierFini; secondaire: true; width: Math.min(implicitWidth, 160) }
        Ico { anchors.verticalCenter: parent.verticalCenter; nom: "check_circle"; taille: 17; color: Couleurs.vert }
    }

    // ── Enregistrement d'écran : point rouge qui palpite et durée (un clic sur la pilule l'arrête) ──
    // ── Téléchargement en cours : flèche qui descend, nom, taille reçue et vitesse ──
    Fondu {
        id: telechargement
        readonly property var t: Etat.telechargements.length ? Etat.telechargements[0] : null
        montre: c.mode === "telechargement"
        // Une ancre ne se déplace pas : la rangée place ce cadre, à la taille de la flèche,
        // et la flèche monte et descend dedans
        Item {
            anchors.verticalCenter: parent.verticalCenter
            width: flecheTelechargement.width; height: flecheTelechargement.height
            Ico {
                id: flecheTelechargement
                nom: "arrow_downward"; taille: 17; color: Couleurs.accent
                // Immobile en Économie ou sans effets (Reglages.sobre)
                readonly property bool bouge: telechargement.montre && !Reglages.sobre
                Pas { running: flecheTelechargement.bouge && Etat.ecranVu            // 30 images/s (voir Pas.qml)
                      onTriggered: flecheTelechargement.y = -3 * Math.cos(2 * Math.PI * t / 1.2)
                      onRunningChanged: if (!running) flecheTelechargement.y = 0 }
            }
        }
        Texte {
            anchors.verticalCenter: parent.verticalCenter; font.weight: Font.DemiBold; width: Math.min(implicitWidth, 190)
            text: telechargement.t ? (Partage.silence ? Etat.sansNom : telechargement.t.nom) : ""
        }
        Texte {
            anchors.verticalCenter: parent.verticalCenter; secondaire: true; font.features: { "tnum": 1 }
            text: telechargement.t ? Etat.octets(telechargement.t.taille) + (telechargement.t.vitesse > 0 ? " · " + Etat.octets(telechargement.t.vitesse) + "/s" : "")
                  + (Etat.telechargements.length > 1 ? "  +" + (Etat.telechargements.length - 1) : "") : ""
        }
    }
    Fondu {
        id: telechargementFini
        montre: c.mode === "telechargement-fini"
        Ico { anchors.verticalCenter: parent.verticalCenter; nom: "download_done"; taille: 17; color: Couleurs.vert }
        Texte { anchors.verticalCenter: parent.verticalCenter; text: Etat.telechargeFini; font.weight: Font.DemiBold; width: Math.min(implicitWidth, 200) }
        Texte { anchors.verticalCenter: parent.verticalCenter; text: Reglages.t("téléchargé", "downloaded"); secondaire: true }
    }
    Fondu {
        id: video
        montre: c.mode === "video"
        Rectangle {
            id: pointVideo
            anchors.verticalCenter: parent.verticalCenter; width: 10; height: 10; radius: 5; color: Couleurs.rouge
            // Point rouge fixe en Économie ou sans effets (Reglages.sobre)
            readonly property bool clignote: video.montre && !Reglages.sobre
            // 30 images/s (voir Pas.qml) ; à l'arrêt, le point redevient plein
            Pas { running: pointVideo.clignote && Etat.ecranVu
                  onTriggered: pointVideo.opacity = 0.675 + 0.325 * Math.cos(2 * Math.PI * t / 1.4)
                  onRunningChanged: if (!running) pointVideo.opacity = 1 }
        }
        Texte {
            anchors.verticalCenter: parent.verticalCenter; font.weight: Font.DemiBold; font.features: { "tnum": 1 }
            text: Etat.duree(Math.max(0, Math.floor(Etat.maintenant.getTime() / 1000 - Etat.debutVideo)))
        }
        Ico { anchors.verticalCenter: parent.verticalCenter; nom: "stop_circle"; taille: 17; color: Couleurs.texteSec }
    }

    // ── Écran partagé (Partage.qml, après 1,5 s de partage continu) : le point du partage devant l'heure, comme l'iPhone
    // qui partage son écran (l'heure reste lisible tout le partage) ; « Partage » pour les lecteurs d'écran.
    // Après l'enregistrement d'écran (nc-video, qui montre déjà qu'on capture et s'arrête d'un clic), avant tout le reste
    Fondu {
        id: partage
        objectName: "nc-partage-pill"
        montre: c.mode === "partage"
        Accessible.role: Accessible.StaticText
        Accessible.name: Reglages.t("Partage", "Sharing") + " · " + Etat.heure
        Rectangle { anchors.verticalCenter: parent.verticalCenter; width: 10; height: 10; radius: 5; color: Couleurs.accentClair }
        Texte { anchors.verticalCenter: parent.verticalCenter; text: Etat.heure; font.weight: Font.DemiBold; font.features: { "tnum": 1 } }
    }

    // ── Surchauffe du processeur (Chaleur.qml, une fois par épisode) : « Processeur à 98 °C » ──
    Fondu {
        id: chaleur
        objectName: "nc-chaleur-pill"
        montre: c.mode === "chaleur"
        Ico { anchors.verticalCenter: parent.verticalCenter; nom: "device_thermostat"; taille: 18; color: Couleurs.rouge }
        Texte { anchors.verticalCenter: parent.verticalCenter; text: Chaleur.titre(); font.weight: Font.DemiBold; color: Couleurs.rouge }
        Texte { anchors.verticalCenter: parent.verticalCenter; text: Reglages.t("voir Santé", "see Health"); secondaire: true }
    }

    // ── Appel en cours (Appel.qml) : icône de l'appli, durée, niveau du micro ; micro coupé : micro barré orange ──
    Fondu {
        id: appel
        objectName: "nc-appel-pill"
        montre: c.mode === "appel"
        Item {
            anchors.verticalCenter: parent.verticalCenter; width: 20; height: 20
            Image { anchors.fill: parent; source: Appel.icone; sourceSize: Qt.size(40, 40); visible: Appel.icone !== "" }
            Ico { anchors.centerIn: parent; nom: "call"; taille: 17; color: Couleurs.vert; visible: Appel.icone === "" }
        }
        Texte { anchors.verticalCenter: parent.verticalCenter; text: Appel.dureeTexte; font.weight: Font.DemiBold; color: Couleurs.vert; font.features: { "tnum": 1 } }
        // Niveau du micro : quatre barres (NiveauMicro.qml, 30 images/s pendant l'appel seulement)
        Row {
            visible: !Appel.muet; spacing: 2
            anchors.verticalCenter: parent.verticalCenter
            Repeater {
                model: 4
                Rectangle {
                    required property int index
                    width: 3; radius: 1.5
                    height: 5 + Appel.niveau * [8, 12, 10, 6][index]
                    anchors.verticalCenter: parent.verticalCenter
                    color: Couleurs.vert
                }
            }
        }
        Ico { anchors.verticalCenter: parent.verticalCenter; nom: "mic_off"; taille: 17; color: Couleurs.orange; visible: Appel.muet }
        Texte { anchors.verticalCenter: parent.verticalCenter; text: Reglages.t("Micro coupé", "Muted"); font.weight: Font.DemiBold; color: Couleurs.orange; visible: Appel.muet }
    }
    // Appel qui commence micro coupé : on parle, personne n'entend
    Fondu {
        id: appelMuet
        montre: c.mode === "appel-muet"
        Ico { anchors.verticalCenter: parent.verticalCenter; nom: "mic_off"; taille: 18; color: Couleurs.orange }
        Texte { anchors.verticalCenter: parent.verticalCenter; text: Reglages.t("Micro coupé", "Microphone muted"); font.weight: Font.DemiBold; color: Couleurs.orange }
        Texte { anchors.verticalCenter: parent.verticalCenter; text: Appel.appli + Reglages.t(" ne t'entend pas", " can't hear you"); secondaire: true; width: Math.min(implicitWidth, 200) }
    }
    Fondu {
        id: appelFini
        montre: c.mode === "appel-fini"
        Ico { anchors.verticalCenter: parent.verticalCenter; nom: "call_end"; taille: 18; color: Couleurs.rouge }
        Texte { anchors.verticalCenter: parent.verticalCenter; text: Reglages.t("Appel terminé", "Call ended"); font.weight: Font.DemiBold }
        Texte { anchors.verticalCenter: parent.verticalCenter; text: Appel.derniereAppli + " · " + Etat.duree(Appel.derniereDuree); secondaire: true; width: Math.min(implicitWidth, 200); font.features: { "tnum": 1 } }
    }

    // ── Commande longue dans le terminal (Terminal.qml) : la commande et sa durée ; finie : coche verte ou croix rouge ──
    Fondu {
        id: terminal
        objectName: "nc-terminal-pill"
        montre: c.mode === "terminal"
        Texte { anchors.verticalCenter: parent.verticalCenter; text: Etat.heure; font.weight: Font.DemiBold }
        Ico { anchors.verticalCenter: parent.verticalCenter; nom: "terminal"; taille: 17; color: Couleurs.accentClair }
        Texte { anchors.verticalCenter: parent.verticalCenter; text: Terminal.commandeAffichee; font.family: "monospace"; width: Math.min(implicitWidth, 170) }
        Texte { anchors.verticalCenter: parent.verticalCenter; text: Terminal.dureeTexte; font.weight: Font.DemiBold; color: Couleurs.accentClair; font.features: { "tnum": 1 } }
    }
    Fondu {
        id: terminalFini
        montre: c.mode === "terminal-fini"
        readonly property bool ok: Terminal.fini !== null && Terminal.fini.code === 0
        Ico { anchors.verticalCenter: parent.verticalCenter; nom: terminalFini.ok ? "check_circle" : "error"; taille: 17; color: terminalFini.ok ? Couleurs.vert : Couleurs.rouge }
        Texte {
            anchors.verticalCenter: parent.verticalCenter; font.weight: Font.DemiBold
            text: terminalFini.ok ? Reglages.t("Terminée", "Done") : Reglages.t("Échec (code " + (Terminal.fini ? Terminal.fini.code : 0) + ")", "Failed (exit " + (Terminal.fini ? Terminal.fini.code : 0) + ")")
        }
        Texte {
            anchors.verticalCenter: parent.verticalCenter; secondaire: true; font.family: "monospace"; width: Math.min(implicitWidth, 170)
            text: Terminal.finiAffichee
        }
        Texte { anchors.verticalCenter: parent.verticalCenter; secondaire: true; font.features: { "tnum": 1 }; text: Terminal.fini ? Etat.duree(Terminal.fini.duree) : "" }
    }

    // ── Résumé au réveil (Resume.qml) : soleil ou lune, puis météo, rendez-vous et mises à jour en court ──
    Fondu {
        id: resume
        objectName: "nc-resume-pill"
        montre: c.mode === "resume"
        Ico { anchors.verticalCenter: parent.verticalCenter; nom: Resume.soir ? "bedtime" : "wb_sunny"; taille: 18; color: Resume.soir ? Couleurs.accentClair : Couleurs.jaune }
        Texte { anchors.verticalCenter: parent.verticalCenter; text: Resume.salut; font.weight: Font.DemiBold }
        Texte { anchors.verticalCenter: parent.verticalCenter; text: Resume.court; secondaire: true; width: Math.min(implicitWidth, 260); font.features: { "tnum": 1 } }
    }

    // ── Mode jeu ──
    Fondu {
        id: jeu
        montre: c.mode === "jeu"
        Ico { anchors.verticalCenter: parent.verticalCenter; nom: "sports_esports"; taille: 19; color: Etat.jeu ? Couleurs.orange : Couleurs.texteSec }
        Texte { anchors.verticalCenter: parent.verticalCenter; text: Etat.jeu ? Reglages.t("Mode jeu", "Game Mode") : Reglages.t("Mode jeu désactivé", "Game Mode Off"); font.weight: Font.DemiBold }
    }
}

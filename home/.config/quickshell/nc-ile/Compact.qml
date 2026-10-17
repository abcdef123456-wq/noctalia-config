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
                                   : Etat.telecharge && !Etat.aMusique && !Agents.travaille ? "telechargement"
                                   : (Agents.attendTerminal ? "claude"
                                   : (Etat.aMusique ? "musique" : (Agents.travaille ? "claude" : (Etat.minuteurFin > 0 ? "minuteur" : "repos"))))
    readonly property real largeur: Math.max(110, actif.implicitWidth + 32)
    implicitHeight: 30

    readonly property Item actif: ({ repos: repos, musique: musique, volume: jauge, luminosite: jauge,
                                      piste: piste, charge: charge, profil: profil, jeu: jeu,
                                      minuteur: minuteur, "minuteur-fini": fini, micro: micro, casque: casque,
                                      claude: claude, "claude-fini": claudeFini, video: video,
                                      telechargement: telechargement, "telechargement-fini": telechargementFini })[mode] || repos

    component Fondu: Row {
        property bool montre: false
        anchors.centerIn: parent
        spacing: 9
        opacity: montre ? 1 : 0
        visible: opacity > 0.01
        Behavior on opacity { NumberAnimation { duration: 160; easing.type: Easing.OutCubic } }
    }

    // ── Repos : heure et date ──
    Fondu {
        id: repos
        montre: c.mode === "repos"
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
            Image { anchors.fill: parent; source: Etat.pochette; fillMode: Image.PreserveAspectCrop; asynchronous: true }
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
                    Behavior on height { NumberAnimation { duration: 70 } }
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
            text: (Etat.branche ? Reglages.t("En charge · ", "Charging · ") : Reglages.t("Sur batterie · ", "On Battery · ")) + Etat.pourcent + Reglages.t(" %", "%")
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
            text: Etat.profil === PowerProfile.PowerSaver ? Reglages.t("Économie", "Power Saver") : (Etat.profil === PowerProfile.Performance ? "Performance" : Reglages.t("Équilibré", "Balanced"))
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
        Etincelle { anchors.verticalCenter: parent.verticalCenter; taille: 16; tourne: !claude.terminal; visible: claude.montre || opacity > 0
                    agent: Agents.agent(claude.terminal ? Agents.attend : claude.s) }
        Texte {
            anchors.verticalCenter: parent.verticalCenter
            text: claude.terminal ? Agents.nom(Agents.attend) + Reglages.t(" t'attend dans le terminal", " is waiting in the terminal")
                                  : (claude.s ? (claude.s.etape || Reglages.t("Travaille…", "Working…")) : "")
            font.weight: Font.DemiBold; color: claude.terminal ? Couleurs.orange : Couleurs.texte
            width: Math.min(implicitWidth, 250)
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
        Ico {
            anchors.verticalCenter: parent.verticalCenter; nom: "arrow_downward"; taille: 17; color: Couleurs.accent
            SequentialAnimation on anchors.verticalCenterOffset { running: telechargement.montre; loops: Animation.Infinite
                NumberAnimation { from: -3; to: 3; duration: 600; easing.type: Easing.InOutSine }
                NumberAnimation { from: 3; to: -3; duration: 600; easing.type: Easing.InOutSine } }
        }
        Texte {
            anchors.verticalCenter: parent.verticalCenter; font.weight: Font.DemiBold; width: Math.min(implicitWidth, 190)
            text: telechargement.t ? telechargement.t.nom : ""
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
        Texte { anchors.verticalCenter: parent.verticalCenter; text: Reglages.t("Téléchargé", "Downloaded"); font.weight: Font.DemiBold }
        Texte { anchors.verticalCenter: parent.verticalCenter; text: Etat.telechargeFini; secondaire: true; width: Math.min(implicitWidth, 200) }
    }
    Fondu {
        id: video
        montre: c.mode === "video"
        Rectangle {
            anchors.verticalCenter: parent.verticalCenter; width: 10; height: 10; radius: 5; color: Couleurs.rouge
            SequentialAnimation on opacity { running: video.montre; loops: Animation.Infinite
                NumberAnimation { to: 0.35; duration: 700 } NumberAnimation { to: 1; duration: 700 } }
        }
        Texte {
            anchors.verticalCenter: parent.verticalCenter; font.weight: Font.DemiBold; font.features: { "tnum": 1 }
            text: Etat.duree(Math.max(0, Math.floor(Etat.maintenant.getTime() / 1000 - Etat.debutVideo)))
        }
        Ico { anchors.verticalCenter: parent.verticalCenter; nom: "stop_circle"; taille: 17; color: Couleurs.texteSec }
    }

    // ── Mode jeu ──
    Fondu {
        id: jeu
        montre: c.mode === "jeu"
        Ico { anchors.verticalCenter: parent.verticalCenter; nom: "sports_esports"; taille: 19; color: Etat.jeu ? Couleurs.orange : Couleurs.texteSec }
        Texte { anchors.verticalCenter: parent.verticalCenter; text: Etat.jeu ? Reglages.t("Mode jeu", "Game Mode") : Reglages.t("Mode jeu désactivé", "Game Mode Off"); font.weight: Font.DemiBold }
    }
}

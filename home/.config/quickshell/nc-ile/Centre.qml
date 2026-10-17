// Centre de contrôle de l'île (île ouverte), dans le langage du Centre de contrôle d'iOS.
// Appui long (ou clic droit) sur Wi-Fi, Bluetooth ou le volume : page de détails.
import QtQuick
import Quickshell
import Quickshell.Widgets
import Quickshell.Services.UPower

Item {
    id: centre
    readonly property color bleu: Couleurs.accent
    readonly property color orange: Couleurs.orange
    readonly property color indigo: Couleurs.violet
    readonly property color rose: Couleurs.rose
    readonly property color vert: Couleurs.vert
    readonly property var s: Etat.sys


    // ── Accueil ──
    Column {
        id: accueil
        anchors.fill: parent
        spacing: 12

        // En-tête : date, batterie
        Item {
            width: parent.width; height: 22
            Texte { anchors.left: parent.left; anchors.leftMargin: 6; text: Etat.dateLongue; secondaire: true; font.weight: Font.DemiBold }
            Row {
                anchors.right: parent.right; anchors.rightMargin: 6; spacing: 5
                visible: Etat.aBatterie
                Texte { text: Etat.pourcent + Reglages.t(" %", "%"); font.weight: Font.DemiBold }
                Ico {
                    nom: Etat.branche ? "battery_charging_full" : (Etat.pourcent > 80 ? "battery_full" : (Etat.pourcent > 30 ? "battery_5_bar" : "battery_2_bar"))
                    taille: 18; color: Etat.branche ? centre.vert : (Etat.pourcent <= 20 ? Couleurs.rouge : Couleurs.texte)
                    rotation: 90
                }
            }
        }

        // Connexions | Musique
        Row {
            width: parent.width; height: 168; spacing: 12
            // Connexions façon macOS : rond (activer / couper) + nom et état (clic : liste des réseaux / appareils)
            Module {
                width: 168; height: 168
                Column {
                    anchors.fill: parent; anchors.margins: 12; spacing: 8
                    Repeater {
                        model: [
                            { cle: "wifi", icone: "wifi", nom: "Wi-Fi", page: "reseau" },
                            { cle: "bluetooth", icone: "bluetooth", nom: "Bluetooth", page: "bluetooth" },
                            { cle: "dnd", icone: "dark_mode", nom: Reglages.t("Concentration", "Focus"), page: "notifications" }
                        ]
                        Item {
                            id: lc
                            required property var modelData
                            readonly property bool actif: modelData.cle === "dnd" ? Notifs.concentration : centre.s[modelData.cle] === "on"
                            readonly property string etat: modelData.cle === "wifi" ? (actif ? (centre.s.reseau || Reglages.t("Activé", "On")) : Reglages.t("Désactivé", "Off"))
                                                        : modelData.cle === "dnd" ? (actif ? Reglages.t("Ne pas déranger", "Do Not Disturb") : Reglages.t("Désactivée", "Off"))
                                                        : (actif ? Reglages.t("Activé", "On") : Reglages.t("Désactivé", "Off"))
                            width: parent.width; height: 41
                            Rectangle {
                                anchors.fill: parent; anchors.leftMargin: -6; anchors.rightMargin: -6; radius: 12
                                color: zl.containsMouse && lc.modelData.page !== "" ? Couleurs.gris2 : "transparent"
                                Behavior on color { ColorAnimation { duration: 120 } }
                            }
                            Rond {
                                id: rl
                                anchors.verticalCenter: parent.verticalCenter
                                taille: 36; icone: lc.modelData.icone; actif: lc.actif
                                couleur: lc.modelData.cle === "dnd" ? centre.indigo : centre.bleu
                                onClic: lc.modelData.cle === "dnd" ? Notifs.basculerConcentration() : Etat.faire(["noctalia", "msg", lc.modelData.cle + "-toggle"])
                            }
                            Column {
                                anchors.left: rl.right; anchors.leftMargin: 9; anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter
                                Texte { text: lc.modelData.nom; font.weight: Font.DemiBold; font.pixelSize: 13; width: parent.width }
                                Texte { text: lc.etat; secondaire: true; font.pixelSize: 11; width: parent.width }
                            }
                            MouseArea {
                                id: zl
                                anchors.fill: parent; anchors.leftMargin: 40
                                hoverEnabled: true
                                onClicked: lc.modelData.page !== "" ? Etat.aller(lc.modelData.page) : rl.clic()
                            }
                        }
                    }
                }
            }
            Module {
                width: parent.width - 180; height: 168
                Column {
                    anchors.fill: parent; anchors.margins: 14; spacing: 10
                    Row {
                        spacing: 10; width: parent.width
                        ClippingRectangle {
                            width: 54; height: 54; radius: 12; color: Couleurs.gris2
                            Image { anchors.fill: parent; source: Etat.pochette; fillMode: Image.PreserveAspectCrop; asynchronous: true }
                            Image { anchors.centerIn: parent; width: 34; height: 34; source: Etat.pochette === "" ? Etat.iconeLecteur : ""; sourceSize: Qt.size(68, 68); visible: Etat.pochette === "" }
                            Ico { anchors.centerIn: parent; nom: "music_note"; taille: 26; color: Couleurs.texteSec; visible: Etat.pochette === "" && Etat.iconeLecteur === "" }
                        }
                        Column {
                            width: parent.width - 64; spacing: 2
                            anchors.verticalCenter: parent.verticalCenter
                            Texte { width: parent.width; text: Etat.titre !== "" ? Etat.titre : Reglages.t("Rien en lecture", "Not Playing"); font.weight: Font.DemiBold; font.pixelSize: 14 }
                            Texte { width: parent.width; text: Etat.artiste !== "" ? Etat.artiste : (Etat.lecteur ? Etat.lecteur.identity : Reglages.t("Lance une musique", "Play some music")); secondaire: true }
                        }
                    }
                    // Progression
                    Rectangle {
                        width: parent.width; height: 4; radius: 2; color: Couleurs.gris3
                        Rectangle {
                            height: parent.height; radius: 2; color: Couleurs.texte
                            width: Etat.lecteur && Etat.lecteur.length > 0 ? parent.width * Math.min(1, Etat.lecteur.position / Etat.lecteur.length) : 0
                        }
                    }
                    // Commandes
                    Row {
                        anchors.horizontalCenter: parent.horizontalCenter; spacing: 26
                        component Commande: Ico {
                            id: cmd
                            signal clic()
                            color: Etat.lecteur ? Couleurs.texte : Couleurs.gris4
                            scale: z.pressed ? 0.85 : 1
                            Behavior on scale { SpringAnimation { spring: 6; damping: 0.4 } }
                            MouseArea { id: z; anchors.fill: parent; anchors.margins: -8; onClicked: cmd.clic() }
                        }
                        Commande { nom: "fast_rewind"; taille: 30; onClic: if (Etat.lecteur) Etat.lecteur.previous() }
                        Commande { nom: Etat.joue ? "pause" : "play_arrow"; taille: 38; onClic: Etat.lecturePause() }
                        Commande { nom: "fast_forward"; taille: 30; onClic: if (Etat.lecteur) Etat.lecteur.next() }
                    }
                }
            }
        }

        // Nuit, Mode jeu | Luminosité | Volume
        Row {
            width: parent.width; height: 168; spacing: 12
            Column {
                width: 168; spacing: 12
                component Pastille: Module {
                    id: pa
                    property string icone
                    property string titre
                    property string sous
                    property bool actif
                    property color couleur
                    width: 168; height: 78; cliquable: true
                    Row {
                        anchors.verticalCenter: parent.verticalCenter; anchors.left: parent.left; anchors.leftMargin: 12; spacing: 10
                        Rectangle {
                            width: 40; height: 40; radius: 20; color: pa.actif ? pa.couleur : Couleurs.gris3
                            Behavior on color { ColorAnimation { duration: 160 } }
                            Ico { anchors.centerIn: parent; nom: pa.icone; taille: 21; color: pa.actif ? Couleurs.surCouleur : Couleurs.texte }
                        }
                        Column {
                            anchors.verticalCenter: parent.verticalCenter
                            Texte { text: pa.titre; font.weight: Font.DemiBold }
                            Texte { text: pa.sous; secondaire: true; font.pixelSize: 11 }
                        }
                    }
                }
                Pastille {
                    icone: "wb_twilight"; titre: Reglages.t("Nuit", "Night Shift"); sous: Etat.nuit ? Reglages.t("Tons chauds", "Warmer colors") : Reglages.t("Désactivée", "Off"); actif: Etat.nuit; couleur: centre.orange
                    onClic: { Etat.nuit = !Etat.nuit; Etat.faire(["noctalia", "msg", "nightlight-force-toggle"]) }
                }
                Pastille {
                    icone: "sports_esports"; titre: Reglages.t("Mode jeu", "Game Mode"); sous: Etat.jeu ? Reglages.t("Effets coupés", "Effects off") : Reglages.t("Désactivé", "Off"); actif: Etat.jeu; couleur: centre.orange
                    onClic: Etat.faire(["hyprctl", "eval", "nc.mode_jeu()"])
                }
            }
            Glissiere {
                width: (parent.width - 168 - 24) / 2; height: 168
                icone: "light_mode"; valeur: Etat.luminosite
                onChange: v => Etat.reglerLuminosite(v)
            }
            Glissiere {
                width: (parent.width - 168 - 24) / 2; height: 168
                icone: Etat.muet ? "volume_off" : (Etat.volume < 0.34 ? "volume_mute" : (Etat.volume < 0.67 ? "volume_down" : "volume_up"))
                valeur: Etat.muet ? 0 : Etat.volume
                onChange: v => Etat.reglerVolume(v)
                onAppuiLong: Etat.aller("son")
            }
        }

        // Énergie : module façon macOS. Clic : mode suivant ; flèche, appui long ou clic droit : liste des modes
        Module {
            id: energie
            readonly property var modes: [
                { nom: Reglages.t("Économie", "Power Saver"), icone: "battery_saver", couleur: Couleurs.jaune, texte: Couleurs.surCouleur, p: PowerProfile.PowerSaver },
                { nom: Reglages.t("Équilibré", "Balanced"), icone: "battery_full", couleur: Couleurs.gris3, texte: Couleurs.texte, p: PowerProfile.Balanced },
                { nom: "Performance", icone: "bolt", couleur: Couleurs.orange, texte: Couleurs.surCouleur, p: PowerProfile.Performance }
            ]
            readonly property int index: Etat.profil === PowerProfile.PowerSaver ? 0 : (Etat.profil === PowerProfile.Performance ? 2 : 1)
            readonly property var mode: modes[index]
            width: parent.width; height: 64; cliquable: true
            onClic: Etat.choisirProfil(modes[(index + 1) % 3].p)
            onAppuiLong: Etat.aller("systeme")
            Row {
                anchors.verticalCenter: parent.verticalCenter; anchors.left: parent.left; anchors.leftMargin: 12; spacing: 12
                Rectangle {
                    width: 40; height: 40; radius: 20; color: energie.mode.couleur
                    Behavior on color { ColorAnimation { duration: 200 } }
                    Ico { anchors.centerIn: parent; nom: energie.mode.icone; taille: 22; color: energie.mode.texte; rotation: energie.mode.icone === "bolt" ? 0 : 90 }
                }
                Column {
                    anchors.verticalCenter: parent.verticalCenter
                    Texte { text: Reglages.t("Énergie", "Power"); font.weight: Font.DemiBold; font.pixelSize: 14 }
                    Texte { text: energie.mode.nom; secondaire: true }
                }
            }
            Ico {
                anchors.right: parent.right; anchors.rightMargin: 16; anchors.verticalCenter: parent.verticalCenter
                nom: "chevron_right"; taille: 24; color: Couleurs.texteSec
                MouseArea { anchors.fill: parent; anchors.margins: -10; onClicked: Etat.aller("systeme") }
            }
        }
    }
}

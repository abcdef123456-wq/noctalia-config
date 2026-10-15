// Centre de contrôle de l'île (île ouverte), dans le langage du Centre de contrôle d'iOS.
// Appui long (ou clic droit) sur Wi-Fi, Bluetooth ou le volume : page de détails.
import QtQuick
import Quickshell
import Quickshell.Widgets
import Quickshell.Services.UPower

Item {
    id: centre
    readonly property color bleu: "#0a84ff"
    readonly property color orange: "#ff9f0a"
    readonly property color indigo: "#5e5ce6"
    readonly property color rose: "#ff375f"
    readonly property color vert: "#30d158"
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
                Texte { text: Etat.pourcent + " %"; font.weight: Font.DemiBold }
                Ico {
                    nom: Etat.branche ? "battery_charging_full" : (Etat.pourcent > 80 ? "battery_full" : (Etat.pourcent > 30 ? "battery_5_bar" : "battery_2_bar"))
                    taille: 18; color: Etat.branche ? centre.vert : (Etat.pourcent <= 20 ? "#ff453a" : "white")
                    rotation: 90
                }
            }
        }

        // Connexions | Musique
        Row {
            width: parent.width; height: 168; spacing: 12
            Module {
                width: 168; height: 168
                Grid {
                    anchors.centerIn: parent; columns: 2; spacing: 14
                    Rond {
                        icone: centre.s.wifi === "on" ? "wifi" : "wifi_off"; actif: centre.s.wifi === "on"; couleur: centre.bleu
                        onClic: Etat.faire(["noctalia", "msg", "wifi-toggle"]); onAppuiLong: Etat.aller("reseau")
                    }
                    Rond {
                        icone: "bluetooth"; actif: centre.s.bluetooth === "on"; couleur: centre.bleu
                        onClic: Etat.faire(["noctalia", "msg", "bluetooth-toggle"]); onAppuiLong: Etat.aller("bluetooth")
                    }
                    Rond {
                        icone: "dark_mode"; actif: centre.s.dnd === "on"; couleur: centre.indigo
                        onClic: Etat.faire(["noctalia", "msg", "notification-dnd-toggle"])
                    }
                    Rond {
                        icone: "sports_esports"; actif: Etat.jeu; couleur: centre.orange
                        onClic: Etat.faire(["hyprctl", "eval", "nc.mode_jeu()"])
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
                            width: 54; height: 54; radius: 12; color: "#2c2c2e"
                            Image { anchors.fill: parent; source: Etat.pochette; fillMode: Image.PreserveAspectCrop; asynchronous: true }
                            Ico { anchors.centerIn: parent; nom: "music_note"; taille: 26; color: "#98989d"; visible: Etat.pochette === "" }
                        }
                        Column {
                            width: parent.width - 64; spacing: 2
                            anchors.verticalCenter: parent.verticalCenter
                            Texte { width: parent.width; text: Etat.titre !== "" ? Etat.titre : "Rien en lecture"; font.weight: Font.DemiBold; font.pixelSize: 14 }
                            Texte { width: parent.width; text: Etat.artiste !== "" ? Etat.artiste : (Etat.lecteur ? Etat.lecteur.identity : "Lance une musique"); secondaire: true }
                        }
                    }
                    // Progression
                    Rectangle {
                        width: parent.width; height: 4; radius: 2; color: "#3a3a3c"
                        Rectangle {
                            height: parent.height; radius: 2; color: "white"
                            width: Etat.lecteur && Etat.lecteur.length > 0 ? parent.width * Math.min(1, Etat.lecteur.position / Etat.lecteur.length) : 0
                        }
                    }
                    // Commandes
                    Row {
                        anchors.horizontalCenter: parent.horizontalCenter; spacing: 26
                        component Commande: Ico {
                            id: cmd
                            signal clic()
                            color: Etat.lecteur ? "white" : "#48484a"
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

        // Nuit, Halo | Luminosité | Volume
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
                            width: 40; height: 40; radius: 20; color: pa.actif ? pa.couleur : "#3a3a3c"
                            Behavior on color { ColorAnimation { duration: 160 } }
                            Ico { anchors.centerIn: parent; nom: pa.icone; taille: 21 }
                        }
                        Column {
                            anchors.verticalCenter: parent.verticalCenter
                            Texte { text: pa.titre; font.weight: Font.DemiBold }
                            Texte { text: pa.sous; secondaire: true; font.pixelSize: 11 }
                        }
                    }
                }
                Pastille {
                    icone: "wb_twilight"; titre: "Nuit"; sous: Etat.nuit ? "Tons chauds" : "Désactivée"; actif: Etat.nuit; couleur: centre.orange
                    onClic: { Etat.nuit = !Etat.nuit; Etat.faire(["noctalia", "msg", "nightlight-force-toggle"]) }
                }
                Pastille {
                    icone: "graphic_eq"; titre: "Halo"; sous: centre.s.halo === "1" ? "Musique" : "Coupé"; actif: centre.s.halo === "1"; couleur: centre.rose
                    onClic: Etat.faire(["systemctl", "--user", centre.s.halo === "1" ? "stop" : "start", "nc-pouls"])
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
                { nom: "Économie", icone: "battery_saver", couleur: "#ffd60a", texte: "#1c1c1e", p: PowerProfile.PowerSaver },
                { nom: "Équilibré", icone: "battery_full", couleur: "#3a3a3c", texte: "white", p: PowerProfile.Balanced },
                { nom: "Performance", icone: "bolt", couleur: "#ff9f0a", texte: "white", p: PowerProfile.Performance }
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
                    Texte { text: "Énergie"; font.weight: Font.DemiBold; font.pixelSize: 14 }
                    Texte { text: energie.mode.nom; secondaire: true }
                }
            }
            Ico {
                anchors.right: parent.right; anchors.rightMargin: 16; anchors.verticalCenter: parent.verticalCenter
                nom: "chevron_right"; taille: 24; color: "#98989d"
                MouseArea { anchors.fill: parent; anchors.margins: -10; onClicked: Etat.aller("systeme") }
            }
        }

        // Raccourcis (ceux de l'ancien centre de contrôle) : café anti-veille, thème, clavier, presse-papiers, fond, minuteur
        Row {
            anchors.horizontalCenter: parent.horizontalCenter
            spacing: (parent.width - 6 * 48) / 5
            Rond { taille: 48; icone: "coffee"; actif: Etat.cafe; couleur: "#ac8e68"; onClic: Etat.basculerCafe() }
            Rond { taille: 48; icone: "contrast"; onClic: Etat.faire(["noctalia", "msg", "theme-mode-toggle"]) }
            Rond { taille: 48; icone: "keyboard"; onClic: Etat.faire(["noctalia", "msg", "keyboard-layout-cycle"]) }
            Rond { taille: 48; icone: "content_paste"; onClic: { Etat.fermer(); Quickshell.execDetached(["noctalia", "msg", "panel-toggle", "launcher", "/clipboard"]) } }
            Rond { taille: 48; icone: "wallpaper"; onClic: { Etat.fermer(); Quickshell.execDetached([Etat.bin + "nc-shell-msg", "wallpapers"]) } }
            Rond { taille: 48; icone: "timer"; actif: Etat.minuteurFin > 0; couleur: "#ff9f0a"; onClic: Etat.aller("minuteur") }
        }

        // Ligne discrète d'actions (façon macOS) : les icônes ne s'éclairent qu'au survol
        Row {
            anchors.horizontalCenter: parent.horizontalCenter
            height: 40; spacing: 30
            Repeater {
                model: [
                    { icone: "photo_camera", cmd: ["sh", "-c", "sleep 0.4; noctalia msg screenshot-annotate"] },
                    { icone: "notifications", cmd: ["noctalia", "msg", "panel-toggle", "control-center"] },
                    { icone: "settings", cmd: ["noctalia", "msg", "settings-open"] },
                    { icone: "lock", cmd: ["noctalia", "msg", "session", "lock"] },
                    { icone: "power_settings_new", cmd: ["noctalia", "msg", "panel-toggle", "session-panel"] }
                ]
                Rectangle {
                    required property var modelData
                    width: 40; height: 40; radius: 20
                    color: zone.containsMouse ? "#2c2c2e" : "transparent"
                    Behavior on color { ColorAnimation { duration: 140 } }
                    scale: zone.pressed ? 0.88 : 1
                    Behavior on scale { SpringAnimation { spring: 6; damping: 0.4 } }
                    Ico { anchors.centerIn: parent; nom: modelData.icone; taille: 22; color: zone.containsMouse ? "white" : "#c7c7cc" }
                    MouseArea {
                        id: zone
                        anchors.fill: parent; hoverEnabled: true
                        onClicked: { Etat.fermer(); Quickshell.execDetached(modelData.cmd) }
                    }
                }
            }
        }
    }

}

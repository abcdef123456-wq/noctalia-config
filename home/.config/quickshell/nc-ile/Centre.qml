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

    // Petit module carré d'action (façon iOS)
    component Tuile: Module {
        id: ac
        property string icone
        radius: 18; cliquable: true
        Ico { anchors.centerIn: parent; nom: ac.icone; taille: 26 }
    }

    // ── Accueil ──
    Column {
        id: accueil
        anchors.fill: parent
        spacing: 12
        opacity: Etat.page === "accueil" ? 1 : 0
        visible: opacity > 0.01
        Behavior on opacity { NumberAnimation { duration: 180 } }

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
                        onClic: Etat.faire(["noctalia", "msg", "wifi-toggle"]); onAppuiLong: Etat.aller("wifi")
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

        // Profil d'énergie : sélecteur segmenté façon iOS (l'indicateur glisse)
        Rectangle {
            id: segments
            width: parent.width; height: 40; radius: 13; color: "#1c1c1e"
            readonly property int index: Etat.profil === PowerProfile.PowerSaver ? 0 : (Etat.profil === PowerProfile.Performance ? 2 : 1)
            Rectangle {
                width: (parent.width - 6) / 3; height: parent.height - 6; y: 3; radius: 10; color: "#636366"
                x: 3 + segments.index * (parent.width - 6) / 3
                Behavior on x { SpringAnimation { spring: 4; damping: 0.45 } }
            }
            Row {
                anchors.fill: parent; anchors.margins: 3
                Repeater {
                    model: [
                        { nom: "Économie", icone: "eco", couleur: "#30d158", p: PowerProfile.PowerSaver },
                        { nom: "Équilibré", icone: "balance", couleur: "white", p: PowerProfile.Balanced },
                        { nom: "Performance", icone: "bolt", couleur: "#ff9f0a", p: PowerProfile.Performance }
                    ]
                    Item {
                        required property var modelData
                        required property int index
                        width: (segments.width - 6) / 3; height: segments.height - 6
                        Texte {
                            anchors.centerIn: parent
                            text: modelData.nom
                            font.pixelSize: 13
                            font.weight: segments.index === index ? Font.DemiBold : Font.Medium
                            secondaire: segments.index !== index
                        }
                        MouseArea { anchors.fill: parent; onClicked: Etat.choisirProfil(modelData.p) }
                    }
                }
            }
        }

        // Actions : petits modules carrés façon iOS (lampe, minuteur, appareil photo…)
        Row {
            id: actions
            width: parent.width; height: 58; spacing: 10
            readonly property real largeurTuile: (width - 4 * spacing) / 5
            Tuile { width: actions.largeurTuile; height: actions.height; icone: "photo_camera"; onClic: { Etat.fermer(); Quickshell.execDetached(["sh", "-c", "sleep 0.4; noctalia msg screenshot-annotate"]) } }
            Tuile { width: actions.largeurTuile; height: actions.height; icone: "notifications"; onClic: { Etat.fermer(); Quickshell.execDetached(["noctalia", "msg", "panel-toggle", "control-center"]) } }
            Tuile { width: actions.largeurTuile; height: actions.height; icone: "settings"; onClic: { Etat.fermer(); Quickshell.execDetached(["noctalia", "msg", "settings-open"]) } }
            Tuile { width: actions.largeurTuile; height: actions.height; icone: "lock"; onClic: { Etat.fermer(); Quickshell.execDetached(["noctalia", "msg", "session", "lock"]) } }
            Tuile { width: actions.largeurTuile; height: actions.height; icone: "power_settings_new"; onClic: { Etat.fermer(); Quickshell.execDetached(["noctalia", "msg", "panel-toggle", "session-panel"]) } }
        }
    }

    // ── Pages : Wi-Fi, Bluetooth, Son ──
    PageListe {
        anchors.fill: parent
        opacity: Etat.page !== "accueil" ? 1 : 0
        visible: opacity > 0.01
        Behavior on opacity { NumberAnimation { duration: 180 } }
    }
}

// Pages de détails de l'île : réseaux Wi-Fi (mot de passe tapé ici), appareils Bluetooth, sorties et micro.
// Listes lues par ~/.local/bin/nc-ile-etat wifi | bt | son.
import QtQuick
import Quickshell.Services.UPower

Item {
    id: p
    property string saisie: ""          // réseau dont on tape le mot de passe

    readonly property string titre: ({ wifi: "Wi-Fi", bluetooth: "Bluetooth", son: "Son", energie: "Énergie" })[Etat.page] || ""
    readonly property bool interrupteur: Etat.page === "wifi" || Etat.page === "bluetooth"
    readonly property bool allume: Etat.page === "wifi" ? Etat.sys.wifi === "on" : Etat.sys.bluetooth === "on"
    onVisibleChanged: saisie = ""

    // En-tête : retour, titre, interrupteur
    Item {
        id: tete
        width: parent.width; height: 40
        Rectangle {
            width: 34; height: 34; radius: 17; color: "#2c2c2e"
            anchors.verticalCenter: parent.verticalCenter
            Ico { anchors.centerIn: parent; nom: "chevron_left"; taille: 24 }
            MouseArea { anchors.fill: parent; onClicked: Etat.page = "accueil" }
        }
        Texte { x: 46; anchors.verticalCenter: parent.verticalCenter; text: p.titre; font.pixelSize: 20; font.weight: Font.Bold }
        // Interrupteur façon iOS
        Rectangle {
            visible: p.interrupteur
            anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter
            width: 51; height: 31; radius: 15.5; color: p.allume ? "#30d158" : "#3a3a3c"
            Behavior on color { ColorAnimation { duration: 180 } }
            Rectangle {
                width: 27; height: 27; radius: 13.5; color: "white"; y: 2
                x: p.allume ? 22 : 2
                Behavior on x { SpringAnimation { spring: 5; damping: 0.5 } }
            }
            MouseArea {
                anchors.fill: parent
                onClicked: Etat.faire(["noctalia", "msg", Etat.page === "wifi" ? "wifi-toggle" : "bluetooth-toggle"])
            }
        }
    }

    // Page Énergie : les trois modes, façon Réglages d'Apple
    Column {
        anchors.top: tete.bottom; anchors.topMargin: 14
        width: parent.width; spacing: 6
        visible: Etat.page === "energie"
        Repeater {
            model: [
                { nom: "Économie", detail: "Autonomie maximale, sans effets", icone: "battery_saver", couleur: "#ffd60a", texte: "#1c1c1e", p: 0 },
                { nom: "Équilibré", detail: "Le bon compromis au quotidien", icone: "battery_full", couleur: "#3a3a3c", texte: "white", p: 1 },
                { nom: "Performance", detail: "Puissance maximale, carte NVIDIA", icone: "bolt", couleur: "#ff9f0a", texte: "white", p: 2 }
            ]
            Module {
                required property var modelData
                readonly property var profils: [PowerProfile.PowerSaver, PowerProfile.Balanced, PowerProfile.Performance]
                readonly property bool actif: Etat.profil === profils[modelData.p]
                width: parent.width; height: 64; radius: 16; cliquable: true
                onClic: Etat.choisirProfil(profils[modelData.p])
                Row {
                    anchors.verticalCenter: parent.verticalCenter; anchors.left: parent.left; anchors.leftMargin: 12; spacing: 12
                    Rectangle {
                        width: 36; height: 36; radius: 18; color: modelData.couleur
                        Ico { anchors.centerIn: parent; nom: modelData.icone; taille: 20; color: modelData.texte; rotation: modelData.icone === "bolt" ? 0 : 90 }
                    }
                    Column {
                        anchors.verticalCenter: parent.verticalCenter
                        Texte { text: modelData.nom; font.weight: Font.DemiBold; font.pixelSize: 14 }
                        Texte { text: modelData.detail; secondaire: true; font.pixelSize: 12 }
                    }
                }
                Ico { anchors.right: parent.right; anchors.rightMargin: 16; anchors.verticalCenter: parent.verticalCenter; nom: "check"; taille: 22; color: "#0a84ff"; visible: parent.actif }
            }
        }
    }

    ListView {
        id: vue
        anchors.top: tete.bottom; anchors.topMargin: 14
        anchors.bottom: parent.bottom
        width: parent.width
        clip: true
        spacing: 6
        model: Etat.liste.filter(e => (Etat.page === "wifi" && e.genre === "net") || (Etat.page === "bluetooth" && e.genre === "bt")
                                      || (Etat.page === "son" && (e.genre === "sortie" || e.genre === "entree")))
        section.property: "genre"
        delegate: Column {
            id: d
            required property var modelData
            readonly property var f: modelData.champs
            readonly property string genre: modelData.genre
            // Champs : net = actif, nom, signal, sécurité, connu ; bt = adresse, nom, connecté, icône ; son = id, nom, défaut
            readonly property bool actif: genre === "net" ? f[0] === "1" : (genre === "bt" ? f[2] === "1" : f[2] === "1")
            readonly property string nom: f[1] || ""
            readonly property string icone: genre === "net" ? (parseInt(f[2]) >= 67 ? "wifi" : (parseInt(f[2]) >= 34 ? "wifi_2_bar" : "wifi_1_bar"))
                : genre === "bt" ? ((f[3] || "").indexOf("audio") >= 0 ? "headphones" : ((f[3] || "").indexOf("phone") >= 0 ? "smartphone"
                    : ((f[3] || "").indexOf("mouse") >= 0 ? "mouse" : ((f[3] || "").indexOf("keyboard") >= 0 ? "keyboard" : "bluetooth"))))
                : genre === "sortie" ? (nom.toLowerCase().indexOf("hdmi") >= 0 || nom.indexOf("GB2") >= 0 ? "tv" : "speaker") : "mic"
            readonly property string sous: genre === "net" ? (actif ? "Connecté" : (f[4] === "1" ? "Enregistré" : (f[3] === "1" ? "Sécurisé" : "Ouvert")))
                : genre === "bt" ? (actif ? "Connecté" : "Non connecté")
                : genre === "sortie" ? (actif ? "Sortie utilisée" : "Sortie") : (actif ? (Etat.microMuet ? "Micro utilisé · coupé" : "Micro utilisé") : "Micro")
            width: vue.width
            spacing: 6

            Module {
                width: parent.width; height: 56; radius: 16; cliquable: true
                Row {
                    anchors.verticalCenter: parent.verticalCenter; anchors.left: parent.left; anchors.leftMargin: 12; spacing: 12
                    Rectangle {
                        width: 34; height: 34; radius: 17; color: d.actif ? "#0a84ff" : "#3a3a3c"
                        Ico { anchors.centerIn: parent; nom: d.icone; taille: 19 }
                    }
                    Column {
                        anchors.verticalCenter: parent.verticalCenter
                        Texte { text: d.nom; font.weight: Font.DemiBold; font.pixelSize: 14; width: Math.min(implicitWidth, 270) }
                        Texte { text: d.sous; font.pixelSize: 12; color: d.actif ? "#0a84ff" : "#98989d" }
                    }
                }
                Ico {
                    anchors.right: parent.right; anchors.rightMargin: 16; anchors.verticalCenter: parent.verticalCenter
                    nom: d.genre === "entree" && d.actif ? (Etat.microMuet ? "mic_off" : "mic") : (d.actif ? "check" : (d.genre === "net" && d.f[3] === "1" ? "lock" : ""))
                    taille: 20; color: d.genre === "entree" && Etat.microMuet ? "#ff453a" : (d.actif ? "#0a84ff" : "#98989d")
                    MouseArea { anchors.fill: parent; anchors.margins: -8; enabled: d.genre === "entree" && d.actif; onClicked: Etat.basculerMicro() }
                }
                onClic: {
                    if (d.genre === "net") {
                        if (d.actif) return
                        if (d.f[3] === "1" && d.f[4] !== "1") { p.saisie = d.nom; return }
                        Etat.faire(d.f[4] === "1" ? ["nmcli", "con", "up", "id", d.nom] : ["nmcli", "dev", "wifi", "connect", d.nom])
                    } else if (d.genre === "bt") {
                        Etat.faire(["bluetoothctl", d.actif ? "disconnect" : "connect", d.f[0]])
                    } else {
                        Etat.faire(["wpctl", "set-default", d.f[0]])
                    }
                }
            }
            // Mot de passe du réseau choisi
            Rectangle {
                visible: p.saisie === d.nom && d.genre === "net"
                width: parent.width; height: 44; radius: 14; color: "#2c2c2e"
                TextInput {
                    id: mdp
                    anchors.fill: parent; anchors.leftMargin: 14; anchors.rightMargin: 14
                    verticalAlignment: TextInput.AlignVCenter
                    color: "white"; font.pixelSize: 14; echoMode: TextInput.Password
                    onVisibleChanged: if (visible) { text = ""; forceActiveFocus() }
                    onAccepted: { Etat.faire(["nmcli", "dev", "wifi", "connect", d.nom, "password", text]); p.saisie = "" }
                    Texte { visible: mdp.text === ""; text: "Mot de passe de « " + d.nom + " »"; secondaire: true; anchors.verticalCenter: parent.verticalCenter }
                }
            }
        }
    }
}

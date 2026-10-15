// Pages Wi-Fi et Bluetooth de l'île, façon macOS (mode : "wifi" ou "bluetooth").
//   Wi-Fi : réseau actuel en tête, autres réseaux ; clic : se connecter (mot de passe tapé ici si besoin) ;
//           clic droit sur un réseau enregistré : l'oublier.
//   Bluetooth : connectés, associés, puis appareils à proximité (« Rechercher ») ; clic : connecter / déconnecter /
//               associer ; clic droit : oublier l'appareil.
// Listes lues par ~/.local/bin/nc-ile-etat wifi | bt.
import QtQuick
import Quickshell

Item {
    id: p
    property string mode: "wifi"
    property string saisie: ""          // réseau dont on tape le mot de passe
    property var attente: ({})          // connexions en cours (nom ou adresse -> vrai)
    property bool recherche: false
    function defiler(dy) { return defil.defiler(dy) }

    readonly property bool wifi: mode === "wifi"
    readonly property bool allume: wifi ? Etat.sys.wifi === "on" : Etat.sys.bluetooth === "on"
    readonly property var elements: Etat.liste.filter(e => e.genre === (wifi ? "net" : "bt"))
    onVisibleChanged: { saisie = ""; attente = ({}) }

    function attendre(cle) { var a = Object.assign({}, attente); a[cle] = true; attente = a; finAttente.restart() }
    Timer { id: finAttente; interval: 15000; onTriggered: p.attente = ({}) }

    // Wi-Fi — champs : actif, nom, signal, sécurisé, enregistré
    readonly property var actuel: wifi ? elements.filter(e => e.champs[0] === "1") : []
    readonly property var autres: wifi ? elements.filter(e => e.champs[0] !== "1") : []
    // Bluetooth — champs : adresse, nom, connecté, icône, associé
    readonly property var connectes: !wifi ? elements.filter(e => e.champs[2] === "1") : []
    readonly property var associes: !wifi ? elements.filter(e => e.champs[2] !== "1" && e.champs[4] === "1") : []
    readonly property var proches: !wifi ? elements.filter(e => e.champs[2] !== "1" && e.champs[4] !== "1") : []

    function iconeWifi(f) { var s = parseInt(f[2]) || 0; return s >= 67 ? "wifi" : (s >= 34 ? "wifi_2_bar" : "wifi_1_bar") }
    function iconeBt(f) {
        var i = f[3] || ""
        return i.indexOf("audio") >= 0 ? "headphones" : (i.indexOf("phone") >= 0 ? "smartphone" : (i.indexOf("mouse") >= 0 ? "mouse"
             : (i.indexOf("keyboard") >= 0 ? "keyboard" : (i.indexOf("gaming") >= 0 ? "sports_esports" : "bluetooth"))))
    }
    function connecterWifi(f) {
        if (f[0] === "1") return
        if (f[3] === "1" && f[4] !== "1") { saisie = f[1]; return }
        attendre(f[1])
        Etat.faire(f[4] === "1" ? ["nmcli", "con", "up", "id", f[1]] : ["nmcli", "dev", "wifi", "connect", f[1]])
    }
    function basculerBt(f) {
        attendre(f[0])
        if (f[2] === "1") Etat.faire(["bluetoothctl", "disconnect", f[0]])
        else if (f[4] === "1") Etat.faire(["bluetoothctl", "connect", f[0]])
        else Etat.faire(["sh", "-c", "bluetoothctl pair " + f[0] + " && bluetoothctl trust " + f[0] + " && bluetoothctl connect " + f[0]])
    }

    component Titre: Texte { font.pixelSize: 12; font.weight: Font.DemiBold; secondaire: true; height: 26; verticalAlignment: Text.AlignBottom; leftPadding: 8 }

    // En-tête : retour, titre, interrupteur façon iOS
    Item {
        id: tete
        width: parent.width; height: 40
        Rectangle {
            width: 32; height: 32; radius: 16; color: zr.containsMouse ? "#3a3a3c" : "#2c2c2e"
            anchors.verticalCenter: parent.verticalCenter
            Ico { anchors.centerIn: parent; nom: "chevron_left"; taille: 22 }
            MouseArea { id: zr; anchors.fill: parent; hoverEnabled: true; onClicked: Etat.aller("centre") }
        }
        Texte { x: 44; anchors.verticalCenter: parent.verticalCenter; text: p.wifi ? "Wi-Fi" : "Bluetooth"; font.pixelSize: 20; font.weight: Font.Bold }
        Rectangle {
            anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter
            width: 46; height: 28; radius: 14; color: p.allume ? "#30d158" : "#3a3a3c"
            Behavior on color { ColorAnimation { duration: 180 } }
            Rectangle {
                width: 24; height: 24; radius: 12; color: "white"; y: 2
                x: p.allume ? 20 : 2
                Behavior on x { SpringAnimation { spring: 5; damping: 0.5 } }
            }
            MouseArea { anchors.fill: parent; onClicked: Etat.faire(["noctalia", "msg", p.wifi ? "wifi-toggle" : "bluetooth-toggle"]) }
        }
    }

    Defilement {
        id: defil
        anchors.top: tete.bottom; anchors.topMargin: 8; anchors.bottom: pied.top; anchors.bottomMargin: 6
        width: parent.width
        contentHeight: liste.implicitHeight
        Column {
            id: liste
            width: p.width; spacing: 2
            readonly property real voulue: 40 + 8 + implicitHeight + 6 + 26
            onVoulueChanged: Etat.annoncerHauteur(p.wifi ? "reseau" : "bluetooth", voulue)
            Component.onCompleted: Etat.annoncerHauteur(p.wifi ? "reseau" : "bluetooth", voulue)

            Texte {
                visible: !p.allume; height: 40; leftPadding: 8; secondaire: true
                text: p.wifi ? "Le Wi-Fi est désactivé." : "Le Bluetooth est désactivé."
            }

            // ── Wi-Fi ──
            Titre { text: "Réseau actuel"; visible: p.wifi && p.allume && p.actuel.length > 0 }
            Repeater {
                model: p.wifi && p.allume ? p.actuel : []
                Ligne {
                    required property var modelData
                    titre: modelData.champs[1]; sous: "Connecté"; icone: p.iconeWifi(modelData.champs); actif: true
                    droite: modelData.champs[3] === "1" ? "lock" : ""
                    onClicDroit: Etat.faire(["nmcli", "con", "down", "id", modelData.champs[1]])
                }
            }
            Titre { text: "Autres réseaux"; visible: p.wifi && p.allume }
            Texte { visible: p.wifi && p.allume && p.elements.length === 0; text: "Recherche des réseaux…"; secondaire: true; height: 34; leftPadding: 8 }
            Repeater {
                model: p.wifi && p.allume ? p.autres : []
                Column {
                    required property var modelData
                    width: p.width; spacing: 2
                    Ligne {
                        titre: modelData.champs[1]
                        sous: modelData.champs[4] === "1" ? "Enregistré" : ""
                        icone: p.iconeWifi(modelData.champs)
                        droite: modelData.champs[3] === "1" ? "lock" : ""
                        attente: p.attente[modelData.champs[1]] === true
                        onClic: p.connecterWifi(modelData.champs)
                        onClicDroit: if (modelData.champs[4] === "1") Etat.faire(["nmcli", "con", "delete", "id", modelData.champs[1]])
                    }
                    // Mot de passe du réseau choisi
                    Rectangle {
                        visible: p.saisie === modelData.champs[1]
                        width: parent.width; height: 40; radius: 12; color: "#2c2c2e"
                        border.color: "#0a84ff"; border.width: 1.5
                        TextInput {
                            id: mdp
                            anchors.fill: parent; anchors.leftMargin: 14; anchors.rightMargin: 14
                            verticalAlignment: TextInput.AlignVCenter
                            color: "white"; font.pixelSize: 14; echoMode: TextInput.Password
                            onVisibleChanged: if (visible) { text = ""; forceActiveFocus() }
                            onAccepted: {
                                p.attendre(modelData.champs[1])
                                Etat.faire(["nmcli", "dev", "wifi", "connect", modelData.champs[1], "password", text])
                                p.saisie = ""
                            }
                            Keys.onEscapePressed: p.saisie = ""
                            Texte { visible: mdp.text === ""; text: "Mot de passe, puis Entrée"; secondaire: true; anchors.verticalCenter: parent.verticalCenter }
                        }
                    }
                }
            }

            // ── Bluetooth ──
            Titre { text: "Connectés"; visible: !p.wifi && p.allume && p.connectes.length > 0 }
            Repeater {
                model: !p.wifi && p.allume ? p.connectes : []
                Ligne {
                    required property var modelData
                    titre: modelData.champs[1]; sous: "Connecté"
                    icone: p.iconeBt(modelData.champs)
                    actif: modelData.champs[2] === "1"
                    attente: p.attente[modelData.champs[0]] === true
                    onClic: p.basculerBt(modelData.champs)
                    onClicDroit: if (modelData.champs[4] === "1") Etat.faire(["bluetoothctl", "remove", modelData.champs[0]])
                }
            }
            Titre { text: "Mes appareils"; visible: !p.wifi && p.allume && p.associes.length > 0 }
            Repeater {
                model: !p.wifi && p.allume ? p.associes : []
                Ligne {
                    required property var modelData
                    titre: modelData.champs[1]; sous: "Non connecté"
                    icone: p.iconeBt(modelData.champs)
                    actif: modelData.champs[2] === "1"
                    attente: p.attente[modelData.champs[0]] === true
                    onClic: p.basculerBt(modelData.champs)
                    onClicDroit: if (modelData.champs[4] === "1") Etat.faire(["bluetoothctl", "remove", modelData.champs[0]])
                }
            }
            Titre { text: "À proximité"; visible: !p.wifi && p.allume && (p.proches.length > 0 || p.recherche) }
            Repeater {
                model: !p.wifi && p.allume ? p.proches : []
                Ligne {
                    required property var modelData
                    titre: modelData.champs[1]; sous: "Clic pour associer"
                    icone: p.iconeBt(modelData.champs)
                    actif: modelData.champs[2] === "1"
                    attente: p.attente[modelData.champs[0]] === true
                    onClic: p.basculerBt(modelData.champs)
                    onClicDroit: if (modelData.champs[4] === "1") Etat.faire(["bluetoothctl", "remove", modelData.champs[0]])
                }
            }
            Texte { visible: !p.wifi && p.allume && p.recherche && p.proches.length === 0; text: "Recherche…"; secondaire: true; height: 30; leftPadding: 8 }
        }
    }

    // Pied : action secondaire en texte bleu, comme les réglages d'Apple
    Texte {
        id: pied
        anchors.bottom: parent.bottom; anchors.left: parent.left; anchors.leftMargin: 8
        height: 26
        color: zp.containsMouse ? "#409cff" : "#0a84ff"
        text: p.wifi ? "Réglages réseau…" : (p.recherche ? "Recherche en cours…" : "Rechercher des appareils")
        MouseArea {
            id: zp
            anchors.fill: parent; hoverEnabled: true
            onClicked: {
                if (p.wifi) { Etat.fermer(); Quickshell.execDetached(["sh", "-c", "nm-connection-editor || noctalia msg panel-toggle control-center"]) }
                else if (!p.recherche) { p.recherche = true; finRecherche.restart(); Etat.faire(["bluetoothctl", "--timeout", "12", "scan", "on"]) }
            }
        }
        Timer { id: finRecherche; interval: 13000; onTriggered: { p.recherche = false; Etat.lirePage() } }
    }
}

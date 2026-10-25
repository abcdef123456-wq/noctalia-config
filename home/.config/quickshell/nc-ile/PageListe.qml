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
    readonly property string cle: wifi ? "wifi" : "bluetooth"
    readonly property bool allume: Etat.valeur(cle, Etat.sys[cle]) === "on"
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
    // Connexion avec mot de passe. Refusée (mauvais mot de passe, réseau trop loin) : on le dit, et le profil à moitié
    // créé par nmcli est effacé (sinon le réseau passait pour « Enregistré » et ne redemandait plus le mot de passe)
    function connecterAvec(mdp) {
        if (saisie === "" || mdp === "") return
        attendre(saisie)
        Etat.faire(["sh", "-c", "nmcli dev wifi connect \"$1\" password \"$2\" >/dev/null 2>&1 || { nmcli con delete id \"$1\" >/dev/null 2>&1; "
                    + "notify-send -a Wi-Fi -i network-wireless-offline \"$3$1$4\" \"$5\"; }",
                    "sh", saisie, mdp, Reglages.t("Connexion impossible à ", "Couldn't join “"), Reglages.t("", "”"),
                    Reglages.t("Mot de passe incorrect, ou réseau trop loin.", "Wrong password, or the network is too far away.")])
        saisie = ""
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
            width: 32; height: 32; radius: 16; color: zr.containsMouse ? Couleurs.gris3 : Couleurs.gris2
            anchors.verticalCenter: parent.verticalCenter
            Ico { anchors.centerIn: parent; nom: "chevron_left"; taille: 22 }
            MouseArea { id: zr; anchors.fill: parent; hoverEnabled: true; onClicked: Etat.aller("centre") }
        }
        Texte { x: 44; anchors.verticalCenter: parent.verticalCenter; text: p.wifi ? "Wi-Fi" : "Bluetooth"; font.pixelSize: 20; font.weight: Font.Bold }
        Rectangle {
            anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter
            width: 46; height: 28; radius: 14; color: p.allume ? Couleurs.vert : Couleurs.gris3
            Behavior on color { ColorAnimation { duration: 180 } }
            Rectangle {
                width: 24; height: 24; radius: 12; color: Couleurs.texte; y: 2
                x: p.allume ? 20 : 2
                Behavior on x { SpringAnimation { spring: 5; damping: 0.5 } }
            }
            MouseArea { anchors.fill: parent; onClicked: Etat.inverser(p.cle, ["noctalia", "msg", p.wifi ? "wifi-toggle" : "bluetooth-toggle"]) }
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
                text: p.wifi ? Reglages.t("Le Wi-Fi est désactivé.", "Wi-Fi is off.") : Reglages.t("Le Bluetooth est désactivé.", "Bluetooth is off.")
            }

            // ── Wi-Fi ──
            Titre { text: Reglages.t("Réseau actuel", "Current Network"); visible: p.wifi && p.allume && p.actuel.length > 0 }
            Repeater {
                model: p.wifi && p.allume ? p.actuel : []
                Ligne {
                    required property var modelData
                    titre: modelData.champs[1]; sous: Reglages.t("Connecté", "Connected"); icone: p.iconeWifi(modelData.champs); actif: true
                    droite: modelData.champs[3] === "1" ? "lock" : ""
                    onClicDroit: Etat.faire(["nmcli", "con", "down", "id", modelData.champs[1]])
                }
            }
            // Mot de passe du réseau choisi : hors de la liste, relue toutes les 2 s (dedans, le champ était recréé à
            // chaque relecture et ce qu'on avait tapé s'effaçait)
            Column {
                visible: p.wifi && p.allume && p.saisie !== ""
                width: p.width; spacing: 6
                Titre { text: Reglages.t("Mot de passe de « " + p.saisie + " »", "Password for “" + p.saisie + "”") }
                Rectangle {
                    width: parent.width; height: 40; radius: 12; color: Couleurs.gris2
                    border.color: Couleurs.accent; border.width: 1.5
                    TextInput {
                        id: mdp
                        anchors.left: parent.left; anchors.leftMargin: 14; anchors.right: voir.left; anchors.rightMargin: 8
                        anchors.verticalCenter: parent.verticalCenter
                        color: Couleurs.texte; font.pixelSize: 14; clip: true
                        echoMode: voir.montre ? TextInput.Normal : TextInput.Password
                        onAccepted: p.connecterAvec(text)
                        Keys.onEscapePressed: p.saisie = ""
                        Texte { visible: mdp.text === ""; text: Reglages.t("Mot de passe, puis Entrée", "Password, then Enter"); secondaire: true; anchors.verticalCenter: parent.verticalCenter }
                    }
                    // Afficher / masquer ce qu'on tape
                    Ico {
                        id: voir
                        property bool montre: false
                        anchors.right: parent.right; anchors.rightMargin: 12; anchors.verticalCenter: parent.verticalCenter
                        nom: montre ? "visibility_off" : "visibility"; taille: 17; color: Couleurs.texteSec
                        MouseArea { anchors.fill: parent; anchors.margins: -6; onClicked: voir.montre = !voir.montre }
                    }
                }
            }
            Connections {
                target: p
                function onSaisieChanged() { mdp.text = ""; voir.montre = false; if (p.saisie !== "") mdp.forceActiveFocus() }
            }
            Titre { text: Reglages.t("Autres réseaux", "Other Networks"); visible: p.wifi && p.allume }
            Texte { visible: p.wifi && p.allume && p.elements.length === 0; text: Reglages.t("Recherche des réseaux…", "Looking for networks…"); secondaire: true; height: 34; leftPadding: 8 }
            Repeater {
                model: p.wifi && p.allume ? p.autres : []
                Ligne {
                    required property var modelData
                    titre: modelData.champs[1]
                    sous: p.saisie === modelData.champs[1] ? Reglages.t("Mot de passe demandé", "Password required")
                                                          : (modelData.champs[4] === "1" ? Reglages.t("Enregistré", "Saved") : "")
                    icone: p.iconeWifi(modelData.champs)
                    droite: modelData.champs[3] === "1" ? "lock" : ""
                    attente: p.attente[modelData.champs[1]] === true
                    onClic: p.connecterWifi(modelData.champs)
                    onClicDroit: if (modelData.champs[4] === "1") Etat.faire(["nmcli", "con", "delete", "id", modelData.champs[1]])
                }
            }

            // ── Bluetooth ──
            Titre { text: Reglages.t("Connectés", "Connected"); visible: !p.wifi && p.allume && p.connectes.length > 0 }
            Repeater {
                model: !p.wifi && p.allume ? p.connectes : []
                Ligne {
                    required property var modelData
                    titre: modelData.champs[1]; sous: Reglages.t("Connecté", "Connected")
                    icone: p.iconeBt(modelData.champs)
                    actif: modelData.champs[2] === "1"
                    attente: p.attente[modelData.champs[0]] === true
                    onClic: p.basculerBt(modelData.champs)
                    onClicDroit: if (modelData.champs[4] === "1") Etat.faire(["bluetoothctl", "remove", modelData.champs[0]])
                }
            }
            Titre { text: Reglages.t("Mes appareils", "My Devices"); visible: !p.wifi && p.allume && p.associes.length > 0 }
            Repeater {
                model: !p.wifi && p.allume ? p.associes : []
                Ligne {
                    required property var modelData
                    titre: modelData.champs[1]; sous: Reglages.t("Non connecté", "Not Connected")
                    icone: p.iconeBt(modelData.champs)
                    actif: modelData.champs[2] === "1"
                    attente: p.attente[modelData.champs[0]] === true
                    onClic: p.basculerBt(modelData.champs)
                    onClicDroit: if (modelData.champs[4] === "1") Etat.faire(["bluetoothctl", "remove", modelData.champs[0]])
                }
            }
            Titre { text: Reglages.t("À proximité", "Nearby Devices"); visible: !p.wifi && p.allume && (p.proches.length > 0 || p.recherche) }
            Repeater {
                model: !p.wifi && p.allume ? p.proches : []
                Ligne {
                    required property var modelData
                    titre: modelData.champs[1]; sous: Reglages.t("Clic pour associer", "Click to pair")
                    icone: p.iconeBt(modelData.champs)
                    actif: modelData.champs[2] === "1"
                    attente: p.attente[modelData.champs[0]] === true
                    onClic: p.basculerBt(modelData.champs)
                    onClicDroit: if (modelData.champs[4] === "1") Etat.faire(["bluetoothctl", "remove", modelData.champs[0]])
                }
            }
            Texte { visible: !p.wifi && p.allume && p.recherche && p.proches.length === 0; text: Reglages.t("Recherche…", "Searching…"); secondaire: true; height: 30; leftPadding: 8 }
        }
    }

    // Pied : action secondaire en texte bleu, comme les réglages d'Apple
    Texte {
        id: pied
        anchors.bottom: parent.bottom; anchors.left: parent.left; anchors.leftMargin: 8
        height: 26
        color: zp.containsMouse ? Couleurs.accentClair : Couleurs.accent
        text: p.wifi ? Reglages.t("Réglages réseau…", "Network Settings…")
                     : (p.recherche ? Reglages.t("Recherche en cours…", "Searching…") : Reglages.t("Rechercher des appareils", "Search for Devices"))
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

// Tiroir Réseau natif du Centre de contrôle :
// carte d'état Wi-Fi / Ethernet, bascule radio, analyse des réseaux, connexion rapide avec mot de passe inline,
// accès VPN intégré et style adapté à l'archétype du thème actif.
import QtQuick
import Quickshell
import Quickshell.Io

Item {
    id: vue
    signal fermerPanneau()

    readonly property bool estBrut: Couleurs.styleBrut || Couleurs.styleTerminal
    readonly property bool estEditorial: Couleurs.styleEditorial
    readonly property var s: Etat.sys
    readonly property bool masque: Partage.silence
    readonly property bool filaire: service && service.filaire || s.filaire === "1"
    readonly property bool wifiAllume: service && service.disponible ? service.allume : Etat.valeur("wifi", s.wifi) === "on"
    readonly property var reseaux: service && service.disponible ? service.reseaux
        : Etat.liste.filter(e => e.genre === "net").map(e => ({
            nom: e.champs[1], signal: Number(e.champs[2]) || 0, protege: e.champs[3] === "1",
            connecte: e.champs[0] === "1", connu: e.champs[4] === "1", objet: null
        }))
    readonly property var actif: reseaux.filter(e => e.connecte)
    readonly property var enregistres: reseaux.filter(e => !e.connecte && e.connu)
    readonly property var autres: reseaux.filter(e => !e.connecte && !e.connu)

    property var service: null
    property var cibleMdp: null
    property var cibleConnexion: null
    property string message: ""
    readonly property bool scanEnCours: procScan.running

    Component.onCompleted: {
        // Le module est facultatif dans Quickshell, mais son API D-Bus transmet le PSK sans processus ni fichier.
        try {
            service = Qt.createQmlObject(`import QtQuick; import Quickshell.Networking
                QtObject {
                    readonly property bool disponible: Networking.backend === NetworkBackendType.NetworkManager
                    readonly property bool allume: Networking.wifiEnabled
                    readonly property bool filaire: Networking.devices.values.some(d => d.type === DeviceType.Wired && d.connected)
                    readonly property var reseaux: {
                        const parNom = new Map()
                        for (const d of Networking.devices.values) {
                            if (d.type !== DeviceType.Wifi) continue
                            for (const n of d.networks.values) {
                                if (!n.name) continue
                                const autre = parNom.get(n.name)
                                if (!autre || n.connected || (!autre.connected && n.signalStrength > autre.signalStrength))
                                    parNom.set(n.name, n)
                            }
                        }
                        return Array.from(parNom.values(), n => ({
                            nom: n.name, signal: Math.round(n.signalStrength * 100), connecte: n.connected, connu: n.known,
                            protege: n.security !== WifiSecurityType.Open && n.security !== WifiSecurityType.Owe, objet: n
                        })).sort((a, b) => b.signal - a.signal)
                    }
                    function psk(n) {
                        return n.security === WifiSecurityType.WpaPsk || n.security === WifiSecurityType.Wpa2Psk || n.security === WifiSecurityType.Sae
                    }
                    function redemanderSecret(raison) {
                        return raison === ConnectionFailReason.NoSecrets || raison === ConnectionFailReason.WifiClientDisconnected
                            || raison === ConnectionFailReason.WifiAuthTimeout
                    }
                    function basculer() { Networking.wifiEnabled = !Networking.wifiEnabled }
                }`, vue, "ControleReseauBackend")
        } catch (_) { Etat.lirePage() }
    }
    onVisibleChanged: if (!visible) annulerSaisie()
    onMasqueChanged: if (masque) { annulerSaisie(); message = "" }
    onWifiAllumeChanged: if (!wifiAllume) { annulerSaisie(); cibleConnexion = null; finConnexion.stop() }

    function nomVisible(n) { return masque ? Reglages.t("Réseau Wi-Fi", "Wi-Fi network") : n.nom }
    function annulerSaisie() { if (champMdp) champMdp.clear(); cibleMdp = null }
    function demanderMdp(n) {
        cibleMdp = n
        champMdp.clear()
        champMdp.forceActiveFocus()
    }
    function iconeSignal(n) { return n >= 67 ? "wifi" : (n >= 34 ? "wifi_2_bar" : "wifi_1_bar") }
    function connecter(n) {
        if (n.connecte || cibleConnexion || masque) return
        annulerSaisie()
        message = ""
        if (!n.objet) {
            if (n.protege && !n.connu) {
                message = Reglages.t("Utilisez les paramètres réseau avancés pour saisir la clé.", "Use advanced network settings to enter the password.")
            } else {
                Etat.faire(["nmcli", "--wait", "25", "device", "wifi", "connect", n.nom])
            }
        } else if (!n.connu && n.protege) {
            if (service.psk(n.objet)) demanderMdp(n.objet)
            else message = Reglages.t("Ce réseau nécessite les paramètres réseau avancés.", "This network requires advanced network settings.")
        } else {
            cibleConnexion = n.objet
            finConnexion.restart()
            n.objet.connect()
        }
    }
    function envoyerMotDePasse() {
        const n = cibleMdp
        if (!n || !champMdp.text || cibleConnexion || masque) return
        const mdp = champMdp.text
        cibleConnexion = n
        message = ""
        finConnexion.restart()
        annulerSaisie()
        n.connectWithPsk(mdp)
    }
    function echecConnexion() {
        message = Reglages.t("Connexion impossible : vérifiez la clé et le signal.", "Couldn't connect: check the password and signal.")
    }
    Connections {
        target: vue.cibleConnexion
        function onConnectedChanged() {
            if (vue.cibleConnexion && vue.cibleConnexion.connected) {
                finConnexion.stop()
                vue.cibleConnexion = null
                Etat.lire()
            }
        }
        function onConnectionFailed(raison) {
            const n = vue.cibleConnexion
            finConnexion.stop()
            vue.cibleConnexion = null
            vue.echecConnexion()
            if (n && !vue.masque && vue.service.redemanderSecret(raison) && vue.service.psk(n)) vue.demanderMdp(n)
        }
    }
    Timer {
        id: finConnexion; interval: 35000
        onTriggered: {
            vue.cibleConnexion = null
            vue.echecConnexion()
        }
    }
    Process {
        id: procScan
        command: ["nmcli", "--wait", "10", "device", "wifi", "rescan"]
        onExited: code => {
            Etat.lirePage()
            if (code !== 0) vue.message = Reglages.t("L’analyse Wi-Fi a échoué.", "Wi-Fi scan failed.")
        }
    }

    component TitreSection: Texte {
        width: parent ? parent.width : 300
        font.pixelSize: vue.estBrut ? 9 : 11
        font.weight: Font.Bold
        font.letterSpacing: vue.estBrut ? 1.0 : 0.4
        secondaire: true
        topPadding: 4; bottomPadding: 2
    }

    component LigneReseau: Rectangle {
        id: row
        required property var modelData
        readonly property bool estActif: modelData.connecte
        width: parent ? parent.width : 300
        height: 44
        radius: Couleurs.rayon(Couleurs.rayonBouton, width, height)
        color: estActif
               ? (vue.estBrut ? Couleurs.accent : Couleurs.accentDoux)
               : (zr.contientPointeur ? Couleurs.carteSurvol : (vue.estEditorial ? "transparent" : Couleurs.surfaceDouce))
        border.width: (vue.estBrut || vue.estEditorial || estActif) ? 1 : 0
        border.color: estActif ? Couleurs.accent : Couleurs.bordureSubtile

        readonly property bool plein: estActif && vue.estBrut
        readonly property bool enCours: !!modelData.objet && (vue.cibleConnexion === modelData.objet || modelData.objet.stateChanging)

        Ico {
            x: 12; anchors.verticalCenter: parent.verticalCenter
            nom: vue.iconeSignal(row.modelData.signal); taille: 17
            color: row.plein ? Couleurs.surAccent : (row.estActif ? Couleurs.accent : Couleurs.texteSec)
        }
        Column {
            x: 38; width: Math.max(0, actions.x - x - 6); anchors.verticalCenter: parent.verticalCenter
            spacing: 1
            Texte {
                width: parent.width
                text: vue.nomVisible(row.modelData)
                font.pixelSize: 12; font.weight: row.estActif ? Font.DemiBold : Font.Medium
                color: row.plein ? Couleurs.surAccent : Couleurs.texte
            }
            Texte {
                width: parent.width
                text: (row.enCours ? Reglages.t("Connexion…", "Connecting…")
                    : row.estActif ? Reglages.t("Connecté", "Connected")
                    : row.modelData.connu ? Reglages.t("Enregistré", "Saved") : "") +
                    (row.enCours || row.estActif || row.modelData.connu ? " · " : "") + row.modelData.signal + "%"
                font.pixelSize: 10
                secondaire: !row.plein
                color: row.plein ? Qt.alpha(Couleurs.surAccent, 0.85) : Couleurs.texteSec
            }
        }
        Row {
            id: actions
            z: 1
            anchors.right: parent.right; anchors.rightMargin: 10
            anchors.verticalCenter: parent.verticalCenter
            spacing: 6
            Ico {
                visible: row.modelData.protege && !row.estActif
                anchors.verticalCenter: parent.verticalCenter
                nom: "lock"; taille: 13
                color: Couleurs.texteSec
            }
            Rectangle {
                visible: row.estActif
                width: 24; height: 24
                radius: Couleurs.rayon(vue.estBrut ? 2 : 12, width, height)
                color: zDisc.contientPointeur ? Qt.alpha(Couleurs.rouge, 0.22) : "transparent"
                Ico {
                    anchors.centerIn: parent
                    nom: zDisc.contientPointeur ? "link_off" : "check"
                    taille: 15
                    color: zDisc.contientPointeur ? Couleurs.rouge : (row.plein ? Couleurs.surAccent : Couleurs.accent)
                }
                ControleAction {
                    id: zDisc; anchors.fill: parent
                    enabled: !row.enCours && !!row.modelData.objet
                    text: Reglages.t("Déconnecter ", "Disconnect ") + vue.nomVisible(row.modelData)
                    onClicked: row.modelData.objet.disconnect()
                }
            }
            Rectangle {
                visible: row.modelData.connu && !!row.modelData.objet && !vue.masque
                width: 24; height: 24
                radius: Couleurs.rayon(Couleurs.rayonBouton, width, height)
                color: oublier.contientPointeur ? Qt.alpha(Couleurs.rouge, 0.18) : "transparent"
                Ico {
                    anchors.centerIn: parent; nom: "delete"; taille: 14
                    color: oublier.contientPointeur ? Couleurs.rouge : (row.plein ? Couleurs.surAccent : Couleurs.texteSec)
                }
                ControleAction {
                    id: oublier; anchors.fill: parent
                    enabled: !row.enCours
                    text: Reglages.t("Oublier ", "Forget ") + vue.nomVisible(row.modelData)
                    onClicked: row.modelData.objet.forget()
                }
            }
        }
        ControleAction {
            id: zr; anchors.fill: parent
            enabled: !row.estActif && !row.enCours && !vue.cibleConnexion && !vue.masque
            text: Reglages.t("Connecter à ", "Connect to ") + vue.nomVisible(row.modelData)
            onClicked: vue.connecter(row.modelData)
        }
    }

    Flickable {
        anchors.fill: parent
        contentWidth: width
        contentHeight: col.implicitHeight + 6
        clip: true
        boundsBehavior: Flickable.StopAtBounds

        Column {
            id: col
            width: parent.width
            spacing: 8

            // ── En-tête radio Wi-Fi + Scan ──
            Rectangle {
                width: parent.width; height: 50
                radius: Couleurs.rayon(Couleurs.rayonBloc, width, height)
                color: vue.estEditorial ? "transparent" : Couleurs.surfaceDouce
                border.width: 1; border.color: Couleurs.bordureSubtile

                Row {
                    x: 12; width: radioActions.x - x - 8; anchors.verticalCenter: parent.verticalCenter; spacing: 10
                    Rectangle {
                        width: 30; height: 30
                        radius: Couleurs.rayon(vue.estBrut ? 2 : 15, width, height)
                        color: vue.wifiAllume ? Couleurs.accent : Qt.alpha(Couleurs.voile, 0.08)
                        Ico { anchors.centerIn: parent; nom: vue.filaire ? "lan" : (vue.wifiAllume ? "wifi" : "wifi_off"); taille: 16; color: vue.wifiAllume ? Couleurs.surAccent : Couleurs.texteSec }
                    }
                    Column {
                        width: parent.width - 40; anchors.verticalCenter: parent.verticalCenter; spacing: 1
                        Texte {
                            width: parent.width
                            text: vue.filaire ? Reglages.t("Ethernet connecté", "Ethernet connected") : "Wi-Fi"
                            font.pixelSize: 13; font.weight: Font.DemiBold
                        }
                        Texte {
                            width: parent.width
                            text: vue.wifiAllume ? (vue.actif.length ? vue.nomVisible(vue.actif[0]) : Reglages.t("Wi-Fi activé", "Wi-Fi enabled")) : Reglages.t("Wi-Fi désactivé", "Wi-Fi disabled")
                            font.pixelSize: 10; secondaire: true
                        }
                    }
                }

                Row {
                    id: radioActions
                    anchors.right: parent.right; anchors.rightMargin: 10
                    anchors.verticalCenter: parent.verticalCenter; spacing: 8

                    Rectangle {
                        visible: vue.wifiAllume
                        width: 28; height: 28
                        radius: Couleurs.rayon(vue.estBrut ? 2 : 14, width, height)
                        color: zScan.contientPointeur ? Couleurs.accentDoux : "transparent"
                        Ico { anchors.centerIn: parent; nom: "refresh"; taille: 16; color: vue.scanEnCours ? Couleurs.accent : Couleurs.texteSec }
                        ControleAction {
                            id: zScan; anchors.fill: parent
                            enabled: !procScan.running
                            text: Reglages.t("Rechercher des réseaux Wi-Fi", "Scan for Wi-Fi networks")
                            onClicked: { vue.message = ""; procScan.running = true }
                        }
                    }

                    // Interrupteur Wi-Fi
                    Rectangle {
                        width: 40; height: 22
                        radius: Couleurs.rayon(vue.estBrut ? 2 : 11, width, height)
                        color: vue.wifiAllume ? Couleurs.accent : Couleurs.gris3
                        Behavior on color { enabled: !Reglages.sobre; ColorAnimation { duration: 120 } }
                        Rectangle {
                            x: vue.wifiAllume ? parent.width - width - 3 : 3
                            anchors.verticalCenter: parent.verticalCenter
                            width: 16; height: 16
                            radius: Couleurs.rayon(vue.estBrut ? 1 : 8, width, height)
                            color: vue.wifiAllume ? Couleurs.surAccent : Couleurs.texte
                            Behavior on x { enabled: !Reglages.sobre; NumberAnimation { duration: 120; easing.type: Easing.OutCubic } }
                        }
                        ControleAction {
                            anchors.fill: parent
                            text: vue.wifiAllume ? Reglages.t("Désactiver le Wi-Fi", "Turn Wi-Fi off") : Reglages.t("Activer le Wi-Fi", "Turn Wi-Fi on")
                            onClicked: {
                                if (vue.service && vue.service.disponible) vue.service.basculer()
                                else Etat.inverser("wifi", ["noctalia", "msg", "wifi-toggle"])
                            }
                        }
                    }
                }
            }

            // ── Bannière VPN rapide ──
            Rectangle {
                width: parent.width; height: 40
                radius: Couleurs.rayon(Couleurs.rayonBouton, width, height)
                color: VpnEtat.actif ? Qt.alpha(Couleurs.vert, 0.14) : (zVpn.contientPointeur ? Couleurs.carteSurvol : Couleurs.surfaceDouce)
                border.width: 1; border.color: VpnEtat.actif ? Qt.alpha(Couleurs.vert, 0.45) : Couleurs.bordureSubtile

                Row {
                    x: 12; anchors.verticalCenter: parent.verticalCenter; spacing: 8
                    Ico { anchors.verticalCenter: parent.verticalCenter; nom: "shield_lock"; taille: 16; color: VpnEtat.actif ? Couleurs.vert : Couleurs.texteSec }
                    Texte {
                        anchors.verticalCenter: parent.verticalCenter
                        text: VpnEtat.actif ? ("VPN · " + (!vue.masque && VpnEtat.libelle ? VpnEtat.libelle : Reglages.t("Actif", "Connected"))) : Reglages.t("VPN · Ouvrir les tunnels", "VPN · Manage tunnels")
                        font.pixelSize: 12; font.weight: Font.Medium
                        color: VpnEtat.actif ? Couleurs.vert : Couleurs.texte
                    }
                }
                Ico { anchors.right: parent.right; anchors.rightMargin: 10; anchors.verticalCenter: parent.verticalCenter; nom: "chevron_right"; taille: 16; color: Couleurs.texteSec }
                ControleAction {
                    id: zVpn; anchors.fill: parent
                    text: Reglages.t("Gérer les tunnels VPN", "Manage VPN tunnels")
                    onClicked: { VpnEtat.demanderPanneau(); vue.fermerPanneau() }
                }
            }

            Texte {
                visible: vue.message !== ""
                width: parent.width; wrapMode: Text.Wrap; font.pixelSize: 11; color: Couleurs.orange
                text: vue.message
            }

            // ── Champ mot de passe inline (si réseau sécurisé sélectionné) ──
            Rectangle {
                visible: !!vue.cibleMdp
                width: parent.width; height: 74
                radius: Couleurs.rayon(Couleurs.rayonBloc, width, height)
                color: Couleurs.accentDoux
                border.width: 1; border.color: Couleurs.accent

                Column {
                    anchors.fill: parent; anchors.margins: 10; spacing: 6
                    Row {
                        width: parent.width; spacing: 6
                        Texte {
                            text: vue.cibleMdp ? Reglages.t("Mot de passe pour ", "Password for ") + vue.cibleMdp.name : ""
                            font.pixelSize: 11; font.weight: Font.DemiBold; width: parent.width - 24
                        }
                        Item {
                            width: 18; height: 18
                            Ico { anchors.centerIn: parent; nom: "close"; taille: 14; color: Couleurs.texteSec }
                            ControleAction {
                                anchors.fill: parent
                                text: Reglages.t("Annuler la saisie", "Cancel password entry")
                                onClicked: vue.annulerSaisie()
                            }
                        }
                    }
                    Row {
                        width: parent.width; spacing: 6
                        Rectangle {
                            width: parent.width - 74; height: 30
                            radius: Couleurs.rayon(Couleurs.rayonBouton, width, height)
                            color: Couleurs.fond; border.width: 1; border.color: Couleurs.accentBord
                            TextInput {
                                id: champMdp
                                anchors.fill: parent; anchors.leftMargin: 8; anchors.rightMargin: 8
                                verticalAlignment: TextInput.AlignVCenter
                                echoMode: TextInput.Password
                                inputMethodHints: Qt.ImhSensitiveData | Qt.ImhNoPredictiveText | Qt.ImhNoAutoUppercase
                                activeFocusOnTab: visible
                                Accessible.name: Reglages.t("Mot de passe Wi-Fi", "Wi-Fi password")
                                color: Couleurs.texte; font.family: Couleurs.police; font.pixelSize: 12
                                onAccepted: vue.envoyerMotDePasse()
                                Keys.onEscapePressed: { vue.annulerSaisie(); zAv.forceActiveFocus() }
                            }
                        }
                        Rectangle {
                            width: 68; height: 30
                            radius: Couleurs.rayon(Couleurs.rayonBouton, width, height)
                            color: Couleurs.accent
                            Texte { anchors.centerIn: parent; text: Reglages.t("Joindre", "Join"); font.pixelSize: 11; font.weight: Font.DemiBold; color: Couleurs.surAccent }
                            ControleAction {
                                anchors.fill: parent; enabled: champMdp.text !== ""
                                text: Reglages.t("Joindre", "Join")
                                onClicked: vue.envoyerMotDePasse()
                            }
                        }
                    }
                }
            }

            // ── Réseau actif ──
            TitreSection { visible: vue.wifiAllume && vue.actif.length > 0; text: Reglages.t("RÉSEAU ACTUEL", "CURRENT NETWORK") }
            Repeater {
                model: vue.wifiAllume ? vue.actif : []
                LigneReseau {}
            }

            // ── Réseaux enregistrés ──
            TitreSection { visible: vue.wifiAllume && vue.enregistres.length > 0; text: Reglages.t("ENREGISTRÉS", "SAVED") }
            Repeater {
                model: vue.wifiAllume ? vue.enregistres : []
                LigneReseau {}
            }

            // ── Réseaux disponibles ──
            TitreSection { visible: vue.wifiAllume && vue.autres.length > 0; text: Reglages.t("DISPONIBLES", "AVAILABLE") }
            Repeater {
                model: vue.wifiAllume ? vue.autres : []
                LigneReseau {}
            }

            Texte {
                visible: vue.wifiAllume && vue.reseaux.length === 0
                width: parent.width; topPadding: 8; bottomPadding: 8
                horizontalAlignment: Text.AlignHCenter; secondaire: true; font.pixelSize: 12
                text: vue.scanEnCours ? Reglages.t("Recherche des réseaux…", "Scanning networks…") : Reglages.t("Aucun réseau Wi-Fi détecté.", "No Wi-Fi networks found.")
            }

            // ── Lien paramètres réseau avancés ──
            Rectangle {
                width: parent.width; height: 34
                radius: Couleurs.rayon(Couleurs.rayonBouton, width, height)
                color: zAv.contientPointeur ? Couleurs.accentDoux : "transparent"
                Texte {
                    anchors.centerIn: parent
                    text: Reglages.t("Paramètres réseau avancés…", "Advanced network settings…")
                    font.pixelSize: 11; font.weight: Font.Medium
                    color: Couleurs.accent
                }
                ControleAction {
                    id: zAv; anchors.fill: parent
                    text: Reglages.t("Paramètres réseau avancés", "Advanced network settings")
                    onClicked: {
                        Quickshell.execDetached(["sh", "-c", "command -v nm-connection-editor >/dev/null && exec nm-connection-editor; exec noctalia msg panel-toggle control-center"])
                        vue.fermerPanneau()
                    }
                }
            }
        }
    }
}

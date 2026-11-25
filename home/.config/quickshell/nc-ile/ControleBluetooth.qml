// Tiroir Bluetooth natif du Centre de contrôle :
// bascule radio, recherche d'appareils à proximité, appareils connectés avec batterie (CasqueBatterie),
// appareils associés et appairage en un clic — adapté à l'archétype du thème actif.
import QtQuick
import Quickshell
import Quickshell.Io

Item {
    id: vue

    readonly property bool estBrut: Couleurs.styleBrut || Couleurs.styleTerminal
    readonly property bool estEditorial: Couleurs.styleEditorial
    readonly property var s: Etat.sys || ({})
    readonly property bool btAllume: Etat.valeur("bluetooth", s.bluetooth) === "on"
    readonly property var appareils: (Etat.liste || []).filter(e => e.genre === "bt")
    readonly property var connectes: appareils.filter(e => e.champs[2] === "1")
    readonly property var associes: appareils.filter(e => e.champs[2] !== "1" && e.champs[4] === "1")
    readonly property var proches: appareils.filter(e => e.champs[2] !== "1" && e.champs[4] !== "1")

    property string adresse: ""
    property string operation: ""
    property string invite: ""
    property string code: ""
    property string message: ""
    property int sortieTraitee: 0
    property bool abandon: false
    readonly property bool masque: Partage.silence
    readonly property bool recherche: scanner.running

    Component.onCompleted: Etat.lirePage()
    onVisibleChanged: if (!visible && appairage.running) annulerAppairage()
    onMasqueChanged: if (masque && appairage.running) annulerAppairage()
    Component.onDestruction: if (operation === "pair" && !abandon) annulerCoteBluez()

    function nomVisible(f) {
        return masque ? Reglages.t("Appareil Bluetooth", "Bluetooth device") : (f[1] || f[0])
    }
    function oublierInvite() { invite = ""; code = ""; if (champCode) champCode.clear() }
    function annulerCoteBluez() {
        Quickshell.execDetached(["timeout", "4s", "bluetoothctl", "cancel-pairing", adresse])
    }
    function annulerAppairage() {
        if (operation === "pair") annulerCoteBluez()
        abandon = true
        oublierInvite()
        appairage.running = false
    }
    function repondre(reponse) {
        if (!appairage.running || masque) return
        if (invite === "confirmation" && reponse !== "yes" && reponse !== "no") return
        if (invite === "cle" && !/^[0-9]{1,6}$/.test(reponse)) return
        if (invite === "pin" && !/^[ -~]{1,16}$/.test(reponse)) return
        if (invite !== "confirmation" && invite !== "cle" && invite !== "pin") return
        appairage.write(reponse + "\n")
        oublierInvite()
    }
    function lireAppairage(texte) {
        if (!appairage.running || abandon) return
        // Readline redessine l'invite sans retour à la ligne : conserver le dernier fragment jusqu'à ce qu'il soit complet.
        const sortie = texte.replace(/\x1b\[[0-?]*[ -/]*[@-~]/g, "").replace(/[\x01\x02]/g, "")
        const fragment = sortie.slice(sortieTraitee)
        if (/(?:^|[\r\n])Agent registered\b/.test(fragment) && operation === "agent") {
            sortieTraitee = sortie.length
            operation = "pair"
            appairage.write("pair " + adresse + "\n")
        } else if (operation === "pair") {
            if (/(?:^|[\r\n])(?:Pairing successful|Connection successful|Failed to pair|Failed to connect|Device [0-9A-F:]+ not available)\b/i.test(fragment)) {
                sortieTraitee = sortie.length
                oublierInvite()
                operation = "verification"
                appairage.write("quit\n")
                return
            }
            const conf = fragment.match(/(?:^|[\r\n])\[agent\] Confirm passkey ([0-9]{6}) \(yes\/no\):/)
            const affiche = fragment.match(/(?:^|[\r\n])\[agent\] (?:Passkey|PIN code): ([0-9]+)/)
            const a = conf ? "confirmation"
                : /(?:^|[\r\n])\[agent\] Accept pairing \(yes\/no\):/.test(fragment) ? "confirmation"
                : /(?:^|[\r\n])\[agent\] Enter passkey[^:]*:/.test(fragment) ? "cle"
                : /(?:^|[\r\n])\[agent\] Enter PIN code:/.test(fragment) ? "pin"
                : affiche ? "affichage" : ""
            if (a !== "") {
                sortieTraitee = sortie.length
                code = (conf || affiche) ? (conf || affiche)[1] : ""
                invite = a
                if (a === "cle" || a === "pin") champCode.forceActiveFocus()
            }
        }
    }
    function lancer(op, mac) {
        if (adresse || masque || !/^([0-9a-f]{2}:){5}[0-9a-f]{2}$/i.test(mac)) return
        adresse = mac
        operation = op
        message = ""
        if (op === "agent") {
            abandon = false
            sortieTraitee = 0
            appairage.stdinEnabled = true
            appairage.running = true
        } else executer(op)
    }
    function executer(op) {
        // Vérifier les propriétés BlueZ, pas le texte optimiste de « pair » ni le seul code de retour de bluetoothctl.
        action.command = ["timeout", "--kill-after=2s", "25s", "sh", "-c",
            "ctl() { bluetoothctl \"$@\"; }; "
            + "info() { ctl info \"$2\" | grep -Eq \"^[[:space:]]*$1: $3$\"; }; "
            + "case $1 in verification) info Paired \"$2\" yes || exit 1; ctl trust \"$2\" || exit 1; "
            + "info Connected \"$2\" yes || ctl connect \"$2\" || exit 1; info Connected \"$2\" yes ;; "
            + "connect) ctl connect \"$2\" && info Connected \"$2\" yes ;; "
            + "disconnect) ctl disconnect \"$2\" && info Connected \"$2\" no ;; "
            + "remove) ctl remove \"$2\" && ! info Paired \"$2\" yes ;; esac", "sh", op, adresse]
        action.running = true
    }
    function finir(ok) {
        if (!ok) message = operation === "agent" || operation === "pair" || operation === "verification"
            ? Reglages.t("Association ou connexion impossible. Relancez la recherche et réessayez.", "Pairing or connection failed. Scan and try again.")
            : Reglages.t("L’action Bluetooth a échoué.", "The Bluetooth action failed.")
        adresse = ""; operation = ""
        oublierInvite()
        Etat.lire(); Etat.lirePage()
    }
    Process {
        id: scanner
        command: ["timeout", "--kill-after=2s", "15s", "bluetoothctl", "--timeout", "12", "scan", "on"]
        stdout: StdioCollector {}
        onExited: code => {
            if (code !== 0) vue.message = Reglages.t("La recherche Bluetooth a échoué.", "Bluetooth scan failed.")
            Etat.lirePage()
        }
    }
    Process {
        id: appairage
        // Un vrai terminal est nécessaire à l'agent Readline. Pas de transcript ni d'historique, et jamais de « yes » automatique.
        command: ["script", "-qefc", "stty -echo; exec timeout --kill-after=2s 50s bluetoothctl --agent KeyboardDisplay", "/dev/null"]
        environment: ({ LC_ALL: "C", TERM: "dumb", INPUTRC: "/dev/null", XDG_CACHE_HOME: "/dev/null" })
        stdout: StdioCollector { waitForEnd: false; onTextChanged: vue.lireAppairage(text) }
        onExited: {
            stdinEnabled = false
            if (vue.abandon) vue.finir(true)
            else if (vue.operation === "verification") vue.executer("verification")
            else vue.finir(false)
        }
    }
    Process {
        id: action
        environment: ({ LC_ALL: "C" })
        stdout: StdioCollector {}
        onExited: code => vue.finir(code === 0)
    }
    Timer {
        interval: 55000
        running: vue.operation === "agent" || vue.operation === "pair"
        onTriggered: {
            if (vue.operation === "pair") vue.annulerCoteBluez()
            if (!appairage.running) vue.finir(false)
            else appairage.running = false
        }
    }
    Timer {
        interval: 1000
        running: vue.adresse !== "" && vue.operation !== "agent" && vue.operation !== "pair" && !action.running && !appairage.running
        onTriggered: vue.finir(false)
    }

    function iconeBt(f) {
        var i = (f[3] || "").toLowerCase()
        if (i.indexOf("audio") >= 0 || i.indexOf("head") >= 0) return "headphones"
        if (i.indexOf("phone") >= 0) return "smartphone"
        if (i.indexOf("mouse") >= 0) return "mouse"
        if (i.indexOf("keyboard") >= 0) return "keyboard"
        if (i.indexOf("gaming") >= 0 || i.indexOf("input") >= 0) return "sports_esports"
        return "bluetooth"
    }
    function batterieBt(f) {
        return CasqueBatterie.niveauAppareil(f[1], f[0])
    }
    function basculerAppareil(f) {
        lancer(f[2] === "1" ? "disconnect" : f[4] === "1" ? "connect" : "agent", f[0])
    }

    component TitreSection: Texte {
        width: parent ? parent.width : 300
        font.pixelSize: vue.estBrut ? 9 : 11
        font.weight: Font.Bold
        font.letterSpacing: vue.estBrut ? 1.0 : 0.4
        secondaire: true
        topPadding: 4; bottomPadding: 2
    }

    component LigneAppareil: Rectangle {
        id: row
        property var champs: []
        property bool estConnecte: false
        property bool estAssocie: false
        readonly property int bat: estConnecte ? vue.batterieBt(champs) : -1
        readonly property bool plein: estConnecte && vue.estBrut
        readonly property bool enCours: vue.adresse === champs[0]

        width: parent ? parent.width : 300
        height: 46
        radius: Couleurs.rayon(Couleurs.rayonBouton, width, height)
        color: estConnecte
               ? (vue.estBrut ? Couleurs.accent : Couleurs.accentDoux)
               : (zb.contientPointeur ? Couleurs.carteSurvol : (vue.estEditorial ? "transparent" : Couleurs.surfaceDouce))
        border.width: (vue.estBrut || vue.estEditorial || estConnecte) ? 1 : 0
        border.color: estConnecte ? Couleurs.accent : Couleurs.bordureSubtile

        Rectangle {
            id: pastille
            x: 10; anchors.verticalCenter: parent.verticalCenter
            width: 28; height: 28
            radius: Couleurs.rayon(vue.estBrut ? 2 : 14, width, height)
            color: row.plein ? Qt.alpha(Couleurs.surAccent, 0.18)
                 : (row.estConnecte ? Couleurs.accent : Qt.alpha(Couleurs.voile, 0.08))
            Ico {
                anchors.centerIn: parent
                nom: vue.iconeBt(row.champs); taille: 15
                color: row.plein || row.estConnecte ? Couleurs.surAccent : Couleurs.texteSec
            }
        }

        Column {
            anchors.left: pastille.right; anchors.leftMargin: 10
            anchors.right: badgeDroite.left; anchors.rightMargin: 8
            anchors.verticalCenter: parent.verticalCenter
            spacing: 1
            Texte {
                width: parent.width
                text: vue.nomVisible(row.champs)
                font.pixelSize: 12; font.weight: row.estConnecte ? Font.DemiBold : Font.Medium
                color: row.plein ? Couleurs.surAccent : Couleurs.texte
            }
            Texte {
                width: parent.width
                text: row.enCours ? (row.estConnecte ? Reglages.t("Déconnexion…", "Disconnecting…")
                                    : row.estAssocie ? Reglages.t("Connexion…", "Connecting…") : Reglages.t("Association…", "Pairing…"))
                    : (row.estConnecte ? Reglages.t("Connecté", "Connected")
                    : (row.estAssocie ? Reglages.t("Associé", "Paired") : Reglages.t("À proximité", "Nearby")))
                font.pixelSize: 10
                secondaire: !row.plein
                color: row.plein ? Qt.alpha(Couleurs.surAccent, 0.85) : Couleurs.texteSec
            }
        }

        Row {
            id: badgeDroite
            z: 1
            anchors.right: parent.right; anchors.rightMargin: 10
            anchors.verticalCenter: parent.verticalCenter
            spacing: 6
            Rectangle {
                visible: row.bat > 0
                anchors.verticalCenter: parent.verticalCenter
                width: txtBat.implicitWidth + 10; height: 20
                radius: Couleurs.rayon(vue.estBrut ? 2 : 10, width, height)
                color: row.bat <= 20 ? Qt.alpha(Couleurs.rouge, 0.18) : Qt.alpha(Couleurs.voile, 0.10)
                Texte {
                    id: txtBat; anchors.centerIn: parent
                    text: row.bat + "%"
                    font.pixelSize: 10; font.weight: Font.DemiBold; font.features: ({ "tnum": 1 })
                    color: row.bat <= 20 ? Couleurs.rouge : (row.plein ? Couleurs.surAccent : Couleurs.texte)
                }
            }
            Ico {
                anchors.verticalCenter: parent.verticalCenter
                nom: row.estConnecte ? (zb.contientPointeur ? "link_off" : "bluetooth_connected") : "chevron_right"
                taille: 16
                color: row.estConnecte && zb.contientPointeur ? Couleurs.rouge : (row.plein ? Couleurs.surAccent : Couleurs.texteSec)
            }
            Rectangle {
                visible: row.estAssocie && !vue.masque
                anchors.verticalCenter: parent.verticalCenter
                width: 24; height: 24
                radius: Couleurs.rayon(Couleurs.rayonBouton, width, height)
                color: zbOublier.contientPointeur ? Qt.alpha(Couleurs.rouge, 0.18) : "transparent"
                Ico { anchors.centerIn: parent; nom: "delete"; taille: 14; color: row.plein ? Couleurs.surAccent : Couleurs.texteSec }
                ControleAction {
                    id: zbOublier; anchors.fill: parent; enabled: !vue.adresse
                    text: Reglages.t("Oublier ", "Forget ") + vue.nomVisible(row.champs)
                    onClicked: vue.lancer("remove", row.champs[0])
                }
            }
        }

        ControleAction {
            id: zb; anchors.fill: parent
            enabled: !vue.adresse && !vue.masque
            text: (row.estConnecte ? Reglages.t("Déconnecter ", "Disconnect ")
                : row.estAssocie ? Reglages.t("Connecter ", "Connect ") : Reglages.t("Associer ", "Pair ")) + vue.nomVisible(row.champs)
            onClicked: vue.basculerAppareil(row.champs)
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

            // ── En-tête Bluetooth + Scan ──
            Rectangle {
                width: parent.width; height: 50
                radius: Couleurs.rayon(Couleurs.rayonBloc, width, height)
                color: vue.estEditorial ? "transparent" : Couleurs.surfaceDouce
                border.width: 1; border.color: Couleurs.bordureSubtile

                Row {
                    x: 12; anchors.verticalCenter: parent.verticalCenter; spacing: 10
                    Rectangle {
                        width: 30; height: 30
                        radius: Couleurs.rayon(vue.estBrut ? 2 : 15, width, height)
                        color: vue.btAllume ? Couleurs.bleu : Qt.alpha(Couleurs.voile, 0.08)
                        Ico { anchors.centerIn: parent; nom: vue.btAllume ? "bluetooth" : "bluetooth_disabled"; taille: 16; color: vue.btAllume ? Couleurs.surCouleur : Couleurs.texteSec }
                    }
                    Column {
                        anchors.verticalCenter: parent.verticalCenter; spacing: 1
                        Texte { text: "Bluetooth"; font.pixelSize: 13; font.weight: Font.DemiBold }
                        Texte {
                            text: !vue.btAllume ? Reglages.t("Désactivé", "Disabled")
                                : (vue.connectes.length > 0 ? vue.connectes.length + " " + Reglages.t(vue.connectes.length > 1 ? "connectés" : "connecté", "connected")
                                : Reglages.t("Prêt à connecter", "Ready to connect"))
                            font.pixelSize: 10; secondaire: true
                        }
                    }
                }

                Row {
                    anchors.right: parent.right; anchors.rightMargin: 10
                    anchors.verticalCenter: parent.verticalCenter; spacing: 8

                    Rectangle {
                        visible: vue.btAllume
                        width: rowScan.implicitWidth + 16; height: 26
                        radius: Couleurs.rayon(Couleurs.rayonBouton, width, height)
                        color: vue.recherche ? Couleurs.accentDoux : (zScan.contientPointeur ? Couleurs.carteSurvol : "transparent")
                        border.width: 1; border.color: vue.recherche ? Couleurs.accent : Couleurs.bordureSubtile
                        Row {
                            id: rowScan; anchors.centerIn: parent; spacing: 4
                            Ico { anchors.verticalCenter: parent.verticalCenter; nom: "radar"; taille: 13; color: vue.recherche ? Couleurs.accent : Couleurs.texteSec }
                            Texte {
                                anchors.verticalCenter: parent.verticalCenter
                                text: vue.recherche ? Reglages.t("Analyse…", "Scanning…") : Reglages.t("Scanner", "Scan")
                                font.pixelSize: 10; font.weight: Font.DemiBold
                                color: vue.recherche ? Couleurs.accent : Couleurs.texte
                            }
                        }
                        ControleAction {
                            id: zScan; anchors.fill: parent
                            text: Reglages.t("Rechercher des appareils Bluetooth", "Scan for Bluetooth devices")
                            enabled: !scanner.running
                            onClicked: { vue.message = ""; scanner.running = true }
                        }
                    }

                    Rectangle {
                        width: 40; height: 22
                        radius: Couleurs.rayon(vue.estBrut ? 2 : 11, width, height)
                        color: vue.btAllume ? Couleurs.bleu : Couleurs.gris3
                        Behavior on color { enabled: !Reglages.sobre; ColorAnimation { duration: 120 } }
                        Rectangle {
                            x: vue.btAllume ? parent.width - width - 3 : 3
                            anchors.verticalCenter: parent.verticalCenter
                            width: 16; height: 16
                            radius: Couleurs.rayon(vue.estBrut ? 1 : 8, width, height)
                            color: vue.btAllume ? Couleurs.surCouleur : Couleurs.texte
                            Behavior on x { enabled: !Reglages.sobre; NumberAnimation { duration: 120; easing.type: Easing.OutCubic } }
                        }
                        ControleAction {
                            anchors.fill: parent
                            enabled: !vue.adresse
                            text: vue.btAllume ? Reglages.t("Désactiver le Bluetooth", "Turn Bluetooth off") : Reglages.t("Activer le Bluetooth", "Turn Bluetooth on")
                            onClicked: Etat.inverser("bluetooth", ["noctalia", "msg", "bluetooth-toggle"])
                        }
                    }
                }
            }

            Rectangle {
                visible: (vue.operation === "agent" || vue.operation === "pair") && !vue.masque
                width: parent.width; height: choix.implicitHeight + 20
                radius: Couleurs.rayon(Couleurs.rayonBloc, width, height)
                color: Couleurs.accentDoux
                border.width: 1; border.color: Couleurs.accent
                Column {
                    id: choix
                    width: parent.width - 20; x: 10; y: 10; spacing: 8
                    Texte {
                        width: parent.width; wrapMode: Text.Wrap; font.pixelSize: 12
                        text: vue.invite === "confirmation"
                            ? (vue.code ? Reglages.t("Le code correspond-il ? ", "Does the code match? ") + vue.code : Reglages.t("Accepter l’association ?", "Accept pairing?"))
                            : vue.invite === "affichage" ? Reglages.t("Saisissez ce code sur l’appareil : ", "Enter this code on the device: ") + vue.code
                            : vue.invite === "pin" || vue.invite === "cle" ? Reglages.t("Saisissez le code fourni par l’appareil.", "Enter the code provided by the device.")
                            : Reglages.t("Association Bluetooth en cours…", "Pairing Bluetooth device…")
                    }
                    Rectangle {
                        visible: vue.invite === "pin" || vue.invite === "cle"
                        width: parent.width; height: 30; radius: Couleurs.rayon(Couleurs.rayonBouton, width, height)
                        color: Couleurs.fond; border.width: 1; border.color: Couleurs.accent
                        TextInput {
                            id: champCode
                            anchors.fill: parent; anchors.margins: 5
                            verticalAlignment: TextInput.AlignVCenter
                            activeFocusOnTab: visible
                            echoMode: TextInput.Password
                            inputMethodHints: Qt.ImhSensitiveData | Qt.ImhNoPredictiveText
                            maximumLength: vue.invite === "cle" ? 6 : 16
                            color: Couleurs.texte; font.family: Couleurs.police
                            Accessible.name: Reglages.t("Code Bluetooth", "Bluetooth code")
                            onAccepted: vue.repondre(text)
                        }
                    }
                    Row {
                        width: parent.width; spacing: 6
                        Repeater {
                            model: vue.invite === "confirmation" ? [{ nom: Reglages.t("Confirmer", "Confirm"), commande: "yes" },
                                                                     { nom: Reglages.t("Refuser", "Decline"), commande: "no" }]
                                : vue.invite === "pin" || vue.invite === "cle" ? [{ nom: Reglages.t("Envoyer", "Send"), commande: "code" }] : []
                            ControleAction {
                                required property var modelData
                                width: libelle.implicitWidth + 12; height: 28; text: modelData.nom
                                Texte { id: libelle; anchors.centerIn: parent; text: parent.text; color: Couleurs.accent; font.weight: Font.DemiBold }
                                onClicked: vue.repondre(modelData.commande === "code" ? champCode.text : modelData.commande)
                            }
                        }
                        ControleAction {
                            width: annuler.implicitWidth + 12; height: 28; text: Reglages.t("Annuler", "Cancel")
                            Texte { id: annuler; anchors.centerIn: parent; text: parent.text; secondaire: true }
                            onClicked: vue.annulerAppairage()
                        }
                    }
                }
            }
            Texte {
                visible: vue.message !== ""; width: parent.width; wrapMode: Text.Wrap; font.pixelSize: 11
                color: Couleurs.orange; text: vue.message
            }

            TitreSection { visible: vue.btAllume && vue.connectes.length > 0; text: Reglages.t("CONNECTÉS", "CONNECTED") }
            Repeater {
                model: vue.btAllume ? vue.connectes : []
                LigneAppareil { required property var modelData; champs: modelData.champs; estConnecte: true; estAssocie: true }
            }

            TitreSection { visible: vue.btAllume && vue.associes.length > 0; text: Reglages.t("MES APPAREILS", "MY DEVICES") }
            Repeater {
                model: vue.btAllume ? vue.associes : []
                LigneAppareil { required property var modelData; champs: modelData.champs; estConnecte: false; estAssocie: true }
            }

            TitreSection { visible: vue.btAllume && (vue.proches.length > 0 || vue.recherche); text: Reglages.t("À PROXIMITÉ", "NEARBY") }
            Repeater {
                model: vue.btAllume ? vue.proches : []
                LigneAppareil { required property var modelData; champs: modelData.champs; estConnecte: false; estAssocie: false }
            }

            Texte {
                visible: vue.btAllume && vue.appareils.length === 0
                width: parent.width; topPadding: 10; bottomPadding: 10
                horizontalAlignment: Text.AlignHCenter; secondaire: true; font.pixelSize: 12
                text: vue.recherche ? Reglages.t("Recherche d'appareils à proximité…", "Searching for nearby devices…")
                                    : Reglages.t("Aucun appareil Bluetooth détecté.", "No Bluetooth devices found.")
            }
        }
    }
}

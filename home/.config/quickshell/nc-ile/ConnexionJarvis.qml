// Fenêtre « Connexion JARVIS » (nc-assistant configurer, « Configurer la connexion » du cockpit et de l'île, fenêtre des
// réglages) : l'adresse du serveur JARVIS-BIS, sa clé secrète, ton identifiant et le délai d'attente, en graphique.
// « Tester la connexion » essaie les valeurs saisies sans les enregistrer (réseau, clé, TLS, moteur) ; « Enregistrer »
// les écrit dans ~/.config/nc/assistant.conf (0600). La clé passe par l'entrée standard de nc-assistant, jamais en
// argument ; elle n'est jamais relue ni affichée : laissée vide, celle qui est enregistrée est gardée.
// Clavier : Tab pour passer d'un champ à l'autre, Entrée teste, Ctrl + Entrée enregistre, Échap ferme (l'île d'abord).
import QtQuick
import Quickshell
import Quickshell.Io

FloatingWindow {
    id: fen
    title: "Connexion JARVIS"
    visible: false
    implicitWidth: 600; implicitHeight: 660; minimumSize: Qt.size(460, 560)
    color: Couleurs.fond
    readonly property string bin: Quickshell.env("HOME") + "/.local/bin/"
    property bool cleEnregistree: false
    property bool existe: false
    property var resultat: null                // dernier test : {online, latency_ms, version, public_url, error, private}
    property string message: ""
    property bool erreur: false
    property bool ileOuverte: false
    signal fermerIle()
    readonly property bool occupe: lecture.running || test.running || enregistrement.running
    // Avertissement en direct, comme nc-assistant : adresse locale ou privée, HTTP en clair
    readonly property string avertissement: {
        var u = url.text.trim().toLowerCase(), h = (u.match(/^https?:\/\/([^/:]+)/) || [null, ""])[1]
        if (!h) return ""
        // Tailscale (100.64.0.0/10, *.ts.net) : joignable de partout sur ton réseau Tailscale, chiffré (WireGuard)
        var m = h.match(/^100\.(\d+)\./)
        if (/\.ts\.net\.?$/.test(h) || (m && +m[1] >= 64 && +m[1] <= 127)) return ""
        if (h === "localhost" || /\.(local|lan|home\.arpa)$/.test(h) || /^(10|127)\./.test(h) || /^192\.168\./.test(h)
            || /^172\.(1[6-9]|2\d|3[01])\./.test(h) || /^169\.254\./.test(h) || /^\[?(fd|fe80|::1)/.test(h))
            return Reglages.t("Adresse locale ou privée : elle ne marche que sur le réseau du serveur. Depuis ailleurs, utilise l'adresse HTTPS d'un tunnel (Cloudflare, Tailscale).",
                              "Local or private address: it only works on the server's network. From elsewhere, use a tunnel's HTTPS address (Cloudflare, Tailscale).")
        if (u.startsWith("http://")) return Reglages.t("HTTP en clair : hors du réseau local, utilise HTTPS.", "Plain HTTP: outside the local network, use HTTPS.")
        return ""
    }
    readonly property bool urlValide: /^https?:\/\/[^\s/@?#]+(:\d+)?(\/[^\s?#]*)?$/i.test(url.text.trim())

    function afficher(nom) {
        var ecrans = Quickshell.screens
        for (var i = 0; i < ecrans.length; i++) if (ecrans[i].name === nom) { screen = ecrans[i]; break }
        resultat = null; message = ""; erreur = false; cle.text = ""
        visible = true
        lecture.running = true
        url.forceActiveFocus()
    }
    function close() { visible = false; cle.text = "" }
    onClosed: close()
    function valeurs() {
        return JSON.stringify({ url: url.text.trim(), secret_key: cle.text, user_id: ident.text.trim(), timeout: delai.text.trim() })
    }
    function tester() {
        if (occupe || !urlValide) return
        resultat = null; message = ""; erreur = false
        test.stdinEnabled = true; test.running = true
    }
    function enregistrer() {
        if (occupe || !urlValide || (!cle.text && !cleEnregistree)) return
        message = ""; erreur = false
        enregistrement.stdinEnabled = true; enregistrement.running = true
    }

    Process {
        id: lecture
        command: [fen.bin + "nc-assistant", "config-ile", "lire"]
        stdout: StdioCollector {
            onStreamFinished: {
                try {
                    var d = JSON.parse(text)
                    url.text = d.url || ""; ident.text = d.user_id || ""; delai.text = String(d.timeout || "180")
                    fen.cleEnregistree = !!d.cle; fen.existe = !!d.existe
                } catch (e) {}
            }
        }
    }
    Process {
        id: test
        command: [fen.bin + "nc-assistant", "config-ile", "tester"]
        onStarted: { write(fen.valeurs() + "\n"); stdinEnabled = false }
        stdout: StdioCollector {
            onStreamFinished: {
                try { fen.resultat = JSON.parse(text.trim().split("\n").pop()) }
                catch (e) { fen.resultat = { online: false, error: Reglages.t("Réponse illisible de nc-assistant.", "Unreadable answer from nc-assistant.") } }
            }
        }
        stderr: StdioCollector {}
    }
    Process {
        id: enregistrement
        command: [fen.bin + "nc-assistant", "config-ile", "enregistrer"]
        onStarted: { write(fen.valeurs() + "\n"); stdinEnabled = false }
        stdout: StdioCollector {
            onStreamFinished: {
                var d = null
                try { d = JSON.parse(text.trim().split("\n").pop()) } catch (e) {}
                if (d && d.ok) {
                    fen.erreur = false; fen.cleEnregistree = true; fen.existe = true; cle.text = ""
                    fen.message = Reglages.t("Connexion enregistrée.", "Connection saved.") + (d.warning ? " " + d.warning : "")
                    JarvisEtat.actualiser()
                } else {
                    fen.erreur = true
                    fen.message = d && d.error ? d.error : Reglages.t("Enregistrement impossible.", "Cannot save.")
                }
            }
        }
        stderr: StdioCollector {}
    }

    Shortcut { sequence: "Escape"; onActivated: { if (fen.ileOuverte) fen.fermerIle(); else fen.close() } }
    Shortcut { sequences: ["Ctrl+Return", "Ctrl+Enter", "Ctrl+S"]; onActivated: fen.enregistrer() }

    component Champ: Column {
        id: ch
        property string titre
        property string aide: ""
        property alias texte: saisie.text
        property alias saisie: saisie
        property bool secret: false
        property string indication: ""
        width: parent.width; spacing: 6
        Texte { text: ch.titre; font.pixelSize: 13; font.weight: Font.DemiBold; leftPadding: 4 }
        Rectangle {
            width: parent.width; height: 42; radius: 21; color: Couleurs.gris2
            border.width: 1.5; border.color: saisie.activeFocus ? Couleurs.accent : "transparent"
            TextInput {
                id: saisie
                anchors.fill: parent; anchors.leftMargin: 16; anchors.rightMargin: 16
                verticalAlignment: TextInput.AlignVCenter; clip: true; selectByMouse: true; activeFocusOnTab: true
                color: Couleurs.texte; selectionColor: Couleurs.accent; font.pixelSize: 14
                echoMode: ch.secret ? TextInput.Password : TextInput.Normal
                onAccepted: fen.tester()
                Texte { anchors.fill: parent; verticalAlignment: Text.AlignVCenter; visible: !saisie.text && !saisie.activeFocus
                        text: ch.indication; secondaire: true; font.pixelSize: 13; elide: Text.ElideRight }
            }
        }
        Texte { visible: ch.aide !== ""; width: parent.width; text: ch.aide; secondaire: true; font.pixelSize: 11; wrapMode: Text.Wrap; elide: Text.ElideNone; leftPadding: 4 }
    }

    Item {
        id: tout
        objectName: "nc-connexion-tout"
        anchors.fill: parent
        Rectangle { anchors.fill: parent; color: Couleurs.fond }
        Flickable {
            anchors.fill: parent; anchors.margins: 24
            contentHeight: colonne.implicitHeight; clip: true; boundsBehavior: Flickable.StopAtBounds
            Column {
                id: colonne
                width: parent.width; spacing: 16
                Row {
                    spacing: 12
                    Etincelle { anchors.verticalCenter: parent.verticalCenter; taille: 30; agent: "assistant"; tourne: fen.occupe }
                    Column {
                        anchors.verticalCenter: parent.verticalCenter; spacing: 2
                        Texte { text: Reglages.t("Connexion à JARVIS", "JARVIS connection"); font.pixelSize: 20; font.weight: Font.Bold }
                        Texte { text: fen.existe ? Reglages.t("Modifie la connexion à ton serveur.", "Edit the connection to your server.")
                                                 : Reglages.t("Relie l'île, le cockpit et Telegram à ton serveur JARVIS.", "Link the island, the dashboard and Telegram to your JARVIS server.")
                                secondaire: true; font.pixelSize: 12 }
                    }
                }
                Champ {
                    id: champUrl
                    titre: Reglages.t("Adresse du serveur", "Server address")
                    indication: "https://jarvis.example.org"
                    aide: Reglages.t("L'adresse du gateway JARVIS-BIS (avec son préfixe de chemin s'il en a un).", "The JARVIS-BIS gateway address (with its path prefix if any).")
                }
                Texte {
                    objectName: "nc-connexion-avertissement"
                    visible: fen.avertissement !== ""; width: parent.width; wrapMode: Text.Wrap; elide: Text.ElideNone
                    text: "⚠  " + fen.avertissement; color: Couleurs.orange; font.pixelSize: 12
                }
                Champ {
                    id: champCle
                    secret: true
                    titre: Reglages.t("Clé secrète", "Secret key")
                    indication: fen.cleEnregistree ? Reglages.t("Clé enregistrée : laisser vide pour la garder", "Saved key: leave empty to keep it")
                                                   : Reglages.t("La SECRET_KEY du serveur", "The server's SECRET_KEY")
                }
                Row {
                    width: parent.width; spacing: 12
                    Champ { id: champIdent; width: (parent.width - 12) * 0.62; titre: Reglages.t("Identifiant", "User ID"); indication: Quickshell.env("USER") || "" }
                    Champ { id: champDelai; width: (parent.width - 12) * 0.38; titre: Reglages.t("Délai d'attente (s)", "Timeout (s)"); indication: "180" }
                }
                Row {
                    spacing: 10
                    JarvisBouton { objectName: "nc-connexion-tester"; texte: test.running ? Reglages.t("Test en cours…", "Testing…") : Reglages.t("Tester la connexion", "Test connection")
                                   enabled: fen.urlValide && !fen.occupe; onClic: fen.tester() }
                    JarvisBouton { objectName: "nc-connexion-enregistrer"; primaire: true; texte: Reglages.t("Enregistrer", "Save")
                                   enabled: fen.urlValide && !fen.occupe && (champCle.texte !== "" || fen.cleEnregistree); onClic: fen.enregistrer() }
                    JarvisBouton { texte: Reglages.t("Fermer", "Close"); onClic: fen.close() }
                }
                // Résultat du test
                Rectangle {
                    objectName: "nc-connexion-resultat"
                    visible: fen.resultat !== null
                    width: parent.width; height: visible ? res.implicitHeight + 24 : 0; radius: 16
                    color: fen.resultat && fen.resultat.online ? Qt.rgba(0.2, 0.7, 0.4, 0.14) : Qt.rgba(0.9, 0.3, 0.3, 0.14)
                    Column {
                        id: res
                        x: 14; y: 12; width: parent.width - 28; spacing: 4
                        Row {
                            spacing: 8
                            Ico { nom: fen.resultat && fen.resultat.online ? "check_circle" : "error"; taille: 18
                                  color: fen.resultat && fen.resultat.online ? Couleurs.vert : Couleurs.rouge }
                            Texte { font.weight: Font.DemiBold
                                    text: !fen.resultat ? "" : fen.resultat.online
                                          ? Reglages.t("Connexion réussie", "Connected") + (fen.resultat.latency_ms !== undefined ? " · " + fen.resultat.latency_ms + " ms" : "")
                                          : Reglages.t("Connexion impossible", "Connection failed") }
                        }
                        Texte { visible: !!(fen.resultat && fen.resultat.error); width: parent.width; wrapMode: Text.Wrap; elide: Text.ElideNone; font.pixelSize: 12
                                text: fen.resultat && fen.resultat.error ? fen.resultat.error : "" }
                        Texte { visible: !!(fen.resultat && fen.resultat.version); secondaire: true; font.pixelSize: 12
                                text: fen.resultat && fen.resultat.version ? Reglages.t("Version du serveur : ", "Server version: ") + fen.resultat.version : "" }
                        Texte { visible: !!(fen.resultat && fen.resultat.public_url && fen.resultat.public_url !== url.text.trim()); width: parent.width; wrapMode: Text.Wrap
                                elide: Text.ElideNone; secondaire: true; font.pixelSize: 12
                                text: fen.resultat && fen.resultat.public_url ? Reglages.t("Adresse publique annoncée : ", "Announced public address: ") + fen.resultat.public_url : "" }
                    }
                }
                Texte {
                    objectName: "nc-connexion-message"
                    visible: fen.message !== ""; width: parent.width; wrapMode: Text.Wrap; elide: Text.ElideNone
                    text: fen.message; color: fen.erreur ? Couleurs.rouge : Couleurs.vert
                }
                Texte {
                    width: parent.width; wrapMode: Text.Wrap; elide: Text.ElideNone; secondaire: true; font.pixelSize: 11
                    text: Reglages.t("Entrée : tester · Ctrl + Entrée : enregistrer · Échap : fermer. La clé n'est jamais affichée ni relue ; elle est rangée dans ~/.config/nc/assistant.conf, lisible par toi seul.",
                                     "Enter: test · Ctrl + Enter: save · Esc: close. The key is never shown or read back; it is stored in ~/.config/nc/assistant.conf, readable only by you.")
                }
            }
        }
    }
    // Raccourcis vers les champs (les tests et le reste de la fenêtre s'en servent)
    property alias url: champUrl.saisie
    property alias cle: champCle.saisie
    property alias ident: champIdent.saisie
    property alias delai: champDelai.saisie
}

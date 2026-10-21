// Fenêtre « Clés des IA » (nc-ia configurer, ligne « Clés d'API des IA » de la fenêtre des réglages) : les services
// d'IA par clé d'API (Anthropic, OpenAI, Gemini, Mistral, Groq, DeepSeek, OpenRouter) et ce qui est déjà sur le PC
// (Claude Code, Codex, Gemini CLI, OpenCode, Qwen, Ollama, JARVIS).
// « Enregistrer » passe la clé à nc-ia par l'entrée standard (jamais en argument), puis l'essaie tout de suite ; la
// clé n'est jamais relue ni affichée (seulement ses 4 derniers caractères). Rangée dans ~/.config/nc/ia.conf (0600).
// Clavier : Tab d'un champ à l'autre, Entrée enregistre la clé du champ, Échap ferme (l'île d'abord).
import QtQuick
import Quickshell
import Quickshell.Io

FloatingWindow {
    id: fen
    title: Reglages.t("Clés des IA", "AI keys")
    visible: false
    implicitWidth: 640; implicitHeight: 720; minimumSize: Qt.size(480, 520)
    color: Couleurs.fond
    readonly property string bin: Quickshell.env("HOME") + "/.local/bin/"
    property var etat: null                    // nc-ia etat --json
    property var cles: ({})                    // nc-ia cles --json : {id: {origine, fin}}
    property var essais: ({})                  // id → {ok, ms, erreur} du dernier essai
    property string enCours: ""                // l'IA dont la clé s'enregistre ou s'essaie
    property string cleEnAttente: ""
    property string message: ""
    property bool ileOuverte: false
    signal fermerIle()
    readonly property bool occupe: lecture.running || lectureCles.running || ecriture.running || essai.running
    readonly property var apis: etat ? etat.ias.filter(i => i.genre === "api") : []
    readonly property var autres: etat ? etat.ias.filter(i => i.genre !== "api") : []

    function afficher(nom) {
        var ecrans = Quickshell.screens
        for (var i = 0; i < ecrans.length; i++) if (ecrans[i].name === nom) { screen = ecrans[i]; break }
        essais = ({}); message = ""
        visible = true
        relire()
    }
    function close() { visible = false; cleEnAttente = ""; viderChamps() }
    onClosed: close()
    signal viderChamps()
    function relire() { lecture.running = true; lectureCles.running = true }
    // Une clé vide efface celle qui est enregistrée dans ia.conf
    function enregistrer(id, valeur) {
        if (occupe) return
        enCours = id; cleEnAttente = valeur; message = ""
        ecriture.command = [bin + "nc-ia", "cle", id]
        ecriture.stdinEnabled = true; ecriture.running = true
    }
    function essayer(id) {
        if (essai.running) return
        enCours = id
        essai.command = [bin + "nc-ia", "tester"].concat(id ? [id] : []).concat(["--json"])
        essai.running = true
    }

    Process {
        id: lecture
        command: [fen.bin + "nc-ia", "etat", "--json"]
        stdout: StdioCollector { onStreamFinished: { try { fen.etat = JSON.parse(text) } catch (e) {} } }
    }
    Process {
        id: lectureCles
        command: [fen.bin + "nc-ia", "cles", "--json"]
        stdout: StdioCollector { onStreamFinished: { try { fen.cles = JSON.parse(text) } catch (e) {} } }
    }
    Process {
        id: ecriture
        onStarted: { write(fen.cleEnAttente + "\n"); fen.cleEnAttente = ""; stdinEnabled = false }
        stdout: StdioCollector {}
        stderr: StdioCollector { id: erreurEcriture }
        onExited: code => {
            if (code !== 0) { fen.message = erreurEcriture.text.trim() || Reglages.t("Enregistrement impossible.", "Cannot save."); return }
            fen.viderChamps()
            fen.relire()
            fen.essayer(fen.enCours)            // essayée tout de suite (une clé effacée échoue : sans importance)
        }
    }
    Process {
        id: essai
        stdout: StdioCollector {
            onStreamFinished: {
                var e = Object.assign({}, fen.essais)
                try { JSON.parse(text).forEach(x => e[x.id] = x) } catch (err) {}
                fen.essais = e
                fen.enCours = ""
                fen.relire()
            }
        }
        stderr: StdioCollector {}
    }

    Shortcut { sequence: "Escape"; onActivated: { if (fen.ileOuverte) fen.fermerIle(); else fen.close() } }

    component Ligne: Rectangle {
        id: l
        required property var modelData          // une IA de nc-ia etat
        readonly property var ia: modelData
        readonly property var cle: fen.cles[ia.id] || ({})
        readonly property var test: fen.essais[ia.id]
        readonly property bool api: ia.genre === "api"
        width: parent ? parent.width : 0
        height: corps.implicitHeight + 24; radius: 18; color: Couleurs.gris2
        Column {
            id: corps
            x: 16; y: 12; width: parent.width - 32; spacing: 8
            Row {
                width: parent.width; spacing: 10
                Etincelle { anchors.verticalCenter: parent.verticalCenter; taille: 18; agent: l.ia.agent; tourne: fen.enCours === l.ia.id }
                Texte { anchors.verticalCenter: parent.verticalCenter; text: l.ia.nom; font.pixelSize: 14; font.weight: Font.DemiBold }
                Texte {
                    anchors.verticalCenter: parent.verticalCenter; secondaire: true; font.pixelSize: 12
                    text: l.api ? (l.cle.origine === "fichier" ? Reglages.t("clé ", "key ") + l.cle.fin
                                   : l.cle.origine === "env" ? Reglages.t("clé de l'environnement ", "environment key ") + l.cle.fin
                                   : Reglages.t("pas de clé", "no key"))
                                : (l.ia.disponible ? Reglages.t("prêt", "ready") : Reglages.t("absent", "not found"))
                }
            }
            // Clé d'API : saisie masquée, Enregistrer (puis essai), Effacer
            Row {
                visible: l.api; width: parent.width; spacing: 8
                Rectangle {
                    width: parent.width - enr.width - eff.width - 16; height: 36; radius: 18; color: Couleurs.fond
                    border.width: 1.5; border.color: saisie.activeFocus ? Couleurs.accent : "transparent"
                    TextInput {
                        id: saisie
                        objectName: "nc-cles-" + l.ia.id
                        anchors.fill: parent; anchors.leftMargin: 14; anchors.rightMargin: 14
                        verticalAlignment: TextInput.AlignVCenter; clip: true; echoMode: TextInput.Password; activeFocusOnTab: true
                        color: Couleurs.texte; selectionColor: Couleurs.accent; font.pixelSize: 13
                        onAccepted: if (text) fen.enregistrer(l.ia.id, text)
                        Connections { target: fen; function onViderChamps() { saisie.text = "" } }
                        Texte { anchors.fill: parent; verticalAlignment: Text.AlignVCenter; visible: !saisie.text && !saisie.activeFocus
                                secondaire: true; font.pixelSize: 12; elide: Text.ElideRight
                                text: l.cle.origine ? Reglages.t("Nouvelle clé (pour la remplacer)", "New key (to replace it)") : Reglages.t("Colle la clé ici", "Paste the key here") }
                    }
                }
                JarvisBouton { id: enr; primaire: true; texte: Reglages.t("Enregistrer", "Save"); enabled: saisie.text !== "" && !fen.occupe
                               onClic: fen.enregistrer(l.ia.id, saisie.text) }
                JarvisBouton { id: eff; texte: Reglages.t("Effacer", "Remove"); visible: l.cle.origine === "fichier"; enabled: !fen.occupe
                               onClic: fen.enregistrer(l.ia.id, "") }
            }
            Row {
                spacing: 14
                Texte { visible: l.api && !!l.ia.inscription; font.pixelSize: 12; color: Couleurs.accent
                        text: Reglages.t("Créer une clé ↗", "Create a key ↗")
                        MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: Qt.openUrlExternally(l.ia.inscription) } }
                Texte { visible: l.ia.id === "jarvis"; font.pixelSize: 12; color: Couleurs.accent
                        text: l.ia.disponible ? Reglages.t("Modifier la connexion ↗", "Edit the connection ↗") : Reglages.t("Relier JARVIS ↗", "Connect JARVIS ↗")
                        MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor
                                    onClicked: Quickshell.execDetached([fen.bin + "nc-assistant", "configurer"]) } }
                Texte { visible: l.ia.disponible || (l.api && !!l.cle.origine); font.pixelSize: 12; color: Couleurs.accent
                        text: Reglages.t("Essayer", "Test")
                        MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: fen.essayer(l.ia.id) } }
                Texte {
                    objectName: "nc-cles-essai-" + l.ia.id
                    visible: !!l.test; font.pixelSize: 12
                    color: l.test && l.test.ok ? Couleurs.vert : Couleurs.rouge
                    width: Math.min(implicitWidth, corps.width - 220); wrapMode: Text.Wrap; elide: Text.ElideNone
                    text: !l.test ? "" : l.test.ok ? "✓ " + Reglages.t("répond", "answers") + " · " + l.test.ms + " ms" : "✗ " + (l.test.erreur || "")
                }
            }
        }
    }

    Item {
        anchors.fill: parent
        Rectangle { anchors.fill: parent; color: Couleurs.fond }
        Flickable {
            anchors.fill: parent; anchors.margins: 22
            contentHeight: colonne.implicitHeight; clip: true; boundsBehavior: Flickable.StopAtBounds
            Column {
                id: colonne
                width: parent.width; spacing: 12
                Row {
                    spacing: 12
                    Etincelle { anchors.verticalCenter: parent.verticalCenter; taille: 30; agent: "claude"; tourne: fen.occupe }
                    Column {
                        anchors.verticalCenter: parent.verticalCenter; spacing: 2
                        Texte { text: Reglages.t("Clés des IA", "AI keys"); font.pixelSize: 20; font.weight: Font.Bold }
                        Texte {
                            objectName: "nc-cles-resume"
                            secondaire: true; font.pixelSize: 12
                            text: !fen.etat ? "" : fen.etat.coupee ? Reglages.t("L'IA est coupée partout (nc-reglages → Intelligence artificielle).", "AI is turned off everywhere (nc-settings → Artificial intelligence).")
                                  : (fen.etat.usages.question.nom ? Reglages.t("Répond maintenant : ", "Answering now: ") + fen.etat.usages.question.nom
                                                                   : Reglages.t("Aucune IA disponible pour l'instant.", "No AI available yet."))
                        }
                    }
                }
                Texte { text: Reglages.t("Par clé d'API", "With an API key"); font.pixelSize: 13; font.weight: Font.DemiBold; leftPadding: 4 }
                Repeater { model: fen.apis; delegate: Ligne {} }
                Texte { text: Reglages.t("Déjà sur ce PC (abonnements, Ollama, JARVIS)", "Already on this PC (subscriptions, Ollama, JARVIS)")
                        font.pixelSize: 13; font.weight: Font.DemiBold; leftPadding: 4; topPadding: 6 }
                Repeater { model: fen.autres; delegate: Ligne {} }
                Row {
                    spacing: 10; topPadding: 4
                    JarvisBouton { texte: essai.running && fen.enCours === "" ? Reglages.t("Essai en cours…", "Testing…") : Reglages.t("Essayer toutes les IA disponibles", "Test all available AIs")
                                   enabled: !fen.occupe; onClic: fen.essayer("") }
                    JarvisBouton { texte: Reglages.t("Fermer", "Close"); onClic: fen.close() }
                }
                Texte {
                    objectName: "nc-cles-message"
                    visible: fen.message !== ""; width: parent.width; wrapMode: Text.Wrap; elide: Text.ElideNone
                    text: fen.message; color: Couleurs.rouge
                }
                Texte {
                    width: parent.width; wrapMode: Text.Wrap; elide: Text.ElideNone; secondaire: true; font.pixelSize: 11
                    text: Reglages.t("Les clés ne sont jamais affichées : seulement leurs 4 derniers caractères. Elles sont rangées dans ~/.config/nc/ia.conf, lisible par toi seul, et ne partent que vers leur service. Le choix de l'IA (automatique, choisie, aucune) est dans nc-reglages → Intelligence artificielle.",
                                     "Keys are never shown: only their last 4 characters. They are stored in ~/.config/nc/ia.conf, readable only by you, and only go to their own service. The AI choice (automatic, chosen, none) is in nc-settings → Artificial intelligence.")
                }
            }
        }
    }
}

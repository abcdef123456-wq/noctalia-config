pragma Singleton
// Conversation partagée entre les écrans, indépendante du Loader de chaque page.
// Historique et brouillon en RAM uniquement. Aucune scrutation réseau.
import QtQuick
import Quickshell
import Quickshell.Io

Singleton {
    id: a
    readonly property string bin: Quickshell.env("HOME") + "/.local/bin/"
    readonly property string session: {
        var s = ""
        for (var i = 0; i < 32; i++) s += Math.floor(Math.random() * 16).toString(16)
        return s
    }
    property string brouillon: ""
    property var messages: []
    property string erreur: ""
    property bool enCours: false
    property string question: ""
    property bool sortieFinie: false
    property bool processusFini: false
    property int code: -1
    property string reponse: ""

    function ajouter(role, texte) {
        var m = messages.concat([{role: role, texte: texte}]).slice(-24)
        var total = m.reduce((n, x) => n + x.texte.length, 0)
        while (total > 48000 && m.length > 1) total -= m.shift().texte.length
        messages = m
    }
    function envoyer() {
        var q = brouillon.trim()
        if (enCours || !q) return
        if (q.length > 8000) {
            erreur = Reglages.t("8 000 caractères maximum.", "8,000 characters maximum.")
            return
        }
        question = q
        erreur = ""
        reponse = ""
        sortieFinie = false
        processusFini = false
        code = -1
        enCours = true
        ajouter("vous", q)
        brouillon = ""
        requete.stdinEnabled = true
        requete.running = true
        demarrage.restart()
    }
    function terminer() {
        if (!enCours || !sortieFinie || !processusFini) return
        demarrage.stop()
        var r = null
        try { r = JSON.parse(reponse) } catch (_) {}
        if (code === 0 && r && r.ok === true && typeof r.text === "string" && r.text.length) {
            ajouter("assistant", r.text.slice(0, 16000) + (r.truncated ? Reglages.t("\n\n[Réponse abrégée dans l’île]", "\n\n[Answer shortened in the island]") : ""))
        } else {
            erreur = r && typeof r.error === "string" ? r.error.slice(0, 1000)
                    : Reglages.t("Impossible de recevoir la réponse. Vérifie la connexion et la configuration.",
                                 "Unable to receive the answer. Check the connection and configuration.")
            // Permet de corriger ou renvoyer manuellement ; aucune répétition automatique.
            if (!brouillon) brouillon = question
        }
        question = ""
        reponse = ""
        enCours = false
    }
    function effacer() { if (!enCours) { messages = []; erreur = "" } }
    function configurer() { Quickshell.execDetached(["kitty", "--class", "nc-reglages", "-e", bin + "nc-reglages", "assistant"]) }

    Process {
        id: requete
        command: [a.bin + "nc-assistant", "requete-ile"]
        onStarted: {
            demarrage.stop()
            write(JSON.stringify({session_id: a.session, question: a.question}) + "\n")
            stdinEnabled = false
        }
        stdout: StdioCollector {
            onStreamFinished: { a.reponse = text; a.sortieFinie = true; a.terminer() }
        }
        // Ne pas envoyer les messages privés du client dans les journaux Quickshell.
        stderr: StdioCollector {}
        onExited: (exitCode, exitStatus) => {
            a.code = exitCode; a.processusFini = true; a.terminer()
        }
    }
    // QProcess ne produit pas forcément exited() si l'exécutable est absent.
    Timer {
        id: demarrage
        interval: 3000
        onTriggered: {
            if (a.enCours && !requete.running) {
                a.code = -1; a.processusFini = true; a.sortieFinie = true; a.terminer()
            }
        }
    }
}

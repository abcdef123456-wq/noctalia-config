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
    property bool reglagesOuverts: false
    property bool reglagesEnCours: false
    property bool reglagesDisponibles: false
    property var moteurs: [
        {id:"agy", name:"Antigravity", installed:false}, {id:"codex", name:"Codex", installed:false},
        {id:"claude", name:"Claude Code", installed:false}, {id:"opencode", name:"OpenCode", installed:false}
    ]
    property string moteur: ""
    property string modele: ""
    property string effort: ""
    property string erreurReglages: ""
    property string operationReglages: ""
    property var parametresReglages: ({})
    property string sortieReglages: ""
    property bool sortieReglagesFinie: false
    property bool processusReglagesFini: false
    property int codeReglages: -1
    readonly property var moteurCourant: moteurs.find(m => m.id === moteur) || ({})
    readonly property var modeles: moteurCourant.models || []
    readonly property var modeleCourant: modeles.find(m => m.id === modele) || ({})
    readonly property var efforts: modeleCourant.efforts || moteurCourant.efforts || []

    function ouvrirReglages() {
        reglagesOuverts = !reglagesOuverts
        if (reglagesOuverts) lireReglages()
    }
    function choisirMoteur(id) { moteur = id; modele = ""; effort = "" }
    function lireReglages() { lancerReglages("quick-settings", {}) }
    function appliquerReglages() {
        if (enCours || !reglagesDisponibles) return
        lancerReglages("session.update", {engine:moteur, model:modele.trim(), effort:effort})
    }
    function lancerReglages(op, params) {
        if (reglagesEnCours) return
        operationReglages = op; parametresReglages = params; erreurReglages = ""
        sortieReglages = ""; sortieReglagesFinie = false; processusReglagesFini = false; codeReglages = -1
        reglagesEnCours = true; reglagesProcess.stdinEnabled = true; reglagesProcess.running = true; attenteReglages.restart()
    }
    function finirReglages() {
        if (!reglagesEnCours || !sortieReglagesFinie || !processusReglagesFini) return
        attenteReglages.stop()
        var r = null
        try { r = JSON.parse(sortieReglages) } catch (_) {}
        var ok = codeReglages === 0 && r && r.ok === true && r.data && !r.data.error
        if (ok && operationReglages === "quick-settings") {
            reglagesDisponibles = !!r.data.session && Array.isArray(r.data.engines)
            if (reglagesDisponibles) {
                moteurs = r.data.engines; moteur = r.data.session.engine || "agy"
                modele = r.data.session.model || ""; effort = r.data.session.effort || ""
            } else ok = false
        }
        if (!ok) {
            erreurReglages = r && typeof r.error === "string" ? r.error.slice(0,500)
                : Reglages.t("Réglages indisponibles. Vérifie la connexion et mets à jour les adaptateurs JARVIS du gateway et du runner.", "Settings unavailable. Check the connection and update the JARVIS gateway and runner adapters.")
            reglagesDisponibles = false
        }
        var actualiser = ok && operationReglages === "session.update"
        sortieReglages = ""; parametresReglages = {}; reglagesEnCours = false
        if (actualiser) lireReglages()
    }

    function ajouter(role, texte) {
        var m = messages.concat([{role: role, texte: texte}]).slice(-24)
        var total = m.reduce((n, x) => n + x.texte.length, 0)
        while (total > 48000 && m.length > 1) total -= m.shift().texte.length
        messages = m
    }
    function envoyer() {
        var q = brouillon.trim()
        if (enCours || reglagesEnCours || !q) return
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
    function ouvrirDashboard() { Quickshell.execDetached([bin + "nc-jarvis", "tableau"]) }

    Process {
        id: reglagesProcess
        command: [a.bin + "nc-jarvis", "requete"]
        onStarted: {
            attenteReglages.stop()
            write(JSON.stringify({op:a.operationReglages, params:a.parametresReglages, confirmed:a.operationReglages === "session.update"}) + "\n")
            stdinEnabled = false
        }
        stdout: StdioCollector { onStreamFinished: { a.sortieReglages = text; a.sortieReglagesFinie = true; a.finirReglages() } }
        stderr: StdioCollector {}
        onExited: (exitCode, exitStatus) => { a.codeReglages = exitCode; a.processusReglagesFini = true; a.finirReglages() }
    }
    Timer { id:attenteReglages; interval:3000; onTriggered: if (a.reglagesEnCours && !reglagesProcess.running) { a.codeReglages=-1; a.processusReglagesFini=true; a.sortieReglagesFinie=true; a.finirReglages() } }

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

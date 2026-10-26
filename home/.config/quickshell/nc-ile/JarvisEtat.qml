pragma Singleton
import QtQuick
import Quickshell
import Quickshell.Io

Singleton {
    id: j
    property bool ouvert: false
    property bool enCours: false
    property string operation: ""
    property var parametres: ({})
    property bool confirme: false
    property var etat: ({})
    property var resultats: ({})
    property var catalogue: ({})
    property string erreur: ""
    property bool sortieFinie: false
    property bool processusFini: false
    property int code: -1
    property string sortie: ""
    signal termine(string operation, bool succes)
    readonly property var gestion: etat.management || ({})
    readonly property bool administration: gestion.protocol === 1 && etat.obsolete !== true
    readonly property var modules: gestion.modules || etat.tools || []
    readonly property var champs: gestion.fields || []
    function actualiser() { executer("overview", {}, false) }
    function executer(op, params, confirmation) {
        if (enCours) return
        operation = op; parametres = params || {}; confirme = confirmation === true
        sortieFinie = false; processusFini = false; sortie = ""; code = -1; erreur = ""; enCours = true
        requete.stdinEnabled = true; requete.running = true; demarrage.restart()
    }
    function finir() {
        if (!enCours || !sortieFinie || !processusFini) return
        demarrage.stop()
        var r = null
        try { r = JSON.parse(sortie) } catch (_) {}
        var ok = code === 0 && r && r.ok === true && r.data && !r.data.error
        if (ok) {
            let copie = Object.assign({}, resultats); copie[operation] = r.data; resultats = copie
            if (operation === "overview") { etat = r.data; catalogue = r.data.catalogue || {} }
        } else {
            erreur = r && typeof r.error === "string" ? r.error.slice(0, 1000)
                   : Reglages.t("Opération impossible. Vérifie la connexion et l’adaptateur de gestion.", "Operation failed. Check the connection and management adapter.")
            if (operation === "overview") etat = Object.assign({}, etat, {online:false,obsolete:true})
        }
        var op = operation
        parametres = {}; sortie = ""; enCours = false
        termine(op, !!ok)
    }
    function terminal(action) {
        Quickshell.execDetached(["kitty", "--class", "nc-jarvis-deploy", "--title", "JARVIS", "-e",
                                Quickshell.env("HOME") + "/.local/bin/nc-jarvis", action])
    }
    function texte(data) {
        if (!data) return ""
        var s = data.message || data.output || data.text
        if (typeof s === "string") return s.slice(0, 20000)
        return JSON.stringify(data, null, 2).slice(0, 20000)
    }
    Process {
        id: requete
        command: [Quickshell.env("HOME") + "/.local/bin/nc-jarvis", "requete"]
        onStarted: {
            demarrage.stop()
            write(JSON.stringify({op: j.operation, params: j.parametres, confirmed: j.confirme}) + "\n")
            stdinEnabled = false; j.parametres = {}
        }
        stdout: StdioCollector { onStreamFinished: { j.sortie = text; j.sortieFinie = true; j.finir() } }
        stderr: StdioCollector {}
        onExited: (exitCode, exitStatus) => { j.code = exitCode; j.processusFini = true; j.finir() }
    }
    // Garde : une requête qui ne finit jamais laissait enCours vrai et les boutons grisés ; arrêtée au bout de 90 s
    Timer {
        id: garde; interval: 90000; running: j.enCours
        onTriggered: { requete.running = false; j.code = -1; j.sortieFinie = true; j.processusFini = true; j.finir() }
    }
    Timer { id: demarrage; interval: 3000; onTriggered: if (j.enCours && !requete.running) { j.code = -1; j.sortieFinie = true; j.processusFini = true; j.finir() } }
}

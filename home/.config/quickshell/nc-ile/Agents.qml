pragma Singleton
// Claude Code dans l'île (comme l'appli coucou) : sessions suivies par ~/.local/bin/nc-claude, que les hooks de Claude
// Code appellent à chaque étape ; relues dès qu'elles changent. Les réponses aux demandes (autoriser, refuser, choix
// d'une question) sont écrites dans …/nc-claude/reponses/ID, où le hook les attend.
// Réglages (nc-reglages, Claude Code) : CLAUDE_ILE (oui/non), CLAUDE_DEMANDES (ile/terminal)
import QtQuick
import Quickshell
import Quickshell.Io

Singleton {
    id: a
    readonly property string dossier: (Quickshell.env("XDG_RUNTIME_DIR") || "/tmp") + "/nc-claude"
    readonly property color couleur: "#d97757"           // l'orange de Claude
    readonly property bool active: Reglages.val("CLAUDE_ILE", "oui") !== "non"
    property var donnees: ({ sessions: {}, demandes: {} })

    readonly property var sessions: {
        if (!active) return []
        var l = Object.values(donnees.sessions || {})
        l.sort((x, y) => (y.maj || 0) - (x.maj || 0))
        return l
    }
    readonly property var demandes: active ? Object.values(donnees.demandes || {}).sort((x, y) => (x.t || 0) - (y.t || 0)) : []
    readonly property var demande: demandes.length ? demandes[0] : null
    readonly property var enCours: sessions.filter(s => s.etat === "travail" || s.etat === "demande" || s.etat === "terminal")
    readonly property bool travaille: enCours.length > 0
    readonly property var principale: enCours.length ? enCours[0] : (sessions.length ? sessions[0] : null)
    // Page de l'île : tant qu'une session a fait quelque chose il y a moins de 30 min
    readonly property bool aPage: sessions.some(s => s.etat !== "pret" && Etat.maintenant.getTime() / 1000 - (s.maj || 0) < 1800)
    readonly property bool attendTerminal: sessions.some(s => s.etat === "terminal")

    FileView {
        id: lecture
        path: a.dossier + "/etat.json"
        watchChanges: true
        printErrors: false
        onFileChanged: reload()
        onLoaded: { try { a.donnees = JSON.parse(text()) } catch (e) {} }
    }
    // Le fichier est remplacé d'un coup à chaque étape : relu aussi régulièrement pendant le travail (filet de sécurité)
    Timer { interval: 1200; repeat: true; running: a.travaille || a.demande !== null; onTriggered: lecture.reload() }

    // Fin d'une session (« Claude a terminé ») et demande dans le terminal : réaction de la pilule
    property var avant: ({})
    property string dernierFini: ""
    onSessionsChanged: {
        var n = {}
        for (var i = 0; i < sessions.length; i++) {
            var s = sessions[i], e = avant[s.id]
            n[s.id] = s.etat
            if (e && e !== s.etat && s.etat === "fini") { dernierFini = s.projet; Etat.activite("claude-fini", 4500) }
        }
        avant = n
    }

    function repondre(id, choix) {
        Quickshell.execDetached(["sh", "-c", "mkdir -p \"$1\" && printf %s \"$2\" > \"$1/$3\"", "sh", dossier + "/reponses", choix, id])
    }
    function allerTerminal(pid) {
        if (pid > 0) Quickshell.execDetached(["hyprctl", "dispatch", "hl.dsp.focus({ window = 'pid:" + pid + "' })"])
    }
    function depuis(t) {
        var s = Math.max(0, Math.round(Etat.maintenant.getTime() / 1000 - (t || 0)))
        return s < 60 ? "à l'instant" : (s < 3600 ? "il y a " + Math.floor(s / 60) + " min" : "il y a " + Math.floor(s / 3600) + " h")
    }
    function libelle(s) {
        return ({ travail: "Travaille", demande: "Attend ta réponse", terminal: "T'attend dans le terminal", attente: "À toi",
                  fini: "Terminé " + depuis(s.fin), pret: "Prêt" })[s.etat] || s.etat
    }
}

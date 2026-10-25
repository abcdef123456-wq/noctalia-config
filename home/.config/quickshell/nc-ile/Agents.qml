pragma Singleton
// Claude Code et Antigravity dans l'île (comme l'appli coucou) : sessions suivies par ~/.local/bin/nc-claude, que leurs
// hooks appellent à chaque étape (agent: "antigravity" pour celles d'Antigravity) ; relues dès qu'elles changent. Les réponses aux demandes (autoriser, refuser, choix
// d'une question) sont écrites dans …/nc-claude/reponses/ID, où le hook les attend.
// Réglages (nc-reglages, Agents IA) : CLAUDE_ILE et ANTIGRAVITY_ILE (oui/non), CLAUDE_DEMANDES (ile/terminal)
import QtQuick
import Quickshell
import Quickshell.Io

Singleton {
    id: a
    readonly property string dossier: (Quickshell.env("XDG_RUNTIME_DIR") || "/tmp") + "/nc-claude"
    readonly property color couleur: "#d97757"           // l'orange de Claude
    readonly property color couleurAgy: "#4c8df6"        // le bleu d'Antigravity
    // Toutes les IA suivies : nom affiché, couleur (celle de leur logo), réglage qui les coupe
    readonly property var ias: ({
        claude: { nom: "Claude", titre: "Claude Code", couleur: "#d97757", reglage: "CLAUDE_ILE" },
        antigravity: { nom: "Antigravity", titre: "Antigravity", couleur: "#4c8df6", reglage: "ANTIGRAVITY_ILE" },
        opencode: { nom: "OpenCode", titre: "OpenCode", couleur: "#c9cdd4", reglage: "OPENCODE_ILE" },
        codex: { nom: "Codex", titre: "Codex", couleur: "#7c8cff", reglage: "CODEX_ILE" },
        gemini: { nom: "Gemini", titre: "Gemini CLI", couleur: "#6f8ff0", reglage: "GEMINI_ILE" },
        cursor: { nom: "Cursor", titre: "Cursor", couleur: "#dfe3ea", reglage: "CURSOR_ILE" },
        copilot: { nom: "Copilot", titre: "Copilot", couleur: "#a371f7", reglage: "COPILOT_ILE" },
        qwen: { nom: "Qwen", titre: "Qwen Code", couleur: "#7a6cf2", reglage: "QWEN_ILE" },
        omp: { nom: "Oh My Pi", titre: "Oh My Pi", couleur: "#e8b04b", reglage: "OMP_ILE" },
        kiro: { nom: "Kiro", titre: "Kiro", couleur: "#9b5cff", reglage: "KIRO_ILE" },
        amp: { nom: "Amp", titre: "Amp", couleur: "#f2624f", reglage: "AMP_ILE" }
    })
    function agent(s) { return s && ias[s.agent] ? s.agent : "claude" }
    function nom(s) { return ias[agent(s)] ? ias[agent(s)].nom : "Claude" }
    function couleurDe(s) { return ias[agent(s)] ? ias[agent(s)].couleur : couleur }
    function suivie(s) {
        if (!s || s.agent === "assistant") return false
        var k = agent(s)
        return !!ias[k] && Reglages.val(ias[k].reglage, "oui") !== "non"
    }
    property var donnees: ({ sessions: {}, demandes: {} })

    readonly property var sessions: {
        var l = Object.values(donnees.sessions || {}).filter(s => suivie(s))
        l.sort((x, y) => (y.maj || 0) - (x.maj || 0))
        return l
    }
    readonly property var demandes: Object.values(donnees.demandes || {}).filter(d =>
        suivie((donnees.sessions || {})[d.session] || d)).sort((x, y) => (x.t || 0) - (y.t || 0))
    // La demande montrée : celle de la session voulue (notification « Voir »), sinon la plus ancienne
    readonly property var demande: demandes.find(d => d.session === cible) || (demandes.length ? demandes[0] : null)
    // Session montrée en premier dans la page (notification « Voir », clic sur la pilule) ; oubliée à la fermeture
    property string cible: ""
    property bool allerCible: false
    // Garder les transitions de fin pour la pilule, sans conserver leurs cartes dans la page.
    readonly property var sessionsVisibles: sessions.filter(s => s.etat !== "fini")
    // Celles de la page : la session voulue d'abord
    readonly property var sessionsPage: sessionsVisibles.filter(s => s.id === cible).concat(sessionsVisibles.filter(s => s.id !== cible))
    function sessionActive(s) {
        if (!s || s.agent === "assistant") return false
        var age = Etat.maintenant.getTime() / 1000 - (s.maj || 0)
        if (s.etat === "travail") return age < 120
        if (s.etat === "demande" || s.etat === "terminal") return age < 900
        return false
    }
    readonly property var enCours: sessions.filter(s => sessionActive(s))
    readonly property bool travaille: enCours.length > 0
    readonly property var principale: enCours.length ? enCours[0] : (sessions.length ? sessions[0] : null)
    // Page de l'île : tant qu'une session a fait quelque chose il y a moins de 30 min, attend ta réponse (aussi vieille
    // soit la question), ou vient d'être demandée (notification « Voir »)
    readonly property bool aPage: attendTerminal || sessionsVisibles.some(s => s.etat !== "pret"
        && (s.id === cible || Etat.maintenant.getTime() / 1000 - (s.maj || 0) < 1800))
    // Une question laissée dans le terminal ne quitte pas la pilule tant qu'elle n'est pas traitée (6 h au plus, comme
    // nc-claude, au cas où l'agent aurait été tué sans prévenir)
    function attendReponse(s) { return !!s && s.etat === "terminal" && Etat.maintenant.getTime() / 1000 - (s.maj || 0) < 6 * 3600 }
    readonly property bool attendTerminal: sessions.some(s => attendReponse(s))

    FileView {
        id: lecture
        path: a.dossier + "/etat.json"
        watchChanges: true
        printErrors: false
        onFileChanged: reload()
        onLoaded: {
            var t = text()
            if (t === a.brut) return                     // inchangé : rien à redessiner (texte en cours de saisie gardé)
            a.brut = t
            try { a.donnees = JSON.parse(t) } catch (e) {}
            Qt.callLater(a.versCible)
        }
    }
    property string brut: ""
    // Le fichier est remplacé d'un coup à chaque étape, et la surveillance de Quickshell finit par le perdre (l'île ne
    // voyait plus du tout Claude) : relu aussi régulièrement, vite pendant le travail
    // Écran éteint ou verrouillé : suspendu (relu dès le réveil) ; au repos, un filet lent suffit (la surveillance voit les changements)
    Timer { interval: a.travaille || a.demande !== null ? 1200 : 10000; repeat: true; running: Etat.ecranVu; triggeredOnStart: true; onTriggered: lecture.reload() }

    // Fin d'une session (« Claude a terminé ») et demande dans le terminal : réaction de la pilule
    property var avant: ({})
    property string dernierFini: ""
    property string dernierFiniAgent: "claude"
    // Titre de la page : selon les agents suivis
    readonly property string titreAgent: sessionsVisibles.length && sessionsVisibles.every(s => agent(s) === agent(sessionsVisibles[0])) ? agent(sessionsVisibles[0]) : ""
    readonly property string titre: titreAgent !== "" ? ias[titreAgent].titre : Reglages.t("Agents IA", "AI Agents")
    readonly property var attend: sessions.find(s => attendReponse(s)) || null
    onSessionsChanged: {
        var n = {}
        for (let i = 0; i < sessions.length; i++) {
            let s = sessions[i], e = avant[s.id]
            n[s.id] = s.etat
            if (e && e !== s.etat && s.etat === "fini") { dernierFini = s.projet; dernierFiniAgent = agent(s); Etat.activite("claude-fini", 4500) }
        }
        avant = n
    }

    // L'île sur cette session (notification « Voir » d'un agent qui t'attend) : sa demande avec ses choix en haut de la
    // page, sinon sa carte en premier, avec le texte entier de sa question. L'état est relu (la notification est
    // souvent plus récente que la dernière lecture) : la page s'ouvre dès que la session y est
    function montrer(sid) {
        cible = sid
        allerCible = true
        oubli.restart()
        lecture.reload()
        versCible()
    }
    function versCible() {
        if (!allerCible || Etat.ecranOuvert === "" || Etat.vues.indexOf("claude") < 0) return
        allerCible = false
        Etat.aller("claude")
    }
    Timer { id: oubli; interval: 4000; onTriggered: a.allerCible = false }
    // Clic sur la pilule fermée pendant qu'un agent attend dans son terminal : sa question, directement ; faux sinon
    function ouvrirAttente(ecran) {
        if (!attend) return false
        var sid = attend.id
        Etat.basculer(ecran, false)
        cible = sid
        Etat.aller("claude")
        return true
    }
    Connections { target: Etat; function onEcranOuvertChanged() { if (Etat.ecranOuvert === "") { a.cible = ""; a.allerCible = false } } }

    function repondre(id, choix) {
        Quickshell.execDetached(["sh", "-c", "mkdir -p \"$1\" && printf %s \"$2\" > \"$1/$3\"", "sh", dossier + "/reponses", choix, id])
    }
    // Écrire à l'agent depuis l'île : tapé dans son terminal kitty, puis Entrée (nc-claude ecrire)
    function ecrire(id, texte) {
        if (texte.trim() !== "") Quickshell.execDetached([Quickshell.env("HOME") + "/.local/bin/nc-claude", "ecrire", id, texte])
    }
    // Son terminal, et dans kitty son onglet ; ramené s'il est réduit (nc-claude aller)
    function allerTerminal(pid, shell) {
        if (pid > 0) Quickshell.execDetached([Quickshell.env("HOME") + "/.local/bin/nc-claude", "aller", String(pid), String(shell || 0)])
    }
    function depuis(t) {
        var s = Math.max(0, Math.round(Etat.maintenant.getTime() / 1000 - (t || 0)))
        if (Reglages.en) return s < 60 ? "just now" : (s < 3600 ? Math.floor(s / 60) + " min ago" : Math.floor(s / 3600) + " h ago")
        return s < 60 ? "à l'instant" : (s < 3600 ? "il y a " + Math.floor(s / 60) + " min" : "il y a " + Math.floor(s / 3600) + " h")
    }
    function libelle(s) {
        if (Reglages.en)
            return ({ travail: "Working", demande: "Waiting for your answer", terminal: "Waiting in the terminal", attente: "Your turn",
                      fini: "Finished " + depuis(s.fin), pret: "Ready" })[s.etat] || s.etat
        return ({ travail: "Travaille", demande: "Attend ta réponse", terminal: "T'attend dans le terminal", attente: "À toi",
                  fini: "Terminé " + depuis(s.fin), pret: "Prêt" })[s.etat] || s.etat
    }
}

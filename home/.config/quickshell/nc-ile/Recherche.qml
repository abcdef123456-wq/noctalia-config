// Spotlight de l'île (Super + R) : la pilule s'étire en une longue capsule de recherche ; en tapant, quelques
// résultats compacts s'ajoutent dessous. ↑ ↓ pour choisir, Entrée pour lancer, Échap pour refermer.
// Appli déjà ouverte : Entrée en ouvre une nouvelle fenêtre, Ctrl + Entrée amène sur celle qui est ouverte (inversé avec
// SPOTLIGHT_ENTREE=aller dans nc-reglages).
// On trouve : fenêtres ouvertes, applications (les plus utilisées d'abord), actions (verrouiller, mode jeu…), pages
// de l'île (son, Wi-Fi…), calculs et conversions (« 1,5 h en min », « 100 € en $ »), fichiers du dossier personnel.
// Préfixes : « g » Google, « yt » YouTube, « w » Wikipédia, « > » commande dans le terminal, « ? » question à une IA
// (réponse dans le Spotlight ; sa commande proposée se lance avec Entrée, un choix proposé par JARVIS part comme question
// suivante : nc-demander), « ! » l'IA sur le texte
// sélectionné ou copié (résumer, traduire, corriger… ou une consigne libre : nc-ia texte), « @ » l'IA qui agit (un plan
// d'actions permises, chacune faite seulement avec Entrée : nc-ia agir, réglage IA_ACTIONS), « + » logiciel à installer
// (dépôts de la distribution, AUR avec paru ou yay, Flatpak : nc-logiciels ; Entrée ouvre un terminal qui l'installe).
// Sans préfixe, deux logiciels à installer dont le nom commence par la saisie s'ajoutent en bas (SPOTLIGHT_PAQUETS).
// Une saisie qui commence par un programme (htop, ping…) propose aussi de la lancer dans le terminal.
// Questions sur la config (« ? question », ou une phrase comme « comment changer le fond d'écran ») : réponses
// instantanées de l'index de nc-aide-config (réglages, raccourcis, commandes, documentation), sans IA ; « Demander à
// l'IA » reste en dernier. Réglage SPOTLIGHT_AIDE.
// Applications et fichiers : ~/.local/bin/nc-apps ; historique partagé avec le lanceur Noctalia (usage.json).
import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Widgets
import Quickshell.Services.UPower
import "AideConfig.js" as Aide

Item {
    id: r
    property bool actif: false
    readonly property int hauteurLigne: 46
    readonly property int hauteurVoulue: 56 + (zoneReponse.visible ? zoneReponse.height + 10 : 0)
                                         + (resultats.length > 0 ? 6 + resultats.length * hauteurLigne + 8 : 0)

    // Question à une IA (« ? … ») : réponse, et la commande qu'elle propose
    property var execs: ({})                 // programmes du PATH (saisie qui commence par une commande)
    property string nomIA: ""
    property string agentIA: "claude"        // logo (Etincelle) de l'IA qui répondrait à la prochaine question
    property string iaReponse: ""            // l'IA qui a vraiment répondu (repli compris) et son logo
    property string agentReponse: "claude"
    property bool iaCoupee: false            // aucune IA (réglage général, ou « IA du Spotlight : Aucune »)
    property bool modeTexte: false           // la réponse en cours est celle d'une action sur le texte (« ! »)
    property string texteSource: ""          // « ! » sur ce texte-là (une entrée du presse-papiers de l'île), sinon la sélection
    property string texteEnvoi: ""           // le texte écrit sur l'entrée standard de nc-ia au démarrage de la demande
    readonly property bool texteActif: !Reglages.iaCoupee && Reglages.val("IA_TEXTE", "oui") !== "non"
    readonly property var actionsTexte: [
        { id: "resumer", t: Reglages.t("Résumer", "Summarize"), k: "résumer résumé synthèse summarize summary tldr", g: "short_text" },
        { id: "traduire", t: Reglages.t("Traduire", "Translate"), k: "traduire traduction anglais français translate translation english french", g: "translate" },
        { id: "corriger", t: Reglages.t("Corriger l'orthographe", "Fix Spelling and Grammar"), k: "corriger orthographe grammaire fautes fix spelling grammar typos", g: "spellcheck" },
        { id: "reformuler", t: Reglages.t("Reformuler", "Rephrase"), k: "reformuler simplifier clarifier réécrire rephrase rewrite simplify", g: "edit_note" },
        { id: "expliquer", t: Reglages.t("Expliquer", "Explain"), k: "expliquer comprendre code erreur explain understand error", g: "lightbulb" },
        { id: "repondre", t: Reglages.t("Rédiger une réponse", "Draft a Reply"), k: "répondre réponse mail courriel message reply answer email", g: "reply" }
    ]
    property string questionPosee: ""
    property string reponse: ""
    property string commandeIA: ""
    // Choix proposés par JARVIS (ligne {"choices": […]} du flux, issue #7) : des lignes de résultat ; Entrée en envoie un
    // comme question suivante
    property var choixIA: []
    function repondreChoix(c) { champ.text = "? " + c; champ.cursorPosition = champ.text.length; demander(c) }
    // Connexion internet (NetworkManager, suivie sans rien lancer) : hors ligne, l'IA disparaît et revient toute seule.
    // Inconnue (pas de NetworkManager) : considérée comme là.
    readonly property bool enLigne: Connexion.enLigne
    onEnLigneChanged: if (actif) lireIA.running = true          // l'IA disponible change avec la connexion
    // Pas d'IA joignable parce que la connexion manque (une IA locale, Ollama, reste proposée : nomIA n'est pas « - »)
    readonly property bool horsLigne: nomIA === "-" && !enLigne
    readonly property var ligneHorsLigne: ({ titre: Reglages.t("Pas de connexion internet", "No internet connection"),
                                             sous: Reglages.t("L'IA revient dès que la connexion revient", "AI comes back as soon as the connection does"),
                                             glyphe: "wifi_off", garder: true, f: () => {} })
    // Pourquoi l'IA ne répond pas : coupée dans les réglages
    readonly property string motifCoupee: Reglages.t("L'IA est désactivée", "AI is turned off")
    readonly property bool reflechit: demandeur.running || agent.running
    // « @ » : le plan de l'IA (nc-ia agir --json), puis chaque action confirmée par Entrée (nc-ia executer)
    property var plan: null
    property bool modeAgent: false
    property string porteeAgent: ""      // « Organiser ce bureau » : le plan ne peut toucher que ce bureau
    readonly property bool agentPermis: !Reglages.iaCoupee && Reglages.val("IA_ACTIONS", "non") === "confirmer"
    function lancerAgent(demande) {
        if (demande === "" || agent.running) return
        questionPosee = q; reponse = ""; commandeIA = ""; modeTexte = false; modeAgent = true; plan = null
        iaReponse = nomIA; agentReponse = agentIA
        agent.command = [Etat.bin + "nc-ia", "agir", "--json"].concat(porteeAgent !== "" ? ["--bureau", porteeAgent] : []).concat([demande])
        agent.running = true
        chercher()
    }
    Timer { id: relireAgent; interval: 700; onTriggered: r.chercher() }      // après l'autorisation : le fichier relu
    function executerPlan(n) {
        if (!plan || executeur.running) return
        executeur.command = [Etat.bin + "nc-ia", "executer", plan.id].concat(n === null ? [] : [String(n)]).concat(["--json"])
        executeur.running = true
    }
    Process {
        id: agent
        stdout: StdioCollector { id: sortieAgent }
        stderr: StdioCollector { id: erreurAgent }
        onExited: code => {
            var d = null
            try { d = JSON.parse(sortieAgent.text) } catch (e) {}
            if (code === 0 && d) { r.plan = d; r.reponse = d.reponse || Reglages.t("Plan prêt.", "Plan ready."); r.iaReponse = d.ia || r.iaReponse; r.agentReponse = d.agent || r.agentReponse }
            else { r.plan = { actions: [], refus: [] }; r.reponse = erreurAgent.text.trim() || Reglages.t("L'IA n'a pas pu proposer de plan.", "The AI couldn't propose a plan.") }
            r.chercher()
        }
    }
    Process {
        id: executeur
        stdout: StdioCollector { id: sortieExec }
        stderr: StdioCollector { id: erreurExec }
        onExited: code => {
            try { r.plan = JSON.parse(sortieExec.text) } catch (e) { r.reponse = erreurExec.text.trim() || r.reponse }
            r.chercher()
        }
    }
    function demander(question) {
        if (question === "" || demandeur.running) return
        questionPosee = question; reponse = ""; commandeIA = ""; choixIA = []; modeTexte = false; modeAgent = false; iaReponse = nomIA; agentReponse = agentIA
        demandeur.command = [Etat.bin + "nc-demander", "--flux", question]
        demandeur.running = true
        chercher()
    }
    // « ! » : une action (ou une consigne libre) sur le texte sélectionné, sinon copié ; le résultat se copie avec Entrée
    function demanderTexte(action) {
        if (action === "" || demandeur.running) return
        questionPosee = q; reponse = ""; commandeIA = ""; choixIA = []; modeTexte = true; modeAgent = false; iaReponse = nomIA; agentReponse = agentIA
        demandeur.command = [Etat.bin + "nc-ia", "texte", action, "--flux"].concat(texteSource !== "" ? ["--stdin"] : [])
        texteEnvoi = texteSource
        demandeur.stdinEnabled = texteSource !== ""
        demandeur.running = true
        chercher()
    }
    // Dans le terminal, avec le PATH de l'utilisateur (l'île n'a que celui du système)
    function lancerCommande(c) { Quickshell.execDetached(["kitty", "--hold", "sh", "-c", "PATH=\"$HOME/.local/bin:$HOME/bin:$PATH\"; " + c]) }

    property var applis: []
    property var sessions: []                // dispositions enregistrées (nc-session) : « session NOM » ou leur nom
    property var fenetres: []
    property var usage: ({})
    property var fichiers: []
    property string calcul: ""
    property var resultats: []
    // Aide sur la config : l'index (nc-aide-config index, refait seulement si une source a changé), et la réponse affichée
    readonly property bool aideActive: Reglages.val("SPOTLIGHT_AIDE", "oui") !== "non"
    property var aide: null
    property string reponseAide: ""
    property string titreAide: ""
    FileView {
        id: indexAide
        path: (Quickshell.env("XDG_CACHE_HOME") || Quickshell.env("HOME") + "/.cache") + "/nc/aide-config.json"
        printErrors: false
        onLoaded: { try { r.aide = Aide.preparer(JSON.parse(text())) } catch (e) { r.aide = null } r.chercher() }
    }
    Process { id: majAide; command: [Etat.bin + "nc-aide-config", "index"]; onExited: indexAide.reload() }
    function reponsesAide(question, nombre) { return aideActive && aide ? Aide.chercher(aide, question, nombre) : [] }
    function itemAide(e, s) {
        var court = t => t.length > 80 ? t.slice(0, 78) + "…" : t
        if (e.type === "reglage")
            return { titre: e.titre, sous: Reglages.t("Réglage · ", "Setting · ") + e.section + (e.valeur ? " · " + e.valeur : ""), glyphe: "tune", s: s,
                     aide: Reglages.t("↵ ouvrir le réglage", "↵ open the setting"), f: () => r.ouvrirReglage(e.titre) }
        if (e.type === "raccourci")
            return { titre: e.titre, sous: Reglages.t("Raccourci · ", "Shortcut · ") + e.touches, glyphe: "keyboard", s: s,
                     aide: Reglages.t("↵ le changer", "↵ change it"), f: () => r.ouvrirReglage(e.titre) }
        if (e.type === "commande")
            return { titre: e.titre, sous: court(e.texte), glyphe: "terminal", s: s, aide: Reglages.t("↵ son aide", "↵ its help"),
                     f: () => r.lancerCommande("nc-aide " + e.titre) }
        return { titre: e.titre, sous: court(e.texte), glyphe: "menu_book", s: s, garder: true, aide: Reglages.t("↵ lire", "↵ read"),
                 f: () => { r.titreAide = e.titre; r.reponseAide = e.texte } }
    }
    // La fenêtre des réglages, cherchant ce réglage (ou ce raccourci)
    function ouvrirReglage(nom) { Quickshell.execDetached(["qs", "-c", "nc-ile", "ipc", "call", "ile", "reglagesChercher", nom]) }

    // Logiciels à installer (nc-logiciels) : la liste et le terme qu'elle concerne
    property var paquets: []
    property string paquetsPour: ""
    readonly property string modePaquets: Reglages.val("SPOTLIGHT_PAQUETS", "auto")
    // Nombre de lignes de résultats (nc-reglages : SPOTLIGHT_RESULTATS, 3 à 10)
    readonly property int nbResultats: Math.max(3, Math.min(10, parseInt(Reglages.val("SPOTLIGHT_RESULTATS", "6")) || 6))
    property int sel: 0
    readonly property string q: champ.text.trim()

    // Chargée à la demande : déjà active à sa création (une seule initialisation, une fois tout créé) ; rouverte avant
    // d'être déchargée : réinitialisée au changement de « actif »
    property bool cree: false
    onActifChanged: if (actif && cree) demarrer()
    Component.onCompleted: { cree = true; if (actif) demarrer() }
    function demarrer() {
        texteSource = Etat.texteIA || ""; if (texteSource !== "") Etat.texteIA = ""
        var agirTout = !!Etat.agirAuto; if (agirTout) Etat.agirAuto = false
        porteeAgent = agirTout ? Etat.agirPortee : ""; Etat.agirPortee = ""
        champ.text = Etat.saisie; Etat.saisie = ""; sel = 0; fichiers = []; calcul = ""; entreeEnAttente = false
        lireApplis.running = true
        lireFenetres.running = true
        lireSessions.running = true
        if (Object.keys(execs).length === 0) lireExecs.running = true
        lireIA.running = true
        if (aideActive && !majAide.running) majAide.running = true
        // Demandé par un raccourci (organiser les fenêtres) : le plan tout de suite si l'IA a le droit d'agir, sinon la
        // ligne qui propose de l'autoriser
        if (agirTout && agentPermis && champ.text.startsWith("@")) Qt.callLater(() => r.lancerAgent(champ.text.slice(1).trim()))
        fichierUsage.reload()
        champ.forceActiveFocus()
        prendreClavier.essais = 0
        prendreClavier.restart()
    }
    // Curseur directement dans la barre : l'île ne reçoit le clavier de Hyprland qu'un instant après s'être ouverte,
    // la demande est donc répétée jusqu'à ce que la barre l'ait vraiment (1 s au plus)
    Timer {
        id: prendreClavier
        property int essais: 0
        interval: 60; repeat: true
        onTriggered: {
            if (!r.actif || champ.activeFocus || ++essais > 16) { stop(); return }
            champ.forceActiveFocus()
        }
    }

    Connections { target: Etat; function onValiderRecherche() { if (r.actif) r.valider(r.sel, false) } }

    // ── Sources ──
    Process {
        id: lireExecs
        command: ["sh", "-c", "IFS=:; for d in $HOME/.local/bin:$HOME/bin:$PATH; do ls -1 \"$d\" 2>/dev/null; done | sort -u"]
        stdout: StdioCollector { onStreamFinished: { var e = {}; text.split("\n").forEach(x => { if (x) e[x] = true }); r.execs = e } }
    }
    Process {
        id: lireIA
        command: [Etat.bin + "nc-demander", "--ia", "--json"]
        stdout: StdioCollector {
            onStreamFinished: {
                // Ancien nc-demander (pendant une mise à jour) : le nom seul, en texte
                try { let d = JSON.parse(text); r.nomIA = d.nom || "-"; r.agentIA = d.agent || "claude"; r.iaCoupee = !!d.coupee }
                catch (e) { r.nomIA = text.trim() || "-" }
            }
        }
    }
    // Réponse affichée pendant qu'elle s'écrit ; à la fin, la ligne « $ … » devient la commande à lancer
    property string brut: ""
    Process {
        id: demandeur
        onStarted: if (demandeur.stdinEnabled) { write(r.texteEnvoi); r.texteEnvoi = ""; stdinEnabled = false }
        onRunningChanged: {
            if (running) { r.brut = "" }
            else if (r.modeTexte) {
                r.reponse = r.brut.trim() || Reglages.t("Pas de réponse.", "No answer.")
            }
            else {
                let l = r.brut.trim().split("\n")
                let c = l.length && l[l.length - 1].trim().startsWith("$ ") ? l.pop().trim().slice(2).trim() : ""
                r.reponse = l.join("\n").trim() || Reglages.t("Pas de réponse.", "No answer.")
                r.commandeIA = c
            }
            if (!running) lireIA.running = true      // la prochaine question peut aller à une autre IA (repli, choix)
            r.chercher()
        }
        stdout: SplitParser {
            onRead: ligne => {
                try {
                    let d = JSON.parse(ligne)
                    if (d.ia) { r.iaReponse = d.ia; r.agentReponse = d.agent || r.agentReponse }    // repli compris
                    if (Array.isArray(d.choices))          // 5 au plus, de 80 caractères au plus, sans doublon
                        r.choixIA = d.choices.filter(x => typeof x === "string" && x.trim() !== "").map(x => x.trim().slice(0, 80))
                                             .filter((x, i, l) => l.indexOf(x) === i).slice(0, 5)
                    r.brut += d.t || ""
                } catch (e) { return }
                r.reponse = r.brut
            }
        }
    }
    Process {
        id: lireApplis
        command: [Etat.bin + "nc-apps", "list"]
        stdout: StdioCollector {
            onStreamFinished: {
                try { r.applis = JSON.parse(text) } catch (e) {}
                r.chercher()
                // Entrée tapée avant que les applis soient chargées : validée maintenant, sur la liste complète
                if (r.entreeEnAttente) { r.entreeEnAttente = false; r.valider(r.sel, false) }
            }
        }
    }
    Process {
        id: lireSessions
        command: [Etat.bin + "nc-session", "liste", "--json"]
        stdout: StdioCollector { onStreamFinished: { try { r.sessions = JSON.parse(text) } catch (e) { r.sessions = [] } r.chercher() } }
    }
    function itemSession(x, s) {
        let nom = x.nom
        return { titre: Reglages.t("Session « ", "Session “") + nom + Reglages.t(" »", "”"), glyphe: "view_quilt", s: s,
                 sous: x.fenetres + Reglages.t(" fenêtre(s) · ", " window(s) · ") + (x.applis || []).join(", "),
                 aide: Reglages.t("↵ l'ouvrir", "↵ open it"), f: () => Quickshell.execDetached([Etat.bin + "nc-session", "ouvrir", nom]) }
    }
    Process {
        id: lireFenetres
        command: ["hyprctl", "clients", "-j"]
        stdout: StdioCollector {
            onStreamFinished: {
                try { r.fenetres = JSON.parse(text).filter(c => c.mapped && c.title !== "" && c.workspace && c.workspace.id > 0) } catch (e) {}
                r.chercher()
            }
        }
    }
    FileView {
        id: fichierUsage
        path: Quickshell.env("HOME") + "/.local/state/noctalia/plugins/data/nc/launcher/usage.json"
        printErrors: false
        onLoaded: { try { r.usage = JSON.parse(text()) } catch (e) { r.usage = ({}) } }
    }
    Process {
        id: lireFichiers
        property string pour: ""
        stdout: StdioCollector {
            onStreamFinished: {
                if (lireFichiers.pour !== r.q) return
                try { r.fichiers = JSON.parse(text).slice(0, 3) } catch (e) { r.fichiers = [] }
                r.chercher()
            }
        }
    }
    Process {
        id: calculer
        property string pour: ""
        stdout: StdioCollector {
            onStreamFinished: {
                if (calculer.pour !== r.q) return
                var t = text.trim().split("\n").pop()
                // Rien d'utile (texte non compris, même chose que la saisie) : pas de ligne de calcul
                r.calcul = t === "" || t === calculer.pour || /[A-Za-z]·|rem\(|^\(/.test(t) ? "" : t
                r.chercher()
            }
        }
    }
    // Logiciels à installer : « + terme » cherche partout (dépôts, AUR, Flatpak) ; sans préfixe, les dépôts seulement
    function termePaquets() {
        if (modePaquets === "non") return ""
        if (q.startsWith("+")) return q.slice(1).trim()
        return modePaquets === "auto" && q.length >= 3 && !/^(>|\?|!|@|g |yt |w |\/|sessions? )/i.test(q) ? q : ""
    }
    Process {
        id: chercheurPaquets
        property string pour: ""
        stdout: StdioCollector {
            onStreamFinished: {
                var p = []
                try { p = JSON.parse(text) } catch (e) {}
                r.paquets = Array.isArray(p) ? p : []
                r.paquetsPour = chercheurPaquets.pour
                r.chercher()
            }
        }
        // La saisie a changé pendant la recherche : la suivante part tout de suite
        onRunningChanged: if (!running && r.termePaquets() !== "" && r.termePaquets() !== pour) attentePaquets.restart()
    }
    Timer {
        id: attentePaquets
        interval: 320
        onTriggered: {
            var t = r.termePaquets()
            if (t.length < 2 || chercheurPaquets.running || t === r.paquetsPour) return
            chercheurPaquets.pour = t
            chercheurPaquets.command = [Etat.bin + "nc-logiciels", "chercher", t].concat(r.q.startsWith("+") ? ["--max", "12"] : ["--rapide", "--max", "6"])
            chercheurPaquets.running = true
        }
    }
    function installer(p) {
        Quickshell.execDetached([Etat.bin + "nc-logiciels", "installer", p.source, p.nom].concat(p.source === "flatpak" ? [p.depot] : []))
    }
    // Icône d'un logiciel à installer : celle du catalogue de la distribution ou de Flatpak, sinon du thème d'icônes ;
    // aucune en Économie (réglage ECO_IMAGES)
    function iconePaquet(p) {
        if (Reglages.imagesLegeres) return ""
        if (p.icone) return "file://" + p.icone
        var n = p.noms_icone || []
        for (let i = 0; i < n.length; i++) { let c = Quickshell.iconPath(n[i], true); if (c) return c }
        return ""
    }
    function itemPaquet(p, s) {
        var origine = p.source === "aur" ? "AUR" : p.source === "flatpak" ? "Flatpak" : Reglages.t("Dépôt ", "Repo ") + p.depot
        var desc = (p.description || "").length > 70 ? p.description.slice(0, 68) + "…" : (p.description || "")
        return { titre: p.titre || p.nom, sous: origine + (desc ? " · " + desc : ""), glyphe: p.installe ? "check_circle" : "download", s: s,
                 icone: iconePaquet(p),
                 aide: p.installe ? Reglages.t("déjà installé", "already installed") : Reglages.t("↵ installer", "↵ install"),
                 garder: p.installe, f: p.installe ? (() => {}) : (() => r.installer(p)) }
    }

    // Fichiers et calcul : lancés un instant après la dernière touche
    Timer {
        id: attente
        interval: 120
        onTriggered: {
            var q = r.q
            if (q.length >= 3 && !/^(>|!|@|g |yt |w |sessions? )/i.test(q) && Reglages.val("SPOTLIGHT_FICHIERS", "oui") !== "non") {
                lireFichiers.pour = q
                lireFichiers.command = [Etat.bin + "nc-apps", "files", q]
                lireFichiers.running = true
            }
            if (Reglages.val("SPOTLIGHT_CALCULS", "oui") !== "non" && /\d/.test(q) && /[-+*/^%()√]|\s(en|to|in)\s|sqrt|sin|cos|log/.test(q)) {
                calculer.pour = q
                calculer.command = ["qalc", "-t", "-set", "mix 0", q.replace(/\s+en\s+/g, " to ")]
                calculer.running = true
            }
        }
    }

    // ── Actions et pages ──
    readonly property var actions: [
        { t: Reglages.t("Verrouiller", "Lock"), k: "verrouiller lock écran screen", g: "lock", f: () => Etat.faire(["noctalia", "msg", "session", "lock"]) },
        { t: Reglages.t("Mettre en veille", "Sleep"), k: "veille suspend dormir sleep", g: "bedtime", f: () => Etat.faire(["systemctl", "suspend"]) },
        { t: Reglages.t("Éteindre, redémarrer…", "Shut Down, Restart…"), k: "éteindre redémarrer arrêt shutdown reboot quitter session shut power off restart log out logout", g: "power_settings_new", f: () => Etat.faire(["noctalia", "msg", "panel-toggle", "session"]) },
        { t: Reglages.t("Mode jeu", "Game Mode"), k: "mode jeu game gaming", g: "sports_esports", f: () => Etat.faire(["hyprctl", "eval", "nc.mode_jeu()"]) },
        { t: Reglages.t("Économie d'énergie", "Power Saver"), k: "économie batterie eco énergie power saver low battery energy", g: "battery_saver", f: () => Etat.choisirProfil(PowerProfile.PowerSaver) },
        { t: Reglages.t("Équilibré", "Balanced"), k: "équilibré énergie normal balanced power energy", g: "battery_full", f: () => Etat.choisirProfil(PowerProfile.Balanced) },
        { t: "Performance", k: "performance énergie puissance nvidia power energy", g: "bolt", f: () => Etat.choisirProfil(PowerProfile.Performance) },
        { t: Reglages.t("Activer ou couper le Wi-Fi", "Turn Wi-Fi On or Off"), k: "wifi wi-fi réseau internet network", g: "wifi", f: () => Etat.faire(["noctalia", "msg", "wifi-toggle"]) },
        { t: Reglages.t("Activer ou couper le Bluetooth", "Turn Bluetooth On or Off"), k: "bluetooth", g: "bluetooth", f: () => Etat.faire(["noctalia", "msg", "bluetooth-toggle"]) },
        { t: Reglages.t("Concentration", "Do Not Disturb"), k: "concentration ne pas déranger dnd notifications focus do not disturb", g: "dark_mode", f: () => Notifs.basculerConcentration() },
        { t: Reglages.t("Nuit (tons chauds)", "Night Light (Warm Tones)"), k: "nuit night lumière bleue blue light warm shift", g: "wb_twilight", f: () => { Etat.nuit = !Etat.nuit; Etat.faire(["noctalia", "msg", "nightlight-force-toggle"]) } },
        { t: Reglages.t("Thème clair ou sombre", "Light or Dark Theme"), k: "thème clair sombre dark light theme mode appearance", g: "contrast", f: () => Etat.faire(["noctalia", "msg", "theme-mode-toggle"]) },
        { t: Reglages.t("Rester éveillé", "Stay Awake"), k: "rester éveillé café caféine veille stay awake caffeine coffee", g: "coffee", f: () => Etat.basculerCafe() },
        { t: Reglages.t("Capture d'une zone", "Capture an Area"), k: "capture écran screenshot screen area region", g: "screenshot_region", f: () => Quickshell.execDetached(["sh", "-c", "sleep 0.4; ~/.local/bin/nc-capture zone"]) },
        { t: "Pomodoro", k: "pomodoro minuteur travail concentration pause tomate timer work focus break tomato", g: "psychology", f: () => { Etat.lancerPomodoro(); Etat.basculer(Etat.ecranOuvert, false) } },
        { t: Reglages.t("Copier le texte de l'écran", "Copy Text from Screen"), k: "texte ocr lire image copier capture extraire text copy read screen extract", g: "text_select_start", f: () => Quickshell.execDetached(["sh", "-c", "sleep 0.4; ~/.local/bin/nc-capture texte"]) },
        { t: Reglages.t("Presse-papiers", "Clipboard"), k: "presse-papiers clipboard copier coller copy paste history", g: "content_paste", f: () => Quickshell.execDetached(["noctalia", "msg", "panel-toggle", "launcher", "/clipboard"]) },
        { t: Reglages.t("Fond d'écran suivant", "Next Wallpaper"), k: "fond écran wallpaper suivant next background", g: "wallpaper", f: () => Etat.faire(["noctalia", "msg", "wallpaper-next"]) },
        { t: Reglages.t("Raccourcis clavier", "Keyboard Shortcuts"), k: "raccourcis clavier touches aide keyboard shortcuts keys help", g: "keyboard", f: () => Quickshell.execDetached([Etat.bin + "nc-shell-msg", "keys"]) },
        // IA (cachées quand elle est coupée)
        { t: Reglages.t("IA sur le texte copié", "AI on Copied Text"), k: "ia ai résumer traduire corriger reformuler texte summarize translate fix rephrase text", g: "auto_awesome",
          ia: "IA_TEXTE", garder: true, f: () => { champ.text = "! "; champ.cursorPosition = 2 } },
        { t: Reglages.t("Expliquer une zone de l'écran", "Explain an Area of the Screen"), k: "ia ai capture écran expliquer erreur image screenshot explain error", g: "center_focus_strong",
          ia: "IA_CAPTURE", f: () => Quickshell.execDetached(["sh", "-c", "sleep 0.4; exec \"$HOME/.local/bin/nc-ia\" capture"]) },
        { t: Reglages.t("Tester les IA", "Test the AIs"), k: "ia ai tester essai clé api claude openai gemini ollama test key", g: "science", ia: "IA_MODE",
          f: () => Quickshell.execDetached([Etat.bin + "nc-ia", "fenetre-test"]) },
        { t: Reglages.t("Demander à l'IA d'agir", "Ask the AI to Act"), k: "ia ai agir gérer service redémarrer réparer act manage restart fix", g: "smart_toy", ia: "IA_ACTIONS", garder: true,
          f: () => { champ.text = "@ "; champ.cursorPosition = 2 } },
        { t: Reglages.t("Couper l'IA partout", "Turn AI Off Everywhere"), k: "ia ai couper désactiver aucune arrêter intelligence artificielle turn off disable none", g: "block", ia: "IA_MODE",
          f: () => Quickshell.execDetached([Etat.bin + "nc-reglages", "set", "IA_MODE", "non"]) },
        { t: Reglages.t("Rallumer l'IA", "Turn AI Back On"), k: "ia ai rallumer activer intelligence artificielle turn on enable", g: "auto_awesome", siCoupee: true,
          f: () => Quickshell.execDetached([Etat.bin + "nc-reglages", "set", "IA_MODE", "auto"]) }
    ]
    readonly property var pagesIle: [
        { t: "JARVIS", k: "jarvis assistant chat ia distant conversation question", g: "chat", p: "assistant" },
        { t: Reglages.t("Son", "Sound"), k: "son volume audio sortie micro haut-parleurs casque sound output speakers headphones microphone", g: "volume_up", p: "son" },
        { t: "Wi-Fi", k: "wifi wi-fi réseau internet réseaux network networks", g: "wifi", p: "reseau" },
        { t: "Bluetooth", k: "bluetooth appareils casque souris devices headphones mouse", g: "bluetooth", p: "bluetooth" },
        { t: "Notifications", k: "notifications messages", g: "notifications", p: "notifications" },
        { t: Reglages.t("Système", "System"), k: "système processeur mémoire batterie température disque énergie system cpu processor memory ram battery temperature disk power", g: "memory", p: "systeme" },
        { t: Reglages.t("Calendrier", "Calendar"), k: "calendrier date agenda calendar", g: "calendar_month", p: "calendrier" },
        { t: Reglages.t("Minuteur", "Timer"), k: "minuteur timer chrono stopwatch countdown", g: "timer", p: "minuteur" },
        { t: Reglages.t("Centre de contrôle", "Control Center"), k: "centre contrôle réglages luminosité control center settings brightness", g: "toggle_on", p: "centre" }
    ]

    // ── Recherche ──
    function sansAccents(s) { s = (s || "").toLowerCase(); try { return s.normalize("NFD").replace(/[̀-ͯ]/g, "") } catch (e) { return s } }
    // Score d'un nom : début 100, début d'un mot 80, dedans 55 (seulement si large), sinon 0.
    // Mots : séparés par espace, tiret, point, tiret bas (« org.gnome.Nautilus », « Wi-Fi »).
    function score(q, texte, large) {
        var t = sansAccents(texte)
        if (t === "" || q === "") return 0
        if (t.startsWith(q)) return 100
        var mots = t.split(/[\s._\-/]+/)
        for (let i = 0; i < mots.length; i++) if (mots[i].startsWith(q)) return 80
        return large && t.indexOf(q) >= 0 ? 55 : 0
    }
    // Icône d'un fichier selon son extension (icônes du thème NC)
    function iconeFichier(nom, dossier) {
        if (dossier) return "folder"
        var e = (nom.split(".").pop() || "").toLowerCase()
        var t = { mp4: "video-x-generic", mkv: "video-x-generic", webm: "video-x-generic", mov: "video-x-generic", avi: "video-x-generic",
                  mp3: "audio-x-generic", flac: "audio-x-generic", ogg: "audio-x-generic", wav: "audio-x-generic", m4a: "audio-x-generic",
                  png: "image-x-generic", jpg: "image-x-generic", jpeg: "image-x-generic", webp: "image-x-generic", gif: "image-x-generic", svg: "image-x-generic",
                  pdf: "application-pdf", zip: "package-x-generic", tar: "package-x-generic", gz: "package-x-generic", xz: "package-x-generic", "7z": "package-x-generic", rar: "package-x-generic",
                  py: "text-x-script", js: "text-x-script", ts: "text-x-script", sh: "text-x-script", c: "text-x-script", cpp: "text-x-script", h: "text-x-script",
                  rs: "text-x-script", go: "text-x-script", lua: "text-x-script", qml: "text-x-script", java: "text-x-script", css: "text-x-script",
                  json: "application-json", jsonl: "application-json", toml: "application-json", yaml: "application-json", yml: "application-json", xml: "application-json",
                  md: "text-markdown", html: "text-html", htm: "text-html", odt: "x-office-document", docx: "x-office-document", doc: "x-office-document",
                  ods: "x-office-spreadsheet", xlsx: "x-office-spreadsheet", csv: "x-office-spreadsheet", odp: "x-office-presentation", pptx: "x-office-presentation",
                  ttf: "font-x-generic", otf: "font-x-generic", iso: "application-x-cd-image" }[e]
        return t || "text-x-generic"
    }
    // Fenêtre déjà ouverte d'une appli (la plus récemment utilisée), sinon null
    function fenetreDe(ap) {
        var noms = [ap.wmclass, ap.id, ap.exe === "env" ? "" : ap.exe].filter(x => x).map(x => x.toLowerCase())
        var meilleure = null
        for (let i = 0; i < fenetres.length; i++) {
            let c = (fenetres[i].class || "").toLowerCase()
            if (noms.indexOf(c) >= 0 && (!meilleure || fenetres[i].focusHistoryID < meilleure.focusHistoryID)) meilleure = fenetres[i]
        }
        return meilleure
    }
    // Aller sur une fenêtre ; réduite (Super + M), elle revient d'abord sur le bureau affiché (nc-fenetre)
    function allerA(adresse) { Etat.faire([Etat.bin + "nc-fenetre", "aller", adresse]) }
    function bureauNom(f) { return f.workspace.name === "special:reduites" ? Reglages.t("Réduite", "Minimized") : Reglages.t("Ouverte · bureau ", "Open · Desktop ") + f.workspace.name }
    function poidsUsage(id) {
        var u = usage[id]
        if (!u) return 1
        var h = (Date.now() / 1000 - (u.t || 0)) / 3600
        return 1 + Math.min(1.2, (u.n || 0) / 15) * (h < 24 ? 1.4 : (h < 168 ? 1.1 : 0.8))
    }

    onQChanged: { sel = 0; fichiers = []; calcul = ""; reponseAide = ""; attente.restart(); attentePaquets.restart(); chercher() }

    function chercher() {
        var q = r.q, qa = sansAccents(q), out = []
        if (q === "") { resultats = []; return }

        // Préfixes : web et commande
        // « g … » : le moteur choisi (SPOTLIGHT_MOTEUR)
        var moteur = ({ google: ["Google", "https://www.google.com/search?q="], duckduckgo: ["DuckDuckGo", "https://duckduckgo.com/?q="],
                        qwant: ["Qwant", "https://www.qwant.com/?q="], startpage: ["Startpage", "https://www.startpage.com/do/search?q="],
                        brave: ["Brave Search", "https://search.brave.com/search?q="], ecosia: ["Ecosia", "https://www.ecosia.org/search?q="] })[Reglages.val("SPOTLIGHT_MOTEUR", "google")]
                     || ["Google", "https://www.google.com/search?q="]
        var web = [["g ", moteur[0], moteur[1]], ["yt ", "YouTube", "https://www.youtube.com/results?search_query="],
                   ["w ", Reglages.t("Wikipédia", "Wikipedia"), Reglages.t("https://fr.wikipedia.org/w/index.php?search=", "https://en.wikipedia.org/w/index.php?search=")]]
        for (let w = 0; w < web.length; w++) {
            if (q.startsWith(web[w][0]) && q.length > web[w][0].length) {
                let terme = q.slice(web[w][0].length)
                let url = web[w][2] + encodeURIComponent(terme)
                resultats = [{ titre: terme, sous: Reglages.t("Rechercher sur ", "Search ") + web[w][1], glyphe: "travel_explore", f: () => Qt.openUrlExternally(url) }]
                return
            }
        }
        if (q.startsWith("?")) {
            let question = q.slice(1).trim()
            // D'abord les réponses de la config (instantanées), puis l'IA en dernier
            let deLaConfig = question.length >= 2 ? reponsesAide(question, nbResultats - 1).map(e => itemAide(e, 0)) : []
            if (r.reponse !== "" && question === r.questionPosee) {
                let cmdIA = r.commandeIA
                let choix = r.choixIA.map(c => ({ titre: c, sous: Reglages.t("Répondre à ", "Reply to ") + r.iaReponse, glyphe: "chevron_right",
                                                   garder: true, f: () => r.repondreChoix(c) }))
                resultats = (cmdIA === "" ? [] : [{ titre: cmdIA, sous: Reglages.t("Lancer dans le terminal", "Run in Terminal"), glyphe: "terminal", f: () => r.lancerCommande(cmdIA) }])
                            .concat(choix, deLaConfig)
            } else {
                let ia = r.reflechit ? []
                          : iaCoupee ? [{ titre: r.motifCoupee, sous: Reglages.t("Réglages · Intelligence artificielle", "Settings · Artificial intelligence"),
                                          glyphe: "block", f: () => r.ouvrirReglage(Reglages.t("IA du bureau", "Desktop AI")) }]
                          : horsLigne ? [ligneHorsLigne]
                          : nomIA === "-" ? [{ titre: Reglages.t("Aucune IA disponible pour répondre", "No AI available to answer"),
                                               sous: Reglages.t("Ajouter une clé d'API, Claude Code, Ollama…", "Add an API key, Claude Code, Ollama…"),
                                               glyphe: "key", f: () => Quickshell.execDetached([Etat.bin + "nc-ia", "configurer"]) }]
                          : [{ titre: question || Reglages.t("Pose ta question", "Ask your question"),
                               sous: r.reflechit ? (nomIA + Reglages.t(" réfléchit…", " is thinking…")) : Reglages.t("Demander à ", "Ask ") + (nomIA || Reglages.t("l'IA", "the AI")),
                               glyphe: "auto_awesome", garder: true, f: () => r.demander(question) }]
                resultats = deLaConfig.concat(ia)
            }
            if (sel >= resultats.length) sel = Math.max(0, resultats.length - 1)
            return
        }
        if (q.startsWith("!")) {
            let consigneT = q.slice(1).trim()
            if (!texteActif) {
                resultats = [{ titre: Reglages.iaCoupee ? r.motifCoupee : Reglages.t("L'IA sur le texte est désactivée", "AI on text is turned off"),
                               sous: Reglages.t("Réglages · Intelligence artificielle", "Settings · Artificial intelligence"), glyphe: "block",
                               f: () => r.ouvrirReglage(Reglages.iaCoupee ? Reglages.t("IA du bureau", "Desktop AI") : Reglages.t("IA sur le texte sélectionné", "AI on the selected text")) }]
                return
            }
            // demandeur.running plutôt que reflechit : à la fin de la réponse, sa liaison n'est pas encore à jour
            if (r.modeTexte && q === r.questionPosee && (demandeur.running || r.reponse !== "")) {
                let resultat = r.reponse
                resultats = demandeur.running ? [] : [{ titre: Reglages.t("Copier le résultat", "Copy the Result"), sous: r.iaReponse, glyphe: "content_copy",
                                                  f: () => Quickshell.execDetached(["wl-copy", "--", resultat]) }]
                sel = 0
                return
            }
            if (horsLigne) { resultats = [ligneHorsLigne]; return }
            let qt = sansAccents(consigneT)
            let lignesT = actionsTexte.filter(a => qt === "" || score(qt, a.t, true) > 0 || score(qt, a.k, false) > 0).map(a => {
                let id = a.id
                return { titre: a.t, sous: (texteSource !== "" ? Reglages.t("Texte du presse-papiers · ", "Clipboard text · ") : Reglages.t("Texte sélectionné ou copié · ", "Selected or copied text · "))
                                           + (nomIA === "-" ? Reglages.t("aucune IA", "no AI") : nomIA),
                         glyphe: a.g, garder: true, f: () => r.demanderTexte(id) }
            })
            // Une consigne qui n'est pas une action connue : appliquée telle quelle (« ! en liste à puces »)
            if (consigneT.length >= 3 && !lignesT.some(l => sansAccents(l.titre) === qt))
                lignesT.push({ titre: "« " + consigneT + " »", sous: Reglages.t("Consigne libre sur le texte sélectionné ou copié", "Free instruction on the selected or copied text"),
                               glyphe: "auto_awesome", garder: true, f: () => r.demanderTexte(consigneT) })
            resultats = lignesT
            if (sel >= resultats.length) sel = Math.max(0, resultats.length - 1)
            return
        }
        if (q.startsWith("@")) {
            let demandeA = q.slice(1).trim()
            if (Reglages.iaCoupee) {
                resultats = [{ titre: r.motifCoupee, sous: Reglages.t("Réglages · Intelligence artificielle", "Settings · Artificial intelligence"),
                               glyphe: "block", f: () => r.ouvrirReglage(Reglages.t("IA du bureau", "Desktop AI")) }]
                return
            }
            // Pas encore permis : l'autoriser ici même (rien ne se fera pour autant sans ta confirmation, action par action)
            if (!agentPermis) {
                resultats = [{ titre: Reglages.t("Autoriser l'IA à proposer des actions", "Allow the AI to propose actions"),
                               sous: Reglages.t("Tu confirmeras chacune · ↵", "You'll confirm each one · ↵"), glyphe: "lock_open", garder: true,
                               f: () => { Quickshell.execDetached([Etat.bin + "nc-reglages", "set", "IA_ACTIONS", "confirmer"]); relireAgent.restart() } }]
                return
            }
            if (horsLigne) { resultats = [ligneHorsLigne]; return }
            if (r.modeAgent && q === r.questionPosee && (agent.running || r.plan)) {
                if (agent.running || !r.plan) { resultats = []; return }
                let lignesA = [], restantes = r.plan.actions.filter(a => !a.fait)
                if (restantes.length > 1)
                    lignesA.push({ titre: Reglages.t("Tout faire", "Do Everything"), sous: restantes.length + Reglages.t(" actions", " actions"), glyphe: "done_all",
                                   garder: true, aide: Reglages.t("↵ confirmer", "↵ confirm"), f: () => r.executerPlan(null) })
                r.plan.actions.forEach(a => {
                    let n = a.n
                    lignesA.push(a.fait ? { titre: (a.ok ? "✓ " : "✗ ") + a.libelle, sous: a.ok ? Reglages.t("Fait", "Done") + (a.note ? " · " + a.note : "") : (a.resultat || "").slice(0, 60), glyphe: a.ok ? "check_circle" : "error", garder: true, f: () => {} }
                                        : { titre: a.libelle, sous: a.danger ? Reglages.t("⚠ à confirmer", "⚠ to confirm") : Reglages.t("À confirmer", "To confirm"), glyphe: "play_arrow",
                                            garder: true, aide: Reglages.t("↵ le faire", "↵ do it"), f: () => r.executerPlan(n) })
                })
                ;(r.plan.refus || []).forEach(t => lignesA.push({ titre: t, sous: Reglages.t("Refusé", "Refused"), glyphe: "block", garder: true, f: () => {} }))
                resultats = lignesA
                if (sel >= resultats.length) sel = Math.max(0, resultats.length - 1)
                return
            }
            resultats = [{ titre: demandeA || Reglages.t("Dis ce que l'IA doit faire", "Say what the AI should do"),
                           sous: Reglages.t("Elle propose, tu confirmes · ", "It proposes, you confirm · ") + (nomIA === "-" ? Reglages.t("aucune IA", "no AI") : nomIA),
                           glyphe: "smart_toy", garder: true, f: () => r.lancerAgent(demandeA) }]
            return
        }
        // « session NOM » : ouvrir une disposition enregistrée, ou enregistrer celle d'aujourd'hui sous ce nom
        if (/^\s*sessions?\s/i.test(champ.text)) {          // le texte brut : « session » seul reste la recherche (déconnexion…)
            let nomS = q.replace(/^sessions?\s*/i, "").trim(), qs = sansAccents(nomS)
            let lignesS = sessions.filter(x => qs === "" || sansAccents(x.nom).indexOf(qs) >= 0).map(x => itemSession(x, 0))
            if (nomS !== "" && /^[\w][\w .\-]{0,39}$/.test(nomS) && !sessions.some(x => x.nom === nomS)) {
                let n = nomS
                lignesS.push({ titre: Reglages.t("Enregistrer la disposition actuelle sous « ", "Save the current layout as “") + n + Reglages.t(" »", "”"),
                               sous: Reglages.t("Applis ouvertes, leurs bureaux et leur place", "Open apps, their desktops and places"), glyphe: "save",
                               f: () => Quickshell.execDetached([Etat.bin + "nc-session", "enregistrer", n]) })
            }
            if (!lignesS.length) lignesS = [{ titre: Reglages.t("Tape un nom pour enregistrer la disposition actuelle", "Type a name to save the current layout"),
                                             sous: "Sessions", glyphe: "view_quilt", garder: true, f: () => {} }]
            resultats = lignesS
            if (sel >= resultats.length) sel = Math.max(0, resultats.length - 1)
            return
        }
        if (q.startsWith("+") && modePaquets !== "non") {
            let tp = q.slice(1).trim()
            if (tp.length < 2) resultats = [{ titre: Reglages.t("Tape le nom d'un logiciel à installer", "Type the name of an app to install"),
                                              sous: Reglages.t("Dépôts, AUR et Flatpak", "Repos, AUR and Flatpak"), glyphe: "download", garder: true, f: () => {} }]
            else if (paquetsPour !== tp) resultats = [{ titre: tp, sous: Reglages.t("Recherche dans les logiciels…", "Searching apps…"), glyphe: "hourglass_top", garder: true, f: () => {} }]
            else if (!paquets.length) resultats = [{ titre: Reglages.t("Aucun logiciel ne correspond", "No app matches"), sous: tp, glyphe: "search_off", garder: true, f: () => {} }]
            else resultats = paquets.slice(0, nbResultats + 1).map(p => itemPaquet(p, p.score))
            if (sel >= resultats.length) sel = Math.max(0, resultats.length - 1)
            return
        }
        if (q.startsWith(">")) {
            let c = q.slice(1).trim()
            resultats = c === "" ? [] : [{ titre: c, sous: Reglages.t("Commande dans le terminal", "Command in Terminal"), glyphe: "terminal",
                                          f: () => r.lancerCommande(c) }]
            return
        }

        // Calcul en tête
        if (calcul !== "") {
            let res = calcul
            out.push({ titre: "= " + res, sous: Reglages.t("Calcul · Entrée pour copier", "Calculation · Enter to copy"), glyphe: "calculate", s: 1000,
                       f: () => Quickshell.execDetached(["wl-copy", res.replace(/^≈?\s*/, "")]) })
        }
        // Applications : déjà ouverte → Entrée en ouvre une nouvelle (Ctrl + Entrée : y aller), sinon Entrée la lance
        var prises = {}
        for (let a = 0; a < applis.length; a++) {
            let ap = applis[a]
            let sa = Math.max(score(qa, ap.name, true), score(qa, ap.generic, false) - 20, score(qa, ap.id, false) - 15, score(qa, ap.keywords, false) - 30)
            if (sa > 0) {
                let id = ap.id, fen = fenetreDe(ap)
                let item = { titre: ap.name, icone: Quickshell.iconPath(ap.icon, true), glyphe: "apps", s: sa * poidsUsage(id) + (fen ? 15 : 0) }
                if (fen) {
                    let adresse = fen.address
                    prises[adresse] = true
                    item.sous = bureauNom(fen)
                    if (Reglages.val("SPOTLIGHT_ENTREE", "nouvelle") === "aller") {
                        item.aide = Reglages.t("↵ y aller · Ctrl ↵ nouvelle", "↵ go to it · Ctrl ↵ new")
                        item.f = () => r.allerA(adresse)
                        item.nouveau = () => r.lancer(id)
                    } else {
                        item.aide = Reglages.t("↵ nouvelle · Ctrl ↵ y aller", "↵ new · Ctrl ↵ go to it")
                        item.f = () => r.lancer(id)
                        item.nouveau = () => r.allerA(adresse)
                    }
                } else {
                    item.sous = ap.generic || "Application"
                    item.f = () => r.lancer(id)
                }
                out.push(item)
            }
        }
        // Fenêtres ouvertes (celles qui ne sont pas déjà proposées par leur appli)
        for (let i = 0; i < (Reglages.val("SPOTLIGHT_FENETRES", "oui") !== "non" ? fenetres.length : 0); i++) {
            let fe = fenetres[i]
            if (prises[fe.address]) continue
            let sf = Math.max(score(qa, fe.class, false), score(qa, fe.initialTitle, false), score(qa, fe.title, false) - 25)
            if (sf > 0) {
                let adr = fe.address
                out.push({ titre: fe.title, sous: fe.workspace.name === "special:reduites" ? Reglages.t("Fenêtre réduite · Entrée pour la ramener", "Minimized window · Enter to bring it back")
                                                                  : Reglages.t("Fenêtre ouverte · bureau ", "Open window · Desktop ") + fe.workspace.name,
                           icone: Quickshell.iconPath(fe.class, true) || Quickshell.iconPath(fe.class.toLowerCase(), true),
                           glyphe: "select_window", s: sf + 30, f: () => r.allerA(adr) })
            }
        }
        // Pages de l'île et actions
        for (let p = 0; p < pagesIle.length; p++) {
            let pg = pagesIle[p], sp = Math.max(score(qa, pg.t, true), score(qa, pg.k, false) - 15)
            if (!Reglages.pageActive(pg.p)) continue
            if (sp > 0) { let nom = pg.p; out.push({ titre: pg.t, sous: Reglages.t("Dans l'île", "In the island"), glyphe: pg.g, s: sp - 5, page: nom }) }
        }
        // Sessions enregistrées : par leur nom (« dev » trouve la session « Dev »)
        for (let ss = 0; ss < sessions.length; ss++) {
            let sc2 = Math.max(score(qa, sessions[ss].nom, true), score(qa, "session " + sessions[ss].nom, false) - 10)
            if (sc2 > 0) out.push(itemSession(sessions[ss], sc2 - 4))
        }
        for (let k = 0; k < actions.length; k++) {
            let ac = actions[k], sc = Math.max(score(qa, ac.t, true), score(qa, ac.k, false) - 15)
            if (ac.ia && (Reglages.iaCoupee || (ac.ia !== "IA_MODE" && horsLigne) || (ac.ia === "IA_ACTIONS" ? !agentPermis : Reglages.val(ac.ia, "oui") === "non"))) continue
            if (ac.siCoupee && !Reglages.iaCoupee) continue
            if (sc > 0) out.push({ titre: ac.t, sous: "Action", glyphe: ac.g, s: sc - 8, f: ac.f, garder: ac.garder })
        }
        // Fichiers
        for (let n = 0; n < fichiers.length; n++) {
            let fi = fichiers[n], chemin = fi.path
            out.push({ titre: fi.name, sous: (fi.dir ? Reglages.t("Dossier · ", "Folder · ") : Reglages.t("Fichier · ", "File · ")) + fi.parent,
                       icone: Quickshell.iconPath(iconeFichier(fi.name, fi.dir), true), glyphe: "description",
                       s: Math.min(70, Math.max(15, score(qa, fi.name, true) * 0.75)),   // jamais devant une appli qui commence par la saisie
                       f: () => Quickshell.execDetached([Etat.bin + "nc-apps", "open", chemin]) })
        }
        // Une question en langage naturel (« comment changer le fond d'écran ») : les réponses de la config en tête
        if (Aide.estQuestion(q)) reponsesAide(q, 3).forEach(e => out.push(itemAide(e, 500 + e.score)))
        out.sort((x, y) => y.s - x.s)
        out = out.slice(0, nbResultats)
        // Logiciels à installer dont le nom commence par la saisie : deux au plus, en bas (pas ceux déjà là)
        if (modePaquets === "auto" && paquetsPour === q && q.length >= 3) {
            let noms = applis.map(a => (a.id || "").toLowerCase().replace(/\.desktop$/, ""))
            let aInstaller = paquets.filter(p => !p.installe && p.score >= 85 && noms.indexOf(p.nom.toLowerCase()) < 0).slice(0, 2)
            if (aInstaller.length) out = out.slice(0, nbResultats - aInstaller.length).concat(aInstaller.map(p => itemPaquet(p, 0)))
        }
        // Saisie qui commence par un programme (« htop », « ping google.fr ») : la lancer dans le terminal
        var prog = q.split(/\s+/)[0]
        if (execs[prog] && !q.startsWith("/")) {
            let commande = q
            out = out.slice(0, out.length && out[0].s >= 90 && q.indexOf(" ") < 0 ? nbResultats - 1 : nbResultats - 2)
            let lancerItem = { titre: commande, sous: Reglages.t("Lancer dans le terminal", "Run in Terminal"), glyphe: "terminal", aide: "↵", f: () => r.lancerCommande(commande) }
            // Avec des arguments, ou si rien ne lui correspond vraiment : en tête
            if (q.indexOf(" ") >= 0 || !out.length || out[0].s < 90) out.unshift(lancerItem); else out.push(lancerItem)
        }
        resultats = out
        if (sel >= resultats.length) sel = Math.max(0, resultats.length - 1)
    }

    function lancer(id) {
        Quickshell.execDetached([Etat.bin + "nc-apps", "launch", id])
        // Suivre l'appli : sa fenêtre peut s'ouvrir sur un autre bureau (Discord réduit dans la zone de notification
        // ressort là où il était) ; dès qu'elle apparaît, on y va
        var ap = applis.find(x => x.id === id)
        if (ap) {
            suivi.noms = [ap.wmclass, ap.id, ap.exe === "env" ? "" : ap.exe].filter(x => x).map(x => x.toLowerCase())
            suivi.avant = fenetres.map(f => f.address)
            suivi.fin = Date.now() + 10000
            suivi.restart()
        }
        try {
            let u = Object.assign({}, usage)
            let e = u[id] || { n: 0 }
            u[id] = { n: (e.n || 0) + 1, t: Math.floor(Date.now() / 1000) }
            usage = u
            fichierUsage.setText(JSON.stringify(u))
        } catch (err) {}
    }
    Timer {
        id: suivi
        property var noms: []
        property var avant: []
        property real fin: 0
        interval: 400; repeat: true
        onTriggered: { if (Date.now() > fin) stop(); else if (!chercheFenetre.running) chercheFenetre.running = true }
    }
    Process {
        id: chercheFenetre
        command: ["hyprctl", "clients", "-j"]
        stdout: StdioCollector {
            onStreamFinished: {
                var l = []
                try { l = JSON.parse(text) } catch (e) { return }
                var f = l.find(c => c.mapped && suivi.noms.indexOf((c.class || "").toLowerCase()) >= 0 && suivi.avant.indexOf(c.address) < 0)
                if (f) { r.allerA(f.address); suivi.stop() }    // arrêter le suivi peut décharger le Spotlight : après
            }
        }
    }
    property bool entreeEnAttente: false
    // Encore du travail après la fermeture (suivre la fenêtre d'une appli lancée, Entrée en attente) : reste chargée
    readonly property bool occupe: suivi.running || entreeEnAttente
    function valider(i, nouveau) {
        // Applis pas encore chargées (on tape vite juste après Super + R) : on attend la liste avant de choisir
        // (pas pour « ? », « ! », « > », « + » ni une question : leurs réponses ne dépendent pas des applis)
        if ((lireApplis.running || applis.length === 0) && !/^([?>+!@]|sessions? )/i.test(q) && !Aide.estQuestion(q)) { entreeEnAttente = true; return }
        var x = resultats[i]
        if (!x) return
        if (x.page) { Etat.recherche = false; Etat.aller(x.page); return }
        if (x.garder) { x.f(); return }        // question à l'IA : le Spotlight reste ouvert pour la réponse
        // Action d'abord : fermer l'île décharge le Spotlight tout de suite (ses fonctions n'existeraient plus)
        if (nouveau && x.nouveau) x.nouveau(); else x.f()
        Etat.fermer()
    }

    // ── Dessin ──
    // Barre de recherche
    Item {
        id: barre
        width: parent.width; height: 56
        Ico { id: loupe; x: 22; anchors.verticalCenter: parent.verticalCenter; nom: "search"; taille: 22; color: Couleurs.texteSec }
        TextInput {
            id: champ
            objectName: "nc-spotlight-champ"
            anchors.left: loupe.right; anchors.leftMargin: 12; anchors.right: parent.right; anchors.rightMargin: 22
            anchors.verticalCenter: parent.verticalCenter
            color: Couleurs.texte; selectionColor: Couleurs.accent; selectedTextColor: Couleurs.surAccent
            font.family: "Adwaita Sans"; font.pixelSize: 19
            clip: true
            cursorVisible: activeFocus
            Keys.onEscapePressed: Etat.fermer()
            Keys.onDownPressed: r.sel = Math.min(r.resultats.length - 1, r.sel + 1)
            Keys.onUpPressed: r.sel = Math.max(0, r.sel - 1)
            Keys.onTabPressed: r.sel = r.resultats.length > 0 ? (r.sel + 1) % r.resultats.length : 0
            Keys.onReturnPressed: e => r.valider(r.sel, (e.modifiers & Qt.ControlModifier) !== 0)
            Keys.onEnterPressed: e => r.valider(r.sel, (e.modifiers & Qt.ControlModifier) !== 0)
            Texte {
                visible: champ.text === ""
                anchors.verticalCenter: parent.verticalCenter
                text: Reglages.t("Rechercher  ·  ? question  ·  > commande  ·  + installer", "Search  ·  ? question  ·  > command  ·  + install"); secondaire: true; font.pixelSize: 19
            }
        }
    }

    // Réponse de l'IA (« ? … »)
    Rectangle {
        id: zoneReponse
        visible: r.reponseAide !== "" || ((r.q.startsWith("?") || ((r.q.startsWith("!") && r.modeTexte || r.q.startsWith("@") && r.modeAgent) && r.q === r.questionPosee)) && (r.reflechit || r.reponse !== ""))
        readonly property bool attend: r.reflechit && r.reponse === ""
        // Plan de rangement en zones (« me montrer le plan d'abord ») : une mini-carte de l'écran plutôt qu'une liste
        readonly property var zones: r.plan && r.plan.actions ? r.plan.actions.filter(a => a.outil === "fenetre_zone" && a.args) : []
        anchors.top: barre.bottom; anchors.topMargin: 4
        x: 14; width: parent.width - 28; radius: 16; color: Couleurs.gris2
        height: Math.min(12 + enTete.height + (texteReponse.visible ? 6 + texteReponse.implicitHeight : 0)
                         + (miniCarte.visible ? 10 + miniCarte.height : 0) + 14, 420)
        clip: true
        Row {
            id: enTete
            x: 14; y: 12; spacing: 8
            Etincelle {
                anchors.verticalCenter: parent.verticalCenter; taille: 15; tourne: r.reflechit
                agent: r.agentReponse
            }
            Texte { anchors.verticalCenter: parent.verticalCenter; secondaire: true; font.pixelSize: 12
                    text: r.reponseAide !== "" ? Reglages.t("Aide de la config · ", "Config help · ") + r.titreAide
                        : zoneReponse.attend ? r.iaReponse + Reglages.t(" réfléchit…", " is thinking…") : r.iaReponse }
        }
        Text {
            id: texteReponse
            anchors.top: enTete.bottom; anchors.topMargin: 6
            x: 14; width: parent.width - 28
            text: r.reponseAide !== "" ? r.reponseAide : AssistantEtat.formater(r.reponse)
            visible: !zoneReponse.attend || r.reponseAide !== ""
            color: Couleurs.texte; font.family: "Adwaita Sans"; font.pixelSize: 14; wrapMode: Text.Wrap
            textFormat: r.reponseAide !== "" ? Text.PlainText : Text.MarkdownText
        }
        // Mini-carte : l'écran aux proportions 16:10, chaque zone en carte arrondie avec le nom de son appli
        Rectangle {
            id: miniCarte
            objectName: "nc-spotlight-mini-carte"
            visible: zoneReponse.zones.length > 0 && !zoneReponse.attend && r.reponseAide === ""
            anchors.top: texteReponse.bottom; anchors.topMargin: 10
            x: 14; width: Math.min(parent.width - 28, 300); height: Math.round(width * 10 / 16)
            radius: 12; color: Qt.alpha(Couleurs.fond, 0.6)
            Repeater {
                model: zoneReponse.zones
                Rectangle {
                    required property var modelData
                    required property int index
                    readonly property real e: 3
                    x: miniCarte.width * Number(modelData.args.x) / 100 + e
                    y: miniCarte.height * Number(modelData.args.y) / 100 + e
                    width: Math.max(4, miniCarte.width * Number(modelData.args.largeur) / 100 - 2 * e)
                    height: Math.max(4, miniCarte.height * Number(modelData.args.hauteur) / 100 - 2 * e)
                    radius: Math.min(9, Math.min(width, height) / 3)
                    color: index % 2 ? Couleurs.carteSurvol : Couleurs.carte
                    border.width: modelData.fait ? 1.5 : 0; border.color: Couleurs.accent
                    Texte {
                        anchors.centerIn: parent; width: parent.width - 8; horizontalAlignment: Text.AlignHCenter
                        text: String(modelData.libelle || "").split(" :")[0]; font.pixelSize: 11; secondaire: true
                    }
                }
            }
        }
    }

    // Résultats
    Column {
        id: liste
        anchors.top: zoneReponse.visible ? zoneReponse.bottom : barre.bottom; anchors.topMargin: 6
        x: 8; width: parent.width - 16
        Repeater {
            model: r.resultats
            Rectangle {
                id: ligne
                required property var modelData
                required property int index
                readonly property bool choisi: index === r.sel
                width: liste.width; height: r.hauteurLigne; radius: 14
                color: choisi ? Couleurs.gris2 : "transparent"
                Item {
                    id: ic
                    x: 12; anchors.verticalCenter: parent.verticalCenter
                    width: 28; height: 28
                    Image {
                        id: img
                        anchors.fill: parent
                        source: ligne.modelData.icone || ""
                        sourceSize: Qt.size(56, 56)
                        visible: status === Image.Ready
                    }
                    Ico { anchors.centerIn: parent; nom: ligne.modelData.glyphe || "search"; taille: 22; color: Couleurs.texteDoux; visible: img.status !== Image.Ready }
                }
                Texte {
                    anchors.left: ic.right; anchors.leftMargin: 12; anchors.verticalCenter: parent.verticalCenter
                    width: parent.width - 12 - 28 - 12 - sous.width - 40
                    text: ligne.modelData.titre; font.pixelSize: 15; font.weight: ligne.choisi ? Font.DemiBold : Font.Normal
                }
                Texte {
                    id: sous
                    anchors.right: parent.right; anchors.rightMargin: 14; anchors.verticalCenter: parent.verticalCenter
                    width: Math.min(implicitWidth, 320)
                    text: ligne.modelData.sous + (ligne.choisi ? "  ·  " + (ligne.modelData.aide || "↵") : ""); secondaire: true; font.pixelSize: 13
                    horizontalAlignment: Text.AlignRight
                }
                MouseArea {
                    anchors.fill: parent; hoverEnabled: true
                    onEntered: r.sel = ligne.index
                    onClicked: e => r.valider(ligne.index, (e.modifiers & Qt.ControlModifier) !== 0)
                }
            }
        }
    }
}

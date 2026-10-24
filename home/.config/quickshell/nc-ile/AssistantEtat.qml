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
        for (let i = 0; i < 32; i++) s += Math.floor(Math.random() * 16).toString(16)
        return s
    }
    property string brouillon: ""
    property var messages: []
    property string erreur: ""
    property bool enCours: false
    property bool reponseRecente: false
    readonly property string activitePilule: enCours ? "jarvis" : (reponseRecente ? "jarvis-fini" : "")
    onEnCoursChanged: if (enCours) { reponseRecente = false; finReponse.stop() }
    Timer { id: finReponse; interval: 3000; onTriggered: a.reponseRecente = false }
    property string question: ""
    property bool sortieFinie: false
    property bool processusFini: false
    property int code: -1
    property string reponse: ""
    property bool reglagesOuverts: false
    property bool reglagesEnCours: false
    readonly property bool ecritureReglagesEnCours: reglagesEnCours && operationReglages !== "quick-settings"
    readonly property var commandes: [
        {nom:"/help", alias:["/aide","/commandes","/commands"], arguments:false, description:Reglages.t("Afficher les commandes", "Show commands")},
        {nom:"/reset", alias:["/clear","/nouveau"], arguments:false, description:Reglages.t("Réinitialiser la session", "Reset the session")},
        {nom:"/status", alias:["/etat","/diag"], arguments:false, description:Reglages.t("État du serveur et du moteur", "Server and engine status")},
        {nom:"/briefing", alias:[], arguments:false, description:Reglages.t("Briefing du jour", "Daily briefing")},
        {nom:"/models", alias:["/modeles"], arguments:false, description:Reglages.t("Lister les modèles disponibles", "List available models")},
        {nom:"/model", alias:["/modele"], arguments:true, description:Reglages.t("Choisir un modèle : /model <nom>", "Choose a model: /model <name>")},
        {nom:"/engine", alias:["/moteur"], arguments:true, description:Reglages.t("Choisir un moteur : agy, codex, claude, opencode", "Choose an engine: agy, codex, claude, opencode")},
        {nom:"/effort", alias:[], arguments:true, description:Reglages.t("Régler le niveau de réflexion", "Set reasoning effort")},
        {nom:Reglages.t("/courses","/shopping"), alias:["/courses","/shopping"], arguments:true, description:Reglages.t("Voir les courses ou ajouter des articles", "View groceries or add items")},
        {nom:Reglages.t("/depenses","/expenses"), alias:["/depenses","/expenses"], arguments:true, description:Reglages.t("Bilan ou ajout d’une dépense", "Summary or add an expense")},
        {nom:Reglages.t("/devoirs","/moodle"), alias:["/devoirs","/moodle"], arguments:false, description:Reglages.t("Consulter les devoirs", "View homework")},
        {nom:Reglages.t("/rappel","/remind"), alias:["/rappel","/remind"], arguments:true, description:Reglages.t("Rappel : /rappel [bureau|telegram|discord] [tous les jours|chaque samedi|toutes les 3 heures] <délai ou heure> <message>", "Reminder: /remind [desktop|telegram|discord] [every day|every saturday|every 3 hours] <delay or time> <message>")},
        {nom:Reglages.t("/rappels","/reminders"), alias:["/rappels","/reminders"], arguments:false, description:Reglages.t("Rappels en attente sur le serveur", "Pending reminders on the server")},
        {nom:"/supprimer", alias:["/supprimer","/delrappel"], arguments:true, description:Reglages.t("Supprimer un rappel : /supprimer <numéro>", "Delete a reminder: /supprimer <number>")},
        {nom:Reglages.t("/memoire","/memory"), alias:["/memoire","/memory"], arguments:true, description:Reglages.t("Consulter ou enrichir la mémoire", "View or add to memory")}
    ]
    function proposerCommandes(texte, position) {
        var m = /^(\/[^\s]*)([\s\S]*)$/.exec(texte)
        if (!m || position < 1 || position > m[1].length) return []
        var prefixe = m[1].slice(0, position).toLowerCase()
        return commandes.map((c, ordre) => {
            var nom = [c.nom].concat(c.alias).find(n => n.indexOf(prefixe) === 0)
            return nom ? {texte:nom, description:c.description, arguments:c.arguments, fin:m[1].length, principal:nom === c.nom, ordre:ordre} : null
        }).filter(c => c !== null).sort((x,y) => Number(y.principal) - Number(x.principal) || x.ordre - y.ordre)
    }
    function commandeComplete(texte) {
        var nom = texte.trim().split(/\s+/)[0].toLowerCase()
        return commandes.some(c => c.nom === nom || c.alias.indexOf(nom) >= 0)
    }
    property bool reglagesDisponibles: false
    property bool reglagesDemandes: false
    property var moteurs: [
        {id:"agy", name:"Antigravity", installed:false}, {id:"codex", name:"Codex", installed:false},
        {id:"claude", name:"Claude Code", installed:false}, {id:"opencode", name:"OpenCode", installed:false}
    ]
    property string moteur: ""
    property string modele: ""
    property string effort: ""
    // Valeurs confirmées par le serveur, distinctes des choix en attente d'« Appliquer ».
    property var sessionReglages: ({engine:"", model:"", effort:""})
    readonly property bool reglagesModifies: moteur !== sessionReglages.engine || modele !== sessionReglages.model || effort !== sessionReglages.effort
    property string erreurReglages: ""
    property string operationReglages: ""
    property var parametresReglages: ({})
    property string sortieReglages: ""
    property bool sortieReglagesFinie: false
    property bool processusReglagesFini: false
    property int codeReglages: -1
    readonly property var moteurCourant: moteurs.find(m => m.id === moteur) || ({})
    // Modes de permission que le serveur permet pour le moteur (agy sans --permission-mode : seulement « default »).
    readonly property var modesPermis: Array.isArray(moteurCourant.permission_modes) ? moteurCourant.permission_modes : []
    readonly property bool permissionUnique: moteur === "agy" && modesPermis.length === 1
    readonly property var modeles: moteurCourant.models || []
    readonly property var modeleCourant: modeles.find(m => m.id === modele) || ({})
    // Niveaux de réflexion proposés : ceux du modèle s'il en annonce (un tableau, même vide), sinon ceux du moteur ; aucun
    // pour un modèle à réflexion fixe (Claude Opus « thinking » : agy refuse --effort, JARVIS-BIS l'ignore)
    function reflexionFixe(id) { return id === "claude-opus-4-6-thinking" || /opus.*thinking/i.test(id || "") }
    readonly property var efforts: reflexionFixe(modele) ? []
        : Array.isArray(modeleCourant.efforts) ? modeleCourant.efforts
        : Array.isArray(moteurCourant.efforts) ? moteurCourant.efforts : []
    readonly property var famillesModeles: ["Flash", "Argon", "Opus", "Sonnet"]
    function familleModele(item) {
        var mots = ((item.id || "") + " " + (item.name || "")).toLowerCase().split(/[^a-z0-9]+/)
        return famillesModeles.find(nom => mots.indexOf(nom.toLowerCase()) >= 0) || ""
    }
    function modelePourFamille(nom) {
        var candidats = modeles.filter(m => familleModele(m) === nom)
        return candidats.find(m => m.id === modele)
            || candidats.find(m => effort && m.id.endsWith("-" + effort)) || candidats[0] || null
    }
    function modelePourEffort(niveau) {
        if (efforts.indexOf(niveau) < 0) return null
        // Opus intègre sa propre réflexion et ne supporte aucun paramètre d'effort : boutons grisés
        if (reflexionFixe(modele)) return null
        // Certains CLI encodent aussi l'effort dans l'identifiant du modèle.
        var suffixe = /-(low|medium|high)$/.exec(modele)
        if (!suffixe) return modele
        var identifiant = modele.slice(0, -suffixe[0].length) + "-" + niveau
        return modeles.some(m => m.id === identifiant) ? identifiant : null
    }
    function choisirFamille(nom) {
        if (!reglagesDisponibles || enCours || reglagesEnCours || !moteurCourant.installed) return
        var m = modelePourFamille(nom)
        if (!m) return
        modele = m.id
        var suffixe = /-(low|medium|high)$/.exec(m.id)
        effort = suffixe ? suffixe[1] : (efforts.indexOf(effort) >= 0 ? effort : "")
    }
    function choisirEffort(niveau) {
        if (!reglagesDisponibles || enCours || reglagesEnCours) return
        var identifiant = modelePourEffort(niveau)
        if (identifiant === null) return
        modele = identifiant; effort = niveau
    }

    function ouvrirReglages() {
        reglagesOuverts = !reglagesOuverts
        if (reglagesOuverts) lireReglages()
        else if (!reglagesEnCours) {
            moteur = sessionReglages.engine; modele = sessionReglages.model; effort = sessionReglages.effort
        }
    }
    function choisirMoteur(id) { moteur = id; modele = ""; effort = "" }
    function lireReglages() { reglagesDemandes = true; lancerReglages("quick-settings", {}) }
    function appliquerReglages() {
        if (enCours || !reglagesDisponibles) return
        lancerReglages("session.update", {engine:moteur, model:modele.trim(), effort:reflexionFixe(modele) ? "" : effort})
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
                sessionReglages = {engine:moteur, model:modele, effort:effort}
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

    readonly property var tableExposants: ({
        "0":"⁰","1":"¹","2":"²","3":"³","4":"⁴","5":"⁵","6":"⁶","7":"⁷","8":"⁸","9":"⁹",
        "+":"⁺","-":"⁻","−":"⁻","=":"⁼","(":"⁽",")":"⁾","n":"ⁿ","i":"ⁱ",
        "a":"ᵃ","b":"ᵇ","c":"ᶜ","d":"ᵈ","e":"ᵉ","f":"ᶠ","g":"ᵍ","h":"ʰ","j":"ʲ","k":"ᵏ","l":"ˡ","m":"ᵐ",
        "o":"ᵒ","p":"ᵖ","r":"ʳ","s":"ˢ","t":"ᵗ","u":"ᵘ","v":"ᵛ","w":"ʷ","x":"ˣ","y":"ʸ","z":"ᶻ",
        "A":"ᴬ","B":"ᴮ","D":"ᴰ","E":"ᴱ","G":"ᴳ","H":"ᴴ","I":"ᴵ","J":"ᴶ","K":"ᴷ","L":"ᴸ","M":"ᴹ","N":"ᴺ","O":"ᴼ","P":"ᴾ","R":"ᴿ","T":"ᵀ","U":"ᵁ","V":"ⱽ","W":"ᵂ"
    })
    readonly property var tableIndices: ({
        "0":"₀","1":"₁","2":"₂","3":"₃","4":"₄","5":"₅","6":"₆","7":"₇","8":"₈","9":"₉",
        "+":"₊","-":"₋","−":"₋","=":"₌","(":"₍",")":"₎",
        "a":"ₐ","e":"ₑ","h":"ₕ","i":"ᵢ","j":"ⱼ","k":"ₖ","l":"ₗ","m":"ₘ","n":"ₙ","o":"ₒ","p":"ₚ","r":"ᵣ","s":"ₛ","t":"ₜ","u":"ᵤ","v":"ᵥ","x":"ₓ",
        "β":"ᵦ","γ":"ᵧ","ρ":"ᵨ","φ":"ᵩ","χ":"ᵪ"
    })
    readonly property var symbolesLatex: ({
        "alpha":"α","beta":"β","gamma":"γ","delta":"δ","epsilon":"ε","varepsilon":"ε","zeta":"ζ","eta":"η",
        "theta":"θ","vartheta":"θ","iota":"ι","kappa":"κ","lambda":"λ","mu":"μ","nu":"ν","xi":"ξ",
        "pi":"π","varpi":"π","rho":"ρ","varrho":"ρ","sigma":"σ","varsigma":"ς","tau":"τ","upsilon":"υ",
        "phi":"φ","varphi":"φ","chi":"χ","psi":"ψ","omega":"ω",
        "Gamma":"Γ","Delta":"Δ","Theta":"Θ","Lambda":"Λ","Xi":"Ξ","Pi":"Π","Sigma":"Σ","Upsilon":"Υ","Phi":"Φ","Psi":"Ψ","Omega":"Ω",
        "infty":"∞","partial":"∂","nabla":"∇","forall":"∀","exists":"∃","nexists":"∄","emptyset":"∅","varnothing":"∅",
        "in":"∈","notin":"∉","ni":"∋","subset":"⊂","subseteq":"⊆","supset":"⊃","supseteq":"⊇","cup":"∪","cap":"∩","setminus":"∖",
        "pm":"±","mp":"∓","times":"×","cdot":"·","div":"÷","ast":"∗","star":"⋆","circ":"∘","bullet":"∙",
        "leq":"≤","le":"≤","geq":"≥","ge":"≥","neq":"≠","ne":"≠","approx":"≈","equiv":"≡","sim":"∼","simeq":"≃","cong":"≅","propto":"∝",
        "to":"→","rightarrow":"→","leftarrow":"←","leftrightarrow":"↔","Rightarrow":"⇒","implies":"⇒","Leftarrow":"⇐","Leftrightarrow":"⇔","iff":"⇔","mapsto":"↦","uparrow":"↑","downarrow":"↓",
        "sum":"∑","prod":"∏","coprod":"∐","int":"∫","iint":"∬","iiint":"∭","oint":"∮",
        "land":"∧","wedge":"∧","lor":"∨","vee":"∨","neg":"¬","lnot":"¬","oplus":"⊕","otimes":"⊗",
        "perp":"⊥","parallel":"∥","angle":"∠","degree":"°","prime":"′","ell":"ℓ","hbar":"ℏ","aleph":"ℵ",
        "dots":"…","ldots":"…","cdots":"⋯","vdots":"⋮","ddots":"⋱",
        "langle":"⟨","rangle":"⟩","lceil":"⌈","rceil":"⌉","lfloor":"⌊","rfloor":"⌋",
        "quad":"  ","qquad":"    "
    })
    readonly property var ensemblesLatex: ({"R":"ℝ","N":"ℕ","Z":"ℤ","Q":"ℚ","C":"ℂ","F":"𝔽","E":"𝔼","P":"ℙ","H":"ℍ","K":"𝕂"})
    readonly property var calligraphieLatex: ({"L":"ℒ","O":"𝒪","H":"ℋ","F":"ℱ","N":"𝒩","P":"𝒫","M":"ℳ","E":"ℰ","B":"ℬ","R":"ℛ","I":"ℐ"})
    readonly property var fractionsUnicode: ({"1/2":"½","1/3":"⅓","2/3":"⅔","1/4":"¼","3/4":"¾","1/5":"⅕","2/5":"⅖","3/5":"⅗","4/5":"⅘","1/6":"⅙","5/6":"⅚","1/8":"⅛","3/8":"⅜","5/8":"⅝","7/8":"⅞"})

    function convertirScript(s, table, prefixe) {
        var propre = String(s || "").trim()
        if (!propre) return ""
        var out = ""
        for (let i = 0; i < propre.length; i++) {
            let ch = propre[i]
            if (ch === " ") continue
            let m = table[ch]
            if (!m) return prefixe + "(" + propre + ")"
            out += m
        }
        return out
    }
    function parentheserTerme(s) {
        var t = String(s || "").trim()
        return /^[a-zA-Z0-9α-ωΑ-Ωℝℕℤℚℂ∞π⁰-⁹₀-₉]+$/.test(t) ? t : "(" + t + ")"
    }
    function formaterCommandesLatex(s) {
        var t = String(s || "")
        t = t.replace(/\\(?:left|right|[bB]ig{1,2}|displaystyle|textstyle|scriptstyle|limits|nolimits)(?![a-zA-Z])\s*/g, "")
        t = t.replace(/\\mathbb\{([A-Z])\}/g, (_, l) => a.ensemblesLatex[l] || l)
        t = t.replace(/\\mathcal\{([A-Z])\}/g, (_, l) => a.calligraphieLatex[l] || l)
        t = t.replace(/\\(?:text|textrm|mathrm|operatorname|mathit|textit|textbf|mathbf)\{([^{}]*)\}/g, "$1")
        t = t.replace(/\\vec\{([^{}]*)\}/g, "$1⃗")
        t = t.replace(/\\hat\{([^{}]*)\}/g, "$1̂")
        t = t.replace(/\\(?:bar|overline)\{([^{}]*)\}/g, "$1̄")
        t = t.replace(/\\tilde\{([^{}]*)\}/g, "$1̃")
        t = t.replace(/\\ddot\{([^{}]*)\}/g, "$1̈")
        t = t.replace(/\\dot\{([^{}]*)\}/g, "$1̇")
        for (let n = 0; n < 4; n++) {
            t = t.replace(/\\sqrt\[([^{}\]]+)\]\{([^{}]*)\}/g, (_, deg, rad) => a.convertirScript(a.formaterCommandesLatex(deg), a.tableExposants, "^") + "√" + a.parentheserTerme(a.formaterCommandesLatex(rad)))
            t = t.replace(/\\sqrt\{([^{}]*)\}/g, (_, rad) => "√" + a.parentheserTerme(a.formaterCommandesLatex(rad)))
            t = t.replace(/\\(?:d|t)?frac\{([^{}]*)\}\{([^{}]*)\}/g, (_, num, den) => {
                var u = a.formaterCommandesLatex(num).trim(), d = a.formaterCommandesLatex(den).trim()
                if (a.fractionsUnicode[u + "/" + d]) return a.fractionsUnicode[u + "/" + d]
                return a.parentheserTerme(u) + "/" + a.parentheserTerme(d)
            })
            t = t.replace(/\\binom\{([^{}]*)\}\{([^{}]*)\}/g, (_, haut, bas) => "C(" + a.formaterCommandesLatex(haut).trim() + ", " + a.formaterCommandesLatex(bas).trim() + ")")
        }
        t = t.replace(/\\([a-zA-Z]+)/g, (m, cmd) => a.symbolesLatex[cmd] !== undefined ? a.symbolesLatex[cmd] : cmd)
        t = t.replace(/\\([,;:])/g, " ").replace(/\\!/g, "").replace(/\\([{}_%&#$])/g, "$1")
        for (let k = 0; k < 3; k++) {
            t = t.replace(/\^\{([^{}]+)\}/g, (_, exp) => a.convertirScript(exp, a.tableExposants, "^"))
            t = t.replace(/_\{([^{}]+)\}/g, (_, ind) => a.convertirScript(ind, a.tableIndices, "_"))
        }
        t = t.replace(/\^([0-9+\-=ni]|[a-zA-Z])/g, (_, exp) => a.convertirScript(exp, a.tableExposants, "^"))
        t = t.replace(/([a-zA-Z0-9α-ωΑ-Ω∑∏∫)\]⟩])_([0-9aehijklmnoprstuvxβγρφχ])/g, (_, base, ind) => base + a.convertirScript(ind, a.tableIndices, "_"))
        return t
    }
    function formaterLatex(expr, bloc) {
        var t = String(expr || "").trim()
        t = t.replace(/\\begin\{([pbvBV]?matrix|cases)\}([\s\S]*?)\\end\{\1\}/g, (_, env, contenu) => {
            var lignes = contenu.trim().split(/\\\\/).map(l => l.trim()).filter(l => l.length > 0).map(l => {
                return l.split("&").map(c => a.formaterCommandesLatex(c.trim())).join(env === "cases" ? "  " : ", ")
            })
            if (env === "cases") return "{ " + lignes.join(" ; ")
            var ouv = env === "pmatrix" ? "(" : (env === "Bmatrix" ? "{" : (env === "vmatrix" || env === "Vmatrix" ? "|" : "["))
            var fer = env === "pmatrix" ? ")" : (env === "Bmatrix" ? "}" : (env === "vmatrix" || env === "Vmatrix" ? "|" : "]"))
            return lignes.map(l => ouv + l + fer).join(bloc ? "\n" : " ; ")
        })
        t = t.replace(/\\\\/g, "\n").replace(/\s*&\s*/g, " ")
        t = formaterCommandesLatex(t)
        if (!bloc) return t.replace(/\s*\n\s*/g, " ").trim()
        return "\n\n" + t.split("\n").map(l => "> **" + l.trim() + "**").join("\n") + "\n\n"
    }
    function formater(texte) {
        if (typeof texte !== "string" || !texte.length) return ""
        var blocs = []
        function garder(s) {
            var id = "\u0000BLOC" + blocs.length + "\u0000"
            blocs.push(s)
            return id
        }
        var t = texte
        // Protéger les blocs de code et le code en ligne avant la conversion HTML / LaTeX
        t = t.replace(/```[\s\S]*?```/g, m => garder(m))
        t = t.replace(/`[^`\n]+`/g, m => garder(m))
        // Balises HTML éventuelles renvoyées par un backend orienté Telegram
        t = t.replace(/<pre>([\s\S]*?)<\/pre>/gi, (_, c) => garder("\n```\n" + c.trim() + "\n```\n"))
        t = t.replace(/<code>([\s\S]*?)<\/code>/gi, (_, c) => garder("`" + c + "`"))
        t = t.replace(/<(?:b|strong)>([\s\S]*?)<\/(?:b|strong)>/gi, "**$1**")
        t = t.replace(/<(?:i|em)>([\s\S]*?)<\/(?:i|em)>/gi, "*$1*")
        t = t.replace(/<s>([\s\S]*?)<\/s>/gi, "~~$1~~")
        // Pas de chargement d'image externe en Markdown
        t = t.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, "[$1]($2)")
        // Les caractères LaTeX d'une URL (notamment $, _ et \\) font partie du lien.
        t = t.replace(/(?:https?:\/\/|file:\/\/\/|mailto:)[^\s<>"`]+/gi, m => garder(m))
        // Blocs LaTeX ($$...$$, \[...\], \begin{equation|align|gather|math|displaymath}...\end{...})
        t = t.replace(/\$\$([\s\S]+?)\$\$/g, (_, m) => a.formaterLatex(m, true))
        t = t.replace(/\\\[([\s\S]+?)\\\]/g, (_, m) => a.formaterLatex(m, true))
        t = t.replace(/\\begin\{(equation|align|gather|math|displaymath)\*?\}([\s\S]+?)\\end\{\1\*?\}/g, (_, _env, m) => a.formaterLatex(m, true))
        // LaTeX en ligne (\(...\) et $...$)
        t = t.replace(/\\\(([\s\S]+?)\\\)/g, (_, m) => a.formaterLatex(m, false))
        t = t.replace(/\$(?!\s)([^\$\n]*?\S)\$/g, (tout, m) => {
            if (/^\d+(?:[.,]\d+)?\s+(?:et|ou|and|or)\s+\d+/i.test(m)) return tout
            return a.formaterLatex(m, false)
        })
        // Commandes LaTeX isolées hors délimiteurs $...$
        if (/\\(?:frac|dfrac|tfrac|sqrt|binom|mathbb|mathcal|text|vec|hat|bar|overline|sum|prod|int|infty|partial|nabla|pm|mp|times|cdot|leq|geq|neq|approx|equiv|to|rightarrow|Rightarrow|iff|implies|alpha|beta|gamma|delta|epsilon|theta|lambda|mu|pi|sigma|tau|phi|omega|Delta|Sigma|Omega)(?![a-zA-Z])/.test(t)) {
            t = a.formaterCommandesLatex(t)
        }
        return t.replace(/\u0000BLOC(\d+)\u0000/g, (_, idx) => blocs[Number(idx)] || "")
    }
    function apercu(texte) {
        var t = formater(texte)
        t = t.replace(/```[\s\S]*?```/g, m => m.replace(/```[a-zA-Z0-9_-]*\n?/g, "").trim())
        t = t.replace(/`([^`]+)`/g, "$1")
        t = t.replace(/\*\*([^*]+)\*\*/g, "$1").replace(/\*([^*]+)\*/g, "$1").replace(/~~([^~]+)~~/g, "$1")
        t = t.replace(/^\s*(?:>+|\#{1,6}|\-|\*|\d+\.)\s+/gm, "")
        return t.replace(/\s+/g, " ").trim()
    }

    property int dernierId: 0               // identifiant du dernier message ajouté (une fenêtre de chat part de là)
    // Réponses de l'IA du bureau versées dans la conversation (nc-ia : zone de l'écran, texte, fichier…) : la suite part
    // vers la même IA (avec le contexte), pas vers JARVIS qui ne les a pas vues ; nomChat : qui répond dans la fenêtre
    property bool suiteParIA: false
    property string nomChat: ""
    property string agentChat: ""
    property int idEchange: 0               // premier message du dernier échange versé (la fenêtre de chat s'ouvre dessus)
    property var arrivees: []               // fichiers d'échange en attente de lecture
    function recevoirReponse(chemin) {
        if (!/^\/[^\0]*\/nc-ia\/chat\/[0-9]+-[0-9]+\.json$/.test(chemin)) return      // seulement les fichiers de nc-ia
        arrivees = arrivees.concat([chemin])
        if (!lectureEchange.running) lireSuivant()
    }
    function lireSuivant() {
        if (!arrivees.length) return
        lectureEchange.chemin = arrivees[0]; arrivees = arrivees.slice(1)
        lectureEchange.command = ["sh", "-c", "cat -- \"$1\" && rm -f -- \"$1\"", "sh", lectureEchange.chemin]
        lectureEchange.running = true
    }
    Process {
        id: lectureEchange
        property string chemin: ""
        stdout: StdioCollector {
            onStreamFinished: {
                try {
                    let d = JSON.parse(text)
                    a.ajouter("vous", String(d.question || "").slice(0, 4000))
                    a.idEchange = a.dernierId
                    a.ajouter("assistant", String(d.reponse || "").slice(0, 16000) + "\n\n*— " + (d.ia || "IA") + "*")
                    a.suiteParIA = d.ia !== "JARVIS"; a.nomChat = d.ia || ""; a.agentChat = d.agent || ""
                } catch (e) {}
                a.lireSuivant()
            }
        }
    }
    // Qui répondra dans une fenêtre de chat ouverte à neuf (JARVIS s'il est relié, sinon l'IA du bureau)
    function lireQuiChat() { if (!quiChat.running) quiChat.running = true }
    Process {
        id: quiChat
        command: [a.bin + "nc-ia", "quelle", "--chat", "--json"]
        stdout: StdioCollector { onStreamFinished: { try { let d = JSON.parse(text); a.nomChat = d.nom || ""; a.agentChat = d.agent || "" } catch (e) {} } }
    }
    // Choix proposés par JARVIS (champ choices de la réponse, issue #7) : gardés avec son message ; choixFait : le libellé
    // cliqué (les pastilles de ce message ne servent plus)
    function nettoyerChoix(c) {
        return (Array.isArray(c) ? c : []).filter(x => typeof x === "string" && x.trim() !== "")
            .map(x => x.trim().slice(0, 80)).filter((x, i, l) => l.indexOf(x) === i).slice(0, 5)
    }
    function ajouter(role, texte, choix) {
        var m = messages.concat([{role: role, texte: texte, num: ++dernierId, choix: nettoyerChoix(choix), choixFait: ""}]).slice(-24)
        var total = m.reduce((n, x) => n + x.texte.length, 0)
        while (total > 48000 && m.length > 1) total -= m.shift().texte.length
        messages = m
    }
    // texte : un choix cliqué sous une réponse (envoyé tel quel, le brouillon reste) ; sinon le brouillon
    function envoyer(texte) {
        var duBrouillon = typeof texte !== "string"
        var q = (duBrouillon ? brouillon : texte).trim()
        if (enCours || ecritureReglagesEnCours || !q) return
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
        if (duBrouillon) brouillon = ""
        requete.stdinEnabled = true
        requete.running = true
        demarrage.restart()
    }
    function terminer() {
        if (!enCours || !sortieFinie || !processusFini) return
        demarrage.stop()
        var r = null
        try { r = JSON.parse(reponse) } catch (_) {}
        var estReset = question.startsWith("/reset") || question.startsWith("/clear") || question.startsWith("/nouveau")
        if (code === 0 && r && r.ok === true && typeof r.text === "string" && r.text.length) {
            if (estReset) messages = []
            ajouter("assistant", r.text.slice(0, 16000) + (r.truncated ? Reglages.t("\n\n[Réponse abrégée dans l’île]", "\n\n[Answer shortened in the island]") : ""), r.choices)
            reponseRecente = true
            // Réponse de JARVIS, ou de l'IA du bureau (le champ engine) : la suite part vers la même
            a.suiteParIA = typeof r.engine === "string" && r.engine !== ""
            a.nomChat = a.suiteParIA ? r.engine : "JARVIS"; if (!a.suiteParIA) a.agentChat = "assistant"
            finReponse.restart()
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
    // Un clic sur un choix du message num : envoyé comme un message tapé, puis ce message ne propose plus rien
    function choisir(num, libelle) {
        var m = messages.find(x => x.num === num)
        if (!m || m.choixFait || m.choix.indexOf(libelle) < 0 || enCours || ecritureReglagesEnCours) return
        envoyer(libelle)
        if (enCours) messages = messages.map(x => x.num === num ? Object.assign({}, x, {choixFait: libelle}) : x)
    }
    function effacer() { if (!enCours) { messages = []; erreur = "" } }
    // Conversation reprise depuis le cockpit (issue #9) : le chat repart de l'échange renvoyé par le serveur (history :
    // [{prompt, response}]) au lieu de rester vide ; la suite part vers JARVIS, qui tient cette conversation
    function chargerHistorique(historique) {
        if (enCours) return
        messages = []; erreur = ""
        var h = Array.isArray(historique) ? historique : []
        for (let i = 0; i < h.length; i++) {
            if (!h[i] || typeof h[i] !== "object") continue
            let q = String(h[i].prompt || "").slice(0, 4000), r = String(h[i].response || "").slice(0, 16000)
            if (q) ajouter("vous", q)
            if (r) ajouter("assistant", r)
        }
        suiteParIA = false; nomChat = "JARVIS"; agentChat = "assistant"
    }
    function resetSession() {
        if (enCours || reglagesEnCours) return
        brouillon = "/reset"
        envoyer()
    }
    // La fenêtre « Connexion JARVIS » (nc-assistant configurer l'ouvre dans la session graphique)
    function configurer() { Quickshell.execDetached([bin + "nc-assistant", "configurer"]) }
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
            // L'historique sert quand une autre IA que JARVIS répond (pas connecté, ou choisie à la main) : borné
            // pour tenir dans la ligne lue par nc-assistant
            var h = [], total = 0
            for (let i = a.messages.length - 2; i >= 0 && h.length < 12; i--) {
                let t = a.messages[i].texte.slice(0, 3000)
                if ((total += t.length) > 16000) break
                h.unshift({role: a.messages[i].role === "vous" ? "user" : "assistant", texte: t})
            }
            write(JSON.stringify({session_id: a.session, question: a.question, historique: h, ia_du_bureau: a.suiteParIA}) + "\n")
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

// « Que se passe-t-il ? » dans le Spotlight (Recherche.qml) : le bilan du bureau, l'explication de l'IA, les réparations.
//   1. nc-diag --json --rapide : le bilan (constats ! et ✗, résumé simple, table des réparations permises), ≈ 1 s
//   2. s'il y a quelque chose à dire et que l'IA est permise : nc-ia diagnostic --json - (le bilan sur l'entrée
//      standard), dont le résumé remplace celui de nc-diag ; Échap la coupe, le bilan reste
//   3. chaque réparation seulement avec Entrée ou un clic : nc-diag reparer ID --json, un ID venu de la table de nc-diag
//      et rien d'autre (jamais une commande écrite par l'IA) ; « Tout réparer » les fait l'une après l'autre, celles qui
//      ferment l'île en dernier
// Les réparations ne passent pas par l'IA : elles marchent même avec IA_MODE=non ou IA_ACTIONS=non.
// Fichier à part (et pas un « component » dans Recherche.qml) : le rechargement à chaud de qs ne connaîtrait pas le type.
import QtQuick
import Quickshell
import Quickshell.Io

Item {
    id: d
    visible: false
    // "" : rien de demandé ; "verif" : nc-diag vérifie ; "bilan" : le bilan est là ; "erreur" : nc-diag n'a pas répondu
    property string etape: ""
    property var bilan: null                 // la sortie de nc-diag --json --rapide
    property string resume: ""               // celui de nc-diag, puis celui de l'IA (et son conseil)
    property string source: ""               // "diag", "ia" ou "sans_ia" : d'où vient le résumé affiché
    property string ia: ""                   // l'IA qui a expliqué, et son logo (Etincelle)
    property string agent: "claude"
    property var ordre: []                   // les ID de réparation proposés, dans l'ordre affiché (ferme_ile en dernier)
    property var faits: ({})                 // ID → { ok, deja, texte } une fois la réparation faite (ou ratée)
    property string enCours: ""              // l'ID que nc-diag répare en ce moment
    property var file: []                    // « Tout réparer » : les ID qui attendent leur tour
    property bool iaPermise: false           // donné par le Spotlight : l'IA n'est ni coupée ni absente
    readonly property bool iaEnCours: explique.running
    readonly property bool reparationEnCours: reparateur.running || enCours !== "" || file.length > 0
    signal change()                          // de quoi refaire les lignes du Spotlight

    function t(fr, en) { return Reglages.t(fr, en) }
    // La table de nc-diag (un objet ID → { libelle, detail, danger, ferme_ile }) : la seule source des ID permis
    function table() { return bilan && bilan.reparations && typeof bilan.reparations === "object" && !Array.isArray(bilan.reparations) ? bilan.reparations : ({}) }
    function permis(id) { return typeof id === "string" && Object.prototype.hasOwnProperty.call(table(), id) }
    function fermeIle(id) { return permis(id) && table()[id].ferme_ile === true }
    function constats() { return bilan && Array.isArray(bilan.constats) ? bilan.constats : [] }
    // Les ID d'abord dans l'ordre donné, sans doublon ni ID inconnu, ceux qui ferment l'île à la fin
    function ranger(ids) {
        let vus = {}, l = []
        ids.forEach(id => { if (permis(id) && !vus[id]) { vus[id] = true; l.push(id) } })
        return l.filter(id => !fermeIle(id)).concat(l.filter(id => fermeIle(id)))
    }
    function restantes() { return ordre.filter(id => !(faits[id] && faits[id].ok)) }

    function lancer() {
        if (verif.running) return
        annuler()
        bilan = null; resume = ""; source = ""; ia = ""; agent = "claude"; ordre = []; faits = ({})
        etape = "verif"
        verif.running = true
        change()
    }
    // Échap ou une autre saisie : la vérification et l'IA s'arrêtent ; une réparation commencée va jusqu'au bout,
    // celles qui attendaient ne se font pas
    function annuler() {
        file = []
        if (explique.running) explique.running = false
        if (verif.running) { etape = ""; verif.running = false }
    }
    function couperIA() { if (explique.running) { explique.running = false; change() } }
    function reparer(id) {
        if (!permis(id) || ordre.indexOf(id) < 0 || (faits[id] && faits[id].ok) || reparateur.running || enCours !== "") return
        enCours = id
        reparateur.command = [Etat.bin + "nc-diag", "reparer", id, "--json"]
        reparateur.running = true
        change()
    }
    function suivante() {
        // Une qui ne part pas (faite entre-temps, ou plus proposée) est sautée
        while (file.length > 0 && enCours === "") {
            let id = file[0]
            file = file.slice(1)
            reparer(id)
        }
        change()
    }
    function toutReparer() {
        if (reparateur.running || enCours !== "") return
        let l = ranger(restantes())
        if (!l.length) return
        file = l.slice(1)
        reparer(l[0])
    }

    Process {
        id: verif
        command: [Etat.bin + "nc-diag", "--json", "--rapide"]
        stdout: StdioCollector { id: sortieVerif }
        stderr: StdioCollector { id: erreurVerif }
        onExited: code => {
            if (d.etape !== "verif") return                  // arrêtée (Échap, autre saisie) : rien à montrer
            let b = null
            try { b = JSON.parse(sortieVerif.text) } catch (e) {}
            if (!b || typeof b !== "object" || !Array.isArray(b.constats)) {
                d.etape = "erreur"
                d.resume = erreurVerif.text.trim().split("\n").pop() || d.t("nc-diag n'a pas pu vérifier le bureau.", "nc-diag couldn't check the desktop.")
                d.change()
                return
            }
            d.bilan = b
            d.resume = String(b.resume || "")
            d.source = "diag"
            let ids = []
            d.constats().forEach(c => (Array.isArray(c.reparations) ? c.reparations : []).forEach(id => ids.push(id)))
            d.ordre = d.ranger(ids)
            d.etape = "bilan"
            // L'IA seulement s'il y a quelque chose à expliquer ; le bilan est déjà affiché pendant ce temps
            if (d.iaPermise && d.constats().length > 0) {
                explique.envoi = sortieVerif.text
                explique.stdinEnabled = true
                explique.running = true
            }
            d.change()
        }
    }
    Process {
        id: explique
        property string envoi: ""
        command: [Etat.bin + "nc-ia", "diagnostic", "--json", "-"]
        // Comme « demandeur » dans Recherche.qml : le bilan écrit au démarrage, puis l'entrée standard fermée
        onStarted: if (stdinEnabled) { write(envoi); envoi = ""; stdinEnabled = false }
        stdout: StdioCollector { id: sortieIA }
        onExited: code => {
            let r = null
            try { r = JSON.parse(sortieIA.text) } catch (e) {}
            if (r && typeof r === "object" && d.bilan) {
                if (r.source === "ia" && typeof r.resume === "string" && r.resume.trim() !== "") {
                    d.resume = r.resume.trim() + (typeof r.conseil === "string" && r.conseil.trim() !== "" ? "\n\n" + r.conseil.trim() : "")
                    d.source = "ia"
                    d.ia = String(r.ia || "")
                    d.agent = String(r.agent || "") || "claude"
                    // L'ordre de l'IA d'abord, parmi les ID de nc-diag seulement ; les autres restent proposés après
                    let siennes = (Array.isArray(r.reparations) ? r.reparations : []).filter(id => d.ordre.indexOf(id) >= 0)
                    d.ordre = d.ranger(siennes.concat(d.ordre))
                } else d.source = "sans_ia"
            }
            d.change()
        }
    }
    Process {
        id: reparateur
        stdout: StdioCollector { id: sortieRep }
        stderr: StdioCollector { id: erreurRep }
        property bool suite: false               // la dernière a marché : la suivante de « Tout réparer » peut partir
        // Le code de sortie arrive avant la fin de running : la suivante part une fois running vraiment faux
        // (et les lignes se refont un instant après : reparationEnCours ne voit running faux qu'après la notification)
        onRunningChanged: if (!running) { Qt.callLater(d.change); if (suite) { suite = false; Qt.callLater(d.suivante) } }
        onExited: code => {
            let id = d.enCours, r = null
            try { r = JSON.parse(sortieRep.text) } catch (e) {}
            if (!r || typeof r !== "object") r = {}
            // nc-diag reparer --json : { id, libelle, resultat: fait | deja | echec | refuse, ferme_ile, texte } ; code 0 / 0 / 1 / 2
            let etat = String(r.resultat || "")
            let deja = etat === "deja"
            let ok = etat !== "" ? (etat === "fait" || deja) : code === 0
            let texte = String(r.texte || "").trim()
                        || (code === 0 ? "" : erreurRep.text.trim().split("\n").pop())
                        || (code === 2 ? d.t("Refusée par nc-diag", "Refused by nc-diag") : "")
            let f = Object.assign({}, d.faits)
            f[id] = { ok: ok || deja, deja: deja, texte: texte }
            d.faits = f
            // La suivante de « Tout réparer » (pas après un échec : le bilan dit ce qui reste)
            if (d.file.length > 0 && (ok || deja)) reparateur.suite = true
            else d.file = []
            d.enCours = ""
            d.change()
        }
    }
}

pragma Singleton
// État du Cloud JARVIS pour le panneau CloudPanneau.qml. Tout passe par `nc-cloud --json` (argv liste, une ligne JSON par
// événement) : aucun appel réseau depuis le QML, et aucun appel tant que le panneau est fermé.
//   - actif : CLOUD_JARVIS=oui ; associe : appareil.json présent sur ce PC (lu sur place, relu à chaque ouverture) ;
//   - sans actif ou sans associe : rien n'est lancé, le panneau dit quoi faire ;
//   - file FIFO : jamais deux nc-cloud en même temps ; la page du dossier est relue après chaque action qui le change ;
//   - les ids et révisions viennent toujours d'une page du serveur, jamais d'un texte tapé ;
//   - chaque action n'est proposée que si le serveur annonce sa capacité (features de nc-cloud etat).
import QtQuick
import Quickshell
import Quickshell.Io

Singleton {
    id: c

    readonly property string bin: Quickshell.env("HOME") + "/.local/bin/"
    readonly property string fichierAppareil: (Quickshell.env("XDG_STATE_HOME") || Quickshell.env("HOME") + "/.local/state") + "/nc-cloud/appareil.json"
    readonly property bool actif: Reglages.val("CLOUD_JARVIS", "non") === "oui"
    property bool associe: false
    property bool panneauOuvert: false            // posé par CloudPanneau.qml
    signal ouvrirPanneau()

    property var chemin: [{ id: "root", nom: Reglages.t("Cloud", "Cloud") }]   // du dossier racine au dossier courant
    readonly property string dossier: chemin[chemin.length - 1].id
    property var entrees: []
    property string suite: ""
    property bool lu: false
    property var etat: ({})
    property var features: ({})
    property string message: ""
    property string erreur: ""
    property string aRemplacer: ""                 // id d'un fichier dont la destination existe déjà (conflit au téléchargement)
    property string selection: ""                  // id de l'entrée choisie d'un clic : ses actions s'affichent
    property var deplacement: null                 // l'entrée à déplacer : on parcourt les dossiers, puis « Déplacer ici »
    property var apercu: null                      // {id, files, directories, size, tree} : aperçu d'un dossier avant sa suppression
    signal redemander(string id)                   // le dossier a changé depuis l'aperçu : la question revient sur sa ligne
    readonly property bool peutDeplacer: features.entry_move === true
    readonly property bool peutSupprimerDossier: features.directory_delete === true && features.delete_preview === true
    function peutSupprimer(e) {
        return !!e && !!e.revision && (e.kind === "file" ? (features.file_delete === true || features.directory_delete === true)
                                                       : peutSupprimerDossier)
    }
    property var enCours: null                     // {args, quoi, id}
    property var suites: []
    readonly property bool occupe: enCours !== null      // posé avant le lancement, vidé à la fin

    function relireAssociation() { appareil.reload() }

    onPanneauOuvertChanged: if (panneauOuvert) {
        relireAssociation()
        message = ""; erreur = ""; aRemplacer = ""; selection = ""; deplacement = null; apercu = null
    }
    // Appelée quand l'association est connue (après la lecture du fichier) : état et première page, une fois par ouverture
    function demarrer() {
        if (!panneauOuvert || !actif || !associe) return
        chemin = [chemin[0]]; entrees = []; suite = ""; lu = false
        lancer(["etat"], "etat")
        lister(false)
    }

    function lancer(args, quoi, id) {
        if (!actif || !associe) return
        var t = { args: args, quoi: quoi, id: id || "" }
        if (enCours !== null) { suites = suites.concat([t]); return }
        enCours = t
        proc.command = [bin + "nc-cloud", "--json"].concat(args)
        proc.running = true
    }
    function lister(plus) { lancer(plus && suite ? ["lister", "--suite=" + suite, "--", dossier] : ["lister", "--", dossier], plus ? "suite" : "page") }
    function aller(e) {
        if (!e || e.kind !== "directory" || occupe) return
        if (deplacement && deplacement.id === e.id) return          // jamais dans le dossier qu'on déplace
        chemin = chemin.concat([{ id: e.id, nom: e.name }]); entrees = []; suite = ""; lu = false; selection = ""; apercu = null
        lister(false)
    }
    function remonter(n) {
        if (occupe || n < 0 || n >= chemin.length - 1) return
        chemin = chemin.slice(0, n + 1); entrees = []; suite = ""; lu = false; selection = ""; apercu = null; lister(false)
    }
    function choisir(e) { if (e) { selection = e.id; if (apercu && apercu.id !== e.id) apercu = null } }
    // Double-clic : un dossier, on y entre ; un fichier, une copie privée ouverte par l'application par défaut
    function ouvrirEntree(e) {
        if (!e || occupe) return
        if (e.kind === "directory") aller(e)
        else if (e.kind === "file") lancer(["ouvrir", "--dossier=" + dossier, "--", e.id], "ouvrir", e.id)
    }
    function creerFichier(nom) {
        nom = String(nom || "").trim()
        if (nom !== "") lancer(["creer", "--", dossier, nom], "creer")
    }
    function renommer(e, nom) {
        nom = String(nom || "").trim()
        if (!e || !peutDeplacer || !e.revision || nom === "" || nom === e.name) return
        lancer(["renommer", "--revision=" + e.revision, "--", e.id, nom], "renommer", e.id)
    }
    function commencerDeplacement(e) { if (e && peutDeplacer && e.revision) { deplacement = e; selection = "" } }
    // « Déplacer ici » : pas dans son propre dossier (rien ne change), ni dans lui-même ou un de ses sous-dossiers
    readonly property bool deplacementPossible: !!deplacement && dossier !== deplacement.parent
        && !chemin.some(x => x.id === deplacement.id)
    function deplacerIci() {
        if (!deplacementPossible) return
        var e = deplacement
        deplacement = null
        lancer(["deplacer", "--revision=" + e.revision, "--vers=" + dossier, "--", e.id], "deplacer", e.id)
    }
    // Un dossier : l'aperçu d'abord (ce que la suppression retirerait), la question ensuite ; un fichier : la question directe
    function demanderApercu(e) {
        apercu = null
        if (e && e.kind === "directory" && peutSupprimerDossier) lancer(["apercu", "--", e.id], "apercu", e.id)
    }
    function actualiser() { if (!occupe) { entrees = []; suite = ""; lu = false; lancer(["etat"], "etat"); lister(false) } }
    function creerDossier(nom) {
        nom = String(nom || "").trim()
        if (nom !== "") lancer(["dossier", "--", dossier, nom], "dossier")
    }
    function telecharger(e, remplacer) {
        if (!e || e.kind !== "file") return
        aRemplacer = ""
        lancer(["telecharger", "--dossier=" + dossier].concat(remplacer ? ["--remplacer"] : [], ["--", e.id]), "telecharger", e.id)
    }
    // Seulement après la question du panneau ; un dossier, seulement avec l'arbre de SON aperçu confirmé
    function supprimer(e) {
        if (!peutSupprimer(e)) return
        if (e.kind === "directory") {
            if (!apercu || apercu.id !== e.id || !/^[0-9a-f]{64}$/.test(apercu.tree)) return
            var arbre = apercu.tree
            apercu = null
            lancer(["supprimer", "--revision=" + e.revision, "--recursif", "--arbre=" + arbre, "--", e.id], "supprimer", e.id)
        } else lancer(["supprimer", "--revision=" + e.revision, "--", e.id], "supprimer", e.id)
    }

    function ligne(texte) {
        var d
        try { d = JSON.parse(texte) } catch (x) { return }
        if (!d || typeof d !== "object") return
        var q = enCours ? enCours.quoi : ""
        if (d.evenement === "etat") { etat = d.etat || ({}); features = d.features || ({}) }
        else if (d.evenement === "page") {
            // Seuls les ids sûrs (root ou 32 hex) : un id qui commencerait par un tiret serait lu comme une option
            var l = Array.isArray(d.entries) ? d.entries.filter(x => x && typeof x.id === "string" && /^(root|[0-9a-f]{32})$/.test(x.id)
                                                                     && typeof x.name === "string") : []
            entrees = q === "suite" ? entrees.concat(l) : l
            suite = typeof d.next_cursor === "string" ? d.next_cursor : ""
            lu = true
        }
        else if (d.evenement === "apercu" && q === "apercu" && d.entree && d.entree.id === enCours.id) {
            var n = x => typeof x === "number" && x >= 0 ? x : -1
            if (n(d.files) >= 0 && n(d.directories) >= 0 && n(d.size) >= 0 && /^[0-9a-f]{64}$/.test(String(d.tree_revision)))
                apercu = { id: enCours.id, files: d.files, directories: d.directories, size: d.size, tree: d.tree_revision }
        }
        else if (d.evenement === "erreur") {
            erreur = String(d.message || Reglages.t("Erreur.", "Error.")).slice(0, 300)
            if (q === "telecharger" && d.code === 6) aRemplacer = enCours.id
            // Le dossier a changé depuis l'aperçu : rien n'est supprimé ; nouvel aperçu (après la page relue), nouvelle question
            if (q === "supprimer" && d.erreur === "tree_changed") {
                suites = [{ args: ["apercu", "--", enCours.id], quoi: "apercu", id: enCours.id }].concat(suites)
                redemander(enCours.id)
            }
            if (d.code === 4) associe = false
        }
        else if (typeof d.message === "string" && d.message !== "") { message = d.message.slice(0, 300); erreur = "" }
    }

    FileView {
        id: appareil
        path: c.fichierAppareil
        printErrors: false
        watchChanges: false
        onLoaded: { c.associe = true; c.demarrer() }
        onLoadFailed: c.associe = false
    }
    Process {
        id: proc
        stdout: SplitParser { onRead: data => c.ligne(data) }
        onExited: code => {
            var fini = c.enCours
            c.enCours = null
            // Le dossier a changé : sa page est relue avant la suite de la file
            if (fini && ["dossier", "supprimer", "creer", "renommer", "deplacer"].indexOf(fini.quoi) >= 0
                && (code === 0 || code === 6))
                c.suites = [{ args: ["lister", "--", c.dossier], quoi: "page", id: "" }].concat(c.suites)
            if (c.suites.length > 0) {
                var s = c.suites[0]
                c.suites = c.suites.slice(1)
                c.lancer(s.args, s.quoi, s.id)
            }
        }
    }
}

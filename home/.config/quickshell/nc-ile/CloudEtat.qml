pragma Singleton
// État du Cloud JARVIS pour le panneau CloudPanneau.qml. Tout passe par `nc-cloud --json` (argv liste, une ligne JSON par
// événement) : aucun appel réseau depuis le QML, et aucun appel tant que le panneau est fermé.
//   - actif : CLOUD_JARVIS=oui ; associe : appareil.json présent sur ce PC (lu sur place, relu à chaque ouverture) ;
//   - sans actif ou sans associe : rien n'est lancé, le panneau dit quoi faire ;
//   - file FIFO : jamais deux nc-cloud en même temps ; la page du dossier est relue après chaque action qui le change ;
//   - les ids et révisions viennent toujours d'une page du serveur, jamais d'un texte tapé ;
//   - chaque action n'est proposée que si le serveur annonce sa capacité (features de nc-cloud etat) ;
//   - envois : des fichiers reçus (dépôt sur l'île, « Importer des fichiers… »), rien ne part avant « Envoyer ici » ;
//     un seul nc-cloud deposer à la fois (procEnvoi, à part de la file) ; fermer le panneau ne l'arrête pas.
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

    // ── Envois ──
    readonly property int maxFichiers: 8
    property var recus: []                         // chemins locaux reçus, 8 au plus : rien ne part avant « Envoyer ici »
    property string recusRefus: ""                 // ce qui a été écarté (pas un fichier local, au-delà de 8)
    // [{fichier, nom, dans, etat, envoye, taille, message, actuel, fin}] ; etat : attente, en_cours, publie, conflit,
    // interrompu, annule, echec, refuse
    property var envois: []
    property var lotEnCours: null                  // {args, fichiers, cible} : le nc-cloud deposer ou reprendre en cours
    property var lots: []
    readonly property bool envoie: lotEnCours !== null
    readonly property var termines: ["publie", "annule", "echec", "refuse"]
    readonly property bool choixOuvert: procChoix.running
    property string choixErreur: ""
    property bool annulation: false                // Annuler demandé : la fin du lot vaut « annulé », même tué avant ses signaux

    function relireAssociation() { appareil.reload() }

    // Des adresses déposées ou choisies : seulement des fichiers locaux (file:///), sans doublon, 8 au plus. Une liste
    // vide (sélecteur annulé) garde la sélection précédente
    function recevoir(urls) {
        var l = [], ecartes = 0
        for (var u of urls || []) {
            var t = String(u), chemin = ""
            try { chemin = t.startsWith("file:///") ? decodeURIComponent(t.slice(7)) : "" } catch (x) { chemin = "" }
            if (chemin === "" || /[\x00-\x1f]/.test(chemin)) { ecartes++; continue }
            if (l.indexOf(chemin) < 0) l.push(chemin)
        }
        if (l.length > maxFichiers) { ecartes += l.length - maxFichiers; l = l.slice(0, maxFichiers) }
        if (l.length > 0) recus = l
        recusRefus = ecartes ? Reglages.t(ecartes + " écarté(s) : " + maxFichiers + " fichiers locaux au plus.",
                                          ecartes + " left out: " + maxFichiers + " local files at most.") : ""
        return l.length > 0
    }
    function viderRecus() { recus = []; recusRefus = "" }
    function choisirFichiers() {
        if (!actif || !associe || procChoix.running) return
        choixErreur = ""
        procChoix.command = [bin + "nc-cloud", "--json", "choisir"]
        procChoix.running = true
    }
    function envoyerIci() {
        if (!actif || !associe || recus.length === 0) return
        var n = recus.map(f => ({ fichier: f, nom: f.slice(f.lastIndexOf("/") + 1), dans: dossier, etat: "attente", envoye: 0,
                                  taille: 0, message: "", actuel: null, fin: 0 }))
        envois = envois.concat(n)
        lancerLot(["deposer", "--dans=" + dossier, "--"].concat(recus), recus, "")
        viderRecus()
    }
    function lancerLot(args, fichiers, cible) {
        var t = { args: args, fichiers: fichiers, cible: cible }
        if (lotEnCours !== null) { lots = lots.concat([t]); return }
        lotEnCours = t
        procEnvoi.command = [bin + "nc-cloud", "--json"].concat(args)
        procEnvoi.running = true
    }
    // SIGTERM : nc-cloud annule le fichier en cours sur le serveur ; les lots en attente sont abandonnés
    function annulerEnvois() {
        for (var t of lots) for (var f of t.fichiers) changer(trouverEnvoi(f), { etat: "annule", fin: Date.now() })
        lots = []
        if (procEnvoi.running) { annulation = true; procEnvoi.running = false }
    }
    // Conflit : conserver les deux, remplacer (la révision vue dans la réponse du serveur), ou annuler (rien ne part)
    // i : l'index dans envois (le modelData d'un Repeater est une copie, jamais l'objet de la liste)
    function resoudre(i, choix) {
        var e = envois[i]
        if (!e || e.etat !== "conflit") return
        if (choix === "annuler") { changer(i, { etat: "annule", fin: Date.now(), message: "" }); return }
        var rev = e.actuel && typeof e.actuel.revision === "string" ? e.actuel.revision : ""
        if (choix === "remplacer" && !/^[!-~]{1,256}$/.test(rev)) return
        changer(i, { etat: "attente", message: "", envoye: 0 })
        lancerLot(["deposer", "--dans=" + e.dans, "--si-existe=" + (choix === "remplacer" ? "remplacer:" + rev : "garder"), "--", e.fichier],
                  [e.fichier], "")
    }
    // Reprendre / vérifier : la liste locale des envois interrompus, puis `reprendre CLE` de celui de ce fichier
    function reprendre(i) {
        var e = envois[i]
        if (!e || e.etat !== "interrompu") return
        changer(i, { etat: "attente", message: "" })
        lancerLot(["reprendre"], [e.fichier], e.fichier)
    }
    function effacerTermines() { envois = envois.filter(e => termines.indexOf(e.etat) < 0) }
    function trouverEnvoi(f) {
        // nc-cloud donne le chemin résolu : le chemin exact, sinon le nom, du plus récent qui n'est pas terminé
        f = String(f || ""); var nom = f.slice(f.lastIndexOf("/") + 1)
        for (var passe = 0; passe < 2; passe++)
            for (var i = envois.length - 1; i >= 0; i--)
                if (termines.indexOf(envois[i].etat) < 0 && (passe === 0 ? envois[i].fichier === f : envois[i].nom === nom)) return i
        return -1
    }
    function changer(i, champs) {
        if (i < 0) return
        var l = envois.slice(); l[i] = Object.assign({}, l[i], champs); envois = l
    }
    function ligneEnvoi(texte) {
        var d
        try { d = JSON.parse(texte) } catch (x) { return }
        if (!d || typeof d !== "object") return
        var lot = lotEnCours, msg = String(d.message || "").slice(0, 300)
        if (d.evenement === "envois" && lot && lot.cible !== "") {
            // Le manifeste garde le chemin résolu : le chemin exact, sinon le même nom de fichier
            var l = (Array.isArray(d.envois) ? d.envois : []).filter(x => x && typeof x.fichier === "string" && /^[A-Za-z0-9_-]{16,128}$/.test(String(x.cle)))
            var base = x => x.slice(x.lastIndexOf("/") + 1)
            var m = l.find(x => x.fichier === lot.cible) || l.find(x => base(x.fichier) === base(lot.cible))
            lot.suite = m ? ["reprendre", "--", m.cle] : null
            if (!m) changer(trouverEnvoi(lot.cible), { etat: "echec", fin: Date.now(),
                message: Reglages.t("Rien à reprendre sur ce PC : regarde dans le dossier, puis envoie-le à nouveau s'il manque.",
                                    "Nothing to resume on this PC: look in the folder, then upload it again if it is missing.") })
            return
        }
        var i = trouverEnvoi(d.fichier)
        if (d.evenement === "progression")
            changer(i, { etat: "en_cours", envoye: Number(d.envoye) || 0, taille: Number(d.taille) || 0 })
        else if (d.evenement === "conflit")
            changer(i, { etat: "conflit", message: msg, actuel: d.actuel && typeof d.actuel === "object" ? d.actuel : null })
        else if (d.evenement === "resultat" && termines.indexOf(d.etat) >= 0) {
            // Une seule relecture par envoi : une ligne publiée est terminée, trouverEnvoi ne la rend plus
            changer(i, { etat: d.etat, message: msg, fin: Date.now() })
            if (d.etat === "publie" && i >= 0) actualiserApresEnvoi()
        }
        else if (d.evenement === "erreur") {
            // Toute la commande s'arrête : hors ligne ou coupure (3, 9), le manifeste reste et l'envoi se reprend
            var reprise = d.code === 3 || d.code === 9
            for (var f of lot ? lot.fichiers : []) {
                var j = trouverEnvoi(f)
                if (j >= 0) changer(j, reprise ? { etat: "interrompu", message: msg } : { etat: "echec", message: msg, fin: Date.now() })
            }
            if (d.code === 4) associe = false
        }
        else if (d.evenement === "info") changer(i, { message: msg })
    }
    // Un envoi vu publié pour la première fois : dossier affiché et quota relus, une fois (panneau fermé : relus à l'ouverture)
    function actualiserApresEnvoi() {
        if (!panneauOuvert || suites.some(t => t.quoi === "page")) return
        lancer(["etat"], "etat")
        lister(false)
    }
    function finLot(code) {
        var lot = lotEnCours
        lotEnCours = null
        if (annulation) { code = 8; annulation = false }
        for (var f of lot && !lot.suite ? lot.fichiers : []) {
            var j = trouverEnvoi(f)
            if (j >= 0 && (envois[j].etat === "attente" || envois[j].etat === "en_cours"))
                changer(j, code === 8 ? { etat: "annule", fin: Date.now() }
                          : code === 3 || code === 9 ? { etat: "interrompu" }
                          : { etat: "echec", fin: Date.now(), message: envois[j].message || Reglages.t("Envoi non confirmé.", "Upload not confirmed.") })
        }
        if (lot && lot.suite) { lancerLot(lot.suite, lot.fichiers, ""); return }
        if (lots.length > 0) { var t = lots[0]; lots = lots.slice(1); lancerLot(t.args, t.fichiers, t.cible); return }
        notifierFin()
    }
    function notifierFin() {
        var p = envois.filter(e => e.etat === "publie" && !e.notifie).length, autres = envois.filter(e => e.etat !== "publie" && termines.indexOf(e.etat) >= 0 && !e.notifie).length
        envois = envois.map(e => termines.indexOf(e.etat) >= 0 ? Object.assign({}, e, { notifie: true }) : e)
        if (p + autres === 0) return
        Quickshell.execDetached(["notify-send", "-a", "Cloud JARVIS", "-i", "folder-cloud", "--", "Cloud JARVIS",
            Reglages.t(p + " fichier(s) envoyé(s)" + (autres ? ", " + autres + " non envoyé(s)" : ""),
                       p + " file(s) uploaded" + (autres ? ", " + autres + " not uploaded" : ""))])
    }


    onPanneauOuvertChanged: if (panneauOuvert) {
        relireAssociation()
        message = ""; erreur = ""; aRemplacer = ""; selection = ""; deplacement = null; apercu = null; choixErreur = ""
    } else if (procChoix.running) procChoix.running = false      // le sélecteur se ferme avec le panneau (nc-cloud le referme)
    // Appelée quand l'association est connue (après la lecture du fichier) : état et première page, une fois par ouverture
    function demarrer() {
        if (!panneauOuvert || !actif || !associe) return
        chemin = [chemin[0]]; entrees = []; suite = ""; lu = false
        lancer(["etat"], "etat")
        lister(false)
        lancer(["reprendre"], "envois")          // la liste des envois interrompus : locale, sans réseau
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
        else if (d.evenement === "envois" && q === "envois") {
            // Envois interrompus de ce PC (après un redémarrage de l'île, une coupure) : une ligne « interrompu » chacun
            var nv = (Array.isArray(d.envois) ? d.envois : []).filter(x => x && typeof x.fichier === "string" && trouverEnvoi(x.fichier) < 0)
            envois = envois.concat(nv.map(x => ({ fichier: x.fichier, nom: String(x.nom || x.fichier.slice(x.fichier.lastIndexOf("/") + 1)),
                dans: "", etat: "interrompu", envoye: 0, taille: Number(x.taille) || 0, message: "", actuel: null, fin: 0 })))
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
        id: procEnvoi
        stdout: SplitParser { onRead: data => c.ligneEnvoi(data) }
        onExited: code => c.finLot(code)
    }
    Process {
        id: procChoix
        stdout: SplitParser { onRead: data => {
            var d
            try { d = JSON.parse(data) } catch (x) { return }
            if (d && d.evenement === "choisis" && Array.isArray(d.fichiers)) c.recevoir(d.fichiers)
            else if (d && d.evenement === "erreur") c.choixErreur = String(d.message || "").slice(0, 300)
        } }
    }
    // Les lignes terminées disparaissent seules après 24 h
    Timer {
        interval: 600000; repeat: true; running: c.envois.length > 0
        onTriggered: c.envois = c.envois.filter(e => !(c.termines.indexOf(e.etat) >= 0 && e.fin > 0 && Date.now() - e.fin > 86400000))
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

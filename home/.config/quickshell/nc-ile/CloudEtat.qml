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
    signal basculerPanneau()

    property var chemin: [{ id: "root", nom: Reglages.t("Cloud", "Cloud") }]   // du dossier racine au dossier courant
    readonly property string dossier: chemin[chemin.length - 1].id
    property var entrees: []
    property string suite: ""
    property bool lu: false
    property var etat: ({})
    property var features: ({})
    property bool fichiersPossible: false          // gi et le moteur WebDAV de GVfs présents (nc-cloud etat) : « Ouvrir dans Fichiers »
    function ouvrirFichiers() { if (fichiersPossible) lancer(["fichiers"], "fichiers") }
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
    property var recents: []                       // les 5 derniers fichiers envoyés ou ouverts par CE PC (nc-cloud recents, local)
    // Corbeille locale (nc-cloud corbeille) : une copie privée de chaque fichier supprimé d'ici, 24 h ; « Annuler »
    // pendant 20 s après la suppression, puis « Remettre » tant que la copie existe. Un fichier de plus de 500 Mio n'a
    // pas de copie (la question le dit avant) ; une copie ratée : rien n'est supprimé, la question revient « sans copie »
    property var corbeille: []
    property var annulable: null                  // { copie, nom } : la dernière suppression, dureeAnnuler ms
    property int dureeAnnuler: 20000
    property string sansCopie: ""                 // id dont la copie a échoué : la question suivante dit « sans copie »
    property string raisonSansCopie: ""           // et pourquoi (corbeille pleine…), en texte brut
    // Presse-papiers d'un PC à l'autre (nc-cloud presse) : toujours un aperçu, puis la confirmation de CE texte (son
    // empreinte) ; le texte ne passe que par la sortie de nc-cloud, jamais par un argv ni par console.log
    property var presse: null                     // { sens: "envoi" | "prise", apercu, caracteres, lignes, caches, retires, empreinte, id, revision }
    property string presseMessage: ""
    property bool presseIndispo: false            // wl-clipboard absent ou hors Wayland : boutons grisés
    readonly property real copieMax: 500 * 1024 * 1024
    function copiable(e) { return !!e && e.kind === "file" && typeof e.size === "number" && e.size <= copieMax }
    property string aRacine: ""                   // copie dont le dossier d'origine n'existe plus : « Remettre à la racine »
    function remettre(copie, racine) {
        if (!/^[0-9a-f]{32}$/.test(String(copie))) return
        annulable = null
        aRacine = ""
        lancer(["corbeille", "--remettre=" + copie].concat(racine ? ["--racine"] : []), "remettre", copie)
        lancer(["corbeille"], "corbeille")
    }
    // Une copie qui ne se remet pas depuis l'île (nom de fichier de secrets) : son dossier, ouvert par xdg-open (argv)
    readonly property string dossierCorbeille: (Quickshell.env("XDG_CACHE_HOME") || (Quickshell.env("HOME") + "/.cache")) + "/nc-cloud/corbeille/"
    function ouvrirCopie(copie, nom) {
        if (!/^[0-9a-f]{32}$/.test(String(copie)) || dossierCorbeille.charAt(0) !== "/") return
        Quickshell.execDetached(["xdg-open", dossierCorbeille + copie])
        // Le dossier montre « contenu » et « copie.json » : le nom d'origine est dit ici
        message = Reglages.t("Le fichier s'y appelle « contenu » ; son nom était « " + String(nom || "").slice(0, 240) + " ».",
                             "The file is named “contenu” there; its name was “" + String(nom || "").slice(0, 240) + "”.")
    }
    // Place utilisée, pour le centre de contrôle : lue SEULEMENT à son ouverture, au plus une fois par 10 minutes (gardée
    // en mémoire) ; aussi notée quand le panneau lit l'état. Hors ligne : la dernière valeur, marquée vieille
    property var quota: null
    property real quotaEssai: 0
    property bool quotaVieux: false
    readonly property string quotaTexte: quota ? tailleCourte(quota.utilise) + Reglages.t(" sur ", " of ") + tailleCourte(quota.total) : ""
    function tailleCourte(n) {
        var u = ["o", "Ko", "Mo", "Go", "To"], i = 0
        while (n >= 1024 && i < u.length - 1) { n /= 1024; i++ }
        return String(i === 0 || n >= 10 ? Math.round(n) : Math.round(n * 10) / 10).replace(".", Reglages.t(",", ".")) + " " + u[i]
    }
    function noterQuota(e) {
        if (e && typeof e.used_bytes === "number" && typeof e.quota_bytes === "number" && e.used_bytes >= 0 && e.quota_bytes > 0) {
            quota = { utilise: e.used_bytes, total: e.quota_bytes }; quotaVieux = false
        }
    }
    function lireQuota() {
        if (!actif || !associe || Date.now() - quotaEssai < 600000) return
        quotaEssai = Date.now()
        procQuota.running = true
    }
    property var examen: ({})                      // chemin -> {taille, cache, refus} : nc-cloud examiner, avant « Envoyer ici »
    readonly property bool examenPret: recus.length > 0 && recus.every(f => examen[f] !== undefined)
    readonly property bool recusCaches: recus.some(f => examen[f] && examen[f].cache && !examen[f].refus)
    readonly property var aEnvoyer: recus.filter(f => examen[f] && !examen[f].refus)
    readonly property string maison: Quickshell.env("HOME") || ""
    // Note : un texte glissé sur l'île, enregistré dans « Notes » par nc-cloud note, le texte par l'ENTRÉE STANDARD
    readonly property int noteMax: 65536
    property string note: ""
    property string noteRefus: ""
    property string noteMessage: ""
    readonly property bool noteEnCours: procNote.running
    function octetsUtf8(t) { var n = 0; for (const ch of t) { var c = ch.codePointAt(0); n += c < 0x80 ? 1 : c < 0x800 ? 2 : c < 0x10000 ? 3 : 4 } return n }
    function recevoirTexte(t) {
        t = String(t || "")
        if (t.trim() === "") return false
        noteMessage = ""
        if (octetsUtf8(t) > noteMax) { note = ""; noteRefus = Reglages.t("Texte trop long pour une note (64 Kio au plus) : rien n'est gardé.",
                                                                        "Text too long for a note (64 KiB at most): nothing kept."); return true }
        note = t; noteRefus = ""
        return true
    }
    function oublierNote() { note = ""; noteRefus = ""; noteMessage = "" }
    function enregistrerNote() {
        if (!actif || !associe || note === "" || procNote.running) return
        procNote.texte = note
        procNote.stdinEnabled = true
        procNote.command = [bin + "nc-cloud", "--json", "note"]
        procNote.running = true
    }
    function court(f) { return maison !== "" && f.startsWith(maison + "/") ? "~" + f.slice(maison.length) : f }
    // [{fichier, nom, dans, etat, envoye, taille, message, actuel, fin}] ; etat : attente, en_cours, publie, conflit,
    // interrompu, annule, echec, refuse
    property var envois: []
    property var lotEnCours: null                  // {args, fichiers, cible} : le nc-cloud deposer ou reprendre en cours
    property var lots: []
    readonly property bool envoie: lotEnCours !== null
    readonly property var termines: ["publie", "annule", "echec", "refuse", "inconnu"]
    readonly property bool choixOuvert: procChoix.running
    property string choixErreur: ""
    property bool annulation: false                // Annuler demandé : la fin du lot vaut « annulé », même tué avant ses signaux

    function relireAssociation() { appareil.reload() }
    function presseVoir() { presse = null; presseMessage = ""; lancer(["presse", "voir"], "presse") }
    function presseVoirCloud() { presse = null; presseMessage = ""; lancer(["presse", "voir-cloud"], "presse") }
    function presseAnnuler() { presse = null; presseMessage = "" }
    function presseConfirmer() {
        var p = presse
        presse = null
        if (!p) return                            // empreinte, id, révision : déjà vérifiés à la réception (ligne)
        if (p.sens === "envoi") lancer(["presse", "envoyer", "--empreinte=" + p.empreinte], "presse")
        else if (p.sens === "prise" && /^[A-Za-z0-9_]{1,128}$/.test(String(p.id)) && /^[!-~]{1,256}$/.test(String(p.revision)))
            lancer(["presse", "prendre", "--id=" + p.id, "--revision=" + p.revision, "--empreinte=" + p.empreinte], "presse")
    }

    // Un téléchargement fini (île, « téléchargé ») : envoyable s'il a un nom simple (ni « / », ni caché, ni « .. », ni
    // caractère de contrôle, ni fichier temporaire du navigateur) dans un dossier absolu. Il passe ensuite par l'examen
    // comme un fichier glissé, et rien ne part avant « Envoyer ici »
    function telechargementEnvoyable(dossier, nom) {
        var d = String(dossier || ""), n = String(nom || "")
        return actif && associe && d.charAt(0) === "/" && n !== "" && n.indexOf("/") < 0 && n.charAt(0) !== "."
               && !/[\x00-\x1f\x7f]/.test(n) && !/\.(part|crdownload|tmp)$/i.test(n)
    }
    function recevoirTelechargement(dossier, nom) {
        if (!telechargementEnvoyable(dossier, nom)) return false
        var chemin = (String(dossier).replace(/\/+$/, "") + "/" + nom).split("/").map(encodeURIComponent).join("/")
        return recevoir(["file://" + chemin])
    }

    // Des adresses déposées ou choisies : seulement des fichiers locaux (file:///), sans doublon, 8 au plus. Une liste
    // vide (sélecteur annulé) garde la sélection précédente
    function recevoir(urls) {
        var l = [], ecartes = 0
        for (var u of urls || []) {
            var t = String(u), chemin = ""
            try { chemin = t.startsWith("file:///") ? decodeURIComponent(t.slice(7)) : "" } catch (x) { chemin = "" }
            // Un chemin déjà normalisé, le même que celui que nc-cloud verra : ni « / » final ou double, ni « . », ni « .. »
            var segments = chemin.split("/").slice(1)
            if (chemin === "" || /[\x00-\x1f]/.test(chemin) || segments.some(x => x === "" || x === "." || x === "..")) { ecartes++; continue }
            if (l.indexOf(chemin) < 0) l.push(chemin)
        }
        if (l.length > maxFichiers) { ecartes += l.length - maxFichiers; l = l.slice(0, maxFichiers) }
        if (l.length > 0) { recus = l; examen = ({}); lancer(["examiner", "--"].concat(l), "examen") }
        recusRefus = ecartes ? Reglages.t(ecartes + " écarté(s) : " + maxFichiers + " fichiers locaux au plus.",
                                          ecartes + " left out: " + maxFichiers + " local files at most.") : ""
        return l.length > 0
    }
    function viderRecus() { recus = []; recusRefus = ""; examen = ({}) }
    function choisirFichiers() {
        if (!actif || !associe || procChoix.running) return
        choixErreur = ""
        procChoix.command = [bin + "nc-cloud", "--json", "choisir"]
        procChoix.running = true
    }
    function envoyerIci() {
        if (!actif || !associe || !examenPret || aEnvoyer.length === 0) return
        var partent = aEnvoyer
        var n = partent.map(f => ({ fichier: f, nom: f.slice(f.lastIndexOf("/") + 1), dans: dossier, etat: "attente", envoye: 0,
                                  taille: 0, message: "", actuel: null, fin: 0 }))
        envois = envois.concat(n)
        lancerLot(["deposer", "--dans=" + dossier, "--"].concat(partent), partent, "")
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
        if (lotEnCours) lotEnCours.suite = null          // une reprise annulée ne part pas après la liste
        if (procEnvoi.running) { annulation = true; procEnvoi.running = false }
    }
    // Conflit : conserver les deux, remplacer (la révision vue dans la réponse du serveur), ou annuler (rien ne part)
    // i : l'index dans envois (le modelData d'un Repeater est une copie, jamais l'objet de la liste)
    function resoudre(i, choix) {
        var e = envois[i]
        if (!e || e.etat !== "conflit") return
        if (choix === "annuler") { changer(i, { etat: "annule", fin: Date.now(), message: "" }); return }
        var rev = e.actuel && typeof e.actuel.revision === "string" ? e.actuel.revision : ""
        if (choix === "remplacer" && (!/^[!-~]{1,256}$/.test(rev) || e.actuel.kind === "directory")) return
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
        // Le chemin EXACT (nc-cloud rend le chemin donné, déjà normalisé des deux côtés), du plus récent pas terminé
        f = String(f || "")
        for (var i = envois.length - 1; i >= 0; i--)
            if (termines.indexOf(envois[i].etat) < 0 && envois[i].fichier === f) return i
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
            // Le chemin exact seulement : un manifeste du même nom peut venir d'un autre dossier
            var l = (Array.isArray(d.envois) ? d.envois : []).filter(x => x && typeof x.fichier === "string" && /^[A-Za-z0-9_-]{16,128}$/.test(String(x.cle)))
            var m = l.find(x => x.fichier === lot.cible)
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
            if (i < 0 && d.etat === "publie" && lot) lot.publieInconnu = true     // jamais « Échec » ensuite pour ce lot
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
        lancer(["recents"], "recents")
    }
    function finLot(code) {
        var lot = lotEnCours
        lotEnCours = null
        if (annulation) { code = 8; annulation = false }
        for (var f of lot && !lot.suite ? lot.fichiers : []) {
            var j = trouverEnvoi(f)
            // Sans résultat pour cette ligne : code 0, ou un « publié » vu sans ligne correspondante, ne valent jamais « Échec »
            if (j >= 0 && (envois[j].etat === "attente" || envois[j].etat === "en_cours"))
                changer(j, code === 8 ? { etat: "annule", fin: Date.now() }
                          : code === 3 || code === 9 ? { etat: "interrompu" }
                          : code === 0 || lot.publieInconnu ? { etat: "inconnu", fin: Date.now(),
                                message: Reglages.t("État inconnu : vérifie dans le dossier.", "Unknown state: check the folder.") }
                          : { etat: "echec", fin: Date.now(), message: envois[j].message || Reglages.t("Envoi non confirmé.", "Upload not confirmed.") })
        }
        if (lot && lot.suite) { lancerLot(lot.suite, lot.fichiers, ""); return }
        if (lots.length > 0) { var t = lots[0]; lots = lots.slice(1); lancerLot(t.args, t.fichiers, t.cible); return }
        notifierFin()
    }
    function notifierFin() {
        var p = envois.filter(e => e.etat === "publie" && !e.notifie).length
        var inconnus = envois.filter(e => e.etat === "inconnu" && !e.notifie).length
        var autres = envois.filter(e => e.etat !== "publie" && e.etat !== "inconnu" && termines.indexOf(e.etat) >= 0 && !e.notifie).length
        envois = envois.map(e => termines.indexOf(e.etat) >= 0 ? Object.assign({}, e, { notifie: true }) : e)
        if (p + autres + inconnus === 0) return
        Quickshell.execDetached(["notify-send", "-a", "Cloud JARVIS", "-i", "folder-cloud", "--", "Cloud JARVIS",
            Reglages.t(p + " fichier(s) envoyé(s)" + (inconnus ? ", " + inconnus + " à vérifier" : "") + (autres ? ", " + autres + " non envoyé(s)" : ""),
                       p + " file(s) uploaded" + (inconnus ? ", " + inconnus + " to check" : "") + (autres ? ", " + autres + " not uploaded" : ""))])
    }


    onPanneauOuvertChanged: if (panneauOuvert) {
        relireAssociation()
        message = ""; erreur = ""; aRemplacer = ""; selection = ""; deplacement = null; apercu = null; choixErreur = ""
        etat = ({})
    } else if (procChoix.running) procChoix.running = false      // le sélecteur se ferme avec le panneau (nc-cloud le referme)
    // Appelée quand l'association est connue (après la lecture du fichier) : état et première page, une fois par ouverture
    function demarrer() {
        if (!panneauOuvert || !actif || !associe) return
        chemin = [chemin[0]]; entrees = []; suite = ""; lu = false
        lancer(["etat"], "etat")
        lister(false)
        lancer(["reprendre"], "envois")          // la liste des envois interrompus : locale, sans réseau
        lancer(["recents"], "recents")           // les récents de ce PC : locaux, sans réseau
        lancer(["corbeille"], "corbeille")       // les copies gardées ici : locales, sans réseau
    }
    function ouvrirRecent(i) {
        var r = recents[i]
        if (!r || occupe) return
        lancer(["ouvrir", "--dossier=" + r.dossier, "--", r.id], "ouvrir", r.id)
        lancer(["recents"], "recents")           // relue après : une entrée qui n'existe plus en sort
    }
    function effacerRecents() { lancer(["recents", "--effacer"], "recents") }

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
        else if (e.kind === "file") { lancer(["ouvrir", "--dossier=" + dossier, "--", e.id], "ouvrir", e.id); lancer(["recents"], "recents") }
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
    // Déplacer e dans le dossier vers (« Déplacer ici », ou glissé sur un dossier de la liste ou sur ↑) : refus local
    // sur soi-même, dans son propre dossier (rien ne change), ou dans un dossier du chemin qui passe par lui ; le serveur
    // contrôle le reste. nc-cloud relit la révision du dossier de destination à chaque déplacement, et la page est relue
    // après : un déplacement vers le parent, puis un autre, part toujours de révisions à jour
    function deposable(e, vers) {
        return !!e && peutDeplacer && typeof e.revision === "string" && e.revision !== "" && e.id !== "root"
            && typeof vers === "string" && vers !== "" && vers !== e.id && vers !== e.parent && !chemin.some(x => x.id === e.id)
    }
    function deplacerVers(e, vers) {
        if (deposable(e, vers)) lancer(["deplacer", "--revision=" + e.revision, "--vers=" + vers, "--", e.id], "deplacer", e.id)
    }
    readonly property bool deplacementPossible: deposable(deplacement, dossier)
    function deplacerIci() {
        if (!deplacementPossible) return
        var e = deplacement
        deplacement = null
        deplacerVers(e, dossier)
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
        } else {
            var copie = copiable(e) && sansCopie !== e.id
            sansCopie = ""; raisonSansCopie = ""
            lancer(["supprimer", "--revision=" + e.revision, "--dossier=" + dossier].concat(copie ? ["--copie"] : [], ["--", e.id]), "supprimer", e.id)
        }
    }

    function ligne(texte) {
        var d
        try { d = JSON.parse(texte) } catch (x) { return }
        if (!d || typeof d !== "object") return
        var q = enCours ? enCours.quoi : ""
        if (d.evenement === "etat") { etat = d.etat || ({}); features = d.features || ({}); fichiersPossible = d.fichiers === true; noterQuota(d.etat) }
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
        else if (d.evenement === "recents" && q === "recents") {
            // Ids sûrs seulement (32 hex ; le dossier : root ou 32 hex), nom en texte brut, 5 au plus
            recents = (Array.isArray(d.recents) ? d.recents : []).filter(x => x && /^[0-9a-f]{32}$/.test(String(x.id))
                          && /^(root|[0-9a-f]{32})$/.test(String(x.dossier)) && typeof x.nom === "string").slice(0, 5)
                          .map(x => ({ id: x.id, nom: x.nom.slice(0, 240), dossier: x.dossier }))
        }
        else if (d.evenement === "examen" && q === "examen") {
            var ex = ({})
            for (var x of Array.isArray(d.fichiers) ? d.fichiers : [])
                if (x && typeof x.fichier === "string" && recus.indexOf(x.fichier) >= 0)
                    ex[x.fichier] = { taille: typeof x.taille === "number" ? x.taille : -1, cache: x.cache === true,
                                      refus: typeof x.refus === "string" ? x.refus.slice(0, 300) : "" }
            examen = ex
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
            if (q === "presse") { presseMessage = erreur; if (d.erreur === "outil") presseIndispo = true }
            if (q === "supprimer" && d.erreur === "copie") { sansCopie = enCours.id; raisonSansCopie = erreur; redemander(enCours.id) }
            if (q === "remettre" && d.erreur === "parent_absent") aRacine = enCours.id
            if (q === "supprimer" && d.erreur === "tree_changed") {
                suites = [{ args: ["apercu", "--", enCours.id], quoi: "apercu", id: enCours.id }].concat(suites)
                redemander(enCours.id)
            }
            if (d.code === 4) associe = false
        }
        else if (d.evenement === "presse" && q === "presse") {
            var n = x => typeof x === "number" && x >= 0 ? x : 0
            if ((d.sens === "envoi" || d.sens === "prise") && typeof d.apercu === "string" && /^[0-9a-f]{64}$/.test(String(d.empreinte)))
                presse = { sens: d.sens, apercu: d.apercu.slice(0, 201), caracteres: n(d.caracteres), lignes: n(d.lignes), caches: n(d.caches), retires: n(d.retires),
                           empreinte: d.empreinte, id: String(d.id || ""), revision: String(d.revision || "") }
            else if (typeof d.message === "string") presseMessage = d.message.slice(0, 300)
        }
        else if (d.evenement === "corbeille") {
            corbeille = (Array.isArray(d.copies) ? d.copies : []).filter(x => x && /^[0-9a-f]{32}$/.test(String(x.copie)) && typeof x.nom === "string")
                          .slice(0, 50).map(x => ({ copie: x.copie, nom: x.nom.slice(0, 240), taille: Number(x.taille) || 0,
                                                    remettable: x.remettable === true, abimee: x.abimee === true,
                                                    etat: ["doute", "supprime", "refuse"].indexOf(x.etat) >= 0 ? x.etat : "doute" }))
        }
        else if (typeof d.message === "string" && d.message !== "") {
            message = d.message.slice(0, 300); erreur = ""
            // « Annuler » seulement pour une suppression confirmée ; une copie « doute » ou « refuse » reste dans la corbeille
            if (q === "supprimer" && d.etat === "supprime" && d.copie_etat === "supprime" && /^[0-9a-f]{32}$/.test(String(d.copie))) {
                var sup = entrees.find(x => x.id === enCours.id)
                annulable = { copie: d.copie, nom: String(d.nom || "").slice(0, 240), remettable: !(sup && sup.sensible === true) }
                finAnnulable.restart()
                suites = suites.concat([{ args: ["corbeille"], quoi: "corbeille", id: "" }])
            }
        }
    }
    Timer { id: finAnnulable; interval: c.dureeAnnuler; onTriggered: c.annulable = null }

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
        id: procQuota
        property bool lu: false
        command: [c.bin + "nc-cloud", "--json", "etat"]
        onStarted: lu = false
        stdout: SplitParser { onRead: data => {
            var d
            try { d = JSON.parse(data) } catch (x) { return }
            if (d && d.evenement === "etat") { c.noterQuota(d.etat); procQuota.lu = true }
        } }
        onExited: code => { if (code !== 0 || !lu) c.quotaVieux = true }
    }
    Process {
        id: procNote
        property string texte: ""
        onStarted: { write(texte); stdinEnabled = false; texte = "" }
        stdout: SplitParser { onRead: data => {
            var d
            try { d = JSON.parse(data) } catch (x) { return }
            if (!d || typeof d.message !== "string") return
            if (d.evenement === "note") { c.note = ""; c.noteMessage = d.message.slice(0, 300) }
            else if (d.evenement === "erreur" || d.evenement === "conflit" || (d.evenement === "resultat" && d.etat !== "publie"))
                c.noteMessage = d.message.slice(0, 300)
        } }
        onExited: code => { if (code === 0) c.actualiserApresEnvoi() }
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
            if (fini && fini.quoi === "etat" && code !== 0) c.etat = ({})
            // Le dossier a changé : sa page est relue avant la suite de la file
            if (fini && ["dossier", "supprimer", "creer", "renommer", "deplacer", "remettre"].indexOf(fini.quoi) >= 0
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

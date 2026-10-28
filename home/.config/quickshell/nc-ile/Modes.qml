pragma Singleton
// Modes Concentration (réglage ILE_CONCENTRATION, nc-reglages → Île) : des profils NOMMÉS que tu crées (Travail, Nuit, Jeu…) et qui
// combinent seulement ce qui existe déjà : Ne pas déranger, un profil d'énergie de nc-energie, le fond du jour ou de la nuit,
// l'IA sur les notifications. Tout le travail est fait par la commande nc-modes (fichiers validés, écrits atomiquement, programmes
// lancés en argv) : l'île ne fait que la lancer SUR UN CLIC, puis poser Ne pas déranger (qui vit dans Notifs.qml) avec la valeur
// qu'elle renvoie. Aucun minuteur, aucun sondage : une lecture au démarrage de l'île et une après chaque action.
// Rien n'existe tant que tu n'as créé aucun mode : pas de pastille, pas de page dans la liste. Le mode actif est gardé par
// nc-modes (~/.local/state/nc/modes-etat.json) : il survit au redémarrage de l'île. Au démarrage, rien n'est réappliqué dehors ;
// seul Ne pas déranger, qui n'est gardé qu'en mémoire, est remis comme le mode l'avait posé (limite connue : s'il avait été
// coupé à la main pendant le mode juste avant un redémarrage de l'île, il revient tel que le mode l'avait posé).
// Ne pas déranger, énergie, fond, IA : à la sortie, une valeur changée à la main depuis l'activation est laissée telle quelle.
import QtQuick
import Quickshell
import Quickshell.Io

Singleton {
    id: m
    readonly property bool reglage: Reglages.val("ILE_CONCENTRATION", "oui") !== "non"
    property var modes: []                    // modes valides lus par nc-modes
    property string actif: ""                 // identifiant du mode actif ("" = aucun)
    property string actifNom: ""
    property string actifIcone: "psychology"
    property bool iaCoupee: false
    property bool fondActif: false
    property bool occupe: false
    property string message: ""
    property bool pageOuverte: false          // appui long sur Ne pas déranger : la page existe même sans mode
    property bool restaure: false             // Ne pas déranger remis une fois après un redémarrage de l'île
    readonly property bool aModes: modes.length > 0
    readonly property bool pagePossible: reglage && (aModes || pageOuverte)
    // Pastille de la pilule : seulement si un mode est actif ; le nom est caché pendant un partage d'écran (privé)
    readonly property bool pastille: reglage && actif !== ""
    readonly property string nomVisible: Partage.silence ? "" : actifNom

    function lire() { if (reglage && !lecteur.running) lecteur.running = true }
    function lancer(args) {
        if (occupe || !reglage) return false
        occupe = true; message = ""
        action.command = [Etat.bin + "nc-modes"].concat(args)
        action.running = true
        return true
    }
    function dnd() { return Notifs.concentration ? "oui" : "non" }
    function sur(id) { return /^[a-z0-9-]{1,24}$/.test(id) }
    function activer(id) { if (sur(id)) lancer(["activer", id, "--dnd", dnd()]) }
    function sortir() { lancer(["sortir", "--dnd", dnd()]) }
    function basculer(id) { if (id === actif) sortir(); else activer(id) }
    function creer(nom, exemple) {
        var a = ["creer", String(nom).slice(0, 24)]
        if (exemple && /^[a-z]{1,10}$/.test(exemple)) a = a.concat(["--exemple", exemple])
        lancer(a)
    }
    function renommer(id, nom) { if (sur(id)) lancer(["renommer", id, String(nom).slice(0, 24)]) }
    function regler(id, cle, valeur) { if (sur(id) && /^[a-z_]{1,12}$/.test(cle)) lancer(["regler", id, cle, String(valeur).slice(0, 40)]) }
    function supprimer(id) { if (sur(id)) lancer(["supprimer", id]) }
    function ouvrirPage() { pageOuverte = true; Etat.aller("concentration") }

    function lu(texte) {
        var r = {}
        try { r = JSON.parse(texte) } catch (e) { return }
        if (!r || r.ok !== true || !Array.isArray(r.modes)) return
        modes = r.modes
        actif = typeof r.actif === "string" ? r.actif : ""
        actifNom = typeof r.actif_nom === "string" ? r.actif_nom : ""
        actifIcone = typeof r.actif_icone === "string" && r.actif_icone !== "" ? r.actif_icone : "psychology"
        iaCoupee = r.ia_coupee === true
        fondActif = r.fond_actif === true
        // Après un redémarrage de l'île : Ne pas déranger (gardé en mémoire seulement) est remis comme le mode l'avait posé
        if (!restaure) {
            restaure = true
            if (actif !== "" && r.dnd_pose === true && !Notifs.concentration) Notifs.concentration = true
        }
    }
    function fini(texte) {
        occupe = false
        var r = {}
        try { r = JSON.parse(texte) } catch (e) { r = {} }
        if (r.dnd === "oui") Notifs.concentration = true
        else if (r.dnd === "non") Notifs.concentration = false
        message = r.ok === true ? (Array.isArray(r.messages) && r.messages.length ? String(r.messages[0]).slice(0, 160) : "")
                                : String(r.erreur || Reglages.t("Pas de réponse de nc-modes.", "No answer from nc-modes.")).slice(0, 160)
        lire()
    }
    Component.onCompleted: lire()
    onReglageChanged: if (reglage) lire()
    // Page fermée avec l'île : elle redevient absente de la liste tant qu'aucun mode n'existe
    Connections { target: Etat; function onEcranOuvertChanged() { if (Etat.ecranOuvert === "") m.pageOuverte = false } }

    Process {
        id: lecteur
        command: [Etat.bin + "nc-modes", "liste"]
        stdout: StdioCollector { onStreamFinished: m.lu(text) }
    }
    Process {
        id: action
        stdout: StdioCollector { onStreamFinished: m.fini(text) }
    }
}

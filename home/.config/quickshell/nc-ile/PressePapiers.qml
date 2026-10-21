pragma Singleton
// Presse-papiers de l'île : ce que tu copies (nc-presse-capture, lancé par wl-paste --watch), gardé d'une session à
// l'autre (Memo « presse » ; les images en fichiers privés de ~/.local/state/nc/ile/images). 50 textes et 12 images au
// plus, 64 Mio d'images en tout : les plus anciens non épinglés partent, leurs fichiers aussi. Jamais ce qu'un
// gestionnaire de mots de passe marque comme secret ; rien du contenu n'est journalisé. Réglage ILE_PRESSE (nc-reglages).
import QtQuick
import Quickshell
import Quickshell.Io

Singleton {
    id: pp
    readonly property int maxTextes: 50
    readonly property int maxImages: 12
    readonly property int maxOctets: 64 * 1024 * 1024
    property var entrees: []              // { id, genre: texte|image, texte | chemin + octets, t, epingle }, plus récent d'abord
    property bool prete: false            // historique gardé relu
    readonly property bool active: Reglages.val("ILE_PRESSE", "oui") !== "non"
    readonly property string bin: Quickshell.env("HOME") + "/.local/bin/"

    // Épinglés d'abord, puis du plus récent au plus ancien
    readonly property var liste: entrees.slice().sort((a, b) => (b.epingle ? 1 : 0) - (a.epingle ? 1 : 0) || b.t - a.t)

    Component.onCompleted: Memo.lire("presse", v => {
        var l = v && Array.isArray(v.entrees) ? v.entrees.filter(e => e && (e.genre === "texte" ? typeof e.texte === "string" && e.texte.trim() !== ""
                                                                     : e.genre === "image" && typeof e.chemin === "string" && typeof e.id === "string")) : []
        entrees = l.map(e => ({ id: String(e.id || e.t || Date.now()), genre: e.genre, texte: e.texte, chemin: e.chemin, octets: e.octets || 0, t: e.t || 0, epingle: !!e.epingle }))
        prete = true
        nettoyerImages()
    })
    // Remplace la liste ; les fichiers des images qui en sortent sont supprimés (jamais ceux des autres)
    function garder(nouvelle) {
        var restantes = {}
        nouvelle.forEach(e => { if (e.genre === "image") restantes[e.id] = true })
        var parties = entrees.filter(e => e.genre === "image" && !restantes[e.id]).map(e => e.id)
        entrees = nouvelle
        Memo.ecrire("presse", { entrees: entrees })
        if (parties.length) Quickshell.execDetached([bin + "nc-ile-memo", "images-supprimer"].concat(parties))
    }
    // Au démarrage seulement : les images orphelines d'une session passée (vieilles d'au moins une minute) sont supprimées
    function nettoyerImages() {
        Quickshell.execDetached([bin + "nc-ile-memo", "images-garder"].concat(entrees.filter(e => e.genre === "image").map(e => e.id)))
    }
    function ajouter(e) {
        e.t = Date.now(); e.epingle = false
        if (e.genre === "texte") e.id = "t" + e.t
        var l = entrees.filter(x => !(x.genre === "texte" && e.genre === "texte" && x.texte === e.texte && !x.epingle))
        // Un texte déjà épinglé n'est pas ajouté une seconde fois
        if (!(e.genre === "texte" && l.some(x => x.genre === "texte" && x.texte === e.texte && x.epingle))) l.unshift(e)
        garder(borner(l))
    }
    // Les limites : textes, images, octets ; les épinglés ne partent pas, les plus anciens d'abord
    function borner(l) {
        var textes = l.filter(e => e.genre === "texte" && !e.epingle), images = l.filter(e => e.genre === "image" && !e.epingle)
        var retirer = textes.slice(maxTextes).concat(images.slice(maxImages))
        var total = l.reduce((n, e) => n + (e.genre === "image" ? (e.octets || 0) : 0), 0)
        for (var i = images.length - 1; i >= 0 && total > maxOctets; i--) {
            if (retirer.indexOf(images[i]) < 0) retirer.push(images[i])
            total -= images[i].octets || 0
        }
        return l.filter(e => retirer.indexOf(e) < 0)
    }
    function supprimer(e) { garder(entrees.filter(x => x.id !== e.id)) }
    function epingler(e) { garder(borner(entrees.map(x => x.id === e.id ? Object.assign({}, x, { epingle: !x.epingle }) : x))) }
    function toutEffacer() { garder(entrees.filter(e => e.epingle)) }
    function oublierPresse() { toutEffacer() }
    // Recopier : le texte brut seulement (text/plain), ou l'image
    function recopier(e) {
        if (e.genre === "texte") Quickshell.execDetached(["wl-copy", "-t", "text/plain", "--", e.texte])
        else Quickshell.execDetached(["sh", "-c", "wl-copy -t image/png < \"$1\"", "sh", e.chemin])
    }
    // Coller en texte brut dans la fenêtre active : recopie, ferme l'île, puis Ctrl + V (send_shortcut de Hyprland, en
    // Lua : depuis Hyprland 0.56, hyprctl dispatch évalue hl.dispatch(...), l'ancienne forme « sendshortcut CTRL,V, » échoue)
    function coller(e) {
        recopier(e)
        Etat.fermer()
        Quickshell.execDetached(["sh", "-c", "sleep 0.2; hyprctl dispatch \"hl.dsp.send_shortcut({ mods = 'CTRL', key = 'V' })\" >/dev/null 2>&1"])
    }
    function correspond(e, recherche, filtre) {
        if (filtre === "textes" && e.genre !== "texte") return false
        if (filtre === "images" && e.genre !== "image") return false
        if (!recherche) return true
        var r = recherche.toLowerCase()
        return e.genre === "texte" ? e.texte.toLowerCase().indexOf(r) >= 0 : "image".indexOf(r) >= 0
    }

    // Chaque copie : une ligne de nc-presse-capture
    Process {
        running: pp.prete && pp.active
        command: ["wl-paste", "--watch", pp.bin + "nc-presse-capture"]
        stdout: SplitParser {
            onRead: ligne => {
                if (ligne.indexOf("T:") === 0) {
                    var t = ligne.slice(2).replace(/\x1f/g, "\n")    // retours à la ligne passés en \x1f (une ligne par copie)
                    if (t.trim() !== "") pp.ajouter({ genre: "texte", texte: t })
                } else if (ligne.indexOf("I:") === 0) {
                    var image = ligne.match(/^I:(\d+):([a-z0-9_-]+):(.*)$/)
                    if (image) pp.ajouter({ genre: "image", octets: +image[1], id: image[2], chemin: image[3] })
                }
            }
        }
        stderr: StdioCollector {}
    }
}

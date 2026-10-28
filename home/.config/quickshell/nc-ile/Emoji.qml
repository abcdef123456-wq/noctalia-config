// Emoji du Spotlight (« : coeur », « : rire », « : heart ») : la liste et la recherche, sans écran.
// La liste (~/.local/share/nc/emoji/emoji.tsv, 1 900 emoji de Unicode avec leurs mots-clés CLDR en français et en
// anglais, générée par outils/emoji-generer.py) n'est lue qu'à la PREMIÈRE frappe de « : » (demander()), jamais au
// démarrage de l'île : le Spotlight est chargé à la demande, la liste vit donc avec lui et disparaît à sa fermeture.
// Recherche sans casse ni accents (« coeur » trouve « cœur »), noms et mots-clés fr ET en : début d'un nom, début d'un
// mot du nom, début d'un mot-clé, puis contenu. Au plus `maximum` résultats.
// Récents : ~/.local/state/nc/emoji-recents (24 emoji au plus, un par ligne, écrit d'un coup par un fichier temporaire
// puis mv, relu sur 4 Kio au plus, seuls les emoji de la liste sont gardés). Rien d'autre n'est noté. Pendant un partage
// d'écran (Partage.silence) ils ne sont ni montrés ni mis en tête.
import QtQuick
import Quickshell
import Quickshell.Io

Item {
    id: e
    visible: false; width: 0; height: 0
    readonly property int maximum: 24
    readonly property bool discret: Partage.silence
    property bool demande: false          // vrai dès la première frappe de « : »
    property bool pret: false             // la liste est lue
    property bool echec: false            // liste introuvable ou illisible
    property var rangees: []              // { e, fr, en, pf, pe, mn, mk, tous } dans l'ordre du fichier
    property var parEmoji: ({})
    property var recents: []              // du plus récent au plus ancien
    signal donnees()
    readonly property string dossier: Quickshell.env("HOME") + "/.local/share/nc/emoji/"

    function demander() { if (!demande) demande = true }

    // Minuscules sans accents (« œ » et « æ » ne se décomposent pas)
    function plat(s) {
        s = (s || "").toLowerCase()
        try { s = s.normalize("NFD").replace(/[̀-ͯ]/g, "") } catch (err) {}
        return s.replace(/œ/g, "oe").replace(/æ/g, "ae")
    }
    function mots(s) { return s.split(/[^a-z0-9]+/).filter(x => x !== "") }

    function lire(texte) {
        var r = [], m = {}
        var lignes = texte.split("\n")
        for (let i = 0; i < lignes.length; i++) {
            var l = lignes[i]
            if (l === "" || l.charAt(0) === "#") continue
            var c = l.split("\t")
            if (c.length < 3 || c[0] === "") continue
            var pf = plat(c[1]), pe = plat(c[2]), pk = plat(c[3] || "")
            r.push({ e: c[0], fr: c[1], en: c[2], pf: pf, pe: pe, mn: mots(pf + " " + pe), mk: mots(pk), tous: pf + "|" + pe + "|" + pk })
            m[c[0]] = r.length - 1
        }
        rangees = r; parEmoji = m
        echec = r.length === 0
        pret = r.length > 0
        donnees()
    }
    function lireRecents(texte) {
        var l = texte.slice(0, 4096).split("\n"), out = []
        for (let i = 0; i < l.length && out.length < 24; i++) {
            var x = l[i].trim()
            if (x !== "" && x.length <= 32 && out.indexOf(x) < 0) out.push(x)
        }
        recents = out
        donnees()
    }

    // Note d'un emoji pour un mot de la saisie (déjà sans accents) : 0 = ne correspond pas
    function note(x, m) {
        if (x.pf.startsWith(m) || x.pe.startsWith(m)) return 100
        if (x.mn.some(w => w.startsWith(m))) return 90
        if (x.mk.some(w => w.startsWith(m))) return 80
        if (x.pf.indexOf(m) >= 0 || x.pe.indexOf(m) >= 0) return 50
        if (x.tous.indexOf(m) >= 0) return 40
        return 0
    }
    // Lignes { e, fr, en, recent } : saisie vide = les récents ; sinon les récents qui correspondent d'abord, puis par note
    function chercher(brut) {
        var rec = discret ? [] : recents
        var q = plat(brut).trim()
        var out = []
        if (q === "") {
            for (let i = 0; i < rec.length && out.length < maximum; i++) {
                var k = parEmoji[rec[i]]
                if (k !== undefined) out.push({ e: rangees[k].e, fr: rangees[k].fr, en: rangees[k].en, recent: true })
            }
            return out
        }
        var tous = q.split(/\s+/), cand = []
        for (let i = 0; i < rangees.length; i++) {
            var x = rangees[i], s = 1000
            for (let j = 0; j < tous.length && s > 0; j++) s = Math.min(s, note(x, tous[j]))
            if (s <= 0) continue
            var ir = rec.indexOf(x.e)
            cand.push({ x: x, i: i, s: s, r: ir >= 0 ? 100 - ir : 0 })
        }
        cand.sort((a, b) => (b.r - a.r) || (b.s - a.s) || (a.i - b.i))
        for (let i = 0; i < cand.length && out.length < maximum; i++)
            out.push({ e: cand[i].x.e, fr: cand[i].x.fr, en: cand[i].x.en, recent: cand[i].r > 0 })
        return out
    }

    // Choisi : le nouveau en tête des récents (24 au plus), écrit d'un coup (fichier temporaire puis mv)
    function noter(em) {
        var l = [em].concat(recents.filter(x => x !== em)).slice(0, 24)
        recents = l
        Quickshell.execDetached(["sh", "-c",
            "umask 077; d=\"$HOME/.local/state/nc\"; mkdir -p \"$d\" || exit 1; t=\"$d/.emoji-recents.$$\"; printf '%s\\n' \"$@\" > \"$t\" && mv -f \"$t\" \"$d/emoji-recents\"",
            "sh"].concat(l))
    }

    FileView {
        path: e.demande ? e.dossier + "emoji.tsv" : ""
        printErrors: false
        onLoaded: e.lire(text())
        onLoadFailed: { e.echec = true; e.donnees() }
    }
    FileView {
        path: e.demande ? Quickshell.env("HOME") + "/.local/state/nc/emoji-recents" : ""
        printErrors: false
        onLoaded: e.lireRecents(text())
    }
}

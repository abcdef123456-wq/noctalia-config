// Rappels locaux (Spotlight « rappel 15h appeler le garage ») : l'analyse de la phrase et la liste, en fonctions pures,
// sans horloge cachée (l'heure est passée en argument). Le texte du rappel reste brut : jamais interprété ni passé à un shell.
.pragma library

var MAX_RAPPELS = 50
var MAX_TEXTE = 200
var MAX_MS = 366 * 86400000          // un rappel plus loin qu'un an : phrase refusée (faute de frappe probable)

// Texte brut : espaces nettoyés, caractères de contrôle remplacés, 200 caractères au plus (par caractère, pas par moitié d'emoji)
function nettoyer(t) {
    return Array.from(String(t || "").replace(/[\x00-\x1f\x7f]+/g, " ").trim()).slice(0, MAX_TEXTE).join("")
}

function heureValide(h, m) { return h >= 0 && h < 24 && m >= 0 && m < 60 }

// « demain 9h », « tomorrow 9am », « à 15h30 », « 15:30 », « 3pm », « dans 20 min », « in 2 h », « 90 s » + le texte.
// Rend { ok: true, due, texte } ou { ok: false, raison: "heure" | "texte" }. « 15h » collé = une heure de la journée ;
// « 2 h » avec espace, « 20 min », « 90 s », ou tout après « dans » / « in » = une durée.
function analyser(phrase, maintenant) {
    var s = String(phrase || "").trim()
    var demain = false, duree = false, m
    if ((m = /^(demain|tomorrow)\b\s*/i.exec(s))) { demain = true; s = s.slice(m[0].length) }
    if ((m = /^(dans|in)\s+/i.exec(s))) { duree = true; s = s.slice(m[0].length) }
    else if ((m = /^(à|a|at)\s+/i.exec(s))) s = s.slice(m[0].length)
    var due = null
    // Durée : « 20 min », « 2 h », « 1h30 » après « dans », « 90 s »
    if ((m = /^(\d{1,5})(\s*)(h|heures?|hours?|hrs?)(\d{1,2})?(?=\s|$)/i.exec(s)) && (duree || m[2] !== "" || m[3].length > 1)) {
        due = maintenant + (parseInt(m[1], 10) * 60 + (m[4] ? parseInt(m[4], 10) : 0)) * 60000
    } else if ((m = /^(\d{1,7})\s*(s|sec|secs|secondes?|seconds?|min|mins|minutes?)(?=\s|$)/i.exec(s))) {
        due = maintenant + parseInt(m[1], 10) * (/^s/i.test(m[2]) ? 1000 : 60000)
    } else m = null
    if (due !== null) {
        if (demain || due - maintenant > MAX_MS) return { ok: false, raison: "heure" }
        s = s.slice(m[0].length)
    } else {
        // Heure de la journée : 15h, 15h30, 15:30, 3pm, 3:30pm
        var h = -1, mi = 0
        if ((m = /^(\d{1,2})\s*(?::|h)\s*(\d{2})?(?=\s|$)/i.exec(s)) && !duree) { h = parseInt(m[1], 10); mi = m[2] ? parseInt(m[2], 10) : 0 }
        else if ((m = /^(\d{1,2})(?::(\d{2}))?\s*(am|pm)(?=\s|$)/i.exec(s)) && !duree) {
            h = parseInt(m[1], 10); mi = m[2] ? parseInt(m[2], 10) : 0
            if (h < 1 || h > 12) return { ok: false, raison: "heure" }
            h = h % 12 + (/pm/i.test(m[3]) ? 12 : 0)
        }
        if (h < 0 || !heureValide(h, mi)) return { ok: false, raison: "heure" }
        var d = new Date(maintenant)
        d.setHours(h, mi, 0, 0)
        if (demain) d.setDate(d.getDate() + 1)
        else if (d.getTime() <= maintenant) d.setDate(d.getDate() + 1)      // déjà passée aujourd'hui : demain
        due = d.getTime()
        s = s.slice(m[0].length)
    }
    var texte = nettoyer(s)
    return texte === "" ? { ok: false, raison: "texte" } : { ok: true, due: due, texte: texte }
}

// « 15:00 », ou « demain 09:00 » (« tomorrow 09:00 ») si ce n'est pas aujourd'hui ; plus loin : la date
function quand(due, maintenant, anglais) {
    var d = new Date(due), a = new Date(maintenant)
    var p = n => (n < 10 ? "0" : "") + n
    var h = p(d.getHours()) + ":" + p(d.getMinutes())
    var jours = Math.round((new Date(d.getFullYear(), d.getMonth(), d.getDate()) - new Date(a.getFullYear(), a.getMonth(), a.getDate())) / 86400000)
    if (jours === 0) return h
    if (jours === 1) return (anglais ? "tomorrow " : "demain ") + h
    return p(d.getDate()) + "/" + p(d.getMonth() + 1) + " " + h
}

// Liste lue du disque : rien d'autre que des { id, texte, due } sains, 50 au plus
function valider(v) {
    if (!Array.isArray(v)) return []
    var vus = {}
    return v.filter(x => x && typeof x.id === "string" && typeof x.texte === "string" && typeof x.due === "number" && isFinite(x.due) && !vus[x.id] && (vus[x.id] = true))
            .slice(0, MAX_RAPPELS).map(x => ({ id: x.id, texte: nettoyer(x.texte), due: x.due }))
}

// Ajoute un rappel : { ok, liste } ; le 51e est refusé (raison "plein")
function ajouter(liste, texte, due, maintenant) {
    if (liste.length >= MAX_RAPPELS) return { ok: false, raison: "plein", liste: liste }
    var id = "q" + maintenant.toString(36), n = 0
    while (liste.some(x => x.id === id + n)) n++
    return { ok: true, liste: liste.concat([{ id: id + n, texte: nettoyer(texte), due: due }]) }
}

function retirer(liste, id) { return liste.filter(x => x.id !== id) }

// Les échus (due <= maintenant) à montrer, ce qui reste, et la prochaine échéance (null s'il ne reste rien)
function partager(liste, maintenant) {
    var dus = liste.filter(x => x.due <= maintenant).sort((a, b) => a.due - b.due)
    var restants = liste.filter(x => x.due > maintenant)
    return { dus: dus, restants: restants, prochaine: restants.length ? Math.min.apply(null, restants.map(x => x.due)) : null }
}

// Intervalle du minuteur unique vers la prochaine échéance : au moins 1 ms, au plus 2^31-1 (limite d'un Timer QML)
function delai(prochaine, maintenant) { return Math.max(1, Math.min(2147483647, prochaine - maintenant)) }

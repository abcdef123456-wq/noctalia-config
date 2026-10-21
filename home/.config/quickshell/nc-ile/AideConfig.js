// Réponses aux questions sur la config (Spotlight « ? question », fenêtre des réglages) : le même calcul que
// nc-aide-config (Python), sur l'index ~/.cache/nc/aide-config.json déjà chargé. Rien n'est lancé pendant la frappe.
// Mots outils et familles de synonymes : ceux de l'index (une seule source de vérité, nc-aide-config).
.pragma library

function normaliser(t) {
    var s = String(t || "").toLowerCase()
    try { s = s.normalize("NFD").replace(/[̀-ͯ]/g, "") } catch (e) {}
    return s.replace(/[^a-z0-9]+/g, " ").trim()
}
function racine(m) { return m.length > 4 && /[sx]$/.test(m) ? m.slice(0, -1) : m }

// Prépare un index lu en JSON : ensembles de mots, familles de synonymes
function preparer(index) {
    if (!index || !Array.isArray(index.entrees)) return null
    var vides = {}, groupe = {}
    ;(index.vides || []).forEach(m => vides[m] = true)
    var familles = (index.synonymes || []).map(l => l.split(" "))
    familles.forEach((f, i) => f.forEach(m => { if (groupe[m] === undefined) groupe[m] = i }))
    return { entrees: index.entrees, vides: vides, familles: familles, groupe: groupe }
}

function mots(prep, t) {
    return normaliser(t).split(" ").filter(m => m.length > 1 && !prep.vides[m]).map(racine)
}

// Un mot court (4 lettres) ne correspond qu'à lui-même ou à sa forme en -s, -x, -e ; plus long, à un mot qui le prolonge
function correspond(q, ws) {
    for (var i = 0; i < ws.length; i++) {
        var w = ws[i]
        if (w === q) return true
        var paires = [[q, w], [w, q]]
        for (var k = 0; k < 2; k++) {
            var a = paires[k][0], b = paires[k][1]
            if (a.length >= 5 && b.startsWith(a)) return true
            if (a.length === 4 && b.length === 5 && b.startsWith(a) && "sxe".indexOf(b[4]) >= 0) return true
        }
    }
    return false
}

// Les meilleures réponses : [{type, titre, texte, …, score}]
function chercher(prep, question, maximum) {
    if (!prep) return []
    var vus = {}, concepts = []
    mots(prep, question).forEach(m => {
        if (vus[m]) return
        vus[m] = true
        var g = prep.groupe[m]
        var famille = g === undefined ? [] : prep.familles[g].map(racine).filter(x => x !== m)
        concepts.push([m].concat(famille))
    })
    if (!concepts.length) return []
    var bonus = { reglage: 0.6, raccourci: 0.4, commande: 0.2, doc: 0 }
    var res = []
    prep.entrees.forEach(e => {
        var score = 0, trouves = 0
        concepts.forEach(c => {
            var meilleur = 0
            for (var i = 0; i < c.length; i++) {
                var poids = i === 0 ? 1 : 0.8
                if (correspond(c[i], e.mt)) meilleur = Math.max(meilleur, 3 * poids)
                else if (correspond(c[i], e.mx)) meilleur = Math.max(meilleur, poids)
            }
            if (meilleur) { trouves++; score += meilleur }
        })
        var couverture = trouves / concepts.length
        if (trouves && (couverture >= 0.5 || concepts.length === 1))
            res.push({ e: e, s: score * (0.4 + couverture) + (bonus[e.type] || 0) })
    })
    res.sort((a, b) => b.s - a.s)
    return res.slice(0, maximum || 5).map(x => Object.assign({ score: Math.round(x.s * 100) / 100 }, x.e))
}

// Une question en langage naturel (sans « ? ») : le Spotlight y répond aussi
function estQuestion(t) {
    // (?=…) plutôt que \b : \b ne connaît pas les lettres accentuées (« où »)
    return /^(comment|pourquoi|ou|où|quel|quelle|quels|quelles|est-ce|est ce|c'est quoi|qu'est|combien|peut-on|puis-je|how|why|where|what|which|can i|is there)(?=[\s'?]|$)/i.test(String(t || "").trim())
        || /\?\s*$/.test(String(t || ""))
}

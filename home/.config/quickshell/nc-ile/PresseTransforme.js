// Transformations d'un texte copié, au clic seulement (page Presse-papiers) : minuscules, MAJUSCULES, JSON mis en forme.
// Fonctions pures : rien n'est lancé ici. L'historique garde 4 000 caractères, puis « … » (nc-presse-capture) : un texte
// plus long est donc coupé, et rien n'est proposé (on ne recopie jamais un texte tronqué).
.pragma library

var MAX = 4000

// JSON valide ET objet ou tableau (« 42 » ou « "x" » ne sont pas proposés) ; sinon undefined
function json(t) {
    try {
        var v = JSON.parse(t)
        return v !== null && typeof v === "object" ? JSON.stringify(v, null, 2) : undefined
    } catch (e) { return undefined }
}
// Le résultat d'une transformation ("min", "maj", "json"), ou undefined si elle ne s'applique pas ou ne change rien
function appliquer(mode, t) {
    if (typeof t !== "string" || t === "" || t.length > MAX) return undefined
    var r = mode === "min" ? t.toLowerCase() : mode === "maj" ? t.toUpperCase() : mode === "json" ? json(t) : undefined
    return r === t ? undefined : r
}
function proposees(t) { return ["min", "maj", "json"].filter(m => appliquer(m, t) !== undefined) }

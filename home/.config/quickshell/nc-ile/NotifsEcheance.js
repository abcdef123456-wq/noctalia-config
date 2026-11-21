// Prochaine échéance de Notifs.qml (début ou fin de la plage « ne pas déranger », retour d'une notification reportée) :
// fonctions pures, l'heure est passée en argument. Un seul minuteur non répétitif vise cette échéance ; sans échéance, rien ne tourne.
.pragma library

var MIN_MS = 1000               // jamais de tir en boucle serrée : une échéance déjà passée tire une fois, 1 s plus tard
var MAX_MS = 2147483647         // limite d'un Timer QML (entier 32 bits)

function minutes(h) { var p = String(h).split(":"); return (parseInt(p[0]) || 0) * 60 + (parseInt(p[1]) || 0) }

// Prochain début ou fin de plage strictement après « maintenant » (ms), null si aucune plage ou si début = fin (plage vide)
function prochainePlage(actif, debut, fin, maintenant) {
    var a = minutes(debut), b = minutes(fin)
    if (!actif || a === b) return null
    var meilleur = null
    ;[a, b].forEach(function (t) {
        var d = new Date(maintenant)
        d.setHours(Math.floor(t / 60) % 24, t % 60, 0, 0)
        if (d.getTime() <= maintenant) d.setDate(d.getDate() + 1)
        if (meilleur === null || d.getTime() < meilleur) meilleur = d.getTime()
    })
    return meilleur
}

// Le plus proche entre la plage et les retours en attente (heures en ms) ; null s'il n'y a rien
function prochaine(actif, debut, fin, dues, maintenant) {
    var m = prochainePlage(actif, debut, fin, maintenant)
    ;(dues || []).forEach(function (d) { if (typeof d === "number" && isFinite(d) && (m === null || d < m)) m = d })
    return m
}

// Intervalle du minuteur : au moins 1 s, au plus 2^31-1 ms (au tir on recompare à l'heure réelle et on réarme)
function delai(echeance, maintenant) { return Math.max(MIN_MS, Math.min(MAX_MS, echeance - maintenant)) }

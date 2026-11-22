// Saisies du Spotlight comprises sans réseau, en fonctions pures (l'heure est passée en argument) : les dates en
// français réécrites pour qalc. Rien n'est passé à un shell : la sortie est un argument de qalc.
.pragma library

function deux(n) { return (n < 10 ? "0" : "") + n }

// Date du calendrier valide (pas de 31/02) : AAAA-MM-JJ, sinon ""
function iso(a, m, j) {
    var d = new Date(a, m - 1, j)
    return d.getFullYear() === a && d.getMonth() === m - 1 && d.getDate() === j && a >= 1900 && a <= 2999
        ? a + "-" + deux(m) + "-" + deux(j) : ""
}

// « jours jusqu'au 25/12 », « jours avant le 25/12/2027 », « jours jusqu'au 2027-01-01 », « days until 2027-01-01 » :
// le nombre de jours (sans année : la prochaine fois que ce jour arrive) ; « dans 45 jours », « in 45 days » : la date.
// "" : la saisie n'est pas une de ces formes (ou la date n'existe pas)
function dateQalc(q, maintenant) {
    var s = String(q || "").trim().toLowerCase().replace(/[’']/g, "'").replace(/\s+/g, " ")
    var m = /^(?:dans|in) (\d{1,5}) (?:jours?|days?)$/.exec(s)
    if (m) return "today + " + parseInt(m[1], 10) + " d"
    var d = ""
    m = /^(?:nombre de )?jours? (?:jusqu'(?:au|à) |avant (?:le )?)(\d{1,2})\/(\d{1,2})(?:\/(\d{4}))?$/.exec(s)
    if (m) {
        var auj = new Date(maintenant), j = parseInt(m[1], 10), mo = parseInt(m[2], 10)
        var a = m[3] ? parseInt(m[3], 10) : auj.getFullYear()
        d = iso(a, mo, j)
        if (d !== "" && !m[3] && new Date(a, mo - 1, j) < new Date(auj.getFullYear(), auj.getMonth(), auj.getDate()))
            d = iso(a + 1, mo, j)                       // déjà passé cette année (29/02 sans année : rien si la suivante n'en a pas)
    } else {
        m = /^(?:(?:nombre de )?jours? (?:jusqu'(?:au|à) |avant (?:le )?)|days? (?:until|till|to|before) )(\d{4})-(\d{2})-(\d{2})$/.exec(s)
        if (m) d = iso(parseInt(m[1], 10), parseInt(m[2], 10), parseInt(m[3], 10))
    }
    return d === "" ? "" : "days(today; " + d + ") d"
}

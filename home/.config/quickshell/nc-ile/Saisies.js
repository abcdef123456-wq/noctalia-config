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

// ── « heure tokyo » : l'heure d'une ville ──
// Minuscules sans accents, tout ce qui n'est pas lettre ou chiffre devient une espace (« New_York » = « new york »)
function nomVille(s) {
    return String(s || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase().replace(/[^a-z0-9]+/g, " ").trim()
}

// « heure tokyo », « heure à tokyo », « heure de new york », « time in tokyo », « time tokyo » : la ville tapée, sinon ""
function villeHeure(q) {
    var m = /^(?:heure|time)\s+(?:(?:a|à|au|aux|de|du|des|in|at|en)\s+|d['’]\s*)?(.+)$/i.exec(String(q || "").trim().replace(/\s+/g, " "))
    if (!m) return ""
    return /^[^\d]{2,40}$/.test(m[1]) ? m[1] : ""
}

// Noms français (ou de villes absentes de zone1970.tab, regroupées avec une voisine de même heure) : nom sans accents → zone
var ZONES_FR = {
    "londres": "Europe/London", "pekin": "Asia/Shanghai", "beijing": "Asia/Shanghai", "moscou": "Europe/Moscow",
    "le caire": "Africa/Cairo", "caire": "Africa/Cairo", "delhi": "Asia/Kolkata", "nouvelle delhi": "Asia/Kolkata",
    "new delhi": "Asia/Kolkata", "mumbai": "Asia/Kolkata", "bombay": "Asia/Kolkata", "seoul": "Asia/Seoul", "sydney": "Australia/Sydney",
    "los angeles": "America/Los_Angeles", "mexico": "America/Mexico_City", "rio": "America/Sao_Paulo",
    "rio de janeiro": "America/Sao_Paulo", "montreal": "America/Toronto", "quebec": "America/Toronto",
    "geneve": "Europe/Zurich", "bruxelles": "Europe/Brussels", "varsovie": "Europe/Warsaw", "lisbonne": "Europe/Lisbon",
    "rome": "Europe/Rome", "athenes": "Europe/Athens", "istanbul": "Europe/Istanbul", "vienne": "Europe/Vienna",
    "prague": "Europe/Prague", "new york": "America/New_York", "tokyo": "Asia/Tokyo", "amsterdam": "Europe/Brussels",
    "stockholm": "Europe/Berlin", "oslo": "Europe/Berlin", "copenhague": "Europe/Berlin", "kiev": "Europe/Kyiv",
    "dubai": "Asia/Dubai", "singapour": "Asia/Singapore", "jerusalem": "Asia/Jerusalem", "le cap": "Africa/Johannesburg"
}

// « heure » seul, « horloge(s) », « clocks », « world clock » : la saisie demande les horloges mondiales (« heure tokyo » : non)
function demandeHorloges(q) {
    return /^(?:heure|horloges?|clocks?|world clocks?)$/i.test(String(q || "").trim().replace(/\s+/g, " "))
}

// Réglage HORLOGES_VILLES (« Tokyo, New York ») → villes valides, 8 au plus (même règle que nc-reglages : 2 à 40 caractères sans chiffre)
function villesHorloges(texte) {
    var out = [], l = String(texte || "").split(",")
    for (var i = 0; i < l.length && out.length < 8; i++) {
        var v = l[i].trim()
        if (/^[^\d,]{2,40}$/.test(v)) out.push(v)
    }
    return out
}

// [{ ville, zone }] : seules les villes que la liste lue connaît (zone prise dans la liste, jamais dans la saisie) ; les autres sont ignorées
function zonesHorloges(villes, zones) {
    var out = []
    for (var i = 0; i < villes.length; i++) {
        var z = zoneVille(villes[i], zones)
        if (z !== "") out.push({ ville: nomAffiche(villes[i]), zone: z })
    }
    return out
}

// Les zones lues dans zone1970.tab (3e colonne) ; seules les formes Région/Ville ou Région/Pays/Ville passent
function listeZones(texte) {
    var out = []
    var lignes = String(texte || "").split("\n")
    for (var i = 0; i < lignes.length; i++) {
        if (lignes[i].charAt(0) === "#") continue
        var c = lignes[i].split("\t")
        if (c.length >= 3 && /^[A-Za-z]+(?:\/[A-Za-z0-9_+-]+){1,2}$/.test(c[2])) out.push(c[2])
    }
    return out
}

// La zone de la ville tapée, TOUJOURS prise dans la liste lue (jamais la saisie telle quelle) ; "" : inconnue
function zoneVille(ville, zones) {
    var n = nomVille(ville), liste = zones || []
    if (n === "") return ""
    var z = Object.prototype.hasOwnProperty.call(ZONES_FR, n) ? ZONES_FR[n] : ""
    for (var i = 0; i < liste.length; i++) {
        var fin = liste[i].substring(liste[i].lastIndexOf("/") + 1)
        if (z !== "" ? liste[i] === z : nomVille(fin) === n) return liste[i]
    }
    return ""
}

// Nom affiché : la ville tapée, chaque mot avec une majuscule
function nomAffiche(ville) {
    return String(ville).trim().toLowerCase().replace(/(^|[\s'’-])(\S)/g, function (t, a, b) { return a + b.toUpperCase() })
}

// Décalage en minutes d'un « +0900 » de date ; NaN si ce n'en est pas un
function minutesZ(z) {
    var m = /^([+-])(\d\d)(\d\d)$/.exec(z)
    return m ? (m[1] === "-" ? -1 : 1) * (parseInt(m[2], 10) * 60 + parseInt(m[3], 10)) : NaN
}

var JOURS = [["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"],
             ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]]
var MOIS = [["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."],
            ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]]

// Sortie de « date +%H:%M|%u|%d|%m|%z » → « Tokyo : 14:32, lundi 23 nov. » (« 2:32 PM » si douze), décalage « +8 h » ;
// localMin : décalage de l'heure locale en minutes. null si la sortie n'a pas la forme attendue.
function ligneHeure(sortie, ville, douze, anglais, localMin) {
    var m = /^(\d\d):(\d\d)\|([1-7])\|(\d\d)\|(\d\d)\|([+-]\d{4})$/.exec(String(sortie || "").trim())
    if (!m) return null
    var h = parseInt(m[1], 10), mois = parseInt(m[5], 10), l = anglais ? 1 : 0
    if (mois < 1 || mois > 12 || h > 23) return null
    var heure = douze ? (h % 12 === 0 ? 12 : h % 12) + ":" + m[2] + (h < 12 ? " AM" : " PM") : m[1] + ":" + m[2]
    var jour = JOURS[l][parseInt(m[3], 10) - 1] + " " + (anglais ? MOIS[l][mois - 1] + " " + parseInt(m[4], 10) : parseInt(m[4], 10) + " " + MOIS[l][mois - 1])
    var ecart = minutesZ(m[6]) - localMin, a = Math.abs(ecart)
    var dec = (ecart < 0 ? "-" : "+") + Math.floor(a / 60) + " h" + (a % 60 ? " " + deux(a % 60) : "")
    return { texte: ville + " : " + heure + ", " + jour, ecart: dec }
}

// « port 8080 », « port :8080 » : { port: N } (1 à 65535) ; « processus firefox » : { nom: … } (lettres, chiffres,
// « ._- », 1 à 32 caractères) ; null sinon (recherche ordinaire seule, rien n'est lancé ; nc-processus revérifie)
function demandeProcessus(q) {
    var s = String(q || "").trim()
    var m = /^port\s+:?(\d{1,5})$/i.exec(s)
    if (m) { var n = parseInt(m[1], 10); return n >= 1 && n <= 65535 ? { port: n } : null }
    m = /^processus\s+([A-Za-z0-9._-]{1,32})$/i.exec(s)
    return m ? { nom: m[1] } : null
}

// Raccourcis web de l'utilisateur (liens-web.conf : « préfixe<TAB>nom<TAB>URL », « %s » = la saisie). Mêmes règles que
// nc-reglages (liens_web_valide) : préfixe [a-z0-9]{1,12} hors mots réservés, URL http(s) avec un seul « %s », nom de
// 40 caractères au plus sans contrôle. Fichier borné à 16 Kio et 50 lignes ; une ligne fausse est ignorée sans bruit.
// Contrôles, séparateurs de ligne, sens d'écriture et invisibles (sans regex Unicode : Qt 6.8 de Debian 13)
var CONTROLES = /[\u0000-\u001f\u007f-\u009f\u00ad\u0600-\u0605\u061c\u06dd\u070f\u180e\u200b-\u200f\u2028-\u202e\u2060-\u2064\u2066-\u206f\ufeff\ufff9-\ufffb\ue000-\uf8ff]/
var RESERVES = ["g", "yt", "w", "heure", "time", "mdp", "password", "port", "processus", "session", "sessions",
                "note", "notes", "rappel", "rappels", "reminder", "reminders"]
function analyseLiens(texte) {
    var t = String(texte || ""), vus = {}, liens = []
    if (t.length > 16384) return []
    var lignes = t.split("\n")
    if (lignes[lignes.length - 1] === "") lignes.pop()      // le retour à la ligne final n'est pas une ligne
    if (lignes.length > 50) return []
    for (var i = 0; i < lignes.length; i++) {
        var l = lignes[i].replace(/\r$/, "")
        if (l === "" || l.charAt(0) === "#") continue
        var c = l.split("\t")
        if (c.length !== 3) continue
        var p = c[0], nom = c[1], url = c[2]
        if (!/^[a-z0-9]{1,12}$/.test(p) || RESERVES.indexOf(p) >= 0 || vus[p]) continue
        if (nom.length < 1 || nom.length > 40 || CONTROLES.test(nom)) continue
        if (!/^https?:\/\/[^\s\u0000-\u001f\u007f-\u009f]+$/.test(url) || url.split("%s").length !== 2) continue
        vus[p] = true
        liens.push({ p: p, nom: nom, url: url })
    }
    return liens
}
// « amz chaussettes » → { nom, terme, url } avec la saisie encodée ; null si le préfixe n'est pas dans la liste
function lienWeb(q, liens) {
    var m = /^([a-z0-9]{1,12}) +(\S.*)$/.exec(String(q || ""))
    if (!m) return null
    for (var i = 0; i < liens.length; i++)
        if (liens[i].p === m[1]) return { nom: liens[i].nom, terme: m[2], url: liens[i].url.replace("%s", encodeURIComponent(m[2])) }
    return null
}

// Snippets de l'utilisateur (snippets.conf : « mot<TAB>titre<TAB>texte[<TAB>secret] », texte échappé : \\ \n \t). Mêmes
// règles que nc-reglages (snippet_comprise) : mot [a-z0-9]{1,12} hors RESERVES, titre de 1 à 40 signes sans contrôle,
// texte de 1 à 2 000 signes (retour à la ligne et tabulation permis). Mêmes bornes de fichier que liens-web.conf.
// Signes : des points de code, comme len() en Python (un emoji compte pour un)
function points(s) { return String(s).match(/[\ud800-\udbff][\udc00-\udfff]|[\s\S]/g) || [] }
function echapper(t) { return String(t).replace(/\\/g, "\\\\").replace(/\n/g, "\\n").replace(/\t/g, "\\t") }
// null si une barre oblique inverse n'est pas suivie de \, n ou t
function deseschapper(s) {
    if (!/^(?:[^\\]|\\[\\nt])*$/.test(s)) return null
    return s.replace(/\\([\\nt])/g, function (m, c) { return c === "n" ? "\n" : c === "t" ? "\t" : "\\" })
}
function analyseSnippets(texte) {
    var t = String(texte || ""), vus = {}, res = []
    if (t.length > 16384) return []
    var lignes = t.split("\n")
    if (lignes[lignes.length - 1] === "") lignes.pop()
    if (lignes.length > 50) return []
    for (var i = 0; i < lignes.length; i++) {
        var l = lignes[i].replace(/\r$/, "")
        if (l === "" || l.charAt(0) === "#") continue
        var c = l.split("\t")
        if ((c.length !== 3 && c.length !== 4) || (c.length === 4 && c[3] !== "secret")) continue
        var mot = c[0], titre = c[1], clair = deseschapper(c[2])
        if (!/^[a-z0-9]{1,12}$/.test(mot) || RESERVES.indexOf(mot) >= 0 || vus[mot]) continue
        var nt = points(titre).length
        if (nt < 1 || nt > 40 || CONTROLES.test(titre) || clair === null) continue
        var nc = points(clair).length
        if (nc < 1 || nc > 2000 || CONTROLES.test(clair.replace(/[\n\t]/g, ""))) continue
        vus[mot] = true
        res.push({ mot: mot, titre: titre, texte: clair, secret: c.length === 4 })
    }
    return res
}
// « ;ad » → 3 cartes au plus, pour les mots qui commencent par la saisie : { mot, titre, sous }. Le sous-titre est le
// texte aplati sur une ligne, coupé à 80 signes ; pour un secret, seulement motSecret : la carte ne porte jamais son texte
function cartesSnippets(q, liste, motSecret) {
    var s = String(q || "")
    if (s.charAt(0) !== ";") return []
    var debut = s.slice(1).trim().toLowerCase(), res = []
    for (var i = 0; i < liste.length && res.length < 3; i++) {
        var x = liste[i]
        if (x.mot.indexOf(debut) !== 0) continue
        var p = points(x.texte.replace(/\s+/g, " ").trim())
        res.push({ mot: x.mot, titre: x.titre, sous: x.secret ? motSecret : (p.length > 80 ? p.slice(0, 79).join("") + "…" : p.join("")) })
    }
    return res
}

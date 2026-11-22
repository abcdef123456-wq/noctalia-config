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
// Caractères refusés (titre, texte, mot, nom de lien) : la MÊME table que CARACTERES_REFUSES de nc-reglages (catégories
// Unicode C*, Zl, Zp, figées d'après Unicode 16 ; test_snippets compare les deux). Plages « début-fin » en hexadécimal.
var REFUSES_TABLE = (
    "0-1f,7f-9f,ad,378-379,380-383,38b,38d,3a2,530,557-558,58b-58c,590,5c8-5cf,5eb-5ee,5f5-605,61c,6dd," +
    "70e-70f,74b-74c,7b2-7bf,7fb-7fc,82e-82f,83f,85c-85d,85f,86b-86f,88f-896,8e2,984,98d-98e,991-992,9a9," +
    "9b1,9b3-9b5,9ba-9bb,9c5-9c6,9c9-9ca,9cf-9d6,9d8-9db,9de,9e4-9e5,9ff-a00,a04,a0b-a0e,a11-a12,a29,a31," +
    "a34,a37,a3a-a3b,a3d,a43-a46,a49-a4a,a4e-a50,a52-a58,a5d,a5f-a65,a77-a80,a84,a8e,a92,aa9,ab1,ab4," +
    "aba-abb,ac6,aca,ace-acf,ad1-adf,ae4-ae5,af2-af8,b00,b04,b0d-b0e,b11-b12,b29,b31,b34,b3a-b3b,b45-b46," +
    "b49-b4a,b4e-b54,b58-b5b,b5e,b64-b65,b78-b81,b84,b8b-b8d,b91,b96-b98,b9b,b9d,ba0-ba2,ba5-ba7,bab-bad," +
    "bba-bbd,bc3-bc5,bc9,bce-bcf,bd1-bd6,bd8-be5,bfb-bff,c0d,c11,c29,c3a-c3b,c45,c49,c4e-c54,c57,c5b-c5c," +
    "c5e-c5f,c64-c65,c70-c76,c8d,c91,ca9,cb4,cba-cbb,cc5,cc9,cce-cd4,cd7-cdc,cdf,ce4-ce5,cf0,cf4-cff,d0d," +
    "d11,d45,d49,d50-d53,d64-d65,d80,d84,d97-d99,db2,dbc,dbe-dbf,dc7-dc9,dcb-dce,dd5,dd7,de0-de5,df0-df1," +
    "df5-e00,e3b-e3e,e5c-e80,e83,e85,e8b,ea4,ea6,ebe-ebf,ec5,ec7,ecf,eda-edb,ee0-eff,f48,f6d-f70,f98,fbd," +
    "fcd,fdb-fff,10c6,10c8-10cc,10ce-10cf,1249,124e-124f,1257,1259,125e-125f,1289,128e-128f,12b1," +
    "12b6-12b7,12bf,12c1,12c6-12c7,12d7,1311,1316-1317,135b-135c,137d-137f,139a-139f,13f6-13f7,13fe-13ff," +
    "169d-169f,16f9-16ff,1716-171e,1737-173f,1754-175f,176d,1771,1774-177f,17de-17df,17ea-17ef,17fa-17ff," +
    "180e,181a-181f,1879-187f,18ab-18af,18f6-18ff,191f,192c-192f,193c-193f,1941-1943,196e-196f,1975-197f," +
    "19ac-19af,19ca-19cf,19db-19dd,1a1c-1a1d,1a5f,1a7d-1a7e,1a8a-1a8f,1a9a-1a9f,1aae-1aaf,1acf-1aff,1b4d," +
    "1bf4-1bfb,1c38-1c3a,1c4a-1c4c,1c8b-1c8f,1cbb-1cbc,1cc8-1ccf,1cfb-1cff,1f16-1f17,1f1e-1f1f,1f46-1f47," +
    "1f4e-1f4f,1f58,1f5a,1f5c,1f5e,1f7e-1f7f,1fb5,1fc5,1fd4-1fd5,1fdc,1ff0-1ff1,1ff5,1fff,200b-200f," +
    "2028-202e,2060-206f,2072-2073,208f,209d-209f,20c1-20cf,20f1-20ff,218c-218f,242a-243f,244b-245f," +
    "2b74-2b75,2b96,2cf4-2cf8,2d26,2d28-2d2c,2d2e-2d2f,2d68-2d6e,2d71-2d7e,2d97-2d9f,2da7,2daf,2db7,2dbf," +
    "2dc7,2dcf,2dd7,2ddf,2e5e-2e7f,2e9a,2ef4-2eff,2fd6-2fef,3040,3097-3098,3100-3104,3130,318f,31e6-31ee," +
    "321f,a48d-a48f,a4c7-a4cf,a62c-a63f,a6f8-a6ff,a7ce-a7cf,a7d2,a7d4,a7dd-a7f1,a82d-a82f,a83a-a83f," +
    "a878-a87f,a8c6-a8cd,a8da-a8df,a954-a95e,a97d-a97f,a9ce,a9da-a9dd,a9ff,aa37-aa3f,aa4e-aa4f,aa5a-aa5b," +
    "aac3-aada,aaf7-ab00,ab07-ab08,ab0f-ab10,ab17-ab1f,ab27,ab2f,ab6c-ab6f,abee-abef,abfa-abff,d7a4-d7af," +
    "d7c7-d7ca,d7fc-f8ff,fa6e-fa6f,fada-faff,fb07-fb12,fb18-fb1c,fb37,fb3d,fb3f,fb42,fb45,fbc3-fbd2," +
    "fd90-fd91,fdc8-fdce,fdd0-fdef,fe1a-fe1f,fe53,fe67,fe6c-fe6f,fe75,fefd-ff00,ffbf-ffc1,ffc8-ffc9," +
    "ffd0-ffd1,ffd8-ffd9,ffdd-ffdf,ffe7,ffef-fffb,fffe-ffff,1000c,10027,1003b,1003e,1004e-1004f," +
    "1005e-1007f,100fb-100ff,10103-10106,10134-10136,1018f,1019d-1019f,101a1-101cf,101fe-1027f," +
    "1029d-1029f,102d1-102df,102fc-102ff,10324-1032c,1034b-1034f,1037b-1037f,1039e,103c4-103c7," +
    "103d6-103ff,1049e-1049f,104aa-104af,104d4-104d7,104fc-104ff,10528-1052f,10564-1056e,1057b,1058b," +
    "10593,10596,105a2,105b2,105ba,105bd-105bf,105f4-105ff,10737-1073f,10756-1075f,10768-1077f,10786," +
    "107b1,107bb-107ff,10806-10807,10809,10836,10839-1083b,1083d-1083e,10856,1089f-108a6,108b0-108df," +
    "108f3,108f6-108fa,1091c-1091e,1093a-1093e,10940-1097f,109b8-109bb,109d0-109d1,10a04,10a07-10a0b," +
    "10a14,10a18,10a36-10a37,10a3b-10a3e,10a49-10a4f,10a59-10a5f,10aa0-10abf,10ae7-10aea,10af7-10aff," +
    "10b36-10b38,10b56-10b57,10b73-10b77,10b92-10b98,10b9d-10ba8,10bb0-10bff,10c49-10c7f,10cb3-10cbf," +
    "10cf3-10cf9,10d28-10d2f,10d3a-10d3f,10d66-10d68,10d86-10d8d,10d90-10e5f,10e7f,10eaa,10eae-10eaf," +
    "10eb2-10ec1,10ec5-10efb,10f28-10f2f,10f5a-10f6f,10f8a-10faf,10fcc-10fdf,10ff7-10fff,1104e-11051," +
    "11076-1107e,110bd,110c3-110cf,110e9-110ef,110fa-110ff,11135,11148-1114f,11177-1117f,111e0," +
    "111f5-111ff,11212,11242-1127f,11287,11289,1128e,1129e,112aa-112af,112eb-112ef,112fa-112ff,11304," +
    "1130d-1130e,11311-11312,11329,11331,11334,1133a,11345-11346,11349-1134a,1134e-1134f,11351-11356," +
    "11358-1135c,11364-11365,1136d-1136f,11375-1137f,1138a,1138c-1138d,1138f,113b6,113c1,113c3-113c4," +
    "113c6,113cb,113d6,113d9-113e0,113e3-113ff,1145c,11462-1147f,114c8-114cf,114da-1157f,115b6-115b7," +
    "115de-115ff,11645-1164f,1165a-1165f,1166d-1167f,116ba-116bf,116ca-116cf,116e4-116ff,1171b-1171c," +
    "1172c-1172f,11747-117ff,1183c-1189f,118f3-118fe,11907-11908,1190a-1190b,11914,11917,11936," +
    "11939-1193a,11947-1194f,1195a-1199f,119a8-119a9,119d8-119d9,119e5-119ff,11a48-11a4f,11aa3-11aaf," +
    "11af9-11aff,11b0a-11bbf,11be2-11bef,11bfa-11bff,11c09,11c37,11c46-11c4f,11c6d-11c6f,11c90-11c91," +
    "11ca8,11cb7-11cff,11d07,11d0a,11d37-11d39,11d3b,11d3e,11d48-11d4f,11d5a-11d5f,11d66,11d69,11d8f," +
    "11d92,11d99-11d9f,11daa-11edf,11ef9-11eff,11f11,11f3b-11f3d,11f5b-11faf,11fb1-11fbf,11ff2-11ffe," +
    "1239a-123ff,1246f,12475-1247f,12544-12f8f,12ff3-12fff,13430-1343f,13456-1345f,143fb-143ff," +
    "14647-160ff,1613a-167ff,16a39-16a3f,16a5f,16a6a-16a6d,16abf,16aca-16acf,16aee-16aef,16af6-16aff," +
    "16b46-16b4f,16b5a,16b62,16b78-16b7c,16b90-16d3f,16d7a-16e3f,16e9b-16eff,16f4b-16f4e,16f88-16f8e," +
    "16fa0-16fdf,16fe5-16fef,16ff2-16fff,187f8-187ff,18cd6-18cfe,18d09-1afef,1aff4,1affc,1afff," +
    "1b123-1b131,1b133-1b14f,1b153-1b154,1b156-1b163,1b168-1b16f,1b2fc-1bbff,1bc6b-1bc6f,1bc7d-1bc7f," +
    "1bc89-1bc8f,1bc9a-1bc9b,1bca0-1cbff,1ccfa-1ccff,1ceb4-1ceff,1cf2e-1cf2f,1cf47-1cf4f,1cfc4-1cfff," +
    "1d0f6-1d0ff,1d127-1d128,1d173-1d17a,1d1eb-1d1ff,1d246-1d2bf,1d2d4-1d2df,1d2f4-1d2ff,1d357-1d35f," +
    "1d379-1d3ff,1d455,1d49d,1d4a0-1d4a1,1d4a3-1d4a4,1d4a7-1d4a8,1d4ad,1d4ba,1d4bc,1d4c4,1d506," +
    "1d50b-1d50c,1d515,1d51d,1d53a,1d53f,1d545,1d547-1d549,1d551,1d6a6-1d6a7,1d7cc-1d7cd,1da8c-1da9a," +
    "1daa0,1dab0-1deff,1df1f-1df24,1df2b-1dfff,1e007,1e019-1e01a,1e022,1e025,1e02b-1e02f,1e06e-1e08e," +
    "1e090-1e0ff,1e12d-1e12f,1e13e-1e13f,1e14a-1e14d,1e150-1e28f,1e2af-1e2bf,1e2fa-1e2fe,1e300-1e4cf," +
    "1e4fa-1e5cf,1e5fb-1e5fe,1e600-1e7df,1e7e7,1e7ec,1e7ef,1e7ff,1e8c5-1e8c6,1e8d7-1e8ff,1e94c-1e94f," +
    "1e95a-1e95d,1e960-1ec70,1ecb5-1ed00,1ed3e-1edff,1ee04,1ee20,1ee23,1ee25-1ee26,1ee28,1ee33,1ee38," +
    "1ee3a,1ee3c-1ee41,1ee43-1ee46,1ee48,1ee4a,1ee4c,1ee50,1ee53,1ee55-1ee56,1ee58,1ee5a,1ee5c,1ee5e," +
    "1ee60,1ee63,1ee65-1ee66,1ee6b,1ee73,1ee78,1ee7d,1ee7f,1ee8a,1ee9c-1eea0,1eea4,1eeaa,1eebc-1eeef," +
    "1eef2-1efff,1f02c-1f02f,1f094-1f09f,1f0af-1f0b0,1f0c0,1f0d0,1f0f6-1f0ff,1f1ae-1f1e5,1f203-1f20f," +
    "1f23c-1f23f,1f249-1f24f,1f252-1f25f,1f266-1f2ff,1f6d8-1f6db,1f6ed-1f6ef,1f6fd-1f6ff,1f777-1f77a," +
    "1f7da-1f7df,1f7ec-1f7ef,1f7f1-1f7ff,1f80c-1f80f,1f848-1f84f,1f85a-1f85f,1f888-1f88f,1f8ae-1f8af," +
    "1f8bc-1f8bf,1f8c2-1f8ff,1fa54-1fa5f,1fa6e-1fa6f,1fa7d-1fa7f,1fa8a-1fa8e,1fac7-1facd,1fadd-1fade," +
    "1faea-1faef,1faf9-1faff,1fb93,1fbfa-1ffff,2a6e0-2a6ff,2b73a-2b73f,2b81e-2b81f,2cea2-2ceaf," +
    "2ebe1-2ebef,2ee5e-2f7ff,2fa1e-2ffff,3134b-3134f,323b0-e00ff,e01f0-10ffff"
)
var REFUSES = REFUSES_TABLE.split(",").map(function (p) {
    var b = p.split("-")
    return [parseInt(b[0], 16), parseInt(b[b.length - 1], 16)]
})
// Vrai si un point de code de s est refusé (recherche dichotomique ; un substitut seul est refusé aussi)
function refuse(s) {
    s = String(s)
    for (var i = 0; i < s.length; i++) {
        var c = s.charCodeAt(i)
        if (c >= 0xd800 && c <= 0xdbff && i + 1 < s.length) {
            var d = s.charCodeAt(i + 1)
            if (d >= 0xdc00 && d <= 0xdfff) { c = (c - 0xd800) * 0x400 + d - 0xdc00 + 0x10000; i++ }
        }
        var lo = 0, hi = REFUSES.length - 1
        while (lo <= hi) {
            var m = (lo + hi) >> 1
            if (c < REFUSES[m][0]) hi = m - 1
            else if (c > REFUSES[m][1]) lo = m + 1
            else return true
        }
    }
    return false
}
var RESERVES = ["g", "yt", "w", "heure", "time", "mdp", "password", "port", "processus", "session", "sessions",
                "note", "notes", "rappel", "rappels", "reminder", "reminders"]
function analyseLiens(texte) {
    var t = String(texte || ""), vus = {}, liens = []
    if (t.length > 16384) return []
    var lignes = t.split("\n")
    if (lignes[lignes.length - 1] === "") lignes.pop()      // le retour à la ligne final n'est pas une ligne
    if (lignes.length > 50) return []
    for (var i = 0; i < lignes.length; i++) {
        var l = lignes[i].replace(/\r+$/, "")
        if (l === "" || l.charAt(0) === "#") continue
        var c = l.split("\t")
        if (c.length !== 3) continue
        var p = c[0], nom = c[1], url = c[2]
        if (!/^[a-z0-9]{1,12}$/.test(p) || RESERVES.indexOf(p) >= 0 || vus[p]) continue
        if (points(nom).length < 1 || points(nom).length > 40 || refuse(nom)) continue
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
        var l = lignes[i].replace(/\r+$/, "")
        if (l === "" || l.charAt(0) === "#") continue
        var c = l.split("\t")
        if ((c.length !== 3 && c.length !== 4) || (c.length === 4 && c[3] !== "secret")) continue
        var mot = c[0], titre = c[1], clair = deseschapper(c[2])
        if (!/^[a-z0-9]{1,12}$/.test(mot) || RESERVES.indexOf(mot) >= 0 || vus[mot]) continue
        var nt = points(titre).length
        if (nt < 1 || nt > 40 || refuse(titre) || clair === null) continue
        var nc = points(clair).length
        if (nc < 1 || nc > 2000 || refuse(clair.replace(/[\n\t]/g, ""))) continue
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

.pragma library

function barresPourEcran(barres, nomEcran, description) {
    return barres.map(barre => {
        for (const [identifiant, options] of Object.entries(barre.monitor || {})) {
            const nom = options.match ?? identifiant
            if (!nom || (nomEcran !== nom && !description.includes(nom))) continue
            const resultat = Object.assign({}, barre, options, { id: barre.id })
            if (options.capsule_group) {
                const groupes = new Map((barre.capsule_group || []).map(g => [g.id, g]))
                for (const groupe of options.capsule_group) {
                    const base = groupes.get(groupe.id)
                    if (base || Array.isArray(groupe.members))
                        groupes.set(groupe.id, Object.assign({}, base, groupe))
                }
                resultat.capsule_group = Array.from(groupes.values())
            }
            return resultat
        }
        return barre
    })
}

function pastillesCote(barre, cote) {
    const groupes = new Map((barre.capsule_group || []).map(g => [g.id, g]))
    const pastilles = []
    for (const nom of barre[cote] || []) {
        const groupe = nom.startsWith("group:") ? groupes.get(nom.slice(6)) : null
        if (nom.startsWith("group:") && (!groupe || groupe.enabled === false)) continue
        const membres = groupe ? groupe.members : [nom]
        if (membres.length) pastilles.push({ membres, groupe })
    }
    return pastilles
}

function barreControle(barres, definitions, bord) {
    const actives = barres.filter(b => b.enabled !== false && (!bord || (b.position ?? "top") === bord))
    const porte = (b, types) => ["end", "start", "center"].some(cote => pastillesCote(b, cote).some(p =>
        p.membres.some(nom => definitions[nom]?.enabled !== false && types.includes(definitions[nom]?.type ?? nom))))
    return actives.find(b => porte(b, ["network", "bluetooth", "volume", "battery", "nc/batterie:batterie"]))
        ?? actives.find(b => porte(b, ["control-center", "notifications"]))
        ?? actives.find(b => (b.end?.length ?? 0) > 0) ?? actives[0]
}

// hyprctl -j layers donne des coordonnées globales en pixels logiques.
function barreNativeControle(calques, x, y, largeur, hauteur, ancre) {
    const barres = Object.values(calques?.levels ?? {}).flat().filter(c => c.namespace?.startsWith("noctalia-bar-") && c.w > 1 && c.h > 1)
    const barre = (ancre && barres.find(c => x + ancre.x >= c.x && x + ancre.x < c.x + c.w
                                        && y + ancre.y >= c.y && y + ancre.y < c.y + c.h))
        || barres.find(c => c.namespace === "noctalia-bar-default") || barres[0]
    if (!barre) return null
    if (barre.w >= barre.h) {
        const haut = barre.y - y, bas = y + hauteur - barre.y - barre.h
        return haut <= bas ? { bord: "top", emprise: haut + barre.h } : { bord: "bottom", emprise: bas + barre.h }
    }
    const gauche = barre.x - x, droite = x + largeur - barre.x - barre.w
    return gauche <= droite ? { bord: "left", emprise: gauche + barre.w } : { bord: "right", emprise: droite + barre.w }
}

// « top » désigne un déclencheur au-dessus de la carte, « bottom » en dessous, etc.
function placerControle(ancre, bord, largeur, hauteur, gauche, haut, droite, bas, largeurFixe = false) {
    if (!ancre) return { x: bord === "left" ? gauche : droite - largeur,
                         y: bord === "top" ? haut : bas - hauteur, largeur, hauteur, bord }
    const gap = 8
    const ax = ancre.x + ancre.width / 2, ay = ancre.y + ancre.height / 2
    const apresX = Math.max(gauche, ancre.x + ancre.width + gap)
    const avantX = Math.min(droite, ancre.x - gap)
    const apresY = Math.max(haut, ancre.y + ancre.height + gap)
    const avantY = Math.min(bas, ancre.y - gap)
    const dessus = Math.max(0, avantY - haut)
    const dessous = Math.max(0, bas - apresY)
    const aGauche = Math.max(0, avantX - gauche)
    const aDroite = Math.max(0, droite - apresX)
    const place = { top: dessous, bottom: dessus, left: aDroite, right: aGauche }
    const vertical = dessous >= dessus ? ["top", "bottom"] : ["bottom", "top"]
    const horizontal = aDroite >= aGauche ? ["left", "right"] : ["right", "left"]
    const ordre = bord ? [bord, ...vertical, ...horizontal] : [...vertical, ...horizontal]
    const besoin = b => b === "top" || b === "bottom" ? hauteur : largeur
    // Un widget de bord garde son côté tant qu'il y tient ; sinon on essaie les trois autres côtés.
    // S'il n'y a pas de place à taille entière, donner la plus grande zone utilisable (le contenu défile).
    const direction = ordre.find(b => place[b] >= besoin(b))
        ?? (largeurFixe ? vertical : ordre).reduce((a, b) => place[b] / Math.max(1, besoin(b)) > place[a] / Math.max(1, besoin(a)) ? b : a)
    const horizontalement = direction === "left" || direction === "right"
    const l = horizontalement ? Math.min(largeur, place[direction]) : largeur
    const h = horizontalement ? hauteur : Math.min(hauteur, place[direction])
    const x = direction === "left" ? apresX : direction === "right" ? avantX - l
        : Math.max(gauche, Math.min(droite - l, ax - l / 2))
    const y = direction === "top" ? apresY : direction === "bottom" ? avantY - h
        : Math.max(haut, Math.min(bas - h, ay - h / 2))
    return { x: Math.round(x), y: Math.round(y), largeur: l, hauteur: h, bord: direction }
}

function blocs(barres) {
    const resultat = []
    for (const barre of barres) {
        if (barre.enabled === false || (barre.background_opacity ?? 0) > 0) continue
        for (const cote of ["center", "start", "end"]) {
            const pastilles = pastillesCote(barre, cote)
            if (!pastilles.length) continue
            if (cote === "center") {
                resultat.push({ barre, cote, pastilles })
            } else {
                if (cote === "end") pastilles.reverse()
                for (const p of pastilles) resultat.push({ barre, cote, pastilles: [p] })
            }
        }
    }
    return resultat
}

function reserves(barres, reserveIleHaut) {
    const bords = { top: 0, bottom: 0, left: 0, right: 0 }
    for (const barre of barres || []) {
        if (barre.enabled === false || barre.reserve_space === false) continue
        const pos = barre.position ?? "top"
        if (!(pos in bords)) continue
        const zone = Math.round((barre.margin_edge ?? 0) + (barre.thickness ?? 34))
        if (zone > bords[pos]) bords[pos] = zone
    }
    bords.top = Math.max(bords.top, Math.round(reserveIleHaut))
    return bords
}

function chevauche(a, b, marge) {
    const m = marge || 0
    return a.x < b.x + b.width + m && a.x + a.width + m > b.x
        && a.y < b.y + b.height + m && a.y + a.height + m > b.y
}

function occulte(placement, obstacle) {
    return !placement || placement.occulte || (obstacle.width > 0 && obstacle.height > 0 && chevauche(placement, obstacle, 2))
}

// Une seule rangée par bord, calculée d'après l'île au repos. L'animation ne change que l'occultation.
function placer(blocs, tailles, largeur, hauteur, ileRepos) {
    const places = new Array(blocs.length).fill(null)
    const aIle = ileRepos.width > 0 && ileRepos.height > 0
    const occupes = []
    const groupes = new Map()
    for (let i = 0; i < blocs.length; ++i) {
        const { barre, cote } = blocs[i]
        const cle = barre.id + "\0" + cote
        if (!groupes.has(cle)) groupes.set(cle, { barre, cote, indices: [] })
        groupes.get(cle).indices.push(i)
    }

    for (const { barre, cote, indices } of groupes.values()) {
        const vertical = barre.position === "left" || barre.position === "right"
        const inverse = barre.position === "right" || barre.position === "bottom"
        const axe = vertical ? hauteur : largeur
        const profondeur = vertical ? largeur : hauteur
        const visibles = []
        let totalLen = 0
        let maxEp = 0
        for (const i of indices) {
            const t = tailles[i]
            const longueur = t ? (vertical ? t.height : t.width) : 0
            const epaisseur = t ? (vertical ? t.width : t.height) : 0
            if (longueur > 0 && epaisseur > 0 && longueur <= axe && epaisseur <= profondeur) {
                visibles.push({ i, longueur, epaisseur })
                totalLen += longueur
                maxEp = Math.max(maxEp, epaisseur)
            }
        }
        if (!visibles.length) continue

        const v = Math.round(barre.margin_edge ?? 0)
        const margeBord = barre.margin_ends ?? 0
        const marge = Math.max(0, Math.round(typeof margeBord === "string" ? axe * parseFloat(margeBord) / 100 : margeBord))
        const ecartVoulu = Math.max(2, barre.widget_spacing ?? 6)
        const ileSurLigne = aIle && !vertical && !inverse && v < ileRepos.y + ileRepos.height && v + maxEp > ileRepos.y
        const minDispo = ileSurLigne && cote === "end" ? Math.max(marge, Math.ceil(ileRepos.x + ileRepos.width + 6)) : marge
        const maxDispo = ileSurLigne && cote === "start" ? Math.min(axe - marge, Math.floor(ileRepos.x - 6)) : axe - marge
        const span = Math.max(0, maxDispo - minDispo)
        let ecart = ecartVoulu
        if (visibles.length > 1 && span > 0 && totalLen + (visibles.length - 1) * ecartVoulu > span) {
            ecart = Math.max(4, Math.min(ecartVoulu, Math.floor((span - totalLen) / (visibles.length - 1))))
        }

        let curseur = cote === "end" ? axe - marge : marge
        for (const { i, longueur, epaisseur } of visibles) {
            let u
            if (cote === "center") {
                u = Math.floor((axe - longueur) / 2)
            } else if (cote === "end") {
                u = curseur - longueur
                curseur = u - ecart
            } else {
                u = curseur
                curseur = u + longueur + ecart
            }
            const p = inverse ? profondeur - v - epaisseur : v
            const rect = vertical ? { x: p, y: u, width: epaisseur, height: longueur }
                                  : { x: u, y: p, width: longueur, height: epaisseur }
            const horsChamp = u < marge - 1 || u + longueur > axe - marge + 1
            const toucheAutre = occupes.some(o => chevauche(rect, o, 1))
            const occulte = horsChamp || toucheAutre
            places[i] = { x: rect.x, y: rect.y, width: rect.width, height: rect.height, occulte }
            if (!occulte) occupes.push(rect)
        }
    }
    return places
}

function barresFlottantes(barres) {
    return (barres || []).filter(b => b.enabled !== false && (b.background_opacity ?? 0) <= 0)
}

// Un seul arbitrage par écran, dans l'ordre du modèle ; tous les rectangles sont en coordonnées écran.
function placerBarres(barres, tailles, largeur, hauteur, ileRepos) {
    const occupes = []
    return barres.map((barre, i) => {
        const t = tailles[i] || {}
        return placerBarre(barre, t.start, t.center, t.end, largeur, hauteur, ileRepos, occupes)
    })
}

function placerBarre(barre, taillesStart, taillesCenter, taillesEnd, largeur, hauteur, ileRepos, occupes = []) {
    const resultat = {
        start: new Array((taillesStart || []).length).fill(null),
        center: new Array((taillesCenter || []).length).fill(null),
        end: new Array((taillesEnd || []).length).fill(null),
    }
    if (!barre || largeur <= 0 || hauteur <= 0) return resultat

    const pos = barre.position ?? "top"
    const vertical = pos === "left" || pos === "right"
    const inverse = pos === "right" || pos === "bottom"
    const axe = vertical ? hauteur : largeur
    const profondeur = vertical ? largeur : hauteur
    const v = Math.round(barre.margin_edge ?? 0)
    const margeBord = barre.margin_ends ?? 0
    const marge = Math.max(0, Math.round(typeof margeBord === "string" ? axe * parseFloat(margeBord) / 100 : margeBord))
    const margeSecurite = Math.min(marge, 4)
    const ecartVoulu = Math.max(2, barre.widget_spacing ?? 6)
    const epaisseurBarre = Math.ceil(barre.thickness ?? 34)
    const aIle = !!ileRepos && ileRepos.width > 0 && ileRepos.height > 0

    const parCote = { center: taillesCenter || [], start: taillesStart || [], end: taillesEnd || [] }
    for (const cote of ["center", "start", "end"]) {
        const tailles = parCote[cote]
        const visibles = []
        let totalLen = 0
        let maxEp = 0
        for (let idx = 0; idx < tailles.length; ++idx) {
            const i = cote === "end" ? tailles.length - 1 - idx : idx
            const t = tailles[i]
            const longueur = t ? (vertical ? t.height : t.width) : 0
            const epaisseur = t ? (vertical ? t.width : t.height) : 0
            if (longueur > 0 && epaisseur > 0 && longueur <= axe && epaisseur <= profondeur) {
                visibles.push({ i, longueur, epaisseur })
                totalLen += longueur
                maxEp = Math.max(maxEp, epaisseur)
            }
        }
        if (!visibles.length) continue

        const epaisseurLigne = Math.max(epaisseurBarre, maxEp)
        const ileSurLigne = aIle && !vertical && !inverse && v < ileRepos.y + ileRepos.height && v + epaisseurLigne > ileRepos.y
        const minDispo = ileSurLigne && cote === "end" ? Math.max(marge, Math.ceil(ileRepos.x + ileRepos.width + 6)) : marge
        const maxDispo = ileSurLigne && cote === "start" ? Math.min(axe - marge, Math.floor(ileRepos.x - 6)) : axe - marge
        const span = Math.max(0, maxDispo - minDispo)
        let ecart = ecartVoulu
        if (visibles.length > 1 && span > 0 && totalLen + (visibles.length - 1) * ecartVoulu > span) {
            ecart = Math.max(4, Math.min(ecartVoulu, Math.floor((span - totalLen) / (visibles.length - 1))))
        }
        const ecartMin = Math.min(ecart, 2)
        const pLigne = inverse ? profondeur - v - epaisseurLigne : v

        const longueurGroupe = totalLen + (visibles.length - 1) * ecart
        let curseur = cote === "end" ? axe - marge : (cote === "center" ? Math.floor((axe - longueurGroupe) / 2) : marge)
        let voisin = null
        for (const { i, longueur, epaisseur } of visibles) {
            let u
            if (cote === "end") {
                u = curseur - longueur
                curseur = u - ecart
            } else {
                u = curseur
                curseur = u + longueur + ecart
            }
            const p = Math.round(pLigne + (epaisseurLigne - epaisseur) / 2)
            const rect = vertical ? { x: p, y: u, width: epaisseur, height: longueur }
                                  : { x: u, y: p, width: longueur, height: epaisseur }
            const horsChamp = u < marge - 1 || u + longueur > axe - marge + 1
            const toucheAutre = occupes.some(o => chevauche(rect, o, 1))
            const occulteRepos = horsChamp || toucheAutre
            let margeMin = 0
            let margeMax = 0
            if (!occulteRepos) {
                if (cote === "start") {
                    margeMin = voisin === null ? Math.max(0, u - margeSecurite)
                                               : Math.max(0, u - (voisin.u + voisin.longueur) - ecartMin)
                } else if (cote === "end") {
                    margeMax = voisin === null ? Math.max(0, (axe - margeSecurite) - (u + longueur))
                                               : Math.max(0, voisin.u - (u + longueur) - ecartMin)
                }
                voisin = { u, longueur }
                occupes.push(rect)
            }
            resultat[cote][i] = {
                x: rect.x, y: rect.y, width: rect.width, height: rect.height,
                cote, margeMin, margeMax, occulteRepos,
            }
        }
    }
    return resultat
}

function reagirPastille(rectRepos, cote, barrePos, maxDecalage, emprise, modeReaction, bandeFondu, estTitre, minLargeurTitre) {
    if (!rectRepos || barrePos !== "top" || !emprise || emprise.width <= 0 || emprise.height <= 0)
        return { dx: 0, opacite: 1, largeurClip: 0 }
    if (rectRepos.y >= emprise.y + emprise.height || rectRepos.y + rectRepos.height <= emprise.y)
        return { dx: 0, opacite: 1, largeurClip: 0 }

    const margeObs = 8
    const obsL = emprise.x - margeObs
    const obsR = emprise.x + emprise.width + margeObs
    const rx = rectRepos.x
    const rw = rectRepos.width
    const rr = rx + rw
    if (rx >= obsR || rr <= obsL) return { dx: 0, opacite: 1, largeurClip: 0 }

    const mode = modeReaction || "glisser"
    if (mode === "instantane") return { dx: 0, opacite: 0, largeurClip: 0 }

    const bande = bandeFondu > 0 ? bandeFondu : 32
    if (mode === "fondu" || cote === "center") {
        const pen = cote === "start" ? rr - obsL : (cote === "end" ? obsR - rx : Math.min(rr - obsL, obsR - rx))
        const opacite = pen <= 0 ? 1 : Math.max(0, Math.min(1, 1 - pen / bande))
        return { dx: 0, opacite, largeurClip: 0 }
    }

    const marge = maxDecalage > 0 ? maxDecalage : 0
    if (cote === "start") {
        const pen = rr - obsL
        if (pen <= 0) return { dx: 0, opacite: 1, largeurClip: 0 }
        let largeurClip = 0
        let reste = pen
        if (estTitre) {
            const minL = minLargeurTitre > 0 ? minLargeurTitre : 56
            const reductible = Math.max(0, rw - minL)
            if (reductible > 0) {
                const coupe = Math.min(pen, reductible)
                largeurClip = Math.max(minL, rw - coupe)
                reste = pen - coupe
            }
        }
        const glisse = Math.min(reste, marge)
        const debord = reste - glisse
        const opacite = debord > 0 ? Math.max(0, Math.min(1, 1 - debord / bande)) : 1
        return { dx: glisse > 0 ? -glisse : 0, opacite, largeurClip }
    }

    if (cote === "end") {
        const pen = obsR - rx
        if (pen <= 0) return { dx: 0, opacite: 1, largeurClip: 0 }
        const glisse = Math.min(pen, marge)
        const debord = pen - glisse
        const opacite = debord > 0 ? Math.max(0, Math.min(1, 1 - debord / bande)) : 1
        return { dx: glisse, opacite, largeurClip: 0 }
    }

    return { dx: 0, opacite: 1, largeurClip: 0 }
}

// Géométrie stable des pastilles visibles, sans englober les espaces transparents.
function rectanglesPastilles(placements, cote, position, empriseStable, mode, origineX, origineY, titres) {
    const rectangles = []
    for (let i = 0; i < (placements || []).length; ++i) {
        const p = placements[i]
        if (!p || p.occulteRepos) continue
        const maxDec = cote === "start" ? p.margeMin : (cote === "end" ? p.margeMax : 0)
        const r = reagirPastille(p, cote, position, maxDec, empriseStable, mode, 32, !!titres?.[i], 56)
        if (r.opacite <= 0.005) continue
        const width = Math.ceil(r.largeurClip > 0 ? Math.min(p.width, r.largeurClip) : p.width)
        const height = Math.ceil(p.height)
        if (width <= 0 || height <= 0) continue
        rectangles.push({
            x: Math.floor(p.x + r.dx - origineX), y: Math.floor(p.y - origineY),
            width, height, opacite: r.opacite,
        })
    }
    return rectangles
}

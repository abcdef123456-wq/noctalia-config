.pragma library

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

// Disposition sur une seule ligne par bord : les pastilles ne descendent jamais sur une 2e rangée par-dessus les fenêtres.
// Quand l'espace se resserre, l'écart entre pastilles se comprime légèrement ; si l'île ouverte (Spotlight, centre)
// recouvre une pastille intérieure, celle-ci est marquée occulte et s'efface en fondu à sa place.
function placer(blocs, tailles, largeur, hauteur, ile) {
    const places = new Array(blocs.length).fill(null)
    const aIle = !!(ile && ile.width > 0 && ile.height > 0)
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
                if (epaisseur > maxEp) maxEp = epaisseur
            }
        }
        if (!visibles.length) continue

        const v = Math.round(barre.margin_edge ?? 0)
        const margeBord = barre.margin_ends ?? 0
        const marge = Math.max(0, Math.round(typeof margeBord === "string" ? axe * parseFloat(margeBord) / 100 : margeBord))
        const ecartVoulu = Math.max(2, barre.widget_spacing ?? 6)
        const ileSurLigne = aIle && !vertical && !inverse && v < ile.y + ile.height && v + maxEp > ile.y
        const demie = Math.max(0, Math.floor(axe / 2) - marge - 126)
        const minDispo = ileSurLigne && cote === "end" ? Math.max(marge, Math.ceil(ile.x + ile.width + 6)) : marge
        const maxDispo = ileSurLigne && cote === "start" ? Math.min(axe - marge, Math.floor(ile.x - 6)) : axe - marge
        const span = ileSurLigne && ile.width > 320 ? demie : Math.max(0, maxDispo - minDispo)
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
            const toucheIle = aIle && chevauche(rect, ile, 2)
            const toucheAutre = occupes.some(o => chevauche(rect, o, 1))
            const occulte = horsChamp || toucheIle || toucheAutre
            places[i] = { x: rect.x, y: rect.y, width: rect.width, height: rect.height, occulte }
            if (!occulte) occupes.push(rect)
        }
    }
    return places
}

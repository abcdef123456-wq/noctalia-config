import QtQuick
import Quickshell
import Quickshell.Wayland
import "DispositionPanneaux.js" as Disposition

PanelWindow {
    id: fen
    required property var barre
    required property var definitions
    required property string police
    required property var teinte
    required property rect empriseLive
    required property rect empriseStable
    required property rect obstacleRepos
    required property var mouv

    readonly property string position: barre.position ?? "top"
    readonly property bool vertical: position === "left" || position === "right"
    readonly property real margeBord: Math.round(barre.margin_edge ?? 0)
    readonly property real epaisseurBarre: Math.ceil(barre.thickness ?? 34)
    readonly property real epaisseurFenetre: epaisseurBarre + margeBord
    readonly property real origineX: position === "right" && screen ? screen.width - epaisseurFenetre : 0
    readonly property real origineY: position === "bottom" && screen ? screen.height - epaisseurFenetre : 0
    readonly property var pastillesStart: Disposition.pastillesCote(barre, "start")
    readonly property var pastillesCenter: Disposition.pastillesCote(barre, "center")
    readonly property var pastillesEnd: Disposition.pastillesCote(barre, "end")
    readonly property var reactionMasquee: ({ dx: 0, opacite: 0, largeurClip: 0 })
    readonly property real limiteLargeurStart: {
        if (position !== "top" || !screen) return 0
        const axe = screen.width
        const m = barre.margin_ends ?? 0
        const marge = Math.round(typeof m === "string" ? axe * parseFloat(m) / 100 : m)
        const bordIle = Math.min(axe / 2 - 120, obstacleRepos.x - 10)
        return Math.max(80, Math.min(240, bordIle - marge - 130))
    }
    readonly property bool compactEnd: {
        if (position !== "top" || !screen) return false
        if (screen.width < 1450) return true
        let nb = 0
        for (const p of pastillesEnd) nb += p.membres.length
        return nb >= 9
    }

    function aTitre(pastille) {
        return pastille.membres.some(nom => {
            const t = String(definitions[nom]?.type || nom)
            return t === "nc/fenetres:titre" || t === "active_window" || t === "active-window"
        })
    }

    function taillesPour(rep) {
        const t = []
        for (let i = 0; i < rep.count; ++i) {
            const p = rep.itemAt(i)
            t.push(p && p.implicitWidth > 0 && p.implicitHeight > 0
                ? { width: Math.ceil(p.implicitWidth), height: Math.ceil(p.implicitHeight) }
                : null)
        }
        return t
    }

    // Positions au repos calculées hors animation (jamais liées à empriseLive).
    readonly property var dispositionRepos: {
        if (!screen || screen.width <= 0 || screen.height <= 0)
            return { start: [], center: [], end: [] }
        repStart.revision; repCenter.revision; repEnd.revision
        return Disposition.placerBarre(
            barre,
            taillesPour(repStart),
            taillesPour(repCenter),
            taillesPour(repEnd),
            screen.width,
            screen.height,
            obstacleRepos
        )
    }

    // Zones de clic calculées uniquement sur empriseStable : zéro commit set_input_region pendant les ressorts.
    function zoneMasque(placements, pastilles, cote) {
        if (!placements || !placements.length) return Qt.rect(0, 0, 0, 0)
        const mode = mouv ? mouv.reactionBarre : "glisser"
        let minX = 1e9, minY = 1e9, maxR = -1e9, maxB = -1e9
        let trouve = false
        for (let i = 0; i < placements.length; ++i) {
            const p = placements[i]
            if (!p || p.occulteRepos) continue
            const maxDec = cote === "start" ? p.margeMin : (cote === "end" ? p.margeMax : 0)
            const estTitre = pastilles && pastilles[i] ? aTitre(pastilles[i]) : false
            const r = Disposition.reagirPastille(p, cote, position, maxDec, empriseStable, mode, 32, estTitre, 56)
            if (r.opacite <= 0.15) continue
            const lx = Math.floor(p.x + r.dx - origineX)
            const ly = Math.floor(p.y - origineY)
            const lw = Math.ceil(r.largeurClip > 0 ? Math.min(p.width, r.largeurClip) : p.width)
            const lh = Math.ceil(p.height)
            if (lw <= 0 || lh <= 0) continue
            minX = Math.min(minX, lx)
            minY = Math.min(minY, ly)
            maxR = Math.max(maxR, lx + lw)
            maxB = Math.max(maxB, ly + lh)
            trouve = true
        }
        return trouve ? Qt.rect(minX, minY, maxR - minX, maxB - minY) : Qt.rect(0, 0, 0, 0)
    }

    readonly property rect zoneStart: zoneMasque(dispositionRepos.start, pastillesStart, "start")
    readonly property rect zoneCenter: zoneMasque(dispositionRepos.center, pastillesCenter, "center")
    readonly property rect zoneEnd: zoneMasque(dispositionRepos.end, pastillesEnd, "end")

    anchors {
        top: position === "top" || vertical
        bottom: position === "bottom" || vertical
        left: position === "left" || !vertical
        right: position === "right" || !vertical
    }
    implicitWidth: vertical ? epaisseurFenetre : 0
    implicitHeight: vertical ? 0 : epaisseurFenetre
    exclusionMode: ExclusionMode.Ignore
    color: "transparent"
    WlrLayershell.namespace: "nc-panneau-" + barre.id
    WlrLayershell.layer: barre.layer === "overlay" ? WlrLayer.Overlay : WlrLayer.Top
    mask: Region { item: masqueStart; Region { item: masqueCenter } Region { item: masqueEnd } }

    Item { id: masqueStart; x: fen.zoneStart.x; y: fen.zoneStart.y; width: fen.zoneStart.width; height: fen.zoneStart.height }
    Item { id: masqueCenter; x: fen.zoneCenter.x; y: fen.zoneCenter.y; width: fen.zoneCenter.width; height: fen.zoneCenter.height }
    Item { id: masqueEnd; x: fen.zoneEnd.x; y: fen.zoneEnd.y; width: fen.zoneEnd.width; height: fen.zoneEnd.height }

    Repeater {
        id: repStart
        property int revision: 0
        onItemAdded: revision++
        onItemRemoved: revision++
        model: fen.pastillesStart
        delegate: PastilleBarre {
            id: itemStart
            required property var modelData
            required property int index
            readonly property var place: fen.dispositionRepos.start[index] || null
            readonly property bool estTitre: fen.aTitre(modelData)
            readonly property var reaction: place && !place.occulteRepos
                ? Disposition.reagirPastille(place, "start", fen.position, place.margeMin,
                      fen.empriseLive, fen.mouv ? fen.mouv.reactionBarre : "glisser", 32, estTitre, 56)
                : fen.reactionMasquee
            modele: modelData
            barre: fen.barre
            definitions: fen.definitions
            ecran: fen.screen
            police: fen.police
            teinte: fen.teinte
            limiteLargeur: fen.limiteLargeurStart
            largeurClip: reaction.largeurClip
            x: place ? place.x - fen.origineX : 0
            y: place ? place.y - fen.origineY : 0
            visible: implicitWidth > 0 && !!place && !place.occulteRepos && reaction.opacite > 0.005
            opacity: reaction.opacite
            enabled: !!place && !place.occulteRepos && reaction.opacite > 0.15
            transform: Translate { x: itemStart.reaction.dx }
        }
    }

    Repeater {
        id: repCenter
        property int revision: 0
        onItemAdded: revision++
        onItemRemoved: revision++
        model: fen.pastillesCenter
        delegate: PastilleBarre {
            id: itemCenter
            required property var modelData
            required property int index
            readonly property var place: fen.dispositionRepos.center[index] || null
            readonly property var reaction: place && !place.occulteRepos
                ? Disposition.reagirPastille(place, "center", fen.position, 0,
                      fen.empriseLive, fen.mouv ? fen.mouv.reactionBarre : "glisser", 32, false, 56)
                : fen.reactionMasquee
            modele: modelData
            barre: fen.barre
            definitions: fen.definitions
            ecran: fen.screen
            police: fen.police
            teinte: fen.teinte
            x: place ? place.x - fen.origineX : 0
            y: place ? place.y - fen.origineY : 0
            visible: implicitWidth > 0 && !!place && !place.occulteRepos && reaction.opacite > 0.005
            opacity: reaction.opacite
            enabled: !!place && !place.occulteRepos && reaction.opacite > 0.15
            transform: Translate { x: itemCenter.reaction.dx }
        }
    }

    Repeater {
        id: repEnd
        property int revision: 0
        onItemAdded: revision++
        onItemRemoved: revision++
        model: fen.pastillesEnd
        delegate: PastilleBarre {
            id: itemEnd
            required property var modelData
            required property int index
            readonly property var place: fen.dispositionRepos.end[index] || null
            readonly property var reaction: place && !place.occulteRepos
                ? Disposition.reagirPastille(place, "end", fen.position, place.margeMax,
                      fen.empriseLive, fen.mouv ? fen.mouv.reactionBarre : "glisser", 32, false, 56)
                : fen.reactionMasquee
            modele: modelData
            barre: fen.barre
            definitions: fen.definitions
            ecran: fen.screen
            police: fen.police
            teinte: fen.teinte
            compact: fen.compactEnd
            x: place ? place.x - fen.origineX : 0
            y: place ? place.y - fen.origineY : 0
            visible: implicitWidth > 0 && !!place && !place.occulteRepos && reaction.opacite > 0.005
            opacity: reaction.opacite
            enabled: !!place && !place.occulteRepos && reaction.opacite > 0.15
            transform: Translate { x: itemEnd.reaction.dx }
        }
    }
}

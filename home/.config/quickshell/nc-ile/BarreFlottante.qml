import QtQuick
import QtQml.Models
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
    readonly property point origine: Qt.point(origineX, origineY)
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

    // Les mesures restent disponibles même lorsque la fenêtre n'est pas mappée.
    readonly property var tailles: {
        repStart.revision; repCenter.revision; repEnd.revision
        return { start: taillesPour(repStart), center: taillesPour(repCenter), end: taillesPour(repEnd) }
    }
    property var dispositionRepos: screen
        ? Disposition.placerBarre(barre, tailles.start, tailles.center, tailles.end,
                                 screen.width, screen.height, obstacleRepos)
        : ({ start: [], center: [], end: [] })

    // Ni le masque ni le mapping Wayland ne dépendent des frames du ressort.
    readonly property var rectanglesRendus: {
        const rectangles = []
        for (const cote of ["start", "center", "end"]) {
            const pastilles = cote === "start" ? pastillesStart : (cote === "center" ? pastillesCenter : pastillesEnd)
            rectangles.push(...Disposition.rectanglesPastilles(
                dispositionRepos[cote], cote, position, empriseStable,
                mouv ? mouv.reactionBarre : "glisser", origineX, origineY, pastilles.map(p => aTitre(p))))
        }
        return rectangles
    }
    readonly property int nombrePastillesRendues: rectanglesRendus.length
    readonly property var rectanglesMasque: rectanglesRendus.filter(r => r.opacite > 0.15)
    // Tenue à la main par morceauxMasque : une Region détruite sort de la liste de Quickshell sans signal, et le
    // compositeur gardait l'ancienne zone d'entrée. Chaque retrait est donc écrit avant la destruction.
    property var regionsMasque: []
    // Le calque existe dès qu'une pastille a sa place au repos : l'île qui les occulte un instant ne le démonte pas,
    // sinon les pastilles ne pourraient pas revenir pendant le ressort de fermeture.
    visible: ["start", "center", "end"].some(cote => (dispositionRepos[cote] || []).some(p => p && !p.occulteRepos))

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
    mask: Region { regions: fen.regionsMasque }

    Instantiator {
        id: morceauxMasque
        onObjectAdded: (index, region) => fen.regionsMasque = fen.regionsMasque.concat([region])
        onObjectRemoved: (index, region) => fen.regionsMasque = fen.regionsMasque.filter(r => r !== region)
        model: fen.rectanglesMasque
        delegate: Region {
            required property var modelData
            x: modelData.x
            y: modelData.y
            width: modelData.width
            height: modelData.height
        }
    }

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
            origine: fen.origine
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
            origine: fen.origine
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
            origine: fen.origine
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

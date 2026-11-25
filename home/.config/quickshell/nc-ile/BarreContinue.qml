import QtQuick
import Quickshell
import Quickshell.Wayland
import "DispositionPanneaux.js" as Disposition
import "WidgetBarreActions.js" as Actions

PanelWindow {
    id: fen
    required property var barre
    required property var definitions
    required property string police
    required property var teinte
    required property rect obstacle
    required property rect obstacleRepos
    property rect empriseLive: obstacle
    property rect empriseStable: obstacle
    property var mouv: Mouvement.pourEcran(screen ? screen.name : "")
    readonly property string position: barre.position ?? "top"
    readonly property bool vertical: position === "left" || position === "right"
    readonly property real epaisseur: Math.ceil(barre.thickness ?? 36)
    readonly property real margeBord: Math.round(barre.margin_edge ?? 0)
    readonly property real margeBouts: {
        const m = barre.margin_ends ?? 0
        const axe = screen ? (vertical ? screen.height : screen.width) : 0
        return Math.round(typeof m === "string" ? axe * parseFloat(m) / 100 : m)
    }
    readonly property point origine: Qt.point(
        vertical ? (position === "right" && screen ? screen.width - margeBord - epaisseur : margeBord) : margeBouts,
        vertical ? margeBouts : (position === "bottom" && screen ? screen.height - margeBord - epaisseur : margeBord))
    readonly property real pad: Math.round(barre.padding ?? 12)
    readonly property real espacement: barre.capsule ? Math.max(2, barre.widget_spacing ?? 6)
                                                     : Math.max(8, barre.widget_spacing ?? 8)
    readonly property real glisseBord: Math.max(0, pad - Math.min(pad, 4))
    readonly property real glisseVoisin: Math.max(0, espacement - Math.min(espacement, 2))
    readonly property var pastillesStart: Disposition.pastillesCote(barre, "start")
    readonly property var pastillesCenter: Disposition.pastillesCote(barre, "center")
    readonly property var pastillesEnd: Disposition.pastillesCote(barre, "end")
    readonly property var reactionNeutre: ({ dx: 0, opacite: 1, largeurClip: 0 })
    readonly property real disponibleStart: {
        if (!screen || vertical) return 0
        const bord = partageLigne(obstacleRepos) ? Math.min(screen.width / 2 - 120, obstacleRepos.x - 10) : screen.width * 0.45
        return Math.max(80, bord - margeBouts - pad)
    }
    readonly property bool compactEnd: {
        if (vertical || position !== "top" || !screen) return false
        if (screen.width < 1450) return true
        let nb = 0
        for (const p of pastillesEnd) nb += p.membres.length
        return nb >= 9
    }

    function partageLigne(rect) {
        return position === "top" && rect.width > 0 && rect.height > 0
            && margeBord < rect.y + rect.height && margeBord + epaisseur > rect.y
    }

    function aTitre(pastille) {
        return pastille.membres.some(nom => {
            const t = String(definitions[nom]?.type || nom)
            return t === "nc/fenetres:titre" || t === "active_window" || t === "active-window"
        })
    }
    function reagir(lx, ly, w, h, cote, maxDec, estTitre) {
        if (position !== "top" || w <= 0 || h <= 0) return reactionNeutre
        return Disposition.reagirPastille(
            { x: margeBouts + lx, y: margeBord + ly, width: w, height: h },
            cote, position, maxDec, empriseLive, mouv ? mouv.reactionBarre : "glisser", 32, estTitre, 56
        )
    }

    anchors {
        top: position === "top" || vertical
        bottom: position === "bottom" || vertical
        left: position === "left" || !vertical
        right: position === "right" || !vertical
    }
    margins {
        top: position === "top" ? margeBord : (vertical ? margeBouts : 0)
        bottom: position === "bottom" ? margeBord : (vertical ? margeBouts : 0)
        left: position === "left" ? margeBord : (!vertical ? margeBouts : 0)
        right: position === "right" ? margeBord : (!vertical ? margeBouts : 0)
    }
    implicitWidth: vertical ? epaisseur : 0
    implicitHeight: vertical ? 0 : epaisseur
    exclusionMode: ExclusionMode.Ignore
    color: "transparent"
    WlrLayershell.namespace: "nc-panneau-" + barre.id + "-barre"
    WlrLayershell.layer: barre.layer === "overlay" ? WlrLayer.Overlay : WlrLayer.Top

    Rectangle {
        id: fond
        anchors.fill: parent
        color: Qt.alpha(fen.teinte("surface", Couleurs.fond), fen.barre.background_opacity ?? 1)
        radius: fen.barre.radius ?? 12

        MouseArea {
            anchors.fill: parent
            acceptedButtons: Qt.LeftButton | Qt.RightButton | Qt.MiddleButton
            onClicked: e => {
                const actions = fen.barre.dead_zone?.actions
                if (!actions) return
                const cle = e.button === Qt.RightButton ? "right" : e.button === Qt.MiddleButton ? "middle" : "left"
                Actions.lancerDepuisBarre(actions[cle], (nom, repli) => {
                    const cible = repli ? Etat.pageOu(nom, repli) : nom
                    if (!Etat.estPageControle(cible)) return false
                    Etat.basculerControle(fen.screen.name, cible, fen.position,
                        Qt.rect(fen.origine.x + e.x, fen.origine.y + e.y, 1, 1))
                    return true
                })
            }
        }

        Grid {
            id: startFlow
            x: fen.vertical ? Math.round((fond.width - width) / 2) : fen.pad
            y: fen.vertical ? fen.pad : Math.round((fond.height - height) / 2)
            columns: fen.vertical ? 1 : Math.max(1, repStart.count)
            horizontalItemAlignment: Grid.AlignHCenter
            verticalItemAlignment: Grid.AlignVCenter
            spacing: fen.espacement
            Repeater {
                id: repStart
                model: fen.pastillesStart
                delegate: PastilleBarre {
                    id: itemStart
                    required property var modelData
                    required property int index
                    readonly property bool estTitre: fen.aTitre(modelData)
                    readonly property var reaction: fen.reagir(startFlow.x + itemStart.x, startFlow.y + itemStart.y,
                        itemStart.width, itemStart.height, "start",
                        index === 0 ? fen.glisseBord : fen.glisseVoisin, estTitre)
                    modele: modelData
                    barre: fen.barre
                    definitions: fen.definitions
                    ecran: fen.screen
                    origine: fen.origine
                    police: fen.police
                    teinte: fen.teinte
                    limiteLargeur: {
                        if (fen.vertical || !fen.disponibleStart || !estTitre) return 0
                        let autres = 0
                        for (let i = 0; i < repStart.count; ++i) {
                            if (i === index || fen.aTitre(fen.pastillesStart[i])) continue
                            const it = repStart.itemAt(i)
                            if (it && it.visible) autres += it.implicitWidth + fen.espacement
                        }
                        return Math.max(64, fen.disponibleStart - autres)
                    }
                    largeurClip: reaction.largeurClip
                    fondClip: fond.color
                    opacity: reaction.opacite
                    enabled: reaction.opacite > 0.15
                    transform: Translate { x: itemStart.reaction.dx }
                }
            }
        }

        Grid {
            id: centerFlow
            x: Math.round((fond.width - width) / 2)
            y: Math.round((fond.height - height) / 2)
            columns: fen.vertical ? 1 : Math.max(1, repCenter.count)
            horizontalItemAlignment: Grid.AlignHCenter
            verticalItemAlignment: Grid.AlignVCenter
            spacing: fen.espacement
            Repeater {
                id: repCenter
                model: fen.pastillesCenter
                delegate: PastilleBarre {
                    id: itemCenter
                    required property var modelData
                    readonly property var reaction: fen.reagir(centerFlow.x + itemCenter.x, centerFlow.y + itemCenter.y,
                        itemCenter.width, itemCenter.height, "center", 0, false)
                    modele: modelData
                    barre: fen.barre
                    definitions: fen.definitions
                    ecran: fen.screen
                    origine: fen.origine
                    police: fen.police
                    teinte: fen.teinte
                    fondClip: fond.color
                    opacity: reaction.opacite
                    enabled: reaction.opacite > 0.15
                    transform: Translate { x: itemCenter.reaction.dx }
                }
            }
        }

        Grid {
            id: endFlow
            x: fen.vertical ? Math.round((fond.width - width) / 2) : Math.max(fen.pad, fond.width - width - fen.pad)
            y: fen.vertical ? Math.max(fen.pad, fond.height - height - fen.pad) : Math.round((fond.height - height) / 2)
            columns: fen.vertical ? 1 : Math.max(1, repEnd.count)
            horizontalItemAlignment: Grid.AlignHCenter
            verticalItemAlignment: Grid.AlignVCenter
            spacing: fen.espacement
            Repeater {
                id: repEnd
                model: fen.pastillesEnd
                delegate: PastilleBarre {
                    id: itemEnd
                    required property var modelData
                    required property int index
                    readonly property var reaction: fen.reagir(endFlow.x + itemEnd.x, endFlow.y + itemEnd.y,
                        itemEnd.width, itemEnd.height, "end",
                        index === repEnd.count - 1 ? fen.glisseBord : fen.glisseVoisin, false)
                    modele: modelData
                    barre: fen.barre
                    definitions: fen.definitions
                    ecran: fen.screen
                    police: fen.police
                    origine: fen.origine
                    teinte: fen.teinte
                    compact: fen.compactEnd
                    fondClip: fond.color
                    opacity: reaction.opacite
                    enabled: reaction.opacite > 0.15
                    transform: Translate { x: itemEnd.reaction.dx }
                }
            }
        }
    }
}

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
    readonly property string position: barre.position ?? "top"
    readonly property bool vertical: position === "left" || position === "right"
    readonly property real epaisseur: Math.ceil(barre.thickness ?? 36)
    readonly property real margeBord: Math.round(barre.margin_edge ?? 0)
    readonly property real margeBouts: {
        const m = barre.margin_ends ?? 0
        const axe = screen ? (vertical ? screen.height : screen.width) : 0
        return Math.round(typeof m === "string" ? axe * parseFloat(m) / 100 : m)
    }
    readonly property real pad: Math.round(barre.padding ?? 12)
    readonly property real espacement: barre.capsule ? Math.max(2, barre.widget_spacing ?? 6)
                                                     : Math.max(8, barre.widget_spacing ?? 8)
    readonly property var pastillesStart: Disposition.pastillesCote(barre, "start")
    readonly property var pastillesCenter: Disposition.pastillesCote(barre, "center")
    readonly property var pastillesEnd: Disposition.pastillesCote(barre, "end")
    readonly property bool bloqueParIle: !vertical && position === "top" && obstacle.width > 0 && obstacle.height > 0
                                         && margeBord < obstacle.y + obstacle.height && margeBord + epaisseur > obstacle.y
    readonly property real disponibleStart: {
        if (!screen || vertical) return 0
        const bord = bloqueParIle ? Math.min(screen.width / 2 - 120, obstacle.x - 10) : screen.width * 0.45
        return Math.max(80, bord - margeBouts - pad)
    }
    readonly property bool compactEnd: {
        if (vertical || position !== "top" || !screen) return false
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
    function estOcculte(conteneurX, itemX, itemW) {
        if (!bloqueParIle || itemW <= 0) return false
        const gx = margeBouts + conteneurX + itemX
        return gx < obstacle.x + obstacle.width && gx + itemW > obstacle.x
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
                if (typeof actions[cle] === "string") Actions.lancer(actions[cle])
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
                    modele: modelData
                    barre: fen.barre
                    definitions: fen.definitions
                    ecran: fen.screen
                    police: fen.police
                    teinte: fen.teinte
                    limiteLargeur: {
                        if (fen.vertical || !fen.disponibleStart || !fen.aTitre(modelData)) return 0
                        let autres = 0
                        for (let i = 0; i < repStart.count; ++i) {
                            if (i === index || fen.aTitre(fen.pastillesStart[i])) continue
                            const it = repStart.itemAt(i)
                            if (it && it.visible) autres += it.implicitWidth + fen.espacement
                        }
                        return Math.max(64, fen.disponibleStart - autres)
                    }
                    readonly property bool masque: fen.estOcculte(startFlow.x, itemStart.x, itemStart.width)
                    opacity: masque ? 0 : 1
                    enabled: !masque
                    Behavior on opacity { NumberAnimation { duration: 120 } }
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
                    modele: modelData
                    barre: fen.barre
                    definitions: fen.definitions
                    ecran: fen.screen
                    police: fen.police
                    teinte: fen.teinte
                    readonly property bool masque: fen.estOcculte(centerFlow.x, itemCenter.x, itemCenter.width)
                    opacity: masque ? 0 : 1
                    enabled: !masque
                    Behavior on opacity { NumberAnimation { duration: 120 } }
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
                    modele: modelData
                    barre: fen.barre
                    definitions: fen.definitions
                    ecran: fen.screen
                    police: fen.police
                    teinte: fen.teinte
                    compact: fen.compactEnd
                    readonly property bool masque: fen.estOcculte(endFlow.x, itemEnd.x, itemEnd.width)
                    opacity: masque ? 0 : 1
                    enabled: !masque
                    Behavior on opacity { NumberAnimation { duration: 120 } }
                }
            }
        }
    }
}

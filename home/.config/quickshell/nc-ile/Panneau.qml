import QtQuick
import Quickshell
import Quickshell.Wayland
import "DispositionPanneaux.js" as Disposition

PanelWindow {
    id: fen
    required property var bloc
    required property var definitions
    required property string police
    required property var teinte
    required property rect obstacle
    property var placement: null
    property real limiteLargeur: 0
    property bool compact: false
    readonly property var barre: bloc.barre
    readonly property bool vertical: barre.position === "left" || barre.position === "right"
    readonly property bool occulte: Disposition.occulte(placement, obstacle)
    readonly property var mesure: {
        repeater.revision
        let longueur = 0
        let travers = 0
        let n = 0
        for (let i = 0; i < repeater.count; ++i) {
            const p = repeater.itemAt(i)
            if (!p || p.implicitWidth <= 0 || p.implicitHeight <= 0) continue
            longueur += vertical ? p.implicitHeight : p.implicitWidth
            travers = Math.max(travers, vertical ? p.implicitWidth : p.implicitHeight)
            ++n
        }
        if (n === 0) return Qt.size(0, 0)
        longueur += (n - 1) * contenu.spacing
        travers = Math.ceil(Math.max(travers, barre.thickness ?? 34))
        return vertical ? Qt.size(travers, Math.ceil(longueur)) : Qt.size(Math.ceil(longueur), travers)
    }

    anchors.top: true
    anchors.left: true
    margins {
        left: placement ? placement.x : 0
        top: placement ? placement.y : 0
    }
    implicitWidth: Math.max(1, mesure.width)
    implicitHeight: Math.max(1, mesure.height)
    visible: placement !== null
    exclusionMode: ExclusionMode.Ignore
    color: "transparent"
    WlrLayershell.namespace: "nc-panneau-" + barre.id + "-" + bloc.cote
    WlrLayershell.layer: barre.layer === "overlay" ? WlrLayer.Overlay : WlrLayer.Top
    mask: Region { item: fen.occulte ? vide : contenu }

    Item { id: vide; width: 0; height: 0 }

    Grid {
        id: contenu
        anchors.centerIn: parent
        columns: fen.vertical ? 1 : Math.max(1, repeater.count)
        horizontalItemAlignment: Grid.AlignHCenter
        verticalItemAlignment: Grid.AlignVCenter
        spacing: fen.barre.widget_spacing ?? 6
        opacity: fen.occulte ? 0 : 1
        enabled: !fen.occulte
        Behavior on opacity { NumberAnimation { duration: 120 } }
        Repeater {
            id: repeater
            property int revision: 0
            onItemAdded: revision++
            onItemRemoved: revision++
            model: fen.bloc.pastilles
            delegate: PastilleBarre {
                required property var modelData
                modele: modelData
                barre: fen.barre
                definitions: fen.definitions
                ecran: fen.screen
                police: fen.police
                teinte: fen.teinte
                limiteLargeur: fen.limiteLargeur
                compact: fen.compact
            }
        }
    }
}

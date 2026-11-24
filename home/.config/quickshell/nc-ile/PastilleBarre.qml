import QtQuick

Item {
    id: pastille
    required property var modele
    required property var barre
    required property var definitions
    required property var ecran
    required property string police
    required property var teinte
    property real limiteLargeur: 0
    property bool compact: false
    readonly property bool vertical: barre.position === "left" || barre.position === "right"
    readonly property var groupe: modele.groupe
    readonly property var widget: groupe ? ({}) : (definitions[modele.membres[0]] || {})
    readonly property bool capsule: !!groupe || (widget.capsule ?? barre.capsule ?? false)
    readonly property real espacement: groupe ? (groupe.spacing ?? Math.min(barre.widget_spacing ?? 6, 7))
                                              : (barre.widget_spacing ?? 6)
    readonly property real padding: capsule ? (groupe?.padding ?? widget.capsule_padding ?? barre.capsule_padding ?? 8) : 0
    readonly property real epaisseur: Math.round((barre.thickness ?? 34) * (capsule ? (barre.capsule_thickness ?? 0.76) : 1))
    readonly property var mesure: {
        repeater.revision
        let longueur = 0
        let travers = 0
        let n = 0
        for (let i = 0; i < repeater.count; ++i) {
            const w = repeater.itemAt(i)
            if (!w || w.implicitWidth <= 0 || w.implicitHeight <= 0) continue
            longueur += vertical ? w.implicitHeight : w.implicitWidth
            travers = Math.max(travers, vertical ? w.implicitWidth : w.implicitHeight)
            ++n
        }
        return n ? Qt.size(longueur + espacement * (n - 1) + padding * 2, Math.max(travers, epaisseur)) : Qt.size(0, 0)
    }
    implicitWidth: vertical ? mesure.height : mesure.width
    implicitHeight: vertical ? mesure.width : mesure.height
    width: implicitWidth
    height: implicitHeight
    visible: implicitWidth > 0

    Rectangle {
        anchors.fill: parent
        visible: pastille.capsule
        radius: pastille.groupe?.radius ?? pastille.widget.capsule_radius ?? pastille.barre.capsule_radius
                ?? Math.min(width, height) / 2
        color: Qt.alpha(pastille.teinte(pastille.groupe ? (pastille.groupe.fill ?? pastille.barre.capsule_fill ?? "surface_container")
                          : (pastille.widget.capsule_fill ?? pastille.barre.capsule_fill ?? "surface_container"), Couleurs.carte),
                        pastille.groupe?.opacity ?? pastille.widget.capsule_opacity ?? pastille.barre.capsule_opacity ?? 1)
        readonly property var cleBordure: pastille.groupe?.border ?? pastille.widget.capsule_border ?? pastille.barre.capsule_border
        border.color: pastille.teinte(cleBordure, "transparent")
        border.width: cleBordure ? (pastille.groupe?.border_width ?? pastille.widget.capsule_border_width ?? pastille.barre.capsule_border_width ?? 1) : 0
    }
    Grid {
        anchors.centerIn: parent
        columns: pastille.vertical ? 1 : Math.max(1, repeater.count)
        horizontalItemAlignment: Grid.AlignHCenter
        verticalItemAlignment: Grid.AlignVCenter
        spacing: pastille.espacement
        Repeater {
            id: repeater
            property int revision: 0
            onItemAdded: revision++
            onItemRemoved: revision++
            model: pastille.modele.membres
            delegate: WidgetBarre {
                required property string modelData
                nom: modelData
                definition: pastille.definitions[nom] || ({})
                ecran: pastille.ecran
                vertical: pastille.vertical
                position: pastille.barre.position ?? "top"
                resoudreTeinte: pastille.teinte
                premierPlan: pastille.teinte(definition.color ?? pastille.groupe?.foreground ?? definition.capsule_foreground
                                             ?? pastille.barre.capsule_foreground ?? pastille.barre.color ?? "on_surface", Couleurs.texte)
                tailleTexte: Math.round(12 * (definition.font_scale ?? pastille.barre.font_scale ?? 1))
                graisse: definition.font_weight ?? pastille.barre.font_weight ?? 400
                police: definition.font_family ?? pastille.barre.font_family ?? pastille.police
                limiteLargeur: pastille.limiteLargeur > 0 ? Math.max(48, pastille.limiteLargeur - pastille.padding * 2) : 0
                compact: pastille.compact
                width: implicitWidth
                height: implicitHeight
            }
        }
    }
}

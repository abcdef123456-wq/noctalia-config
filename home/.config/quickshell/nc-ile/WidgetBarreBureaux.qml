import QtQuick
import Quickshell.Hyprland
import "WidgetBarreFenetres.js" as Fenetres

Item {
    id: w
    required property Item barre
    readonly property var mouv: Mouvement.pourEcran(barre.ecran ? barre.ecran.name : "")
    readonly property var options: barre.definition
    readonly property var moniteur: barre.ecran ? Hyprland.monitorFor(barre.ecran) : Hyprland.focusedMonitor
    readonly property var sorties: options.monitors || (options.show_all_outputs ? ["*"] : [])
    readonly property var bureaux: {
        const nom = moniteur ? moniteur.name : ""
        return Hyprland.workspaces.values.filter(b => !b.name.startsWith("special:") && b.id > 0
            && (sorties.length ? !!b.monitor && (sorties.indexOf("*") >= 0 || sorties.indexOf(b.monitor.name) >= 0) : b.monitor === moniteur)
            && (options.hide_when_empty !== true || b.active || b.toplevels.values.length > 0)).sort((a, b) => {
                if (a.monitor === b.monitor) return a.id - b.id
                if (a.monitor && a.monitor.name === nom) return -1
                if (b.monitor && b.monitor.name === nom) return 1
                const i = a.monitor ? sorties.indexOf(a.monitor.name) : -1, j = b.monitor ? sorties.indexOf(b.monitor.name) : -1
                return i !== j ? i - j : a.id - b.id
            })
    }
    readonly property bool affiche: bureaux.length > 0
    readonly property string style: options.style || "regular"
    readonly property string separateur: options.separator || ""
    readonly property real epaisseur: Math.max(6, barre.tailleIcone * Number(options.pill_scale ?? 1))
    implicitWidth: ligne.implicitWidth
    implicitHeight: ligne.implicitHeight

    function changer(pas) {
        if (!bureaux.length) return
        let i = bureaux.indexOf(moniteur ? moniteur.activeWorkspace : Hyprland.focusedWorkspace)
        if (i < 0) i = 0
        bureaux[(i + pas + bureaux.length) % bureaux.length].activate()
    }
    Grid {
        id: ligne
        columns: w.barre.vertical ? 1 : Math.max(1, w.bureaux.length)
        horizontalItemAlignment: Grid.AlignHCenter
        verticalItemAlignment: Grid.AlignVCenter
        spacing: 4
        Repeater {
            model: w.bureaux
            Item {
                id: cel
                required property var modelData
                required property int index
                readonly property bool actif: modelData.active && (w.options.focused_output_only !== true || modelData.focused)
                readonly property bool occupe: modelData.toplevels.values.length > 0
                readonly property bool focusIndice: w.style === "focus_hint"
                readonly property bool point: focusIndice && !actif
                readonly property bool afficherTexte: w.options.show_labels !== false && !point
                    && (focusIndice || w.options.labels_only_when_occupied !== true || actif || occupe)
                readonly property var fenetre: focusIndice && actif && w.options.show_icons !== false ?
                    (modelData.focused ? Hyprland.activeToplevel : modelData.toplevels.values.find(t => t.activated)) : null
                readonly property string label: {
                    const t = w.options.label_source === "name" ? modelData.name : String(modelData.id)
                    return /^\d+$/.test(t) ? t : Array.from(t).slice(0, Number(w.options.max_label_chars ?? 1)).join("")
                }
                readonly property color encre: modelData.urgent ? w.barre.teinte(w.options.urgent_color || "error", Couleurs.rouge)
                    : actif ? w.barre.teinte(w.options.focused_color || "primary", Couleurs.accent)
                    : occupe ? w.barre.teinte(w.options.occupied_color || "secondary", w.barre.premierPlan)
                    : w.barre.teinte(w.options.empty_color || "outline", Couleurs.texteSec)
                readonly property color fond: zone.containsMouse && w.options.change_color_on_hover !== false ? Couleurs.accentClair : encre
                readonly property real longueur: point ? 7 : Math.max(w.epaisseur * Number(actif ? w.options.active_pill_size ?? 2.2 : w.options.inactive_pill_size ?? 1),
                    (w.barre.vertical ? contenu.height : contenu.width) + (afficherTexte || fenetre ? 5 : 0))
                readonly property real large: point ? 7 : Math.max(w.epaisseur, w.barre.vertical ? contenu.width + 2 : contenu.height)
                readonly property bool avecSep: w.separateur !== "" && index + 1 < w.bureaux.length
                width: w.barre.vertical ? Math.max(puce.width, avecSep ? sep.implicitWidth : 0) : puce.width + (avecSep ? sep.implicitWidth + 4 : 0)
                height: w.barre.vertical ? puce.height + (avecSep ? sep.implicitHeight + 2 : 0) : Math.max(puce.height, avecSep ? sep.implicitHeight : 0)
                Rectangle {
                    id: puce
                    width: w.barre.vertical ? cel.large : cel.longueur; height: w.barre.vertical ? cel.longueur : cel.large
                    x: w.barre.vertical ? (cel.width - width) / 2 : 0
                    y: w.barre.vertical ? 0 : (cel.height - height) / 2
                    radius: Math.min(width / 2, height / 2, w.style === "regular" ? Number(w.options.capsule_radius ?? 100) : 100)
                    color: w.style === "minimal" ? "transparent" : cel.actif || cel.modelData.urgent || cel.point ? cel.fond
                        : Qt.alpha(cel.fond, cel.occupe ? 0.2 : 0.33)
                    Behavior on width { enabled: w.mouv.actif; NumberAnimation { duration: w.mouv.dureeCourte; easing.type: w.mouv.courbe } }
                    Behavior on height { enabled: w.mouv.actif; NumberAnimation { duration: w.mouv.dureeCourte; easing.type: w.mouv.courbe } }
                    Grid {
                        id: contenu
                        anchors.centerIn: parent
                        columns: w.barre.vertical ? 1 : 2
                        spacing: 2
                        horizontalItemAlignment: Grid.AlignHCenter
                        verticalItemAlignment: Grid.AlignVCenter
                        Image {
                            visible: !!cel.fenetre
                            width: w.epaisseur; height: width
                            source: cel.fenetre ? Fenetres.icone(Fenetres.classe(cel.fenetre), Fenetres.application(Fenetres.classe(cel.fenetre))) : ""
                            sourceSize: Qt.size(width * 2, height * 2); fillMode: Image.PreserveAspectFit
                        }
                        Text {
                            visible: cel.afficherTexte
                            text: cel.afficherTexte ? cel.label : ""
                            textFormat: Text.PlainText
                            color: w.style !== "minimal" && (cel.actif || cel.modelData.urgent) ?
                                (cel.fond.r * 0.2126 + cel.fond.g * 0.7152 + cel.fond.b * 0.0722 > 0.56 ? "#111111" : "#ffffff") : cel.fond
                            font.family: w.barre.police; font.pixelSize: w.barre.tailleTexte; font.weight: w.barre.graisse
                        }
                    }
                    MouseArea {
                        id: zone
                        anchors.fill: parent; hoverEnabled: true
                        enabled: w.options.interactive !== false
                        acceptedButtons: Qt.LeftButton | Qt.RightButton | Qt.MiddleButton | Qt.BackButton | Qt.ForwardButton
                        cursorShape: Qt.PointingHandCursor
                        onClicked: e => { if (e.button === Qt.LeftButton) cel.modelData.activate(); else w.barre.clic(e.button) }
                        onWheel: e => { e.accepted = w.barre.molette(e.angleDelta.y || e.angleDelta.x, w.changer, !e.angleDelta.y) }
                    }
                    WidgetBarreBulle {
                        barre: w.barre; ancre: puce; survol: zone.containsMouse
                        texte: w.options.show_tooltip === false || cel.afficherTexte && cel.label === cel.modelData.name ? "" : cel.modelData.name
                    }
                }
                Text {
                    id: sep
                    visible: cel.avecSep
                    text: w.separateur; textFormat: Text.PlainText
                    x: w.barre.vertical ? (cel.width - width) / 2 : puce.width + 4
                    y: w.barre.vertical ? puce.height + 2 : (cel.height - height) / 2
                    font.family: w.barre.police; font.pixelSize: w.barre.tailleTexte
                    color: w.barre.teinte(w.options.separator_color, w.barre.premierPlan)
                }
            }
        }
    }
}

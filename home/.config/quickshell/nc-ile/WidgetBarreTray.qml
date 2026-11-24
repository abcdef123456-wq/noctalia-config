pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Effects
import Quickshell
import Quickshell.Services.SystemTray

Item {
    id: tray
    required property Item barre
    readonly property var options: barre.definition
    readonly property var caches: (options.hidden || []).map(x => String(x).toLowerCase())
    readonly property var epingles: (options.pinned || []).map(x => String(x).toLowerCase())
    readonly property var icones: SystemTray.items.values.filter(x => (options.hide_passive === false || x.status !== Status.Passive) && !correspond(x, caches))
    readonly property bool tiroir: options.drawer === true
    readonly property bool peek: !tiroir && options.peek === true
    readonly property bool apres: options.glyph_position === "after"
    readonly property var rangee: tiroir ? icones.filter(x => correspond(x, epingles)) : peek && !revele ? [] : icones
    readonly property var iconesTiroir: tiroir ? icones.filter(x => !correspond(x, epingles)) : []
    readonly property bool boutonVisible: peek || iconesTiroir.length > 0
    readonly property real taille: barre.tailleIcone
    readonly property real espace: Number(options.item_spacing ?? (options.match_adjacent_spacing ? 10 : 5))
    readonly property real longueur: (rangee.length + (boutonVisible ? 1 : 0)) * (taille + espace) - espace
    readonly property bool affiche: icones.length > 0 && longueur > 0
    property bool revele: false
    property bool ouvert: false
    implicitWidth: barre.vertical ? taille : Math.max(0, longueur)
    implicitHeight: barre.vertical ? Math.max(0, longueur) : taille

    function correspond(item, liste) {
        if (!liste.length) return false
        const id = String(item.id).toLowerCase(), titre = String(item.title).toLowerCase()
        const morceaux = id.split(/[./:]/)
        return liste.some(x => id === x || titre === x || morceaux.indexOf(x) >= 0)
    }
    function chevron() {
        if (options.glyph) {
            const connu = { "chevron-up": "keyboard_arrow_up", "chevron-down": "keyboard_arrow_down",
                "chevron-left": "chevron_left", "chevron-right": "chevron_right", "dots": "more_horiz" }
            if (connu[options.glyph]) return connu[options.glyph]
        }
        if (peek) return barre.vertical ? (apres ? "keyboard_arrow_up" : "keyboard_arrow_down") : apres ? "chevron_left" : "chevron_right"
        return barre.position === "bottom" ? "keyboard_arrow_up" : barre.position === "left" ? "chevron_right" : barre.position === "right" ? "chevron_left" : "keyboard_arrow_down"
    }
    HoverHandler {
        enabled: tray.peek
        onHoveredChanged: {
            if (hovered) delai.restart()
            else { delai.stop(); tray.revele = false }
        }
    }
    Timer { id: delai; interval: Number(tray.options.peek_delay_ms ?? 100); onTriggered: tray.revele = true }
    Repeater {
        model: tray.rangee
        Tuile {
            required property var modelData
            required property int index
            item: modelData; taille: tray.taille
            readonly property real offset: (index + (tray.boutonVisible && !tray.apres ? 1 : 0)) * (tray.taille + tray.espace)
            x: tray.barre.vertical ? 0 : offset; y: tray.barre.vertical ? offset : 0
        }
    }
    Item {
        id: bouton
        visible: tray.boutonVisible
        width: tray.taille; height: width
        readonly property real offset: tray.apres ? tray.rangee.length * (tray.taille + tray.espace) : 0
        x: tray.barre.vertical ? 0 : offset; y: tray.barre.vertical ? offset : 0
        Ico { anchors.centerIn: parent; nom: tray.chevron(); taille: tray.taille; color: tray.barre.premierPlan; plein: false }
        MouseArea {
            anchors.fill: parent; enabled: tray.tiroir
            cursorShape: Qt.PointingHandCursor
            onClicked: tray.ouvert = !tray.ouvert
        }
    }
    WidgetBarrePopup {
        barre: tray.barre; ancre: bouton
        visible: tray.visible && tray.ouvert && tray.iconesTiroir.length > 0
        grabFocus: true
        implicitWidth: grille.implicitWidth + 14; implicitHeight: grille.implicitHeight + 14
        onVisibleChanged: if (!visible) tray.ouvert = false
        Rectangle {
            anchors.fill: parent
            color: Qt.alpha(Couleurs.carte, Number(tray.options.drawer_background_opacity ?? 0.97))
            radius: 10; border.color: Couleurs.gris3
            Grid {
                id: grille
                anchors.centerIn: parent
                columns: Math.max(1, Math.min(5, Number(tray.options.drawer_columns ?? 3)))
                spacing: 6
                Repeater {
                    model: tray.ouvert ? tray.iconesTiroir : []
                    Tuile {
                        required property var modelData
                        item: modelData
                        taille: Math.max(8, Math.min(64, Number(tray.options.drawer_item_size ?? tray.taille)))
                    }
                }
            }
        }
    }
    component Tuile: Item {
        id: tuile
        required property var item
        required property real taille
        width: taille; height: taille
        readonly property string titre: item.tooltipTitle || item.title || item.id
        readonly property color encre: item.status === Status.NeedsAttention ? Couleurs.rouge : tray.barre.teinte(tray.options.icon_color || tray.options.color, tray.barre.premierPlan)
        Image {
            id: image
            anchors.fill: parent
            source: tuile.item.icon
            sourceSize: Qt.size(width * 2, height * 2)
            fillMode: Image.PreserveAspectFit
            layer.enabled: tray.options.colorize_icons === true || String(source).indexOf("-symbolic") >= 0
            layer.effect: MultiEffect { colorization: 1; colorizationColor: tuile.encre }
        }
        Text {
            anchors.centerIn: parent
            visible: image.status === Image.Null || image.status === Image.Error
            text: tuile.titre.slice(0, 1).toUpperCase(); textFormat: Text.PlainText
            font.family: tray.barre.police; font.pixelSize: tray.barre.tailleTexte; font.bold: true
            color: tuile.encre
        }
        QsMenuAnchor {
            id: menu
            menu: tuile.item.hasMenu ? tuile.item.menu : null
            anchor.item: tuile
            anchor.edges: tray.barre.bordInterieur
            anchor.gravity: tray.barre.bordInterieur
        }
        MouseArea {
            id: zone
            anchors.fill: parent; hoverEnabled: true
            acceptedButtons: Qt.LeftButton | Qt.RightButton | Qt.MiddleButton | Qt.BackButton | Qt.ForwardButton
            cursorShape: Qt.PointingHandCursor
            onClicked: e => {
                if (e.button === Qt.RightButton || e.button === Qt.LeftButton && tuile.item.onlyMenu) {
                    if (tuile.item.hasMenu) menu.open()
                } else if (e.button === Qt.LeftButton) tuile.item.activate()
                else tray.barre.clic(e.button, null, null, () => tuile.item.secondaryActivate())
            }
            onWheel: e => {
                const delta = e.angleDelta.y || e.angleDelta.x
                if (!tray.barre.molette(delta, null, !e.angleDelta.y)) tuile.item.scroll(delta, !e.angleDelta.y)
            }
        }
        WidgetBarreBulle {
            barre: tray.barre; ancre: tuile; survol: zone.containsMouse && !menu.visible
            texte: tray.options.show_tooltip === false ? "" : [tuile.titre, tuile.item.tooltipDescription].filter(t => t).join("\n")
        }
    }
}

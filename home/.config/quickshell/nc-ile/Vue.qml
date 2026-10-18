// Vue de toutes les fenêtres (comme Mission Control) : Super + A, trois doigts vers le haut, ou un coin actif.
//   Même allure que le carrousel (Super + W) : un cadre sous la barre, sur le fond d'écran flouté.
//   Le bureau affiché en miniature : chaque fenêtre à sa place et à sa taille, à la même échelle (comme sur l'écran) ;
//   les masquées à la place qu'elles avaient, voilées et marquées « Masquée » ; les bureaux de l'écran en haut.
//   Glisser une fenêtre sur une autre : elles échangent leurs places.
//   Clic : aller sur la fenêtre · clic molette : la fermer · la glisser sur un bureau : l'y envoyer
//   Au survol : boutons Masquer et Fermer · les fenêtres masquées (Super + H, nc-fenetre) sont des cartes de la grille,
//   marquées « Masquée » : un clic les ramène sur le bureau affiché, au premier plan
//   Clic sur un bureau : y aller · Échap ou clic dans le vide : fermer
import QtQuick
import Quickshell
import Quickshell.Wayland
import Quickshell.Hyprland
import Quickshell.Io
import Quickshell.Widgets
import QtQuick.Effects

PanelWindow {
    id: v
    required property var modelData
    screen: modelData
    anchors { top: true; bottom: true; left: true; right: true }
    exclusionMode: ExclusionMode.Ignore
    // Calque Top, sous l'île (Overlay) : ses notifications et activités passent par-dessus la vue (entre surfaces du
    // même calque, la plus récente serait au-dessus). Overlay seulement devant une fenêtre en plein écran.
    WlrLayershell.layer: Hyprland.activeToplevel && Hyprland.activeToplevel.lastIpcObject
                         && (Hyprland.activeToplevel.lastIpcObject.fullscreen || 0) > 0 ? WlrLayer.Overlay : WlrLayer.Top
    WlrLayershell.namespace: "nc-vue"
    WlrLayershell.keyboardFocus: WlrKeyboardFocus.Exclusive
    color: "transparent"

    readonly property var moniteur: Hyprland.monitorFor(modelData)
    readonly property int bureau: moniteur && moniteur.activeWorkspace ? moniteur.activeWorkspace.id : -1
    // Bureaux de cet écran (les bureaux cachés « special: » à part), dans l'ordre
    readonly property var bureaux: Hyprland.workspaces.values.filter(w => w.id > 0 && w.monitor === moniteur).sort((a, b) => a.id - b.id)
    // Fenêtres du bureau affiché, puis les masquées (sur l'écran actif seulement)
    // Les masquées de ce bureau (à la place qu'elles avaient) ; sans trace de leur bureau : sur l'écran actif
    readonly property var reduites: Hyprland.toplevels.values.filter(t => t.workspace && t.workspace.name === "special:reduites" && t.wayland
        && (tailles[adresse(t)] ? tailles[adresse(t)].ws === bureau : Hyprland.focusedMonitor === moniteur))
    readonly property var fenetres: Hyprland.toplevels.values.filter(t => t.workspace && t.workspace.id === bureau && t.wayland).concat(reduites)
    function fenetre(action, t) { Quickshell.execDetached([Etat.bin + "nc-fenetre", action, adresse(t)]) }
    function adresse(t) { var a = String(t.address); return a.startsWith("0x") ? a : "0x" + a }
    function dispatch(lua) { Quickshell.execDetached(["hyprctl", "eval", "hl.dispatch(" + lua + ")"]) }
    function fermer() { Etat.vueFenetres = false }
    function allerA(t) { dispatch("hl.dsp.focus({ window = 'address:" + adresse(t) + "' })"); fermer() }
    function masquee(t) { return t && t.workspace && t.workspace.name === "special:reduites" }
    // Une fenêtre masquée revient sur le bureau affiché (nc-fenetre aller), les autres : on y va
    function activer(t) { if (masquee(t)) { fenetre("aller", t); fermer() } else allerA(t) }

    // Ouverture : léger zoom arrière, comme macOS
    property real entree: 0
    Component.onCompleted: { Hyprland.refreshToplevels(); Hyprland.refreshMonitors(); entree = 1 }
    Timer { interval: 60; running: true; onTriggered: { Hyprland.refreshToplevels() } }
    Behavior on entree { NumberAnimation { duration: Reglages.val("EFFETS", "tous") === "aucun" ? 0 : 220; easing.type: Easing.OutCubic } }

    // ── Fond comme le carrousel (Super + W) : un cadre sous la barre, le fond d'écran de cet écran flouté ──
    readonly property int hautBarre: 42
    readonly property int bord: 8
    // Le fond d'écran : celui que Noctalia a retenu pour cet écran, en version floutée du carrousel s'il l'a préparée
    FileView { id: etatNoctalia; path: Quickshell.env("HOME") + "/.local/state/noctalia/settings.toml"; blockLoading: true }
    readonly property string fondOriginal: {
        var t = etatNoctalia.text() || "", nom = (v.modelData.name || "").replace(/[.*+?^${}()|[\]\\]/g, "\\$&")
        var m = t.match(new RegExp("\\[wallpaper\\.monitors\\.\"?" + nom + "\"?\\]\\s*\\npath\\s*=\\s*\"([^\"]+)\""))
                || t.match(/\[wallpaper\.default\]\s*\npath\s*=\s*"([^"]+)"/)
        return m ? m[1] : ""
    }
    // Place, taille et bureau des fenêtres masquées avant d'être cachées (nc-fenetre reduire)
    FileView { id: taillesMasquees; path: (Quickshell.env("XDG_RUNTIME_DIR") || "/tmp") + "/nc-reduites-tailles"; blockLoading: true }
    readonly property var tailles: {
        var r = {}
        for (var l of (taillesMasquees.text() || "").split("\n")) {
            var c = l.trim().split(/\s+/)
            if (c.length >= 6) r[c[0]] = { x: +c[1], y: +c[2], w: +c[3], h: +c[4], ws: +c[5] }
        }
        return r
    }

    Rectangle {
        anchors.fill: parent
        color: Qt.rgba(0, 0, 0, 0.35 * v.entree)
        MouseArea { anchors.fill: parent; onClicked: v.fermer() }
    }
    ClippingRectangle {
        id: cadre
        x: v.bord; y: v.hautBarre + v.bord; width: v.width - 2 * v.bord; height: v.height - y - v.bord
        radius: 10; color: Couleurs.carte
        border.width: 1; border.color: Qt.rgba(1, 1, 1, 0.08)
        opacity: v.entree
        // Flouté ici (la version floutée du carrousel est en WebP, que Qt ne lit pas toujours) ; petite image : flou léger
        Image {
            id: fond
            anchors.fill: parent; fillMode: Image.PreserveAspectCrop; asynchronous: true; visible: false
            sourceSize: Qt.size(width / 3, height / 3)
            source: v.fondOriginal !== "" ? "file://" + v.fondOriginal : ""
        }
        MultiEffect { anchors.fill: parent; source: fond; blurEnabled: true; blur: 1; blurMax: 40; autoPaddingEnabled: false }
        Rectangle { anchors.fill: parent; color: Qt.rgba(0, 0, 0, 0.28) }
        MouseArea { anchors.fill: parent; onClicked: v.fermer() }
    }
    Item {
        anchors.fill: parent
        focus: true
        Keys.onEscapePressed: v.fermer()
        Keys.onReturnPressed: if (v.fenetres.length) v.activer(v.fenetres[0])
    }

    // ── Bureaux ──
    Row {
        id: rangee
        anchors.horizontalCenter: parent.horizontalCenter
        y: cadre.y + 26 + (1 - v.entree) * -20
        spacing: 10
        opacity: v.entree
        Repeater {
            model: v.bureaux
            Rectangle {
                id: pastille
                required property var modelData
                readonly property bool actif: modelData.id === v.bureau
                width: Math.max(64, etiq.implicitWidth + 28); height: 40; radius: 20
                color: depot.containsDrag ? Couleurs.accent : (actif ? Couleurs.gris4 : (zp.containsMouse ? Couleurs.gris3 : Couleurs.gris2))
                border.width: actif ? 1.5 : 0; border.color: Couleurs.accent
                Behavior on color { ColorAnimation { duration: 120 } }
                Texte {
                    id: etiq
                    anchors.centerIn: parent; font.pixelSize: 14; font.weight: Font.DemiBold
                    text: Reglages.t("Bureau ", "Desktop ") + pastille.modelData.name + (pastille.modelData.toplevels.values.length
                          ? "  ·  " + pastille.modelData.toplevels.values.length : "")
                }
                MouseArea {
                    id: zp; anchors.fill: parent; hoverEnabled: true
                    onClicked: v.dispatch("hl.dsp.focus({ workspace = " + pastille.modelData.id + " })")
                }
                // Fenêtre lâchée ici : envoyée sur ce bureau (on reste sur la vue)
                DropArea {
                    id: depot; anchors.fill: parent
                    onDropped: d => v.dispatch("hl.dsp.window.move({ workspace = " + pastille.modelData.id + ", follow = false, window = 'address:"
                                               + v.adresse(d.source.toplevel) + "' })")
                }
            }
        }
        // Nouveau bureau vide
        Rectangle {
            width: 40; height: 40; radius: 20; color: zn.containsMouse ? Couleurs.gris3 : Couleurs.gris2
            Ico { anchors.centerIn: parent; nom: "add"; taille: 20 }
            MouseArea { id: zn; anchors.fill: parent; hoverEnabled: true; onClicked: v.dispatch("hl.dsp.focus({ workspace = 'emptynm' })") }
            DropArea {
                anchors.fill: parent
                onDropped: d => v.dispatch("hl.dsp.window.move({ workspace = 'emptynm', follow = false, window = 'address:" + v.adresse(d.source.toplevel) + "' })")
            }
        }
    }

    // ── Le bureau en miniature : une seule échelle pour toutes les fenêtres, chacune à sa place ; les masquées en dessous ──
    Item {
        id: zone
        anchors { top: rangee.bottom; topMargin: 32; bottom: cadre.bottom; bottomMargin: 30; left: cadre.left; leftMargin: 50; right: cadre.right; rightMargin: 50 }
        readonly property int n: v.fenetres.length
        // L'écran, en points
        readonly property var mon: v.moniteur && v.moniteur.lastIpcObject ? v.moniteur.lastIpcObject : ({})
        readonly property real ech: mon.scale || (v.moniteur ? v.moniteur.scale : 1) || 1
        readonly property real mw: mon.width ? mon.width / ech : v.width
        readonly property real mh: mon.height ? mon.height / ech : v.height
        readonly property real mx: mon.x || 0
        readonly property real my: mon.y || 0
        // Taille et place (en points, sur l'écran) : celles d'avant pour une masquée
        function taille(t) {
            var m = v.masquee(t) ? v.tailles[v.adresse(t)] : null
            if (m) return [m.w, m.h]
            var o = t.lastIpcObject || {}; return o.size ? o.size : [mw / 2, mh / 2]
        }
        function place(t) {
            var m = v.masquee(t) ? v.tailles[v.adresse(t)] : null
            if (m) return [m.x, m.y]
            var o = t.lastIpcObject || {}
            if (o.at && !v.masquee(t)) return o.at
            var tl = taille(t); return [mx + (mw - tl[0]) / 2, my + (mh - tl[1]) / 2]   // masquée sans trace : au milieu
        }
        readonly property var masquees: v.fenetres.filter(t => v.masquee(t))
        // Une seule échelle pour tout le bureau, sans déformer
        readonly property real e: Math.min(width / mw, height / mh)
        readonly property real bx: (width - mw * e) / 2
        readonly property real by: (height - mh * e) / 2

        // Le cadre de l'écran
        Rectangle {
            x: zone.bx - 8; y: zone.by - 8; width: zone.mw * zone.e + 16; height: zone.mh * zone.e + 16; radius: 18
            color: Qt.rgba(1, 1, 1, 0.04); border.width: 1; border.color: Qt.rgba(1, 1, 1, 0.12); opacity: v.entree
        }
        Texte {
            anchors.horizontalCenter: parent.horizontalCenter; y: zone.by + zone.mh * zone.e / 2 - height / 2
            visible: zone.n === zone.masquees.length; opacity: v.entree
            text: Reglages.t("Aucune fenêtre sur ce bureau", "No windows on this desktop"); secondaire: true; font.pixelSize: 18
        }
        Repeater {
            model: v.fenetres
            Item {
                id: case_
                required property var modelData
                required property int index
                readonly property var ipc: modelData.lastIpcObject || ({})
                readonly property bool masquee: v.masquee(modelData)
                readonly property var sz: zone.taille(modelData)
                readonly property var pl: zone.place(modelData)
                width: sz[0] * zone.e; height: sz[1] * zone.e
                x: zone.bx + (pl[0] - zone.mx) * zone.e
                y: zone.by + (pl[1] - zone.my) * zone.e
                // Les masquées par-dessus (estompées), celle qu'on survole ou qu'on traîne encore au-dessus
                z: survol.hovered || zf.drag.active ? 5 : (masquee ? 2 : 0)

                // Déposer une autre fenêtre ici : elles échangent leurs places (fenêtres affichées seulement)
                DropArea {
                    id: depot
                    anchors.fill: parent
                    enabled: !case_.masquee
                    onDropped: d => {
                        var t = d.source && d.source.toplevel
                        if (t && t !== case_.modelData && !v.masquee(t))
                            v.dispatch("hl.dsp.window.swap({ window = 'address:" + v.adresse(t) + "', target = 'address:" + v.adresse(case_.modelData) + "' })")
                    }
                }
                Rectangle {
                    anchors.fill: parent; anchors.margins: 2; radius: 12; z: 1
                    visible: depot.containsDrag && depot.drag.source !== carte
                    color: Qt.rgba(1, 1, 1, 0.08); border.width: 2; border.color: Couleurs.accent
                }
                opacity: v.entree
                scale: 0.92 + 0.08 * v.entree

                Item {
                    id: carte
                    property var toplevel: case_.modelData
                    // Un peu d'air entre les fenêtres collées (les espaces de Hyprland, réduits, ne se voient plus)
                    readonly property real marge: case_.masquee ? 0 : Math.min(7, case_.width * 0.04)
                    x: marge; y: marge
                    width: case_.width - 2 * marge; height: case_.height - 2 * marge
                    // Survol de toute la carte, boutons du coin compris : sinon, la souris sur un bouton la faisait
                    // rétrécir, le bouton sortait de sous la souris, elle regrossissait… (va-et-vient)
                    scale: zf.pressed ? 0.97 : (survol.hovered ? 1.03 : 1)
                    Behavior on scale { NumberAnimation { duration: 140; easing.type: Easing.OutCubic } }
                    Drag.active: zf.drag.active
                    Drag.source: carte
                    Drag.hotSpot.x: width / 2; Drag.hotSpot.y: height / 2
                    z: zf.drag.active ? 10 : 0

                    Rectangle {
                        anchors.fill: parent; anchors.margins: -3; radius: 14
                        color: "transparent"; border.width: 3
                        border.color: survol.hovered ? Couleurs.accent : "transparent"
                    }
                    ClippingRectangle {
                        // Masquée : fond plein (les terminaux transparents laisseraient voir la fenêtre dessous)
                        anchors.fill: parent; radius: case_.masquee ? 10 : 0; color: case_.masquee ? Couleurs.carte : "transparent"
                        ScreencopyView {
                            id: capture
                            // Masquée : son image (à la taille du bureau caché) recadrée sur la place qu'elle avait
                            readonly property real ratio: sourceSize.width > 0 && sourceSize.height > 0
                                                          ? sourceSize.width / sourceSize.height : parent.width / Math.max(1, parent.height)
                            anchors.centerIn: parent
                            width: case_.masquee ? Math.max(parent.width, parent.height * ratio) : parent.width
                            height: case_.masquee ? Math.max(parent.height, parent.width / ratio) : parent.height
                            captureSource: case_.modelData.wayland
                            live: !case_.masquee          // masquée : une seule image, Hyprland ne la dessine plus
                            layer.enabled: true
                            layer.smooth: true
                            // Effet sur une masquée : noir et blanc, floutée
                            layer.effect: case_.masquee ? effetMasquee : null
                        }
                    }
                    Component {
                        id: effetMasquee
                        MultiEffect { saturation: -1; blurEnabled: true; blur: 0.45; blurMax: 24; brightness: -0.1 }
                    }
                    // Masquée sans image (Hyprland ne la dessine plus) : une carte avec la grande icône de l'appli
                    Rectangle {
                        anchors.fill: parent; radius: 12; color: Couleurs.gris2
                        visible: case_.masquee && !capture.hasContent
                        Image {
                            anchors.centerIn: parent
                            readonly property real t: Math.min(96, parent.height * 0.4)
                            width: t; height: t; sourceSize: Qt.size(192, 192)
                            source: Quickshell.iconPath(String(case_.ipc.class || "").toLowerCase(), "application-x-executable")
                        }
                    }
                    // Masquée : voilée et cerclée, pour la distinguer des fenêtres affichées
                    Rectangle {
                        visible: case_.masquee; z: 1
                        anchors.fill: parent; radius: 10
                        color: Qt.rgba(0, 0, 0, 0.35); border.width: 2; border.color: Qt.rgba(1, 1, 1, 0.45)
                    }
                    // Badge « Masquée », en haut à gauche
                    Rectangle {
                        visible: case_.masquee; z: 2
                        anchors.top: parent.top; anchors.left: parent.left; anchors.margins: 8
                        width: badge.implicitWidth + 34; height: 28; radius: 14; color: Qt.rgba(0, 0, 0, 0.65)
                        Ico { anchors.verticalCenter: parent.verticalCenter; x: 9; nom: "visibility_off"; taille: 15; color: "#ffffff" }
                        Texte { id: badge; anchors.verticalCenter: parent.verticalCenter; x: 28; text: Reglages.t("Masquée", "Hidden")
                                font.pixelSize: 12; font.weight: Font.DemiBold; color: "#ffffff" }
                    }
                    // Nom de l'appli et titre, dans la miniature, en bas
                    Rectangle {
                        z: 2; visible: parent.width > 100
                        anchors.bottom: parent.bottom; anchors.bottomMargin: 8; anchors.horizontalCenter: parent.horizontalCenter
                        width: Math.min(parent.width - 16, nom.implicitWidth + 22); height: 26; radius: 13; color: Qt.rgba(0, 0, 0, 0.65)
                        Row {
                            id: nom
                            anchors.centerIn: parent; spacing: 6
                            Image {
                                width: 16; height: 16; sourceSize: Qt.size(32, 32); anchors.verticalCenter: parent.verticalCenter
                                source: Quickshell.iconPath(String(case_.ipc.class || "").toLowerCase(), true)
                                visible: source != ""
                            }
                            Texte {
                                anchors.verticalCenter: parent.verticalCenter
                                width: Math.min(implicitWidth, carte.width - 60); elide: Text.ElideRight
                                text: case_.modelData.title || case_.ipc.class || ""; font.pixelSize: 12; color: "#ffffff"
                            }
                        }
                    }
                    // Boutons au survol : réduire, fermer (au-dessus de la zone de clic de la miniature)
                    HoverHandler { id: survol }
                    Row {
                        z: 2
                        anchors.top: parent.top; anchors.right: parent.right; anchors.margins: 8
                        spacing: 6
                        opacity: survol.hovered ? 1 : 0
                        Behavior on opacity { NumberAnimation { duration: 120 } }
                        Repeater {
                            model: case_.masquee ? [{ ico: "close", action: "fermer" }]
                                                 : [{ ico: "remove", action: "reduire" }, { ico: "close", action: "fermer" }]
                            Rectangle {
                                required property var modelData
                                width: 30; height: 30; radius: 15
                                color: zb.containsMouse ? (modelData.action === "fermer" ? Couleurs.rouge : Couleurs.gris4) : Qt.rgba(0, 0, 0, 0.6)
                                Ico { anchors.centerIn: parent; nom: parent.modelData.ico; taille: 17; color: "#ffffff" }
                                MouseArea {
                                    id: zb; anchors.fill: parent; hoverEnabled: true
                                    onClicked: parent.modelData.action === "fermer"
                                               ? v.dispatch("hl.dsp.window.close({ window = 'address:" + v.adresse(case_.modelData) + "' })")
                                               : v.fenetre("reduire", case_.modelData)
                                }
                            }
                        }
                    }
                    MouseArea {
                        id: zf
                        anchors.fill: parent
                        hoverEnabled: true
                        acceptedButtons: Qt.LeftButton | Qt.MiddleButton
                        drag.target: carte
                        onClicked: e => {
                            if (e.button === Qt.MiddleButton) v.dispatch("hl.dsp.window.close({ window = 'address:" + v.adresse(case_.modelData) + "' })")
                            else v.activer(case_.modelData)
                        }
                        onReleased: {
                            if (carte.Drag.active) carte.Drag.drop()
                            carte.x = carte.marge; carte.y = carte.marge
                        }
                    }
                }
            }
        }
    }
}

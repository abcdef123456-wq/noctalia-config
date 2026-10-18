// Vue de toutes les fenêtres (comme Mission Control) : Super + A, trois doigts vers le haut, ou un coin actif.
//   Les fenêtres du bureau affiché en miniatures vivantes ; les bureaux de l'écran en haut.
//   Clic : aller sur la fenêtre · clic molette : la fermer · la glisser sur un bureau : l'y envoyer
//   Au survol : boutons Masquer et Fermer · les fenêtres masquées (Super + H, nc-fenetre) sont des cartes de la grille,
//   marquées « Masquée » : un clic les ramène sur le bureau affiché, au premier plan
//   Clic sur un bureau : y aller · Échap ou clic dans le vide : fermer
import QtQuick
import Quickshell
import Quickshell.Wayland
import Quickshell.Hyprland

PanelWindow {
    id: v
    required property var modelData
    screen: modelData
    anchors { top: true; bottom: true; left: true; right: true }
    exclusionMode: ExclusionMode.Ignore
    WlrLayershell.layer: WlrLayer.Overlay
    WlrLayershell.namespace: "nc-vue"
    WlrLayershell.keyboardFocus: WlrKeyboardFocus.Exclusive
    color: "transparent"

    readonly property var moniteur: Hyprland.monitorFor(modelData)
    readonly property int bureau: moniteur && moniteur.activeWorkspace ? moniteur.activeWorkspace.id : -1
    // Bureaux de cet écran (les bureaux cachés « special: » à part), dans l'ordre
    readonly property var bureaux: Hyprland.workspaces.values.filter(w => w.id > 0 && w.monitor === moniteur).sort((a, b) => a.id - b.id)
    // Fenêtres du bureau affiché, puis les masquées (sur l'écran actif seulement)
    readonly property var reduites: Hyprland.focusedMonitor !== moniteur ? []
        : Hyprland.toplevels.values.filter(t => t.workspace && t.workspace.name === "special:reduites" && t.wayland)
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
    Component.onCompleted: { Hyprland.refreshToplevels(); entree = 1 }
    Timer { interval: 60; running: true; onTriggered: { Hyprland.refreshToplevels() } }
    Behavior on entree { NumberAnimation { duration: Reglages.val("EFFETS", "tous") === "aucun" ? 0 : 220; easing.type: Easing.OutCubic } }

    Rectangle {
        anchors.fill: parent
        color: Qt.rgba(0, 0, 0, 0.74 * v.entree)
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
        y: 70 + (1 - v.entree) * -20
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

    // ── Fenêtres du bureau, en grille ──
    Item {
        id: zone
        anchors { top: rangee.bottom; topMargin: 36; bottom: parent.bottom; bottomMargin: 60; left: parent.left; leftMargin: 70; right: parent.right; rightMargin: 70 }
        readonly property int n: v.fenetres.length
        // Colonnes : la grille la plus proche de la forme de l'écran (fenêtres en 16:10 environ)
        readonly property int colonnes: Math.max(1, Math.min(n, Math.round(Math.sqrt(n * width / Math.max(1, height) / 1.6))))
        readonly property int lignes: Math.max(1, Math.ceil(n / colonnes))
        readonly property real ecart: 28
        readonly property real cw: (width - (colonnes - 1) * ecart) / colonnes
        readonly property real ch: (height - (lignes - 1) * ecart) / lignes

        Texte {
            anchors.centerIn: parent; visible: zone.n === 0; opacity: v.entree
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
                // Taille réelle de la fenêtre : celle de Hyprland, sinon celle de l'image capturée (en points)
                readonly property real ech: v.moniteur ? v.moniteur.scale : 1
                readonly property real rw: ipc.size ? ipc.size[0] : (capture.sourceSize.width > 0 ? capture.sourceSize.width / ech : 1600)
                readonly property real rh: ipc.size ? ipc.size[1] : (capture.sourceSize.height > 0 ? capture.sourceSize.height / ech : 1000)
                readonly property int ligne: Math.floor(index / zone.colonnes)
                readonly property int dansLigne: Math.min(zone.colonnes, zone.n - ligne * zone.colonnes)
                // Taille de la miniature : la fenêtre entière dans sa case, sans déformer ; jamais plus grande que nature
                readonly property real echelle: Math.min((zone.cw) / rw, (zone.ch - 34) / rh, 1)
                width: zone.cw; height: zone.ch
                x: (zone.width - dansLigne * zone.cw - (dansLigne - 1) * zone.ecart) / 2 + (index % zone.colonnes) * (zone.cw + zone.ecart)
                y: (zone.height - zone.lignes * zone.ch - (zone.lignes - 1) * zone.ecart) / 2 + ligne * (zone.ch + zone.ecart)
                opacity: v.entree
                scale: 0.92 + 0.08 * v.entree

                Item {
                    id: carte
                    property var toplevel: case_.modelData
                    width: case_.rw * case_.echelle; height: case_.rh * case_.echelle
                    x: (case_.width - width) / 2; y: (case_.height - 34 - height) / 2
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
                    ScreencopyView {
                        id: capture
                        anchors.fill: parent
                        captureSource: case_.modelData.wayland
                        live: true
                        layer.enabled: true
                        layer.smooth: true
                        opacity: case_.masquee ? 0.55 : 1
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
                    // Badge « Masquée », en haut à gauche
                    Rectangle {
                        visible: case_.masquee; z: 2
                        anchors.top: parent.top; anchors.left: parent.left; anchors.margins: 8
                        width: badge.implicitWidth + 34; height: 28; radius: 14; color: Qt.rgba(0, 0, 0, 0.65)
                        Ico { anchors.verticalCenter: parent.verticalCenter; x: 9; nom: "visibility_off"; taille: 15; color: "#ffffff" }
                        Texte { id: badge; anchors.verticalCenter: parent.verticalCenter; x: 28; text: Reglages.t("Masquée", "Hidden")
                                font.pixelSize: 12; font.weight: Font.DemiBold; color: "#ffffff" }
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
                            carte.x = (case_.width - carte.width) / 2; carte.y = (case_.height - 34 - carte.height) / 2
                        }
                    }
                }
                // Nom de l'appli et titre, sous la miniature
                Row {
                    anchors.horizontalCenter: parent.horizontalCenter
                    y: carte.y + carte.height + 10
                    spacing: 8
                    Image {
                        width: 18; height: 18; sourceSize: Qt.size(36, 36); anchors.verticalCenter: parent.verticalCenter
                        source: Quickshell.iconPath(String(case_.ipc.class || "").toLowerCase(), true)
                        visible: source != ""
                    }
                    Texte {
                        anchors.verticalCenter: parent.verticalCenter
                        width: Math.min(implicitWidth, case_.width - 40)
                        text: case_.modelData.title || case_.ipc.class || ""; font.pixelSize: 13
                        color: "#ffffff"
                    }
                }
            }
        }
    }
}

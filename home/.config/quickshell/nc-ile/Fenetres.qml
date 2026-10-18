// Page « Fenêtres » de l'île (clic sur le titre de la fenêtre, dans la barre) : les fenêtres du bureau affiché, puis
// les masquées (Super + H). Un clic va sur une fenêtre ou ramène une masquée ; l'œil la masque ou la ramène, la croix
// la ferme ; « Tout masquer » / « Tout afficher ». L'île prend la hauteur de la liste ; lignes plus serrées au-delà de
// 5 fenêtres. Actions : nc-fenetre (fondu, bureau caché « special:reduites »).
import QtQuick
import Quickshell
import Quickshell.Hyprland

Item {
    id: p
    function defiler(dy) { return defil.defiler(dy) }

    readonly property var moniteur: Hyprland.focusedMonitor
    readonly property int bureau: moniteur && moniteur.activeWorkspace ? moniteur.activeWorkspace.id : -1
    function position(t) { var o = t.lastIpcObject; return o && o.at ? o.at[0] * 10000 + o.at[1] : 0 }
    readonly property var fenetres: Hyprland.toplevels.values
        .filter(t => t.workspace && t.workspace.id === bureau).sort((a, b) => position(a) - position(b))
    readonly property var masquees: Hyprland.toplevels.values.filter(t => t.workspace && t.workspace.name === "special:reduites")
    readonly property bool serre: fenetres.length + masquees.length > 5
    Component.onCompleted: Hyprland.refreshToplevels()

    function adresse(t) { var a = String(t.address); return a.startsWith("0x") ? a : "0x" + a }
    function faire(action, t) { Quickshell.execDetached(t ? [Etat.bin + "nc-fenetre", action, adresse(t)] : [Etat.bin + "nc-fenetre", action]) }

    Item {
        id: tete
        width: parent.width; height: 34
        Row {
            anchors.verticalCenter: parent.verticalCenter; leftPadding: 4; spacing: 8
            Texte { anchors.verticalCenter: parent.verticalCenter; text: Reglages.t("Fenêtres", "Windows"); font.pixelSize: 20; font.weight: Font.Bold }
            Texte { anchors.verticalCenter: parent.verticalCenter; text: Reglages.t("Bureau ", "Desktop ") + p.bureau; secondaire: true }
        }
        Row {
            anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter; spacing: 14
            Repeater {
                model: [
                    { texte: Reglages.t("Tout masquer", "Hide All"), action: "tout-masquer", ok: p.fenetres.length > 0 },
                    { texte: Reglages.t("Tout afficher", "Show All"), action: "tout-afficher", ok: p.masquees.length > 0 }
                ]
                Texte {
                    required property var modelData
                    visible: modelData.ok
                    text: modelData.texte; color: zl.containsMouse ? Couleurs.accentClair : Couleurs.accent
                    MouseArea { id: zl; anchors.fill: parent; anchors.margins: -6; hoverEnabled: true; onClicked: p.faire(parent.modelData.action) }
                }
            }
        }
    }

    Defilement {
        id: defil
        anchors.top: tete.bottom; anchors.topMargin: 10; anchors.bottom: parent.bottom
        width: parent.width
        contentHeight: liste.implicitHeight

        Column {
            id: liste
            width: p.width; spacing: 6
            readonly property real voulue: 34 + 10 + implicitHeight
            onVoulueChanged: Etat.annoncerHauteur("fenetres", voulue)
            Component.onCompleted: Etat.annoncerHauteur("fenetres", voulue)

            Item {
                visible: p.fenetres.length + p.masquees.length === 0
                width: parent.width; height: 100
                Column {
                    anchors.centerIn: parent; spacing: 6
                    Ico { anchors.horizontalCenter: parent.horizontalCenter; nom: "select_window"; taille: 30; color: Couleurs.gris4 }
                    Texte { anchors.horizontalCenter: parent.horizontalCenter; text: Reglages.t("Aucune fenêtre sur ce bureau", "No windows on this desktop"); secondaire: true }
                }
            }
            Repeater {
                model: [{ titre: Reglages.t("Sur ce bureau", "On this desktop"), liste: p.fenetres, masquee: false },
                        { titre: Reglages.t("Masquées", "Hidden"), liste: p.masquees, masquee: true }]
                Column {
                    id: groupe
                    required property var modelData
                    visible: modelData.liste.length > 0
                    width: liste.width; spacing: 6
                    Texte { leftPadding: 4; topPadding: 4; text: groupe.modelData.titre + "  ·  " + groupe.modelData.liste.length; secondaire: true; font.pixelSize: 12; font.weight: Font.DemiBold }
                    Repeater {
                        model: groupe.modelData.liste
                        Rectangle {
                            id: el
                            required property var modelData
                            readonly property var ipc: modelData.lastIpcObject || ({})
                            readonly property bool masquee: groupe.modelData.masquee
                            readonly property bool active: !masquee && Hyprland.activeToplevel === modelData
                            width: liste.width; height: p.serre ? 46 : 58; radius: 14
                            color: survolLigne.hovered ? Couleurs.carteSurvol : Couleurs.carte
                            HoverHandler { id: survolLigne }
                            border.width: active ? 1.5 : 0; border.color: Couleurs.accent
                            Image {
                                id: ic
                                x: 12; anchors.verticalCenter: parent.verticalCenter
                                readonly property int t: p.serre ? 24 : 32
                                width: t; height: t; sourceSize: Qt.size(64, 64)
                                source: Quickshell.iconPath(String(el.ipc.class || "").toLowerCase(), "application-x-executable")
                                opacity: el.masquee ? 0.45 : 1
                            }
                            Column {
                                anchors.left: ic.right; anchors.leftMargin: 12; anchors.right: boutons.left; anchors.rightMargin: 8
                                anchors.verticalCenter: parent.verticalCenter; spacing: 1
                                Texte { width: parent.width; elide: Text.ElideRight; font.pixelSize: 14; font.weight: el.active ? Font.DemiBold : Font.Normal
                                        text: el.modelData.title || el.ipc.class || Reglages.t("Fenêtre", "Window"); secondaire: el.masquee }
                                Texte { visible: !p.serre && (el.ipc.class || "") !== ""; width: parent.width; elide: Text.ElideRight
                                        text: el.ipc.class || ""; secondaire: true; font.pixelSize: 12 }
                            }
                            Row {
                                id: boutons
                                anchors.right: parent.right; anchors.rightMargin: 10; anchors.verticalCenter: parent.verticalCenter; spacing: 6
                                Repeater {
                                    model: [{ ico: el.masquee ? "visibility" : "visibility_off", action: "basculer" }, { ico: "close", action: "fermer" }]
                                    Rectangle {
                                        required property var modelData
                                        width: 30; height: 30; radius: 15
                                        color: zb.containsMouse ? (modelData.action === "fermer" ? Couleurs.rouge : Couleurs.gris4) : Couleurs.gris2
                                        Ico { anchors.centerIn: parent; nom: parent.modelData.ico; taille: 16
                                              color: zb.containsMouse && parent.modelData.action === "fermer" ? "#ffffff" : Couleurs.texte }
                                        MouseArea { id: zb; anchors.fill: parent; hoverEnabled: true; onClicked: p.faire(parent.modelData.action, el.modelData) }
                                    }
                                }
                            }
                            MouseArea {
                                id: zone; anchors.fill: parent; z: -1; hoverEnabled: true
                                onClicked: { p.faire("aller", el.modelData); Etat.fermer() }
                            }
                        }
                    }
                }
            }
        }
    }
}

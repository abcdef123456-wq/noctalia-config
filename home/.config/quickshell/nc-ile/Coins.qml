// Coins actifs (nc-reglages → Clavier et souris) : pousser la souris dans un coin de l'écran lance une action, comme sur
// macOS. Un carré de 2 px dans chaque coin choisi ; l'action part après un court arrêt (pas en passant vite), une fois
// par visite. Coupés en mode jeu et sur une fenêtre en plein écran.
// Réglages COIN_HG, COIN_HD, COIN_BG, COIN_BD : rien, vue, recherche, centre, lanceur, notifications, verrouiller,
// ecran (éteindre l'écran). Par défaut, en mode souris : coin en haut à gauche = vue de toutes les fenêtres.
import QtQuick
import Quickshell
import Quickshell.Wayland
import Quickshell.Hyprland

Scope {
    id: c
    required property var modelData

    readonly property bool souris: Reglages.val("SAISIE", "clavier") !== "clavier"
    function action(coin) {
        var a = Reglages.val("COIN_" + coin, "auto")
        return a !== "auto" ? a : (coin === "HG" && souris ? "vue" : "rien")
    }
    function lancer(a) {
        var ecran = c.modelData.name
        if (a === "vue") Quickshell.execDetached(["qs", "-c", "nc-ile", "ipc", "call", "ile", "vue"])
        else if (a === "recherche") Etat.chercher(ecran)
        else if (a === "centre") Etat.basculer(ecran, true)
        else if (a === "notifications") { Etat.basculer(ecran, true); Etat.aller("notifications") }
        else if (a === "lanceur") Quickshell.execDetached(["noctalia", "msg", "panel-toggle", "launcher"])
        else if (a === "verrouiller") Quickshell.execDetached(["noctalia", "msg", "lock"])
        else if (a === "ecran") Quickshell.execDetached(["sh", "-c", "sleep 0.5; hyprctl dispatch 'hl.dsp.dpms({ action = \"off\" })'"])
    }
    readonly property bool coupe: Etat.jeu || (Hyprland.activeToplevel && Hyprland.activeToplevel.lastIpcObject
                                              && (Hyprland.activeToplevel.lastIpcObject.fullscreen || 0) > 0)

    Variants {
        model: ["HG", "HD", "BG", "BD"]
        Scope {
            id: coin
            required property string modelData
            readonly property string quoi: c.action(modelData)
            LazyLoader {
                active: coin.quoi !== "rien" && !c.coupe
                PanelWindow {
                    screen: c.modelData
                    anchors { top: coin.modelData[0] === "H"; bottom: coin.modelData[0] === "B"
                              left: coin.modelData[1] === "G"; right: coin.modelData[1] === "D" }
                    implicitWidth: 2; implicitHeight: 2
                    exclusionMode: ExclusionMode.Ignore
                    WlrLayershell.layer: WlrLayer.Overlay
                    WlrLayershell.namespace: "nc-coin"
                    WlrLayershell.keyboardFocus: WlrKeyboardFocus.None
                    color: "transparent"
                    MouseArea {
                        anchors.fill: parent
                        hoverEnabled: true
                        property bool fait: false
                        onEntered: { fait = false; attente.restart() }
                        onExited: attente.stop()
                        Timer { id: attente; interval: 140; onTriggered: if (!parent.fait) { parent.fait = true; c.lancer(coin.quoi) } }
                    }
                }
            }
        }
    }
}

// Terminal déroulant sorti (Super + touche sous Échap) : un clic sur le bureau vide, à côté, le range. Les autres façons
// d'aller ailleurs (clic sur une fenêtre, Alt + Tab, autre bureau) sont vues par Hyprland (nc/automatismes.lua).
// Une zone invisible sous les fenêtres, sur l'écran du terminal, seulement tant qu'il est sorti : rien le reste du temps.
import QtQuick
import Quickshell
import Quickshell.Wayland
import Quickshell.Hyprland

Scope {
    id: r
    property string ecran: ""                 // l'écran où le terminal est sorti, sinon ""
    Connections {
        target: Hyprland
        // « activespecial>>special:term,eDP-1 » quand il sort, « activespecial>>,eDP-1 » quand le bureau caché se range
        function onRawEvent(e) {
            if (e.name !== "activespecial") return
            var i = e.data.lastIndexOf(","), nom = e.data.slice(0, i), mon = e.data.slice(i + 1)
            if (nom === "special:term") r.ecran = mon
            else if (mon === r.ecran) r.ecran = ""
        }
    }
    Variants {
        model: r.ecran === "" ? [] : Quickshell.screens.filter(s => s.name === r.ecran)
        PanelWindow {
            required property var modelData
            screen: modelData
            anchors { top: true; bottom: true; left: true; right: true }
            exclusionMode: ExclusionMode.Ignore
            WlrLayershell.layer: WlrLayer.Bottom
            WlrLayershell.namespace: "nc-range-terminal"
            WlrLayershell.keyboardFocus: WlrKeyboardFocus.None
            color: "transparent"
            MouseArea {
                anchors.fill: parent
                acceptedButtons: Qt.LeftButton | Qt.RightButton | Qt.MiddleButton
                onPressed: {
                    r.ecran = ""
                    Quickshell.execDetached(["hyprctl", "dispatch", "hl.dsp.workspace.toggle_special('term')"])
                }
            }
        }
    }
}

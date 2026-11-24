import QtQuick
import Quickshell
import Quickshell.Wayland

PanelWindow {
    required property string bord
    required property int zone
    readonly property bool vertical: bord === "left" || bord === "right"
    anchors {
        top: bord === "top" || vertical
        bottom: bord === "bottom" || vertical
        left: bord === "left" || !vertical
        right: bord === "right" || !vertical
    }
    implicitWidth: vertical ? 1 : 0
    implicitHeight: vertical ? 0 : 1
    exclusiveZone: zone
    color: "transparent"
    mask: Region {}
    WlrLayershell.layer: WlrLayer.Background
    WlrLayershell.namespace: "nc-panneau-reserve-" + bord
}

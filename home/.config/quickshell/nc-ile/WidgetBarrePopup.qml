import QtQuick
import Quickshell

PopupWindow {
    id: popup
    required property Item barre
    required property Item ancre
    color: "transparent"
    anchor.item: ancre
    anchor.edges: barre.bordInterieur
    anchor.gravity: barre.bordInterieur
}

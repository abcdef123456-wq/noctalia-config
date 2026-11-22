// Bande réservée pour l'île (ILE_BANDE=oui, posé par les thèmes dont la barre n'est pas en haut) : une couche vide et
// transparente en haut de l'écran, sans contenu ni clic, qui garde la place de l'île : les fenêtres ne passent plus dessous.
// 42 = la place que réserve la barre de base (6 + 36) : l'île fermée (9 + 30, contour de 3 px compris) y tient, et une
// bannière ne déborde pas plus qu'avec la barre de base. Une barre en haut réserve déjà sa place, et Hyprland empile les
// zones exclusives d'un même bord : avec elle, une barre plus épaisse vaut mieux que cette bande.
import QtQuick
import Quickshell
import Quickshell.Wayland

PanelWindow {
    required property var modelData
    screen: modelData
    anchors.top: true
    anchors.left: true
    anchors.right: true
    implicitHeight: 1
    exclusiveZone: 42
    color: "transparent"
    mask: Region {}
    WlrLayershell.layer: WlrLayer.Background
    WlrLayershell.namespace: "nc-ile-bande"
}

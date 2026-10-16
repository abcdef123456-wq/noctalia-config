// Spotlight ouvert : un clic n'importe où à côté (sur une fenêtre, le bureau, la barre ou un autre écran) le referme.
// Couche invisible sous l'île (Top, l'île est en Overlay), créée seulement pendant la recherche (shell.qml). La prise de focus
// de Hyprland (Ile.qml) ne suffisait pas : l'île garde le clavier en exclusif pendant la recherche.
import QtQuick
import Quickshell
import Quickshell.Wayland

PanelWindow {
    required property var modelData
    screen: modelData
    anchors { top: true; bottom: true; left: true; right: true }
    exclusionMode: ExclusionMode.Ignore
    WlrLayershell.layer: WlrLayer.Top
    WlrLayershell.namespace: "nc-ile-dehors"
    WlrLayershell.keyboardFocus: WlrKeyboardFocus.None
    color: "transparent"
    MouseArea {
        anchors.fill: parent
        acceptedButtons: Qt.AllButtons
        onPressed: Etat.fermer()
        onWheel: Etat.fermer()
    }
}

// Capture épinglée (`nc-capture epingler`, bouton « Épingler » de la notification d'une capture) : une petite fenêtre qui
// garde l'image à l'écran, au-dessus des autres (règle Hyprland nc-epingle-fenetre). Image bornée à 40 % de la largeur et
// de la hauteur de l'écran, proportions gardées. Échap ou clic droit : fermer ; l'île efface alors la copie (shell.qml).
// Pour la déplacer : Super + glisser, comme toute fenêtre flottante. Rien ne tourne fermé (la fenêtre n'existe qu'ouverte).
import QtQuick
import Quickshell

FloatingWindow {
    id: ce
    signal fermer()
    property string chemin: ""
    title: Reglages.t("Capture épinglée", "Pinned screenshot")
    color: "transparent"
    implicitWidth: ce.largeur
    implicitHeight: ce.hauteur
    onClosed: ce.fermer()
    onVisibleChanged: if (!visible) ce.fermer()

    readonly property real largeurEcran: ce.screen ? ce.screen.width : 1600
    readonly property real hauteurEcran: ce.screen ? ce.screen.height : 900
    // Échelle : jamais plus grande que l'image, jamais au-delà de 40 % de l'écran (largeur ET hauteur)
    readonly property real echelle: image.implicitWidth > 0 && image.implicitHeight > 0
        ? Math.min(1, 0.4 * ce.largeurEcran / image.implicitWidth, 0.4 * ce.hauteurEcran / image.implicitHeight) : 1
    readonly property int largeur: Math.max(32, Math.round(image.implicitWidth * ce.echelle))
    readonly property int hauteur: Math.max(32, Math.round(image.implicitHeight * ce.echelle))
    property alias cible: image         // pour le rendu hors écran

    Image {
        id: image
        anchors.fill: parent
        source: ce.chemin !== "" ? "file://" + ce.chemin : ""
        fillMode: Image.PreserveAspectFit
        cache: false
        asynchronous: true
        smooth: true
        focus: true
        Keys.onEscapePressed: ce.fermer()
        MouseArea {
            anchors.fill: parent
            acceptedButtons: Qt.RightButton
            onClicked: ce.fermer()
        }
    }
}

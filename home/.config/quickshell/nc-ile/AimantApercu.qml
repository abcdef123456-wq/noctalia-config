// Aperçu d'aimantation : pendant qu'on glisse une fenêtre vers un bord ou un coin de l'écran (nc/raccourcis.lua), un cadre
// arrondi, translucide, aux couleurs de l'île, montre où elle va se ranger. Chargé par un LazyLoader de shell.qml
// seulement pendant un glisser avec zone : rien en mémoire le reste du temps.
// Calque Overlay (au-dessus des fenêtres, même en plein écran), aucune zone de clic (mask vide) et jamais le clavier :
// le glisser n'est pas gêné. La surface fait toujours l'écran entier (sa taille ne change jamais) ; seul le cadre bouge,
// en ressort, et se fond. Aucune animation en boucle. Règle de calque no_anim (nc/regles.lua) : Hyprland n'anime pas en plus.
// Le rectangle (rx, ry, rw, rh) est en coordonnées logiques globales ; le cadre le place sur CET écran.
import QtQuick
import Quickshell
import Quickshell.Wayland

PanelWindow {
    id: ap
    property bool montre: true               // faux : le cadre se fond (le rectangle reste où il était)
    property real rx: 0
    property real ry: 0
    property real rw: 0
    property real rh: 0
    // Arrondi des fenêtres du bureau (réglage FENETRES_ARRONDI, 20 au plus comme Hyprland)
    readonly property real arrondi: Math.min(20, Math.max(0, Number(Reglages.val("FENETRES_ARRONDI", 14)) || 14))

    anchors { top: true; bottom: true; left: true; right: true }
    exclusionMode: ExclusionMode.Ignore
    WlrLayershell.layer: WlrLayer.Overlay
    WlrLayershell.namespace: "nc-aimant"
    WlrLayershell.keyboardFocus: WlrKeyboardFocus.None
    mask: Region {}
    color: "transparent"

    Rectangle {
        id: cadre
        objectName: "cadre"
        // Vrai une fois le premier placement fait : le cadre apparaît à sa place, il ne vient pas du coin de l'écran
        property bool anime: false
        x: ap.rx - (ap.screen ? ap.screen.x : 0)
        y: ap.ry - (ap.screen ? ap.screen.y : 0)
        width: Math.max(0, ap.rw)
        height: Math.max(0, ap.rh)
        radius: ap.arrondi
        color: Qt.rgba(Couleurs.accent.r, Couleurs.accent.g, Couleurs.accent.b, 0.20)
        border.width: 2
        border.color: Qt.rgba(Couleurs.accent.r, Couleurs.accent.g, Couleurs.accent.b, 0.75)
        opacity: ap.montre ? 1 : 0
        Behavior on x { enabled: cadre.anime; SpringAnimation { spring: 3.4; damping: 0.4 } }
        Behavior on y { enabled: cadre.anime; SpringAnimation { spring: 3.4; damping: 0.4 } }
        Behavior on width { enabled: cadre.anime; SpringAnimation { spring: 3.4; damping: 0.4 } }
        Behavior on height { enabled: cadre.anime; SpringAnimation { spring: 3.4; damping: 0.4 } }
        Behavior on opacity { NumberAnimation { duration: 160; easing.type: Easing.OutCubic } }
        Component.onCompleted: cadre.anime = true
    }
}

// Fond d'écran animé « aurore » (nc-reglages → Fonds d'écran → FOND_ANIME) : trois grandes lueurs aux couleurs du
// thème dérivent lentement par-dessus le fond d'écran, sous les fenêtres. Rien à installer.
// Économe : 15 images par seconde, en pause dès qu'une fenêtre est ouverte sur le bureau affiché (le fond est caché),
// sur batterie (sauf FOND_ANIME_BATTERIE=oui), en mode Économie et en mode jeu.
import QtQuick
import QtQuick.Shapes
import Quickshell
import Quickshell.Wayland
import Quickshell.Hyprland
import Quickshell.Services.UPower

PanelWindow {
    id: f
    required property var modelData
    screen: modelData
    anchors { top: true; bottom: true; left: true; right: true }
    exclusionMode: ExclusionMode.Ignore
    WlrLayershell.layer: WlrLayer.Bottom
    WlrLayershell.namespace: "nc-fond"
    color: "transparent"
    mask: Region {}                                         // ne prend jamais la souris

    readonly property var moniteur: Hyprland.monitorFor(modelData)
    readonly property bool bureauVide: !moniteur || !moniteur.activeWorkspace
                                       || moniteur.activeWorkspace.toplevels.values.length === 0
    readonly property bool economie: PowerProfiles.profile === PowerProfile.PowerSaver
    readonly property bool batterieOk: !UPower.onBattery || Reglages.val("FOND_ANIME_BATTERIE", "non") === "oui"
    readonly property bool anime: bureauVide && batterieOk && !economie && !Etat.jeu

    property real t: 0
    Timer { interval: 66; repeat: true; running: f.anime; onTriggered: f.t += 0.066 }

    // Lueurs : couleur du thème, centre qui décrit une lente boucle, rayon qui respire
    component Lueur: ShapePath {
        id: l
        property color teinte: "white"
        property real cx: 0.5
        property real cy: 0.5
        property real r: 0.5
        strokeWidth: -1
        fillGradient: RadialGradient {
            centerX: l.cx * f.width; centerY: l.cy * f.height; centerRadius: l.r * Math.max(f.width, f.height)
            focalX: centerX; focalY: centerY
            GradientStop { position: 0; color: Qt.alpha(l.teinte, 0.42) }
            GradientStop { position: 0.55; color: Qt.alpha(l.teinte, 0.14) }
            GradientStop { position: 1; color: "transparent" }
        }
        startX: 0; startY: 0
        PathLine { x: f.width; y: 0 }
        PathLine { x: f.width; y: f.height }
        PathLine { x: 0; y: f.height }
        PathLine { x: 0; y: 0 }
    }
    Shape {
        anchors.fill: parent
        opacity: f.anime ? 1 : 0.6                           // en pause : figée, un peu plus discrète
        Behavior on opacity { NumberAnimation { duration: 800 } }
        preferredRendererType: Shape.CurveRenderer
        Lueur { teinte: Couleurs.accent; cx: 0.28 + 0.16 * Math.sin(f.t * 0.11); cy: 0.32 + 0.14 * Math.cos(f.t * 0.09); r: 0.55 + 0.06 * Math.sin(f.t * 0.2) }
        Lueur { teinte: Couleurs.violet; cx: 0.74 + 0.14 * Math.cos(f.t * 0.08); cy: 0.62 + 0.16 * Math.sin(f.t * 0.12); r: 0.5 + 0.07 * Math.cos(f.t * 0.17) }
        Lueur { teinte: Couleurs.bleu; cx: 0.5 + 0.22 * Math.sin(f.t * 0.06 + 2); cy: 0.9 + 0.08 * Math.cos(f.t * 0.1); r: 0.45 }
    }
}

// Logo de l'IA, dessiné à la main (aux couleurs de chacune, Agents.ias) ; bouge doucement pendant qu'elle travaille :
//   claude : étincelle à huit rayons (tourne) ; gemini : étoile à quatre branches (tourne)
//   antigravity : arche en dégradé ; opencode : carré dans un carré ; codex : invite >_ ; cursor : cube ;
//   copilot : lunettes ; qwen : hexagone ; kiro : fantôme ; amp : « A » en flèche (flottent)
//   assistant : emblème animé fourni par l'utilisateur (atlas PNG, immobile au repos)
// Les mouvements sans fin sont des Animator (fil de rendu) : aucune propriété QML n'est réécrite à chaque image.
// Un Animator n'écrit sa propriété qu'à l'arrêt : c'est donc dans onStopped que le logo revient droit et en place.
import QtQuick
import Quickshell.Services.UPower

Item {
    id: e
    property real taille: 18
    property bool tourne: false
    property string agent: "claude"
    readonly property bool tournante: agent === "claude" || agent === "gemini"
    property color couleur: (Agents.ias[agent] || Agents.ias.claude).couleur
    width: taille; height: taille
    onCouleurChanged: dessin.requestPaint()
    onAgentChanged: { retour.stop(); rotation = 0; dessin.requestPaint() }   // les autres logos ne gardent pas l'angle de l'étincelle

    // Le dessin, sans ancres : le « flotte » des autres logos anime son y (YAnimator) dans le cadre de e
    Canvas {
        id: dessin
        width: e.width; height: e.height
        onPaint: {
            var c = getContext("2d"); c.reset()
            var w = width, h = height, r = w / 2, k = String(e.couleur)
            c.lineCap = "round"; c.lineJoin = "round"
            c.strokeStyle = k; c.fillStyle = k
            c.lineWidth = Math.max(1.6, w * 0.13)
            function chemin(points, ferme) {
                c.beginPath(); c.moveTo(points[0][0] * w, points[0][1] * h)
                for (var i = 1; i < points.length; i++) c.lineTo(points[i][0] * w, points[i][1] * h)
                if (ferme) c.closePath()
            }
            switch (e.agent) {
            case "assistant":
                break  // rendu par LogoAssistant, sans ajouter de rotation au mouvement de la vidéo
            case "antigravity": {
                var g = c.createLinearGradient(0, 0, w, 0)
                g.addColorStop(0, k); g.addColorStop(0.5, "#a374f0"); g.addColorStop(1, "#f0736d")
                c.strokeStyle = g; c.lineWidth = Math.max(2, w * 0.2)
                c.beginPath(); c.moveTo(w * 0.14, h * 0.86)
                c.bezierCurveTo(w * 0.2, h * 0.1, w * 0.8, h * 0.1, w * 0.86, h * 0.86); c.stroke()
                break
            }
            case "gemini": {
                var gg = c.createLinearGradient(0, h, w, 0)
                gg.addColorStop(0, "#4796e3"); gg.addColorStop(0.6, "#9177c7"); gg.addColorStop(1, "#ca6673")
                c.fillStyle = gg; c.beginPath(); c.moveTo(r, 0)
                c.quadraticCurveTo(r, r, w, r); c.quadraticCurveTo(r, r, r, h)
                c.quadraticCurveTo(r, r, 0, r); c.quadraticCurveTo(r, r, r, 0); c.fill()
                break
            }
            case "opencode":
                c.lineWidth = Math.max(1.5, w * 0.12)
                c.strokeRect(w * 0.12, h * 0.12, w * 0.76, h * 0.76)
                c.fillRect(w * 0.36, h * 0.36, w * 0.28, h * 0.28)
                break
            case "codex":
                chemin([[0.12, 0.26], [0.42, 0.5], [0.12, 0.74]]); c.stroke()
                chemin([[0.52, 0.8], [0.9, 0.8]]); c.stroke()
                break
            case "cursor":
                c.lineWidth = Math.max(1.4, w * 0.1)
                chemin([[0.5, 0.06], [0.9, 0.28], [0.9, 0.72], [0.5, 0.94], [0.1, 0.72], [0.1, 0.28]], true); c.stroke()
                chemin([[0.1, 0.28], [0.5, 0.5], [0.9, 0.28]]); c.stroke()
                chemin([[0.5, 0.5], [0.5, 0.94]]); c.stroke()
                break
            case "copilot":
                c.lineWidth = Math.max(1.4, w * 0.11)
                c.beginPath(); c.ellipse(w * 0.06, h * 0.3, w * 0.4, h * 0.36); c.stroke()
                c.beginPath(); c.ellipse(w * 0.54, h * 0.3, w * 0.4, h * 0.36); c.stroke()
                chemin([[0.46, 0.48], [0.54, 0.48]]); c.stroke()
                break
            case "qwen":
                c.lineWidth = Math.max(1.5, w * 0.12)
                chemin([[0.5, 0.08], [0.88, 0.29], [0.88, 0.71], [0.5, 0.92], [0.12, 0.71], [0.12, 0.29]], true); c.stroke()
                c.beginPath(); c.arc(r, r, w * 0.13, 0, Math.PI * 2); c.fill()
                break
            case "kiro":
                c.beginPath(); c.moveTo(w * 0.18, h * 0.9); c.lineTo(w * 0.18, h * 0.45)
                c.arc(r, h * 0.45, w * 0.32, Math.PI, 0); c.lineTo(w * 0.82, h * 0.9)
                c.lineTo(w * 0.66, h * 0.78); c.lineTo(w * 0.5, h * 0.9); c.lineTo(w * 0.34, h * 0.78); c.closePath(); c.fill()
                c.fillStyle = "#1b1b24"
                c.beginPath(); c.arc(w * 0.4, h * 0.45, w * 0.06, 0, Math.PI * 2); c.fill()
                c.beginPath(); c.arc(w * 0.6, h * 0.45, w * 0.06, 0, Math.PI * 2); c.fill()
                break
            case "amp":
                chemin([[0.12, 0.9], [0.5, 0.1], [0.88, 0.9]]); c.stroke()
                chemin([[0.3, 0.62], [0.7, 0.62]]); c.stroke()
                break
            default: {                                         // claude : rayons alternés, comme le logo
                c.translate(r, r)
                for (var i = 0; i < 8; i++) {
                    var a = i * Math.PI / 4, l = i % 2 ? r * 0.62 : r * 0.92
                    c.beginPath(); c.moveTo(Math.cos(a) * r * 0.18, Math.sin(a) * r * 0.18); c.lineTo(Math.cos(a) * l, Math.sin(a) * l); c.stroke()
                }
            }
            }
        }
    }
    Loader {
        anchors.fill: parent
        active: e.agent === "assistant"
        sourceComponent: Item {
            // Garder le blanc sur noir de la vidéo, y compris avec un thème clair.
            Rectangle { anchors.fill: parent; radius: width / 2; color: "#000000" }
            LogoAssistant { anchors.fill: parent; anime: e.tourne && !Reglages.sobre }
        }
    }
    // En Économie ou sans effets (Reglages.sobre) : immobile ; Hyprland n'a plus à recomposer l'écran à chaque image
    readonly property bool bouge: e.tourne && e.visible && !Reglages.sobre
    // Sur batterie, avec « Animations de l'île sur batterie : douces » (par défaut) : un tour en 4 s au lieu de 2,6.
    // Un Animator garde la durée de son départ : la nouvelle vaut à la prochaine mise en route.
    readonly property int dureeTour: UPower.onBattery && Reglages.val("ILE_ANIM_BATTERIE", "douces") !== "continues" ? 4000 : 2600
    RotationAnimator on rotation {
        running: e.bouge && e.tournante; from: 0; to: 360; duration: e.dureeTour; loops: Animation.Infinite
        onStarted: retour.stop()
        // L'angle réel vient d'être écrit : l'étincelle qui s'arrête de travailler revient droite en douceur,
        // celle qui laisse la place à un logo qui ne tourne pas revient d'un coup
        onStopped: if (e.tournante) retour.start(); else e.rotation = 0
    }
    NumberAnimation { id: retour; target: e; property: "rotation"; to: 0; duration: 300 }

    // Les autres : flottent (montent et redescendent) pendant le travail
    SequentialAnimation {
        running: e.bouge && !e.tournante && e.agent !== "assistant"; loops: Animation.Infinite
        YAnimator { target: dessin; from: 0; to: -e.taille * 0.16; duration: 900; easing.type: Easing.InOutSine }
        YAnimator { target: dessin; from: -e.taille * 0.16; to: 0; duration: 900; easing.type: Easing.InOutSine }
        onStopped: dessin.y = 0                        // l'Animator a écrit sa dernière hauteur : le logo revient en place
    }
}

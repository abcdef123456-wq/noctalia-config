// Mini disposition d'un thème (vignette du carrousel) : barre, île, deux fenêtres et dock, dessinés à l'échelle d'un écran
// de 1280 px de large avec les valeurs EFFECTIVES de `nc-reglages themes --json` (objet « disposition »). Statique : rien
// n'est animé, rien ne tourne, rien n'est généré dans un fichier. Sans `disp`, il ne dessine rien.
import QtQuick

Item {
    id: md
    property var disp: null
    property color surface: "#1e1f24"
    property color primaire: "#8ab4f8"
    property color secondaire: "#8ab4f8"
    property color couleurBarre: "#101114"
    property bool avecIle: true
    clip: true

    readonly property real s: width / 1280
    readonly property var b: disp && disp.barre ? disp.barre : ({})
    readonly property var f: disp && disp.fenetres ? disp.fenetres : ({})
    readonly property var dk: disp && disp.dock ? disp.dock : ({})
    readonly property var il: disp && disp.ile ? disp.ile : ({})
    // une valeur > 0 reste visible (au moins 1 px) même à cette échelle
    function px(v) { return v > 0 ? Math.max(1, v * md.s) : 0 }

    readonly property string posBarre: b.position || "top"
    readonly property real ep: Math.max(2, px(b.epaisseur || 36))
    readonly property real mb: px(b.marge || 0)
    readonly property bool dockVisible: dk.actif === true && dk.cache !== true
    readonly property string posDock: dk.position || "bottom"
    readonly property real epDock: Math.max(3, px(56))

    // zone libre pour les fenêtres : l'écran moins la barre et le dock
    readonly property rect zone: {
        var x0 = 0, y0 = 0, x1 = width, y1 = height, r = ep + 2 * mb
        if (posBarre === "top") y0 += r; else if (posBarre === "bottom") y1 -= r
        else if (posBarre === "left") x0 += r; else x1 -= r
        if (dockVisible) {
            var d = epDock + px(8)
            if (posDock === "top") y0 += d; else if (posDock === "left") x0 += d
            else if (posDock === "right") x1 -= d; else y1 -= d
        }
        var m = px(f.marge || 0)
        return Qt.rect(x0 + m, y0 + m, Math.max(1, x1 - x0 - 2 * m), Math.max(1, y1 - y0 - 2 * m))
    }
    readonly property real g: px(f.espace || 0)
    // deux rectangles {x, y, w, h} selon la disposition
    readonly property var cases: {
        var z = zone, e = g, d = f.disposition || "dwindle", o = f.orientation || "auto"
        if (d === "scrolling") {
            var w1 = z.width * 0.62
            return [Qt.rect(z.x, z.y, w1, z.height), Qt.rect(z.x + w1 + e, z.y, w1, z.height)]   // la 2e colonne sort de l'écran
        }
        if (d === "master" && (o === "haut" || o === "bas")) {
            var hm = (z.height - e) * 0.6, hs = z.height - e - hm
            return o === "haut" ? [Qt.rect(z.x, z.y, z.width, hm), Qt.rect(z.x, z.y + hm + e, z.width, hs)]
                                : [Qt.rect(z.x, z.y + hs + e, z.width, hm), Qt.rect(z.x, z.y, z.width, hs)]
        }
        var wm = (z.width - e) * (d === "master" ? 0.6 : 0.5), ws = z.width - e - wm
        if (d === "master" && o === "droite")
            return [Qt.rect(z.x + ws + e, z.y, wm, z.height), Qt.rect(z.x, z.y, ws, z.height)]
        return [Qt.rect(z.x, z.y, wm, z.height), Qt.rect(z.x + wm + e, z.y, ws, z.height)]
    }

    Repeater {
        model: md.disp ? 2 : 0
        delegate: Rectangle {
            x: md.cases[index].x; y: md.cases[index].y; width: md.cases[index].width; height: md.cases[index].height
            radius: Math.min(Math.min(width, height) / 2, md.px(md.f.arrondi || 0))
            color: Qt.alpha(Qt.lighter(md.surface, 1.35), 0.9)
            border.width: md.px(md.f.bordure || 0)
            border.color: index === 0 ? md.primaire : md.secondaire
        }
    }
    // le dock, seulement s'il est actif et visible
    Rectangle {
        objectName: "nc-mini-dock"
        visible: md.dockVisible
        readonly property bool vertical: md.posDock === "left" || md.posDock === "right"
        readonly property real marge: md.px(8)
        width: vertical ? md.epDock : md.width * 0.28
        height: vertical ? md.height * 0.28 : md.epDock
        x: md.posDock === "left" ? marge : md.posDock === "right" ? md.width - width - marge : (md.width - width) / 2
        y: md.posDock === "top" ? marge : md.posDock === "bottom" ? md.height - height - marge : (md.height - height) / 2
        radius: Math.min(width, height) / 2
        color: Qt.alpha(md.couleurBarre, 0.9)
        border.width: 1; border.color: Qt.alpha(md.primaire, 0.5)
    }
    // la barre (bord collé si la marge vaut 0)
    Rectangle {
        objectName: "nc-mini-barre"
        readonly property bool vertical: md.posBarre === "left" || md.posBarre === "right"
        x: md.posBarre === "right" ? md.width - width - md.mb : md.mb
        y: md.posBarre === "bottom" ? md.height - height - md.mb : md.mb
        width: vertical ? md.ep : md.width - 2 * md.mb
        height: vertical ? md.height - 2 * md.mb : md.ep
        radius: md.mb > 0 ? Math.min(width, height) / 2 : 0
        color: md.couleurBarre
    }
    // l'île, par-dessus
    Rectangle {
        objectName: "nc-mini-ile"
        visible: md.avecIle
        anchors.horizontalCenter: parent.horizontalCenter
        y: Math.round(md.height * 0.07)
        width: md.width * 0.4; height: md.height * 0.16
        radius: Math.min(height / 2, height * (md.il.rayon === undefined ? 100 : md.il.rayon) / 200)
        color: "#000000"
        border.width: 1; border.color: Qt.alpha(md.primaire, 0.6)
    }
}

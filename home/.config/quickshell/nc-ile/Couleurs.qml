pragma Singleton
// Couleurs de l'île, assorties au fond d'écran sans en faire trop : la palette que Noctalia tire du fond
// (~/.config/noctalia/colors.json, relue dès qu'elle change) donne une teinte, posée en touche légère.
//   fond      noir à peine teinté (la pilule reste presque noire, comme sur iPhone ; ouverte, un peu plus)
//   gris      les gris d'Apple (cartes, boutons éteints, curseurs) légèrement teintés
//   accent    remplace le bleu d'Apple (boutons actifs, coches, sélection) : couleur du fond, gardée assez
//             soutenue pour une icône blanche dessus
// Rouge, vert, orange et jaune gardent leur sens (alerte, recharge, minuteur, Économie) et restent ceux d'Apple.
// Fond d'écran presque sans couleur (noir et blanc) : gris neutres et bleu d'Apple. Sans palette : couleurs d'Apple.
import QtQuick
import Quickshell
import Quickshell.Io

Singleton {
    id: c

    property color primaire: "#0a84ff"
    property color surface: "#000000"
    property bool palette: false

    FileView {
        path: Quickshell.env("HOME") + "/.config/noctalia/colors.json"
        watchChanges: true
        onFileChanged: reload()
        onLoaded: {
            try {
                var j = JSON.parse(text())
                c.primaire = j.mPrimary; c.surface = j.mSurface; c.palette = true
            } catch (e) { c.palette = false }
        }
        onLoadFailed: c.palette = false
    }

    // Force de la teinte : nulle pour une palette grise, pleine pour une palette colorée
    readonly property real force: palette ? Math.max(0, Math.min(1, (primaire.hslSaturation - 0.12) / 0.3)) : 0
    readonly property color teinte: Qt.hsla(primaire.hslHue, Math.min(primaire.hslSaturation, 0.75), 0.5, 1)

    function melange(a, b, t) {
        a = Qt.lighter(a, 1); b = Qt.lighter(b, 1)          // "#rrggbb" -> couleur
        return Qt.rgba(a.r + (b.r - a.r) * t, a.g + (b.g - a.g) * t, a.b + (b.b - a.b) * t, 1)
    }
    function gris(base, k) { return melange(base, teinte, k * force) }

    // Fond de l'île : noir mêlé à la surface sombre de la palette (déjà teintée par le fond d'écran)
    readonly property color fondCompact: palette ? melange("#000000", surface, 0.35) : "#000000"
    readonly property color fond: palette ? melange("#000000", surface, 0.7) : "#000000"
    // Liseré de l'île ouverte : un filet de la couleur du fond d'écran, à peine visible
    readonly property color lisere: Qt.rgba(teinte.r, teinte.g, teinte.b, 0.22 * force)

    readonly property color carte: gris("#1c1c1e", 0.06)
    readonly property color carteSurvol: gris("#242426", 0.07)
    readonly property color gris2: gris("#2c2c2e", 0.08)
    readonly property color gris3: gris("#3a3a3c", 0.09)
    readonly property color gris4: gris("#48484a", 0.10)
    readonly property color gris5: gris("#5a5a5e", 0.10)
    readonly property color texteSec: gris("#98989d", 0.08)
    readonly property color texteDoux: gris("#d1d1d6", 0.05)

    // Accent : teinte du fond, saturation et luminosité ramenées dans la zone du bleu d'Apple ; une teinte claire
    // (jaune, cyan) est assombrie jusqu'à ce qu'une icône blanche reste lisible dessus
    function lum(x) {
        function l(v) { return v <= 0.04045 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4) }
        return 0.2126 * l(x.r) + 0.7152 * l(x.g) + 0.0722 * l(x.b)
    }
    function calculerAccent() {
        if (force <= 0.3) return Qt.lighter("#0a84ff", 1)
        var s = Math.max(0.5, Math.min(primaire.hslSaturation, 0.75))
        var l = Math.max(0.45, Math.min(primaire.hslLightness, 0.55))
        var a = Qt.hsla(primaire.hslHue, s, l, 1)
        for (var i = 0; i < 12 && lum(a) > 0.26; i++) { l -= 0.03; a = Qt.hsla(primaire.hslHue, s, l, 1) }
        return a
    }
    readonly property color accent: calculerAccent()
    readonly property color accentClair: force > 0.3 ? Qt.lighter(accent, 1.18) : "#409cff"
}

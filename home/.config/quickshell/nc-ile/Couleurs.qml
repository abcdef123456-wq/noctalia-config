pragma Singleton
// Couleurs de l'île : celles du terminal, pour qu'elle fasse partie de la config comme les fenêtres.
// nc-theme-sync les tire du fond d'écran (comme le thème de kitty) dans ~/.config/nc/palette-ile.json, relu dès
// qu'il change : fond et textes du terminal, gris en paliers au-dessus du fond, accent du terminal (curseur,
// onglet actif) et couleurs ANSI pour les états (vert : recharge, orange : minuteur, rouge : alerte…), bordure en
// dégradé des fenêtres. Sur une couleur vive, icônes et textes prennent la couleur du fond (comme l'onglet actif).
// Réglages (nc-reglages, ~/.config/nc/reglages.conf) :
//   ILE_STYLE=terminal (par défaut) | noir (île noire d'iPhone, couleurs d'Apple)
//   ILE_CONTOUR=degrade (par défaut, comme les fenêtres) | discret (filet de l'accent) | aucun
import QtQuick
import Quickshell
import Quickshell.Io

Singleton {
    id: c

    property var p: ({})                 // palette du terminal (vide : couleurs d'Apple)
    property string style: "terminal"
    property string contour: "degrade"

    FileView {
        path: Quickshell.env("HOME") + "/.config/nc/palette-ile.json"
        watchChanges: true
        onFileChanged: reload()
        onLoaded: { try { c.p = JSON.parse(text()) } catch (e) { c.p = {} } }
        onLoadFailed: c.p = {}
    }
    FileView {
        path: Quickshell.env("HOME") + "/.config/nc/reglages.conf"
        watchChanges: true
        onFileChanged: reload()
        onLoaded: {
            var r = {}
            text().split("\n").forEach(l => { var m = l.match(/^\s*([A-Z0-9_]+)\s*=\s*"?([^"#]*?)"?\s*(#.*)?$/); if (m) r[m[1]] = m[2] })
            c.style = r.ILE_STYLE === "noir" ? "noir" : "terminal"
            c.contour = ["degrade", "discret", "aucun"].indexOf(r.ILE_CONTOUR) >= 0 ? r.ILE_CONTOUR : "degrade"
        }
        onLoadFailed: { c.style = "terminal"; c.contour = "degrade" }
    }

    readonly property bool terminal: style === "terminal" && p.fond !== undefined
    function v(cle, apple) { return terminal && p[cle] ? p[cle] : apple }

    readonly property color fond: v("fond", "#000000")
    readonly property color texte: v("texte", "#ffffff")
    readonly property color texteSec: v("texteSec", "#98989d")
    readonly property color texteDoux: v("texteDoux", "#d1d1d6")

    readonly property color carte: v("carte", "#1c1c1e")
    readonly property color carteSurvol: v("carteSurvol", "#242426")
    readonly property color gris2: v("gris2", "#2c2c2e")
    readonly property color gris3: v("gris3", "#3a3a3c")
    readonly property color gris4: v("gris4", "#48484a")
    readonly property color gris5: v("gris5", "#5a5a5e")

    readonly property color accent: v("accent", "#0a84ff")
    readonly property color accentClair: terminal ? Qt.lighter(accent, 1.12) : "#409cff"
    readonly property color surAccent: v("surAccent", "#ffffff")
    // Icône ou texte posé sur une couleur vive (vert, orange, jaune…) : sombre dans le terminal, blanc chez Apple
    readonly property color surCouleur: v("surCouleur", "#ffffff")

    readonly property color rouge: v("rouge", "#ff453a")
    readonly property color vert: v("vert", "#30d158")
    readonly property color jaune: v("jaune", "#ffd60a")
    readonly property color orange: v("orange", "#ff9f0a")
    readonly property color bleu: v("bleu", "#0a84ff")
    readonly property color violet: v("violet", "#5e5ce6")
    readonly property color rose: v("violet", "#ff375f")
    readonly property color fondVert: v("fondVert", "#0d3318")
    readonly property color fondOrange: v("fondOrange", "#3a2a10")

    // Contour : dégradé des fenêtres, filet de l'accent, ou rien
    readonly property var degrade: terminal && p.bordure ? p.bordure : [accent, accent, accent]
    readonly property bool aContour: contour !== "aucun" && (terminal || contour === "discret")
}

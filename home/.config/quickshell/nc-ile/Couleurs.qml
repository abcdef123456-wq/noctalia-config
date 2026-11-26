pragma Singleton
// Couleurs de l'île : celles du terminal, pour qu'elle fasse partie de la config comme les fenêtres.
// nc-theme-sync les tire du fond d'écran (comme le thème de kitty) dans ~/.config/nc/palette-ile.json, relu dès
// qu'il change : fond et textes du terminal, gris en paliers au-dessus du fond, accent du terminal (curseur,
// onglet actif) et couleurs ANSI pour les états (vert : recharge, orange : minuteur, rouge : alerte…), contour
// dans la teinte de l'accent (adoucie, nuancée d'un bord à l'autre). Sur une couleur vive, icônes et textes prennent la couleur du fond (comme l'onglet actif).
// Réglages (nc-reglages, ~/.config/nc/reglages.conf) :
//   ILE_STYLE=terminal (par défaut) | noir (île noire d'iPhone, couleurs d'Apple)
//   ILE_CONTOUR=degrade (par défaut, l'accent fondu au milieu) | discret (filet de l'accent) | aucun
//   Allure (par défaut : celle d'avant, rien ne change) :
//   ILE_RAYON=auto ou normal (rayons d'origine, 100) | carre (0) | doux (50) | rond (200) ; ou 0 à 200 : % des rayons d'origine, plafonné à la demi-taille
//   ILE_CONTOUR_EPAISSEUR=2 (0 à 4 px) ; ILE_VERRE=100 (85 à 100 % d'opacité du fond, sans flou)
//   ILE_POLICE=Adwaita Sans, ou une liste « A, B » : la première installée (aucune : Adwaita Sans) ; ILE_MAJUSCULES=non | oui
//   ILE_FORME=pilule (par défaut) | encoche (collée au bord haut, coins du haut carrés) | rectangle (coins faibles) | cadre (bordure d'accent fine, voile du fond à 72 % : le texte reste lisible sur un fond clair) | point (fermée : un point d'accent de 10 px)
//   ILE_ANIM=ressort (allure d'origine) | doux | vif | sec ; ILE_LUEUR=non | oui (halo autour de l'île ouverte)
import QtQuick
import Quickshell
import Quickshell.Io

Singleton {
    id: c

    property var p: ({})                 // palette du terminal (vide : couleurs d'Apple)
    readonly property string style: Reglages.val("ILE_STYLE", "terminal") === "noir" ? "noir" : "terminal"
    readonly property string contour: ["degrade", "discret", "aucun"].indexOf(Reglages.val("ILE_CONTOUR", "")) >= 0
                                      ? Reglages.val("ILE_CONTOUR", "") : "degrade"

    // Allure : chaque valeur invalide retombe sur celle d'origine
    readonly property real rayonPct: {
        const r = Reglages.val("ILE_RAYON", "auto")
        const noms = { "auto": 100, "normal": 100, "carre": 0, "doux": 50, "rond": 200 }
        if (Object.keys(noms).indexOf(r) >= 0) return noms[r]
        const n = /^[0-9]+$/.test(r) ? parseInt(r) : 100
        return n <= 200 ? n : 100                   // 100 : rayons d'origine
    }
    readonly property string forme: ["encoche", "rectangle", "cadre", "point"].indexOf(Reglages.val("ILE_FORME", "")) >= 0 ? Reglages.val("ILE_FORME", "") : "pilule"
    // Rectangle et cadre : tous les rayons de l'île (pages comprises) restent faibles
    readonly property real rayonFinal: forme === "rectangle" || forme === "point" ? Math.min(rayonPct, 12) : (forme === "cadre" ? Math.min(rayonPct, 5) : rayonPct)
    // Rayon d'un élément de taille w x h : « base » est son rayon d'origine, multiplié par le réglage, jamais au-delà de la demi-taille
    function rayon(base, w, h) { return Math.min(base * rayonFinal / 100, Math.min(w, h) / 2) }
    function entier(cle, defaut, mini, maxi) {
        const r = Reglages.val(cle, "")
        const n = /^[0-9]+$/.test(r) ? parseInt(r) : defaut
        return n >= mini && n <= maxi ? n : defaut
    }
    readonly property int epaisseur: entier("ILE_CONTOUR_EPAISSEUR", 2, 0, 4)
    readonly property real verre: entier("ILE_VERRE", 100, 85, 100) / 100
    readonly property bool majuscules: Reglages.val("ILE_MAJUSCULES", "non") === "oui"
    // ILE_ACCENTS=accent : jauges, barres de la musique et du volume dans la couleur d'accent du thème (sinon : texte)
    readonly property color jauge: Reglages.val("ILE_ACCENTS", "texte") === "accent" ? accent : texte
    readonly property bool lueur: Reglages.val("ILE_LUEUR", "non") === "oui"
    // ILE_CONTOUR_FERMEE=oui : contour et lueur aussi autour de la pilule fermée (sinon : île ouverte seulement)
    readonly property bool contourFermee: Reglages.val("ILE_CONTOUR_FERMEE", "non") === "oui"
    readonly property string police: {
        var installees = Qt.fontFamilies(), liste = String(Reglages.val("ILE_POLICE", "")).split(",")
        for (var i = 0; i < liste.length; i++) {
            var nom = liste[i].trim()
            if (nom !== "" && installees.indexOf(nom) >= 0) return nom
        }
        return "Adwaita Sans"
    }
    // Délègue à Mouvement quand présent (repli autonome pour les essais hors écran ne chargeant que Couleurs)
    readonly property string animNom: {
        if (typeof Mouvement !== "undefined") return Mouvement.profilBase
        var v = Reglages.val("ILE_ANIM", "ressort")
        return (v === "ressort" || v === "doux" || v === "vif" || v === "sec") ? v : "ressort"
    }
    readonly property var anim: {
        if (typeof Mouvement !== "undefined") {
            var b = Mouvement.profils[Mouvement.profilBase]
            var f = Mouvement.vitessePct / 100
            return {
                raideur: f === 1 ? b.raideur : Number((b.raideur * f).toFixed(3)),
                amortiL: b.amortiL,
                amortiH: b.amortiH,
                duree: Mouvement.echelonnerDuree(b.duree, f),
                courbe: b.courbe,
                contour: Mouvement.echelonnerDuree(b.dureeContour, f),
                spot: Mouvement.echelonnerDuree(b.dureeSpot, f)
            }
        }
        var def = ({
            "ressort": { raideur: 3.4, amortiL: 0.34, amortiH: 0.36, duree: 280, courbe: Easing.OutCubic, contour: 220, spot: 170 },
            "doux":    { raideur: 2.2, amortiL: 0.7,  amortiH: 0.7,  duree: 400, courbe: Easing.InOutQuad, contour: 320, spot: 240 },
            "vif":     { raideur: 5.5, amortiL: 0.28, amortiH: 0.3,  duree: 200, courbe: Easing.OutBack,  contour: 150, spot: 120 },
            "sec":     { raideur: 8,   amortiL: 1,    amortiH: 1,    duree: 120, courbe: Easing.Linear,   contour: 100, spot: 90 }
        })
        return def[animNom]
    }
    FileView {
        id: pal
        path: Quickshell.env("HOME") + "/.config/nc/palette-ile.json"
        watchChanges: true
        onFileChanged: reload()
        onLoaded: { try { c.p = JSON.parse(text()) } catch (e) { c.p = {} } }
        onLoadFailed: c.p = {}
    }
    readonly property bool terminal: style === "terminal" && p.fond !== undefined
    function v(cle, apple) { return terminal && p[cle] ? p[cle] : apple }

    // Palette sombre (par défaut, y compris sans palette ni style noir) ou claire (fond clair, texte sombre) : « sombre » de palette-ile.json
    readonly property bool sombre: !(terminal && p.sombre === false)
    // Filet ou reflet posé sur un fond de carte : blanc en sombre, la couleur du texte en clair (le blanc y serait invisible)
    readonly property color voile: sombre ? "#ffffff" : texte

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
    readonly property color rose: v("rose", "#ff375f")
    readonly property color cyan: v("cyan", "#64d2ff")
    readonly property color fondVert: v("fondVert", "#0d3318")
    readonly property color fondOrange: v("fondOrange", "#3a2a10")

    // Contour : dégradé des fenêtres, filet de l'accent, ou rien
    readonly property var degrade: terminal && p.bordure ? p.bordure : [accent, accent, accent]
    readonly property bool aContour: contour !== "aucun" && (terminal || contour === "discret")

    // Identité visuelle dérivée du thème actif (partagée par l'île, le Centre de contrôle et les Réglages)
    readonly property string themeActif: (Reglages.style && Reglages.style["STYLE"]) || Reglages.val("STYLE", "noctalia")
    readonly property bool estCarre: rayonFinal <= 15 || forme === "rectangle" || forme === "cadre"
    readonly property bool estEditorial: /Serif/i.test(police)
    readonly property bool estTech: majuscules || /Mono|Code|Doto|Orbitron|Rajdhani/i.test(police)
    readonly property string familleTheme: {
        if (themeActif === "matrice") return "matrice"
        if (["retro", "pluie-verte"].includes(themeActif)) return "terminal"
        if (["apple", "oled", "clair-neutre"].includes(themeActif)) return "apple"
        if (["brutaliste", "cyberjaune", "gruvbox"].includes(themeActif)) return "brut"
        if (["papier", "solarized-clair", "sakura", "kanagawa", "rose-aube", "everforest"].includes(themeActif)) return "editorial"
        if (["synthwave", "vaporwave", "tokyo", "dracula", "ocean"].includes(themeActif)) return "neon"
        if (forme === "point") return "matrice"
        if (forme === "cadre" && estTech) return "terminal"
        if (forme === "encoche") return "apple"
        if (estCarre && estTech) return "brut"
        if (estEditorial) return "editorial"
        if (lueur) return "neon"
        return "noctalia"
    }
    readonly property bool styleApple: familleTheme === "apple"
    readonly property bool styleBrut: familleTheme === "brut"
    readonly property bool styleTerminal: familleTheme === "terminal" || familleTheme === "matrice"
    readonly property bool styleEditorial: familleTheme === "editorial"
    readonly property bool styleNeon: familleTheme === "neon"
    readonly property bool styleModerne: familleTheme === "noctalia"

    // Surfaces & bordures adaptées à l'archétype du thème actif
    readonly property color surfaceDouce: {
        if (styleBrut) return Qt.alpha(voile, sombre ? 0.05 : 0.04)
        if (styleTerminal) return Qt.alpha(accent, sombre ? 0.07 : 0.06)
        if (styleEditorial) return Qt.alpha(voile, sombre ? 0.04 : 0.035)
        if (styleNeon) return Qt.alpha(accent, sombre ? 0.09 : 0.07)
        return Qt.alpha(carte, sombre ? 0.78 : 0.88)
    }
    readonly property color surfaceActive: {
        if (styleBrut || styleTerminal) return accent
        if (styleNeon) return Qt.alpha(accent, sombre ? 0.24 : 0.18)
        if (styleEditorial) return Qt.alpha(accent, sombre ? 0.15 : 0.11)
        return Qt.alpha(accent, sombre ? 0.20 : 0.14)
    }
    readonly property color texteSurSurfaceActive: (styleBrut || styleTerminal) ? surAccent : texte
    readonly property color bordureSubtile: {
        if (styleBrut) return Qt.alpha(voile, sombre ? 0.24 : 0.28)
        if (styleTerminal || forme === "cadre") return Qt.alpha(accent, sombre ? 0.44 : 0.50)
        if (styleNeon) return Qt.alpha(accent, 0.34)
        if (styleEditorial) return Qt.alpha(voile, sombre ? 0.14 : 0.16)
        if (styleApple) return Qt.alpha(voile, sombre ? 0.09 : 0.10)
        return Qt.alpha(voile, sombre ? 0.10 : 0.13)
    }
    readonly property real epaisseurBordureCarte: (styleBrut || styleTerminal || forme === "cadre") ? Math.max(1, Math.min(2, epaisseur)) : 1
    readonly property color separateur: {
        if (styleTerminal) return Qt.alpha(accent, 0.26)
        if (styleBrut) return Qt.alpha(voile, sombre ? 0.18 : 0.22)
        if (styleNeon) return Qt.alpha(accent, 0.22)
        return Qt.alpha(voile, sombre ? 0.09 : 0.12)
    }
    readonly property color accentDoux: Qt.alpha(accent, sombre ? 0.17 : 0.13)
    readonly property color accentBord: Qt.alpha(accent, sombre ? 0.48 : 0.38)
    readonly property real opacitePanneau: Reglages.val("FENETRES_FLOU", "oui") !== "non" && !Reglages.sobre
                                           ? (sombre ? Math.min(verre, styleApple ? 0.84 : 0.88) : Math.min(verre, 0.92))
                                           : Math.max(verre, 0.97)
    // Géométrie harmonisée par archétype de thème (utilisée par l'île, le Centre de contrôle et les Réglages)
    readonly property real rayonPanneau: styleTerminal ? 2 : (styleBrut ? 4 : (styleEditorial ? 14 : (styleNeon ? 18 : (styleApple ? 24 : 20))))
    readonly property real rayonBloc: styleTerminal ? 2 : (styleBrut ? 3 : (styleEditorial ? 10 : (styleNeon ? 14 : (styleApple ? 16 : 14))))
    readonly property real rayonBouton: styleTerminal ? 2 : (styleBrut ? 3 : (styleEditorial ? 8 : (styleNeon ? 10 : 12)))
    // Libellé humain du thème actif (pour les en-têtes / page d'accueil des réglages)
    readonly property string nomThemeAffiche: {
        var n = String(themeActif || "noctalia")
        return n.split("-").map(s => s ? s.charAt(0).toUpperCase() + s.slice(1) : "").join(" ")
    }
    readonly property string libelleArchetype: {
        if (styleApple) return Reglages.t("Verre & capsule", "Glass & capsule")
        if (styleBrut) return Reglages.t("Architectural", "Architectural")
        if (styleTerminal) return Reglages.t("Terminal", "Terminal")
        if (styleEditorial) return Reglages.t("Éditorial", "Editorial")
        if (styleNeon) return Reglages.t("Néon", "Neon")
        return "Noctalia"
    }
}

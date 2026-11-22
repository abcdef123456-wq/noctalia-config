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
    // Ressorts de la largeur et de la hauteur de l'île, durée et courbe du rayon, durées du contour et du Spotlight
    readonly property var animations: ({
        "ressort": { raideur: 3.4, amortiL: 0.34, amortiH: 0.36, duree: 280, courbe: Easing.OutCubic, contour: 220, spot: 170 },
        "doux":    { raideur: 2.2, amortiL: 0.7,  amortiH: 0.7,  duree: 400, courbe: Easing.InOutQuad, contour: 320, spot: 240 },
        "vif":     { raideur: 5.5, amortiL: 0.28, amortiH: 0.3,  duree: 200, courbe: Easing.OutBack,  contour: 150, spot: 120 },
        "sec":     { raideur: 8,   amortiL: 1,    amortiH: 1,    duree: 120, courbe: Easing.Linear,   contour: 100, spot: 90 }
    })
    readonly property string animNom: Object.keys(animations).indexOf(Reglages.val("ILE_ANIM", "ressort")) >= 0 ? Reglages.val("ILE_ANIM", "ressort") : "ressort"
    readonly property var anim: animations[animNom]

    FileView {
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
    readonly property color fondVert: v("fondVert", "#0d3318")
    readonly property color fondOrange: v("fondOrange", "#3a2a10")

    // Contour : dégradé des fenêtres, filet de l'accent, ou rien
    readonly property var degrade: terminal && p.bordure ? p.bordure : [accent, accent, accent]
    readonly property bool aContour: contour !== "aucun" && (terminal || contour === "discret")
}

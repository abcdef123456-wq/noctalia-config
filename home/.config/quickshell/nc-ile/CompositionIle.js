.pragma library

// Bord et forme des onglets, largeur utile, composition du tableau de bord et du lecteur.
// Les petits dessins suivent la même grille de 100 × 100 ; ils n'ont besoin ni d'images ni de police externe.
function plan(bord, onglets, largeur, accueil, media, icone, dessin) {
    return { bord, onglets, largeur, accueil, media, icone, dessin }
}
const plans = {
    noctalia: plan("haut", "capsules", 484, "orbite", "scene", "dark_mode",
        "M70,16 A35,35 0 1,0 78,75 A31,31 0 0,1 70,16 Z M79,20 v17 m-8,-8 h16 M85,48 v10 m-5,-5 h10"),
    apple: plan("bas", "capsules", 520, "carte", "portrait", "blur_on",
        "M14,56 Q14,40 31,37 Q35,18 52,22 Q65,22 71,39 Q90,39 90,56 Q90,72 73,72 H31 Q14,72 14,56 Z M26,80 H78"),
    oled: plan("droite", "icones", 442, "minimal", "console", "contrast",
        "M50,10 A40,40 0 1,0 50,90 Z M60,18 A34,34 0 0,1 60,82 M70,32 A22,22 0 0,1 70,68"),
    "clair-neutre": plan("gauche", "index", 564, "marge", "bande", "view_sidebar",
        "M20,18 H78 V82 H20 Z M38,18 V82 M48,33 H69 M48,47 H69 M48,61 H61"),
    brutaliste: plan("gauche", "blocs", 594, "dalle", "console", "view_quilt",
        "M12,22 H61 V66 H12 Z M31,66 V84 H84 V39 H61 M22,32 H47 M22,44 H47 M65,73 H75"),
    cyberjaune: plan("droite", "blocs", 603, "dalle", "bande", "warning",
        "M50,10 L91,81 H9 Z M50,34 V56 m0,9 v5 M18,89 h18 m9,0 h12 m9,0 h16"),
    gruvbox: plan("bas", "blocs", 548, "carte", "vinyle", "album",
        "M10,23 H90 V77 H10 Z M22,35 H78 V55 H22 Z M25,77 l7,-14 h36 l7,14 M32,45 a5,5 0 1,0 10,0 a5,5 0 1,0 -10,0 M58,45 a5,5 0 1,0 10,0 a5,5 0 1,0 -10,0"),
    matrice: plan("haut", "index", 502, "terminal", "console", "grid_on",
        "M14,14 H26 M14,24 H39 M14,34 H26 M14,44 H55 M14,54 H39 M14,64 H26 M14,74 H69 M35,14 h12 m8,0 h24 M48,24 h24 M35,34 h36 M64,44 h22 M48,54 h32 M35,64 h23 M14,84 h42"),
    retro: plan("bas", "index", 558, "terminal", "bande", "tv",
        "M19,24 Q50,19 81,24 Q90,50 81,73 Q50,78 19,73 Q10,50 19,24 Z M26,36 H67 M24,48 H66 M25,60 H68 M31,75 L27,82 M69,75 L73,82"),
    "pluie-verte": plan("gauche", "icones", 483, "terminal", "console", "grain",
        "M24,7 v23 m0,14 v32 M40,14 v43 m0,12 v18 M56,23 v28 m0,10 v13 M72,10 v37 m0,14 v27 M86,35 v13 m0,14 v13 M12,48 v17"),
    papier: plan("gauche", "filets", 576, "marge", "portrait", "description",
        "M25,11 H61 L77,27 V87 H25 Z M61,11 V27 H77 M35,40 H67 M35,50 H67 M35,60 H56 M35,70 H64 M18,20 h7 m-7,18 h7 m-7,18 h7 m-7,18 h7"),
    "solarized-clair": plan("bas", "filets", 534, "carte", "bande", "architecture",
        "M18,18 H82 V82 H18 Z M18,39 H82 M18,61 H82 M39,18 V82 M61,18 V82 M13,50 H87 M50,13 V87"),
    sakura: plan("haut", "galerie", 590, "jardin", "radial", "local_florist",
        "M49,42 C20,40 31,10 49,23 C63,8 78,33 55,42 C84,35 89,64 65,66 C62,88 37,79 47,54 C30,81 8,61 24,49 C16,29 40,27 49,42 Z M50,46 l10,12 M15,79 l10,-6 M81,19 l7,-5"),
    kanagawa: plan("droite", "filets", 602, "jardin", "scene", "waves",
        "M5,75 C26,72 34,83 59,66 C82,51 78,22 58,22 C45,22 37,30 40,36 C49,28 57,31 58,39 C59,53 41,61 16,57 M6,84 C34,77 57,95 92,70 M67,16 l8,-3 M85,30 l10,3"),
    "rose-aube": plan("bas", "galerie", 508, "aube", "radial", "light_mode",
        "M17,66 A33,33 0 0,1 83,66 M8,67 H92 M19,77 H81 M34,86 H66 M50,13 V24 M22,23 l6,10 M78,23 l-6,10"),
    everforest: plan("gauche", "galerie", 561, "jardin", "portrait", "forest",
        "M9,71 L28,39 H20 L36,16 L52,39 H44 L63,71 Z M43,71 V85 M60,64 L75,41 L89,64 H82 L94,80 H55 L67,64 Z M76,80 V90"),
    synthwave: plan("bas", "galerie", 612, "horizon", "scene", "wb_twilight",
        "M24,48 A26,26 0 0,1 76,48 Z M26,54 H74 M31,60 H69 M39,66 H61 M12,73 H88 M6,83 H94 M26,70 L11,91 M41,70 L35,91 M59,70 L65,91 M74,70 L89,91"),
    vaporwave: plan("droite", "galerie", 575, "horizon", "vinyle", "play_circle",
        "M13,24 H76 V73 H13 Z M28,73 L42,54 L65,73 M50,37 A6,6 0 1,0 62,37 A6,6 0 1,0 50,37 M77,39 H88 V85 H30 V74"),
    tokyo: plan("haut", "index", 580, "marge", "scene", "location_city",
        "M9,79 V48 H22 V33 H34 V52 H45 V18 H62 V40 H74 V54 H89 V79 Z M50,29 h7 m-7,10 h7 m-7,10 h7 m-7,10 h7 M15,59 h6 m5,-16 h5 m45,21 h6"),
    dracula: plan("droite", "galerie", 562, "orbite", "vinyle", "nightlight",
        "M9,34 Q30,28 43,44 L46,33 L50,39 L54,33 L57,44 Q70,28 91,34 L82,59 Q72,53 65,67 Q58,62 50,73 Q42,62 35,67 Q28,53 18,59 Z M17,22 l6,-7 M82,20 l-4,-7"),
    ocean: plan("haut", "filets", 537, "horizon", "radial", "water",
        "M7,48 C20,25 35,24 49,43 S78,60 93,38 M7,62 C20,39 35,38 49,57 S78,74 93,52 M7,76 C20,53 35,52 49,71 S78,88 93,66 M68,20 a5,5 0 1,0 10,0 a5,5 0 1,0 -10,0"),
    catppuccin: plan("haut", "galerie", 528, "carte", "vinyle", "coffee",
        "M21,40 H69 V60 Q69,77 45,77 Q21,77 21,60 Z M69,43 H78 Q91,43 86,54 Q82,61 69,63 M15,80 H80 M36,32 Q27,24 38,16 M49,32 Q41,23 51,12"),
    nord: plan("droite", "index", 586, "minimal", "portrait", "ac_unit",
        "M8,76 L37,17 L51,40 L61,31 L92,76 Z M25,42 L39,52 L51,40 M51,40 L67,65 L77,56 M37,17 L35,32 L48,48 M8,84 H92")
}

function pour(theme) { return Object.prototype.hasOwnProperty.call(plans, theme) ? plans[theme] : plans.noctalia }

function cadre(profil, largeurEcran, multi, reglages) {
    // Les pages conservent leur largeur utile si l'écran est trop étroit pour un rail latéral.
    const bord = largeurEcran < 470 && (profil.bord === "gauche" || profil.bord === "droite") ? "haut" : profil.bord
    const lateral = bord === "gauche" || bord === "droite"
    const rail = lateral && multi ? (profil.onglets === "icones" ? 48 : 102) : 0
    const bande = !lateral && multi ? (profil.onglets === "galerie" ? 50 : 36) : 0
    const pied = reglages ? 30 : 0
    return { bord, lateral, rail, bande, pied, haut: 36, bas: 16,
             largeur: Math.min(largeurEcran, profil.largeur + rail),
             surHauteur: 36 + 16 + bande + pied }
}

// Géométrie de l'accueil : [abscisse (fraction), ordonnée, largeur (fraction), alignement].
// L'horloge, le dessin et les données ambiantes changent de rôle, pas seulement de style.
const heros = {
    orbite:   { h: 116, heure: [.23, 19, .54, "centre"], art: [0, 4, .30, 95], etat: [.66, 80, .34, "droite"] },
    carte:    { h: 104, heure: [.06, 19, .56, "gauche"], art: [.65, 5, .29, 80], etat: [.62, 76, .32, "droite"] },
    minimal:  { h: 94, heure: [0, 7, .67, "gauche"], art: [.74, 0, .26, 82], etat: [0, 68, .65, "gauche"] },
    marge:    { h: 111, heure: [.33, 9, .67, "gauche"], art: [0, 0, .27, 102], etat: [.33, 76, .67, "gauche"] },
    dalle:    { h: 108, heure: [0, 13, .63, "gauche"], art: [.69, 0, .31, 79], etat: [0, 79, 1, "gauche"] },
    terminal: { h: 100, heure: [0, 4, .65, "gauche"], art: [.70, 0, .30, 74], etat: [0, 76, 1, "droite"] },
    jardin:   { h: 126, heure: [.04, 16, .58, "gauche"], art: [.61, 0, .39, 114], etat: [.04, 87, .57, "gauche"] },
    aube:     { h: 146, heure: [0, 53, 1, "centre"], art: [.37, 0, .26, 54], etat: [0, 116, 1, "centre"] },
    horizon:  { h: 120, heure: [.36, 7, .64, "droite"], art: [0, 0, .37, 112], etat: [.38, 83, .62, "droite"] }
}
function accueil(profil) { return heros[profil.accueil] }

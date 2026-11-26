.pragma library
.import "ScenesIle.js" as S

function avecPochette(planche, x, y, taille, rayon) {
    planche.cover = [x, y, taille, rayon];
    return planche;
}

function papier() {
    // Une fiche de discothèque glissée dans sa pochette kraft, avec onglets d’index.
    const papier = '#f5eedc', encre = '#382f28', tampon = '#8e4837';
    const fiche = S.box(0, 0, 480, 176, 0, '#bb9e73')
        + S.path('M9 122V11H267l6 -5h57l7 5h133v127Z', '#887455')
        + S.path('M8 119V8H265l6 -5h57l7 5h133v126Z', papier)
        + S.path('M17 33H340M17 84H340M348 15V122', null, '#c7b89c')
        + S.path('M23 12V119', null, '#c99c8d')
        + S.box(361, 12, 94, 94, 1, '#715a44')
        + S.path('M358 23V9h15m70 0h15v14m0 73v13h-15m-70 0h-15V96', null, tampon, 1.5)
        + S.path('M0 122H167q20 0 29 8h87q8 -8 25 -8h172v54H0Z', '#d6bb90', '#9b815e')
        + S.path('M7 128v41h466v-41', null, '#ae8e67')
        + S.repeat(8, i => S.box(365 + i * 11, 114, i % 3 === 0 ? 5 : 2, 5, 0, encre));
    return avecPochette(S.sheet('Discothèque · fiche de prêt', 'Record library · loan card', papier, encre, tampon, 'serif',
        [31, 12, 308, 12], [30, 39, 310, 30], [32, 89, 307, 16],
        [[19, 133, 123, 30], [158, 135, 164, 30], [337, 133, 124, 30]], 1, fiche), 365, 16, 86, 0);
}

function sakura() {
    // Le couvercle fleuri se soulève au-dessus du cylindre à picots et du peigne.
    const soie = '#fff2e5', prune = '#52323b', cuivre = '#955660';
    const fleur = (x, y) => S.repeat(5, i => S.dot(x + 3.4 * Math.cos(i * 1.257), y + 3.4 * Math.sin(i * 1.257), 3, '#e1a8a4'))
        + S.dot(x, y, 1.6, '#9f7354');
    const boite = S.box(7, 5, 466, 166, 16, '#c99391') + S.box(12, 9, 456, 112, 12, '#fff8ef')
        + S.box(20, 15, 102, 100, 9, '#d8aaa1') + S.box(24, 18, 94, 94, 7, '#fff2da')
        + S.path('M127 17q8 13 18 10t19 -11m-19 11l6 10M416 13q12 18 41 24m-20 -14l14 -3', null, '#997a69', 1.6)
        + fleur(156, 20) + fleur(148, 34) + fleur(433, 20) + fleur(454, 38)
        + S.path('M15 122H465', null, '#72454c', 2)
        + S.box(30, 119, 31, 6, 2, '#a77b59') + S.box(411, 119, 31, 6, 2, '#a77b59')
        + S.box(20, 132, 128, 30, 9, '#805755') + S.box(33, 138, 99, 18, 7, '#efcc96')
        + S.repeat(13, i => S.path('M' + (40 + i * 7) + ' 136v' + (8 + (i * 5) % 14), null, '#886947', 2))
        + S.path('M24 147h9m99 0h10', null, '#dfbe8b', 3);
    return avecPochette(S.sheet('Boîte à musique', 'Music box', soie, prune, cuivre, 'serif',
        [172, 19, 238, 13], [137, 43, 311, 30], [139, 85, 307, 15],
        [[158, 131, 65, 32], [231, 130, 142, 34], [381, 131, 76, 32]], 13, boite), 28, 22, 86, 5);
}

function kanagawa() {
    // Livre-disque relié à la japonaise. Les trois commandes occupent le rabat séparé.
    const ivoire = '#f1e6c9', sumi = '#283648', sceau = '#904e3c';
    const album = S.box(0, 0, 480, 176, 0, '#30445a') + S.box(13, 6, 356, 163, 1, ivoire)
        + S.path('M103 7v160m4 -160v160', null, '#ccbd99')
        + S.repeat(4, i => S.path('M8 ' + (25 + i * 40) + 'l13 -7v14z', null, '#dcc6a0', 1.8))
        + S.box(25, 24, 68, 68, 0, '#a49b82')
        + S.path('M24 109H92M24 114H69', null, '#a4997f')
        + S.path('M24 129h19v20H24Zm5 3v13m5 -13v13m-6 -7h10m0 -6v13', null, '#a05d45', 1.5)
        + S.path('M108 153q25 -3 44 -21q18 -19 32 -14q-13 1 -11 13q10 -7 14 -2q-17 7 -20 21q32 -7 48 -19q20 -16 39 -7q-17 -2 -19 12q21 -9 45 -5q42 7 89 -14v52H108Z', '#536b79')
        + S.path('M109 160q31 -4 54 -27m9 21q27 -5 47 -21m14 15q26 -10 53 -5t65 -8', null, ivoire, 1.5)
        + S.path('M376 8h95v160h-95Z', null, '#a0a69a');
    return avecPochette(S.sheet('Carnet d’estampes', 'Woodblock album', ivoire, sumi, sceau, 'serif',
        [117, 19, 239, 12], [115, 44, 243, 28], [118, 85, 238, 15],
        [[382, 15, 83, 35], [381, 58, 85, 59], [382, 125, 83, 35]], 1, album), 27, 26, 64, 0);
}

function roseAube() {
    // Le disque solaire se loge dans l’arche du cadran; le transport l’encadre.
    const nacre = '#fbe9dd', brun = '#593b43', or = '#965f60';
    const cadran = S.box(0, 0, 480, 176, 0, '#edc8b7')
        + S.path('M7 166V11h237q12 0 22 7v148Z', nacre)
        + S.path('M15 20h57m-57 5h31m202 130h-57m57 -5h-31', null, '#c59286')
        + S.path('M274 166v-46a96 96 0 0 1 192 0v46Z', '#e0a99c', '#97696c', 1.5)
        + S.path('M283 161v-39a87 87 0 0 1 174 0v39Z', nacre, '#b47c75')
        + S.repeat(19, i => S.ray(370, 116, 77, 185 + i * 9.5, i % 3 ? 4 : 9, '#b58076', 1.5))
        + S.dot(370, 91, 42, '#b27d75') + S.ring(370, 91, 45, '#d8a187', 1)
        + S.path('M21 138q34 -12 65 -5t69 0q40 -9 72 -3m-206 15q34 -10 65 -5t69 0', null, '#bb8d89', 1.2);
    return avecPochette(S.sheet('Sérénade à l’aube', 'Dawn serenade', nacre, brun, or, 'serif',
        [21, 34, 231, 13], [20, 59, 235, 28], [22, 99, 228, 15],
        [[280, 104, 40, 35], [324, 136, 92, 30], [421, 104, 40, 35]], 17, cadran), 331, 52, 78, 39);
}

function everforest() {
    // Enregistreur de terrain : clavier mécanique en haut, fiche et grilles micro en bas.
    const mousse = '#dbe0be', encre = '#2c4036', metal = '#587054';
    const appareil = S.box(0, 0, 480, 176, 0, '#647264') + S.box(5, 5, 470, 166, 8, '#33473c')
        + S.box(17, 12, 283, 44, 4, '#1d3029') + S.box(311, 14, 151, 38, 8, '#53685a')
        + S.repeat(13, i => S.path('M' + (328 + 10 * i) + ' 22v22', null, '#293e33', 3))
        + S.box(17, 66, 445, 94, 3, '#b6bd9e') + S.box(19, 68, 441, 90, 2, '#e8e5ce')
        + S.path('M109 73v80m7 -22h333', null, '#b9b89c')
        + S.path('M23 83V72h12m53 0h12v11m0 58v12H89m-53 0H23v-12', null, '#72836a', 1.5)
        + S.path('M429 86l5 -10 5 10h-3l5 6h-14l5 -6Z', metal)
        + S.path('M442 87l4 -7 4 7h-2l4 5h-12l4 -5Z', '#9ca281');
    return avecPochette(S.sheet('Phonothèque de terrain', 'Field sound archive', mousse, encre, metal, 'monospace',
        [118, 73, 302, 12], [116, 94, 334, 27], [119, 135, 329, 14],
        [[23, 17, 70, 33], [99, 16, 119, 35], [224, 17, 70, 33]], 3, appareil), 26, 77, 72, 1);
}

function catppuccin() {
    // Façade de juke-box de comptoir : arche chromée, fenêtre disque et sélecteurs en colonne.
    const creme = '#f9ece0', cafe = '#503f48', cerise = '#925a67';
    const facade = S.box(0, 0, 480, 176, 0, '#634a52') + S.box(6, 6, 468, 164, 15, '#d9b3ab')
        + S.path('M13 162V83a74 74 0 0 1 148 0v79Z', '#8f646b', '#f2d9be', 3)
        + S.path('M20 159V83a67 67 0 0 1 134 0v76Z', '#67535a', '#dab992', 2)
        + S.dot(87, 82, 56, '#443b48') + S.repeat(3, i => S.ring(87, 82, 44 + 4 * i, '#74646f', 1))
        + S.path('M28 145q58 13 117 0m-116 6q57 13 115 0', null, '#e3c9a8', 2)
        + S.box(165, 16, 240, 144, 12, '#8b6970') + S.box(169, 20, 232, 136, 10, creme)
        + S.path('M176 49h217m-216 65h215', null, '#d9b6ad')
        + S.repeat(5, i => S.box(187 + i * 42, 151, 27, 2, 1, '#cba49d'))
        + S.box(412, 15, 52, 147, 23, '#83616b');
    return avecPochette(S.sheet('Juke-box du café', 'Coffee bar jukebox', creme, cafe, cerise, 'sans-serif',
        [179, 28, 211, 13], [177, 63, 215, 27], [180, 120, 209, 15],
        [[417, 20, 42, 34], [415, 61, 46, 52], [417, 121, 42, 34]], 20, facade), 51, 46, 72, 36);
}

function penombre() {
    // Diapositive montée sur la bande d’une table de montage, entre les deux avances.
    const noir = '#332326', bougie = '#f2d6bd', cuivre = '#cf9682';
    const montage = S.box(0, 0, 480, 176, 0, noir)
        + S.box(0, 10, 480, 97, 0, '#201c22')
        + S.repeat(29, i => S.box(3 + i * 17, 13, 9, 4, 1, '#99776d') + S.box(3 + i * 17, 99, 9, 4, 1, '#99776d'))
        + S.box(15, 22, 289, 72, 1, '#4b3032')
        + S.box(311, 20, 80, 77, 2, '#c9a48a') + S.box(317, 25, 68, 67, 0, '#684942')
        + S.box(398, 22, 79, 72, 0, '#513333')
        + S.path('M404 76l17 -26 7 7 18 -24 -2 28 24 16 -33 -6 -14 10Z', '#a96e5c')
        + S.path('M421 50l14 21 11 -38 -18 24Z', '#dbad8e')
        + S.path('M0 115h480m-398 27h73m170 0h73', null, '#9d7065')
        + S.repeat(9, i => S.path('M' + (90 + i * 8) + ' 142v' + (i % 4 ? 4 : 8), null, '#a67b70')
            + S.path('M' + (326 + i * 8) + ' 142v' + (i % 4 ? 4 : 8), null, '#a67b70'));
    return avecPochette(S.sheet('Montage de nuit', 'Night editing room', noir, bougie, cuivre, 'monospace',
        [23, 24, 269, 10], [22, 40, 274, 24], [24, 73, 268, 13],
        [[15, 123, 64, 39], [159, 122, 162, 41], [401, 123, 64, 39]], 2, montage), 320, 28, 61, 0);
}

function pluieVerte() {
    // Hydrophone suspendu au-dessus des ondes ; le clavier de l’ampli est sur la tranche gauche.
    const eau = '#193832', vapeur = '#d9eadb', menthe = '#9dc5a8';
    const sonde = S.box(0, 0, 75, 176, 0, '#102a25') + S.path('M75 6v164m4 -164v164', null, '#567d6a')
        + S.path('M402 0v11q0 9 9 9h3q8 0 8 9v8', null, '#94ad93', 3)
        + S.box(413, 30, 18, 19, 3, '#7a9d8a') + S.dot(422, 76, 39, '#3a5b50')
        + S.ring(422, 76, 35, '#b0c4a4', 1.5)
        + S.path('M369 101q-15 8 -2 16t48 11m52 -24q13 10 -6 18m-100 -18q-27 10 -7 23t75 14m39 -16l12 -6', null, '#517f6c', 1.5)
        + S.path('M89 117h237', null, '#648572')
        + S.path('M90 147h28l4 -4 6 8 6 -15 6 21 7 -37 5 31 6 -12 5 7h13l5 -5 5 8 5 -5h22l6 -9 4 14 6 -25 5 31 5 -19 5 10 7 -4h54', null, '#9bc3a7', 1.6)
        + S.repeat(6, i => S.path('M' + (91 + i * 41) + ' 160v4', null, '#648572'));
    return avecPochette(S.sheet('Écoute sous la pluie', 'Rain listening post', eau, vapeur, menthe, 'monospace',
        [91, 15, 283, 12], [89, 44, 286, 28], [92, 90, 279, 15],
        [[12, 11, 49, 39], [10, 58, 53, 60], [12, 126, 49, 39]], 7, sonde), 393, 47, 58, 29);
}

const catalogue = {papier, sakura, kanagawa, 'rose-aube': roseAube, everforest, catppuccin, penombre, 'pluie-verte': pluieVerte};
function pour(nom) {
    return Object.prototype.hasOwnProperty.call(catalogue, nom) ? catalogue[nom]() : null;
}

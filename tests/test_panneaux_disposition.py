import shutil
import subprocess
import unittest
from pathlib import Path


class DispositionPanneaux(unittest.TestCase):
    def verifier(self, scenario):
        if not shutil.which("node"):
            self.skipTest("Node nécessaire pour exécuter le JS partagé avec QML")
        source = Path(__file__).resolve().parents[1] / "home/.config/quickshell/nc-ile/DispositionPanneaux.js"
        javascript = source.read_text(encoding="utf-8").split("\n", 1)[1]
        resultat = subprocess.run(["node", "-"], text=True, capture_output=True, input=javascript + scenario)
        self.assertEqual(resultat.returncode, 0, resultat.stderr)

    def test_ligne_unique_occultation_et_reserves(self):
        self.verifier("""
const assert = require('node:assert/strict');
const largeur = 1600, hauteur = 1000;
const barres = [
    {id:'haut', position:'top', margin_ends:16, margin_edge:6, thickness:40, widget_spacing:12,
     start:['logo','workspaces'], end:['sys','tray','vpn','garmin','status','date']},
    {id:'solide', position:'bottom', margin_edge:0, thickness:36, background_opacity:0.96, start:['logo'], end:['clock']},
    {id:'gauche', position:'left', margin_edge:10, thickness:52, center:['session']},
    {id:'droite', position:'right', margin_ends:'5%', margin_edge:0, thickness:48, reserve_space:false, start:['taches']},
];

// Les barres continues (background_opacity > 0) ne sont pas découpées en blocs flottants.
const b = blocs(barres);
assert.ok(b.every(x => x.barre.id !== 'solide'));

// Réserves d'écran par bord : barres flottantes ET continues, mais pas reserve_space:false.
const res = reserves(barres, 42);
assert.deepEqual(res, { top: 46, bottom: 36, left: 62, right: 0 });
assert.deepEqual(reserves([{id:'b', position:'top', margin_edge:6, thickness:34}], 42), { top: 42, bottom: 0, left: 0, right: 0 });
assert.deepEqual(reserves([{id:'b', position:'top', enabled:false}, barres[1]], 42), { top: 42, bottom: 36, left: 0, right: 0 });

const dimensions = b.map(({barre,cote}) => barre.position === 'top'
    ? {width:cote === 'end' ? 100 : 112, height:40} : {width:48, height:78});
const compacte = {x:680, y:4, width:240, height:43};
const ouverte = {x:450, y:4, width:700, height:470};

// Île compacte : toutes les pastilles tiennent sur UNE seule ligne (y === 6), sans recouvrement ni 2e rangée.
const repos = placer(b, dimensions, largeur, hauteur, compacte);
assert.ok(repos.every(r => !occulte(r, compacte)));
for (const [i, r] of repos.entries()) {
    if (b[i].barre.position === 'top') assert.equal(r.y, 6);
    assert.ok(!chevauche(r, compacte), `panneau ${i} touche l’île compacte`);
}

// Île ouverte (Spotlight) : seules les pastilles intérieures sont occultées.
for (const [i, r] of repos.entries()) {
    assert.ok(r);
    if (b[i].barre.position === 'top') assert.equal(r.y, 6, 'jamais de 2e rangée par-dessus les fenêtres');
    if (!occulte(r, ouverte)) {
        assert.ok(!chevauche(r, ouverte), `panneau visible ${i} sous l’île`);
    }
}
assert.ok(repos.some((r, i) => b[i].barre.position === 'top' && occulte(r, ouverte)));
assert.ok(repos.some((r, i) => b[i].barre.position === 'top' && !occulte(r, ouverte)));
assert.equal(repos.find((_, i) => b[i].barre.id === 'droite').x, largeur - 48);
assert.equal(repos.find((_, i) => b[i].barre.id === 'gauche').x, 10);
""")

    def test_spotlight_a_1280_masque_sans_decaler(self):
        self.verifier("""
const assert = require('node:assert/strict');
const barre = {id:'haut', position:'top', margin_ends:10, widget_spacing:12, end:['a','b','c','d','e','f']};
const b = blocs([barre]);
const tailles = b.map(() => ({width:80, height:34}));
const repos = {x:580, y:4, width:120, height:40};
const spotlight = {x:295, y:4, width:690, height:56};
const p = placer(b, tailles, 1280, 720, repos);
assert.deepEqual(p.map(r => r.x), [1190,1098,1006,914,822,730]);
assert.ok(p.every(r => !occulte(r, repos)));
assert.deepEqual(p.map(r => occulte(r, spotlight)), [false,false,false,true,true,true]);
""")

    def test_surcharge_ecran_fusionne_les_groupes(self):
        self.verifier("""
const assert = require('node:assert/strict');
const base = {id:'haut', position:'top', end:['group:sys','group:reseau'],
    capsule_group:[
        {id:'sys', members:['cpu','ram'], opacity:0.8},
        {id:'reseau', members:['wifi']},
    ],
    monitor:{externe:{match:'DELL', position:'bottom', end:['group:sys','group:reseau','group:media'],
        capsule_group:[{id:'sys', opacity:0.45}, {id:'media', members:['music']}]}}
};
const [externe] = barresPourEcran([base], 'DP-1', 'DELL U2724D');
assert.equal(externe.position, 'bottom');
assert.deepEqual(pastillesCote(externe, 'end').map(p => p.membres), [['cpu','ram'],['wifi'],['music']]);
assert.equal(pastillesCote(externe, 'end')[0].groupe.opacity, 0.45);
const [interne] = barresPourEcran([base], 'eDP-1', 'Interne');
assert.equal(interne.position, 'top');
assert.deepEqual(pastillesCote(interne, 'end').map(p => p.membres), [['cpu','ram'],['wifi']]);
assert.equal(pastillesCote(interne, 'end')[0].groupe.opacity, 0.8);
""")

    def test_barres_flottantes_et_placer_barre(self):
        self.verifier("""
const assert = require('node:assert/strict');
const barres = [
    {id:'haut', position:'top', margin_ends:16, margin_edge:6, thickness:40, widget_spacing:12},
    {id:'solide', position:'top', background_opacity:0.9, thickness:36},
    {id:'coupee', position:'bottom', enabled:false, thickness:34},
    {id:'gauche', position:'left', margin_edge:10, thickness:48, background_opacity:0},
];
assert.deepEqual(barresFlottantes(barres).map(b => b.id), ['haut', 'gauche']);

const compacte = {x:680, y:4, width:240, height:43};
const disp = placerBarre(
    barres[0],
    [{width:100, height:30}, null, {width:200, height:30}],
    [{width:80, height:30}, {width:60, height:30}],
    [{width:100, height:30}, {width:80, height:30}],
    1600, 1000, compacte
);

// Ligne unique centrée dans la bande [6..46] -> y === 11.
assert.equal(disp.start[1], null);
assert.equal(disp.start[0].x, 16);
assert.equal(disp.start[0].y, 11);
assert.equal(disp.start[0].margeMin, 12);
assert.equal(disp.start[2].x, 128);
assert.equal(disp.start[2].margeMin, 10);

// Center groupé et centré sans recouvrement.
assert.equal(disp.center[0].x + disp.center[0].width + 12, disp.center[1].x);
assert.equal(disp.center[0].margeMin, 0);
assert.equal(disp.center[0].margeMax, 0);

// End : index n-1 au bord droit, index 0 côté île, marges bornées sans collision.
assert.equal(disp.end[1].x, 1504);
assert.equal(disp.end[1].margeMax, 12);
assert.equal(disp.end[0].x, 1392);
assert.equal(disp.end[0].margeMax, 10);

// Vérifie que les glissements maximaux ne provoquent ni recouvrement ni sortie d'écran.
assert.ok(disp.start[0].x - disp.start[0].margeMin >= 0);
assert.ok(disp.start[2].x - disp.start[2].margeMin >= disp.start[0].x + disp.start[0].width + 2);
assert.ok(disp.end[0].x + disp.end[0].width + disp.end[0].margeMax <= disp.end[1].x - 2);
assert.ok(disp.end[1].x + disp.end[1].width + disp.end[1].margeMax <= 1600);
""")

    def test_reagir_pastille_glisser_titre_fondu_et_liberation_verticale(self):
        self.verifier("""
const assert = require('node:assert/strict');
const startRect = {x:128, y:11, width:120, height:30};
const endRect = {x:1352, y:11, width:120, height:30};
const centerRect = {x:740, y:11, width:120, height:30};

// Repos : aucun contact -> neutre.
const repos = {x:680, y:4, width:240, height:43};
assert.deepEqual(reagirPastille(startRect, 'start', 'top', 10, repos, 'glisser'), {dx:0, opacite:1, largeurClip:0});
assert.deepEqual(reagirPastille(endRect, 'end', 'top', 10, repos, 'glisser'), {dx:0, opacite:1, largeurClip:0});

// Barre non-top : jamais déplacée ni masquée.
assert.deepEqual(reagirPastille(startRect, 'start', 'bottom', 10, {x:0, y:0, width:1600, height:100}, 'glisser'),
                 {dx:0, opacite:1, largeurClip:0});

// Libération verticale (tiroir descendu sous la bande haute) -> retour immédiat au repos.
assert.deepEqual(reagirPastille(startRect, 'start', 'top', 10, {x:100, y:41, width:1400, height:500}, 'glisser'),
                 {dx:0, opacite:1, largeurClip:0});

// Glissement start borné par maxDecalage (10 px), puis fondu sur 32 px.
// startRect.x + width = 248 ; obsL = emprise.x - 8.
let r = reagirPastille(startRect, 'start', 'top', 10, {x:250, y:4, width:400, height:43}, 'glisser');
assert.deepEqual(r, {dx:-6, opacite:1, largeurClip:0});
r = reagirPastille(startRect, 'start', 'top', 10, {x:230, y:4, width:400, height:43}, 'glisser');
assert.equal(r.dx, -10);
assert.equal(r.largeurClip, 0);
assert.equal(r.opacite, 0.5);
r = reagirPastille(startRect, 'start', 'top', 10, {x:200, y:4, width:400, height:43}, 'glisser');
assert.equal(r.dx, -10);
assert.equal(r.opacite, 0);

// Glissement end borné par maxDecalage (10 px), puis fondu sur 32 px.
// endRect.x = 1352 ; obsR = emprise.x + width + 8.
r = reagirPastille(endRect, 'end', 'top', 10, {x:950, y:4, width:400, height:43}, 'glisser');
assert.deepEqual(r, {dx:6, opacite:1, largeurClip:0});
r = reagirPastille(endRect, 'end', 'top', 10, {x:970, y:4, width:400, height:43}, 'glisser');
assert.equal(r.dx, 10);
assert.equal(r.opacite, 0.5);

// Center ne glisse pas et fond linéairement.
r = reagirPastille(centerRect, 'center', 'top', 10, {x:852, y:4, width:100, height:43}, 'glisser');
assert.equal(r.dx, 0);
assert.equal(r.opacite, 0.5);

// Titre actif (start, estTitre: true, minLargeurTitre: 56) : repli GPU clip d'abord, puis glisse, puis fondu.
const titre = {x:128, y:11, width:156, height:30}; // 100 px réductibles (156 -> 56), droite = 284.
r = reagirPastille(titre, 'start', 'top', 10, {x:252, y:4, width:400, height:43}, 'glisser', 32, true, 56);
assert.deepEqual(r, {dx:0, opacite:1, largeurClip:116}); // pen = 284 - 244 = 40
r = reagirPastille(titre, 'start', 'top', 10, {x:186, y:4, width:400, height:43}, 'glisser', 32, true, 56);
assert.deepEqual(r, {dx:-6, opacite:1, largeurClip:56}); // pen = 106 -> coupe 100, glisse 6
r = reagirPastille(titre, 'start', 'top', 10, {x:166, y:4, width:400, height:43}, 'glisser', 32, true, 56);
assert.equal(r.largeurClip, 56);
assert.equal(r.dx, -10);
assert.equal(r.opacite, 0.5); // pen = 126 -> coupe 100, glisse 10, debord 16 -> 1 - 16/32

// Mode fondu : jamais de glissement ni de clip, opacité progressive.
r = reagirPastille(startRect, 'start', 'top', 10, {x:240, y:4, width:400, height:43}, 'fondu', 32, true, 56);
assert.deepEqual(r, {dx:0, opacite:0.5, largeurClip:0});

// Mode instantane : binaire strict 0 ou 1, zéro glissement.
assert.deepEqual(reagirPastille(startRect, 'start', 'top', 10, {x:255, y:4, width:400, height:43}, 'instantane'),
                 {dx:0, opacite:0, largeurClip:0});
assert.deepEqual(reagirPastille(startRect, 'start', 'top', 10, {x:256, y:4, width:400, height:43}, 'instantane'),
                 {dx:0, opacite:1, largeurClip:0});
""")

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

import shutil
import subprocess
import unittest
from pathlib import Path


class DispositionPanneaux(unittest.TestCase):
    @unittest.skipUnless(shutil.which("node"), "Node nécessaire pour exécuter le JS partagé avec QML")
    def test_ligne_unique_occultation_et_reserves(self):
        source = Path(__file__).resolve().parents[1] / "home/.config/quickshell/nc-ile/DispositionPanneaux.js"
        javascript = source.read_text(encoding="utf-8").split("\n", 1)[1]
        resultat = subprocess.run(["node", "-"], text=True, capture_output=True, input=javascript + """
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
assert.ok(repos.every(r => r && !r.occulte));
for (const [i, r] of repos.entries()) {
    if (b[i].barre.position === 'top') assert.equal(r.y, 6);
    assert.ok(!chevauche(r, compacte), `panneau ${i} touche l’île compacte`);
}

// Île ouverte (Spotlight) : aucune pastille ne descend sur une 2e rangée ; les intérieures sont occultées, les extérieures restent fixes.
const etendues = placer(b, dimensions, largeur, hauteur, ouverte);
for (const [i, r] of etendues.entries()) {
    assert.ok(r);
    if (b[i].barre.position === 'top') assert.equal(r.y, 6, 'jamais de 2e rangée par-dessus les fenêtres');
    if (!r.occulte) {
        assert.ok(!chevauche(r, ouverte), `panneau visible ${i} sous l’île`);
        assert.equal(r.x, repos[i].x, `panneau extérieur ${i} ne bouge pas à l’ouverture`);
    }
}
assert.ok(etendues.some((r, i) => b[i].barre.position === 'top' && r.occulte));
assert.ok(etendues.some((r, i) => b[i].barre.position === 'top' && !r.occulte));
assert.equal(etendues.find((_, i) => b[i].barre.id === 'droite').x, largeur - 48);
assert.equal(etendues.find((_, i) => b[i].barre.id === 'gauche').x, 10);
""")
        self.assertEqual(resultat.returncode, 0, resultat.stderr)

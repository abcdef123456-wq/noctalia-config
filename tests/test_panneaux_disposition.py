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

    def test_barres_adjacentes_arbitrage_en_coordonnees_ecran(self):
        self.verifier("""
const assert = require('node:assert/strict');
const barres = ['top', 'left'].map((position, i) => ({
    id: String(i), position, margin_edge: 6, margin_ends: 16, thickness: 34, reserve_space: false
}));
const tailles = [
    {start: [{width: 24, height: 34}]},
    {start: [{width: 34, height: 24}]},
];
const p = placerBarres(barres, tailles, 640, 360, {x: 260, y: 4, width: 120, height: 40});
assert.deepEqual(p.map(b => [b.start[0].x, b.start[0].y, b.start[0].occulteRepos]),
                 [[16, 6, false], [6, 16, true]]);
assert.equal(rectanglesPastilles(p[1].start, 'start', 'left', {}, 'glisser', 0, 0).length, 0);
// L'état occupé ne fuit jamais vers un autre écran ou un nouveau calcul.
assert.equal(placerBarres([barres[1]], [tailles[1]], 640, 360, {}).at(0).start[0].occulteRepos, false);
""")

    def test_rectangles_individuels_et_barre_sans_rendu(self):
        self.verifier("""
const assert = require('node:assert/strict');
const barre = {position: 'top', margin_edge: 6, margin_ends: 16, widget_spacing: 20, thickness: 40};
const obstacle = {x: 260, y: 4, width: 120, height: 40};
const p = placerBarre(barre, [{width: 15, height: 40}, {width: 15, height: 40}], [], [], 640, 360, obstacle);
const r = rectanglesPastilles(p.start, 'start', 'top', obstacle, 'glisser', 0, 0);
assert.deepEqual(r.map(r => [r.x, r.y, r.width, r.height]), [[16, 6, 15, 40], [51, 6, 15, 40]]);
assert.ok(!r.some(r => r.x <= 40 && 40 < r.x + r.width), 'le vide de 20 px doit laisser passer les clics');
const vide = placerBarre(barre, [null, {width: 0, height: 40}], [], [], 640, 360, obstacle);
assert.deepEqual(rectanglesPastilles(vide.start, 'start', 'top', obstacle, 'glisser', 0, 0), []);
assert.deepEqual(rectanglesPastilles(p.start, 'start', 'top',
    {x: 0, y: 0, width: 640, height: 100}, 'instantane', 0, 0), []);
""")

    @unittest.skipUnless(shutil.which("qs"), "Quickshell requis")
    def test_vrai_shell_disponibilite_et_regions_hors_ecran(self):
        import tempfile
        from tests.test_ile_demarrage import copie, sans_couche, environnement, lignes_en_erreur

        with tempfile.TemporaryDirectory(prefix="nc-pastilles-") as d:
            root = copie(d)
            for f in root.glob("*.qml"):
                texte = f.read_text()
                if f.name == "Panneaux.qml":
                    f.write_text(texte.replace("id: ecranPanneaux", "id: ecranPanneaux; property alias flottantesTest: flottantes"))
                if f.name == "BarreFlottante.qml":
                    # Conserver et instancier le VRAI Region, même sans backend layer-shell.
                    texte = texte.replace("mask: Region", "property Region masqueTeste: Region")
                if "PanelWindow {" in texte:
                    f.write_text(sans_couche(texte))
            shell = root / "shell.qml"
            texte = shell.read_text().replace('target: "ile"', 'id: ipcTeste; target: "ile"')
            texte = texte.replace("id: ile", "id: ile; property alias panneauxTest: panneaux", 1)
            scenario = """
    Timer {
        interval: 500; running: true; repeat: true
        property int etape: 0
        property int signaux: 0   // « changed » du masque : ce que la fenêtre Quickshell écoute pour poser la zone d'entrée
        function verifier(ok, message) { if (!ok) { console.error("ECHEC: " + message); Qt.exit(2) } }
        function barres() {
            const rep = ecransIle.instances[0].panneauxTest.flottantesTest;
            const resultat = [];
            for (let i = 0; i < rep.count; ++i) resultat.push(rep.objectAt(i));
            return resultat;
        }
        onTriggered: {
            if (etape === 0) {
                Reglages.valeurs = { BARRE_MODULAIRE: "oui" }
                racine.modelePanneaux = { generation: "test", barres: [
                    {id: "vide", position: "top", start: ["inconnu"], reserve_space: false}
                ] }
            } else if (etape === 1) {
                verifier(barres().length === 1, "la sonde de mesure existe");
                verifier(barres()[0].nombrePastillesRendues === 0 && !barres()[0].visible,
                         "aucune fenêtre visible pour un widget non pris en charge");
                verifier(ipcTeste.panneauxPrets("test") === "", "ne pas acquitter une barre vide");
                racine.modelePanneaux = { generation: "test", widgets: {
                    a: {type: "text", text: "A"}, b: {type: "text", text: "B"}
                }, barres: [
                    {id: "haut", position: "top", margin_edge: 6, margin_ends: 16,
                     widget_spacing: 20, start: ["a", "b"], reserve_space: false}
                ] }
            } else if (etape === 2) {
                const w = barres()[0];
                verifier(w.visible && w.nombrePastillesRendues === 2, "deux pastilles rendues");
                verifier(ipcTeste.panneauxPrets("test") === "test", "acquitter le rendu courant");
                verifier(ipcTeste.panneauxPrets("autre") === "", "refuser une génération périmée");
                const regions = w.masqueTeste.regions;
                verifier(regions.length === 2, "une Region par pastille");
                verifier(regions[1].x - (regions[0].x + regions[0].width) === 20,
                         "le masque ne couvre pas le vide entre les pastilles");
                w.empriseLive = Qt.rect(0, 0, 2000, 2000);
            } else if (etape === 3) {
                const w = barres()[0];
                verifier(w.masqueTeste.regions.length === 2 && w.visible,
                         "aucune reconfiguration de masque ou mapping pendant le ressort");
                w.masqueTeste.changed.connect(() => signaux++);
                // Nouvel objet : les pastilles (emprise vive) relisent le mode comme le masque (emprise stable).
                w.mouv = Object.assign({}, w.mouv, { reactionBarre: "instantane" });
                w.empriseStable = Qt.rect(0, 0, 2000, 2000);
            } else if (etape === 4) {
                const w = barres()[0], panneaux = ecransIle.instances[0].panneauxTest;
                verifier(w.visible && w.nombrePastillesRendues === 0,
                         "une barre occultée par l'île garde son calque, sans pastille rendue");
                verifier(w.masqueTeste.regions.length === 0, "aucune zone cliquable sous l'île");
                verifier(signaux > 0, "le masque vidé est signalé à la fenêtre");
                signaux = 0;
                verifier(!panneaux.aPastilleRendue(w.contentItem), "pastilles masquées pendant l'occultation");
                verifier(ipcTeste.panneauxPrets("test") === "", "ne pas acquitter un écran sans pastille");
                w.empriseLive = Qt.rect(0, 0, 0, 0);
            } else if (etape === 5) {
                const w = barres()[0], panneaux = ecransIle.instances[0].panneauxTest;
                verifier(w.visible && panneaux.aPastilleRendue(w.contentItem),
                         "les pastilles reviennent pendant le ressort de fermeture");
                verifier(w.masqueTeste.regions.length === 0, "masque inchangé tant que l'emprise n'est pas stable");
                w.empriseStable = Qt.rect(0, 0, 0, 0);
            } else if (etape === 6) {
                const w = barres()[0];
                verifier(w.visible && w.nombrePastillesRendues === 2 && w.masqueTeste.regions.length === 2,
                         "retour complet après occultation");
                verifier(signaux > 0, "le masque rendu est signalé à la fenêtre");
                verifier(ipcTeste.panneauxPrets("test") === "test", "acquitter de nouveau au repos");
                racine.modelePanneaux = { generation: "test", widgets: { a: {type: "text", text: "A"} },
                    barres: ["top", "left"].map((position, i) => ({
                        id: String(i), position, margin_edge: 6, margin_ends: 16, thickness: 34,
                        start: ["a"], reserve_space: false
                    })) };
            } else if (etape === 7) {
                verifier(barres()[0].visible && !barres()[1].visible,
                         "seule la première barre adjacente est mappée");
                verifier(barres()[1].dispositionRepos.start[0].occulteRepos,
                         "arbitrage partagé par les vraies instances QML");
                racine.modelePanneaux = { generation: "test", barres: [
                    {id: "continue", position: "bottom", background_opacity: 1, start: ["inconnu"]}
                ] };
            } else if (etape === 8) {
                verifier(ipcTeste.panneauxPrets("test") === "", "un fond continu seul ne suffit pas");
                racine.modelePanneaux = { generation: "test", widgets: { a: {type: "text", text: "A"} },
                    barres: [{id: "continue", position: "bottom", background_opacity: 1, start: ["a"]}] };
            } else {
                verifier(ipcTeste.panneauxPrets("test") === "test", "une pastille continue suffit");
                console.log("PASTILLES_OK"); Qt.quit();
            }
            etape++;
        }
    }
"""
            shell.write_text(texte[:texte.rfind("}")] + scenario + "}\n")
            env = environnement(root)
            try:
                resultat = subprocess.run(["qs", "--no-color", "-p", str(shell)], env=env, text=True,
                                          capture_output=True, timeout=15, stdin=subprocess.DEVNULL)
            except subprocess.TimeoutExpired as erreur:
                self.fail(str(erreur.stdout) + str(erreur.stderr))
            sortie = resultat.stdout + resultat.stderr
            self.assertEqual(resultat.returncode, 0, sortie)
            self.assertEqual(lignes_en_erreur(sortie), [], sortie)
            self.assertNotIn("ECHEC", sortie, sortie)
            self.assertIn("PASTILLES_OK", sortie, sortie)

    @unittest.skipUnless(shutil.which("qs") and shutil.which("sway"),
                         "Quickshell et sway requis (compositeur sans écran qui connaît layer-shell)")
    def test_zone_d_entree_wayland_videe_sous_l_ile_puis_rendue(self):
        """Côté Wayland (WAYLAND_DEBUG), le calque de la barre pose : deux pastilles, puis aucune zone quand Spotlight
        les couvre, puis les deux mêmes au retour. Le vrai shell.qml, 1280×720 à l'échelle 2."""
        import re
        import tempfile
        import time
        from tests.test_ile_demarrage import copie, environnement

        with tempfile.TemporaryDirectory(prefix="nc-masque-") as d:
            root = copie(d)
            panneaux = root / "Panneaux.qml"
            panneaux.write_text(panneaux.read_text().replace(
                "id: ecranPanneaux", "id: ecranPanneaux; property alias flottantesTest: flottantes"))
            shell = root / "shell.qml"
            texte = shell.read_text().replace('target: "ile"', 'id: ipcTeste; target: "ile"')
            texte = texte.replace("id: ile", "id: ile; property alias panneauxTest: panneaux", 1)
            scenario = """
    Timer {
        interval: 100; running: true; repeat: true
        property int phase: 0
        property int tenu: 0
        property int tours: 0
        function rendues() {
            const rep = ecransIle.instances[0].panneauxTest.flottantesTest;
            return rep.count ? rep.objectAt(0).nombrePastillesRendues : -1;
        }
        // Trois tours de suite dans l'état attendu : la zone d'entrée a eu le temps de partir.
        function atteint(n) { tenu = rendues() === n ? tenu + 1 : 0; if (tenu < 3) return false; tenu = 0; return true }
        onTriggered: {
            if (++tours > 150) { console.error("ECHEC: phase " + phase + " jamais atteinte"); Qt.exit(2) }
            if (phase === 0) {
                Reglages.valeurs = { BARRE_MODULAIRE: "oui" };
                racine.modelePanneaux = { generation: "test", widgets: {
                    a: {type: "text", text: "A"}, b: {type: "text", text: "B"}
                }, barres: [
                    {id: "revue", position: "top", margin_edge: 6, margin_ends: 16, thickness: 40,
                     widget_spacing: 20, start: ["a", "b"], reserve_space: false}
                ] };
                phase = 1;
            } else if (phase === 1 && atteint(2)) { ipcTeste.recherche(); phase = 2 }
            else if (phase === 2 && atteint(0)) { Etat.fermer(); phase = 3 }
            else if (phase === 3 && atteint(2)) Qt.quit()
        }
    }
"""
            shell.write_text(texte[:texte.rfind("}")] + scenario + "}\n")
            env = environnement(root, WLR_BACKENDS="headless", WLR_LIBINPUT_NO_DEVICES="1", WLR_RENDERER="pixman")
            for cle in ("QT_QPA_PLATFORM", "WAYLAND_DISPLAY", "HYPRLAND_INSTANCE_SIGNATURE", "DISPLAY"):
                env.pop(cle, None)
            conf = root / "sway.conf"
            conf.write_text("output HEADLESS-1 resolution 1280x720 scale 2\n")
            sway = subprocess.Popen(["sway", "-c", str(conf)], env=env, stdin=subprocess.DEVNULL,
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            try:
                prises = []
                for _ in range(100):
                    prises = [p.name for p in Path(env["XDG_RUNTIME_DIR"]).glob("wayland-*") if not p.name.endswith(".lock")]
                    if prises or sway.poll() is not None:
                        break
                    time.sleep(0.1)
                self.assertTrue(prises, "sway sans écran n'a pas démarré")
                resultat = subprocess.run(
                    ["qs", "--no-color", "-p", str(shell)], text=True, timeout=40, stdin=subprocess.DEVNULL,
                    env=dict(env, WAYLAND_DISPLAY=prises[0], WAYLAND_DEBUG="1", QT_QPA_PLATFORM="wayland"),
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            finally:
                sway.terminate()
                try:
                    sway.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    sway.kill()
            sortie = resultat.stdout
            self.assertEqual(resultat.returncode, 0, sortie[-3000:])
            calque = re.search(r'get_layer_surface\(new id zwlr_layer_surface_v1#\d+, wl_surface#(\d+),[^\n]*"nc-panneau-revue"\)',
                               sortie)
            self.assertIsNotNone(calque, sortie[-3000:])
            regions, zones = {}, []
            for ligne in sortie.splitlines():
                creee = re.search(r"create_region\(new id wl_region#(\d+)\)", ligne)
                if creee:
                    regions[creee.group(1)] = []            # les identifiants Wayland sont réutilisés
                ajout = re.search(r"wl_region#(\d+)\.add\(([-\d, ]+)\)", ligne)
                if ajout:
                    regions[ajout.group(1)].append(ajout.group(2))
                # « nil » (toute la surface) n'est qu'un état d'attente avant la vraie zone du même commit : ignoré ici
                pose = re.search(r"wl_surface#%s\.set_input_region\(wl_region#(\d+)\)" % calque.group(1), ligne)
                if pose:
                    zones.append(regions.get(pose.group(1), []))
            self.assertTrue(zones and len(zones[0]) == 2, zones)
            self.assertIn([], zones[1:-1], "aucune zone vide envoyée pendant que Spotlight couvre les pastilles : %r" % zones)
            self.assertEqual(zones[-1], zones[0], zones)
            self.assertEqual(len(re.findall(r'"nc-panneau-revue"', sortie)), 1, "le calque ne doit pas être recréé")

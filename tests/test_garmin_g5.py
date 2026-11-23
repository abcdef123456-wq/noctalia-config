"""Lot G5 : tableau Garmin riche (jauges, courbes, sommeil en phases, distance).
1. Connecteur (sous-processus, faux module garminconnect, HOME/XDG isolés) : sans nouveau champ, à moitié, types faux, complet.
2. Tableau sur le vrai qs hors écran : vide, partiel, complet ; masqué pendant le partage ; courbes non repeintes panneau fermé.
Sauté si Quickshell manque. NC_G5_CONNECTEUR / NC_G5_QML permettent de viser une autre copie (mutation, ancien code)."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests import _ile_hors_ecran as H
from tests.test_garmin_qml import DEMO, FAUX, textwrap_corps

REPO = Path(__file__).resolve().parents[1]
CONNECTEUR = Path(os.environ.get("NC_G5_CONNECTEUR", REPO / "home/.local/libexec/nc-garmin-connecteur.py"))
QML = Path(os.environ.get("NC_G5_QML", REPO / "home/.config/quickshell/nc-ile"))

FAUX_MODULE = '''import json, os
class Garmin:
    def login(self, tokenstore=None): pass
    def __getattr__(self, nom):
        if not nom.startswith("get_"): raise AttributeError(nom)
        d = json.load(open(os.environ["NC_FAUX_DONNEES"]))
        return lambda *a, **k: d.get(nom, {})
'''


def paires(valeurs):
    return [[1000 * i, v] for i, v in enumerate(valeurs)]


COMPLET = {
    "get_body_battery": [{"bodyBatteryValuesArray": paires([30, 45, 62, 80])}],
    "get_heart_rates": {"restingHeartRate": 55, "maxHeartRate": 150, "heartRateValues": paires([60, 70, 90, 80])},
    "get_sleep_data": {"dailySleepDTO": {"sleepTimeSeconds": 27000, "sleepScores": {"overall": {"value": 80}},
                                         "deepSleepSeconds": 5000, "lightSleepSeconds": 15000, "remSleepSeconds": 6000, "awakeSleepSeconds": 1000}},
    "get_stress_data": {"avgStressLevel": 30, "stressValuesArray": paires([20, 30, -1, 40])},
    "get_stats": {"totalSteps": 6000, "totalDistanceMeters": 5000.0},
}
ANCIEN = {"get_body_battery": [{"bodyBatteryValuesArray": [[0, 70]]}], "get_heart_rates": {"restingHeartRate": 55},
          "get_sleep_data": {"dailySleepDTO": {"sleepTimeSeconds": 27000}}, "get_stats": {"totalSteps": 6000}}
MOITIE = {"get_body_battery": [{"bodyBatteryValuesArray": paires([30, 45])}], "get_heart_rates": {"heartRateValues": [[0, 60]]},
          "get_sleep_data": {"dailySleepDTO": {"deepSleepSeconds": 5000}}, "get_stress_data": {"avgStressLevel": 30}}
FAUX_TYPES = {"get_body_battery": [{"bodyBatteryValuesArray": "abc"}],
              "get_heart_rates": {"heartRateValues": paires([float("nan")] * 5) + [None, "x", [1], 7], "restingHeartRate": "55"},
              "get_sleep_data": {"dailySleepDTO": {"deepSleepSeconds": "5", "lightSleepSeconds": float("inf"), "remSleepSeconds": True,
                                                   "awakeSleepSeconds": [1]}},
              "get_stress_data": {"avgStressLevel": float("nan"), "stressValuesArray": 5},
              "get_stats": {"totalDistanceMeters": "5000"}}
ENORME = {"get_heart_rates": {"heartRateValues": paires(list(range(100000)))}, "get_stress_data": {"stressValuesArray": paires([5] * 100000)}}


class Connecteur(unittest.TestCase):
    def lancer(self, donnees):
        with tempfile.TemporaryDirectory(prefix="nc-g5-") as d:
            d = Path(d)
            (d / "mod").mkdir()
            (d / "mod/garminconnect.py").write_text(FAUX_MODULE)
            (d / "donnees.json").write_text(json.dumps(donnees))  # NaN accepté en écriture : le faux module le relit
            env = {"PATH": os.environ.get("PATH", ""), "HOME": str(d), "XDG_CONFIG_HOME": str(d), "XDG_DATA_HOME": str(d),
                   "XDG_CACHE_HOME": str(d), "XDG_STATE_HOME": str(d), "XDG_RUNTIME_DIR": str(d), "TMPDIR": str(d),
                   "PYTHONPATH": str(d / "mod"), "NC_FAUX_DONNEES": str(d / "donnees.json")}
            r = subprocess.run([sys.executable, str(CONNECTEUR), str(d / "jetons"), "2026-01-02"], env=env, capture_output=True,
                               text=True, timeout=60, cwd=str(d))
            self.assertEqual(r.returncode, 0, r.stderr)

            def refus(c):
                raise ValueError("constante non finie " + c)
            sortie = json.loads(r.stdout, parse_constant=refus)
            self.assertIn("metriques", sortie)
            m = sortie["metriques"]
            for cle in ("bb_serie", "fc_serie", "stress_serie"):
                v = m.get(cle)
                self.assertTrue(v is None or (isinstance(v, list) and 2 <= len(v) <= 300 and all(isinstance(x, (int, float)) for x in v)), (cle, v))
            return m

    def test_sans_nouveau_champ(self):
        m = self.lancer(ANCIEN)
        self.assertEqual(m["body_battery"], 70)
        self.assertEqual(m["pas"], 6000)
        for cle in ("distance_m", "bb_serie", "fc_serie", "stress_serie", "stress_moyen", "sommeil_profond_s"):
            self.assertIsNone(m.get(cle), cle)

    def test_a_moitie(self):
        m = self.lancer(MOITIE)
        self.assertEqual(m["bb_serie"], [30, 45])
        self.assertIsNone(m.get("fc_serie"))
        self.assertEqual(m["sommeil_profond_s"], 5000)
        self.assertIsNone(m.get("sommeil_leger_s"))
        self.assertEqual(m["stress_moyen"], 30)

    def test_types_faux(self):
        m = self.lancer(FAUX_TYPES)
        self.assertIsNone(m.get("bb_serie"))
        self.assertIsNone(m.get("fc_serie"))
        self.assertIsNone(m.get("distance_m"))
        self.assertIsNone(m.get("stress_moyen"))
        for cle in ("sommeil_profond_s", "sommeil_leger_s", "sommeil_paradoxal_s", "sommeil_eveil_s"):
            self.assertIsNone(m.get(cle), cle)

    def test_liste_enorme(self):
        m = self.lancer(ENORME)
        self.assertLessEqual(len(m["fc_serie"]), 300)
        self.assertLessEqual(len(m["stress_serie"]), 300)

    def test_complet(self):
        m = self.lancer(COMPLET)
        self.assertEqual(m["distance_m"], 5000.0)
        self.assertEqual(m["bb_serie"], [30, 45, 62, 80])
        self.assertEqual(m["stress_serie"], [20, 30, 40])
        self.assertEqual([m["sommeil_profond_s"], m["sommeil_leger_s"], m["sommeil_paradoxal_s"], m["sommeil_eveil_s"]],
                         [5000, 15000, 6000, 1000])


@unittest.skipUnless(shutil.which("qs"), "Quickshell requis")
class Tableau(unittest.TestCase):
    def lancer(self, corps, metriques, widgets=None, largeur=846):
        if widgets is None:
            widgets = ["body_battery", "frequence_cardiaque", "sommeil", "stress", "pas"]
        etat = dict(DEMO, metriques=metriques, widgets_actifs=widgets)
        with tempfile.TemporaryDirectory(prefix="nc-garmin-g5-") as d:
            lire = lambda n: (QML / n).read_text()
            composants = ("GarminTableau", "GarminCarte", "GarminBouton", "GarminSommeil", "GarminCourbe", "GarminJauge", "GarminEtat")
            root = H.preparer(d, ("Couleurs", "Texte", "Ico"), extra={
                **{n + ".qml": lire(n + ".qml") for n in composants},
                "Partage.qml": "pragma Singleton\nimport QtQuick\nQtObject { property bool silence: false }\n"},
                singletons=("GarminEtat", "Partage"))
            (root / "etat.json").write_text(json.dumps(etat))
            bin_ = root / "home/.local/bin"
            bin_.mkdir(parents=True)
            (bin_ / "nc-garmin").write_text(FAUX.replace("@ROOT@", str(root)))
            (bin_ / "nc-garmin").chmod(0o755)
            (root / "shell.qml").write_text(H.ENTETE + "ShellRoot {\n property int etape: 0\n property int ticks: 0\n property var fige: []\n"
                                            + f" property int largeur: {largeur}\n" + H.OUTILS + '''
                Window { id: w; visible: true; width: largeur; height: 780
                    Item { id: cadre; anchors.fill: parent; GarminTableau { id: tab; width: parent.width; objectName: "nc-garmin-tableau" } } }
                function vus() { var l = []; var noms = ["nc-garmin-jauges", "nc-garmin-courbe-bb", "nc-garmin-courbe-fc", "nc-garmin-courbe-stress", "nc-garmin-sommeil", "nc-garmin-distance"]
                    for (var i = 0; i < noms.length; i++) { var o = trouver(cadre, noms[i]); if (o && o.visible && tab.visible) l.push(noms[i]) } return l }
                function jauge(n) { return trouver(cadre, "nc-garmin-jauge-" + n) }
                function carte(n) { return trouver(cadre, "nc-garmin-carte-" + n) }
                function droite(n) {
                    var v = trouver(cadre, "nc-garmin-valeur-" + n)
                    return v.mapToItem(cadre, v.width, 0).x
                }
                ''' + textwrap_corps(corps)
                                            + "\n Timer { interval: 15000; running: true; onTriggered: { console.error(\"ECHEC délai\"); Qt.exit(3) } }\n}\n")
            code, sortie = H.lancer(root, delai=40)
            for e in H.ERREURS:
                self.assertNotIn(e, sortie, sortie)
            self.assertIn("FINI", sortie, sortie)

    ATTENTE = '''
        Timer { interval: 60; running: true; repeat: true; onTriggered: {
            if (etape === 0) { GarminEtat.panneauOuvert = true; etape++; return }
            if (!GarminEtat.lu) return
            ticks++
            if (ticks < 6) return
            %s
            console.log("FINI"); Qt.exit(0)
        } }
    '''

    def test_vide(self):
        self.lancer(self.ATTENTE % '''
            verifier(vus().length === 0, "pas de jauge, courbe ou phase visible sans mesure : " + vus())
            verifier(carte("body_battery").valeur === "—", "carte sans donnée")
        ''', {})

    def test_partiel(self):
        self.lancer(self.ATTENTE % '''
            var v = vus()
            verifier(v.indexOf("nc-garmin-jauges") >= 0, "jauges visibles")
            verifier(jauge("bb").texte === "70 %" && jauge("fc").texte === "—" && jauge("stress").texte === "—", "jauges : " + jauge("bb").texte + jauge("fc").texte)
            verifier(v.indexOf("nc-garmin-courbe-bb") >= 0 && v.indexOf("nc-garmin-courbe-fc") < 0, "courbes : " + v)
            verifier(v.indexOf("nc-garmin-sommeil") < 0, "barre de sommeil cachée sans phases")
        ''', {"body_battery": 70, "bb_serie": [30, 45, 70], "fc_serie": [60]})

    def test_complet(self):
        self.lancer(self.ATTENTE % '''
            var v = vus()
            verifier(v.length === 6, "tout visible : " + v)
            verifier(jauge("sommeil").texte === "80/100" && jauge("pas").texte === "6000", "jauges")
            verifier(jauge("fc").texte === "80 bpm" && carte("frequence_cardiaque").valeur === "80 bpm", "dernière mesure cardiaque dans les deux vues")
            verifier(jauge("pas").valeur === 0.75, "fraction de l'objectif réel")
            verifier(trouver(cadre, "nc-garmin-distance").text === "5.00 km", "distance en km")
            var cles = ["body_battery", "frequence_cardiaque", "sommeil", "stress", "pas"]
            var noms = ["bb", "fc", "sommeil", "stress", "pas"]
            for (var i = 0; i < cles.length; i++) {
                var j = jauge(noms[i]), c = carte(cles[i])
                verifier(j.couleur === c.couleur && Math.abs(droite(cles[i]) - droite(cles[0])) < 1, "teinte et alignement " + cles[i])
                verifier(j.parent.y === jauge("bb").parent.y && (!i || j.parent.x > jauge(noms[i - 1]).parent.x), "ordre sur une même rangée")
                verifier(c.width === tab.width && (!i || c.y > carte(cles[i - 1]).y), "ordre des cartes pleine largeur")
            }
            var b = trouver(cadre, "nc-garmin-sommeil-barre"), total = b.spacing * 3
            for (var k = 0; k < 4; k++) {
                var segment = trouver(cadre, "nc-garmin-sommeil-" + k)
                verifier(segment.visible && segment.width > 0, "phase représentée " + k)
                total += segment.width
            }
            verifier(Math.abs(total - b.width) < 1, "la barre tient exactement dans la carte")
        ''', {"body_battery": 70, "fc_repos": 55, "sommeil_score": 80, "stress_moyen": 30, "pas": 6000, "pas_objectif": 8000, "distance_m": 5000,
              "bb_serie": [30, 45, 70], "fc_serie": [60, 70, 80], "stress_serie": [20, 30, 25],
              "sommeil_profond_s": 5000, "sommeil_leger_s": 15000, "sommeil_paradoxal_s": 6000, "sommeil_eveil_s": 1000})

    def test_ordre_personnalise_et_fenetre_etroite(self):
        self.lancer(self.ATTENTE % '''
            var pas = jauge("pas"), coeur = jauge("fc"), bb = jauge("bb")
            var rang = trouver(cadre, "nc-garmin-jauges")
            verifier(pas.parent.x < coeur.parent.x && coeur.parent.x < bb.parent.x, "ordre personnalisé des jauges")
            verifier(rang.width === 368 && bb.parent.x + bb.parent.width <= rang.width && bb.parent.y === pas.parent.y, "jauges visibles sur une rangée étroite")
            verifier(carte("pas").y < carte("hydratation").y && carte("hydratation").y < carte("frequence_cardiaque").y, "ordre personnalisé des cartes")
            verifier(!jauge("stress") && !carte("stress"), "indicateur désactivé absent des deux vues")
            verifier(coeur.texte === "55 bpm", "fréquence au repos sans série")
        ''', {"pas": 6000, "fc_repos": 55}, widgets=["pas", "hydratation", "frequence_cardiaque", "body_battery"], largeur=368)

    def test_partage_cache_tout(self):
        self.lancer(self.ATTENTE % '''
            verifier(vus().length === 6, "visible hors partage")
            Partage.silence = true
            verifier(vus().length === 0 && !tab.visible, "rien de visible pendant le partage : " + vus())
            Partage.silence = false
        ''', {"body_battery": 70, "bb_serie": [30, 45, 70], "fc_serie": [60, 70, 80], "stress_serie": [20, 30, 25], "distance_m": 5000,
              "sommeil_profond_s": 5000, "sommeil_leger_s": 15000, "sommeil_paradoxal_s": 6000, "sommeil_eveil_s": 1000})

    def test_panneau_ferme_pas_de_peinture(self):
        self.lancer('''
            Timer { interval: 60; running: true; repeat: true; onTriggered: {
                if (etape === 0) { GarminEtat.panneauOuvert = true; etape++; return }
                if (etape === 1) { if (!GarminEtat.lu) return
                    ticks++; if (ticks < 6) return
                    GarminEtat.panneauOuvert = false; ticks = 0; etape++; return }
                if (etape === 2) { ticks++; if (ticks < 4) return
                    var c = trouver(cadre, "nc-garmin-courbe-bb"); var j = jauge("bb")
                    verifier(c && j, "composants présents")
                    verifier(c.peintures > 0, "la courbe a bien été peinte une fois ouverte")
                    fige = [c.peintures, j.peintures, c.demandes, j.demandes]
                    // de nouvelles mesures arrivent panneau fermé : aucune demande de peinture
                    c.points = [10, 20, 30, 40]; c.couleur = "#ff0000"; j.valeur = 33
                    etape++; ticks = 0; return }
                if (etape === 3) { ticks++; if (ticks < 6) return
                    var c2 = trouver(cadre, "nc-garmin-courbe-bb"); var j2 = jauge("bb")
                    verifier(c2.demandes === fige[2] && j2.demandes === fige[3], "demandes panneau fermé : " + c2.demandes + "/" + fige[2] + " " + j2.demandes + "/" + fige[3])
                    verifier(c2.peintures === fige[0] && j2.peintures === fige[1], "repeint panneau fermé : " + c2.peintures + "/" + fige[0])
                    console.log("FINI"); Qt.exit(0) }
            } }
        '''.replace("Window { id: w;", "Window { id: w;"), {"body_battery": 70, "bb_serie": [30, 45, 70], "fc_serie": [60, 70, 80]})


if __name__ == "__main__":
    unittest.main()

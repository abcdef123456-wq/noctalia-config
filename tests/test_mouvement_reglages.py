"""Moteur de mouvement (Mouvement.qml, Couleurs.qml, Etincelle.qml) et réglages nc-reglages :
ILE_ANIM_VITESSE, ILE_ANIM_BATTERIE (douces/aucune/continues), ILE_ANIM_ECRANS, BARRE_REACTION, BARRE_CONTENU."""
import json
import os
import re
import runpy
import shutil
import tempfile
import unittest
import warnings
from pathlib import Path
from unittest.mock import patch

from tests import _ile_hors_ecran as H

REPO = H.REPO
QML = H.QML

REGLAGES_TEST = """pragma Singleton
import QtQuick
QtObject {
    property var valeurs: ({})
    property var style: ({})
    property var faux: []
    property bool sobre: false
    property bool batterie: false
    readonly property bool en: false
    readonly property bool iaCoupee: true
    function t(fr, en) { return fr }
    function val(k, d) {
        if (valeurs[k] !== undefined && valeurs[k] !== "") return valeurs[k]
        if (style[k] !== undefined && style[k] !== "") return style[k]
        return d
    }
}
"""

PARTAGE_TEST = """pragma Singleton
import QtQuick
QtObject {
    property bool silence: false
    property bool indicateur: false
    property int sessions: 0
}
"""


def charger_nc_reglages(home, avec_ile=False):
    xdg = Path(home) / ".config"
    if avec_ile:
        p = xdg / "quickshell/nc-ile/shell.qml"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("", encoding="utf-8")
    env = {"HOME": str(home), "XDG_CONFIG_HOME": str(xdg)}
    with patch.dict(os.environ, env), warnings.catch_warnings():
        warnings.simplefilter("ignore", ResourceWarning)
        return runpy.run_path(str(REPO / "home/.local/bin/nc-reglages"))


class ReglagesMouvement(unittest.TestCase):
    CLES = ("ILE_ANIM_VITESSE", "ILE_ANIM_BATTERIE", "ILE_ANIM_ECRANS", "BARRE_REACTION", "BARRE_CONTENU")

    def test_defauts_et_validation(self):
        with tempfile.TemporaryDirectory(prefix="nc-mouv-reg-") as d:
            nc = charger_nc_reglages(d, avec_ile=True)
        par_cle = nc["PAR_CLE"]
        attendus = {
            "ILE_ANIM_VITESSE": "100",
            "ILE_ANIM_BATTERIE": "douces",
            "ILE_ANIM_ECRANS": "",
            "BARRE_REACTION": "glisser",
            "BARRE_CONTENU": "theme",
        }
        for cle, defaut in attendus.items():
            with self.subTest(cle=cle):
                self.assertIn(cle, par_cle)
                self.assertEqual(par_cle[cle].defaut, defaut)
                self.assertEqual(nc["MATERIEL"].get(cle), "ile")

        self.assertEqual(par_cle["ILE_ANIM_VITESSE"].section, "Île")
        self.assertEqual(par_cle["ILE_ANIM_ECRANS"].section, "Île")
        self.assertEqual(par_cle["BARRE_REACTION"].section, "Barre et dock")
        self.assertEqual(par_cle["BARRE_CONTENU"].section, "Barre et dock")
        self.assertEqual(par_cle["BARRE_CONTENU"].groupe, "noctalia")

        # Bornes ILE_ANIM_VITESSE (50..200)
        for ok in ("50", "100", "200"):
            self.assertEqual(par_cle["ILE_ANIM_VITESSE"].valider(ok), ok)
        for ko in ("49", "201", "0", "-10", "abc"):
            with self.assertRaises(ValueError, msg=ko):
                par_cle["ILE_ANIM_VITESSE"].valider(ko)

        # Choix ILE_ANIM_BATTERIE
        for ok in ("douces", "aucune", "continues"):
            self.assertEqual(par_cle["ILE_ANIM_BATTERIE"].valider(ok), ok)
        with self.assertRaises(ValueError):
            par_cle["ILE_ANIM_BATTERIE"].valider("rapide")

        # ILE_ANIM_ECRANS : vide accepté, couples normalisés, entrées invalides refusées
        self.assertEqual(par_cle["ILE_ANIM_ECRANS"].valider(""), "")
        self.assertEqual(par_cle["ILE_ANIM_ECRANS"].valider("DP-1 : vif , eDP-1:aucun, HDMI-*:sec"),
                         "DP-1:vif,eDP-1:aucun,HDMI-*:sec")
        for ko in ("bad", ":doux", "DP-1:inconnu", "DP-1:vif:sec"):
            with self.assertRaises(ValueError, msg=ko):
                par_cle["ILE_ANIM_ECRANS"].valider(ko)

        # Choix BARRE_REACTION et BARRE_CONTENU
        for ok in ("glisser", "fondu"):
            self.assertEqual(par_cle["BARRE_REACTION"].valider(ok), ok)
        with self.assertRaises(ValueError):
            par_cle["BARRE_REACTION"].valider("saut")

        for ok in ("theme", "minimale"):
            self.assertEqual(par_cle["BARRE_CONTENU"].valider(ok), ok)
        with self.assertRaises(ValueError):
            par_cle["BARRE_CONTENU"].valider("complete")

    def test_caches_sans_ile_quickshell(self):
        with tempfile.TemporaryDirectory(prefix="nc-mouv-sans-ile-") as d:
            nc = charger_nc_reglages(d, avec_ile=False)
        visibles = {r.cle for r in nc["VISIBLES"]}
        self.assertFalse(nc["_DISPO"]["ile"])
        for cle in self.CLES:
            self.assertNotIn(cle, visibles, cle)

        with tempfile.TemporaryDirectory(prefix="nc-mouv-avec-ile-") as d:
            nc = charger_nc_reglages(d, avec_ile=True)
        visibles = {r.cle for r in nc["VISIBLES"]}
        self.assertTrue(nc["_DISPO"]["ile"])
        for cle in self.CLES:
            self.assertIn(cle, visibles, cle)


@unittest.skipUnless(shutil.which("qs"), "Quickshell requis")
class MouvementHorsEcran(unittest.TestCase):
    def test_chargement_reel_upower(self):
        with tempfile.TemporaryDirectory(prefix="nc-mouv-reel-") as d:
            root = H.preparer(d, ("Mouvement", "Couleurs"),
                              extra={"Reglages.qml": REGLAGES_TEST, "Partage.qml": PARTAGE_TEST},
                              singletons=("Mouvement", "Partage"))
            (root / "shell.qml").write_text(H.ENTETE + "ShellRoot {\n" + H.OUTILS + """
                Timer {
                    interval: 150; running: true
                    onTriggered: {
                        var r = Mouvement.pourEcran("DP-1")
                        console.log("OK:" + r.profil + ":" + Couleurs.animNom + ":" + r.epsilonPx + ":" + r.epsilonNorm)
                        Qt.exit(0)
                    }
                }
            }\n""")
            code, sortie = H.lancer(root, delai=30)
        self.assertEqual(code, 0, sortie)
        for e in H.ERREURS:
            self.assertNotIn(e, sortie)
        self.assertIn("OK:ressort:ressort:0.2:0.0005", sortie)

    def test_profils_vitesse_batterie_ecrans_partage_sobre(self):
        mouvement_src = (QML / "Mouvement.qml").read_text(encoding="utf-8").replace("UPower.onBattery", "Reglages.batterie")
        with tempfile.TemporaryDirectory(prefix="nc-mouv-cas-") as d:
            root = H.preparer(d, ("Couleurs",),
                              extra={
                                  "Mouvement.qml": mouvement_src,
                                  "Reglages.qml": REGLAGES_TEST,
                                  "Partage.qml": PARTAGE_TEST,
                              },
                              singletons=("Mouvement", "Partage"))
            (root / "shell.qml").write_text(H.ENTETE + "ShellRoot {\n" + H.OUTILS + """
                QtObject {
                    id: sonde
                    readonly property var dp1: Mouvement.pourEcran("DP-1")
                }
                function snap(ecran) {
                    var r = Mouvement.pourEcran(ecran)
                    return {
                        profil: r.profil, actif: r.actif, morphActif: r.morphActif, reactionBarre: r.reactionBarre,
                        raideur: r.raideur, amortiL: r.amortiL, amortiH: r.amortiH,
                        duree: r.duree, dureeCourte: r.dureeCourte, dureeContour: r.dureeContour, dureeSpot: r.dureeSpot,
                        courbeOutCubic: r.courbe === Easing.OutCubic,
                        epsilonPx: r.epsilonPx, epsilonNorm: r.epsilonNorm,
                        couleursNom: Couleurs.animNom,
                        couleursAnim: [Couleurs.anim.raideur, Couleurs.anim.amortiL, Couleurs.anim.amortiH,
                                       Couleurs.anim.duree, Couleurs.anim.contour, Couleurs.anim.spot]
                    }
                }
                Timer {
                    interval: 150; running: true
                    onTriggered: {
                        var res = {}
                        // 1. Défaut secteur 100 %
                        res.defaut = snap("DP-1")

                        // 2. Vitesse 50 % et 200 %
                        Reglages.valeurs = { ILE_ANIM_VITESSE: "50" }
                        res.v50 = snap("DP-1")
                        Reglages.valeurs = { ILE_ANIM_VITESSE: "200" }
                        res.v200 = snap("DP-1")

                        // 3. Batterie douces, aucune, continues
                        Reglages.valeurs = {}
                        Reglages.batterie = true
                        res.batDouces = snap("DP-1")
                        Reglages.valeurs = { ILE_ANIM_BATTERIE: "aucune" }
                        res.batAucune = snap("DP-1")
                        Reglages.valeurs = { ILE_ANIM_BATTERIE: "continues" }
                        res.batContinues = snap("DP-1")
                        Reglages.batterie = false

                        // 4. Exceptions par écran (avec entrées malformées + joker *)
                        Reglages.valeurs = { ILE_ANIM_ECRANS: "DP-1 : vif , bad, :doux, eDP-1:aucun, HDMI-*:sec" }
                        res.exDp1 = snap("DP-1")
                        res.exEdp1 = snap("eDP-1")
                        res.exHdmi = snap("HDMI-A-1")
                        res.exAutre = snap("DP-2")
                        res.sondeReactifProfil = sonde.dp1.profil

                        // 5. Partage actif : actif=true, morphActif=false
                        Reglages.valeurs = {}
                        Partage.sessions = 1
                        res.partage = snap("DP-1")
                        res.sondeReactifPartage = sonde.dp1.morphActif
                        Partage.sessions = 0

                        // 6. Réaction fondu + mode sobre
                        Reglages.valeurs = { BARRE_REACTION: "fondu" }
                        res.fondu = snap("DP-1")
                        Reglages.sobre = true
                        res.sobre = snap("DP-1")

                        console.log("RES:" + JSON.stringify(res))
                        Qt.exit(0)
                    }
                }
            }\n""")
            code, sortie = H.lancer(root, delai=30)
        self.assertEqual(code, 0, sortie)
        for e in H.ERREURS:
            self.assertNotIn(e, sortie)
        m = re.search(r"RES:(\{.*\})", sortie)
        self.assertIsNotNone(m, sortie)
        r = json.loads(m.group(1))

        # Défaut secteur 100 %
        d = r["defaut"]
        self.assertEqual(d["profil"], "ressort")
        self.assertTrue(d["actif"])
        self.assertTrue(d["morphActif"])
        self.assertEqual(d["reactionBarre"], "glisser")
        self.assertAlmostEqual(d["raideur"], 3.4)
        self.assertAlmostEqual(d["amortiL"], 0.34)
        self.assertAlmostEqual(d["amortiH"], 0.36)
        self.assertEqual((d["duree"], d["dureeCourte"], d["dureeContour"], d["dureeSpot"]), (280, 120, 220, 170))
        self.assertTrue(d["courbeOutCubic"])
        self.assertAlmostEqual(d["epsilonPx"], 0.2)
        self.assertAlmostEqual(d["epsilonNorm"], 0.0005)
        self.assertEqual(d["couleursNom"], "ressort")
        self.assertEqual(d["couleursAnim"], [3.4, 0.34, 0.36, 280, 220, 170])

        # Vitesse 50 % / 200 %
        self.assertAlmostEqual(r["v50"]["raideur"], 1.7)
        self.assertEqual((r["v50"]["duree"], r["v50"]["dureeCourte"], r["v50"]["dureeContour"], r["v50"]["dureeSpot"]),
                         (560, 240, 440, 340))
        self.assertAlmostEqual(r["v200"]["raideur"], 6.8)
        self.assertEqual((r["v200"]["duree"], r["v200"]["dureeCourte"], r["v200"]["dureeContour"], r["v200"]["dureeSpot"]),
                         (140, 60, 110, 85))

        # Batterie
        self.assertTrue(r["batDouces"]["actif"])
        self.assertGreaterEqual(r["batDouces"]["amortiL"], 0.85)
        self.assertGreaterEqual(r["batDouces"]["amortiH"], 0.85)
        self.assertEqual((r["batDouces"]["dureeCourte"], r["batDouces"]["dureeContour"], r["batDouces"]["dureeSpot"]),
                         (96, 176, 136))
        self.assertFalse(r["batAucune"]["actif"])
        self.assertFalse(r["batAucune"]["morphActif"])
        self.assertEqual(r["batAucune"]["reactionBarre"], "instantane")
        self.assertEqual((r["batAucune"]["duree"], r["batAucune"]["dureeCourte"],
                          r["batAucune"]["dureeContour"], r["batAucune"]["dureeSpot"]), (0, 0, 0, 0))
        self.assertAlmostEqual(r["batContinues"]["amortiL"], 0.34)
        self.assertEqual(r["batContinues"]["dureeSpot"], 170)

        # Exceptions par écran
        self.assertEqual(r["exDp1"]["profil"], "vif")
        self.assertAlmostEqual(r["exDp1"]["raideur"], 5.5)
        self.assertEqual(r["sondeReactifProfil"], "vif")
        self.assertEqual(r["exEdp1"]["profil"], "aucun")
        self.assertFalse(r["exEdp1"]["actif"])
        self.assertEqual(r["exEdp1"]["duree"], 0)
        self.assertEqual(r["exEdp1"]["reactionBarre"], "instantane")
        self.assertEqual(r["exHdmi"]["profil"], "sec")
        self.assertAlmostEqual(r["exHdmi"]["raideur"], 8.0)
        self.assertEqual(r["exAutre"]["profil"], "ressort")

        # Partage actif
        self.assertTrue(r["partage"]["actif"])
        self.assertFalse(r["partage"]["morphActif"])
        self.assertFalse(r["sondeReactifPartage"])

        # Réaction fondu + sobre
        self.assertEqual(r["fondu"]["reactionBarre"], "fondu")
        self.assertFalse(r["sobre"]["actif"])
        self.assertFalse(r["sobre"]["morphActif"])
        self.assertEqual(r["sobre"]["reactionBarre"], "instantane")
        self.assertEqual(r["sobre"]["duree"], 0)


if __name__ == "__main__":
    unittest.main()

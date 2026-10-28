"""Le lanceur qui sort de la pilule de l'île (LanceurFondu.qml, ILE_LANCEUR_FONDU), hors écran.

Le vrai qs (« qs -p », jamais « qs -c nc-ile ») charge le vrai LanceurFondu.qml avec un Etat, un Reglages et un Partage de
remplacement et une fausse pilule (un Item qui se cache quand Etat.lanceurFondu porte son écran, comme Ile.qml). Cas : réglage
non = rien ne change ; oui = le panneau part exactement de la géométrie de la pilule, la pilule est cachée pendant l'ouverture puis
rendue à la fermeture ; animations réduites, partage d'écran, autre écran, pilule pas au repos = ouverture classique ; deux
ouvertures rapides (fermer avant le premier tour, détruire en pleine ouverture) = pilule jamais laissée cachée ; aucune animation
en boucle dans les fichiers. HOME, XDG_* et TMPDIR sont ceux d'un dossier temporaire court."""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

from tests import _ile_hors_ecran as H

PARTAGE = "pragma Singleton\nimport QtQuick\nQtObject { property bool silence: false; property bool indicateur: false; property int sessions: 0 }\n"
ETAT = """
  property var pilules: ({})
  property string lanceurFondu: ""
  property var lanceurProprio: null
"""
SHELL = """
    property int i: 0
    property int essais: 0
    property bool lance: false
    property var f: null
    property var deuxieme: null
    property var depart: null
    property bool fini: false
    property var etapes: [%s]
    Item {
        id: pilule
        objectName: "pilule"
        x: 700; y: 9; width: 200; height: 30
        property real radius: 15
        property color color: "#101820"
        property bool auRepos: true
        opacity: Etat.lanceurFondu === "DP-1" ? 0 : 1
    }
    Component { id: fabrique; LanceurFondu { ecran: "%s"; largeurEcran: 1600 } }
    function ouvrir() { if (racine.f) racine.f.destroy(); racine.fini = false; racine.f = fabrique.createObject(racine); racine.f.termine.connect(function () { racine.fini = true }); return racine.f.demarrer() }
    Component.onCompleted: Etat.enregistrerPilule("DP-1", pilule)
    Timer {
        interval: 100; running: true; repeat: true
        onTriggered: {
            if (racine.i >= racine.etapes.length) { console.log("FINI"); Qt.exit(0); return }
            var e = racine.etapes[racine.i]
            if (!racine.lance) { if (e.f) e.f(); racine.lance = true; racine.essais = 0; return }
            if (e.c()) { racine.i++; racine.lance = false; return }
            if (++racine.essais > 60) { console.error("ECHEC: " + e.m); Qt.exit(2) }
        }
    }
"""


def etape(c, m, f="null"):
    return "{ f: %s, c: function() { return %s }, m: %s }" % (f if f == "null" else "function() { %s }" % f, c, json.dumps(m))


@unittest.skipUnless(shutil.which("qs"), "Quickshell requis")
class LanceurFondu(unittest.TestCase):
    def lancer(self, etapes, valeurs=None, sobre=False, ecran="DP-1", partage=""):
        os.makedirs("/tmp/claude-1000", exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="nq-", dir="/tmp/claude-1000") as d:
            root = H.preparer(d, ["LanceurFondu"], etat=ETAT + """
  function enregistrerPilule(nom, pilule) { pilules[nom] = pilule }
  function oublierPilule(nom, pilule) { if (pilules[nom] === pilule) delete pilules[nom] }
""", extra={"Partage.qml": PARTAGE}, singletons=("Partage",))
            reglages = (root / "Reglages.qml").read_text().replace("property var valeurs: ({})", "property var valeurs: (" + json.dumps(valeurs or {}) + ")")
            if sobre:
                reglages = reglages.replace("readonly property bool sobre: false", "readonly property bool sobre: true")
            (root / "Reglages.qml").write_text(reglages)
            if partage:
                (root / "Partage.qml").write_text(PARTAGE.replace(partage + ": false", partage + ": true").replace("sessions: 0", "sessions: 0"))
            (root / "shell.qml").write_text(H.ENTETE + "ShellRoot {\n    id: racine\n" + H.OUTILS + SHELL % (",\n".join(etapes), ecran) + "\n}\n")
            code, sortie = H.lancer(root, delai=60)
            for e in H.ERREURS:
                self.assertNotIn(e, sortie, sortie)
            self.assertIn("FINI", sortie, sortie)

    OUI = {"ILE_LANCEUR_FONDU": "oui"}
    CLASSIQUE = [etape("racine.f && !racine.f.actif", "animation lancée", "racine.ouvrir()"),
                 etape("!racine.f.actif && racine.f.p === 1 && pilule.opacity === 1 && Etat.lanceurFondu === '' && racine.f.fermer() === false",
                       "ouverture pas classique")]

    def test_reglage_non_rien_ne_change(self):
        self.lancer(self.CLASSIQUE)
        self.lancer(self.CLASSIQUE, valeurs={"ILE_LANCEUR_FONDU": "non"})

    def test_oui_part_de_la_pilule_puis_la_rend(self):
        self.lancer([
            etape("true", "ouverture", "racine.ouvrir(); racine.depart = ({ p: racine.f.p, w: racine.f.mix(racine.f.w0, 900), r: racine.f.mix(racine.f.r0, 20), h: racine.f.mix(racine.f.h0, 580) })"),
            etape("racine.f.actif && racine.depart.p === 0 && racine.depart.w === 200 && racine.depart.r === 15 && racine.depart.h === 30 && racine.f.x0 === 700 && racine.f.y0 === 9 && racine.f.w0 === 200 && racine.f.h0 === 30"
                  " && racine.f.r0 === 15 && String(racine.f.couleur0) === String(pilule.color)", "la géométrie de départ n'est pas celle de la pilule"),
            etape("pilule.opacity === 0 && Etat.lanceurFondu === 'DP-1' && Etat.lanceurProprio === racine.f", "pilule pas cachée pendant l'ouverture"),
            etape("racine.f.p > 0.98", "le ressort n'arrive pas"),
            etape("racine.f.fermer() === true", "fermeture non prise en charge", "null"),
            etape("racine.fini && !racine.f.actif && pilule.opacity === 1 && Etat.lanceurFondu === ''", "pilule pas rendue à la fermeture")],
            valeurs=self.OUI)

    def test_sobre_partage_autre_ecran_pilule_occupee(self):
        for kw in ({"sobre": True}, {"partage": "silence"}, {"partage": "indicateur"}, {"ecran": "DP-2"}):
            with self.subTest(**kw):
                self.lancer(self.CLASSIQUE, valeurs=self.OUI, **kw)
        self.lancer([etape("true", "pilule occupée", "pilule.auRepos = false")] + self.CLASSIQUE, valeurs=self.OUI)

    def test_ouvertures_rapides_ne_laissent_pas_la_pilule_cachee(self):
        self.lancer([
            # fermer avant le premier tour : finit tout de suite, pilule visible
            etape("racine.fini && Etat.lanceurFondu === '' && pilule.opacity === 1", "pilule cachée après une fermeture immédiate",
                  "racine.ouvrir(); racine.f.fermer()"),
            # détruire en pleine ouverture, puis rouvrir
            etape("pilule.opacity === 0", "pilule pas cachée", "racine.ouvrir()"),
            etape("pilule.opacity === 1 && Etat.lanceurFondu === ''", "pilule cachée après la destruction du lanceur", "racine.f.destroy(); racine.f = null"),
            etape("pilule.opacity === 0", "la nouvelle ouverture ne cache pas la pilule", "racine.ouvrir()"),
            etape("racine.f.p > 0.98", "le ressort n'arrive pas"),
            etape("true", "second lanceur pendant le premier", "var g = fabrique.createObject(racine); racine.deuxieme = g.demarrer(); g.destroy()"),
            etape("racine.deuxieme === false && pilule.opacity === 0", "deux lanceurs en même temps sur une pilule"),
            etape("true", "fermeture", "racine.f.fermer()"),
            etape("racine.fini && pilule.opacity === 1", "pilule jamais rendue")],
            valeurs=self.OUI)

    def test_aucune_animation_en_boucle(self):
        qml = H.QML
        for nom in ("LanceurFondu.qml", "Code.qml"):
            texte = (qml / nom).read_text()
            self.assertNotIn("Animation.Infinite", texte, nom)
        self.assertNotRegex((qml / "LanceurFondu.qml").read_text(), r"repeat:\s*true")
        # la décision dépend d'abord du réglage : sans lui, rien d'autre n'est lu
        self.assertRegex((qml / "LanceurFondu.qml").read_text(), r'ILE_LANCEUR_FONDU", "non"\) !== "oui"')


class RegleHyprland(unittest.TestCase):
    """La règle de calque no_anim sur nc-code suit le réglage : absente si non (Super + X garde le fondu de Hyprland),
    présente si oui ; et changer le réglage recharge Hyprland (groupe « hypr » de nc-reglages)."""
    REGLES = Path(__file__).resolve().parents[1] / "home/.config/hypr/nc/regles.lua"

    def regles(self, valeur):
        harnais = r'''
hl = setmetatable({ layer_rule = function(r) if r.no_anim then print(r.name .. "\t" .. r.match.namespace) end end },
                  { __index = function() return function() end end })
nc = setmetatable({ reglage = function(c, d) if c == "ILE_LANCEUR_FONDU" then return VALEUR end return d end },
                  { __index = function() return function() return "" end end })
dofile(FICHIER)
'''.replace("FICHIER", json.dumps(str(self.REGLES))).replace("VALEUR", json.dumps(valeur))
        r = subprocess.run(["lua", "-"], input=harnais, text=True, capture_output=True, timeout=10, env=dict(PATH="/usr/bin:/bin"))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return dict(l.split("\t", 1) for l in r.stdout.splitlines())

    @unittest.skipUnless(shutil.which("lua"), "lua absent")
    def test_regle_suit_le_reglage(self):
        self.assertNotIn("nc-code-sans-anim", self.regles("non"))
        self.assertEqual(self.regles("oui").get("nc-code-sans-anim"), "^nc-code$")

    def test_reglage_recharge_hyprland(self):
        src = (Path(__file__).resolve().parents[1] / "home/.local/bin/nc-reglages").read_text()
        bloc = src[src.index('R("ILE_LANCEUR_FONDU"'):]
        bloc = bloc[:bloc.index("\n    R(")]
        self.assertIn('groupe="hypr"', bloc)


if __name__ == "__main__":
    unittest.main()

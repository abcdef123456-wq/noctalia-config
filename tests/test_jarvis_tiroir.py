"""Tiroir JARVIS Chat (PanelWindow épinglable), LanceurFondu bidirectionnel et règle de calque Hyprland."""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

from tests import _ile_hors_ecran as H
from tests import _isolation
from tests.test_ile_demarrage import sans_couche

REPO = H.REPO
QML = H.QML
REGLES = REPO / "home/.config/hypr/nc/regles.lua"

PARTAGE = (
    "pragma Singleton\nimport QtQuick\n"
    "QtObject { property bool silence: false; property bool indicateur: false; property int sessions: 0 }\n"
)
ETAT_STUB = """pragma Singleton
import QtQuick
QtObject {
    readonly property bool ecranVu: true
    property var pilules: ({})
    property string lanceurFondu: ""
    property var lanceurProprio: null
    property var emprisesExternes: ({})
    function enregistrerPilule(nom, pilule) { pilules[nom] = pilule }
    function oublierPilule(nom, pilule) { if (pilules[nom] === pilule) delete pilules[nom] }
    function definirEmpriseExterne(nom, rect) {
        if (!nom) return
        var t = Object.assign({}, emprisesExternes)
        if (!rect || rect.width <= 0 || rect.height <= 0) delete t[nom]
        else t[nom] = { x: rect.x, y: rect.y, width: rect.width, height: rect.height }
        emprisesExternes = t
    }
    function effacerEmpriseExterne(nom) {
        if (!nom || emprisesExternes[nom] === undefined) return
        var t = Object.assign({}, emprisesExternes)
        delete t[nom]
        emprisesExternes = t
    }
    function empriseExterne(nom) { return emprisesExternes[nom] || Qt.rect(0, 0, 0, 0) }
}
"""


@unittest.skipUnless(shutil.which("qs"), "Quickshell requis")
class LanceurFonduBidirectionnel(unittest.TestCase):
    def lancer(self, scenario, partage_sessions=0):
        with tempfile.TemporaryDirectory(prefix="nj-", dir=_isolation.dossier_court()) as d:
            root = H.preparer(
                d,
                ["Mouvement", "LanceurFondu"],
                etat="""
  property var pilules: ({})
  property string lanceurFondu: ""
  property var lanceurProprio: null
  function enregistrerPilule(nom, pilule) { pilules[nom] = pilule }
  function oublierPilule(nom, pilule) { if (pilules[nom] === pilule) delete pilules[nom] }
""",
                extra={"Partage.qml": PARTAGE.replace("sessions: 0", f"sessions: {partage_sessions}")},
                singletons=("Mouvement", "Partage"),
            )
            shell = (
                H.ENTETE
                + """ShellRoot {
    id: racine
"""
                + H.OUTILS
                + """
    property int etape: 0
    property int essais: 0
    property real pMid: 0
    property real pReprise: 0
    property bool fini: false
    Item {
        id: pilule
        x: 700; y: 9; width: 200; height: 30
        property real radius: 15
        property color color: "#101820"
        property bool auRepos: true
        opacity: Etat.lanceurFondu === "DP-1" ? 0 : 1
    }
    LanceurFondu {
        id: fondu
        exigeReglage: false
        ecran: "DP-1"
        largeurEcran: 1600
        onTermine: racine.fini = true
    }
    Component.onCompleted: Etat.enregistrerPilule("DP-1", pilule)
    Timer {
        interval: 16; running: true; repeat: true
        onTriggered: {
            if (++racine.essais > 400) { console.error("ECHEC: delai depasse a l'etape " + racine.etape); Qt.exit(2); return }
"""
                + scenario
                + """
        }
    }
}
"""
            )
            (root / "shell.qml").write_text(shell)
            code, sortie = H.lancer(root, delai=30)
            self.assertEqual(code, 0, sortie)
            for e in H.ERREURS:
                self.assertNotIn(e, sortie, sortie)
            self.assertIn("FINI", sortie, sortie)

    def test_inversion_mi_ouverture_puis_mi_fermeture_sans_saut_ni_pilule_bloquee(self):
        self.lancer(
            """
            if (etape === 0) {
                verifier(fondu.demarrer() === true, "demarrer echoue")
                verifier(fondu.actif && fondu.p === 0 && !fondu.fermeture, "etat initial morph")
                etape++
            } else if (etape === 1) {
                if (fondu.p > 0.25 && fondu.p < 0.9) {
                    pMid = fondu.p
                    verifier(Etat.lanceurFondu === "DP-1" && pilule.opacity === 0, "pilule non cachee a mi-ouverture")
                    verifier(fondu.fermer() === true, "fermer a mi-ouverture refuse")
                    verifier(fondu.fermeture && Math.abs(fondu.p - pMid) < 0.05, "saut a l'inversion ouverture->fermeture")
                    etape++
                }
            } else if (etape === 2) {
                if (fondu.p < pMid - 0.04 && fondu.p > 0.02) {
                    pReprise = fondu.p
                    verifier(fondu.demarrer() === true, "demarrer a mi-fermeture refuse")
                    verifier(fondu.actif && !fondu.fermeture && Math.abs(fondu.p - pReprise) < 0.05, "saut a l'inversion fermeture->ouverture")
                    etape++
                }
            } else if (etape === 3) {
                if (fondu.p > 0.95) {
                    fondu.relacherPilule()
                    verifier(fondu.piluleRelachee && Etat.lanceurFondu === "" && pilule.opacity === 1, "relacherPilule inefficace")
                    verifier(fondu.fermer() === true, "fermer apres relache refuse")
                    etape++
                }
            } else if (etape === 4) {
                if (fini) {
                    verifier(!fondu.actif && !fondu.fermeture && Etat.lanceurFondu === "" && Etat.lanceurProprio === null && pilule.opacity === 1,
                             "pilule bloquee cachee apres fermeture")
                    console.log("FINI")
                    Qt.exit(0)
                }
            }
"""
        )

    def test_partage_desactive_morph(self):
        self.lancer(
            """
            verifier(Mouvement.pourEcran("DP-1").morphActif === false, "morphActif doit etre faux en partage")
            verifier(fondu.demarrer() === false, "demarrer doit refuser en partage")
            verifier(!fondu.actif && Etat.lanceurFondu === "", "pilule touchee en partage")
            console.log("FINI")
            Qt.exit(0)
""",
            partage_sessions=1,
        )


@unittest.skipUnless(shutil.which("qs"), "Quickshell requis")
class JarvisChatTiroir(unittest.TestCase):
    def executer(self, scenario):
        with tempfile.TemporaryDirectory(prefix="nt-", dir=_isolation.dossier_court()) as d:
            root = Path(d)
            shutil.copytree(QML, root / "qml")
            (root / "runtime").mkdir(mode=0o700)
            jc = (root / "qml/JarvisChat.qml").read_text()
            jc = sans_couche(jc).replace("FloatingWindow {\n", "FloatingWindow {\n    implicitWidth: 1600; implicitHeight: 1000\n", 1)
            (root / "qml/JarvisChat.qml").write_text(jc)
            (root / "qml/Etat.qml").write_text(ETAT_STUB)
            (root / "qml/Reglages.qml").write_text(
                "pragma Singleton\nimport QtQuick\n"
                "QtObject { readonly property bool sobre: false; readonly property bool iaCoupee: false; "
                "function t(fr, en) { return fr } function val(k, d) { return d } }\n"
            )
            (root / "qml/Partage.qml").write_text(PARTAGE)
            (root / "qml/Agents.qml").write_text(
                'pragma Singleton\nimport QtQuick\nQtObject { property var ias: ({ assistant: { couleur: "#10b981" } }) }\n'
            )
            singletons = {"Etat", "Reglages", "Agents", "Partage", "Mouvement", "Couleurs", "AssistantEtat"}
            noms = [
                "Etat", "Reglages", "Agents", "Partage", "Mouvement", "Couleurs", "AssistantEtat",
                "LanceurFondu", "JarvisChat", "JarvisBouton", "JarvisChamp", "JarvisResultat",
                "Assistant", "AssistantReglages", "AssistantCommande",
                "AssistantOrbe", "AssistantPieces", "Texte", "Ico", "BoutonReglages", "Etincelle", "Pas",
                "LogoAssistant", "Defilement", "Ligne", "Rond",
            ]
            (root / "qml/qmldir").write_text(
                "\n".join(("singleton " if n in singletons else "") + f"{n} 1.0 {n}.qml" for n in noms) + "\n"
            )
            b = root / ".local/bin"
            b.mkdir(parents=True)
            (b / "nc-assistant").write_text(
                """#!/usr/bin/env python3
import json, os, sys, time
from pathlib import Path
with Path(os.environ["HOME"], "calls").open("a") as f:
    f.write(json.dumps({"bin": "nc-assistant", "argv": sys.argv[1:]}) + "\\n")
if sys.argv[1:] == ["selectionner-fichiers"]:
    time.sleep(0.35)
    print(json.dumps({"ok": True, "files": []}), flush=True)
else:
    print(json.dumps({"ok": True, "text": "ok"}), flush=True)
"""
            )
            (b / "nc-assistant").chmod(0o755)
            (b / "nc-jarvis").write_text(
                """#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
with Path(os.environ["HOME"], "calls").open("a") as f:
    f.write(json.dumps({"bin": "nc-jarvis", "argv": sys.argv[1:]}) + "\\n")
"""
            )
            (b / "nc-jarvis").chmod(0o755)
            shell = (
                """import QtQuick
import Quickshell
import Quickshell.Wayland
ShellRoot {
    id: racine
"""
                + H.OUTILS
                + """
    property int etape: 0
    property int essais: 0
    property var tiroir: null
    Item {
        id: pilule1
        x: 700; y: 9; width: 200; height: 30
        property real radius: 15
        property color color: "#101820"
        property bool auRepos: true
    }
    Item {
        id: pilule2
        x: 700; y: 9; width: 200; height: 30
        property real radius: 15
        property color color: "#101820"
        property bool auRepos: true
    }
    Component.onCompleted: {
        Etat.enregistrerPilule("DP-1", pilule1)
        Etat.enregistrerPilule("DP-2", pilule2)
        var c = Qt.createComponent("JarvisChat.qml")
        verifier(c.status === Component.Ready, c.errorString())
        tiroir = c.createObject(racine)
        verifier(tiroir !== null, "creation JarvisChat")
    }
    Timer {
        interval: 40; running: true; repeat: true
        onTriggered: {
            if (!tiroir) return
            if (++racine.essais > 250) { console.error("ECHEC: delai depasse etape " + etape); Qt.exit(2); return }
"""
                + scenario
                + """
        }
    }
}
"""
            )
            (root / "qml/shell.qml").write_text(shell)
            env = dict(
                os.environ,
                HOME=d,
                QT_QPA_PLATFORM="offscreen",
                QT_QUICK_BACKEND="software",
                XDG_RUNTIME_DIR=str(root / "runtime"),
                XDG_CACHE_HOME=str(root / "cache"),
            )
            env.pop("WAYLAND_DISPLAY", None)
            r = subprocess.run(
                ["qs", "--no-color", "-p", str(root / "qml/shell.qml")],
                env=env,
                text=True,
                capture_output=True,
                timeout=20,
            )
            sortie = r.stdout + r.stderr
            self.assertEqual(r.returncode, 0, sortie)
            for e in H.ERREURS:
                self.assertNotIn(e, sortie, sortie)
            self.assertIn("FINI", sortie, sortie)
            p = root / "calls"
            return [json.loads(l) for l in p.read_text().splitlines()] if p.exists() else []

    def test_ephemere_epingle_selecteur_et_cockpit(self):
        calls = self.executer(
            """
            if (etape === 0) {
                tiroir.basculer("DP-1")
                verifier(tiroir.visible && tiroir.ouvert && !tiroir.epingle, "ouverture ephemere")
                verifier(tiroir.coucheVoulue === WlrLayer.Overlay, "couche ephemere")
                verifier(tiroir.focusVoulu === WlrKeyboardFocus.Exclusive, "focus ephemere")
                verifier(tiroir.itemMasque.objectName === "nc-jarvis-chat-fond", "masque ephemere")
                verifier(Etat.empriseExterne("DP-1").width > 0, "emprise externe non publiee")
                etape++
            } else if (etape === 1) {
                var pin = trouver(tiroir.contentItem, "nc-jarvis-chat-pin")
                verifier(pin !== null, "bouton epingle absent")
                pin.clic()
                verifier(tiroir.epingle === true, "epingle non active")
                verifier(tiroir.coucheVoulue === WlrLayer.Top, "couche epinglee")
                verifier(tiroir.focusVoulu === WlrKeyboardFocus.OnDemand, "focus epingle")
                verifier(tiroir.itemMasque.objectName === "nc-jarvis-chat-carte", "masque carte epingle")
                verifier(Etat.lanceurFondu === "", "pilule non relachee en mode epingle")
                pin.clic()
                verifier(!tiroir.epingle && tiroir.coucheVoulue === WlrLayer.Overlay && tiroir.focusVoulu === WlrKeyboardFocus.Exclusive,
                         "retour ephemere")
                AssistantEtat.choisirFichiers()
                etape++
            } else if (etape === 2) {
                if (!AssistantEtat.selecteurOuvert) return
                verifier(tiroir.visible && tiroir.ouvert, "tiroir ferme pendant le selecteur")
                verifier(tiroir.selecteurActif === true, "selecteurActif faux")
                verifier(tiroir.focusVoulu === WlrKeyboardFocus.OnDemand, "Exclusive non relache pour le selecteur")
                verifier(tiroir.itemMasque.objectName === "nc-jarvis-chat-carte", "masque non restreint pour le selecteur")
                etape++
            } else if (etape === 3) {
                if (AssistantEtat.selecteurOuvert) return
                verifier(!tiroir.selecteurActif, "selecteurActif reste vrai")
                verifier(tiroir.focusVoulu === WlrKeyboardFocus.Exclusive, "Exclusive non restaure apres selecteur")
                verifier(tiroir.itemMasque.objectName === "nc-jarvis-chat-fond", "masque non restaure apres selecteur")
                var dash = trouver(tiroir.contentItem, "nc-jarvis-chat-dashboard")
                verifier(dash !== null, "bouton open_in_full absent")
                dash.clic()
                verifier(!tiroir.ouvert, "open_in_full doit fermer le tiroir")
                etape++
            } else if (etape === 4) {
                if (tiroir.visible) return
                verifier(Etat.empriseExterne("DP-1").width === 0, "emprise externe non effacee apres fermeture")
                verifier(Etat.lanceurFondu === "", "pilule bloquee apres fermeture")
                console.log("FINI")
                Qt.exit(0)
            }
"""
        )
        self.assertTrue(any(c["bin"] == "nc-jarvis" and c["argv"] == ["tableau"] for c in calls), calls)

    def test_bascule_multi_ecran_ferme_avant_changement_ecran(self):
        self.executer(
            """
            if (etape === 0) {
                tiroir.basculer("DP-1")
                verifier(tiroir.visible && tiroir.ecranCible === "DP-1", "ouverture DP-1")
                etape++
            } else if (etape === 1) {
                if (tiroir.rectCarte.y <= 12) return
                tiroir.basculer("DP-2")
                verifier(tiroir.visible && tiroir.ecranCible === "DP-1" && tiroir.ecranEnAttente === "DP-2" && !tiroir.ouvert,
                         "changement d'ecran doit fermer DP-1 avant d'ouvrir DP-2")
                etape++
            } else if (etape === 2) {
                if (!tiroir.visible || tiroir.ecranCible !== "DP-2") return
                verifier(tiroir.ouvert && tiroir.ecranEnAttente === "", "reouverture DP-2 incomplete")
                verifier(Etat.empriseExterne("DP-1").width === 0, "emprise DP-1 non nettoyee")
                verifier(Etat.empriseExterne("DP-2").width > 0, "emprise DP-2 absente")
                tiroir.close()
                verifier(!tiroir.visible && Etat.empriseExterne("DP-2").width === 0 && Etat.lanceurFondu === "",
                         "close immediat incomplet")
                console.log("FINI")
                Qt.exit(0)
            }
"""
        )

    def test_contrat_source_panelwindow(self):
        src = (QML / "JarvisChat.qml").read_text()
        self.assertIn("PanelWindow {", src)
        self.assertNotIn("FloatingWindow {", src)
        self.assertIn('WlrLayershell.namespace: "nc-jarvis-chat"', src)
        self.assertIn("WlrLayershell.layer: coucheVoulue", src)
        self.assertIn("WlrLayershell.keyboardFocus: focusVoulu", src)
        self.assertIn("mask: Region { item: fen.itemMasque }", src)
        self.assertNotRegex(src, r"^\s*component\s+\w+\s*:", "pas de component inline")
        self.assertNotRegex(re.sub(r"//.*", "", src), r"MultiEffect|FastBlur|GaussianBlur")


@unittest.skipUnless(shutil.which("lua"), "Lua requis")
class ReglesHyprlandJarvisChat(unittest.TestCase):
    def charger(self, flou):
        harness = r'''
w, l = {}, {}
hl = setmetatable({
    window_rule = function(r) w[r.name] = r end,
    layer_rule = function(r) l[r.name] = r end,
}, { __index = function() return function() end end })
nc = setmetatable({
    reglage = function(c, d) if c == "FENETRES_FLOU" then return __FLOU__ end return d end,
}, { __index = function() return function() return "" end end })
dofile(FICHIER)
local r = l["nc-jarvis-chat"]
print("HAS_WIN\t" .. tostring(w["jarvis-chat"] ~= nil))
print("NS\t" .. tostring(r and r.match and r.match.namespace or ""))
print("NO_ANIM\t" .. tostring(r and r.no_anim == true))
print("BLUR\t" .. tostring(r and r.blur == true))
print("IGNORE_ALPHA\t" .. tostring(r and r.ignore_alpha or ""))
'''.replace("FICHIER", json.dumps(str(REGLES))).replace("__FLOU__", json.dumps(flou))
        r = subprocess.run(["lua", "-"], input=harness, text=True, capture_output=True, timeout=10, env=dict(PATH="/usr/bin:/bin"))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return dict(line.split("\t", 1) for line in r.stdout.splitlines())

    def test_layer_rule_no_anim_et_suppression_window_rule(self):
        oui = self.charger("oui")
        self.assertEqual(oui["HAS_WIN"], "false")
        self.assertEqual(oui["NS"], "^nc-jarvis-chat$")
        self.assertEqual(oui["NO_ANIM"], "true")
        self.assertEqual(oui["BLUR"], "true")
        self.assertEqual(oui["IGNORE_ALPHA"], "0.2")

        non = self.charger("non")
        self.assertEqual(non["HAS_WIN"], "false")
        self.assertEqual(non["NS"], "^nc-jarvis-chat$")
        self.assertEqual(non["NO_ANIM"], "true")
        self.assertEqual(non["BLUR"], "false")


if __name__ == "__main__":
    unittest.main()

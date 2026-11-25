"""Tests dédiés à la refonte en trois volets :
1. Île essentielle (EssentielIle, EnteteIle, Compact épuré) et adaptation visuelle aux thèmes (Couleurs.familleTheme).
2. Panneau Centre de contrôle dédié (PanneauControle, ControleTuile, ControleGlissiere, routage IPC & Hyprland).
3. Refonte du panneau de réglages (Parametres deux volets, ParametresSidebar par catégories, filtre Modifiés)."""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
QML = REPO / "home/.config/quickshell/nc-ile"
THEMES = REPO / "home/.local/share/nc/themes"

ECHECS_QML = ("ReferenceError", "TypeError", "Cannot assign", "Binding loop", "is not a type", "non-existent property")


def sans_couche(texte):
    propre = []
    bloc, retrait = 0, -1
    prop_couche = re.compile(r"^\s*(exclusionMode|WlrLayershell\.\w+|mask|aboveWindows|screen|focusable|exclusiveZone)\s*:")
    ancre_bool = re.compile(r"^\s*anchors\.(top|bottom|left|right)\s*:\s*(true|false)\s*$")
    for ligne in texte.splitlines():
        if retrait >= 0:
            if ligne.strip() == "" or len(ligne) - len(ligne.lstrip()) > retrait:
                continue
            retrait = -1
        if bloc > 0:
            bloc += ligne.count("{") - ligne.count("}")
            continue
        if re.match(r"^\s*(anchors|margins) \{", ligne):
            bloc = ligne.count("{") - ligne.count("}")
            continue
        if ancre_bool.match(ligne):
            continue
        if prop_couche.match(ligne):
            retrait = len(ligne) - len(ligne.lstrip())
            continue
        propre.append(ligne.replace("PanelWindow {", "FloatingWindow {"))
    return "\n".join(propre) + "\n"


class IntegrationSource(unittest.TestCase):
    def test_couche_hyprland_et_routage_controle(self):
        regles = (REPO / "home/.config/hypr/nc/regles.lua").read_text(encoding="utf-8")
        self.assertIn('name = "nc-controle"', regles)
        self.assertIn('namespace = "^nc-controle$"', regles)
        msg = (REPO / "home/.local/bin/nc-shell-msg").read_text(encoding="utf-8")
        self.assertIn("ipc call ile controle", msg)
        racc = (REPO / "home/.config/hypr/nc/raccourcis.lua").read_text(encoding="utf-8")
        self.assertIn("ipc call ile controle", racc)

    def test_themes_architecturaux_ont_leur_forme(self):
        attendus = {"apple": "encoche", "brutaliste": "rectangle", "cyberjaune": "rectangle",
                    "gruvbox": "rectangle", "matrice": "point", "retro": "cadre",
                    "pluie-verte": "cadre", "papier": "cadre"}
        for nom, forme in attendus.items():
            d = json.loads((THEMES / f"{nom}.json").read_text(encoding="utf-8"))
            self.assertEqual(d["reglages"].get("ILE_FORME"), forme, nom)


@unittest.skipUnless(shutil.which("qs"), "Quickshell requis")
class RefonteHorsEcran(unittest.TestCase):
    def lancer_qml(self, shell_code, reglages="", palette=None, langue="fr", faux_reglages=None):
        with tempfile.TemporaryDirectory(prefix="nc-refonte-") as d:
            root = Path(d)
            qml_dir = root / "qml"
            shutil.copytree(QML, qml_dir)
            for f in qml_dir.glob("*.qml"):
                t = f.read_text(encoding="utf-8")
                if "PanelWindow {" in t:
                    f.write_text(sans_couche(t), encoding="utf-8")
            (root / "runtime").mkdir(mode=0o700)
            nc_cfg = root / ".config/nc"
            nc_cfg.mkdir(parents=True)
            if reglages:
                (nc_cfg / "reglages.conf").write_text(reglages, encoding="utf-8")
            if palette is not None:
                (nc_cfg / "palette-ile.json").write_text(json.dumps(palette), encoding="utf-8")
            b = root / ".local/bin"
            b.mkdir(parents=True)
            for nom_script in ("nc-ile-etat", "nc-brightness", "nc-meteo", "nc-vpn", "nc-cloud", "nc-aide-config"):
                p = b / nom_script
                p.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
                p.chmod(0o755)
            if faux_reglages is not None:
                p = b / "nc-reglages"
                p.write_text(faux_reglages, encoding="utf-8")
                p.chmod(0o755)
            (qml_dir / "test_shell.qml").write_text(shell_code, encoding="utf-8")
            env = {k: v for k, v in os.environ.items() if k in ("PATH", "LANG", "LC_ALL")}
            env.update(
                HOME=str(root),
                XDG_CONFIG_HOME=str(root / ".config"),
                XDG_CACHE_HOME=str(root / ".cache"),
                XDG_STATE_HOME=str(root / ".local/state"),
                XDG_DATA_HOME=str(root / ".local/share"),
                XDG_RUNTIME_DIR=str(root / "runtime"),
                TMPDIR=str(root),
                QT_QPA_PLATFORM="offscreen",
                QT_QUICK_BACKEND="software",
                NC_LANGUE=langue,
            )
            r = subprocess.run(["qs", "--no-color", "-p", str(qml_dir / "test_shell.qml")],
                               env=env, text=True, capture_output=True, timeout=20)
            sortie = r.stdout + r.stderr
            self.assertEqual(r.returncode, 0, sortie)
            for err in ECHECS_QML:
                self.assertNotIn(err, sortie)
            return sortie

    def test_familles_themes_couleurs(self):
        cas = [
            ("STYLE=apple\nILE_FORME=encoche\nILE_RAYON=rond\n", "apple"),
            ("STYLE=brutaliste\nILE_FORME=rectangle\nILE_RAYON=carre\nILE_MAJUSCULES=oui\n", "brut"),
            ("STYLE=matrice\nILE_FORME=point\n", "matrice"),
            ("STYLE=papier\nILE_FORME=cadre\nILE_RAYON=carre\nILE_POLICE=Noto Serif\n", "editorial"),
            ("STYLE=synthwave\nILE_LUEUR=oui\nILE_RAYON=rond\n", "neon"),
            ("STYLE=noctalia\n", "noctalia"),
        ]
        for reg, attendu in cas:
            with self.subTest(attendu=attendu):
                out = self.lancer_qml(f'''import QtQuick
import Quickshell
ShellRoot {{
    Timer {{
        interval: 80; running: true; repeat: true
        onTriggered: {{
            if (Object.keys(Reglages.valeurs).length === 0) return
            console.warn("FAMILLE:" + Couleurs.familleTheme + " STYLE=" + Couleurs.themeActif + " FORME=" + Couleurs.forme)
            if (Couleurs.familleTheme !== "{attendu}") Qt.exit(3)
            Qt.quit()
        }}
    }}
    Timer {{ interval: 4000; running: true; onTriggered: {{ console.warn("TIMEOUT:" + Couleurs.familleTheme); Qt.exit(4) }} }}
}}
''', reglages=reg)
                self.assertIn("FAMILLE:" + attendu, out)

    def test_ile_essentielle_par_defaut_et_navigation_entete(self):
        out = self.lancer_qml('''import QtQuick
import Quickshell
ShellRoot {
    id: r
    property bool controleDemande: false
    property bool rechercheDemandee: false
    property bool themesDemandes: false
    FloatingWindow {
        visible: true; implicitWidth: 460; implicitHeight: 420
        Column {
            anchors.fill: parent; anchors.margins: 12; spacing: 8
            EnteteIle {
                id: entete
                width: parent.width
                pages: Etat.vues
                active: Etat.vueActive
                nonLues: 2
                onChoisir: nom => Etat.aller(nom)
                onOuvrirControle: r.controleDemande = true
            }
            EssentielIle {
                id: ess
                width: parent.width
                onOuvrirControle: r.controleDemande = true
                onOuvrirRecherche: r.rechercheDemandee = true
                onOuvrirThemes: r.themesDemandes = true
            }
        }
    }
    Timer {
        interval: 350; running: true
        onTriggered: {
            var v = Etat.vues
            if (v.indexOf("essentiel") < 0 || v.indexOf("notifications") < 0) { console.error("essentiel/notifs absents: " + v); Qt.exit(2) }
            if (v.indexOf("centre") >= 0 || v.indexOf("son") >= 0 || v.indexOf("reseau") >= 0 || v.indexOf("systeme") >= 0) {
                console.error("pages du centre de contrôle encore sur l'île par défaut: " + v); Qt.exit(3)
            }
            if (ess.implicitHeight < 120) { console.error("hauteur EssentielIle trop faible: " + ess.implicitHeight); Qt.exit(4) }
            ess.ouvrirControle()
            ess.ouvrirRecherche()
            ess.ouvrirThemes()
            if (!r.controleDemande || !r.rechercheDemandee || !r.themesDemandes) { console.error("signaux manquants"); Qt.exit(5) }
            console.warn("VUES_DEFAUT:" + v.join(","))
            Qt.quit()
        }
    }
}
''')
        self.assertIn("VUES_DEFAUT:essentiel,notifications", out)

    def test_panneau_controle_dedie_et_sous_vues(self):
        out = self.lancer_qml('''import QtQuick
import Quickshell
ShellRoot {
    id: r
    property bool ferme: false
    property int etape: 0
    function trouver(item, nom) {
        if (!item) return null
        if (item.objectName === nom) return item
        for (var i = 0; i < item.children.length; i++) {
            var res = trouver(item.children[i], nom)
            if (res) return res
        }
        return null
    }
    PanneauControle {
        id: ctrl
        visible: true; implicitWidth: 900; implicitHeight: 720
        onFermer: { r.ferme = true; Etat.fermerControle() }
    }
    Timer {
        interval: 180; running: true; repeat: true
        onTriggered: {
            if (r.etape === 0) {
                Etat.ouvrirControle("TEST", "accueil")
                if (!Etat.controleOuvert || Etat.controleSection !== "accueil") { console.error("ouverture accueil"); Qt.exit(2) }
                if (!trouver(ctrl.contentItem, "nc-controle-tuile-reseau")) { console.error("tuile réseau absente"); Qt.exit(3) }
                if (!trouver(ctrl.contentItem, "nc-controle-volume")) { console.error("glissière volume absente"); Qt.exit(4) }
                r.etape++
                return
            }
            if (r.etape === 1) {
                Etat.allerControle("son")
                if (Etat.controleSection !== "son" || ctrl.surAccueil) { console.error("sous-vue son non ouverte"); Qt.exit(5) }
                if (!trouver(ctrl.contentItem, "nc-controle-retour")) { console.error("bouton retour absent"); Qt.exit(6) }
                r.etape++
                return
            }
            if (r.etape === 2) {
                Etat.allerControle("systeme")
                if (Etat.controleSection !== "systeme") { console.error("sous-vue systeme"); Qt.exit(7) }
                Etat.allerControle("accueil")
                if (!ctrl.surAccueil) { console.error("retour accueil échoué"); Qt.exit(8) }
                Etat.basculer("TEST", false)
                if (Etat.controleOuvert) { console.error("ouvrir l'île doit fermer le centre de contrôle"); Qt.exit(9) }
                console.warn("CONTROLE_OK")
                Qt.quit()
            }
        }
    }
}
''')
        self.assertIn("CONTROLE_OK", out)

    def test_parametres_sidebar_et_filtre_modifies(self):
        faux = '''#!/usr/bin/env python3
import json, sys
if sys.argv[1:2] == ["catalogue"]:
    print(json.dumps([
        dict(cle="ILE_STYLE", section="Île", sectionNom="Île", nom="Couleurs", genre="choix", defaut="terminal",
             aide="Style de l'île.", choix=[["terminal", "Terminal"], ["noir", "Noire"]], mini=0, maxi=0, pas=1,
             unite="", zero="", valeur="noir", affiche="Noire", modifie=True, groupe="ile"),
        dict(cle="ILE_DATE", section="Île", sectionNom="Île", nom="Date", genre="ouinon", defaut="oui",
             aide="Afficher la date.", choix=[["oui", "Oui"], ["non", "Non"]], mini=0, maxi=0, pas=1,
             unite="", zero="", valeur="oui", affiche="Oui", modifie=False, groupe="ile"),
        dict(cle="FENETRES_ARRONDI", section="Fenêtres", sectionNom="Fenêtres", nom="Arrondi", genre="entier", defaut="14",
             aide="Rayon des fenêtres.", choix=[], mini=0, maxi=30, pas=1,
             unite="px", zero="", valeur="20", affiche="20 px", modifie=True, groupe="hypr"),
    ], ensure_ascii=False))
'''
        out = self.lancer_qml('''import QtQuick
import Quickshell
ShellRoot {
    id: r
    property int etape: 0
    function trouver(item, nom) {
        if (!item) return null
        if (item.objectName === nom) return item
        for (var i = 0; i < item.children.length; i++) {
            var res = trouver(item.children[i], nom)
            if (res) return res
        }
        return null
    }
    Parametres { id: p }
    Timer {
        interval: 150; running: true; repeat: true
        onTriggered: {
            if (r.etape === 0) { p.afficher(Quickshell.screens[0].name); r.etape++; return }
            if (p.enCours || p.catalogue.length === 0) return
            if (r.etape === 1) {
                if (p.nbModifies !== 2) { console.error("nbModifies attendu 2, eu " + p.nbModifies); Qt.exit(2) }
                if (!trouver(p.contentItem, "nc-reglages-filtre-modifies")) { console.error("filtre modifiés absent"); Qt.exit(3) }
                if (!trouver(p.contentItem, "nc-reglages-titre-section")) { console.error("titre de section absent"); Qt.exit(4) }
                p.filtreModifies = true
                r.etape++
                return
            }
            if (r.etape === 2) {
                if (p.visibles.length !== 2) { console.error("filtre modifiés doit montrer 2 lignes, eu " + p.visibles.length); Qt.exit(5) }
                p.allerSection("Fenêtres")
                if (p.filtreModifies || p.section !== "Fenêtres" || p.visibles.length !== 1) {
                    console.error("allerSection doit quitter le filtre modifiés"); Qt.exit(6)
                }
                console.warn("PARAMETRES_REFONTE_OK")
                Qt.quit()
            }
        }
    }
}
''', faux_reglages=faux)
        self.assertIn("PARAMETRES_REFONTE_OK", out)


if __name__ == "__main__":
    unittest.main()

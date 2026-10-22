"""Changer de mode graphique (Hybride ↔ Dédiée) sans bouton de notification : la carte de confirmation de l'île
(ModeGraphique.qml, ConfirmationGpu.qml) hors écran, et nc-reglages (Énergie : le mode actuel en lecture seule, l'action
« Changer de mode graphique… », cachés sans objet ; la confirmation dans l'île, sinon au terminal). Un faux nc-gpu-mode
note ses arguments : rien ne bascule ni ne redémarre pour de vrai. HOME temporaire."""
import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock
import warnings

REPO = Path(__file__).resolve().parents[1]
QML = REPO / "home/.config/quickshell/nc-ile"
BIN = REPO / "home/.local/bin"

# Faux nc-gpu-mode, dans <home>/.local/bin : « json » répond le contenu de <home>/gpu.json ; tout appel est noté dans
# <home>/appels. Le dossier vient de son propre chemin, jamais de $HOME (un appel fait hors du HOME du test ne doit rien
# écrire dans le vrai)
FAUX_GPU = '''#!/bin/sh
PATH=/usr/bin:/bin
H="$(cd "$(dirname "$0")/../.." && pwd)"
echo "nc-gpu-mode $*" >> "$H/appels"
[ "$1" = json ] && cat "$H/gpu.json"
exit 0
'''
LEGION = {"mode": "hybride", "methode": "bios", "bios_direct": True, "carte_ecran": "AMD"}
SANS_OBJET = {"mode": "sans-objet", "methode": "", "bios_direct": False, "carte_ecran": ""}


def preparer(home, etat):
    b = home / ".local/bin"
    b.mkdir(parents=True, exist_ok=True)
    (b / "nc-gpu-mode").write_text(FAUX_GPU)
    (b / "nc-gpu-mode").chmod(0o755)
    (home / "gpu.json").write_text(json.dumps(etat))


def appels(home, attendre=None):
    """Les appels notés ; avec `attendre`, patiente (lancement détaché) jusqu'à voir cette ligne."""
    f = home / "appels"
    fin = time.monotonic() + 4
    while True:
        lignes = f.read_text().splitlines() if f.exists() else []
        if attendre is None or attendre in lignes or time.monotonic() > fin:
            return lignes
        time.sleep(0.05)


# ── Carte de confirmation de l'île ─────────────────────────────────────────────────────────────────────────────
@unittest.skipUnless(shutil.which("qs"), "Quickshell requis")
class Carte(unittest.TestCase):
    def executer(self, etat, scenario):
        with tempfile.TemporaryDirectory(prefix="nc-mode-graphique-") as d:
            home = Path(d)
            root = home / "qml"; root.mkdir()
            (home / "runtime").mkdir(mode=0o700)
            preparer(home, etat)
            for nom in ("ModeGraphique", "ConfirmationGpu", "Texte", "Ico"):
                shutil.copy2(QML / (nom + ".qml"), root)
            (root / "Reglages.qml").write_text('pragma Singleton\nimport QtQuick\nQtObject {readonly property bool sobre: true\n'
                                               ' function t(fr,en){return fr} function val(k,d){return d}}')
            (root / "Couleurs.qml").write_text('pragma Singleton\nimport QtQuick\nQtObject {readonly property color fond:"black"; '
                                               'readonly property color texte:"white"; readonly property color texteSec:"#98989d"; '
                                               'readonly property color texteDoux:"#d1d1d6"; readonly property color gris2:"#2c2c2e"; '
                                               'readonly property color gris3:"#3a3a3c"}')
            (root / "qmldir").write_text("\n".join(("singleton " if n in ("ModeGraphique", "Reglages", "Couleurs") else "")
                                                   + n + " 1.0 " + n + ".qml"
                                                   for n in ("ModeGraphique", "ConfirmationGpu", "Texte", "Ico", "Reglages", "Couleurs")))
            (root / "shell.qml").write_text('''import QtQuick
import QtQuick.Window
import QtTest
import Quickshell
ShellRoot {
 id: racine
 property int etape: 0
 property int attente: 0
 property bool occupe: false
 function verifier(v,m) { if (!v) { console.error(m); Qt.exit(2); throw new Error(m) } }
 function trouver(item,nom){if(item.objectName===nom)return item;for(var i=0;i<item.children.length;i++){var r=trouver(item.children[i],nom);if(r)return r}return null}
 function texteDe(b){for(var i=0;i<b.children.length;i++)if(b.children[i].text!==undefined)return b.children[i].text;return ""}
 TestCase { id: souris; when: false }
 Window { visible: true; width: 500; height: 260; ConfirmationGpu { id: carte; width: 460; height: implicitHeight } }
 Timer { interval: 80; running: true; repeat: true; onTriggered: {
  if (occupe) return
  occupe = true
  try {
''' + scenario + '''
  } finally { occupe = false } } }
 Timer { interval: 6000; running: true; onTriggered: Qt.exit(9) }
}''')
            env = dict(os.environ, HOME=d, XDG_RUNTIME_DIR=str(home / "runtime"), XDG_CACHE_HOME=str(home / "cache"),
                       QT_QPA_PLATFORM="offscreen", QT_QUICK_BACKEND="software")
            env.pop("WAYLAND_DISPLAY", None)
            r = subprocess.run(["qs", "--no-color", "-p", str(root / "shell.qml")], env=env, text=True, capture_output=True, timeout=12)
            sortie = r.stdout + r.stderr
            self.assertEqual(r.returncode, 0, sortie)
            for erreur in ("ReferenceError", "TypeError", "Cannot assign", "Binding loop", "is not a type"):
                self.assertNotIn(erreur, sortie)
            attendu = "nc-gpu-mode basculer --sans-question dediee" if "confirmer" in scenario else None
            return [l for l in appels(home, attendu) if "basculer" in l]

    def test_annuler_n_appelle_rien_redemarrer_bascule(self):
        bascules = self.executer(LEGION, '''
if(etape===0){ModeGraphique.demander("");etape++;return}
if(etape===1){if(!ModeGraphique.demande)return
 verifier(ModeGraphique.cible==="dediee","cible : "+ModeGraphique.cible)
 verifier(trouver(carte,"nc-gpu-titre").text==="Passer en mode Dédiée ?","titre : "+trouver(carte,"nc-gpu-titre").text)
 verifier(trouver(carte,"nc-gpu-texte").text==="Ton PC redémarre dans son BIOS : choisis GPU Working Mode → Dédiée, puis F10. Les applis ouvertes seront fermées.","texte : "+trouver(carte,"nc-gpu-texte").text)
 var ok=trouver(carte,"nc-gpu-confirmer"),non=trouver(carte,"nc-gpu-annuler")
 verifier(ok!==null&&non!==null,"boutons absents")
 verifier(texteDe(ok)==="Redémarrer dans le BIOS"&&texteDe(non)==="Annuler","libellés : "+texteDe(ok)+" / "+texteDe(non))
 verifier(non.x<ok.x,"Annuler à gauche, Redémarrer à droite")
 souris.mouseClick(non);verifier(!ModeGraphique.demande,"Annuler n'a pas fermé la carte");etape++;return}
if(etape===2){attente++;if(attente<4)return;ModeGraphique.demander("");etape++;return}
if(etape===3){if(!ModeGraphique.demande)return
 souris.mouseClick(trouver(carte,"nc-gpu-confirmer"));verifier(!ModeGraphique.demande,"la carte reste après Redémarrer");etape++;return}
if(etape===4){Qt.quit()}
''')
        self.assertEqual(bascules, ["nc-gpu-mode basculer --sans-question dediee"], "Annuler n'appelle rien, Redémarrer une fois")

    def test_bascule_par_logiciel_puis_redemarre(self):
        bascules = self.executer({"mode": "dediee", "methode": "supergfxctl", "bios_direct": True, "carte_ecran": "NVIDIA"}, '''
if(etape===0){ModeGraphique.demander("");etape++;return}
if(etape===1){if(!ModeGraphique.demande)return
 verifier(ModeGraphique.cible==="hybride","vers l'autre mode : "+ModeGraphique.cible)
 verifier(trouver(carte,"nc-gpu-texte").text==="Ton PC passe en mode Hybride, puis redémarre. Les applis ouvertes seront fermées.","texte : "+trouver(carte,"nc-gpu-texte").text)
 verifier(texteDe(trouver(carte,"nc-gpu-confirmer"))==="Redémarrer","bouton")
 souris.mouseClick(trouver(carte,"nc-gpu-annuler"));etape++;return}
if(etape===2){ModeGraphique.demander("hybride");etape++;return}
if(etape===3){if(!ModeGraphique.demande)return
 verifier(ModeGraphique.cible==="hybride","mode demandé");souris.mouseClick(trouver(carte,"nc-gpu-annuler"));etape++;return}
if(etape===4){ModeGraphique.demander("dediee");attente=0;etape++;return}
if(etape===5){attente++;if(attente<6)return;verifier(!ModeGraphique.demande,"déjà en Dédiée : pas de carte");Qt.quit()}
''')
        self.assertEqual(bascules, [])

    def test_bios_sans_demarrage_direct_seulement_expliquer(self):
        bascules = self.executer(dict(LEGION, bios_direct=False), '''
if(etape===0){ModeGraphique.demander("");etape++;return}
if(etape===1){if(!ModeGraphique.demande)return
 verifier(trouver(carte,"nc-gpu-confirmer")===null,"pas de redémarrage possible : pas de bouton")
 verifier(trouver(carte,"nc-gpu-texte").text.indexOf("F2")>=0,"la touche à presser")
 var b=trouver(carte,"nc-gpu-annuler");verifier(texteDe(b)==="Compris","libellé : "+texteDe(b))
 souris.mouseClick(b);verifier(!ModeGraphique.demande,"fermée");etape++;return}
if(etape===2){ModeGraphique.demande=true;ModeGraphique.confirmer();verifier(!ModeGraphique.demande,"fermée");Qt.quit()}
''')
        self.assertEqual(bascules, [], "rien n'est lancé")

    def test_sans_objet_pas_de_carte(self):
        bascules = self.executer(SANS_OBJET, '''
if(etape===0){ModeGraphique.demander("");etape++;return}
if(etape===1){attente++;if(attente<8)return
 verifier(!ModeGraphique.demande&&!ModeGraphique.possible,"une seule carte : pas de carte de confirmation");Qt.quit()}
''')
        self.assertEqual(bascules, [])


class FichiersIle(unittest.TestCase):
    """La carte est câblée : fonction ipc de shell.qml, île étirée en carte (Ile.qml), bouton de la page Système ; la
    carte est un fichier à part (le rechargement à chaud ne connaît pas les nouveaux composants internes)."""
    def test_cablage(self):
        shell = (QML / "shell.qml").read_text()
        self.assertIn('function gpuMode(): void { Etat.fermer(); ModeGraphique.demander("") }', shell)
        ile = (QML / "Ile.qml").read_text()
        self.assertIn("sourceComponent: ConfirmationGpu {", ile)
        self.assertIn("ModeGraphique.demande", ile)
        systeme = (QML / "Systeme.qml").read_text()
        self.assertIn('objectName: "nc-mode-graphique"', systeme)
        self.assertIn("visible: ModeGraphique.possible", systeme)
        for f in ("ConfirmationGpu.qml", "ModeGraphique.qml"):
            self.assertNotIn("component ", (QML / f).read_text(), f)
        self.assertNotIn("Timer", (QML / "ModeGraphique.qml").read_text(), "aucun sondage")


# ── nc-reglages ────────────────────────────────────────────────────────────────────────────────────────────────
class Reglages(unittest.TestCase):
    def setUp(self):
        d = tempfile.TemporaryDirectory(prefix="nc-reglages-gpu-")
        self.addCleanup(d.cleanup)
        self.home = Path(d.name)
        (self.home / ".config/nc").mkdir(parents=True)

    def charger(self, etat):
        preparer(self.home, etat)
        with mock.patch.dict(os.environ, HOME=str(self.home), NC_LANGUE="fr"), warnings.catch_warnings():
            warnings.simplefilter("ignore", ResourceWarning)              # lecture de /sys par materiel()
            chargeur = importlib.machinery.SourceFileLoader("nc_reglages_gpu", str(BIN / "nc-reglages"))
            mod = importlib.util.module_from_spec(importlib.util.spec_from_loader(chargeur.name, chargeur))
            chargeur.exec_module(mod)
        mod.catalogue_raccourcis = lambda: []
        return mod

    def test_catalogue_info_et_action_en_tete_d_energie(self):
        mod = self.charger(LEGION)
        cat = mod.catalogue({})
        energie = [x for x in cat if x["section"] == "Énergie"]
        info, action = energie[0], energie[1]
        self.assertEqual((info["cle"], info["genre"], info["nom"]), ("info:mode-graphique", "info", "Mode graphique"))
        self.assertEqual(info["affiche"], "Hybride · se change dans le BIOS")
        self.assertIn("Hybride sur batterie, Dédiée sur secteur", info["aide"])
        self.assertFalse(info["modifie"])
        self.assertEqual((action["cle"], action["genre"], action["nom"]), ("action:mode-graphique", "action", "Changer de mode graphique…"))
        self.assertEqual(action["affiche"], "Passer en Dédiée…")
        self.assertEqual(action["commande"], ["nc-reglages", "mode-graphique"])
        self.assertNotIn("commande", info)
        # Dans l'écran du terminal aussi, en tête de la section Énergie
        lignes = mod.lignes_gpu()
        self.assertEqual([l["genre"] for l in lignes], ["info", "assistant"])
        self.assertEqual(lignes[1]["action"], "mode-graphique")
        self.assertEqual([l for l in appels(self.home) if "basculer" in l], [], "afficher n'appelle jamais la bascule")

    def test_cachees_sans_objet(self):
        for etat in (SANS_OBJET, None):
            with self.subTest(etat=etat):
                if etat is None:
                    mod = self.charger(LEGION)
                    (self.home / ".local/bin/nc-gpu-mode").unlink()      # nc-gpu-mode absent : caché aussi
                    mod._MEMO.clear()
                else:
                    mod = self.charger(etat)
                cles = [x["cle"] for x in mod.catalogue({})]
                self.assertNotIn("info:mode-graphique", cles)
                self.assertNotIn("action:mode-graphique", cles)
                self.assertEqual(mod.lignes_gpu(), [])

    def test_question_comme_la_carte(self):
        mod = self.charger(LEGION)
        self.assertEqual(mod.question_gpu(LEGION), (
            "dediee", "Passer en mode Dédiée ?",
            "Ton PC redémarre dans son BIOS : choisis GPU Working Mode → Dédiée, puis F10. Les applis ouvertes seront fermées.",
            "Redémarrer dans le BIOS"))
        cible, _, texte, bouton = mod.question_gpu({"mode": "dediee", "methode": "gsync", "bios_direct": False})
        self.assertEqual((cible, bouton), ("hybride", "Redémarrer"))
        self.assertIn("puis redémarre", texte)
        self.assertEqual(mod.question_gpu(dict(LEGION, bios_direct=False))[3], "", "rien à confirmer")

    def ecran(self, mod, choix):
        """L'écran du terminal sans curses : la question répond `choix` (0 : Redémarrer, 1 : Annuler)."""
        e = mod.Ecran.__new__(mod.Ecran)
        e.messages, e.questions = [], []
        e.statut = lambda texte, erreur=False: e.messages.append(texte)
        e.dessiner = lambda: None
        e.e = mock.Mock()
        e.choisir = lambda titre, options, aide="", texte="": e.questions.append((titre, options, texte)) or choix
        e.afficher = lambda titre, points: e.questions.append((titre, points))
        mod.curses = mock.Mock()
        return e

    def test_terminal_ile_d_abord_sinon_question(self):
        mod = self.charger(LEGION)
        demandes = []
        mod.ile_appel = lambda f, d: demandes.append(f) or "ok"
        e = self.ecran(mod, 0)
        with mock.patch.dict(os.environ, HOME=str(self.home)):
            e.assistant({"genre": "assistant", "action": "mode-graphique"})
        self.assertEqual(demandes, ["gpuMode"])
        self.assertEqual(e.questions, [], "l'île pose la question : rien ici")
        self.assertEqual(e.messages[-1], "Confirmation ouverte dans l'île")
        # Île absente : la question ici ; Annuler n'appelle rien
        mod.ile_appel = lambda f, d: "absente"
        e = self.ecran(mod, 1)
        e.assistant({"genre": "assistant", "action": "mode-graphique"})
        self.assertEqual(e.questions[0][:2], ("Passer en mode Dédiée ?", ["Redémarrer dans le BIOS", "Annuler"]))
        self.assertIn("GPU Working Mode → Dédiée", e.questions[0][2])
        self.assertEqual([l for l in appels(self.home) if "basculer" in l], [])
        # Redémarrer : la bascule, sans autre question
        e = self.ecran(mod, 0)
        with mock.patch.dict(os.environ, HOME=str(self.home)):
            e.assistant({"genre": "assistant", "action": "mode-graphique"})
        self.assertEqual([l for l in appels(self.home) if "basculer" in l], ["nc-gpu-mode basculer --sans-question dediee"])

    def test_commande_mode_graphique(self):
        """nc-reglages mode-graphique (le bouton de la fenêtre des réglages) : l'île ; sans île ni terminal, un terminal
        ouvert pour la question. Jamais la bascule directement."""
        preparer(self.home, LEGION)
        faux = self.home / "faux"; faux.mkdir()
        (faux / "python3").symlink_to(sys.executable)
        for nom in ("kitty", "qs"):
            (faux / nom).write_text(f'#!/bin/sh\necho "{nom} $*" >> "$HOME/appels"\nexit 0\n'); (faux / nom).chmod(0o755)
        env = dict(os.environ, HOME=str(self.home), PATH=str(faux), NC_LANGUE="fr", XDG_CONFIG_HOME=str(self.home / ".config"))
        r = subprocess.run([str(BIN / "nc-reglages"), "mode-graphique"], env=env, capture_output=True, text=True, timeout=30,
                           stdin=subprocess.DEVNULL)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("qs -c nc-ile ipc call ile gpuMode", appels(self.home))
        self.assertFalse(any("kitty" in l for l in appels(self.home)))
        (faux / "qs").unlink()
        (self.home / "appels").unlink()
        r = subprocess.run([str(BIN / "nc-reglages"), "mode-graphique"], env=env, capture_output=True, text=True, timeout=30,
                           stdin=subprocess.DEVNULL)
        self.assertEqual(r.returncode, 0, r.stderr)
        fin = time.monotonic() + 4                         # kitty est lancé détaché
        while not any(l.startswith("kitty") for l in appels(self.home)) and time.monotonic() < fin:
            time.sleep(0.05)
        kitty = [l for l in appels(self.home) if l.startswith("kitty")]
        self.assertEqual(len(kitty), 1, appels(self.home))
        self.assertTrue(kitty[0].startswith("kitty --class nc-reglages -e ") and kitty[0].endswith("nc-reglages mode-graphique"), kitty)
        self.assertEqual([l for l in appels(self.home) if "basculer" in l], [])


if __name__ == "__main__":
    unittest.main()

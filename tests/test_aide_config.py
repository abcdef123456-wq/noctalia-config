"""Réponses aux questions sur la config (nc-aide-config, AideConfig.js dans le Spotlight) et nouveaux réglages de
personnalisation (préférences Firefox, lignes du terminal). HOME isolé ; la documentation est celle du dépôt."""
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
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[1]
BIN = REPO / "home/.local/bin"
QML = REPO / "home/.config/quickshell/nc-ile"
QS = shutil.which("qs") or "qs"


def charger(nom, chemin):
    l = importlib.machinery.SourceFileLoader(nom, str(chemin))
    s = importlib.util.spec_from_loader(nom, l)
    m = importlib.util.module_from_spec(s)
    l.exec_module(m)
    return m


class Index(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        b = self.home / ".local/bin"; b.mkdir(parents=True)
        for n in ("nc-aide-config", "nc-reglages", "nc-aide", "nc-raccourci", "nc-langue", "nc-anim"):
            if (BIN / n).exists():
                shutil.copy2(BIN / n, b / n)
        (self.home / ".config/nc").mkdir(parents=True)
        (self.home / ".config/nc/depot").write_text(str(REPO) + "\n")
        (self.home / ".config/nc/reglages.conf").write_text("LANGUE=fr\n")
        self.env = dict(os.environ, HOME=str(self.home), XDG_CONFIG_HOME=str(self.home / ".config"),
                        XDG_CACHE_HOME=str(self.home / ".cache"), NC_LANGUE="fr", PATH="/usr/bin:/bin")
        self.env.pop("WAYLAND_DISPLAY", None)

    def lancer(self, *a):
        return subprocess.run([str(self.home / ".local/bin/nc-aide-config"), *a], env=self.env, capture_output=True, text=True, timeout=60)

    def chercher(self, q):
        return json.loads(self.lancer("chercher", q, "--json").stdout)

    def test_index_reponses_et_cache(self):
        r = self.lancer("index")
        self.assertEqual(r.returncode, 0, r.stderr)
        f = self.home / ".cache/nc/aide-config.json"
        index = json.loads(f.read_text())
        types = {e["type"] for e in index["entrees"]}
        self.assertTrue({"reglage", "commande", "doc"} <= types, types)
        self.assertGreater(len(index["entrees"]), 150)
        # Les questions de quelqu'un qui ne connaît pas la config
        attendus = {
            "comment changer la taille du curseur": "Taille du pointeur",
            "how to change the keyboard layout": "Disposition du clavier",
            "où sont mes captures d'écran": "Dossier des captures d'écran",
            "désactiver les notifications la nuit": "Ne pas déranger la nuit",
            "installer un logiciel": "Logiciels à installer dans le Spotlight",
        }
        for q, titre in attendus.items():
            titres = [e["titre"] for e in self.chercher(q)[:3]]
            self.assertIn(titre, titres, f"{q} → {titres}")
        # Les mots outils seuls ne trouvent rien ; « vide » ne trouve pas « vidéo »
        self.assertEqual(self.chercher("comment est-ce que"), [])
        m = charger("ncaide", self.home / ".local/bin/nc-aide-config")
        self.assertFalse(m.correspond("vide", ["video"]))
        self.assertTrue(m.correspond("fenetre", ["fenetres"]) and m.correspond("fond", ["fonds"]))
        # À jour : gardé tel quel (même fichier) ; une source qui change : refait
        avant = f.stat().st_mtime_ns
        time.sleep(0.05); self.lancer("index")
        self.assertEqual(f.stat().st_mtime_ns, avant, "index à jour : pas refait")
        self.env["NC_LANGUE"] = "en"
        self.lancer("index")
        self.assertNotEqual(f.stat().st_mtime_ns, avant, "langue changée : refait")


class Personnalisation(unittest.TestCase):
    def test_firefox_suit_les_reglages(self):
        with tempfile.TemporaryDirectory() as d:
            env = dict(os.environ, HOME=d, XDG_CONFIG_HOME=d + "/.config")
            (Path(d) / ".config/nc").mkdir(parents=True)
            (Path(d) / ".config/nc/reglages.conf").write_text("FIREFOX_ONGLETS_VERTICAUX=oui\nFIREFOX_SESSION=non\nFIREFOX_DEFILEMENT_DOUX=non\n")
            with patch.dict(os.environ, env):
                m = charger("ncff", BIN / "nc-firefox")
                b = m.bloc_reglages()
            self.assertIn('user_pref("sidebar.verticalTabs", true);', b)
            self.assertIn('user_pref("browser.startup.page", 1);', b)
            self.assertIn('user_pref("general.smoothScroll", false);', b)

    def test_terminal_clignote_copie_ligatures(self):
        with tempfile.TemporaryDirectory() as d:
            with patch.dict(os.environ, dict(os.environ, HOME=d)):
                m = charger("ncreg", BIN / "nc-reglages")
                m.KITTY_OUT = str(Path(d) / "kitty.conf")
                with patch.object(m.subprocess, "run") as run:
                    m.appliquer_terminal({"TERMINAL_CLIGNOTE": "non", "TERMINAL_COPIE_SELECTION": "oui", "TERMINAL_LIGATURES": "non"})
                texte = Path(m.KITTY_OUT).read_text()
            for l in ("cursor_blink_interval 0", "copy_on_select clipboard", "disable_ligatures always"):
                self.assertIn(l, texte)
            self.assertTrue(run.called, "kitty relit sa config")


@unittest.skipUnless(shutil.which("qs"), "Quickshell requis")
class SpotlightQuestions(unittest.TestCase):
    def test_questions_reponses_instantanees_puis_ia(self):
        m = charger("ncaide2", BIN / "nc-aide-config")
        entrees = [m.entree("raccourci", "Choisir le fond d'écran", "Super + W · Applis et barre", section="Applis et barre", touches="Super + W"),
                   m.entree("reglage", "Changer de fond automatiquement", "Un nouveau fond d'écran à intervalle régulier.", section="Fonds d'écran", cle="FONDS_ROTATION", valeur="Oui"),
                   m.entree("reglage", "Taille du pointeur", "La taille du curseur de la souris.", section="Clavier et souris", cle="CURSEUR_TAILLE", valeur="24"),
                   m.entree("doc", "Fonds d'écran", "Super + W ouvre le carrousel des fonds d'écran : flèches pour choisir, Entrée pour appliquer.", fichier="README.md"),
                   m.entree("commande", "nc-anim", "Animations du bouton d'arrêt.", exemple="nc-anim liste")]
        index = dict(signature=[], synonymes=m.SYNONYMES, vides=sorted(m.VIDES), entrees=entrees)
        attendu = [e["titre"] for e in m.chercher(index, "comment changer le fond d'écran", 4)]
        with tempfile.TemporaryDirectory(prefix="nc-spot-aide-") as d:
            root = Path(d); q = root / "qml"; shutil.copytree(QML, q); (root / "runtime").mkdir(mode=0o700)
            (root / "cache/nc").mkdir(parents=True)
            (root / "cache/nc/aide-config.json").write_text(json.dumps(index, ensure_ascii=False))
            (q / "Reglages.qml").write_text('pragma Singleton\nimport QtQuick\nQtObject {property bool iaCoupee: false; function t(fr,en){return fr} function val(k,d){return d} function pageActive(n){return true}}')
            (q / "Etat.qml").write_text('''pragma Singleton
import QtQuick
import Quickshell
QtObject { property string saisie: ""; property bool recherche: true; property bool nuit: false; property string ecranOuvert: "TEST"
 readonly property string bin: Quickshell.env("HOME") + "/.local/bin/"; property int fermetures: 0; signal validerRecherche()
 function faire(c) {} function fermer() { fermetures++ } function aller(p) {} function basculer(e, c) {} function basculerCafe() {} function lancerPomodoro() {} }''')
            (q / "AssistantEtat.qml").write_text('pragma Singleton\nimport QtQuick\nQtObject {function formater(t){return t}}')
            (q / "Etincelle.qml").write_text('import QtQuick\nItem {property real taille: 10; property bool tourne: false; property string agent: ""}')
            noms = ["Reglages", "Etat", "AssistantEtat", "Couleurs", "Connexion", "Recherche", "Etincelle", "Texte", "Ico"]
            (q / "qmldir").write_text("\n".join(("singleton " if n in ("Reglages", "Etat", "AssistantEtat", "Couleurs", "Connexion") else "") + n + " 1.0 " + n + ".qml" for n in noms))
            b = root / ".local/bin"; b.mkdir(parents=True)
            for nom, code in {"nc-apps": '#!/bin/sh\necho "[]"\n', "nc-demander": "#!/bin/sh\necho Claude\n", "nc-aide-config": "#!/bin/sh\nexit 0\n",
                              "nc-logiciels": "#!/bin/sh\necho '[]'\n", "hyprctl": "#!/bin/sh\necho '[]'\n",
                              "qs": '#!/bin/sh\necho "$*" >> "$HOME/qs-appels"\n'}.items():
                (b / nom).write_text(code); (b / nom).chmod(0o755)
            (q / "shell.qml").write_text('''import QtQuick
import Quickshell
ShellRoot {
 id: racine
 property int etape: 0
 function trouver(item,nom){if(item.objectName===nom)return item;for(var i=0;i<item.children.length;i++){var r=trouver(item.children[i],nom);if(r)return r}return null}
 function verifier(ok,m){if(!ok){console.error(m);Qt.exit(2);throw new Error(m)}}
 FloatingWindow { visible: true; implicitWidth: 700; implicitHeight: 500; Recherche { id: spot; width: 700; actif: true } }
 Timer { interval: 100; running: true; repeat: true; onTriggered: {
  var champ = trouver(spot, "nc-spotlight-champ")
  if (etape === 0) { if (!spot.aide) return; champ.text = "? comment changer le fond d'écran"; etape++; return }
  if (etape === 1) {
   var t = spot.resultats.map(x => x.titre)
   verifier(JSON.stringify(t.slice(0, ATTENDU.length)) === JSON.stringify(ATTENDU), "JavaScript et Python classent pareil : " + JSON.stringify(t))
   verifier(spot.resultats[spot.resultats.length - 1].sous.indexOf("Demander à") === 0, "l'IA en dernier")
   var i = t.indexOf("Fonds d'écran"); verifier(i >= 0, "passage de doc absent"); spot.valider(i, false)
   verifier(spot.reponseAide.indexOf("carrousel") > 0 && Etat.fermetures === 0, "la doc s'affiche dans le Spotlight, sans le fermer")
   spot.valider(t.indexOf("Taille du pointeur") >= 0 ? t.indexOf("Taille du pointeur") : t.indexOf("Changer de fond automatiquement"), false)
   champ.text = "comment changer la taille du curseur"; etape++; return }
  if (etape === 2) {
   verifier(spot.resultats.length && spot.resultats[0].titre === "Taille du pointeur", "question sans « ? » : réponse en tête : " + JSON.stringify(spot.resultats.map(x => x.titre)))
   Qt.quit() }
 } }
 Timer { interval: 9000; running: true; onTriggered: Qt.exit(9) }
}'''.replace("ATTENDU", json.dumps(attendu)))
            env = dict(os.environ, HOME=d, QT_QPA_PLATFORM="offscreen", QT_QUICK_BACKEND="software", XDG_RUNTIME_DIR=str(root / "runtime"),
                       XDG_CACHE_HOME=str(root / "cache"), PATH=str(b) + os.pathsep + os.environ["PATH"])
            env.pop("WAYLAND_DISPLAY", None)
            # Le vrai qs par son chemin : le faux, dans le PATH du test, n'intercepte que les appels du Spotlight
            r = subprocess.run([QS, "--no-color", "-p", str(q / "shell.qml")], env=env, text=True, capture_output=True, timeout=15)
            sortie = r.stdout + r.stderr
            self.assertEqual(r.returncode, 0, sortie)
            for e in ("ReferenceError", "TypeError", "is not a type"):
                self.assertNotIn(e, sortie)
            self.assertIn("reglagesChercher", (root / "qs-appels").read_text(), "un réglage ouvre la fenêtre des réglages sur lui")


if __name__ == "__main__":
    unittest.main()

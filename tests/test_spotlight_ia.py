"""L'IA dans le Spotlight (Recherche.qml) hors écran : « ! » sur le texte sélectionné (filtre des actions, consigne
libre, réponse en flux puis « Copier le résultat »), « ? » avec la commande proposée, le nom et le logo de l'IA qui
répond réellement (repli compris), et l'IA coupée : messages clairs, page JARVIS cachée, aucune commande d'IA lancée."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
QML = REPO / "home/.config/quickshell/nc-ile"


@unittest.skipUnless(shutil.which("qs"), "Quickshell requis")
class SpotlightIA(unittest.TestCase):
    def test_texte_question_et_ia_coupee(self):
        with tempfile.TemporaryDirectory(prefix="nc-spotlight-ia-") as d:
            root = Path(d); shutil.copytree(QML, root / "qml"); (root / "runtime").mkdir(mode=0o700)
            q = root / "qml"
            (q / "Reglages.qml").write_text('''pragma Singleton
import QtQuick
QtObject {
 property var v: ({})
 readonly property bool iaCoupee: v.IA_MODE === "non"
 function t(fr,en){return fr}
 function val(k,d){return v[k] !== undefined ? v[k] : d}
 function pageActive(n){return !(iaCoupee && (n === "assistant" || n === "claude"))}
}''')
            (q / "Etat.qml").write_text('''pragma Singleton
import QtQuick
import Quickshell
QtObject {
 property string saisie: ""
 property string texteIA: ""
 property bool recherche: true
 property bool nuit: false
 readonly property string bin: Quickshell.env("HOME") + "/.local/bin/"
 property int fermetures: 0
 signal validerRecherche()
 function faire(c) {} function fermer() { fermetures++ } function aller(p) {} function basculer(e, c) {}
}''')
            (q / "AssistantEtat.qml").write_text('pragma Singleton\nimport QtQuick\nQtObject {function formater(t){return t}}')
            (q / "Etincelle.qml").write_text('import QtQuick\nItem {property real taille: 10; property bool tourne: false; property string agent: ""}')
            noms = ["Reglages", "Etat", "AssistantEtat", "Couleurs", "Recherche", "Etincelle", "Texte", "Ico"]
            (q / "qmldir").write_text("\n".join(("singleton " if n in ("Reglages", "Etat", "AssistantEtat", "Couleurs") else "") + n + " 1.0 " + n + ".qml" for n in noms))
            b = root / ".local/bin"; b.mkdir(parents=True)
            scripts = {
                "nc-apps": '#!/bin/sh\necho "[]"\n',
                "hyprctl": "#!/bin/sh\necho '[]'\n",
                "nc-aide-config": "#!/bin/sh\nexit 0\n",
                "nc-demander": '''#!/bin/sh
echo "nc-demander $*" >> "$HOME/appels"
case "$1" in
  --ia) echo '{"nom": "Claude (API Anthropic)", "agent": "claude", "coupee": false}' ;;
  --flux) echo '{"ia": "Claude (API Anthropic)", "id": "anthropic", "agent": "claude"}'; echo '{"t": "Voici les fichiers."}'; echo '{"t": "\\n$ ls -la"}' ;;
esac
''',
                "nc-ia": '''#!/bin/sh
echo "nc-ia $*" >> "$HOME/appels"
case "$*" in *--stdin*) cat > "$HOME/stdin-ia" ;; esac
echo '{"ia": "Claude (API Anthropic)", "id": "anthropic", "agent": "claude"}'
echo '{"t": "", "erreur": false}'
echo '{"ia": "Codex", "id": "codex", "agent": "codex"}'
echo '{"t": "Texte "}'; echo '{"t": "traduit"}'
''',
                "wl-copy": '#!/bin/sh\necho "wl-copy $*" >> "$HOME/appels"\n',
            }
            for nom, code in scripts.items():
                (b / nom).write_text(code); (b / nom).chmod(0o755)
            (q / "shell.qml").write_text('''import QtQuick
import Quickshell
ShellRoot {
 id: racine
 property int etape: 0
 function trouver(item,nom){if(item.objectName===nom)return item;for(var i=0;i<item.children.length;i++){var r=trouver(item.children[i],nom);if(r)return r}return null}
 function verifier(ok,message){if(!ok){console.error(message);Qt.exit(2);throw new Error(message)}}
 function titres(){ return spot.resultats.map(x => x.titre) }
 FloatingWindow { id: fen; visible: true; implicitWidth: 700; implicitHeight: 500
  Recherche { id: spot; width: 700; actif: true } }
 Timer { interval: 100; running: true; repeat: true; onTriggered: {
  var champ = trouver(spot, "nc-spotlight-champ")
  if (etape === 0) { if (spot.nomIA === "") return
   verifier(spot.nomIA === "Claude (API Anthropic)", "nom de l'IA : " + spot.nomIA)
   champ.text = "! tra"; etape++; return }
  if (etape === 1) {
   var t = titres()
   verifier(t[0] === "Traduire" && t.indexOf("Résumer") < 0, "actions filtrées : " + JSON.stringify(t))
   verifier(t[t.length - 1] === "« tra »", "consigne libre proposée : " + JSON.stringify(t))
   spot.valider(0, false); verifier(Etat.fermetures === 0, "le Spotlight reste ouvert pour la réponse"); etape++; return }
  if (etape === 2) { if (spot.reflechit) return
   verifier(spot.reponse === "Texte traduit", "réponse : " + JSON.stringify(spot.reponse))
   verifier(spot.iaReponse === "Codex" && spot.agentReponse === "codex", "IA qui a vraiment répondu (repli) : " + spot.iaReponse + " " + spot.agentReponse)
   verifier(titres()[0] === "Copier le résultat", "copie proposée : " + JSON.stringify(titres()))
   spot.valider(0, false); verifier(Etat.fermetures === 1, "Entrée copie et ferme")
   champ.text = "? lister les fichiers"; etape++; return }
  if (etape === 3) { if (spot.nomIA !== "Claude (API Anthropic)") return      // relu après la réponse de Codex
   var n = spot.resultats.length - 1
   verifier(spot.resultats[n].sous.indexOf("Claude (API Anthropic)") >= 0, "« ? » : " + JSON.stringify(spot.resultats))
   spot.valider(n, false); etape++; return }
  if (etape === 4) { if (spot.reflechit) return
   verifier(spot.commandeIA === "ls -la" && titres()[0] === "ls -la", "commande proposée : " + spot.commandeIA)
   verifier(spot.reponse === "Voici les fichiers.", "réponse sans la ligne de commande : " + JSON.stringify(spot.reponse))
   // IA coupée
   Reglages.v = { IA_MODE: "non" }; spot.iaCoupee = true
   champ.text = "! résumer"; etape++; return }
  if (etape === 5) {
   verifier(titres()[0] === "L'IA est désactivée" && titres().length === 1, "« ! » coupé : " + JSON.stringify(titres()))
   champ.text = "? comment faire"
   verifier(titres().indexOf("L'IA est désactivée") >= 0, "« ? » coupé : " + JSON.stringify(titres()))
   champ.text = "jarvis"
   verifier(titres().indexOf("JARVIS") < 0, "page JARVIS cachée : " + JSON.stringify(titres()))
   champ.text = "traduire"
   verifier(titres().indexOf("IA sur le texte copié") < 0, "actions d'IA cachées : " + JSON.stringify(titres()))
   champ.text = "rallumer"
   verifier(titres().indexOf("Rallumer l'IA") >= 0, "on peut la rallumer depuis le Spotlight : " + JSON.stringify(titres()))
   // Une entrée du presse-papiers de l'île : « ! » sur ce texte-là, passé par l'entrée standard
   Reglages.v = {}; spot.iaCoupee = false
   Etat.texteIA = "texte du presse-papiers"; Etat.saisie = "! "; spot.demarrer()
   verifier(spot.texteSource === "texte du presse-papiers" && Etat.texteIA === "", "texte repris : " + spot.texteSource)
   verifier(titres()[0] === "Résumer" && spot.resultats[0].sous.indexOf("presse-papiers") >= 0, "source affichée : " + JSON.stringify(spot.resultats[0]))
   spot.valider(0, false); etape++; return }
  if (etape === 6) { if (spot.reflechit) return
   Qt.quit() }
 } }
 Timer { interval: 12000; running: true; onTriggered: Qt.exit(9) }
}''')
            env = dict(os.environ, HOME=d, QT_QPA_PLATFORM="offscreen", QT_QUICK_BACKEND="software", XDG_RUNTIME_DIR=str(root / "runtime"),
                       XDG_CACHE_HOME=str(root / "cache"), PATH=str(b) + os.pathsep + os.environ["PATH"])
            env.pop("WAYLAND_DISPLAY", None)
            r = subprocess.run(["qs", "--no-color", "-p", str(q / "shell.qml")], env=env, text=True, capture_output=True, timeout=20)
            sortie = r.stdout + r.stderr
            self.assertEqual(r.returncode, 0, sortie)
            for erreur in ("ReferenceError", "TypeError", "is not a type"):
                self.assertNotIn(erreur, sortie)
            appels = (root / "appels").read_text()
            self.assertIn("nc-ia texte traduire --flux", appels)
            self.assertIn("wl-copy -- Texte traduit", appels)
            self.assertIn("nc-demander --flux lister les fichiers", appels)
            self.assertEqual(appels.count("nc-ia texte traduire"), 1, "rien de lancé une fois l'IA coupée")
            self.assertIn("nc-ia texte resumer --flux --stdin", appels)
            self.assertEqual((root / "stdin-ia").read_text(), "texte du presse-papiers")


    def test_arobase_plan_puis_confirmation(self):
        with tempfile.TemporaryDirectory(prefix="nc-spotlight-agent-") as d:
            root = Path(d); shutil.copytree(QML, root / "qml"); (root / "runtime").mkdir(mode=0o700)
            q = root / "qml"
            (q / "Reglages.qml").write_text('pragma Singleton\nimport QtQuick\nQtObject {property var v: ({IA_ACTIONS: "confirmer"}); readonly property bool iaCoupee: false\n'
                                            ' function t(fr,en){return fr} function val(k,d){return v[k] !== undefined ? v[k] : d} function pageActive(n){return true}}')
            (q / "Etat.qml").write_text('pragma Singleton\nimport QtQuick\nimport Quickshell\nQtObject {property string saisie: ""; property string texteIA: ""; property bool recherche: true\n'
                                        ' readonly property string bin: Quickshell.env("HOME") + "/.local/bin/"; property int fermetures: 0; signal validerRecherche()\n'
                                        ' function faire(c) {} function fermer() { fermetures++ } function aller(p) {}}')
            (q / "AssistantEtat.qml").write_text('pragma Singleton\nimport QtQuick\nQtObject {function formater(t){return t}}')
            (q / "Etincelle.qml").write_text('import QtQuick\nItem {property real taille: 10; property bool tourne: false; property string agent: ""}')
            noms = ["Reglages", "Etat", "AssistantEtat", "Couleurs", "Recherche", "Etincelle", "Texte", "Ico"]
            (q / "qmldir").write_text("\n".join(("singleton " if n in ("Reglages", "Etat", "AssistantEtat", "Couleurs") else "") + n + " 1.0 " + n + ".qml" for n in noms))
            b = root / ".local/bin"; b.mkdir(parents=True)
            plan = {"id": "0123456789abcdef", "reponse": "Je coupe le Bluetooth.", "ia": "Claude Code", "agent": "claude", "refus": [],
                    "actions": [{"n": 0, "libelle": "Bluetooth : off", "danger": False, "fait": False, "ok": None, "resultat": ""},
                                {"n": 1, "libelle": "Arrêter nc-pouls.service", "danger": True, "fait": False, "ok": None, "resultat": ""}]}
            fait = dict(plan, actions=[dict(plan["actions"][0], fait=True, ok=True), plan["actions"][1]])
            scripts = {"nc-apps": '#!/bin/sh\necho "[]"\n', "hyprctl": "#!/bin/sh\necho '[]'\n", "nc-aide-config": "#!/bin/sh\nexit 0\n",
                       "nc-demander": '#!/bin/sh\necho \'{"nom": "Claude Code", "agent": "claude", "coupee": false}\'\n',
                       "nc-ia": "#!/bin/sh\necho \"nc-ia $*\" >> \"$HOME/appels\"\ncase \"$1\" in agir) echo '" + json.dumps(plan) + "' ;; executer) echo '" + json.dumps(fait) + "' ;; esac\n"}
            for nom, code in scripts.items():
                (b / nom).write_text(code); (b / nom).chmod(0o755)
            (q / "shell.qml").write_text('''import QtQuick
import Quickshell
ShellRoot {
 property int etape: 0
 function trouver(item,nom){if(item.objectName===nom)return item;for(var i=0;i<item.children.length;i++){var r=trouver(item.children[i],nom);if(r)return r}return null}
 function verifier(ok,message){if(!ok){console.error(message);Qt.exit(2);throw new Error(message)}}
 function titres(){ return spot.resultats.map(x => x.titre) }
 FloatingWindow { visible: true; implicitWidth: 700; implicitHeight: 500
  Recherche { id: spot; width: 700; actif: true } }
 Timer { interval: 100; running: true; repeat: true; onTriggered: {
  var champ = trouver(spot, "nc-spotlight-champ")
  if (etape === 0) { if (spot.nomIA === "") return; champ.text = "@ coupe le bluetooth"; etape++; return }
  if (etape === 1) { verifier(spot.resultats[0].titre === "coupe le bluetooth", JSON.stringify(titres())); spot.valider(0, false); etape++; return }
  if (etape === 2) { if (spot.reflechit || !spot.plan) return
   verifier(spot.reponse === "Je coupe le Bluetooth.", "réponse : " + spot.reponse)
   verifier(JSON.stringify(titres()) === JSON.stringify(["Tout faire", "Bluetooth : off", "Arrêter nc-pouls.service"]), "plan : " + JSON.stringify(titres()))
   verifier(spot.resultats[2].sous.indexOf("⚠") === 0, "action risquée signalée")
   spot.valider(1, false); verifier(Etat.fermetures === 0, "le Spotlight reste ouvert"); etape++; return }
  if (etape === 3) { if (spot.plan.actions[0].fait !== true) return
   verifier(JSON.stringify(titres()) === JSON.stringify(["✓ Bluetooth : off", "Arrêter nc-pouls.service"]), "après : " + JSON.stringify(titres()))
   Qt.quit() }
 } }
 Timer { interval: 12000; running: true; onTriggered: Qt.exit(9) }
}''')
            env = dict(os.environ, HOME=d, QT_QPA_PLATFORM="offscreen", QT_QUICK_BACKEND="software", XDG_RUNTIME_DIR=str(root / "runtime"),
                       XDG_CACHE_HOME=str(root / "cache"), PATH=str(b) + os.pathsep + os.environ["PATH"])
            env.pop("WAYLAND_DISPLAY", None)
            r = subprocess.run(["qs", "--no-color", "-p", str(q / "shell.qml")], env=env, text=True, capture_output=True, timeout=20)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            appels = (root / "appels").read_text().splitlines()
            self.assertEqual(appels, ["nc-ia agir --json coupe le bluetooth", "nc-ia executer 0123456789abcdef 0 --json"])


if __name__ == "__main__":
    unittest.main()

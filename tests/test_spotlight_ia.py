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
            noms = ["Reglages", "Etat", "AssistantEtat", "Couleurs", "Connexion", "Recherche", "Emoji", "Partage", "Diagnostic", "Etincelle", "Texte", "Ico"]
            (q / "Partage.qml").write_text('pragma Singleton\nimport QtQuick\nQtObject { property bool silence: false }')
            (q / "qmldir").write_text("\n".join(("singleton " if n in ("Reglages", "Etat", "AssistantEtat", "Couleurs", "Connexion", "Partage") else "") + n + " 1.0 " + n + ".qml" for n in noms))
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
   // Plan de rangement en zones, « me montrer le plan d'abord » : une mini-carte de l'écran (IDÉE-2)
   champ.text = "@ range"; spot.questionPosee = "@ range"; spot.modeAgent = true; spot.reponse = "Plan prêt."
   spot.plan = { actions: [ { n: 1, outil: "fenetre_zone", libelle: "code : 60 × 100 %", fait: false, args: { x: "0", y: "0", largeur: "60", hauteur: "100" } },
                            { n: 2, outil: "fenetre_zone", libelle: "firefox : 40 × 100 %", fait: false, args: { x: "60", y: "0", largeur: "40", hauteur: "100" } } ], refus: [] }
   etape++; return }
  if (etape === 7) {
   var carte = trouver(spot, "nc-spotlight-mini-carte")
   verifier(carte && carte.visible, "mini-carte affichée")
   var zones = carte.children.filter(c => c.width > 4 && c.height > 4)
   verifier(zones.length === 2, "deux zones : " + zones.length)
   verifier(Math.abs(zones[0].width / carte.width - 0.6) < 0.05 && zones[1].x > zones[0].x, "proportions de l'écran")
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


    def test_reponse_en_echec_jamais_copiee(self):
        """Revue B2-08 : une réponse en échec (ligne {"erreur": true}, ou code de sortie ≠ 0) était ajoutée au texte et
        proposée à « Copier le résultat » (ou comme commande à lancer) : l'erreur est dite à part, rien à copier."""
        with tempfile.TemporaryDirectory(prefix="nc-spotlight-echec-") as d:
            root = Path(d); shutil.copytree(QML, root / "qml"); (root / "runtime").mkdir(mode=0o700)
            q = root / "qml"
            (q / "Reglages.qml").write_text('pragma Singleton\nimport QtQuick\nQtObject {property var v: ({}); readonly property bool iaCoupee: false\n'
                                            ' function t(fr,en){return fr} function val(k,d){return v[k] !== undefined ? v[k] : d} function pageActive(n){return true}}')
            (q / "Etat.qml").write_text('pragma Singleton\nimport QtQuick\nimport Quickshell\nQtObject {property string saisie: ""; property string texteIA: ""; property bool recherche: true\n'
                                        ' property bool nuit: false; readonly property string bin: Quickshell.env("HOME") + "/.local/bin/"; property int fermetures: 0; signal validerRecherche()\n'
                                        ' function faire(c) {} function fermer() { fermetures++ } function aller(p) {} function basculer(e, c) {}}')
            (q / "AssistantEtat.qml").write_text('pragma Singleton\nimport QtQuick\nQtObject {function formater(t){return t}}')
            (q / "Etincelle.qml").write_text('import QtQuick\nItem {property real taille: 10; property bool tourne: false; property string agent: ""}')
            noms = ["Reglages", "Etat", "AssistantEtat", "Couleurs", "Connexion", "Recherche", "Emoji", "Partage", "Diagnostic", "Etincelle", "Texte", "Ico"]
            (q / "Partage.qml").write_text('pragma Singleton\nimport QtQuick\nQtObject { property bool silence: false }')
            (q / "qmldir").write_text("\n".join(("singleton " if n in ("Reglages", "Etat", "AssistantEtat", "Couleurs", "Connexion", "Partage") else "") + n + " 1.0 " + n + ".qml" for n in noms))
            b = root / ".local/bin"; b.mkdir(parents=True)
            scripts = {
                "nc-apps": '#!/bin/sh\necho "[]"\n', "hyprctl": "#!/bin/sh\necho '[]'\n", "nc-aide-config": "#!/bin/sh\nexit 0\n",
                "nc-demander": '''#!/bin/sh
case "$1" in
  --ia) echo '{"nom": "Codex", "agent": "codex", "coupee": false}' ;;
  --flux) echo '{"t": "Début de réponse"}'; echo '{"t": "\\n$ rm -rf ~/projet"}'; exit 1 ;;
esac
''',
                # traduire : un début puis une ligne d'erreur ; résumer : un début puis un code d'erreur, sans ligne d'erreur
                "nc-ia": '''#!/bin/sh
echo "nc-ia $*" >> "$HOME/appels"
echo '{"ia": "Codex", "id": "codex", "agent": "codex"}'
echo '{"t": "Texte à moitié"}'
case "$2" in
  traduire) echo '{"t": "Codex a échoué (code 2)", "erreur": true}'; exit 1 ;;
  *) exit 9 ;;
esac
''',
                "wl-copy": '#!/bin/sh\necho "wl-copy $*" >> "$HOME/appels"\n',
            }
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
  if (etape === 0) { if (spot.nomIA === "") return; champ.text = "! traduire"; etape++; return }
  if (etape === 1) { verifier(titres()[0] === "Traduire", JSON.stringify(titres())); spot.valider(0, false); etape++; return }
  if (etape === 2) { if (spot.reflechit) return
   verifier(titres().indexOf("Copier le résultat") < 0, "ligne d'erreur : rien à copier : " + JSON.stringify(titres()))
   verifier(titres()[0] === "Codex a échoué (code 2)", "l'erreur est dite : " + JSON.stringify(titres()))
   verifier(spot.reponse.indexOf("Texte à moitié") === 0 && spot.reponse.indexOf("Codex a échoué") > 0, "réponse : " + spot.reponse)
   spot.valider(0, false); verifier(Etat.fermetures === 0, "Entrée sur l'erreur ne ferme rien")
   champ.text = "! résumer"; etape++; return }
  if (etape === 3) { verifier(titres()[0] === "Résumer", JSON.stringify(titres())); spot.valider(0, false); etape++; return }
  if (etape === 4) { if (spot.reflechit) return
   verifier(titres().indexOf("Copier le résultat") < 0, "code ≠ 0 : rien à copier : " + JSON.stringify(titres()))
   verifier(titres()[0].indexOf("code 9") >= 0, "le code est dit : " + JSON.stringify(titres()))
   champ.text = "? supprimer le projet"; spot.valider(spot.resultats.length - 1, false); etape++; return }
  if (etape === 5) { if (spot.reflechit || spot.reponse === "") return
   verifier(spot.commandeIA === "" && titres().indexOf("rm -rf ~/projet") < 0, "réponse en échec : aucune commande proposée : " + JSON.stringify(titres()))
   verifier(spot.reponse.indexOf("échoué (code 1)") > 0, "l'échec est dit : " + spot.reponse)
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
            for erreur in ("ReferenceError", "TypeError"):
                self.assertNotIn(erreur, sortie)
            self.assertNotIn("wl-copy", (root / "appels").read_text())

    def test_choix_de_jarvis_en_resultats(self):
        """Issue #7 : les choix d'une réponse de JARVIS (ligne {"choices": …} du flux) deviennent des résultats (chevron),
        choisis au clavier comme les autres ; Entrée envoie le libellé comme question suivante ; sans choix, aucun."""
        with tempfile.TemporaryDirectory(prefix="nc-spotlight-choix-") as d:
            root = Path(d); shutil.copytree(QML, root / "qml"); (root / "runtime").mkdir(mode=0o700)
            q = root / "qml"
            (q / "Reglages.qml").write_text('pragma Singleton\nimport QtQuick\nQtObject {property var v: ({}); readonly property bool iaCoupee: false\n'
                                            ' function t(fr,en){return fr} function val(k,d){return v[k] !== undefined ? v[k] : d} function pageActive(n){return true}}')
            (q / "Etat.qml").write_text('pragma Singleton\nimport QtQuick\nimport Quickshell\nQtObject {property string saisie: ""; property string texteIA: ""; property bool recherche: true\n'
                                        ' readonly property string bin: Quickshell.env("HOME") + "/.local/bin/"; property int fermetures: 0; signal validerRecherche()\n'
                                        ' function faire(c) {} function fermer() { fermetures++ } function aller(p) {}}')
            (q / "AssistantEtat.qml").write_text('pragma Singleton\nimport QtQuick\nQtObject {function formater(t){return t}}')
            (q / "Etincelle.qml").write_text('import QtQuick\nItem {property real taille: 10; property bool tourne: false; property string agent: ""}')
            noms = ["Reglages", "Etat", "AssistantEtat", "Couleurs", "Connexion", "Recherche", "Emoji", "Partage", "Diagnostic", "Etincelle", "Texte", "Ico"]
            (q / "Partage.qml").write_text('pragma Singleton\nimport QtQuick\nQtObject { property bool silence: false }')
            (q / "qmldir").write_text("\n".join(("singleton " if n in ("Reglages", "Etat", "AssistantEtat", "Couleurs", "Connexion", "Partage") else "") + n + " 1.0 " + n + ".qml" for n in noms))
            b = root / ".local/bin"; b.mkdir(parents=True)
            scripts = {"nc-apps": '#!/bin/sh\necho "[]"\n', "hyprctl": "#!/bin/sh\necho '[]'\n", "nc-aide-config": "#!/bin/sh\nexit 0\n",
                       "nc-demander": '''#!/bin/sh
echo "nc-demander $*" >> "$HOME/appels"
case "$1" in
  --ia) echo '{"nom": "JARVIS", "agent": "assistant", "coupee": false}' ;;
  --flux) echo '{"ia": "JARVIS", "id": "jarvis", "agent": "assistant"}'
    if [ "$2" = "quelle couleur" ]; then echo '{"t": "Laquelle ?"}'; echo '{"choices": ["Rouge", "Vert", "Bleu"]}'
    else echo '{"t": "Parfait."}'; fi ;;
esac
'''}
            for nom, code in scripts.items():
                (b / nom).write_text(code); (b / nom).chmod(0o755)
            (q / "shell.qml").write_text('''import QtQuick
import QtTest
import Quickshell
ShellRoot {
 property int etape: 0
 function trouver(item,nom){if(item.objectName===nom)return item;for(var i=0;i<item.children.length;i++){var r=trouver(item.children[i],nom);if(r)return r}return null}
 function verifier(ok,message){if(!ok){console.error(message);Qt.exit(2);throw new Error(message)}}
 function titres(){ return spot.resultats.map(x => x.titre) }
 function choix(){ return spot.resultats.filter(x => x.glyphe === "chevron_right").map(x => x.titre) }
 TestCase { id: clavier; name: "SpotlightChoix"; when: false }
 FloatingWindow { visible: true; implicitWidth: 700; implicitHeight: 500
  Recherche { id: spot; width: 700; actif: true } }
 Timer { interval: 100; running: true; repeat: true; onTriggered: {
  var champ = trouver(spot, "nc-spotlight-champ")
  if (etape === 0) { if (spot.nomIA === "") return; champ.text = "? quelle couleur"; spot.valider(spot.resultats.length - 1, false); etape++; return }
  if (etape === 1) { if (spot.reflechit) return
   verifier(spot.reponse === "Laquelle ?", "réponse : " + JSON.stringify(spot.reponse))
   verifier(JSON.stringify(choix()) === JSON.stringify(["Rouge", "Vert", "Bleu"]), "choix en résultats : " + JSON.stringify(titres()))
   var i = titres().indexOf("Vert"); verifier(spot.resultats[i].sous === "Répondre à JARVIS", "sous-titre : " + spot.resultats[i].sous)
   champ.forceActiveFocus(); verifier(spot.sel === 0, "sélection : " + spot.sel)
   for (var k = 0; k < i; k++) clavier.keyClick(Qt.Key_Down)
   verifier(spot.sel === i, "flèches : " + spot.sel)
   clavier.keyClick(Qt.Key_Return)
   verifier(Etat.fermetures === 0, "le Spotlight reste ouvert pour la réponse")
   verifier(champ.text === "? Vert" && spot.questionPosee === "Vert", "question suivante : " + champ.text)
   etape++; return }
  if (etape === 2) { if (spot.reflechit) return
   verifier(spot.reponse === "Parfait.", "seconde réponse : " + JSON.stringify(spot.reponse))
   verifier(choix().length === 0, "choix sous une réponse qui n'en a pas : " + JSON.stringify(titres()))
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
            appels = [l for l in (root / "appels").read_text().splitlines() if "--flux" in l]
            self.assertEqual(appels, ["nc-demander --flux quelle couleur", "nc-demander --flux Vert"])

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
            noms = ["Reglages", "Etat", "AssistantEtat", "Couleurs", "Connexion", "Recherche", "Emoji", "Partage", "Diagnostic", "Etincelle", "Texte", "Ico"]
            (q / "Partage.qml").write_text('pragma Singleton\nimport QtQuick\nQtObject { property bool silence: false }')
            (q / "qmldir").write_text("\n".join(("singleton " if n in ("Reglages", "Etat", "AssistantEtat", "Couleurs", "Connexion", "Partage") else "") + n + " 1.0 " + n + ".qml" for n in noms))
            b = root / ".local/bin"; b.mkdir(parents=True)
            plan = {"id": "0123456789abcdef", "reponse": "Je coupe le Bluetooth.", "ia": "Claude Code", "agent": "claude", "refus": [],
                    "actions": [{"n": 0, "libelle": "Bluetooth : off", "danger": False, "fait": False, "ok": None, "resultat": ""},
                                {"n": 1, "libelle": "Arrêter nc-pouls.service", "danger": True, "fait": False, "ok": None, "resultat": ""}]}
            fait = dict(plan, actions=[dict(plan["actions"][0], fait=True, ok=True), plan["actions"][1]])
            # Coupé en route : le plan gardé sur la sortie, l'erreur à part, code 3 (contre-relecture de B2)
            coupe = dict(plan, actions=[dict(a, fait=True, ok=True) for a in plan["actions"]])
            scripts = {"nc-apps": '#!/bin/sh\necho "[]"\n', "hyprctl": "#!/bin/sh\necho '[]'\n", "nc-aide-config": "#!/bin/sh\nexit 0\n",
                       "nc-demander": '#!/bin/sh\necho \'{"nom": "Claude Code", "agent": "claude", "coupee": false}\'\n',
                       "nc-ia": "#!/bin/sh\necho \"nc-ia $*\" >> \"$HOME/appels\"\ncase \"$1\" in agir) echo '" + json.dumps(plan) + "' ;; executer) sleep 0.5; case \"$3\" in 1) echo '" + json.dumps(coupe) + "'; echo \"L'IA est désactivée.\" >&2; exit 3 ;; esac; echo '" + json.dumps(fait) + "' ;; esac\n"}
            for nom, code in scripts.items():
                (b / nom).write_text(code); (b / nom).chmod(0o755)
            (q / "shell.qml").write_text('''import QtQuick
import Quickshell
ShellRoot {
 property int etape: 0
 property bool vuOccupe: false
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
  if (etape === 3) { if (spot.occupe) vuOccupe = true
   if (spot.plan.actions[0].fait !== true) return
   verifier(vuOccupe, "actions en cours : le Spotlight reste chargé même fermé (revue B2-01)")
   verifier(!spot.occupe, "plus rien en cours")
   verifier(JSON.stringify(titres()) === JSON.stringify(["✓ Bluetooth : off", "Arrêter nc-pouls.service"]), "après : " + JSON.stringify(titres()))
   spot.valider(1, false); etape++; return }
  if (etape === 4) { if (spot.occupe || spot.plan.actions[1].fait !== true) return
   verifier(JSON.stringify(titres()) === JSON.stringify(["✓ Bluetooth : off", "✓ Arrêter nc-pouls.service"]), "coupé en route : " + JSON.stringify(titres()))
   verifier(spot.reponse === "L'IA est désactivée.", "l'erreur est dite : " + spot.reponse)
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
            self.assertEqual(appels, ["nc-ia agir --json coupe le bluetooth", "nc-ia executer 0123456789abcdef 0 --json",
                                      "nc-ia executer 0123456789abcdef 1 --json"])


    # « Que se passe-t-il ? » : le bilan de nc-diag, l'explication de nc-ia, les réparations (fausses commandes, rien du vrai bureau)
    BILAN = {"version": 1, "langue": "fr", "duree_ms": 900, "ko": 2, "attention": 1, "ok": 40, "resume": "2 problèmes : noctalia arrêtée.",
             "constats": [
                 {"cle": "ile", "niveau": "avert", "section": "Bureau", "texte": "L'île est bloquée", "quoi": "", "reparations": ["redemarrer:nc-ile.service"]},
                 {"cle": "noctalia", "niveau": "faux", "section": "Bureau", "texte": "Noctalia est arrêtée", "quoi": "", "reparations": ["redemarrer:noctalia.service"]},
                 {"cle": "ia_conf", "niveau": "avert", "section": "IA", "texte": "ia.conf lisible par tous", "quoi": "", "reparations": ["ia_conf_prive"]},
                 {"cle": "hypr", "niveau": "faux", "section": "Hyprland", "texte": "Erreur dans hyprland.lua", "quoi": "ligne 12", "reparations": []}],
             "reparations": {"redemarrer:nc-ile.service": {"libelle": "Redémarrer l'île", "detail": "", "danger": True, "ferme_ile": True},
                             "redemarrer:noctalia.service": {"libelle": "Relancer Noctalia", "detail": "", "danger": False, "ferme_ile": False},
                             "ia_conf_prive": {"libelle": "Protéger ia.conf", "detail": "", "danger": False, "ferme_ile": False}}}

    def _diag(self, scenario, ia_mode="oui"):
        """Lance le Spotlight hors écran avec un faux nc-diag et un faux nc-ia ; renvoie (journal des appels, dossier)."""
        with tempfile.TemporaryDirectory(prefix="nc-spotlight-diag-") as d:
            root = Path(d); shutil.copytree(QML, root / "qml"); (root / "runtime").mkdir(mode=0o700)
            q = root / "qml"
            (q / "Reglages.qml").write_text('pragma Singleton\nimport QtQuick\nQtObject {property var v: ({IA_MODE: "' + ia_mode + '"}); readonly property bool iaCoupee: v.IA_MODE === "non"\n'
                                            ' function t(fr,en){return fr} function val(k,d){return v[k] !== undefined ? v[k] : d} function pageActive(n){return true}}')
            (q / "Etat.qml").write_text('pragma Singleton\nimport QtQuick\nimport Quickshell\nQtObject {property string saisie: ""; property string texteIA: ""; property bool recherche: true\n'
                                        ' readonly property string bin: Quickshell.env("HOME") + "/.local/bin/"; property int fermetures: 0; signal validerRecherche()\n'
                                        ' function faire(c) {} function fermer() { fermetures++ } function aller(p) {}}')
            (q / "AssistantEtat.qml").write_text('pragma Singleton\nimport QtQuick\nQtObject {function formater(t){return t}}')
            (q / "Etincelle.qml").write_text('import QtQuick\nItem {property real taille: 10; property bool tourne: false; property string agent: ""}')
            noms = ["Reglages", "Etat", "AssistantEtat", "Couleurs", "Connexion", "Recherche", "Emoji", "Partage", "Diagnostic", "Etincelle", "Texte", "Ico"]
            (q / "Partage.qml").write_text('pragma Singleton\nimport QtQuick\nQtObject { property bool silence: false }')
            (q / "qmldir").write_text("\n".join(("singleton " if n in ("Reglages", "Etat", "AssistantEtat", "Couleurs", "Connexion", "Partage") else "") + n + " 1.0 " + n + ".qml" for n in noms))
            b = root / ".local/bin"; b.mkdir(parents=True)
            (root / "bilan.json").write_text(json.dumps(self.BILAN))
            ia = {"source": "ia", "raison": "", "ia": "Claude Code", "agent": "claude", "resume": "Noctalia est arrêtée.", "conseil": "Relance-la d'abord.",
                  "reparations": ["redemarrer:nc-ile.service", "redemarrer:noctalia.service", "ia_conf_prive", "rm -rf /"], "refus": []}
            scripts = {
                "nc-apps": '#!/bin/sh\necho "[]"\n', "hyprctl": "#!/bin/sh\necho '[]'\n", "nc-aide-config": "#!/bin/sh\nexit 0\n",
                "nc-demander": '#!/bin/sh\necho \'{"nom": "Claude Code", "agent": "claude", "coupee": ' + ("true" if ia_mode == "non" else "false") + '}\'\n',
                "nc-diag": '#!/bin/sh\necho "nc-diag $*" >> "$HOME/appels"\ncase "$1" in\n reparer) sleep 0.4; printf \'{"id": "%s", "libelle": "x", "resultat": "fait", "ferme_ile": false, "texte": "ok"}\\n\' "$2" ;;\n'
                           ' *) sleep 0.3; cat "$HOME/bilan.json" ;;\nesac\n',
                "nc-ia": '#!/bin/sh\necho "nc-ia $*" >> "$HOME/appels"\ncat > "$HOME/stdin-ia"\nsleep 0.3\necho \'' + json.dumps(ia) + '\'\n'}
            for nom, code in scripts.items():
                (b / nom).write_text(code); (b / nom).chmod(0o755)
            (q / "shell.qml").write_text("""import QtQuick
import Quickshell
ShellRoot {
 property int etape: 0
 property bool vuOccupe: false
 property bool vuVerif: false
 property int cycles: 0
 function trouver(item,nom){if(item.objectName===nom)return item;for(var i=0;i<item.children.length;i++){var r=trouver(item.children[i],nom);if(r)return r}return null}
 function verifier(ok,message){if(!ok){console.error(message);Qt.exit(2);throw new Error(message)}}
 function titres(){ return spot.resultats.map(x => x.titre) }
 FloatingWindow { visible: true; implicitWidth: 700; implicitHeight: 500
  Recherche { id: spot; width: 700; actif: true } }
 Timer { interval: 100; running: true; repeat: true; onTriggered: {
  var champ = trouver(spot, "nc-spotlight-champ")
  if (etape === 0) { if (spot.nomIA === "") return; champ.text = "que se passe-t-il ?"; etape++; return }
""" + scenario + """
 } }
 Timer { interval: 14000; running: true; onTriggered: { console.error("délai : étape " + etape + " " + JSON.stringify(titres())); Qt.exit(9) } }
}""")
            env = dict(os.environ, HOME=d, QT_QPA_PLATFORM="offscreen", QT_QUICK_BACKEND="software", XDG_RUNTIME_DIR=str(root / "runtime"),
                       XDG_CACHE_HOME=str(root / "cache"), PATH=str(b) + os.pathsep + os.environ["PATH"])
            env.pop("WAYLAND_DISPLAY", None)
            r = subprocess.run(["qs", "--no-color", "-p", str(q / "shell.qml")], env=env, text=True, capture_output=True, timeout=25)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            fichier = root / "appels"
            appels = fichier.read_text().splitlines() if fichier.exists() else []
            ia_stdin = root / "stdin-ia"
            return appels, (ia_stdin.read_text() if ia_stdin.exists() else "")

    def test_diag_mots_cles_sans_entree_aucun_appel(self):
        # Les mots-clés montrent la ligne en tête ; sans Entrée ni clic, ni nc-diag ni nc-ia ne sont lancés
        scenario = r"""
  if (etape === 1) { verifier(spot.resultats.length > 0 && spot.resultats[0].titre === "Que se passe-t-il ?", "ligne : " + JSON.stringify(titres()))
   verifier(spot.resultats[0].glyphe === "monitor_heart", "glyphe"); champ.text = "ça marche plus"; etape++; return }
  if (etape === 2) { verifier(spot.resultats[0].titre === "Que se passe-t-il ?", "ça marche plus : " + JSON.stringify(titres())); champ.text = "?"; etape++; return }
  if (etape === 3) { verifier(spot.resultats[0].titre === "Que se passe-t-il ?", "? seul : " + JSON.stringify(titres())); champ.text = "what's wrong"; etape++; return }
  if (etape === 4) { verifier(spot.resultats[0].titre === "Que se passe-t-il ?", "what's wrong : " + JSON.stringify(titres())); cycles = 0; etape++; return }
  if (etape === 5) { if (++cycles < 15) return
   verifier(!spot.occupe, "rien en cours"); Qt.quit() }
"""
        appels, _ = self._diag(scenario)
        self.assertEqual(appels, [])

    def test_diag_bilan_ia_reparations_confirmees(self):
        # Entrée : nc-diag vérifie ; le bilan s'affiche, nc-ia l'explique (bilan sur l'entrée standard) ; une réparation seulement
        # sur Entrée, « Tout réparer » fait le reste, l'île (ferme_ile) en dernier ; occupe pendant une réparation
        scenario = r"""
  if (etape === 1) { spot.valider(0, false); etape++; return }
  if (etape === 2) { if (spot.resultats[0].titre === "Vérification du bureau…") vuVerif = true
   if (spot.resultats[0].titre === "Vérification du bureau…" || titres().indexOf("Voir le bilan complet") < 0) return
   if (trouver(spot, "nc-spotlight-reponse").visible !== true) return
   cycles++; if (cycles < 8) return
   verifier(vuVerif, "la vérification a été vue")
   verifier(JSON.stringify(titres()) === JSON.stringify(["Tout réparer", "Relancer Noctalia", "Protéger ia.conf", "Redémarrer l'île", "Erreur dans hyprland.lua", "Voir le bilan complet", "Copier le rapport"]), "bilan : " + JSON.stringify(titres()))
   verifier(spot.resultats[3].sous.indexOf("⚠ L'île se ferme") === 0, "l'île signalée")
   verifier(spot.resultats[1].sous === "À confirmer", "à confirmer : " + spot.resultats[1].sous)
   spot.valider(2, false); etape++; return }
  if (etape === 3) { if (spot.occupe) vuOccupe = true
   if (titres()[2] !== "✓ Protéger ia.conf" || spot.occupe) return
   verifier(spot.resultats[0].sous.indexOf("En cours") < 0, "lignes à jour : " + JSON.stringify(spot.resultats[0]))
   verifier(vuOccupe, "occupe pendant la réparation"); verifier(Etat.fermetures === 0, "le Spotlight reste ouvert")
   spot.valider(0, false); etape++; return }
  if (etape === 4) {
   if (titres()[0] !== "✓ Tout est réparé") return
   verifier(JSON.stringify(titres().slice(1, 4)) === JSON.stringify(["✓ Relancer Noctalia", "✓ Protéger ia.conf", "✓ Redémarrer l'île"]), "fin : " + JSON.stringify(titres()))
   Qt.quit() }
"""
        appels, ia_stdin = self._diag(scenario)
        self.assertEqual(appels, ["nc-diag --json --rapide", "nc-ia diagnostic --json -",
                                  "nc-diag reparer ia_conf_prive --json",
                                  "nc-diag reparer redemarrer:noctalia.service --json", "nc-diag reparer redemarrer:nc-ile.service --json"])
        self.assertEqual(json.loads(ia_stdin)["constats"][1]["cle"], "noctalia")

    def test_diag_ia_coupee_les_reparations_marchent(self):
        # IA_MODE=non : nc-ia n'est jamais lancé, le bilan de nc-diag et les réparations marchent quand même
        scenario = r"""
  if (etape === 1) { verifier(spot.resultats[0].titre === "Que se passe-t-il ?", "ligne : " + JSON.stringify(titres())); spot.valider(0, false); etape++; return }
  if (etape === 2) { if (titres().indexOf("Voir le bilan complet") < 0 || spot.occupe) return
   verifier(titres()[1] === "Relancer Noctalia", "bilan : " + JSON.stringify(titres())); spot.valider(1, false); etape++; return }
  if (etape === 3) { if (titres()[1] !== "✓ Relancer Noctalia") return; Qt.quit() }
"""
        appels, _ = self._diag(scenario, ia_mode="non")
        self.assertEqual(appels, ["nc-diag --json --rapide", "nc-diag reparer redemarrer:noctalia.service --json"])


class SpotlightSource(unittest.TestCase):
    """Lecture du source (pas besoin de Quickshell) : ce que le bilan (constats, sortie de systemctl) met à l'écran n'est
    jamais interprété comme du HTML, et l'icône de l'en-tête est celle de l'IA du bilan."""
    def test_lignes_en_texte_brut(self):
        src = (QML / "Recherche.qml").read_text()
        for champ in ("text: ligne.modelData.titre", "text: ligne.modelData.sous"):
            i = src.index(champ)
            bloc = src[src.rindex("Texte {", 0, i):i + len(champ)]
            self.assertIn("textFormat: Text.PlainText", bloc, champ)
        self.assertIn("textFormat: r.reponseAide !== \"\" || zoneReponse.enDiag ? Text.PlainText", src)

    def test_icone_du_bilan_est_celle_du_bilan(self):
        src = (QML / "Recherche.qml").read_text()
        self.assertIn("agent: zoneReponse.enDiag ? diag.agent : r.agentReponse", src)
        self.assertNotIn("zoneReponse.enDiag ? r.agentIA", src)


if __name__ == "__main__":
    unittest.main()

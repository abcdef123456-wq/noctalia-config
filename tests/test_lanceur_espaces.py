"""Lanceur de l'île (Recherche.qml) : trois espaces stricts, Applis, Fichiers et Actions, jamais mêlés. Joué hors écran
avec le vrai Recherche.qml et de faux nc-apps / qalc qui notent leurs appels : Tab (espaceSuivant) et les onglets changent
d'espace, un préfixe (? > + ; : mdp note…) mène aux Actions, un calcul aussi tant que l'espace n'est pas choisi à la main,
et nc-apps files n'est lancé que dans l'espace Fichiers."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

QML = Path(__file__).resolve().parents[1] / "home/.config/quickshell/nc-ile"
RECHERCHE = (QML / "Recherche.qml").read_text(encoding="utf-8")

SHELL = '''import QtQuick
import Quickshell
ShellRoot {
 property int etape: 0
 property int attente: 0
 function trouver(item,nom){if(item.objectName===nom)return item;for(var i=0;i<item.children.length;i++){var r=trouver(item.children[i],nom);if(r)return r}return null}
 function verifier(ok,message){if(!ok){console.error(message);Qt.exit(2);throw new Error(message)}}
 function titres(){ return spot.resultats.map(x => x.titre) }
 function seul(e){ return spot.resultats.every(x => (x.e || "actions") === e) }
 FloatingWindow { visible: true; implicitWidth: 438; implicitHeight: 600
  Recherche { id: spot; width: 438; height: 600; actif: true } }
 Timer { interval: 100; running: true; repeat: true; onTriggered: {
  var champ = trouver(spot, "nc-spotlight-champ")
  if (etape === 0) { if (!spot.applisLues) return
   verifier(spot.espace === "applis", "Applis à l'ouverture")
   champ.text = "fire"; etape++; return }
  if (etape === 1) {
   if (titres().indexOf("Firefox") < 0) { attente++; verifier(attente < 50, "Applis : " + JSON.stringify(titres())); return }
   attente++; if (attente < 8) return
   verifier(seul("applis"), "Applis seules : " + JSON.stringify(spot.resultats))
   verifier(spot.fichiers.length === 0, "nc-apps files jamais lancé dans Applis")
   verifier(trouver(spot, "nc-lanceur-compteur").text === spot.resultats.length + (spot.resultats.length > 1 ? " résultats" : " résultat"), "compteur")
   spot.espaceSuivant(1); attente = 0; etape++; return }
  if (etape === 2) {
   verifier(spot.espace === "fichiers" && spot.espaceManuel, "Tab : Fichiers")
   if (titres().indexOf("firefox-notes.txt") < 0) { attente++; verifier(attente < 50, "Fichiers : " + JSON.stringify(titres())); return }
   verifier(seul("fichiers") && titres().indexOf("Firefox") < 0, "Fichiers seuls : " + JSON.stringify(titres()))
   spot.espaceSuivant(1); attente = 0; etape++; return }
  if (etape === 3) {
   verifier(spot.espace === "actions", "Tab : Actions")
   verifier(seul("actions") && titres().indexOf("Firefox") < 0 && titres().indexOf("firefox-notes.txt") < 0, "Actions seules : " + JSON.stringify(titres()))
   spot.espaceSuivant(1); verifier(spot.espace === "applis", "Tab revient à Applis")
   spot.espaceSuivant(-1); verifier(spot.espace === "actions", "Maj + Tab : Actions")
   trouver(spot, "nc-lanceur-onglets").choisir("applis"); verifier(spot.espace === "applis" && seul("applis"), "clic sur l'onglet Applis")
   // Un préfixe mène aux Actions, même depuis un espace choisi à la main
   var prefixes = ["? test", "> ls", "+ gimp", "; mot", ":coeur", "mdp 20", "note acheter du pain", "g chat", "port 8080"]
   for (var i = 0; i < prefixes.length; i++) {
    spot.changerEspace("fichiers"); champ.text = prefixes[i]
    verifier(spot.espace === "actions", prefixes[i] + " : " + spot.espace)
    verifier(seul("actions"), prefixes[i] + " : rien d'autre que des actions")
   }
   // Un calcul sans appli qui lui correspond : Actions, sans rien choisir
   champ.text = ""; spot.espaceManuel = false; champ.text = "2+2"
   verifier(spot.espace === "applis", "calcul : Applis le temps que qalc réponde")
   attente = 0; etape++; return }
  if (etape === 4) {
   if (spot.espace !== "actions" || titres().indexOf("= 4") < 0) { attente++; verifier(attente < 50, "calcul : " + spot.espace + " " + JSON.stringify(titres())); return }
   verifier(seul("actions"), "calcul seul en Actions")
   // Espace choisi à la main : le calcul ne l'en sort pas
   spot.changerEspace("applis"); champ.text = "3+3"; attente = 0; etape++; return }
  if (etape === 5) {
   attente++; if (attente < 10) return
   verifier(spot.espace === "applis" && titres().indexOf("= 6") < 0, "manuel : reste en Applis : " + JSON.stringify(titres()))
   Qt.quit() }
 } }
 Timer { interval: 40000; running: true; onTriggered: Qt.exit(9) }
}'''

FAUX_APPS = r'''#!/bin/sh
printf '%s\n' "$*" >> "$HOME/appels"
case "$1" in
  list) printf '%s\n' '[{"id": "firefox", "name": "Firefox", "generic": "Navigateur", "icon": "", "exe": "firefox"}]' ;;
  files) printf '%s\n' '[{"name": "firefox-notes.txt", "path": "/home/user/firefox-notes.txt", "dir": false, "parent": "~"}]' ;;
  *) printf '%s\n' '[]' ;;
esac
'''
FAUX_QALC = r'''#!/bin/sh
case "$2" in
  2+2) echo 4 ;;
  3+3) echo 6 ;;
esac
'''


class Source(unittest.TestCase):
    def test_touches_et_composants(self):
        self.assertIn("Keys.onTabPressed: r.espaceSuivant(1)", RECHERCHE)
        self.assertIn("Keys.onBacktabPressed: r.espaceSuivant(-1)", RECHERCHE)
        self.assertIn('r.espace === "fichiers" && q.length >= 3', RECHERCHE)
        self.assertIn('out = out.filter(x => (x.e || "actions") === espace)', RECHERCHE)
        for nom in ("LanceurOnglets", "LanceurLigne", "LanceurPied"):
            self.assertTrue((QML / (nom + ".qml")).exists(), nom)
            self.assertIn(nom + " {", RECHERCHE)


@unittest.skipUnless(shutil.which("qs"), "Quickshell absent")
class EspacesHorsEcran(unittest.TestCase):
    def test_trois_espaces_jamais_meles(self):
        with tempfile.TemporaryDirectory(prefix="ncl-") as d:
            root = Path(d)
            q = root / "qml"
            shutil.copytree(QML, q)
            for sous in ("run", "cache", "state", "data", "config", "tmp"):
                (root / sous).mkdir(mode=0o700)
            (q / "Reglages.qml").write_text('pragma Singleton\nimport QtQuick\nQtObject {\n property var v: ({})\n readonly property bool iaCoupee: true\n'
                                            ' readonly property bool sobre: true\n readonly property bool en: false\n function t(fr,en){return fr}\n'
                                            ' function val(k,d){return v[k] !== undefined ? v[k] : d}\n function pageActive(n){return true}\n}')
            (q / "Etat.qml").write_text('pragma Singleton\nimport QtQuick\nimport Quickshell\nQtObject {\n property string saisie: ""\n property string texteIA: ""\n'
                                        ' property bool recherche: true\n property bool nuit: false\n readonly property string bin: Quickshell.env("HOME") + "/.local/bin/"\n'
                                        ' signal validerRecherche()\n function faire(c) {} function fermer() {} function aller(p) {} function basculer(e, c) {}\n}')
            (q / "Partage.qml").write_text('pragma Singleton\nimport QtQuick\nQtObject { property bool silence: false }')
            (q / "AssistantEtat.qml").write_text('pragma Singleton\nimport QtQuick\nQtObject {function formater(t){return t} function sansReseau(t){return t}}')
            (q / "Etincelle.qml").write_text('import QtQuick\nItem {property real taille: 10; property bool tourne: false; property string agent: ""}')
            (q / "CloudEtat.qml").write_text('pragma Singleton\nimport QtQuick\nQtObject { property bool actif: false; property bool associe: false }')
            (q / "Rappels.qml").write_text('pragma Singleton\nimport QtQuick\nQtObject { property var liste: []; property bool plein: false; function analyser(p) '
                                           '{ return {ok: false, raison: "heure"} } function quand(d) { return "" } function creer(t, d) { return false } function supprimer(i) {} }')
            singletons = ("Reglages", "Etat", "Partage", "AssistantEtat", "Couleurs", "Connexion")
            noms = list(singletons) + ["Recherche", "LanceurOnglets", "LanceurLigne", "LanceurPied", "Emoji", "Diagnostic", "Etincelle", "Texte", "Ico"]
            (q / "qmldir").write_text("\n".join(("singleton " if n in singletons else "") + n + " 1.0 " + n + ".qml" for n in noms)
                                      + "\nsingleton CloudEtat 1.0 CloudEtat.qml\nsingleton Rappels 1.0 Rappels.qml")
            b = root / ".local/bin"
            b.mkdir(parents=True)
            scripts = {"nc-apps": FAUX_APPS, "qalc": FAUX_QALC, "hyprctl": "#!/bin/sh\nprintf '%s\\n' '[]'\n", "nc-aide-config": "#!/bin/sh\nexit 0\n",
                       "nc-demander": '#!/bin/sh\ncase "$1" in --ia) printf \'%s\\n\' \'{"nom": "-", "agent": "claude", "coupee": true}\' ;; esac\n',
                       "nc-logiciels": "#!/bin/sh\nprintf '%s\\n' '[]'\n", "nc-processus": "#!/bin/sh\nprintf '%s\\n' '{\"ss\": true, \"lignes\": []}'\n"}
            for nom, code in scripts.items():
                (b / nom).write_text(code)
                (b / nom).chmod(0o755)
            (q / "shell.qml").write_text(SHELL)
            env = dict(os.environ, HOME=d, XDG_CONFIG_HOME=str(root / "config"), XDG_CACHE_HOME=str(root / "cache"),
                       XDG_STATE_HOME=str(root / "state"), XDG_DATA_HOME=str(root / "data"), XDG_RUNTIME_DIR=str(root / "run"),
                       TMPDIR=str(root / "tmp"), QT_QPA_PLATFORM="offscreen", QT_QUICK_BACKEND="software",
                       PATH=str(b) + os.pathsep + os.environ["PATH"])
            for k in ("WAYLAND_DISPLAY", "HYPRLAND_INSTANCE_SIGNATURE", "DISPLAY"):
                env.pop(k, None)
            r = subprocess.run(["qs", "--no-color", "-p", str(q / "shell.qml")], env=env, text=True, capture_output=True, timeout=70,
                               stdin=subprocess.DEVNULL)
            sortie = r.stdout + r.stderr
            self.assertEqual(r.returncode, 0, sortie)
            for erreur in ("ReferenceError", "TypeError", "is not a type", "Binding loop"):
                self.assertNotIn(erreur, sortie)
            appels = (root / "appels").read_text(encoding="utf-8").splitlines()
            # nc-apps files : seulement pour « fire », une fois dans l'espace Fichiers ; jamais pour un préfixe ni un calcul
            self.assertEqual([a for a in appels if a.startswith("files")], ["files fire"], appels)


if __name__ == "__main__":
    unittest.main()

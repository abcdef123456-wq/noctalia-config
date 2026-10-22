"""nc-session : enregistrer la disposition (applis, bureaux, places des fenêtres libres, terminaux), la rouvrir (une
appli déjà ouverte va sur son bureau, une absente est lancée puis placée quand sa fenêtre apparaît), et le Spotlight
(« session NOM »). Et nc-reglages, section Fenêtres : les sessions enregistrées, chacune supprimable après confirmation."""
import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import tempfile
import time
import unittest
from unittest import mock
import warnings

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "home/.local/bin/nc-session"
QML = REPO / "home/.config/quickshell/nc-ile"

FAUX_HYPRCTL = r'''#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
H = Path(os.environ["HOME"])
if sys.argv[1:3] == ["clients", "-j"]:
    print((H / "clients.json").read_text())
elif sys.argv[1] in ("dispatch", "eval"):
    with (H / "appels").open("a") as f: f.write(sys.argv[1] + " " + sys.argv[2] + "\n")
'''
# Faux nc-apps : la liste des applis ; « launch » ajoute la fenêtre de l'appli (comme si elle s'ouvrait)
FAUX_APPS = r'''#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
H = Path(os.environ["HOME"])
if sys.argv[1] == "list":
    print(json.dumps([{"id": "firefox", "wmclass": "firefox"}, {"id": "discord", "wmclass": "discord"}]))
elif sys.argv[1] == "launch":
    with (H / "appels").open("a") as f: f.write("launch " + sys.argv[2] + "\n")
    def ajouter(adresse, titre):
        c = [x for x in json.loads((H / "clients.json").read_text()) if x["address"] != "0xmaj"]
        c.append({"address": adresse, "class": sys.argv[2], "title": titre, "mapped": True, "workspace": {"id": 1},
                  "floating": False, "at": [0, 0], "size": [800, 600], "pid": 1})
        (H / "clients.json").write_text(json.dumps(c))
    if sys.argv[2] == "discord":
        ajouter("0xmaj", "Discord Updater")            # l'écran de mise à jour, puis la vraie fenêtre
        if os.fork() == 0:
            import time; time.sleep(1); ajouter("0xnouveau", "Discord"); os._exit(0)
    else:
        ajouter("0xnouveau", sys.argv[2])
'''


def client(adresse, classe, bureau, flottant=False, at=(0, 0), taille=(800, 600), titre=None, pid=1):
    return {"address": adresse, "class": classe, "title": titre or classe, "mapped": True, "workspace": {"id": bureau},
            "monitor": 0, "floating": flottant, "at": list(at), "size": list(taille), "fullscreen": 0, "pid": pid}


class Sessions(unittest.TestCase):
    def setUp(self):
        d = tempfile.TemporaryDirectory(prefix="nc-session-")
        self.addCleanup(d.cleanup)
        self.home = Path(d.name)
        b = self.home / ".local/bin"
        b.mkdir(parents=True)
        for nom, code in (("hyprctl", FAUX_HYPRCTL), ("nc-apps", FAUX_APPS)):
            (b / nom).write_text(code); (b / nom).chmod(0o755)
        for nom in ("notify-send", "kitty"):
            (b / nom).write_text('#!/bin/sh\necho "' + nom + ' $*" >> "$HOME/appels"\n'); (b / nom).chmod(0o755)

    def clients(self, *c):
        (self.home / "clients.json").write_text(json.dumps(list(c)))

    def lancer(self, *a):
        env = dict(HOME=str(self.home), PATH=str(self.home / ".local/bin") + ":/usr/bin:/bin", NC_LANGUE="fr", NC_SESSION_DELAI="4", NC_SESSION_CALME="1.5",
                   XDG_RUNTIME_DIR=str(self.home))
        return subprocess.run([str(SCRIPT), *a], env=env, capture_output=True, text=True, timeout=30)

    def appels(self):
        f = self.home / "appels"
        return f.read_text() if f.exists() else ""

    def test_enregistrer_puis_rouvrir(self):
        self.clients(client("0xa", "firefox", 2), client("0xb", "discord", 3, flottant=True, at=(100, 200), taille=(640, 480)),
                     client("0xc", "kitty", 1, pid=999999), client("0xd", "dropterm", -98), client("0xe", "org.quickshell", 1, titre="JARVIS"))
        r = self.lancer("enregistrer", "Dev")
        self.assertEqual(r.returncode, 0, r.stderr)
        s = json.loads((self.home / ".config/nc/sessions/Dev.json").read_text())
        self.assertEqual([(f["classe"], f["bureau"]) for f in s["fenetres"]], [("kitty", 1), ("firefox", 2), ("discord", 3)],
                         "ni le terminal déroulant, ni les fenêtres du bureau")
        self.assertEqual(s["fenetres"][1]["appli"], "firefox")
        self.assertIn("terminal", s["fenetres"][0])
        # Rouvrir : Firefox déjà là (sur le bureau 5) y retourne ; Discord absent est lancé puis placé ; un terminal est rouvert
        (self.home / "appels").unlink()
        self.clients(client("0xf", "firefox", 5))
        r = self.lancer("ouvrir", "Dev")
        self.assertEqual(r.returncode, 0, r.stderr)
        a = self.appels()
        self.assertIn("dispatch hl.dsp.window.move({ workspace = 2, follow = false, window = 'address:0xf' })", a)
        self.assertIn("launch discord", a)
        self.assertNotIn("launch firefox", a, "pas de seconde fenêtre pour une appli déjà ouverte")
        self.assertIn("dispatch hl.dsp.window.move({ workspace = 3, follow = false, window = 'address:0xnouveau' })", a)
        self.assertIn("hl.dsp.window.float({ action = 'set', window = 'address:0xnouveau' })", a)
        self.assertIn("hl.dsp.window.resize({ x = 640, y = 480, window = 'address:0xnouveau' })", a)
        self.assertIn("kitty --directory", a)
        # La fenêtre de mise à jour de Discord, puis la vraie : toutes deux sur le bureau 3 ; la règle temporaire posée puis retirée
        self.assertIn("dispatch hl.dsp.window.move({ workspace = 3, follow = false, window = 'address:0xmaj' })", a)
        import re
        self.assertIn("eval hl.window_rule({ name = 'nc-session-1', enabled = true, match = { class = [[^(discord)$]] }, workspace = '3 silent' })", a)
        self.assertIn("eval hl.window_rule({ name = 'nc-session-1', enabled = false,", a)
        self.assertFalse((self.home / "nc-session-regles.json").exists(), "plus rien à retirer après une ouverture finie")
        self.assertLess(a.index("enabled = true"), a.index("launch discord"), "la règle avant le lancement")
        l = json.loads(self.lancer("liste", "--json").stdout)
        self.assertEqual((l[0]["nom"], l[0]["fenetres"]), ("Dev", 3))

    def test_regles_retirees_meme_si_le_lancement_echoue(self):
        """Revue SESSION-01 : une erreur de lancement laissait la règle temporaire active (toute fenêtre de l'appli
        partait ensuite sur son bureau)."""
        self.clients(client("0xb", "discord", 3))
        self.assertEqual(self.lancer("enregistrer", "Jeu").returncode, 0)
        self.clients()
        (self.home / ".local/bin/nc-apps").write_text("#!/bin/sh\n[ \"$1\" = list ] && echo '[]' || exit 1\n")
        os.remove(self.home / ".local/bin/kitty")
        # nc-apps en échec, et plus aucun moyen de lancer : l'ouverture échoue, la règle est quand même retirée
        r = self.lancer("ouvrir", "Jeu")
        a = self.appels()
        self.assertIn("enabled = true", a, r.stderr)
        self.assertIn("enabled = false", a, "règle retirée malgré l'échec")

    def test_regles_retirees_si_l_ouverture_est_arretee(self):
        """Revue SESSION-02 : un nc-session arrêté (SIGTERM : île relancée, fin de session) pendant l'attente des
        fenêtres laissait sa règle active pour toujours ; tué net (SIGKILL), l'ouverture suivante la retire."""
        self.clients(client("0xb", "discord", 3))
        self.assertEqual(self.lancer("enregistrer", "Jeu").returncode, 0)
        self.clients()
        (self.home / ".local/bin/nc-apps").write_text("#!/bin/sh\n[ \"$1\" = list ] && echo '[]'\nexit 0\n")   # la fenêtre ne vient jamais
        env = dict(HOME=str(self.home), PATH=str(self.home / ".local/bin") + ":/usr/bin:/bin", NC_LANGUE="fr",
                   NC_SESSION_DELAI="20", XDG_RUNTIME_DIR=str(self.home))
        for sig in (signal.SIGTERM, signal.SIGKILL):
            (self.home / "appels").unlink(missing_ok=True)
            p = subprocess.Popen([str(SCRIPT), "ouvrir", "Jeu"], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            for _ in range(100):
                if "enabled = true" in self.appels():
                    break
                time.sleep(0.05)
            p.send_signal(sig)
            self.assertEqual(p.wait(timeout=10), 143 if sig == signal.SIGTERM else -9)
            a = self.appels()
            self.assertIn("name = 'nc-session-0', enabled = true", a)
            if sig == signal.SIGTERM:
                self.assertIn("name = 'nc-session-0', enabled = false", a, "retirée à l'arrêt")
            else:
                self.assertNotIn("enabled = false", a)
        # Après le SIGKILL : la suivante retire l'orpheline avant toute chose
        (self.home / "appels").unlink()
        self.clients(client("0xb", "discord", 3))
        self.assertEqual(self.lancer("ouvrir", "Jeu").returncode, 0)
        a = self.appels()
        self.assertTrue(a.startswith("eval hl.window_rule({ name = 'nc-session-0', enabled = false,"), a[:200])
        self.assertFalse((self.home / "nc-session-regles.json").exists())

    def test_terminal_deja_ouvert_et_plein_ecran(self):
        dossier = self.home / "projet"; dossier.mkdir()
        shell = subprocess.Popen(["sh", "-c", f"cd {dossier} && sleep 30 & wait"])     # un « terminal » dont le shell est dans le dossier
        self.addCleanup(shell.kill)
        import time; time.sleep(0.3)
        (self.home / ".config/nc/sessions").mkdir(parents=True)
        (self.home / ".config/nc/sessions/T.json").write_text(json.dumps({"version": 1, "nom": "T", "fenetres": [
            {"classe": "kitty", "bureau": 4, "flottant": False, "plein_ecran": 2,
             "terminal": {"programme": "kitty", "dossier": str(dossier), "commande": None}}]}))
        self.clients(client("0xk", "kitty", 1, pid=shell.pid))
        self.lancer("ouvrir", "T")
        a = self.appels()
        self.assertNotIn("kitty --directory", a, "pas de second terminal dans le même dossier")
        self.assertIn("dispatch hl.dsp.window.move({ workspace = 4, follow = false, window = 'address:0xk' })", a)
        self.assertIn("hl.dsp.window.fullscreen({ action = 'set', mode = 'fullscreen', window = 'address:0xk' })", a)

    def test_pas_de_script_rejoue_et_fichier_prive(self):
        """Revues SESS-01 et SESS-02 : un terminal qui faisait tourner « python3 migrer.py --oui » le relançait à chaque
        ouverture de la session ; et la session (titres, lignes de commande) était lisible par tous (0644)."""
        import importlib.machinery, importlib.util
        from unittest import mock
        l = importlib.machinery.SourceFileLoader("ncsession", str(SCRIPT))
        m = importlib.util.module_from_spec(importlib.util.spec_from_loader("ncsession", l)); l.exec_module(m)
        cas = {("python3", "migrer.py", "--oui"): None, ("python3",): ["python3"], ("/usr/bin/python3", "-q"): ["python3", "-q"],
               ("python3", "-m", "http.server"): None, ("node", "deploiement.js"): None, ("node",): ["node"],
               ("nvim", "notes.md"): ["nvim", "notes.md"], ("ssh", "serveur"): ["ssh", "serveur"],
               ("mysql", "--password=zzz"): None, ("nvim", "auth.lua"): ["nvim", "auth.lua"],
               ("ssh", "author@hote"): ["ssh", "author@hote"], ("ssh", "--auth=x", "h"): None}
        for cmd, attendu in cas.items():
            m.INTERACTIFS.add("mysql")
            with mock.patch.object(m, "enfants", lambda pid: [pid + 1]), \
                    mock.patch.object(m, "ligne_commande", lambda pid, c=cmd: list(c)), mock.patch("os.readlink", lambda x: "/projet"):
                self.assertEqual(m.terminal(1), ("/projet", attendu), cmd)
        # Une fenêtre sans fichier .desktop dont la commande porte un jeton : seulement le programme
        p = subprocess.Popen(["sh", "-c", "sleep 30; :", "--token=zzz"])
        self.addCleanup(p.kill)
        self.clients(client("0xa", "monappli", 2, pid=p.pid))
        self.assertEqual(self.lancer("enregistrer", "Privee").returncode, 0)
        f = self.home / ".config/nc/sessions/Privee.json"
        self.assertEqual(json.loads(f.read_text())["fenetres"][0]["commande"], ["sh"])
        self.assertEqual(f.stat().st_mode & 0o777, 0o600)
        self.assertEqual(f.parent.stat().st_mode & 0o777, 0o700)

    def test_noms_refuses(self):
        self.clients(client("0xa", "firefox", 2))
        for nom in ("../evil", "", "a/b"):
            self.assertNotEqual(self.lancer("enregistrer", nom).returncode, 0)
        self.assertFalse((self.home / ".config/nc/sessions").exists() and list((self.home / ".config/nc/sessions").glob("*.json")))


@unittest.skipUnless(shutil.which("qs"), "Quickshell requis")
class SpotlightSessions(unittest.TestCase):
    def test_session_nom(self):
        with tempfile.TemporaryDirectory(prefix="nc-spotlight-sessions-") as d:
            root = Path(d); shutil.copytree(QML, root / "qml"); (root / "runtime").mkdir(mode=0o700)
            q = root / "qml"
            (q / "Reglages.qml").write_text('pragma Singleton\nimport QtQuick\nQtObject {readonly property bool iaCoupee: false; function t(fr,en){return fr} function val(k,d){return d} function pageActive(n){return true}}')
            (q / "Etat.qml").write_text('pragma Singleton\nimport QtQuick\nimport Quickshell\nQtObject {property string saisie: ""; property string texteIA: ""; property bool recherche: true\n'
                                        ' readonly property string bin: Quickshell.env("HOME") + "/.local/bin/"; property int fermetures: 0; signal validerRecherche()\n'
                                        ' function faire(c) {} function fermer() { fermetures++ } function aller(p) {}}')
            (q / "AssistantEtat.qml").write_text('pragma Singleton\nimport QtQuick\nQtObject {function formater(t){return t}}')
            (q / "Etincelle.qml").write_text('import QtQuick\nItem {property real taille: 10; property bool tourne: false; property string agent: ""}')
            noms = ["Reglages", "Etat", "AssistantEtat", "Couleurs", "Connexion", "Recherche", "Etincelle", "Texte", "Ico"]
            (q / "qmldir").write_text("\n".join(("singleton " if n in ("Reglages", "Etat", "AssistantEtat", "Couleurs", "Connexion") else "") + n + " 1.0 " + n + ".qml" for n in noms))
            b = root / ".local/bin"; b.mkdir(parents=True)
            scripts = {"nc-apps": '#!/bin/sh\necho "[]"\n', "hyprctl": "#!/bin/sh\necho '[]'\n", "nc-aide-config": "#!/bin/sh\nexit 0\n",
                       "nc-demander": '#!/bin/sh\necho \'{"nom": "", "agent": "", "coupee": false}\'\n',
                       "nc-session": '#!/bin/sh\necho "nc-session $*" >> "$HOME/appels"\n[ "$1" = liste ] && echo \'[{"nom": "Dev", "fenetres": 3, "applis": ["kitty", "firefox"]}]\'\n'}
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
  if (etape === 0) { if (!spot.sessions.length) return; champ.text = "session "; etape++; return }
  if (etape === 1) { verifier(JSON.stringify(titres()) === JSON.stringify(["Session « Dev »"]), JSON.stringify(titres()))
   champ.text = "session Cours"
   verifier(titres()[0] === "Enregistrer la disposition actuelle sous « Cours »", JSON.stringify(titres()))
   spot.valider(0, false); champ.text = "dev"; etape++; return }
  if (etape === 2) { verifier(titres().indexOf("Session « Dev »") >= 0, "par son nom : " + JSON.stringify(titres()))
   Qt.quit() }
 } }
 Timer { interval: 9000; running: true; onTriggered: Qt.exit(9) }
}''')
            env = dict(os.environ, HOME=d, QT_QPA_PLATFORM="offscreen", QT_QUICK_BACKEND="software", XDG_RUNTIME_DIR=str(root / "runtime"),
                       XDG_CACHE_HOME=str(root / "cache"), PATH=str(b) + os.pathsep + os.environ["PATH"])
            env.pop("WAYLAND_DISPLAY", None)
            r = subprocess.run(["qs", "--no-color", "-p", str(q / "shell.qml")], env=env, text=True, capture_output=True, timeout=20)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("nc-session enregistrer Cours", (root / "appels").read_text())

    def test_supprimer_une_session(self):
        # Issue #11 : Suppr (ou le rond « − ») demande confirmation sur la ligne ; Entrée supprime puis relit la liste,
        # Échap ou une autre ligne annule, le Spotlight reste ouvert ; une ligne sans suppr ne réagit pas
        with tempfile.TemporaryDirectory(prefix="nc-spotlight-suppr-") as d:
            root = Path(d); shutil.copytree(QML, root / "qml"); (root / "runtime").mkdir(mode=0o700)
            q = root / "qml"
            (q / "Reglages.qml").write_text('pragma Singleton\nimport QtQuick\nQtObject {readonly property bool iaCoupee: false; readonly property bool sobre: true; function t(fr,en){return fr} function val(k,d){return d} function pageActive(n){return true}}')
            (q / "Etat.qml").write_text('pragma Singleton\nimport QtQuick\nimport Quickshell\nQtObject {property string saisie: ""; property string texteIA: ""; property bool recherche: true\n'
                                        ' readonly property string bin: Quickshell.env("HOME") + "/.local/bin/"; property int fermetures: 0; signal validerRecherche()\n'
                                        ' function faire(c) {} function fermer() { fermetures++ } function aller(p) {}}')
            (q / "AssistantEtat.qml").write_text('pragma Singleton\nimport QtQuick\nQtObject {function formater(t){return t}}')
            (q / "Etincelle.qml").write_text('import QtQuick\nItem {property real taille: 10; property bool tourne: false; property string agent: ""}')
            noms = ["Reglages", "Etat", "AssistantEtat", "Couleurs", "Connexion", "Recherche", "Etincelle", "Texte", "Ico"]
            (q / "qmldir").write_text("\n".join(("singleton " if n in ("Reglages", "Etat", "AssistantEtat", "Couleurs", "Connexion") else "") + n + " 1.0 " + n + ".qml" for n in noms))
            b = root / ".local/bin"; b.mkdir(parents=True)
            # Faux nc-session : journalise ses appels ; « supprimer Dev » la retire de la liste
            faux_session = '''#!/bin/sh
echo "nc-session $*" >> "$HOME/appels"
case "$1" in
  liste) if [ -e "$HOME/dev-supprimee" ]; then echo '[{"nom": "Cours", "fenetres": 1, "applis": ["kitty"]}]'
         else echo '[{"nom": "Dev", "fenetres": 3, "applis": ["kitty", "firefox"]}, {"nom": "Cours", "fenetres": 1, "applis": ["kitty"]}]'; fi ;;
  supprimer) [ "$2" = Dev ] && : > "$HOME/dev-supprimee" ;;
esac
'''
            scripts = {"nc-apps": '#!/bin/sh\necho "[]"\n', "hyprctl": "#!/bin/sh\necho '[]'\n", "nc-aide-config": "#!/bin/sh\nexit 0\n",
                       "nc-demander": '#!/bin/sh\necho \'{"nom": "", "agent": "", "coupee": false}\'\n', "nc-session": faux_session}
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
  if (etape === 0) { if (spot.sessions.length !== 2) return
   // Une ligne sans suppr : Suppr ne fait rien (la touche revient à la saisie)
   champ.text = "session Zzz"; champ.cursorPosition = champ.text.length
   verifier(!spot.resultats[0].suppr, "« Enregistrer… » n'a pas de suppr")
   verifier(!spot.toucheSuppr(false) && !spot.toucheSuppr(true) && spot.confirmer === -1, "ligne sans suppr : Suppr ne fait rien")
   champ.text = "session "; champ.cursorPosition = champ.text.length; etape++; return }
  if (etape === 1) {
   verifier(JSON.stringify(titres()) === JSON.stringify(["Session « Dev »", "Session « Cours »"]), JSON.stringify(titres()))
   verifier(spot.resultats[0].aide === "↵ l'ouvrir · Suppr la supprimer", "aide : " + spot.resultats[0].aide)
   var moins = trouver(spot, "nc-spotlight-moins")
   verifier(moins !== null && moins.montre, "le rond − est montré sur la ligne choisie")
   // Suppr : la confirmation sur la ligne, en rouge
   verifier(spot.toucheSuppr(false) && spot.confirmer === 0, "Suppr demande confirmation")
   var conf = trouver(spot, "nc-spotlight-confirmation")
   verifier(conf.visible && conf.text === "Supprimer la session « Dev » ?  ↵ oui · Échap non", "confirmation : " + conf.visible + " " + conf.text)
   verifier(String(conf.color) === String(Couleurs.rouge), "en rouge : " + conf.color)
   verifier(!moins.montre, "pas de − pendant la confirmation")
   // Échap : annule, rien n'est lancé, le Spotlight reste ouvert
   spot.echap()
   verifier(spot.confirmer === -1 && !conf.visible && Etat.fermetures === 0, "Échap annule sans fermer")
   // Une autre ligne annule aussi
   verifier(spot.toucheSuppr(true) && spot.confirmer === 0, "Maj + Suppr demande confirmation")
   spot.sel = 1
   verifier(spot.confirmer === -1, "changer de ligne annule")
   // Le rond − : la même confirmation
   spot.sel = 0
   var zone = moins.children[moins.children.length - 1]
   zone.clicked(null)
   verifier(spot.confirmer === 0 && conf.visible, "le − demande confirmation")
   spot.echap()
   // Entrée : supprime, sans fermer le Spotlight
   spot.toucheSuppr(false)
   spot.valider(spot.sel, false)
   verifier(Etat.fermetures === 0 && spot.confirmer === -1, "Entrée supprime sans fermer")
   etape++; return }
  if (etape === 2) { if (spot.sessions.length !== 1) return
   verifier(JSON.stringify(titres()) === JSON.stringify(["Session « Cours »"]), "liste relue : " + JSON.stringify(titres()))
   Qt.quit() }
 } }
 Timer { interval: 9000; running: true; onTriggered: Qt.exit(9) }
}''')
            env = dict(os.environ, HOME=d, QT_QPA_PLATFORM="offscreen", QT_QUICK_BACKEND="software", XDG_RUNTIME_DIR=str(root / "runtime"),
                       XDG_CACHE_HOME=str(root / "cache"), PATH=str(b) + os.pathsep + os.environ["PATH"])
            env.pop("WAYLAND_DISPLAY", None)
            r = subprocess.run(["qs", "--no-color", "-p", str(q / "shell.qml")], env=env, text=True, capture_output=True, timeout=20)
            sortie = r.stdout + r.stderr
            self.assertEqual(r.returncode, 0, sortie)
            for erreur in ("ReferenceError", "TypeError", "is not a type"):
                self.assertNotIn(erreur, sortie)
            appels = (root / "appels").read_text().splitlines()
            self.assertEqual([a for a in appels if "supprimer" in a], ["nc-session supprimer Dev"], "la commande exacte, une seule fois")
            self.assertIn("nc-session liste --json", appels[appels.index("nc-session supprimer Dev") + 1:], "liste relue après")
            self.assertNotIn("ouvrir", " ".join(appels), "aucune session ouverte")


# Le vrai nc-session, enveloppé : HOME pris du chemin de l'enveloppe (<home>/.local/bin), jamais le vrai ; chaque appel
# noté (ses arguments en JSON) dans <home>/appels-session
ENVELOPPE = r'''#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
H = Path(__file__).resolve().parents[2]
with (H / "appels-session").open("a") as f: f.write(json.dumps(sys.argv[1:]) + "\n")
os.environ["HOME"] = str(H)
os.execv(sys.executable, [sys.executable, "@SCRIPT@"] + sys.argv[1:])
'''


class ReglagesSessions(unittest.TestCase):
    """nc-reglages : une ligne par session enregistrée (fenêtres, applis) et « Supprimer… », qui demande confirmation
    (terminal : une question ; fenêtre graphique : le champ « confirmer » du catalogue) puis lance nc-session supprimer NOM."""

    def setUp(self):
        d = tempfile.TemporaryDirectory(prefix="nc-reglages-sessions-")
        self.addCleanup(d.cleanup)
        self.home = Path(d.name)
        b = self.home / ".local/bin"
        b.mkdir(parents=True)
        (b / "nc-session").write_text(ENVELOPPE.replace("@SCRIPT@", str(SCRIPT))); (b / "nc-session").chmod(0o755)
        self.dossier = self.home / ".config/nc/sessions"
        self.dossier.mkdir(parents=True)
        env = mock.patch.dict(os.environ, HOME=str(self.home), NC_LANGUE="fr")
        env.start()
        self.addCleanup(env.stop)

    def session(self, nom, *classes):
        (self.dossier / f"{nom}.json").write_text(json.dumps(dict(version=1, nom=nom, date=1, fenetres=[{"classe": c} for c in classes])))

    def charger(self):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", ResourceWarning)              # lecture de /sys par materiel()
            chargeur = importlib.machinery.SourceFileLoader("nc_reglages_sessions", str(SCRIPT.parent / "nc-reglages"))
            mod = importlib.util.module_from_spec(importlib.util.spec_from_loader(chargeur.name, chargeur))
            chargeur.exec_module(mod)
        mod.catalogue_raccourcis = lambda: []
        return mod

    def appels(self):
        f = self.home / "appels-session"
        return [json.loads(l) for l in f.read_text().splitlines()] if f.exists() else []

    def test_catalogue_une_ligne_par_session_a_la_fin_de_fenetres(self):
        self.session("Dev", "kitty", "firefox", "kitty")
        self.session("Cours", "evince")
        mod = self.charger()
        fen = [x for x in mod.catalogue({}) if x["section"] == "Fenêtres"]
        self.assertGreater(len(fen), 2)
        self.assertEqual([x["cle"] for x in fen[-2:]], ["session:Cours", "session:Dev"], "à la fin de la section Fenêtres")
        cours, dev = fen[-2:]
        self.assertEqual((dev["nom"], dev["genre"], dev["affiche"]), ("Session « Dev »", "action", "Supprimer…"))
        self.assertEqual(dev["aide"], "3 fenêtres : firefox, kitty")
        self.assertEqual(cours["aide"], "1 fenêtre : evince")
        self.assertEqual(dev["commande"], ["nc-session", "supprimer", "Dev"])
        self.assertIn("Supprimer la session « Dev » ?", dev["confirmer"])
        self.assertEqual(dev["bouton"], "Supprimer")
        self.assertTrue(dev["relire"])
        self.assertEqual(self.appels(), [["liste", "--json"]], "lue une fois, rien de supprimé en affichant")
        self.assertTrue((self.dossier / "Dev.json").exists())

    def test_catalogue_sans_session(self):
        mod = self.charger()
        fen = [x for x in mod.catalogue({}) if x["section"] == "Fenêtres"]
        self.assertEqual((fen[-1]["cle"], fen[-1]["genre"], fen[-1]["nom"]), ("info:sessions", "info", "Aucune session enregistrée"))
        self.assertNotIn("commande", fen[-1])
        # nc-session absent : la même ligne, sans erreur
        (self.home / ".local/bin/nc-session").unlink()
        self.assertEqual(mod.lignes_sessions()[0]["cle"], "info:sessions")

    def ecran(self, mod, reponses):
        """L'écran du terminal sans curses ; chaque question répond la suivante de `reponses` (0 : Supprimer)."""
        e = mod.Ecran.__new__(mod.Ecran)
        e.messages, e.questions, e.pos, e.vals = [], [], {}, {}
        e.sec = mod.SECTIONS.index("Fenêtres")
        e.statut = lambda texte, erreur=False: e.messages.append((texte, erreur))
        e.dessiner = lambda: None
        e.choisir = lambda titre, options, aide="", texte="": e.questions.append((titre, options, texte)) or reponses.pop(0)
        return e

    def test_terminal_refus_puis_suppression(self):
        self.session("Dev", "kitty")
        mod = self.charger()
        e = self.ecran(mod, [1, None, 0])
        lignes = e.items()
        self.assertEqual(lignes[-2], {"genre": "titre", "nom": "Sessions enregistrées"})
        dev = lignes[-1]
        self.assertEqual((dev["genre"], dev["action"], dev["session"]), ("assistant", "session-supprimer", "Dev"))
        e.items(); e.items()
        self.assertEqual(self.appels(), [["liste", "--json"]], "lue à l'affichage de la section, pas à chaque dessin")
        # Annuler, puis Échap : rien
        e.assistant(dev)
        e.assistant(dev)
        self.assertEqual(e.questions[0][:2], ("Session « Dev »", ["Supprimer", "Annuler"]))
        self.assertIn("Ses fenêtres restent ouvertes", e.questions[0][2])
        self.assertTrue((self.dossier / "Dev.json").exists())
        self.assertNotIn("supprimer", [a[0] for a in self.appels()])
        self.assertEqual(e.messages, [("Rien n'a changé", False)] * 2)
        # Supprimer : nc-session supprimer Dev, exactement ; la liste est relue
        e.assistant(dev)
        self.assertEqual([a for a in self.appels() if a[0] == "supprimer"], [["supprimer", "Dev"]])
        self.assertFalse((self.dossier / "Dev.json").exists())
        self.assertEqual(e.messages[-1], ("Session « Dev » supprimée.", False))
        self.assertEqual(e.items()[-1]["nom"], "Aucune session enregistrée")
        # Une autre section, puis Fenêtres à nouveau : relue
        n = len(self.appels())
        e.sec = mod.SECTIONS.index("Énergie"); e.items()
        e.sec = mod.SECTIONS.index("Fenêtres"); e.items()
        self.assertEqual(len(self.appels()), n + 1)

    def test_supprimer_une_session_absente(self):
        env = dict(HOME=str(self.home), PATH="/usr/bin:/bin", NC_LANGUE="fr")
        r = subprocess.run([str(SCRIPT), "supprimer", "Rien"], env=env, capture_output=True, text=True, timeout=30)
        self.assertEqual(r.returncode, 1)
        self.assertIn("Aucune session « Rien »", r.stderr)


if __name__ == "__main__":
    unittest.main()

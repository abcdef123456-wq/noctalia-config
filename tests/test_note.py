"""Note rapide (nc-note et « note … » du Spotlight). Tout se passe dans un dossier temporaire (HOME, XDG_*), avec un faux
xdg-open : rien ne s'ouvre à l'écran, aucun fichier réel n'est touché."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
NC_NOTE = REPO / "home/.local/bin/nc-note"
QML = REPO / "home/.config/quickshell/nc-ile"


class Script(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.TemporaryDirectory(prefix="nc-note-")
        self.d = Path(self.t.name)
        self.bin = self.d / "bin"
        self.bin.mkdir()
        x = self.bin / "xdg-open"
        x.write_text('#!/bin/sh\necho "xdg-open $*" >> "$HOME/appels"\n')
        x.chmod(0o755)
        self.fichier = self.d / "data/nc/notes.md"

    def tearDown(self):
        self.t.cleanup()

    def note(self, *args, entree=b"", code=None):
        env = {"HOME": str(self.d), "PATH": str(self.bin) + os.pathsep + "/usr/bin:/bin", "XDG_DATA_HOME": str(self.d / "data"),
               "TMPDIR": str(self.d), "LANG": "C.UTF-8"}
        r = subprocess.run([sys.executable, str(NC_NOTE), *args], input=entree, capture_output=True, env=env, timeout=30)
        if code is not None:
            self.assertEqual(r.returncode, code, r.stdout + r.stderr)
        return r

    def test_ajouter_une_ligne_datee_privee(self):
        self.note("ajouter", entree="acheter du pain\nET\x1b[31m du lait\u2028fin\u202e !".encode(), code=0)
        lignes = self.fichier.read_text().splitlines()
        self.assertEqual(len(lignes), 1)
        self.assertRegex(lignes[0], r"^- \d{4}-\d\d-\d\d \d\d:\d\d  acheter du pain ET \[31m du lait fin !$")
        self.assertEqual(self.fichier.stat().st_mode & 0o777, 0o600)
        self.note("ajouter", entree="deuxième".encode(), code=0)
        self.assertEqual(len(self.fichier.read_text().splitlines()), 2)

    def test_refus(self):
        self.assertEqual(json.loads(self.note("ajouter", entree=b" \n\t\x07 ", code=2).stdout)["erreur"], "vide")
        self.assertEqual(json.loads(self.note("ajouter", entree=b"a" * 1001, code=2).stdout)["erreur"], "trop_long")
        self.note("ajouter", entree=b"a" * 1000, code=0)
        r = self.note("ajouter", "texte dans argv", entree=b"x", code=2)   # le texte ne passe jamais par argv : refusé
        self.assertEqual(r.stdout, b"")
        self.assertIn(b"usage", r.stderr)
        self.assertEqual(len(self.fichier.read_text().splitlines()), 1)

    def test_jamais_au_bout_d_un_lien_et_remis_en_0600(self):
        self.fichier.parent.mkdir(parents=True)
        cible = self.d / "ailleurs"
        cible.write_text("intact\n")
        self.fichier.symlink_to(cible)
        self.assertEqual(json.loads(self.note("ajouter", entree=b"x", code=1).stdout)["erreur"], "local")
        self.note("liste", code=1)
        self.note("ouvrir", code=1)
        self.assertEqual(cible.read_text(), "intact\n")
        self.assertFalse((self.d / "appels").exists())
        self.fichier.unlink()
        os.mkfifo(self.fichier)                                   # un tube nommé : refusé, sans rester bloqué
        self.note("ajouter", entree=b"x", code=1)
        self.assertEqual(json.loads(self.note("liste", code=1).stdout)["erreur"], "local")
        self.fichier.unlink()
        self.fichier.write_text("- vieille note")                 # écrite à la main, en 0644, sans retour final
        self.fichier.chmod(0o644)
        self.note("ajouter", entree=b"neuve", code=0)
        self.assertEqual(self.fichier.stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.fichier.read_text().splitlines()[0], "- vieille note")
        self.assertEqual(len(self.fichier.read_text().splitlines()), 2)

    def test_liste_la_plus_recente_d_abord(self):
        self.assertEqual(json.loads(self.note("liste", code=0).stdout)["notes"], [])
        self.assertFalse(self.fichier.exists())                   # lire ne crée pas le fichier
        for i in range(25):
            self.note("ajouter", entree=f"note {i}".encode(), code=0)
        n = json.loads(self.note("liste", code=0).stdout)["notes"]
        self.assertEqual(len(n), 20)
        self.assertEqual(n[0]["texte"], "note 24")
        self.assertRegex(n[0]["date"], r"^\d{4}-\d\d-\d\d \d\d:\d\d$")
        self.assertEqual([x["texte"] for x in json.loads(self.note("liste", "3", code=0).stdout)["notes"]], ["note 24", "note 23", "note 22"])

    def test_ouvrir_cree_puis_ouvre(self):
        self.note("ouvrir", code=0)
        self.assertEqual(self.fichier.stat().st_mode & 0o777, 0o600)
        for _ in range(50):                                       # xdg-open part en fond
            if (self.d / "appels").exists():
                break
            subprocess.run(["sleep", "0.1"])
        self.assertEqual((self.d / "appels").read_text(), f"xdg-open {self.fichier}\n")


@unittest.skipUnless(shutil.which("qs"), "Quickshell requis")
class Spotlight(unittest.TestCase):
    def test_note_puis_liste_puis_ouvrir(self):
        with tempfile.TemporaryDirectory(prefix="nc-note-spot-") as d:
            root = Path(d); shutil.copytree(QML, root / "qml"); (root / "runtime").mkdir(mode=0o700)
            q = root / "qml"
            (q / "Reglages.qml").write_text('pragma Singleton\nimport QtQuick\nQtObject {property var v: ({}); readonly property bool iaCoupee: false\n'
                                            ' function t(fr,en){return fr} function val(k,d){return v[k] !== undefined ? v[k] : d} function pageActive(n){return true}}')
            (q / "Etat.qml").write_text('pragma Singleton\nimport QtQuick\nimport Quickshell\nQtObject {property string saisie: ""; property string texteIA: ""\n'
                                        ' property bool recherche: true; property bool nuit: false; readonly property string bin: Quickshell.env("HOME") + "/.local/bin/"\n'
                                        ' property int fermetures: 0; signal validerRecherche()\n'
                                        ' function faire(c) {} function fermer() { fermetures++ } function aller(p) {} function basculer(e, c) {}}')
            (q / "AssistantEtat.qml").write_text('pragma Singleton\nimport QtQuick\nQtObject {function formater(t){return t} function sansReseau(t){return t}}')
            (q / "Etincelle.qml").write_text('import QtQuick\nItem {property real taille: 10; property bool tourne: false; property string agent: ""}')
            (q / "Partage.qml").write_text('pragma Singleton\nimport QtQuick\nQtObject { property bool silence: false }')
            (q / "CloudEtat.qml").write_text('pragma Singleton\nimport QtQuick\nQtObject { property bool actif: false; property bool associe: false }')
            (q / "Rappels.qml").write_text('pragma Singleton\nimport QtQuick\nQtObject { property var liste: []; property bool plein: false; function analyser(p) { return {ok: false, raison: "heure"} } function quand(d) { return "" } function creer(t, d) { return false } function supprimer(i) {} }')
            noms = ["Reglages", "Etat", "AssistantEtat", "Couleurs", "Connexion", "Recherche", "LanceurOnglets", "LanceurLigne", "LanceurPied", "Emoji", "Partage", "Diagnostic", "Etincelle", "Texte", "Ico"]
            (q / "qmldir").write_text("\n".join(("singleton " if n in ("Reglages", "Etat", "AssistantEtat", "Couleurs", "Connexion", "Partage") else "") + n + " 1.0 " + n + ".qml" for n in noms) + "\nsingleton CloudEtat 1.0 CloudEtat.qml\nsingleton Rappels 1.0 Rappels.qml")
            b = root / ".local/bin"; b.mkdir(parents=True)
            scripts = {
                # Recherche de fichiers et de logiciels (réseau) : elles ne doivent jamais recevoir le texte d'une note
                "nc-apps": '#!/bin/sh\necho "nc-apps $*" >> "$HOME/appels"\necho "[]"\n',
                "nc-logiciels": '#!/bin/sh\necho "nc-logiciels $*" >> "$HOME/appels"\necho "[]"\n',
                "hyprctl": "#!/bin/sh\necho '[]'\n",
                "nc-aide-config": "#!/bin/sh\nexit 0\n",
                "nc-demander": '#!/bin/sh\necho \'{"nom": "Claude", "agent": "claude", "coupee": false}\'\n',
                # Le vrai nc-note, derrière un enregistreur de ses arguments
                "nc-note": f'#!/bin/sh\necho "nc-note $*" >> "$HOME/appels"\nexec {sys.executable} {NC_NOTE} "$@"\n',
                "xdg-open": '#!/bin/sh\necho "xdg-open $*" >> "$HOME/appels"\n',
            }
            for nom, code in scripts.items():
                (b / nom).write_text(code); (b / nom).chmod(0o755)
            (q / "shell.qml").write_text('''import QtQuick
import Quickshell
ShellRoot {
 property int etape: 0
 function trouver(item,nom){if(item.objectName===nom)return item;for(var i=0;i<item.children.length;i++){var r=trouver(item.children[i],nom);if(r)return r}return null}
 function verifier(ok,message){if(!ok){console.error("ECHEC: " + message);Qt.exit(2);throw new Error(message)}}
 function titres(){ return spot.resultats.map(x => x.titre) }
 FloatingWindow { visible: true; implicitWidth: 700; implicitHeight: 500
  Recherche { id: spot; width: 700; actif: true } }
 Timer { interval: 100; running: true; repeat: true; onTriggered: {
  var champ = trouver(spot, "nc-spotlight-champ")
  if (etape === 0) { champ.text = "notes"; etape = -1; return }
  if (etape === -1) { if (!spot.notesLues) return                // d'abord la liste vide, déjà lue avant l'ajout
   verifier(JSON.stringify(titres()) === JSON.stringify(["Ouvrir mes notes"]), "liste vide : " + JSON.stringify(titres()))
   champ.text = "note acheter <b>du</b> pain"; etape = 1; return }
  if (etape < 7) { etape++; return }                       // 600 ms : les délais des fichiers (120) et logiciels (320) passent
  if (etape === 7) {
   verifier(JSON.stringify(titres()) === JSON.stringify(["Noter : acheter <b>du</b> pain"]), "aperçu de la note : " + JSON.stringify(titres()))
   spot.valider(0, false); verifier(Etat.fermetures === 0, "le Spotlight reste ouvert"); etape = 10; return }
  if (etape === 10) { if (champ.text !== "notes" || !spot.notesLues) return    // la liste, relue après l'ajout
   verifier(JSON.stringify(titres()) === JSON.stringify(["Ouvrir mes notes", "acheter <b>du</b> pain"]), "liste : " + JSON.stringify(titres()))
   champ.text = "note"
   verifier(titres().length === 2 && titres()[1] === "acheter <b>du</b> pain", "« note » seul : la liste : " + JSON.stringify(titres()))
   spot.valider(1, false); verifier(Etat.fermetures === 1, "Entrée sur une note ouvre le fichier et ferme")
   champ.text = "note " + "x".repeat(1001); spot.valider(0, false); etape = 11; return }
  if (etape === 11) { if (spot.noteErreur === "") return
   verifier(titres()[0] === "Note trop longue (1000 caractères au plus) : rien n'est noté.", "refus dit : " + JSON.stringify(titres()))
   champ.text = "notepad"; spot.changerEspace("fichiers")      // les fichiers ne sont cherchés que dans leur espace
   verifier(titres().every(t => t !== "Ouvrir mes notes" && t.indexOf("Noter") !== 0), "« notepad » reste une recherche : " + JSON.stringify(titres()))
   // Une note ajoutée hors du Spotlight : relue à la réouverture
   Quickshell.execDetached(["sh", "-c", "printf '%s\\n' '- 2026-01-01 10:00  externe' >> \\"$XDG_DATA_HOME/nc/notes.md\\""])
   etape = 12; return }
  if (etape < 19) { if (etape === 13) spot.changerEspace("actions"); etape++; return }      // puis les logiciels, dans les Actions
  if (etape === 19) { Etat.saisie = "notes"; spot.demarrer(); etape++; return }
  if (etape === 20) { if (!spot.notesLues) return
   verifier(titres()[1] === "externe", "relue à la réouverture : " + JSON.stringify(titres()))
   etape = 21; return }
  if (etape < 24) { etape++; return }
  Qt.quit()
 } }
 Timer { interval: 15000; running: true; onTriggered: Qt.exit(9) }
}''')
            env = dict(os.environ, HOME=d, QT_QPA_PLATFORM="offscreen", QT_QUICK_BACKEND="software", XDG_RUNTIME_DIR=str(root / "runtime"),
                       XDG_CACHE_HOME=str(root / "cache"), XDG_DATA_HOME=str(root / "data"), PATH=str(b) + os.pathsep + os.environ["PATH"])
            env.pop("WAYLAND_DISPLAY", None)
            r = subprocess.run(["qs", "--no-color", "-p", str(q / "shell.qml")], env=env, text=True, capture_output=True, timeout=30)
            sortie = r.stdout + r.stderr
            self.assertEqual(r.returncode, 0, sortie)
            for erreur in ("ReferenceError", "TypeError", "is not a type"):
                self.assertNotIn(erreur, sortie)
            notes = (root / "data/nc/notes.md").read_text().splitlines()
            self.assertEqual(len(notes), 2)                         # la note du Spotlight, puis celle écrite à côté
            self.assertTrue(notes[0].endswith("  acheter <b>du</b> pain"), notes)
            appels = (root / "appels").read_text()
            self.assertNotIn("acheter", appels)                     # jamais dans un argv, ni vers les fichiers ou les logiciels
            self.assertIn("nc-apps files notepad", appels)          # le contrôle : ces recherches partent bien hors des notes
            self.assertIn("nc-logiciels chercher notepad", appels)
            self.assertIn("nc-note ajouter\n", appels)
            self.assertIn("nc-note liste 20\n", appels)
            self.assertIn("nc-note ouvrir\n", appels)
            for _ in range(50):
                if "xdg-open" in (root / "appels").read_text():
                    break
                subprocess.run(["sleep", "0.1"])
            self.assertIn(f"xdg-open {root}/data/nc/notes.md", (root / "appels").read_text())


if __name__ == "__main__":
    unittest.main()

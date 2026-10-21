"""Fenêtre « Connexion JARVIS » (ConnexionJarvis.qml) hors écran, avec un faux nc-assistant : pré-remplissage sans la
clé, avertissement d'adresse privée en direct, test puis enregistrement des valeurs saisies (la clé sur l'entrée
standard, jamais en argument), champ de la clé vidé après l'enregistrement, Échap qui ferme l'île d'abord."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
QML = REPO / "home/.config/quickshell/nc-ile"

FAUX = r'''#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
H = Path(os.environ["HOME"])
with (H / "argv").open("a") as f: f.write(json.dumps(sys.argv[1:]) + "\n")
action = sys.argv[2]
if action == "lire":
    print(json.dumps({"existe": True, "url": "https://ancien.example", "user_id": "moi", "timeout": "120", "cle": True}))
else:
    d = json.loads(sys.stdin.readline())
    with (H / "stdin").open("a") as f: f.write(json.dumps([action, d]) + "\n")
    if action == "tester": print(json.dumps({"online": True, "latency_ms": 42, "version": "2.1", "private": True}))
    else: print(json.dumps({"ok": True, "warning": "Adresse privée."}))
'''


@unittest.skipUnless(shutil.which("qs"), "Quickshell requis")
class ConnexionJarvis(unittest.TestCase):
    def test_saisie_test_enregistrement(self):
        with tempfile.TemporaryDirectory(prefix="nc-connexion-") as d:
            root = Path(d); q = root / "qml"; shutil.copytree(QML, q); (root / "runtime").mkdir(mode=0o700)
            (q / "Reglages.qml").write_text('pragma Singleton\nimport QtQuick\nQtObject {function t(fr,en){return fr} function val(k,d){return d}}')
            (q / "JarvisEtat.qml").write_text('pragma Singleton\nimport QtQuick\nQtObject {property int actualisations: 0; function actualiser(){actualisations++}}')
            (q / "Etincelle.qml").write_text('import QtQuick\nItem {property real taille: 10; property bool tourne: false; property string agent: ""}')
            noms = ["Reglages", "JarvisEtat", "Couleurs", "ConnexionJarvis", "Etincelle", "Texte", "Ico", "JarvisBouton"]
            (q / "qmldir").write_text("\n".join(("singleton " if n in ("Reglages", "JarvisEtat", "Couleurs") else "") + n + " 1.0 " + n + ".qml" for n in noms))
            b = root / ".local/bin"; b.mkdir(parents=True)
            (b / "nc-assistant").write_text(FAUX); (b / "nc-assistant").chmod(0o755)
            (q / "shell.qml").write_text('''import QtQuick
import QtTest
import Quickshell
ShellRoot {
 id: racine
 property int etape: 0
 property var fen: null
 property bool ileFermee: false
 TestCase { id: clavier; name: "Connexion"; when: false }
 function verifier(ok, m) { if (!ok) { console.error(m); Qt.exit(2); throw new Error(m) } }
 function trouver(item, nom) { if (item.objectName === nom) return item; for (var i = 0; i < item.children.length; i++) { var r = trouver(item.children[i], nom); if (r) return r } return null }
 Timer { interval: 100; running: true; repeat: true; onTriggered: {
  if (etape === 0) { var c = Qt.createComponent("ConnexionJarvis.qml"); verifier(c.status === Component.Ready, c.errorString()); fen = c.createObject(racine)
                     fen.fermerIle.connect(function () { racine.ileFermee = true; fen.ileOuverte = false }); fen.afficher(Quickshell.screens[0].name); etape++; return }
  if (fen.occupe) return
  if (etape === 1) {
   verifier(fen.url.text === "https://ancien.example" && fen.ident.text === "moi" && fen.delai.text === "120", "pré-remplissage : " + fen.url.text)
   verifier(fen.cleEnregistree && fen.cle.text === "", "la clé n'est jamais relue")
   verifier(fen.avertissement === "", "pas d'avertissement pour une adresse HTTPS publique")
   fen.url.text = "http://192.168.1.28:8000"
   verifier(fen.avertissement.indexOf("privée") >= 0 && trouver(fen.contentItem, "nc-connexion-avertissement").visible, "avertissement d'adresse privée absent")
   fen.cle.text = "nouvelle-cle-secrete"; fen.tester(); etape++; return }
  if (etape === 2) {
   verifier(fen.resultat && fen.resultat.online && fen.resultat.latency_ms === 42, "résultat du test : " + JSON.stringify(fen.resultat))
   verifier(trouver(fen.contentItem, "nc-connexion-resultat").visible, "résultat non affiché")
   fen.enregistrer(); etape++; return }
  if (etape === 3) {
   verifier(!fen.erreur && fen.message.indexOf("Connexion enregistrée.") === 0, "message : " + fen.message)
   verifier(fen.cle.text === "" && fen.cleEnregistree, "la clé reste dans le champ après l'enregistrement")
   verifier(JarvisEtat.actualisations === 1, "le cockpit n'est pas relu")
   fen.ileOuverte = true; clavier.keyClick(Qt.Key_Escape); verifier(racine.ileFermee && fen.visible, "Échap : l'île d'abord")
   clavier.keyClick(Qt.Key_Escape); verifier(!fen.visible, "second Échap : la fenêtre"); Qt.quit() }
 } }
 Timer { interval: 10000; running: true; onTriggered: Qt.exit(9) }
}''')
            env = dict(os.environ, HOME=d, QT_QPA_PLATFORM="offscreen", QT_QUICK_BACKEND="software", XDG_RUNTIME_DIR=str(root / "runtime"), XDG_CACHE_HOME=str(root / "cache"))
            env.pop("WAYLAND_DISPLAY", None)
            r = subprocess.run(["qs", "--no-color", "-p", str(q / "shell.qml")], env=env, text=True, capture_output=True, timeout=15)
            sortie = r.stdout + r.stderr
            self.assertEqual(r.returncode, 0, sortie)
            for e in ("ReferenceError", "TypeError", "Cannot assign", "is not a type"):
                self.assertNotIn(e, sortie)
            argv = (root / "argv").read_text()
            self.assertNotIn("nouvelle-cle-secrete", argv, "la clé ne passe jamais en argument")
            envois = [json.loads(l) for l in (root / "stdin").read_text().splitlines()]
            self.assertEqual([a for a, _ in envois], ["tester", "enregistrer"])
            for _, d in envois:
                self.assertEqual((d["url"], d["secret_key"], d["user_id"], d["timeout"]), ("http://192.168.1.28:8000", "nouvelle-cle-secrete", "moi", "120"))


if __name__ == "__main__":
    unittest.main()

"""Fenêtre « Clés des IA » (ClesIA.qml) hors écran, avec un faux nc-ia : l'état des IA, une clé enregistrée par l'entrée
standard (jamais en argument) puis essayée tout de suite, le champ vidé, l'effacement d'une clé, Échap qui ferme l'île
d'abord."""
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
c = sys.argv[1]
cle = (H / "cle").read_text() if (H / "cle").exists() else ""
if c == "etat":
    print(json.dumps({"mode": "auto", "coupee": False, "usages": {"question": {"id": "claude", "nom": "Claude Code"}},
                      "ias": [{"id": "anthropic", "nom": "Claude (API Anthropic)", "genre": "api", "disponible": bool(cle), "agent": "claude",
                               "inscription": "https://console.anthropic.com/settings/keys"},
                              {"id": "claude", "nom": "Claude Code", "genre": "cli", "disponible": True, "agent": "claude", "inscription": ""}]}))
elif c == "cles":
    print(json.dumps({"anthropic": {"origine": "fichier" if cle else "", "fin": ("…" + cle[-4:]) if cle else ""}}))
elif c == "cle":
    v = sys.stdin.readline().strip()
    with (H / "stdin").open("a") as f: f.write(json.dumps([sys.argv[2], v]) + "\n")
    (H / "cle").write_text(v)
    print("ok")
elif c == "tester":
    print(json.dumps([{"id": sys.argv[2], "nom": "x", "ok": bool(cle), "ms": 321} if bool(cle) else
                      {"id": sys.argv[2], "nom": "x", "ok": False, "erreur": "pas de clé"}]))
'''


@unittest.skipUnless(shutil.which("qs"), "Quickshell requis")
class ClesIA(unittest.TestCase):
    def test_enregistrer_essayer_effacer(self):
        with tempfile.TemporaryDirectory(prefix="nc-cles-ia-") as d:
            root = Path(d); q = root / "qml"; shutil.copytree(QML, q); (root / "runtime").mkdir(mode=0o700)
            (q / "Reglages.qml").write_text('pragma Singleton\nimport QtQuick\nQtObject {function t(fr,en){return fr} function val(k,d){return d}}')
            (q / "Etincelle.qml").write_text('import QtQuick\nItem {property real taille: 10; property bool tourne: false; property string agent: ""}')
            noms = ["Reglages", "Couleurs", "ClesIA", "Etincelle", "Texte", "Ico", "JarvisBouton"]
            (q / "qmldir").write_text("\n".join(("singleton " if n in ("Reglages", "Couleurs") else "") + n + " 1.0 " + n + ".qml" for n in noms))
            b = root / ".local/bin"; b.mkdir(parents=True)
            (b / "nc-ia").write_text(FAUX); (b / "nc-ia").chmod(0o755)
            (q / "shell.qml").write_text('''import QtQuick
import QtTest
import Quickshell
ShellRoot {
 id: racine
 property int etape: 0
 property var fen: null
 property bool ileFermee: false
 TestCase { id: clavier; name: "Cles"; when: false }
 function verifier(ok, m) { if (!ok) { console.error(m); Qt.exit(2); throw new Error(m) } }
 function trouver(item, nom) { if (item.objectName === nom) return item; for (var i = 0; i < item.children.length; i++) { var r = trouver(item.children[i], nom); if (r) return r } return null }
 Timer { interval: 100; running: true; repeat: true; onTriggered: {
  if (etape === 0) { var c = Qt.createComponent("ClesIA.qml"); verifier(c.status === Component.Ready, c.errorString()); fen = c.createObject(racine)
                     fen.fermerIle.connect(function () { racine.ileFermee = true; fen.ileOuverte = false }); fen.afficher(Quickshell.screens[0].name); etape++; return }
  if (fen.occupe) return
  if (etape === 1) {
   verifier(fen.apis.length === 1 && fen.autres.length === 1, "IA lues : " + JSON.stringify(fen.etat))
   verifier(trouver(fen.contentItem, "nc-cles-resume").text.indexOf("Claude Code") >= 0, "qui répond maintenant")
   var champ = trouver(fen.contentItem, "nc-cles-anthropic"); verifier(champ !== null, "champ de la clé absent")
   champ.text = "sk-ant-secrete-9876"; fen.enregistrer("anthropic", champ.text); etape++; return }
  if (etape === 2) { if (!fen.essais.anthropic) return
   verifier(fen.essais.anthropic.ok && fen.essais.anthropic.ms === 321, "essai après l'enregistrement : " + JSON.stringify(fen.essais))
   verifier(trouver(fen.contentItem, "nc-cles-anthropic").text === "", "le champ garde la clé")
   verifier(fen.cles.anthropic.fin === "…9876", "fin de la clé : " + JSON.stringify(fen.cles))
   fen.essais = ({}); fen.enregistrer("anthropic", ""); etape++; return }
  if (etape === 3) { if (!fen.essais.anthropic) return
   verifier(!fen.cles.anthropic.origine, "clé effacée : " + JSON.stringify(fen.cles))
   fen.ileOuverte = true; clavier.keyClick(Qt.Key_Escape); verifier(racine.ileFermee && fen.visible, "Échap : l'île d'abord")
   clavier.keyClick(Qt.Key_Escape); verifier(!fen.visible, "second Échap : la fenêtre"); Qt.quit() }
 } }
 Timer { interval: 12000; running: true; onTriggered: Qt.exit(9) }
}''')
            env = dict(os.environ, HOME=d, QT_QPA_PLATFORM="offscreen", QT_QUICK_BACKEND="software", XDG_RUNTIME_DIR=str(root / "runtime"),
                       XDG_CACHE_HOME=str(root / "cache"))
            env.pop("WAYLAND_DISPLAY", None)
            r = subprocess.run(["qs", "--no-color", "-p", str(q / "shell.qml")], env=env, text=True, capture_output=True, timeout=20)
            sortie = r.stdout + r.stderr
            self.assertEqual(r.returncode, 0, sortie)
            for e in ("ReferenceError", "TypeError", "Cannot assign", "is not a type"):
                self.assertNotIn(e, sortie)
            argv = (root / "argv").read_text()
            self.assertNotIn("sk-ant-secrete-9876", argv, "la clé ne passe jamais en argument")
            self.assertIn('["cle", "anthropic"]', argv)
            self.assertIn('["tester", "anthropic", "--json"]', argv)
            envois = [json.loads(l) for l in (root / "stdin").read_text().splitlines()]
            self.assertEqual(envois, [["anthropic", "sk-ant-secrete-9876"], ["anthropic", ""]])


if __name__ == "__main__":
    unittest.main()

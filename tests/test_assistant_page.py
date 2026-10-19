"""Vrais composants QML et Process, isolés de la session et du serveur personnels."""
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
class PageAssistant(unittest.TestCase):
    def executer(self, scenario, absent=False):
        with tempfile.TemporaryDirectory(prefix="nc-assistant-page-") as d:
            root = Path(d)
            (root / "run").mkdir(mode=0o700)
            (root / "assets").mkdir()
            noms = ["Assistant.qml", "AssistantEtat.qml", "Defilement.qml", "Texte.qml", "Ico.qml",
                    "Etincelle.qml", "LogoAssistant.qml", "Couleurs.qml"]
            for nom in noms + ["assets/assistant-animation.png"]:
                shutil.copy2(QML / nom, root / nom)
            (root / "Reglages.qml").write_text('pragma Singleton\nimport QtQuick\nQtObject {function t(fr,en){return en} function val(k,d){return d}}')
            (root / "Agents.qml").write_text('pragma Singleton\nimport QtQuick\nQtObject {property var ias: ({claude:{couleur:"#d97757"},assistant:{couleur:"#10b981"}})}')
            (root / "qmldir").write_text("\n".join(
                ("singleton " if nom in ("AssistantEtat.qml", "Couleurs.qml", "Reglages.qml", "Agents.qml") else "")
                + nom[:-4] + " 1.0 " + nom for nom in noms + ["Reglages.qml", "Agents.qml"]))
            if not absent:
                bin = root / ".local/bin"
                bin.mkdir(parents=True)
                helper = bin / "nc-assistant"
                helper.write_text('''#!/usr/bin/env python3
import json,os,sys,time
from pathlib import Path
r=json.loads(sys.stdin.readline())
with Path(os.environ["HOME"],"recus").open("a") as f:f.write(json.dumps(dict(argv=sys.argv[1:],payload=r))+"\\n")
time.sleep(.2)
if r["question"]=="erreur":
 print(json.dumps(dict(ok=False,error="Échec simulé")),flush=True);sys.exit(1)
if r["question"]=="invalide":print("not json",flush=True);sys.exit(0)
print(json.dumps(dict(ok=True,text="<b>Réponse</b>\\n"+r["question"])),flush=True)
''')
                helper.chmod(0o755)
            (root / "shell.qml").write_text('''import QtQuick
import QtQuick.Window
import Quickshell
ShellRoot {
 id: test
 property int etape:0
 property var page:null
 function verifier(ok,message){if(!ok){console.error(message);Qt.exit(2);throw new Error(message)}}
 function creer(){var c=Qt.createComponent("Assistant.qml");verifier(c.status===Component.Ready,c.errorString());page=c.createObject(w.contentItem,{width:400,height:488});verifier(page!==null,"page absente")}
 Window {id:w;visible:true;width:432;height:520}
 Timer {interval:80;running:true;repeat:true;onTriggered:{
''' + scenario + '''
 }}
 Timer {interval:5000;running:true;onTriggered:Qt.exit(9)}
}''')
            env = dict(os.environ, HOME=d, QT_QPA_PLATFORM="offscreen", QT_QUICK_BACKEND="software",
                       XDG_RUNTIME_DIR=str(root / "run"), XDG_CACHE_HOME=str(root / "cache"))
            env.pop("WAYLAND_DISPLAY", None)
            r = subprocess.run(["qs", "--no-color", "-p", str(root / "shell.qml")], env=env,
                               capture_output=True, text=True, timeout=8)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertNotIn("ReferenceError", r.stdout + r.stderr)
            self.assertNotIn("TypeError", r.stdout + r.stderr)
            recus = root / "recus"
            return [json.loads(l) for l in recus.read_text().splitlines()] if recus.exists() else []

    def test_request_survives_page_destruction_and_blocks_double_send(self):
        recus = self.executer('''
if(etape===0){creer();AssistantEtat.brouillon="question privée";AssistantEtat.envoyer();AssistantEtat.envoyer();verifier(AssistantEtat.enCours,"pas occupé");page.destroy();page=null;etape++}
else if(etape===1&&!AssistantEtat.enCours){verifier(AssistantEtat.messages.length===2,"messages perdus");verifier(AssistantEtat.erreur==="",AssistantEtat.erreur);creer();verifier(AssistantEtat.messages[1].texte==="<b>Réponse</b>\\nquestion privée","réponse altérée");AssistantEtat.brouillon="brouillon gardé";page.destroy();etape++}
else if(etape===2){creer();verifier(AssistantEtat.brouillon==="brouillon gardé","brouillon perdu");AssistantEtat.effacer();verifier(AssistantEtat.messages.length===0,"effacement");Qt.quit()}
''')
        self.assertEqual(len(recus), 1)
        self.assertEqual(recus[0]["argv"], ["requete-ile"])
        self.assertEqual(recus[0]["payload"]["question"], "question privée")

    def test_error_invalid_output_and_second_request(self):
        recus = self.executer('''
if(etape===0){creer();AssistantEtat.brouillon="erreur";AssistantEtat.envoyer();etape++}
else if(etape===1&&!AssistantEtat.enCours){verifier(AssistantEtat.erreur==="Échec simulé","erreur perdue");verifier(AssistantEtat.brouillon==="erreur","question perdue");AssistantEtat.brouillon="invalide";AssistantEtat.envoyer();etape++}
else if(etape===2&&!AssistantEtat.enCours){verifier(AssistantEtat.erreur!=="","JSON invalide accepté");AssistantEtat.brouillon="succès";AssistantEtat.envoyer();etape++}
else if(etape===3&&!AssistantEtat.enCours){verifier(AssistantEtat.erreur==="",AssistantEtat.erreur);verifier(AssistantEtat.messages.length===4,"nombre de messages");Qt.quit()}
''')
        self.assertEqual(len(recus), 3)
        self.assertEqual(len({r["payload"]["session_id"] for r in recus}), 1)

    def test_missing_client_does_not_leave_page_busy(self):
        self.executer('''
if(etape===0){creer();AssistantEtat.brouillon="test";AssistantEtat.envoyer();etape++}
else if(etape===1&&!AssistantEtat.enCours){verifier(AssistantEtat.erreur!=="","erreur absente");Qt.quit()}
''', absent=True)

    def test_history_is_bounded_and_draft_survives_clear(self):
        self.executer('''
if(etape===0){creer();for(var i=0;i<100;i++)AssistantEtat.ajouter("assistant","x".repeat(16000));verifier(AssistantEtat.messages.length<=3,"historique trop grand");AssistantEtat.messages=[];for(var j=0;j<100;j++)AssistantEtat.ajouter("vous","x");verifier(AssistantEtat.messages.length===24,"trop de messages");AssistantEtat.brouillon="gardé";AssistantEtat.effacer();verifier(AssistantEtat.brouillon==="gardé","brouillon effacé");Qt.quit()}
''')

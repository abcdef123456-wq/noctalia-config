"""Cockpit QML réel hors écran ; aucun serveur/bot/session utilisateur utilisé."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

REPO=Path(__file__).resolve().parents[1]
QML=REPO/'home/.config/quickshell/nc-ile'


@unittest.skipUnless(shutil.which('qs'),'Quickshell requis')
class CockpitJarvis(unittest.TestCase):
    def executer(self,scenario,absent=False,evenements=False):
        with tempfile.TemporaryDirectory(prefix='nc-jarvis-qml-') as d:
            root=Path(d);shutil.copytree(QML,root/'qml');(root/'runtime').mkdir(mode=0o700)
            (root/'qml/Reglages.qml').write_text('pragma Singleton\nimport QtQuick\nQtObject {function t(fr,en){return en} function val(k,d){return d}}')
            (root/'qml/Agents.qml').write_text('pragma Singleton\nimport QtQuick\nQtObject {property var ias: ({claude:{couleur:"#d97757"},assistant:{couleur:"#10b981"}})}')
            singletons={'Reglages','Agents','Couleurs','AssistantEtat','JarvisEtat'}
            noms=['Reglages','Agents','Couleurs','AssistantEtat','JarvisEtat','Jarvis','JarvisChat','JarvisBouton','JarvisChamp','JarvisResultat','Assistant','AssistantReglages','AssistantCommande','AssistantOrbe','Texte','Ico','Etincelle','LogoAssistant','Defilement','Ligne','Rond']
            (root/'qml/qmldir').write_text('\n'.join(('singleton ' if n in singletons else '')+n+' 1.0 '+n+'.qml' for n in noms))
            if not absent:
                b=root/'.local/bin';b.mkdir(parents=True)
                script='''#!/usr/bin/env python3
import json,os,sys,time
from pathlib import Path
r=json.loads(sys.stdin.readline())
with Path(os.environ['HOME'],'calls').open('a') as f:f.write(json.dumps(dict(argv=sys.argv[1:],data=r))+'\\n')
time.sleep(.04)
if Path(sys.argv[0]).name=='nc-assistant':print(json.dumps(dict(ok=True,text='Réponse native')),flush=True);sys.exit()
op=r['op']
if op=='overview':
 data=dict(online=True,deploy_mode='server',gateway=dict(telegram_configured=True,discord_configured=True),management=dict(protocol=1,modules=[dict(id='shopping',name='Courses',enabled=True,description='Tes courses')],fields=[dict(key='DISCORD_TOKEN',label='Discord',secret=True,configured=True,value='',group='bots'),dict(key='ENABLE_TOOL_SHOPPING',label='Activer',kind='bool',value='1',group='shopping')]),catalogue=dict(shopping=[dict(id='add',label='Ajouter',fields=[dict(key='text',label='Articles')])]))
elif op=='models':data=dict(models=['model-a'])
elif op=='memory':data=dict(facts=[dict(id='one',text='Une mémoire')],profile=dict(city='Paris'))
elif op=='conversations':data=dict(conversations=[dict(id='conv-one',title='Conversation')])
elif op=='reminders':data=dict(reminders=[dict(id=1,message='Test',platform='telegram')])
elif op=='services':data=dict(services=[])
else:data=dict(success=True,message='Action terminée')
print(json.dumps(dict(ok=True,data=data)),flush=True)
'''
                for n in ('nc-assistant','nc-jarvis'):
                    p=b/n;p.write_text(script);p.chmod(0o755)
            shell=(('import QtTest\n' if evenements else '')+'''import QtQuick
import Quickshell
ShellRoot {
 id:racine
 property int etape:0
 property bool dansEtape:false
 property var dashboard:null
 // TEST_INPUT
 function trouver(item,nom){if(item.objectName===nom)return item;for(var i=0;i<item.children.length;i++){var r=trouver(item.children[i],nom);if(r)return r}return null}
 function verifier(ok,message){if(!ok){console.error(message);Qt.exit(2);throw new Error(message)}}
 function creer(){var c=Qt.createComponent("Jarvis.qml");verifier(c.status===Component.Ready,c.errorString());dashboard=c.createObject(racine);verifier(dashboard!==null,"création du cockpit");dashboard.afficher(Quickshell.screens[0].name);}
 Timer {interval:100;running:true;repeat:true;onTriggered:{
 if(racine.dansEtape)return
 racine.dansEtape=true
 try {
'''+scenario+'''
 }finally{racine.dansEtape=false}
 }}
 Timer {interval:9000;running:true;onTriggered:Qt.exit(9)}
}''')
            (root/'qml/shell.qml').write_text(shell.replace('// TEST_INPUT','TestCase {id:clavier;name:"DashboardInput";when:false}' if evenements else ''))
            env=dict(os.environ,HOME=d,QT_QPA_PLATFORM='offscreen',QT_QUICK_BACKEND='software',XDG_RUNTIME_DIR=str(root/'runtime'),XDG_CACHE_HOME=str(root/'cache'))
            env.pop('WAYLAND_DISPLAY',None)
            r=subprocess.run(['qs','--no-color','-p',str(root/'qml/shell.qml')],env=env,text=True,capture_output=True,timeout=12)
            output=r.stdout+r.stderr
            self.assertEqual(r.returncode,0,output)
            for error in ('ReferenceError','TypeError','Cannot assign','Binding loop','is not a type'):
                self.assertNotIn(error,output)
            p=root/'calls'
            return [json.loads(line) for line in p.read_text().splitlines()] if p.exists() else []

    def test_all_pages_load_and_share_the_island_chat_without_duplicate_request(self):
        calls=self.executer('''
if(etape===0){creer();etape++;return}
if(JarvisEtat.enCours||AssistantEtat.enCours)return
if(etape===1){verifier(JarvisEtat.administration,"adaptateur absent");dashboard.ouvrir("chat");AssistantEtat.brouillon="message partagé";AssistantEtat.envoyer();etape++}
else if(etape===2){verifier(AssistantEtat.messages.length===2,"chat perdu");dashboard.visible=false;verifier(AssistantEtat.messages[1].texte==="Réponse native","réponse");dashboard.visible=true;dashboard.ouvrir("modules");dashboard.moduleId="shopping";dashboard.configurerGroupe("shopping");etape++}
else if(etape===3){dashboard.formulaire("action","Ajouter",[{key:"text",label:"Articles"}]);dashboard.selection=Object.assign({},dashboard.selection,{action:"add"});dashboard.valeurs={text:"café"};dashboard.soumettre();verifier(!JarvisEtat.enCours,"action sans confirmation");verifier(dashboard.attente.params.params.text==="café","paramètres perdus");dashboard.attente=null;dashboard.ouvrir("session");etape++}
else if(etape===4){dashboard.ouvrir("memoire");etape++}
else if(etape===5){dashboard.ouvrir("conversations");etape++}
else if(etape===6){dashboard.ouvrir("rappels");etape++}
else if(etape===7){dashboard.ouvrir("configuration");dashboard.configurerGroupe("bots");etape++}
else if(etape===8){verifier(dashboard.selection.champs[0].secret,"champ secret non masqué");dashboard.valeurs={DISCORD_TOKEN:"private-ui-token"};dashboard.soumettre();verifier(dashboard.resumeConfirmation().indexOf("private-ui-token")<0,"secret dans la confirmation");dashboard.attente=null;dashboard.ouvrir("services");etape++}
else if(etape===9){dashboard.ouvrir("deploiement");etape++}
else if(etape===10){dashboard.ouvrir("accueil");etape++}
else{dashboard.destroy();Qt.quit()}
''')
        questions=[c for c in calls if 'question' in c['data']]
        self.assertEqual(len(questions),1)
        self.assertEqual(questions[0]['argv'],['requete-ile'])
        self.assertFalse(any(c['data'].get('confirmed') for c in calls))

    def test_dashboard_missing_helper_finishes_without_blocking_chat(self):
        self.executer('''
if(etape===0){creer();etape++;return}
if(!JarvisEtat.enCours){verifier(JarvisEtat.erreur!=="","erreur absente");dashboard.ouvrir("chat");dashboard.destroy();Qt.quit()}
''',absent=True)

    def test_close_reopen_and_screen_selection_keep_shell_and_chat_alive(self):
        calls=self.executer('''
if(etape===0){creer();AssistantEtat.brouillon="ne pas perdre";etape++;return}
if(JarvisEtat.enCours)return
if(etape===1||etape===3||etape===5){dashboard.close();verifier(!dashboard.visible,"fermeture incomplète");etape++;return}
if(etape===2||etape===4||etape===6){dashboard.afficher(Quickshell.screens[0].name);verifier(dashboard.visible&&dashboard.maximized&&!dashboard.fullscreen,"réouverture impossible (maximisée sous la barre, pas plein écran)");verifier(AssistantEtat.brouillon==="ne pas perdre","chat perdu");etape++;return}
if(etape===7){JarvisEtat.executer("session",{},false);etape++;return}
if(etape===8){dashboard.close();Qt.quit()}
''')
        self.assertTrue(any(c['data'].get('op')=='session' for c in calls),"Quickshell a quitté avant la réouverture")

    def test_escape_closes_completions_before_closing_dashboard(self):
        self.executer('''
if(etape===0){creer();dashboard.ouvrir("chat");etape++;return}
if(JarvisEtat.enCours)return
if(etape===1){
 var entree=trouver(dashboard.contentItem,"nc-assistant-input");verifier(entree!==null,"saisie absente")
 entree.forceActiveFocus();clavier.keyClick("/");clavier.keyClick("e");etape++
}else if(etape===2){
 verifier(trouver(dashboard.contentItem,"nc-jarvis-completions").visible,"complétion absente dans le vrai cockpit")
 clavier.keyClick(Qt.Key_Escape);etape++
}else if(etape===3){
 verifier(dashboard.visible,"Échap a fermé le dashboard au lieu des suggestions")
 verifier(!trouver(dashboard.contentItem,"nc-jarvis-completions").visible,"suggestions encore ouvertes")
 clavier.keyClick(Qt.Key_Escape);etape++
}else if(etape===4){verifier(!dashboard.visible,"second Échap n'a pas fermé le cockpit");Qt.quit()}
''',evenements=True)

    # Petite fenêtre de chat (Super + Alt + A) : vierge à l'ouverture, envoi par AssistantEtat, nouvelle conversation, Échap
    def test_compact_chat_window_is_blank_shares_the_session_and_closes_on_escape(self):
        calls=self.executer('''
if(etape===0){
 AssistantEtat.ajouter("vous","ancienne question");AssistantEtat.ajouter("assistant","ancienne réponse")
 var c=Qt.createComponent("JarvisChat.qml");verifier(c.status===Component.Ready,c.errorString());dashboard=c.createObject(racine);verifier(dashboard!==null,"création de la fenêtre")
 dashboard.afficher(Quickshell.screens[0].name);etape++;return}
if(AssistantEtat.enCours)return
if(etape===1){
 verifier(dashboard.visible&&dashboard.title==="JARVIS Chat","fenêtre absente ou mal nommée")
 verifier(dashboard.page.nombre===0,"conversation non vierge : "+dashboard.page.nombre)
 verifier(AssistantEtat.messages.length===2,"l'historique de l'île a été perdu")
 var entree=trouver(dashboard.contentItem,"nc-assistant-input");verifier(entree!==null&&entree.activeFocus,"saisie sans focus à l'ouverture")
 entree.forceActiveFocus();clavier.keyClick("s");clavier.keyClick("a");clavier.keyClick("l");clavier.keyClick("u");clavier.keyClick("t");clavier.keyClick(Qt.Key_Return);verifier(AssistantEtat.enCours,"Entrée n'envoie pas");etape++
}else if(etape===2){
 var conv=dashboard.page.conversation()
 verifier(conv.length===2&&conv[0].texte==="salut"&&conv[1].texte==="Réponse native","conversation de la fenêtre : "+JSON.stringify(conv))
 verifier(AssistantEtat.messages.length===4,"historique partagé : "+AssistantEtat.messages.length)
 trouver(dashboard.contentItem,"nc-jarvis-chat-new").clic();verifier(AssistantEtat.enCours,"nouvelle conversation sans reset");etape++
}else if(etape===3){
 verifier(dashboard.page.nombre===0,"fenêtre non vide après la nouvelle conversation")
 verifier(AssistantEtat.messages.length===1,"session non remise à zéro : "+AssistantEtat.messages.length)
 clavier.keyClick(Qt.Key_Escape);etape++
}else if(etape===4){verifier(!dashboard.visible,"Échap n'a pas fermé la fenêtre");dashboard.afficher(Quickshell.screens[0].name);verifier(dashboard.visible&&dashboard.page.nombre===0,"réouverture non vierge");Qt.quit()}
''',evenements=True)
        self.assertEqual([c['data']['question'] for c in calls if c['argv']==['requete-ile']],['salut','/reset'])


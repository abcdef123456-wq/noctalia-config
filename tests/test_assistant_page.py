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
    def executer(self, scenario, absent=False, lectureReglages=False, evenements=False, delai=.2, configuration=None, compact=False, dictee=None):
        with tempfile.TemporaryDirectory(prefix="nc-assistant-page-") as d:
            root = Path(d)
            (root / "run").mkdir(mode=0o700)
            (root / "assets").mkdir()
            if configuration is not None:
                (root / "catalogue.json").write_text(json.dumps(configuration))
            noms = ["Assistant.qml", "AssistantEtat.qml", "Defilement.qml", "Texte.qml", "Ico.qml",
                    "Etincelle.qml", "Pas.qml", "LogoAssistant.qml", "Couleurs.qml", "AssistantReglages.qml", "JarvisBouton.qml", "JarvisChamp.qml", "AssistantCommande.qml", "AssistantOrbe.qml", "AssistantPieces.qml"]
            if compact:
                noms.append("Compact.qml")
            for nom in noms + ["assets/assistant-animation.png", "assets/jarvis-animation.png"]:
                shutil.copy2(QML / nom, root / nom)
            (root / "Reglages.qml").write_text('pragma Singleton\nimport QtQuick\nQtObject {property string effets:"tous"; readonly property bool sobre: effets==="aucun"; function t(fr,en){return en} function val(k,d){return k==="EFFETS"?effets:d}}')
            (root / "Agents.qml").write_text('pragma Singleton\nimport QtQuick\nQtObject {property var ias: ({claude:{couleur:"#d97757",nom:"Claude"},assistant:{couleur:"#10b981"}}); property bool travaille:false; property bool attendTerminal:false; property var principale:null; property var attend:null; property string dernierFini:""; property string dernierFiniAgent:"claude"; function agent(s){return "claude"} function nom(s){return "Claude"}}')
            if compact:
                champs = {k:'""' for k in ('activiteType','heure','dateCourte','iconeLecteur','pochette','titre','artiste','appliCamera','appliMicro','casqueBatterie','casqueNom','telechargeFini')}
                champs.update({k:'false' for k in ('aMusique','enregistre','telecharge','pomodoro','pomoPause','muet','joue','branche','cameraActive','meteoPilule','jeu')})
                champs.update({k:'0' for k in ('minuteurFin','minuteurReste','volume','luminosite','pourcent','profil','debutVideo')})
                champs.update(meteo='({})',bandes='[0,0,0,0,0]',telechargements='[]',maintenant='new Date()')
                (root/'Partage.qml').write_text('pragma Singleton\nimport QtQuick\nQtObject {property bool indicateur: false}')
                (root/'Chaleur.qml').write_text('pragma Singleton\nimport QtQuick\nQtObject {property bool alerte: false; function titre(){return "CPU"}}')
                (root/'Etat.qml').write_text('pragma Singleton\nimport QtQuick\nQtObject {\n'+ '\n'.join('property var '+k+':'+v for k,v in champs.items())+'\nfunction duree(n){return "0:00"} function nomJoli(s){return s} function octets(n){return "0"}\n}')
            (root / "qmldir").write_text("\n".join(
                ("singleton " if nom in ("AssistantEtat.qml", "Couleurs.qml", "Reglages.qml", "Agents.qml", "Etat.qml", "Partage.qml", "Chaleur.qml") else "")
                + nom[:-4] + " 1.0 " + nom for nom in noms + ["Reglages.qml", "Agents.qml"] + (["Etat.qml", "Partage.qml", "Chaleur.qml"] if compact else [])))
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
if r["question"] in ("erreur","Option C"):
 print(json.dumps(dict(ok=False,error="Échec simulé")),flush=True);sys.exit(1)
if r["question"]=="invalide":print("not json",flush=True);sys.exit(0)
choix=dict(choices=["Option A","Option B","Option C"]) if r["question"]=="choix" else {}
print(json.dumps(dict(ok=True,text="<b>Réponse</b>\\n"+r["question"],**choix)),flush=True)
'''.replace('time.sleep(.2)',f'time.sleep({delai})'))
                helper.chmod(0o755)
                jarvis=bin/"nc-jarvis"
                jarvis.write_text('''#!/usr/bin/env python3
import json,os,sys
from pathlib import Path
r=json.loads(sys.stdin.readline())
with Path(os.environ['HOME'],'reglages-recus').open('a') as f:f.write(json.dumps(r)+'\\n')
session=dict(engine='codex',model='requested-model',effort='high')
catalogue=Path(os.environ['HOME'],'catalogue.json')
if catalogue.exists():
 data=json.loads(catalogue.read_text())
 if r['op']=='session.update':
  data['session'].update(r['params']);catalogue.write_text(json.dumps(data))
 print(json.dumps(dict(ok=True,data=data)),flush=True);sys.exit()
print(json.dumps(dict(ok=True,data=dict(session=session,engines=[dict(id='codex',name='Codex',installed=True,models=[dict(id='requested-model',name='Requested',efforts=['high','xhigh'])])]))),flush=True)
''')
                jarvis.chmod(0o755)
                if dictee is not None:
                    (root / "dictee.json").write_text(json.dumps(dictee))
                    faux = bin / "nc-dictee"
                    faux.write_text('''#!/usr/bin/env python3
import json,os,sys,time
from pathlib import Path
with Path(os.environ['HOME'],'dictee-recus').open('a') as f:f.write(json.dumps(sys.argv[1:])+'\\n')
time.sleep(.05)
print(json.dumps(json.loads(Path(os.environ['HOME'],'dictee.json').read_text())[sys.argv[1]]),flush=True)
''')
                    faux.chmod(0o755)
            shell=(('import QtTest\n' if evenements else '')+'''import QtQuick
import QtQuick.Window
import Quickshell
ShellRoot {
 id: test
 property int etape:0
 property bool dansEtape:false
 property var page:null
 property var memo:({})
 // TEST_INPUT
 function verifier(ok,message){if(!ok){console.error(message);Qt.exit(2);throw new Error(message)}}
 function trouver(item,nom){if(item.objectName===nom)return item;for(var i=0;i<item.children.length;i++){var r=trouver(item.children[i],nom);if(r)return r}return null}
 function creer(){var c=Qt.createComponent("Assistant.qml");verifier(c.status===Component.Ready,c.errorString());page=c.createObject(w.contentItem,{width:400,height:488});verifier(page!==null,"page absente")}
 Window {id:w;visible:true;width:432;height:520;color:"#151f2b"}
 Timer {interval:80;running:true;repeat:true;onTriggered:{
 if(test.dansEtape)return
 test.dansEtape=true
 try {
''' + scenario + '''
 }finally{test.dansEtape=false}
 }}
 Timer {interval:5000;running:true;onTriggered:Qt.exit(9)}
}''')
            (root/'shell.qml').write_text(shell.replace('// TEST_INPUT','TestCase {id:clavier;name:"ChatInput";when:false}\nfunction ecrire(texte){for(var i=0;i<texte.length;i++)clavier.keyClick(texte.charAt(i))}' if evenements else ''))
            env = dict(os.environ, HOME=d, QT_QPA_PLATFORM="offscreen", QT_QUICK_BACKEND="software",
                       XDG_RUNTIME_DIR=str(root / "run"), XDG_CACHE_HOME=str(root / "cache"))
            env.pop("WAYLAND_DISPLAY", None)
            r = subprocess.run(["qs", "--no-color", "-p", str(root / "shell.qml")], env=env,
                               capture_output=True, text=True, timeout=8)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertNotIn("ReferenceError", r.stdout + r.stderr)
            self.assertNotIn("TypeError", r.stdout + r.stderr)
            self.assertNotIn("Binding loop", r.stdout + r.stderr)
            self.assertNotIn("Cannot assign", r.stdout + r.stderr)
            recus = root / ("reglages-recus" if lectureReglages else "dictee-recus" if dictee is not None else "recus")
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
if(etape===0){for(var i=0;i<100;i++)AssistantEtat.ajouter("assistant","x".repeat(16000));verifier(AssistantEtat.messages.length<=3,"historique trop grand");AssistantEtat.messages=[];for(var j=0;j<100;j++)AssistantEtat.ajouter("vous","x");verifier(AssistantEtat.messages.length===24,"trop de messages");creer();verifier(page.nombre===24&&trouver(page,"nc-jarvis-message")!==null,"messages non affichés");AssistantEtat.brouillon="gardé";AssistantEtat.effacer();verifier(AssistantEtat.brouillon==="gardé","brouillon effacé");verifier(page.nombre===0,"affichage non vidé");etape=99;Qt.quit()}
''')   # etape=99 : la minuterie peut refaire un tour avant la fin du processus ; rejouer le flot redessinerait 100 fois les messages

    def test_quick_settings_preserve_draft_and_visual_stops_when_hidden(self):
        recus=self.executer('''
if(etape===0){creer();AssistantEtat.brouillon="brouillon";AssistantEtat.ouvrirReglages();etape++}
else if(etape===1&&!AssistantEtat.reglagesEnCours){verifier(AssistantEtat.reglagesDisponibles,"réglages absents");verifier(AssistantEtat.modele==="requested-model","modèle perdu");verifier(AssistantEtat.efforts.join(",")==="high,xhigh","efforts inventés");AssistantEtat.effort="xhigh";AssistantEtat.appliquerReglages();etape++}
else if(etape===2&&!AssistantEtat.reglagesEnCours){verifier(AssistantEtat.brouillon==="brouillon","brouillon perdu");AssistantEtat.ouvrirReglages();page.animationsActives=false;etape++}
else if(etape===3){page.visible=false;verifier(!page.visible,"page visible");Qt.quit()}
''',lectureReglages=True)
        writes=[r for r in recus if r['op']=='session.update']
        self.assertEqual(len(writes),1)
        self.assertTrue(writes[0]['confirmed'])
        self.assertEqual(writes[0]['params'],dict(engine='codex',model='requested-model',effort='xhigh'))
        self.assertEqual(len(recus),3)

    def test_orb_layout_lifecycle_and_complete_error_in_history(self):
        self.executer('''
if(etape===0){creer();etape++}
else if(etape===1){
 var logo=trouver(page,"nc-jarvis-hero"),orbe=trouver(page,"nc-jarvis-visual"),statut=trouver(page,"nc-jarvis-status")
 verifier(logo&&logo.running,"emblème arrêté sur page visible")
 verifier(orbe.width>140,"orbe écrasé à 400×488")
 verifier(orbe.mapToItem(page,0,orbe.height).y<=statut.mapToItem(page,0,0).y,"orbe superposé au statut")
 page.historiqueOuvert=true;verifier(!logo.running,"animation cachée par l’historique")
 page.historiqueOuvert=false;page.animationsActives=false;verifier(!logo.running,"effets désactivés ignorés")
 page.animationsActives=true;Reglages.effets="aucun";verifier(!logo.running,"préférence sans effets ignorée")
 Reglages.effets="tous";page.visible=false;verifier(!logo.running,"animation de page masquée")
 page.visible=true;page.width=434;page.height=588;AssistantEtat.erreur="Erreur très longue ".repeat(40);page.historiqueOuvert=true;etape++
} else if(etape===2){
 var longs=[];function chercher(i){if(i.text===AssistantEtat.erreur&&i.readOnly===true)longs.push(i);for(var j=0;j<i.children.length;j++)chercher(i.children[j])}chercher(page)
 verifier(longs.length===1&&longs[0].height>46,"erreur complète inaccessible dans l’historique")
 verifier(!trouver(page,"nc-jarvis-hero").running,"animation cachée encore active")
 Qt.quit()
}
''')

    def test_closing_settings_discards_unapplied_selection_without_server_write(self):
        recus=self.executer('''
if(etape===0){creer();AssistantEtat.ouvrirReglages();etape++}
else if(etape===1&&!AssistantEtat.reglagesEnCours){
 verifier(!AssistantEtat.reglagesModifies,"session confirmée marquée en attente")
 AssistantEtat.effort="xhigh";verifier(AssistantEtat.reglagesModifies,"choix non appliqué affiché comme actif")
 AssistantEtat.ouvrirReglages();verifier(AssistantEtat.effort==="high"&&!AssistantEtat.reglagesModifies,"choix annulé encore actif")
 verifier(!AssistantEtat.reglagesOuverts,"réglages restés ouverts");Qt.quit()
}
''',lectureReglages=True)
        self.assertEqual([r['op'] for r in recus],['quick-settings'])

    def test_markdown_latex_and_island_only_visual(self):
        self.executer('''
if(etape===0){
 creer()
 var f=AssistantEtat.formater("Voici **gras**, `code $x^2$` et $\\\\frac{a+b}{2} + \\\\alpha_0^2 \\\\leq \\\\sqrt{x}$\\n$$\\\\int_0^\\\\infty e^{-x} dx = 1$$")
 verifier(f.indexOf("**gras**")>=0,"markdown gras perdu")
 verifier(f.indexOf("`code $x^2$`")>=0,"code en ligne altéré")
 verifier(f.indexOf("(a+b)/2 + α₀² ≤ √x")>=0,"latex en ligne non converti: "+f)
 verifier(f.indexOf("∫₀^(∞) e⁻ˣ dx = 1")>=0||f.indexOf("∫₀")>=0,"latex bloc non converti: "+f)
 var orbe=trouver(page,"nc-jarvis-visual")
 verifier(orbe&&orbe.visible,"orbe invisible dans la Dynamic Island")
 page.dansDashboard=true
 verifier(!orbe.visible,"orbe visible dans le dashboard plein écran")
 Qt.quit()
}
''')

    def test_links_are_clickable_and_text_stays_selectable(self):
        self.executer('''
if(etape===0){
 creer();memo.liens=[]
 page.ouvrirLien=function(lien){memo.liens.push(lien)}
 AssistantEtat.ajouter("assistant","[Documentation](https://example.test/doc)\\n\\n[PDF](file:///tmp/rapport.pdf)\\n\\nhttps://example.test/guide")
 etape++
}else if(etape===1){
 var message=trouver(page,"nc-jarvis-message")
 verifier(message.readOnly&&message.selectByMouse,"sélection du texte désactivée")
 var urls=["https://example.test/doc","file:///tmp/rapport.pdf","https://example.test/guide"]
 for(var k=0;k<urls.length;k++){
  var point=null
  for(var p=0;p<message.length&&!point;p++){
   var r=message.positionToRectangle(p),s=message.positionToRectangle(p+1)
   var x=s.y===r.y?(r.x+s.x)/2:r.x+2,y=r.y+r.height/2
   if(message.linkAt(x,y)===urls[k])point={x:x,y:y}
  }
  verifier(point!==null,"lien non reconnu : "+urls[k])
  message.forceActiveFocus();clavier.mouseMove(message,point.x,point.y)
  clavier.mouseClick(message,point.x,point.y,Qt.LeftButton)
 }
 verifier(memo.liens.join("|")===urls.join("|"),"clic non transmis : "+memo.liens.join("|"))
 message.forceActiveFocus();clavier.keyClick(Qt.Key_A,Qt.ControlModifier)
 verifier(message.selectedText.indexOf("Documentation")>=0,"texte non sélectionnable")
 var cible="https://example.test/fichier_a?prix=$x$"
 verifier(AssistantEtat.formater("[Doc]("+cible+") et \\\\alpha").indexOf(cible)>=0,"URL altérée par le rendu mathématique")
 Qt.quit()
}
''',evenements=True)

    def test_choix_de_jarvis_en_pastilles_clic_et_clavier(self):
        """Issue #7 : les choix d'une réponse (champ choices) deviennent des pastilles sous la dernière réponse ; un clic
        envoie le libellé par le chemin de l'envoi tapé (le brouillon reste), puis les pastilles se grisent ; une réponse
        sans choix n'en montre aucune ; Entrée sur une pastille focalisée l'envoie aussi. NC_CAPTURE : PNG du rendu."""
        recus = self.executer('''
var tous=function tous(item,acc){if(item.objectName==="nc-jarvis-choix-pastille"&&item.visible)acc.push(item);for(var i=0;i<item.children.length;i++)tous(item.children[i],acc);return acc}
var capture=function(nom){var c=Quickshell.env("NC_CAPTURE");if(!c){memo.capture=true;return}memo.capture=false
 page.grabToImage(function(r){r.saveToFile(c+"-"+nom+".png");memo.capture=true})}
if(etape===0){creer();AssistantEtat.brouillon="choix";AssistantEtat.envoyer();etape++}
else if(etape===1&&!AssistantEtat.enCours){
 var p=tous(page,[])
 verifier(p.length===3,"3 pastilles attendues : "+p.length)
 verifier(p.map(x=>x.texte).join("|")==="Option A|Option B|Option C","libellés : "+p.map(x=>x.texte).join("|"))
 verifier(p.every(x=>x.enabled&&!x.fait&&x.height===32&&x.radius===16),"pastilles actives, arrondies")
 var bulle=p[0].parent.parent.parent
 verifier(bulle.modelData.num===AssistantEtat.messages[AssistantEtat.messages.length-1].num,"sous le dernier message")
 capture("actives");etape++}
else if(etape===2&&memo.capture){
 var p=tous(page,[]);AssistantEtat.brouillon="brouillon gardé"
 clavier.mouseMove(p[1],20,16);clavier.mouseClick(p[1],20,16,Qt.LeftButton)
 verifier(AssistantEtat.enCours,"le clic n'envoie pas")
 verifier(tous(page,[]).length===0,"pastilles pendant la demande")
 verifier(AssistantEtat.messages[1].choixFait==="Option B","choix non marqué")
 verifier(AssistantEtat.messages[2].role==="vous"&&AssistantEtat.messages[2].texte==="Option B","message envoyé : "+JSON.stringify(AssistantEtat.messages[2]))
 verifier(AssistantEtat.brouillon==="brouillon gardé","brouillon écrasé par le choix")
 AssistantEtat.choisir(AssistantEtat.messages[1].num,"Option A");etape++}
else if(etape===3&&!AssistantEtat.enCours){
 verifier(AssistantEtat.messages.length===4,"second choix envoyé sur le même message : "+AssistantEtat.messages.length)
 verifier(tous(page,[]).length===0,"pastilles sous une réponse sans choix")
 verifier(!trouver(page,"nc-jarvis-choix").visible,"rangée de choix visible")
 AssistantEtat.brouillon="";AssistantEtat.envoyer("choix");etape++}
else if(etape===4&&!AssistantEtat.enCours){
 var p=tous(page,[]);verifier(p.length===3,"nouvelles pastilles : "+p.length)
 p[2].forceActiveFocus();verifier(p[2].activeFocus,"pastille non focalisable au clavier")
 clavier.keyClick(Qt.Key_Return);verifier(AssistantEtat.enCours,"Entrée n'envoie pas le choix");etape++}
else if(etape===5&&!AssistantEtat.enCours){
 // Échec de l'envoi : la réponse aux choix reste la dernière, ses pastilles restent grisées, le choix fait marqué
 verifier(AssistantEtat.erreur==="Échec simulé","erreur : "+AssistantEtat.erreur)
 var p=tous(page,[]);verifier(p.length===3&&p.every(x=>!x.enabled),"pastilles non grisées après le choix")
 verifier(p[2].fait&&!p[0].fait,"choix fait non marqué")
 capture("choisie");etape++}
else if(etape===6&&memo.capture){Qt.quit()}
''', evenements=True)
        self.assertEqual([r["payload"]["question"] for r in recus], ["choix", "Option B", "choix", "Option C"])

    def test_thinking_dots_follow_the_real_request_and_stop_when_hidden(self):
        recus=self.executer('''
if(etape===0){creer();AssistantEtat.brouillon="réflexion";AssistantEtat.envoyer();etape++}
else if(etape===1){
 var bulle=trouver(page,"nc-jarvis-thinking"),dot=trouver(page,"nc-jarvis-thinking-dot")
 verifier(bulle.visible&&page.animeAttente,"bulle absente pendant la demande")
 memo.opacity=dot.opacity;etape++
}else if(etape===2){
 var dot=trouver(page,"nc-jarvis-thinking-dot")
 verifier(Math.abs(dot.opacity-memo.opacity)>.02,"points non animés")
 page.visible=false;memo.opacity=dot.opacity;etape++
}else if(etape===3){
 verifier(!page.animeAttente,"animation encore active sur page cachée")
 verifier(Math.abs(trouver(page,"nc-jarvis-thinking-dot").opacity-memo.opacity)<.001,"animation cachée consomme encore")
 page.visible=true;Reglages.effets="aucun";verifier(!page.animeAttente,"effets désactivés ignorés")
 Reglages.effets="tous";page.animationsActives=false;verifier(!page.animeAttente,"cockpit masqué ignoré")
 etape++
}else if(etape===4&&!AssistantEtat.enCours){
 verifier(!trouver(page,"nc-jarvis-thinking").visible,"points restés après la réponse")
 verifier(AssistantEtat.messages.length===2,"faux message conservé dans l'historique")
 Qt.quit()
}
''',delai=.8)
        self.assertEqual(len(recus),1)

    def test_reopen_resize_and_recreate_restore_the_end_after_layout(self):
        self.executer('''
function enBas(){var h=trouver(page,"nc-jarvis-history");verifier(h.contentHeight>h.height*2,"historique de test trop court");verifier(Math.abs(h.contentY-Math.max(0,h.contentHeight-h.height))<1,"retour en tête : "+h.contentY+" / "+h.contentHeight+" / "+h.height)}
if(etape===0){for(var i=0;i<18;i++)AssistantEtat.ajouter("assistant",("Message "+i+" ligne longue\\n").repeat(12));creer();etape++}
else if(etape===1){enBas();page.defiler(1);verifier(!page.suivreFin,"lecture des anciens messages empêchée");etape++}
else if(etape===2){page.visible=false;etape++}
else if(etape===3){page.visible=true;etape++}
else if(etape===4){enBas();page.width=330;page.height=410;etape++}
else if(etape===5){enBas();AssistantEtat.reglagesOuverts=true;etape++}
else if(etape===6){AssistantEtat.reglagesOuverts=false;etape++}
else if(etape===7){enBas();page.destroy();creer();page.dansDashboard=true;etape++}
else if(etape===8){enBas();page.defiler(1);page.animationsActives=false;etape++}
else if(etape===9){page.animationsActives=true;etape++}
else if(etape===10){enBas();Qt.quit()}
''')

    def test_live_command_completion_by_keyboard_in_both_chat_modes(self):
        for dashboard in (False,True):
            with self.subTest(dashboard=dashboard):
                recus=self.executer('''
if(etape===0){creer();page.dansDashboard=DASHBOARD;trouver(page,"nc-assistant-input").forceActiveFocus();etape++}
else if(etape===1){
 ecrire("/e");verifier(page.propositionsVisibles,"suggestions absentes")
 verifier(page.propositions.some(p=>p.texte==="/engine")&&page.propositions.some(p=>p.texte==="/effort"),"filtrage incorrect")
 clavier.keyClick(Qt.Key_Down)
 verifier(page.indiceSuggestion===1,"flèche ignorée : "+page.indiceSuggestion+" / "+page.propositions.map(p=>p.texte).join(","))
 memo.choisi=page.propositions[page.indiceSuggestion].texte
 clavier.keyClick(Qt.Key_Return)
 verifier(AssistantEtat.brouillon==="/effort ","flèche/Entrée n'a pas complété : "+AssistantEtat.brouillon+" attendu "+memo.choisi)
 verifier(!AssistantEtat.enCours,"complétion envoyée au serveur")
 clavier.keyClick(Qt.Key_A,Qt.ControlModifier);ecrire("/rapp");clavier.keyClick(Qt.Key_Tab)
 verifier(AssistantEtat.brouillon==="/rappel ","Tab n'a pas complété")
 clavier.keyClick(Qt.Key_A,Qt.ControlModifier);ecrire("/m");clavier.keyClick(Qt.Key_Escape)
 verifier(!page.propositionsVisibles,"Échap n'a pas fermé les propositions")
 ecrire("o");verifier(page.propositionsVisibles,"liste non actualisée après Échap")
 clavier.keyClick(Qt.Key_A,Qt.ControlModifier);ecrire("/h");clavier.keyClick(Qt.Key_Return)
 verifier(AssistantEtat.brouillon==="/help"&&!AssistantEtat.enCours,"préfixe envoyé au lieu d'être complété")
 clavier.keyClick(Qt.Key_Return);etape++
}else if(etape===2&&!AssistantEtat.enCours){
 verifier(AssistantEtat.messages.length===2,"commande non envoyée une seule fois")
 verifier(!page.propositionsVisibles,"liste restée après envoi")
 Qt.quit()
}
'''.replace('DASHBOARD','true' if dashboard else 'false'),evenements=True)
                self.assertEqual(len(recus),1)
                self.assertEqual(recus[0]['payload']['question'],'/help')

    def test_completion_preserves_arguments_and_supports_aliases_without_requests(self):
        recus=self.executer('''
if(etape===0){
 creer();var entree=trouver(page,"nc-assistant-input")
 AssistantEtat.brouillon="/rapp 15m sortir le pain";entree.cursorPosition=5
 verifier(page.propositions.length===2&&page.propositions[0].texte==="/rappel","préfixe avec arguments non reconnu (/rappel puis /rappels)")
 page.completer(0);verifier(AssistantEtat.brouillon==="/rappel 15m sortir le pain","arguments écrasés")
 verifier(entree.cursorPosition===7,"curseur déplacé au mauvais endroit")
 AssistantEtat.brouillon="/sh";entree.cursorPosition=3;page.completer(0)
 verifier(AssistantEtat.brouillon==="/shopping ","alias anglais non complété")
 verifier(!AssistantEtat.proposerCommandes("question /help",14).length,"complétion dans du texte normal")
 verifier(!AssistantEtat.proposerCommandes("/rappel 15m",11).length,"complétion dans un argument")
 verifier(!AssistantEtat.proposerCommandes("/inconnu",8).length,"commande inventée")
 Qt.quit()
}
''')
        self.assertFalse(recus)

    def test_mouse_completion_inserts_without_sending(self):
        recus=self.executer('''
if(etape===0){creer();trouver(page,"nc-assistant-input").forceActiveFocus();ecrire("/br");etape++}
else if(etape===1){
 var popup=trouver(page,"nc-jarvis-completions"),list=popup.children[0]
 verifier(popup.visible&&list.count===1,"proposition /briefing absente")
 var option=list.itemAtIndex(0);verifier(option!==null,"ligne non créée")
 clavier.mouseMove(option,30,20);clavier.mouseClick(option,30,20,Qt.LeftButton)
 verifier(AssistantEtat.brouillon==="/briefing","clic non complété")
 verifier(!AssistantEtat.enCours&&!popup.visible,"clic a envoyé au lieu de compléter")
 Qt.quit()
}
''',evenements=True)
        self.assertFalse(recus)


    def test_model_families_and_reasoning_send_real_ids_only_after_apply(self):
        models = [dict(id='gemini-flash-'+e, name='Gemini Flash ('+e+')') for e in ('low','medium','high')]
        models += [dict(id='gemini-argon-'+e, name='Gemini Argon ('+e+')') for e in ('low','medium','high')]
        models += [dict(id='claude-opus-4-6-thinking',name='Claude Opus 4.6 (Thinking)'),dict(id='claude-sonnet',name='Claude Sonnet',efforts='high')]
        config=dict(session=dict(engine='agy',model='gemini-flash-low',effort='low'),engines=[dict(id='agy',name='Antigravity',installed=True,models=models,efforts=['low','medium','high'])])
        recus=self.executer('''
if(etape===0){creer();AssistantEtat.lireReglages();etape++}
else if(etape===1&&!AssistantEtat.reglagesEnCours){
 verifier(AssistantEtat.famillesModeles.join(",")==="Flash,Argon,Opus,Sonnet","familles incohérentes")
 for(var nom of AssistantEtat.famillesModeles)verifier(trouver(page,"nc-jarvis-model-"+nom.toLowerCase()).enabled,"famille absente : "+nom)
 var bouton=trouver(page,"nc-jarvis-model-argon");clavier.mouseClick(bouton,bouton.width/2,bouton.height/2)
 verifier(AssistantEtat.modele==="gemini-argon-low","mauvais identifiant Argon")
 var effort=trouver(page,"nc-jarvis-effort-high");clavier.mouseClick(effort,effort.width/2,effort.height/2)
 verifier(AssistantEtat.modele==="gemini-argon-high"&&AssistantEtat.effort==="high","modèle/effort contradictoires")
 verifier(AssistantEtat.sessionReglages.model==="gemini-flash-low"&&AssistantEtat.reglagesModifies,"sélection prétendue confirmée")
 etape++
}else if(etape===2){
 var appliquer=trouver(page,"nc-jarvis-apply-model");verifier(appliquer.visible,"application absente")
 clavier.mouseClick(appliquer,appliquer.width/2,appliquer.height/2);verifier(AssistantEtat.reglagesEnCours,"clic Appliquer perdu");etape++
}else if(etape===3&&!AssistantEtat.reglagesEnCours){
 verifier(!AssistantEtat.reglagesModifies&&AssistantEtat.sessionReglages.model==="gemini-argon-high","confirmation serveur perdue")
 AssistantEtat.choisirFamille("Opus");verifier(AssistantEtat.modele==="claude-opus-4-6-thinking","mauvais Opus")
 // Opus : réflexion intégrée, aucun effort (agy refuse --effort) ; l'effort hérité (high) n'est pas gardé
 for(var n of ["low","medium","high"]){verifier(AssistantEtat.modelePourEffort(n)===null,"Opus accepte l'effort "+n);verifier(!trouver(page,"nc-jarvis-effort-"+n).enabled,"bouton "+n+" actif sous Opus")}
 verifier(AssistantEtat.effort==="","effort hérité gardé sous Opus : "+AssistantEtat.effort)
 AssistantEtat.choisirEffort("high");verifier(AssistantEtat.modele==="claude-opus-4-6-thinking"&&AssistantEtat.effort==="","effort imposé à Opus")
 // Sonnet : les trois niveaux du moteur (son champ efforts n'est pas un tableau : ignoré)
 AssistantEtat.choisirFamille("Sonnet");verifier(AssistantEtat.modele==="claude-sonnet","mauvais Sonnet")
 for(var n2 of ["low","medium","high"]){verifier(AssistantEtat.modelePourEffort(n2)==="claude-sonnet","Sonnet refuse "+n2);verifier(trouver(page,"nc-jarvis-effort-"+n2).enabled,"bouton "+n2+" grisé sous Sonnet")}
 AssistantEtat.choisirEffort("medium");verifier(AssistantEtat.effort==="medium","Sonnet : effort non appliqué")
 // Flash : les identifiants -low, -medium, -high
 AssistantEtat.choisirFamille("Flash");verifier(AssistantEtat.modele==="gemini-flash-medium","effort oublié au changement de famille : "+AssistantEtat.modele)
 for(var n3 of ["low","medium","high"]){AssistantEtat.choisirEffort(n3);verifier(AssistantEtat.modele==="gemini-flash-"+n3&&AssistantEtat.effort===n3,"Flash "+n3)}
 page.width=330;page.height=410;etape++
}else if(etape===4){
 var low=trouver(page,"nc-jarvis-effort-low"),high=trouver(page,"nc-jarvis-effort-high")
 verifier(low.mapToItem(page,0,0).x>=0&&high.mapToItem(page,high.width,0).x<=page.width,"réflexion hors du padding")
 Qt.quit()
}
''',lectureReglages=True,evenements=True,configuration=config)
        updates=[r for r in recus if r['op']=='session.update']
        self.assertEqual(len(updates),1)
        self.assertEqual(updates[0]['params'],dict(engine='agy',model='gemini-argon-high',effort='high'))
        self.assertTrue(updates[0]['confirmed'])

    def test_unadvertised_family_and_encoded_effort_are_disabled(self):
        config=dict(session=dict(engine='agy',model='gemini-flash-low',effort='low'),engines=[dict(id='agy',name='Antigravity',installed=True,models=[dict(id='gemini-flash-low',name='Flash')],efforts=['low','medium','high'])])
        self.executer('''
if(etape===0){creer();AssistantEtat.lireReglages();etape++}
else if(etape===1&&!AssistantEtat.reglagesEnCours){
 verifier(!trouver(page,"nc-jarvis-model-argon").enabled,"Argon inventé")
 verifier(!trouver(page,"nc-jarvis-effort-medium").enabled,"variante non annoncée activée")
 AssistantEtat.choisirFamille("Argon");AssistantEtat.choisirEffort("medium")
 verifier(AssistantEtat.modele==="gemini-flash-low"&&AssistantEtat.effort==="low","identifiant inventé")
 AssistantEtat.moteur="codex";verifier(AssistantEtat.modelePourFamille("Flash")===null,"catalogue d’un autre moteur")
 Qt.quit()
}
''',configuration=config)

    def test_home_shows_short_status_while_history_keeps_complete_output(self):
        self.executer('''
if(etape===0){
 creer();AssistantEtat.reglagesDemandes=true
 AssistantEtat.ajouter("assistant","Sortie privée très longue avec https://example.test/rapport")
 page.historiqueOuvert=false;etape++
}else if(etape===1){
 var statut=trouver(page,"nc-jarvis-status")
 verifier(statut.libelleStatut==="Reply received — open conversation","sortie brute dans l’accueil : "+statut.libelleStatut)
 verifier(AssistantEtat.messages[0].texte.indexOf("Sortie privée")===0,"sortie complète supprimée")
 AssistantEtat.erreur="Détail technique privé";verifier(statut.libelleStatut.indexOf("Détail")<0,"erreur brute dans l’accueil")
 AssistantEtat.enCours=true;verifier(statut.libelleStatut==="Thinking…","attente masquée par l’erreur")
 AssistantEtat.enCours=false;page.historiqueOuvert=true;etape++
}else if(etape===2){
 var message=trouver(page,"nc-jarvis-message");verifier(message.text.indexOf("https://example.test/rapport")>=0,"conversation altérée")
 Qt.quit()
}
''')

    def test_reading_model_catalog_does_not_delay_chat_but_writes_still_block_send(self):
        calls=self.executer('''
if(etape===0){
 creer();AssistantEtat.lireReglages();AssistantEtat.brouillon="pendant lecture"
 verifier(AssistantEtat.reglagesEnCours,"catalogue non démarré")
 AssistantEtat.envoyer();verifier(AssistantEtat.enCours,"lecture du catalogue bloque le chat");etape++
}else if(etape===1&&!AssistantEtat.enCours&&!AssistantEtat.reglagesEnCours){
 AssistantEtat.effort="xhigh";AssistantEtat.appliquerReglages();AssistantEtat.brouillon="après application"
 AssistantEtat.envoyer();verifier(!AssistantEtat.enCours,"écriture concurrente à une demande");etape++
}else if(etape===2&&!AssistantEtat.reglagesEnCours){AssistantEtat.envoyer();verifier(AssistantEtat.enCours,"chat bloqué après application");etape++}
else if(etape===3&&!AssistantEtat.enCours){verifier(AssistantEtat.messages.length===4,"demande perdue ou doublée");Qt.quit()}
''')
        self.assertEqual([r['payload']['question'] for r in calls],['pendant lecture','après application'])

    def test_active_pill_and_send_spinner_survive_hidden_chat_then_fade_after_reply(self):
        self.executer('''
if(etape===0){
 creer();AssistantEtat.reglagesDemandes=true
 var c=Qt.createComponent("Compact.qml");verifier(c.status===Component.Ready,c.errorString())
 memo.pilule=c.createObject(w.contentItem,{width:300,height:30});memo.debut=Date.now()
 AssistantEtat.brouillon="test";AssistantEtat.envoyer();page.visible=false;etape++
}else if(etape===1){
 if(Date.now()-memo.debut<300)return
 verifier(memo.pilule.mode==="jarvis","inférence absente de la pilule")
 var pill=trouver(memo.pilule,"nc-jarvis-pill"),logo=trouver(pill,"nc-assistant-logo")
 verifier(logo.running,"logo de pilule arrêté : anime="+logo.anime+" visible="+logo.visible+" pill="+pill.visible+" op="+pill.opacity+" c="+memo.pilule.visible+" enCours="+AssistantEtat.enCours)
 page.visible=true
 var bouton=trouver(page,"nc-jarvis-send"),spinner=trouver(bouton,"nc-assistant-button-spinner")
 verifier(bouton.occupe&&bouton.icone!=="stop"&&spinner.visible&&spinner.anime,"faux bouton stop ou spinner absent")
 page.animationsActives=false;verifier(!spinner.anime,"animation désactivée ignorée")
 page.animationsActives=true;page.visible=false;verifier(!spinner.anime,"spinner sur page masquée")
 etape++
}else if(etape===2&&!AssistantEtat.enCours){
 verifier(AssistantEtat.reponseRecente&&memo.pilule.mode==="jarvis-fini","confirmation absente")
 verifier(!trouver(trouver(memo.pilule,"nc-jarvis-pill"),"nc-assistant-logo").running,"logo continue après la réponse")
 memo.fin=Date.now();etape++
}else if(etape===3&&Date.now()-memo.fin>3200){
 verifier(!AssistantEtat.reponseRecente&&memo.pilule.mode==="repos","confirmation ne disparaît pas")
 Qt.quit()
}
''',delai=.7,compact=True)

    def test_error_does_not_claim_reply_and_new_request_resets_completion(self):
        self.executer('''
if(etape===0){creer();AssistantEtat.brouillon="erreur";AssistantEtat.envoyer();etape++}
else if(etape===1&&!AssistantEtat.enCours){verifier(!AssistantEtat.reponseRecente&&AssistantEtat.activitePilule==="","erreur présentée comme réponse");AssistantEtat.brouillon="succès";AssistantEtat.envoyer();etape++}
else if(etape===2&&!AssistantEtat.enCours){verifier(AssistantEtat.reponseRecente,"réponse non signalée");AssistantEtat.brouillon="encore";AssistantEtat.envoyer();verifier(!AssistantEtat.reponseRecente&&AssistantEtat.activitePilule==="jarvis","ancienne confirmation conservée");etape++}
else if(etape===3&&!AssistantEtat.enCours){Qt.quit()}
''')

    # Dictée vocale (bouton micro → nc-dictee start / stop) : le texte transcrit va dans le brouillon, sans envoi
    def test_dictation_fills_draft_without_sending(self):
        appels = self.executer('''
if(etape===0){creer();AssistantEtat.brouillon="Note :";memo.micro=trouver(page,"nc-jarvis-mic");verifier(memo.micro!==null,"micro absent");memo.micro.clic();verifier(page.ecouteVocale,"écoute non démarrée");verifier(page.information==="Listening…","badge écoute : "+page.information);etape++}
else if(etape===1&&page.ecouteVocale&&Date.now()-memo.t0>300){memo.micro.clic();verifier(!page.ecouteVocale,"écoute non arrêtée");verifier(page.information==="Transcribing…","badge transcription : "+page.information);etape++}
else if(etape===1){memo.t0=memo.t0||Date.now()}
else if(etape===2&&page.information===""){verifier(AssistantEtat.brouillon==="Note : bonjour jarvis","brouillon : "+AssistantEtat.brouillon);verifier(trouver(page,"nc-assistant-input").activeFocus,"saisie sans focus");verifier(AssistantEtat.messages.length===0&&!AssistantEtat.enCours,"envoi automatique");Qt.quit()}
''', dictee={"start": {"ok": True, "recording": True}, "stop": {"ok": True, "text": " bonjour jarvis ", "engine": "test"}})
        self.assertEqual(appels, [["start"], ["stop"]])

    def test_dictation_errors_are_shown_without_crash(self):
        appels = self.executer('''
if(etape===0){creer();memo.micro=trouver(page,"nc-jarvis-mic");memo.micro.clic();memo.micro.clic();verifier(page.ecouteVocale,"second clic pris pour un arrêt");etape++}
else if(etape===1&&page.ecouteVocale&&Date.now()-memo.t0>300){memo.micro.clic();etape++}
else if(etape===1){memo.t0=memo.t0||Date.now()}
else if(etape===2&&page.information!=="Transcribing…"){verifier(page.information==="Transcription impossible : serveur arrêté","erreur : "+page.information);verifier(!page.ecouteVocale&&AssistantEtat.brouillon==="","brouillon modifié");trouver(page,"nc-jarvis-voice-output").clic();verifier(page.information==="Voice output is not configured on this client.","haut-parleur : "+page.information);verifier(!page.ecouteVocale,"haut-parleur lance une écoute");Qt.quit()}
''', dictee={"start": {"ok": True, "recording": True}, "stop": {"ok": False, "error": "Transcription impossible : serveur arrêté"}})
        self.assertEqual(appels, [["start"], ["stop"]], "double clic : un seul démarrage ; haut-parleur : aucun appel")

    def test_dictation_start_failure_resets_listening(self):
        self.executer('''
if(etape===0){creer();trouver(page,"nc-jarvis-mic").clic();verifier(page.ecouteVocale,"écoute non démarrée");etape++}
else if(etape===1&&!page.ecouteVocale){verifier(page.information==="Micro coupé","erreur : "+page.information);Qt.quit()}
''', dictee={"start": {"ok": False, "error": "Micro coupé"}})


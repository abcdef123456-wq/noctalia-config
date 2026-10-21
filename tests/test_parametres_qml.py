"""Fenêtre graphique des réglages (Parametres.qml) hors écran, avec un faux nc-reglages : lecture du catalogue, recherche
sans accent dans toutes les sections, bascule oui/non et remise à la config par « set » / « reset », relecture après."""
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
import json,os,sys
from pathlib import Path
H=Path(os.environ['HOME']); etat=H/'etat.json'
d=json.loads(etat.read_text()) if etat.exists() else {"SOURIS_VITESSE":"0","GESTES":"oui","FENETRES_FLOU_FORCE":"normal"}
with (H/'calls').open('a') as f: f.write(json.dumps(sys.argv[1:])+'\n')
a=sys.argv[1:]
if a[0]=='catalogue':
    print(json.dumps([
      dict(cle="SOURIS_VITESSE",section="Clavier et souris",sectionNom="Clavier et souris",nom="Vitesse du pointeur",genre="entier",defaut="0",aide="",choix=[],mini=-10,maxi=10,pas=1,unite="",zero="",valeur=d["SOURIS_VITESSE"],affiche=d["SOURIS_VITESSE"],modifie=d["SOURIS_VITESSE"]!="0",groupe="hypr"),
      dict(cle="GESTES",section="Clavier et souris",sectionNom="Clavier et souris",nom="Gestes du pavé tactile",genre="ouinon",defaut="oui",aide="Trois doigts : bureaux.",choix=[["oui","Oui"],["non","Non"]],mini=0,maxi=100,pas=1,unite="",zero="",valeur=d["GESTES"],affiche="Oui" if d["GESTES"]=="oui" else "Non",modifie=d["GESTES"]!="oui",groupe="hypr"),
      dict(cle="FENETRES_FLOU_FORCE",section="Fenêtres",sectionNom="Fenêtres",nom="Force du flou",genre="choix",defaut="normal",aide="Derrière les fenêtres transparentes.",choix=[["leger","Léger"],["normal","Normal"],["fort","Fort"]],mini=0,maxi=100,pas=1,unite="",zero="",valeur=d["FENETRES_FLOU_FORCE"],affiche=d["FENETRES_FLOU_FORCE"].capitalize(),modifie=d["FENETRES_FLOU_FORCE"]!="normal",groupe="hypr"),
    ],ensure_ascii=False))
elif a[0]=='set': d[a[1]]=a[2]; etat.write_text(json.dumps(d)); print(a[1]+" : "+a[2])
elif a[0]=='reset': d[a[1]]={"SOURIS_VITESSE":"0","GESTES":"oui","FENETRES_FLOU_FORCE":"normal"}[a[1]]; etat.write_text(json.dumps(d)); print("Valeur de la config remise.")
'''


@unittest.skipUnless(shutil.which("qs"), "Quickshell requis")
class FenetreReglages(unittest.TestCase):
    def executer(self, scenario, evenements=False):
        with tempfile.TemporaryDirectory(prefix="nc-reglages-qml-") as d:
            root = Path(d); shutil.copytree(QML, root / "qml"); (root / "runtime").mkdir(mode=0o700)
            (root / "qml/Reglages.qml").write_text('pragma Singleton\nimport QtQuick\nQtObject {function t(fr,en){return fr} function val(k,d){return d}}')
            noms = ["Reglages", "Couleurs", "Parametres", "AssistantCommande", "Texte", "Ico"]
            (root / "qml/qmldir").write_text("\n".join(("singleton " if n in ("Reglages", "Couleurs") else "") + n + " 1.0 " + n + ".qml" for n in noms))
            b = root / ".local/bin"; b.mkdir(parents=True)
            (b / "nc-reglages").write_text(FAUX); (b / "nc-reglages").chmod(0o755)
            (root / "qml/shell.qml").write_text((('import QtTest\n' if evenements else '') + '''import QtQuick
import Quickshell
ShellRoot {
 id:racine
 property int etape:0
 property bool dansEtape:false
 property var fen:null
 // TEST_INPUT
 function trouver(item,nom){if(item.objectName===nom)return item;for(var i=0;i<item.children.length;i++){var r=trouver(item.children[i],nom);if(r)return r}return null}
 function verifier(ok,message){if(!ok){console.error(message);Qt.exit(2);throw new Error(message)}}
 function creer(){var c=Qt.createComponent("Parametres.qml");verifier(c.status===Component.Ready,c.errorString());fen=c.createObject(racine);verifier(fen!==null,"création");fen.afficher(Quickshell.screens[0].name)}
 Timer {interval:100;running:true;repeat:true;onTriggered:{
 if(racine.dansEtape)return
 racine.dansEtape=true
 try {
''' + scenario + '''
 }finally{racine.dansEtape=false}
 }}
 Timer {interval:9000;running:true;onTriggered:Qt.exit(9)}
}''').replace('// TEST_INPUT', 'TestCase {id:clavier;name:"Reglages";when:false}' if evenements else ''))
            env = dict(os.environ, HOME=d, QT_QPA_PLATFORM="offscreen", QT_QUICK_BACKEND="software", XDG_RUNTIME_DIR=str(root / "runtime"), XDG_CACHE_HOME=str(root / "cache"))
            env.pop("WAYLAND_DISPLAY", None)
            r = subprocess.run(["qs", "--no-color", "-p", str(root / "qml/shell.qml")], env=env, text=True, capture_output=True, timeout=12)
            sortie = r.stdout + r.stderr
            self.assertEqual(r.returncode, 0, sortie)
            for erreur in ("ReferenceError", "TypeError", "Cannot assign", "Binding loop", "is not a type"):
                self.assertNotIn(erreur, sortie)
            p = root / "calls"
            return [json.loads(l) for l in p.read_text().splitlines()] if p.exists() else []

    def test_catalogue_recherche_bascule_et_remise(self):
        appels = self.executer('''
if(etape===0){creer();etape++;return}
if(fen.enCours)return
if(etape===1){
 verifier(fen.catalogue.length===3,"catalogue non lu : "+fen.catalogue.length)
 verifier(fen.sections.join("|")==="Clavier et souris|Fenêtres","sections : "+fen.sections.join("|"))
 verifier(fen.section==="Clavier et souris"&&fen.visibles.length===2,"première section")
 var champ=trouver(fen.contentItem,"nc-reglages-recherche");verifier(champ!==null,"champ de recherche absent")
 champ.text="FLOU";verifier(fen.visibles.length===1&&fen.visibles[0].cle==="FENETRES_FLOU_FORCE","recherche en majuscules : "+fen.visibles.length)
 champ.text="trois doigts";verifier(fen.visibles.length===1&&fen.visibles[0].cle==="GESTES","recherche dans l'aide, hors section courante")
 champ.text="fenetres";verifier(fen.visibles.length===1,"recherche sans accent (fenêtres)")
 champ.text="";verifier(fen.visibles.length===2,"retour à la section")
 fen.regler("GESTES","non");etape++;return}
if(etape===2){verifier(fen.reglage("GESTES").valeur==="non"&&fen.reglage("GESTES").modifie,"bascule non relue");fen.regler("SOURIS_VITESSE",5);fen.remettre("GESTES");etape++;return}
if(etape===3){verifier(fen.reglage("SOURIS_VITESSE").valeur==="5","entier non écrit");verifier(fen.reglage("GESTES").valeur==="oui"&&!fen.reglage("GESTES").modifie,"remise à la config");verifier(fen.message!=="","message de confirmation");etape++;return}
if(etape===4){fen.close();verifier(!fen.visible,"fermeture");Qt.quit()}
''')
        sets = [a for a in appels if a[0] in ("set", "reset")]
        self.assertEqual(sets, [["set", "GESTES", "non"], ["set", "SOURIS_VITESSE", "5"], ["reset", "GESTES"]])
        self.assertGreaterEqual(sum(1 for a in appels if a[0] == "catalogue"), 3, "le catalogue est relu après les écritures")

    def test_tout_au_clavier(self):
        appels = self.executer('''
if(etape===0){creer();etape++;return}
if(fen.enCours)return
var liste=trouver(fen.contentItem,"nc-reglages-liste");var champ=trouver(fen.contentItem,"nc-reglages-recherche")
if(etape===1){verifier(liste!==null&&liste.activeFocus,"la liste n'a pas le focus à l'ouverture");verifier(fen.courant.cle==="SOURIS_VITESSE","première ligne");clavier.keyClick(Qt.Key_Right);etape++;return}
if(etape===2){verifier(fen.reglage("SOURIS_VITESSE").valeur==="1","→ n'a pas augmenté : "+fen.reglage("SOURIS_VITESSE").valeur);clavier.keyClick(Qt.Key_Down);verifier(fen.courant.cle==="GESTES","↓");clavier.keyClick(Qt.Key_Return);etape++;return}
if(etape===3){verifier(fen.reglage("GESTES").valeur==="non","Entrée n'a pas basculé");clavier.keyClick(Qt.Key_Tab);verifier(fen.section==="Fenêtres"&&fen.courant.cle==="FENETRES_FLOU_FORCE","Tab section : "+fen.section);clavier.keyClick(Qt.Key_Left);etape++;return}
if(etape===4){verifier(fen.reglage("FENETRES_FLOU_FORCE").valeur==="leger","← choix précédent : "+fen.reglage("FENETRES_FLOU_FORCE").valeur);clavier.keyClick(Qt.Key_R);etape++;return}
if(etape===5){verifier(fen.reglage("FENETRES_FLOU_FORCE").valeur==="normal"&&!fen.reglage("FENETRES_FLOU_FORCE").modifie,"r : valeur de la config");clavier.keyClick(Qt.Key_G);verifier(champ.activeFocus&&champ.text==="g"&&fen.visibles.length===1&&fen.visibles[0].cle==="GESTES","une lettre lance la recherche : "+champ.text+" / "+fen.visibles.length);clavier.keyClick(Qt.Key_Escape);verifier(fen.recherche===""&&fen.visible,"Échap vide la recherche sans fermer");clavier.keyClick(Qt.Key_Escape);verifier(!fen.visible,"second Échap ferme");Qt.quit()}
''', evenements=True)
        self.assertEqual([a for a in appels if a[0] in ("set", "reset")], [["set", "SOURIS_VITESSE", "1"], ["set", "GESTES", "non"], ["set", "FENETRES_FLOU_FORCE", "leger"], ["reset", "FENETRES_FLOU_FORCE"]])

    def test_onglets_aux_fleches_depuis_le_haut(self):
        appels = self.executer('''
if(etape===0){creer();etape++;return}
if(fen.enCours)return
var liste=trouver(fen.contentItem,"nc-reglages-liste"),rangee=trouver(fen.contentItem,"nc-reglages-sections"),champ=trouver(fen.contentItem,"nc-reglages-recherche")
if(etape===1){
 verifier(liste.activeFocus&&liste.currentIndex===0,"départ sur la première ligne")
 clavier.keyClick(Qt.Key_Up);verifier(rangee.activeFocus,"↑ depuis la première ligne ne monte pas sur les onglets")
 clavier.keyClick(Qt.Key_Right);verifier(fen.section==="Fenêtres"&&rangee.activeFocus,"→ sur les onglets : "+fen.section)
 clavier.keyClick(Qt.Key_Right);verifier(fen.section==="Clavier et souris","→ revient au premier onglet après le dernier")
 clavier.keyClick(Qt.Key_Left);verifier(fen.section==="Fenêtres","← onglet précédent")
 verifier(appels_vides(),"rien n'est écrit en changeant d'onglet")
 clavier.keyClick(Qt.Key_Down);verifier(liste.activeFocus&&fen.courant.cle==="FENETRES_FLOU_FORCE","↓ redescend dans la liste de l'onglet")
 clavier.keyClick(Qt.Key_Up);clavier.keyClick(Qt.Key_Up);verifier(champ.activeFocus,"↑ depuis les onglets va à la recherche")
 clavier.keyClick(Qt.Key_Down);verifier(rangee.activeFocus,"↓ depuis une recherche vide revient aux onglets")
 Qt.quit()}
'''.replace("appels_vides()", "true"), evenements=True)
        self.assertEqual([a for a in appels if a[0] in ("set", "reset")], [], "changer d'onglet n'écrit rien")


if __name__ == "__main__":
    unittest.main()

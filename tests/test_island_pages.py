"""Navigation, préférences et événements Agents QML, sans session personnelle."""
import os
from pathlib import Path
import runpy
import shutil
import subprocess
import tempfile
import unittest
import warnings

REPO = Path(__file__).resolve().parents[1]
QML = REPO / "home/.config/quickshell/nc-ile"
PAGES = "musique claude minuteur charge jeu centre assistant notifications son reseau bluetooth systeme sante calendrier meteo presse fenetres appel terminal".split()


class ReglagesPages(unittest.TestCase):
    def test_all_pages_are_registered_with_safe_defaults(self):
        with tempfile.TemporaryDirectory() as d:
            from unittest.mock import patch
            with patch.dict(os.environ, HOME=d), warnings.catch_warnings():
                warnings.simplefilter("ignore", ResourceWarning)
                settings = runpy.run_path(str(REPO / "home/.local/bin/nc-reglages"))
            keys = settings["PAR_CLE"]
            for page in PAGES:
                r = keys["ILE_PAGE_" + page.upper()]
                self.assertEqual(r.valider("non"), "non")
                self.assertEqual(r.defaut, "oui")
                self.assertEqual(r.section, "Pages de l’île")


@unittest.skipUnless(shutil.which("qs"), "Quickshell requis")
class NavigationPages(unittest.TestCase):
    def executer(self, scenario, scale="1", etat_reel=False):
        with tempfile.TemporaryDirectory(prefix="nc-island-pages-") as d:
            root = Path(d)
            (root / "runtime").mkdir(mode=0o700)
            for name in ("NavigationIle", "Reglages", "Agents"):
                shutil.copy2(QML / (name + ".qml"), root)
            (root / "Couleurs.qml").write_text('pragma Singleton\nimport QtQuick\nQtObject {readonly property color texte:"white"}')
            # Activités Appel et Terminal (Appel.qml, Terminal.qml) : lues par Etat.activites, ici sans appel ni commande
            for name in ("Appel", "Terminal"):
                (root / (name + ".qml")).write_text('pragma Singleton\nimport QtQuick\nQtObject {property bool enCours: false}')
            (root / "Resume.qml").write_text('pragma Singleton\nimport QtQuick\nQtObject { property bool actif: false; property bool ouvert: false; property bool soir: false; property string salut: ""; property string court: ""; property var contenu: ({}) }')
            # Le bloc de navigation de production, avec les entrées matérielles simulées.
            source = (QML / "Etat.qml").read_text()
            bloc = source[source.index('    property string ecranOuvert:'):source.index('    // Spotlight (Super + R)')]
            stub = '''pragma Singleton
import QtQuick
QtObject {
 property var maintenant: new Date()
 property var lecteur: null
 property var dernierLecteur: null
 property string titre: ""
 property bool joue: false
 property real finLecture: 0
 property real minuteurFin: 0
 property bool enCharge: false
 property bool batteriePc: false
 property bool jeu: false
 property var meteo: ({})
 property string meteoErreur: ""
 property bool recherche: false
 property string activiteType: ""
 property int fins: 0
 function activite(n,d) { if (n === "claude-fini") fins++ }
 function lire() {}
 function lireLuminosite(a) {}
 function lirePage() {}
'''
            (root / "Etat.qml").write_text(stub + (bloc if etat_reel else "") + "\n}")
            (root / "qmldir").write_text("\n".join(("" if n == "NavigationIle" else "singleton ") + n + " 1.0 " + n + ".qml" for n in ("NavigationIle", "Reglages", "Agents", "Couleurs", "Etat", "Appel", "Terminal", "Resume")))
            shell = '''import QtQuick
import QtQuick.Window
import QtTest
import Quickshell
ShellRoot {
 id: racine
 property int etape: 0
 property bool occupe: false
 function verifier(v,m) { if (!v) { console.error(m); Qt.exit(2); throw new Error(m) } }
 TestCase { id: clavier; when: false }
 Window {
  visible: true; width: 500; height: 700
  NavigationIle {
   id: nav; x: 450; y: 32; width: 18; height: 76
   pages: ["musique","claude","minuteur","charge","jeu","centre","assistant","notifications","son","reseau","bluetooth","systeme","sante","calendrier","meteo","presse","fenetres"]
   courant: 7
   onChoisir: nom => courant = pages.indexOf(nom)
  }
 }
 function points() { return nav.children.filter(c => c.modelData !== undefined) }
 Timer { interval: 80; running: true; repeat: true; onTriggered: {
  if (occupe) return
  occupe = true
  try {
'''
            (root / "shell.qml").write_text(shell + scenario + "\n} finally {occupe=false} }}\nTimer {interval:5000;running:true;onTriggered:Qt.exit(9)}\n}")
            env = dict(os.environ, HOME=d, XDG_RUNTIME_DIR=str(root / "runtime"), XDG_CACHE_HOME=str(root / "cache"), QT_QPA_PLATFORM="offscreen", QT_QUICK_BACKEND="software", QT_SCALE_FACTOR=scale)
            env.pop("WAYLAND_DISPLAY", None)
            r = subprocess.run(["qs", "--no-color", "-p", str(root / "shell.qml")], env=env, text=True, capture_output=True, timeout=8)
            out = r.stdout + r.stderr
            self.assertEqual(r.returncode, 0, out)
            for error in ("ReferenceError", "TypeError", "Cannot assign", "Binding loop", "is not a type"):
                self.assertNotIn(error, out)

    def test_short_pages_keep_active_and_fade_neighbors_without_overflow(self):
        for scale in ("1", "1.6"):
            with self.subTest(scale=scale):
                self.executer('''
if(etape===0){etape++;return}
function controler(){
 var ps=points(), visibles=ps.filter(p=>p.visible)
 verifier(ps.length===17,"pages perdues")
 verifier(visibles.length>1&&visibles.length<17,"fenêtre de points non bornée")
 var actif=ps.find(p=>p.index===nav.courant)
 verifier(actif.visible&&actif.opacity===1,"page active masquée")
 visibles.forEach(p=>verifier(p.y>=0&&p.y+p.height<=nav.height,"point hors du padding"))
 var autres=visibles.filter(p=>p.index>nav.courant).sort((a,b)=>a.index-b.index)
 for(var i=1;i<autres.length;i++)verifier(autres[i].opacity<autres[i-1].opacity,"opacité non décroissante")
}
if(etape===1){controler();var cible=points().find(p=>p.index===8);clavier.mouseClick(cible,cible.width/2,cible.height/2);verifier(nav.courant===8,"clic perdu");nav.courant=0;etape++}
else if(etape===2){controler();nav.courant=15;etape++}
else if(etape===3){controler();nav.height=0;etape++}
else if(etape===4){verifier(points().every(p=>!p.visible),"points pendant la fermeture");Qt.quit()}
''', scale=scale)

    def test_nom_accessible_est_le_libelle_pas_l_identifiant(self):
        self.executer('''
if(etape===0){etape++;return}
var noms=nav.pages.map(n=>nav.libelle(n))
verifier(noms.every((l,i)=>l!==nav.pages[i]||l==="Claude"||l==="Bluetooth"||l==="Notifications"||l==="Assistant"),"identifiant brut lu : "+noms.join())
verifier(nav.libelle("fenetres")===Reglages.t("Fenêtres","Windows")&&nav.libelle("presse")===Reglages.t("Presse-papiers","Clipboard"),"libellé traduit")
verifier(nav.libelle("inconnue")==="inconnue","page inconnue : repli sur l'identifiant")
Qt.quit()
''')

    def test_preferences_filter_dynamic_and_static_pages_and_allow_all_off(self):
        self.executer('''
if(etape===0){Etat.enCharge=true;Etat.jeu=true;Etat.minuteurFin=Date.now()+10000;Etat.meteo={temp:20};etape++}
else if(etape===1){
 verifier(Etat.vues.indexOf("charge")>=0,"activité absente")
 Etat.basculer("TEST",true);Etat.aller("assistant")
 Reglages.valeurs={ILE_PAGE_ASSISTANT:"non",ILE_PAGE_CHARGE:"non",ILE_PAGE_CENTRE:"non"};etape++
}else if(etape===2){
 verifier(Etat.vues.indexOf("assistant")<0&&Etat.vues.indexOf("charge")<0,"page désactivée visible")
 verifier(Etat.vueActive!=="assistant"&&Etat.vueActive!=="centre","repli vers page désactivée")
 var valeurs={};nav.pages.forEach(n=>valeurs["ILE_PAGE_"+n.toUpperCase()]="non");Reglages.valeurs=valeurs;etape++
}else if(etape===3){
 verifier(Etat.vues.length===0&&Etat.vueActive===""&&Etat.ecranOuvert==="","toutes désactivées")
 Etat.basculer("TEST",true);verifier(Etat.ecranOuvert==="","réouverture sans page")
 Etat.changerVue(1);Reglages.valeurs={};etape++
}else if(etape===4){
 Etat.basculer("TEST",true);verifier(Etat.vueActive==="centre"&&Etat.ecranOuvert==="TEST","réactivation impossible");Qt.quit()
}
''', etat_reel=True)

    def test_page_batterie_apres_le_centre_seulement_avec_une_batterie(self):
        # Page Batterie (charge) : juste après le centre sur un PC à batterie, jamais deux fois pendant une recharge
        # (elle est alors en tête, comme activité), absente sans batterie ou avec ILE_PAGE_CHARGE=non ; le clic sur la
        # batterie de la barre (pageOu) revient alors à Système
        self.executer('''
if(etape===0){
 verifier(Etat.vues.indexOf("charge")<0,"page Batterie sur un PC sans batterie")
 verifier(Etat.pageOu("charge","systeme")==="systeme","repli sans batterie")
 Etat.batteriePc=true;etape++
}else if(etape===1){
 var v=Etat.vues
 verifier(v[v.indexOf("centre")+1]==="charge","Batterie pas juste après le centre : "+v)
 verifier(Etat.pageOu("charge","systeme")==="charge","clic vers Batterie")
 Etat.basculer("TEST",false);verifier(Etat.vueActive==="centre","sans activité, l'île s'ouvre sur le centre");Etat.fermer()
 Etat.enCharge=true;etape++
}else if(etape===2){
 var v=Etat.vues
 verifier(v.filter(n=>n==="charge").length===1,"Batterie deux fois : "+v)
 verifier(v[0]==="charge","recharge : la page en tête, comme activité")
 Etat.enCharge=false;Reglages.valeurs={ILE_PAGE_CHARGE:"non"};etape++
}else if(etape===3){
 verifier(Etat.vues.indexOf("charge")<0,"ILE_PAGE_CHARGE=non : page affichée")
 verifier(Etat.pageOu("charge","systeme")==="systeme","ILE_PAGE_CHARGE=non : pas de repli vers Système");Qt.quit()
}
''', etat_reel=True)

    def test_finished_sessions_are_hidden_without_losing_completion_events(self):
        self.executer('''
if(etape===0){Agents.donnees={sessions:{a:{id:"a",agent:"codex",etat:"travail",projet:"A",maj:Date.now()/1000},b:{id:"b",agent:"claude",etat:"fini",projet:"B",maj:Date.now()/1000}}};etape++}
else if(etape===1){
 verifier(Agents.sessions.length===2&&Agents.sessionsVisibles.length===1,"filtre des sessions")
 verifier(Agents.titreAgent==="codex"&&Agents.aPage,"titre avec anciennes sessions")
 var s=Object.assign({},Agents.donnees.sessions);s.a=Object.assign({},s.a,{etat:"fini"});Agents.donnees={sessions:s};etape++
}else if(etape===2){
 verifier(Agents.sessionsVisibles.length===0&&!Agents.aPage,"page de sessions terminées conservée")
 verifier(Etat.fins===1&&Agents.dernierFini==="A","notification de fin perdue")
 verifier(Agents.sessions.length===2,"historique supprimé")
 var s=Object.assign({},Agents.donnees.sessions);s.a=Object.assign({},s.a,{etat:"travail"});Agents.donnees={sessions:s};etape++
}else if(etape===3){verifier(Agents.sessionsVisibles.length===1&&Agents.aPage,"reprise invisible");Qt.quit()}
''')

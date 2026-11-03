"""Aucun texte affiché dans l'île ne fait partir de requête réseau : une réponse d'IA peut recopier une balise venue d'une
notification ou d'une page, et une adresse peut porter des données de la conversation. Le vrai Quickshell hors écran, un petit
serveur en boucle locale qui note ce qu'il reçoit, et un témoin qui prouve qu'il reçoit bien ce qu'on lui envoie."""
import http.server
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import threading
import time
import unittest

from tests import test_assistant_page as banc

REPO = Path(__file__).resolve().parents[1]
QML = REPO / "home/.config/quickshell/nc-ile"
# U : une adresse par piège, pour savoir lequel a parlé
PIEGES = [
    '<img src="U">', "<IMG SRC=U>", '<img\nsrc="U">', '<a href="https://x.invalid"><img src="U"></a>', "<table background=U><tr><td>x</td></tr></table>",
    '<p style="background-image:url(U)">x</p>', "<style>@import url(U);</style>", "<body background=U>", '<svg><image href="U"/></svg>',
    "<object data=U></object>", '<link rel="stylesheet" href="U">', "<![CDATA[<img src=U>]]>", "<!-- --><img src=U>", "<?x?><img src=U>",
    "![a](U)", "!![a](U)", "[i]: U\n\n![i]", "x\n\n[i]: U\n\n!![i]", "[l](https://x.invalid)![a](U)", "https://x.invalid/![a](U)", "mailto:a![a](U)",
    "!\\( \\)[a](U)", "\\pi !\\displaystyle[a](U)", "&lt;img src=U&gt;", "&#60;img src=U&#62;", "&#x3c;img src=U&#x3e;", "&amp;lt;img src=U&amp;gt;",
    "> <img src=U>", "- <img src=U>", "# <img src=U>", "[<img src=U>](https://x.invalid)", "*<img src=U>*", "**<img src=U>**",
    # Ce qui ressemble à du code sans en être pour Markdown
    "`<img src=U>``", "\\`<img src=U>`", "``a`<img src=U>`", "\\\\\\`<img src=U>`", "<p>\n```\n<img src=U>\n```\n", "<b>\n```\n<img src=U>\n```\n",
    "-  a\n   ```\n<img src=U>\n```", "~~~\n```\n~~~\n<img src=U>", "    ```\n<img src=U>\n```", "```\ncode\n```\r<img src=U>",
    "   ```\ncode\n```  x\n```\n<img src=U>", "| a | b |\n|---|---|\n| `x | <img src=U> `y |", "```a`b\n<img src=U>\n```", "\n```\n```\n<img src=U>",
    "\x00BLOC0\x00<img src=U>", "`a`<img src=U>`b`",
]
# <img> ne fait partir aucune requête dans Qt, même sans filtre : chaque forme est rejouée avec une balise qui en fait partir une
QUI_PARLE = "<table background=U><tr><td>x</td></tr></table>"
PIEGES += [p.replace("<img src=U>", QUI_PARLE) for p in PIEGES if "<img src=U>" in p]
PIEGES += [p.replace("<img src=U>", '<p style="background-image:url(U)">x</p>') for p in PIEGES[:49] if "<img src=U>" in p]
# Les formes qui trompaient un parcours du Markdown : fence hors colonne 0, U+2028, code sur plusieurs lignes, « | », front matter de Qt
T_ = QUI_PARLE
PIEGES += [
    "   ```\ncode\n```\n" + T_, " ```\ncode\n```\n" + T_, "  ~~~\ncode\n~~~\n" + T_, "   ~~~\n```\n   ~~~\n" + T_, "   ```\ncode\n```\n\n![a](U)",
    "- ```\n  x\n```\n" + T_, "> ```\n> x\n```\n" + T_, "1. ```\n   x\n```\n" + T_, "- a\n  ```\n  x\n```\n" + T_,
    "```\u2028x\ncode\n```\n" + T_, "```x\u2029\ncode\n```\n" + T_, "`a\nb` " + T_ + " `c`", "`a\nb` ![a](U) `c`", "> `a\n> b` " + T_ + " `c`", "- `a\n  b` " + T_ + " `c`",
    "`a | b` " + T_ + " `c`", "`|` " + T_ + " `c`", "`a | b` ![a](U) `c`", "| `a\\|b` " + T_ + " `c` |\n|---|\n",
    "---\n```\n---\n" + T_, "---\n~~~\n---\n\n" + T_, "---\r\n```\r\n---\r\n" + T_, "---\n```\n---\n\n![a](U)", "| a | b |\n|---|---|\n| x ` | `" + T_ + "` | y ` |",
    "<div style=\"background:url(U)\">x</div>", "<span style=\"background-image:url(U)\">x</span>", "<body background=U>", "<style>p{background-image:url(U)}</style><p>x</p>",
    "- a\n  ```\n" + T_ + "\n  ```", "x\n10. a\n    ~~~\n    " + T_ + "\n    ~~~", "- ~~~\n  ~~~\n  " + T_ + "\n  ~~~",
]
# Qt retire les demi-surrogats isolés avant md4c ; les majuscules ; <img> fermée parle, seule elle ne parle pas
DEMI = chr(0xd83d)
PIEGES += [
    "!" + DEMI + "[a](U)", "[i]: U\n\n!" + DEMI + "[i]", "!" + chr(0xdc80) + "[a](U)", "<" + DEMI + 'p style="background-image:url(U)">x<' + DEMI + "/p>",
    "<" + DEMI + "style>@import url(U);<" + DEMI + "/style>", "<" + DEMI + "table background=U><" + DEMI + "tr><" + DEMI + "td>x<" + DEMI + "/td><" + DEMI + "/tr><" + DEMI + "/table>",
    "<TABLE BACKGROUND=U><TR><TD>x</TD></TR></TABLE>", "<STYLE>@IMPORT URL(U);</STYLE>", "<img src=U></img>", "<<table background=U><tr><td>x</td></tr></table>",
    '<?p style="background-image:url(U)">x<?/p>', "<TABLE BACKGROUND=U/>", "<IMG SRC=U/>",
]
ORDINAIRES = [
    ("- point\n  ```html\n  <div>x</div>\n  ```", "point\u2029<div>x</div>"), ("1. un\n\n   ```\n   vector<int> v;\n   ```\n2. deux", "un\u2029vector<int> v;\u2029deux"),
    ("- point\n\n      <div>x</div>", "point\u2029<div>x</div>"), ("> ```\n> a<b>\n> ```", "a<b>"), ("`cat < f | wc -l`", "cat < f | wc -l"),
    ("**gras** et *italique*", "gras et italique"), ("`vector<int> x`", "vector<int> x"), ("a < b et c > d", "a < b et c > d"), ("Bravo![1]", "Bravo![1]"),
    ("<b>gras</b>", "gras"), ("<code>a<b</code>", "a<b"), ("a<br>b", "a b"), ("$x^2$", "x²"), ("[l](https://x.invalid)", "l"),
]


DOUBLURE_REGLAGES = '''pragma Singleton
import QtQuick
QtObject {
 property var v: ({}); property string effets:"tous"; readonly property bool sobre:false; readonly property bool en:false; readonly property bool iaCoupee:false
 function t(fr,en){return fr} function val(k,d){return d} function pageActive(n){return true}
}'''
DOUBLURE_ETAT = '''pragma Singleton
import QtQuick
import Quickshell
QtObject {
 property string saisie:""; property string texteIA:""; property bool recherche:true; property bool nuit:false
 readonly property string bin: Quickshell.env("HOME") + "/.local/bin/"
 signal validerRecherche()
 function faire(c){} function fermer(){} function aller(p){} function basculer(e,c){}
}'''


class Serveur(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.server.recus.append(self.path)
        self.send_response(404)
        self.end_headers()

    def log_message(self, *a):
        pass


@unittest.skipUnless(shutil.which("qs"), "Quickshell requis")
class RenduSansReseau(unittest.TestCase):
    def setUp(self):
        self.serveur = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Serveur)
        self.serveur.recus = []
        fil = threading.Thread(target=self.serveur.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True)
        fil.start()
        self.addCleanup(self.serveur.server_close)
        self.addCleanup(self.serveur.shutdown)
        self.base = f"http://127.0.0.1:{self.serveur.server_address[1]}"

    def adresse(self, n):
        return f"{self.base}/p{n}.png"

    def pieges(self):
        # U seul : BACKGROUND ou URL en majuscules contiennent aussi cette lettre
        return [re.sub(r"(?<![A-Za-z])U(?![A-Za-z])", lambda _, n=i: self.adresse(n), p) for i, p in enumerate(PIEGES)]

    def executer(self, scenario, **options):
        # Des centaines de textes rendus : le délai de 5 s du banc ne tient pas sur une machine chargée
        banc.PageAssistant.executer(self, scenario, limite=25, **options)

    # Toutes les surfaces qui lisent du Markdown ou du HTML, sous leur vraie forme ; le témoin passe par le même canal, sans filtre
    OUTILS = """
 var creer2=function(type,t){var e=Qt.createQmlObject('import QtQuick; '+type+'{textFormat:Text.MarkdownText;width:400}',page);e.text=t;return e}
"""

    def verifier_recus(self):
        """Attend le témoin, puis : lui seul a parlé."""
        recus = list(self.serveur.recus)
        self.assertIn("/temoin.png", recus, "le serveur n'a rien vu : ce test ne prouverait rien")
        self.assertEqual([r for r in recus if r != "/temoin.png"], [], [PIEGES[int(re.search(r"\d+", r)[0])] for r in recus if r != "/temoin.png"])

    TEMOIN = """ creer2("TextEdit","x\\n\\n[i]: BASE/temoin.png\\n\\n![i]")
"""

    def temoin(self):
        return self.TEMOIN.replace("BASE", self.base)

    def test_formater_toutes_les_surfaces_de_texte(self):
        self.executer("""
if(etape===0){
 creer()""" + self.OUTILS + """
 for(var t of """ + json.dumps(self.pieges()) + """){
  // Assistant.qml, JarvisResultat.qml : TextEdit ; Recherche.qml, PageNotifs.qml : Text
  creer2("TextEdit",AssistantEtat.formater(t))
  creer2("Text",AssistantEtat.formater(t))
  // Parametres.qml, JarvisResultat.qml (dernière branche) : sans formater
  creer2("Text",AssistantEtat.sansReseau(t))
 }
""" + self.temoin() + """
 memo.t=Date.now();etape++
}else if(etape===1&&Date.now()-memo.t>1500){Qt.quit()}
""")
        self.verifier_recus()

    def test_vraie_page_du_chat(self):
        """La page ne garde que 24 messages : les pièges passent par paquets, chacun affiché avant le suivant."""
        self.executer(self.OUTILS + """
if(etape===0){
 creer();page.historiqueOuvert=true;memo.p=""" + json.dumps(self.pieges()) + """;memo.i=0;memo.t=0;etape++
}else if(etape===1&&Date.now()-memo.t>60){
 for(var n=0;n<24&&memo.i<memo.p.length;n++)AssistantEtat.ajouter("assistant",memo.p[memo.i++])
 verifier(trouver(page,"nc-jarvis-message")!==null,"aucun message rendu")
 memo.t=Date.now()
 if(memo.i>=memo.p.length){""" + self.temoin() + """;etape++}
}else if(etape===2&&Date.now()-memo.t>1500){Qt.quit()}
""")
        self.verifier_recus()

    def test_ordinaire_inchange(self):
        cas = json.dumps(ORDINAIRES)
        self.executer("""
if(etape===0){
 creer()""" + self.OUTILS + """
 for(var c of """ + cas + """){
  var e=creer2("TextEdit",AssistantEtat.formater(c[0]))
  var vu=AssistantEtat.sansInvisible(e.getText(0,e.length))
  verifier(vu===AssistantEtat.sansInvisible(c[1]),"affiché : ["+vu+"] attendu : ["+c[1]+"]")
 }
 // Le code reste du code, entier ; un lien et un tableau Markdown restent
 var code=AssistantEtat.sansInvisible(AssistantEtat.formater("```\\n<img src=x> a<b>\\n```"))
 verifier(code==="```\\n<img src=x> a<b>\\n```","bloc de code : "+code)
 var deux=AssistantEtat.sansReseau("<a ![b](c)");verifier(AssistantEtat.sansReseau(deux)===deux,"deux passages")
 verifier(AssistantEtat.sansReseau("a < b")==="a < b","pas de caractère invisible sans besoin")
 verifier(AssistantEtat.sansInvisible(deux)==="<a ![b](c)","copie fidèle")
 var l=creer2("TextEdit",AssistantEtat.formater("[l](https://x.invalid/a)"))
 verifier(l.linkAt(4,4)==="https://x.invalid/a","lien Markdown perdu")
 var tb=creer2("TextEdit",AssistantEtat.formater("| a | b |\\n|---|---|\\n| 1 | 2 |"))
 verifier(tb.getText(0,tb.length).indexOf("|---")<0,"tableau Markdown perdu")
 verifier(AssistantEtat.sansReseau("")==="","vide")
 Qt.quit()
}
""")

    def test_vrai_cockpit(self):
        """JarvisResultat.qml en vrai : le message et chaque branche de ses lignes, chacune seule, car la première liste trouvée gagne."""
        p = self.pieges()
        champs = lambda x: dict(id=x[:40], name=x, title=x, text=x, response=x, content=x, desc=x, platform=x, remind_at=x, state=x, model=x)
        cles = ("models", "conversations", "facts", "reminders", "services", "history", "messages")
        paquets = [{cle: [champs(x) for x in p[i::len(cles)][:14]]} for i, cle in enumerate(cles)]
        paquets += [dict(message=p[4] + "\n\n" + p[5]), dict(profile={f"c{i}": x for i, x in enumerate(p[-14:])})]
        self.executer("""
if(etape===0){
 creer()""" + self.OUTILS + """
 var c=Qt.createComponent("JarvisResultat.qml");verifier(c.status===Component.Ready,c.errorString())
 memo.r=[]
 for(var d of """ + json.dumps(paquets) + """){var o=c.createObject(page,{width:400});o.donnees=d;memo.r.push(o)}
""" + self.temoin() + """
 memo.t=Date.now();etape++
}else if(etape===1&&Date.now()-memo.t>1500){
 for(var i=0;i<memo.r.length;i++)verifier(memo.r[i].lignes.length>0||memo.r[i].message!=="","paquet vide : "+i)
 Qt.quit()
}
""")
        self.verifier_recus()

    def test_vrai_cockpit_valeurs_simples(self):
        """La branche des valeurs simples de JarvisResultat.qml (ni message ni liste)."""
        donnees = {f"cle{i}": x for i, x in enumerate(self.pieges()[-60:])}
        self.executer("""
if(etape===0){
 creer()""" + self.OUTILS + """
 var c=Qt.createComponent("JarvisResultat.qml");verifier(c.status===Component.Ready,c.errorString())
 memo.r=c.createObject(page,{width:400})
 memo.r.donnees=""" + json.dumps(donnees) + """
""" + self.temoin() + """
 memo.t=Date.now();etape++
}else if(etape===1&&Date.now()-memo.t>1500){
 verifier(memo.r.lignes.length>=60,"lignes : "+memo.r.lignes.length)
 Qt.quit()
}
""")
        self.verifier_recus()

    def piege_de_page(self):
        b = self.base
        return (f'<table background={b}/p0.png><tr><td>x</td></tr></table>\n\n<p style="background-image:url({b}/p1.png)">y</p>\n\n'
                f'<style>@import url({b}/p2.css);</style>\n\n![z]({b}/p3.png)\n\n[i]: {b}/p4.png\n\n![i]\n\n<img src={b}/p5.png></img>')

    def jouer_page(self, corps):
        """Un vrai fichier de l'île, Etat et Reglages en doublures ; s'arrête au témoin, posé une fois le piège affiché."""
        with tempfile.TemporaryDirectory(prefix="nc-rendu-") as d:
            root = Path(d)
            q = root / "qml"
            shutil.copytree(QML, q)
            (root / "run").mkdir(mode=0o700)
            (q / "Reglages.qml").write_text(DOUBLURE_REGLAGES)
            (q / "Etat.qml").write_text(DOUBLURE_ETAT)
            for f in q.glob("shell*.qml"):
                f.unlink()
            b = root / ".local/bin"
            b.mkdir(parents=True)
            for nom, code in {"nc-apps": 'echo "[]"', "nc-aide-config": "exit 0", "nc-reglages": 'echo "[]"', "nc-demander": 'echo "{}"', "nc-ia": "exit 0"}.items():
                (b / nom).write_text("#!/bin/sh\n" + code + "\n")
                (b / nom).chmod(0o755)
            (q / "shell.qml").write_text(corps)
            env = dict(os.environ, HOME=d, QT_QPA_PLATFORM="offscreen", QT_QUICK_BACKEND="software", XDG_RUNTIME_DIR=str(root / "run"), XDG_CACHE_HOME=str(root / "cache"))
            with open(root / "log", "w+") as log:
                p = subprocess.Popen(["qs", "--no-color", "-p", str(q / "shell.qml")], env=env, stdout=log, stderr=subprocess.STDOUT)
                try:
                    fin = time.monotonic() + 25
                    while time.monotonic() < fin and p.poll() is None and "/temoin.png" not in self.serveur.recus:
                        time.sleep(.05)
                    time.sleep(1)
                finally:
                    if p.poll() is None:
                        p.kill()
                    p.wait()
                log.seek(0)
                return log.read()

    TROUVER = """function trouver(i){if(i.textFormat===Text.MarkdownText&&i.visible&&(""+i.text).indexOf("<")>=0)return i;for(var k=0;k<i.children.length;k++){var r=trouver(i.children[k]);if(r)return r}return null}
 function constat(t){console.log("SURFACE "+(t!==null)+" filtre "+(t?t.text.indexOf(String.fromCharCode(0x200b))>=0:false))}
"""

    def verifier_page(self, log):
        recus = list(self.serveur.recus)
        self.assertIn("/temoin.png", recus, log[-1500:])
        self.assertEqual([r for r in recus if r != "/temoin.png"], [])
        self.assertIn("SURFACE true filtre true", log, "la vraie surface n'a pas été trouvée : ce test ne prouverait rien\n" + log[-1500:])

    def test_vrai_spotlight(self):
        log = self.jouer_page("""import QtQuick
import Quickshell
ShellRoot { property int etape:0
 """ + self.TROUVER + """
 function champ(i){if(i.objectName==="nc-spotlight-champ")return i;for(var k=0;k<i.children.length;k++){var r=champ(i.children[k]);if(r)return r}return null}
 FloatingWindow { id:fen; visible:true; implicitWidth:700; implicitHeight:500
  Recherche { id:spot; width:700; actif:true } }
 Timer { interval:150; running:true; repeat:true; onTriggered:{
  if(etape===0){ champ(spot).text="?question"; spot.reponse=""" + json.dumps(self.piege_de_page()) + """ }
  if(etape===5){ constat(trouver(spot))
   var e=Qt.createQmlObject('import QtQuick; Text{textFormat:Text.MarkdownText;width:300}',fen.contentItem); e.text="![w](""" + self.base + """/temoin.png)" }
  etape++
 }}
}""")
        self.verifier_page(log)

    def test_vrais_reglages(self):
        ligne = dict(cle="rap", section="s", sectionNom="S", nom="N", genre="rapport", aide=self.piege_de_page(), ia="", choix=[], valeur="", affiche="", modifie=False, defaut="", mini=0, maxi=0, pas=1, unite="", zero="")
        log = self.jouer_page("""import QtQuick
import Quickshell
ShellRoot { property int etape:0
 """ + self.TROUVER + """
 Parametres { id:p; visible:true }
 Timer { interval:200; running:true; repeat:true; onTriggered:{
  if(etape===3){ p.catalogue=""" + json.dumps([ligne]) + """; p.section="S" }
  if(etape===12){ constat(trouver(p.contentItem))
   var e=Qt.createQmlObject('import QtQuick; Text{textFormat:Text.MarkdownText;width:300}',p.contentItem); e.text="![w](""" + self.base + """/temoin.png)" }
  etape++
 }}
}""")
        self.verifier_page(log)

    def test_ce_qui_est_garde_vient_de_la_source(self):
        """Le filtre ne touche que l'affichage : l'historique envoyé à une IA garde le texte d'origine."""
        self.executer("""
if(etape===0){
 creer()
 var t="vector<int> ![a](b) <div>"
 AssistantEtat.ajouter("assistant",t)
 var m=AssistantEtat.messages[AssistantEtat.messages.length-1]
 verifier(m.texte===t,"message enregistré : "+m.texte)
 verifier(AssistantEtat.formater(t)!==t,"le filtre agit bien à l'affichage")
 Qt.quit()
}
""")

    INVISIBLES = "[0x200b,0x2028,0x2029,0xfdd0,0xfdd1,0xa0]"

    def test_ctrl_c_dans_le_vrai_qt(self):
        """Le vrai TextEdit du chat, le vrai clavier de QtTest, le presse-papiers de Qt relu ensuite : si Qt copie aussi, le test le voit."""
        message = "Ligne un\n\n```\ncat <f\ndeux\n```\n\n- puce\n\n| a | b |\n|---|---|\n| 1 | 2 |\n\nfin `x<y>` z\n\nespace&nbsp;dur\n\ncoupe" + chr(0x2028) + "ici"
        self.executer("""
var invisibles=""" + self.INVISIBLES + """
if(etape===0){
 creer();page.historiqueOuvert=true
 AssistantEtat.ajouter("assistant",""" + json.dumps(message) + """)
 w.requestActivate();memo.t=Date.now();etape++
}else if(etape===1&&Date.now()-memo.t>300){
 var e=trouver(page,"nc-jarvis-message");verifier(e!==null,"pas de message");memo.e=e
 clavier.mouseClick(e,6,8)
 verifier(e.activeFocus,"le message n'a pas le focus");e.selectAll()
 for(var c of invisibles)verifier(e.selectedText.indexOf(String.fromCharCode(c))>=0,"absent de la sélection, ce test ne prouverait rien : "+c)
 Quickshell.clipboardText="avant"
 clavier.keyClick(Qt.Key_C,Qt.ControlModifier)
 memo.t=Date.now();etape++
}else if(etape===2&&Date.now()-memo.t>200){
 var t=Quickshell.clipboardText
 verifier(t!=="avant","rien de copié")
 for(var c2 of invisibles)verifier(t.indexOf(String.fromCharCode(c2))<0,"invisible copié : "+c2)
 verifier(t.indexOf("Ligne un\\ncat <f\\ndeux\\n")===0,"début : "+t)
 for(var x of ["fin x<y> z","espace dur","coupe\\nici"])verifier(t.indexOf(x)>=0,x+" absent de : "+t)
 // Sélection vide : rien n'écrase le presse-papiers
 memo.e.deselect();Quickshell.clipboardText="garde"
 clavier.keyClick(Qt.Key_C,Qt.ControlModifier)
 memo.t=Date.now();etape++
}else if(etape===3&&Date.now()-memo.t>200){
 verifier(Quickshell.clipboardText==="garde","sélection vide : "+Quickshell.clipboardText)
 // Une sélection du seul caractère invisible n'écrase pas non plus
 AssistantEtat.copierSansInvisible(String.fromCharCode(0x200b))
 verifier(Quickshell.clipboardText==="garde","caractère invisible seul : ["+Quickshell.clipboardText+"]")
 // Au-delà de ce que tient une ligne de commande
 AssistantEtat.copierSansInvisible("€".repeat(47000))
 verifier(Quickshell.clipboardText.length===47000,"long : "+Quickshell.clipboardText.length)
 Qt.quit()
}
""", evenements=True)

    def test_ctrl_c_du_cockpit(self):
        """Le même Ctrl + C, dans le vrai JarvisResultat.qml."""
        self.executer("""
var invisibles=""" + self.INVISIBLES + """
if(etape===0){
 creer()
 var c=Qt.createComponent("JarvisResultat.qml");verifier(c.status===Component.Ready,c.errorString())
 memo.r=c.createObject(page,{width:400});memo.r.donnees={message:"cat <f\\n\\n| a | b |\\n|---|---|\\n| 1 | 2 |"}
 w.requestActivate();memo.t=Date.now();etape++
}else if(etape===1&&Date.now()-memo.t>300){
 var chercher=function(i){if(i.selectByMouse===true&&i.readOnly===true&&i.visible)return i;for(var k=0;k<i.children.length;k++){var t=chercher(i.children[k]);if(t)return t}return null}
 var e=chercher(memo.r);verifier(e!==null,"pas de message");e.forceActiveFocus();e.selectAll()
 verifier(e.selectedText.indexOf("<"+String.fromCharCode(0x200b))>=0,"le caractère invisible n'est pas dans la sélection : ce test ne prouverait rien")
 Quickshell.clipboardText="avant"
 clavier.keyClick(Qt.Key_C,Qt.ControlModifier)
 memo.t=Date.now();etape++
}else if(etape===2&&Date.now()-memo.t>200){
 var copie=Quickshell.clipboardText
 verifier(copie.indexOf("cat <f\\n")===0,"copie : "+copie)
 for(var c2 of invisibles)verifier(copie.indexOf(String.fromCharCode(c2))<0,"invisible copié : "+c2)
 Qt.quit()
}
""", evenements=True)


class SourcesDuRendu(unittest.TestCase):
    """Lecture des sources seulement : se joue aussi sans Quickshell, donc en CI. Le rendu lui-même n'y est pas essayé."""

    def test_le_filtre_n_est_appele_qu_a_l_affichage(self):
        """Ce qui se copie ou s'exécute vient de la source : tous les appels du filtre sont des liaisons d'affichage."""
        # Tous les appels du filtre sont des liaisons d'affichage, et ce qui se copie ou s'exécute dans le Spotlight vient de r.brut
        attendu = {"Assistant.qml": 1, "JarvisResultat.qml": 5, "PageNotifs.qml": 1, "Parametres.qml": 1, "Recherche.qml": 1}
        vus = {}
        for f in sorted(QML.glob("*.qml")):
            if f.name == "AssistantEtat.qml":
                continue
            for ligne in f.read_text().splitlines():
                ligne = ligne.strip()
                if ligne.startswith("//") or not re.search(r"AssistantEtat\.(formater|sansReseau)\(", ligne):
                    continue
                vus[f.name] = vus.get(f.name, 0) + 1
                # La liaison text: d'un texte affiché, ou la suite de celle à plusieurs lignes de JarvisResultat.qml
                self.assertTrue(re.search(r"\btext:", ligne) or ligne.startswith(('carte.kind==="value"', "AssistantEtat.sansReseau([carte")), f"{f.name} : un appel hors d'une liaison d'affichage : {ligne}")
        self.assertEqual(vus, attendu)
        # Dans AssistantEtat.qml : le dernier passage de formater, et apercu(), qui n'a aucun appelant aujourd'hui
        internes = [ligne.strip() for ligne in (QML / "AssistantEtat.qml").read_text().splitlines() if re.search(r"\b(formater|sansReseau)\(", ligne) and not ligne.strip().startswith(("function", "//"))]
        self.assertEqual(len(internes), 2, internes)
        self.assertTrue(internes[0].startswith("return sansReseau(") and internes[1] == "var t = formater(texte)", internes)
        recherche = (QML / "Recherche.qml").read_text()
        self.assertIn("let resultat = r.reponse", recherche)
        self.assertIn("r.reponse = r.brut", recherche)
        self.assertNotIn("r.reponse = AssistantEtat", recherche)
        self.assertNotIn("r.brut = AssistantEtat", recherche)

    def test_chaque_surface_passe_par_la_meme_fonction(self):
        """Tout ce qui lit du Markdown passe par formater ou sansReseau : une surface ajoutée sans cela fait échouer ce test."""
        permis = re.compile(r"AssistantEtat\.(?:formater|sansReseau)\(")
        vus = 0
        sans_format = {}
        for f in sorted(QML.glob("*.qml")):
            s = f.read_text()
            for m in re.finditer(r"(?<![\w.])(Text|TextEdit|Texte|Label)\s*\{", s):
                i, d = m.end(), 1
                while i < len(s) and d:
                    d += {"{": 1, "}": -1}.get(s[i], 0)
                    i += 1
                bloc = s[m.end():i]
                if m[1] != "Texte" and "textFormat" not in bloc:
                    sans_format[f.name] = sans_format.get(f.name, 0) + 1
                if "MarkdownText" in bloc or "RichText" in bloc or "StyledText" in bloc:
                    vus += 1
                    texte = re.search(r"(?s)\btext\s*:(.*?)(?:\n\s*visible|\n\s*\w+\s*:|;\s*\w+\s*:)", bloc)
                    self.assertTrue(permis.search(bloc), f"{f.name} : {bloc[:80]}")
                    self.assertIsNotNone(texte, f.name)
        self.assertGreaterEqual(vus, 5, "le motif ne voit plus les surfaces")
        # Sans format, Qt devine (<img src="U"> parle) : ces cinq-là n'affichent que des textes fixes ; un nouveau doit nommer son format
        self.assertEqual(sans_format, {"Assistant.qml": 3, "AssistantOrbe.qml": 1, "Parametres.qml": 1})
        self.assertIn("textFormat: Text.PlainText", (QML / "Texte.qml").read_text())
        recherche = (QML / "Recherche.qml").read_text()
        self.assertIn('text: AssistantEtat.sansReseau(r.reponseAide !== "" ? r.reponseAide', recherche, "filtré quel que soit le format")
        self.assertIn('AssistantEtat.sansReseau([carte.item.id!==undefined', (QML / "JarvisResultat.qml").read_text(), "chaque branche")
        self.assertIn('text: p.resumeIA !== "" ? AssistantEtat.formater(p.resumeIA) : ""', (QML / "PageNotifs.qml").read_text())
        self.assertIn('ligne.r.genre === "rapport" ? AssistantEtat.sansReseau(ligne.r.aide', (QML / "Parametres.qml").read_text())
        self.assertIn("textFormat: Text.PlainText", (QML / "Ico.qml").read_text())
        for nom in ("Assistant.qml", "JarvisResultat.qml"):
            self.assertIn("AssistantEtat.copierSansInvisible(selectedText)", (QML / nom).read_text(), nom)
        self.assertIn("page.ouvrirLien(AssistantEtat.sansInvisible(lien))", (QML / "Assistant.qml").read_text(), "un lien ouvert sans le caractère")
        for nom, ligne in (("DemandeClaude.qml", 'text: d.vue ? (d.vue.detail || "") : ""\n                textFormat: Text.PlainText'),
                           ("AssistantCommande.qml", "text: bouton.texte; textFormat: Text.PlainText")):
            self.assertIn(ligne, (QML / nom).read_text(), nom)


if __name__ == "__main__":
    unittest.main()

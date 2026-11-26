"""Lanceur de l'île (Recherche.qml) : trois espaces stricts, Applis, Fichiers et Actions, jamais mêlés. Joué hors écran
avec le vrai Recherche.qml et de faux nc-apps / qalc qui notent leurs appels : Tab (espaceSuivant) et les onglets changent
d'espace, un préfixe (? > + ; : mdp note…) mène aux Actions, un calcul aussi tant que l'espace n'est pas choisi à la main,
et nc-apps files n'est lancé que dans l'espace Fichiers. Avec une liste d'applis ou un qalc retenus (fichiers bloquer-*),
les tests d'ordre : une Entrée en attente n'est jamais rejouée dans un autre espace, un calcul attend les applis, et les
raccourcis web ou les zones lus après la saisie réévaluent l'espace. Les touches passent par le vrai champ (TestCase)."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

QML = Path(__file__).resolve().parents[1] / "home/.config/quickshell/nc-ile"
RECHERCHE = (QML / "Recherche.qml").read_text(encoding="utf-8")

SHELL = '''import QtQuick
import Quickshell
ShellRoot {
 property int etape: 0
 property int attente: 0
 function trouver(item,nom){if(item.objectName===nom)return item;for(var i=0;i<item.children.length;i++){var r=trouver(item.children[i],nom);if(r)return r}return null}
 function verifier(ok,message){if(!ok){console.error(message);Qt.exit(2);throw new Error(message)}}
 function titres(){ return spot.resultats.map(x => x.titre) }
 function seul(e){ return spot.resultats.every(x => (x.e || "actions") === e) }
 FloatingWindow { visible: true; implicitWidth: 438; implicitHeight: 600
  Recherche { id: spot; width: 438; height: 600; actif: true } }
 Timer { interval: 100; running: true; repeat: true; onTriggered: {
  var champ = trouver(spot, "nc-spotlight-champ")
  if (etape === 0) { if (!spot.applisLues) return
   verifier(spot.espace === "applis", "Applis à l'ouverture")
   champ.text = "fire"; etape++; return }
  if (etape === 1) {
   if (titres().indexOf("Firefox") < 0) { attente++; verifier(attente < 50, "Applis : " + JSON.stringify(titres())); return }
   attente++; if (attente < 8) return
   verifier(seul("applis"), "Applis seules : " + JSON.stringify(spot.resultats))
   verifier(spot.fichiers.length === 0, "nc-apps files jamais lancé dans Applis")
   verifier(trouver(spot, "nc-lanceur-compteur").text === spot.resultats.length + (spot.resultats.length > 1 ? " résultats" : " résultat"), "compteur")
   spot.espaceSuivant(1); attente = 0; etape++; return }
  if (etape === 2) {
   verifier(spot.espace === "fichiers" && spot.espaceManuel, "Tab : Fichiers")
   if (titres().indexOf("firefox-notes.txt") < 0) { attente++; verifier(attente < 50, "Fichiers : " + JSON.stringify(titres())); return }
   verifier(seul("fichiers") && titres().indexOf("Firefox") < 0, "Fichiers seuls : " + JSON.stringify(titres()))
   spot.espaceSuivant(1); attente = 0; etape++; return }
  if (etape === 3) {
   verifier(spot.espace === "actions", "Tab : Actions")
   verifier(seul("actions") && titres().indexOf("Firefox") < 0 && titres().indexOf("firefox-notes.txt") < 0, "Actions seules : " + JSON.stringify(titres()))
   spot.espaceSuivant(1); verifier(spot.espace === "applis", "Tab revient à Applis")
   spot.espaceSuivant(-1); verifier(spot.espace === "actions", "Maj + Tab : Actions")
   trouver(spot, "nc-lanceur-onglets").choisir("applis"); verifier(spot.espace === "applis" && seul("applis"), "clic sur l'onglet Applis")
   // Un préfixe mène aux Actions, même depuis un espace choisi à la main
   var prefixes = ["? test", "> ls", "+ gimp", "; mot", ":coeur", "mdp 20", "note acheter du pain", "g chat", "port 8080"]
   for (var i = 0; i < prefixes.length; i++) {
    spot.changerEspace("fichiers"); champ.text = prefixes[i]
    verifier(spot.espace === "actions", prefixes[i] + " : " + spot.espace)
    verifier(seul("actions"), prefixes[i] + " : rien d'autre que des actions")
   }
   // Un calcul sans appli qui lui correspond : Actions, sans rien choisir
   champ.text = ""; spot.espaceManuel = false; champ.text = "2+2"
   verifier(spot.espace === "applis", "calcul : Applis le temps que qalc réponde")
   attente = 0; etape++; return }
  if (etape === 4) {
   if (spot.espace !== "actions" || titres().indexOf("= 4") < 0) { attente++; verifier(attente < 50, "calcul : " + spot.espace + " " + JSON.stringify(titres())); return }
   verifier(seul("actions"), "calcul seul en Actions")
   champ.text = "2+23"; verifier(spot.espace === "actions", "calcul en cours de frappe : reste dans Actions (pas de clignotement)")
   // Espace choisi à la main : le calcul ne l'en sort pas
   spot.changerEspace("applis"); champ.text = "3+3"; attente = 0; etape++; return }
  if (etape === 5) {
   attente++; if (attente < 10) return
   verifier(spot.espace === "applis" && titres().indexOf("= 6") < 0, "manuel : reste en Applis : " + JSON.stringify(titres()))
   // Un préfixe passager (« note » de « notebook », « ? » effacé) ne fait pas perdre l'espace choisi
   spot.changerEspace("fichiers")
   var mots = ["n", "no", "not", "note", "noteb", "notebook"]
   for (var j = 0; j < mots.length; j++) {
    champ.text = mots[j]
    verifier(spot.espace === (mots[j] === "note" ? "actions" : "fichiers"), mots[j] + " : " + spot.espace)
   }
   champ.text = "?"; verifier(spot.espace === "actions", "« ? » : Actions")
   champ.text = ""; verifier(spot.espace === "fichiers", "« ? » effacé : retour à Fichiers")
   champ.text = "notebook"; attente = 0; etape++; return }
  if (etape === 6) { attente++; if (attente < 4) return
   // La réponse (aide, IA, bilan) n'existe que dans les Actions
   champ.text = "? quelle heure"; verifier(spot.espace === "actions", "« ? » : Actions")
   spot.reponseAide = "Réponse de la config"
   var zone = trouver(spot, "nc-spotlight-reponse")
   verifier(zone.visible, "réponse visible dans Actions")
   var h = spot.hauteurVoulue
   spot.changerEspace("fichiers")
   verifier(!zone.visible && spot.hauteurVoulue < h, "réponse cachée en Fichiers, hauteur sans elle : " + spot.hauteurVoulue + " / " + h)
   spot.changerEspace("applis"); verifier(!zone.visible, "réponse cachée en Applis")
   spot.changerEspace("fichiers")       // nc-apps files ne part pas pour une saisie d'action
   attente = 0; etape++; return }
  if (etape === 7) { attente++; if (attente < 4) return
   // Bascule automatique d'un calcul : la sélection revient en tête (Entrée ne lance pas une ligne sans rapport)
   champ.text = ""; spot.espaceManuel = false; champ.text = "7*8"
   verifier(spot.espace === "applis" && spot.resultats.length === 2, "deux applis faibles : " + JSON.stringify(titres()))
   spot.sel = 1; attente = 0; etape++; return }
  if (etape === 8) {
   if (spot.espace !== "actions" || titres().indexOf("= 56") < 0) { attente++; verifier(attente < 50, "7*8 : " + spot.espace + " " + JSON.stringify(titres())); return }
   verifier(spot.resultats.length >= 2 && spot.sel === 0, "sélection en tête après la bascule : " + spot.sel + " " + JSON.stringify(titres()))
   // SPOTLIGHT_FICHIERS=non : plus d'espace Fichiers
   Reglages.v = { SPOTLIGHT_FICHIERS: "non" }
   verifier(JSON.stringify(spot.espaces) === '["applis","actions"]', "espaces : " + JSON.stringify(spot.espaces))
   spot.changerEspace("applis"); spot.espaceSuivant(1); verifier(spot.espace === "actions", "Tab saute Fichiers")
   spot.espaceSuivant(1); verifier(spot.espace === "applis", "Tab revient à Applis")
   spot.changerEspace("fichiers"); verifier(spot.espace === "applis", "Fichiers refusé")
   etape++; return }
  if (etape === 9) {
   verifier(trouver(spot, "nc-lanceur-onglet-fichiers") === null && trouver(spot, "nc-lanceur-onglet-actions") !== null, "onglet Fichiers caché")
   Qt.quit() }
 } }
 Timer { interval: 40000; running: true; onTriggered: Qt.exit(9) }
}'''

FAUX_APPS = r'''#!/bin/sh
printf '%s\n' "$*" >> "$HOME/appels"
case "$1" in
  list) while [ -e "$HOME/bloquer-list" ]; do sleep 0.05; done
        printf '%s\n' '[{"id": "firefox", "name": "Firefox", "generic": "Navigateur", "icon": "", "exe": "firefox"}, {"id": "o1", "name": "Outil7*8a", "generic": "", "icon": "", "exe": "o1"}, {"id": "o2", "name": "Outil7*8b", "generic": "", "icon": "", "exe": "o2"}, {"id": "agenda", "name": "9-5 Agenda", "generic": "", "icon": "", "exe": "agenda"}]' ;;
  files) printf '%s\n' '[{"name": "firefox-notes.txt", "path": "/home/user/firefox-notes.txt", "dir": false, "parent": "~"}]' ;;
  *) printf '%s\n' '[]' ;;
esac
'''
FAUX_QALC = r'''#!/bin/sh
while [ -e "$HOME/bloquer-qalc" ]; do sleep 0.05; done
case "$2" in
  2+2) echo 4 ;;
  3+3) echo 6 ;;
  7\*8) echo 56 ;;
  9-5) echo 4 ;;
esac
'''

# Scénarios d'ordre : un pas par tic de 100 ms ; attendre() échoue après 5 s ; liberer() / bloquer() ôtent ou posent un
# fichier bloquer-* (le faux script attend tant qu'il existe) ; clavier envoie les touches au champ qui a le focus
GABARIT = '''import QtQuick
import QtTest
import Quickshell
import Quickshell.Io
ShellRoot {
 property int etape: 0
 property int attente: 0
 TestCase { id: clavier; name: "Lanceur"; when: false }
 function ecrire(t){for(var i=0;i<t.length;i++)clavier.keyClick(t.charAt(i))}
 function trouver(item,nom){if(item.objectName===nom)return item;for(var i=0;i<item.children.length;i++){var r=trouver(item.children[i],nom);if(r)return r}return null}
 function verifier(ok,message){if(!ok){console.error(message);Qt.exit(2);throw new Error(message)}}
 function titres(){ return spot.resultats.map(x => x.titre) }
 function attendre(ok,message){if(ok){attente=0;return true}attente++;verifier(attente<50,message);return false}
 function liberer(nom){ Quickshell.execDetached(["rm", "-f", Quickshell.env("HOME") + "/bloquer-" + nom]) }
 function bloquer(nom){ commande.command = ["touch", Quickshell.env("HOME") + "/bloquer-" + nom]; commande.running = true }
 Process { id: commande }
 FloatingWindow { visible: true; implicitWidth: 438; implicitHeight: 600
  Recherche { id: spot; width: 438; height: 600; actif: ACTIF } }
 Timer { interval: 100; running: true; repeat: true; onTriggered: {
  var champ = trouver(spot, "nc-spotlight-champ")
SCENARIO
 } }
 Timer { interval: 40000; running: true; onTriggered: Qt.exit(9) }
}'''


class Source(unittest.TestCase):
    def test_touches_et_composants(self):
        self.assertIn("Keys.onTabPressed: r.espaceSuivant(1)", RECHERCHE)
        self.assertIn("Keys.onBacktabPressed: r.espaceSuivant(-1)", RECHERCHE)
        self.assertIn('r.espace === "fichiers" && q.length >= 3', RECHERCHE)
        self.assertIn('out = out.filter(x => (x.e || "actions") === espace)', RECHERCHE)
        for nom in ("LanceurOnglets", "LanceurLigne", "LanceurPied"):
            self.assertTrue((QML / (nom + ".qml")).exists(), nom)
            self.assertIn(nom + " {", RECHERCHE)


@unittest.skipUnless(shutil.which("qs"), "Quickshell absent")
class EspacesHorsEcran(unittest.TestCase):
    def jouer(self, shell, bloquer=(), fichiers=None):
        """Joue shell hors écran ; bloquer : faux scripts retenus au départ ; fichiers : {chemin sous HOME: texte}.
        Rend les appels de nc-apps."""
        with tempfile.TemporaryDirectory(prefix="ncl-") as d:
            root = Path(d)
            q = root / "qml"
            shutil.copytree(QML, q)
            for sous in ("run", "cache", "state", "data", "config", "tmp"):
                (root / sous).mkdir(mode=0o700)
            (q / "Reglages.qml").write_text('pragma Singleton\nimport QtQuick\nQtObject {\n property var v: ({})\n readonly property bool iaCoupee: true\n'
                                            ' readonly property bool sobre: true\n readonly property bool en: false\n function t(fr,en){return fr}\n'
                                            ' function val(k,d){return v[k] !== undefined ? v[k] : d}\n function pageActive(n){return true}\n}')
            # faits / fermetures : ce qu'une Entrée a vraiment lancé
            (q / "Etat.qml").write_text('pragma Singleton\nimport QtQuick\nimport Quickshell\nQtObject {\n property string saisie: ""\n property string texteIA: ""\n'
                                        ' property bool recherche: true\n property bool nuit: false\n readonly property string bin: Quickshell.env("HOME") + "/.local/bin/"\n'
                                        ' property var faits: []\n property int fermetures: 0\n signal validerRecherche()\n'
                                        ' function faire(c) { faits = faits.concat([c.join(" ")]) } function fermer() { fermetures++ } function aller(p) {} function basculer(e, c) {}\n}')
            (q / "Partage.qml").write_text('pragma Singleton\nimport QtQuick\nQtObject { property bool silence: false }')
            (q / "AssistantEtat.qml").write_text('pragma Singleton\nimport QtQuick\nQtObject {function formater(t){return t} function sansReseau(t){return t}}')
            (q / "Etincelle.qml").write_text('import QtQuick\nItem {property real taille: 10; property bool tourne: false; property string agent: ""}')
            (q / "CloudEtat.qml").write_text('pragma Singleton\nimport QtQuick\nQtObject { property bool actif: false; property bool associe: false }')
            (q / "Rappels.qml").write_text('pragma Singleton\nimport QtQuick\nQtObject { property var liste: []; property bool plein: false; function analyser(p) '
                                           '{ return {ok: false, raison: "heure"} } function quand(d) { return "" } function creer(t, d) { return false } function supprimer(i) {} }')
            singletons = ("Reglages", "Etat", "Partage", "AssistantEtat", "Couleurs", "Connexion")
            noms = list(singletons) + ["Recherche", "LanceurOnglets", "LanceurLigne", "LanceurPied", "Emoji", "Diagnostic", "Etincelle", "Texte", "Ico"]
            (q / "qmldir").write_text("\n".join(("singleton " if n in singletons else "") + n + " 1.0 " + n + ".qml" for n in noms)
                                      + "\nsingleton CloudEtat 1.0 CloudEtat.qml\nsingleton Rappels 1.0 Rappels.qml")
            b = root / ".local/bin"
            b.mkdir(parents=True)
            scripts = {"nc-apps": FAUX_APPS, "qalc": FAUX_QALC, "hyprctl": "#!/bin/sh\nprintf '%s\\n' '[]'\n", "nc-aide-config": "#!/bin/sh\nexit 0\n",
                       "nc-demander": '#!/bin/sh\ncase "$1" in --ia) printf \'%s\\n\' \'{"nom": "-", "agent": "claude", "coupee": true}\' ;; esac\n',
                       "nc-logiciels": "#!/bin/sh\nprintf '%s\\n' '[]'\n", "nc-processus": "#!/bin/sh\nprintf '%s\\n' '{\"ss\": true, \"lignes\": []}'\n",
                       # une session qui répond aussi à « 7*8 » : les Actions ont deux lignes après la bascule du calcul
                       "nc-session": "#!/bin/sh\nprintf '%s\\n' '[{\"nom\": \"Plan7*8\", \"fenetres\": 1, \"applis\": []}]'\n"}
            for nom, code in scripts.items():
                (b / nom).write_text(code)
                (b / nom).chmod(0o755)
            for nom in bloquer:
                (root / ("bloquer-" + nom)).touch()
            for chemin, texte in (fichiers or {}).items():
                (root / chemin).parent.mkdir(parents=True, exist_ok=True)
                (root / chemin).write_text(texte, encoding="utf-8")
            (q / "shell.qml").write_text(shell)
            env = dict(os.environ, HOME=d, XDG_CONFIG_HOME=str(root / "config"), XDG_CACHE_HOME=str(root / "cache"),
                       XDG_STATE_HOME=str(root / "state"), XDG_DATA_HOME=str(root / "data"), XDG_RUNTIME_DIR=str(root / "run"),
                       TMPDIR=str(root / "tmp"), TZDIR=str(root / "zones"), QT_QPA_PLATFORM="offscreen", QT_QUICK_BACKEND="software",
                       PATH=str(b) + os.pathsep + os.environ["PATH"])
            for k in ("WAYLAND_DISPLAY", "HYPRLAND_INSTANCE_SIGNATURE", "DISPLAY"):
                env.pop(k, None)
            r = subprocess.run(["qs", "--no-color", "-p", str(q / "shell.qml")], env=env, text=True, capture_output=True, timeout=70,
                               stdin=subprocess.DEVNULL)
            sortie = r.stdout + r.stderr
            self.assertEqual(r.returncode, 0, sortie)
            for erreur in ("ReferenceError", "TypeError", "is not a type", "Binding loop"):
                self.assertNotIn(erreur, sortie)
            return (root / "appels").read_text(encoding="utf-8").splitlines()

    def scenario(self, etapes, actif=True, **options):
        return self.jouer(GABARIT.replace("ACTIF", "true" if actif else "false").replace("SCENARIO", etapes), **options)

    def test_trois_espaces_jamais_meles(self):
        appels = self.jouer(SHELL)
        # nc-apps files : seulement dans l'espace Fichiers (« fire », puis « notebook » retrouvé après « note ») ; jamais
        # pour un préfixe (« ? quelle heure » passé en Fichiers), un calcul, ni dans Applis
        self.assertEqual([a for a in appels if a.startswith("files")], ["files fire", "files notebook"], appels)

    def test_entree_en_attente_oubliee_hors_de_son_espace(self):
        # Liste d'applis lente : Entrée sur « verrouiller » dans Applis, puis Maj + Tab vers Actions. L'arrivée de la liste
        # ne doit pas valider l'action Verrouiller sélectionnée entre-temps (revue PR 63, P1). Touches dans le vrai champ.
        self.scenario('''
  if (etape === 0) { if (!attendre(champ.activeFocus, "le champ n'a pas le focus")) return
   verifier(!spot.applisLues && spot.espace === "applis", "liste d'applis retenue, Applis")
   clavier.keyClick(Qt.Key_Tab); verifier(spot.espace === "fichiers", "Tab : Fichiers")
   clavier.keyClick(Qt.Key_Backtab, Qt.ShiftModifier); verifier(spot.espace === "applis", "Maj + Tab : Applis")
   ecrire("verrouiller"); verifier(spot.q === "verrouiller", "saisie au clavier : " + spot.q)
   clavier.keyClick(Qt.Key_Return); verifier(spot.entreeEnAttente, "Entrée en attente des applis")
   ecrire("x"); verifier(!spot.entreeEnAttente, "saisie changée : l'Entrée en attente est oubliée")
   clavier.keyClick(Qt.Key_Backspace); clavier.keyClick(Qt.Key_Return); verifier(spot.entreeEnAttente, "Entrée de nouveau en attente")
   clavier.keyClick(Qt.Key_Backtab, Qt.ShiftModifier)
   verifier(spot.espace === "actions" && !spot.entreeEnAttente, "Maj + Tab : Actions, Entrée oubliée")
   liberer("list"); etape++; return }
  if (etape === 1) { if (attendre(spot.applisLues, "liste d'applis jamais lue")) etape++; return }
  if (etape === 2) { attente++; if (attente < 4) return
   verifier(Etat.faits.length === 0 && Etat.fermetures === 0, "Entrée rejouée dans Actions : " + JSON.stringify(Etat.faits))
   verifier(spot.espace === "actions" && titres()[spot.sel] === "Verrouiller", "sélection : " + JSON.stringify(titres()))
   // Entrée tapée dans Actions, elle : l'action part
   clavier.keyClick(Qt.Key_Return)
   verifier(JSON.stringify(Etat.faits) === '["noctalia msg session lock"]' && Etat.fermetures === 1, "Entrée dans Actions : " + JSON.stringify(Etat.faits))
   Qt.quit() }''', bloquer=("list",))

    def test_calcul_attend_la_liste_des_applis(self):
        # « 9-5 » : calculable, et l'appli « 9-5 Agenda » commence par la saisie : Applis, quel que soit l'ordre de fin de
        # qalc et de nc-apps list (revue PR 63, P2). « 2+2 », sans appli : Actions dès que la liste arrive.
        self.scenario('''
  if (etape === 0) { if (!attendre(champ.activeFocus, "le champ n'a pas le focus")) return
   champ.text = "9-5"; etape++; return }
  if (etape === 1) { if (!attendre(spot.calcul === "4", "qalc : " + spot.calcul)) return
   // qalc d'abord : rien à conclure tant que la liste d'applis n'est pas lue
   verifier(!spot.applisLues && spot.espace === "applis", "qalc avant la liste : " + spot.espace)
   liberer("list"); etape++; return }
  if (etape === 2) { if (!attendre(titres().indexOf("9-5 Agenda") >= 0, "appli : " + JSON.stringify(titres()))) return
   verifier(spot.espace === "applis", "qalc puis liste : l'appli reste dans Applis, " + spot.espace)
   // La liste d'abord, qalc ensuite
   champ.text = ""; bloquer("qalc"); etape++; return }
  if (etape === 3) { if (!attendre(!commande.running, "touch")) return
   champ.text = "9-5"; attente = 0; etape++; return }
  if (etape === 4) { attente++; if (attente < 4) return; attente = 0
   verifier(spot.calcul === "", "qalc retenu"); liberer("qalc"); etape++; return }
  if (etape === 5) { if (!attendre(spot.calcul === "4", "qalc : " + spot.calcul)) return
   verifier(spot.espace === "applis" && titres().indexOf("9-5 Agenda") >= 0, "liste puis qalc : " + spot.espace)
   // Rouvert, liste retenue : « 2+2 » sans appli passe dans les Actions à l'arrivée de la liste
   spot.actif = false; bloquer("list"); etape++; return }
  if (etape === 6) { if (!attendre(!commande.running, "touch")) return
   Etat.saisie = "2+2"; spot.actif = true; etape++; return }
  if (etape === 7) { if (!attendre(spot.calcul === "4", "qalc : " + spot.calcul)) return
   verifier(!spot.applisLues && spot.espace === "applis", "2+2 avant la liste : " + spot.espace)
   liberer("list"); etape++; return }
  if (etape === 8) { if (!attendre(spot.espace === "actions", "2+2 après la liste : " + spot.espace)) return
   verifier(titres()[0] === "= 4" && spot.sel === 0, "calcul en tête : " + JSON.stringify(titres()))
   Qt.quit() }''', bloquer=("list",))

    def test_ville_inconnue_reste_une_recherche(self):
        # « time machine » : ville inconnue, pas une demande d'heure ; Fichiers le cherche (revue PR 63, P2). « heure
        # paris » tapé avant la lecture des zones : Actions dès qu'elles arrivent.
        appels = self.scenario('''
  if (etape === 0) { if (!attendre(spot.applisLues, "liste d'applis jamais lue")) return
   champ.text = "heure paris"; etape++; return }
  if (etape === 1) { if (!attendre(spot.zonesHeure.length > 0 && spot.espace === "actions", "heure paris : " + spot.espace)) return
   champ.text = "time machine"; verifier(spot.espace === "applis", "time machine : " + spot.espace)
   trouver(spot, "nc-lanceur-onglets").choisir("fichiers"); etape++; return }
  if (etape === 2) { if (!attendre(titres().indexOf("firefox-notes.txt") >= 0, "Fichiers : " + JSON.stringify(titres()))) return
   verifier(spot.espace === "fichiers", "Fichiers choisi : " + spot.espace)
   Qt.quit() }''', fichiers={"zones/zone1970.tab": "# zones\nFR\t+4852+00220\tEurope/Paris\n"})
        self.assertIn("files time machine", appels)

    def test_raccourci_web_lu_apres_la_saisie(self):
        # « gh noctalia » déjà saisi à l'ouverture, liens-web.conf lu ensuite : Actions et le raccourci (revue PR 63, P2)
        self.scenario('''
  if (etape === 0) { verifier(spot.liensWeb.length === 0, "liens pas encore lus")
   Etat.saisie = "gh noctalia"; spot.actif = true; etape++; return }
  if (etape === 1) { if (!attendre(spot.espace === "actions" && titres()[0] === "noctalia", "gh noctalia : " + spot.espace + " " + JSON.stringify(titres()))) return
   verifier(spot.resultats[0].sous === "Rechercher sur GitHub", "raccourci : " + spot.resultats[0].sous)
   Qt.quit() }''', actif=False, fichiers={"config/nc/liens-web.conf": "gh\tGitHub\thttps://github.com/search?q=%s\n"})


if __name__ == "__main__":
    unittest.main()

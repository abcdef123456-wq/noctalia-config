"""Actions rapides du presse-papiers (PresseAnalyse.qml, PresseAction.qml, Presse.qml, réglage ILE_PRESSE_ACTIONS).

- Source : xdg-open en argv, adresse vérifiée, qalc en argv borné par timeout et sans lettre dans l'expression (donc ni devise
  ni taux de change en ligne), aucun minuteur qui se répète, réglage et README.
- Hors écran, avec le vrai qs lancé par « qs -p » (jamais l'île réelle) et de faux xdg-open et qalc qui notent seulement
  leurs arguments : détection (couleurs, liens, chemins, calculs, nombres, et ce qui ne doit rien proposer), conversions
  exactes, aperçu du calcul, clic sur « Ouvrir » (lien, dossier d'un fichier, dossier lui-même), chemin inexistant sans
  ligne, qalc absent, pendant un partage d'écran rien (ni ligne ni processus), réglage coupé, écran éteint.
HOME et XDG_* isolés, sans Wayland."""
import os
from pathlib import Path
import re
import runpy
import shutil
import tempfile
import textwrap
import unittest
import warnings
from unittest.mock import patch

from tests import _ile_hors_ecran as H

REPO = Path(__file__).resolve().parents[1]
QML = REPO / "home/.config/quickshell/nc-ile"


class Source(unittest.TestCase):
    def setUp(self):
        self.action = (QML / "PresseAction.qml").read_text()
        self.analyse = (QML / "PresseAnalyse.qml").read_text()
        self.code = re.sub(r"//.*", "", self.action + self.analyse)

    def test_commandes_en_argv(self):
        self.assertIn('Quickshell.execDetached(["xdg-open", info.url])', self.action)
        self.assertIn('["timeout", "2", "qalc", "-t", ', self.action)
        # Aucune commande construite par collage de texte copié : le seul « sh -c » reçoit le chemin en argument
        for m in re.finditer(r'"sh", "-c", "([^"]|\\")*"', self.code):
            self.assertNotIn("+", m.group(0))
        self.assertNotRegex(self.code, r"repeat: true|bash|eval")

    def test_calcul_sans_lettre(self):
        self.assertIn(r"^[0-9(.][0-9+\-*/^().%\s×÷]*$", self.analyse)

    def test_reglage_et_readme(self):
        with tempfile.TemporaryDirectory() as d, patch.dict(os.environ, HOME=d), warnings.catch_warnings():
            warnings.simplefilter("ignore", ResourceWarning)
            cles = runpy.run_path(str(REPO / "home/.local/bin/nc-reglages"))["PAR_CLE"]
        self.assertEqual(cles["ILE_PRESSE_ACTIONS"].defaut, "oui")
        self.assertEqual(cles["ILE_PRESSE_ACTIONS"].section, "Île")
        self.assertIn("`ILE_PRESSE_ACTIONS`", (REPO / "README.md").read_text())

    def test_presse_masque_et_utilise_la_ligne(self):
        presse = (QML / "Presse.qml").read_text()
        self.assertIn("masque: p.masque", presse)
        self.assertIn("PresseAction {", presse)


@unittest.skipUnless(shutil.which("qs"), "Quickshell requis")
class HorsEcran(unittest.TestCase):
    def lancer(self, corps, preparer=None, reglages="", etat=""):
        with tempfile.TemporaryDirectory(prefix="nc-actions-") as d:
            root = H.preparer(d, ("PresseAction", "Texte", "Ico", "Couleurs"), etat=etat, extra={"PresseAnalyse.qml": (QML / "PresseAnalyse.qml").read_text()},
                              singletons=("PresseAnalyse",))
            H.faux(root, "xdg-open")
            H.faux(root, "qalc", 'echo 14')
            (root / "home/dossier").mkdir()
            (root / "home/dossier/fichier.txt").write_text("x")
            if preparer:
                preparer(root)
            (root / "shell.qml").write_text(H.ENTETE + textwrap.dedent('''\
                ShellRoot {
                    property var objets: []
                    function creer(texte, masque) {
                        var c = Qt.createComponent("PresseAction.qml")
                        verifier(c.status === Component.Ready, c.errorString())
                        var o = c.createObject(w.contentItem, { width: 400, texte: texte, masque: !!masque })
                        objets.push(o); return o
                    }
                    function cliquerBouton(o) {
                        var b = trouver(o, "nc-presse-ouvrir"); verifier(b !== null && b.visible, "bouton Ouvrir absent")
                        for (var i = 0; i < b.children.length; i++) if (b.children[i].containsMouse !== undefined) { b.children[i].clicked(null); return }
                        verifier(false, "pas de zone de clic")
                    }
                    Window { id: w; visible: true; width: 440; height: 600; color: "black" }
                ''') + H.OUTILS + textwrap.dedent(corps) + "\n}\n")
            code, sortie = H.lancer(root)
            for e in H.ERREURS:
                self.assertNotIn(e, sortie, sortie)
            self.assertIn("FINI", sortie, sortie)
            return H.journal(root), root

    def test_detection_et_conversions(self):
        self.lancer('''
            Timer { interval: 200; running: true; onTriggered: {
                var D = PresseAnalyse.detecter
                function g(t) { var r = D(t, "/home/user"); return r ? r.genre : "" }
                verifier(g("#ff8800") === "couleur" && g("#F80") === "couleur" && g("rgb(255, 136, 0)") === "couleur" && g("rgba(1,2,3,0.5)") === "couleur", "couleurs")
                verifier(g("#ff88") === "" && g("#gg0000") === "" && g("rgb(300, 0, 0)") === "", "fausses couleurs")
                var c = D("#ff8800", "")
                verifier(c.hex === "#ff8800" && c.rgb === "rgb(255, 136, 0)" && c.hsl === "hsl(32, 100%, 50%)", "conversions : " + JSON.stringify(c))
                var c3 = D("#f80", ""); verifier(c3.hex === "#ff8800", "forme courte : " + c3.hex)
                var rgb = D("rgb(0, 0, 0)", ""); verifier(rgb.hex === "#000000" && rgb.hsl === "hsl(0, 0%, 0%)", "noir")
                verifier(g("https://exemple.fr/a?b=1#c") === "url" && g("http://x.org") === "url", "liens")
                verifier(g("ftp://x.org") === "" && g("javascript:alert(1)") === "" && g("https://a b.fr") === "" && g("https://x.fr/'; rm -rf") === "", "faux liens")
                verifier(g("/etc/hostname") === "chemin" && g("~/Documents/a b.pdf") === "chemin", "chemins")
                verifier(D("~/Documents/a b.pdf", "/home/user").chemin === "/home/user/Documents/a b.pdf", "~ remplacé")
                verifier(g("/") === "" && g("relatif/chemin") === "" && g("-rf /") === "", "faux chemins")
                verifier(g("2+3*4") === "calcul" && g("(1+2)^2 / 3") === "calcul" && g("12×3") === "calcul", "calculs")
                verifier(D("12×3", "").expr === "12*3", "× devient *")
                verifier(g("3 + a") === "" && g("2 km + 3 m") === "" && g("5 USD + 3") === "" && g("(1+2") === "" && g("-5+3") === "", "pas de lettres, parenthèses équilibrées, pas d'option")
                verifier(g("2024-10-28") === "" && g("12/05/2024") === "", "une date n'est pas un calcul")
                verifier(g("1234") === "nombre" && D("1234", "").hex === "0x4d2" && D("1234", "").bin === "0b10011010010", "nombre")
                verifier(g("123456789012345678") === "" && g("bonjour") === "" && g("") === "" && g("a\\nb") === "", "le reste : rien")
                verifier(PresseAnalyse.resultat("14\\n", "2+3*4") === "14" && PresseAnalyse.resultat("2+3", "2+3") === "" && PresseAnalyse.resultat("a\\nb", "1+1") === "", "sortie de qalc")
                console.log("FINI"); Qt.exit(0)
            } }
        ''')

    def test_couleur_lien_calcul_et_clics(self):
        j, root = self.lancer('''
            property var a: null
            property var b: null
            property var c: null
            property var d: null
            property var e: null
            property var f: null
            Timer { interval: 100; running: true; onTriggered: {
                a = creer("#336699"); b = creer("https://exemple.fr/page?x=1&y=2"); c = creer("2+3*4")
                d = creer(Quickshell.env("HOME") + "/dossier/fichier.txt"); e = creer(Quickshell.env("HOME") + "/dossier"); f = creer(Quickshell.env("HOME") + "/absent")
                attente.start()
            } }
            Timer { id: attente; interval: 1500; onTriggered: {
                verifier(a.utile && a.genre === "couleur", "couleur")
                verifier(b.utile && b.genre === "url", "lien")
                verifier(c.utile && c.calcule === "14", "calcul : " + c.calcule)
                verifier(d.utile && d.nature === "f" && e.utile && e.nature === "d", "chemins existants")
                verifier(!f.utile && f.nature === "", "chemin inexistant : pas de ligne")
                console.log("FINI"); Qt.exit(0)
            } }
        ''')
        self.assertEqual(j.count("qalc -t 2+3*4"), 1, j)            # un seul aperçu, en argv
        self.assertNotIn("xdg-open", j)                               # rien d'ouvert sans clic

    def test_clics_ouvrent_en_argv(self):
        # Le clic lance xdg-open avec l'adresse, le dossier du fichier, le dossier lui-même (un argument chacun)
        with tempfile.TemporaryDirectory(prefix="nc-actions-clic-") as d:
            root = H.preparer(d, ("PresseAction", "Texte", "Ico", "Couleurs"), extra={"PresseAnalyse.qml": (QML / "PresseAnalyse.qml").read_text()},
                              singletons=("PresseAnalyse",))
            H.faux(root, "xdg-open")
            (root / "home/dossier").mkdir()
            (root / "home/dossier/un fichier.txt").write_text("x")
            (root / "shell.qml").write_text(H.ENTETE + textwrap.dedent('''\
                ShellRoot {
                    property var objets: []
                    function creer(texte) { var c = Qt.createComponent("PresseAction.qml"); var o = c.createObject(w.contentItem, { width: 400, texte: texte }); objets.push(o); return o }
                    function cliquerBouton(o) {
                        var b = trouver(o, "nc-presse-ouvrir"); verifier(b !== null && b.visible, "bouton Ouvrir absent")
                        for (var i = 0; i < b.children.length; i++) if (b.children[i].containsMouse !== undefined) { b.children[i].clicked(null); return }
                        verifier(false, "pas de zone de clic")
                    }
                    Window { id: w; visible: true; width: 440; height: 600; color: "black" }
                ''') + H.OUTILS + textwrap.dedent('''\
                    property var b: null
                    property var d: null
                    property var e: null
                    Timer { interval: 100; running: true; onTriggered: {
                        b = creer("https://exemple.fr/page?x=1&y=2"); d = creer(Quickshell.env("HOME") + "/dossier/un fichier.txt"); e = creer(Quickshell.env("HOME") + "/dossier")
                        attente.start() } }
                    Timer { id: attente; interval: 1200; onTriggered: { cliquerBouton(b); cliquerBouton(d); cliquerBouton(e); fin.start() } }
                    Timer { id: fin; interval: 600; onTriggered: { console.log("FINI"); Qt.exit(0) } }
                }
                '''))
            code, sortie = H.lancer(root)
            for err in H.ERREURS:
                self.assertNotIn(err, sortie, sortie)
            self.assertIn("FINI", sortie, sortie)
            lignes = H.journal(root).splitlines()
            maison = str(root / "home")
            self.assertEqual(sorted(lignes), sorted(["xdg-open https://exemple.fr/page?x=1&y=2", "xdg-open " + maison + "/dossier", "xdg-open " + maison + "/dossier"]))

    def test_partage_ecran_eteint_reglage_coupe_et_qalc_absent(self):
        for nom, avant in (("masque", ""), ("ecran-eteint", "Etat.ecranVu = false"), ("reglage", "Reglages.valeurs = { ILE_PRESSE_ACTIONS: \"non\" }"),
                           ("qalc-absent", "PresseAnalyse.qalcDispo = 0")):
            with self.subTest(cas=nom):
                j, root = self.lancer('''
                    Timer { interval: 100; running: true; onTriggered: {
                        %s
                        var x = creer("2+3*4", %s), y = creer(Quickshell.env("HOME") + "/dossier", %s), z = creer("#336699", %s)
                        attente.start(); objets.push(x, y, z)
                    } }
                    Timer { id: attente; interval: 1200; onTriggered: {
                        %s
                        console.log("FINI"); Qt.exit(0)
                    } }
                ''' % (avant, "true" if nom == "masque" else "false", "true" if nom == "masque" else "false", "true" if nom == "masque" else "false",
                       ('verifier(!objets.slice(-3)[0].utile && !objets.slice(-3)[1].utile, "écran éteint : ni aperçu ni test du chemin")' if nom == "ecran-eteint" else
                        'verifier(objets.slice(-3).every(x => !x.utile), "aucune ligne") ') if nom != "qalc-absent" else
                       'verifier(!objets.slice(-3)[0].utile && objets.slice(-3)[1].utile && objets.slice(-3)[2].utile, "qalc absent : pas de résultat, le reste marche")'))
                self.assertNotIn("qalc", j)                  # ni aperçu ni test de présence lancé quand il ne doit pas
                if nom != "qalc-absent":
                    self.assertNotIn("xdg-open", j)


if __name__ == "__main__":
    unittest.main()

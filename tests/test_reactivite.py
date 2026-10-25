"""Interrupteurs réactifs de l'île (Voulu.qml, LectureFile.qml, et leur branchement dans Etat.qml) : sous Quickshell hors
écran, avec un faux nc-ile-etat (lent) et de fausses commandes qui réussissent ou échouent.
Cas : bascule immédiate, confirmation par la mesure, mesure contraire ignorée pendant la grâce, fin de grâce à 3 s qui
revient à la mesure, échec de la commande qui revient tout de suite, lecture mise en file (une seule en attente), lecture
dès la fin de la commande. Puis des contrôles statiques : tous les interrupteurs passent par le mécanisme."""
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import textwrap
import unittest

REPO = Path(__file__).resolve().parents[1]
QML = REPO / "home/.config/quickshell/nc-ile"

# Faux nc-ile-etat : note chaque lecture (début, fin), met 0,4 s à répondre, rend le contenu du fichier « mesure »
FAUX_ETAT = '''#!/bin/sh
echo "debut $(date +%s%N)" >> "$HOME/lectures"
sleep 0.4
cat "$HOME/mesure"
echo "fin $(date +%s%N)" >> "$HOME/lectures"
'''

SHELL = '''import QtQuick
import Quickshell
ShellRoot {
    id: t
    property var mesures: ({})
    property var echecs: []
    property var finis: []
    property int lus: 0
    property int etape: 0
    property real depuis: Date.now()
    function verifier(ok, m) { if (!ok) { console.error("ECHEC " + m); Qt.exit(2); throw new Error(m) } }
    function lire() { lecteur.demander() }
    // Ce que fait Etat.inverser : voulu tout de suite, puis la commande suivie
    function inverser(cle, valeur, cmd) { reac.voulu(cle, valeur); reac.lancer(cmd, cle) }
    Voulu {
        id: reac
        mesure: cle => t.mesures[cle]
        onEchec: (cle, code) => t.echecs.push(cle + ":" + code)
        onFini: (cle, code) => { t.finis.push(cle + ":" + code + "@" + Date.now()); lecteur.demander() }
    }
    LectureFile {
        id: lecteur
        commande: [Quickshell.env("HOME") + "/nc-ile-etat"]
        onLu: texte => {
            var m = {}
            texte.split("\\n").forEach(l => { var p = l.indexOf("="); if (p > 0) m[l.slice(0, p)] = l.slice(p + 1) })
            t.mesures = m; t.lus++
            reac.confirmer()
        }
    }
    readonly property var pas: [
PAS
    ]
    Timer {
        interval: 25; running: true; repeat: true
        onTriggered: {
            if (t.etape >= t.pas.length) { console.log("FINI"); Qt.quit(); return }
            if (Date.now() - t.depuis < t.pas[t.etape].d) return
            var f = t.pas[t.etape].f; t.etape++; t.depuis = Date.now(); f()
        }
    }
    Timer { interval: 14000; running: true; onTriggered: { console.error("ECHEC délai"); Qt.exit(3) } }
}
'''


def pas(*etapes):
    """Chaque étape : (délai en ms après la précédente, corps JavaScript)."""
    return ",\n".join("{ d: %d, f: function () { %s } }" % (d, corps) for d, corps in etapes)


@unittest.skipUnless(shutil.which("qs"), "Quickshell requis")
class Reactivite(unittest.TestCase):
    def executer(self, etapes, mesure="wifi=on\nhalo=0\n"):
        with tempfile.TemporaryDirectory(prefix="nc-reac-") as d:
            root = Path(d)
            (root / "run").mkdir(mode=0o700)
            for nom in ("Voulu.qml", "LectureFile.qml"):
                shutil.copy2(QML / nom, root / nom)
            (root / "qmldir").write_text("Voulu 1.0 Voulu.qml\nLectureFile 1.0 LectureFile.qml\n")
            (root / "mesure").write_text(mesure)
            (root / "nc-ile-etat").write_text(FAUX_ETAT)
            (root / "nc-ile-etat").chmod(0o755)
            (root / "shell.qml").write_text(SHELL.replace("PAS", pas(*etapes)))
            env = dict(os.environ, HOME=d, QT_QPA_PLATFORM="offscreen", QT_QUICK_BACKEND="software",
                       XDG_RUNTIME_DIR=str(root / "run"), XDG_CACHE_HOME=str(root / "cache"), XDG_CONFIG_HOME=str(root / "config"))
            env.pop("WAYLAND_DISPLAY", None)
            r = subprocess.run(["qs", "--no-color", "-p", str(root / "shell.qml")], env=env, capture_output=True, text=True, timeout=25)
            sortie = r.stdout + r.stderr
            self.assertEqual(r.returncode, 0, sortie)
            self.assertIn("FINI", sortie)
            for e in ("ReferenceError", "TypeError", "Cannot assign", "Binding loop", "is not a type", "ECHEC"):
                self.assertNotIn(e, sortie)
            lectures = (root / "lectures").read_text().splitlines() if (root / "lectures").exists() else []
            return sortie, lectures

    def test_bascule_immediate(self):
        self.executer([
            (0, 't.mesures = { wifi: "on" }; t.verifier(reac.valeur("wifi", t.mesures.wifi) === "on", "mesure avant")'),
            (0, 'reac.voulu("wifi", "off"); t.verifier(reac.valeur("wifi", t.mesures.wifi) === "off", "voulu pris tout de suite, sans lecture")'),
            (0, 't.verifier(reac.valeur("halo", "0") === "0", "une autre clé garde sa mesure")'),
        ])

    def test_confirmation_efface_le_voulu(self):
        self.executer([
            (0, 'reac.voulu("wifi", "off")'),
            (0, 'Qt.callLater(function () {}); t.lire()'),
            (1000, 't.verifier(t.lus === 1, "lecture finie"); t.verifier(Object.keys(reac.voulus).length === 0, "voulu effacé par la confirmation : " + JSON.stringify(reac.voulus))'),
            (0, 't.verifier(Date.now() - t.depuis < 3000, "bien avant la fin de la grâce")'),
        ], mesure="wifi=off\n")

    def test_mesure_contraire_pendant_la_grace_ignoree(self):
        self.executer([
            (0, 'reac.voulu("wifi", "off")'),
            (0, 't.lire()'),
            (900, 't.verifier(t.lus === 1 && t.mesures.wifi === "on", "la mesure contraire est arrivée")'),
            (0, 't.verifier(reac.valeur("wifi", t.mesures.wifi) === "off", "le bouton ne s inverse pas : " + reac.valeur("wifi", t.mesures.wifi))'),
            (0, 't.lire()'),
            (900, 't.verifier(t.lus === 2 && reac.valeur("wifi", t.mesures.wifi) === "off", "toujours voulu après une 2e mesure contraire")'),
        ], mesure="wifi=on\n")

    def test_fin_de_grace_a_3_s_revient_a_la_mesure(self):
        self.executer([
            (0, 'reac.voulu("wifi", "off")'),
            (2500, 't.verifier(reac.valeur("wifi", "on") === "off", "toujours voulu à 2,5 s")'),
            (700, 't.verifier(reac.valeur("wifi", "on") === "on", "à 3,2 s : retour à la mesure")'),
        ])

    def test_echec_de_la_commande_revient_tout_de_suite(self):
        self.executer([
            (0, 't.inverser("wifi", "off", ["sh", "-c", "sleep 0.15; exit 3"])'),
            (0, 't.verifier(reac.valeur("wifi", "on") === "off", "voulu pendant la commande")'),
            (600, 't.verifier(t.echecs.length === 1 && t.echecs[0] === "wifi:3", "échec signalé avec son code : " + t.echecs); '
                  't.verifier(reac.valeur("wifi", "on") === "on", "retour tout de suite à l état réel, bien avant 3 s")'),
            # commande réussie : le voulu reste, et la lecture part dès la fin
            (0, 't.inverser("halo", "1", ["sh", "-c", "sleep 0.1"])'),
            (500, 't.verifier(t.echecs.length === 1, "pas d échec pour une commande réussie"); t.verifier(reac.valeur("halo", "0") === "1", "voulu gardé")'),
        ])

    def test_commande_introuvable_est_un_echec(self):
        self.executer([
            (0, 't.inverser("wifi", "off", ["/nc-commande-qui-nexiste-pas"])'),
            (800, 't.verifier(t.echecs.length === 1, "binaire absent : échec signalé"); t.verifier(reac.valeur("wifi", "on") === "on", "retour à la mesure")'),
        ])

    def test_lecture_des_la_fin_de_la_commande(self):
        sortie, lectures = self.executer([
            (0, 't.inverser("wifi", "off", ["sh", "-c", "sleep 0.3"])'),
            (1200, 't.verifier(t.finis.length === 1 && t.lus === 1, "commande finie puis lecture : " + t.finis + " " + t.lus); '
                   'console.log("DELAI " + (Date.now() - t.depuis))'),
        ])
        debuts = [int(l.split()[1]) for l in lectures if l.startswith("debut")]
        self.assertEqual(len(debuts), 1, lectures)

    def test_lecture_demandee_pendant_une_lecture_est_mise_en_file(self):
        sortie, lectures = self.executer([
            (0, 't.lire(); t.lire(); t.lire(); t.lire()'),
            (100, 't.verifier(lecteur.enCours && lecteur.enAttente, "une lecture en cours, une seule en attente")'),
            (1500, 't.verifier(t.lus === 2, "deux lectures au total (la 1re et une seule rejouée) : " + t.lus); '
                   't.verifier(!lecteur.enAttente && !lecteur.enCours, "plus rien en attente")'),
        ])
        self.assertEqual(len([l for l in lectures if l.startswith("debut")]), 2, lectures)
        # la seconde ne commence qu'après la fin de la première (jamais deux à la fois)
        t = [(l.split()[0], int(l.split()[1])) for l in lectures]
        self.assertEqual([x[0] for x in t], ["debut", "fin", "debut", "fin"])
        self.assertLess(t[1][1], t[2][1] + 1)


class Branchement(unittest.TestCase):
    """Contrôles statiques : le mécanisme est commun (Etat.qml) et tous les interrupteurs l'utilisent."""
    def lire(self, nom):
        return (QML / nom).read_text()

    def test_etat_relit_a_la_fin_puis_a_1_5_s_et_met_en_file(self):
        s = self.lire("Etat.qml")
        self.assertRegex(s, r"onFini:\s*\{\s*etat\.lire\(\);\s*etat\.lirePage\(\);\s*relecture\.restart\(\)")
        self.assertRegex(s, r"Timer \{ id: relecture; interval: 1500")
        self.assertNotIn("interval: 700", s)
        self.assertEqual(s.count("LectureFile {"), 2, "nc-ile-etat et la page Système passent tous deux par la file")
        self.assertNotIn("!lecteurPage.running) return", s)
        self.assertRegex(s, r"onEchec:[^\n]*\n?[^\n]*notify-send")
        self.assertIn("reac.confirmer()", s)

    def test_les_interrupteurs_passent_par_le_mecanisme(self):
        for nom, attendus in (("Centre.qml", ['Etat.valeur(modelData.cle, centre.s[modelData.cle])', 'Etat.inverser(lc.modelData.cle']),
                              ("PageListe.qml", ['Etat.valeur(cle, Etat.sys[cle])', 'Etat.inverser(p.cle']),
                              ("Systeme.qml", ['Etat.valeur("protection", protection.v)', 'Etat.inverser("protection"', 'Etat.inverser("halo"', 'Etat.valeur("halo", Etat.sys.halo)']),
                              ("Recherche.qml", ['Etat.inverser("wifi"', 'Etat.inverser("bluetooth"'])):
            s = self.lire(nom)
            for a in attendus:
                self.assertIn(a, s, nom)
        # plus aucun interrupteur lié à la seule mesure
        self.assertNotIn('Etat.faire(["noctalia", "msg", p.wifi', self.lire("PageListe.qml"))
        self.assertNotIn("attente", self.lire("Systeme.qml").split("Protection de la batterie")[1].split("Modes d'énergie")[0])


@unittest.skipUnless(shutil.which("qs"), "Quickshell requis")
class EtatReel(unittest.TestCase):
    """Le vrai Etat.qml (avec ses voisins), faux nc-ile-etat et fausse commande « noctalia » dans un HOME jetable : un clic
    bascule tout de suite, la mesure le confirme dès la fin de la commande, un échec rend l'état réel."""
    def executer(self, casse):
        with tempfile.TemporaryDirectory(prefix="nc-reac-etat-") as d:
            root = Path(d)
            (root / "run").mkdir(mode=0o700)
            q = root / "q"
            shutil.copytree(QML, q, ignore=shutil.ignore_patterns("assets"))
            b = root / ".local/bin"
            b.mkdir(parents=True)
            # nc-ile-etat : lit le fichier « wifi » ; noctalia msg wifi-toggle : le bascule après 0,2 s, ou échoue si « casse » existe
            (b / "nc-ile-etat").write_text('#!/bin/sh\n[ -n "$1" ] && exit 0\necho "wifi=$(cat "$HOME/wifi")"\n')
            (b / "noctalia").write_text('#!/bin/sh\nsleep 0.2\n[ -e "$HOME/casse" ] && exit 1\n'
                                        '[ "$(cat "$HOME/wifi")" = on ] && echo off > "$HOME/wifi" || echo on > "$HOME/wifi"\n')
            (b / "notify-send").write_text('#!/bin/sh\necho "$@" >> "$HOME/notifs"\n')
            for f in b.iterdir():
                f.chmod(0o755)
            (root / "wifi").write_text("on\n")
            if casse:
                (root / "casse").write_text("")
            (q / "shell.qml").write_text(textwrap.dedent('''\
                import QtQuick
                import Quickshell
                ShellRoot {
                    id: t
                    property int etape: 0
                    property real depuis: Date.now()
                    function verifier(ok, m) { if (!ok) { console.error("ECHEC " + m); Qt.exit(2); throw new Error(m) } }
                    function affiche() { return Etat.valeur("wifi", Etat.sys.wifi) }
                    readonly property var pas: [
                        { d: 100, f: function () { Etat.vueNom = "reseau"; Etat.ecranOuvert = "T"; t.verifier(Etat.pageSys, "page Wi-Fi : " + Etat.vueActive); Etat.lire() } },
                        { d: 800, f: function () { t.verifier(Etat.sys.wifi === "on", "mesure lue : " + JSON.stringify(Etat.sys)) } },
                        { d: 0, f: function () { Etat.inverser("wifi", ["noctalia", "msg", "wifi-toggle"]); t.verifier(t.affiche() === "off", "bascule immédiate") } },
                        { d: 100, f: function () { t.verifier(Etat.sys.wifi === "on" && t.affiche() === "off", "la mesure contraire n inverse pas le bouton") } },
                        { d: 900, f: function () { ETAPE_FINALE } },
                        { d: 600, f: function () {} },
                    ]
                    Timer {
                        interval: 25; running: true; repeat: true
                        onTriggered: {
                            if (t.etape >= t.pas.length) { console.log("FINI"); Qt.quit(); return }
                            if (Date.now() - t.depuis < t.pas[t.etape].d) return
                            var f = t.pas[t.etape].f; t.etape++; t.depuis = Date.now(); f()
                        }
                    }
                    Timer { interval: 12000; running: true; onTriggered: { console.error("ECHEC délai"); Qt.exit(3) } }
                }
                '''))
            fin = ('t.verifier(Etat.sys.wifi === "on" && t.affiche() === "on", "échec : retour tout de suite à l état réel")' if casse else
                   't.verifier(Etat.sys.wifi === "off" && t.affiche() === "off", "confirmé dès la fin de la commande : " + JSON.stringify(Etat.sys)); '
                   't.verifier(Etat.valeur("wifi", "zz") === "zz", "voulu effacé")')
            (q / "shell.qml").write_text((q / "shell.qml").read_text().replace("ETAPE_FINALE", fin))
            env = dict(os.environ, HOME=d, QT_QPA_PLATFORM="offscreen", QT_QUICK_BACKEND="software", PATH=str(b) + ":" + os.environ["PATH"],
                       XDG_RUNTIME_DIR=str(root / "run"), XDG_CACHE_HOME=str(root / "cache"), XDG_CONFIG_HOME=str(root / "config"))
            env.pop("WAYLAND_DISPLAY", None)
            r = subprocess.run(["qs", "--no-color", "-p", str(q / "shell.qml")], env=env, capture_output=True, text=True, timeout=25)
            sortie = r.stdout + r.stderr
            self.assertIn("FINI", sortie, sortie)
            for e in ("ECHEC", "ReferenceError", "TypeError", "Binding loop"):
                self.assertNotIn(e, sortie)
            return (root / "notifs").exists()

    def test_inverser_de_bout_en_bout(self):
        self.assertFalse(self.executer(False), "pas de message d'erreur quand tout va bien")

    def test_echec_de_la_commande_rend_l_etat_reel_et_previent(self):
        self.assertTrue(self.executer(True), "message d'erreur envoyé")

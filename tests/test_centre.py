"""Centre de contrôle personnalisable (Centre.qml) hors écran : disposition de départ identique, mode édition (œil,
flèches, Réinitialiser, Terminer), au moins un module visible, clavier, disposition gardée par nc-ile-memo puis relue."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import textwrap
import unittest

REPO = Path(__file__).resolve().parents[1]
QML = REPO / "home/.config/quickshell/nc-ile"
BIN = REPO / "home/.local/bin"


@unittest.skipUnless(shutil.which("qs"), "Quickshell requis")
class Centre(unittest.TestCase):
    def executer(self, scenario, memo=None):
        with tempfile.TemporaryDirectory(prefix="nc-centre-") as d:
            root = Path(d)
            (root / "run").mkdir(mode=0o700)
            bin = root / ".local/bin"
            bin.mkdir(parents=True)
            shutil.copy2(BIN / "nc-ile-memo", bin / "nc-ile-memo")
            if memo is not None:
                etat = root / ".local/state/nc/ile"
                etat.mkdir(parents=True, mode=0o700)
                (etat / "centre.json").write_text(json.dumps(memo))
            for nom in ("Centre.qml", "Memo.qml", "Module.qml", "Rond.qml", "Glissiere.qml", "Texte.qml", "Ico.qml", "Couleurs.qml"):
                shutil.copy2(QML / nom, root / nom)
            (root / "Reglages.qml").write_text('pragma Singleton\nimport QtQuick\nQtObject {readonly property bool en: false; function t(fr,en){return fr} function val(k,d){return d}}')
            (root / "Notifs.qml").write_text('pragma Singleton\nimport QtQuick\nQtObject {property bool concentration: false; function basculerConcentration(){concentration=!concentration}}')
            (root / "Etat.qml").write_text(textwrap.dedent('''\
                pragma Singleton
                import QtQuick
                QtObject {
                    property var sys: ({ wifi: "on", bluetooth: "off", reseau: "Box" })
                    readonly property string dateLongue: "mardi 20 octobre"
                    property bool aBatterie: true
                    property int pourcent: 64
                    property bool branche: false
                    property string pochette: ""
                    property string iconeLecteur: ""
                    property string titre: ""
                    property string artiste: ""
                    property var lecteur: null
                    property bool joue: false
                    property bool nuit: false
                    property bool jeu: false
                    property real luminosite: 0.5
                    property real volume: 0.5
                    property bool muet: false
                    property int profil: 1
                    property var hauteurs: ({})
                    property var faits: []
                    property var allees: []
                    function faire(c) { faits.push(c) }
                    function aller(n) { allees.push(n) }
                    function lecturePause() {}
                    function reglerLuminosite(v) {}
                    function reglerVolume(v) {}
                    function choisirProfil(p) { profil = p }
                    function annoncerHauteur(nom, h) { var t = Object.assign({}, hauteurs); t[nom] = Math.round(h); hauteurs = t }
                }'''))
            (root / "qmldir").write_text("\n".join(
                ("singleton " if n in ("Memo", "Couleurs", "Reglages", "Etat", "Notifs") else "") + n + " 1.0 " + n + ".qml"
                for n in ("Centre", "Memo", "Module", "Rond", "Glissiere", "Texte", "Ico", "Couleurs", "Reglages", "Etat", "Notifs")))
            (root / "shell.qml").write_text(textwrap.dedent('''\
                import QtQuick
                import QtQuick.Window
                import QtTest
                import Quickshell
                ShellRoot {
                    id: test
                    property int etape: 0
                    property bool dansEtape: false
                    property var page: null
                    property var memo: ({})
                    TestCase { id: clavier; name: "CentreClavier"; when: false }
                    function verifier(ok, message) { if (!ok) { console.error(message); Qt.exit(2); throw new Error(message) } }
                    function trouver(item, nom) { if (item.objectName === nom) return item; for (var i = 0; i < item.children.length; i++) { var r = trouver(item.children[i], nom); if (r) return r } return null }
                    function cliquer(nom) { var it = trouver(page, nom); verifier(it !== null, nom + " absent"); for (var i = 0; i < it.children.length; i++) if (it.children[i].clicked !== undefined) { it.children[i].clicked(null); return } verifier(false, nom + " sans zone de clic") }
                    function pos(nom) { var it = trouver(page, nom); return it ? [it.x, it.y, it.width, it.height].join(",") : "absent" }
                    function creer() { if (page) page.destroy(); var c = Qt.createComponent("Centre.qml"); verifier(c.status === Component.Ready, c.errorString()); page = c.createObject(w.contentItem, { width: 400, height: 560 }); verifier(page !== null, "page absente") }
                    Window { id: w; visible: true; width: 432; height: 600; color: "#151f2b" }
                    Timer { interval: 100; running: true; repeat: true; onTriggered: {
                        if (test.dansEtape) return
                        test.dansEtape = true
                        try {
                ''') + scenario + textwrap.dedent('''
                        } finally { test.dansEtape = false }
                    } }
                    Timer { interval: 9000; running: true; onTriggered: Qt.exit(9) }
                }'''))
            env = dict(os.environ, HOME=d, QT_QPA_PLATFORM="offscreen", QT_QUICK_BACKEND="software",
                       XDG_RUNTIME_DIR=str(root / "run"), XDG_CACHE_HOME=str(root / "cache"), XDG_STATE_HOME=str(root / ".local/state"),
                       XDG_CONFIG_HOME=str(root / ".config"))
            env.pop("WAYLAND_DISPLAY", None)
            r = subprocess.run(["qs", "--no-color", "-p", str(root / "shell.qml")], env=env, capture_output=True, text=True, timeout=14)
            sortie = r.stdout + r.stderr
            self.assertEqual(r.returncode, 0, sortie)
            for e in ("ReferenceError", "TypeError", "Cannot assign", "Binding loop", "is not a type"):
                self.assertNotIn(e, sortie)
            f = root / ".local/state/nc/ile/centre.json"
            return json.loads(f.read_text()) if f.exists() else None

    DEFAUT = {"connexions": "0,0,168,168", "musique": "180,0,220,168", "nuit": "0,180,168,78", "jeu": "0,270,168,78",
              "luminosite": "180,180,104,168", "volume": "296,180,104,168", "energie": "0,360,400,64"}

    def test_disposition_de_depart_edition_et_sauvegarde(self):
        memo = self.executer('''
if (etape === 0) { creer(); etape++; return }
if (!page.pret) return
function etapeSuivante() { etape++ }
if (etape === 1) {
    var attendu = %s
    for (var id in attendu) verifier(pos("nc-centre-" + id) === attendu[id], id + " : " + pos("nc-centre-" + id) + " au lieu de " + attendu[id])
    verifier(page.disposition.hauteur === 424 && Etat.hauteurs.centre === 458, "hauteur : " + page.disposition.hauteur + " / " + Etat.hauteurs.centre)
    verifier(!page.edition && !trouver(page, "nc-centre-terminer").visible, "mode édition actif au départ")
    cliquer("nc-centre-crayon"); verifier(page.edition && trouver(page, "nc-centre-terminer").visible, "crayon sans effet")
    verifier(Etat.hauteurs.centre > 458, "l'île ne grandit pas pour les outils")
    cliquer("nc-centre-jeu-masquer"); etapeSuivante()
} else if (etape === 2) {
    verifier(page.masques.join() === "jeu" && trouver(page, "nc-centre-jeu") === null && trouver(page, "nc-centre-masque-jeu") !== null, "jeu non masqué")
    verifier(pos("nc-centre-nuit") === "0,180,168,78" && pos("nc-centre-luminosite") === "180,180,104,168", "disposition après masquage : " + pos("nc-centre-luminosite"))
    memo.reste = ["nuit", "luminosite", "volume", "energie", "musique"]; etapeSuivante()
} else if (etape === 3) {
    if (memo.reste.length) { cliquer("nc-centre-" + memo.reste.shift() + "-masquer"); return }
    verifier(page.visibles.join() === "connexions", "visibles : " + page.visibles.join())
    cliquer("nc-centre-connexions-masquer")
    verifier(page.visibles.join() === "connexions", "le dernier module a pu être masqué")
    cliquer("nc-centre-masque-jeu"); etapeSuivante()
} else if (etape === 4) {
    verifier(page.visibles.join() === "connexions,jeu", "remontrer : " + page.visibles.join())
    cliquer("nc-centre-reinitialiser"); etapeSuivante()
} else if (etape === 5) {
    verifier(page.masques.length === 0 && page.ordre.join() === page.defaut.join(), "réinitialiser")
    cliquer("nc-centre-energie-monter"); etapeSuivante()
} else if (etape === 6) {
    verifier(page.ordre.join() === "connexions,musique,nuit,jeu,luminosite,energie,volume", "monter : " + page.ordre.join())
    verifier(pos("nc-centre-energie") === "0,360,400,64" && pos("nc-centre-volume") === "0,436,168,168", "bandeau remonté, glissière seule étroite : " + pos("nc-centre-volume"))
    cliquer("nc-centre-energie-monter"); etapeSuivante()
} else if (etape === 7) {
    cliquer("nc-centre-jeu-masquer"); etapeSuivante()
} else if (etape === 8) {
    cliquer("nc-centre-terminer"); verifier(!page.edition, "Terminer"); etapeSuivante()
} else if (etape === 9 && Memo.enAttente === 0 && Memo.courant === null) { Qt.quit() }
''' % json.dumps(self.DEFAUT))
        self.assertEqual(memo, {"ordre": ["connexions", "musique", "nuit", "jeu", "energie", "luminosite", "volume"], "masques": ["jeu"]})

    def test_disposition_relue_et_clavier(self):
        memo = self.executer('''
if (etape === 0) { creer(); etape++; return }
if (!page.pret) return
if (etape === 1) {
    verifier(page.ordre.join() === "energie,connexions,musique,nuit,jeu,luminosite,volume" && page.masques.join() === "jeu,volume", "disposition non relue : " + page.ordre.join() + " / " + page.masques.join())
    verifier(pos("nc-centre-energie") === "0,0,400,64" && pos("nc-centre-connexions") === "0,76,168,168" && pos("nc-centre-musique") === "180,76,220,168", "bandeau en premier : " + pos("nc-centre-connexions"))
    verifier(pos("nc-centre-nuit") === "0,256,168,78" && pos("nc-centre-luminosite") === "180,256,168,168", "nuit seule, glissière seule étroite : " + pos("nc-centre-luminosite"))
    page.editer(true); verifier(page.activeFocus && page.choix === 0, "focus clavier")
    clavier.keyClick(Qt.Key_Down); verifier(page.choix === 1 && page.visibles[1] === "connexions", "flèche bas")
    clavier.keyClick(Qt.Key_Down, Qt.ShiftModifier); verifier(page.ordre.join() === "energie,musique,connexions,nuit,jeu,luminosite,volume" && page.choix === 2, "Maj + bas : " + page.ordre.join())
    clavier.keyClick(Qt.Key_Space); verifier(page.masques.join() === "jeu,volume,connexions", "Espace masque : " + page.masques.join())
    clavier.keyClick(Qt.Key_Up); clavier.keyClick(Qt.Key_Up); clavier.keyClick(Qt.Key_Up); verifier(page.choix === 0, "flèche haut bornée")
    clavier.keyClick(Qt.Key_Escape); verifier(!page.edition, "Échap termine")
    etape++
} else if (etape === 2 && Memo.enAttente === 0 && Memo.courant === null) { Qt.quit() }
''', memo={"ordre": ["energie", "connexions", "musique", "nuit", "jeu", "luminosite", "volume", "inconnu"], "masques": ["jeu", "volume", "inconnu"]})
        self.assertEqual(memo, {"ordre": ["energie", "musique", "connexions", "nuit", "jeu", "luminosite", "volume"], "masques": ["jeu", "volume", "connexions"]})

    def test_tout_masque_dans_le_fichier_est_repare(self):
        memo = self.executer('''
if (etape === 0) { creer(); etape++; return }
if (!page.pret) return
verifier(page.visibles.length === 7 && page.masques.length === 0, "tout masqué accepté")
Qt.quit()
''', memo={"ordre": ["connexions"], "masques": ["connexions", "musique", "nuit", "jeu", "luminosite", "volume", "energie"]})


if __name__ == "__main__":
    unittest.main()

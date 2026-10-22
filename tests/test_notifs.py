"""Notifications de l'île (Notifs.qml, PageNotifs.qml) hors écran, sur un bus de session privé (dbus-run-session) pour ne
pas toucher au serveur de notifications de la session : vraies notifications envoyées par notify-send ; groupes,
filtres, recherche, lu / non lu, report, appli masquée, clavier, état gardé par nc-ile-memo."""
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


@unittest.skipUnless(shutil.which("qs") and shutil.which("dbus-run-session") and shutil.which("notify-send"), "Quickshell, dbus-run-session et notify-send requis")
class Notifications(unittest.TestCase):
    def executer(self, scenario, memo=None, preparer=None, apres=None):
        with tempfile.TemporaryDirectory(prefix="nc-notifs-") as d:
            root = Path(d)
            (root / "run").mkdir(mode=0o700)
            bin = root / ".local/bin"
            bin.mkdir(parents=True)
            if preparer:
                preparer(root)
            shutil.copy2(BIN / "nc-ile-memo", bin / "nc-ile-memo")
            if memo is not None:
                (root / ".local/state/nc/ile").mkdir(parents=True, mode=0o700)
                (root / ".local/state/nc/ile/notifs.json").write_text(json.dumps(memo))
            for nom in ("Notifs.qml", "PageNotifs.qml", "Connexion.qml", "Memo.qml", "Defilement.qml", "Texte.qml", "Ico.qml", "Couleurs.qml"):
                shutil.copy2(QML / nom, root / nom)
            (root / "Reglages.qml").write_text('pragma Singleton\nimport QtQuick\nQtObject {readonly property bool en: true; property var valeurs: ({}); function t(fr,en){return en} function val(k,d){return valeurs[k]!==undefined?valeurs[k]:d}}')
            (root / "Etat.qml").write_text('pragma Singleton\nimport QtQuick\nQtObject {property var maintenant: new Date(); property var minute: new Date(); property var hauteurs: ({}); property int fermetures: 0; function annoncerHauteur(n,h){var t=Object.assign({},hauteurs);t[n]=Math.round(h);hauteurs=t} function fermer(){fermetures++}}')
            (root / "qmldir").write_text("\n".join(
                ("singleton " if n in ("Notifs", "Memo", "Couleurs", "Reglages", "Etat", "Connexion") else "") + n + " 1.0 " + n + ".qml"
                for n in ("PageNotifs", "Notifs", "Connexion", "Memo", "Defilement", "Texte", "Ico", "Couleurs", "Reglages", "Etat")))
            (root / "shell.qml").write_text(textwrap.dedent('''\
                import QtQuick
                import QtQuick.Window
                import QtTest
                import Quickshell
                import Quickshell.Io
                ShellRoot {
                    id: test
                    property int etape: 0
                    property bool dansEtape: false
                    property var page: null
                    property var memo: ({})
                    property int envoisFinis: 0
                    TestCase { id: clavier; name: "NotifsClavier"; when: false }
                    function verifier(ok, message) { if (!ok) { console.error(message); Qt.exit(2); throw new Error(message) } }
                    function trouver(item, nom) { if (item.objectName === nom) return item; for (var i = 0; i < item.children.length; i++) { var r = trouver(item.children[i], nom); if (r) return r } return null }
                    function cliquer(nom) { var it = trouver(page, nom); verifier(it !== null, nom + " absent"); for (var i = 0; i < it.children.length; i++) if (it.children[i].clicked !== undefined) { it.children[i].clicked(null); return } verifier(false, nom + " sans zone de clic") }
                    function creer() { var c = Qt.createComponent("PageNotifs.qml"); verifier(c.status === Component.Ready, c.errorString()); page = c.createObject(w.contentItem, { width: 400, height: 560, visible: false }); verifier(page !== null, "page absente"); page.visible = true }
                    // notify-send sur le bus privé : une notification après l'autre
                    property var envois: []
                    function notifier(app, titre, corps, urgence) { envois = envois.concat([[app, titre, corps, urgence || "normal"]]); envoyerSuivant() }
                    function envoyerSuivant() { if (envoi.running || !envois.length) return; var e = envois[0]; envois = envois.slice(1); envoi.command = ["notify-send", "-a", e[0], "-u", e[3], "-t", "60000", e[1], e[2]]; envoi.running = true }
                    Process { id: envoi; onExited: { test.envoisFinis++; test.envoyerSuivant() } }
                    Window { id: w; visible: true; width: 432; height: 600; color: "#151f2b" }
                    Timer { interval: 100; running: true; repeat: true; onTriggered: {
                        if (test.dansEtape) return
                        test.dansEtape = true
                        try {
                ''') + scenario + textwrap.dedent('''
                        } finally { test.dansEtape = false }
                    } }
                    Timer { interval: 14000; running: true; onTriggered: Qt.exit(9) }
                }'''))
            env = dict(os.environ, HOME=d, QT_QPA_PLATFORM="offscreen", QT_QUICK_BACKEND="software",
                       XDG_RUNTIME_DIR=str(root / "run"), XDG_CACHE_HOME=str(root / "cache"), XDG_STATE_HOME=str(root / ".local/state"),
                       XDG_CONFIG_HOME=str(root / ".config"))
            env.pop("WAYLAND_DISPLAY", None)
            r = subprocess.run(["dbus-run-session", "--", "qs", "--no-color", "-p", str(root / "shell.qml")], env=env, capture_output=True, text=True, timeout=20)
            sortie = r.stdout + r.stderr
            self.assertEqual(r.returncode, 0, sortie)
            for e in ("ReferenceError", "TypeError", "Cannot assign", "Binding loop", "is not a type"):
                self.assertNotIn(e, sortie)
            if apres:
                apres(root)
            f = root / ".local/state/nc/ile/notifs.json"
            return json.loads(f.read_text()) if f.exists() else None

    def test_carte_des_mises_a_jour(self):
        import time
        def preparer(root):
            (root / "cache/nc").mkdir(parents=True)
            (root / "cache/nc/paquets.json").write_text(json.dumps({
                "date": int(time.time()) - 7200, "total": 3, "noyau": True, "sources": {"depot": 2, "aur": 1, "flatpak": 0},
                "paquets": [{"source": "depot", "nom": "linux", "avant": "6.1", "apres": "6.2", "important": True},
                            {"source": "depot", "nom": "zsh", "avant": "5.1", "apres": "5.2", "important": False}]}))
            f = root / ".local/bin/nc-paquets"
            f.write_text('#!/bin/sh\necho "$1" >> "$HOME/appels-maj"\n'); f.chmod(0o755)
        vu = {}
        def apres(root):
            a = root / "appels-maj"
            vu["appels"] = a.read_text().split() if a.exists() else []
        self.executer('''
                if (etape === 0) { creer(); page.visible = true; etape++; return }
                if (etape === 1) {
                    var r = trouver(page, "nc-notifs-maj-resume"); verifier(r !== null, "carte des mises à jour absente")
                    if (r.text.indexOf("pending") < 0) return
                    verifier(r.text.indexOf("3 pending") === 0 && r.text.indexOf("linux") > 0 && r.text.indexOf("kernel") > 0 && r.text.indexOf("2 h ago") > 0, "résumé : " + r.text)
                    cliquer("nc-notifs-maj-chercher"); etape++; return }
                if (etape === 2) { cliquer("nc-notifs-maj-maj"); verifier(Etat.fermetures === 1, "« Mettre à jour » ferme l'île"); etape++; return }
                if (etape === 3) Qt.quit()
        ''', preparer=preparer, apres=apres)
        self.assertEqual(vu["appels"], ["verifier", "mettre-a-jour"])

    def test_carte_des_mises_a_jour_verification_impossible(self):
        """Revue PKG-03 : une vérification qui n'aboutit pas ne s'affiche jamais « À jour » ; l'heure est celle du
        dernier compte complet."""
        import time
        def preparer(root):
            (root / "cache/nc").mkdir(parents=True)
            (root / "cache/nc/paquets.json").write_text(json.dumps({
                "date": int(time.time()), "date_ok": int(time.time()) - 3 * 3600, "total": 0, "incomplet": ["depot", "flatpak"],
                "noyau": False, "sources": {"depot": 0, "aur": 0, "flatpak": 0}, "paquets": []}))
        self.executer('''
                if (etape === 0) { creer(); page.visible = true; etape++; return }
                if (etape === 1) {
                    var r = trouver(page, "nc-notifs-maj-resume"); verifier(r !== null, "carte des mises à jour absente")
                    if (r.text.indexOf("Could not") < 0) return
                    verifier(r.text.indexOf("Up to date") < 0 && r.text.indexOf("repositories, Flatpak") > 0 && r.text.indexOf("3 h ago") > 0, "résumé : " + r.text)
                    Qt.quit() }
        ''', preparer=preparer)

    def test_groupes_filtres_lecture_report_masquage_clavier(self):
        memo = self.executer('''
if (etape === 0) { creer(); etape++; return }
if (!Notifs.pret) return
if (etape === 1) { notifier("Alpha", "Un", "premier message"); notifier("Alpha", "Deux", "second message"); notifier("Beta", "Urgent", "alerte", "critical"); etape++; return }
if (etape === 2) { if (Notifs.liste.length < 3) return; etape++; return }
if (etape === 3) {
    verifier(Notifs.liste.map(x => x.summary).join() === "Urgent,Deux,Un", "ordre : " + Notifs.liste.map(x => x.summary).join())
    verifier(page.groupes.map(g => g.nom + ":" + g.notifs.length).join() === "Beta:1,Alpha:2", "groupes : " + page.groupes.map(g => g.nom + ":" + g.notifs.length).join())
    verifier(Notifs.nonLues === 3 && page.visibles.length === 3, "non lues")
    verifier(Notifs.banniere !== null && Notifs.banniere.summary === "Urgent", "bannière de la dernière reçue : " + (Notifs.banniere ? Notifs.banniere.summary : "aucune"))
    cliquer("nc-notifs-filtre-urgentes"); verifier(page.visibles.length === 1 && page.visibles[0].summary === "Urgent", "filtre urgentes")
    cliquer("nc-notifs-filtre-toutes")
    trouver(page, "nc-notifs-recherche").text = "SECOND"; verifier(page.visibles.map(x => x.summary).join() === "Deux", "recherche dans le texte : " + page.visibles.map(x => x.summary).join())
    trouver(page, "nc-notifs-recherche").text = "beta"; verifier(page.visibles.map(x => x.summary).join() === "Urgent", "recherche par appli")
    trouver(page, "nc-notifs-recherche").text = ""
    var deux = Notifs.liste.find(x => x.summary === "Deux")
    cliquer("nc-notif-" + deux.id + "-lue"); verifier(Notifs.nonLues === 2 && Notifs.lus[deux.id], "marquer lue")
    cliquer("nc-notifs-filtre-nonlues"); verifier(page.visibles.length === 2, "filtre non lues")
    cliquer("nc-notifs-filtre-toutes")
    cliquer("nc-notifs-groupe-alpha-titre"); etape = 4
} else if (etape === 4) {
    verifier(page.replies.alpha === true && page.visibles.length === 2, "groupe replié : " + page.visibles.length)
    page.replier("alpha")
    cliquer("nc-notifs-tout-lu"); verifier(Notifs.nonLues === 0, "tout lu")
    var un = Notifs.liste.find(x => x.summary === "Un")
    cliquer("nc-notif-" + un.id + "-reporter"); cliquer("nc-notif-" + un.id + "-reporter-15m")
    verifier(Notifs.liste.length === 2 && Notifs.attentes.length === 1 && Notifs.attentes[0].summary === "Un", "reportée : " + Notifs.liste.length + " / " + Notifs.attentes.length)
    verifier(Notifs.attentes[0].due > Date.now() + 14 * 60000, "échéance 15 min")
    Notifs.banniere = null
    Notifs.attentes = [Object.assign({}, Notifs.attentes[0], { due: Date.now() - 1 })]
    var r = Object.assign({}, Notifs.reports); r[un.id] = Date.now() - 1; Notifs.reports = r
    Notifs.verifierReports()
    verifier(Notifs.liste.length === 3 && Notifs.attentes.length === 0 && !Notifs.lus[un.id], "revenue à l'heure : " + Notifs.liste.length)
    verifier(Notifs.banniere === un, "bannière au retour")
    var beta = Notifs.liste.find(x => x.summary === "Urgent")
    cliquer("nc-notif-" + beta.id + "-masquer"); cliquer("nc-notif-" + beta.id + "-masquer-1h")
    verifier(Notifs.liste.length === 2 && Notifs.applisMasquees.join() === "beta" && Notifs.masques.beta > Date.now(), "appli masquée : " + Notifs.applisMasquees.join())
    cliquer("nc-notifs-masquee-beta"); verifier(Notifs.liste.length === 3 && Notifs.applisMasquees.length === 0, "démasquée")
    Notifs.masquerAppli(beta, "toujours"); verifier(Notifs.masques.beta === -1, "toujours")
    etape = 5
} else if (etape === 5) {
    page.forceActiveFocus(); clavier.keyClick(Qt.Key_Down); verifier(page.choix === 0 && page.visibles[0].summary === "Un", "flèche (la revenue est la plus récente) : " + page.visibles[0].summary)
    clavier.keyClick(Qt.Key_Delete); etape = 6
} else if (etape === 6) {
    if (Notifs.liste.length !== 1) return
    verifier(Notifs.liste[0].summary === "Deux", "Suppr retire la carte : " + Notifs.liste.map(x => x.summary).join())
    clavier.keyClick(Qt.Key_Down); clavier.keyClick(Qt.Key_Return); verifier(Etat.fermetures === 1, "Entrée ouvre et ferme l'île")
    etape = 7
} else if (etape === 7 && Notifs.liste.length === 0 && Memo.enAttente === 0 && Memo.courant === null) { Qt.quit() }
''')
        self.assertEqual(memo["masques"], {"beta": -1})
        self.assertEqual(memo["attentes"], [])
        self.assertEqual(list(memo["lus"].values()), [True], "seule la notification de l'appli masquée, toujours sur le serveur, garde son état lu : " + json.dumps(memo))

    def test_report_recree_apres_redemarrage_et_appli_masquee_sans_banniere(self):
        memo = self.executer('''
if (etape === 0) { creer(); etape++; return }
if (!Notifs.pret) return
if (etape === 1) {
    verifier(Notifs.revenues.length === 1 && Notifs.liste.length === 1 && Notifs.liste[0].synthetique && Notifs.liste[0].summary === "Rendez-vous", "report recréé : " + Notifs.liste.length)
    verifier(Notifs.banniere === Notifs.liste[0] && Notifs.attentes.length === 1 && Notifs.attentes[0].summary === "Plus tard", "bannière du report ; celui de demain attend")
    verifier(Notifs.nonLues === 1 && page.groupes[0].nom === "Agenda", "groupe de la synthétique")
    Notifs.banniere = null
    notifier("Gamma", "Caché", "rien ne doit sortir"); etape++; return
}
if (etape === 2) { if (envoisFinis < 1 || Notifs.brutes.length < 1) return; etape++; return }
if (etape === 3) {
    verifier(Notifs.liste.length === 1 && Notifs.banniere === null, "appli masquée : ni carte ni bannière")
    Notifs.ouvrir(Notifs.liste[0]); verifier(Notifs.liste.length === 0 && Notifs.revenues.length === 0, "ouvrir une synthétique la retire")
    etape++
} else if (etape === 4 && Memo.enAttente === 0 && Memo.courant === null) { Qt.quit() }
''', memo={"masques": {"gamma": -1}, "lus": {}, "heures": {},
           "attentes": [{"id": "9", "app": "Agenda", "summary": "Rendez-vous", "body": "dentiste", "image": "", "urgency": 1, "due": 1},
                        {"id": "10", "app": "Agenda", "summary": "Plus tard", "body": "", "image": "", "urgency": 1, "due": 4102444800000}]})
        self.assertEqual([a["summary"] for a in memo["attentes"]], ["Plus tard"])
        self.assertEqual(memo["masques"], {"gamma": -1})


    def test_bannieres_en_pause_le_temps_d_une_capture(self):
        # nc-session capture l'aperçu d'une session (ipc bannieresPause) : la bannière affichée se cache aussitôt, une
        # nouvelle attend la reprise puis s'affiche ; sans reprise, l'île reprend seule au bout de 3 s.
        self.executer('''
if (etape === 0) { creer(); etape++; return }
if (!Notifs.pret) return
if (etape === 1) { notifier("Alpha", "Session « Dev » enregistrée", "2 fenêtres"); etape++; return }
if (etape === 2) {
    if (!Notifs.banniere) return
    verifier(Notifs.banniere.summary === "Session « Dev » enregistrée", "bannière affichée")
    Notifs.pauseBannieres(true)
    verifier(Notifs.enPause && Notifs.banniere === null, "pause : la bannière affichée est cachée aussitôt")
    notifier("Beta", "Pendant la capture", "attend la reprise"); etape++; return
}
if (etape === 3) {
    if (envoisFinis < 2 || Notifs.liste.length < 2) return
    verifier(Notifs.banniere === null, "pendant la pause, aucune nouvelle bannière")
    verifier(Notifs.liste.length === 2, "rangée dans l'historique quand même")
    Notifs.pauseBannieres(false)
    verifier(!Notifs.enPause && Notifs.banniere && Notifs.banniere.summary === "Pendant la capture", "reprise : la bannière en attente s'affiche")
    Notifs.pauseBannieres(false)                     // une reprise de trop ne change rien
    verifier(Notifs.banniere && Notifs.banniere.summary === "Pendant la capture", "reprise en double sans effet")
    // Pause sans reprise (nc-session arrêté en pleine capture) : l'île reprend seule au bout de 3 s
    Notifs.banniere = null
    Notifs.pauseBannieres(true)
    test.memo = { t: Date.now() }
    notifier("Gamma", "Après la capture", "s'affiche à la reprise automatique"); etape++; return
}
if (etape === 4) {
    if (Notifs.enPause) {
        verifier(Notifs.banniere === null, "toujours en pause : rien d'affiché")
        verifier(Date.now() - test.memo.t < 3600, "reprise automatique en retard")
        return
    }
    var duree = Date.now() - test.memo.t
    verifier(duree >= 2900, "reprise automatique trop tôt : " + duree + " ms")
    verifier(Notifs.banniere && Notifs.banniere.summary === "Après la capture", "reprise automatique : la bannière en attente s'affiche")
    // Une bannière en attente fermée entre-temps ne revient pas
    Notifs.pauseBannieres(true)
    var g = Notifs.liste.find(x => x.summary === "Après la capture")
    Notifs.fermer(g)
    etape++; return
}
if (etape === 5) {
    if (Notifs.liste.some(x => x.summary === "Après la capture")) return
    Notifs.pauseBannieres(false)
    verifier(Notifs.banniere === null, "fermée pendant la pause : pas de bannière à la reprise")
    Qt.quit()
}
''')

if __name__ == "__main__":
    unittest.main()

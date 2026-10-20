"""Page Calendrier de l'île avec Google Agenda (par un faux nc-jarvis), hors écran : rien sans le réglage, points sous
les jours, agenda du jour, prochain événement, cache de 5 minutes et « Actualiser », erreur, bouton « + »."""
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

FAUX_JARVIS = '''#!/usr/bin/env python3
import json,os,sys
from pathlib import Path
r=json.loads(sys.stdin.readline())
with Path(os.environ["HOME"],"appels").open("a") as f:f.write(json.dumps(r)+"\\n")
scenario=json.loads(Path(os.environ["HOME"],"scenario.json").read_text())
if scenario.get("erreur"):print(json.dumps(dict(ok=False,error=scenario["erreur"])));sys.exit(1)
m=r["params"]["from"][:7]
ev=[e for e in scenario["events"] if e["debut"][:7]==m]
print(json.dumps(dict(ok=True,data=dict(events=ev,calendars=scenario["calendars"],timezone="Europe/Paris"))))
'''


@unittest.skipUnless(shutil.which("qs"), "Quickshell requis")
class Calendrier(unittest.TestCase):
    def executer(self, scenario, google="oui", evenements=None, erreur=""):
        with tempfile.TemporaryDirectory(prefix="nc-calendrier-") as d:
            root = Path(d)
            (root / "run").mkdir(mode=0o700)
            bin = root / ".local/bin"
            bin.mkdir(parents=True)
            (bin / "nc-jarvis").write_text(FAUX_JARVIS)
            (bin / "nc-jarvis").chmod(0o755)
            (root / "scenario.json").write_text(json.dumps(dict(events=evenements or [], calendars=[dict(nom="Perso", couleur="#1a73e8")], erreur=erreur)))
            for nom in ("Calendrier.qml", "GoogleAgenda.qml", "Defilement.qml", "Texte.qml", "Ico.qml", "Rond.qml", "Couleurs.qml"):
                shutil.copy2(QML / nom, root / nom)
            (root / "Reglages.qml").write_text('pragma Singleton\nimport QtQuick\nQtObject {readonly property bool en: false; readonly property var locale: Qt.locale("fr_FR"); property var valeurs: ({GOOGLE_INTEGRATION: "%s"}); function t(fr,en){return fr} function val(k,d){return valeurs[k]!==undefined?valeurs[k]:d}}' % google)
            (root / "Etat.qml").write_text(textwrap.dedent('''\
                pragma Singleton
                import QtQuick
                QtObject {
                    property var maintenant: new Date(2026, 9, 20, 18, 0)
                    property var minute: new Date(2026, 9, 20, 18, 0)
                    readonly property var mois: ["janvier","février","mars","avril","mai","juin","juillet","août","septembre","octobre","novembre","décembre"]
                    property var hauteurs: ({})
                    property var allees: []
                    function annoncerHauteur(nom, h) { var t = Object.assign({}, hauteurs); t[nom] = Math.round(h); hauteurs = t }
                    function aller(nom) { allees.push(nom) }
                }'''))
            (root / "AssistantEtat.qml").write_text('pragma Singleton\nimport QtQuick\nQtObject { property string brouillon: "" }')
            (root / "qmldir").write_text("\n".join(
                ("singleton " if n in ("GoogleAgenda", "Couleurs", "Reglages", "Etat", "AssistantEtat") else "") + n + " 1.0 " + n + ".qml"
                for n in ("Calendrier", "GoogleAgenda", "Defilement", "Texte", "Ico", "Rond", "Couleurs", "Reglages", "Etat", "AssistantEtat")))
            (root / "shell.qml").write_text(textwrap.dedent('''\
                import QtQuick
                import QtQuick.Window
                import Quickshell
                ShellRoot {
                    id: test
                    property int etape: 0
                    property bool dansEtape: false
                    property var page: null
                    property var memo: ({})
                    function verifier(ok, message) { if (!ok) { console.error(message); Qt.exit(2); throw new Error(message) } }
                    function trouver(item, nom) { if (item.objectName === nom) return item; for (var i = 0; i < item.children.length; i++) { var r = trouver(item.children[i], nom); if (r) return r } return null }
                    function creer() { var c = Qt.createComponent("Calendrier.qml"); verifier(c.status === Component.Ready, c.errorString()); page = c.createObject(w.contentItem, { width: 400, height: 560, visible: false }); verifier(page !== null, "page absente"); page.visible = true }
                    Window { id: w; visible: true; width: 432; height: 600; color: "#151f2b" }
                    Timer { interval: 100; running: true; repeat: true; onTriggered: {
                        if (test.dansEtape) return
                        test.dansEtape = true
                        try {
                ''') + scenario + textwrap.dedent('''
                        } finally { test.dansEtape = false }
                    } }
                    Timer { interval: 8000; running: true; onTriggered: Qt.exit(9) }
                }'''))
            env = dict(os.environ, HOME=d, QT_QPA_PLATFORM="offscreen", QT_QUICK_BACKEND="software",
                       XDG_RUNTIME_DIR=str(root / "run"), XDG_CACHE_HOME=str(root / "cache"))
            env.pop("WAYLAND_DISPLAY", None)
            r = subprocess.run(["qs", "--no-color", "-p", str(root / "shell.qml")], env=env, capture_output=True, text=True, timeout=12)
            sortie = r.stdout + r.stderr
            self.assertEqual(r.returncode, 0, sortie)
            for e in ("ReferenceError", "TypeError", "Cannot assign", "Binding loop", "is not a type"):
                self.assertNotIn(e, sortie)
            appels = root / "appels"
            return [json.loads(l) for l in appels.read_text().splitlines()] if appels.exists() else []

    EVENEMENTS = [
        dict(id="a", titre="Dentiste", lieu="Rue A", calendrier="Perso", couleur="#1a73e8", debut="2026-10-21T14:00:00+02:00", fin="2026-10-21T15:00:00+02:00", journee=False),
        dict(id="b", titre="Vacances", lieu="", calendrier="Perso", couleur="#1a73e8", debut="2026-10-24", fin="2026-10-26", journee=True),
        dict(id="c", titre="Réunion", lieu="", calendrier="Travail", couleur="#0b8043", debut="2026-10-21T09:30:00+02:00", fin="2026-10-21T10:00:00+02:00", journee=False),
        dict(id="d", titre="Passé", lieu="", calendrier="Perso", couleur="#1a73e8", debut="2026-10-20T08:00:00+02:00", fin="", journee=False),
        dict(id="n", titre="Novembre", lieu="", calendrier="Perso", couleur="#1a73e8", debut="2026-11-03T10:00:00+01:00", fin="", journee=False),
    ]

    def test_rien_sans_le_reglage(self):
        appels = self.executer('''
if (etape === 0) { creer(); etape++ }
else if (etape === 2) {
    verifier(!trouver(page, "nc-cal-plus").visible && !trouver(page, "nc-cal-actualiser").visible, "boutons Google visibles sans le réglage")
    verifier(!trouver(page, "nc-cal-agenda").visible && !trouver(page, "nc-cal-prochain").visible, "zone Google visible sans le réglage")
    verifier(trouver(page, "nc-cal-jour-21") !== null && !trouver(trouver(page, "nc-cal-jour-21"), "nc-cal-points").visible, "points sans le réglage")
    verifier(Etat.hauteurs.calendrier === undefined, "hauteur annoncée sans Google : la page garde sa taille d'avant")
    Qt.quit()
} else etape++
''', google="non", evenements=self.EVENEMENTS)
        self.assertEqual(appels, [], "aucun appel à JARVIS sans le réglage")

    def test_points_agenda_prochain_cache_et_plus(self):
        appels = self.executer('''
if (etape === 0) { creer(); etape++; return }
if (GoogleAgenda.enCours !== "") return
if (etape === 1) {
    verifier(page.mois !== null, "mois non chargé")
    var j21 = trouver(trouver(page, "nc-cal-jour-21"), "nc-cal-points"), j24 = trouver(trouver(page, "nc-cal-jour-24"), "nc-cal-points"), j25 = trouver(trouver(page, "nc-cal-jour-25"), "nc-cal-points"), j26 = trouver(trouver(page, "nc-cal-jour-26"), "nc-cal-points"), j22 = trouver(trouver(page, "nc-cal-jour-22"), "nc-cal-points")
    verifier(j21.visible && j21.children.filter(c => c.width === 5).length === 2, "deux calendriers le 21 : deux points")
    verifier(j24.visible && j25.visible && !j26.visible && !j22.visible, "journée entière du 24 au 25 (fin exclue), rien le 22 ni le 26")
    verifier(trouver(page, "nc-cal-prochain").visible && page.prochain.titre === "Réunion", "prochain : " + (page.prochain ? page.prochain.titre : "aucun"))
    page.jourChoisi = 21
    verifier(page.duJour.map(e => e.titre).join(",") === "Réunion,Dentiste", "agenda du 21 : " + page.duJour.map(e => e.titre).join(","))
    verifier(page.heure(page.duJour[1]) === "14:00 – 15:00" && page.heure(page.duJour[0]) === "09:30 – 10:00", "heures")
    page.jourChoisi = 24
    verifier(page.duJour.length === 1 && page.heure(page.duJour[0]) === "Toute la journée", "journée entière")
    verifier(Etat.hauteurs.calendrier > 300, "hauteur annoncée (l'île en tient compte, 410 au moins) : " + Etat.hauteurs.calendrier)
    page.charger(false); verifier(GoogleAgenda.enCours === "", "rechargé malgré le cache de 5 minutes")
    trouver(page, "nc-cal-actualiser").clic(); verifier(GoogleAgenda.enCours === "2026-10", "Actualiser ne recharge pas")
    etape++
} else if (etape === 2) {
    page.decalage = 1; etape++
} else if (etape === 3) {
    verifier(page.mois !== null && page.evenements.length === 1 && page.evenements[0].titre === "Novembre", "mois suivant : " + JSON.stringify(Object.keys(GoogleAgenda.cache)) + " cle=" + page.cle + " n=" + page.evenements.length + " erreur=" + page.erreur + " enCours=" + GoogleAgenda.enCours)
    verifier(page.prochain.titre === "Réunion", "le prochain reste celui d'octobre")
    page.decalage = 0; page.jourChoisi = 21; trouver(page, "nc-cal-plus").clic()
    verifier(AssistantEtat.brouillon.indexOf("2026-10-21") > 0 && Etat.allees[0] === "assistant", "bouton + : " + AssistantEtat.brouillon)
    Qt.quit()
}
''', evenements=self.EVENEMENTS)
        self.assertEqual([a["params"]["from"] for a in appels], ["2026-10-01", "2026-10-01", "2026-11-01"], "chargement, Actualiser, puis le mois suivant ; octobre ensuite repris du cache")
        self.assertTrue(all(a["op"] == "google.calendar" and a["confirmed"] is False for a in appels))
        self.assertEqual(appels[0]["params"]["to"], "2026-11-01")

    def test_erreur_puis_actualiser(self):
        appels = self.executer('''
if (etape === 0) { creer(); etape++; return }
if (GoogleAgenda.enCours !== "") return
if (etape === 1) {
    verifier(trouver(page, "nc-cal-erreur").visible && page.erreur === "Google n'est pas connecté", "erreur non affichée : " + page.erreur)
    verifier(page.mois === null && !trouver(trouver(page, "nc-cal-jour-21"), "nc-cal-points").visible, "pas d'événement en erreur")
    trouver(page, "nc-cal-actualiser").clic(); etape++
} else if (etape === 2) { verifier(page.erreur !== "", "erreur perdue"); Qt.quit() }
''', erreur="Google n'est pas connecté")
        self.assertEqual(len(appels), 2)


if __name__ == "__main__":
    unittest.main()

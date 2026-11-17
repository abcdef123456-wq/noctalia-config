"""Panneau Santé Garmin de l'île (GarminEtat.qml et Garmin*.qml, raccourci Super + Alt + S).
Sources : masquage en un seul endroit, aucun component inline ajouté, raccourci lié à GARMIN_ACTIF, file FIFO.
Hors écran (vrai qs lancé par « qs -p », HOME et XDG_* isolés, faux nc-garmin dans le PATH) : mesures vides pendant un partage
d'écran, et trois actions rapides jouées l'une après l'autre. Sauté si Quickshell manque (la CI n'en a pas)."""
import json
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests import _ile_hors_ecran as H

REPO = Path(__file__).resolve().parents[1]
QML = REPO / "home/.config/quickshell/nc-ile"
DEMO = {"actif": True, "installe": True, "connecte": False, "demo": True, "pret": True, "widgets_actifs": ["body_battery"],
        "widgets_catalogue": [{"id": "body_battery", "nom": "Batterie", "defaut": True, "actif": True}],
        "metriques": {"body_battery": 77, "pas": 4321}}
FAUX = r"""#!/bin/sh
# Faux nc-garmin : note début et fin ; un verrou détecte deux lancements en même temps.
J="@ROOT@/journal"
case "$1" in
  etat-json) cat "@ROOT@/etat.json"; exit 0 ;;
  installer) echo '{"erreur": "venv_absent", "message": "MODULE VENV MANQUANT", "contrat": 1}'; exit 1 ;;
esac
if ! mkdir "@ROOT@/verrou" 2>/dev/null; then echo "CHEVAUCHE $*" >> "$J"; fi
echo "DEBUT $* $(date +%s.%N)" >> "$J"
sleep 0.25
echo "FIN $* $(date +%s.%N)" >> "$J"
rmdir "@ROOT@/verrou" 2>/dev/null
exit 0
"""


def lire(nom):
    return (QML / nom).read_text()


def fichiers_garmin():
    return sorted(p.name for p in QML.glob("Garmin*.qml") if p.name != "GarminEtat.qml")


class Sources(unittest.TestCase):
    def test_masque_en_un_seul_endroit(self):
        etat = lire("GarminEtat.qml")
        self.assertIn("readonly property bool masque: Partage.silence", etat)
        self.assertIn("masque ? ({}) : brut", etat)
        self.assertIn('masque ? "" : resume', etat)
        for nom in fichiers_garmin() + ["shell.qml"]:
            t = lire(nom)
            self.assertNotRegex(t, r"GarminEtat\.(brut|resume)\b", nom + " lit une mesure sans le masque")
            self.assertNotRegex(t, r"GarminEtat\.metriques\b", nom)
            if nom != "shell.qml":
                self.assertNotIn("Partage.silence", t, nom + " : le masquage se fait dans GarminEtat")

    def test_file_fifo(self):
        etat = lire("GarminEtat.qml")
        self.assertEqual(len(re.findall(r"\bProcess\s*{", etat)), 2)  # lire et agir : jamais deux nc-garmin d'action
        self.assertIn("if (agir.running) { g.suites = g.suites.concat([args]); return }", etat)
        self.assertIn("g.suites.slice(1)", etat)
        self.assertEqual(len(re.findall(r"agir\.running = true", etat)), 1)
        self.assertIn('lancer(["sync", "--force"])', etat)
        self.assertNotIn("Timer", etat)

    def test_pas_de_component_inline_ajoute(self):
        d = subprocess.run(["git", "-C", str(REPO), "diff", "8ade4dc", "--", "home/.config/quickshell/nc-ile/shell.qml"],
                           capture_output=True, text=True)
        if d.returncode != 0:
            self.skipTest("historique git absent")
        self.assertNotIn("component ", d.stdout)
        self.assertIsNone(re.search(r"^\s*component\s+\w+\s*:", lire("shell.qml"), re.M))

    def test_mention_non_officiel_et_icone(self):
        a = lire("GarminAccueil.qml")
        self.assertIn("Connecteur non officiel : peut cesser de marcher si Garmin change son service", a)
        self.assertIn("Unofficial connector", a)
        self.assertIn("GarminIcone", lire("Garmin.qml"))

    def test_raccourci_depend_de_garmin_actif(self):
        r = (REPO / "home/.config/hypr/nc/raccourcis.lua").read_text()
        m = re.search(r'if nc\.reglage\("GARMIN_ACTIF", "non"\) == "oui" then\n(.*?)\nend', r, re.S)
        self.assertTrue(m)
        self.assertIn('SUPER .. " + ALT + code:39"', m.group(1))
        self.assertIn("ipc call ile garmin", m.group(1))
        self.assertEqual(r.count('SUPER .. " + ALT + code:39"'), 1)


@unittest.skipUnless(shutil.which("qs"), "Quickshell requis")
class HorsEcran(unittest.TestCase):
    def lancer(self, corps, etat=DEMO):
        with tempfile.TemporaryDirectory(prefix="nc-garmin-") as d:
            root = H.preparer(d, ("Couleurs",), extra={
                "GarminEtat.qml": lire("GarminEtat.qml"),
                "Partage.qml": "pragma Singleton\nimport QtQuick\nQtObject { property bool silence: false }\n"},
                singletons=("GarminEtat", "Partage"))
            (root / "etat.json").write_text(json.dumps(etat))
            bin_ = root / "home/.local/bin"
            bin_.mkdir(parents=True)
            (bin_ / "nc-garmin").write_text(FAUX.replace("@ROOT@", str(root)))
            (bin_ / "nc-garmin").chmod(0o755)
            (root / "shell.qml").write_text(H.ENTETE + "ShellRoot {\n property int etape: 0\n property int ticks: 0\n" + H.OUTILS
                                            + textwrap_corps(corps)
                                            + "\n Timer { interval: 15000; running: true; onTriggered: { console.error(\"ECHEC délai\"); Qt.exit(3) } }\n}\n")
            code, sortie = H.lancer(root, delai=40)
            for e in H.ERREURS:
                self.assertNotIn(e, sortie, sortie)
            self.assertIn("FINI", sortie, sortie)
            return H.journal(root)

    def test_masque_partage(self):
        self.lancer('''
            Timer { interval: 60; running: true; repeat: true; onTriggered: {
                if (etape === 0) { GarminEtat.panneauOuvert = true; etape++; return }
                if (etape === 1) {
                    if (!GarminEtat.lu) return
                    verifier(GarminEtat.metriquesVisibles.body_battery === 77, "mesure visible hors partage")
                    verifier(GarminEtat.resumeVisible !== "", "résumé visible hors partage")
                    Partage.silence = true
                    verifier(GarminEtat.masque && Object.keys(GarminEtat.metriquesVisibles).length === 0, "aucune mesure pendant le partage")
                    verifier(GarminEtat.resumeVisible === "", "résumé vide pendant le partage")
                    Partage.silence = false
                    verifier(GarminEtat.metriquesVisibles.pas === 4321, "mesures revenues")
                    console.log("FINI"); Qt.exit(0) }
            } }
        ''')

    def test_inactif_rien_ne_tourne(self):
        j = self.lancer('''
            Timer { interval: 60; running: true; repeat: true; onTriggered: {
                if (etape === 0) { GarminEtat.panneauOuvert = true; etape++; return }
                if (!GarminEtat.lu) return
                verifier(!GarminEtat.actif && Object.keys(GarminEtat.metriquesVisibles).length === 0, "inactif")
                ticks++
                if (ticks > 8) { console.log("FINI"); Qt.exit(0) }
            } }
        ''', etat={"actif": False})
        self.assertEqual(j, "")  # aucun sync ni action

    def test_trois_actions_en_file(self):
        j = self.lancer('''
            Timer { interval: 60; running: true; repeat: true; onTriggered: {
                if (etape === 0) { GarminEtat.panneauOuvert = true; etape++; return }
                if (etape === 1) {
                    if (!GarminEtat.lu) return
                    GarminEtat.hydrater("+250"); GarminEtat.hydrater("+500"); GarminEtat.actualiser()
                    etape++; return }
                if (etape === 2) {
                    ticks++
                    if (!GarminEtat.occupe && GarminEtat.suites.length === 0 && ticks > 5) { console.log("FINI"); Qt.exit(0) } }
            } }
        ''')
        self.assertNotIn("CHEVAUCHE", j)
        debuts = [l.split()[1:-1] for l in j.splitlines() if l.startswith("DEBUT")]
        # le sync d'ouverture, puis les trois actions, dans l'ordre des clics
        self.assertEqual([d for d in debuts if d[0] != "sync" or len(d) > 1 and d[1] == "--force"],
                         [["hydratation", "+250"], ["hydratation", "+500"], ["sync", "--force"]])
        temps = [(l.split()[0], float(l.split()[-1])) for l in j.splitlines()]
        for (a, ta), (b, tb) in zip(temps, temps[1:]):
            self.assertLessEqual(ta, tb)
        self.assertEqual([t[0] for t in temps], ["DEBUT", "FIN"] * (len(temps) // 2))

    def test_erreur_d_action_montree(self):
        self.lancer('''
            Timer { interval: 60; running: true; repeat: true; onTriggered: {
                if (etape === 0) { GarminEtat.panneauOuvert = true; etape++; return }
                if (etape === 1) { if (!GarminEtat.lu) return; GarminEtat.installer(); etape++; return }
                if (GarminEtat.erreur !== "") {
                    verifier(GarminEtat.erreur === "MODULE VENV MANQUANT", "message du moteur : " + GarminEtat.erreur)
                    console.log("FINI"); Qt.exit(0) }
            } }
        ''')



def textwrap_corps(corps):
    import textwrap
    return textwrap.dedent(corps)


if __name__ == "__main__":
    unittest.main()

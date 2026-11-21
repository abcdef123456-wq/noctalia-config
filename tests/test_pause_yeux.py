"""Pause des yeux 20-20-20 (Etat.qml, Compact.qml, réglage PAUSE_YEUX). Le bloc du vrai Etat.qml est extrait dans un
Scope de test (comme test_ile_telechargements), avec un intervalle de 300 ms au lieu de 20 min ; qs hors écran, HOME et
XDG_* isolés, sans Wayland ni Hyprland."""
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest

from tests import _ile_hors_ecran as H

REPO = Path(__file__).resolve().parents[1]
QML = REPO / "home/.config/quickshell/nc-ile"
ETAT = (QML / "Etat.qml").read_text()


def bloc():
    i = ETAT.index("    // ── Pause des yeux 20-20-20")
    j = ETAT.index("    // ── fin de la pause des yeux")
    return ETAT[i:j]


class Source(unittest.TestCase):
    def test_vingt_minutes_vingt_secondes_un_seul_minuteur(self):
        b = bloc()
        self.assertIn("property int pauseYeuxIntervalle: 20 * 60 * 1000", b)
        self.assertIn('etat.activite("pause-yeux", 20000)', b)
        self.assertEqual(b.count("Timer {"), 1)
        self.assertIn("repeat: false", b)
        self.assertNotIn("component ", b)

    def test_pilule_reglage_et_doc(self):
        compact = (QML / "Compact.qml").read_text()
        self.assertIn('"pause-yeux": pauseYeux', compact)
        self.assertIn('montre: c.mode === "pause-yeux"', compact)
        r = subprocess.run([sys.executable, str(REPO / "home/.local/bin/nc-reglages"), "get", "PAUSE_YEUX"], capture_output=True, text=True,
                           env={"HOME": "/nonexistent", "PATH": "/usr/bin:/bin", "NC_LANGUE": "fr"}, timeout=30)
        self.assertEqual(r.stdout.strip(), "non", r.stdout + r.stderr)
        self.assertIn("PAUSE_YEUX", (REPO / "README.md").read_text())


@unittest.skipUnless(shutil.which("qs"), "Quickshell requis")
class HorsEcran(unittest.TestCase):
    def lancer(self, corps, reglage="oui"):
        with tempfile.TemporaryDirectory(prefix="nc-yeux-") as d:
            root = H.preparer(d, ("Couleurs",), extra={"Partage.qml": "pragma Singleton\nimport QtQuick\nQtObject { property bool silence: false }"},
                              singletons=("Partage",))
            if reglage is not None:                          # None : réglage absent, la valeur par défaut compte
                (root / "Reglages.qml").write_text((root / "Reglages.qml").read_text().replace(
                    "property var valeurs: ({})", "property var valeurs: ({ PAUSE_YEUX: \"%s\" })" % reglage))
            court = bloc().replace("20 * 60 * 1000", "300")
            self.assertNotEqual(court, bloc())
            (root / "shell.qml").write_text(H.ENTETE + textwrap.dedent('''\
                ShellRoot {
                    Scope {
                        id: etat
                        property bool ecranVu: true
                        property bool jeu: false
                        property bool plein: false
                        property string activiteType: ""
                        property int nbActivites: 0
                        property int derniereDuree: 0
                        function activite(t, duree) { activiteType = t; derniereDuree = duree; nbActivites++ }
                        function pleinEcranActif() { return plein }
                    ''') + court + textwrap.dedent('''\
                    }
                    ''') + H.OUTILS + textwrap.dedent(corps) + "\n}\n")
            _, sortie = H.lancer(root, delai=30)
            for e in H.ERREURS:
                self.assertNotIn(e, sortie, sortie)
            self.assertIn("FINI", sortie, sortie)

    def test_pause_puis_rearmee(self):
        self.lancer('''
            Timer { interval: 1100; running: true; onTriggered: {
                verifier(etat.nbActivites >= 2 && etat.activiteType === "pause-yeux" && etat.derniereDuree === 20000, "pauses : " + etat.nbActivites)
                verifier(pauseYeux.running, "réarmé")
                console.log("FINI"); Qt.exit(0) } }
        ''')

    def test_non_aucun_minuteur(self):
        self.lancer('''
            Timer { interval: 100; running: true; repeat: true; property int tours: 0; onTriggered: {
                verifier(!pauseYeux.running, "aucun minuteur à non")
                if (++tours < 10) return
                verifier(etat.nbActivites === 0, "aucune pause")
                Reglages.valeurs = { PAUSE_YEUX: "oui" }
                verifier(pauseYeux.running, "armé dès que le réglage passe à oui")
                Reglages.valeurs = { PAUSE_YEUX: "non" }
                verifier(!pauseYeux.running, "coupé dès qu'il repasse à non")
                running = false; console.log("FINI"); Qt.exit(0) } }
        ''', reglage="non")

    def test_eteint_par_defaut(self):
        self.lancer('''
            Timer { interval: 700; running: true; onTriggered: {
                verifier(!pauseYeux.running && etat.nbActivites === 0, "réglage absent : rien")
                console.log("FINI"); Qt.exit(0) } }
        ''', reglage=None)

    def test_ecran_eteint_ou_verrouille_arrete(self):
        self.lancer('''
            Timer { interval: 100; running: true; repeat: true; property int tours: 0; onTriggered: {
                tours++
                if (tours === 1) { verifier(pauseYeux.running, "armé"); etat.ecranVu = false; verifier(!pauseYeux.running, "arrêté écran non vu"); return }
                if (tours < 10) { verifier(!pauseYeux.running && etat.nbActivites === 0, "rien pendant que l'écran dort"); return }
                etat.ecranVu = true
                verifier(pauseYeux.running, "repart au retour")
                running = false; console.log("FINI"); Qt.exit(0) } }
        ''')

    def test_jeu_partage_plein_ecran_pas_de_pause(self):
        for etat in ("etat.jeu = true", "Partage.silence = true", "etat.plein = true"):
            with self.subTest(etat):
                self.lancer('''
                    Component.onCompleted: %s
                    Timer { interval: 1100; running: true; onTriggered: {
                        verifier(etat.nbActivites === 0, "pas de pause : " + etat.nbActivites)
                        verifier(pauseYeux.running, "réarmé pour plus tard")
                        console.log("FINI"); Qt.exit(0) } }
                ''' % etat)


if __name__ == "__main__":
    unittest.main()

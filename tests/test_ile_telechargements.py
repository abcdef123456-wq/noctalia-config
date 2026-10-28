"""Téléchargement terminé dans l'île (Etat.qml : relevé du dossier Téléchargements, inotify, fin « téléchargé »; Compact.qml,
Ile.qml ; réglage ILE_TELECHARGEMENTS).

Ce qui existait : le relevé régulier (find toutes les 6 s), la pilule « Téléchargé », le réglage. Ajouts : inotifywait quand il est
installé (plus aucun réveil au repos), .tmp en plus de .part et .crdownload, « Fichier.pdf téléchargé », un clic ouvre le dossier,
rien pendant un partage d'écran.
- Hors écran, avec le vrai qs lancé par « qs -p » : le bloc « Téléchargements » du vrai Etat.qml est extrait dans un Scope de
  test (comme test_ile_energie), avec de faux inotifywait, xdg-user-dir et xdg-open qui notent leurs arguments.
HOME et XDG_* isolés, sans Wayland."""
from pathlib import Path
import re
import shutil
import tempfile
import textwrap
import unittest

from tests import _ile_hors_ecran as H

REPO = Path(__file__).resolve().parents[1]
QML = REPO / "home/.config/quickshell/nc-ile"
ETAT = (QML / "Etat.qml").read_text()


def bloc():
    i = ETAT.index("    // ── Téléchargements du navigateur")
    j = ETAT.index("    function octets(n) {")
    return ETAT[i:j]


class Source(unittest.TestCase):
    def test_inotify_detecte_et_silencieux_sans_lui(self):
        b = bloc()
        self.assertIn("command -v inotifywait", b)
        self.assertIn("inotifywait -m -q -e create -e moved_to -e moved_from -e delete -e close_write", b)
        self.assertIn("exit 4", b)
        # Le relevé régulier ne tourne plus au repos quand inotify surveille
        self.assertIn("(etat.telechargements.length > 0 || !etat.surveillance)", b)
        for ext in (".part", ".crdownload", ".tmp"):
            self.assertIn(ext.lstrip("."), b)

    def test_masque_en_partage_et_clic(self):
        b = bloc()
        self.assertIn("!Partage.silence", b)                    # aucune activité pendant un partage
        compact = (QML / "Compact.qml").read_text()
        self.assertIn("Partage.silence ? Etat.sansNom : telechargement.t.nom", compact)
        self.assertIn('Reglages.t("téléchargé", "downloaded")', compact)
        self.assertIn('Etat.activiteType === "telechargement-fini" && Etat.dossierTel !== "" ? Etat.ouvrirTelechargements()', (QML / "Ile.qml").read_text())
        self.assertIn('Quickshell.execDetached(["xdg-open", dossierTel])', b)

    def test_reglage_toujours_la_et_readme(self):
        self.assertIn('R("ILE_TELECHARGEMENTS"', (REPO / "home/.local/bin/nc-reglages").read_text())
        readme = (REPO / "README.md").read_text()
        self.assertIn("inotifywait", readme)

    def test_aucun_sondage_en_plus(self):
        b = re.sub(r"//.*", "", bloc())
        self.assertEqual(len(re.findall(r"repeat: true", b)), 1)             # le seul : le relevé de repli


@unittest.skipUnless(shutil.which("qs"), "Quickshell requis")
class HorsEcran(unittest.TestCase):
    def lancer(self, corps, inotify="", reglage=None, silence=False, ecran=True, fichiers=("doc.pdf.part",)):
        with tempfile.TemporaryDirectory(prefix="nc-tele-") as d:
            root = H.preparer(d, ("Couleurs",), extra={"Partage.qml": "pragma Singleton\nimport QtQuick\nQtObject { property bool silence: %s }" % ("true" if silence else "false")},
                              singletons=("Partage",))
            dl = root / "home/Telechargements"
            dl.mkdir()
            for f in fichiers:
                (dl / f).write_text("x" * 100)
            if reglage:
                (root / "Reglages.qml").write_text((root / "Reglages.qml").read_text().replace("property var valeurs: ({})", "property var valeurs: " + reglage))
            H.faux(root, "xdg-user-dir", 'echo "%s"' % dl)
            H.faux(root, "xdg-open")
            if inotify is not None:
                H.faux(root, "inotifywait", inotify.replace("DL", str(dl)) if inotify else "exec sleep 8")
            (root / "shell.qml").write_text(H.ENTETE + "import Quickshell.Io\nimport Quickshell.Services.UPower\n" + textwrap.dedent('''\
                ShellRoot {
                    Scope {
                        id: etat
                        property bool ecranVu: %s
                        property string activiteType: ""
                        property int nbActivites: 0
                        function activite(t, duree) { activiteType = t; nbActivites++ }
                    ''' % ("true" if ecran else "false")) + bloc() + textwrap.dedent('''\
                    }
                    ''') + H.OUTILS + textwrap.dedent(corps) + "\n}\n")
            code, sortie = H.lancer(root, delai=40)
            for e in H.ERREURS:
                self.assertNotIn(e, sortie, sortie)
            self.assertIn("FINI", sortie, sortie)
            return H.journal(root)

    FIN_PAR_INOTIFY = 'sleep 1; mv "DL/doc.pdf.part" "DL/doc.pdf" && echo doc.pdf.part; exec sleep 8'

    def test_fin_vue_par_inotify_et_clic_ouvre_le_dossier(self):
        j = self.lancer('''
            Timer { interval: 200; running: true; repeat: true; property int tours: 0
                onTriggered: {
                    tours++
                    if (etat.telechargeFini === "" && tours < 60) {
                        if (tours === 3) verifier(etat.telechargements.length === 1 && etat.telechargements[0].nom === "doc.pdf", "en cours : doc.pdf : " + JSON.stringify(etat.telechargements))
                        return }
                    verifier(etat.telechargeFini === "doc.pdf" && etat.activiteType === "telechargement-fini", "fin vue : " + etat.telechargeFini)
                    verifier(etat.surveillance && !etat.sansInotify, "inotify surveille")
                    verifier(etat.dossierTel.indexOf("Telechargements") > 0, "dossier retenu : " + etat.dossierTel)
                    running = false
                    etat.ouvrirTelechargements()
                    fin.start() } }
            Timer { id: fin; interval: 500; onTriggered: { console.log("FINI"); Qt.exit(0) } }
        ''', inotify=self.FIN_PAR_INOTIFY)
        self.assertIn("inotifywait -m -q -e create -e moved_to -e moved_from -e delete -e close_write --format %f ", j)
        self.assertRegex(j, r"xdg-open \S+/Telechargements\n")
        self.assertEqual(j.count("xdg-open "), 1, j)

    def test_tmp_aussi(self):
        self.lancer('''
            Timer { interval: 200; running: true; repeat: true; property int tours: 0
                onTriggered: {
                    tours++
                    if (etat.telechargeFini === "" && tours < 60) return
                    verifier(etat.telechargeFini === "rapport.xlsx", "fin d'un .tmp : " + etat.telechargeFini)
                    console.log("FINI"); Qt.exit(0) } }
        ''', inotify='sleep 1; mv "DL/rapport.xlsx.tmp" "DL/rapport.xlsx" && echo rapport.xlsx.tmp; exec sleep 8', fichiers=("rapport.xlsx.tmp",))

    def test_masque_pendant_un_partage(self):
        self.lancer('''
            Timer { interval: 3500; running: true; onTriggered: {
                verifier(etat.telechargeFini === "" && etat.nbActivites === 0, "rien pendant un partage : " + etat.telechargeFini)
                console.log("FINI"); Qt.exit(0) } }
        ''', inotify=self.FIN_PAR_INOTIFY, silence=True)

    def test_reglage_coupe_aucun_processus(self):
        j = self.lancer('''
            Timer { interval: 1500; running: true; onTriggered: {
                verifier(etat.telechargements.length === 0 && etat.telechargeFini === "", "réglage non : rien")
                console.log("FINI"); Qt.exit(0) } }
        ''', inotify=self.FIN_PAR_INOTIFY, reglage='({ ILE_TELECHARGEMENTS: "non" })')
        self.assertNotIn("inotifywait", j)

    def test_ecran_eteint_aucun_processus(self):
        j = self.lancer('''
            Timer { interval: 1500; running: true; onTriggered: {
                verifier(etat.telechargements.length === 0, "écran éteint : aucun relevé")
                console.log("FINI"); Qt.exit(0) } }
        ''', inotify=self.FIN_PAR_INOTIFY, ecran=False)
        self.assertNotIn("inotifywait", j)

    def test_sans_inotifywait_le_releve_regulier_reste(self):
        # inotifywait absent (le faux sort avec 4 comme le script) : repli sur le relevé régulier, qui voit la fin aussi
        self.lancer('''
            Timer { interval: 300; running: true; repeat: true; property int tours: 0
                onTriggered: {
                    tours++
                    if (tours === 4) { verifier(etat.sansInotify && !etat.surveillance, "repli : " + etat.sansInotify); Quickshell.execDetached(["mv", Quickshell.env("HOME") + "/Telechargements/doc.pdf.part", Quickshell.env("HOME") + "/Telechargements/doc.pdf"]) }
                    if (etat.telechargeFini === "" && tours < 80) return
                    verifier(etat.telechargeFini === "doc.pdf", "fin vue par le relevé : " + etat.telechargeFini)
                    console.log("FINI"); Qt.exit(0) } }
        ''', inotify="exit 4")


if __name__ == "__main__":
    unittest.main()

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
        self.assertEqual(len(re.findall(r"\bProcess\s*{", etat)), 3)  # lire, agir (file FIFO) et connexion (attend kitty, à part)
        self.assertIn("if (agir.running) { g.suites = g.suites.concat([args]); return }", etat)
        self.assertIn("g.suites.slice(1)", etat)
        self.assertEqual(len(re.findall(r"agir\.running = true", etat)), 1)
        self.assertIn('lancer(["sync", "--force"])', etat)
        self.assertNotIn("Timer", etat)

    def test_connexion_a_part_et_relecture(self):
        etat = lire("GarminEtat.qml")
        m = re.search(r"Process\s*{\s*id:\s*connexion\b(.*?)\n    }", etat, re.S)
        self.assertTrue(m, "Process connexion absent")
        self.assertIn('"login"', m.group(1))
        self.assertIn("onExited: g.relire()", m.group(1))
        self.assertIn("if (!connexion.running)", etat)  # une seule connexion à la fois

    def test_partage_pose_un_fichier_vide_0600(self):
        t = lire("Partage.qml")
        self.assertIn("nc-partage-actif", t)
        self.assertIn('Quickshell.env("XDG_RUNTIME_DIR")', t)
        self.assertIn("if (marque === \"\") return", t)  # sans XDG_RUNTIME_DIR : rien n'est écrit
        self.assertIn("onSilenceChanged: poserMarque(silence)", t)
        self.assertIn("Component.onCompleted: poserMarque(false)", t)  # effacé au démarrage de l'île
        self.assertIn('["rm", "-f", marque]', t)
        self.assertIsNone(re.search(r"^\s*component\s+\w+\s*:", t, re.M))
        # la commande réelle, jouée dans un dossier temporaire : fichier vide en 0600
        m = re.search(r'\["sh", "-c", "((?:[^"\\]|\\.)*)", "sh", marque\]', t)
        self.assertTrue(m, "commande de pose introuvable")
        cmd = m.group(1).replace('\\"', '"')
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "nc-partage-actif"
            subprocess.run(["sh", "-c", cmd, "sh", str(f)], check=True, env={"PATH": "/usr/bin:/bin"})
            self.assertEqual(f.stat().st_size, 0)
            self.assertEqual(f.stat().st_mode & 0o777, 0o600)

    def test_plugin_se_cache_pendant_le_partage(self):
        lua = (REPO / "home/.local/share/noctalia/plugins/nc-garmin/garmin.luau").read_text()
        self.assertIn("/nc-partage-actif", lua)
        self.assertIn("noctalia.fileExists(PARTAGE)", lua)
        self.assertIn("SANS_RUN or", lua)  # sans XDG_RUNTIME_DIR : caché par prudence
        self.assertRegex(lua, r"enPartage")

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
    def lancer(self, corps, etat=DEMO, avec_fenetre=False):
        with tempfile.TemporaryDirectory(prefix="nc-garmin-") as d:
            composants = ("Couleurs",)
            fichiers = {}
            entete = H.ENTETE
            if avec_fenetre:
                composants += ("Texte", "Ico", "BoutonReglages") + tuple(
                    Path(n).stem for n in fichiers_garmin() if n != "Garmin.qml")
                # Comme pour le VPN, Window remplace la FloatingWindow (Wayland) hors écran.
                panneau = lire("Garmin.qml").replace("FloatingWindow {", "Window {", 1)
                panneau = re.sub(r"(?m)^    (implicitWidth|implicitHeight|minimumSize|onClosed|onVisibleChanged):.*\n", "", panneau)
                fichiers["Garmin.qml"] = "import QtQuick.Window\n" + panneau
                entete += "import QtTest\n"
            root = H.preparer(d, composants, extra={
                **fichiers, "GarminEtat.qml": lire("GarminEtat.qml"),
                "Partage.qml": "pragma Singleton\nimport QtQuick\nQtObject { property bool silence: false }\n"},
                singletons=("GarminEtat", "Partage"))
            (root / "etat.json").write_text(json.dumps(etat))
            bin_ = root / "home/.local/bin"
            bin_.mkdir(parents=True)
            (bin_ / "nc-garmin").write_text(FAUX.replace("@ROOT@", str(root)))
            (bin_ / "nc-garmin").chmod(0o755)
            if avec_fenetre:
                reglages = bin_ / "nc-reglages"
                reglages.write_text(f"""#!/bin/sh\nprintf 'REGLAGES %s\\n' "$*" >> "{root}/journal"\n""")
                reglages.chmod(0o755)
            (root / "shell.qml").write_text(entete + "ShellRoot {\n property int etape: 0\n property int ticks: 0\n" + H.OUTILS
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

    def test_en_tete_et_actions_du_panneau(self):
        etat = dict(DEMO, widgets_actifs=["body_battery", "hydratation"])
        journal = self.lancer('''
            property bool fermee: false
            Garmin { id: fen; visible: true; width: 900; height: 780; onFermer: fermee = true }
            TestCase { id: t; name: "Garmin"; when: false }
            function chercher(suffixe) { return trouver(fen.contentItem, "nc-garmin-" + suffixe) }
            Timer { interval: 60; running: true; repeat: true; onTriggered: {
                if (!GarminEtat.lu) return
                if (etape === 0) {
                    var titre = chercher("titre"), perso = chercher("perso"), actualiser = chercher("actualiser")
                    var reglages = chercher("reglages"), fermer = chercher("fermer")
                    verifier(titre.text === "Santé Garmin" && chercher("sous-titre").text.indexOf("Données de démonstration") !== -1, "mode démo annoncé")
                    verifier(perso.parent === fermer.parent && perso.x < actualiser.x && actualiser.x < reglages.x && reglages.x < fermer.x, "quatre boutons ordonnés dans l’en-tête")
                    t.mouseClick(perso)
                    etape++; return
                }
                if (etape === 1) {
                    verifier(chercher("tiroir").visible, "Personnaliser ouvre le tiroir")
                    t.mouseClick(chercher("coche-body_battery"))
                    t.mouseClick(chercher("perso"))
                    verifier(!chercher("tiroir").visible, "Personnaliser referme le tiroir")
                    etape++; return
                }
                if (etape === 2) {
                    if (GarminEtat.occupe) return
                    t.mouseClick(chercher("actualiser"))
                    etape++; return
                }
                if (etape === 3) {
                    if (!GarminEtat.occupe) return
                    verifier(!chercher("actualiser").enabled && chercher("actualiser").texte === "Synchro…", "actualisation en cours")
                    t.mouseClick(chercher("eau-250"))
                    t.mouseClick(chercher("eau-500"))
                    t.mouseClick(chercher("reglages"))
                    etape++; return
                }
                if (GarminEtat.occupe) return
                t.mouseClick(chercher("fermer"))
                verifier(fermee, "Fermer émet le signal de fermeture")
                console.log("FINI"); Qt.exit(0)
            } }
        ''', etat=etat, avec_fenetre=True)
        self.assertIn("REGLAGES fenetre Santé Garmin", journal)
        debut = [l.split()[1:-1] for l in journal.splitlines() if l.startswith("DEBUT")]
        self.assertEqual(debut, [["sync"], ["widgets", "basculer", "body_battery"], ["sync", "--force"],
                                 ["hydratation", "+250"], ["hydratation", "+500"]])

    def test_en_tete_sync_et_masquage(self):
        self.lancer('''
            Garmin { id: fen; visible: true; width: 420; height: 520 }
            Timer { interval: 60; running: true; repeat: true; onTriggered: {
                if (!GarminEtat.lu || ++ticks < 5) return
                var titre = trouver(fen.contentItem, "nc-garmin-sous-titre")
                var perso = trouver(fen.contentItem, "nc-garmin-perso")
                var fermer = trouver(fen.contentItem, "nc-garmin-fermer")
                var contenu = trouver(fen.contentItem, "nc-garmin-contenu")
                verifier(titre.text.indexOf("Garmin Connect · Synchro ") === 0, "heure de synchronisation dans l’en-tête")
                verifier(perso.mapToItem(contenu, 0, 0).x >= 0 && fermer.mapToItem(contenu, fermer.width, 0).x <= contenu.width,
                         "contrôles contenus dans la largeur minimale")
                Partage.silence = true
                verifier(titre.text.indexOf("Indicateurs masqués") === 0 && titre.text.indexOf("Synchro") === -1, "statut de confidentialité sans horodatage")
                console.log("FINI"); Qt.exit(0)
            } }
        ''', etat=dict(DEMO, demo=False, connecte=True, maj=1761000000), avec_fenetre=True)



def textwrap_corps(corps):
    import textwrap
    return textwrap.dedent(corps)


if __name__ == "__main__":
    unittest.main()

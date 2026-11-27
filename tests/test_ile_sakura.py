"""Sakura : choix persistant, vues contextuelles utilisables et thème voisin intact."""
from pathlib import Path
import runpy
import shutil
import subprocess
import tempfile
import unittest

from tests import _ile_hors_ecran as H
from tests.test_refonte_ile_controle_reglages import ECHECS_QML

CLE = "ILE_SAKURA_VARIANTE"
CLI = H.REPO / "home/.local/bin/nc-reglages"


class ReglageSakura(unittest.TestCase):
    def test_catalogue_et_persistance_a_travers_les_themes(self):
        with tempfile.TemporaryDirectory(prefix="nc-sakura-reglages-") as dossier:
            root = Path(dossier)
            home = root / "home"
            conf = home / ".config/nc"
            conf.mkdir(parents=True)
            # Le catalogue ne propose les réglages de l’île que si le composant est installé.
            (home / ".config/quickshell").mkdir()
            (home / ".config/quickshell/nc-ile").symlink_to(H.QML)
            runtime = root / "run"
            runtime.mkdir(mode=0o700)
            env = dict(HOME=str(home), PATH="/usr/bin:/bin", XDG_CONFIG_HOME=str(home / ".config"),
                       XDG_CACHE_HOME=str(root / "cache"), XDG_STATE_HOME=str(root / "state"),
                       XDG_DATA_HOME=str(root / "data"), XDG_RUNTIME_DIR=str(runtime), NC_LANGUE="fr")

            def cli(*args):
                r = subprocess.run([str(CLI), *args], env=env, text=True, capture_output=True, timeout=5)
                self.assertEqual(r.returncode, 0, r.stderr)
                return r.stdout

            style = conf / "style.conf"
            style.write_text("STYLE=sakura\n")
            self.assertIn(CLE, cli("liste"))
            self.assertEqual(cli("get", CLE).strip(), "petale")
            cli("set", CLE, "bourgeons")
            style.write_text("STYLE=dracula\n")
            self.assertNotIn(CLE, cli("liste"))
            style.write_text("STYLE=sakura\n")
            self.assertIn("Deux bourgeons", cli("liste"))
            self.assertEqual(cli("get", CLE).strip(), "bourgeons")


@unittest.skipUnless(shutil.which("qs"), "Quickshell requis")
class SakuraHorsEcran(unittest.TestCase):
    def test_les_boutons_contextuels_et_le_noyau_sakura(self):
        outil = runpy.run_path(str(H.REPO / "outils/rendu-ile.py"))
        with tempfile.TemporaryDirectory(prefix="nc-sakura-") as d:
            root = Path(d)
            reglages = root / "reglages.conf"
            reglages.write_text("STYLE=sakura\nILE_ANIM=doux\nILE_RESUME_REVEIL=non\n")
            qml = outil["preparer"](root, "lecteur", reglages, None)
            journal_catalogue = instrumenter_catalogue(root)
            f = qml / "test_sakura.qml"
            f.write_text(H.ENTETE + 'import QtTest\nShellRoot {' + H.OUTILS + SCENARIO, encoding="utf-8")
            env = outil["environnement"](root, root / "unused.png")
            env["XDG_CONFIG_HOME"] = str(root / "home/.config")
            r = subprocess.run(["qs", "--no-color", "-p", str(f)], env=env, text=True,
                               capture_output=True, timeout=10)
            journal = r.stdout + r.stderr
            self.assertEqual(r.returncode, 0, journal)
            for erreur in (*ECHECS_QML, "Unable to assign"):
                self.assertNotIn(erreur, journal)
            self.assertIn("SAKURA_OK", journal)
            self.assertEqual(journal_catalogue.read_text().splitlines(), ["catalogue --fenetre"])


def instrumenter_catalogue(root):
    cli = root / "home/.local/bin/nc-reglages"
    cli.unlink()
    cli.write_text('''#!/bin/sh
[ "$1" = catalogue ] || exit 0
[ "$2" != --fenetre ] || printf '%s\\n' "$*" >> "$HOME/lectures"
cat <<'EOF'
[{"cle":"ILE_SAKURA_VARIANTE","section":"Île","sectionNom":"Île","nom":"Variante Sakura","genre":"choix","defaut":"petale","valeur":"petale","choix":[["petale","Pétale"]],"aide":"Carte","affiche":"Pétale","modifie":false}]
EOF
''', encoding="utf-8")
    cli.chmod(0o755)
    return root / "home/lectures"


SCENARIO = r'''
    id: test
    readonly property var variantes: ["petale", "ticket", "bourgeons"]
    property int indice: 0
    property int etape: 0
    property real centreRepos: 0
    property real centreCarte: 0
    property bool carteEnRepli: false
    Connections {
        target: Etat
        function onPageSysChanged() {
            if (fen.ouverte && Couleurs.themeActif === "sakura")
                verifier(!Etat.pageSys, "passage par une vue système pendant l’ouverture de Sakura")
        }
    }
    TestCase { id: clic; when: false }
    Ile { id: fen; visible: true; modelData: ({ name: "sakura", width: 800, height: 680 }) }
    Parametres { id: preferences; ileOuverte: fen.ouverte }
    Component.onCompleted: { preferences.afficher("sakura"); preferences.allerSection("ile") }
    function element(nom) { return trouver(fen.contentItem, nom) }
    function cliquer(nom) {
        const bouton = element(nom)
        if (!verifier(bouton && bouton.visible && bouton.enabled, "bouton inaccessible : " + nom)) return false
        clic.mouseClick(bouton, bouton.width / 2, bouton.height / 2)
        return true
    }
    function centre(item) { return item.mapToItem(fen.cible, item.width / 2, 0).x }
    Timer {
        interval: 75; running: true; repeat: true
        onTriggered: {
            const s = test.element("nc-sakura")
            if (test.etape === 0) {
                if (!s || !Reglages.valeurs.ILE_ANIM || !Etat.aMusique || !Notifs.pret) return
                if (preferences.enCours || preferences.section !== "ile" || !preferences.reglage("ILE_SAKURA_VARIANTE")) return
                Notifs.revenues = [
                    { id: "sakura-a", appName: "Agenda", summary: "Réunion dans 10 min", actions: [], synthetique: true },
                    { id: "sakura-b", appName: "Fichiers", summary: "Synchronisation terminée", actions: [], synthetique: true }
                ]
                Etat.meteo = { temp: 14, icone: "cloud" }
                test.etape++
            } else if (test.etape === 1) {
                if (!s || !test.element("nc-sakura-ouvrir-notifications")?.visible) return
                const variante = test.variantes[test.indice]
                if (!verifier(s.variante === variante && s.height === 30, "mauvais choix au repos : " + variante)) return
                if (!verifier(test.element("nc-sakura-meteo").text === "14°", "météo perdue avec la musique")) return
                if (!verifier(test.element("nc-sakura-ouvrir-musique").visible, "titre de musique absent")) return
                if (variante === "bourgeons") test.centreRepos = test.centre(s.zonePrincipale)
                if (test.cliquer("nc-sakura-ouvrir-notifications")) test.etape++
            } else if (test.etape === 2) {
                const liste = test.element("nc-sakura-notifs-liste")
                if (!liste?.visible || !(s.height > 100)) return
                if (!verifier(Etat.vueActive === "notifications" && liste.count === 2, "notifications réelles absentes")) return
                if (!verifier(!Etat.controleOuvert && !test.element("nc-notifs-tout-effacer")?.visible,
                              "l’ancien panneau est encore affiché")) return
                if (s.variante === "bourgeons" && !verifier(s.zoneCarte.y > s.zonePrincipale.height
                    && Math.abs(test.centre(s.zonePrincipale) - test.centreRepos) < .5, "le noyau bouge à l’ouverture")) return
                if (test.indice === 0) {
                    if (!test.cliquer("nc-sakura-notifs-tout-lire")
                        || !verifier(Notifs.nonLues === 0 && Notifs.liste.length === 2, "marquer comme lues a retiré les entrées")
                        || !test.cliquer("nc-sakura-notif-retirer-sakura-a")
                        || !verifier(Notifs.liste.length === 1 && Notifs.liste[0].id === "sakura-b",
                                     "retrait individuel : " + Notifs.liste.map(n => n.id).join(", "))
                        || !test.cliquer("nc-sakura-notifs-tout-effacer")
                        || !verifier(Notifs.liste.length === 0, "effacer n’a pas vidé les notifications")) return
                }
                if (test.cliquer("nc-sakura-ouvrir-musique")) test.etape++
            } else if (test.etape === 3) {
                const titre = test.element("nc-sakura-musique-titre")
                if (!titre?.visible) return
                const art = test.element("nc-sakura-musique-pochette")
                const pause = test.element("nc-sakura-transport-lecture")
                if (!verifier(Etat.vueActive === "musique" && titre.text === Etat.titre && pause?.enabled,
                              "lecteur ou commandes manquants")) return
                const decalage = pause.mapToItem(art, 0, 0).y
                if (!verifier(s.variante === "petale" ? decalage > art.height : decalage < art.height,
                              "composition du lecteur incorrecte : " + s.variante)) return
                if (s.variante === "bourgeons") test.centreCarte = test.centre(s.zoneCarte)
                if (test.cliquer("nc-sakura-ouvrir-musique")) test.etape++
            } else if (test.etape === 4) {
                if (s.variante === "bourgeons" && !fen.ouverte) {
                    const carte = test.element("nc-sakura-carte-satellite")
                    if (!verifier(!s.zoneCarte && Math.abs(test.centre(s.zonePrincipale) - test.centreRepos) < .5,
                                  "le noyau bouge ou la carte capte encore des clics au repli")) return
                    if (carte.visible) {
                        test.carteEnRepli = true
                        if (!verifier(carte.opacity < 1 && Math.abs(test.centre(carte) - test.centreCarte) < 1,
                                      "la carte satellite saute pendant le repli")) return
                    }
                    if (s.height === 30 && !verifier(test.carteEnRepli && !carte.visible,
                                                    "pas de transition de sortie pour la carte satellite")) return
                }
                if (fen.ouverte || s.height !== 30) return
                test.indice++
                if (test.indice < test.variantes.length) {
                    Reglages.valeurs = Object.assign({}, Reglages.valeurs, { ILE_SAKURA_VARIANTE: test.variantes[test.indice] })
                    Notifs.revenues = [
                        { id: "sakura-a", appName: "Agenda", summary: "Réunion dans 10 min", actions: [], synthetique: true },
                        { id: "sakura-b", appName: "Fichiers", summary: "Synchronisation terminée", actions: [], synthetique: true }
                    ]
                    test.etape = 1
                } else {
                    Reglages.style = { STYLE: "dracula" }
                    Etat.basculer("sakura", false)
                    Etat.aller("notifications")
                    test.etape++
                }
            } else if (test.etape === 5) {
                if (!test.element("nc-notifs-tout-effacer")?.visible) return
                if (!verifier(!s && Couleurs.themeActif === "dracula", "une variante Sakura a fui vers Dracula")) return
                Etat.fermer()
                Reglages.style = { STYLE: "sakura" }
                test.etape++
            } else if (test.etape === 6 && s) {
                if (!verifier(s.variante === "bourgeons", "choix Sakura perdu après Dracula")) return
                if (!verifier(preferences.visible && preferences.section === "ile", "les Réglages ont perdu la rubrique Île")) return
                console.warn("SAKURA_OK")
                Qt.quit()
            }
        }
    }
    Timer { interval: 5500; running: true; onTriggered: verifier(false, "Sakura bloquée à l’étape " + test.indice + "/" + test.etape) }
}
'''

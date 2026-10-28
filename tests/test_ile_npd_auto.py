"""Ne pas déranger automatique en jeu et en projection (Partage.qml, Projecteur.qml, Notifs.qml, PageNotifs.qml, réglage NPD_AUTO).

- Source : même retenue que le partage d'écran (Partage.retient lu par Notifs.montrer), détection de la projection par les
  événements de Hyprland (aucun minuteur qui se répète), réglage et README.
- Hors écran, avec le vrai qs lancé par « qs -p » (jamais l'île réelle), faux hyprctl qui note ses arguments :
  mode jeu et projection retiennent les bulles, un seul groupe à la fin (nombre exact, une notification remplacée compte une
  fois), silence du partage inchangé (« silence » reste réservé au partage), partage fini pendant le jeu : groupe à la fin du
  jeu seulement, réglage coupé (rien retenu, aucun groupe), écran éteint (aucun hyprctl).
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
        self.partage = (QML / "Partage.qml").read_text()
        self.proj = (QML / "Projecteur.qml").read_text()
        self.code = re.sub(r"//.*", "", self.proj)
        self.notifs = (QML / "Notifs.qml").read_text()

    def test_notifs_consulte_retient(self):
        self.assertIn("if (Partage.retient) { Partage.retenir(notif); return }", self.notifs)
        self.assertIn("function onRetientChanged()", self.notifs)
        self.assertIn("function onTermineAuto(nombre, raison)", self.notifs)
        self.assertIn("readonly property bool retient: silence || auto", self.partage)

    def test_projecteur_par_evenements(self):
        self.assertIn('hyprctl", "monitors", "all", "-j"', self.proj)
        self.assertRegex(self.proj, r"monitoradded.*monitorremoved.*configreloaded")
        self.assertNotRegex(self.code, r"repeat: true|running: true")
        self.assertIn("Etat.ecranVu", self.proj)
        self.assertEqual(len(re.findall(r"(?m)^\s*component ", self.proj)), 0)

    def test_reglage_et_readme(self):
        with tempfile.TemporaryDirectory() as d, patch.dict(os.environ, HOME=d), warnings.catch_warnings():
            warnings.simplefilter("ignore", ResourceWarning)
            cles = runpy.run_path(str(REPO / "home/.local/bin/nc-reglages"))["PAR_CLE"]
        self.assertEqual(cles["NPD_AUTO"].defaut, "oui")
        self.assertEqual(cles["NPD_AUTO"].valider("non"), "non")
        self.assertIn("`NPD_AUTO`", (REPO / "README.md").read_text())


@unittest.skipUnless(shutil.which("qs"), "Quickshell requis")
class HorsEcran(unittest.TestCase):
    def lancer(self, corps, hyprctl=None):
        with tempfile.TemporaryDirectory(prefix="nc-npd-") as d:
            root = H.preparer(d, ("Partage", "Projecteur"), singletons=("Partage", "Projecteur"))
            H.faux(root, "hyprctl", "cat '%s/moniteurs.json'" % root)
            (root / "moniteurs.json").write_text(hyprctl or "[]")
            (root / "shell.qml").write_text(H.ENTETE + textwrap.dedent('''\
                ShellRoot {
                    property var groupes: []
                    Connections { target: Partage; function onTermineAuto(n, raison) { groupes = groupes.concat([n + ":" + raison]) } }
                    property var fins: []
                    Connections { target: Partage; function onTermine(n) { fins = fins.concat([n]) } }
                ''') + H.OUTILS + textwrap.dedent(corps) + "\n}\n")
            code, sortie = H.lancer(root)
            for e in H.ERREURS:
                self.assertNotIn(e, sortie, sortie)
            self.assertIn("FINI", sortie, sortie)
            return H.journal(root)

    def test_jeu_retient_et_un_seul_groupe(self):
        self.lancer('''
            Timer { interval: 200; running: true; onTriggered: {
                verifier(!Partage.retient && !Partage.auto, "rien au repos")
                Etat.jeu = true
                verifier(Partage.retient && Partage.jeuAuto && !Partage.silence, "jeu : bulles retenues, silence intact")
                Partage.retenir({ id: 1 }); Partage.retenir({ id: 2 }); Partage.retenir({ id: 2 }); Partage.retenir({ id: 3 })
                verifier(Partage.compte === 3, "3 notifications (la remplacée compte une fois) : " + Partage.compte)
                Etat.jeu = false
                verifier(!Partage.retient, "jeu fini : bulles de retour")
                verifier(groupes.length === 1 && groupes[0] === "3:jeu", "un seul groupe : " + JSON.stringify(groupes))
                verifier(Partage.compte === 0, "compteur remis à zéro")
                verifier(Partage.texteFinAuto(3, "jeu") === "3 notifications reçues pendant le jeu", Partage.texteFinAuto(3, "jeu"))
                verifier(Partage.texteFinAuto(1, "projection") === "1 notification reçue pendant la projection", "texte singulier")
                // Rien reçu : pas de groupe
                Etat.jeu = true; Etat.jeu = false
                verifier(groupes.length === 1, "aucun groupe sans notification")
                console.log("FINI"); Qt.exit(0)
            } }
        ''')

    def test_projection_et_jeu_ensemble_un_groupe(self):
        self.lancer('''
            Timer { interval: 200; running: true; onTriggered: {
                Projecteur.analyser(JSON.stringify([{ name: "eDP-1", disabled: false, mirrorOf: "none" }, { name: "HDMI-A-1", disabled: false, mirrorOf: "eDP-1" }]))
                verifier(Projecteur.actif && Projecteur.mode === "miroir" && Partage.projAuto && Partage.retient, "miroir : retenu")
                Partage.retenir({ id: "a" })
                Etat.jeu = true
                Partage.retenir({ id: "b" })
                Etat.jeu = false
                verifier(Partage.retient && groupes.length === 0, "projection toujours là : pas de groupe")
                Projecteur.analyser("[]")
                verifier(!Partage.retient && groupes.length === 1 && groupes[0] === "2:jeu", "un groupe à la toute fin : " + JSON.stringify(groupes))
                console.log("FINI"); Qt.exit(0)
            } }
        ''')

    def test_partage_pendant_le_jeu(self):
        self.lancer('''
            Timer { interval: 200; running: true; onTriggered: {
                Etat.jeu = true
                Partage.debut(); Partage.retenir({ id: 1 })
                verifier(Partage.silence && Partage.retient, "partage + jeu")
                Partage.indicateur = true
                Partage.terminer()
                verifier(!Partage.silence && Partage.retient, "partage fini, jeu en cours : toujours retenu")
                verifier(fins.length === 0 && groupes.length === 0, "ni message de partage ni groupe encore")
                Partage.retenir({ id: 2 })
                Etat.jeu = false
                verifier(groupes.length === 1 && groupes[0] === "2:jeu", "groupe unique à la fin du jeu : " + JSON.stringify(groupes))
                // Le partage seul garde son comportement
                Partage.debut(); Partage.retenir({ id: 3 }); Partage.indicateur = true; Partage.terminer()
                verifier(fins.length === 1 && fins[0] === 1 && groupes.length === 1, "partage seul : son propre message")
                console.log("FINI"); Qt.exit(0)
            } }
        ''')

    def test_reglage_coupe(self):
        self.lancer('''
            Timer { interval: 200; running: true; onTriggered: {
                Reglages.valeurs = { NPD_AUTO: "non" }
                Etat.jeu = true
                verifier(!Partage.retient && !Partage.auto, "réglage non : rien retenu en jeu")
                Projecteur.analyser(JSON.stringify([{ name: "eDP-1", disabled: false, mirrorOf: "none" }, { name: "HDMI-A-1", disabled: false, mirrorOf: "eDP-1" }]))
                verifier(!Partage.retient, "réglage non : rien retenu en projection")
                Etat.jeu = false
                verifier(groupes.length === 0, "aucun groupe")
                // Coupé en plein jeu : tout s'arrête sans message
                Reglages.valeurs = ({})
                Projecteur.analyser("[]")
                Etat.jeu = true
                Partage.retenir({ id: 1 })
                Reglages.valeurs = { NPD_AUTO: "non" }
                verifier(!Partage.retient && groupes.length === 0, "coupé en plein jeu : sans message : " + JSON.stringify(groupes))
                console.log("FINI"); Qt.exit(0)
            } }
        ''')

    def test_detection_des_moniteurs(self):
        self.lancer('''
            Timer { interval: 200; running: true; onTriggered: {
                function mode(l) { Projecteur.analyser(typeof l === "string" ? l : JSON.stringify(l)); return Projecteur.mode }
                var portable = { name: "eDP-1", disabled: false, mirrorOf: "none" }
                verifier(mode([portable]) === "", "seul : rien")
                verifier(mode([portable, { name: "HDMI-A-1", disabled: false, mirrorOf: "none" }]) === "", "étendre : rien")
                verifier(mode([portable, { name: "HDMI-A-1", disabled: false, mirrorOf: "eDP-1" }]) === "miroir", "dupliquer")
                verifier(mode([{ name: "eDP-1", disabled: true, mirrorOf: "none" }, { name: "HDMI-A-1", disabled: false, mirrorOf: "none" }]) === "externe", "second écran seulement")
                verifier(mode([{ name: "DP-1", disabled: false, mirrorOf: "none" }]) === "", "PC de bureau : rien")
                verifier(mode([{ name: "eDP-1", disabled: true, mirrorOf: "none" }]) === "", "tout éteint : rien")
                verifier(mode([portable, { name: "HEADLESS-2", disabled: false, mirrorOf: "eDP-1" }]) === "", "écran virtuel : rien")
                verifier(mode("pas du json") === "" && !Projecteur.actif, "réponse illisible : rien")
                verifier(mode("{}") === "", "objet : rien")
                console.log("FINI"); Qt.exit(0)
            } }
        ''')

    def test_lecture_sur_evenement_et_ecran_eteint(self):
        json = '[{"name":"eDP-1","disabled":false,"mirrorOf":"none"},{"name":"HDMI-A-1","disabled":false,"mirrorOf":"eDP-1"}]'
        j = self.lancer('''
            property int etape: 0
            Timer { interval: 300; running: true; repeat: true; onTriggered: {
                if (etape === 0) { verifier(Projecteur.actif, "lu au démarrage : miroir"); Etat.ecranVu = false; Projecteur.analyser("[]"); etape++; return }
                if (etape === 1) { Projecteur.lire(); etape++; return }
                if (etape === 2) { verifier(!Projecteur.actif, "écran éteint : aucune relecture"); Etat.ecranVu = true; etape++; return }
                if (etape === 3) { verifier(Projecteur.actif, "écran rallumé : relu"); console.log("FINI"); Qt.exit(0) }
            } }
        ''', hyprctl=json)
        self.assertEqual(j.count("hyprctl monitors all -j"), 2, j)           # démarrage et réveil, rien écran éteint


if __name__ == "__main__":
    unittest.main()

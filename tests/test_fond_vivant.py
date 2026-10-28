"""Fond d'écran vivant (Fond.qml, Lueurs.qml, Gouttes.qml, Lueur.qml ; nc-reglages FOND_ANIME=vivant ; nc-pouls).

- Énergie : le compteur du fond s'arrête (0 image calculée) écran éteint ou verrouillé, fenêtre ouverte (plein écran
  compris), en jeu, en Économie et sur batterie par défaut ; cadence bornée (15 images/s) ; le fichier du pouls n'est
  surveillé que fond actif et musique en cours.
- Chargement hors écran (qs -p, QT_QPA_PLATFORM=offscreen) de Lueurs.qml puis de Fond.qml (PanelWindow remplacé par une
  fenêtre ordinaire, Hyprland et UPower retirés), sans erreur : teintes selon l'heure, gouttes selon la météo, pouls
  lu dans le fichier, arrêt complet écran éteint et en jeu.
- Réglage : FOND_ANIME accepte vivant, reste « non » par défaut ; « aussi sur batterie » non par défaut.
- nc-pouls : avec FOND_ANIME=vivant, le niveau des basses est écrit dans XDG_RUNTIME_DIR/nc-pouls-niveau (retiré à
  l'arrêt) ; sans le réglage, aucun fichier.
Tout se passe dans des dossiers temporaires (HOME, XDG_RUNTIME_DIR, XDG_CONFIG_HOME…) : rien ne touche la vraie session."""
import os
from pathlib import Path
import re
import runpy
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest
import warnings

from tests.test_pouls import CAVA_OK, Cadre, attend

REPO = Path(__file__).resolve().parents[1]
QML = REPO / "home/.config/quickshell/nc-ile"
BIN = REPO / "home/.local/bin"


def lire(nom):
    return (QML / nom).read_text(encoding="utf-8")


COULEURS = ('pragma Singleton\nimport QtQuick\nQtObject { readonly property color texte: "#ffffff"; readonly property color texteSec: "#98989d"\n'
            ' readonly property color accent: "#0a84ff"; readonly property color bleu: "#0a84ff"; readonly property color violet: "#5e5ce6"\n'
            ' readonly property color rose: "#ff375f"; readonly property color orange: "#ff9f0a" }\n')


class FondVivantSource(unittest.TestCase):
    def test_le_fond_ne_calcule_rien_ecran_eteint_en_jeu_fenetre_ouverte_ou_sur_batterie(self):
        fond = lire("Fond.qml")
        self.assertRegex(fond, r"anime:\s*Etat\.ecranVu\s*&&\s*bureauVide\s*&&\s*batterieOk\s*&&\s*!economie\s*&&\s*!Etat\.jeu")
        # Une fenêtre sur le bureau affiché (plein écran compris) : le fond est caché, donc en pause
        self.assertRegex(fond, r"bureauVide:[^\n]*\n[^\n]*toplevels\.values\.length === 0")
        # Sur batterie : seulement avec le réglage
        self.assertRegex(fond, r'batterieOk:\s*!UPower\.onBattery\s*\|\|\s*Reglages\.val\("FOND_ANIME_BATTERIE",\s*"non"\)\s*===\s*"oui"')
        # Le seul compteur ne tourne que fond actif, à 15 images par seconde au plus (jamais la fréquence de l'écran)
        m = re.search(r"interval:\s*(\d+);\s*repeat:\s*true;\s*running:\s*f\.anime\n", fond)
        self.assertIsNotNone(m, "compteur du fond")
        self.assertGreaterEqual(int(m.group(1)), 50)
        # L'heure n'est relue que fond actif ; le fichier du pouls n'est surveillé que fond vivant, actif et musique en cours
        self.assertRegex(fond, r"interval:\s*60000;\s*repeat:\s*true;\s*running:\s*f\.anime\s*&&\s*f\.vivant")
        self.assertRegex(fond, r"surveille:\s*vivant\s*&&\s*anime\s*&&\s*Etat\.joue"); self.assertRegex(fond, r"watchChanges:\s*f\.surveille")
        self.assertIn("nc-pouls-niveau", fond)
        # Le pouls n'est lissé qu'au tic du compteur : aucune animation (Behavior) sur lui ni sur t
        self.assertNotRegex(fond, r"Behavior on (t|pouls|niveau)\b")
        self.assertNotRegex(lire("Lueurs.qml"), r"Behavior on (t|pouls|heure)\b")

    def test_par_dessus_le_fond_sous_les_fenetres_sans_souris(self):
        fond = lire("Fond.qml")
        self.assertIn("WlrLayershell.layer: WlrLayer.Bottom", fond)
        self.assertIn("exclusionMode: ExclusionMode.Ignore", fond)
        self.assertRegex(fond, r"mask:\s*Region\s*\{\s*\}")
        self.assertIn('color: "transparent"', fond)

    def test_nouveaux_composants_dans_leurs_fichiers_sans_component_inline_ajoute(self):
        for nom in ("Lueurs.qml", "Lueur.qml", "Gouttes.qml"):
            self.assertTrue((QML / nom).is_file(), nom)
        for nom in ("Fond.qml", "Lueurs.qml", "Lueur.qml", "Gouttes.qml"):
            self.assertNotRegex(lire(nom), r"^\s*component\s+\w+\s*:", nom)

    def test_shell_cree_le_fond_pour_aurore_et_vivant(self):
        shell = lire("shell.qml")
        self.assertRegex(shell, r'\["aurore", "vivant"\]\.indexOf\(Reglages\.val\("FOND_ANIME", "non"\)\) >= 0 && !Reglages\.sobre')
        self.assertRegex(shell, r'Fond \{ vivant: Reglages\.val\("FOND_ANIME", "non"\) === "vivant" \}')

    def test_meteo_de_l_ile_reutilisee_et_couleurs_de_la_palette(self):
        self.assertRegex(lire("Fond.qml"), r"meteoCode:\s*vivant && Etat\.meteo\.code !== undefined \? Etat\.meteo\.code : -1")
        lueurs = lire("Lueurs.qml")
        for c in ("Couleurs.accent", "Couleurs.violet", "Couleurs.bleu", "Couleurs.rose", "Couleurs.orange", "Couleurs.texteSec"):
            self.assertIn(c, lueurs)
        self.assertNotRegex(lueurs, r'"#[0-9a-fA-F]{6}"', "pas de couleur en dur : la palette de l'île")
        self.assertIn("Couleurs.texte", lire("Gouttes.qml"))

    def test_reglage_vivant_accepte_et_coupe_par_defaut(self):
        with tempfile.TemporaryDirectory() as d:
            from unittest.mock import patch
            with patch.dict(os.environ, HOME=d), warnings.catch_warnings():
                warnings.simplefilter("ignore", ResourceWarning)
                reglages = runpy.run_path(str(BIN / "nc-reglages"))
            r = reglages["PAR_CLE"]["FOND_ANIME"]
            self.assertEqual(r.defaut, "non")
            self.assertEqual(r.valider("vivant"), "vivant")
            self.assertEqual(r.valider("aurore"), "aurore")
            self.assertEqual([v for v, _ in r.choix()], ["non", "aurore", "vivant"])
            with self.assertRaises(ValueError):
                r.valider("disco")
            self.assertEqual(reglages["PAR_CLE"]["FOND_ANIME_BATTERIE"].defaut, "non")

    def test_readme_et_aide_du_reglage(self):
        self.assertIn("**Fond vivant**", (REPO / "README.md").read_text(encoding="utf-8"))
        self.assertIn("Vivant", (BIN / "nc-reglages").read_text(encoding="utf-8"))


@unittest.skipUnless(shutil.which("qs"), "Quickshell requis")
class FondVivantHorsEcran(unittest.TestCase):
    def executer(self, fichiers, shell, etat="", delai=10):
        with tempfile.TemporaryDirectory(prefix="nc-fond-") as d:
            root = Path(d); q = root / "qml"; q.mkdir(); (root / "runtime").mkdir(mode=0o700)
            for nom in ("Lueurs.qml", "Lueur.qml", "Gouttes.qml"):
                shutil.copy2(QML / nom, q / nom)
            for nom, texte in fichiers.items():
                (q / nom).write_text(texte)
            (q / "Couleurs.qml").write_text(COULEURS)
            (q / "Reglages.qml").write_text('pragma Singleton\nimport QtQuick\nQtObject { function val(k, d) { return d } }\n')
            (q / "Etat.qml").write_text('pragma Singleton\nimport QtQuick\nQtObject { property bool ecranVu: true; property bool jeu: false; property bool joue: true\n'
                                        ' property var meteo: ({ code: 63 }); property string dossierSession: "' + str(root / "runtime") + '"\n' + etat + ' }\n')
            noms = ["Couleurs", "Reglages", "Etat", "Lueurs", "Lueur", "Gouttes"] + [n[:-4] for n in fichiers]
            (q / "qmldir").write_text("\n".join(("singleton " if n in ("Couleurs", "Reglages", "Etat") else "") + n + " 1.0 " + n + ".qml" for n in noms))
            (q / "shell.qml").write_text('''import QtQuick
import QtQuick.Window
import Quickshell
ShellRoot {
 id: racine
 property int etape: 0
 property real t0: 0
 property int attente: 0
 property var fond: null
 function verifier(ok, m) { if (!ok) { console.error("ECHEC " + m); Qt.exit(2) } }
 function trouver(item, cle) { var e = item.children || []
   for (var i = 0; i < e.length; i++) { if (e[i][cle] !== undefined) return e[i]; var r = trouver(e[i], cle); if (r) return r } return null }
 Timer { interval: 200; running: true; repeat: true; onTriggered: {
  SCENARIO
 } }
 Timer { interval: 9000; running: true; onTriggered: { console.error("ECHEC délai"); Qt.exit(3) } }
}
'''.replace("SCENARIO", shell))
            env = dict(os.environ, HOME=d, QT_QPA_PLATFORM="offscreen", QT_QUICK_BACKEND="software", XDG_RUNTIME_DIR=str(root / "runtime"),
                       XDG_CACHE_HOME=str(root / "cache"), XDG_CONFIG_HOME=str(root / "config"), XDG_STATE_HOME=str(root / "state"),
                       XDG_DATA_HOME=str(root / "data"), TMPDIR=str(root))
            env.pop("WAYLAND_DISPLAY", None)
            (root / "runtime" / "nc-pouls-niveau").write_text("0.90\n")
            r = subprocess.run(["qs", "--no-color", "-p", str(q / "shell.qml")], env=env, text=True, capture_output=True, timeout=delai + 20)
            out = r.stdout + r.stderr
            self.assertEqual(r.returncode, 0, out)
            for erreur in ("ECHEC", "ReferenceError", "TypeError", "Cannot assign", "Binding loop", "is not a type", "Unable to assign"):
                self.assertNotIn(erreur, out)
            return out

    def test_lueurs_teintes_de_l_heure_et_gouttes_de_la_meteo(self):
        self.executer({"Scene.qml": '''import QtQuick
import QtQuick.Window
Window { visible: true; width: 640; height: 400; Lueurs { id: l; anchors.fill: parent; vivant: true; heure: 12; meteoCode: 63 }
         property alias lueurs: l }
'''}, '''
  if (etape === 0) { var c = Qt.createComponent("Scene.qml"); verifier(c.status === Component.Ready, c.errorString()); fond = c.createObject(racine); etape++; return }
  var l = fond.lueurs, g = trouver(l, "nombre"), rep = trouver(g, "count")
  if (etape === 1) {
    verifier(l.pluie && !l.neige && !l.brouillard, "pluie attendue pour le code 63")
    verifier(g.nombre === 18 && rep.count === 18, "18 gouttes attendues : " + g.nombre + " / " + rep.count)
    var jour = l.teintes[0].toString()
    l.heure = 3; verifier(l.teintes[0].toString() !== jour, "la nuit a sa teinte"); verifier(l.nuit === 1 && l.force < 1, "nuit discrète")
    l.heure = 6; verifier(l.nuit > 0 && l.nuit < 1, "aube fondue : " + l.nuit)
    l.heure = 19.5; var crepuscule = l.teintes[0].toString(); verifier(crepuscule !== jour, "le crépuscule a sa teinte")
    l.meteoCode = 45; verifier(l.brouillard && !l.pluie, "brouillard"); verifier(l.teintes[0].toString() !== crepuscule, "voile gris du brouillard")
    l.meteoCode = 73; verifier(l.neige && g.nombre === 28, "28 flocons attendus"); l.t = 3; l.pouls = 1
    etape++; return }
  if (etape === 2) {
    verifier(rep.count === 28, "flocons créés")
    l.vivant = false; verifier(!l.pluie && !l.neige && g.nombre === 0 && l.force === 1, "aurore simple : ni météo ni nuit")
    l.heure = 12; l.meteoCode = -1; l.vivant = true; verifier(g.nombre === 0, "sans météo, pas de goutte")
    Qt.quit() }
''')

    def test_fond_pulse_sur_le_fichier_du_pouls_et_s_arrete_ecran_eteint_ou_en_jeu(self):
        source = lire("Fond.qml")
        # Hors Hyprland : une fenêtre ordinaire à la place du calque Wayland, sans moniteur ni batterie
        remplacements = [("import Quickshell.Wayland\n", "import QtQuick.Window\n"), ("import Quickshell.Hyprland\n", ""),
                         ("import Quickshell.Services.UPower\n", ""), ("PanelWindow {", "Window {"),
                         ("    required property var modelData\n", "    property var modelData: null\n"), ("    screen: modelData\n", ""),
                         ("    anchors { top: true; bottom: true; left: true; right: true }\n", ""), ("    exclusionMode: ExclusionMode.Ignore\n", ""),
                         ("    WlrLayershell.layer: WlrLayer.Bottom\n", ""), ('    WlrLayershell.namespace: "nc-fond"\n', ""),
                         ("readonly property var moniteur: Hyprland.monitorFor(modelData)", "readonly property var moniteur: null"),
                         ("PowerProfiles.profile === PowerProfile.PowerSaver", "false"), ("!UPower.onBattery ||", "true ||"),
                         ('    color: "transparent"\n', '    color: "transparent"; width: 640; height: 400; visible: true\n')]
        for avant, apres in remplacements:
            self.assertIn(avant, source); source = source.replace(avant, apres)
        source = re.sub(r"    mask: Region \{\}[^\n]*\n", "", source)
        self.executer({"Fond.qml": source}, '''
  if (etape === 0) { var c = Qt.createComponent("Fond.qml"); verifier(c.status === Component.Ready, c.errorString())
                     fond = c.createObject(racine, { vivant: true }); etape++; return }
  var l = trouver(fond.contentItem, "meteoCode"), g = trouver(l, "nombre")
  if (etape === 1) {                       // écran vu, bureau vide, musique : le fond tourne et pulse sur le fichier
    verifier(fond.anime, "fond actif"); verifier(fond.t > 0.1, "le compteur tourne : " + fond.t)
    verifier(fond.pouls > 0.5, "pouls lu dans nc-pouls-niveau : " + fond.pouls)
    verifier(l.pluie && g.nombre === 18 && g.visible, "la pluie de l'île tombe")
    verifier(fond.heure >= 0 && fond.heure < 24, "heure relue")
    Etat.ecranVu = false; racine.t0 = fond.t; etape++; return }
  if (etape === 2) {                       // écran éteint : plus rien ne bouge, le fichier n'est plus surveillé, pouls à zéro
    verifier(!fond.anime && fond.t === racine.t0, "compteur arrêté écran éteint : " + fond.t + " / " + racine.t0)
    if (++racine.attente < 6) return       // le fondu des gouttes dure 800 ms
    verifier(!g.visible, "gouttes cachées en pause")
    Etat.ecranVu = true; Etat.jeu = true; etape++; return }
  if (etape === 3) {
    verifier(!fond.anime && fond.t === racine.t0, "compteur arrêté en jeu")
    Etat.jeu = false; Etat.joue = false; etape++; return }
  if (etape === 4) {                       // musique arrêtée : le fond tourne mais le pouls retombe sans surveiller le fichier
    verifier(fond.anime && fond.t > racine.t0, "reprise")
    if (++racine.attente < 12) return      // la retombée douce (x 0,8 par tic) prend une seconde
    verifier(fond.niveau === 0 && fond.pouls < 0.1, "pouls retombé sans musique : " + fond.pouls + " niveau " + fond.niveau)
    Qt.quit() }
''', etat="")


# Garde-fou contre un blocage seulement : nc-pouls s'arrête en 0,02 s après SIGTERM (mesuré 5 fois) ; 5 s avaient été dépassées
# une fois sous la charge de plusieurs suites lancées ensemble. Ce que le test vérifie (code 0, fichier retiré) ne change pas.
DELAI_ARRET = 30


class PoulsEtFondVivant(unittest.TestCase):
    def cadre(self, vivant):
        c = Cadre(CAVA_OK)
        self.addCleanup(c.ferme)
        conf = Path(c.env["HOME"]) / ".config/nc"
        conf.mkdir(parents=True)
        (conf / "reglages.conf").write_text("FOND_ANIME=vivant\n" if vivant else "FOND_ANIME=aurore\n")
        p = c.lance()
        self.addCleanup(lambda: p.poll() is None and p.kill())
        return c, p

    def test_niveau_ecrit_pour_le_fond_vivant_et_retire_a_l_arret(self):
        c, p = self.cadre(True)
        f = c.run / "nc-pouls-niveau"
        self.assertTrue(attend(lambda: f.exists() and f.read_text().strip() not in ("", "0.00"), 8), c.cmds)
        self.assertRegex(f.read_text(), r"^[01]\.\d\d\n$")
        self.assertTrue(any(x != "eval nc.halo(0.00)" for x in c.cmds), "le halo d'Hyprland reste alimenté")
        p.send_signal(signal.SIGTERM)
        self.assertEqual(p.wait(timeout=DELAI_ARRET), 0)
        self.assertFalse(f.exists(), "fichier retiré à l'arrêt")

    def test_sans_le_reglage_aucun_fichier(self):
        c, p = self.cadre(False)
        self.assertTrue(attend(lambda: any(x != "eval nc.halo(0.00)" for x in c.cmds), 8), c.cmds)
        time.sleep(1)
        self.assertFalse((c.run / "nc-pouls-niveau").exists())
        p.send_signal(signal.SIGTERM)
        p.wait(timeout=DELAI_ARRET)


if __name__ == "__main__":
    sys.exit(unittest.main())

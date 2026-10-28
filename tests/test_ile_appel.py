"""Appel en cours dans l'île (Appel.qml, AppelSource.qml, NiveauMicro.qml, PageAppel.qml, Compact.qml, réglage ILE_APPEL).

- Source : détection par les flux PipeWire (Etat.fluxMicro), aucun processus ni sondage, rien d'écrit sur le disque, le
  niveau du micro mesuré seulement pendant qu'il s'affiche (écran vu, hors Économie, micro actif), sourdine sur la source
  liée au flux sinon la source par défaut, les noms venus de PipeWire jamais dans une commande, mode de la pilule,
  réglages de nc-reglages, README.
- Hors écran, avec le vrai qs : le vrai Appel.qml et la vraie page PageAppel.qml reçoivent de faux flux (un faux Etat,
  sans PipeWire : AppelSource.qml et NiveauMicro.qml sont remplacés par des doublures). Cas : débounce (2,5 s, raccourci),
  nom et fin d'appel (« Appel terminé »), appel commencé micro coupé (« Micro coupé »), niveau mesuré seulement pilule ou
  page visible, écran vu et hors Économie, réglage ILE_APPEL=non, dictée et flux de Quickshell ignorés, page Appel.
HOME et XDG_RUNTIME_DIR isolés, jamais les vrais ; aucun vrai micro, aucun vrai PipeWire."""
import os
from pathlib import Path
import re
import runpy
import shutil
import subprocess
import tempfile
import textwrap
import unittest
import warnings

REPO = Path(__file__).resolve().parents[1]
QML = REPO / "home/.config/quickshell/nc-ile"


class Source(unittest.TestCase):
    def setUp(self):
        self.appel = (QML / "Appel.qml").read_text()
        self.code = re.sub(r"//.*", "", self.appel)
        self.source = re.sub(r"//.*", "", (QML / "AppelSource.qml").read_text())
        self.niveau = re.sub(r"//.*", "", (QML / "NiveauMicro.qml").read_text())
        self.page = re.sub(r"//.*", "", (QML / "PageAppel.qml").read_text())
        self.compact = (QML / "Compact.qml").read_text()
        self.etat = (QML / "Etat.qml").read_text()

    def test_evenements_seulement(self):
        # Les flux viennent d'Etat.fluxMicro (événements PipeWire de Quickshell) : ni processus, ni minuteur répété,
        # ni wpctl / pw-dump / pactl
        for code in (self.code, self.source, self.niveau, self.page):
            self.assertNotRegex(code, r"\bProcess\b|repeat: true|running: true|wpctl|pw-dump|pactl|execDetached|hyprctl")
        self.assertIn("Etat.fluxMicro.filter", self.code)
        self.assertIn("Timer { id: attente; interval: a.delai;", self.appel)
        self.assertIn("property int delai: 2500", self.appel)

    def test_niveau_seulement_quand_il_se_voit(self):
        # Le niveau du micro (PwNodePeakMonitor) : un fichier à part, chargé par son chemin, actif seulement pendant un
        # appel, micro actif, pilule ou page visible, écran vu, hors Économie
        self.assertIn('Loader { id: mesure; source: "NiveauMicro.qml"; active: a.niveauVoulu }', self.appel)
        self.assertIn("readonly property bool niveauVoulu: enCours && !muet && affiche && Etat.ecranVu && !Reglages.sobre", self.appel)
        self.assertIn("PwNodePeakMonitor", self.niveau)
        self.assertRegex(self.niveau, r"enabled: n\.actif && node !== null")
        self.assertIn("Pas {", self.niveau)
        self.assertIn("running: n.actif", self.niveau)
        # Seulement la crête (peak) : jamais le son
        self.assertNotRegex(self.niveau, r"pw-record|parec|arecord|FileView|writeFile")
        self.assertIn("crete.peak", self.niveau)

    def test_sourdine_sur_la_source_de_l_appel(self):
        # La source liée au flux (PwNodeLinkTracker), sinon la source par défaut ; le flux de l'appli n'est jamais suivi
        self.assertIn("PwNodeLinkTracker { id: liens; node: Appel.noeud }", self.source)
        self.assertIn("return Pipewire.defaultAudioSource", self.source)
        self.assertIn("PwObjectTracker { objects: s.source ? [s.source] : [] }", self.source)
        # Un flux relié au moniteur d'une sortie (OBS, partage avec le son) : la sortie n'est jamais « le micro »
        self.assertIn("if (g[i].source && !g[i].source.isStream && !g[i].source.isSink) return g[i].source", self.source)
        self.assertIn("function basculerMicro() { if (lien.item && lien.item.lie) lien.item.basculer(); else Etat.basculerMicro() }", self.appel)
        self.assertIn('(source.name || "").indexOf("bluez_input.") === 0', self.source)

    def test_noms_en_texte_brut_jamais_dans_une_commande(self):
        self.assertIn("textFormat: Text.PlainText", (QML / "Texte.qml").read_text())
        for code in (self.code, self.source, self.niveau, self.page, re.sub(r"//.*", "", self.compact)):
            self.assertNotRegex(code, r"execDetached|Process|hyprctl|sh\b.*-c")

    def test_rien_sur_le_disque(self):
        for code in (self.code, self.source, self.niveau, self.page):
            self.assertNotRegex(code, r"FileView|PersistentProperties|writeFile|Memo\.")

    def test_etat_et_pilule(self):
        self.assertIn('if (Appel.enCours) a.push("appel")', self.etat)
        # Etat.fluxMicro (point orange, « X utilise le micro ») n'écarte pas tout « quickshell » : Appel.qml écarte lui-même sa mesure
        self.assertNotIn("quickshell", re.sub(r"//.*", "", self.etat))
        self.assertIn("/quickshell|peak|", self.appel)
        self.assertIn('n.properties["node.passive"] === "true"', self.appel)
        self.assertIn(': Appel.enCours ? "appel"', self.compact)
        for mode in ('appel: appel', '"appel-muet": appelMuet', '"appel-fini": appelFini'):
            self.assertIn(mode, self.compact)
        # Priorité : après l'enregistrement, le partage et JARVIS, avant les téléchargements et la musique
        m = re.search(r"readonly property string mode: (.*?)\n    readonly property real largeur", self.compact, re.S)
        ordre = [m.group(1).index(x) for x in ('"video"', '"partage"', 'AssistantEtat.activitePilule !== ""', '"appel"', '"telechargement"', '"musique"')]
        self.assertEqual(ordre, sorted(ordre))
        self.assertIn('appel: adaptee("appel", 150)', (QML / "Ile.qml").read_text())
        self.assertIn('appel: ["Appel", "Call"]', (QML / "NavigationIle.qml").read_text())

    def test_pas_de_composant_neuf(self):
        for nom in ("Etat.qml", "Ile.qml", "NavigationIle.qml", "Appel.qml", "AppelSource.qml", "NiveauMicro.qml", "PageAppel.qml"):
            self.assertEqual(len(re.findall(r"(?m)^\s*component ", (QML / nom).read_text())), 0, nom)
        self.assertEqual(len(re.findall(r"(?m)^\s*component ", self.compact)), 1)      # Compact avait déjà son « Fondu »

    def test_reglages_et_readme(self):
        with tempfile.TemporaryDirectory() as d:
            from unittest.mock import patch
            with patch.dict(os.environ, HOME=d), warnings.catch_warnings():
                warnings.simplefilter("ignore", ResourceWarning)
                reglages = runpy.run_path(str(REPO / "home/.local/bin/nc-reglages"))
        cles = reglages["PAR_CLE"]
        self.assertEqual(cles["ILE_APPEL"].defaut, "oui")
        self.assertEqual(cles["ILE_APPEL"].section, "Île")
        self.assertEqual(cles["ILE_APPEL"].valider("non"), "non")
        self.assertEqual(cles["ILE_PAGE_APPEL"].section, "Pages de l’île")
        readme = (REPO / "README.md").read_text()
        self.assertIn("`ILE_APPEL`", readme)
        self.assertIn("jamais le son", readme)


STUB_ETAT = '''pragma Singleton
import QtQuick
QtObject {
    property var fluxMicro: []
    property date maintenant: new Date()
    property bool ecranVu: true
    property string ecranOuvert: ""
    property string activiteType: ""
    property bool enregistre: false
    property string vueActive: "centre"
    property bool microMuet: false
    property var hauteurs: ({})
    property var reactions: []
    property int basculesDefaut: 0
    // Doublures d'AppelSource.qml (sans PipeWire)
    property bool fauxMuet: false
    property bool fauxMono: false
    property int mesures: 0
    function activite(t, d) { reactions = reactions.concat([t]) }
    function basculerMicro() { basculesDefaut++ }
    function duree(s) { var m = Math.floor(s / 60), x = s % 60; return m + ":" + String(x).padStart(2, "0") }
    function nomJoli(n) { return n === "WEBRTC VoiceEngine" ? "Discord" : n }
    function annoncerHauteur(nom, h) { var t = Object.assign({}, hauteurs); t[nom] = Math.round(h); hauteurs = t }
}
'''
STUB_REGLAGES = '''pragma Singleton
import QtQuick
QtObject {
    property var valeurs: ({})
    property bool sobre: false
    readonly property bool en: false
    function val(k, d) { return valeurs[k] !== undefined ? valeurs[k] : d }
    function t(fr, en) { return fr }
}
'''
STUB_SOURCE = '''import QtQuick
Item {
    readonly property var source: ({ name: Etat.fauxMono ? "bluez_input.AA_BB" : "alsa_input.pci", description: "Micro" })
    readonly property bool lie: true
    readonly property bool muet: Etat.fauxMuet
    readonly property bool monoBt: Etat.fauxMono
    readonly property string nomSource: "Micro"
    function basculer() { Etat.fauxMuet = !Etat.fauxMuet }
}
'''
STUB_NIVEAU = '''import QtQuick
Item {
    property var source: null
    property bool actif: false
    readonly property real niveau: actif ? 0.5 : 0
    onActifChanged: if (actif) Etat.mesures++
}
'''
ENTETE = '''import QtQuick
import QtQuick.Window
import Quickshell
ShellRoot {
    id: racine
    property int etape: 0
    property int attente: 0
    function verifier(v, m) { if (!v) { console.error("ÉCHEC étape " + etape + " : " + m); Qt.exit(2) } }
    function trouver(item, nom) { if (item.objectName === nom) return item; for (var i = 0; i < item.children.length; i++) { var r = trouver(item.children[i], nom); if (r) return r } return null }
    function flux(nom) { return [{ name: nom, description: nom, type: 0 }] }
    Window {
        id: w; visible: true; width: 432; height: 300; color: "black"
        Item { id: cadre; x: 16; y: 16; width: 378; height: 268; Loader { id: page; anchors.fill: parent; source: "PageAppel.qml" } }
    }
    Timer { interval: 80; running: true; repeat: true; onTriggered: {
'''
PIED = '''
    } }
    Timer { interval: 12000; running: true; onTriggered: { console.error("délai dépassé à l'étape " + racine.etape); Qt.exit(9) } }
}
'''


@unittest.skipUnless(shutil.which("qs"), "Quickshell requis")
class Banc(unittest.TestCase):
    def executer(self, scenario):
        with tempfile.TemporaryDirectory(prefix="nc-appel-") as d:
            root = Path(d)
            (root / "run").mkdir(mode=0o700)
            for nom in ("Appel", "PageAppel", "Texte", "Ico", "Module", "Couleurs"):
                shutil.copy2(QML / (nom + ".qml"), root)
            (root / "Etat.qml").write_text(STUB_ETAT)
            (root / "Reglages.qml").write_text(STUB_REGLAGES)
            (root / "AppelSource.qml").write_text(STUB_SOURCE)
            (root / "NiveauMicro.qml").write_text(STUB_NIVEAU)
            (root / "Partage.qml").write_text("pragma Singleton\nimport QtQuick\nQtObject { property bool indicateur: false }")
            (root / "AssistantEtat.qml").write_text('pragma Singleton\nimport QtQuick\nQtObject { property string activitePilule: "" }')
            singletons = ("Appel", "Etat", "Reglages", "Couleurs", "Partage", "AssistantEtat")
            (root / "qmldir").write_text("\n".join(("singleton " if n in singletons else "") + n + " 1.0 " + n + ".qml"
                                                   for n in singletons + ("PageAppel", "Texte", "Ico", "Module", "AppelSource", "NiveauMicro")))
            (root / "shell.qml").write_text(ENTETE + textwrap.indent(textwrap.dedent(scenario), " " * 8) + PIED)
            env = dict(os.environ, HOME=d, XDG_RUNTIME_DIR=str(root / "run"), XDG_CACHE_HOME=str(root / "cache"),
                       QT_QPA_PLATFORM="offscreen", QT_QUICK_BACKEND="software")
            env.pop("WAYLAND_DISPLAY", None)
            r = subprocess.run(["qs", "--no-color", "-p", str(root / "shell.qml")], env=env, text=True, capture_output=True, timeout=30)
            out = r.stdout + r.stderr
            self.assertEqual(r.returncode, 0, out)
            for erreur in ("ReferenceError", "TypeError", "Cannot assign", "Binding loop", "is not a type", "Unable to assign"):
                self.assertNotIn(erreur, out)
            return out

    def test_appel_detecte_apres_le_delai_puis_termine(self):
        self.executer('''
            if (etape === 0) { Appel.delai = 300; verifier(!Appel.enCours, "appel sans flux"); Etat.fluxMicro = flux("WEBRTC VoiceEngine"); etape++ }
            else if (etape === 1) {
                verifier(Appel.presence && !Appel.enCours, "appel avant le délai")
                verifier(Appel.appli === "Discord", "nom de l'appli : " + Appel.appli)
                etape++
            } else if (etape === 2) {
                if (!Appel.enCours) { verifier(++attente < 12, "jamais en cours"); return }
                verifier(Etat.reactions.indexOf("appel-muet") < 0, "« micro coupé » alors que le micro est actif")
                verifier(Appel.derniereAppli === "Discord", "appli mémorisée")
                verifier(Appel.niveauVoulu && Appel.niveau > 0 && Etat.mesures === 1, "niveau non mesuré pilule visible")
                verifier(Appel.dureeTexte.indexOf(":") > 0, "durée : " + Appel.dureeTexte)
                // Page Appel : la ligne « micro coupé » cachée, le bouton « Couper le micro » là
                var p = page.item
                verifier(p && !trouver(p, "nc-appel-muet").visible && trouver(p, "nc-appel-micro").visible, "page Appel")
                verifier(Etat.hauteurs.appel > 60, "hauteur annoncée : " + Etat.hauteurs.appel)
                verifier(!trouver(p, "nc-appel-mono").visible, "rappel mono sans casque")
                Etat.fauxMono = true; etape++
            } else if (etape === 3) {
                verifier(Appel.monoBt && trouver(page.item, "nc-appel-mono").visible, "rappel « mode appel : son mono »")
                Etat.fluxMicro = []; etape++
            } else if (etape === 4) {
                verifier(!Appel.enCours, "appel toujours en cours sans flux")
                verifier(Etat.reactions.indexOf("appel-fini") >= 0, "pas de « Appel terminé »")
                verifier(Appel.derniereDuree >= 0 && Appel.niveau === 0, "fin : durée " + Appel.derniereDuree + ", niveau " + Appel.niveau)
                Qt.quit()
            }
        ''')

    def test_niveau_seulement_ecran_vu_pilule_ou_page_visible(self):
        self.executer('''
            if (etape === 0) { Appel.delai = 100; Etat.fluxMicro = flux("Firefox"); etape++ }
            else if (etape === 1) {
                if (!Appel.enCours) { verifier(++attente < 12, "jamais en cours"); return }
                verifier(Appel.niveauVoulu, "niveau voulu pilule visible")
                Etat.ecranVu = false; etape++
            } else if (etape === 2) {
                verifier(!Appel.niveauVoulu && Appel.niveau === 0, "niveau mesuré écran éteint")
                Etat.ecranVu = true; Reglages.sobre = true; etape++
            } else if (etape === 3) {
                verifier(!Appel.niveauVoulu, "niveau mesuré en Économie")
                Reglages.sobre = false; Etat.activiteType = "volume"; etape++
            } else if (etape === 4) {
                verifier(!Appel.niveauVoulu, "niveau mesuré pendant une autre réaction de la pilule")
                Etat.activiteType = ""; Etat.ecranOuvert = "E"; Etat.vueActive = "centre"; etape++
            } else if (etape === 5) {
                verifier(!Appel.niveauVoulu, "niveau mesuré île ouverte sur une autre page")
                Etat.vueActive = "appel"; etape++
            } else if (etape === 6) {
                verifier(Appel.niveauVoulu, "niveau non mesuré sur la page Appel")
                Etat.fauxMuet = true; etape++
            } else if (etape === 7) {
                verifier(Appel.muet && !Appel.niveauVoulu, "niveau mesuré micro coupé")
                verifier(trouver(page.item, "nc-appel-muet").visible, "ligne « micro coupé » absente de la page")
                Appel.basculerMicro(); etape++
            } else if (etape === 8) {
                verifier(!Appel.muet && Etat.basculesDefaut === 0, "sourdine : pas sur la source de l'appel")
                Qt.quit()
            }
        ''')

    def test_appel_commence_micro_coupe(self):
        self.executer('''
            if (etape === 0) { Appel.delai = 100; Etat.fauxMuet = true; Etat.microMuet = true; Etat.fluxMicro = flux("ZOOM VoiceEngine"); etape++ }
            else if (etape === 1) {
                if (!Appel.enCours) { verifier(++attente < 12, "jamais en cours"); return }
                verifier(Etat.reactions.indexOf("appel-muet") >= 0, "appel commencé micro coupé sans « Micro coupé »")
                verifier(Appel.muet && !Appel.niveauVoulu, "niveau mesuré micro coupé")
                Qt.quit()
            }
        ''')

    def test_reglage_non_dictee_traitements_et_flux_de_quickshell_ignores(self):
        self.executer('''
            function ignore(f, message) {        // un flux qui ne doit jamais faire un appel (6 tours de 80 ms, plus que le délai)
                if (attente === 0) Etat.fluxMicro = f
                if (++attente < 6) return false
                verifier(!Appel.enCours && !Appel.presence, message)
                attente = 0; etape++
                return true
            }
            if (etape === 0) { Appel.delai = 100; Reglages.valeurs = { ILE_APPEL: "non" }; Etat.fluxMicro = flux("Firefox"); attente = 0; etape++ }
            else if (etape === 1) {
                if (++attente < 6) return
                verifier(!Appel.enCours && Appel.flux.length === 0 && Appel.appli === "", "ILE_APPEL=non : appel détecté")
                Reglages.valeurs = {}; attente = 0; etape++
            }
            else if (etape === 2) ignore(flux("parec"), "la dictée (parec) prise pour un appel")
            else if (etape === 3) ignore(flux("quickshell"), "la mesure de niveau de l'île prise pour un appel")
            else if (etape === 4) ignore([{ name: "Chromium", description: "Chromium input", type: 0, properties: { "stream.monitor": "true" } }], "un flux « stream.monitor » pris pour un appel")
            else if (etape === 5) ignore([{ name: "Chromium", description: "Chromium input", type: 0, properties: { "node.passive": "true" } }], "un flux passif (boucle) pris pour un appel")
            else if (etape === 6) ignore(flux("easyeffects_soe"), "EasyEffects pris pour un appel")
            else if (etape === 7) ignore([{ name: "rnnoise_source", description: "RNNoise", type: 0 }], "rnnoise pris pour un appel")
            else if (etape === 8) ignore([{ name: "OBS", description: "OBS Studio", type: 0 }], "OBS pris pour un appel")
            else if (etape === 9) { Etat.fluxMicro = flux("Firefox"); attente = 0; etape++ }
            else if (etape === 10) {
                if (!Appel.enCours) { verifier(++attente < 12, "jamais en cours"); return }
                Reglages.valeurs = { ILE_APPEL: "non" }; etape++
            } else if (etape === 11) {
                verifier(!Appel.enCours, "réglage coupé en plein appel : l'activité reste")
                verifier(Etat.reactions.indexOf("appel-fini") < 0, "« Appel terminé » alors que le réglage est coupé")
                Qt.quit()
            }
        ''')


if __name__ == "__main__":
    unittest.main()

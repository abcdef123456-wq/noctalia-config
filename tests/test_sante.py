"""Santé du PC à l'écran : page Santé (Sante.qml, JaugeSante.qml), veille de surchauffe (Chaleur.qml),
nc-ile-etat capteurs | sante, réglage CHALEUR_ALERTE.
Faux /sys/class/hwmon (NC_HWMON_DIR) et faux /sys (NC_SYSFS) : jamais la vraie machine ; faux nvidia-smi qui note
seulement son appel (une carte endormie ne doit jamais le voir) ; faux notify-send qui note ses arguments.
Machine générique : k10temp ou coretemp, nvme, spd5118, un Wi-Fi, deux ventilateurs (yogafan + lenovo_wmi_other)."""
import os
from pathlib import Path
import runpy
import shutil
import subprocess
import tempfile
import textwrap
import unittest
from unittest.mock import patch
import warnings

from tests.test_conso_pourquoi import ENTETE_QML, OUTILS_QML, lancer_qs

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "home/.local/bin/nc-ile-etat"
QML = REPO / "home/.config/quickshell/nc-ile"


def faux(dossier, nom, corps):
    f = dossier / nom
    f.write_text("#!/bin/sh\n" + corps)
    f.chmod(0o755)
    return f


class Script(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="nc-sante-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.bin = self.tmp / "bin"
        self.bin.mkdir()
        (self.tmp / "home").mkdir()
        self.hw = self.tmp / "hwmon"
        self.sys = self.tmp / "sys"
        (self.sys / "class/dmi/id").mkdir(parents=True)
        (self.sys / "firmware/acpi").mkdir(parents=True)
        faux(self.bin, "busctl", "exit 1\n")
        faux(self.bin, "nvidia-smi", f'echo "nvidia-smi $*" >> "{self.tmp}/journal"\necho 71\n')

    def capteur(self, i, nom, temp=None, crit=None, fans=()):
        d = self.hw / f"hwmon{i}"
        d.mkdir(parents=True)
        (d / "name").write_text(nom + "\n")
        if temp is not None:
            (d / "temp1_input").write_text(f"{temp}\n")
        if crit is not None:
            (d / "temp1_crit").write_text(f"{crit}\n")
        for n, (rpm, maxi) in enumerate(fans, 1):
            (d / f"fan{n}_input").write_text(f"{rpm}\n")
            if maxi:
                (d / f"fan{n}_max").write_text(f"{maxi}\n")

    def machine(self):
        self.capteur(0, "acpitz", 16800)
        self.capteur(1, "nvme", 35000, 84850)
        self.capteur(2, "k10temp", 87375)
        self.capteur(3, "yogafan", fans=((0, None), (0, None)))
        self.capteur(4, "lenovo_wmi_other", fans=((3600, 5100), (2900, 5100)))
        self.capteur(5, "spd5118", 41000, 85000)
        self.capteur(6, "spd5118", 43000, 85000)
        self.capteur(7, "mt7921_phy0", 61000)
        (self.sys / "class/dmi/id/sys_vendor").write_text("LENOVO\n")
        (self.sys / "firmware/acpi/platform_profile").write_text("balanced\n")

    def lancer(self, *args):
        env = dict(os.environ, HOME=str(self.tmp / "home"), PATH=f"{self.bin}:{os.environ['PATH']}",
                   NC_HWMON_DIR=str(self.hw), NC_SYSFS=str(self.sys))
        r = subprocess.run(["bash", str(SCRIPT), *args], env=env, capture_output=True, text=True, timeout=30)
        return r.stdout

    @staticmethod
    def lignes(sortie, cle):
        return [l.split("=", 1)[1].split("\t") for l in sortie.splitlines() if l.startswith(cle + "=")]

    def test_capteurs_trouves(self):
        self.machine()
        c = dict(l.split("=", 1) for l in self.lancer("capteurs").splitlines())
        self.assertEqual(c["cpu"], str(self.hw / "hwmon2/temp1_input"))      # k10temp avant acpitz (issue #33)
        self.assertEqual(c["capteurs"], "1")
        self.assertEqual(c["fabricant"], "LENOVO")

    def test_sante_lit_tout(self):
        self.machine()
        s = self.lancer("sante")
        temps = {t[0]: t[1:] for t in self.lignes(s, "temp")}
        self.assertEqual(temps["cpu"], ["87", ""])
        self.assertEqual(temps["ssd"], ["35", "84"])
        self.assertEqual(temps["ram"], ["43", "85"])                           # la barrette la plus chaude, une ligne
        self.assertEqual(temps["wifi"], ["61", ""])
        self.assertEqual(temps["carte"], ["16", ""])                           # acpitz, à part du processeur
        self.assertNotIn("gpu", temps)
        # yogafan (sans maximum, et à 0 ici) écarté quand lenovo_wmi_other lit les mêmes ventilateurs
        self.assertEqual(self.lignes(s, "fan"), [["1", "3600", "5100"], ["2", "2900", "5100"]])
        self.assertEqual(self.lignes(s, "profil_firmware"), [["balanced"]])
        self.assertTrue(self.lignes(s, "cpu"))
        self.assertFalse((self.tmp / "journal").exists(), "nvidia-smi appelé sans carte NVIDIA")

    def test_coretemp_et_acpitz_seul(self):
        self.capteur(0, "coretemp", 52000, 100000)
        temps = {t[0]: t[1:] for t in self.lignes(self.lancer("sante"), "temp")}
        self.assertEqual(temps, {"cpu": ["52", "100"]})
        self.assertNotIn("cpu_fiable", self.lancer("capteurs"))
        shutil.rmtree(self.hw)
        self.capteur(0, "acpitz", 40000)
        temps = {t[0]: t[1:] for t in self.lignes(self.lancer("sante"), "temp")}
        self.assertEqual(temps, {"cpu": ["40", ""]})                           # repli : pas de ligne « carte » en double
        # Repli acpitz : la page le montre, la veille de surchauffe ne s'y fie pas (valeur parfois fictive, issue #33)
        self.assertIn("cpu_fiable=0", self.lancer("capteurs").splitlines())

    def test_valeurs_aberrantes_ignorees(self):
        # 0, 255000, 128000, -1 ou du texte : capteur muet ou cassé, jamais une mesure (et jamais un calcul cassé)
        self.capteur(0, "coretemp", 61000, 999999)
        self.capteur(1, "nvme", 0)
        self.capteur(2, "spd5118", "abc")
        self.capteur(3, "mt7921_phy0", 128000)
        self.capteur(4, "acpitz", -1)
        self.capteur(6, "yogafan", fans=(("abc", None), (2000, "x")))
        s = self.lancer("sante")
        temps = {t[0]: t[1:] for t in self.lignes(s, "temp")}
        self.assertEqual(temps, {"cpu": ["61", ""]})                           # coretemp valide, son maximum absurde écarté
        self.assertEqual(self.lignes(s, "fan"), [["1", "2000", ""]])
        shutil.rmtree(self.hw)                                                 # k10temp à 255 °C : pas de température nulle part
        self.capteur(0, "k10temp", 255000)
        self.assertNotIn("temperature=", self.lancer("systeme"))
        self.assertNotIn("cpu_temp=", self.lancer("jeu"))

    def test_sans_capteur_rien(self):
        # Tour sans capteur ou machine virtuelle : ni cpu= ni capteurs= (pas de page, pas de veille), rien dans sante
        self.hw.mkdir()
        c = self.lancer("capteurs")
        self.assertNotIn("cpu=", c)
        self.assertNotIn("capteurs=", c)
        s = self.lancer("sante")
        self.assertEqual([l for l in s.splitlines() if l.startswith(("temp=", "fan=", "gpu="))], [])

    def test_nvidia_endormie_jamais_reveillee(self):
        self.machine()
        carte = self.sys / "bus/pci/drivers/nvidia/0000:01:00.0/power"
        carte.mkdir(parents=True)
        (carte / "runtime_status").write_text("suspended\n")
        s = self.lancer("sante")
        self.assertIn("gpu=veille", s.splitlines())
        self.assertFalse((self.tmp / "journal").exists(), "nvidia-smi appelé sur une carte endormie")
        # « resuming », « suspending », vide : pas « active », donc pas de nvidia-smi non plus
        (carte / "runtime_status").write_text("resuming\n")
        self.assertIn("gpu=veille", self.lancer("sante").splitlines())
        self.assertFalse((self.tmp / "journal").exists(), "nvidia-smi appelé sur une carte qui n'est pas « active »")
        (carte / "runtime_status").write_text("active\n")
        s = self.lancer("sante")
        self.assertEqual({t[0]: t[1:] for t in self.lignes(s, "temp")}["gpu"], ["71", ""])
        self.assertIn("temperature.gpu", (self.tmp / "journal").read_text())

    def test_amdgpu_endormie_pas_lue(self):
        self.machine()
        self.capteur(8, "amdgpu", 64000, 100000)
        etat = self.hw / "hwmon8/device/power"
        etat.mkdir(parents=True)
        (etat / "runtime_status").write_text("suspended\n")
        s = self.lancer("sante")
        self.assertIn("gpu=veille", s.splitlines())
        self.assertNotIn("gpu", {t[0] for t in self.lignes(s, "temp")})
        (etat / "runtime_status").write_text("active\n")
        s = self.lancer("sante")
        self.assertEqual({t[0]: t[1:] for t in self.lignes(s, "temp")}["gpu"], ["64", "100"])
        self.assertNotIn("gpu=veille", s.splitlines())

    def test_programme_avec_tabulation_ecarte(self):
        # Un programme dont le nom contient une tabulation casserait la ligne top=<nom>\t<%> : il est écarté
        sh = shutil.which("sh")
        self.assertTrue(sh)
        copie = self.tmp / "x\ty"
        shutil.copy2(sh, copie)
        p = subprocess.Popen([str(copie), "-c", "while :; do :; done"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.addCleanup(p.wait)
        self.addCleanup(p.kill)                 # par son pid, c'est nous qui l'avons lancé
        self.hw.mkdir()
        for _ in range(3):
            tops = self.lignes(self.lancer("sante"), "top")
            for t in tops:
                self.assertEqual(len(t), 2, t)
                self.assertNotIn(t[0], ("x", "x\ty", "y"), t)

    def test_peu_de_processus(self):
        # Lecture directe des fichiers du noyau (read), pas un cat par capteur toutes les 2 s
        src = SCRIPT.read_text()
        bloc = src[src.index("\ntemperature_cpu() {"):src.index("\nsysteme() {")]
        self.assertNotIn("$(cat", bloc)
        self.assertNotIn("| head", bloc.replace("nvidia-smi --query-gpu=temperature.gpu --format=csv,noheader,nounits 2>/dev/null | head -1", ""))

    def test_lecture_seule(self):
        # Rien n'écrit dans /sys, pas de sudo : on lit, on explique ; le profil passe par le service de profils
        src = SCRIPT.read_text()
        bloc = src[src.index("\ncapteurs() {"):src.index("\n# Noms anglais")]
        for interdit in ("sudo", "tee ", "> /sys", ">/sys", "pwm", "fan_mode", "platform_profile\"\n"):
            self.assertNotIn(interdit, bloc)
        for nom in ("Chaleur.qml", "Sante.qml", "JaugeSante.qml"):
            q = (QML / nom).read_text()
            self.assertNotIn("sudo", q)
            self.assertNotIn("/sys/class/hwmon/hwmon", q, nom + " : capteur en dur")
            self.assertNotIn("nvidia-smi", q)


class Reglage(unittest.TestCase):
    def test_chaleur_alerte_et_page(self):
        with tempfile.TemporaryDirectory() as d:
            with patch.dict(os.environ, HOME=d), warnings.catch_warnings():
                warnings.simplefilter("ignore", ResourceWarning)
                settings = runpy.run_path(str(REPO / "home/.local/bin/nc-reglages"))
        r = settings["PAR_CLE"]["CHALEUR_ALERTE"]
        self.assertEqual((r.section, r.defaut, r.genre, r.unite), ("Île", "95", "entier", "°C"))
        self.assertEqual(r.valider("0"), "0")
        self.assertEqual(r.valider("100"), "100")
        with self.assertRaises(ValueError):
            r.valider("200")
        self.assertEqual(settings["MATERIEL"]["CHALEUR_ALERTE"], "ile")
        self.assertEqual(settings["MATERIEL"]["ILE_PAGE_SANTE"], "ile")
        self.assertEqual(settings["PAR_CLE"]["ILE_PAGE_SANTE"].defaut, "oui")
        self.assertNotIn("CHALEUR_ALERTE", settings["DISTANT_PERMIS"])


class Source(unittest.TestCase):
    def test_veille_arretee_ecran_eteint_et_sans_capteur(self):
        ch = (QML / "Chaleur.qml").read_text()
        self.assertIn('readonly property bool veille: fichierCpu !== "" && seuil > 0 && Etat.ecranVu', ch)
        self.assertIn("running: ch.veille", ch)
        self.assertIn("blockLoading: true", ch)                 # lecture directe du fichier du noyau, aucun processus
        sa = (QML / "Sante.qml").read_text()
        self.assertIn("running: sa.affichee && Etat.ecranVu", sa)
        courbe = (QML / "Courbe.qml").read_text()
        self.assertNotIn("Animation.Infinite", sa + (QML / "JaugeSante.qml").read_text() + courbe)
        # Historique et conseil : alimentés par le relevé existant (aucun Timer ni Process de plus), rien écrit sur le disque
        self.assertNotIn("Timer", courbe)
        self.assertNotIn("Process", courbe)
        self.assertEqual(sa.count("Timer {"), 2)            # attente + relevé, comme avant
        self.assertEqual(sa.count("Process {"), 1)
        for interdit in ("FileView", "writeText", "localStorage", "Settings"):
            self.assertNotIn(interdit, sa + courbe)

    def test_pas_de_composant_neuf(self):
        import re
        for nom in ("Etat.qml", "Compact.qml", "Ile.qml", "Sante.qml", "Chaleur.qml", "JaugeSante.qml", "Courbe.qml"):
            self.assertEqual(len(re.findall(r"(?m)^\s*component ", (QML / nom).read_text())), 1 if nom == "Compact.qml" else 0, nom)

    def test_page_apres_systeme_seulement_avec_capteurs(self):
        etat = (QML / "Etat.qml").read_text()
        self.assertIn('["son", "reseau", "bluetooth", "systeme"], capteursSante ? ["sante"] : [], ["calendrier"]', etat)
        self.assertIn('sante: pSante', (QML / "Ile.qml").read_text())
        # Bouton et pastilles Performance seulement si le service de profils le propose (Quickshell 0.3 : hasPerformanceProfile)
        self.assertIn("readonly property bool performanceDisponible: PowerProfiles.hasPerformanceProfile", etat)
        self.assertIn('objectName: "blocProfil"\n                visible: Etat.performanceDisponible', (QML / "Sante.qml").read_text())
        self.assertIn("Etat.performanceDisponible && Etat.profil !== PowerProfile.Performance", (QML / "Chaleur.qml").read_text())
        self.assertIn('sante: ["Santé", "Health"]', (QML / "NavigationIle.qml").read_text())
        self.assertIn("Chaleur.demarrer()", (QML / "shell.qml").read_text())


def bouchons(root, d, etat_extra=""):
    (root / "run").mkdir(mode=0o700)
    (root / "bin").mkdir()
    (root / "Reglages.qml").write_text('pragma Singleton\nimport QtQuick\nQtObject {readonly property bool en: false; readonly property bool sobre: true; '
                                       'property var valeurs: ({}); function t(fr,en){return fr} function val(k,d){return valeurs[k] !== undefined ? valeurs[k] : d}}')
    (root / "Partage.qml").write_text('pragma Singleton\nimport QtQuick\nQtObject { property bool silence: false }')
    (root / "Etat.qml").write_text('pragma Singleton\nimport QtQuick\nQtObject { readonly property string bin: "%s/bin/"\n'
                                   '  property bool ecranVu: true; property bool capteursSante: false; property int profil: 1; property bool performanceDisponible: true\n'
                                   '  property int activites: 0; property string derniereActivite: ""; property int profilChoisi: -1\n'
                                   '  property var hauteurs: ({})\n'
                                   '  function activite(t, d) { activites++; derniereActivite = t }\n'
                                   '  function choisirProfil(p) { profilChoisi = p }\n'
                                   '  function annoncerHauteur(nom, h) { var t = Object.assign({}, hauteurs); t[nom] = Math.round(h); hauteurs = t }\n%s }' % (d, etat_extra))


@unittest.skipUnless(shutil.which("qs"), "Quickshell requis")
class Veille(unittest.TestCase):
    """Chaleur.qml chargé hors écran avec le vrai qs : capteur trouvé par nc-ile-etat capteurs (faux), lectures espacées,
    un pic court ne déclenche rien, au-delà du seuil soutenu une seule activité et une seule notification (avec le
    programme gourmand et le bouton Performance, qui passe par Etat.choisirProfil), silence ensuite, retour à la normale
    10 °C sous le seuil, et plus aucune lecture écran éteint."""

    QMLDIR = "singleton Chaleur 1.0 Chaleur.qml\nsingleton Reglages 1.0 Reglages.qml\nsingleton Etat 1.0 Etat.qml\nsingleton Partage 1.0 Partage.qml\n"

    def test_veille(self):
        with tempfile.TemporaryDirectory(prefix="nc-chaleur-") as d:
            root = Path(d)
            bouchons(root, d)
            shutil.copy2(QML / "Chaleur.qml", root)
            (root / "qmldir").write_text(self.QMLDIR)
            temp = root / "temp1_input"
            temp.write_text("50000\n")
            faux(root / "bin", "nc-ile-etat", textwrap.dedent(f'''\
                echo "nc-ile-etat $*" >> "{root}/appels"
                case "$1" in
                  capteurs) echo "cpu={temp}"; echo "capteurs=1"; echo "fabricant=LENOVO" ;;
                  sante) sleep 0.2; printf 'cpu=12\\ntop=firefox\\t42\\n' ;;
                esac
                '''))
            faux(root / "bin", "notify-send", f'printf "%s\\n" "$*" >> "{root}/notifs"\necho perf\n')
            def ecrire(v):
                return f'Quickshell.execDetached(["sh", "-c", "echo {v} > \\"$1\\"", "sh", "{temp}"])'
            (root / "shell.qml").write_text(ENTETE_QML + "import Quickshell.Services.UPower\n" + textwrap.dedent('''\
                ShellRoot {
                    id: racine
                    property int etape: 0
                    property real marque: 0
                    function verifier(ok, message) { if (!ok) { console.error(message); Qt.exit(2) } return ok }
                    function attendre(ms) { if (marque === 0) marque = Date.now(); if (Date.now() - marque < ms) return true; marque = 0; return false }
                    Timer { interval: 50; running: true; repeat: true; onTriggered: {
                        if (etape === 0) { Chaleur.intervalle = 100; Chaleur.duree = 450; Chaleur.demarrer(); etape++ }
                        else if (etape === 1) {
                            if (Chaleur.fichierCpu === "" || Chaleur.derniereLecture === 0) return
                            verifier(Etat.capteursSante, "capteurs non annoncés à Etat")
                            verifier(Chaleur.lenovo, "fabricant non lu")
                            verifier(Chaleur.temperature === 50, "température : " + Chaleur.temperature)
                            verifier(Chaleur.seuil === 95, "seuil par défaut : " + Chaleur.seuil)
                            etape++ }
                        else if (etape === 2) { %(aberrant)s; etape++ }
                        else if (etape === 3) { if (attendre(250)) return
                            verifier(Chaleur.temperature === 50 && Chaleur.chaudDepuis === 0, "255000 m°C pris pour une mesure : " + Chaleur.temperature)
                            %(chaud)s; etape++ }
                        else if (etape === 4) { if (attendre(250)) return; verifier(Chaleur.temperature === 98 && Chaleur.chaudDepuis > 0, "pic non vu"); %(tiede)s; etape = 5 }
                        else if (etape === 5) { if (attendre(400)) return
                            verifier(!Chaleur.alerte && Etat.activites === 0, "un pic court a déclenché l'alerte")
                            verifier(Chaleur.chaudDepuis === 0, "série non remise à zéro après le pic")
                            %(chaud)s; marque = Date.now(); etape++ }
                        else if (etape === 6) {
                            if (!Chaleur.alerte) { verifier(Date.now() - marque < 3000, "pas d'alerte au-delà du seuil soutenu"); return }
                            verifier(Date.now() - marque >= 400, "alerte trop tôt : " + (Date.now() - marque) + " ms")
                            verifier(Etat.activites === 1 && Etat.derniereActivite === "chaleur", "activité de la pilule : " + Etat.activites)
                            marque = 0; etape++ }
                        else if (etape === 7) { if (attendre(1200)) return
                            verifier(Chaleur.alerte && Etat.activites === 1, "alerte répétée pendant l'épisode")
                            verifier(Chaleur.programme === "firefox" && Chaleur.programmePct === 42, "programme gourmand : " + Chaleur.programme)
                            verifier(Etat.profilChoisi === PowerProfile.Performance, "le bouton Performance n'a pas changé le profil")
                            verifier(Chaleur.situation().indexOf("firefox") >= 0 && Chaleur.gestes().indexOf("Fn + Q") >= 0, "texte : " + Chaleur.situation())
                            Partage.silence = true
                            verifier(Chaleur.situation().indexOf("firefox") < 0 && Chaleur.situation().indexOf("minute") >= 0, "partage d'écran : programme encore nommé : " + Chaleur.situation())
                            Partage.silence = false
                            Etat.performanceDisponible = false
                            verifier(!Chaleur.performancePossible, "bouton Performance sans service de profils")
                            Etat.performanceDisponible = true
                            %(tiede)s; etape++ }
                        else if (etape === 8) { if (attendre(300)) return
                            verifier(!Chaleur.alerte, "alerte encore levée à 80 °C")
                            Etat.ecranVu = false; %(chaud)s; etape++ }
                        else if (etape === 9) { if (attendre(500)) return
                            verifier(Chaleur.temperature === 80 && !Chaleur.alerte, "lecture écran éteint : " + Chaleur.temperature)
                            Qt.quit() }
                    } }
                    Timer { interval: 12000; running: true; onTriggered: Qt.exit(9) }
                }
                ''') % {"chaud": ecrire(98000), "tiede": ecrire(80000), "aberrant": ecrire(255000)})
            # Le faux notify-send de ce test devant celui du garde-fou (il répond « perf », le bouton de la notification)
            with patch.dict(os.environ, PATH=f"{root / 'bin'}:{os.environ['PATH']}"):
                r, sortie = lancer_qs(root, d, delai=25)
            self.assertEqual(r.returncode, 0, sortie)
            # Une ligne par appel (le texte de la notification a lui-même des retours à la ligne)
            notifs = [l for l in (root / "notifs").read_text().splitlines() if l.startswith("-a ")]
            self.assertEqual(len(notifs), 1, notifs)
            self.assertIn("perf=Mode Performance -- Processeur à 98 °C", notifs[0])     # « -- » avant le titre
            self.assertIn("firefox", notifs[0])
            appels = (root / "appels").read_text().splitlines()
            self.assertEqual(appels.count("nc-ile-etat capteurs"), 1)
            self.assertEqual(appels.count("nc-ile-etat sante"), 1)         # seulement à l'alerte, jamais en veille

    def test_notification_fermee_a_la_fin_et_episode_suivant(self):
        # notify-send avec un bouton attend un clic : sans fermeture à la fin de l'épisode, le Process resterait
        # « running » et l'épisode suivant n'aurait plus de notification
        with tempfile.TemporaryDirectory(prefix="nc-chaleur-") as d:
            root = Path(d)
            bouchons(root, d)
            shutil.copy2(QML / "Chaleur.qml", root)
            (root / "qmldir").write_text(self.QMLDIR)
            temp = root / "temp1_input"
            temp.write_text("98000\n")
            faux(root / "bin", "nc-ile-etat", f'case "$1" in capteurs) echo "cpu={temp}"; echo "capteurs=1" ;; sante) echo "cpu=5" ;; esac\n')
            faux(root / "bin", "notify-send", f'printf "%s\\n" "$*" >> "{root}/notifs"\nsleep 30\n')
            def ecrire(v):
                return f'Quickshell.execDetached(["sh", "-c", "echo {v} > \\"$1\\"", "sh", "{temp}"])'
            (root / "shell.qml").write_text(ENTETE_QML + textwrap.dedent('''\
                ShellRoot {
                    property int etape: 0
                    property real marque: 0
                    property int episodes: 0
                    function verifier(ok, message) { if (!ok) { console.error(message); Qt.exit(2) } }
                    function attendre(ms) { if (marque === 0) marque = Date.now(); if (Date.now() - marque < ms) return true; marque = 0; return false }
                    Timer { interval: 50; running: true; repeat: true; onTriggered: {
                        if (etape === 0) { Chaleur.intervalle = 100; Chaleur.duree = 300; Chaleur.demarrer(); marque = Date.now(); etape++ }
                        else if (etape === 1) { if (!Chaleur.alerte) { verifier(Date.now() - marque < 4000, "pas d'alerte"); return } marque = 0; etape++ }
                        else if (etape === 2) { if (attendre(500)) return
                            verifier(Chaleur.notificationOuverte, "notification pas lancée")
                            %(tiede)s; etape++ }
                        else if (etape === 3) { if (attendre(400)) return
                            verifier(!Chaleur.alerte, "alerte encore levée")
                            verifier(!Chaleur.notificationOuverte, "notify-send encore en attente après la fin de l'épisode")
                            if (++episodes === 2) Qt.quit()
                            %(chaud)s; marque = Date.now(); etape = 1 }
                    } }
                    Timer { interval: 12000; running: true; onTriggered: Qt.exit(9) }
                }
                ''') % {"chaud": ecrire(98000), "tiede": ecrire(80000)})
            with patch.dict(os.environ, PATH=f"{root / 'bin'}:{os.environ['PATH']}"):
                r, sortie = lancer_qs(root, d, delai=25)
            self.assertEqual(r.returncode, 0, sortie)
            notifs = [l for l in (root / "notifs").read_text().splitlines() if l.startswith("-a ")]
            self.assertEqual(len(notifs), 2, notifs)

    def test_repli_acpitz_sans_veille(self):
        # cpu_fiable=0 (acpitz en repli, valeur parfois fictive) : la page existe, la veille ne tourne pas
        with tempfile.TemporaryDirectory(prefix="nc-chaleur-") as d:
            root = Path(d)
            bouchons(root, d)
            shutil.copy2(QML / "Chaleur.qml", root)
            (root / "qmldir").write_text(self.QMLDIR)
            temp = root / "temp1_input"
            temp.write_text("99000\n")
            faux(root / "bin", "nc-ile-etat", f'case "$1" in capteurs) echo "cpu={temp}"; echo "cpu_fiable=0"; echo "capteurs=1" ;; esac\n')
            (root / "shell.qml").write_text(ENTETE_QML + textwrap.dedent('''\
                ShellRoot {
                    property int etape: 0
                    property real marque: 0
                    function verifier(ok, message) { if (!ok) { console.error(message); Qt.exit(2) } }
                    Timer { interval: 50; running: true; repeat: true; onTriggered: {
                        if (etape === 0) { Chaleur.intervalle = 100; Chaleur.duree = 200; Chaleur.demarrer(); marque = Date.now(); etape++ }
                        else if (etape === 1) { if (Date.now() - marque < 800) return
                            verifier(Etat.capteursSante, "page Santé absente avec acpitz")
                            verifier(Chaleur.fichierCpu === "" && !Chaleur.veille && Chaleur.derniereLecture === 0 && !Chaleur.alerte, "veille sur le repli acpitz")
                            Qt.quit() }
                    } }
                    Timer { interval: 8000; running: true; onTriggered: Qt.exit(9) }
                }
                '''))
            r, sortie = lancer_qs(root, d, delai=20)
            self.assertEqual(r.returncode, 0, sortie)

    def test_seuil_zero_jamais(self):
        with tempfile.TemporaryDirectory(prefix="nc-chaleur-") as d:
            root = Path(d)
            bouchons(root, d)
            shutil.copy2(QML / "Chaleur.qml", root)
            (root / "qmldir").write_text(self.QMLDIR)
            temp = root / "temp1_input"
            temp.write_text("99000\n")
            faux(root / "bin", "nc-ile-etat", f'case "$1" in capteurs) echo "cpu={temp}"; echo "capteurs=1" ;; esac\n')
            faux(root / "bin", "notify-send", f'printf "%s\\n" "$*" >> "{root}/notifs"\n')
            (root / "shell.qml").write_text(ENTETE_QML + textwrap.dedent('''\
                ShellRoot {
                    property int etape: 0
                    property real marque: 0
                    function verifier(ok, message) { if (!ok) { console.error(message); Qt.exit(2) } }
                    Timer { interval: 50; running: true; repeat: true; onTriggered: {
                        if (etape === 0) {
                            // Seuil : texte → défaut ; trop bas → plancher 50 ; trop haut → plafond 110 ; 0 → jamais
                            Reglages.valeurs = { CHALEUR_ALERTE: "abc" }; verifier(Chaleur.seuil === 95, "seuil invalide : " + Chaleur.seuil)
                            Reglages.valeurs = { CHALEUR_ALERTE: "20" }; verifier(Chaleur.seuil === 50, "plancher : " + Chaleur.seuil)
                            Reglages.valeurs = { CHALEUR_ALERTE: "500" }; verifier(Chaleur.seuil === 110, "plafond : " + Chaleur.seuil)
                            Reglages.valeurs = { CHALEUR_ALERTE: "0" }; Chaleur.intervalle = 100; Chaleur.duree = 200; Chaleur.demarrer(); etape++ }
                        else if (etape === 1) { if (Chaleur.fichierCpu === "") return; marque = Date.now(); etape++ }
                        else if (etape === 2) { if (Date.now() - marque < 700) return
                            verifier(!Chaleur.veille && Chaleur.derniereLecture === 0 && !Chaleur.alerte, "réglage à 0 : la veille tourne encore")
                            Reglages.valeurs = { CHALEUR_ALERTE: "90" }; marque = Date.now(); etape++ }
                        else if (etape === 3) { if (!Chaleur.alerte) { verifier(Date.now() - marque < 3000, "seuil 90 : pas d'alerte"); return } Qt.quit() }
                    } }
                    Timer { interval: 10000; running: true; onTriggered: Qt.exit(9) }
                }
                '''))
            r, sortie = lancer_qs(root, d, delai=20)
            self.assertEqual(r.returncode, 0, sortie)


@unittest.skipUnless(shutil.which("qs"), "Quickshell requis")
class Page(unittest.TestCase):
    """Sante.qml chargée hors écran : une jauge par capteur (la carte graphique endormie en gris), les ventilateurs,
    les trois profils (clic : Etat.choisirProfil), la carte d'alerte seulement pendant une alerte ; sans capteur,
    pas de jauge ni de bloc des ventilateurs ; aucune erreur QML."""

    def executer(self, sante, scenario):
        with tempfile.TemporaryDirectory(prefix="nc-sante-page-") as d:
            root = Path(d)
            bouchons(root, d)
            for nom in ("Sante", "JaugeSante", "Courbe", "Texte", "Ico", "Module", "Defilement", "Couleurs", "EnergieProfils", "BoutonEnergie", "PourquoiChaleur", "DemandeIA", "IaPrete"):
                shutil.copy2(QML / (nom + ".qml"), root)
            (root / "Chaleur.qml").write_text('pragma Singleton\nimport QtQuick\nQtObject { property bool alerte: false; property bool lenovo: true; '
                                              'property int seuil: 95; property string fichierCpu: "x"; readonly property bool performancePossible: Etat.performanceDisponible\n'
                                              '  function titre() { return "Processeur à 98 °C" } function situation() { return "s" } function causes() { return "c" } function gestes() { return "g" } }')
            (root / "qmldir").write_text("\n".join(("singleton " if n in ("Couleurs", "Reglages", "Etat", "Chaleur", "Partage") else "") + n + " 1.0 " + n + ".qml"
                                                   for n in ("Sante", "JaugeSante", "Courbe", "Texte", "Ico", "Module", "Defilement", "Couleurs", "Reglages", "Etat", "Chaleur", "Partage", "EnergieProfils", "BoutonEnergie", "PourquoiChaleur", "DemandeIA", "IaPrete")))
            faux(root / "bin", "nc-ile-etat", f'echo "nc-ile-etat $*" >> "{root}/appels"\nprintf \'{sante}\'\n')
            (root / "shell.qml").write_text(ENTETE_QML + "import Quickshell.Services.UPower\n" + textwrap.dedent('''\
                ShellRoot {
                    id: racine
                    property int etape: 0
                    property real marque: 0
                ''') + OUTILS_QML + textwrap.dedent('''\
                    function attendre(ms) { if (marque === 0) marque = Date.now(); if (Date.now() - marque < ms) return true; marque = 0; return false }
                    Window { id: w; visible: true; width: 400; height: 600; Sante { id: page; objectName: "page"; width: 378; height: 560 } }
                    Timer { interval: 50; running: true; repeat: true; onTriggered: {
                ''') + scenario + "\n} }\nTimer { interval: 10000; running: true; onTriggered: Qt.exit(9) }\n}")
            r, sortie = lancer_qs(root, d, delai=20)
            self.assertEqual(r.returncode, 0, sortie)
            return (root / "appels").read_text().count("nc-ile-etat sante")

    def test_page_complete(self):
        n = self.executer('cpu=12\\ntop=firefox\\t42\\ntemp=cpu\\t87\\t\\ntemp=carte\\t16\\t\\ntemp=ssd\\t35\\t84\\nfan=1\\t3600\\t5100\\nfan=2\\t0\\t5100\\n'
                          'temp=wifi\\t61\\t\\ntemp=ram\\t43\\t85\\ngpu=veille\\nprofil_firmware=custom\\n', '''
if (etape === 0) { if (attendre(900)) return
  var j = tous(page, "jaugeTemp"); verifier(j.length === 6, "jauges : " + j.length)
  verifier(j[0].titre === "Processeur" && j[0].valeur === "87 °C" && j[0].teinte === Couleurs.orange, "jauge processeur : " + j[0].titre + " " + j[0].valeur)
  verifier(j[1].titre === "Carte graphique" && j[1].sans && j[1].valeur === "en veille", "carte endormie : " + j[1].valeur)
  verifier(j[2].titre === "SSD" && j[2].teinte === Couleurs.vert, "ssd")
  verifier(j[5].titre === "Carte mère", "ordre des jauges : " + j[5].titre)
  verifier(trouver(page, "jaugeCharge").visible && trouver(page, "jaugeCharge").valeur === "12 %", "charge")
  verifier(trouver(page, "blocFans").visible && tous(page, "fan").length === 2, "ventilateurs")
  verifier(tous(page, "profil").length === 3 && tous(page, "profil").filter(p => p.actif).length === 1, "profils")
  verifier(!trouver(page, "alerteChaleur").visible, "carte d'alerte sans alerte")
  verifier(Etat.hauteurs.sante > 300, "hauteur non annoncée : " + Etat.hauteurs.sante)
  verifier(trouver(page, "programmeGourmand").visible, "programme gourmand absent")
  Partage.silence = true; verifier(!trouver(page, "programmeGourmand").visible, "programme gourmand visible pendant un partage d'écran"); Partage.silence = false
  Chaleur.alerte = true; etape++ }
else if (etape === 1) { verifier(trouver(page, "alerteChaleur").visible, "carte d'alerte absente")
  Etat.performanceDisponible = false
  verifier(!trouver(page, "blocProfil").visible && !trouver(page, "boutonPerformance").visible, "profils affichés sans service de profils")
  Etat.performanceDisponible = true
  verifier(cliquer(page, "boutonPerformance"), "bouton Performance introuvable")
  verifier(Etat.profilChoisi === PowerProfile.Performance, "clic Performance : " + Etat.profilChoisi)
  var p = tous(page, "profil")[0]; for (var i = 0; i < p.children.length; i++) if (p.children[i].containsMouse !== undefined) p.children[i].clicked(null)
  verifier(Etat.profilChoisi === PowerProfile.PowerSaver, "clic Économie : " + Etat.profilChoisi)
  page.visible = false; marque = Date.now(); etape++ }
else if (etape === 2) { if (attendre(500)) return; verifier(!page.affichee, "page cachée encore affichée"); Qt.quit() }
''')
        self.assertGreaterEqual(n, 1)
        self.assertLessEqual(n, 2)        # toutes les 2 s, et plus rien page cachée

    def test_courbe_conseil_textes(self):
        self.executer('cpu=8\\n', '''
if (etape === 0) { if (attendre(700)) return
  function rel(deg, charge, top) { return { temps: [{ id: "cpu", deg: deg, max: 0 }], fans: [], cpu: String(charge), top: top } }
  page.lecturesConseil = 3
  // La courbe ne garde jamais plus de maxPoints points ; la plus ancienne part la première
  for (var i = 0; i < 350; i++) page.noter(rel(40 + (i % 10), 10, undefined))
  verifier(page.histoTemp.length === 300 && page.histoCharge.length === 300, "historique non borné : " + page.histoTemp.length)
  verifier(page.histoTemp[299] === 49 && page.histoTemp[0] === 40 + (50 % 10), "ordre de l'historique")
  verifier(trouver(page, "courbeTemp").visible && trouver(page, "courbeTemp").nombre === 300, "courbe de température")
  verifier(trouver(page, "courbeTemp").teinte === Couleurs.vert, "teinte courbe fraîche")
  // Pas de conseil sans chauffe, ni pour un pic, ni quand la charge est forte ou que personne ne pèse
  page.noter(rel(60, 20, "Discord\\t75")); page.noter(rel(60, 20, "Discord\\t75")); page.noter(rel(60, 20, "Discord\\t75"))
  verifier(!trouver(page, "conseilChauffe").visible, "conseil sans chauffe")
  page.noter(rel(90, 40, "Discord\\t30")); page.noter(rel(90, 40, "Discord\\t30")); page.noter(rel(60, 40, "Discord\\t30"))
  verifier(!trouver(page, "conseilChauffe").visible, "conseil pour un pic")
  for (i = 0; i < 4; i++) page.noter(rel(92, 90, "Discord\\t75"))
  verifier(!trouver(page, "conseilChauffe").visible, "conseil sous forte charge")
  for (i = 0; i < 4; i++) page.noter(rel(92, 40, undefined))
  verifier(!trouver(page, "conseilChauffe").visible, "conseil sans programme gourmand")
  // Un autre programme à chaque relevé : la série repart de zéro
  page.noter(rel(92, 40, "a\\t30")); page.noter(rel(92, 40, "b\\t30")); page.noter(rel(92, 40, "a\\t30"))
  verifier(!trouver(page, "conseilChauffe").visible, "conseil pour des programmes qui changent")
  // Le bon cas : chaud, charge modérée, un programme en prend une grosse part, plusieurs relevés de suite
  page.noter(rel(90, 50, "Discord\\t30")); page.noter(rel(90, 50, "Discord\\t30"))
  verifier(!trouver(page, "conseilChauffe").visible, "conseil trop tôt")
  page.noter(rel(90, 50, "Discord\\t30"))
  var c = trouver(page, "conseilChauffe")
  verifier(c.visible, "conseil absent")
  verifier(page.conseil() === "Discord prend 30 % du processeur : redémarre-le, ou coupe son accélération matérielle.", "texte Discord : " + page.conseil())
  verifier(trouver(page, "courbeTemp").teinte === Couleurs.rouge, "courbe rouge à 90 °C : " + trouver(page, "courbeTemp").teinte)
  // Nom caché pendant un partage d'écran
  Partage.silence = true; verifier(!c.visible, "conseil visible pendant un partage d'écran"); Partage.silence = false
  verifier(c.visible, "conseil absent après le partage")
  // Textes selon le programme
  page.chaudNom = "firefox"; verifier(page.conseil().indexOf("onglets") > 0, "navigateur : " + page.conseil())
  page.chaudNom = "Isolated Web Co"; verifier(page.conseil().indexOf("onglets") > 0, "navigateur (contenu web)")
  page.chaudNom = "electron"; verifier(page.conseil().indexOf("accélération matérielle") > 0, "electron : " + page.conseil())
  page.chaudNom = "make"; verifier(page.conseil() === "make prend 30 % : ferme-le s'il ne sert pas.", "générique : " + page.conseil())
  // Page fermée : historique et conseil vidés
  page.visible = false; marque = Date.now(); etape++ }
else if (etape === 1) { if (attendre(500)) return
  verifier(page.histoTemp.length === 0 && page.histoCharge.length === 0 && page.chaudLectures === 0, "historique gardé page cachée")
  verifier(!trouver(page, "blocCourbes").visible, "courbes visibles page cachée")
  Qt.quit() }
''')

    def test_sans_capteur(self):
        self.executer('cpu=8\\n', '''
if (etape === 0) { if (attendre(700)) return
  verifier(tous(page, "jaugeTemp").length === 0 && !trouver(page, "blocFans").visible, "quelque chose d'affiché sans capteur")
  verifier(trouver(page, "jaugeCharge").visible, "charge du processeur")
  Etat.ecranVu = false; etape++ }
else if (etape === 1) { if (attendre(400)) return; Qt.quit() }
''')


if __name__ == "__main__":
    unittest.main()

"""Page Charge de l'île : « Qu'est-ce qui vide ma batterie ? » et santé de la batterie.

nc-conso est testé avec un faux /sys (NC_SYSFS) et un faux /proc (NC_PROC) : lissage de la puissance sur 5 s, temps
restant, programmes regroupés par appli sans le noyau, part estimée en watts, carte NVIDIA absente ou non, champs de
santé absents. La page Charge réelle est chargée hors écran avec un faux nc-conso : les lignes s'affichent, les champs
absents sont masqués, et rien n'est lu tant que la page n'est pas affichée. HOME isolé, jamais le vrai.
"""
from importlib.machinery import SourceFileLoader
from importlib.util import module_from_spec, spec_from_loader
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import textwrap
import unittest
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "home/.local/bin/nc-conso"
QML = REPO / "home/.config/quickshell/nc-ile"


def charger():
    """nc-conso comme module (sans extension .py)."""
    chargeur = SourceFileLoader("nc_conso", str(SCRIPT))
    m = module_from_spec(spec_from_loader("nc_conso", chargeur))
    chargeur.exec_module(m)
    return m


def ligne_stat(pid, comm, ppid, ticks, drapeaux=0, debut=100):
    # Champs après « (comm) » : état, ppid, pgrp, session, tty, tpgid, drapeaux, 4 fautes, utime, stime, …, début (22e)
    return f"{pid} ({comm}) S {ppid} 1 1 0 -1 {drapeaux} 0 0 0 0 {ticks} 0 0 0 20 0 1 0 {debut} 0 0\n"


class FauxSysteme:
    def __init__(self, racine):
        self.sys = racine / "sys"
        self.proc = racine / "proc"
        (self.sys / "class/power_supply").mkdir(parents=True)
        self.proc.mkdir()
        self.occupe = 0
        self.total = 0

    def batterie(self, nom="BAT0", **champs):
        d = self.sys / "class/power_supply" / nom
        d.mkdir(exist_ok=True)
        champs = {"TYPE": "Battery", **champs}
        (d / "uevent").write_text("".join(f"POWER_SUPPLY_{k}={v}\n" for k, v in champs.items()))
        return d

    def secteur(self):
        d = self.sys / "class/power_supply/AC"
        d.mkdir()
        (d / "uevent").write_text("POWER_SUPPLY_TYPE=Mains\nPOWER_SUPPLY_ONLINE=0\n")

    def processus(self, pid, comm, ticks, cmdline=None, ppid=1, drapeaux=0):
        d = self.proc / str(pid)
        d.mkdir(exist_ok=True)
        (d / "stat").write_text(ligne_stat(pid, comm, ppid, ticks, drapeaux))
        (d / "cmdline").write_bytes((cmdline if cmdline is not None else "").encode())

    def processeur(self, occupe, total):
        """/proc/stat : ticks occupés et totaux (tous les cœurs) depuis le démarrage."""
        inactif = total - occupe
        (self.proc / "stat").write_text(f"cpu  {occupe} 0 0 {inactif} 0 0 0 0 0 0\ncpu0 {occupe} 0 0 {inactif} 0 0 0 0 0 0\n")

    def nvidia(self):
        d = self.sys / "bus/pci/devices/0000:01:00.0"
        d.mkdir(parents=True)
        (d / "vendor").write_text("0x10de\n")


class Conso(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="nc-conso-")
        self.addCleanup(tmp.cleanup)
        self.racine = Path(tmp.name)
        self.f = FauxSysteme(self.racine)
        self.env = patch.dict(os.environ, HOME=str(self.racine), XDG_STATE_HOME=str(self.racine / "state"),
                              NC_SYSFS=str(self.f.sys), NC_PROC=str(self.f.proc), NC_RTX_VEILLE="")
        self.env.start()
        self.addCleanup(self.env.stop)
        self.m = charger()

    def test_lissage_sur_5_s_et_temps_restant(self):
        self.f.secteur()
        for t, w in ((0, 10), (2, 20), (4, 30)):
            self.f.batterie(STATUS="Discharging", CAPACITY=50, ENERGY_NOW=40_000_000, ENERGY_FULL=80_000_000, POWER_NOW=w * 1_000_000)
            r = self.m_mesure(t)
        self.assertEqual(r["batterie"]["watts"], 20.0, "moyenne des 5 dernières secondes")
        self.assertEqual(r["batterie"]["restant"], 7200, "40 Wh à 20 W : 2 h")
        self.assertEqual(r["batterie"]["pct"], 50)
        # À t = 6 s, la mesure de t = 0 est oubliée : (20 + 30 + 40) / 3
        self.f.batterie(STATUS="Discharging", CAPACITY=50, ENERGY_NOW=40_000_000, ENERGY_FULL=80_000_000, POWER_NOW=-40_000_000)
        self.assertEqual(self.m_mesure(6)["batterie"]["watts"], 30.0, "puissance négative (certains pilotes) comptée en valeur absolue")

    def m_mesure(self, t):
        if not hasattr(self, "mes"):
            self.mes = self.m.Mesureur()
        return self.mes.mesurer(t)

    def test_charge_en_uah_et_ua_deux_batteries(self):
        # µA × µV pour la puissance, µAh × V pour l'énergie ; deux batteries additionnées ; en charge : avant pleine
        commun = dict(STATUS="Charging", VOLTAGE_NOW=10_000_000, CURRENT_NOW=1_000_000)
        self.f.batterie("BAT0", CAPACITY=50, CHARGE_NOW=2_000_000, CHARGE_FULL=4_000_000, **commun)
        self.f.batterie("BAT1", CAPACITY=50, CHARGE_NOW=2_000_000, CHARGE_FULL=4_000_000, **commun)
        b = self.m_mesure(0)["batterie"]
        self.assertEqual(b["watts"], 20.0)
        self.assertEqual(b["statut"], "Charging")
        self.assertEqual(b["restant"], 7200, "40 Wh à remplir à 20 W")
        self.assertEqual(b["pct"], 50)

    def test_sans_batterie(self):
        self.f.secteur()
        souris = self.f.batterie("hidpp_battery_0", SCOPE="Device", CAPACITY=80)
        self.assertTrue(souris.exists())
        r = self.m_mesure(0)
        self.assertIsNone(r["batterie"], "la batterie d'une souris n'est pas celle du PC")
        self.assertIsNone(r["sante"])
        self.assertIsNone(r["rtx"])

    def preparer_programmes(self, facteur):
        """Huit applis (une en trois processus, une en script Python) et un fil du noyau ; ticks × facteur."""
        f = self.f
        f.processus(100, "firefox", 30 * facteur, "/usr/lib/firefox/firefox\0-new-window\0")
        f.processus(101, "Isolated Web Co", 15 * facteur, "/usr/lib/firefox/firefox\0-contentproc\0", ppid=100)
        f.processus(102, "Isolated Web Co", 5 * facteur, "/usr/lib/firefox/firefox\0-contentproc\0", ppid=100)
        f.processus(110, "chrome", 12 * facteur, "/opt/google/chrome/chrome --type=renderer --lang=fr")
        f.processus(120, "nc-truc", 8 * facteur, "python3\0/home/user/.local/bin/nc-truc\0")
        f.processus(130, "kitty", 6 * facteur, "kitty\0")
        f.processus(140, "Hyprland", 4 * facteur, "Hyprland\0")
        f.processus(150, "pipewire", 2 * facteur, "/usr/bin/pipewire\0")
        f.processus(160, "ghost", 0, "")
        f.processus(3, "kworker/0:1", 500 * facteur, "", ppid=2, drapeaux=0x00208040)
        f.processus(2, "kthreadd", 0, "", ppid=0, drapeaux=0x00208040)
        # Tout le processeur : 100 ticks occupés par seconde de mesure sur 1000 (le noyau compris)
        f.processeur(100 * facteur, 1000 * facteur)

    def test_top_5_regroupe_par_appli_sans_le_noyau_et_part_estimee(self):
        self.f.batterie(STATUS="Discharging", CAPACITY=60, ENERGY_NOW=30_000_000, POWER_NOW=10_000_000)
        self.preparer_programmes(1)
        premiere = self.m_mesure(0)
        self.assertEqual(premiere["top"], [], "un seul relevé : pas encore de temps écoulé")
        self.preparer_programmes(2)
        top = self.m_mesure(2)["top"]
        self.assertEqual([p["nom"] for p in top], ["Firefox", "Chrome", "Nc-truc", "Kitty", "Hyprland"])
        # Firefox : 50 ticks de ses trois processus sur 100 occupés (et 1000 au total) → 50 % × 10 W, 5 % du processeur
        self.assertEqual(top[0]["watts"], 5.0)
        self.assertEqual(top[0]["pct"], 5.0)
        self.assertEqual(top[1]["watts"], 1.2)
        self.assertNotIn("Kworker/0:1", [p["nom"] for p in top])
        # Les relevés de plus de 30 s sont oubliés : rien n'a bougé depuis, plus personne en tête
        top = self.m_mesure(40)["top"]
        self.assertEqual(top, [], "rien n'a tourné pendant les 30 dernières secondes")

    def test_en_charge_pas_de_watts_par_programme(self):
        self.f.batterie(STATUS="Charging", CAPACITY=60, ENERGY_NOW=30_000_000, ENERGY_FULL=60_000_000, POWER_NOW=40_000_000)
        self.preparer_programmes(1)
        self.m_mesure(0)
        self.preparer_programmes(2)
        top = self.m_mesure(2)["top"]
        self.assertEqual(top[0]["nom"], "Firefox")
        self.assertIsNone(top[0]["watts"], "en charge, la batterie mesure ce qui entre, pas ce que le PC consomme")
        self.assertEqual(top[0]["pct"], 5.0)

    def test_sans_proc_stat_les_programmes_seuls(self):
        self.f.batterie(STATUS="Discharging", CAPACITY=60, ENERGY_NOW=30_000_000, POWER_NOW=10_000_000)
        self.f.processus(100, "a", 10, "a\0")
        self.f.processus(101, "b", 10, "b\0")
        self.m_mesure(0)
        self.f.processus(100, "a", 40, "a\0")
        self.f.processus(101, "b", 20, "b\0")
        top = self.m_mesure(2)["top"]
        self.assertEqual([(p["nom"], p["watts"], p["pct"]) for p in top], [("A", 7.5, None), ("B", 2.5, None)])

    def test_rtx_absente_sans_appeler_nc_rtx_veille(self):
        appel = self.racine / "appel-rtx"
        faux = self.racine / "faux-rtx"
        faux.write_text(f"#!/bin/sh\ntouch {appel}\necho '{{\"hybride\": true, \"runtime_status\": \"suspended\"}}'\n")
        faux.chmod(0o755)
        with patch.dict(os.environ, NC_RTX_VEILLE=str(faux)):
            self.assertIsNone(self.m_mesure(0)["rtx"])
        self.assertFalse(appel.exists(), "sans carte NVIDIA, nc-rtx-veille n'est pas lancé")

    def test_rtx_endormie_allumee_ou_pc_non_hybride(self):
        self.f.nvidia()
        faux = self.racine / "faux-rtx"
        cas = [
            ({"hybride": True, "runtime_status": "suspended", "causes": []}, {"etat": "endormie", "cause": None}),
            ({"hybride": True, "runtime_status": "active", "causes": [{"cle": "processus:firefox", "nom": "Firefox", "texte": "Firefox utilise la carte NVIDIA"}]},
             {"etat": "allumee", "cause": "Firefox"}),
            ({"hybride": True, "runtime_status": "active", "causes": [{"cle": "inconnue", "texte": "sans cause trouvée"}]},
             {"etat": "allumee", "cause": None}),
            ({"hybride": False, "runtime_status": None}, None),
        ]
        for e, attendu in cas:
            with self.subTest(e=e):
                faux.write_text("#!/bin/sh\ncat <<'FIN'\n" + json.dumps(e) + "\nFIN\n")
                faux.chmod(0o755)
                with patch.dict(os.environ, NC_RTX_VEILLE=str(faux)):
                    self.assertEqual(self.m.Mesureur().mesurer(0)["rtx"], attendu)

    def test_rtx_relue_une_mesure_sur_cinq(self):
        self.f.nvidia()
        appels = self.racine / "appels-rtx"
        faux = self.racine / "faux-rtx"
        faux.write_text(f"#!/bin/sh\necho x >> {appels}\necho '{{\"hybride\": true, \"runtime_status\": \"suspended\"}}'\n")
        faux.chmod(0o755)
        with patch.dict(os.environ, NC_RTX_VEILLE=str(faux)):
            m = self.m.Mesureur()
            etats = [m.mesurer(t * 2)["rtx"] for t in range(6)]
        self.assertEqual(len(appels.read_text().split()), 2)
        self.assertTrue(all(e == {"etat": "endormie", "cause": None} for e in etats), "l'état est gardé entre deux lectures")

    def test_sante_complete(self):
        d = self.f.batterie(STATUS="Discharging", CAPACITY=60, ENERGY_NOW=30_000_000, ENERGY_FULL=46_000_000,
                            ENERGY_FULL_DESIGN=50_000_000, CYCLE_COUNT=143)
        (d / "charge_control_end_threshold").write_text("80\n")
        self.assertEqual(self.m_mesure(0)["sante"], {"garde": 92, "cycles": 143, "limite": {"active": True, "seuil": 80}})
        (d / "charge_control_end_threshold").write_text("100\n")
        self.assertEqual(self.m.Mesureur().mesurer(0)["sante"]["limite"], {"active": False, "seuil": None})
        (d / "charge_types").write_text("Fast Standard [Long_Life]\n")
        self.assertEqual(self.m.Mesureur().mesurer(0)["sante"]["limite"], {"active": True, "seuil": None})

    def test_sante_en_uah_et_mode_conservation_lenovo(self):
        self.f.batterie(STATUS="Full", CAPACITY=100, CHARGE_NOW=3_000_000, CHARGE_FULL=3_000_000, CHARGE_FULL_DESIGN=4_000_000)
        c = self.f.sys / "bus/platform/drivers/ideapad_acpi/VPC2004:00"
        c.mkdir(parents=True)
        (c / "conservation_mode").write_text("1\n")
        self.assertEqual(self.m_mesure(0)["sante"], {"garde": 75, "cycles": None, "limite": {"active": True, "seuil": None}},
                         "sans tension, le rapport des µAh reste juste")

    def test_sante_suit_la_mediane_de_nc_sysinfo(self):
        self.f.batterie(STATUS="Discharging", CAPACITY=60, ENERGY_NOW=30_000_000, ENERGY_FULL=46_000_000, ENERGY_FULL_DESIGN=50_000_000)
        h = self.racine / "state/nc/batterie-sante"
        h.parent.mkdir(parents=True)
        h.write_text("2026-10-01 45000000 50000000\n2026-10-02 45500000 50000000\n2026-10-03 47000000 50000000\n")
        self.assertEqual(self.m_mesure(0)["sante"]["garde"], 91, "même chiffre que la page Système")

    def test_champs_de_sante_absents(self):
        # Ni capacité d'origine, ni cycles (0 : inconnu chez beaucoup de pilotes), ni limite : rien
        self.f.batterie(STATUS="Discharging", CAPACITY=60, ENERGY_NOW=30_000_000, ENERGY_FULL=46_000_000, CYCLE_COUNT=0)
        self.assertIsNone(self.m_mesure(0)["sante"])
        self.f.batterie(STATUS="Discharging", CAPACITY=60, ENERGY_NOW=30_000_000, CYCLE_COUNT=12)
        self.assertEqual(self.m.Mesureur().mesurer(0)["sante"], {"garde": None, "cycles": 12, "limite": None})

    def test_suivre_ecrit_une_ligne_json_par_mesure(self):
        self.f.batterie(STATUS="Discharging", CAPACITY=60, ENERGY_NOW=30_000_000, POWER_NOW=10_000_000)
        env = dict(os.environ, NC_CONSO_PAS="0.05", PATH="/usr/bin:/bin")
        r = subprocess.run([str(SCRIPT), "suivre", "--fois", "3"], env=env, capture_output=True, text=True, timeout=10)
        self.assertEqual(r.returncode, 0, r.stderr)
        lignes = [json.loads(l) for l in r.stdout.splitlines()]
        self.assertEqual(len(lignes), 3)
        self.assertEqual(lignes[-1]["batterie"], {"statut": "Discharging", "pct": 60, "watts": 10.0, "restant": 10800})


# Faux nc-conso : note son lancement puis chaque ligne écrite (« tick »), et répète ~/mesure.json toutes les 0,1 s
FAUX_CONSO = """#!/bin/sh
echo start >> "$HOME/appels"
while :; do echo tick >> "$HOME/appels"; tr -d '\\n' < "$HOME/mesure.json"; echo; sleep 0.1; done
"""
COMPLETE = {
    "batterie": {"statut": "Discharging", "pct": 63, "watts": 12.3, "restant": 4680},
    "top": [{"nom": "Firefox", "pct": 8.2, "watts": 4.1}, {"nom": "Code", "pct": 4.0, "watts": 2.0},
            {"nom": "Discord", "pct": 2.1, "watts": 1.0}, {"nom": "Kitty", "pct": 0.4, "watts": 0.2},
            {"nom": "Hyprland", "pct": 0.3, "watts": 0.1}],
    "rtx": {"etat": "allumee", "cause": "Firefox"},
    "sante": {"garde": 92, "cycles": 143, "limite": {"active": True, "seuil": 80}},
}
VIDE = {"batterie": None, "top": [], "rtx": None, "sante": {"garde": None, "cycles": None, "limite": None}}


@unittest.skipUnless(shutil.which("qs"), "Quickshell requis")
class PageCharge(unittest.TestCase):
    def test_lignes_affichees_masquees_et_rien_lu_page_cachee(self):
        with tempfile.TemporaryDirectory(prefix="nc-conso-qml-") as d:
            root = Path(d)
            (root / "run").mkdir(mode=0o700)
            (root / "bin").mkdir()
            (root / "bin/nc-conso").write_text(FAUX_CONSO)
            (root / "bin/nc-conso").chmod(0o755)
            (root / "mesure.json").write_text(json.dumps(COMPLETE, ensure_ascii=False))
            (root / "mesure2.json").write_text(json.dumps(VIDE))
            noms = ("Charge", "Texte", "Ico", "Module", "Couleurs")
            for nom in noms:
                shutil.copy2(QML / (nom + ".qml"), root)
            (root / "Reglages.qml").write_text('pragma Singleton\nimport QtQuick\nQtObject {readonly property bool en: false; readonly property bool sobre: false; function t(fr,en){return fr} function val(k,d){return d}}')
            (root / "Etat.qml").write_text(textwrap.dedent('''\
                pragma Singleton
                import QtQuick
                QtObject {
                    readonly property string bin: "%s/bin/"
                    property var batterie: ({ timeToFull: 0, timeToEmpty: 4680 })
                    property bool branche: false
                    property bool enCharge: false
                    property int pourcent: 63
                    property var hauteurs: ({})
                    function annoncerHauteur(nom, h) { var t = Object.assign({}, hauteurs); t[nom] = Math.round(h); hauteurs = t }
                }''' % d))
            (root / "qmldir").write_text("\n".join(
                ("singleton " if n in ("Couleurs", "Reglages", "Etat") else "") + n + " 1.0 " + n + ".qml"
                for n in noms + ("Reglages", "Etat")))
            (root / "shell.qml").write_text(textwrap.dedent('''\
                import QtQuick
                import QtQuick.Window
                import Quickshell
                import Quickshell.Io
                ShellRoot {
                    property int etape: 0
                    property int attente: 0
                    property var page: null
                    function verifier(ok, message) { if (!ok) { console.error(message); Qt.exit(2) } return ok }
                    function trouver(item, nom) { if (item.objectName === nom) return item; for (var i = 0; i < item.children.length; i++) { var r = trouver(item.children[i], nom); if (r) return r } return null }
                    function tous(item, nom, l) { l = l || []; if (item.objectName === nom) l.push(item); for (var i = 0; i < item.children.length; i++) tous(item.children[i], nom, l); return l }
                    function texte(item) { var l = []; (function f(x) { if (x.text !== undefined && x.visible) l.push(x.text); for (var i = 0; i < x.children.length; i++) f(x.children[i]) })(item); return l.join(" | ") }
                    function marquer(m) { var p = marqueur.createObject(null, { command: ["sh", "-c", "echo " + m + " >> \\"$HOME/appels\\""] }); p.running = true }
                    Component { id: marqueur; Process {} }
                    Process { id: vider; command: ["sh", "-c", "cp \\"$HOME/mesure2.json\\" \\"$HOME/mesure.json\\""] }
                    Window {
                        id: w; visible: true; width: 432; height: 600; color: Couleurs.fond
                        Rectangle { anchors.fill: parent; color: Couleurs.fond }
                        // Comme une page de l'île (Ile.qml) : préparée en avance par un Loader asynchrone quand elle est
                        // voisine de la page affichée, mais transparente donc invisible tant qu'on n'y est pas
                        Item {
                            id: pageIle
                            x: 16; y: 16; width: 378; height: 560
                            opacity: 0
                            visible: opacity > 0.01
                            Loader { id: chargeur; anchors.fill: parent; asynchronous: true; active: true; source: "Charge.qml" }
                        }
                    }
                    Timer { interval: 100; running: true; repeat: true; onTriggered: {
                        if (etape === 0) { verifier(chargeur.status !== Loader.Error, "Charge.qml ne se charge pas"); if (chargeur.status !== Loader.Ready) return
                            page = chargeur.item; verifier(!page.visible, "page voisine visible"); etape++ }
                        // Page préparée en avance comme voisine (ou île fermée) : nc-conso n'est pas lancé
                        else if (etape === 1) { if (++attente < 6) return; marquer("montre"); pageIle.opacity = 1; etape++ }
                        else if (etape === 2) {
                            if (tous(page, "programme").length < 5) return
                            var t = texte(page)
                            verifier(trouver(page, "conso").visible, "ligne de consommation masquée")
                            verifier(t.indexOf("Consommation | 12,3 W · encore 1 h 18") >= 0, "consommation : " + t)
                            verifier(t.indexOf("Firefox | environ 4,1 W") >= 0, "part estimée : " + t)
                            verifier(t.indexOf("Carte NVIDIA : allumée — Firefox") >= 0, "carte NVIDIA : " + t)
                            verifier(t.indexOf("Ta batterie garde 92 % de sa capacité d'origine") >= 0, "usure : " + t)
                            verifier(t.indexOf("143 cycles de charge") >= 0, "cycles : " + t)
                            verifier(t.indexOf("Charge limitée à 80 % pour la ménager") >= 0, "limite : " + t)
                            verifier(Etat.hauteurs.charge > 300 && Etat.hauteurs.charge + 32 <= 580, "hauteur annoncée : " + Etat.hauteurs.charge)
                            verifier(page.childrenRect.height <= 560, "la page déborde")
                            var capture = Quickshell.env("NC_TEST_CAPTURE")
                            if (capture) w.contentItem.grabToImage(r => r.saveToFile(capture))
                            vider.running = true; etape++ }
                        // Champs absents : les lignes et les blocs disparaissent, la page se resserre
                        else if (etape === 3) {
                            if (trouver(page, "blocConso").visible) return
                            verifier(!trouver(page, "rtx").visible, "carte NVIDIA absente affichée")
                            verifier(!trouver(page, "blocSante").visible, "santé sans champ affichée")
                            verifier(Etat.hauteurs.charge < 100, "page non resserrée : " + Etat.hauteurs.charge)
                            verifier(texte(page).indexOf("undefined") < 0 && texte(page).indexOf("null") < 0, "valeur absente écrite : " + texte(page))
                            pageIle.opacity = 0; attente = 0; etape++ }
                        // Page cachée : nc-conso est arrêté, plus aucune lecture
                        else if (etape === 4) { if (++attente < 4) return; marquer("fige"); attente = 0; etape++ }
                        else if (etape === 5) { if (++attente < 6) return; Qt.quit() } } }
                    Timer { interval: 9000; running: true; onTriggered: Qt.exit(9) }
                }'''))
            env = dict(os.environ, HOME=d, QT_QPA_PLATFORM="offscreen", QT_QUICK_BACKEND="software",
                       XDG_RUNTIME_DIR=str(root / "run"), XDG_CACHE_HOME=str(root / ".cache"))
            env.pop("WAYLAND_DISPLAY", None)
            r = subprocess.run(["qs", "--no-color", "-p", str(root / "shell.qml")], env=env, capture_output=True, text=True, timeout=15)
            sortie = r.stdout + r.stderr
            self.assertEqual(r.returncode, 0, sortie)
            for erreur in ("ReferenceError", "TypeError", "Cannot assign", "Binding loop", "is not a type"):
                self.assertNotIn(erreur, sortie)
            appels = (root / "appels").read_text().split()
            self.assertEqual(appels[0], "montre", "nc-conso lancé alors que la page était cachée : " + " ".join(appels[:5]))
            self.assertEqual(appels.count("start"), 1)
            self.assertGreater(appels.count("tick"), 0)
            self.assertNotIn("tick", appels[appels.index("fige"):], "nc-conso tourne encore, page cachée")


# Faux qs, noctalia et systemctl : notent leurs arguments ; NC_TEST_ILE=0 : l'île n'est pas installée
FAUX_SYSTEMCTL = '#!/bin/sh\ncase "$2" in is-enabled) [ "${NC_TEST_ILE:-1}" = 1 ] ;; *) exit 0 ;; esac\n'
FAUX_QS = '#!/bin/sh\necho "qs $*" >> "$HOME/appels"\n'
FAUX_NOCTALIA = '#!/bin/sh\necho "noctalia $*" >> "$HOME/appels"\n'


class ClicBatterie(unittest.TestCase):
    def lancer(self, *args, ile=True):
        with tempfile.TemporaryDirectory(prefix="nc-clic-batterie-") as d:
            b = Path(d) / "bin"
            b.mkdir()
            for nom, code in (("systemctl", FAUX_SYSTEMCTL), ("qs", FAUX_QS), ("noctalia", FAUX_NOCTALIA), ("pgrep", "#!/bin/sh\nexit 0\n")):
                (b / nom).write_text(code)
                (b / nom).chmod(0o755)
            env = dict(HOME=d, PATH=str(b) + os.pathsep + "/usr/bin:/bin", NC_LANGUE="fr", NC_TEST_ILE="1" if ile else "0")
            r = subprocess.run([str(REPO / "home/.local/bin/nc-shell-msg"), *args], env=env, capture_output=True, text=True, timeout=10)
            self.assertEqual(r.returncode, 0, r.stderr)
            return (Path(d) / "appels").read_text().splitlines()

    def test_page_batterie_avec_repli(self):
        # L'île choisit : la page Batterie si elle existe, sinon Système (Etat.pageOu, testé dans test_island_pages)
        self.assertEqual(self.lancer("ile", "charge", "systeme"), ["qs -c nc-ile ipc call ile pageOu charge systeme"])
        # Sans l'île : le centre de Noctalia, sur l'onglet du repli
        self.assertEqual(self.lancer("ile", "charge", "systeme", ile=False), ["noctalia msg panel-toggle control-center system"])
        # Les autres icônes ne changent pas
        self.assertEqual(self.lancer("ile", "systeme"), ["qs -c nc-ile ipc call ile page systeme"])

    def test_ipc_et_barre(self):
        shell = (QML / "shell.qml").read_text()
        self.assertIn("function pageOu(nom: string, repli: string): void { page(Etat.pageOu(nom, repli)) }", shell)
        config = (REPO / "home/.config/noctalia/config.toml").read_text()
        bloc = config[config.index('[widget."nc/batterie:batterie".actions]'):][:200]
        self.assertIn('nc-shell-msg ile charge systeme"', bloc)


class PageBatterieSysfs(unittest.TestCase):
    def test_a_batterie(self):
        with tempfile.TemporaryDirectory(prefix="nc-a-batterie-") as d:
            f = FauxSysteme(Path(d))
            env = dict(os.environ, HOME=d, NC_SYSFS=str(f.sys))
            lancer = lambda: subprocess.run([str(SCRIPT), "a-batterie"], env=env, capture_output=True, timeout=10).returncode
            f.secteur()
            f.batterie("hidpp_battery_0", SCOPE="Device", CAPACITY=80)
            self.assertEqual(lancer(), 1, "PC fixe avec une souris sans fil : pas de page Batterie")
            f.batterie("BAT0", CAPACITY=80)
            self.assertEqual(lancer(), 0)


if __name__ == "__main__":
    unittest.main()

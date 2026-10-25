"""« Pourquoi ça se vide ? » de la page Charge : nc-conso pourquoi --json (les faits, sans IA) et --ia (nc-ia).

Faux /sys (NC_SYSFS), faux /proc (NC_PROC), faux nc-rtx-veille (NC_RTX_VEILLE), faux nc-ia (NC_IA) et faux outils
(hyprctl, bluetoothctl, brightnessctl, gdbus) dans un PATH à eux : rien ne touche la vraie session, aucune action réelle
n'est lancée (les commandes proposées sont seulement lues, jamais exécutées). Les cas : tout allumé, rien, sans batterie,
français et anglais, jamais d'action sur le rafraîchissement, et une réponse d'IA qui ne peut rien ajouter (action
inventée, commande, 5 000 caractères avec séquences d'échappement), IA coupée (aucun appel), délai. La carte
Pourquoi.qml est chargée hors écran avec le vrai qs. HOME isolé, jamais le vrai.
"""
import contextlib
import io
import json
import signal
import time
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
from unittest.mock import patch

from tests.test_conso import FauxSysteme, charger

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "home/.local/bin/nc-conso"
QML = REPO / "home/.config/quickshell/nc-ile"


class Base(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="nc-pourquoi-")
        self.addCleanup(tmp.cleanup)
        self.racine = Path(tmp.name)
        self.f = FauxSysteme(self.racine)
        self.bin = self.racine / "bin"
        self.bin.mkdir()
        self.journal = self.racine / "journal"
        (self.racine / ".config/nc").mkdir(parents=True)
        # Un portable sur batterie, écran à 100 %, profil Équilibré, rien d'autre
        self.f.batterie(STATUS="Discharging", CAPACITY=70, ENERGY_NOW=35_000_000, ENERGY_FULL=50_000_000, POWER_NOW=10_000_000)
        self.f.secteur()
        self.ecran(50)
        self.profil("balanced")
        # PATH réduit à nos faux : ni le vrai brightnessctl, ni busctl, ni gdbus de la machine
        self.faux("hyprctl", "echo '[]'")
        self.faux("bluetoothctl", 'case "$1" in show) echo "Powered: no" ;; esac')
        # Get (le service répond) : rien noté ; Set (changer le profil) : noté, ce qui ne doit jamais arriver ici
        self.faux("gdbus", f'case "$*" in *Set*) echo "gdbus $*" >> {self.journal} ;; esac')
        self.faux("brightnessctl", f'echo "brightnessctl $*" >> {self.journal}')
        self.env = dict(HOME=str(self.racine), XDG_STATE_HOME=str(self.racine / "state"), XDG_DATA_HOME=str(self.racine / "share"),
                        XDG_DATA_DIRS=str(self.racine / "vide"), NC_SYSFS=str(self.f.sys), NC_PROC=str(self.f.proc),
                        NC_RTX_VEILLE="", NC_LANGUE="fr", NC_CONSO_PAS="0.01", PATH=str(self.bin),
                        NC_IA=str(self.bin / "absent"))
        self.m = None

    # ── Le faux matériel ──
    def faux(self, nom, corps):
        p = self.bin / nom
        p.write_text("#!/bin/sh\n" + corps + "\n")
        p.chmod(0o755)
        return p

    def ecran(self, brut, maxi=100):
        d = self.f.sys / "class/backlight/intel_backlight"
        d.mkdir(parents=True, exist_ok=True)
        (d / "type").write_text("raw\n")
        (d / "brightness").write_text(f"{brut}\n")
        (d / "max_brightness").write_text(f"{maxi}\n")

    def profil(self, nom):
        d = self.f.sys / "firmware/acpi"
        d.mkdir(parents=True, exist_ok=True)
        (d / "platform_profile").write_text(nom + "\n")

    def bluetooth(self, allume=True, connectes=()):
        lignes = "".join(f'echo "Device {m} {n}"; ' for m, n in connectes)
        self.faux("bluetoothctl", f'case "$1" in show) echo "Powered: {"yes" if allume else "no"}" ;; '
                                  f'devices) {lignes}true ;; power) echo "bluetoothctl $*" >> {self.journal} ;; esac')

    def hyprctl(self, hz):
        self.faux("hyprctl", "echo '" + json.dumps([{"name": "eDP-1", "refreshRate": hz}, {"name": "DP-1", "refreshRate": 60.0}]) + "'")

    def rtx(self, relancable=True, cause=True):
        if not (self.f.sys / "bus").exists():
            self.f.nvidia()
        c = [{"cle": "processus:firefox", "nom": "Firefox", "texte": "Firefox utilise la carte NVIDIA", "pid": 4242,
              "debut": "555", "relancable": relancable}] if cause else [{"cle": "inconnue", "texte": "sans cause trouvée"}]
        e = json.dumps({"hybride": True, "runtime_status": "active", "causes": c})
        p = self.faux("faux-rtx", f"""case "$1" in
  etat) echo '{e}' ;;
  relancable) echo '{{"relancable": {"true" if relancable else "false"}, "nom": "Firefox", "raison": null}}'; {"exit 0" if relancable else "exit 1"} ;;
  *) echo "rtx $*" >> {self.journal} ;;
esac""")
        self.env["NC_RTX_VEILLE"] = str(p)

    def tout_allume(self):
        self.rtx()
        self.ecran(100)
        self.profil("performance")
        self.bluetooth()
        self.hyprctl(165.0)

    # ── Les faits ──
    def charger(self, **plus):
        env = dict(self.env, **plus)
        with patch.dict(os.environ, env):
            m = charger()
        return m

    def faits(self, m=None, **plus):
        """faits_pourquoi() en direct (l'attente de 1 s supprimée, les processus ne bougent pas)."""
        env = dict(self.env, **plus)
        with patch.dict(os.environ, env, clear=True):
            m = m or charger()
            with patch.object(m.os, "getpid", return_value=4_000_000), patch.object(m.time, "sleep"):
                return m.faits_pourquoi()

    def ids(self, f):
        return [c["id"] for c in f["causes"]]

    def lancer(self, *args, entree=None, **plus):
        """nc-conso en vrai (processus), pour la sortie JSON et l'IA ; entree : ce qu'on lui donne sur l'entrée standard."""
        env = dict(os.environ, **self.env)
        env.update(plus)
        r = subprocess.run([sys.executable, str(SCRIPT), *args], env=env, capture_output=True, text=True, timeout=30,
                           input=entree if entree is not None else "")
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)


class Faits(Base):
    def test_tout_allume(self):
        self.tout_allume()
        f = self.faits()
        self.assertTrue(f["sur_batterie"])
        self.assertEqual(self.ids(f), ["rtx", "profil", "luminosite", "rafraichissement", "bluetooth"])
        # Au plus 3 actions, les plus lourdes d'abord ; le Bluetooth (la plus légère) n'a plus son action
        self.assertEqual([a["id"] for a in f["actions"]], ["rtx_relancer", "profil_economie", "luminosite_baisser"])
        self.assertEqual([c["action"] for c in f["causes"]], ["rtx_relancer", "profil_economie", "luminosite_baisser", None, None])
        for a in f["actions"]:
            self.assertEqual(set(a), {"id", "libelle", "detail", "commande"})
            self.assertTrue(all(isinstance(x, str) for x in a["commande"]), a)
        a = {x["id"]: x for x in f["actions"]}
        self.assertEqual(a["rtx_relancer"]["commande"], [self.env["NC_RTX_VEILLE"], "relancer", "4242", "555", "--oui"])
        self.assertEqual(a["rtx_relancer"]["libelle"], "Relancer Firefox sur la carte intégrée")
        self.assertEqual(a["rtx_relancer"]["detail"], "Firefox sera fermé puis rouvert (enregistre ton travail)")
        self.assertEqual(a["luminosite_baisser"]["libelle"], "Luminosité 100 % → 60 %")
        # Pas de sous-titre qui répète le titre (aucun gain en watts mesurable)
        self.assertEqual((a["luminosite_baisser"]["detail"], a["profil_economie"]["detail"]), ("", ""))
        self.assertEqual(a["luminosite_baisser"]["commande"][1:], ["set", "60"])
        self.assertEqual(os.path.basename(a["luminosite_baisser"]["commande"][0]), "nc-brightness")
        self.assertEqual(a["profil_economie"]["commande"][0], "gdbus")
        self.assertIn("<'power-saver'>", a["profil_economie"]["commande"])
        self.assertEqual(a["profil_economie"]["libelle"], "Passer en Économie")
        # Trois phrases fixes, en français, tutoiement
        self.assertEqual(f["phrases"].count("."), 3, f["phrases"])
        self.assertIn("La carte NVIDIA est allumée (Firefox)", f["phrases"])
        self.assertIn("Performance", f["phrases"])
        self.assertIn("100 % de luminosité", f["phrases"])
        self.assertFalse(f["ia"])
        # Rien n'a été lancé : seulement lu
        self.assertFalse(self.journal.exists(), self.journal.read_text() if self.journal.exists() else "")

    def test_cles_des_causes(self):
        self.tout_allume()
        for c in self.faits()["causes"]:
            self.assertTrue({"id", "poids", "unite", "phrase", "action"} <= set(c), c)
            self.assertIn(c["unite"], ("W", "score"))
            self.assertIsInstance(c["poids"], (int, float))
            self.assertTrue(c["phrase"].endswith("."), c["phrase"])

    def test_rien(self):
        f = self.faits()
        self.assertTrue(f["sur_batterie"])
        self.assertEqual(f["causes"], [])
        self.assertEqual(f["actions"], [])
        self.assertTrue(f["phrases"].startswith("Rien d'anormal"), f["phrases"])

    def test_sans_batterie_ou_sur_secteur_pas_de_bouton(self):
        self.tout_allume()
        # Sur secteur (charge) : aucun fait, aucune cause
        self.f.batterie(STATUS="Charging", CAPACITY=70, ENERGY_NOW=35_000_000, ENERGY_FULL=50_000_000, POWER_NOW=10_000_000)
        f = self.faits()
        self.assertEqual((f["sur_batterie"], f["causes"], f["actions"], f["phrases"]), (False, [], [], ""))
        # Pleine
        self.f.batterie(STATUS="Full", CAPACITY=100)
        self.assertFalse(self.faits()["sur_batterie"])
        # Sans batterie du tout (ou seulement celle d'une souris) : la ligne n'existe pas
        shutil.rmtree(self.f.sys / "class/power_supply/BAT0")
        self.assertEqual(self.faits(), {"sur_batterie": False, "langue": "fr", "causes": [], "phrases": "", "actions": [], "ia": False,
                                       "batterie": None})
        self.f.batterie("hidpp_battery_0", SCOPE="Device", STATUS="Discharging", CAPACITY=80)
        self.assertFalse(self.faits()["sur_batterie"], "la batterie d'une souris n'est pas celle du PC")
        # Par la ligne de commande : une seule sortie JSON, avec ou sans --json, jamais d'IA appelée
        for args in (("pourquoi",), ("pourquoi", "--json"), ("pourquoi", "--ia")):
            self.assertFalse(self.lancer(*args)["sur_batterie"])

    def test_programmes_noms_seulement(self):
        """Le nom de l'appli, jamais la ligne de commande (ici un jeton dans les arguments)."""
        self.f.processus(100, "firefox", 10, "/usr/bin/firefox\0--token=SECRET123\0https://exemple.fr/?cle=abc\0", exe="/usr/bin/firefox")
        self.f.processus(101, "code", 10, "/usr/bin/code\0/srv/projet-prive\0", exe="/usr/bin/code")
        self.f.processeur(100, 1000)
        m = self.charger()
        suivant = {"n": 0}

        def dormir(_):
            self.f.processus(100, "firefox", 70, "/usr/bin/firefox\0--token=SECRET123\0", exe="/usr/bin/firefox")
            self.f.processus(101, "code", 30, "/usr/bin/code\0", exe="/usr/bin/code")
            self.f.processeur(180, 1100)
        with patch.dict(os.environ, self.env, clear=True), patch.object(m.os, "getpid", return_value=4_000_000), \
                patch.object(m.time, "sleep", dormir):
            f = m.faits_pourquoi()
        c = {x["id"]: x for x in f["causes"]}["programmes"]
        self.assertEqual(c["noms"], ["Firefox", "Code"])
        self.assertEqual(c["unite"], "W")
        self.assertEqual(c["poids"], 10.0, "toute la puissance, partagée entre les deux")
        self.assertIn("Firefox et Code prennent le plus de processeur (environ 10,0 W)", f["phrases"])
        texte = json.dumps(f, ensure_ascii=False)
        for interdit in ("SECRET123", "--token", "exemple.fr", "/srv/projet-prive", "/usr/bin"):
            self.assertNotIn(interdit, texte)
        self.assertEqual(f["actions"], [], "les programmes n'ont pas d'action")

    def test_rtx_non_relancable_cause_sans_action(self):
        self.rtx(relancable=False)
        f = self.faits()
        self.assertEqual(self.ids(f), ["rtx"])
        self.assertIsNone(f["causes"][0]["action"])
        self.assertEqual(f["actions"], [])
        # nc-rtx-veille ne dit pas relançable lui-même (session, programme introuvable…) : pas de relance, même si le
        # processus semblait relançable dans la liste
        self.rtx()
        self.faux("faux-rtx", self.bin.joinpath("faux-rtx").read_text().split("\n", 1)[1].replace('"relancable": true, "nom"', '"relancable": false, "nom"').replace("exit 0", "exit 1"))
        self.assertEqual(self.faits()["actions"], [])

    def test_rtx_sans_cause_trouvee_ni_nvidia(self):
        self.rtx(cause=False)
        f = self.faits()
        self.assertEqual((self.ids(f), f["actions"]), (["rtx"], []))
        self.assertEqual(f["causes"][0]["phrase"], "La carte NVIDIA est allumée : elle consomme beaucoup plus que la carte intégrée.")
        # Pas de carte NVIDIA : nc-rtx-veille n'est même pas lancé
        shutil.rmtree(self.f.sys / "bus")
        self.assertEqual(self.faits()["causes"], [])

    def test_rtx_ne_ferme_jamais_rien_au_calcul(self):
        self.rtx()
        self.faits()
        # Seulement « etat » et « relancable » : jamais « relancer »
        self.assertFalse(self.journal.exists())

    def test_cibles_sans_rien_a_ecrire(self):
        # brightnessctl absent : la cause reste (lue dans /sys), l'action n'existe pas
        self.ecran(100)
        (self.bin / "brightnessctl").unlink()
        f = self.faits()
        self.assertEqual((self.ids(f), f["actions"]), (["luminosite"], []))
        self.assertIsNone(f["causes"][0]["action"])
        # Pas de rétroéclairage (PC fixe) : pas de cause
        shutil.rmtree(self.f.sys / "class/backlight")
        self.assertEqual(self.faits()["causes"], [])

    def test_luminosite_echelle_de_nc_brightness(self):
        # nc-brightness get : racine du rapport (courbe au carré) ; 64/100 -> 80 %, 36/100 -> 60 %
        self.ecran(64)
        self.assertEqual(self.ids(self.faits()), ["luminosite"])
        self.ecran(63)
        self.assertEqual(self.ids(self.faits()), [], "79 % : pas encore haute")
        self.ecran(36)
        self.assertEqual(self.ids(self.faits()), [])

    def test_profil_selon_le_service_disponible(self):
        self.profil("performance")
        (self.bin / "gdbus").unlink()
        self.assertEqual(self.faits()["actions"], [], "aucun outil, aucun service")
        self.faux("powerprofilesctl", 'case "$1" in get) echo performance ;; esac')
        self.assertEqual(self.faits()["actions"][0]["commande"], ["powerprofilesctl", "set", "power-saver"])
        (self.bin / "powerprofilesctl").unlink()
        self.faux("noctalia", "true")
        self.faux("busctl", "echo 's \"performance\"'")
        self.assertEqual(self.faits()["actions"][0]["commande"], ["noctalia", "msg", "power-set", "power-saver"])
        # Les noms de profil d'une Legion comptent comme Performance ; Équilibré et Économie, non
        for brut, attendu in (("max-power", True), ("balanced-performance", True), ("balanced", False), ("low-power", False)):
            self.profil(brut)
            self.assertEqual("profil" in self.ids(self.faits()), attendu, brut)

    def test_pas_d_action_profil_si_le_service_ne_repond_pas(self):
        """gdbus est installé presque partout, le service de profils non : la cause reste, l'action disparaît."""
        self.profil("performance")
        self.faux("gdbus", "exit 1")                         # « The name net.hadess.PowerProfiles was not provided »
        f = self.faits()
        self.assertEqual((self.ids(f), f["actions"]), (["profil"], []))
        self.assertIsNone(f["causes"][0]["action"])
        self.faux("busctl", "exit 1")
        self.faux("powerprofilesctl", "exit 1")
        self.assertEqual(self.faits()["actions"], [])
        self.faux("busctl", "echo 's \"performance\"'")       # il répond : l'action revient
        self.assertEqual(self.faits()["actions"][0]["id"], "profil_economie")

    def test_profil_lu_par_dbus_sans_profil_de_plateforme(self):
        self.profil("custom")
        self.faux("busctl", "echo 's \"performance\"'")
        self.assertEqual(self.ids(self.faits()), ["profil"])
        self.faux("busctl", "echo 's \"balanced\"'")
        self.assertEqual(self.faits()["causes"], [])

    def test_bluetooth(self):
        self.bluetooth()
        f = self.faits()
        self.assertEqual(self.ids(f), ["bluetooth"])
        self.assertEqual(f["actions"][0]["commande"], ["bluetoothctl", "power", "off"])
        self.assertEqual(f["actions"][0]["libelle"], "Couper le Bluetooth")
        self.bluetooth(connectes=[("AA:BB:CC:DD:EE:FF", "Casque")])
        self.assertEqual(self.faits()["causes"], [], "un appareil est connecté")
        self.bluetooth(allume=False)
        self.assertEqual(self.faits()["causes"], [], "déjà coupé")
        (self.bin / "bluetoothctl").unlink()
        self.assertEqual(self.faits()["causes"], [], "pas de Bluetooth")

    def test_165_hz_jamais_d_action(self):
        self.hyprctl(165.0)
        f = self.faits()
        self.assertEqual(self.ids(f), ["rafraichissement"])
        self.assertIsNone(f["causes"][0]["action"])
        self.assertEqual(f["actions"], [])
        self.assertIn("165 Hz", f["phrases"])
        self.assertIn("je n'y touche pas", f["phrases"])
        # Avec toutes les autres causes : aucune action ne touche à l'écran ou à Hyprland
        self.tout_allume()
        tout = self.faits()
        for a in tout["actions"]:
            for mot in ("hyprctl", "refresh", "monitor", "hz"):
                texte = " ".join([os.path.basename(a["commande"][0])] + a["commande"][1:] + [a["libelle"], a["detail"]])
                self.assertNotIn(mot, texte.lower())
        # Un écran à 60 Hz, ou sans Hyprland : pas de cause
        self.hyprctl(60.0)
        self.assertNotIn("rafraichissement", self.ids(self.faits()))
        (self.bin / "hyprctl").unlink()
        self.assertNotIn("rafraichissement", self.ids(self.faits()))

    def test_textes_francais_et_anglais(self):
        self.tout_allume()
        fr = self.faits()
        en = self.faits(NC_LANGUE="en")
        self.assertEqual((fr["langue"], en["langue"]), ("fr", "en"))
        self.assertEqual(self.ids(fr), self.ids(en))
        self.assertEqual([a["id"] for a in fr["actions"]], [a["id"] for a in en["actions"]])
        a = {x["id"]: x for x in en["actions"]}
        self.assertEqual(a["luminosite_baisser"]["libelle"], "Brightness 100% → 60%")
        self.assertEqual(a["rtx_relancer"]["libelle"], "Restart Firefox on the integrated GPU")
        self.assertEqual(a["rtx_relancer"]["detail"], "Firefox will be closed then reopened (save your work)")
        self.assertEqual(a["profil_economie"]["libelle"], "Switch to Power Saver")
        self.assertIn("The NVIDIA GPU is on (Firefox)", en["phrases"])
        self.assertIn("165 Hz: it uses a bit more power, but I leave it alone.", " ".join(c["phrase"] for c in en["causes"]))
        for mot in ("allumée", "écran", "Économie", "tourne"):
            self.assertNotIn(mot, en["phrases"] + json.dumps(en["actions"], ensure_ascii=False))
        self.ecran(50)
        self.profil("balanced")
        (self.bin / "bluetoothctl").unlink()
        (self.bin / "hyprctl").unlink()
        shutil.rmtree(self.f.sys / "bus")                     # plus de carte NVIDIA
        self.assertEqual(self.faits(NC_LANGUE="en")["phrases"], "Nothing unusual: your battery drains at the pace of what you're doing.")

    def processus_occupes(self, m, cmdline, exe, comm="python3"):
        """Un processus qui prend tout le processeur entre les deux relevés ; renvoie le dormir() à poser."""
        self.f.processus(100, comm, 10, cmdline, exe=exe)
        self.f.processeur(100, 1000)

        def dormir(_):
            self.f.processus(100, comm, 90, cmdline, exe=exe)
            self.f.processeur(180, 1100)
        return dormir

    def test_un_nom_tire_d_un_script_devient_un_script(self):
        """Un interprète qui lance un fichier : son nom (un projet perso) ne part jamais vers l'IA ni dans « noms »."""
        m = self.charger()
        dormir = self.processus_occupes(m, "python3\0/srv/projet-prive/monsecret.py\0", "/usr/bin/python3")
        with patch.dict(os.environ, self.env, clear=True), patch.object(m.os, "getpid", return_value=4_000_000), \
                patch.object(m.time, "sleep", dormir):
            f = m.faits_pourquoi()
        c = {x["id"]: x for x in f["causes"]}["programmes"]
        self.assertEqual(c["noms"], ["un script"])
        self.assertNotIn("monsecret", json.dumps(c), "ni dans noms ni ailleurs dans la cause")
        # Un exécutable ordinaire garde son nom
        shutil.rmtree(self.f.proc / "100")
        m2 = self.charger()
        dormir = self.processus_occupes(m2, "/opt/outil/bin/rapide\0--x\0", "/opt/outil/bin/rapide", comm="rapide")
        with patch.dict(os.environ, self.env, clear=True), patch.object(m2.os, "getpid", return_value=4_000_000), \
                patch.object(m2.time, "sleep", dormir):
            f = m2.faits_pourquoi()
        self.assertEqual({x["id"]: x for x in f["causes"]}["programmes"]["noms"], ["Rapide"])
        # Et la sortie de suivre (page Charge) n'a pas de champ « script »
        self.assertNotIn("script", json.dumps(m2.Mesureur().mesurer(0)["top"]))

    def test_la_phrase_nvidia_nomme_l_appli_que_l_action_relance(self):
        self.f.nvidia()
        c = [{"cle": "processus:zoom", "nom": "Zoom", "texte": "x", "pid": 1, "debut": "5", "relancable": False},
             {"cle": "processus:firefox", "nom": "Firefox", "texte": "x", "pid": 4242, "debut": "555", "relancable": True}]
        e = json.dumps({"hybride": True, "runtime_status": "active", "causes": c})
        p = self.faux("faux-rtx", f"""case "$1" in
  etat) echo '{e}' ;;
  relancable) echo '{{"relancable": true}}' ;;
esac""")
        self.env["NC_RTX_VEILLE"] = str(p)
        f = self.faits()
        self.assertEqual(f["actions"][0]["commande"][2:4], ["4242", "555"])
        self.assertIn("(Firefox)", f["causes"][0]["phrase"])
        self.assertNotIn("Zoom", f["causes"][0]["phrase"])
        self.assertIn("Firefox", f["actions"][0]["libelle"])

    def test_pid_et_debut_en_chiffres_ascii_seulement(self):
        self.f.nvidia()
        for pid, debut in (("²", "555"), ("4242", "٣٣"), ("42 42", "555"), ("4242;ls", "5")):
            c = [{"cle": "processus:firefox", "nom": "Firefox", "texte": "x", "pid": pid, "debut": debut, "relancable": True}]
            e = json.dumps({"hybride": True, "runtime_status": "active", "causes": c})
            self.env["NC_RTX_VEILLE"] = str(self.faux("faux-rtx", f"""case "$1" in
  etat) echo '{e}' ;;
  relancable) echo '{{"relancable": true}}' ;;
esac"""))
            self.assertEqual(self.faits()["actions"], [], (pid, debut))

    def test_noms_longs_coupes_dans_les_libelles(self):
        self.rtx()
        long_ = "UneApplicationAuNomInterminableEtSansEspaceAucun"
        self.env["NC_RTX_VEILLE"] = str(self.faux("faux-rtx", self.bin.joinpath("faux-rtx").read_text().split("\n", 1)[1].replace("Firefox", long_)))
        a = self.faits()["actions"][0]
        self.assertLessEqual(len(a["libelle"]), 60)
        self.assertLessEqual(len(a["detail"]), 100)
        self.assertIn("…", a["libelle"])

    def test_phrases_courtes(self):
        self.tout_allume()
        self.assertLessEqual(len(self.faits()["phrases"]), 330, "trois phrases fixes au plus (l'IA : 250 caractères)")

    def test_retroeclairage_choisi_par_nc_brightness_appareil(self):
        """nvidia_0 quand l'écran interne est sur la NVIDIA ; sans « appareil » (ancien script : aide, code 1), le choix d'avant."""
        self.ecran(100)                                                  # intel_backlight : 100 %
        d = self.f.sys / "class/backlight/nvidia_0"
        d.mkdir(parents=True)
        for n, v in (("type", "raw"), ("brightness", "25"), ("max_brightness", "100")):   # 50 % sur l'échelle de nc-brightness
            (d / n).write_text(v + "\n")
        m = self.charger()
        fixe = lambda corps: self.faux("faux-nc-brightness", corps)
        cas = (('echo nvidia_0', 50), ('echo /sys/class/backlight/nvidia_0', 50), ('echo aide; exit 1', 100),
               ('echo inexistant', 100), ('echo "../../etc"', 100), ('exit 0', 100))
        for corps, attendu in cas:
            with self.subTest(corps):
                chemin = str(fixe(corps))
                with patch.dict(os.environ, self.env, clear=True), patch.object(m, "outil", lambda nom: chemin):
                    self.assertEqual(m.luminosite(), attendu)

    def test_au_plus_trois_actions_meme_avec_quatre_possibles(self):
        self.tout_allume()
        self.assertLessEqual(len(self.faits()["actions"]), 3)

    def test_la_sortie_cli_est_un_seul_json(self):
        self.tout_allume()
        f = self.lancer("pourquoi", "--json")
        self.assertEqual(set(f), {"sur_batterie", "langue", "causes", "phrases", "actions", "ia", "batterie"})
        self.assertEqual(f["batterie"], {"pct": 70, "watts": 10.0})
        self.assertTrue(all("_tri" not in c for c in f["causes"]))
        self.assertEqual(f, self.lancer("pourquoi"))


FAUX_IA = """#!/bin/sh
# Faux nc-ia : note ses arguments et la question reçue, puis rend la réponse du fichier réponse
echo "nc-ia $*" >> {journal}
while IFS= read -r l || [ -n "$l" ]; do printf '%s\\n' "$l" >> {entree}; done
{corps}
"""


class Ia(Base):
    def setUp(self):
        super().setUp()
        self.entree = self.racine / "question"

    def ia(self, reponse=None, corps=None, code=0):
        """Un faux nc-ia qui répond cette réponse (une chaîne, ou un objet mis en JSON) puis sort avec ce code."""
        if corps is None:
            texte = reponse if isinstance(reponse, str) else json.dumps(reponse)
            corps = "printf '%s' '" + texte.replace("'", "'\\''") + f"'\nexit {code}"
        p = self.bin / "faux-ia"
        p.write_text(FAUX_IA.format(journal=self.journal, entree=self.entree, corps=corps))
        p.chmod(0o755)
        self.env["NC_IA"] = str(p)

    def appels_ia(self):
        return [l for l in (self.journal.read_text().splitlines() if self.journal.exists() else []) if l.startswith("nc-ia")]

    def test_phrases_de_l_ia_et_ordre_des_actions(self):
        self.tout_allume()
        self.ia({"phrases": "Ta carte NVIDIA et l'écran trop lumineux vident la batterie.",
                 "ordre": ["luminosite_baisser", "profil_economie"]})
        f = self.lancer("pourquoi", "--ia")
        self.assertTrue(f["ia"])
        self.assertEqual(f["phrases"], "Ta carte NVIDIA et l'écran trop lumineux vident la batterie.")
        # Remis dans l'ordre demandé ; l'action oubliée par l'IA reste, à la fin
        self.assertEqual([a["id"] for a in f["actions"]], ["luminosite_baisser", "profil_economie", "rtx_relancer"])
        self.assertEqual(self.appels_ia(), ["nc-ia demander --usage question -"], "pas de --fond : un clic de l'utilisateur")

    def test_aucune_action_hors_liste(self):
        self.tout_allume()
        reference = self.lancer("pourquoi", "--json")
        permis = {a["id"]: a for a in reference["actions"]}
        mechant = {"phrases": "Fais ceci.", "ordre": ["supprimer_tout", "../../bin/sh", "profil_economie", "profil_economie", 42, None, ["x"]],
                   "actions": [{"id": "supprimer_tout", "libelle": "Tout supprimer", "detail": "x", "commande": ["rm", "-rf", "/"]}],
                   "commande": ["rm", "-rf", "/"], "action": {"id": "x", "commande": ["curl", "evil"]}}
        self.ia(mechant)
        f = self.lancer("pourquoi", "--ia")
        self.assertTrue(f["ia"])
        self.assertEqual(sorted(a["id"] for a in f["actions"]), sorted(permis), "aucune action ajoutée, aucune perdue")
        self.assertEqual(f["actions"][0]["id"], "profil_economie")
        for a in f["actions"]:
            self.assertEqual(a, permis[a["id"]], "les commandes sont celles de nc-conso, pas celles de l'IA")
        texte = json.dumps(f)
        for interdit in ("rm", "evil", "curl", "supprimer_tout"):
            self.assertNotIn(interdit, [x for a in f["actions"] for x in a["commande"]])
        self.assertNotIn("Tout supprimer", texte)

    def test_texte_long_avec_sequences_d_echappement(self):
        self.tout_allume()
        sale = "\x1b[31mROUGE\x1b[0m " + "mot " * 1500 + "\x07\x1b]0;titre\x07\x00\x7f fin"
        self.assertGreater(len(sale), 5000)
        self.ia({"phrases": sale, "ordre": []})
        f = self.lancer("pourquoi", "--ia")
        self.assertTrue(f["ia"])
        p = f["phrases"]
        self.assertLessEqual(len(p), 400)
        self.assertTrue(p.startswith("ROUGE mot mot"), p[:30])
        self.assertTrue(p.endswith("…"))
        self.assertTrue(all(c == " " or c.isprintable() for c in p), repr(p))
        for interdit in ("\x1b", "\x07", "\x00", "\x7f", " ", "[31m", "titre"):
            self.assertNotIn(interdit, p)

    def test_reponse_inutilisable_garde_les_phrases_fixes(self):
        self.tout_allume()
        fixe = self.lancer("pourquoi", "--json")
        cas = {"pas du json": dict(reponse="Bonjour, voici mon avis."),
               "échec": dict(reponse={"phrases": "Autre", "ordre": []}, code=1),
               "phrases vides": dict(reponse={"phrases": "   \x1b[0m ", "ordre": []}),
               "phrases pas un texte": dict(reponse={"phrases": ["a", "b"], "ordre": []}),
               "liste": dict(reponse=["phrases"]),
               "rien": dict(reponse="")}
        for nom, c in cas.items():
            with self.subTest(nom):
                self.ia(**c)
                f = self.lancer("pourquoi", "--ia")
                self.assertEqual(f, fixe, "mêmes faits, mêmes phrases, aucune erreur affichée")
        # JSON entouré de texte ou de ```
        self.ia("Voici :\n```json\n" + json.dumps({"phrases": "Bien.", "ordre": ["rtx_relancer"]}) + "\n```")
        f = self.lancer("pourquoi", "--ia")
        self.assertEqual((f["ia"], f["phrases"], f["actions"][0]["id"]), (True, "Bien.", "rtx_relancer"))

    def test_delai_depasse_phrases_fixes(self):
        self.tout_allume()
        self.ia(corps="while :; do :; done")                 # ne répond jamais
        m = self.charger()
        with patch.dict(os.environ, self.env, clear=True), patch.object(m, "DELAI_IA", 0.4), \
                patch.object(m.os, "getpid", return_value=4_000_000), patch.object(m.time, "sleep"):
            f = m.faits_pourquoi()
            t0 = m.time.monotonic()
            self.assertIsNone(m.appeler_ia(dict(f, actions=[a["id"] for a in f["actions"]])))
            self.assertLess(m.time.monotonic() - t0, 3)

    def test_faits_donnes_par_l_ile_rien_n_est_remesure(self):
        """--faits : l'IA raconte les faits AFFICHÉS, même si le monde a changé depuis ; la réponse ne porte que sur le
        texte et l'ordre des ids, jamais sur une commande."""
        self.tout_allume()
        faits = self.lancer("pourquoi", "--json")
        self.ecran(50)                                       # si c'était remesuré, la luminosité ne serait plus une cause
        self.profil("balanced")
        self.ia({"phrases": "Récit.", "ordre": ["luminosite_baisser", "rtx_relancer", "inconnue", "luminosite_baisser", 7],
                 "actions": [{"id": "x", "commande": ["rm", "-rf", "/"]}]})
        # Un JSON empoisonné d'une commande : elle ne part pas vers l'IA et ne revient pas
        faits["actions"][0]["commande"] = ["rm", "-rf", "/"]
        r = self.lancer("pourquoi", "--ia", "--faits", "-", entree=json.dumps(faits))
        self.assertEqual(r, {"ia": True, "phrases": "Récit.", "ordre": ["luminosite_baisser", "rtx_relancer"]})
        q = self.entree.read_text()
        self.assertIn("luminosite_baisser", q, "les actions affichées, pas celles du monde d'après")
        self.assertIn("profil_economie", q)
        for interdit in ("rm -rf", "-rf", "gdbus", "faux-rtx", '"rm"'):
            self.assertNotIn(interdit, q)
        self.assertEqual(len(self.appels_ia()), 1)

    def test_les_faits_ne_sont_jamais_dans_l_argv(self):
        """Lisible par les autres comptes dans /proc/*/cmdline : les faits passent par l'entrée standard."""
        self.tout_allume()
        faits = self.lancer("pourquoi", "--json")
        pids = self.racine / "pids"
        self.ia(corps=self.FAUX_LENT.format(pids=pids, journal=self.journal))
        env = dict(os.environ, **self.env)
        p = subprocess.Popen([sys.executable, str(SCRIPT), "pourquoi", "--ia", "--faits", "-"], env=env, stdin=subprocess.PIPE,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.addCleanup(lambda: p.poll() is None and p.kill())
        p.stdin.write(json.dumps(faits))
        p.stdin.close()
        self.assertTrue(self.attendre(lambda: pids.exists() and pids.read_text().strip()), "nc-ia n'a pas démarré")
        for pid in [p.pid] + pids.read_text().split():
            argv = Path(f"/proc/{pid}/cmdline").read_bytes().decode().replace("\0", " ")
            for mot in ("luminosite", "rtx", "causes", "profil", "{"):
                self.assertNotIn(mot, argv, f"pid {pid} : {argv}")
        p.send_signal(signal.SIGTERM)
        p.wait(timeout=10)

    def test_faits_inutilisables_ou_ia_coupee_aucun_appel(self):
        self.tout_allume()
        faits = self.lancer("pourquoi", "--json")
        self.ia({"phrases": "Non.", "ordre": []})
        mauvais = ["pas du json", "[]", json.dumps({"causes": "x", "actions": []}),
                   json.dumps(dict(faits, causes=[{"id": "../../x"}])),
                   json.dumps(dict(faits, actions=[{"id": "Rm -rf"}])), json.dumps(faits) + " " * 30000]
        for m in mauvais:
            with self.subTest(m[:30]):
                self.assertEqual(self.lancer("pourquoi", "--ia", "--faits", "-", entree=m), {"ia": False})
        self.assertEqual(self.appels_ia(), [])
        (self.racine / ".config/nc/reglages.conf").write_text("IA_MODE=non\n")
        self.assertEqual(self.lancer("pourquoi", "--ia", "--faits", "-", entree=json.dumps(faits)), {"ia": False})
        self.assertEqual(self.appels_ia(), [])

    def test_ia_mode_lu_comme_nc_ia(self):
        """La dernière valeur gagne, espaces et guillemets compris (nc-ia lit le fichier de la même façon)."""
        self.ecran(100)
        self.ia({"phrases": "Oui.", "ordre": []})
        cas = (("IA_MODE=non\nIA_MODE=auto\n", True), ("IA_MODE=auto\nIA_MODE=non\n", False),
               (' IA_MODE = "non" \n', False), ("IA_MODE=non # x\n", True), ("# IA_MODE=non\n", True), ("", True))
        for texte, permise in cas:
            with self.subTest(texte):
                (self.racine / ".config/nc/reglages.conf").write_text(texte)
                self.assertEqual(self.lancer("pourquoi", "--ia")["ia"], permise)

    def pids_vivants(self, fichier):
        """Les pids notés par le faux nc-ia (lui et son fils) qui existent encore (un zombie compte comme mort)."""
        vivants = []
        for pid in fichier.read_text().split():
            try:
                os.kill(int(pid), 0)
                etat = Path(f"/proc/{pid}/stat").read_text()
                if etat[etat.rfind(")") + 2] != "Z":
                    vivants.append(pid)
            except (ProcessLookupError, FileNotFoundError, IndexError):
                pass
        return vivants

    def attendre(self, condition, delai=6):
        fin = time.monotonic() + delai
        while time.monotonic() < fin:
            if condition():
                return True
            time.sleep(0.05)
        return condition()

    FAUX_LENT = """trap 'echo termine >> {journal}; exit 0' TERM
echo $$ >> {pids}
while :; do :; done"""

    def test_sigterm_a_nc_conso_pas_de_nc_ia_orphelin(self):
        self.ecran(100)
        pids = self.racine / "pids"
        self.ia(corps=self.FAUX_LENT.format(pids=pids, journal=self.journal))
        env = dict(os.environ, **self.env)
        p = subprocess.Popen([sys.executable, str(SCRIPT), "pourquoi", "--ia"], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.addCleanup(lambda: p.poll() is None and p.kill())
        self.assertTrue(self.attendre(lambda: pids.exists() and pids.read_text().strip()), "nc-ia n'a pas démarré")
        time.sleep(0.3)
        p.send_signal(signal.SIGTERM)
        p.communicate(timeout=10)
        self.assertTrue(self.attendre(lambda: not self.pids_vivants(pids), 4), "nc-ia est resté : " + str(self.pids_vivants(pids)))
        self.assertIn("termine", self.journal.read_text(), "arrêté poliment (SIGTERM), pas tué")
        # Même chose avec SIGHUP
        pids.unlink()
        self.journal.unlink()
        p = subprocess.Popen([sys.executable, str(SCRIPT), "pourquoi", "--ia"], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.addCleanup(lambda: p.poll() is None and p.kill())
        self.assertTrue(self.attendre(lambda: pids.exists() and pids.read_text().strip()))
        time.sleep(0.3)
        p.send_signal(signal.SIGHUP)
        p.communicate(timeout=10)
        self.assertTrue(self.attendre(lambda: not self.pids_vivants(pids), 4))

    def delai_court(self, corps):
        """appeler_ia avec un délai de 0,4 s sur ce faux nc-ia ; (durée, résultat)."""
        self.ecran(100)
        pids = self.racine / "pids"
        self.ia(corps=corps.format(pids=pids, journal=self.journal))
        m = self.charger()
        with patch.dict(os.environ, self.env, clear=True), patch.object(m, "DELAI_IA", 0.4):
            t0 = time.monotonic()
            r = m.appeler_ia({"causes": [{"id": "luminosite", "poids": 5, "unite": "score", "action": None}], "actions": [], "batterie": {}})
            return time.monotonic() - t0, r, pids

    def test_delai_arret_poli_puis_kill_et_aucun_processus_restant(self):
        # Il écoute SIGTERM : fermeture polie, son nettoyage a tourné, on n'attend pas 2 s
        duree, r, pids = self.delai_court(self.FAUX_LENT)
        self.assertIsNone(r)
        self.assertLess(duree, 1.8)
        self.assertIn("termine", self.journal.read_text())
        self.assertTrue(self.attendre(lambda: not self.pids_vivants(pids), 3), str(self.pids_vivants(pids)))
        # Il ignore SIGTERM : SIGKILL seulement après 2 s, et plus rien ne reste
        self.journal.unlink()
        pids.unlink()
        duree, r, pids = self.delai_court("echo $$ >> {pids}\ntrap '' TERM\nwhile :; do :; done")
        self.assertIsNone(r)
        self.assertGreaterEqual(duree, 2.3, "SIGKILL trop tôt : le nettoyage de nc-ia ne peut pas tourner")
        self.assertTrue(self.attendre(lambda: not self.pids_vivants(pids), 3), str(self.pids_vivants(pids)))

    def test_ia_coupee_aucun_appel(self):
        self.tout_allume()
        self.ia({"phrases": "Ne doit pas apparaître.", "ordre": ["luminosite_baisser"]})
        (self.racine / ".config/nc/reglages.conf").write_text('LANGUE=fr\nIA_MODE="non"\n')
        fixe = self.lancer("pourquoi", "--json")
        f = self.lancer("pourquoi", "--ia")
        self.assertEqual(f, fixe)
        self.assertFalse(f["ia"])
        self.assertEqual(self.appels_ia(), [], "IA_MODE=non : nc-ia n'est pas appelé")
        # Réactivée : il est appelé
        (self.racine / ".config/nc/reglages.conf").write_text("IA_MODE=auto\n")
        self.assertTrue(self.lancer("pourquoi", "--ia")["ia"])
        self.assertEqual(len(self.appels_ia()), 1)

    def test_la_pause_economie_ne_bloque_pas_un_clic(self):
        """IA_ECONOMIE (pause de l'IA d'arrière-plan en Économie sur batterie) vise nc-ia --fond : ici c'est un clic."""
        self.tout_allume()
        self.profil("power-saver")
        self.ecran(100)
        (self.racine / ".config/nc/reglages.conf").write_text("IA_ECONOMIE=oui\n")
        self.ia({"phrases": "Réponse.", "ordre": []})
        self.assertTrue(self.lancer("pourquoi", "--ia")["ia"])
        self.assertNotIn("--fond", self.appels_ia()[0])

    def test_rien_a_expliquer_pas_d_appel(self):
        self.ia({"phrases": "Ne doit pas apparaître.", "ordre": []})
        f = self.lancer("pourquoi", "--ia")
        self.assertEqual((f["causes"], f["ia"]), ([], False))
        self.assertEqual(self.appels_ia(), [])

    def test_sans_batterie_aucun_appel(self):
        self.tout_allume()
        shutil.rmtree(self.f.sys / "class/power_supply/BAT0")
        self.ia({"phrases": "Non.", "ordre": []})
        self.assertFalse(self.lancer("pourquoi", "--ia")["sur_batterie"])
        self.assertEqual(self.appels_ia(), [])

    def test_l_ia_ne_recoit_que_des_faits(self):
        """Noms d'applis, chiffres, ids : pas de ligne de commande, de pid, de chemin ni de commande à lancer."""
        self.rtx()
        self.ecran(100)
        self.f.processus(100, "firefox", 10, "/usr/bin/firefox\0--token=SECRET123\0", exe="/usr/bin/firefox")
        self.f.processeur(100, 1000)
        self.ia({"phrases": "Ok.", "ordre": []})
        m = self.charger()

        def dormir(_):
            self.f.processus(100, "firefox", 90, "/usr/bin/firefox\0--token=SECRET123\0", exe="/usr/bin/firefox")
            self.f.processeur(180, 1100)
        with patch.dict(os.environ, self.env, clear=True), patch.object(m.os, "getpid", return_value=4_000_000), \
                patch.object(m.time, "sleep", dormir):
            with contextlib.redirect_stdout(io.StringIO()):
                m.pourquoi(True)
        q = self.entree.read_text()
        self.assertIn("Firefox", q)
        self.assertIn('"id": "rtx"', q)
        self.assertIn('"luminosite_baisser"', q)
        for interdit in ("SECRET123", "--token", "/usr/bin", "4242", "555", "--oui", "gdbus", "nc-brightness",
                         "power-saver", str(self.racine), "/home/"):
            self.assertNotIn(interdit, q)


ENTETE_QML = """import QtQuick
import QtQuick.Window
import Quickshell
"""
OUTILS_QML = """
    function verifier(ok, message) { if (!ok) { console.error(message); Qt.exit(2) } return ok }
    function trouver(item, nom) { if (item.objectName === nom) return item; for (var i = 0; i < item.children.length; i++) { var r = trouver(item.children[i], nom); if (r) return r } return null }
    function tous(item, nom, l) { l = l || []; if (item.objectName === nom) l.push(item); for (var i = 0; i < item.children.length; i++) tous(item.children[i], nom, l); return l }
    // Le vrai bouton « pourquoi-confirmer » de la confirmation visible : son MouseArea émet clicked
    function cliquer(p, nom) {
        var b = tous(p, nom).filter(x => x.visible && x.width > 0)[0]
        if (!b) return false
        for (var i = 0; i < b.children.length; i++) if (b.children[i].containsMouse !== undefined) { b.children[i].clicked(null); return true }
        return false
    }
"""


def preparer_qml(d, noms, etat_extra=""):
    """Un dossier QML hors écran : les vrais fichiers, des singletons Reglages et Etat de remplacement."""
    root = Path(d)
    (root / "run").mkdir(mode=0o700)
    (root / "bin").mkdir()
    for nom in noms:
        shutil.copy2(QML / (nom + ".qml"), root)
    (root / "Reglages.qml").write_text('pragma Singleton\nimport QtQuick\nQtObject {readonly property bool en: false; readonly property bool sobre: true; function t(fr,en){return fr} function val(k,d){return d}}')
    (root / "Etat.qml").write_text('pragma Singleton\nimport QtQuick\nQtObject { readonly property string bin: "%s/bin/"\n'
                                   '  property bool branche: false; property bool enCharge: false; property int pourcent: 63\n'
                                   '  property var batterie: ({ timeToFull: 0, timeToEmpty: 4680 })\n'
                                   '  property var hauteurs: ({})\n'
                                   '  function annoncerHauteur(nom, h) { var t = Object.assign({}, hauteurs); t[nom] = Math.round(h); hauteurs = t }\n%s }' % (d, etat_extra))
    (root / "qmldir").write_text("\n".join(("singleton " if n in ("Couleurs", "Reglages", "Etat") else "") + n + " 1.0 " + n + ".qml"
                                           for n in tuple(noms) + ("Reglages", "Etat")))
    return root


def lancer_qs(root, d, delai=25):
    env = dict(os.environ, HOME=d, QT_QPA_PLATFORM="offscreen", QT_QUICK_BACKEND="software",
               XDG_RUNTIME_DIR=str(root / "run"), XDG_CACHE_HOME=str(root / ".cache"))
    env.pop("WAYLAND_DISPLAY", None)
    r = subprocess.run(["qs", "--no-color", "-p", str(root / "shell.qml")], env=env, capture_output=True, text=True, timeout=delai)
    sortie = r.stdout + r.stderr
    for erreur in ("ReferenceError", "TypeError", "Cannot assign", "Binding loop", "is not a type", "Unable to assign"):
        assert erreur not in sortie, sortie
    return r, sortie


@unittest.skipUnless(shutil.which("qs"), "Quickshell requis")
class Carte(unittest.TestCase):
    """Pourquoi.qml chargée hors écran avec le vrai qs : visible seulement en décharge, faits puis IA (qui ne touche pas
    aux actions affichées), texte brut, confirmation avant toute commande, clic sur le vrai bouton, action qui va au
    bout page cachée, rien de lancé après, résultats périmés ignorés."""

    def test_carte(self):
        with tempfile.TemporaryDirectory(prefix="nc-pourquoi-qml-") as d:
            root = preparer_qml(d, ("Pourquoi", "Texte", "Ico", "Module", "Couleurs"))
            faits = {"sur_batterie": True, "langue": "fr", "ia": False, "phrases": "Fixe <b>gras</b> https://x.fr tourne.",
                     "batterie": {"pct": 70, "watts": 10.0},
                     "causes": [{"id": "luminosite", "poids": 5, "unite": "score", "phrase": "x", "action": "luminosite_baisser"}],
                     "actions": [{"id": "luminosite_baisser", "libelle": "Luminosité 100 % → 60 %", "detail": "",
                                  "commande": [str(root / "bin/action"), "un", "deux"]},
                                 {"id": "bluetooth_couper", "libelle": "Couper le Bluetooth", "detail": "Tu peux le rallumer quand tu veux",
                                  "commande": [str(root / "bin/action"), "bt"]}]}
            # L'IA ne rend que le texte et l'ordre ; une commande « inventée » dans sa réponse n'est jamais utilisée
            ia = {"ia": True, "phrases": "Récit de l'IA <i>brut</i>.", "ordre": ["bluetooth_couper", "inconnue", "luminosite_baisser"],
                  "actions": [{"id": "x", "libelle": "pirate", "detail": "x", "commande": ["rm", "-rf", "/"]}]}
            (root / "faits.json").write_text(json.dumps(faits))
            (root / "ia.json").write_text(json.dumps(ia))
            (root / "bin/nc-conso").write_text(textwrap.dedent('''\
                #!/bin/sh
                echo "$1 $2 $3 $4 langue=$NC_LANGUE" | tr -s ' ' >> "$HOME/appels"
                case "$2" in
                  --json) cat "$HOME/faits.json" ;;
                  --ia) cat > "$HOME/faits-recu"; sleep 1; cat "$HOME/ia.json" ;;
                esac
                '''))
            (root / "bin/action").write_text('#!/bin/sh\necho "debut $*" >> "$HOME/appels"\nsleep 2\necho "fin $*" >> "$HOME/appels"\n')
            for n in ("nc-conso", "action"):
                (root / "bin" / n).chmod(0o755)
            (root / "shell.qml").write_text(ENTETE_QML + textwrap.dedent('''\
                ShellRoot {
                    property int etape: 0
                    property int attente: 0
                    property var actionsAffichees: null
                ''') + OUTILS_QML + textwrap.dedent('''\
                    Window {
                        id: w; visible: true; width: 432; height: 600; color: Couleurs.fond
                        Pourquoi { id: p; x: 16; y: 16; width: 378; actif: false }
                    }
                    Timer { interval: 100; running: true; repeat: true; onTriggered: {
                        // Pas en décharge : ni bouton ni place
                        if (etape === 0) {
                            verifier(!p.visible, "visible hors décharge")
                            p.actif = true; etape++ }
                        else if (etape === 1) {
                            verifier(p.visible, "invisible en décharge")
                            verifier(trouver(p, "pourquoi-bouton").visible, "bouton absent")
                            verifier(!trouver(p, "pourquoi-texte").visible, "réponse avant le clic")
                            p.ouvrir(); etape++ }
                        // Les faits tout de suite, puis l'IA qui remplace le texte
                        else if (etape === 2) {
                            if (!p.res) return
                            var t = trouver(p, "pourquoi-texte")
                            verifier(t.textFormat === Text.PlainText, "texte pas en texte brut")
                            verifier(t.text === "Fixe <b>gras</b> https://x.fr tourne.", "phrases fixes : " + t.text)
                            verifier(tous(p, "pourquoi-action").length === 2, "deux actions attendues")
                            actionsAffichees = JSON.stringify(p.res.actions)
                            // Un résultat d'une génération périmée est ignoré
                            var avant = p.res
                            p.phase = "faits"
                            p.recu(JSON.stringify(Object.assign({}, faitsVieux())), p.gen - 1)
                            verifier(p.res === avant, "un vieux résultat a été pris")
                            p.phase = "ia"
                            etape++ }
                        else if (etape === 3) {
                            if (!p.res.ia) return
                            var t = trouver(p, "pourquoi-texte")
                            verifier(t.text === "Récit de l'IA <i>brut</i>.", "texte de l'IA : " + t.text)
                            verifier(t.textFormat === Text.PlainText, "IA : texte pas brut")
                            var ids = tous(p, "pourquoi-action").map(x => x.modelData.id)
                            verifier(ids.join() === "bluetooth_couper,luminosite_baisser", "ordre de l'IA : " + ids)
                            verifier(JSON.stringify(p.res.actions.slice().sort((a, b) => a.id < b.id ? -1 : 1)) === JSON.stringify(JSON.parse(actionsAffichees).sort((a, b) => a.id < b.id ? -1 : 1)), "l'IA a changé les actions")
                            verifier(tous(p, "pourquoi-confirmation").filter(x => x.visible).length === 0, "confirmation avant le clic")
                            // Un clic ouvre la confirmation, rien n'est lancé
                            p.choix = "luminosite_baisser"; attente = 0; etape++ }
                        else if (etape === 4) {
                            if (++attente < 5) return
                            verifier(tous(p, "pourquoi-confirmation").filter(x => x.visible).length === 1, "une seule confirmation attendue")
                            verifier(p.etatAction === "", "action lancée sans confirmation")
                            // Annuler (le vrai bouton) : la confirmation disparaît, toujours rien de lancé
                            verifier(cliquer(p, "pourquoi-annuler"), "bouton Annuler introuvable")
                            verifier(p.choix === "" && p.etatAction === "", "annuler a lancé ou gardé le choix")
                            // Les actions changent pendant une confirmation (nouveau résultat de --json) : elle se ferme
                            p.choix = "luminosite_baisser"
                            var autre = JSON.parse(JSON.stringify(p.res))
                            autre.actions.filter(a => a.id === "luminosite_baisser")[0].commande = ["/bin/autre"]
                            p.phase = "faits"; p.recu(JSON.stringify(autre), p.gen); p.phase = "ia"
                            verifier(p.choix === "", "la confirmation est restée ouverte alors que l'action a changé")
                            p.res = Object.assign({}, p.res, { actions: JSON.parse(actionsAffichees).reverse() })
                            p.choix = "luminosite_baisser"; attente = 0; etape++ }
                        // Confirmer : le vrai bouton ; l'action part (2 s), la page est cachée pendant qu'elle tourne
                        else if (etape === 5) {
                            if (++attente < 3) return
                            verifier(cliquer(p, "pourquoi-confirmer"), "bouton Confirmer introuvable")
                            verifier(p.etatAction === "encours", "l'action n'est pas partie : " + p.etatAction)
                            attente = 0; etape++ }
                        else if (etape === 6) {
                            if (++attente < 5) return
                            p.actif = false; attente = 0; etape++ }
                        else if (etape === 7) {
                            verifier(!p.visible, "visible sur secteur")
                            verifier(!p.ouvert && p.res === null, "pas remis à zéro")
                            if (++attente < 40) return          // 4 s : assez pour que l'action finisse seule
                            verifier(p.etatAction === "", "état affiché après coup : " + p.etatAction)
                            Qt.quit() } } }
                    function faitsVieux() { var o = JSON.parse(JSON.stringify(p.res)); o.phrases = "vieux"; return o }
                    Timer { interval: 16000; running: true; onTriggered: Qt.exit(9) }
                }'''))
            r, sortie = lancer_qs(root, d)
            self.assertEqual(r.returncode, 0, sortie)
            appels = (root / "appels").read_text().splitlines()
            self.assertEqual(appels[:2], ["pourquoi --json langue=fr", "pourquoi --ia --faits - langue=fr"])
            self.assertEqual((appels.count("debut un deux"), appels.count("fin un deux")), (1, 1),
                             "la commande de la liste, une fois, jusqu'au bout malgré la page cachée : " + str(appels))
            self.assertEqual(len([a for a in appels if "bt" in a.split()]), 0, "une action non confirmée a été lancée")
            # Après l'action et la page cachée : aucune relecture, aucun appel à l'IA
            self.assertEqual([a for a in appels[appels.index("debut un deux"):] if a.startswith("pourquoi")], [], str(appels))
            recu = json.loads((root / "faits-recu").read_text())
            self.assertEqual(sorted(a["id"] for a in recu["actions"]), ["bluetooth_couper", "luminosite_baisser"])

    def test_reouverture_pendant_une_action_pas_de_deuxieme_action(self):
        """Page cachée puis rouverte pendant qu'une action tourne : l'état reste « en cours », une 2e confirmation ne
        lance rien, et « C'est fait. » n'apparaît qu'à la fin de la première."""
        with tempfile.TemporaryDirectory(prefix="nc-pourquoi-reouv-") as d:
            root = preparer_qml(d, ("Pourquoi", "Texte", "Ico", "Module", "Couleurs"))
            faits = {"sur_batterie": True, "langue": "fr", "ia": False, "phrases": "Fixe.", "batterie": None,
                     "causes": [{"id": "luminosite", "poids": 5, "unite": "score", "phrase": "x", "action": "luminosite_baisser"}],
                     "actions": [{"id": "luminosite_baisser", "libelle": "Luminosité 100 % → 60 %", "detail": "d",
                                  "commande": [str(root / "bin/action"), "un"]}]}
            (root / "faits.json").write_text(json.dumps(faits))
            (root / "bin/nc-conso").write_text('#!/bin/sh\ncase "$2" in --json) cat "$HOME/faits.json" ;; *) printf \'{"ia": false}\' ;; esac\n')
            (root / "bin/action").write_text('#!/bin/sh\necho "debut $*" >> "$HOME/appels"\nsleep 2\necho "fin $*" >> "$HOME/appels"\n')
            for n in ("nc-conso", "action"):
                (root / "bin" / n).chmod(0o755)
            (root / "shell.qml").write_text(ENTETE_QML + textwrap.dedent('''\
                ShellRoot {
                    property int etape: 0
                    property int attente: 0
                ''') + OUTILS_QML + textwrap.dedent('''\
                    Window {
                        id: w; visible: true; width: 432; height: 600; color: Couleurs.fond
                        Pourquoi { id: p; x: 16; y: 16; width: 378; actif: true }
                    }
                    Timer { interval: 100; running: true; repeat: true; onTriggered: {
                        if (etape === 0) { p.ouvrir(); etape++ }
                        else if (etape === 1) {
                            if (!p.res) return
                            p.choix = "luminosite_baisser"; attente = 0; etape++ }
                        else if (etape === 2) {
                            if (++attente < 3) return
                            verifier(cliquer(p, "pourquoi-confirmer"), "Confirmer introuvable")
                            verifier(p.etatAction === "encours", "pas partie")
                            p.actif = false; attente = 0; etape++ }
                        // Rouverte pendant l'action
                        else if (etape === 3) {
                            if (++attente < 3) return
                            p.actif = true; p.ouvrir(); attente = 0; etape++ }
                        else if (etape === 4) {
                            if (!p.res) return
                            verifier(p.etatAction === "encours", "état remis à zéro pendant l'action : " + p.etatAction)
                            verifier(tous(p, "pourquoi-etat").filter(x => x.visible && x.text.indexOf("fait") >= 0).length === 0, "« C'est fait » trop tôt")
                            // Une 2e confirmation : rien ne part (les boutons sont désactivés, la commande refusée)
                            p.lancerAction(p.res.actions[0])
                            p.choix = "luminosite_baisser"
                            cliquer(p, "pourquoi-confirmer")
                            verifier(p.etatAction === "encours", "2e action acceptée : " + p.etatAction)
                            etape++ }
                        else if (etape === 5) {
                            if (p.etatAction !== "fait") return
                            Qt.quit() } } }
                    Timer { interval: 14000; running: true; onTriggered: Qt.exit(9) }
                }'''))
            r, sortie = lancer_qs(root, d)
            self.assertEqual(r.returncode, 0, sortie)
            appels = (root / "appels").read_text().splitlines()
            self.assertEqual((appels.count("debut un"), appels.count("fin un")), (1, 1), str(appels))

    def test_hauteur_de_la_page_ouverte(self):
        """La page Charge entière, carte ouverte avec le pire cas (nom d'appli long, 3 actions, 2e confirmation, ligne
        d'état) reste sous les 580 px de l'île ; les hauteurs mesurées sont affichées dans le message en cas d'échec."""
        with tempfile.TemporaryDirectory(prefix="nc-pourquoi-haut-") as d:
            noms = ("Charge", "Pourquoi", "Texte", "Ico", "Module", "Couleurs")
            root = preparer_qml(d, noms)
            long_ = "Un-nom-d-application-vraiment-tres-long-et-sans-espace"
            phrases = " ".join(["Une phrase assez longue pour prendre de la place dans la carte de l'île."] * 5)
            faits = {"sur_batterie": True, "langue": "fr", "ia": False, "phrases": phrases, "batterie": {"pct": 70, "watts": 10.0},
                     "causes": [{"id": "rtx", "poids": 8, "unite": "score", "phrase": "x", "action": "rtx_relancer"}],
                     "actions": [{"id": "rtx_relancer", "libelle": "Relancer %s sur la carte intégrée" % long_,
                                  "detail": "%s sera fermé puis rouvert (enregistre ton travail)" % long_, "commande": ["/bin/true"]},
                                 {"id": "profil_economie", "libelle": "Passer en Économie", "detail": "", "commande": ["/bin/true"]},
                                 {"id": "luminosite_baisser", "libelle": "Luminosité 100 % → 60 %", "detail": "", "commande": ["/bin/true"]}]}
            mesure = {"batterie": {"statut": "Discharging", "pct": 63, "watts": 12.3, "restant": 4680},
                      "top": [{"nom": "Firefox", "pct": 8.2, "watts": 4.1}, {"nom": "Code", "pct": 4.0, "watts": 2.0},
                             {"nom": "Discord", "pct": 2.1, "watts": 1.0}, {"nom": "Kitty", "pct": 0.4, "watts": 0.2},
                             {"nom": "Hyprland", "pct": 0.3, "watts": 0.1}],
                      "rtx": {"etat": "allumee", "cause": "Firefox"},
                      "sante": {"garde": 92, "cycles": 143, "limite": {"active": True, "seuil": 80}}}
            (root / "faits.json").write_text(json.dumps(faits))
            (root / "mesure.json").write_text(json.dumps(mesure))
            (root / "bin/nc-conso").write_text(textwrap.dedent('''\
                #!/bin/sh
                case "$2" in
                  --json) cat "$HOME/faits.json" ;;
                  --ia) printf '{"ia": false}' ;;
                  *) cat "$HOME/mesure.json"; echo; sleep 3 ;;
                esac
                '''))
            (root / "bin/nc-conso").chmod(0o755)
            (root / "shell.qml").write_text(ENTETE_QML + textwrap.dedent('''\
                ShellRoot {
                    property int etape: 0
                    property int attente: 0
                    property var page: null
                ''') + OUTILS_QML + textwrap.dedent('''\
                    Window {
                        id: w; visible: true; width: 432; height: 600; color: Couleurs.fond
                        Item { x: 16; y: 16; width: 378; height: 560; Loader { id: chargeur; anchors.fill: parent; source: "Charge.qml" } }
                    }
                    function bilan() { return "page fermée " + fermee + " px, carte ouverte " + Etat.hauteurs.charge + " px (+32 de marge, limite 580)" }
                    property real fermee: 0
                    Timer { interval: 100; running: true; repeat: true; onTriggered: {
                        if (etape === 0) { if (chargeur.status !== Loader.Ready) return; page = chargeur.item; etape++ }
                        else if (etape === 1) {
                            var q = trouver(page, "pourquoi")
                            if (!q || !q.visible) { return }
                            fermee = Etat.hauteurs.charge
                            verifier(fermee + 32 <= 580, "page fermée trop haute : " + fermee)
                            q.ouvrir(); attente = 0; etape++ }
                        else if (etape === 2) {
                            var q = trouver(page, "pourquoi")
                            if (!q.res) return
                            // Pire cas : première action en confirmation + la ligne d'état d'une action d'avant
                            q.etatAction = "echec"; q.derniereAction = "rtx_relancer"
                            q.choix = "rtx_relancer"
                            verifier(q.etatAction === "", "la ligne d'état doit disparaître à l'ouverture d'une confirmation")
                            q.etatAction = "echec"            // et si elle revenait quand même, la page tient
                            attente = 0; etape++ }
                        else if (etape === 3) {
                            if (++attente < 5) return
                            verifier(Etat.hauteurs.charge + 32 <= 580, bilan())
                            console.log("HAUTEURS " + bilan())
                            Qt.quit() } } }
                    Timer { interval: 15000; running: true; onTriggered: Qt.exit(9) }
                }'''))
            r, sortie = lancer_qs(root, d)
            self.assertEqual(r.returncode, 0, sortie)
            hauteurs = [l for l in sortie.splitlines() if "HAUTEURS" in l]
            self.assertTrue(hauteurs, sortie)
            print("\n" + hauteurs[0].strip())


class Source(unittest.TestCase):
    """Garde-fous lus dans le source."""

    def test_pas_de_composant_interne_dans_charge_et_pourquoi(self):
        for nom in ("Charge.qml", "Pourquoi.qml"):
            t = (QML / nom).read_text()
            self.assertNotRegex(t, r"(?m)^\s*component\s+\w+\s*:", nom + " : jamais de nouveau `component` interne")
        # Le bouton n'existe que sur batterie en décharge
        self.assertIn("actif: charge.decharge", (QML / "Charge.qml").read_text())
        self.assertIn("visible: actif", (QML / "Pourquoi.qml").read_text())

    def test_texte_de_l_ia_en_texte_brut(self):
        t = (QML / "Pourquoi.qml").read_text()
        self.assertIn("textFormat: Text.PlainText", t)
        self.assertNotIn("Text.RichText", t)
        self.assertNotIn("Text.StyledText", t)
        self.assertNotIn("Text.MarkdownText", t)
        self.assertNotIn("onLinkActivated", t)


if __name__ == "__main__":
    unittest.main()

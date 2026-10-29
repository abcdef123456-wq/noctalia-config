"""nc-energie-root, l'assistant root des profils d'énergie poussés : sous-commandes et valeurs de la liste seulement,
chemins construits par le script (jamais reçus), faux /sys (NC_ENERGIE_RACINE, lu seulement hors root) et faux outils
(NC_ENERGIE_BIN) qui notent leurs arguments ; règle sudo à commandes exactes (relue par « sudoers », validée par
visudo -cf sur un fichier temporaire)."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
ROOT = REPO / "system/nc-energie-root"
INSTALL = (REPO / "install.sh").read_text(encoding="utf-8")


def ecrire(chemin, texte):
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(texte + "\n")


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="nc-energie-root-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.sys = self.tmp / "sys"
        self.bin = self.tmp / "bin"
        self.bin.mkdir()
        self.journal = self.tmp / "journal"
        self.journal.touch()
        self.env = {"PATH": "/usr/bin:/bin", "HOME": str(self.tmp / "home"), "NC_ENERGIE_RACINE": str(self.sys),
                    "NC_ENERGIE_BIN": str(self.bin), "NC_LANGUE": "fr"}

    def faux(self, nom, corps):
        f = self.bin / nom
        f.write_text("#!/bin/sh\n" + corps)
        f.chmod(0o755)

    def noteur(self, nom, sortie=""):
        self.faux(nom, f'echo "{nom} $*" >> "{self.journal}"\n{sortie}')

    def lancer(self, *args, env=None):
        return subprocess.run([str(ROOT), *args], env=env or self.env, capture_output=True, text=True, timeout=30)

    def lire(self, chemin):
        return (self.sys / chemin).read_text().strip()

    def machine(self):
        """Un portable générique : AMD, EPP, boost, deux politiques, plateforme, NVIDIA active, Wi-Fi, USB, audio, clavier."""
        for n in (0, 1):
            p = f"devices/system/cpu/cpufreq/policy{n}"
            ecrire(self.sys / p / "energy_performance_preference", "balance_performance")
            ecrire(self.sys / p / "energy_performance_available_preferences", "performance balance_performance balance_power power")
            ecrire(self.sys / p / "cpuinfo_max_freq", "4000000")
            ecrire(self.sys / p / "scaling_max_freq", "4000000")
        ecrire(self.sys / "devices/system/cpu/cpufreq/boost", "1")
        ecrire(self.sys / "firmware/acpi/platform_profile", "balanced")
        ecrire(self.sys / "firmware/acpi/platform_profile_choices", "low-power balanced performance")
        g = self.sys / "bus/pci/devices/0000:01:00.0"
        ecrire(g / "vendor", "0x10de")
        ecrire(g / "class", "0x030000")
        ecrire(g / "power/control", "on")
        ecrire(g / "power/runtime_status", "active")
        i = self.sys / "bus/pci/devices/0000:05:00.0"
        ecrire(i / "vendor", "0x1002")
        ecrire(i / "class", "0x030000")
        ecrire(i / "power/control", "on")
        (self.sys / "class/net/wlan0/wireless").mkdir(parents=True)
        (self.sys / "class/net/eth0").mkdir(parents=True)
        # USB : un disque (réglable), une souris (interface HID : jamais touchée), un clavier (classe du périphérique)
        ecrire(self.sys / "bus/usb/devices/1-1/power/control", "on")
        ecrire(self.sys / "bus/usb/devices/1-1/1-1:1.0/bInterfaceClass", "08")
        ecrire(self.sys / "bus/usb/devices/1-2/power/control", "on")
        ecrire(self.sys / "bus/usb/devices/1-2/1-2:1.0/bInterfaceClass", "03")
        ecrire(self.sys / "bus/usb/devices/1-3/power/control", "on")
        ecrire(self.sys / "bus/usb/devices/1-3/bDeviceClass", "03")
        ecrire(self.sys / "module/snd_hda_intel/parameters/power_save", "0")
        d = self.sys / "class/leds/platform::kbd_backlight"
        ecrire(d / "brightness", "3")
        ecrire(d / "max_brightness", "2")
        self.noteur("iw")
        self.faux("nvidia-smi", f'echo "nvidia-smi $*" >> "{self.journal}"\ncase "$*" in\n  *query*) echo "50.00, 140.00" ;;\nesac\n')


class Refus(Base):
    def test_sous_commandes_et_valeurs_libres_refusees(self):
        self.machine()
        for args in [(), ("zzz",), ("epp",), ("epp", "turbo"), ("epp", "power; id"), ("epp", "../../etc"), ("epp", "-h"),
                     ("epp", "power", "extra"), ("boost", "1"), ("boost", "ON"), ("freqmax", "70"), ("freqmax", "100%"),
                     ("freqmax", "$(id)"), ("platform", "custom"), ("platform", "max-power"), ("platform", "/etc/passwd"),
                     ("nvidia-pl", "4"), ("nvidia-pl", "-1"), ("nvidia-pl", "250"), ("nvidia-pm", "off"), ("kbd", "9"),
                     ("kbd", "*"), ("wifi-ps", "yes"), ("usb-autosuspend", "auto"), ("audio-ps", "1"),
                     ("fan", "1"), ("undervolt", "-30"), ("ryzenadj", "--tctl-temp=90"), ("tdp", "65"),
                     ("ecrire", "/sys/x", "1"), ("etat", "x"), ("sudoers",), ("sudoers", "a b"), ("sudoers", "-x"),
                     ("sudoers", "alice;id")]:
            r = self.lancer(*args)
            self.assertEqual(r.returncode, 2, f"{args} doit être refusé (code 2) : {r.stdout}{r.stderr}")
        # Aucun fichier n'a bougé, aucun outil n'a été lancé
        self.assertEqual(self.lire("devices/system/cpu/cpufreq/policy0/energy_performance_preference"), "balance_performance")
        self.assertEqual(self.lire("devices/system/cpu/cpufreq/policy0/scaling_max_freq"), "4000000")
        self.assertEqual(self.journal.read_text(), "")

    def test_pas_root_hors_essai(self):
        # Sans la variable d'essai, l'assistant exige root (et ne regarde que le vrai /sys) : jamais d'écriture ici
        env = {k: v for k, v in self.env.items() if not k.startswith("NC_ENERGIE")}
        if os.getuid() == 0:
            self.skipTest("lancé en root")
        r = self.lancer("kbd", "1", env=env)
        self.assertEqual(r.returncode, 1, r.stderr)
        self.assertIn("sudo", r.stderr)

    def test_aucun_chemin_recu(self):
        source = ROOT.read_text(encoding="utf-8")
        # Chaque sous-commande valide sa valeur avant d'écrire ; aucune ne lit un chemin dans ses arguments
        self.assertNotIn('"$2"/', source.replace('ecrire "$1" "$2"', ""))
        for mot in ("fan", "pwm", "undervolt", "ryzenadj", "ryzen_smu", "render:", "hyprctl", "sudo "):
            for ligne in source.splitlines():
                if ligne.lstrip().startswith("#"):
                    continue
                self.assertNotIn(mot, ligne, f"« {mot} » n'a rien à faire ici : {ligne}")


class Ecritures(Base):
    def setUp(self):
        super().setUp()
        self.machine()

    def test_epp_sur_toutes_les_politiques(self):
        r = self.lancer("epp", "power")
        self.assertEqual(r.returncode, 0, r.stderr)
        for n in (0, 1):
            self.assertEqual(self.lire(f"devices/system/cpu/cpufreq/policy{n}/energy_performance_preference"), "power")

    def test_epp_indisponible_sur_ce_pc(self):
        ecrire(self.sys / "devices/system/cpu/cpufreq/policy0/energy_performance_available_preferences", "performance")
        ecrire(self.sys / "devices/system/cpu/cpufreq/policy1/energy_performance_available_preferences", "performance")
        r = self.lancer("epp", "power")
        self.assertEqual(r.returncode, 3, r.stderr)
        self.assertEqual(self.lire("devices/system/cpu/cpufreq/policy0/energy_performance_preference"), "balance_performance")

    def test_boost_amd_et_intel(self):
        self.assertEqual(self.lancer("boost", "off").returncode, 0)
        self.assertEqual(self.lire("devices/system/cpu/cpufreq/boost"), "0")
        self.assertEqual(self.lancer("boost", "on").returncode, 0)
        self.assertEqual(self.lire("devices/system/cpu/cpufreq/boost"), "1")
        (self.sys / "devices/system/cpu/cpufreq/boost").unlink()
        r = self.lancer("boost", "off")
        self.assertEqual(r.returncode, 3, "ni boost ni no_turbo : rien à régler")
        ecrire(self.sys / "devices/system/cpu/intel_pstate/no_turbo", "0")
        self.assertEqual(self.lancer("boost", "off").returncode, 0)
        self.assertEqual(self.lire("devices/system/cpu/intel_pstate/no_turbo"), "1")
        self.assertEqual(self.lancer("boost", "on").returncode, 0)
        self.assertEqual(self.lire("devices/system/cpu/intel_pstate/no_turbo"), "0")

    def test_freqmax_en_pourcentage_de_cpuinfo(self):
        for pct, khz in (("80", "3200000"), ("60", "2400000"), ("100", "4000000")):
            self.assertEqual(self.lancer("freqmax", pct).returncode, 0)
            self.assertEqual(self.lire("devices/system/cpu/cpufreq/policy1/scaling_max_freq"), khz)
            self.assertEqual(self.lire("devices/system/cpu/cpufreq/policy1/cpuinfo_max_freq"), "4000000", "cpuinfo jamais touché")

    def test_platform_seulement_si_le_noyau_le_propose(self):
        self.assertEqual(self.lancer("platform", "low-power").returncode, 0)
        self.assertEqual(self.lire("firmware/acpi/platform_profile"), "low-power")
        r = self.lancer("platform", "quiet")           # dans la liste de l'assistant, mais pas dans platform_profile_choices
        self.assertEqual(r.returncode, 3, r.stderr)
        self.assertEqual(self.lire("firmware/acpi/platform_profile"), "low-power")

    def test_nvidia_pm_seulement_la_carte_nvidia(self):
        self.assertEqual(self.lancer("nvidia-pm", "auto").returncode, 0)
        self.assertEqual(self.lire("bus/pci/devices/0000:01:00.0/power/control"), "auto")
        self.assertEqual(self.lire("bus/pci/devices/0000:05:00.0/power/control"), "on", "la carte AMD n'est pas touchée")

    def test_nvidia_pl_paliers_et_carte_endormie(self):
        for palier, watts in (("0", "50"), ("1", "80"), ("2", "110"), ("3", "140")):
            self.journal.write_text("")
            self.assertEqual(self.lancer("nvidia-pl", palier).returncode, 0)
            self.assertIn(f"nvidia-smi -pl {watts}", self.journal.read_text())
        # Carte endormie : jamais réveillée, nvidia-smi n'est même pas lancé
        self.journal.write_text("")
        ecrire(self.sys / "bus/pci/devices/0000:01:00.0/power/runtime_status", "suspended")
        r = self.lancer("nvidia-pl", "1")
        self.assertEqual(r.returncode, 3, r.stderr)
        self.assertEqual(self.journal.read_text(), "")

    def test_wifi_nom_pris_dans_sys(self):
        self.assertEqual(self.lancer("wifi-ps", "on").returncode, 0)
        self.assertEqual(self.journal.read_text().splitlines(), ["iw dev wlan0 set power_save on"])

    def test_usb_jamais_les_peripheriques_de_saisie(self):
        self.assertEqual(self.lancer("usb-autosuspend", "on").returncode, 0)
        self.assertEqual(self.lire("bus/usb/devices/1-1/power/control"), "auto")
        self.assertEqual(self.lire("bus/usb/devices/1-2/power/control"), "on", "souris (interface HID)")
        self.assertEqual(self.lire("bus/usb/devices/1-3/power/control"), "on", "clavier (classe 03)")
        self.assertEqual(self.lancer("usb-autosuspend", "off").returncode, 0)
        self.assertEqual(self.lire("bus/usb/devices/1-1/power/control"), "on")

    def test_usb_jamais_audio_impression_bluetooth(self):
        """Relecture : un casque USB (01), une imprimante (07) ou l'adaptateur Bluetooth (e0, souris et casques sans fil)
        ne sont jamais mis en veille, au niveau du périphérique ou d'une interface."""
        for nom, f, classe in (("1-4", "bDeviceClass", "e0"), ("1-5", "1-5:1.0/bInterfaceClass", "01"),
                               ("1-6", "1-6:1.0/bInterfaceClass", "07"), ("1-7", "1-7:1.1/bInterfaceClass", "E0")):
            ecrire(self.sys / f"bus/usb/devices/{nom}/power/control", "on")
            ecrire(self.sys / f"bus/usb/devices/{nom}/{f}", classe)
        self.assertEqual(self.lancer("usb-autosuspend", "on").returncode, 0)
        for nom in ("1-4", "1-5", "1-6", "1-7"):
            self.assertEqual(self.lire(f"bus/usb/devices/{nom}/power/control"), "on", nom)
        self.assertEqual(self.lire("bus/usb/devices/1-1/power/control"), "auto")

    def test_audio_et_clavier(self):
        self.assertEqual(self.lancer("audio-ps", "on").returncode, 0)
        self.assertEqual(self.lire("module/snd_hda_intel/parameters/power_save"), "1")
        self.assertEqual(self.lancer("audio-ps", "off").returncode, 0)
        self.assertEqual(self.lire("module/snd_hda_intel/parameters/power_save"), "0")
        self.assertEqual(self.lancer("kbd", "1").returncode, 0)
        self.assertEqual(self.lire("class/leds/platform::kbd_backlight/brightness"), "1")
        self.assertEqual(self.lancer("kbd", "3").returncode, 0)
        self.assertEqual(self.lire("class/leds/platform::kbd_backlight/brightness"), "2", "borné au maximum du clavier")

    def test_fichier_cible_absent_rien_n_est_cree(self):
        shutil.rmtree(self.sys / "module")
        shutil.rmtree(self.sys / "class/leds")
        for args in (("audio-ps", "on"), ("kbd", "1")):
            self.assertEqual(self.lancer(*args).returncode, 3)
        self.assertFalse((self.sys / "module").exists(), "l'assistant ne crée jamais de fichier")
        self.assertFalse((self.sys / "class/leds").exists())

    def test_etat_sans_ecriture(self):
        r = self.lancer("etat")
        self.assertEqual(r.returncode, 0, r.stderr)
        for attendu in ("epp=balance_performance", "boost=1", "platform=balanced", "nvidia_pm=on active", "wifi=wlan0",
                        "kbd=3/2", "audio=0", "freqmax_khz=4000000/4000000"):
            self.assertIn(attendu, r.stdout)
        self.assertEqual(r.stdout.count("usb="), 1, "un seul périphérique USB réglable")

    def test_machine_sans_rien(self):
        # Un PC sans aucune de ces capacités : tout répond « absent » (3), rien ne plante
        shutil.rmtree(self.sys)
        self.sys.mkdir()
        for args in (("epp", "power"), ("boost", "on"), ("freqmax", "60"), ("platform", "quiet"), ("nvidia-pm", "auto"),
                     ("nvidia-pl", "1"), ("wifi-ps", "on"), ("usb-autosuspend", "on"), ("audio-ps", "on"), ("kbd", "1")):
            self.assertEqual(self.lancer(*args).returncode, 3, args)
        self.assertEqual(self.lancer("etat").returncode, 0)


class PlateformePortables(Base):
    """Profil de la plateforme : choix du noyau variés (quiet sans low-power, balanced-performance sans performance),
    valeur relue après l'écriture, contrôleurs multiples et « custom »."""
    def choix(self, texte, courant="balanced"):
        ecrire(self.sys / "firmware/acpi/platform_profile_choices", texte)
        ecrire(self.sys / "firmware/acpi/platform_profile", courant)

    def controleur(self, n, nom, profil, choix="quiet balanced balanced-performance"):
        d = self.sys / f"class/platform-profile/platform-profile-{n}"
        ecrire(d / "name", nom)
        ecrire(d / "profile", profil)
        ecrire(d / "choices", choix)

    def test_quiet_sans_low_power(self):
        self.choix("quiet balanced balanced-performance")
        self.assertEqual(self.lancer("platform", "low-power").returncode, 3)       # ce PC ne l'a pas : rien n'est écrit
        self.assertEqual(self.lire("firmware/acpi/platform_profile"), "balanced")
        self.assertEqual(self.lancer("platform", "quiet").returncode, 0)
        self.assertEqual(self.lire("firmware/acpi/platform_profile"), "quiet")

    def test_balanced_performance_sans_performance(self):
        self.choix("quiet balanced balanced-performance")
        r = self.lancer("platform", "performance")
        self.assertEqual(r.returncode, 3)
        self.assertIn("choix du noyau", r.stderr)
        self.assertEqual(self.lancer("platform", "balanced-performance").returncode, 0)
        self.assertEqual(self.lire("firmware/acpi/platform_profile"), "balanced-performance")

    def test_aucun_profil_compatible(self):
        self.choix("custom", "custom")
        for v in ("low-power", "quiet", "cool", "balanced", "balanced-performance", "performance"):
            self.assertEqual(self.lancer("platform", v).returncode, 3, v)
        self.assertEqual(self.lire("firmware/acpi/platform_profile"), "custom")

    def test_ecriture_refusee(self):
        self.choix("quiet balanced performance")
        f = self.sys / "firmware/acpi/platform_profile"
        f.chmod(0o444)
        r = self.lancer("platform", "quiet")
        self.assertEqual(r.returncode, 1, r.stderr)
        self.assertIn("refusée", r.stderr)
        self.assertEqual(self.lire("firmware/acpi/platform_profile"), "balanced")

    def test_valeur_relue_differente_jamais_un_faux_succes(self):
        self.choix("quiet balanced performance")
        # un service réécrit le profil juste après l'écriture (le faux « sleep » est appelé entre l'écriture et la relecture)
        self.faux("sleep", f'echo balanced > "{self.sys}/firmware/acpi/platform_profile"')
        r = self.lancer("platform", "performance")
        self.assertEqual(r.returncode, 4, r.stderr)
        self.assertIn("relu", r.stderr)
        self.assertIn("balanced", r.stderr)

    def test_service_qui_reecrit_en_retard(self):
        """Un service détaché (tlp-pd) réécrit un instant après l'écriture : la relecture bornée le voit (code 4)."""
        self.choix("quiet balanced performance")
        compteur = self.tmp / "n"
        compteur.write_text("0")
        self.faux("sleep", f'n=$(cat "{compteur}"); n=$((n+1)); echo $n > "{compteur}"\n'
                           f'[ "$n" = 2 ] && echo balanced > "{self.sys}/firmware/acpi/platform_profile"\nexit 0')
        r = self.lancer("platform", "performance")
        self.assertEqual(r.returncode, 4, r.stderr)

    def test_relecture_identique_est_un_succes(self):
        self.choix("quiet balanced performance")
        self.faux("sleep", "exit 0")
        self.assertEqual(self.lancer("platform", "performance").returncode, 0)

    def test_controleurs_qui_suivent(self):
        self.choix("quiet balanced balanced-performance")
        self.controleur(0, "acer-wmi", "balanced")
        # le noyau aligne les contrôleurs : ici le faux service le fait après l'écriture
        self.faux("sleep", f'echo quiet > "{self.sys}/class/platform-profile/platform-profile-0/profile"')
        self.assertEqual(self.lancer("platform", "quiet").returncode, 0)

    def test_controleur_en_retard_code_5(self):
        self.choix("quiet balanced balanced-performance")
        self.controleur(0, "acer-wmi", "balanced")
        self.controleur(1, "autre-pilote", "balanced")
        r = self.lancer("platform", "quiet")
        self.assertEqual(r.returncode, 5, r.stderr)        # global juste, contrôleurs différents : code à part
        self.assertIn("acer-wmi=balanced", r.stderr)
        self.assertEqual(self.lire("class/platform-profile/platform-profile-0/profile"), "balanced", "contrôleurs jamais écrits ici")

    def test_custom_remplace_par_un_profil_commun(self):
        self.choix("quiet balanced", "custom")
        self.assertEqual(self.lancer("platform", "balanced").returncode, 0)
        self.assertEqual(self.lire("firmware/acpi/platform_profile"), "balanced")
        self.assertEqual(self.lancer("platform", "custom").returncode, 2)

    def test_etat_decrit_les_controleurs(self):
        self.choix("quiet balanced balanced-performance")
        self.controleur(0, "acer-wmi", "quiet")
        self.controleur(1, "mauvais nom; $(id)", "balanced")
        r = self.lancer("etat")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("platform_choices=quiet balanced balanced-performance", r.stdout)
        self.assertIn("platform_ctl=acer-wmi|quiet|quiet balanced balanced-performance", r.stdout)
        self.assertNotIn("$(", r.stdout)
        self.assertNotIn(";", r.stdout)

    def test_pas_de_regression_hors_acer(self):
        self.machine()                                  # profils standard : low-power balanced performance
        for v in ("low-power", "balanced", "performance"):
            self.assertEqual(self.lancer("platform", v).returncode, 0, v)
            self.assertEqual(self.lire("firmware/acpi/platform_profile"), v)


class Sudoers(Base):
    def test_compte_strict(self):
        """Relecture : jamais ALL, un %groupe, des majuscules ou un tiret en tête dans la règle sudo."""
        for compte in ("ALL", "Alice", "%wheel", "-x", "a b", "a,b", "", "a:b"):
            with self.subTest(compte=compte):
                self.assertEqual(self.lancer("sudoers", compte).returncode, 2)
        self.assertEqual(self.lancer("sudoers", "alice_2-b").returncode, 0)

    def ligne(self, compte="alice"):
        r = self.lancer("sudoers", compte)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout.strip()

    def commandes(self):
        ligne = self.ligne()
        self.assertTrue(ligne.startswith("alice ALL=(root) NOPASSWD: "))
        return [c.strip() for c in ligne.split("NOPASSWD:", 1)[1].split(",")]

    def test_commandes_exactes(self):
        cmds = self.commandes()
        base = "/usr/local/bin/nc-energie-root"
        self.assertIn(f"{base} etat", cmds)
        self.assertEqual(len(cmds), len(set(cmds)))
        for c in cmds:
            self.assertRegex(c, r"^/usr/local/bin/nc-energie-root (etat|[a-z-]+ [a-z_0-9-]+)$", c)
        self.assertNotIn("*", self.ligne())
        self.assertNotIn(f"{base},", self.ligne() + ",", "pas de commande sans argument : tout serait permis")
        self.assertNotIn("sudoers", " ".join(cmds), "la sous-commande sudoers n'est pas permise par sudo")
        self.assertEqual(len(cmds), 1 + 4 + 2 + 3 + 6 + 2 + 4 + 2 + 2 + 2 + 4)

    def test_chaque_ligne_est_acceptee_par_l_assistant(self):
        # Sur un PC vide, une commande acceptée répond 3 (rien de tel ici), jamais 2 (refusée) : la règle sudo
        # n'autorise donc que ce que l'assistant comprend, et l'assistant ne comprend que ce que la règle autorise
        for c in self.commandes():
            args = c.split()[1:]
            r = self.lancer(*args)
            self.assertIn(r.returncode, (0, 3), f"{c} : {r.stdout}{r.stderr}")

    def test_install_sh_ecrit_la_ligne_de_l_assistant(self):
        self.assertIn('"$REPO/system/nc-energie-root" sudoers "$(id -un)"', INSTALL)
        self.assertIn("ask \"$(t \"L'installer ?\" \"Install it?\")\" n sensible", INSTALL.split("nc-energie-root", 1)[1])
        self.assertIn("sudo install -Dm0755 -o root -g root \"$REPO/system/nc-energie-root\" /usr/local/bin/nc-energie-root", INSTALL)
        self.assertIn("/etc/sudoers.d/nc-energie", INSTALL)
        self.assertIn('sudo visudo -cf "$regle_e.tmp"', INSTALL)          # vérifiée à sa place, en root, puis mise en service
        self.assertIn('sudo mv -f "$regle_e.tmp" "$regle_e"', INSTALL)

    def test_pas_d_installation_sans_accord(self):
        # La question est « sensible » avec NON par défaut : sans terminal, install.sh ne pose rien (sauf --oui)
        bloc = INSTALL.split("etape_energie_root() {", 1)[1].split("\n}\n", 1)[0]
        self.assertRegex(bloc, r'ask "[^\n]*" n sensible')
        self.assertNotIn("systemctl enable", bloc)
        self.assertNotIn(".service", bloc, "rien n'est réappliqué tout seul au démarrage")

    @unittest.skipUnless(shutil.which("visudo"), "visudo requis")
    def test_syntaxe_validee_par_visudo(self):
        f = self.tmp / "regle"
        f.write_text("# test\n" + self.ligne() + "\n")
        f.chmod(0o440)
        r = subprocess.run(["visudo", "-cf", str(f)], capture_output=True, text=True, timeout=20)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        f.unlink()
        f.write_text("alice ALL=(root) NOPASSWD: /usr/local/bin/nc-energie-root epp power,, boost on\n")
        r = subprocess.run(["visudo", "-cf", str(f)], capture_output=True, text=True, timeout=20)
        self.assertNotEqual(r.returncode, 0)


if __name__ == "__main__":
    unittest.main()


class ShebangRoot(unittest.TestCase):
    """Les scripts de system/ tournent en root par sudo : un « #!/usr/bin/env bash » prendrait bash dans le PATH de
    l'appelant (sudo sans secure_path) AVANT que le script fixe le sien. Shebang absolu, PATH et langue fixés."""
    def test_shebang_absolu_et_path_fixe(self):
        racine = Path(__file__).resolve().parents[1] / "system"
        scripts = [f for f in racine.rglob("*") if f.is_file() and f.read_bytes()[:2] == b"#!"]
        self.assertTrue(scripts)
        for f in scripts:
            with self.subTest(f=f.name):
                premiere = f.read_text(errors="replace").splitlines()[0]
                self.assertRegex(premiere, r"^#!/(usr/)?bin/(ba)?sh\b|^#!/usr/bin/python3 -I$")   # nc-vpn-root : Python isolé, chemin absolu
                self.assertNotIn("env", premiere)
        for nom in ("nc-energie-root", "nc-limite-charge"):
            t = (racine / nom).read_text()
            self.assertIn("PATH=/usr/sbin:/usr/bin:/sbin:/bin", t)
            self.assertIn("LC_ALL=C", t)

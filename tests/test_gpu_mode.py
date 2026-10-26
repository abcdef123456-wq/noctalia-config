"""nc-gpu-mode : mode graphique d'un portable à MUX (hybride, dédiée, sans objet) lu dans un faux /sys (NC_SYSFS),
et la bascule selon le constructeur : supergfxctl (ASUS), system76-power, attribut gsync du module legion_laptop,
sinon le BIOS (notification à bouton, redémarrage dans le BIOS seulement sur un clic) ; l'état en JSON pour l'île, et
--sans-question (confirmation déjà donnée par l'île ou nc-reglages : aucune question, la bascule puis le redémarrage
tout de suite). Toutes les commandes
extérieures sont fausses (en tête du PATH) : rien ne bascule ni ne redémarre pour de vrai."""
import json
import os
import shutil
from pathlib import Path
import subprocess
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "home/.local/bin/nc-gpu-mode"
NVIDIA, AMD = "0x10de", "0x1002"


class GpuMode(unittest.TestCase):
    def setUp(self):
        d = tempfile.TemporaryDirectory(prefix="nc-gpu-mode-")
        self.addCleanup(d.cleanup)
        self.home = Path(d.name)
        self.sys = self.home / "sys"
        self.faux = self.home / "faux"
        self.faux.mkdir()
        (self.home / ".local/bin").mkdir(parents=True)
        (self.home / ".local/bin/nc-langue").symlink_to(REPO / "home/.local/bin/nc-langue")
        self.journal = self.home / "journal"
        # Jamais de vrai systemctl, pkexec ni sudo : des faux qui notent leurs arguments
        for nom in ("systemctl", "pkexec", "sudo", "system76-power"):
            self.programme(nom, f'echo "{nom} $*" >> "$JOURNAL"')
        self.clic("")

    # --- faux système ---
    def programme(self, nom, corps):
        f = self.faux / nom
        f.write_text("#!/bin/sh\n" + corps + "\n")
        f.chmod(0o755)

    def clic(self, action):
        """Fausse notify-send : note ses arguments (une ligne JSON) et répond l'action « cliquée » (vide : fermée)."""
        f = self.faux / "notify-send"
        f.write_text("#!/usr/bin/env python3\nimport json, os, sys\n"
                     "open(os.environ['JOURNAL'], 'a').write('notify ' + json.dumps(sys.argv[1:], ensure_ascii=False) + '\\n')\n"
                     f"print({action!r})\n")
        f.chmod(0o755)

    def ecrire(self, chemin, texte):
        p = self.sys / chemin
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(texte + "\n")
        return p

    def carte(self, n, vendeur, edp=None):
        """Carte DRM cardN ; edp : None (pas de connecteur eDP), « connected » ou « disconnected »."""
        self.ecrire(f"class/drm/card{n}/device/vendor", vendeur)
        self.ecrire(f"class/drm/card{n}-HDMI-A-{n}/status", "disconnected")
        if edp:
            self.ecrire(f"class/drm/card{n}-eDP-{n + 1}/status", edp)

    def machine(self, vendeur="LENOVO", nom="82B5", famille="Legion 5 15ARH05", uefi=True):
        if uefi:   # OsIndicationsSupported : 4 octets d'attributs, puis 0x7f (bit 0 : démarrage dans le BIOS possible)
            efi = self.sys / "firmware/efi/efivars/OsIndicationsSupported-8be4df61-93ca-11d2-aa0d-00e098032b8c"
            efi.parent.mkdir(parents=True, exist_ok=True)
            efi.write_bytes(bytes([6, 0, 0, 0, 0x7f, 0, 0, 0, 0, 0, 0, 0]))
        self.ecrire("class/dmi/id/sys_vendor", vendeur)
        self.ecrire("class/dmi/id/product_name", nom)
        self.ecrire("class/dmi/id/product_family", famille)
        self.ecrire("class/dmi/id/product_version", famille)

    def legion(self, ecran_sur_nvidia=False):
        """Le portable de l'utilisateur : card0 NVIDIA, card1 AMD ; l'écran interne branché sur l'une des deux."""
        self.machine()
        self.carte(0, NVIDIA, "connected" if ecran_sur_nvidia else "disconnected")
        self.carte(1, AMD, "disconnected" if ecran_sur_nvidia else "connected")

    def lancer(self, *args, graphique=True, entree="", langue="fr"):
        env = dict(HOME=str(self.home), PATH=f"{self.faux}:/usr/bin:/bin", NC_LANGUE=langue, NC_SYSFS=str(self.sys),
                   JOURNAL=str(self.journal))
        if graphique:
            env["WAYLAND_DISPLAY"] = "wayland-test"
        return subprocess.run([str(SCRIPT), *args], env=env, input=entree, capture_output=True, text=True, timeout=20)

    def appels(self):
        return self.journal.read_text() if self.journal.exists() else ""

    def notifs(self):
        return [json.loads(l[7:]) for l in self.appels().splitlines() if l.startswith("notify ")]

    # --- (a) Legion sans legion_laptop, écran interne sur l'AMD ---
    def test_legion_hybride_bascule_par_le_bios(self):
        self.legion()
        self.assertEqual(self.lancer("actuel").stdout.strip(), "hybride")
        self.assertEqual(self.lancer("methode").stdout.strip(), "bios")
        info = self.lancer("info").stdout
        self.assertIn("Hybride", info)
        self.assertIn("carte AMD", info)
        self.assertIn("BIOS", info)
        self.assertIn("G-Sync", info)
        # Notification fermée sans clic : aucun redémarrage
        r = self.lancer("basculer", "dediee")
        self.assertEqual(r.returncode, 0, r.stderr)
        n = self.notifs()
        self.assertEqual(len(n), 1)
        self.assertEqual(n[0][:2], ["-a", "noctalia-config"])
        self.assertIn("-A", n[0])
        self.assertIn("oui=Redémarrer dans le BIOS", n[0])
        self.assertIn("GPU Working Mode (ou Mode graphique) → Dédiée", n[0][-1])
        self.assertIn("Les applis ouvertes seront fermées", n[0][-1])
        self.assertNotIn("systemctl", self.appels())
        # Clic sur le bouton : redémarrage dans le BIOS, et rien d'autre
        self.clic("oui")
        self.lancer("basculer", "dediee")
        self.assertEqual([l for l in self.appels().splitlines() if l.startswith("systemctl")],
                         ["systemctl reboot --firmware-setup"])

    def test_bios_sans_demarrage_direct_explique_la_touche(self):
        # BIOS ancien ou variables EFI absentes : pas de bouton qui ne marcherait pas, seulement la touche à presser
        self.machine(uefi=False)
        self.carte(0, NVIDIA, "disconnected")
        self.carte(1, AMD, "connected")
        self.clic("oui")
        r = self.lancer("basculer", "dediee")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("F2", r.stdout)
        self.assertEqual(self.notifs(), [])
        self.assertNotIn("systemctl", self.appels())

    def test_dediee_meme_si_la_carte_integree_a_disparu(self):
        # En mode Dédiée, certains BIOS retirent la carte intégrée du bus : seule la NVIDIA reste, avec l'écran interne
        self.machine()
        self.carte(0, NVIDIA, "connected")
        self.assertEqual(self.lancer("actuel").stdout.strip(), "dediee")

    def test_sans_argument_vers_l_autre_mode(self):
        self.legion()
        self.lancer("basculer")
        self.assertIn("→ Dédiée", self.notifs()[0][-1])

    def test_hors_session_graphique_question_au_terminal(self):
        self.legion()
        r = self.lancer("basculer", "dediee", graphique=False, entree="\n")
        self.assertIn("Redémarrer dans le BIOS", r.stdout)
        self.assertEqual(self.notifs(), [])
        self.assertNotIn("systemctl", self.appels(), "réponse vide : non")
        self.lancer("basculer", "dediee", graphique=False, entree="")           # pas d'entrée du tout : non
        self.assertNotIn("systemctl", self.appels())
        self.lancer("basculer", "dediee", graphique=False, entree="o\n")
        self.assertIn("systemctl reboot --firmware-setup", self.appels())

    def test_deja_dans_le_mode_demande(self):
        self.legion()
        r = self.lancer("basculer", "hybride")
        self.assertEqual(r.returncode, 0)
        self.assertIn("Déjà en mode Hybride", r.stdout)
        self.assertEqual(self.appels(), "")

    def test_mode_inconnu(self):
        self.legion()
        r = self.lancer("basculer", "turbo")
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual(self.appels(), "")

    # --- (b) écran interne sur la NVIDIA ---
    def test_ecran_interne_sur_la_nvidia(self):
        self.legion(ecran_sur_nvidia=True)
        self.assertEqual(self.lancer("actuel").stdout.strip(), "dediee")
        self.assertIn("carte NVIDIA", self.lancer("info").stdout)
        self.assertIn("Déjà en mode Dédiée", self.lancer("basculer", "dediee").stdout)
        self.lancer("basculer", "hybride")
        self.assertIn("→ Hybride", self.notifs()[0][-1])

    # --- (c) ASUS avec supergfxctl ---
    def test_asus_supergfxctl(self):
        self.machine("ASUSTeK COMPUTER INC.", "ROG Strix G614JV", "ROG Strix")
        self.carte(0, NVIDIA, "disconnected")
        self.carte(1, "0x8086", "connected")
        self.programme("supergfxctl", 'echo "supergfxctl $*" >> "$JOURNAL"\n'
                       '[ "$1" = --supported ] && echo "[Integrated, Hybrid, AsusMuxDgpu]"; exit 0')
        self.assertEqual(self.lancer("methode").stdout.strip(), "supergfxctl")
        self.clic("oui")
        self.lancer("basculer", "dediee")
        lignes = self.appels().splitlines()
        self.assertIn("supergfxctl --supported", lignes, "les noms de modes sont vérifiés avant")
        self.assertIn("supergfxctl --mode AsusMuxDgpu", lignes)
        self.assertEqual(len(self.notifs()), 1, "une seule question, posée avant")
        self.assertIn("oui=Changer et redémarrer", self.notifs()[0])
        self.assertIn("systemctl reboot\n", self.appels())
        self.assertNotIn("--firmware-setup", self.appels())

    def test_asus_sans_mux_passe_par_le_bios(self):
        # Un ROG dont supergfxctl ne propose pas AsusMuxDgpu : la méthode reste « bios » (MUX probable : famille ROG)
        self.machine("ASUSTeK COMPUTER INC.", "ROG Zephyrus G14", "ROG Zephyrus")
        self.carte(0, NVIDIA, "disconnected")
        self.carte(1, "0x8086", "connected")
        self.programme("supergfxctl", 'echo "supergfxctl $*" >> "$JOURNAL"\n'
                       '[ "$1" = --supported ] && echo "[Integrated, Hybrid]"; exit 0')
        self.assertEqual(self.lancer("methode").stdout.strip(), "bios")
        self.assertEqual(self.lancer("actuel").stdout.strip(), "hybride")
        self.lancer("basculer", "dediee")
        self.assertNotIn("--mode", self.appels())

    def test_vivobook_sans_mux_sans_objet(self):
        # Avant : tout portable Optimus passait par le BIOS (« Hybride, clic : Dédiée ») alors qu'un Vivobook n'a
        # aucun MUX. Désormais « sans objet » : rien à proposer, aucun redémarrage
        self.machine("ASUSTeK COMPUTER INC.", "Vivobook", "Vivobook")
        self.carte(0, NVIDIA, "disconnected")
        self.carte(1, "0x8086", "connected")
        self.assertEqual(self.lancer("actuel").stdout.strip(), "sans-objet")
        self.assertEqual(self.json()["mode"], "sans-objet")
        r = self.lancer("basculer", "--sans-question", "dediee")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.appels(), "")

    def test_portables_optimus_ordinaires_sans_objet(self):
        for vendeur, nom, famille in (("Dell Inc.", "XPS 15 9520", "XPS"), ("HP", "HP ZBook Fury 16", "ZBook"),
                                      ("LENOVO", "21HH", "ThinkPad P1 Gen 6"), ("Acer", "Swift X", "Swift")):
            with self.subTest(nom=nom):
                self.machine(vendeur, nom, famille)
                self.carte(0, NVIDIA, "disconnected")
                self.carte(1, "0x8086", "connected")
                self.assertEqual(self.lancer("actuel").stdout.strip(), "sans-objet")

    def test_familles_a_mux_gardent_le_mode(self):
        for vendeur, nom, famille in (("LENOVO", "82XV", "LOQ 15IRH8"), ("Alienware", "Alienware m16 R1", "Alienware"),
                                      ("HP", "OMEN by HP Laptop 16", "OMEN"), ("Acer", "Predator PH16", "Predator"),
                                      ("Micro-Star International Co., Ltd.", "GE76 Raider", "GE"),
                                      ("ASUSTeK COMPUTER INC.", "TUF Gaming A15", "TUF Gaming")):
            with self.subTest(nom=nom):
                self.machine(vendeur, nom, famille)
                self.carte(0, NVIDIA, "disconnected")
                self.carte(1, "0x8086", "connected")
                self.assertEqual(self.lancer("actuel").stdout.strip(), "hybride")

    def test_dediee_deja_active_meme_sans_famille_connue(self):
        # Écran interne déjà sur la NVIDIA : c'est le vrai indice d'un MUX, quel que soit le constructeur
        self.machine("Dell Inc.", "XPS 15 9520", "XPS")
        self.carte(0, NVIDIA, "connected")
        self.carte(1, "0x8086", "disconnected")
        self.assertEqual(self.lancer("actuel").stdout.strip(), "dediee")

    def test_legion_ne_change_pas(self):
        # Le Legion de l'utilisateur : mêmes réponses qu'avant, pour l'île et nc-reglages
        self.legion()
        self.assertEqual(self.lancer("actuel").stdout.strip(), "hybride")
        self.assertEqual(self.lancer("methode").stdout.strip(), "bios")
        self.assertEqual(self.json()["mode"], "hybride")
        self.legion(ecran_sur_nvidia=True)
        self.assertEqual(self.lancer("actuel").stdout.strip(), "dediee")

    def test_system76(self):
        self.machine("System76", "Oryx Pro", "Oryx Pro")
        self.carte(0, NVIDIA, "connected")
        self.carte(1, "0x8086", "disconnected")
        self.assertEqual(self.lancer("methode").stdout.strip(), "system76-power")
        self.clic("oui")
        self.lancer("basculer", "hybride")
        self.assertIn("system76-power graphics hybrid", self.appels())

    # --- (d) une seule carte ---
    def test_une_seule_carte_sans_objet(self):
        self.machine()
        self.carte(0, AMD, "connected")
        self.assertEqual(self.lancer("actuel").stdout.strip(), "sans-objet")
        self.assertIn("sans objet", self.lancer("info").stdout)
        for cible in ("dediee", "hybride", ""):
            r = self.lancer("basculer", *([cible] if cible else []))
            self.assertEqual(r.returncode, 0)
        self.assertEqual(self.appels(), "", "rien n'est appelé")

    def test_pc_fixe_deux_cartes_sans_ecran_interne(self):
        self.machine("Micro-Star International Co., Ltd.", "MS-7C02", "Default string")
        self.carte(0, NVIDIA)
        self.carte(1, AMD)
        self.assertEqual(self.lancer("actuel").stdout.strip(), "sans-objet")

    def test_carte_nvidia_sans_pilote_comptee_par_le_pci(self):
        """Pilote NVIDIA non chargé : pas de card0, mais deux contrôleurs d'affichage PCI → hybride."""
        self.machine()
        self.carte(1, AMD, "connected")
        self.ecrire("bus/pci/devices/0000:01:00.0/class", "0x030000")
        self.ecrire("bus/pci/devices/0000:01:00.0/vendor", NVIDIA)
        self.ecrire("bus/pci/devices/0000:06:00.0/class", "0x030000")
        self.ecrire("bus/pci/devices/0000:06:00.1/class", "0x040300")    # le son HDMI ne compte pas
        self.assertEqual(self.lancer("actuel").stdout.strip(), "hybride")

    # --- (e) Legion avec le module legion_laptop et un attribut gsync ---
    def test_legion_gsync(self):
        self.legion()
        (self.sys / "module/legion_laptop").mkdir(parents=True)
        gsync = self.ecrire("bus/platform/drivers/legion/PNP0C09:00/gsync", "0")
        self.assertEqual(self.lancer("methode").stdout.strip(), "gsync")
        self.clic("oui")
        self.lancer("basculer", "dediee")
        self.assertEqual(gsync.read_text().strip(), "1")
        self.assertNotIn("pkexec", self.appels(), "fichier modifiable : écrit sans root")
        self.assertNotIn("sudo", self.appels())
        # Retour en hybride, une fois l'écran passé sur la NVIDIA
        (self.sys / "class/drm/card0-eDP-1/status").write_text("connected\n")
        (self.sys / "class/drm/card1-eDP-2/status").write_text("disconnected\n")
        self.lancer("basculer", "hybride")
        self.assertEqual(gsync.read_text().strip(), "0")

    def test_gsync_sans_module_charge_ignore(self):
        self.legion()
        self.ecrire("bus/platform/drivers/legion/PNP0C09:00/gsync", "0")
        self.assertEqual(self.lancer("methode").stdout.strip(), "bios")

    def test_module_sans_attribut_gsync_ignore(self):
        self.legion()
        (self.sys / "module/legion_laptop").mkdir(parents=True)
        (self.sys / "bus/platform/drivers/legion/PNP0C09:00").mkdir(parents=True)
        self.assertEqual(self.lancer("methode").stdout.strip(), "bios")

    # --- (f) état pour l'île, et bascule déjà confirmée ailleurs (--sans-question) ---
    def json(self):
        r = self.lancer("json")
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)

    def test_json_legion(self):
        self.legion()
        self.assertEqual(self.json(), {"mode": "hybride", "methode": "bios", "bios_direct": True, "carte_ecran": "AMD",
                                       "pilote_nvidia": False})
        (self.sys / "class/drm/card0-eDP-1/status").write_text("connected\n")
        (self.sys / "class/drm/card1-eDP-2/status").write_text("disconnected\n")
        self.assertEqual(self.json(), {"mode": "dediee", "methode": "bios", "bios_direct": True, "carte_ecran": "NVIDIA",
                                       "pilote_nvidia": False})
        self.assertEqual(self.appels(), "", "lire l'état n'appelle rien")

    def test_json_pilote_nvidia(self):
        self.legion()
        self.assertFalse(self.json()["pilote_nvidia"])
        (self.sys / "module/nouveau").mkdir(parents=True)
        self.assertTrue(self.json()["pilote_nvidia"])
        (self.sys / "module/nouveau").rmdir()
        (self.sys / "module/nvidia").mkdir()
        self.assertTrue(self.json()["pilote_nvidia"])

    def test_json_sans_demarrage_direct(self):
        self.machine(uefi=False)
        self.carte(0, NVIDIA, "disconnected")
        self.carte(1, AMD, "connected")
        self.assertFalse(self.json()["bios_direct"])
        self.assertEqual(self.lancer("json", langue="en").stdout, self.lancer("json").stdout, "même JSON en anglais")

    def test_json_sans_objet(self):
        self.machine()
        self.carte(0, AMD, "connected")
        self.assertEqual(self.json(), {"mode": "sans-objet", "methode": "", "bios_direct": False, "carte_ecran": "",
                                       "pilote_nvidia": False})

    def test_sans_question_bios_redemarre_dans_le_bios(self):
        self.legion()
        self.clic("")                            # une notification fermée ne doit rien empêcher : il n'y en a pas
        r = self.lancer("basculer", "--sans-question", "dediee")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.notifs(), [], "aucune question")
        self.assertEqual(self.appels().splitlines(), ["systemctl reboot --firmware-setup"])
        # Hors session graphique non plus, aucune question (rien n'est lu au terminal), option après le mode aussi
        self.journal.unlink()
        r = self.lancer("basculer", "dediee", "--sans-question", graphique=False, entree="")
        self.assertNotIn("[o/N]", r.stdout)
        self.assertEqual(self.appels().splitlines(), ["systemctl reboot --firmware-setup"])

    def test_sans_question_exige_le_mode(self):
        self.legion()
        r = self.lancer("basculer", "--sans-question")
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual(self.appels(), "")

    def test_sans_question_deja_dans_le_mode(self):
        self.legion()
        self.lancer("basculer", "--sans-question", "hybride")
        self.assertEqual(self.appels(), "", "déjà en Hybride : pas de redémarrage")

    def test_sans_question_une_seule_carte(self):
        self.machine()
        self.carte(0, AMD, "connected")
        self.lancer("basculer", "--sans-question", "dediee")
        self.assertEqual(self.appels(), "", "une seule carte : rien")

    def test_sans_question_bios_sans_demarrage_direct(self):
        # Pas de démarrage direct dans le BIOS : même confirmé, seulement l'explication (la touche à presser)
        self.machine(uefi=False)
        self.carte(0, NVIDIA, "disconnected")
        self.carte(1, AMD, "connected")
        r = self.lancer("basculer", "--sans-question", "dediee")
        self.assertIn("F2", r.stdout)
        self.assertEqual(self.appels(), "")

    def test_par_logiciel_la_question_vient_avant_le_changement(self):
        # Refusée (notification fermée) ou sans réponse (stdin vide, hors session graphique) : rien ne bouge
        self.machine("ASUSTeK COMPUTER INC.", "ROG Strix G614JV", "ROG Strix")
        self.carte(0, NVIDIA, "disconnected")
        self.carte(1, "0x8086", "connected")
        self.programme("supergfxctl", 'echo "supergfxctl $*" >> "$JOURNAL"\n'
                       '[ "$1" = --supported ] && echo "[Integrated, Hybrid, AsusMuxDgpu]"; exit 0')
        for graphique in (True, False):
            r = self.lancer("basculer", "dediee", graphique=graphique)
            self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn("--mode", self.appels())
        self.assertNotIn("systemctl", self.appels())

    def test_deux_cartes_sans_nvidia_sans_objet(self):
        # Intel (écran interne) + AMD (eGPU ou autre) : pas de MUX, donc pas de mode à choisir
        self.machine("LENOVO", "21XX", "ThinkPad")
        self.carte(0, AMD, "disconnected")
        self.carte(1, "0x8086", "connected")
        self.assertEqual(self.lancer("actuel").stdout.strip(), "sans-objet")
        self.assertIn('"mode": "sans-objet"', self.lancer("json").stdout)
        r = self.lancer("basculer", "--sans-question", "dediee")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn("systemctl", self.appels())

    def test_sans_question_par_logiciel_puis_redemarrage(self):
        self.machine("System76", "Oryx Pro", "Oryx Pro")
        self.carte(0, NVIDIA, "disconnected")
        self.carte(1, "0x8086", "connected")
        self.lancer("basculer", "--sans-question", "dediee")
        self.assertEqual(self.appels().splitlines(), ["system76-power graphics nvidia", "systemctl reboot"])
        self.assertEqual(self.notifs(), [])

    def test_sans_question_methode_en_echec_ne_redemarre_pas(self):
        self.machine("System76", "Oryx Pro", "Oryx Pro")
        self.carte(0, NVIDIA, "disconnected")
        self.carte(1, "0x8086", "connected")
        self.programme("system76-power", 'echo "system76-power $*" >> "$JOURNAL"; exit 1')
        r = self.lancer("basculer", "--sans-question", "dediee")
        self.assertNotEqual(r.returncode, 0)
        self.assertNotIn("systemctl", self.appels())

    # --- échec visible (--sans-question) ---
    def test_sans_question_echec_notifie(self):
        self.machine("System76", "Oryx Pro", "Oryx Pro")
        self.carte(0, NVIDIA, "disconnected")
        self.carte(1, "0x8086", "connected")
        self.programme("system76-power", 'echo "system76-power $*" >> "$JOURNAL"; exit 1')
        r = self.lancer("basculer", "--sans-question", "dediee")
        self.assertNotEqual(r.returncode, 0)
        n = self.notifs()
        self.assertEqual(len(n), 1)
        self.assertEqual(n[0][-1], "Le changement de mode a échoué : system76-power")
        self.lancer("basculer", "--sans-question", "dediee", langue="en")
        self.assertEqual(self.notifs()[-1][-1], "The mode change failed: system76-power")

    def test_sans_option_pas_de_notification_d_echec(self):
        self.machine("System76", "Oryx Pro", "Oryx Pro")
        self.carte(0, NVIDIA, "disconnected")
        self.carte(1, "0x8086", "connected")
        self.programme("system76-power", 'exit 1')
        self.clic("oui")
        self.lancer("basculer", "dediee")
        self.assertTrue(all("échoué" not in n[-1] for n in self.notifs()))

    def test_gsync_seulement_si_l_ecriture_peut_aboutir(self):
        # Fichier non inscriptible : gsync seulement avec pkexec (un sudo sans terminal échouerait en silence)
        self.legion()
        (self.sys / "module/legion_laptop").mkdir(parents=True)
        gsync = self.ecrire("bus/platform/drivers/legion/PNP0C09:00/gsync", "0")
        gsync.chmod(0o444)
        if os.access(gsync, os.W_OK):
            self.skipTest("lancé en root : tout fichier est inscriptible")
        self.assertEqual(self.lancer("methode").stdout.strip(), "gsync", "faux pkexec présent")
        (self.faux / "pkexec").unlink()
        if shutil.which("pkexec", path="/usr/bin:/bin"):
            self.skipTest("un vrai pkexec est installé : le cas sans pkexec ne peut pas être simulé")
        self.assertEqual(self.lancer("methode").stdout.strip(), "bios")

    # --- langue ---
    def test_en_anglais(self):
        self.legion()
        info = self.lancer("info", langue="en").stdout
        self.assertIn("Graphics mode: Hybrid", info)
        self.assertIn("Tip: Hybrid on battery", info)
        self.assertEqual(self.lancer("actuel", langue="en").stdout.strip(), "hybride", "la sortie d'actuel ne change pas")
        self.lancer("basculer", "dediee", langue="en")
        self.assertIn("oui=Restart into BIOS", self.notifs()[0])
        self.assertIn("→ Discrete", self.notifs()[0][-1])


if __name__ == "__main__":
    unittest.main()

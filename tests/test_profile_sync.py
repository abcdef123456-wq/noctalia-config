"""nc-profile-sync sur batterie : relevés de la barre Noctalia espacés (zz-batterie.toml, réglage BAT_RELEVES), section
[system.monitor] de zz-economie.toml en Économie, un seul config-reload par vrai changement, clavier lumineux ramené au
niveau 1 puis rendu au branchement (BAT_CLAVIER) ; nc-paquets.service attend le secteur.

Faux gdbus (profil voulu ; le flux D-Bus s'arrête aussitôt, le script fait un passage puis sort), hyprctl, noctalia,
brightnessctl, bluetoothctl et notify-send ; alimentation et clavier lumineux dans de faux dossiers /sys ; HOME et
XDG_RUNTIME_DIR temporaires.
"""
import os
from pathlib import Path
import subprocess
import tempfile
import time
import unittest

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "home/.local/bin/nc-profile-sync"
UNITES = REPO / "home/.config/systemd/user"
BIN = REPO / "home/.local/bin"

FAUX = {
    # call … Get : le profil de NC_TEST_PROFIL ; monitor : rien (le flux se ferme, le script sort après un passage)
    "gdbus": 'case "$*" in *Properties.Get*) echo "(<\'$NC_TEST_PROFIL\'>,)" ;; esac\nexit 0',
    "hyprctl": 'echo "hyprctl $*" >> "$JOURNAL"\nexit 0',
    "noctalia": 'echo "noctalia $*" >> "$JOURNAL"\nexit 0',
    # Le clavier lumineux : « set N » écrit vraiment dans le faux /sys (comme le vrai brightnessctl)
    "brightnessctl": 'echo "brightnessctl $*" >> "$JOURNAL"\n'
                     'case "$*" in *" get") echo 50 ;; *" max") echo 100 ;;\n'
                     '  *kbd_backlight*" set "*) for a; do n=$a; done; echo "$n" > "$NC_LEDS/test::kbd_backlight/brightness" ;; esac\nexit 0',
    "bluetoothctl": "exit 0",
    "notify-send": "exit 0",
    # sudo -n : NC_TEST_SUDO=refus imite l'absence de règle (« a password is required », code 1) ; sinon lance la commande
    "sudo": 'echo "sudo $*" >> "$JOURNAL"\n[ "$1" = -n ] || exit 9\n[ "${NC_TEST_SUDO:-}" = refus ] && { echo "sudo: a password is required" >&2; exit 1; }\nshift; exec "$@"',
}


class ProfileSync(unittest.TestCase):
    def setUp(self):
        d = tempfile.TemporaryDirectory(prefix="nc-profile-sync-")
        self.addCleanup(d.cleanup)
        self.home = Path(d.name)
        self.faux = self.home / "faux"
        self.faux.mkdir()
        for nom, corps in FAUX.items():
            f = self.faux / nom
            f.write_text("#!/bin/sh\n" + corps + "\n")
            f.chmod(0o755)
        (self.home / ".config/nc").mkdir(parents=True)
        (self.home / ".config/noctalia").mkdir(parents=True)
        self.reglages("")
        self.run_dir = self.home / "run"
        self.run_dir.mkdir(mode=0o700)
        self.journal = self.home / "journal"
        # Faux /sys : un chargeur et une batterie, un clavier lumineux au niveau 3
        self.alim = self.home / "sys/power_supply"
        for nom, contenu in (("AC", {"type": "Mains", "online": "1"}), ("BAT0", {"type": "Battery", "capacity": "80"})):
            (self.alim / nom).mkdir(parents=True)
            for k, v in contenu.items():
                (self.alim / nom / k).write_text(v + "\n")
        self.leds = self.home / "sys/leds"
        (self.leds / "test::kbd_backlight").mkdir(parents=True)
        self.clavier(3)
        self.batt = self.home / ".config/noctalia/zz-batterie.toml"
        self.eco = self.home / ".config/noctalia/zz-economie.toml"
        self.env_plus = {}
        # Faux assistant root : note sa sous-commande (le vrai est testé dans test_energie_root)
        a = self.home / "nc-energie-root"
        a.write_text('#!/bin/sh\necho "assistant $*" >> "$JOURNAL"\nexit 0\n')
        a.chmod(0o755)

    def reglages(self, texte):
        (self.home / ".config/nc/reglages.conf").write_text("LANGUE=fr\n" + texte)

    def secteur(self, branche):
        (self.alim / "AC/online").write_text("1\n" if branche else "0\n")

    def clavier(self, niveau=None):
        f = self.leds / "test::kbd_backlight/brightness"
        if niveau is not None:
            f.write_text(f"{niveau}\n")
        return int(f.read_text())

    def lancer(self, profil, config=None):
        self.journal.write_text("")
        env = dict(HOME=str(self.home), PATH=f"{self.faux}:/usr/bin:/bin", NC_LANGUE="fr", JOURNAL=str(self.journal),
                   XDG_RUNTIME_DIR=str(self.run_dir), XDG_CONFIG_HOME=str(config or self.home / ".config"),
                   NC_POWER_SUPPLY=str(self.alim), NC_LEDS=str(self.leds), NC_TEST_PROFIL=profil,
                   NC_ENERGIE_ROOT_CHEMIN=str(self.home / "nc-energie-root"), **self.env_plus)
        r = subprocess.run(["bash", str(SCRIPT)], env=env, capture_output=True, text=True, timeout=30,
                           stdin=subprocess.DEVNULL)
        self.assertIn("flux D-Bus interrompu", r.stdout, r.stdout + r.stderr)   # un passage, puis la fin du flux
        return r

    def rechargements(self):
        return self.journal.read_text().count("noctalia msg config-reload")

    def test_equilibre_sur_batterie_releves_espaces(self):
        self.secteur(False)
        self.lancer("balanced")
        texte = self.batt.read_text()
        self.assertIn("[system.monitor]", texte)
        for ligne in ("cpu_poll_seconds = 5.0", "memory_poll_seconds = 6.0", "network_poll_seconds = 6.0",
                      "disk_poll_seconds = 30.0", "gpu_poll_seconds = 0.0"):
            self.assertIn(ligne, texte)
        self.assertFalse(self.eco.exists())
        self.assertEqual(self.rechargements(), 1)
        # Même état au passage suivant : rien n'est réécrit, Noctalia n'est pas rechargée
        self.lancer("balanced")
        self.assertEqual(self.rechargements(), 0)
        # Branché : le fichier part, un rechargement
        self.secteur(True)
        self.lancer("balanced")
        self.assertFalse(self.batt.exists())
        self.assertEqual(self.rechargements(), 1)

    def test_config_derniere_ligne_sans_retour_et_blancs(self):
        """« HZ_ECO=60  \\r » en dernière ligne, sans \\n final (fichier édité sous Windows) : la valeur 60 est prise."""
        (self.home / ".config/nc-profile.conf").write_bytes(b"HZ_PERFORMANCE=  max \t\r\nHZ_ECO=60  \r")
        r = self.lancer("power-saver")
        sortie = (self.home / ".config/hypr/nc/profil.lua").read_text()
        self.assertIn('hz = "60"', sortie, r.stderr)
        (self.home / ".config/hypr/nc/profil.lua").unlink()
        self.lancer("performance")
        self.assertIn('hz = "max"', (self.home / ".config/hypr/nc/profil.lua").read_text())
        self.assertNotIn("valeur ignorée", r.stderr)

    def test_secteur_rien(self):
        self.lancer("balanced")
        self.assertFalse(self.batt.exists())
        self.assertFalse(self.eco.exists())
        self.assertEqual(self.rechargements(), 0)

    def test_performance_sur_batterie_rien(self):
        self.secteur(False)
        self.lancer("performance")
        self.assertFalse(self.batt.exists())
        self.assertEqual(self.clavier(), 3)

    def test_economie_section_monitor(self):
        self.lancer("power-saver")
        texte = self.eco.read_text()
        self.assertIn("[shell.animation]", texte)
        self.assertIn("[system.monitor]", texte)
        for ligne in ("cpu_poll_seconds = 10.0", "memory_poll_seconds = 10.0", "network_poll_seconds = 10.0",
                      "disk_poll_seconds = 60.0", "gpu_poll_seconds = 0.0"):
            self.assertIn(ligne, texte)
        self.assertFalse(self.batt.exists())                      # sur secteur
        # Économie sur batterie : les deux fichiers (zz-economie gagne, ordre alphabétique), un seul rechargement
        self.eco.unlink()
        self.secteur(False)
        self.lancer("power-saver")
        self.assertTrue(self.eco.exists())
        self.assertTrue(self.batt.exists())
        self.assertLess("zz-batterie.toml", "zz-economie.toml")
        self.assertEqual(self.rechargements(), 1)

    def test_dossier_de_noctalia_suit_xdg_config_home(self):
        # Noctalia lit $XDG_CONFIG_HOME/noctalia (sans NOCTALIA_CONFIG_HOME) : zz-economie.toml doit y être, sinon
        # le profil Économie ne fait rien
        ailleurs = self.home / "config-ailleurs"
        (ailleurs / "noctalia").mkdir(parents=True)
        self.secteur(False)
        self.lancer("power-saver", config=ailleurs)
        self.assertTrue((ailleurs / "noctalia/zz-economie.toml").exists())
        self.assertFalse(self.eco.exists())

    def test_releves_non(self):
        self.reglages("BAT_RELEVES=non\n")
        self.secteur(False)
        self.lancer("balanced")
        self.assertFalse(self.batt.exists())

    def test_clavier_batterie_puis_branchement(self):
        self.secteur(False)
        self.lancer("balanced")
        self.assertEqual(self.clavier(), 1)
        self.secteur(True)
        self.lancer("balanced")
        self.assertEqual(self.clavier(), 3)
        self.assertFalse((self.run_dir / "nc-kbd-saved").exists())

    def test_clavier_deja_bas_ou_reglage_non(self):
        self.clavier(1)
        self.secteur(False)
        self.lancer("balanced")
        self.assertEqual(self.clavier(), 1)
        self.assertNotIn("kbd_backlight", self.journal.read_text())   # rien à faire, rien n'est touché
        self.clavier(2)
        self.reglages("BAT_CLAVIER=non\n")
        self.lancer("balanced")
        self.assertEqual(self.clavier(), 2)

    def test_clavier_economie_eteint(self):
        self.lancer("power-saver")
        self.assertEqual(self.clavier(), 0)
        self.lancer("balanced")
        self.assertEqual(self.clavier(), 3)

    def service_ouvert(self, secours):
        """Lance le service avec un flux D-Bus qui reste ouvert sans événement ; le profil se lit dans un fichier."""
        profil = self.home / "profil-voulu"
        profil.write_text("balanced\n")
        (self.faux / "gdbus").write_text("#!/bin/sh\ncase \"$*\" in *Properties.Get*) echo \"(<'$(cat \"$NC_TEST_FICHIER\")'>,)\" ;;\n"
                                         "*monitor*) exec sleep 20 ;; esac\nexit 0\n")
        self.journal.write_text("")
        env = dict(HOME=str(self.home), PATH=f"{self.faux}:/usr/bin:/bin", NC_LANGUE="fr", JOURNAL=str(self.journal),
                   XDG_RUNTIME_DIR=str(self.run_dir), XDG_CONFIG_HOME=str(self.home / ".config"),
                   NC_POWER_SUPPLY=str(self.alim), NC_LEDS=str(self.leds), NC_TEST_FICHIER=str(profil),
                   NC_SYNC_SECOURS=str(secours))
        p = subprocess.Popen(["bash", str(SCRIPT)], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                             stdin=subprocess.DEVNULL, start_new_session=True)
        self.addCleanup(lambda: (p.poll() is None) and (p.kill(), p.wait()))
        return p, profil

    def passages(self):
        return self.journal.read_text().count("hyprctl monitors")

    def test_reveil_de_secours_rien_ne_change_rien_n_est_applique(self):
        p, _ = self.service_ouvert(1)
        time.sleep(4.5)                                   # plusieurs réveils de secours (1 s), rien de changé
        self.assertEqual(self.passages(), 1, self.journal.read_text())
        p.kill()

    def test_reveil_de_secours_profil_change_applique(self):
        p, profil = self.service_ouvert(1)
        time.sleep(1.5)
        profil.write_text("power-saver\n")
        # Attendre le contenu, pas le compte des passages : « hyprctl monitors » est appelé au début du passage, avant
        # l'écriture de profil.lua (nc-profile-sync), qu'on lisait parfois trop tôt
        sortie = self.home / ".config/hypr/nc/profil.lua"
        lire = lambda: sortie.read_text() if sortie.exists() else ""
        fin = time.time() + 6
        while time.time() < fin and 'profil = "power-saver"' not in lire():
            time.sleep(0.2)
        self.assertGreaterEqual(self.passages(), 2, self.journal.read_text())
        self.assertIn('profil = "power-saver"', lire())
        p.kill()

    # Carte Ethernet : veille permise en Économie seulement (eth-pm on), jamais ailleurs (eth-pm off) ; dès le premier
    # passage ; une fois par changement ; sans règle sudo, ni message ni nouvel essai.
    def appels(self):
        return [l for l in self.journal.read_text().splitlines() if l.startswith(("assistant", "sudo"))]

    def test_demarrage_deja_en_economie(self):
        r = self.lancer("power-saver")
        self.assertEqual(self.appels(), [f"sudo -n {self.home}/nc-energie-root eth-pm on", "assistant eth-pm on"], r.stderr)

    def test_equilibre_et_performance_jamais_en_veille(self):
        for profil in ("balanced", "performance"):
            self.lancer(profil)
            self.assertIn("assistant eth-pm off", self.appels(), profil)

    def test_sans_regle_sudo_silencieux_un_seul_essai(self):
        self.env_plus = {"NC_TEST_SUDO": "refus"}
        r = self.lancer("power-saver")
        self.assertEqual(self.appels(), [f"sudo -n {self.home}/nc-energie-root eth-pm on"], "un seul essai")
        self.assertNotIn("password", r.stdout + r.stderr)
        self.assertNotIn("eth", r.stdout + r.stderr)

    def test_sans_assistant_rien(self):
        (self.home / "nc-energie-root").unlink()
        r = self.lancer("power-saver")
        self.assertEqual(self.appels(), [])
        self.assertNotIn("eth", r.stdout + r.stderr)

    def test_une_seule_fois_par_changement(self):
        # Deux passages dans le même processus (le second sans changement de profil) : un seul appel
        source = SCRIPT.read_text()
        m = source.split("rm -f \"$GPU_STATE\" \"$RTX_GUET\"\napply\n", 1)
        self.assertEqual(len(m), 2, "le premier passage a bougé")
        (self.home / "nc-gpu-regle").symlink_to(BIN / "nc-gpu-regle")   # cherché à côté du script
        script = self.home / "deux-passages"
        # Économie deux fois (un seul appel), puis Équilibré dans le même processus : « off »
        script.write_text(m[0] + "apply\napply\nexport NC_TEST_PROFIL=balanced\napply\n")
        self.journal.write_text("")
        env = dict(HOME=str(self.home), PATH=f"{self.faux}:/usr/bin:/bin", NC_LANGUE="fr", JOURNAL=str(self.journal),
                   XDG_RUNTIME_DIR=str(self.run_dir), XDG_CONFIG_HOME=str(self.home / ".config"),
                   NC_POWER_SUPPLY=str(self.alim), NC_LEDS=str(self.leds), NC_TEST_PROFIL="power-saver",
                   NC_ENERGIE_ROOT_CHEMIN=str(self.home / "nc-energie-root"))
        r = subprocess.run(["bash", str(script)], env=env, capture_output=True, text=True, timeout=30, stdin=subprocess.DEVNULL)
        self.assertEqual([l for l in self.appels() if l.startswith("assistant")], ["assistant eth-pm on", "assistant eth-pm off"],
                         r.stderr)


class Paquets(unittest.TestCase):
    def test_paquets_decide_lui_meme_du_secteur(self):
        # Une condition dans l'unité empêcherait la cadence batterie (3 h) que nc-paquets calcule lui-même ;
        # network-online.target n'existe pas dans le gestionnaire utilisateur
        unite = (UNITES / "nc-paquets.service").read_text()
        for ligne in unite.splitlines():
            if not ligne.lstrip().startswith("#"):
                self.assertNotIn("ConditionACPower", ligne)
                self.assertNotIn("network-online", ligne)
        self.assertIn("-p ConditionACPower=true", (BIN / "nc-paquets").read_text())
        self.assertIn("AccuracySec=10min", (UNITES / "nc-maj-verif.timer").read_text())
        self.assertIn("AccuracySec=1min", (UNITES / "nc-alertes.timer").read_text())
        # La vérification des nouvelles versions de la config, elle, passe aussi sur batterie
        self.assertNotIn("ConditionACPower", (UNITES / "nc-maj-verif.service").read_text())


if __name__ == "__main__":
    unittest.main()

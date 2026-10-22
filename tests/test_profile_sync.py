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
import unittest

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "home/.local/bin/nc-profile-sync"
UNITES = REPO / "home/.config/systemd/user"

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

    def reglages(self, texte):
        (self.home / ".config/nc/reglages.conf").write_text("LANGUE=fr\n" + texte)

    def secteur(self, branche):
        (self.alim / "AC/online").write_text("1\n" if branche else "0\n")

    def clavier(self, niveau=None):
        f = self.leds / "test::kbd_backlight/brightness"
        if niveau is not None:
            f.write_text(f"{niveau}\n")
        return int(f.read_text())

    def lancer(self, profil):
        self.journal.write_text("")
        env = dict(HOME=str(self.home), PATH=f"{self.faux}:/usr/bin:/bin", NC_LANGUE="fr", JOURNAL=str(self.journal),
                   XDG_RUNTIME_DIR=str(self.run_dir), XDG_CONFIG_HOME=str(self.home / ".config"),
                   NC_POWER_SUPPLY=str(self.alim), NC_LEDS=str(self.leds), NC_TEST_PROFIL=profil)
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


class Paquets(unittest.TestCase):
    def test_paquets_attend_le_secteur(self):
        unite = (UNITES / "nc-paquets.service").read_text()
        avant_service = unite.split("[Service]")[0]
        self.assertIn("ConditionACPower=true", avant_service)
        # La vérification des nouvelles versions de la config, elle, passe aussi sur batterie
        self.assertNotIn("ConditionACPower", (UNITES / "nc-maj-verif.service").read_text())


if __name__ == "__main__":
    unittest.main()

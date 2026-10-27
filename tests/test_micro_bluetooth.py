"""nc-micro-bluetooth : le micro d'un casque Bluetooth réparé (réactivé, choisi par défaut, mode appel s'il n'y a pas de
micro). Faux pw-dump, wpctl et pactl qui notent leurs arguments, HOME temporaire."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "home/.local/bin/nc-micro-bluetooth"
CASQUE = {"id": 69, "type": "PipeWire:Interface:Device",
          "info": {"props": {"device.api": "bluez5", "device.name": "bluez_card.AA_BB", "device.description": "AirPods"}}}
MICROS = [{"id": 64, "type": "PipeWire:Interface:Node", "info": {"props": {"node.name": "bluez_input.AA:BB", "media.class": "Audio/Source"}}},
          {"id": 89, "type": "PipeWire:Interface:Node", "info": {"props": {"node.name": "bluez_input.AA_BB.0", "media.class": "Audio/Source/Internal"}}},
          {"id": 92, "type": "PipeWire:Interface:Node", "info": {"props": {"node.name": "bluez_output.AA_BB.1", "media.class": "Audio/Sink"}}}]


@unittest.skipUnless(shutil.which("jq"), "jq requis")
class MicroBluetooth(unittest.TestCase):
    def setUp(self):
        d = tempfile.TemporaryDirectory(prefix="nc-micro-bt-")
        self.addCleanup(d.cleanup)
        self.home = Path(d.name)
        self.bin = self.home / "bin"
        self.bin.mkdir()
        self.journal = self.home / "appels"
        for nom in ("wpctl", "pactl"):
            f = self.bin / nom
            f.write_text(f'#!/bin/sh\necho "{nom} $*" >> "{self.journal}"\n'
                         + (f'[ "$1" = set-card-profile ] && cp "{self.home}/apres.json" "{self.home}/etat.json"\n' if nom == "pactl" else "")
                         + "exit 0\n")
            f.chmod(0o755)
        f = self.bin / "pw-dump"
        f.write_text(f'#!/bin/sh\ncat "{self.home}/etat.json"\n')
        f.chmod(0o755)

    def lancer(self, *args, etat, apres=None):
        (self.home / "etat.json").write_text(json.dumps(etat))
        (self.home / "apres.json").write_text(json.dumps(apres if apres is not None else etat))
        env = dict(os.environ, HOME=str(self.home), PATH=f"{self.bin}:/usr/bin:/bin", NC_LANGUE="fr")
        r = subprocess.run(["bash", str(SCRIPT), *args], env=env, capture_output=True, text=True, timeout=30)
        return r, (self.journal.read_text().splitlines() if self.journal.exists() else [])

    def test_micros_reactives_et_choisi_par_defaut(self):
        r, appels = self.lancer(etat=[CASQUE] + MICROS)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("wpctl set-mute 64 0", appels)
        self.assertIn("wpctl set-mute 89 0", appels)
        self.assertNotIn("wpctl set-mute 92 0", appels)                     # la sortie son n'est pas un micro
        self.assertIn("wpctl set-default 64", appels)
        self.assertFalse([a for a in appels if a.startswith("pactl")])      # déjà en mode appel : rien à changer

    def test_mode_musique_passe_en_mode_appel(self):
        r, appels = self.lancer(etat=[CASQUE, MICROS[2]], apres=[CASQUE] + MICROS)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("pactl set-card-profile bluez_card.AA_BB headset-head-unit", appels)
        self.assertIn("wpctl set-default 64", appels)

    def test_sans_casque_et_retour_au_mode_musique(self):
        r, appels = self.lancer(etat=MICROS)
        self.assertEqual(r.returncode, 1)
        self.assertIn("Aucun casque", r.stdout)
        self.assertEqual(appels, [])
        r, appels = self.lancer("musique", etat=[CASQUE] + MICROS)
        self.assertIn("pactl set-card-profile bluez_card.AA_BB a2dp-sink", appels)


if __name__ == "__main__":
    unittest.main()

"""Incident du carrousel plein écran : Échap ferme les panneaux qui prennent tout le clavier, Noctalia est relancé
même après un SIGTERM, et nc-shell-msg le redémarre (ou prévient) au lieu d'envoyer un message dans le vide."""
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
PLUGINS = REPO / "home/.local/share/noctalia/plugins"
MSG = REPO / "home/.local/bin/nc-shell-msg"


class PanneauxExclusifs(unittest.TestCase):
    def test_echap_capture_et_gere(self):
        for toml in sorted(PLUGINS.glob("*/plugin.toml")):
            texte = toml.read_text()
            if 'keyboard_focus = "exclusive"' not in texte or "capture_keys" not in texte:
                continue                                  # sans capture, Noctalia ferme lui-même le panneau sur Échap
            with self.subTest(plugin=toml.parent.name):
                cles = re.search(r"^capture_keys\s*=\s*\[(.*)\]", texte, re.M)[1]
                self.assertIn('"Escape"', cles)
                luau = "\n".join(f.read_text() for f in toml.parent.glob("*.luau"))
                self.assertRegex(luau, r'(?s)(chord|touche) == "Escape".{0,40}(panel\.close|fermer)\(', "Échap capturé mais ignoré")


class Service(unittest.TestCase):
    def test_relance_apres_arret_propre(self):
        texte = (REPO / "home/.config/systemd/user/noctalia.service").read_text()
        self.assertRegex(texte, r"(?m)^Restart=always$")
        self.assertRegex(texte, r"(?m)^RestartSec=\d+$")


FAUX = {
    "pgrep": 'echo "pgrep $*" >> "$JOURNAL"; [ -e "$ETAT/vivant" ]',
    "systemctl": 'echo "systemctl $*" >> "$JOURNAL"; case "$*" in *"start noctalia.service"*) [ -e "$ETAT/demarre" ] && : > "$ETAT/vivant" ;; esac; exit 0',
    "noctalia": 'echo "noctalia $*" >> "$JOURNAL"; [ -e "$ETAT/vivant" ]',
    "notify-send": 'echo "notify-send $*" >> "$JOURNAL"',
    "sleep": "exit 0",
}


class ShellMsg(unittest.TestCase):
    def lancer(self, *etat):
        d = tempfile.TemporaryDirectory(prefix="nc-shell-msg-"); self.addCleanup(d.cleanup)
        root = Path(d.name); b = root / "bin"; b.mkdir(); (root / "etat").mkdir()
        for nom, corps in FAUX.items():
            (b / nom).write_text("#!/bin/sh\n" + corps + "\n"); (b / nom).chmod(0o755)
        for e in etat:
            (root / "etat" / e).touch()
        env = dict(os.environ, HOME=str(root), PATH=f"{b}:/usr/bin:/bin", JOURNAL=str(root / "journal"), ETAT=str(root / "etat"))
        r = subprocess.run(["bash", str(MSG), "keys"], env=env, capture_output=True, text=True, timeout=10)
        journal = (root / "journal").read_text() if (root / "journal").exists() else ""
        return r.returncode, journal

    def test_noctalia_vivant_message_direct(self):
        code, j = self.lancer("vivant")
        self.assertEqual(code, 0, j)
        self.assertNotIn("systemctl", j)
        self.assertIn("noctalia msg panel-toggle nc/keys:main", j)

    def test_noctalia_arrete_relance_puis_message(self):
        code, j = self.lancer("demarre")
        self.assertEqual(code, 0, j)
        self.assertIn("systemctl --user start noctalia.service", j)
        self.assertIn("noctalia msg panel-toggle nc/keys:main", j)
        self.assertNotIn("notify-send", j)

    def test_noctalia_injoignable_notification(self):
        code, j = self.lancer()
        self.assertEqual(code, 1, j)
        self.assertIn("notify-send -u critical", j)
        self.assertNotIn("panel-toggle", j)


if __name__ == "__main__":
    unittest.main()

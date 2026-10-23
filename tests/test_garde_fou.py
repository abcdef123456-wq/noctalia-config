"""Garde-fou des tests (tests/_isolation.py) : les commandes qui touchent la session (notifications, Hyprland, île…)
sont des faux qui notent leurs appels dans un journal, jamais les vraies."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from tests import _isolation

FAUX = Path(os.environ["NC_TEST_FAUX"])
JOURNAL = Path(os.environ["NC_TEST_JOURNAL"])


class GardeFou(unittest.TestCase):
    def lancer(self, *args, **kw):
        avant = JOURNAL.read_text()
        r = subprocess.run(list(args), capture_output=True, text=True, timeout=10, **kw)
        return r, JOURNAL.read_text()[len(avant):].splitlines()

    def test_faux_en_tete_du_path(self):
        self.assertTrue(os.environ["PATH"].startswith(str(FAUX) + os.pathsep))
        for nom in _isolation.FAUX:
            self.assertEqual(Path(shutil.which(nom)).parent, FAUX, nom)

    def test_notify_send_note_au_journal(self):
        """Depuis un sous-processus (comme un script du dépôt), notify-send écrit au journal, rien à l'écran."""
        r, appels = self.lancer("sh", "-c", 'notify-send -a Sessions "Titre" "Corps"')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(appels, ["notify-send -a Sessions Titre Corps"])

    def test_hyprctl(self):
        r, appels = self.lancer("hyprctl", "dispatch", "exec", "kitty")
        self.assertEqual((r.returncode, r.stdout.strip()), (0, "ok"))
        self.assertEqual(appels, ["hyprctl dispatch exec kitty"])
        for args, attendu in ((["monitors", "-j"], []), (["-j", "clients"], []), (["activewindow", "-j"], {}),
                              (["-j", "getoption", "general:gaps_in"], {})):
            r, _ = self.lancer("hyprctl", *args)
            self.assertEqual(json.loads(r.stdout), attendu, args)

    def test_un_faux_du_test_passe_devant(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "notify-send").write_text('#!/bin/sh\necho le-mien\n')
            (Path(d) / "notify-send").chmod(0o755)
            env = dict(os.environ, PATH=d + os.pathsep + os.environ["PATH"])
            r, appels = self.lancer("sh", "-c", "notify-send x", env=env)
        self.assertEqual((r.stdout.strip(), appels), ("le-mien", []))

    def test_vrais_outils_gardes(self):
        for nom in ("sh", "python3", "git", "flock", "timeout"):
            chemin = shutil.which(nom)
            if chemin:
                self.assertNotEqual(Path(chemin).parent, FAUX, nom)

    @unittest.skipUnless(os.environ.get("NC_TEST_VRAI_QS"), "Quickshell absent : pas de faux qs")
    def test_qs_ipc_jamais_vers_la_vraie_ile(self):
        self.assertEqual(Path(shutil.which("qs")).parent, FAUX)
        for args in (["-c", "nc-ile", "ipc", "call", "ile", "montrer"], ["ipc", "call", "x", "y"], ["-c", "nc-ile"]):
            r, appels = self.lancer("qs", *args)
            self.assertEqual(r.returncode, 0)
            self.assertEqual(appels, ["qs " + " ".join(args)])

    @unittest.skipUnless(os.environ.get("NC_TEST_VRAI_QS"), "Quickshell absent : pas de faux qs")
    def test_qs_fichier_vers_le_vrai(self):
        r, appels = self.lancer("qs", "--help")
        self.assertEqual(appels, ["qs --help"])                        # sans -p : seulement noté
        r, appels = self.lancer("qs", "-p", "/nexiste/pas.qml")        # avec -p : le vrai qs répond
        self.assertEqual(appels, [])
        self.assertNotEqual(r.returncode, 0)


if __name__ == "__main__":
    unittest.main()

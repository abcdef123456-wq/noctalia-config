"""Ce qui rendait des suites instables sans rapport avec le code testé : qs orphelin après un délai, limite de processus trop proche."""
import os
from pathlib import Path
import signal
import subprocess
import tempfile
import time
import unittest

from tests import _isolation


class Bancs(unittest.TestCase):
    def test_delai_depasse_ne_laisse_aucun_orphelin(self):
        """Le premier processus lance un enfant, comme dbus-run-session lance qs : au délai, les deux partent."""
        with tempfile.TemporaryDirectory() as d:
            note = Path(d) / "enfant"
            script = 'sleep 30 & echo $! > "$1"; wait'
            debut = time.monotonic()
            with self.assertRaises(subprocess.TimeoutExpired):
                _isolation.executer_sans_orphelin(["sh", "-c", script, "sh", str(note)], 1)
            # Sans le groupe, l'enfant garde les tubes ouverts : le banc attendrait sa fin
            self.assertLess(time.monotonic() - debut, 15, "le banc a attendu l'enfant au lieu de le tuer")
            enfant = int(note.read_text())
            self.addCleanup(lambda: self.tuer(enfant))
            fin = time.monotonic() + 5
            while self.vivant(enfant) and time.monotonic() < fin:
                time.sleep(0.02)
            self.assertFalse(self.vivant(enfant), "l'enfant a survécu au délai")

    def test_sortie_normale_rend_code_et_textes(self):
        r = _isolation.executer_sans_orphelin(["sh", "-c", "echo sortie; echo erreur >&2; exit 3"], 10)
        self.assertEqual((r.returncode, r.stdout, r.stderr), (3, "sortie\n", "erreur\n"))

    @staticmethod
    def vivant(pid):
        try:
            with open(f"/proc/{pid}/stat") as f:
                return f.read().rsplit(")", 1)[1].split()[0] != "Z"
        except OSError:
            return False

    @staticmethod
    def tuer(pid):
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass

    def test_avis_seulement_pres_de_la_limite(self):
        self.assertEqual(_isolation.avis_limite_de_processus(limite=3000, fils=2700), "")
        self.assertIn("ulimit -u 3000", _isolation.avis_limite_de_processus(limite=3000, fils=2701))
        self.assertEqual(_isolation.avis_limite_de_processus(limite=_isolation.resource.RLIM_INFINITY, fils=10 ** 6), "")


class DossierCourt(unittest.TestCase):
    """dossier_court() : un dossier court, à nous, en 0700 ; jamais un dossier d'un autre ou trop ouvert."""

    def test_dossier_court_a_nous(self):
        d = _isolation.dossier_court()
        st = os.lstat(d)
        self.assertLessEqual(len(d), 24)
        self.assertEqual(st.st_uid, os.getuid())
        self.assertFalse(os.path.islink(d))
        if d.startswith("/tmp/nct-"):
            self.assertEqual(st.st_mode & 0o777, 0o700)
        self.assertNotIn("claude", d)

    def test_trop_ouvert_ou_lien_refuse(self):
        from unittest import mock
        vrai_lstat = os.lstat
        with tempfile.TemporaryDirectory() as t:
            ouvert = Path(t) / "ouvert"
            ouvert.mkdir()
            ouvert.chmod(0o777)
            lien = Path(t) / "lien"
            lien.symlink_to(ouvert)
            fichier = Path(t) / "fichier"
            fichier.write_text("")
            fichier.chmod(0o600)
            for cible in (ouvert, lien, fichier):
                with self.subTest(cible=cible.name), \
                        mock.patch.object(_isolation.os, "mkdir", side_effect=FileExistsError), \
                        mock.patch.object(_isolation.os, "lstat", side_effect=lambda _d, c=cible: vrai_lstat(c)):
                    self.assertEqual(_isolation.dossier_court(), tempfile.gettempdir())


if __name__ == "__main__":
    unittest.main()

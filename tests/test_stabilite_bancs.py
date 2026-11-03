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


if __name__ == "__main__":
    unittest.main()

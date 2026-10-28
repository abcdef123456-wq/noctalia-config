"""nc-claude ecrire vers OpenCode 2 (service de fond) : le message part en ARGUMENT de « opencode run --session ID TEXTE ».
Un texte qui commence par un tiret (« --auto », « -x ») y serait lu comme une option : il est refusé sans rien lancer."""
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest

NC_CLAUDE = Path(__file__).resolve().parents[1] / "home/.local/bin/nc-claude"


class OpencodeTiret(unittest.TestCase):
    def setUp(self):
        os.makedirs("/tmp/claude-1000", exist_ok=True)
        d = tempfile.TemporaryDirectory(prefix="nc-oc-", dir="/tmp/claude-1000")
        self.addCleanup(d.cleanup)
        r = Path(d.name)
        for s in ("home", "run", "bin"):
            (r / s).mkdir()
        (r / "run/nc-claude").mkdir()
        (r / "run/nc-claude/etat.json").write_text(json.dumps({"sessions": {
            "opencode-ses_test": {"agent": "opencode", "cwd": "~", "etat": "attente", "maj": 0}}}))
        self.journal = r / "appels"
        faux = r / "bin/opencode"
        faux.write_text(f"#!/bin/sh\nprintf '%s\\n' \"$@\" >> {self.journal}\necho FIN >> {self.journal}\n")
        faux.chmod(faux.stat().st_mode | stat.S_IEXEC)
        self.env = {"HOME": str(r / "home"), "XDG_RUNTIME_DIR": str(r / "run"), "PATH": f"{r / 'bin'}:/usr/bin:/bin",
                    "NC_LANGUE": "fr", "TMPDIR": str(r)}

    def ecrire(self, texte):
        return subprocess.run([sys.executable, str(NC_CLAUDE), "ecrire", "opencode-ses_test", texte], env=self.env,
                              capture_output=True, text=True, timeout=30, stdin=subprocess.DEVNULL)

    def appels(self):
        for _ in range(50):                    # opencode est lancé détaché : on lui laisse le temps d'écrire
            if self.journal.exists() and self.journal.read_text().endswith("FIN\n"):
                break
            subprocess.run(["sleep", "0.1"])
        return self.journal.read_text() if self.journal.exists() else ""

    def test_tiret_en_tete_refuse_sans_lancer_opencode(self):
        for texte in ("--auto", "-x", "  --server=http://198.51.100.1", "-f fichier"):
            r = self.ecrire(texte)
            self.assertNotEqual(r.returncode, 0, texte)
            self.assertIn("commence ton message par un mot", r.stderr, texte)
        self.assertFalse(self.journal.exists(), "opencode ne doit jamais être lancé")

    def test_texte_ordinaire_part_en_argument(self):
        r = self.ecrire("bonjour, continue")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.appels().splitlines(), ["run", "--session", "ses_test", "bonjour, continue", "FIN"])


if __name__ == "__main__":
    unittest.main()

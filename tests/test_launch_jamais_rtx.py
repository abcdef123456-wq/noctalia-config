"""nc-launch : les applis de GPU_JAMAIS_RTX (terminaux, gestionnaires de fichiers…) ne vont jamais sur la carte NVIDIA,
même quand la règle la permet : elles n'en profitent pas et la garderaient éveillée des heures (vu : deux kitty sur la
RTX, restée allumée une fois sur batterie)."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

LAUNCH = Path(__file__).resolve().parents[1] / "home/.local/bin/nc-launch"


class JamaisSurLaRtx(unittest.TestCase):
    def lancer(self, *cmd, reglage=None):
        with tempfile.TemporaryDirectory(prefix="nc-launch-") as d:
            h = Path(d); b = h / ".local/bin"; b.mkdir(parents=True); run = h / "run"; run.mkdir()
            (run / "nc-gpu-default").write_text("nvidia\n")
            (b / "nvidia-run").write_text('#!/bin/sh\necho "RTX $*"\n'); (b / "nvidia-run").chmod(0o755)
            if reglage is not None:
                (h / ".config/nc").mkdir(parents=True)
                (h / ".config/nc/reglages.conf").write_text(f'GPU_JAMAIS_RTX="{reglage}"\n')
            env = dict(os.environ, HOME=d, XDG_RUNTIME_DIR=str(run))
            return subprocess.run([str(LAUNCH), *cmd], env=env, capture_output=True, text=True, timeout=10).stdout.strip()

    def test_terminal_sur_l_integree(self):
        self.assertEqual(self.lancer("echo", "kitty"), "RTX echo kitty")       # « echo » : une appli ordinaire
        with tempfile.TemporaryDirectory() as d:
            kitty = Path(d) / "kitty"; kitty.write_text('#!/bin/sh\necho "integree $*"\n'); kitty.chmod(0o755)
            self.assertEqual(self.lancer(str(kitty), "-1"), "integree -1")
            self.assertEqual(self.lancer("env", "A=1", str(kitty)), "integree")
            # Réglage personnel : la liste remplace celle par défaut
            self.assertEqual(self.lancer(str(kitty), reglage="foot"), "RTX " + str(kitty))
            self.assertEqual(self.lancer("echo", "x", reglage="foot echo"), "x")


if __name__ == "__main__":
    unittest.main()

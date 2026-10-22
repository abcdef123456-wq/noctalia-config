"""TLP sur batterie (mesuré : 26,2 W → 23,6 W au repos) : EPP balance_power et ASPM powersupersave dans 10-nc.conf ;
un fichier TLP à soi n'est jamais modifié, install.sh y conseille seulement balance_power en une ligne."""
from pathlib import Path
import os
import re
import subprocess
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]


class TlpBatterie(unittest.TestCase):
    def test_reglages_du_depot(self):
        conf = (REPO / "system/tlp.d/10-nc.conf").read_text()
        self.assertRegex(conf, r"(?m)^CPU_ENERGY_PERF_POLICY_ON_BAT=balance_power\b")
        self.assertRegex(conf, r"(?m)^PCIE_ASPM_ON_BAT=powersupersave\b")
        self.assertRegex(conf, r"(?m)^CPU_BOOST_ON_BAT=1\b")          # rien de visible : le turbo reste

    def test_fichier_perso_conseil_sans_modification(self):
        source = (REPO / "install.sh").read_text()
        m = re.search(r"(?ms)^  tlp_conseil_perso\(\) \{.*?^  \}\n", source)
        self.assertIsNotNone(m)
        with tempfile.TemporaryDirectory() as d:
            perso = Path(d) / "10-legion-pro5.conf"
            perso.write_text("CPU_ENERGY_PERF_POLICY_ON_BAT=balance_performance\n")
            autre = Path(d) / "20-autre.conf"
            autre.write_text("CPU_ENERGY_PERF_POLICY_ON_BAT=balance_power\n")
            avant = perso.read_text()
            script = 't() { printf %s "$1"; }; info() { echo "INFO $*"; }\n' + m.group(0) + f'tlp_conseil_perso "{perso}" "{autre}"\n'
            r = subprocess.run(["bash", "-c", script], capture_output=True, text=True, env=dict(os.environ, HOME=d))
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(r.stdout.count("INFO"), 1, r.stdout)
            self.assertIn(f"balance_power dans {perso}", r.stdout)
            self.assertEqual(perso.read_text(), avant)


if __name__ == "__main__":
    unittest.main()

"""Connexion.qml : l'île démarre même si Quickshell a été compilé sans Quickshell.Networking (ancienne compilation
Debian, -DNETWORK=OFF) ; elle suppose alors qu'on est en ligne. Avant, toute l'île plantait au chargement."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

QML = Path(__file__).resolve().parents[1] / "home/.config/quickshell/nc-ile"


@unittest.skipUnless(shutil.which("qs"), "Quickshell requis")
class ConnexionIle(unittest.TestCase):
    def charger(self, module):
        with tempfile.TemporaryDirectory(prefix="nc-connexion-") as d:
            root = Path(d)
            (root / "run").mkdir(mode=0o700)
            (root / "Connexion.qml").write_text((QML / "Connexion.qml").read_text().replace("Quickshell.Networking", module))
            (root / "qmldir").write_text("singleton Connexion 1.0 Connexion.qml\n")
            (root / "shell.qml").write_text('import QtQuick\nimport Quickshell\nShellRoot {\n'
                                            '  Timer { interval: 300; running: true; onTriggered: { console.log("RESULTAT " + Connexion.enLigne + " " + Connexion.disponible); Qt.quit() } }\n}\n')
            env = dict(os.environ, HOME=d, XDG_RUNTIME_DIR=str(root / "run"), QT_QPA_PLATFORM="offscreen")
            env.pop("WAYLAND_DISPLAY", None)
            r = subprocess.run(["qs", "--no-color", "-p", str(root / "shell.qml")], env=env, text=True, capture_output=True, timeout=20)
            return r.stdout + r.stderr

    def test_sans_le_module_l_ile_demarre(self):
        sortie = self.charger("Quickshell.ModuleAbsent")
        self.assertNotIn("Failed to load configuration", sortie)
        self.assertIn("RESULTAT true false", sortie, "supposé en ligne, module signalé absent")

    def test_avec_le_module(self):
        sortie = self.charger("Quickshell.Networking")
        self.assertRegex(sortie, r"RESULTAT (true|false) true")


if __name__ == "__main__":
    unittest.main()

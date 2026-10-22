"""Plugins Noctalia : aucun champ qui exige une plugin_api plus récente que celle déclarée. Sinon Noctalia ignore TOUT
le plugin (vu en 5.3.0 : « widget entry 'titre': hover_highlight requires plugin_api >= 34 », et le titre des fenêtres
avait disparu de la barre). Les plugins restent à l'API 32, celle des Noctalia v5 les plus anciennes visées."""
from pathlib import Path
import re
import tomllib
import unittest

PLUGINS = Path(__file__).resolve().parents[1] / "home/.local/share/noctalia/plugins"
API_MAX = 32
# Champ (de plugin.toml, ou d'une entrée [[widget]] / [[panel]]) → plugin_api minimale qui l'accepte
EXIGE = {"hover_highlight": 34}


class ApiDesPlugins(unittest.TestCase):
    def test_champs_compatibles(self):
        for f in sorted(PLUGINS.glob("*/plugin.toml")):
            with self.subTest(plugin=f.parent.name):
                d = tomllib.loads(f.read_text())
                api = d.get("plugin_api", 0)
                self.assertLessEqual(api, API_MAX, "plugin_api trop récente pour les Noctalia v5 visées")
                entrees = [d] + d.get("widget", []) + d.get("panel", [])
                for e in entrees:
                    for champ, mini in EXIGE.items():
                        self.assertNotIn(champ, e, f"{champ} exige plugin_api >= {mini} (déclarée : {api})")


if __name__ == "__main__":
    unittest.main()

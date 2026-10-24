"""nc-theme-sync : l'accent de l'île (palette-ile.json, repris par Firefox) reste lisible sur le fond.

Les schémas clairs prédéfinis de Noctalia donnent un accent sous 3:1 sur leur fond (Noctalia-default-light 2,55:1,
Eldritch-light 1,3:1) : accent_lisible ne bouge que sa luminosité, et laisse tel quel un accent qui passe déjà (le cas
des palettes tirées d'un fond d'écran)."""
import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

BIN = Path(__file__).resolve().parent.parent / "home/.local/bin"
SCHEMAS = Path("/etc/xdg/quickshell/noctalia-shell/Assets/ColorScheme")

# (mPrimary, mOnPrimary, mSurface, mOnSurface) de schémas publics de Noctalia et d'une palette Material claire
CLAIRS = {
    "Noctalia-default-light": ("#5d65f5", "#dadcff", "#e6e8fa", "#0e0e43"),
    "Eldritch-light": ("#37f499", "#171928", "#ffffff", "#171928"),
    "Ayu-light": ("#FF8F40", "#F8F9FA", "#F8F9FA", "#5C6166"),
    "Gruvbox-light": ("#98971a", "#fbf1c7", "#fbf1c7", "#3c3836"),
    "Rosepine-light": ("#d7827e", "#faf4ed", "#fffaf3", "#575279"),
    "material-clair": ("#33618d", "#ffffff", "#f8f9ff", "#191c20"),
    # Accents aux extrêmes : tone() partait déjà d'une borne de luminosité et rendait la couleur telle quelle
    "blanc-sur-clair": ("#ffffff", "#000000", "#f5f5f5", "#101010"),
    "presque-blanc": ("#f5f9fd", "#000000", "#1fd00d", "#000000"),
}
EXTREMES_SOMBRES = {"noir-sur-sombre": ("#000000", "#ffffff", "#101010", "#f0f0f0")}
SOMBRES = {
    "Noctalia-default-dark": ("#fff59b", "#0e0e43", "#070722", "#f3edf7"),
    "Catppuccin-dark": ("#cba6f7", "#11111b", "#1e1e2e", "#cdd6f4"),
    "Kanagawa-dark": ("#76946a", "#1f1f28", "#1f1f28", "#c8c093"),
    "fond-d-ecran": ("#67b3e4", "#182025", "#13212a", "#f2f2f3"),
}


def charger():
    with tempfile.TemporaryDirectory(prefix="nc-theme-sync-") as d, mock.patch.dict(os.environ, {"HOME": d}):
        chargeur = importlib.machinery.SourceFileLoader("nc_theme_sync", str(BIN / "nc-theme-sync"))
        m = importlib.util.module_from_spec(importlib.util.spec_from_loader(chargeur.name, chargeur))
        chargeur.exec_module(m)
    return m


class AccentLisible(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = charger()

    def verifier(self, nom, primary, sur, bg, fg):
        m = self.m
        dark = m.luminance(m.hex_to_rgb(bg)) < 0.18
        accent, sur_accent = m.accent_lisible(primary, sur, bg, fg, dark)
        with self.subTest(schema=nom):
            self.assertGreaterEqual(m.contrast(m.hex_to_rgb(accent), m.hex_to_rgb(bg)), 3.0, (nom, accent))
            self.assertGreaterEqual(m.contrast(m.hex_to_rgb(sur_accent), m.hex_to_rgb(accent)), 4.5, (nom, sur_accent))
        return accent, sur_accent

    def test_schemas_clairs_releves_a_3_pour_1(self):
        for nom, (primary, sur, bg, fg) in CLAIRS.items():
            self.verifier(nom, primary, sur, bg, fg)
        # Le cas mesuré le plus bas (1,3:1) change vraiment, en gardant sa teinte
        accent, _ = self.verifier("Eldritch-light", *CLAIRS["Eldritch-light"])
        self.assertNotEqual(accent.lower(), "#37f499")
        h_avant = self.m.rgb_to_oklch(self.m.hex_to_rgb("#37f499"))[2]
        h_apres = self.m.rgb_to_oklch(self.m.hex_to_rgb(accent))[2]
        self.assertLess(abs((h_apres - h_avant + 180) % 360 - 180), 8)

    def test_accent_aux_extremes(self):
        for nom, (primary, sur, bg, fg) in EXTREMES_SOMBRES.items():
            self.verifier(nom, primary, sur, bg, fg)

    def test_accent_deja_lisible_garde_tel_quel(self):
        # Palette tirée d'un fond d'écran (7:1) et schémas sombres : accent et texte sur l'accent identiques à l'octet
        for nom, (primary, sur, bg, fg) in SOMBRES.items():
            with self.subTest(schema=nom):
                self.assertEqual(self.verifier(nom, primary, sur, bg, fg), (primary, sur))

    @unittest.skipUnless(SCHEMAS.is_dir(), "schémas de Noctalia absents")
    def test_tous_les_schemas_installes(self):
        vus = 0
        for f in sorted(SCHEMAS.glob("*/*.json")):
            d = json.loads(f.read_text())
            for mode in ("light", "dark"):
                c = d.get(mode)
                if isinstance(c, dict) and all(k in c for k in ("mPrimary", "mSurface", "mOnSurface")):
                    self.verifier(f"{f.stem}-{mode}", c["mPrimary"], c.get("mOnPrimary", c["mSurface"]),
                                  c["mSurface"], c["mOnSurface"])
                    vus += 1
        self.assertGreater(vus, 0)


if __name__ == "__main__":
    unittest.main()

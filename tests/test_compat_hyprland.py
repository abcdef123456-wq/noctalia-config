"""Compatibilité avec Hyprland 0.55 (Debian 13) et 0.56 (Arch, Fedora, openSUSE) : bornes des réglages que Hyprland
refuse au-delà, couleur d'ombre des deux formes, contournement de la barre seulement avant 0.56, version comparée."""
from pathlib import Path
import re
import shutil
import subprocess
import unittest

REPO = Path(__file__).resolve().parents[1]
HYPR = REPO / "home/.config/hypr"


class Bornes(unittest.TestCase):
    def test_arrondi_et_pointeur_20_au_plus(self):
        reglages = (REPO / "home/.local/bin/nc-reglages").read_text()
        for cle in ("FENETRES_ARRONDI", "CURSEUR_CACHER"):
            bloc = reglages[reglages.index(f'R("{cle}"'):]
            bloc = bloc[:bloc.index("\n    R(")]
            self.assertRegex(bloc, r"maxi=20\b", cle)
        apparence = (HYPR / "nc/apparence.lua").read_text()
        self.assertIn('math.min(20, nc.reglage("FENETRES_ARRONDI", 14))', apparence, "une ancienne valeur au-delà est ramenée")
        self.assertIn('math.min(20, nc.reglage("CURSEUR_CACHER", 8))', apparence)


@unittest.skipUnless(shutil.which("lua"), "Lua requis")
class Versions(unittest.TestCase):
    def lua(self, code):
        r = subprocess.run(["lua", "-"], input=code, text=True, capture_output=True, timeout=10)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return r.stdout

    def test_hypr_min(self):
        source = (HYPR / "hyprland.lua").read_text()
        bloc = source[source.index("nc.hypr = { 0, 0, 0 }"):source.index("-- Ce que Hyprland 0.55 ne donne pas")]
        for version, attendu in (("0.55.2", "false true"), ("0.56.2", "true true"), ("0.57.0", "true true")):
            out = self.lua('nc = {} hl = { version = function() return "%s" end }\n%s\nprint(nc.hypr_min(0, 56, 0), nc.hypr_min(0, 55, 0))'
                           % (version, bloc))
            self.assertEqual(out.strip().replace("\t", " "), attendu, version)

    def test_couleur_d_ombre_des_deux_formes(self):
        source = (HYPR / "nc/automatismes.lua").read_text()
        argb = source[source.index("local function argb(c)"):source.index("local function rgba(")]
        ligne = re.search(r"local a, r, g, b = argb\(.*base_ombre\)", source)[0]
        for ombre in ('{ colors = { "0xee1a1a1a" } }', '"0xee1a1a1a"'):
            out = self.lua(f"{argb}\nlocal base_ombre = {ombre}\n{ligne}\nprint(a, r)")
            self.assertEqual(out.split(), ["238", "26"], ombre)

    def test_barre_apres_plein_ecran_seulement_avant_056(self):
        source = (HYPR / "nc/automatismes.lua").read_text()
        bloc = source[source.index('hl.on("window.fullscreen"'):source.index("-- ── Halo musical")]
        self.assertIn("not nc.hypr_min(0, 56, 0)", bloc)


if __name__ == "__main__":
    unittest.main()

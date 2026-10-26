"""nc-theme-sync : l'accent de l'île (palette-ile.json, repris par Firefox) reste lisible sur le fond.

Les schémas clairs prédéfinis de Noctalia donnent un accent sous 3:1 sur leur fond (Noctalia-default-light 2,55:1,
Eldritch-light 1,3:1) : accent_lisible ne bouge que sa luminosité, et laisse tel quel un accent qui passe déjà (le cas
des palettes tirées d'un fond d'écran)."""
import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import subprocess
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


class TextesDeCarte(unittest.TestCase):
    """texteSec et texteDoux de palette-ile.json restent lisibles (4,5:1) sur la carte, palette claire comme sombre."""
    PALETTES = {
        # mOnSurfaceVariant volontairement pâle sur fond clair, et sombre sur fond sombre : le pire cas
        "claire": {"mSurface": "#f8f9ff", "mOnSurface": "#191c20", "mPrimary": "#33618d", "mOnPrimary": "#ffffff",
                   "mOnSurfaceVariant": "#b8bcc4"},
        "sombre": {"mSurface": "#1e1e2e", "mOnSurface": "#cdd6f4", "mPrimary": "#cba6f7", "mOnPrimary": "#11111b",
                   "mOnSurfaceVariant": "#4a4d60"},
    }

    @classmethod
    def setUpClass(cls):
        cls.m = charger()

    def palette(self, couleurs):
        with tempfile.TemporaryDirectory(prefix="nc-theme-sync-") as d:
            home = Path(d)
            (home / ".config/noctalia").mkdir(parents=True)
            (home / ".config/noctalia/colors.json").write_text(json.dumps(couleurs))
            (home / ".local/bin").mkdir(parents=True)
            for nom in ("nc-icones", "nc-firefox"):
                (home / ".local/bin" / nom).write_text("#!/bin/sh\nexit 0\n")
                (home / ".local/bin" / nom).chmod(0o755)
            env = dict(os.environ, HOME=d, XDG_CONFIG_HOME=d + "/.config", LANG="fr_FR.UTF-8", LC_ALL="fr_FR.UTF-8")
            r = subprocess.run([str(BIN / "nc-theme-sync")], env=env, capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            return json.loads((home / ".config/nc/palette-ile.json").read_text())

    def test_textes_lisibles_sur_la_carte(self):
        m = self.m
        for nom, couleurs in self.PALETTES.items():
            p = self.palette(couleurs)
            carte = m.hex_to_rgb(p["carte"])
            for cle in ("texteSec", "texteDoux"):
                with self.subTest(palette=nom, cle=cle):
                    self.assertGreaterEqual(m.contrast(m.hex_to_rgb(p[cle]), carte), 4.5, (p[cle], p["carte"]))

    def test_rose_tire_de_la_palette(self):
        m = self.m
        for nom, couleurs in self.PALETTES.items():
            p = self.palette(couleurs)
            with self.subTest(palette=nom):
                self.assertIn("rose", p)
                self.assertNotEqual(p["rose"], p["violet"])
                self.assertGreaterEqual(m.contrast(m.hex_to_rgb(p["rose"]), m.hex_to_rgb(couleurs["mSurface"])), 4.5, p["rose"])


class CouleursIlisibles(unittest.TestCase):
    """colors.json aux formats variés ou illisibles : jamais de plantage, thème kitty en « #rrggbb » ; texte lisible ;
    kdeglobals : le thème d'icônes de l'utilisateur n'est pas réécrit."""
    BASE = {"mSurface": "#13212a", "mOnSurface": "#f2f2f3", "mPrimary": "#67b3e4", "mOnPrimary": "#182025"}

    def lancer(self, couleurs, kdeglobals=None):
        tmp = tempfile.TemporaryDirectory(prefix="nc-theme-sync-")
        self.addCleanup(tmp.cleanup)
        d = tmp.name
        home = Path(d)
        (home / ".config/noctalia").mkdir(parents=True)
        (home / ".config/noctalia/colors.json").write_text(json.dumps(couleurs))
        (home / ".local/bin").mkdir(parents=True)
        for nom in ("nc-icones", "nc-firefox"):
            (home / ".local/bin" / nom).write_text("#!/bin/sh\nexit 0\n")
            (home / ".local/bin" / nom).chmod(0o755)
        if kdeglobals is not None:
            (home / ".local/share/color-schemes").mkdir(parents=True)
            (home / ".local/share/color-schemes/noctalia.colors").write_text("[Colors:View]\nBackgroundNormal=1,2,3\n")
            (home / ".config/kdeglobals").write_text(kdeglobals)
        env = dict(os.environ, HOME=d, XDG_CONFIG_HOME=d + "/.config", XDG_CACHE_HOME=d + "/.cache", TMPDIR=d,
                   LANG="fr_FR.UTF-8", LC_ALL="fr_FR.UTF-8", NC_LANGUE="fr")
        r = subprocess.run(["python3", str(BIN / "nc-theme-sync")], env=env, capture_output=True, text=True, timeout=60)
        return home, r

    def kitty(self, home):
        return dict(l.split(None, 1) for l in (home / ".config/kitty/themes/noctalia-dynamic.conf").read_text().splitlines()
                    if l and not l.startswith("#"))

    def test_formats_de_couleur(self):
        valeurs = {"#13212aff": "#13212a", "13212a": "#13212a", "rgb(19, 33, 42)": "#13212a", "#123": "#112233",
                   "": None, "pas une couleur": None, 42: None, None: None}
        for v, attendu in valeurs.items():
            with self.subTest(valeur=v):
                couleurs = dict(self.BASE, mSurface=v, mPrimary=v, mSecondary=v, mOutline=v)
                home, r = self.lancer(couleurs)
                self.assertEqual(r.returncode, 0, r.stderr)
                k = self.kitty(home)
                for cle in ("foreground", "background", "active_border_color", "active_tab_background", "inactive_border_color",
                            "tab_bar_background", "selection_foreground", "cursor_text_color"):
                    self.assertRegex(k[cle], r"^#[0-9a-f]{6}$", (cle, k[cle]))
                if attendu:
                    self.assertEqual(k["background"], attendu)
                else:
                    self.assertIn("illisible", r.stderr, "le repli est dit dans le journal")
                self.assertTrue((home / ".config/nc/palette-ile.json").is_file())

    def test_colors_json_pas_un_objet(self):
        home, r = self.lancer(["#fff"])
        self.assertNotEqual(r.returncode, 0)
        self.assertNotIn("Traceback", r.stderr)

    def test_texte_du_terminal_lisible(self):
        m = charger()
        for nom, (fond, texte) in {"blanc-sur-blanc": ("#ffffff", "#ffffff"), "gris-moyen": ("#777777", "#7a7a7a"),
                                   "noir-sur-noir": ("#000000", "#050505"), "gris-sur-gris": ("#777777", "#777777"),
                                   "deja-bon": ("#13212a", "#f2f2f3")}.items():
            with self.subTest(cas=nom):
                home, r = self.lancer(dict(self.BASE, mSurface=fond, mOnSurface=texte, mOnSurfaceVariant=texte))
                self.assertEqual(r.returncode, 0, r.stderr)
                k = self.kitty(home)
                self.assertGreaterEqual(m.contrast(m.hex_to_rgb(k["foreground"]), m.hex_to_rgb(k["background"])), 4.5, k["foreground"])
                if nom == "deja-bon":
                    self.assertEqual(k["foreground"], texte, "un texte déjà lisible reste tel quel")
                p = json.loads((home / ".config/nc/palette-ile.json").read_text())
                self.assertEqual(p["texte"], k["foreground"])

    def test_kdeglobals_icones_non_reecrites(self):
        # Thème d'icônes choisi par l'utilisateur : gardé
        home, r = self.lancer(self.BASE, "[Icons]\nTheme=Mon-Theme\n")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("Theme=Mon-Theme", (home / ".config/kdeglobals").read_text())
        # Pas de clé : posée (Papirus-Dark tant que le thème NC n'existe pas)
        home, r = self.lancer(self.BASE, "[General]\nA=1\n")
        self.assertIn("Theme=Papirus-Dark", (home / ".config/kdeglobals").read_text())
        # … et NC quand nc-icones l'a dessiné
        home, r = self.lancer(self.BASE, "[General]\nA=1\n")
        nc = home / ".local/share/icons/NC"
        nc.mkdir(parents=True)
        (nc / "index.theme").write_text("[Icon Theme]\n")
        (home / ".config/kdeglobals").write_text("[General]\nA=1\n")
        env = dict(os.environ, HOME=str(home), XDG_CONFIG_HOME=str(home / ".config"), TMPDIR=str(home), NC_LANGUE="fr")
        subprocess.run(["python3", str(BIN / "nc-theme-sync")], env=env, capture_output=True, text=True, timeout=60)
        self.assertIn("Theme=NC", (home / ".config/kdeglobals").read_text())


if __name__ == "__main__":
    unittest.main()

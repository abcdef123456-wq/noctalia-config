"""Table « noctalia » d'un thème : un réglage de la personne gagne sur le thème, et seules les clés de la liste blanche
passent (jamais compositor_blur, ni flou, ni verrou, ni fond). apple et oled sont figés à l'octet (contenu de A7 : barre, bureaux, dock ;
barres épaissies pour que l'île fermée y tienne, dock visible d'apple qui réserve sa place : test_defauts_ecran_v3). Faux HOME, faux noctalia ; jamais le vrai HOME."""
import re
import unittest

from tests import test_themes as tt

# zy-reglages.toml d'apple et d'oled tels qu'ils sortaient de 6c144c5 (sans police : fc-list est un faux vide), barres
# épaissies et reserve_space d'apple en plus (défauts vus à l'écran, test_defauts_ecran_v3)
ENTETE = "# Écrit par nc-reglages (tes réglages de Noctalia). Ne pas éditer : nc-reglages.\n\n"
APPLE = ENTETE + ('[lockscreen]\nblur_intensity = 0.35\ntransition = ["fade"]\n\n'
                  '[dock]\nposition = "bottom"\nenabled = true\nauto_hide = false\nmagnification = true\nicon_size = 56\nreserve_space = true\n\n'
                  '[bar.default]\ncapsule = false\nbackground_opacity = 0.55\nposition = "top"\nmargin_edge = 0\nthickness = 40\n\n'
                  '[widget.workspaces]\nstyle = "minimal"\nshow_labels = false\n\n'
                  '[wallpaper]\ntransition = ["fade"]\ndirectory = "@FONDS@"\n')
OLED = ENTETE + ('[theme]\npure_black_dark = true\n\n'
                 '[bar.default]\nposition = "top"\nmargin_edge = 6\nthickness = 34\ncapsule = false\nbackground_opacity = 0.0\n\n'
                 '[widget.workspaces]\nstyle = "focus_hint"\nshow_labels = true\n\n'
                 '[dock]\nenabled = false\n\n[wallpaper]\ndirectory = "@FONDS@"\n')


class TableNoctalia(tt.Base):
    def setUp(self):
        super().setUp()
        faux = self.home.parent / "faux"
        (faux / "fc-list").write_text("#!/bin/sh\nexit 0\n")
        (faux / "fc-list").chmod(0o755)
        (self.home / ".config/noctalia").mkdir(parents=True, exist_ok=True)
        self.toml = self.home / ".config/noctalia/zy-reglages.toml"

    def avec_theme(self, noctalia):
        self.ecrire_theme("essai", noctalia=noctalia)
        return self.nc("set", "STYLE", "essai")

    def sortie(self, style):
        r = self.nc("set", "STYLE", style)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return re.sub(r'directory = "[^"]*"', 'directory = "@FONDS@"', self.toml.read_text(encoding="utf-8"))

    # --- l'ordre : le réglage de la personne gagne
    def test_position_du_dock_de_la_personne_gagne(self):
        self.assertEqual(self.nc("set", "DOCK_POSITION", "left").returncode, 0)
        r = self.avec_theme({"dock": {"position": "right"}})
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn('position = "left"', self.toml.read_text(encoding="utf-8"))

    def test_taille_du_dock_de_la_personne_gagne(self):
        self.assertEqual(self.nc("set", "DOCK_TAILLE", "40").returncode, 0)
        r = self.avec_theme({"dock": {"icon_size": 60}})
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        t = self.toml.read_text(encoding="utf-8")
        self.assertIn("icon_size = 40", t)
        self.assertNotIn("icon_size = 60", t)

    def test_theme_complete_ce_qui_nest_pas_regle(self):
        r = self.avec_theme({"dock": {"position": "right"}})
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn('position = "right"', self.toml.read_text(encoding="utf-8"))

    # --- la liste blanche
    def test_cles_permises(self):
        ok = {"bar.default": {"position": "bottom", "thickness": 40, "margin_ends": 12, "background_opacity": 0.5,
                              "capsule": True, "capsule_fill": "surface", "start": ["logo", "workspaces"]},
              "widget.workspaces": {"style": "minimal", "label_source": "name", "max_label_chars": 3,
                                    "focused_color": "primary"},
              "dock": {"enabled": True, "position": "left", "icon_size": 48, "magnification_scale": 1.4}}
        r = self.avec_theme(ok)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_cles_refusees(self):
        for noctalia in ({"bar.default": {"compositor_blur": True}},
                         {"lockscreen": {"blur_intensity": 0.5}},
                         {"wallpaper": {"directory": "/tmp"}},
                         {"bar.default": {"clef_inconnue": 1}},
                         {"bar.default": {"thickness": 500}},
                         {"bar.default": {"background_opacity": 3}},
                         {"bar.default": {"thickness": True}},
                         {"bar.default": {"position": "milieu"}},
                         {"bar.default": {"start": ["widget_inventé"]}},
                         {"dock": {"position": "top"}}):
            with self.subTest(noctalia=noctalia):
                r = self.avec_theme(noctalia)
                self.assertNotEqual(r.returncode, 0, r.stdout)

    # --- apple et oled : mêmes octets qu'avant
    def test_apple_identique(self):
        self.assertEqual(self.sortie("apple"), APPLE)

    def test_oled_identique(self):
        self.assertEqual(self.sortie("oled"), OLED)


if __name__ == "__main__":
    unittest.main()

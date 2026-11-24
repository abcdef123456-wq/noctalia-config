"""L'export reprend la composition native avant de masquer la barre (HOME isolé)."""
import json
import shutil
import unittest

from tests import test_barre_composition as tb


class ExportPanneaux(unittest.TestCase):
    def test_styles_aliases_et_interrupteurs_avant_masquage_natif(self):
        composition = {**tb.COMPOSE, "bar.default": {**tb.COMPOSE["bar.default"],
                       "capsule_radius": 5,
                       "capsule_group": [*tb.COMPOSE["bar.default"]["capsule_group"],
                                         {"id": "sys", "opacity": 0.4}]}}
        with tb.nc_isole(install="quickshell", style="essai", themes={"essai": tb.theme(composition)}) as (nc, sortie):
            base = sortie.with_name("config.toml")
            config = base.read_text(encoding="utf-8").replace("enable_daemon = 0", "enable_daemon = false")
            config += '\n[bar."côté arrêté"]\nposition = "left"\nenabled = false\nstart = []\ncenter = []\nend = []\n'
            base.write_text(config, encoding="utf-8")
            panneaux = sortie.parent.parent / "nc/panneaux.json"
            vals = {"BARRE_MODULAIRE": "oui", "BARRE_OPACITE": "64", "VPN_PILULE_BARRE": "oui", "VPN_MASQUER_TRAY": "oui",
                    "VPN_BOUCLIER_WIFI": "non", "POLICE": "Inter"}
            natif = tb.barre(nc, sortie, vals)["bar"]
            export = json.loads(panneaux.read_text(encoding="utf-8"))
            barres = {b["id"]: b for b in export["barres"]}
            principale = barres["default"]
            self.assertTrue(principale.get("enabled", True))
            self.assertFalse(barres["côté arrêté"]["enabled"])
            self.assertTrue(all(b["enabled"] is False for b in natif.values()))
            self.assertEqual((principale["capsule_radius"], principale["capsule_opacity"]), (5, 0.64))
            self.assertEqual(principale["center"], ["t-heure"])
            self.assertEqual(barres["bas"]["center"], ["t-taches"])
            self.assertIn("nc/vpn:vpn", principale["end"])
            groupes = {g["id"]: g for g in principale["capsule_group"]}
            self.assertEqual(groupes["sys"], {"id": "sys", "members": ["cpu", "temp", "ram"], "opacity": 0.4})
            widgets = export["widgets"]
            self.assertEqual(widgets["t-heure"], composition["widget.t-heure"])
            self.assertEqual(widgets["t-taches"], composition["widget.t-taches"])
            self.assertEqual(widgets["cpu"]["type"], "sysmon")
            self.assertEqual(widgets["network"]["vpn_status"], "hidden")
            self.assertIn("nordvpn", widgets["tray"]["hidden"])
            self.assertEqual(export["police"], "Inter")

            natif = tb.barre(nc, sortie, {"BARRE_MODULAIRE": "non"})["bar"]
            self.assertFalse(panneaux.exists())
            self.assertNotIn("enabled", natif["default"])
            self.assertNotIn("enabled", natif["bas"])

            # Le choix de l'installation vient de la base, pas des QML copiés.
            legacy = {"notifications": config.replace("enable_daemon = false", "enable_daemon = true"),
                      "île": config.replace("center = []", 'center = ["nc/ile:pilule"]', 1)}
            for marqueur, texte in legacy.items():
                with self.subTest(marqueur=marqueur):
                    base.write_text(texte, encoding="utf-8")
                    panneaux.write_text("{}", encoding="utf-8")
                    natif = tb.barre(nc, sortie, vals)["bar"]
                    self.assertFalse(panneaux.exists())
                    self.assertNotIn("enabled", natif["default"])

    def test_conserve_le_titre_et_les_jauges_dans_un_theme_lateral(self):
        composition = {"bar.default": {"position": "left", "start": ["nc/fenetres:titre"]},
                       "bar.droite": {"position": "right", "end": ["volume"]}}
        with tb.nc_isole(install="quickshell", style="essai", themes={"essai": tb.theme(composition)}) as (nc, sortie):
            base = sortie.with_name("config.toml")
            base.write_text(base.read_text(encoding="utf-8").replace("enable_daemon = 0", "enable_daemon = false"), encoding="utf-8")
            tb.barre(nc, sortie, {"BARRE_MODULAIRE": "oui"})
            panneaux = sortie.parent.parent / "nc/panneaux.json"
            barres = {b["position"]: b for b in json.loads(panneaux.read_text(encoding="utf-8"))["barres"]}
            self.assertIn("nc/fenetres:titre", barres["left"]["start"])
            self.assertIn("group:sys", barres["left"]["end"])
            self.assertEqual(barres["right"]["end"], ["volume"])

    def test_epingles_du_dock_heritees_sans_ecraser_les_epingles_du_widget(self):
        with tb.nc_isole(install="quickshell") as (nc, sortie):
            base = sortie.with_name("config.toml")
            config = base.read_text(encoding="utf-8").replace("enable_daemon = 0", "enable_daemon = false")
            config += '\n[widget.raccourcis]\ntype = "dock"\n\n[widget.prive]\ntype = "dock"\npinned = ["org.gnome.Console"]\n'
            base.write_text(config, encoding="utf-8")
            home = sortie.parents[2]
            bin_ = home / ".local/bin"
            bin_.mkdir(parents=True)
            shutil.copyfile(tb.NC_REGLAGES.with_name("nc-dock"), bin_ / "nc-dock")
            etat = home / ".local/state/noctalia/settings.toml"
            etat.parent.mkdir(parents=True)
            panneaux = home / ".config/nc/panneaux.json"
            for epingles in ('["org.gnome.Nautilus"]', '[]'):
                with self.subTest(epingles=epingles):
                    etat.write_text(f"[dock]\npinned = {epingles}\n", encoding="utf-8")
                    tb.barre(nc, sortie, {"BARRE_MODULAIRE": "oui"})
                    widgets = json.loads(panneaux.read_text(encoding="utf-8"))["widgets"]
                    self.assertEqual(widgets["raccourcis"]["pinned"], json.loads(epingles))
                    self.assertEqual(widgets["prive"]["pinned"], ["org.gnome.Console"])

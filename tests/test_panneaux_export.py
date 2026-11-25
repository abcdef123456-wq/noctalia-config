"""L'export reprend la composition native avant de masquer la barre (HOME isolé)."""
import json
import os
import shutil
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

from tests import test_barre_composition as tb


class SessionBarres:
    """Simule seulement les IPC ; nc-reglages crée, relit et restaure ses vrais fichiers."""

    NATIVE = "noctalia-bar-default-DP-1"
    MODULAIRE = "nc-panneau-default-start"

    def __init__(self, nc, sortie):
        self.nc = nc["appliquer_noctalia"].__globals__
        self.sortie = sortie
        self.panneaux = Path(self.nc["PANNEAUX_OUT"])
        self.natifs = {"DP-1", "eDP-1"}
        self.modulaires = {"DP-1", "eDP-1"}
        self.ile_repond = True
        self.noctalia_repond = True
        self.noctalia_affiche = True
        self.natif_cache = False
        self.panneaux_pendant_recharge = []
        self.etapes = []

    def __enter__(self):
        self.patches = (
            patch.dict(os.environ, {"WAYLAND_DISPLAY": "voie-de-test"}),
            patch.object(self.nc["subprocess"], "run", side_effect=self.commande),
            patch.dict(self.nc, {"attendre_barres": lambda condition: condition()}),
        )
        for p in self.patches:
            p.start()
        return self

    def __exit__(self, *_):
        for p in reversed(self.patches):
            p.stop()

    def commande(self, cmd, **_):
        texte = ""
        code = 0
        if cmd == ["hyprctl", "layers", "-j"]:
            ecrans = {}
            for ecran in self.natifs | self.modulaires:
                couches = []
                if ecran in self.natifs and not self.natif_cache and self.noctalia_affiche:
                    couches.append({"namespace": self.NATIVE, "w": 1200, "h": 36})
                if self.panneaux.exists():
                    couches.append({"namespace": "nc-panneau-reserve-top", "w": 1200, "h": 40})
                    if ecran in self.modulaires and self.ile_repond:
                        couches.append({"namespace": self.MODULAIRE, "w": 80, "h": 34})
                ecrans[ecran] = {"levels": {"2": couches}}
            texte = json.dumps(ecrans)
        elif cmd[:3] == ["noctalia", "config", "validate"]:
            tb.tomllib.loads(Path(cmd[-1]).read_text(encoding="utf-8"))
        elif cmd[:6] == ["qs", "-c", "nc-ile", "ipc", "call", "ile"]:
            self.etapes.append("acquittement île")
            modele = json.loads(self.panneaux.read_text(encoding="utf-8"))
            assert modele["generation"] == cmd[-1]
            if self.ile_repond:
                texte = modele["generation"]
        elif cmd == ["noctalia", "msg", "config-reload"]:
            self.etapes.append("recharge Noctalia")
            self.panneaux_pendant_recharge.append(self.panneaux.exists())
            if self.noctalia_repond:
                t = tb.tomllib.loads(self.sortie.read_text(encoding="utf-8")) if self.sortie.exists() else {}
                self.natif_cache = t.get("bar", {}).get("default", {}).get("enabled") is False
                texte = "ok"
            else:
                code = 1
        return subprocess.CompletedProcess(cmd, code, texte, "")


def config_quickshell(sortie):
    base = sortie.with_name("config.toml")
    return base.read_text(encoding="utf-8").replace("enable_daemon = 0", "enable_daemon = false")


class BasculePanneaux(unittest.TestCase):
    def test_ile_arretee_ou_absente_sur_un_ecran_garde_noctalia(self):
        for repond, ecrans in ((False, {"DP-1", "eDP-1"}), (True, {"DP-1"})):
            with self.subTest(repond=repond), tb.nc_isole(install="quickshell") as (nc, sortie):
                sortie.with_name("config.toml").write_text(config_quickshell(sortie), encoding="utf-8")
                with SessionBarres(nc, sortie) as session:
                    session.ile_repond = repond
                    session.modulaires = ecrans
                    with self.assertRaises(ValueError):
                        nc["regler"]({}, "BARRE_MODULAIRE", "oui")
                    self.assertEqual(session.etapes, ["acquittement île"])
                    self.assertFalse(sortie.exists())
                    self.assertFalse(session.panneaux.exists())
                    self.assertNotIn("BARRE_MODULAIRE", nc["lire"]())

    def test_retour_garde_les_panneaux_jusqua_affichage_noctalia(self):
        with tb.nc_isole(install="quickshell") as (nc, sortie):
            sortie.with_name("config.toml").write_text(config_quickshell(sortie), encoding="utf-8")
            with SessionBarres(nc, sortie) as session:
                nc["regler"]({}, "BARRE_MODULAIRE", "oui")
                self.assertEqual(session.etapes, ["acquittement île", "recharge Noctalia"])
                avant = (sortie.read_bytes(), session.panneaux.read_bytes())
                for repond, affiche in ((False, True), (True, False)):
                    with self.subTest(repond=repond, affiche=affiche):
                        session.noctalia_repond = repond
                        session.noctalia_affiche = affiche
                        with self.assertRaises(ValueError):
                            nc["regler"]({}, "BARRE_MODULAIRE", "non")
                        self.assertEqual((sortie.read_bytes(), session.panneaux.read_bytes()), avant)
                        self.assertEqual(nc["lire"]()["BARRE_MODULAIRE"], "oui")
                session.noctalia_repond = session.noctalia_affiche = True
                nc["regler"]({}, "BARRE_MODULAIRE", "non")
                self.assertTrue(session.panneaux_pendant_recharge[-1])
                self.assertFalse(session.panneaux.exists())
                self.assertFalse(session.natif_cache)
                self.assertNotIn("BARRE_MODULAIRE", nc["lire"]())

    def test_hors_session_ne_masque_pas_noctalia(self):
        with tb.nc_isole(install="quickshell") as (nc, sortie):
            sortie.with_name("config.toml").write_text(config_quickshell(sortie), encoding="utf-8")
            with patch.dict(os.environ, {"WAYLAND_DISPLAY": "", "HYPRLAND_INSTANCE_SIGNATURE": ""}):
                with self.assertRaises(ValueError):
                    nc["regler"]({}, "BARRE_MODULAIRE", "oui")
                nc["appliquer_noctalia"]({"BARRE_MODULAIRE": "oui", "BARRE_OPACITE": "64"})
                self.assertNotIn("enabled", tb.tomllib.loads(sortie.read_text(encoding="utf-8"))["bar"]["default"])
                self.assertFalse(Path(nc["PANNEAUX_OUT"]).exists())


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
            with SessionBarres(nc, sortie):
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

            with SessionBarres(nc, sortie) as session:
                session.natif_cache = True
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
            with SessionBarres(nc, sortie):
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
                    with SessionBarres(nc, sortie):
                        tb.barre(nc, sortie, {"BARRE_MODULAIRE": "oui"})
                    widgets = json.loads(panneaux.read_text(encoding="utf-8"))["widgets"]
                    self.assertEqual(widgets["raccourcis"]["pinned"], json.loads(epingles))
                    self.assertEqual(widgets["prive"]["pinned"], ["org.gnome.Console"])

    def test_minimal_neutralise_seulement_la_composition_des_ecrans_de_la_barre_principale(self):
        with tb.nc_isole(install="quickshell", style="essai", themes={"essai": tb.theme(tb.COMPOSE)}) as (nc, sortie):
            base = sortie.with_name("config.toml")
            base.write_text(config_quickshell(sortie) + """
[bar.default.monitor.DP-1]
start = ["logo"]
center = ["clock"]
end = ["network", "clock"]
capsule_group = [{ id = "perso", members = ["network", "clock"] }]
position = "left"
thickness = 48
margin_edge = 12
capsule_opacity = 0.45
enabled = false

[bar.default.monitor.HDMI-A-1]
end = ["network", "clock"]

[bar.bas]
position = "bottom"
start = []
center = ["clock"]
end = []

[bar.bas.monitor.DP-1]
end = ["clock"]
position = "right"
thickness = 42
""", encoding="utf-8")
            panneaux = Path(nc["PANNEAUX_OUT"])
            with SessionBarres(nc, sortie):
                tb.barre(nc, sortie, {"BARRE_MODULAIRE": "oui"})
            normales = {b["id"]: b for b in json.loads(panneaux.read_text(encoding="utf-8"))["barres"]}
            self.assertEqual(normales["default"]["monitor"]["DP-1"]["end"], ["network", "clock"])
            for batterie in (True, False):
                with self.subTest(batterie=batterie):
                    with patch.dict(nc["configuration_panneaux"].__globals__,
                                    _a_batterie=lambda batterie=batterie: batterie), SessionBarres(nc, sortie):
                        tb.barre(nc, sortie, {"BARRE_MODULAIRE": "oui", "BARRE_CONTENU": "minimale"})
                    barres = {b["id"]: b for b in json.loads(panneaux.read_text(encoding="utf-8"))["barres"]}
                    principale = barres["default"]
                    self.assertEqual(principale["start"], ["workspaces"])
                    self.assertEqual(principale["center"], [])
                    self.assertEqual(principale["end"], ["network", "volume"] + (["battery"] if batterie else []))
                    self.assertEqual(principale["monitor"], {
                        "DP-1": {"position": "left", "thickness": 48, "margin_edge": 12,
                                 "capsule_opacity": 0.45, "enabled": False},
                        "HDMI-A-1": {},
                    })
                    self.assertEqual(barres["bas"], normales["bas"])
                    self.assertEqual(barres["bas"]["monitor"]["DP-1"],
                                     {"end": ["clock"], "position": "right", "thickness": 42})

    def test_contenu_minimal_avec_et_sans_batterie_preserve_theme_et_ignore_pilules(self):
        composition = {
            **tb.COMPOSE,
            "bar.default": {
                **tb.COMPOSE["bar.default"],
                "position": "bottom",
                "capsule_radius": 6,
                "background_opacity": 0.0,
            },
            "bar.bas": {
                **tb.COMPOSE["bar.bas"],
                "position": "top",
            },
        }
        with tb.nc_isole(install="quickshell", style="essai", themes={"essai": tb.theme(composition)}) as (nc, sortie):
            base = sortie.with_name("config.toml")
            base.write_text(config_quickshell(sortie), encoding="utf-8")
            panneaux = sortie.parent.parent / "nc/panneaux.json"
            vals = {
                "BARRE_MODULAIRE": "oui",
                "BARRE_CONTENU": "minimale",
                "BARRE_OPACITE": "70",
                "BARRE_SYSTEME": "oui",
                "VPN_PILULE_BARRE": "oui",
                "GARMIN_ACTIF": "oui",
                "GARMIN_PILULE_BARRE": "oui",
            }
            for a_bat, fin_attendue in ((True, ["network", "volume", "battery"]), (False, ["network", "volume"])):
                with self.subTest(a_bat=a_bat):
                    sysfs = sortie.parent.parent / ("sys-bat" if a_bat else "sys-fixe")
                    if a_bat:
                        (sysfs / "class/power_supply/BAT0").mkdir(parents=True, exist_ok=True)
                    else:
                        (sysfs / "class/power_supply").mkdir(parents=True, exist_ok=True)
                    with patch.dict(os.environ, {"NC_SYSFS": str(sysfs)}), SessionBarres(nc, sortie):
                        tb.barre(nc, sortie, vals)
                    export = json.loads(panneaux.read_text(encoding="utf-8"))
                    barres = {b["id"]: b for b in export["barres"]}
                    principale = barres["default"]
                    self.assertEqual(principale["position"], "bottom")
                    self.assertEqual((principale["capsule_radius"], principale["capsule_opacity"]), (6, 0.7))
                    self.assertEqual(principale["start"], ["workspaces"])
                    self.assertEqual(principale["center"], [])
                    self.assertEqual(principale["end"], fin_attendue)
                    self.assertEqual(principale["capsule_group"], [])
                    # Barre secondaire intacte
                    self.assertEqual(barres["bas"]["center"], ["t-taches"])
                    # Définitions présentes pour les widgets utilisés
                    for w in ["workspaces", *fin_attendue]:
                        self.assertIn(w, export["widgets"])
                    self.assertNotIn("nc/vpn:vpn", principale["end"])
                    self.assertNotIn("nc/garmin:garmin", principale["end"])
                    self.assertNotIn("group:sys", principale["end"])

            # BARRE_MODULAIRE=non reste intact même si BARRE_CONTENU=minimale
            with SessionBarres(nc, sortie) as session:
                session.natif_cache = True
                natif = tb.barre(nc, sortie, {"BARRE_MODULAIRE": "non", "BARRE_CONTENU": "minimale"})["bar"]
            self.assertFalse(panneaux.exists())
            self.assertNotIn("enabled", natif["default"])
            self.assertNotIn("enabled", natif["bas"])

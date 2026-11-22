"""Barre composée par un thème (A9) : un thème peut donner ses listes start, center et end, ses instances « t-… », ses
groupes de pastilles et UNE seconde barre. Les interrupteurs de la personne (BARRE_SYSTEME, pilules VPN et Garmin) et les
widgets posés à l'installation (notifications, île) s'appliquent ensuite : un thème ne les force ni ne les retire.
Sans composition, zy-reglages.toml reste identique à l'octet à l'état d'avant cette composition (correctif d'écran 78ca96f, empreintes figées ci-dessous).
Le thème est un fichier tiers : tout ce qui n'est pas dans la liste blanche est refusé (commandes, actions, textes).
Faux HOME, appliquer_noctalia appelé sans aucun programme lancé ; jamais le vrai HOME."""
import contextlib
import hashlib
import json
import os
import re
from pathlib import Path
import runpy
import shutil
import subprocess
import tempfile
import tomllib
import unittest
from unittest.mock import patch
import warnings

REPO = Path(__file__).resolve().parents[1]
NC_REGLAGES = REPO / "home/.local/bin/nc-reglages"
CONFIG = REPO / "home/.config/noctalia/config.toml"
THEMES = REPO / "home/.local/share/nc/themes"

# config.toml installé : île en plugin et notifications de Noctalia (« plugin »), ou île Quickshell (« quickshell »)
INSTALLS = {"plugin": {"@ILE_CENTRE@": '"nc/ile:pilule"', "@NOTIF_WIDGET@": ', "notifications"'},
            "quickshell": {"@ILE_CENTRE@": "", "@NOTIF_WIDGET@": ""}}
COMBOS = ({}, {"BARRE_SYSTEME": "non"}, {"BARRE_SYSTEME": "oui"}, {"VPN_PILULE_BARRE": "oui"},
          {"GARMIN_ACTIF": "oui", "GARMIN_PILULE_BARRE": "oui"},
          {"BARRE_SYSTEME": "non", "VPN_PILULE_BARRE": "oui", "GARMIN_ACTIF": "oui", "GARMIN_PILULE_BARRE": "oui"})


# Empreintes (sha256, 16 premiers caractères) de zy-reglages.toml produit par nc-reglages d'avant la composition (78ca96f), pour chaque
# installation, thème sans composition et combinaison d'interrupteurs (COMBOS dans l'ordre)
REFERENCE = {
    "plugin/noctalia/0": "e3b0c44298fc1c14",
    "plugin/noctalia/1": "0ed2a0605153fbd2",
    "plugin/noctalia/2": "7a29255a12ff7969",
    "plugin/noctalia/3": "c8dd78a3ffa16f48",
    "plugin/noctalia/4": "0d00747cb0888bac",
    "plugin/noctalia/5": "009cf2e9ff55794d",
    "quickshell/noctalia/0": "e3b0c44298fc1c14",
    "quickshell/noctalia/1": "d2bb81bad99f06b1",
    "quickshell/noctalia/2": "ed7ae48e9d56a941",
    "quickshell/noctalia/3": "de8c4f8144e2154b",
    "quickshell/noctalia/4": "80c0eb1ba78189d0",
    "quickshell/noctalia/5": "73533f04732264f2",
}


def config_installee(install):
    t = CONFIG.read_text(encoding="utf-8")
    for k, v in INSTALLS[install].items():
        t = t.replace(k, v)
    t = t.replace("@PLUGIN_ILE@", "").replace("@HOME@", "/home/user").replace("@MONITOR@", "eDP-1")
    return re.sub(r"@[A-Z0-9_]+@", "0", t)          # le reste (logo, navigateur, positions) : sans effet sur la barre


@contextlib.contextmanager
def nc_isole(source=NC_REGLAGES, install="plugin", style="noctalia", themes=None):
    """nc-reglages chargé dans un HOME neuf (config.toml installé, style.conf, dossier de thèmes) ; rend (module, sortie)."""
    with tempfile.TemporaryDirectory(prefix="nc-a9-") as d:
        home = Path(d)
        noct = home / ".config/noctalia"
        noct.mkdir(parents=True)
        (home / "tmp").mkdir()
        (noct / "config.toml").write_text(config_installee(install), encoding="utf-8")
        (home / ".config/nc").mkdir()
        (home / ".config/nc/style.conf").write_text(f"STYLE={style}\n", encoding="utf-8")
        dossier = home / "themes"
        shutil.copytree(THEMES, dossier)
        for nom, t in (themes or {}).items():
            (dossier / f"{nom}.json").write_text(json.dumps(t), encoding="utf-8")
        env = {k: v for k, v in os.environ.items() if not k.startswith(("NOCTALIA_", "XDG_"))}
        env.update(HOME=str(home), XDG_CONFIG_HOME=str(home / ".config"), XDG_DATA_HOME=str(home / ".local/share"),
                   XDG_STATE_HOME=str(home / ".local/state"), XDG_CACHE_HOME=str(home / ".cache"),
                   TMPDIR=str(home / "tmp"), NC_LANGUE="fr", NC_THEMES_DIR=str(dossier))
        with patch.dict(os.environ, env, clear=True), warnings.catch_warnings():
            warnings.simplefilter("ignore", ResourceWarning)
            nc = runpy.run_path(str(source))
            faux = type("S", (), {k: getattr(subprocess, k) for k in dir(subprocess) if not k.startswith("__")})
            faux.run = staticmethod(lambda *a, **k: subprocess.CompletedProcess(a, 0, "", ""))
            nc["appliquer_noctalia"].__globals__["subprocess"] = faux
            yield nc, noct / "zy-reglages.toml"


def sortie(nc, fichier, vals):
    nc["appliquer_noctalia"](dict(vals))
    return fichier.read_bytes() if fichier.exists() else b""


def empreinte(b):
    return hashlib.sha256(b).hexdigest()[:16]


def theme(noctalia, nom="essai"):
    d = json.loads((THEMES / "nord.json").read_text(encoding="utf-8"))
    d.update(nom=nom, noctalia=noctalia)
    return d


# Un thème façon GNOME + barre des tâches en bas : heure au centre, un texte, un groupe et une seconde barre
COMPOSE = {
    "bar.default": {"position": "top", "start": ["logo", "t-texte"], "center": ["t-heure"],
                    "end": ["tray", "group:t-etat"], "capsule_group": [{"id": "t-etat", "members": ["network", "volume"]}]},
    "widget.t-heure": {"type": "clock", "format": "{:%a %d %b  %H:%M}"},
    "widget.t-texte": {"type": "text", "text": "Activités"},
    "widget.t-taches": {"type": "taskbar", "show_window_title": True, "window_title_max_width": 120},
    "bar.bas": {"position": "bottom", "thickness": 40, "center": ["t-taches"], "end": ["clock"]},
}


def barre(nc, fichier, vals):
    """zy-reglages.toml lu en TOML après appliquer_noctalia(vals)."""
    return tomllib.loads(sortie(nc, fichier, vals).decode())


class SansComposition(unittest.TestCase):
    def test_identique_a_avant(self):
        for install in INSTALLS:
            # apple et oled (barre sans pastilles) mettent leurs groupes à plat : test_barre_verticale
            for style in ("noctalia",):
                with nc_isole(install=install, style=style) as (nc, f):
                    for i, c in enumerate(COMBOS):
                        with self.subTest(install=install, style=style, interrupteurs=c):
                            b = sortie(nc, f, c)
                            self.assertEqual(empreinte(b), REFERENCE[f"{install}/{style}/{i}"], b.decode())

    def test_repli_egal_au_config_du_depot(self):
        """Les noms permis quand config.toml est illisible sont ceux du config.toml du dépôt."""
        for install in INSTALLS:
            with self.subTest(install=install), nc_isole(install=install) as (nc, f):
                noms, groupes, pos = nc["_barre_installee"]()
                (f.parent / "config.toml").unlink()
                self.assertEqual(nc["_barre_installee"](), (noms | {"nc/ile:pilule", "notifications"}, groupes, pos))
                self.assertEqual(nc["_WIDGETS_BARRE"], noms | {"nc/ile:pilule", "notifications"} | {"group:" + g for g in groupes})


class Composition(unittest.TestCase):
    def appliquer(self, vals, noctalia=COMPOSE, install="plugin"):
        with nc_isole(install=install, style="essai", themes={"essai": theme(noctalia)}) as (nc, f):
            return barre(nc, f, vals)

    def test_base_du_theme_puis_installation(self):
        t = self.appliquer({})
        b = t["bar"]["default"]
        self.assertEqual(b["start"], ["logo", "t-texte"])
        self.assertEqual(b["center"], ["nc/ile:pilule", "t-heure"], "île en plugin : gardée")
        self.assertEqual(b["end"], ["group:sys", "tray", "group:t-etat", "notifications"], "sys et notifications installés")
        self.assertEqual([g["id"] for g in b["capsule_group"]], ["sys", "status", "t-etat"], "groupes de config.toml d'abord")
        self.assertEqual(t["widget"]["t-heure"], {"type": "clock", "format": "{:%a %d %b  %H:%M}"})
        self.assertEqual(t["widget"]["t-texte"]["text"], "Activités")
        self.assertEqual(t["bar"]["bas"], {"position": "bottom", "thickness": 40, "center": ["t-taches"], "end": ["clock"],
                                           "start": []})

    def test_quickshell_ni_ile_ni_notifications(self):
        b = self.appliquer({}, install="quickshell")["bar"]["default"]
        self.assertEqual(b["center"], ["t-heure"])
        self.assertEqual(b["end"], ["group:sys", "tray", "group:t-etat"])

    def test_interrupteurs_sur_la_base_du_theme(self):
        b = self.appliquer({"BARRE_SYSTEME": "non", "VPN_PILULE_BARRE": "oui", "GARMIN_ACTIF": "oui",
                            "GARMIN_PILULE_BARRE": "oui"})["bar"]["default"]
        self.assertEqual(b["end"], ["tray", "group:t-etat", "notifications", "nc/vpn:vpn", "nc/garmin:garmin"],
                         "sans power_profile ni group:status : à la fin de end")
        noct = dict(COMPOSE, **{"bar.default": dict(COMPOSE["bar.default"], start=["logo", "power_profile"],
                                                     end=["tray", "group:status"])})
        b = self.appliquer({"VPN_PILULE_BARRE": "oui", "GARMIN_ACTIF": "oui", "GARMIN_PILULE_BARRE": "oui"}, noct)["bar"]["default"]
        self.assertEqual(b["start"], ["logo", "nc/vpn:vpn", "nc/garmin:garmin", "power_profile"], "avant power_profile")
        self.assertEqual(b["end"], ["group:sys", "tray", "group:status", "notifications"])
        noct["bar.default"]["start"] = ["logo"]
        b = self.appliquer({"VPN_PILULE_BARRE": "oui"}, noct)["bar"]["default"]
        self.assertEqual(b["end"], ["group:sys", "tray", "nc/vpn:vpn", "group:status", "notifications"], "avant group:status")

    def test_le_theme_ne_force_ni_ne_retire(self):
        noct = {"bar.default": {"start": ["group:sys", "nc/vpn:vpn", "logo"], "center": ["notifications"],
                                "end": ["nc/garmin:garmin", "nc/ile:pilule", "tray"]},
                "bar.bas": {"position": "bottom", "end": ["group:sys", "nc/vpn:vpn", "clock"]}}
        t = self.appliquer({"BARRE_SYSTEME": "non"}, noct, install="quickshell")
        b = t["bar"]["default"]
        self.assertEqual((b["start"], b["center"], b["end"]), (["logo"], [], ["tray"]))
        self.assertEqual(t["bar"]["bas"]["end"], ["clock"], "rien de conditionnel dans la seconde barre")
        b = self.appliquer({}, {"bar.default": {"end": ["tray"]}})["bar"]["default"]
        self.assertEqual(b["end"], ["group:sys", "tray", "notifications"], "ni retirés")
        self.assertNotIn("start", b)

    def test_groupes_ecrits_en_toml_valide(self):
        with nc_isole(style="essai", themes={"essai": theme(COMPOSE)}) as (nc, f):
            nc["appliquer_noctalia"]({})
            texte = f.read_text(encoding="utf-8")
        self.assertIn('capsule_group = [{ id = "sys", members = ["cpu", "temp", "ram"] }, ', texte)
        self.assertEqual(tomllib.loads(texte)["bar"]["default"]["capsule_group"][-1], {"id": "t-etat", "members": ["network", "volume"]})


class Nord(unittest.TestCase):
    """nord (validé à l'écran) : une seule pilule centrée en bas (logo, bureaux, applis du bureau, état, heure), barre sans
    fond, le plateau à droite ; group:sys (BARRE_SYSTEME) tombe à droite en pastille."""
    def test_composition_de_nord(self):
        with nc_isole(style="nord") as (nc, f):
            t = barre(nc, f, {})
        b = t["bar"]["default"]
        self.assertEqual((b["position"], b["thickness"]), ("bottom", 44))
        self.assertEqual(b["center"], ["nc/ile:pilule", "group:tout"], "l'île du plugin, posée à l'installation, puis la pilule")
        self.assertEqual(b["end"], ["group:sys", "tray", "notifications"])
        tout = [g for g in b["capsule_group"] if g["id"] == "tout"][0]["members"]
        self.assertEqual(tout, ["logo", "workspaces", "t-taches", "network", "bluetooth", "volume", "nc/batterie:batterie", "t-heure"])
        self.assertEqual(t["widget"]["t-heure"], {"type": "clock", "format": "{:%H:%M}"})
        with nc_isole(style="nord", install="quickshell") as (nc, f):
            b = barre(nc, f, {"BARRE_SYSTEME": "non"})["bar"]["default"]
        self.assertEqual((b["center"], b["end"]), (["group:tout"], ["tray"]))


class Refus(unittest.TestCase):
    """Le thème est un fichier tiers : chaque cas est refusé en entier (ValueError, message clair)."""
    LONG = "a" * 33
    CAS = {
        "custom-button": {"widget.t-a": {"type": "custom_button"}},
        "custom-button (tiret)": {"widget.t-a": {"type": "custom-button"}},
        "actions d'une instance": {"widget.t-a": {"type": "clock", "actions": {"left": "exec x"}}},
        "table actions d'une instance": {"widget.t-a": {"type": "clock"}, "widget.t-a.actions": {"left": "exec x"}},
        "actions des bureaux": {"widget.workspaces.actions": {"left": "exec x"}},
        "actions dans les bureaux": {"widget.workspaces": {"actions": {"left": "exec x"}}},
        "zone vide (table)": {"bar.default.dead_zone.actions": {"right": "exec x"}},
        "zone vide (clé)": {"bar.default": {"dead_zone": {"actions": {"right": "exec x"}}}},
        "actions de la seconde barre": {"bar.bas": {"position": "bottom", "dead_zone": {"actions": {"right": "exec x"}}}},
        "type hors liste": {"widget.t-a": {"type": "inconnu"}},
        "type absent": {"widget.t-a": {"format": "{:%H}"}},
        "control-center": {"widget.t-a": {"type": "control-center"}},
        "session": {"widget.t-a": {"type": "session"}},
        "screenshot": {"widget.t-a": {"type": "screenshot"}},
        "wallpaper": {"widget.t-a": {"type": "wallpaper"}},
        "clipboard": {"widget.t-a": {"type": "clipboard"}},
        "settings": {"widget.t-a": {"type": "settings"}},
        "clé exec": {"widget.t-a": {"type": "clock", "exec": "x"}},
        "clé command": {"widget.t-a": {"type": "text", "text": "a", "command": "x"}},
        "sysmon path": {"widget.t-a": {"type": "sysmon", "path": "/home"}},
        "sysmon image": {"widget.t-a": {"type": "sysmon", "custom_image": "/tmp/x.png"}},
        "taskbar pinned": {"widget.t-a": {"type": "taskbar", "pinned": ["firefox"]}},
        "text trop long": {"widget.t-a": {"type": "text", "text": LONG}},
        "text vide": {"widget.t-a": {"type": "text", "text": ""}},
        "text <": {"widget.t-a": {"type": "text", "text": "<b>x</b>"}},
        "text &": {"widget.t-a": {"type": "text", "text": "a &amp; b"}},
        "heure fausse": {"widget.t-a": {"type": "clock", "format": "{:%Q}"}},
        "heure ouverte": {"widget.t-a": {"type": "clock", "format": "{"}},
        "heure sans %": {"widget.t-a": {"type": "clock", "format": "{:abc}"}},
        "heure vide": {"widget.t-a": {"type": "clock", "format": "{:}"}},
        "instance sans t-": {"widget.heure": {"type": "clock"}},
        "instance de config.toml": {"widget.clock": {"format": "{:%H}"}},
        "deux barres en plus": {"bar.bas": {"position": "bottom"}, "bar.gauche": {"position": "left"}},
        "seconde barre même bord": {"bar.bas": {"position": "top"}},
        "seconde barre même bord que le thème": {"bar.default": {"position": "left"}, "bar.bas": {"position": "left"}},
        "seconde barre sans bord": {"bar.bas": {"end": ["clock"]}},
        "seconde barre mal nommée": {"bar.Bas": {"position": "bottom"}},
        "nom inconnu": {"bar.default": {"end": ["inconnu"]}},
        "instance non déclarée": {"bar.default": {"end": ["t-rien"]}},
        "groupe de config dans la seconde barre": {"bar.bas": {"position": "bottom", "end": ["group:status"]}},
        "groupe inconnu": {"bar.default": {"end": ["group:rien"]}},
        "membre inconnu": {"bar.default": {"capsule_group": [{"id": "g", "members": ["inconnu"]}]}},
        "groupe dans un groupe": {"bar.default": {"capsule_group": [{"id": "g", "members": ["group:status"]}]}},
        "groupe sans membre": {"bar.default": {"capsule_group": [{"id": "g", "members": ["nc/vpn:vpn"]}]}},
        "id de groupe de config.toml": {"bar.default": {"capsule_group": [{"id": "status", "members": ["tray"]}]}},
        "clé de groupe en plus": {"bar.default": {"capsule_group": [{"id": "g", "members": ["tray"], "fill": "x"}]}},
        "neuf groupes": {"bar.default": {"capsule_group": [{"id": f"g{i}", "members": ["tray"]} for i in range(9)]}},
        "liste qui n'est pas une liste": {"bar.default": {"end": "tray"}},
        "flou": {"bar.default": {"compositor_blur": True}},
        "rôle de couleur inconnu de Noctalia": {"bar.default": {"capsule_fill": "surface_container"}},
    }

    def test_refus(self):
        with nc_isole() as (nc, _):
            cas = dict(self.CAS)
            for c in (7, 0x85, 0x202E, 0x2066, 0x200B, 0x2028, 0x2029):      # contrôle, sens d'écriture, séparateurs
                cas[f"text U+{c:04X}"] = {"widget.t-a": {"type": "text", "text": "a" + chr(c) + "b"}}
            for nom, noct in cas.items():
                with self.subTest(nom), self.assertRaises(ValueError):
                    nc["_verifier_theme"]("essai", theme(noct))

    def test_accepte_et_nettoie(self):
        with nc_isole() as (nc, _):
            t = nc["_verifier_theme"]("essai", theme(dict(COMPOSE, **{"widget.t-sys": {"type": "sysmon", "stat": "cpu_usage"}})))
            self.assertEqual(t["noctalia"]["bar.bas"]["start"], [])
            noct = {"bar.default": {"end": ["group:sys", "tray"],
                                    "capsule_group": [{"id": "g", "members": ["tray", "nc/vpn:vpn"]}]}}
            t = nc["_verifier_theme"]("essai", theme(noct))["noctalia"]["bar.default"]
            self.assertEqual((t["end"], t["capsule_group"]), (["tray"], [{"id": "g", "members": ["tray"]}]))
            for texte in ("Bonjour", "a" * 32, "Menu ⌘", "café-noir"):
                nc["_verifier_theme"]("essai", theme({"widget.t-a": {"type": "text", "text": texte}}))
            for fmt in ("{:%H:%M}", "{:%a %d %b}   {:%H:%M}", "Il est {:%H h %M}", "{:%x}"):
                nc["_verifier_theme"]("essai", theme({"widget.t-a": {"type": "clock", "format": fmt}}))


if __name__ == "__main__":
    unittest.main()

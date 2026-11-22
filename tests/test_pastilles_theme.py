"""Forme et couleur des pastilles dans un thème (docs.noctalia.dev/noctalia/bar/) : rayon, contour, fond et texte sur la
barre (capsule_*), par groupe (fill, foreground, border, border_width, radius, opacity, padding) et par widget (capsule_*).
- acceptées, transmises telles quelles à zy-reglages.toml ; toute autre clé de groupe refusée ;
- texte lisible : fond et texte en hexadécimal sur la même pastille → 4,5:1 au moins, sinon refus du thème ;
- weather refusé (« Pas de localisation » sans [weather]) ;
- le VRAI noctalia (pas le faux du PATH des tests) ne signale rien sur les thèmes du dossier ni sur un thème qui pose
  toutes ces clés ; retour à noctalia à l'octet après ce thème.
Faux HOME ; jamais le vrai HOME."""
from tests import _isolation  # noqa: F401  (HOME, XDG_*, langue : avant tout le reste)
import copy
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests import test_barre_composition as bc
from tests.test_themes_retour import Retour

THEMES = Path(__file__).resolve().parents[1] / "home/.local/share/nc/themes"
PLUGINS_NC = ("nc/", "nc-batterie", "nc-heure", "nc-musique")      # plugins absents du HOME factice : avertis, attendu

NOCT = {
    "bar.default": {"position": "top", "thickness": 40, "margin_edge": 0, "background_opacity": 1.0,
                    "capsule_radius": 0, "capsule_border_width": 2, "capsule_border": "#000000",
                    "capsule_fill": "#fff3d6", "capsule_foreground": "#1a1a1a",
                    "capsule_group": [{"id": "bureaux", "members": ["workspaces"], "fill": "#ff3366", "foreground": "#000000",
                                       "border": "#000000", "border_width": 2, "radius": 0, "opacity": 1.0, "padding": 10},
                                      {"id": "jour", "members": ["t-date"], "fill": "#33ccff"}],
                    "start": ["group:bureaux"], "center": [], "end": ["group:status", "group:jour"]},
    "widget.workspaces": {"style": "regular", "capsule_border": "primary"},
    "widget.t-date": {"type": "clock", "format": "{:%d.%m}", "capsule_fill": "#ffd23f", "capsule_foreground": "#000000",
                      "capsule_border": "#000000", "capsule_border_width": 1, "capsule_radius": 4},
}


def theme(noct):
    d = json.loads((THEMES / "catppuccin.json").read_text(encoding="utf-8"))
    d["nom"] = "essai-pastilles"
    d["noctalia"] = copy.deepcopy(noct)
    return d


def vrai_noctalia():
    """/usr/bin/noctalia ou celui du PATH, en sautant le faux noctalia que les tests mettent en tête du PATH."""
    chemin = os.pathsep.join(p for p in os.environ.get("PATH", "").split(os.pathsep) if "faux" not in p)
    return shutil.which("noctalia", path=chemin)


def avertissements(dossier_noctalia):
    """WARN et ERROR de « noctalia config validate » (qui rend 0 même avec des WARN) sur une copie de ce dossier, hors
    plugins nc/ ; un code de retour non nul compte aussi."""
    with tempfile.TemporaryDirectory() as h:
        shutil.copytree(dossier_noctalia, Path(h) / ".config/noctalia")
        (Path(h) / "run").mkdir()
        o = subprocess.run(["env", "-i", "PATH=/usr/bin:/bin", f"HOME={h}", f"XDG_CONFIG_HOME={h}/.config",
                            f"XDG_RUNTIME_DIR={h}/run", vrai_noctalia(), "config", "validate"],
                           capture_output=True, text=True, timeout=60)
    lignes = [l.split("/.config/noctalia/")[-1] for l in (o.stdout + o.stderr).splitlines() if l.startswith(("WARN", "ERROR"))]
    return [l for l in lignes if not any(x in l for x in PLUGINS_NC)] + ([f"code {o.returncode}"] if o.returncode else [])


class Liste(unittest.TestCase):
    def sortie(self, noct, vals=None, install="quickshell"):
        with bc.nc_isole(style="essai-pastilles", install=install, themes={"essai-pastilles": theme(noct)}) as (nc, f):
            return bc.barre(nc, f, vals or {})

    def test_cles_transmises(self):
        t = self.sortie(NOCT)
        b = t["bar"]["default"]
        for k in ("capsule_radius", "capsule_border_width", "capsule_border", "capsule_fill", "capsule_foreground"):
            self.assertEqual(b[k], NOCT["bar.default"][k], k)
        g = {x["id"]: x for x in b["capsule_group"]}
        self.assertEqual(g["bureaux"], NOCT["bar.default"]["capsule_group"][0])
        self.assertEqual(g["jour"]["fill"], "#33ccff")
        self.assertEqual(t["widget"]["t-date"]["capsule_radius"], 4)
        self.assertEqual(t["widget"]["workspaces"]["capsule_border"], "primary")

    def refuse(self, noct):
        with self.assertRaises(ValueError):
            with bc.nc_isole(style="noctalia", themes={"essai-pastilles": theme(noct)}) as (nc, f):
                nc["_verifier_theme"]("essai-pastilles", theme(noct))

    def test_refus(self):
        for chemin, v in ((("bar.default", "capsule_group", 0, "color"), "#000000"),        # clé de groupe inconnue
                          (("bar.default", "capsule_border"), "rouge"),                     # ni rôle ni hexadécimal
                          (("bar.default", "capsule_radius"), -1),
                          (("widget.t-date", "capsule_border_width"), 9),
                          (("widget.workspaces", "pill_scale"), 1.3)):                      # Noctalia : 1 au plus
            n = copy.deepcopy(NOCT)
            x = n
            for k in chemin[:-1]:
                x = x[k]
            x[chemin[-1]] = v
            with self.subTest(chemin=chemin):
                self.refuse(n)

    def test_weather_refuse(self):
        n = copy.deepcopy(NOCT)
        n["widget.t-meteo"] = {"type": "weather"}
        self.refuse(n)

    def test_contraste(self):
        for ou in ("barre", "groupe", "widget", "groupe sans texte propre"):
            n = copy.deepcopy(NOCT)
            if ou == "barre":
                n["bar.default"]["capsule_foreground"] = "#ffffff"           # sur #fff3d6
            elif ou == "groupe":
                n["bar.default"]["capsule_group"][0]["foreground"] = "#ff3366"
            elif ou == "widget":
                n["widget.t-date"]["capsule_foreground"] = "#ffffff"         # sur #ffd23f
            else:
                n["bar.default"]["capsule_group"][1]["fill"] = "#101010"     # le texte de la barre (#1a1a1a) dessus
            with self.subTest(ou=ou):
                self.refuse(n)
        self.assertTrue(self.sortie(NOCT))                                  # contrôle : la table d'origine passe
        with bc.nc_isole() as (nc, f):
            c = nc["_contraste"]
        self.assertAlmostEqual(c("#000", "#ffffff"), 21, places=3)
        self.assertIsNone(c("primary", "#000000"))


@unittest.skipUnless(vrai_noctalia(), "noctalia absent")
class VraiNoctalia(unittest.TestCase):
    def test_aucun_avertissement(self):
        cas = {p.stem: None for p in sorted(THEMES.glob("*.json"))}
        cas["essai-pastilles"] = theme(NOCT)
        for nom, d in cas.items():
            for install in ("plugin", "quickshell"):
                for vals in ({}, {"BARRE_SYSTEME": "oui", "VPN_PILULE_BARRE": "oui"}):
                    with self.subTest(theme=nom, install=install, vals=vals):
                        with bc.nc_isole(style=nom, install=install, themes={nom: d} if d else None) as (nc, f):
                            nc["appliquer_noctalia"](dict(vals))
                            self.assertEqual(avertissements(f.parent), [])

    def test_controle_du_controle(self):
        with bc.nc_isole(style="essai-pastilles", themes={"essai-pastilles": theme(NOCT)}) as (nc, f):
            nc["appliquer_noctalia"]({})
            with open(f, "a", encoding="utf-8") as z:
                z.write('\n[bar.essai]\nposition = "bottom"\n\n[[bar.essai.capsule_group]]\nid = "x"\nmembers = ["tray"]\n'
                        'couleur_bidon = "#000000"\n')
            self.assertEqual([l.split(": ", 1)[1] for l in avertissements(f.parent)], ["bar.essai.capsule_group.couleur_bidon: unknown setting"])


class RetourPastilles(Retour):
    def test_chaque_theme(self):
        self.skipTest("couvert par test_themes_retour")

    def test_retour_a_l_octet(self):
        (self.themes / "essai-pastilles.json").write_text(json.dumps(theme(NOCT), ensure_ascii=False), encoding="utf-8")
        self.aller_retour("essai-pastilles")


if __name__ == "__main__":
    unittest.main()

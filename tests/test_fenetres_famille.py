"""Famille des fenêtres réglable par un thème : disposition (scrolling), orientation du maître, fond, décalage de l'ombre.
« auto », absent ou inconnu rendent les appels d'avant. apparence.lua est exécuté avec lua et de faux hl / nc :
jamais le vrai Hyprland. L'effet réel à l'écran n'est pas testé."""
import importlib.machinery
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import unittest

from tests import _isolation  # noqa: F401

REPO = Path(__file__).resolve().parents[1]
APPARENCE = REPO / "home/.config/hypr/nc/apparence.lua"
ENERGIE = REPO / "home/.config/hypr/nc/energie.lua"
LUA = shutil.which("lua") or shutil.which("lua5.4")

# Faux hl et nc : sortie = tous les appels de hl.config, en JSON (clés triées)
PRELUDE = r'''
local function ser(x)
  if type(x) == "table" then
    local ks = {}
    for k in pairs(x) do ks[#ks + 1] = k end
    table.sort(ks, function(a, b) return tostring(a) < tostring(b) end)
    local t = {}
    for _, k in ipairs(ks) do t[#t + 1] = string.format("%q:%s", tostring(k), ser(x[k])) end
    return "{" .. table.concat(t, ",") .. "}"
  elseif type(x) == "string" then return string.format("%q", x)
  else return tostring(x) end
end
cfg = {}
hl = { config = function(t) cfg[#cfg + 1] = ser(t) end, curve = function() end, animation = function() end }
nc = { reglage = function(k, d) if REG[k] ~= nil then return REG[k] end return d end, hypr_min = function() return false end,
       profil = { profil = PROFIL or "balanced" } }
'''


def lancer(reg, economie=False):
    lig = ", ".join(f'{k} = "{v}"' for k, v in reg.items())
    code = f'REG = {{ {lig} }}\nPROFIL = {'"power-saver"' if economie else 'nil'}\n' + PRELUDE + f'dofile("{APPARENCE}")\n'
    if economie:
        code += f'dofile("{ENERGIE}")\n'
    code += 'io.write("[" .. table.concat(cfg, ",") .. "]")\n'
    r = subprocess.run([LUA, "-"], input=code, capture_output=True, text=True, timeout=30)
    assert r.returncode == 0, r.stdout + r.stderr
    return json.loads(r.stdout)


def cle(appels, *chemin):
    """Dernière valeur posée pour ce chemin (None si aucun appel ne la pose)."""
    val = None
    for t in appels:
        x = t
        for c in chemin:
            x = x.get(c) if isinstance(x, dict) else None
        if x is not None:
            val = x
    return val


def charger_reglages():
    l = importlib.machinery.SourceFileLoader("nc_reglages_famille", str(REPO / "home/.local/bin/nc-reglages"))
    m = importlib.util.module_from_spec(importlib.util.spec_from_loader("nc_reglages_famille", l))
    l.exec_module(m)
    return m


@unittest.skipUnless(LUA, "lua absent")
class Lua(unittest.TestCase):
    def test_auto_identique_a_main(self):
        ref = lancer({})
        self.assertEqual(cle(ref, "general", "layout"), "dwindle")
        self.assertEqual(cle(ref, "decoration", "shadow", "offset"), {"1": 0, "2": 4})
        self.assertEqual(cle(ref, "misc", "background_color"), "rgb(0b0d12)")
        self.assertEqual(ref[0]["master"], {"new_status": "master"})   # aucune orientation posée
        for reg in ({"FENETRES_DISPOSITION": "auto", "FENETRES_MAITRE_ORIENTATION": "auto", "FENETRES_FOND": "auto",
                     "FENETRES_OMBRE_DECALAGE": "auto"},
                    {"FENETRES_DISPOSITION": "inconnu", "FENETRES_MAITRE_ORIENTATION": "x", "FENETRES_FOND": "x",
                     "FENETRES_OMBRE_DECALAGE": "x"},
                    {"FENETRES_FOND": "", "FENETRES_OMBRE_DECALAGE": ""}):
            self.assertEqual(lancer(reg), ref, reg)
        self.assertEqual(lancer({"FENETRES_MAITRE_ORIENTATION": "gauche"}), ref)   # dwindle : ignorée

    def test_disposition(self):
        for v in ("dwindle", "master", "scrolling"):
            self.assertEqual(cle(lancer({"FENETRES_DISPOSITION": v}), "general", "layout"), v)
        self.assertEqual(cle(lancer({"FENETRES_DISPOSITION": "monocle"}), "general", "layout"), "dwindle")

    def test_orientation_seulement_en_master(self):
        for fr, en in (("gauche", "left"), ("droite", "right"), ("haut", "top"), ("bas", "bottom"), ("centre", "center")):
            self.assertEqual(cle(lancer({"FENETRES_DISPOSITION": "master", "FENETRES_MAITRE_ORIENTATION": fr}),
                                 "master", "orientation"), en)
            for disp in ("dwindle", "scrolling"):
                self.assertIsNone(cle(lancer({"FENETRES_DISPOSITION": disp, "FENETRES_MAITRE_ORIENTATION": fr}),
                                      "master", "orientation"))
        self.assertIsNone(cle(lancer({"FENETRES_DISPOSITION": "master"}), "master", "orientation"))

    def test_fond(self):
        self.assertEqual(cle(lancer({"FENETRES_FOND": "noir"}), "misc", "background_color"), "rgb(000000)")

    def test_ombre_decalage(self):
        for v, xy in (("aucun", (0, 0)), ("bas", (0, 8)), ("dure", (8, 8)), ("auto", (0, 4))):
            self.assertEqual(cle(lancer({"FENETRES_OMBRE_DECALAGE": v}), "decoration", "shadow", "offset"),
                             {"1": xy[0], "2": xy[1]})

    def test_economie_ne_reactive_rien(self):
        for reg in ({}, {"FENETRES_OMBRE_DECALAGE": "dure", "FENETRES_FOND": "noir", "FENETRES_DISPOSITION": "master",
                         "FENETRES_MAITRE_ORIENTATION": "centre"}):
            a = lancer(reg, economie=True)
            self.assertEqual(cle(a, "decoration", "shadow", "enabled"), False)
            self.assertEqual(cle(a, "decoration", "blur", "enabled"), False)
            self.assertEqual(cle(a, "animations", "enabled"), False)


class Reglages(unittest.TestCase):
    def test_valeurs(self):
        reg = charger_reglages()
        attendu = {"FENETRES_MAITRE_ORIENTATION": ("auto", "gauche", "droite", "haut", "bas", "centre"),
                   "FENETRES_FOND": ("auto", "noir"), "FENETRES_OMBRE_DECALAGE": ("auto", "aucun", "bas", "dure"),
                   "FENETRES_DISPOSITION": ("dwindle", "master", "scrolling")}
        for k, vals in attendu.items():
            r = reg.PAR_CLE[k]
            for v in vals:
                self.assertEqual(r.valider(v), v)
            for v in ("inconnu", "", "monocle"):
                with self.assertRaises(ValueError):
                    r.valider(v)
            self.assertNotIn(k, reg.DISTANT_PERMIS)
        self.assertEqual(reg.PAR_CLE["FENETRES_DISPOSITION"].defaut, "dwindle")
        for k in ("FENETRES_MAITRE_ORIENTATION", "FENETRES_FOND", "FENETRES_OMBRE_DECALAGE"):
            self.assertEqual(reg.PAR_CLE[k].defaut, "auto")

    def test_theme_accepte_les_cles(self):
        reg = charger_reglages()
        d = {"nom": "essai", "libelle": {"fr": "Essai", "en": "Test"}, "palette": {"source": "fond", "nom": ""},
             "reglages": {"FENETRES_DISPOSITION": "scrolling", "FENETRES_MAITRE_ORIENTATION": "droite",
                          "FENETRES_FOND": "noir", "FENETRES_OMBRE_DECALAGE": "dure"}}
        self.assertEqual(reg._verifier_theme("essai", d)["reglages"]["FENETRES_OMBRE_DECALAGE"], "dure")
        d["reglages"]["FENETRES_DISPOSITION"] = "monocle"
        with self.assertRaises(ValueError):
            reg._verifier_theme("essai", d)


if __name__ == "__main__":
    unittest.main()

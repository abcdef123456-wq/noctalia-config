"""FENETRES_CARACTERE : un jeu de courbes (et un facteur de durée) par caractère d'animation, dans nc/apparence.lua.
« auto » et un réglage absent ou inconnu rendent exactement les appels d'avant (référence écrite en dur, relevée sur main).
apparence.lua est exécuté avec lua et de faux hl / nc : jamais le vrai Hyprland. L'effet réel à l'écran n'est pas testé."""
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
VALEURS = ("auto", "doux", "vif", "sec", "rebond", "aucun")

# Faux hl et nc : REG = les réglages posés, sortie en JSON (courbes, animations, clés de hl.config)
PRELUDE = r'''
local cj = function(v)
  local function s(x)
    if type(x) == "table" then
      local t = {}
      for i, y in ipairs(x) do t[i] = s(y) end
      return "[" .. table.concat(t, ",") .. "]"
    end
    return string.format("%.17g", x)
  end
  return s(v)
end
courbes, anims, cfg = {}, {}, {}
hl = {
  config = function(t) cfg[#cfg + 1] = t end,
  curve = function(n, o) courbes[#courbes + 1] = '"' .. n .. '":' .. cj(o.points) end,
  animation = function(a)
    anims[#anims + 1] = string.format('["%s",%s,%.17g,"%s","%s"]', a.leaf, tostring(a.enabled), a.speed, a.bezier, a.style or "")
  end,
}
nc = { reglage = function(k, d) if REG[k] ~= nil then return REG[k] end return d end, hypr_min = function() return false end,
       profil = { profil = PROFIL or "balanced" } }
'''
SORTIE = r'''
io.write("{" .. table.concat(courbes, ",") .. "}\n[" .. table.concat(anims, ",") .. "]\n")
local anim_cfg = false
for _, t in ipairs(cfg) do if t.animations then anim_cfg = tostring(t.animations.enabled) end end  -- le dernier gagne
io.write(tostring(anim_cfg) .. "\n")
'''


def lancer(reg, economie=False, avec_energie=False):
    lig = ", ".join(f'{k} = "{v}"' for k, v in reg.items())
    code = f'REG = {{ {lig} }}\nPROFIL = {'"power-saver"' if economie else 'nil'}\n' + PRELUDE + f'dofile("{APPARENCE}")\n'
    if avec_energie:
        code += f'dofile("{ENERGIE}")\n'
    code += SORTIE
    r = subprocess.run([LUA, "-"], input=code, capture_output=True, text=True, timeout=30)
    assert r.returncode == 0, r.stdout + r.stderr
    c, a, e = r.stdout.splitlines()
    return json.loads(c), json.loads(a), e


# Référence : ce que main (f8a8ef4) appelle avec la vitesse normale
REF_COURBES = {"emphasized": [[0.05, 0.7], [0.1, 1]], "emphasizedAccel": [[0.3, 0], [0.8, 0.15]],
               "standard": [[0.2, 0], [0, 1]], "linear": [[0, 0], [1, 1]]}
REF_ANIMS = [["global", True, 5, "standard", ""], ["border", True, 5, "standard", ""],
             ["windowsIn", True, 4, "emphasized", "popin 90%"], ["windowsOut", True, 2.5, "emphasizedAccel", "popin 90%"],
             ["windowsMove", True, 4, "emphasized", "slide"], ["fadeIn", True, 3, "standard", ""],
             ["fadeOut", True, 2, "emphasizedAccel", ""], ["layersIn", True, 3, "emphasized", "fade"],
             ["layersOut", True, 2, "emphasizedAccel", "fade"], ["fadeLayersIn", True, 2.5, "standard", ""],
             ["fadeLayersOut", True, 2, "standard", ""], ["workspaces", True, 3.5, "emphasized", "slidefadevert 15%"],
             ["specialWorkspace", True, 3.5, "emphasized", "slidevert -100%"], ["zoomFactor", True, 5, "standard", ""]]


@unittest.skipUnless(LUA, "lua absent")
class Lua(unittest.TestCase):
    def test_auto_et_absent_identiques_a_main(self):
        for reg in ({}, {"FENETRES_CARACTERE": "auto"}, {"FENETRES_CARACTERE": "inconnu"}, {"FENETRES_CARACTERE": ""}):
            c, a, _ = lancer(reg)
            self.assertEqual(c, REF_COURBES, reg)
            self.assertEqual(a, REF_ANIMS, reg)

    def test_auto_garde_vitesse_et_styles(self):
        _, a, _ = lancer({"FENETRES_ANIMATIONS_VITESSE": "rapide", "FENETRES_OUVERTURE": "gnomed", "ANIM_BUREAUX": "fade"})
        self.assertEqual(a[0][2], 5 * 0.65)
        self.assertEqual(a[2][4], "gnomed")
        self.assertEqual(a[11][4], "fade")

    def test_chaque_valeur_differe_de_toutes_les_autres(self):
        jeux = {v: lancer({"FENETRES_CARACTERE": v}) for v in VALEURS}
        for v in VALEURS[1:]:
            self.assertEqual(set(jeux[v][0]), set(REF_COURBES), v)   # mêmes noms de courbes
            self.assertEqual([x[3:] for x in jeux[v][1]], [x[3:] for x in REF_ANIMS], v)   # mêmes courbes et styles
            self.assertEqual([x[0] for x in jeux[v][1]], [x[0] for x in REF_ANIMS], v)
        for v in VALEURS:
            for w in VALEURS:
                if v < w:
                    for k in REF_COURBES:
                        self.assertNotEqual(jeux[v][0][k], jeux[w][0][k], f"{k} : {v} = {w}")
                    self.assertNotEqual(jeux[v][1], jeux[w][1], f"{v} = {w}")

    def test_caractere_visible(self):
        rap = {v: lancer({"FENETRES_CARACTERE": v})[1][2][2] for v in VALEURS}   # vitesse de windowsIn
        self.assertGreater(rap["doux"], rap["auto"])
        for v in ("vif", "sec", "aucun"):
            self.assertLess(rap[v], rap["auto"], v)
        self.assertLess(rap["aucun"], rap["sec"])
        ys = lambda v: [p[1] for pts in lancer({"FENETRES_CARACTERE": v})[0].values() for p in pts]   # noqa: E731
        self.assertTrue(any(y > 1 for y in ys("rebond")))
        self.assertTrue(any(y > 1 for y in ys("vif")))
        self.assertFalse(any(y > 1 for y in ys("doux") + ys("sec")))

    def test_economie_rien_reactive(self):
        # le réglage ne change pas animations.enabled ; energie.lua (chargé après) le coupe en Économie
        for v in VALEURS:
            _, _, cfg = lancer({"FENETRES_CARACTERE": v})
            self.assertEqual(cfg, "true", v)   # apparence.lua pose enabled = true, comme sur main
            _, _, cfg = lancer({"FENETRES_CARACTERE": v}, economie=True, avec_energie=True)
            self.assertEqual(cfg, "false", v)   # energie.lua passe en dernier et coupe

    def test_mutation_sentinelle(self):
        # le test de référence échoue si un point d'auto change (contrôle que la comparaison compare vraiment)
        c, _, _ = lancer({})
        c["emphasized"][0][0] = 0.06
        self.assertNotEqual(c, REF_COURBES)


def charger_reglages():
    l = importlib.machinery.SourceFileLoader("nc_reglages_caractere", str(REPO / "home/.local/bin/nc-reglages"))
    m = importlib.util.module_from_spec(importlib.util.spec_from_loader("nc_reglages_caractere", l))
    l.exec_module(m)
    return m


class Reglages(unittest.TestCase):
    def test_valeurs(self):
        reg = charger_reglages()
        r = reg.PAR_CLE["FENETRES_CARACTERE"]
        self.assertEqual(r.defaut, "auto")
        for v in VALEURS:
            self.assertEqual(r.valider(v), v)
        for v in ("inconnu", "", "DOUX"):
            with self.assertRaises(ValueError):
                r.valider(v)
        self.assertNotIn("FENETRES_CARACTERE", reg.DISTANT_PERMIS)   # comme FENETRES_OUVERTURE

    def test_theme_accepte_la_cle(self):
        reg = charger_reglages()
        d = {"nom": "essai", "libelle": {"fr": "Essai", "en": "Test"}, "palette": {"source": "fond", "nom": ""},
             "reglages": {"FENETRES_CARACTERE": "rebond"}}
        self.assertEqual(reg._verifier_theme("essai", d)["reglages"]["FENETRES_CARACTERE"], "rebond")
        d["reglages"]["FENETRES_CARACTERE"] = "inconnu"
        with self.assertRaises(ValueError):
            reg._verifier_theme("essai", d)


class Bornes(unittest.TestCase):
    def test_depassement_borne_a_1_3(self):
        """Tant que personne ne l'a vu à l'écran : aucun point de courbe hors de [-0,3 ; 1,3]."""
        import re
        src = (Path(__file__).resolve().parents[1] / "home/.config/hypr/nc/apparence.lua").read_text(encoding="utf-8")
        jeux = [l for l in src.splitlines() if re.match(r"\s*\w+\s*=\s*\{\s*f\s*=", l)]     # une ligne par caractère
        self.assertGreaterEqual(len(jeux), 6)
        ys = [float(y) for l in jeux for y in re.findall(r"\{\s*-?[\d.]+\s*,\s*(-?[\d.]+)\s*\}", l)]
        self.assertTrue(ys)
        self.assertLessEqual(max(ys), 1.3)
        self.assertGreaterEqual(min(ys), -0.3)


if __name__ == "__main__":
    unittest.main()

"""hypr/nc/zones.lua : la disposition nc-zones des bureaux rangés par l'IA, hors Hyprland (faux hl, fausses fenêtres).
Les fenêtres restent en tuiles : poser un arbre, ouvrir et fermer une fenêtre, échanger, changer le sens, redimensionner."""
from pathlib import Path
import shutil
import subprocess
import unittest

ZONES = Path(__file__).resolve().parents[1] / "home/.config/hypr/nc/zones.lua"

HARNAIS = r'''
local regles, enregistre, active = {}, nil, nil
nc = { reglage = function(_, d) return d end }
hl = {
  layout = { register = function(nom, f) enregistre = { nom = nom, f = f } end },
  workspace_rule = function(r) regles[#regles + 1] = r.workspace .. "=" .. r.layout end,
  get_active_window = function() return active end,
}
dofile(arg[1])
assert(nc.zones_dispo and enregistre.nom == "nc-zones", "disposition enregistrée")
local area = { x = 10, y = 52, w = 1580, h = 938 }
local fen = {}
local function f(adr) fen[adr] = fen[adr] or { address = adr, workspace = { id = 2 }, floating = false } return fen[adr] end
local function calcul(ordre)
  local places, ctx = {}, { area = area, targets = {} }
  function ctx:grid_cell(i, n) return { x = 0, y = 0, w = 1, h = 1 } end
  for _, a in ipairs(ordre) do
    ctx.targets[#ctx.targets + 1] = { window = f(a), place = function(_, b) places[a] = b end }
  end
  enregistre.f.recalculate(ctx)
  return places, ctx
end
local function vaut(b, x, y, w, h, m) assert(b and b.x == x and b.y == y and b.w == w and b.h == h,
  m .. " : " .. (b and (b.x .. "," .. b.y .. " " .. b.w .. "x" .. b.h) or "nil")) end

nc.zones_poser(2, { sens = "v", r = 0.6, a = { f = "0xa" }, b = { sens = "h", r = 0.5, a = { f = "0xb" }, b = { f = "0xc" } } })
assert(regles[1] == "2=lua:nc-zones", "règle du bureau")
local p = calcul({ "0xa", "0xb", "0xc" })
vaut(p["0xa"], 10, 52, 948, 938, "a 60 % à gauche"); vaut(p["0xb"], 958, 52, 632, 469, "b en haut à droite")
vaut(p["0xc"], 958, 521, 632, 469, "c en bas à droite")
-- Échange (Hyprland change l'ordre) : les places suivent l'ordre
p = calcul({ "0xb", "0xa", "0xc" })
vaut(p["0xb"], 10, 52, 948, 938, "échange : b prend la grande place")
-- Nouvelle fenêtre, a active : la place de a (en haut à droite maintenant) est coupée en deux
active = f("0xa")
p = calcul({ "0xb", "0xa", "0xc", "0xd" })
assert(p["0xd"] and (p["0xa"].h + p["0xd"].h == 469 or p["0xa"].w + p["0xd"].w == 632), "ouverture : la place de la fenêtre active partagée")
-- Fermeture : la voisine reprend la place
p = calcul({ "0xb", "0xa", "0xc" })
vaut(p["0xa"], 958, 52, 632, 469, "fermeture : a reprend sa place")
-- togglesplit sur c : la découpe droite devient verticale
active = f("0xc")
enregistre.f.layout_msg({ area = area }, "togglesplit")
p = calcul({ "0xb", "0xa", "0xc" })
vaut(p["0xc"], 1274, 52, 316, 938, "togglesplit")
-- resize : b (grande, à gauche) s'élargit de 158 points (10 % de la largeur)
active = f("0xb")
enregistre.f.layout_msg({ area = area }, "resize 158 0")
p = calcul({ "0xb", "0xa", "0xc" })
vaut(p["0xb"], 10, 52, 1106, 938, "resize")
-- Retirer : la disposition habituelle revient, et ce bureau n'a plus de zones
nc.zones_retirer(2)
assert(regles[#regles] == "2=dwindle" and nc.zones[2] == nil, "retrait")
print("OK")
'''


@unittest.skipUnless(shutil.which("lua"), "Lua requis")
class ZonesLua(unittest.TestCase):
    def test_disposition_en_tuiles(self):
        r = subprocess.run(["lua", "-", str(ZONES)], input=HARNAIS, text=True, capture_output=True, timeout=10)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("OK", r.stdout)

    def test_sans_api_rien_ne_casse(self):
        r = subprocess.run(["lua", "-", str(ZONES)], input='nc = {} hl = {} dofile(arg[1]) assert(nc.zones_dispo == false) print("OK")',
                           text=True, capture_output=True, timeout=10)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


if __name__ == "__main__":
    unittest.main()

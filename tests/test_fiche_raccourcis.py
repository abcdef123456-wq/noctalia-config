"""Fiche des raccourcis (Super + /, plugin nc/keys) : jamais plus haute que l'écran. Avec beaucoup de raccourcis et des
descriptions sur deux lignes, tout est réduit pour tenir sous la barre ; sur un grand écran, rien n'est réduit."""
import json
from pathlib import Path
import shutil
import subprocess
import unittest

REPO = Path(__file__).resolve().parents[1]
PANEL = REPO / "home/.local/share/noctalia/plugins/nc-keys/panel.luau"


@unittest.skipUnless(shutil.which("lua"), "Lua requis")
class Fiche(unittest.TestCase):
    def hauteur(self, ecran_h, lignes):
        sections = [{"title": t, "label": t, "rows": [{"keys": ["Super", "Ctrl", "Maj", "Tab"], "text": "Une description assez longue pour passer sur deux lignes " + str(i)}
                                                      for i in range(n)]}
                    for t, n in lignes.items()]
        harness = r'''
local rendu
local function noeud(k) return function(o, enfants) return { k = k, o = o or {}, e = enfants or {} } end end
ui = setmetatable({}, { __index = function(_, k) return noeud(k) end })
panel = { render = function(n) rendu = n end, setNeedsFrameTick = function() end, close = function() end }
local donnees = ''' + json.dumps(json.dumps(sections)) + r'''
noctalia = {
  getenv = function() return "fr" end, expandPath = function(p) return p end, readFile = function() return "" end,
  fileExists = function() return false end, focusedOutputName = function() return "E" end,
  outputs = function() return { { name = "E", focused = true, width = 1600, height = ''' + str(ecran_h) + r''' } } end,
  json = { decode = function(t) return DECODE(t) end },
  runAsync = function(_, cb) if cb then cb({ exitCode = 0, stdout = donnees }) end end,
}
-- Petit décodeur JSON (tables, chaînes, nombres) pour le test
function DECODE(t)
  local i = 1
  local function ws() while t:sub(i, i):match("%s") do i = i + 1 end end
  local val
  local function str() local j = i + 1; local out = {}
    while true do local c = t:sub(j, j)
      if c == "\\" then local d = t:sub(j + 1, j + 1)
        if d == "u" then out[#out + 1] = utf8.char(tonumber(t:sub(j + 2, j + 5), 16)); j = j + 6 else out[#out + 1] = d; j = j + 2 end
      elseif c == '"' then i = j + 1; return table.concat(out) else out[#out + 1] = c; j = j + 1 end end end
  function val() ws(); local c = t:sub(i, i)
    if c == "{" then i = i + 1; local o = {}; ws(); if t:sub(i, i) == "}" then i = i + 1; return o end
      while true do ws(); local k = str(); ws(); i = i + 1; o[k] = val(); ws(); local d = t:sub(i, i); i = i + 1; if d == "}" then return o end end
    elseif c == "[" then i = i + 1; local a = {}; ws(); if t:sub(i, i) == "]" then i = i + 1; return a end
      while true do a[#a + 1] = val(); ws(); local d = t:sub(i, i); i = i + 1; if d == "]" then return a end end
    elseif c == '"' then return str()
    else local n = t:match("^-?[%d.]+", i); i = i + #n; return tonumber(n) end end
  return val()
end
dofile(arg[1])
onOpen()
local function cherche(n) if n.k == "scroll" then return n.o.height end
  if n.k == "row" and n.o.gap and n.o.align == "start" and n.o.height then return n.o.height end
  for _, e in ipairs(n.e or {}) do local h = cherche(e); if h then return h end end end
print("HAUTEUR", cherche(rendu))
'''
        r = subprocess.run(["lua", "-", str(PANEL)], input=harness, text=True, capture_output=True, timeout=10)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return float(r.stdout.split("HAUTEUR")[1])

    def test_tient_dans_l_ecran(self):
        beaucoup = {"Applis et barre": 20, "Bureaux": 6, "Fenêtres": 24, "Souris": 6, "Système": 20, "IA": 10}
        self.assertLessEqual(self.hauteur(1000, beaucoup), 1000 - 120 + 2)
        self.assertLessEqual(self.hauteur(800, beaucoup), 800 - 120 + 2)

    def test_pas_reduite_quand_elle_tient(self):
        peu = {"Applis et barre": 4, "Fenêtres": 4, "Système": 4}
        self.assertGreater(self.hauteur(1000, peu), 4 * 30)        # taille normale (30 points par ligne au moins)


if __name__ == "__main__":
    unittest.main()

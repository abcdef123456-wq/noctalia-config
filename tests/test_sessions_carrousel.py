"""Carrousel des sessions (plugin nc/sessions) : panel.luau exécuté par lua avec un faux Noctalia et un faux nc-session
(format figé de « nc-session json »). Rien n'est écrit hors d'un dossier temporaire."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import tomllib
import unittest

REPO = Path(__file__).resolve().parents[1]
PLUGIN = REPO / "home/.local/share/noctalia/plugins/nc-sessions"
MSG = REPO / "home/.local/bin/nc-shell-msg"

# Faux Noctalia : ui.* rend un arbre { t, p, c } ; runAsync note la commande et répond comme nc-session (callbacks
# différés, rejoués par vider()) ; panel.render garde le dernier arbre.
HARNAIS = r'''
local JSON_FILE, PANEL, DIR = arg[1], arg[2], arg[3]
local function lire(p) local f = io.open(p) if not f then return nil end local s = f:read("a") f:close() return s end

-- Décodeur JSON minimal (null → nil, comme un champ absent)
local function decode(s)
  local i = 1
  local function ws() i = s:find("[^ \t\r\n]", i) or #s + 1 end
  local val
  local function str()
    local out, j = {}, i + 1
    while true do
      local ch = s:sub(j, j)
      if ch == '"' then break end
      if ch == "\\" then
        local e = s:sub(j + 1, j + 1)
        local map = { n = "\n", t = "\t", ['"'] = '"', ["\\"] = "\\", ["/"] = "/" }
        out[#out + 1] = map[e] or e; j = j + 2
      else out[#out + 1] = ch; j = j + 1 end
    end
    i = j + 1
    return table.concat(out)
  end
  function val()
    ws()
    local ch = s:sub(i, i)
    if ch == "{" then
      local t = {}; i = i + 1; ws()
      if s:sub(i, i) == "}" then i = i + 1 return t end
      while true do
        ws(); local k = str(); ws(); i = i + 1
        t[k] = val(); ws()
        local d = s:sub(i, i); i = i + 1
        if d == "}" then return t end
      end
    elseif ch == "[" then
      local t = {}; i = i + 1; ws()
      if s:sub(i, i) == "]" then i = i + 1 return t end
      local n = 0
      while true do
        n = n + 1; t[n] = val(); ws()
        local d = s:sub(i, i); i = i + 1
        if d == "]" then return t end
      end
    elseif ch == '"' then return str()
    elseif s:sub(i, i + 3) == "true" then i = i + 4 return true
    elseif s:sub(i, i + 4) == "false" then i = i + 5 return false
    elseif s:sub(i, i + 3) == "null" then i = i + 4 return nil
    else
      local num = s:match("^-?[%d.eE+-]+", i); i = i + #num
      return tonumber(num)
    end
  end
  return val()
end

calls, pending, closed, tree, ticks = {}, {}, false, nil, false
REPONSES = {}   -- sous-commande → { exitCode, stdout, stderr }
local function rep(argv)
  local sub = argv[1] == "sh" and argv[6] or argv[2]
  if argv[1] == "sh" then sub = "ouvrir" end
  if REPONSES[sub] then return REPONSES[sub] end
  if sub == "json" then return { exitCode = 0, stdout = lire(JSON_FILE), stderr = "" } end
  return { exitCode = 0, stdout = "ok\n", stderr = "" }
end
noctalia = {
  getenv = function(n) if n == "NC_LANGUE" then return "fr" end return nil end,
  expandPath = function(p) return (p:gsub("^~", DIR)) end,
  readFile = function(p) return lire(p) end,
  outputs = function() return { { name = "eDP-1", width = 1600, height = 1000, focused = true } } end,
  focusedOutputName = function() return "eDP-1" end,
  fileExists = function(p) return lire(p) ~= nil end,
  wallpaperPath = function() return nil end,
  appIconPath = function(c) if c == "firefox" or c == "kitty" then return "/icones/" .. c .. ".png" end return nil end,
  string = { trim = function(s) return (s:match("^%s*(.-)%s*$")) end },
  json = { decode = decode },
  runAsync = function(argv, cb)
    table.insert(calls, argv)
    if cb then table.insert(pending, function() cb(rep(argv)) end) end
  end,
}
panel = {
  close = function() closed = true end,
  setNeedsFrameTick = function(on) ticks = on end,
  render = function(t) tree = t end,
}
ui = setmetatable({}, { __index = function(_, nom)
  return function(p, c) return { t = nom, p = p or {}, c = c or {} } end
end })

function vider()
  while #pending > 0 do local f = table.remove(pending, 1); f() end
end
function noeuds(t, out)
  out = out or {}
  if type(t) ~= "table" then return out end
  if t.t then table.insert(out, t) end
  for _, k in ipairs(t.c or {}) do noeuds(k, out) end
  return out
end
function textes() local o = {} for _, n in ipairs(noeuds(tree)) do if n.t == "label" then table.insert(o, n.p.text) end end return o end
function contient(mot)
  for _, s in ipairs(textes()) do if s:find(mot, 1, true) then return true end end
  return false
end
function images() local o = {} for _, n in ipairs(noeuds(tree)) do if n.t == "image" then o[n.p.path] = true end end return o end
function cartes() local o = {} for _, n in ipairs(noeuds(tree)) do if n.p.key and n.p.key:match("^c%d+$") then table.insert(o, n) end end return o end
function derniere() return calls[#calls] end
function touche(k) onKey(k, true); onKey(k, false) end
function verifier(c, m) if not c then error(m or "échec", 2) end end

dofile(PANEL)
'''


def session(nom, **plus):
    s = {"nom": nom, "date": "2026-10-19T10:00:00", "nb_fenetres": 2, "applis": ["firefox", "kitty"], "icone": "code",
         "couleur": "tertiary", "fond": None, "profil": "garder", "npd": False, "demarrage": False, "fermer_autres": "non",
         "raccourci": None, "bureaux_noms": {"1": "Code"}, "apercu": None,
         "schema": [{"ecran": "eDP-1", "bureau": 1, "largeur": 1600, "hauteur": 1000,
                     "rects": [{"x": 0.0, "y": 0.0, "w": 0.5, "h": 1.0, "classe": "firefox"},
                               {"x": 0.5, "y": 0.0, "w": 0.5, "h": 1.0, "classe": "kitty"}]},
                    {"ecran": "eDP-1", "bureau": 2, "largeur": 1600, "hauteur": 1000,
                     "rects": [{"x": 0.1, "y": 0.1, "w": 0.8, "h": 0.8, "classe": "kitty"}]}],
         "fenetres": []}
    s.update(plus)
    return s


@unittest.skipUnless(shutil.which("lua"), "lua requis")
class Carrousel(unittest.TestCase):
    def lancer(self, sessions, scenario, apercu=False):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            if apercu:
                (root / "Web.png").write_bytes(b"png")
                for s in sessions:
                    if s["nom"] == "Web":
                        s["apercu"] = str(root / "Web.png")
            (root / "sessions.json").write_text(json.dumps({"version": 2, "sessions": sessions}))
            (root / "harnais.lua").write_text(HARNAIS + "\n" + scenario)
            r = subprocess.run(["lua", str(root / "harnais.lua"), str(root / "sessions.json"), str(PLUGIN / "panel.luau"), d],
                               capture_output=True, text=True, timeout=10, env=dict(os.environ, HOME=d))
            self.assertEqual(r.returncode, 0, r.stderr + r.stdout)

    def test_cartes_depuis_le_json(self):
        # Dev : schéma (deux bureaux), couleur du thème ; Web : capture, couleur #hex ; puis « + Nouvelle session »
        self.lancer([session("Dev"), session("Web", couleur="#ff8800", applis=["firefox"], icone="public")], r'''
onOpen(nil); vider()
verifier(calls[1][2] == "json", "liste lue par nc-session json")
local c = cartes()
verifier(#c == 3, "deux sessions et la nouvelle : " .. #c)
verifier(contient("Dev") and contient("Code"), "nom et nom du bureau")
verifier(contient("il y a"), "date relative")
verifier(contient("2 fenêtres"), "nombre de fenêtres")
local im = images()
verifier(im["/icones/firefox.png"] and im["/icones/kitty.png"], "icônes des applis")
local fills, glyphes = {}, {}
for _, n in ipairs(noeuds(tree)) do
  if n.p.fill then fills[n.p.fill] = true end
  if n.t == "glyph" then glyphes[n.p.name] = true end
end
verifier(fills["tertiary"], "couleur de la session (rôle du thème)")
verifier(glyphes["code"] and glyphes["plus"], "icône Material → Tabler et carte +")
-- schéma : bureaux 1 et 2, trois rectangles de fenêtres
local rangees = 0
for _, n in ipairs(noeuds(tree)) do if n.t == "label" and (n.p.text == "Code" or n.p.text == "Bureau 2") then rangees = rangees + 1 end end
verifier(rangees == 2, "une rangée par bureau")
touche("Right")
for _ = 1, 30 do onFrameTick(16) end
local im2 = images()
local trouve = false
for p in pairs(im2) do if p:match("Web%.png$") then trouve = true end end
verifier(trouve, "capture de Web affichée")
fills = {}
for _, n in ipairs(noeuds(tree)) do if n.p.fill then fills[n.p.fill] = true end end
verifier(fills["#ff8800"], "couleur #hex")
for _, n in ipairs(noeuds(tree)) do if n.t == "glyph" and n.p.name == "world" then trouve = "w" end end
verifier(trouve == "w", "public → world")
''', apercu=True)

    def test_entree_ouvre_et_ferme(self):
        self.lancer([session("Dev"), session("Web")], r'''
onOpen(nil); vider()
touche("Right"); for _ = 1, 30 do onFrameTick(16) end
touche("Return")
verifier(closed, "panneau fermé")
local a = derniere()
local vu = table.concat(a, " ")
verifier(vu:find("ouvrir", 1, true) and a[#a] == "Web", "nc-session ouvrir Web : " .. vu)
''')

    def test_maj_suppr_confirme_puis_supprime(self):
        self.lancer([session("Dev"), session("Web")], r'''
onOpen(nil); vider()
local avant = #calls
touche("shift+Delete")
verifier(#calls == avant, "rien supprimé avant la confirmation")
verifier(contient("Supprimer « Dev » ? ↵ oui · Échap non"), "confirmation sur la carte")
touche("Escape")
verifier(not closed and not contient("Supprimer « Dev »"), "Échap : non, le panneau reste")
touche("shift+Delete"); touche("Return")
local a = calls[#calls]
verifier(a[2] == "supprimer" and a[3] == "Dev", "nc-session supprimer Dev")
vider()
verifier(calls[#calls][2] == "json", "liste relue après la suppression")
verifier(not closed, "le panneau reste ouvert")
-- la nouvelle carte ne se supprime pas
touche("End"); touche("shift+Delete")
verifier(not contient("Supprimer «"), "pas de confirmation sur + Nouvelle session")
-- E : l'éditeur (bientôt)
touche("Home"); touche("e")
verifier(contient("Bientôt"), "E → editer()")
''')

    def test_nouvelle_session_enregistre_le_nom(self):
        self.lancer([session("Dev")], r'''
onOpen(nil); vider()
touche("End"); touche("Return")
local champ
for _, n in ipairs(noeuds(tree)) do if n.t == "input" then champ = n end end
verifier(champ and champ.p.focus, "champ du nom")
champ.p.onChange("Jeux d")
touche("e")   -- « e » capturé : ajouté au nom par le panneau
for _, n in ipairs(noeuds(tree)) do if n.t == "input" then champ = n end end
verifier(champ.p.value == "Jeux de", "e ajouté au nom : " .. tostring(champ.p.value))
champ.p.onChange("Jeux")
champ.p.onSubmit()
local a = calls[#calls]
verifier(a[2] == "enregistrer" and a[3] == "Jeux", "nc-session enregistrer Jeux")
vider()
verifier(calls[#calls][2] == "json", "liste relue après l'enregistrement")
-- nom refusé : la phrase de nc-session, le champ reste
REPONSES.enregistrer = { exitCode = 1, stdout = "", stderr = "Nom de session : lettres, chiffres\n" }
touche("End"); touche("Return")
for _, n in ipairs(noeuds(tree)) do if n.t == "input" then champ = n end end
champ.p.onChange("a/b"); touche("Return"); vider()
verifier(contient("Nom de session : lettres, chiffres"), "erreur affichée")
local reste = false
for _, n in ipairs(noeuds(tree)) do if n.t == "input" then reste = true end end
verifier(reste, "le champ reste pour corriger")
''')

    def test_sans_session_une_seule_carte(self):
        self.lancer([], r'''
onOpen(nil); vider()
verifier(#cartes() == 1, "seulement + Nouvelle session : " .. #cartes())
verifier(contient("Aucune session pour l'instant"), "phrase simple")
touche("shift+Delete"); touche("e")
verifier(not contient("Supprimer «") and not contient("Bientôt"), "rien à supprimer ni à modifier")
touche("Escape")
verifier(closed, "Échap ferme")
''')

    def test_economie_sans_animation(self):
        self.lancer([session("Dev"), session("Web")], r'''
local f = io.open(DIR .. "/.config/noctalia/zz-economie.toml", "w")
if not f then os.execute("mkdir -p '" .. DIR .. "/.config/noctalia'"); f = io.open(DIR .. "/.config/noctalia/zz-economie.toml", "w") end
f:write(""); f:close()
onOpen(nil); vider()
verifier(not ticks, "pas d'animation à l'ouverture")
touche("Right")
onFrameTick(16)
verifier(not ticks, "défilement immédiat, sans images suivantes")
''')


class Integration(unittest.TestCase):
    def test_plugin_active_exporte_et_raccourci(self):
        manifeste = tomllib.loads((PLUGIN / "plugin.toml").read_text())
        self.assertEqual(manifeste["id"], "nc/sessions")
        self.assertEqual(manifeste["plugin_api"], 32)
        conf = (REPO / "home/.config/noctalia/config.toml").read_text()
        ligne = next(l for l in conf.splitlines() if l.startswith("enabled = ["))
        self.assertIn('"nc/sessions"', ligne)
        self.assertIn(".local/share/noctalia/plugins/nc-sessions\n", (REPO / "export.sh").read_text())
        rac = (REPO / "home/.config/hypr/nc/raccourcis.lua").read_text()
        self.assertIn('SUPER .. " + SHIFT + code:25", cmd(barre .. "sessions")', rac)

    def faux(self, plugin, vivant=True):
        d = tempfile.TemporaryDirectory(prefix="nc-sessions-"); self.addCleanup(d.cleanup)
        root = Path(d.name); b = root / "bin"; b.mkdir()
        j = root / "journal"
        for nom, corps in {"pgrep": "exit " + ("0" if vivant else "1"), "noctalia": 'echo "noctalia $*" >> "$J"; exit ' + ("0" if vivant else "1"),
                           "hyprctl": 'echo "hyprctl $*" >> "$J"', "systemctl": "exit 0", "sleep": "exit 0",
                           "notify-send": 'echo "notify-send" >> "$J"'}.items():
            (b / nom).write_text("#!/bin/sh\n" + corps + "\n"); (b / nom).chmod(0o755)
        (root / ".local/bin").mkdir(parents=True)
        s = root / ".local/bin/nc-session"
        s.write_text('#!/bin/sh\necho "nc-session $*" >> "$J"\n'); s.chmod(0o755)
        if plugin:
            p = root / ".local/share/noctalia/plugins/nc-sessions"; p.mkdir(parents=True)
            (p / "plugin.toml").write_text('id = "nc/sessions"\n')
            (root / ".config/noctalia").mkdir(parents=True)
            (root / ".config/noctalia/config.toml").write_text('[plugins]\nenabled = ["nc/launcher", "nc/sessions"]\n')
        env = dict(os.environ, HOME=str(root), PATH=f"{b}:/usr/bin:/bin", J=str(j), XDG_RUNTIME_DIR=str(root),
                   XDG_CONFIG_HOME=str(root / ".config"))
        r = subprocess.run(["bash", str(MSG), "sessions"], env=env, capture_output=True, text=True, timeout=10)
        return r.returncode, j.read_text() if j.exists() else ""

    def test_raccourci_ouvre_le_carrousel(self):
        code, j = self.faux(plugin=True)
        self.assertEqual(code, 0, j)
        self.assertIn("noctalia msg panel-toggle nc/sessions:main", j)
        self.assertNotIn("nc-session menu", j)

    def test_sans_plugin_le_menu_de_repli(self):
        code, j = self.faux(plugin=False)
        self.assertEqual(code, 0, j)
        self.assertIn("nc-session menu", j)
        self.assertNotIn("panel-toggle", j)

    def test_noctalia_injoignable_menu_de_repli(self):
        code, j = self.faux(plugin=True, vivant=False)
        self.assertIn("nc-session menu", j)


if __name__ == "__main__":
    unittest.main()

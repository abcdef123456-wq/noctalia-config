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
ECRAN = { 1600, 1000 }
-- hyprctl -j clients : deux fenêtres sur le bureau 1, une sur le 3
CLIENTS = [[ [{"class": "firefox", "workspace": {"id": 1}, "mapped": true, "at": [0, 0], "size": [800, 1000]},
  {"class": "kitty", "workspace": {"id": 1}, "mapped": true, "at": [800, 0], "size": [800, 1000]},
  {"class": "kitty", "workspace": {"id": 3}, "mapped": true, "at": [0, 0], "size": [1600, 1000]}] ]]
MONITEURS = [[ [{"name": "eDP-1", "focused": true, "x": 0, "y": 0, "width": 1600, "height": 1000, "scale": 1,
  "transform": 0, "activeWorkspace": {"id": 1}}] ]]
REPONSES = {}   -- sous-commande → { exitCode, stdout, stderr }
local function rep(argv)
  local sub = argv[2]
  if argv[1] == "sh" then sub = argv[3]:find("grim", 1, true) and "grim" or "ouvrir" end
  if argv[1] == "hyprctl" then sub = "hyprctl " .. argv[3] end
  if argv[1] == "rm" then sub = "rm" end
  if REPONSES[sub] then return REPONSES[sub] end
  if sub == "hyprctl clients" then return { exitCode = 0, stdout = CLIENTS, stderr = "" } end
  if sub == "hyprctl monitors" then return { exitCode = 0, stdout = MONITEURS, stderr = "" } end
  if REPONSES[sub] then return REPONSES[sub] end
  if sub == "json" then return { exitCode = 0, stdout = lire(JSON_FILE), stderr = "" } end
  return { exitCode = 0, stdout = "ok\n", stderr = "" }
end
noctalia = {
  getenv = function(n) if n == "NC_LANGUE" then return "fr" end if n == "XDG_RUNTIME_DIR" then return DIR .. "/run" end return nil end,
  nowMs = function() return 42 end,
  expandPath = function(p) return (p:gsub("^~", DIR)) end,
  readFile = function(p) return lire(p) end,
  outputs = function() return { { name = "eDP-1", width = ECRAN[1], height = ECRAN[2], focused = true } } end,
  focusedOutputName = function() return "eDP-1" end,
  fileExists = function(p) return lire(p) ~= nil end,
  wallpaperPath = function() return nil end,
  wallpaperDirectory = function() return DIR .. "/fonds" end,
  listDir = function(d)
    local o, f = {}, io.popen("ls '" .. d .. "' 2>/dev/null")
    for l in f:lines() do table.insert(o, l) end
    f:close()
    return o
  end,
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
function trouver(cle, prefixe)
  for _, n in ipairs(noeuds(tree)) do
    if n.p.key == cle or (prefixe and type(n.p.key) == "string" and n.p.key:sub(1, #cle) == cle) then return n end
  end
  return nil
end
function dans(parent, cle)
  for _, n in ipairs(noeuds(parent)) do if n.p.key == cle then return n end end
  return nil
end
function compte(mot) local k = 0 for _, t in ipairs(textes()) do if t == mot then k = k + 1 end end return k end
-- dernière commande de nc-session : modifier Dev CLE VALEUR ?
function modifie(cle, v)
  local a = nil
  for i = #calls, 1, -1 do if calls[i][1]:find("nc%-session$") then a = calls[i]; break end end
  return a[2] == "modifier" and a[3] == "Dev" and a[4] == cle and a[5] == v, table.concat(a, " ")
end
function commandes(sub) local k = 0 for _, a in ipairs(calls) do if a[1]:find("nc%-session$") and a[2] == sub then k = k + 1 end end return k end
-- Images suivantes tant que le panneau en demande (défilement, apparition du volet), comme Noctalia
function defiler() for _ = 1, 60 do if not ticks then break end onFrameTick(16) end end
function touche(k) onKey(k, true); onKey(k, false); defiler() end
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
         "fenetres": [{"classe": "firefox", "titre": "Firefox", "bureau": 1, "ecran": "eDP-1", "flottant": False,
                       "plein_ecran": False, "inclure": True, "terminal": None},
                      {"classe": "kitty", "titre": "nvim", "bureau": 2, "ecran": "eDP-1", "flottant": False,
                       "plein_ecran": False, "inclure": True,
                       "terminal": {"programme": "nvim", "dossier": "/tmp", "commande": "nvim ."}}],
         "tranche": None, "tranche_etroite": None}
    s.update(plus)
    return s


@unittest.skipUnless(shutil.which("lua"), "lua requis")
class Carrousel(unittest.TestCase):
    def lancer(self, sessions, scenario, apercu=False, tranches=(), outil=False):
        """tranches : noms des sessions qui ont leurs tranches inclinées (NOM.W.png, NOM.N.png) ; outil : un faux
        ~/.local/bin/nc-carousel-thumbs (le harnais répond à « tranche » comme lui, code 0 par défaut)."""
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "fonds").mkdir()
            for f in ("aube.jpg", "nuit.png", "notes.txt"):
                (root / "fonds" / f).write_bytes(b"img")
            for s in sessions:
                if s["nom"] in tranches:
                    n = s["nom"]
                    (root / f"{n}.W.png").write_bytes(b"png"); (root / f"{n}.N.png").write_bytes(b"png")
                    s["tranche"], s["tranche_etroite"] = str(root / f"{n}.W.png"), str(root / f"{n}.N.png")
            if outil:
                (root / ".local/bin").mkdir(parents=True)
                (root / ".local/bin/nc-carousel-thumbs").write_text("#!/bin/sh\nexit 1\n")
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
verifier(#c == 4, "trois cartes en boucle (la dernière revient à gauche de la première) : " .. #c)
verifier(trouver("c0") and trouver("c3"), "voisines de part et d'autre : la bande boucle")
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
verifier(trouver("i2") and trouver("i2").p.fit == "cover" and trouver("i2").p.width == 720, "la capture remplit la carte")
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
verifier(contient("Supprimer « Dev » ?") and contient("oui") and contient("non") and trouver("touche:↵"), "confirmation sous la carte")
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
-- E (si Noctalia la transmettait) : l'éditeur
touche("Home"); touche("e")
verifier(trouver("volet") and contient("Modifier « Dev »"), "E → editer()")
''')

    def test_nouvelle_session_enregistre_le_nom(self):
        self.lancer([session("Dev")], r'''
onOpen(nil); vider()
touche("End"); touche("Return")
local champ
for _, n in ipairs(noeuds(tree)) do if n.t == "input" then champ = n end end
verifier(champ and champ.p.focus, "champ du nom")
champ.p.onChange("Jeux d")
for _, n in ipairs(noeuds(tree)) do if n.t == "input" then champ = n end end
verifier(champ.p.value == "Jeux d", "le texte tapé reste dans le champ : " .. tostring(champ.p.value))
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
local dedans = false
for _, n in ipairs(noeuds(trouver("c1"))) do if n.t == "label" and n.p.text:find("Aucune session", 1, true) then dedans = true end end
verifier(dedans, "la phrase est dans la carte « nouvelle »")
verifier(compte("Nouvelle session") == 1, "un seul « Nouvelle session » : " .. compte("Nouvelle session"))
touche("shift+Delete"); touche("e")
verifier(not contient("Supprimer «") and not trouver("volet"), "rien à supprimer ni à modifier")
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

    def test_editeur_s_ouvre(self):
        self.lancer([session("Dev"), session("Web")], r'''
onOpen(nil); vider()
verifier(not trouver("volet"), "pas de volet au départ")
trouver("c1").p.onRightClick()
verifier(trouver("volet"), "clic droit : le volet")
verifier(contient("Modifier « Dev »"), "titre du volet")
for _, k in ipairs({ "s:icone", "s:couleur", "s:fond", "s:profil", "s:npd", "s:demarrage", "s:fermer_autres", "s:raccourci",
                     "s:bureau.1", "s:bureau.2", "s:fenetre.0.inclure", "s:fenetre.1.inclure", "s:fenetre.1.dossier",
                     "s:fenetre.1.commande" }) do
  verifier(trouver(k), "champ " .. k)
end
verifier(not trouver("s:fenetre.0.dossier"), "pas de dossier pour une fenêtre qui n'est pas un terminal")
verifier(trouver("ed:icone:movie") and trouver("ed:couleur:outline") and trouver("ed:fond:"), "icônes, couleurs, aucun fond")
verifier(trouver("ed:fond:" .. DIR .. "/fonds/aube.jpg") and not trouver("ed:fond:" .. DIR .. "/fonds/notes.txt"),
  "fonds du dossier des fonds, images seulement")
verifier(contient("Garder le profil") and contient("Équilibré") and contient("Économie") and contient("Garder les autres fenêtres"),
  "libellés du profil et de fermer les autres")
local g = false
for _, n in ipairs(noeuds(trouver("volet"))) do if n.t == "glyph" and n.p.name == "rocket" then g = true end end
verifier(g, "rocket_launch → rocket")
-- bouton Modifier de la carte
touche("Escape")
verifier(not trouver("volet") and not closed, "Échap ferme le volet")
trouver("modifier").p.onClick()
verifier(trouver("volet"), "bouton Modifier")
''')

    def test_chaque_champ_envoie_modifier(self):
        self.lancer([session("Dev"), session("Web")], r'''
onOpen(nil); vider()
trouver("c1").p.onRightClick()
local function clic(k, cle, v)
  local n = trouver(k)
  verifier(n, "case " .. k)
  n.p.onClick()
  local ok, vu = modifie(cle, v)
  verifier(ok, k .. " : " .. vu)
  local avant = commandes("json")
  vider()
  verifier(commandes("json") == avant + 1, "relu après " .. k)
  verifier(trouver("volet"), "le volet reste après " .. k)
end
clic("ed:icone:movie", "icone", "movie")
clic("ed:couleur:secondary", "couleur", "secondary")
clic("ed:fond:" .. DIR .. "/fonds/nuit.png", "fond", DIR .. "/fonds/nuit.png")
clic("ed:fond:", "fond", "")
clic("ed:profil:balanced", "profil", "balanced")
clic("ed:fermer_autres:demander", "fermer_autres", "demander")
local function bascule(k, cle, v)
  trouver(k).p.onChange(true)
  local ok, vu = modifie(cle, v)
  verifier(ok, k .. " : " .. vu)
  vider()
end
bascule("ed:npd", "npd", "oui")
bascule("ed:demarrage", "demarrage", "oui")
bascule("ed:fenetre.0.inclure", "fenetre.0.inclure", "non")
local function saisir(k, cle, t, v)
  local n = trouver("t:" .. k .. ":", true)
  verifier(n, "champ " .. k)
  n.p.onChange(t)
  local avant = commandes("modifier")
  touche("Return")
  local ok, vu = modifie(cle, v)
  verifier(ok, k .. " : " .. vu)
  n.p.onSubmit()   -- Entrée vue aussi par le champ : pas d'envoi en double
  verifier(commandes("modifier") == avant + 1, "un seul envoi pour " .. k)
  vider()
end
saisir("raccourci", "raccourci", "Super+Alt+1", "Super+Alt+1")
saisir("bureau.2", "bureau.2.nom", "  Jeux ", "Jeux")
saisir("fenetre.1.dossier", "fenetre.1.dossier", "/tmp/x", "/tmp/x")
saisir("fenetre.1.commande", "fenetre.1.commande", "htop", "htop")
saisir("raccourci", "raccourci", "", "")
''')

    def test_erreur_sous_le_champ(self):
        self.lancer([session("Dev")], r'''
onOpen(nil); vider()
trouver("c1").p.onRightClick()
REPONSES.modifier = { exitCode = 1, stdout = "", stderr = "Touche inconnue : Z9.\n" }
trouver("t:raccourci:", true).p.onChange("Super+Z9")
touche("Return"); vider()
local e = dans(trouver("s:raccourci"), "err:raccourci")
verifier(e and e.p.text == "Touche inconnue : Z9." and e.p.color == "error", "refus sous le champ, couleur d'erreur")
verifier(trouver("t:raccourci:", true).p.value == "Super+Z9", "le texte reste pour corriger")
verifier(not dans(trouver("s:icone"), "err:icone"), "les autres champs sans erreur")
REPONSES.modifier = nil
touche("Return"); vider()
verifier(not trouver("err:raccourci"), "erreur effacée une fois acceptée")
''')

    def test_tab_parcourt_les_champs(self):
        self.lancer([session("Dev")], r'''
onOpen(nil); vider()
trouver("c1").p.onRightClick()
local function focus() for _, n in ipairs(noeuds(tree)) do
  if type(n.p.key) == "string" and n.p.key:match("^s:") and n.p.border == "primary" then return n.p.key end end end
local ordre = { "s:icone", "s:couleur", "s:fond", "s:profil", "s:npd", "s:demarrage", "s:fermer_autres", "s:raccourci",
  "s:bureau.1", "s:bureau.2", "s:fenetre.0.inclure", "s:fenetre.1.inclure", "s:fenetre.1.dossier", "s:fenetre.1.commande" }
for i, k in ipairs(ordre) do
  verifier(focus() == k, "Tab " .. i .. " : " .. tostring(focus()) .. " au lieu de " .. k)
  touche("Tab")
end
verifier(focus() == "s:icone", "après le dernier, le premier")
touche("shift+Tab")
verifier(focus() == "s:fenetre.1.commande", "Maj + Tab : le précédent")
verifier(trouver("t:fenetre.1.commande:", true).p.focus, "le champ texte a le focus")
verifier(not trouver("t:raccourci:", true).p.focus, "un seul champ avec le focus")
touche("ISO_Left_Tab")
verifier(focus() == "s:fenetre.1.dossier", "ISO_Left_Tab aussi")
touche("Tab"); touche("Tab")
verifier(focus() == "s:icone", "retour à l'icône")
touche("Right"); touche("Return")
local ok, vu = modifie("icone", "work")
verifier(ok, "→ puis Entrée : icône suivante : " .. vu)
vider()
touche("Tab"); touche("Left"); touche("Return")
ok, vu = modifie("couleur", "secondary")
verifier(ok, "← sur la couleur (tertiary → secondary) : " .. vu)
vider()
touche("Tab"); touche("Tab"); touche("Tab"); touche("Return")
ok, vu = modifie("npd", "oui")
verifier(ok, "Entrée bascule l'interrupteur : " .. vu)
''')

    def test_echap_ferme_le_volet_puis_le_panneau(self):
        self.lancer([session("Dev"), session("Web")], r'''
onOpen(nil); vider()
trouver("c1").p.onRightClick()
verifier(trouver("volet"), "volet ouvert")
touche("Escape")
verifier(not trouver("volet") and not closed, "1er Échap : le volet")
touche("Escape")
verifier(closed, "2e Échap : le panneau")
''')

    def test_economie_editeur_sans_animation(self):
        self.lancer([session("Dev"), session("Web")], r'''
os.execute("mkdir -p '" .. DIR .. "/.config/noctalia'")
local f = io.open(DIR .. "/.config/noctalia/zz-economie.toml", "w"); f:write(""); f:close()
onOpen(nil); vider()
trouver("c1").p.onRightClick()
verifier(not ticks, "pas d'animation à l'ouverture du volet")
verifier(trouver("volet").p.opacity == 1, "volet affiché d'un coup")
''')

    def test_volet_a_cote_de_la_carte(self):
        # La carte du milieu glisse juste assez à gauche pour que le volet, à droite, ne la couvre pas
        for w, h in ((1600, 1000), (1280, 800)):
            with self.subTest(ecran=f"{w}x{h}"):
                self.lancer([session("Dev"), session("Web")], r'''
ECRAN = { %d, %d }
onOpen(nil); vider()
trouver("c1").p.onRightClick()
defiler()
local v = trouver("volet")
local z = math.min(1, ECRAN[1] / 1600, ECRAN[2] / 1000)
local bgw = ECRAN[1] - 16
local cw = trouver("c1").p.width
verifier(v.p.width == math.floor(440 * z + 0.5), "largeur du volet : " .. v.p.width)
verifier(v.p.height == ECRAN[2] - 42 - 32, "toute la hauteur du cadre : " .. v.p.height)
-- décalage de la bande : boîte vide de tête (2 s) ; centre de la carte = bgw / 2 - decal
local bande
for _, n in ipairs(noeuds(tree)) do if n.t == "row" and n.c[2] and n.c[2].p.key and n.c[2].p.key:match("^r") then bande = n end end
local x = 0
for _, k in ipairs(bande.c) do
  if k.p.key == "r1" then break end
  x = x + k.p.width + 4
end
local gauche = (bgw - bande.p.width) / 2 + x + 30   -- bord gauche de la carte dans le cadre
verifier(gauche + cw + math.floor(16 * z + 0.5) <= bgw - 8 - v.p.width + 1, "pas de recouvrement : " .. (gauche + cw) .. " / " .. (bgw - 8 - v.p.width))
verifier(gauche >= 16, "carte à plus de 16 points du bord gauche")
''' % (w, h))

    def test_lettres_vont_au_champ(self):
        manifeste = tomllib.loads((PLUGIN / "plugin.toml").read_text())
        touches = manifeste["panel"][0]["capture_keys"]
        self.assertFalse([t for t in touches if len(t) == 1], "aucune lettre capturée : " + repr(touches))
        self.lancer([session("Dev")], r'''
onOpen(nil); vider()
touche("End"); touche("Return")
local champ
for _, n in ipairs(noeuds(tree)) do if n.t == "input" then champ = n end end
champ.p.onChange("essai")
for _, l in ipairs({ "e", "s", "s", "a", "i" }) do touche(l) end
for _, n in ipairs(noeuds(tree)) do if n.t == "input" then champ = n end end
verifier(champ.p.value == "essai", "le texte vaut essai : " .. tostring(champ.p.value))
verifier(not trouver("volet"), "l'éditeur ne s'ouvre pas")
touche("Escape"); touche("Home")
trouver("c1").p.onRightClick()
local avant = #calls
touche("e"); touche("q")
verifier(#calls == avant and trouver("volet"), "lettres ignorées par l'éditeur")
''')

    def test_tranches_inclinees(self):
        # Chaque session a ses tranches et nc-carousel-thumbs est là : la bande est celle des fonds, rien que des images
        self.lancer([session("Dev"), session("Web"), session("Cours")], r'''
onOpen(nil); vider()
local outil
for _, a in ipairs(calls) do if a[1] == DIR .. "/.local/bin/nc-carousel-thumbs" then outil = a end end
local g
for _, a in ipairs(calls) do if a[1] == "sh" and a[3]:find("grim", 1, true) then g = a end end
verifier(outil and outil[2] == "tranche" and outil[3] == g[4], "l'écran en direct passe dans nc-carousel-thumbs tranche")
verifier(outil[4]:sub(1, #DIR + 5) == DIR .. "/run/" and outil[5]:sub(1, #DIR + 5) == DIR .. "/run/",
  "tranches temporaires dans XDG_RUNTIME_DIR")
-- toutes les cartes de la bande sont des images, sans boîte ni verre derrière
local n = 0
for _, c in ipairs(cartes()) do
  n = n + 1
  verifier(c.t == "image", "carte " .. c.p.key .. " : une image seule, pas un " .. c.t)
end
verifier(n >= 4, "bande pleine : " .. n)
for _, nd in ipairs(noeuds(tree)) do
  verifier(nd.p.fill ~= "surface/0.55" or nd.p.radius == math.floor(40 / 2), "aucun verre de carte derrière une tranche")
  verifier(nd.p.fill ~= "#00000073", "aucun voile de carte droite")
  if nd.t == "row" and type(nd.p.key) == "string" and nd.p.key:match("^r%-?%d+$") then
    verifier(#nd.c == 1 and nd.c[1].t == "image", "rangée " .. nd.p.key .. " : l'image seule")
  end
end
local dev = trouver("c1")
verifier(dev.p.path:match("Dev%.W%.png$") and math.abs(dev.p.width - (600 + 0.30 * 450)) < 0.01 and dev.p.height == 450,
  "au milieu : la grande tranche, taille des fonds")
local web = trouver("c2")
verifier(web.p.path:match("Web%.N%.png$") and math.abs(web.p.width - (192 + 0.30 * 420)) < 0.01 and web.p.height == 420
  and web.p.fit == "cover", "voisine : tranche étroite, taille des fonds : " .. web.p.width)
verifier(web.p.opacity == 0.7, "voisine à 70 % (comme les fonds)")
-- les informations de la session choisie, sous la tranche
local titre = trouver("titre")
verifier(titre, "titre sous la tranche")
local nom, info, pastille, glyphe, applis = false, false, false, false, 0
for _, nd in ipairs(noeuds(titre)) do
  if nd.t == "label" and nd.p.text == "Dev" and nd.p.fontWeight == "bold" and nd.p.fontSize == 22 then nom = true end
  if nd.t == "label" and nd.p.text:match("^2 fenêtres · il y a %d+ jours$") then info = true end
  if nd.t == "box" and nd.p.fill == "tertiary" and nd.p.width == 12 then pastille = true end
  if nd.t == "glyph" and nd.p.name == "code" and nd.p.color == "tertiary" then glyphe = true end
  if nd.t == "image" and nd.p.path:match("^/icones/") then applis = applis + 1 end
end
verifier(nom and info and pastille and glyphe and applis == 2, "nom en gras 22, pastille, icône, fenêtres et date, applis")
verifier(dans(titre, "modifier"), "« Modifier » à côté du nom")
local lignes = 0
for _, nd in ipairs(noeuds(tree)) do if nd.p.key == "aide" then lignes = lignes + 1 end end
verifier(lignes == 1 and trouver("touche:↵"), "une seule ligne d'aide, en pastilles")
-- clic droit sur une tranche : l'éditeur
touche("Right"); for _ = 1, 30 do onFrameTick(16) end
web = trouver("c2")
verifier(web.p.path:match("Web%.W%.png$"), "Web au milieu : sa grande tranche")
verifier(contient("Web") and not contient("Dev"), "le titre suit la carte choisie")
web.p.onRightClick()
verifier(trouver("volet"), "clic droit sur une tranche : l'éditeur")
touche("Escape")
-- « Nouvelle session » : une tranche aussi, le « + » et le texte dessous
touche("End"); for _ = 1, 30 do onFrameTick(16) end
local nv = trouver("c4")
verifier(nv and nv.t == "image" and nv.p.path == outil[4], "Nouvelle session : la grande tranche de l'écran en direct")
verifier(math.abs(nv.p.width - (600 + 0.30 * 450)) < 0.01, "même taille que les autres tranches")
titre = trouver("titre")
local plus, texte = false, false
for _, nd in ipairs(noeuds(titre)) do
  if nd.t == "glyph" and nd.p.name == "plus" then plus = true end
  if nd.t == "label" and nd.p.text == "Nouvelle session" then texte = true end
end
verifier(plus and texte and compte("Nouvelle session") == 1, "le « + » et « Nouvelle session » sous la tranche")
verifier(contient("3 fenêtres sur 2 bureaux"), "fenêtres de l'écran actuel sous la tranche")
-- voisine étroite de « Nouvelle session »
touche("Left"); for _ = 1, 30 do onFrameTick(16) end
verifier(trouver("c4").p.path == outil[5], "voisine : la tranche étroite de l'écran en direct")
-- nom de la nouvelle session : le champ sous la tranche
touche("Right"); for _ = 1, 30 do onFrameTick(16) end
touche("Return")
local champ
for _, nd in ipairs(noeuds(trouver("titre"))) do if nd.t == "input" then champ = nd end end
verifier(champ and champ.p.focus, "le champ du nom, sous la tranche")
touche("Escape")
-- tout est effacé à la fermeture
onClose()
local a = derniere()
local vus = {}
for i = 3, #a do vus[a[i]] = true end
verifier(a[1] == "rm" and vus[g[4]] and vus[outil[4]] and vus[outil[5]], "capture et tranches effacées à la fermeture")
''', tranches=("Dev", "Web", "Cours"), outil=True)

    def test_tranches_bande_centree(self):
        # La bande au milieu du cadre (comme les fonds) : une place vide au-dessus, de la hauteur de la légende
        for tr in ((), ("Dev", "Web")):
            with self.subTest(tranches=bool(tr)):
                self.lancer([session("Dev"), session("Web")], r'''
onOpen(nil); vider()
local bande
for _, nd in ipairs(noeuds(tree)) do
  if nd.t == "column" and #nd.c == 3 and nd.c[3].p.key == nil and nd.c[2].t == "row" and nd.c[2].p.height == 480 then bande = nd end
end
verifier(bande, "colonne de la bande")
verifier(bande.c[1].p.height == bande.c[3].p.height, "place au-dessus = légende dessous : "
  .. bande.c[1].p.height .. " / " .. bande.c[3].p.height)
''', tranches=tr, outil=True)

    def test_tranches_attendues_puis_pretes(self):
        # Pendant que l'écran en direct se découpe : une place vide pour « Nouvelle session », déjà en tranches
        self.lancer([session("Dev")], r'''
onOpen(nil)
table.remove(pending, 1)()   -- nc-session json seulement
verifier(trouver("c1").t == "image", "tranches tout de suite (la tranche de Nouvelle session est attendue)")
verifier(not trouver("c2"), "Nouvelle session : une place vide en attendant")
vider()
verifier(trouver("c2") and trouver("c2").t == "image", "puis sa tranche")
''', tranches=("Dev",), outil=True)

    def test_sans_outil_toutes_droites(self):
        cas = {
            "sans nc-carousel-thumbs": ("", ("Dev", "Web"), False),
            "tranches manquantes pour une session": ("", ("Web",), True),
            "découpe impossible (ImageMagick absent)": ('REPONSES.tranche = { exitCode = 1, stdout = "", stderr = "" }',
                                                         ("Dev", "Web"), True),
            "sans grim": ('REPONSES.grim = { exitCode = 3, stdout = "", stderr = "" }', ("Dev", "Web"), True),
        }
        for nom, (avant, tranches, outil) in cas.items():
            with self.subTest(cas=nom):
                self.lancer([session("Dev"), session("Web")], avant + r'''
onOpen(nil); vider()
for _, c in ipairs(cartes()) do verifier(c.t == "column", "carte " .. c.p.key .. " droite, pas " .. c.t) end
for p in pairs(images()) do verifier(not p:match("%.[WN]%.png$") and not p:match("tranche"), "aucune tranche : " .. p) end
verifier(not trouver("titre"), "titre dans la carte, pas dessous")
''', tranches=tranches, outil=outil)

    def test_tranche_du_fond_sans_capture(self):
        # SESSIONS_CAPTURE=non : « Nouvelle session » prend les tranches du fond courant (carrousel des fonds)
        self.lancer([session("Dev")], r'''
os.execute("mkdir -p '" .. DIR .. "/.config/nc' '" .. DIR .. "/.cache/nc/carousel'")
local f = io.open(DIR .. "/.config/nc/reglages.conf", "w"); f:write('SESSIONS_CAPTURE="non"\n'); f:close()
for _, x in ipairs({ "W", "N" }) do
  f = io.open(DIR .. "/.cache/nc/carousel/aube.jpg." .. x .. ".webp", "w"); f:write("img"); f:close()
end
noctalia.wallpaperPath = function() return DIR .. "/fonds/aube.jpg" end
onOpen(nil); vider()
for _, a in ipairs(calls) do verifier(not (a[1] == "sh" and a[3]:find("grim", 1, true)), "pas de grim") end
local nv = trouver("c2")
verifier(nv and nv.t == "image" and nv.p.path:match("aube%.jpg%.N%.webp$"), "voisine : tranche étroite du fond")
touche("Right"); for _ = 1, 30 do onFrameTick(16) end
verifier(trouver("c2").p.path:match("aube%.jpg%.W%.webp$"), "au milieu : grande tranche du fond")
''', tranches=("Dev",), outil=True)

    def test_style_des_cartes(self):
        for w, h in ((1600, 1000), (1280, 800), (1920, 1080)):
            with self.subTest(ecran=f"{w}x{h}"):
                self.lancer([session("Dev"), session("Web")], r'''
ECRAN = { %d, %d }
onOpen(nil); vider()
local z = math.min(1, ECRAN[1] / 1600, ECRAN[2] / 1000)
if ECRAN[1] > 1600 or ECRAN[2] > 1000 then z = math.max(1, math.min(2, ECRAN[1] / 1600, ECRAN[2] / 1000)) end
local c = trouver("c1")
verifier(c.p.height == math.floor(450 * z + 0.5), "hauteur de la tranche du milieu des fonds : " .. c.p.height)
verifier(math.abs(c.p.width / c.p.height - ECRAN[1] / ECRAN[2]) < 0.01, "ratio de l'écran : " .. c.p.width .. "x" .. c.p.height)
-- verre : fond de surface à 55 %%, reflet blanc 16 %%, contour d'accent de 1,5 sur la choisie seulement
local fond, reflet, contour = false, false, nil
for _, n in ipairs(noeuds(c)) do
  if n.p.fill == "surface/0.55" and n.p.width == c.p.width then fond = true end
  if n.p.fill == "#ffffff29" and n.p.height == 1 then reflet = true end
  if n.p.borderWidth == 1.5 then contour = n.p.border end
  verifier(not (n.p.borderWidth == 1 and n.p.border == "on_surface/0.18"), "plus de trait gris")
end
verifier(fond and reflet and contour == "primary", "verre et contour d'accent")
-- couches du verre superposées : chacune à la taille de la carte (sinon elles se décalent)
for _, k in ipairs({ "c1", "c2", "c3" }) do
  local n = trouver(k)
  if n and n.t == "column" then
    for i, couche in ipairs(n.c) do verifier(couche.p.height == n.p.height, k .. " : couche " .. i .. " de " .. tostring(couche.p.height)) end
  end
end
local v = trouver("c2")
verifier(v.p.opacity == 0.7, "voisine à 70 %% (comme les fonds)")
for _, n in ipairs(noeuds(v)) do verifier(n.p.borderWidth ~= 1.5, "aucun contour sur une voisine") end
-- la carte d'une session porte nom, nombre de fenêtres et date, applis
local nom, info = false, false
for _, n in ipairs(noeuds(c)) do
  if n.t == "label" and n.p.text == "Dev" and n.p.fontWeight == "bold" and n.p.fontSize == math.floor(22 * z + 0.5) then nom = true end
  if n.t == "label" and n.p.text:match("^2 fenêtres · il y a") then info = true end
end
verifier(nom and info, "nom en gras, « 2 fenêtres · il y a … » dans la carte")
-- une ligne d'aide en pastilles de touches
for _, k in ipairs({ "touche:↵", "touche:Maj", "touche:Suppr", "touche:Échap" }) do verifier(trouver(k), "pastille " .. k) end
local lignes = 0
for _, n in ipairs(noeuds(tree)) do if n.p.key == "aide" then lignes = lignes + 1 end end
verifier(lignes == 1, "une seule ligne d'aide")
''' % (w, h))

    def test_nouvelle_session_ecran_en_direct(self):
        self.lancer([session("Dev")], r'''
onOpen(nil)
local g
for _, a in ipairs(calls) do if a[1] == "sh" and a[3]:find("grim", 1, true) then g = a end end
verifier(g and g[3]:find("-s 0.25", 1, true), "grim -s 0.25 lancé à l'ouverture")
local f = g[4]
verifier(f:sub(1, #DIR + 5) == DIR .. "/run/" and f:match("%.png$"), "fichier temporaire dans XDG_RUNTIME_DIR : " .. f)
local h = false
for _, a in ipairs(calls) do if a[1] == "hyprctl" and a[2] == "-j" and a[3] == "clients" then h = true end end
verifier(h, "fenêtres lues par hyprctl -j clients (asynchrone)")
vider()
touche("End"); for _ = 1, 30 do onFrameTick(16) end
local d = trouver("direct")
verifier(d and d.p.path == f and d.p.fit == "cover", "miniature en fond de la carte")
local sombre = false
for _, n in ipairs(noeuds(trouver("c2"))) do if n.p.fill == "#00000073" then sombre = true end end
verifier(sombre, "assombrie à 45 %")
verifier(contient("3 fenêtres sur 2 bureaux"), "fenêtres et bureaux de l'écran actuel")
local im = images()
verifier(im["/icones/firefox.png"] and im["/icones/kitty.png"], "icônes des applis ouvertes")
verifier(compte("Nouvelle session") == 1, "un seul « Nouvelle session »")
onClose()
local a = derniere()
verifier(a[1] == "rm" and a[3] == f, "fichier effacé à la fermeture")
''')

    def test_nouvelle_session_sans_capture_ni_grim(self):
        self.lancer([], r'''
-- grim absent : rien en fond
REPONSES.grim = { exitCode = 3, stdout = "", stderr = "" }
onOpen(nil); vider()
verifier(not trouver("direct"), "sans grim : pas de miniature")
verifier(contient("Nouvelle session"), "la carte reste")
onClose()
-- SESSIONS_CAPTURE=non : pas de grim, le schéma des fenêtres du bureau actif
os.execute("mkdir -p '" .. DIR .. "/.config/nc'")
local f = io.open(DIR .. "/.config/nc/reglages.conf", "w"); f:write('SESSIONS_CAPTURE="non"\n'); f:close()
calls = {}
onOpen(nil); vider()
for _, a in ipairs(calls) do verifier(not (a[1] == "sh" and a[3]:find("grim", 1, true)), "pas de grim") end
local rects = 0
for _, n in ipairs(noeuds(trouver("c1"))) do if n.p.fill == "on_surface" and n.p.opacity == 0.55 then rects = rects + 1 end end
verifier(rects == 2, "schéma : les deux fenêtres du bureau actif : " .. rects)
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

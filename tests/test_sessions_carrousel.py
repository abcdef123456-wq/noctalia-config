"""Carrousel des sessions (plugin nc/sessions) : panel.luau exécuté par lua avec un faux Noctalia et un faux nc-session
(format figé de « nc-session json »). Rien n'est écrit hors d'un dossier temporaire."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
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
-- L'écran de l'utilisateur : 1600 x 1000 points (2560 x 1600 pixels à l'échelle 1,6), la barre réservée en haut
MONITEURS = [[ [{"name": "eDP-1", "focused": true, "x": 0, "y": 0, "width": 2560, "height": 1600, "scale": 1.6,
  "transform": 0, "reserved": [0, 42, 0, 0], "activeWorkspace": {"id": 1}}] ]]
REPONSES = {}   -- sous-commande → { exitCode, stdout, stderr }
local function rep(argv)
  local sub = argv[2]
  if argv[1] == "sh" then
    sub = argv[3]:find("grim", 1, true) and "grim" or argv[3]:find("enregistrer", 1, true) and "enregistrer" or "ouvrir"
  end
  if argv[1] == "hyprctl" then sub = "hyprctl " .. argv[3] end
  if argv[1] == "rm" then sub = "rm" end
  -- grim réussi : l'image est écrite (le .tmp renommé)
  if sub == "grim" and not REPONSES.grim then local f = io.open(argv[4], "w"); f:write("png"); f:close() end
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
function cartes() local o = {} for _, n in ipairs(noeuds(tree)) do if n.p.key and n.p.key:match("^c%-?%d+$") then table.insert(o, n) end end return o end
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
    def lancer(self, sessions, scenario, apercu=False, apercus=()):
        """apercu : la session Web a son aperçu (Web.png) ; apercus : les noms des sessions qui ont le leur."""
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "fonds").mkdir()
            (root / "run").mkdir()
            for f in ("aube.jpg", "nuit.png", "notes.txt"):
                (root / "fonds" / f).write_bytes(b"img")
            noms = set(apercus) | ({"Web"} if apercu else set())
            for s in sessions:
                if s["nom"] in noms:
                    (root / f"{s['nom']}.png").write_bytes(b"png")
                    s["apercu"] = str(root / f"{s['nom']}.png")
            (root / "sessions.json").write_text(json.dumps({"version": 2, "sessions": sessions}))
            (root / "harnais.lua").write_text(HARNAIS + "\n" + scenario)
            r = subprocess.run(["lua", str(root / "harnais.lua"), str(root / "sessions.json"), str(PLUGIN / "panel.luau"), d],
                               capture_output=True, text=True, timeout=10, env=dict(os.environ, HOME=d))
            self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
            return r.stdout

    def test_cartes_depuis_le_json(self):
        # Dev : schéma (deux bureaux), couleur du thème ; Web : capture, couleur #hex ; puis « + Nouvelle session »
        self.lancer([session("Dev"), session("Web", couleur="#ff8800", applis=["firefox"], icone="public")], r'''
onOpen(nil); vider()
verifier(calls[1][2] == "json", "liste lue par nc-session json")
local c = cartes()
verifier(#c == 3, "trois cartes en boucle, chacune une fois (la dernière revient à gauche de la première) : " .. #c)
verifier(trouver("c0") and trouver("c2"), "voisines de part et d'autre : la bande boucle")
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
verifier(trouver("i2") and trouver("i2").p.fit == "cover" and trouver("i2").p.width == 736, "la capture remplit la carte")
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
-- E n'arrive pas au panneau (non capturée) : la ligne d'aide ne la promet pas, ni un clic droit ; le bouton
-- « Modifier » à côté du nom, et l'aide sans « Modifier »
touche("Home")
verifier(trouver("modifier") and not contient("Clic droit") and not trouver("touche:E"), "bouton « Modifier »")
for _, n in ipairs(noeuds(trouver("aide"))) do verifier(not (n.t == "label" and n.p.text == "Modifier"), "aide sans « Modifier »") end
verifier(not trouver("c1").p.onRightClick, "pas de onRightClick sur la carte (ui.column le refuse)")
''')

    def test_apres_suppression_plus_rendue(self):
        # nc-session supprimer a réussi : la session sort de la bande avant tout autre rendu (même avant la relecture
        # de la liste), et pendant la suppression sa carte n'a plus d'image (son fichier s'efface)
        self.lancer([session("Dev"), session("Web"), session("Cours")], r'''
onOpen(nil); vider()
verifier(images()[DIR .. "/Dev.png"], "aperçu de Dev affiché")
touche("shift+Delete"); touche("Return")
verifier(calls[#calls][2] == "supprimer", "nc-session supprimer Dev")
verifier(not images()[DIR .. "/Dev.png"], "pendant la suppression : plus d'image pour Dev")
os.remove(DIR .. "/Dev.png")
table.remove(pending, 1)()   -- la réponse de nc-session supprimer, pas encore la relecture
verifier(not contient("Dev") and not images()[DIR .. "/Dev.png"], "Dev n'est plus dessinée")
for _ = 1, 10 do onFrameTick(16) end
verifier(not contient("Dev"), "ni aux images suivantes")
verifier(contient("Web"), "la suivante prend sa place")
-- la relecture (Dev n'y est plus)
local f = io.open(JSON_FILE, "w")
f:write('{"version": 2, "sessions": []}'); f:close()
vider()
verifier(not contient("Dev") and #cartes() == 1, "liste relue")
''', apercus=("Dev", "Web", "Cours"))

    def test_fichier_absent_le_dessin(self):
        # Aperçu annoncé mais absent (effacé entre-temps) : noctalia.fileExists faux → le dessin, aucune ui.image
        self.lancer([session("Dev", apercu="/nexiste/pas/Dev.png"), session("Web")], r'''
local vus = {}
local fe = noctalia.fileExists
noctalia.fileExists = function(p) vus[p] = true; return fe(p) end
onOpen(nil); vider()
verifier(vus["/nexiste/pas/Dev.png"], "fileExists demandé avant l'image")
verifier(not images()["/nexiste/pas/Dev.png"], "aucune ui.image pour un fichier absent")
verifier(contient("Code") and contient("Bureau 2"), "le dessin de ses fenêtres à la place")
-- présent puis effacé : au rendu suivant, plus d'image
touche("Right"); for _ = 1, 30 do onFrameTick(16) end
verifier(images()[DIR .. "/Web.png"], "Web : son aperçu")
os.remove(DIR .. "/Web.png")
onFrameTick(16); render()
verifier(not images()[DIR .. "/Web.png"], "effacé : plus d'image")
''', apercu=True)

    def test_au_plus_cinq_cartes_avec_image(self):
        noms = [f"S{i}" for i in range(8)]
        self.lancer([session(n) for n in noms], r'''
onOpen(nil); vider()
local function apercus()
  local k = 0
  for _, n in ipairs(noeuds(tree)) do if n.t == "image" and n.p.path:match("/S%d%.png$") then k = k + 1 end end
  return k
end
verifier(apercus() == 4 and #cartes() == 5, "au départ, 4 aperçus et Nouvelle session : " .. apercus() .. " / " .. #cartes())
touche("Right"); touche("Right")
verifier(apercus() == 5 and #cartes() == 5, "la choisie et 2 de chaque côté : " .. apercus() .. " / " .. #cartes())
onKey("Right", true)
for _ = 1, 3 do onFrameTick(16); verifier(apercus() <= 5, "en glissant aussi : " .. apercus()) end
onKey("Right", false); defiler()
verifier(apercus() == 5, "après : " .. apercus())
''', apercus=tuple(noms))

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
-- nom refusé (règle de nc-session) : la phrase, le champ reste, rien n'est lancé
local avant = #calls
for _, mauvais in ipairs({ "a/b", " .x", "-x", string.rep("x", 41), "a\tb" }) do
  champ.p.onChange(mauvais); touche("Return")
  verifier(#calls == avant and not closed, "refusé avant de fermer : " .. mauvais)
end
verifier(contient("Nom de session : lettres, chiffres, espaces"), "erreur affichée")
local reste = false
for _, n in ipairs(noeuds(tree)) do if n.t == "input" then reste = true end end
verifier(reste, "le champ reste pour corriger")
-- accepté (accents compris) : le panneau se ferme d'abord, nc-session enregistre une fois son calque disparu
champ.p.onChange("Jeux é-2")
champ.p.onSubmit()
verifier(closed, "panneau fermé avant la capture")
local a = calls[#calls]
verifier(a[1] == "sh" and a[4] == DIR .. "/.local/bin/nc-session" and a[5] == "Jeux é-2", "nc-session enregistrer « Jeux é-2 »")
verifier(a[3]:find('hyprctl layers', 1, true) and a[3]:find("namespace: noctalia-panel", 1, true)
  and a[3]:find('-lt 8', 1, true) and a[3]:find('sleep 0.25', 1, true), "attend la disparition du calque, 2 s au plus")
verifier(a[3]:find('exec "$0" enregistrer "$1"', 1, true) and a[3]:find("done", 1, true) < a[3]:find("enregistrer", 1, true),
  "enregistre après l'attente")
''')

    def test_attente_du_calque_en_vrai_shell(self):
        # Le script d'attente, lancé par sh : calque présent puis parti, puis absent dès le début, puis jamais parti
        script = self.lancer([session("Dev")], r'''
onOpen(nil); vider()
touche("End"); touche("Return")
local champ
for _, n in ipairs(noeuds(tree)) do if n.t == "input" then champ = n end end
champ.p.onChange("Jeux"); champ.p.onSubmit()
local a = calls[#calls]
io.write(a[3])
''')
        for k, appels in ((3, 4), (0, 1), (99, 8)):
            with self.subTest(calque=k), tempfile.TemporaryDirectory() as d:
                root = Path(d)
                (root / "bin").mkdir()
                (root / "bin/hyprctl").write_text('#!/bin/sh\nn=$(cat "$C" 2>/dev/null || echo 0); echo $((n + 1)) > "$C"\n'
                                                  '[ "$n" -lt "$K" ] && echo "namespace: noctalia-panel"\nexit 0\n')
                (root / "bin/sleep").write_text("#!/bin/sh\nexit 0\n")
                (root / "nc").write_text('#!/bin/sh\necho "$*" > "$S"\n')
                for f in ("bin/hyprctl", "bin/sleep", "nc"):
                    (root / f).chmod(0o755)
                env = dict(PATH=f"{root / 'bin'}:/usr/bin:/bin", C=str(root / "compte"), K=str(k), S=str(root / "sortie"))
                r = subprocess.run(["sh", "-c", script, str(root / "nc"), "Jeux"], env=env, capture_output=True, text=True,
                                   timeout=10)
                self.assertEqual(r.returncode, 0, r.stderr)
                self.assertEqual((root / "sortie").read_text().strip(), "enregistrer Jeux")
                self.assertEqual(int((root / "compte").read_text()), appels, "nombre de vérifications du calque")

    def test_sans_session_une_seule_carte(self):
        self.lancer([], r'''
onOpen(nil); vider()
verifier(#cartes() == 1, "seulement + Nouvelle session : " .. #cartes())
verifier(contient("Aucune session pour l'instant"), "phrase simple")
local dedans = false
for _, n in ipairs(noeuds(trouver("titre"))) do if n.t == "label" and n.p.text:find("Aucune session", 1, true) then dedans = true end end
verifier(dedans, "la phrase est sous la carte « nouvelle »")
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
trouver("modifier").p.onClick()
verifier(trouver("volet"), "« Modifier » : le volet")
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
trouver("modifier").p.onClick()
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
trouver("modifier").p.onClick()
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
trouver("modifier").p.onClick()
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
trouver("modifier").p.onClick()
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
trouver("modifier").p.onClick()
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
trouver("modifier").p.onClick()
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
  x = x + k.p.width + bande.p.gap
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
trouver("modifier").p.onClick()
local avant = #calls
touche("e"); touche("q")
verifier(#calls == avant and trouver("volet"), "lettres ignorées par l'éditeur")
''')

    def test_cartes_plates(self):
        # Plus de tranches inclinées : chaque carte est une carte droite (ui.column), ses images sont des aperçus
        self.lancer([session("Dev"), session("Web"), session("Cours")], r'''
onOpen(nil); vider()
for _, c in ipairs(cartes()) do verifier(c.t == "column", "carte " .. c.p.key .. " droite, pas " .. c.t) end
for p in pairs(images()) do
  verifier(not p:match("%.[WN]%.webp$") and not p:match("%.[WN]%.png$") and not p:match("tranche"), "aucune tranche : " .. p)
end
for _, a in ipairs(calls) do
  verifier(not a[1]:find("nc-carousel-thumbs", 1, true), "aucun appel à nc-carousel-thumbs : " .. table.concat(a, " "))
end
verifier(trouver("i1") and trouver("i1").p.radius == 10 and trouver("c1").p.radius == nil, "image aux coins de 10")
''', apercus=("Dev", "Web", "Cours"))

    def test_bande_centree(self):
        # La bande au milieu du cadre (comme les fonds) : une place vide au-dessus, de la hauteur de la légende
        self.lancer([session("Dev"), session("Web")], r'''
onOpen(nil); vider()
local bande
for _, nd in ipairs(noeuds(tree)) do
  if nd.t == "column" and #nd.c == 3 and nd.c[3].p.key == nil and nd.c[2].t == "row" and nd.c[2].p.height == 490 then bande = nd end
end
verifier(bande, "colonne de la bande")
verifier(bande.c[1].p.height == bande.c[3].p.height, "place au-dessus = légende dessous : "
  .. bande.c[1].p.height .. " / " .. bande.c[3].p.height)
''')

    def test_style_des_cartes(self):
        for w, h in ((1600, 1000), (1280, 800), (1920, 1080), (2560, 1080)):
            with self.subTest(ecran=f"{w}x{h}"):
                self.lancer([session("Dev"), session("Web"), session("Cours")], r'''
ECRAN = { %d, %d }
onOpen(nil); vider()
local z = math.min(1, ECRAN[1] / 1600, ECRAN[2] / 1000)
if ECRAN[1] > 1600 or ECRAN[2] > 1000 then z = math.max(1, math.min(2, ECRAN[1] / 1600, ECRAN[2] / 1000)) end
local c = trouver("c1")
local cadre = ECRAN[1] - 16
verifier(c.p.width == math.floor(0.46 * ECRAN[1] + 0.5), "largeur de la carte choisie : " .. c.p.width)
verifier(math.abs(c.p.width / cadre - 0.46) < 0.01, "environ 46 %% du cadre : " .. c.p.width / cadre)
verifier(math.abs(c.p.width / c.p.height - ECRAN[1] / ECRAN[2]) < 0.005, "ratio de l'écran : " .. c.p.width .. "x" .. c.p.height)
verifier(c.p.opacity == 1, "choisie opaque")
-- contour blanc de 1,5 sur la choisie seulement
local contour = nil
for _, n in ipairs(noeuds(c)) do if n.p.borderWidth == 1.5 then contour = n.p.border end end
verifier(contour == "#ffffff", "contour blanc sur la choisie : " .. tostring(contour))
for _, k in ipairs({ "c0", "c2" }) do
  local v = trouver(k)
  verifier(math.abs(v.p.width - 0.72 * c.p.width) < 0.01 and math.abs(v.p.height - 0.72 * c.p.height) < 0.01,
    k .. " à 0,72 : " .. v.p.width .. "x" .. v.p.height)
  verifier(math.abs(v.p.opacity - 0.6) < 1e-9, k .. " à 60 %% : " .. v.p.opacity)
  for _, n in ipairs(noeuds(v)) do verifier(not n.p.borderWidth or n.p.borderWidth < 1.5 or n.p.border ~= "#ffffff", "aucun contour sur " .. k) end
end
-- couches superposées : chacune à la taille de la carte (sinon elles se décalent)
for _, k in ipairs({ "c0", "c1", "c2" }) do
  local n = trouver(k)
  for i, couche in ipairs(n.c) do
    verifier(couche.p.height == n.p.height and couche.p.width == n.p.width, k .. " : couche " .. i)
  end
end
-- sous la carte : pastille, icône, nom, Modifier, fenêtres et date, applis
local titre = trouver("titre")
local nom, info, pastille, glyphe, applis = false, false, false, false, 0
for _, nd in ipairs(noeuds(titre)) do
  if nd.t == "label" and nd.p.text == "Dev" and nd.p.fontWeight == "bold" and nd.p.fontSize == math.floor(22 * z + 0.5) then nom = true end
  if nd.t == "label" and nd.p.text:match("^2 fenêtres · il y a %%d+ jours$") then info = true end
  if nd.t == "box" and nd.p.fill == "tertiary" and nd.p.width == math.floor(12 * z + 0.5) then pastille = true end
  if nd.t == "glyph" and nd.p.name == "code" and nd.p.color == "tertiary" then glyphe = true end
  if nd.t == "image" and nd.p.path:match("^/icones/") then applis = applis + 1 end
end
verifier(nom and info and pastille and glyphe and applis == 2, "nom en gras, pastille, icône, fenêtres et date, applis")
verifier(dans(titre, "modifier"), "« Modifier » à côté du nom")
-- une ligne d'aide en pastilles : ↵ ouvrir · Maj Suppr supprimer · Échap fermer
for _, k in ipairs({ "touche:↵", "touche:Maj", "touche:Suppr", "touche:Échap" }) do verifier(trouver(k), "pastille " .. k) end
local mots = {}
for _, n in ipairs(noeuds(trouver("aide"))) do if n.t == "label" and n.p.text ~= "·" then table.insert(mots, n.p.text) end end
verifier(table.concat(mots, " ") == "↵ ouvrir Maj Suppr supprimer Échap fermer", "aide : " .. table.concat(mots, " "))
local lignes = 0
for _, n in ipairs(noeuds(tree)) do if n.p.key == "aide" then lignes = lignes + 1 end end
verifier(lignes == 1, "une seule ligne d'aide")
-- glissement doux : à mi-chemin, tailles et opacités entre les deux
onKey("Right", true); onFrameTick(16); onKey("Right", false)
local d1, d2 = trouver("c1"), trouver("c2")
verifier(d1.p.width < c.p.width and d1.p.width > 0.72 * c.p.width and d2.p.width > 0.72 * c.p.width, "tailles intermédiaires")
verifier(d2.p.opacity > 0.6 and d2.p.opacity < 1, "opacité intermédiaire")
defiler()
verifier(trouver("c2").p.width == c.p.width and trouver("c2").p.opacity == 1, "Web au milieu, en grand")
''' % (w, h))

    def test_nouvelle_session_ecran_en_direct(self):
        self.lancer([session("Dev")], r'''
onOpen(nil)
verifier(calls[2][1] == "hyprctl" and calls[2][3] == "monitors", "d'abord l'écran (zones réservées, échelle)")
for _, a in ipairs(calls) do verifier(not (a[1] == "sh" and a[3]:find("grim", 1, true)), "pas de grim avant de connaître l'écran") end
table.remove(pending, 1)()     -- nc-session json
table.remove(pending, 1)()     -- hyprctl -j monitors : grim et hyprctl -j clients lancés
local g
for _, a in ipairs(calls) do if a[1] == "sh" and a[3]:find("grim", 1, true) then g = a end end
verifier(g, "grim lancé à l'ouverture")
verifier(g[5] == "33,42 1533x958" and g[6] == "0.768428", "sous la barre, au format des aperçus : " .. g[5] .. " -s " .. g[6])
verifier(g[3]:find('grim -g "$1" -s "$2" -t png "$0.tmp" && exec mv -f "$0.tmp" "$0"', 1, true), "vers un .tmp renommé une fois écrit")
local f = g[4]
verifier(f:sub(1, #DIR + 5) == DIR .. "/run/" and f:match("%.png$"), "fichier temporaire dans XDG_RUNTIME_DIR : " .. f)
table.remove(pending, 2)()     -- hyprctl -j clients, avant la fin de grim
touche("End"); for _ = 1, 30 do onFrameTick(16) end
verifier(not trouver("direct") and not images()[f], "en attendant : pas d'image")
local rects = 0
for _, n in ipairs(noeuds(trouver("c2"))) do if n.p.fill == "primary" and n.p.opacity == 0.55 then rects = rects + 1 end end
verifier(rects == 2, "le dessin des deux fenêtres du bureau actif, aux couleurs du thème : " .. rects)
vider()                        -- grim fini
local d = trouver("direct")
verifier(d and d.p.path == f and d.p.fit == "cover" and d.p.width == 736, "l'image remplace le dessin")
rects = 0
for _, n in ipairs(noeuds(trouver("c2"))) do if n.p.fill == "primary" and n.p.opacity == 0.55 then rects = rects + 1 end end
verifier(rects == 0, "plus de dessin")
verifier(contient("3 fenêtres sur 2 bureaux"), "fenêtres et bureaux de l'écran actuel")
local im = images()
verifier(im["/icones/firefox.png"] and im["/icones/kitty.png"], "icônes des applis ouvertes")
verifier(compte("Nouvelle session") == 1, "un seul « Nouvelle session »")
onClose()
local a = derniere()
verifier(a[1] == "rm" and a[3] == f and a[4] == f .. ".tmp", "image et .tmp effacés à la fermeture")
''')

    def test_nouvelle_session_fermee_avant_grim(self):
        self.lancer([session("Dev")], r'''
onOpen(nil)
table.remove(pending, 1)(); table.remove(pending, 1)()
local g
for _, a in ipairs(calls) do if a[1] == "sh" and a[3]:find("grim", 1, true) then g = a end end
onClose()
vider()
local a = derniere()
verifier(a[1] == "rm" and a[3] == g[4] and a[4] == g[4] .. ".tmp", "réponse tardive : fichiers effacés")
verifier(not trouver("direct"), "pas d'image")
''')

    def test_nouvelle_session_sans_capture_ni_grim(self):
        self.lancer([], r'''
-- grim absent : le dessin reste
REPONSES.grim = { exitCode = 3, stdout = "", stderr = "" }
onOpen(nil); vider()
verifier(not trouver("direct"), "sans grim : pas de miniature")
verifier(contient("Nouvelle session"), "la carte reste")
local rects = 0
for _, n in ipairs(noeuds(trouver("c1"))) do if n.p.fill == "primary" and n.p.opacity == 0.55 then rects = rects + 1 end end
verifier(rects == 2, "le dessin : " .. rects)
onClose()
-- grim réussi mais fichier absent : pas d'image
REPONSES.grim = { exitCode = 0, stdout = "", stderr = "" }
onOpen(nil); vider()
verifier(not trouver("direct"), "fichier absent : pas d'image")
onClose()
REPONSES.grim = nil
-- SESSIONS_CAPTURE=non : pas de grim, le schéma des fenêtres du bureau actif
os.execute("mkdir -p '" .. DIR .. "/.config/nc'")
local f = io.open(DIR .. "/.config/nc/reglages.conf", "w"); f:write('SESSIONS_CAPTURE="non"\n'); f:close()
calls = {}
onOpen(nil); vider()
for _, a in ipairs(calls) do verifier(not (a[1] == "sh" and a[3]:find("grim", 1, true)), "pas de grim") end
rects = 0
for _, n in ipairs(noeuds(trouver("c1"))) do if n.p.fill == "primary" and n.p.opacity == 0.55 then rects = rects + 1 end end
verifier(rects == 2, "schéma : les deux fenêtres du bureau actif : " .. rects)
-- sans information sur l'écran : ni grim ni dessin, la carte reste
f = io.open(DIR .. "/.config/nc/reglages.conf", "w"); f:write(''); f:close()
REPONSES["hyprctl monitors"] = { exitCode = 1, stdout = "", stderr = "" }
calls = {}
onOpen(nil); vider()
for _, a in ipairs(calls) do verifier(not (a[1] == "sh" and a[3]:find("grim", 1, true)), "pas de grim sans l'écran") end
verifier(contient("Nouvelle session"), "la carte reste")
''')


# Écrans d'essai (hyprctl -j monitors) : zone et facteur de grim calculés par le panneau et par nc-session
ECRANS_ESSAI = [
    {"name": "eDP-1", "x": 0, "y": 0, "width": 2560, "height": 1600, "scale": 1.6, "transform": 0, "reserved": [0, 42, 0, 0]},
    {"name": "eDP-1", "x": 1600, "y": 0, "width": 1920, "height": 1080, "scale": 1, "transform": 0},
    {"name": "eDP-1", "x": 0, "y": -200, "width": 1280, "height": 800, "scale": 1, "transform": 0, "reserved": [0, 0, 0, 50]},
    {"name": "eDP-1", "x": 0, "y": 0, "width": 1080, "height": 1920, "scale": 1, "transform": 1, "reserved": [0, 42, 0, 0]},
    {"name": "eDP-1", "x": 0, "y": 0, "width": 3840, "height": 2160, "scale": 1.5, "transform": 0, "reserved": [60, 0, 0, 0]},
    {"name": "eDP-1", "x": 0, "y": 0, "width": 2880, "height": 1800, "scale": 1.75, "transform": 0, "reserved": "abîmé"},
]


@unittest.skipUnless(shutil.which("lua"), "lua requis")
class Concordance(unittest.TestCase):
    """La largeur de la carte et la zone de l'aperçu : même formule dans panel.luau et dans nc-session."""

    def python(self, ecran):
        code = ("import importlib.machinery, importlib.util, json, sys\n"
                "l = importlib.machinery.SourceFileLoader('ncs', sys.argv[1])\n"
                "m = importlib.util.module_from_spec(importlib.util.spec_from_loader('ncs', l)); l.exec_module(m)\n"
                "e = json.loads(sys.argv[2]); s = e.get('scale') or 1\n"
                "w, h = round(e['width'] / s), round(e['height'] / s)\n"
                "w, h = (h, w) if e.get('transform', 0) % 2 else (w, h)\n"
                "print(json.dumps([*m.zone_capture(e), m.largeur_carte(w), m.hauteur_carte(w, h)]))\n")
        with tempfile.TemporaryDirectory() as d:
            r = subprocess.run([sys.executable, "-I", "-c", code, str(REPO / "home/.local/bin/nc-session"), json.dumps(ecran)],
                               capture_output=True, text=True, timeout=10, env=dict(os.environ, HOME=d, NC_LANGUE="fr"))
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)

    def lua(self, ecran):
        s = ecran.get("scale") or 1
        w, h = round(ecran["width"] / s), round(ecran["height"] / s)
        if ecran.get("transform", 0) % 2:
            w, h = h, w
        sortie = Carrousel.lancer(self, [session("Dev")], r'''
ECRAN = { %d, %d }
MONITEURS = [==[ [%s] ]==]
onOpen(nil); vider()
local g
for _, a in ipairs(calls) do if a[1] == "sh" and a[3]:find("grim", 1, true) then g = a end end
touche("End"); for _ = 1, 30 do onFrameTick(16) end
io.write(g[5] .. "|" .. g[6] .. "|" .. trouver("c2").p.width .. "|" .. trouver("c2").p.height)
''' % (w, h, json.dumps(dict(ecran, focused=True, activeWorkspace={"id": 1}))))
        z, f, cw, ch = sortie.split("|")
        return [z, f, int(float(cw)), int(float(ch))]

    def test_meme_formule(self):
        for e in ECRANS_ESSAI:
            with self.subTest(ecran=e):
                self.assertEqual(self.lua(e), self.python(e))

    def test_valeurs_de_l_utilisateur(self):
        # 1600 x 1000 points à l'échelle 1,6, barre de 42 : carte de 736 x 460 points, aperçu de 1178 pixels de large
        zone, facteur, cw, ch = self.python(ECRANS_ESSAI[0])
        self.assertEqual((zone, facteur, cw, ch), ("33,42 1533x958", "0.768428", 736, 460))
        self.assertEqual(int(1533 * float(facteur)), round(736 * 1.6), "grim donne 1178 pixels de large")
        self.assertEqual(int(958 * float(facteur)), round(460 * 1.6), "et 736 de haut : affiché à 1:1")


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

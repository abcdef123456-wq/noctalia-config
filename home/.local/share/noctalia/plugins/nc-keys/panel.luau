-- nc/keys (Noctalia v5) : fiche des raccourcis, générée à chaque ouverture par ~/.local/bin/nc-keys
-- (lit hyprctl binds : un raccourci ajouté dans Hyprland apparaît tout seul). Échap ou clic pour fermer.
-- Ouverture : noctalia msg panel-toggle nc/keys:main

-- Langue (nc-reglages → Apparence → Langue : auto, fr, en ; auto = celle du système) : tr("texte français", "English text")
local function env(nom)
  local v = noctalia.getenv and noctalia.getenv(nom)
  return (v and v ~= "") and v or nil
end
local function langue()
  local l = env("NC_LANGUE")
  if l ~= "fr" and l ~= "en" then
    local conf = noctalia.readFile(noctalia.expandPath("~/.config/nc/reglages.conf")) or ""
    for k, v in string.gmatch(conf, "([%u%d_]+)=([^\n]*)") do
      if k == "LANGUE" then l = string.match(v, '^%s*"?(%a*)') end
    end
  end
  if l ~= "fr" and l ~= "en" then
    local loc = env("LC_ALL") or env("LC_MESSAGES") or env("LANG")
      or string.match(noctalia.readFile("/etc/locale.conf") or "", 'LANG="?([%w_.@-]+)') or ""
    l = string.sub(loc, 1, 2) == "fr" and "fr" or "en"
  end
  return l
end
local EN = langue() == "en"
local function tr(fr, en) return EN and en or fr end

local KEYS_CMD = noctalia.expandPath("~/.local/bin/nc-keys")
local FADE_MS = 150

-- Taille : dessinée pour un écran de 1600 x 1000 points, réduite sur un écran plus petit (jamais agrandie)
local Z = 1
local function px(v) return math.floor(v * Z + 0.5) end
local function setZoom()
  local name, out = noctalia.focusedOutputName(), nil
  for _, o in ipairs(noctalia.outputs()) do
    if o.name == name or (not out and o.focused) then out = o end
  end
  out = out or noctalia.outputs()[1]
  Z = out and math.max(0.6, math.min(1, out.width / 1600, out.height / 1000)) or 1
end
local COL_W, KEY_W, ROW_H, TITLE_H, SEC_GAP = 490, 220, 30, 34, 22
local ECO = noctalia.expandPath("~/.config/noctalia/zz-economie.toml")   -- présent en mode Économie : pas d'animation
-- Sections par colonne (titres produits par nc-keys)
local COLUMNS = {
  { "Applis et barre", "Bureaux" },
  { "Fenêtres", "Souris" },
  { "Système", "IA", "Mes raccourcis" },
}
-- Titre affiché : « label » donné par nc-keys (dans la langue choisie), sinon traduit ici ; « title » est l'identifiant
-- français de la section (un titre anglais est aussi ramené au français)
local TITRES_EN = { ["Applis et barre"] = "Apps & Bar", ["Fenêtres"] = "Windows", ["Bureaux"] = "Desktops",
  ["Souris"] = "Mouse", ["Système"] = "System", ["IA"] = "AI", ["Mes raccourcis"] = "My Shortcuts" }
local TITRES_FR = { ["apps and bar"] = "Applis et barre", ["apps & bar"] = "Applis et barre", ["apps"] = "Applis et barre",
  ["windows"] = "Fenêtres", ["workspaces"] = "Bureaux", ["desktops"] = "Bureaux", ["mouse"] = "Souris",
  ["system"] = "Système", ["my shortcuts"] = "Mes raccourcis", ["spaces"] = "Bureaux" }
for fr, en in pairs(TITRES_EN) do TITRES_FR[string.lower(en)] = fr end

local sections = {}
local libelles = {}     -- titre français -> titre affiché (label de nc-keys)
local appear = 1
local ticking = false

local function chip(text)
  return ui.row({ height = px(24), paddingH = px(8), radius = px(7), align = "center", fill = "on_surface/0.08", border = "outline/0.3", borderWidth = 1 }, {
    ui.label({ text = text, fontSize = math.max(9, px(12)), fontWeight = "semibold", color = "on_surface" }),
  })
end

local function plus()
  return ui.label({ text = "+", fontSize = math.max(9, px(11)), color = "on_surface_variant" })
end

-- Une description trop longue pour sa colonne passe sur deux lignes (la ligne grandit) au lieu d'être coupée
local function hauteur(r)
  local place = COL_W - KEY_W - px(14)
  local n = utf8.len(r.text or "") or #(r.text or "")
  return n * math.max(10, px(13)) * 0.56 > place and ROW_H + px(18) or ROW_H
end

local function row(r)
  local keys = {}
  for i, k in ipairs(r.keys) do
    if i > 1 then table.insert(keys, plus()) end
    table.insert(keys, chip(k))
  end
  return ui.row({ height = hauteur(r), gap = px(14), align = "center" }, {
    ui.row({ width = KEY_W, gap = px(5), align = "center" }, keys),
    ui.label({ text = r.text, fontSize = math.max(10, px(13)), color = "on_surface_variant", maxLines = 2, maxWidth = COL_W - KEY_W - px(14) }),
  })
end

local function column(titles)
  local kids, h = {}, 0
  for _, t in ipairs(titles) do
    local sec = sections[t]
    if sec and #sec > 0 then
      if h > 0 then table.insert(kids, ui.box({ height = SEC_GAP, width = 1, opacity = 0 })); h = h + SEC_GAP end
      table.insert(kids, ui.label({ text = libelles[t] or tr(t, TITRES_EN[t] or t), fontSize = math.max(11, px(14)), fontWeight = "bold", color = "primary", height = TITLE_H }))
      h = h + TITLE_H
      for _, r in ipairs(sec) do table.insert(kids, row(r)); h = h + hauteur(r) end
    end
  end
  return ui.column({ width = COL_W, height = h, align = "stretch", gap = 0 }, kids), h
end

function render()
  local cols, maxH = {}, 0
  for _, titles in ipairs(COLUMNS) do
    local c, h = column(titles)
    table.insert(cols, c)
    if h > maxH then maxH = h end
  end
  local ease = 1 - (1 - appear) * (1 - appear)
  local body
  if maxH == 0 then
    body = ui.label({ text = tr("Lecture des raccourcis…", "Reading shortcuts…"), fontSize = 14, color = "on_surface_variant" })
    maxH = 40
  else
    body = ui.row({ gap = px(24), align = "start", height = maxH }, cols)
  end
  panel.render(ui.column({ flexGrow = 1, align = "center", justify = "center", paddingH = px(32), paddingV = px(28), opacity = ease }, { body }))
end

function onFrameTick(deltaMs)
  appear = math.min(1, appear + math.min(tonumber(deltaMs) or 16, 64) / FADE_MS)
  render()
  if appear >= 1 and ticking then ticking = false; panel.setNeedsFrameTick(false) end
end

local function load()
  noctalia.runAsync({ KEYS_CMD, "json" }, function(r)
    local data = r.exitCode == 0 and noctalia.json.decode(r.stdout)
    if type(data) == "table" then
      sections, libelles = {}, {}
      for _, s in ipairs(data) do
        local titre = tostring(s.title or "")
        titre = TITRES_FR[string.lower(titre)] or titre
        sections[titre] = s.rows
        if type(s.label) == "string" and s.label ~= "" then libelles[titre] = s.label end
      end
      render()
    end
  end, 5000)
end

function onOpen()
  EN = langue() == "en"
  setZoom()
  COL_W, KEY_W, ROW_H, TITLE_H, SEC_GAP = px(490), px(220), px(30), px(34), px(22)
  appear = 0
  ticking = true
  if noctalia.fileExists(ECO) then appear = 1; ticking = false end
  panel.setNeedsFrameTick(ticking)
  render()
  load()
end

function onClose()
  if ticking then ticking = false; panel.setNeedsFrameTick(false) end
end

load()

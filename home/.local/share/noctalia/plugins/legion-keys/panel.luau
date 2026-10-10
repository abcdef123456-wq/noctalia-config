-- Legion Keys (Noctalia v5) : fiche des raccourcis, générée à chaque ouverture par ~/.local/bin/legion-keys
-- (lit hyprctl binds : un raccourci ajouté dans Hyprland apparaît tout seul). Échap ou clic pour fermer.
-- Ouverture : noctalia msg panel-toggle legion/keys:main

local KEYS_CMD = noctalia.expandPath("~/.local/bin/legion-keys")
local COL_W = 470
local KEY_W = 180
local ROW_H = 30
local TITLE_H = 34
local SEC_GAP = 22
local FADE_MS = 150
local ECO = noctalia.expandPath("~/.config/noctalia/zz-economie.toml")   -- présent en mode Économie : pas d'animation
-- Sections par colonne (titres produits par legion-keys)
local COLUMNS = {
  { "Applis et barre", "Bureaux" },
  { "Fenêtres" },
  { "Souris", "Système" },
}

local sections = {}
local appear = 1
local ticking = false

local function chip(text)
  return ui.row({ height = 24, paddingH = 8, radius = 7, align = "center", fill = "on_surface/0.08", border = "outline/0.3", borderWidth = 1 }, {
    ui.label({ text = text, fontSize = 12, fontWeight = "semibold", color = "on_surface" }),
  })
end

local function plus()
  return ui.label({ text = "+", fontSize = 11, color = "on_surface_variant" })
end

local function row(r)
  local keys = {}
  for i, k in ipairs(r.keys) do
    if i > 1 then table.insert(keys, plus()) end
    table.insert(keys, chip(k))
  end
  return ui.row({ height = ROW_H, gap = 14, align = "center" }, {
    ui.row({ width = KEY_W, gap = 5, align = "center" }, keys),
    ui.label({ text = r.text, fontSize = 13, color = "on_surface_variant", maxLines = 1, maxWidth = COL_W - KEY_W - 14 }),
  })
end

local function column(titles)
  local kids, h = {}, 0
  for _, t in ipairs(titles) do
    local sec = sections[t]
    if sec and #sec > 0 then
      if h > 0 then table.insert(kids, ui.box({ height = SEC_GAP, width = 1, opacity = 0 })); h = h + SEC_GAP end
      table.insert(kids, ui.label({ text = t, fontSize = 14, fontWeight = "bold", color = "primary", height = TITLE_H }))
      h = h + TITLE_H
      for _, r in ipairs(sec) do table.insert(kids, row(r)) end
      h = h + #sec * ROW_H
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
    body = ui.label({ text = "Lecture des raccourcis…", fontSize = 14, color = "on_surface_variant" })
    maxH = 40
  else
    body = ui.row({ gap = 36, align = "start", height = maxH }, cols)
  end
  panel.render(ui.column({ flexGrow = 1, align = "center", justify = "center", paddingH = 32, paddingV = 28, opacity = ease }, { body }))
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
      sections = {}
      for _, s in ipairs(data) do sections[s.title] = s.rows end
      render()
    end
  end, 5000)
end

function onOpen()
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

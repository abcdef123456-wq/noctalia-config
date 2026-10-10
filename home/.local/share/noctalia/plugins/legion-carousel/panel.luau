-- Legion Carousel (Noctalia v5) : choisir le fond d'écran dans un carrousel plein écran (comme la v4).
-- Gauche/Droite (maintenir pour défiler), Entrée ou clic sur l'image centrale pour appliquer, clic sur une
-- autre image pour la centrer, taper pour chercher, Échap / clic sur le fond pour fermer.
-- Défilement animé : la position suit la cible avec un amorti exponentiel (onFrameTick).
-- Miniatures : ~/.cache/legion/carousel/<fichier>.jpg (créées par legion-carousel-thumbs).
-- Ouverture : noctalia msg panel-toggle legion/carousel:main

local THUMBS = noctalia.expandPath("~/.cache/legion/carousel/")
local EXTS = { jpg = true, jpeg = true, png = true, webp = true, bmp = true, gif = true, jxl = true, avif = true, tif = true, tiff = true }
-- Taille et opacité selon la distance à l'image centrale (interpolées entre les paliers)
local STEPS = {
  { w = 340, h = 470, a = 1.0 },
  { w = 220, h = 390, a = 0.75 },
  { w = 180, h = 330, a = 0.45 },
  { w = 120, h = 270, a = 0.2 },
  { w = 0, h = 220, a = 0.0 },
}
local ROW_H = 470
local GAP = 18
local SMOOTH_MS = 70          -- plus petit = plus rapide
local REPEAT_DELAY = 280      -- flèche maintenue : délai puis cadence
local REPEAT_EVERY = 115
local FADE_MS = 160
local ECO = noctalia.expandPath("~/.config/noctalia/zz-economie.toml")   -- présent en mode Économie : pas d'animation
local eco = false

local all = {}        -- { path, file, title, thumb }
local shown = {}      -- liste filtrée par la recherche
local target = 1      -- index cible, non replié (peut dépasser n : carrousel infini)
local pos = 1         -- position affichée (réelle), tend vers target
local query = ""
local current = nil
local inputKey = 0
local holdDir = 0
local holdT = 0
local appear = 1
local ticking = false

local function prettify(file)
  local t = file:gsub("%.[%w]+$", "")
  t = t:gsub("[-_]%d+x%d+[-_]?%d*$", "")
  t = t:gsub("[-_]+", " ")
  return t
end

local function loadList()
  all = {}
  local dir = noctalia.wallpaperDirectory()
  if not dir then return end
  if dir:sub(-1) ~= "/" then dir = dir .. "/" end
  local files = noctalia.listDir(dir) or {}
  table.sort(files, function(a, b) return a:lower() < b:lower() end)
  for _, f in ipairs(files) do
    local ext = (f:match("%.([%w]+)$") or ""):lower()
    if EXTS[ext] then
      local path = dir .. f
      local info = noctalia.fileInfo(path)
      if info and not info.isDir then
        local thumb = THUMBS .. f .. ".jpg"
        table.insert(all, { path = path, file = f, title = prettify(f), thumb = noctalia.fileExists(thumb) and thumb or path })
      end
    end
  end
end

-- Écran de référence : celui qui a le focus, sinon le premier (focusedOutputName() peut être nil)
local function outputName()
  local name = noctalia.focusedOutputName()
  if name then return name end
  local outs = noctalia.outputs()
  for _, o in ipairs(outs) do if o.focused then return o.name end end
  return outs[1] and outs[1].name or ""
end

local function wrap(i)
  local n = #shown
  return ((i - 1) % n) + 1
end

local function filter()
  local q = noctalia.string.trim(query)
  if q == "" then
    shown = all
  else
    local ranked = {}
    for _, w in ipairs(all) do
      local s = noctalia.fuzzyScore(q, w.title)
      if s then table.insert(ranked, { w = w, s = s }) end
    end
    table.sort(ranked, function(a, b) return a.s > b.s end)
    shown = {}
    for _, r in ipairs(ranked) do table.insert(shown, r.w) end
  end
  target = 1
  if q == "" and current then
    for i, w in ipairs(shown) do if w.path == current then target = i end end
  end
  pos = target
end

local function setTicking(on)
  if on ~= ticking then
    ticking = on
    panel.setNeedsFrameTick(on)
  end
end

local function step(d)
  if #shown == 0 then return end
  target = target + d
  setTicking(true)
end

local function apply(w)
  if not w then return end
  noctalia.setWallpaper(w.path)
  current = w.path
  panel.close()
end

local function lerp(a, b, t) return a + (b - a) * t end

local function sizeAt(dist)
  local d = math.min(math.abs(dist), #STEPS - 1)
  local i = math.floor(d)
  local t = d - i
  local s0, s1 = STEPS[i + 1], STEPS[math.min(i + 2, #STEPS)]
  return lerp(s0.w, s1.w, t), lerp(s0.h, s1.h, t), lerp(s0.a, s1.a, t)
end

local function cards()
  local n = #shown
  local reach = math.min(4, math.floor(n / 2))
  local center = math.floor(pos + 0.5)
  local out = {}
  for k = -reach, reach do
    local idx = center + k
    local dist = idx - pos
    local w, h, a = sizeAt(dist)
    if w >= 1 then
      local wp = shown[wrap(idx)]
      local margin = GAP / 2 * math.max(0, math.min(1, 4 - math.abs(dist)))
      local focus = math.max(0, 1 - math.abs(dist) * 2)        -- 1 au centre, 0 à mi-chemin
      local isCur = wp.path == current
      table.insert(out, ui.row({ key = "c" .. idx, width = math.floor(w + 2 * margin), height = ROW_H, align = "center", justify = "center" }, {
        ui.image({
          key = "i" .. idx,
          path = wp.thumb,
          width = math.floor(w),
          height = math.floor(h),
          fit = "cover",
          radius = 16,
          opacity = a * appear,
          border = focus > 0 and "primary" or (isCur and "secondary/0.8" or nil),
          borderWidth = focus > 0 and math.max(1, math.floor(3 * focus + 0.5)) or (isCur and 2 or 0),
          onClick = function()
            if idx == target then apply(wp) else target = idx; setTicking(true) end
          end,
        }),
      }))
    end
  end
  return out
end

function render()
  local middle
  if #shown == 0 then
    middle = ui.column({ height = ROW_H, align = "center", justify = "center", gap = 10 }, {
      ui.label({ text = #all == 0 and "Aucune image dans le dossier des fonds d'écran" or "Aucun fond d'écran trouvé", fontSize = 22, fontWeight = "bold", color = "on_surface" }),
    })
  else
    middle = ui.row({ height = ROW_H, align = "center", justify = "center", gap = 0, opacity = appear }, cards())
  end

  panel.render(ui.column({ fill = "surface/0.55", flexGrow = 1, align = "stretch", justify = "space_between", paddingV = 24, paddingH = 24, onClick = function() panel.close() end }, {
    ui.row({ height = 42, align = "center", justify = "space_between" }, {
      ui.box({ width = 42, height = 42, opacity = 0 }),
      ui.row({ width = 380, height = 42, paddingH = 16, gap = 10, align = "center", radius = 12, opacity = appear,
        fill = "surface/0.85", border = "outline/0.5", borderWidth = 1, onClick = function() end }, {
        ui.glyph({ name = "search", size = 18, color = "primary" }),
        ui.input({
          key = "q" .. inputKey,
          placeholder = "Rechercher un fond d'écran",
          fontSize = 15,
          frameVisible = false,
          focus = true,
          flexGrow = 1,
          onChange = function(v) query = v; filter(); render() end,
        }),
      }),
      ui.box({ width = 42, height = 42, opacity = 0 }),
    }),
    middle,
    ui.box({ height = 42, width = 1, opacity = 0 }),   -- garde le carrousel centré (même hauteur que la recherche)
  }))
end

function onFrameTick(deltaMs)
  local dt = math.min(tonumber(deltaMs) or 16, 64)
  if appear < 1 then appear = math.min(1, appear + dt / FADE_MS) end
  if holdDir ~= 0 then
    holdT = holdT + dt
    if holdT >= REPEAT_EVERY then
      holdT = holdT - REPEAT_EVERY
      target = target + holdDir
    end
  end
  local k = eco and 1 or (1 - math.exp(-dt / SMOOTH_MS))
  pos = pos + (target - pos) * k
  if math.abs(target - pos) < 0.003 then pos = target end
  render()
  if pos == target and holdDir == 0 and appear >= 1 then setTicking(false) end
end

function onKey(chord, pressed)
  local dir = 0
  if chord == "Left" or chord == "Up" or chord == "shift+Tab" or chord == "ISO_Left_Tab" then dir = -1
  elseif chord == "Right" or chord == "Down" or chord == "Tab" then dir = 1 end
  if dir ~= 0 then
    if pressed then
      step(dir)
      holdDir = dir
      holdT = -REPEAT_DELAY
    elseif holdDir == dir then
      holdDir = 0
    end
    return
  end
  if not pressed then return end
  if chord == "Home" then target = target - (wrap(target) - 1); setTicking(true)
  elseif chord == "End" then target = target + (#shown - wrap(target)); setTicking(true)
  elseif chord == "Return" or chord == "KP_Enter" then
    if #shown > 0 then apply(shown[wrap(target)]) end
  end
end

function onOpen(context)
  query = ""
  holdDir = 0
  inputKey = inputKey + 1
  current = noctalia.wallpaperPath(outputName())
  loadList()
  filter()
  eco = noctalia.fileExists(ECO)
  appear = eco and 1 or 0
  ticking = false
  if not eco then setTicking(true) end
  render()
end

function onClose()
  holdDir = 0
  setTicking(false)
end

-- Touches simulées (tests, raccourcis) : noctalia msg plugin legion/carousel:main all key Right
function onIpc(event, payload)
  if event == "key" and payload then onKey(payload, true); onKey(payload, false) end
end

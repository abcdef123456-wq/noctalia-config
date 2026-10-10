-- Legion Carousel (Noctalia v5) : choisir le fond d'écran dans une bande de tranches inclinées (style Serpentinum).
-- Gauche/Droite (maintenir pour défiler), Entrée ou clic sur la tranche du milieu pour appliquer, clic sur une
-- autre tranche pour la centrer, taper pour chercher, Échap pour fermer.
-- Les tranches sont des images déjà découpées en parallélogramme (l'image n'est pas déformée) par
-- ~/.local/bin/legion-carousel-thumbs : <fond>.W.webp (grande, au milieu) et <fond>.N.webp (étroite, voisines),
-- à la taille exacte d'affichage. Les tailles ci-dessous doivent rester celles du script.
-- Défilement animé : la position suit la cible avec un amorti exponentiel (onFrameTick).
-- Ouverture : noctalia msg panel-toggle legion/carousel:main

local THUMBS = noctalia.expandPath("~/.cache/legion/carousel/")
local EXTS = { jpg = true, jpeg = true, png = true, webp = true, bmp = true, gif = true, jxl = true, avif = true, tif = true, tiff = true }
local CW, CH = 600, 450      -- tranche du milieu
local NW, NH = 192, 420      -- tranche étroite (voisine immédiate)
local SK = 0.30              -- inclinaison
local SPACE = 4              -- écart entre tranches
local REACH = 3              -- tranches de chaque côté
local ROW_H = CH + 30
local SMOOTH_MS = 55         -- plus petit = plus rapide
local REPEAT_DELAY = 280     -- flèche maintenue : délai puis cadence
local REPEAT_EVERY = 115
local FADE_MS = 260
local ECO = noctalia.expandPath("~/.config/noctalia/zz-economie.toml")   -- présent en mode Économie : pas d'animation
local eco = false

local all = {}        -- { path, file, title, thumbW, thumbN }
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
        local tw, tn = THUMBS .. f .. ".W.webp", THUMBS .. f .. ".N.webp"
        table.insert(all, {
          path = path, file = f, title = prettify(f),
          thumbW = noctalia.fileExists(tw) and tw or path,
          thumbN = noctalia.fileExists(tn) and tn or path,
        })
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

-- Taille de la tranche à la distance (continue) delta du centre : grande au milieu, étroite à côté, de plus en plus petite
local function dims(delta)
  local t = math.min(delta, 1)
  local sc = delta <= 1 and 1 or math.max(0.58, 0.88 ^ (delta - 1))
  return lerp(CW, NW * sc, t), lerp(CH, NH * sc, t)
end

local function strip()
  local n = #shown
  local reach = math.min(REACH, math.max(1, math.floor(n / 2)))
  local c = math.floor(pos + 0.5)
  local fl = math.floor(pos)
  local cards, centers, x = {}, {}, 0
  for idx = c - reach, c + reach + 1 do
    local delta = math.abs(idx - pos)
    local d = math.abs(idx - c)
    local w, h = dims(d)
    local a = 1 - 0.3 * math.min(d, 1)
    if d >= REACH then a = a * 0.5 end
    local wp = shown[wrap(idx)]
    local bw = w + SK * h                                  -- largeur de l'image découpée (parallélogramme + débord)
    local kindW = d == 0
    centers[idx] = x + w / 2
    table.insert(cards, ui.row({ key = "c" .. idx, width = w, height = ROW_H, align = "center", justify = "center" }, {
      ui.image({
        key = "i" .. idx,
        path = kindW and wp.thumbW or wp.thumbN,
        width = bw,
        height = h,
        fit = "cover",
        opacity = a,
        onClick = function()
          if idx == target then apply(wp) else target = idx; setTicking(true) end
        end,
      }),
    }))
    x = x + w + SPACE
  end
  -- Amène le point « pos » au centre de l'écran (la bande est centrée : on la décale avec une boîte vide d'un côté)
  local contentW = x - SPACE
  local p = lerp(centers[fl] or contentW / 2, centers[fl + 1] or contentW / 2, pos - fl)
  local e = 1 - (1 - appear) ^ 3
  local s = contentW / 2 - p
  if s > 0 then
    table.insert(cards, 1, ui.box({ width = math.max(1, 2 * s - SPACE), height = 1, opacity = 0 }))
  elseif s < 0 then
    table.insert(cards, ui.box({ width = math.max(1, -2 * s - SPACE), height = 1, opacity = 0 }))
  end
  return ui.row({ height = ROW_H, width = contentW + 2 * math.abs(s) + 60, align = "center", justify = "center", gap = SPACE }, cards)
end

function render()
  local middle
  if #shown == 0 then
    middle = ui.column({ height = ROW_H, align = "center", justify = "center", gap = 10 }, {
      ui.label({ text = #all == 0 and "Aucune image dans le dossier des fonds d'écran" or "Aucun fond d'écran trouvé", fontSize = 22, fontWeight = "bold", color = "on_surface" }),
    })
  else
    middle = strip()
  end

  local ease = 1 - (1 - appear) * (1 - appear)
  panel.render(ui.column({ flexGrow = 1, align = "center", justify = "center", opacity = ease }, { middle, ui.box({ width = 1, height = (1 - ease) * 60, opacity = 0 }) }))
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

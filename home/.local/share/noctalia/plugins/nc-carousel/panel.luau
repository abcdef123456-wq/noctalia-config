-- nc/carousel (Noctalia v5) : choisir le fond d'écran dans une bande de tranches inclinées (style Serpentinum).
-- Gauche/Droite (maintenir pour défiler), Entrée ou clic sur la tranche du milieu pour appliquer, clic sur une
-- autre tranche pour la centrer, taper pour chercher, Échap pour fermer.
-- Les tranches sont des images déjà découpées en parallélogramme (l'image n'est pas déformée) par
-- ~/.local/bin/nc-carousel-thumbs : <fond>.W.webp (grande, au milieu) et <fond>.N.webp (étroite, voisines),
-- à la taille exacte d'affichage. Les tailles ci-dessous (et le calcul de Z) doivent rester celles du script.
-- Taille : dessinée pour un écran de 1600 x 1000 points, réduite sur un écran plus petit (jamais agrandie) ;
-- le nombre de tranches visibles est réduit si la bande ne tient pas dans la largeur de l'écran.
-- Défilement animé : la position suit la cible avec un amorti exponentiel (onFrameTick).
-- Ouverture : noctalia msg panel-toggle nc/carousel:main

local THUMBS = noctalia.expandPath("~/.cache/nc/carousel/")
local EXTS = { jpg = true, jpeg = true, png = true, webp = true, bmp = true, gif = true, jxl = true, avif = true, tif = true, tiff = true }
local BASE = { CW = 600, CH = 450, NW = 192, NH = 420, BGW = 1560, BGH = 940 }
local CW, CH = BASE.CW, BASE.CH   -- tranche du milieu
local NW, NH = BASE.NW, BASE.NH   -- tranche étroite (voisine immédiate)
local SK = 0.30              -- inclinaison
local SPACE = 4              -- écart entre tranches
local REACH = 3              -- tranches de chaque côté (au plus)
local ROW_H = CH + 30
local SCREEN_W = 1600
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
local bg = nil
local BGW, BGH = BASE.BGW, BASE.BGH
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
local function currentOutput()
  local name, out = noctalia.focusedOutputName(), nil
  for _, o in ipairs(noctalia.outputs()) do
    if o.name == name or (not out and o.focused) then out = o end
  end
  return out or noctalia.outputs()[1]
end

local function outputName()
  local o = currentOutput()
  return o and o.name or ""
end

-- Tailles pour l'écran courant (même calcul que nc-carousel-thumbs) : dessinées pour 1600 x 1000 points, réduites
-- sur un écran plus petit, agrandies sur un plus grand (jusqu'à x2) ; le fond flou prend tout l'écran, quel que soit
-- son format (16:9, 16:10, ultra-large…)
local function setZoom()
  local o = currentOutput()
  local z = o and math.max(0.6, math.min(2, o.width / 1600, o.height / 1000)) or 1
  local function px(v) return math.floor(v * z + 0.5) end
  CW, CH, NW, NH = px(BASE.CW), px(BASE.CH), px(BASE.NW), px(BASE.NH)
  if o then BGW, BGH = o.width - px(40), o.height - px(60) else BGW, BGH = px(BASE.BGW), px(BASE.BGH) end
  ROW_H = CH + px(30)
  SCREEN_W = o and o.width or 1600
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

-- Le panneau se ferme d'abord, le fond change une fois la fermeture finie : changer le fond fait recharger les plugins
-- par Noctalia, et un panneau rechargé en pleine fermeture restait figé à l'écran.
local function apply(w)
  if not w then return end
  current = w.path
  panel.close()
  noctalia.runAsync({ "sh", "-c", 'sleep 0.4; exec noctalia msg wallpaper-set "$1"', "sh", w.path })
end

local function lerp(a, b, t) return a + (b - a) * t end

-- Taille de la tranche à la distance (continue) delta du centre : grande au milieu, étroite à côté, de plus en plus petite
local function dims(delta)
  local t = math.min(delta, 1)
  local sc = delta <= 1 and 1 or math.max(0.58, 0.88 ^ (delta - 1))
  return lerp(CW, NW * sc, t), lerp(CH, NH * sc, t)
end

-- Bande de tranches, de largeur fixe (celle du fond flouté, sans dépasser l'écran) et centrée sur « pos ».
-- Deux contraintes de Noctalia : un contenu plus large que son parent n'est pas centré, et une image plus large que
-- sa case déborde à droite (elle commence au bord gauche de la case). Chaque case commence donc exactement là où
-- son image (parallélogramme + débord) doit commencer ; les tranches qui ne tiennent pas sont omises, celles proches
-- des bords s'estompent.
local function strip()
  local n = #shown
  local reach = math.min(REACH + 1, math.max(1, math.floor(n / 2) + 1))
  local half = (math.min(BGW, SCREEN_W) - 24) / 2
  local c = math.floor(pos + 0.5)
  local fl = math.floor(pos)
  -- Centre voulu de chaque tranche le long de la bande, puis centre de la bande interpolé entre deux tranches
  local items, x = {}, 0
  for idx = c - reach, c + reach + 1 do
    local d = math.abs(idx - c)
    local w, h = dims(d)
    local bw = w + SK * h                                  -- image découpée : parallélogramme + débord
    table.insert(items, { idx = idx, d = d, w = w, h = h, bw = bw, cx = x + w / 2 })
    x = x + w + SPACE
  end
  local centers = {}
  for _, it in ipairs(items) do centers[it.idx] = it.cx end
  local p = lerp(centers[fl] or x / 2, centers[fl + 1] or x / 2, pos - fl)
  -- Tranches dont l'image tient entièrement dans [-half, half] autour du centre
  local kept = {}
  for _, it in ipairs(items) do
    it.l = it.cx - it.bw / 2 - p
    it.r = it.l + it.bw
    if it.l >= -half and it.r <= half then table.insert(kept, it) end
  end
  if #kept == 0 then return ui.box({ width = 1, height = ROW_H, opacity = 0 }) end
  local cards = { ui.box({ width = math.max(0, kept[1].l + half), height = 1, opacity = 0 }) }
  for i, it in ipairs(kept) do
    local nxt = kept[i + 1]
    local edge = half - math.max(math.abs(it.l), math.abs(it.r))
    local a = (1 - 0.3 * math.min(it.d, 1)) * math.max(0.35, math.min(1, edge / NW + 0.35))
    local wp = shown[wrap(it.idx)]
    local idx = it.idx
    table.insert(cards, ui.row({ key = "c" .. idx, width = nxt and (nxt.l - it.l) or it.bw, height = ROW_H, align = "center", justify = "start" }, {
      ui.image({
        key = "i" .. idx,
        path = it.d == 0 and wp.thumbW or wp.thumbN,
        width = it.bw,
        height = it.h,
        fit = "cover",
        opacity = a,
        onClick = function()
          if idx == target then apply(wp) else target = idx; setTicking(true) end
        end,
      }),
    }))
  end
  table.insert(cards, ui.box({ width = math.max(0, half - kept[#kept].r), height = 1, opacity = 0 }))
  return ui.row({ height = ROW_H, width = 2 * half, align = "center", justify = "start", gap = 0 }, cards)
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
  panel.render(ui.column({ flexGrow = 1, align = "center", justify = "start", gap = -(BGH + ROW_H) / 2, opacity = ease }, {
    bg and ui.image({ path = bg, width = BGW, height = BGH, fit = "cover", radius = 18 }) or ui.box({ width = 1, height = 1, opacity = 0 }),
    ui.column({ height = ROW_H, width = BGW, align = "center", justify = "center" }, { middle }),
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
  setZoom()
  query = ""
  holdDir = 0
  inputKey = inputKey + 1
  current = noctalia.wallpaperPath(outputName())
  bg = nil
  if current then
    local b = THUMBS .. (current:match("([^/]+)$") or "") .. ".B.webp"
    if noctalia.fileExists(b) then bg = b end
  end
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

-- Touches simulées (tests, raccourcis) : noctalia msg plugin nc/carousel:main all key Right
function onIpc(event, payload)
  if event == "key" and payload then onKey(payload, true); onKey(payload, false) end
end

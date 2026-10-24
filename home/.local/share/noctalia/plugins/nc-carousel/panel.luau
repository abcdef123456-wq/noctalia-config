-- nc/carousel (Noctalia v5) : choisir le fond d'écran dans une bande de tranches inclinées (style Serpentinum).
-- Gauche/Droite (maintenir pour défiler), Entrée ou clic sur la tranche du milieu pour appliquer, clic sur une
-- autre tranche pour la centrer, taper pour chercher, Échap pour fermer.
-- Les tranches sont des images déjà découpées en parallélogramme (l'image n'est pas déformée) par
-- ~/.local/bin/nc-carousel-thumbs : <fond>.W.webp (grande, au milieu) et <fond>.N.webp (étroite, voisines),
-- à la taille exacte d'affichage. Les tailles ci-dessous (et le calcul de Z) doivent rester celles du script.
-- Taille : dessinée pour un écran de 1600 x 1000 points, réduite sur un écran plus petit, agrandie sur un plus grand ;
-- fond calé sur le cadre du panneau.
-- Défilement animé : la position suit la cible avec un amorti exponentiel (onFrameTick).
-- Ouverture : noctalia msg panel-toggle nc/carousel:main

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

local THUMBS = noctalia.expandPath("~/.cache/nc/carousel/")
local EXTS = { jpg = true, jpeg = true, png = true, webp = true, bmp = true, gif = true, jxl = true, avif = true, tif = true, tiff = true }
local BASE = { CW = 600, CH = 450, NW = 192, NH = 420, BGW = 1560, BGH = 940 }
local CW, CH = BASE.CW, BASE.CH   -- tranche du milieu
local NW, NH = BASE.NW, BASE.NH   -- tranche étroite (voisine immédiate)
local SK = 0.30              -- inclinaison
local SPACE = 4              -- écart entre tranches
local REACH = 3              -- tranches de chaque côté (au moins ; plus sur un écran large : portee)
local ROW_H = CH + 30
local SCREEN_W = 1600
local SMOOTH_MS = 55         -- plus petit = plus rapide
local REPEAT_DELAY = 280     -- flèche maintenue : délai puis cadence
local REPEAT_EVERY = 115
local FADE_MS = 260
-- Présent en mode Économie : pas d'animation. Le dossier de Noctalia, comme lui et comme nc-profile-sync qui l'écrit :
-- NOCTALIA_CONFIG_HOME, puis XDG_CONFIG_HOME, puis ~/.config
local ECO = (env("NOCTALIA_CONFIG_HOME") or env("XDG_CONFIG_HOME") or noctalia.expandPath("~/.config"))
  .. "/noctalia/zz-economie.toml"
local eco = false

local all = {}        -- { path, file, title, thumbW, thumbN }
local shown = {}      -- liste filtrée par la recherche
local target = 1      -- index cible, non replié (peut dépasser n : carrousel infini)
local pos = 1         -- position affichée (réelle), tend vers target
local query = ""
local current = nil
local bg = nil
local BGW, BGH = BASE.BGW, BASE.BGH
-- Cadre que Noctalia dessine autour du carrousel (mesuré) : sous la barre (épaisseur 36 + marge 6), à 8 points des
-- bords de l'écran, coins arrondis de 10 ; le contenu du panneau commence 65 points sous le haut de l'écran.
-- Le fond flou le remplit exactement.
local HAUT_BARRE, BORD, HAUT_PANNEAU, RAYON = 42, 8, 65, 10
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

-- Tailles pour l'écran courant (même calcul que nc-carousel-thumbs)
local function setZoom()
  local o = currentOutput()
  local z = o and math.max(0.6, math.min(1, o.width / 1600, o.height / 1000)) or 1
  -- Écran plus grand que 1600 x 1000 points (1920 x 1080…) : le carrousel grandit avec lui (jusqu'à x2) et son fond
  -- couvre tout l'écran ; jusqu'à 1600 x 1000, rien ne change
  local grand = o and (o.width > 1600 or o.height > 1000)
  if grand then z = math.max(1, math.min(2, o.width / 1600, o.height / 1000)) end
  local function px(v) return math.floor(v * z + 0.5) end
  CW, CH, NW, NH = px(BASE.CW), px(BASE.CH), px(BASE.NW), px(BASE.NH)
  -- Fond : exactement le cadre du panneau
  if o then BGW, BGH = o.width - 2 * BORD, o.height - HAUT_BARRE - 2 * BORD else BGW, BGH = px(BASE.BGW), px(BASE.BGH) end
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

-- Bande de tranches comme avant (version du 12/10) : toutes les tranches voisines sont dessinées et filent jusqu'aux
-- bords de l'écran ; les plus éloignées à moitié transparentes.
-- Nombre de tranches de chaque côté pour que la bande atteigne les bords du cadre (écran large : plus de tranches),
-- jamais moins de REACH (écran de 1600 points : 3, comme avant)
local function portee()
  local r, x = 0, CW / 2
  while x < BGW / 2 and r < 12 do
    r = r + 1
    x = x + dims(r) + SPACE
  end
  return math.max(REACH, r)
end

local function strip()
  local n = #shown
  local reach = math.min(portee(), math.max(1, math.floor(n / 2)))
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
      ui.label({ text = #all == 0 and tr("Aucune image dans le dossier des fonds d'écran", "No images in the wallpaper folder")
        or tr("Aucun fond d'écran trouvé", "No wallpaper found"), fontSize = 22, fontWeight = "bold", color = "on_surface" }),
    })
  else
    middle = strip()
  end

  local ease = 1 - (1 - appear) * (1 - appear)
  -- Remonté pour que le fond commence en haut du cadre (le contenu du panneau commence plus bas)
  panel.render(ui.column({ flexGrow = 1, align = "center", justify = "start", gap = (HAUT_BARRE + BORD) - HAUT_PANNEAU - 1, opacity = ease }, {
    ui.box({ width = 1, height = 1, opacity = 0 }),
    ui.column({ minWidth = BGW, align = "center", justify = "start", gap = -(BGH + ROW_H) / 2 }, {   -- minWidth : sinon rétréci aux marges du panneau
      bg and ui.image({ path = bg, width = BGW, height = BGH, fit = "cover", radius = RAYON }) or ui.box({ width = BGW, height = BGH, opacity = 0 }),
      ui.column({ height = ROW_H, width = BGW, align = "center", justify = "center" }, { middle }),
    }),
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
  elseif chord == "Escape" then
    panel.close()
  elseif chord == "Return" or chord == "KP_Enter" then
    if #shown > 0 then apply(shown[wrap(target)]) end
  end
end

function onOpen(context)
  EN = langue() == "en"
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

-- Legion Launcher (Noctalia v5) : barre de recherche compacte au centre de l'écran.
-- Rien sous la barre tant qu'on n'a pas tapé, sauf les applications courantes (souvent ET récemment utilisées).
-- Une rangée de grosses icônes : ← → (ou Tab) pour choisir, Entrée lance, Échap ferme. Lancement : legion-apps (uwsm-app + GPU du profil).
-- Ouverture : noctalia msg panel-toggle legion/launcher:main

local APPS_CMD = { noctalia.expandPath("~/.local/bin/legion-apps") }
local PINNED = { "@BROWSER@", "kitty", "org.kde.dolphin" }
local MAX_TILES = 6
local MAX_FAV = 6
local CARD_W = 700
local HEAD_H = 60
local TILE_H = 116
local CALC_H = 56
local FADE_MS = 150
local ECO = noctalia.expandPath("~/.config/noctalia/zz-economie.toml")   -- présent en mode Économie : pas d'animation

local apps = {}
local byId = {}
local results = {}      -- éléments affichés : { key, name, icon | glyph, hint, run }
local appResults = {}
local calcValue = nil
local files = {}
local favorites = {}
local selected = 0      -- 0 = rien de choisi (barre vide)
local query = ""
local inputKey = 0
local iconCache = {}
local usage = {}
local usagePath = nil
local appear = 1
local ticking = false

-- ── Historique d'utilisation (persistant) ───────────────────────────────────
local function loadUsage()
  local dir = noctalia.pluginDataDir()
  if not dir then return end
  usagePath = dir .. "/usage.json"
  local raw = noctalia.readFile(usagePath)
  local data = raw and noctalia.json.decode(raw)
  if type(data) == "table" then usage = data end
end

local function saveUsage()
  if not usagePath then return end
  local raw = noctalia.json.encode(usage)
  if raw then noctalia.writeFile(usagePath, raw) end
end

-- Score = (1 + lancements) × poids selon l'ancienneté du dernier lancement (comme la v4)
local function recencyWeight(ts)
  if not ts then return 0.8 end
  local h = (os.time() - ts) / 3600
  if h < 4 then return 4 elseif h < 24 then return 2.5 elseif h < 168 then return 1.5 end
  return 1
end

local function computeFavorites()
  local list = {}
  for id, u in pairs(usage) do
    if byId[id] then
      table.insert(list, { app = byId[id], score = (1 + (u.n or 0)) * recencyWeight(u.t) })
    end
  end
  table.sort(list, function(a, b) return a.score > b.score end)
  local out, seen = {}, {}
  for _, it in ipairs(list) do
    if #out >= MAX_FAV then break end
    table.insert(out, it.app); seen[it.app.id] = true
  end
  for _, id in ipairs(PINNED) do
    if #out >= MAX_FAV then break end
    if byId[id] and not seen[id] then table.insert(out, byId[id]); seen[id] = true end
  end
  favorites = out
end

local function iconFor(app)
  local c = iconCache[app.id]
  if c == nil then
    c = noctalia.appIconPath(app.id, 64) or (app.icon ~= "" and noctalia.appIconPath(app.icon, 64))
      or noctalia.appIconPath("application-x-executable", 64) or false
    iconCache[app.id] = c
  end
  return c or nil
end

-- ── Recherche ───────────────────────────────────────────────────────────────
local WEIGHTS = { name = 1, exe = 0.9, generic = 0.7, keywords = 0.6 }

local launch, openFile, copyCalc

-- Calcul : « 12*8 », « (3+4)/2 », « 2^10 »… ou n'importe quoi après « = » (« =sqrt(2) », « =20 % de 80 »)
local function mathExpr(q)
  if q:sub(1, 1) == "=" then
    local e = noctalia.string.trim(q:sub(2))
    return e ~= "" and e or nil
  end
  if q:find("%d") and q:find("[%+%-%*/%^%%×÷]") and not q:find("[^%d%s%.,%+%-%*/%^%%%(%)×÷]") then
    return q
  end
  return nil
end

local function buildItems()
  results = {}
  if calcValue then
    table.insert(results, { key = "calc", name = calcValue, glyph = "calculator", hint = "copier", run = function() copyCalc(calcValue) end })
  end
  local nFiles = math.min(#files, 2)
  local nApps = math.min(#appResults, MAX_TILES - nFiles - (calcValue and 1 or 0))
  for i = 1, nApps do
    local app = appResults[i]
    table.insert(results, { key = "app-" .. app.id, app = app, name = app.name, run = function() launch(app) end })
  end
  for i = 1, nFiles do
    local f = files[i]
    table.insert(results, { key = "file-" .. f.path, name = f.name, glyph = f.dir and "folder" or "file", hint = f.parent,
      run = function() openFile(f.path) end })
  end
  if selected > #results then selected = math.max(1, #results) end
end

local function searchApps(q)
  appResults = {}
  local ranked = {}
  local ql = q:lower()
  for _, app in ipairs(apps) do
    local best = nil
    if #ql <= 2 then
      local nl = app.name:lower()
      if nl:sub(1, #ql) == ql then best = 3 elseif nl:find(" " .. ql, 1, true) then best = 2 end
    end
    for field, w in pairs(#ql <= 2 and {} or WEIGHTS) do
      local text = app[field]
      if text and text ~= "" then
        local s = noctalia.fuzzyScore(q, text)
        if s then
          s = s * w
          if not best or s > best then best = s end
        end
      end
    end
    if best then
      local u = usage[app.id]
      local bonus = u and math.min(0.25, 0.06 * math.log(1 + (u.n or 0))) or 0
      table.insert(ranked, { app = app, rank = best * (1 + bonus) })
    end
  end
  table.sort(ranked, function(a, b) return a.rank > b.rank end)
  -- Seuil : on écarte les correspondances vagues (score de 0,8 à ~4 ; nom presque exact ≈ 3,9)
  local cut = ranked[1] and math.max(1.5, 0.5 * ranked[1].rank) or 0
  for _, r in ipairs(ranked) do
    if #appResults >= MAX_TILES or r.rank < cut then break end
    table.insert(appResults, r.app)
  end
end

local function search()
  local q = noctalia.string.trim(query)
  selected = (q == "") and 0 or 1
  calcValue = nil
  files = {}
  appResults = {}
  if q == "" then results = {} return end
  local expr = mathExpr(q)
  if not expr then searchApps(q) end
  buildItems()
  -- Calcul et fichiers arrivent en différé ; une réponse pour un ancien texte est ignorée
  if expr then
    noctalia.runAsync({ "qalc", "-t", expr }, function(r)
      if noctalia.string.trim(query) ~= q then return end
      local v = noctalia.string.trim(r.stdout or "")
      if r.exitCode == 0 and v ~= "" and v ~= expr and not v:find("error", 1, true) then
        calcValue = v
        buildItems()
        render()
      end
    end, 3000)
  elseif #q >= 3 then
    noctalia.runAsync({ APPS_CMD[1], "files", q }, function(r)
      if noctalia.string.trim(query) ~= q then return end
      local list = r.exitCode == 0 and noctalia.json.decode(r.stdout)
      if type(list) == "table" and #list > 0 then
        files = list
        buildItems()
        render()
      end
    end, 3000)
  end
end

-- ── Lancement ───────────────────────────────────────────────────────────────
function launch(app)
  if not app then return end
  local u = usage[app.id] or { n = 0 }
  u.n = (u.n or 0) + 1
  u.t = os.time()
  usage[app.id] = u
  saveUsage()
  noctalia.runAsync({ APPS_CMD[1], "launch", app.id })
  panel.close()
end

function openFile(path)
  noctalia.runAsync({ APPS_CMD[1], "open", path })
  panel.close()
end

function copyCalc(v)
  noctalia.copyToClipboard(v, "text/plain;charset=utf-8")
  panel.close()
end

local function activate(item)
  if item then item.run() end
end

-- ── Affichage ───────────────────────────────────────────────────────────────
-- Éléments affichés : applis courantes quand la barre est vide, sinon les résultats
local function currentItems()
  if noctalia.string.trim(query) ~= "" then return results end
  local out = {}
  for _, app in ipairs(favorites) do
    table.insert(out, { key = "fav-" .. app.id, app = app, name = app.name, run = function() launch(app) end })
  end
  return out
end

local function tile(item, i, w)
  local sel = i == selected
  local top
  if item.app then
    top = ui.image({ path = iconFor(item.app), width = 52, height = 52, fit = "contain" })
  else
    top = ui.row({ width = 52, height = 52, align = "center", justify = "center" }, {
      ui.glyph({ name = item.glyph, size = 38, color = sel and "primary" or "on_surface_variant" }) })
  end
  local kids = {
    top,
    ui.label({ text = item.name, fontSize = 12, fontWeight = sel and "semibold" or "medium", maxWidth = w - 12, maxLines = 2,
      textAlign = "center", color = sel and "on_surface" or "on_surface_variant" }),
  }
  if item.hint then
    table.insert(kids, ui.label({ text = item.hint, fontSize = 10, maxWidth = w - 12, maxLines = 1, textAlign = "center",
      color = "on_surface_variant", opacity = 0.65 }))
  end
  return ui.column({
    key = "t-" .. item.key,
    width = w - 6,
    height = TILE_H - 12,
    align = "center",
    justify = "center",
    gap = 8,
    radius = 18,
    fill = sel and "primary/0.18" or "primary/0",
    onClick = function() activate(item) end,
    onHover = function(state) if state == "true" and selected ~= i then selected = i; render() end end,
  }, kids)
end

-- Corps sous la barre : résultat de calcul en bandeau (s'il y en a), puis la rangée de tuiles
local function body(items)
  local q = noctalia.string.trim(query)
  if #items == 0 then
    if q == "" then return nil, 0 end
    return ui.column({ height = 56, align = "center", justify = "start" }, {
      ui.label({ text = "Aucun résultat", fontSize = 13, color = "on_surface_variant" }) }), 56
  end
  local kids, h, first = {}, 0, 1
  if items[1].key == "calc" then
    local sel = selected == 1
    table.insert(kids, ui.row({
      key = "calc", height = CALC_H, paddingH = 20, gap = 14, align = "center", radius = 16,
      fill = sel and "primary/0.18" or "primary/0",
      onClick = function() activate(items[1]) end,
      onHover = function(state) if state == "true" and selected ~= 1 then selected = 1; render() end end,
    }, {
      ui.glyph({ name = "calculator", size = 26, color = "primary" }),
      ui.label({ text = items[1].name, flexGrow = 1, fontSize = 22, fontWeight = "semibold", color = "on_surface", maxLines = 1, maxWidth = CARD_W - 200 }),
      ui.label({ text = "copier", fontSize = 12, color = "on_surface_variant", opacity = 0.7 }),
    }))
    h = h + CALC_H + 4
    first = 2
  end
  if #items >= first then
    local n = #items - first + 1
    local w = math.floor((CARD_W - 40) / MAX_TILES)
    local row = {}
    for i = first, #items do table.insert(row, tile(items[i], i, w)) end
    table.insert(kids, ui.row({ justify = "center", align = "start", gap = 0, height = TILE_H }, row))
    h = h + TILE_H
  end
  return ui.column({ paddingH = 20, paddingBottom = 4, align = "stretch", height = h + 4 }, kids), h + 4
end

function render()
  local items = currentItems()
  local content = body(items)
  -- Le panneau a la taille de la carte : le cadre, le flou et l'ombre sont ceux de Noctalia, rien d'autre sur l'écran.
  local ease = 1 - (1 - appear) * (1 - appear)
  panel.render(ui.column({ flexGrow = 1, align = "stretch", opacity = ease }, {
    ui.row({ height = HEAD_H, paddingH = 24, gap = 14, align = "center" }, {
      ui.glyph({ name = "search", size = 20, color = "primary" }),
      ui.input({
        key = "q" .. inputKey,
        value = query,
        placeholder = "Rechercher",
        fontSize = 20,
        frameVisible = false,
        focus = true,
        flexGrow = 1,
        onChange = function(v) query = v; search(); render() end,
        onSubmit = function() activate(currentItems()[selected]) end,
      }),
    }),
    content,
  }))
end

function onFrameTick(deltaMs)
  appear = math.min(1, appear + math.min(tonumber(deltaMs) or 16, 64) / FADE_MS)
  render()
  if appear >= 1 and ticking then ticking = false; panel.setNeedsFrameTick(false) end
end

-- ── Clavier ─────────────────────────────────────────────────────────────────
function onKey(chord, pressed)
  if not pressed then return end
  local nextKey = chord == "Right" or chord == "Down" or chord == "Tab" or chord == "ctrl+j" or chord == "ctrl+n"
  local prevKey = chord == "Left" or chord == "Up" or chord == "shift+Tab" or chord == "ISO_Left_Tab" or chord == "ctrl+k" or chord == "ctrl+p"
  local enter = chord == "Return" or chord == "KP_Enter"
  local items = currentItems()
  if enter then activate(items[selected]) return end
  local n = #items
  if n == 0 then return end
  if nextKey then selected = selected % n + 1
  elseif prevKey then selected = selected <= 1 and n or selected - 1
  else return end
  render()
end

-- ── Cycle de vie ────────────────────────────────────────────────────────────
local function loadApps(after)
  noctalia.runAsync(APPS_CMD[1] .. " list", function(r)
    local list = r.exitCode == 0 and noctalia.json.decode(r.stdout)
    if type(list) == "table" then
      apps = list
      byId = {}
      for _, a in ipairs(apps) do byId[a.id] = a end
      computeFavorites()
      local q = noctalia.string.trim(query)
      if q ~= "" and not mathExpr(q) then searchApps(q); buildItems() end
    end
    if after then after() end
  end, 5000)
end

function onOpen(context)
  query = context or ""   -- texte de départ facultatif : panel-toggle legion/launcher:main "fir"
  results = {}
  selected = 0
  inputKey = inputKey + 1
  computeFavorites()
  search()
  appear = 0
  ticking = true
  if noctalia.fileExists(ECO) then appear = 1; ticking = false end
  panel.setNeedsFrameTick(ticking)
  render()
  loadApps(render)   -- rafraîchit la liste (nouvelles applis) sans retarder l'ouverture
end

function onClose()
  if ticking then ticking = false; panel.setNeedsFrameTick(false) end
end

loadUsage()
loadApps()

-- Touches simulées (tests, raccourcis) : noctalia msg plugin <id>:main all key Right
function onIpc(event, payload)
  if event == "key" and payload then onKey(payload, true) end
end

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
-- La fiche tient toujours dans l'écran : si ses colonnes (descriptions sur deux lignes comprises) sont plus hautes que la
-- place sous la barre, tout est réduit d'autant (render) ; jamais sous 0,55
local Z = 1
local ECRAN_H = 1000
local ECRAN_W = 1600
local LARGE = false     -- quatre colonnes plus étroites (écran assez large) plutôt que trois réduites
local function px(v) return math.floor(v * Z + 0.5) end
local function setZoom()
  local name, out = noctalia.focusedOutputName(), nil
  for _, o in ipairs(noctalia.outputs()) do
    if o.name == name or (not out and o.focused) then out = o end
  end
  out = out or noctalia.outputs()[1]
  Z = out and math.max(0.6, math.min(1, out.width / 1600, out.height / 1000)) or 1
  ECRAN_H = out and out.height or 1000
  ECRAN_W = out and out.width or 1600
  LARGE = false
end
local COL_W, KEY_W, ROW_H, TITLE_H, SEC_GAP = 490, 220, 30, 34, 22
local function tailles()
  COL_W, KEY_W, ROW_H, TITLE_H, SEC_GAP = px(490), px(220), px(30), px(34), px(22)
  -- Quatre colonnes : toute la largeur de l'écran (marges et écarts déduits)
  -- (et une colonne de touches plus étroite : une combinaison plus longue met sa description en dessous)
  if LARGE then COL_W, KEY_W = math.min(px(490), math.floor((ECRAN_W - 2 * px(32) - 3 * px(20)) / 4)), px(150) end
end
-- Présent en mode Économie : pas d'animation. Le dossier de Noctalia, comme lui et comme nc-profile-sync qui l'écrit :
-- NOCTALIA_CONFIG_HOME, puis XDG_CONFIG_HOME, puis ~/.config
local ECO = (env("NOCTALIA_CONFIG_HOME") or env("XDG_CONFIG_HOME") or noctalia.expandPath("~/.config"))
  .. "/noctalia/zz-economie.toml"
-- Sections par colonne (titres produits par nc-keys)
local COLUMNS = {
  { "Applis et barre", "Bureaux" },
  { "Fenêtres", "Souris" },
  { "Système", "IA", "Mes raccourcis" },
}
-- Trop haute en trois colonnes sur un écran large (1400 points ou plus) : quatre colonnes équilibrées, à taille normale,
-- au lieu de tout réduire (texte à 9 px, colonnes étroites qui font passer les descriptions sur deux lignes : issue #1)
local COLUMNS_4 = {
  { "Applis et barre", "Bureaux" },
  { "Fenêtres" },
  { "Système", "Mes raccourcis" },
  { "IA", "Souris" },
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
-- Pourquoi rien n'est lu (nc-keys absent, en échec, sortie vide ou illisible) : affiché à la place de la fiche, jamais une
-- fiche vide ; nil tant que la lecture n'a pas échoué
local erreur = nil
local appear = 1
local ticking = false

local function chip(text)
  return ui.row({ height = px(24), paddingH = px(LARGE and 6 or 8), radius = px(7), align = "center", fill = "on_surface/0.08", border = "outline/0.3", borderWidth = 1 }, {
    ui.label({ text = text, fontSize = math.max(9, px(LARGE and 11 or 12)), fontWeight = "semibold", color = "on_surface" }),
  })
end

local function plus()
  return ui.label({ text = "+", fontSize = math.max(9, px(11)), color = "on_surface_variant" })
end

-- Largeur des touches d'un raccourci (pastilles et « + ») : la colonne des touches est celle de la plus longue de sa
-- colonne, pas une largeur fixe (« Super + Q » laisse plus de place à sa description)
local function largeur_touches(r)
  local fs, l = math.max(9, px(LARGE and 11 or 12)), 0
  for i, k in ipairs(r.keys or {}) do
    if i > 1 then l = l + fs * 0.6 + 2 * px(5) end
    l = l + (utf8.len(k) or #k) * fs * 0.62 + 2 * px(LARGE and 6 or 8)
  end
  return math.ceil(l)
end

-- Une description trop longue pour sa colonne passe sur deux lignes (la ligne grandit) au lieu d'être coupée
local function hauteur(r, kw)
  if largeur_touches(r) > (kw or KEY_W) then return ROW_H + px(18) end      -- touches, puis la description dessous
  local place = COL_W - (kw or KEY_W) - px(14)
  local n = utf8.len(r.text or "") or #(r.text or "")
  return n * math.max(10, px(13)) * 0.56 > place and ROW_H + px(18) or ROW_H
end

local function row(r, kw)
  local keys = {}
  for i, k in ipairs(r.keys) do
    if i > 1 then table.insert(keys, plus()) end
    table.insert(keys, chip(k))
  end
  if largeur_touches(r) > kw then
    return ui.column({ height = hauteur(r, kw), gap = px(2), justify = "center" }, {
      ui.row({ gap = px(5), align = "center" }, keys),
      ui.label({ text = r.text, fontSize = math.max(10, px(13)), color = "on_surface_variant", maxLines = 1, maxWidth = COL_W }),
    })
  end
  return ui.row({ height = hauteur(r, kw), gap = px(14), align = "center" }, {
    ui.row({ width = kw, gap = px(5), align = "center" }, keys),
    ui.label({ text = r.text, fontSize = math.max(10, px(13)), color = "on_surface_variant", maxLines = 2, maxWidth = COL_W - kw - px(14) }),
  })
end

local function column(titles)
  local kids, h, kw = {}, 0, px(60)
  for _, t in ipairs(titles) do
    for _, r in ipairs(sections[t] or {}) do kw = math.max(kw, largeur_touches(r)) end
  end
  kw = math.min(kw, KEY_W)
  for _, t in ipairs(titles) do
    local sec = sections[t]
    if sec and #sec > 0 then
      if h > 0 then table.insert(kids, ui.box({ height = SEC_GAP, width = 1, opacity = 0 })); h = h + SEC_GAP end
      table.insert(kids, ui.label({ text = libelles[t] or tr(t, TITRES_EN[t] or t), fontSize = math.max(11, px(14)), fontWeight = "bold", color = "primary", height = TITLE_H }))
      h = h + TITLE_H
      for _, r in ipairs(sec) do table.insert(kids, row(r, kw)); h = h + hauteur(r, kw) end
    end
  end
  return ui.column({ width = COL_W, height = h, align = "stretch", gap = 0 }, kids), h
end

local function colonnes()
  local cols, maxH = {}, 0
  for _, titles in ipairs(LARGE and COLUMNS_4 or COLUMNS) do
    local c, h = column(titles)
    table.insert(cols, c)
    if h > maxH then maxH = h end
  end
  return cols, maxH
end

function render()
  local cols, maxH = colonnes()
  -- Place sous la barre (et les marges du panneau) : trop haute, la fiche est réduite pour y tenir
  local dispo = ECRAN_H - 120
  if maxH > dispo and not LARGE and ECRAN_W >= 1400 then
    LARGE = true
    tailles()
    cols, maxH = colonnes()
  end
  if maxH > dispo and Z > 0.55 then
    Z = math.max(0.55, Z * dispo / maxH)
    tailles()
    cols, maxH = colonnes()
  end
  local ease = 1 - (1 - appear) * (1 - appear)
  local body
  if maxH == 0 then
    body = ui.label({ text = erreur or tr("Lecture des raccourcis…", "Reading shortcuts…"), fontSize = 14, color = "on_surface_variant",
                      maxWidth = px(720), maxLines = 4 })
    maxH = 40
  else
    body = ui.row({ gap = px(LARGE and 20 or 24), align = "start", height = maxH }, cols)
    -- Même réduite au plus petit, encore trop haute (petit écran, beaucoup de raccourcis) : elle défile à la molette
    if maxH > dispo then body = ui.scroll({ height = dispo, gap = 0 }, { body }) end
  end
  -- « Modifier » : la section Raccourcis de la fenêtre des réglages (île) ; sans l'île, nc-reglages ouvre de lui-même
  -- l'écran des raccourcis dans un terminal
  local modifier = ui.row({ key = "modifier", height = px(28), paddingH = px(14), radius = px(14), align = "center",
                            fill = "on_surface/0.08", onClick = function()
                              noctalia.runAsync({ "sh", "-c", "~/.local/bin/nc-reglages fenetre Raccourcis" })
                              panel.close()
                            end }, {
    ui.label({ text = tr("Modifier", "Edit"), fontSize = math.max(10, px(13)), fontWeight = "semibold", color = "on_surface" }),
  })
  panel.render(ui.column({ flexGrow = 1, align = "center", justify = "center", paddingH = px(32), paddingV = px(28), opacity = ease, gap = px(10) },
    { ui.row({ justify = "end", align = "center" }, { modifier }), body }))
end

function onFrameTick(deltaMs)
  appear = math.min(1, appear + math.min(tonumber(deltaMs) or 16, 64) / FADE_MS)
  render()
  if appear >= 1 and ticking then ticking = false; panel.setNeedsFrameTick(false) end
end

local function premiere_ligne(t)
  if type(t) ~= "string" then return "" end
  local l = t:match("[^\n]*%S[^\n]*") or ""
  l = l:gsub("^%s+", ""):gsub("%s+$", "")
  if #l > 200 then l = l:sub(1, 200) .. "…" end
  return l
end

local function load()
  if not noctalia.fileExists(KEYS_CMD) then
    sections, erreur = {}, tr("Aucun raccourci lu : nc-keys est absent de ~/.local/bin (relance install.sh).",
                              "No shortcuts read: nc-keys is missing from ~/.local/bin (run install.sh again).")
    render()
    return
  end
  noctalia.runAsync({ KEYS_CMD, "json" }, function(r)
    local data = r and r.exitCode == 0 and noctalia.json.decode(r.stdout)
    local n = 0
    if type(data) == "table" then
      sections, libelles = {}, {}
      for _, s in ipairs(data) do
        local titre = tostring(s.title or "")
        titre = TITRES_FR[string.lower(titre)] or titre
        if type(s.rows) == "table" and #s.rows > 0 then
          sections[titre] = s.rows
          n = n + #s.rows
        end
        if type(s.label) == "string" and s.label ~= "" then libelles[titre] = s.label end
      end
    end
    if n > 0 then
      erreur = nil
    else
      -- nc-keys écrit sa raison sur une ligne (« nc-keys : … ») ; sinon une raison générale, jamais une fiche vide
      sections = {}
      local e = premiere_ligne(r and r.stderr)
      erreur = e ~= "" and (tr("Aucun raccourci lu : ", "No shortcuts read: ") .. e:gsub("^nc%-keys ?: ?", ""))
               or tr("Aucun raccourci lu : nc-keys n'a rien renvoyé de lisible (essaie « nc-keys » dans un terminal).",
                     "No shortcuts read: nc-keys returned nothing readable (try \"nc-keys\" in a terminal).")
    end
    render()
  end, 5000)
end

function onOpen()
  EN = langue() == "en"
  setZoom()
  tailles()
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

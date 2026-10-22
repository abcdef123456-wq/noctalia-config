-- nc/sessions (Noctalia v5) : les sessions enregistrées (nc-session) dans un carrousel, sur le modèle de nc/carousel.
-- Une carte par session (sa capture, sinon le dessin de ses fenêtres, une rangée par bureau), puis « + Nouvelle session ».
-- Gauche/Droite ou molette (maintenir une flèche pour défiler), clic sur une voisine pour la centrer.
-- Entrée ou clic sur la carte du milieu : ouvrir la session (ou nommer la nouvelle) ; Maj + Suppr : la supprimer, après
-- confirmation sur la carte ; E ou clic droit : la modifier ; Échap : fermer.
-- Données : seulement nc-session (json, ouvrir, enregistrer, supprimer…), jamais ses fichiers.
-- Même cadre et mêmes tailles que le carrousel des fonds : dessiné pour un écran de 1600 x 1000 points, réduit sur un
-- plus petit, agrandi sur un plus grand ; fond flou du fond d'écran courant (miniature de nc-carousel-thumbs).
-- Ouverture : nc-shell-msg sessions (Super + Maj + W), ou noctalia msg panel-toggle nc/sessions:main [NOM]

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

local NC = noctalia.expandPath("~/.local/bin/nc-session")
local THUMBS = noctalia.expandPath("~/.cache/nc/carousel/")   -- fond flou du fond courant (<fond>.B.webp)
-- Tailles du carrousel des fonds (nc/carousel/panel.luau) : mêmes cartes, mêmes voisines
local BASE = { CW = 600, CH = 450, NW = 192, NH = 420, BGW = 1560, BGH = 940, INFO = 150 }
local CW, CH = BASE.CW, BASE.CH   -- carte du milieu
local NW, NH = BASE.NW, BASE.NH   -- carte étroite (voisine immédiate)
local INFO_H = BASE.INFO          -- sous la bande : nom, applis, date, aide de la carte du milieu
local Z = 1
local SPACE = 4
local REACH = 3
local ROW_H = CH + 30
local SMOOTH_MS = 55
local REPEAT_DELAY = 280
local REPEAT_EVERY = 115
local FADE_MS = 260
local ECO = noctalia.expandPath("~/.config/noctalia/zz-economie.toml")   -- présent en mode Économie : pas d'animation
local eco = false
-- Cadre du carrousel des fonds (mesuré) : sous la barre (36 + 6), à 8 points des bords, coins arrondis de 10
local HAUT_BARRE, BORD, HAUT_PANNEAU, RAYON = 42, 8, 65, 10
local BGW, BGH = BASE.BGW, BASE.BGH
local MAX_APPLIS = 8
local MAX_BUREAUX = 4

local sessions = {}   -- sessions de nc-session json
local cartes = {}     -- sessions, puis { nouvelle = true }
local charge = false  -- liste lue au moins une fois
local target, pos = 1, 1
local holdDir, holdT = 0, 0
local appear = 1
local ticking = false
local bg = nil
local mode = "liste"  -- liste | nom (nouvelle session) | confirmer (suppression) | attente
local nomSaisi = ""
local inputKey = 0
local message = nil   -- texte bref sous la carte (« Bientôt », erreur de nc-session…)
local messageErreur = false
local voulu = nil     -- nom de session à centrer à la prochaine lecture
local iconesApplis = {}

-- ── Outils ──────────────────────────────────────────────────────────────────
local function texte(v) return type(v) == "string" and v ~= "" and v or nil end

-- Couleur de la session : rôle du thème (primary, tertiary…) ou #rrggbb ; sinon l'accent
local function couleur(s)
  local c = texte(s and s.couleur)
  if c and (string.match(c, "^#%x%x%x%x%x%x$") or string.match(c, "^[%a_]+$")) then return c end
  return "primary"
end

-- Icône : nom Material Symbols (celui de l'île) → glyphe Tabler de Noctalia
local MATERIAL = {
  work = "briefcase", work_outline = "briefcase", business_center = "briefcase", code = "code", terminal = "terminal",
  sports_esports = "device-gamepad-2", videogame_asset = "device-gamepad", games = "device-gamepad",
  music_note = "music", library_music = "music", headphones = "headphones", movie = "movie", live_tv = "device-tv",
  tv = "device-tv", school = "school", home = "home", mail = "mail", edit = "edit", brush = "brush", palette = "palette",
  photo = "photo", image = "photo", photo_camera = "camera", camera_alt = "camera", videocam = "video", chat = "message",
  forum = "messages", public = "world", language = "world", travel_explore = "world-search", book = "book",
  menu_book = "book", auto_stories = "book", science = "flask", bug_report = "bug", cloud = "cloud", star = "star",
  favorite = "heart", bolt = "bolt", rocket_launch = "rocket", desktop_windows = "device-desktop",
  computer = "device-desktop", laptop = "device-laptop", view_quilt = "layout-dashboard", dashboard = "layout-dashboard",
  apps = "apps", folder = "folder", settings = "settings", build = "tool", construction = "tools",
  calendar_month = "calendar", event = "calendar", coffee = "coffee", local_cafe = "coffee",
  fitness_center = "barbell", shopping_cart = "shopping-cart", payments = "cash", attach_money = "cash",
  person = "user", group = "users", design_services = "ruler", analytics = "chart-bar", bar_chart = "chart-bar",
  auto_awesome = "sparkles", bedtime = "moon", nightlight = "moon", wb_sunny = "sun", mic = "microphone",
  description = "file-text", article = "file-text", play_arrow = "player-play", keyboard = "keyboard",
}
local ICONE_DEFAUT = "layout-dashboard"
local tabler = nil   -- noms des glyphes de Noctalia (lus une fois, seulement pour un nom hors de la table)
local function glyphe(nom)
  nom = texte(nom)
  if not nom then return ICONE_DEFAUT end
  if MATERIAL[nom] then return MATERIAL[nom] end
  local t = string.gsub(nom, "_", "-")
  if tabler == nil then
    tabler = false
    for _, p in ipairs({ "/usr/share/noctalia/assets/fonts/tabler.json", "/usr/local/share/noctalia/assets/fonts/tabler.json" }) do
      local brut = noctalia.readFile(p)
      if brut and brut ~= "" then tabler = brut; break end
    end
  end
  if tabler and not string.find(tabler, '"' .. t .. '"', 1, true) then return ICONE_DEFAUT end
  return t
end

local function iconeAppli(classe, taille)
  local k = (classe or "") .. ":" .. taille
  if iconesApplis[k] == nil then
    iconesApplis[k] = (texte(classe) and noctalia.appIconPath(classe, taille * 2)) or false
  end
  return iconesApplis[k] or nil
end

-- « il y a 3 jours » (date ISO, heure locale)
local function depuis(iso)
  iso = texte(iso)
  if not iso then return nil end
  local a, mo, j, h, mi, se = string.match(iso, "^(%d+)-(%d+)-(%d+)[T ](%d+):(%d+):?(%d*)")
  if not a then return nil end
  local t = os.time({ year = tonumber(a), month = tonumber(mo), day = tonumber(j), hour = tonumber(h), min = tonumber(mi),
    sec = tonumber(se) or 0 })
  local d = math.max(0, os.time() - t)
  local function n(v) return math.floor(v) end
  if d < 60 then return tr("à l'instant", "just now") end
  if d < 3600 then return tr("il y a " .. n(d / 60) .. " min", n(d / 60) .. " min ago") end
  if d < 86400 then return tr("il y a " .. n(d / 3600) .. " h", n(d / 3600) .. " h ago") end
  local jours = n(d / 86400)
  if jours == 1 then return tr("hier", "yesterday") end
  if jours < 30 then return tr("il y a " .. jours .. " jours", jours .. " days ago") end
  if jours < 365 then
    local m = n(jours / 30)
    return tr("il y a " .. m .. " mois", m .. (m == 1 and " month ago" or " months ago"))
  end
  local an = n(jours / 365)
  return tr("il y a " .. an .. (an == 1 and " an" or " ans"), an .. (an == 1 and " year ago" or " years ago"))
end

local function px(v) return math.floor(v * Z + 0.5) end

-- Écran de référence : celui qui a le focus, sinon le premier
local function currentOutput()
  local name, out = noctalia.focusedOutputName(), nil
  for _, o in ipairs(noctalia.outputs()) do
    if o.name == name or (not out and o.focused) then out = o end
  end
  return out or noctalia.outputs()[1]
end

-- Tailles pour l'écran courant (même calcul que nc/carousel)
local function setZoom()
  local o = currentOutput()
  local z = o and math.max(0.6, math.min(1, o.width / 1600, o.height / 1000)) or 1
  if o and (o.width > 1600 or o.height > 1000) then z = math.max(1, math.min(2, o.width / 1600, o.height / 1000)) end
  Z = z
  CW, CH, NW, NH, INFO_H = px(BASE.CW), px(BASE.CH), px(BASE.NW), px(BASE.NH), px(BASE.INFO)
  if o then BGW, BGH = o.width - 2 * BORD, o.height - HAUT_BARRE - 2 * BORD else BGW, BGH = px(BASE.BGW), px(BASE.BGH) end
  ROW_H = CH + px(30)
end

local function setTicking(on)
  if on ~= ticking then
    ticking = on
    panel.setNeedsFrameTick(on)
  end
end

local function courante() return cartes[target] end

-- Aller à la carte i (bornée) ; animé, sauf en Économie
local function aller(i)
  local n = #cartes
  if n == 0 then return end
  if i < 1 then i = n elseif i > n then i = 1 end
  if i ~= target then
    target = i
    if mode == "confirmer" then mode = "liste" end
    message = nil
    setTicking(true)
  end
end

-- ── nc-session ──────────────────────────────────────────────────────────────
local function construire()
  cartes = {}
  for _, s in ipairs(sessions) do table.insert(cartes, s) end
  table.insert(cartes, { nouvelle = true })
  local t = math.min(target, #cartes)
  if voulu then
    for i, c in ipairs(cartes) do if c.nom == voulu then t = i end end
    voulu = nil
  end
  target, pos = t, t
end

local function recharger(apres)
  noctalia.runAsync({ NC, "json" }, function(r)
    local d = r and r.exitCode == 0 and noctalia.json.decode(r.stdout or "")
    if type(d) == "table" and type(d.sessions) == "table" then
      sessions = {}
      for _, s in ipairs(d.sessions) do
        if type(s) == "table" and texte(s.nom) then table.insert(sessions, s) end
      end
    elseif not charge then
      message, messageErreur = tr("Impossible de lire les sessions (nc-session json)", "Couldn't read the sessions (nc-session json)"), true
    end
    charge = true
    construire()
    if apres then apres() end
    render()
  end, 5000)
end

-- Erreur de nc-session : sa propre phrase (stderr), sinon une phrase générale
local function erreur(r, fr, en)
  local e = r and texte(r.stderr) and noctalia.string.trim(r.stderr) or nil
  message, messageErreur = e or tr(fr, en), true
end

-- Ouvrir : le panneau se ferme d'abord (la session peut changer le fond, ce qui recharge les plugins : un panneau
-- rechargé en pleine fermeture restait figé, voir nc/carousel)
local function ouvrir(s)
  if not s or not s.nom then return end
  panel.close()
  noctalia.runAsync({ "sh", "-c", 'sleep 0.4; exec "$0" ouvrir "$1"', NC, s.nom })
end

local function supprimer(s)
  mode = "attente"
  render()
  noctalia.runAsync({ NC, "supprimer", s.nom }, function(r)
    mode = "liste"
    if r and r.exitCode == 0 then
      message = nil
      recharger()
    else
      erreur(r, "La session n'a pas pu être supprimée", "The session couldn't be deleted")
      render()
    end
  end, 10000)
end

local function existe(nom)
  for _, s in ipairs(sessions) do if s.nom == nom then return true end end
  return false
end

local function enregistrer()
  local nom = noctalia.string.trim(nomSaisi or "")
  if nom == "" then return end   -- le nom lui-même est vérifié par nc-session (son message s'affiche s'il le refuse)
  mode = "attente"
  message = tr("Enregistrement de « " .. nom .. " »…", "Saving “" .. nom .. "”…")
  messageErreur = false
  render()
  noctalia.runAsync({ NC, "enregistrer", nom }, function(r)
    if r and r.exitCode == 0 then
      mode, message, nomSaisi = "liste", nil, ""
      voulu = nom
      recharger()
    else
      mode = "nom"
      inputKey = inputKey + 1
      erreur(r, "La session n'a pas pu être enregistrée", "The session couldn't be saved")
      render()
    end
  end, 30000)
end

-- Éditeur d'une session : à venir (nc-session modifier NOM CLE VALEUR)
function editer(session)
  if not session or session.nouvelle then return end
  message, messageErreur = tr("Bientôt : modifier « " .. session.nom .. " » ici", "Coming soon: edit “" .. session.nom .. "” here"), false
  render()
end

local function activer(c)
  if not c then return end
  if c.nouvelle then
    mode, nomSaisi, message = "nom", "", nil
    inputKey = inputKey + 1
    render()
  else
    ouvrir(c)
  end
end

-- ── Dessin ──────────────────────────────────────────────────────────────────
local function lerp(a, b, t) return a + (b - a) * t end

-- Taille de la carte à la distance (continue) delta du centre : comme nc/carousel
local function dims(delta)
  local t = math.min(delta, 1)
  local sc = delta <= 1 and 1 or math.max(0.58, 0.88 ^ (delta - 1))
  return lerp(CW, NW * sc, t), lerp(CH, NH * sc, t)
end

local function portee()
  local r, x = 0, CW / 2
  while x < BGW / 2 and r < 12 do
    r = r + 1
    x = x + dims(r) + SPACE
  end
  return math.max(REACH, r)
end

local function vide(w, h) return ui.box({ width = math.max(1, w), height = math.max(1, h), opacity = 0 }) end

-- Un écran du schéma : ses fenêtres en rectangles (x, y, w, h entre 0 et 1), superposés par des marges négatives
local function ecranSchema(e, sw, sh, col)
  local couches = {}
  for _, r in ipairs(type(e.rects) == "table" and e.rects or {}) do
    local x, y = tonumber(r.x) or 0, tonumber(r.y) or 0
    local w, h = tonumber(r.w) or 0, tonumber(r.h) or 0
    local rw, rh = math.max(2, w * sw - 3), math.max(2, h * sh - 3)
    local ic = math.floor(math.min(rw, rh) * 0.5)
    local dedans = {}
    if ic >= 14 then
      local p = iconeAppli(r.classe, math.min(ic, 48))
      if p then table.insert(dedans, ui.image({ path = p, width = math.min(ic, 48), height = math.min(ic, 48), fit = "contain" })) end
    end
    local rect = ui.column({ width = rw, height = rh, radius = math.max(2, px(5)), fill = col, opacity = 0.55,
      align = "center", justify = "center" }, dedans)
    local ligne = { rect }
    if x * sw >= 1 then table.insert(ligne, 1, vide(x * sw, 1)) end
    local couche = { ui.row({ height = rh, gap = 0, align = "start", justify = "start" }, ligne) }
    if y * sh >= 1 then table.insert(couche, 1, vide(1, y * sh)) end
    table.insert(couches, ui.column({ width = sw, height = sh, gap = 0, align = "start", justify = "start" }, couche))
  end
  if #couches == 0 then table.insert(couches, vide(sw, sh)) end
  return ui.column({ width = sw, height = sh, radius = px(6), fill = "on_surface/0.06", border = "on_surface/0.22",
    borderWidth = 1, gap = -sh, align = "start", justify = "start" }, couches)
end

-- Schéma d'une session : une rangée par bureau, ses écrans côte à côte
local function schema(s, w, h, col)
  local parBureau, ordre = {}, {}
  for _, e in ipairs(type(s.schema) == "table" and s.schema or {}) do
    if type(e) == "table" then
      local b = tostring(e.bureau or "?")
      if not parBureau[b] then parBureau[b] = {}; table.insert(ordre, b) end
      table.insert(parBureau[b], e)
    end
  end
  table.sort(ordre, function(a, b)
    local na, nb = tonumber(a), tonumber(b)
    if na and nb then return na < nb end
    if na or nb then return na ~= nil end
    return a < b
  end)
  local pad, gap, etiq = px(18), px(10), px(64)
  local n = math.min(#ordre, MAX_BUREAUX)
  if n == 0 then
    return { ui.glyph({ name = glyphe(s.icone), size = px(72), color = col }) }
  end
  local rh = math.floor((h - 2 * pad - (n - 1) * gap) / n)
  local noms = type(s.bureaux_noms) == "table" and s.bureaux_noms or {}
  local rangees = {}
  for i = 1, n do
    local b = ordre[i]
    local ecrans = parBureau[b]
    -- Largeur de chaque écran à la hauteur de la rangée, réduite si la rangée déborde
    local larg, total = {}, 0
    for k, e in ipairs(ecrans) do
      local ratio = (tonumber(e.largeur) or 16) / math.max(1, tonumber(e.hauteur) or 10)
      larg[k] = rh * ratio
      total = total + larg[k]
    end
    local dispo = w - 2 * pad - etiq - gap * #ecrans
    local k2 = total > dispo and dispo / total or 1
    local kids = {
      ui.column({ width = etiq, height = rh, align = "start", justify = "center", gap = px(2) }, {
        ui.label({ text = texte(noms[b]) or (tr("Bureau ", "Desktop ") .. b), fontSize = px(13), fontWeight = "semibold",
          color = "on_surface", maxWidth = etiq, maxLines = 2 }),
      }),
    }
    for k, e in ipairs(ecrans) do
      table.insert(kids, ecranSchema(e, math.floor(larg[k] * k2), math.floor(rh * k2), col))
    end
    table.insert(rangees, ui.row({ height = rh, gap = gap, align = "center", justify = "start" }, kids))
  end
  if #ordre > n then
    table.insert(rangees, ui.label({ text = "+" .. (#ordre - n) .. tr(" bureau(x)", " desktop(s)"), fontSize = px(12),
      color = "on_surface_variant" }))
  end
  return rangees
end

local function apercu(s)
  local p = texte(s.apercu)
  return p and noctalia.fileExists(p) and p or nil
end

-- Une carte de la bande, à la distance d (entière) du centre
local function carte(c, idx, w, h, d, a)
  local milieu = d == 0
  local clic = function()
    if idx == target then activer(c) else aller(idx) end
  end
  local droit = function() if not c.nouvelle then aller(idx); editer(c) end end
  local R = px(18)
  if c.nouvelle then
    local kids = { ui.glyph({ name = "plus", size = px(milieu and 72 or 40), color = "primary" }) }
    if milieu then
      table.insert(kids, ui.label({ text = tr("Nouvelle session", "New session"), fontSize = px(22), fontWeight = "bold",
        color = "on_surface" }))
    end
    return ui.column({ key = "c" .. idx, width = w, height = h, radius = R, fill = "on_surface/0.06",
      border = (milieu and mode == "nom") and "primary" or "on_surface/0.25", borderWidth = 2, opacity = a,
      align = "center", justify = "center", gap = px(12), onClick = clic }, kids)
  end
  local col = couleur(c)
  local bord = (milieu and mode == "confirmer") and "error" or (milieu and col or "on_surface/0.18")
  local img = apercu(c)
  if img then
    -- Liseré : le cadre (couleur de la session au milieu) déborde de 3 points autour de la capture
    return ui.column({ key = "c" .. idx, width = w, height = h, radius = R, fill = bord, opacity = a,
      align = "center", justify = "center", onClick = clic, onRightClick = droit }, {
      ui.image({ key = "i" .. idx, path = img, width = w - 6, height = h - 6, fit = "cover", radius = R - 3 }),
    })
  end
  local kids
  if milieu then
    kids = schema(c, w, h, col)
  else
    kids = {
      ui.glyph({ name = glyphe(c.icone), size = px(40), color = col }),
      ui.label({ text = c.nom, fontSize = px(15), fontWeight = "semibold", color = "on_surface", maxWidth = w - px(16),
        maxLines = 3, textAlign = "center" }),
    }
  end
  return ui.column({ key = "c" .. idx, width = w, height = h, radius = R, fill = "surface_variant/0.85", border = bord,
    borderWidth = milieu and 2 or 1, opacity = a, align = milieu and "start" or "center", justify = "center",
    gap = milieu and px(10) or px(12), paddingH = milieu and px(18) or 0, onClick = clic, onRightClick = droit }, kids)
end

-- Bande de cartes : la carte du milieu grande, les voisines étroites et de plus en plus petites (bornée, sans boucle)
local function bande()
  local n = #cartes
  local reach = portee()
  local c = math.floor(pos + 0.5)
  local fl = math.floor(pos)
  local kids, centres, x = {}, {}, 0
  for idx = math.max(1, c - reach), math.min(n, c + reach + 1) do
    local d = math.abs(idx - c)
    local w, h = dims(d)
    local a = 1 - 0.3 * math.min(d, 1)
    if d >= REACH then a = a * 0.5 end
    centres[idx] = x + w / 2
    table.insert(kids, ui.row({ key = "r" .. idx, width = w, height = ROW_H, align = "center", justify = "center" }, {
      carte(cartes[idx], idx, w, h, d, a),
    }))
    x = x + w + SPACE
  end
  -- Amène « pos » au centre : la bande est centrée, une boîte vide d'un côté la décale
  local largeur = x - SPACE
  local p0 = centres[fl] or centres[c] or largeur / 2
  local p = lerp(p0, centres[fl + 1] or p0, pos - fl)
  local s = largeur / 2 - p
  if s > 0 then
    table.insert(kids, 1, vide(2 * s - SPACE, 1))
  elseif s < 0 then
    table.insert(kids, vide(-2 * s - SPACE, 1))
  end
  return ui.row({ height = ROW_H, width = largeur + 2 * math.abs(s) + 60, align = "center", justify = "center", gap = SPACE }, kids)
end

local function aide(t, couleurTexte)
  return ui.label({ text = t, fontSize = px(13), color = couleurTexte or "on_surface_variant", maxWidth = CW + px(200),
    maxLines = 2, textAlign = "center" })
end

-- Sous la bande : ce qu'il faut savoir de la carte du milieu, et ce qu'on peut y faire
local function legende()
  local c = courante()
  local kids = {}
  if not c then return ui.column({ height = INFO_H }, {}) end
  if c.nouvelle then
    table.insert(kids, ui.row({ gap = px(10), align = "center" }, {
      ui.glyph({ name = "plus", size = px(26), color = "primary" }),
      ui.label({ text = tr("Nouvelle session", "New session"), fontSize = px(26), fontWeight = "bold", color = "on_surface" }),
    }))
    if mode == "nom" or (mode == "attente" and nomSaisi ~= "") then
      table.insert(kids, ui.row({ width = px(460), height = px(52), paddingH = px(20), gap = px(10), align = "center",
        radius = px(26), fill = "on_surface/0.10", border = "primary/0.6", borderWidth = 2 }, {
        ui.glyph({ name = "edit", size = px(20), color = "primary" }),
        ui.input({
          key = "nom" .. inputKey,
          value = nomSaisi,
          placeholder = tr("Nom de la session (ex. Dev)", "Session name (e.g. Dev)"),
          fontSize = px(20),
          frameVisible = false,
          focus = true,
          flexGrow = 1,
          onChange = function(v) nomSaisi = v; render() end,
          onSubmit = function() enregistrer() end,
        }),
      }))
      local t = noctalia.string.trim(nomSaisi)
      if t ~= "" and existe(t) then
        table.insert(kids, aide(tr("« " .. t .. " » existe déjà : Entrée la remplace par tes fenêtres d'aujourd'hui",
          "“" .. t .. "” already exists: Enter replaces it with today's windows"), "error"))
      else
        table.insert(kids, aide(tr("↵ enregistrer les fenêtres ouvertes · Échap annuler", "↵ save the open windows · Esc cancel")))
      end
    else
      table.insert(kids, aide(#sessions == 0
        and tr("Aucune session pour l'instant. Enregistre tes fenêtres ouvertes pour les retrouver d'un geste.",
               "No sessions yet. Save your open windows to get them back in one go.")
        or tr("Enregistre tes fenêtres ouvertes, leurs bureaux et leur place.", "Save your open windows, their desktops and places.")))
      table.insert(kids, aide(tr("↵ lui donner un nom · Échap fermer", "↵ give it a name · Esc close")))
    end
  else
    local col = couleur(c)
    local ligne = {
      ui.box({ width = px(14), height = px(14), radius = px(7), fill = col }),
      ui.glyph({ name = glyphe(c.icone), size = px(26), color = col }),
      ui.label({ text = c.nom, fontSize = px(26), fontWeight = "bold", color = "on_surface", maxWidth = CW, maxLines = 1 }),
    }
    local quand = depuis(c.date)
    if quand then table.insert(ligne, ui.label({ text = "· " .. quand, fontSize = px(16), color = "on_surface_variant" })) end
    table.insert(kids, ui.row({ gap = px(10), align = "center" }, ligne))
    local applis = {}
    local liste = type(c.applis) == "table" and c.applis or {}
    for i, a in ipairs(liste) do
      if i > MAX_APPLIS then break end
      local p = iconeAppli(a, px(28))
      if p then
        table.insert(applis, ui.image({ path = p, width = px(28), height = px(28), fit = "contain" }))
      else
        table.insert(applis, ui.glyph({ name = "app-window", size = px(24), color = "on_surface_variant" }))
      end
    end
    if #liste > MAX_APPLIS then
      table.insert(applis, ui.label({ text = "+" .. (#liste - MAX_APPLIS), fontSize = px(14), color = "on_surface_variant" }))
    end
    local nf = tonumber(c.nb_fenetres) or 0
    table.insert(applis, ui.label({ text = nf .. (nf > 1 and tr(" fenêtres", " windows") or tr(" fenêtre", " window")),
      fontSize = px(14), color = "on_surface_variant" }))
    table.insert(kids, ui.row({ gap = px(8), align = "center" }, applis))
    if mode == "confirmer" then
      table.insert(kids, aide(tr("Supprimer « " .. c.nom .. " » ? ↵ oui · Échap non", "Delete “" .. c.nom .. "”? ↵ yes · Esc no"), "error"))
    elseif mode ~= "attente" then
      table.insert(kids, aide(tr("↵ ouvrir · E modifier · Maj + Suppr supprimer · Échap fermer",
        "↵ open · E edit · Shift + Del delete · Esc close")))
    end
  end
  if message then table.insert(kids, aide(message, messageErreur and "error" or "primary")) end
  return ui.column({ height = INFO_H, width = BGW, align = "center", justify = "start", gap = px(10) }, kids)
end

function render()
  local corps
  if not charge then
    corps = ui.column({ height = ROW_H + INFO_H, align = "center", justify = "center" }, {
      ui.label({ text = tr("Lecture des sessions…", "Reading the sessions…"), fontSize = px(20), color = "on_surface_variant" }),
    })
  else
    corps = ui.column({ height = ROW_H + INFO_H, width = BGW, align = "center", justify = "start", gap = 0 }, { bande(), legende() })
  end
  local ease = 1 - (1 - appear) * (1 - appear)
  local H = ROW_H + INFO_H
  -- Remonté pour que le fond commence en haut du cadre (comme nc/carousel)
  panel.render(ui.column({ flexGrow = 1, align = "center", justify = "start", gap = (HAUT_BARRE + BORD) - HAUT_PANNEAU - 1, opacity = ease }, {
    ui.box({ width = 1, height = 1, opacity = 0 }),
    ui.column({ minWidth = BGW, align = "center", justify = "start", gap = -(BGH + H) / 2 }, {
      bg and ui.image({ path = bg, width = BGW, height = BGH, fit = "cover", radius = RAYON }) or ui.box({ width = BGW, height = BGH, opacity = 0 }),
      ui.column({ height = H, width = BGW, align = "center", justify = "center" }, { corps }),
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
      local t = target + holdDir
      if t >= 1 and t <= #cartes then aller(t) end   -- maintenu : s'arrête au bout au lieu de boucler
    end
  end
  local k = eco and 1 or (1 - math.exp(-dt / SMOOTH_MS))
  pos = pos + (target - pos) * k
  if math.abs(target - pos) < 0.003 then pos = target end
  render()
  if pos == target and holdDir == 0 and appear >= 1 then setTicking(false) end
end

-- ── Clavier ─────────────────────────────────────────────────────────────────
local function entree(chord) return chord == "Return" or chord == "KP_Enter" end

function onKey(chord, pressed)
  -- Champ du nom : Entrée enregistre, Échap revient à la liste ; « e », capturé pour E (modifier), y est ajouté ici
  if mode == "nom" then
    if not pressed then return end
    if chord == "Escape" then mode, message = "liste", nil; render()
    elseif entree(chord) then enregistrer()
    elseif chord == "e" then nomSaisi = nomSaisi .. "e"; inputKey = inputKey + 1; render() end
    return
  end
  if mode == "attente" then
    if pressed and chord == "Escape" then panel.close() end
    return
  end
  if mode == "confirmer" then
    if not pressed then return end
    local c = courante()
    if entree(chord) and c and not c.nouvelle then supprimer(c)
    else mode = "liste"; render() end
    return
  end
  local dir = 0
  if chord == "Left" or chord == "Up" or chord == "shift+Tab" or chord == "ISO_Left_Tab" then dir = -1
  elseif chord == "Right" or chord == "Down" or chord == "Tab" then dir = 1 end
  if dir ~= 0 then
    if pressed then
      aller(target + dir)
      holdDir = dir
      holdT = -REPEAT_DELAY
    elseif holdDir == dir then
      holdDir = 0
    end
    return
  end
  if not pressed then return end
  local c = courante()
  if chord == "Escape" then panel.close()
  elseif chord == "Home" then aller(1)
  elseif chord == "End" then aller(#cartes)
  elseif entree(chord) then activer(c)
  elseif chord == "shift+Delete" or chord == "Shift+Delete" then
    if c and not c.nouvelle then mode, message = "confirmer", nil; render() end
  elseif chord == "e" or chord == "E" then
    if c and not c.nouvelle then editer(c) end
  end
end

-- Molette : carte précédente ou suivante
function onScroll(axe, pas)
  if mode ~= "liste" or not tonumber(pas) or tonumber(pas) == 0 then return end
  aller(target + (tonumber(pas) < 0 and -1 or 1))
end

function onOpen(context)
  EN = langue() == "en"
  setZoom()
  holdDir = 0
  mode, nomSaisi, message = "liste", "", nil
  voulu = texte(context)   -- nom facultatif à centrer : panel-toggle nc/sessions:main "Dev"
  bg = nil
  local o = currentOutput()
  local fond = noctalia.wallpaperPath(o and o.name or "")
  if fond then
    local b = THUMBS .. (string.match(fond, "([^/]+)$") or "") .. ".B.webp"
    if noctalia.fileExists(b) then bg = b end
  end
  if charge then construire() end   -- la liste d'avant tout de suite, relue juste après
  eco = noctalia.fileExists(ECO)
  appear = eco and 1 or 0
  ticking = false
  if not eco then setTicking(true) end
  render()
  recharger()
end

function onClose()
  holdDir = 0
  mode = "liste"
  setTicking(false)
end

-- Touches simulées (tests, raccourcis) : noctalia msg plugin nc/sessions:main all key Right
function onIpc(event, payload)
  if event == "key" and payload then onKey(payload, true); onKey(payload, false) end
end

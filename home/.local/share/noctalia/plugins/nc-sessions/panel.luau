-- nc/sessions (Noctalia v5) : les sessions enregistrées (nc-session) dans un carrousel, sur le modèle de nc/carousel.
-- Une carte par session (sa capture, sinon le dessin de ses fenêtres, une rangée par bureau), puis « + Nouvelle session ».
-- Gauche/Droite ou molette (maintenir une flèche pour défiler), clic sur une voisine pour la centrer ; la bande boucle
-- comme celle des fonds dès 3 cartes. Tranches inclinées : toutes les cartes de la bande en sont, ou aucune. Quand
-- chaque session a les siennes (« tranche », « tranche_etroite » de nc-session json) et que « Nouvelle session » en a
-- une (l'écran en direct passé dans nc-carousel-thumbs tranche, sinon les tranches du fond courant), la bande est
-- exactement celle du carrousel des fonds : seules les images, et le titre de la carte choisie dessous. Sinon (pas
-- d'ImageMagick, pas de grim…), toutes les cartes sont droites, en verre, le titre dedans.
-- Entrée ou clic sur la carte du milieu : ouvrir la session (ou nommer la nouvelle) ; Maj + Suppr : la supprimer, après
-- confirmation sur la carte ; clic droit ou « Modifier » : l'éditeur, un volet à droite de la carte ; Échap : fermer.
-- Aucune lettre n'est capturée (plugin.toml) : elles vont toujours au champ qui a le focus.
-- Données : seulement nc-session (json, ouvrir, enregistrer, supprimer…), jamais ses fichiers.
-- Même cadre que le carrousel des fonds : dessiné pour un écran de 1600 x 1000 points, réduit sur un plus petit, agrandi
-- sur un plus grand ; fond flou du fond d'écran courant (miniature de nc-carousel-thumbs). Carte du milieu à la hauteur
-- de la tranche du milieu des fonds, au ratio de l'écran actif (celui des captures), en verre (style de la DA).
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
local OUTIL = noctalia.expandPath("~/.local/bin/nc-carousel-thumbs")   -- « tranche IMAGE LARGE ETROITE »
-- Tailles du carrousel des fonds (nc/carousel/panel.luau) : mêmes cartes, mêmes voisines.
-- INFO : sous des cartes droites, la ligne d'aide ; INFO_T : sous des tranches, le titre de la carte choisie en plus
local BASE = { CW = 600, CH = 450, NW = 192, NH = 420, BGW = 1560, BGH = 940, INFO = 90, INFO_T = 190 }
local CW, CH = 720, BASE.CH       -- carte du milieu : hauteur de la tranche du milieu des fonds, ratio de l'écran actif
local CWT = BASE.CW               -- tranche du milieu (session avec ses tranches inclinées) : celle des fonds
local NW, NH = BASE.NW, BASE.NH   -- carte étroite (voisine immédiate)
local INFO_H = BASE.INFO          -- sous la bande : une ligne d'aide (ou la confirmation, ou un message)
local INFO_T = BASE.INFO_T        -- sous des tranches : nom, fenêtres, applis de la carte choisie, puis l'aide
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
local SK = 0.30       -- inclinaison des tranches (celle de nc-carousel-thumbs)
local BOUCLE_MIN = 3  -- la bande boucle à partir de 3 cartes

local sessions = {}   -- sessions de nc-session json
local cartes = {}     -- sessions, puis { nouvelle = true }
local charge = false  -- liste lue au moins une fois
local target, pos = 1, 1
local holdDir, holdT = 0, 0
local appear = 1
local ticking = false
local bg = nil
local mode = "liste"  -- liste | nom (nouvelle session) | confirmer (suppression) | attente | editeur
local nomSaisi = ""
local inputKey = 0
local message = nil   -- texte bref sous la carte (erreur de nc-session…)
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
  CWT, CH, NW, NH, INFO_H, INFO_T = px(BASE.CW), px(BASE.CH), px(BASE.NW), px(BASE.NH), px(BASE.INFO), px(BASE.INFO_T)
  CW = o and o.height > 0 and math.floor(CH * o.width / o.height + 0.5) or math.floor(CH * 1.6 + 0.5)
  if o then BGW, BGH = o.width - 2 * BORD, o.height - HAUT_BARRE - 2 * BORD else BGW, BGH = px(BASE.BGW), px(BASE.BGH) end
  ROW_H = CH + px(30)
end

local function setTicking(on)
  if on ~= ticking then
    ticking = on
    panel.setNeedsFrameTick(on)
  end
end

-- Bande en boucle (comme les fonds) dès 3 cartes : target n'est alors plus borné, wrap() donne la carte
local function boucle() return #cartes >= BOUCLE_MIN end
local function wrap(i)
  local n = #cartes
  if n == 0 then return 1 end
  return ((i - 1) % n) + 1
end
local function courante() return cartes[wrap(target)] end

local fermerEditeur   -- plus bas (l'éditeur)

-- Aller à la carte i ; animé, sauf en Économie. Sans boucle (1 ou 2 cartes), d'un bout à l'autre
local function aller(i)
  local n = #cartes
  if n == 0 then return end
  if not boucle() then
    if i < 1 then i = n elseif i > n then i = 1 end
  end
  if i ~= target then
    target = i
    if mode == "confirmer" then mode = "liste" end
    if mode == "editeur" then fermerEditeur() end   -- l'éditeur suit sa carte : une autre carte le ferme
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

local function entree(chord) return chord == "Return" or chord == "KP_Enter" end

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

-- Taille de la carte à la distance (continue) delta du centre : comme nc/carousel ; large : largeur au milieu
local function dims(delta, large)
  local t = math.min(delta, 1)
  local sc = delta <= 1 and 1 or math.max(0.58, 0.88 ^ (delta - 1))
  return lerp(large or CW, NW * sc, t), lerp(CH, NH * sc, t)
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
  local pad, gap, etiq = px(24), px(10), px(64)
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

-- Tranche inclinée de la session (nc-session json : « tranche » au milieu, « tranche_etroite » pour les voisines)
local function tranche(s, milieu)
  if not s or s.nouvelle then return nil end
  local p = texte(milieu and s.tranche or s.tranche_etroite)
  return p and noctalia.fileExists(p) and p or nil
end

-- Verre de la DA : couches superposées à la même taille (marge négative = hauteur), dans l'ordre du dessin :
-- fond translucide de la surface (55 %), contenu, reflet d'un point en haut (blanc 16 %), et pour la carte choisie
-- seulement un contour de 1,5 point à l'accent. L'API des plugins (32) n'a pas de dégradé : contour d'une couleur.
local function verre(props, w, h, couches, choisie)
  local R = px(RAYON)
  local l = { ui.box({ width = w, height = h, radius = R, fill = "surface/0.55" }) }
  for _, c in ipairs(couches) do table.insert(l, c) end
  table.insert(l, ui.column({ width = w, height = h, align = "center", justify = "start" }, {
    ui.box({ width = math.max(1, w - 2 * R), height = 1, fill = "#ffffff29" }),
  }))
  if choisie then
    table.insert(l, ui.box({ width = w, height = h, radius = R, fill = "#00000000", border = "primary", borderWidth = 1.5 }))
  end
  props.width, props.height, props.gap = w, h, -h
  props.align, props.justify = "start", "start"
  return ui.column(props, l)
end

-- Une couche : contenu calé en bas (ou en haut, au centre), aux marges de la carte
local function couche(w, h, justify, align, kids, marge)
  return ui.column({ width = w, height = h, justify = justify, align = align or "start", paddingH = marge or 0,
    paddingV = marge or 0, gap = px(6) }, kids)
end

-- Voile en bas de la carte : de transparent au fond à 70 %, en marches superposées (pas de dégradé dans l'API)
local VOILE_MARCHES = 5
local function voile(w, h, vh)
  local l = {}
  local a = 1 - 0.3 ^ (1 / VOILE_MARCHES)   -- les marches cumulées donnent 70 % tout en bas
  for i = 1, VOILE_MARCHES do
    local hi = math.floor(vh * (VOILE_MARCHES - i + 1) / VOILE_MARCHES)
    table.insert(l, ui.column({ width = w, height = h, justify = "end" }, {
      ui.box({ width = w, height = hi, radius = px(RAYON), fill = string.format("surface/%.3f", a) }),
    }))
  end
  return l
end

local function iconesApplis(classes, taille, max)
  local l = {}
  for i, a in ipairs(classes) do
    if i > max then break end
    local p = iconeAppli(a, taille)
    if p then
      table.insert(l, ui.image({ path = p, width = taille, height = taille, fit = "contain" }))
    else
      table.insert(l, ui.glyph({ name = "app-window", size = taille - px(4), color = "on_surface_variant" }))
    end
  end
  if #classes > max then
    table.insert(l, ui.label({ text = "+" .. (#classes - max), fontSize = px(13), color = "on_surface_variant" }))
  end
  return l
end

local function nbFenetres(n)
  return n .. (n > 1 and tr(" fenêtres", " windows") or tr(" fenêtre", " window"))
end

-- ── Écran actuel (carte « Nouvelle session ») ───────────────────────────────
-- Miniature en direct (grim -s 0.25, fichier temporaire dans $XDG_RUNTIME_DIR, effacé à la fermeture), ou le schéma
-- des fenêtres du bureau actif si SESSIONS_CAPTURE=non ; rien sans grim. Fenêtres : hyprctl -j clients, en asynchrone.
-- Ses tranches inclinées : la miniature passée dans nc-carousel-thumbs tranche (mêmes fichiers temporaires, effacés à
-- la fermeture) ; en attendant, ou sans capture, celles du fond courant (cache du carrousel des fonds).
local direct = nil        -- miniature prête
local directFichier = nil -- fichier demandé à grim (effacé à la fermeture)
local directTranche = nil -- { large, etroite } prêtes
local aEffacer = {}       -- fichiers temporaires de cette ouverture
local trancheAttendue = false   -- grim puis nc-carousel-thumbs en cours
local fondTranche = nil   -- { large, etroite } du fond courant (<fond>.W.webp, <fond>.N.webp), s'il y en a
local ouverture = 0       -- rang de l'ouverture : une réponse arrivée après la fermeture est ignorée
local ouvert = false
local actuel = nil        -- { n, bureaux, classes, schema = { largeur, hauteur, rects } }

local function captureVoulue()
  local conf = noctalia.readFile(noctalia.expandPath("~/.config/nc/reglages.conf")) or ""
  for k, v in string.gmatch(conf, "([%u%d_]+)=([^\n]*)") do
    if k == "SESSIONS_CAPTURE" and string.match(v, '^%s*"?(%a*)') == "non" then return false end
  end
  return true
end

local function lireClients(brut, moniteurs)
  local l = noctalia.json.decode(brut or "")
  if type(l) ~= "table" then return nil end
  local res = { n = 0, bureaux = 0, classes = {} }
  local vusB, vusC = {}, {}
  for _, c in ipairs(l) do
    local ws = type(c) == "table" and type(c.workspace) == "table" and tonumber(c.workspace.id) or nil
    if ws and ws > 0 and c.mapped ~= false and c.hidden ~= true then
      res.n = res.n + 1
      if not vusB[ws] then vusB[ws] = true; res.bureaux = res.bureaux + 1 end
      local k = texte(c.class)
      if k and not vusC[k] then vusC[k] = true; table.insert(res.classes, k) end
    end
  end
  -- Schéma (capture refusée) : les fenêtres du bureau actif, dans l'écran actif
  if type(moniteurs) == "table" then
    for _, m in ipairs(moniteurs) do
      if type(m) == "table" and m.focused then
        local sc = tonumber(m.scale) or 1
        if sc <= 0 then sc = 1 end
        local mw, mh = (tonumber(m.width) or 0) / sc, (tonumber(m.height) or 0) / sc
        if (tonumber(m.transform) or 0) % 2 == 1 then mw, mh = mh, mw end
        local aws = type(m.activeWorkspace) == "table" and tonumber(m.activeWorkspace.id)
        local rects = {}
        for _, c in ipairs(l) do
          if type(c) == "table" and type(c.workspace) == "table" and tonumber(c.workspace.id) == aws and mw > 0 and mh > 0
             and type(c.at) == "table" and type(c.size) == "table" then
            local x = ((tonumber(c.at[1]) or 0) - (tonumber(m.x) or 0)) / mw
            local y = ((tonumber(c.at[2]) or 0) - (tonumber(m.y) or 0)) / mh
            table.insert(rects, { x = math.max(0, x), y = math.max(0, y), w = (tonumber(c.size[1]) or 0) / mw,
              h = (tonumber(c.size[2]) or 0) / mh, classe = c.class })
          end
        end
        res.schema = { largeur = mw, hauteur = mh, rects = rects }
      end
    end
  end
  return res
end

local function lireActuel()
  ouverture = ouverture + 1
  local rangO = ouverture
  local o = currentOutput()
  local capture = captureVoulue()
  if capture then
    local dir = env("XDG_RUNTIME_DIR") or "/tmp"
    local f = dir .. "/nc-sessions-direct-" .. rangO .. "-" .. tostring(noctalia.nowMs and noctalia.nowMs() or 0) .. ".png"
    local large, etroite = string.gsub(f, "%.png$", ".tranche.png"), string.gsub(f, "%.png$", ".tranche-etroite.png")
    directFichier = f
    aEffacer = { f }
    trancheAttendue = noctalia.fileExists(OUTIL)
    noctalia.runAsync({ "sh", "-c", 'command -v grim >/dev/null 2>&1 || exit 3; umask 077; exec grim -o "$1" -s 0.25 -t png "$0"',
      f, o and o.name or "" }, function(r)
      if rangO ~= ouverture or not ouvert then
        noctalia.runAsync({ "rm", "-f", f })     -- fermé entre-temps
        return
      end
      if r and r.exitCode == 0 then
        direct = f
        if trancheAttendue then
          table.insert(aEffacer, large)
          table.insert(aEffacer, etroite)
          noctalia.runAsync({ OUTIL, "tranche", f, large, etroite }, function(r2)
            if rangO ~= ouverture or not ouvert then
              noctalia.runAsync({ "rm", "-f", large, etroite })
              return
            end
            trancheAttendue = false
            if r2 and r2.exitCode == 0 then directTranche = { large = large, etroite = etroite } end
            render()
          end, 20000)
        end
      else
        trancheAttendue = false
      end
      render()
    end, 5000)
  end
  local function clients(moniteurs)
    noctalia.runAsync({ "hyprctl", "-j", "clients" }, function(r)
      if rangO ~= ouverture or not ouvert then return end
      actuel = r and r.exitCode == 0 and lireClients(r.stdout, moniteurs) or nil
      render()
    end, 3000)
  end
  if capture then
    clients(nil)
  else
    noctalia.runAsync({ "hyprctl", "-j", "monitors" }, function(r)
      if rangO ~= ouverture or not ouvert then return end
      clients(r and r.exitCode == 0 and noctalia.json.decode(r.stdout or "") or nil)
    end, 3000)
  end
end

local function oublierActuel()
  ouvert = false
  ouverture = ouverture + 1
  if #aEffacer > 0 then
    local argv = { "rm", "-f" }
    for _, f in ipairs(aEffacer) do table.insert(argv, f) end
    noctalia.runAsync(argv)
  end
  direct, directFichier, actuel, directTranche, aEffacer, trancheAttendue = nil, nil, nil, nil, {}, false
end

-- Tranche de « Nouvelle session » : l'écran en direct, sinon le fond courant
local function trancheNouvelle(milieu)
  local t = directTranche or fondTranche
  if not t then return nil end
  return milieu and t.large or t.etroite
end

-- Toutes les cartes en tranches, ou aucune : chaque session a les deux siennes, et « Nouvelle session » en a une (ou
-- l'attend : grim et nc-carousel-thumbs en cours, une place vide en attendant)
local enTranches = false   -- calculé à chaque image (render)
local function toutesTranches()
  for _, s in ipairs(sessions) do
    if not tranche(s, true) or not tranche(s, false) then return false end
  end
  return trancheNouvelle(true) ~= nil or trancheAttendue
end

-- ── Cartes ──────────────────────────────────────────────────────────────────
-- Contenu partagé entre la carte droite (dedans, sur le voile) et le titre sous une tranche (largeur L disponible)

-- « Modifier » (le clic droit aussi) : ouvre l'éditeur de la session
local function boutonModifier(c)
  return ui.row({ key = "modifier", height = px(30), paddingH = px(14), radius = px(15), align = "center", gap = px(6),
    fill = "surface/0.70", border = "#ffffff29", borderWidth = 1, onClick = function() editer(c) end }, {
    ui.glyph({ name = "edit", size = px(14), color = "on_surface" }),
    ui.label({ text = tr("Modifier", "Edit"), fontSize = px(13), fontWeight = "semibold", color = "on_surface" }),
  })
end

-- Nom de la session : pastille et icône à sa couleur, nom en gras ; « Modifier » à côté s'il est demandé
local function titreSession(c, L, taille, modifier)
  local col = couleur(c)
  local kids = {
    ui.box({ width = px(12), height = px(12), radius = px(6), fill = col }),
    ui.glyph({ name = glyphe(c.icone), size = px(22), color = col }),
    ui.label({ text = c.nom, fontSize = taille, fontWeight = "bold", color = "on_surface",
      maxWidth = math.max(px(60), L - px(60) - (modifier and px(120) or 0)), maxLines = 1 }),
  }
  if modifier then table.insert(kids, boutonModifier(c)) end
  return ui.row({ gap = px(10), align = "center", justify = "center" }, kids)
end

-- « 4 fenêtres · il y a 2 jours » puis les icônes des applis
local function ligneSession(c)
  local quand = depuis(c.date)
  local nf = tonumber(c.nb_fenetres) or 0
  local l = { ui.label({ text = nbFenetres(nf) .. (quand and (" · " .. quand) or ""), fontSize = px(13),
    color = "on_surface_variant" }) }
  for _, x in ipairs(iconesApplis(type(c.applis) == "table" and c.applis or {}, px(22), MAX_APPLIS)) do table.insert(l, x) end
  return ui.row({ gap = px(8), align = "center", justify = "center" }, l)
end

-- « Nouvelle session » : le champ du nom (et ses avertissements), sinon les fenêtres ouvertes
local function lignesNouvelle(L)
  local kids = {}
  if mode == "nom" or (mode == "attente" and nomSaisi ~= "") then
    table.insert(kids, ui.row({ width = math.min(px(420), L), height = px(44), paddingH = px(18), gap = px(10),
      align = "center", radius = px(22), fill = "surface/0.70", border = "primary/0.6", borderWidth = 1.5 }, {
      ui.glyph({ name = "edit", size = px(18), color = "primary" }),
      ui.input({
        key = "nom" .. inputKey,
        value = nomSaisi,
        placeholder = tr("Nom de la session (ex. Dev)", "Session name (e.g. Dev)"),
        fontSize = px(16),
        frameVisible = false,
        focus = true,
        flexGrow = 1,
        onChange = function(v) nomSaisi = v; render() end,
        onSubmit = function() enregistrer() end,
      }),
    }))
    local t = noctalia.string.trim(nomSaisi)
    if t ~= "" and existe(t) then
      table.insert(kids, ui.label({ text = tr("« " .. t .. " » existe déjà : Entrée la remplace par tes fenêtres d'aujourd'hui",
        "“" .. t .. "” already exists: Enter replaces it with today's windows"), fontSize = px(13), color = "error",
        maxWidth = L, maxLines = 2, textAlign = "center" }))
    end
    if message then
      table.insert(kids, ui.label({ text = message, fontSize = px(13), color = messageErreur and "error" or "primary",
        maxWidth = L, maxLines = 2, textAlign = "center" }))
    end
  else
    if actuel and actuel.n > 0 then
      local ligne = iconesApplis(actuel.classes, px(24), MAX_APPLIS)
      local b = actuel.bureaux
      table.insert(ligne, ui.label({ text = nbFenetres(actuel.n) .. tr(" sur ", " on ") .. b
        .. (b > 1 and tr(" bureaux", " desktops") or tr(" bureau", " desktop")), fontSize = px(13), color = "on_surface_variant" }))
      table.insert(kids, ui.row({ gap = px(8), align = "center" }, ligne))
    end
    if #sessions == 0 then
      table.insert(kids, ui.label({ text = tr("Aucune session pour l'instant : garde tes fenêtres pour plus tard.",
        "No sessions yet: keep your windows for later."), fontSize = px(13), color = "on_surface_variant",
        maxWidth = L, maxLines = 2, textAlign = "center" }))
    end
  end
  return kids
end

-- Le « + » dans un rond de verre, de diamètre d
local function plus(d)
  return ui.column({ width = d, height = d, radius = math.floor(d / 2), fill = "surface/0.55", border = "#ffffff29",
    borderWidth = 1, align = "center", justify = "center" }, {
    ui.glyph({ name = "plus", size = math.floor(d * 0.47 + 0.5), color = "primary" }),
  })
end

-- Carte « Nouvelle session » : l'écran actuel assombri, un « + » dans un rond de verre, le titre, les applis ouvertes ;
-- le champ du nom y vient aussi. Rien en dessous (l'aide seulement).
local function carteNouvelle(idx, w, h, milieu, a, clic)
  local M = px(24)
  local couches = {}
  if milieu then
    if direct then
      table.insert(couches, ui.image({ key = "direct", path = direct, width = w, height = h, fit = "cover", radius = px(RAYON) }))
      table.insert(couches, ui.box({ width = w, height = h, radius = px(RAYON), fill = "#00000073" }))   -- assombrie à 45 %
    elseif actuel and actuel.schema and #actuel.schema.rects > 0 then
      local sh = h - 2 * M
      local sw = math.min(w - 2 * M, math.floor(sh * actuel.schema.largeur / math.max(1, actuel.schema.hauteur)))
      table.insert(couches, couche(w, h, "center", "center", { ecranSchema(actuel.schema, sw, sh, "on_surface") }))
      table.insert(couches, ui.box({ width = w, height = h, radius = px(RAYON), fill = "#00000073" }))
    end
    local kids = {
      plus(px(72)),
      ui.label({ text = tr("Nouvelle session", "New session"), fontSize = px(22), fontWeight = "bold", color = "on_surface" }),
    }
    for _, k in ipairs(lignesNouvelle(w - 2 * M)) do table.insert(kids, k) end
    table.insert(couches, ui.column({ width = w, height = h, align = "center", justify = "center", gap = px(12), paddingH = M },
      kids))
  else
    table.insert(couches, couche(w, h, "center", "center", { ui.glyph({ name = "plus", size = px(40), color = "primary" }) }))
  end
  return verre({ key = "c" .. idx, opacity = a, onClick = clic }, w, h, couches, milieu)
end

-- Carte d'une session : la capture (ou le schéma) remplit la carte ; en bas, sur un voile, icône, couleur, nom, nombre
-- de fenêtres, date et applis. Les voisines : capture, ou icône et nom.
local function carteSession(c, idx, w, h, milieu, a, clic, droit)
  local M = px(24)
  local col = couleur(c)
  local img = apercu(c)
  local couches = {}
  if milieu then
    local vh = math.floor(h * 0.42)
    if img then
      table.insert(couches, ui.image({ key = "i" .. idx, path = img, width = w, height = h, fit = "cover", radius = px(RAYON) }))
    else
      -- (chaque couche fait la hauteur de la carte : le schéma occupe le haut, au-dessus du voile)
      table.insert(couches, ui.column({ width = w, height = h, align = "start", justify = "start" }, {
        ui.column({ width = w, height = h - vh + px(24), paddingH = M, align = "start", justify = "center", gap = px(10) },
          schema(c, w, h - vh + px(24), col)),
      }))
    end
    for _, v in ipairs(voile(w, h, vh)) do table.insert(couches, v) end
    table.insert(couches, couche(w, h, "end", "start", { titreSession(c, w - 2 * M, px(22)), ligneSession(c) }, M))
    -- « Modifier » en haut à droite (le clic droit aussi)
    if mode == "liste" then
      table.insert(couches, ui.column({ width = w, height = h, align = "end", justify = "start", paddingH = px(16), paddingV = px(16) }, {
        boutonModifier(c),
      }))
    end
  else
    if img then
      table.insert(couches, ui.image({ key = "i" .. idx, path = img, width = w, height = h, fit = "cover", radius = px(RAYON) }))
      for _, v in ipairs(voile(w, h, math.floor(h * 0.35))) do table.insert(couches, v) end
      table.insert(couches, couche(w, h, "end", "center", {
        ui.label({ text = c.nom, fontSize = px(13), fontWeight = "semibold", color = "on_surface", maxWidth = w - 2 * px(16),
          maxLines = 2, textAlign = "center" }),
      }, px(16)))
    else
      table.insert(couches, couche(w, h, "center", "center", {
        ui.glyph({ name = glyphe(c.icone), size = px(40), color = col }),
        ui.label({ text = c.nom, fontSize = px(15), fontWeight = "semibold", color = "on_surface", maxWidth = w - 2 * px(16),
          maxLines = 3, textAlign = "center" }),
      }, px(16)))
    end
  end
  return verre({ key = "c" .. idx, opacity = a, onClick = clic, onRightClick = droit }, w, h, couches, milieu)
end

-- Une carte de la bande, à la distance d (entière) du centre
local function carte(c, idx, w, h, d, a)
  local milieu = d == 0
  local clic = function()
    if idx == target then
      if mode ~= "editeur" then activer(c) end   -- éditeur ouvert : un clic sur sa carte n'ouvre pas la session
    else
      aller(idx)
    end
  end
  local droit = function() if not c.nouvelle then aller(idx); editer(c) end end
  -- Tranches : exactement un fond de nc/carousel (image découpée, plus large que sa place : SK x hauteur), et rien
  -- d'autre (ni verre ni boîte derrière) ; le titre de la carte choisie est sous la bande (legende)
  if enTranches then
    local t
    if c.nouvelle then t = trancheNouvelle(milieu) else t = tranche(c, milieu) end
    if t then
      return ui.image({ key = "c" .. idx, path = t, width = w + SK * h, height = h, fit = "cover", opacity = a,
        onClick = clic, onRightClick = droit })
    end
    -- « Nouvelle session » dont la tranche se prépare : une place vide (invisible) de la même taille
    return vide(w + SK * h, h)
  end
  if c.nouvelle then return carteNouvelle(idx, w, h, milieu, a, clic) end
  return carteSession(c, idx, w, h, milieu, a, clic, droit)
end

-- Bande de cartes : la carte du milieu grande, les voisines étroites, plus petites et à 70 %, les plus lointaines à
-- moitié moins (mêmes tailles, écarts et opacités que les tranches des fonds) ; en boucle dès 3 cartes. decal : la
-- carte du milieu glisse d'autant vers la gauche (éditeur ouvert).
local function bande(decal)
  local n = #cartes
  local enBoucle = boucle()
  local reach = enBoucle and math.min(portee(), math.max(1, math.floor(n / 2))) or portee()
  local c = math.floor(pos + 0.5)
  local fl = math.floor(pos)
  local kids, centres, x = {}, {}, 0
  local de, a_ = c - reach, c + reach + 1
  if not enBoucle then de, a_ = math.max(1, de), math.min(n, a_) end
  for idx = de, a_ do
    local d = math.abs(idx - c)
    local cc = cartes[wrap(idx)]
    local w, h = dims(d, enTranches and CWT or CW)
    local a = 1 - 0.3 * math.min(d, 1)
    if d >= REACH then a = a * 0.5 end
    centres[idx] = x + w / 2
    table.insert(kids, ui.row({ key = "r" .. idx, width = w, height = ROW_H, align = "center", justify = "center" }, {
      carte(cc, idx, w, h, d, a),
    }))
    x = x + w + SPACE
  end
  -- Amène « pos » au centre (moins decal) : la bande est centrée, une boîte vide d'un côté la décale
  local largeur = x - SPACE
  local p0 = centres[fl] or centres[c] or largeur / 2
  local p = lerp(p0, centres[fl + 1] or p0, pos - fl)
  local s = largeur / 2 - p - (decal or 0)
  if s > 0 then
    table.insert(kids, 1, vide(2 * s - SPACE, 1))
  elseif s < 0 then
    table.insert(kids, vide(-2 * s - SPACE, 1))
  end
  return ui.row({ height = ROW_H, width = largeur + 2 * math.abs(s) + 60, align = "center", justify = "center", gap = SPACE }, kids)
end

-- ── Aide sous la carte : une ligne, en pastilles de touches comme la fiche des raccourcis (nc/keys) ─────────────
local function pastille(t)
  return ui.row({ key = "touche:" .. t, height = px(24), paddingH = px(8), radius = px(7), align = "center",
    fill = "on_surface/0.08", border = "outline/0.3", borderWidth = 1 }, {
    ui.label({ text = t, fontSize = px(12), fontWeight = "semibold", color = "on_surface" }),
  })
end

-- { { touches…, texte }, … } → [↵] ouvrir · [Maj] [Suppr] supprimer…
local function ligneAide(groupes, couleurTexte)
  local kids = {}
  for i, g in ipairs(groupes) do
    if i > 1 then table.insert(kids, ui.label({ text = "·", fontSize = px(13), color = "on_surface_variant" })) end
    for k = 1, #g - 1 do table.insert(kids, pastille(g[k])) end
    table.insert(kids, ui.label({ text = g[#g], fontSize = px(13), color = couleurTexte or "on_surface_variant" }))
  end
  return ui.row({ key = "aide", gap = px(6), align = "center", justify = "center" }, kids)
end

local function phrase(t, couleurTexte)
  return ui.label({ text = t, fontSize = px(13), color = couleurTexte or "on_surface_variant",
    maxWidth = mode == "editeur" and CW or CW + px(200), maxLines = 2, textAlign = "center" })
end

-- Sous des tranches : le titre de la carte choisie, comme un titre sous une image (un voile droit dans la tranche
-- inclinée déborderait). Session : pastille, icône, nom, « Modifier » ; puis fenêtres, date, applis.
-- « Nouvelle session » : le « + », le titre, puis le champ du nom ou les fenêtres ouvertes.
local function titreSous(c)
  local L = math.min(BGW - 2 * px(24), CWT + px(200))
  if c.nouvelle then
    local kids = { ui.row({ gap = px(12), align = "center", justify = "center" }, {
      plus(px(40)),
      ui.label({ text = tr("Nouvelle session", "New session"), fontSize = px(22), fontWeight = "bold", color = "on_surface" }),
    }) }
    for _, k in ipairs(lignesNouvelle(L)) do table.insert(kids, k) end
    return ui.column({ key = "titre", align = "center", gap = px(8) }, kids)
  end
  return ui.column({ key = "titre", align = "center", gap = px(8) }, {
    titreSession(c, L, px(22), mode == "liste"),
    ligneSession(c),
  })
end

local function hauteurInfo() return enTranches and INFO_T or INFO_H end

local function legende()
  local c = courante()
  local kids = {}
  if not c then return ui.column({ height = hauteurInfo() }, {}) end
  local ECHAP = tr("Échap", "Esc")
  if enTranches then table.insert(kids, titreSous(c)) end
  if c.nouvelle then
    if mode == "nom" or mode == "attente" then
      table.insert(kids, ligneAide({ { "↵", tr("enregistrer les fenêtres ouvertes", "save the open windows") },
        { ECHAP, tr("annuler", "cancel") } }))
    else
      table.insert(kids, ligneAide({ { "↵", tr("lui donner un nom", "give it a name") }, { ECHAP, tr("fermer", "close") } }))
    end
  elseif mode == "confirmer" then
    table.insert(kids, ligneAide({ { tr("Supprimer « " .. c.nom .. " » ?", "Delete “" .. c.nom .. "”?") },
      { "↵", tr("oui", "yes") }, { ECHAP, tr("non", "no") } }, "error"))
  elseif mode == "editeur" then
    table.insert(kids, ligneAide({ { "Tab", tr("champ suivant", "next field") }, { ECHAP, tr("fermer l'éditeur", "close the editor") } }))
  elseif mode ~= "attente" then
    -- E n'est pas capturée (les lettres vont aux champs) : le clic droit ou « Modifier » ouvrent l'éditeur
    table.insert(kids, ligneAide({ { "↵", tr("ouvrir", "open") }, { tr("Maj", "Shift"), tr("Suppr", "Del"), tr("supprimer", "delete") },
      { tr("Clic droit", "Right click"), tr("modifier", "edit") }, { ECHAP, tr("fermer", "close") } }))
  end
  if message and not (c.nouvelle and (mode == "nom" or mode == "attente")) then table.insert(kids, phrase(message, messageErreur and "error" or "primary")) end
  return ui.column({ height = hauteurInfo(), width = BGW, align = "center", justify = "start", gap = px(10),
    paddingV = enTranches and px(8) or px(16) }, kids)
end

-- ── Éditeur d'une session ───────────────────────────────────────────────────
-- Un volet à droite, sur toute la hauteur du cadre du carrousel (à BORD de ses bords, rayon RAYON), par-dessus les
-- voisines de droite ; la carte du milieu glisse juste assez à gauche pour rester entière à côté. Chaque champ passe par nc-session modifier NOM CLE VALEUR
-- (qui valide tout), puis la liste est relue (nc-session json) : la carte montre aussitôt la nouvelle icône, couleur…
-- Tab / Maj + Tab (ou Haut / Bas) : champ suivant / précédent ; Gauche / Droite : parcourir les choix ; Entrée :
-- valider le choix, basculer l'interrupteur ou envoyer le texte ; Échap : fermer le volet. Un refus de nc-session
-- s'affiche sous le champ, en couleur d'erreur.
-- Raccourci : un champ texte (« Super+Alt+1 »). Une capture comme celle de l'île (nc-reglages capture, sous-carte
-- nc-capture) n'est pas faisable ici : un panneau en API 32 ne reçoit que les touches listées dans capture_keys, pas
-- une combinaison quelconque.
local ICONES = { "code", "work", "school", "sports_esports", "movie", "music_note", "brush", "terminal", "science", "home",
  "travel_explore", "chat", "mail", "book", "fitness_center", "photo", "bolt", "star", "favorite", "rocket_launch" }
-- Rôles du thème (acceptés par nc-session, dessinés par Noctalia)
local COULEURS = { "primary", "secondary", "tertiary", "error", "on_surface", "on_surface_variant", "outline", "hover" }
local PROFILS = { "garder", "performance", "balanced", "power-saver" }
local FERMER = { "non", "demander", "oui" }
local EXTS = { jpg = true, jpeg = true, png = true, webp = true, bmp = true, gif = true, jxl = true, avif = true, tif = true, tiff = true }
local edNom = nil       -- session modifiée
local champ = 1         -- champ qui a le focus (rang dans listeChamps)
local curseur = {}      -- choix parcouru au clavier, par champ
local brouillon = {}    -- texte tapé, pas encore envoyé
local erreurs = {}      -- refus de nc-session, par champ
local enCours = {}      -- modifier en cours, par champ (Entrée et onSubmit ne l'envoient pas deux fois)
local fonds = nil       -- fonds proposés : { path, vignette }
local gen = 0           -- recrée les champs texte quand le focus change (focus = true sur le seul champ choisi)
local vol = 1           -- apparition du volet (0 → 1), immédiate en Économie
local VOLET_W = 440     -- largeur du volet (écran de 1600 points)
local ECART = 16        -- entre la carte et le volet

local function edSession()
  for _, s in ipairs(sessions) do if s.nom == edNom then return s end end
  return nil
end

-- Fonds : ceux du carrousel des fonds (dossier de Noctalia), vignettes de nc-carousel-thumbs (<fond>.W.webp)
local function chargerFonds(actuel)
  fonds = {}
  local dir = noctalia.wallpaperDirectory and noctalia.wallpaperDirectory()
  if dir then
    if string.sub(dir, -1) ~= "/" then dir = dir .. "/" end
    local fichiers = noctalia.listDir(dir) or {}
    table.sort(fichiers, function(a, b) return string.lower(a) < string.lower(b) end)
    for _, f in ipairs(fichiers) do
      if EXTS[string.lower(string.match(f, "%.([%w]+)$") or "")] then
        local w = THUMBS .. f .. ".W.webp"
        table.insert(fonds, { path = dir .. f, vignette = noctalia.fileExists(w) and w or dir .. f })
      end
    end
  end
  -- Le fond de la session, même hors du dossier
  actuel = texte(actuel)
  if actuel then
    local vu = false
    for _, f in ipairs(fonds) do if f.path == actuel then vu = true end end
    if not vu and noctalia.fileExists(actuel) then table.insert(fonds, 1, { path = actuel, vignette = actuel }) end
  end
end

-- Bureaux présents dans la session (numérotés : nc-session refuse les autres)
local function bureauxDe(s)
  local vus, l = {}, {}
  local function ajouter(b)
    local n = tonumber(b)
    if n and n >= 1 and n <= 999 and n == math.floor(n) and not vus[n] then vus[n] = true; table.insert(l, n) end
  end
  for _, e in ipairs(type(s.schema) == "table" and s.schema or {}) do if type(e) == "table" then ajouter(e.bureau) end end
  for _, f in ipairs(type(s.fenetres) == "table" and s.fenetres or {}) do if type(f) == "table" then ajouter(f.bureau) end end
  table.sort(l)
  return l
end

-- Les champs, dans l'ordre de Tab
local function listeChamps(s)
  local valeursFond = { "" }
  for _, f in ipairs(fonds or {}) do table.insert(valeursFond, f.path) end
  local l = {
    { id = "icone", type = "choix", cle = "icone", valeurs = ICONES },
    { id = "couleur", type = "choix", cle = "couleur", valeurs = COULEURS },
    { id = "fond", type = "choix", cle = "fond", valeurs = valeursFond },
    { id = "profil", type = "choix", cle = "profil", valeurs = PROFILS },
    { id = "npd", type = "inter", cle = "npd" },
    { id = "demarrage", type = "inter", cle = "demarrage" },
    { id = "fermer_autres", type = "choix", cle = "fermer_autres", valeurs = FERMER },
    { id = "raccourci", type = "texte", cle = "raccourci" },
  }
  for _, b in ipairs(bureauxDe(s)) do
    table.insert(l, { id = "bureau." .. b, type = "texte", cle = "bureau." .. b .. ".nom", bureau = b })
  end
  for i, f in ipairs(type(s.fenetres) == "table" and s.fenetres or {}) do
    if type(f) == "table" then
      local n = i - 1   -- nc-session compte les fenêtres à partir de 0
      table.insert(l, { id = "fenetre." .. n .. ".inclure", type = "inter", cle = "fenetre." .. n .. ".inclure", fenetre = f })
      if type(f.terminal) == "table" then
        table.insert(l, { id = "fenetre." .. n .. ".dossier", type = "texte", cle = "fenetre." .. n .. ".dossier", fenetre = f })
        table.insert(l, { id = "fenetre." .. n .. ".commande", type = "texte", cle = "fenetre." .. n .. ".commande", fenetre = f })
      end
    end
  end
  return l
end

-- Valeur actuelle d'un champ (texte pour un choix ou un champ texte, booléen pour un interrupteur)
local function valeur(s, ch)
  local id = ch.id
  if id == "icone" then return texte(s.icone) or "" end
  if id == "couleur" then return texte(s.couleur) or "" end
  if id == "fond" then return texte(s.fond) or "" end
  if id == "profil" then return texte(s.profil) or "garder" end
  if id == "fermer_autres" then return texte(s.fermer_autres) or "non" end
  if id == "npd" or id == "demarrage" then return s[id] == true end
  if id == "raccourci" then return texte(s.raccourci) or "" end
  if ch.bureau then
    local noms = type(s.bureaux_noms) == "table" and s.bureaux_noms or {}
    return texte(noms[tostring(ch.bureau)]) or ""
  end
  if ch.fenetre then
    local quoi = string.match(id, "%.(%a+)$")
    if quoi == "inclure" then return ch.fenetre.inclure ~= false end
    return texte(type(ch.fenetre.terminal) == "table" and ch.fenetre.terminal[quoi]) or ""
  end
  return ""
end

local function rang(liste, v)
  for i, x in ipairs(liste) do if x == v then return i end end
  return nil
end

-- Le focus va au champ i : le curseur sur sa valeur, les champs texte recréés (seul le choisi a focus = true)
local function focaliser(i, l)
  local n = #l
  if n == 0 then return end
  if i < 1 then i = n elseif i > n then i = 1 end
  champ = i
  local ch, s = l[i], edSession()
  if ch.type == "choix" and s then curseur[ch.id] = rang(ch.valeurs, valeur(s, ch)) or 1 end
  gen = gen + 1
end

local function envoyer(ch, v)
  local s = edSession()
  if not s or enCours[ch.id] then return end
  enCours[ch.id] = true
  erreurs[ch.id] = nil
  render()
  noctalia.runAsync({ NC, "modifier", s.nom, ch.cle, v }, function(r)
    enCours[ch.id] = nil
    if r and r.exitCode == 0 then
      brouillon[ch.id] = nil
      voulu = s.nom
      recharger(function() gen = gen + 1 end)
    else
      local e = r and texte(r.stderr) and noctalia.string.trim(r.stderr) or nil
      erreurs[ch.id] = e or tr("Modification refusée", "Change refused")
      render()
    end
  end, 15000)
end

-- Entrée sur le champ qui a le focus
local function valider(ch)
  local s = edSession()
  if not s or not ch then return end
  if ch.type == "choix" then
    local v = ch.valeurs[curseur[ch.id] or 1]
    if v then envoyer(ch, v) end
  elseif ch.type == "inter" then
    envoyer(ch, valeur(s, ch) and "non" or "oui")
  else
    local t = brouillon[ch.id]
    if t == nil then t = valeur(s, ch) end
    envoyer(ch, noctalia.string.trim(t))
  end
end

-- Point d'entrée (clic droit, bouton « Modifier », E hors d'un champ)
function editer(session)
  if not session or session.nouvelle or not texte(session.nom) then return end
  mode, edNom, message = "editeur", session.nom, nil
  curseur, brouillon, erreurs, enCours = {}, {}, {}, {}
  chargerFonds(session.fond)
  focaliser(1, listeChamps(session))
  vol = eco and 1 or 0
  if not eco then setTicking(true) end
  render()
end

fermerEditeur = function()
  mode, edNom = "liste", nil
  vol = 1
end

local function clavierEditeur(chord)
  local s = edSession()
  if not s then fermerEditeur(); render(); return end
  local l = listeChamps(s)
  local ch = l[champ]
  if chord == "Escape" then fermerEditeur()
  elseif chord == "Tab" or chord == "Down" then focaliser(champ + 1, l)
  elseif chord == "shift+Tab" or chord == "ISO_Left_Tab" or chord == "Up" then focaliser(champ - 1, l)
  elseif (chord == "Left" or chord == "Right") and ch and ch.type == "choix" then
    local n = #ch.valeurs
    local c = (curseur[ch.id] or 1) + (chord == "Left" and -1 or 1)
    if c < 1 then c = n elseif c > n then c = 1 end
    curseur[ch.id] = c
  elseif entree(chord) then valider(ch)
  else return end
  render()
end

-- Largeur du volet (fixe, réduite avec l'écran) et glissement de la carte du milieu vers la gauche, juste assez pour
-- qu'elle ne passe pas sous le volet : environ 30 points en 1600 x 1000 comme en 1280 x 800 (carte au ratio de l'écran)
local function placeVolet()
  local VW = px(VOLET_W)
  local largeur = enTranches and CWT + SK * CH or CW     -- une tranche déborde de SK x hauteur (moitié de chaque côté)
  local droite = BGW / 2 + largeur / 2 + px(ECART)      -- bord droit de la carte du milieu, plus l'écart
  local decal = math.max(0, math.floor(droite - (BGW - BORD - VW) + 0.5))
  decal = math.min(decal, math.max(0, math.floor(BGW / 2 - largeur / 2 - px(16))))   -- jamais à moins de 16 du bord gauche
  return VW, decal
end

-- Dessin du volet
local LIB_PROFIL = {
  garder = { "Garder le profil", "Keep the profile" }, performance = { "Performance", "Performance" },
  balanced = { "Équilibré", "Balanced" }, ["power-saver"] = { "Économie", "Power saver" },
}
local LIB_FERMER = {
  non = { "Garder les autres fenêtres", "Keep the other windows" }, demander = { "Demander", "Ask" },
  oui = { "Fermer les autres", "Close the others" },
}

local function grille(cases, cols, gap)
  local rangees, ligne = {}, {}
  for _, c in ipairs(cases) do
    table.insert(ligne, c)
    if #ligne == cols then table.insert(rangees, ui.row({ gap = gap, align = "center" }, ligne)); ligne = {} end
  end
  if #ligne > 0 then table.insert(rangees, ui.row({ gap = gap, align = "center" }, ligne)) end
  return ui.column({ gap = gap, align = "start" }, rangees)
end

local function volet(VW, H)
  local s = edSession()
  if not s then return vide(VW, H) end
  local l = listeChamps(s)
  if champ > #l then champ = #l end
  local col = couleur(s)
  local pad = px(16)
  local IW = VW - 2 * pad - px(12)   -- largeur utile (place pour la barre de défilement)

  local function section(i, ch, titre, contenu)
    local focus = i == champ
    local kids = {}
    if titre then
      table.insert(kids, ui.label({ text = titre, fontSize = px(13), fontWeight = "semibold",
        color = focus and "primary" or "on_surface_variant", maxWidth = IW - px(16), maxLines = 1 }))
    end
    for _, k in ipairs(contenu) do table.insert(kids, k) end
    if erreurs[ch.id] then
      table.insert(kids, ui.label({ key = "err:" .. ch.id, text = erreurs[ch.id], fontSize = px(12), color = "error",
        maxWidth = IW - px(16), maxLines = 3 }))
    end
    return ui.column({ key = "s:" .. ch.id, width = IW, paddingH = px(8), paddingV = px(6), radius = px(10), gap = px(6),
      fill = focus and "on_surface/0.07" or "on_surface/0.0", border = focus and "primary" or "on_surface/0.0",
      borderWidth = focus and 2 or 1, align = "start" }, kids)
  end

  -- Une case de choix : la valeur actuelle remplie, le choix parcouru au clavier entouré
  local function caseChoix(i, ch, v, w, h, contenu, rayon)
    local actuel = valeur(s, ch) == v
    local vise = i == champ and ch.valeurs[curseur[ch.id] or 0] == v
    return ui.row({ key = "ed:" .. ch.id .. ":" .. v, width = w, height = h, radius = rayon or px(8),
      fill = actuel and "primary/0.28" or "on_surface/0.06",
      border = vise and "primary" or (actuel and "primary/0.6" or "on_surface/0.12"),
      borderWidth = vise and 2 or 1, align = "center", justify = "center", gap = px(6),
      onClick = function() champ = i; curseur[ch.id] = rang(ch.valeurs, v) or 1; envoyer(ch, v) end }, contenu)
  end

  local function champTexte(i, ch, placeholder)
    local focus = i == champ
    local v = brouillon[ch.id]
    if v == nil then v = valeur(s, ch) end
    return ui.row({ width = IW - px(16), height = px(38), paddingH = px(12), radius = px(19), align = "center",
      fill = "on_surface/0.10", border = focus and "primary/0.7" or "on_surface/0.15", borderWidth = focus and 2 or 1 }, {
      ui.input({ key = "t:" .. ch.id .. ":" .. gen, value = v, placeholder = placeholder, fontSize = px(14),
        frameVisible = false, focus = focus, flexGrow = 1,
        onChange = function(t)
          brouillon[ch.id] = t
          if champ ~= i then champ = i; render() end   -- un clic dans le champ y met le focus
        end,
        onSubmit = function() champ = i; valider(ch) end }),
    })
  end

  local function interrupteur(i, ch, contenu)
    local oui = valeur(s, ch)
    table.insert(contenu, ui.spacer({ flexGrow = 1 }))
    table.insert(contenu, ui.toggle({ key = "ed:" .. ch.id, checked = oui,
      onChange = function() champ = i; envoyer(ch, oui and "non" or "oui") end }))
    return ui.row({ width = IW - px(16), height = px(30), gap = px(8), align = "center" }, contenu)
  end

  local sections = {}
  local bureauxVus, fenetresVues = false, false
  local function intertitre(t)
    table.insert(sections, ui.label({ text = t, fontSize = px(15), fontWeight = "bold", color = "on_surface" }))
  end
  for i, ch in ipairs(l) do
    local id = ch.id
    if id == "icone" then
      local cases = {}
      local c = math.floor((IW - px(16) - 9 * px(4)) / 10)
      for _, nom in ipairs(ICONES) do
        table.insert(cases, caseChoix(i, ch, nom, c, c, { ui.glyph({ name = glyphe(nom), size = math.floor(c * 0.55), color = col }) }))
      end
      table.insert(sections, section(i, ch, tr("Icône", "Icon"), { grille(cases, 10, px(4)) }))
    elseif id == "couleur" then
      local cases = {}
      local c, d = px(32), px(22)
      for _, role in ipairs(COULEURS) do
        table.insert(cases, caseChoix(i, ch, role, c, c,
          { ui.box({ width = d, height = d, radius = math.floor(d / 2), fill = role }) }, math.floor(c / 2)))
      end
      table.insert(sections, section(i, ch, tr("Couleur", "Color"), { grille(cases, 8, px(10)) }))
    elseif id == "fond" then
      local cases = {}
      local w = math.floor((IW - px(16) - 3 * px(6)) / 4)
      local h = math.floor(w * 0.66)
      table.insert(cases, caseChoix(i, ch, "", w, h, {
        ui.glyph({ name = "ban", size = px(18), color = "on_surface_variant" }),
        ui.label({ text = tr("Aucun", "None"), fontSize = px(12), color = "on_surface_variant" }),
      }))
      for _, f in ipairs(fonds or {}) do
        table.insert(cases, caseChoix(i, ch, f.path, w, h, {
          ui.image({ path = f.vignette, width = w - px(6), height = h - px(6), fit = "cover", radius = px(5) }),
        }))
      end
      local t = { grille(cases, 4, px(6)) }
      if #(fonds or {}) == 0 then
        table.insert(t, ui.label({ text = tr("Aucune image dans le dossier des fonds d'écran", "No images in the wallpaper folder"),
          fontSize = px(12), color = "on_surface_variant" }))
      end
      table.insert(sections, section(i, ch, tr("Fond d'écran", "Wallpaper"), t))
    elseif id == "profil" or id == "fermer_autres" then
      local libs = id == "profil" and LIB_PROFIL or LIB_FERMER
      local cases = {}
      local cols = id == "profil" and 2 or 1
      local w = math.floor((IW - px(16) - (cols - 1) * px(6)) / cols)
      for _, v in ipairs(ch.valeurs) do
        table.insert(cases, caseChoix(i, ch, v, w, px(32), {
          ui.label({ text = tr(libs[v][1], libs[v][2]), fontSize = px(13), color = "on_surface", maxWidth = w - px(12), maxLines = 1 }),
        }, px(16)))
      end
      table.insert(sections, section(i, ch, id == "profil" and tr("Profil d'énergie", "Power profile")
        or tr("À l'ouverture, les autres fenêtres", "When it opens, the other windows"), { grille(cases, cols, px(6)) }))
    elseif id == "npd" or id == "demarrage" then
      local t = id == "npd" and tr("Ne pas déranger", "Do not disturb") or tr("Ouvrir au démarrage", "Open at startup")
      table.insert(sections, section(i, ch, nil, { interrupteur(i, ch, {
        ui.label({ text = t, fontSize = px(14), color = "on_surface", maxWidth = IW - px(90), maxLines = 1 }) }) }))
    elseif id == "raccourci" then
      table.insert(sections, section(i, ch, tr("Raccourci (vide : aucun)", "Shortcut (empty: none)"),
        { champTexte(i, ch, "Super+Alt+1") }))
    elseif ch.bureau then
      if not bureauxVus then bureauxVus = true; intertitre(tr("Noms des bureaux", "Desktop names")) end
      table.insert(sections, section(i, ch, tr("Bureau ", "Desktop ") .. ch.bureau,
        { champTexte(i, ch, tr("Nom (vide : aucun)", "Name (empty: none)")) }))
    elseif ch.fenetre then
      if not fenetresVues then fenetresVues = true; intertitre(tr("Fenêtres", "Windows")) end
      local f = ch.fenetre
      local quoi = string.match(id, "%.(%a+)$")
      if quoi == "inclure" then
        local p = iconeAppli(f.classe, px(22))
        local contenu = { interrupteur(i, ch, {
          p and ui.image({ path = p, width = px(22), height = px(22), fit = "contain" })
            or ui.glyph({ name = "app-window", size = px(20), color = "on_surface_variant" }),
          ui.label({ text = texte(f.titre) or texte(f.classe) or "?", fontSize = px(14), color = "on_surface",
            maxWidth = IW - px(110), maxLines = 1 }),
        }) }
        table.insert(contenu, ui.label({ text = (texte(f.classe) or "?") .. tr(" · bureau ", " · desktop ") .. tostring(f.bureau or "?"),
          fontSize = px(12), color = "on_surface_variant", maxWidth = IW - px(16), maxLines = 1 }))
        table.insert(sections, section(i, ch, nil, contenu))
      elseif quoi == "dossier" then
        table.insert(sections, section(i, ch, tr("Dossier du terminal", "Terminal folder"), { champTexte(i, ch, "~/projet") }))
      else
        table.insert(sections, section(i, ch, tr("Commande du terminal (vide : le shell)", "Terminal command (empty: the shell)"),
          { champTexte(i, ch, "nvim .") }))
      end
    end
  end

  return ui.column({ key = "volet", width = VW, height = H, radius = RAYON, fill = "surface/0.94", border = "on_surface/0.15",
    borderWidth = 1, paddingH = pad, paddingV = px(14), gap = px(10), opacity = vol, align = "start" }, {
    ui.row({ width = VW - 2 * pad, height = px(34), gap = px(10), align = "center" }, {
      ui.glyph({ name = glyphe(s.icone), size = px(24), color = col }),
      ui.label({ text = tr("Modifier « " .. s.nom .. " »", "Edit “" .. s.nom .. "”"), fontSize = px(18), fontWeight = "bold",
        color = "on_surface", maxWidth = VW - 2 * pad - px(80), maxLines = 1 }),
      ui.spacer({ flexGrow = 1 }),
      ui.button({ key = "ed:fermer", glyph = "x", variant = "ghost", controlSize = "sm",
        onClick = function() fermerEditeur(); render() end }),
    }),
    ui.scroll({ flexGrow = 1, gap = px(10) }, sections),
    ui.label({ text = tr("Tab champ suivant · ← → choisir · ↵ valider · Échap fermer",
      "Tab next field · ← → choose · ↵ apply · Esc close"), fontSize = px(12), color = "on_surface_variant",
      maxWidth = VW - 2 * pad, maxLines = 2 }),
  })
end

function render()
  local corps
  enTranches = charge and toutesTranches()
  local edite = mode == "editeur" and charge and edSession() ~= nil
  local VW, decal = 0, 0
  if edite then
    VW, decal = placeVolet()
    decal = math.floor(decal * vol)
  end
  if not charge then
    corps = ui.column({ height = ROW_H + 2 * INFO_H, align = "center", justify = "center" }, {
      ui.label({ text = tr("Lecture des sessions…", "Reading the sessions…"), fontSize = px(20), color = "on_surface_variant" }),
    })
  else
    -- La bande au milieu du cadre, comme celle des fonds : une place vide au-dessus, de la hauteur de la légende
    local IH = hauteurInfo()
    corps = ui.column({ height = ROW_H + 2 * IH, width = BGW, align = "center", justify = "start", gap = 0 },
      { vide(1, IH), bande(decal), legende() })
  end
  local ease = 1 - (1 - appear) * (1 - appear)
  local H = ROW_H + 2 * hauteurInfo()
  if edite then
    -- Le volet à droite, sur toute la hauteur du cadre (à BORD de ses bords), par-dessus les voisines de droite
    local HV = BGH - 2 * BORD
    corps = ui.column({ height = HV, width = BGW, align = "end", justify = "start", gap = -HV }, {
      ui.column({ height = HV, width = BGW, align = "center", justify = "center" }, { corps }),
      ui.row({ width = VW + BORD, height = HV, align = "center", justify = "start" }, { volet(VW, HV) }),
    })
    H = HV
  end
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
  if vol < 1 then vol = eco and 1 or math.min(1, vol + dt / FADE_MS) end
  if holdDir ~= 0 then
    holdT = holdT + dt
    if holdT >= REPEAT_EVERY then
      holdT = holdT - REPEAT_EVERY
      local t = target + holdDir
      if boucle() or (t >= 1 and t <= #cartes) then aller(t) end   -- maintenu, sans boucle : s'arrête au bout
    end
  end
  local k = eco and 1 or (1 - math.exp(-dt / SMOOTH_MS))
  pos = pos + (target - pos) * k
  if math.abs(target - pos) < 0.003 then pos = target end
  render()
  if pos == target and holdDir == 0 and appear >= 1 and vol >= 1 then setTicking(false) end
end

-- ── Clavier ─────────────────────────────────────────────────────────────────

function onKey(chord, pressed)
  -- Champ du nom : Entrée enregistre, Échap revient à la liste ; les lettres vont au champ (aucune n'est capturée)
  if mode == "nom" then
    if not pressed then return end
    if chord == "Escape" then mode, message = "liste", nil; render()
    elseif entree(chord) then enregistrer() end
    return
  end
  if mode == "editeur" then
    if pressed then clavierEditeur(chord) end
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
  elseif chord == "Home" then aller(target - (wrap(target) - 1))
  elseif chord == "End" then aller(target + (#cartes - wrap(target)))
  elseif entree(chord) then activer(c)
  elseif chord == "shift+Delete" or chord == "Shift+Delete" then
    if c and not c.nouvelle then mode, message = "confirmer", nil; render() end
  elseif chord == "e" or chord == "E" then   -- seulement si Noctalia la transmet (non capturée) ; sinon clic droit
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
  mode, nomSaisi, message, edNom, vol = "liste", "", nil, nil, 1
  voulu = texte(context)   -- nom facultatif à centrer : panel-toggle nc/sessions:main "Dev"
  bg, fondTranche = nil, nil
  local o = currentOutput()
  local fond = noctalia.wallpaperPath(o and o.name or "")
  if fond then
    local base = THUMBS .. (string.match(fond, "([^/]+)$") or "")
    if noctalia.fileExists(base .. ".B.webp") then bg = base .. ".B.webp" end
    -- Tranches du fond courant (carrousel des fonds) : celles de « Nouvelle session » en attendant l'écran en direct
    if noctalia.fileExists(base .. ".W.webp") and noctalia.fileExists(base .. ".N.webp") then
      fondTranche = { large = base .. ".W.webp", etroite = base .. ".N.webp" }
    end
  end
  if charge then construire() end   -- la liste d'avant tout de suite, relue juste après
  eco = noctalia.fileExists(ECO)
  appear = eco and 1 or 0
  ticking = false
  if not eco then setTicking(true) end
  ouvert = true
  recharger()
  lireActuel()   -- avant la première image : la tranche de « Nouvelle session » est déjà attendue (pas de saut)
  render()
end

function onClose()
  holdDir = 0
  mode, edNom, vol = "liste", nil, 1
  oublierActuel()
  setTicking(false)
end

-- Touches simulées (tests, raccourcis) : noctalia msg plugin nc/sessions:main all key Right
function onIpc(event, payload)
  if event == "key" and payload then onKey(payload, true); onKey(payload, false) end
end

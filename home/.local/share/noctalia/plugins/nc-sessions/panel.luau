-- nc/sessions (Noctalia v5) : les sessions enregistrées (nc-session) dans un carrousel, comme un sélecteur d'applis.
-- Une carte par session (son aperçu, sinon le dessin de ses fenêtres, une rangée par bureau), puis « + Nouvelle
-- session ». Cartes plates, au ratio de la zone utile de l'écran actif (sans la barre), coins arrondis de 10 : la
-- choisie grande au centre (environ 46 % du cadre) avec un contour blanc de 1,5 point, ses voisines plus petites (0,72)
-- et à 60 %. Sous la carte choisie :
-- pastille, icône, nom, « Modifier », « N fenêtres · date », icônes des applis, puis une ligne d'aide.
-- Gauche/Droite ou molette (maintenir une flèche pour défiler), clic sur une voisine pour la centrer ; la bande boucle
-- dès 3 cartes. Entrée ou clic sur la carte du milieu : ouvrir la session (ou nommer la nouvelle) ; Maj + Suppr : la
-- supprimer, après confirmation ; « Modifier » : l'éditeur, un volet à droite de la carte ; Échap : fermer.
-- Aucune lettre n'est capturée (plugin.toml) : elles vont toujours au champ qui a le focus, et onKey ne reçoit que les
-- touches capturées (donc pas E). Pas de clic droit sur une carte : l'API 32 ne le prend que sur ui.button (ni
-- ui.image, ni ui.box, ni ui.row, ni ui.column : « has no prop 'onRightClick', ignored »).
-- Données : seulement nc-session (json, ouvrir, enregistrer, supprimer…), jamais ses fichiers.
-- Aperçus : faits UNE fois par nc-session (enregistrer, apercu), à la taille exacte de la carte choisie en pixels
-- physiques, sous la barre : rien n'est calculé ni converti à l'ouverture, l'image s'affiche à 1:1 ; les voisines
-- reprennent la même image, réduite à l'affichage. Seule « Nouvelle session » prend l'écran en direct (grim, au même
-- format), en attendant le dessin des fenêtres ouvertes. Avant chaque ui.image, noctalia.fileExists : un fichier absent
-- donne le dessin, jamais une image cassée ; seules les cartes visibles (la choisie et 2 de chaque côté) sont dessinées.
-- Même cadre que le carrousel des fonds : dessiné pour un écran de 1600 x 1000 points, réduit sur un plus petit, agrandi
-- sur un plus grand ; fond flou du fond d'écran courant (miniature de nc-carousel-thumbs).
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
-- INFO : sous la carte choisie, son nom, ses fenêtres, ses applis, puis la ligne d'aide (écran de 1600 x 1000 points)
local BASE = { BGW = 1560, BGH = 940, INFO = 150, GAP = 24 }
local PART_CARTE = 0.46        -- largeur de la carte choisie : part de la largeur de l'écran (même valeur que nc-session)
local ECHELLE_VOISINE = 0.72   -- voisines : plus petites…
local OPACITE_VOISINE = 0.6    -- … et à 60 %
local VISIBLES = 2             -- cartes dessinées de chaque côté de la choisie
local CW, CH = 736, 441        -- carte choisie (setZoom : largeurCarte, hauteurCarte)
local INFO_H = BASE.INFO
local GAP = BASE.GAP           -- entre deux cartes
local Z = 1
local ROW_H = CH + 30
local SMOOTH_MS = 55
local REPEAT_DELAY = 280
local REPEAT_EVERY = 115
local FADE_MS = 260
-- Présent en mode Économie : pas d'animation. Le dossier de Noctalia, comme lui et comme nc-profile-sync qui l'écrit :
-- NOCTALIA_CONFIG_HOME, puis XDG_CONFIG_HOME, puis ~/.config
local ECO = (env("NOCTALIA_CONFIG_HOME") or env("XDG_CONFIG_HOME") or noctalia.expandPath("~/.config"))
  .. "/noctalia/zz-economie.toml"
local eco = false
-- Cadre du carrousel des fonds (mesuré) : sous la barre (36 + 6), à 8 points des bords, coins arrondis de 10
local HAUT_BARRE, BORD, HAUT_PANNEAU, RAYON = 42, 8, 65, 10
local BGW, BGH = BASE.BGW, BASE.BGH
local MAX_APPLIS = 8
local MAX_BUREAUX = 4
local BOUCLE_MIN = 3  -- la bande boucle à partir de 3 cartes
-- Avant d'enregistrer depuis le carrousel : attendre que le calque du panneau ait disparu (2 s au plus, comme
-- nc-shell-msg), pour que ni le panneau ni sa fermeture ne soient dans l'aperçu
local ATTENTE_PANNEAU = 'i=0; while [ "$i" -lt 8 ] && hyprctl layers 2>/dev/null | grep -q "namespace: noctalia-panel"; '
  .. 'do sleep 0.25; i=$((i + 1)); done; '

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

-- ── Taille de la carte choisie et zone de l'aperçu ──────────────────────────
-- MÊME FORMULE que nc-session (largeur_carte, hauteur_carte, zone_utile, zone_capture ; un test vérifie qu'elles
-- concordent), en points logiques de l'écran actif :
--   largeur = plancher(0,46 x largeur de l'écran + 0,5)
--   hauteur = plancher(largeur x hauteur de la zone utile / largeur de la zone utile + 0,5)
-- La zone utile : l'écran sans ses zones réservées (la barre). La carte en prend le ratio, et l'aperçu est la zone
-- utile ENTIÈRE, sans rien couper (une fenêtre collée au bord gauche ou droit reste dans l'aperçu), réduite par grim
-- (-s) à la largeur de la carte en pixels physiques (largeur x échelle, arrondie) ; affichée à 1:1.
-- Chez l'utilisateur (1600 x 1000 à l'échelle 1,6, barre de 42) : zone 1600 x 958, carte 736 x 441, 1178 pixels.
local function arrondi(v) return math.floor(v + 0.5) end
local function entier(v)   -- int() de Python : vers zéro
  v = tonumber(v) or 0
  return v >= 0 and math.floor(v) or -math.floor(-v)
end
local function largeurCarte(w) return arrondi(PART_CARTE * w) end
local function hauteurCarte(w, uw, uh) return arrondi(largeurCarte(w) * uh / uw) end

-- Zone utile d'un écran de hyprctl -j monitors : { w, h (l'écran en points), x, y (son coin), zx, zy, uw, uh (la zone
-- utile) } ; nil s'il est illisible. Sans « reserved » (ou mal formé, ou plus grand que l'écran), l'écran entier.
local function zoneUtile(m)
  if type(m) ~= "table" then return nil end
  local e = tonumber(m.scale) or 1
  if e == 0 then e = 1 end
  local w, h = tonumber(m.width), tonumber(m.height)
  if not w or not h then return nil end
  if entier(m.transform) % 2 == 1 then w, h = h, w end   -- écran tourné d'un quart
  w, h = arrondi(w / e), arrondi(h / e)
  if w <= 0 or h <= 0 then return nil end
  local x, y = entier(m.x), entier(m.y)
  local g, haut, d, bas = 0, 0, 0, 0
  local r = m.reserved
  if type(r) == "table" and #r == 4 and tonumber(r[1]) and tonumber(r[2]) and tonumber(r[3]) and tonumber(r[4]) then
    g, haut, d, bas = math.max(0, entier(r[1])), math.max(0, entier(r[2])), math.max(0, entier(r[3])), math.max(0, entier(r[4]))
  end
  local uw, uh = w - g - d, h - haut - bas
  if uw <= 0 or uh <= 0 then g, haut, uw, uh = 0, 0, w, h end
  return { w = w, h = h, x = x, y = y, e = e, zx = x + g, zy = y + haut, uw = uw, uh = uh }
end

-- Région « X,Y LxH » de grim -g et facteur de grim -s : la zone utile entière, réduite à la largeur de la carte
local function zoneCapture(m)
  local z = zoneUtile(m)
  if not z then return nil end
  local pixels = arrondi(largeurCarte(z.w) * z.e)
  local facteur = math.ceil(pixels / z.uw * 1e6) / 1e6   -- grim tronque : arrondi au-dessus, jamais un pixel de moins
  return string.format("%d,%d %dx%d", z.zx, z.zy, z.uw, z.uh), string.format("%.6f", facteur)
end

-- Zone utile connue de chaque écran (nom → { w, uw, uh }), lue par hyprctl à chaque ouverture et gardée pour la suivante ;
-- avant la première lecture, l'écran sans la barre du haut (HAUT_BARRE)
local zonesConnues = {}

-- Tailles pour l'écran courant (zoom du texte comme nc/carousel ; cartes : largeurCarte, hauteurCarte)
local function setZoom()
  local o = currentOutput()
  local z = o and math.max(0.6, math.min(1, o.width / 1600, o.height / 1000)) or 1
  if o and (o.width > 1600 or o.height > 1000) then z = math.max(1, math.min(2, o.width / 1600, o.height / 1000)) end
  Z = z
  INFO_H, GAP = px(BASE.INFO), px(BASE.GAP)
  local w, h = 1600, 1000
  if o and o.width > 0 and o.height > 0 then w, h = o.width, o.height end
  local zu = o and zonesConnues[o.name]
  local uw, uh = w, math.max(1, h - HAUT_BARRE)
  if zu and zu.w == w then uw, uh = zu.uw, zu.uh end
  CW, CH = largeurCarte(w), hauteurCarte(w, uw, uh)
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
-- Les cartes d'après la liste ; la carte centrée garde sa place (après une suppression, celle qui la suit)
local function construire()
  local avant = #cartes
  local i = avant > 0 and (((target - 1) % avant) + 1) or 1
  cartes = {}
  for _, s in ipairs(sessions) do table.insert(cartes, s) end
  table.insert(cartes, { nouvelle = true })
  local t = math.max(1, math.min(i, #cartes))
  if voulu then
    for k, c in ipairs(cartes) do if c.nom == voulu then t = k end end
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

-- Supprimer : pendant la suppression, la carte n'a plus d'image (son fichier s'efface) ; une fois faite, la session
-- est retirée de la liste AVANT le rendu suivant (la carte supprimée n'est plus jamais dessinée), puis la liste relue
local function supprimer(s)
  mode = "attente"
  s.supprimee = true
  render()
  noctalia.runAsync({ NC, "supprimer", s.nom }, function(r)
    mode = "liste"
    if r and r.exitCode == 0 then
      message = nil
      local reste = {}
      for _, x in ipairs(sessions) do if x ~= s and x.nom ~= s.nom then table.insert(reste, x) end end
      sessions = reste
      construire()
      recharger()
    else
      s.supprimee = nil
      erreur(r, "La session n'a pas pu être supprimée", "The session couldn't be deleted")
    end
    render()
  end, 10000)
end

local function existe(nom)
  for _, s in ipairs(sessions) do if s.nom == nom then return true end end
  return false
end

-- La règle de nc-session ([\w][\w .\-]{0,39}), vérifiée avant de fermer le panneau : lettres et chiffres (accentués
-- compris), espaces, - . _ ; pas d'espace, de point ni de tiret en tête ; 40 caractères au plus. nc-session la
-- vérifie de nouveau (et notifie un refus).
local function nomAccepte(nom)
  if string.find(nom, "%c") then return false end
  local n = 0
  for car in string.gmatch(nom, "[\1-\127\194-\244][\128-\191]*") do
    n = n + 1
    if #car == 1 and not string.match(car, "[%w_]") and not (n > 1 and string.match(car, "[ .%-]")) then return false end
  end
  return n >= 1 and n <= 40
end

-- Enregistrer : le panneau se ferme d'abord, nc-session prend l'aperçu une fois son calque disparu (sinon le panneau
-- serait dans l'image) ; sa notification arrive après la capture
local function enregistrer()
  local nom = noctalia.string.trim(nomSaisi or "")
  if nom == "" then return end
  if not nomAccepte(nom) then
    message, messageErreur = tr("Nom de session : lettres, chiffres, espaces, - . _ (40 au plus).",
      "Session name: letters, digits, spaces, - . _ (40 at most)."), true
    render()
    return
  end
  mode, message, nomSaisi = "liste", nil, ""
  panel.close()
  noctalia.runAsync({ "sh", "-c", ATTENTE_PANNEAU .. 'exec "$0" enregistrer "$1"', NC, nom })
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

-- Une image seulement si son fichier est là (noctalia.fileExists) : sinon le dessin, jamais « image failed to load »
local function fichierImage(p)
  p = texte(p)
  return p and noctalia.fileExists(p) and p or nil
end

local function apercu(s)
  if not s or s.supprimee then return nil end   -- en cours de suppression : son fichier s'efface
  return fichierImage(s.apercu)
end

-- Carte plate : fond de verre (surface à 55 %, visible sous un dessin), le contenu par-dessus (couches de la taille
-- de la carte, superposées par une marge négative), et pour la carte choisie seulement un contour blanc de 1,5 point
-- (comme le liseré de la tranche choisie du carrousel des fonds). Coins arrondis de 10.
local function cartePlate(props, w, h, couches, choisie)
  local l = { ui.box({ width = w, height = h, radius = RAYON, fill = "surface/0.55" }) }
  for _, c in ipairs(couches) do table.insert(l, c) end
  if choisie then
    table.insert(l, ui.box({ width = w, height = h, radius = RAYON, fill = "#00000000", border = "#ffffff", borderWidth = 1.5 }))
  end
  props.width, props.height, props.gap = w, h, -h
  props.align, props.justify = "start", "start"
  return ui.column(props, l)
end

-- Une couche : contenu centré, aux marges de la carte
local function couche(w, h, kids, marge, align)
  return ui.column({ width = w, height = h, justify = "center", align = align or "center", paddingH = marge or 0,
    gap = px(10) }, kids)
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
-- À l'ouverture, en asynchrone : hyprctl -j monitors (l'écran du panneau, ses zones réservées), puis grim au format
-- des aperçus des sessions (zoneCapture : sous la barre, à la taille exacte de la carte) vers un fichier .tmp de
-- $XDG_RUNTIME_DIR, renommé d'un coup une fois écrit (jamais une image à moitié lue) ; et hyprctl -j clients (les
-- fenêtres ouvertes, et le dessin de celles du bureau actif). En attendant l'image, ou sans capture
-- (SESSIONS_CAPTURE=non, grim absent), le dessin ; l'image le remplace dans le rappel. Effacée à la fermeture.
local direct = nil        -- image prête (renommée, vérifiée)
local aEffacer = {}       -- fichiers temporaires de cette ouverture
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
  noctalia.runAsync({ "hyprctl", "-j", "monitors" }, function(r)
    if rangO ~= ouverture or not ouvert then return end
    local moniteurs = r and r.exitCode == 0 and noctalia.json.decode(r.stdout or "") or nil
    if type(moniteurs) ~= "table" then moniteurs = nil end
    -- L'écran du panneau (sinon celui qui a le focus)
    local m = nil
    for _, x in ipairs(moniteurs or {}) do
      if type(x) == "table" and o and x.name == o.name then m = x end
    end
    if not m then
      for _, x in ipairs(moniteurs or {}) do if type(x) == "table" and x.focused then m = x end end
    end
    local zu = zoneUtile(m)
    if zu and o and m.name == o.name then         -- l'écran du panneau lui-même (pas celui qui a le focus, à défaut)
      zonesConnues[o.name] = { w = zu.w, uw = zu.uw, uh = zu.uh }
      local cw, ch = CW, CH
      setZoom()                                  -- la carte au ratio exact de la zone utile
      if cw ~= CW or ch ~= CH then render() end
    end
    local zone, facteur = zoneCapture(m)
    if capture and zone then
      local dir = env("XDG_RUNTIME_DIR") or "/tmp"
      local f = dir .. "/nc-sessions-direct-" .. rangO .. "-" .. tostring(noctalia.nowMs and noctalia.nowMs() or 0) .. ".png"
      aEffacer = { f, f .. ".tmp" }
      noctalia.runAsync({ "sh", "-c", 'command -v grim >/dev/null 2>&1 || exit 3; umask 077; '
        .. 'grim -g "$1" -s "$2" -t png "$0.tmp" && exec mv -f "$0.tmp" "$0"', f, zone, facteur }, function(r2)
        if rangO ~= ouverture or not ouvert then
          noctalia.runAsync({ "rm", "-f", f, f .. ".tmp" })     -- fermé entre-temps
          return
        end
        if r2 and r2.exitCode == 0 and noctalia.fileExists(f) then direct = f end
        render()
      end, 5000)
    end
    noctalia.runAsync({ "hyprctl", "-j", "clients" }, function(r3)
      if rangO ~= ouverture or not ouvert then return end
      actuel = r3 and r3.exitCode == 0 and lireClients(r3.stdout, moniteurs) or nil
      render()
    end, 3000)
  end, 3000)
end

local function oublierActuel()
  ouvert = false
  ouverture = ouverture + 1
  direct, actuel = nil, nil
  if #aEffacer > 0 then
    local argv = { "rm", "-f" }
    for _, f in ipairs(aEffacer) do table.insert(argv, f) end
    noctalia.runAsync(argv)
  end
  aEffacer = {}
end

-- ── Ligne d'info sous la carte ──────────────────────────────────────────────
-- « Modifier » : ouvre l'éditeur de la session
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

-- Carte « Nouvelle session » : l'écran actuel (image en direct, sinon le dessin des fenêtres du bureau actif), et
-- un « + » dans un rond de verre au milieu
local function carteNouvelle(idx, w, h, choisie, a, clic)
  local couches = {}
  local img = fichierImage(direct)
  if img then
    table.insert(couches, ui.image({ key = "direct", path = img, width = w, height = h, fit = "cover", radius = RAYON }))
  elseif actuel and actuel.schema and #actuel.schema.rects > 0 then
    local M = math.floor(px(24) * w / CW)
    local sh = h - 2 * M
    local sw = math.min(w - 2 * M, math.floor(sh * actuel.schema.largeur / math.max(1, actuel.schema.hauteur)))
    table.insert(couches, couche(w, h, { ecranSchema(actuel.schema, sw, sh, "primary") }))
  end
  table.insert(couches, couche(w, h, { plus(math.floor(px(72) * w / CW)) }))
  return cartePlate({ key = "c" .. idx, opacity = a, onClick = clic }, w, h, couches, choisie)
end

-- Carte d'une session : son aperçu remplit la carte (le même fichier pour la choisie et ses voisines, réduit à
-- l'affichage) ; sans aperçu, le dessin de ses fenêtres
local function carteSession(c, idx, w, h, choisie, a, clic)
  local img = apercu(c)
  local couches = {}
  if img then
    table.insert(couches, ui.image({ key = "i" .. idx, path = img, width = w, height = h, fit = "cover", radius = RAYON }))
  else
    local M = math.floor(px(24) * w / CW)
    table.insert(couches, couche(w, h, schema(c, w, h, couleur(c)), M, "start"))
  end
  return cartePlate({ key = "c" .. idx, opacity = a, onClick = clic }, w, h, couches, choisie)
end

-- Une carte de la bande ; choisie : celle du milieu
local function carte(c, idx, w, h, choisie, a)
  local clic = function()
    if idx == target then
      if mode ~= "editeur" then activer(c) end   -- éditeur ouvert : un clic sur sa carte n'ouvre pas la session
    else
      aller(idx)
    end
  end
  if c.nouvelle then return carteNouvelle(idx, w, h, choisie, a, clic) end
  return carteSession(c, idx, w, h, choisie, a, clic)
end

-- Bande de cartes, comme un sélecteur d'applis : la choisie au centre, ses voisines à ECHELLE_VOISINE et
-- OPACITE_VOISINE ; la taille et l'opacité suivent la distance (continue) au centre, pour un glissement doux. Seules
-- la choisie et VISIBLES cartes de chaque côté sont dessinées (en boucle, jamais deux fois la même). decal : la carte
-- du milieu glisse d'autant vers la gauche (éditeur ouvert).
local function bande(decal)
  local n = #cartes
  local enBoucle = boucle()
  local reach = enBoucle and math.min(VISIBLES, math.max(1, math.floor((n - 1) / 2))) or VISIBLES
  local c = math.floor(pos + 0.5)
  local fl = math.floor(pos)
  local kids, centres, x = {}, {}, 0
  local de, a_ = c - reach, c + reach
  if not enBoucle then de, a_ = math.max(1, de), math.min(n, a_) end
  for idx = de, a_ do
    local t = math.min(math.abs(idx - pos), 1)
    local k = lerp(1, ECHELLE_VOISINE, t)
    local w, h = CW * k, CH * k
    centres[idx] = x + w / 2
    table.insert(kids, ui.row({ key = "r" .. idx, width = w, height = ROW_H, align = "center", justify = "center" }, {
      carte(cartes[wrap(idx)], idx, w, h, idx == c, lerp(1, OPACITE_VOISINE, t)),
    }))
    x = x + w + GAP
  end
  -- Amène « pos » au centre (moins decal) : la bande est centrée, une boîte vide d'un côté la décale
  local largeur = x - GAP
  local p0 = centres[fl] or centres[c] or largeur / 2
  local p = lerp(p0, centres[fl + 1] or p0, pos - fl)
  local s = largeur / 2 - p - (decal or 0)
  if s > 0 then
    table.insert(kids, 1, vide(2 * s - GAP, 1))
  elseif s < 0 then
    table.insert(kids, vide(-2 * s - GAP, 1))
  end
  return ui.row({ height = ROW_H, width = largeur + 2 * math.abs(s) + 60, align = "center", justify = "center", gap = GAP }, kids)
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

-- Sous la carte choisie. Session : pastille, icône, nom, « Modifier » ; puis fenêtres, date, applis.
-- « Nouvelle session » : le « + », le titre, puis le champ du nom ou les fenêtres ouvertes.
local function titreSous(c)
  local L = math.min(BGW - 2 * px(24), CW + px(200))
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

local function hauteurInfo() return INFO_H end

local function legende()
  local c = courante()
  local kids = {}
  if not c then return ui.column({ height = hauteurInfo() }, {}) end
  local ECHAP = tr("Échap", "Esc")
  table.insert(kids, titreSous(c))
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
    -- E n'arrive pas au panneau (non capturée : les lettres vont aux champs) et le clic droit n'existe que sur un
    -- ui.button : seul le bouton « Modifier », à côté du nom, ouvre l'éditeur
    table.insert(kids, ligneAide({ { "↵", tr("ouvrir", "open") }, { tr("Maj", "Shift"), tr("Suppr", "Del"), tr("supprimer", "delete") },
      { ECHAP, tr("fermer", "close") } }))
  end
  if message and not (c.nouvelle and (mode == "nom" or mode == "attente")) then table.insert(kids, phrase(message, messageErreur and "error" or "primary")) end
  return ui.column({ height = hauteurInfo(), width = BGW, align = "center", justify = "start", gap = px(10),
    paddingV = px(10) }, kids)
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

-- Point d'entrée (bouton « Modifier »)
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
-- qu'elle ne passe pas sous le volet : environ 30 points en 1600 x 1000 comme en 1280 x 800 (carte au ratio de la zone utile)
local function placeVolet()
  local VW = px(VOLET_W)
  local largeur = CW
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
  bg = nil
  local o = currentOutput()
  local fond = noctalia.wallpaperPath(o and o.name or "")
  if fond then
    local base = THUMBS .. (string.match(fond, "([^/]+)$") or "")
    if noctalia.fileExists(base .. ".B.webp") then bg = base .. ".B.webp" end
  end
  if charge then construire() end   -- la liste d'avant tout de suite, relue juste après
  eco = noctalia.fileExists(ECO)
  appear = eco and 1 or 0
  ticking = false
  if not eco then setTicking(true) end
  ouvert = true
  recharger()
  lireActuel()   -- « Nouvelle session » : le dessin des fenêtres, puis l'écran en direct dès qu'il est prêt
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

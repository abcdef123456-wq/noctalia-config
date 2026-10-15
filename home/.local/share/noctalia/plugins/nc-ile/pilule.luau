--!nonstrict
-- nc/ile : la pilule (île dynamique) au centre de la barre.
--   Repos : l'heure et la date ; musique en cours : pochette, titre et égaliseur qui danse sur le son.
--   Réactions, comme sur iPhone : la pilule s'étire avec un petit rebond, montre l'événement 2 à 3 s, puis revient :
--   volume, luminosité, nouveau morceau, chargeur branché / débranché, profil d'énergie, mode jeu.
--   Clic : centre de contrôle.  Molette : volume.  Clic droit : lecture / pause.
-- Volume et luminosité arrivent des raccourcis Hyprland (noctalia msg plugin nc/ile:pilule all volume|luminosite) ;
-- le reste est surveillé ici : fichiers du système chaque seconde, lecteur de musique toutes les 2 s.

local sym = require("./symboles.luau")
local ETAT = noctalia.expandPath("~/.local/bin/nc-ile-etat")
local LUM = noctalia.expandPath("~/.local/bin/nc-brightness")
local PROFIL = noctalia.expandPath("~/.config/hypr/nc/profil.lua")
local JEU = (noctalia.getenv("XDG_RUNTIME_DIR") or "/tmp") .. "/nc-mode-jeu"
local JOURS = { "dim.", "lun.", "mar.", "mer.", "jeu.", "ven.", "sam." }
local MOIS = { "janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc." }
local NOMS_PROFIL = { ["power-saver"] = { "feuille", "Économie" }, balanced = { "equilibre", "Équilibré" }, performance = { "eclair", "Performance" } }
-- Couleurs façon Apple (mode sombre) : île noir pur, texte blanc, gris secondaire, vert système
local NOIR, BLANC, GRIS, PISTE, VERT = "#000000", "#ffffff", "#98989d", "#3a3a3c", "#30d158"
local BARRES = 5
local CAR = 7.4            -- largeur moyenne d'un caractère dans la barre (px), pour estimer la taille du contenu

local media = nil          -- musique en cours, ou nil
local spectre = {}         -- hauteurs 0..1 de l'égaliseur
local activite = nil       -- réaction en cours : { genre, …, fin = ms }
local batterie, etatBatterie, profil, jeu = nil, nil, nil, nil
local dernierMedia, derniereSeconde = 0, 0

-- Animation : largeur en ressort (avec rebond), contenu qui s'efface puis réapparaît à chaque changement
local largeur, vitesse, opacite = nil, 0, 1
-- Liaison avec le centre de contrôle (l'île ouverte) : la pilule s'efface pendant qu'il est ouvert, réapparaît
-- quand il se rétracte ; sa largeur est publiée pour que l'île naisse exactement à sa taille
local ileOuverte = false
local presence, publiee = 1, 0
local signature = ""

local function maintenant() return noctalia.nowMs() end

local function longueur(s)
  return (utf8 and utf8.len(s or "")) or #(s or "")
end

local function texte(s, max)
  return math.min(longueur(s) * CAR, max or 1000)
end

-- ── Contenu de la pilule : renvoie (enfants, largeur estimée, signature) ─────

local function egaliseur()
  local barres = {}
  for i = 1, BARRES do
    table.insert(barres, ui.box({ width = 3, height = math.max(3, math.floor(3 + (spectre[i] or 0) * 13)), radius = 2, fill = "primary" }))
  end
  return ui.row({ gap = 2, align = "center", height = 16 }, barres)
end

local function repos()
  local t = os.date("*t")
  local heure = string.format("%02d:%02d", t.hour, t.min)
  if media then
    -- Comme l'iPhone : pochette à gauche, onde sonore à droite ; l'heure au milieu (et le titre en pause)
    local joue = media.etat == "Playing"
    local p = media.pochette
    local gauche = (p ~= "" and noctalia.fileExists(p))
      and ui.image({ key = "pochette", path = p, width = 20, height = 20, radius = 6, fit = "cover" })
      or sym.image("note", BLANC, 15)
    local milieu = { ui.label({ text = heure, fontWeight = "semibold", color = BLANC }) }
    local l = 20 + texte(heure) + 9
    if not joue then
      table.insert(milieu, ui.label({ text = media.titre, maxWidth = 150, maxLines = 1, color = GRIS }))
      l += texte(media.titre, 150) + 8
    end
    local droite = joue and egaliseur() or sym.image("lecture", GRIS, 13)
    l += joue and (BARRES * 5) or 12
    return { gauche, ui.row({ gap = 8, align = "center", flexGrow = 1, justify = "center" }, milieu), droite },
      l + 40, "media:" .. media.titre .. media.etat
  end
  local date = JOURS[t.wday] .. " " .. t.day .. " " .. MOIS[t.month]
  return {
    ui.label({ text = heure, fontWeight = "semibold", color = BLANC }),
    ui.label({ text = date, color = GRIS }),
  }, texte(heure) + texte(date) + 9, "repos"
end

local function jauge(icone, valeur, couleur)
  return {
    sym.image(icone, couleur or BLANC, 17),
    ui.progress({ width = 130, height = 6, radius = 3, progress = math.max(0, math.min(1, valeur / 100)), fill = couleur or BLANC, track = PISTE }),
    ui.label({ text = valeur .. " %", fontWeight = "semibold", width = 42, textAlign = "end", color = BLANC }),
  }, 16 + 130 + 42 + 2 * 9
end

local function reaction()
  local a = activite
  if a.genre == "volume" then
    local e, l = jauge(a.muet and "muet" or "haut-parleur", a.valeur, a.muet and GRIS or nil)
    return e, l, "volume"
  elseif a.genre == "luminosite" then
    local e, l = jauge("soleil", a.valeur)
    return e, l, "luminosite"
  elseif a.genre == "piste" then
    local enfants = {}
    if a.pochette ~= "" and noctalia.fileExists(a.pochette) then
      table.insert(enfants, ui.image({ key = "pochette-r", path = a.pochette, width = 22, height = 22, radius = 6, fit = "cover" }))
    else
      table.insert(enfants, sym.image("note", BLANC, 16))
    end
    table.insert(enfants, ui.label({ text = a.titre, maxWidth = 190, maxLines = 1, fontWeight = "semibold", color = BLANC }))
    local l = 24 + texte(a.titre, 190) + 9
    if a.artiste ~= "" then
      table.insert(enfants, ui.label({ text = a.artiste, maxWidth = 130, maxLines = 1, color = GRIS }))
      l += texte(a.artiste, 130) + 9
    end
    return enfants, l, "piste:" .. a.titre
  elseif a.genre == "charge" then
    local t = (a.branche and "En charge · " or "Sur batterie · ") .. (batterie or "?") .. " %"
    return {
      ui.glyph({ name = a.branche and "battery-charging" or "battery-2", size = 17, color = a.branche and VERT or BLANC }),
      ui.label({ text = t, fontWeight = "semibold", color = a.branche and VERT or BLANC }),
    }, 17 + texte(t) + 9, "charge" .. tostring(a.branche)
  elseif a.genre == "profil" then
    local n = NOMS_PROFIL[a.profil] or { "equilibre", a.profil }
    return {
      sym.image(n[1], a.profil == "power-saver" and VERT or (a.profil == "performance" and "#ff9f0a" or BLANC), 17),
      ui.label({ text = n[2], fontWeight = "semibold", color = BLANC }),
    }, 16 + texte(n[2]) + 9, "profil" .. a.profil
  elseif a.genre == "jeu" then
    local t = a.actif and "Mode jeu" or "Mode jeu désactivé"
    return {
      sym.image("manette", a.actif and "#ff9f0a" or GRIS, 18),
      ui.label({ text = t, fontWeight = "semibold", color = BLANC }),
    }, 17 + texte(t) + 9, "jeu" .. tostring(a.actif)
  end
  return repos()
end

-- ── Rendu et animation ──────────────────────────────────────────────────────

local function animer(actif)
  noctalia.setUpdateInterval(actif and 16 or 1000)
end

function rendre()
  if activite and maintenant() > activite.fin then activite = nil end
  local enfants, cible, sig
  if activite then enfants, cible, sig = reaction() else enfants, cible, sig = repos() end
  cible = math.floor(cible + 28)                       -- marges intérieures
  if sig ~= signature then                             -- nouveau contenu : il s'efface puis réapparaît
    signature = sig
    if largeur then opacite = 0 end
  end
  largeur = largeur or cible
  -- Ressort amorti : rapide, avec un léger dépassement (rebond) avant de se poser
  local ecart = cible - largeur
  vitesse = vitesse * 0.62 + ecart * 0.26
  largeur += vitesse
  if math.abs(ecart) < 0.5 and math.abs(vitesse) < 0.5 then largeur, vitesse = cible, 0 end
  if opacite < 1 then opacite = math.min(1, opacite + 0.09) end
  -- Présence de la pilule : effacée très vite quand l'île s'ouvre, revient en douceur quand elle se referme
  if ileOuverte and presence > 0 then presence = math.max(0, presence - 0.34)
  elseif not ileOuverte and presence < 1 then presence = math.min(1, presence + 0.12) end
  if not ileOuverte and math.abs(largeur - publiee) > 0.5 and largeur == cible then
    publiee = largeur
    noctalia.state.set("ile-largeur", math.floor(largeur))
  end
  animer(largeur ~= cible or opacite < 1 or (presence > 0 and presence < 1) or activite ~= nil or (media ~= nil and media.etat == "Playing"))
  -- La pilule : noir pur, entièrement arrondie, sans contour (la pastille de la barre est désactivée pour elle)
  barWidget.render(ui.row({ width = math.floor(largeur), height = 30, radius = 15, fill = NOIR, paddingH = 14, align = "center",
    opacity = presence }, {
    ui.row({ flexGrow = 1, gap = 9, align = "center", justify = "center", opacity = opacite }, enfants),
  }))
end

local function reagir(a, duree)
  a.fin = maintenant() + (duree or 2200)
  activite = a
  rendre()
end

-- ── Sources d'événements ────────────────────────────────────────────────────

local function lireMedia()
  dernierMedia = maintenant()
  noctalia.runAsync({ ETAT, "media" }, function(r)
    local t = {}
    for k, v in string.gmatch(r.stdout or "", "([%w_]+)=([^\n]*)") do t[k] = v end
    local avant = media
    if t.media == "1" and t.media_etat ~= "Stopped" then
      media = { etat = t.media_etat, titre = t.media_titre or "", artiste = t.media_artiste or "",
        pochette = t.media_pochette or "", duree = tonumber(t.media_duree) or 0, position = tonumber(t.media_position) or 0 }
    else
      media = nil
    end
    noctalia.state.set("media", media)
    -- Nouveau morceau qui joue : la pilule le présente
    if media and media.etat == "Playing" and media.titre ~= "" and (not avant or avant.titre ~= media.titre) then
      reagir({ genre = "piste", titre = media.titre, artiste = media.artiste, pochette = media.pochette }, 3200)
    end
    rendre()
  end, 3000)
end

local function surveiller()
  -- Chargeur
  local dir = noctalia.listDir("/sys/class/power_supply") or {}
  for _, n in ipairs(dir) do
    if string.sub(n, 1, 3) == "BAT" then
      local st = noctalia.readFile("/sys/class/power_supply/" .. n .. "/status")
      local cap = noctalia.readFile("/sys/class/power_supply/" .. n .. "/capacity")
      batterie = tonumber(noctalia.string.trim(cap or "")) or batterie
      st = noctalia.string.trim(st or "")
      local branche = st ~= "Discharging"
      if etatBatterie ~= nil and branche ~= etatBatterie then reagir({ genre = "charge", branche = branche }) end
      etatBatterie = branche
      break
    end
  end
  -- Profil d'énergie (écrit par nc-profile-sync) et mode jeu
  local p = string.match(noctalia.readFile(PROFIL) or "", 'profil%s*=%s*"([%a-]+)"')
  if p and profil and p ~= profil and not (activite and activite.genre == "jeu") then reagir({ genre = "profil", profil = p }) end
  profil = p or profil
  local j = noctalia.fileExists(JEU)
  if jeu ~= nil and j ~= jeu then reagir({ genre = "jeu", actif = j }) end
  jeu = j
end

local function lireVolume()
  noctalia.runAsync({ "wpctl", "get-volume", "@DEFAULT_AUDIO_SINK@" }, function(r)
    local v = tonumber(string.match(r.stdout or "", "([%d.]+)"))
    if v then reagir({ genre = "volume", valeur = math.floor(v * 100 + 0.5), muet = string.find(r.stdout, "MUTED") ~= nil }) end
  end, 2000)
end

local function lireLuminosite()
  noctalia.runAsync({ LUM, "get" }, function(r)
    local v = tonumber(noctalia.string.trim(r.stdout or ""))
    if v then reagir({ genre = "luminosite", valeur = v }) end
  end, 2000)
end

-- ── Entrées de Noctalia ─────────────────────────────────────────────────────

function onIpc(evenement)
  if evenement == "volume" then lireVolume()
  elseif evenement == "luminosite" then lireLuminosite()
  elseif evenement == "media" then lireMedia() end
end

function onAudioSpectrum(valeursCsv)
  if not media or media.etat ~= "Playing" then return end
  local v = {}
  for x in string.gmatch(valeursCsv or "", "[^,]+") do table.insert(v, tonumber(x) or 0) end
  if #v == 0 then return end
  local pas = math.max(1, math.floor(#v * 0.6 / BARRES))
  for i = 1, BARRES do
    local s = 0
    for j = 0, pas - 1 do s = math.max(s, v[(i - 1) * pas + j + 1] or 0) end
    spectre[i] = (spectre[i] or 0) * 0.35 + math.min(1, s) * 0.65
  end
end

function update()
  local t = maintenant()
  if t - derniereSeconde >= 1000 then derniereSeconde = t; surveiller() end
  if t - dernierMedia >= 2000 then lireMedia() end
  rendre()
end

function onClick()
  if ileOuverte then
    noctalia.state.set("ile-commande", { action = "fermer", n = maintenant() })   -- fermeture animée
  else
    noctalia.togglePanel("nc/ile:centre")
  end
end

noctalia.state.watch("ile-ouverte", function(etat)
  ileOuverte = etat == "ouverte"
  rendre()
end)

function onRightClick()
  noctalia.runAsync({ "playerctl", "play-pause" }, function() lireMedia() end, 3000)
end

function onScroll(axe, pas)
  if axe ~= "vertical" then return end
  noctalia.runAsync({ "wpctl", "set-volume", "-l", "1", "@DEFAULT_AUDIO_SINK@", pas < 0 and "5%+" or "5%-" }, function() lireVolume() end, 2000)
end

surveiller()
lireMedia()
rendre()

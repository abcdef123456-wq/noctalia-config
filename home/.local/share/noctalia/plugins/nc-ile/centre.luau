--!nonstrict
-- nc/ile : le centre de contrôle, qui sort de la pilule (il démarre à sa taille et se déploie en ressort).
--   Accueil : heure, batterie, musique, Wi-Fi, Bluetooth, ne pas déranger, lumière de nuit, mode jeu, halo musical,
--             volume, luminosité, profil d'énergie, capture, notifications, réglages, verrouillage, session.
--   Pages   : Wi-Fi (réseaux, mot de passe), Bluetooth (appareils), Son (sorties, micro).
-- État lu par ~/.local/bin/nc-ile-etat à l'ouverture puis toutes les 2 s tant que le panneau est ouvert.

local ETAT = noctalia.expandPath("~/.local/bin/nc-ile-etat")
local LUM = noctalia.expandPath("~/.local/bin/nc-brightness")
local L, H = 470, 612                       -- taille du panneau (plugin.toml)
local JOURS = { "dimanche", "lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi" }
local MOIS = { "janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre" }
local CARTE = "surface_variant/0.55"

local e = {}                                -- état (clé -> texte)
local listes = { net = {}, bt = {}, sortie = {}, entree = {} }
local page = "accueil"
local ouvert, tic = false, 0
local volume, luminosite = nil, nil
local saisie = nil                          -- réseau dont on tape le mot de passe
local enCours = {}                          -- connexions en cours (nom ou adresse -> true)

-- Déploiement depuis la pilule : largeur et hauteur en ressort, contenu en fondu à la fin
local anim = { w = L, h = H, vw = 0, vh = 0, a = 1 }

-- ── Lecture de l'état ───────────────────────────────────────────────────────

local function analyser(texte)
  local t = {}
  for k, v in string.gmatch(texte or "", "([%w_]+)=([^\n]*)") do t[k] = v end
  return t
end

local function analyserListe(texte)
  local l = { net = {}, bt = {}, sortie = {}, entree = {} }
  for k, v in string.gmatch(texte or "", "([%w_]+)=([^\n]*)") do
    if l[k] then
      local champs = {}
      for c in string.gmatch(v .. "\t", "([^\t]*)\t") do table.insert(champs, c) end
      table.insert(l[k], champs)
    end
  end
  return l
end

local function lire()
  noctalia.runAsync({ ETAT }, function(r)
    e = analyser(r.stdout)
    volume = tonumber(e.volume) or volume or 0
    luminosite = tonumber(e.luminosite) or luminosite
    if ouvert then dessiner() end
  end, 4000)
end

local function lirePage()
  local quoi = ({ wifi = "wifi", bluetooth = "bt", son = "son" })[page]
  if not quoi then return end
  noctalia.runAsync({ ETAT, quoi }, function(r)
    local l = analyserListe(r.stdout)
    if quoi == "wifi" then listes.net = l.net
    elseif quoi == "bt" then listes.bt = l.bt
    else listes.sortie, listes.entree = l.sortie, l.entree end
    if ouvert then dessiner() end
  end, 8000)
end

local function faire(argv, apres)
  noctalia.runAsync(argv, function(r)
    if apres then apres(r) end
    lire(); lirePage()
  end, 15000)
end

local function msg(...) faire({ "noctalia", "msg", ... }) end

local function aller(p)
  page = p
  saisie = nil
  anim.a = 0                                -- le nouveau contenu apparaît en fondu
  panel.setNeedsFrameTick(true)
  lirePage()
  dessiner()
end

-- ── Briques ─────────────────────────────────────────────────────────────────

local function titrePage(nom, droite)
  return ui.row({ height = 44, gap = 8, align = "center" }, {
    ui.button({ glyph = "chevron-left", variant = "ghost", controlSize = "sm", onClick = function() aller("accueil") end }),
    ui.label({ text = nom, fontSize = 19, fontWeight = "bold", color = "on_surface", flexGrow = 1 }),
    droite or ui.spacer({ width = 1 }),
  })
end

local function ligne(icone, nom, sous, actif, action, droite)
  return ui.row({ height = 54, flexGrow = 1, gap = 12, paddingH = 14, align = "center", radius = 18,
    fill = actif and "primary/0.18" or CARTE, onClick = action }, {
    ui.glyph({ name = icone, size = 19, color = actif and "primary" or "on_surface" }),
    ui.column({ flexGrow = 1, gap = 1 }, {
      ui.label({ text = nom, fontSize = 13, fontWeight = "semibold", color = "on_surface", maxLines = 1, maxWidth = 290 }),
      ui.label({ text = sous, fontSize = 11, color = actif and "primary" or "on_surface_variant", maxLines = 1 }),
    }),
    droite or ui.spacer({ width = 1 }),
  })
end

local function tuile(icone, titre, sous, actif, action, detail)
  local haut = { ui.glyph({ name = icone, size = 20, color = actif and "on_primary" or "on_surface" }), ui.spacer({ flexGrow = 1 }) }
  if detail then
    table.insert(haut, ui.button({ glyph = "chevron-right", variant = "ghost", controlSize = "sm", height = 26, width = 26, onClick = detail }))
  end
  return ui.column({ flexGrow = 1, height = 78, radius = 20, paddingH = 12, paddingV = 10, gap = 3, justify = "center",
    fill = actif and "primary" or CARTE, onClick = action }, {
    ui.row({ height = 24, align = "center" }, haut),
    ui.label({ text = titre, fontSize = 12, fontWeight = "semibold", color = actif and "on_primary" or "on_surface", maxLines = 1 }),
    ui.label({ text = sous, fontSize = 10, color = actif and "on_primary/0.75" or "on_surface_variant", maxLines = 1, maxWidth = 120 }),
  })
end

local function curseur(icone, valeur, bouton, change, fin, detail)
  valeur = math.floor((valeur or 0) + 0.5)
  local enfants = {
    ui.button({ glyph = icone, variant = "ghost", controlSize = "sm", onClick = bouton }),
    ui.slider({ flexGrow = 1, min = 0, max = 100, step = 1, value = valeur, onChange = change, onDragEnd = fin }),
    ui.label({ text = valeur .. " %", width = 42, fontSize = 12, fontWeight = "semibold", color = "on_surface_variant", textAlign = "end" }),
  }
  if detail then
    table.insert(enfants, ui.button({ glyph = "chevron-right", variant = "ghost", controlSize = "sm", onClick = detail }))
  end
  return ui.row({ gap = 6, align = "center", height = 40, paddingH = 6, radius = 20, fill = CARTE }, enfants)
end

local function curseurVolume(detail)
  local muet = e.muet == "1"
  return curseur(muet and "volume-off" or "volume", volume, function()
    faire({ "wpctl", "set-mute", "@DEFAULT_AUDIO_SINK@", "toggle" })
  end, function(v)
    volume = tonumber(v) or volume
    noctalia.runAsync({ "wpctl", "set-volume", "-l", "1", "@DEFAULT_AUDIO_SINK@", string.format("%.2f", (volume or 0) / 100) })
    dessiner()
  end, function() lire() end, detail)
end

-- ── Accueil ─────────────────────────────────────────────────────────────────

local function entete()
  local t = os.date("*t")
  local bat = tonumber(e.batterie)
  local droite = {}
  if bat then
    local charge = e.batterie_etat ~= "Discharging"
    table.insert(droite, ui.row({ gap = 6, align = "center", paddingH = 12, height = 32, radius = 16, fill = CARTE }, {
      ui.glyph({ name = charge and "battery-charging" or "battery-2", size = 16, color = (bat <= 20 and not charge) and "error" or "primary" }),
      ui.label({ text = bat .. " %", fontSize = 13, fontWeight = "semibold", color = "on_surface" }),
    }))
  end
  return ui.row({ align = "center", gap = 10, height = 64 }, {
    ui.column({ gap = 0, flexGrow = 1 }, {
      ui.label({ text = string.format("%02d:%02d", t.hour, t.min), fontSize = 38, fontWeight = "bold", color = "on_surface" }),
      ui.label({ text = JOURS[t.wday] .. " " .. t.day .. " " .. MOIS[t.month], fontSize = 13, color = "on_surface_variant" }),
    }),
    ui.row({ gap = 6, align = "center" }, droite),
  })
end

local function carteMedia()
  if e.media ~= "1" or e.media_etat == "Stopped" then
    return ui.row({ gap = 12, align = "center", height = 106, paddingH = 12, radius = 22, fill = CARTE }, {
      ui.column({ width = 58, height = 58, radius = 14, fill = "primary/0.18", align = "center", justify = "center" }, {
        ui.glyph({ name = "music", size = 24, color = "primary" }),
      }),
      ui.column({ flexGrow = 1, gap = 2 }, {
        ui.label({ text = "Rien en lecture", fontSize = 15, fontWeight = "bold", color = "on_surface" }),
        ui.label({ text = "Lance une musique : elle s'affichera ici et dans la pilule.", fontSize = 12, color = "on_surface_variant", maxLines = 1, maxWidth = 330 }),
      }),
    })
  end
  local duree = (tonumber(e.media_duree) or 0) / 1000000
  local pos = tonumber(e.media_position) or 0
  local p = e.media_pochette or ""
  local pochette
  if p ~= "" and noctalia.fileExists(p) then
    pochette = ui.image({ key = "pochette-" .. p, path = p, width = 58, height = 58, radius = 14, fit = "cover" })
  else
    pochette = ui.column({ width = 58, height = 58, radius = 14, fill = "primary/0.18", align = "center", justify = "center" }, {
      ui.glyph({ name = "music", size = 24, color = "primary" }),
    })
  end
  local joue = e.media_etat == "Playing"
  return ui.column({ gap = 10, paddingH = 12, paddingV = 12, height = 106, radius = 22, fill = CARTE }, {
    ui.row({ gap = 12, align = "center" }, {
      pochette,
      ui.column({ flexGrow = 1, gap = 2 }, {
        ui.label({ text = e.media_titre or "", fontSize = 15, fontWeight = "bold", color = "on_surface", maxLines = 1, maxWidth = 210 }),
        ui.label({ text = (e.media_artiste or "") .. (joue and "" or "  ·  en pause"), fontSize = 12, color = "on_surface_variant", maxLines = 1, maxWidth = 210 }),
      }),
      ui.row({ gap = 2, align = "center" }, {
        ui.button({ glyph = "player-skip-back-filled", variant = "ghost", controlSize = "sm", onClick = function() faire({ "playerctl", "previous" }) end }),
        ui.button({ glyph = joue and "player-pause-filled" or "player-play-filled", variant = "primary", controlSize = "md",
          onClick = function() faire({ "playerctl", "play-pause" }) end }),
        ui.button({ glyph = "player-skip-forward-filled", variant = "ghost", controlSize = "sm", onClick = function() faire({ "playerctl", "next" }) end }),
      }),
    }),
    ui.progress({ height = 4, radius = 2, progress = duree > 0 and math.min(1, pos / duree) or 0, fill = "primary", track = "on_surface/0.12" }),
  })
end

local function tuiles()
  local wifi, bt, dnd = e.wifi == "on", e.bluetooth == "on", e.dnd == "on"
  local nuit = noctalia.state.get("nuit") == true
  local jeu, halo = e.jeu == "1", e.halo == "1"
  return ui.column({ gap = 8, height = 164 }, {
    ui.row({ gap = 8, height = 78 }, {
      tuile(wifi and "wifi" or "wifi-off", "Wi-Fi", wifi and ((e.reseau ~= "" and e.reseau) or "Activé") or "Coupé", wifi,
        function() msg("wifi-toggle") end, function() aller("wifi") end),
      tuile(bt and "bluetooth" or "bluetooth-off", "Bluetooth", bt and "Activé" or "Coupé", bt,
        function() msg("bluetooth-toggle") end, function() aller("bluetooth") end),
      tuile(dnd and "bell-off" or "bell", "Ne pas déranger", dnd and "Notifications en pause" or "Désactivé", dnd,
        function() msg("notification-dnd-toggle") end),
    }),
    ui.row({ gap = 8, height = 78 }, {
      tuile(nuit and "moon-stars" or "moon", "Lumière de nuit", nuit and "Tons chauds" or "Désactivée", nuit,
        function() noctalia.state.set("nuit", not nuit); msg("nightlight-force-toggle") end),
      tuile("device-gamepad-2", "Mode jeu", jeu and "Effets coupés" or "Désactivé", jeu,
        function() faire({ "hyprctl", "eval", "nc.mode_jeu()" }) end),
      tuile("wave-sine", "Halo musical", halo and "Suit les basses" or "Coupé", halo,
        function() faire({ "systemctl", "--user", halo and "stop" or "start", "nc-pouls" }) end),
    }),
  })
end

local function curseurs()
  local enfants = { curseurVolume(function() aller("son") end) }
  if luminosite then
    table.insert(enfants, curseur("brightness-half", luminosite, nil, function(v)
      luminosite = tonumber(v) or luminosite
      noctalia.runAsync({ LUM, "set", tostring(math.max(1, math.floor(luminosite))) })
      dessiner()
    end, function() lire() end))
  end
  return ui.column({ gap = 8, height = #enfants * 40 + (#enfants - 1) * 8 }, enfants)
end

local function profils()
  local actuel = e.profil or ""
  if actuel == "" then return nil end
  local function choix(id, icone, nom)
    return ui.button({ text = nom, glyph = icone, flexGrow = 1, controlSize = "sm",
      variant = actuel == id and "primary" or "ghost", onClick = function() msg("power-set", id) end })
  end
  return ui.row({ gap = 4, padding = 4, height = 44, align = "center", radius = 22, fill = CARTE }, {
    choix("power-saver", "leaf", "Économie"),
    choix("balanced", "scale", "Équilibré"),
    choix("performance", "bolt", "Performance"),
  })
end

local function pied()
  local function action(icone, info, argv)
    return ui.button({ glyph = icone, variant = "ghost", controlSize = "md", tooltip = info, flexGrow = 1,
      onClick = function() panel.close(); noctalia.runAsync(argv) end })
  end
  return ui.row({ gap = 4, height = 44, align = "center" }, {
    action("screenshot", "Capture à annoter", { "noctalia", "msg", "screenshot-annotate" }),
    action("bell-ringing", "Notifications et agenda", { "noctalia", "msg", "panel-toggle", "control-center" }),
    action("settings", "Réglages de la barre", { "noctalia", "msg", "settings-open" }),
    action("lock", "Verrouiller", { "noctalia", "msg", "session", "lock" }),
    action("power", "Éteindre, redémarrer…", { "noctalia", "msg", "panel-toggle", "session-panel" }),
  })
end

local function accueil()
  local blocs = { entete(), carteMedia(), tuiles(), curseurs() }
  local p = profils()
  if p then table.insert(blocs, p) end
  table.insert(blocs, pied())
  return blocs
end

-- ── Page Wi-Fi ──────────────────────────────────────────────────────────────

local function connecter(n)
  local nom, actif, secu, connu = n[2], n[1] == "1", n[4] == "1", n[5] == "1"
  if actif then return end
  if secu and not connu then saisie = nom; dessiner(); return end
  enCours[nom] = true
  local argv = connu and { "nmcli", "con", "up", "id", nom } or { "nmcli", "dev", "wifi", "connect", nom }
  faire(argv, function(r)
    enCours[nom] = nil
    if r.exitCode ~= 0 then noctalia.notifyError("Wi-Fi", "Connexion à « " .. nom .. " » impossible.") end
  end)
  dessiner()
end

local function pageWifi()
  local wifi = e.wifi == "on"
  local lignes = {}
  if not wifi then
    table.insert(lignes, ui.label({ text = "Le Wi-Fi est coupé.", fontSize = 13, color = "on_surface_variant" }))
  elseif #listes.net == 0 then
    table.insert(lignes, ui.label({ text = "Recherche des réseaux…", fontSize = 13, color = "on_surface_variant" }))
  end
  for _, n in ipairs(wifi and listes.net or {}) do
    local nom, actif, sig, secu, connu = n[2], n[1] == "1", tonumber(n[3]) or 0, n[4] == "1", n[5] == "1"
    local icone = sig >= 67 and "wifi" or (sig >= 34 and "wifi-2" or "wifi-1")
    local sous = actif and "Connecté" or (enCours[nom] and "Connexion…" or (connu and "Enregistré" or (secu and "Sécurisé" or "Ouvert")))
    local droite = nil
    if actif then droite = ui.glyph({ name = "check", size = 18, color = "primary" })
    elseif secu then droite = ui.glyph({ name = "lock", size = 15, color = "on_surface_variant" }) end
    table.insert(lignes, ui.row({ key = "net-" .. nom, height = 54 }, { ligne(icone, nom, sous, actif, function() connecter(n) end, droite) }))
    if saisie == nom then
      table.insert(lignes, ui.row({ key = "mdp-ligne-" .. nom, gap = 8, height = 44, align = "center" }, {
        ui.input({ key = "mdp-" .. nom, flexGrow = 1, password = true, placeholder = "Mot de passe de « " .. nom .. " »", focus = true,
          onSubmit = function(mdp)
            saisie = nil; enCours[nom] = true
            faire({ "nmcli", "dev", "wifi", "connect", nom, "password", mdp }, function(r)
              enCours[nom] = nil
              if r.exitCode ~= 0 then noctalia.notifyError("Wi-Fi", "Mot de passe refusé pour « " .. nom .. " ».") end
            end)
            dessiner()
          end }),
        ui.button({ glyph = "x", variant = "ghost", controlSize = "sm", onClick = function() saisie = nil; dessiner() end }),
      }))
    end
  end
  return {
    titrePage("Wi-Fi", ui.toggle({ checked = wifi, onChange = function() msg("wifi-toggle") end })),
    ui.scroll({ flexGrow = 1, gap = 6 }, lignes),
    ui.row({ height = 40, gap = 8 }, {
      ui.button({ text = "Actualiser", glyph = "refresh", variant = "ghost", controlSize = "sm", flexGrow = 1,
        onClick = function() listes.net = {}; faire({ "nmcli", "dev", "wifi", "rescan" }); dessiner() end }),
      ui.button({ text = "Réglages réseau", glyph = "settings", variant = "ghost", controlSize = "sm", flexGrow = 1,
        onClick = function() panel.close(); noctalia.runAsync("nm-connection-editor || noctalia msg panel-toggle control-center") end }),
    }),
  }
end

-- ── Page Bluetooth ──────────────────────────────────────────────────────────

local ICONES_BT = { ["audio-headphones"] = "headphones", ["audio-headset"] = "headphones", ["audio-card"] = "device-speaker",
  ["input-mouse"] = "mouse", ["input-keyboard"] = "keyboard", ["input-gaming"] = "device-gamepad", phone = "device-mobile" }

local function pageBluetooth()
  local bt = e.bluetooth == "on"
  local lignes = {}
  if not bt then
    table.insert(lignes, ui.label({ text = "Le Bluetooth est coupé.", fontSize = 13, color = "on_surface_variant" }))
  elseif #listes.bt == 0 then
    table.insert(lignes, ui.label({ text = "Aucun appareil associé.", fontSize = 13, color = "on_surface_variant" }))
  end
  for _, d in ipairs(bt and listes.bt or {}) do
    local mac, nom, connecte = d[1], d[2], d[3] == "1"
    local sous = enCours[mac] and (connecte and "Déconnexion…" or "Connexion…") or (connecte and "Connecté" or "Non connecté")
    table.insert(lignes, ui.row({ key = "bt-" .. mac, height = 54 }, {
      ligne(ICONES_BT[d[4]] or "bluetooth", nom, sous, connecte, function()
        enCours[mac] = true
        faire({ "bluetoothctl", connecte and "disconnect" or "connect", mac }, function(r)
          enCours[mac] = nil
          if r.exitCode ~= 0 then noctalia.notifyError("Bluetooth", "« " .. nom .. " » ne répond pas.") end
        end)
        dessiner()
      end, connecte and ui.glyph({ name = "check", size = 18, color = "primary" }) or nil),
    }))
  end
  return {
    titrePage("Bluetooth", ui.toggle({ checked = bt, onChange = function() msg("bluetooth-toggle") end })),
    ui.scroll({ flexGrow = 1, gap = 6 }, lignes),
    ui.row({ height = 40 }, {
      ui.button({ text = "Associer un nouvel appareil", glyph = "bluetooth", variant = "ghost", controlSize = "sm", flexGrow = 1,
        onClick = function() panel.close(); noctalia.runAsync("blueman-manager || noctalia msg panel-toggle control-center") end }),
    }),
  }
end

-- ── Page Son ────────────────────────────────────────────────────────────────

local function pageSon()
  local lignes = { ui.label({ text = "SORTIE", fontSize = 11, fontWeight = "bold", color = "on_surface_variant", height = 18 }) }
  for _, s in ipairs(listes.sortie) do
    local id, nom, defaut = s[1], s[2], s[3] == "1"
    local bas = string.lower(nom)
    local icone = (string.find(bas, "casque") or string.find(bas, "head") or string.find(bas, "airpods")) and "headphones" or "device-speaker"
    table.insert(lignes, ui.row({ key = "so-" .. id, height = 54 }, {
      ligne(icone, nom, defaut and "Utilisée" or "Choisir", defaut, function() faire({ "wpctl", "set-default", id }) end,
        defaut and ui.glyph({ name = "check", size = 18, color = "primary" }) or nil),
    }))
  end
  table.insert(lignes, ui.label({ text = "MICROPHONE", fontSize = 11, fontWeight = "bold", color = "on_surface_variant", height = 26 }))
  for _, s in ipairs(listes.entree) do
    local id, nom, defaut = s[1], s[2], s[3] == "1"
    local muet = e.micro_muet == "1"
    local droite = nil
    if defaut then
      droite = ui.button({ glyph = muet and "microphone-off" or "microphone", variant = muet and "ghost" or "primary", controlSize = "sm",
        tooltip = muet and "Remettre le micro" or "Couper le micro",
        onClick = function() faire({ "wpctl", "set-mute", "@DEFAULT_AUDIO_SOURCE@", "toggle" }) end })
    end
    table.insert(lignes, ui.row({ key = "en-" .. id, height = 54 }, {
      ligne("microphone", nom, defaut and (muet and "Utilisé · coupé" or "Utilisé") or "Choisir", defaut,
        function() faire({ "wpctl", "set-default", id }) end, droite),
    }))
  end
  return {
    titrePage("Son"),
    curseurVolume(),
    ui.scroll({ flexGrow = 1, gap = 6 }, lignes),
  }
end

-- ── Rendu ───────────────────────────────────────────────────────────────────

function dessiner()
  local blocs
  if page == "wifi" then blocs = pageWifi()
  elseif page == "bluetooth" then blocs = pageBluetooth()
  elseif page == "son" then blocs = pageSon()
  else blocs = accueil() end
  local contenu = {}
  if anim.a > 0.02 then
    contenu = { ui.column({ width = L - 36, height = H - 36, gap = 12, align = "stretch", opacity = anim.a }, blocs) }
  end
  -- L'île : fond propre (la barre est transparente), bord fin, coins de pilule pendant le déploiement
  panel.render(ui.column({ width = L, height = H, align = "center", justify = "start" }, {
    ui.column({ width = math.floor(anim.w), height = math.floor(anim.h), padding = 18, align = "center", justify = "start",
      fill = "surface/0.94", radius = math.min(30, anim.h / 2), border = "primary/0.22", borderWidth = 1 }, contenu),
  }))
end

function onFrameTick(dt)
  local k = math.min(2.5, (tonumber(dt) or 16) / 16)
  -- Ressort amorti (léger rebond) pour la taille ; le contenu apparaît quand l'île est presque déployée
  anim.vw = anim.vw * 0.64 + (L - anim.w) * 0.2 * k
  anim.vh = anim.vh * 0.64 + (H - anim.h) * 0.2 * k
  anim.w = math.min(L, anim.w + anim.vw)
  anim.h = math.min(H, anim.h + anim.vh)
  -- (seulement une fois l'état lu : pas de « Rien en lecture » ni de réglages vides qui clignotent)
  if anim.h > H * 0.8 and next(e) ~= nil then anim.a = math.min(1, anim.a + 0.12 * k) end
  local pose = math.abs(L - anim.w) < 0.5 and math.abs(H - anim.h) < 0.5 and math.abs(anim.vw) + math.abs(anim.vh) < 0.5
  if pose then anim.w, anim.h, anim.vw, anim.vh = L, H, 0, 0 end
  if pose and anim.a >= 1 then panel.setNeedsFrameTick(false) end
  dessiner()
end

function onOpen()
  ouvert, tic, page, saisie = true, 0, "accueil", nil
  anim = { w = 230, h = 38, vw = 0, vh = 0, a = 0 }   -- part de la taille de la pilule
  panel.setWantsSecondTicks(true)
  panel.setNeedsFrameTick(true)
  lire()
  dessiner()
end

function onClose()
  ouvert = false
  panel.setWantsSecondTicks(false)
  panel.setNeedsFrameTick(false)
end

function update()
  tic += 1
  if not ouvert then return end
  if tic % 2 == 0 then lire() end
  if page ~= "accueil" and tic % 4 == 0 then lirePage() end
  if tic % 2 == 1 then dessiner() end
end

dessiner()

-- Ouvrir directement une page : noctalia msg plugin nc/ile:centre all page wifi|bluetooth|son|accueil
function onIpc(evenement, charge)
  if evenement == "page" and charge then aller(charge) end
end

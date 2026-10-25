--!nonstrict
-- nc/ile : le centre de contrôle, qui sort de la pilule (il démarre à sa taille et se déploie en ressort).
--   Accueil : heure, batterie, musique, Wi-Fi, Bluetooth, ne pas déranger, lumière de nuit, mode jeu, halo musical,
--             volume, luminosité, profil d'énergie, capture, notifications, réglages, verrouillage, session.
--   Pages   : Wi-Fi (réseaux, mot de passe), Bluetooth (appareils), Son (sorties, micro).
-- État lu par ~/.local/bin/nc-ile-etat à l'ouverture puis toutes les 2 s tant que le panneau est ouvert.

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

local sym = require("./symboles.luau")
local ETAT = noctalia.expandPath("~/.local/bin/nc-ile-etat")
local LUM = noctalia.expandPath("~/.local/bin/nc-brightness")
local L, H = 470, 640                       -- taille du panneau (plugin.toml)
local JOURS = { "dimanche", "lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi" }
local MOIS = { "janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre" }
local DAYS = { "Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday" }
local MONTHS = { "January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December" }

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

-- ── Interrupteurs réactifs ──────────────────────────────────────────────────
-- Même règle que Voulu.qml dans l'île : l'état « voulu » prend le pas sur la mesure dès le clic, jusqu'à ce que la mesure
-- le confirme ou au plus GRACE secondes ; une mesure contraire pendant la grâce est ignorée ; si la commande échoue, retour
-- immédiat à l'état réel. (Le bloc entre DEBUT et FIN est celui que tests/test_reactivite.py exécute.)
-- DEBUT voulu
local GRACE = 3                             -- secondes
local voulus = {}                           -- clé -> { valeur, fin }
local CONTRAIRE = { on = "off", off = "on", ["1"] = "0", ["0"] = "1" }
local function horloge() return os.clock() end
local function valeur(cle, mesure)
  local w = voulus[cle]
  if w then return w.valeur end
  return mesure
end
local function voulu(cle, v) voulus[cle] = { valeur = tostring(v), fin = horloge() + GRACE } end
local function annuler(cle) voulus[cle] = nil end
local function confirmer()
  for cle, w in pairs(voulus) do if e[cle] == w.valeur then voulus[cle] = nil end end
end
local function expirer()
  local t = horloge()
  for cle, w in pairs(voulus) do if t >= w.fin then voulus[cle] = nil end end
end
-- FIN voulu

local function lire()
  noctalia.runAsync({ ETAT }, function(r)
    e = analyser(r.stdout)
    confirmer()
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

local relire = nil                           -- seconde relecture (transitions lentes : BlueZ, NetworkManager)

-- Lance une commande ; relit l'état dès sa fin. cle : l'interrupteur qu'elle bascule (retour immédiat à la mesure si elle échoue)
local function faire(argv, apres, cle)
  noctalia.runAsync(argv, function(r)
    if cle and r.exitCode ~= 0 then
      annuler(cle)
      noctalia.notifyError(tr("Île", "Island"), tr("La commande a échoué.", "The command failed."))
      if ouvert then dessiner() end
    end
    if apres then apres(r) end
    lire(); lirePage()
    relire = horloge() + 1.5
  end, 15000)
end

local function msg(...) faire({ "noctalia", "msg", ... }) end

-- Inverse l'interrupteur `cle` (on/off ou 1/0) tout de suite, puis lance la commande
local function basculer(cle, argv)
  local cible = CONTRAIRE[tostring(valeur(cle, e[cle]))]
  if cible then voulu(cle, cible); dessiner() end
  faire(argv, nil, cle)
end
local function basculerMsg(cle, ...) basculer(cle, { "noctalia", "msg", ... }) end

local function aller(p)
  page = p
  saisie = nil
  anim.a = 0                                -- le nouveau contenu apparaît en fondu
  panel.setNeedsFrameTick(true)
  lirePage()
  dessiner()
end

-- ── Briques (langage visuel d'Apple, mode sombre) ───────────────────────────
-- Île noir pur ; modules gris foncé ; boutons ronds qui s'allument dans la couleur système de leur fonction.

local NOIR, MODULE, MODULE2, GRIS, BLANC = "#000000", "#1c1c1e", "#2c2c2e", "#98989d", "#ffffff"
local BLEU, VERT, ORANGE, INDIGO, JAUNE, ROSE = "#0a84ff", "#30d158", "#ff9f0a", "#5e5ce6", "#ffd60a", "#ff375f"
local ETEINT = "#3a3a3c"

-- Icône : symbole dessiné façon SF Symbols quand il existe (couleur en hexadécimal), sinon glyphe Tabler
local SYMBOLES = { wifi = "wifi", ["wifi-off"] = "wifi-off", bluetooth = "bluetooth", ["bluetooth-off"] = "bluetooth",
  moon = "lune", ["moon-stars"] = "lune", bell = "cloche", ["device-gamepad-2"] = "manette", sun = "soleil",
  ["wave-sine"] = "onde", volume = "haut-parleur", ["volume-off"] = "muet", music = "note",
  ["player-play-filled"] = "lecture", ["player-pause-filled"] = "pause", ["player-skip-back-filled"] = "precedent",
  ["player-skip-forward-filled"] = "suivant", lock = "cadenas", power = "marche", settings = "reglages",
  screenshot = "capture", bolt = "eclair", leaf = "feuille", scale = "equilibre", microphone = "micro",
  ["microphone-off"] = "micro-coupe", ["chevron-left"] = "chevron-gauche", ["chevron-right"] = "chevron-droite",
  check = "coche", headphones = "casque", ["device-speaker"] = "enceinte", ["bell-ringing"] = "cloche" }

local function ico(nom, couleur, taille)
  local s = SYMBOLES[nom]
  if s and type(couleur) == "string" and string.sub(couleur, 1, 1) == "#" then
    return sym.image(s, couleur, taille)
  end
  return ui.glyph({ name = nom, size = taille, color = couleur })
end

local function titrePage(nom, droite)
  return ui.row({ height = 44, gap = 6, align = "center" }, {
    ui.column({ width = 36, height = 36, radius = 18, fill = MODULE2, align = "center", justify = "center",
      onClick = function() aller("accueil") end }, { ico("chevron-left", BLANC, 18) }),
    ui.label({ text = nom, fontSize = 20, fontWeight = "bold", color = BLANC, flexGrow = 1 }),
    droite or ui.spacer({ width = 1 }),
  })
end

local function ligne(icone, nom, sous, actif, action, droite)
  return ui.row({ height = 56, flexGrow = 1, gap = 12, paddingH = 14, align = "center", radius = 16,
    fill = MODULE, onClick = action }, {
    ui.column({ width = 32, height = 32, radius = 16, fill = actif and BLEU or ETEINT, align = "center", justify = "center" }, {
      ico(icone, BLANC, 19),
    }),
    ui.column({ flexGrow = 1, gap = 1 }, {
      ui.label({ text = nom, fontSize = 14, fontWeight = "semibold", color = BLANC, maxLines = 1, maxWidth = 280 }),
      ui.label({ text = sous, fontSize = 12, color = actif and BLEU or GRIS, maxLines = 1 }),
    }),
    droite or ui.spacer({ width = 1 }),
  })
end

-- Bouton rond façon Centre de contrôle iOS : gris éteint, couleur de la fonction quand il est actif
local function rond(icone, actif, couleur, info, action, taille)   -- info : description (non affichée)
  taille = taille or 54
  return ui.column({ width = taille, height = taille, radius = taille / 2, fill = actif and couleur or ETEINT,
    align = "center", justify = "center", onClick = action }, {
    ico(icone, BLANC, math.floor(taille * 0.5)),
  })
end

-- Grande pastille avec bouton rond et libellé (style « Concentration » d'iOS)
local function pastille(icone, titre, sous, actif, couleur, action)
  return ui.row({ flexGrow = 1, height = 71, gap = 10, paddingH = 12, align = "center", radius = 22, fill = MODULE, onClick = action }, {
    ui.column({ width = 38, height = 38, radius = 19, fill = actif and couleur or ETEINT, align = "center", justify = "center" }, {
      ico(icone, BLANC, 21),
    }),
    ui.column({ flexGrow = 1, gap = 1 }, {
      ui.label({ text = titre, fontSize = 13, fontWeight = "semibold", color = BLANC, maxLines = 1 }),
      ui.label({ text = sous, fontSize = 11, color = GRIS, maxLines = 1, maxWidth = 130 }),
    }),
  })
end

local function curseur(icone, valeur, bouton, change, fin, detail)
  valeur = math.floor((valeur or 0) + 0.5)
  local enfants = {
    ui.column({ width = 36, height = 36, radius = 18, align = "center", justify = "center", onClick = bouton }, {
      ico(icone, BLANC, 22),
    }),
    ui.slider({ flexGrow = 1, min = 0, max = 100, step = 1, value = valeur, onChange = change, onDragEnd = fin }),
    ui.label({ text = tr(valeur .. " %", valeur .. "%"), width = 44, fontSize = 13, fontWeight = "semibold", color = GRIS, textAlign = "end" }),
  }
  if detail then
    table.insert(enfants, ui.column({ width = 30, height = 36, align = "center", justify = "center", onClick = detail }, {
      ico("chevron-right", GRIS, 16),
    }))
  end
  return ui.row({ gap = 6, align = "center", height = 54, paddingH = 10, radius = 22, fill = MODULE }, enfants)
end

local function curseurVolume(detail)
  local muet = valeur("muet", e.muet) == "1"
  return curseur(muet and "volume-off" or "volume", volume, function()
    basculer("muet", { "wpctl", "set-mute", "@DEFAULT_AUDIO_SINK@", "toggle" })
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
    table.insert(droite, ui.label({ text = tr(bat .. " %", bat .. "%"), fontSize = 13, fontWeight = "semibold", color = BLANC }))
    table.insert(droite, ui.glyph({ name = charge and "battery-charging" or "battery-2", size = 18,
      color = charge and VERT or ((bat <= 20) and "#ff453a" or BLANC) }))
  end
  return ui.row({ align = "center", gap = 8, height = 26, paddingH = 6 }, {
    ui.label({ text = tr(JOURS[t.wday] .. " " .. t.day .. " " .. MOIS[t.month], DAYS[t.wday] .. ", " .. MONTHS[t.month] .. " " .. t.day), fontSize = 13, fontWeight = "semibold", color = GRIS, flexGrow = 1 }),
    ui.row({ gap = 6, align = "center" }, droite),
  })
end

local function carteMedia()
  local rien = e.media ~= "1" or e.media_etat == "Stopped"
  local duree = (tonumber(e.media_duree) or 0) / 1000000
  local pos = tonumber(e.media_position) or 0
  local p = e.media_pochette or ""
  local pochette
  if not rien and p ~= "" and noctalia.fileExists(p) then
    pochette = ui.image({ key = "pochette-" .. p, path = p, width = 62, height = 62, radius = 12, fit = "cover" })
  else
    pochette = ui.column({ width = 62, height = 62, radius = 12, fill = MODULE2, align = "center", justify = "center" }, {
      ico("music", GRIS, 26),
    })
  end
  local joue = e.media_etat == "Playing"
  local function commande(icone, taille, action)
    return ui.column({ width = 40, height = 40, radius = 20, align = "center", justify = "center", onClick = action }, {
      ico(icone, rien and ETEINT or BLANC, taille),
    })
  end
  local function temps(s)
    s = math.max(0, math.floor(s or 0))
    return string.format("%d:%02d", math.floor(s / 60), s % 60)
  end
  return ui.column({ gap = 10, padding = 14, height = 140, radius = 26, fill = MODULE }, {
    ui.row({ gap = 12, align = "center", height = 62 }, {
      pochette,
      ui.column({ flexGrow = 1, gap = 2 }, {
        ui.label({ text = rien and tr("Rien en lecture", "Not Playing") or (e.media_titre or ""), fontSize = 15, fontWeight = "semibold", color = BLANC, maxLines = 1, maxWidth = 230 }),
        ui.label({ text = rien and tr("Lance une musique", "Play some music") or (e.media_artiste or ""), fontSize = 13, color = GRIS, maxLines = 1, maxWidth = 230 }),
      }),
      ui.row({ gap = 0, align = "center" }, {
        commande("player-skip-back-filled", 22, function() faire({ "playerctl", "previous" }) end),
        commande(joue and "player-pause-filled" or "player-play-filled", 30, function() faire({ "playerctl", "play-pause" }) end),
        commande("player-skip-forward-filled", 22, function() faire({ "playerctl", "next" }) end),
      }),
    }),
    ui.row({ gap = 8, align = "center", height = 16 }, {
      ui.label({ text = temps(pos), width = 38, fontSize = 11, color = GRIS }),
      ui.progress({ flexGrow = 1, height = 4, radius = 2, progress = duree > 0 and math.min(1, pos / duree) or 0, fill = BLANC, track = ETEINT }),
      ui.label({ text = "-" .. temps(math.max(0, duree - pos)), width = 42, fontSize = 11, color = GRIS, textAlign = "end" }),
    }),
  })
end

local function reglages()
  local wifi, bt, dnd = valeur("wifi", e.wifi) == "on", valeur("bluetooth", e.bluetooth) == "on", valeur("dnd", e.dnd) == "on"
  local nuit = noctalia.state.get("nuit") == true
  local jeu, halo = valeur("jeu", e.jeu) == "1", valeur("halo", e.halo) == "1"
  -- Module de connexions : quatre boutons ronds (clic : activer ; clic droit impossible ici, d'où les pastilles › )
  local connexions = ui.column({ width = 150, height = 150, padding = 14, gap = 14, radius = 26, fill = MODULE, justify = "center", align = "center" }, {
    ui.row({ gap = 14, height = 54 }, {
      rond(wifi and "wifi" or "wifi-off", wifi, BLEU, wifi and ("Wi-Fi : " .. ((e.reseau ~= "" and e.reseau) or "activé")) or "Wi-Fi coupé",
        function() basculerMsg("wifi", "wifi-toggle") end),
      rond(bt and "bluetooth" or "bluetooth-off", bt, BLEU, bt and "Bluetooth activé" or "Bluetooth coupé", function() basculerMsg("bluetooth", "bluetooth-toggle") end),
    }),
    ui.row({ gap = 14, height = 54 }, {
      rond(dnd and "moon" or "bell", dnd, INDIGO, dnd and "Ne pas déranger : activé" or "Ne pas déranger", function() basculerMsg("dnd", "notification-dnd-toggle") end),
      rond("device-gamepad-2", jeu, ORANGE, jeu and "Mode jeu : activé" or "Mode jeu", function() basculer("jeu", { "hyprctl", "eval", "nc.mode_jeu()" }) end),
    }),
  })
  local reseau = (wifi and ((e.reseau ~= "" and e.reseau) or tr("Activé", "On"))) or tr("Coupé", "Off")
  return ui.row({ gap = 12, height = 150 }, {
    connexions,
    ui.column({ flexGrow = 1, gap = 8 }, {
      ui.row({ gap = 8, height = 71 }, {
        pastille("wifi", "Wi-Fi", reseau, wifi, BLEU, function() aller("wifi") end),
      }),
      ui.row({ gap = 8, height = 71 }, {
        pastille(nuit and "moon-stars" or "sun", tr("Nuit", "Night"), nuit and tr("Tons chauds", "Warm tones") or tr("Désactivée", "Off"), nuit, ORANGE,
          function() noctalia.state.set("nuit", not nuit); msg("nightlight-force-toggle") end),
        pastille("wave-sine", tr("Halo", "Glow"), halo and tr("Musique", "Music") or tr("Coupé", "Off"), halo, ROSE,
          function() basculer("halo", { "systemctl", "--user", halo and "stop" or "start", "nc-pouls" }) end),
      }),
    }),
  })
end

local function curseurs()
  local enfants = { curseurVolume(function() aller("son") end) }
  if luminosite then
    table.insert(enfants, curseur("sun", luminosite, nil, function(v)
      luminosite = tonumber(v) or luminosite
      noctalia.runAsync({ LUM, "set", tostring(math.max(1, math.floor(luminosite))) })
      dessiner()
    end, function() lire() end))
  end
  return ui.column({ gap = 10, height = #enfants * 54 + (#enfants - 1) * 10 }, enfants)
end

-- Sélecteur segmenté façon iOS
local function profils()
  local actuel = valeur("profil", e.profil) or ""
  if actuel == "" then return nil end
  local function choix(id, icone, nom, couleur)
    local actif = actuel == id
    return ui.row({ flexGrow = 1, height = 34, radius = 12, gap = 6, align = "center", justify = "center",
      fill = actif and "#636366" or NOIR .. "00", onClick = function() voulu("profil", id); dessiner(); faire({ "noctalia", "msg", "power-set", id }, nil, "profil") end }, {
      ico(icone, actif and couleur or GRIS, 16),
      ui.label({ text = nom, fontSize = 13, fontWeight = "semibold", color = actif and BLANC or GRIS }),
    })
  end
  return ui.row({ gap = 2, padding = 3, height = 40, align = "center", radius = 14, fill = MODULE }, {
    choix("power-saver", "leaf", tr("Économie", "Power Saver"), VERT),
    choix("balanced", "scale", tr("Équilibré", "Balanced"), BLANC),
    choix("performance", "bolt", "Performance", ORANGE),
  })
end

local function pied()
  local function action(icone, info, argv)
    return rond(icone, false, ETEINT, info, function() panel.close(); noctalia.runAsync(argv) end, 46)
  end
  return ui.row({ gap = 0, height = 46, align = "center", justify = "space_between", paddingH = 6 }, {
    action("screenshot", "Capture à annoter", { noctalia.expandPath("~/.local/bin/nc-capture"), "retouche" }),
    action("bluetooth", "Appareils Bluetooth", { "noctalia", "msg", "plugin", "nc/ile:centre", "all", "page", "bluetooth" }),
    action("bell-ringing", "Notifications et agenda", { "noctalia", "msg", "panel-toggle", "control-center" }),
    action("settings", "Réglages de la barre", { "noctalia", "msg", "settings-open" }),
    action("lock", "Verrouiller", { "noctalia", "msg", "session", "lock" }),
    action("power", "Éteindre, redémarrer…", { "noctalia", "msg", "panel-toggle", "session" }),
  })
end

local function accueil()
  local blocs = { entete(), carteMedia(), reglages(), curseurs() }
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
    if r.exitCode ~= 0 then noctalia.notifyError("Wi-Fi", tr("Connexion à « " .. nom .. " » impossible.", "Couldn’t connect to “" .. nom .. "”.")) end
  end)
  dessiner()
end

local function pageWifi()
  local wifi = valeur("wifi", e.wifi) == "on"
  local lignes = {}
  if not wifi then
    table.insert(lignes, ui.label({ text = tr("Le Wi-Fi est coupé.", "Wi-Fi is off."), fontSize = 13, color = GRIS }))
  elseif #listes.net == 0 then
    table.insert(lignes, ui.label({ text = tr("Recherche des réseaux…", "Searching for networks…"), fontSize = 13, color = GRIS }))
  end
  for _, n in ipairs(wifi and listes.net or {}) do
    local nom, actif, sig, secu, connu = n[2], n[1] == "1", tonumber(n[3]) or 0, n[4] == "1", n[5] == "1"
    local icone = sig >= 67 and "wifi" or (sig >= 34 and "wifi-2" or "wifi-1")
    local sous = actif and tr("Connecté", "Connected") or (enCours[nom] and tr("Connexion…", "Connecting…")
      or (connu and tr("Enregistré", "Saved") or (secu and tr("Sécurisé", "Secured") or tr("Ouvert", "Open"))))
    local droite = nil
    if actif then droite = ico("check", BLEU, 18)
    elseif secu then droite = ico("lock", GRIS, 15) end
    table.insert(lignes, ui.row({ key = "net-" .. nom, height = 54 }, { ligne(icone, nom, sous, actif, function() connecter(n) end, droite) }))
    if saisie == nom then
      table.insert(lignes, ui.row({ key = "mdp-ligne-" .. nom, gap = 8, height = 44, align = "center" }, {
        ui.input({ key = "mdp-" .. nom, flexGrow = 1, password = true, placeholder = tr("Mot de passe de « " .. nom .. " »", "Password for “" .. nom .. "”"), focus = true,
          onSubmit = function(mdp)
            saisie = nil; enCours[nom] = true
            faire({ "nmcli", "dev", "wifi", "connect", nom, "password", mdp }, function(r)
              enCours[nom] = nil
              if r.exitCode ~= 0 then noctalia.notifyError("Wi-Fi", tr("Mot de passe refusé pour « " .. nom .. " ».", "Wrong password for “" .. nom .. "”.")) end
            end)
            dessiner()
          end }),
        ui.button({ glyph = "x", variant = "ghost", controlSize = "sm", onClick = function() saisie = nil; dessiner() end }),
      }))
    end
  end
  return {
    titrePage("Wi-Fi", ui.toggle({ checked = wifi, onChange = function() basculerMsg("wifi", "wifi-toggle") end })),
    ui.scroll({ flexGrow = 1, gap = 6 }, lignes),
    ui.row({ height = 40, gap = 8 }, {
      ui.button({ text = tr("Actualiser", "Refresh"), glyph = "refresh", variant = "ghost", controlSize = "sm", flexGrow = 1,
        onClick = function() listes.net = {}; faire({ "nmcli", "dev", "wifi", "rescan" }); dessiner() end }),
      ui.button({ text = tr("Réglages réseau", "Network Settings"), glyph = "settings", variant = "ghost", controlSize = "sm", flexGrow = 1,
        onClick = function() panel.close(); noctalia.runAsync("nm-connection-editor || noctalia msg panel-toggle control-center") end }),
    }),
  }
end

-- ── Page Bluetooth ──────────────────────────────────────────────────────────

local ICONES_BT = { ["audio-headphones"] = "headphones", ["audio-headset"] = "headphones", ["audio-card"] = "device-speaker",
  ["input-mouse"] = "mouse", ["input-keyboard"] = "keyboard", ["input-gaming"] = "device-gamepad", phone = "device-mobile" }

local function pageBluetooth()
  local bt = valeur("bluetooth", e.bluetooth) == "on"
  local lignes = {}
  if not bt then
    table.insert(lignes, ui.label({ text = tr("Le Bluetooth est coupé.", "Bluetooth is off."), fontSize = 13, color = GRIS }))
  elseif #listes.bt == 0 then
    table.insert(lignes, ui.label({ text = tr("Aucun appareil associé.", "No paired devices."), fontSize = 13, color = GRIS }))
  end
  for _, d in ipairs(bt and listes.bt or {}) do
    local mac, nom, connecte = d[1], d[2], d[3] == "1"
    local sous = enCours[mac] and (connecte and tr("Déconnexion…", "Disconnecting…") or tr("Connexion…", "Connecting…"))
      or (connecte and tr("Connecté", "Connected") or tr("Non connecté", "Not connected"))
    table.insert(lignes, ui.row({ key = "bt-" .. mac, height = 54 }, {
      ligne(ICONES_BT[d[4]] or "bluetooth", nom, sous, connecte, function()
        enCours[mac] = true
        faire({ "bluetoothctl", connecte and "disconnect" or "connect", mac }, function(r)
          enCours[mac] = nil
          if r.exitCode ~= 0 then noctalia.notifyError("Bluetooth", tr("« " .. nom .. " » ne répond pas.", "“" .. nom .. "” isn’t responding.")) end
        end)
        dessiner()
      end, connecte and ico("check", BLEU, 18) or nil),
    }))
  end
  return {
    titrePage("Bluetooth", ui.toggle({ checked = bt, onChange = function() basculerMsg("bluetooth", "bluetooth-toggle") end })),
    ui.scroll({ flexGrow = 1, gap = 6 }, lignes),
    ui.row({ height = 40 }, {
      ui.button({ text = tr("Associer un nouvel appareil", "Pair a New Device"), glyph = "bluetooth", variant = "ghost", controlSize = "sm", flexGrow = 1,
        onClick = function() panel.close(); noctalia.runAsync("blueman-manager || noctalia msg panel-toggle control-center") end }),
    }),
  }
end

-- ── Page Son ────────────────────────────────────────────────────────────────

local function pageSon()
  local lignes = { ui.label({ text = tr("SORTIE", "OUTPUT"), fontSize = 11, fontWeight = "bold", color = GRIS, height = 18 }) }
  for _, s in ipairs(listes.sortie) do
    local id, nom, defaut = s[1], s[2], s[3] == "1"
    local bas = string.lower(nom)
    local icone = (string.find(bas, "casque") or string.find(bas, "head") or string.find(bas, "airpods")) and "headphones" or "device-speaker"
    table.insert(lignes, ui.row({ key = "so-" .. id, height = 54 }, {
      ligne(icone, nom, defaut and tr("Utilisée", "In use") or tr("Choisir", "Select"), defaut, function() faire({ "wpctl", "set-default", id }) end,
        defaut and ico("check", BLEU, 18) or nil),
    }))
  end
  table.insert(lignes, ui.label({ text = "MICROPHONE", fontSize = 11, fontWeight = "bold", color = GRIS, height = 26 }))
  for _, s in ipairs(listes.entree) do
    local id, nom, defaut = s[1], s[2], s[3] == "1"
    local muet = valeur("micro_muet", e.micro_muet) == "1"
    local droite = nil
    if defaut then
      droite = rond(muet and "microphone-off" or "microphone", muet, "#ff453a", muet and "Remettre le micro" or "Couper le micro",
        function() basculer("micro_muet", { "wpctl", "set-mute", "@DEFAULT_AUDIO_SOURCE@", "toggle" }) end, 34)
    end
    table.insert(lignes, ui.row({ key = "en-" .. id, height = 54 }, {
      ligne("microphone", nom, defaut and (muet and tr("Utilisé · coupé", "In use · muted") or tr("Utilisé", "In use")) or tr("Choisir", "Select"), defaut,
        function() faire({ "wpctl", "set-default", id }) end, droite),
    }))
  end
  return {
    titrePage(tr("Son", "Sound")),
    curseurVolume(),
    ui.scroll({ flexGrow = 1, gap = 6 }, lignes),
  }
end

-- ── Rendu et animation ──────────────────────────────────────────────────────
-- L'île naît à la taille exacte de la pilule (largeur publiée par la pilule), sous elle, et s'étire avec un ressort
-- physique (comme l'île dynamique de l'iPhone) ; la pilule s'efface pendant ce temps. À la fermeture (clic sur la
-- pilule, Super + C, Échap), le contenu s'efface puis l'île se rétracte jusqu'à la pilule, qui réapparaît.

local PILULE_H = 30
local RESSORT = { k = 210, c = 25 }        -- raideur, amortissement (≈ 0,45 s, très léger rebond)
local fermeture = false

local function cibleL() return fermeture and anim.l0 or (L - 8) end
local function cibleH() return fermeture and PILULE_H or (H - 8) end

function dessiner()
  local blocs
  if page == "wifi" then blocs = pageWifi()
  elseif page == "bluetooth" then blocs = pageBluetooth()
  elseif page == "son" then blocs = pageSon()
  else blocs = accueil() end
  local contenu = {}
  if anim.a > 0.02 then
    contenu = { ui.column({ width = L - 44, height = H - 44, gap = 14, align = "stretch", opacity = anim.a }, blocs) }
  end
  local w, h = math.max(10, math.floor(anim.w + 0.5)), math.max(10, math.floor(anim.h + 0.5))
  panel.render(ui.column({ width = L, height = H, align = "center", justify = "start" }, {
    ui.column({ width = w, height = h, padding = 18, align = "center", justify = "start",
      fill = NOIR, radius = math.min(42, h / 2) }, contenu),
  }))
end

local function ressort(x, v, cible, dt)
  local a = RESSORT.k * (cible - x) - RESSORT.c * v
  v = v + a * dt
  return x + v * dt, v
end

function onFrameTick(ms)
  local reste = math.min(0.05, (tonumber(ms) or 16) / 1000)
  while reste > 0 do                          -- petits pas : mouvement régulier même si une image saute
    local dt = math.min(0.004, reste)
    anim.w, anim.vw = ressort(anim.w, anim.vw, cibleL(), dt)
    anim.h, anim.vh = ressort(anim.h, anim.vh, cibleH(), dt)
    reste -= dt
  end
  anim.w, anim.h = math.min(L, anim.w), math.min(H, anim.h)
  local ms_ = (tonumber(ms) or 16)
  if fermeture then
    anim.a = math.max(0, anim.a - ms_ / 90)
    if math.abs(anim.h - PILULE_H) < 1.5 and math.abs(anim.vh) < 40 then
      fermeture = false
      panel.setNeedsFrameTick(false)
      panel.close()
      return
    end
  elseif anim.h > (H - 8) * 0.72 and next(e) ~= nil then
    anim.a = math.min(1, anim.a + ms_ / 160)
  end
  local pose = not fermeture and math.abs(cibleL() - anim.w) < 0.3 and math.abs(cibleH() - anim.h) < 0.3
    and math.abs(anim.vw) + math.abs(anim.vh) < 2 and anim.a >= 1
  if pose then panel.setNeedsFrameTick(false) end
  dessiner()
end

-- Fermeture animée (au lieu de disparaître d'un coup)
local function fermer()
  if fermeture or not ouvert then return end
  fermeture = true
  anim.l0 = tonumber(noctalia.state.get("ile-largeur")) or anim.l0 or 200
  noctalia.state.set("ile-ouverte", "fermeture")       -- la pilule se prépare à réapparaître
  panel.setNeedsFrameTick(true)
end

function onOpen()
  EN = langue() == "en"
  ouvert, tic, page, saisie, fermeture = true, 0, "accueil", nil, false
  local l0 = tonumber(noctalia.state.get("ile-largeur")) or 200
  anim = { w = l0, h = PILULE_H, vw = 0, vh = 0, a = 0, l0 = l0 }   -- part de la pilule, à sa taille exacte
  noctalia.state.set("ile-ouverte", "ouverte")
  panel.setWantsSecondTicks(true)
  panel.setNeedsFrameTick(true)
  lire()
  dessiner()
end

function onClose()
  ouvert, fermeture = false, false
  noctalia.state.set("ile-ouverte", "fermee")
  panel.setWantsSecondTicks(false)
  panel.setNeedsFrameTick(false)
end

function onKey(touche, appui)
  if touche == "Escape" and appui ~= false then fermer() end
end

function update()
  tic += 1
  if not ouvert or fermeture then return end
  expirer()
  if relire and horloge() >= relire then relire = nil; lire() end
  if tic % 2 == 0 then lire() end
  if page ~= "accueil" and tic % 4 == 0 then lirePage() end
  if tic % 2 == 1 then dessiner() end
end

-- Messages : noctalia msg plugin nc/ile:centre all page wifi|bluetooth|son|accueil   ·   … all fermer
function onIpc(evenement, charge)
  if evenement == "page" and charge then aller(charge)
  elseif evenement == "fermer" then fermer() end
end

noctalia.state.watch("ile-commande", function(c)
  if type(c) == "table" and c.action == "fermer" then fermer() end
end)

dessiner()

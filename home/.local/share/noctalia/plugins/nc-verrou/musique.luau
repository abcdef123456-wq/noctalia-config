--!nonstrict
-- nc/verrou : la musique sur l'écran de verrouillage, en longue capsule noire comme l'île dynamique.
--   Pochette (sinon l'icône de l'appli sur une tuile sombre, comme sur iPhone), titre, artiste ou source,
--   progression avec temps écoulé / restant, précédent / lecture / suivant.
--   Infos : ~/.local/bin/nc-verrou-media (dernier lecteur actif selon playerctld, pochette d'internet mise en cache,
--   fichier d'icône de l'appli, temps depuis la dernière pause noté par l'île). Rien ne s'affiche quand rien ne joue, ni
--   pour un lecteur en pause depuis plus de 15 min.
--   Vie privée : VERROU_MUSIQUE (nc-reglages → Apparence) = tout | sans-navigateur (défaut) | icone. Un navigateur
--   affiche le titre de l'onglet : avec sans-navigateur il n'y a que son icône et « Lecture en cours » ; avec icone,
--   tous les lecteurs n'ont que leur icône. Les boutons précédent / suivant ne sont cliquables qu'avec « tout ».
--   Énergie : écran éteint (fichier nc-ecran-eteint de nc-ecran), plus aucun lancement ; 5 s au lieu de 1 s si rien ne joue.
--   Navigateurs sans métadonnées : « Épisode 3 – Série – Crunchyroll » devient « Épisode 3 – Série », source « Crunchyroll ».
-- Taille : box_width / box_height du widget dans config.toml (680 × 104).

local NOIR, BLANC, GRIS, PISTE, TUILE = "#000000", "#ffffff", "#98989d", "#3a3a3c", "#1c1c1e"
local L, H = 680, 104
local MEDIA = noctalia.expandPath("~/.local/bin/nc-verrou-media")
local NAVIGATEURS = { "firefox", "chrom", "brave", "vivaldi", "opera", "edge", "zen", "librewolf", "floorp", "epiphany",
  "falkon", "qutebrowser", "waterfox", "browser" }
local ETEINT = (noctalia.getenv("XDG_RUNTIME_DIR") or "/tmp") .. "/nc-ecran-eteint"   -- posé par nc-ecran écran éteint

local media = nil          -- { etat, titre, source, pochette, icone, duree, position, age }
local derniereLecture = 0
local ecranEteint = false
local mode = "sans-navigateur"   -- VERROU_MUSIQUE, relu à chaque lecture

local function maintenant() return noctalia.nowMs() end

local function navigateur(joueur)
  local j = string.lower(joueur or "")
  for _, n in ipairs(NAVIGATEURS) do
    if string.find(j, n, 1, true) then return true end
  end
  return false
end

-- Titre d'onglet découpé sur « – », « — », « | », « · » ou « - » entourés d'espaces
local function decouper(titre)
  titre = string.gsub(titre, "^%(%d+%)%s*", "")
  local parties, reste = {}, titre
  while true do
    local a, b = nil, nil
    for _, sep in ipairs({ " – ", " — ", " | ", " · ", " - " }) do
      local x, y = string.find(reste, sep, 1, true)
      if x and (not a or x < a) then a, b = x, y end
    end
    if not a then table.insert(parties, reste); break end
    table.insert(parties, string.sub(reste, 1, a - 1))
    reste = string.sub(reste, b + 1)
  end
  return parties
end

local function temps(s)
  s = math.max(0, math.floor(s or 0))
  if s >= 3600 then return string.format("%d:%02d:%02d", math.floor(s / 3600), math.floor(s / 60) % 60, s % 60) end
  return string.format("%d:%02d", math.floor(s / 60), s % 60)
end

-- VERROU_MUSIQUE dans style.conf puis reglages.conf (comme heure.luau) ; valeur inconnue : le défaut
local function lireMode()
  local m = "sans-navigateur"
  for _, nom in ipairs({ "~/.config/nc/style.conf", "~/.config/nc/reglages.conf" }) do
    local t = noctalia.readFile(noctalia.expandPath(nom)) or ""
    for k, v in string.gmatch(t, "([%u%d_]+)=([^\n]*)") do
      if k == "VERROU_MUSIQUE" then m = string.gsub(string.gsub(v, "^%s+", ""), "%s+$", "") end
    end
  end
  if m ~= "tout" and m ~= "icone" then m = "sans-navigateur" end
  return m
end

local function lire()
  derniereLecture = maintenant()
  mode = lireMode()
  noctalia.runAsync({ MEDIA }, function(r)
    local l = string.gsub(r.stdout or "", "\n$", "")
    local c = {}
    for v in string.gmatch(l .. "\t", "([^\t]*)\t") do table.insert(c, v) end
    if #c < 9 or c[1] == "" or c[1] == "Stopped" or c[2] == "" then
      media = nil
    else
      local titre, source = c[2], c[3]
      if source == "" and navigateur(c[7]) then
        local p = decouper(titre)
        if #p > 1 then
          source = p[#p]; table.remove(p); titre = table.concat(p, " – ")
        else
          titre = p[1]
        end
      end
      -- age : secondes depuis le dernier départ / arrêt de lecture (noté par l'île), nil si inconnu
      media = { etat = c[1], titre = titre, source = source ~= "" and source or c[7], pochette = c[4], icone = c[8], joueur = c[7],
        duree = (tonumber(c[5]) or 0) / 1e6, position = (tonumber(c[6]) or 0) / 1e6, age = tonumber(c[9]) }
    end
    rendre()
  end, 4000)
end

local function commander(action)
  noctalia.runAsync({ "playerctl", "-p", "playerctld", action }, function() lire() end, 3000)
end

local function bouton(nom, taille, action)
  return ui.column({ width = 46, height = 46, radius = 23, align = "center", justify = "center", onClick = action }, {
    ui.glyph({ name = nom, size = taille, color = BLANC }),
  })
end

function rendre()
  -- Lecture en cours, ou pause de moins de 15 min (un onglet oublié en pause depuis des heures reste caché)
  local visible = media ~= nil and (media.etat == "Playing" or (media.age ~= nil and media.age < 15 * 60))
  if not visible then
    desktopWidget.render(ui.box({ width = L, height = H, opacity = 0 }))
    return
  end
  -- Vie privée : un navigateur (titre d'onglet, vignette) ou le mode « icone » ne montre que l'icône de l'appli
  local prive = mode == "icone" or (mode == "sans-navigateur" and navigateur(media.joueur))
  -- Image de gauche : pochette, sinon icône de l'appli sur une tuile sombre, sinon une note
  local image
  if not prive and media.pochette ~= "" and noctalia.fileExists(media.pochette) then
    image = ui.image({ key = "pochette:" .. media.pochette, path = media.pochette, width = 76, height = 76, radius = 18, fit = "cover" })
  else
    local dedans
    if media.icone ~= "" and noctalia.fileExists(media.icone) then
      dedans = ui.image({ key = "icone:" .. media.icone, path = media.icone, width = 50, height = 50, fit = "contain" })
    else
      dedans = ui.glyph({ name = "music", size = 30, color = GRIS })
    end
    image = ui.column({ width = 76, height = 76, radius = 18, fill = TUILE, align = "center", justify = "center" }, { dedans })
  end
  local progression = media.duree > 0 and math.max(0, math.min(1, media.position / media.duree)) or 0
  local textes = {
    ui.label({ text = media.titre, maxLines = 1, fontWeight = "semibold", fontSize = 17, color = BLANC }),
    ui.label({ text = media.source, maxLines = 1, fontSize = 14, color = GRIS }),
  }
  if prive then
    textes = mode == "icone" and {} or { ui.label({ text = "Lecture en cours", maxLines = 1, fontWeight = "semibold", fontSize = 17, color = BLANC }) }
  elseif media.duree > 0 then
    table.insert(textes, ui.row({ gap = 8, align = "center" }, {
      ui.label({ text = temps(media.position), fontSize = 11, color = GRIS, width = 40 }),
      ui.progress({ flexGrow = 1, height = 4, radius = 2, progress = progression, fill = BLANC, track = PISTE }),
      ui.label({ text = "-" .. temps(media.duree - media.position), fontSize = 11, color = GRIS, width = 48, textAlign = "end" }),
    }))
  end
  -- Précédent / lecture / suivant : cliquables seulement avec VERROU_MUSIQUE=tout ; sinon seul l'état (sans onClick)
  local commandes
  if mode == "tout" then
    commandes = ui.row({ gap = 0, align = "center", paddingH = 6 }, {
      bouton("player-skip-back-filled", 22, function() commander("previous") end),
      bouton(media.etat == "Playing" and "player-pause-filled" or "player-play-filled", 30, function() commander("play-pause") end),
      bouton("player-skip-forward-filled", 22, function() commander("next") end),
    })
  else
    commandes = ui.row({ gap = 0, align = "center", paddingH = 6 }, {
      bouton(media.etat == "Playing" and "player-pause-filled" or "player-play-filled", 30, nil),
    })
  end
  desktopWidget.render(ui.row({ width = L, height = H, radius = H / 2, fill = NOIR, paddingH = 14, gap = 14, align = "center" }, {
    image,
    ui.column({ flexGrow = 1, gap = 3, justify = "center" }, textes),
    commandes,
  }))
end

-- DEBUT cadence (testé par tests/test_cadence_verrou.py : sous-ensemble commun à Lua et Luau)
-- Écran éteint : plus aucun lancement. Au rallumage : relecture tout de suite. Rien ne joue : toutes les 5 s.
-- (fileExists est l'API de fichiers du plugin : un simple stat, pas un processus lancé.)
function update()
  if noctalia.fileExists(ETEINT) then ecranEteint = true; return end
  local rallume = ecranEteint
  ecranEteint = false
  local pause = (media ~= nil and media.etat == "Playing") and 1000 or 5000
  if rallume or maintenant() - derniereLecture >= pause then lire() end
end
-- FIN cadence

noctalia.setUpdateInterval(1000)
lire()
rendre()

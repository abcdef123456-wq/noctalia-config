--!nonstrict
-- nc/verrou : la musique sur l'écran de verrouillage, en longue capsule noire comme l'île dynamique.
--   Pochette (sinon l'icône de l'appli sur une tuile sombre, comme sur iPhone), titre, artiste ou source,
--   progression avec temps écoulé / restant, précédent / lecture / suivant.
--   Infos : ~/.local/bin/nc-verrou-media (dernier lecteur actif selon playerctld, pochette d'internet mise en cache,
--   fichier d'icône de l'appli). Rien ne s'affiche quand rien ne joue, ni pour un lecteur en pause depuis plus de 15 min.
--   Navigateurs sans métadonnées : « Épisode 3 – Série – Crunchyroll » devient « Épisode 3 – Série », source « Crunchyroll ».
-- Taille : box_width / box_height du widget dans config.toml (680 × 104).

local NOIR, BLANC, GRIS, PISTE, TUILE = "#000000", "#ffffff", "#98989d", "#3a3a3c", "#1c1c1e"
local L, H = 680, 104
local MEDIA = noctalia.expandPath("~/.local/bin/nc-verrou-media")
local NAVIGATEURS = { "firefox", "chrom", "brave", "vivaldi", "opera", "edge", "zen", "librewolf", "floorp" }

local media = nil          -- { etat, titre, source, pochette, icone, duree, position }
local finLecture = nil     -- heure de la dernière pause (ms)
local aJoue = false
local derniereLecture = 0

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

local function lire()
  derniereLecture = maintenant()
  noctalia.runAsync({ MEDIA }, function(r)
    local l = string.gsub(r.stdout or "", "\n$", "")
    local c = {}
    for v in string.gmatch(l .. "\t", "([^\t]*)\t") do table.insert(c, v) end
    if #c < 8 or c[1] == "" or c[1] == "Stopped" or c[2] == "" then
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
      -- Pause : comptée depuis maintenant seulement si on l'a vu jouer (un lecteur déjà en pause reste caché)
      if c[1] == "Playing" then finLecture = nil; aJoue = true
      elseif not finLecture then finLecture = aJoue and maintenant() or 0 end
      media = { etat = c[1], titre = titre, source = source ~= "" and source or c[7], pochette = c[4], icone = c[8],
        duree = (tonumber(c[5]) or 0) / 1e6, position = (tonumber(c[6]) or 0) / 1e6 }
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
  local visible = media ~= nil and (media.etat == "Playing" or (finLecture and finLecture > 0 and maintenant() - finLecture < 15 * 60000))
  if not visible then
    desktopWidget.render(ui.box({ width = L, height = H, opacity = 0 }))
    return
  end
  -- Image de gauche : pochette, sinon icône de l'appli sur une tuile sombre, sinon une note
  local image
  if media.pochette ~= "" and noctalia.fileExists(media.pochette) then
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
  if media.duree > 0 then
    table.insert(textes, ui.row({ gap = 8, align = "center" }, {
      ui.label({ text = temps(media.position), fontSize = 11, color = GRIS, width = 40 }),
      ui.progress({ flexGrow = 1, height = 4, radius = 2, progress = progression, fill = BLANC, track = PISTE }),
      ui.label({ text = "-" .. temps(media.duree - media.position), fontSize = 11, color = GRIS, width = 48, textAlign = "end" }),
    }))
  end
  desktopWidget.render(ui.row({ width = L, height = H, radius = H / 2, fill = NOIR, paddingH = 14, gap = 14, align = "center" }, {
    image,
    ui.column({ flexGrow = 1, gap = 3, justify = "center" }, textes),
    ui.row({ gap = 0, align = "center", paddingH = 6 }, {
      bouton("player-skip-back-filled", 22, function() commander("previous") end),
      bouton(media.etat == "Playing" and "player-pause-filled" or "player-play-filled", 30, function() commander("play-pause") end),
      bouton("player-skip-forward-filled", 22, function() commander("next") end),
    }),
  }))
end

function update()
  if maintenant() - derniereLecture >= 1000 then lire() end
end

noctalia.setUpdateInterval(1000)
lire()
rendre()

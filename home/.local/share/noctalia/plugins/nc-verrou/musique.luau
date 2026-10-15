--!nonstrict
-- nc/verrou : la musique sur l'écran de verrouillage, en longue capsule noire comme l'île dynamique.
--   Pochette (sinon l'icône de l'appli), titre et source, fine barre de progression, précédent / lecture / suivant.
--   Lecteur suivi : le dernier actif (playerctld), comme les touches de musique du clavier. Rien ne s'affiche quand
--   rien ne joue, ni pour un lecteur en pause depuis plus de 15 min.
--   Navigateurs sans métadonnées : « Épisode 3 – Série – Crunchyroll » devient « Épisode 3 – Série », source « Crunchyroll ».

local NOIR, BLANC, GRIS, PISTE = "#000000", "#ffffff", "#98989d", "#3a3a3c"
local L, H = 640, 96
local NAVIGATEURS = { "firefox", "chrom", "brave", "vivaldi", "opera", "edge", "zen", "librewolf", "floorp" }

local media = nil          -- { etat, titre, source, pochette, icone, duree, position }
local finLecture = nil     -- heure de la dernière pause (ms)
local dernierTitre = ""
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

-- Titre d'onglet découpé sur « – », « — », « | », « · » ou « - » entouré d'espaces
local function decouper(titre)
  titre = string.gsub(titre, "^%(%d+%)%s*", "")
  local parties = {}
  local reste = titre
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

local function lire()
  derniereLecture = maintenant()
  -- Vrai lecteur derrière playerctld (le premier de sa liste : le dernier actif), pour son nom et son icône
  noctalia.runAsync({ "sh", "-c", [[n=$(busctl --user get-property org.mpris.MediaPlayer2.playerctld /org/mpris/MediaPlayer2 \
      com.github.altdesktop.playerctld PlayerNames 2>/dev/null | grep -o '"[^"]*"' | head -1 | tr -d '"' | sed 's/^org\.mpris\.MediaPlayer2\.//')
    [ -n "$n" ] || exit 0
    exec playerctl -p "$n" metadata --format '{{status}}	{{title}}	{{artist}}	{{mpris:artUrl}}	{{mpris:length}}	{{position}}	{{playerName}}']] }, function(r)
    local l = string.gsub(r.stdout or "", "\n$", "")
    local c = {}
    for v in string.gmatch(l .. "\t", "([^\t]*)\t") do table.insert(c, v) end
    if #c < 7 or c[1] == "" or c[1] == "Stopped" or c[2] == "" then
      media = nil
    else
      local titre, source = c[2], c[3]
      if source == "" and navigateur(c[7]) then
        local p = decouper(titre)
        if #p > 1 then
          source = p[#p]
          table.remove(p)
          titre = table.concat(p, " – ")
        else
          titre = p[1]
        end
      end
      -- Pause : comptée depuis maintenant seulement si on l'a vu jouer (un lecteur déjà en pause reste caché)
      if c[1] == "Playing" then finLecture = nil; aJoue = true
      elseif not finLecture then finLecture = aJoue and maintenant() or 0 end
      dernierTitre = titre
      local joueur = string.gsub(c[7], "%..*$", "")
      media = { etat = c[1], titre = titre, source = source ~= "" and source or joueur,
        pochette = string.gsub(c[4], "^file://", ""), icone = noctalia.appIconPath(joueur, 64) or nil,
        duree = (tonumber(c[5]) or 0) / 1e6, position = (tonumber(c[6]) or 0) / 1e6 }
    end
    rendre()
  end, 3000)
end

local function commander(action)
  noctalia.runAsync({ "playerctl", "-p", "playerctld", action }, function() lire() end, 3000)
end

local function bouton(nom, taille, action)
  return ui.column({ width = 44, height = 44, radius = 22, align = "center", justify = "center", onClick = action }, {
    ui.glyph({ name = nom, size = taille, color = BLANC }),
  })
end

function rendre()
  -- En pause depuis plus de 15 min, ou rien : rien n'est dessiné
  local visible = media ~= nil and (media.etat == "Playing" or (finLecture and maintenant() - finLecture < 15 * 60000))
  if not visible then
    desktopWidget.render(ui.box({ width = L, height = H, opacity = 0 }))
    return
  end
  local image
  if media.pochette ~= "" and noctalia.fileExists(media.pochette) then
    image = ui.image({ key = "pochette", path = media.pochette, width = 64, height = 64, radius = 14, fit = "cover" })
  elseif media.icone and media.icone ~= "" then
    image = ui.image({ key = "icone", path = media.icone, width = 52, height = 52, fit = "contain" })
  else
    image = ui.column({ width = 64, height = 64, radius = 14, fill = "#2c2c2e", align = "center", justify = "center" },
      { ui.glyph({ name = "music", size = 28, color = GRIS }) })
  end
  local progression = media.duree > 0 and math.max(0, math.min(1, media.position / media.duree)) or 0
  desktopWidget.render(ui.row({ width = L, height = H, radius = H / 2, fill = NOIR, paddingH = 16, gap = 14, align = "center" }, {
    ui.column({ width = 64, height = 64, align = "center", justify = "center" }, { image }),
    ui.column({ flexGrow = 1, gap = 4, justify = "center" }, {
      ui.label({ text = media.titre, maxLines = 1, fontWeight = "semibold", fontSize = 16, color = BLANC }),
      ui.label({ text = media.source, maxLines = 1, fontSize = 13, color = GRIS }),
      ui.progress({ height = 4, radius = 2, progress = progression, fill = BLANC, track = PISTE }),
    }),
    ui.row({ gap = 2, align = "center" }, {
      bouton("player-skip-back-filled", 22, function() commander("previous") end),
      bouton(media.etat == "Playing" and "player-pause-filled" or "player-play-filled", 28, function() commander("play-pause") end),
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

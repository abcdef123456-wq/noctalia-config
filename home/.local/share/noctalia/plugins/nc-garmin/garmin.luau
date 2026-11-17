--!nonstrict
-- nc/garmin : la pastille Santé Garmin de la barre (ajoutée par nc-reglages quand GARMIN_ACTIF et GARMIN_PILULE_BARRE sont à oui).
--   Contenu : cœur MAISON (dessiné ici, en SVG, sans logo de marque) + Body Battery.
--   Clic : la fenêtre Garmin de l'île (qs -c nc-ile ipc call ile garmin).
--   État écrit par nc-garmin : $XDG_RUNTIME_DIR/nc-garmin-barre.json {actif, metriques:{body_battery}}. Ici : un simple stat
--   (taille + date) toutes les 3 s, lecture seulement si le fichier a changé, rien du tout écran éteint (fichier nc-ecran-eteint).
--   Caché si le fichier manque ou si « actif » n'est pas vrai ; une pastille cachée ne garde JAMAIS de zone de clic.
--   Partage d'écran : l'île pose un fichier vide $XDG_RUNTIME_DIR/nc-partage-actif pendant le partage ; tant qu'il existe
--   (vérifié à la même cadence de 3 s), la pastille est cachée. Sans XDG_RUNTIME_DIR on ne peut pas savoir : cachée par prudence.
-- Écrit en Lua simple (sans « += » ni types) : tests/test_garmin_reglages.py le charge aussi avec lua.

local function env(nom)
  local v = noctalia.getenv and noctalia.getenv(nom)
  return (v and v ~= "") and v or nil
end
local RUN = env("XDG_RUNTIME_DIR") or "/tmp"
local SANS_RUN = env("XDG_RUNTIME_DIR") == nil
local ETAT = RUN .. "/nc-garmin-barre.json"
local ETEINT = RUN .. "/nc-ecran-eteint"          -- posé par nc-ecran écran éteint
local PARTAGE = RUN .. "/nc-partage-actif"      -- posé par l'île (Partage.qml) pendant un partage d'écran
local ROUGE = "#ff453a"
local INTERVALLE = 3000

local etat = nil
local signature = ""
local visible = nil
local dernierRendu = nil
local dossier = nil
local enPartage = false

local function partage()
  return SANS_RUN or noctalia.fileExists(PARTAGE)
end

local function montrer(v)
  if v ~= visible then visible = v; barWidget.setVisible(v) end
end

-- Cœur maison, écrit une fois dans le dossier de données du plugin
local FORME = "M12 21C5 15.5 2.5 12 2.5 8.4 2.5 5.7 4.6 3.7 7.1 3.7c1.8 0 3.4 1 4.9 2.9 1.5-1.9 3.1-2.9 4.9-2.9 2.5 0 4.6 2 4.6 4.7C21.5 12 19 15.5 12 21Z"
local function coeur()
  if not dossier then
    dossier = (noctalia.pluginDataDir and noctalia.pluginDataDir() or (RUN .. "/nc-garmin-plugin")) .. "/coeur-v1"
    noctalia.mkdirAll(dossier)
  end
  local f = dossier .. "/coeur.svg"
  if not noctalia.fileExists(f) then
    noctalia.writeFile(f, '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path fill="' .. ROUGE .. '" d="' .. FORME .. '"/></svg>')
  end
  return f
end

local function texte(e)
  local m = type(e.metriques) == "table" and e.metriques or {}
  local b = m.body_battery
  if type(b) ~= "number" then return "" end
  return tostring(math.floor(b + 0.5))
end

function rendre()
  if enPartage or not etat or etat.actif ~= true then montrer(false); return end
  local t = texte(etat)
  montrer(true)
  if t == dernierRendu then return end
  dernierRendu = t
  local enfants = { ui.image({ key = "coeur", path = coeur(), width = 17, height = 17, fit = "contain" }) }
  if t ~= "" then
    table.insert(enfants, ui.label({ text = t, maxLines = 1, fontWeight = "semibold", color = "on_surface" }))
  end
  barWidget.render(ui.row({ gap = 6, align = "center" }, enfants))
  barWidget.setTooltip(t ~= "" and ("Body Battery " .. t) or "Garmin")
end

local function lire()
  local info = noctalia.fileInfo(ETAT)
  if not info then
    signature = ""
    etat = nil
    dernierRendu = nil
    rendre()
    return
  end
  local sig = tostring(info.size) .. ":" .. tostring(info.mtime)
  if sig == signature then return end
  signature = sig
  local brut = noctalia.readFile(ETAT)
  local d = brut and noctalia.json.decode(brut) or nil
  if type(d) == "table" then etat = d else etat = nil end
  dernierRendu = nil
  rendre()
end

function update()
  if noctalia.fileExists(ETEINT) then return end
  local p = partage()
  if p ~= enPartage then enPartage = p; rendre() end
  if not p then lire() end
end

function onClick()
  if not visible then return end
  noctalia.runAsync({ "qs", "-c", "nc-ile", "ipc", "call", "ile", "garmin" }, function() end, 3000)
end

noctalia.setUpdateInterval(INTERVALLE)
montrer(false)
enPartage = partage()
if not enPartage then lire() end

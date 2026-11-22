--!nonstrict
-- nc/verrou : heure de l'écran de verrouillage, comme sur iPhone : petit cadenas (ou ta photo), date au-dessus, très
-- grande heure, et un message à toi en dessous si tu en as mis un.
-- Réglages (nc-reglages → Verrouillage) : VERROU_HORLOGE (grande, fine, petite), VERROU_PHOTO (oui/non),
-- VERROU_MESSAGE (texte ; « aucun » : rien), VERROU_POLICE (familles installées séparées par des virgules ; vide : police de
-- Noctalia), VERROU_COULEUR (blanc, accent). Relus chaque minute. Batterie et musique restent blanches.
-- Taille : box_width / box_height du widget dans config.toml (640 × 280).

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

local L, H = 640, 280
local JOURS = { "dimanche", "lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi" }
local MOIS = { "janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre",
  "novembre", "décembre" }
local DAYS = { "Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday" }
local MONTHS = { "January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
  "November", "December" }
local PHOTO = noctalia.expandPath("~/.face")
local derniere = ""

-- Réglages : ceux du style (style.conf), puis les tiens (reglages.conf)
local function reglages()
  local r = {}
  for _, nom in ipairs({ "~/.config/nc/style.conf", "~/.config/nc/reglages.conf" }) do
    local t = noctalia.readFile(noctalia.expandPath(nom)) or ""
    for k, v in string.gmatch(t, "([%u%d_]+)=([^\n]*)") do
      r[k] = string.gsub(string.gsub(v, "^%s+", ""), "%s+$", "")
    end
  end
  return r
end

-- DEBUT choix : fonctions pures (sous-ensemble commun à Lua et Luau), testées avec lua dans tests/test_verrou_police_couleur.py
-- Première famille de la liste « A, B » présente dans installees (table nom -> true) ; nil : pas de fontFamily
local function choisirPolice(valeur, installees)
  if type(valeur) ~= "string" or type(installees) ~= "table" then return nil end
  for brut in string.gmatch(valeur .. ",", "([^,]*),") do
    local nom = string.gsub(string.gsub(brut, "^%s+", ""), "%s+$", "")
    if nom ~= "" and installees[nom] then return nom end
  end
  return nil
end
-- Familles de la sortie de « fc-list : family » (une ligne par police, alias séparés par des virgules)
local function famillesInstallees(sortie)
  local t = {}
  for ligne in string.gmatch(tostring(sortie or ""), "[^\n]+") do
    for nom in string.gmatch(ligne .. ",", "([^,]*),") do t[nom] = true end
  end
  return t
end
-- Blanc, ou mPrimary de colors.json si VERROU_COULEUR=accent ; fichier absent, de plus de 64 Ko ou mal formé : blanc
local BLANC = "#ffffff"
local function choisirCouleur(reglage, json)
  if reglage ~= "accent" or type(json) ~= "string" or #json > 65536 then return BLANC end
  local c = string.match(json, '"mPrimary"%s*:%s*"(#%x%x%x%x%x%x)"')
  return c or BLANC
end
-- FIN choix

local polices = nil        -- liste fc-list, lue une seule fois au démarrage (nil tant qu'elle n'est pas arrivée)
if noctalia.runAsync then
  noctalia.runAsync({ "fc-list", ":", "family" }, function(r)
    polices = famillesInstallees(r and r.stdout)
    derniere = ""                           -- redessin à la prochaine seconde
  end, 5000)
end

function rendre()
  EN = langue() == "en"                     -- relue chaque minute, comme les réglages
  local t = os.date("*t")
  local heure = string.format("%02d:%02d", t.hour, t.min)
  derniere = heure
  local r = reglages()
  local horloge = r.VERROU_HORLOGE or "grande"
  local message = r.VERROU_MESSAGE or ""
  if message == "aucun" then message = "" end
  local photo = r.VERROU_PHOTO == "oui" and noctalia.readFile(PHOTO) ~= nil
  local taille, graisse = 150, "bold"
  if horloge == "fine" then graisse = "regular" elseif horloge == "petite" then taille, graisse = 96, "semibold" end
  if message ~= "" and taille > 130 then taille = 130 end        -- place pour le message
  local couleur = BLANC
  if r.VERROU_COULEUR == "accent" then
    couleur = choisirCouleur("accent", noctalia.readFile(noctalia.expandPath("~/.config/noctalia/colors.json")))
  end
  local police = polices and choisirPolice(r.VERROU_POLICE, polices)
  local haut = photo and ui.image({ path = PHOTO, width = 56, height = 56, fit = "cover", radius = 28 })
    or ui.glyph({ name = "lock", size = 22, color = "#ffffff", opacity = 0.85 })
  local enfants = {
    haut,
    ui.label({ text = tr(JOURS[t.wday] .. " " .. t.day .. " " .. MOIS[t.month], DAYS[t.wday] .. ", " .. MONTHS[t.month] .. " " .. t.day), fontSize = 24, fontWeight = "semibold",
      color = couleur, opacity = 0.9, fontFamily = police }),
    ui.label({ text = heure, fontSize = taille, fontWeight = graisse, color = couleur, fontFamily = police }),
  }
  if message ~= "" then
    table.insert(enfants, ui.label({ text = message, fontSize = 17, fontWeight = "semibold", color = "#ffffff", opacity = 0.8 }))
  end
  desktopWidget.render(ui.column({ width = L, height = H, align = "center", justify = "center", gap = 2 }, enfants))
end

-- Énergie : écran éteint (fichier nc-ecran-eteint de nc-ecran), rien n'est relu ni redessiné ; l'heure juste dès le rallumage
local ETEINT = (noctalia.getenv("XDG_RUNTIME_DIR") or "/tmp") .. "/nc-ecran-eteint"

function update()
  -- Chaque minute (et dès qu'un réglage change, à la minute suivante)
  if noctalia.fileExists(ETEINT) then return end
  if os.date("%H:%M") ~= derniere then rendre() end
end

noctalia.setUpdateInterval(1000)
rendre()

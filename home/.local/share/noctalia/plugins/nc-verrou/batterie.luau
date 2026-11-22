--!nonstrict
-- nc/verrou : batterie de l'écran de verrouillage, seulement quand le PC est branché (éclair et pourcentage).

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

-- DEBUT couleur : identique dans heure, batterie et musique (tests/test_verrou_police_couleur.py le vérifie) ; Lua et Luau
-- Blanc, ou mPrimary de colors.json si VERROU_COULEUR=accent ; fichier absent, de plus de 64 Ko ou mal formé : blanc
local BLANC = "#ffffff"
local function choisirCouleur(reglage, json)
  if reglage ~= "accent" or type(json) ~= "string" or #json > 65536 then return BLANC end
  local c = string.match(json, '"mPrimary"%s*:%s*"(#%x%x%x%x%x%x)"')
  return c or BLANC
end
-- VERROU_COULEUR dans style.conf puis reglages.conf ; la couleur n'est lue que pour « accent »
local function couleurVerrou(reglage)
  if reglage == nil then
    for _, nom in ipairs({ "~/.config/nc/style.conf", "~/.config/nc/reglages.conf" }) do
      local t = noctalia.readFile(noctalia.expandPath(nom)) or ""
      for k, v in string.gmatch(t, "([%u%d_]+)=([^\n]*)") do
        if k == "VERROU_COULEUR" then reglage = string.gsub(string.gsub(v, "^%s+", ""), "%s+$", "") end
      end
    end
  end
  if reglage ~= "accent" then return BLANC end
  return choisirCouleur(reglage, noctalia.readFile(noctalia.expandPath("~/.config/noctalia/colors.json")))
end
-- FIN couleur

local L, H = 200, 40
local derniere = nil

local function lire(chemin)
  local v = noctalia.readFile(chemin)
  return v and string.gsub(v, "%s+$", "") or nil
end

local function etat()
  for _, nom in ipairs({ "BAT0", "BAT1", "BAT2", "BATT", "CMB0" }) do
    local base = "/sys/class/power_supply/" .. nom
    local cap = lire(base .. "/capacity")
    if cap then return lire(base .. "/status") or "", tonumber(cap) or 0 end
  end
  return nil, 0
end

function rendre()
  local statut, pc = etat()
  local branche = statut == "Charging" or statut == "Full" or statut == "Not charging"
  EN = langue() == "en"
  local couleur = branche and couleurVerrou() or BLANC     -- relue (5 s) seulement quand la batterie est montrée
  local cle = tostring(branche) .. pc .. tostring(EN) .. couleur
  if cle == derniere then return end
  derniere = cle
  if not statut or not branche then
    desktopWidget.render(ui.box({ width = L, height = H, opacity = 0 }))
    return
  end
  desktopWidget.render(ui.row({ width = L, height = H, align = "center", justify = "center", gap = 6 }, {
    ui.glyph({ name = "bolt", size = 18, color = "#30d158" }),
    ui.label({ text = tr(pc .. " %", pc .. "%"), fontSize = 16, fontWeight = "semibold", color = couleur }),
  }))
end

-- Énergie : écran éteint (fichier nc-ecran-eteint de nc-ecran), plus aucune lecture ; à jour dès le rallumage
local ETEINT = (noctalia.getenv("XDG_RUNTIME_DIR") or "/tmp") .. "/nc-ecran-eteint"

function update()
  if noctalia.fileExists(ETEINT) then return end
  rendre()
end

noctalia.setUpdateInterval(5000)
rendre()

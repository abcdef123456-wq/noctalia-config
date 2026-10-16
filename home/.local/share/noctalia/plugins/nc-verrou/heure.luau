--!nonstrict
-- nc/verrou : heure de l'écran de verrouillage, comme sur iPhone : petit cadenas (ou ta photo), date au-dessus, très
-- grande heure, et un message à toi en dessous si tu en as mis un.
-- Réglages (nc-reglages → Verrouillage) : VERROU_HORLOGE (grande, fine, petite), VERROU_PHOTO (oui/non),
-- VERROU_MESSAGE (texte ; « aucun » : rien). Relus chaque minute.
-- Taille : box_width / box_height du widget dans config.toml (640 × 280).

local L, H = 640, 280
local JOURS = { "dimanche", "lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi" }
local MOIS = { "janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre",
  "novembre", "décembre" }
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

function rendre()
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
  local haut = photo and ui.image({ path = PHOTO, width = 56, height = 56, fit = "cover", radius = 28 })
    or ui.glyph({ name = "lock", size = 22, color = "#ffffff", opacity = 0.85 })
  local enfants = {
    haut,
    ui.label({ text = JOURS[t.wday] .. " " .. t.day .. " " .. MOIS[t.month], fontSize = 24, fontWeight = "semibold",
      color = "#ffffff", opacity = 0.9 }),
    ui.label({ text = heure, fontSize = taille, fontWeight = graisse, color = "#ffffff" }),
  }
  if message ~= "" then
    table.insert(enfants, ui.label({ text = message, fontSize = 17, fontWeight = "semibold", color = "#ffffff", opacity = 0.8 }))
  end
  desktopWidget.render(ui.column({ width = L, height = H, align = "center", justify = "center", gap = 2 }, enfants))
end

function update()
  -- Chaque minute (et dès qu'un réglage change, à la minute suivante)
  if os.date("%H:%M") ~= derniere then rendre() end
end

noctalia.setUpdateInterval(1000)
rendre()

--!nonstrict
-- nc/verrou : heure de l'écran de verrouillage, comme sur iPhone : petit cadenas, date au-dessus, très grande heure.
-- Taille : box_width / box_height du widget dans config.toml (640 × 280).

local L, H = 640, 280
local JOURS = { "dimanche", "lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi" }
local MOIS = { "janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre",
  "novembre", "décembre" }
local derniere = ""

function rendre()
  local t = os.date("*t")
  local heure = string.format("%02d:%02d", t.hour, t.min)
  derniere = heure
  desktopWidget.render(ui.column({ width = L, height = H, align = "center", justify = "center", gap = 2 }, {
    ui.glyph({ name = "lock", size = 22, color = "#ffffff", opacity = 0.85 }),
    ui.label({ text = JOURS[t.wday] .. " " .. t.day .. " " .. MOIS[t.month], fontSize = 24, fontWeight = "semibold",
      color = "#ffffff", opacity = 0.9 }),
    ui.label({ text = heure, fontSize = 150, fontWeight = "bold", color = "#ffffff" }),
  }))
end

function update()
  if os.date("%H:%M") ~= derniere then rendre() end
end

noctalia.setUpdateInterval(1000)
rendre()

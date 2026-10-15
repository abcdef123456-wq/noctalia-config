--!nonstrict
-- nc/verrou : batterie de l'écran de verrouillage, seulement quand le PC est branché (éclair et pourcentage).

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
  local cle = tostring(branche) .. pc
  if cle == derniere then return end
  derniere = cle
  if not statut or not branche then
    desktopWidget.render(ui.box({ width = L, height = H, opacity = 0 }))
    return
  end
  desktopWidget.render(ui.row({ width = L, height = H, align = "center", justify = "center", gap = 6 }, {
    ui.glyph({ name = "bolt", size = 18, color = "#30d158" }),
    ui.label({ text = pc .. " %", fontSize = 16, fontWeight = "semibold", color = "#ffffff" }),
  }))
end

function update() rendre() end

noctalia.setUpdateInterval(5000)
rendre()

--!nonstrict
-- nc/batterie : le calcul, sans rien lire ni dessiner (puissance, énergie, lissage, temps restant, textes).
-- Écrit en Lua simple (sans « += » ni types) : tests/test_batterie_barre.py le charge aussi avec lua.
local M = {}

M.FENETRE = 5000      -- lissage de la puissance : moyenne des mesures des 5 dernières secondes

-- Fichier uevent d'une batterie (/sys/class/power_supply/BAT*/uevent) : une ligne « POWER_SUPPLY_CLE=valeur » par
-- propriété, tout ce qu'il faut en une seule lecture
function M.lireUevent(texte)
  local p = {}
  for cle, v in string.gmatch(texte or "", "POWER_SUPPLY_([%u%d_]+)=([^\n]*)") do p[cle] = v end
  return p
end

local function nombre(v)
  local n = tonumber(v or "")
  if n == nil then return nil end
  return math.abs(n)     -- certains pilotes donnent un courant ou une puissance négatifs en décharge
end

-- Une batterie, en unités lisibles. Le noyau donne des µW, µWh, µA, µV et µAh ; selon le pilote, l'énergie
-- (energy_*) ou la charge (charge_*, à multiplier par la tension), la puissance (power_now) ou le courant
-- (current_now × voltage_now).
function M.batterie(p)
  local v = nombre(p.VOLTAGE_NOW)
  if not v or v == 0 then v = nombre(p.VOLTAGE_MIN_DESIGN) end
  local volts = v and v / 1e6 or nil
  local function wh(energie, charge)
    local e = nombre(energie)
    if e then return e / 1e6 end
    local c = nombre(charge)
    if c and volts then return c / 1e6 * volts end
    return nil
  end
  local watts = nombre(p.POWER_NOW)
  if watts then
    watts = watts / 1e6
  else
    local i = nombre(p.CURRENT_NOW)
    if i and volts then watts = i / 1e6 * volts end
  end
  return {
    pct = tonumber(p.CAPACITY or ""),
    statut = p.STATUS or "",
    energie = wh(p.ENERGY_NOW, p.CHARGE_NOW),
    pleine = wh(p.ENERGY_FULL, p.CHARGE_FULL),
    puissance = watts,
  }
end

-- Toutes les batteries en une seule (deux batteries : énergies et puissances additionnées)
function M.resumer(liste)
  local bats = {}
  for _, p in ipairs(liste) do
    local b = M.batterie(p)
    if b.pct or b.energie then table.insert(bats, b) end
  end
  if #bats == 0 then return nil end
  local r = { statut = "", energie = 0, pleine = 0, puissance = nil }
  local statuts = {}
  local somme, n = 0, 0
  for _, b in ipairs(bats) do
    statuts[b.statut] = true
    if b.pct then somme = somme + b.pct; n = n + 1 end
    if r.energie and b.energie then r.energie = r.energie + b.energie else r.energie = nil end
    if r.pleine and b.pleine then r.pleine = r.pleine + b.pleine else r.pleine = nil end
    if b.puissance then r.puissance = (r.puissance or 0) + b.puissance end
  end
  if statuts.Charging then r.statut = "Charging"
  elseif statuts.Discharging then r.statut = "Discharging"
  else r.statut = bats[1].statut end
  if #bats == 1 and bats[1].pct then
    r.pct = bats[1].pct
  elseif r.energie and r.pleine and r.pleine > 0 then
    r.pct = r.energie / r.pleine * 100
  elseif n > 0 then
    r.pct = somme / n
  else
    r.pct = 0
  end
  r.pct = math.max(0, math.min(100, r.pct))
  return r
end

-- Moyenne glissante : ajoute la mesure (instant t en ms, puissance w), oublie celles de plus de 5 s
function M.lisser(echantillons, t, w)
  if w then table.insert(echantillons, { t = t, w = w }) end
  while #echantillons > 0 and echantillons[1].t <= t - M.FENETRE do table.remove(echantillons, 1) end
  if #echantillons == 0 then return nil end
  local s = 0
  for _, e in ipairs(echantillons) do s = s + e.w end
  return s / #echantillons
end

-- Branché sur secteur (même règle que Noctalia : en charge, pleine, ou en pause sur secteur)
function M.branche(statut)
  return statut == "Charging" or statut == "Full" or statut == "Not charging"
end

-- Icône à côté de la batterie : éclair en charge, prise quand elle est pleine ou en pause sur secteur
function M.glyphe(statut)
  if statut == "Charging" then return "bolt-filled" end
  if statut == "Full" or statut == "Not charging" then return "plug-filled" end
  return nil
end

-- Secondes avant vide (décharge) ou avant pleine (charge), avec la puissance lissée
function M.restant(r, w)
  if not r or not w or w < 0.05 or not r.energie then return nil end
  local wh
  if r.statut == "Discharging" then
    wh = r.energie
  elseif r.statut == "Charging" and r.pleine then
    wh = math.max(0, r.pleine - r.energie)
  else
    return nil
  end
  return wh / w * 3600
end

-- « 1 h 18 », « 42 min », « < 1 min » ; rien au-delà de deux jours (mesure sans valeur)
function M.duree(s)
  if not s or s ~= s or s > 48 * 3600 then return nil end
  local m = math.floor(s / 60 + 0.5)
  if m < 1 then return "< 1 min", 0 end
  if m < 60 then return m .. " min", m end
  return string.format("%d h %02d", math.floor(m / 60), m % 60), m
end

local function watts(w, en, decimales)
  local t = string.format(decimales and "%.1f" or "%.0f", w)
  if not en then t = string.gsub(t, "%.", ",") end
  return t .. " W"
end

local function pourcent(pct, en)
  local p = tostring(math.floor(pct + 0.5))
  return en and (p .. "%") or (p .. " %")
end

-- Infobulle : « 40,0 W · 1 h 18 restantes », en charge « +65 W · pleine dans 42 min »
function M.infobulle(r, w, en)
  if not r then return "" end
  local d, minutes = M.duree(M.restant(r, w))
  if r.statut == "Discharging" then
    if not w then return pourcent(r.pct, en) end
    if not d then return watts(w, en, true) end
    if en then return watts(w, en, true) .. " · " .. d .. " left" end
    return watts(w, en, true) .. " · " .. d .. (minutes and minutes <= 1 and " restante" or " restantes")
  elseif r.statut == "Charging" then
    if not w or w < 0.05 then return en and ("Charging · " .. pourcent(r.pct, en)) or ("En charge · " .. pourcent(r.pct, en)) end
    if not d then return "+" .. watts(w, en) .. (en and " · charging" or " · en charge") end
    return "+" .. watts(w, en) .. (en and " · full in " or " · pleine dans ") .. d
  elseif r.statut == "Full" then
    return en and "Full · plugged in" or "Pleine · branchée"
  elseif r.statut == "Not charging" then
    return pourcent(r.pct, en) .. (en and " · plugged in, not charging" or " · branchée, pas en charge")
  end
  return pourcent(r.pct, en)
end

return M

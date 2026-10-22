--!nonstrict
-- nc/batterie : la batterie de la barre (à la place du widget battery de Noctalia), avec le même dessin que son mode
-- graphic : corps arrondi, remplissage aux couleurs du thème, pourcentage dedans, couleur d'alerte sous le seuil,
-- éclair (en charge) ou prise (pleine) à côté.
--   Repos : lecture de /sys/class/power_supply/BAT*/uevent toutes les 30 s (un petit fichier par batterie).
--   Survol : lecture tout de suite, puis chaque seconde tant que la souris est dessus ; l'infobulle donne la puissance
--   lissée sur 5 s et le temps restant (« 40,0 W · 1 h 18 restantes », « +65 W · pleine dans 42 min »). Le widget de
--   Noctalia suivait UPower, qui relit la puissance à son rythme (31 W affichés pour 40 W consommés).
--   Clic : île, page Système (actions dans config.toml).  Sans batterie (PC fixe) : caché.
-- Écrit en Lua simple (sans « += » ni types) : tests/test_batterie_barre.py le charge aussi avec lua.
local calc = require("./calcul.luau")

-- Langue (nc-reglages → Apparence → Langue : auto, fr, en ; auto = celle du système)
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

local SYS = "/sys/class/power_supply"
local REPOS, SURVOL, SANS = 30000, 1000, 300000   -- ms entre deux lectures : au repos, au survol, sans batterie
local ALERTE = "error"                            -- warning_color par défaut du widget battery

-- Seuil d'alerte : celui des notifications de Noctalia ([battery] warning_threshold, 10 % par défaut)
local function seuilAlerte()
  if noctalia.getSetting then
    local ok, v = pcall(noctalia.getSetting, "battery.warning_threshold")
    if ok and tonumber(v) then return tonumber(v) end
  end
  return 10
end
local SEUIL = seuilAlerte()

local survol = false
local etat = nil            -- dernière lecture (toutes les batteries en une)
local lissee = nil          -- puissance moyenne des 5 dernières secondes
local echantillons = {}
local dernierStatut = nil
local lectureDepuis = 0     -- lecture en cours (0 : aucune)
local intervalle = 0
local signature, bulle, visible = nil, nil, nil

local function cadence(ms)
  if ms ~= intervalle then intervalle = ms; noctalia.setUpdateInterval(ms) end
end

local function montrer(v)
  if v ~= visible then visible = v; barWidget.setVisible(v) end
end

-- Dessin du mode graphic de Noctalia 5.3 (battery_widget.cpp), en points de la barre : corps 25 × 15 (barre
-- horizontale) ou 18 × 23 (barre verticale, 14 × 22 à 100 %, sans chiffre), coins 4, borne 3 × 7, chiffre de 13 pt
-- réduit pour tenir dans le corps, 2 pt avant l'icône d'état de 13 pt
local function dessin(r)
  local vertical = barWidget.isVertical and barWidget.isVertical() or false
  local pct = math.floor(r.pct + 0.5)
  local alerte = SEUIL > 0 and pct <= SEUIL and not calc.branche(r.statut)
  local fg = alerte and ALERTE or "on_surface"
  local frac = math.max(0, math.min(1, r.pct / 100))
  local chiffre = not (vertical and pct >= 100)
  local L, H = 25, 15
  if vertical then
    if chiffre then L, H = 18, 23 else L, H = 14, 22 end
  end
  -- Fond du corps : le mélange de Noctalia (couleur à 65 % sur « surface ») ; deux fonds superposés, car la capsule de
  -- la barre est translucide et le corps doit rester opaque pour que le chiffre se lise des deux côtés du remplissage
  local remplissage
  if vertical then
    remplissage = ui.column({ width = L, height = H, radius = 4, fill = fg .. "/0.65", justify = "end" }, {
      ui.box({ width = L, height = H * frac, radius = 4, fill = fg, visible = frac > 0 }),
    })
  else
    remplissage = ui.row({ width = L, height = H, radius = 4, fill = fg .. "/0.65", align = "start" }, {
      ui.box({ width = L * frac, height = H, radius = 4, fill = fg, visible = frac > 0 }),
    })
  end
  local texte = tostring(pct)
  local enfants = { remplissage }
  if chiffre then
    -- Le chiffre par-dessus le remplissage : un écart négatif ramène sa zone (même taille que le corps) sur le corps
    table.insert(enfants, ui.row({ width = L, height = H, align = "center", justify = "center" }, {
      ui.label({ text = texte, fontSize = vertical and 11 or (#texte > 2 and 12 or 13), fontWeight = "semibold",
        color = "surface" }),
    }))
  end
  local direction = vertical and ui.column or ui.row
  local corps = direction({ width = L, height = H, radius = 4, fill = "surface", gap = -(vertical and H or L),
    align = "start" }, enfants)
  local borne = ui.box({ width = vertical and 7 or 3, height = vertical and 3 or 7, radius = 2, fill = fg })
  local tout = vertical and { borne, corps } or { corps, borne }
  local g = calc.glyphe(r.statut)
  if g then
    table.insert(tout, ui.box({ width = 2, height = 2, fill = "#00000000" }))
    table.insert(tout, ui.glyph({ name = g, size = 13, color = fg }))
  end
  return direction({ gap = 0, align = "center" }, tout), table.concat({ pct, r.statut, tostring(vertical), fg,
    string.format("%.3f", frac) }, "|")
end

function rendre()
  if not etat then montrer(false); return end
  montrer(true)
  local arbre, sig = dessin(etat)
  if sig ~= signature then
    signature = sig
    barWidget.render(arbre)
  end
  local b = calc.infobulle(etat, lissee, EN)
  if b ~= bulle then
    bulle = b
    barWidget.setTooltip(b)
  end
end

local function recevoir(liste)
  local r = calc.resumer(liste)
  if not r then
    etat, lissee, echantillons = nil, nil, {}
    rendre()
    cadence(SANS)
    return
  end
  -- Charge ↔ décharge : les anciennes mesures ne valent plus rien
  if r.statut ~= dernierStatut then echantillons = {} end
  dernierStatut = r.statut
  lissee = calc.lisser(echantillons, noctalia.nowMs(), r.puissance)
  etat = r
  rendre()
  cadence(survol and SURVOL or REPOS)
end

-- Une lecture : uevent de chaque batterie, sans bloquer (readFileAsync, prévu pour le sysfs)
local function lire()
  local maintenant = noctalia.nowMs()
  if lectureDepuis > 0 and maintenant - lectureDepuis < 5000 then return end
  local noms = {}
  for _, n in ipairs(noctalia.listDir(SYS) or {}) do
    if string.match(n, "^BAT") or string.match(n, "^CMB") then table.insert(noms, n) end
  end
  table.sort(noms)
  if #noms == 0 then recevoir({}); return end
  lectureDepuis = maintenant
  local liste, reste = {}, #noms
  for i, n in ipairs(noms) do
    local chemin = SYS .. "/" .. n .. "/uevent"
    local function fini(texte)
      liste[i] = calc.lireUevent(texte)
      reste = reste - 1
      if reste == 0 then lectureDepuis = 0; recevoir(liste) end
    end
    if not (noctalia.readFileAsync and noctalia.readFileAsync(chemin, fini)) then fini(noctalia.readFile(chemin)) end
  end
end

-- Survol du widget (Noctalia appelle onHover à l'entrée et à la sortie du pointeur)
function onHover(dedans)
  survol = dedans == true or dedans == "true"
  if survol then
    EN = langue() == "en"
    lire()
    cadence(SURVOL)
  else
    cadence(REPOS)
  end
end

function update() lire() end

cadence(REPOS)
lire()

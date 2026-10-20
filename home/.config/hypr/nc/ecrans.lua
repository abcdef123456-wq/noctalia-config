-- Écrans : définition native, placés automatiquement, échelle choisie d'après la taille réelle de l'écran.
--
-- Échelle : mêmes seuils que Hyprland (densité de pixels), mais sans jamais descendre sous 1600 x 900 points
-- utiles. Sans cette limite, un portable 15" en 1920 x 1080 passe à 1,5 : tout paraît zoomé et les panneaux
-- (recherche, fonds d'écran) débordent de l'écran.
-- Fréquence : écran interne d'un portable selon le profil énergétique (voir nc-profile-sync) ; écran externe
-- (bureau, écran 144 Hz branché au portable) : sa fréquence la plus haute dans sa définition native. Le mode
-- « preferred » de l'écran le laisse souvent à 60 Hz.
--
-- Forcer une échelle ou un mode : dans ~/.config/hypr/perso.lua, par exemple
--   hl.monitor({ output = "HDMI-A-1", mode = "preferred", position = "auto", scale = 1 })

local MIN_W, MIN_H = 1600, 900

-- Modes disponibles : { w, h, hz }, dans l'ordre de Hyprland (le mode préféré de l'écran, puis par définition décroissante)
local function modes(m)
    local liste = {}
    for _, v in ipairs(type(m.available_modes) == "table" and m.available_modes or {}) do
        local w, h, hz
        if type(v) == "string" then
            w, h, hz = v:match("^(%d+)x(%d+)@([%d.]+)")
        elseif type(v) == "table" then
            w, h, hz = v.width, v.height, v.refresh_rate or v.refresh or v.refreshRate
        end
        w, h, hz = tonumber(w), tonumber(h), tonumber(hz)
        if w and h and hz then
            if hz > 1000 then hz = hz / 1000 end   -- certaines sources donnent des mHz
            table.insert(liste, { w = w, h = h, hz = hz })
        end
    end
    return liste
end

-- Définition native. Le premier mode de la liste est celui que l'écran dit préférer (sa dalle) ; sur un écran à haute
-- fréquence (100 Hz et plus), c'est lui : beaucoup d'écrans 1440p à 144 Hz annoncent aussi un 3840x2160 à 60 Hz, un
-- mode de compatibilité HDMI pour les consoles, qui n'est pas leur dalle (image réduite par l'écran, 60 Hz, échelle
-- calculée sur une fausse définition). Sinon (écran 4K à 60 Hz, écran sans liste de modes) : la plus grande proposée.
local function native(m, liste)
    local pref = liste[1]
    if pref then
        local max_hz = 0
        for _, md in ipairs(liste) do if md.hz > max_hz then max_hz = md.hz end end
        if max_hz >= 100 and pref.hz >= 100 then return pref.w, pref.h end
    end
    local w, h = m.width or 0, m.height or 0
    for _, md in ipairs(liste) do
        if md.w * md.h > w * h then w, h = md.w, md.h end
    end
    return w, h
end

-- Une échelle est « propre » si elle donne un nombre entier de points dans les deux sens (calcul de Hyprland, en 1/120)
local function propre(w, h, k)
    return (w * 120) % k == 0 and (h * 120) % k == 0
end

function nc.echelle(m)
    local liste = modes(m)
    local w, h = native(m, liste)
    if w <= 0 or h <= 0 then return 1 end
    local voulu = 1
    local pw, ph = m.physical_width or 0, m.physical_height or 0
    if pw > 0 and ph > 0 then
        local ppp = math.sqrt(w * w + h * h) / (math.sqrt(pw * pw + ph * ph) / 25.4)
        if ppp > 200 then voulu = 2 elseif ppp > 140 then voulu = 1.5 end
    end
    local plafond = math.max(1, math.min(w / MIN_W, h / MIN_H))
    voulu = math.max(1, math.min(voulu, plafond))
    local base = math.floor(voulu * 120 + 0.5)
    for i = 0, 120 do
        for _, k in ipairs({ base + i, base - i }) do
            if k >= 120 and k / 120 <= plafond + 1e-9 and propre(w, h, k) then return k / 120 end
        end
    end
    return 1
end

-- Mode dans la définition native : « max » (fréquence la plus haute), « low » (60 Hz) ou un nombre
local function mode_hz(m, voulu)
    local liste = modes(m)
    if not voulu or #liste == 0 then return "preferred" end
    local w, h = native(m, liste)
    local choix
    for _, md in ipairs(liste) do
        if md.w == w and md.h == h then
            local hz = math.floor(md.hz + 0.5)
            if voulu == "max" then
                if not choix or md.hz > choix.hz then choix = md end
            elseif voulu == "low" then
                if hz == 60 then choix = md; break end
                if not choix or md.hz < choix.hz then choix = md end
            elseif tonumber(voulu) then
                -- Un nombre : cette fréquence, sinon la plus proche que l'écran propose
                if not choix or math.abs(md.hz - tonumber(voulu)) < math.abs(choix.hz - tonumber(voulu)) then choix = md end
            end
        end
    end
    if not choix then return "preferred" end
    return string.format("%dx%d@%.2f", choix.w, choix.h, choix.hz)
end

-- ── Projection, comme Windows + P (fenêtre : Super + O, commande nc-ecrans) ──
-- ~/.config/nc/ecrans.conf, écrit par nc-ecrans :
--   PRINCIPAL=nom                                   l'écran du PC (celui du portable, sinon celui choisi)
--   ECRAN<tab>MODE<tab>CÔTÉ<tab>modèle de l'écran   un écran déjà branché et son mode, retenus par son modèle
-- MODE : pc (cet écran éteint), miroir, etendre (vers CÔTÉ : droite, gauche, haut, bas), externe (celui du PC éteint).
-- Un écran jamais vu étend le bureau, à droite.
local proj = { principal = nil, ecrans = {} }
do
    local f = io.open((os.getenv("HOME") or "") .. "/.config/nc/ecrans.conf", "r")
    if f then
        for ligne in f:lines() do
            local p = ligne:match("^PRINCIPAL=(.+)$")
            if p then proj.principal = p end
            local mode, cote, desc = ligne:match("^ECRAN\t([^\t]*)\t([^\t]*)\t(.+)$")
            if mode then proj.ecrans[desc] = { mode = mode, cote = cote } end
        end
        f:close()
    end
end
local COTES = { droite = "auto-right", gauche = "auto-left", haut = "auto-up", bas = "auto-down" }

-- Écran virtuel (partage de bureau) ou de secours (créé par Hyprland quand aucun écran ne reste allumé)
local function virtuel(m) return m.name:match("^HEADLESS") ~= nil or m.name == "FALLBACK" end
-- Un écran est retenu par son modèle (description), sinon par sa prise
local function retenu(m)
    local cle = (m.description or "") ~= "" and m.description or m.name
    return proj.ecrans[cle] or { mode = "etendre", cote = "droite" }
end

-- Écran principal : celui du portable, sinon celui retenu par nc-ecrans, sinon le premier
local function principal()
    if proj.principal then return proj.principal end
    local premier
    for _, m in ipairs(hl.get_monitors()) do
        if m.name:match("^eDP") or m.name:match("^LVDS") or m.name:match("^DSI") then return m.name end
        if not premier and not virtuel(m) then premier = m.name end
    end
    return premier
end

-- Un autre écran allumé en « second écran seulement » : celui du PC s'éteint
local function externe_seul(p)
    for _, m in ipairs(hl.get_monitors()) do
        if m.name ~= p and not virtuel(m) and retenu(m).mode == "externe" then return true end
    end
    return false
end

local function regle(m)
    local interne = m.name:match("^eDP") ~= nil
    local p = principal()
    local spec = {
        output   = m.name,
        mode     = mode_hz(m, interne and nc.profil.hz or "max"),
        position = "auto",
        scale    = nc.echelle(m),
    }
    if virtuel(m) or not p then
        -- écran virtuel (partage de bureau…) : placé automatiquement
    elseif m.name == p then
        if externe_seul(p) then spec = { output = m.name, disabled = true } else spec.position = "0x0" end
    else
        local r = retenu(m)
        if r.mode == "pc" then spec = { output = m.name, disabled = true }
        elseif r.mode == "miroir" then spec.mirror = p
        else spec.position = COTES[r.cote] or "auto-right" end
    end
    hl.monitor(spec)
end

-- Tous les écrans, le principal d'abord (les autres se placent par rapport à lui)
local function tout()
    local p = principal()
    local liste = hl.get_monitors()
    table.sort(liste, function(a, b) return (a.name == p) and b.name ~= p end)
    for _, m in ipairs(liste) do regle(m) end
end

-- Règle par défaut (avant que l'écran ne soit connu), puis une règle précise par écran
hl.monitor({ output = "", mode = "preferred", position = "auto", scale = "auto" })
tout()
hl.on("monitor.added", function()
    tout()
    -- Écran de verrouillage recentré sur l'écran (sa taille réelle, échelle comprise)
    hl.exec_cmd("sleep 2; ~/.local/bin/nc-verrou-place")
end)
hl.on("monitor.removed", function()
    -- Second écran débranché alors que celui du PC était éteint : nc-ecrans le rallume
    hl.exec_cmd("~/.local/bin/nc-ecrans verifier; sleep 1; ~/.local/bin/nc-verrou-place")
end)
hl.on("hyprland.start", function() hl.exec_cmd("sleep 3; ~/.local/bin/nc-verrou-place") end)

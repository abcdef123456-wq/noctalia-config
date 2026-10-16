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

-- Modes disponibles : { w, h, hz }, triés comme Hyprland (plus grande définition d'abord)
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

-- Définition native : la plus grande proposée par l'écran
local function native(m, liste)
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

local function regle(m)
    local interne = m.name:match("^eDP") ~= nil
    hl.monitor({
        output   = m.name,
        mode     = mode_hz(m, interne and nc.profil.hz or "max"),
        position = "auto",
        scale    = nc.echelle(m),
    })
end

-- Règle par défaut (avant que l'écran ne soit connu), puis une règle précise par écran
hl.monitor({ output = "", mode = "preferred", position = "auto", scale = "auto" })
for _, m in ipairs(hl.get_monitors()) do regle(m) end
hl.on("monitor.added", regle)

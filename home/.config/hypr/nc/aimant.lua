-- Aimantation des fenêtres (nc-reglages → Clavier et souris : SAISIE = souris ou les-deux).
-- Lâchée sur un bord de l'écran, une fenêtre se range : en haut elle s'agrandit, sur un côté elle prend la moitié,
-- dans un coin elle prend le quart. Seuls les bords EXTÉRIEURS comptent : le bord que deux écrans partagent laisse passer.
-- Pendant le glisser, l'île montre un cadre d'aperçu (nc/ile, AimantApercu.qml) : un minuteur de 50 ms, armé à l'appui
-- et arrêté au relâchement, lit la place du curseur. Aucun minuteur ne tourne hors d'un glisser.
-- Hyprland n'a aucun événement « début / fin de glisser » : ce sont deux raccourcis (appui, relâchement) qui encadrent.

local M = {}

local ZONES = { "haut", "gauche", "droite", "haut-gauche", "haut-droite", "bas-gauche", "bas-droite" }
M.ZONES = ZONES

-- Un voisin est collé à ce bord, à la hauteur (ou largeur) du curseur : le bord est partagé, donc pas aimanté
local function voisin(ecrans, m, cote, px, py)
    for _, n in ipairs(ecrans) do
        if n ~= m then
            if cote == "gauche" and math.abs(n.x + n.w - m.x) <= 1 and py >= n.y and py < n.y + n.h then return true end
            if cote == "droite" and math.abs(m.x + m.w - n.x) <= 1 and py >= n.y and py < n.y + n.h then return true end
            if cote == "haut" and math.abs(n.y + n.h - m.y) <= 1 and px >= n.x and px < n.x + n.w then return true end
            if cote == "bas" and math.abs(m.y + m.h - n.y) <= 1 and px >= n.x and px < n.x + n.w then return true end
        end
    end
    return false
end

-- Fonction PURE. px, py : curseur (points logiques, global). ecrans : liste de { x, y, w, h, reserve = { gauche, haut,
-- droite, bas } } en points logiques (largeur déjà divisée par l'échelle). bord, coin : seuils en points logiques.
-- marge : FENETRES_MARGE. Renvoie nil, ou la zone (chaîne de ZONES) et le rectangle cible { x, y, w, h } en entiers.
function M.zone(px, py, ecrans, bord, coin, marge)
    if type(px) ~= "number" or type(py) ~= "number" or type(ecrans) ~= "table" then return nil end
    local m
    -- l'écran dont le curseur est dans [x, x + w[ ; sinon (dernier point de la dernière colonne) bord compris
    for _, large in ipairs({ false, true }) do
        for _, e in ipairs(ecrans) do
            local fin_x, fin_y = e.x + e.w, e.y + e.h
            if px >= e.x and py >= e.y and (large and px <= fin_x and py <= fin_y or px < fin_x and py < fin_y) then m = e; break end
        end
        if m then break end
    end
    if not m then return nil end
    local cercle = math.max(coin or 0, bord or 0)       -- un coin ne peut pas être plus petit qu'un bord
    local gauche = not voisin(ecrans, m, "gauche", px, py)
    local droite = not voisin(ecrans, m, "droite", px, py)
    local haut   = not voisin(ecrans, m, "haut", px, py)
    local bas    = not voisin(ecrans, m, "bas", px, py)
    local dg, dd, dh, db = px - m.x, m.x + m.w - px, py - m.y, m.y + m.h - py
    -- sur un bord extérieur : à moins de « bord » ; dans un coin : près d'un bord ET à moins de « coin » de l'autre
    local sur_g, sur_d = gauche and dg <= bord, droite and dd <= bord
    local sur_h, sur_b = haut and dh <= bord, bas and db <= bord
    local pres_g, pres_d = gauche and dg <= cercle, droite and dd <= cercle
    local pres_h, pres_b = haut and dh <= cercle, bas and db <= cercle
    local z
    if sur_g or sur_d or sur_h or sur_b then
        local v = (pres_g and "gauche") or (pres_d and "droite")
        local hz = (pres_h and "haut") or (pres_b and "bas")
        if v and hz then z = hz .. "-" .. v
        elseif sur_h then z = "haut"
        elseif sur_g then z = "gauche"
        elseif sur_d then z = "droite" end
    end
    if not z then return nil end

    local r = m.reserve or {}
    local rg, rh, rd, rb = r.left or r[1] or 0, r.top or r[2] or 0, r.right or r[3] or 0, r.bottom or r[4] or 0
    local g = marge or 10
    local ax, ay = m.x + rg + g, m.y + rh + g
    local aw, ah = m.w - rg - rd - 2 * g, m.h - rh - rb - 2 * g
    local demi, demih = math.floor((aw - g) / 2), math.floor((ah - g) / 2)
    local x, y, w, h = ax, ay, aw, ah
    if z == "gauche" or z == "droite" then w = demi
    elseif z ~= "haut" then w, h = demi, demih end
    if z == "droite" or z == "haut-droite" or z == "bas-droite" then x = ax + demi + g end
    if z == "bas-gauche" or z == "bas-droite" then y = ay + demih + g end
    if z == "bas-gauche" or z == "bas-droite" then h = ah - demih - g end
    return z, { x = math.floor(x), y = math.floor(y), w = math.floor(w), h = math.floor(h) }
end

-- Les écrans de Hyprland, en points logiques
local function ecrans_logiques()
    local liste = {}
    for _, m in ipairs(hl.get_monitors() or {}) do
        local s = (m.scale and m.scale > 0) and m.scale or 1
        -- Écran tourné d'un quart de tour (transform impair) : largeur et hauteur sont données avant la rotation
        local w, h = m.width, m.height
        if (tonumber(m.transform) or 0) % 2 == 1 then w, h = h, w end
        liste[#liste + 1] = { x = m.x, y = m.y, w = w / s, h = h / s, reserve = nc.reserve(m) }
    end
    return liste
end

local function xy(v)
    if type(v) ~= "table" then return nil end
    return v.x or v[1], v.y or v[2]
end

local function zone_au_curseur()
    local px, py = xy(hl.get_cursor_pos())
    if not px then return nil end
    return M.zone(px, py, ecrans_logiques(), nc.reglage("AIMANT_BORD", 40), nc.reglage("AIMANT_COIN", 110),
        nc.reglage("FENETRES_MARGE", 10))
end

-- Prévient l'île : zone de la liste fixe et quatre entiers, rien d'autre dans la commande
local function prevenir(z, r)
    if z and r then
        hl.exec_cmd(string.format("qs -c nc-ile ipc call ile aimant %s %d %d %d %d", z, r.x, r.y, r.w, r.h))
    else
        hl.exec_cmd('qs -c nc-ile ipc call ile aimant "" 0 0 0 0')
    end
end

local GARDE_FOU = 10          -- secondes : un glisser n'est jamais suivi plus longtemps (relâchement manqué)
local minuteur                -- un seul objet, créé au premier appui puis réutilisé
local suivi = false           -- un glisser est en cours
local derniere                -- dernière zone annoncée à l'île
local debut, depart = 0, nil
local avec_super = false     -- le glisser a commencé avec Super maintenu

local function arreter_minuteur()
    if minuteur then pcall(minuteur.set_enabled, minuteur, false) end
    if derniere ~= nil then prevenir(nil) end
    derniere = nil
end

-- Super est-il encore tenu ? En cas de doute (API absente ou en erreur), oui
local function super_tenu()
    for _, nom in ipairs({ "Super_L", "Super_R" }) do
        local ok, v = pcall(hl.is_key_down, nom)
        if not ok then return true end
        if v then return true end
    end
    return false
end

local function pas()
    if not suivi then return end
    -- Super lâché avant le bouton : Hyprland ne joue plus le raccourci de relâchement (il compare les modificateurs
    -- d'à présent) ; on arrête ici, aperçu effacé, sans ranger la fenêtre
    if avec_super and not super_tenu() then suivi = false; arreter_minuteur(); return end
    if os.time() - debut >= GARDE_FOU then suivi = false; arreter_minuteur(); return end
    local z, r = zone_au_curseur()
    if z ~= derniere then
        derniere = z
        prevenir(z, r)
    end
end

-- Appui sur la combinaison de déplacement : arme le suivi
function M.presse(super)
    suivi, derniere, debut, avec_super = true, nil, os.time(), super == true

    depart = { xy(hl.get_cursor_pos()) }
    if not nc.reglage("AIMANT_APERCU", true) then return end        -- sans aperçu, rien à suivre
    if not minuteur then
        local ok, t = pcall(hl.timer, pas, { timeout = 50, type = "repeat" })
        if not ok or not t then return end
        minuteur = t
    end
    pcall(minuteur.set_enabled, minuteur, true)
end

local function adresse_valide(a)
    return type(a) == "string" and a:match("^0x[0-9a-fA-F]+$") ~= nil
end

-- Applique la zone à la fenêtre active
function M.appliquer(w, z, r)
    if not (w and z and r) then return end
    if not w.floating then hl.dispatch(hl.dsp.window.float({ action = "set", window = w })) end
    if z == "haut" then
        if nc.reglage("AIMANT_PLEIN_MASQUE", false) and adresse_valide(w.address) then
            hl.exec_cmd("~/.local/bin/nc-fenetre plein-masquer " .. w.address)
        end
        hl.dispatch(hl.dsp.window.fullscreen({ window = w, mode = "maximized", action = "set" }))
    else
        hl.dispatch(hl.dsp.window.resize({ window = w, x = r.w, y = r.h }))
        hl.dispatch(hl.dsp.window.move({ window = w, x = r.x, y = r.y }))
    end
end

-- Relâchement : arrête le suivi, efface l'aperçu et range la fenêtre si elle a vraiment été glissée
function M.relache()
    if not suivi then return end
    suivi = false
    arreter_minuteur()
    local w = hl.get_active_window()
    local px, py = xy(hl.get_cursor_pos())
    if not (w and px and depart and depart[1]) then return end
    -- un simple clic (bouton latéral Précédent) ne range rien : le curseur doit avoir bougé de plus que le seuil
    if (px - depart[1]) ^ 2 + (py - depart[2]) ^ 2 <= 64 then return end
    local z, r = zone_au_curseur()
    M.appliquer(w, z, r)
end

return M

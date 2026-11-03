-- Aimantation des fenêtres (nc-reglages → Clavier et souris : SAISIE = souris ou les-deux).
-- Lâchée sur un bord de l'écran, une fenêtre se range : en haut elle s'agrandit, sur un côté elle prend la moitié,
-- dans un coin elle prend le quart. Seuls les bords EXTÉRIEURS comptent : le bord que deux écrans partagent laisse passer.
-- Pendant le glisser, l'île montre un cadre d'aperçu (nc/ile, AimantApercu.qml) : un minuteur de 50 ms, armé à l'appui
-- et arrêté au relâchement, lit la place du curseur. Aucun minuteur ne tourne hors d'un glisser.
-- Hyprland n'a aucun événement « début / fin de glisser » : ce sont deux raccourcis (appui, relâchement) qui encadrent.
-- L'état d'AVANT le rangement (rangée ou libre, place et taille) est gardé par adresse : Super + V, la sortie du
-- maximisé ou un nouveau glisser loin des bords remettent la fenêtre comme elle était (Hyprland, lui, ne connaît que
-- l'endroit où elle a été lâchée, parfois à moitié hors de l'écran).

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
-- marge : FENETRES_MARGE. grille (facultatif) : { bordure = FENETRES_BORDURE, espace = FENETRES_ESPACE }.
-- Renvoie nil, ou la zone (chaîne de ZONES), le rectangle cible { x, y, w, h } de la SURFACE (ce que move et resize
-- placent ; Hyprland dessine la bordure autour) et le cadre bordure comprise (pour l'aperçu), en entiers.
-- Même grille que les tuiles : une moitié rangée a exactement la place et la taille d'une tuile de demi-écran.
-- L'écran dont le point est dans [x, x + w[ ; sinon (dernier point de la dernière colonne) bord compris
local function ecran_de(px, py, ecrans)
    for _, large in ipairs({ false, true }) do
        for _, e in ipairs(ecrans) do
            local fin_x, fin_y = e.x + e.w, e.y + e.h
            if px >= e.x and py >= e.y and (large and px <= fin_x and py <= fin_y or px < fin_x and py < fin_y) then return e end
        end
    end
    return nil
end

local function reserve_de(m)
    local r = m.reserve or {}
    return r.left or r[1] or 0, r.top or r[2] or 0, r.right or r[3] or 0, r.bottom or r[4] or 0
end

function M.zone(px, py, ecrans, bord, coin, marge, grille)
    if type(px) ~= "number" or type(py) ~= "number" or type(ecrans) ~= "table" then return nil end
    local m = ecran_de(px, py, ecrans)
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

    local rg, rh, rd, rb = reserve_de(m)
    local g = marge or 10
    local b = math.max(0, tonumber(type(grille) == "table" and grille.bordure) or 0)
    local e = math.max(0, tonumber(type(grille) == "table" and grille.espace) or g / 2)
    -- Cadres bordure comprise : marge g au bord de l'écran, 2·espace entre deux voisines (gaps_in de chacune)
    local ax, ay = m.x + rg + g, m.y + rh + g
    local aw, ah = m.w - rg - rd - 2 * g, m.h - rh - rb - 2 * g
    local demi, demih = math.floor((aw - 2 * e) / 2), math.floor((ah - 2 * e) / 2)
    local x, y, w, h = ax, ay, aw, ah
    if z == "gauche" or z == "droite" then w = demi
    elseif z ~= "haut" then w, h = demi, demih end
    if z == "droite" or z == "haut-droite" or z == "bas-droite" then x = ax + demi + 2 * e end
    if z == "bas-gauche" or z == "bas-droite" then y = ay + demih + 2 * e end
    if z == "bas-gauche" or z == "bas-droite" then h = ah - demih - 2 * e end
    local cadre = { x = math.floor(x), y = math.floor(y), w = math.floor(w), h = math.floor(h) }
    -- la surface est le cadre moins la bordure, dessinée autour par Hyprland
    return z, { x = cadre.x + b, y = cadre.y + b, w = math.max(1, cadre.w - 2 * b), h = math.max(1, cadre.h - 2 * b) }, cadre
end

-- Fonction PURE. Ramène le rectangle { x, y, w, h } dans la zone utile (hors réserves) de son écran : jamais hors de
-- l'écran, jamais plus grand que lui. Sans écran connu, inchangé.
function M.recadrer(r, ecrans)
    if type(r) ~= "table" or type(ecrans) ~= "table" then return r end
    local m = ecran_de(r.x + r.w / 2, r.y + r.h / 2, ecrans) or ecran_de(r.x, r.y, ecrans) or ecrans[1]
    if not m then return r end
    local rg, rh, rd, rb = reserve_de(m)
    local ax, ay, aw, ah = m.x + rg, m.y + rh, m.w - rg - rd, m.h - rh - rb
    local w, h = math.min(r.w, aw), math.min(r.h, ah)
    local x = math.max(ax, math.min(r.x, ax + aw - w))
    local y = math.max(ay, math.min(r.y, ay + ah - h))
    return { x = math.floor(x), y = math.floor(y), w = math.floor(w), h = math.floor(h) }
end

-- Fonction PURE. Une fenêtre a pu refuser sa cible r (taille minimale : l, h plus grands que r.w, r.h) : sa place pour rester
-- entière à l'écran, du côté du bord choisi (une cible à droite garde son bord droit, une cible en bas son bord bas).
-- nil : elle tient dans sa cible (à 2 points près, l'arrondi d'affichage), rien à faire.
function M.recaler(r, l, h, ecrans)
    if type(r) ~= "table" or type(l) ~= "number" or type(h) ~= "number" or type(ecrans) ~= "table" then return nil end
    if l <= r.w + 2 and h <= r.h + 2 then return nil end
    local m = ecran_de(r.x + r.w / 2, r.y + r.h / 2, ecrans)
    if not m then return nil end
    local x, y = r.x, r.y
    if l > r.w and r.x + r.w / 2 > m.x + m.w / 2 then x = r.x + r.w - l end
    if h > r.h and r.y + r.h / 2 > m.y + m.h / 2 then y = r.y + r.h - h end
    local c = M.recadrer({ x = x, y = y, w = l, h = h }, ecrans)
    return c.x, c.y
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
        nc.reglage("FENETRES_MARGE", 10),
        { bordure = nc.reglage("FENETRES_BORDURE", 2), espace = nc.reglage("FENETRES_ESPACE", 4) })
end

-- Prévient l'île : zone de la liste fixe et quatre entiers (le cadre, bordure comprise), rien d'autre dans la commande
local function prevenir(z, cadre)
    if z and cadre then
        hl.exec_cmd(string.format("qs -c nc-ile ipc call ile aimant %s %d %d %d %d", z, cadre.x, cadre.y, cadre.w, cadre.h))
    else
        hl.exec_cmd('qs -c nc-ile ipc call ile aimant "" 0 0 0 0')
    end
end

local function adresse_valide(a)
    return type(a) == "string" and a:match("^0x[0-9a-fA-F]+$") ~= nil
end

local GARDE_FOU = 10          -- secondes : un glisser n'est jamais suivi plus longtemps (relâchement manqué)
local minuteur                -- un seul objet, créé au premier appui puis réutilisé
local suivi = false           -- un glisser est en cours
local derniere                -- dernière zone annoncée à l'île
local debut, depart = 0, nil
local avec_super = false     -- le glisser a commencé avec Super maintenu
local apercu = true           -- le cadre de l'île est demandé pour ce glisser
local RELECTURE = 250         -- ms avant de relire la taille réelle d'une fenêtre rangée (son client répond après coup)
local avant = {}              -- par adresse : l'état d'avant le rangement { libre, x, y, w, h } (voir M.remettre)
local instantane = {}         -- à l'appui : l'état de chaque fenêtre (la glissée est celle sous le curseur, pas forcément l'active)

-- L'état à garder d'une fenêtre, ou nil (maximisée : sa place n'est pas la vraie)
local function etat_de(w)
    if type(w) ~= "table" or not adresse_valide(w.address) or (tonumber(w.fullscreen) or 0) ~= 0 then return nil end
    local x, y = xy(w.at)
    local l, h = xy(w.size)
    if not (x and y and l and h) then return nil end
    return { libre = w.floating == true, x = x, y = y, w = l, h = h }
end

local function fenetres()
    local ok, liste = pcall(hl.get_windows)
    if ok and type(liste) == "table" then return liste end
    return { hl.get_active_window() }
end

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
    -- Super lâché avant le bouton : tout événement clavier termine le glisser (0.56 comme 0.57). C'est un dépôt : la zone
    -- sous le curseur range la fenêtre, comme le cadre le promettait ; relache coupe le suivi, le vrai relâchement ne fait rien
    if avec_super and not super_tenu() then M.relache(); return end
    if os.time() - debut >= GARDE_FOU then suivi = false; arreter_minuteur(); return end
    if not apercu then return end
    local z, _, cadre = zone_au_curseur()
    if z ~= derniere then
        derniere = z
        prevenir(z, cadre)
    end
end

-- Appui sur la combinaison de déplacement : arme le suivi
function M.presse(super)
    suivi, derniere, debut, avec_super = true, nil, os.time(), super == true

    depart = { xy(hl.get_cursor_pos()) }
    instantane = {}
    for _, w in ipairs(fenetres()) do
        if type(w) == "table" and w.address then instantane[w.address] = etat_de(w) end
    end
    local active = hl.get_active_window()
    if type(active) == "table" and active.address and instantane[active.address] == nil then
        instantane[active.address] = etat_de(active)
    end
    apercu = nc.reglage("AIMANT_APERCU", true) and true or false
    -- Sans aperçu, rien à suivre, sauf Super lâché avant le bouton (un glisser commencé avec Super)
    if not apercu and not avec_super then return end
    if not minuteur then
        local ok, t = pcall(hl.timer, pas, { timeout = 50, type = "repeat" })
        if not ok or not t then return end
        minuteur = t
    end
    pcall(minuteur.set_enabled, minuteur, true)
end

-- Applique la zone à la fenêtre active
function M.appliquer(w, z, r)
    if not (w and z and r) then return end
    if z == "haut" then
        -- une tuile reste une tuile (elle retrouve sa place à la sortie du maximisé) ; une libre est maximisée telle quelle
        if nc.reglage("AIMANT_PLEIN_MASQUE", false) and adresse_valide(w.address) then
            hl.exec_cmd("~/.local/bin/nc-fenetre plein-masquer " .. w.address)
        end
        hl.dispatch(hl.dsp.window.fullscreen({ window = w, mode = "maximized", action = "set" }))
    else
        if not w.floating then hl.dispatch(hl.dsp.window.float({ action = "enable", window = w })) end
        hl.dispatch(hl.dsp.window.resize({ window = w, x = r.w, y = r.h }))
        hl.dispatch(hl.dsp.window.move({ window = w, x = r.x, y = r.y }))
        -- Une fenêtre à taille minimale reste plus grande que sa cible : relue une seule fois, puis gardée entière à l'écran
        local a = w.address
        if adresse_valide(a) then
            pcall(hl.timer, function()
                if suivi then return end
                for _, v in ipairs(fenetres()) do
                    if type(v) == "table" and v.address == a then
                        local l, h = xy(v.size)
                        local x, y = M.recaler(r, l, h, ecrans_logiques())
                        if x and (tonumber(v.fullscreen) or 0) == 0 then hl.dispatch(hl.dsp.window.move({ window = v, x = x, y = y })) end
                        return
                    end
                end
            end, { timeout = RELECTURE, type = "oneshot" })
        end
    end
end

-- Remet la fenêtre comme avant son rangement par l'aimant, puis l'oublie. Renvoie true si elle avait un état d'avant,
-- false sinon (rien n'est fait). Rangée d'origine : de retour en tuile. Libre d'origine : sa taille et sa place d'avant,
-- recadrées dans l'écran ; avec le curseur (px, py), lâchée loin des bords, elle reprend sa taille sous le curseur, à la
-- même proportion (comme Windows). Le maximisé est retiré dans les deux cas.
function M.remettre(w, px, py)
    local a = type(w) == "table" and w.address
    local e = a and avant[a]
    if not e then return false end
    avant[a] = nil
    if (tonumber(w.fullscreen) or 0) ~= 0 then
        hl.dispatch(hl.dsp.window.fullscreen({ window = w, mode = "maximized", action = "unset" }))
    end
    if not e.libre then
        if w.floating then hl.dispatch(hl.dsp.window.float({ action = "disable", window = w })) end
        return true
    end
    if not w.floating then hl.dispatch(hl.dsp.window.float({ action = "enable", window = w })) end
    local x, y = e.x, e.y
    if px and py then
        local cx, cy = xy(w.at)
        local cw, ch = xy(w.size)
        if cx and cy and cw and ch and cw > 0 and ch > 0 then
            local fx = math.max(0, math.min(1, (px - cx) / cw))
            local fy = math.max(0, math.min(1, (py - cy) / ch))
            x, y = px - fx * e.w, py - fy * e.h
        end
    end
    local r = M.recadrer({ x = x, y = y, w = e.w, h = e.h }, ecrans_logiques())
    hl.dispatch(hl.dsp.window.resize({ window = w, x = r.w, y = r.h }))
    hl.dispatch(hl.dsp.window.move({ window = w, x = r.x, y = r.y }))
    return true
end

-- Relâchement : arrête le suivi, efface l'aperçu et range la fenêtre si elle a vraiment été glissée
function M.relache()
    if not suivi then return end
    suivi = false
    arreter_minuteur()
    local w = hl.get_active_window()
    local px, py = xy(hl.get_cursor_pos())
    local photo = instantane
    instantane = {}
    if not (w and px and depart and depart[1]) then return end
    -- un simple clic (bouton latéral Précédent) ne range rien : le curseur doit avoir bougé de plus que le seuil
    if (px - depart[1]) ^ 2 + (py - depart[2]) ^ 2 <= 64 then return end
    local z, r = zone_au_curseur()
    local a = w.address
    if z then
        -- l'état d'avant le PREMIER rangement est gardé : passer d'un bord à l'autre ne l'oublie pas
        if a and not avant[a] then avant[a] = photo[a] end
        M.appliquer(w, z, r)
    elseif a and avant[a] then
        M.remettre(w, px, py)           -- lâchée loin des bords : sa taille d'avant (libre) ou sa rangée (tuile)
    end
end

-- Sortie du maximisé par un autre chemin (Super + F, « aller » de nc-fenetre, fermeture d'une masquée…) : la fenêtre
-- retrouve sa place d'avant. Seulement une sortie DURABLE, relue après un court délai : Super + V sur une fenêtre
-- maximisée la fait sortir puis rentrer aussitôt (changeFloatingMode de Hyprland), et le glisser d'une fenêtre
-- maximisée commence par en sortir (c'est le relâchement qui décide alors)
local function sortie_du_maximise(w)
    if not (type(w) == "table" and w.address and avant[w.address]) then return end
    if (tonumber(w.fullscreen) or 0) ~= 0 or suivi then return end
    local a = w.address
    pcall(hl.timer, function()
        if suivi or not avant[a] then return end
        for _, v in ipairs(fenetres()) do
            if type(v) == "table" and v.address == a then
                if (tonumber(v.fullscreen) or 0) == 0 then M.remettre(v) end
                return
            end
        end
    end, { timeout = 150, type = "oneshot" })
end
pcall(hl.on, "window.fullscreen", sortie_du_maximise)
pcall(hl.on, "window.close", function(w)
    if type(w) == "table" and w.address then avant[w.address] = nil end
end)

return M

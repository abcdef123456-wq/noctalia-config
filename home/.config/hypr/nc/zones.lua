-- Zones : la disposition des bureaux rangés par l'IA (Super + Maj + O, Super + Ctrl + O). Les fenêtres restent
-- rangées (en tuiles) : Super + flèches, Super + Maj + flèches, Super + Ctrl + flèches, changer le sens de la division,
-- fermer, ouvrir une fenêtre… marchent comme sur les autres bureaux. Un bureau rangé est un arbre de découpes
-- (comme dwindle) dont les proportions viennent de l'IA :
--   feuille  : { f = "0x…" }                          (l'adresse de la fenêtre)
--   découpe  : { sens = "v" | "h", r = 0.6, a = …, b = … }  (v : a à gauche ; h : a en haut ; r = part de a)
-- nc-ia pose l'arbre (nc.zones_poser) puis la règle du bureau ; « Annuler » le retire (nc.zones_retirer).
-- Les places suivent l'ordre des fenêtres de Hyprland : échanger ou déplacer une fenêtre échange les places.

nc = nc or {}
nc.zones = nc.zones or {}          -- [bureau] = { arbre = …, ordre = { adresses, dans l'ordre de Hyprland } }

local function feuilles(n, l)
    l = l or {}
    if n.f then l[#l + 1] = n else feuilles(n.a, l); feuilles(n.b, l) end
    return l
end

-- Retire la feuille de cette fenêtre : sa voisine prend toute la place de la découpe.
local function retirer(n, adr)
    if n.f then return n.f ~= adr and n or nil end
    local a, b = retirer(n.a, adr), retirer(n.b, adr)
    if not a then return b end
    if not b then return a end
    n.a, n.b = a, b
    return n
end

-- Une nouvelle fenêtre coupe en deux la place de la fenêtre active (sinon la plus grande), dans son sens le plus long.
local function ajouter(z, adr, boites, active)
    local cible, aire = nil, -1
    for _, f in ipairs(feuilles(z.arbre)) do
        local b = boites[f.f]
        local s = b and b.w * b.h or 0
        if f.f == active then cible, aire = f, math.huge elseif s > aire then cible, aire = f, s end
    end
    local b = boites[cible.f] or { w = 1, h = 1 }
    local ancienne = cible.f
    cible.f = nil
    cible.sens, cible.r = b.w >= b.h and "v" or "h", 0.5
    cible.a, cible.b = { f = ancienne }, { f = adr }
end

local function placer(n, box, boites)
    if n.f then boites[n.f] = box return end
    local r = math.max(0.1, math.min(0.9, n.r or 0.5))
    if n.sens == "v" then
        local w = math.floor(box.w * r + 0.5)
        placer(n.a, { x = box.x, y = box.y, w = w, h = box.h }, boites)
        placer(n.b, { x = box.x + w, y = box.y, w = box.w - w, h = box.h }, boites)
    else
        local h = math.floor(box.h * r + 0.5)
        placer(n.a, { x = box.x, y = box.y, w = box.w, h = h }, boites)
        placer(n.b, { x = box.x, y = box.y + h, w = box.w, h = box.h - h }, boites)
    end
end

-- Remet l'arbre d'accord avec les fenêtres du bureau : fermées retirées, échangées suivies, nouvelles ajoutées.
local function suivre(z, adresses, area)
    local presentes, par = {}, {}
    for _, a in ipairs(adresses) do presentes[a] = true end
    for _, f in ipairs(z.arbre and feuilles(z.arbre) or {}) do
        if presentes[f.f] then par[f.f] = f else z.arbre = retirer(z.arbre, f.f) end
    end
    -- Un échange ou un déplacement dans Hyprland change l'ordre : la place de la i-ème suit la i-ème.
    local restantes, connues = {}, {}
    for _, a in ipairs(z.ordre or adresses) do if par[a] then restantes[#restantes + 1] = a end end
    for _, a in ipairs(adresses) do if par[a] then connues[#connues + 1] = a end end
    for i, a in ipairs(restantes) do par[a].f = connues[i] end
    local anciennes = par
    local active = hl.get_active_window()
    active = active and tostring(active.address) or nil
    for _, a in ipairs(adresses) do
        if not anciennes[a] then
            if not z.arbre then
                z.arbre = { f = a }
            else
                local boites = {}
                placer(z.arbre, area, boites)
                ajouter(z, a, boites, active)
            end
        end
    end
    z.ordre = adresses
end

function nc.zones_recalculer(ctx)
    local adresses, cibles, bureau = {}, {}, nil
    for _, t in ipairs(ctx.targets) do
        local w = t.window
        if w then
            local a = tostring(w.address)
            adresses[#adresses + 1], cibles[a] = a, t
            bureau = bureau or (w.workspace and w.workspace.id)
        end
    end
    local z = bureau and nc.zones[bureau]
    if not z then
        for i, t in ipairs(ctx.targets) do t:place(ctx:grid_cell(i, #ctx.targets)) end
        return
    end
    suivre(z, adresses, ctx.area)
    local boites = {}
    if z.arbre then placer(z.arbre, ctx.area, boites) end
    for a, t in pairs(cibles) do
        if boites[a] then t:place(boites[a]) end
    end
end

-- Les messages de disposition : changer le sens de la division (togglesplit), inverser (swapsplit),
-- agrandir / rétrécir de dx, dy points (resize dx dy, envoyé par Super + Ctrl + flèches sur un bureau rangé).
function nc.zones_message(ctx, msg)
    local w = hl.get_active_window()
    local ws = w and w.workspace and w.workspace.id
    local z = ws and nc.zones[ws]
    if not z or not z.arbre then return end
    local adr = tostring(w.address)
    local chemin = {}
    local function trouver(n)
        if n.f then return n.f == adr end
        chemin[#chemin + 1] = n
        if trouver(n.a) or trouver(n.b) then return true end
        chemin[#chemin] = nil
        return false
    end
    if not trouver(z.arbre) then return end
    local parent = chemin[#chemin]
    local mot, dx, dy = msg:match("^(%S+)%s*(%-?[%d.]*)%s*(%-?[%d.]*)")
    if mot == "togglesplit" and parent then
        parent.sens = parent.sens == "v" and "h" or "v"
    elseif mot == "swapsplit" and parent then
        parent.a, parent.b = parent.b, parent.a
    elseif mot == "resize" then
        -- Comme dwindle : dx > 0 élargit la fenêtre, dx < 0 la rétrécit, en bougeant la découpe la plus proche dans ce sens.
        for sens, d in pairs({ v = { tonumber(dx) or 0, ctx.area.w }, h = { tonumber(dy) or 0, ctx.area.h } }) do
            if d[1] ~= 0 then
                for i = #chemin, 1, -1 do
                    local n = chemin[i]
                    if n.sens == sens then
                        local enfant = chemin[i + 1]
                        local cote = ((enfant and n.a == enfant) or (not enfant and n.a.f == adr)) and 1 or -1
                        n.r = math.max(0.1, math.min(0.9, (n.r or 0.5) + cote * d[1] / d[2]))
                        break
                    end
                end
            end
        end
    else
        return false
    end
end

-- Poser l'arbre d'un bureau (nc-ia) puis lui donner cette disposition ; la retirer rend la disposition habituelle
-- (dwindle ou master, nc-reglages → Fenêtres), avec son ancien arbre.
function nc.zones_poser(bureau, arbre)
    nc.zones[bureau] = { arbre = arbre }
    hl.workspace_rule({ workspace = tostring(bureau), layout = "lua:nc-zones" })
end

function nc.zones_retirer(bureau)
    nc.zones[bureau] = nil
    hl.workspace_rule({ workspace = tostring(bureau),
                        layout = (nc.reglage("FENETRES_DISPOSITION", "dwindle") == "master") and "master" or "dwindle" })
end

-- Hyprland sans dispositions en Lua (avant hl.layout.register) : nc.zones_dispo reste faux et nc-ia range comme avant
-- (fenêtres libres posées à leur place)
nc.zones_dispo = false
if hl.layout and hl.layout.register and hl.workspace_rule then
    nc.zones_dispo = pcall(function()
        hl.layout.register("nc-zones", { recalculate = nc.zones_recalculer, layout_msg = nc.zones_message })
    end)
end

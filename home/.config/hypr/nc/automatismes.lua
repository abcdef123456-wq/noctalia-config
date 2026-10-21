-- Automatismes : le bureau réagit tout seul.
--   Barre             : réaffichée quand une fenêtre sort du plein écran
--   Halo musical      : le halo de la fenêtre active pulse sur les basses de la musique (nc-pouls appelle nc.halo)
--   Mode jeu auto     : un jeu s'ouvre -> mode jeu + profil Performance ; le dernier jeu fermé -> tout revient
--   Marque-pages      : Super + Ctrl + 1…4 attache la fenêtre active à la touche, puis la ramène d'où que tu sois
--   Fenêtres flottantes : chaque appli flottante se rouvre à la taille et à la place où tu l'as laissée
-- L'état qui doit survivre aux rechargements de la config est gardé dans des fichiers (session ou ~/.local/state).

local RUN   = (os.getenv("XDG_RUNTIME_DIR") or "/tmp") .. "/"
local STATE = (os.getenv("XDG_STATE_HOME") or (os.getenv("HOME") .. "/.local/state")) .. "/noctalia-config/"

local function lire(chemin)
    local f = io.open(chemin)
    if not f then return nil end
    local t = f:read("a")
    f:close()
    return t
end

local function ecrire(chemin, texte)
    local f = io.open(chemin .. ".tmp", "w")
    if not f then return end
    f:write(texte)
    f:close()
    os.rename(chemin .. ".tmp", chemin)
end

-- ── Barre après le plein écran ──────────────────────────────────────────────
-- Une fenêtre sort du plein écran (Super + F, vidéo, jeu) : la barre de Noctalia est réaffichée. Avec certaines
-- versions de Noctalia et de Hyprland (Debian), elle restait cachée alors que l'île revenait.
hl.on("window.fullscreen", function(w)
    if w and (tonumber(w.fullscreen) or 0) == 0 then
        hl.exec_cmd("sleep 0.3; noctalia msg bar-show >/dev/null 2>&1")
    end
end)

-- ── Halo musical ────────────────────────────────────────────────────────────
-- n de 0 (silence) à 1 (basse forte) : le halo de la fenêtre active s'intensifie et s'élargit, sa bordure s'éclaircit.
-- Couleurs de départ lues au chargement (celles du fond d'écran, nc/couleurs.lua) ; n = 0 les remet telles quelles.
-- Sans effet en Économie et en mode jeu (ombres coupées).
local function argb(c)   -- « 0xAARRGGBB » -> a, r, g, b
    local a, r, g, b = tostring(c):match("0x(%x%x)(%x%x)(%x%x)(%x%x)")
    if not a then return nil end
    return tonumber(a, 16), tonumber(r, 16), tonumber(g, 16), tonumber(b, 16)
end
local function rgba(r, g, b, a)
    return string.format("rgba(%02x%02x%02x%02x)", math.floor(r + 0.5), math.floor(g + 0.5), math.floor(b + 0.5), math.floor(a + 0.5))
end
local base_portee = tonumber(hl.get_config("decoration.shadow.range")) or 22
local base_ombre  = hl.get_config("decoration.shadow.color")
local base_bord   = hl.get_config("general.col.active_border")

function nc.halo(n)
    if not nc.flou_actif then return end
    n = math.max(0, math.min(1, tonumber(n) or 0))
    local reglage = { decoration = { shadow = { range = math.floor(base_portee + n * 18 + 0.5) } } }
    local a, r, g, b = argb(base_ombre and base_ombre.colors and base_ombre.colors[1])
    if a then reglage.decoration.shadow.color = rgba(r, g, b, a + (0xF0 - a) * n) end
    if base_bord and base_bord.colors then
        local couleurs = {}
        for _, c in ipairs(base_bord.colors) do
            local ca, cr, cg, cb = argb(c)
            if not ca then couleurs = nil break end
            local k = 0.55 * n   -- vers le blanc
            couleurs[#couleurs + 1] = rgba(cr + (255 - cr) * k, cg + (255 - cg) * k, cb + (255 - cb) * k, ca)
        end
        if couleurs then reglage.general = { col = { active_border = { colors = couleurs, angle = base_bord.angle or 45 } } } end
    end
    hl.config(reglage)
end

-- ── Mode jeu automatique ────────────────────────────────────────────────────
-- Jeux reconnus : Steam / Proton (steam_app_…), gamescope, jeux Windows (….exe). Le profil d'avant est noté dans
-- un fichier : il est remis à la fermeture du dernier jeu, avec la sortie du mode jeu (s'il a été mis par ici).
local JEU_AUTO = RUN .. "nc-jeu-auto"

local function est_jeu(w)
    local c = w and w.class or ""
    return c:match("^steam_app_") ~= nil or c == "gamescope" or c:lower():match("%.exe$") ~= nil
end

hl.on("window.open", function(w)
    if not est_jeu(w) or lire(JEU_AUTO) then return end
    ecrire(JEU_AUTO, nc.profil.profil or "balanced")
    hl.exec_cmd("noctalia msg power-set performance")
    if not nc.jeu then nc.mode_jeu() end
end)

hl.on("window.close", function(w)
    if not est_jeu(w) then return end
    local avant = lire(JEU_AUTO)
    if not avant then return end
    for _, autre in ipairs(hl.get_windows()) do
        if autre.address ~= w.address and est_jeu(autre) then return end   -- un autre jeu tourne encore
    end
    os.remove(JEU_AUTO)
    hl.exec_cmd("noctalia msg power-set " .. avant)
    if nc.jeu then nc.mode_jeu() end
end)

-- ── Marque-pages de fenêtres ────────────────────────────────────────────────
-- Super + Ctrl + N : 1er appui, la fenêtre active est attachée à N ; ensuite, N amène à elle (son bureau compris) ;
-- depuis la fenêtre marquée, N revient à la fenêtre d'avant. Super + Ctrl + Maj + N : attacher la fenêtre active à N.
local MARQUES = RUN .. "nc-marques"

local function marques()
    local m = {}
    for n, adr in (lire(MARQUES) or ""):gmatch("(%d+)=(%S+)") do m[tonumber(n)] = adr end
    return m
end

local function sauver(m)
    local t = {}
    for n, adr in pairs(m) do t[#t + 1] = n .. "=" .. adr end
    ecrire(MARQUES, table.concat(t, "\n"))
end

local function fenetre(adr)
    for _, w in ipairs(hl.get_windows()) do
        if w.address == adr then return w end
    end
end

local function notifier(titre, texte)
    hl.exec_cmd(string.format("notify-send -a %s -t 1800 %s %s", nc.guillemets(nc.t("Fenêtres", "Windows")),
        nc.guillemets(titre), nc.guillemets(texte)))
end

local function attacher(n)
    local w = hl.get_active_window()
    if not w then return end
    local m = marques()
    m[n] = w.address
    sauver(m)
    notifier(nc.t("Marque-page ", "Bookmark ") .. n, (w.class or "")
        .. nc.t(" — Super + Ctrl + " .. n .. " pour y revenir", " — Super + Ctrl + " .. n .. " to come back to it"))
end

local function rappeler(n)
    local m = marques()
    local cible = m[n] and fenetre(m[n])
    if not cible then return attacher(n) end
    local active = hl.get_active_window()
    if active and active.address == cible.address then
        hl.dispatch(hl.dsp.focus({ last = true }))
    else
        hl.dispatch(hl.dsp.focus({ window = "address:" .. cible.address }))
    end
end

nc.attacher, nc.rappeler = attacher, rappeler   -- aussi pour hyprctl eval / tes scripts

for n = 1, 4 do
    local code = 9 + n
    hl.bind("SUPER + CTRL + code:" .. code, function() rappeler(n) end,
        { description = "Fenêtres|" .. nc.t("Marque-pages : attacher, puis rappeler la fenêtre (1…4)",
            "Bookmarks: attach, then recall the window (1…4)") })
    hl.bind("SUPER + CTRL + SHIFT + code:" .. code, function() attacher(n) end,
        { description = "Fenêtres|" .. nc.t("Marque-pages : rattacher la fenêtre active (1…4)",
            "Bookmarks: reattach the active window (1…4)") })
end

-- Fenêtres de l'île qui prennent toute la place d'une fenêtre rangée seule (voir « Cockpit JARVIS » plus bas) :
-- ni mémorisées ici, ni centrées par la règle souris-libres
local PLEINE_PLACE = { ["JARVIS"] = true, ["Réglages du bureau"] = true }

-- ── Mémoire des fenêtres flottantes ─────────────────────────────────────────
-- À la fermeture d'une fenêtre flottante, sa taille et sa place (en proportion de l'écran) sont notées par appli ;
-- à sa prochaine ouverture flottante, elle les retrouve. Exclues : terminal déroulant, incrustation vidéo, jeux,
-- cockpit JARVIS (sa place est fixe, voir plus bas).
local MEMOIRE = STATE .. "fenetres-flottantes"
os.execute("mkdir -p '" .. STATE .. "'")

local function cle(w)
    return (w.class or "") .. "|" .. (w.initial_title or "")
end

local function exclue(w)
    local c, t = w.class or "", w.initial_title or ""
    return c == "" or c == "dropterm" or c == "fingerpop" or est_jeu(w) or w.pinned
        or t:match("[Pp]icture") ~= nil or t:match("Incrustation") ~= nil
        or PLEINE_PLACE[t] or PLEINE_PLACE[w.title or ""]
end

local function memoire()
    local m = {}
    for k, x, y, l, h in (lire(MEMOIRE) or ""):gmatch("([^\n]-)=([%d.]+),([%d.]+),([%d.]+),([%d.]+)") do
        m[k] = { tonumber(x), tonumber(y), tonumber(l), tonumber(h) }
    end
    return m
end

local function ecran(w)
    local mon = w.monitor or hl.get_active_monitor()
    if not mon then return nil end
    return mon.x or 0, mon.y or 0, mon.width / mon.scale, mon.height / mon.scale
end

local function xy(v)
    if type(v) ~= "table" then return nil end
    return v.x or v[1], v.y or v[2]
end

hl.on("window.close", function(w)
    if not w or not w.floating or exclue(w) then return end
    if (tonumber(w.fullscreen) or 0) ~= 0 then return end   -- maximisée ou en plein écran : pas sa vraie place
    local mx, my, lw, lh = ecran(w)
    local x, y = xy(w.at)
    local l, h = xy(w.size)
    if not (lw and x and l) then return end
    local m = memoire()
    m[cle(w)] = { (x - mx) / lw, (y - my) / lh, l / lw, h / lh }
    local t = {}
    for k, v in pairs(m) do t[#t + 1] = string.format("%s=%.4f,%.4f,%.4f,%.4f", k, v[1], v[2], v[3], v[4]) end
    ecrire(MEMOIRE, table.concat(t, "\n"))
end)

hl.on("window.open", function(w)
    if not w or not w.floating or exclue(w) then return end
    local v = memoire()[cle(w)]
    if not v then return end
    local mx, my, lw, lh = ecran(w)
    if not lw then return end
    local l, h = math.floor(v[3] * lw + 0.5), math.floor(v[4] * lh + 0.5)
    if l < 120 or h < 80 then return end
    hl.dispatch(hl.dsp.window.resize({ x = l, y = h, window = w }))
    hl.dispatch(hl.dsp.window.move({ x = math.floor(mx + v[1] * lw + 0.5), y = math.floor(my + v[2] * lh + 0.5), window = w }))
end)

-- ── Cockpit JARVIS et fenêtre des réglages ─────────────────────────────────
-- Des fenêtres classiques (règles jarvis-cockpit et nc-reglages-fenetre : flottantes, bordure et arrondi de Hyprland)
-- à la place et à la taille d'une fenêtre rangée seule : la zone utile de leur écran (sous la barre et les panneaux
-- réservés) moins la marge des fenêtres (FENETRES_MARGE). Placées ici, à l'ouverture : la zone réservée n'est connue
-- qu'à ce moment-là, et une fenêtre maximisée par Hyprland n'aurait pas les marges.
hl.on("window.open", function(w)
    if not w or not w.floating or not PLEINE_PLACE[w.title or w.initial_title or ""] then return end
    local m = w.monitor or hl.get_active_monitor()
    local mx, my, lw, lh = ecran(w)
    if not (m and lw) then return end
    local r = type(m.reserved) == "table" and m.reserved or {}
    local rg, rh, rd, rb = r.left or r[1] or 0, r.top or r[2] or 0, r.right or r[3] or 0, r.bottom or r[4] or 0
    local g = nc.reglage("FENETRES_MARGE", 10)
    local arrondi = function(v) return math.floor(v + 0.5) end     -- 2560 / 1,6 vaut 1599,999… en virgule flottante
    hl.dispatch(hl.dsp.window.resize({ x = arrondi(lw - rg - rd - 2 * g), y = arrondi(lh - rh - rb - 2 * g), window = w }))
    hl.dispatch(hl.dsp.window.move({ x = arrondi(mx + rg + g), y = arrondi(my + rh + g), window = w }))
end)

-- Couvercle du portable : en mode « l'écran s'éteint, le PC continue » (nc-reglages, COUVERCLE=ecran), nc-couvercle
-- éteint l'écran et verrouille en fermant, rallume en ouvrant (sinon il ne fait rien : le système met en veille)
pcall(hl.bind, "switch:on:Lid Switch",  hl.dsp.exec_cmd("~/.local/bin/nc-couvercle ferme"), { locked = true })
pcall(hl.bind, "switch:off:Lid Switch", hl.dsp.exec_cmd("~/.local/bin/nc-couvercle ouvre"), { locked = true })

-- Plantage de Quickshell (l'île) : il se relance tout seul, mais ouvrait en plus une fenêtre de rapport en anglais
-- (« Quickshell has crashed »). Elle est fermée et remplacée par une notification ; le détail reste dans
-- ~/.cache/quickshell/crashes et dans « nc-diag rapport ». Cas connu : une erreur de PipeWire (casque qui se
-- déconnecte, appli audio qui se ferme) fait réinitialiser sa connexion au son, et il plante pendant ce temps-là.
local rapports_vus = {}
local function rapport_quickshell(w)
    if not w or w.class ~= "org.quickshell" or rapports_vus[w.address] then return end
    -- La classe est aussi celle des fenêtres normales, dont le cockpit JARVIS.
    -- Le vrai rapport est un processus distinct, lancé avec ces marqueurs par Quickshell
    -- (src/crash/main.cpp, qsCheckCrash). Sans preuve, laisser la fenêtre ouverte.
    local pid = tonumber(w.pid)
    if not pid or pid < 1 or pid ~= math.floor(pid) then return end
    local environnement = lire(string.format("/proc/%d/environ", pid))
    if not environnement then return end
    environnement = "\0" .. environnement
    local plante = environnement:match("%z__QUICKSHELL_CRASH_DUMP_PID=(%d+)%z")
    local dump = environnement:match("%z__QUICKSHELL_CRASH_DUMP_FD=(%d+)%z")
    if not plante or tonumber(plante) < 1 or not dump then return end
    rapports_vus[w.address] = true
    -- Fermée un instant après son ouverture (tout de suite, la demande arrivait trop tôt et était ignorée)
    local q = nc.guillemets
    hl.exec_cmd("sleep 0.4; hyprctl dispatch \"hl.dsp.window.close({ window = 'address:" .. w.address .. "' })\"; notify-send -a "
        .. q(nc.t("Île dynamique", "Dynamic Island")) .. " -i dialog-warning " .. q(nc.t("L’île a redémarré", "The island restarted")) .. " "
        .. q(nc.t("Quickshell a planté (souvent un souci de son) et s’est relancé tout seul. Détails : nc-diag rapport",
            "Quickshell crashed (often an audio glitch) and restarted on its own. Details: nc-diag report")))
end
hl.on("window.open", rapport_quickshell)
hl.on("window.class", rapport_quickshell)

-- Terminal déroulant (Super + touche sous Échap, bureau caché « special:term ») : rangé dès qu'on va ailleurs — une autre
-- fenêtre activée (clic, Alt + Tab, appli qui s'ouvre) ou un autre bureau ; il revient tel quel au prochain appel.
-- Ce qu'on y lance s'ouvre sur le bureau du dessous.
-- Un clic sur le bureau vide à côté : l'île le range aussi (nc-ile, RangeTerminal.qml).
local function ecran_du_terminal()
    for _, m in ipairs(hl.get_monitors()) do
        local s = m.active_special_workspace
        if s and s.name == "special:term" then return m end
    end
end
local function ranger_terminal(m, w)
    local actif = hl.get_active_monitor()
    -- toggle_special agit sur l'écran actif : passer un instant sur celui du terminal, puis revenir à la fenêtre choisie
    if actif and actif.name ~= m.name then hl.dispatch(hl.dsp.focus({ monitor = m.name })) end
    hl.dispatch(hl.dsp.workspace.toggle_special("term"))
    if w and actif and actif.name ~= m.name then hl.dispatch(hl.dsp.focus({ window = "address:" .. w.address })) end
end
hl.on("window.active", function(w)
    if not w or not w.workspace or w.workspace.name == "special:term" then return end
    local m = ecran_du_terminal()
    if m then ranger_terminal(m, w) end
end)
hl.on("workspace.active", function(ws)
    if not ws or not ws.name or ws.name:sub(1, 8) == "special:" then return end
    local m = ecran_du_terminal()
    if m and ws.monitor and ws.monitor.name == m.name then ranger_terminal(m) end
end)
-- Une appli lancée depuis le terminal déroulant (ou pendant qu'il est sorti) s'ouvre sur le bureau affiché dessous, pas
-- dans le bureau caché : elle y prend la main, et le terminal se range (window.active ci-dessus)
hl.on("window.open", function(w)
    if not w or not w.workspace or w.workspace.name ~= "special:term" then return end
    if (w.class or "") == "dropterm" or (w.initial_class or "") == "dropterm" then return end
    local m = w.monitor or hl.get_active_monitor()
    local ws = m and m.active_workspace
    if not ws then return end
    hl.dispatch(hl.dsp.window.move({ workspace = ws.id, follow = false, window = w }))
    hl.dispatch(hl.dsp.focus({ window = "address:" .. w.address }))
end)

-- Fenêtre réduite (nc-fenetre : bureau caché « special:reduites ») activée par le dock, Alt + Tab ou une notification :
-- elle revient sur le bureau affiché au lieu d'ouvrir le bureau caché par-dessus
hl.on("window.active", function(w)
    if w and w.workspace and w.workspace.name == "special:reduites" then
        hl.exec_cmd("~/.local/bin/nc-fenetre aller " .. w.address)
    end
end)

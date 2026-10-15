-- Automatismes : le bureau réagit tout seul.
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

-- ── Halo musical ────────────────────────────────────────────────────────────
-- n de 0 (silence) à 1 (basse forte) ; sans effet en Économie et en mode jeu (ombres coupées)
nc.halo_base = tonumber(hl.get_config("decoration.shadow.range")) or 22
function nc.halo(n)
    if not nc.flou_actif then return end
    n = math.max(0, math.min(1, tonumber(n) or 0))
    hl.config({ decoration = { shadow = { range = math.floor(nc.halo_base + n * 34 + 0.5) } } })
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
    hl.exec_cmd(string.format("notify-send -a Fenêtres -t 1800 %q %q", titre, texte))
end

local function attacher(n)
    local w = hl.get_active_window()
    if not w then return end
    local m = marques()
    m[n] = w.address
    sauver(m)
    notifier("Marque-page " .. n, (w.class or "") .. " — Super + Ctrl + " .. n .. " pour y revenir")
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
        { description = "Fenêtres|Marque-pages : attacher, puis rappeler la fenêtre (1…4)" })
    hl.bind("SUPER + CTRL + SHIFT + code:" .. code, function() attacher(n) end,
        { description = "Fenêtres|Marque-pages : rattacher la fenêtre active (1…4)" })
end

-- ── Mémoire des fenêtres flottantes ─────────────────────────────────────────
-- À la fermeture d'une fenêtre flottante, sa taille et sa place (en proportion de l'écran) sont notées par appli ;
-- à sa prochaine ouverture flottante, elle les retrouve. Exclues : terminal déroulant, incrustation vidéo, jeux.
local MEMOIRE = STATE .. "fenetres-flottantes"
os.execute("mkdir -p '" .. STATE .. "'")

local function cle(w)
    return (w.class or "") .. "|" .. (w.initial_title or "")
end

local function exclue(w)
    local c, t = w.class or "", w.initial_title or ""
    return c == "" or c == "dropterm" or c == "fingerpop" or est_jeu(w) or w.pinned
        or t:match("[Pp]icture") ~= nil or t:match("Incrustation") ~= nil
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

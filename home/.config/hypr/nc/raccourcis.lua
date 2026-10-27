-- Raccourcis clavier et souris.
-- Les touches sont données par leur position (code:NN) : elles restent les mêmes en disposition US, FR ou autre.
-- La description (« Section|Texte ») alimente la fiche Super + / et la commande nc-keys : un raccourci
-- ajouté avec une description y apparaît tout seul. Sections : Applis et barre, Fenêtres, Bureaux, Souris, Système, IA.

local SUPER    = "SUPER"
-- Terminal et gestionnaire de fichiers des raccourcis (nc-reglages → Applications) ; un nom de commande simple seulement
local terminal = nc.reglage("APPLI_TERMINAL", "kitty")
if not terminal:match("^[%w%.%-]+$") then terminal = "kitty" end
local fichiers = ({ nautilus = "nautilus --new-window", thunar = "thunar", dolphin = "dolphin --new-window", nemo = "nemo",
                    ["pcmanfm-qt"] = "pcmanfm-qt", yazi = terminal .. " -e yazi" })[nc.reglage("APPLI_FICHIERS", "nautilus")]
    or "nautilus --new-window"
local barre    = "~/.local/bin/nc-shell-msg "   -- actions envoyées à Noctalia v5

-- Tes changements (commande nc-raccourci) : ~/.config/nc/raccourcis.conf, jamais remplacé par les mises à jour.
-- Une ligne par changement, champs séparés par des tabulations :
--   change  MASQUE:TOUCHE  NOUVELLES TOUCHES      un raccourci de la config déplacé sur d'autres touches
--   aucun   MASQUE:TOUCHE                         un raccourci de la config désactivé
--   ajout   TOUCHES  TYPE  VALEUR  NOM            un raccourci à toi (TYPE : commande, appli, bureau, ile)
-- MASQUE:TOUCHE désigne le raccourci d'origine comme « hyprctl binds » : 64:code:36 pour Super + Entrée.
local perso = { change = {}, ajouts = {} }
do
    local f = io.open((os.getenv("HOME") or "") .. "/.config/nc/raccourcis.conf", "r")
    if f then
        for ligne in f:lines() do
            local c = {}
            for champ in (ligne .. "\t"):gmatch("([^\t]*)\t") do c[#c + 1] = champ end
            if c[1] == "change" and (c[3] or "") ~= "" then perso.change[c[2]] = c[3]
            elseif c[1] == "aucun" and c[2] then perso.change[c[2]] = false
            elseif c[1] == "ajout" and c[5] then table.insert(perso.ajouts, c) end
        end
        f:close()
    end
end

-- Identifiant d'une combinaison : masque des modificateurs et dernière touche, en minuscules
local MASQUES = { SUPER = 64, CTRL = 4, CONTROL = 4, ALT = 8, SHIFT = 1 }
local function id_touches(touches)
    local vus, masque, cle = {}, 0, ""
    for morceau in touches:gmatch("[^+]+") do
        local m = morceau:match("^%s*(.-)%s*$")
        local b = MASQUES[m:upper()]
        if b then
            if not vus[b] then vus[b] = true; masque = masque + b end
        else
            cle = m:lower()
        end
    end
    return masque .. ":" .. cle
end

local function touche(touches, action, description, options)
    local remplace = perso.change[id_touches(touches)]
    if remplace == false then return end          -- désactivé avec nc-raccourci
    options = options or {}
    options.description = description
    if remplace then
        -- entrée « change » écrite à la main dans raccourcis.conf : une touche invalide ne doit pas arrêter le module
        local ok, b = pcall(hl.bind, remplace, action, options)
        if not ok then print("noctalia-config : raccourci " .. tostring(remplace) .. " ignoré (" .. tostring(b) .. ")") end
        return ok and b or nil
    end
    return hl.bind(touches, action, options)
end

-- Description dans la langue choisie : la section (avant « | ») reste en français, nc-keys s'en sert pour classer
local function trad(fr, en)
    return nc.t(fr, (fr:match("^[^|]*|") or "") .. en)
end

local function cmd(c) return hl.dsp.exec_cmd(c) end

-- Taille logique (en points) de l'écran d'une fenêtre
local function taille_ecran(m)
    m = m or hl.get_active_monitor()
    if not m then return nil end
    return m.width / m.scale, m.height / m.scale
end

local function xy(v)
    if type(v) ~= "table" then return 0, 0 end
    return v.x or v[1] or 0, v.y or v[2] or 0
end

-- ── Applis et barre ──────────────────────────────────────────────────────────
touche(SUPER .. " + code:36", cmd(terminal),                       trad("Applis et barre|Terminal", "Terminal"))
-- Espace de code (nc-code) : le sélecteur de projets de l'île (Code.qml, façon Raycast ; sans l'île, le même dans une
-- fenêtre kitty), puis Neovim + l'agent de l'IA + lazygit dans une fenêtre kitty
touche(SUPER .. " + code:53", cmd("~/.local/bin/nc-code"),         trad("Applis et barre|Espace de code (projet, Neovim et agent IA)", "Code workspace (project, Neovim and AI agent)"))
touche(SUPER .. " + SHIFT + code:38", cmd("~/.local/bin/nc-jarvis chat"),    trad("IA|Chat JARVIS", "JARVIS chat"))
touche(SUPER .. " + CTRL + code:38", cmd("~/.local/bin/nc-jarvis tableau"), trad("IA|Cockpit JARVIS", "JARVIS dashboard"))
-- IA du bureau (nc-ia : celle choisie dans nc-reglages → Intelligence artificielle ; coupée, ces touches le disent)
touche(SUPER .. " + code:31", cmd("~/.local/bin/nc-ia menu"), trad("IA|Résumer, traduire… le texte sélectionné", "Summarize, translate… the selected text"))
touche(SUPER .. " + SHIFT + code:31", cmd("~/.local/bin/nc-ia capture"), trad("IA|Expliquer une zone de l'écran", "Explain an area of the screen"))
-- L'IA organise les fenêtres (« L'IA peut agir » : un plan, chaque action confirmée)
touche(SUPER .. " + SHIFT + code:32", cmd("~/.local/bin/nc-ia organiser"), trad("IA|Organiser toutes les fenêtres et les bureaux", "Organize all windows and desktops"))
touche(SUPER .. " + CTRL + code:32", cmd("~/.local/bin/nc-ia organiser --bureau"), trad("IA|Organiser les fenêtres de ce bureau", "Organize this desktop's windows"))
-- Dictée partout (nc-dictee) : maintenir Super + D et parler, relâcher : le texte est écrit dans la fenêtre active ; un
-- appui bref lance une dictée longue, le suivant l'écrit. Relâcher Super avant D finit aussi la dictée (sinon elle
-- resterait ouverte) ; ce test-là ne lance rien tant qu'aucune dictée n'est en cours.
touche(SUPER .. " + code:40", cmd([[sh -c ': > "${XDG_RUNTIME_DIR:-/tmp}/nc-dictee-appui"; exec ~/.local/bin/nc-dictee ptt-debut']]), trad("IA|Dicter (maintenir, relâcher pour écrire)", "Dictate (hold, release to write)"))
-- L'appui et le relâchement sont notés ici, à l'heure exacte : un appui si bref qu'il finit avant que nc-dictee ait
-- démarré n'est pas perdu (le micro resterait ouvert), et sa durée ne dépend pas de la lenteur de Python
local fin_dictee = cmd([[sh -c 'r="${XDG_RUNTIME_DIR:-/tmp}"; : > "$r/nc-dictee-relache"; [ -e "$r/nc-dictee-ptt.json" ] && exec ~/.local/bin/nc-dictee ptt-fin']])
-- Le relâchement suit le raccourci choisi (nc-raccourci) : Super + S à la place de Super + D, il était attendu sur D et
-- la dictée restait ouverte (issue #2)
local dictee = perso.change[id_touches(SUPER .. " + code:40")]
if dictee ~= false then
    hl.bind(dictee or (SUPER .. " + code:40"), fin_dictee, { release = true })
    hl.bind(SUPER .. " + Super_L", fin_dictee, { release = true, non_consuming = true })
    hl.bind(SUPER .. " + Super_R", fin_dictee, { release = true, non_consuming = true })
end
touche(SUPER .. " + code:26", cmd(fichiers),                       trad("Applis et barre|Fichiers", "Files"))
touche(SUPER .. " + code:27", cmd(barre .. "menu"),                trad("Applis et barre|Rechercher (applis, fichiers, calculs)", "Search (apps, files, calculations)"))
touche(SUPER .. " + code:25", cmd(barre .. "wallpapers"),          trad("Applis et barre|Choisir le fond d'écran", "Choose the wallpaper"))
-- Carrousel des sessions (plugin nc/sessions) ; sans lui, le menu de nc-session
touche(SUPER .. " + SHIFT + code:25", cmd(barre .. "sessions"),    trad("Bureaux|Sessions : ouvrir ou enregistrer une disposition", "Sessions: open or save a layout"))
touche(SUPER .. " + code:54", cmd(barre .. "control-center"),      trad("Applis et barre|Centre de contrôle (île)", "Control Center (island)"))
touche(SUPER .. " + code:59", cmd(barre .. "settings"),            trad("Applis et barre|Réglages de la barre", "Bar settings"))
touche(SUPER .. " + ALT + code:59", cmd("~/.local/bin/nc-reglages fenetre"), trad("Applis et barre|Réglages du bureau (fenêtre, avec recherche)", "Desktop settings (window, with search)"))
-- La fiche éditable de l'île Quickshell ; sans elle (île de secours, Quickshell absent), celle de Noctalia
touche(SUPER .. " + code:61", cmd([[sh -c 'qs -c nc-ile ipc call ile fiche >/dev/null 2>&1 || exec ~/.local/bin/nc-shell-msg keys']]),
    trad("Applis et barre|Afficher cette fiche (Modifier : changer, ajouter)", "Show this cheat sheet (Edit: change, add)"))
touche(SUPER .. " + code:33", cmd("~/.local/bin/nc-capture zone"), trad("Applis et barre|Capture d'une zone de l'écran", "Screenshot of an area"))
touche(SUPER .. " + code:49", hl.dsp.workspace.toggle_special("term"), trad("Applis et barre|Terminal déroulant (sous Échap)", "Drop-down terminal (below Esc)"))
-- Presse-papiers : la page de l'île (textes et images), sinon l'historique de Noctalia
touche(SUPER .. " + SHIFT + code:55", cmd("qs -c nc-ile ipc call ile page presse 2>/dev/null || noctalia msg panel-toggle launcher /clipboard"),
    trad("Applis et barre|Historique du presse-papiers", "Clipboard history"))
touche(SUPER .. " + code:60", cmd("noctalia msg panel-toggle launcher /emo"),  trad("Applis et barre|Émojis", "Emoji"))

-- Captures d'écran (nc-capture) : enregistrées dans Images/Captures ET copiées, notification de l'île (clic : annoter)
touche("Print",                 cmd("~/.local/bin/nc-capture ecran"),    trad("Applis et barre|Capture de l'écran", "Screenshot of the screen"))
touche("SHIFT + Print",         cmd("~/.local/bin/nc-capture zone"))     -- comme Super + P (pas répété dans la fiche)
touche(SUPER .. " + SHIFT + code:39", cmd("~/.local/bin/nc-capture retouche"), trad("Applis et barre|Capture d'une zone à annoter", "Screenshot of an area to annotate"))
touche(SUPER .. " + SHIFT + code:28", cmd("~/.local/bin/nc-capture texte"), trad("Applis et barre|Copier le texte d'une zone de l'écran", "Copy the text in an area of the screen"))
-- Vidéo de l'écran (nc-video) : zone ou écran entier ; le même raccourci (ou un clic sur l'île) arrête
touche(SUPER .. " + SHIFT + code:27", cmd("~/.local/bin/nc-video"), trad("Applis et barre|Enregistrer l'écran en vidéo (démarrer / arrêter)", "Record the screen (start / stop)"))

-- ── Fenêtres ─────────────────────────────────────────────────────────────────
-- Fermer : si c'était la seule fenêtre de son programme (Discord & co), le programme est arrêté 5 s plus tard
touche(SUPER .. " + SHIFT + code:24", function()
    local w = hl.get_active_window()
    if not w then return end
    -- Un cockpit Quickshell partage son processus avec les surfaces de l'île,
    -- absentes de get_windows() : sa « dernière fenêtre » n'est pas la dernière interface.
    if w.class == "org.quickshell" then
        hl.dispatch(hl.dsp.window.close())
        return
    end
    -- Terminal kitty : nc-fermer demande, aux flèches, s'il faut fermer alors qu'un programme y tourne encore
    local comm = w.pid and io.open("/proc/" .. w.pid .. "/comm", "r")
    if comm then
        local nom = comm:read("l")
        comm:close()
        -- Shells de la session (île, barre Noctalia et ses réglages) : fermer la fenêtre, jamais le processus,
        -- sinon la barre, les menus et Super + / disparaissent avec elle
        if nom == "quickshell" or nom == "qs" or nom == "noctalia" then
            hl.dispatch(hl.dsp.window.close())
            return
        end
        if nom == "kitty" then
            hl.exec_cmd(string.format("~/.local/bin/nc-fermer %d %s", w.pid, w.address))
            return
        end
    end
    local n = 0
    for _, autre in ipairs(hl.get_windows()) do
        if autre.pid == w.pid then n = n + 1 end
    end
    local seule = n <= 1
    hl.dispatch(hl.dsp.window.close())
    if seule and w.pid and w.pid > 1 then
        hl.exec_cmd(string.format(
            "sleep 5; kill -0 %d 2>/dev/null && { kill -TERM %d; sleep 0.6; kill -0 %d 2>/dev/null && kill -KILL %d; }",
            w.pid, w.pid, w.pid, w.pid))
    end
end, trad("Fenêtres|Fermer (et le programme si dernière)", "Close (and the app if it was the last window)"))

touche(SUPER .. " + code:55", hl.dsp.window.float({ action = "toggle" }), trad("Fenêtres|Fenêtre libre ↔ rangée", "Floating ↔ tiled window"))
-- Réduire (comme le « _ » de Windows) : la fenêtre part dans un bureau caché ; elle revient par la vue des fenêtres,
-- Spotlight, le dock, Alt + Tab ou Super + Ctrl + M (nc-fenetre)
touche(SUPER .. " + code:58", cmd("~/.local/bin/nc-fenetre reduire"), trad("Fenêtres|Masquer la fenêtre", "Hide the window"))
touche(SUPER .. " + code:43", cmd("~/.local/bin/nc-fenetre reduire"), trad("Fenêtres|Masquer la fenêtre (comme macOS)", "Hide the window (like macOS)"))
touche(SUPER .. " + CTRL + code:58", cmd("~/.local/bin/nc-fenetre restaurer"), trad("Fenêtres|Ramener la dernière fenêtre masquée", "Restore the last hidden window"))
touche(SUPER .. " + code:38", cmd("qs -c nc-ile ipc call ile vue"),  trad("Fenêtres|Vue de toutes les fenêtres (glisser sur un bureau : l'y envoyer)", "All windows overview (drag onto a desktop to send it there)"))
touche(SUPER .. " + code:41", hl.dsp.window.fullscreen_state({ internal = 3, client = 0, action = "toggle" }), trad("Fenêtres|Plein écran", "Full screen"))
touche(SUPER .. " + SHIFT + code:33", hl.dsp.window.pseudo(),      trad("Fenêtres|Garder sa taille (pseudo)", "Keep its size (pseudo)"))
touche(SUPER .. " + code:44", hl.dsp.layout("togglesplit"),        trad("Fenêtres|Changer le sens de la division", "Change the split direction"))

for code, sens in pairs({ [113] = "left", [114] = "right", [111] = "up", [116] = "down" }) do
    touche(SUPER .. " + code:" .. code, hl.dsp.focus({ direction = sens }), trad("Fenêtres|Aller à la fenêtre voisine", "Focus the neighboring window"))
    touche(SUPER .. " + SHIFT + code:" .. code, hl.dsp.window.move({ direction = sens }), trad("Fenêtres|Déplacer la fenêtre", "Move the window"))
end

local pas = { [113] = { -40, 0 }, [114] = { 40, 0 }, [111] = { 0, -40 }, [116] = { 0, 40 } }
for code, d in pairs(pas) do
    -- Sur un bureau rangé par l'IA (disposition nc-zones), la découpe bouge par un message de disposition
    touche(SUPER .. " + CTRL + code:" .. code, function()
        local w = hl.get_active_window()
        local ws = w and w.workspace and w.workspace.id
        if ws and nc.zones and nc.zones[ws] and not w.floating then
            hl.dispatch(hl.dsp.layout("resize " .. d[1] .. " " .. d[2]))
        else
            hl.dispatch(hl.dsp.window.resize({ x = d[1], y = d[2], relative = true }))
        end
    end, trad("Fenêtres|Agrandir / rétrécir la fenêtre", "Grow / shrink the window"), { repeating = true })
end

-- Épingler : la fenêtre devient flottante et reste au même endroit sur tous les bureaux (même touche pour libérer)
touche(SUPER .. " + CTRL + code:33", function()
    local w = hl.get_active_window()
    if not w then return end
    if not w.pinned and not w.floating then
        hl.dispatch(hl.dsp.window.float({ action = "set" }))
    end
    hl.dispatch(hl.dsp.window.pin({ action = "toggle" }))
end, trad("Fenêtres|Épingler sur tous les bureaux", "Pin on all desktops"))

-- Taille : flottante centrée à 50 %, puis 70 %, puis 90 % de l'écran
touche(SUPER .. " + CTRL + code:39", function()
    local w = hl.get_active_window()
    local lw, lh = taille_ecran(w and w.monitor)
    if not w or not lw then return end
    if not w.floating then hl.dispatch(hl.dsp.window.float({ action = "set" })) end
    local pct = math.floor(xy(w.size) * 100 / lw + 0.5)
    local n = pct < 60 and 0.7 or (pct < 80 and 0.9 or 0.5)
    hl.dispatch(hl.dsp.window.resize({ x = math.floor(lw * n), y = math.floor(lh * n) }))
    hl.dispatch(hl.dsp.window.center())
end, trad("Fenêtres|Taille : 50 %, 70 %, 90 % de l'écran", "Size: 50%, 70%, 90% of the screen"))

touche(SUPER .. " + CTRL + code:54", hl.dsp.window.center(),       trad("Fenêtres|Recentrer la fenêtre flottante", "Recenter the floating window"))

touche(SUPER .. " + code:42", hl.dsp.group.toggle(),                trad("Fenêtres|Grouper les fenêtres en onglets", "Group windows into tabs"))
touche(SUPER .. " + SHIFT + code:42", hl.dsp.window.move({ out_of_group = true }), trad("Fenêtres|Sortir la fenêtre du groupe", "Take the window out of the group"))
touche(SUPER .. " + CTRL + code:23", hl.dsp.group.next(),           trad("Fenêtres|Onglet suivant du groupe", "Next tab in the group"))
touche(SUPER .. " + CTRL + SHIFT + code:23", hl.dsp.group.prev(),   trad("Fenêtres|Onglet précédent du groupe", "Previous tab in the group"))

touche("ALT + code:23", cmd(barre .. "window-switcher"),            trad("Fenêtres|Passer d'une fenêtre à l'autre", "Switch between windows"))
touche("ALT + SHIFT + code:23", cmd(barre .. "window-switcher"))
touche(SUPER .. " + ALT + code:23", cmd(barre .. "window-switcher"))

-- ── Bureaux ──────────────────────────────────────────────────────────────────
for i = 1, 10 do
    local code = 9 + i   -- touches 1 à 0 de la rangée du haut
    touche(SUPER .. " + code:" .. code, hl.dsp.focus({ workspace = i }), trad("Bureaux|Aller au bureau 1 à 10", "Go to desktop 1 to 10"))
    touche(SUPER .. " + SHIFT + code:" .. code, hl.dsp.window.move({ workspace = i }), trad("Bureaux|Envoyer la fenêtre au bureau 1 à 10", "Send the window to desktop 1 to 10"))
end
touche(SUPER .. " + mouse_down", hl.dsp.focus({ workspace = "e+1" }), trad("Bureaux|Bureau suivant / précédent", "Next / previous desktop"))
touche(SUPER .. " + mouse_up",   hl.dsp.focus({ workspace = "e-1" }), trad("Bureaux|Bureau suivant / précédent", "Next / previous desktop"))
touche(SUPER .. " + code:23", hl.dsp.workspace.toggle_special("magic"), trad("Bureaux|Bureau caché (bloc-notes)", "Hidden desktop (scratchpad)"))

-- Envoyer la fenêtre vers un bureau caché, ou l'en ramener si elle y est déjà.
-- Le terminal caché n'accepte qu'une fenêtre : elle y est flottante et centrée.
local function vers_cache(nom)
    return function()
        local w = hl.get_active_window()
        if not w then return end
        local ici = w.workspace and w.workspace.name or ""
        if ici == "special:" .. nom then
            local ws = hl.get_active_workspace()
            if ws then hl.dispatch(hl.dsp.window.move({ workspace = ws.id })) end
            return
        end
        if nom == "term" and #hl.get_windows({ workspace = "special:term" }) > 0 then
            hl.exec_cmd("notify-send -t 2500 " .. nc.guillemets(nc.t("Terminal caché", "Hidden terminal")) .. " "
                .. nc.guillemets(nc.t("Il contient déjà une fenêtre.", "It already contains a window.")))
            return
        end
        hl.dispatch(hl.dsp.window.move({ workspace = "special:" .. nom, follow = false, window = w }))
        if nom == "term" then
            local lw, lh = taille_ecran(w.monitor)
            hl.dispatch(hl.dsp.window.float({ action = "set", window = w }))
            if lw then hl.dispatch(hl.dsp.window.resize({ x = math.floor(lw * 0.72), y = math.floor(lh * 0.62), window = w })) end
            hl.dispatch(hl.dsp.window.center({ window = w }))
        end
    end
end
touche(SUPER .. " + SHIFT + code:23", vers_cache("magic"), trad("Bureaux|Fenêtre ↔ bureau caché", "Window ↔ hidden desktop"))
touche(SUPER .. " + SHIFT + code:49", vers_cache("term"),  trad("Bureaux|Fenêtre ↔ terminal caché", "Window ↔ hidden terminal"))

-- ── Souris ───────────────────────────────────────────────────────────────────
-- Super + glisser : déplacer la tuile (la lâcher sur une autre fenêtre la place à côté) ; Super + clic droit : redimensionner.
touche(SUPER .. " + mouse:272", hl.dsp.window.drag(),   trad("Souris|Déplacer la fenêtre", "Move the window"),       { mouse = true })
touche(SUPER .. " + mouse:273", hl.dsp.window.resize(), trad("Souris|Redimensionner la fenêtre", "Resize the window"), { mouse = true })
-- Super + Alt : détacher la fenêtre et la poser ou la redimensionner librement (Super + V la remet dans le pavage)
touche(SUPER .. " + ALT + mouse:272", hl.dsp.window.float({ action = "set" }))
touche(SUPER .. " + ALT + mouse:272", hl.dsp.window.drag(),   trad("Souris|Détacher et placer librement", "Detach and place freely"), { mouse = true })
touche(SUPER .. " + ALT + mouse:273", hl.dsp.window.float({ action = "set" }))
touche(SUPER .. " + ALT + mouse:273", hl.dsp.window.resize(), trad("Souris|Détacher et redimensionner librement", "Detach and resize freely"), { mouse = true })
-- Pavé tactile : Super + Maj + appuyer-glisser (un doigt)
touche(SUPER .. " + SHIFT + mouse:272", hl.dsp.window.float({ action = "set" }))
touche(SUPER .. " + SHIFT + mouse:272", hl.dsp.window.resize(), trad("Souris|Redimensionner (pavé tactile)", "Resize (touchpad)"), { mouse = true })

-- Souris sans clavier (nc-reglages → Clavier et souris, SAISIE = souris ou les-deux) : boutons latéraux maintenus pour
-- déplacer (arrière) ou redimensionner (avant) ; un simple clic garde Précédent / Suivant (Alt + ←/→, navigateurs et
-- fichiers). Lâchée en haut de l'écran, une fenêtre libre s'agrandit ; sur le bord gauche ou droit, elle en prend la
-- moitié (comme Windows). Super + clic molette : libre ↔ rangée.
local saisie = nc.reglage("SAISIE", "clavier")
if saisie == "souris" or saisie == "les-deux" then
    pcall(hl.config, { binds = { drag_threshold = 8 } })
    local function aimanter()
        local w, p = hl.get_active_window(), hl.get_cursor_pos()
        local m = w and w.monitor
        if not (w and p and m) or not w.floating then return end
        local px, py = xy(p)
        local lw, lh = taille_ecran(m)
        local r = nc.reserve(m)          -- place de la barre (lue autrement sous Hyprland 0.55)
        local rg, rh, rd, rb = r.left or r[1] or 0, r.top or r[2] or 0, r.right or r[3] or 0, r.bottom or r[4] or 0
        local g = 10
        local ax, ay, aw, ah = m.x + rg + g, m.y + rh + g, lw - rg - rd - 2 * g, lh - rh - rb - 2 * g
        if py <= m.y + rh + 4 then
            hl.dispatch(hl.dsp.window.fullscreen({ window = w, mode = "maximized", action = "set" }))
        elseif px <= m.x + 4 or px >= m.x + lw - 4 then
            local demi = math.floor((aw - g) / 2)
            hl.dispatch(hl.dsp.window.resize({ window = w, x = demi, y = math.floor(ah) }))
            hl.dispatch(hl.dsp.window.move({ window = w, x = math.floor(px <= m.x + 4 and ax or ax + demi + g), y = math.floor(ay) }))
        end
    end
    -- Raccourci « au clic » ou « après un glisser » : gardé seulement si ce Hyprland connaît l'option (sinon il partirait
    -- dès l'appui, en même temps que le déplacement)
    local function si_compris(drapeau, touches, action)
        local ok, b = pcall(touche, touches, action, nil, { mouse = drapeau == "click", [drapeau] = true })
        if ok and b and b[drapeau] ~= true and b.remove then pcall(b.remove, b) end
    end
    touche("mouse:275", hl.dsp.window.drag(), trad("Souris|Bouton latéral arrière maintenu : déplacer", "Hold back side button: move"), { mouse = true })
    touche("mouse:276", hl.dsp.window.resize(), trad("Souris|Bouton latéral avant maintenu : redimensionner", "Hold forward side button: resize"), { mouse = true })
    if hl.dsp.send_shortcut then
        si_compris("click", "mouse:275", hl.dsp.send_shortcut({ mods = "ALT", key = "Left" }))
        si_compris("click", "mouse:276", hl.dsp.send_shortcut({ mods = "ALT", key = "Right" }))
    end
    si_compris("drag", "mouse:275", aimanter)
    si_compris("drag", SUPER .. " + mouse:272", aimanter)
    touche(SUPER .. " + mouse:274", hl.dsp.window.float({ action = "toggle" }), trad("Souris|Fenêtre libre ↔ rangée", "Floating ↔ tiled window"))
end

-- ── Système ──────────────────────────────────────────────────────────────────
touche(SUPER .. " + code:46", cmd(barre .. "lock"),                 trad("Système|Verrouiller l'écran", "Lock the screen"))
touche(SUPER .. " + SHIFT + code:9", cmd(barre .. "session"),       trad("Système|Verrouiller et mettre en veille", "Lock and sleep"))
touche(SUPER .. " + ALT + code:33", cmd(barre .. "power-cycle"),    trad("Système|Changer de profil d'énergie", "Switch power profile"))
touche(SUPER .. " + ALT + code:42", function() nc.mode_jeu() end,   trad("Système|Mode jeu (effets coupés, pas de notifications)", "Game Mode (effects off, no notifications)"))
touche(SUPER .. " + code:57", cmd("noctalia msg nightlight-force-toggle"), trad("Système|Lumière de nuit", "Night light"))
-- Projection (comme Windows + P) : miroir, étendre, un seul écran (nc-ecrans) ; sans l'île, passe au mode suivant.
-- Aussi la touche « écran / projecteur » des portables (XF86Display)
local projection = cmd("qs -c nc-ile ipc call ile projection 2>/dev/null || ~/.local/bin/nc-ecrans suivant")
touche(SUPER .. " + code:32", projection, trad("Système|Projeter sur un second écran (miroir, étendre…)", "Project to a second display (mirror, extend…)"))
pcall(touche, "XF86Display", projection)
local halo = nc.guillemets(nc.t("Halo musical", "Music Glow"))
touche(SUPER .. " + ALT + code:58", cmd("systemctl --user is-active --quiet nc-pouls"
    .. " && { systemctl --user stop nc-pouls; notify-send -a " .. halo .. " -t 2000 "
    .. nc.guillemets(nc.t("Halo musical coupé", "Music glow off")) .. "; }"
    .. " || { systemctl --user start nc-pouls; notify-send -a " .. halo .. " -t 2500 "
    .. nc.guillemets(nc.t("Halo musical activé", "Music glow on")) .. " "
    .. nc.guillemets(nc.t("Le halo suit les basses quand de la musique joue.", "The glow follows the bass when music is playing.")) .. "; }"),
    trad("Système|Halo musical (pulse sur les basses)", "Music glow (pulses with the bass)"))
touche(SUPER .. " + SHIFT + code:57", cmd("noctalia msg notification-dnd-toggle"), trad("Système|Ne pas déranger", "Do Not Disturb"))

-- Loupe : zoom autour du curseur (Super + Ctrl + molette, ou Super + = / Super + -)
local function loupe(facteur)
    return function()
        local z = tonumber(hl.get_config("cursor.zoom_factor")) or 1
        z = math.max(1, math.min(8, z * facteur))
        if z < 1.05 then z = 1 end
        hl.config({ cursor = { zoom_factor = z } })
    end
end
touche(SUPER .. " + CTRL + mouse_up",   loupe(1.25), trad("Système|Loupe : zoomer / dézoomer", "Magnifier: zoom in / out"))
touche(SUPER .. " + CTRL + mouse_down", loupe(0.8),  trad("Système|Loupe : zoomer / dézoomer", "Magnifier: zoom in / out"))
touche(SUPER .. " + code:21", loupe(1.25), trad("Système|Loupe : zoomer / dézoomer", "Magnifier: zoom in / out"), { repeating = true })
touche(SUPER .. " + code:20", loupe(0.8),  trad("Système|Loupe : zoomer / dézoomer", "Magnifier: zoom in / out"), { repeating = true })
touche(SUPER .. " + SHIFT + code:58",
    cmd("command -v hyprshutdown >/dev/null 2>&1 && hyprshutdown || hyprctl dispatch 'hl.dsp.exit()'"), trad("Système|Quitter la session", "Log out"))
touche(SUPER .. " + code:70", cmd("systemctl poweroff"),            trad("Système|Éteindre", "Shut down"))
touche(SUPER .. " + code:71", cmd("systemctl reboot"),              trad("Système|Redémarrer", "Restart"))

-- Touches multimédia (actives aussi sur l'écran de verrouillage)
local media = trad("Système|Son, luminosité, musique", "Sound, brightness, music")
-- L'île dynamique (plugin nc/ile) montre le nouveau niveau, à la place des bulles de Noctalia
local function ile(evenement)
    return "; { qs -c nc-ile ipc call ile " .. evenement .. " || noctalia msg plugin nc/ile:pilule all " .. evenement .. "; } >/dev/null 2>&1"
end
-- Pas du volume et volume maximal (100 %, ou 150 % pour des haut-parleurs faibles) : nc-reglages
local vol_pas = math.max(1, math.min(20, math.floor(nc.reglage("VOLUME_PAS", 5))))
local vol_max = nc.reglage("VOLUME_MAX", "100") == "150" and "1.5" or "1"
local monter = "wpctl set-volume -l " .. vol_max .. " @DEFAULT_AUDIO_SINK@ " .. vol_pas .. "%+"
local baisser = "wpctl set-volume @DEFAULT_AUDIO_SINK@ " .. vol_pas .. "%-"
touche("XF86AudioRaiseVolume",  cmd(monter .. ile("volume")),  media, { locked = true, repeating = true })
touche("XF86AudioLowerVolume",  cmd(baisser .. ile("volume")), media, { locked = true, repeating = true })
touche("XF86AudioMute",         cmd("wpctl set-mute @DEFAULT_AUDIO_SINK@ toggle" .. ile("volume")),     media, { locked = true })
touche("XF86AudioMicMute",      cmd("wpctl set-mute @DEFAULT_AUDIO_SOURCE@ toggle"),   media, { locked = true })
touche("XF86MonBrightnessUp",   cmd("~/.local/bin/nc-brightness up" .. ile("luminosite")),                  media, { locked = true, repeating = true })
touche("XF86MonBrightnessDown", cmd("~/.local/bin/nc-brightness down" .. ile("luminosite")),                media, { locked = true, repeating = true })
-- Musique : nc-media vise le lecteur qu'on entend (voir le script)
touche("XF86AudioPlay",         cmd("~/.local/bin/nc-media play-pause" .. ile("media")),   media, { locked = true })
touche("XF86AudioPause",        cmd("~/.local/bin/nc-media play-pause" .. ile("media")),   media, { locked = true })
touche("XF86AudioNext",         cmd("~/.local/bin/nc-media next" .. ile("media")),         media, { locked = true })
touche("XF86AudioPrev",         cmd("~/.local/bin/nc-media previous" .. ile("media")),     media, { locked = true })
touche("XF86AudioStop",         cmd("~/.local/bin/nc-media stop" .. ile("media")),         media, { locked = true })
touche("XF86AudioForward",      cmd("~/.local/bin/nc-media avance"),                       media, { locked = true, repeating = true })
touche("XF86AudioRewind",       cmd("~/.local/bin/nc-media recule"),                       media, { locked = true, repeating = true })
-- Rangée F1…F12 en touches de son, luminosité et musique, comme les icônes d'un clavier de portable : tout le monde
-- les a, même sur un clavier de bureau. F1…F12 classiques (F5 actualiser, F11 plein écran…) : nc-reglages,
-- « Touches F1 à F12 » ; en mode jeu, elles redeviennent classiques d'elles-mêmes.
do
    local f = io.open((os.getenv("XDG_RUNTIME_DIR") or "/tmp") .. "/nc-mode-jeu", "r")
    local en_jeu = f ~= nil
    if f then f:close() end
    if nc.reglage("TOUCHES_F", "media") == "media" and not en_jeu then
        local rangee = trad("Système|F1 à F12 : son, micro, luminosité, musique, clavier, pavé, calculatrice", "F1 to F12: sound, mic, brightness, music, keyboard, touchpad, calculator")
        local nm = "~/.local/bin/nc-media "
        touche("F1",  cmd("wpctl set-mute @DEFAULT_AUDIO_SINK@ toggle" .. ile("volume")), rangee, { locked = true })
        touche("F2",  cmd(baisser .. ile("volume")), rangee, { locked = true, repeating = true })
        touche("F3",  cmd(monter .. ile("volume")), rangee, { locked = true, repeating = true })
        touche("F4",  cmd("wpctl set-mute @DEFAULT_AUDIO_SOURCE@ toggle"), rangee, { locked = true })
        touche("F5",  cmd("~/.local/bin/nc-brightness down" .. ile("luminosite")), rangee, { locked = true, repeating = true })
        touche("F6",  cmd("~/.local/bin/nc-brightness up" .. ile("luminosite")), rangee, { locked = true, repeating = true })
        touche("F7",  cmd(nm .. "previous" .. ile("media")), rangee, { locked = true })
        touche("F8",  cmd(nm .. "play-pause" .. ile("media")), rangee, { locked = true })
        touche("F9",  cmd(nm .. "next" .. ile("media")), rangee, { locked = true })
        touche("F10", cmd("~/.local/bin/nc-touches clavier bascule"), rangee, { locked = true })
        touche("F11", cmd("~/.local/bin/nc-touches pave bascule"), rangee, { locked = true })
        touche("F12", cmd("~/.local/bin/nc-touches calculatrice"), rangee)
    end
end

-- Autres touches spéciales des portables (selon le modèle, avec Fn) : rétroéclairage du clavier, pavé tactile,
-- calculatrice, recherche, fichiers, navigateur, courrier, veille, verrouillage, réglages ; touche Copilot des
-- PC récents (Super + Maj + F23) : la recherche. Une touche absente du clavier ne gêne pas.
local portable = trad("Système|Touches spéciales du portable", "Laptop special keys")
local tp = "~/.local/bin/nc-touches "
touche("XF86KbdBrightnessUp",   cmd(tp .. "clavier up"),      portable, { locked = true, repeating = true })
touche("XF86KbdBrightnessDown", cmd(tp .. "clavier down"),    portable, { locked = true, repeating = true })
touche("XF86KbdLightOnOff",     cmd(tp .. "clavier bascule"), portable, { locked = true })
-- Même chose sans touche Fn dédiée (Fn + Espace n'arrive pas toujours jusqu'au système)
touche(SUPER .. " + CTRL + code:65", cmd(tp .. "clavier bascule"), trad("Système|Éclairage du clavier (palier suivant)", "Keyboard backlight (next level)"), { locked = true })
touche("XF86TouchpadToggle",    cmd(tp .. "pave bascule"),    portable, { locked = true })
touche("XF86TouchpadOn",        cmd(tp .. "pave on"),         portable, { locked = true })
touche("XF86TouchpadOff",       cmd(tp .. "pave off"),        portable, { locked = true })
touche("XF86Calculator",        cmd(tp .. "calculatrice"),    portable)
touche("XF86Search",            cmd(barre .. "menu"),         portable)
touche("SUPER + SHIFT + F23",   cmd(barre .. "menu"),         portable)
touche("XF86Explorer",          cmd(fichiers),                portable)
touche("XF86MyComputer",        cmd(fichiers),                portable)
touche("XF86HomePage",          cmd("xdg-open https://"),     portable)
touche("XF86WWW",               cmd("xdg-open https://"),     portable)
touche("XF86Mail",              cmd("xdg-open mailto:"),      portable)
touche("XF86Tools",             cmd("~/.local/bin/nc-reglages fenetre"), portable)   -- sans l'île : l'écran du terminal
touche("XF86ScreenSaver",       cmd(barre .. "lock"),         portable, { locked = true })
touche("XF86Sleep",             cmd("systemctl suspend"),     portable, { locked = true })

-- Super seul (appuyée puis relâchée sans autre touche) : nc-reglages → Clavier et souris → « Touche Super seule »
-- (rien par défaut). Coupé en mode jeu.
do
    local f = io.open((os.getenv("XDG_RUNTIME_DIR") or "/tmp") .. "/nc-mode-jeu", "r")
    local en_jeu = f ~= nil
    if f then f:close() end
    local actions = {
        recherche = { "~/.local/bin/nc-shell-msg menu", nc.t("la recherche (Spotlight)", "Search (Spotlight)") },
        lanceur   = { "noctalia msg panel-toggle launcher", nc.t("le lanceur d'applis", "App launcher") },
        centre    = { "qs -c nc-ile ipc call ile basculer 2>/dev/null || noctalia msg panel-toggle control-center",
                      nc.t("le centre de contrôle", "Control Center") },
    }
    local a = actions[nc.reglage("SUPER_SEUL", "rien")]
    if a and not en_jeu then
        touche(SUPER .. " + Super_L", cmd(a[1]), "Système|" .. nc.t("Super seule : ", "Super alone: ") .. a[2], { release = true })
    end
end

-- Bouton d'arrêt : une petite surprise au lieu d'éteindre (Super + F4 éteint) ; laquelle : nc-reglages, Animations
touche("XF86PowerOff",          cmd("~/.local/bin/nc-anim bouton"), nil, { locked = true })

-- Mode « capture » de nc-reglages : le temps d'appuyer sur une nouvelle combinaison, aucun raccourci ne réagit
-- (retour automatique au bout de 20 s, ou avec Super + Ctrl + Alt + F12)
hl.define_submap("nc-capture", function()
    hl.bind("SUPER + CTRL + ALT + F12", hl.dsp.submap("reset"))
end)

-- ── Tes raccourcis (nc-raccourci) ───────────────────────────────────────────
-- Un raccourci refusé par Hyprland est ignoré sans bloquer les autres
local function guillemets(t) return "'" .. tostring(t):gsub("'", "'\\''") .. "'" end
for _, a in ipairs(perso.ajouts) do
    local touches, type_, valeur, nom = a[2], a[3], a[4], a[5]
    local action
    if type_ == "commande" then action = cmd(valeur)
    elseif type_ == "appli" then action = cmd("~/.local/bin/nc-raccourci ouvrir " .. guillemets(valeur))
    elseif type_ == "bureau" then action = hl.dsp.focus({ workspace = tonumber(valeur) or valeur })
    elseif type_ == "ile" then action = cmd(barre .. "ile " .. guillemets(valeur))
    end
    if action then
        local ok, err = pcall(hl.bind, touches, action, { description = "Mes raccourcis|" .. (nom ~= "" and nom or valeur) })
        if not ok then print("noctalia-config : raccourci " .. touches .. " ignoré (" .. tostring(err) .. ")") end
    end
end

-- Raccourcis clavier et souris.
-- Les touches sont données par leur position (code:NN) : elles restent les mêmes en disposition US, FR ou autre.
-- La description (« Section|Texte ») alimente la fiche Super + / et la commande nc-keys : un raccourci
-- ajouté avec une description y apparaît tout seul. Sections : Applis et barre, Fenêtres, Bureaux, Souris, Système.

local SUPER    = "SUPER"
local terminal = "kitty"
local fichiers = "nautilus --new-window"
local barre    = "~/.local/bin/nc-shell-msg "   -- actions envoyées à Noctalia v5

local function touche(touches, action, description, options)
    options = options or {}
    options.description = description
    return hl.bind(touches, action, options)
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
touche(SUPER .. " + code:36", cmd(terminal),                       "Applis et barre|Terminal")
touche(SUPER .. " + code:26", cmd(fichiers),                       "Applis et barre|Fichiers")
touche(SUPER .. " + code:27", cmd(barre .. "menu"),                "Applis et barre|Rechercher (applis, fichiers, calculs)")
touche(SUPER .. " + code:25", cmd(barre .. "wallpapers"),          "Applis et barre|Choisir le fond d'écran")
touche(SUPER .. " + code:54", cmd(barre .. "control-center"),      "Applis et barre|Centre de contrôle (île)")
touche(SUPER .. " + code:59", cmd(barre .. "settings"),            "Applis et barre|Réglages de la barre")
touche(SUPER .. " + code:61", cmd(barre .. "keys"),                "Applis et barre|Afficher cette fiche")
touche(SUPER .. " + code:33", cmd('grim -g "$(slurp)" - | swappy -f -'), "Applis et barre|Capture d'une zone de l'écran")
touche(SUPER .. " + code:49", hl.dsp.workspace.toggle_special("term"), "Applis et barre|Terminal déroulant (sous Échap)")
touche(SUPER .. " + SHIFT + code:55", cmd("noctalia msg panel-toggle launcher /clipboard"), "Applis et barre|Historique du presse-papiers")
touche(SUPER .. " + code:60", cmd("noctalia msg panel-toggle launcher /emo"),  "Applis et barre|Émojis")

-- Captures d'écran (Noctalia) : écran entier, zone, ou zone à annoter avant de copier / enregistrer
-- (Super + P plus haut : zone retouchée dans Swappy)
touche("Print",                 cmd("noctalia msg screenshot-fullscreen"),      "Applis et barre|Capture de l'écran")
touche("SHIFT + Print",         cmd("noctalia msg screenshot-region"))   -- comme Super + P (pas répété dans la fiche)
touche(SUPER .. " + SHIFT + code:39", cmd("noctalia msg screenshot-annotate"), "Applis et barre|Capture à annoter")

-- ── Fenêtres ─────────────────────────────────────────────────────────────────
-- Fermer : si c'était la seule fenêtre de son programme (Discord & co), le programme est arrêté 5 s plus tard
touche(SUPER .. " + SHIFT + code:24", function()
    local w = hl.get_active_window()
    if not w then return end
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
end, "Fenêtres|Fermer (et le programme si dernière)")

touche(SUPER .. " + code:55", hl.dsp.window.float({ action = "toggle" }), "Fenêtres|Fenêtre libre ↔ rangée")
touche(SUPER .. " + code:41", hl.dsp.window.fullscreen_state({ internal = 3, client = 0, action = "toggle" }), "Fenêtres|Plein écran")
touche(SUPER .. " + SHIFT + code:33", hl.dsp.window.pseudo(),      "Fenêtres|Garder sa taille (pseudo)")
touche(SUPER .. " + code:44", hl.dsp.layout("togglesplit"),        "Fenêtres|Changer le sens de la division")

for code, sens in pairs({ [113] = "left", [114] = "right", [111] = "up", [116] = "down" }) do
    touche(SUPER .. " + code:" .. code, hl.dsp.focus({ direction = sens }), "Fenêtres|Aller à la fenêtre voisine")
    touche(SUPER .. " + SHIFT + code:" .. code, hl.dsp.window.move({ direction = sens }), "Fenêtres|Déplacer la fenêtre")
end

local pas = { [113] = { -40, 0 }, [114] = { 40, 0 }, [111] = { 0, -40 }, [116] = { 0, 40 } }
for code, d in pairs(pas) do
    touche(SUPER .. " + CTRL + code:" .. code, hl.dsp.window.resize({ x = d[1], y = d[2], relative = true }),
        "Fenêtres|Agrandir / rétrécir la fenêtre", { repeating = true })
end

-- Épingler : la fenêtre devient flottante et reste au même endroit sur tous les bureaux (même touche pour libérer)
touche(SUPER .. " + CTRL + code:33", function()
    local w = hl.get_active_window()
    if not w then return end
    if not w.pinned and not w.floating then
        hl.dispatch(hl.dsp.window.float({ action = "set" }))
    end
    hl.dispatch(hl.dsp.window.pin({ action = "toggle" }))
end, "Fenêtres|Épingler sur tous les bureaux")

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
end, "Fenêtres|Taille : 50 %, 70 %, 90 % de l'écran")

touche(SUPER .. " + CTRL + code:54", hl.dsp.window.center(),       "Fenêtres|Recentrer la fenêtre flottante")

touche(SUPER .. " + code:42", hl.dsp.group.toggle(),                "Fenêtres|Grouper les fenêtres en onglets")
touche(SUPER .. " + SHIFT + code:42", hl.dsp.window.move({ out_of_group = true }), "Fenêtres|Sortir la fenêtre du groupe")
touche(SUPER .. " + CTRL + code:23", hl.dsp.group.next(),           "Fenêtres|Onglet suivant du groupe")
touche(SUPER .. " + CTRL + SHIFT + code:23", hl.dsp.group.prev(),   "Fenêtres|Onglet précédent du groupe")

touche("ALT + code:23", cmd(barre .. "window-switcher"),            "Fenêtres|Passer d'une fenêtre à l'autre")
touche("ALT + SHIFT + code:23", cmd(barre .. "window-switcher"))
touche(SUPER .. " + ALT + code:23", cmd(barre .. "window-switcher"))

-- ── Bureaux ──────────────────────────────────────────────────────────────────
for i = 1, 10 do
    local code = 9 + i   -- touches 1 à 0 de la rangée du haut
    touche(SUPER .. " + code:" .. code, hl.dsp.focus({ workspace = i }), "Bureaux|Aller au bureau 1 à 10")
    touche(SUPER .. " + SHIFT + code:" .. code, hl.dsp.window.move({ workspace = i }), "Bureaux|Envoyer la fenêtre au bureau 1 à 10")
end
touche(SUPER .. " + mouse_down", hl.dsp.focus({ workspace = "e+1" }), "Bureaux|Bureau suivant / précédent")
touche(SUPER .. " + mouse_up",   hl.dsp.focus({ workspace = "e-1" }), "Bureaux|Bureau suivant / précédent")
touche(SUPER .. " + code:23", hl.dsp.workspace.toggle_special("magic"), "Bureaux|Bureau caché (bloc-notes)")

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
            hl.exec_cmd("notify-send -t 2500 'Terminal caché' 'Il contient déjà une fenêtre.'")
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
touche(SUPER .. " + SHIFT + code:23", vers_cache("magic"), "Bureaux|Fenêtre ↔ bureau caché")
touche(SUPER .. " + SHIFT + code:49", vers_cache("term"),  "Bureaux|Fenêtre ↔ terminal caché")

-- ── Souris ───────────────────────────────────────────────────────────────────
-- Super + glisser : déplacer la tuile (la lâcher sur une autre fenêtre la place à côté) ; Super + clic droit : redimensionner.
touche(SUPER .. " + mouse:272", hl.dsp.window.drag(),   "Souris|Déplacer la fenêtre",       { mouse = true })
touche(SUPER .. " + mouse:273", hl.dsp.window.resize(), "Souris|Redimensionner la fenêtre", { mouse = true })
-- Super + Alt : détacher la fenêtre et la poser ou la redimensionner librement (Super + V la remet dans le pavage)
touche(SUPER .. " + ALT + mouse:272", hl.dsp.window.float({ action = "set" }))
touche(SUPER .. " + ALT + mouse:272", hl.dsp.window.drag(),   "Souris|Détacher et placer librement", { mouse = true })
touche(SUPER .. " + ALT + mouse:273", hl.dsp.window.float({ action = "set" }))
touche(SUPER .. " + ALT + mouse:273", hl.dsp.window.resize(), "Souris|Détacher et redimensionner librement", { mouse = true })
-- Pavé tactile : Super + Maj + appuyer-glisser (un doigt)
touche(SUPER .. " + SHIFT + mouse:272", hl.dsp.window.float({ action = "set" }))
touche(SUPER .. " + SHIFT + mouse:272", hl.dsp.window.resize(), "Souris|Redimensionner (pavé tactile)", { mouse = true })

-- ── Système ──────────────────────────────────────────────────────────────────
touche(SUPER .. " + code:46", cmd(barre .. "lock"),                 "Système|Verrouiller l'écran")
touche(SUPER .. " + SHIFT + code:9", cmd(barre .. "session"),       "Système|Verrouiller et mettre en veille")
touche(SUPER .. " + ALT + code:33", cmd(barre .. "power-cycle"),    "Système|Changer de profil d'énergie")
touche(SUPER .. " + ALT + code:42", function() nc.mode_jeu() end,   "Système|Mode jeu (effets coupés, pas de notifications)")
touche(SUPER .. " + code:57", cmd("noctalia msg nightlight-force-toggle"), "Système|Lumière de nuit")
touche(SUPER .. " + ALT + code:58", cmd("systemctl --user is-active --quiet nc-pouls"
    .. " && { systemctl --user stop nc-pouls; notify-send -a 'Halo musical' -t 2000 'Halo musical coupé'; }"
    .. " || { systemctl --user start nc-pouls; notify-send -a 'Halo musical' -t 2500 'Halo musical activé' 'Le halo suit les basses quand de la musique joue.'; }"),
    "Système|Halo musical (pulse sur les basses)")
touche(SUPER .. " + SHIFT + code:57", cmd("noctalia msg notification-dnd-toggle"), "Système|Ne pas déranger")

-- Loupe : zoom autour du curseur (Super + Ctrl + molette, ou Super + = / Super + -)
local function loupe(facteur)
    return function()
        local z = tonumber(hl.get_config("cursor.zoom_factor")) or 1
        z = math.max(1, math.min(8, z * facteur))
        if z < 1.05 then z = 1 end
        hl.config({ cursor = { zoom_factor = z } })
    end
end
touche(SUPER .. " + CTRL + mouse_up",   loupe(1.25), "Système|Loupe : zoomer / dézoomer")
touche(SUPER .. " + CTRL + mouse_down", loupe(0.8),  "Système|Loupe : zoomer / dézoomer")
touche(SUPER .. " + code:21", loupe(1.25), "Système|Loupe : zoomer / dézoomer", { repeating = true })
touche(SUPER .. " + code:20", loupe(0.8),  "Système|Loupe : zoomer / dézoomer", { repeating = true })
touche(SUPER .. " + SHIFT + code:58",
    cmd("command -v hyprshutdown >/dev/null 2>&1 && hyprshutdown || hyprctl dispatch 'hl.dsp.exit()'"), "Système|Quitter la session")
touche(SUPER .. " + code:70", cmd("systemctl poweroff"),            "Système|Éteindre")
touche(SUPER .. " + code:71", cmd("systemctl reboot"),              "Système|Redémarrer")

-- Touches multimédia (actives aussi sur l'écran de verrouillage)
local media = "Système|Son, luminosité, musique"
-- L'île dynamique (plugin nc/ile) montre le nouveau niveau, à la place des bulles de Noctalia
local function ile(evenement)
    return "; { qs -c nc-ile ipc call ile " .. evenement .. " || noctalia msg plugin nc/ile:pilule all " .. evenement .. "; } >/dev/null 2>&1"
end
touche("XF86AudioRaiseVolume",  cmd("wpctl set-volume -l 1 @DEFAULT_AUDIO_SINK@ 5%+" .. ile("volume")), media, { locked = true, repeating = true })
touche("XF86AudioLowerVolume",  cmd("wpctl set-volume @DEFAULT_AUDIO_SINK@ 5%-" .. ile("volume")),      media, { locked = true, repeating = true })
touche("XF86AudioMute",         cmd("wpctl set-mute @DEFAULT_AUDIO_SINK@ toggle" .. ile("volume")),     media, { locked = true })
touche("XF86AudioMicMute",      cmd("wpctl set-mute @DEFAULT_AUDIO_SOURCE@ toggle"),   media, { locked = true })
touche("XF86MonBrightnessUp",   cmd("~/.local/bin/nc-brightness up" .. ile("luminosite")),                  media, { locked = true, repeating = true })
touche("XF86MonBrightnessDown", cmd("~/.local/bin/nc-brightness down" .. ile("luminosite")),                media, { locked = true, repeating = true })
touche("XF86AudioNext",         cmd("playerctl -p playerctld next" .. ile("media")),                                 media, { locked = true })
touche("XF86AudioPause",        cmd("playerctl -p playerctld play-pause" .. ile("media")),                           media, { locked = true })
touche("XF86AudioPlay",         cmd("playerctl -p playerctld play-pause" .. ile("media")),                           media, { locked = true })
touche("XF86AudioPrev",         cmd("playerctl -p playerctld previous" .. ile("media")),                             media, { locked = true })
-- Bouton d'arrêt : une petite surprise au lieu d'éteindre (Super + F4 éteint)
touche("XF86PowerOff",          cmd("~/.local/bin/nc-finger"), nil, { locked = true })

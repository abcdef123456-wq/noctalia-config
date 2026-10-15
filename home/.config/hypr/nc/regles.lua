-- Règles de fenêtres, de bureaux et de surfaces (barre, panneaux).

-- Les applis ne se maximisent pas toutes seules
hl.window_rule({ name = "pas-de-maximisation", match = { class = ".*" }, suppress_event = "maximize" })
-- Fenêtres sans nom ni classe (glisser-déposer XWayland, menus fantômes) : ne prennent pas le focus en apparaissant
hl.window_rule({ name = "sans-nom", match = { class = "^$", title = "^$" }, no_initial_focus = true })
hl.window_rule({ name = "hyprland-run", match = { class = "hyprland-run" }, float = true, move = "20 monitor_h-120" })

-- Fenêtres utilitaires en flottant
hl.window_rule({
    name   = "utilitaires",
    match  = { class = "^(org.pulseaudio.pavucontrol|com.saivert.pwvucontrol|nm-connection-editor|blueman-manager)$" },
    float  = true,
    center = true,
    size   = { "monitor_w*0.55", "monitor_h*0.6" },
})
hl.window_rule({
    name   = "polkit",
    match  = { class = "^(org.kde.polkit-kde-authentication-agent-1|polkit-kde-authentication-agent-1)$" },
    float  = true,
    center = true,
})

-- Incrustation vidéo des navigateurs : flottante, sur tous les bureaux, en bas à droite (taille relative à l'écran)
hl.window_rule({
    name              = "incrustation-video",
    match             = { title = "^(Picture-in-Picture|Picture in picture|Incrustation vidéo)$" },
    float             = true,
    pin               = true,
    keep_aspect_ratio = true,
    size              = { "monitor_w*0.28", "monitor_w*0.1575" },
    move              = { "monitor_w-window_w-20", "monitor_h-window_h-20" },
})

-- Terminal déroulant (Super + touche sous Échap) : kitty lancé au premier appel
hl.workspace_rule({ workspace = "special:term", on_created_empty = "kitty --class dropterm" })
hl.window_rule({
    name   = "terminal-deroulant",
    match  = { class = "^(dropterm)$" },
    float  = true,
    size   = { "monitor_w*0.72", "monitor_h*0.62" },
    center = true,
})

-- Pas de mise en veille pendant une vidéo en plein écran
hl.window_rule({ name = "video-plein-ecran", match = { class = ".*" }, idle_inhibit = "fullscreen" })

-- Bouton d'arrêt (nc-finger) : plein écran
hl.window_rule({ name = "doigts", match = { class = "^(fingerpop)$" }, float = true, fullscreen = true })

-- Noctalia v5 : flou derrière la barre, les panneaux, le dock, l'OSD et le sélecteur de fenêtres ;
-- animations Hyprland coupées sur ces surfaces (Noctalia anime elle-même). Règle de la documentation officielle v5.
hl.layer_rule({
    name         = "noctalia-v5",
    match        = { namespace = "^noctalia-(bar-.+|notification|dock|panel|attached-panel|osd|window-switcher)$" },
    no_anim      = true,
    ignore_alpha = 0.5,
    blur         = true,
    blur_popups  = true,
})

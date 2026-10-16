-- Apparence : sombre, épurée, rayons alignés sur Noctalia.
-- Couleurs des bordures et du halo : nc/couleurs.lua (généré). Flou, ombres et animations selon le profil : nc/energie.lua.

hl.config({
    general = {
        -- Espaces et bordure : réglables avec nc-reglages
        gaps_in                 = nc.reglage("FENETRES_ESPACE", 4),
        gaps_out                = nc.reglage("FENETRES_MARGE", 10),
        border_size             = nc.reglage("FENETRES_BORDURE", 2),
        resize_on_border        = true,
        extend_border_grab_area = 20,
        allow_tearing           = false,
        -- Disposition des fenêtres (nc-reglages) : dwindle (spirale) ou master (une grande + une pile)
        layout                  = (nc.reglage("FENETRES_DISPOSITION", "dwindle") == "master") and "master" or "dwindle",

        -- Aimantation des fenêtres flottantes aux bords de l'écran et aux autres fenêtres
        snap = {
            enabled      = true,
            window_gap   = 14,
            monitor_gap  = 14,
            respect_gaps = true,
        },
    },

    decoration = {
        rounding       = nc.reglage("FENETRES_ARRONDI", 14),
        rounding_power = 2.5,

        active_opacity   = 1.0,
        inactive_opacity = math.max(0.3, math.min(1, nc.reglage("FENETRES_OPACITE_INACTIVE", 100) / 100)),   -- nc-reglages
        dim_special      = 0.35,

        -- Fenêtres inactives légèrement assombries : la fenêtre active ressort
        dim_inactive = true,
        dim_strength = 0.10,

        shadow = {
            enabled        = true,
            range          = 22,
            render_power   = 3,
            offset         = { 0, 4 },
            color          = "rgba(00000088)",
            color_inactive = "rgba(00000044)",
        },

        -- Valeurs modérées : un processeur graphique intégré doit tenir un grand écran à haute fréquence
        blur = {
            enabled           = true,
            size              = 3,
            passes            = 2,
            noise             = 0.015,
            contrast          = 0.9,
            brightness        = 1.0,
            vibrancy          = 0.17,
            popups            = true,
            new_optimizations = true,
            xray              = false,
        },
    },

    animations = {
        enabled = true,
    },

    -- Fenêtres groupées en onglets (Super + G) : onglets arrondis au-dessus du groupe
    group = {
        groupbar = {
            enabled            = true,
            font_family        = "Adwaita Sans",
            font_size          = 11,
            height             = 20,
            indicator_height   = 0,
            rounding           = 8,
            gradients          = true,
            gradient_rounding  = 8,
            gaps_in            = 4,
            gaps_out           = 4,
            keep_upper_gap     = true,
        },
    },

    dwindle = {
        preserve_split = true,
        smart_split    = false,
    },

    master = {
        new_status = "master",
    },

    misc = {
        force_default_wallpaper  = 0,
        disable_hyprland_logo    = true,
        disable_splash_rendering = true,
        background_color         = "rgb(0b0d12)",
        animate_manual_resizes   = false,
        focus_on_activate        = true,
        key_press_enables_dpms   = true,
        mouse_move_enables_dpms  = true,
        -- Fréquence variable (FreeSync / G-Sync) seulement pour un jeu ou une vidéo en plein écran : plus fluide,
        -- sans scintillement sur le bureau
        vrr                      = 3,
        -- Si Noctalia redémarre pendant que l'écran est verrouillé, elle reprend le verrouillage
        -- (au lieu de l'écran rouge « lockscreen app died »)
        allow_session_lock_restore = true,
    },

    -- Jeu ou vidéo en plein écran affiché directement, sans passer par le compositeur : moins de latence
    render = {
        direct_scanout = 2,
    },

    -- Super + chiffre du bureau où l'on est déjà : retour au bureau précédent
    binds = {
        workspace_back_and_forth = true,
    },

    ecosystem = {
        no_update_news  = true,
        no_donation_nag = true,
    },

    cursor = {
        inactive_timeout  = 8,
        hide_on_key_press = true,
    },

    xwayland = {
        force_zero_scaling = true,
    },
})

-- Courbes et animations
-- Vitesse (nc-reglages, FENETRES_ANIMATIONS_VITESSE) : durées multipliées ; style d'ouverture (FENETRES_OUVERTURE)
local duree = ({ lente = 1.5, normale = 1, rapide = 0.65 })[nc.reglage("FENETRES_ANIMATIONS_VITESSE", "normale")] or 1
local ouverture = ({ popin = "popin 90%", slide = "slide", gnomed = "gnomed" })[nc.reglage("FENETRES_OUVERTURE", "popin")] or "popin 90%"
hl.curve("emphasized",      { type = "bezier", points = { { 0.05, 0.7 }, { 0.1, 1 } } })
hl.curve("emphasizedAccel", { type = "bezier", points = { { 0.3, 0 },    { 0.8, 0.15 } } })
hl.curve("standard",        { type = "bezier", points = { { 0.2, 0 },    { 0, 1 } } })
hl.curve("linear",          { type = "bezier", points = { { 0, 0 },      { 1, 1 } } })

hl.animation({ leaf = "global",           enabled = true, speed = 5 * duree,   bezier = "standard" })
hl.animation({ leaf = "border",           enabled = true, speed = 5 * duree,   bezier = "standard" })
hl.animation({ leaf = "windowsIn",        enabled = true, speed = 4 * duree,   bezier = "emphasized",      style = ouverture })
hl.animation({ leaf = "windowsOut",       enabled = true, speed = 2.5 * duree, bezier = "emphasizedAccel", style = ouverture })
hl.animation({ leaf = "windowsMove",      enabled = true, speed = 4 * duree,   bezier = "emphasized",      style = "slide" })
hl.animation({ leaf = "fadeIn",           enabled = true, speed = 3 * duree,   bezier = "standard" })
hl.animation({ leaf = "fadeOut",          enabled = true, speed = 2 * duree,   bezier = "emphasizedAccel" })
hl.animation({ leaf = "layersIn",         enabled = true, speed = 3 * duree,   bezier = "emphasized",      style = "fade" })
hl.animation({ leaf = "layersOut",        enabled = true, speed = 2 * duree,   bezier = "emphasizedAccel", style = "fade" })
hl.animation({ leaf = "fadeLayersIn",     enabled = true, speed = 2.5 * duree, bezier = "standard" })
hl.animation({ leaf = "fadeLayersOut",    enabled = true, speed = 2 * duree,   bezier = "standard" })
hl.animation({ leaf = "workspaces",       enabled = true, speed = 3.5 * duree, bezier = "emphasized",      style = "slidefadevert 15%" })
-- Bureaux cachés (terminal déroulant, bloc-notes) : descendent du haut de l'écran et y remontent
hl.animation({ leaf = "specialWorkspace", enabled = true, speed = 3.5 * duree, bezier = "emphasized",      style = "slidevert -100%" })
hl.animation({ leaf = "zoomFactor",       enabled = true, speed = 5 * duree,   bezier = "standard" })

-- Apparence : sombre, épurée, rayons alignés sur Noctalia.
-- Couleurs des bordures et du halo : nc/couleurs.lua (généré). Flou, ombres et animations selon le profil : nc/energie.lua.

-- Famille des fenêtres réglable par un thème (nc-reglages) : « auto », absent ou inconnu = les valeurs d'origine.
local disposition = ({ dwindle = "dwindle", master = "master", scrolling = "scrolling" })[nc.reglage("FENETRES_DISPOSITION", "dwindle")] or "dwindle"
-- Orientation de la grande fenêtre : seulement en master (sinon rien n'est posé)
local maitre_orientation = (disposition == "master")
    and ({ gauche = "left", droite = "right", haut = "top", bas = "bottom", centre = "center" })[nc.reglage("FENETRES_MAITRE_ORIENTATION", "auto")] or nil
local fond = ({ auto = "rgb(0b0d12)", noir = "rgb(000000)" })[nc.reglage("FENETRES_FOND", "auto")] or "rgb(0b0d12)"
local ombre_decalage = ({ auto = { 0, 4 }, aucun = { 0, 0 }, bas = { 0, 8 }, dure = { 8, 8 } })[nc.reglage("FENETRES_OMBRE_DECALAGE", "auto")] or { 0, 4 }

hl.config({
    general = {
        -- Espaces et bordure : réglables avec nc-reglages
        gaps_in                 = nc.reglage("FENETRES_ESPACE", 4),
        gaps_out                = nc.reglage("FENETRES_MARGE", 10),
        border_size             = nc.reglage("FENETRES_BORDURE", 2),
        resize_on_border        = nc.reglage("FENETRES_BORDURE_REDIM", true),
        extend_border_grab_area = 20,
        allow_tearing           = false,
        -- Disposition des fenêtres (nc-reglages) : dwindle (spirale), master (une grande + une pile) ou scrolling
        layout                  = disposition,

        -- Aimantation des fenêtres flottantes aux bords de l'écran et aux autres fenêtres
        snap = {
            enabled      = nc.reglage("FENETRES_AIMANT", true),
            window_gap   = 14,
            monitor_gap  = 14,
            respect_gaps = true,
        },
    },

    decoration = {
        rounding       = math.min(20, nc.reglage("FENETRES_ARRONDI", 14)),   -- Hyprland : 20 au plus (une valeur plus haute = erreur)
        rounding_power = ({ rond = 2, doux = 2.5, carres = 4 })[nc.reglage("FENETRES_COINS_FORME", "doux")] or 2.5,   -- nc-reglages

        active_opacity   = math.max(0.7, math.min(1, nc.reglage("FENETRES_OPACITE_ACTIVE", 100) / 100)),   -- nc-reglages
        inactive_opacity = math.max(0.3, math.min(1, nc.reglage("FENETRES_OPACITE_INACTIVE", 100) / 100)),   -- nc-reglages
        dim_special      = 0.35,

        -- Fenêtres inactives légèrement assombries : la fenêtre active ressort
        dim_inactive = true,
        dim_strength = math.max(0, math.min(0.9, nc.reglage("FENETRES_ASSOMBRIR_FORCE", 10) / 100)),   -- nc-reglages

        shadow = {
            enabled        = true,
            range          = math.max(0, nc.reglage("FENETRES_OMBRE", 22)),   -- nc-reglages (0 : pas d'ombre)
            render_power   = 3,
            offset         = ombre_decalage,   -- nc-reglages
            color          = "rgba(00000088)",
            color_inactive = "rgba(00000044)",
        },

        -- Valeurs modérées : un processeur graphique intégré doit tenir un grand écran à haute fréquence
        blur = {
            enabled           = true,
            -- Force du flou (nc-reglages, FENETRES_FLOU_FORCE) : léger, normal ou fort
            size              = ({ leger = 2, normal = 3, fort = 6 })[nc.reglage("FENETRES_FLOU_FORCE", "normal")] or 3,
            passes            = ({ leger = 1, normal = 2, fort = 3 })[nc.reglage("FENETRES_FLOU_FORCE", "normal")] or 2,
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
        new_status  = "master",
        orientation = maitre_orientation,   -- nil (rien de posé) hors master ou en auto
    },

    misc = {
        force_default_wallpaper  = 0,
        disable_hyprland_logo    = true,
        disable_splash_rendering = true,
        background_color         = fond,   -- nc-reglages
        animate_manual_resizes   = false,
        focus_on_activate        = nc.reglage("FENETRES_FOCUS_DEMANDE", true),
        middle_click_paste       = nc.reglage("COLLER_CLIC_MILIEU", true),   -- nc-reglages
        key_press_enables_dpms   = true,
        mouse_move_enables_dpms  = true,
        -- Fréquence variable (FreeSync / G-Sync) seulement pour un jeu ou une vidéo en plein écran : plus fluide,
        -- sans scintillement sur le bureau
        vrr                      = ({ auto = 3, ["plein-ecran"] = 2, oui = 1, non = 0 })[nc.reglage("ECRAN_VRR", "auto")] or 3,   -- nc-reglages
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
        workspace_back_and_forth = nc.reglage("BUREAU_ALLER_RETOUR", true),   -- nc-reglages
        -- Plein écran d'une fenêtre épinglée (Super + Ctrl + P puis Super + F) : sans cela Hyprland le refuse ; avec,
        -- il la désépingle le temps du plein écran et la ré-épingle en sortant (FullscreenController, 0.56)
        allow_pin_fullscreen = true,
    },

    ecosystem = {
        no_update_news  = true,
        no_donation_nag = true,
    },

    cursor = {
        inactive_timeout  = math.min(20, nc.reglage("CURSEUR_CACHER", 8)),   -- nc-reglages (0 : jamais caché ; 20 s au plus)
        no_warps          = not nc.reglage("CURSEUR_SUIT_FOCUS", true),   -- nc-reglages
        hide_on_key_press = true,
    },

    xwayland = {
        force_zero_scaling = true,
    },
})

-- Courbes et animations
-- Vitesse (nc-reglages, FENETRES_ANIMATIONS_VITESSE) : durées multipliées ; style d'ouverture (FENETRES_OUVERTURE)
local duree = ({ lente = 1.5, normale = 1, rapide = 0.65 })[nc.reglage("FENETRES_ANIMATIONS_VITESSE", "normale")] or 1
local bureaux = ({ slidefadevert = "slidefadevert 15%", slidefade = "slidefade 15%", slidevert = "slidevert", slide = "slide",
                   fade = "fade" })[nc.reglage("ANIM_BUREAUX", "slidefadevert")] or "slidefadevert 15%"
local ouverture = ({ popin = "popin 90%", slide = "slide", gnomed = "gnomed" })[nc.reglage("FENETRES_OUVERTURE", "popin")] or "popin 90%"
-- Caractère (nc-reglages, FENETRES_CARACTERE) : mêmes noms de courbes, autres points ; « auto » = les courbes d'origine.
-- Les points en y hors de [0, 1] font dépasser l'animation (bezier d'Hyprland). Inconnu : auto. Le facteur s'applique à duree.
local caracteres = {
    auto   = { f = 1,    e = { { 0.05, 0.7 }, { 0.1, 1 } },    a = { { 0.3, 0 },  { 0.8, 0.15 } }, s = { { 0.2, 0 },  { 0, 1 } },    l = { { 0, 0 }, { 1, 1 } } },
    doux   = { f = 1.4,  e = { { 0.2, 0.6 }, { 0.3, 1 } },     a = { { 0.4, 0 },  { 0.7, 0.3 } },   s = { { 0.4, 0 },  { 0.2, 1 } },  l = { { 0.25, 0.1 }, { 0.75, 0.9 } } },
    vif    = { f = 0.75, e = { { 0.2, 0.9 }, { 0.2, 1.08 } },  a = { { 0.5, 0 },  { 0.9, 0.3 } },   s = { { 0.1, 0.8 }, { 0.2, 1.04 } }, l = { { 0.1, 0.1 }, { 0.9, 0.9 } } },
    sec    = { f = 0.55, e = { { 0.4, 0.1 }, { 0.6, 0.9 } },   a = { { 0.5, 0.1 }, { 0.9, 0.5 } },  s = { { 0.4, 0.2 }, { 0.6, 0.8 } },  l = { { 0.33, 0.33 }, { 0.66, 0.66 } } },
    rebond = { f = 1.1,  e = { { 0.3, 1.3 }, { 0.5, 1 } },     a = { { 0.5, -0.2 }, { 0.8, 0.2 } }, s = { { 0.2, 1.25 }, { 0.4, 1 } },  l = { { 0.2, 0.2 }, { 0.8, 0.8 } } },
    aucun  = { f = 0.1,  e = { { 0, 1 }, { 0, 1 } },           a = { { 0, 1 }, { 0, 1 } },          s = { { 0, 1 }, { 0, 1 } },         l = { { 0, 1 }, { 0, 1 } } },
}
local car = caracteres[nc.reglage("FENETRES_CARACTERE", "auto")] or caracteres.auto
duree = duree * car.f
hl.curve("emphasized",      { type = "bezier", points = car.e })
hl.curve("emphasizedAccel", { type = "bezier", points = car.a })
hl.curve("standard",        { type = "bezier", points = car.s })
hl.curve("linear",          { type = "bezier", points = car.l })

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
hl.animation({ leaf = "workspaces",       enabled = true, speed = 3.5 * duree, bezier = "emphasized",      style = bureaux })
-- Bureaux cachés (terminal déroulant, bloc-notes) : descendent du haut de l'écran et y remontent
hl.animation({ leaf = "specialWorkspace", enabled = true, speed = 3.5 * duree, bezier = "emphasized",      style = "slidevert -100%" })
hl.animation({ leaf = "zoomFactor",       enabled = true, speed = 5 * duree,   bezier = "standard" })

-- Hyprland 0.56 et plus : pas de barre d'onglets pour un groupe d'une seule fenêtre (option absente avant : ignorée)
if nc.hypr_min and nc.hypr_min(0, 56, 0) then
    pcall(hl.config, { group = { groupbar = { disable_when_only = true } } })
end

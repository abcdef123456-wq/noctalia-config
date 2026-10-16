-- Clavier, souris, pavé tactile et gestes.
-- Disposition : celle du système, relevée par install.sh, ou celle choisie avec nc-reglages (CLAVIER_DISPOSITION,
-- ex. « us » ou « us,fr »). S'il y en a plusieurs, Super + Espace passe de l'une à l'autre.
local disposition = nc.reglage("CLAVIER_DISPOSITION", "@KB_LAYOUT@")
if disposition == "systeme" then disposition = "@KB_LAYOUT@" end
local options = "@KB_OPTIONS@"
if disposition:find(",") then
    if not options:find("grp:") then options = (options ~= "" and options .. "," or "") .. "grp:win_space_toggle" end
else
    options = options:gsub(",?grp:[%w_]+", ""):gsub("^,", "")
end

hl.config({
    input = {
        kb_layout  = disposition,
        kb_variant = "",
        kb_model   = "",
        kb_options = options,
        kb_rules   = "",

        repeat_rate  = 35,
        repeat_delay = 300,

        follow_mouse = 1,
        sensitivity  = math.max(-1, math.min(1, nc.reglage("SOURIS_VITESSE", 0) / 10)),   -- nc-reglages : -10 à 10

        touchpad = {
            natural_scroll       = nc.reglage("DEFILEMENT_NATUREL", true),
            tap_to_click         = nc.reglage("TAPOTER_CLIC", true),
            drag_lock            = false,
            disable_while_typing = true,
            clickfinger_behavior = true,
        },
    },
})

-- Gestes du pavé tactile
--   3 doigts gauche/droite : changer de bureau
--   4 doigts en glissant   : déplacer la fenêtre sous le curseur
--   Alt + 4 doigts         : redimensionner la fenêtre
--   4 doigts en pincement  : détacher / remettre la fenêtre dans le pavage
hl.gesture({ fingers = 3, direction = "horizontal", action = "workspace" })
hl.gesture({ fingers = 4, direction = "swipe", action = "move" })
hl.gesture({ fingers = 4, direction = "swipe", mods = "ALT", action = "resize" })
hl.gesture({ fingers = 4, direction = "pinch", action = "float" })

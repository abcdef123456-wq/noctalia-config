-- Clavier, souris, pavé tactile et gestes.
-- Disposition : celle du système, relevée par install.sh. S'il y en a plusieurs, Super + Espace passe de l'une à l'autre.

hl.config({
    input = {
        kb_layout  = "@KB_LAYOUT@",
        kb_variant = "",
        kb_model   = "",
        kb_options = "@KB_OPTIONS@",
        kb_rules   = "",

        repeat_rate  = 35,
        repeat_delay = 300,

        follow_mouse = 1,
        sensitivity  = 0,

        touchpad = {
            natural_scroll       = true,
            tap_to_click         = true,
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

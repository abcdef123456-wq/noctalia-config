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

-- Verr. Maj et touche compose (nc-reglages → Clavier et souris)
do
    local maj = ({ ctrl = "ctrl:nocaps", echap = "caps:escape", super = "caps:super" })[nc.reglage("CLAVIER_MAJ", "normal")]
    local compose = ({ menu = "compose:menu", ["ctrl-droit"] = "compose:rctrl" })[nc.reglage("CLAVIER_COMPOSE", "non")]
    for _, o in ipairs({ maj or "", compose or "" }) do
        if o ~= "" and not options:find(o, 1, true) then options = (options ~= "" and options .. "," or "") .. o end
    end
end

hl.config({
    input = {
        kb_layout  = disposition,
        kb_variant = "",
        kb_model   = "",
        kb_options = options,
        kb_rules   = "",

        -- Répétition des touches et focus : réglables avec nc-reglages
        repeat_rate  = nc.reglage("CLAVIER_REPETITION", 35),
        repeat_delay = nc.reglage("CLAVIER_DELAI", 300),

        follow_mouse = nc.reglage("FOCUS_SOURIS", true) and 1 or 0,
        sensitivity  = math.max(-1, math.min(1, nc.reglage("SOURIS_VITESSE", 0) / 10)),   -- nc-reglages : -10 à 10
        accel_profile = (nc.reglage("SOURIS_ACCELERATION", "adaptative") == "plate") and "flat" or "adaptive",
        scroll_factor = math.max(0.1, nc.reglage("SOURIS_DEFILEMENT", 100) / 100),       -- molette
        numlock_by_default = nc.reglage("CLAVIER_VERR_NUM", false),
        left_handed   = nc.reglage("SOURIS_GAUCHER", false),

        touchpad = {
            natural_scroll       = nc.reglage("DEFILEMENT_NATUREL", true),
            tap_to_click         = nc.reglage("TAPOTER_CLIC", true),
            scroll_factor        = math.max(0.1, nc.reglage("PAVE_DEFILEMENT", 100) / 100),
            drag_lock            = false,
            disable_while_typing = nc.reglage("PAVE_PENDANT_FRAPPE", true),
            middle_button_emulation = nc.reglage("PAVE_CLIC_MILIEU", false),
            clickfinger_behavior = true,
        },
    },
})

-- Pavé tactile coupé avec sa touche (nc-touches pave) : le reste après un rechargement de Hyprland
do
    local f = io.open((os.getenv("XDG_RUNTIME_DIR") or "/tmp") .. "/nc-pave-coupe", "r")
    if f then
        for nom in f:lines() do
            if nom ~= "" then pcall(hl.device, { name = nom, enabled = false }) end
        end
        f:close()
    end
end

-- Gestes du pavé tactile
--   3 doigts gauche/droite : changer de bureau
--   4 doigts en glissant   : déplacer la fenêtre sous le curseur
--   Alt + 4 doigts         : redimensionner la fenêtre
--   4 doigts en pincement  : détacher / remettre la fenêtre dans le pavage
if nc.reglage("GESTES", true) then   -- nc-reglages : gestes du pavé tactile
    hl.gesture({ fingers = 3, direction = "horizontal", action = "workspace" })
    hl.gesture({ fingers = 4, direction = "swipe", action = "move" })
    hl.gesture({ fingers = 4, direction = "swipe", mods = "ALT", action = "resize" })
    hl.gesture({ fingers = 4, direction = "pinch", action = "float" })
    -- Trois doigts vers le haut : vue de toutes les fenêtres (comme Mission Control)
    hl.gesture({ fingers = 3, direction = "up", action = function() hl.exec_cmd("qs -c nc-ile ipc call ile vueOuvrir") end })
    -- Trois doigts vers le bas : la referme
    hl.gesture({ fingers = 3, direction = "down", action = function() hl.exec_cmd("qs -c nc-ile ipc call ile vueFermer") end })
end

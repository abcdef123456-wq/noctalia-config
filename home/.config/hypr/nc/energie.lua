-- Effets selon le profil énergétique (nc.profil, écrit par nc-profile-sync dans nc/profil.lua) :
--   Performance : tout, et bordure animée en rotation continue sur secteur
--   Équilibré   : tout
--   Économie    : ni flou, ni ombres, ni assombrissement, ni animations
-- La fréquence de l'écran interne est réglée dans nc/ecrans.lua.

local eco = nc.profil.profil == "power-saver"
-- « Aucun effet » (nc-reglages → Animations → Effets visuels) : comme l'Économie, dans tous les profils
local coupe = eco or nc.reglage("EFFETS", "tous") == "aucun"
nc.flou_actif = not coupe

-- Tes choix (nc-reglages) s'ajoutent : un effet coupé par toi le reste dans tous les profils
nc.flou_actif = nc.flou_actif and nc.reglage("FENETRES_HALO", true)
hl.config({
    animations = { enabled = not coupe and nc.reglage("FENETRES_ANIMATIONS", true) },
    decoration = {
        dim_inactive = not coupe and nc.reglage("FENETRES_ASSOMBRIR", true),
        blur   = { enabled = not coupe and nc.reglage("FENETRES_FLOU", true) },
        shadow = { enabled = not coupe and nc.reglage("FENETRES_HALO", true) },
    },
})

-- Bordure en rotation continue : seulement en Performance sur secteur (elle force un rendu permanent de l'écran)
if nc.profil.profil == "performance" and not nc.profil.batterie and not coupe then
    hl.animation({ leaf = "borderangle", enabled = true, speed = 100, bezier = "linear", style = "loop" })
else
    hl.animation({ leaf = "borderangle", enabled = true, speed = 8, bezier = "standard" })
end

-- Mode jeu (Super + Alt + G) : effets coupés et image envoyée sans attendre l'écran (jeux marqués dans nc/regles.lua),
-- notifications en pause (Concentration de l'île, sinon « ne pas déranger » de Noctalia). L'état tient dans un fichier de la session : il survit aux rechargements, pas à la déconnexion.
local fichier_jeu = (os.getenv("XDG_RUNTIME_DIR") or "/tmp") .. "/nc-mode-jeu"
local f = io.open(fichier_jeu)
nc.jeu = f ~= nil
if f then f:close() end

if nc.jeu then
    nc.flou_actif = false
    hl.config({
        general    = { allow_tearing = true },
        animations = { enabled = false },
        decoration = { dim_inactive = false, blur = { enabled = false }, shadow = { enabled = false } },
    })
    hl.animation({ leaf = "borderangle", enabled = false })
end

function nc.mode_jeu()
    local actif = not nc.jeu
    if actif then
        local w = io.open(fichier_jeu, "w")
        if w then w:close() end
    else
        os.remove(fichier_jeu)
    end
    -- Profil Performance le temps du jeu (nc-reglages, JEU_PERFORMANCE) ; celui d'avant est remis en sortant
    local profil = (os.getenv("XDG_RUNTIME_DIR") or "/tmp") .. "/nc-mode-jeu-profil"
    if nc.reglage("JEU_PERFORMANCE", true) then
        if actif then
            hl.exec_cmd("p=$(gdbus call --system --dest net.hadess.PowerProfiles --object-path /net/hadess/PowerProfiles"
                .. " --method org.freedesktop.DBus.Properties.Get net.hadess.PowerProfiles ActiveProfile 2>/dev/null"
                .. " | grep -oE \"'[a-z-]+'\" | tr -d \"'\"); [ -n \"$p\" ] && echo \"$p\" > " .. profil
                .. " && noctalia msg power-set performance >/dev/null 2>&1")
        else
            hl.exec_cmd("[ -s " .. profil .. " ] && noctalia msg power-set \"$(cat " .. profil .. ")\" >/dev/null 2>&1; rm -f " .. profil)
        end
    end
    -- Message affiché avant la pause des notifications (en entrant) ou après (en sortant)
    if actif then
        hl.exec_cmd("hyprctl reload; notify-send -a 'Mode jeu' -t 2500 'Mode jeu activé' 'Effets coupés, notifications en pause, profil Performance.';"
            .. " sleep 2.6; qs -c nc-ile ipc call ile concentrationRegler true 2>/dev/null || noctalia msg notification-dnd-set on")
    else
        hl.exec_cmd("{ qs -c nc-ile ipc call ile concentrationRegler false 2>/dev/null || noctalia msg notification-dnd-set off; }; hyprctl reload;"
            .. " notify-send -a 'Mode jeu' -t 2500 'Mode jeu désactivé' 'Effets et notifications rétablis.'")
    end
end

-- Flou coupé le temps d'un panneau plein écran (carrousel des fonds) : appelé par nc-shell-msg via « hyprctl eval »
function nc.flou(actif)
    hl.config({ decoration = { blur = { enabled = actif and nc.flou_actif } } })
end

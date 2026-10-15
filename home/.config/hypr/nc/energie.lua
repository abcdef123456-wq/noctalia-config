-- Effets selon le profil énergétique (nc.profil, écrit par nc-profile-sync dans nc/profil.lua) :
--   Performance : tout, et bordure animée en rotation continue sur secteur
--   Équilibré   : tout
--   Économie    : ni flou, ni ombres, ni assombrissement, ni animations
-- La fréquence de l'écran interne est réglée dans nc/ecrans.lua.

local eco = nc.profil.profil == "power-saver"
nc.flou_actif = not eco

hl.config({
    animations = { enabled = not eco },
    decoration = {
        dim_inactive = not eco,
        blur   = { enabled = not eco },
        shadow = { enabled = not eco },
    },
})

-- Bordure en rotation continue : seulement en Performance sur secteur (elle force un rendu permanent de l'écran)
if nc.profil.profil == "performance" and not nc.profil.batterie then
    hl.animation({ leaf = "borderangle", enabled = true, speed = 100, bezier = "linear", style = "loop" })
else
    hl.animation({ leaf = "borderangle", enabled = true, speed = 8, bezier = "standard" })
end

-- Flou coupé le temps d'un panneau plein écran (carrousel des fonds) : appelé par nc-shell-msg via « hyprctl eval »
function nc.flou(actif)
    hl.config({ decoration = { blur = { enabled = actif and nc.flou_actif } } })
end

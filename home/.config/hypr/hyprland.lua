-- noctalia-config : configuration Hyprland (format Lua, Hyprland 0.55 ou plus).
-- Chaque fichier de nc/ couvre un domaine. Une erreur dans l'un n'empêche pas les autres de se charger.
-- Tes ajouts personnels vont dans ~/.config/hypr/perso.lua (chargé en dernier, jamais remplacé par install.sh).
-- Fichiers générés automatiquement, à ne pas éditer : nc/couleurs.lua (nc-theme-sync), nc/profil.lua (nc-profile-sync).

-- État partagé entre les modules
nc = {}

-- Charge un module sans arrêter la config s'il manque ou contient une erreur (renvoie sa valeur, ou nil)
function nc.charger(nom)
    local ok, res = pcall(require, nom)
    if ok then return res end
    print("noctalia-config : " .. nom .. " ignoré (" .. tostring(res) .. ")")
    return nil
end

-- Profil énergétique courant : performance, balanced ou power-saver ; sur batterie ou non (écrit par nc-profile-sync)
nc.profil = nc.charger("nc.profil") or { profil = "balanced", batterie = false }

require("nc.ecrans")
require("nc.session")
require("nc.apparence")
require("nc.couleurs")
require("nc.clavier")
require("nc.raccourcis")
require("nc.regles")
require("nc.energie")

-- Tes réglages personnels, s'il y en a
local perso = os.getenv("HOME") .. "/.config/hypr/perso.lua"
local f = io.open(perso, "r")
if f then
    f:close()
    require("perso")
end

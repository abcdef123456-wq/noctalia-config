-- noctalia-config : configuration Hyprland (format Lua, Hyprland 0.55 ou plus).
-- Chaque fichier de nc/ couvre un domaine. Une erreur dans l'un n'empêche pas les autres de se charger.
-- Réglages courants (espaces, bordures, pavé tactile, écran…) : commande nc-reglages.
-- Tes ajouts personnels vont dans ~/.config/hypr/perso.lua (chargé en dernier, jamais remplacé par install.sh).
-- Fichiers générés automatiquement, à ne pas éditer : nc/couleurs.lua (nc-theme-sync), nc/profil.lua (nc-profile-sync).

-- État partagé entre les modules
nc = {}

-- Tes réglages (commande nc-reglages) : ~/.config/nc/reglages.conf, lignes CLE=valeur, jamais remplacé par les
-- mises à jour. nc.reglage(CLE, défaut) : la valeur choisie, du type du défaut (nombre, oui/non, texte), sinon le défaut.
-- Le style du bureau (style Apple…) donne ses propres valeurs dans ~/.config/nc/style.conf ; tes réglages passent devant.
nc.reglages = {}
for _, nom in ipairs({ "style.conf", "reglages.conf" }) do
    local f = io.open((os.getenv("HOME") or "") .. "/.config/nc/" .. nom, "r")
    if f then
        for ligne in f:lines() do
            local k, v = ligne:match("^%s*([%u%d_]+)%s*=%s*(.-)%s*$")
            if k then nc.reglages[k] = v:gsub('^"(.*)"$', "%1") end
        end
        f:close()
    end
end
function nc.reglage(cle, defaut)
    local v = nc.reglages[cle]
    if v == nil or v == "" then return defaut end
    if type(defaut) == "number" then return tonumber(v) or defaut end
    if type(defaut) == "boolean" then
        if v == "oui" or v == "true" or v == "1" then return true end
        if v == "non" or v == "false" or v == "0" then return false end
        return defaut
    end
    return v
end

-- Langue (nc-reglages → Apparence → Langue : auto, fr, en ; auto = celle du système) :
-- nc.t("texte français", "English text")
do
    local l = os.getenv("NC_LANGUE")
    if l ~= "fr" and l ~= "en" then l = nc.reglages.LANGUE end
    if l ~= "fr" and l ~= "en" then
        local loc = os.getenv("LC_ALL") or os.getenv("LC_MESSAGES") or os.getenv("LANG") or ""
        if loc == "" then
            local f = io.open("/etc/locale.conf", "r")
            if f then loc = (f:read("a"):match("LANG=\"?([%w_.@-]+)") or ""); f:close() end
        end
        l = loc:sub(1, 2) == "fr" and "fr" or "en"
    end
    nc.langue = l
end
function nc.t(fr, en)
    return nc.langue == "en" and en or fr
end

-- Texte entre apostrophes pour une commande shell (hl.exec_cmd), apostrophes du texte comprises
function nc.guillemets(texte)
    return "'" .. tostring(texte):gsub("'", "'\\''") .. "'"
end

-- Charge un module sans arrêter la config s'il manque ou contient une erreur (renvoie sa valeur, ou nil)
function nc.charger(nom)
    local ok, res = pcall(require, nom)
    if ok then return res end
    print("noctalia-config : " .. nom .. " ignoré (" .. tostring(res) .. ")")
    return nil
end

-- Version de Hyprland (hl.version, dès 0.55.0) : nc.hypr_min(0, 56, 0) est vrai à partir de la 0.56.0
nc.hypr = { 0, 0, 0 }
pcall(function() nc.hypr = { tostring(hl.version()):match("(%d+)%.(%d+)%.(%d+)") } end)
for i = 1, 3 do nc.hypr[i] = tonumber(nc.hypr[i]) or 0 end
function nc.hypr_min(a, b, c)
    local v, w = nc.hypr, { a, b or 0, c or 0 }
    for i = 1, 3 do if v[i] ~= w[i] then return v[i] > w[i] end end
    return true
end

-- Ce que Hyprland 0.55 ne donne pas aux écrans en Lua (modes, taille physique, place réservée à la barre ; arrivés en
-- 0.56) : lu une fois par « hyprctl monitors -j », en arrière-plan, rangé ici par nc/ecrans.lua (nc.ecrans_infos)
nc.ecrans_infos = {}
function nc.reserve(m)
    if m and type(m.reserved) == "table" and next(m.reserved) ~= nil then return m.reserved end
    return (m and nc.ecrans_infos[m.name] or {}).reserved or {}
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
require("nc.automatismes")
nc.charger("nc.zones")          -- la disposition des bureaux rangés par l'IA (hl.layout.register, si Hyprland l'a)

-- Tes réglages personnels, s'il y en a
local perso = os.getenv("HOME") .. "/.config/hypr/perso.lua"
local f = io.open(perso, "r")
if f then
    f:close()
    require("perso")
end

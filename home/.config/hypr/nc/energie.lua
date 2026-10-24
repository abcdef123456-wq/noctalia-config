-- Effets selon le profil énergétique (nc.profil, écrit par nc-profile-sync dans nc/profil.lua) :
--   Performance : tout, et bordure animée en rotation continue sur secteur
--   Équilibré   : tout
--   Économie    : ni flou, ni ombres, ni assombrissement, ni animations
-- La fréquence de l'écran interne est réglée dans nc/ecrans.lua.

-- Effets gardés en Économie si tu le choisis (nc-reglages → Énergie)
local eco = nc.profil.profil == "power-saver" and nc.reglage("ECO_EFFETS", true)
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
        shadow = { enabled = not coupe and nc.reglage("FENETRES_HALO", true) and nc.reglage("FENETRES_OMBRE", 22) > 0 },
    },
})

-- La session est-elle rendue par une carte graphique dédiée (mode Dédiée du BIOS d'un portable à MUX, PC fixe) ?
-- Lu dans /sys pendant le chargement, sans rien lancer : la carte de AQ_DRM_DEVICES (la première), sinon celle de
-- l'écran interne allumé, sinon celle d'un écran branché. Dédiée = NVIDIA, ou AMD / Intel avec au moins 2 Gio de
-- mémoire vidéo (une carte intégrée en annonce peu). Dans le doute : non. NC_SYSFS : un faux /sys, pour les tests.
local function lire(chemin)
    local f = io.open((os.getenv("NC_SYSFS") or "/sys") .. chemin)
    if not f then return nil end
    local t = f:read("*a")
    f:close()
    return t
end
local function carte_de_la_session()
    local premiere = (os.getenv("AQ_DRM_DEVICES") or ""):match("^[^:]+")
    if premiere and premiere ~= "" then
        -- /dev/dri/cardN (env-hyprland) ; un chemin by-path ne peut pas y figurer (ses « : » séparent la liste)
        local n = premiere:match("card(%d+)$")
        return n and ("card" .. n) or nil
    end
    local function branche(prises)
        for i = 0, 7 do
            for _, prise in ipairs(prises) do
                for j = 1, 4 do
                    if (lire("/class/drm/card" .. i .. "-" .. prise .. "-" .. j .. "/status") or ""):match("^connected") then
                        return "card" .. i
                    end
                end
            end
        end
    end
    return branche({ "eDP" }) or branche({ "DP", "HDMI-A", "DVI-D", "DVI-I", "VGA" })
end
function nc.session_sur_carte_dediee()
    local carte = carte_de_la_session()
    if not carte then return false end
    local vendeur = (lire("/class/drm/" .. carte .. "/device/vendor") or ""):match("0x%x+")
    if vendeur == "0x10de" then return true end
    local vram = tonumber((lire("/class/drm/" .. carte .. "/device/mem_info_vram_total") or ""):match("%d+"))
    return (vendeur == "0x1002" or vendeur == "0x8086") and vram ~= nil and vram >= 2 * 1024 ^ 3
end

-- Bordure en rotation continue : seulement en Performance sur secteur, et quand la session est rendue par une carte
-- dédiée. Elle fait redessiner tout l'écran à chaque image : sur une carte intégrée (Radeon 610M à 165 Hz), environ la
-- moitié du GPU et des images perdues au changement de bureau. Coupable dans nc-reglages → Énergie
local boucle_permise = nc.profil.profil == "performance" and not nc.profil.batterie and not coupe
    and nc.reglage("BORDURE_PERFORMANCE", true) and nc.session_sur_carte_dediee()
-- Écran éteint : la bordure ne tourne plus (Hyprland continuait à l'animer et à consommer environ 3 % d'un cœur).
-- nc-ecran l'appelle (hyprctl eval) à l'extinction (true) et au rallumage (false). Sans argument (chargement ou
-- rechargement de la config) : l'état noté par nc-ecran dans $XDG_RUNTIME_DIR/nc-ecran-eteint, pour qu'un rechargement
-- écran éteint ne relance pas la boucle.
local function marque(nom)
    local f = io.open((os.getenv("XDG_RUNTIME_DIR") or "/tmp") .. "/" .. nom)
    if f then f:close() end
    return f ~= nil
end
function nc.bordure(ecran_eteint)
    -- Mode jeu : bordure coupée par la section du mode jeu, on n'y touche pas (lu sur la marque, pas sur nc.jeu, que le
    -- chargement de la config ne connaît pas encore ici)
    if marque("nc-mode-jeu") then return end
    if ecran_eteint == nil then ecran_eteint = marque("nc-ecran-eteint") end
    if boucle_permise and not ecran_eteint then
        hl.animation({ leaf = "borderangle", enabled = true, speed = 100, bezier = "linear", style = "loop" })
    else
        hl.animation({ leaf = "borderangle", enabled = true, speed = 8, bezier = "standard" })
    end
end
nc.bordure()

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
    local q = nc.guillemets
    local appli = q(nc.t("Mode jeu", "Game Mode"))
    if actif then
        hl.exec_cmd("hyprctl reload; notify-send -a " .. appli .. " -t 2500 " .. q(nc.t("Mode jeu activé", "Game Mode on")) .. " "
            .. q(nc.t("Effets coupés, notifications en pause, profil Performance.", "Effects off, notifications paused, Performance profile.")) .. ";"
            .. " sleep 2.6; qs -c nc-ile ipc call ile concentrationRegler true 2>/dev/null || noctalia msg notification-dnd-set on")
    else
        hl.exec_cmd("{ qs -c nc-ile ipc call ile concentrationRegler false 2>/dev/null || noctalia msg notification-dnd-set off; }; hyprctl reload;"
            .. " notify-send -a " .. appli .. " -t 2500 " .. q(nc.t("Mode jeu désactivé", "Game Mode off")) .. " "
            .. q(nc.t("Effets et notifications rétablis.", "Effects and notifications restored.")))
    end
end

-- Flou coupé le temps d'un panneau plein écran (carrousel des fonds) : appelé par nc-shell-msg via « hyprctl eval »
function nc.flou(actif)
    hl.config({ decoration = { blur = { enabled = actif and nc.flou_actif } } })
end

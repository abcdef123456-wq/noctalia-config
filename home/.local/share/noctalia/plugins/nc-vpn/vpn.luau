--!nonstrict
-- nc/vpn : la pilule VPN de la barre, près du profil d'énergie (ajoutée par nc-reglages quand VPN_PILULE_BARRE=oui).
--   Contenu : bouclier MAISON (dessiné ici, en SVG) ; connecté : bouclier plein vert + fournisseur + drapeau et code du pays
--   RÉELLEMENT connectés ; déconnecté : bouclier vide et grisé, sans texte ; partage d'écran : « VPN » seul.
--   Clic : la fenêtre VPN de l'île (le même IPC que Super + Alt + V : qs -c nc-ile ipc call ile vpn), connecté ou non.
--   État POUSSÉ par l'île : $XDG_RUNTIME_DIR/nc-vpn-barre.json {connecte, fournisseur, pays, masque_partage}, écrit par
--   VpnEtat.qml quand il change. Ici : un simple stat (taille + date) toutes les 3 s, lecture du fichier seulement s'il a changé,
--   rien du tout écran éteint (fichier nc-ecran-eteint, comme musique.luau). Aucun nmcli, aucun réseau, aucune géolocalisation.
--   Pas de fichier (île arrêtée, réglage coupé, NetworkManager absent) : la pilule est cachée, et une pastille cachée ne garde
--   JAMAIS de zone de clic (onClick ne fait rien tant qu'elle est cachée).
-- Écrit en Lua simple (sans « += » ni types) : tests/test_vpn_barre.py le charge aussi avec lua.

local function env(nom)
  local v = noctalia.getenv and noctalia.getenv(nom)
  return (v and v ~= "") and v or nil
end
local RUN = env("XDG_RUNTIME_DIR") or "/tmp"
local ETAT = RUN .. "/nc-vpn-barre.json"
local ETEINT = RUN .. "/nc-ecran-eteint"          -- posé par nc-ecran écran éteint
local VERT, GRIS = "#30d158", "#98989d"            -- vert et gris système (comme l'île)
local INTERVALLE = 3000

local etat = nil               -- table lue du fichier, ou nil (caché)
local signature = ""           -- taille:date du fichier lu
local visible = nil
local dernierRendu = nil
local dossier = nil

local function montrer(v)
  if v ~= visible then visible = v; barWidget.setVisible(v) end
end

-- Bouclier maison : plein (connecté) ou contour (déconnecté), écrit une fois dans le dossier de données du plugin
local FORME = "M12 2.6 4.6 5.4v5.9c0 4.7 3.1 8.3 7.4 10.1 4.3-1.8 7.4-5.4 7.4-10.1V5.4L12 2.6Z"
local function bouclier(plein)
  if not dossier then
    dossier = (noctalia.pluginDataDir and noctalia.pluginDataDir() or (RUN .. "/nc-vpn-plugin")) .. "/bouclier-v1"
    noctalia.mkdirAll(dossier)
  end
  local f = dossier .. (plein and "/plein.svg" or "/vide.svg")
  if not noctalia.fileExists(f) then
    local corps
    if plein then
      corps = '<path fill="' .. VERT .. '" d="' .. FORME .. '"/><path fill="none" stroke="#000000" stroke-opacity=".55" stroke-width="2.2" '
        .. 'stroke-linecap="round" stroke-linejoin="round" d="M8.6 12.2l2.5 2.5 4.4-4.9"/>'
    else
      corps = '<path fill="none" stroke="' .. GRIS .. '" stroke-width="2.2" stroke-linejoin="round" d="' .. FORME .. '"/>'
    end
    noctalia.writeFile(f, '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">' .. corps .. "</svg>")
  end
  return f
end

-- « FR » : les deux indicateurs régionaux Unicode ; vide si ce n'est pas deux lettres majuscules
local function drapeau(cc)
  if type(cc) ~= "string" or not string.match(cc, "^%u%u$") then return "" end
  local a, b = string.byte(cc, 1), string.byte(cc, 2)
  return utf8.char(0x1F1E6 + a - 65, 0x1F1E6 + b - 65)
end

local function texte(e)
  if e.masque_partage == true then return "VPN" end
  if e.connecte ~= true then return "" end
  local t = type(e.fournisseur) == "string" and e.fournisseur or ""
  if t == "" then t = "VPN" end
  if type(e.pays) == "string" and string.match(e.pays, "^%u%u$") then t = t .. " · " .. drapeau(e.pays) .. " " .. e.pays end
  return t
end

function rendre()
  if not etat then montrer(false); return end
  local connecte = etat.connecte == true
  local t = texte(etat)
  local sig = (connecte and "1" or "0") .. "|" .. t
  montrer(true)
  if sig == dernierRendu then return end
  dernierRendu = sig
  local enfants = { ui.image({ key = "bouclier:" .. (connecte and "plein" or "vide"), path = bouclier(connecte), width = 17, height = 17, fit = "contain" }) }
  if t ~= "" then
    table.insert(enfants, ui.label({ text = t, maxLines = 1, fontWeight = "semibold", color = "on_surface" }))
  end
  barWidget.render(ui.row({ gap = 6, align = "center" }, enfants))
  barWidget.setTooltip(connecte and (t ~= "" and t or "VPN") or "VPN")
end

local function lire()
  local info = noctalia.fileInfo(ETAT)
  if not info then
    signature = ""
    etat = nil
    dernierRendu = nil
    rendre()
    return
  end
  local sig = tostring(info.size) .. ":" .. tostring(info.mtime)
  if sig == signature then return end                  -- inchangé : aucune lecture
  signature = sig
  local brut = noctalia.readFile(ETAT)
  local d = brut and noctalia.json.decode(brut) or nil
  if type(d) == "table" then etat = d else etat = nil end
  rendre()
end

-- DEBUT cadence (même forme que musique.luau) : écran éteint, plus rien n'est lu ; au rallumage, un contrôle tout de suite
function update()
  if noctalia.fileExists(ETEINT) then return end
  lire()
end
-- FIN cadence

-- Clic : la fenêtre VPN de l'île. Caché : aucune zone de clic, donc rien.
function onClick()
  if not visible then return end
  noctalia.runAsync({ "qs", "-c", "nc-ile", "ipc", "call", "ile", "vpn" }, function() end, 3000)
end

noctalia.setUpdateInterval(INTERVALLE)
montrer(false)
lire()

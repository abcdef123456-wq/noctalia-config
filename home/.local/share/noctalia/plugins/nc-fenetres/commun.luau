--!nonstrict
-- nc/fenetres : ce que partagent le titre de la barre et le menu de gestion (langue, actions, icônes)
local M = {}

-- Langue (nc-reglages → Apparence → Langue : auto, fr, en ; auto = celle du système)
local function env(nom)
  local v = noctalia.getenv and noctalia.getenv(nom)
  return (v and v ~= "") and v or nil
end
function M.langue()
  local l = env("NC_LANGUE")
  if l ~= "fr" and l ~= "en" then
    local conf = noctalia.readFile(noctalia.expandPath("~/.config/nc/reglages.conf")) or ""
    for k, v in string.gmatch(conf, "([%u%d_]+)=([^\n]*)") do
      if k == "LANGUE" then l = string.match(v, '^%s*"?(%a*)') end
    end
  end
  if l ~= "fr" and l ~= "en" then
    local loc = env("LC_ALL") or env("LC_MESSAGES") or env("LANG")
      or string.match(noctalia.readFile("/etc/locale.conf") or "", 'LANG="?([%w_.@-]+)') or ""
    l = string.sub(loc, 1, 2) == "fr" and "fr" or "en"
  end
  return l
end
M.EN = M.langue() == "en"
function M.tr(fr, en) return M.EN and en or fr end

M.NC = noctalia.expandPath("~/.local/bin/nc-fenetre")

-- Une action de nc-fenetre (aller, basculer, reduire, fermer, tout-masquer, tout-afficher), puis l'état relu
function M.faire(action, adresse, apres)
  local argv = { M.NC, action }
  if adresse then table.insert(argv, adresse) end
  noctalia.runAsync(argv, function() if apres then apres() end end, 5000)
end

-- Vue de toutes les fenêtres (île Quickshell, si elle tourne)
function M.vue()
  noctalia.runAsync({ "qs", "-c", "nc-ile", "ipc", "call", "ile", "vueOuvrir" })
end

-- Icône de l'appli (même recherche que la barre des tâches de Noctalia)
local icones = {}
function M.icone(classe, taille)
  local k = (classe or "") .. ":" .. taille
  if icones[k] == nil then
    icones[k] = (classe and classe ~= "" and noctalia.appIconPath(classe, taille * 2)) or false
  end
  return icones[k] or nil
end
function M.image(w, taille, opacite)
  local p = M.icone(w.classe, taille)
  if p then return ui.image({ path = p, width = taille, height = taille, fit = "contain", opacity = opacite }) end
  return ui.glyph({ name = "app-window", size = taille - 2, opacity = opacite })
end

function M.nom(w)
  if w.titre and w.titre ~= "" then return w.titre end
  return w.classe ~= "" and w.classe or M.tr("Fenêtre", "Window")
end

return M

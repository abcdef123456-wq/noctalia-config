-- Tes réglages de noctalia-config (~/.config/nc/reglages.conf, nc-reglages → Terminal) lus par Neovim au démarrage.
-- nc.reglage("NVIM_NUMEROS", "relatifs") : la valeur choisie, sinon le défaut (aussi sans noctalia-config).
local M = {}
local valeurs

local function lire()
  valeurs = {}
  local chemin = (os.getenv("XDG_CONFIG_HOME") or (os.getenv("HOME") .. "/.config")) .. "/nc/reglages.conf"
  local f = io.open(chemin)
  if not f then
    return
  end
  for ligne in f:lines() do
    local cle, v = ligne:match("^%s*([%u%d_]+)%s*=%s*(.-)%s*$")
    if cle then
      valeurs[cle] = v:gsub('^"(.*)"$', "%1")
    end
  end
  f:close()
end

function M.reglage(cle, defaut)
  if not valeurs then
    lire()
  end
  local v = valeurs[cle]
  if v == nil or v == "" then
    return defaut
  end
  return v
end

return M

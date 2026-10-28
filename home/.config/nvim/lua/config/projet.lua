-- Neovim ouvert par nc-code (variable NC_CODE=1, aucun fichier donné) : on arrive sur le projet, pas sur le tableau de
-- bord. S'il existe une session de ce dossier (plugin persistence), on la reprend ; sinon l'explorateur de fichiers de
-- Snacks et le README, ou à défaut le fichier modifié en dernier. Le tableau de bord reste pour « nvim » sans rien.
local M = {}

local IGNORES = { node_modules = true, target = true, build = true, dist = true, venv = true, __pycache__ = true }
local README = { "README.md", "README", "readme.md", "Readme.md", "README.rst", "README.txt", "README.markdown" }
local MAX_ENTREES = 300

-- Le fichier à ouvrir : le README du dossier, sinon le fichier le plus récent (dossier lui-même et un niveau dessous,
-- sans fichiers cachés, 300 entrées au plus). Aucun git.
function M.fichier(dossier)
  for _, nom in ipairs(README) do
    local st = vim.uv.fs_stat(dossier .. "/" .. nom)
    if st and st.type == "file" then
      return dossier .. "/" .. nom
    end
  end
  local meilleur, quand, vus = nil, -1, 0
  local function parcourir(d, profondeur)
    local h = vim.uv.fs_scandir(d)
    if not h then
      return
    end
    while vus < MAX_ENTREES do
      local nom, type_ = vim.uv.fs_scandir_next(h)
      if not nom then
        break
      end
      vus = vus + 1
      if nom:sub(1, 1) ~= "." and not IGNORES[nom] then
        local chemin = d .. "/" .. nom
        if type_ == "file" then
          local st = vim.uv.fs_stat(chemin)
          if st and st.mtime.sec > quand then
            meilleur, quand = chemin, st.mtime.sec
          end
        elseif type_ == "directory" and profondeur < 1 then
          parcourir(chemin, profondeur + 1)
        end
      end
    end
  end
  parcourir(dossier, 0)
  return meilleur
end

-- dep (pour les tests) : { persistence = module, explorateur = function }
function M.ouvrir(dep)
  dep = dep or {}
  local dossier = vim.fn.getcwd()
  local ok, pers = true, dep.persistence
  if not pers then
    ok, pers = pcall(require, "persistence")
  end
  if ok and type(pers) == "table" then
    local lisible = false
    for _, o in ipairs({ {}, { branch = false } }) do
      local ok2, f = pcall(pers.current, o)
      if ok2 and type(f) == "string" and vim.fn.filereadable(f) == 1 then
        lisible = true
      end
    end
    if lisible and pcall(pers.load) then
      return "session"
    end
  end
  local f = M.fichier(dossier)
  if f then
    vim.cmd("silent! edit " .. vim.fn.fnameescape(f))
  end
  local expl = dep.explorateur
  if not expl and _G.Snacks and Snacks.explorer then
    expl = function()
      Snacks.explorer()
    end
  end
  if expl then
    pcall(expl)
  end
  return f and "fichier" or "explorateur"
end

-- Appelé au démarrage : seulement dans nc-code et sans dossier ni fichier donné
function M.au_demarrage()
  if vim.env.NC_CODE ~= "1" or vim.fn.argc(-1) > 0 then
    return
  end
  vim.schedule(function()
    M.ouvrir()
  end)
end

return M

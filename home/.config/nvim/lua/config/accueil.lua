-- Tableau de bord de Neovim (Snacks) en français simple : les entrées de LazyVim (et de ses extras) sont traduites,
-- les doublons retirés, la ligne « Neovim prêt » en français, et une aide pour débutant quand Neovim est ouvert par
-- nc-code (variable NC_CODE=1 posée par la session kitty). Les touches ne changent pas.
local M = {}

-- Le texte anglais de LazyVim → le français (les entrées ajoutées par ce dépôt sont déjà en français)
M.traduction = {
  ["Find File"] = "Chercher un fichier",
  ["New File"] = "Nouveau fichier",
  ["Find Text"] = "Chercher du texte",
  ["Recent Files"] = "Fichiers récents",
  ["Config"] = "Configuration",
  ["Restore Session"] = "Reprendre la session",
  ["Lazy Extras"] = "Extensions",
  ["Lazy"] = "Plugins",
  ["Quit"] = "Quitter",
  ["Projects"] = "Projets",
  ["Projects (util.project)"] = "Projets",
}

M.aide_code = "À droite : ton agent IA. Écris-lui ce que tu veux faire. Ici : tes fichiers."

-- La première fois : trois phrases pour un débutant (les onglets, parler à l'agent, changer de panneau), puis plus jamais
-- (marqueur dans $XDG_STATE_HOME/nc/code-aide-vue) ; ensuite la seule ligne ci-dessus
M.aide_premiere = {
  "Trois onglets en haut : Code (Neovim à gauche, ton agent IA à droite), Git (lazygit) et Terminal.",
  "Pour parler à l'agent, clique dans le panneau de droite, écris en français ce que tu veux faire, puis Entrée.",
  "Pour changer de panneau : clique dessus, ou Ctrl+Maj+] et Ctrl+Maj+[ (Ctrl+L et Ctrl+H si ton kitty les a réglés). Message affiché une seule fois.",
}

function M.fichier_aide_vue()
  local base = vim.env.XDG_STATE_HOME
  if not base or base == "" then
    base = (vim.env.HOME or "") .. "/.local/state"
  end
  return base .. "/nc/code-aide-vue"
end

-- Vrai (et noté) la toute première fois seulement
function M.premiere_fois()
  local f = M.fichier_aide_vue()
  if vim.uv.fs_stat(f) then
    return false
  end
  pcall(vim.fn.mkdir, vim.fn.fnamemodify(f, ":h"), "p", "0700")
  local h = io.open(f, "w")
  if h then
    h:close()
  end
  return true
end

-- L'aide du haut : seulement dans l'espace de code ; ailleurs rien (pas de bruit)
function M.aide()
  if vim.env.NC_CODE == "1" then
    return M.aide_code
  end
  return nil
end

-- « Neovim prêt : 4/62 plugins en 23,6 ms » (virgule décimale)
function M.pied(charges, total, ms)
  return string.format("Neovim prêt : %d/%d plugins en %s ms", charges, total, (string.format("%.1f", ms):gsub("%.", ",")))
end

function M.section_pied()
  local ok, stats = pcall(function()
    return require("lazy.stats").stats()
  end)
  if not ok or type(stats) ~= "table" then
    return nil
  end
  return {
    align = "center",
    text = { { "⚡ " .. M.pied(stats.loaded or 0, stats.count or 0, stats.startuptime or 0), hl = "footer" } },
  }
end

-- Traduit les entrées et retire les doublons (même texte français) ; les touches ne changent pas
function M.touches(touches)
  local vus, res = {}, {}
  for _, t in ipairs(touches) do
    local desc = t.desc
    if type(desc) == "string" then
      desc = M.traduction[vim.trim(desc)] or desc
    end
    if type(desc) ~= "string" or not vus[desc] then
      if type(desc) == "string" then
        vus[desc] = true
      end
      t.desc = desc
      table.insert(res, t)
    end
  end
  return res
end

-- Adapte les options de Snacks (opts.dashboard) : touches, sections, pied
function M.adapter(opts)
  opts.dashboard = opts.dashboard or {}
  local d = opts.dashboard
  d.preset = d.preset or {}
  if type(d.preset.keys) == "table" then
    d.preset.keys = M.touches(d.preset.keys)
  end
  local sections = {}
  local aide = M.aide()
  if aide then
    if M.premiere_fois() then
      for i, ligne in ipairs(M.aide_premiere) do
        table.insert(sections, { text = { { ligne, hl = "special" } }, align = "center", padding = i == #M.aide_premiere and 1 or 0 })
      end
    else
      table.insert(sections, { text = { { aide, hl = "special" } }, align = "center", padding = 1 })
    end
  end
  vim.list_extend(sections, {
    { section = "header" },
    { section = "keys", gap = 1, padding = 1 },
    { icon = " ", title = "Fichiers récents", section = "recent_files", indent = 2, padding = 1 },
    M.section_pied,
  })
  d.sections = sections
  return opts
end

return M

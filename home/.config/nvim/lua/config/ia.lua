-- L'IA du bureau dans Neovim (nc-ia : celle choisie dans nc-reglages → Intelligence artificielle, ou aucune).
-- Menu « Espace i » (lua/config/keymaps.lua) : demander, expliquer, transformer ou corriger les lignes sélectionnées.
-- Le texte passe par l'entrée standard de nc-ia, jamais en argument ; rien ne bloque l'éditeur pendant la réponse.
-- (« Espace a » reste Claude Code dans Neovim, l'extra LazyVim claudecode.)
local M = {}
local nc_ia = os.getenv("HOME") .. "/.local/bin/nc-ia"

-- Les lignes de la dernière sélection (après Échap, les marques '< et '> sont posées)
local function lignes_choisies()
  local debut, fin = vim.fn.line("'<"), vim.fn.line("'>")
  if debut == 0 or fin == 0 then
    return nil
  end
  return debut, fin, vim.api.nvim_buf_get_lines(0, debut - 1, fin, false)
end

local function lancer(args, texte, fini)
  if vim.fn.executable(nc_ia) ~= 1 then
    vim.notify("nc-ia est introuvable (~/.local/bin/nc-ia).", vim.log.levels.ERROR)
    return
  end
  vim.notify("L'IA réfléchit…", vim.log.levels.INFO, { title = "IA" })
  vim.system(vim.list_extend({ nc_ia }, args), { stdin = texte or "", text = true }, function(r)
    vim.schedule(function()
      local sortie = (r.stdout or ""):gsub("%s+$", "")
      if r.code ~= 0 or sortie == "" then
        local erreur = (r.stderr or ""):gsub("%s+$", "")
        vim.notify(erreur ~= "" and erreur or "L'IA n'a rien répondu.", vim.log.levels.WARN, { title = "IA" })
        return
      end
      fini(sortie)
    end)
  end)
end

-- La réponse dans une fenêtre flottante (Markdown), refermée par q ou Échap
local function montrer(texte)
  local _, fen = vim.lsp.util.open_floating_preview(vim.split(texte, "\n"), "markdown",
    { border = "rounded", max_width = math.floor(vim.o.columns * 0.7), max_height = math.floor(vim.o.lines * 0.7),
      focus_id = "nc-ia" })
  if fen and vim.api.nvim_win_is_valid(fen) then
    vim.api.nvim_set_current_win(fen)
    local buf = vim.api.nvim_win_get_buf(fen)
    for _, touche in ipairs({ "q", "<Esc>" }) do
      vim.keymap.set("n", touche, "<Cmd>close<CR>", { buffer = buf, nowait = true })
    end
  end
end

-- Une question ; en visuel, les lignes choisies l'accompagnent
function M.demander(visuel)
  local contexte = ""
  if visuel then
    local _, _, l = lignes_choisies()
    contexte = l and table.concat(l, "\n") or ""
  end
  vim.ui.input({ prompt = "Question à l'IA : " }, function(q)
    if not q or q == "" then
      return
    end
    if contexte ~= "" then
      local ft = vim.bo.filetype ~= "" and vim.bo.filetype or "texte"
      lancer({ "texte", q, "--stdin" }, "(" .. ft .. ")\n" .. contexte, montrer)
    else
      lancer({ "demander", "-" }, q, montrer)
    end
  end)
end

function M.expliquer()
  local _, _, l = lignes_choisies()
  if l then
    lancer({ "texte", "expliquer", "--stdin" }, table.concat(l, "\n"), montrer)
  end
end

-- Les lignes choisies remplacées par le résultat (annulable avec u)
local function remplacer(action)
  local debut, fin, l = lignes_choisies()
  if not l then
    return
  end
  local buf = vim.api.nvim_get_current_buf()
  lancer({ "texte", action, "--stdin" }, table.concat(l, "\n"), function(sortie)
    if vim.api.nvim_buf_is_valid(buf) then
      vim.api.nvim_buf_set_lines(buf, debut - 1, fin, false, vim.split(sortie, "\n"))
    end
  end)
end

function M.transformer()
  vim.ui.input({ prompt = "Consigne pour la sélection : " }, function(c)
    if c and c ~= "" then
      remplacer(c)
    end
  end)
end

function M.corriger()
  remplacer("corriger")
end

return M

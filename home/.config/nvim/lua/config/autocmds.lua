-- Automatismes, chargés après les plugins (VeryLazy). Ceux de LazyVim restent (rouvrir à la dernière position,
-- fermer l'aide avec q, correction orthographique en Markdown…) :
-- https://github.com/LazyVim/LazyVim/blob/main/lua/lazyvim/config/autocmds.lua
-- Pour en retirer un : vim.api.nvim_del_augroup_by_name("lazyvim_wrap_spell") par exemple.
local groupe = vim.api.nvim_create_augroup("nc", { clear = true })

-- Les fichiers du bureau (réglages nc-*, .conf, TOML) : indentation à 4 espaces, comme dans le dépôt
vim.api.nvim_create_autocmd("FileType", {
  group = groupe,
  pattern = { "conf", "toml", "hyprlang" },
  callback = function()
    vim.opt_local.expandtab = true
    vim.opt_local.shiftwidth = 4
    vim.opt_local.tabstop = 4
  end,
})

-- Fichier modifié ailleurs : vérifié au retour dans Neovim (autoread fait le reste)
vim.api.nvim_create_autocmd({ "FocusGained", "TermClose", "TermLeave" }, {
  group = groupe,
  command = "checktime",
})

-- Le texte collé ou copié clignote un instant (on voit ce qui a été pris)
vim.api.nvim_create_autocmd("TextYankPost", {
  group = groupe,
  callback = function()
    vim.hl.on_yank({ timeout = 150 })
  end,
})

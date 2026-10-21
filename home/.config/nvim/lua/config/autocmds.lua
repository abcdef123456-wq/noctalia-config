-- Automatismes, chargés après les plugins (VeryLazy). Ceux de LazyVim restent (rouvrir à la dernière position,
-- fermer l'aide avec q, correction orthographique en Markdown…) :
-- https://github.com/LazyVim/LazyVim/blob/main/lua/lazyvim/config/autocmds.lua
-- Pour en retirer un : vim.api.nvim_del_augroup_by_name("lazyvim_wrap_spell") par exemple.
local groupe = vim.api.nvim_create_augroup("nc", { clear = true })

-- Les fichiers du bureau (Hyprland en Lua, réglages nc-*) : pas d'indentation automatique surprenante sur les .conf
vim.api.nvim_create_autocmd("FileType", {
  group = groupe,
  pattern = { "conf", "toml" },
  callback = function()
    vim.opt_local.expandtab = true
    vim.opt_local.shiftwidth = 4
  end,
})

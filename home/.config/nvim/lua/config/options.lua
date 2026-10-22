-- Options, chargées avant lazy.nvim. Celles de LazyVim restent (numéros relatifs, presse-papiers du système,
-- indentation à 2, recherche sans casse…) : https://github.com/LazyVim/LazyVim/blob/main/lua/lazyvim/config/options.lua
-- Ici, seulement ce qui change par rapport à LazyVim.

-- Le curseur garde 8 lignes de marge en haut et en bas en défilant
vim.opt.scrolloff = 8

local nc = require("config.nc")

-- Retour à la ligne (nc-reglages → Terminal → Retour à la ligne dans Neovim) ; Markdown garde le sien via LazyVim
vim.opt.wrap = nc.reglage("NVIM_RETOUR_LIGNE", "non") == "oui"

-- Numéros de ligne (nc-reglages → Terminal → Numéros de ligne de Neovim) : relatifs, absolus ou aucun
local numeros = nc.reglage("NVIM_NUMEROS", "relatifs")
vim.opt.number = numeros ~= "aucun"
vim.opt.relativenumber = numeros == "relatifs"

-- Fenêtres flottantes (aide, survol LSP, menus) aux coins arrondis, comme l'île (option de Neovim 0.11 ;
-- Debian 13 a la 0.10.4, où elle n'existe pas)
if vim.fn.has("nvim-0.11") == 1 then
  vim.opt.winborder = "rounded"
end

-- Presse-papiers : LazyVim prend déjà celui du système (« unnamedplus », par wl-copy), sauf en SSH où il laisse
-- passer l'OSC 52 du terminal ; rien à changer ici.

-- Les tabulations et espaces de fin se voient (utile dans les scripts et les .conf)
vim.opt.list = true
vim.opt.listchars = { tab = "» ", trail = "·", nbsp = "␣" }

-- Fichier modifié ailleurs (nc-maj, un script) : rechargé tout seul s'il n'est pas édité ici
vim.opt.autoread = true

-- Historique d'annulation gardé d'une session à l'autre
vim.opt.undofile = true

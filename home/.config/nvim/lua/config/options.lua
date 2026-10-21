-- Options, chargées avant lazy.nvim. Celles de LazyVim restent (numéros relatifs, presse-papiers du système,
-- indentation à 2, recherche sans casse…) : https://github.com/LazyVim/LazyVim/blob/main/lua/lazyvim/config/options.lua
-- Ici, seulement ce qui change par rapport à LazyVim.

-- Le curseur garde 8 lignes de marge en haut et en bas en défilant
vim.opt.scrolloff = 8

-- Pas de retour à la ligne automatique dans le texte (Markdown garde le sien via LazyVim)
vim.opt.wrap = false

-- Fenêtres flottantes (aide, survol LSP, menus) aux coins arrondis, comme l'île
vim.opt.winborder = "rounded"

-- Les tabulations et espaces de fin se voient (utile dans les scripts et les .conf)
vim.opt.list = true
vim.opt.listchars = { tab = "» ", trail = "·", nbsp = "␣" }

-- Fichier modifié ailleurs (nc-maj, un script) : rechargé tout seul s'il n'est pas édité ici
vim.opt.autoread = true

-- Historique d'annulation gardé d'une session à l'autre
vim.opt.undofile = true

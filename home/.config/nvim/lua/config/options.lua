-- Options, chargées avant lazy.nvim. Celles de LazyVim restent (numéros relatifs, presse-papiers du système,
-- indentation à 2, recherche sans casse…) : https://github.com/LazyVim/LazyVim/blob/main/lua/lazyvim/config/options.lua
-- Ici, seulement ce qui change par rapport à LazyVim.

-- Le curseur garde 8 lignes de marge en haut et en bas en défilant
vim.opt.scrolloff = 8

-- Pas de retour à la ligne automatique dans le texte (Markdown garde le sien via LazyVim)
vim.opt.wrap = false

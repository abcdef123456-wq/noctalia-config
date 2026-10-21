-- Raccourcis, chargés après les plugins (VeryLazy). Ceux de LazyVim restent (Espace ouvre le menu, Espace e les
-- fichiers, Espace / la recherche…) : https://github.com/LazyVim/LazyVim/blob/main/lua/lazyvim/config/keymaps.lua
-- Ici, seulement les ajouts.
local map = vim.keymap.set

-- Ctrl + S enregistre, dans tous les modes (réflexe des autres éditeurs)
map({ "n", "i", "v" }, "<C-s>", "<Cmd>w<CR><Esc>", { desc = "Enregistrer" })

-- Échap efface aussi le surlignage de la dernière recherche
map("n", "<Esc>", "<Cmd>nohlsearch<CR><Esc>", { desc = "Effacer le surlignage" })

-- Alt + flèches déplacent la ligne (ou la sélection) vers le haut ou le bas
map("n", "<A-Down>", "<Cmd>m .+1<CR>==", { desc = "Descendre la ligne" })
map("n", "<A-Up>", "<Cmd>m .-2<CR>==", { desc = "Monter la ligne" })
map("v", "<A-Down>", ":m '>+1<CR>gv=gv", { desc = "Descendre la sélection" })
map("v", "<A-Up>", ":m '<-2<CR>gv=gv", { desc = "Monter la sélection" })

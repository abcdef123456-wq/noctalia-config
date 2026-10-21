-- Raccourcis, chargés après les plugins (VeryLazy). Ceux de LazyVim restent (Espace ouvre le menu, Espace e les
-- fichiers, Espace / la recherche, Espace g g l'interface Git…) :
-- https://github.com/LazyVim/LazyVim/blob/main/lua/lazyvim/config/keymaps.lua
-- Ici, seulement les ajouts. Le menu « Espace n » (bureau Noctalia) est dans lua/plugins/bureau.lua.
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

-- Collé par-dessus une sélection sans perdre ce qu'on vient de copier
map("x", "p", '"_dP', { desc = "Coller sans écraser le presse-papiers" })

-- Indenter ou désindenter une sélection sans la perdre
map("v", "<", "<gv", { desc = "Désindenter" })
map("v", ">", ">gv", { desc = "Indenter" })

-- Le curseur reste au milieu quand on saute d'une page ou d'un résultat de recherche
map("n", "<C-d>", "<C-d>zz")
map("n", "<C-u>", "<C-u>zz")
map("n", "n", "nzzzv")
map("n", "N", "Nzzzv")

-- Ctrl + Entrée en insertion : nouvelle ligne en dessous sans couper la ligne courante
map("i", "<C-CR>", "<Esc>o", { desc = "Nouvelle ligne en dessous" })

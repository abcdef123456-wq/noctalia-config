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

-- Ctrl + C en visuel copie la sélection dans le presse-papiers du système (registre +, donc aussi sous SSH où LazyVim ne
-- met pas unnamedplus). En mode normal, Ctrl + C reste une interruption ; Échap quitte toujours le mode visuel.
map("x", "<C-c>", '"+y', { desc = "Copier (presse-papiers)" })

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

-- IA du bureau (nc-ia, lua/config/ia.lua) : Espace i… ; en visuel, sur les lignes choisies.
-- Les demandes s'écrivent dans une fenêtre (Ctrl + S envoie, q annule, Ctrl + P / Ctrl + N l'historique).
local ia = require("config.ia")
local function visuel(f)
  return "<Esc><Cmd>lua require('config.ia')." .. f .. "(true)<CR>"
end
map("n", "<leader>ii", function() ia.demander(false) end, { desc = "Demander à l'IA" })
map("x", "<leader>ii", visuel("demander"), { desc = "Demander à l'IA (sur la sélection)" })
map("x", "<leader>ie", visuel("expliquer"), { desc = "Expliquer la sélection" })
map("x", "<leader>it", visuel("transformer"), { desc = "Transformer la sélection (consigne)" })
map("x", "<leader>ic", visuel("corriger"), { desc = "Corriger la sélection" })
map("n", "<leader>if", function() ia.faire(false) end, { desc = "Faire une tâche (aperçu avant d'insérer)" })
map("x", "<leader>if", visuel("faire"), { desc = "Faire la tâche décrite (aperçu avant d'insérer)" })
-- Les agents sur le projet (panneau sidekick.nvim, l'agent de l'IA choisie ; sans lui, un terminal en bas)
map("n", "<leader>ia", function() ia.agent_panneau(false) end, { desc = "Agents : ouvrir ou masquer le panneau (IA choisie)" })
map("x", "<leader>ia", visuel("agent_panneau"), { desc = "Agents : ouvrir le panneau (IA choisie)" })
map({ "n", "x" }, "<leader>iA", function() ia.choisir_panneau() end, { desc = "Agents : choisir l'agent" })
map({ "n", "x" }, "<leader>is", function() ia.envoyer("{this}") end, { desc = "Agents : envoyer le code ou la sélection" })
map({ "n", "x" }, "<leader>ip", function() ia.prompt() end, { desc = "Agents : choisir un prompt" })
map("n", "<leader>iF", function() ia.envoyer("{file}") end, { desc = "Agents : envoyer le fichier" })
map({ "n", "t", "i", "x" }, "<C-.>", function() ia.focus_panneau() end, { desc = "Agents : aller au panneau" })
map("n", "<leader>iw", function() require("config.agents").aller() end, { desc = "Aller au terminal d'un agent suivi" })
-- Message de commit (dans git commit, lazygit, fugitive…) et diagnostic de la ligne
map("n", "<leader>im", function() ia.commit() end, { desc = "Écrire le message de commit" })
map("n", "<leader>id", function() ia.diagnostic() end, { desc = "Expliquer et corriger le diagnostic de la ligne" })

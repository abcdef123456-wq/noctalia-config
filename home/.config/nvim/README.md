# Neovim

Une [LazyVim](https://lazyvim.github.io) avec ses extras (C/C++, JavaScript, formatage, Git, projets…), et quelques
choix maison. Installée par `install.sh` (étape 3b) ; `lazy.nvim` télécharge les plugins au premier lancement.

- `lua/config/lazy.lua` : amorçage de lazy.nvim et de LazyVim (le fichier d'origine du modèle).
- `lua/config/options.lua`, `keymaps.lua`, `autocmds.lua` : ce qui change par rapport à LazyVim, commenté.
- `lua/plugins/completion.lua` : une fonction proposée par la complétion s'insère par son nom seul (plus de signature
  entière à parcourir avec Tab, plus de carré ∎ en fin de snippet) ; Entrée valide la proposition sélectionnée.
- `lua/plugins/interface.lua` : le thème suit le bureau (sombre ou clair, d'après les couleurs du fond d'écran).
- `lazyvim.json` : les extras activés (`:LazyExtras` pour en changer).

Mettre à jour les plugins : `:Lazy sync`. Les outils de langage (serveurs LSP, formateurs) : `:Mason`.

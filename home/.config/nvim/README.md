# Neovim

Une [LazyVim](https://lazyvim.github.io) avec ses extras, et des choix maison pour ce bureau. Installée par
`install.sh` (étape 3b) ; `lazy.nvim` télécharge les plugins au premier lancement, Mason les outils de langage.

## Ce qui est à nous

- `lua/plugins/completion.lua` : une fonction proposée par la complétion s'insère par son nom seul (plus de signature
  entière à parcourir avec Tab, plus de carré ∎ en fin de snippet) ; Entrée valide la proposition sélectionnée.
- `lua/plugins/langages.lua` : tree-sitter pour tout ce qui vit dans le dépôt (Lua, QML, shell, Python, TOML, JSON,
  CSS, Markdown…), serveur shell avec shellcheck, QML si `qmlls` est installé, scripts `nc-*` reconnus d'après leur
  shebang, `.conf` de nc-reglages.
- `lua/plugins/bureau.lua` : le menu **Espace n** (Noctalia) : config Hyprland, île, scripts `nc-*`, tes réglages,
  `perso.lua`, le dépôt, `nc-reglages` et le journal de l'île dans un terminal flottant, `nc-theme-sync`. Les fichiers
  du bureau ne sont jamais reformatés à l'enregistrement (ils gardent leur style).
- `lua/plugins/interface.lua` : thème sombre ou clair d'après les couleurs du fond d'écran, tableau de bord Snacks,
  fenêtres flottantes arrondies comme l'île.
- `lua/config/options.lua`, `keymaps.lua`, `autocmds.lua` : ce qui change par rapport à LazyVim, commenté (Ctrl + S,
  Alt + flèches, coller sans écraser le presse-papiers, fichiers rechargés quand ils changent ailleurs…).
- `lazyvim.json` : les extras activés (`:LazyExtras` pour en changer) : Python, Markdown, TOML, YAML, Docker, Git,
  C/C++, JavaScript, formatage, historique du presse-papiers (yanky), Harpoon, renommage en direct, plan du fichier
  (outline), couleurs affichées dans le texte, et **Claude Code** dans Neovim (`claudecode.nvim`, Espace a).

Mettre à jour les plugins : `:Lazy sync`. Les outils de langage : `:Mason`. L'aide des raccourcis : Espace, puis
attendre une demi-seconde.

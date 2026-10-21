-- Apparence : le thème suit le bureau. nc-theme-sync note dans ~/.config/nc/palette-ile.json si les couleurs du
-- fond d'écran sont sombres ou claires ; Neovim ouvre alors tokyonight-moon (sombre) ou tokyonight-day (clair).
-- Sans ce fichier (autre bureau, serveur) : sombre. Fenêtres flottantes aux coins arrondis, comme l'île ;
-- tableau de bord Snacks au démarrage (fichiers récents, projets, état Git).
local function bureau_sombre()
  local chemin = (os.getenv("XDG_CONFIG_HOME") or (os.getenv("HOME") .. "/.config")) .. "/nc/palette-ile.json"
  local f = io.open(chemin)
  if not f then
    return true
  end
  local texte = f:read("*a") or ""
  f:close()
  return texte:match('"sombre"%s*:%s*false') == nil
end

return {
  {
    "LazyVim/LazyVim",
    opts = {
      colorscheme = function()
        vim.cmd.colorscheme(bureau_sombre() and "tokyonight-moon" or "tokyonight-day")
      end,
    },
  },
  {
    "folke/tokyonight.nvim",
    opts = { transparent = false, styles = { floats = "normal", sidebars = "normal" } },
  },
  {
    "folke/snacks.nvim",
    opts = {
      dashboard = {
        preset = {
          header = table.concat({
            "               _        _ _",
            " _ __   ___   ___| |_ __ _| (_) __ _",
            "| '_ \\ / _ \\ / __| __/ _` | | |/ _` |",
            "| | | | (_) | (__| || (_| | | | (_| |",
            "|_| |_|\\___/ \\___|\\__\\__,_|_|_|\\__,_|",
            "",
          }, "\n"),
        },
        sections = {
          { section = "header" },
          { section = "keys", gap = 1, padding = 1 },
          { icon = " ", title = "Fichiers récents", section = "recent_files", indent = 2, padding = 1 },
          { icon = " ", title = "Projets", section = "projects", indent = 2, padding = 1 },
          { section = "startup" },
        },
      },
      -- Coins arrondis pour les fenêtres flottantes de Snacks (pickers, terminal, notifications)
      styles = { float = { border = "rounded" }, notification = { border = "rounded" } },
    },
  },
}

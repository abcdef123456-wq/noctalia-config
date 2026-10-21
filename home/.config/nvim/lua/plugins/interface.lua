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

-- Thème choisi dans nc-reglages → Terminal → Thème de Neovim (NVIM_THEME) ; « auto » : d'après le bureau
local function theme_choisi()
  local chemin = (os.getenv("XDG_CONFIG_HOME") or (os.getenv("HOME") .. "/.config")) .. "/nc/reglages.conf"
  local f = io.open(chemin)
  if not f then
    return "auto"
  end
  local texte = f:read("*a") or ""
  f:close()
  return texte:match("\nNVIM_THEME=\"?([%w%-]+)") or texte:match("^NVIM_THEME=\"?([%w%-]+)") or "auto"
end

return {
  {
    "LazyVim/LazyVim",
    opts = {
      colorscheme = function()
        local choix = theme_choisi()
        if choix == "auto" or not pcall(vim.cmd.colorscheme, choix) then
          vim.cmd.colorscheme(bureau_sombre() and "tokyonight-moon" or "tokyonight-day")
        end
      end,
    },
  },
  -- Fond transparent (nc-reglages → Terminal → Fond transparent dans Neovim) : celui du terminal se voit derrière
  {
    "folke/tokyonight.nvim",
    opts = function(_, opts)
      local transparent = require("config.nc").reglage("NVIM_TRANSPARENT", "non") == "oui"
      opts.transparent = transparent
      opts.styles = { floats = transparent and "transparent" or "normal", sidebars = transparent and "transparent" or "normal" }
      return opts
    end,
  },
  {
    "catppuccin/nvim",
    optional = true,
    opts = function(_, opts)
      opts.transparent_background = require("config.nc").reglage("NVIM_TRANSPARENT", "non") == "oui"
      return opts
    end,
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

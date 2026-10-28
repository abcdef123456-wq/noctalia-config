-- Apparence : le thème suit le bureau. nc-theme-sync écrit les couleurs du fond d'écran dans
-- ~/.config/nc/palette-ile.json ; Neovim prend tokyonight (moon si sombre, day si clair) repeint avec ces couleurs,
-- comme kitty, et se met à jour tout seul quand le fond change (lua/config/noctalia.lua).
-- Sans ce fichier (autre bureau, serveur) : tokyonight-moon normal. Fenêtres flottantes aux coins arrondis, comme l'île ;
-- tableau de bord Snacks au démarrage (fichiers récents, projets, état Git).
-- Thème choisi dans nc-reglages → Terminal → Thème de Neovim (NVIM_THEME) ; « auto » ou « noctalia » : les couleurs du fond
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
        if choix == "auto" or choix == "noctalia" or not pcall(vim.cmd.colorscheme, choix) then
          require("config.noctalia").activer()
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
      opts.on_colors = function(c)
        require("config.noctalia").on_colors(c)
      end
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
      },
      -- Coins arrondis pour les fenêtres flottantes de Snacks (pickers, terminal, notifications)
      styles = { float = { border = "rounded" }, notification = { border = "rounded" } },
    },
  },
  -- Tableau de bord en français (config/accueil.lua) : entrées traduites, doublons retirés, aide dans nc-code
  {
    "folke/snacks.nvim",
    opts = function(_, opts)
      return require("config.accueil").adapter(opts)
    end,
  },
}

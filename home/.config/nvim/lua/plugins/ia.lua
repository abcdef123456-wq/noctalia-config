-- L'IA dans Neovim, côté plugins (les touches « Espace i » et leurs fonctions : lua/config/keymaps.lua, ia.lua) :
--  - sidekick.nvim : le panneau d'agents en terminal (claude, codex, gemini, opencode… ceux qui sont installés).
--    Seulement le panneau : pas de « next edit suggestions » (donc ni Copilot ni serveur lancé), et pas l'extra
--    LazyVim ai.sidekick, dont les touches (Espace a…) se marcheraient dessus avec Claude Code.
--  - claudecode.nvim (extra ai.claudecode) : Claude Code en IDE, diffs à accepter dans Neovim, sous Espace a ;
--    ses touches sont reprises ici pour dire « IA désactivée » quand l'IA est coupée.
--  - un élément lualine pour les agents suivis par nc-claude, yazi si installé, deux entrées du tableau de bord.
local function garde(commande)
  return function()
    if not require("config.ia").refuse() then
      vim.cmd(commande)
    end
  end
end

-- Les agents que sidekick ne connaît pas encore (les autres : claude, codex, gemini, opencode, qwen, cursor, copilot…)
local OUTILS = {
  omp = { cmd = { "omp" } },
  ["kiro-cli"] = { cmd = { "kiro-cli", "chat" } },
  amp = { cmd = { "amp" } },
  goose = { cmd = { "goose" } },
}

return {
  {
    "folke/which-key.nvim",
    opts = {
      spec = {
        { "<leader>a", group = "Agents (Claude Code)", icon = { icon = "󰚩", color = "orange" }, mode = { "n", "v" } },
        { "<leader>iw", icon = { icon = "󰍹", color = "cyan" } },
      },
    },
  },

  {
    "folke/sidekick.nvim",
    lazy = true,
    opts = {
      nes = { enabled = false }, -- pas de suggestions d'édition : ni Copilot, ni serveur de langage
      cli = {
        tools = OUTILS,
        -- Des demandes toutes faites (Espace i p), en français ; {this}, {file}… sont remplacés par le contexte
        -- stylua: ignore
        prompts = {
          expliquer       = "Explique {this} en français simple.",
          corriger        = "Corrige {this} et dis ce qui n'allait pas.",
          revoir          = "Relis {file} : y a-t-il des erreurs ou des choses à améliorer ?",
          changements     = "Relis mes changements en cours et dis-moi ce qui ne va pas.",
          tests           = "Écris des tests pour {this}.",
          documenter      = "Ajoute la documentation de {function|line}.",
          optimiser       = "Comment optimiser {this} ?",
          diagnostics     = "Aide-moi à corriger les diagnostics de {file} :\n{diagnostics}",
          diagnostics_tous = "Aide-moi à corriger ces diagnostics :\n{diagnostics_all}",
        },
      },
    },
  },

  -- Claude Code en IDE : mêmes touches que l'extra, mais l'IA coupée les arrête avec un message
  {
    "coder/claudecode.nvim",
    keys = {
      { "<leader>ac", garde("ClaudeCode"), desc = "Ouvrir ou fermer Claude" },
      { "<leader>af", garde("ClaudeCodeFocus"), desc = "Aller à Claude" },
      { "<leader>ar", garde("ClaudeCode --resume"), desc = "Reprendre la dernière conversation" },
      { "<leader>aC", garde("ClaudeCode --continue"), desc = "Continuer la conversation" },
      { "<leader>ab", garde("ClaudeCodeAdd %"), desc = "Ajouter ce fichier à Claude" },
      { "<leader>as", garde("ClaudeCodeSend"), mode = "v", desc = "Envoyer la sélection à Claude" },
      { "<leader>as", garde("ClaudeCodeTreeAdd"), desc = "Ajouter le fichier", ft = { "NvimTree", "neo-tree", "oil" } },
      { "<leader>aa", garde("ClaudeCodeDiffAccept"), desc = "Accepter la modification" },
      { "<leader>ad", garde("ClaudeCodeDiffDeny"), desc = "Refuser la modification" },
    },
  },

  -- L'état des agents suivis par nc-claude, dans la barre : rien tant qu'aucun agent ne travaille ni n'attend
  {
    "nvim-lualine/lualine.nvim",
    optional = true,
    opts = function(_, opts)
      local agents = require("config.agents")
      agents.demarrer()
      opts.sections = opts.sections or {}
      opts.sections.lualine_x = opts.sections.lualine_x or {}
      table.insert(opts.sections.lualine_x, 1, agents.composant())
    end,
  },

  -- Le gestionnaire de fichiers yazi, seulement s'il est installé
  {
    "mikavilpas/yazi.nvim",
    cond = function()
      return vim.fn.executable("yazi") == 1
    end,
    event = "VeryLazy",
    keys = {
      { "<leader>-", "<Cmd>Yazi<CR>", mode = { "n", "v" }, desc = "Ouvrir yazi sur le fichier courant" },
    },
    opts = {
      open_for_directories = false,
      yazi_floating_window_border = "rounded",
    },
  },

  -- Tableau de bord : deux entrées de plus (la liste des touches est celle de LazyVim, complétée ici)
  {
    "folke/snacks.nvim",
    opts = function(_, opts)
      local touches = vim.tbl_get(opts, "dashboard", "preset", "keys")
      if type(touches) ~= "table" then
        return
      end
      local ajout = {
        { icon = "󰚩 ", key = "i", desc = "Demander à l'IA", action = ":lua require('config.ia').demander(false)" },
        { icon = "󰆍 ", key = "a", desc = "Agent sur le projet", action = ":lua require('config.ia').agent_panneau(false)" },
      }
      local pos = #touches + 1
      for i, t in ipairs(touches) do
        if t.key == "s" or t.key == "x" then
          pos = i
          break
        end
      end
      for n, t in ipairs(ajout) do
        table.insert(touches, pos + n - 1, t)
      end
    end,
  },
}

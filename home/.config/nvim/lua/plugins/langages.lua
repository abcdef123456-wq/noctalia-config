-- Langages du bureau : Lua (Hyprland), QML (l'île), shell (scripts nc-*), Python, TOML, JSON, CSS, Markdown.
-- Les extras LazyVim (lazyvim.json) apportent Python, Markdown, TOML, YAML, JSON, Docker, Git ; ici le reste.
return {
  -- Coloration et textobjects : les parseurs tree-sitter de tout ce qui vit dans ce dépôt
  {
    "nvim-treesitter/nvim-treesitter",
    opts = function(_, opts)
      vim.list_extend(opts.ensure_installed, {
        "bash", "css", "diff", "git_config", "git_rebase", "gitcommit", "gitignore", "ini", "javascript", "json", "jsonc",
        "lua", "luadoc", "luap", "markdown", "markdown_inline", "python", "qmljs", "regex", "toml", "vim", "vimdoc", "yaml",
      })
    end,
  },
  -- Serveurs de langage : shell (bashls + shellcheck), QML si qmlls est là (paquet qt6-declarative), Lua et Python par
  -- LazyVim. qmlls ne connaît pas les modules Quickshell : il souligne les imports de l'île, mais reste utile pour la
  -- syntaxe, le survol et les sauts dans un même fichier.
  {
    "neovim/nvim-lspconfig",
    opts = {
      servers = {
        bashls = {
          filetypes = { "sh", "bash", "zsh" },
          settings = { bashIde = { shellcheckArguments = { "-x" } } },
        },
        qmlls = { enabled = vim.fn.executable("qmlls") == 1, mason = false, cmd = { "qmlls", "-E" } },
      },
    },
  },
  -- Outils installés par Mason (formatage et vérification du shell en plus de ceux de LazyVim)
  {
    "mason-org/mason.nvim",
    opts = { ensure_installed = { "bash-language-server", "shellcheck", "shfmt", "stylua" } },
  },
  -- Types de fichiers propres au dépôt (les scripts nc-* sans extension : Neovim lit leur shebang tout seul)
  {
    "LazyVim/LazyVim",
    init = function()
      vim.filetype.add({
        extension = { qml = "qml", luau = "luau", conf = "conf" },
        filename = { ["hypridle.conf"] = "hyprlang", ["reglages.conf"] = "conf", ["raccourcis.conf"] = "conf" },
        pattern = { [".*/%.config/nc/.*%.conf"] = "conf" },
      })
    end,
  },
}

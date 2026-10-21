-- Complétion (nvim-cmp + serveurs LSP + mini.snippets).
--
-- Une fonction proposée par un serveur de langage s'insère par son nom seul. Sans ce fichier, le serveur envoie la
-- fonction en « snippet » : toute la signature est collée, chaque paramètre devient une étape à parcourir avec Tab,
-- le curseur file à la fin et mini.snippets y dessine un carré (∎) pour l'étape finale. Entrée valide la proposition
-- sélectionnée ; ensuite tu tapes la parenthèse et les arguments toi-même, comme dans un éditeur classique.
--
-- Les vrais snippets (friendly-snippets : « for », « if »…) gardent leurs étapes, mais sans marqueur visible pour les
-- étapes vides (plus de • ni de ∎) ; Tab passe à l'étape suivante, Maj + Tab revient.
return {
  {
    "neovim/nvim-lspconfig",
    opts = {
      servers = {
        ["*"] = {
          capabilities = {
            textDocument = { completion = { completionItem = { snippetSupport = false } } },
          },
        },
      },
    },
  },
  {
    -- L'extra nvim-cmp de LazyVim remet snippetSupport à vrai pour tous les serveurs quand nvim-cmp se charge
    -- (vim.lsp.config("*") avec les capacités de cmp_nvim_lsp) : repassé à faux juste après, pour les serveurs
    -- lancés ensuite
    "hrsh7th/nvim-cmp",
    optional = true,
    opts = function(_, opts)
      vim.lsp.config("*", { capabilities = { textDocument = { completion = { completionItem = { snippetSupport = false } } } } })
      return opts
    end,
  },
  {
    "nvim-mini/mini.snippets",
    optional = true,
    opts = function(_, opts)
      opts.expand = opts.expand or {}
      local inserer = opts.expand.insert
      opts.expand.insert = function(snippet, options)
        local o = vim.tbl_extend("force", { empty_tabstop = "", empty_tabstop_final = "" }, options or {})
        return (inserer or MiniSnippets.default_insert)(snippet, o)
      end
    end,
  },
}

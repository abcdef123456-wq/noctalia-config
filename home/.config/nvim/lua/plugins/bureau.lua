-- Le bureau à portée de main : un menu « Espace n » (Noctalia) pour ouvrir la config Hyprland, l'île, les scripts
-- nc-*, tes réglages, le dépôt, et lancer nc-reglages ou suivre le journal de l'île sans quitter Neovim.
-- Les fichiers du bureau gardent leur mise en forme : pas de formatage automatique à l'enregistrement dans
-- ~/.config/hypr, ~/.config/quickshell et les scripts nc-* (leur style n'est pas celui de stylua ou shfmt).
local maison = os.getenv("HOME")
local config = os.getenv("XDG_CONFIG_HOME") or (maison .. "/.config")

-- Le dépôt noctalia-config, s'il est connu (nc-maj note son chemin dans ~/.config/nc/depot)
local function depot()
  local f = io.open(config .. "/nc/depot")
  if not f then
    return nil
  end
  local chemin = (f:read("*l") or ""):gsub("%s+$", "")
  f:close()
  return chemin ~= "" and vim.fn.isdirectory(chemin) == 1 and chemin or nil
end

local function fichiers(dossier, titre)
  return function()
    Snacks.picker.files({ cwd = dossier, title = titre, hidden = true })
  end
end

local function terminal(commande)
  return function()
    Snacks.terminal(commande, { win = { position = "float", border = "rounded" } })
  end
end

return {
  {
    "folke/which-key.nvim",
    opts = { spec = { { "<leader>n", group = "Noctalia (bureau)", icon = { icon = "󰍹", color = "cyan" } } } },
  },
  {
    "folke/snacks.nvim",
    keys = {
      { "<leader>nh", fichiers(config .. "/hypr", "Hyprland (nc/*.lua)"), desc = "Config Hyprland" },
      { "<leader>ni", fichiers(config .. "/quickshell/nc-ile", "Île dynamique (QML)"), desc = "Île dynamique" },
      { "<leader>ns", fichiers(maison .. "/.local/bin", "Scripts nc-*"), desc = "Scripts nc-*" },
      { "<leader>nr", "<Cmd>edit " .. config .. "/nc/reglages.conf<CR>", desc = "Mes réglages (reglages.conf)" },
      { "<leader>np", "<Cmd>edit " .. config .. "/hypr/perso.lua<CR>", desc = "Mes règles Hyprland (perso.lua)" },
      {
        "<leader>nd",
        function()
          local d = depot()
          if d then
            Snacks.picker.files({ cwd = d, title = "Dépôt noctalia-config" })
          else
            vim.notify("Dépôt inconnu : lance nc-maj une fois, il note son chemin dans ~/.config/nc/depot", vim.log.levels.WARN)
          end
        end,
        desc = "Dépôt noctalia-config",
      },
      { "<leader>nc", terminal({ maison .. "/.local/bin/nc-reglages" }), desc = "nc-reglages" },
      { "<leader>nl", terminal({ "journalctl", "--user", "-u", "nc-ile", "-f", "-n", "80" }), desc = "Journal de l'île" },
      { "<leader>nt", terminal({ maison .. "/.local/bin/nc-theme-sync" }), desc = "Resynchroniser les couleurs" },
    },
  },
  {
    "LazyVim/LazyVim",
    init = function()
      vim.api.nvim_create_autocmd("BufReadPost", {
        group = vim.api.nvim_create_augroup("nc_bureau", { clear = true }),
        callback = function(ev)
          local chemin = vim.api.nvim_buf_get_name(ev.buf)
          if chemin:find("/%.config/hypr/", 1) or chemin:find("/%.config/quickshell/", 1) or chemin:find("/%.local/bin/nc%-", 1)
            or chemin:find("/home/%.config/hypr/", 1) or chemin:find("/home/%.config/quickshell/", 1) or chemin:find("/home/%.local/bin/nc%-", 1) then
            vim.b[ev.buf].autoformat = false
          end
        end,
      })
    end,
  },
}

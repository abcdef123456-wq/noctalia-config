-- Apparence : le thème suit le bureau. nc-theme-sync note dans ~/.config/nc/palette-ile.json si les couleurs du
-- fond d'écran sont sombres ou claires ; Neovim ouvre alors tokyonight-moon (sombre) ou tokyonight-day (clair).
-- Sans ce fichier (autre bureau, serveur) : sombre.
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
}

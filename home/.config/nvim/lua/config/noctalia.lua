-- Thème « noctalia » : tokyonight (moon si le fond est sombre, day s'il est clair) repeint avec les couleurs du fond
-- d'écran, les mêmes que celles de kitty. nc-theme-sync les écrit dans ~/.config/nc/palette-ile.json ; on passe par
-- l'option on_colors de tokyonight pour que tous les plugins gardent leurs groupes de couleurs.
-- Sans ce fichier (autre bureau, serveur SSH) ou s'il est abîmé : tokyonight-moon normal, sans erreur.
-- À chaud : un seul observateur du DOSSIER ~/.config/nc (nc-theme-sync remplace le fichier d'un bloc, donc l'inode
-- change) avec un anti-rebond de 200 ms ; aucun sondage, rien ne tourne tant que le fond ne change pas.
local M = {}

M.actif = false -- vrai tant que le thème courant est celui-ci (un :colorscheme manuel le coupe)
local palette -- dernière palette lue
local interne = false
local observateur, minuteur

local function dossier()
  return (os.getenv("XDG_CONFIG_HOME") or (os.getenv("HOME") .. "/.config")) .. "/nc"
end

local function hex_ok(v)
  return type(v) == "string" and v:match("^#%x%x%x%x%x%x$") ~= nil
end

-- La palette lue, ou nil si le fichier manque ou est abîmé (le fond et le texte doivent être de vraies couleurs)
function M.lire()
  local f = io.open(dossier() .. "/palette-ile.json")
  if not f then
    return nil
  end
  local texte = f:read("*a") or ""
  f:close()
  local ok, p = pcall(vim.json.decode, texte)
  if not ok or type(p) ~= "table" or not hex_ok(p.fond) or not hex_ok(p.texte) then
    return nil
  end
  return p
end

function M.sombre(p)
  return not (p and p.sombre == false)
end

local function rgb(c)
  return tonumber(c:sub(2, 3), 16), tonumber(c:sub(4, 5), 16), tonumber(c:sub(6, 7), 16)
end

-- t part de a, 1 - t part de b
local function melange(a, b, t)
  local ar, ag, ab = rgb(a)
  local br, bg, bb = rgb(b)
  local function m(x, y)
    return math.floor(x * t + y * (1 - t) + 0.5)
  end
  return string.format("#%02x%02x%02x", m(ar, br), m(ag, bg), m(ab, bb))
end

-- Les couleurs de tokyonight remplacées d'après la palette ; une clé absente ou invalide est remplacée par une
-- dérivée du fond et du texte, jamais d'erreur.
function M.couleurs(p)
  local fond, texte = p.fond, p.texte
  local function pris(cle, defaut)
    return hex_ok(p[cle]) and p[cle] or defaut
  end
  local sec = pris("texteSec", melange(texte, fond, 0.7))
  local carte = pris("carte", melange(texte, fond, 0.06))
  local survol = pris("carteSurvol", melange(texte, fond, 0.12))
  local accent = pris("accent", pris("bleu", texte))
  local bleu = pris("bleu", accent)
  local cyan = pris("cyan", bleu)
  local vert = pris("vert", accent)
  local rouge = pris("rouge", accent)
  local jaune = pris("jaune", accent)
  local orange = pris("orange", jaune)
  local violet = pris("violet", accent)
  local rose = pris("rose", violet)
  local gris3 = pris("gris3", melange(texte, fond, 0.2))
  local gris4 = pris("gris4", melange(texte, fond, 0.28))
  return {
    bg = fond, bg_dark = carte, bg_dark1 = melange("#000000", carte, 0.2), bg_highlight = survol,
    fg = texte, fg_dark = sec, fg_gutter = gris3,
    -- les commentaires restent lisibles : le texte secondaire un peu estompé, pas le gris5 trop proche du fond
    comment = melange(sec, fond, 0.8), dark3 = gris4, dark5 = pris("gris5", sec), terminal_black = gris4,
    blue = accent, blue1 = bleu, blue2 = cyan, blue0 = melange(accent, fond, 0.55), blue5 = melange(cyan, texte, 0.6),
    blue6 = melange(accent, texte, 0.5), blue7 = melange(accent, fond, 0.3),
    cyan = cyan, teal = melange(vert, cyan, 0.5),
    green = vert, green1 = melange(vert, cyan, 0.5), green2 = melange(vert, fond, 0.7),
    magenta = violet, magenta2 = rose, purple = rose,
    red = rouge, red1 = melange(rouge, fond, 0.75), orange = orange, yellow = jaune,
    border_highlight = accent,
    git = { add = vert, change = accent, delete = rouge },
  }
end

-- À brancher sur l'option on_colors de tokyonight ; ne fait rien si ce thème n'est pas celui choisi.
function M.on_colors(c)
  if not M.actif or not palette then
    return
  end
  local ok, nouveau = pcall(M.couleurs, palette)
  if not ok then
    return
  end
  local flottant, lateral = c.bg_float, c.bg_sidebar
  for cle, v in pairs(nouveau) do
    c[cle] = v
  end
  -- fond transparent : tokyonight a mis « NONE » aux fenêtres flottantes et aux barres latérales, on le garde
  c.bg_float = flottant == "NONE" and "NONE" or nouveau.bg_dark
  c.bg_sidebar = lateral == "NONE" and "NONE" or nouveau.bg_dark
  c.bg_popup, c.bg_statusline = nouveau.bg_dark, nouveau.bg_dark
  c.fg_sidebar, c.fg_float = nouveau.fg_dark, nouveau.fg
  -- ce que tokyonight déduit des couleurs, refait avec les nouvelles
  local ok_u, U = pcall(require, "tokyonight.util")
  if ok_u then
    U.bg, U.fg = c.bg, c.fg
    c.diff = {
      add = U.blend_bg(c.green2, 0.25), delete = U.blend_bg(c.red1, 0.25),
      change = U.blend_bg(c.blue7, 0.15), text = c.blue7,
    }
    c.black = U.blend_bg(c.bg, 0.8, "#000000")
  end
  c.git.ignore = c.dark3
  c.border = c.black
  c.bg_visual = nouveau.blue7
  c.bg_search = c.blue0
  c.error, c.todo, c.warning, c.info, c.hint = c.red1, c.blue, c.yellow, c.blue2, c.teal
  c.rainbow = { c.blue, c.yellow, c.green, c.teal, c.magenta, c.purple, c.orange, c.red }
  c.terminal = {
    black = c.black, black_bright = c.terminal_black, red = c.red, red_bright = c.red, green = c.green,
    green_bright = c.green, yellow = c.yellow, yellow_bright = c.yellow, blue = c.blue, blue_bright = c.blue,
    magenta = c.magenta, magenta_bright = c.magenta, cyan = c.cyan, cyan_bright = c.cyan, white = c.fg_dark,
    white_bright = c.fg,
  }
end

-- Applique tokyonight-moon ou -day avec les couleurs de la palette (p vaut nil : tokyonight-moon normal).
function M.appliquer(p)
  palette = p
  interne = true
  local ok = pcall(vim.cmd.colorscheme, M.sombre(p) and "tokyonight-moon" or "tokyonight-day")
  interne = false
  return ok
end

local function releve()
  if not M.actif then
    return
  end
  local p = M.lire()
  if p then -- palette abîmée entre-temps : on garde les couleurs actuelles
    M.appliquer(p)
  end
end

local function surveiller()
  if observateur then
    return
  end
  local uv = vim.uv or vim.loop
  local ok, obs = pcall(uv.new_fs_event)
  if not ok or not obs then
    return
  end
  minuteur = uv.new_timer()
  local debut = obs:start(dossier(), {}, function(err, nom)
    if err or nom ~= "palette-ile.json" then
      return
    end
    minuteur:stop()
    minuteur:start(200, 0, vim.schedule_wrap(releve))
  end)
  if debut ~= 0 then -- dossier absent : rien à surveiller
    obs:close()
    minuteur:close()
    minuteur = nil
    return
  end
  observateur = obs
  vim.api.nvim_create_autocmd("VimLeavePre", {
    once = true,
    callback = function()
      observateur:stop()
      minuteur:stop()
    end,
  })
end

-- Choisit ce thème : applique, surveille la palette, et se désactive si on change de thème à la main.
function M.activer()
  M.actif = true
  M.appliquer(M.lire())
  vim.api.nvim_create_autocmd("ColorScheme", {
    group = vim.api.nvim_create_augroup("nc_noctalia", { clear = true }),
    callback = function()
      if not interne then
        M.actif = false
      end
    end,
  })
  surveiller()
end

return M

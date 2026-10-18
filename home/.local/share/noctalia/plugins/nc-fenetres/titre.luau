--!nonstrict
-- nc/fenetres : le titre de la fenêtre active dans la barre (à la place de active_window).
--   Repos : icône et titre de la fenêtre active ; un badge s'il y a des fenêtres masquées.
--   Survol : la zone s'agrandit et montre toutes les fenêtres du bureau, puis les masquées (estompées) :
--   un clic va sur une fenêtre ou ramène une masquée ; « − » masque la fenêtre active, « ≡ » ouvre le menu de gestion.
--   Clic : menu de gestion.  Clic droit : vue de toutes les fenêtres.
-- Les fenêtres viennent de nc-fenetre etat, relu à chaque changement dans Hyprland (nc-fenetre suivre).
local c = require("./commun.luau")
local tr = c.tr

local etat = { bureau = 0, fenetres = {}, masquees = {} }
local dedans = {}          -- éléments survolés (le survol passe d'un élément à l'autre sans refermer)
local developpe = false
local fermerA = 0          -- fin du délai avant de se replier, quand le pointeur est sorti

local function lire()
  noctalia.runAsync({ c.NC, "etat" }, function(r)
    local ok, e = pcall(noctalia.json.decode, r.stdout or "")
    if ok and type(e) == "table" then
      etat = { bureau = e.bureau or 0, fenetres = e.fenetres or {}, masquees = e.masquees or {} }
      noctalia.state.set("fenetres", etat)
      rendre()
    end
  end, 3000)
end

-- La fenêtre active ; quand un panneau prend le clavier, Hyprland n'en a plus : on garde la dernière
local derniere = nil
local function active()
  for _, w in ipairs(etat.fenetres) do if w.active then derniere = w.adresse; return w end end
  for _, w in ipairs(etat.fenetres) do if w.adresse == derniere then return w end end
  return nil
end

-- Survol : se déplier tout de suite, se replier 350 ms après la sortie du pointeur
function onSurvol(etatSurvol, cle)
  dedans[cle ~= "" and cle or "fond"] = (etatSurvol == "true") or nil
  if next(dedans) then
    fermerA = 0
    if not developpe then developpe = true; rendre() end
  elseif developpe then
    fermerA = noctalia.nowMs() + 350
    noctalia.setUpdateInterval(60)
  end
end

local function puce(w, masquee, a)
  local actif = not masquee and a ~= nil and w.adresse == a.adresse
  local enfants = { c.image(w, 16, masquee and 0.45 or 1) }
  if actif then
    table.insert(enfants, ui.label({ text = c.nom(w), maxWidth = 180, maxLines = 1 }))
  end
  return ui.row({
    key = "w" .. w.adresse, gap = 6, paddingH = 7, height = 24, radius = 12, align = "center",
    fill = actif and "primary/0.22" or nil,
    tooltip = masquee and (c.nom(w) .. tr(" · masquée, clic pour la ramener", " · hidden, click to bring it back")) or c.nom(w),
    onHover = "onSurvol",
    onClick = function() c.faire("aller", w.adresse, lire) end,
  }, enfants)
end

function rendre()
  local a = active()
  local nf, nm = #etat.fenetres, #etat.masquees
  barWidget.setVisible(nf + nm > 0)
  if nf + nm == 0 then return end

  local enfants = {}
  if developpe then
    for _, w in ipairs(etat.fenetres) do table.insert(enfants, puce(w, false, a)) end
    if nm > 0 then
      if nf > 0 then table.insert(enfants, ui.separator({ orientation = "vertical", spacing = 2 })) end
      for _, w in ipairs(etat.masquees) do table.insert(enfants, puce(w, true, nil)) end
    end
    table.insert(enfants, ui.separator({ orientation = "vertical", spacing = 2 }))
    if a then
      table.insert(enfants, ui.button({ key = "masquer", glyph = "minus", variant = "ghost", glyphSize = 14,
        tooltip = tr("Masquer la fenêtre (Super + H)", "Hide the window (Super + H)"), onHover = "onSurvol",
        onClick = function() c.faire("reduire", a.adresse, lire) end }))
    end
    table.insert(enfants, ui.button({ key = "menu", glyph = "layout-list", variant = "ghost", glyphSize = 14,
      tooltip = tr("Gérer les fenêtres du bureau", "Manage the desktop's windows"), onHover = "onSurvol",
      onClick = function() noctalia.togglePanel("nc/fenetres:gestion") end }))
  else
    if a then
      table.insert(enfants, c.image(a, 16))
      table.insert(enfants, ui.label({ text = c.nom(a), maxWidth = 240, maxLines = 1 }))
    elseif nf > 0 then
      table.insert(enfants, ui.glyph({ name = "app-window", size = 15 }))
      table.insert(enfants, ui.label({ text = nf == 1 and tr("1 fenêtre", "1 window") or (nf .. tr(" fenêtres", " windows")) }))
    end
    if nm > 0 then
      table.insert(enfants, ui.row({ gap = 3, paddingH = 6, height = 20, radius = 10, align = "center", fill = "surface_variant/0.7" }, {
        ui.glyph({ name = "eye-off", size = 12, color = "on_surface_variant" }),
        ui.label({ text = tostring(nm), fontSize = 11, color = "on_surface_variant" }),
      }))
    end
  end
  barWidget.render(ui.row({ key = "fond", gap = developpe and 3 or 7, align = "center", onHover = "onSurvol" }, enfants))
end

function update()
  if fermerA > 0 and noctalia.nowMs() >= fermerA then
    fermerA = 0
    if not next(dedans) then developpe = false; rendre() end
  end
  if fermerA == 0 then noctalia.setUpdateInterval(5000); lire() end   -- filet de sécurité, si le flux s'arrête
end

function onClick() noctalia.togglePanel("nc/fenetres:gestion") end
function onRightClick() c.vue() end

-- Chaque changement de fenêtres dans Hyprland (le flux se relance tout seul s'il s'arrête)
noctalia.runStream("while :; do '" .. c.NC .. "' suivre; sleep 2; done", function() lire() end)
noctalia.setUpdateInterval(5000)
lire()

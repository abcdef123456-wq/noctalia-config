--!nonstrict
-- nc/fenetres : le menu de gestion, sous le titre de la barre. Les fenêtres du bureau affiché, puis les masquées ;
-- pour chacune : y aller (clic), la masquer ou la ramener, la fermer. En bas : tout masquer, tout ramener, la vue.
-- Lignes plus grandes quand il y a peu de fenêtres, plus serrées quand il y en a beaucoup.
local c = require("./commun.luau")
local tr = c.tr

local etat = { bureau = 0, fenetres = {}, masquees = {} }
local ouvert = false

-- L'écran où le menu s'ouvre : son bureau et ses fenêtres, et toutes les masquées
local function prendre(e)
  if type(e) ~= "table" then return end
  local m = (e.moniteurs or {})[noctalia.focusedOutputName() or ""] or e
  etat = { bureau = m.bureau or 0, fenetres = m.fenetres or {}, masquees = e.masquees or {} }
end

-- Sans titre dans la barre (pas d'état publié) : lu une fois
local function lire()
  noctalia.runAsync({ c.NC, "etat" }, function(r)
    local ok, e = pcall(noctalia.json.decode, r.stdout or "")
    if ok then prendre(e); render() end
  end, 3000)
end

local function compte(n, un, plusieurs)
  return n == 1 and un or (n .. " " .. plusieurs)
end

local function ligne(w, masquee, grand)
  local taille = grand and 30 or 22
  local actif = w.active and not masquee
  local sous = (w.classe ~= "" and w.classe ~= c.nom(w)) and w.classe or nil
  local texte = { ui.label({ text = c.nom(w), maxLines = 1, fontWeight = actif and "semibold" or "normal",
    color = masquee and "on_surface_variant" or "on_surface" }) }
  if grand and sous then
    table.insert(texte, ui.label({ text = sous, maxLines = 1, fontSize = 11, color = "on_surface_variant" }))
  end
  return ui.row({
    key = (masquee and "m" or "f") .. w.adresse, gap = 12, paddingH = 10, height = grand and 54 or 40, radius = 12,
    align = "center", fill = actif and "primary/0.16" or "surface_variant/0.35",
    tooltip = masquee and tr("Ramener sur le bureau", "Bring back to the desktop") or tr("Aller sur la fenêtre", "Go to the window"),
    onClick = function() c.faire("aller", w.adresse); panel.close() end,
  }, {
    c.image(w, taille, masquee and 0.5 or 1),
    ui.column({ flexGrow = 1, gap = 1 }, texte),
    ui.button({ glyph = masquee and "eye" or "eye-off", variant = "ghost", controlSize = "sm",
      tooltip = masquee and tr("Afficher", "Show") or tr("Masquer", "Hide"),
      onClick = function() c.faire("basculer", w.adresse) end }),
    ui.button({ glyph = "x", variant = "ghost", controlSize = "sm", tooltip = tr("Fermer", "Close"),
      onClick = function() c.faire("fermer", w.adresse) end }),
  })
end

local function section(titre, n)
  return ui.row({ paddingH = 4, align = "center", gap = 6 }, {
    ui.label({ text = titre, fontSize = 12, fontWeight = "semibold", color = "on_surface_variant" }),
    ui.label({ text = tostring(n), fontSize = 12, color = "on_surface_variant/0.7" }),
  })
end

function render()
  if not ouvert then return end
  local nf, nm = #etat.fenetres, #etat.masquees
  local grand = nf + nm <= 5
  local corps
  if nf + nm == 0 then
    corps = ui.column({ flexGrow = 1, align = "center", justify = "center", gap = 10 }, {
      ui.glyph({ name = "app-window", size = 40, color = "on_surface_variant/0.6" }),
      ui.label({ text = tr("Aucune fenêtre sur ce bureau", "No windows on this desktop"), color = "on_surface_variant" }),
    })
  else
    local liste = {}
    if nf > 0 then
      table.insert(liste, section(tr("Sur ce bureau", "On this desktop"), nf))
      for _, w in ipairs(etat.fenetres) do table.insert(liste, ligne(w, false, grand)) end
    end
    if nm > 0 then
      table.insert(liste, section(tr("Masquées", "Hidden"), nm))
      for _, w in ipairs(etat.masquees) do table.insert(liste, ligne(w, true, grand)) end
    end
    corps = ui.scroll({ flexGrow = 1, gap = grand and 8 or 5 }, liste)
  end
  panel.render(ui.column({ flexGrow = 1, padding = 16, gap = 12 }, {
    ui.row({ align = "center", gap = 8 }, {
      ui.glyph({ name = "app-window", size = 18, color = "primary" }),
      ui.label({ text = tr("Fenêtres", "Windows"), fontSize = 16, fontWeight = "bold" }),
      ui.spacer({ flexGrow = 1 }),
      ui.label({ text = tr("Bureau ", "Desktop ") .. etat.bureau .. " · "
        .. compte(nf, tr("1 fenêtre", "1 window"), tr("fenêtres", "windows")), color = "on_surface_variant", fontSize = 12 }),
    }),
    corps,
    ui.row({ gap = 8 }, {
      ui.button({ text = tr("Tout masquer", "Hide All"), glyph = "eye-off", variant = "secondary", controlSize = "sm",
        flexGrow = 1, enabled = nf > 0, onClick = function() c.faire("tout-masquer") end }),
      ui.button({ text = tr("Tout afficher", "Show All"), glyph = "eye", variant = "secondary", controlSize = "sm",
        flexGrow = 1, enabled = nm > 0, onClick = function() c.faire("tout-afficher") end }),
      ui.button({ glyph = "layout-grid", variant = "ghost", controlSize = "sm",
        tooltip = tr("Vue de toutes les fenêtres (Super + A)", "All windows overview (Super + A)"),
        onClick = function() panel.close(); c.vue() end }),
    }),
  }))
end

function onOpen()
  ouvert = true
  local e = noctalia.state.get and noctalia.state.get("fenetres")
  if type(e) == "table" then prendre(e); render() else lire() end
end

function onClose() ouvert = false end

-- Le titre de la barre publie chaque changement : le menu ouvert suit
noctalia.state.watch("fenetres", function(e)
  prendre(e)
  render()
end)

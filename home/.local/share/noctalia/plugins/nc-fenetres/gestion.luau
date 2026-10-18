--!nonstrict
-- nc/fenetres : le menu de gestion, sous le titre de la barre. Les fenêtres du bureau affiché, puis les masquées ;
-- pour chacune : y aller (clic), la masquer ou la ramener, la fermer ; en haut : tout masquer, tout afficher.
-- Seulement sans l'île Quickshell (sinon le titre de la barre ouvre sa page « Fenêtres ») ; même allure que l'île.
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

-- Bouton rond, comme dans l'île
local function rond(glyphe, action, danger)
  return ui.column({ width = 30, height = 30, radius = 15, fill = "surface_variant", align = "center", justify = "center",
    onClick = action }, { ui.glyph({ name = glyphe, size = 15, color = danger and "error" or "on_surface" }) })
end

-- Lien texte de l'en-tête (« Tout masquer »), comme « Effacer » dans l'île
local function lien(texte, action)
  return ui.row({ paddingH = 4, height = 26, align = "center", onClick = action }, {
    ui.label({ text = texte, fontSize = 13, color = "primary" }),
  })
end

local function ligne(w, masquee, grand)
  local actif = w.active and not masquee
  local texte = { ui.label({ text = c.nom(w), maxLines = 1, fontSize = 14, fontWeight = actif and "semibold" or "normal",
    color = masquee and "on_surface_variant" or "on_surface" }) }
  if grand and w.classe ~= "" then
    table.insert(texte, ui.label({ text = w.classe, maxLines = 1, fontSize = 12, color = "on_surface_variant" }))
  end
  return ui.row({
    key = (masquee and "m" or "f") .. w.adresse, gap = 12, paddingH = 12, height = grand and 58 or 46, radius = 14,
    align = "center", fill = "surface_variant/0.45", border = actif and "primary" or "#00000000", borderWidth = actif and 1.5 or 0,
    onClick = function() c.faire("aller", w.adresse); panel.close() end,
  }, {
    c.image(w, grand and 32 or 24, masquee and 0.45 or 1),
    ui.column({ flexGrow = 1, gap = 1 }, texte),
    rond(masquee and "eye" or "eye-off", function() c.faire("basculer", w.adresse) end),
    rond("x", function() c.faire("fermer", w.adresse) end, true),
  })
end

local function section(titre, n)
  return ui.label({ text = titre .. "  ·  " .. n, fontSize = 12, fontWeight = "semibold", color = "on_surface_variant" })
end

function render()
  if not ouvert then return end
  local nf, nm = #etat.fenetres, #etat.masquees
  local grand = nf + nm <= 5
  local corps
  if nf + nm == 0 then
    corps = ui.column({ flexGrow = 1, align = "center", justify = "center", gap = 8 }, {
      ui.glyph({ name = "app-window", size = 30, color = "on_surface_variant/0.6" }),
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
    corps = ui.scroll({ flexGrow = 1, gap = 6 }, liste)
  end
  local liens = {}
  if nf > 0 then table.insert(liens, lien(tr("Tout masquer", "Hide All"), function() c.faire("tout-masquer") end)) end
  if nm > 0 then table.insert(liens, lien(tr("Tout afficher", "Show All"), function() c.faire("tout-afficher") end)) end
  panel.render(ui.column({ flexGrow = 1, padding = 18, gap = 10 }, {
    ui.row({ align = "center", gap = 8, height = 34 }, {
      ui.label({ text = tr("Fenêtres", "Windows"), fontSize = 20, fontWeight = "bold" }),
      ui.label({ text = tr("Bureau ", "Desktop ") .. etat.bureau, color = "on_surface_variant" }),
      ui.spacer({ flexGrow = 1 }),
      ui.row({ gap = 10, align = "center" }, liens),
    }),
    corps,
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

--!nonstrict
-- nc/fenetres : le titre de la fenêtre active dans la barre (à la place de active_window).
--   Repos : icône et titre de la fenêtre active de cet écran ; un badge s'il y a des fenêtres masquées.
--   Survol : la zone s'agrandit et montre les icônes des fenêtres du bureau, puis des masquées (estompées), et le nom
--   de celle sous la souris ; un clic va sur une fenêtre ou ramène une masquée ; « − » masque la fenêtre active,
--   « ≡ » ouvre le menu des fenêtres.
--   Clic : menu des fenêtres (page « Fenêtres » de l'île Quickshell, sinon le panneau nc/fenetres:gestion).  Clic droit : vue de toutes les fenêtres.  Molette : fenêtre suivante / précédente du bureau.
-- L'état vient de nc-fenetre suivre : une ligne de JSON à chaque changement dans Hyprland, rien entre-temps.
local c = require("./commun.luau")
local tr = c.tr

local etat = nil           -- dernier état complet (tous les écrans)
local vue = { bureau = 0, fenetres = {}, masquees = {} }   -- ce que montre la barre de cet écran
local derniere = nil       -- dernière fenêtre active de cet écran (un panneau ouvert prend le clavier à Hyprland)
local dedans = {}          -- éléments survolés (le survol passe d'un élément à l'autre sans refermer)
local developpe = false
local fermerA = 0          -- fin du délai avant de se replier, quand le pointeur est sorti
local survolee = nil       -- fenêtre sous la souris (son nom s'affiche à la place de celui de l'active)
local oublierA = 0         -- entre deux icônes, le nom affiché reste un instant (pas de clignotement)
local NOM = 200            -- largeur fixe du nom une fois dépliée : la zone ne change pas de taille d'une icône à l'autre
local CAR = 7.4            -- largeur moyenne d'un caractère dans la barre, pour estimer la largeur repliée
local signature = ""       -- pour ne redessiner que si ce qui est montré a changé

local function choisir()
  if not etat then return end
  local m = (etat.moniteurs or {})[barWidget.outputName() or ""] or { bureau = etat.bureau, fenetres = etat.fenetres }
  vue = { bureau = m.bureau or 0, fenetres = m.fenetres or {}, masquees = etat.masquees or {} }
end

local function recevoir(ligne)
  local ok, e = pcall(noctalia.json.decode, ligne or "")
  if not ok or type(e) ~= "table" or not e.moniteurs then return end
  etat = e
  noctalia.state.set("fenetres", e)
  choisir()
  rendre()
end

local function active()
  for _, w in ipairs(vue.fenetres) do if w.active then derniere = w.adresse; return w end end
  for _, w in ipairs(vue.fenetres) do if w.adresse == derniere then return w end end
  return nil
end

-- Survol : se déplier tout de suite, se replier 350 ms après la sortie du pointeur
function onSurvol(etatSurvol, cle)
  dedans[cle ~= "" and cle or "fond"] = (etatSurvol == "true") or nil
  local avant = survolee
  if string.sub(cle, 1, 1) == "w" then
    if etatSurvol == "true" then
      survolee, oublierA = string.sub(cle, 2), 0
    elseif survolee == string.sub(cle, 2) then
      oublierA = noctalia.nowMs() + 250
      noctalia.setUpdateInterval(60)
    end
  end
  if survolee ~= avant and developpe then rendre() end
  if next(dedans) then
    fermerA = 0
    if not developpe then developpe = true; rendre() end
  elseif developpe then
    fermerA = noctalia.nowMs() + 350
    noctalia.setUpdateInterval(60)
  end
end

-- Le menu des fenêtres : la page de l'île si elle tourne (même allure que le reste), sinon le panneau de Noctalia
local function menu()
  noctalia.runAsync({ "qs", "-c", "nc-ile", "ipc", "call", "ile", "page", "fenetres" }, function(r)
    if r.exitCode ~= 0 then noctalia.togglePanel("nc/fenetres:gestion") end
  end, 3000)
end

-- Une fenêtre : son icône seule ; fond teinté pour l'active, plus léger pour celle sous la souris
local function puce(w, masquee, a)
  local actif = not masquee and a ~= nil and w.adresse == a.adresse
  return ui.row({
    key = "w" .. w.adresse, paddingH = 6, height = 24, radius = 12, align = "center",
    -- Toujours une couleur (transparente au besoin) : un fond retiré (nil) garderait l'ancien au rendu suivant
    fill = actif and "primary/0.25" or (survolee == w.adresse and "on_surface/0.12" or "#00000000"),
    onHover = "onSurvol",
    onClick = function() c.faire("aller", w.adresse) end,
  }, { c.image(w, 16, masquee and 0.45 or 1) })
end

local function trouver(adresse)
  for _, w in ipairs(vue.fenetres) do if w.adresse == adresse then return w, false end end
  for _, w in ipairs(vue.masquees) do if w.adresse == adresse then return w, true end end
  return nil, false
end

function rendre()
  local a = active()
  local nf, nm = #vue.fenetres, #vue.masquees
  -- Signature de ce qui est montré : rien à refaire si seul un autre écran a changé
  local sig = tostring(developpe) .. (a and (a.adresse .. a.titre) or "") .. "|" .. nm .. "|" .. (survolee or "")
  if developpe then
    for _, w in ipairs(vue.fenetres) do sig ..= w.adresse .. w.classe end
    for _, w in ipairs(vue.masquees) do sig ..= w.adresse .. w.titre end
  else
    sig ..= nf
  end
  if sig == signature then return end
  signature = sig

  barWidget.setVisible(nf + nm > 0)
  if nf + nm == 0 then return end
  local enfants = {}
  if developpe then
    for _, w in ipairs(vue.fenetres) do table.insert(enfants, puce(w, false, a)) end
    if nm > 0 then
      if nf > 0 then table.insert(enfants, ui.separator({ orientation = "vertical", spacing = 2 })) end
      for _, w in ipairs(vue.masquees) do table.insert(enfants, puce(w, true, nil)) end
    end
    -- Le nom de la fenêtre sous la souris, sinon celui de l'active
    local w, masquee = trouver(survolee or "")
    w = w or a
    if w then
      table.insert(enfants, ui.label({ text = c.nom(w) .. (masquee and tr(" · masquée", " · hidden") or ""), width = NOM, maxWidth = NOM, maxLines = 1,
        color = masquee and "on_surface_variant" or nil }))
    end
    if a then
      table.insert(enfants, ui.button({ key = "masquer", glyph = "minus", variant = "ghost", glyphSize = 14,
        onHover = "onSurvol",
        onClick = function() c.faire("reduire", a.adresse) end }))
    end
    table.insert(enfants, ui.button({ key = "menu", glyph = "layout-list", variant = "ghost", glyphSize = 14,
      onHover = "onSurvol",
      onClick = menu }))
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
  -- Dépliée, jamais plus étroite que repliée : sinon, la souris près du bord en sortirait, la zone se replierait sous
  -- elle, s'y retrouverait et se déplierait encore (va-et-vient)
  local repliee = (a and (16 + 7 + math.min(240, ((utf8 and utf8.len(c.nom(a))) or #c.nom(a)) * CAR)) or 110) + (nm > 0 and 44 or 0) + 12
  barWidget.render(ui.row({ key = "fond", gap = developpe and 4 or 7, align = "center", onHover = "onSurvol",
    minWidth = developpe and math.floor(repliee) or nil }, enfants))
end

-- Seulement pour se replier après le survol : le reste arrive par le flux
function update()
  if oublierA > 0 and noctalia.nowMs() >= oublierA then
    oublierA = 0
    survolee = nil
    if developpe then rendre() end
    if fermerA == 0 then noctalia.setUpdateInterval(60000) end
  end
  if fermerA > 0 and noctalia.nowMs() >= fermerA then
    fermerA = 0
    noctalia.setUpdateInterval(60000)
    if not next(dedans) then developpe = false; survolee = nil; rendre() end
  end
end

function onClick() menu() end
function onRightClick() c.vue() end

-- Molette : fenêtre suivante ou précédente du bureau, dans l'ordre de la barre
function onScroll(axe, pas)
  local n = #vue.fenetres
  if n < 2 then return end
  local i = 1
  local a = active()
  for k, w in ipairs(vue.fenetres) do if a and w.adresse == a.adresse then i = k end end
  i = ((i - 1 + (pas < 0 and -1 or 1)) % n) + 1
  c.faire("aller", vue.fenetres[i].adresse)
end

-- Le flux se relance tout seul s'il s'arrête (Hyprland redémarré…)
-- Le chemin est entre apostrophes (celles qu'il contient sont protégées) : un dossier personnel avec espace ou apostrophe marche
local cheminSur = "'" .. string.gsub(c.NC, "'", "'\\''") .. "'"
noctalia.runStream("while :; do " .. cheminSur .. " suivre; sleep 2; done", recevoir)
noctalia.setUpdateInterval(60000)

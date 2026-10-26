-- L'IA du bureau dans Neovim (nc-ia : celle choisie dans nc-reglages → Intelligence artificielle, ou aucune).
-- Menu « Espace i » (lua/config/keymaps.lua) : demander (ii), expliquer (ie), transformer (it), corriger (ic),
-- faire une tâche (if), expliquer et corriger le diagnostic de la ligne (id), écrire le message de commit (im),
-- et les agents sur le projet : le panneau sidekick.nvim avec la CLI agentique de l'IA choisie (ia ouvre ou masque,
-- iA choisit, is envoie le code ou la sélection, ip un prompt, iF le fichier, Ctrl+. y va), ou, sans sidekick, un
-- terminal en bas. iw va sur le terminal d'un agent suivi par nc-claude (voir lua/config/agents.lua).
-- IA coupée (IA_MODE=non dans reglages.conf, relu à chaque appui) : toutes ces touches le disent et n'ouvrent rien.
-- « Espace a » reste à Claude Code en IDE (claudecode.nvim : diffs à accepter dans Neovim).
-- Le texte passe par l'entrée standard de nc-ia ; rien ne bloque l'éditeur pendant la réponse.
-- Rien ici ne suppose une IA en particulier : tout passe par nc-ia, donc par l'IA choisie.
-- Neovim 0.11.2 au moins (le minimum de LazyVim ; Debian 13 a la 0.10.4, install.sh propose la version officielle) : vim.system, vim.fs.root, titres et pieds des fenêtres flottantes.
local M = {}
local nc_ia = os.getenv("HOME") .. "/.local/bin/nc-ia"
local HISTORIQUE = vim.fn.stdpath("state") .. "/nc-ia-demandes.json"
local MAX_HISTORIQUE = 20
local compteur = 0

-- IA coupée ? IA_MODE=non dans reglages.conf, relu à chaque appel (un petit fichier : bon marché, pas de sondage)
function M.coupee()
  local f = io.open((os.getenv("XDG_CONFIG_HOME") or (os.getenv("HOME") .. "/.config")) .. "/nc/reglages.conf")
  if not f then
    return false
  end
  local mode
  for ligne in f:lines() do
    local v = ligne:match("^%s*IA_MODE%s*=%s*(.-)%s*$")
    if v then
      mode = v:gsub('^"(.*)"$', "%1")
    end
  end
  f:close()
  return mode == "non"
end

-- À mettre en tête d'une action d'IA : vrai (et le dit) si l'IA est coupée, l'action s'arrête là
function M.refuse()
  if M.coupee() then
    vim.notify("IA désactivée (nc-reglages → Intelligence artificielle)", vim.log.levels.WARN, { title = "IA" })
    return true
  end
  return false
end

-- Les lignes de la dernière sélection (après Échap, les marques '< et '> sont posées)
local function lignes_choisies()
  local debut, fin = vim.fn.line("'<"), vim.fn.line("'>")
  if debut == 0 or fin == 0 then
    return nil
  end
  return debut, fin, vim.api.nvim_buf_get_lines(0, debut - 1, fin, false)
end

local function type_fichier(buf)
  local ft = vim.bo[buf or 0].filetype
  return ft ~= "" and ft or "texte brut"
end

local function lancer(args, texte, fini)
  if vim.fn.executable(nc_ia) ~= 1 then
    vim.notify("nc-ia est introuvable (~/.local/bin/nc-ia).", vim.log.levels.ERROR)
    return
  end
  vim.notify("L'IA réfléchit…", vim.log.levels.INFO, { title = "IA" })
  vim.system(vim.list_extend({ nc_ia }, args), { stdin = texte or "", text = true }, function(r)
    vim.schedule(function()
      local sortie = (r.stdout or ""):gsub("%s+$", "")
      -- Un échec (code non nul) ne touche à rien : on montre le message de nc-ia, tel quel
      if r.code ~= 0 or sortie == "" then
        local erreur = (r.stderr or ""):gsub("%s+$", "")
        if erreur == "" then
          erreur = r.code ~= 0 and sortie or ""
        end
        vim.notify(erreur ~= "" and erreur or "L'IA n'a rien répondu.", vim.log.levels.WARN, { title = "IA" })
        return
      end
      fini(sortie)
    end)
  end)
end

-- Du balisage d'appel d'outil au lieu d'un texte : jamais écrit dans le fichier (nc-ia le filtre déjà ; ceinture)
local function balisage_outil(t)
  for _, motif in ipairs({ "<function_calls", "<invoke", "<parameter name=", "<tool_call", "<tool_use", '"tool_use"' }) do
    if t:find(motif, 1, true) then
      return true
    end
  end
  return false
end

-- Retire les clôtures de code Markdown. tout = false : seulement si la réponse entière est un bloc ```…```.
-- tout = true : si la réponse mêle du texte et des blocs, on ne garde que le contenu des blocs.
local function sans_clotures(t, tout)
  local l = vim.split(t, "\n")
  while #l > 0 and l[1]:match("^%s*$") do
    table.remove(l, 1)
  end
  while #l > 0 and l[#l]:match("^%s*$") do
    table.remove(l)
  end
  local function cloture(s)
    return s and s:match("^%s*```") ~= nil
  end
  if #l >= 2 and cloture(l[1]) and l[#l]:match("^%s*```%s*$") then
    local dedans = vim.list_slice(l, 2, #l - 1)
    local ailleurs = false
    for _, s in ipairs(dedans) do
      ailleurs = ailleurs or cloture(s)
    end
    if not ailleurs then
      return table.concat(dedans, "\n")
    end
  end
  if tout then
    local blocs, dans = {}, false
    for _, s in ipairs(l) do
      if cloture(s) then
        dans = not dans
      elseif dans then
        table.insert(blocs, s)
      end
    end
    if #blocs > 0 then
      return table.concat(blocs, "\n")
    end
  end
  return table.concat(l, "\n")
end

local function copier(texte)
  vim.fn.setreg('"', texte)
  pcall(vim.fn.setreg, "+", texte)
  vim.notify("Copié dans le presse-papiers.", vim.log.levels.INFO, { title = "IA" })
end

-- Une fenêtre flottante en verre, au centre : bordure arrondie, titre, ligne d'aide en bas, hauteur qui suit le
-- texte (entre `hauteur` et 80 % de l'écran). Rend le buffer, la fenêtre et la fonction qui réajuste la hauteur.
local function flottante(o)
  local buf = vim.api.nvim_create_buf(false, true)
  vim.bo[buf].bufhidden = "wipe"
  vim.api.nvim_buf_set_lines(buf, 0, -1, false, o.lignes or { "" })
  local largeur = math.max(20, math.floor(vim.o.columns * 0.7))
  local mini = math.max(1, math.min(o.hauteur or 1, vim.o.lines - 4))
  local maxi = math.max(mini, math.floor(vim.o.lines * 0.8))
  local function place(h)
    return { row = math.max(0, math.floor((vim.o.lines - h) / 2) - 1), col = math.floor((vim.o.columns - largeur) / 2) }
  end
  local p = place(mini)
  local win = vim.api.nvim_open_win(buf, true, {
    relative = "editor", width = largeur, height = mini, row = p.row, col = p.col, style = "minimal",
    border = "rounded", title = " " .. o.titre .. " ", title_pos = "center",
    footer = o.aide and (" " .. o.aide .. " ") or nil, footer_pos = o.aide and "center" or nil,
  })
  vim.wo[win].wrap = true
  vim.wo[win].linebreak = true
  vim.wo[win].winblend = 10
  vim.wo[win].winhighlight = "Normal:NormalFloat,FloatBorder:FloatBorder,FloatTitle:FloatTitle,FloatFooter:FloatFooter"
  if o.ft then
    vim.bo[buf].filetype = o.ft
  end
  local function ajuster()
    if not vim.api.nvim_win_is_valid(win) then
      return
    end
    local h = vim.api.nvim_win_text_height(win, {}).all
    h = math.max(mini, math.min(maxi, h))
    if h ~= vim.api.nvim_win_get_height(win) then
      local q = place(h)
      vim.api.nvim_win_set_config(win, { relative = "editor", height = h, row = q.row, col = q.col })
    end
  end
  ajuster()
  return buf, win, ajuster
end

local function fermer(win, origine)
  if win and vim.api.nvim_win_is_valid(win) then
    vim.api.nvim_win_close(win, true)
  end
  if origine and vim.api.nvim_win_is_valid(origine) then
    vim.api.nvim_set_current_win(origine)
  end
end

-- Historique des demandes (les 20 dernières, la plus récente en premier)
local function lire_historique()
  local ok, f = pcall(io.open, HISTORIQUE, "r")
  if not ok or not f then
    return {}
  end
  local contenu = f:read("*a")
  f:close()
  local bon, h = pcall(vim.json.decode, contenu)
  return bon and type(h) == "table" and h or {}
end

local function retenir(texte)
  local h = { texte }
  for _, t in ipairs(lire_historique()) do
    if t ~= texte and type(t) == "string" and #h < MAX_HISTORIQUE then
      table.insert(h, t)
    end
  end
  vim.fn.mkdir(vim.fn.fnamemodify(HISTORIQUE, ":h"), "p")
  local f = io.open(HISTORIQUE, "w")
  if f then
    f:write(vim.json.encode(h))
    f:close()
  end
end

-- La saisie : tout le texte se voit, on édite comme dans vim, on colle (p, P, <C-r>", <C-r>+).
-- Ctrl + S (ou :w) envoie, q ou Échap (mode normal) annule, Ctrl + P / Ctrl + N rappellent les demandes d'avant.
-- fini(texte) n'est appelé qu'à l'envoi d'un texte non vide, une fois la fenêtre fermée.
function M.saisir(titre, fini)
  local origine = vim.api.nvim_get_current_win()
  local buf, win, ajuster = flottante({ titre = titre, ft = "markdown", hauteur = math.floor(vim.o.lines * 0.3),
    aide = "Ctrl+S envoyer · q annuler · Ctrl+P/N historique" })
  compteur = compteur + 1
  vim.bo[buf].buftype = "acwrite"
  vim.api.nvim_buf_set_name(buf, "nc-ia://demande-" .. compteur)
  -- Pas de menu de complétion par-dessus le texte (nvim-cmp, ou blink.cmp de LazyVim)
  vim.b[buf].completion = false
  if package.loaded.cmp then
    pcall(function() require("cmp").setup.buffer({ enabled = false }) end)
  end
  local fait = false

  local function finir(envoyer)
    if fait then
      return
    end
    fait = true
    local texte = vim.trim(table.concat(vim.api.nvim_buf_get_lines(buf, 0, -1, false), "\n"))
    vim.bo[buf].modified = false
    vim.cmd.stopinsert()
    vim.schedule(function()
      fermer(win, origine)
      if envoyer and texte ~= "" then
        retenir(texte)
        fini(texte)
      end
    end)
  end

  local historique, pos, brouillon = lire_historique(), 0, nil
  local function rappeler(pas)
    local n = pos + pas
    if n < 0 or n > #historique then
      return
    end
    if pos == 0 then
      brouillon = vim.api.nvim_buf_get_lines(buf, 0, -1, false)
    end
    pos = n
    local l = pos == 0 and brouillon or vim.split(historique[pos], "\n")
    vim.api.nvim_buf_set_lines(buf, 0, -1, false, l)
    vim.api.nvim_win_set_cursor(win, { #l, #l[#l] })
    ajuster()
  end

  local function touche(modes, lhs, f)
    vim.keymap.set(modes, lhs, f, { buffer = buf, nowait = true })
  end
  touche({ "n", "i" }, "<C-s>", function() finir(true) end)
  touche("n", "q", function() finir(false) end)
  touche("n", "<Esc>", function() finir(false) end)
  touche({ "n", "i" }, "<C-p>", function() rappeler(1) end)
  touche({ "n", "i" }, "<C-n>", function() rappeler(-1) end)
  vim.api.nvim_create_autocmd("BufWriteCmd", { buffer = buf, callback = function() finir(true) end })
  vim.api.nvim_create_autocmd({ "TextChanged", "TextChangedI" }, { buffer = buf, callback = ajuster })
  vim.api.nvim_create_autocmd("WinClosed", { pattern = tostring(win), once = true, callback = function()
    fait = true -- fermée autrement (:q, Ctrl+W c) : annulée
  end })
  vim.cmd.startinsert()
  return buf, win
end

-- Une réponse dans une fenêtre flottante : y copie tout, i l'insère au curseur de la fenêtre d'origine,
-- q ou Échap ferme. touches : d'autres touches propres à l'appelant ({ lhs = fonction(texte, fermer) }).
local function montrer(texte, o)
  o = o or {}
  local origine = o.origine or vim.api.nvim_get_current_win()
  local buf, win = flottante({ titre = o.titre or "Réponse de l'IA", ft = o.ft or "markdown",
    lignes = vim.split(texte, "\n"), hauteur = 3, aide = o.aide or "y copier · i insérer · q fermer" })
  vim.bo[buf].modifiable = false
  local function ferme()
    fermer(win, origine)
  end
  local touches = o.touches or {
    i = function(t, f)
      f()
      if vim.api.nvim_win_is_valid(origine) then
        vim.api.nvim_put(vim.split(t, "\n"), "l", true, true)
      end
    end,
  }
  touches.y = touches.y or function(t) copier(t) end
  for lhs, f in pairs(touches) do
    vim.keymap.set("n", lhs, function() f(texte, ferme) end, { buffer = buf, nowait = true })
  end
  for _, lhs in ipairs({ "q", "<Esc>" }) do
    vim.keymap.set("n", lhs, ferme, { buffer = buf, nowait = true })
  end
  return buf, win
end
M.montrer = montrer

-- Une question ; en visuel, les lignes choisies l'accompagnent
function M.demander(visuel)
  if M.refuse() then
    return
  end
  local contexte = ""
  if visuel then
    local _, _, l = lignes_choisies()
    contexte = l and table.concat(l, "\n") or ""
  end
  local ft = type_fichier()
  local origine = vim.api.nvim_get_current_win()
  M.saisir("Demande à l'IA", function(q)
    local fini = function(s) montrer(s, { origine = origine }) end
    if contexte ~= "" then
      lancer({ "texte", q, "--stdin" }, "(" .. ft .. ")\n" .. contexte, fini)
    else
      lancer({ "demander", "-" }, q, fini)
    end
  end)
end

function M.expliquer()
  if M.refuse() then
    return
  end
  local _, _, l = lignes_choisies()
  if l then
    lancer({ "texte", "expliquer", "--stdin" }, table.concat(l, "\n"), montrer)
  end
end

-- Les lignes choisies remplacées par le résultat (annulable avec u). Rien n'est touché si nc-ia échoue, si la
-- réponse ressemble à un appel d'outil, ou si le fichier a changé entre-temps : le résultat est alors seulement montré.
local function remplacer(action, debut, fin, l)
  if not l then
    debut, fin, l = lignes_choisies()
  end
  if not l then
    return
  end
  local buf = vim.api.nvim_get_current_buf()
  local tick = vim.b[buf].changedtick
  lancer({ "texte", action, "--stdin" }, table.concat(l, "\n"), function(sortie)
    if not vim.api.nvim_buf_is_valid(buf) then
      return
    end
    if balisage_outil(sortie) then
      vim.notify("L'IA a répondu par un appel d'outil : la sélection n'est pas touchée.", vim.log.levels.WARN,
        { title = "IA" })
      return
    end
    sortie = sans_clotures(sortie, false)
    if vim.b[buf].changedtick ~= tick then
      vim.notify("Le fichier a changé pendant la réponse : rien n'est remplacé.", vim.log.levels.WARN, { title = "IA" })
      return montrer(sortie, { ft = vim.bo[buf].filetype })
    end
    vim.api.nvim_buf_set_lines(buf, debut - 1, fin, false, vim.split(sortie, "\n"))
  end)
end

function M.transformer()
  if M.refuse() then
    return
  end
  local debut, fin, l = lignes_choisies()
  if not l then
    return
  end
  M.saisir("Consigne pour la sélection", function(c)
    remplacer(c, debut, fin, l)
  end)
end

function M.corriger()
  if M.refuse() then
    return
  end
  remplacer("corriger")
end

-- Faire la tâche : la sélection (ou ce qu'on tape) est l'énoncé ; le fichier courant (300 lignes au plus autour
-- du curseur) sert de contexte. Le code écrit ne remplace jamais rien d'office : il s'ouvre dans un aperçu
-- (a l'ajouter dessous, r remplacer la sélection, y copier, q fermer).
local function faire(enonce, debut, fin)
  local buf, origine = vim.api.nvim_get_current_buf(), vim.api.nvim_get_current_win()
  local ft = type_fichier(buf)
  local n, c = vim.api.nvim_buf_line_count(buf), vim.api.nvim_win_get_cursor(origine)[1]
  local a = math.max(1, c - 150)
  local b = math.min(n, a + 299)
  a = math.max(1, b - 299)
  local contexte = table.concat(vim.api.nvim_buf_get_lines(buf, a - 1, b, false), "\n")
  local nom = vim.fn.expand("%:t")
  local entree = "Tâche :\n" .. enonce .. "\n\nFichier « " .. (nom ~= "" and nom or "sans nom") .. " » (" .. ft
    .. "), lignes " .. a .. " à " .. b .. ", pour le contexte (ne le recopie pas) :\n" .. contexte
  local ligne = fin or c -- l'ajout va sous la sélection, sinon sous le curseur
  lancer({ "texte", "Écris le code demandé, en " .. ft .. ", uniquement le code, sans explication.", "--stdin" }, entree,
    function(sortie)
      if balisage_outil(sortie) then
        vim.notify("L'IA a répondu par un appel d'outil, pas par du code. Pour une tâche sur le projet : l'agent (Espace i a).",
          vim.log.levels.WARN, { title = "IA" })
        return
      end
      local code = sans_clotures(sortie, true)
      local function lignes()
        return vim.split(code, "\n")
      end
      montrer(code, {
        origine = origine, ft = vim.bo[buf].filetype, titre = "Résultat de la tâche",
        aide = (debut and "a ajouter dessous · r remplacer la sélection" or "a ajouter dessous") .. " · y copier · q fermer",
        touches = {
          a = function(_, ferme)
            ferme()
            if vim.api.nvim_buf_is_valid(buf) then
              vim.api.nvim_buf_set_lines(buf, ligne, ligne, false, lignes())
            end
          end,
          r = function()
            if not debut then
              return vim.notify("Pas de sélection à remplacer : a pour ajouter.", vim.log.levels.INFO, { title = "IA" })
            end
            fermer(vim.api.nvim_get_current_win(), origine)
            if vim.api.nvim_buf_is_valid(buf) then
              vim.api.nvim_buf_set_lines(buf, debut - 1, fin, false, lignes())
            end
          end,
        },
      })
    end)
end

function M.faire(visuel)
  if M.refuse() then
    return
  end
  if visuel then
    local debut, fin, l = lignes_choisies()
    if l then
      faire(table.concat(l, "\n"), debut, fin)
    end
    return
  end
  M.saisir("Tâche à faire", function(t) faire(t) end)
end

-- Agent sur le projet : la CLI agentique de l'IA choisie, dans un terminal en bas (40 %), à la racine du projet.
-- La demande est pré-remplie, en mode interactif ; l'agent garde ses propres demandes de permission.
-- Comment chaque CLI reçoit une demande sans quitter après la réponse (false : elle ne sait pas, la demande est
-- copiée dans le presse-papiers).
local AGENTS = {
  claude = function(d) return { d } end,                 -- claude "demande"
  codex = function(d) return { d } end,                  -- codex "demande"
  ["cursor-agent"] = function(d) return { d } end,
  gemini = function(d) return { "-i", d } end,           -- -i : --prompt-interactive
  qwen = function(d) return { "-i", d } end,             -- Qwen Code, dérivé de Gemini CLI
  copilot = function(d) return { "-i", d } end,          -- GitHub Copilot CLI : --interactive
  opencode = function(d) return { "--prompt", d } end,
  -- Oh My Pi : « launch » (une demande n'est jamais une sous-commande : commit, config…) puis « -- » : tout ce qui suit est du
  -- texte (sinon « @app.route(…) » serait un fichier à lire, et omp s'arrête s'il manque ; vérifié dans cli/args.ts)
  omp = function(d) return { "launch", "--", d } end,
  ["kiro-cli"] = function(d) return { "chat", d } end,
  amp = false, crush = false, goose = false, aider = false,
}
local SANS_DEMANDE = { ["kiro-cli"] = { "chat" } }
-- Repli, si nc-ia etat --json ne donne pas la CLI agentique d'une IA : les IA qui sont elles-mêmes une CLI
local PROG_PAR_ID = { claude = "claude", codex = "codex", ["gemini-cli"] = "gemini", opencode = "opencode", qwen = "qwen", omp = "omp" }

-- La CLI agentique d'une IA de nc-ia etat --json : { prog, argv de base, nom } ou nil
local function cli_de(ia)
  local v
  for _, k in ipairs({ "cli_agent", "agent_cli", "cli_agentique", "agentique" }) do
    v = v or ia[k]
  end
  if type(v) == "table" then
    v = v.prog or v.commande or v.cli
  end
  if type(v) ~= "string" or v == "" then
    v = ia.prog or PROG_PAR_ID[ia.id]
  end
  if type(v) ~= "string" or v == "" then
    return nil
  end
  local argv = vim.split(vim.trim(v), "%s+")
  return { prog = vim.fs.basename(argv[1]), argv = argv, nom = ia.nom or ia.id }
end

local function cli_utilisable(ia, cli)
  for _, k in ipairs({ "agent_disponible", "cli_disponible" }) do
    if ia[k] == false then
      return false
    end
  end
  return vim.fn.executable(cli.argv[1]) == 1
end

local function etat(fini)
  if vim.fn.executable(nc_ia) ~= 1 then
    return vim.notify("nc-ia est introuvable (~/.local/bin/nc-ia).", vim.log.levels.ERROR)
  end
  vim.system({ nc_ia, "etat", "--json" }, { text = true }, function(r)
    vim.schedule(function()
      local ok, e = pcall(vim.json.decode, r.stdout or "")
      if r.code ~= 0 or not ok or type(e) ~= "table" then
        return vim.notify("nc-ia etat ne répond pas.", vim.log.levels.ERROR, { title = "IA" })
      end
      if e.coupee or e.mode == "non" then
        return vim.notify("L'IA est coupée (nc-reglages → Intelligence artificielle).", vim.log.levels.WARN,
          { title = "IA" })
      end
      fini(e)
    end)
  end)
end

local function terminal(cli, demande, dossier)
  local argv = vim.deepcopy(cli.argv)
  local forme = AGENTS[cli.prog]
  if demande ~= "" and forme then
    vim.list_extend(argv, forme(demande:sub(1, 1) == "-" and " " .. demande or demande))
  else
    vim.list_extend(argv, SANS_DEMANDE[cli.prog] or {})
    if demande ~= "" then
      copier(demande)
      vim.notify(cli.nom .. " ne reçoit pas de demande au lancement : elle est dans le presse-papiers (Ctrl+Maj+V).",
        vim.log.levels.INFO, { title = "IA" })
    end
  end
  vim.cmd("botright " .. math.max(5, math.floor(vim.o.lines * 0.4)) .. "split")
  vim.cmd.enew()
  if vim.fn.has("nvim-0.11") == 1 then
    vim.fn.jobstart(argv, { term = true, cwd = dossier })
  else
    vim.fn.termopen(argv, { cwd = dossier })
  end
  vim.cmd.startinsert()
  return argv
end

-- La demande (la sélection en visuel) et le dossier du projet, pris tout de suite : la réponse de nc-ia est asynchrone
local function demande_et_dossier(visuel)
  local demande = ""
  if visuel then
    local debut, fin, l = lignes_choisies()
    if l then
      local rel = vim.fn.expand("%:.")
      demande = vim.trim(table.concat(l, "\n"))
      if rel ~= "" then
        demande = demande .. "\n\n(Fichier : " .. rel .. ", lignes " .. debut .. " à " .. fin .. ")"
      end
    end
  end
  local fichier = vim.api.nvim_buf_get_name(0)
  local dossier = vim.fs.root(0, ".git")
    or (fichier ~= "" and vim.bo.buftype == "" and vim.fs.dirname(fichier))
    or vim.fn.getcwd()
  return demande, dossier
end

function M.agent(visuel)
  if M.refuse() then
    return
  end
  local demande, dossier = demande_et_dossier(visuel)
  etat(function(e)
    local id = e.mode == "manuel" and e.choix or (e.usages and e.usages.question or {}).id
    local ia
    for _, x in ipairs(e.ias or {}) do
      ia = ia or (x.id == id and x or nil)
    end
    if not ia then
      return vim.notify("Aucune IA disponible (nc-reglages → Intelligence artificielle).", vim.log.levels.WARN,
        { title = "IA" })
    end
    local cli = cli_de(ia)
    if not cli then
      return vim.notify("« " .. (ia.nom or id) .. " » n'a pas d'agent en terminal. Espace i A pour en choisir un autre.",
        vim.log.levels.WARN, { title = "IA" })
    end
    if not cli_utilisable(ia, cli) then
      return vim.notify("« " .. (ia.nom or id) .. " » : le programme « " .. cli.argv[1] .. " » est introuvable."
        .. " Espace i A pour en choisir un autre.", vim.log.levels.WARN, { title = "IA" })
    end
    terminal(cli, demande, dossier)
  end)
end

-- Espace i A : choisir l'agent parmi les IA disponibles
function M.choisir_agent(visuel)
  if M.refuse() then
    return
  end
  local demande, dossier = demande_et_dossier(visuel)
  etat(function(e)
    local liste, vus = {}, {}
    for _, ia in ipairs(e.ias or {}) do
      local cli = ia.disponible ~= false and cli_de(ia)
      if cli and not vus[cli.prog] and cli_utilisable(ia, cli) then
        vus[cli.prog] = true
        table.insert(liste, cli)
      end
    end
    if #liste == 0 then
      return vim.notify("Aucune IA disponible n'a d'agent en terminal.", vim.log.levels.WARN, { title = "IA" })
    end
    vim.ui.select(liste, { prompt = "Agent sur le projet", format_item = function(c)
      return c.nom .. " (" .. c.prog .. ")"
    end }, function(c)
      if c then
        terminal(c, demande, dossier)
      end
    end)
  end)
end

-- ── Le panneau d'agents (sidekick.nvim) ────────────────────────────────────────────────────────────────────────
-- L'IA de nc-ia traduite en outil sidekick (les noms de sidekick.cli.tools ; omp, kiro-cli… sont déclarés dans
-- lua/plugins/ia.lua). Sans sidekick (pas encore installé), Espace i a retombe sur le terminal en bas.
local OUTIL_SIDEKICK = { ["cursor-agent"] = "cursor" }

local function sidekick()
  local ok, cli = pcall(require, "sidekick.cli")
  return ok and cli or nil
end

local function sans_sidekick()
  vim.notify("Le panneau d'agents (sidekick.nvim) n'est pas installé : :Lazy sync.", vim.log.levels.WARN, { title = "IA" })
end

-- Espace i a : ouvre ou masque le panneau avec l'agent de l'IA choisie
function M.agent_panneau(visuel)
  if M.refuse() then
    return
  end
  local sk = sidekick()
  if not sk then
    return M.agent(visuel)
  end
  etat(function(e)
    local id = e.mode == "manuel" and e.choix or (e.usages and e.usages.question or {}).id
    local ia
    for _, x in ipairs(e.ias or {}) do
      ia = ia or (x.id == id and x or nil)
    end
    local cli = ia and cli_de(ia)
    if not ia then
      return vim.notify("Aucune IA disponible (nc-reglages → Intelligence artificielle).", vim.log.levels.WARN,
        { title = "IA" })
    elseif not cli then
      return vim.notify("« " .. (ia.nom or id) .. " » n'a pas d'agent en terminal. Espace i A pour en choisir un autre.",
        vim.log.levels.WARN, { title = "IA" })
    elseif not cli_utilisable(ia, cli) then
      return vim.notify("« " .. (ia.nom or id) .. " » : le programme « " .. cli.argv[1] .. " » est introuvable."
        .. " Espace i A pour en choisir un autre.", vim.log.levels.WARN, { title = "IA" })
    end
    sk.toggle({ name = OUTIL_SIDEKICK[cli.prog] or cli.prog, focus = true })
  end)
end

-- Espace i A : choisir l'agent (parmi ceux qui sont installés)
function M.choisir_panneau()
  if M.refuse() then
    return
  end
  local sk = sidekick()
  if not sk then
    return M.choisir_agent(false)
  end
  sk.select({ filter = { installed = true } })
end

-- Espace i s (code sous le curseur, ou sélection en visuel), Espace i F (le fichier) : envoyés à l'agent du panneau
function M.envoyer(msg)
  if M.refuse() then
    return
  end
  local sk = sidekick()
  if not sk then
    return sans_sidekick()
  end
  sk.send({ msg = msg })
end

function M.prompt()
  if M.refuse() then
    return
  end
  local sk = sidekick()
  if not sk then
    return sans_sidekick()
  end
  sk.prompt()
end

-- Ctrl + . : aller au panneau
function M.focus_panneau()
  if M.refuse() then
    return
  end
  local sk = sidekick()
  if sk then
    sk.focus()
  end
end

-- ── Le message de commit (nc-ia commit) ────────────────────────────────────────────────────────────────────────
-- Racine du dépôt d'un message de commit : COMMIT_EDITMSG est dans .git/ (ou .git/worktrees/NOM/ pour un arbre de
-- travail lié, dont le fichier gitdir renvoie vers le .git de cet arbre)
local function racine_depot(buf)
  local nom = vim.api.nvim_buf_get_name(buf)
  local lie = nom:match("^(.*/%.git/worktrees/[^/]+)/")
  if lie then
    local f = io.open(lie .. "/gitdir")
    if f then
      local g = (f:read("*l") or ""):gsub("%s+$", "")
      f:close()
      if g ~= "" then
        return vim.fs.dirname(g)
      end
    end
  end
  return vim.fs.root(nom ~= "" and nom or vim.fn.getcwd(), ".git") or vim.fn.getcwd()
end

-- Une ligne de vrai texte (ni vide, ni commentaire « # ») : un message est déjà écrit
local function message_ecrit(buf)
  for _, l in ipairs(vim.api.nvim_buf_get_lines(buf, 0, -1, false)) do
    if l:match("%S") and not l:match("^#") then
      return true
    end
  end
  return false
end

function M.commit()
  if M.refuse() then
    return
  end
  local buf = vim.api.nvim_get_current_buf()
  if vim.bo[buf].filetype ~= "gitcommit" then
    return vim.notify("Espace i m écrit le message d'un commit : à lancer dans le message (git commit).",
      vim.log.levels.INFO, { title = "IA" })
  end
  if message_ecrit(buf) then
    return vim.notify("Un message est déjà écrit : rien n'est changé.", vim.log.levels.INFO, { title = "IA" })
  end
  if vim.fn.executable(nc_ia) ~= 1 then
    return vim.notify("nc-ia est introuvable (~/.local/bin/nc-ia).", vim.log.levels.ERROR)
  end
  vim.notify("L'IA écrit le message…", vim.log.levels.INFO, { title = "IA" })
  vim.system({ nc_ia, "commit" }, { cwd = racine_depot(buf), text = true }, function(r)
    vim.schedule(function()
      local sortie = (r.stdout or ""):gsub("%s+$", "")
      local erreur = (r.stderr or ""):gsub("%s+$", "")
      if r.code == 2 then
        return vim.notify("Rien n'est indexé : git add d'abord.", vim.log.levels.WARN, { title = "IA" })
      elseif r.code == 3 then
        return vim.notify("IA désactivée (nc-reglages → Intelligence artificielle)", vim.log.levels.WARN, { title = "IA" })
      elseif r.code == 4 then
        return vim.notify("Un secret a été repéré dans les changements : rien n'est envoyé à l'IA."
          .. (erreur ~= "" and "\n" .. erreur or ""), vim.log.levels.WARN, { title = "IA" })
      elseif r.code ~= 0 or sortie == "" then
        return vim.notify(erreur ~= "" and erreur or "L'IA n'a rien répondu.", vim.log.levels.WARN, { title = "IA" })
      end
      if not vim.api.nvim_buf_is_valid(buf) then
        return
      end
      if message_ecrit(buf) then -- écrit pendant l'attente : on n'écrase rien
        return vim.notify("Un message a été écrit entre-temps : celui de l'IA n'est pas inséré.", vim.log.levels.INFO,
          { title = "IA" })
      end
      sortie = sans_clotures(sortie, false)
      local lignes = vim.api.nvim_buf_get_lines(buf, 0, -1, false)
      local n = 0 -- les lignes vides du début sont remplacées par le message ; les commentaires restent dessous
      while n < #lignes and not lignes[n + 1]:match("%S") do
        n = n + 1
      end
      local neuf = vim.split(sortie, "\n")
      if n < #lignes then
        table.insert(neuf, "")
      end
      vim.api.nvim_buf_set_lines(buf, 0, n, false, neuf)
      vim.notify("Message écrit : relis-le, puis enregistre.", vim.log.levels.INFO, { title = "IA" })
    end)
  end)
end

-- ── Un diagnostic expliqué et corrigé (Espace i d) ─────────────────────────────────────────────────────────────
local SEVERITE = { "erreur", "avertissement", "information", "astuce" }

-- Le dernier bloc de code d'une réponse (la correction), sans ses clôtures
local function dernier_bloc(t)
  local dernier, courant, dans = nil, nil, false
  for _, l in ipairs(vim.split(t, "\n")) do
    if l:match("^%s*```") then
      if dans then
        dernier = courant
      end
      dans, courant = not dans, {}
    elseif dans then
      table.insert(courant, l)
    end
  end
  return dernier and table.concat(dernier, "\n") or nil
end

function M.diagnostic()
  if M.refuse() then
    return
  end
  local buf, origine = vim.api.nvim_get_current_buf(), vim.api.nvim_get_current_win()
  local c = vim.api.nvim_win_get_cursor(origine)
  local diags = vim.diagnostic.get(buf, { lnum = c[1] - 1 })
  if #diags == 0 then
    return vim.notify("Aucun diagnostic sur cette ligne.", vim.log.levels.INFO, { title = "IA" })
  end
  table.sort(diags, function(a, b) return a.severity < b.severity end)
  local d = diags[1]
  local ft = type_fichier(buf)
  local n = vim.api.nvim_buf_line_count(buf)
  local a, b = math.max(1, c[1] - 15), math.min(n, c[1] + 15)
  local tick = vim.b[buf].changedtick
  local contexte = table.concat(vim.api.nvim_buf_get_lines(buf, a - 1, b, false), "\n")
  local nom = vim.fn.expand("%:t")
  local qui = (d.source and d.source .. " : " or "") .. (d.code and "[" .. tostring(d.code) .. "] " or "")
  local entree = "Diagnostic (" .. (SEVERITE[d.severity] or "erreur") .. ") à la ligne " .. (d.lnum + 1) .. " : " .. qui
    .. d.message .. "\n\nFichier « " .. (nom ~= "" and nom or "sans nom") .. " » (" .. ft .. "), lignes " .. a .. " à " .. b
    .. " :\n" .. contexte
  local consigne = "Explique cette erreur en quelques phrases simples, puis donne la correction : les lignes " .. a
    .. " à " .. b .. " corrigées, recopiées en entier dans un seul bloc de code " .. ft .. "."
  lancer({ "texte", consigne, "--stdin" }, entree, function(sortie)
    if balisage_outil(sortie) then
      return vim.notify("L'IA a répondu par un appel d'outil : rien n'est proposé.", vim.log.levels.WARN, { title = "IA" })
    end
    montrer(sortie, {
      origine = origine, titre = "Diagnostic expliqué",
      aide = "a appliquer la correction (lignes " .. a .. " à " .. b .. ") · y copier · r refuser",
      touches = {
        a = function(_, ferme)
          local code = dernier_bloc(sortie)
          if not code then
            return vim.notify("Pas de code corrigé dans la réponse : rien à appliquer.", vim.log.levels.INFO,
              { title = "IA" })
          end
          if not vim.api.nvim_buf_is_valid(buf) or vim.b[buf].changedtick ~= tick then
            return vim.notify("Le fichier a changé depuis la demande : rien n'est appliqué.", vim.log.levels.WARN,
              { title = "IA" })
          end
          ferme()
          vim.api.nvim_buf_set_lines(buf, a - 1, b, false, vim.split(code, "\n"))
        end,
        r = function(_, ferme) ferme() end,
        y = function(t) copier(dernier_bloc(t) or t) end,
      },
    })
  end)
end

return M

-- Les agents suivis par nc-claude (Claude Code, Codex, Gemini CLI…), vus depuis Neovim : un petit élément de la
-- barre lualine (« 󰚩 Claude travaille » / « 󰚩 Claude t'attend ») et Espace i w pour aller sur son terminal.
-- Source : $XDG_RUNTIME_DIR/nc-claude/etat.json, écrit par ~/.local/bin/nc-claude (sessions[id].etat : travail,
-- attente / demande / terminal = il t'attend ; fini et pret = rien à montrer). Aucune minuterie de sondage : un
-- observateur de dossier (vim.uv fs_event), avec un court anti-rebond. Rien quand nc-claude n'a jamais tourné.
local M = {}
local uv = vim.uv or vim.loop

local ATTEND = { attente = true, demande = true, terminal = true }
local NOMS = { claude = "Claude", antigravity = "Antigravity", opencode = "OpenCode", codex = "Codex", gemini = "Gemini",
  qwen = "Qwen", cursor = "Cursor", copilot = "Copilot", kiro = "Kiro", amp = "Amp" }

local etat = nil -- { texte, attend, session } ou nil quand rien ne tourne
local observateurs = {} -- { dossier = fs_event }
local minuteur
local demarre = false

local function dossier_run()
  local run = os.getenv("XDG_RUNTIME_DIR")
  return run and (run .. "/nc-claude") or nil
end

-- Lit etat.json et en tire la phrase à montrer : les sessions qui t'attendent d'abord, sinon celles qui travaillent
function M.lire()
  local run = dossier_run()
  local f = run and io.open(run .. "/etat.json")
  if not f then
    return nil
  end
  local contenu = f:read("*a")
  f:close()
  local ok, d = pcall(vim.json.decode, contenu)
  if not ok or type(d) ~= "table" or type(d.sessions) ~= "table" then
    return nil
  end
  local attendent, travaillent = {}, {}
  for _, s in pairs(d.sessions) do
    if type(s) == "table" then
      if ATTEND[s.etat] then
        table.insert(attendent, s)
      elseif s.etat == "travail" then
        table.insert(travaillent, s)
      end
    end
  end
  local liste = #attendent > 0 and attendent or travaillent
  if #liste == 0 then
    return nil
  end
  table.sort(liste, function(a, b) return (a.maj or 0) > (b.maj or 0) end)
  local s = liste[1]
  local nom = NOMS[s.agent or "claude"] or tostring(s.agent)
  local attend = #attendent > 0
  local texte = "󰚩 " .. nom
  if #liste > 1 then
    texte = texte .. " ×" .. #liste
  end
  texte = texte .. (attend and " t'attend" or " travaille")
  return { texte = texte, attend = attend, session = s }
end

local function rafraichir()
  etat = M.lire()
  vim.schedule(function()
    local ok, lualine = pcall(require, "lualine")
    if ok then
      pcall(lualine.refresh)
    end
  end)
end

-- Anti-rebond ~200 ms : un seul minuteur d'un coup, qui s'arrête de lui-même (jamais périodique)
local function plus_tard()
  if not minuteur then
    minuteur = uv.new_timer()
  end
  minuteur:stop()
  minuteur:start(200, 0, vim.schedule_wrap(rafraichir))
end

local function observer(dossier, suit)
  if observateurs[dossier] then
    return true
  end
  local e = uv.new_fs_event()
  local ok = e and e:start(dossier, {}, function(err, nom)
    if err then
      return
    end
    suit(nom)
  end)
  if not ok or ok < 0 then
    if e and not e:is_closing() then
      e:close()
    end
    return false
  end
  observateurs[dossier] = e
  return true
end

-- Démarre l'observation (une fois). Le dossier nc-claude n'existe qu'après le premier événement d'un agent : on
-- regarde alors son parent, et on passe au dossier dès qu'il apparaît.
function M.demarrer()
  if demarre then
    return
  end
  local run = dossier_run()
  if not run then
    return
  end
  demarre = true
  etat = M.lire()
  local function dossier_present()
    if uv.fs_stat(run) then
      observer(run, function(nom)
        if nom == "etat.json" or nom == nil then
          plus_tard()
        end
      end)
      return true
    end
  end
  if not dossier_present() then
    observer(vim.fs.dirname(run), function(nom)
      if nom == "nc-claude" and dossier_present() then
        plus_tard()
      end
    end)
  end
end

function M.arreter()
  for d, e in pairs(observateurs) do
    if not e:is_closing() then
      e:close()
    end
    observateurs[d] = nil
  end
  if minuteur and not minuteur:is_closing() then
    minuteur:close()
  end
  minuteur, demarre, etat = nil, false, nil
end

-- Espace i w (ou clic sur l'élément) : va sur le terminal de l'agent qui t'attend (sinon celui qui travaille)
function M.aller()
  local e = M.lire()
  local s = e and e.session
  local terminal = s and tonumber(s.terminal)
  if not terminal or terminal <= 0 then
    return vim.notify("Aucun agent à rejoindre.", vim.log.levels.INFO, { title = "Agents" })
  end
  local bin = os.getenv("HOME") .. "/.local/bin/nc-claude"
  if vim.fn.executable(bin) ~= 1 then
    return
  end
  vim.system({ bin, "aller", tostring(terminal), tostring(tonumber(s.shell) or 0) }, { detach = true })
end

-- Pour lualine (lualine_x) : une entrée prête à insérer
function M.composant()
  return {
    function()
      return etat and etat.texte or ""
    end,
    cond = function()
      return etat ~= nil
    end,
    color = function()
      local hl = etat and etat.attend and "DiagnosticWarn" or "Special"
      local fg = vim.api.nvim_get_hl(0, { name = hl, link = false }).fg
      return fg and { fg = string.format("#%06x", fg) } or nil
    end,
    on_click = function()
      M.aller()
    end,
  }
end

-- Pour les tests : l'état courant, sans attendre lualine
function M.etat()
  return etat
end

return M

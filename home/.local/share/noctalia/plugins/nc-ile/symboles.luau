--!nonstrict
-- nc/ile : symboles dessinés dans l'esprit des SF Symbols d'Apple (traits arrondis, formes pleines), en SVG.
-- Chaque couleur demandée est écrite une fois dans le dossier de données du plugin, puis réutilisée.
--   local sym = require("./symboles.luau")
--   sym.image("wifi", "#ffffff", 22)      -> nœud ui.image
--   sym.existe("wifi")                    -> vrai si le symbole est dessiné ici

local M = {}
local VERSION = "v2"                       -- à changer quand un dessin change (les anciens fichiers sont ignorés)

-- Trait arrondi (épaisseur w, 2,2 par défaut) et forme pleine
local function Tw(w) return 'fill="none" stroke="{c}" stroke-width="' .. (w or "2.5") .. '" stroke-linecap="round" stroke-linejoin="round"' end
local T = Tw()
local P = 'fill="{c}"'

-- Engrenage plein (8 dents) calculé : trou central par la règle « evenodd »
local function engrenage()
  local pts, n = {}, 8
  for i = 0, n * 4 - 1 do
    local a = (i / (n * 4)) * 2 * math.pi - math.pi / 2
    local r = (i % 4 == 0 or i % 4 == 1) and 10.2 or 7.9
    table.insert(pts, string.format("%.2f %.2f", 12 + r * math.cos(a), 12 + r * math.sin(a)))
  end
  return '<path fill-rule="evenodd" ' .. P .. ' d="M' .. table.concat(pts, " L") .. ' Z M12 8.6a3.4 3.4 0 1 0 0 6.8a3.4 3.4 0 1 0 0-6.8Z"/>'
end

local DESSINS = {
  wifi = '<g ' .. Tw("2.9") .. '><path d="M2.6 9.2a13.3 13.3 0 0 1 18.8 0"/><path d="M5.9 12.6a8.6 8.6 0 0 1 12.2 0"/><path d="M9.2 16a3.9 3.9 0 0 1 5.6 0"/></g><circle cx="12" cy="19.2" r="1.9" ' .. P .. '/>',
  ["wifi-off"] = '<g ' .. Tw("2.9") .. ' opacity=".55"><path d="M2.6 9.2a13.3 13.3 0 0 1 18.8 0"/><path d="M5.9 12.6a8.6 8.6 0 0 1 12.2 0"/><path d="M9.2 16a3.9 3.9 0 0 1 5.6 0"/></g><circle cx="12" cy="19.2" r="1.9" ' .. P .. ' opacity=".55"/><path ' .. T .. ' d="M4 3.5 20 20.5"/>',
  bluetooth = '<path ' .. Tw("2.7") .. ' d="M6.8 7.6 17 16.4 12 20.9V3.1l5 4.5L6.8 16.4"/>',
  lune = '<path ' .. P .. ' d="M20.6 14.8A8.8 8.8 0 1 1 9.2 3.4a7 7 0 0 0 11.4 11.4Z"/>',
  cloche = '<path ' .. P .. ' d="M12 3a6 6 0 0 0-6 6v3.6l-1.7 2.8a1 1 0 0 0 .9 1.6h13.6a1 1 0 0 0 .9-1.6L18 12.6V9a6 6 0 0 0-6-6Z"/><path ' .. P .. ' d="M9.7 18.8a2.4 2.4 0 0 0 4.6 0Z"/>',
  manette = '<path fill-rule="evenodd" ' .. P .. ' d="M7.2 6.5h9.6c2.6 0 4.4 2 4.9 4.8l.9 5.1c.4 2.2-1 3.6-2.6 3.6-1.3 0-2.2-.8-3-1.9l-1.1-1.5H8.1L7 18.1c-.8 1.1-1.7 1.9-3 1.9-1.6 0-3-1.4-2.6-3.6l.9-5.1C2.8 8.5 4.6 6.5 7.2 6.5Z M6.4 10.4h1.5V8.9h1.5v1.5h1.5v1.5H9.4v1.5H7.9v-1.5H6.4Z M15.3 9.9a1.05 1.05 0 1 0 2.1 0a1.05 1.05 0 1 0-2.1 0Z M13.4 12.3a1.05 1.05 0 1 0 2.1 0a1.05 1.05 0 1 0-2.1 0Z"/>',
  soleil = '<circle cx="12" cy="12" r="4.7" ' .. P .. '/><g ' .. Tw("2.9") .. '><path d="M12 2.6v2.1M12 19.3v2.1M2.6 12h2.1M19.3 12h2.1M5.4 5.4l1.5 1.5M17.1 17.1l1.5 1.5M5.4 18.6l1.5-1.5M17.1 6.9l1.5-1.5"/></g>',
  ["haut-parleur"] = '<path ' .. P .. ' d="M3.5 9.3h3.3l4.5-3.9c.6-.5 1.5-.1 1.5.7v11.8c0 .8-.9 1.2-1.5.7l-4.5-3.9H3.5c-.6 0-1-.4-1-1v-3.4c0-.6.4-1 1-1Z"/><g ' .. T .. '><path d="M16 9.2a4 4 0 0 1 0 5.6"/><path d="M18.7 6.5a7.8 7.8 0 0 1 0 11"/></g>',
  muet = '<path ' .. P .. ' d="M3.5 9.3h3.3l4.5-3.9c.6-.5 1.5-.1 1.5.7v11.8c0 .8-.9 1.2-1.5.7l-4.5-3.9H3.5c-.6 0-1-.4-1-1v-3.4c0-.6.4-1 1-1Z"/><path ' .. T .. ' d="M16 9.5l5 5M21 9.5l-5 5"/>',
  note = '<path ' .. T .. ' d="M9.3 17.4V6.3l10-2.3v11.2"/><ellipse cx="6.9" cy="17.6" rx="2.6" ry="2.2" ' .. P .. '/><ellipse cx="16.9" cy="15.4" rx="2.6" ry="2.2" ' .. P .. '/>',
  lecture = '<path ' .. P .. ' d="M7.4 4.9c0-.9 1-1.4 1.7-.9l10.1 6.9c.7.5.7 1.6 0 2.1L9.1 20c-.7.5-1.7 0-1.7-.9Z"/>',
  pause = '<rect x="6.2" y="4.6" width="4" height="14.8" rx="1.3" ' .. P .. '/><rect x="13.8" y="4.6" width="4" height="14.8" rx="1.3" ' .. P .. '/>',
  precedent = '<path ' .. P .. ' d="M11.6 6.3v11.4c0 .7-.8 1.1-1.3.6L3.9 12.6a.8.8 0 0 1 0-1.2l6.4-5.7c.5-.5 1.3-.1 1.3.6Z"/><path ' .. P .. ' d="M20.3 6.3v11.4c0 .7-.8 1.1-1.3.6l-6.4-5.7a.8.8 0 0 1 0-1.2L19 5.7c.5-.5 1.3-.1 1.3.6Z"/>',
  suivant = '<path ' .. P .. ' d="M12.4 6.3v11.4c0 .7.8 1.1 1.3.6l6.4-5.7a.8.8 0 0 0 0-1.2L13.7 5.7c-.5-.5-1.3-.1-1.3.6Z"/><path ' .. P .. ' d="M3.7 6.3v11.4c0 .7.8 1.1 1.3.6l6.4-5.7a.8.8 0 0 0 0-1.2L5 5.7c-.5-.5-1.3-.1-1.3.6Z"/>',
  cadenas = '<path ' .. T .. ' d="M8 10.6V7.9a4 4 0 0 1 8 0v2.7"/><rect x="5.3" y="10.4" width="13.4" height="10.4" rx="2.6" ' .. P .. '/>',
  marche = '<path ' .. Tw("2.8") .. ' d="M12 3.4v8.1M6.9 6.4a7.3 7.3 0 1 0 10.2 0"/>',
  reglages = engrenage(),
  capture = '<path ' .. T .. ' d="M4 8.6V6.1A2.1 2.1 0 0 1 6.1 4h2.5M15.4 4h2.5A2.1 2.1 0 0 1 20 6.1v2.5M20 15.4v2.5a2.1 2.1 0 0 1-2.1 2.1h-2.5M8.6 20H6.1A2.1 2.1 0 0 1 4 17.9v-2.5"/><circle cx="12" cy="12" r="2.6" ' .. P .. '/>',
  eclair = '<path ' .. P .. ' d="M13.4 2.6 4.9 13.5c-.4.5 0 1.3.6 1.3h5.2l-1.3 6.5c-.1.6.6.9 1 .4l8.5-10.9c.4-.5 0-1.3-.6-1.3h-5.2l1.3-6.5c.1-.6-.6-.9-1-.4Z"/>',
  feuille = '<path ' .. P .. ' d="M20.2 3.8c-8.6 0-15.2 3.8-15.2 11.3 0 1.6.4 3 1 4.2C7.6 14.4 11.1 11 15.2 9.4c-3.5 2.1-6.8 5.5-8.4 10.6.9.4 2 .6 3.3.6 7.4 0 10.1-7.2 10.1-16.8Z"/>',
  equilibre = '<circle cx="12" cy="12" r="8.4" ' .. T .. '/><path ' .. P .. ' d="M12 3.6a8.4 8.4 0 0 0 0 16.8Z"/>',
  onde = '<path ' .. Tw("2.8") .. ' d="M4 10.2v3.6M8 7v10M12 4v16M16 8v8M20 10.6v2.8"/>',
  micro = '<rect x="8.8" y="2.8" width="6.4" height="11.4" rx="3.2" ' .. P .. '/><path ' .. T .. ' d="M5.6 11.2a6.4 6.4 0 0 0 12.8 0M12 17.7V21"/>',
  ["micro-coupe"] = '<rect x="8.8" y="2.8" width="6.4" height="11.4" rx="3.2" ' .. P .. ' opacity=".55"/><path ' .. T .. ' d="M5.6 11.2a6.4 6.4 0 0 0 12.8 0M12 17.7V21M4 3.5l16 17"/>',
  ["chevron-gauche"] = '<path ' .. Tw("2.9") .. ' d="M14.6 5.4 8 12l6.6 6.6"/>',
  ["chevron-droite"] = '<path ' .. Tw("2.9") .. ' d="M9.4 5.4 16 12l-6.6 6.6"/>',
  coche = '<path ' .. Tw("2.9") .. ' d="M5 12.6l4.3 4.3L19.2 7"/>',
  casque = '<path ' .. T .. ' d="M4 15.5V12a8 8 0 0 1 16 0v3.5"/><rect x="2.8" y="13.4" width="5.2" height="7.4" rx="2" ' .. P .. '/><rect x="16" y="13.4" width="5.2" height="7.4" rx="2" ' .. P .. '/>',
  enceinte = '<rect x="5.5" y="2.8" width="13" height="18.4" rx="3" ' .. T .. '/><circle cx="12" cy="14.6" r="3" ' .. P .. '/><circle cx="12" cy="7.3" r="1.3" ' .. P .. '/>',
}

local DOSSIER = nil
local function dossier()
  if DOSSIER then return DOSSIER end
  local base = noctalia.pluginDataDir()
  DOSSIER = (base or noctalia.expandPath("~/.cache/nc")) .. "/symboles-" .. VERSION
  noctalia.mkdirAll(DOSSIER)
  return DOSSIER
end

function M.existe(nom)
  return DESSINS[nom] ~= nil
end

function M.chemin(nom, couleur)
  couleur = couleur or "#ffffff"
  local f = dossier() .. "/" .. nom .. "-" .. string.gsub(couleur, "#", "") .. ".svg"
  if not noctalia.fileExists(f) then
    local svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">' .. string.gsub(DESSINS[nom], "{c}", couleur) .. "</svg>"
    noctalia.writeFile(f, svg)
  end
  return f
end

function M.image(nom, couleur, taille, cle)
  return ui.image({ key = cle, path = M.chemin(nom, couleur), width = taille, height = taille, fit = "contain" })
end

return M

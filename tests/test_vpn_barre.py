"""Pilule VPN de la barre Noctalia (plugin nc/vpn), poussée par l'île.
- Le widget (vpn.luau) tourne avec lua et un faux `noctalia` : caché sans fichier d'état, jamais de zone de clic caché, lecture du fichier
  seulement s'il a changé (taille + date) et seulement écran allumé, « VPN » seul en partage d'écran, déconnecté mais cliquable,
  clic = argv exact de l'IPC « ile vpn » (le même que Super + Alt + V), aucun réseau ni nmcli.
- VPN_PILULE_BARRE et VPN_MASQUER_TRAY : appliqués à la config de Noctalia (zy-reglages.toml) par nc-reglages, et retirés quand ils
  sont coupés ; réglages présents dans le catalogue (donc dans le ⚙ de la fenêtre VPN, section Île, et dans Parametres.qml).
- La règle Hyprland de la fenêtre VPN ne vise que son titre ; elle est placée à l'ouverture et exclue de la mémoire des fenêtres.
Tout est isolé (faux HOME) ; le vrai Noctalia, le vrai Hyprland et la vraie île ne sont jamais touchés."""
import json
import os
import re
from pathlib import Path
import runpy
import shutil
import subprocess
import tempfile
import tomllib
import unittest
from unittest.mock import patch
import warnings

REPO = Path(__file__).resolve().parents[1]
PLUGIN = REPO / "home/.local/share/noctalia/plugins/nc-vpn"
CONFIG = REPO / "home/.config/noctalia/config.toml"
NC_REGLAGES = REPO / "home/.local/bin/nc-reglages"

PRELUDE = r'''
local FICHIER = arg[1]
RUN = "/run/test"
ETAT, ETEINT = RUN .. "/nc-vpn-barre.json", RUN .. "/nc-ecran-eteint"
FILES, JSON, LECTURES, STATS, LANCES, VISIBLE, RENDU, BULLE, INTERVALLES = {}, {}, 0, 0, {}, nil, nil, nil, {}
noctalia = {
  getenv = function(n) if n == "XDG_RUNTIME_DIR" then return RUN end end,
  expandPath = function(p) return p end,
  pluginDataDir = function() return "/data" end, mkdirAll = function() return true end,
  fileExists = function(p) return FILES[p] ~= nil or p:match("^/data/") ~= nil and ECRITS ~= nil and ECRITS[p] ~= nil end,
  writeFile = function(p, c) ECRITS = ECRITS or {}; ECRITS[p] = c; return true end,
  fileInfo = function(p) STATS = STATS + 1; local f = FILES[p]; if not f then return nil, "absent" end; return { size = #f.texte, mtime = f.mtime, isDir = false } end,
  readFile = function(p) LECTURES = LECTURES + 1; local f = FILES[p]; return f and f.texte or nil end,
  json = { decode = function(s) return JSON[s] end },
  runAsync = function(argv, cb, t) LANCES[#LANCES + 1] = argv end,
  setUpdateInterval = function(ms) INTERVALLES[#INTERVALLES + 1] = ms end,
  nowMs = function() return 0 end,
}
barWidget = { render = function(t) RENDU = t end, setTooltip = function(t) BULLE = t end, setVisible = function(v) VISIBLE = v end,
  isVertical = function() return false end }
local function noeud(k) return function(o, e) return { k = k, o = o or {}, e = e or {} } end end
ui = setmetatable({}, { __index = function(_, k) return noeud(k) end })
function chercher(n, test, r) r = r or {}; if test(n) then r[#r + 1] = n end; for _, e in ipairs(n.e or {}) do chercher(e, test, r) end; return r end
function textes(n) local t = {}; for _, x in ipairs(chercher(n, function(m) return m.k == "label" end)) do t[#t + 1] = x.o.text end; return t end
function egal(a, b, msg) if a ~= b then error((msg or "") .. " : attendu " .. tostring(b) .. ", obtenu " .. tostring(a), 2) end end
function poser(etat, mtime)
  local texte = "etat" .. tostring(mtime) .. tostring(#tostring(etat))   -- contenu opaque, la taille varie avec l'état
  FILES[ETAT] = { texte = texte, mtime = mtime }; JSON[texte] = etat
end
function charger() dofile(FICHIER) end
'''


@unittest.skipUnless(shutil.which("lua"), "Lua requis")
class Widget(unittest.TestCase):
    def lua(self, code):
        with tempfile.TemporaryDirectory() as d:
            h = Path(d) / "harnais.lua"
            h.write_text(PRELUDE + code)
            r = subprocess.run(["lua", str(h), str(PLUGIN / "vpn.luau")], text=True, capture_output=True, timeout=10)
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)

    def test_cache_sans_fichier_et_sans_zone_de_clic(self):
        self.lua(r'''
charger()
egal(VISIBLE, false, "caché sans fichier d'état")
onClick(); egal(#LANCES, 0, "une pastille cachée ne garde jamais de zone de clic")
-- Le fichier apparaît : visible ; il disparaît : caché de nouveau, de nouveau sans clic
poser({ connecte = false, fournisseur = "", pays = "", masque_partage = false }, 100)
update(); egal(VISIBLE, true)
onClick(); egal(#LANCES, 1)
FILES[ETAT] = nil
update(); egal(VISIBLE, false, "fichier retiré (réglage coupé, île arrêtée) : caché")
onClick(); egal(#LANCES, 1, "toujours aucun clic une fois caché")
''')

    def test_connecte_fournisseur_et_drapeau_et_clic_exact(self):
        self.lua(r'''
poser({ connecte = true, fournisseur = "Proton VPN", pays = "FR", masque_partage = false }, 100)
charger()
egal(VISIBLE, true)
local t = textes(RENDU)
egal(#t, 1); egal(t[1], "Proton VPN · " .. utf8.char(0x1F1EB, 0x1F1F7) .. " FR", "fournisseur, drapeau et pays")
local imgs = chercher(RENDU, function(n) return n.k == "image" end)
egal(#imgs, 1, "le bouclier maison"); egal(imgs[1].o.path:match("plein%.svg$"), "plein.svg")
assert(ECRITS[imgs[1].o.path]:find("<svg"), "bouclier écrit en SVG")
onClick()
egal(#LANCES, 1)
local a = LANCES[1]
egal(table.concat(a, " "), "qs -c nc-ile ipc call ile vpn", "le même IPC que Super + Alt + V, en argv")
''')

    def test_deconnecte_reste_cliquable_sans_texte(self):
        self.lua(r'''
poser({ connecte = false, fournisseur = "", pays = "", masque_partage = false }, 100)
charger()
egal(VISIBLE, true); egal(#textes(RENDU), 0, "déconnecté : le bouclier seul")
egal(chercher(RENDU, function(n) return n.k == "image" end)[1].o.path:match("vide%.svg$"), "vide.svg")
onClick(); egal(#LANCES, 1, "cliquable même déconnecté")
''')

    def test_partage_d_ecran_vpn_seul(self):
        self.lua(r'''
poser({ connecte = true, fournisseur = "", pays = "", masque_partage = true }, 100)
charger()
local t = textes(RENDU); egal(#t, 1); egal(t[1], "VPN", "partage : « VPN » seul")
-- même si un fichier mal fait contenait un fournisseur, le partage l'emporte
poser({ connecte = true, fournisseur = "Mullvad", pays = "SE", masque_partage = true }, 101)
update(); egal(textes(RENDU)[1], "VPN")
''')

    def test_lecture_seulement_si_le_fichier_change(self):
        self.lua(r'''
poser({ connecte = true, fournisseur = "Mullvad", pays = "SE", masque_partage = false }, 100)
charger()
egal(LECTURES, 1)
for i = 1, 10 do update() end
egal(LECTURES, 1, "fichier inchangé : aucune relecture")
egal(textes(RENDU)[1]:match("^Mullvad"), "Mullvad")
poser({ connecte = false, fournisseur = "", pays = "", masque_partage = false }, 105)
update(); egal(LECTURES, 2, "changé : une seule lecture"); egal(#textes(RENDU), 0)
update(); egal(LECTURES, 2)
''')

    def test_ecran_eteint_rien_n_est_lu(self):
        self.lua(r'''
poser({ connecte = true, fournisseur = "Mullvad", pays = "SE", masque_partage = false }, 100)
charger()
local l, s = LECTURES, STATS
FILES[ETEINT] = { texte = "", mtime = 1 }
poser({ connecte = false, fournisseur = "", pays = "", masque_partage = false }, 200)
for i = 1, 5 do update() end
egal(LECTURES, l, "écran éteint : aucune lecture"); egal(STATS, s, "écran éteint : pas même un stat du fichier d'état")
FILES[ETEINT] = nil
update(); egal(LECTURES, l + 1, "au rallumage : relu tout de suite"); egal(#textes(RENDU), 0)
''')

    def test_aucun_reseau_ni_commande_reseau(self):
        src = (PLUGIN / "vpn.luau").read_text()
        code = re.sub(r"--[^\n]*", "", src).replace("http://www.w3.org/2000/svg", "").lower()                 # le code, sans les commentaires qui disent justement « aucun nmcli »
        for interdit in ("nmcli", "http", "download", "geoloc", "ipwho", "curl", "wget"):
            self.assertNotIn(interdit, code, interdit)
        # Le seul lancement : l'IPC de l'île, en argv
        self.assertEqual(src.count("runAsync"), 1)
        self.assertIn('{ "qs", "-c", "nc-ile", "ipc", "call", "ile", "vpn" }', src)
        self.assertIn("nc-ecran-eteint", src)

    def test_syntaxe_luau_simple(self):
        if shutil.which("luac"):
            subprocess.run(["luac", "-p", str(PLUGIN / "vpn.luau")], check=True)


class Configuration(unittest.TestCase):
    def test_manifeste_et_plugin_active_et_exporte(self):
        m = tomllib.loads((PLUGIN / "plugin.toml").read_text())
        self.assertEqual(m["id"], "nc/vpn")
        self.assertLessEqual(m["plugin_api"], 32)
        self.assertEqual([w["id"] for w in m["widget"]], ["vpn"])
        conf = CONFIG.read_text()
        self.assertIn('"nc/vpn"', conf.split("[plugins]")[1])
        self.assertIn(".local/share/noctalia/plugins/nc-vpn", (REPO / "export.sh").read_text())
        # Rien de nouveau dans la barre tant que le réglage n'est pas à oui
        self.assertNotIn("nc/vpn:vpn", conf.split("[bar.default]")[1].split("[[bar")[0])

    def charger(self, d):
        home = Path(d)
        (home / ".config/noctalia").mkdir(parents=True)
        shutil.copy(CONFIG, home / ".config/noctalia/config.toml")
        env = dict(HOME=str(home), XDG_CONFIG_HOME=str(home / ".config"), NC_LANGUE="fr")
        with patch.dict(os.environ, env), warnings.catch_warnings():
            warnings.simplefilter("ignore", ResourceWarning)
            nc = runpy.run_path(str(NC_REGLAGES))
        nc["appliquer_noctalia"].__globals__["subprocess"] = type("S", (), {"run": staticmethod(lambda *a, **k: None)})
        return nc, home / ".config/noctalia/zy-reglages.toml"

    def test_reglages_dans_le_catalogue_section_ile_defauts_non(self):
        with tempfile.TemporaryDirectory(prefix="nc-vpn-barre-") as d:
            nc, _ = self.charger(d)
            for cle in ("VPN_PILULE_BARRE", "VPN_MASQUER_TRAY"):
                r = nc["PAR_CLE"][cle]
                self.assertEqual((r.section, r.genre, r.defaut, r.groupe), ("Île", "ouinon", "non", "noctalia"), cle)
            self.assertEqual(nc["MATERIEL"]["VPN_PILULE_BARRE"], "ile", "sans l'île, pas de pilule : réglage caché")
            # Le ⚙ de la fenêtre VPN ouvre cette section, et la fenêtre des réglages (Parametres.qml) montre tout le catalogue
            self.assertIn('section: "Île"', (REPO / "home/.config/quickshell/nc-ile/VpnEntete.qml").read_text())

    def test_pilule_avant_le_profil_d_energie_et_retiree_quand_coupee(self):
        with tempfile.TemporaryDirectory(prefix="nc-vpn-barre-") as d:
            nc, sortie = self.charger(d)
            appliquer = nc["appliquer_noctalia"]
            # Config du dépôt avec ses marqueurs remplis comme l'installeur
            conf = sortie.parent / "config.toml"
            conf.write_text(re.sub(r"@[A-Z0-9_]+@", "0", conf.read_text().replace("@ILE_CENTRE@", "").replace("@NOTIF_WIDGET@", "").replace("@PLUGIN_ILE@", "")))
            appliquer({})
            self.assertFalse(sortie.exists(), "rien de demandé : rien d'écrit")
            appliquer({"VPN_PILULE_BARRE": "oui"})
            fin = tomllib.loads(sortie.read_text())["bar"]["default"]["end"]
            self.assertEqual(fin, ["group:sys", "tray", "nc/vpn:vpn", "power_profile", "group:status"])
            # Avec la pastille système coupée : les deux réglages se combinent
            appliquer({"VPN_PILULE_BARRE": "oui", "BARRE_SYSTEME": "non"})
            self.assertEqual(tomllib.loads(sortie.read_text())["bar"]["default"]["end"], ["tray", "nc/vpn:vpn", "power_profile", "group:status"])
            appliquer({"VPN_PILULE_BARRE": "non"})
            self.assertFalse(sortie.exists(), "coupé : la barre redevient celle de l'installation")

    def test_masquer_tray_ecrit_la_liste_hidden_et_la_retire(self):
        with tempfile.TemporaryDirectory(prefix="nc-vpn-barre-") as d:
            nc, sortie = self.charger(d)
            appliquer = nc["appliquer_noctalia"]
            appliquer({"VPN_MASQUER_TRAY": "oui"})
            t = tomllib.loads(sortie.read_text())
            cache = t["widget"]["tray"]["hidden"]
            for ident in ("nordvpn-tray-white", "protonvpn-app", "mullvad-vpn"):
                self.assertIn(ident, cache)
            self.assertNotIn("pinned", t["widget"]["tray"])
            appliquer({"VPN_MASQUER_TRAY": "non"})
            self.assertFalse(sortie.exists(), "réglage coupé : liste retirée, rien n'est désinstallé")


class HyprlandFenetre(unittest.TestCase):
    def test_regle_limitee_au_titre_et_fenetre_exclue_de_la_memoire(self):
        harness = r'''
regles = {}
hl = setmetatable({ window_rule = function(r) regles[r.name] = r end, layer_rule = function() end },
                  { __index = function() return function() end end })
nc = setmetatable({ reglage = function(_, d) return d end }, { __index = function() return function() return "" end end })
dofile(FICHIER)
local r = regles["nc-vpn-fenetre"]
assert(r, "règle de la fenêtre VPN")
print(r.match.title, tostring(r.match.class), tostring(r.float), tostring(r.size), tostring(r.move))
'''.replace("FICHIER", json.dumps(str(REPO / "home/.config/hypr/nc/regles.lua")))
        r = subprocess.run(["lua", "-"], input=harness, text=True, capture_output=True, timeout=10, env=dict(PATH="/usr/bin:/bin"))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        titre, classe, flottante, taille, deplace = r.stdout.split()
        self.assertEqual((titre, classe, flottante, taille, deplace), ("^(VPN)$", "^(org.quickshell)$", "true", "nil", "nil"),
                         "flottante, limitée au titre exact et à Quickshell, ni size ni move (écrasés par la mémoire des fenêtres)")
        for titre_autre in ("VPN Manager", "NordVPN", "vpn", "Mon VPN"):
            self.assertNotRegex(titre_autre, "^(VPN)$")

    def lancer(self, corps, d):
        # Mêmes faux que tests/test_automatismes.py
        from tests import test_automatismes as A
        code = (A.ENTETE.replace("PROFIL", json.dumps("balanced")).replace("JEU", "false")
                .replace("FICHIER", json.dumps(str(A.LUA))) + corps)
        r = subprocess.run(["lua", "-"], input=code, text=True, capture_output=True, timeout=20,
                           env=dict(HOME=d, PATH="/usr/bin:/bin", XDG_RUNTIME_DIR=d, XDG_STATE_HOME=d + "/etat"))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return r.stdout.strip()

    @unittest.skipUnless(shutil.which("lua"), "Lua requis")
    def test_placement_a_l_ouverture_et_jamais_memorisee(self):
        with tempfile.TemporaryDirectory(prefix="nc-vpn-hypr-") as d:
            sortie = self.lancer(r'''
local appels = {}
local vrai_dispatch = hl.dispatch
hl.dispatch = function(x) appels[#appels + 1] = x end
hl.dsp = { window = { resize = function(t) return { r = t } end, move = function(t) return { m = t } end } }
nc.reserve = function() return { 0, 40, 0, 0 } end
local w = { class = "org.quickshell", title = "VPN", initial_title = "VPN", floating = true, address = "0x1",
  at = { x = 100, y = 100 }, size = { x = 300, y = 300 } }
emettre("window.open", w)
local r, m
for _, a in ipairs(appels) do r = r or a.r; m = m or a.m end
-- Écran 2000 x 1000 (faux hl), barre de 40 : zone utile 2000 x 960 ; 900 de large, 780 de haut (90 % de 960 = 864 > 780)
print(r.x, r.y, m.x, m.y, #appels)
-- À la fermeture : jamais mémorisée
emettre("window.close", w)
-- Un autre titre n'est pas touché
appels = {}
emettre("window.open", { class = "autre", title = "VPN Manager", initial_title = "VPN Manager", floating = true, address = "0x2" })
-- Une fenêtre d'une autre appli titrée « VPN » n'est pas touchée non plus
emettre("window.open", { class = "autre", title = "VPN", initial_title = "VPN", floating = true, address = "0x3" })
print(#appels)''', d)
            self.assertEqual(sortie.split("\n")[0].split(), ["900", "780", "550", "130", "2"])
            self.assertEqual(sortie.split("\n")[1], "0")
            self.assertFalse((Path(d) / "etat/noctalia-config/fenetres-flottantes").exists(), "la fenêtre VPN n'est jamais mémorisée")


if __name__ == "__main__":
    unittest.main()

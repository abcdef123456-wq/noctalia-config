"""Section de réglages « Santé Garmin » et pastille de barre Noctalia (plugin nc/garmin).
- 5 réglages ouinon, tous à non par défaut, dans la section « Santé Garmin » ; 4 actions à argv fixe.
- La pastille n'est insérée dans la barre que si GARMIN_ACTIF ET GARMIN_PILULE_BARRE sont à oui, et retirée sinon.
- Le widget (garmin.luau) tourne avec lua et un faux `noctalia` : caché sans fichier ou si « actif » est faux, clic exact, aucun réseau.
Tout est isolé (faux HOME) ; le vrai Noctalia, le vrai Hyprland ne sont jamais touchés."""
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
PLUGIN = REPO / "home/.local/share/noctalia/plugins/nc-garmin"
CONFIG = REPO / "home/.config/noctalia/config.toml"
NC_REGLAGES = REPO / "home/.local/bin/nc-reglages"
CLES = ("GARMIN_ACTIF", "GARMIN_PILULE_BARRE", "GARMIN_RESUME_MATIN", "GARMIN_DEMO", "GARMIN_JARVIS")

PRELUDE = r'''
local FICHIER = arg[1]
RUN = "/run/test"
ETAT, ETEINT = RUN .. "/nc-garmin-barre.json", RUN .. "/nc-ecran-eteint"
FILES, JSON, LECTURES, LANCES, VISIBLE, RENDU, BULLE, ECRITS = {}, {}, 0, {}, nil, nil, nil, {}
noctalia = {
  getenv = function(n) if n == "XDG_RUNTIME_DIR" then return RUN end end,
  pluginDataDir = function() return "/data" end, mkdirAll = function() return true end,
  fileExists = function(p) return FILES[p] ~= nil or ECRITS[p] ~= nil end,
  writeFile = function(p, c) ECRITS[p] = c; return true end,
  fileInfo = function(p) local f = FILES[p]; if not f then return nil, "absent" end; return { size = #f.texte, mtime = f.mtime, isDir = false } end,
  readFile = function(p) LECTURES = LECTURES + 1; local f = FILES[p]; return f and f.texte or nil end,
  json = { decode = function(s) return JSON[s] end },
  runAsync = function(argv, cb, t) LANCES[#LANCES + 1] = argv end,
  setUpdateInterval = function(ms) end,
}
barWidget = { render = function(t) RENDU = t end, setTooltip = function(t) BULLE = t end, setVisible = function(v) VISIBLE = v end }
local function noeud(k) return function(o, e) return { k = k, o = o or {}, e = e or {} } end end
ui = setmetatable({}, { __index = function(_, k) return noeud(k) end })
function chercher(n, test, r) r = r or {}; if test(n) then r[#r + 1] = n end; for _, e in ipairs(n.e or {}) do chercher(e, test, r) end; return r end
function textes(n) local t = {}; for _, x in ipairs(chercher(n, function(m) return m.k == "label" end)) do t[#t + 1] = x.o.text end; return t end
function egal(a, b, msg) if a ~= b then error((msg or "") .. " : attendu " .. tostring(b) .. ", obtenu " .. tostring(a), 2) end end
function poser(etat, mtime)
  local texte = "etat" .. tostring(mtime)
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
            r = subprocess.run(["lua", str(h), str(PLUGIN / "garmin.luau")], text=True, capture_output=True, timeout=10)
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)

    def test_cache_sans_fichier_ou_si_actif_est_faux(self):
        self.lua(r'''
charger()
egal(VISIBLE, false, "caché sans fichier")
onClick(); egal(#LANCES, 0, "caché : aucune zone de clic")
poser({ actif = false, metriques = {} }, 100)
update(); egal(VISIBLE, false, "actif faux : caché")
onClick(); egal(#LANCES, 0)
poser({ actif = true, metriques = { body_battery = 74 } }, 101)
update(); egal(VISIBLE, true)
FILES[ETAT] = nil
update(); egal(VISIBLE, false, "fichier retiré : caché de nouveau")
''')

    def test_coeur_body_battery_et_clic_exact(self):
        self.lua(r'''
poser({ actif = true, metriques = { body_battery = 74 } }, 100)
charger()
egal(VISIBLE, true)
local t = textes(RENDU); egal(#t, 1); egal(t[1], "74")
local imgs = chercher(RENDU, function(n) return n.k == "image" end)
egal(#imgs, 1, "le cœur maison")
assert(ECRITS[imgs[1].o.path]:find("<svg"), "cœur écrit en SVG")
onClick(); egal(#LANCES, 1)
egal(table.concat(LANCES[1], " "), "qs -c nc-ile ipc call ile garmin")
''')

    def test_lecture_seulement_si_le_fichier_change_et_ecran_allume(self):
        self.lua(r'''
poser({ actif = true, metriques = { body_battery = 74 } }, 100)
charger(); egal(LECTURES, 1)
for i = 1, 5 do update() end
egal(LECTURES, 1, "inchangé : aucune relecture")
FILES[ETEINT] = { texte = "", mtime = 1 }
poser({ actif = true, metriques = { body_battery = 50 } }, 200)
update(); egal(LECTURES, 1, "écran éteint : rien lu")
FILES[ETEINT] = nil
update(); egal(textes(RENDU)[1], "50")
''')

    def test_aucun_reseau_et_un_seul_lancement(self):
        src = (PLUGIN / "garmin.luau").read_text()
        code = re.sub(r"--[^\n]*", "", src).replace("http://www.w3.org/2000/svg", "").lower()
        for interdit in ("http", "curl", "wget", "garmin.com", "download"):
            self.assertNotIn(interdit, code, interdit)
        self.assertEqual(src.count("runAsync"), 1)
        self.assertIn('{ "qs", "-c", "nc-ile", "ipc", "call", "ile", "garmin" }', src)

    def test_syntaxe_luau_simple(self):
        if shutil.which("luac"):
            subprocess.run(["luac", "-p", str(PLUGIN / "garmin.luau")], check=True)


class Configuration(unittest.TestCase):
    def charger(self, d):
        home = Path(d)
        (home / ".config/noctalia").mkdir(parents=True)
        (home / "tmp").mkdir()
        conf = (home / ".config/noctalia/config.toml")
        conf.write_text(re.sub(r"@[A-Z0-9_]+@", "0", CONFIG.read_text().replace("@ILE_CENTRE@", "").replace("@NOTIF_WIDGET@", "").replace("@PLUGIN_ILE@", "")))
        env = dict(HOME=str(home), XDG_CONFIG_HOME=str(home / ".config"), XDG_DATA_HOME=str(home / ".local/share"),
                   XDG_STATE_HOME=str(home / ".local/state"), XDG_CACHE_HOME=str(home / ".cache"), TMPDIR=str(home / "tmp"), NC_LANGUE="fr")
        with patch.dict(os.environ, env), warnings.catch_warnings():
            warnings.simplefilter("ignore", ResourceWarning)
            nc = runpy.run_path(str(NC_REGLAGES))
        faux = type("S", (), {k: getattr(subprocess, k) for k in dir(subprocess) if not k.startswith("__")})
        faux.run = staticmethod(lambda *a, **k: subprocess.CompletedProcess(a, 0, "", ""))
        nc["appliquer_noctalia"].__globals__["subprocess"] = faux
        return nc, home / ".config/noctalia/zy-reglages.toml"

    def test_manifeste_et_export(self):
        m = tomllib.loads((PLUGIN / "plugin.toml").read_text())
        self.assertEqual(m["id"], "nc/garmin")
        self.assertLessEqual(m["plugin_api"], 32)
        self.assertEqual([w["id"] for w in m["widget"]], ["garmin"])
        self.assertIn(".local/share/noctalia/plugins/nc-garmin", (REPO / "export.sh").read_text())
        self.assertNotIn("nc/garmin:garmin", CONFIG.read_text().split("[bar.default]")[1].split("[[bar")[0])

    def test_cinq_reglages_non_par_defaut_section_sante_garmin(self):
        with tempfile.TemporaryDirectory(prefix="nc-garmin-reg-") as d:
            nc, _ = self.charger(d)
            for cle in CLES:
                r = nc["PAR_CLE"][cle]
                self.assertEqual((r.section, r.genre, r.defaut), ("Santé Garmin", "ouinon", "non"), cle)
                self.assertTrue(r.aide, cle)
            self.assertIn("non officiel", nc["PAR_CLE"]["GARMIN_ACTIF"].aide.lower())
            self.assertEqual(nc["PAR_CLE"]["GARMIN_PILULE_BARRE"].groupe, "noctalia")
            self.assertIn('section: "Santé Garmin"', (REPO / "home/.config/quickshell/nc-ile/Garmin.qml").read_text())

    def test_actions_a_argv_fixe(self):
        with tempfile.TemporaryDirectory(prefix="nc-garmin-reg-") as d:
            nc, _ = self.charger(d)
            lignes = {l["cle"]: l for l in nc["catalogue"]({})}
            attendu = {"GARMIN_ACTION_CONNECTER": ["nc-garmin", "login"], "GARMIN_ACTION_DECONNECTER": ["nc-garmin", "logout"],
                       "GARMIN_ACTION_RETIRER": ["nc-garmin", "desinstaller"]}
            for cle, argv in attendu.items():
                self.assertEqual(lignes[cle]["commande"], argv, cle)
                self.assertEqual((lignes[cle]["genre"], lignes[cle]["section"], lignes[cle]["relire"]), ("action", "Santé Garmin", True))
            self.assertTrue(lignes["GARMIN_ACTION_RETIRER"]["confirmer"])
            inst = lignes["GARMIN_ACTION_INSTALLER"]["commande"]
            self.assertIn("--texte", " ".join(inst))  # sortie en phrases, pas en JSON
            if len(inst) > 4:  # avec un terminal : il reste ouvert jusqu'à Entrée
                self.assertIn("read r", inst[-2])
                self.assertIn("nc-garmin installer --texte", inst[-2])
            else:
                self.assertEqual(inst, ["nc-garmin", "installer", "--texte"])
            for l in lignes.values():
                if l["cle"].startswith("GARMIN_ACTION"):
                    self.assertIsInstance(l["commande"], list)

    def test_pilule_seulement_si_actif_et_pilule_et_retiree_sinon(self):
        with tempfile.TemporaryDirectory(prefix="nc-garmin-reg-") as d:
            nc, sortie = self.charger(d)
            appliquer = nc["appliquer_noctalia"]

            def fin():
                return tomllib.loads(sortie.read_text())["bar"]["default"]["end"] if sortie.exists() else None
            appliquer({"GARMIN_PILULE_BARRE": "oui"})
            self.assertNotIn("nc/garmin:garmin", fin() or [], "sans GARMIN_ACTIF : pas de pastille")
            appliquer({"GARMIN_ACTIF": "oui"})
            self.assertNotIn("nc/garmin:garmin", fin() or [], "sans GARMIN_PILULE_BARRE : pas de pastille")
            appliquer({"GARMIN_ACTIF": "oui", "GARMIN_PILULE_BARRE": "oui"})
            f = fin()
            self.assertEqual(f[f.index("nc/garmin:garmin") + 1], "power_profile")
            appliquer({"GARMIN_ACTIF": "non", "GARMIN_PILULE_BARRE": "oui"})
            self.assertNotIn("nc/garmin:garmin", fin() or [], "retirée")


if __name__ == "__main__":
    unittest.main()

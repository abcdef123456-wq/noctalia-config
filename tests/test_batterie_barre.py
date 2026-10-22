"""Batterie de la barre (plugin nc/batterie, à la place du widget battery de Noctalia) : la consommation réelle au survol.
Le calcul (unités du noyau, lissage sur 5 s, temps restant en charge ou en décharge, textes) et le widget (lecture
tout de suite au survol puis chaque seconde, 30 s au repos, caché sans batterie, couleur d'alerte) tournent avec lua
sur un faux /sys/class/power_supply ; la config de la barre et export.sh sont vérifiés à part."""
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import tomllib
import unittest

REPO = Path(__file__).resolve().parents[1]
PLUGIN = REPO / "home/.local/share/noctalia/plugins/nc-batterie"
CONFIG = REPO / "home/.config/noctalia/config.toml"

PRELUDE = r'''
local DIR = arg[1]
local modules = {}
function require(nom)
  local f = DIR .. "/" .. string.gsub(nom, "^%./", "")
  if not modules[f] then modules[f] = dofile(f) end
  return modules[f]
end
calc = require("./calcul.luau")

-- Faux sysfs : SYSFS[nom] = texte du fichier uevent
SYSFS, HORLOGE, ASYNC, INTERVALLES, LECTURES = {}, 0, {}, {}, 0
LANGUE, SEUIL_CONF, VERTICAL = "fr", nil, false
RENDU, BULLE, VISIBLE = nil, nil, nil
function uevent(t)
  local l = {}
  for k, v in pairs(t) do l[#l + 1] = "POWER_SUPPLY_" .. k .. "=" .. tostring(v) end
  table.sort(l)
  return "DEVTYPE=power_supply\n" .. table.concat(l, "\n") .. "\n"
end
noctalia = {
  getenv = function(n) if n == "NC_LANGUE" then return LANGUE end end,
  expandPath = function(p) return p end,
  readFile = function(p)
    local n = string.match(p, "^/sys/class/power_supply/([^/]+)/uevent$")
    if n then LECTURES = LECTURES + 1; return SYSFS[n] end
    return nil
  end,
  readFileAsync = function(p, cb) ASYNC[#ASYNC + 1] = function() cb(noctalia.readFile(p)) end; return true end,
  listDir = function(p)
    assert(p == "/sys/class/power_supply", p)
    local t = { "ADP0", "ucsi-source-psy-USBC000:001" }
    for n in pairs(SYSFS) do t[#t + 1] = n end
    return t
  end,
  nowMs = function() return HORLOGE end,
  setUpdateInterval = function(ms) INTERVALLES[#INTERVALLES + 1] = ms end,
  getSetting = function(k) if k == "battery.warning_threshold" then return SEUIL_CONF end end,
}
function vider() local a = ASYNC; ASYNC = {}; for _, f in ipairs(a) do f() end end
function cadence() return INTERVALLES[#INTERVALLES] end
barWidget = {
  render = function(t) RENDU = t end, setTooltip = function(t) BULLE = t end,
  setVisible = function(v) VISIBLE = v end, isVertical = function() return VERTICAL end,
}
local function noeud(k) return function(o, e) return { k = k, o = o or {}, e = e or {} } end end
ui = setmetatable({}, { __index = function(_, k) return noeud(k) end })
function chercher(n, test, r)
  r = r or {}
  if test(n) then r[#r + 1] = n end
  for _, e in ipairs(n.e or {}) do chercher(e, test, r) end
  return r
end
function egal(a, b, msg) if a ~= b then error((msg or "") .. " : attendu " .. tostring(b) .. ", obtenu " .. tostring(a), 2) end end
function proche(a, b, msg) if math.abs(a - b) > 1e-6 then error((msg or "") .. " : attendu " .. b .. ", obtenu " .. tostring(a), 2) end end
function charger() dofile(DIR .. "/batterie.luau") end
DECHARGE = { STATUS = "Discharging", CAPACITY = 60, ENERGY_NOW = 44820000, ENERGY_FULL = 74690000,
  VOLTAGE_NOW = 15435000, POWER_NOW = 32000000 }
'''


@unittest.skipUnless(shutil.which("lua"), "Lua requis")
class Calcul(unittest.TestCase):
    def lua(self, code):
        with tempfile.TemporaryDirectory() as d:
            h = Path(d) / "harnais.lua"
            h.write_text(PRELUDE + code)
            r = subprocess.run(["lua", str(h), str(PLUGIN)], text=True, capture_output=True, timeout=10)
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        return r.stdout

    def test_unites_energie_et_puissance(self):
        self.lua(r'''
-- µW et µWh
local b = calc.batterie(calc.lireUevent(uevent({ STATUS = "Discharging", CAPACITY = 60, ENERGY_NOW = 44820000,
  ENERGY_FULL = 74690000, POWER_NOW = 40000000 })))
proche(b.puissance, 40, "power_now en µW"); proche(b.energie, 44.82, "energy_now en µWh"); proche(b.pleine, 74.69)
egal(b.pct, 60); egal(b.statut, "Discharging")
-- µA × µV, charge en µAh × tension ; courant négatif en décharge (certains pilotes)
b = calc.batterie(calc.lireUevent(uevent({ STATUS = "Discharging", CAPACITY = 60, CURRENT_NOW = -2600000,
  VOLTAGE_NOW = 15400000, CHARGE_NOW = 2900000, CHARGE_FULL = 4850000 })))
proche(b.puissance, 2.6 * 15.4, "current_now × voltage_now"); proche(b.energie, 2.9 * 15.4, "charge_now × voltage_now")
proche(b.pleine, 4.85 * 15.4)
-- Sans tension mesurée : la tension nominale
b = calc.batterie(calc.lireUevent(uevent({ STATUS = "Discharging", CAPACITY = 50, CHARGE_NOW = 2000000,
  VOLTAGE_MIN_DESIGN = 15000000, CURRENT_NOW = 1000000 })))
proche(b.energie, 30); proche(b.puissance, 15)
''')

    def test_deux_batteries_et_statut(self):
        self.lua(r'''
local r = calc.resumer({
  calc.lireUevent(uevent({ STATUS = "Discharging", CAPACITY = 80, ENERGY_NOW = 40000000, ENERGY_FULL = 50000000, POWER_NOW = 10000000 })),
  calc.lireUevent(uevent({ STATUS = "Not charging", CAPACITY = 20, ENERGY_NOW = 5000000, ENERGY_FULL = 25000000, POWER_NOW = 0 })),
})
egal(r.statut, "Discharging"); proche(r.energie, 45); proche(r.pleine, 75); proche(r.puissance, 10); proche(r.pct, 60)
r = calc.resumer({ calc.lireUevent(uevent({ STATUS = "Full", CAPACITY = 100 })), calc.lireUevent(uevent({ STATUS = "Charging", CAPACITY = 90 })) })
egal(r.statut, "Charging"); proche(r.pct, 95)
egal(calc.resumer({}), nil); egal(calc.resumer({ calc.lireUevent("") }), nil)
''')

    def test_lissage_sur_cinq_secondes(self):
        self.lua(r'''
local e = {}
proche(calc.lisser(e, 0, 30), 30)
proche(calc.lisser(e, 1000, 40), 35)
proche(calc.lisser(e, 2000, 50), 40)
-- À 5,5 s, la mesure de 0 s a plus de 5 s : oubliée ; à 6 s, celle de 1 s aussi
proche(calc.lisser(e, 5500, 60), (40 + 50 + 60) / 3)
proche(calc.lisser(e, 6000, nil), (50 + 60) / 2)
-- Au repos (30 s entre deux lectures) : seulement la dernière mesure
proche(calc.lisser(e, 36000, 20), 20)
-- Sans mesure de puissance : la moyenne de ce qui reste, puis plus rien
proche(calc.lisser(e, 37000, nil), 20)
egal(calc.lisser(e, 42000, nil), nil)
''')

    def test_temps_restant_et_textes(self):
        self.lua(r'''
local d = { statut = "Discharging", pct = 60, energie = 52, pleine = 74.69 }
proche(calc.restant(d, 40), 52 / 40 * 3600, "décharge : énergie restante / puissance")
egal(calc.infobulle(d, 40, false), "40,0 W · 1 h 18 restantes")
egal(calc.infobulle(d, 40, true), "40.0 W · 1 h 18 left")
local c = { statut = "Charging", pct = 60, energie = 29.5, pleine = 75 }
proche(calc.restant(c, 65), (75 - 29.5) / 65 * 3600, "charge : énergie manquante / puissance")
egal(calc.infobulle(c, 65, false), "+65 W · pleine dans 42 min")
egal(calc.infobulle(c, 65, true), "+65 W · full in 42 min")
egal(calc.infobulle({ statut = "Discharging", pct = 60, energie = 0.6, pleine = 70 }, 40, false), "40,0 W · 1 min restante")
egal(calc.infobulle({ statut = "Discharging", pct = 60, energie = 52 }, nil, false), "60 %")
egal(calc.infobulle({ statut = "Full", pct = 100, energie = 75, pleine = 75 }, 0, false), "Pleine · branchée")
egal(calc.infobulle({ statut = "Full", pct = 100 }, 0, true), "Full · plugged in")
egal(calc.restant({ statut = "Full", energie = 75, pleine = 75 }, 3), nil)
egal(calc.restant(d, 0), nil, "puissance nulle : pas de temps")
egal(calc.duree(3 * 24 * 3600), nil, "plus de deux jours : pas de temps")
egal(calc.duree(3720), "1 h 02")
egal(calc.glyphe("Charging"), "bolt-filled"); egal(calc.glyphe("Full"), "plug-filled")
egal(calc.glyphe("Not charging"), "plug-filled"); egal(calc.glyphe("Discharging"), nil)
''')

    def test_widget_survol_repos_et_lissage(self):
        self.lua(r'''
SYSFS.BAT0 = uevent(DECHARGE)
charger()
egal(cadence(), 30000, "au repos : toutes les 30 s")
vider()
egal(VISIBLE, true); egal(BULLE, "32,0 W · 1 h 24 restantes")
-- Rendu du mode graphic : corps 25 × 15, remplissage à 60 %, chiffre par-dessus (écart négatif), borne 3 × 7
local corps = chercher(RENDU, function(n) return n.o.fill == "surface" end)[1]
egal(corps.o.width, 25); egal(corps.o.height, 15); egal(corps.o.gap, -25); egal(corps.o.radius, 4)
local plein = chercher(RENDU, function(n) return n.k == "box" and n.o.fill == "on_surface" and n.o.height == 15 end)[1]
proche(plein.o.width, 15, "remplissage à 60 %")
egal(chercher(RENDU, function(n) return n.k == "row" and n.o.fill == "on_surface/0.65" end)[1].o.width, 25)
local chiffre = chercher(RENDU, function(n) return n.k == "label" end)[1]
egal(chiffre.o.text, "60"); egal(chiffre.o.color, "surface")
egal(#chercher(RENDU, function(n) return n.k == "box" and n.o.width == 3 and n.o.height == 7 end), 1, "borne")
egal(#chercher(RENDU, function(n) return n.k == "glyph" end), 0, "en décharge : pas d'icône")
-- Survol : lecture immédiate, puis chaque seconde ; la mesure de 30 s plus tôt ne compte plus
HORLOGE = 60000
SYSFS.BAT0 = uevent((function() local t = {} for k, v in pairs(DECHARGE) do t[k] = v end t.POWER_NOW = 40000000 return t end)())
local avant = LECTURES
onHover(true)
egal(cadence(), 1000, "au survol : chaque seconde")
vider()
egal(LECTURES, avant + 1, "lecture tout de suite")
egal(BULLE, "40,0 W · 1 h 07 restantes")
-- Moyenne glissante sur 5 s
HORLOGE = 61000
SYSFS.BAT0 = string.gsub(SYSFS.BAT0, "POWER_NOW=%d+", "POWER_NOW=50000000")
update(); vider()
egal(string.sub(BULLE, 1, 6), "45,0 W", BULLE)
for t = 62000, 66000, 1000 do HORLOGE = t; update(); vider() end
egal(string.sub(BULLE, 1, 6), "50,0 W", BULLE)
onHover(false)
egal(cadence(), 30000, "souris partie : retour aux 30 s")
''')

    def test_widget_charge_alerte_et_pc_fixe(self):
        self.lua(r'''
SYSFS.BAT0 = uevent({ STATUS = "Charging", CAPACITY = 40, ENERGY_NOW = 29500000, ENERGY_FULL = 75000000, POWER_NOW = 65000000 })
charger(); vider()
egal(BULLE, "+65 W · pleine dans 42 min")
egal(chercher(RENDU, function(n) return n.k == "glyph" end)[1].o.name, "bolt-filled")
-- Passage en décharge : les mesures de la charge sont oubliées
HORLOGE = 1000
SYSFS.BAT0 = uevent({ STATUS = "Discharging", CAPACITY = 8, ENERGY_NOW = 6000000, ENERGY_FULL = 75000000, POWER_NOW = 20000000 })
update(); vider()
egal(BULLE, "20,0 W · 18 min restantes")
-- Sous le seuil de Noctalia (10 %) et sur batterie : couleur d'alerte (error)
egal(#chercher(RENDU, function(n) return n.o.fill == "error" end), 2, "remplissage et borne en couleur d'alerte")
egal(#chercher(RENDU, function(n) return n.o.fill == "error/0.65" end), 1)
-- Branchée sous le seuil : pas d'alerte, comme Noctalia
HORLOGE = 2000
SYSFS.BAT0 = uevent({ STATUS = "Charging", CAPACITY = 8, ENERGY_NOW = 6000000, ENERGY_FULL = 75000000, POWER_NOW = 20000000 })
update(); vider()
egal(#chercher(RENDU, function(n) return n.o.fill == "error" end), 0)
-- Pleine : prise à côté
SYSFS.BAT0 = uevent({ STATUS = "Full", CAPACITY = 100, ENERGY_NOW = 75000000, ENERGY_FULL = 75000000, POWER_NOW = 0 })
update(); vider()
egal(chercher(RENDU, function(n) return n.k == "glyph" end)[1].o.name, "plug-filled")
egal(chercher(RENDU, function(n) return n.k == "label" end)[1].o.text, "100")
-- La batterie disparaît (PC fixe) : widget caché, lecture espacée
SYSFS = {}
update(); vider()
egal(VISIBLE, false); egal(cadence(), 300000)
''')

    def test_widget_microamperes_anglais_et_seuil_de_la_config(self):
        self.lua(r'''
LANGUE, SEUIL_CONF = "en", 15
SYSFS.BAT1 = uevent({ STATUS = "Discharging", CAPACITY = 12, CURRENT_NOW = 2600000, VOLTAGE_NOW = 15400000,
  CHARGE_NOW = 2900000, CHARGE_FULL = 4850000 })
charger(); vider()
egal(BULLE, "40.0 W · 1 h 07 left")
egal(#chercher(RENDU, function(n) return n.o.fill == "error" end), 2, "12 % sous le seuil de 15 % de config.toml")
''')

    def test_widget_pc_fixe_des_le_depart(self):
        self.lua(r'''
charger(); vider()
egal(VISIBLE, false); egal(RENDU, nil); egal(LECTURES, 0); egal(cadence(), 300000)
''')

    def test_barre_verticale(self):
        self.lua(r'''
VERTICAL = true
SYSFS.BAT0 = uevent(DECHARGE)
charger(); vider()
local corps = chercher(RENDU, function(n) return n.o.fill == "surface" end)[1]
egal(corps.k, "column"); egal(corps.o.width, 18); egal(corps.o.height, 23); egal(corps.o.gap, -23)
egal(RENDU.k, "column"); egal(RENDU.e[1].o.width, 7, "borne en haut")
''')


class Configuration(unittest.TestCase):
    def test_capsule_status_et_clic(self):
        texte = CONFIG.read_text()
        # Marqueurs remplis comme install.sh le ferait (valeurs quelconques mais valides en TOML)
        valeurs = {"POLKIT": "true", "NOTIF_NOCTALIA": "false", "LCX": "0"}
        conf = tomllib.loads(re.sub(r"@([A-Z_]+)[0-9]*@", lambda m: valeurs.get(m.group(1), "0" if m.group(1) == "LCY" else ""),
                                    texte))
        groupes = {g["id"]: g["members"] for g in conf["bar"]["default"]["capsule_group"]}
        self.assertEqual(groupes["status"], ["network", "bluetooth", "volume", "nc/batterie:batterie"])
        self.assertNotIn("battery", conf["widget"], "l'ancien widget battery n'est plus utilisé")
        self.assertEqual(conf["widget"]["nc/batterie:batterie"]["actions"]["left"],
                         "exec /.local/bin/nc-shell-msg ile systeme")
        self.assertIn("nc/batterie", conf["plugins"]["enabled"])
        manifeste = tomllib.loads((PLUGIN / "plugin.toml").read_text())
        self.assertEqual(manifeste["id"], "nc/batterie")
        self.assertEqual([(w["id"], w["entry"]) for w in manifeste["widget"]], [("batterie", "batterie.luau")])
        self.assertTrue((PLUGIN / "batterie.luau").is_file())

    def test_seulement_le_sysfs(self):
        # Toutes distributions : rien d'UPower, d'upower, de busctl ni d'acpi ; seulement /sys/class/power_supply
        for f in PLUGIN.glob("*.luau"):
            code = "\n".join(l for l in f.read_text().splitlines() if not l.lstrip().startswith("--"))
            self.assertNotRegex(code, r"(?i)upower|busctl|acpi|runAsync|runStream", f.name)

    def test_export(self):
        script = (REPO / "export.sh").read_text()
        self.assertIn(".local/share/noctalia/plugins/nc-batterie\n", script)
        ligne = next(l for l in script.splitlines() if "@PLUGIN_ILE@" in l and l.startswith("sed "))
        with tempfile.TemporaryDirectory() as d:
            conf = Path(d) / "home/.config/noctalia/config.toml"
            conf.parent.mkdir(parents=True)
            for avec in ("", ', "nc/ile"'):
                with self.subTest(ile=avec):
                    conf.write_text('[plugins]\nenabled = ["nc/launcher", "nc/fenetres", "nc/batterie"' + avec + "]\n")
                    subprocess.run(["bash", "-c", ligne], cwd=d, check=True)
                    self.assertIn('enabled = ["nc/launcher", "nc/fenetres", "nc/batterie"@PLUGIN_ILE@]', conf.read_text())


if __name__ == "__main__":
    unittest.main()

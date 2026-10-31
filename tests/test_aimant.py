"""Aimantation des fenêtres (nc/aimant.lua) : zones (fonction pure), suivi par minuteur, rangement au relâchement,
raccourcis sans mouse (comme Hyprland 0.57) et réglages. Faux `hl` et faux `nc`, jamais le vrai Hyprland ni le vrai qs."""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

RACINE = Path(__file__).resolve().parents[1]
HYPR = RACINE / "home/.config/hypr"
MODULE = HYPR / "nc/aimant.lua"

# Faux hl et nc pour le module seul : tout ce qu'il fait est noté dans `trace` ; l'heure est fausse (TEMPS)
HARNAIS = r'''
trace, TEMPS, REG, MONS, CURSEUR, WIN = {}, 0, {}, {}, { x = 0, y = 0 }, nil
os.time = function() return TEMPS end
local function noter(s) trace[#trace + 1] = s end
local function plan(nom) return function(t)
  local p = { nom }
  if t.mode then p[#p + 1] = t.mode elseif t.action then p[#p + 1] = t.action end
  if t.x then p[#p + 1] = t.x; p[#p + 1] = t.y end
  return table.concat(p, " ")
end end
hl = {
  get_monitors = function() return MONS end,
  get_cursor_pos = function() return { x = CURSEUR.x, y = CURSEUR.y } end,
  get_active_window = function() return WIN end,
  exec_cmd = function(c) noter("exec " .. c) end,
  dispatch = function(d) noter(d) end,
  timer = function(f, o)
    noter("timer-cree " .. o.timeout .. " " .. o.type)
    PAS = f
    return { set_enabled = function(self, b) noter("actif " .. tostring(b)) end }
  end,
  dsp = { window = { float = plan("float"), fullscreen = plan("plein"), resize = plan("taille"), move = plan("place") } },
}
nc = { reglage = function(c, d) if REG[c] ~= nil then return REG[c] end return d end,
       reserve = function(m) return m.reserved or {} end }
AIMANT = dofile(MODULE)
function ecran(x, y, w, h, haut) return { x = x, y = y, w = w, h = h, reserve = { left = 0, top = haut or 0, right = 0, bottom = 0 } } end
function dire(...) print(...) end
function z(px, py, ecrans)
  local nom, r = AIMANT.zone(px, py, ecrans, 40, 110, 10)
  if not nom then return "nil" end
  return nom .. " " .. r.x .. " " .. r.y .. " " .. r.w .. " " .. r.h
end
'''


def lua(script, extra=""):
    code = ("MODULE = %s\n" % json.dumps(str(MODULE))) + HARNAIS + extra + script
    r = subprocess.run(["lua", "-"], input=code, text=True, capture_output=True, timeout=20,
                       env=dict(PATH="/usr/bin:/bin", HOME="/home/user"))
    assert r.returncode == 0, r.stdout + r.stderr
    return r.stdout.splitlines()


@unittest.skipUnless(shutil.which("lua"), "Lua requis")
class Zones(unittest.TestCase):
    def test_un_ecran(self):
        # 1920 x 1080, barre de 40 en haut, marge 10 : zone utile x 10..1910, y 50..1070 ; moitié = 945
        s = 'local E = { ecran(0, 0, 1920, 1080, 40) }\n'
        sorties = lua(s + '''
for _, p in ipairs({ {0,500}, {1919,500}, {960,0}, {5,5}, {1915,3}, {3,1078}, {1915,1075}, {960,540}, {960,1078},
                     {60,60}, {3,100}, {3,200}, {40,500}, {41,500}, {960,40}, {960,41} }) do dire(p[1], p[2], z(p[1], p[2], E)) end
''')
        attendu = {
            "0 500": "gauche 10 50 945 1020", "1919 500": "droite 965 50 945 1020", "960 0": "haut 10 50 1900 1020",
            "5 5": "haut-gauche 10 50 945 505", "1915 3": "haut-droite 965 50 945 505",
            "3 1078": "bas-gauche 10 565 945 505", "1915 1075": "bas-droite 965 565 945 505",
            "960 540": "nil", "960 1078": "nil", "60 60": "nil", "3 100": "haut-gauche 10 50 945 505",
            "3 200": "gauche 10 50 945 1020", "40 500": "gauche 10 50 945 1020", "41 500": "nil",
            "960 40": "haut 10 50 1900 1020", "960 41": "nil",
        }
        lues = {" ".join(l.split("\t")[:2]).replace("\t", " "): l.split("\t")[2] for l in sorties}
        self.assertEqual(lues, attendu)

    def test_echelle_1_6_en_points_logiques(self):
        # 3072 x 1920 pixels à l'échelle 1,6 = 1920 x 1200 points : les seuils sont en points, pas en pixels
        sorties = lua('''
MONS = { { name = "A", x = 0, y = 0, width = 3072, height = 1920, scale = 1.6, reserved = {} } }
for _, px in ipairs({ 39, 41 }) do
  CURSEUR = { x = px, y = 600 }; WIN = { floating = true, address = "0xab" }
  AIMANT.presse(); CURSEUR = { x = px, y = 600 }
  trace = {}; AIMANT.relache()
  dire(px, table.concat(trace, "|"))
end
''', 'REG.AIMANT_APERCU = false\n')
        # départ = arrivée : un simple clic ne range rien ; on teste donc avec un vrai déplacement ci-dessous
        self.assertEqual([l.split("\t")[1] for l in sorties], ["", ""])
        sorties = lua('''
MONS = { { name = "A", x = 0, y = 0, width = 3072, height = 1920, scale = 1.6, reserved = {} } }
for _, px in ipairs({ 39, 41 }) do
  CURSEUR = { x = 900, y = 600 }; WIN = { floating = true, address = "0xab" }
  AIMANT.presse(); CURSEUR = { x = px, y = 600 }
  trace = {}; AIMANT.relache()
  dire(px, table.concat(trace, "|"))
end
''', 'REG.AIMANT_APERCU = false\n')
        self.assertEqual(sorties[0].split("\t")[1], "taille 945 1180|place 10 10")
        self.assertEqual(sorties[1].split("\t")[1], "")

    def test_ecran_tourne_en_portrait(self):
        # 1920 x 1080 tourné d'un quart de tour (transform 1 ou 3) : 1080 de large, 1920 de haut ; transform 2 : inchangé
        sorties = lua('''
for _, t in ipairs({ 1, 3, 2 }) do
  MONS = { { name = "A", x = 0, y = 0, width = 1920, height = 1080, scale = 1, transform = t, reserved = {} } }
  CURSEUR = { x = 500, y = 900 }; WIN = { floating = true, address = "0xab" }
  AIMANT.presse(); CURSEUR = { x = 1060, y = 900 }
  trace = {}; AIMANT.relache()
  dire(t, table.concat(trace, "|"))
end
''', 'REG.AIMANT_APERCU = false\n')
        self.assertEqual([l.split("\t")[1] for l in sorties],
                         ["taille 525 1900|place 545 10", "taille 525 1900|place 545 10", ""])

    def test_deux_ecrans_cote_a_cote(self):
        s = 'local E = { ecran(0, 0, 1920, 1080), ecran(1920, 0, 1920, 1080) }\n'
        sorties = lua(s + '''
for _, p in ipairs({ {0,500}, {1919,500}, {1920,500}, {3839,500}, {1919.5,500}, {1900,2}, {1925,2}, {2500,0} }) do
  dire(p[1], p[2], z(p[1], p[2], E))
end
''')
        res = {" ".join(l.split("\t")[:2]): l.split("\t")[2].split(" ")[0] for l in sorties}
        self.assertEqual(res, {"0 500": "gauche", "1919 500": "nil", "1920 500": "nil", "3839 500": "droite",
                               "1919.5 500": "nil", "1900 2": "haut", "1925 2": "haut", "2500 0": "haut"})

    def test_ecrans_de_tailles_differentes_et_decales(self):
        # A : 1920 x 1080 en (0,0) ; B : 2560 x 1440 en (1920,200). Le bord commun n'existe que sur y 200..1080
        s = 'local E = { ecran(0, 0, 1920, 1080), ecran(1920, 200, 2560, 1440) }\n'
        sorties = lua(s + '''
for _, p in ipairs({ {1919,150}, {1919,500}, {1920,500}, {1920,1200}, {2000,200}, {1000,1079}, {1919,1078} }) do
  dire(p[1], p[2], z(p[1], p[2], E))
end
''')
        res = {" ".join(l.split("\t")[:2]): l.split("\t")[2].split(" ")[0] for l in sorties}
        self.assertEqual(res["1919 150"], "droite", "au-dessus de B, le bord droit de A est extérieur")
        self.assertEqual(res["1919 500"], "nil")
        self.assertEqual(res["1920 500"], "nil")
        self.assertEqual(res["1920 1200"], "gauche", "sous A, le bord gauche de B est extérieur")
        self.assertEqual(res["2000 200"], "haut")
        self.assertEqual(res["1000 1079"], "nil", "le bas seul n'aimante pas")
        self.assertEqual(res["1919 1078"], "nil")


@unittest.skipUnless(shutil.which("lua"), "Lua requis")
class Suivi(unittest.TestCase):
    ECRAN = 'MONS = { { name = "A", x = 0, y = 0, width = 1920, height = 1080, scale = 1, reserved = {} } }\n'

    def test_minuteur_arme_au_appui_arrete_au_relachement(self):
        sorties = lua(self.ECRAN + '''
dire("charge", #trace)
CURSEUR = { x = 900, y = 500 }; WIN = { floating = true, address = "0xab" }
AIMANT.presse()
dire("presse", table.concat(trace, "|"))
trace = {}
CURSEUR = { x = 2, y = 500 }; PAS()       -- gauche
PAS()                                      -- même zone : rien de plus
CURSEUR = { x = 960, y = 500 }; PAS()      -- plus de zone
dire("pas", table.concat(trace, "|"))
trace = {}
AIMANT.relache()
dire("relache", table.concat(trace, "|"))
trace = {}
AIMANT.presse()
dire("2e", table.concat(trace, "|"))
''')
        self.assertEqual(sorties[0], "charge\t0", "rien créé au chargement")
        self.assertEqual(sorties[1], "presse\ttimer-cree 50 repeat|actif true")
        self.assertEqual(sorties[2], "pas\texec qs -c nc-ile ipc call ile aimant gauche 10 10 945 1060"
                         "|exec qs -c nc-ile ipc call ile aimant \"\" 0 0 0 0", "une commande par changement de zone")
        self.assertEqual(sorties[3], "relache\tactif false", "arrêt ; rien à effacer (zone déjà vide), pas de rangement")
        self.assertEqual(sorties[4], "2e\tactif true", "le même objet minuteur est réutilisé")

    def test_relache_efface_l_apercu_si_zone(self):
        sorties = lua(self.ECRAN + '''
CURSEUR = { x = 900, y = 500 }; WIN = { floating = true, address = "0xab" }
AIMANT.presse(); CURSEUR = { x = 0, y = 500 }; PAS(); trace = {}
AIMANT.relache()
dire(table.concat(trace, "|"))
''')
        self.assertEqual(sorties[0], 'actif false|exec qs -c nc-ile ipc call ile aimant "" 0 0 0 0|taille 945 1060|place 10 10')

    def test_garde_fou_dix_secondes(self):
        sorties = lua(self.ECRAN + '''
CURSEUR = { x = 900, y = 500 }
AIMANT.presse(); CURSEUR = { x = 0, y = 500 }; PAS(); trace = {}
TEMPS = 9; PAS(); dire("9s", #trace)
TEMPS = 10; PAS(); dire("10s", table.concat(trace, "|"))
trace = {}; PAS(); dire("apres", #trace)
''')
        self.assertEqual(sorties[0], "9s\t0")
        self.assertEqual(sorties[1], '10s\tactif false|exec qs -c nc-ile ipc call ile aimant "" 0 0 0 0')
        self.assertEqual(sorties[2], "apres\t0", "plus rien après l'arrêt du garde-fou")

    def test_super_lache_avant_le_bouton_arrete_sans_ranger(self):
        sorties = lua(self.ECRAN + '''
KEYS = { Super_L = true }
hl.is_key_down = function(n) return KEYS[n] == true end
CURSEUR = { x = 900, y = 500 }; WIN = { floating = true, address = "0xab" }
AIMANT.presse(true); CURSEUR = { x = 0, y = 500 }; PAS(); trace = {}
PAS(); dire("tenu", #trace)
KEYS = {}; PAS(); dire("lache", table.concat(trace, "|"))
trace = {}; PAS(); AIMANT.relache(); dire("fin", #trace)
''')
        self.assertEqual(sorties[0], "tenu\t0")
        self.assertEqual(sorties[1], 'lache\tactif false|exec qs -c nc-ile ipc call ile aimant "" 0 0 0 0')
        self.assertEqual(sorties[2], "fin\t0", "plus de suivi et aucun rangement")

    def test_bouton_lateral_non_concerne_par_super(self):
        sorties = lua(self.ECRAN + '''
hl.is_key_down = function() return false end
CURSEUR = { x = 900, y = 500 }; WIN = { floating = true, address = "0xab" }
AIMANT.presse(false); CURSEUR = { x = 0, y = 500 }; PAS(); trace = {}
PAS(); AIMANT.relache(); dire(table.concat(trace, "|"))
''')
        self.assertEqual(sorties[0], 'actif false|exec qs -c nc-ile ipc call ile aimant "" 0 0 0 0|taille 945 1060|place 10 10')

    def test_is_key_down_en_erreur_ne_coupe_pas(self):
        sorties = lua(self.ECRAN + '''
hl.is_key_down = function() error("absent") end
CURSEUR = { x = 900, y = 500 }
AIMANT.presse(true); CURSEUR = { x = 0, y = 500 }; PAS(); trace = {}; PAS(); dire(#trace)
''')
        self.assertEqual(sorties, ["0"])

    def test_sans_apercu_pas_de_minuteur(self):
        sorties = lua(self.ECRAN + 'CURSEUR = { x = 900, y = 500 }; AIMANT.presse(); dire(#trace)\n', 'REG.AIMANT_APERCU = false\n')
        self.assertEqual(sorties, ["0"])

    def test_relache_sans_appui_ne_fait_rien(self):
        sorties = lua(self.ECRAN + 'WIN = { floating = true }; CURSEUR = { x = 0, y = 500 }; AIMANT.relache(); dire(#trace)\n')
        self.assertEqual(sorties, ["0"])

    def test_commande_seulement_zone_et_entiers(self):
        # Tous les appels de l'île suivent exactement le même modèle
        sorties = lua(self.ECRAN + '''
CURSEUR = { x = 900, y = 500 }; AIMANT.presse()
for _, p in ipairs({ {1,1}, {1919,1}, {1,1079}, {1919,1079}, {960,1}, {1,540}, {1919,540} }) do
  CURSEUR = { x = p[1], y = p[2] }; PAS()
end
for _, c in ipairs(trace) do if c:find("^exec") then dire(c) end end
''')
        self.assertEqual(len(sorties), 7)
        for c in sorties:
            self.assertRegex(c, r'^exec qs -c nc-ile ipc call ile aimant (haut|gauche|droite|haut-gauche|haut-droite|bas-gauche|bas-droite)'
                                r' -?\d+ -?\d+ \d+ \d+$')


@unittest.skipUnless(shutil.which("lua"), "Lua requis")
class Rangement(unittest.TestCase):
    ECRAN = Suivi.ECRAN

    def test_fenetre_rangee_devient_libre_puis_taille_et_place(self):
        sorties = lua(self.ECRAN + '''
CURSEUR = { x = 900, y = 500 }; WIN = { floating = false, address = "0xab" }
AIMANT.presse(); CURSEUR = { x = 1919, y = 500 }; trace = {}
AIMANT.relache()
dire(table.concat(trace, "|"))
''', 'REG.AIMANT_APERCU = false\n')
        self.assertEqual(sorties[0], "float set|taille 945 1060|place 965 10")

    def test_haut_sans_masquage(self):
        for valeur in (False, None):
            with self.subTest(valeur=valeur):
                reg = "REG.AIMANT_APERCU = false\n" + ("REG.AIMANT_PLEIN_MASQUE = false\n" if valeur is False else "")
                sorties = lua(self.ECRAN + '''
CURSEUR = { x = 900, y = 500 }; WIN = { floating = true, address = "0xab" }
AIMANT.presse(); CURSEUR = { x = 900, y = 0 }; trace = {}
AIMANT.relache()
dire(table.concat(trace, "|"))
''', reg)
                self.assertEqual(sorties[0], "plein maximized")
                self.assertNotIn("nc-fenetre", sorties[0])

    def test_haut_avec_masquage_avant_le_maximise(self):
        sorties = lua(self.ECRAN + '''
CURSEUR = { x = 900, y = 500 }; WIN = { floating = false, address = "0xab12" }
AIMANT.presse(); CURSEUR = { x = 900, y = 0 }; trace = {}
AIMANT.relache()
dire(table.concat(trace, "|"))
''', 'REG.AIMANT_APERCU = false\nREG.AIMANT_PLEIN_MASQUE = true\n')
        self.assertEqual(sorties[0], "float set|exec ~/.local/bin/nc-fenetre plein-masquer 0xab12|plein maximized")

    def test_adresse_invalide_jamais_passee_au_shell(self):
        for adr in ("0xab; rm -rf ~", "$(id)", "", "0x"):
            with self.subTest(adr=adr):
                sorties = lua(self.ECRAN + '''
CURSEUR = { x = 900, y = 500 }; WIN = { floating = true, address = %s }
AIMANT.presse(); CURSEUR = { x = 900, y = 0 }; trace = {}
AIMANT.relache()
dire(table.concat(trace, "|"))
''' % json.dumps(adr), 'REG.AIMANT_APERCU = false\nREG.AIMANT_PLEIN_MASQUE = true\n')
                self.assertEqual(sorties[0], "plein maximized")

    def test_simple_clic_au_bord_ne_range_rien(self):
        sorties = lua(self.ECRAN + '''
CURSEUR = { x = 1919, y = 500 }; WIN = { floating = false, address = "0xab" }
AIMANT.presse(); trace = {}
AIMANT.relache()
dire(#trace)
''', 'REG.AIMANT_APERCU = false\n')
        self.assertEqual(sorties, ["0"])


# Chargement complet de hyprland.lua avec un faux hl.bind qui REFUSE comme Hyprland 0.57
CHARGEMENT = r'''
package.path = os.getenv("CFG") .. "/?.lua;" .. package.path
local proxy; proxy = setmetatable({}, { __index = function() return proxy end, __call = function() return proxy end })
local mons = { { name = "DP-1", width = 1920, height = 1080, scale = 1, x = 0, y = 0, description = "a",
                 physical_width = 600, physical_height = 340, reserved = {} } }
last, handlers, notifs, execs, binds, refus, timers, dispatches = {}, {}, {}, {}, {}, {}, {}, {}
curseur = { x = 900, y = 500 }
hl = {
  version = function() return "0.57.0" end, config = function() end, env = function() end,
  on = function(e, f) handlers[e] = handlers[e] or {}; table.insert(handlers[e], f) end,
  exec_cmd = function(c) execs[#execs + 1] = c end,
  bind = function(k, f, o)
    o = o or {}
    if o.mouse and (o.click or o.drag or o.release or o.repeating or o.locked) then
      refus[#refus + 1] = tostring(k); error("hl.bind: mouse is exclusive")
    end
    binds[#binds + 1] = { k = tostring(k), f = f, o = o }
    return { release = o.release == true, click = o.click == true, drag = o.drag == true, remove = function() end }
  end,
  monitor = function(s) end, get_monitors = function() return mons end, get_active_monitor = function() return mons[1] end,
  get_windows = function() return {} end, get_active_window = function() return { floating = true, address = "0xab", monitor = mons[1] } end,
  get_active_workspace = function() end, get_config = function() return nil end, curve = function() end, animation = function() end,
  window_rule = function() end, layer_rule = function() end, workspace_rule = function() end, gesture = function() end,
  device = function() end, define_submap = function(n, f) f() end,
  timer = function(f, o) timers[#timers + 1] = { f = f, o = o, etats = {} }
    local t = timers[#timers]
    return { set_enabled = function(self, b) t.etats[#t.etats + 1] = b end } end,
  dsp = proxy, dispatch = function(d) dispatches[#dispatches + 1] = d end,
  get_cursor_pos = function() return { x = curseur.x, y = curseur.y } end,
  notification = { create = function(t) notifs[#notifs + 1] = t end },
}
'''


@unittest.skipUnless(shutil.which("lua"), "Lua requis")
class Chargement(unittest.TestCase):
    def lancer(self, saisie, apres):
        with tempfile.TemporaryDirectory() as d:
            home = Path(d)
            cfg = home / ".config/hypr"
            cfg.mkdir(parents=True)
            (cfg / "hyprland.lua").symlink_to(HYPR / "hyprland.lua")
            (cfg / "nc").symlink_to(HYPR / "nc")
            (home / ".config/nc").mkdir(parents=True)
            (home / ".config/nc/reglages.conf").write_text(f"SAISIE={saisie}\n")
            e = dict(os.environ, HOME=str(home), CFG=str(cfg), XDG_CONFIG_HOME=str(home / ".config"), NC_LANGUE="fr")
            code = CHARGEMENT + f'dofile("{cfg}/hyprland.lua")\n' + apres
            r = subprocess.run(["lua", "-"], input=code, text=True, capture_output=True, timeout=30, env=e)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return r.stdout.strip().splitlines()

    FLUX = r'''
print("refus", #refus, "echecs", #nc.echecs, "minuteurs", #timers)
for _, b in ipairs(binds) do
  if (b.k == "mouse:275" or b.k == "SUPER + mouse:272") and not b.o.mouse and not b.o.click and not b.o.drag then
    print("bind", b.k, b.o.release and "release" or "press")
  end
end
local p, r
for _, b in ipairs(binds) do
  if b.k == "SUPER + mouse:272" and not b.o.mouse and not b.o.click and not b.o.drag then
    if b.o.release then r = b.f else p = b.f end
  end
end
p()
print("apres appui", #timers, timers[1] and timers[1].o.timeout, timers[1] and timers[1].o.type, timers[1] and #timers[1].etats)
curseur = { x = 1919, y = 500 }; timers[1].f()
print("exec", execs[#execs])
r()
print("apres relache", table.concat((function() local t = {} for _, e in ipairs(timers[1].etats) do t[#t+1] = tostring(e) end return t end)(), ","))
'''

    def test_chargement_sans_refus_et_flux_complet(self):
        for saisie in ("souris", "les-deux"):
            with self.subTest(saisie=saisie):
                l = self.lancer(saisie, self.FLUX)
                self.assertEqual(l[0], "refus\t0\techecs\t0\tminuteurs\t0", "aucun refus, module chargé, minuteur absent au chargement")
                self.assertIn("bind\tmouse:275\tpress", l)
                self.assertIn("bind\tmouse:275\trelease", l)
                self.assertIn("bind\tSUPER + mouse:272\tpress", l)
                self.assertIn("bind\tSUPER + mouse:272\trelease", l)
                self.assertEqual(l[-3].split("\t")[:4], ["apres appui", "1", "50", "repeat"])
                self.assertEqual(l[-2], "exec\tqs -c nc-ile ipc call ile aimant droite 965 10 945 1060")
                self.assertEqual(l[-1], "apres relache\ttrue,false")

    def test_clavier_seul_aucune_aimantation(self):
        l = self.lancer("clavier", self.FLUX.split("local p, r")[0])
        self.assertEqual(l, ["refus\t0\techecs\t0\tminuteurs\t0"])

    def test_statique_jamais_mouse_avec_release(self):
        src = (HYPR / "nc/raccourcis.lua").read_text(encoding="utf-8")
        self.assertIn('si_compris("release", combinaison, aimant.relache)', src)
        self.assertNotIn("aimanter", src)
        self.assertNotRegex(src, r"mouse\s*=\s*true[^}]*release")
        self.assertEqual(len(re.findall(r"hl\.timer", (HYPR / "nc/aimant.lua").read_text())), 1, "un seul minuteur créé")


class Reglages(unittest.TestCase):
    SRC = (RACINE / "home/.local/bin/nc-reglages").read_text(encoding="utf-8")

    def bloc(self, cle):
        i = self.SRC.index(f'R("{cle}"')
        j = self.SRC.index("\n    R(", i)
        return self.SRC[i:j]

    def test_les_quatre_reglages(self):
        for cle, kind, defaut, bornes in (("AIMANT_BORD", "entier", "40", "mini=8, maxi=120"),
                                           ("AIMANT_COIN", "entier", "110", "mini=40, maxi=300"),
                                           ("AIMANT_APERCU", "ouinon", "oui", None),
                                           ("AIMANT_PLEIN_MASQUE", "ouinon", "non", None)):
            with self.subTest(cle=cle):
                b = self.bloc(cle)
                self.assertIn('"Fenêtres"', b)
                self.assertIn(f'"{kind}", "{defaut}"', b)
                self.assertIn('groupe="hypr"', b)
                self.assertIn("L(", b)
                if bornes:
                    self.assertIn(bornes, b)
                    self.assertIn('unite="px"', b)


if __name__ == "__main__":
    unittest.main()

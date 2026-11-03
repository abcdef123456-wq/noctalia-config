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
trace, TEMPS, REG, MONS, CURSEUR, WIN, WINS, handlers = {}, 0, {}, {}, { x = 0, y = 0 }, nil, nil, {}
-- grille sans bordure, 5 d'espace : les nombres ronds de ces tests ; la vraie grille (bordure 2, espace 4) est dans Grille
REG.FENETRES_BORDURE, REG.FENETRES_ESPACE = 0, 5
os.time = function() return TEMPS end
local function noter(s) trace[#trace + 1] = s end
local function plan(nom) return function(t)
  local p = { nom }
  if t.mode then p[#p + 1] = t.mode elseif t.action then p[#p + 1] = t.action end
  if t.mode and t.action == "unset" then p[#p + 1] = "unset" end
  if t.x then p[#p + 1] = t.x; p[#p + 1] = t.y end
  return table.concat(p, " ")
end end
hl = {
  get_monitors = function() return MONS end,
  get_cursor_pos = function() return { x = CURSEUR.x, y = CURSEUR.y } end,
  get_active_window = function() return WIN end,
  get_windows = function() return WINS or { WIN } end,
  on = function(e, f) handlers[e] = handlers[e] or {}; table.insert(handlers[e], f) end,
  exec_cmd = function(c) noter("exec " .. c) end,
  dispatch = function(d) noter(d) end,
  timer = function(f, o)
    if o.timeout == 250 then RECALE = f; return {} end  -- la relecture d'une fenêtre rangée : testée à part (classe Recalage)
    noter("timer-cree " .. o.timeout .. " " .. o.type)
    if o.type == "repeat" then PAS = f else DIFFERE = f end
    return { set_enabled = function(self, b) noter("actif " .. tostring(b)) end }
  end,
  dsp = { window = { float = plan("float"), fullscreen = plan("plein"), resize = plan("taille"), move = plan("place") } },
}
function emettre(e, w) for _, f in ipairs(handlers[e] or {}) do f(w) end end
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

    def test_super_lache_avant_le_bouton_depose_dans_la_zone(self):
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
        self.assertEqual(sorties[1], 'lache\tactif false|exec qs -c nc-ile ipc call ile aimant "" 0 0 0 0|taille 945 1060|place 10 10',
                         "rangée dans la zone sous le curseur, comme le cadre le promettait")
        self.assertEqual(sorties[2], "fin\t0", "le vrai relâchement ne range pas une seconde fois")

    def test_super_lache_loin_des_bords_ne_range_rien(self):
        sorties = lua(self.ECRAN + '''
hl.is_key_down = function() return false end
CURSEUR = { x = 900, y = 500 }; WIN = { floating = true, address = "0xab" }
AIMANT.presse(true); CURSEUR = { x = 700, y = 400 }; trace = {}
PAS(); dire(table.concat(trace, "|"))
''')
        self.assertEqual(sorties[0], "actif false")

    def test_super_clic_sans_deplacement_ne_range_rien(self):
        sorties = lua(self.ECRAN + '''
hl.is_key_down = function() return false end
CURSEUR = { x = 2, y = 500 }; WIN = { floating = true, address = "0xab" }
AIMANT.presse(true); CURSEUR = { x = 4, y = 502 }; trace = {}
PAS(); dire(table.concat(trace, "|"))
''')
        self.assertEqual(sorties[0], "actif false", "moins de 8 points de déplacement : le seuil de relache protège")

    def test_sans_apercu_super_lache_est_vu_et_l_ile_n_est_pas_prevenue(self):
        sorties = lua(self.ECRAN + '''
KEYS = { Super_L = true }
hl.is_key_down = function(n) return KEYS[n] == true end
CURSEUR = { x = 900, y = 500 }; WIN = { floating = true, address = "0xab" }
AIMANT.presse(true); dire("appui", table.concat(trace, "|")); trace = {}
CURSEUR = { x = 0, y = 500 }; PAS(); dire("tenu", #trace)
KEYS = {}; PAS(); dire("lache", table.concat(trace, "|"))
trace = {}; PAS(); AIMANT.relache(); dire("fin", #trace)
''', 'REG.AIMANT_APERCU = false\n')
        self.assertEqual(sorties[0], "appui\ttimer-cree 50 repeat|actif true", "le minuteur sert à voir Super lâché")
        self.assertEqual(sorties[1], "tenu\t0", "aucun message à l'île pendant le glisser")
        self.assertEqual(sorties[2], "lache\tactif false|taille 945 1060|place 10 10", "minuteur arrêté, rangée, île jamais prévenue")
        self.assertEqual(sorties[3], "fin\t0")

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

    def test_sans_apercu_le_garde_fou_arrete_le_minuteur(self):
        sorties = lua(self.ECRAN + '''
KEYS = { Super_L = true }
hl.is_key_down = function(n) return KEYS[n] == true end
CURSEUR = { x = 900, y = 500 }; AIMANT.presse(true); trace = {}
TEMPS = 10; PAS(); dire(table.concat(trace, "|"))
''', 'REG.AIMANT_APERCU = false\n')
        self.assertEqual(sorties[0], "actif false")

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
        self.assertEqual(sorties[0], "float enable|taille 945 1060|place 965 10")

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
        # une tuile n'est pas passée en libre : à la sortie du maximisé elle reprend sa place dans la disposition
        self.assertEqual(sorties[0], "exec ~/.local/bin/nc-fenetre plein-masquer 0xab12|plein maximized")

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


@unittest.skipUnless(shutil.which("lua"), "Lua requis")
class Recalage(unittest.TestCase):
    """Une fenêtre à taille minimale reste plus grande que sa cible (fonction pure, puis une seule relecture différée)."""
    ECRAN = 'MONS = { { name = "A", x = 0, y = 0, width = 1600, height = 1000, scale = 1, reserved = {} } }\n'

    def recale(self, code):
        return lua(self.ECRAN + """
ECRANS = { ecran(0, 0, 1600, 1000) }
function R(x, y, w, h, l, ht) local a, b = AIMANT.recaler({ x = x, y = y, w = w, h = h }, l, ht, ECRANS); dire(tostring(a), tostring(b)) end
""" + code)

    def test_pure_tient_dans_sa_cible_rien_a_faire(self):
        self.assertEqual(self.recale("R(805, 10, 781, 980, 781, 980); R(805, 10, 781, 980, 700, 500); R(805, 10, 781, 980, 783, 982)"),
                         ["nil\tnil"] * 3, "plus petite, ou à 2 points près (arrondi d'affichage) : rien")

    def test_pure_droite_garde_son_bord_droit_gauche_son_bord_gauche(self):
        self.assertEqual(self.recale("R(805, 10, 781, 980, 833, 980); R(10, 10, 781, 980, 833, 980)"), ["753\t10", "10\t10"])

    def test_pure_bas_garde_son_bord_bas_et_jamais_hors_ecran(self):
        self.assertEqual(self.recale("R(805, 510, 781, 480, 781, 600)"), ["805\t390"])
        self.assertEqual(self.recale("R(805, 10, 781, 980, 1700, 980)"), ["0\t10"], "plus large que l'écran : calée au bord")

    def depose(self, taille_reelle, apres=""):
        return lua(self.ECRAN + f'''
WIN = {{ floating = true, address = "0xab", at = {{ x = 100, y = 100 }}, size = {{ x = 500, y = 500 }} }}
CURSEUR = {{ x = 900, y = 500 }}
AIMANT.presse(); CURSEUR = {{ x = 1599, y = 500 }}; AIMANT.relache()
WINS = {{ {{ address = "0xab", floating = true, at = {{ x = 805, y = 10 }}, size = {taille_reelle} }} }}
{apres}
trace = {{}}; if RECALE then RECALE() end
dire(table.concat(trace, "|"))
''', 'REG.AIMANT_APERCU = false\n')

    def test_fenetre_trop_large_decalee_une_seule_fois(self):
        self.assertEqual(self.depose("{ x = 833, y = 980 }")[0], "place 757 10")

    def test_fenetre_qui_tient_ne_bouge_plus(self):
        self.assertEqual(self.depose("{ x = 786, y = 980 }")[0], "", "cible de 785 : à 2 points près, l'arrondi d'affichage")

    def test_nouveau_glisser_entre_temps_rien(self):
        self.assertEqual(self.depose("{ x = 833, y = 980 }", "CURSEUR = { x = 900, y = 500 }; AIMANT.presse()")[0], "")

    def test_fenetre_fermee_ou_maximisee_entre_temps_rien(self):
        self.assertEqual(self.depose("{ x = 833, y = 980 }", "WINS = {}")[0], "")
        self.assertEqual(self.depose("{ x = 833, y = 980 }", "WINS[1].fullscreen = 1")[0], "")

    def test_haut_ne_relit_rien(self):
        sorties = lua(self.ECRAN + '''
WIN = { floating = true, address = "0xab" }
CURSEUR = { x = 900, y = 500 }; AIMANT.presse(); CURSEUR = { x = 800, y = 0 }; AIMANT.relache()
dire(tostring(RECALE))
''', 'REG.AIMANT_APERCU = false\nREG.AIMANT_PLEIN_MASQUE = false\n')
        self.assertEqual(sorties, ["nil"], "agrandie : rien à recaler")


class Grille(unittest.TestCase):
    """Même grille que les tuiles : bordure dessinée autour de la surface, 2·espace entre deux voisines."""
    # L'écran de l'essai réel : 1600 × 1000 points, barre de 42 en haut, marge 10, bordure 2, espace 4 ; une tuile de
    # demi-écran y est à (12, 54) en 782 × 934 (hyprctl clients), son cadre bordure comprise à (10, 52) en 786 × 938
    ECRAN = 'MONS = { { name = "A", x = 0, y = 0, width = 1600, height = 1000, scale = 1, reserved = { top = 42 } } }\n'
    REG = "REG.FENETRES_BORDURE = 2\nREG.FENETRES_ESPACE = 4\n"

    def test_surface_et_cadre(self):
        sorties = lua('''
local E = { ecran(0, 0, 1600, 1000, 42) }
for _, p in ipairs({ {0,500}, {1599,500}, {800,0}, {0,0}, {1599,999} }) do
  local nom, r, c = AIMANT.zone(p[1], p[2], E, 40, 110, 10, { bordure = 2, espace = 4 })
  dire(nom, r.x, r.y, r.w, r.h, c.x, c.y, c.w, c.h)
end
''')
        self.assertEqual(sorties, [
            "gauche\t12\t54\t782\t934\t10\t52\t786\t938",
            "droite\t806\t54\t782\t934\t804\t52\t786\t938",
            "haut\t12\t54\t1576\t934\t10\t52\t1580\t938",
            "haut-gauche\t12\t54\t782\t461\t10\t52\t786\t465",
            "bas-droite\t806\t527\t782\t461\t804\t525\t786\t465",
        ])

    def test_sans_grille_les_anciens_nombres(self):
        # sans bordure ni espace donnés : bordure 0, espace = marge / 2, donc le même écart entre deux moitiés qu'au bord
        sorties = lua('''
local E = { ecran(0, 0, 1920, 1080, 40) }
local nom, r, c = AIMANT.zone(1919, 500, E, 40, 110, 10)
dire(nom, r.x, r.y, r.w, r.h, c.x, c.y, c.w, c.h)
''')
        self.assertEqual(sorties, ["droite\t965\t50\t945\t1020\t965\t50\t945\t1020"])

    def test_moitie_rangee_egale_une_tuile_et_apercu_bordure_comprise(self):
        sorties = lua(self.ECRAN + '''
CURSEUR = { x = 900, y = 500 }; WIN = { floating = false, address = "0xab" }
AIMANT.presse(); CURSEUR = { x = 0, y = 500 }; PAS(); dire("apercu", trace[#trace])
trace = {}; AIMANT.relache(); dire("range", table.concat(trace, "|"))
''', self.REG)
        self.assertEqual(sorties[0], "apercu\texec qs -c nc-ile ipc call ile aimant gauche 10 52 786 938")
        self.assertEqual(sorties[1], 'range\tactif false|exec qs -c nc-ile ipc call ile aimant "" 0 0 0 0'
                         "|float enable|taille 782 934|place 12 54")


@unittest.skipUnless(shutil.which("lua"), "Lua requis")
class Remise(unittest.TestCase):
    """L'état d'avant le rangement est gardé par adresse et rendu par M.remettre (Super + V), à la sortie durable du
    maximisé, ou quand la fenêtre est lâchée loin des bords."""
    ECRAN = Suivi.ECRAN
    SANS_APERCU = "REG.AIMANT_APERCU = false\n"
    LIBRE = 'WIN = { floating = true, address = "0xab", at = { x = 300, y = 200 }, size = { x = 600, y = 400 } }\n'
    TUILE = 'WIN = { floating = false, address = "0xab", at = { x = 12, y = 54 }, size = { x = 940, y = 1016 } }\n'
    A_DROITE = "CURSEUR = { x = 900, y = 500 }; AIMANT.presse(); CURSEUR = { x = 1919, y = 500 }; trace = {}; AIMANT.relache()\n"

    def test_libre_rangee_puis_remise_a_sa_place(self):
        sorties = lua(self.ECRAN + self.LIBRE + self.A_DROITE + '''
dire("range", table.concat(trace, "|"))
WIN.at, WIN.size = { x = 965, y = 10 }, { x = 945, y = 1060 }     -- comme Hyprland l'a placée
trace = {}; dire("remise", tostring(AIMANT.remettre(WIN)), table.concat(trace, "|"))
trace = {}; dire("encore", tostring(AIMANT.remettre(WIN)), #trace)
''', self.SANS_APERCU)
        self.assertEqual(sorties, ["range\ttaille 945 1060|place 965 10",
                                   "remise\ttrue\ttaille 600 400|place 300 200",
                                   "encore\tfalse\t0"])

    def test_tuile_rangee_puis_remise_en_tuile(self):
        sorties = lua(self.ECRAN + self.TUILE + self.A_DROITE + '''
dire("range", table.concat(trace, "|"))
WIN.floating = true
trace = {}; dire("remise", tostring(AIMANT.remettre(WIN)), table.concat(trace, "|"))
''', self.SANS_APERCU)
        self.assertEqual(sorties, ["range\tfloat enable|taille 945 1060|place 965 10", "remise\ttrue\tfloat disable"])

    def test_sans_etat_davant_rien(self):
        sorties = lua(self.ECRAN + self.LIBRE + '''
dire(tostring(AIMANT.remettre(WIN)), #trace)
dire(tostring(AIMANT.remettre(nil)), tostring(AIMANT.remettre({})), #trace)
''')
        self.assertEqual(sorties, ["false\t0", "false\tfalse\t0"])

    def test_haut_libre_sort_du_maximise_puis_sa_place(self):
        sorties = lua(self.ECRAN + self.LIBRE + '''
CURSEUR = { x = 900, y = 500 }; AIMANT.presse(); CURSEUR = { x = 900, y = 0 }; trace = {}; AIMANT.relache()
dire("range", table.concat(trace, "|"))
WIN.fullscreen = 1; WIN.at = { x = 2, y = 44 }
trace = {}; dire("remise", table.concat(trace, "|"))
AIMANT.remettre(WIN); dire("remise", table.concat(trace, "|"))
''', self.SANS_APERCU)
        self.assertEqual(sorties[0], "range\tplein maximized")
        self.assertEqual(sorties[2], "remise\tplein maximized unset|taille 600 400|place 300 200")

    def test_haut_tuile_reste_tuile(self):
        sorties = lua(self.ECRAN + self.TUILE + '''
CURSEUR = { x = 900, y = 500 }; AIMANT.presse(); CURSEUR = { x = 900, y = 0 }; trace = {}; AIMANT.relache()
dire("range", table.concat(trace, "|"))
WIN.fullscreen = 1
trace = {}; AIMANT.remettre(WIN); dire("remise", table.concat(trace, "|"))
''', self.SANS_APERCU)
        self.assertEqual(sorties, ["range\tplein maximized", "remise\tplein maximized unset"])

    def test_dun_bord_a_lautre_le_premier_etat_est_garde(self):
        sorties = lua(self.ECRAN + self.LIBRE + self.A_DROITE + '''
WIN.at, WIN.size = { x = 965, y = 10 }, { x = 945, y = 1060 }
CURSEUR = { x = 1400, y = 500 }; AIMANT.presse(); CURSEUR = { x = 0, y = 500 }; trace = {}; AIMANT.relache()
dire("gauche", table.concat(trace, "|"))
WIN.at = { x = 10, y = 10 }
trace = {}; AIMANT.remettre(WIN); dire("remise", table.concat(trace, "|"))
''', self.SANS_APERCU)
        self.assertEqual(sorties, ["gauche\ttaille 945 1060|place 10 10", "remise\ttaille 600 400|place 300 200"])

    def test_lachee_loin_des_bords_reprend_sa_taille_sous_le_curseur(self):
        sorties = lua(self.ECRAN + self.LIBRE + self.A_DROITE + '''
WIN.at, WIN.size = { x = 965, y = 10 }, { x = 945, y = 1060 }
-- saisie à 46 % de la largeur et de la hauteur de la fenêtre rangée : la taille d'avant garde la même proportion
-- (Hyprland a déplacé la fenêtre avec le curseur : at suit le glisser de -500, +100)
CURSEUR = { x = 1400, y = 500 }; AIMANT.presse(); CURSEUR = { x = 900, y = 600 }; WIN.at = { x = 465, y = 110 }
trace = {}; AIMANT.relache()
dire("milieu", table.concat(trace, "|"))
trace = {}; dire("apres", tostring(AIMANT.remettre(WIN)), #trace)
''', self.SANS_APERCU)
        self.assertEqual(sorties, ["milieu\ttaille 600 400|place 623 415", "apres\tfalse\t0"])

    def test_lachee_loin_des_bords_sans_etat_rien(self):
        sorties = lua(self.ECRAN + self.LIBRE + '''
CURSEUR = { x = 900, y = 500 }; AIMANT.presse(); CURSEUR = { x = 700, y = 600 }; trace = {}; AIMANT.relache()
dire(#trace)
''', self.SANS_APERCU)
        self.assertEqual(sorties, ["0"])

    def test_fenetre_glissee_pas_forcement_l_active_a_l_appui(self):
        # follow_mouse : à l'appui, l'active peut être une autre fenêtre ; l'état d'avant est celui de la fenêtre glissée
        sorties = lua(self.ECRAN + '''
local autre = { floating = true, address = "0xcc", at = { x = 1, y = 1 }, size = { x = 50, y = 50 } }
local glissee = { floating = true, address = "0xab", at = { x = 300, y = 200 }, size = { x = 600, y = 400 } }
WINS = { autre, glissee }
WIN = autre; CURSEUR = { x = 900, y = 500 }; AIMANT.presse()
WIN = glissee; CURSEUR = { x = 1919, y = 500 }; trace = {}; AIMANT.relache()
glissee.at, glissee.size = { x = 965, y = 10 }, { x = 945, y = 1060 }
trace = {}; AIMANT.remettre(glissee); dire(table.concat(trace, "|"))
''', self.SANS_APERCU)
        self.assertEqual(sorties, ["taille 600 400|place 300 200"])

    def test_deja_maximisee_a_l_appui_pas_d_etat(self):
        sorties = lua(self.ECRAN + self.LIBRE + '''
WIN.fullscreen = 1
''' + self.A_DROITE + '''
WIN.fullscreen = 0
trace = {}; dire(tostring(AIMANT.remettre(WIN)), #trace)
''', self.SANS_APERCU)
        self.assertEqual(sorties, ["false\t0"])

    def test_sortie_durable_du_maximise(self):
        sorties = lua(self.ECRAN + self.LIBRE + '''
CURSEUR = { x = 900, y = 500 }; AIMANT.presse(); CURSEUR = { x = 900, y = 0 }; AIMANT.relache()
WIN.fullscreen = 1; WIN.at = { x = 395, y = -170 }
trace = {}; emettre("window.fullscreen", { address = "0xab", fullscreen = 1 }); dire("encore", #trace)
emettre("window.fullscreen", { address = "0xab", fullscreen = 0 }); dire("sortie", table.concat(trace, "|"))
-- Super + V de Hyprland : sortie puis retour aussitôt ; à la relecture elle est encore maximisée, rien
trace = {}; DIFFERE(); dire("relue-max", #trace)
emettre("window.fullscreen", { address = "0xab", fullscreen = 0 })
WIN.fullscreen = 0
trace = {}; DIFFERE(); dire("relue-sortie", table.concat(trace, "|"))
trace = {}; dire("apres", tostring(AIMANT.remettre(WIN)))
''', self.SANS_APERCU)
        self.assertEqual(sorties, ["encore\t0", "sortie\ttimer-cree 150 oneshot", "relue-max\t0",
                                   "relue-sortie\ttaille 600 400|place 300 200", "apres\tfalse"])

    def test_sortie_pendant_un_glisser_attend_le_relachement(self):
        sorties = lua(self.ECRAN + self.LIBRE + '''
CURSEUR = { x = 900, y = 500 }; AIMANT.presse(); CURSEUR = { x = 900, y = 0 }; AIMANT.relache()
WIN.fullscreen = 1; WIN.at = { x = 2, y = 44 }; WIN.size = { x = 1916, y = 1034 }
CURSEUR = { x = 900, y = 300 }; AIMANT.presse()
trace = {}; emettre("window.fullscreen", { address = "0xab", fullscreen = 0 }); dire("glisser", #trace)
WIN.fullscreen = 0
CURSEUR = { x = 900, y = 600 }; WIN.at = { x = 2, y = 344 }          -- la fenêtre a suivi le curseur (+300 en y)
trace = {}; AIMANT.relache(); dire("milieu", table.concat(trace, "|"))
''', self.SANS_APERCU)
        self.assertEqual(sorties[0], "glisser\t0", "aucun minuteur pendant le glisser")
        # lâchée au milieu : sa taille d'avant, sous le curseur à la même proportion (47 % de 1916, 25 % de 1034)
        self.assertEqual(sorties[1], "milieu\ttaille 600 400|place 618 500")

    def test_fermeture_oublie_l_etat(self):
        sorties = lua(self.ECRAN + self.LIBRE + self.A_DROITE + '''
emettre("window.close", { address = "0xab" })
dire(tostring(AIMANT.remettre(WIN)))
emettre("window.close", nil); emettre("window.close", {}); dire("ok")
''', self.SANS_APERCU)
        self.assertEqual(sorties, ["false", "ok"])

    def test_recadrer(self):
        sorties = lua('''
local E = { ecran(0, 0, 1920, 1080, 40), ecran(1920, 0, 1920, 1080) }
for _, r in ipairs({ { x = -100, y = -50, w = 600, h = 400 }, { x = 1800, y = 1000, w = 600, h = 400 },
                     { x = 0, y = 0, w = 3000, h = 2000 }, { x = 2500, y = 900, w = 600, h = 400 }, { x = 100, y = 100, w = 600, h = 400 } }) do
  local c = AIMANT.recadrer(r, E)
  dire(c.x, c.y, c.w, c.h)
end
local r = { x = 5, y = 5, w = 10, h = 10 }
dire(AIMANT.recadrer(r, {}) == r, AIMANT.recadrer(nil, E) == nil)
''')
        self.assertEqual(sorties, ["0\t40\t600\t400", "1320\t680\t600\t400", "0\t40\t1920\t1040",
                                   "2500\t680\t600\t400", "100\t100\t600\t400", "true\ttrue"])


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
    print("bind", b.k, b.o.release and "release" or "press", b.o.transparent and "transparent" or "-")
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

    # Super + V : une fenêtre rangée par l'aimant est remise comme avant (2 dispatchs : taille et place), sinon libre ↔ rangée
    SUPER_V = r'''
local p, r, sv
for _, b in ipairs(binds) do
  if b.k == "SUPER + mouse:272" and not b.o.mouse and not b.o.click and not b.o.drag then
    if b.o.release then r = b.f else p = b.f end
  elseif b.k == "SUPER + code:55" then sv = b.f end
end
hl.get_active_window = function() return { floating = true, address = "0xab", at = { x = 300, y = 200 }, size = { x = 600, y = 400 }, monitor = mons[1] } end
local n = #dispatches; sv(); print("sans etat", #dispatches - n)
if p then p(); curseur = { x = 1919, y = 500 }; r() end
n = #dispatches; sv(); print("rangee", #dispatches - n, tostring(nc.aimant ~= nil))
n = #dispatches; sv(); print("apres", #dispatches - n)
'''

    def test_chargement_sans_refus_et_flux_complet(self):
        for saisie in ("souris", "les-deux"):
            with self.subTest(saisie=saisie):
                l = self.lancer(saisie, self.FLUX)
                self.assertEqual(l[0], "refus\t0\techecs\t0\tminuteurs\t0", "aucun refus, module chargé, minuteur absent au chargement")
                # Le relâchement est transparent : en 0.57, l'appui consommé par le déplacement le masquerait sinon
                self.assertIn("bind\tmouse:275\tpress\t-", l)
                self.assertIn("bind\tmouse:275\trelease\ttransparent", l)
                self.assertIn("bind\tSUPER + mouse:272\tpress\t-", l)
                self.assertIn("bind\tSUPER + mouse:272\trelease\ttransparent", l)
                self.assertEqual(l[-3].split("\t")[:4], ["apres appui", "1", "50", "repeat"])
                # le cadre d'aperçu, bordure comprise, avec les vrais réglages (bordure 2, espace 4)
                self.assertEqual(l[-2], "exec\tqs -c nc-ile ipc call ile aimant droite 964 10 946 1060")
                self.assertEqual(l[-1], "apres relache\ttrue,false")

    def test_clavier_seul_aucune_aimantation(self):
        l = self.lancer("clavier", self.FLUX.split("local p, r")[0])
        self.assertEqual(l, ["refus\t0\techecs\t0\tminuteurs\t0"])

    def test_super_v_remet_une_fenetre_rangee(self):
        l = self.lancer("les-deux", self.SUPER_V)
        self.assertEqual(l, ["sans etat\t1", "rangee\t2\ttrue", "apres\t1"])

    def test_super_v_au_clavier_reste_le_basculement(self):
        l = self.lancer("clavier", self.SUPER_V)
        self.assertEqual(l, ["sans etat\t1", "rangee\t1\tfalse", "apres\t1"])

    def test_statique_jamais_mouse_avec_release(self):
        src = (HYPR / "nc/raccourcis.lua").read_text(encoding="utf-8")
        self.assertIn('si_compris("release", combinaison, aimant.relache)', src)
        self.assertNotIn("aimanter", src)
        self.assertNotRegex(src, r"mouse\s*=\s*true[^}]*release")
        aimant = (HYPR / "nc/aimant.lua").read_text()
        self.assertEqual(len(re.findall(r'type = "repeat"', aimant)), 1, "un seul minuteur répété")
        # un seul minuteur répété, et deux à un coup : sortie du maximisé, relecture d'une fenêtre rangée
        self.assertEqual(len(re.findall(r"hl\.timer", aimant)), 3)


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

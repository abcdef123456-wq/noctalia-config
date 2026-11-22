"""Barre sur un côté (nord à gauche, kanagawa à droite) et barre sans pastilles (apple).
Batterie : Noctalia 5.3 passe aux rappels asynchrones (readFileAsync, runAsync…) un contexte vide, où
barWidget.isVertical() vaut toujours faux (script_runtime.cpp : enqueueAsyncFileResult sans snapshot) ; le faux barWidget
d'ici fait pareil. La batterie lit donc l'orientation dans lire() (update, survol, chargement), pas dans le rappel.
Pilules VPN et Garmin : en colonne sur un côté. apple : logo puis titre, et aucun groupe qui garderait sa pastille.
Faux HOME (test_barre_composition.nc_isole) ; jamais le vrai HOME."""
from pathlib import Path
import json
import re
import shutil
import subprocess
import tempfile
import unittest

from tests import test_barre_composition as bc
from tests.test_batterie_barre import PRELUDE as PRELUDE_BATTERIE
from tests.test_vpn_barre import PRELUDE as PRELUDE_PILULE

REPO = Path(__file__).resolve().parents[1]
PLUGINS = REPO / "home/.local/share/noctalia/plugins"
BATTERIE = PLUGINS / "nc-batterie"
AVANT = "640aa0e"       # batterie.luau qui lisait isVertical() dans le rappel de readFileAsync

# Comme Noctalia : isVertical() juste seulement hors des rappels asynchrones
SNAPSHOT = r'''
DANS_RAPPEL = false
barWidget.isVertical = function() return VERTICAL and not DANS_RAPPEL end
function vider() local a = ASYNC; ASYNC = {}; DANS_RAPPEL = true; for _, f in ipairs(a) do f() end; DANS_RAPPEL = false end
'''
OUTILS = r'''
function larg(n)
  if n.k == "glyph" then return n.o.size end
  if n.k == "image" or n.o.width then return n.o.width end
  if n.k == "label" then return 8 * utf8.len(n.o.text) end
  local t = 0
  for i, e in ipairs(n.e) do
    if n.k == "row" then t = t + larg(e) + (i > 1 and (n.o.gap or 0) or 0) else t = math.max(t, larg(e)) end
  end
  return t
end
function ser(n)
  if type(n) ~= "table" then return tostring(n) end
  local t = {}
  for k, v in pairs(n) do t[#t + 1] = tostring(k) .. "=" .. ser(v) end
  table.sort(t)
  return "{" .. table.concat(t, ",") .. "}"
end
'''


def pastille_nord():
    """Largeur intérieure de la pastille d'une barre de 52 (Noctalia : round(épaisseur × capsule_thickness), contenu centré)
    moins capsule_padding de chaque côté, pour garder de l'air."""
    t = (REPO / "home/.config/noctalia/config.toml").read_text(encoding="utf-8")
    ep = float(re.search(r"^capsule_thickness\s*=\s*([\d.]+)", t, re.M).group(1))
    pad = float(re.search(r"^capsule_padding\s*=\s*([\d.]+)", t, re.M).group(1))
    return round(52 * ep) - 2 * pad


def lancer_lua(code, dossier):
    with tempfile.TemporaryDirectory() as d:
        h = Path(d) / "harnais.lua"
        h.write_text(code, encoding="utf-8")
        return subprocess.run(["lua", str(h), str(dossier)], text=True, capture_output=True, timeout=10)


@unittest.skipUnless(shutil.which("lua"), "Lua requis")
class Batterie(unittest.TestCase):
    VERTICALE = r'''
VERTICAL = true
SYSFS.BAT0 = uevent({ STATUS = "Charging", CAPACITY = 80, ENERGY_NOW = 59000000, ENERGY_FULL = 74690000,
  POWER_NOW = 20000000 })
charger(); vider()
egal(RENDU.k, "column", "une colonne")
egal(RENDU.e[1].o.width, 7, "borne en haut"); egal(RENDU.e[1].o.height, 3)
local corps = RENDU.e[2]
egal(corps.o.width, 18); egal(corps.o.height, 23)
egal(RENDU.e[#RENDU.e].k, "glyph", "état au-dessous")
egal(RENDU.o.align, "center", "centré sur l'axe")
assert(larg(RENDU) <= LIMITE, "plus large que la pastille : " .. larg(RENDU))
-- 100 % : corps sans chiffre, 14 × 22
SYSFS.BAT0 = uevent({ STATUS = "Full", CAPACITY = 100 })
HORLOGE = 40000; update(); vider()
egal(RENDU.k, "column"); egal(RENDU.e[2].o.width, 14); egal(RENDU.e[2].o.height, 22)
assert(larg(RENDU) <= LIMITE)
'''

    def lua(self, code, dossier=BATTERIE):
        return lancer_lua(PRELUDE_BATTERIE + SNAPSHOT + OUTILS + f"LIMITE = {pastille_nord()}\n" + code, dossier)

    def test_verticale_dans_la_pastille(self):
        r = self.lua(self.VERTICALE)
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)

    def test_horizontale_identique_a_avant(self):
        code = r'''
SYSFS.BAT0 = uevent(DECHARGE)
charger(); vider()
egal(RENDU.k, "row")
print(ser(RENDU))
'''
        nouveau = self.lua(code)
        self.assertEqual(nouveau.returncode, 0, nouveau.stderr)
        with tempfile.TemporaryDirectory() as d:
            shutil.copy(BATTERIE / "calcul.luau", d)
            chemin = f"{AVANT}:home/.local/share/noctalia/plugins/nc-batterie/batterie.luau"
            ancien = subprocess.run(["git", "-C", str(REPO), "show", chemin], capture_output=True, text=True, check=False)
            if ancien.returncode:
                self.skipTest("historique git absent")
            (Path(d) / "batterie.luau").write_text(ancien.stdout, encoding="utf-8")
            avant = self.lua(code, d)
            # Contrôle du contrôle : l'ancienne lecture (dans le rappel) reste à l'horizontale, le test vertical échoue
            controle = self.lua(self.VERTICALE, d)
        self.assertEqual(avant.returncode, 0, avant.stderr)
        self.assertEqual(nouveau.stdout, avant.stdout)
        self.assertNotEqual(controle.returncode, 0, "l'ancienne batterie.luau passe le test vertical : il ne prouve rien")
        self.assertIn("une colonne", controle.stderr)


@unittest.skipUnless(shutil.which("lua"), "Lua requis")
class Pilules(unittest.TestCase):
    def lua(self, fichier, code):
        r = lancer_lua(PRELUDE_PILULE + OUTILS + f"LIMITE = {pastille_nord()}\n" + code, fichier)
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)

    def test_vpn(self):
        self.lua(PLUGINS / "nc-vpn/vpn.luau", r'''
VERTICAL = false
barWidget.isVertical = function() return VERTICAL end
poser({ connecte = true, fournisseur = "NordVPN", pays = "FR" }, 1)
charger()
egal(RENDU.k, "row"); egal(textes(RENDU)[1], "NordVPN · " .. utf8.char(0x1F1EB, 0x1F1F7) .. " FR")
VERTICAL = true; RENDU = nil; poser({ connecte = true, fournisseur = "NordVPN", pays = "DE" }, 2); update()
egal(RENDU.k, "column"); egal(textes(RENDU)[1], "DE", "le seul code pays")
assert(larg(RENDU) <= LIMITE, "VPN plus large que la pastille : " .. larg(RENDU))
egal(BULLE, "NordVPN · " .. utf8.char(0x1F1E9, 0x1F1EA) .. " DE", "le nom complet dans l'infobulle")
poser({ connecte = true, masque_partage = true, fournisseur = "NordVPN", pays = "DE" }, 3); update()
egal(#textes(RENDU), 0, "partage d'écran : ni nom ni pays")
''')

    def test_garmin(self):
        self.lua(PLUGINS / "nc-garmin/garmin.luau", r'''
ETAT = RUN .. "/nc-garmin-barre.json"
VERTICAL = true
barWidget.isVertical = function() return VERTICAL end
poser({ actif = true, metriques = { body_battery = 73 } }, 1)
charger()
egal(RENDU.k, "column"); egal(textes(RENDU)[1], "73")
assert(larg(RENDU) <= LIMITE)
''')


class SansPastilles(unittest.TestCase):
    """Tout thème dont la barre est sans pastilles (apple, oled, barres plates des recettes) : aucun groupe (Noctalia lui
    donne toujours la sienne) ; ses membres restent, posés à nu."""
    def test_tout_ou_rien(self):
        for install in bc.INSTALLS:
            plats = sorted(p.stem for p in bc.THEMES.glob("*.json")
                           if json.loads(p.read_text(encoding="utf-8")).get("noctalia", {}).get("bar.default", {}).get("capsule") is False)
            self.assertTrue({"apple", "oled"} <= set(plats))
            for style in plats:
                with bc.nc_isole(install=install, style=style) as (nc, f):
                    for c in bc.COMBOS:
                        with self.subTest(install=install, style=style, interrupteurs=c):
                            b = bc.barre(nc, f, c)["bar"]["default"]
                            self.assertIs(b["capsule"], False)
                            listes = b.get("start", []) + b.get("center", []) + b["end"]
                            self.assertFalse([w for w in listes if w.startswith("group:")], "un groupe garde sa pastille")
                            self.assertNotIn("capsule_group", b)
                            if style == "apple":
                                for w in ("network", "bluetooth", "volume", "nc/batterie:batterie", "power_profile"):
                                    self.assertIn(w, b["end"])
                            self.assertEqual("cpu" in b["end"], c.get("BARRE_SYSTEME") != "non")
                            if style == "apple":
                                self.assertEqual(b["start"], ["logo", "nc/fenetres:titre"], "logo puis le titre, sans trou")
                                self.assertNotIn("workspaces", listes)

if __name__ == "__main__":
    unittest.main()

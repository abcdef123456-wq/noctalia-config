"""nc/ecrans.lua : définition native, fréquence et échelle choisies d'après la liste de modes de l'écran.

Le fichier est chargé entier dans Lua avec un faux `hl` : les règles d'écran qu'il pose (hl.monitor) sont relues.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
LUA = REPO / "home/.config/hypr/nc/ecrans.lua"

# ASUS VG32VQR (31,5", 2560x1440 à 144 Hz) en HDMI : un 3840x2160 à 60 Hz de compatibilité en plus de sa dalle
ASUS = dict(name="HDMI-A-1", description="ASUS VG32VQR", width=3840, height=2160, physical_width=700, physical_height=390,
            available_modes=["2560x1440@143.97Hz", "3840x2160@60.00Hz", "3840x2160@59.94Hz", "2560x1440@120.00Hz",
                             "2560x1440@59.95Hz", "1920x1080@143.86Hz", "1920x1080@60.00Hz"])
# Revue ECR-01 : écrans 144 Hz qui disent préférer un mode à 60 Hz, avec un faux 4K de compatibilité
PREF60 = dict(name="HDMI-A-3", description="", width=3840, height=2160, physical_width=700, physical_height=390,
              available_modes=["2560x1440@59.95Hz", "2560x1440@143.97Hz", "3840x2160@60.00Hz"])
FHD144 = dict(name="HDMI-A-4", description="", width=3840, height=2160, physical_width=530, physical_height=300,
              available_modes=["1920x1080@60.00Hz", "1920x1080@144.00Hz", "3840x2160@30.00Hz"])
# Téléviseur 4K qui préfère 60 Hz et propose 120 Hz
TV = dict(name="HDMI-A-5", description="", width=3840, height=2160, physical_width=1210, physical_height=680,
          available_modes=["3840x2160@60.00Hz", "3840x2160@120.00Hz", "1920x1080@120.00Hz"])
# Vrai écran 4K à 60 Hz de 27"
UHD = dict(name="DP-1", description="Dell U2720Q", width=3840, height=2160, physical_width=600, physical_height=340,
           available_modes=["3840x2160@60.00Hz", "3840x2160@30.00Hz", "2560x1440@59.95Hz", "1920x1080@60.00Hz"])
# Écran sans liste de modes (projecteur, partage de bureau…)
SANS = dict(name="HDMI-A-2", description="", width=1920, height=1080, physical_width=0, physical_height=0, available_modes=[])
# Écran de portable à 165 Hz
PORTABLE = dict(name="eDP-1", description="", width=2560, height=1600, physical_width=340, physical_height=215,
                available_modes=["2560x1600@165.00Hz", "2560x1600@60.00Hz", "1920x1200@165.00Hz", "1920x1080@60.00Hz"])


@unittest.skipUnless(shutil.which("lua"), "Lua requis")
class Ecrans(unittest.TestCase):
    def regles(self, moniteurs, hz="max", lid=None):
        """Charge ecrans.lua avec ces écrans ; renvoie les règles posées, par nom d'écran."""
        with tempfile.TemporaryDirectory() as home:
            env = dict(HOME=home, PATH="/usr/bin:/bin", XDG_RUNTIME_DIR=home, NC_LID_DIR=home + "/lid")
            if lid:                              # « closed » ou « open » : état du couvercle (sinon : pas de fichier)
                (Path(home) / "lid/LID0").mkdir(parents=True)
                (Path(home) / "lid/LID0/state").write_text(f"state:      {lid}\n")
            harness = r'''
local regles = {}
local moniteurs = MONITEURS
hl = {
  get_monitors = function() return moniteurs end,
  monitor = function(spec) if spec.output ~= "" then regles[#regles + 1] = spec end end,
  on = function() end,
  exec_cmd = function() end,
}
nc = { profil = { hz = HZ } }
dofile(FICHIER)
for _, r in ipairs(regles) do print(r.output, r.mode, r.scale, r.disabled and "off" or "on") end
'''.replace("MONITEURS", self.lua(moniteurs)).replace("HZ", json.dumps(hz)).replace("FICHIER", json.dumps(str(LUA)))
            r = subprocess.run(["lua", "-"], input=harness, text=True, capture_output=True, timeout=5, env=env)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        regles = {}
        for ligne in r.stdout.splitlines():
            nom, mode, echelle, etat = ligne.split("\t")
            regles[nom] = dict(mode=mode, echelle=float(echelle) if echelle != "nil" else None, actif=etat == "on")
        return regles

    @staticmethod
    def lua(moniteurs):
        def table(m):
            modes = ", ".join(json.dumps(v) for v in m["available_modes"])
            return ("{ name = %s, description = %s, width = %d, height = %d, physical_width = %d, physical_height = %d, "
                    "available_modes = { %s } }" % (json.dumps(m["name"]), json.dumps(m["description"]), m["width"],
                                                     m["height"], m["physical_width"], m["physical_height"], modes))
        return "{ " + ", ".join(table(m) for m in moniteurs) + " }"

    def test_hyprland_055_sans_modes_en_lua(self):
        """Hyprland 0.55 (Debian 13) : les écrans n'ont en Lua ni modes, ni taille physique, ni place réservée. Lus en
        arrière-plan par hyprctl monitors -j (jamais pendant le chargement), puis tout est réappliqué : le Dell 4K de
        27 pouces reçoit son mode 4K et son échelle 1,5, au lieu de « preferred » et 1."""
        with tempfile.TemporaryDirectory() as home:
            harness = r'''
local regles, commandes = {}, {}
local moniteurs = { { name = "DP-1", description = "Dell U2720Q", width = 3840, height = 2160 } }
hl = {
  get_monitors = function() return moniteurs end,
  monitor = function(spec) if spec.output ~= "" then regles[spec.output] = spec end end,
  on = function() end,
  exec_cmd = function(c) commandes[#commandes + 1] = c end,
}
nc = { profil = { hz = "max" } }
dofile(FICHIER)
print("AVANT", regles["DP-1"].mode, regles["DP-1"].scale)
assert(#commandes == 1 and commandes[1]:find("hyprctl monitors %-j"), "les infos demandées une fois, en arrière-plan")
nc.ecrans_infos_poser({ ["DP-1"] = { modes = { "3840x2160@60.00Hz", "2560x1440@59.95Hz" }, pw = 600, ph = 340, reserved = { 0, 42, 0, 0 } } })
print("APRES", regles["DP-1"].mode, regles["DP-1"].scale)
'''.replace("FICHIER", json.dumps(str(LUA)))
            r = subprocess.run(["lua", "-"], input=harness, text=True, capture_output=True, timeout=5, env=dict(HOME=home, PATH="/usr/bin:/bin", XDG_RUNTIME_DIR=home))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("AVANT\tpreferred\t1", r.stdout)
        self.assertIn("APRES\t3840x2160@60.00\t1.5", r.stdout)

    def test_hyprland_055_echelle_gardee_au_rechargement(self):
        """Hyprland 0.55 : après un rechargement de la config, l'écran reprend sa dernière échelle connue au lieu de
        passer par 1 (clignotement) ; le fichier n'est réécrit que si l'échelle change ; un autre écran sur la même prise
        ne reprend pas l'échelle de l'ancien."""
        harness = r'''
local regles, commandes = {}, {}
local moniteurs = { { name = "DP-1", description = DESC, width = 3840, height = 2160 } }
hl = {
  get_monitors = function() return moniteurs end,
  monitor = function(spec) if spec.output ~= "" then regles[spec.output] = spec end end,
  on = function() end,
  exec_cmd = function(c) commandes[#commandes + 1] = c end,
}
nc = { profil = { hz = "max" } }
dofile(FICHIER)
print("AVANT", regles["DP-1"].scale)
if INFOS then
  nc.ecrans_infos_poser({ ["DP-1"] = { modes = { "3840x2160@60.00Hz" }, pw = PW, ph = PH, reserved = { 0, 0, 0, 0 } } })
  print("APRES", regles["DP-1"].scale)
end
'''
        with tempfile.TemporaryDirectory() as home:
            def lancer(desc, infos, pw=600, ph=340):
                code = (harness.replace("FICHIER", json.dumps(str(LUA))).replace("DESC", json.dumps(desc, ensure_ascii=False))
                        .replace("INFOS", "true" if infos else "false").replace("PW", str(pw)).replace("PH", str(ph)))
                r = subprocess.run(["lua", "-"], input=code, text=True, capture_output=True, timeout=5,
                                   env=dict(HOME=home, PATH="/usr/bin:/bin", XDG_RUNTIME_DIR=home))
                self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
                return r.stdout
            def avant(sortie):
                return float(sortie.split("AVANT\t")[1].split()[0])
            fichier = Path(home) / "nc-ecrans-echelles"
            # 1er chargement : rien de gardé, 1 puis 1,5 quand hyprctl a répondu
            out = lancer("Dell U2720Q", True)
            self.assertIn("AVANT\t1", out)
            self.assertIn("APRES\t1.5", out)
            self.assertTrue(fichier.exists())
            # Rechargement : 1,5 tout de suite (hyprctl pas encore revenu)
            self.assertIn("AVANT\t1.5", lancer("Dell U2720Q", False))
            # Pas réécrit tant que l'échelle ne change pas
            fichier.write_text(fichier.read_text())
            os.utime(fichier, (1, 1))
            lancer("Dell U2720Q", True)
            self.assertEqual(int(fichier.stat().st_mtime), 1, "écrit seulement quand l'échelle change")
            # Un autre écran sur la même prise : pas l'échelle de l'ancien
            self.assertEqual(avant(lancer("Autre écran", False)), 1)
            # L'échelle change (écran de 32" en 4K : 1,5 -> 1 avec un écran géant) : le fichier suit
            lancer("Dell U2720Q", True, pw=1210, ph=680)
            self.assertEqual(avant(lancer("Dell U2720Q", False)), 1)

    def test_ecran_interne_eDP_LVDS_DSI(self):
        """L'écran interne (fréquence du profil, premier écran principal) : eDP, LVDS ou DSI, la même règle partout."""
        for nom in ("eDP-1", "LVDS-1", "DSI-1"):
            interne = dict(PORTABLE, name=nom)
            r = self.regles([ASUS, interne], hz="low")
            self.assertEqual(r[nom]["mode"], "2560x1600@60.00", nom + " : fréquence du profil énergétique")
            self.assertTrue(r[nom]["actif"], nom)
        r = self.regles([ASUS, dict(PORTABLE, name="HDMI-A-9")], hz="low")
        self.assertEqual(r["HDMI-A-9"]["mode"], "2560x1600@165.00", "un écran externe garde sa fréquence la plus haute")

    def test_ecran_1440p_144hz_avec_faux_4k(self):
        r = self.regles([ASUS])["HDMI-A-1"]
        self.assertEqual(r["mode"], "2560x1440@143.97", "la dalle est en 1440p, pas le 4K de compatibilité HDMI")
        self.assertEqual(round(float(r["mode"].split("@")[1])), 144)
        self.assertEqual(r["echelle"], 1, "31,5 pouces en 1440p : 93 points par pouce, échelle 1")

    def test_ecran_144hz_qui_prefere_60hz(self):
        r = self.regles([PREF60, FHD144, TV])
        self.assertEqual(r["HDMI-A-3"]["mode"], "2560x1440@143.97", "le 144 Hz vient en second : la dalle reste en 1440p")
        self.assertEqual(r["HDMI-A-4"]["mode"], "1920x1080@144.00", "1080p à 144 Hz, pas le faux 4K à 30 Hz")
        self.assertEqual(r["HDMI-A-5"]["mode"], "3840x2160@120.00", "un vrai 4K à 120 Hz reste en 4K")

    def test_vrai_4k_60hz_inchange(self):
        r = self.regles([UHD])["DP-1"]
        self.assertEqual(r["mode"], "3840x2160@60.00")
        self.assertEqual(r["echelle"], 1.5, "27 pouces en 4K : 163 points par pouce, échelle 1,5")

    def test_ecran_sans_liste_de_modes(self):
        r = self.regles([SANS])["HDMI-A-2"]
        self.assertEqual(r["mode"], "preferred")
        self.assertEqual(r["echelle"], 1)

    def test_portable_et_externe(self):
        r = self.regles([PORTABLE, ASUS], hz="low")
        self.assertEqual(r["eDP-1"]["mode"], "2560x1600@60.00", "écran interne : la fréquence du profil énergétique")
        self.assertEqual(r["HDMI-A-1"]["mode"], "2560x1440@143.97", "écran externe : sa fréquence la plus haute")
        self.assertTrue(r["HDMI-A-1"]["actif"])

    def test_couvercle_ferme_avec_externe_l_ecran_du_pc_reste_coupe(self):
        """Après un rechargement de la config, l'écran du PC couvercle fermé ne se rallume pas si un externe est là."""
        r = self.regles([PORTABLE, ASUS], lid="closed")
        self.assertFalse(r["eDP-1"]["actif"])
        self.assertTrue(r["HDMI-A-1"]["actif"])

    def test_couvercle_ouvert_ferme_sans_externe_ou_absent_rien_ne_change(self):
        self.assertTrue(self.regles([PORTABLE, ASUS], lid="open")["eDP-1"]["actif"])
        self.assertTrue(self.regles([PORTABLE, ASUS])["eDP-1"]["actif"], "pas de fichier de couvercle : rien ne change")
        self.assertTrue(self.regles([PORTABLE], lid="closed")["eDP-1"]["actif"], "pas d'externe : l'écran reste")
        virtuel = dict(SANS, name="HEADLESS-2")
        self.assertTrue(self.regles([PORTABLE, virtuel], lid="closed")["eDP-1"]["actif"], "un écran virtuel ne compte pas")


if __name__ == "__main__":
    unittest.main()

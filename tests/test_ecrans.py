"""nc/ecrans.lua : définition native, fréquence et échelle choisies d'après la liste de modes de l'écran.

Le fichier est chargé entier dans Lua avec un faux `hl` : les règles d'écran qu'il pose (hl.monitor) sont relues.
"""
import json
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
    def regles(self, moniteurs, hz="max"):
        """Charge ecrans.lua avec ces écrans ; renvoie les règles posées, par nom d'écran."""
        with tempfile.TemporaryDirectory() as home:
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
            r = subprocess.run(["lua", "-"], input=harness, text=True, capture_output=True, timeout=5,
                               env=dict(HOME=home, PATH="/usr/bin:/bin"))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        regles = {}
        for ligne in r.stdout.splitlines():
            nom, mode, echelle, etat = ligne.split("\t")
            regles[nom] = dict(mode=mode, echelle=float(echelle), actif=etat == "on")
        return regles

    @staticmethod
    def lua(moniteurs):
        def table(m):
            modes = ", ".join(json.dumps(v) for v in m["available_modes"])
            return ("{ name = %s, description = %s, width = %d, height = %d, physical_width = %d, physical_height = %d, "
                    "available_modes = { %s } }" % (json.dumps(m["name"]), json.dumps(m["description"]), m["width"],
                                                     m["height"], m["physical_width"], m["physical_height"], modes))
        return "{ " + ", ".join(table(m) for m in moniteurs) + " }"

    def test_ecran_1440p_144hz_avec_faux_4k(self):
        r = self.regles([ASUS])["HDMI-A-1"]
        self.assertEqual(r["mode"], "2560x1440@143.97", "la dalle est en 1440p, pas le 4K de compatibilité HDMI")
        self.assertEqual(round(float(r["mode"].split("@")[1])), 144)
        self.assertEqual(r["echelle"], 1, "31,5 pouces en 1440p : 93 points par pouce, échelle 1")

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


if __name__ == "__main__":
    unittest.main()

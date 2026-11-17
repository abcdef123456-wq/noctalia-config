"""Mode jeu : le pointeur passe en accel_profile « flat » (energie.lua), sauf si JEU_SOURIS_PLATE=non ; hors jeu, le
réglage SOURIS_ACCELERATION de clavier.lua reste. clavier.lua puis energie.lua, dans l'ordre de hyprland.lua, avec un faux hl."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

NC = Path(__file__).resolve().parents[1] / "home/.config/hypr/nc"
LUA = shutil.which("lua5.4") or shutil.which("lua")

HARNAIS = r'''
local reglages = {}
for k, v in arg[2]:gmatch("([%w_]+)=(%S+)") do if v == "true" then v = true elseif v == "false" then v = false end reglages[k] = v end
nc = { profil = { profil = "balanced", batterie = false }, t = function(fr) return fr end,
       reglage = function(cle, d) if reglages[cle] ~= nil then return reglages[cle] end return d end,
       guillemets = function(s) return "'" .. s .. "'" end }
local input = {}
hl = { config = function(t) for k, v in pairs(t.input or {}) do input[k] = v end end,
       exec_cmd = function() end, animation = function() end, gesture = function() end, device = function() end }
dofile(arg[1] .. "/clavier.lua")
dofile(arg[1] .. "/energie.lua")
print(input.accel_profile)
'''


@unittest.skipUnless(LUA, "lua requis")
class SourisEnModeJeu(unittest.TestCase):
    def accel(self, reglages="", jeu=False):
        with tempfile.TemporaryDirectory(prefix="nc-jeu-souris-") as d:
            (Path(d) / "harnais.lua").write_text(HARNAIS)
            if jeu:
                (Path(d) / "nc-mode-jeu").write_text("")
            env = dict(os.environ, HOME=d, XDG_RUNTIME_DIR=d, XDG_CONFIG_HOME=d, XDG_STATE_HOME=d, TMPDIR=d)
            r = subprocess.run([LUA, str(Path(d) / "harnais.lua"), str(NC), reglages or "-"],
                               env=env, capture_output=True, text=True, timeout=10)
            self.assertEqual(r.returncode, 0, r.stderr)
            return r.stdout.strip()

    def test_jeu_par_defaut_plat(self):
        for accel in ("SOURIS_ACCELERATION=adaptative", "SOURIS_ACCELERATION=plate", ""):
            self.assertEqual(self.accel(accel, jeu=True), "flat", accel)

    def test_jeu_sans_le_reglage_garde_celui_du_bureau(self):
        self.assertEqual(self.accel("JEU_SOURIS_PLATE=false SOURIS_ACCELERATION=adaptative", jeu=True), "adaptive")
        self.assertEqual(self.accel("JEU_SOURIS_PLATE=false SOURIS_ACCELERATION=plate", jeu=True), "flat")

    def test_hors_jeu_inchange(self):
        self.assertEqual(self.accel("SOURIS_ACCELERATION=adaptative"), "adaptive")
        self.assertEqual(self.accel("SOURIS_ACCELERATION=plate"), "flat")
        self.assertEqual(self.accel("JEU_SOURIS_PLATE=true"), "adaptive")

    def test_la_cle_est_un_reglage(self):
        src = (NC.parents[2] / ".local/bin/nc-reglages").read_text()
        self.assertIn('R("JEU_SOURIS_PLATE"', src)


if __name__ == "__main__":
    unittest.main()

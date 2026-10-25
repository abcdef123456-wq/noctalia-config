"""hyprland.lua : chaque module passe par nc.charger (une erreur n'arrête pas les suivants, elle est signalée une fois),
et les écrans réglés dans perso.lua ne sont pas écrasés par nc/ecrans.lua. Faux `hl`, jamais le vrai Hyprland."""
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

HYPR = Path(__file__).resolve().parents[1] / "home/.config/hypr"

# Faux hl : MODE_BIND=casse fait lever hl.bind ; NOTIF=exec retire hl.notification (cas sans l'API)
ENTETE = r'''
package.path = os.getenv("CFG") .. "/?.lua;" .. package.path
local proxy; proxy = setmetatable({}, { __index = function() return proxy end, __call = function() return proxy end })
local mons = {
  { name = "DP-1", width = 3840, height = 2160, scale = 1, x = 0, y = 0, description = "a", physical_width = 600, physical_height = 340 },
  { name = "HDMI-A-1", width = 3840, height = 2160, scale = 1, x = 3840, y = 0, description = "b", physical_width = 600, physical_height = 340 },
}
last, handlers, notifs, execs, nbinds = {}, {}, {}, {}, 0
hl = {
  version = function() return "0.55.2" end, config = function() end, env = function() end,
  on = function(e, f) handlers[e] = handlers[e] or {}; table.insert(handlers[e], f) end,
  exec_cmd = function(c) execs[#execs + 1] = c end,
  bind = function(k)
    if os.getenv("MODE_BIND") == "casse" or (type(k) == "string" and k:find("BIDON")) then error("invalid modifier") end
    nbinds = nbinds + 1
    return {}
  end,
  monitor = function(s) if s.output == "PIEGE" then error("spec invalide") end last[s.output] = s.scale end,
  get_monitors = function() return mons end, get_active_monitor = function() return mons[1] end,
  get_windows = function() return {} end, get_active_window = function() end, get_active_workspace = function() end,
  get_config = function() return nil end, curve = function() end, animation = function() end, window_rule = function() end,
  layer_rule = function() end, workspace_rule = function() end, gesture = function() end, device = function() end,
  define_submap = function(n, f) f() end, timer = function() end, dsp = proxy, dispatch = function() end,
  get_cursor_pos = function() end,
  notification = { create = function(t) notifs[#notifs + 1] = t end },
}
if os.getenv("NOTIF") == "exec" then hl.notification = nil end
'''


@unittest.skipUnless(shutil.which("lua"), "Lua requis")
class Chargement(unittest.TestCase):
    def lancer(self, apres, perso=None, env=None, conf=None):
        with tempfile.TemporaryDirectory() as d:
            home = Path(d)
            cfg = home / ".config/hypr"
            cfg.mkdir(parents=True)
            (cfg / "hyprland.lua").symlink_to(HYPR / "hyprland.lua")
            (cfg / "nc").symlink_to(HYPR / "nc")
            if conf:
                (home / ".config/nc").mkdir(parents=True)
                (home / ".config/nc/raccourcis.conf").write_text(conf)
            if perso:
                (cfg / "perso.lua").write_text(perso)
            e = dict(os.environ, HOME=str(home), CFG=str(cfg), XDG_CONFIG_HOME=str(home / ".config"), NC_LANGUE="fr")
            e.update(env or {})
            code = ENTETE + f'dofile("{cfg}/hyprland.lua")\n' + apres
            r = subprocess.run(["lua", "-"], input=code, text=True, capture_output=True, timeout=30, env=e)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            return r.stdout

    def test_statique_aucun_require_nu(self):
        src = (HYPR / "hyprland.lua").read_text()
        self.assertIsNone(re.search(r'^\s*require\(', src, re.M), "tout passe par nc.charger")
        self.assertIn('nc.charger("perso")', src)
        self.assertIn("nc.signaler_echecs()", src)

    def test_module_en_echec_n_arrete_pas_les_suivants(self):
        out = self.lancer('print("suite", nc.mode_jeu ~= nil, #notifs, notifs[1] and (notifs[1].text:gsub("\\n", " ")))',
                          env={"MODE_BIND": "casse"})
        ligne = out.strip().splitlines()[-1].split("\t")
        self.assertEqual(ligne[1], "true", "un module après nc.raccourcis est quand même chargé : " + out)
        self.assertEqual(ligne[2], "1", "une seule notification")
        self.assertIn("nc.raccourcis", ligne[3])

    def test_sans_echec_pas_de_notification(self):
        out = self.lancer('print("n", #notifs, #nc.echecs)')
        self.assertEqual(out.strip().splitlines()[-1].split("\t")[1:], ["0", "0"], out)

    def test_repli_notify_send(self):
        out = self.lancer('local n = 0 for _, c in ipairs(execs) do if c:find("notify%-send") then n = n + 1 end end print("n", n)',
                          env={"MODE_BIND": "casse", "NOTIF": "exec"})
        self.assertEqual(out.strip().splitlines()[-1].split("\t")[1], "1", out)

    def test_perso_en_echec_signale(self):
        out = self.lancer('print("n", #notifs, notifs[1] and (notifs[1].text:gsub("\\n", " ")))', perso='error("boum")')
        l = out.strip().splitlines()[-1].split("\t")
        self.assertEqual(l[1], "1", out)
        self.assertIn("perso", l[2])

    def test_ecran_de_perso_garde_son_echelle(self):
        perso = 'hl.monitor({ output = "HDMI-A-1", mode = "preferred", position = "auto", scale = 1 })\n'
        # l'échelle calculée ne vaut 1 pour personne : on force un écran 4K de 27" -> échelle > 1 hors perso
        apres = r'''
for _, m in ipairs(hl.get_monitors()) do m.physical_width = 600 end
last["HDMI-A-1"] = nil; last["DP-1"] = nil
nc.ecrans_infos_poser({ ["HDMI-A-1"] = { modes = { "3840x2160@60.00Hz" }, pw = 600, ph = 340, reserved = {} } })
print("a", last["HDMI-A-1"], last["DP-1"])
last["HDMI-A-1"] = nil
for _, f in ipairs(handlers["monitor.added"]) do f() end
print("b", last["HDMI-A-1"], last["DP-1"], nc.ecrans_perso["HDMI-A-1"], hl.monitor ~= nil)
'''
        out = self.lancer(apres, perso=perso).strip().splitlines()
        a = out[-2].split("\t"); b = out[-1].split("\t")
        self.assertEqual(a[1], "nil", "ecrans_infos_poser ne réapplique pas l'écran de perso")
        self.assertNotEqual(a[2], "nil", "les autres écrans sont réappliqués")
        self.assertEqual(b[1], "nil", "monitor.added non plus")
        self.assertEqual(b[3], "true")

    def test_ecran_de_perso_en_prefixe_desc(self):
        # Hyprland compare « desc:… » au DÉBUT de la description (CMonitor::matchesStaticSelector)
        perso = 'hl.monitor({ output = "desc:b", scale = 1 })\n'
        apres = r'''
last["HDMI-A-1"] = nil; last["DP-1"] = nil
nc.ecrans_infos_poser({})
print("a", last["HDMI-A-1"], last["DP-1"] ~= nil)
'''
        a = self.lancer(apres, perso=perso).strip().splitlines()[-1].split("\t")
        self.assertEqual(a[1:], ["nil", "true"], "description « b » : préfixe de la description de HDMI-A-1")

    def test_hl_monitor_qui_leve_ne_bloque_pas_la_regle(self):
        perso = 'hl.monitor({ output = "PIEGE" })\n'   # le faux hl.monitor lève pour PIEGE
        out = self.lancer('print("n", nc.ecrans_perso["PIEGE"], #nc.echecs)', perso=perso).strip().splitlines()[-1].split("\t")
        self.assertEqual(out[1], "nil", "sortie non notée quand hl.monitor lève")
        apres = r'''
last["HDMI-A-1"] = nil
nc.ecrans_infos_poser({})
print("a", last["HDMI-A-1"] ~= nil)
'''
        perso2 = 'pcall(hl.monitor, { output = "HDMI-A-1", scale = 1, bidon = true }) pcall(function() hl.monitor({ output = "PIEGE" }) end)\n'
        out = self.lancer(apres, perso=perso2).strip().splitlines()[-1].split("\t")
        self.assertEqual(out[1], "false", "contrôle : HDMI-A-1 posé par perso est bien sauté")

    def test_change_invalide_ne_casse_pas_raccourcis(self):
        conf = "change\t64:code:36\tBIDON + x\n"
        out = self.lancer('local n = 0 for _, e in ipairs(nc.echecs) do n = n + 1 end print("n", n, nbinds, #notifs)',
                          conf=conf).strip().splitlines()[-1].split("\t")
        self.assertEqual(out[1], "0", "nc.raccourcis ne figure pas dans nc.echecs")
        self.assertGreater(int(out[2]), 20, "les autres raccourcis sont posés")
        self.assertEqual(out[3], "0")

    def test_coupe_du_message_sur_un_caractere_entier(self):
        perso = 'error(string.rep("a", 159) .. "éé fin", 0)'
        out = self.lancer('print("n", notifs[1].text)', perso=perso)
        texte = out.split("\t", 1)[1] if "\t" in out else out
        texte.encode("utf-8")            # lève si un octet est coupé en deux
        self.assertIn("\n" + "a" * 159, texte)
        self.assertNotIn("\ufffd", texte)

    def test_sans_perso_les_ecrans_sont_reappliques(self):
        apres = 'last["HDMI-A-1"] = nil nc.ecrans_infos_poser({}) print("a", last["HDMI-A-1"] ~= nil, next(nc.ecrans_perso))'
        out = self.lancer(apres).strip().splitlines()[-1].split("\t")
        self.assertEqual(out[1], "true")


if __name__ == "__main__":
    unittest.main()

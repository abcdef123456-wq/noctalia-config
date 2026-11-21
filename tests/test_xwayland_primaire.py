"""Lot J47 : l'écran primaire de XWayland suit l'écran actif (nc-xwayland-primaire, bloc de nc/ecrans.lua), et les
jeux en plein écran en option (JEUX_PLEIN_ECRAN, règle « jeux » de nc/regles.lua). Faux /proc, faux xrandr qui note
ses arguments, dossier temporaire : rien de la vraie session n'est touché, aucun vrai xrandr."""
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "home/.local/bin/nc-xwayland-primaire"
ECRANS = (REPO / "home/.config/hypr/nc/ecrans.lua").read_text()
REGLES = (REPO / "home/.config/hypr/nc/regles.lua").read_text()
LUA = shutil.which("lua5.4") or shutil.which("lua")


class Script(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.TemporaryDirectory(prefix="nc-xw-")
        self.d = Path(self.t.name)
        self.run_ = self.d / "run"; self.run_.mkdir(mode=0o700)
        self.proc = self.d / "proc"; self.proc.mkdir()
        self.bin = self.d / "bin"; self.bin.mkdir()
        self.xrandr(0)

    def tearDown(self):
        self.t.cleanup()

    def xrandr(self, code):
        x = self.bin / "xrandr"
        x.write_text(f'#!/bin/sh\necho "xrandr $*" >> "{self.d}/appels"\nexit {code}\n')
        x.chmod(0o755)

    def processus(self, pid, nom, uid=None):
        p = self.proc / str(pid); p.mkdir()
        (p / "status").write_text(f"Name:\t{nom}\nUmask:\t0022\nState:\tS\nUid:\t{os.getuid() if uid is None else uid}\t0\t0\t0\n")

    def lancer(self, *args, env=None, code=0):
        e = {"PATH": f"{self.bin}:/usr/bin:/bin", "XDG_RUNTIME_DIR": str(self.run_), "DISPLAY": ":1", "NC_XWAYLAND_PROC": str(self.proc),
             "HOME": str(self.d)}
        e.update(env or {})
        r = subprocess.run([sys.executable, str(SCRIPT), *args], env={k: v for k, v in e.items() if v is not None},
                           capture_output=True, text=True, timeout=30)
        self.assertEqual(r.returncode, code, r.stdout + r.stderr)
        return r

    def appels(self):
        f = self.d / "appels"
        return f.read_text().splitlines() if f.exists() else []

    def test_pose_une_fois_puis_dedoublonne(self):
        self.processus(4242, "Xwayland")
        self.processus(77, "kitty")
        self.lancer("DP-1")
        self.lancer("DP-1")
        self.assertEqual(self.appels(), ["xrandr --output DP-1 --primary"])
        etat = self.run_ / "nc-xwayland-primaire"
        self.assertEqual(etat.read_text(), "4242|:1|DP-1\n")
        self.assertEqual(etat.stat().st_mode & 0o777, 0o600)
        self.lancer("eDP-1")
        self.assertEqual(self.appels()[-1], "xrandr --output eDP-1 --primary")
        self.assertFalse([f for f in self.run_.iterdir() if f.name.startswith(".nc-xwayland")])    # pas de fichier temporaire

    def test_xwayland_absent_ou_d_un_autre_utilisateur_rien(self):
        self.lancer("DP-1")
        self.processus(500, "Xwayland", uid=os.getuid() + 1)
        self.lancer("DP-1")
        self.assertEqual(self.appels(), [])
        self.assertFalse((self.run_ / "nc-xwayland-primaire").exists())

    def test_nouveau_xwayland_reposé(self):
        """Xwayland redémarré (autre pid) : le primaire est reposé, même nom d'écran."""
        self.processus(10, "Xwayland")
        self.lancer("DP-1")
        shutil.rmtree(self.proc / "10")
        self.processus(11, "Xwayland")
        self.lancer("DP-1")
        self.assertEqual(len(self.appels()), 2)

    def test_deux_xwayland(self):
        """Deux Xwayland de cet utilisateur : xrandr vise celui de DISPLAY ; l'état les retient tous les deux."""
        self.processus(30, "Xwayland")
        self.processus(20, "Xwayland")
        self.lancer("DP-1")
        self.assertEqual(self.appels(), ["xrandr --output DP-1 --primary"])
        self.assertEqual((self.run_ / "nc-xwayland-primaire").read_text(), "20,30|:1|DP-1\n")

    def test_echec_de_xrandr_silencieux_et_rien_note(self):
        self.processus(9, "Xwayland")
        self.xrandr(1)                                   # sortie inconnue (vieux XWayland : XWAYLAND0…)
        r = self.lancer("DP-1")
        self.assertEqual(r.stdout + r.stderr, "")
        self.assertFalse((self.run_ / "nc-xwayland-primaire").exists())
        self.xrandr(0)
        self.lancer("DP-1")
        self.assertEqual(len(self.appels()), 2)          # réessayé, puisque rien n'avait été noté

    def test_refus_et_silences(self):
        self.processus(9, "Xwayland")
        for nom in ("--inconnu", "-x", "a;b", "DP 1", "", "a" * 33, "../x", "é"):
            with self.subTest(nom):
                self.lancer(nom, code=2)
        self.lancer(code=2)
        self.lancer("DP-1", "eDP-1", code=2)
        self.lancer("DP-1", env={"XDG_RUNTIME_DIR": None})
        self.lancer("DP-1", env={"XDG_RUNTIME_DIR": "relatif"})
        self.lancer("DP-1", env={"DISPLAY": None})
        (self.bin / "xrandr").unlink()
        self.lancer("DP-1")
        self.assertEqual(self.appels(), [])
        self.lancer("a" * 32)                              # 32 : accepté (sans xrandr, rien)


ENTETE_LUA = r'''
local appels, actif, ecrans, handlers = {}, "eDP-1", { "eDP-1", "DP-1" }, {}
hl = {
  get_active_monitor = function() return { name = actif } end,
  get_monitors = function() local t = {} for _, n in ipairs(ecrans) do t[#t + 1] = { name = n } end return t end,
  exec_cmd = function(c) appels[#appels + 1] = c end,
  on = function(e, f) handlers[e] = handlers[e] or {}; table.insert(handlers[e], f) end,
}
local function feu(e, a) for _, f in ipairs(handlers[e] or {}) do f(a) end end
local function n() return #appels end
local function voir(ok, m) if not ok then io.stderr:write("ECHEC: " .. m .. " ; appels=" .. table.concat(appels, " | ") .. "\n"); os.exit(2) end end
'''


@unittest.skipUnless(LUA, "Lua requis")
class Lua(unittest.TestCase):
    def bloc(self):
        i = ECRANS.index("-- ── XWayland : l'écran primaire suit l'écran actif")
        j = ECRANS.index("-- ── fin du primaire de XWayland")
        virtuel = re.search(r"^local function virtuel\(m\).*$", ECRANS, re.M)[0]
        return virtuel + "\n" + ECRANS[i:j]

    def lua(self, corps):
        r = subprocess.run([LUA, "-"], input=ENTETE_LUA + self.bloc() + corps + "\nprint('FINI')\n", text=True, capture_output=True, timeout=20)
        self.assertIn("FINI", r.stdout, r.stdout + r.stderr)

    def test_window_active_ne_lance_rien_tant_que_l_ecran_ne_change_pas(self):
        self.lua(r'''
feu("window.active", {}); voir(n() == 1, "premier écran posé")
for i = 1, 20 do feu("window.active", {}); feu("workspace.active", {}) end
voir(n() == 1, "aucun processus tant que l'écran actif ne change pas")
actif = "DP-1"; feu("window.active", {}); voir(n() == 2 and appels[2] == "~/.local/bin/nc-xwayland-primaire DP-1", "écran changé")
feu("workspace.active", {}); voir(n() == 2, "workspace.active sur le même écran : rien")
feu("monitor.added", {}); voir(n() == 3, "écran branché : reposé (le script dédoublonne)")
feu("monitor.removed", {}); voir(n() == 4, "écran débranché : reposé")
feu("hyprland.start", {}); voir(n() == 5, "démarrage")
feu("window.open", { class = "firefox" }); voir(n() == 5, "une fenêtre ordinaire : rien")
for _, c in ipairs({ "steam", "steam_app_1091500", "gamescope", "Game.exe" }) do feu("window.open", { class = c }) end
voir(n() == 9, "Steam ou un jeu s'ouvre : appelé")
''')

    def test_un_seul_ecran_ou_nom_refuse_rien(self):
        self.lua(r'''
ecrans = { "eDP-1", "HEADLESS-2", "FALLBACK" }
for _, a in ipairs({ "eDP-1", "HEADLESS-2", "DP-1" }) do actif = a; feu("window.active", {}); feu("monitor.added", {}) end
voir(n() == 0, "un seul vrai écran : rien")
ecrans = { "eDP-1", "DP-1" }
for _, a in ipairs({ "x;rm -rf ~", "-x", "DP 1", "", string.rep("a", 33) }) do actif = a; feu("monitor.added", {}) end
voir(n() == 0, "nom refusé : rien")
actif = "DP-1"; feu("window.active", {}); voir(n() == 1, "nom valide")
''')


@unittest.skipUnless(LUA, "Lua requis")
class PleinEcran(unittest.TestCase):
    def regle(self, valeur):
        i = REGLES.index("local jeux = {")
        j = REGLES.index("hl.window_rule(jeux)") + len("hl.window_rule(jeux)")
        code = ("local vu\nhl = { window_rule = function(t) vu = t end }\nnc = { reglage = function(c, d) assert(c == 'JEUX_PLEIN_ECRAN' and d == false); return %s end }\n"
                % valeur) + REGLES[i:j] + "\nlocal cles = {} for k in pairs(vu) do cles[#cles + 1] = k end table.sort(cles)\nprint(table.concat(cles, ',') .. ' ' .. tostring(vu.fullscreen))\n"
        r = subprocess.run([LUA, "-"], input=code, text=True, capture_output=True, timeout=20)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout.strip()

    def test_non_rien_ne_change_oui_plein_ecran(self):
        self.assertEqual(self.regle("false"), "content,immediate,match,name nil")
        self.assertEqual(self.regle("true"), "content,fullscreen,immediate,match,name true")
        self.assertNotIn("fullscreen_state", REGLES[REGLES.index("local jeux = {"):REGLES.index("hl.window_rule(jeux)")])

    def test_reglage_non_par_defaut_section_fenetres(self):
        r = subprocess.run([sys.executable, str(REPO / "home/.local/bin/nc-reglages"), "get", "JEUX_PLEIN_ECRAN"], capture_output=True, text=True,
                           env={"HOME": "/nonexistent", "PATH": "/usr/bin:/bin", "NC_LANGUE": "fr"}, timeout=30)
        self.assertEqual(r.stdout.strip(), "non", r.stdout + r.stderr)
        src = (REPO / "home/.local/bin/nc-reglages").read_text()
        self.assertRegex(src, r'R\("JEUX_PLEIN_ECRAN", "Fenêtres", .*"ouinon", "non"')
        bloc = src[src.index('R("JEUX_PLEIN_ECRAN"'):src.index('R("FENETRES_FOCUS_DEMANDE"')]
        self.assertIn('groupe="hypr"', bloc)                # appliqué par hyprctl reload, comme les autres réglages de fenêtres


if __name__ == "__main__":
    unittest.main()

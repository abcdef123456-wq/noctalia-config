"""Terminal déroulant (special:term) rangé dès qu'on va ailleurs : une autre fenêtre activée, sur cet écran ou un autre
(l'écran du terminal repris un instant, puis la fenêtre choisie), un autre bureau ; jamais quand c'est lui qui s'active.
La zone de l'île qui range au clic sur le bureau vide n'existe que tant qu'il est sorti."""
from pathlib import Path
import shutil
import subprocess
import unittest

REPO = Path(__file__).resolve().parents[1]


@unittest.skipUnless(shutil.which("lua"), "Lua requis")
class TerminalDeroulant(unittest.TestCase):
    def test_range_quand_on_va_ailleurs(self):
        source = (REPO / "home/.config/hypr/nc/automatismes.lua").read_text()
        debut = source.index("-- Terminal déroulant (Super + touche sous Échap")
        fin = source.index("-- Fenêtre réduite (nc-fenetre", debut)
        harness = r'''
local handlers, actions, monitors, actif = {}, {}, {}, nil
hl = {
 on = function(e, f) handlers[e] = f end,
 get_monitors = function() return monitors end,
 get_active_monitor = function() return actif end,
 dispatch = function(a) actions[#actions + 1] = a end,
 dsp = { focus = function(t) return t.monitor and ("focus monitor " .. t.monitor) or ("focus " .. t.window) end,
         workspace = { toggle_special = function(n) return "toggle " .. n end } },
}
''' + source[debut:fin] + r'''
local function etat(term_sur)
 monitors = { { name = "A", active_special_workspace = term_sur == "A" and { name = "special:term" } or nil },
              { name = "B", active_special_workspace = term_sur == "B" and { name = "special:term" } or nil } }
 actions = {}
end
-- Une autre fenêtre sur l'écran du terminal : rangé
etat("A"); actif = monitors[1]
handlers["window.active"]({ address = "0x1", workspace = { name = "1" } })
assert(#actions == 1 and actions[1] == "toggle term", "fenêtre du même écran : " .. table.concat(actions, ", "))
-- Le terminal lui-même qui s'active : rien
etat("A"); handlers["window.active"]({ address = "0x2", workspace = { name = "special:term" } })
assert(#actions == 0, "le terminal lui-même")
-- Terminal rangé : rien
etat(nil); handlers["window.active"]({ address = "0x1", workspace = { name = "1" } })
assert(#actions == 0, "déjà rangé")
-- Une fenêtre d'un autre écran : l'écran du terminal un instant, rangé, puis retour à la fenêtre cliquée
etat("A"); actif = monitors[2]
handlers["window.active"]({ address = "0x9", workspace = { name = "2" } })
assert(table.concat(actions, ", ") == "focus monitor A, toggle term, focus address:0x9", table.concat(actions, ", "))
-- Un autre bureau sur l'écran du terminal : rangé ; sur un autre écran : rien ; un bureau caché : rien
etat("A"); actif = monitors[1]
handlers["workspace.active"]({ name = "3", monitor = { name = "A" } })
assert(#actions == 1 and actions[1] == "toggle term", "autre bureau")
etat("A"); handlers["workspace.active"]({ name = "3", monitor = { name = "B" } })
assert(#actions == 0, "bureau d'un autre écran")
etat("A"); handlers["workspace.active"]({ name = "special:term", monitor = { name = "A" } })
assert(#actions == 0, "le bureau caché lui-même")
print("TERMINAL_OK")
'''
        r = subprocess.run(["lua", "-"], input=harness, text=True, capture_output=True, timeout=5)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("TERMINAL_OK", r.stdout)

    def test_zone_de_l_ile_seulement_quand_il_est_sorti(self):
        qml = (REPO / "home/.config/quickshell/nc-ile/RangeTerminal.qml").read_text()
        self.assertIn('model: r.ecran === "" ? []', qml)
        self.assertIn("WlrLayer.Bottom", qml, "sous les fenêtres : un clic sur une fenêtre lui revient")
        self.assertIn("RangeTerminal {}", (REPO / "home/.config/quickshell/nc-ile/shell.qml").read_text())


if __name__ == "__main__":
    unittest.main()

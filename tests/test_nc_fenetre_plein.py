"""nc-fenetre plein-masquer / plein-rendre (plein écran qui masque) avec un faux hyprctl qui note ses appels."""
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
NC_FENETRE = REPO / "home/.local/bin/nc-fenetre"

FAKE_HYPR = r'''#!/usr/bin/env python3
import json, os, re, sys
from pathlib import Path
p = Path(os.environ["NC_TEST_STATE"]); d = json.loads(p.read_text())
cmd = " ".join(sys.argv[1:])
with open(os.environ["NC_TEST_APPELS"], "a") as f:
    f.write(cmd + "\n")
if cmd == "clients -j":
    print(json.dumps(d["clients"]))
elif cmd == "monitors -j":
    print(json.dumps([dict(id=0, name="T", x=0, y=0, width=1600, height=1000, scale=1, transform=0, focused=True,
                           activeWorkspace=dict(id=1), specialWorkspace=dict(name=""))]))
elif cmd == "cursorpos":
    print("12, 34")
elif cmd == "activewindow -j":
    print(json.dumps(next((c for c in d["clients"] if c["address"] == d.get("active")), {})))
elif cmd.startswith("dispatch"):
    if "window.move(" in cmd:
        a = re.search(r"address:(0x[0-9a-fA-F]+)", cmd)[1]
        m = re.search(r"workspace = ('[^']+'|[0-9]+)", cmd)[1].strip("'")
        for c in d["clients"]:
            if c["address"] == a:
                c["workspace"] = dict(id=-99 if m == "special:reduites" else int(m), name=m)
        # fenêtre qui se ferme pendant le masquage
        if m == "special:reduites" and a in d.get("ferme_au_masquage", []):
            d["clients"] = [c for c in d["clients"] if c["address"] != a]
        p.write_text(json.dumps(d))
    elif "focus(" in cmd:
        d["active"] = re.search(r"address:(0x[0-9a-fA-F]+)", cmd)[1]; p.write_text(json.dumps(d))
else:
    sys.exit(1)
'''

def client(adresse, ws, pinned=False):
    return dict(address=adresse, at=[0, 0], size=[400, 300], workspace=dict(id=ws, name=str(ws)), monitor=0,
                floating=False, pinned=pinned)

class PleinMasque(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "bin").mkdir()
        for nom, code in [("hyprctl", FAKE_HYPR), ("sleep", "#!/bin/sh\nexit 0\n")]:
            f = self.root / "bin" / nom
            f.write_text(code); f.chmod(0o755)
        self.state = self.root / "state.json"
        self.appels = self.root / "appels.log"
        self.appels.write_text("")
        self.env = dict(os.environ, HOME=str(self.root), XDG_RUNTIME_DIR=str(self.root), NC_LANGUE="fr",
                        PATH=str(self.root / "bin") + os.pathsep + os.environ["PATH"],
                        NC_TEST_STATE=str(self.state), NC_TEST_APPELS=str(self.appels))
        self.plein = self.root / "nc-reduites-plein"

    def donner(self, clients, **autres):
        self.state.write_text(json.dumps(dict(clients=clients, **autres)))

    def fen(self, *args):
        return subprocess.run(["bash", str(NC_FENETRE), *args], env=self.env, capture_output=True, text=True, timeout=30)

    def bureaux(self):
        return {c["address"]: c["workspace"]["name"] for c in json.loads(self.state.read_text())["clients"]}

    def lignes(self):
        return self.plein.read_text().splitlines() if self.plein.exists() else []

    def dispatchs(self):
        return [l for l in self.appels.read_text().splitlines() if l.startswith("dispatch")]

    def test_masquer_puis_rendre(self):
        self.donner([client("0x1", 1), client("0x2", 1), client("0x3", 1), client("0x4", 2)])
        r = self.fen("plein-masquer", "0x1")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.bureaux(), {"0x1": "1", "0x2": "special:reduites", "0x3": "special:reduites", "0x4": "2"})
        self.assertEqual(self.lignes(), ["0x1 1 0x2 0x3"])
        r = self.fen("plein-rendre", "0x1")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.bureaux(), {"0x1": "1", "0x2": "1", "0x3": "1", "0x4": "2"})
        self.assertFalse(self.plein.exists(), "plus de propriétaire : fichier retiré")
        self.assertEqual((self.root / "nc-reduites").read_text().strip(), "")

    def test_nom_anglais(self):
        self.donner([client("0x1", 1), client("0x2", 1)])
        self.assertEqual(self.fen("fullscreen-hide", "0x1").returncode, 0)
        self.assertEqual(self.lignes(), ["0x1 1 0x2"])
        self.assertEqual(self.fen("fullscreen-restore", "0x1").returncode, 0)
        self.assertEqual(self.bureaux()["0x2"], "1")

    def test_epinglee_non_masquee(self):
        self.donner([client("0x1", 1), client("0x2", 1, pinned=True), client("0x3", 1)])
        self.assertEqual(self.fen("plein-masquer", "0x1").returncode, 0)
        self.assertEqual(self.bureaux()["0x2"], "1")
        self.assertEqual(self.lignes(), ["0x1 1 0x3"])

    def test_adresse_invalide_sans_appel(self):
        self.donner([client("0x1", 1)])
        for mauvaise in ["", "abc", "0x", "0x1;rm", "0x1' }) os.exit() --", "$(id)", "0xZZ"]:
            for action in ("plein-masquer", "plein-rendre"):
                r = self.fen(action, mauvaise)
                self.assertEqual(r.returncode, 2, (action, mauvaise, r.stderr))
        self.assertEqual(self.appels.read_text(), "", "aucun appel à hyprctl")

    def test_pile_absente_rien(self):
        self.donner([client("0x1", 1), client("0x2", 1)])
        self.assertEqual(self.fen("plein-rendre", "0x1").returncode, 0)
        self.assertEqual(self.dispatchs(), [])
        self.assertFalse(self.plein.exists())

    def test_seul_sur_son_bureau_pas_de_ligne(self):
        self.donner([client("0x1", 1), client("0x4", 2)])
        self.assertEqual(self.fen("plein-masquer", "0x1").returncode, 0)
        self.assertEqual(self.lignes(), [])
        self.assertEqual(self.bureaux()["0x4"], "2")

    def test_masquee_fermee_pendant_le_masquage(self):
        self.donner([client("0x1", 1), client("0x2", 1), client("0x3", 1)], ferme_au_masquage=["0x2"])
        self.fen("plein-masquer", "0x1")
        self.assertEqual(self.lignes(), ["0x1 1 0x3"], "la fermée n'est pas notée")
        # fermée aussi après coup : le rendu ne plante pas
        d = json.loads(self.state.read_text())
        d["clients"] = [c for c in d["clients"] if c["address"] != "0x3"]
        self.state.write_text(json.dumps(d))
        r = self.fen("plein-rendre", "0x1")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertFalse(self.plein.exists())

    def test_deux_pleins_ecrans_deux_bureaux(self):
        self.donner([client("0x1", 1), client("0x2", 1), client("0xa", 2), client("0xb", 2)])
        self.fen("plein-masquer", "0x1"); self.fen("plein-masquer", "0xa")
        self.assertEqual(sorted(self.lignes()), ["0x1 1 0x2", "0xa 2 0xb"])
        self.fen("plein-rendre", "0x1")
        self.assertEqual(self.lignes(), ["0xa 2 0xb"])
        self.assertEqual(self.bureaux(), {"0x1": "1", "0x2": "1", "0xa": "2", "0xb": "special:reduites"})

    def test_rappel_par_aller(self):
        """Une masquée rappelée : le propriétaire quitte le maximisé, toutes ses masquées reviennent, la rappelée a le focus."""
        self.donner([client("0x1", 1), client("0x2", 1), client("0x3", 1)])
        self.fen("plein-masquer", "0x1")
        r = self.fen("aller", "0x2")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.bureaux(), {"0x1": "1", "0x2": "1", "0x3": "1"})
        self.assertFalse(self.plein.exists())
        unset = [l for l in self.dispatchs() if "window.fullscreen" in l and "action = 'unset'" in l]
        self.assertTrue(all("address:0x1" in l for l in unset) and unset, unset)
        self.assertEqual(json.loads(self.state.read_text()).get("active"), "0x2")

    def test_aller_fenetre_normale_sans_unset(self):
        self.donner([client("0x1", 1), client("0x2", 1)])
        self.fen("reduire", "0x2")
        self.assertEqual(self.fen("aller", "0x2").returncode, 0)
        self.assertEqual([l for l in self.dispatchs() if "window.fullscreen" in l], [])

LUA = REPO / "home/.config/hypr/nc/automatismes.lua"
ENTETE_LUA = r'''
local proxy; proxy = setmetatable({}, { __index = function() return proxy end, __call = function() return proxy end })
handlers, cmds = {}, {}
hl = {
  on = function(e, f) handlers[e] = handlers[e] or {}; table.insert(handlers[e], f) end,
  exec_cmd = function(c) cmds[#cmds + 1] = c end,
  get_config = function() return nil end, bind = function() end, timer = function() end,
  get_windows = function() return {} end, get_active_window = function() end,
  get_active_monitor = function() return { x = 0, y = 0, width = 2000, height = 1000, scale = 1 } end,
  dsp = proxy, dispatch = function() end,
}
nc = { profil = { profil = "balanced" }, jeu = false, hypr_min = function() return true end,
       reglage = function(_, d) return d end, t = function(fr) return fr end,
       guillemets = function(s) return "'" .. s .. "'" end }
function nc.mode_jeu() end
dofile(FICHIER)
function emettre(e, w) for _, f in ipairs(handlers[e] or {}) do f(w) end end
'''


@unittest.skipUnless(shutil.which("lua"), "Lua requis")
class AutomatismesPlein(unittest.TestCase):
    def lancer(self, corps, plein=None):
        with tempfile.TemporaryDirectory() as d:
            if plein is not None:
                (Path(d) / "nc-reduites-plein").write_text(plein)
            code = ENTETE_LUA.replace("FICHIER", json.dumps(str(LUA))) + corps
            r = subprocess.run(["lua", "-"], input=code, text=True, capture_output=True, timeout=20,
                               env=dict(HOME=d, PATH="/usr/bin:/bin", XDG_RUNTIME_DIR=d, XDG_STATE_HOME=d + "/etat"))
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            return r.stdout.strip()

    COMMANDES = 'for _, c in ipairs(cmds) do if c:find("plein", 1, true) then print(c) end end'

    def test_sortie_du_maximise_rend(self):
        out = self.lancer('emettre("window.fullscreen", { address = "0x1a", fullscreen = 0 })\n' + self.COMMANDES,
                          plein="0x1a 1 0x2 0x3\n0xb 2 0xc\n")
        self.assertEqual(out, "~/.local/bin/nc-fenetre plein-rendre 0x1a")

    def test_encore_maximise_ne_rend_pas(self):
        out = self.lancer('emettre("window.fullscreen", { address = "0x1a", fullscreen = 1 })\n' + self.COMMANDES,
                          plein="0x1a 1 0x2\n")
        self.assertEqual(out, "")

    def test_fermeture_du_proprietaire_rend(self):
        out = self.lancer('emettre("window.close", { address = "0xb", class = "x" })\n' + self.COMMANDES,
                          plein="0x1a 1 0x2\n0xb 2 0xc\n")
        self.assertEqual(out, "~/.local/bin/nc-fenetre plein-rendre 0xb")

    def test_fermeture_dune_autre_ou_dune_masquee_ne_fait_rien(self):
        out = self.lancer('emettre("window.close", { address = "0xc" })\nemettre("window.close", { address = "0x1" })\n'
                          'emettre("window.fullscreen", { address = "0x2", fullscreen = 0 })\n' + self.COMMANDES,
                          plein="0x1a 1 0x2\n0xb 2 0xc\n")
        self.assertEqual(out, "", "0x1 n'est pas le début de 0x1a : pas de confusion de préfixe")

    def test_sans_pile_aucun_travail(self):
        corps = ('emettre("window.fullscreen", { address = "0x1a", fullscreen = 0 })\n'
                 'emettre("window.close", { address = "0x1a" })\n' + self.COMMANDES)
        self.assertEqual(self.lancer(corps), "")
        self.assertEqual(self.lancer(corps, plein=""), "")

    def test_adresse_bizarre_ignoree(self):
        out = self.lancer('emettre("window.close", { address = "0x1a\\n0x1a; rm" })\n' + self.COMMANDES, plein="0x1a 1 0x2\n")
        self.assertEqual(out, "")


if __name__ == "__main__":
    unittest.main()

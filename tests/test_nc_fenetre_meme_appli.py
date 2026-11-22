"""nc-fenetre meme-appli : fenêtre suivante de la même appli, avec un faux hyprctl qui note ses appels."""
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests import _isolation  # noqa: F401

REPO = Path(__file__).resolve().parents[1]
NC_FENETRE = REPO / "home/.local/bin/nc-fenetre"

FAKE_HYPR = r'''#!/usr/bin/env python3
import json, os, random, re, sys
from pathlib import Path
p = Path(os.environ["NC_TEST_STATE"]); d = json.loads(p.read_text())
cmd = " ".join(sys.argv[1:])
with open(os.environ["NC_TEST_APPELS"], "a") as f:
    f.write(cmd + "\n")
if cmd == "clients -j":
    c = list(d["clients"]); random.shuffle(c)   # l'ordre du JSON change à chaque appel
    print(json.dumps(c))
elif cmd == "monitors -j":
    print(json.dumps([dict(id=0, name="T", focused=True, activeWorkspace=dict(id=1), specialWorkspace=dict(name=""))]))
elif cmd == "activewindow -j":
    print(json.dumps(next((c for c in d["clients"] if c["address"] == d.get("active")), {})))
elif cmd.startswith("dispatch") and "focus(" in cmd:
    d["active"] = re.search(r"address:(0x[0-9a-fA-F]+)", cmd)[1]; p.write_text(json.dumps(d))
elif not cmd.startswith("dispatch"):
    sys.exit(1)
'''


def cl(adresse, classe="kitty", ws=(1, "1"), plein=0):
    return dict(address=adresse, **{"class": classe}, workspace=dict(id=ws[0], name=ws[1]), fullscreen=plein, mapped=True)


class MemeAppli(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "bin").mkdir()
        f = self.root / "bin" / "hyprctl"
        f.write_text(FAKE_HYPR); f.chmod(0o755)
        self.state = self.root / "state.json"
        self.appels = self.root / "appels.log"
        self.appels.write_text("")
        self.env = dict(os.environ, HOME=str(self.root), XDG_RUNTIME_DIR=str(self.root), NC_LANGUE="fr",
                        PATH=str(self.root / "bin") + os.pathsep + os.environ["PATH"],
                        NC_TEST_STATE=str(self.state), NC_TEST_APPELS=str(self.appels))

    def lancer(self, clients, active):
        self.state.write_text(json.dumps(dict(clients=clients, active=active)))
        self.appels.write_text("")
        subprocess.run(["bash", str(NC_FENETRE), "meme-appli"], env=self.env, check=True, timeout=20,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return json.loads(self.state.read_text())["active"]

    def focus(self):
        return [ligne for ligne in self.appels.read_text().splitlines() if "focus(" in ligne]

    def test_boucle_stable(self):
        cs = [cl("0xa"), cl("0xb"), cl("0xc"), cl("0xd", "firefox")]
        a = "0xa"
        suite = []
        for _ in range(4):
            a = self.lancer(cs, a)
            suite.append(a)
        self.assertEqual(suite, ["0xb", "0xc", "0xa", "0xb"])

    def test_reduite_sautee(self):
        cs = [cl("0xa"), cl("0xb", ws=(-99, "special:reduites")), cl("0xc")]
        self.assertEqual(self.lancer(cs, "0xa"), "0xc")

    def test_reduite_sautee_par_son_nom(self):
        # même si son numéro de bureau était celui de l'active, le nom du bureau caché suffit
        cs = [cl("0xa"), cl("0xb", ws=(1, "special:reduites")), cl("0xc")]
        self.assertEqual(self.lancer(cs, "0xa"), "0xc")

    def test_tous_les_bureaux_celui_ci_d_abord(self):
        # 0xa et 0xd sur le bureau 1, 0xb sur le 3, 0xc sur le 2 : 1 d'abord, puis 2, puis 3, en boucle (toutes atteintes)
        cs = [cl("0xa"), cl("0xb", ws=(3, "3")), cl("0xc", ws=(2, "2")), cl("0xd"), cl("0xe", "firefox", ws=(2, "2"))]
        a, suite = "0xa", []
        for _ in range(5):
            a = self.lancer(cs, a)
            suite.append(a)
        self.assertEqual(suite, ["0xd", "0xc", "0xb", "0xa", "0xd"])

    def test_depuis_un_autre_bureau_ses_voisines_d_abord(self):
        cs = [cl("0xa"), cl("0xb", ws=(2, "2")), cl("0xc", ws=(2, "2"))]
        self.assertEqual(self.lancer(cs, "0xb"), "0xc")

    def test_bureau_special_saute(self):
        # le terminal déroulant (special:term) ne surgit pas
        cs = [cl("0xa"), cl("0xb", ws=(-98, "special:term")), cl("0xc", ws=(2, "2"))]
        self.assertEqual(self.lancer(cs, "0xa"), "0xc")
        self.assertEqual(self.lancer(cs, "0xc"), "0xa", "le tour revient au début sans passer par le bureau spécial")

    def test_une_seule(self):
        self.lancer([cl("0xa"), cl("0xb", "firefox")], "0xa")
        self.assertEqual(self.focus(), [])

    def test_une_seule_apres_reduite(self):
        self.lancer([cl("0xa"), cl("0xb", ws=(-99, "special:reduites"))], "0xa")
        self.assertEqual(self.focus(), [])

    def test_pas_de_fenetre_active(self):
        self.lancer([cl("0xa"), cl("0xb")], "")
        self.assertEqual(self.focus(), [])

    def test_plein_ecran_rien(self):
        self.lancer([cl("0xa", plein=2), cl("0xb")], "0xa")
        self.assertEqual(self.focus(), [])


class Declaration(unittest.TestCase):
    def test_raccourci_declare_et_documente(self):
        lua = (REPO / "home/.config/hypr/nc/raccourcis.lua").read_text()
        self.assertIn('SUPER .. " + CTRL + code:52", cmd("~/.local/bin/nc-fenetre meme-appli")', lua)
        self.assertIn("Fenêtres|Fenêtre suivante de la même appli", lua)
        self.assertIn("| `Super` + `Ctrl` + `Z` | Fenêtre suivante de la même appli |",
                      (REPO / "RACCOURCIS.md").read_text())
        self.assertEqual(lua.count("code:52"), 1)


if __name__ == "__main__":
    unittest.main()

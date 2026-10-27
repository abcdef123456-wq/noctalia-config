"""Le tableau de bord de Neovim en français (lua/config/accueil.lua) et l'ouverture du projet par nc-code
(lua/config/projet.lua), dans un Neovim sans interface (--headless), HOME et dossiers XDG temporaires. Les entrées de
LazyVim sont celles de sa configuration d'origine, données ici à la main. Sauté si nvim est absent."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
NVIM_CONF = REPO / "home/.config/nvim"

INIT = """
vim.opt.rtp:prepend(vim.env.NC_NVIM)
"""
FIN = """
local f = io.open(vim.env.FAUX_DIR .. "/resultat.json", "w")
f:write(vim.json.encode(R)); f:close()
vim.cmd("qa!")
"""

TOUCHES = """
local function touches()
  return {
    { icon = " ", key = "f", desc = "Find File", action = ":x" },
    { icon = " ", key = "n", desc = "New File", action = ":x" },
    { icon = " ", key = "P", desc = "Projects (util.project)", action = ":x" },
    { icon = " ", key = "g", desc = "Find Text", action = ":x" },
    { icon = " ", key = "r", desc = "Recent Files", action = ":x" },
    { icon = " ", key = "c", desc = "Config", action = ":x" },
    { icon = " ", key = "s", desc = "Restore Session", section = "session" },
    { icon = " ", key = "x", desc = "Lazy Extras", action = ":LazyExtras" },
    { icon = "󰒲 ", key = "l", desc = "Lazy", action = ":Lazy" },
    { icon = " ", key = "q", desc = "Quit", action = ":qa" },
    { icon = " ", key = "p", desc = "Projects", action = ":x" },
    { icon = "󰚩 ", key = "i", desc = "Demander à l'IA", action = ":x" },
  }
end
"""


@unittest.skipUnless(shutil.which("nvim"), "nvim absent")
class NvimAccueil(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="nc-nvim-accueil-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.home = self.tmp / "home"
        self.home.mkdir()
        (self.tmp / "init.lua").write_text(INIT)
        self.faux = self.tmp / "faux"
        self.faux.mkdir()
        self.projet = self.tmp / "projet"
        self.projet.mkdir()

    def nvim(self, scenario, env_plus=None, cwd=None):
        (self.tmp / "scenario.lua").write_text("R = {}\n" + TOUCHES + scenario + FIN)
        env = dict(os.environ, HOME=str(self.home), FAUX_DIR=str(self.faux), NC_NVIM=str(NVIM_CONF))
        for cle, nom in (("XDG_CONFIG_HOME", "config"), ("XDG_DATA_HOME", "data"), ("XDG_STATE_HOME", "state"),
                         ("XDG_CACHE_HOME", "cache"), ("XDG_RUNTIME_DIR", "run")):
            (self.tmp / nom).mkdir(mode=0o700, exist_ok=True)
            env[cle] = str(self.tmp / nom)
        env.pop("NC_CODE", None)
        env.update(env_plus or {})
        subprocess.run(["nvim", "--headless", "-i", "NONE", "-u", str(self.tmp / "init.lua"), "-c", f"luafile {self.tmp / 'scenario.lua'}"],
                       env=env, cwd=cwd or self.tmp, timeout=60, capture_output=True)
        return json.loads((self.faux / "resultat.json").read_text())

    def test_tout_en_francais_sans_doublon(self):
        r = self.nvim("""
local opts = require("config.accueil").adapter({ dashboard = { preset = { keys = touches() } } })
local d = opts.dashboard
R.descs, R.cles = {}, {}
for _, t in ipairs(d.preset.keys) do table.insert(R.descs, t.desc); table.insert(R.cles, t.key) end
R.sections = #d.sections
R.pied = require("config.accueil").pied(4, 62, 23.64)
""")
        self.assertEqual(r["descs"], ["Chercher un fichier", "Nouveau fichier", "Projets", "Chercher du texte", "Fichiers récents",
                                      "Configuration", "Reprendre la session", "Extensions", "Plugins", "Quitter", "Demander à l'IA"])
        self.assertEqual(r["cles"], ["f", "n", "P", "g", "r", "c", "s", "x", "l", "q", "i"])      # les touches ne bougent pas
        for anglais in ("Find File", "Quit", "Projects", "New File", "Lazy", "Config"):
            self.assertNotIn(anglais, r["descs"])
        self.assertEqual(r["descs"].count("Projets"), 1)
        self.assertEqual(r["pied"], "Neovim prêt : 4/62 plugins en 23,6 ms")

    def test_aide_seulement_dans_nc_code(self):
        scen = """
local d = require("config.accueil").adapter({}).dashboard
R.premier = d.sections[1].text and d.sections[1].text[1][1] or ""
R.nb = #d.sections
"""
        dans = self.nvim(scen, {"NC_CODE": "1"})
        self.assertEqual(dans["premier"], "À droite : ton agent IA. Écris-lui ce que tu veux faire. Ici : tes fichiers.")
        hors = self.nvim(scen)
        self.assertEqual(hors["premier"], "")
        self.assertEqual(dans["nb"], hors["nb"] + 1)

    def test_aucun_texte_anglais_dans_la_config_du_depot(self):
        for f in ("lua/plugins/interface.lua", "lua/config/accueil.lua"):
            t = (NVIM_CONF / f).read_text()
            for mot in ('"Find File"', 'desc = "Quit"', "Neovim loaded"):
                if f.endswith("accueil.lua") and mot == '"Find File"':
                    continue                                              # la table de traduction cite l'anglais
                self.assertNotIn(mot, t)

    # ── l'ouverture du projet par nc-code ──
    def test_projet_session_reprise(self):
        r = self.nvim(f"""
local p = {{ load = function() R.charge = true end, current = function() return "{self.projet}/session.vim" end }}
vim.fn.writefile({{ "x" }}, "{self.projet}/session.vim")
vim.cmd.cd("{self.projet}")
R.mode = require("config.projet").ouvrir({{ persistence = p, explorateur = function() R.expl = true end }})
""")
        self.assertEqual((r["mode"], r.get("charge"), r.get("expl")), ("session", True, None))

    def test_projet_sans_session_readme_et_explorateur(self):
        (self.projet / "README.md").write_text("# Salut\n")
        (self.projet / "main.c").write_text("int main(void){}\n")
        r = self.nvim(f"""
local p = {{ load = function() R.charge = true end, current = function() return "{self.projet}/nexiste-pas.vim" end }}
vim.cmd.cd("{self.projet}")
R.mode = require("config.projet").ouvrir({{ persistence = p, explorateur = function() R.expl = true end }})
R.nom = vim.fn.fnamemodify(vim.api.nvim_buf_get_name(0), ":t")
""")
        self.assertEqual((r["mode"], r["nom"], r.get("charge"), r.get("expl")), ("fichier", "README.md", None, True))

    def test_projet_sans_readme_dernier_fichier_modifie(self):
        vieux, neuf = self.projet / "vieux.c", self.projet / "neuf.c"
        vieux.write_text("a\n")
        neuf.write_text("b\n")
        os.utime(vieux, (1_600_000_000, 1_600_000_000))
        r = self.nvim(f"""
vim.cmd.cd("{self.projet}")
R.fichier = vim.fn.fnamemodify(require("config.projet").fichier("{self.projet}"), ":t")
""")
        self.assertEqual(r["fichier"], "neuf.c")

    def test_pas_d_ouverture_sans_nc_code_ni_avec_fichier(self):
        r = self.nvim("""
R.argc = vim.fn.argc(-1)
local appele = false
local m = require("config.projet")
local ouvrir = m.ouvrir
m.ouvrir = function() appele = true end
m.au_demarrage()
vim.wait(100)
R.sans_nc_code = appele
""")
        self.assertFalse(r["sans_nc_code"])


if __name__ == "__main__":
    unittest.main()

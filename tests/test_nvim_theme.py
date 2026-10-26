"""Le thème « noctalia » de Neovim (lua/config/noctalia.lua) : tokyonight repeint avec palette-ile.json, rechargé
à chaud quand le fichier est réécrit, sans erreur si la palette manque ou est abîmée, sans effet si un autre
thème est choisi. Neovim sans interface (--headless), dossiers XDG temporaires, tokyonight.nvim ajouté en
lecture seule depuis le dossier de plugins de lazy. Sauté si nvim ou tokyonight.nvim manquent."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
NVIM_CONF = REPO / "home/.config/nvim"
# le vrai dossier de plugins de lazy (XDG_DATA_HOME est détourné par les tests), ajouté en lecture seule
TOKYO = Path.home() / ".local/share/nvim/lazy/tokyonight.nvim"

PALETTE = {
    "sombre": True, "fond": "#171e26", "texte": "#f2f2f3", "texteSec": "#afb2b6", "carte": "#1f262f",
    "carteSurvol": "#232a32", "gris3": "#323942", "gris4": "#3c444d", "gris5": "#4e5760", "accent": "#679fe4",
    "rouge": "#ef86a0", "vert": "#47c496", "jaune": "#c9cb61", "orange": "#fc9667", "bleu": "#6faefb",
    "violet": "#c293ea", "rose": "#ddb9fd", "cyan": "#6faefb",
}
CLAIRE = dict(PALETTE, sombre=False, fond="#f4f1ea", texte="#222222", carte="#e8e4da")

INIT = """
vim.opt.rtp:prepend(vim.env.NC_NVIM)
vim.opt.rtp:prepend(vim.env.NC_TOKYO)
vim.g.mapleader = " "
"""

PRELUDE = """
local nc = require("config.noctalia")
local function fond(groupe) return string.format("#%06x", vim.api.nvim_get_hl(0, { name = groupe, link = false }).bg) end
local function config(transparent)
  require("tokyonight").setup({ transparent = transparent or false, on_colors = function(c) nc.on_colors(c) end })
end
local function ecrire(p)
  local f = io.open(vim.env.XDG_CONFIG_HOME .. "/nc/palette-ile.json.tmp", "w")
  f:write(type(p) == "string" and p or vim.json.encode(p)); f:close()
  os.rename(vim.env.XDG_CONFIG_HOME .. "/nc/palette-ile.json.tmp", vim.env.XDG_CONFIG_HOME .. "/nc/palette-ile.json")
end
R = {}
local ok, err = pcall(function()
"""
FIN = """
end)
R.ok, R.err = ok, err and tostring(err)
local f = io.open(vim.env.FAUX_DIR .. "/resultat.json", "w")
f:write(vim.json.encode(R)); f:close()
vim.cmd("qa!")
"""


@unittest.skipUnless(shutil.which("nvim"), "nvim absent")
@unittest.skipUnless((TOKYO / "lua/tokyonight").is_dir(), "tokyonight.nvim absent")
class NvimTheme(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="nc-nvim-theme-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.home, self.faux = self.tmp / "home", self.tmp / "faux"
        self.faux.mkdir()
        (self.tmp / "config/nc").mkdir(parents=True)
        (self.tmp / "init.lua").write_text(INIT)

    def palette(self, contenu):
        p = self.tmp / "config/nc/palette-ile.json"
        p.write_text(contenu if isinstance(contenu, str) else json.dumps(contenu))

    def nvim(self, scenario):
        (self.tmp / "scenario.lua").write_text(PRELUDE + scenario + FIN)
        env = dict(os.environ, HOME=str(self.home), FAUX_DIR=str(self.faux), NC_NVIM=str(NVIM_CONF),
                   NC_TOKYO=str(TOKYO))
        for cle, nom in (("XDG_CONFIG_HOME", "config"), ("XDG_DATA_HOME", "data"), ("XDG_STATE_HOME", "state"),
                         ("XDG_CACHE_HOME", "cache"), ("XDG_RUNTIME_DIR", "run"), ("TMPDIR", "tmp")):
            (self.tmp / nom).mkdir(mode=0o700, exist_ok=True)
            env[cle] = str(self.tmp / nom)
        self.home.mkdir(exist_ok=True)
        env.pop("SSH_CONNECTION", None)
        cmd = ["nvim", "--headless", "-i", "NONE", "-u", str(self.tmp / "init.lua"),
               "-c", f"luafile {self.tmp / 'scenario.lua'}"]
        subprocess.run(cmd, env=env, cwd=self.tmp, timeout=60, capture_output=True)
        r = json.loads((self.faux / "resultat.json").read_text())
        self.assertTrue(r["ok"], r.get("err"))
        return r

    def test_couleurs_prises_dans_la_palette(self):
        self.palette(PALETTE)
        r = self.nvim("""
config(); nc.activer()
R.normal = fond("Normal"); R.nom = vim.g.colors_name; R.actif = nc.actif
R.carte = fond("StatusLine"); R.survol = fond("CursorLine")
R.fg = string.format("#%06x", vim.api.nvim_get_hl(0, { name = "Normal" }).fg)
R.bordure = string.format("#%06x", vim.api.nvim_get_hl(0, { name = "FloatBorder" }).fg)
""")
        self.assertEqual(r["normal"], PALETTE["fond"])
        self.assertEqual(r["nom"], "tokyonight-moon")
        self.assertEqual(r["carte"], PALETTE["carte"])
        self.assertEqual(r["survol"], PALETTE["carteSurvol"])
        self.assertEqual(r["fg"], PALETTE["texte"])
        self.assertEqual(r["bordure"], PALETTE["accent"])

    def test_palette_claire_donne_day(self):
        self.palette(CLAIRE)
        r = self.nvim("config(); nc.activer(); R.nom = vim.g.colors_name; R.normal = fond('Normal')")
        self.assertEqual(r["nom"], "tokyonight-day")
        self.assertEqual(r["normal"], CLAIRE["fond"])

    def test_palette_absente(self):
        r = self.nvim("config(); nc.activer(); R.nom = vim.g.colors_name; R.normal = fond('Normal')")
        self.assertEqual(r["nom"], "tokyonight-moon")
        self.assertEqual(r["normal"], "#222436")  # le moon d'origine

    def test_palette_abimee(self):
        for texte in ("{pas du json", "[1, 2]", '{"fond": "rouge", "texte": 3}', ""):
            with self.subTest(texte=texte):
                self.palette(texte)
                r = self.nvim("config(); nc.activer(); R.nom = vim.g.colors_name; R.normal = fond('Normal')")
                self.assertEqual(r["nom"], "tokyonight-moon")
                self.assertEqual(r["normal"], "#222436")

    def test_cles_manquantes_sans_erreur(self):
        self.palette({"fond": "#101010", "texte": "#eeeeee"})
        r = self.nvim("config(); nc.activer(); R.normal = fond('Normal')")
        self.assertEqual(r["normal"], "#101010")

    def test_fond_transparent_respecte(self):
        self.palette(PALETTE)
        r = self.nvim("""
config(true); nc.activer()
R.normal = vim.api.nvim_get_hl(0, { name = "Normal" }).bg
R.flottante = vim.api.nvim_get_hl(0, { name = "NormalFloat" }).bg
R.fg = string.format("#%06x", vim.api.nvim_get_hl(0, { name = "Normal" }).fg)
""")
        self.assertIsNone(r.get("normal"))
        self.assertEqual(r["fg"], PALETTE["texte"])

    def test_rechargement_a_chaud(self):
        self.palette(PALETTE)
        r = self.nvim("""
config(); nc.activer()
R.avant = fond("Normal")
local neuve = vim.deepcopy(vim.json.decode(vim.fn.join(vim.fn.readfile(vim.env.XDG_CONFIG_HOME .. "/nc/palette-ile.json"), "\\n")))
neuve.fond = "#2a1b3d"; neuve.carte = "#33244a"
ecrire(neuve)
R.suivi = vim.wait(3000, function() return fond("Normal") == "#2a1b3d" end, 20)
R.apres = fond("Normal"); R.carte = fond("StatusLine")
-- palette abîmée : on garde les couleurs actuelles, sans erreur
ecrire("{abîmé")
vim.wait(600)
R.garde = fond("Normal")
-- palette claire : bascule sur day
ecrire(vim.deepcopy(vim.tbl_extend("force", neuve, { sombre = false, fond = "#f4f1ea", texte = "#222222" })))
R.clair = vim.wait(3000, function() return vim.g.colors_name == "tokyonight-day" end, 20)
""")
        self.assertEqual(r["avant"], PALETTE["fond"])
        self.assertTrue(r["suivi"])
        self.assertEqual(r["apres"], "#2a1b3d")
        self.assertEqual(r["carte"], "#33244a")
        self.assertEqual(r["garde"], "#2a1b3d")
        self.assertTrue(r["clair"])

    def test_autre_theme_rien_ne_change(self):
        self.palette(PALETTE)
        r = self.nvim("""
config(); nc.activer()
vim.cmd.colorscheme("habamax")
R.actif = nc.actif
local avant = fond("Normal")
local neuve = vim.deepcopy(vim.json.decode(vim.fn.join(vim.fn.readfile(vim.env.XDG_CONFIG_HOME .. "/nc/palette-ile.json"), "\\n")))
neuve.fond = "#2a1b3d"
ecrire(neuve)
vim.wait(700)
R.nom = vim.g.colors_name
R.inchange = fond("Normal") == avant
-- tokyonight-moon choisi à la main : ses couleurs d'origine, pas la palette
vim.cmd.colorscheme("tokyonight-moon")
R.moon = fond("Normal")
""")
        self.assertFalse(r["actif"])
        self.assertEqual(r["nom"], "habamax")
        self.assertTrue(r["inchange"])
        self.assertEqual(r["moon"], "#222436")

    def test_dossier_nc_absent(self):
        shutil.rmtree(self.tmp / "config/nc")
        r = self.nvim("config(); nc.activer(); R.nom = vim.g.colors_name")
        self.assertEqual(r["nom"], "tokyonight-moon")


if __name__ == "__main__":
    unittest.main()

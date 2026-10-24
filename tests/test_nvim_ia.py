"""L'IA du bureau dans Neovim (lua/config/ia.lua), avec un faux nc-ia et de fausses CLI agentiques, dans un Neovim
sans interface (--headless) et des dossiers XDG temporaires : la saisie multiligne (envoi, annulation, collage,
historique), « Faire la tâche » (aperçu, puis a, r, y), un échec de nc-ia qui laisse le fichier intact, et l'agent
sur le projet (CLI de l'IA choisie, IA sans CLI agentique, IA coupée). Sauté si nvim est absent."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
NVIM_CONF = REPO / "home/.config/nvim"

FAUX_NC_IA = """#!/bin/sh
printf '%s\\n' "$@" > "$FAUX_DIR/args"
cat > "$FAUX_DIR/stdin"
if [ "$1" = etat ]; then cat "$FAUX_DIR/etat.json"; exit 0; fi
cat "$FAUX_DIR/sortie" 2>/dev/null
[ -f "$FAUX_DIR/erreur" ] && cat "$FAUX_DIR/erreur" >&2
exit "$(cat "$FAUX_DIR/code" 2>/dev/null || echo 0)"
"""
FAUSSE_CLI = """#!/bin/sh
pwd > "$FAUX_DIR/{nom}-pwd"
printf '%s\\n---\\n' "$@" > "$FAUX_DIR/{nom}-args"
"""

INIT = """
vim.opt.rtp:prepend(vim.env.NC_NVIM)
vim.g.mapleader = " "
_G.PP = {}
local function copie(r) return function(l) _G.PP[r] = l end end
local function colle(r) return function() return { _G.PP[r] or {}, "v" } end end
vim.g.clipboard = { name = "faux", copy = { ["+"] = copie("+"), ["*"] = copie("*") },
  paste = { ["+"] = colle("+"), ["*"] = colle("*") } }
require("config.keymaps")
"""

PRELUDE = """
local ia = require("config.ia")
R = { notes = {} }
vim.notify = function(m, n) table.insert(R.notes, { m = m, n = n }) end
local function touches(k)
  vim.api.nvim_feedkeys(vim.api.nvim_replace_termcodes(k, true, false, true), "xt", false)
end
-- startinsert ne prend effet qu'au retour dans la boucle principale de Neovim, que ce script ne rend pas, et
-- chaque nvim_feedkeys(…, "x") ressort du mode insertion : on vérifie qu'elle est demandée, et les touches tapées
-- dans la saisie commencent par « i ».
local saisir, demandee = ia.saisir, false
vim.cmd.startinsert = function() demandee = true end
ia.saisir = function(...)
  demandee = false
  local b, w = saisir(...)
  R.insertion = (R.insertion ~= false) and demandee
  return b, w
end
local function attendre(c) return vim.wait(5000, c, 20) end
local function lignes() return vim.api.nvim_buf_get_lines(0, 0, -1, false) end
local function nb_fen() return #vim.api.nvim_tabpage_list_wins(0) end
local function note(motif)
  for _, x in ipairs(R.notes) do if x.m:find(motif, 1, true) then return x end end
end
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
class NvimIA(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="nc-nvim-ia-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.home, self.faux, self.bin = self.tmp / "home", self.tmp / "faux", self.tmp / "bin"
        (self.home / ".local/bin").mkdir(parents=True)
        self.faux.mkdir()
        self.bin.mkdir()
        nc = self.home / ".local/bin/nc-ia"
        nc.write_text(FAUX_NC_IA)
        nc.chmod(0o755)
        for nom in ("codex", "gemini", "omp"):
            p = self.bin / nom
            p.write_text(FAUSSE_CLI.format(nom=nom))
            p.chmod(0o755)
        (self.tmp / "init.lua").write_text(INIT)
        self.projet = self.tmp / "projet"
        (self.projet / ".git").mkdir(parents=True)
        (self.projet / "src").mkdir()

    def nvim(self, scenario, fichier=None):
        (self.tmp / "scenario.lua").write_text(PRELUDE + scenario + FIN)
        env = dict(os.environ, HOME=str(self.home), FAUX_DIR=str(self.faux), NC_NVIM=str(NVIM_CONF),
                   PATH=f"{self.bin}:{os.environ.get('PATH', '/usr/bin:/bin')}")
        for cle, nom in (("XDG_CONFIG_HOME", "config"), ("XDG_DATA_HOME", "data"), ("XDG_STATE_HOME", "state"),
                         ("XDG_CACHE_HOME", "cache"), ("XDG_RUNTIME_DIR", "run")):
            (self.tmp / nom).mkdir(mode=0o700, exist_ok=True)
            env[cle] = str(self.tmp / nom)
        env.pop("SSH_CONNECTION", None)
        cmd = ["nvim", "--headless", "-i", "NONE", "-u", str(self.tmp / "init.lua")]
        if fichier:
            cmd.append(str(fichier))
        cmd += ["-c", f"luafile {self.tmp / 'scenario.lua'}"]
        subprocess.run(cmd, env=env, cwd=self.tmp, timeout=60, capture_output=True)
        r = json.loads((self.faux / "resultat.json").read_text())
        self.assertTrue(r["ok"], r.get("err"))
        return r

    def fichier_c(self):
        f = self.projet / "src/main.c"
        f.write_text("int main(void) {\n  // écrire une boucle de 1 à 3\n  return 0;\n}\n")
        return f

    # --- Saisie multiligne ---

    def test_saisie(self):
        r = self.nvim("""
local recu
local _, win = ia.saisir("Demande à l'IA", function(t) recu = t end)
local cfg = vim.api.nvim_win_get_config(win)
R.flottante = cfg.relative == "editor" and vim.bo.filetype == "markdown"
R.largeur = cfg.width == math.floor(vim.o.columns * 0.7)
touches("ipremière ligne<CR>deuxième ligne<C-s>")
attendre(function() return recu end)
R.envoi = recu
R.fen_apres_envoi = nb_fen()

-- Annulation : q en mode normal, puis Échap en mode normal
recu = nil
ia.saisir("Demande à l'IA", function(t) recu = t end)
touches("ià jeter<Esc>q")
vim.wait(150)
R.annule_q = recu == nil and nb_fen() == 1
ia.saisir("Demande à l'IA", function(t) recu = t end)
touches("ià jeter<Esc><Esc>")
vim.wait(150)
R.annule_echap = recu == nil and nb_fen() == 1

-- Collage depuis un registre : p en normal, <C-r>" en insertion ; :w envoie aussi
vim.fn.setreg('"', "collé du registre")
ia.saisir("Demande à l'IA", function(t) recu = t end)
touches("p<C-s>")
attendre(function() return recu end)
R.colle_p = recu
recu = nil
ia.saisir("Demande à l'IA", function(t) recu = t end)
touches('iavant <C-r>"<Esc>:w<CR>')
attendre(function() return recu end)
R.colle_ctrl_r = recu

-- Historique : Ctrl+P rappelle la dernière demande, Ctrl+P encore celle d'avant
recu = nil
ia.saisir("Demande à l'IA", function(t) recu = t end)
touches("<C-p><C-p><C-s>")
attendre(function() return recu end)
R.historique = recu
""")
        self.assertTrue(r["insertion"])            # la saisie s'ouvre en mode insertion
        self.assertTrue(r["flottante"])
        self.assertTrue(r["largeur"])
        self.assertEqual(r["envoi"], "première ligne\ndeuxième ligne")
        self.assertEqual(r["fen_apres_envoi"], 1)
        self.assertTrue(r["annule_q"])
        self.assertTrue(r["annule_echap"])
        self.assertEqual(r["colle_p"], "collé du registre")
        self.assertEqual(r["colle_ctrl_r"], "avant collé du registre")
        self.assertEqual(r["historique"], "collé du registre")
        h = json.loads((self.tmp / "state/nvim/nc-ia-demandes.json").read_text())
        self.assertEqual(h[0], "collé du registre")
        self.assertLessEqual(len(h), 20)

    # --- Faire la tâche ---

    def tache(self, touche):
        (self.faux / "sortie").write_text("```c\n  for (int i = 1; i <= 3; i++)\n    printf(\"%d\\n\", i);\n```\n")
        return self.nvim(f"""
touches("2GV<Esc>")
ia.faire(true)
attendre(function() return nb_fen() == 2 end)
R.apercu = lignes()
R.apercu_ft = vim.bo.filetype
R.fichier_pendant = vim.api.nvim_buf_get_lines(vim.fn.bufnr("main.c"), 0, -1, false)
touches("{touche}")
vim.wait(100)
R.fen = nb_fen()
R.fichier = vim.api.nvim_buf_get_lines(vim.fn.bufnr("main.c"), 0, -1, false)
R.presse = _G.PP["+"]
""", self.fichier_c())

    def test_faire_apercu_puis_ajouter(self):
        r = self.tache("a")
        code = ["  for (int i = 1; i <= 3; i++)", '    printf("%d\\n", i);']
        self.assertEqual(r["apercu"], code)          # clôtures ``` retirées
        self.assertEqual(r["apercu_ft"], "c")
        self.assertEqual(len(r["fichier_pendant"]), 4)  # rien de remplacé d'office
        self.assertEqual(r["fichier"], ["int main(void) {", "  // écrire une boucle de 1 à 3"] + code
                         + ["  return 0;", "}"])
        self.assertEqual(r["fen"], 1)
        args = (self.faux / "args").read_text().splitlines()
        self.assertEqual(args[:2], ["texte", "Écris le code demandé, en c, uniquement le code, sans explication."])
        entree = (self.faux / "stdin").read_text()
        self.assertTrue(entree.startswith("Tâche :\n  // écrire une boucle de 1 à 3\n"))
        self.assertIn("return 0;", entree)           # le fichier en contexte

    def test_faire_remplacer(self):
        r = self.tache("r")
        self.assertEqual(r["fichier"][1], "  for (int i = 1; i <= 3; i++)")
        self.assertEqual(len(r["fichier"]), 5)

    def test_faire_copier(self):
        r = self.tache("y")
        self.assertEqual(r["presse"], ["  for (int i = 1; i <= 3; i++)", '    printf("%d\\n", i);'])
        self.assertEqual(len(r["fichier"]), 4)

    # --- Échec de nc-ia : rien n'est touché ---

    def test_transformer_echec_buffer_intact(self):
        (self.faux / "code").write_text("3")
        (self.faux / "erreur").write_text("nc-ia : réponse refusée (appel d'outil).")
        (self.faux / "sortie").write_text("<tool_use>rm -rf</tool_use>")
        r = self.nvim("""
local avant = lignes()
touches("2GV<Esc>")
ia.transformer()
touches("iajoute un commentaire<C-s>")
attendre(function() return note("refusée") end)
R.note = note("refusée")
R.intact = vim.deep_equal(avant, lignes())
""", self.fichier_c())
        self.assertIsNotNone(r["note"])
        self.assertTrue(r["intact"])
        self.assertIn("ajoute un commentaire", (self.faux / "args").read_text())

    def test_transformer_balisage_outil_ignore(self):
        (self.faux / "sortie").write_text('<invoke name="Bash">rm</invoke>')
        r = self.nvim("""
local avant = lignes()
touches("2GV<Esc>")
ia.transformer()
touches("ix<C-s>")
attendre(function() return note("appel d'outil") end)
R.intact = vim.deep_equal(avant, lignes())
""", self.fichier_c())
        self.assertTrue(r["intact"])

    def test_montrer_copier_inserer(self):
        r = self.nvim("""
ia.montrer("ligne A\\nligne B")
touches("y")
R.presse = _G.PP["+"]
touches("i")
vim.wait(50)
R.fichier = lignes()
""", self.fichier_c())
        self.assertEqual(r["presse"], ["ligne A", "ligne B"])
        self.assertEqual(r["fichier"][1:3], ["ligne A", "ligne B"])

    # --- Agent sur le projet ---

    def etat(self, choix, ias, mode="manuel", coupee=False):
        (self.faux / "etat.json").write_text(json.dumps({
            "mode": mode, "coupee": coupee, "choix": choix, "usages": {"question": {"id": choix, "nom": choix}},
            "ias": ias}))

    def test_agent_codex(self):
        self.etat("codex", [{"id": "codex", "nom": "Codex", "genre": "cli", "disponible": True, "agent": "codex"}])
        r = self.nvim("""
touches("2GV<Esc>")
ia.agent(true)
attendre(function() return vim.uv.fs_stat(vim.env.FAUX_DIR .. "/codex-args") end)
vim.wait(100)
R.terminal = vim.bo.buftype == "terminal"
R.hauteur = vim.api.nvim_win_get_height(0)
""", self.fichier_c())
        self.assertTrue(r["terminal"])
        self.assertGreaterEqual(r["hauteur"], 5)
        args = (self.faux / "codex-args").read_text()
        self.assertTrue(args.startswith("// écrire une boucle de 1 à 3\n"))
        self.assertIn("src/main.c, lignes 2 à 2", args)
        self.assertNotIn("dangerously", args)
        self.assertEqual((self.faux / "codex-pwd").read_text().strip(), str(self.projet))

    def test_agent_omp(self):
        """Oh My Pi : « omp launch <demande> » (jamais la demande seule : « commit … » serait une sous-commande d'omp)."""
        self.etat("omp", [{"id": "omp", "nom": "Oh My Pi (omp)", "genre": "cli", "disponible": True, "agent": "omp"}])
        r = self.nvim("""
touches("2GV<Esc>")
ia.agent(true)
attendre(function() return vim.uv.fs_stat(vim.env.FAUX_DIR .. "/omp-args") end)
vim.wait(100)
R.terminal = vim.bo.buftype == "terminal"
""", self.fichier_c())
        self.assertTrue(r["terminal"])
        args = (self.faux / "omp-args").read_text()
        self.assertTrue(args.startswith("launch\n---\n--\n---\n// écrire une boucle de 1 à 3\n"), args)
        self.assertNotIn("yolo", args)

    def test_agent_omp_demande_en_arobase_ou_tiret(self):
        """Une sélection qui commence par « @ » (un décorateur) ou « - » reste du texte pour omp : après « -- »."""
        self.etat("omp", [{"id": "omp", "nom": "Oh My Pi (omp)", "genre": "cli", "disponible": True, "agent": "omp"}])
        for sel in ("@app.route('/x')", "-- commentaire"):
            (self.faux / "omp-args").unlink(missing_ok=True)
            f = self.projet / "src/x.py"
            f.write_text(sel + "\n")
            self.nvim("""
touches("ggV<Esc>")
ia.agent(true)
attendre(function() return vim.uv.fs_stat(vim.env.FAUX_DIR .. "/omp-args") end)
vim.wait(100)
""", f)
            lignes = (self.faux / "omp-args").read_text().splitlines()
            self.assertEqual(lignes[:4], ["launch", "---", "--", "---"], lignes)
            self.assertTrue(any(l.strip() == sel for l in lignes[4:]), lignes)

    def test_agent_choisir(self):
        self.etat("anthropic", [
            {"id": "anthropic", "nom": "Claude (API Anthropic)", "genre": "api", "disponible": True},
            {"id": "codex", "nom": "Codex", "genre": "cli", "disponible": True},
            {"id": "gemini-cli", "nom": "Gemini CLI", "genre": "cli", "disponible": True},
            {"id": "qwen", "nom": "Qwen Code", "genre": "cli", "disponible": False}])
        r = self.nvim("""
vim.ui.select = function(liste, o, f)
  R.choix = vim.tbl_map(o.format_item, liste)
  f(liste[2])
end
touches("2GV<Esc>")
ia.choisir_agent(true)
attendre(function() return vim.uv.fs_stat(vim.env.FAUX_DIR .. "/gemini-args") end)
""", self.fichier_c())
        self.assertEqual(r["choix"], ["Codex (codex)", "Gemini CLI (gemini)"])
        self.assertTrue((self.faux / "gemini-args").read_text().startswith("-i\n"))

    def test_agent_sans_cli(self):
        self.etat("anthropic", [{"id": "anthropic", "nom": "Claude (API Anthropic)", "genre": "api",
                                 "disponible": True, "agent": "claude"}])
        r = self.nvim("""
ia.agent(false)
attendre(function() return #R.notes > 0 end)
R.fen = nb_fen()
""", self.fichier_c())
        self.assertIn("n'a pas d'agent en terminal", r["notes"][0]["m"])
        self.assertEqual(r["fen"], 1)

    def test_agent_ia_coupee(self):
        self.etat("codex", [{"id": "codex", "nom": "Codex", "genre": "cli", "disponible": True}],
                  mode="non", coupee=True)
        r = self.nvim("""
ia.agent(false)
attendre(function() return #R.notes > 0 end)
R.fen = nb_fen()
""", self.fichier_c())
        self.assertIn("coupée", r["notes"][0]["m"])
        self.assertEqual(r["fen"], 1)
        self.assertFalse((self.faux / "codex-args").exists())


if __name__ == "__main__":
    unittest.main()

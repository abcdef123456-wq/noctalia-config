"""Les agents et l'IA ciblée dans Neovim (lua/config/ia.lua, agents.lua, plugins/ia.lua) avec un faux nc-ia, dans un
Neovim sans interface et des dossiers XDG temporaires : IA coupée (rien ne s'ouvre, le message le dit), message de
commit (nc-ia commit : rempli, jamais écrasé, codes 2/3/4), diagnostic expliqué puis appliqué, panneau sidekick
(faux module), élément de barre qui suit etat.json, et aucune touche en double entre Claude Code (Espace a) et le
reste. Sauté si nvim est absent."""
import json
import shutil
import unittest

from tests import test_nvim_ia as base

FAUX_NC_IA = """#!/bin/sh
printf '%s\\n' "$@" > "$FAUX_DIR/args"
pwd > "$FAUX_DIR/pwd"
cat > "$FAUX_DIR/stdin"
if [ "$1" = etat ]; then cat "$FAUX_DIR/etat.json"; exit 0; fi
cat "$FAUX_DIR/sortie" 2>/dev/null
[ -f "$FAUX_DIR/erreur" ] && cat "$FAUX_DIR/erreur" >&2
exit "$(cat "$FAUX_DIR/code" 2>/dev/null || echo 0)"
"""


@unittest.skipUnless(shutil.which("nvim"), "nvim absent")
class NvimAgents(unittest.TestCase):
    setUp = base.NvimIA.setUp
    nvim = base.NvimIA.nvim
    fichier_c = base.NvimIA.fichier_c
    etat = base.NvimIA.etat

    def setUp(self):
        base.NvimIA.setUp(self)
        (self.home / ".local/bin/nc-ia").write_text(FAUX_NC_IA)

    def coupe(self):
        d = self.tmp / "config/nc"
        d.mkdir(parents=True, exist_ok=True)
        (d / "reglages.conf").write_text('LANGUE=fr\nIA_MODE="non"\n')

    # --- IA coupée ---

    def test_ia_coupee_rien_ne_s_ouvre(self):
        self.coupe()
        r = self.nvim("""
local touches_ia = { "ii", "ia", "iA", "is", "ip", "iF", "im", "id" }
R.pas_ouvert, R.dit = true, true
for _, t in ipairs(touches_ia) do
  R.notes = {}
  touches(" " .. t)
  vim.wait(50)
  R.pas_ouvert = R.pas_ouvert and nb_fen() == 1
  R.dit = R.dit and note("IA désactivée (nc-reglages → Intelligence artificielle)") ~= nil
end
-- visuel
R.notes = {}
touches("2GV<Esc>")
ia.faire(true)
ia.expliquer()
R.visuel = nb_fen() == 1 and note("IA désactivée") ~= nil
-- les touches de Claude Code (Espace a…) passent par la même garde
local spec = dofile(vim.env.NC_NVIM .. "/lua/plugins/ia.lua")
local claude
for _, s in ipairs(spec) do if s[1] == "coder/claudecode.nvim" then claude = s end end
R.claude = #claude.keys
R.notes = {}
for _, k in ipairs(claude.keys) do k[2]() end
R.claude_dit = note("IA désactivée") ~= nil and nb_fen() == 1
""", self.fichier_c())
        self.assertTrue(r["pas_ouvert"])
        self.assertTrue(r["dit"])
        self.assertTrue(r["visuel"])
        self.assertEqual(r["claude"], 9)
        self.assertTrue(r["claude_dit"])
        self.assertFalse((self.faux / "args").exists())  # nc-ia n'a même pas été lancé

    # --- Message de commit ---

    def message_vide(self):
        f = self.projet / ".git/COMMIT_EDITMSG"
        f.write_text("\n# Please enter the commit message for your changes.\n#\n")
        return f

    def test_commit_remplit_un_message_vide(self):
        (self.faux / "sortie").write_text("Corrige le calcul\n\nLe total oubliait la remise.\n")
        r = self.nvim("""
vim.bo.filetype = "gitcommit"
touches(" im")
attendre(function() return lignes()[1] ~= "" end)
R.lignes = lignes()
R.attente = note("L'IA écrit") ~= nil
""", self.message_vide())
        self.assertEqual(r["lignes"][:4], ["Corrige le calcul", "", "Le total oubliait la remise.", ""])
        self.assertEqual(r["lignes"][4], "# Please enter the commit message for your changes.")
        self.assertTrue(r["attente"])
        self.assertEqual((self.faux / "args").read_text().strip(), "commit")
        self.assertEqual((self.faux / "pwd").read_text().strip(), str(self.projet.resolve()))

    def test_commit_ne_touche_pas_un_message_ecrit(self):
        f = self.projet / ".git/COMMIT_EDITMSG"
        f.write_text("mon message\n# commentaire\n")
        (self.faux / "sortie").write_text("autre chose")
        r = self.nvim("""
vim.bo.filetype = "gitcommit"
local avant = lignes()
touches(" im")
vim.wait(300)
R.intact = vim.deep_equal(avant, lignes())
R.dit = note("déjà écrit") ~= nil
""", f)
        self.assertTrue(r["intact"])
        self.assertTrue(r["dit"])
        self.assertFalse((self.faux / "args").exists())

    def test_commit_message_ecrit_pendant_l_attente(self):
        (self.faux / "sortie").write_text("celui de l'IA")
        r = self.nvim("""
vim.bo.filetype = "gitcommit"
ia.commit()
vim.api.nvim_buf_set_lines(0, 0, 1, false, { "le mien" })
attendre(function() return note("entre-temps") end)
R.lignes = lignes()
R.dit = note("entre-temps") ~= nil
""", self.message_vide())
        self.assertEqual(r["lignes"][0], "le mien")
        self.assertTrue(r["dit"])

    def test_commit_codes_2_3_4_et_autre(self):
        for code, erreur, motif in ((2, "", "Rien n'est indexé"), (3, "", "IA désactivée"),
                                    (4, "clé repérée ligne 3", "secret"), (1, "nc-ia : panne du moteur", "panne du moteur")):
            with self.subTest(code=code):
                (self.faux / "code").write_text(str(code))
                (self.faux / "erreur").write_text(erreur)
                (self.faux / "sortie").write_text("")
                r = self.nvim(f"""
vim.bo.filetype = "gitcommit"
local avant = lignes()
ia.commit()
attendre(function() return note("{motif}") end)
R.dit = note("{motif}") ~= nil
R.intact = vim.deep_equal(avant, lignes())
""", self.message_vide())
                self.assertTrue(r["dit"])
                self.assertTrue(r["intact"])

    def test_commit_hors_message(self):
        r = self.nvim("""
ia.commit()
R.dit = note("dans le message") ~= nil
""", self.fichier_c())
        self.assertTrue(r["dit"])
        self.assertFalse((self.faux / "args").exists())

    # --- Diagnostic ---

    DIAG = """
vim.bo.filetype = "c"
local ns = vim.api.nvim_create_namespace("essai")
vim.diagnostic.set(ns, 0, { { lnum = 1, col = 2, message = "variable i non déclarée", severity = 1,
  source = "clangd", code = "undeclared" } })
"""

    def test_diagnostic_envoye_puis_applique(self):
        (self.faux / "sortie").write_text(
            "i n'est pas déclarée.\n\n```c\nint main(void) {\n  int i = 0;\n  return 0;\n}\n```\n")
        r = self.nvim(self.DIAG + """
touches("2G")
ia.diagnostic()
attendre(function() return nb_fen() == 2 end)
R.apercu = lignes()[1]
touches("a")
vim.wait(100)
R.fen = nb_fen()
R.fichier = vim.api.nvim_buf_get_lines(vim.fn.bufnr("main.c"), 0, -1, false)
""", self.fichier_c())
        entree = (self.faux / "stdin").read_text()
        self.assertIn("variable i non déclarée", entree)
        self.assertIn("clangd", entree)
        self.assertIn("(c)", entree)
        self.assertIn("return 0;", entree)  # les lignes autour
        self.assertEqual(r["apercu"], "i n'est pas déclarée.")
        self.assertEqual(r["fen"], 1)
        self.assertEqual(r["fichier"], ["int main(void) {", "  int i = 0;", "  return 0;", "}"])

    def test_diagnostic_refuser_ne_change_rien(self):
        (self.faux / "sortie").write_text("Explication.\n```c\nrien\n```\n")
        r = self.nvim(self.DIAG + """
local avant = lignes()
touches("2G")
ia.diagnostic()
attendre(function() return nb_fen() == 2 end)
touches("r")
vim.wait(100)
R.fen = nb_fen()
R.intact = vim.deep_equal(avant, vim.api.nvim_buf_get_lines(vim.fn.bufnr("main.c"), 0, -1, false))
""", self.fichier_c())
        self.assertEqual(r["fen"], 1)
        self.assertTrue(r["intact"])

    def test_diagnostic_aucun_sur_la_ligne(self):
        r = self.nvim(self.DIAG + """
touches("1G")
ia.diagnostic()
R.dit = note("Aucun diagnostic") ~= nil
R.fen = nb_fen()
""", self.fichier_c())
        self.assertTrue(r["dit"])
        self.assertEqual(r["fen"], 1)
        self.assertFalse((self.faux / "args").exists())

    # --- Panneau d'agents (sidekick, remplacé par un faux module) ---

    FAUX_SIDEKICK = """
package.loaded["sidekick.cli"] = {
  toggle = function(o) R.toggle = o end,
  select = function(o) R.select = o end,
  send = function(o) R.send = o end,
  prompt = function() R.prompt = true end,
  focus = function() R.focus = true end,
}
"""

    def test_panneau_agent_de_l_ia_choisie(self):
        self.etat("cursor", [{"id": "cursor", "nom": "Cursor", "disponible": True, "cli_agent": "cursor-agent"}])
        (self.bin / "cursor-agent").write_text("#!/bin/sh\n")
        (self.bin / "cursor-agent").chmod(0o755)
        r = self.nvim(self.FAUX_SIDEKICK + """
touches(" ia")
attendre(function() return R.toggle end)
touches(" iA"); touches(" is"); touches(" iF"); touches(" ip")
vim.fn.maparg("<C-.>", "n", false, true).callback()
vim.wait(100)
""", self.fichier_c())
        self.assertEqual(r["toggle"], {"name": "cursor", "focus": True})
        self.assertEqual(r["select"], {"filter": {"installed": True}})
        self.assertTrue(r["prompt"])
        self.assertTrue(r["focus"])

    def test_panneau_envoyer(self):
        r = self.nvim(self.FAUX_SIDEKICK + """
touches(" is")
R.this = R.send and R.send.msg
touches(" iF")
R.fichier = R.send and R.send.msg
""", self.fichier_c())
        self.assertEqual(r["this"], "{this}")
        self.assertEqual(r["fichier"], "{file}")

    def test_panneau_sans_cli_utilisable(self):
        self.etat("gem", [{"id": "gem", "nom": "Gem", "disponible": True, "cli_agent": "introuvable-xyz"}])
        r = self.nvim(self.FAUX_SIDEKICK + """
touches(" ia")
attendre(function() return note("introuvable") end)
R.dit = note("introuvable") ~= nil
""", self.fichier_c())
        self.assertTrue(r["dit"])
        self.assertNotIn("toggle", r)

    # --- Élément de barre (agents suivis par nc-claude) ---

    def test_barre_suit_etat_json(self):
        r = self.nvim("""
local ag = require("config.agents")
local run = vim.env.XDG_RUNTIME_DIR .. "/nc-claude"
ag.demarrer()
R.vide = ag.etat() == nil
local function ecrire(d)
  vim.fn.mkdir(run, "p")
  local f = io.open(run .. "/etat.json.tmp", "w"); f:write(vim.json.encode(d)); f:close()
  os.rename(run .. "/etat.json.tmp", run .. "/etat.json")
end
ecrire({ sessions = { a = { id = "a", etat = "travail", maj = 1, terminal = 4242, shell = 4243 } }, demandes = {} })
R.t = attendre(function() return ag.etat() ~= nil end)
R.travail = ag.etat() and ag.etat().texte
ecrire({ sessions = { a = { id = "a", etat = "attente", maj = 2 } }, demandes = {} })
R.a = attendre(function() return ag.etat() and ag.etat().attend end)
R.attente = ag.etat() and ag.etat().texte
local c = ag.composant()
R.composant = c[1]() ; R.cond = c.cond()
ecrire({ sessions = { a = { id = "a", etat = "fini", maj = 3 } }, demandes = {} })
R.f = attendre(function() return ag.etat() == nil end)
R.cond_apres = c.cond()
ag.arreter()
""", self.fichier_c())
        self.assertTrue(r["vide"])
        self.assertTrue(r["t"] and r["a"] and r["f"])
        self.assertEqual(r["travail"], "󰚩 Claude travaille")
        self.assertEqual(r["attente"], "󰚩 Claude t'attend")
        self.assertEqual(r["composant"], "󰚩 Claude t'attend")
        self.assertTrue(r["cond"])
        self.assertFalse(r["cond_apres"])

    def test_barre_rien_sans_dossier_ni_session(self):
        r = self.nvim("""
local ag = require("config.agents")
ag.demarrer()
R.rien = ag.etat() == nil and ag.composant().cond() == false
ag.aller()
R.dit = note("Aucun agent") ~= nil
ag.arreter()
""", self.fichier_c())
        self.assertTrue(r["rien"])
        self.assertTrue(r["dit"])

    # --- Touches ---

    def test_aucune_touche_en_double_avec_claude_code(self):
        r = self.nvim("""
local spec = dofile(vim.env.NC_NVIM .. "/lua/plugins/ia.lua")
local claude, sidekick = {}, {}
for _, s in ipairs(spec) do
  if s[1] == "coder/claudecode.nvim" then
    for _, k in ipairs(s.keys) do table.insert(claude, k[1]) end
  elseif s[1] == "folke/sidekick.nvim" then
    for _, k in ipairs(s.keys or {}) do table.insert(sidekick, k[1]) end
    R.nes = s.opts.nes.enabled
  end
end
R.claude, R.sidekick = claude, sidekick
-- les touches posées par keymaps.lua : aucune sous « Espace a », aucune en double par mode
local vues, doubles = {}, {}
for _, mode in ipairs({ "n", "x", "t", "i" }) do
  for _, m in ipairs(vim.api.nvim_get_keymap(mode)) do
    if m.lhs:sub(1, 2) == " a" then doubles[#doubles + 1] = "a:" .. m.lhs end
    local id = mode .. m.lhs
    if vues[id] then doubles[#doubles + 1] = id end
    vues[id] = true
  end
end
R.doubles = doubles
R.ia = {}
for _, k in ipairs({ " ia", " iA", " is", " ip", " iF", " im", " id", " iw", " if" }) do
  R.ia[k] = vim.fn.maparg(k, "n") ~= ""
end
""", self.fichier_c())
        self.assertFalse(r["nes"])
        self.assertEqual(r["doubles"], [])
        self.assertTrue(all(r["ia"].values()), r["ia"])
        self.assertFalse(any(k.startswith("<leader>a") for k in r["sidekick"]))
        self.assertEqual(len(set(r["claude"])), len(r["claude"]) - 1)  # as : deux fois (visuel, arbre de fichiers)


if __name__ == "__main__":
    unittest.main()

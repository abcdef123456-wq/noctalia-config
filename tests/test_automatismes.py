"""nc/automatismes.lua : mode jeu automatique (ne défait que ce qu'il a fait) et mémoire des fenêtres flottantes
(bornée aux 200 dernières). Le fichier est chargé entier avec un faux `hl`, jamais le vrai Hyprland."""
import json
import re
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
LUA = REPO / "home/.config/hypr/nc/automatismes.lua"

ENTETE = r'''
local proxy; proxy = setmetatable({}, { __index = function() return proxy end, __call = function() return proxy end })
handlers, cmds, bascules, fenetres = {}, {}, 0, {}
hl = {
  on = function(e, f) handlers[e] = handlers[e] or {}; table.insert(handlers[e], f) end,
  exec_cmd = function(c) cmds[#cmds + 1] = c end,
  get_config = function() return nil end, bind = function() end, timer = function() end,
  get_windows = function() return fenetres end, get_active_window = function() end,
  get_active_monitor = function() return { x = 0, y = 0, width = 2000, height = 1000, scale = 1 } end,
  dsp = proxy, dispatch = function() end,
}
nc = { profil = { profil = PROFIL }, jeu = JEU, hypr_min = function() return true end,
       reglage = function(_, d) return d end, t = function(fr) return fr end,
       guillemets = function(s) return "'" .. s .. "'" end }
function nc.mode_jeu() bascules = bascules + 1 end
dofile(FICHIER)
function emettre(e, w) for _, f in ipairs(handlers[e] or {}) do f(w) end end
'''


@unittest.skipUnless(shutil.which("lua"), "Lua requis")
class Automatismes(unittest.TestCase):
    def lancer(self, corps, d, jeu=False, profil="balanced"):
        code = (ENTETE.replace("PROFIL", json.dumps(profil)).replace("JEU", "true" if jeu else "false")
                .replace("FICHIER", json.dumps(str(LUA))) + corps)
        r = subprocess.run(["lua", "-"], input=code, text=True, capture_output=True, timeout=20,
                           env=dict(HOME=d, PATH="/usr/bin:/bin", XDG_RUNTIME_DIR=d, XDG_STATE_HOME=d + "/etat"))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return r.stdout.strip()

    def test_mode_jeu_automatique_coupe_a_la_fin(self):
        with tempfile.TemporaryDirectory() as d:
            out = self.lancer('''
local jeu = { class = "steam_app_1", address = "0x1" }
emettre("window.open", jeu)
print("ouvert", bascules)
fenetres = { jeu }
nc.jeu = true; io.open(os.getenv("XDG_RUNTIME_DIR") .. "/nc-mode-jeu", "w"):close()   -- après le rechargement
emettre("window.close", jeu)
print("ferme", bascules)''', d)
            self.assertEqual(out.splitlines(), ["ouvert\t1", "ferme\t2"])

    def test_mode_jeu_a_la_main_pas_coupe(self):
        """Le mode jeu était déjà mis à la main : le jeu qui se ferme ne le coupe pas."""
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "nc-mode-jeu").write_text("")
            out = self.lancer('''
local jeu = { class = "steam_app_1", address = "0x1" }
emettre("window.open", jeu)
fenetres = { jeu }
emettre("window.close", jeu)
print(bascules)''', d, jeu=True, profil="power-saver")
            self.assertEqual(out, "0")
            self.assertFalse((Path(d) / "nc-jeu-auto").exists())

    def test_mode_jeu_change_entre_temps_pas_touche(self):
        """Mis par l'automatisme, puis coupé à la main avant la fin : rien à défaire."""
        with tempfile.TemporaryDirectory() as d:
            out = self.lancer('''
local jeu = { class = "gamescope", address = "0x1" }
emettre("window.open", jeu)
fenetres = { jeu }
nc.jeu = false   -- coupé à la main : ni variable ni marque
emettre("window.close", jeu)
print(bascules, cmds[#cmds])''', d)
            self.assertEqual(out, "1\tnoctalia msg power-set balanced", "1 bascule à l'ouverture, aucune à la fin ; le profil est remis")

    def test_memoire_fenetres_bornee(self):
        with tempfile.TemporaryDirectory() as d:
            self.lancer('''
for i = 1, 230 do
    emettre("window.close", { class = "app", initial_title = "t" .. i, floating = true, address = "0x" .. i,
        at = { x = 100, y = 50 }, size = { x = 500, y = 400 } })
end
-- La plus ancienne revue (t100) repasse en bas : elle survit
emettre("window.close", { class = "app", initial_title = "t100", floating = true, address = "0xa",
    at = { x = 100, y = 50 }, size = { x = 600, y = 400 } })''', d)
            lignes = (Path(d) / "etat/noctalia-config/fenetres-flottantes").read_text().splitlines()
            self.assertEqual(len(lignes), 200)
            self.assertTrue(lignes[-1].startswith("app|t100="), lignes[-1])
            self.assertTrue(lignes[0].startswith("app|t31="), lignes[0])
            self.assertFalse(any(l.startswith("app|t1=") for l in lignes))
            # Une entrée gardée est toujours rouverte à sa place
            out = self.lancer('''
emettre("window.open", { class = "app", initial_title = "t231", floating = true, address = "0xb" })
print("ok")''', d)
            self.assertEqual(out, "ok")

    def test_fenetres_de_l_ile_reconnues_en_francais_et_en_anglais(self):
        """Titres de l'île (Reglages.t) : chaque règle de fenêtre reconnaît le titre FR et le titre EN, la mémoire des
        fenêtres flottantes les ignore, et nc-session ne les range pas dans une session."""
        qml = REPO / "home/.config/quickshell/nc-ile"
        titres = {}
        for fichier in ("Parametres.qml", "ConnexionJarvis.qml", "JarvisChat.qml", "Jarvis.qml", "ClesIA.qml"):
            m = re.search(r'^\s*title:\s*Reglages\.t\("([^"]+)",\s*"([^"]+)"\)', (qml / fichier).read_text(), re.M)
            self.assertIsNotNone(m, fichier)
            titres[fichier] = set(m.groups())
        regles_lua = (REPO / "home/.config/hypr/nc/regles.lua").read_text()
        # Faux hl : les motifs de titre de chaque règle sont notés
        harness = r'''
motifs = {}
hl = setmetatable({ window_rule = function(r) motifs[r.name] = r.match.title end },
                  { __index = function() return function() end end })
nc = setmetatable({ reglage = function(c, d) if c == "SAISIE" then return "souris" end return d end },
                  { __index = function() return function() return "" end end })
dofile(FICHIER)
for n, p in pairs(motifs) do print(n .. "\t" .. p) end
'''.replace("FICHIER", json.dumps(str(REPO / "home/.config/hypr/nc/regles.lua")))
        r = subprocess.run(["lua", "-"], input=harness, text=True, capture_output=True, timeout=10,
                           env=dict(PATH="/usr/bin:/bin"))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        motifs = dict(l.split("\t", 1) for l in r.stdout.splitlines())
        attendu = {"nc-connexion-jarvis": "ConnexionJarvis.qml", "nc-reglages-fenetre": "Parametres.qml",
                   "nc-cles-ia": "ClesIA.qml", "jarvis-chat": "JarvisChat.qml", "jarvis-cockpit": "Jarvis.qml"}
        for regle, fichier in attendu.items():
            for titre in titres[fichier]:
                self.assertRegex(titre, motifs[regle], f"{regle} ne reconnaît pas « {titre} »")
        libres = motifs["souris-libres"].replace("negative:", "")
        for fichier in ("Parametres.qml", "Jarvis.qml"):
            for titre in titres[fichier]:
                self.assertRegex(titre, libres, f"souris-libres doit exclure « {titre} »")
        # Place pleine (automatismes.lua) : jamais mémorisée comme fenêtre flottante ordinaire
        with tempfile.TemporaryDirectory() as d:
            for titre in titres["Parametres.qml"] | titres["Jarvis.qml"]:
                self.lancer(f'''emettre("window.close", {{ class = "org.quickshell", initial_title = {json.dumps(titre, ensure_ascii=False)},
    title = {json.dumps(titre, ensure_ascii=False)}, floating = true, address = "0x1", at = {{ x = 1, y = 1 }}, size = {{ x = 500, y = 400 }} }})''', d)
            self.assertFalse((Path(d) / "etat/noctalia-config/fenetres-flottantes").exists())
        # nc-session
        session = (REPO / "home/.local/bin/nc-session").read_text()
        exclus = re.search(r"EXCLUS_TITRES = \{(.*?)\}", session)[1]
        for fichier in ("Parametres.qml", "ConnexionJarvis.qml", "JarvisChat.qml", "Jarvis.qml", "ClesIA.qml"):
            for titre in titres[fichier]:
                self.assertIn(json.dumps(titre, ensure_ascii=False), exclus, titre)


if __name__ == "__main__":
    unittest.main()

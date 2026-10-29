"""Fiche des raccourcis (Super + /) sous plusieurs Hyprland : nc-keys lit la sortie texte de « hyprctl binds » au format 0.56
(« bindd » et ses drapeaux) comme au format 0.57 (« bind » seul, ligne « flags: », touche par code donnée par la chaîne
d'origine), et passe à « hyprctl binds -j » si le texte ne donne rien. Sans raccourci décrit, ou en échec, une raison sur
une ligne (code 1), jamais une fiche vide ; le plugin nc/keys l'affiche. Faux hyprctl, HOME temporaire, jamais le vrai."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
NC_KEYS = REPO / "home/.local/bin/nc-keys"
PANEL = REPO / "home/.local/share/noctalia/plugins/nc-keys/panel.luau"

# Mêmes raccourcis, écrits par Hyprland 0.56.2 (src/debug/HyprCtl.cpp) puis 0.57.0 (src/ipc/s1/Commands.cpp)
TEXTE_056 = ("bindd\n\tmodmask: 64\n\tsubmap: \n\tkey: Return\n\tkeycode: 0\n\tcatchall: false\n\tdescription: Applis et barre|Terminal\n"
             "\tdispatcher: __lua\n\targ: 1\n\n"
             "bindd\n\tmodmask: 64\n\tsubmap: \n\tkey: SUPER + code:46\n\tkeycode: 46\n\tcatchall: false\n\tdescription: Système|Verrouiller l'écran\n"
             "\tdispatcher: __lua\n\targ: 2\n\n"
             "bindmd\n\tmodmask: 64\n\tsubmap: \n\tkey: mouse:272\n\tkeycode: 0\n\tcatchall: false\n\tdescription: Souris|Déplacer la fenêtre\n"
             "\tdispatcher: __lua\n\targ: 3\n\n"
             "bind\n\tmodmask: 0\n\tsubmap: \n\tkey: mouse:275\n\tkeycode: 0\n\tcatchall: false\n\tdescription: \n\tdispatcher: __lua\n\targ: 4\n\n")
TEXTE_057 = ("bind\n\tflags: \n\tmodmask: 64\n\tsubmap: \n\tkey: Return\n\tkeycode: 0\n\tcatchall: false\n\tdescription: Applis et barre|Terminal\n"
             "\tdispatcher: __lua\n\targ: 1\n\n"
             "bind\n\tflags: \n\tmodmask: 64\n\tsubmap: \n\tkey: SUPER + code:46\n\tkeycode: 46\n\tcatchall: false\n\tdescription: Système|Verrouiller l'écran\n"
             "\tdispatcher: __lua\n\targ: 2\n\n"
             "bind\n\tflags: mouse\n\tmodmask: 64\n\tsubmap: \n\tkey: mouse:272\n\tkeycode: 0\n\tcatchall: false\n\tdescription: Souris|Déplacer la fenêtre\n"
             "\tdispatcher: __lua\n\targ: 3\n\n"
             "bind\n\tflags: release, click\n\tmodmask: 0\n\tsubmap: \n\tkey: mouse:275\n\tkeycode: 0\n\tcatchall: false\n\tdescription: \n"
             "\tdispatcher: __lua\n\targ: 4\n\n")
JSON_057 = json.dumps([
    {"modmask": 64, "submap": "", "key": "Return", "keycode": 0, "description": "Applis et barre|Terminal"},
    {"modmask": 64, "submap": "", "key": "", "keycode": 46, "description": "Système|Verrouiller l'écran"},
    {"modmask": 64, "submap": "", "key": "mouse:272", "keycode": 0, "description": "Souris|Déplacer la fenêtre"},
])

FAUX_HYPRCTL = r'''#!/bin/sh
d="$(dirname "$0")"
case "$*" in
  "binds") [ -f "$d/texte" ] && cat "$d/texte"; [ -f "$d/echec" ] && exit 1; exit 0 ;;
  "binds -j") [ -f "$d/json" ] && cat "$d/json"; exit 0 ;;
  *) exit 0 ;;
esac
'''


class Formats(unittest.TestCase):
    def lancer(self, texte=None, json_=None, echec=False):
        with tempfile.TemporaryDirectory(prefix="nc-fiche-") as d:
            home = Path(d)
            faux = home / "faux"; faux.mkdir()
            (faux / "hyprctl").write_text(FAUX_HYPRCTL); (faux / "hyprctl").chmod(0o755)
            if texte is not None:
                (faux / "texte").write_text(texte)
            if json_ is not None:
                (faux / "json").write_text(json_)
            if echec:
                (faux / "echec").write_text("")
            (home / ".config/nc").mkdir(parents=True)
            (home / ".config/nc/reglages.conf").write_text("IA_MODE=non\n")      # rien d'ajouté par nc-keys lui-même
            env = dict(os.environ, HOME=str(home), XDG_CONFIG_HOME=str(home / ".config"), PATH=f"{faux}:/usr/bin:/bin",
                       NC_LANGUE="fr")
            return subprocess.run([str(NC_KEYS), "json"], env=env, capture_output=True, text=True, timeout=30)

    def lignes(self, r):
        self.assertEqual(r.returncode, 0, r.stderr)
        return {s["title"]: [(tuple(x["keys"]), x["text"]) for x in s["rows"]] for s in json.loads(r.stdout)}

    ATTENDU = {"Applis et barre": [(("Super", "Entrée"), "Terminal")],
               "Système": [(("Super", "L"), "Verrouiller l'écran")],
               "Souris": [(("Super", "Clic gauche"), "Déplacer la fenêtre")]}

    def comparer(self, r):
        l = self.lignes(r)
        self.assertEqual(sorted(l), sorted(self.ATTENDU), r.stdout)
        for sec, rows in self.ATTENDU.items():
            self.assertEqual(len(l[sec]), 1, l[sec])
            self.assertEqual(l[sec][0][1], rows[0][1])
            self.assertEqual(l[sec][0][0][0], "Super")
        return l

    def test_format_056_et_057_donnent_la_meme_fiche(self):
        self.assertEqual(self.comparer(self.lancer(TEXTE_056)), self.comparer(self.lancer(TEXTE_057)))

    def test_secours_json_si_le_texte_ne_donne_rien(self):
        self.assertEqual(self.comparer(self.lancer("format inconnu\n", JSON_057)), self.comparer(self.lancer(TEXTE_056)))

    def test_aucun_raccourci_decrit_une_raison_claire(self):
        # Config de Hyprland en erreur (descriptions perdues), sortie vide, JSON vide : code 1 et une ligne, jamais []
        for texte, js in (("", "[]"), ("bind\n\tflags: \n\tmodmask: 0\n\tkey: A\n\tdescription: \n\n", None), (None, "pas du json")):
            with self.subTest(texte=texte, json=js):
                r = self.lancer(texte, js)
                self.assertEqual(r.returncode, 1)
                self.assertEqual(r.stdout, "")
                self.assertEqual(len(r.stderr.strip().splitlines()), 1, r.stderr)
                self.assertIn("aucun raccourci décrit", r.stderr)
                self.assertIn("configerrors", r.stderr)

    def test_hyprctl_en_echec(self):
        r = self.lancer(TEXTE_056, echec=True)
        self.assertEqual(r.returncode, 1)
        self.assertIn("Hyprland ne répond pas", r.stderr)
        self.assertNotIn("Traceback", r.stderr)


@unittest.skipUnless(shutil.which("lua"), "Lua requis")
class PluginSansDonnees(unittest.TestCase):
    """Le plugin ne montre jamais une fiche vide : nc-keys absent, en échec, ou une liste vide donnent un message."""
    def texte(self, existe, resultat):
        harness = r'''
local rendu
local function noeud(k) return function(o, enfants) return { k = k, o = o or {}, e = enfants or {} } end end
ui = setmetatable({}, { __index = function(_, k) return noeud(k) end })
panel = { render = function(n) rendu = n end, setNeedsFrameTick = function() end, close = function() end }
noctalia = {
  getenv = function() return "fr" end, expandPath = function(p) return p end, readFile = function() return "" end,
  fileExists = function(p) return ''' + ("true" if existe else "false") + r''' and p == "~/.local/bin/nc-keys" end,
  focusedOutputName = function() return "E" end,
  outputs = function() return { { name = "E", focused = true, width = 1600, height = 1000 } } end,
  json = { decode = function(t) if t == "[]" then return {} end return nil end },
  runAsync = function(_, cb) if cb then cb(''' + resultat + r''') end end,
}
dofile(arg[1])
onOpen()
local function labels(n, out) if n.k == "label" then out[#out + 1] = n.o.text end
  for _, e in ipairs(n.e or {}) do labels(e, out) end; return out end
print(table.concat(labels(rendu, {}), "|"))
'''
        r = subprocess.run(["lua", "-", str(PANEL)], input=harness, text=True, capture_output=True, timeout=10)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return r.stdout.strip()

    def test_nc_keys_absent(self):
        t = self.texte(False, '{ exitCode = 0, stdout = "[]" }')
        self.assertIn("Aucun raccourci lu : nc-keys est absent", t)

    def test_echec_affiche_la_raison_de_nc_keys(self):
        t = self.texte(True, '{ exitCode = 1, stdout = "", stderr = "nc-keys : « hyprctl binds » ne donne aucun raccourci décrit (voir hyprctl configerrors)\\n" }')
        self.assertIn("Aucun raccourci lu : « hyprctl binds » ne donne aucun raccourci décrit (voir hyprctl configerrors)", t)
        self.assertNotIn("Lecture des raccourcis", t)

    def test_liste_vide_ou_illisible(self):
        for res in ('{ exitCode = 0, stdout = "[]" }', '{ exitCode = 0, stdout = "n importe quoi" }', '{ exitCode = 124 }'):
            with self.subTest(res=res):
                t = self.texte(True, res)
                self.assertIn("Aucun raccourci lu : nc-keys n'a rien renvoyé de lisible", t)
                self.assertNotIn("Lecture des raccourcis", t)


if __name__ == "__main__":
    unittest.main()

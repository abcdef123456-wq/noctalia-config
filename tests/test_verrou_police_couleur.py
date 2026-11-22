"""Verrou : choix de la police (VERROU_POLICE) et de la couleur (VERROU_COULEUR) de l'heure (nc-verrou heure.luau).
Le bloc « DEBUT choix » / « FIN choix » est écrit dans le sous-ensemble commun à Lua et Luau et exécuté avec lua (sauté
s'il est absent). L'effet réel de fontFamily dans Noctalia n'est pas testable ici : le reste est vérifié sur le texte."""
import json
from pathlib import Path
import re
import shutil
import subprocess
import unittest

from tests import _isolation  # noqa: F401

REPO = Path(__file__).resolve().parents[1]
HEURE = REPO / "home/.local/share/noctalia/plugins/nc-verrou/heure.luau"
REGLAGES = REPO / "home/.local/bin/nc-reglages"
LUA = shutil.which("lua") or shutil.which("lua5.4")
SRC = HEURE.read_text(encoding="utf-8")
BLOC = SRC.split("-- DEBUT choix", 1)[1].split("-- FIN choix", 1)[0].split("\n", 1)[1]

TESTS = r'''
local function egal(a, b, m) if a ~= b then error(m .. " : " .. tostring(a) .. " ~= " .. tostring(b)) end end
local inst = famillesInstallees("Inter,Inter Variable\nDejaVu Sans Mono\nNoto Sans\n")
egal(choisirPolice("Inter", inst), "Inter", "installée")
egal(choisirPolice("JetBrains Mono, DejaVu Sans Mono", inst), "DejaVu Sans Mono", "première absente, seconde présente")
egal(choisirPolice("DejaVu Sans Mono,Inter", inst), "DejaVu Sans Mono", "la première installée l'emporte")
egal(choisirPolice("  Inter  ,Noto Sans", inst), "Inter", "espaces ignorés")
egal(choisirPolice("JetBrains Mono, Fira Code", inst), nil, "aucune installée")
egal(choisirPolice("", inst), nil, "vide")
egal(choisirPolice(nil, inst), nil, "absent")
egal(choisirPolice(" , ,", inst), nil, "que des virgules")
egal(choisirPolice("Inter", nil), nil, "liste pas arrivée")
egal(choisirPolice("inter", inst), nil, "casse exacte")
egal(choisirCouleur("accent", '{"mPrimary": "#ff00aa", "mOnSurface": "#111111"}'), "#ff00aa", "accent")
egal(choisirCouleur("blanc", '{"mPrimary": "#ff00aa"}'), "#ffffff", "blanc choisi")
egal(choisirCouleur(nil, '{"mPrimary": "#ff00aa"}'), "#ffffff", "réglage absent")
egal(choisirCouleur("accent", nil), "#ffffff", "fichier absent")
egal(choisirCouleur("accent", '{"mPrimary": "rouge"}'), "#ffffff", "pas #rrggbb")
egal(choisirCouleur("accent", '{"mPrimary": "#fff"}'), "#ffffff", "trop court")
egal(choisirCouleur("accent", '{"mPrimary": "#ff00aazz"}'), "#ffffff", "trop long")
egal(choisirCouleur("accent", '{"mSecondary": "#ff00aa"}'), "#ffffff", "pas de mPrimary")
egal(choisirCouleur("accent", "pas du json"), "#ffffff", "mal formé")
egal(choisirCouleur("accent", string.rep(" ", 70000) .. '{"mPrimary": "#ff00aa"}'), "#ffffff", "énorme")
print("OK")
'''


@unittest.skipUnless(LUA, "lua absent")
class Logique(unittest.TestCase):
    def test_choix(self):
        r = subprocess.run([LUA, "-"], input=BLOC + TESTS, capture_output=True, text=True, timeout=30)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("OK", r.stdout)


class Texte(unittest.TestCase):
    def test_fontfamily_seulement_si_choisie(self):
        self.assertEqual(len(re.findall(r"fontFamily = police\b", SRC)), 2)
        self.assertRegex(SRC, r"local police = polices and choisirPolice\(r\.VERROU_POLICE, polices\)")
        self.assertNotRegex(SRC, r"fontFamily = r\.")             # jamais la valeur brute du réglage

    def test_liste_lue_une_fois(self):
        self.assertEqual(SRC.count('"fc-list"'), 1)
        self.assertLess(SRC.index('"fc-list"'), SRC.index("function rendre()"))

    def test_couleur_relue_avec_les_reglages(self):
        self.assertIn("colors.json", SRC)
        self.assertEqual(SRC.count("readFile(noctalia.expandPath(\"~/.config/noctalia/colors.json\"))"), 1)

    def test_batterie_musique_intactes(self):
        d = HEURE.parent
        self.assertNotIn("fontFamily", (d / "batterie.luau").read_text(encoding="utf-8"))
        self.assertNotIn("fontFamily", (d / "musique.luau").read_text(encoding="utf-8"))

    def test_reponse_de_fc_list_protegee(self):
        """Rappel de runAsync : r doit être une table et r.stdout une chaîne, sinon polices reste nil, sans redessin."""
        debut = SRC.index('noctalia.runAsync({ "fc-list"')
        rappel = SRC[debut:SRC.index("end, 5000)", debut)]
        garde = rappel.index('if type(r) ~= "table" or type(r.stdout) ~= "string" then return end')
        self.assertLess(garde, rappel.index("polices = famillesInstallees(r.stdout)"))
        self.assertLess(garde, rappel.index('derniere = ""'))

    def test_aucun_theme_ne_pose_la_police_du_verrou(self):
        """fontFamily dans Noctalia n'a jamais été essayé à l'écran : aucun thème ne pose VERROU_POLICE pour l'instant."""
        for f in sorted((REPO / "home/.local/share/nc/themes").glob("*.json")):
            with self.subTest(theme=f.stem):
                self.assertNotIn("VERROU_POLICE", json.loads(f.read_text(encoding="utf-8"))["reglages"])

    def test_reglages_declares(self):
        t = REGLAGES.read_text(encoding="utf-8")
        self.assertRegex(t, r'R\("VERROU_POLICE", "Apparence".*?"texte", ""')
        self.assertRegex(t, r'R\("VERROU_COULEUR", "Apparence".*?"choix", "blanc"')


if __name__ == "__main__":
    unittest.main()

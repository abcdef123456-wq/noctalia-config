"""FENETRES_GESTE : un geste d'ouverture par thème. nc/apparence.lua en tire le style natif de windowsIn (et sa courbe
pour rail et feuille) ; pour les gestes du plugin nc-gestes, ce style est le repli quand le plugin n'est pas chargé.
« auto », absent ou inconnu rendent exactement les appels d'avant. Faux hl / nc (test_caractere_animations)."""
import json
from pathlib import Path
import re
import unittest

from tests.test_caractere_animations import LUA, REF_ANIMS, REF_COURBES, charger_reglages, lancer

REPO = Path(__file__).resolve().parents[1]
THEMES = REPO / "home/.local/share/nc/themes"
PLUGIN_MAIN = REPO / "plugins/nc-gestes/src/main.cpp"
# Styles de fenêtre qu'Hyprland 0.57 comprend (WindowAnimationController.cpp) : tout autre texte tombe en popin
STYLE_FENETRE = re.compile(r"^(popin \d{1,3}%|slide( (top|bottom|left|right))?|gnomed)$")


def gestes_du_plugin():
    return re.findall(r'\{"([a-z]+)", (?:GESTE_GOUTTE|\d+), \d+\}', PLUGIN_MAIN.read_text(encoding="utf-8"))


def gestes_des_themes():
    return {f.stem: json.loads(f.read_text(encoding="utf-8"))["reglages"].get("FENETRES_GESTE") for f in sorted(THEMES.glob("*.json"))}


class Choix(unittest.TestCase):
    def test_plugin_et_reglages_d_accord(self):
        valeurs = [v for v, _ in charger_reglages().PAR_CLE["FENETRES_GESTE"].choix()]
        plugin = gestes_du_plugin()
        self.assertEqual(len(plugin), 14)
        self.assertEqual(valeurs[0], "auto")
        for g in plugin:
            self.assertIn(g, valeurs)          # chaque geste du plugin se choisit dans nc-reglages

    def test_un_geste_distinct_par_theme(self):
        par_theme = gestes_des_themes()
        self.assertEqual(len(par_theme), 23)
        # noctalia garde « auto » : son style.conf reste celui de main à l'octet (test_themes)
        self.assertIsNone(par_theme.pop("noctalia"))
        self.assertEqual(len(set(par_theme.values())), 22, par_theme)
        self.assertTrue(set(gestes_du_plugin()) <= set(par_theme.values()))


@unittest.skipUnless(LUA, "lua absent")
class Apparence(unittest.TestCase):
    def test_auto_absent_inconnu_identiques_a_main(self):
        for reg in ({"FENETRES_GESTE": "auto"}, {"FENETRES_GESTE": "inconnu"}, {"FENETRES_GESTE": ""}):
            c, a, _ = lancer(reg)
            self.assertEqual(c, REF_COURBES, reg)
            self.assertEqual(a, REF_ANIMS, reg)

    def test_chaque_geste_un_style_valide(self):
        for v, _ in charger_reglages().PAR_CLE["FENETRES_GESTE"].choix():
            if v == "auto":
                continue
            with self.subTest(geste=v):
                c, a, _ = lancer({"FENETRES_GESTE": v, "FENETRES_OUVERTURE": "gnomed"})
                entree, sortie = a[2], a[3]
                self.assertEqual(entree[0], "windowsIn")
                self.assertRegex(entree[4], STYLE_FENETRE)
                self.assertEqual(sortie[4], entree[4])          # la fermeture suit le même geste
                courbe = "geste" in c
                self.assertEqual(courbe, v in ("rail", "feuille"))
                self.assertEqual(entree[3], "geste" if courbe else "emphasized")

    def test_le_geste_passe_avant_l_ouverture(self):
        _, a, _ = lancer({"FENETRES_GESTE": "horizon", "FENETRES_OUVERTURE": "gnomed"})
        self.assertEqual(a[2][4], "slide bottom")


if __name__ == "__main__":
    unittest.main()

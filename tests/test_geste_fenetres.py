"""FENETRES_GESTE : un geste d'ouverture par thème. nc/apparence.lua en tire le style natif de windowsIn (et sa courbe
pour rail et feuille) ; pour les gestes du plugin nc-gestes, ce style est le repli quand le plugin n'est pas chargé.
« auto », absent ou inconnu rendent exactement les appels d'avant. nc.gestes_sync (nc/energie.lua) donne au plugin le
geste, coupé avec les animations. Faux hl / nc (test_caractere_animations)."""
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

from tests.test_caractere_animations import (APPARENCE, ENERGIE, LUA, PRELUDE, REF_ANIMS, REF_COURBES, charger_reglages,
                                             lancer)

REPO = Path(__file__).resolve().parents[1]
THEMES = REPO / "home/.local/share/nc/themes"
PLUGIN_MAIN = REPO / "plugins/nc-gestes/src/main.cpp"
# Styles de fenêtre qu'Hyprland 0.57 comprend (WindowAnimationController.cpp) : tout autre texte tombe en popin
STYLE_FENETRE = re.compile(r"^(popin \d{1,3}%|slide( (top|bottom|left|right))?|gnomed)$")


def gestes_du_plugin():
    return re.findall(r'\{"([a-z]+)", (?:GESTE_GOUTTE|\d+), \d+\}', PLUGIN_MAIN.read_text(encoding="utf-8"))


def gestes_des_themes():
    return {f.stem: json.loads(f.read_text(encoding="utf-8"))["reglages"].get("FENETRES_GESTE") for f in sorted(THEMES.glob("*.json"))}


def synchro(reg, profil=None, batterie=False, jeu=False):
    """(enabled, mode, speed) de la commande hyprctl que nc.gestes_sync lance au chargement de nc/energie.lua."""
    with tempfile.TemporaryDirectory() as run:
        if jeu:
            Path(run, "nc-mode-jeu").touch()
        lig = ", ".join(f"{k} = {json.dumps(v)}" for k, v in reg.items())     # json : true / false / "texte", comme Lua
        code = (f"REG = {{ {lig} }}\nPROFIL = {json.dumps(profil) if profil else 'nil'}\nBATTERIE = {json.dumps(batterie)}\n"
                + PRELUDE + f'dofile("{APPARENCE}")\ndofile("{ENERGIE}")\nio.write(cmds[#cmds])\n')
        r = subprocess.run([LUA, "-"], input=code, capture_output=True, text=True, timeout=30,
                           env=dict(os.environ, XDG_RUNTIME_DIR=run))
    assert r.returncode == 0, r.stdout + r.stderr
    m = re.fullmatch(r"hyprctl nc-gestes set enabled ([01]) mode ([a-z]+) speed (\d+\.\d\d) >/dev/null 2>&1", r.stdout)
    assert m, r.stdout
    return m.groups()


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


@unittest.skipUnless(LUA, "lua absent")
class Synchro(unittest.TestCase):
    def test_geste_du_plugin_sinon_natif(self):
        plugin = set(gestes_du_plugin())
        for v, _ in charger_reglages().PAR_CLE["FENETRES_GESTE"].choix():
            with self.subTest(geste=v):
                self.assertEqual(synchro({"FENETRES_GESTE": v}), ("1", v if v in plugin else "natif", "1.00"))
        self.assertEqual(synchro({}), ("1", "natif", "1.00"))

    def test_coupe_avec_les_animations(self):
        for reg, cas in (({"FENETRES_ANIMATIONS": False}, {}), ({"FENETRES_CARACTERE": "aucun"}, {}),
                         ({"EFFETS": "aucun"}, {}), ({}, {"profil": "power-saver"}), ({}, {"jeu": True}),
                         ({"ILE_ANIM_BATTERIE": "aucune"}, {"batterie": True})):
            with self.subTest(reg=reg, cas=cas):
                self.assertEqual(synchro({"FENETRES_GESTE": "goutte", **reg}, **cas)[:2], ("0", "goutte"))
        # Économie avec les effets gardés (ECO_EFFETS) : le geste reste
        self.assertEqual(synchro({"FENETRES_GESTE": "goutte", "ECO_EFFETS": False}, profil="power-saver")[0], "1")

    def test_vitesse(self):
        for reg, batterie, vitesse in (({}, True, "1.25"), ({"ILE_ANIM_BATTERIE": "continues"}, True, "1.00"),
                                       ({"FENETRES_ANIMATIONS_VITESSE": "lente"}, False, "0.67"),
                                       ({"FENETRES_ANIMATIONS_VITESSE": "rapide"}, False, "1.54"),
                                       ({"FENETRES_CARACTERE": "vif"}, False, "1.33")):
            with self.subTest(reg=reg, batterie=batterie):
                self.assertEqual(synchro({"FENETRES_GESTE": "maree", **reg}, batterie=batterie), ("1", "maree", vitesse))


if __name__ == "__main__":
    unittest.main()

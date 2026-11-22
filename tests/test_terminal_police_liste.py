"""TERMINAL_POLICE accepte une liste « A, B, C » avec repli (comme ILE_POLICE et VERROU_POLICE) : kitty prend la
première police installée ; aucune installée : kitty.conf reste comme avant. Faux fc-list, HOME isolé, aucun kitty."""
import copy
import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[1]
BIN = REPO / "home/.local/bin"
THEMES = REPO / "home/.local/share/nc/themes"
# Famille d'allure de l'île et du terminal que chaque thème (sauf noctalia) posera en entier (A7)
FAMILLE_ILE = ("ILE_STYLE", "ILE_CONTOUR", "ILE_CONTOUR_EPAISSEUR", "ILE_CONTOUR_FERMEE", "ILE_RAYON", "ILE_VERRE",
               "ILE_POLICE", "ILE_ANIM", "ILE_LUEUR", "ILE_MAJUSCULES", "ILE_ACCENTS")
FAMILLE_TERMINAL = ("TERMINAL_POLICE", "TERMINAL_OPACITE", "TERMINAL_MARGE", "TERMINAL_CURSEUR")


def charger():
    l = importlib.machinery.SourceFileLoader("nc_reglages_police", str(BIN / "nc-reglages"))
    s = importlib.util.spec_from_loader("nc_reglages_police", l)
    m = importlib.util.module_from_spec(s)
    l.exec_module(m)
    return m


class PoliceListe(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.m = charger()
        self.m.KITTY_OUT = os.path.join(self.tmp.name, "kitty/nc-reglages.conf")
        self.installees = {"Alpha Nerd Font Mono", "Beta Nerd Font Mono", "Gamma Nerd Font Mono"}
        # Faux fc-list : la liste est posée sur la fonction qui lit fc-list (sortie_memo garde 30 s)
        p = patch.object(self.m, "sortie_memo", lambda cmd, duree=30: "\n".join(sorted(self.installees)) + "\n"
                         if cmd[0] == "fc-list" else "")
        p.start(); self.addCleanup(p.stop)
        r = patch.object(self.m.subprocess, "run"); r.start(); self.addCleanup(r.stop)

    def kitty(self):
        try:
            return Path(self.m.KITTY_OUT).read_text(encoding="utf-8")
        except OSError:
            return None

    def test_premiere_installee(self):
        self.m.appliquer_terminal({"TERMINAL_POLICE": "Absente, Beta Nerd Font Mono, Alpha Nerd Font Mono"})
        self.assertIn("font_family Beta Nerd Font Mono\n", self.kitty())

    def test_aucune_installee_kitty_inchange(self):
        os.makedirs(os.path.dirname(self.m.KITTY_OUT))
        base = Path(self.m.KITTY_OUT).with_name("kitty.conf")
        base.write_text("font_family Ma police\nfont_size 11\n", encoding="utf-8")
        self.m.appliquer_terminal({"TERMINAL_POLICE": "Absente, Autre absente"})
        self.assertEqual(base.read_text(encoding="utf-8"), "font_family Ma police\nfont_size 11\n")
        self.assertNotIn("font_family", self.kitty() or "")       # aucune ligne de police ajoutée
        self.m.appliquer_terminal({"TERMINAL_POLICE": "Absente, Autre absente", "TERMINAL_MARGE": "4"})
        self.assertNotIn("font_family", self.kitty())
        self.assertIn("window_padding_width 4", self.kitty())

    def test_valeur_simple(self):
        self.m.appliquer_terminal({"TERMINAL_POLICE": "Gamma Nerd Font Mono"})
        self.assertIn("font_family Gamma Nerd Font Mono\n", self.kitty())
        self.assertEqual(self.m.PAR_CLE["TERMINAL_POLICE"].valider("Gamma Nerd Font Mono"), "Gamma Nerd Font Mono")

    def test_validation_liste(self):
        v = self.m.PAR_CLE["TERMINAL_POLICE"].valider
        self.assertEqual(v("Absente ,Beta-Mono,  Nerd 2"), "Absente, Beta-Mono, Nerd 2")
        self.assertEqual(v("A1, B2, C3, D4"), "A1, B2, C3, D4")

    def test_refus(self):
        v = self.m.PAR_CLE["TERMINAL_POLICE"].valider
        for mauvais in ("A, B, C, D, E", "A, , B", "A, B;rm", "A, B" + chr(9) + "C", "A, B" + chr(0) + "C",
                        "A, B" + chr(10) + "C", "A, B" + chr(0x202e), "A, B" + chr(0x200f), "A, B" + chr(0x1b) + "[0m",
                        "A, -", "A, B/C"):
            with self.subTest(mauvais=mauvais), self.assertRaises(ValueError):
                v(mauvais)

    def theme(self, **reglages):
        d = json.loads((THEMES / "apple.json").read_text(encoding="utf-8"))
        d["reglages"].update(reglages)
        return d

    def test_un_theme_peut_poser_une_liste(self):
        t = self.m._verifier_theme("apple", self.theme(TERMINAL_POLICE="Absente, Beta Nerd Font Mono"))
        self.assertEqual(t["reglages"]["TERMINAL_POLICE"], "Absente, Beta Nerd Font Mono")
        with self.assertRaises(ValueError):
            self.m._verifier_theme("apple", self.theme(TERMINAL_POLICE="A, B, C, D, E"))

    def test_reglages_d_allure_poses_par_un_theme(self):
        """A6 : chaque réglage ILE_*/TERMINAL_* d'allure est accepté dans « reglages » d'un thème avec sa valeur par défaut."""
        for cle in FAMILLE_ILE + FAMILLE_TERMINAL:
            r = self.m.PAR_CLE[cle]
            v = "Alpha Nerd Font Mono" if cle == "TERMINAL_POLICE" else r.defaut
            with self.subTest(cle=cle):
                self.m._verifier_theme("apple", self.theme(**{cle: v}))

    @unittest.skip("activé en A7")
    def test_familles_completes(self):
        for f in sorted(THEMES.glob("*.json")):
            if f.stem == "noctalia":
                continue
            reglages = json.loads(f.read_text(encoding="utf-8"))["reglages"]
            with self.subTest(theme=f.stem):
                for cle in FAMILLE_ILE + FAMILLE_TERMINAL:
                    self.assertIn(cle, reglages)


if __name__ == "__main__":
    unittest.main()

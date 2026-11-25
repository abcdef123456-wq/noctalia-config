"""Rangement des fenêtres (part du maître, maître au centre, fenêtre seule centrée, largeur des colonnes, partage de la
spirale). apparence.lua est exécuté avec lua et de faux hl / nc : jamais le vrai Hyprland. L'effet à l'écran n'est pas testé."""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

from tests import _isolation  # noqa: F401
from tests.test_fenetres_famille import APPARENCE, LUA, PRELUDE, REPO, charger_reglages, cle, lancer

CLES = ("FENETRES_MAITRE_PART", "FENETRES_MAITRE_CENTRE_AIR", "FENETRES_SEULE_CENTREE", "FENETRES_COLONNE_LARGEUR",
        "FENETRES_COUPE")
M = {"FENETRES_DISPOSITION": "master"}
S = {"FENETRES_DISPOSITION": "scrolling"}


def avant():
    """apparence.lua de 3c8f7e3 (avant le rangement), pour comparer appel par appel."""
    return subprocess.run(["git", "show", "3c8f7e3:home/.config/hypr/nc/apparence.lua"], cwd=REPO, capture_output=True,
                          text=True, check=True).stdout


def lancer_texte(texte, reg):
    lig = ", ".join(f'{k} = "{v}"' for k, v in reg.items())
    code = f'REG = {{ {lig} }}\nPROFIL = nil\n' + PRELUDE + texte + '\nio.write("[" .. table.concat(cfg, ",") .. "]")\n'
    r = subprocess.run([LUA, "-"], input=code, capture_output=True, text=True, timeout=30)
    assert r.returncode == 0, r.stdout + r.stderr
    return json.loads(r.stdout)


@unittest.skipUnless(LUA, "lua absent")
class Lua(unittest.TestCase):
    def test_defaut_identique_a_avant(self):
        try:
            ref_texte = avant()
        except (subprocess.CalledProcessError, FileNotFoundError):
            self.skipTest("commit 3c8f7e3 absent (clone superficiel)")
        faux = {c: v for c, v in zip(CLES, ("x", "x", "x", "x", "x"))}
        for disp in ("dwindle", "master", "scrolling"):
            base = {"FENETRES_DISPOSITION": disp}
            ref = lancer_texte(ref_texte, base)
            for reg in ({}, dict.fromkeys(CLES, "auto"), dict.fromkeys(CLES, ""), faux,
                        {"FENETRES_SEULE_CENTREE": "non", "FENETRES_MAITRE_PART": "2.0"}):
                self.assertEqual(lancer({**base, **reg}), ref, (disp, reg))

    def test_part_du_maitre(self):
        for v in ("0.3", "0.55", "0.8"):
            self.assertEqual(cle(lancer({**M, "FENETRES_MAITRE_PART": v}), "master", "mfact"), float(v))
        for v in ("2.0", "0.1", "0.81", "abc", "auto"):   # hors bornes ou faux : rien
            self.assertIsNone(cle(lancer({**M, "FENETRES_MAITRE_PART": v}), "master", "mfact"), v)
        self.assertIsNone(cle(lancer({"FENETRES_MAITRE_PART": "0.6"}), "master", "mfact"))   # dwindle : ignoré

    def test_maitre_centre_air(self):
        a = lancer({**M, "FENETRES_MAITRE_CENTRE_AIR": "oui"})
        self.assertEqual(cle(a, "master", "slave_count_for_center_master"), 0)
        self.assertEqual(cle(a, "master", "orientation"), "center")
        a = lancer({**M, "FENETRES_MAITRE_CENTRE_AIR": "oui", "FENETRES_MAITRE_ORIENTATION": "droite"})
        self.assertEqual(cle(a, "master", "orientation"), "right")   # le choix explicite reste
        for reg in ({**M, "FENETRES_MAITRE_CENTRE_AIR": "auto"}, {**M, "FENETRES_MAITRE_CENTRE_AIR": "x"},
                    {"FENETRES_MAITRE_CENTRE_AIR": "oui"}):
            a = lancer(reg)
            self.assertIsNone(cle(a, "master", "slave_count_for_center_master"), reg)
            self.assertIsNone(cle(a, "master", "orientation"), reg)

    def test_seule_centree(self):
        for v, xy in (("16:10", (16, 10)), ("4:3", (4, 3)), ("1:1", (1, 1))):
            self.assertEqual(cle(lancer({"FENETRES_SEULE_CENTREE": v}), "layout", "single_window_aspect_ratio"),
                             {"1": xy[0], "2": xy[1]})   # tableau Lua à 2 éléments : le vec2 de Hyprland (pas de clés x, y)
        for v in ("non", "auto", "3:2", ""):
            self.assertIsNone(cle(lancer({"FENETRES_SEULE_CENTREE": v}), "layout", "single_window_aspect_ratio"), v)

    def test_largeur_des_colonnes(self):
        self.assertEqual(cle(lancer({**S, "FENETRES_COLONNE_LARGEUR": "0.5"}), "scrolling", "column_width"), 0.5)
        for v in ("1.5", "0.1", "abc", "auto"):
            self.assertIsNone(cle(lancer({**S, "FENETRES_COLONNE_LARGEUR": v}), "scrolling", "column_width"), v)
        self.assertIsNone(cle(lancer({"FENETRES_COLONNE_LARGEUR": "0.5"}), "scrolling", "column_width"))

    def test_coupe(self):
        self.assertEqual(cle(lancer({"FENETRES_COUPE": "0.7"}), "dwindle", "default_split_ratio"), 0.7)
        for v in ("1.8", "0.2", "abc", "auto"):
            self.assertIsNone(cle(lancer({"FENETRES_COUPE": v}), "dwindle", "default_split_ratio"), v)
        self.assertIsNone(cle(lancer({**M, "FENETRES_COUPE": "0.7"}), "dwindle", "default_split_ratio"))

    def test_aucune_option_de_rendu(self):
        txt = APPARENCE.read_text(encoding="utf-8")
        i = txt.index("-- Rangement : posé")
        bloc = txt[i:txt.index("\nend", i)]
        for interdit in ("render", "cm_", "fp16", "xp_mode", "blur", "new_render_scheduling"):
            self.assertNotIn(interdit, bloc)
        for interdit in ("render:", "cm_enabled", "use_fp16", "xp_mode", "new_render_scheduling"):
            self.assertNotIn(interdit, txt)

    def test_la_personne_gagne_sur_le_theme(self):
        """Vraie lecture de style.conf puis reglages.conf (extraite de hyprland.lua)."""
        src = (REPO / "home/.config/hypr/hyprland.lua").read_text(encoding="utf-8")
        i = src.index("nc.reglages = {}")
        j = src.index("\nend\n", src.index("function nc.reglage")) + 5
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / ".config/nc").mkdir(parents=True)
            (Path(d) / ".config/nc/style.conf").write_text("FENETRES_COUPE=0.5\nFENETRES_SEULE_CENTREE=4:3\n")
            (Path(d) / ".config/nc/reglages.conf").write_text("FENETRES_COUPE=0.9\n")
            code = (f'nc = {{}}\n{src[i:j]}\nhl = {{ config = function(t) CFG = t end }}\n'
                    'io.write(nc.reglage("FENETRES_COUPE", "auto"), " ", nc.reglage("FENETRES_SEULE_CENTREE", "non"))')
            r = subprocess.run([LUA, "-"], input=code, capture_output=True, text=True, timeout=30,
                               env={**os.environ, "HOME": d})
        self.assertEqual(r.stdout, "0.9 4:3", r.stderr)   # reglages.conf devant, le thème seulement là où la personne n'a rien mis


class Reglages(unittest.TestCase):
    def test_valeurs(self):
        reg = charger_reglages()
        attendu = {"FENETRES_MAITRE_PART": ("auto", "0.30", "0.55", "0.80"),
                   "FENETRES_MAITRE_CENTRE_AIR": ("auto", "oui"),
                   "FENETRES_SEULE_CENTREE": ("non", "16:10", "4:3", "1:1"),
                   "FENETRES_COLONNE_LARGEUR": ("auto", "0.30", "0.50", "1.00"),
                   "FENETRES_COUPE": ("auto", "0.30", "1.00", "1.70")}
        for k, vals in attendu.items():
            r = reg.PAR_CLE[k]
            self.assertEqual(r.section, "Fenêtres")
            self.assertEqual(r.defaut, vals[0])
            for v in vals:
                self.assertEqual(r.valider(v), v, (k, v))
            for v in ("2.0", "inconnu", "", "9:9"):
                with self.assertRaises(ValueError, msg=(k, v)):
                    r.valider(v)
            self.assertNotIn(k, reg.DISTANT_PERMIS)

    def test_aide_fr_en(self):
        reg = charger_reglages()
        for k in CLES:
            r = reg.PAR_CLE[k]
            self.assertTrue(str(r.nom) and str(r.aide), k)

    def test_theme_accepte_les_cles(self):
        reg = charger_reglages()
        d = {"nom": "essai", "libelle": {"fr": "Essai", "en": "Test"}, "palette": {"source": "fond", "nom": ""},
             "reglages": {"FENETRES_MAITRE_PART": "0.60", "FENETRES_MAITRE_CENTRE_AIR": "oui",
                          "FENETRES_SEULE_CENTREE": "16:10", "FENETRES_COLONNE_LARGEUR": "0.50", "FENETRES_COUPE": "0.70"}}
        self.assertEqual(reg._verifier_theme("essai", d)["reglages"]["FENETRES_COUPE"], "0.70")
        d["reglages"]["FENETRES_COUPE"] = "5"
        with self.assertRaises(ValueError):
            reg._verifier_theme("essai", d)

    def test_themes_livres_deux_fenetres_entierement_visibles(self):
        for f in sorted((REPO / "home/.local/share/nc/themes").glob("*.json")):
            reg = json.loads(f.read_text(encoding="utf-8"))["reglages"]
            if reg.get("FENETRES_DISPOSITION") == "scrolling":
                largeur = reg.get("FENETRES_COLONNE_LARGEUR", "auto")
                self.assertTrue(largeur == "auto" or float(largeur) <= 0.5, f.name)
            if reg.get("FENETRES_DISPOSITION") == "master":
                self.assertNotEqual(reg.get("FENETRES_MAITRE_CENTRE_AIR"), "oui", f.name)


if __name__ == "__main__":
    unittest.main()

"""ILE_FORME : la forme de l'île suit le thème (pilule, encoche, rectangle, cadre, point).

- Hors écran avec le vrai qs (outils/rendu-ile.py, « -p ») : pilule = mêmes octets que le commit 3c8f7e3 (extrait dans un
  dossier temporaire) ; encoche = collée au bord haut (le pixel y = 0 au centre est de la couleur de l'île) ; rectangle =
  coin rempli ; cadre = centre presque transparent, bord de la couleur d'accent ; point = fermée, un point plein
  d'accent (centre) et rien à 20 px.
- nc-reglages : les 5 valeurs acceptées, les autres refusées, clé acceptée dans un thème, pas dans DISTANT_PERMIS."""
from tests import _isolation  # noqa: F401  (HOME, XDG_*, langue : avant tout le reste)
import importlib.machinery
import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests.test_rendu_ile import lire_png

DEPOT = Path(__file__).resolve().parents[1]
OUTIL = DEPOT / "outils/rendu-ile.py"
REF = "3c8f7e3"
FORMES = ("pilule", "encoche", "rectangle", "cadre", "point")


def charger_reglages():
    l = importlib.machinery.SourceFileLoader("nc_reglages_forme", str(DEPOT / "home/.local/bin/nc-reglages"))
    m = importlib.util.module_from_spec(importlib.util.spec_from_loader("nc_reglages_forme", l))
    l.exec_module(m)
    return m


def pixel(png, x, y):
    w, _, lignes = png
    return tuple(lignes[y][x * 4:x * 4 + 4])


def rendre(outil, dossier, etat, forme=None):
    env = {k: v for k, v in os.environ.items() if k in ("PATH", "LANG", "LC_ALL")}
    cmd = [sys.executable, str(outil), "--sortie", str(dossier)]
    if forme:
        conf = Path(dossier) / ("%s.conf" % forme)
        conf.write_text("ILE_FORME=%s\n" % forme)
        cmd += ["--reglages", str(conf)]
    r = subprocess.run(cmd + [etat], capture_output=True, text=True, env=env, timeout=240)
    assert r.returncode == 0, r.stderr
    return Path(dossier) / (etat + ".png")


def rendre_brut(dossier, forme):
    """Rend l'état « fermee » sans recadrage : (png, cadre de l'île dans la fenêtre)."""
    l = importlib.machinery.SourceFileLoader("rendu_ile_brut", str(OUTIL))
    m = importlib.util.module_from_spec(importlib.util.spec_from_loader("rendu_ile_brut", l))
    l.exec_module(m)
    vus = []
    m.recadrer = lambda png, cadre: vus.append(cadre)
    d = Path(dossier) / ("brut-" + forme)
    d.mkdir()
    conf = d / "r.conf"
    conf.write_text("ILE_FORME=%s\n" % forme)
    png, journal = m.rendre("fermee", str(d), str(conf), None)
    assert png and vus, journal[-800:]
    return lire_png(png), vus[0]


class Reglage(unittest.TestCase):
    def test_valeurs_acceptees_et_refusees(self):
        reg = charger_reglages()
        r = reg.PAR_CLE["ILE_FORME"]
        self.assertEqual(r.defaut, "pilule")
        for v in FORMES:
            self.assertEqual(r.valider(v), v)
        for v in ("", "rond", "Encoche", "carre"):
            with self.assertRaises(ValueError):
                r.valider(v)
        self.assertNotIn("ILE_FORME", reg.DISTANT_PERMIS)

    def test_theme_accepte_la_cle(self):
        reg = charger_reglages()
        d = {"nom": "essai", "libelle": {"fr": "Essai", "en": "Test"}, "palette": {"source": "fond", "nom": ""},
             "reglages": {"ILE_FORME": "encoche"}}
        self.assertEqual(reg._verifier_theme("essai", d)["reglages"]["ILE_FORME"], "encoche")
        d["reglages"]["ILE_FORME"] = "triangle"
        with self.assertRaises(ValueError):
            reg._verifier_theme("essai", d)


@unittest.skipUnless(shutil.which("qs"), "Quickshell (qs) absent")
class Rendu(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.t = Path(tempfile.mkdtemp(prefix="nct-"))
        cls.png = {}
        for f in FORMES:
            d = cls.t / f
            d.mkdir()
            cls.png[f] = lire_png(rendre(OUTIL, d, "fermee", f))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(str(cls.t), ignore_errors=True)

    def test_encoche_collee_au_bord_haut(self):
        # le recadrage de rendu-ile cache le décalage : on le coupe et on lit la fenêtre entière
        # pilule : l'île est à y = 9 de la fenêtre ; encoche : elle touche le bord haut (y = 0)
        for f, y_attendu in (("pilule", 9), ("encoche", 0)):
            png, cadre = rendre_brut(self.t, f)
            x, y, ew, eh, pw, ph = cadre
            self.assertEqual(y, y_attendu, f)
            e = png[0] / pw
            haut = pixel(png, int(round((x + ew / 2) * e)), 0)
            self.assertEqual(haut[3] > 200, y_attendu == 0, "%s %s" % (f, haut))
            if y_attendu == 0:
                self.assertLess(max(haut[:3]), 60)   # la couleur de l'île (noir verre)

    def test_rectangle_coin_rempli(self):
        # le coin de la pilule est arrondi (transparent), celui du rectangle presque carré (rempli)
        def coin(f):
            w, h, lignes = self.png[f]
            ys = [y for y in range(h) if lignes[y][3::4].count(255) > 0]
            xs = [x for x in range(w) if any(l[x * 4 + 3] > 200 for l in lignes)]
            return pixel(self.png[f], xs[0] + 2, ys[0] + 2)[3]
        self.assertGreater(coin("rectangle"), 200)
        self.assertLess(coin("pilule"), 100)

    def test_cadre_centre_transparent_et_bord_accent(self):
        w, h, lignes = self.png["cadre"]
        ys = [y for y in range(h) if any(lignes[y][i] > 0 for i in range(3, w * 4, 4))]
        y0, y1 = ys[0], ys[-1]
        xs = [x for x in range(w) if any(l[x * 4 + 3] > 0 for l in lignes)]
        # un point sans texte (près du bord gauche, à mi-hauteur) : le fond est presque transparent
        centre = pixel(self.png["cadre"], xs[0] + 6, (y0 + y1) // 2)
        self.assertLess(centre[3], 80)
        bord = pixel(self.png["cadre"], w // 2, y0)
        self.assertGreater(bord[3], 150)        # un trait net
        # le bord est coloré (accent), alors que le verre de l'île est noir sans teinte
        self.assertGreater(max(bord[:3]) - min(bord[:3]), 40)

    def test_point_ferme_plein_d_accent(self):
        w, h, lignes = self.png["point"]
        cx, cy = w // 2, h // 2
        centre = pixel(self.png["point"], cx, cy)
        self.assertGreater(centre[3], 240)
        self.assertGreater(max(centre[:3]) - min(centre[:3]), 40)   # accent coloré, pas le noir du verre
        for dx, dy in ((20, 0), (-20, 0), (0, 20), (0, -20)):
            self.assertLess(pixel(self.png["point"], cx + dx, cy + dy)[3], 40, (dx, dy))   # le fond, pas de pilule
        # la pilule d'origine, elle, couvre ce même point à 20 px
        wp, hp, _ = self.png["pilule"]
        self.assertGreater(pixel(self.png["pilule"], wp // 2 + 20, hp // 2)[3], 150)

    def test_pilule_identique_au_commit_de_reference(self):
        if not shutil.which("git"):
            self.skipTest("git absent")
        ref = self.t / "ref"
        ref.mkdir()
        a = subprocess.run(["git", "-C", str(DEPOT), "archive", REF], capture_output=True)
        if a.returncode != 0:
            self.skipTest("commit de référence absent (clone superficiel)")
        subprocess.run(["tar", "-x", "-C", str(ref)], input=a.stdout, check=True)
        for etat in ("fermee", "page", "recherche"):
            d1, d2 = self.t / ("a-" + etat), self.t / ("b-" + etat)
            d1.mkdir()
            d2.mkdir()
            vieux = rendre(ref / "outils/rendu-ile.py", d1, etat)
            neuf = rendre(OUTIL, d2, etat, "pilule")
            self.assertEqual(vieux.read_bytes(), neuf.read_bytes(), etat)


if __name__ == "__main__":
    unittest.main()

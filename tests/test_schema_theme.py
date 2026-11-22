"""outils/schema-theme.py : valeurs effectives, dessin, sortie refusée dans le dépôt."""
import importlib.util
from importlib.machinery import SourceFileLoader
from pathlib import Path
import tempfile
import unittest
from tests import _isolation


DEPOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_loader("schema_theme", SourceFileLoader("schema_theme", str(DEPOT / "outils/schema-theme.py")))
st = importlib.util.module_from_spec(spec)
spec.loader.exec_module(st)

try:
    import PIL  # noqa: F401
    PIL_OK = True
except ImportError:
    PIL_OK = False

THEME = {"libelle": "Essai", "palette": ["custom", "Absente"],
         "reglages": {"FENETRES_DISPOSITION": "master", "FENETRES_MAITRE_ORIENTATION": "droite", "DOCK": "non"},
         "noctalia": {"bar.default": {"position": "bottom", "thickness": 30, "margin_edge": 0}}}


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(dir=_isolation.dossier_court())
        t = Path(cls.tmp.name)
        cls.mod, _, _ = st.charger_reglages(DEPOT / "home/.local/share/nc/themes", t)
        cls.noct = st.lire_noctalia_defaut()

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()


class Valeurs(Base):
    def test_effectives(self):
        reg, n = st.valeurs_effectives(self.mod, THEME, self.noct)
        self.assertEqual(reg["FENETRES_DISPOSITION"], "master")
        self.assertEqual(reg["FENETRES_MAITRE_ORIENTATION"], "droite")
        self.assertEqual(n["bar"]["position"], "bottom")
        self.assertEqual(n["bar"]["thickness"], 30)
        self.assertEqual(n["bar"]["margin_edge"], 0)

    def test_noctalia_vide_donne_les_defauts(self):
        _, n = st.valeurs_effectives(self.mod, {}, self.noct)
        self.assertEqual(n["bar"], self.noct["bar"]["default"])
        self.assertEqual(n["dock"], self.noct["dock"])


@unittest.skipUnless(PIL_OK, "Pillow absent")
class Dessin(Base):
    def test_pixel_de_la_barre(self):
        from PIL import Image  # noqa: F401
        reg, n = st.valeurs_effectives(self.mod, THEME, self.noct)
        coul, neutre = st.palette_du_theme(self.mod, THEME, None)
        self.assertTrue(neutre)
        img = st.dessiner("essai", THEME, reg, n, coul, neutre, 800)
        self.assertEqual(img.size[0], 800)
        H = int(round(st.LOGIQUE[1] * 800 / st.LOGIQUE[0]))
        self.assertGreater(img.size[1], H)  # le bandeau de légende s'ajoute sous le schéma
        bas = img.getpixel((img.size[0] // 2, H - 3))  # barre collée en bas, centre = place de l'île
        haut = img.getpixel((img.size[0] // 2, 3))
        self.assertNotEqual(bas, haut)

    def test_barre_a_droite(self):
        t = {"reglages": {"FENETRES_DISPOSITION": "scrolling", "DOCK": "non"}, "palette": ["custom", "Absente"],
             "noctalia": {"bar.default": {"position": "right", "thickness": 40, "margin_edge": 0}}}
        reg, n = st.valeurs_effectives(self.mod, t, self.noct)
        coul, neutre = st.palette_du_theme(self.mod, t, None)
        W = 1000
        img = st.dessiner("essai", t, reg, n, coul, neutre, W)
        y = int(round(st.LOGIQUE[1] * W / st.LOGIQUE[0])) // 2
        ep = int(round(40 * W / st.LOGIQUE[0]))
        barre = img.getpixel((W - 3, y))
        self.assertNotEqual(barre, img.getpixel((2, y)))  # pas la couleur du fond
        for x in range(W - ep + 2, W):  # aucune fenêtre ne mord sur la barre
            # la barre est translucide : l'ombre d'une fenêtre peut la teinter de quelques unités, pas plus
            self.assertTrue(all(abs(a - b) <= 4 for a, b in zip(img.getpixel((x, y)), barre)), x)

    def test_ile_au_dessus_des_fenetres(self):
        t = {"reglages": {"FENETRES_DISPOSITION": "scrolling", "FENETRES_MARGE": "0", "DOCK": "non"},
             "palette": ["custom", "Absente"], "noctalia": {"bar.default": {"position": "bottom", "margin_edge": 0}}}
        reg, n = st.valeurs_effectives(self.mod, t, self.noct)
        coul, neutre = st.palette_du_theme(self.mod, t, None)
        W = 1000
        img = st.dessiner("essai", t, reg, n, coul, neutre, W)
        s = W / float(st.LOGIQUE[0])
        px = img.getpixel((int((W - 380 * s) / 2 + 20 * s), int(8 * s + 23 * s)))  # dans l'île, près de son bord gauche
        attendu = "#000000" if reg.get("ILE_STYLE") == "noir" else coul["surface"]
        # arrondis de la conversion : 1 d'écart ; la fenêtre dessous (mélange 6 %) en aurait environ 12
        self.assertTrue(all(abs(a - b) <= 1 for a, b in zip(px, st.rgb(attendu))), (px, attendu))

    def test_sortie_png(self):
        t = Path(self.tmp.name)
        rc = st.main(["apple", "--sortie", str(t / "s"), "--planche", str(t / "p.png"), "--largeur", "800"])
        self.assertEqual(rc, 0)
        self.assertTrue((t / "s/apple.png").is_file() and (t / "p.png").is_file())


class Refus(unittest.TestCase):
    def test_sortie_dans_le_depot(self):
        self.assertEqual(st.main(["apple", "--sortie", str(DEPOT / "essai-schema")]), 2)
        self.assertFalse((DEPOT / "essai-schema").exists())


if __name__ == "__main__":
    unittest.main()

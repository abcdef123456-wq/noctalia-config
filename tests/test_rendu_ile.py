"""outils/rendu-ile.py : les PNG hors écran de l'île (sauté si Quickshell est absent)."""
from tests import _isolation  # noqa: F401  (HOME, XDG_*, langue : avant tout le reste)
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
import zlib
from pathlib import Path

DEPOT = Path(__file__).resolve().parents[1]
OUTIL = DEPOT / "outils/rendu-ile.py"
ETATS = ("fermee", "musique", "page", "recherche")


def lire_png(chemin):
    """(largeur, hauteur, pixels en lignes d'octets) d'un PNG 8 bits RGB/RGBA non entrelacé."""
    d = Path(chemin).read_bytes()
    assert d[:8] == b"\x89PNG\r\n\x1a\n", "pas un PNG"
    pos, idat, ihdr = 8, b"", None
    while pos < len(d):
        n, t = struct.unpack(">I4s", d[pos:pos + 8])
        corps = d[pos + 8:pos + 8 + n]
        if t == b"IHDR":
            ihdr = struct.unpack(">IIBBBBB", corps)
        elif t == b"IDAT":
            idat += corps
        pos += 12 + n
    w, h, prof, couleur, _, _, entrelace = ihdr
    assert prof == 8 and couleur in (2, 6) and entrelace == 0, "format PNG non géré"
    bpp = 3 if couleur == 2 else 4
    brut, long_ = zlib.decompress(idat), w * bpp
    lignes, prec = [], bytearray(long_)
    for y in range(h):
        f = brut[y * (long_ + 1)]
        cur = bytearray(brut[y * (long_ + 1) + 1:(y + 1) * (long_ + 1)])
        for i in range(long_):
            a = cur[i - bpp] if i >= bpp else 0
            b = prec[i]
            c = prec[i - bpp] if i >= bpp else 0
            if f == 1:
                cur[i] = (cur[i] + a) & 255
            elif f == 2:
                cur[i] = (cur[i] + b) & 255
            elif f == 3:
                cur[i] = (cur[i] + (a + b) // 2) & 255
            elif f == 4:
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                cur[i] = (cur[i] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
        lignes.append(bytes(cur))
        prec = cur
    return w, h, lignes


def est_unie(w, lignes):
    """Vrai si tous les pixels de l'image sont identiques (image vide)."""
    n = len(lignes[0]) // w
    return len({l[i:i + n] for l in lignes for i in range(0, len(l), n)}) <= 1


def faire_png(w, h, rgb_par_ligne, couleur=2):
    def bloc(t, c):
        return struct.pack(">I", len(c)) + t + c + struct.pack(">I", zlib.crc32(t + c))
    brut = b"".join(b"\x00" + rgb_par_ligne(y) for y in range(h))
    return (b"\x89PNG\r\n\x1a\n" + bloc(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, couleur, 0, 0, 0))
            + bloc(b"IDAT", zlib.compress(brut)) + bloc(b"IEND", b""))


class AssistantsPng(unittest.TestCase):
    def test_image_unie_detectee(self):
        t = Path(tempfile.mkdtemp(prefix="nct-"))
        try:
            (t / "u.png").write_bytes(faire_png(4, 4, lambda y: b"\x10\x20\x30" * 4))
            (t / "v.png").write_bytes(faire_png(4, 4, lambda y: bytes([y * 40, 0, 9]) * 4))
            self.assertTrue(est_unie(*lire_png(t / "u.png")[::2]))
            self.assertFalse(est_unie(*lire_png(t / "v.png")[::2]))
        finally:
            shutil.rmtree(str(t), ignore_errors=True)


    def test_controle_refuse_le_rgb_et_accepte_le_rgba_transparent(self):
        m = charger_outil()
        t = Path(tempfile.mkdtemp(prefix="nct-"))
        try:
            (t / "rgb.png").write_bytes(faire_png(4, 4, lambda y: b"\x00\x00\x00" * 4))
            (t / "rgba.png").write_bytes(faire_png(4, 4, lambda y: b"\x00\x00\x00\x00" * 4, 6))
            (t / "opaque.png").write_bytes(faire_png(4, 4, lambda y: b"\x00\x00\x00\xff" * 4, 6))
            (t / "vide.png").write_bytes(b"")
            self.assertFalse(m.png_valide(t / "rgb.png"))
            self.assertFalse(m.png_valide(t / "opaque.png"))
            self.assertFalse(m.png_valide(t / "vide.png"))
            self.assertFalse(m.png_valide(t / "absent.png"))
            self.assertTrue(m.png_valide(t / "rgba.png"))
        finally:
            shutil.rmtree(str(t), ignore_errors=True)


class Refus(unittest.TestCase):
    def test_sortie_dans_le_depot_refusee(self):
        for sortie in (DEPOT / "rendu-essai", DEPOT):
            r = subprocess.run([sys.executable, str(OUTIL), "--sortie", str(sortie), "fermee"],
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 2, r.stderr)
            self.assertFalse((DEPOT / "rendu-essai").exists())


class Polices(unittest.TestCase):
    def test_dossier_de_polices_lu_sans_etre_modifie(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("rendu_ile", OUTIL)
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        with tempfile.TemporaryDirectory() as t:
            polices = Path(t) / "polices"
            polices.mkdir()
            (polices / "x.ttf").write_bytes(b"pas une vraie police")
            avant = (polices.stat().st_mtime_ns, (polices / "x.ttf").stat().st_mtime_ns)
            root = Path(t) / "root"
            root.mkdir()
            env = m.environnement(root, root / "a.png", str(polices))
            conf = Path(env["FONTCONFIG_FILE"])
            self.assertTrue(conf.is_file())
            self.assertEqual(conf.parent, root)
            texte = conf.read_text()
            self.assertIn("<dir>%s</dir>" % polices, texte)
            self.assertIn("/etc/fonts/fonts.conf", texte)
            self.assertIn("<cachedir>%s" % root, texte)
            self.assertNotIn("FONTCONFIG_FILE", m.environnement(root, root / "a.png"))
            apres = (polices.stat().st_mtime_ns, (polices / "x.ttf").stat().st_mtime_ns)
            self.assertEqual(avant, apres)
            self.assertEqual(sorted(p.name for p in polices.iterdir()), ["x.ttf"])

    def test_dossier_de_polices_absent_refuse(self):
        with tempfile.TemporaryDirectory() as t:
            r = subprocess.run([sys.executable, str(OUTIL), "--sortie", t, "--polices", t + "/nexiste-pas", "fermee"],
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 2, r.stderr)


    def test_echelle_hors_limites_refusee(self):
        with tempfile.TemporaryDirectory() as t:
            for n in ("0", "4"):
                r = subprocess.run([sys.executable, str(OUTIL), "--sortie", t, "--echelle", n, "fermee"],
                                   capture_output=True, text=True)
                self.assertEqual(r.returncode, 2, r.stderr)
                self.assertIn("échelle", r.stderr)


def charger_outil():
    import importlib.util
    spec = importlib.util.spec_from_file_location("rendu_ile", OUTIL)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def modeles_cpu():
    try:
        lignes = Path("/proc/cpuinfo").read_text(errors="replace").splitlines()
    except OSError:
        return set()
    return {l.split(":", 1)[1].strip() for l in lignes if l.startswith("model name") and ":" in l}


class SystemeFactice(unittest.TestCase):
    def test_faux_scripts_dans_le_home_temporaire(self):
        m = charger_outil()
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            m.preparer(root, "page", None, None)
            bin_ = root / "home/.local/bin"
            for nom in m.FAUX:
                f = bin_ / nom
                self.assertTrue(f.is_file() and not f.is_symlink(), nom)
                self.assertTrue(os.access(str(f), os.X_OK), nom)
                self.assertTrue((DEPOT / "home/.local/bin" / nom).exists() is False or
                                f.read_text() != (DEPOT / "home/.local/bin" / nom).read_text(), nom)
            for modele in modeles_cpu():
                for f in root.rglob("*"):
                    if f.is_file() and not f.is_symlink():
                        self.assertNotIn(modele, f.read_text(errors="replace"), str(f))


@unittest.skipUnless(shutil.which("qs"), "Quickshell (qs) absent")
class Rendu(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dossier = Path(tempfile.mkdtemp(prefix="nct-"))
        env = {k: v for k, v in os.environ.items() if k in ("PATH", "LANG", "LC_ALL")}
        cls.r = subprocess.run([sys.executable, str(OUTIL), "--sortie", str(cls.dossier)] + list(ETATS),
                               capture_output=True, text=True, env=env, timeout=240)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(str(cls.dossier), ignore_errors=True)

    def test_quatre_png_corrects(self):
        self.assertEqual(self.r.returncode, 0, self.r.stderr)
        for e in ETATS:
            w, h, lignes = lire_png(self.dossier / (e + ".png"))
            self.assertGreater(w, 0)
            self.assertGreater(h, 0)
            self.assertFalse(est_unie(w, lignes), e + " : image unie")

    def test_fermee_plus_petite_que_page(self):
        f = lire_png(self.dossier / "fermee.png")
        p = lire_png(self.dossier / "page.png")
        self.assertLess(f[0] * f[1], p[0] * p[1])

    def test_echelle_2_double_la_taille(self):
        m = charger_outil()
        with tempfile.TemporaryDirectory() as t:
            png, journal = m.rendre("fermee", t, None, None, None, 2)
            self.assertIsNotNone(png, journal)
            w1, h1, _ = lire_png(self.dossier / "fermee.png")
            w2, h2, _ = lire_png(png)
            self.assertAlmostEqual(w2 / w1, 2, delta=0.2)
            self.assertAlmostEqual(h2 / h1, 2, delta=0.2)

    def marge_opaque(self, reglages):
        """Nombre de pixels non transparents dans la marge de MARGE px autour de l'île (page, échelle 1)."""
        m = charger_outil()
        with tempfile.TemporaryDirectory() as t:
            conf = Path(t) / "r.conf"
            conf.write_text(reglages)
            png, journal = m.rendre("page", t, str(conf), None, None, 1)
            self.assertIsNotNone(png, journal)
            self.assertEqual(Path(png).read_bytes()[25], 6)
            w, h, bpp, lignes = m.lire_png(png)
            self.assertEqual(bpp, 4)
            n = 0
            for y in range(h):
                for x in range(w):
                    if (x < m.MARGE or y < m.MARGE or x >= w - m.MARGE or y >= h - m.MARGE) and lignes[y][x * 4 + 3]:
                        n += 1
            return n

    def test_contour_et_lueur_visibles_dans_la_marge(self):
        self.assertGreater(self.marge_opaque("ILE_LUEUR=oui\nILE_CONTOUR=degrade\n"), 50)

    def test_echelle_2_ile_entiere_cote_gauche_et_droit(self):
        m = charger_outil()
        with tempfile.TemporaryDirectory() as t:
            conf = Path(t) / "r.conf"
            conf.write_text("ILE_LUEUR=oui\nILE_CONTOUR=degrade\n")
            png, journal = m.rendre("page", t, str(conf), None, None, 2)
            self.assertIsNotNone(png, journal)
            w, h, bpp, lignes = m.lire_png(png)
            e = 2 * m.MARGE
            for nom, xs in (("gauche", range(e)), ("droite", range(w - e, w))):
                n = sum(1 for y in range(h) for x in xs if lignes[y][x * 4 + 3])
                self.assertGreater(n, 50, "bord " + nom + " : île rognée ou sans lueur")

    def test_sans_contour_ni_lueur_la_marge_est_transparente(self):
        self.assertEqual(self.marge_opaque("ILE_LUEUR=non\nILE_CONTOUR=aucun\n"), 0)

    def test_ile_carree_et_opaque_reste_en_rgba_avec_coin_transparent(self):
        m = charger_outil()
        with tempfile.TemporaryDirectory() as t:
            conf = Path(t) / "r.conf"
            conf.write_text("ILE_RAYON=carre\nILE_VERRE=100\nILE_CONTOUR=discret\nILE_CONTOUR_EPAISSEUR=1\nILE_LUEUR=non\n")
            for e in ETATS:
                png, journal = m.rendre(e, t, str(conf), None, None, 1)
                self.assertIsNotNone(png, e + " : " + journal)
                self.assertEqual(Path(png).read_bytes()[25], 6, e)
                self.assertEqual(m.lire_png(png)[3][0][3], 0, e + " : coin non transparent")

    def test_rien_de_reel_dans_les_images_ni_le_journal(self):
        m = charger_outil()
        modeles = modeles_cpu()
        with tempfile.TemporaryDirectory() as t:
            png, journal = m.rendre("page", t, None, None, None, 1)
            self.assertIsNotNone(png, journal)
            produits = [Path(png).read_bytes().decode("latin-1"), journal]
            for modele in modeles:
                for texte in produits:
                    self.assertNotIn(modele, texte)
                    self.assertNotIn(modele.encode("utf-8").decode("latin-1"), texte)


if __name__ == "__main__":
    unittest.main()

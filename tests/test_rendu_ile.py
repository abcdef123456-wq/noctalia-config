"""outils/rendu-ile.py : les PNG hors écran de l'île (sauté si Quickshell est absent)."""
import _isolation  # noqa: F401  (HOME, XDG_*, langue : avant tout le reste)
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


def faire_png(w, h, rgb_par_ligne):
    def bloc(t, c):
        return struct.pack(">I", len(c)) + t + c + struct.pack(">I", zlib.crc32(t + c))
    brut = b"".join(b"\x00" + rgb_par_ligne(y) for y in range(h))
    return (b"\x89PNG\r\n\x1a\n" + bloc(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
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


class Refus(unittest.TestCase):
    def test_sortie_dans_le_depot_refusee(self):
        for sortie in (DEPOT / "rendu-essai", DEPOT):
            r = subprocess.run([sys.executable, str(OUTIL), "--sortie", str(sortie), "fermee"],
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 2, r.stderr)
            self.assertFalse((DEPOT / "rendu-essai").exists())


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


if __name__ == "__main__":
    unittest.main()

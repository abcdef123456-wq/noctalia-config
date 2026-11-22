"""nc-capture habiller : nouvelle image à côté (coins arrondis, ombre, dégradé du thème), original intact, bouton
« Habiller » de la notification seulement avec ImageMagick. Tout dans un HOME temporaire, faux notify-send."""
import hashlib
import os
import shutil
import signal
import struct
import subprocess
import time
import zlib
import unittest
from pathlib import Path

from tests import _isolation  # noqa: F401
from tests.test_captures_e4 import BIN, Base

IM = shutil.which("magick") or shutil.which("convert")


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def taille(p):
    with open(p, "rb") as f:
        r = subprocess.run([IM, "-[0]", "-format", "%w %h", "info:"], stdin=f, capture_output=True, text=True)
    return tuple(int(x) for x in r.stdout.split())


def png_uni(chemin, w, h):
    """PNG gris uni de w x h, petit en octets (jamais décodé par nous)."""
    def morceau(t, d):
        c = struct.pack(">I", len(d)) + t + d
        return c + struct.pack(">I", zlib.crc32(t + d))
    z = zlib.compressobj(9)
    ligne = b"\0" * (w + 1)
    data = b"".join(z.compress(ligne) for _ in range(h)) + z.flush()
    Path(chemin).write_bytes(b"\x89PNG\r\n\x1a\n" + morceau(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 0, 0, 0, 0))
                             + morceau(b"IDAT", data) + morceau(b"IEND", b""))


FAUX_MAGICK = r"""echo "$*" >> "$JOURNAL"
case "$*" in
  *info:*) python3 -c 'import struct,sys;d=sys.stdin.buffer.read(24);print(*struct.unpack(">II",d[16:24]))' ;;
  *) for a; do o="${a#png:}"; done; echo x > "$o"; [ -n "${LENT:-}" ] && sleep 20; exit 0 ;;
esac
"""


class Faux(Base):
    """Faux magick qui journalise ses appels : on voit ce qui est lancé, sans vraie composition."""
    def setUp(self):
        super().setUp()
        self.faux_prog("magick", FAUX_MAGICK)

    def hab(self, f, **env):
        return subprocess.run([shutil.which("bash"), str(BIN / "nc-capture"), "habiller", str(f)], capture_output=True,
                              text=True, timeout=30, env=self.env(**env), stdin=subprocess.DEVNULL, cwd=self.home)

    def appels(self):
        return [x for x in self.journal.read_text().splitlines() if x]

    def test_surface_juste_sous_le_plafond_acceptee(self):
        png_uni(self.home / "a.png", 6324, 6324)  # 39 992 976 pixels
        r = self.hab(self.home / "a.png")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(len(self.appels()), 2)

    def test_surface_au_dessus_refusee_sans_composition(self):
        png_uni(self.home / "a.png", 6325, 6325)
        r = self.hab(self.home / "a.png")
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual(len(self.appels()), 1)  # seulement info:
        self.assertIn("info:", self.appels()[0])
        self.assertEqual(sorted(p.name for p in self.home.glob("*habillee*")), [])

    def test_bombe_refusee_vite(self):
        png_uni(self.home / "bomb.png", 16384, 16384)
        t0 = time.time()
        r = self.hab(self.home / "bomb.png")
        self.assertNotEqual(r.returncode, 0)
        self.assertLess(time.time() - t0, 5)
        self.assertEqual(len(self.appels()), 1)

    def test_limit_dans_les_deux_appels(self):
        png_uni(self.home / "a.png", 100, 100)
        self.assertEqual(self.hab(self.home / "a.png").returncode, 0)
        a = self.appels()
        self.assertEqual(len(a), 2)
        for ligne in a:
            for t in ("area", "memory", "map", "time"):
                self.assertIn("-limit " + t, ligne)

    def test_sortie_incomplete_retiree_quand_on_tue(self):
        png_uni(self.home / "a.png", 100, 100)
        p = subprocess.Popen([shutil.which("bash"), str(BIN / "nc-capture"), "habiller", str(self.home / "a.png")],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=self.env(LENT="1"),
                             stdin=subprocess.DEVNULL, cwd=self.home)
        sortie = self.home / "a-habillee.png"
        for _ in range(100):
            if sortie.exists() and sortie.stat().st_size > 0:
                break
            time.sleep(0.1)
        self.assertTrue(sortie.exists())
        os.kill(p.pid, signal.SIGTERM)
        p.communicate(timeout=10)
        self.assertFalse(sortie.exists())

    def test_formats_refuses_sans_magick(self):
        for nom, octets in (("a.svg", b"<svg xmlns='http://www.w3.org/2000/svg'/>"), ("b.png", b"texte simple"),
                            ("c.gif", b"GIF89a\x01\x00"), ("d.mvg", b"push graphic-context\n"), ("e.png", b"")):
            (self.home / nom).write_bytes(octets)
            with self.subTest(nom=nom):
                r = self.hab(self.home / nom)
                self.assertNotEqual(r.returncode, 0)
        self.assertEqual(self.appels(), [])

    def test_jpeg_accepte_avec_codeur_explicite(self):
        (self.home / "j.jpg").write_bytes(b"\xff\xd8\xff\xe0" + b"\0" * 40)
        self.hab(self.home / "j.jpg")
        self.assertIn("jpeg:-[0]", self.appels()[0])

    def test_nom_de_sortie_suffixe_final_seulement(self):
        for nom, attendu in (("a-habillee-b.png", "a-habillee-b-habillee.png"), ("a-habillee.png", "a-habillee-2.png"),
                             ("a-habillee-7.png", "a-habillee.png"), ("x-habillee-2-y.png", "x-habillee-2-y-habillee.png")):
            png_uni(self.home / nom, 100, 100)
            with self.subTest(nom=nom):
                r = self.hab(self.home / nom)
                self.assertEqual(Path(r.stdout.strip()).name, attendu, r.stderr)
                Path(r.stdout.strip()).unlink()
            (self.home / nom).unlink()


@unittest.skipUnless(IM, "ImageMagick absent")
class Habiller(Base):
    def setUp(self):
        super().setUp()
        for nom in ("magick", "convert"):
            c = shutil.which(nom)
            if c:
                (self.faux / nom).symlink_to(c)
        self.img = self.home / "cap.png"
        subprocess.run([IM, "-size", "300x200", "xc:white", str(self.img)], check=True)

    def hab(self, *args, path=None):
        return subprocess.run([shutil.which("bash"), str(BIN / "nc-capture"), "habiller", *args], capture_output=True,
                              text=True, timeout=30, env=self.env(), stdin=subprocess.DEVNULL, cwd=path or self.home)

    def test_sortie_a_cote_original_intact_et_borne(self):
        avant = sha(self.img)
        r = self.hab(str(self.img))
        self.assertEqual(r.returncode, 0, r.stderr)
        out = Path(r.stdout.strip())
        self.assertEqual(out, self.home / "cap-habillee.png")
        self.assertEqual(sha(self.img), avant)
        w, h = taille(out)
        self.assertTrue(w > 300 and h > 200 and w <= 600 and h <= 400, (w, h))

    def test_noms_suivants_sans_ecrasement(self):
        o1 = Path(self.hab(str(self.img)).stdout.strip())
        s1 = sha(o1)
        o2 = Path(self.hab(str(self.img)).stdout.strip())
        o3 = Path(self.hab(str(o1)).stdout.strip())
        self.assertEqual((o2.name, o3.name), ("cap-habillee-2.png", "cap-habillee-3.png"))
        self.assertEqual(sha(o1), s1)

    def test_palette_presente_ou_absente(self):
        r0 = self.hab(str(self.img))
        self.assertEqual(r0.returncode, 0)
        p = self.home / ".config/nc/palette-ile.json"
        p.write_text('{"accent": "#e07a5f", "fond": "#291416"}')
        r = self.hab(str(self.img))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotEqual(sha(r0.stdout.strip()), sha(r.stdout.strip()))

    def test_refus(self):
        (self.home / "dossier").mkdir()
        (self.home / "lien.png").symlink_to(self.img)
        (self.home / "-x.png").write_bytes(b"pas une image")
        for a in ("absent.png", "dossier", "lien.png", "-x.png", ""):
            with self.subTest(a=a):
                r = self.hab(str(self.home / a) if a and a != "-x.png" else a)
                self.assertNotEqual(r.returncode, 0)
                self.assertEqual(r.stdout.strip(), "")
        self.assertEqual(sorted(p.name for p in self.home.glob("*habillee*")), [])

    def test_nom_en_tiret_valide(self):
        (self.home / "-opt.png").write_bytes(self.img.read_bytes())
        r = self.hab("-opt.png")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue((self.home / r.stdout.strip()).exists())


class Bouton(Base):
    def capturer(self, avec_magick):
        self.faux_prog("grim", 'for a; do f="$a"; done; echo "png" > "$f"')
        self.faux_prog("xdg-user-dir", 'echo "$HOME/Pictures"')
        self.faux_prog("hyprctl", "echo '[]'")
        self.faux_prog("jq", "exit 0")
        self.faux_prog("wl-copy", "exit 0")
        self.faux_prog("notify-send", 'echo "notif $*" >> "$JOURNAL"')
        for nom in ("magick", "convert"):
            f = self.faux / nom
            if f.exists() or f.is_symlink():
                f.unlink()
        if avec_magick:
            self.faux_prog("magick", "exit 0")
        (self.home / ".config/nc/reglages.conf").write_text("LANGUE=fr\nCAPTURES_COPIER=non\n")
        self.journal.write_text("")
        r = subprocess.run([shutil.which("bash"), str(BIN / "nc-capture"), "ecran"], capture_output=True, text=True,
                           timeout=20, env=self.env(), stdin=subprocess.DEVNULL)
        self.assertEqual(r.returncode, 0, r.stderr)
        time.sleep(0.5)  # la notification part en arrière-plan
        return self.journal.read_text()

    def test_bouton_selon_magick(self):
        self.assertIn("habiller=Habiller", self.capturer(True))
        self.assertNotIn("habiller", self.capturer(False))


if __name__ == "__main__":
    unittest.main()

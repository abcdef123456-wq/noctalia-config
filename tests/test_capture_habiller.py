"""nc-capture habiller : nouvelle image à côté (coins arrondis, ombre, dégradé du thème), original intact, bouton
« Habiller » de la notification seulement avec ImageMagick. Tout dans un HOME temporaire, faux notify-send."""
import hashlib
import shutil
import subprocess
import time
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

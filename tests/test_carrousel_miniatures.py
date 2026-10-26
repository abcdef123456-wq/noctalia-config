"""Miniatures du carrousel (nc-carousel-thumbs) : surveillance du vrai dossier des fonds (drop-in du .path), image
illisible non retraitée, restes .tmp.webp nettoyés, hyprctl en échec = rien de régénéré.
Tout se passe dans un dossier temporaire : HOME et XDG_* y pointent, faux magick, hyprctl et systemctl devant dans le PATH."""
import os
import shutil
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "home/.local/bin/nc-carousel-thumbs"
UNITE = REPO / "home/.config/systemd/user/nc-carousel-thumbs.path"

MONITEURS = '[{"width":1920,"height":1080,"scale":1.0}]'


class Miniatures(unittest.TestCase):
    def setUp(self):
        d = tempfile.TemporaryDirectory(prefix="nc-carrousel-")
        self.addCleanup(d.cleanup)
        self.r = Path(d.name)
        self.home = self.r / "home/user"
        self.bin = self.r / "bin"
        self.bin.mkdir()
        self.home.mkdir(parents=True)
        self.journal = self.r / "journal"
        self.journal.touch()
        self.fonds = self.home / "Pictures/Wallpapers"
        self.fonds.mkdir(parents=True)
        self.sortie = self.home / ".cache/nc/carousel"
        # faux magick : écrit la sortie (dernier argument) ; « casse » dans le nom de l'entrée = échec, avec un reste .tmp
        self.faux("magick", 'echo "magick $1" >> "$NC_JOURNAL"\n'
                  'for a; do last="$a"; done\n'
                  'case "$1" in *casse*) echo x > "$last"; exit 1 ;; esac\n'
                  'echo x > "$last"\n')
        self.faux("hyprctl", '[ -e "$NC_SANS_HYPR" ] && exit 1\necho \'' + MONITEURS + "'\n")
        self.faux("systemctl", 'echo "systemctl $*" >> "$NC_JOURNAL"\n'
                  '[ "$2" = is-active ] && exit 0\nexit 0\n')
        self.env = dict(os.environ, HOME=str(self.home), XDG_CONFIG_HOME=str(self.home / ".config"),
                        XDG_STATE_HOME=str(self.home / ".local/state"), XDG_CACHE_HOME=str(self.home / ".cache"),
                        TMPDIR=str(self.r), PATH=f"{self.bin}:{os.environ['PATH']}",
                        NC_JOURNAL=str(self.journal), NC_SANS_HYPR=str(self.r / "sans-hypr"))
        self.env.pop("NOCTALIA_CONFIG_HOME", None)
        self.env.pop("HYPRLAND_INSTANCE_SIGNATURE", None)

    def faux(self, nom, corps):
        f = self.bin / nom
        f.write_text("#!/bin/sh\n" + corps)
        f.chmod(f.stat().st_mode | stat.S_IEXEC)

    def lance(self, *args):
        return subprocess.run([str(SCRIPT), *args], env=self.env, capture_output=True, text=True, timeout=60, check=False)

    def config(self, dossier, nom="zy-reglages.toml"):
        c = self.home / ".config/noctalia"
        c.mkdir(parents=True, exist_ok=True)
        (c / nom).write_text(f'[wallpaper]\ndirectory = "{dossier}"\n')

    @property
    def dropin(self):
        return self.home / ".config/systemd/user/nc-carousel-thumbs.path.d/dossier.conf"

    # surveillance du vrai dossier

    def test_unite_sans_chemin_de_noctalia_v4(self):
        texte = UNITE.read_text()
        self.assertNotIn("wallpaperCarousel", texte)
        self.assertIn("PathChanged=%h/Pictures/Wallpapers", texte)

    def test_dropin_avec_espace_et_pour_cent(self):
        dossier = self.home / "Mes fonds 100% beaux"
        dossier.mkdir()
        self.config(dossier)
        r = self.lance("--surveillance")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.dropin.read_text(),
                         f"[Path]\nPathChanged=\nPathChanged={self.home}/Mes fonds 100%% beaux\n")
        j = self.journal.read_text()
        self.assertIn("systemctl --user daemon-reload", j)
        self.assertIn("systemctl --user restart nc-carousel-thumbs.path", j)

    def test_dropin_inchange_ne_recharge_pas(self):
        dossier = self.home / "Images"
        dossier.mkdir()
        self.config(dossier)
        self.lance("--surveillance")
        self.journal.write_text("")
        self.lance("--surveillance")
        self.assertEqual(self.journal.read_text(), "")

    def test_dropin_retire_pour_le_defaut(self):
        dossier = self.home / "Images"
        dossier.mkdir()
        self.config(dossier)
        self.lance("--surveillance")
        self.assertTrue(self.dropin.exists())
        self.config(self.home / "Pictures/Wallpapers")
        self.lance("--surveillance")
        self.assertFalse(self.dropin.exists())

    def test_defaut_sans_config_pas_de_dropin(self):
        self.lance("--surveillance")
        self.assertFalse(self.dropin.exists())
        self.assertEqual(self.journal.read_text(), "")

    def test_zy_reglages_l_emporte_sur_config(self):
        a = self.home / "A"
        b = self.home / "B"
        a.mkdir()
        b.mkdir()
        self.config(a, "config.toml")
        self.config(b, "zy-reglages.toml")
        self.lance("--surveillance")
        self.assertIn(f"PathChanged={b}\n", self.dropin.read_text())

    # miniatures

    def image(self, nom, mtime=None):
        f = self.fonds / nom
        f.write_text("img")
        if mtime:
            os.utime(f, (mtime, mtime))
        return f

    def test_echec_marque_et_pas_retraite(self):
        self.image("casse.png", 1000)
        self.image("bon.png", 1000)
        self.assertEqual(self.lance().returncode, 0)
        self.assertEqual((self.sortie / "casse.png.echec").read_text().strip(), "1000")
        self.assertFalse((self.sortie / "casse.png.W.webp").exists())
        self.assertTrue((self.sortie / "bon.png.W.webp").exists())
        self.assertFalse(list(self.sortie.glob("*.tmp.webp")))       # reste de l'échec nettoyé
        self.journal.write_text("")
        self.lance()
        self.assertNotIn("casse.png", self.journal.read_text())      # pas de nouvel essai
        self.image("casse.png", 2000)                                # l'image a changé : nouvel essai
        self.lance()
        self.assertIn("casse.png", self.journal.read_text())
        self.assertEqual((self.sortie / "casse.png.echec").read_text().strip(), "2000")

    def test_echec_efface_si_l_image_disparait(self):
        f = self.image("casse.png", 1000)
        self.lance()
        f.unlink()
        self.lance()
        self.assertFalse((self.sortie / "casse.png.echec").exists())

    def test_restes_tmp_nettoyes_au_debut(self):
        self.sortie.mkdir(parents=True)
        (self.sortie / "vieux.png.W.tmp.webp").write_text("x")
        self.lance()
        self.assertFalse(list(self.sortie.glob("*.tmp.webp")))

    def test_hyprctl_en_echec_ne_regenere_rien(self):
        self.image("bon.png")
        self.lance()
        self.assertEqual((self.sortie / ".dpr").read_text().strip(), "1.080")
        signature = (self.sortie / ".size").read_text()
        avant = (self.sortie / "bon.png.W.webp").stat().st_mtime_ns
        (self.r / "sans-hypr").touch()
        self.journal.write_text("")
        self.assertEqual(self.lance().returncode, 0)
        self.assertEqual((self.sortie / ".size").read_text(), signature)
        self.assertEqual((self.sortie / "bon.png.W.webp").stat().st_mtime_ns, avant)
        self.assertEqual(self.journal.read_text(), "")

    def test_hyprctl_en_echec_sans_dpr_connu_prend_1_sans_le_garder(self):
        # Première installation hors session : des miniatures quand même (facteur 1), et le vrai facteur plus tard
        self.image("bon.png")
        (self.r / "sans-hypr").touch()
        self.assertEqual(self.lance().returncode, 0)
        self.assertTrue((self.sortie / "bon.png.W.webp").exists())
        self.assertFalse((self.sortie / ".dpr").exists())

    def test_hyprctl_en_echec_garde_le_dpr_pour_les_nouvelles_images(self):
        self.image("a.png", 1000)
        self.lance()
        (self.r / "sans-hypr").touch()
        self.image("b.png", 1000)
        self.lance()
        self.assertTrue((self.sortie / "b.png.W.webp").exists())
        self.assertTrue((self.sortie / "a.png.W.webp").exists())


@unittest.skipUnless(shutil.which("systemd-analyze"), "systemd-analyze absent")
class Verification(unittest.TestCase):
    def test_unite_et_dropin_valides(self):
        with tempfile.TemporaryDirectory(prefix="nc-carrousel-unite-") as d:
            d = Path(d)
            shutil.copy(UNITE, d / "nc-carousel-thumbs.path")
            shutil.copy(REPO / "home/.config/systemd/user/nc-carousel-thumbs.service", d / "nc-carousel-thumbs.service")
            (d / "nc-carousel-thumbs.path.d").mkdir()
            (d / "nc-carousel-thumbs.path.d/dossier.conf").write_text("[Path]\nPathChanged=\nPathChanged=/tmp/a b/100%%\n")
            r = subprocess.run(["systemd-analyze", "--user", "verify", str(d / "nc-carousel-thumbs.path")],
                               capture_output=True, text=True, check=False,
                               env=dict(os.environ, HOME=str(d), XDG_CONFIG_HOME=str(d)))
            for mot in ("Unknown", "Invalid", "not valid", "Failed", "Bad"):
                self.assertNotIn(mot, r.stderr, r.stderr)


if __name__ == "__main__":
    unittest.main()

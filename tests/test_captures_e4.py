"""Audit E4 : nc-capture (deux captures dans la même seconde, config Swappy gardée) et nc-wallpaper-colors (image
illisible, copie de démarrage écrite d'un coup, -h). Faux grim, slurp, magick… dans un HOME temporaire : jamais la vraie
session. Le PATH ne contient que les faux et les outils de base."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
BIN = REPO / "home/.local/bin"
OUTILS = ("bash", "sh", "sed", "tail", "tr", "mkdir", "date", "cat", "grep", "head", "rm", "env", "cmp", "awk", "mktemp",
          "chmod", "mv", "cut", "sleep", "python3", "paste", "dirname", "basename")


class Base(unittest.TestCase):
    def setUp(self):
        d = tempfile.TemporaryDirectory(prefix="nc-e4-")
        self.addCleanup(d.cleanup)
        self.home = Path(d.name)
        self.faux = self.home / "faux"
        self.faux.mkdir()
        for nom in OUTILS:
            chemin = shutil.which(nom)
            if chemin:
                (self.faux / nom).symlink_to(chemin)
        (self.home / ".config/nc").mkdir(parents=True)
        (self.home / ".config/nc/reglages.conf").write_text('LANGUE=fr\nCAPTURES_NOTIF=non\nCAPTURES_COPIER=non\n')
        self.journal = self.home / "journal"
        self.journal.write_text("")

    def faux_prog(self, nom, corps):
        f = self.faux / nom
        f.unlink() if f.is_symlink() else None
        f.write_text("#!/bin/sh\n" + corps + "\n")
        f.chmod(0o755)

    def env(self, **plus):
        env = dict(HOME=str(self.home), PATH=str(self.faux), NC_LANGUE="fr", JOURNAL=str(self.journal),
                   XDG_RUNTIME_DIR=str(self.home / "run"), XDG_CONFIG_HOME=str(self.home / ".config"))
        env.update(plus)
        return env


class Capture(Base):
    def setUp(self):
        super().setUp()
        self.faux_prog("grim", 'for a; do f="$a"; done; echo "png" > "$f"; echo "grim $*" >> "$JOURNAL"')
        self.faux_prog("xdg-user-dir", 'echo "$HOME/Pictures"')
        self.faux_prog("hyprctl", "echo '[]'")
        self.faux_prog("jq", "exit 0")
        self.faux_prog("wl-copy", "exit 0")
        self.faux_prog("notify-send", "exit 0")
        # Même seconde pour toutes les captures du test
        self.faux_prog("date", 'case "$*" in +%s) echo 1792947000 ;; *) echo "2026-10-25 à 18.00.00" ;; esac')
        self.dossier = self.home / "Pictures/Captures"
        self.conf = self.home / ".config/swappy/config"

    def capturer(self, mode="ecran"):
        r = subprocess.run([shutil.which("bash"), str(BIN / "nc-capture"), mode], env=self.env(), capture_output=True,
                           text=True, timeout=20, stdin=subprocess.DEVNULL)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_deux_captures_meme_seconde_ne_s_ecrasent_pas(self):
        for _ in range(3):
            self.capturer()
        noms = sorted(p.name for p in self.dossier.iterdir())
        self.assertEqual(len(noms), 3, noms)
        self.assertEqual(noms[0], "Capture du 2026-10-25 à 18.00.00-2.png")
        self.assertIn("Capture du 2026-10-25 à 18.00.00.png", noms)
        self.assertIn("Capture du 2026-10-25 à 18.00.00-3.png", noms)
        for p in self.dossier.iterdir():
            self.assertEqual(p.read_text(), "png\n")

    def test_capture_ratee_ne_laisse_pas_de_fichier_vide(self):
        self.faux_prog("grim", "exit 1")
        r = subprocess.run([shutil.which("bash"), str(BIN / "nc-capture"), "ecran"], env=self.env(),
                           capture_output=True, text=True, timeout=20)
        self.assertEqual(r.returncode, 1)
        self.assertEqual(list(self.dossier.iterdir()), [])

    def test_swappy_sans_config_pose_les_reglages_de_depart(self):
        self.capturer()
        self.assertEqual(self.conf.read_text(), "[Default]\nsave_dir=%s\nsave_filename_format=Capture annotée du "
                         "%%Y-%%m-%%d à %%H.%%M.%%S.png\nshow_panel=true\nearly_exit=true\n" % self.dossier)

    def test_swappy_garde_le_reste_de_la_config(self):
        self.conf.parent.mkdir(parents=True)
        self.conf.write_text("# ma config\n[Default]\nline_size=7\nsave_dir=/ailleurs\nshow_panel=false\n"
                             "text_font=Fira Sans\n\n[Autre]\nsave_dir=garde\n")
        self.capturer()
        texte = self.conf.read_text().splitlines()
        self.assertIn("# ma config", texte)
        self.assertIn("line_size=7", texte)
        self.assertIn("show_panel=false", texte)                 # pas remplacé par true
        self.assertIn("text_font=Fira Sans", texte)
        self.assertIn("save_dir=" + str(self.dossier), texte)
        self.assertNotIn("save_dir=/ailleurs", texte)
        self.assertIn("save_filename_format=Capture annotée du %Y-%m-%d à %H.%M.%S.png", texte)
        self.assertIn("save_dir=garde", texte)                   # une autre section n'est pas touchée
        self.assertEqual(texte.count("[Default]"), 1)
        avant = self.conf.read_text()
        self.capturer()                                          # 2e passage : plus rien à changer
        self.assertEqual(self.conf.read_text(), avant)

    def test_swappy_sans_section_default_l_ajoute(self):
        self.conf.parent.mkdir(parents=True)
        self.conf.write_text("[Autre]\nx=1\n")
        self.capturer()
        texte = self.conf.read_text()
        self.assertTrue(texte.startswith("[Autre]\nx=1\n"), texte)
        self.assertIn("[Default]\nsave_dir=%s\n" % self.dossier, texte)


class FondEcran(Base):
    def setUp(self):
        super().setUp()
        # Faux magick : « BAD » dans l'image = illisible ; la lecture 64x64 rend du gris ; sinon il écrit le fichier de sortie
        self.faux_prog("magick", '''src="$1"
if grep -q BAD "${src%\\[0\\]}"; then echo "magick: image corrompue" >&2; exit 1; fi
for a; do last="$a"; done
case "$*" in
  *rgb:-*) head -c 12288 /dev/zero | tr '\\0' '\\200' ;;
  *) echo "magick $last" >> "$JOURNAL"; sleep 0.3; echo JPEG > "${last#jpg:}" ;;
esac''')
        self.faux_prog("hyprctl", "echo '[]'")
        self.faux_prog("noctalia", "exit 0")
        self.cache = self.home / ".cache/nc"
        self.boot = self.cache / "wallpaper-boot.jpg"
        self.bon = self.home / "bon.png"
        self.bon.write_text("ok")
        self.mauvais = self.home / "mauvais.png"
        self.mauvais.write_text("BAD")

    def lancer(self, *args):
        return subprocess.run([sys.executable, str(BIN / "nc-wallpaper-colors"), *args], env=self.env(PATH=str(self.faux)),
                              capture_output=True, text=True, timeout=30, stdin=subprocess.DEVNULL)

    def test_image_illisible_message_clair_sans_trace(self):
        for args in ((str(self.mauvais),), (str(self.mauvais), "--dry-run")):
            r = self.lancer(*args)
            self.assertEqual(r.returncode, 1)
            self.assertNotIn("Traceback", r.stderr)
            self.assertIn("image illisible", r.stderr)

    def test_image_illisible_garde_la_copie_de_demarrage_existante(self):
        self.cache.mkdir(parents=True)
        self.boot.write_text("ANCIENNE")
        self.lancer(str(self.mauvais))
        self.assertEqual(self.boot.read_text(), "ANCIENNE")
        self.assertEqual(sorted(p.name for p in self.cache.iterdir()), ["wallpaper-boot.jpg"], "pas de temporaire resté")

    def test_copie_de_demarrage_ecrite_dans_un_temporaire_puis_posee(self):
        r = self.lancer(str(self.bon))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.boot.read_text(), "JPEG\n")
        self.assertEqual(sorted(p.name for p in self.cache.iterdir()), ["wallpaper-boot.jpg"])
        cible = [l for l in self.journal.read_text().splitlines() if l.startswith("magick ")][0].split(" ", 1)[1].replace("jpg:", "", 1)
        self.assertNotEqual(Path(cible).name, "wallpaper-boot.jpg", "magick doit écrire ailleurs que la cible")
        self.assertEqual(Path(cible).parent, self.cache, "même dossier : os.replace atomique")

    def test_aide_sur_stdout_code_zero(self):
        for opt in ("-h", "--help"):
            r = self.lancer(opt)
            self.assertEqual(r.returncode, 0)
            self.assertIn("nc-wallpaper-colors", r.stdout)
            self.assertEqual(r.stderr, "")

    def test_sans_argument_reste_une_erreur(self):
        r = self.lancer()
        self.assertEqual(r.returncode, 1)
        self.assertIn("Usage", r.stderr)


if __name__ == "__main__":
    unittest.main()

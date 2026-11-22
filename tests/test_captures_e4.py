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
          "chmod", "mv", "cut", "sleep", "python3", "paste", "dirname", "basename", "timeout", "od")


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


class EnvoyerAuCloud(Base):
    """I2 : l'action « Envoyer au cloud » de la notification, seulement avec CLOUD_JARVIS=oui et ce PC associé (fichier
    local) ; elle passe par nc-cloud deposer --racine Captures, et la capture locale n'est jamais touchée."""
    def setUp(self):
        super().setUp()
        self.faux_prog("grim", 'for a; do f="$a"; done; echo "png" > "$f"')
        self.faux_prog("xdg-user-dir", 'echo "$HOME/Pictures"')
        self.faux_prog("hyprctl", "echo '[]'")
        self.faux_prog("jq", "exit 0")
        self.faux_prog("wl-copy", "exit 0")
        # La notification avec actions répond CHOIX ; chaque appel est noté
        self.faux_prog("notify-send", 'echo "notif $*" >> "$JOURNAL"; case "$*" in *-A*) echo "$CHOIX" ;; esac')
        b = self.home / ".local/bin"
        b.mkdir(parents=True)
        (b / "nc-cloud").write_text('#!/bin/sh\necho "nc-cloud $*" >> "$JOURNAL"\necho "$MESSAGE_CLOUD"\nexit "$CODE_CLOUD"\n')
        (b / "nc-cloud").chmod(0o755)
        self.appareil = self.home / ".local/state/nc-cloud/appareil.json"

    def capturer(self, reglages, associe=True, choix="cloud", code=0, message="Envoyé : capture.png → capture.png."):
        (self.home / ".config/nc/reglages.conf").write_text("LANGUE=fr\nCAPTURES_COPIER=non\n" + reglages)
        if associe:
            self.appareil.parent.mkdir(parents=True, exist_ok=True)
            self.appareil.write_text("{}")
        elif self.appareil.exists():
            self.appareil.unlink()
        self.journal.write_text("")
        r = subprocess.run([shutil.which("bash"), str(BIN / "nc-capture"), "ecran"], capture_output=True, text=True, timeout=20,
                           env=self.env(CHOIX=choix, CODE_CLOUD=str(code), MESSAGE_CLOUD=message), stdin=subprocess.DEVNULL)
        self.assertEqual(r.returncode, 0, r.stderr)
        # L'action tourne en arrière-plan : on attend la notification du résultat (ou la fin)
        import time
        fin = time.monotonic() + 10
        while time.monotonic() < fin:
            l = self.journal.read_text().splitlines()
            if choix != "cloud" or len([x for x in l if x.startswith("notif")]) >= 2 or not any("cloud=" in x for x in l):
                break
            time.sleep(0.05)
        time.sleep(0.2)
        return self.journal.read_text().splitlines()

    def test_action_seulement_avec_le_cloud_actif_et_associe(self):
        for reglages, associe in (("", True), ("CLOUD_JARVIS=non\n", True), ("CLOUD_JARVIS=oui\n", False)):
            with self.subTest(reglages=reglages, associe=associe):
                j = self.capturer(reglages, associe, choix="")
                self.assertTrue(j and j[0].startswith("notif"), j)
                self.assertNotIn("cloud=", j[0])
                self.assertFalse([x for x in j if x.startswith("nc-cloud")])
        j = self.capturer("CLOUD_JARVIS=oui\n", True, choix="")
        self.assertIn("cloud=Envoyer au cloud", j[0])
        self.assertFalse([x for x in j if x.startswith("nc-cloud")])          # rien ne part sans le clic

    def test_envoi_resultats_et_capture_locale_intacte(self):
        for code, mot, message in ((0, "Capture envoyée au cloud", ""), (3, "Cloud injoignable", ""), (6, "même nom", ""),
                                   (7, "Quota plein", "Quota plein\033[31m"), (1, "-- Capture non envoyée --version", "--version")):
            with self.subTest(code=code):
                j = self.capturer("CLOUD_JARVIS=oui\n", choix="cloud", code=code, message=message)
                envoi = [x for x in j if x.startswith("nc-cloud")]
                self.assertEqual(len(envoi), 1, j)
                self.assertRegex(envoi[0], r"^nc-cloud deposer --racine Captures -- /.+/Pictures/Captures/.+\.png$")
                fin = [x for x in j if x.startswith("notif")][-1]
                self.assertIn(mot, fin)
                self.assertNotIn("\033", fin)
                captures = list((self.home / "Pictures/Captures").glob("*.png"))
                self.assertTrue(captures and all(c.read_text() == "png\n" for c in captures))


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


class CaptureRetardee(Capture):
    """--dans N : refus poli hors 1..30, compte à rebours en notification, verrou unique, annulation."""

    def setUp(self):
        super().setUp()
        (self.home / "run").mkdir()
        self.faux_prog("notify-send", 'echo "notif $*" >> "$JOURNAL"; echo 42')
        self.verrou = self.home / "run/nc-capture-retard.pid"

    def lancer(self, *args, **env):
        return subprocess.Popen([shutil.which("bash"), str(BIN / "nc-capture"), *args], env=self.env(**env),
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, stdin=subprocess.DEVNULL)

    def test_delai_hors_bornes_refuse_sans_capture(self):
        for d in ("0", "31", "-1", "abc", "5s", ""):
            r = subprocess.run([shutil.which("bash"), str(BIN / "nc-capture"), "ecran", "--dans", d], env=self.env(),
                               capture_output=True, text=True, timeout=20, stdin=subprocess.DEVNULL)
            self.assertEqual(r.returncode, 2, d)
            self.assertIn("1 et 30", r.stderr)
        self.assertNotIn("grim", self.journal.read_text())

    def test_compte_a_rebours_puis_capture(self):
        self.faux_prog("sleep", 'echo "sleep $*" >> "$JOURNAL"')
        r = self.lancer("ecran", "--dans", "3")
        r.communicate(timeout=20)
        self.assertEqual(r.returncode, 0)
        j = self.journal.read_text()
        self.assertEqual(j.count("sleep 1"), 3)
        self.assertIn("Capture dans 3 s", j)
        self.assertIn("-r 42", j)                       # la même notification est remplacée
        self.assertLess(j.index("Capture dans 1 s"), j.index("grim"))
        self.assertFalse(self.verrou.exists())
        self.assertEqual(len(list(self.dossier.iterdir())), 1)

    def test_bannieres_en_pause_avant_grim(self):
        self.faux_prog("sleep", "exit 0")
        self.faux_prog("qs", 'echo "qs $*" >> "$JOURNAL"')
        r = self.lancer("ecran", "--dans", "2")
        r.communicate(timeout=20)
        self.assertEqual(r.returncode, 0)
        j = self.journal.read_text()
        self.assertIn("qs -c nc-ile ipc call ile bannieresPause true", j)
        self.assertLess(j.rindex("Capture dans 1 s"), j.index("qs -c"))
        self.assertLess(j.index("qs -c"), j.index("grim"))

    def test_sans_qs_la_capture_se_fait(self):
        self.faux_prog("sleep", "exit 0")
        r = self.lancer("ecran", "--dans", "1")
        r.communicate(timeout=20)
        self.assertEqual(r.returncode, 0)
        self.assertIn("grim", self.journal.read_text())

    def attendre_verrou(self, p):
        import time
        for _ in range(100):
            if self.verrou.exists() or p.poll() is not None:
                return
            time.sleep(0.1)

    def test_annuler_et_verrou_unique(self):
        self.faux_prog("sleep", 'exec /bin/sleep 1')
        p = self.lancer("ecran", "--dans", "20")
        self.addCleanup(lambda: p.poll() is None and p.kill())
        self.attendre_verrou(p)
        self.assertTrue(self.verrou.exists())
        # Deuxième capture retardée : refusée, la première continue
        r2 = self.lancer("zone", "--dans", "5")
        r2.communicate(timeout=20)
        self.assertEqual(r2.returncode, 1)
        self.assertIsNone(p.poll())
        # Annulation : la capture en attente s'arrête, sans image, verrou libéré
        r3 = self.lancer("annuler")
        r3.communicate(timeout=20)
        p.communicate(timeout=20)
        self.assertEqual(p.returncode, 0)
        self.assertFalse(self.verrou.exists())
        self.assertNotIn("grim", self.journal.read_text())
        self.assertIn("Capture annulée", self.journal.read_text())

    def test_verrou_perime_ignore(self):
        self.faux_prog("sleep", "exit 0")
        self.verrou.write_text("999999\n")
        r = self.lancer("ecran", "--dans", "1")
        r.communicate(timeout=20)
        self.assertEqual(r.returncode, 0)
        self.assertEqual(len(list(self.dossier.iterdir())), 1)


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

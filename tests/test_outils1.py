"""Lot « Outils-1 » : petits défauts des outils du bureau (nc-capture, nc-greeting, nc-keys, nc-shell-msg, nc-touches,
nc-verrou-place, nc-aide-config, nc-wallpaper-colors, nc-icones). HOME, XDG_* et PATH temporaires, faux outils qui
notent seulement leurs arguments : jamais la vraie session."""
import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import unittest

REPO = Path(__file__).resolve().parents[1]
BIN = REPO / "home/.local/bin"
OUTILS = ("bash", "sh", "sed", "tail", "tr", "mkdir", "date", "cat", "grep", "head", "rm", "env", "cmp", "awk", "mktemp",
          "chmod", "mv", "cut", "sleep", "python3", "paste", "dirname", "basename", "timeout", "id", "jq", "wc", "touch", "ls")


class Base(unittest.TestCase):
    def setUp(self):
        d = tempfile.TemporaryDirectory(prefix="nc-outils1-")
        self.addCleanup(d.cleanup)
        self.home = Path(d.name)
        self.faux = self.home / "faux"
        self.faux.mkdir()
        for nom in OUTILS:
            chemin = shutil.which(nom)
            if chemin:
                (self.faux / nom).symlink_to(chemin)
        (self.home / ".config/nc").mkdir(parents=True)
        self.regler("LANGUE=fr\n")
        self.journal = self.home / "journal"
        self.journal.write_text("")

    def regler(self, texte):
        (self.home / ".config/nc/reglages.conf").write_text(texte)

    def faux_prog(self, nom, corps):
        f = self.faux / nom
        if f.is_symlink() or f.exists():
            f.unlink()
        f.write_text("#!/bin/sh\n" + corps + "\n")
        f.chmod(0o755)

    def env(self, **plus):
        env = dict(HOME=str(self.home), PATH=str(self.faux), NC_LANGUE="fr", JOURNAL=str(self.journal),
                   XDG_RUNTIME_DIR=str(self.home / "run"), XDG_CONFIG_HOME=str(self.home / ".config"),
                   XDG_CACHE_HOME=str(self.home / ".cache"), XDG_STATE_HOME=str(self.home / ".local/state"),
                   XDG_DATA_HOME=str(self.home / ".local/share"), TMPDIR=str(self.home))
        (self.home / "run").mkdir(exist_ok=True)
        env.update(plus)
        return env

    def attendre(self, cond, delai=8):
        fin = time.time() + delai
        while time.time() < fin:
            if cond():
                return True
            time.sleep(0.1)
        return cond()

    def journal_texte(self):
        return self.journal.read_text()


# ───────────────────────────── 1, 2, 3 : nc-capture ─────────────────────────────
class Capture(Base):
    def setUp(self):
        super().setUp()
        self.faux_prog("grim", 'for a; do f="$a"; done; if [ "$f" = - ]; then echo png; else echo "png" > "$f"; fi')
        self.faux_prog("slurp", 'echo "0,0 10x10"')
        self.faux_prog("swappy", 'echo "swappy $*" >> "$JOURNAL"')
        self.faux_prog("wl-copy", 'cat > /dev/null; echo "wl-copy $*" >> "$JOURNAL"')
        self.faux_prog("xdg-user-dir", 'echo "$HOME/Pictures"')
        self.faux_prog("hyprctl", "echo '[]'")
        self.faux_prog("notify-send", 'echo "notify $*" >> "$JOURNAL"')
        self.dossier = self.home / "Pictures/Captures"

    def lancer(self, mode):
        return subprocess.run(["bash", str(BIN / "nc-capture"), mode], env=self.env(), capture_output=True, text=True,
                              timeout=30, stdin=subprocess.DEVNULL)

    def test_slurp_absent_dit_le_paquet(self):
        (self.faux / "slurp").unlink()
        r = self.lancer("zone")
        self.assertNotEqual(r.returncode, 0)
        j = self.journal_texte()
        self.assertIn("slurp n'est pas installé", j)
        self.assertIn("« slurp »", j)
        self.assertFalse(self.dossier.exists() and list(self.dossier.iterdir()), "aucun fichier vide laissé")

    def test_swappy_absent_retouche_dit_le_paquet(self):
        (self.faux / "swappy").unlink()
        r = self.lancer("retouche")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("swappy n'est pas installé", self.journal_texte())

    def test_grim_absent_dit_le_paquet(self):
        (self.faux / "grim").unlink()
        r = self.lancer("ecran")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("grim n'est pas installé", self.journal_texte())

    def test_wl_copy_absent_ne_dit_pas_copiee_aussi(self):
        (self.faux / "wl-copy").unlink()
        r = self.lancer("ecran")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(self.attendre(lambda: "Capture enregistrée" in self.journal_texte()))
        j = self.journal_texte()
        self.assertIn("wl-copy n'est pas installé", j)
        self.assertIn("wl-clipboard", j)
        self.assertNotIn("Copiée aussi", j)

    def test_wl_copy_en_echec_ne_dit_pas_copiee_aussi(self):
        self.faux_prog("wl-copy", "cat > /dev/null; exit 1")
        r = self.lancer("ecran")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(self.attendre(lambda: "Capture enregistrée" in self.journal_texte()))
        self.assertNotIn("Copiée aussi", self.journal_texte())

    def test_wl_copy_qui_marche_dit_copiee_aussi(self):
        r = self.lancer("ecran")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(self.attendre(lambda: "Capture enregistrée" in self.journal_texte()))
        self.assertIn("Copiée aussi", self.journal_texte())

    def test_captures_privees(self):
        r = self.lancer("ecran")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(stat.S_IMODE(self.dossier.stat().st_mode), 0o700)
        fichiers = list(self.dossier.iterdir())
        self.assertEqual(len(fichiers), 1)
        self.assertEqual(stat.S_IMODE(fichiers[0].stat().st_mode), 0o600)

    def texte(self, apercu=None):
        self.faux_prog("tesseract", 'if [ "$1" = --list-langs ]; then echo fra; echo eng; else echo "motdepasse42"; fi')
        if apercu is not None:
            self.regler(f"LANGUE=fr\nCAPTURES_APERCU={apercu}\n")
        r = self.lancer("texte")
        self.assertEqual(r.returncode, 0, r.stderr)
        return self.journal_texte()

    def test_texte_sans_apercu_par_defaut(self):
        j = self.texte()
        self.assertIn("12 caractères copiés", j)
        self.assertNotIn("motdepasse42", j)

    def test_texte_apercu_si_demande(self):
        self.assertIn("motdepasse42", self.texte("oui"))
        self.journal.write_text("")
        self.assertNotIn("motdepasse42", self.texte("non"))

    def test_reglage_declare(self):
        src = (BIN / "nc-reglages").read_text()
        self.assertRegex(src, r'R\("CAPTURES_APERCU", "Captures",[^\n]*\n\s*"ouinon", "non"')


class Greeting(unittest.TestCase):
    def test_photo_ronde_privee(self):
        src = (BIN / "nc-greeting").read_text()
        i = src.index("term-photo-rond.png")
        j = src.index('mv "$PHOTO.tmp"', i)
        self.assertIn("umask 077", src[i:j])


# ───────────────────────────── 5 : nc-keys ─────────────────────────────
BINDS = """bind
\tlocked: false
\tmouse: false
\trelease: false
\trepeat: false
\tnon_consuming: false
\tmodmask: 64
\tsubmap:
\tkey: {touche}
\tkeycode: 0
\tcatch_all: false
\tdescription: IA|Essai
\tdispatcher: exec
\targ: x
"""


class Cles(Base):
    def cles(self, layout, code, variante=""):
        self.faux_prog("hyprctl", f'''case "$*" in
  binds) cat "{self.home}/binds" ;;
  "getoption input:kb_layout") printf 'str: {layout}\\nset: true\\n' ;;
  "getoption input:kb_variant") printf 'str: {variante}\\nset: true\\n' ;;
  *) printf 'str: \\nset: false\\n' ;;
esac''')
        (self.home / "binds").write_text(BINDS.format(touche=f"code:{code}"))
        r = subprocess.run([sys.executable, str(BIN / "nc-keys"), "json"], env=self.env(IA_MODE="non"), capture_output=True,
                           text=True, timeout=30)
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)[0]["rows"][0]["keys"][-1]

    def test_azerty_code_38_est_q(self):
        self.assertEqual(self.cles("fr", 38), "Q")
        self.assertEqual(self.cles("fr", 24), "A")
        self.assertEqual(self.cles("fr", 25), "Z")
        self.assertEqual(self.cles("fr", 52), "W")
        self.assertEqual(self.cles("fr", 58), ",")
        self.assertEqual(self.cles("fr", 47), "M")

    def test_belge_et_premiere_disposition(self):
        self.assertEqual(self.cles("be", 38), "Q")
        self.assertEqual(self.cles("fr,us", 38), "Q")

    def test_qwertz(self):
        self.assertEqual(self.cles("de", 52), "Y")
        self.assertEqual(self.cles("ch", 29), "Z")
        self.assertEqual(self.cles("de", 38), "A")

    def test_us_et_inconnues_gardent_les_noms_us(self):
        self.assertEqual(self.cles("us", 38), "A")
        self.assertEqual(self.cles("jp", 38), "A")

    def test_variante_bepo_pas_de_traduction(self):
        self.assertEqual(self.cles("fr", 38, "bepo"), "A")

    def test_disposition_active_du_clavier_principal(self):
        """Réglée par appareil, ou changée en cours de session (us,fr, 2e active) : celle du clavier principal compte,
        pas la valeur globale de getoption (us)."""
        appareils = {"keyboards": [{"name": "autre", "main": False, "layout": "de", "active_layout_index": 0},
                                   {"name": "interne", "main": True, "layout": "us,fr", "variant": ",", "active_layout_index": 1}]}
        self.faux_prog("hyprctl", f'''case "$*" in
  binds) cat "{self.home}/binds" ;;
  "devices -j") cat "{self.home}/devices.json" ;;
  "getoption input:kb_layout") printf 'str: us\\nset: true\\n' ;;
  *) printf 'str: \\nset: false\\n' ;;
esac''')
        (self.home / "devices.json").write_text(json.dumps(appareils))
        (self.home / "binds").write_text(BINDS.format(touche="code:38"))
        lire = lambda: json.loads(subprocess.run([sys.executable, str(BIN / "nc-keys"), "json"], env=self.env(IA_MODE="non"),
                                                 capture_output=True, text=True, timeout=30).stdout)[0]["rows"][0]["keys"][-1]
        self.assertEqual(lire(), "Q")
        appareils["keyboards"][1]["active_layout_index"] = 0
        (self.home / "devices.json").write_text(json.dumps(appareils))
        self.assertEqual(lire(), "A")
        appareils["keyboards"][1].update(layout="fr", variant="bepo")
        (self.home / "devices.json").write_text(json.dumps(appareils))
        self.assertEqual(lire(), "A")                                            # bépo : noms US

    def test_hyprctl_muet_noms_us(self):
        self.faux_prog("hyprctl", 'case "$*" in binds) cat "%s/binds" ;; esac' % self.home)
        (self.home / "binds").write_text(BINDS.format(touche="code:38"))
        r = subprocess.run([sys.executable, str(BIN / "nc-keys"), "json"], env=self.env(IA_MODE="non"), capture_output=True,
                           text=True, timeout=30)
        self.assertEqual(json.loads(r.stdout)[0]["rows"][0]["keys"][-1], "A")

    def test_doc_previent_pour_azerty(self):
        self.assertIn("AZERTY", (REPO / "RACCOURCIS.md").read_text())


# ───────────────────────────── 6, 7, 10 : nc-shell-msg et nc-touches ─────────────────────────────
class ShellMsg(Base):
    def setUp(self):
        super().setUp()
        self.faux_prog("pgrep", "exit 0")
        self.faux_prog("noctalia", 'echo "noctalia $*" >> "$JOURNAL"')
        self.faux_prog("hyprctl", 'echo "hyprctl $*" >> "$JOURNAL"')
        self.faux_prog("systemctl", "exit 1")
        self.faux_prog("notify-send", 'echo "notify $*" >> "$JOURNAL"')

    def test_sonde_chaque_seconde_et_bornee(self):
        src = (BIN / "nc-shell-msg").read_text()
        i = src.index("sans_flou()")
        corps = src[i:src.index("\n}\n", i)]
        self.assertNotIn("sleep 0.3", corps)
        self.assertIn("-lt 300", corps)
        self.assertIn("sleep 1;", corps)

    def test_sans_dossier_de_session_pas_de_verrou_dans_tmp(self):
        env = self.env()
        env.pop("XDG_RUNTIME_DIR")
        avant = Path("/tmp/nc-carousel-blur").exists()
        r = subprocess.run(["bash", str(BIN / "nc-shell-msg"), "wallpapers"], env=env, capture_output=True, text=True, timeout=30)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn("nc.flou", self.journal_texte(), "le flou n'est pas touché sans dossier de session")
        self.assertEqual(Path("/tmp/nc-carousel-blur").exists(), avant)

    def test_avec_dossier_de_session_verrou_puis_flou_remis(self):
        env = self.env()
        r = subprocess.run(["bash", str(BIN / "nc-shell-msg"), "wallpapers"], env=env, capture_output=True, text=True, timeout=30)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("nc.flou(false)", self.journal_texte())
        self.assertTrue(self.attendre(lambda: "nc.flou(true)" in self.journal_texte(), 10))
        self.assertTrue(self.attendre(lambda: not (self.home / "run/nc-carousel-blur").exists()))


class Touches(Base):
    def test_pave_sans_dossier_de_session_pas_de_fichier_dans_tmp(self):
        self.faux_prog("notify-send", 'echo "notify $*" >> "$JOURNAL"')
        self.faux_prog("hyprctl", 'echo "hyprctl $*" >> "$JOURNAL"')
        env = self.env()
        env.pop("XDG_RUNTIME_DIR")
        avant = Path("/tmp/nc-pave-coupe").exists()
        r = subprocess.run(["bash", str(BIN / "nc-touches"), "pave", "off"], env=env, capture_output=True, text=True, timeout=30)
        self.assertEqual(r.returncode, 1)
        self.assertEqual(Path("/tmp/nc-pave-coupe").exists(), avant)
        self.assertIn("session incomplète", self.journal_texte())

    def test_hyprland_relit_le_meme_fichier_jamais_tmp(self):
        """clavier.lua relit l'état du pavé au rechargement : le fichier de nc-touches, rien sans XDG_RUNTIME_DIR."""
        lua = (BIN.parent.parent / ".config/hypr/nc/clavier.lua").read_text()
        bloc = lua[lua.index("nc-pave-coupe") - 400:lua.index("nc-pave-coupe") + 200]
        self.assertNotIn('"/tmp"', bloc)
        self.assertIn('os.getenv("XDG_RUNTIME_DIR")', bloc)

    def test_langue_absente_ne_plante_pas(self):
        self.faux_prog("hyprctl", '''echo '{"keyboards":[{"main":true,"layout":"fr,us","active_keymap":"French"}]}' ''')
        env = self.env()
        env.pop("NC_LANGUE")
        r = subprocess.run(["bash", str(BIN / "nc-touches"), "disposition-active"], env=env, capture_output=True, text=True,
                           timeout=30)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), "Français\t2")


# ───────────────────────────── 8, 9 : nc-verrou-place ─────────────────────────────
class VerrouPlace(Base):
    CONFIG = '[lockscreen_widgets]\nenabled = true\nwidget_order = ["nc-heure"]\n\n' \
             '[lockscreen_widgets.widget.nc-heure]\ntype = "nc/verrou:heure"\noutput = "eDP-1"\ncx = 1.0\ncy = 1.0\n'

    def setUp(self):
        super().setUp()
        ecrans = json.dumps([{"name": "eDP-1", "width": 2000, "height": 1000, "scale": 1.0, "transform": 0}])
        self.faux_prog("hyprctl", f"echo '{ecrans}'")
        self.faux_prog("noctalia", 'echo "noctalia $*" >> "$JOURNAL"')
        self.conf = self.home / ".config/noctalia"
        self.etat = self.home / ".local/state/noctalia"
        self.conf.mkdir(parents=True)
        self.etat.mkdir(parents=True)
        (self.conf / "config.toml").write_text(self.CONFIG)
        (self.etat / "settings.toml").write_text(self.CONFIG)

    def lancer(self):
        env = self.env()
        return subprocess.run([sys.executable, str(BIN / "nc-verrou-place")], env=env, capture_output=True, text=True, timeout=30)

    def test_droits_de_settings_toml_gardes(self):
        if sys.version_info < (3, 11):
            self.skipTest("tomllib absent")
        s = self.etat / "settings.toml"
        s.chmod(0o640)
        r = self.lancer()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("cx = 1000.0", s.read_text(), "l'état a bien été recentré")
        self.assertEqual(stat.S_IMODE(s.stat().st_mode), 0o640)

    def test_temporaires_uniques_et_effaces(self):
        if sys.version_info < (3, 11):
            self.skipTest("tomllib absent")
        src = (BIN / "nc-verrou-place").read_text()
        self.assertNotIn("zx-verrou.toml.tmp", src)
        self.assertNotIn('ETAT + ".nc-tmp"', src)
        self.assertIn("mkstemp", src)
        r = self.lancer()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue((self.conf / "zx-verrou.toml").exists())
        self.assertEqual(sorted(p.name for p in self.conf.iterdir()), ["config.toml", "zx-verrou.toml"])
        self.assertEqual(sorted(p.name for p in self.etat.iterdir()), ["settings.toml"])

    def test_deux_executions_en_meme_temps(self):
        if sys.version_info < (3, 11):
            self.skipTest("tomllib absent")
        env = self.env()
        procs = [subprocess.Popen([sys.executable, str(BIN / "nc-verrou-place")], env=env, stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE, text=True) for _ in range(6)]
        for p in procs:
            _, err = p.communicate(timeout=60)
            self.assertEqual(p.returncode, 0, err)
        self.assertIn("cx = 1000.0", (self.conf / "zx-verrou.toml").read_text())
        self.assertEqual(sorted(p.name for p in self.conf.iterdir()), ["config.toml", "zx-verrou.toml"])


# ───────────────────────────── 11 : nc-aide-config ─────────────────────────────
class AideConfig(Base):
    def lancer(self, langue):
        b = self.home / ".local/bin"
        b.mkdir(parents=True)
        for n in ("nc-aide-config", "nc-reglages", "nc-aide", "nc-raccourci", "nc-langue", "nc-anim", "nc-keys"):
            if (BIN / n).exists():
                shutil.copy2(BIN / n, b / n)
        (self.home / ".config/nc/depot").write_text(str(REPO) + "\n")
        env = dict(os.environ, HOME=str(self.home), XDG_CONFIG_HOME=str(self.home / ".config"),
                   XDG_CACHE_HOME=str(self.home / ".cache"), NC_LANGUE=langue, PATH="/usr/bin:/bin")
        env.pop("WAYLAND_DISPLAY", None)
        return subprocess.run([str(b / "nc-aide-config"), "chercher", "zqxjwvkpzz"], env=env, capture_output=True, text=True,
                              timeout=120)

    def test_rien_trouve_traduit(self):
        r = self.lancer("en")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("Nothing found", r.stdout)
        self.assertNotIn("Rien trouvé", r.stdout)

    def test_rien_trouve_en_francais(self):
        r = self.lancer("fr")
        self.assertIn("Rien trouvé", r.stdout)


# ───────────────────────────── 12 : nc-wallpaper-colors ─────────────────────────────
class Fond(Base):
    def setUp(self):
        super().setUp()
        self.faux_prog("hyprctl", "echo '[]'")
        self.faux_prog("noctalia", "exit 0")
        self.img = self.home / "fond.png"
        self.img.write_text("ok")

    def lancer(self, *args, **env):
        return subprocess.run([sys.executable, str(BIN / "nc-wallpaper-colors"), str(self.img), *args],
                              env=self.env(PATH=str(self.faux), **env), capture_output=True, text=True, timeout=60,
                              stdin=subprocess.DEVNULL)

    def test_sans_imagemagick_le_dit_avec_le_paquet(self):
        r = self.lancer()
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("ImageMagick manquant", r.stderr)
        self.assertRegex(r.stderr, r"paquet (imagemagick|ImageMagick)\)")
        self.assertNotIn("illisible", r.stderr)

    def test_copie_trop_lente_est_arretee(self):
        # La lecture 64x64 répond tout de suite ; la copie du fond (sans « rgb:- ») ne finit jamais
        self.faux_prog("magick", '''case "$*" in
  *rgb:-*) head -c 12288 /dev/zero | tr '\\0' '\\200' ;;
  *) echo "$$" > "$JOURNAL.pid"; exec sleep 120 ;;
esac''')
        debut = time.time()
        r = self.lancer(NC_WALLPAPER_DELAI="1")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertLess(time.time() - debut, 20, "le hook ne reste pas bloqué sur la copie")
        self.assertFalse((self.home / ".cache/nc/wallpaper-boot.jpg").exists())
        pid = Path(str(self.journal) + ".pid")
        if pid.exists():                       # le fils lancé par le script doit être mort
            n = int(pid.read_text())
            try:
                os.kill(n, 0)
                vivant = True
            except OSError:
                vivant = False
            self.assertFalse(vivant)


# ───────────────────────────── 13 : nc-icones ─────────────────────────────
class Icones(Base):
    def test_inventaire_avec_chemins_a_espaces(self):
        env = self.env()
        anciennes = {k: os.environ.get(k) for k in ("HOME", "XDG_DATA_HOME")}
        os.environ["HOME"], os.environ["XDG_DATA_HOME"] = env["HOME"], env["XDG_DATA_HOME"]
        try:
            ch = importlib.machinery.SourceFileLoader("nc_icones_outils1", str(BIN / "nc-icones"))
            m = importlib.util.module_from_spec(importlib.util.spec_from_loader("nc_icones_outils1", ch))
            ch.exec_module(m)
        finally:
            for k, v in anciennes.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v
        dossier = self.home / "mes icônes"
        dossier.mkdir()
        icone = dossier / "mon icone.svg"
        icone.write_text("nouvelle")
        orig = dossier / "mon icone.svg.nc-orig"
        orig.write_text("origine")
        m.INVENTAIRE = self.home / "inventaire"
        m.INVENTAIRE.write_text(f"{icone}\n")
        m.remettre_autres_themes()
        self.assertEqual(icone.read_text(), "origine")
        self.assertFalse(orig.exists())
        self.assertFalse(m.INVENTAIRE.exists())


if __name__ == "__main__":
    unittest.main()

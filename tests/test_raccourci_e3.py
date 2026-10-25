"""nc-raccourci, nc-keys, nc-fenetre : champs à saut de ligne, lettres selon la disposition, adresse de « fermer »,
aide et action inconnue, touches Suppr/Début/Fin…, nc-keys sans Hyprland. HOME temporaire, faux hyprctl."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
BIN = REPO / "home/.local/bin"


class Base(unittest.TestCase):
    def setUp(self):
        d = tempfile.TemporaryDirectory(prefix="nc-e3-")
        self.addCleanup(d.cleanup)
        self.home = Path(d.name)
        (self.home / ".config/nc").mkdir(parents=True)
        b = self.home / ".local/bin"; b.mkdir(parents=True)
        for nom in ("nc-raccourci", "nc-keys", "nc-fenetre"):
            (b / nom).symlink_to(BIN / nom)
        self.faux = self.home / "faux"; self.faux.mkdir()
        self.env = dict(os.environ, HOME=str(self.home), PATH=f"{self.faux}:/usr/bin:/bin", NC_LANGUE="fr",
                        XDG_CONFIG_HOME=str(self.home / ".config"))

    def hyprctl(self, corps):
        f = self.faux / "hyprctl"
        f.write_text("#!/bin/sh\necho \"hyprctl $*\" >> \"$HOME/appels\"\n" + corps)
        f.chmod(0o755)

    def run_bin(self, nom, *args):
        return subprocess.run([str(self.home / ".local/bin" / nom), *args], env=self.env, capture_output=True, text=True,
                              timeout=30)

    def appels(self):
        f = self.home / "appels"
        return f.read_text() if f.exists() else ""


class Raccourci(Base):
    def faux_hyprctl(self, disposition, binds=""):
        self.hyprctl(f'''case "$1" in
  binds) cat <<'FIN'
{binds}
FIN
;;
  getoption) printf 'str: {disposition}\\nset: true\\n' ;;      # la sortie de Hyprland 0.56 : str puis set
  configerrors) echo ok ;;
esac
''')

    PRIS = "bind\n\tmodmask: 64\n\tsubmap: \n\tkey: \n\tkeycode: 0\n\tdescription: Vue de toutes les fenêtres\n\targ: x\n"

    def pris_sur_38(self):
        return self.PRIS.replace("key: \n", "key: code:38\n")

    def test_saut_de_ligne_dans_la_commande(self):
        self.faux_hyprctl("fr")
        r = self.run_bin("nc-raccourci", "ajoute", "Super+B", "echo a\nb")
        self.assertEqual(r.returncode, 0, r.stderr)
        brut = (self.home / ".config/nc/raccourcis.conf").read_text().splitlines()
        lignes = [l for l in brut if not l.startswith("#")]
        self.assertEqual(len(lignes), 1, "une seule ligne dans le fichier")
        r = self.run_bin("nc-raccourci", "liste")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn("Traceback", r.stderr)
        self.assertEqual(r.stdout.count("●"), 1)

    def test_ligne_abimee_ignoree(self):
        self.faux_hyprctl("fr")
        (self.home / ".config/nc/raccourcis.conf").write_text("ajout\tSUPER + B\tcommande\techo a\n")
        r = self.run_bin("nc-raccourci", "liste")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn("Traceback", r.stderr)
        self.assertEqual(r.stdout.count("●"), 0)

    def test_lettre_azerty_seul(self):
        self.faux_hyprctl("fr", self.pris_sur_38())          # code:38 = touche Q en AZERTY
        r = self.run_bin("nc-raccourci", "ajoute", "Super+A", "true")
        self.assertEqual(r.returncode, 0, r.stderr)
        r = self.run_bin("nc-raccourci", "ajoute", "Super+Q", "true")
        self.assertEqual(r.returncode, 1)
        self.assertIn("déjà pris", r.stderr)

    def test_lettre_us_et_fr_us(self):
        for disp in ("us", "fr,us"):
            self.faux_hyprctl(disp, self.pris_sur_38())      # code:38 = A en QWERTY
            r = self.run_bin("nc-raccourci", "ajoute", "Super+A", "true")
            self.assertEqual(r.returncode, 1, disp)
            self.assertIn("déjà pris", r.stderr, disp)
        self.faux_hyprctl("us", self.pris_sur_38())
        self.assertEqual(self.run_bin("nc-raccourci", "ajoute", "Super+Q", "true").returncode, 0)

    def test_disposition_inconnue_garde_qwerty(self):
        self.faux_hyprctl("fr", self.pris_sur_38())
        (self.faux / "hyprctl").write_text((self.faux / "hyprctl").read_text().replace("getoption)", "getoption) exit 0 ;;\n  zz)"))
        r = self.run_bin("nc-raccourci", "ajoute", "Super+A", "true")
        self.assertEqual(r.returncode, 1)


class Keys(Base):
    def test_touches_ajoutees(self):
        r = subprocess.run(["python3", "-I", "-c",
                            "import importlib.machinery as m, importlib.util as u, sys;"
                            "l=m.SourceFileLoader('k',sys.argv[1]);k=u.module_from_spec(u.spec_from_loader('k',l));l.exec_module(k);"
                            "print(*[k.key_label('code:%d'%c) for c in (119,110,115,112,117,118)],sep='|')",
                            str(BIN / "nc-keys")], env=self.env, capture_output=True, text=True)
        self.assertEqual(r.stdout.strip(), "Suppr|Début|Fin|Page préc.|Page suiv.|Inser.", r.stderr)

    def test_sans_hyprland(self):
        self.hyprctl("exit 1\n")
        r = self.run_bin("nc-keys")
        self.assertNotEqual(r.returncode, 0)
        self.assertNotIn("Traceback", r.stderr)
        self.assertIn("Hyprland", r.stderr)


@unittest.skipUnless(shutil.which("jq") and shutil.which("bash") and shutil.which("flock"), "jq, bash et flock requis")
class Fenetre(Base):
    def setUp(self):
        super().setUp()
        self.hyprctl("exit 0\n")

    def test_fermer_valide_adresse(self):
        r = self.run_bin("nc-fenetre", "fermer", "0x1'}) os.exit() --")
        self.assertEqual(r.returncode, 2)
        self.assertNotIn("hyprctl", self.appels())
        r = self.run_bin("nc-fenetre", "fermer", "0xAb12")
        self.assertEqual(r.returncode, 0)
        self.assertIn("window.close", self.appels())

    def test_aide_complete(self):
        r = self.run_bin("nc-fenetre", "aide")
        self.assertEqual(r.returncode, 0)
        self.assertIn("nc-fenetre suivre", r.stdout)
        self.assertIn("revient aussi d'elle-même", r.stdout)
        self.assertNotIn("set -uo", r.stdout)

    def test_action_inconnue(self):
        r = self.run_bin("nc-fenetre", "zzz")
        self.assertEqual(r.returncode, 2)
        self.assertEqual(self.run_bin("nc-fenetre").returncode, 0)


if __name__ == "__main__":
    unittest.main()

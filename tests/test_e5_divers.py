"""Petits correctifs E5 : coupe des lignes de nc-greeting (octets de mawk) et kdeglobals cassé de nc-theme-sync.
Tout se passe dans un HOME temporaire, avec de faux fastfetch et nc-icones."""
import importlib.machinery
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock

BIN = Path(__file__).resolve().parent.parent / "home/.local/bin"


class Greeting(unittest.TestCase):
    COUL = "\033[1;38;5;12m"
    LIGNE = COUL + "\U000f0322\033[0m  Batterie ▰▰▰▰▰▱▱▱▱▱ 50 % ééééé"

    def setUp(self):
        d = tempfile.TemporaryDirectory(prefix="nc-greeting-")
        self.addCleanup(d.cleanup)
        self.home = Path(d.name)
        self.faux = self.home / "faux"
        self.faux.mkdir()
        (self.faux / "fastfetch").write_text("#!/bin/sh\nprintf '%s\\n' \"$NC_TEST_LIGNE\"\n")
        (self.faux / "fastfetch").chmod(0o755)

    def lancer(self, cols, ligne=None, path=None):
        env = dict(os.environ, HOME=str(self.home), PATH=path or f"{self.faux}:{os.environ['PATH']}",
                   NC_TEST_LIGNE=self.LIGNE if ligne is None else ligne, LC_ALL="C.UTF-8")
        r = subprocess.run(["bash", str(BIN / "nc-greeting"), str(cols), "20"], env=env, capture_output=True, timeout=30)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout.decode("utf-8")

    def visible(self, texte):
        return texte.replace(self.COUL, "").replace("\033[0m", "").rstrip("\n")

    def test_coupe_en_colonnes_et_pas_en_octets(self):
        entier = self.visible(self.LIGNE)                     # 38 colonnes
        for cols in (34, 36, 45):
            sortie = self.lancer(cols)
            self.assertEqual(self.visible(sortie), entier[:cols - 1], cols)   # jamais d'octet coupé en deux
            self.assertNotIn("\ufffd", sortie)
            self.assertTrue(sortie.startswith(self.COUL))     # les codes couleur sont gardés
            self.assertTrue(sortie.endswith("\033[0m\n"))

    def test_caracteres_larges_comptent_double(self):
        sortie = self.lancer(34, ligne="日本語" * 10)                  # largeur 33 : 16 caractères larges
        self.assertEqual(self.visible(sortie), ("日本語" * 10)[:16])

    def test_dernier_retour_absent(self):
        (self.faux / "fastfetch").write_text("#!/bin/sh\nprintf 'abc\\ndef'\n")
        self.assertEqual(self.visible(self.lancer(40)).replace("\033[0m", ""), "abc\ndef")

    @unittest.skipUnless(shutil.which("gawk"), "gawk absent")
    def test_awk_en_octets_ne_gene_plus(self):
        """Un awk qui compte en octets (mawk, ou gawk en LC_ALL=C) ne change plus la coupe : elle se fait en Python."""
        bindir = self.home / "awkc"
        bindir.mkdir()
        (bindir / "awk").write_text("#!/bin/sh\nLC_ALL=C exec gawk \"$@\"\n")
        (bindir / "awk").chmod(0o755)
        avec = self.lancer(40, path=f"{bindir}:{self.faux}:{os.environ['PATH']}")
        self.assertEqual(avec, self.lancer(40))
        self.assertIn("▱▱▱▱▱", avec)


def charger_theme_sync(home):
    with mock.patch.dict(os.environ, {"HOME": home}):
        chargeur = importlib.machinery.SourceFileLoader("nc_theme_sync_e5", str(BIN / "nc-theme-sync"))
        m = importlib.util.module_from_spec(importlib.util.spec_from_loader(chargeur.name, chargeur))
        chargeur.exec_module(m)
    return m


class KdeglobalsCasse(unittest.TestCase):
    COLORS = ('{"mPrimary":"#67b3e4","mOnPrimary":"#182025","mSurface":"#13212a","mOnSurface":"#f2f2f3",'
              '"mSecondary":"#aabbcc","mTertiary":"#ccbbaa","mOnSurfaceVariant":"#cccccc"}')

    def preparer(self, kdeglobals):
        d = tempfile.TemporaryDirectory(prefix="nc-theme-sync-e5-")
        self.addCleanup(d.cleanup)
        home = Path(d.name)
        (home / ".config/noctalia").mkdir(parents=True)
        (home / ".config/noctalia/colors.json").write_text(self.COLORS)
        (home / ".local/share/color-schemes").mkdir(parents=True)
        (home / ".local/share/color-schemes/noctalia.colors").write_text("[Colors:View]\nBackgroundNormal=1,2,3\n")
        (home / ".local/bin").mkdir(parents=True)
        for nom in ("nc-icones", "nc-firefox", "nc-term-logo"):
            f = home / ".local/bin" / nom
            f.write_text('#!/bin/sh\necho "%s $*" >> "%s/appels"\n' % (nom, home))
            f.chmod(0o755)
        if kdeglobals is not None:
            (home / ".config/kdeglobals").write_bytes(kdeglobals)
        return home

    def lancer(self, home):
        env = dict(os.environ, HOME=str(home), NC_LANGUE="fr")
        return subprocess.run(["python3", str(BIN / "nc-theme-sync")], env=env, capture_output=True, text=True, timeout=60)

    def test_kdeglobals_casse_laisse_intact_et_la_suite_continue(self):
        for contenu in (b"ligne sans egal\n[General]\nA=1\n", b"A=1\n[General]\nB=2\n", b"[General]\n\xff\xfe=\x80\n"):
            home = self.preparer(contenu)
            r = self.lancer(home)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual((home / ".config/kdeglobals").read_bytes(), contenu)
            self.assertIn("kdeglobals", r.stderr)
            appels = (home / "appels").read_text()
            self.assertIn("nc-icones", appels)
            self.assertIn("nc-firefox couleurs", appels)
            self.assertIn("nc-term-logo", appels)

    def test_kdeglobals_sain_toujours_mis_a_jour(self):
        home = self.preparer(b"[General]\nA=1\n")
        r = self.lancer(home)
        self.assertEqual(r.returncode, 0, r.stderr)
        t = (home / ".config/kdeglobals").read_text()
        self.assertIn("BackgroundNormal=1,2,3", t)
        self.assertIn("A=1", t)


if __name__ == "__main__":
    unittest.main()

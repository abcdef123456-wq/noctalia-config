"""Issue 28 : nc-touches disposition (bascule de tous les claviers + bulle), nc-ile-etat clavier_disposition, ligne de l'île."""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
BIN = REPO / "home/.local/bin"
SYSTEME = REPO / "home/.config/quickshell/nc-ile/Systeme.qml"


class Disposition(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="nc-disp-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.fb = self.tmp / "fb"; self.fb.mkdir()
        self.journal = self.tmp / "j"; self.journal.touch()
        (self.tmp / "run").mkdir(); (self.tmp / "home/.local/bin").mkdir(parents=True)
        for n in ("nc-langue", "nc-touches", "nc-ile-etat"):
            (self.tmp / "home/.local/bin" / n).symlink_to(BIN / n)

    def faux(self, nom, corps):
        f = self.fb / nom
        f.write_text("#!/bin/sh\n" + corps); f.chmod(0o755)

    def clavier(self, claviers, suivant=None):
        """hyprctl factice : devices -j répond `claviers` ; switchxkblayout passe à `suivant` (active_keymap) et est noté."""
        etat = self.tmp / "etat.json"
        etat.write_text(json.dumps({"keyboards": claviers}))
        nouveau = self.tmp / "nouveau.json"
        if suivant is not None:
            nouveau.write_text(json.dumps({"keyboards": suivant}))
        self.faux("hyprctl", f'''case "$*" in
  *switchxkblayout*) echo "hyprctl $*" >> {self.journal}; [ -f {nouveau} ] && cp {nouveau} {etat}; echo ok ;;
  *devices*) cat {etat} ;;
  *) echo "hyprctl $*" >> {self.journal} ;;
esac
''')
        self.faux("notify-send", f'echo "notify $*" >> {self.journal}\n')
        self.faux("noctalia", f'echo "noctalia $*" >> {self.journal}\n')

    def lancer(self, script, *args, langue="fr"):
        env = dict(os.environ, HOME=str(self.tmp / "home"), XDG_RUNTIME_DIR=str(self.tmp / "run"), NC_LANGUE=langue,
                   PATH=f"{self.fb}:{os.environ['PATH']}")
        r = subprocess.run([str(self.tmp / "home/.local/bin" / script), *args], env=env, capture_output=True, text=True, timeout=30)
        return r.stdout

    def appels(self):
        return self.journal.read_text().splitlines()

    @staticmethod
    def kb(nom, layout, keymap, main=False):
        return {"name": nom, "layout": layout, "active_keymap": keymap, "main": main}

    def test_deux_dispositions_bascule_tous_les_claviers(self):
        self.clavier([self.kb("usb", "us,fr", "English (US)"), self.kb("portable", "us,fr", "English (US)", True)],
                     [self.kb("usb", "us,fr", "French"), self.kb("portable", "us,fr", "French", True)])
        self.lancer("nc-touches", "disposition")
        a = self.appels()
        self.assertIn("hyprctl switchxkblayout all next", a)
        self.assertFalse(any(x.startswith("noctalia") for x in a))
        bulles = [x for x in a if x.startswith("notify")]
        self.assertEqual(len(bulles), 1)
        self.assertTrue(bulles[0].endswith("Disposition : Français"), bulles[0])

    def test_bulle_en_anglais(self):
        self.clavier([self.kb("p", "us,fr", "English (US)", True)], [self.kb("p", "us,fr", "French", True)])
        self.lancer("nc-touches", "layout", langue="en")
        self.assertTrue(self.appels()[-1].endswith("Layout: French"))

    def test_une_seule_disposition_explique(self):
        self.clavier([self.kb("p", "fr", "French", True)])
        self.lancer("nc-touches", "disposition")
        a = self.appels()
        self.assertFalse(any("switchxkblayout" in x for x in a))
        self.assertEqual(len([x for x in a if x.startswith("notify")]), 1)
        self.assertIn("Une seule disposition", a[-1])
        self.assertIn("us,fr", a[-1])

    def test_aucun_clavier_ne_plante_pas(self):
        self.clavier([])
        self.lancer("nc-touches", "disposition")
        self.assertIn("Une seule disposition", self.appels()[-1])

    def test_clavier_principal_prefere(self):
        self.clavier([self.kb("usb", "us", "English (US)"), self.kb("p", "us,fr", "French", True)])
        self.assertEqual(self.lancer("nc-touches", "disposition-active"), "Français\t2\n")

    def test_ile_etat(self):
        self.clavier([self.kb("p", "us,fr", "English (US)", True)])
        sortie = self.lancer("nc-ile-etat", "systeme")
        c = dict(l.split("=", 1) for l in sortie.splitlines() if "=" in l)
        self.assertEqual(c.get("clavier_disposition"), "Anglais (US)")
        self.assertEqual(c.get("clavier_nb"), "2")

    def test_ligne_de_l_ile(self):
        src = SYSTEME.read_text()
        ligne = next(l for l in src.splitlines() if "Switch Keyboard Layout" in l)
        self.assertIn('[Etat.bin + "nc-touches", "disposition"]', ligne)
        self.assertIn("sous: Etat.sys.clavier_disposition", ligne)
        self.assertNotIn("keyboard-layout-cycle", src)
        self.assertRegex(src, r'titre: modelData\.titre; sous: modelData\.sous')


if __name__ == "__main__":
    unittest.main()

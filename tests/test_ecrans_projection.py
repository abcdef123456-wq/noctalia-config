"""nc-ecrans : le mode « externe » (l'écran du PC s'éteint) demande « Garder ? » et revient à « étendre » sans réponse ;
une erreur de configuration nouvelle après le rechargement l'annule tout de suite ; les « \\ » d'une description d'écran
ne sont plus lus comme des échappements par awk. Faux hyprctl, faux notify-send, HOME temporaire."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import unittest

REPO = Path(__file__).resolve().parents[1]
NC_ECRANS = REPO / "home/.local/bin/nc-ecrans"


def moniteurs(desc_externe):
    return json.dumps([
        {"name": "eDP-1", "description": "Panneau interne", "disabled": False, "mirrorOf": "none", "focused": True,
         "width": 2560, "height": 1600, "refreshRate": 165.0},
        {"name": "HDMI-A-1", "description": desc_externe, "disabled": False, "mirrorOf": "none", "focused": False,
         "width": 1920, "height": 1080, "refreshRate": 60.0}])


@unittest.skipUnless(shutil.which("jq"), "jq requis")
class Projection(unittest.TestCase):
    def setUp(self):
        d = tempfile.TemporaryDirectory(prefix="nc-ecrans-proj-")
        self.addCleanup(d.cleanup)
        self.d = Path(d.name)
        self.home = self.d / "home"
        (self.home / ".config/nc").mkdir(parents=True)
        self.faux = self.d / "faux"
        self.faux.mkdir()
        self.journal = self.d / "journal"
        self.conf = self.home / ".config/nc/ecrans.conf"
        self.env = dict(os.environ, HOME=str(self.home), XDG_CONFIG_HOME=str(self.home / ".config"),
                        XDG_CACHE_HOME=str(self.home / ".cache"), XDG_RUNTIME_DIR=str(self.d), TMPDIR=str(self.d),
                        NC_LANGUE="fr", J=str(self.journal), D=str(self.d), PATH=f"{self.faux}:{os.environ['PATH']}")
        self.desc = "Projecteur"
        self.erreurs()

    def script(self, nom, corps):
        p = self.faux / nom
        p.write_text("#!/bin/sh\n" + corps + "\n")
        p.chmod(0o755)

    def erreurs(self, avant="", apres=None):
        """Faux hyprctl : les erreurs de configuration valent `avant`, puis `apres` une fois rechargé."""
        (self.d / "erreurs").write_text(avant)
        if apres is not None:
            (self.d / "apres").write_text(apres)
        self.script("hyprctl", '''echo "hyprctl $*" >> "$J"
case "$1" in
  monitors) cat "$D/moniteurs" ;;
  reload) [ -f "$D/apres" ] && cp "$D/apres" "$D/erreurs" ;;
  configerrors) if [ -s "$D/erreurs" ]; then cat "$D/erreurs"; else echo ok; fi ;;
esac''')

    def lancer(self, *args, choix=""):
        (self.d / "moniteurs").write_text(moniteurs(self.desc))
        self.script("notify-send", f'echo "notify-send $*" >> "$J"; printf "%s" "{choix}"')
        return subprocess.run(["bash", str(NC_ECRANS), *args], env=self.env, capture_output=True, text=True, timeout=30,
                              stdin=subprocess.DEVNULL)

    def lignes(self):
        return self.journal.read_text().splitlines() if self.journal.exists() else []

    def attendre(self, condition, delai=8.0):
        fin = time.monotonic() + delai
        while time.monotonic() < fin:
            if condition():
                return True
            time.sleep(0.1)
        return False

    def mode_conf(self):
        ecran = [l.split("\t") for l in self.conf.read_text().splitlines() if l.startswith("ECRAN\t")]
        return [(e[1], e[3]) for e in ecran]

    def test_externe_sans_reponse_revient_a_etendre(self):
        r = self.lancer("externe")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(self.attendre(lambda: ("etendre", "Projecteur") in self.mode_conf()),
                        f"retour à étendre attendu : {self.mode_conf()} {self.lignes()}")
        question = [l for l in self.lignes() if l.startswith("notify-send ") and "-A garder=" in l]
        self.assertEqual(len(question), 1, self.lignes())
        self.assertIn(" -- ", question[0])
        self.assertIn("-t 15000", question[0])

    def test_externe_garder_reste(self):
        r = self.lancer("externe", choix="garder")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(self.attendre(lambda: any("-A garder=" in l for l in self.lignes())))
        time.sleep(0.5)
        self.assertEqual(self.mode_conf(), [("externe", "Projecteur")])

    def test_deja_externe_pas_de_question(self):
        self.conf.write_text("ECRAN\texterne\tdroite\tProjecteur\n")
        self.lancer("externe")
        time.sleep(0.5)
        self.assertEqual([l for l in self.lignes() if "-A garder=" in l], [])

    def test_autres_modes_pas_de_question(self):
        for mode in ("pc", "miroir", "etendre"):
            self.lancer(mode)
        time.sleep(0.5)
        self.assertEqual([l for l in self.lignes() if "-A garder=" in l], [])

    def test_erreur_nouvelle_annule_tout_de_suite(self):
        self.conf.write_text("PRINCIPAL=eDP-1\nECRAN\tetendre\tdroite\tProjecteur\n")
        self.erreurs(avant="", apres="ecrans.lua: erreur nouvelle\n")
        r = self.lancer("externe")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertEqual(self.mode_conf(), [("etendre", "Projecteur")])
        time.sleep(0.5)
        self.assertEqual([l for l in self.lignes() if "-A garder=" in l], [], "pas de question : déjà annulé")

    def test_vieille_erreur_ne_bloque_pas(self):
        self.erreurs(avant="perso.lua: vieille erreur\n", apres="perso.lua: vieille erreur\n")
        r = self.lancer("externe", choix="garder")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.mode_conf(), [("externe", "Projecteur")])

    def test_description_avec_barre_oblique_inverse(self):
        self.desc = "Proj\\tecteur \\x41"
        self.conf.write_text(f"PRINCIPAL=eDP-1\nECRAN\tpc\tdroite\t{self.desc}\n")
        r = self.lancer("etendre")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.mode_conf(), [("etendre", self.desc)], "une seule ligne, description intacte")
        self.conf.write_text(f"PRINCIPAL=eDP-1\nECRAN\tmiroir\tgauche\t{self.desc}\n")
        etat = json.loads(self.lancer("etat").stdout)
        self.assertEqual((etat["mode"], etat["position"]), ("miroir", "gauche"))


if __name__ == "__main__":
    unittest.main()

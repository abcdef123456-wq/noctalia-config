"""Le pilotage de kitty passe par le socket seulement (allow_remote_control socket-only) : une commande reçue par le
terminal est refusée, donc du texte affiché (un fichier piégé, un journal, un hôte SSH) ne peut pas piloter kitty.
Tout ce que le dépôt envoie à kitty passe par --to unix:…, et rien ne redonne le droit à une fenêtre en particulier."""
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
CONF = REPO / "home/.config/kitty/kitty.conf"
# « kitty @ », « kitten @ », et leurs formes en liste : ["kitty", "@", …]
PILOTAGE = re.compile(r"""\b(?:kitty|kitten)\b["',\s]*@(?![\w.])""")


def fichiers_du_depot():
    for f in [REPO / "install.sh", *sorted((REPO / "home").rglob("*"))]:
        if f.is_file() and not f.is_symlink() and f.stat().st_size < 2_000_000:
            try:
                yield f, f.read_text()
            except UnicodeDecodeError:
                continue


def lignes_utiles(conf):
    return [l.strip() for l in conf.splitlines() if l.strip() and not l.lstrip().startswith("#")]


class Pilotage(unittest.TestCase):
    def test_socket_seulement_et_socket_declare(self):
        lignes = lignes_utiles(CONF.read_text())
        self.assertEqual([l for l in lignes if l.startswith("allow_remote_control")], ["allow_remote_control socket-only"])
        self.assertEqual([l for l in lignes if l.startswith("listen_on")], ["listen_on unix:${XDG_RUNTIME_DIR}/kitty-{kitty_pid}"],
                         "sans listen_on, socket-only coupe tout : l'île ne pourrait plus écrire dans le terminal")
        self.assertNotIn("remote_control_password", CONF.read_text(), "un mot de passe rouvrirait le terminal")

    def test_tout_appel_du_depot_passe_par_le_socket(self):
        appels = []
        for f, texte in fichiers_du_depot():
            for n, ligne in enumerate(texte.splitlines(), 1):
                if not PILOTAGE.search(ligne):
                    continue
                nu = ligne.strip()
                if nu.startswith(("#", "//", '"""')):           # un commentaire ou une docstring ne lance rien
                    continue
                appels.append(f"{f.relative_to(REPO)}:{n}")
                self.assertIn('"--to", "unix:"', ligne, f"{f.relative_to(REPO)}:{n} : sans --to, le terminal est refusé")
        self.assertGreaterEqual(len(appels), 3, f"le motif ne voit plus les appels de nc-claude : {appels}")

    def test_aucune_fenetre_ne_recoit_le_droit_a_part(self):
        """launch --allow-remote-control donnerait le pilotage par le terminal à cette fenêtre, malgré socket-only."""
        for f, texte in fichiers_du_depot():
            self.assertNotIn("--allow-remote-control", texte, str(f.relative_to(REPO)))

    @unittest.skipUnless(shutil.which("kitty"), "kitty requis")
    def test_le_vrai_kitty_lit_cette_valeur(self):
        """Une valeur inconnue serait ignorée par kitty (le défaut « no » couperait l'île) : le vrai lecteur de config la lit."""
        with tempfile.TemporaryDirectory(prefix="nc-kitty-") as d:
            home = Path(d) / "home"
            (home / ".config/kitty").mkdir(parents=True)
            copie = home / ".config/kitty/kitty.conf"
            copie.write_text(CONF.read_text())
            env = dict(os.environ, HOME=str(home), XDG_CONFIG_HOME=str(home / ".config"), XDG_RUNTIME_DIR=d, XDG_CACHE_HOME=d,
                       XDG_STATE_HOME=d, XDG_DATA_HOME=d, KITTY_CONFIG_DIRECTORY=str(home / ".config/kitty"))
            code = ("from kitty.config import load_config\n"
                    f"o = load_config({str(copie)!r})\n"
                    "print(o.allow_remote_control)\n"
                    "print(o.listen_on)\n")
            r = subprocess.run(["kitty", "+runpy", code], env=env, cwd=d, capture_output=True, text=True, timeout=30)
        self.assertEqual(r.returncode, 0, r.stderr)
        lignes = r.stdout.splitlines()
        self.assertEqual(lignes[0], "socket-only", r.stdout + r.stderr)
        self.assertIn("kitty-", lignes[1])


if __name__ == "__main__":
    unittest.main()

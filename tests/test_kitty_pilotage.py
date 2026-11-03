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
# « kitty @ », « kitten @ », « $KITTY @ », « kitty_bin @ », et les formes en liste, même sur deux lignes : ["kitty", "@", …]
PILOTAGE = re.compile(r"""(?<![\w-])\$?\{?(?:kitty|kitten)\w*\}?["',\s]*@(?![\w.])""", re.I)


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
        self.assertNotIn("remote_control_password", CONF.read_text(), "ce dépôt n'utilise pas de mot de passe de pilotage")

    def test_tout_appel_du_depot_passe_par_le_socket(self):
        """--to est exigé parce que l'île tourne hors de kitty : sans lui, kitty lirait KITTY_LISTEN_ON, absent de son environnement."""
        appels = []
        for f, texte in fichiers_du_depot():
            for trouve in PILOTAGE.finditer(texte):
                ligne = texte[texte.rfind("\n", 0, trouve.start()) + 1:].split("\n", 1)[0].strip()
                if ligne.startswith(("#", "//", '"""')):         # un commentaire ou une docstring ne lance rien
                    continue
                ou = f"{f.relative_to(REPO)}:{texte.count(chr(10), 0, trouve.start()) + 1}"
                appels.append(ou)
                self.assertIn("--to", texte[trouve.end():trouve.end() + 60], f"{ou} : sans --to, ce pilotage ne vise pas le socket")
        self.assertGreaterEqual(len(appels), 3, f"le motif ne voit plus les appels de nc-claude : {appels}")

    def test_le_motif_voit_les_formes_courantes(self):
        for forme in ("kitty @ ls", "kitten @ ls", '["kitty", "@", "ls"]', '["kitten",\n  "@", "ls"]', "$KITTY @ ls", "${KITTY} @ ls", "kitty_bin @ ls"):
            self.assertRegex(forme, PILOTAGE, forme)
        for autre in ("nc-kitty @x", "kitty@exemple.org", "kitten|kitty|pet"):
            self.assertNotRegex(autre, PILOTAGE, autre)

    def test_aucune_fenetre_ni_aucun_script_ne_rouvre_le_terminal(self):
        """Une fenêtre lancée avec ce droit reste pilotable par le texte affiché, malgré socket-only ; une commande écrite à la
        main sur le terminal serait refusée ; et ce réglage ne se décide que dans kitty.conf."""
        for f, texte in fichiers_du_depot():
            nom = str(f.relative_to(REPO))
            for interdit in ("--allow-remote-control", "new_window @", "P@kitty-cmd"):
                self.assertNotIn(interdit, texte, nom)
            if f != CONF:
                self.assertNotIn("allow_remote_control", texte, nom)

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

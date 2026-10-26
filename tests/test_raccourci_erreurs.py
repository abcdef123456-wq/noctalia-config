"""nc-raccourci : une vieille erreur de configuration (perso.lua, vieux raccourci) ne fait plus refuser tout ajout ;
seule une erreur nouvelle, apparue avec le changement, le refuse (et le fichier est remis comme avant). HOME
temporaire, faux hyprctl qui lit ses erreurs dans un fichier."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
BIN = REPO / "home/.local/bin"


class Erreurs(unittest.TestCase):
    def setUp(self):
        d = tempfile.TemporaryDirectory(prefix="nc-raccourci-err-")
        self.addCleanup(d.cleanup)
        self.home = Path(d.name)
        (self.home / ".config/nc").mkdir(parents=True)
        faux = self.home / "faux"
        faux.mkdir()
        (faux / "hyprctl").write_text(
            '#!/bin/sh\ncase "$1" in\n'
            '  binds) ;;\n'
            "  getoption) printf 'str: fr\\nset: true\\n' ;;\n"
            '  reload) [ -f "$HOME/apres" ] && [ -s "$HOME/.config/nc/raccourcis.conf" ] && '
            'grep -q "Super+B\\|SUPER" "$HOME/.config/nc/raccourcis.conf" && cp "$HOME/apres" "$HOME/erreurs" ;;\n'
            '  configerrors) if [ -s "$HOME/erreurs" ]; then cat "$HOME/erreurs"; else echo ok; fi ;;\n'
            'esac\n')
        (faux / "hyprctl").chmod(0o755)
        self.env = dict(os.environ, HOME=str(self.home), PATH=f"{faux}:/usr/bin:/bin", NC_LANGUE="fr",
                        XDG_CONFIG_HOME=str(self.home / ".config"))

    def ajoute(self):
        return subprocess.run([str(BIN / "nc-raccourci"), "ajoute", "Super+B", "true"], env=self.env,
                              capture_output=True, text=True, timeout=30)

    def test_vieille_erreur_n_empeche_pas_l_ajout(self):
        (self.home / "erreurs").write_text("perso.lua:12: attempt to call a nil value\n")
        r = self.ajoute()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("Super+B", (self.home / ".config/nc/raccourcis.conf").read_text().replace("SUPER + B", "Super+B"))

    def test_erreur_nouvelle_refuse_et_remet(self):
        (self.home / "erreurs").write_text("perso.lua:12: attempt to call a nil value\n")
        (self.home / "apres").write_text("perso.lua:12: attempt to call a nil value\nraccourcis.conf: touche inconnue\n")
        r = self.ajoute()
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("touche inconnue", r.stderr)
        self.assertNotIn("attempt to call", r.stderr, "seulement la nouvelle erreur")
        conf = self.home / ".config/nc/raccourcis.conf"
        self.assertNotIn("true", conf.read_text() if conf.exists() else "")

    def test_sans_erreur_comme_avant(self):
        self.assertEqual(self.ajoute().returncode, 0)


if __name__ == "__main__":
    unittest.main()

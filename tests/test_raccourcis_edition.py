"""Édition des raccourcis par nc-reglages raccourci JSON (la fiche Super + / et la page des réglages, Raccourcis.qml) :
ajouter un raccourci à toi, le renommer, le retirer ; HOME temporaire, faux hyprctl (aucun vrai rechargement)."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
BIN = REPO / "home/.local/bin"


class Edition(unittest.TestCase):
    def setUp(self):
        d = tempfile.TemporaryDirectory(prefix="nc-raccourcis-")
        self.addCleanup(d.cleanup)
        self.home = Path(d.name)
        (self.home / ".config/nc").mkdir(parents=True)
        b = self.home / ".local/bin"; b.mkdir(parents=True)
        for nom in ("nc-reglages", "nc-raccourci", "nc-keys"):                 # chargés depuis ~/.local/bin
            (b / nom).symlink_to(BIN / nom)
        faux = self.home / "faux"; faux.mkdir()
        (faux / "hyprctl").write_text('#!/bin/sh\necho "hyprctl $*" >> "$HOME/appels"\n'); (faux / "hyprctl").chmod(0o755)
        self.env = dict(os.environ, HOME=str(self.home), PATH=f"{faux}:/usr/bin:/bin", NC_LANGUE="fr",
                        XDG_CONFIG_HOME=str(self.home / ".config"))

    def action(self, **d):
        return subprocess.run([str(self.home / ".local/bin/nc-reglages"), "raccourci", json.dumps(d)], env=self.env, capture_output=True,
                              text=True, timeout=30)

    def conf(self):
        f = self.home / ".config/nc/raccourcis.conf"
        return [l.split("\t") for l in f.read_text().splitlines() if l and not l.startswith("#")] if f.exists() else []

    def test_ajouter_renommer_retirer(self):
        r = self.action(action="ajouter", touches="Super+B", cible="bureau 3", nom="")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.conf(), [["ajout", "SUPER + B", "bureau", "3", "Bureau 3"]])
        self.assertIn("hyprctl reload", (self.home / "appels").read_text())
        bind = self.conf()[0][1]
        r = self.action(action="renommer", mien=bind, nom="Jeux\tvidéo")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.conf()[0][4], "Jeux vidéo", "pas de tabulation dans le fichier")
        self.assertNotEqual(self.action(action="renommer", mien=bind, nom="  ").returncode, 0, "nom vide refusé")
        self.assertNotEqual(self.action(action="ajouter", touches="Super+C", cible=" ").returncode, 0, "cible vide refusée")
        r = self.action(action="retirer", mien=bind)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.conf(), [])


if __name__ == "__main__":
    unittest.main()

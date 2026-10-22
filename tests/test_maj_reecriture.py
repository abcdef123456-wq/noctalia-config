"""nc-maj suit un historique réécrit en amont (auteurs changés, mêmes changements) : la mise à jour reprend la nouvelle
version, garde l'ancienne dans une branche de sauvegarde et ne montre que les vraies nouveautés ; avec des commits à
toi, rien n'est touché. Vrais dépôts git dans un dossier temporaire (HOME et XDG_* compris)."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
NC_MAJ = REPO / "home/.local/bin/nc-maj"


class Reecriture(unittest.TestCase):
    def setUp(self):
        d = tempfile.TemporaryDirectory(prefix="nc-maj-reecrit-")
        self.addCleanup(d.cleanup)
        self.d = Path(d.name)
        self.home = self.d / "home"
        (self.home / ".config/nc").mkdir(parents=True)
        self.env = dict(os.environ, HOME=str(self.home), XDG_CACHE_HOME=str(self.home / ".cache"),
                        XDG_CONFIG_HOME=str(self.home / ".config"), NC_LANGUE="fr", GIT_AUTHOR_NAME="Ancien Nom",
                        GIT_AUTHOR_EMAIL="ancien@exemple.invalid", GIT_COMMITTER_NAME="Ancien Nom",
                        GIT_COMMITTER_EMAIL="ancien@exemple.invalid", FILTER_BRANCH_SQUELCH_WARNING="1")
        self.env.pop("HYPRLAND_INSTANCE_SIGNATURE", None)
        self.amont = self.d / "amont.git"
        self.git("init", "-q", "--bare", "-b", "main", str(self.amont))
        self.auteur = self.d / "auteur"
        self.git("clone", "-q", str(self.amont), str(self.auteur))
        self.git("-C", str(self.auteur), "checkout", "-q", "-b", "main")
        (self.auteur / "install.sh").write_text("#!/bin/sh\necho installé\n"); (self.auteur / "install.sh").chmod(0o755)
        self.commit(self.auteur, "Départ")
        self.commit(self.auteur, "Deuxième changement")
        self.git("-C", str(self.auteur), "push", "-q", "origin", "main")
        self.ami = self.d / "ami"
        self.git("clone", "-q", str(self.amont), str(self.ami))
        (self.home / ".config/nc/depot").write_text(str(self.ami))

    def git(self, *a):
        return subprocess.run(["git", *a], env=self.env, capture_output=True, text=True, check=True).stdout.strip()

    def commit(self, depot, sujet):
        (depot / "fichier").write_text(sujet)
        self.git("-C", str(depot), "add", "-A")
        self.git("-C", str(depot), "commit", "-q", "-m", sujet)

    def reecrire_en_amont(self, nouveaute=True):
        if nouveaute:
            self.commit(self.auteur, "Nouveauté après le pseudo")
        self.git("-C", str(self.auteur), "filter-branch", "-f", "--env-filter",
                 "export GIT_AUTHOR_NAME=pseudo GIT_AUTHOR_EMAIL=pseudo@users.noreply.github.com "
                 "GIT_COMMITTER_NAME=pseudo GIT_COMMITTER_EMAIL=pseudo@users.noreply.github.com", "--", "main")
        self.git("-C", str(self.auteur), "push", "-q", "-f", "origin", "main")

    def nc_maj(self, *a):
        return subprocess.run(["bash", str(NC_MAJ), *a], env=self.env, capture_output=True, text=True, timeout=60)

    def test_historique_reecrit_repris_avec_sauvegarde(self):
        avant = self.git("-C", str(self.ami), "rev-parse", "HEAD")
        self.reecrire_en_amont()
        r = self.nc_maj("--no-system")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.git("-C", str(self.ami), "rev-parse", "HEAD"), self.git("-C", str(self.amont), "rev-parse", "main"))
        self.assertEqual(self.git("-C", str(self.ami), "log", "-1", "--format=%an"), "pseudo")
        sauvegardes = self.git("-C", str(self.ami), "branch", "--list", "nc-sauvegarde-*")
        self.assertTrue(sauvegardes, "l'ancienne version est gardée")
        self.assertEqual(self.git("-C", str(self.ami), "rev-parse", sauvegardes.strip(" *")), avant)
        self.assertIn("• Nouveauté après le pseudo", r.stdout)
        self.assertNotIn("Deuxième changement", r.stdout, "seulement les vraies nouveautés")
        self.assertIn("historique du dépôt réorganisé", r.stdout)
        self.assertIn("installé", r.stdout)

    def test_commits_a_toi_jamais_touches(self):
        self.commit(self.ami, "Mon changement à moi")
        mien = self.git("-C", str(self.ami), "rev-parse", "HEAD")
        self.reecrire_en_amont()
        r = self.nc_maj("--no-system")
        self.assertEqual(r.returncode, 1)
        self.assertIn("commits à toi", r.stderr)
        self.assertEqual(self.git("-C", str(self.ami), "rev-parse", "HEAD"), mien)

    def test_sans_reecriture_comme_avant(self):
        self.commit(self.auteur, "Simple nouveauté")
        self.git("-C", str(self.auteur), "push", "-q", "origin", "main")
        r = self.nc_maj("--no-system")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("• Simple nouveauté", r.stdout)
        self.assertNotIn("réorganisé", r.stdout)
        self.assertEqual(self.git("-C", str(self.ami), "branch", "--list", "nc-sauvegarde-*"), "")
        self.assertIn("Déjà à jour", self.nc_maj("--no-system").stdout)

    def test_verifier_n_annonce_que_les_nouveautes(self):
        faux = self.d / "faux"; faux.mkdir()
        (faux / "notify-send").write_text('#!/bin/sh\necho "$*" >> "$HOME/notifs"\n'); (faux / "notify-send").chmod(0o755)
        self.env["PATH"] = f"{faux}:/usr/bin:/bin"
        self.reecrire_en_amont(nouveaute=False)          # seulement l'historique : mêmes fichiers, rien à annoncer
        self.assertEqual(self.nc_maj("verifier").returncode, 0)
        self.assertFalse((self.home / "notifs").exists())
        self.commit(self.auteur, "Vraie nouveauté")
        self.git("-C", str(self.auteur), "push", "-q", "origin", "main")
        self.nc_maj("verifier")
        notifs = (self.home / "notifs").read_text()
        self.assertIn("Vraie nouveauté", notifs)
        self.assertNotIn("Deuxième changement", notifs)


if __name__ == "__main__":
    unittest.main()

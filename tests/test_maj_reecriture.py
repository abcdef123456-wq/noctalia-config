"""nc-maj suit un historique réécrit en amont (auteurs changés, mêmes changements) : la mise à jour reprend la nouvelle
version, garde l'ancienne dans une branche de sauvegarde et ne montre que les vraies nouveautés ; avec des commits à
toi, rien n'est touché ; un fichier non suivi à toi n'est jamais écrasé ; après un install.sh resté à moitié, la
relance reprend depuis la dernière version installée ; GitHub injoignable : une phrase, code 2. Vrais dépôts git dans
un dossier temporaire (HOME et XDG_* compris)."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
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

    def ajouter(self, depot, chemin, contenu, sujet):
        (depot / chemin).write_text(contenu)
        self.git("-C", str(depot), "add", "-A")
        self.git("-C", str(depot), "commit", "-q", "-m", sujet)

    def test_fichier_non_suivi_jamais_ecrase_par_la_reecriture(self):
        """M1 : git reset --hard écrasait sans un mot un fichier non suivi au chemin d'un fichier apporté par l'amont."""
        self.ajouter(self.auteur, "notes.txt", "version de l'amont\n", "Notes de l'amont")
        self.reecrire_en_amont(nouveaute=False)
        avant = self.git("-C", str(self.ami), "rev-parse", "HEAD")
        (self.ami / "notes.txt").write_text("MES NOTES\n")
        r = self.nc_maj("--no-system")
        self.assertNotEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual((self.ami / "notes.txt").read_text(), "MES NOTES\n")
        self.assertIn("notes.txt", r.stderr)
        self.assertIn("écraserait", r.stderr)
        self.assertEqual(self.git("-C", str(self.ami), "rev-parse", "HEAD"), avant)
        self.assertNotIn("installé", r.stdout)

    def test_fichier_non_suivi_avance_rapide_message_clair(self):
        self.ajouter(self.auteur, "notes.txt", "version de l'amont\n", "Notes de l'amont")
        self.git("-C", str(self.auteur), "push", "-q", "origin", "main")
        (self.ami / "notes.txt").write_text("MES NOTES\n")
        r = self.nc_maj("--no-system")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertEqual((self.ami / "notes.txt").read_text(), "MES NOTES\n")
        self.assertIn("écraserait", r.stderr)

    def test_reecriture_deja_recuperee_par_un_fetch(self):
        """M2 : un git pull ou un éditeur a récupéré la réécriture avant nc-maj ; l'amont d'avant ce fetch est déjà le
        nouveau : ce n'était pas des « commits à toi »."""
        avant = self.git("-C", str(self.ami), "rev-parse", "HEAD")
        self.reecrire_en_amont()
        self.git("-C", str(self.ami), "fetch", "-q", "origin")
        r = self.nc_maj("--no-system")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertNotIn("commits à toi", r.stderr)
        self.assertEqual(self.git("-C", str(self.ami), "rev-parse", "HEAD"), self.git("-C", str(self.amont), "rev-parse", "main"))
        sauvegardes = self.git("-C", str(self.ami), "branch", "--list", "nc-sauvegarde-*")
        self.assertEqual(self.git("-C", str(self.ami), "rev-parse", sauvegardes.strip(" *")), avant)
        self.assertIn("• Nouveauté après le pseudo", r.stdout)

    def test_commits_a_toi_apres_un_fetch_toujours_gardes(self):
        self.commit(self.ami, "Mon changement à moi")
        mien = self.git("-C", str(self.ami), "rev-parse", "HEAD")
        self.reecrire_en_amont()
        self.git("-C", str(self.ami), "fetch", "-q", "origin")
        r = self.nc_maj("--no-system")
        self.assertEqual(r.returncode, 1)
        self.assertIn("commits à toi", r.stderr)
        self.assertEqual(self.git("-C", str(self.ami), "rev-parse", "HEAD"), mien)

    def test_install_a_moitie_puis_relance(self):
        """M3 : install.sh échoue à moitié (HEAD a déjà avancé) ; la relance montre encore les nouveautés, relance
        l'installation et le rapport, et nc-maj verifier annonce toujours la version pas installée."""
        # Comme le vrai install.sh : la version n'est notée que s'il va jusqu'au bout
        (self.auteur / "install.sh").write_text(
            '#!/bin/sh\necho "étape 1"\n[ -e "$HOME/casse" ] && { echo "étape 2 : échec" >&2; exit 3; }\n'
            'git -C "$(dirname "$0")" rev-parse HEAD > "$HOME/.config/nc/version-installee"\necho installé\n')
        self.commit(self.auteur, "Installation qui note sa version")
        self.git("-C", str(self.auteur), "push", "-q", "origin", "main")
        self.assertEqual(self.nc_maj("--no-system").returncode, 0)
        installee = self.home / ".config/nc/version-installee"
        base = installee.read_text().strip()
        self.commit(self.auteur, "Changement important")
        self.git("-C", str(self.auteur), "push", "-q", "origin", "main")
        (self.home / "casse").touch()
        r = self.nc_maj("--no-system")
        self.assertEqual(r.returncode, 3, r.stdout + r.stderr)
        self.assertEqual(installee.read_text().strip(), base, "pas notée après un échec")
        # nc-maj verifier : la version publiée est déjà là (HEAD), mais pas installée : annoncée
        faux = self.d / "faux"; faux.mkdir()
        (faux / "notify-send").write_text('#!/bin/sh\necho "$*" >> "$HOME/notifs"\n'); (faux / "notify-send").chmod(0o755)
        env_verif = dict(self.env, PATH=f"{faux}:{self.env['PATH']}")
        subprocess.run(["bash", str(NC_MAJ), "verifier"], env=env_verif, capture_output=True, text=True, timeout=60)
        self.assertIn("Changement important", (self.home / "notifs").read_text())
        # La relance : nouveautés, installation, rapport de l'IA sur base..HEAD
        (self.home / "casse").unlink()
        ia = self.home / ".local/bin/nc-ia"; ia.parent.mkdir(parents=True)
        ia.write_text('#!/bin/sh\necho "$*" > "$HOME/rapport"\n'); ia.chmod(0o755)
        r = self.nc_maj("--no-system")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertNotIn("Déjà à jour", r.stdout)
        self.assertIn("• Changement important", r.stdout)
        self.assertNotIn("Installation qui note sa version", r.stdout)
        self.assertIn("installé", r.stdout)
        head = self.git("-C", str(self.ami), "rev-parse", "HEAD")
        self.assertEqual(installee.read_text().strip(), head)
        rapport = self.home / "rapport"
        for _ in range(100):
            if rapport.exists() and rapport.read_text():
                break
            time.sleep(0.05)
        self.assertEqual(rapport.read_text().split(), ["rapport-maj", "config", base, head])
        self.assertIn("Déjà à jour", self.nc_maj("--no-system").stdout)

    def test_version_installee_notee_par_install_sh_seulement_au_bout(self):
        texte = (REPO / "install.sh").read_text()
        self.assertIn('git -C "$REPO" rev-parse HEAD > "$HOME/.config/nc/version-installee"', texte)
        self.assertEqual(texte.count("noter_version"), 3, "définie, puis appelée aux deux « Terminé »")
        self.assertIn('{ noter_version; say "$(t "Terminé (fichiers seulement).', texte)
        self.assertIn('noter_version\nsay "$(t "Terminé" "Done")"', texte)

    def test_fetch_injoignable_message_et_delai(self):
        """M4 : fetch sans délai et erreur brute de git ; maintenant 120 s au plus, une phrase, code 2."""
        faux = self.d / "faux-timeout"; faux.mkdir()
        vrai = shutil.which("timeout")
        (faux / "timeout").write_text(f'#!/bin/sh\necho "$*" >> "$HOME/timeout"\nexec {vrai} "$@"\n')
        (faux / "timeout").chmod(0o755)
        self.env["PATH"] = f"{faux}:{self.env['PATH']}"
        self.git("-C", str(self.ami), "remote", "set-url", "origin", str(self.d / "nulle-part.git"))
        avant = self.git("-C", str(self.ami), "rev-parse", "HEAD")
        r = self.nc_maj("--no-system")
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("GitHub injoignable", r.stderr)
        self.assertNotIn("fatal", r.stderr)
        self.assertIn("120 git fetch -q origin main", (self.home / "timeout").read_text())
        self.assertEqual(self.git("-C", str(self.ami), "rev-parse", "HEAD"), avant)


if __name__ == "__main__":
    unittest.main()

"""nc-maj suit un historique réécrit en amont (auteurs changés, mêmes changements) : la mise à jour reprend la nouvelle
version, garde l'ancienne dans une branche de sauvegarde et ne montre que les vraies nouveautés ; avec des commits à
toi, rien n'est touché ; un fichier non suivi à toi n'est jamais écrasé ; après un install.sh resté à moitié, la
relance reprend depuis la dernière version installée ; GitHub injoignable : une phrase, code 2, sans délai fixe (ssh
peut poser sa question) ; git cherry lu sans tube (SIGPIPE) ; un fichier non suivi identique ne bloque pas ; marqueur
d'installation en cours ; un « non » à « On y va ? » n'est pas une réussite. Vrais dépôts git dans un dossier
temporaire (HOME et XDG_* compris), jamais le vrai ~/.config/nc/depot."""
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
        for v in ("HYPRLAND_INSTANCE_SIGNATURE", "GIT_SSH_COMMAND", "GIT_SSH", "GIT_CONFIG_GLOBAL", "GIT_CONFIG_SYSTEM"):
            self.env.pop(v, None)
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
        # Comme le vrai install.sh : la version n'est notée (et le marqueur d'installation en cours effacé) que s'il va
        # jusqu'au bout
        (self.auteur / "install.sh").write_text(
            '#!/bin/sh\necho "étape 1"\n[ -e "$HOME/casse" ] && { echo "étape 2 : échec" >&2; exit 3; }\n'
            'git -C "$(dirname "$0")" rev-parse HEAD > "$HOME/.config/nc/version-installee"\n'
            'rm -f "$HOME/.config/nc/installation-en-cours"\necho installé\n')
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

    def faux_git(self, cherry_en_echec=False):
        """Un git témoin devant le vrai : note chaque fetch (avec GIT_SSH_COMMAND), peut faire échouer git cherry."""
        faux = self.d / "faux-git"; faux.mkdir(exist_ok=True)
        vrai = shutil.which("git")
        (faux / "git").write_text(
            '#!/bin/sh\nfor a; do [ "$a" = fetch ] && echo "ssh=[${GIT_SSH_COMMAND:-}] $*" >> "$HOME/fetchs"; done\n'
            + ('for a; do [ "$a" = cherry ] && { echo "fatal: cherry simulé" >&2; exit 128; }; done\n'
               if cherry_en_echec else "") + f'exec {vrai} "$@"\n')
        (faux / "git").chmod(0o755)
        (faux / "timeout").write_text(f'#!/bin/sh\necho "$*" >> "$HOME/timeout"\nexec {shutil.which("timeout")} "$@"\n')
        (faux / "timeout").chmod(0o755)
        self.env["PATH"] = f"{faux}:{self.env['PATH']}"

    def test_fetch_injoignable_message_sans_delai_fixe(self):
        """P2-M2 / P3-M3 : plus de timeout 120 (il coupait un fetch lent et empêchait ssh ou HTTPS de poser une
        question) ; seul un réseau bloqué est coupé (options de ssh et d'HTTPS) ; une phrase, la dernière ligne de
        l'erreur de git, code 2."""
        self.faux_git()
        nulle_part = str(self.d / "nulle-part.git")
        self.git("-C", str(self.ami), "remote", "set-url", "origin", nulle_part)
        attendu = subprocess.run(["git", "-C", str(self.ami), "fetch", "-q", "origin", "main"], env=self.env,
                                 capture_output=True, text=True).stderr.strip().splitlines()[-1]
        (self.home / "fetchs").unlink()
        avant = self.git("-C", str(self.ami), "rev-parse", "HEAD")
        r = self.nc_maj("--no-system")
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("GitHub injoignable", r.stderr)
        self.assertIn(f"(git : {attendu})", r.stderr)
        self.assertEqual(self.git("-C", str(self.ami), "rev-parse", "HEAD"), avant)
        self.assertFalse((self.home / "timeout").exists(), "aucun délai fixe autour du fetch")
        fetch = (self.home / "fetchs").read_text()
        self.assertIn("-c http.lowSpeedLimit=1000 -c http.lowSpeedTime=60 fetch -q origin main", fetch)
        for o in ("ConnectTimeout=20", "ServerAliveInterval=15", "ServerAliveCountMax=4"):
            self.assertIn(o, fetch)

    def test_fetch_garde_la_commande_ssh_de_l_utilisateur(self):
        self.faux_git()
        r = self.nc_maj("--no-system")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("ConnectTimeout=20", (self.home / "fetchs").read_text())
        (self.home / "fetchs").unlink()
        r = subprocess.run(["bash", str(NC_MAJ), "--no-system"], env=dict(self.env, GIT_SSH_COMMAND="mon-ssh -v"),
                           capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("ssh=[mon-ssh -v]", (self.home / "fetchs").read_text())
        (self.home / "fetchs").unlink()
        self.git("-C", str(self.ami), "config", "core.sshCommand", "mon-ssh")
        r = self.nc_maj("--no-system")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("ssh=[]", (self.home / "fetchs").read_text(), "core.sshCommand n'est pas écrasé")

    @unittest.skipUnless(shutil.which("script"), "script (util-linux) absent")
    def test_fetch_peut_poser_une_question_dans_le_terminal(self):
        """P2-M2 : sous timeout (sans --foreground), git et ssh n'étaient plus au premier plan du terminal : la
        question de ssh (phrase de passe, empreinte) les arrêtait (SIGTTIN). Un faux ssh qui lit une réponse sur
        /dev/tty puis sert le dépôt en local, dans un pseudo-terminal (script) : la réponse est lue, la mise à jour
        passe."""
        self.commit(self.auteur, "Nouveauté par ssh")
        self.git("-C", str(self.auteur), "push", "-q", "origin", "main")
        ssh = self.d / "faux-ssh"
        ssh.write_text('#!/bin/sh\n[ "$1" = -G ] && exit 1\nprintf "Phrase de passe : " > /dev/tty\n'
                       'read r < /dev/tty\necho "$r" > "$HOME/lu"\nfor a; do c="$a"; done\nexec sh -c "$c"\n')
        ssh.chmod(0o755)
        self.git("-C", str(self.ami), "config", "core.sshCommand", str(ssh))
        self.git("-C", str(self.ami), "config", "ssh.variant", "simple")
        self.git("-C", str(self.ami), "remote", "set-url", "origin", f"fauxhote:{self.amont}")
        try:
            r = subprocess.run(["script", "-qec", f"bash {NC_MAJ} --no-system", "/dev/null"], input="ma-phrase\n",
                               env=dict(self.env, SHELL="/bin/sh", GIT_PAGER="cat"), capture_output=True, text=True,
                               timeout=30)
        except subprocess.TimeoutExpired:
            self.fail("la question de ssh n'a pas pu être lue (fetch arrêté hors du premier plan)")
        self.assertEqual((self.home / "lu").read_text().strip(), "ma-phrase", r.stdout + r.stderr)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("• Nouveauté par ssh", r.stdout)
        self.assertEqual(self.git("-C", str(self.ami), "rev-parse", "HEAD"), self.git("-C", str(self.amont), "rev-parse", "main"))

    def beaucoup_de_commits(self, n):
        """n commits chez l'auteur d'un coup (git fast-import), poussés."""
        tete = self.git("-C", str(self.auteur), "rev-parse", "main")
        t0 = int(time.time()) + 60
        flux = []
        for i in range(n):
            msg = f"c{i}".encode(); contenu = f"{i}\n".encode()
            flux.append(b"commit refs/heads/main\n")
            flux.append(f"committer Ancien Nom <ancien@exemple.invalid> {t0 + i} +0000\n".encode())
            flux.append(b"data %d\n%s\n" % (len(msg), msg))
            if i == 0:
                flux.append(f"from {tete}\n".encode())
            flux.append(b"M 100644 inline f%d\ndata %d\n%s\n" % (i % 7, len(contenu), contenu))
        subprocess.run(["git", "-C", str(self.auteur), "fast-import", "--quiet"], input=b"".join(flux), env=self.env,
                       check=True, capture_output=True)
        self.git("-C", str(self.auteur), "reset", "-q", "--hard", "main")
        self.git("-C", str(self.auteur), "push", "-q", "origin", "main")

    def reecrire_vite(self):
        """La réécriture d'auteurs de reecrire_en_amont, par fast-export / fast-import (filter-branch est trop lent
        pour des milliers de commits)."""
        flux = subprocess.run(["git", "-C", str(self.auteur), "fast-export", "main"], env=self.env, check=True,
                              capture_output=True).stdout
        flux = flux.replace(b"Ancien Nom <ancien@exemple.invalid>", b"pseudo <pseudo@users.noreply.github.com>")
        subprocess.run(["git", "-C", str(self.auteur), "fast-import", "--quiet", "--force"], input=flux, env=self.env,
                       check=True, capture_output=True)
        self.git("-C", str(self.auteur), "reset", "-q", "--hard", "main")
        self.git("-C", str(self.auteur), "push", "-q", "-f", "origin", "main")

    def test_commit_a_toi_apres_une_grosse_fusion_garde(self):
        """P2-M1 : git cherry | grep -q '^+' rendait 141 (SIGPIPE, pipefail) quand le « + » n'était pas en dernier,
        après une fusion de beaucoup de commits ; le « ! » y voyait « aucun commit à toi » : reset --hard."""
        (self.ami / "mien.txt").write_text("mien\n")
        self.git("-C", str(self.ami), "add", "mien.txt")
        self.git("-C", str(self.ami), "commit", "-q", "-m", "Mon commit à moi")
        mien = self.git("-C", str(self.ami), "rev-parse", "HEAD")
        self.beaucoup_de_commits(4000)
        self.git("-C", str(self.ami), "pull", "-q", "--no-rebase", "--no-edit", "origin", "main")
        fusion = self.git("-C", str(self.ami), "rev-parse", "HEAD")
        self.reecrire_vite()
        self.git("-C", str(self.ami), "fetch", "-q", "origin")
        lignes = self.git("-C", str(self.ami), "cherry", "origin/main", "HEAD").splitlines()
        self.assertGreater(len(lignes) - 1 - [l[0] for l in lignes].index("+"), 2000, "le « + » loin de la fin")
        r = self.nc_maj("--no-system")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("commits à toi", r.stderr)
        self.assertEqual(self.git("-C", str(self.ami), "rev-parse", "HEAD"), fusion)
        self.git("-C", str(self.ami), "merge-base", "--is-ancestor", mien, "HEAD")
        self.assertEqual(self.git("-C", str(self.ami), "branch", "--list", "nc-sauvegarde-*"), "")

    def test_git_cherry_en_echec_refus(self):
        """P2-M1 : un git cherry en échec ne prouve pas « aucun commit à toi »."""
        self.commit(self.ami, "Mon changement à moi")
        mien = self.git("-C", str(self.ami), "rev-parse", "HEAD")
        self.reecrire_en_amont()
        self.git("-C", str(self.ami), "fetch", "-q", "origin")
        self.faux_git(cherry_en_echec=True)
        r = self.nc_maj("--no-system")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("commits à toi", r.stderr)
        self.assertEqual(self.git("-C", str(self.ami), "rev-parse", "HEAD"), mien)

    def test_fichier_non_suivi_identique_ne_bloque_pas(self):
        """P3-M4 : un fichier non suivi identique à celui que l'amont apporte (rien à perdre) ne bloque plus."""
        (self.ami / "docs").mkdir()
        (self.ami / "docs/perso.md").write_text("perso\n")
        (self.auteur / "docs").mkdir()
        self.ajouter(self.auteur, "docs/perso.md", "perso\n", "Le même fichier, publié")
        self.git("-C", str(self.auteur), "push", "-q", "origin", "main")
        r = self.nc_maj("--no-system")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.git("-C", str(self.ami), "rev-parse", "HEAD"), self.git("-C", str(self.amont), "rev-parse", "main"))
        self.assertEqual((self.ami / "docs/perso.md").read_text(), "perso\n")
        self.assertEqual(self.git("-C", str(self.ami), "status", "--porcelain"), "")

    def test_fichier_ignore_que_l_amont_suit_message_clair(self):
        """P3-M4 : un fichier ignoré ici (git status ne le montre pas) que l'amont se met à suivre : le message le dit."""
        (self.ami / ".git/info/exclude").write_text("secrets/\n")
        (self.ami / "secrets").mkdir()
        (self.ami / "secrets/cle").write_text("à moi\n")
        (self.ami / "autre.txt").write_text("à moi aussi\n")
        (self.auteur / "secrets").mkdir()
        self.ajouter(self.auteur, "secrets/cle", "de l'amont\n", "Suivi d'un fichier que tu ignorais")
        self.ajouter(self.auteur, "autre.txt", "de l'amont\n", "Un autre fichier")
        self.git("-C", str(self.auteur), "push", "-q", "origin", "main")
        avant = self.git("-C", str(self.ami), "rev-parse", "HEAD")
        r = self.nc_maj("--no-system")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        lignes = r.stderr.splitlines()
        cle = [l for l in lignes if "secrets/cle" in l]
        self.assertEqual(len(cle), 1, r.stderr)
        self.assertIn("ignoré par git ici, mais la mise à jour se met à le suivre", cle[0])
        autre = [l for l in lignes if "autre.txt" in l]
        self.assertEqual(len(autre), 1, r.stderr)
        self.assertNotIn("ignoré", autre[0])
        self.assertEqual((self.ami / "secrets/cle").read_text(), "à moi\n")
        self.assertEqual(self.git("-C", str(self.ami), "rev-parse", "HEAD"), avant)

    def faux_notify(self):
        faux = self.d / "faux-notify"; faux.mkdir(exist_ok=True)
        (faux / "notify-send").write_text('#!/bin/sh\necho "$*" >> "$HOME/notifs"\n'); (faux / "notify-send").chmod(0o755)
        self.env["PATH"] = f"{faux}:{self.env['PATH']}"

    def test_mainteneur_pas_prevenu_de_ses_propres_versions(self):
        """P3-M5 : qui pousse ses commits et copie les fichiers à la main (sans install.sh) a une version-installee
        ancienne ; sans installation lancée par nc-maj restée en route, verifier part de HEAD : aucune annonce."""
        self.faux_notify()
        installee = self.home / ".config/nc/version-installee"
        installee.write_text(self.git("-C", str(self.auteur), "rev-parse", "HEAD") + "\n")
        (self.home / ".config/nc/depot").write_text(str(self.auteur))
        for k in range(3):
            self.commit(self.auteur, f"Mon travail {k}")
            self.git("-C", str(self.auteur), "push", "-q", "origin", "main")
            self.assertEqual(self.nc_maj("verifier").returncode, 0)
        self.assertFalse((self.home / "notifs").exists(), "pas d'annonce de ses propres pushs")
        # Une installation lancée par nc-maj restée en route : la base redevient version-installee
        (self.home / ".config/nc/installation-en-cours").write_text("x\n")
        self.nc_maj("verifier")
        self.assertIn("Mon travail", (self.home / "notifs").read_text())

    def test_nc_maj_marque_l_installation_en_cours(self):
        """P3-M5 : nc-maj écrit le marqueur (= la version qu'il installe) juste avant ./install.sh."""
        (self.auteur / "install.sh").write_text('#!/bin/sh\ncat "$HOME/.config/nc/installation-en-cours" > "$HOME/vu"\n')
        self.commit(self.auteur, "Installation témoin")
        self.git("-C", str(self.auteur), "push", "-q", "origin", "main")
        r = self.nc_maj("--no-system")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual((self.home / "vu").read_text().strip(), self.git("-C", str(self.ami), "rev-parse", "HEAD"))

    def test_install_sh_efface_le_marqueur_au_bout(self):
        """P3-M5 : noter_version (appelée seulement aux deux « Terminé » d'install.sh) efface le marqueur."""
        import re
        texte = (REPO / "install.sh").read_text()
        m = re.search(r"^noter_version\(\) \{\n.*?^\}\n", texte, re.M | re.S)
        self.assertIsNotNone(m, "noter_version introuvable dans install.sh")
        marqueur = self.home / ".config/nc/installation-en-cours"
        marqueur.write_text("x\n")
        r = subprocess.run(["bash", "-c", m.group(0) + "noter_version"], env=dict(self.env, REPO=str(self.ami)),
                           capture_output=True, text=True, timeout=30)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertFalse(marqueur.exists())
        self.assertEqual((self.home / ".config/nc/version-installee").read_text().strip(),
                         self.git("-C", str(self.ami), "rev-parse", "HEAD"))

    def test_nc_reglages_meme_base_que_verifier(self):
        """P3-M6 : maj_disponible() de nc-reglages comparait toujours l'annonce à HEAD ; même base que verifier."""
        import importlib.machinery, importlib.util, warnings
        from unittest import mock
        ancienne = self.git("-C", str(self.ami), "rev-parse", "HEAD~1")
        head = self.git("-C", str(self.ami), "rev-parse", "HEAD")
        (self.home / ".cache/nc").mkdir(parents=True)
        (self.home / ".cache/nc/maj-annoncee").write_text(head + "\n")
        (self.home / ".config/nc/version-installee").write_text(ancienne + "\n")
        with mock.patch.dict(os.environ, self.env), warnings.catch_warnings():
            warnings.simplefilter("ignore", ResourceWarning)
            chargeur = importlib.machinery.SourceFileLoader("nc_reglages_maj", str(REPO / "home/.local/bin/nc-reglages"))
            m = importlib.util.module_from_spec(importlib.util.spec_from_loader(chargeur.name, chargeur))
            chargeur.exec_module(m)
            m.HOME = str(self.home)
            self.assertFalse(m.maj_disponible(), "sans marqueur : HEAD, la version annoncée y est")
            (self.home / ".config/nc/installation-en-cours").write_text(head + "\n")
            self.assertTrue(m.maj_disponible(), "installation restée en route : pas encore installée")
            (self.home / ".config/nc/version-installee").write_text(head + "\n")
            self.assertFalse(m.maj_disponible())

    def test_non_a_on_y_va_ni_rapport_ni_bilan(self):
        """P3-M7 : un « non » à « On y va ? » sortait en 0, pris pour une réussite (rapport de l'IA, nc-diag)."""
        texte = (REPO / "install.sh").read_text()
        self.assertIn("\nANNULE=10\n", texte)
        self.assertIn('ask "$(t "On y va ?" "Ready to go?")" o || exit "$ANNULE"', texte)
        (self.auteur / "install.sh").write_text('#!/bin/sh\necho "On y va ? non"\nexit 10\n')
        self.commit(self.auteur, "Changement refusé")
        self.git("-C", str(self.auteur), "push", "-q", "origin", "main")
        bin_ = self.home / ".local/bin"; bin_.mkdir(parents=True)
        for nom in ("nc-ia", "nc-diag"):
            (bin_ / nom).write_text(f'#!/bin/sh\necho {nom} >> "$HOME/appels"\n'); (bin_ / nom).chmod(0o755)
        r = subprocess.run(["bash", str(NC_MAJ), "--no-system"], env=dict(self.env, HYPRLAND_INSTANCE_SIGNATURE="x"),
                           capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 10, r.stdout + r.stderr)
        self.assertIn("Installation annulée", r.stdout)
        time.sleep(0.3)
        self.assertFalse((self.home / "appels").exists(), "ni rapport ni bilan")
        self.assertTrue((self.home / ".config/nc/installation-en-cours").exists(), "pas installée : marqueur gardé")


if __name__ == "__main__":
    unittest.main()

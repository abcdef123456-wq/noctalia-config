"""Lot Maj-Écrans, partie nc-maj : amont forcé vers un commit plus ancien (demande avant le reset, rien sans terminal) ;
HEAD détaché ou branche locale sans homonyme sur GitHub (une phrase claire, jamais « GitHub injoignable » ni « Déjà à
jour ») ; « % » doublés pour systemd-run seulement ; notification avec « -- », terminal de nc-apps et chemin passé en
argument. Vrais dépôts git dans un dossier temporaire, faux systemd-run / notify-send / terminal, HOME isolé."""
import os
from pathlib import Path
import pty
import subprocess
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
NC_MAJ = REPO / "home/.local/bin/nc-maj"


class MajLot(unittest.TestCase):
    def setUp(self):
        d = tempfile.TemporaryDirectory(prefix="nc-maj-lot-")
        self.addCleanup(d.cleanup)
        self.d = Path(d.name)
        self.home = self.d / "ho me"                      # une espace : le chemin ne doit pas être recollé dans une commande
        (self.home / ".config/nc").mkdir(parents=True)
        self.faux = self.d / "faux"
        self.faux.mkdir()
        self.journal = self.d / "journal"
        self.env = dict(os.environ, HOME=str(self.home), XDG_CACHE_HOME=str(self.home / ".cache"),
                        XDG_CONFIG_HOME=str(self.home / ".config"), XDG_STATE_HOME=str(self.home / ".state"),
                        XDG_DATA_HOME=str(self.home / ".data"), XDG_RUNTIME_DIR=str(self.d), TMPDIR=str(self.d),
                        NC_LANGUE="fr", J=str(self.journal), PATH=f"{self.faux}:{os.environ['PATH']}",
                        GIT_AUTHOR_NAME="T", GIT_AUTHOR_EMAIL="t@exemple.invalid",
                        GIT_COMMITTER_NAME="T", GIT_COMMITTER_EMAIL="t@exemple.invalid")
        for v in ("HYPRLAND_INSTANCE_SIGNATURE", "GIT_SSH_COMMAND", "GIT_SSH", "GIT_CONFIG_GLOBAL", "GIT_CONFIG_SYSTEM",
                  "TERMINAL"):
            self.env.pop(v, None)
        self.amont, self.auteur, self.ami = self.d / "amont.git", self.d / "auteur", self.d / "ami"
        self.git("init", "-q", "--bare", "-b", "main", str(self.amont))
        self.git("clone", "-q", str(self.amont), str(self.auteur))
        self.git("-C", str(self.auteur), "checkout", "-q", "-b", "main")
        (self.auteur / "install.sh").write_text("#!/bin/sh\necho installé\n")
        (self.auteur / "install.sh").chmod(0o755)
        self.commit(self.auteur, "Départ")
        self.commit(self.auteur, "Deuxième")
        self.git("-C", str(self.auteur), "push", "-q", "origin", "main")
        self.git("clone", "-q", str(self.amont), str(self.ami))
        (self.home / ".config/nc/depot").write_text(str(self.ami))

    def script(self, nom, corps):
        p = self.faux / nom
        p.write_text("#!/bin/sh\n" + corps + "\n")
        p.chmod(0o755)

    def git(self, *a):
        return subprocess.run(["git", *a], env=self.env, capture_output=True, text=True, check=True).stdout.strip()

    def commit(self, depot, sujet):
        (depot / "fichier").write_text(sujet)
        self.git("-C", str(depot), "add", "fichier", "install.sh")
        self.git("-C", str(depot), "commit", "-q", "-m", sujet)

    def nc_maj(self, *a):
        return subprocess.run(["bash", str(NC_MAJ), *a], env=self.env, capture_output=True, text=True, timeout=60,
                              stdin=subprocess.DEVNULL)

    def lignes(self):
        return self.journal.read_text().splitlines() if self.journal.exists() else []

    def forcer_en_arriere(self):
        self.git("-C", str(self.auteur), "push", "-q", "-f", "origin", "HEAD~1:main")

    # --- 1. amont plus ancien ---
    def test_amont_plus_ancien_rien_sans_terminal(self):
        avant = self.git("-C", str(self.ami), "rev-parse", "HEAD")
        self.forcer_en_arriere()
        r = self.nc_maj("--no-system")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("plus ancienne ou réécrite", r.stderr)
        self.assertEqual(self.git("-C", str(self.ami), "rev-parse", "HEAD"), avant)
        self.assertEqual(self.git("-C", str(self.ami), "branch", "--list", "nc-sauvegarde-*"), "")
        self.assertNotIn("installé", r.stdout)

    def repondre(self, reponse):
        """nc-maj dans un vrai terminal (pty), qui reçoit la réponse à la question."""
        maitre, esclave = pty.openpty()
        p = subprocess.Popen(["bash", str(NC_MAJ), "--no-system"], env=self.env, stdin=esclave, stdout=esclave,
                             stderr=esclave, close_fds=True)
        os.close(esclave)
        os.write(maitre, reponse.encode())
        sortie = b""
        try:
            while True:
                morceau = os.read(maitre, 4096)
                if not morceau:
                    break
                sortie += morceau
        except OSError:
            pass
        os.close(maitre)
        return p.wait(timeout=60), sortie.decode(errors="replace")

    def test_amont_plus_ancien_non_au_terminal(self):
        avant = self.git("-C", str(self.ami), "rev-parse", "HEAD")
        self.forcer_en_arriere()
        code, sortie = self.repondre("n\n")
        self.assertEqual(code, 1, sortie)
        self.assertIn("plus ancienne ou réécrite", sortie)
        self.assertEqual(self.git("-C", str(self.ami), "rev-parse", "HEAD"), avant)

    def test_amont_plus_ancien_oui_au_terminal_garde_la_sauvegarde(self):
        avant = self.git("-C", str(self.ami), "rev-parse", "HEAD")
        self.forcer_en_arriere()
        code, sortie = self.repondre("o\n")
        self.assertEqual(code, 0, sortie)
        self.assertEqual(self.git("-C", str(self.ami), "rev-parse", "HEAD"), self.git("-C", str(self.amont), "rev-parse", "main"))
        sauvegarde = self.git("-C", str(self.ami), "branch", "--list", "nc-sauvegarde-*").strip(" *")
        self.assertEqual(self.git("-C", str(self.ami), "rev-parse", sauvegarde), avant)

    # --- 2. branche non suivie ---
    def test_tete_detachee(self):
        self.git("-C", str(self.ami), "checkout", "-q", "--detach")
        for args in (("--no-system",), ("verifier",)):
            r = self.nc_maj(*args)
            self.assertIn("pas sur une branche suivie", r.stderr, args)
            self.assertIn("git switch main", r.stderr)
            self.assertNotIn("injoignable", r.stderr)
            self.assertNotIn("Déjà à jour", r.stdout)
        self.assertEqual(self.nc_maj("--no-system").returncode, 1)

    def test_branche_locale_sans_homonyme(self):
        self.git("-C", str(self.ami), "checkout", "-q", "-b", "travail")
        r = self.nc_maj("--no-system")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("pas sur une branche suivie", r.stderr)
        self.assertNotIn("injoignable", r.stderr)
        v = self.nc_maj("verifier")
        self.assertEqual(v.returncode, 0)
        self.assertIn("pas sur une branche suivie", v.stderr)

    def test_branche_avec_amont_configure_suivie(self):
        """Une branche locale d'un autre nom mais qui suit origin/main (@{u}) se met à jour."""
        self.git("-C", str(self.ami), "checkout", "-q", "-b", "travail", "--track", "origin/main")
        self.commit(self.auteur, "Nouveauté")
        self.git("-C", str(self.auteur), "push", "-q", "origin", "main")
        r = self.nc_maj("--no-system")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("• Nouveauté", r.stdout)

    # --- 3. « % » pour systemd-run ---
    def test_pourcent_double_pour_systemd_run(self):
        self.script("notify-send", 'echo "notify-send $*" >> "$J"')
        self.script("systemd-run", 'for a in "$@"; do printf "ARG<%s>\\n" "$a"; done >> "$J"; exit 0')
        self.git("-C", str(self.ami), "reset", "-q", "--hard", "HEAD~1")
        self.commit(self.auteur, "Batterie à 58 % de mieux")
        self.git("-C", str(self.auteur), "push", "-q", "origin", "main")
        r = self.nc_maj("verifier")
        self.assertEqual(r.returncode, 0, r.stderr)
        args = [l for l in self.lignes() if l.startswith("ARG<")]
        texte = [a for a in args if "mieux" in a]
        self.assertEqual(len(texte), 1, args)
        self.assertIn("58 %% de mieux", texte[0], "systemd lit %x comme un spécificateur : il faut %%")

    # --- 7. notification : « -- », terminal de nc-apps, chemin en argument ---
    def test_annoncer_terminal_et_arguments(self):
        self.script("notify-send", 'echo "notify-send $*" >> "$J"; echo maj')
        self.script("xdg-terminal-exec", 'for a in "$@"; do printf "T<%s>\\n" "$a"; done >> "$J"')
        r = subprocess.run(["bash", str(NC_MAJ), "annoncer", "Du neuf"], env=self.env, capture_output=True, text=True, timeout=30)
        self.assertEqual(r.returncode, 0, r.stderr)
        j = self.lignes()
        self.assertTrue(any(l.startswith("notify-send ") and " -- " in l and "Du neuf" in l for l in j), j)
        t = [l for l in j if l.startswith("T<")]
        self.assertEqual(t[0], "T<sh>", t)
        self.assertEqual(t[1], "T<-c>")
        self.assertNotIn(str(self.home), t[2], "le chemin n'est pas recollé dans la commande")
        self.assertIn(f"T<{self.home}/.local/bin/nc-maj>", t)

    def test_install_previent_avant_de_relancer_la_barre(self):
        src = (REPO / "install.sh").read_text()
        i = src.index("La barre et l'île vont se relancer quelques secondes.")
        self.assertIn("The bar and the island will restart for a few seconds.", src[i:i + 300])
        self.assertLess(i, src.index("systemctl --user restart noctalia.service nc-profile-sync.service"))


if __name__ == "__main__":
    unittest.main()

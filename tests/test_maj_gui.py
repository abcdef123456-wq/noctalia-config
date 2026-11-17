"""Mise à jour graphique (lot IG2) : nc-installeur --maj lance nc-maj, nc-maj --graphique et la notification ouvrent
l'interface si possible. Aucun vrai nc-maj, aucun vrai install.sh, aucune fenêtre : faux programmes, HOME isolé,
dépôts git dans un dossier temporaire. Rien ne change dans os.environ : seulement des dicts env."""
import importlib.machinery
import importlib.util
import os
import pathlib
import shutil
import stat
import subprocess
import tempfile
import time
import unittest

REPO = pathlib.Path(__file__).resolve().parents[1]
NC_MAJ = REPO / "home/.local/bin/nc-maj"
_l = importlib.machinery.SourceFileLoader("nc_installeur_maj", str(REPO / "installeur/nc-installeur"))
M = importlib.util.module_from_spec(importlib.util.spec_from_loader("nc_installeur_maj", _l))
_l.exec_module(M)


def ecrire(p, corps):
    p = pathlib.Path(p)
    p.write_text("#!/bin/sh\n" + corps + "\n")
    p.chmod(stat.S_IRWXU)
    return p


class Session(unittest.TestCase):
    """Session(maj=True) contre un FAUX nc-maj désigné par NC_MAJ_SCRIPT."""

    def setUp(self):
        d = tempfile.TemporaryDirectory(prefix="nc-maj-gui-")
        self.addCleanup(d.cleanup)
        self.d = pathlib.Path(d.name)

    def lancer(self, corps, options=()):
        faux = ecrire(self.d / "nc-maj", corps)
        env = dict(os.environ, NC_MAJ_SCRIPT=str(faux), HOME=str(self.d), TMPDIR=str(self.d), J=str(self.d / "j"))
        evs, fin = [], []
        s = M.Session(options, evs.append, lambda l: None, lambda c, i: fin.append((c, i)), env, maj=True)
        s.demarrer()
        return s, evs, fin

    def test_lance_nc_maj_avec_les_fifo(self):
        s, evs, fin = self.lancer('echo "$NC_UI|$NC_UI_SORTIE|$NC_UI_ENTREE|$*" > "$J"\n'
                                  'echo \'{"type":"etape","n":1,"titre":"Salut"}\' >&3 2>/dev/null || '
                                  'echo \'{"type":"etape","n":1,"titre":"Salut"}\' >> "$NC_UI_SORTIE"', ["--fr"])
        self.assertTrue(s.termine.wait(15))
        ui, sortie, entree, args = (self.d / "j").read_text().strip().split("|")
        self.assertEqual(ui, "1")
        self.assertTrue(sortie and entree and sortie != entree)
        self.assertEqual(args, "--fr")
        self.assertEqual(fin[0][0], 0)
        self.assertEqual(evs[0]["titre"], "Salut")

    def test_evenement_de_install_sh_via_nc_maj(self):
        # le faux nc-maj lance un faux install.sh qui hérite de l'environnement, comme le vrai
        ecrire(self.d / "install.sh", 'echo \'{"type":"etape","n":2,"titre":"Depuis install"}\' >> "$NC_UI_SORTIE"')
        s, evs, fin = self.lancer('exec "%s/install.sh" "$@"' % self.d)
        self.assertTrue(s.termine.wait(15))
        self.assertEqual([e["titre"] for e in evs], ["Depuis install"])

    def test_code_2_github_injoignable(self):
        s, evs, fin = self.lancer("exit 2")
        self.assertTrue(s.termine.wait(15))
        self.assertEqual(fin[0][0], 2)
        ok, texte = M.message_fin(2, "fr", False, True)
        self.assertFalse(ok)
        self.assertIn("GitHub injoignable", texte)
        self.assertIn("introuvable", M.message_fin(1, "fr", False, True)[1])
        self.assertIn("annulée", M.message_fin(10, "fr", False, True)[1])
        self.assertTrue(M.message_fin(0, "fr", False, True)[0])

    def test_annuler_tue_le_groupe(self):
        s, evs, fin = self.lancer('echo $$ > "$J"; sleep 60 & echo $! >> "$J"; wait')
        for _ in range(100):
            if (self.d / "j").exists() and len((self.d / "j").read_text().split()) == 2:
                break
            time.sleep(0.1)
        s.annuler()
        self.assertTrue(s.termine.wait(10))
        self.assertTrue(fin and fin[0][0] != 0)
        _, sommeil = (self.d / "j").read_text().split()
        time.sleep(0.3)
        self.assertFalse(os.path.exists("/proc/%s" % sommeil) and
                         "sleep" in pathlib.Path("/proc/%s/cmdline" % sommeil).read_text())

    def test_chemin_maj(self):
        self.assertEqual(M.chemin_maj({"NC_MAJ_SCRIPT": "/x/y"}), "/x/y")
        cmd, env = M.construire_commande([], "/s", "/e", {"NC_MAJ_SCRIPT": "/x/y"}, maj=True)
        self.assertEqual(cmd[0], "/x/y")
        self.assertEqual(env["NC_UI"], "1")


class NcMaj(unittest.TestCase):
    """Le vrai nc-maj (bash) dans un dépôt de test, avec de faux python3, notify-send et terminal."""

    def setUp(self):
        d = tempfile.TemporaryDirectory(prefix="nc-maj-gui-")
        self.addCleanup(d.cleanup)
        self.d = pathlib.Path(d.name)
        self.home = self.d / "home"
        (self.home / ".config/nc").mkdir(parents=True)
        self.faux = self.d / "faux"
        self.faux.mkdir()
        self.j = self.d / "journal"
        reel = shutil.which("python3")
        # import gi : réussit si GI_OK=1 ; autre -c : le vrai python3 ; sinon on note les arguments
        ecrire(self.faux / "python3",
               'case "$1" in -c) case "$2" in "import gi"*) [ "$GI_OK" = 1 ]; exit $?;; esac; exec %s "$@";; esac\n'
               'echo "python3 $*" >> "$J"' % reel)
        ecrire(self.faux / "notify-send", "echo maj")
        ecrire(self.faux / "xdg-terminal-exec", 'echo "terminal $*" >> "$J"')
        ecrire(self.faux / "kitty", 'echo "terminal $*" >> "$J"')
        env = dict(os.environ, HOME=str(self.home), XDG_CACHE_HOME=str(self.home / ".cache"),
                   XDG_CONFIG_HOME=str(self.home / ".config"), NC_LANGUE="fr", J=str(self.j), GI_OK="1",
                   PATH=f"{self.faux}:{os.environ['PATH']}", GIT_AUTHOR_NAME="T", GIT_AUTHOR_EMAIL="t@exemple.invalid",
                   GIT_COMMITTER_NAME="T", GIT_COMMITTER_EMAIL="t@exemple.invalid")
        for v in ("HYPRLAND_INSTANCE_SIGNATURE", "GIT_SSH_COMMAND", "GIT_SSH", "GIT_CONFIG_GLOBAL", "GIT_CONFIG_SYSTEM",
                  "WAYLAND_DISPLAY", "DISPLAY", "TERMINAL"):
            env.pop(v, None)
        self.env = env
        amont, auteur, self.ami = self.d / "amont.git", self.d / "auteur", self.d / "ami"
        self.git("init", "-q", "--bare", "-b", "main", str(amont))
        self.git("clone", "-q", str(amont), str(auteur))
        self.git("-C", str(auteur), "checkout", "-q", "-b", "main")
        (auteur / "installeur").mkdir()
        ecrire(auteur / "installeur/nc-installeur", 'echo "installeur $*" >> "$J"')
        ecrire(auteur / "install.sh", 'echo "install $NC_UI|$NC_UI_SORTIE|$NC_UI_ENTREE|$*" >> "$J"')
        self.git("-C", str(auteur), "add", "installeur/nc-installeur", "install.sh")
        self.git("-C", str(auteur), "commit", "-q", "-m", "Départ")
        self.git("-C", str(auteur), "push", "-q", "origin", "main")
        self.git("clone", "-q", str(amont), str(self.ami))
        (self.home / ".config/nc/depot").write_text(str(self.ami))

    def git(self, *a):
        subprocess.run(["git", *a], env=self.env, check=True, capture_output=True)

    def nc_maj(self, *args, **sup):
        env = dict(self.env, **sup)
        return subprocess.run(["bash", str(NC_MAJ), *args], env=env, capture_output=True, text=True, timeout=60,
                              stdin=subprocess.DEVNULL)

    def journal(self):
        return self.j.read_text().splitlines() if self.j.exists() else []

    def test_graphique_sans_session_reste_au_terminal(self):
        r = self.nc_maj("--graphique", "--no-system")
        self.assertEqual([l for l in self.journal() if l.startswith("installeur")], [])
        self.assertEqual([l for l in self.journal() if l.startswith("install ")], ["install |||--no-system"])

    def test_graphique_avec_session_ouvre_l_installeur(self):
        r = self.nc_maj("--graphique", "--no-system", WAYLAND_DISPLAY="wayland-test")
        self.assertEqual(r.returncode, 0, r.stderr)
        j = self.journal()
        self.assertEqual(len(j), 1, j)
        self.assertTrue(j[0].startswith("python3 ") and j[0].endswith("installeur/nc-installeur --maj --no-system"), j)

    def test_graphique_sans_gtk_reste_au_terminal(self):
        self.nc_maj("--graphique", WAYLAND_DISPLAY="wayland-test", GI_OK="0")
        self.assertEqual(self.journal(), ["install |||"])

    def test_nc_maj_transmet_l_environnement_a_install_sh(self):
        self.nc_maj(NC_UI="1", NC_UI_SORTIE="/s", NC_UI_ENTREE="/e")
        self.assertEqual(self.journal(), ["install 1|/s|/e|"])

    def test_notification_avec_session_ouvre_l_interface(self):
        self.nc_maj("annoncer", "texte", WAYLAND_DISPLAY="wayland-test")
        j = self.journal()
        self.assertEqual(len(j), 1, j)
        self.assertTrue(j[0].endswith("installeur/nc-installeur --maj"), j)

    def test_notification_sans_session_ouvre_le_terminal(self):
        self.nc_maj("annoncer", "texte")
        j = self.journal()
        self.assertEqual(len(j), 1, j)
        self.assertTrue(j[0].startswith("terminal "), j)


if __name__ == "__main__":
    unittest.main()

"""get.sh : refus de root, git/sudo absents, origine étrangère, mise à jour qui échoue, NC_VERSION, script tronqué.

Rien de réel : faux id, sudo, git, apt-get, pacman… dans un dossier temporaire, faux HOME temporaire.
"""
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
GET = REPO / "get.sh"
DEPOT = "https://github.com/abcdef123456-wq/noctalia-config.git"
BASH = subprocess.run(["bash", "-c", "command -v bash"], capture_output=True, text=True).stdout.strip()
# Outils système de base dont get.sh a besoin, liés dans le faux PATH (jamais git, sudo ni un gestionnaire de paquets)
BASE = ["bash", "dirname", "cat", "env", "mkdir", "chmod", "rm"]


def outil(dossier, nom, corps):
    p = Path(dossier) / nom
    p.write_text("#!/usr/bin/env bash\n" + corps + "\n")
    p.chmod(p.stat().st_mode | stat.S_IEXEC)


class TestGet(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)
        self.bin = self.tmp / "bin"
        self.home = self.tmp / "home"
        self.bin.mkdir()
        self.home.mkdir()
        self.journal = self.tmp / "journal"
        self.journal.touch()
        for n in BASE:
            r = subprocess.run(["bash", "-c", f"command -v {n}"], capture_output=True, text=True).stdout.strip()
            if r.startswith("/"):
                (self.bin / n).symlink_to(r)
        outil(self.bin, "id", 'echo "${FAUX_UID:-1000}"')

    def faux_git(self, origine=DEPOT, echec=""):
        """git qui note ses arguments ; échoue pour les sous-commandes de `echec` (ex. « pull »)."""
        outil(self.bin, "git", f'''
echo "git $*" >> "{self.journal}"
case "$*" in
  *"remote get-url"*) echo "{origine}"; exit 0 ;;
esac
for m in {echec}; do case "$*" in *" $m"*) exit 1 ;; esac; done
if [ "$1" = clone ]; then
  d="${{@: -1}}"; mkdir -p "$d/.git"
  printf '#!/usr/bin/env bash\\necho INSTALL "$@" >> "{self.journal}"\\n' > "$d/install.sh"; chmod +x "$d/install.sh"
fi
exit 0''')

    def depot_existant(self):
        d = self.home / "noctalia-config"
        (d / ".git").mkdir(parents=True, exist_ok=True)
        outil(d, "install.sh", f'echo INSTALL "$@" >> "{self.journal}"')

    def lancer(self, args=(), env=None, script=None):
        e = {"PATH": str(self.bin), "HOME": str(self.home), "TMPDIR": str(self.tmp),
             "XDG_CONFIG_HOME": str(self.home / ".config"), "XDG_DATA_HOME": str(self.home / ".local/share"),
             "XDG_CACHE_HOME": str(self.home / ".cache"), "XDG_STATE_HOME": str(self.home / ".local/state")}
        e.update(env or {})
        cmd = [BASH, "-c", script, "x", *args] if script else [BASH, str(GET), *args]
        return subprocess.run(cmd, capture_output=True, text=True, stdin=subprocess.DEVNULL, env=e, timeout=30)

    def appels(self):
        return self.journal.read_text()

    def test_sans_sudo_ni_git(self):
        outil(self.bin, "apt-get", f'echo "apt-get $*" >> "{self.journal}"')
        r = self.lancer()
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("sudo est absent", r.stderr)
        self.assertIn("su -c 'apt install sudo git'", r.stderr)
        self.assertNotIn("command not found", r.stderr)
        self.assertNotIn("apt-get", self.appels())

    def test_installation_de_git_ratee(self):
        outil(self.bin, "sudo", 'exit 1')
        outil(self.bin, "pacman", 'exit 0')
        r = self.lancer()
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("a échoué", r.stderr)
        self.assertNotIn("command not found", r.stderr)

    def test_root_refuse(self):
        self.faux_git()
        r = self.lancer(env={"FAUX_UID": "0"})
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("root", r.stderr)
        self.assertEqual(self.appels(), "")

    def test_clone_et_options_transmises(self):
        self.faux_git()
        r = self.lancer(["--no-system"])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("git clone --depth 1 " + DEPOT, self.appels())
        self.assertIn("INSTALL --no-system", self.appels())

    def test_origine_etrangere_refusee(self):
        self.faux_git(origine="https://exemple.invalid/autre.git")
        self.depot_existant()
        r = self.lancer()
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("autre dépôt", r.stderr)
        self.assertNotIn("INSTALL", self.appels())
        self.assertNotIn("pull", self.appels())

    def test_meme_depot_en_ssh_accepte(self):
        for origine in ("git@github.com:abcdef123456-wq/noctalia-config.git",
                        "ssh://git@github.com/abcdef123456-wq/noctalia-config"):
            with self.subTest(origine):
                self.journal.write_text("")
                self.faux_git(origine=origine)
                self.depot_existant()
                r = self.lancer()
                self.assertEqual(r.returncode, 0, r.stderr)
                self.assertIn("pull --ff-only", self.appels())

    def test_head_detache_va_a_la_derniere_version(self):
        # Après NC_VERSION (HEAD détaché), une mise à jour sans NC_VERSION ne tente pas un « pull » impossible
        self.faux_git(echec="symbolic-ref")
        self.depot_existant()
        r = self.lancer()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("fetch --depth 1 origin HEAD", self.appels())
        self.assertIn("checkout -q FETCH_HEAD", self.appels())
        self.assertNotIn("pull", self.appels())

    def test_pull_rate_arrete(self):
        self.faux_git(echec="pull")
        self.depot_existant()
        r = self.lancer()
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("NC_GARDER=1", r.stderr)
        self.assertNotIn("INSTALL", self.appels())

    def test_pull_rate_avec_nc_garder(self):
        self.faux_git(echec="pull")
        self.depot_existant()
        r = self.lancer(["--files-only"], env={"NC_GARDER": "1"})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("INSTALL --files-only", self.appels())

    def test_nc_version_clone(self):
        self.faux_git()
        r = self.lancer(env={"NC_VERSION": "v1.2"})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("--branch v1.2", self.appels())

    def test_nc_version_depot_existant(self):
        self.faux_git()
        self.depot_existant()
        r = self.lancer(env={"NC_VERSION": "v1.2"})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("fetch --depth 1 origin v1.2", self.appels())
        self.assertIn("checkout -q FETCH_HEAD", self.appels())
        self.assertNotIn("pull", self.appels())

    def test_git_sans_invite(self):
        outil(self.bin, "git", f'echo "PROMPT=$GIT_TERMINAL_PROMPT" >> "{self.journal}"; d="${{@: -1}}"; mkdir -p "$d/.git"; '
              f'printf \'#!/usr/bin/env bash\\n\' > "$d/install.sh"; chmod +x "$d/install.sh"')
        self.lancer()
        self.assertIn("PROMPT=0", self.appels())

    def test_script_tronque_n_execute_rien(self):
        self.faux_git()
        lignes = GET.read_text().splitlines()
        self.assertEqual(lignes[-1], 'main "$@"')
        r = self.lancer(script="\n".join(lignes[:-1]) + "\n")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.appels(), "")
        self.assertFalse((self.home / "noctalia-config").exists())
        # coupé en pleine fonction : erreur de syntaxe, rien d'exécuté
        r = self.lancer(script="\n".join(lignes[:30]) + "\n")
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual(self.appels(), "")


if __name__ == "__main__":
    unittest.main()

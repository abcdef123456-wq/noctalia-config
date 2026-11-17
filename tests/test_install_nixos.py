"""install.sh sur NixOS : aucune étape du système, outils vérifiés avant la copie, unités réécrites.

Faux os-release, faux outils dans le PATH ; faux sudo, curl, wget, git, chsh et gestionnaires de
paquets qui notent leurs appels dans un journal : ils ne doivent jamais être lancés.
HOME et XDG_* pointent vers un dossier temporaire.
"""
import os
import pty
import re
import select
import time
import shutil
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUTILS = ["Hyprland", "hyprctl", "noctalia", "qs", "jq", "kitty", "uwsm"]
INTERDITS = ["sudo", "curl", "wget", "git", "chsh", "dnf", "apt-get", "pacman", "zypper"]
UNITES = ["noctalia.service", "nc-theme-sync.service", "nc-ile.service"]
BASE = ["python3", "bash", "sed", "find", "cmp", "awk", "timeout", "cat", "cp", "mv", "rm", "mkdir", "chmod",
        "dirname", "basename", "date", "env", "grep", "head", "tail", "tr", "sort", "uname", "id", "ln",
        "mktemp", "touch", "wc", "cut", "tee", "readlink", "stat", "diff", "ls", "printf", "sleep", "xargs",
        "install", "sh", "true", "false", "test", "uniq", "realpath", "whoami", "hostname", "sync", "df",
        "getent", "rmdir", "chown", "expr", "od", "base64", "sha256sum", "md5sum", "tar", "tput", "stty"]


def outil(dossier, nom, corps):
    p = Path(dossier) / nom
    p.write_text("#!/bin/sh\n" + corps + "\n")
    p.chmod(p.stat().st_mode | stat.S_IEXEC)


class Banc:
    """Un HOME, un PATH de faux outils et un os-release jetables."""

    def __init__(self, famille="nixos", absents=()):
        self.d = Path(tempfile.mkdtemp(prefix="nc-nixos-"))
        self.home = self.d / "home"
        self.bin = self.d / "bin"
        self.journal = self.d / "appels"
        self.home.mkdir()
        self.bin.mkdir()
        (self.d / "osr").write_text(f'ID={famille}\nNAME={famille}\nVERSION_ID="25.11"\n')
        for n in OUTILS:
            if n not in absents:
                outil(self.bin, n, 'case "$1" in --version) echo "Hyprland v0.55.1"; echo "Tag: v0.55.1";; esac')
        for n in INTERDITS:
            outil(self.bin, n, f'echo "{n} $*" >> "{self.journal}"; exit 1')
        outil(self.bin, "fc-match", 'echo "MaterialSymbolsRounded.ttf: Material Symbols Rounded"')
        for n in BASE:
            w = shutil.which(n)
            if w and not (self.bin / n).exists():
                (self.bin / n).symlink_to(w)

    def lance(self, *args, tty=None):
        """tty : réponse (« o ») tapée à chaque question dans un vrai terminal ; sinon aucun terminal."""
        env = self.env()
        cmd = ["bash", str(REPO / "install.sh"), *args]
        if tty is None:
            return subprocess.run(cmd, capture_output=True, text=True, stdin=subprocess.DEVNULL,
                                  start_new_session=True, env=env, timeout=120)
        pid, fd = pty.fork()
        if pid == 0:
            os.execvpe("bash", cmd, env)
        sortie = b""
        fin = time.monotonic() + 90
        while time.monotonic() < fin:
            if select.select([fd], [], [], 0.2)[0]:
                try:
                    bout = os.read(fd, 4096)
                except OSError:
                    break
                if not bout:
                    break
                sortie += bout
                if re.search(rb"\[[oOyY]/[nN]\] $", sortie):
                    rep = tty if re.search(rb"(Remplacer|Replace|On y va|Proceed)[^\n]*$", sortie.rsplit(b"\n", 1)[-1]) else "n"
                    os.write(fd, (rep + "\n").encode())
        else:
            os.kill(pid, 9)
        _, st = os.waitpid(pid, 0)
        os.close(fd)
        return subprocess.CompletedProcess(cmd, os.waitstatus_to_exitcode(st), sortie.decode(errors="replace"), "")

    def env(self):
        return {"HOME": str(self.home), "PATH": str(self.bin), "TMPDIR": str(self.d), "LANG": "C",
               "XDG_CONFIG_HOME": str(self.home / ".config"), "XDG_DATA_HOME": str(self.home / ".local/share"),
               "XDG_STATE_HOME": str(self.home / ".local/state"), "XDG_CACHE_HOME": str(self.home / ".cache"),
               "NC_INSTALLER_TEST": "1", "NC_OS_RELEASE": str(self.d / "osr"), "NC_LANGUE": "fr"}

    def appels(self):
        return self.journal.read_text() if self.journal.exists() else ""

    def fin(self):
        shutil.rmtree(self.d, ignore_errors=True)


class NixosTest(unittest.TestCase):
    def banc(self, **kw):
        b = Banc(**kw)
        self.addCleanup(b.fin)
        return b

    def test_de_bout_en_bout_rien_du_systeme(self):
        b = self.banc()
        r = b.lance("--oui")
        sortie = r.stdout + r.stderr
        self.assertEqual(r.returncode, 0, sortie)
        self.assertEqual(b.appels(), "", "un outil du système a été lancé")
        self.assertTrue((b.home / ".config/systemd/user/noctalia.service").is_file(), sortie)

    def test_unites_reecrites_sur_nixos(self):
        b = self.banc()
        r = b.lance("--oui")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        for u in UNITES:
            texte = (b.home / ".config/systemd/user" / u).read_text()
            self.assertNotIn("/usr/bin/", texte, u)
        self.assertIn("/run/current-system/sw/bin/", (b.home / ".config/systemd/user/noctalia.service").read_text())

    def test_unites_inchangees_ailleurs(self):
        for fam in ["arch", "debian", "fedora", "opensuse-tumbleweed"]:
            with self.subTest(fam):
                b = self.banc(famille=fam)
                r = b.lance("--oui", "--files-only")
                self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
                texte = (b.home / ".config/systemd/user/noctalia.service").read_text()
                self.assertIn("/usr/bin/noctalia", texte)
                self.assertNotIn("/run/current-system", texte)

    def _existants(self, b):
        (b.home / ".zshrc").write_text("ancien\n")
        (b.home / ".config/nvim").mkdir(parents=True)
        (b.home / ".config/nvim/init.lua").write_text("ancien nvim\n")

    def test_zshrc_existant_inchange_par_defaut(self):
        b = self.banc()
        self._existants(b)
        r = b.lance("--oui")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual((b.home / ".zshrc").read_text(), "ancien\n")
        self.assertEqual((b.home / ".config/nvim/init.lua").read_text(), "ancien nvim\n")
        self.assertEqual(sorted(p.name for p in (b.home / ".config/nvim").iterdir()), ["init.lua"])

    def test_zshrc_existant_remplace_si_oui(self):
        b = self.banc()
        self._existants(b)
        r = b.lance("--oui", tty="o")
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertNotEqual((b.home / ".zshrc").read_text(), "ancien\n")
        self.assertNotEqual((b.home / ".config/nvim/init.lua").read_text(), "ancien nvim\n")
        sauvegardes = [p for p in b.home.rglob("*") if p.is_file() and "ancien" in p.read_text(errors="ignore")]
        self.assertTrue(sauvegardes, "pas de sauvegarde de l'ancien .zshrc")

    def test_zshrc_nvim_absents_copies(self):
        b = self.banc()
        r = b.lance("--oui")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertTrue((b.home / ".zshrc").is_file())
        self.assertTrue((b.home / ".p10k.zsh").is_file())
        self.assertTrue((b.home / ".config/nvim").is_dir())

    def test_zshrc_lien_symbolique_inchange_par_defaut(self):
        b = self.banc()
        cible = b.d / "store-zshrc"
        cible.write_text("du store\n")
        (b.home / ".zshrc").symlink_to(cible)
        r = b.lance("--oui")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertTrue((b.home / ".zshrc").is_symlink())
        self.assertEqual(cible.read_text(), "du store\n")

    def test_outil_manquant_arret_avant_copie(self):
        b = self.banc(absents=["kitty"])
        r = b.lance("--oui")
        sortie = r.stdout + r.stderr
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("kitty", sortie)
        self.assertIn("noctalia-config-nixos", sortie)
        self.assertEqual(b.appels(), "")
        self.assertFalse((b.home / ".config/systemd").exists(), "copie faite malgré l'outil manquant")

    def test_seulement_energie_arret(self):
        b = self.banc()
        r = b.lance("--oui", "--seulement", "energie")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("NixOS", r.stdout + r.stderr)
        self.assertEqual(b.appels(), "")


if __name__ == "__main__":
    unittest.main()

"""Fonds d'écran séparés par thème, et « Mes fonds » qui survivent aux mises à jour (contrat fonds-separes-et-perso).

F1 : ~/Pictures/Wallpapers/<thème>/mes-fonds/ (et mes-fonds/ à la racine pour la base) : jamais livré par le dépôt,
jamais touché par install.sh (boucle de copie rejouée) ni par nc-maj (vrais dépôts git, faux install.sh en sh).
Tout se passe dans un dossier temporaire : HOME et XDG_* y pointent."""
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests import _isolation  # noqa: F401

REPO = Path(__file__).resolve().parents[1]
INSTALL = (REPO / "install.sh").read_text(encoding="utf-8")
NC_MAJ = REPO / "home/.local/bin/nc-maj"
# La boucle de copie d'install.sh, telle quelle
BOUCLE = INSTALL[INSTALL.index("while IFS= read -r -d '' src; do\n  rel=\"${src#\"$root/\"}\""):
                 INSTALL.index('done < <(find "$root" -type f -print0)') + len('done < <(find "$root" -type f -print0)')]


class Base(unittest.TestCase):
    def setUp(self):
        d = tempfile.TemporaryDirectory(prefix="nc-fonds-perso-")
        self.addCleanup(d.cleanup)
        self.r = Path(d.name)
        self.home = self.r / "home/user"
        self.home.mkdir(parents=True)
        self.fonds = self.home / "Pictures/Wallpapers"
        self.env = dict(os.environ, HOME=str(self.home), XDG_CONFIG_HOME=str(self.home / ".config"),
                        XDG_CACHE_HOME=str(self.home / ".cache"), XDG_STATE_HOME=str(self.home / ".local/state"),
                        XDG_DATA_HOME=str(self.home / ".local/share"), TMPDIR=str(self.r), NC_LANGUE="fr")
        for v in ("HYPRLAND_INSTANCE_SIGNATURE", "NOCTALIA_CONFIG_HOME", "GIT_SSH_COMMAND", "GIT_SSH"):
            self.env.pop(v, None)

    def mes_fonds(self):
        """Fonds posés par la personne, dont un du même nom qu'un fond livré ; renvoie {chemin: (contenu, mtime)}."""
        poses = {}
        for rel in ("mes-fonds/b.jpg", "mes-fonds/perso.png", "nord/mes-fonds/a.jpg", "nord/mes-fonds/x.webp"):
            p = self.fonds / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(b"a moi " + rel.encode())
            os.utime(p, (1000, 1000))
        return self.etat_mes_fonds()

    def etat_mes_fonds(self):
        return {str(p.relative_to(self.fonds)): (p.read_bytes(), p.stat().st_mtime)
                for p in sorted(self.fonds.rglob("*")) if p.is_file() and "mes-fonds" in p.parts}


class F1Depot(unittest.TestCase):
    def test_le_depot_ne_livre_aucun_mes_fonds(self):
        r = subprocess.run(["git", "-C", str(REPO), "ls-files", "home/Pictures"], capture_output=True, text=True)
        if r.returncode != 0:
            self.skipTest("pas un dépôt git")
        self.assertTrue(r.stdout.strip())                       # contrôle : des fonds sont bien livrés
        self.assertNotIn("mes-fonds", r.stdout)
        self.assertFalse(list((REPO / "home").rglob("mes-fonds")))


class F1Install(Base):
    def copie(self, depot):
        prog = ("set -uo pipefail\n"
                f'root="{depot}"; FAMILY=arch; MODE=full; NIXOS_TERM=n; NIXOS_NVIM=n\n'
                f'SED_ARGS=(-e "s|@HOME@|$HOME|g"); tmp="$(mktemp)"; same=0; copied=0; hypr_changed=0; BK="{self.r}/bk"\n'
                'mkdir -p "$BK"; backup() { :; }\n' + BOUCLE + '\necho "copies=$copied"\n')
        r = subprocess.run(["bash", "-c", prog], env=self.env, capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout

    def test_installation_rejouee_laisse_mes_fonds_intacts(self):
        depot = self.r / "depot"
        for rel, texte in (("Pictures/Wallpapers/b.jpg", b"livre b"), ("Pictures/Wallpapers/nord/a.jpg", b"livre a"),
                           (".config/nc/exemple.conf", b"X=1\n")):
            (depot / rel).parent.mkdir(parents=True, exist_ok=True)
            (depot / rel).write_bytes(texte)
        avant = self.mes_fonds()
        (self.home / ".config/nc").mkdir(parents=True)
        (self.home / ".config/nc/exemple.conf").write_text("ancien\n")
        self.assertIn("copies=3", self.copie(depot))                         # contrôle : la boucle copie bien
        self.assertEqual((self.fonds / "nord/a.jpg").read_bytes(), b"livre a")
        self.assertEqual((self.home / ".config/nc/exemple.conf").read_text(), "X=1\n")
        self.copie(depot)                                                    # installation rejouée
        self.assertEqual(self.etat_mes_fonds(), avant)
        self.assertEqual((self.fonds / "mes-fonds/b.jpg").read_bytes(), b"a moi mes-fonds/b.jpg")   # même nom qu'un livré


class F1Maj(Base):
    def git(self, *a, cwd=None):
        subprocess.run(["git", *a], env=self.env, cwd=cwd, capture_output=True, text=True, check=True)

    def test_maj_laisse_mes_fonds_intacts(self):
        self.env.update(GIT_AUTHOR_NAME="T", GIT_AUTHOR_EMAIL="t@exemple.invalid", GIT_COMMITTER_NAME="T",
                        GIT_COMMITTER_EMAIL="t@exemple.invalid", GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1",
                        J=str(self.r / "journal"))
        amont, auteur, ami = self.r / "amont.git", self.r / "auteur", self.r / "ami"
        self.git("init", "-q", "--bare", "-b", "main", str(amont))
        self.git("clone", "-q", str(amont), str(auteur))
        self.git("-C", str(auteur), "checkout", "-q", "-b", "main")
        # faux install.sh : il note son passage, rien d'autre
        (auteur / "install.sh").write_text('#!/bin/sh\nprintf "install %s\\n" "$*" >> "$J"\n')
        (auteur / "install.sh").chmod(0o755)
        self.git("-C", str(auteur), "add", "install.sh")
        self.git("-C", str(auteur), "commit", "-qm", "Départ")
        self.git("-C", str(auteur), "push", "-q", "origin", "main")
        self.git("clone", "-q", str(amont), str(ami))
        (auteur / "f").write_text("nouveau\n")
        self.git("-C", str(auteur), "add", "f")
        self.git("-C", str(auteur), "commit", "-qm", "Nouveauté")
        self.git("-C", str(auteur), "push", "-q", "origin", "main")
        (self.home / ".config/nc").mkdir(parents=True)
        (self.home / ".config/nc/depot").write_text(str(ami))
        avant = self.mes_fonds()
        r = subprocess.run(["bash", str(NC_MAJ), "--no-system"], env=self.env, capture_output=True, text=True,
                           timeout=60, stdin=subprocess.DEVNULL)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("install --no-system", (self.r / "journal").read_text())   # contrôle : la mise à jour a eu lieu
        self.assertTrue((ami / "f").exists())
        self.assertEqual(self.etat_mes_fonds(), avant)


if __name__ == "__main__":
    unittest.main()

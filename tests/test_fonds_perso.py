"""Fonds d'écran séparés par thème, et « Mes fonds » qui survivent aux mises à jour (contrat fonds-separes-et-perso).

F1 : ~/Pictures/Wallpapers/<thème>/mes-fonds/ (et mes-fonds/ à la racine pour la base) : jamais livré par le dépôt,
jamais touché par install.sh (boucle de copie rejouée) ni par nc-maj (vrais dépôts git, faux install.sh en sh).
F3 : nc-fonds ajoute (copie), ouvre, met à la corbeille un fond à toi (jamais un fond livré) ; faux magick, zenity,
gio, systemctl et xdg-open en sh qui notent leurs arguments.
Tout se passe dans un dossier temporaire : HOME et XDG_* y pointent."""
import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests import _isolation  # noqa: F401

REPO = Path(__file__).resolve().parents[1]
INSTALL = (REPO / "install.sh").read_text(encoding="utf-8")
NC_MAJ = REPO / "home/.local/bin/nc-maj"
NC_FONDS = REPO / "home/.local/bin/nc-fonds"
PANEL = REPO / "home/.local/share/noctalia/plugins/nc-carousel/panel.luau"
REGLAGES = REPO / "home/.local/bin/nc-reglages"
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


class Fonds(Base):
    """nc-fonds dans un faux HOME, avec de faux programmes."""
    def setUp(self):
        super().setUp()
        self.bin = self.r / "bin"
        self.bin.mkdir()
        self.journal = self.r / "journal"
        self.journal.touch()
        # faux magick : « identify » écrit la taille si le fichier contient « L H », sinon échoue (pas une image)
        self.faux("magick", 'for a; do last="$a"; done\nf="${last%\\[0\\]}"\n'
                  'grep -qx "[0-9]* [0-9]*" "$f" && cat "$f"\n')
        self.faux("gio", 'mkdir -p "$HOME/corbeille" && mv -- "$3" "$HOME/corbeille/"\n')
        self.faux("zenity", 'printf "%s" "$NC_CHOISI"\n')
        for nom in ("systemctl", "xdg-open", "notify-send"):
            self.faux(nom, "")
        self.env.update(PATH=f"{self.bin}:{os.environ['PATH']}", J=str(self.journal))
        (self.fonds / "nord").mkdir(parents=True)
        (self.fonds / "nord/n.png").write_text("3840 2160\n")
        self.image = self.r / "mon fond.png"
        self.image.write_text("3840 2160\n")

    def faux(self, nom, corps):
        f = self.bin / nom
        f.write_text('#!/bin/sh\nprintf "%s %s\\n" "' + nom + '" "$*" >> "$J"\n' + corps)
        f.chmod(f.stat().st_mode | stat.S_IEXEC)

    def theme(self):
        c = self.home / ".config/noctalia"
        c.mkdir(parents=True, exist_ok=True)
        (c / "zy-reglages.toml").write_text(f'[wallpaper]\ndirectory = "{self.fonds}/nord"\n')
        return self.fonds / "nord/mes-fonds"

    def lance(self, *args, **env):
        return subprocess.run([str(NC_FONDS), *args], env=dict(self.env, **env), capture_output=True, text=True,
                              timeout=60, stdin=subprocess.DEVNULL)

    def journal_de(self, nom):
        return [l for l in self.journal.read_text().splitlines() if l.startswith(nom + " ")]

    def test_dossier_du_theme_et_de_la_base(self):
        self.assertEqual(self.lance("dossier").stdout.strip(), f"{self.fonds}/mes-fonds")
        mes = self.theme()
        self.assertEqual(self.lance("dossier").stdout.strip(), str(mes))
        self.assertFalse(mes.exists())                                     # rien n'est créé

    def test_ajouter_copie_dans_mes_fonds_du_theme(self):
        mes = self.theme()
        r = self.lance("ajouter", str(self.image))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual((mes / "mon fond.png").read_text(), "3840 2160\n")
        self.assertTrue(self.image.exists())                               # copié, pas déplacé
        self.assertEqual(sorted(p.name for p in mes.iterdir()), ["mon fond.png"])     # aucun reste .part
        self.assertIn("systemctl --user restart --no-block nc-carousel-thumbs.service", self.journal.read_text())
        self.assertIn("1 fond(s) ajouté(s)", r.stdout)
        self.assertNotIn("Attention", r.stdout)

    def test_pas_une_image_refus_clair(self):
        mes = self.theme()
        faux_png = self.r / "faux.png"
        faux_png.write_text("du texte")
        texte = self.r / "notes.txt"
        texte.write_text("3840 2160\n")                                    # « lisible », mais pas une extension d'image
        for f in (faux_png, texte):
            r = self.lance("ajouter", str(f))
            self.assertEqual(r.returncode, 1)
            self.assertIn("n'est pas une image", r.stderr)
        self.assertFalse(mes.exists() and list(mes.iterdir()))
        self.assertEqual(self.journal_de("systemctl"), [])

    def test_petite_image_avertissement_sans_refus(self):
        mes = self.theme()
        petit = self.r / "petit.jpg"
        petit.write_text("1920 1080\n")
        r = self.lance("ajouter", str(petit))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue((mes / "petit.jpg").exists())
        self.assertIn("moins que 2560 x 1600", r.stdout)

    def test_meme_nom_autre_image_numerotee_meme_image_une_fois(self):
        mes = self.theme()
        self.lance("ajouter", str(self.image))
        self.lance("ajouter", str(self.image))                             # la même : rien de plus
        autre = self.r / "autre" / "mon fond.png"
        autre.parent.mkdir()
        autre.write_text("5120 2880\n")
        self.lance("ajouter", str(autre))
        self.assertEqual(sorted(p.name for p in mes.iterdir()), ["mon fond-2.png", "mon fond.png"])
        self.assertEqual((mes / "mon fond-2.png").read_text(), "5120 2880\n")

    def test_sans_argument_le_selecteur(self):
        r = self.lance("ajouter", NC_CHOISI=str(self.image))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(self.journal_de("zenity"))
        self.assertTrue((self.fonds / "mes-fonds/mon fond.png").exists())
        r = self.lance("ajouter", NC_CHOISI="")                            # annulé : rien, sans erreur
        self.assertEqual((r.returncode, r.stderr), (0, ""))

    def test_retirer_un_fond_a_toi_a_la_corbeille(self):
        mes = self.theme()
        self.lance("ajouter", str(self.image))
        r = self.lance("retirer", str(mes / "mon fond.png"))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertFalse((mes / "mon fond.png").exists())
        self.assertTrue((self.home / "corbeille/mon fond.png").exists())  # à la corbeille, pas supprimé

    def test_retirer_un_fond_livre_refuse(self):
        r = self.lance("retirer", str(self.fonds / "nord/n.png"))
        self.assertEqual(r.returncode, 1)
        self.assertIn("se masque", r.stderr)
        self.assertTrue((self.fonds / "nord/n.png").exists())
        self.assertEqual(self.journal_de("gio"), [])

    def test_ouvrir_cree_et_ouvre(self):
        mes = self.theme()
        r = self.lance("ouvrir")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(mes.is_dir())
        for _ in range(50):                                                # xdg-open part en arrière-plan
            if self.journal_de("xdg-open"):
                break
            subprocess.run(["sleep", "0.1"])
        self.assertEqual(self.journal_de("xdg-open"), [f"xdg-open {mes}"])

    def test_inconnu_code_2_sans_rien_faire(self):
        r = self.lance("ajoute")
        self.assertEqual(r.returncode, 2)
        self.assertEqual(self.journal.read_text(), "")

    def test_boutons_du_carrousel_et_des_reglages(self):
        panneau = PANEL.read_text(encoding="utf-8")
        for mot in ('NC_FONDS, "ajouter"', 'NC_FONDS, "ouvrir"', 'NC_FONDS, "retirer", w.path', "if w and w.perso then"):
            self.assertIn(mot, panneau)
        reglages = REGLAGES.read_text(encoding="utf-8")
        self.assertIn('["nc-fonds", "ajouter"]', reglages)
        self.assertIn('["nc-fonds", "ouvrir"]', reglages)


if __name__ == "__main__":
    unittest.main()

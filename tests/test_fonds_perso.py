"""Fonds d'écran séparés par thème, et « Mes fonds » qui survivent aux mises à jour (contrat fonds-separes-et-perso).

F1 : ~/Pictures/Wallpapers/<thème>/mes-fonds/ (et mes-fonds/ à la racine pour la base) : jamais livré par le dépôt,
jamais touché par install.sh (boucle de copie rejouée) ni par nc-maj (vrais dépôts git, faux install.sh en sh).
F3 : nc-fonds ajoute (copie), ouvre, met à la corbeille un fond à toi (jamais un fond livré) ; faux magick, zenity,
gio, systemctl et xdg-open en sh qui notent leurs arguments.
F4 : un fond livré se masque (liste fonds-masques.conf, puis corbeille) ; ni le carrousel ni une installation rejouée
ne le ramènent ; « reafficher » vide la liste et le recopie depuis le dépôt. Contrôles : l'ancien carrousel (9dc038d)
montre le fond masqué, l'ancienne boucle d'install.sh (719f872) le recopie. Le fond affiché masqué ou rangé est reposé
(faux noctalia qui note ses arguments).
F5 : les fonds posés par toi à la racine ne bougent pas tout seuls ; nc-fonds a-ranger les compte (les fonds livrés de
la base, absents de CREDITS.tsv, ne comptent pas), ranger / garder répondent une fois pour toutes.
Tout se passe dans un dossier temporaire : HOME et XDG_* y pointent."""
import os
import shutil
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
LUA = shutil.which("lua") or shutil.which("lua5.4")
# La boucle de copie d'install.sh, telle quelle
def boucle(texte):
    return texte[texte.index("while IFS= read -r -d '' src; do\n  rel=\"${src#\"$root/\"}\""):
                 texte.index('done < <(find "$root" -type f -print0)') + len('done < <(find "$root" -type f -print0)')]


BOUCLE = boucle(INSTALL)


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

    def copie(self, depot, boucle=BOUCLE):
        """La boucle de copie d'install.sh (ou une autre version de cette boucle) avec ce faux dépôt."""
        prog = ("set -uo pipefail\n"
                f'root="{depot}"; FAMILY=arch; MODE=full; NIXOS_TERM=n; NIXOS_NVIM=n\n'
                f'SED_ARGS=(-e "s|@HOME@|$HOME|g"); tmp="$(mktemp)"; same=0; copied=0; hypr_changed=0; BK="{self.r}/bk"\n'
                'mkdir -p "$BK"; backup() { :; }\n' + boucle + '\necho "copies=$copied"\n')
        r = subprocess.run(["bash", "-c", prog], env=self.env, capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout

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


class EnvFonds(Base):
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
        for nom in ("systemctl", "xdg-open", "notify-send", "noctalia"):
            self.faux(nom, "")
        self.env.update(PATH=f"{self.bin}:{os.environ['PATH']}", J=str(self.journal))
        (self.fonds / "nord").mkdir(parents=True)
        (self.fonds / "nord/n.png").write_text("3840 2160\n")
        # les fonds livrés des thèmes : ceux de CREDITS.tsv (copie de ~, faute de dépôt installé)
        (self.fonds / "CREDITS.tsv").write_text("fichier\tsource\nnord/n.png\tx\nnord/o.png\tx\n")
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


class F3Fonds(EnvFonds):
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


class F4Masquer(EnvFonds):
    def masques(self):
        f = self.home / ".config/nc/fonds-masques.conf"
        return f.read_text().splitlines() if f.exists() else None

    def test_masquer_met_a_la_corbeille_et_inscrit(self):
        r = self.lance("masquer", str(self.fonds / "nord/n.png"))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.masques(), ["nord/n.png"])
        self.assertFalse((self.fonds / "nord/n.png").exists())
        self.assertTrue((self.home / "corbeille/n.png").exists())          # à la corbeille, pas supprimé
        self.assertEqual(self.journal_de("noctalia"), [])                   # pas le fond affiché : rien n'est posé

    def test_masquer_le_fond_affiche_pose_le_suivant(self):
        (self.fonds / "nord/o.png").write_text("3840 2160\n")
        r = self.lance("masquer", str(self.fonds / "nord/n.png"), "--poser", str(self.fonds / "nord/o.png"))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.journal_de("noctalia"), [f"noctalia msg wallpaper-set {self.fonds}/nord/o.png"])

    def depot_installe(self):
        depot = self.r / "depot"
        (depot / "home/Pictures/Wallpapers/nord").mkdir(parents=True)
        (depot / "home/Pictures/Wallpapers/nord/n.png").write_text("3840 2160\n")
        (self.home / ".config/nc").mkdir(parents=True, exist_ok=True)
        (self.home / ".config/nc/depot").write_text(str(depot))
        return depot

    def test_installation_rejouee_ne_ramene_pas_un_fond_masque(self):
        depot = self.depot_installe()
        self.lance("masquer", str(self.fonds / "nord/n.png"))
        self.copie(depot / "home")
        self.assertFalse((self.fonds / "nord/n.png").exists())
        # contrôle du contrôle : la boucle d'install.sh d'avant (719f872) le recopiait
        r = subprocess.run(["git", "-C", str(REPO), "show", "719f872:install.sh"], capture_output=True, text=True)
        if r.returncode != 0:
            self.skipTest("719f872 absent (clone partiel)")
        self.copie(depot / "home", boucle(r.stdout))
        self.assertTrue((self.fonds / "nord/n.png").exists(), "contrôle : l'ancienne boucle ramenait le fond masqué")

    def test_reafficher_recopie_depuis_le_depot(self):
        self.depot_installe()
        self.lance("masquer", str(self.fonds / "nord/n.png"))
        r = self.lance("reafficher")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("1 fond(s) réaffiché(s).", r.stdout)
        self.assertEqual((self.fonds / "nord/n.png").read_text(), "3840 2160\n")
        self.assertIsNone(self.masques())

    def test_reafficher_sans_depot_dit_de_mettre_a_jour(self):
        self.lance("masquer", str(self.fonds / "nord/n.png"))
        r = self.lance("reafficher")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("nc-maj", r.stdout)
        self.assertIsNone(self.masques())                                   # la mise à jour les remettra
        self.assertFalse((self.fonds / "nord/n.png").exists())

    def test_reafficher_jamais_hors_du_dossier(self):
        self.depot_installe()
        (self.home / ".config/nc/fonds-masques.conf").write_text("../../dehors.png\n/etc/passwd\n")
        self.lance("reafficher")
        self.assertFalse((self.home.parent / "dehors.png").exists())

    @unittest.skipUnless(LUA, "lua absent")
    def test_suivant_du_groupe(self):
        bloc = PANEL.read_text(encoding="utf-8").split("-- DEBUT cle", 1)[1].split("-- FIN cle", 1)[0].split("\n", 1)[1]
        prog = bloc + r"""
local a, b, c, m = { g = 1, n = "a" }, { g = 1, n = "b" }, { g = 1, n = "c" }, { g = 2, n = "m" }
local l = { a, b, c, m }
local function n(x) return x and x.n or "nil" end
io.write(n(suivantDuGroupe(l, a)), n(suivantDuGroupe(l, c)), n(suivantDuGroupe(l, m)), n(suivantDuGroupe({ a, m }, a)))
"""
        f = self.r / "suivant.lua"
        f.write_text(prog, encoding="utf-8")
        r = subprocess.run([LUA, str(f)], capture_output=True, text=True, check=False)
        self.assertEqual(r.stdout, "banilnil", r.stderr)

    def test_une_image_non_livree_ne_se_masque_pas(self):
        """Une image à toi à la racine, dans un dossier de thème, ou dans un dossier hors de ~/Pictures/Wallpapers :
        refus, fichier intact, liste inchangée. Contrôle : l'ancien nc-fonds (e4d2efd) la mettait à la corbeille."""
        ailleurs = self.home / "Images/perso.jpg"
        ailleurs.parent.mkdir(parents=True)
        for f in (self.fonds / "moi.jpg", self.fonds / "nord/perso.png", ailleurs):
            f.write_text("3840 2160\n")
            r = self.lance("masquer", str(f))
            self.assertEqual(r.returncode, 1, (f, r.stdout))
            self.assertIn("n'est pas un fond livré", r.stderr)
            self.assertIn("Ranger dans Mes fonds", r.stderr)
            self.assertTrue(f.exists())
            self.assertIsNone(self.masques())
        self.assertEqual(self.journal_de("gio"), [])
        r = subprocess.run(["git", "-C", str(REPO), "show", "e4d2efd:home/.local/bin/nc-fonds"], capture_output=True, text=True)
        if r.returncode != 0:
            self.skipTest("e4d2efd absent (clone partiel)")
        vieux = self.r / "vieux-nc-fonds"
        vieux.write_text(r.stdout)
        vieux.chmod(0o755)
        subprocess.run([str(vieux), "masquer", str(self.fonds / "moi.jpg")], env=self.env, capture_output=True, timeout=60)
        self.assertFalse((self.fonds / "moi.jpg").exists(), "contrôle : l'ancien nc-fonds jetait une image à toi")

    def test_retirer_hors_des_fonds_refuse(self):
        dehors = self.home / "ailleurs/mes-fonds/x.png"                     # un « mes-fonds » hors de ~/Pictures/Wallpapers
        dehors.parent.mkdir(parents=True)
        dehors.write_text("3840 2160\n")
        lien = self.fonds / "nord/mes-fonds/lien.png"                       # un lien qui sort des fonds
        lien.parent.mkdir(parents=True)
        cible = self.home / "Documents/precieux.png"
        cible.parent.mkdir(parents=True)
        cible.write_text("3840 2160\n")
        lien.symlink_to(cible)
        for f in (dehors, lien):
            r = self.lance("retirer", str(f))
            self.assertEqual(r.returncode, 1, (f, r.stdout))
        self.assertTrue(dehors.exists() and cible.exists())
        self.assertEqual(self.journal_de("gio"), [])
        mes = self.fonds / "nord/mes-fonds/vrai.png"                        # contrôle : un vrai fond à toi part bien
        mes.write_text("3840 2160\n")
        self.assertEqual(self.lance("retirer", str(mes)).returncode, 0)

    def test_livres_base_et_themes(self):
        l = self.lance("livres").stdout.splitlines()
        self.assertIn("nord/n.png", l)
        self.assertIn("astronaut-dark-5120x2880-22768.jpg", l)
        self.assertNotIn("fichier", l)

    @unittest.skipUnless(LUA, "lua absent")
    def test_remplacant_jamais_l_ecran_vide(self):
        bloc = PANEL.read_text(encoding="utf-8").split("-- DEBUT cle", 1)[1].split("-- FIN cle", 1)[0].split("\n", 1)[1]
        prog = bloc + r"""
local a, b, m = { g = 1, n = "a" }, { g = 1, n = "b" }, { g = 2, n = "m" }
local function n(x) return x and x.n or "nil" end
io.write(n(remplacant({ a, b, m }, a)), n(remplacant({ a, m }, a)), n(remplacant({ m, a }, a)), n(remplacant({ a }, a)))
"""
        f = self.r / "remplacant.lua"
        f.write_text(prog, encoding="utf-8")
        r = subprocess.run([LUA, str(f)], capture_output=True, text=True, check=False)
        self.assertEqual(r.stdout, "bmmnil", r.stderr)

    def test_home_et_fin_gardes_sur_liste_vide(self):
        self.assertIn('if (chord == "Home" or chord == "End") and #shown == 0 then return end',
                      PANEL.read_text(encoding="utf-8"))

    def test_un_fond_a_toi_ne_se_masque_pas(self):
        mes = self.theme()
        self.lance("ajouter", str(self.image))
        r = self.lance("masquer", str(mes / "mon fond.png"))
        self.assertEqual(r.returncode, 1)
        self.assertIn("corbeille", r.stderr)
        self.assertIsNone(self.masques())

    def lance_liste(self, src, appel):
        bloc = src.split("-- DEBUT cle", 1)[1].split("-- FIN cle", 1)[0].split("\n", 1)[1]
        prog = bloc + r"""
local fichiers = {
  ["/h/u/Pictures/Wallpapers/nord"] = { "a.png", "b.png", "mes-fonds" },
  ["/h/u/Pictures/Wallpapers/nord/mes-fonds"] = { "m.png" },
}
local api = {
  listDir = function(d) local l = fichiers[(d:gsub("/$", ""))]; if not l then return nil end
    local c = {} for i, f in ipairs(l) do c[i] = f end return c end,
  fileInfo = function(p) return { isDir = fichiers[p] ~= nil } end,
  fileExists = function() return true end,
}
local out = {}
for _, w in ipairs(""" + appel + r""") do out[#out + 1] = w.path end
io.write(table.concat(out, "\n"))
"""
        f = self.r / "liste.lua"
        f.write_text(prog, encoding="utf-8")
        r = subprocess.run([LUA, str(f)], capture_output=True, text=True, check=False)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout.split("\n")

    @unittest.skipUnless(LUA, "lua absent")
    def test_le_carrousel_cache_les_masques(self):
        l = self.lance_liste(PANEL.read_text(encoding="utf-8"),
                             'listerFonds(groupesDuCarrousel("/h/u/Pictures/Wallpapers/nord"), "/c/", api, { png = true }, '
                             'lireMasques("nord/b.png\\n/ailleurs/x.png\\n"), "/h/u/Pictures/Wallpapers")')
        self.assertEqual(l, ["/h/u/Pictures/Wallpapers/nord/a.png", "/h/u/Pictures/Wallpapers/nord/mes-fonds/m.png"])
        r = subprocess.run(["git", "-C", str(REPO), "show", "9dc038d:home/.local/share/noctalia/plugins/nc-carousel/panel.luau"],
                           capture_output=True, text=True)
        if r.returncode != 0:
            self.skipTest("9dc038d absent (clone partiel)")
        vieux = self.lance_liste(r.stdout, 'listerFonds({ "/h/u/Pictures/Wallpapers/nord" }, "/c/", api, { png = true }, '
                                           '{ ["nord/b.png"] = true }, "/h/u/Pictures/Wallpapers")')
        self.assertIn("/h/u/Pictures/Wallpapers/nord/b.png", vieux, "contrôle : l'ancien carrousel montrait le fond masqué")

    def test_boutons_masquer_et_reafficher(self):
        panneau = PANEL.read_text(encoding="utf-8")
        i = panneau.index("elseif w and livres[cheminMasque(w.path, baseFonds)] then")   # seulement pour un fond livré
        self.assertIn('NC_FONDS, "masquer", w.path', panneau[i:i + 1100])
        self.assertIn('"--poser", x.path', panneau[i:i + 1100])              # le fond affiché : un remplaçant
        self.assertIn("if not x then", panneau[i:i + 1100])                  # aucun remplaçant : refus
        j = panneau.index('elseif w and w.path:match("^(.*)/[^/]*$") == baseFonds then')
        self.assertIn('bouton("ranger-un"', panneau[j:j + 300])              # une image à toi de la racine : la ranger
        self.assertIn('["nc-fonds", "reafficher"]', REGLAGES.read_text(encoding="utf-8"))


class F5Ranger(EnvFonds):
    LIVRE = "astronaut-dark-5120x2880-22768.jpg"

    def setUp(self):
        super().setUp()
        (self.fonds / self.LIVRE).write_text("5120 2880\n")
        (self.fonds / "moi.jpg").write_text("3840 2160\n")
        (self.fonds / "CREDITS.tsv").write_text("fichier\tsource\n")

    def test_liste_des_fonds_livres_a_jour(self):
        src = NC_FONDS.read_text(encoding="utf-8")
        liste = src.split('LIVRES_BASE="', 1)[1].split('"', 1)[0].split("\n")
        livres = sorted(p.name for p in (REPO / "home/Pictures/Wallpapers").iterdir()
                        if p.is_file() and p.name != "CREDITS.tsv")
        self.assertEqual(liste, livres)
        # contrôle : CREDITS.tsv ne liste pas ces fonds (le critère du contrat les aurait pris pour les tiens)
        credits = (REPO / "home/Pictures/Wallpapers/CREDITS.tsv").read_text(encoding="utf-8")
        self.assertNotIn(self.LIVRE, credits)

    def test_compter_ne_deplace_rien(self):
        r = self.lance("a-ranger")
        self.assertEqual((r.returncode, r.stdout.strip()), (0, "1"), r.stderr)
        self.assertTrue((self.fonds / "moi.jpg").exists())
        self.assertFalse((self.fonds / "mes-fonds").exists())

    def test_oui_range_les_tiens_seulement_et_ne_redemande_plus(self):
        r = self.lance("ranger")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual((self.fonds / "mes-fonds/moi.jpg").read_text(), "3840 2160\n")
        self.assertFalse((self.fonds / "moi.jpg").exists())
        self.assertTrue((self.fonds / self.LIVRE).exists())                # un fond livré reste à sa place
        self.assertTrue((self.fonds / "nord/n.png").exists())
        self.assertEqual((self.home / ".config/nc/fonds-rangement").read_text(), "oui\n")
        self.assertEqual(self.lance("a-ranger").stdout.strip(), "0")

    def test_le_fond_affiche_range_est_repose(self):
        r = self.lance("ranger", "--affiche", str(self.fonds / "moi.jpg"))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.journal_de("noctalia"), [f"noctalia msg wallpaper-set {self.fonds}/mes-fonds/moi.jpg"])

    def test_un_autre_fond_affiche_n_est_pas_repose(self):
        self.lance("ranger", "--affiche", str(self.fonds / self.LIVRE))
        self.assertEqual(self.journal_de("noctalia"), [])

    def test_ranger_une_seule_image(self):
        (self.fonds / "autre.jpg").write_text("3840 2160\n")
        r = self.lance("ranger", str(self.fonds / "moi.jpg"))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue((self.fonds / "mes-fonds/moi.jpg").exists())
        self.assertTrue((self.fonds / "autre.jpg").exists())                 # les autres restent
        self.assertFalse((self.home / ".config/nc/fonds-rangement").exists())   # la question reste posée
        r = self.lance("ranger", str(self.fonds / self.LIVRE))                # un fond livré : refus
        self.assertEqual(r.returncode, 1)
        self.assertTrue((self.fonds / self.LIVRE).exists())

    def test_non_ne_deplace_rien_et_ne_redemande_plus(self):
        r = self.lance("garder")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue((self.fonds / "moi.jpg").exists())
        self.assertEqual(self.lance("a-ranger").stdout.strip(), "0")

    def test_carrousel_demande_seulement_sans_reponse(self):
        panneau = PANEL.read_text(encoding="utf-8")
        i = panneau.index("if not noctalia.fileExists(RANGEMENT) then")
        self.assertIn('NC_FONDS, "a-ranger"', panneau[i:i + 200])
        # « ranger » ne part que du bouton « Oui »
        j = panneau.index('bouton("ranger-oui"')
        self.assertEqual(panneau[j:j + 500].count('NC_FONDS, "ranger"'), 2)


class Identify(EnvFonds):
    """La taille d'une image : magick identify, sinon identify (ImageMagick 6), sinon rien (accepté sur l'extension)."""
    OUTILS = ("bash", "cat", "cp", "mv", "mkdir", "rm", "realpath", "dirname", "basename", "grep", "cmp", "awk", "sort",
              "sed", "tail", "head", "setsid", "tr")

    def setUp(self):
        super().setUp()
        outils = self.r / "outils"                 # PATH sans le vrai ImageMagick du PC
        outils.mkdir()
        for nom in self.OUTILS:
            if shutil.which(nom):
                (outils / nom).symlink_to(shutil.which(nom))
        self.env["PATH"] = f"{self.bin}:{outils}"
        self.mes = self.fonds / "mes-fonds"
        self.petit = self.r / "petit.png"
        self.petit.write_text("1920 1080\n")

    def test_magick_seul(self):
        r = self.lance("ajouter", str(self.petit))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("moins que 2560 x 1600", r.stdout)
        self.assertIn("magick identify", self.journal.read_text())

    def test_identify_seul_imagemagick_6(self):
        (self.bin / "magick").unlink()
        self.faux("identify", 'for a; do last="$a"; done\nf="${last%\\[0\\]}"\n'
                  'grep -qx "[0-9]* [0-9]*" "$f" && cat "$f"\n')
        r = self.lance("ajouter", str(self.petit))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("moins que 2560 x 1600", r.stdout)
        self.assertTrue(self.journal_de("identify"))
        faux_png = self.r / "faux.png"
        faux_png.write_text("du texte")
        self.assertEqual(self.lance("ajouter", str(faux_png)).returncode, 1)   # identify voit bien que ce n'en est pas une

    def test_aucun_outil_accepte_sur_l_extension(self):
        (self.bin / "magick").unlink()
        r = self.lance("ajouter", str(self.petit))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue((self.mes / "petit.png").exists())
        self.assertIn("ImageMagick absent", r.stdout)
        texte = self.r / "notes.txt"
        texte.write_text("1920 1080\n")
        self.assertEqual(self.lance("ajouter", str(texte)).returncode, 1)      # l'extension reste vérifiée


if __name__ == "__main__":
    unittest.main()

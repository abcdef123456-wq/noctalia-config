"""Poser un assistant root depuis l'interface : « nc-assistant-install killswitch | energie » ouvre une fenêtre kitty qui lance
UNIQUEMENT « install.sh --seulement ÉTAPE » du clone noté dans ~/.config/nc/depot ; « install.sh --seulement » pose LA MÊME
question que l'installation complète (non par défaut, --oui ne l'accepte pas) avec les mêmes contrôles (dossiers sûrs, visudo -cf,
firewalld annoncé), sans aucune autre étape. Faux sudo, kitty, stat : ils notent leurs arguments et ne lancent JAMAIS le vrai ;
HOME, XDG_* et TMPDIR isolés ; aucune installation réelle."""
import json
import os
from pathlib import Path
import pty
import select
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
INSTALL = REPO / "install.sh"
OUTIL = REPO / "home/.local/bin/nc-assistant-install"


def faux(dossier, nom, corps):
    p = Path(dossier) / nom
    p.write_text("#!/usr/bin/env bash\n" + corps + "\n")
    p.chmod(p.stat().st_mode | stat.S_IEXEC)


class Base(unittest.TestCase):
    def setUp(self):
        parent = "/tmp/claude-1000"
        os.makedirs(parent, exist_ok=True)
        self._tmp = tempfile.TemporaryDirectory(prefix="nc-as-", dir=parent)
        self.addCleanup(self._tmp.cleanup)
        self.r = Path(self._tmp.name)
        self.home = self.r / "home/user"
        self.home.mkdir(parents=True)
        self.bin = self.r / "bin"
        self.bin.mkdir()
        self.journal = self.r / "journal.txt"
        (self.r / "run").mkdir()
        self.env = {"HOME": str(self.home), "XDG_CONFIG_HOME": str(self.home / ".config"), "XDG_DATA_HOME": str(self.home / ".local/share"),
                    "XDG_STATE_HOME": str(self.home / ".local/state"), "XDG_CACHE_HOME": str(self.home / ".cache"),
                    "XDG_RUNTIME_DIR": str(self.r / "run"), "TMPDIR": str(self.r), "PATH": f"{self.bin}:/usr/bin:/bin", "NC_LANGUE": "fr",
                    "FAUX_JOURNAL": str(self.journal)}

    def log(self):
        return self.journal.read_text() if self.journal.exists() else ""


class Installateur(Base):
    """nc-assistant-install : la fenêtre kitty et son argv."""

    def setUp(self):
        super().setUp()
        faux(self.bin, "kitty", 'python3 -c \'import json,sys; open(sys.argv[1], "a").write(json.dumps(sys.argv[2:]) + "\\n")\' "$FAUX_JOURNAL" "$@"')
        self.depot = self.r / "clone"
        self.depot.mkdir()
        (self.depot / "install.sh").write_text("#!/usr/bin/env bash\n")
        (self.home / ".config/nc").mkdir(parents=True)
        (self.home / ".config/nc/depot").write_text(str(self.depot) + "\n")

    def lancer(self, *args, **plus):
        return subprocess.run([sys.executable, str(OUTIL), *args], env=dict(self.env, **plus), capture_output=True, text=True,
                              stdin=subprocess.DEVNULL, timeout=30)

    def appels(self):
        return [json.loads(l) for l in self.log().splitlines()]

    def test_kitty_lance_seulement_l_etape_killswitch(self):
        r = self.lancer("killswitch")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(len(self.appels()), 1)
        argv = self.appels()[0]
        self.assertEqual(argv[-4:], ["bash", str(self.depot / "install.sh"), "--seulement", "killswitch"])
        self.assertEqual(argv[0], "--hold")                 # la fenêtre reste ouverte : la sortie se lit avant de la fermer
        self.assertNotIn("--oui", argv)

    def test_energie(self):
        self.assertEqual(self.lancer("energie").returncode, 0)
        self.assertEqual(self.appels()[0][-4:], ["bash", str(self.depot / "install.sh"), "--seulement", "energie"])

    def test_jamais_de_droits_root_ni_d_option_oui_dans_l_outil(self):
        src = OUTIL.read_text()
        for mot in ("pkexec", "sudo", "--oui", "shell=True", "os.system"):
            self.assertNotIn(mot, src, mot)

    def test_etape_inconnue_ou_absente(self):
        self.assertEqual(self.lancer("autre").returncode, 2)
        self.assertEqual(self.lancer().returncode, 2)
        self.assertEqual(self.lancer("killswitch; rm -rf x").returncode, 2)
        self.assertEqual(self.log(), "")

    def test_depot_introuvable_dit_comment_faire(self):
        (self.home / ".config/nc/depot").write_text(str(self.r / "nulle-part") + "\n")
        r = self.lancer("killswitch")
        self.assertEqual(r.returncode, 1)
        self.assertIn("introuvable", r.stderr)
        self.assertIn("./install.sh --seulement killswitch", r.stderr)
        self.assertEqual(self.log(), "")
        (self.home / ".config/nc/depot").unlink()
        self.assertEqual(self.lancer("energie").returncode, 1)

    def test_kitty_introuvable_dit_comment_faire(self):
        vide = self.r / "vide"
        vide.mkdir()
        r = self.lancer("killswitch", PATH=str(vide))
        self.assertEqual(r.returncode, 1)
        self.assertIn("kitty est introuvable", r.stderr)
        self.assertIn("./install.sh --seulement killswitch", r.stderr)


class Seulement(Base):
    """install.sh --seulement : une étape, une question, les mêmes contrôles."""

    def setUp(self):
        super().setUp()
        # sudo : note ses arguments, ne lance rien ; « grep » (règle déjà posée ?) répond non
        faux(self.bin, "sudo", 'echo "sudo $*" >> "$FAUX_JOURNAL"\n[ "$1" = grep ] && exit 1\nexit 0')
        # stat : note l'appel, dit que le dossier est à root (uid 0, droits 755) sauf FAUX_UID
        # (le clone de l'essai, lui, est regardé pour de vrai : /usr/bin/stat)
        faux(self.bin, "stat", 'echo "stat $*" >> "$FAUX_JOURNAL"\ncase "${@: -1}" in "$CLONE_ESSAI"*) exec /usr/bin/stat "$@" ;; esac\ncase "$*" in *%u*) echo "${FAUX_UID:-0}" ;; *) echo 755 ;; esac')
        self.clone = self.r / "clone-essai"
        self.faire_clone(self.clone)
        self.install = self.clone / "install.sh"
        self.env["CLONE_ESSAI"] = str(self.clone)
        faux(self.bin, "nft", "exit 0")                      # nftables « présent » : aucun paquet à proposer dans ces essais
        for nom in ("pacman", "apt-get", "dnf", "zypper", "systemctl"):
            faux(self.bin, nom, f'echo "{nom} $*" >> "$FAUX_JOURNAL"')

    def git(self, d, *args):
        subprocess.run(["git", "-c", "user.name=essai", "-c", "user.email=essai@example.invalid", "-C", str(d), *args], check=True,
                       capture_output=True, env={"PATH": "/usr/bin:/bin", "HOME": str(self.home), "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_SYSTEM": "/dev/null"})

    def faire_clone(self, d):
        """Un VRAI petit dépôt git : install.sh et system/ du dépôt, un commit."""
        d.mkdir()
        shutil.copy(INSTALL, d / "install.sh")
        shutil.copytree(REPO / "system", d / "system")
        d.chmod(0o755)
        self.git(d, "init", "-q")
        self.git(d, "add", "install.sh", "system")
        self.git(d, "commit", "-q", "-m", "Commit d'essai")

    def sans_terminal(self, *args, **plus):
        r = subprocess.run(["bash", str(self.install), *args], env=dict(self.env, **plus), capture_output=True, text=True, stdin=subprocess.DEVNULL,
                           start_new_session=True, timeout=60)
        return r

    def avec_terminal(self, args, reponse, **plus):
        env = dict(self.env, **plus)
        pid, fd = pty.fork()
        if pid == 0:
            os.execvpe("bash", ["bash", str(self.install), *args], env)
        os.write(fd, reponse.encode())
        sortie = b""
        while True:
            pret, _, _ = select.select([fd], [], [], 60)
            if not pret:
                os.kill(pid, 9)
                self.fail("délai dépassé : " + sortie.decode(errors="replace"))
            try:
                bloc = os.read(fd, 4096)
            except OSError:
                break
            if not bloc:
                break
            sortie += bloc
        _, statut = os.waitpid(pid, 0)
        return os.waitstatus_to_exitcode(statut), sortie.decode(errors="replace")

    def appels_sudo(self):
        return [l for l in self.log().splitlines() if l.startswith("sudo ")]

    # ── sans terminal : non par défaut, --oui n'y change rien ──
    def test_sans_terminal_refuse_meme_avec_oui(self):
        for etape in ("killswitch", "energie"):
            for extra in ([], ["--oui"]):
                self.journal.write_text("")
                r = self.sans_terminal("--seulement", etape, *extra)
                self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
                self.assertIn("réponse par défaut (n)", r.stdout, r.stdout)
                self.assertEqual(r.stdout.count("réponse par défaut"), 1, "une seule question : " + r.stdout)
                self.assertNotIn("sudo install", self.log(), (etape, extra))
                self.assertNotIn("visudo", self.log(), (etape, extra))
                self.assertNotIn("mv -f", self.log(), (etape, extra))

    def test_forme_avec_egal_et_option_apres(self):
        r = self.sans_terminal("--oui", "--seulement=killswitch")
        self.assertIn("réponse par défaut (n)", r.stdout)
        self.assertNotIn("visudo", self.log())

    # ── avec un terminal ──
    def test_killswitch_entree_vide_ne_pose_rien(self):
        code, sortie = self.avec_terminal(["--seulement", "killswitch"], "\n")
        self.assertEqual(code, 0, sortie)
        self.assertIn("[o/N]", sortie)
        self.assertIn("firewalld", sortie)                               # annoncé avant la question
        self.assertEqual(sortie.count("[o/N]") + sortie.count("[O/n]"), 1, "une seule question : " + sortie)
        self.assertNotIn("visudo", self.log())
        self.assertNotIn("install -Dm0755", self.log())

    def test_killswitch_oui_memes_controles(self):
        code, sortie = self.avec_terminal(["--seulement", "killswitch"], "o\n")
        self.assertEqual(code, 0, sortie)
        self.assertEqual(sortie.count("[o/N]") + sortie.count("[O/n]"), 1, "une seule question : " + sortie)
        j = self.log().splitlines()
        stats = [i for i, l in enumerate(j) if l.startswith("stat ")]
        poses = [i for i, l in enumerate(j) if l.startswith("sudo install -Dm0755") and "/usr/local/bin/nc-vpn-root" in l]
        visudo = [i for i, l in enumerate(j) if l.startswith("sudo visudo -cf /etc/sudoers.d/nc-vpn.tmp")]
        mv = [i for i, l in enumerate(j) if l.startswith("sudo mv -f /etc/sudoers.d/nc-vpn.tmp /etc/sudoers.d/nc-vpn")]
        self.assertTrue(stats and poses and visudo and mv, self.log())
        self.assertLess(max(stats), poses[0], "dossiers_root_surs avant la pose")
        self.assertLess(poses[0], visudo[0])
        self.assertLess(visudo[0], mv[0])
        self.assertNotIn("nc-energie", self.log())
        for gestionnaire in ("pacman", "apt-get", "dnf", "zypper", "systemctl"):
            self.assertNotIn(gestionnaire + " ", self.log().replace("sudo ", ""), "aucun paquet, aucun service")
        self.assertIn("installé", sortie)

    def test_energie_oui_memes_controles(self):
        code, sortie = self.avec_terminal(["--seulement", "energie"], "o\n")
        self.assertEqual(code, 0, sortie)
        self.assertEqual(sortie.count("[o/N]") + sortie.count("[O/n]"), 1, "une seule question : " + sortie)
        j = self.log()
        self.assertIn("sudo install -Dm0755 -o root -g root " + str(self.clone / "system/nc-energie-root") + " /usr/local/bin/nc-energie-root", j)
        self.assertIn("sudo visudo -cf /etc/sudoers.d/nc-energie.tmp", j)
        self.assertIn("stat ", j)
        self.assertNotIn("nc-vpn", j)

    def test_energie_entree_vide_ne_pose_rien(self):
        code, sortie = self.avec_terminal(["--seulement", "energie", "--oui"], "\n")
        self.assertEqual(code, 0, sortie)
        self.assertNotIn("visudo", self.log())
        self.assertNotIn("install -Dm0755", self.log())

    def test_dossier_non_sur_refuse(self):
        code, sortie = self.avec_terminal(["--seulement", "killswitch"], "o\n", FAUX_UID="1000")
        self.assertEqual(code, 0, sortie)
        self.assertIn("Assistant root non posé", sortie)
        self.assertNotIn("visudo", self.log())
        self.assertNotIn("install -Dm0755", self.log())

    # ── garde du clone avant de poser un assistant root ──
    def pose(self):
        return "install -Dm0755" in self.log()

    def modifier(self, etape):
        with open(self.clone / "system" / ("nc-vpn-root" if etape == "killswitch" else "nc-energie-root"), "a") as f:
            f.write("\n# modif\n")

    def test_clone_propre_affiche_chemin_et_commit(self):
        code, sortie = self.avec_terminal(["--seulement", "killswitch"], "o\n")
        self.assertEqual(code, 0, sortie)
        self.assertIn(str(self.clone), sortie)
        self.assertIn("Commit d'essai", sortie)
        self.assertNotIn("modifications locales", sortie)
        self.assertEqual(sortie.count("[o/N]"), 1, sortie)
        self.assertTrue(self.pose(), self.log())

    def test_system_modifie_question_a_part_entree_vide_non(self):
        for etape in ("killswitch", "energie"):
            self.journal.write_text("")
            self.modifier(etape)
            code, sortie = self.avec_terminal(["--seulement", etape], "\n")
            self.assertEqual(code, 0, sortie)
            self.assertIn("modifications locales non validées", sortie)
            self.assertIn("nc-" + ("vpn" if etape == "killswitch" else "energie") + "-root", sortie)
            self.assertFalse(self.pose(), sortie)
            self.git(self.clone, "checkout", "--", "system")

    def test_system_modifie_deux_oui_puis_pose(self):
        self.modifier("killswitch")
        code, sortie = self.avec_terminal(["--seulement", "killswitch"], "o\no\n")
        self.assertEqual(code, 0, sortie)
        self.assertEqual(sortie.count("[o/N]"), 2, "deux questions : " + sortie)
        self.assertTrue(self.pose(), sortie)

    def test_system_modifie_puis_non_a_la_seconde(self):
        self.modifier("energie")
        code, sortie = self.avec_terminal(["--seulement", "energie"], "o\nn\n")
        self.assertEqual(sortie.count("[o/N]"), 2, sortie)
        self.assertFalse(self.pose(), sortie)

    def test_fichier_non_suivi_meme_garde(self):
        (self.clone / "system/intrus.sh").write_text("x\n")
        code, sortie = self.avec_terminal(["--seulement", "energie"], "\n")
        self.assertIn("modifications locales non validées", sortie)
        self.assertIn("intrus.sh", sortie)
        self.assertFalse(self.pose(), sortie)

    def test_oui_n_accepte_pas_les_modifications(self):
        self.modifier("killswitch")
        r = self.sans_terminal("--seulement", "killswitch", "--oui")
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("modifications locales non validées", r.stdout)
        self.assertIn("réponse par défaut (n)", r.stdout)
        self.assertFalse(self.pose(), r.stdout)

    def refus(self, attendu, etape="killswitch"):
        code, sortie = self.avec_terminal(["--seulement", etape], "o\n")
        self.assertEqual(code, 0, sortie)           # refus clair, mais le reste d'une installation complète continuerait
        self.assertIn("Assistant root non posé", sortie)
        self.assertIn(attendu, sortie)
        self.assertNotIn("[o/N]", sortie)
        self.assertFalse(self.pose(), sortie)
        self.assertNotIn("visudo", self.log())

    def test_dossier_ecrivable_par_le_groupe_refuse(self):
        self.clone.chmod(0o775)
        self.refus("groupe")
        self.clone.chmod(0o757)
        self.refus("groupe", "energie")

    def test_sans_git_dans_le_clone_refuse(self):
        shutil.rmtree(self.clone / ".git")
        self.refus("clone git")

    def test_clone_lien_refuse(self):
        lien = self.r / "lien"
        lien.symlink_to(self.clone)
        self.install = lien / "install.sh"
        self.refus("pas un vrai dossier")

    def test_proprietaire_autre_refuse(self):
        faux(self.bin, "id", 'if [ "$1" = -u ]; then echo 4242; else exec /usr/bin/id "$@"; fi')
        self.refus("n'appartient pas")

    def test_git_absent_refuse(self):
        sain = self.r / "sain"
        sain.mkdir()
        for c in ("bash", "dirname", "cat", "cmp", "mktemp", "rm", "id", "head", "paste", "sort", "grep", "sed", "awk", "tr", "cut", "date", "env", "uname", "mkdir", "timeout"):
            f = shutil.which(c)
            if f:
                (sain / c).symlink_to(f)
        for c in ("sudo", "stat", "nft"):
            (sain / c).symlink_to(self.bin / c)
        code, sortie = self.avec_terminal(["--seulement", "killswitch"], "o\n", PATH=str(sain))
        self.assertIn("git est absent", sortie)
        self.assertFalse(self.pose(), sortie)

    def test_garde_dans_les_deux_etapes_et_installation_complete_continue(self):
        src = INSTALL.read_text()
        self.assertIn('[ -n "$ligne_e" ] && garde_clone_assistant && ask', src)
        self.assertIn('[ -n "$ligne_v" ] && garde_clone_assistant && ask', src)
        # appelée dans une condition : un refus (retour 1) n'arrête pas l'installation complète, l'étape suivante part
        self.assertIn("  if [ \"$LAPTOP\" = 1 ]; then etape_energie_root; fi\n  etape_killswitch_root\n", src)

    def test_aucune_autre_etape(self):
        code, sortie = self.avec_terminal(["--seulement", "killswitch"], "\n")
        for autre in ("Vérifications", "5a.", "Terminé", "Écran", "Copie", "paquets"):
            self.assertNotIn(autre, sortie, autre)
        self.assertFalse((self.home / ".config").exists() and any((self.home / ".config").iterdir()), "aucun fichier copié")
        self.assertFalse((self.home / ".local/state/noctalia-config").exists())

    def test_options_invalides(self):
        for args in (["--seulement", "bidule"], ["--seulement"], ["--seulement="]):
            r = self.sans_terminal(*args)
            self.assertNotEqual(r.returncode, 0, args)
            self.assertEqual(self.appels_sudo(), [])

    def test_aide_et_sources(self):
        r = self.sans_terminal("--help")
        self.assertIn("--seulement killswitch | energie", r.stdout)
        r = self.sans_terminal("--help", NC_LANGUE="en")
        self.assertIn("--seulement killswitch | energie", r.stdout)
        src = INSTALL.read_text()
        self.assertIn("etape_killswitch_root() {", src)
        self.assertIn("etape_energie_root() {", src)
        self.assertEqual(src.count("ask \"$(t \"Installer l'assistant du kill switch VPN ?\""), 1, "la question n'existe qu'une fois")


class LigneSudoers(unittest.TestCase):
    """La ligne sudoers imprimée par un assistant (peut-être modifié localement) n'est posée que de la forme exacte attendue."""
    def fonction(self):
        src = INSTALL.read_text()
        i = src.index("ligne_sudoers_sure() {")
        return src[i:src.index("\n}\n", i) + 3]

    def sure(self, outil, ligne):
        r = subprocess.run(["bash", "-c", self.fonction() + '\nligne_sudoers_sure user "$1" "$2"', "_", outil, ligne],
                           capture_output=True, text=True, timeout=10, env={"PATH": "/usr/bin:/bin"})
        return r.returncode == 0

    def vraie(self, assistant, interp):
        r = subprocess.run([interp, str(REPO / "system" / assistant), "sudoers", "user"], capture_output=True, text=True,
                           timeout=10, env={"PATH": "/usr/bin:/bin"})
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout.strip()

    def test_vraies_lignes_acceptees(self):
        self.assertTrue(self.sure("nc-vpn-root", self.vraie("nc-vpn-root", sys.executable)))
        self.assertTrue(self.sure("nc-energie-root", self.vraie("nc-energie-root", "sh")))

    def test_lignes_piegees_refusees(self):
        b = "user ALL=(root) NOPASSWD: "
        for outil, ligne in (("nc-vpn-root", "ALL ALL=(ALL) NOPASSWD: ALL"),
                             ("nc-vpn-root", "user ALL=(ALL) NOPASSWD: /usr/local/bin/nc-vpn-root etat"),
                             ("nc-vpn-root", b + "/usr/local/bin/nc-vpn-root etat, /bin/sh"),
                             ("nc-vpn-root", b + "/usr/local/bin/nc-vpn-root *"),
                             ("nc-energie-root", b + "/usr/local/bin/nc-energie-root activer *"),
                             ("nc-vpn-root", b + "/usr/local/bin/nc-vpn-root etat\nALL ALL=(ALL) NOPASSWD: ALL"),
                             ("nc-vpn-root", "autre ALL=(root) NOPASSWD: /usr/local/bin/nc-vpn-root etat"),
                             ("nc-vpn-root", b + "/usr/local/bin/nc-vpn-root-x etat"),
                             ("nc-vpn-root", b + "/usr/local/bin/nc-vpn-root etat, /usr/local/bin/nc-vpn-root ../x"),
                             ("nc-vpn-root", b + "/usr/local/bin/nc-vpn-root etat, "),
                             ("nc-vpn-root", b)):
            self.assertFalse(self.sure(outil, ligne), ligne)

    def test_verifiee_avant_la_question(self):
        src = INSTALL.read_text()
        for var, outil in (("ligne_e", "nc-energie-root"), ("ligne_v", "nc-vpn-root")):
            i = src.index(f'! ligne_sudoers_sure "$(id -un)" {outil} "${var}"')
            self.assertLess(i, src.index(f'elif [ -n "${var}" ] && garde_clone_assistant && ask', i))


if __name__ == "__main__":
    unittest.main()

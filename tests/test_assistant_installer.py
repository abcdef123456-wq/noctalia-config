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
        faux(self.bin, "stat", 'echo "stat $*" >> "$FAUX_JOURNAL"\ncase "$*" in *%u*) echo "${FAUX_UID:-0}" ;; *) echo 755 ;; esac')
        faux(self.bin, "nft", "exit 0")                      # nftables « présent » : aucun paquet à proposer dans ces essais
        for nom in ("pacman", "apt-get", "dnf", "zypper", "systemctl"):
            faux(self.bin, nom, f'echo "{nom} $*" >> "$FAUX_JOURNAL"')

    def sans_terminal(self, *args, **plus):
        r = subprocess.run(["bash", str(INSTALL), *args], env=dict(self.env, **plus), capture_output=True, text=True, stdin=subprocess.DEVNULL,
                           start_new_session=True, timeout=60)
        return r

    def avec_terminal(self, args, reponse, **plus):
        env = dict(self.env, **plus)
        pid, fd = pty.fork()
        if pid == 0:
            os.execvpe("bash", ["bash", str(INSTALL), *args], env)
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
        self.assertIn("sudo install -Dm0755 -o root -g root " + str(REPO / "system/nc-energie-root") + " /usr/local/bin/nc-energie-root", j)
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


if __name__ == "__main__":
    unittest.main()

"""install.sh : pose_regle dit la vraie cause d'un échec (sudo sans mot de passe, copie, visudo), et l'étape batterie
est sautée sans terminal ni sudo autorisé. Faux sudo seulement : rien de réel n'est lancé ni copié."""
import os
import pty
import re
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SOURCE = (REPO / "install.sh").read_text()
DEBUT = SOURCE[SOURCE.index("sans_tty() {"):SOURCE.index("ask() {")]
POSE = SOURCE[SOURCE.index("pose_regle() {"):SOURCE.index("# Code de sortie d'un")]
BATTERIE = SOURCE[SOURCE.index('  if [ "$LAPTOP" = 1 ] && [ "$("$REPO/system/nc-limite-charge" etat'):SOURCE.index("  # Assistants root facultatifs")]
# Faux sudo : note l'appel ; FAUX_ECHEC=auth fait échouer « -n » et « -v », copie « install », visudo « visudo ».
# « -n » (demandé par le script, ou forcé sans terminal ni fenêtre) ne passe que si sudo est déjà autorisé (FAUX_N=1)
SUDO = '''echo "sudo $*" >> "$FAUX_JOURNAL"
n=0; [ "$1" = -n ] && { n=1; shift; }
[ "$n" = 1 ] && { [ "$FAUX_ECHEC" = auth ] || [ "${FAUX_N:-0}" = 0 ]; } && exit 1
case "$FAUX_ECHEC:$1" in auth:-v|copie:install|visudo:visudo) exit 1 ;; esac
[ "$1" = grep ] && exit 1
exit 0'''
PRE = '''t() { [ "${NC_LANGUE:-}" = fr ] && printf '%s' "$1" || printf '%s' "$2"; }
info() { echo "INFO $*"; }; warn() { echo "WARN $*"; }; ok() { echo "OK $*"; }
ask() { echo "QUESTION"; return 1; }
'''


class PoseRegle(unittest.TestCase):
    def setUp(self):
        os.makedirs("/tmp/claude-1000", exist_ok=True)
        tmp = tempfile.TemporaryDirectory(prefix="nc-pr-", dir="/tmp/claude-1000")
        self.addCleanup(tmp.cleanup)
        self.r = Path(tmp.name)
        self.journal = self.r / "journal.txt"
        (self.r / "bin").mkdir()
        for nom, corps in (("sudo", SUDO), ("mktemp", f'echo {self.r}/tmp-regle')):
            p = self.r / "bin" / nom
            p.write_text("#!/usr/bin/env bash\n" + corps + "\n")
            p.chmod(p.stat().st_mode | stat.S_IEXEC)
        (self.r / "system").mkdir()
        lim = self.r / "system/nc-limite-charge"
        lim.write_text("#!/bin/sh\necho present\n")
        lim.chmod(0o755)
        self.env = {"HOME": str(self.r), "XDG_CONFIG_HOME": str(self.r), "XDG_STATE_HOME": str(self.r), "XDG_DATA_HOME": str(self.r),
                    "XDG_CACHE_HOME": str(self.r), "XDG_RUNTIME_DIR": str(self.r), "TMPDIR": str(self.r), "NC_LANGUE": "fr",
                    "PATH": f"{self.r}/bin:/usr/bin:/bin", "FAUX_JOURNAL": str(self.journal), "REPO": str(self.r)}

    def lancer(self, corps, tty=False, **plus):
        script = "NC_UI=0\n" + PRE + DEBUT + POSE + corps
        env = dict(self.env, **plus)
        if not tty:
            r = subprocess.run(["bash", "-c", script], env=env, capture_output=True, text=True, stdin=subprocess.DEVNULL,
                               start_new_session=True, timeout=30)
            return r.stdout + r.stderr
        pid, fd = pty.fork()
        if pid == 0:
            os.execvpe("bash", ["bash", "-c", script], env)
        sortie = b""
        while True:
            try:
                d = os.read(fd, 4096)
            except OSError:
                break
            if not d:
                break
            sortie += d
        os.waitpid(pid, 0)
        return sortie.decode(errors="replace")

    APPEL = 'pose_regle /home/user/r /home/user/sudoers.d/x /home/user/src /home/user/bin/x || echo "CAUSE $NC_CAUSE"\n'

    def log_brut(self):
        return self.journal.read_text() if self.journal.exists() else ""

    def log(self):
        """Le journal sans le « -n » forcé hors terminal, et sans les sondes « sudo -n true »."""
        lignes = [re.sub(r"^sudo (-n )+", "sudo ", l) for l in self.log_brut().splitlines()]
        return "\n".join(l for l in lignes if l != "sudo true")

    def test_authentification_impossible_sans_terminal(self):
        sortie = self.lancer(self.APPEL, FAUX_ECHEC="auth")
        self.assertIn("sudo n'a pas pu vérifier ton mot de passe (pas de terminal, ou mot de passe refusé)", sortie)
        self.assertNotIn("visudo", self.log())
        self.assertNotIn("install", self.log())

    def test_mot_de_passe_refuse_avec_terminal(self):
        sortie = self.lancer(self.APPEL, tty=True, FAUX_ECHEC="auth")
        self.assertIn("sudo n'a pas pu vérifier ton mot de passe", sortie)
        self.assertIn("sudo -v", self.log())
        self.assertNotIn("visudo", self.log())

    def test_mode_graphique_sans_terminal_sudo_demande_par_sa_fenetre(self):
        """Installeur graphique : pas de terminal, mais SUDO_ASKPASS. sudo doit être essayé (« -v »), pas refusé d'avance."""
        sortie = self.lancer(self.APPEL, SUDO_ASKPASS="/home/user/nc-askpass")
        self.assertNotIn("CAUSE", sortie)
        self.assertIn("sudo -v", self.log())
        self.assertIn("sudo mv", self.log())

    def test_sans_terminal_ni_fenetre_tout_sudo_porte_n(self):
        """nc-maj lancé sans terminal : un sudo qui « demande » échoue ET compte comme un mot de passe faux (pam_faillock,
        compte verrouillé au 3e). Tous les appels du script et de ses sous-scripts bash portent donc -n."""
        self.lancer("sudo grep -q x /home/user/y; sudo install a b; bash -c 'sudo cmp a b'; true\n")
        lignes = self.log_brut().splitlines()
        self.assertEqual(len(lignes), 3, lignes)
        self.assertTrue(all(l.startswith("sudo -n ") for l in lignes), lignes)

    def test_avec_un_moyen_de_demander_sudo_inchange(self):
        for plus in ({"SUDO_ASKPASS": "/home/user/nc-askpass"}, {"tty": True}):
            with self.subTest(plus):
                self.journal.unlink(missing_ok=True)
                self.lancer("sudo grep -q x /home/user/y; true\n", **plus)
                self.assertEqual(self.log_brut().splitlines(), ["sudo grep -q x /home/user/y"])

    def test_copie_echoue(self):
        sortie = self.lancer(self.APPEL, FAUX_ECHEC="copie", FAUX_N="1")
        self.assertIn("la copie d'un fichier a échoué", sortie)
        self.assertNotIn("visudo", sortie)
        self.assertIn("sudo rm -f /home/user/sudoers.d/x.tmp", self.log())

    def test_visudo_refuse(self):
        sortie = self.lancer(self.APPEL, FAUX_ECHEC="visudo", FAUX_N="1")
        self.assertIn("visudo a refusé la règle sudo", sortie)
        self.assertIn("sudo rm -f /home/user/sudoers.d/x.tmp", self.log())
        self.assertNotIn("sudo mv", self.log())

    def test_succes_ordre_des_controles(self):
        sortie = self.lancer(self.APPEL, FAUX_N="1")
        self.assertNotIn("CAUSE", sortie)
        j = self.log().splitlines()
        self.assertEqual([l.split()[1] for l in j], ["install", "install", "visudo", "mv"], j)

    def test_anglais(self):
        sortie = self.lancer(self.APPEL, NC_LANGUE="en", FAUX_ECHEC="visudo", FAUX_N="1")
        self.assertIn("visudo rejected the sudo rule", sortie)

    # ── étape batterie ──
    BATT = 'LAPTOP=1; REPO="$REPO"; regle=/home/user/sudoers.d/nc-limite-charge\n' + BATTERIE + "\n"

    def test_batterie_sautee_sans_terminal_ni_sudo(self):
        sortie = self.lancer(self.BATT)
        self.assertIn("à faire dans un terminal : nc-maj", sortie)
        self.assertNotIn("QUESTION", sortie)
        self.assertNotIn("sudo install", self.log())

    def test_batterie_demandee_sans_terminal_si_sudo_deja_autorise(self):
        sortie = self.lancer(self.BATT, FAUX_N="1")
        self.assertIn("QUESTION", sortie)
        self.assertNotIn("nc-maj", sortie)

    def test_batterie_demandee_en_mode_graphique(self):
        sortie = self.lancer(self.BATT, SUDO_ASKPASS="/home/user/nc-askpass")
        self.assertIn("QUESTION", sortie)
        self.assertNotIn("nc-maj", sortie)

    def test_batterie_demandee_avec_terminal(self):
        sortie = self.lancer(self.BATT, tty=True)
        self.assertIn("QUESTION", sortie)
        self.assertNotIn("nc-maj", sortie)


if __name__ == "__main__":
    unittest.main()

"""install.sh sans terminal : options non interactives de pacman et zypper, étapes sensibles refusées, choix polkit.

Aucun paquet ni service touché : faux sudo, pacman et systemctl dans un dossier temporaire.
"""
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
# De sans_tty() à pkg_installed() : sans_tty, ask, ANNULE, sonder, pacman_s… (jusqu'avant les familles de paquets)
DEBUT = SOURCE[SOURCE.index("sans_tty() {"):SOURCE.index("choisir() {")]
PACMAN_S = SOURCE[SOURCE.index("pacman_s() {"):SOURCE.index("pkg_installed() {")]
POLKIT = SOURCE[SOURCE.index("POLKIT=true; KDE_POLKIT=0"):SOURCE.index("# Nom affiché au démarrage (GRUB)")]
PREAMBULE = r'''
set -euo pipefail
OUI="${OUI:-0}"; NC_LANGUE=fr
t() { printf '%s' "$1"; }
info() { printf '   %s\n' "$*"; }
warn() { printf '   ! %s\n' "$*"; }
'''


def outil(dossier, nom, corps):
    p = Path(dossier) / nom
    p.write_text("#!/usr/bin/env bash\n" + corps + "\n")
    p.chmod(p.stat().st_mode | stat.S_IEXEC)


def sans_tty(script, env=None, args=()):
    """Lance bash sans terminal de contrôle (nouvelle session) : /dev/tty est inutilisable."""
    e = dict(os.environ, **(env or {}))
    return subprocess.run(["bash", "-c", script, "x", *args], capture_output=True, text=True, stdin=subprocess.DEVNULL,
                          start_new_session=True, env=e, timeout=30)


def avec_tty(script, env=None):
    """Lance bash avec un vrai terminal de contrôle (pty) ; renvoie (code, sortie)."""
    e = dict(os.environ, **(env or {}))
    pid, fd = pty.fork()
    if pid == 0:
        os.execvpe("bash", ["bash", "-c", script], e)
    sortie = b""
    try:
        while True:
            try:
                d = os.read(fd, 4096)
            except OSError:
                break
            if not d:
                break
            sortie += d
    finally:
        _, st = os.waitpid(pid, 0)
    return os.waitstatus_to_exitcode(st), sortie.decode(errors="replace")


class AskSansTerminal(unittest.TestCase):
    def lance(self, appel, oui="0"):
        return sans_tty(PREAMBULE + DEBUT + appel, {"OUI": oui})

    def test_question_ordinaire_garde_son_defaut_oui(self):
        self.assertEqual(self.lance('ask "Q ?" o').returncode, 0)
        self.assertEqual(self.lance('ask "Q ?" n').returncode, 1)

    def test_etape_sensible_non_par_defaut(self):
        r = self.lance('ask "Q ?" o sensible')
        self.assertEqual(r.returncode, 1)
        self.assertIn("--oui", r.stdout)

    def test_etape_sensible_oui_avec_option(self):
        self.assertEqual(self.lance('ask "Q ?" o sensible', oui="1").returncode, 0)
        # --oui ne change pas un défaut « non » (Plymouth)
        self.assertEqual(self.lance('ask "Q ?" n sensible', oui="1").returncode, 1)

    def test_sensibles_du_script(self):
        # Démarrage, connexion, pilotes : tous marqués « sensible »
        for debut in ("Mettre à jour le thème GRUB", "Installer l'écran de démarrage", "Le télécharger (et ses modules Qt)",
                      "Installer l'écran de connexion", "Installer le pilote officiel de NVIDIA",
                      "La carte NVIDIA reste allumée"):
            m = re.search(r'ask "\$\(t "' + re.escape(debut) + r'.*?"\)" ([on])( sensible)?', SOURCE)
            self.assertTrue(m, debut)
            self.assertEqual(m.group(2), " sensible", debut)

    def test_chsh_saute_sans_terminal(self):
        i = SOURCE.index("Faire de zsh ton shell par défaut")
        bloc = SOURCE[i - 400:i]
        self.assertIn("if sans_tty; then", bloc)

    def test_aide_et_option(self):
        self.assertIn("--oui", SOURCE[:SOURCE.index("set -euo pipefail")])
        self.assertIn("--oui | --yes", SOURCE)
        self.assertIn("--oui|--yes)", SOURCE)
        self.assertIn("--oui", (REPO / "README.md").read_text())


class PacmanZypper(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        d = self.tmp.name
        self.journal = Path(d) / "appels"
        outil(d, "sudo", 'exec "$@"')
        outil(d, "pacman", 'echo "pacman $*" >> "$NC_APPELS"')

    def appel(self, runner):
        env = {"PATH": self.tmp.name + ":" + os.environ["PATH"], "NC_APPELS": str(self.journal)}
        script = PREAMBULE + DEBUT + PACMAN_S + 'pacman_s noctalia tlp'
        r = runner(script, env)
        return r, self.journal.read_text() if self.journal.exists() else ""

    def test_noconfirm_sans_terminal(self):
        r, vu = self.appel(sans_tty)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("pacman -S --needed --noconfirm noctalia tlp", vu)

    def test_confirmation_gardee_au_terminal(self):
        (code, sortie), vu = avec_tty_appel(self)
        self.assertEqual(code, 0, sortie)
        self.assertIn("pacman -S --needed noctalia tlp", vu)
        self.assertNotIn("--noconfirm", vu)

    def test_aucun_pacman_ni_zypper_sans_option_dans_le_script(self):
        for n, ligne in enumerate(SOURCE.splitlines(), 1):
            code = ligne.split("#", 1)[0]
            # « sudo pacman -S » nu : seulement dans pacman_s lui-même (deux formes, avec et sans --noconfirm) et pkg_try
            if re.search(r"\bpacman -S\b", code) and "pacman_s()" not in code and "--noconfirm" not in code:
                self.assertRegex(code, r"^\s*if sans_tty; then sudo pacman|else sudo pacman -S --needed \"\$@\"", f"ligne {n} : {ligne}")
            for m in re.finditer(r"\bsudo zypper\b(.*?)(&&|\|\||;|$)", code):
                if m.group(1).split()[:1] and re.match(r"\s*(-\S+\s+)*(info|se|search)\b", m.group(1)):
                    continue
                self.assertIn("--non-interactive", m.group(1), f"ligne {n} : {ligne}")


def avec_tty_appel(cas):
    d = cas.tmp.name
    env = {"PATH": d + ":" + os.environ["PATH"], "NC_APPELS": str(cas.journal)}
    res = avec_tty(PREAMBULE + DEBUT + PACMAN_S + "pacman_s noctalia tlp", env)
    return res, cas.journal.read_text() if cas.journal.exists() else ""


class Telechargements(unittest.TestCase):
    def test_nouvel_essai_et_delai(self):
        # Un miroir lent ou une coupure d'un instant ne doit ni tout arrêter (set -e) ni bloquer sans fin
        for ligne in SOURCE.splitlines():
            code = ligne.split("#", 1)[0]
            if re.search(r"\bwget\s+-", code):
                self.assertIn("--tries=3", code, ligne)
                self.assertRegex(code, r"--timeout=\d+", ligne)
            if re.search(r"\bcurl\s+-", code):
                self.assertIn("--retry 3", code, ligne)
                self.assertIn("--max-time", code, ligne)


class CompilationQuickshell(unittest.TestCase):
    def test_libegl_dans_les_dependances(self):
        i = SOURCE.index("compiler_quickshell() {")
        self.assertIn("libegl-dev", SOURCE[i:i + 2500], "cmake cherche egl.pc, absent sur Debian 13 neuve sans libegl-dev")

    def test_echec_dit_clairement(self):
        i = SOURCE.index("compiler_quickshell() {")
        bloc = SOURCE[i:SOURCE.index("# L'île Quickshell pour tout le monde")]
        self.assertIn("Quickshell n'a pas pu être compilé", bloc)
        self.assertIn("Quickshell could not be built", bloc)
        self.assertIn("Could NOT find", bloc, "le paquet que cmake n'a pas trouvé est tiré du journal")
        self.assertIn("tail -n 8", bloc)

    def test_extraction_du_paquet_manquant(self):
        with tempfile.TemporaryDirectory() as d:
            log = Path(d) / "cmake.log"
            log.write_text("-- x\n  Package 'egl', required by 'virtual:world', not found\nCould NOT find Foo (missing: Bar)\n")
            i = SOURCE.index('cmake_manque="$(')
            ligne = SOURCE[i:SOURCE.index("\n", i)].replace('"$wd/cmake.log"', f'"{log}"')
            r = subprocess.run(["bash", "-c", ligne + '\necho "$cmake_manque"'], capture_output=True, text=True)
            self.assertEqual(r.stdout.strip(), "Foo egl")      # LC_ALL=C : le même ordre sur toutes les machines


class ChoixPolkit(unittest.TestCase):
    """L'agent KDE n'est « installé » que si son unité existe : le dossier .service.d du dépôt ne compte pas."""
    SONDE = SOURCE[SOURCE.index("sonder() {"):SOURCE.index("choisir() {")]

    def lance(self, systemctl):
        with tempfile.TemporaryDirectory() as d:
            outil(d, "systemctl", systemctl)
            script = PREAMBULE + self.SONDE + POLKIT + 'echo "POLKIT=$POLKIT KDE=$KDE_POLKIT"'
            r = sans_tty(script, {"PATH": d + ":" + os.environ["PATH"]})
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout.strip().splitlines()[-1]

    def test_dropin_seul_ne_coupe_pas_l_agent_de_noctalia(self):
        # « cat » réussit avec le seul drop-in (affiche son fichier) ; list-unit-files ne liste rien
        fake = '''case "$*" in
  *list-unit-files*) exit 1 ;;
  *cat*) echo "# ~/.config/systemd/user/plasma-polkit-agent.service.d/nc-apres-session.conf"; exit 0 ;;
esac'''
        self.assertEqual(self.lance(fake), "POLKIT=true KDE=0")

    def test_aucune_unite(self):
        self.assertEqual(self.lance("exit 1"), "POLKIT=true KDE=0")

    def test_vrai_agent_kde_garde_polkit_false(self):
        fake = '''case "$*" in
  *list-unit-files*) echo "plasma-polkit-agent.service static -"; exit 0 ;;
esac'''
        self.assertEqual(self.lance(fake), "POLKIT=false KDE=1")


if __name__ == "__main__":
    unittest.main()

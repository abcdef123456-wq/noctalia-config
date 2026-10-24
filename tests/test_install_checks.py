"""Vérifications réelles de l'installateur avec de faux outils ; aucun paquet/service modifié."""
import os
from pathlib import Path
import shutil
import signal
import subprocess
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
SOURCE = (REPO / 'install.sh').read_text()
SONDE = SOURCE[SOURCE.index('sonder() {'):SOURCE.index('choisir() {')]
CHECKS = SOURCE[SOURCE.index('# ── Vérifications'):SOURCE.index('\necho\ninfo "$(t "Ce script va :')]

OUTIL = r'''#!/usr/bin/env python3
import json,os,signal,sys,time
from pathlib import Path
nom=Path(sys.argv[0]).name; args=sys.argv[1:]
with Path(os.environ['NC_TEST_CALLS']).open('a') as f:f.write(json.dumps([nom,*args])+'\n')
mode=os.environ.get('NC_TEST_CASE','')
if nom=='Hyprland':
 if mode=='hypr-hang':time.sleep(60)
 print('Hyprland 0.54.0' if mode.startswith('dnf-') else 'Hyprland 0.56.2')
elif nom in ('rpm','pacman','dpkg-query'):
 print('hyprland 0.56.2' if nom=='pacman' else '0.56.2')
elif nom=='noctalia':
 if mode=='noctalia-status-ignore-term' and args==['msg','status']:
  signal.signal(signal.SIGTERM,signal.SIG_IGN);time.sleep(60)
 if (mode=='noctalia-version-hang' and args==['--version']) or (mode=='noctalia-status-hang' and args==['msg','status']):time.sleep(60)
 print('noctalia v5.3.0' if args==['--version'] else json.dumps(dict(locked=mode=='locked')))
elif nom=='dnf':
 if mode=='dnf-hang':time.sleep(60)
 if mode=='dnf-error':sys.exit(1)
 print('0.56.2')
elif nom=='hyprctl':
 if mode=='display-hang':time.sleep(60)
 print('[]')
elif nom=='localectl':
 if mode=='keyboard-hang':time.sleep(60)
 print('X11 Layout: us')
elif nom=='xdg-settings':
 if mode=='browser-hang':time.sleep(60)
 print('firefox.desktop')
elif nom=='systemctl':
 if mode=='polkit-hang':time.sleep(60)
 sys.exit(1)
elif nom=='sudo':sys.exit(99)
'''


@unittest.skipUnless(shutil.which('timeout') and shutil.which('jq'), 'timeout et jq requis')
class InstallChecks(unittest.TestCase):
    def executer(self, scenario='', famille='fedora', mode='nosystem', manque=False):
        with tempfile.TemporaryDirectory(prefix='nc-install-checks-') as d:
            root=Path(d); b=root/'bin'; b.mkdir(); log=root/'calls'
            for nom in ('Hyprland','noctalia','rpm','pacman','dpkg-query','dnf','hyprctl','localectl','xdg-settings','systemctl','sudo'):
                p=b/nom; p.write_text(OUTIL); p.chmod(0o755)
            # Même vraie limite et mêmes signaux que la production, avec une durée raccourcie.
            p=b/'timeout'; p.write_text('#!/bin/sh\nshift 2\nexec /usr/bin/timeout --kill-after=0.1s 0.15s "$@"\n'); p.chmod(0o755)
            if scenario=='python36':   # python3 en 3.6 (openSUSE Leap 15.6) ; les faux outils gardent le vrai
                p=b/'python3'; p.write_text('#!/bin/sh\ncase "$*" in *version_info*) exit 1 ;; -V|--version) echo "Python 3.6.15"; exit 0 ;; esac\n'
                                           f'exec {shutil.which("python3")} "$@"\n'); p.chmod(0o755)
            prelude=r'''
set -euo pipefail
say(){ printf '%s\n' "$*"; }
info(){ printf '%s\n' "$*"; }
ok(){ printf '%s\n' "$*"; }
warn(){ printf '%s\n' "$*"; }
die(){ printf '%s\n' "$*" >&2; exit 1; }
t(){ printf '%s' "$2"; }
have(){ if [ "${NC_TEST_MISSING:-}" = 1 ] && [ "$1" = jq ]; then return 1; fi; command -v "$1" >/dev/null; }
ask(){ case "${NC_TEST_CASE:-}" in dnf-*) return 0;; *) echo 'UNEXPECTED_QUESTION' >&2; return 1;; esac; }
pkg_install(){ echo 'PACKAGE_INSTALL' >&2; return 99; }
pkg_installed(){ return 1; }
FAMILY="$NC_TEST_FAMILY"; MODE="$NC_TEST_MODE"; OSID="$FAMILY"; OSNAME=Test; OSVER=44; OSCODE=other; OSLOGO=''; HYPR_MIN=0.55.0
NOCT_DOCS=https://example.invalid; APT_OPT=''; BPO=''
'''
            script=root/'test.sh'; script.write_text(prelude+SONDE+CHECKS+'\necho CHECKS_FINISHED\n')
            env=dict(os.environ, HOME=d, PATH=str(b)+':'+os.environ['PATH'], NC_TEST_CALLS=str(log),
                     NC_TEST_CASE=scenario, NC_TEST_FAMILY=famille, NC_TEST_MODE=mode, NC_TEST_MISSING='1' if manque else '')
            process=subprocess.Popen(['bash',str(script)],env=env,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=True)
            try:
                out,err=process.communicate(timeout=8)
            finally:
                try:os.killpg(process.pid,signal.SIGKILL)
                except ProcessLookupError:pass
                if process.poll() is None:process.communicate()
            appels=log.read_text() if log.exists() else ''
            return process.returncode,out+err,appels

    def test_healthy_checks_on_all_families_do_not_install_anything(self):
        for famille in ('fedora','arch','debian','suse','other'):
            with self.subTest(famille=famille):
                code,texte,appels=self.executer(famille=famille)
                self.assertEqual(code,0,texte)
                self.assertIn('CHECKS_FINISHED',texte)
                self.assertNotIn('PACKAGE_INSTALL',texte)
                self.assertNotIn('UNEXPECTED_QUESTION',texte)
                self.assertNotIn('["sudo"',appels)
                self.assertNotIn('["dnf"',appels)

    def test_hung_version_and_session_probes_finish_with_visible_stage(self):
        for scenario,libelle in (('hypr-hang','Hyprland --version'),('noctalia-version-hang','noctalia --version'),
                                 ('display-hang','hyprctl monitors'),('keyboard-hang','localectl status'),
                                 ('browser-hang','xdg-settings'),('polkit-hang','systemctl polkit')):
            with self.subTest(scenario=scenario):
                code,texte,_=self.executer(scenario)
                self.assertEqual(code,0,texte)
                self.assertIn(libelle+': timed out',texte)
                self.assertIn('CHECKS_FINISHED',texte)

    def test_unknown_lock_status_stops_before_copying(self):
        for scenario in ('noctalia-status-hang','noctalia-status-ignore-term','locked'):
            with self.subTest(scenario=scenario):
                code,texte,_=self.executer(scenario)
                self.assertEqual(code,1,texte)
                self.assertNotIn('CHECKS_FINISHED',texte)
                self.assertIn('lock',texte)

    def test_fedora_dnf_failure_or_timeout_does_not_enable_copr(self):
        for scenario in ('dnf-error','dnf-hang'):
            with self.subTest(scenario=scenario):
                code,texte,appels=self.executer(scenario)
                self.assertEqual(code,1,texte)
                self.assertIn('DNF could not query',texte)
                self.assertNotIn('copr',appels)
                self.assertNotIn('["sudo"',appels)
                self.assertNotIn('PACKAGE_INSTALL',texte)

    def test_files_only_never_installs_missing_base_tools(self):
        code,texte,appels=self.executer(mode='files',manque=True)
        self.assertEqual(code,1,texte)
        self.assertIn('missing command: jq',texte)
        self.assertNotIn('PACKAGE_INSTALL',texte)
        self.assertNotIn('["sudo"',appels)


    def test_python_trop_ancien_arrete_meme_en_files_only(self):
        # C-4 : capture_output (3.7) et := (3.8) dans les outils ; openSUSE Leap 15.6 n'a que Python 3.6
        for mode in ('files','nosystem'):
            with self.subTest(mode=mode):
                code,texte,appels=self.executer('python36',famille='suse',mode=mode)
                self.assertEqual(code,1,texte)
                self.assertIn('Python 3.8 or later is required (python3 is 3.6.15)',texte)
                self.assertNotIn('CHECKS_FINISHED',texte)
                self.assertNotIn('PACKAGE_INSTALL',texte)
                self.assertNotIn('["sudo"',appels)


class NettoyageCockpit(unittest.TestCase):
    def test_old_dashboard_is_backed_up_once_without_touching_current_cockpit(self):
        block=SOURCE[SOURCE.index('# Ancien cockpit QML orphelin'):SOURCE.index('# Ancienne version de ce dépôt')]
        with tempfile.TemporaryDirectory() as d:
            home=Path(d);folder=home/'.config/quickshell/nc-ile';folder.mkdir(parents=True)
            old=folder/'JarvisDashboard.qml';old.write_text('ancien cockpit personnalisé')
            current=folder/'Jarvis.qml';current.write_text('cockpit actif')
            script='''set -eu
backup() { mkdir -p "$HOME/backup/$(dirname "$1")"; cp -a -- "$HOME/$1" "$HOME/backup/$1"; }
'''+block
            for _ in range(2):
                r=subprocess.run(['bash','-c',script],env=dict(os.environ,HOME=d),text=True,capture_output=True,timeout=3)
                self.assertEqual(r.returncode,0,r.stderr)
                self.assertFalse(old.exists());self.assertEqual(current.read_text(),'cockpit actif')
                self.assertEqual((home/'backup/.config/quickshell/nc-ile/JarvisDashboard.qml').read_text(),'ancien cockpit personnalisé')


class EnregistreurDictee(unittest.TestCase):
    """Revue DIST-01 : rien ne garantissait un enregistreur pour la dictée (pw-record, parec ou arecord). Noms vérifiés
    dans chaque dépôt : pipewire-audio (Arch), pipewire-utils (Fedora), pipewire-bin (Debian), pipewire-tools (openSUSE)."""
    def test_paquet_par_famille_et_seulement_s_il_manque(self):
        texte = (REPO / "install.sh").read_text()
        debut = texte.index("pname() {")
        fonction = texte[debut:texte.index("\n}\n", debut) + 3]
        attendu = {"arch": "pipewire-audio", "fedora": "pipewire-utils", "debian": "pipewire-bin", "suse": "pipewire-tools", "other": ""}
        for famille, paquet in attendu.items():
            r = subprocess.run(["bash", "-c", fonction + f'FAMILY={famille}; pname enregistreur'], capture_output=True, text=True)
            self.assertEqual(r.stdout.strip(), paquet, famille)
        generic = texte[texte.index("GENERIC=("):texte.index(")", texte.index("GENERIC=("))]
        self.assertIn("enregistreur", generic)
        self.assertIn('[ "$g" = enregistreur ] && { have pw-record || have parec || have arecord; } && continue', texte)

"""Vérifications réelles de l'installateur avec de faux outils ; aucun paquet/service modifié."""
import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import warnings

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
    def executer(self, scenario='', famille='fedora', mode='nosystem', manque=False, xdg=None):
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
            # Dossiers XDG : ceux par défaut du HOME temporaire (pas ceux du garde-fou, qui pointent ailleurs), sauf
            # ceux que le test donne ; None = variable retirée, « {HOME} » = le HOME temporaire
            env.update(XDG_CONFIG_HOME=d+'/.config', XDG_STATE_HOME=d+'/.local/state')
            env.pop('NOCTALIA_CONFIG_HOME',None); env.pop('NOCTALIA_STATE_HOME',None)
            for cle,valeur in (xdg or {}).items():
                if valeur is None:env.pop(cle,None)
                else:env[cle]=valeur.replace('{HOME}',d)
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

    def test_xdg_ailleurs_averti_sans_bloquer(self):
        # Lot C-3 : l'installateur copie tout sous ~/.config et ~/.local/state ; un XDG_*_HOME ailleurs n'est pas lu
        for cle,defaut in (('XDG_CONFIG_HOME','~/.config'),('XDG_STATE_HOME','~/.local/state'),
                           ('NOCTALIA_CONFIG_HOME','~/.config'),('NOCTALIA_STATE_HOME','~/.local/state')):
            for valeur in ('{HOME}/ailleurs','/srv/ailleurs/','~/autre'):
                with self.subTest(cle=cle,valeur=valeur):
                    code,texte,_=self.executer(xdg={cle:valeur})
                    self.assertEqual(code,0,texte)
                    self.assertIn('CHECKS_FINISHED',texte)
                    self.assertEqual(texte.count('points elsewhere'),1,texte)
                    self.assertIn(f'Your {cle} points elsewhere (',texte)
                    if '{HOME}' not in valeur:self.assertIn(f'points elsewhere ({valeur}):',texte)
                    self.assertIn(f'installs into {defaut}, which Noctalia',texte)
                    self.assertIn('this setup is not supported.',texte)

    def test_xdg_absent_vide_ou_par_defaut_rien(self):
        for cas in ({'XDG_CONFIG_HOME':None,'XDG_STATE_HOME':None},{'XDG_CONFIG_HOME':'','XDG_STATE_HOME':''},
                    {'XDG_CONFIG_HOME':'{HOME}/.config/','XDG_STATE_HOME':'{HOME}/.local/state//'},
                    {'XDG_CONFIG_HOME':'~/.config','XDG_STATE_HOME':'~/.local/state/'},
                    {'XDG_CONFIG_HOME':'{HOME}/./.config','XDG_STATE_HOME':'{HOME}/.local/../.local/state'},
                    {'NOCTALIA_CONFIG_HOME':'','NOCTALIA_STATE_HOME':''},
                    {'NOCTALIA_CONFIG_HOME':'~/.config/','NOCTALIA_STATE_HOME':'{HOME}/.local/state'}):
            with self.subTest(cas=cas):
                code,texte,_=self.executer(xdg=cas)
                self.assertEqual(code,0,texte)
                self.assertIn('CHECKS_FINISHED',texte)
                self.assertNotIn('points elsewhere',texte)

    def test_xdg_message_francais(self):
        source=SOURCE[SOURCE.index('xdg_net() {'):SOURCE.index('info "$(t "Distribution')]
        self.assertIn("Ton XDG_CONFIG_HOME pointe ailleurs ($XDG_CONFIG_HOME) : noctalia-config s'installe dans ~/.config",source)
        self.assertIn("Ton XDG_STATE_HOME pointe ailleurs ($XDG_STATE_HOME) : noctalia-config s'installe dans ~/.local/state",source)
        self.assertIn('ce cas n\'est pas pris en charge.',source)


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


class ClavierVariante(unittest.TestCase):
    """Point 3 de l'audit : install.sh relevait la disposition mais perdait la variante (bépo, intl…) et les options.
    Le bloc « Clavier » d'install.sh est joué avec de faux fichiers (/etc/default/keyboard, /etc/vconsole.conf), une
    fausse liste xkb et un faux localectl ; jamais les vrais fichiers du PC."""
    LST = ('! layout\n  fr  French\n  us  English (US)\n  de  German\n\n'
           '! variant\n  bepo  fr: French (Bepo, ergonomic)\n  intl  us: English (US, intl., with dead keys)\n'
           '  nodeadkeys  de: German (no dead keys)\n\n! option\n  grp  Switching to another layout\n'
           '  ctrl:nocaps  Caps Lock as Ctrl\n  grp:win_space_toggle  Super+Space\n  compose:rctrl  Right Ctrl\n')

    def relever(self, localectl='', debian='', vconsole='', lang='C'):
        bloc = SOURCE[SOURCE.index('XKB_LST=/usr/share'):SOURCE.index('# Navigateur par défaut')]
        with tempfile.TemporaryDirectory(prefix='nc-clavier-') as d:
            r = Path(d); (r / 'bin').mkdir()
            (r / 'evdev.lst').write_text(self.LST)
            (r / 'keyboard').write_text(debian); (r / 'vconsole.conf').write_text(vconsole)
            lc = r / 'bin/localectl'; lc.write_text('#!/bin/sh\ncat <<\'FIN\'\n' + localectl + '\nFIN\n'); lc.chmod(0o755)
            bloc = bloc.replace('XKB_LST=/usr/share/X11/xkb/rules/evdev.lst', f'XKB_LST={r}/evdev.lst') \
                       .replace('/etc/default/keyboard', f'{r}/keyboard').replace('/etc/vconsole.conf', f'{r}/vconsole.conf')
            script = ('set -euo pipefail\ninfo(){ :; }\nok(){ :; }\nt(){ printf %s "$1"; }\n'
                      'sonder(){ shift 2; "$@"; }\n' + bloc + 'printf "%s|%s|%s" "$KBL" "$KBV" "$KBO"\n')
            p = subprocess.run(['bash', '-c', script], env=dict(os.environ, PATH=f'{r}/bin:' + os.environ['PATH'], LANG=lang),
                               text=True, capture_output=True, timeout=10)
            self.assertEqual(p.returncode, 0, p.stderr)
            return p.stdout.split('|')

    def test_localectl_variante_et_options(self):
        self.assertEqual(self.relever('X11 Layout: fr\nX11 Variant: bepo\nX11 Options: ctrl:nocaps'), ['fr', 'bepo', 'ctrl:nocaps'])

    def test_debian_xkbvariant_xkboptions(self):
        d = 'XKBMODEL="pc105"\nXKBLAYOUT="us"\nXKBVARIANT="intl"\nXKBOPTIONS="compose:rctrl"\n'
        self.assertEqual(self.relever('X11 Layout: n/a', debian=d), ['us', 'intl', 'compose:rctrl'])
        self.assertEqual(self.relever('', debian='XKBLAYOUT=de\nXKBVARIANT=nodeadkeys\n'), ['de', 'nodeadkeys', ''])

    def test_vconsole_conf(self):
        self.assertEqual(self.relever('', vconsole='KEYMAP=fr\nXKBLAYOUT=fr\nXKBVARIANT=bepo\nXKBOPTIONS=ctrl:nocaps\n'),
                         ['fr', 'bepo', 'ctrl:nocaps'])

    def test_rien_trouve_est_vide(self):
        self.assertEqual(self.relever('X11 Layout: us\nX11 Variant: n/a\nX11 Options: n/a'), ['us', '', ''])
        self.assertEqual(self.relever('', lang='fr_FR.UTF-8'), ['fr', '', ''])

    def test_variante_ou_option_inconnue_laissee_de_cote(self):
        # Une variante d'une autre disposition, ou une option qui n'existe pas, ferait une erreur dans Hyprland
        self.assertEqual(self.relever('X11 Layout: fr\nX11 Variant: intl\nX11 Options: truc:machin'), ['fr', '', ''])
        self.assertEqual(self.relever('X11 Layout: fr\nX11 Variant: bepo;rm\nX11 Options: ctrl:nocaps'), ['fr', '', 'ctrl:nocaps'])

    def test_plusieurs_dispositions(self):
        self.assertEqual(self.relever('X11 Layout: us,fr\nX11 Variant: ,bepo\nX11 Options: ctrl:nocaps'),
                         ['us,fr', ',bepo', 'ctrl:nocaps,grp:win_space_toggle'])
        self.assertEqual(self.relever('X11 Layout: us,fr\nX11 Variant: bepo,\nX11 Options: n/a'), ['us,fr', '', 'grp:win_space_toggle'])

    def test_marqueur_rempli_dans_le_sed_de_copie(self):
        self.assertIn('-e "s|@KB_VARIANT@|$KBV|g"', SOURCE)


@unittest.skipUnless(shutil.which('lua'), 'lua requis')
class ClavierLuaVariante(unittest.TestCase):
    """clavier.lua : CLAVIER_VARIANTE gagne sur la variante relevée par install.sh, est validée, et ne s'applique
    pas à une autre disposition que celle du système. Faux hl et faux nc.reglage ; marqueurs remplis comme install.sh."""
    LUA = REPO / 'home/.config/hypr/nc/clavier.lua'

    def lancer(self, reglages, layout='fr', variante='bepo', options=''):
        texte = self.LUA.read_text().replace('@KB_LAYOUT@', layout).replace('@KB_VARIANT@', variante).replace('@KB_OPTIONS@', options)
        self.assertNotIn('@KB_', texte)
        harnais = '''
local R = {%s}
nc = { reglage = function(c, d) if R[c] ~= nil and R[c] ~= "" then if type(d) == "number" then return tonumber(R[c]) or d end return R[c] end return d end }
local cfg
hl = { config = function(t) cfg = t end, gesture = function() end, device = function() end, exec_cmd = function() end }
local src = io.open(arg[1]):read("a")
assert(load(src))()
print(cfg.input.kb_layout .. "|" .. cfg.input.kb_variant .. "|" .. cfg.input.kb_options)
''' % ', '.join('%s = %s' % (k, json.dumps(v, ensure_ascii=False)) for k, v in reglages.items())
        with tempfile.TemporaryDirectory(prefix='nc-clavier-lua-') as d:
            f = Path(d) / 'clavier.lua'; f.write_text(texte)
            p = subprocess.run(['lua', '-', str(f)], input=harnais, text=True, capture_output=True, timeout=10)
        self.assertEqual(p.returncode, 0, p.stderr)
        return p.stdout.strip()

    def test_variante_du_systeme_par_defaut(self):
        self.assertEqual(self.lancer({}), 'fr|bepo|')

    def test_reglage_gagne(self):
        self.assertEqual(self.lancer({'CLAVIER_VARIANTE': 'oss'}), 'fr|oss|')
        self.assertEqual(self.lancer({'CLAVIER_VARIANTE': 'aucune'}), 'fr||')
        self.assertEqual(self.lancer({'CLAVIER_VARIANTE': 'systeme'}, variante='intl', layout='us'), 'us|intl|')

    def test_valeur_invalide_refusee(self):
        for mauvaise in ('bepo;rm -rf', 'a b', 'x"y', 'é'):
            self.assertEqual(self.lancer({'CLAVIER_VARIANTE': mauvaise}), 'fr||', mauvaise)

    def test_autre_disposition_pas_de_variante_du_systeme(self):
        self.assertEqual(self.lancer({'CLAVIER_DISPOSITION': 'us'}), 'us||')
        self.assertEqual(self.lancer({'CLAVIER_DISPOSITION': 'us', 'CLAVIER_VARIANTE': 'intl'}), 'us|intl|')
        self.assertEqual(self.lancer({'CLAVIER_DISPOSITION': 'fr'}), 'fr|bepo|')

    def test_plusieurs_dispositions_variante_alignee(self):
        self.assertEqual(self.lancer({}, layout='us,fr', variante=',bepo', options='ctrl:nocaps'),
                         'us,fr|,bepo|ctrl:nocaps,grp:win_space_toggle')


class ReglageClavierVariante(unittest.TestCase):
    """nc-reglages : CLAVIER_VARIANTE, à côté de CLAVIER_DISPOSITION."""
    def test_validation(self):
        with tempfile.TemporaryDirectory(prefix='nc-reglage-variante-') as d:
            with patch.dict(os.environ, HOME=d, NC_LANGUE='fr'), warnings.catch_warnings():
                warnings.simplefilter('ignore', ResourceWarning)
                ch = importlib.machinery.SourceFileLoader('nc_reglages_variante', str(REPO / 'home/.local/bin/nc-reglages'))
                m = importlib.util.module_from_spec(importlib.util.spec_from_loader(ch.name, ch)); ch.exec_module(m)
            r = next(x for x in m.REGLAGES if x.cle == 'CLAVIER_VARIANTE')
            self.assertEqual(r.defaut, 'systeme'); self.assertEqual(r.genre, 'texte')
            self.assertEqual(r.valider('System'), 'systeme'); self.assertEqual(r.valider('none'), 'aucune')
            self.assertEqual(r.valider('aucune'), 'aucune')
            # Sans la liste xkb (conteneur minimal, CI), seul le format est vérifié : une variante inconnue mais bien
            # écrite passe alors
            mauvaises = ['bepo;rm', 'a b']
            if Path('/usr/share/X11/xkb/rules/evdev.lst').exists():
                self.assertEqual(r.valider('bepo'), 'bepo'); self.assertEqual(r.valider(',bepo'), ',bepo')
                mauvaises.append('pas-une-variante-xkb')
            for mauvaise in mauvaises:
                with self.assertRaises(ValueError):
                    r.valider(mauvaise)
            self.assertIn('CLAVIER_VARIANTE', (REPO / 'home/.local/bin/nc-sauvegarde').read_text())

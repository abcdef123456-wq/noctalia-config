"""nc-jarvis verifier : la liste de contrôle avant déploiement. Faux os-release, faux programmes devant le PATH,
vrais sockets pour les ports ; HOME est un dossier temporaire (jamais le vrai)."""
import io
import os
from pathlib import Path
import socket
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

REPO=Path(__file__).resolve().parents[1]
SHARE=REPO/'home/.local/share/nc-jarvis'
BIN=REPO/'home/.local/bin/nc-jarvis'
sys.path.insert(0,str(SHARE))
import verifier  # noqa: E402

OS_RELEASE={
    'debian':'PRETTY_NAME="Debian GNU/Linux 13"\nID=debian\nVERSION_ID="13"\n',
    'ubuntu':'NAME="Ubuntu"\nID=ubuntu\nID_LIKE=debian\n',
    'mint':'ID=linuxmint\nID_LIKE="ubuntu debian"\n',
    'fedora':'NAME="Fedora Linux"\nID=fedora\n',
    'arch':'NAME="Arch Linux"\nID=arch\n',
    'cachyos':'ID=cachyos\nID_LIKE=arch\n',
    'opensuse':'NAME="openSUSE Tumbleweed"\nID="opensuse-tumbleweed"\nID_LIKE="opensuse suse"\n',
    'inconnue':'ID=nixos\n',
}


def script(dossier,nom,corps):
    p=Path(dossier)/nom;p.write_text('#!/bin/sh\n'+corps+'\n');p.chmod(p.stat().st_mode|stat.S_IXUSR);return p


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.home=self.root/'home';self.home.mkdir();self.bin=self.root/'bin';self.bin.mkdir()
        (self.bin/'python3').symlink_to(sys.executable)
        script(self.bin,'git','exit 0')
        script(self.bin,'systemctl','echo running')
        script(self.bin,'loginctl','echo Linger=yes')
        self.osr=self.root/'os-release';self.distro('debian')
        env=patch.dict(os.environ,HOME=str(self.home),PATH=str(self.bin),USER='testeur',NC_JARVIS_OS_RELEASE=str(self.osr))
        env.start();self.addCleanup(env.stop)
        # des ports de test libres, pour ne dépendre ni du 8000 ni du 8080 de la machine
        ports=[]
        for _ in range(2):
            s=socket.socket();s.bind(('127.0.0.1',0));ports.append(s.getsockname()[1]);s.close()
        p=patch.object(verifier,'PORTS',((ports[0],'le gateway'),(ports[1],'le runner')));p.start();self.addCleanup(p.stop)
        self.ports=ports
        libre=patch.object(verifier.shutil,'disk_usage',lambda d:type('U',(),{'free':50*2**30})());libre.start();self.addCleanup(libre.stop)

    def distro(self,nom):self.osr.write_text(OS_RELEASE[nom])

    def lancer(self,moteur=None):
        sortie=[];ok=verifier.verifier(moteur,sortie.append);return ok,'\n'.join(sortie)

    def moteur_connecte(self,nom='claude'):
        script(self.bin,nom,'case "$*" in "auth status") echo \'{"loggedIn": true}\';; "login status") echo ok;; esac')


class Distributions(Base):
    def test_gestionnaire(self):
        attendu=dict(debian='apt',ubuntu='apt',mint='apt',fedora='dnf',arch='pacman',cachyos='pacman',opensuse='zypper',inconnue=None)
        for nom,gest in attendu.items():
            self.distro(nom);self.assertEqual(verifier.gestionnaire(),gest,nom)

    def test_os_release_absent(self):
        self.osr.unlink();self.assertIsNone(verifier.gestionnaire())

    def test_git_absent_la_commande_de_chaque_distribution(self):
        (self.bin/'git').unlink()
        attendu=dict(debian='apt install git',ubuntu='apt install git',fedora='dnf install git',arch='pacman -S git',opensuse='zypper install git')
        with patch.object(verifier.os,'geteuid',lambda:1000):
            for nom,cmd in attendu.items():
                self.distro(nom);ok,t=self.lancer('claude')
                self.assertFalse(ok);self.assertIn('✗ git manque.',t);self.assertIn('Tape : sudo '+cmd,t,nom)

    def test_root_sans_sudo(self):
        (self.bin/'git').unlink()
        with patch.object(verifier.os,'geteuid',lambda:0):
            self.assertIn('Tape : apt install git',self.lancer('claude')[1])

    def test_distribution_inconnue_ne_devine_pas(self):
        (self.bin/'git').unlink();self.distro('inconnue')
        ok,t=self.lancer('claude');self.assertIn('Distribution non reconnue',t);self.assertIn('avec le gestionnaire de ta distribution',t)
        self.assertNotIn('sudo apt',t)


class Controles(Base):
    def test_tout_vert(self):
        self.moteur_connecte();ok,t=self.lancer('claude')
        self.assertTrue(ok,t);self.assertNotIn('✗',t)
        for mot in ('git est installé','python3 ','venv','pip marche','Claude Code est installé et connecté','systemd --user répond','Le port','Espace disque'):
            self.assertIn(mot,t)

    def test_python_absent(self):
        (self.bin/'python3').unlink();ok,t=self.lancer('claude')
        self.assertFalse(ok);self.assertIn('✗ python3 manque.',t);self.assertIn('sudo apt install python3',t);self.assertIn('venv et pip non testés',t)

    def test_python_trop_ancien(self):
        (self.bin/'python3').unlink()
        script(self.bin,'python3','echo 3.10.12')
        ok,t=self.lancer('claude');self.assertFalse(ok);self.assertIn('3.10.12',t);self.assertIn('trop ancien',t)

    def test_venv_casse_debian_puis_autres(self):
        (self.bin/'python3').unlink()
        script(self.bin,'python3','case "$*" in *"-m venv"*) echo "ensurepip is not available" >&2; exit 1;; esac\nexec '+sys.executable+' "$@"')
        attendu=dict(debian='sudo apt install python3-venv',fedora='sudo dnf install python3',arch='sudo pacman -S python',opensuse='sudo zypper install python3-pip')
        with patch.object(verifier.os,'geteuid',lambda:1000):
            for nom,cmd in attendu.items():
                self.distro(nom);ok,t=self.lancer('claude')
                self.assertFalse(ok);self.assertIn('✗ Python ne sait pas créer',t);self.assertIn('Tape : '+cmd,t,nom)
        self.assertNotIn('pip manque',t)

    def test_pip_absent_du_venv(self):
        (self.bin/'python3').unlink()
        # un faux python3 qui crée un « venv » dont le python n'a pas pip
        script(self.bin,'python3','case "$*" in *"-m venv"*) d=$3; mkdir -p "$d/bin"; printf \'#!/bin/sh\\nexit 1\\n\' > "$d/bin/python"; chmod +x "$d/bin/python"; exit 0;; esac\nexec '+sys.executable+' "$@"')
        ok,t=self.lancer('claude');self.assertFalse(ok);self.assertIn('✓ Les environnements virtuels',t);self.assertIn('✗ pip manque',t)
        self.assertIn('sudo apt install python3-venv python3-pip',t)

    def test_le_venv_temporaire_est_supprime(self):
        avant=set(Path(tempfile.gettempdir()).glob('nc-verifier-*'));self.moteur_connecte();self.lancer('claude')
        self.assertEqual(set(Path(tempfile.gettempdir()).glob('nc-verifier-*')),avant)

    def test_port_occupe(self):
        s=socket.socket();self.addCleanup(s.close);s.bind(('127.0.0.1',self.ports[0]));s.listen()
        self.moteur_connecte();ok,t=self.lancer('claude')
        self.assertFalse(ok);self.assertIn('✗ Le port '+str(self.ports[0])+' est occupé',t);self.assertIn('ss -ltnp',t)
        self.assertIn('✓ Le port '+str(self.ports[1])+' est libre',t)

    def test_port_libre_et_rien_laisse_ouvert(self):
        self.assertTrue(verifier.port_libre(self.ports[0]));self.assertTrue(verifier.port_libre(self.ports[0]))

    def test_disque_insuffisant(self):
        with patch.object(verifier.shutil,'disk_usage',lambda d:type('U',(),{'free':2**29})()):
            self.moteur_connecte();ok,t=self.lancer('claude')
        self.assertFalse(ok);self.assertIn('✗ Espace disque : 0.5 Go',t)

    def test_systemd_user_absent(self):
        script(self.bin,'systemctl','echo "Failed to connect to bus" >&2; exit 1')
        self.moteur_connecte();ok,t=self.lancer('claude');self.assertFalse(ok);self.assertIn('✗ systemd --user ne répond pas',t)

    def test_linger_est_un_avertissement(self):
        script(self.bin,'loginctl','echo Linger=no');self.moteur_connecte();ok,t=self.lancer('claude')
        self.assertTrue(ok);self.assertIn('! Le maintien de session',t);self.assertIn('loginctl enable-linger $USER',t)

    def test_linger_actif(self):
        self.moteur_connecte();self.assertIn('✓ Le maintien de session',self.lancer('claude')[1])

    def test_jarvis_deja_present_avertit_et_ne_bloque_pas(self):
        unites=self.home/'.config/systemd/user';unites.mkdir(parents=True);(unites/'assistant-gateway.service').write_text('[Service]\n')
        self.moteur_connecte();ok,t=self.lancer('claude')
        self.assertTrue(ok);self.assertIn('! Tu as déjà un JARVIS ici',t);self.assertIn('nc-jarvis deployer',t);self.assertNotIn(str(self.home),t)

    def test_jarvis_present_ports_occupes_normal(self):
        (self.home/'.local/share/jarvis-bis').mkdir(parents=True)
        s=socket.socket();self.addCleanup(s.close);s.bind(('127.0.0.1',self.ports[0]));s.listen()
        self.moteur_connecte();ok,t=self.lancer('claude')
        self.assertTrue(ok);self.assertIn('! Le port',t)


class Moteurs(Base):
    def test_moteur_absent_donne_installation_et_connexion(self):
        for m,ins,con in (('claude','claude.ai/install.sh','claude auth login'),('codex','@openai/codex','codex login'),
                          ('opencode','opencode-ai','opencode auth login')):
            ok,t=self.lancer(m);self.assertFalse(ok);self.assertIn('✗',t);self.assertIn(ins,t);self.assertIn(con,t)

    def test_moteur_installe_pas_connecte(self):
        script(self.bin,'claude','echo \'{"loggedIn": false}\'')
        ok,t=self.lancer('claude');self.assertFalse(ok);self.assertIn('✗ Claude Code est installé mais pas connecté',t);self.assertIn('claude auth login',t)

    def test_claude_ancien_repli_sur_le_fichier(self):
        script(self.bin,'claude','exit 2');(self.home/'.claude').mkdir();(self.home/'.claude/.credentials.json').write_text('{"x":1}')
        self.assertTrue(self.lancer('claude')[0])

    def test_codex_connecte_par_login_status(self):
        script(self.bin,'codex','[ "$1 $2" = "login status" ] && exit 0; exit 1')
        ok,t=self.lancer('codex');self.assertTrue(ok);self.assertIn('✓ Codex est installé et connecté',t)

    def test_opencode_par_fichier(self):
        script(self.bin,'opencode','exit 0')
        self.assertFalse(self.lancer('opencode')[0])
        d=self.home/'.local/share/opencode';d.mkdir(parents=True);(d/'auth.json').write_text('{"a":{"type":"api"}}')
        self.assertTrue(self.lancer('opencode')[0])

    def test_agy_connexion_inverifiable_n_est_qu_un_avertissement(self):
        script(self.bin,'agy','exit 0');ok,t=self.lancer('agy');self.assertTrue(ok);self.assertIn('! Antigravity est installé',t)

    def test_cherche_aussi_dans_local_bin(self):
        d=self.home/'.local/bin';d.mkdir(parents=True);script(d,'claude','echo \'{"loggedIn": true}\'')
        self.assertTrue(self.lancer('claude')[0])

    def test_sans_moteur_choisi_un_seul_pret_suffit(self):
        script(self.bin,'claude','echo \'{"loggedIn": false}\'');self.moteur_connecte('codex')
        ok,t=self.lancer();self.assertTrue(ok);self.assertIn('! Claude Code est installé mais pas connecté',t);self.assertIn('✓ Codex',t)

    def test_sans_moteur_choisi_aucun_pret(self):
        ok,t=self.lancer();self.assertFalse(ok);self.assertIn("✗ Aucun moteur d'IA n'est prêt",t)

    def test_moteur_inconnu(self):
        with self.assertRaises(ValueError):self.lancer('gpt')

    def test_aucune_requete_n_est_envoyee(self):
        journal=self.root/'j';script(self.bin,'claude','echo "$*" >> '+str(journal)+'\necho \'{"loggedIn": true}\'')
        self.lancer('claude');self.assertEqual(journal.read_text().split('\n')[:-1],['auth status'])


class Commande(Base):
    def run_cmd(self,*args):
        return subprocess.run([sys.executable,str(BIN),'verifier',*args],capture_output=True,text=True,env=dict(os.environ),timeout=120)

    def test_code_de_sortie_et_aiguillage(self):
        r=self.run_cmd('--moteur','claude');self.assertEqual(r.returncode,1,r.stdout+r.stderr);self.assertIn('✗ Claude Code',r.stdout)
        self.moteur_connecte();r=self.run_cmd('--moteur','claude')
        if all(verifier.port_libre(p) for p in (8000,8080)):   # le sous-processus teste les vrais ports
            self.assertEqual(r.returncode,0,r.stdout+r.stderr);self.assertIn('Rien ne bloque',r.stdout)

    def test_main_moteur_refuse(self):
        with self.assertRaises(SystemExit),patch('sys.stderr',io.StringIO()):verifier.main(['--moteur','gpt'])

    def test_rien_n_est_ecrit_dans_home(self):
        self.moteur_connecte();self.lancer('claude');self.assertEqual(list(self.home.iterdir()),[])


if __name__=='__main__':unittest.main()

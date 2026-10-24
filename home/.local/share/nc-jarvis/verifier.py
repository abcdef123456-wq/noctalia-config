"""nc-jarvis verifier : la liste de contrôle AVANT de déployer JARVIS. Ne modifie rien, n'installe rien :
pour chaque problème, elle affiche la commande exacte à taper pour ta distribution."""
import argparse
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile

PORTS=((8000,'le gateway'),(8080,'le runner'))
DISQUE_MIN_GIO=2     # dépôt + deux venv Python + leurs paquets + sauvegardes des unités : compte large
MOTEURS={'agy':'Antigravity','codex':'Codex','claude':'Claude Code','opencode':'OpenCode'}
DOSSIER_PAR_DEFAUT='~/.local/share/jarvis-bis'     # le même que le déployeur
FAMILLES={'debian':'apt','ubuntu':'apt','linuxmint':'apt','raspbian':'apt','pop':'apt',
          'fedora':'dnf','rhel':'dnf','centos':'dnf','rocky':'dnf','almalinux':'dnf',
          'arch':'pacman','manjaro':'pacman','endeavouros':'pacman','cachyos':'pacman',
          'opensuse':'zypper','opensuse-tumbleweed':'zypper','opensuse-leap':'zypper','sles':'zypper','suse':'zypper'}
PAQUETS={
    'git':dict(apt='git',dnf='git',pacman='git',zypper='git'),
    'python':dict(apt='python3',dnf='python3',pacman='python',zypper='python3'),
    'venv':dict(apt='python3-venv',dnf='python3',pacman='python',zypper='python3-pip'),
    'pip':dict(apt='python3-venv python3-pip',dnf='python3-pip',pacman='python-pip',zypper='python3-pip'),
}
NOM_PAQUET={'git':'git','python':'python 3.11 ou plus récent','venv':'« venv » de Python','pip':'pip de Python'}
INSTALLER={
    'claude':'curl -fsSL https://claude.ai/install.sh | bash',
    'codex':'npm install -g --prefix ~/.local @openai/codex',
    'opencode':'npm install -g --prefix ~/.local opencode-ai',
    'agy':"installe Antigravity depuis son site officiel (le programme s'appelle agy)",
}
CONNECTER={'claude':'claude auth login','codex':'codex login','opencode':'opencode auth login','agy':'agy'}


def gestionnaire(chemin=None):
    """apt, dnf, pacman ou zypper selon l'ID puis l'ID_LIKE de os-release ; None si inconnu."""
    chemin=chemin or os.environ.get('NC_JARVIS_OS_RELEASE') or '/etc/os-release'
    try:lignes=Path(chemin).read_text(encoding='utf-8').splitlines()
    except OSError:return None
    valeurs={}
    for ligne in lignes:
        if '=' in ligne and not ligne.lstrip().startswith('#'):
            cle,_,valeur=ligne.partition('=');valeurs[cle.strip()]=valeur.strip().strip('"\'')
    for mot in [valeurs.get('ID','')]+valeurs.get('ID_LIKE','').split():
        if mot.lower() in FAMILLES:return FAMILLES[mot.lower()]
    return None


def commande_paquet(gest,nom):
    """La commande d'installation pour cette distribution (sudo sauf si tu es déjà root)."""
    sudo='' if hasattr(os,'geteuid') and os.geteuid()==0 else 'sudo '
    paquets=PAQUETS[nom].get(gest) if gest else None
    if not paquets:return 'installe le paquet '+NOM_PAQUET[nom]+' avec le gestionnaire de ta distribution'
    verbe={'apt':'apt install','dnf':'dnf install','pacman':'pacman -S','zypper':'zypper install'}[gest]
    return sudo+verbe+' '+paquets


def executable(nom):
    """Comme le runner (nc_engines.executable) : le PATH, puis ~/.local/bin et ~/.cargo/bin."""
    trouve=shutil.which(nom)
    if trouve:return trouve
    candidats=[Path.home()/'.local/bin'/nom,Path.home()/'.cargo/bin'/nom]
    if nom=='agy':candidats.append(Path.home()/'.gemini/antigravity-cli/agy')
    return next((str(p) for p in candidats if p.is_file() and os.access(p,os.X_OK)),None)


def lancer(cmd,delai=15):
    try:return subprocess.run(cmd,capture_output=True,text=True,timeout=delai,stdin=subprocess.DEVNULL)
    except (OSError,subprocess.SubprocessError):return None


def fichier_non_vide(chemin):
    try:return chemin.is_file() and chemin.stat().st_size>2
    except OSError:return False


def connecte(moteur,chemin):
    """True / False ; None si on ne peut pas le savoir sans lancer une vraie requête. Aucune requête n'est envoyée."""
    home=Path.home()
    if moteur=='claude':
        r=lancer([chemin,'auth','status'])
        if r is not None and r.returncode==0:
            try:return bool(json.loads(r.stdout).get('loggedIn'))
            except (ValueError,AttributeError):pass
        return fichier_non_vide(home/'.claude/.credentials.json')
    if moteur=='codex':
        r=lancer([chemin,'login','status'])
        if r is not None and r.returncode==0:return True
        return fichier_non_vide(home/'.codex/auth.json')
    if moteur=='opencode':return fichier_non_vide(home/'.local/share/opencode/auth.json')
    return None


def python_ok():
    """(chemin, version texte, assez récent) pour le python3 du PATH."""
    chemin=shutil.which('python3')
    if not chemin:return None,'',False
    r=lancer([chemin,'-c','import sys;print("%d.%d.%d"%sys.version_info[:3])'])
    if r is None or r.returncode!=0:return chemin,'',False
    version=r.stdout.strip()
    try:return chemin,version,tuple(int(x) for x in version.split('.')[:2])>=(3,11)
    except ValueError:return chemin,version,False


def venv_utilisable(python):
    """(venv créé, pip présent) en essayant pour de vrai dans un dossier temporaire, supprimé ensuite."""
    tmp=tempfile.mkdtemp(prefix='nc-verifier-')
    try:
        r=lancer([python,'-m','venv',tmp+'/v'],delai=90)
        if r is None or r.returncode!=0:return False,False
        p=lancer([tmp+'/v/bin/python','-m','pip','--version'],delai=30)
        return True,bool(p is not None and p.returncode==0)
    finally:shutil.rmtree(tmp,ignore_errors=True)


def port_libre(port):
    s=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
    try:
        s.bind(('127.0.0.1',port));return True
    except OSError:return False
    finally:s.close()


def jarvis_present():
    home=Path.home()
    unites=[home/'.config/systemd/user'/('assistant-'+n+'.service') for n in ('gateway','runner')]
    return [str(p).replace(str(home),'~',1) for p in unites+[Path(DOSSIER_PAR_DEFAUT).expanduser()] if p.exists()]


def verifier(moteur=None,ecrire=print):
    """Affiche la liste de contrôle. True si rien ne bloque (les « ! » ne bloquent pas)."""
    if moteur is not None and moteur not in MOTEURS:
        raise ValueError('Moteur inconnu : '+str(moteur)+' (choix : '+', '.join(MOTEURS)+').')
    gest=gestionnaire()
    bloquant=[]
    def ok(texte):ecrire('✓ '+texte)
    def avert(texte,aide=None):
        ecrire('! '+texte)
        if aide:ecrire('    '+aide)
    def ko(texte,aide=None):
        bloquant.append(texte);ecrire('✗ '+texte)
        if aide:ecrire('    '+aide)
    ecrire("Vérification avant de déployer JARVIS (rien n'est installé ni modifié) :")
    if gest is None:avert('Distribution non reconnue : je ne peux pas te donner la commande exacte, seulement le nom des paquets.')

    present=jarvis_present()
    if present:avert('Tu as déjà un JARVIS ici ('+', '.join(present)+').','Utilise « nc-jarvis deployer » pour le mettre à jour : il garde ta configuration.')

    if shutil.which('git'):ok('git est installé.')
    else:ko('git manque.','Tape : '+commande_paquet(gest,'git'))

    python,version,assez=python_ok()
    if python is None:ko('python3 manque.','Tape : '+commande_paquet(gest,'python'))
    elif assez:ok('python3 '+version+' (il faut la 3.11 ou plus).')
    else:ko('python3 '+(version or '?')+' est trop ancien : il faut la 3.11 ou plus.','Tape : '+commande_paquet(gest,'python')+'  (sur une distribution ancienne, cherche un paquet python3.11 ou plus récent)')

    if python:
        venv,pip=venv_utilisable(python)
        if venv:ok('Les environnements virtuels (venv) marchent.')
        else:ko("Python ne sait pas créer d'environnement virtuel (venv).",'Tape : '+commande_paquet(gest,'venv'))
        if venv:
            if pip:ok('pip marche dans le venv.')
            else:ko('pip manque dans le venv.','Tape : '+commande_paquet(gest,'pip'))
    else:avert("venv et pip non testés : il faut d'abord python3.")

    # CLI d'IA : installé ET connecté, sans envoyer aucune requête
    choix=[moteur] if moteur else list(MOTEURS)
    prets=[];ecrire('IA (le moteur doit être installé et connecté sur cette machine) :')
    for m in choix:
        nom=MOTEURS[m];chemin=executable(m)
        if not chemin:
            if moteur:ko(nom+' ('+m+") n'est pas installé.",'Installe-le : '+INSTALLER[m]+'\n    puis connecte-toi : '+CONNECTER[m])
            else:ecrire('  - '+nom+' ('+m+") n'est pas installé ; pour l'installer : "+INSTALLER[m])
            continue
        etat=connecte(m,chemin)
        if etat:ok(nom+' est installé et connecté.');prets.append(m)
        elif etat is None:avert(nom+" est installé ; je ne peux pas savoir s'il est connecté sans envoyer une vraie requête.",'Si besoin, connecte-toi : '+CONNECTER[m]);prets.append(m)
        elif moteur:ko(nom+' est installé mais pas connecté.','Connecte-toi : '+CONNECTER[m])
        else:avert(nom+' est installé mais pas connecté.','Connecte-toi : '+CONNECTER[m])
    if not moteur and not prets:
        ko("Aucun moteur d'IA n'est prêt (installé et connecté).",'Le plus simple : '+INSTALLER['claude']+'\n    puis : '+CONNECTER['claude'])

    ecrire('Services :')
    sysd=lancer(['systemctl','--user','is-system-running'],delai=10)
    etat=(sysd.stdout.strip() if sysd else '')
    if sysd is not None and etat in ('running','degraded'):ok('systemd --user répond ('+etat+').')
    else:ko('systemd --user ne répond pas'+(' ('+etat+')' if etat else '')+' : JARVIS ne pourrait pas démarrer ses services.',
            'Ouvre une vraie session (pas un « su » ni un conteneur). Par SSH : « export XDG_RUNTIME_DIR=/run/user/$(id -u) » puis réessaie.')
    user=os.environ.get('USER') or os.environ.get('LOGNAME') or ''
    ling=lancer(['loginctl','show-user',user,'-p','Linger'],delai=10) if user else None
    if ling is not None and ling.returncode==0 and 'Linger=yes' in ling.stdout:
        ok('Le maintien de session (linger) est activé : JARVIS reste allumé quand tu fermes ta session.')
    else:avert("Le maintien de session (linger) n'est pas activé : JARVIS s'arrêterait quand tu fermes ta session (utile surtout sur un serveur).",
               'Tape : loginctl enable-linger $USER   (si on te le refuse, ajoute « sudo » devant)')

    ecrire('Réseau et place :')
    for port,role in PORTS:
        if port_libre(port):ok('Le port '+str(port)+' est libre ('+role+').')
        elif present:avert('Le port '+str(port)+' est occupé ('+role+') : normal si ton JARVIS tourne déjà.')
        else:ko('Le port '+str(port)+' est occupé ('+role+") : JARVIS en a besoin sur 127.0.0.1.","Cherche qui l'utilise : ss -ltnp 'sport = :"+str(port)+"'   puis arrête ce programme.")
    dossier=Path.home()
    while not dossier.exists() and dossier!=dossier.parent:dossier=dossier.parent
    try:libre=shutil.disk_usage(dossier).free/2**30
    except OSError:libre=None
    if libre is None:avert("Je n'ai pas pu lire l'espace disque.")
    elif libre>=DISQUE_MIN_GIO:ok('Espace disque : %.1f Go libres (il en faut %d : dépôt, deux venv Python et leurs paquets).'%(libre,DISQUE_MIN_GIO))
    else:ko('Espace disque : %.1f Go libres, il en faut au moins %d (dépôt, deux venv Python et leurs paquets).'%(libre,DISQUE_MIN_GIO),'Fais de la place dans ton dossier personnel.')

    if bloquant:ecrire('\nIl reste '+str(len(bloquant))+' point'+('s' if len(bloquant)>1 else '')+' à régler (✗) avant de déployer. Relance « nc-jarvis verifier » ensuite.')
    else:ecrire('\nRien ne bloque : tu peux lancer « nc-jarvis deployer ».')
    return not bloquant


def main(argv=None):
    p=argparse.ArgumentParser(prog='nc-jarvis verifier',description=__doc__)
    p.add_argument('--moteur',choices=list(MOTEURS),help="ne contrôler que ce moteur d'IA (par défaut : tous)")
    a=p.parse_args(argv)
    return 0 if verifier(a.moteur) else 1


if __name__=='__main__':sys.exit(main(sys.argv[1:]))

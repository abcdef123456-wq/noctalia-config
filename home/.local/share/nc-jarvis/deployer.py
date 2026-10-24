"""Déploiement utilisateur JARVIS-BIS, local ou serveur Linux (jamais exécuté par nc-maj)."""
import argparse
import getpass
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import sys
import tempfile
import zipfile
from datetime import datetime

REPO='https://github.com/RaphaelBlanc/JARVIS-BIS.git'
# 9cd91bbb : dictée côté serveur (POST /api/transcribe), accès par Tailscale ; ses propres copies de nos nc_* restent
# derrière l'overlay (--app-dir, revue DEP-01). Ne jamais lancer ses scripts/switch-to-unified.sh ni « deploy.sh setup »
# chez nous : ports sur 0.0.0.0, sans overlay, et son .env par-dessus les nôtres.
# 3d1c6b6 (issue #10) : choix interactifs extraits par le serveur ([CHOIX: A | B], gardés par notre nc_gateway s'ils
# respectent nos limites), import re manquant (HTTP 500), délais par défaut à 600 s
# 64523e5 : une session AGY par PC (session_key tiré du client_id, accepté par notre nc_engines), dictée en français
# par défaut (WHISPER_LANGUAGE ; nc-dictee envoie la langue de l'utilisateur), nœuds durcis (secret dans l'en-tête
# seulement, ws:// refusé sur un hôte public, exec coupé par défaut). 1ae55f3, 8ff25c3 et 4d279b6 restent exclues :
# elles passent session_key à des fonctions que notre overlay remplaçait sans ce paramètre (HTTP 500 à chaque /run).
# aae5b9b (issue #17) : timeout en tête de chaque trame action (nc-noeud en tire son délai de confirmation) ;
# ENABLE_NODE_EXEC dans exec_cmd et pour run_shell relayé ; MCP jarvis-nodes (stdio, pour agy, non installé ici)
# f522291 (issue #20) : relais Telegram de la confirmation à distance de nc-noeud (confirm_request, code en réponse au
# message même, un chat occupé ne reçoit pas la nouvelle demande), délais des nœuds à 80 s, session_key aussi pour sa
# route de gestion (remplacée par celle de notre nc_gateway), client HTTP partagé gardé en direct dans gateway.py
# (notre RunnerLease le fait passer par le pool). Relais : un deny automatique quand il ne peut pas relayer
# (docs/jarvis.md : « ecran » ou « distance », pas « les-deux »), ENABLE_NODE_EXEC ne couvre pas run_shell par
# /api/node/{id}/action (nc-noeud confirme toujours)
# 4ecc57a : confirm_unavailable à la place du refus automatique (« les-deux » redevient sûr), run_shell et nom exact du
# nœud contrôlés pour exec/write_file, desktop:* imposé et listes blanches sur /api/nc/manage (repris dans notre
# nc_management, qui remplace cette route), fin de session des nœuds au reset, sessions AGY bornées à 64, un client HTTP
# par boucle (4 au plus : des emprunts de notre pool). L'origine reste prise dans le corps des requêtes (session de confiance).
# 94a3a93 : /api/ask limité à desktop:<pc> ou default, jeton d'origine par session (neutralisé chez nous par nc_runner :
# aucun jeton gardé ni écrit, nodes_mcp n'est pas installé), modes de permission resserrés (nc_engines ignore un ancien
# always-proceed enregistré), fin de session ciblée sur l'origine, GATEWAY_ORIGIN_KEY facultative (non générée)
# ffb19b9 : plus aucun jeton d'origine gardé par le runner (en-tête de la requête en cours seulement), permission_mode validé
# dans run_agy (repli default), un ancien always-proceed ne bloque plus le démarrage, clé HMAC sans SECRET_KEY, /api/stream
# sans clé en query. Chez nous : nc_runner et nc_engines restent en place (94a3a93 et 4ecc57a en ont besoin) ; agy n'a pas
# --permission-mode : nc_engines force default pour agy quand `agy --help` ne le cite pas
REVISION='ffb19b94f9c98ed98723500efbaa5c2c7f832821'
VALIDATED_REVISIONS=('8867dd093c43a5e5d3f0a13d3e14600e57edc96a','9c12e00ffc6f11732013b575f0652e920331756a',
                     '9cd91bbb6235116e3cadd433eb68fcd9b17203bf','3d1c6b6df5d6bc1352a4b66fcdde74fd56d59175',
                     '64523e57c958f23af459c8069d1a6985bf349640','aae5b9b3e6da13cfb78c2da33b5584c854f5139a',
                     'f522291ca02af08903cbebd32203e14013dc80a6','4ecc57a8351fee610185b699b12c4b15092fe5ff',
                     '94a3a930efae59dbfd7758be5af6f883ab34b9df',REVISION)


def ask(message, default=False):
    value=input(message+(' [O/n] : ' if default else ' [o/N] : ')).strip().lower()
    return value in ('o','oui','y','yes') if value else default


def verification():
    """Vérification préalable (verifier.py, voisin de ce fichier). True : on peut déployer ; False : il manque quelque chose.
    Sans verifier.py (ancienne installation) : on continue, avec un avertissement. Rien n'est modifié ici."""
    here=str(Path(__file__).resolve().parent)
    if here not in sys.path:sys.path.insert(0,here)
    try:import verifier
    except ImportError:
        print('Attention : la vérification préalable n’est pas installée (ancienne version) ; on continue sans elle.')
        return True
    return bool(verifier.verifier(None,print))


def run(args, **kwargs):
    return subprocess.run([str(a) for a in args],check=True,**kwargs)


def read_env(path):
    result={}
    if path.exists():
        for line in path.read_text().splitlines():
            if not line.strip() or line.lstrip().startswith('#') or '=' not in line: continue
            k,v=line.split('=',1);v=v.strip()
            if v.startswith('"'):
                try:v=json.loads(v)
                except ValueError:raise ValueError('Valeur .env multiligne ou non prise en charge : '+k)
            elif v.startswith("'") and v.endswith("'"): v=v[1:-1]
            if not isinstance(v,str):raise ValueError('Valeur .env invalide : '+k)
            result[k.strip()]=v
    return result


def private_write(path, text):
    if path.is_symlink():raise ValueError('Lien symbolique à examiner : '+str(path))
    path.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent,delete=False) as f:
        name=f.name;f.write(text.encode());f.flush();os.fsync(f.fileno())
    try:os.chmod(name,0o600);os.replace(name,path)
    finally:
        if os.path.exists(name):os.unlink(name)


def merge_env(path, values):
    before=read_env(path);before.update(values)
    private_write(path,'\n'.join(k+'='+json.dumps(v,ensure_ascii=False) for k,v in before.items())+'\n')


def resource(name):
    path=Path(__file__).resolve().parent/name
    if path.is_file():return path.read_bytes()
    with zipfile.ZipFile(sys.argv[0]) as archive:return archive.read(name)


def unit_path(value):
    return str(value).replace('%','%%')


def unit_quote(value):
    return '"'+str(value).replace('%','%%').replace('\\','\\\\').replace('"','\\"')+'"'


def units(backend, overlay):
    result={}
    for role,port in (('runner',8080),('gateway',8000)):
        folder=backend/('home-runner' if role=='runner' else 'gateway')
        module='nc_runner:app' if role=='runner' else 'nc_gateway:app'
        # --app-dir passe en tête de sys.path : l'overlay, pour que nos nc_* l'emportent sur les copies du dépôt
        # (gateway/nc_management.py, home-runner/nc_engines.py…) ; main, gateway et bots viennent de folder (revue DEP-01)
        args=[folder/'.venv/bin/uvicorn',module,'--app-dir',overlay,'--host','127.0.0.1','--port',str(port)]
        result['assistant-'+role+'.service']='\n'.join([
            '[Unit]','Description=JARVIS '+role+' (Noctalia)', 'After=network.target', *(
                # Le gateway répond aux messages Telegram en attente dès son démarrage : le runner d'abord (revue SRV-01)
                ['Wants=assistant-runner.service','After=assistant-runner.service'] if role=='gateway' else []), '', '[Service]',
            'WorkingDirectory='+unit_path(folder),'EnvironmentFile='+unit_path(folder/'.env'),
            'Environment='+unit_quote('PYTHONPATH='+str(folder)+':'+str(backend)),
            'ExecStart='+' '.join(unit_quote(a) for a in args),'Restart=on-failure','RestartSec=5',
            'UMask=0077','NoNewPrivileges=true','PrivateTmp=true','','[Install]','WantedBy=default.target',''])
    return result


def configure(backend, mode):
    paths=[backend/'.env',backend/'home-runner/.env',backend/'gateway/.env']
    configs=[read_env(p) for p in paths]
    keys={c['SECRET_KEY'] for c in configs if c.get('SECRET_KEY') and not c['SECRET_KEY'].lower().startswith('change_me')}
    if len(keys)>1:raise ValueError('Les composants ont des clés différentes ; harmonise-les avant le déploiement.')
    current={}
    for config in reversed(configs):current.update(config)
    changes={'SECRET_KEY':next(iter(keys),secrets.token_hex(32)), 'DEPLOY_MODE':mode,
             'HOME_SERVER_URL':current.get('HOME_SERVER_URL','http://127.0.0.1:8080')}
    print('\nÉtape 2 sur 4 : les réglages.\n'
          'D’abord le moteur : c’est l’IA qui répondra à tes messages (agy, codex, claude ou opencode).\n'
          'Tu peux appuyer sur Entrée pour garder le choix proposé entre crochets ; tu pourras le changer plus tard.')
    initial=current.get('NC_JARVIS_ENGINE','agy')
    engine=input('Moteur initial : agy, codex, claude, opencode ['+initial+'] : ').strip() or initial
    if engine not in ('agy','codex','claude','opencode'):raise ValueError('Moteur inconnu.')
    changes['NC_JARVIS_ENGINE']=engine
    print('\nMaintenant ton bot Telegram (facultatif : Entrée pour passer, tu pourras le faire plus tard).\n'
          ' - Le jeton du bot, c’est son mot de passe : écris à @BotFather sur Telegram, tape /newbot, choisis un nom,\n'
          '   puis copie la ligne qui ressemble à 123456789:ABCdef… Ce que tu tapes ne s’affiche pas, c’est normal : colle et valide.\n'
          ' - Ton identifiant Telegram dit au bot de n’obéir qu’à toi : écris à @userinfobot, il te répond un nombre.\n'
          'Discord fonctionne pareil ; si tu ne l’utilises pas, appuie sur Entrée.\n'
          'Les réglages déjà présents sont conservés : une saisie vide ne change rien.')
    for key,label,secret in [('TELEGRAM_TOKEN','Token Telegram',True),('TELEGRAM_ALLOWED_USER_IDS','IDs Telegram autorisés',False),
                              ('DISCORD_TOKEN','Token Discord',True),('DISCORD_ALLOWED_USER_IDS','IDs Discord autorisés',False)]:
        value=(getpass.getpass(label+' (vide : conserver) : ') if secret else input(label+' ['+current.get(key,'')+'] : ')).strip()
        if value:changes[key]=value
    # Ne pas activer automatiquement tous les modules avec des valeurs d'exemple.
    sys.path.insert(0,str(backend))
    from core.tools.base import ToolRegistry
    import core.tools.definitions  # noqa
    print('\nLes modules sont des options en plus (calendrier, domotique…). Tu peux répondre non : tout reste désactivé.')
    if ask('Configurer les modules maintenant ?'):
        for tool in ToolRegistry.list_tools():
            key='ENABLE_TOOL_'+tool.id.upper()
            enabled=ask('Activer '+tool.name+' ?', current.get(key,'0')=='1')
            changes[key]='1' if enabled else '0'
            if enabled:
                for field in tool.params:
                    prompt=field.label+(' (vide : conserver) : ' if field.secret else ' ['+current.get(field.name,str(field.default))+'] : ')
                    value=getpass.getpass(prompt) if field.secret else input(prompt)
                    if value:changes[field.name]=value
                    elif field.name not in current and not field.secret:changes[field.name]=str(field.default)
    elif not any(configs):
        changes.update({ 'ENABLE_TOOL_'+tool.id.upper():'0' for tool in ToolRegistry.list_tools() })
    stamp=datetime.now().strftime('%Y%m%d-%H%M%S')
    for path in paths:
        if path.exists():
            backup=path.with_name(path.name+'.backup-'+stamp);shutil.copy2(path,backup);backup.chmod(0o600)
        # Les valeurs propres à chaque composant restent en place.
        values=dict(current);values.update(read_env(path));values.update(changes)
        merge_env(path,values)
    return changes['SECRET_KEY']


def checkout(backend):
    if not backend.exists():
        run(['git','init',backend]);run(['git','-C',backend,'remote','add','origin',REPO])
        run(['git','-C',backend,'fetch','--depth=1','origin',REVISION]);run(['git','-C',backend,'checkout','--detach','FETCH_HEAD'])
    else:
        remote=subprocess.check_output(['git','-C',backend,'remote','get-url','origin'],text=True).strip()
        remote=remote.replace('git@github.com:','https://github.com/')
        if remote.rstrip('/').removesuffix('.git')!=REPO.removesuffix('.git'):raise ValueError('Le dépôt existant ne pointe pas vers JARVIS-BIS.')
        if subprocess.check_output(['git','-C',backend,'status','--porcelain','--untracked-files=no'],text=True).strip():raise ValueError('Modifications locales du backend : préservées, déploiement arrêté.')
        revision=subprocess.check_output(['git','-C',backend,'rev-parse','HEAD'],text=True).strip()
        if revision not in VALIDATED_REVISIONS:raise ValueError('Backend existant sur une autre révision. Vérifie sa compatibilité avant de changer de version ; aucun reset effectué.')


def deploy(mode, target):
    if sys.version_info<(3,11):raise ValueError('Python 3.11 ou plus récent est nécessaire.')
    if not sys.stdin.isatty():raise ValueError('Lance le déploiement dans un terminal interactif.')
    backend=Path(target).expanduser().resolve()
    if any(c in str(backend) for c in '\n\r:'):raise ValueError('Chemin non pris en charge.')
    # Garder le dossier de données d'une instance existante : une unité sauvegardée
    # ne suffit pas à éviter de relancer les bots sur une base vierge ailleurs.
    for role,folder in (('runner','home-runner'),('gateway','gateway')):
        unit=Path.home()/'.config/systemd/user'/('assistant-'+role+'.service')
        if unit.exists():
            working=next((line.split('=',1)[1].strip().strip('"') for line in unit.read_text().splitlines() if line.startswith('WorkingDirectory=')),None)
            if not working:raise ValueError('Service existant à examiner : '+str(unit))
            working=working.replace('%h',str(Path.home())).replace('%%','%')
            if Path(working).resolve()!=backend/folder:
                raise ValueError('Instance existante dans '+str(Path(working).parent)+'. Réutilise son dossier avec --path après vérification du dépôt ; aucune instance remplacée.')
    if backend.exists() and not (backend/'.git').is_dir():raise ValueError('Le dossier existe sans dépôt Git : aucune copie.')
    print('Étape 0 : on vérifie que ta machine est prête (rien n’est modifié).')
    if not verification():
        print('Il manque quelque chose (voir ci-dessus). Corrige, puis relance nc-jarvis deployer.',file=sys.stderr)
        raise SystemExit(1)
    print('JARVIS-BIS : '+mode+'\nDossier : '+str(backend)+'\nRévision validée : '+REVISION)
    print('\nÉtape 1 sur 4 : télécharger JARVIS et ses dépendances.\n'
          'Ça copie le programme JARVIS dans le dossier ci-dessus et installe ce dont il a besoin, chez toi seulement.\n'
          'Il faut une connexion Internet ; compte quelques minutes. Rien d’autre sur ta machine n’est changé.')
    if not ask('Préparer ce backend (Git, venv et dépendances Python) ?'):return
    checkout(backend)
    # Le guide utilise deux venv ; aucune installation pip globale.
    for folder in ('home-runner','gateway'):
        directory=backend/folder
        if not (directory/'.venv/bin/python').exists():run([sys.executable,'-m','venv',directory/'.venv'])
        python=directory/'.venv/bin/python'
        run([python,'-m','pip','install','-r',directory/'requirements.txt'])
        if folder=='gateway':run([python,'-m','pip','install','-r',backend/'requirements.txt'])
    secret=configure(backend,mode)
    connection=Path.home()/'.local/state/nc-jarvis/connection.conf'
    merge_env(connection,dict(URL='http://127.0.0.1:8000',SECRET_KEY=secret,USER_ID=getpass.getuser(),TIMEOUT='180'))
    overlay=Path.home()/'.local/share/nc-jarvis/server';overlay.mkdir(parents=True,exist_ok=True)
    for name in ('nc_gateway.py','nc_management.py','nc_runner.py','nc_engines.py','nc_telegram.py','nc_noctalia.py','nc_google.py','nc_choix.py'):
        data=resource('server/'+name)
        (overlay/name).write_bytes(data)
    print('\nÉtape 3 sur 4 : faire tourner JARVIS en arrière-plan.\n'
          'On crée deux petits services : le « runner » (il fait le travail) et le « gateway » (il reçoit tes messages Telegram).\n'
          'Ils ne sont joignables que depuis cette machine. Les anciens fichiers éventuels sont sauvegardés.')
    service_dir=Path.home()/'.config/systemd/user';service_dir.mkdir(parents=True,exist_ok=True)
    generated=units(backend,overlay)
    print('Services proposés : '+', '.join(generated)+'\nGateway et runner écouteront seulement sur 127.0.0.1. Les bots restent dans le gateway.')
    started=False
    if ask('Installer/mettre à jour ces services (les anciens seront sauvegardés) ?'):
        for name,content in generated.items():
            path=service_dir/name
            if path.is_symlink():raise ValueError('Service symbolique à examiner : '+str(path))
            if path.exists():shutil.copy2(path,path.with_name(name+'.backup-'+datetime.now().strftime('%Y%m%d-%H%M%S')))
            path.write_text(content)
        run(['systemctl','--user','daemon-reload'])
        if ask('Activer et démarrer/redémarrer ces deux services maintenant ?'):
            run(['systemctl','--user','enable',*generated]);run(['systemctl','--user','restart',*generated]);started=True
    print('Choisis ensuite un moteur dans l’île : agy, Codex, Claude Code ou OpenCode. Le CLI choisi doit être installé et authentifié sur la machine du runner.')
    print('\nÉtape 4 sur 4 : relier le bureau à JARVIS.\n'
          'On écrit l’adresse locale et une clé secrète dans ta configuration, pour que le bureau parle à JARVIS. Rien à saisir.')
    client=Path.home()/'.config/nc/assistant.conf'
    if not client.exists() or ask('Remplacer la connexion client existante par ce backend local ?'):
        if client.exists():shutil.copy2(client,client.with_name('assistant.conf.backup-'+datetime.now().strftime('%Y%m%d-%H%M%S')))
        merge_env(client,dict(URL='http://127.0.0.1:8000',SECRET_KEY=secret,USER_ID=getpass.getuser(),TIMEOUT='180'))
    print('Préparation terminée. Teste nc-assistant verifier. Pour un PC distant, configure son URL HTTPS ou VPN vers le gateway uniquement.')
    print('Sur serveur 24/7 : le maintien des services après déconnexion peut nécessiter loginctl enable-linger (administrateur).')
    print('Accès distant : '+str(backend/'scripts/expose-gateway.sh')+' ; le runner 8080 reste privé.')
    summary(started)


def summary(started):
    if started:print('\nC’est prêt : écris /start à ton bot sur Telegram.')
    else:print('\nC’est presque prêt : les services ne sont pas démarrés. Lance-les avec : systemctl --user enable --now assistant-runner assistant-gateway\nPuis écris /start à ton bot sur Telegram.')
    print('Vérifier que ça tourne : nc-assistant verifier   (ou : systemctl --user status assistant-runner assistant-gateway)\n'
          'Si ça ne marche pas, regarde les messages d’erreur :\n'
          '  journalctl --user -u assistant-gateway -n 50\n'
          '  journalctl --user -u assistant-runner -n 50\n'
          'Arrêter : systemctl --user stop assistant-gateway assistant-runner\n'
          'Relancer : systemctl --user restart assistant-runner assistant-gateway')


def bundle(path):
    with zipfile.ZipFile(path,'w',compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr('__main__.py','from deployer import main\nmain()\n')
        z.writestr('deployer.py',resource('deployer.py'))
        try:z.writestr('verifier.py',resource('verifier.py'))  # la vérification tourne sur le serveur ; absent : ancien dépôt
        except (OSError,KeyError):pass
        for name in ('nc_gateway.py','nc_management.py','nc_runner.py','nc_engines.py','nc_telegram.py','nc_noctalia.py','nc_google.py','nc_choix.py'):z.writestr('server/'+name,resource('server/'+name))


def agent():
    raise ValueError("Le dépôt JARVIS actuel a supprimé le relais PC. Les fonctions matérielles s’exécutent sur la machine hébergeant JARVIS ; aucun ancien relais n’est installé.")


def remote(host):
    if not re.fullmatch(r'(?:[a-zA-Z_][\w.-]*@)?[a-zA-Z0-9][\w.-]*',host):raise ValueError('Adresse SSH attendue : utilisateur@serveur (sans options).')
    with tempfile.TemporaryDirectory(prefix='nc-jarvis-ssh-') as d:
        archive=Path(d)/'bootstrap.pyz';bundle(archive)
        print('Installation sur '+host+' ; aucun token local ne sera transmis.\n'
              'Je me connecte au serveur : il peut te demander ton mot de passe SSH. La vérification préalable et les questions '
              'se passent sur le serveur lui-même (et non sur ce PC).')
        run(['ssh',host,'umask 077; mkdir -p .local/share/nc-jarvis'])
        run(['scp',archive,host+':.local/share/nc-jarvis/bootstrap.pyz'])
        run(['ssh','-t',host,'python3 .local/share/nc-jarvis/bootstrap.pyz --mode server'])
        if ask('Importer la connexion de ce serveur sur le bureau (la connexion existante sera sauvegardée) ?'):
            from urllib.parse import urlsplit
            url=input('URL HTTPS ou VPN du gateway : ').strip().rstrip('/')
            parsed=urlsplit(url)
            if parsed.scheme not in ('http','https') or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment or any(ord(c)<=32 for c in url):raise ValueError('URL de gateway invalide.')
            incoming=Path(d)/'connection.conf'
            run(['scp',host+':.local/state/nc-jarvis/connection.conf',incoming])
            values=read_env(incoming)
            if not values.get('SECRET_KEY') or any(ord(c)<32 or ord(c)>126 for c in values['SECRET_KEY']):raise ValueError('Le serveur n’a pas fourni de clé de connexion valide.')
            path=Path.home()/'.config/nc/assistant.conf'
            existing=read_env(path)
            if path.exists():
                backup=path.with_name('assistant.conf.backup-'+datetime.now().strftime('%Y%m%d-%H%M%S'));shutil.copy2(path,backup);backup.chmod(0o600)
            merge_env(path,dict(URL=url,SECRET_KEY=values['SECRET_KEY'],USER_ID=existing.get('USER_ID',getpass.getuser()),TIMEOUT=existing.get('TIMEOUT','180')))
            print('Connexion importée sans affichage de la clé. Vérifie nc-assistant verifier.')
    print('Sur ton PC : nc-assistant configurer (URL du gateway distant et sa clé).')


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--mode',choices=['local','server'],default='local')
    p.add_argument('--path',default='~/.local/share/jarvis-bis')
    p.add_argument('--serveur')
    p.add_argument('--agent',action='store_true')
    a=p.parse_args(argv)
    try:
        if a.agent:agent()
        elif a.serveur:remote(a.serveur)
        else:deploy(a.mode,a.path)
    except (OSError,ValueError,subprocess.SubprocessError) as e:
        print('Déploiement arrêté : '+str(e),file=sys.stderr);raise SystemExit(1)
    except (KeyboardInterrupt,EOFError):raise SystemExit(130)


if __name__=='__main__':main()

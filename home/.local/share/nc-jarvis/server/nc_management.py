"""Administration authentifiée derrière le gateway, sans exposer le runner.

Aucun shell arbitraire, aucun secret en lecture, aucun remplacement des bots.
"""
import asyncio
import contextlib
import fcntl
import json
import math
import os
from http.cookiejar import CookieJar, DefaultCookiePolicy
from pathlib import Path
import re
import tempfile
from urllib.parse import quote, urlencode

PROTOCOL = 1
UNITS = ('assistant-runner.service', 'assistant-gateway.service')
BASE_FIELDS = [
    ('TELEGRAM_TOKEN', 'Token Telegram', True), ('TELEGRAM_ALLOWED_USER_IDS', 'Utilisateurs Telegram autorisés', False),
    ('DISCORD_TOKEN', 'Token Discord', True), ('DISCORD_ALLOWED_USER_IDS', 'Utilisateurs Discord autorisés', False),
    ('DISCORD_GUILD_ID', 'Serveur Discord', False), ('TELEGRAM_WEBHOOK_URL', 'Webhook Telegram (vide : polling)', False),
    ('BRIEFING_ENABLED', 'Briefing activé (0/1)', False), ('BRIEFING_TIME', 'Heure du briefing', False),
    ('BRIEFING_DAYS', 'Jours du briefing', False), ('BRIEFING_TIMEZONE', 'Fuseau horaire', False),
    ('BRIEFING_CITY', 'Ville du briefing', False), ('BRIEFING_SECTIONS', 'Sections du briefing', False),
]
DEFAULTS = dict(BRIEFING_ENABLED='1', BRIEFING_TIME='08:00', BRIEFING_DAYS='mon,tue,wed,thu,fri,sat,sun',
                BRIEFING_TIMEZONE='Europe/Paris', BRIEFING_SECTIONS='agenda,news,email,weather,tasks')


REQUEST_METHODS = frozenset({'get', 'post', 'put', 'patch', 'delete', 'head', 'options', 'request', 'stream'})


class RequestOptions:
    """Délais propres à chaque appel, sans modifier le client partagé concurrent. Jamais de redirection suivie, même si
    un appel en demande une (follow_redirects=True) : la clé secrète du runner ne doit pas partir ailleurs."""
    def __init__(self, client, timeout):
        self.client, self.timeout = client, timeout

    async def aclose(self):
        """Le pool n'appartient pas à l'emprunteur : seul le lifespan du gateway le ferme."""

    def __getattr__(self, name):
        method = getattr(self.client, name)
        if name not in REQUEST_METHODS:
            return method
        def request(*args, **kwargs):
            kwargs.setdefault('timeout', self.timeout)
            kwargs['follow_redirects'] = False
            return method(*args, **kwargs)
        return request


class NoRunnerCookies(DefaultCookiePolicy):
    def set_ok(self, cookie, request):
        return False


class RunnerConnections:
    """Connexions bornées, ouvertes/fermées avec le gateway ; aucun cache de réponses.

    Le pool appartient à la boucle asyncio qui l'a ouvert (celle d'uvicorn) : ses connexions et ses verrous y sont liés.
    Le polling Telegram tourne dans un autre fil, avec sa propre boucle (nc_telegram, comme l'upstream) ; y prendre le
    pool finissait en « RuntimeError: … is bound to a different event loop » à chaque message. Depuis une autre boucle,
    chaque requête a donc son propre client, fermé aussitôt (voir RunnerLease._single)."""
    def __init__(self):
        self.client = None
        self.loop = None

    def pool(self):
        """Le client du pool, seulement dans la boucle qui l'a ouvert ; sinon None."""
        try:
            courante = asyncio.get_running_loop()
        except RuntimeError:
            return None
        return self.client if self.client is not None and courante is self.loop else None

    @contextlib.asynccontextmanager
    async def lifespan(self):
        import httpx
        if self.client is not None:
            raise RuntimeError('Pool runner déjà ouvert')
        async with httpx.AsyncClient(timeout=30, follow_redirects=False,
                cookies=CookieJar(policy=NoRunnerCookies()),
                limits=httpx.Limits(max_connections=16, max_keepalive_connections=8, keepalive_expiry=60)) as client:
            self.client, self.loop = client, asyncio.get_running_loop()
            try:
                yield
            finally:
                self.client = self.loop = None

    def lease(self, **options):
        """Ce que reçoit le module gateway upstream à la place de httpx.AsyncClient(**options).

        Une future option upstream non prise en charge garde exactement son client dédié : un vrai httpx.AsyncClient,
        en « async with » comme en direct, avec son propre cycle de vie (celui qu'il aurait sans l'overlay).
        « limits » est accepté et ignoré : il ne règle que la taille du pool, et le nôtre a ses propres bornes."""
        if set(options) <= {'timeout', 'follow_redirects', 'limits'} and not options.get('follow_redirects', False):
            return RunnerLease(self, options.get('timeout', 5.0))
        import httpx
        return httpx.AsyncClient(**options)


class RunnerLease:
    """Un emprunt du pool, utilisable des deux façons dont l'upstream crée ses clients.

    - « async with httpx.AsyncClient(...) as client » (jusqu'à aae5b9b) et client partagé gardé en direct (f522291,
      gateway._get_http_client) : dans les deux cas, chaque requête passe par le pool ouvert à ce moment-là, s'il l'a
      été dans la boucle qui appelle ; sinon (avant le démarrage, après l'arrêt, ou depuis la boucle du polling
      Telegram) par un client d'une seule requête, fermé aussitôt, sans cookie ni redirection, avec le même délai. L'emprunt ne possède
      aucune connexion et n'est lié à aucun pool précis : après un rechargement du gateway, il suit le nouveau pool.
    - La sortie d'un « async with » ne ferme rien. is_closed ne devient vrai qu'après aclose() (close_http_client de
      l'upstream), qui ne ferme que l'emprunt, jamais le pool : tant qu'il est faux, l'upstream garde le même objet.
    Les garanties du pool tiennent dans les deux cas : connexions bornées (16), aucun cookie gardé, pas de redirection
    suivie, délai de l'emprunt par défaut et délai de chaque appel respecté, pool fermé avec le gateway. Aucune
    restriction d'adresse, ni avant ni maintenant : la météo directe de f522291 (open-meteo) passe aussi par le pool.
    Les autres attributs d'un client httpx (headers, cookies…) ne sont pas prêtés : les modifier changerait le pool
    commun, alors une utilisation inconnue échoue franchement."""
    def __init__(self, connections, timeout):
        self.connections, self.timeout = connections, timeout
        self.closed = False

    @property
    def is_closed(self):
        return self.closed

    async def aclose(self):
        self.closed = True

    def _check(self):
        if self.closed: raise RuntimeError('Cannot send a request, as the client has been closed.')

    async def __aenter__(self):
        self._check()
        return self

    async def __aexit__(self, *exc):
        """Rien à rendre : l'emprunt ne possède aucune connexion. Ni le pool ni l'emprunt ne sont fermés, même si
        l'upstream entourait un jour son client partagé d'un « async with »."""

    def __getattr__(self, name):
        if name not in REQUEST_METHODS: raise AttributeError(name)
        def request(*args, **kwargs):
            self._check()
            client = self.connections.pool()
            if client is not None:
                return getattr(RequestOptions(client, self.timeout), name)(*args, **kwargs)
            return self._single(name, args, kwargs)
        return request

    def _single(self, name, args, kwargs):
        """Hors du pool (avant le démarrage, après l'arrêt, autre boucle) : un client pour cette seule requête, avec
        les mêmes règles que le pool (aucun cookie, aucune redirection, le délai de l'emprunt par défaut). Il est créé
        et fermé dans la boucle qui appelle : rien n'est partagé entre les boucles."""
        import httpx
        kwargs.setdefault('timeout', self.timeout)
        kwargs['follow_redirects'] = False
        options = dict(follow_redirects=False, cookies=CookieJar(policy=NoRunnerCookies()))
        if name == 'stream':
            @contextlib.asynccontextmanager
            async def stream():
                async with httpx.AsyncClient(**options) as client:
                    async with client.stream(*args, **kwargs) as response:
                        yield response
            return stream()
        async def single():
            async with httpx.AsyncClient(**options) as client:
                return await getattr(client, name)(*args, **kwargs)
        return single()


class RunnerHttpx:
    """Façade limitée au module gateway upstream ; le module httpx global reste intact."""
    def __init__(self, original, connections):
        self.original, self.connections = original, connections

    def __getattr__(self, name):
        return self.connections.lease if name == 'AsyncClient' else getattr(self.original, name)


runner_connections = RunnerConnections()


def root():
    import main
    return Path(main.__file__).resolve().parent.parent


def schema():
    from core.tools.base import ToolRegistry
    fields = [dict(key=k, label=l, secret=s, default=DEFAULTS.get(k,''), group='bots' if k.startswith(('TELEGRAM_', 'DISCORD_')) else 'briefing') for k,l,s in BASE_FIELDS]
    modules = []
    for tool in ToolRegistry.list_tools():
        modules.append(dict(id=tool.id, name=tool.name, description=tool.description, enabled=tool.is_enabled,
                            hardware=tool.requires_local_hardware))
        fields.append(dict(key='ENABLE_TOOL_'+tool.id.upper(), label='Activer '+tool.name, kind='bool', default='1' if tool.is_enabled else '0', secret=False, group=tool.id))
        for p in tool.params:
            if re.fullmatch('[A-Z][A-Z0-9_]{0,100}', p.name) and p.name not in ('SECRET_KEY', 'HOME_SERVER_URL'):
                fields.append(dict(key=p.name, label=p.label, secret=p.secret, group=tool.id, default=str(p.default), kind='number' if getattr(p,'param_type','') in ('int','float') else 'text'))
    for field in fields:
        if field['key']=='BRIEFING_ENABLED': field['kind']='bool'
        value = os.getenv(field['key'], field.get('default', ''))
        if field.get('kind')=='bool': value='1' if value.lower() in ('1','true','yes','on','oui') else '0'
        field['configured'] = bool(value)
        field['value'] = '' if field['secret'] else value
    return dict(protocol=PROTOCOL, modules=modules, fields=fields, shared_session=True, hardware_relay=False)


def rewrite_env(original, values):
    lines, written = [], set()
    for line in original.splitlines():
        key = line.split('=', 1)[0].strip()
        if key in values:
            if key not in written:
                lines.append(key+'='+json.dumps(values[key], ensure_ascii=False)); written.add(key)
        else:
            lines.append(line)
    lines += [k+'='+json.dumps(v, ensure_ascii=False) for k,v in values.items() if k not in written]
    return '\n'.join(lines)+'\n'


def atomic(path, content):
    name = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix='.nc-jarvis-', delete=False) as f:
            name=f.name; f.write(content); f.flush(); os.fsync(f.fileno())
        os.chmod(name, 0o600); os.replace(name, path)
    finally:
        if name and os.path.exists(name): os.unlink(name)


def update_config(values, clear=None):
    clear = clear or []
    if not isinstance(values, dict) or not isinstance(clear,list) or (not values and not clear): raise ValueError
    fields = {f['key']:f for f in schema()['fields']}
    selected = {}
    for key in clear:
        if key not in fields or not fields[key]['secret'] or values.get(key): raise ValueError
        selected[key]=''
    for key, value in values.items():
        if key not in fields or not isinstance(value, str) or len(value)>4000 or any(ord(c)<32 for c in value): raise ValueError
        if fields[key]['secret'] and not value: continue  # un champ masqué vide conserve le token
        if fields[key].get('kind')=='bool' and value not in ('0','1'): raise ValueError
        if fields[key].get('kind')=='number' and (not math.isfinite(float(value)) or float(value)<0): raise ValueError
        if key=='BRIEFING_TIME' and not re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d',value): raise ValueError
        if key in ('TELEGRAM_ALLOWED_USER_IDS','DISCORD_ALLOWED_USER_IDS','DISCORD_GUILD_ID') and value and any(not x.strip().isascii() or not x.strip().isdigit() for x in value.split(',')): raise ValueError
        selected[key]=value
    paths = [root()/'.env', root()/('gateway' if (root()/'gateway').is_dir() else 'render-gateway')/'.env', root()/'home-runner/.env']
    lock = os.open(root()/'.nc-jarvis-config.lock', os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW, 0o600)
    with os.fdopen(lock,'w') as f:
        try: fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError: raise ValueError('Une mise à jour des réglages est déjà en cours.') from None
        old={}
        for path in paths:
            if path.is_symlink(): raise ValueError
            old[path]=path.read_bytes() if path.exists() else None
        changed=[]
        try:
            for path in paths:
                atomic(path, rewrite_env((old[path] or b'').decode('utf-8'), selected).encode('utf-8')); changed.append(path)
        except BaseException:
            for path in reversed(changed):
                if old[path] is None: path.unlink()
                else: atomic(path, old[path])
            raise
    return dict(saved=True, restart_required=True, message='Réglages enregistrés. Redémarre les services pour les appliquer ; les tokens non renseignés sont conservés.')


async def runner(method, path, body=None):
    import httpx
    import main
    if not main.HOME_SERVER_URL: return dict(error='Runner non configuré')
    try:
        async with runner_connections.lease(timeout=30, follow_redirects=False) as client:
            async with client.stream(method, main.HOME_SERVER_URL.rstrip('/')+path,
                                     headers={'X-Secret-Key':main.SECRET_KEY}, json=body) as response:
                if response.status_code != 200: return dict(error='Le runner a refusé la requête (HTTP '+str(response.status_code)+').')
                data=bytearray()
                async for chunk in response.aiter_bytes():
                    data.extend(chunk)
                    if len(data)>2*1024*1024: return dict(error='Réponse du runner trop volumineuse')
                result=json.loads(data)
                if not isinstance(result,dict): return dict(error='Réponse du runner invalide')
                return result
    except (httpx.HTTPError, ValueError, OSError):
        return dict(error='Runner inaccessible ou réponse invalide')


async def command(*args):
    p=await asyncio.create_subprocess_exec(*args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL)
    try:
        out,_=await asyncio.wait_for(p.communicate(),10)
    except BaseException:
        with contextlib.suppress(ProcessLookupError): p.kill()
        await p.wait(); raise
    return p.returncode, out.decode('utf-8',errors='replace')[:40000]


def identifier(value):
    if not isinstance(value,str) or not re.fullmatch(r'[\w-]{1,200}',value,flags=re.ASCII): raise ValueError
    return quote(value,safe='')


def cle_session(value):
    """Clé de session du PC qui demande (« desktop:nom-du-pc ») : avec AGY depuis 64523e5, chaque PC a sa session.
    Absente (ancien client) : la session « default » du runner, comme avant. Depuis 4ecc57a, le serveur impose
    « desktop:<pc> » ou « default » sur cette route : nous aussi (nos clients envoient toujours « desktop: »)."""
    if value is None: return None
    if not isinstance(value,str) or not re.fullmatch(r'default|desktop:[\w.@-]{1,180}',value,flags=re.ASCII): raise ValueError
    return value


# Listes blanches de 4ecc57a pour les réglages de session (permission_mode est aussi refusé par agy_bridge)
PERMISSION_MODES=frozenset({'always-proceed','request-review','default','auto_edit','yolo','ask','bypass','plan','auto'})
MODES=frozenset({'agent','auto','plan','accept-edits','ask'})


async def fin_session_noeuds(session_key, node_id=None):
    """Ferme la session de confiance des machines reliées et change l'identifiant de conversation (4ecc57a). Sans
    effet, sans erreur, sur une révision qui n'a pas ces méthodes ou sans nœud (best effort, comme le serveur)."""
    try:
        from core.node_hub import NODE_HUB
        if node_id is None:
            NODE_HUB.rotate_conversation_token(session_key or 'default')
            await NODE_HUB.send_session_end()
        else:
            return await NODE_HUB.send_session_end(node_id=node_id)
    except Exception:
        pass
    return []


def jeton_conversation(session_key, resultat):
    """Retient le jeton de session rendu par le runner pour les nœuds (4ecc57a) ; sans effet avant."""
    try:
        session=resultat.get('session') if isinstance(resultat,dict) else None
        if isinstance(session,dict) and session.get('session_token'):
            from core.node_hub import NODE_HUB
            NODE_HUB.set_conversation_token(session_key or 'default',str(session['session_token']))
    except Exception:
        pass


async def dispatch(op, p, confirmed=False, session_key=None):
    session_key=cle_session(session_key)
    cle='?'+urlencode(dict(session_key=session_key)) if session_key else ''
    read = {'capabilities','models','session','memory','conversations','usage','conversation.history','services','logs','quick-settings','google.status','google.calendar'}
    write = {'session.update','session.reset','conversation.resume','conversation.delete','memory.add','memory.delete','profile.set','profile.delete','config.update','config.clear','service.restart','notify','noctalia','node.session_end'}
    if op not in read|write: raise ValueError
    if op in ('google.status','google.calendar'):
        # Google Agenda pour l'île, par le jeton Google de JARVIS (nc_google) ; jamais le jeton lui-même
        import nc_google
        return await nc_google.dispatch(op, p)
    if op=='noctalia':
        # Réglages du PC (nc_noctalia) : lecture sans confirmation, le reste avec ; seulement en déploiement local
        import nc_noctalia
        action=p.get('action'); params=p.get('params',{})
        if action not in nc_noctalia.ACTIONS or not isinstance(params,dict): raise ValueError
        if not nc_noctalia.ACTIONS[action]['readonly'] and not confirmed: return dict(error='Confirmation explicite requise')
        arguments=[str(params[f['key']])[:200] for f in nc_noctalia.ACTIONS[action]['fields'] if params.get(f['key'])]
        return await nc_noctalia.agir(action, arguments, confirme=confirmed)
    if op in write and not confirmed: return dict(error='Confirmation explicite requise')
    if op=='notify':
        # Un message Telegram aux chats connus du bot (alertes de la machine : nc-alertes)
        import nc_telegram
        return await nc_telegram.diffuser(p.get('text'))
    if op=='capabilities': return schema()
    paths={'models':'/models','session':'/session'+cle,'memory':'/memory','conversations':'/conversations?limit=25','usage':'/usage/stats'}
    if op in paths: return await runner('GET',paths[op])
    if op=='conversation.history': return await runner('GET','/conversation/'+identifier(p['id'])+'/history')
    if op=='quick-settings': return await runner('GET','/nc/engines'+cle)
    if op=='session.update':
        if not p or set(p)-{'engine','model','effort','mode','permission_mode'} or any(not isinstance(v,str) or len(v)>200 for v in p.values()): raise ValueError
        if (p.get('permission_mode') or 'default') not in PERMISSION_MODES or (p.get('mode') or 'agent') not in MODES: raise ValueError
        return await runner('POST','/nc/engine' if 'engine' in p else '/session',dict(p,session_key=session_key) if session_key else p)
    if op=='session.reset':
        await fin_session_noeuds(session_key)
        resultat=await runner('POST','/session/reset'+cle)
        jeton_conversation(session_key,resultat)
        return resultat
    if op=='conversation.resume':
        identifiant=identifier(p['id'])
        await fin_session_noeuds(session_key)
        resultat=await runner('POST','/conversation/resume',dict(conversation_id=identifiant,**({'session_key':session_key} if session_key else {})))
        jeton_conversation(session_key,resultat)
        return resultat
    if op=='node.session_end':
        noeud=str(p.get('node_id') or 'all').strip()[:64]
        return dict(success=True,closed_nodes=await fin_session_noeuds(session_key,noeud))
    if op=='conversation.delete': return await runner('DELETE','/conversation/'+identifier(p['id']))
    if op=='memory.add':
        text=p['text']
        if not isinstance(text,str) or not 1<=len(text)<=2000: raise ValueError
        return await runner('POST','/memory/facts',dict(text=text))
    if op=='memory.delete': return await runner('DELETE','/memory/facts/'+identifier(p['id']))
    if op=='profile.set': return await runner('POST','/memory/profile',dict(key=p['key'],value=p['value']))
    if op=='profile.delete': return await runner('DELETE','/memory/profile/'+identifier(p['key']))
    if op=='config.update': return await asyncio.to_thread(update_config,p.get('values'))
    if op=='config.clear': return await asyncio.to_thread(update_config,{},p.get('keys'))
    if op=='services':
        results=[]
        for unit in UNITS:
            code,text=await command('systemctl','--user','is-active',unit)
            results.append(dict(unit=unit,active=code==0,state=text.strip() or 'indisponible'))
        return dict(services=results)
    unit=p.get('unit')
    if unit not in UNITS: raise ValueError
    if op=='service.restart':
        code,_=await command('systemctl','--user','--no-block','restart',unit)
        return dict(requested=code==0, message='Redémarrage demandé' if code==0 else 'Redémarrage refusé')
    if op=='logs':
        _,text=await command('journalctl','--user','-u',unit,'-n','60','--no-pager','-o','cat')
        from dotenv import dotenv_values
        for path in (root()/'.env',root()/('gateway' if (root()/'gateway').is_dir() else 'render-gateway')/'.env',root()/'home-runner/.env'):
            for k,v in dotenv_values(path,interpolate=False).items():
                if v and re.search('TOKEN|SECRET|PASSWORD|API_KEY',k): text=text.replace(v,'[masqué]')
        return dict(text=re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]','',text))

"""Administration authentifiée derrière le gateway, sans exposer le runner.

Aucun shell arbitraire, aucun secret en lecture, aucun remplacement des bots.
"""
import asyncio
import contextlib
import fcntl
import json
import math
import os
from pathlib import Path
import re
import tempfile
from urllib.parse import quote

PROTOCOL = 1
UNITS = ('assistant-runner.service', 'assistant-gateway.service', 'assistant-pc-agent.service')
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
    return dict(protocol=PROTOCOL, modules=modules, fields=fields, shared_session=True)


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
    paths = [root()/'.env', root()/'render-gateway/.env', root()/'home-runner/.env']
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
        async with httpx.AsyncClient(timeout=30, follow_redirects=False) as client:
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


async def dispatch(op, p, confirmed=False):
    read = {'capabilities','models','session','memory','conversations','usage','conversation.history','services','logs'}
    write = {'session.update','session.reset','conversation.resume','conversation.delete','memory.add','memory.delete','profile.set','profile.delete','config.update','config.clear','service.restart'}
    if op not in read|write: raise ValueError
    if op in write and not confirmed: return dict(error='Confirmation explicite requise')
    if op=='capabilities': return schema()
    paths={'models':'/models','session':'/session','memory':'/memory','conversations':'/conversations?limit=25','usage':'/usage/stats'}
    if op in paths: return await runner('GET',paths[op])
    if op=='conversation.history': return await runner('GET','/conversation/'+identifier(p['id'])+'/history')
    if op=='session.update':
        if not p or set(p)-{'model','effort','mode','permission_mode'} or any(not isinstance(v,str) or len(v)>200 for v in p.values()): raise ValueError
        return await runner('POST','/session',p)
    if op=='session.reset': return await runner('POST','/session/reset')
    if op=='conversation.resume': return await runner('POST','/conversation/resume',dict(conversation_id=identifier(p['id'])))
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
        for path in (root()/'.env',root()/'render-gateway/.env',root()/'home-runner/.env'):
            for k,v in dotenv_values(path,interpolate=False).items():
                if v and re.search('TOKEN|SECRET|PASSWORD|API_KEY',k): text=text.replace(v,'[masqué]')
        return dict(text=re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]','',text))

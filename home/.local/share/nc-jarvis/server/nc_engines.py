"""Moteurs du runner JARVIS. L'AGY d'origine reste intact ; les autres CLI
reçoivent un contexte textuel borné, indépendant de leurs sessions personnelles.
Aucun shell ni contournement d'approbation n'est ajouté.
"""
import asyncio
import contextlib
import json
import os
from pathlib import Path
import shutil
import signal
import tempfile
import uuid

ENGINES = {'agy': 'Antigravity', 'codex': 'Codex', 'claude': 'Claude Code', 'opencode': 'OpenCode'}
EFFORTS = {'', 'low', 'medium', 'high', 'xhigh', 'max', 'ultra'}


def executable(engine):
    found = shutil.which(engine)
    if found: return found
    candidates = [Path.home()/'.local/bin'/engine, Path.home()/'.cargo/bin'/engine]
    if engine == 'agy': candidates += [Path.home()/'.gemini/antigravity-cli/agy']
    return next((str(p) for p in candidates if p.is_file() and os.access(p, os.X_OK)), None)


def atomique(path, data):
    if path.is_symlink(): raise ValueError('Fichier moteur symbolique : aucune écriture.')
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as f:
        name = f.name
        try:
            f.write(json.dumps(data, ensure_ascii=False).encode()); f.flush(); os.fsync(f.fileno())
            os.chmod(name, 0o600); os.replace(name, path)
        finally:
            if os.path.exists(name): os.unlink(name)


async def process(args, prompt, timeout, cwd):
    """Sorties bornées, groupe entier tué sur timeout/annulation/débordement."""
    p = await asyncio.create_subprocess_exec(*args, cwd=cwd, start_new_session=True,
        stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        env={**os.environ, 'TERM':'dumb', 'NO_COLOR':'1', 'FORCE_COLOR':'0'})
    async def read(stream):
        data = bytearray()
        while True:
            chunk = await stream.read(65536)
            if not chunk: return bytes(data)
            data.extend(chunk)
            if len(data) > 2*1024*1024: raise ValueError('Sortie moteur trop volumineuse.')
    async def write():
        try:
            p.stdin.write(prompt.encode()); await p.stdin.drain()
        except (BrokenPipeError, ConnectionResetError): pass
        finally: p.stdin.close()
    tasks = [asyncio.create_task(read(p.stdout)), asyncio.create_task(read(p.stderr)), asyncio.create_task(write())]
    try:
        out, _, _ = await asyncio.wait_for(asyncio.gather(*tasks), timeout)
        await asyncio.wait_for(p.wait(), 2)
        return p.returncode, out.decode(errors='replace')
    finally:
        # Un enfant peut encore détenir les tubes même si son parent vient de sortir.
        with contextlib.suppress(ProcessLookupError): os.killpg(p.pid, signal.SIGKILL)
        for task in tasks: task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        await p.wait()


def commande(engine, path, model, effort):
    if not isinstance(model, str) or len(model)>200 or any(ord(c)<33 for c in model):
        if model != '': raise ValueError('Identifiant de modèle invalide.')
    if model.startswith('-'): raise ValueError('Identifiant de modèle invalide.')
    if effort not in EFFORTS: raise ValueError('Niveau de réflexion invalide.')
    if engine == 'codex':
        cmd = [path, 'exec', '--skip-git-repo-check', '--ephemeral', '--sandbox', 'read-only', '--json']
        if model: cmd += ['--model', model]
        if effort: cmd += ['-c', 'model_reasoning_effort='+json.dumps(effort)]
        return cmd + ['-']
    if engine == 'claude':
        if effort == 'ultra': raise ValueError('Claude Code ne propose pas le niveau ultra.')
        cmd = [path, '--print', '--output-format', 'json', '--permission-mode', 'plan', '--no-session-persistence']
        if model: cmd += ['--model', model]
        if effort: cmd += ['--effort', effort]
        return cmd
    if engine == 'opencode':
        if effort and not model: raise ValueError('OpenCode demande provider/modèle pour choisir une variante.')
        return [path, 'run', '--format', 'json', '--agent', 'plan'] + (['--model', model+('#'+effort if effort else '')] if model else [])
    raise ValueError('Moteur inconnu.')


def reponse(engine, output):
    if engine == 'claude':
        data = json.loads(output)
        if not isinstance(data,dict): raise ValueError('Réponse Claude invalide.')
        if data.get('is_error'): raise ValueError('Claude Code a refusé la requête.')
        text = data.get('result', '')
    else:
        texts = []
        for line in output.splitlines():
            try: event = json.loads(line)
            except ValueError: continue
            if not isinstance(event,dict): continue
            if engine == 'codex':
                if event.get('type') in ('error', 'turn.failed'): raise ValueError('Codex a refusé la requête.')
                item = event.get('item', {})
                if not isinstance(item,dict): continue
                if event.get('type') == 'item.completed' and item.get('type') == 'agent_message': texts.append(item.get('text', ''))
            else:
                if event.get('type') == 'error': raise ValueError('OpenCode a refusé la requête.')
                part=event.get('part', {})
                if event.get('type') == 'text' and isinstance(part,dict): texts.append(part.get('text', ''))
        text = '\n\n'.join(t for t in texts if isinstance(t, str))
    if not isinstance(text, str) or not text.strip(): raise ValueError('Le moteur n’a renvoyé aucune réponse exploitable.')
    return text.strip()[:64000]


class Engines:
    def __init__(self, upstream):
        self.up = upstream
        names = ('run_agy','get_session_info','update_session','reset_session_async','list_recent_conversations',
                 'get_conversation_history','resume_conversation','delete_conversation','delete_all_conversations','get_token_usage')
        self.original = {n:getattr(upstream,n) for n in names}
        self.should_inject = upstream._should_inject_memory
        self.agy_models = list(upstream.KNOWN_MODELS)
        self.path = Path(upstream.__file__).resolve().parent/'.nc-jarvis-engines.json'
        self.lock = asyncio.Lock()
        initial=os.getenv('NC_JARVIS_ENGINE','agy')
        if initial not in ENGINES: raise ValueError('NC_JARVIS_ENGINE invalide.')
        self.state = dict(engine=initial, settings={}, conversations=[], active={})
        if self.path.exists():
            st = self.path.lstat()
            if self.path.is_symlink() or st.st_mode & 0o077 or st.st_size > 8*1024*1024:
                raise ValueError('État privé des moteurs à vérifier.')
            data = json.loads(self.path.read_text())
            if not isinstance(data,dict) or data.get('engine') not in ENGINES: raise ValueError('État moteur invalide.')
            self.state.update(data)
        if self.state['engine']=='agy' and self.state['settings'].get('agy'):
            self.original['update_session'](**{k:v for k,v in self.state['settings']['agy'].items() if k in ('model','effort','mode','permission_mode')})

    def session(self):
        engine = self.state['engine']
        if engine == 'agy': return dict(self.original['get_session_info'](), engine='agy')
        settings = self.state['settings'].get(engine, {})
        ident = self.state['active'].get(engine)
        conv = next((c for c in self.state['conversations'] if c['id']==ident), {})
        return dict(engine=engine, model=settings.get('model',''), effort=settings.get('effort',''),
                    mode='plan', permission_mode='request-review', conversation_id=ident,
                    has_active_session=bool(conv.get('history')), turns=len(conv.get('history',[])))

    def models(self, engine=None):
        engine = engine or self.state['engine']
        if engine == 'agy': return self.agy_models
        if engine == 'codex':
            path = Path.home()/'.codex/models_cache.json'
            if path.is_file() and path.stat().st_size < 8*1024*1024:
                try:
                    data = json.loads(path.read_text())
                    return [dict(id=m['slug'],name=m.get('display_name',m['slug']),efforts=[e['effort'] for e in m.get('supported_reasoning_levels',[])])
                            for m in data.get('models',[])[:100] if isinstance(m,dict) and isinstance(m.get('slug'),str)]
                except (ValueError, KeyError, TypeError, OSError): pass
        return []  # Ne pas présenter une liste inventée comme celle du compte distant.

    def snapshot(self):
        return dict(session=self.session(), engines=[dict(id=k,name=v,installed=bool(executable(k)),models=self.models(k),
            efforts=(['low','medium','high'] if k=='agy' else ['low','medium','high','xhigh','max'] if k=='claude' else ['low','medium','high','xhigh','max','ultra'] if k=='codex' else [])) for k,v in ENGINES.items()],
            shared_session=True, context_limit=32000)

    def choose(self, **values):
        if self.lock.locked(): raise ValueError('Une réponse est en cours ; attends avant de changer de moteur.')
        if set(values)-{'engine','model','effort','mode','permission_mode'}: raise ValueError('Réglage inconnu.')
        engine = values.get('engine',self.state['engine'])
        if engine not in ENGINES: raise ValueError('Moteur inconnu.')
        if engine != self.state['engine'] and not executable(engine): raise ValueError('Installe et authentifie ce CLI sur la machine du runner.')
        if engine == 'agy':
            result = self.original['update_session'](**{k:v for k,v in values.items() if k!='engine'})
        else:
            if any(values.get(k) not in (None,'',v) for k,v in (('mode','plan'),('permission_mode','request-review'))):
                raise ValueError('Ce moteur utilise le mode plan avec ses protections habituelles.')
            result = dict(self.state['settings'].get(engine,{}))
            result.update({k:v for k,v in values.items() if k in ('model','effort') and v is not None})
            commande(engine, executable(engine) or engine, result.get('model',''), result.get('effort',''))
        state = dict(self.state, engine=engine, settings=dict(self.state['settings'], **{engine:result}))
        atomique(self.path,state); self.state = state
        self.up.KNOWN_MODELS = self.models()
        self.up._reset_memory_injection()
        return self.session()

    async def reset(self):
        if self.lock.locked(): raise ValueError('Une réponse est en cours.')
        async with self.lock:
            if self.state['engine']=='agy': return await self.original['reset_session_async']()
            active=dict(self.state['active']); active.pop(self.state['engine'],None)
            state=dict(self.state,active=active); atomique(self.path,state); self.state=state
            return self.session()

    def conversations(self, limit=8):
        if self.state['engine']=='agy': return self.original['list_recent_conversations'](limit=limit)
        return [dict(id=c['id'],title=c['title'],engine=c['engine']) for c in reversed(self.state['conversations']) if c['engine']==self.state['engine']][:max(0,min(limit,30))]

    def history(self, ident, max_turns=15):
        if self.state['engine']=='agy': return self.original['get_conversation_history'](ident,max_turns=max_turns)
        return next((c['history'][-max(1,min(max_turns,20)):] for c in self.state['conversations'] if c['id']==ident and c['engine']==self.state['engine']), [])

    def resume(self, ident):
        if self.lock.locked(): raise ValueError('Une réponse est en cours.')
        if self.state['engine']=='agy': return self.original['resume_conversation'](ident)
        if not any(c['id']==ident and c['engine']==self.state['engine'] for c in self.state['conversations']): raise ValueError('Conversation inconnue pour ce moteur.')
        state=dict(self.state,active=dict(self.state['active'],**{self.state['engine']:ident}))
        atomique(self.path,state); self.state=state; self.up._reset_memory_injection()
        return dict(session=self.session(),history=self.history(ident))

    def delete(self, ident):
        if self.lock.locked(): return dict(success=False,error='Une réponse est en cours.')
        if self.state['engine']=='agy': return self.original['delete_all_conversations']() if ident=='all' else self.original['delete_conversation'](ident)
        engine=self.state['engine']
        before=len(self.state['conversations'])
        conversations=[c for c in self.state['conversations'] if c['engine']!=engine or (ident!='all' and c['id']!=ident)]
        active=dict(self.state['active'])
        if ident=='all' or active.get(engine)==ident: active.pop(engine,None)
        state=dict(self.state,active=active,conversations=conversations); atomique(self.path,state); self.state=state
        return dict(success=before!=len(self.state['conversations']))

    def usage(self):
        if self.state['engine']=='agy': return self.original['get_token_usage']()
        return dict(engine=self.state['engine'],tokens_available=False,message='Les tokens de ce CLI ne sont pas agrégés par JARVIS.')

    async def run(self, prompt, timeout=120, model=None, effort=None, mode=None,
                  continue_session=True, reset_session_flag=False, permission_mode=None):
        def failure(message): return dict(success=False,output='',error=message,session=self.session())
        if self.lock.locked(): return failure('Une autre requête JARVIS est déjà en cours.')
        async with self.lock:
            engine=self.state['engine']
            if engine=='agy':
                return await self.original['run_agy'](prompt=prompt,timeout=timeout,model=model,effort=effort,mode=mode,
                    continue_session=continue_session,reset_session_flag=reset_session_flag,permission_mode=permission_mode)
            path=executable(engine)
            if not path: return failure('CLI '+ENGINES[engine]+' absent sur la machine du runner.')
            if prompt.lstrip().startswith('/'):
                return failure('Les commandes / d’AGY ne sont pas disponibles avec ce moteur. Utilise les réglages JARVIS.')
            settings=self.state['settings'].get(engine,{})
            ident=self.state['active'].get(engine) if continue_session and not reset_session_flag else None
            conv=next((c for c in self.state['conversations'] if c['id']==ident),None)
            history=list(conv['history']) if conv else []
            while sum(len(h['prompt'])+len(h['response']) for h in history)>12000 or len(history)>10: history.pop(0)
            context='\n\n'.join('Utilisateur : '+h['prompt']+'\nAssistant : '+h['response'] for h in history)
            # Choix cliquables (issue #7) : le gateway retire ce marqueur et en fait des boutons (nc_choix)
            directive=("Consigne : sois direct, concis et précis. Utilise Markdown et LaTeX si pertinent. Pas de bavardage superflu. "
                       "Seulement si l'utilisateur doit choisir parmi quelques options (2 à 5), ajoute en toute dernière ligne "
                       "[CHOIX: Option A | Option B], avec des options courtes.")
            full=directive+'\n\n'+(('Historique récent de cette conversation JARVIS :\n'+context+'\n\nNouvelle demande :\n' if context else '')+prompt)
            memory=self.up.render_memory_prompt()
            if memory: full=memory+'\n\n'+full
            try:
                args=commande(engine,path,model if model is not None else settings.get('model',''),effort if effort is not None else settings.get('effort',''))
                code,out=await process(args,full,timeout,self.path.parent)
                if code: return failure(ENGINES[engine]+' a échoué (code '+str(code)+'). Vérifie son authentification et le modèle sur le runner.')
                answer=reponse(engine,out)
                if continue_session:
                    if not conv:
                        conv=dict(id='nc-'+uuid.uuid4().hex,engine=engine,title=prompt[:100],history=[])
                    history.append(dict(prompt=prompt[:16000],response=answer[:16000]))
                    while sum(len(h['prompt'])+len(h['response']) for h in history)>12000 or len(history)>10: history.pop(0)
                    conversations=[c for c in self.state['conversations'] if c['id']!=conv['id']]+[dict(conv,history=history)]
                    state=dict(self.state,conversations=conversations[-30:],active=dict(self.state['active'],**{engine:conv['id']}))
                    await asyncio.to_thread(atomique,self.path,state); self.state=state
                return dict(success=True,output=answer,error=None,session=self.session())
            except asyncio.TimeoutError: return failure('Délai dépassé ; le processus moteur a été arrêté.')
            except (ValueError,OSError): return failure('Réponse moteur invalide ou indisponible. Vérifie le modèle, la réflexion et l’authentification du CLI.')


def install(upstream):
    engines=Engines(upstream)
    upstream.run_agy=engines.run; upstream.get_session_info=engines.session; upstream.update_session=engines.choose
    upstream.reset_session_async=engines.reset; upstream.list_recent_conversations=engines.conversations
    upstream.get_conversation_history=engines.history; upstream.resume_conversation=engines.resume
    upstream.delete_conversation=engines.delete; upstream.delete_all_conversations=lambda:engines.delete('all')
    upstream.get_token_usage=engines.usage; upstream.KNOWN_MODELS=engines.models()
    upstream._should_inject_memory=lambda version: engines.should_inject(version) if engines.state['engine']=='agy' else False
    return engines

"""Moteurs réels remplacés par de petits CLI locaux, sans compte ni appel modèle."""
import asyncio
import json
import os
from pathlib import Path
import importlib.machinery as importlib_machinery
import importlib.util as importlib_util
import shutil
import subprocess
import sys
import time
import tempfile
import types
import unittest
from unittest.mock import AsyncMock, patch

REPO=Path(__file__).resolve().parents[1]
SOURCE=REPO/'home/.local/share/nc-jarvis/server/nc_engines.py'


class Moteurs(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.m=types.ModuleType('engines_test');exec(compile(SOURCE.read_text(),str(SOURCE),'exec'),self.m.__dict__)
        self.m.isoler=AsyncMock(return_value=None)   # l'isolation systemd a ses propres tests (IsolationMoteur)
        self.opt=patch.object(self.m,'agy_accepte_permission_mode',return_value=True);self.opt.start();self.addCleanup(self.opt.stop)
        self.up=types.SimpleNamespace(__file__=str(self.root/'main.py'),KNOWN_MODELS=[dict(id='agy-test')],
            run_agy=AsyncMock(return_value=dict(success=True,output='AGY')),get_session_info=lambda:dict(model='agy-test',effort='low'),
            update_session=lambda **kw:kw,reset_session_async=AsyncMock(return_value={}),
            list_recent_conversations=lambda **kw:[],get_conversation_history=lambda *a,**kw:[],resume_conversation=lambda *a:{},
            delete_conversation=lambda *a:{},delete_all_conversations=lambda:{},get_token_usage=lambda:dict(tokens_available=False),
            _reset_memory_injection=lambda:None,_should_inject_memory=lambda version:True,render_memory_prompt=lambda:'Mémoire durable')
        self.env=patch.dict(os.environ,HOME=str(self.root));self.env.start();self.addCleanup(self.env.stop)
        self.e=self.m.install(self.up)
        self.cli=self.root/'fake-cli'
        self.cli.write_text('''#!'''+sys.executable+'''
import json,sys
from pathlib import Path
prompt=sys.stdin.read()
Path(__file__).with_suffix('.prompt').write_text(prompt)
Path(__file__).with_suffix('.args').write_text(json.dumps(sys.argv[1:]))
if '--print' in sys.argv: print(json.dumps(dict(result='réponse Claude')))
elif 'exec' in sys.argv: print(json.dumps(dict(type='item.completed',item=dict(type='agent_message',text='réponse Codex'))))
else: print(json.dumps(dict(type='text',part=dict(text='réponse OpenCode'))))
''');self.cli.chmod(0o755)
        self.find=patch.object(self.m,'executable',return_value=str(self.cli));self.find.start();self.addCleanup(self.find.stop)

    def test_each_choice_reaches_its_cli_with_model_effort_and_private_stdin(self):
        for engine,model,effort,expected in [('codex','requested-model','xhigh','Codex'),('claude','sonnet','high','Claude'),('opencode','provider/model','high','OpenCode')]:
            with self.subTest(engine=engine):
                self.e.choose(engine=engine,model=model,effort=effort)
                result=asyncio.run(self.up.run_agy(prompt='question privée'))
                self.assertTrue(result['success'],result);self.assertIn(expected,result['output'])
                args=json.loads(self.cli.with_suffix('.args').read_text())
                self.assertNotIn('question privée',repr(args))
                self.assertIn('question privée',self.cli.with_suffix('.prompt').read_text())
                self.assertIn('Mémoire durable',self.cli.with_suffix('.prompt').read_text())
                self.assertIn('[CHOIX: Option A | Option B]',self.cli.with_suffix('.prompt').read_text())  # issue #7
                self.assertFalse(any('dangerously' in x or x=='--auto' for x in args))
                self.assertIn(model+('#high' if engine=='opencode' else ''),args)
                self.assertFalse(self.up._should_inject_memory('v'))
        self.assertEqual(self.e.path.stat().st_mode&0o777,0o600)

    def test_engine_settings_and_histories_survive_restart_without_crossing_engines(self):
        self.e.choose(engine='codex',model='exact-model',effort='high')
        asyncio.run(self.e.run('première demande'))
        first=self.e.session()['conversation_id']
        asyncio.run(self.e.run('deuxième demande'))
        prompt=self.cli.with_suffix('.prompt').read_text()
        self.assertIn('première demande',prompt);self.assertIn('réponse Codex',prompt)
        self.e.choose(engine='claude',model='',effort='')
        asyncio.run(self.e.run('demande Claude'))
        self.assertNotIn('première demande',self.cli.with_suffix('.prompt').read_text())
        self.e.choose(engine='codex')
        recovered=self.m.Engines(self.up)
        self.assertEqual(recovered.session()['model'],'exact-model')
        self.assertEqual(recovered.session()['conversation_id'],first)
        self.assertEqual(len(self.e.history(first)),2)
        self.assertEqual(self.e.resume(first)['session']['engine'],'codex')
        self.e.delete(first)
        self.assertFalse(self.e.history(first));self.assertFalse(self.e.session()['has_active_session'])

    def test_agy_is_delegated_unchanged_and_missing_cli_cannot_be_selected(self):
        result=asyncio.run(self.e.run('native',model='chosen',effort='high',continue_session=False))
        self.assertEqual(result['output'],'AGY')
        self.e.original['run_agy'].assert_awaited_once_with(prompt='native',timeout=120,model='chosen',effort='high',mode=None,
            continue_session=False,reset_session_flag=False,permission_mode=None)
        with patch.object(self.m,'executable',return_value=None):
            with self.assertRaises(ValueError):self.e.choose(engine='codex')

    def test_parallel_questions_and_settings_are_rejected_and_timeout_kills_children(self):
        self.e.choose(engine='codex')
        async def scenario():
            await self.e.lock.acquire()
            self.assertFalse((await self.e.run('duplicate'))['success'])
            with self.assertRaises(ValueError):self.e.choose(engine='claude')
            self.e.lock.release()
        asyncio.run(scenario())
        async def reset_scenario():
            self.e.choose(engine='agy')
            entered=asyncio.Event();release=asyncio.Event()
            async def controlled_reset():
                entered.set();await release.wait();return {}
            self.e.original['reset_session_async'].side_effect=controlled_reset
            reset=asyncio.create_task(self.e.reset());await entered.wait()
            with self.assertRaises(ValueError):self.e.choose(engine='claude')
            self.assertFalse((await self.e.run('pendant reset'))['success'])
            release.set();await reset
        asyncio.run(reset_scenario())
        self.e.choose(engine='codex')
        self.cli.write_text('#!'+sys.executable+'\nimport time\ntime.sleep(10)\n');self.cli.chmod(0o755)
        result=asyncio.run(self.e.run('timeout',timeout=.1))
        self.assertFalse(result['success']);self.assertIn('Délai',result['error'])
        self.assertFalse(self.e.session()['has_active_session'])

    def test_output_is_bounded_and_failed_cli_is_not_recorded_as_answer(self):
        self.e.choose(engine='codex')
        for script in ("print('invalid json')", "print('[]')", "import sys;sys.stdout.write('x'*2200000)", "import sys;sys.exit(3)"):
            self.cli.write_text('#!'+sys.executable+'\n'+script+'\n');self.cli.chmod(0o755)
            result=asyncio.run(self.e.run('private',timeout=2))
            self.assertFalse(result['success'],result)
            self.assertFalse(self.e.session()['has_active_session'])

    def test_model_catalogue_uses_runner_cache_without_exposing_other_cache_fields(self):
        p=self.root/'.codex/models_cache.json';p.parent.mkdir()
        p.write_text(json.dumps(dict(identity='private-cache-field',models=[dict(slug='exact-model',display_name='Modèle',supported_reasoning_levels=[dict(effort='high')])])) )
        data=self.e.snapshot()
        self.assertNotIn('private-cache-field',json.dumps(data))
        model=next(e for e in data['engines'] if e['id']=='codex')['models'][0]
        self.assertEqual(model,dict(id='exact-model',name='Modèle',efforts=['high']))

    def test_history_and_persistent_file_stay_bounded(self):
        self.e.choose(engine='codex')
        with patch.object(self.m,'process',new_callable=AsyncMock,return_value=(0,json.dumps(dict(type='item.completed',item=dict(type='agent_message',text='a'*16000))))):
            for i in range(25):asyncio.run(self.e.run('p'*16000))
        history=self.e.history(self.e.session()['conversation_id'],max_turns=20)
        self.assertLessEqual(sum(len(h['prompt'])+len(h['response']) for h in history),32000)
        self.assertLess(self.e.path.stat().st_size,2*1024*1024)


class ReglagesEnregistres(unittest.TestCase):
    """94a3a93 refuse « always-proceed » (valeur que 4ecc57a faisait enregistrer par défaut) : le runner doit démarrer."""
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.m=types.ModuleType('engines_reglages');exec(compile(SOURCE.read_text(),str(SOURCE),'exec'),self.m.__dict__)
        self.m.isoler=AsyncMock(return_value=None)   # l'isolation systemd a ses propres tests (IsolationMoteur)
        # ces tests décrivent un agy qui a --permission-mode (le cas sans l'option est dans PermissionModeAgy)
        self.opt=patch.object(self.m,'agy_accepte_permission_mode',return_value=True);self.opt.start();self.addCleanup(self.opt.stop)
        self.recus=[]
        def update_session(model=None,effort=None,mode=None,permission_mode=None,session_key='default'):
            if permission_mode and permission_mode not in ('default','request-review','plan','ask','auto_edit','auto'):
                raise ValueError('permission_mode non autorisé : '+permission_mode)
            self.recus.append(dict(model=model,effort=effort,mode=mode,permission_mode=permission_mode))
            return dict(model=model or 'm',effort=effort or 'high',mode=mode or 'agent',permission_mode=permission_mode or 'request-review',
                        session_token='x'*32)
        self.up=types.SimpleNamespace(__file__=str(self.root/'main.py'),KNOWN_MODELS=[dict(id='agy-test')],
            run_agy=AsyncMock(return_value={}),get_session_info=lambda session_key='default':dict(model='m',effort='high'),
            update_session=update_session,reset_session_async=AsyncMock(return_value={}),
            list_recent_conversations=lambda **kw:[],get_conversation_history=lambda *a,**kw:[],resume_conversation=lambda *a:{},
            delete_conversation=lambda *a:{},delete_all_conversations=lambda:{},get_token_usage=lambda:dict(tokens_available=False),
            _reset_memory_injection=lambda session_key=None:None,_should_inject_memory=lambda version:True,render_memory_prompt=lambda:'')
        self.env=patch.dict(os.environ,HOME=str(self.root));self.env.start();self.addCleanup(self.env.stop)

    def ecrit(self,settings):
        chemin=self.root/'.nc-jarvis-engines.json'
        chemin.write_text(json.dumps(dict(engine='agy',settings=dict(agy=settings),conversations=[],active={})));chemin.chmod(0o600)

    def test_a_saved_always_proceed_does_not_stop_the_runner(self):
        self.ecrit(dict(model='gemini-x',effort='low',mode='agent',permission_mode='always-proceed',session_token='y'*32))
        with self.assertLogs('nc_engines',level='WARNING') as journal:
            e=self.m.Engines(self.up)
        self.assertEqual(e.state['engine'],'agy')
        # les autres réglages sont gardés, le mode refusé est abandonné (donc le mode par défaut du serveur)
        self.assertEqual([r['model'] for r in self.recus if r['model']],['gemini-x'])
        self.assertFalse([r for r in self.recus if r['permission_mode']])
        self.assertNotIn('always-proceed',e.state['settings']['agy'].values())
        self.assertNotIn('y'*32,'\n'.join(journal.output))   # aucun secret dans le journal

    def test_allowed_saved_settings_are_still_restored(self):
        self.ecrit(dict(model='gemini-x',permission_mode='plan'))
        self.m.Engines(self.up)
        self.assertIn('plan',[r['permission_mode'] for r in self.recus])

    def test_choose_saves_only_what_the_user_gave(self):
        e=self.m.Engines(self.up)
        with patch.object(self.m,'executable',return_value='/bin/true'):
            e.choose(engine='agy',model='gemini-x')
        enregistre=json.loads(e.path.read_text())['settings']['agy']
        self.assertEqual(enregistre,dict(model='gemini-x'))
        self.assertNotIn('permission_mode',enregistre);self.assertNotIn('session_token',enregistre)
        with patch.object(self.m,'executable',return_value='/bin/true'):
            e.choose(engine='agy',effort='low')
            e.choose(engine='agy',permission_mode='plan')
        self.assertEqual(json.loads(e.path.read_text())['settings']['agy'],dict(model='gemini-x',effort='low',permission_mode='plan'))

    def permissif(self):
        # comme 4ecc57a : le serveur accepte encore yolo, bypass et always-proceed
        def update_session(model=None,effort=None,mode=None,permission_mode=None,session_key='default'):
            self.recus.append(dict(model=model,effort=effort,mode=mode,permission_mode=permission_mode))
            return dict(model=model or 'm',permission_mode=permission_mode or 'always-proceed')
        self.up.update_session=update_session

    def test_dangerous_modes_refused_even_if_the_server_accepts_them(self):
        self.permissif()
        for mode in ('yolo','bypass','always-proceed','bypassPermissions'):
            with self.subTest(mode=mode):
                self.recus.clear()
                self.ecrit(dict(model='gemini-x',permission_mode=mode))
                with self.assertLogs('nc_engines',level='WARNING'):
                    e=self.m.Engines(self.up)
                self.assertFalse([r for r in self.recus if r['permission_mode']])
                with patch.object(self.m,'executable',return_value='/bin/true'), self.assertRaises(ValueError):
                    e.choose(engine='agy',permission_mode=mode)

    def test_run_drops_a_permission_mode_outside_the_list(self):
        # /run n'est pas contrôlé par l'upstream (P2-2 de 94a3a93) : bypassPermissions ne doit jamais arriver à agy
        e=self.m.Engines(self.up)
        for donne,attendu in (('bypassPermissions',None),('yolo',None),('plan','plan'),(None,None)):
            with self.subTest(mode=donne):
                self.up.run_agy.reset_mock()
                asyncio.run(e.run('bonjour',permission_mode=donne))
                self.assertEqual(self.up.run_agy.call_args.kwargs['permission_mode'],attendu)

    def test_broken_state_file_does_not_stop_the_runner(self):
        chemin=self.root/'.nc-jarvis-engines.json'
        for contenu in ('{pas du json','[]','null',json.dumps(dict(engine='agy',settings=[])),
                        json.dumps(dict(engine='agy',settings=None)),json.dumps(dict(engine='agy',settings=dict(agy='x')))):
            with self.subTest(contenu=contenu):
                chemin.write_text(contenu);chemin.chmod(0o600)
                e=self.m.Engines(self.up)
                self.assertEqual(e.state['engine'],'agy')
                self.assertIsInstance(e.state['settings'],dict)
                self.assertEqual(chemin.read_text(),contenu,'le fichier illisible n\'est pas réécrit')

    def test_same_list_as_nc_management(self):
        texte=(SOURCE.parent/'nc_management.py').read_text()
        ligne=next(l for l in texte.splitlines() if l.startswith('PERMISSION_MODES='))
        self.assertEqual(eval(ligne.split('=',1)[1]),self.m.MODES_PERMIS)


def faux_agy(dossier,aide,code=0):
    """Petit exécutable qui répond à --help (jamais de modèle) et note chaque appel."""
    chemin=Path(dossier)/'agy'
    chemin.write_text('#!'+sys.executable+'\nimport sys\nfrom pathlib import Path\n'
        'Path(__file__).with_suffix(".appels").open("a").write(" ".join(sys.argv[1:])+"\\n")\n'
        'print('+repr(aide)+')\nsys.exit('+str(code)+')\n');chemin.chmod(0o755)
    return chemin


class PermissionModeAgy(unittest.TestCase):
    """agy 1.4.7 n'a pas --permission-mode : sans l'option, seul default est envoyé et permis."""
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.m=types.ModuleType('engines_perm');exec(compile(SOURCE.read_text(),str(SOURCE),'exec'),self.m.__dict__)
        self.m.isoler=AsyncMock(return_value=None)   # l'isolation systemd a ses propres tests (IsolationMoteur)
        self.up=types.SimpleNamespace(__file__=str(self.root/'main.py'),KNOWN_MODELS=[dict(id='agy-test')],
            run_agy=AsyncMock(return_value=dict(success=True,output='AGY')),get_session_info=lambda session_key='default':dict(model='m'),
            update_session=lambda **kw:kw,reset_session_async=AsyncMock(return_value={}),
            list_recent_conversations=lambda **kw:[],get_conversation_history=lambda *a,**kw:[],resume_conversation=lambda *a:{},
            delete_conversation=lambda *a:{},delete_all_conversations=lambda:{},get_token_usage=lambda:dict(tokens_available=False),
            _reset_memory_injection=lambda session_key=None:None,_should_inject_memory=lambda version:True,render_memory_prompt=lambda:'')
        self.env=patch.dict(os.environ,HOME=str(self.root));self.env.start();self.addCleanup(self.env.stop)

    def avec(self,chemin):
        p=patch.object(self.m,'executable',return_value=None if chemin is None else str(chemin));p.start();self.addCleanup(p.stop)

    def test_sans_l_option_run_envoie_default_et_choose_refuse_plan(self):
        self.avec(faux_agy(self.root,'Usage of agy:\n  --mode  Set the agent execution mode (accept-edits, auto, plan)'))
        e=self.m.Engines(self.up)
        for donne in ('plan','request-review',None,'default'):
            with self.subTest(mode=donne):
                self.up.run_agy.reset_mock()
                asyncio.run(e.run('bonjour',permission_mode=donne))
                self.assertEqual(self.up.run_agy.call_args.kwargs['permission_mode'],'default')
        with self.assertRaises(ValueError) as r: e.choose(engine='agy',permission_mode='plan')
        self.assertIn('qu\'un mode de permission',str(r.exception))
        e.choose(engine='agy',permission_mode='default')   # default reste permis
        self.assertEqual(e.snapshot()['engines'][0]['permission_modes'],['default'])

    def test_sans_l_option_la_restauration_abandonne_le_mode(self):
        self.avec(faux_agy(self.root,'Usage of agy:'))
        chemin=self.root/'.nc-jarvis-engines.json'
        chemin.write_text(json.dumps(dict(engine='agy',settings=dict(agy=dict(model='gemini-x',permission_mode='plan')),conversations=[],active={})));chemin.chmod(0o600)
        recus=[];self.up.update_session=lambda **kw:recus.append(kw)
        with self.assertLogs('nc_engines',level='WARNING'):
            e=self.m.Engines(self.up)
        self.assertEqual(recus,[dict(model='gemini-x')]);self.assertNotIn('permission_mode',e.state['settings']['agy'])

    def test_avec_l_option_le_comportement_reste_le_meme(self):
        self.avec(faux_agy(self.root,'Usage of agy:\n  --permission-mode  Mode de permission'))
        e=self.m.Engines(self.up)
        asyncio.run(e.run('bonjour',permission_mode='plan'))
        self.assertEqual(self.up.run_agy.call_args.kwargs['permission_mode'],'plan')
        asyncio.run(e.run('bonjour',permission_mode='yolo'))
        self.assertIsNone(self.up.run_agy.call_args.kwargs['permission_mode'])
        e.choose(engine='agy',permission_mode='plan')
        self.assertEqual(e.snapshot()['engines'][0]['permission_modes'],sorted(self.m.MODES_PERMIS))

    def test_agy_absent_ou_help_en_echec_option_absente(self):
        self.avec(None)
        self.assertFalse(self.m.agy_accepte_permission_mode())
        m2=types.ModuleType('engines_perm2');exec(compile(SOURCE.read_text(),str(SOURCE),'exec'),m2.__dict__)
        with patch.object(m2,'executable',return_value=str(faux_agy(self.root,'--permission-mode',code=2))):
            self.assertFalse(m2.agy_accepte_permission_mode())   # --help en échec, même si le texte cite l'option
        m3=types.ModuleType('engines_perm3');exec(compile(SOURCE.read_text(),str(SOURCE),'exec'),m3.__dict__)
        with patch.object(m3,'executable',return_value=str(self.root/'inexistant')):
            self.assertFalse(m3.agy_accepte_permission_mode())   # OSError

    def test_la_verification_est_faite_une_seule_fois_avec_un_delai(self):
        agy=faux_agy(self.root,'--permission-mode');self.avec(agy)
        for _ in range(3): self.assertTrue(self.m.agy_accepte_permission_mode())
        e=self.m.Engines(self.up);e.snapshot();asyncio.run(e.run('x'))
        self.assertEqual(agy.with_suffix('.appels').read_text(),'--help\n')
        m=types.ModuleType('engines_perm4');exec(compile(SOURCE.read_text(),str(SOURCE),'exec'),m.__dict__)
        with patch.object(m,'executable',return_value='/x/agy'),patch.object(m.subprocess,'run',side_effect=subprocess.TimeoutExpired('agy',5)) as run:
            self.assertFalse(m.agy_accepte_permission_mode());self.assertFalse(m.agy_accepte_permission_mode())
        self.assertEqual(run.call_count,1)
        self.assertEqual(run.call_args.kwargs['timeout'],5);self.assertIs(run.call_args.kwargs.get('shell',False),False)


class UpstreamParPC(unittest.TestCase):
    """JARVIS-BIS 64523e5 (session_key partout) et 3d1c6b6 (aucune) : mêmes appels, aucun TypeError."""
    def charge(self,nouvelle):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup);root=Path(tmp.name)
        m=types.ModuleType('engines_pc');exec(compile(SOURCE.read_text(),str(SOURCE),'exec'),m.__dict__)
        m.isoler=AsyncMock(return_value=None)
        appels=[];sessions={};versions={}
        if nouvelle:
            def info(session_key='default'):return dict(sessions.setdefault(session_key,dict(model='agy',has_active_session=False)),cle=session_key)
            def update(model=None,effort=None,mode=None,permission_mode=None,session_key='default'):
                appels.append(('update',session_key));sessions.setdefault(session_key,{})['effort']=effort;return info(session_key)
            async def reset(session_key='default'):appels.append(('reset',session_key));return info(session_key)
            def resume(conv_id,session_key='default'):appels.append(('resume',conv_id,session_key));return dict(session=info(session_key),history=[])
            async def run(prompt,timeout=600,model=None,effort=None,mode=None,continue_session=True,reset_session_flag=False,permission_mode=None,session_key='default'):
                appels.append(('run',prompt,session_key));await asyncio.sleep(.05);return dict(success=True,output=session_key,session=info(session_key))
            def reset_memoire(session_key='default'):appels.append(('oubli',session_key));versions.pop(session_key,None)
            def should(version,session_key='default'):appels.append(('inject',session_key));return True
        else:
            def info():return dict(model='agy',has_active_session=False)
            def update(model=None,effort=None,mode=None,permission_mode=None):appels.append(('update',));return info()
            async def reset():appels.append(('reset',));return info()
            def resume(conv_id):appels.append(('resume',conv_id));return dict(session=info(),history=[])
            async def run(prompt,timeout=600,model=None,effort=None,mode=None,continue_session=True,reset_session_flag=False,permission_mode=None):
                appels.append(('run',prompt));await asyncio.sleep(.05);return dict(success=True,output='seul',session=info())
            def reset_memoire():appels.append(('oubli',))
            def should(version):appels.append(('inject',));return True
        up=types.SimpleNamespace(__file__=str(root/'main.py'),KNOWN_MODELS=[],run_agy=run,get_session_info=info,update_session=update,
            reset_session_async=reset,list_recent_conversations=lambda limit=8:[],get_conversation_history=lambda *a,**kw:[],
            resume_conversation=resume,delete_conversation=lambda *a:{},delete_all_conversations=lambda:{},get_token_usage=lambda:{},
            _reset_memory_injection=reset_memoire,_should_inject_memory=should,render_memory_prompt=lambda:'',_LAST_INJECTED_MEMORY_VERSIONS=versions)
        env=patch.dict(os.environ,HOME=str(root));env.start();self.addCleanup(env.stop)
        return m,up,m.install(up),appels

    def appels_comme_main(self,up):
        """Exactement les appels de home-runner/main.py à 64523e5."""
        async def scenario():
            self.assertTrue(up._should_inject_memory('v',session_key='client:bureau'))
            up.get_session_info(session_key='client:bureau');up.update_session(model=None,effort='high',mode=None,permission_mode=None,session_key='client:bureau')
            await up.reset_session_async(session_key='client:bureau');up.resume_conversation('c1',session_key='client:bureau')
            return await asyncio.gather(up.run_agy(prompt='a',timeout=5,session_key='client:bureau'),up.run_agy(prompt='b',timeout=5,session_key='client:portable'))
        return asyncio.run(scenario())

    def test_agy_recent_recoit_la_cle_de_chaque_pc_et_tourne_en_parallele(self):
        m,up,e,appels=self.charge(True)
        a,b=self.appels_comme_main(up)
        self.assertEqual((a['output'],b['output']),('client:bureau','client:portable'))  # deux PC, deux sessions, sans attente
        for attendu in [('inject','client:bureau'),('update','client:bureau'),('reset','client:bureau'),('resume','c1','client:bureau'),('run','a','client:bureau'),('run','b','client:portable')]:
            self.assertIn(attendu,appels)
        self.assertEqual(up.get_session_info('client:portable')['cle'],'client:portable')  # appel positionnel de _should_inject_memory
        self.assertFalse(e.snapshot()['shared_session'])
        self.assertEqual(e.agy_en_cours,0)

    def test_agy_ancien_ne_recoit_jamais_session_key(self):
        m,up,e,appels=self.charge(False)
        a,b=self.appels_comme_main(up)
        self.assertTrue(a['success'] and b['success'])
        self.assertTrue(all(len(x)<=2 for x in appels),appels)  # aucun appel n'a reçu de clé
        self.assertTrue(e.snapshot()['shared_session'])

    def test_nos_cli_gardent_une_session_partagee_et_un_seul_verrou(self):
        m,up,e,appels=self.charge(True)
        cli=Path(os.environ['HOME'])/'fake-cli'
        cli.write_text('#!'+sys.executable+"""
import json,sys,time
sys.stdin.read();time.sleep(.3)
print(json.dumps(dict(type='item.completed',item=dict(type='agent_message',text='commune'))))
""");cli.chmod(0o755)
        with patch.object(m,'executable',return_value=str(cli)):
            e.choose(engine='codex',session_key='client:bureau')
            self.assertIn(('oubli','client:bureau'),appels)
            self.assertTrue(e.snapshot()['shared_session'])
            async def scenario():
                return await asyncio.gather(up.run_agy(prompt='bureau',session_key='client:bureau',futur=1),
                                            up.run_agy(prompt='portable',session_key='client:portable'))
            a,b=asyncio.run(scenario())
            self.assertTrue(a['success'],a);self.assertFalse(b['success'])  # un seul verrou pour tous les PC
            self.assertEqual(up.get_session_info(session_key='client:portable')['conversation_id'],e.session()['conversation_id'])
            self.assertFalse(up._should_inject_memory('v',session_key='client:bureau'))
            with self.assertRaises(ValueError):e.choose(session_key='x',inconnu='1')
        self.assertFalse(any(x[0]=='run' for x in appels))

class EnvironnementMoteur(unittest.TestCase):
    """Le moteur ne reçoit ni les jetons du serveur ni son dossier ; IA_MODE=non l'empêche de démarrer."""
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.m=types.ModuleType('engines_env');exec(compile(SOURCE.read_text(),str(SOURCE),'exec'),self.m.__dict__)
        self.m.isoler=AsyncMock(return_value=None)   # l'isolation systemd a ses propres tests (IsolationMoteur)
        self.opt=patch.object(self.m,'agy_accepte_permission_mode',return_value=True);self.opt.start();self.addCleanup(self.opt.stop)
        self.agy=AsyncMock();self.up=types.SimpleNamespace(__file__=str(self.root/'main.py'),KNOWN_MODELS=[],run_agy=self.agy,
            get_session_info=lambda:{},update_session=lambda **kw:kw,reset_session_async=AsyncMock(),
            list_recent_conversations=lambda **kw:[],get_conversation_history=lambda *a,**kw:[],resume_conversation=lambda *a:{},
            delete_conversation=lambda *a:{},delete_all_conversations=lambda:{},get_token_usage=lambda:{},
            _reset_memory_injection=lambda:None,_should_inject_memory=lambda version:True,render_memory_prompt=lambda:'')
        env=dict(HOME=str(self.root),TELEGRAM_TOKEN='faux-tg',DISCORD_TOKEN='faux-dc',SECRET_KEY='faux-secret',
            ANTHROPIC_API_KEY='cle-claude',OPENAI_API_KEY='cle-openai',LC_ALL='C',DEPLOY_MODE='local')
        self.env=patch.dict(os.environ,env);self.env.start();self.addCleanup(self.env.stop)
        self.e=self.m.install(self.up)
        self.cli=self.root/'fake-cli'
        self.cli.write_text('#!'+sys.executable+'''
import json,os,sys
from pathlib import Path
sys.stdin.read()
Path(__file__).with_suffix('.etat').write_text(json.dumps(dict(env=dict(os.environ),cwd=os.getcwd(),vide=os.listdir('.'))))
print(json.dumps(dict(result='ok') if '--print' in sys.argv else dict(type='item.completed',item=dict(type='agent_message',text='ok'))))
''');self.cli.chmod(0o755)
        self.find=patch.object(self.m,'executable',return_value=str(self.cli));self.find.start();self.addCleanup(self.find.stop)

    def etat(self): return json.loads(self.cli.with_suffix('.etat').read_text())

    def test_pas_de_jeton_du_serveur_cle_du_moteur_transmise_cwd_temporaire_supprime(self):
        for engine,presente,absente in (('claude','ANTHROPIC_API_KEY','OPENAI_API_KEY'),('codex','OPENAI_API_KEY','ANTHROPIC_API_KEY')):
            with self.subTest(engine=engine):
                self.e.choose(engine=engine)
                r=asyncio.run(self.up.run_agy(prompt='q',continue_session=False));self.assertTrue(r['success'],r)
                st=self.etat();env=st['env']
                for k in ('TELEGRAM_TOKEN','DISCORD_TOKEN','SECRET_KEY'):self.assertNotIn(k,env)
                self.assertEqual(env[presente],'cle-'+('claude' if presente.startswith('ANTHROPIC') else 'openai'))
                self.assertNotIn(absente,env);self.assertEqual(env['LC_ALL'],'C');self.assertEqual(env['TERM'],'dumb')
                self.assertEqual(st['vide'],[])
                self.assertNotEqual(Path(st['cwd']).resolve(),self.root.resolve())
                self.assertFalse(Path(st['cwd']).exists())

    def test_une_reponse_de_moteur_ne_sort_pas_avec_un_secret_du_env(self):
        """Un faux moteur qui recopie TELEGRAM_TOKEN, SECRET_KEY ou une clé d'API : la ligne est retirée avant de sortir."""
        (self.root/'.env').write_text('TELEGRAM_TOKEN="123456:ABCdef-jeton-secret"\nSECRET_KEY=cle-serveur-0123456789\nBRIEFING_TIME="08:00"\n')
        (self.root/'home-runner').mkdir(); 
        with patch.dict(os.environ,OPENAI_API_KEY='sk-test-abcdef123456'):
            self.cli.write_text('''#!'''+sys.executable+'''
import json,sys
sys.stdin.read()
t="début\\nle jeton est 123456:ABCdef-jeton-secret ok\\nclé cle-serveur-0123456789\\nmoteur sk-test-abcdef123456\\nfin 08:00"
print(json.dumps(dict(type='item.completed',item=dict(type='agent_message',text=t))))
''')
            self.e.choose(engine='codex')
            r=asyncio.run(self.up.run_agy(prompt='q',continue_session=True))
        self.assertTrue(r['success'],r)
        self.assertEqual(r['output'].split('\n'),['début','[secret retiré]','[secret retiré]','[secret retiré]','fin 08:00'])
        for v in ('ABCdef-jeton-secret','cle-serveur-0123456789','sk-test-abcdef123456'):
            self.assertNotIn(v,r['output'])
            self.assertNotIn(v,self.e.path.read_text(),'ni dans l\'historique gardé')

    def test_ia_mode_non_refuse_sans_lancer_le_moteur_en_local(self):
        conf=self.root/'.config/nc';conf.mkdir(parents=True)
        (conf/'reglages.conf').write_text('IA_MODE=auto\n  IA_MODE = "non"\n')
        r=asyncio.run(self.e.run('q'));self.assertFalse(r['success']);self.assertIn('IA_MODE',r['error'])
        self.assertFalse(self.cli.with_suffix('.etat').exists());self.agy.assert_not_called()
        (conf/'reglages.conf').write_text('IA_MODE=non\nIA_MODE=auto\n')   # dernière valeur
        self.e.choose(engine='claude');self.assertTrue(asyncio.run(self.e.run('q',continue_session=False))['success'])
        (conf/'reglages.conf').write_text('IA_MODE=non\n')
        with patch.dict(os.environ,DEPLOY_MODE='server'):                    # serveur de l'hébergeur : réglages du PC absents
            self.assertTrue(asyncio.run(self.e.run('q',continue_session=False))['success'])


def _bus_utilisateur():
    """Un vrai systemd-run --user joignable (le garde-fou des tests a dérouté PATH et XDG_RUNTIME_DIR : on regarde ceux d'avant)."""
    vrai=os.environ.get('NC_TEST_VRAI_RUNTIME') or ''
    return bool(shutil.which('systemd-run',path=os.environ.get('NC_TEST_VRAI_PATH',os.environ.get('PATH'))) and
                ((vrai and os.path.exists(os.path.join(vrai,'bus'))) or os.environ.get('DBUS_SESSION_BUS_ADDRESS')))


class IsolationMoteur(unittest.TestCase):
    """Local : le moteur tourne dans une unité systemd --user où le backend (son .env) est inaccessible ; sans cela, il
    n'est pas lancé. Le faux systemd-run n'isole rien ; le vrai est dans IsolationMoteurReelle."""
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='nc-iso-',dir=self.base_tmp());self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.home=self.root/'home';(self.home/'.claude').mkdir(parents=True)
        (self.home/'.claude/session').write_text('SESSION-DU-MOTEUR')
        self.backend=self.root/'backend';(self.backend/'home-runner').mkdir(parents=True);(self.backend/'gateway').mkdir()
        (self.backend/'.env').write_text('TELEGRAM_TOKEN=123456:ABCdef-jeton-secret\nSECRET_KEY=cle-serveur-0123456789\n')
        (self.backend/'home-runner/.env').write_text('SECRET_KEY=cle-serveur-0123456789\n')
        # nc-bac (la liste des chemins secrets) est lu dans ~/.local/bin, comme en vrai
        (self.home/'.local/bin').mkdir(parents=True)
        for nom in ('nc-bac','nc-noeud'):shutil.copy2(REPO/'home/.local/bin'/nom,self.home/'.local/bin'/nom)   # leurs listes de chemins
        self.secrets={'totp':'.config/nc/noeud-totp.json','conn':'.local/state/nc-jarvis/connection.conf','assist':'.config/nc/assistant.conf',
            'backup':'.config/nc/assistant.conf.backup-20260101','ia':'.config/nc/ia.conf','ssh':'.ssh/id_ed25519','codex':'.codex/auth.json',
            'noct':'.local/state/noctalia/storage.key','homeenv':'.env.backup-1','pki':'.pki/nssdb/key4.db',
            'tor':'.config/torbrowser/profile/x','mullvad':'.config/Mullvad VPN/settings.json','proton':'.config/Proton/a','chromet':'.config/google-chrome-for-testing/a'}
        for rel in self.secrets.values():
            f=self.home/rel;f.parent.mkdir(parents=True,exist_ok=True);f.write_text('SECRET_KEY=faux-secret-0123456789\n')
        # Ce que le moteur ne doit pas pouvoir écrire (du code qui s'exécuterait plus tard hors de l'unité)
        self.ecrits={'runner':'.local/share/nc-jarvis/server/nc_runner.py','bac':'.local/bin/nc-bac','zshrc':'.zshrc.perso',
            'hypr':'.config/hypr/x.lua','desktop':'.local/share/applications/x.desktop','claudeset':'.claude/settings.json',
            'claudemd':'.claude/CLAUDE.md','opencode':'.config/opencode/opencode.json',
            'pth':'.local/lib/python3.99/site-packages/x.pth','node':'.local/lib/node_modules/codex/bin','fastfetch':'.config/fastfetch/config.jsonc',
            'noctshare':'.local/share/noctalia/x','dbus':'.local/share/dbus-1/services/x.service','vim':'.vim/plugin/x.vim','homemd':'CLAUDE.md',
            'envd':'.config/environment.d/x.conf','nautilus':'.local/share/nautilus/scripts/x'}
        self.permis=('.claude.json','.claude/x')   # la config du CLI reste inscriptible (limite connue)
        for rel in self.ecrits.values():
            f=self.home/rel;f.parent.mkdir(parents=True,exist_ok=True)
            if not f.exists():f.write_text('# original\n')
        # La mémoire de l'utilisateur : illisible dans l'unité (tmpfs jetable sur ~/.claude/projects)
        (self.home/'.claude/projects/p1/memory').mkdir(parents=True);(self.home/'.claude/projects/p1/memory/MEMORY.md').write_text('MEMOIRE-UTILISATEUR')
        self.m=types.ModuleType('engines_iso');exec(compile(SOURCE.read_text(),str(SOURCE),'exec'),self.m.__dict__)
        self.opt=patch.object(self.m,'agy_accepte_permission_mode',return_value=True);self.opt.start();self.addCleanup(self.opt.stop)
        self.up=types.SimpleNamespace(__file__=str(self.backend/'home-runner/main.py'),KNOWN_MODELS=[],run_agy=AsyncMock(),
            get_session_info=lambda:{},update_session=lambda **kw:kw,reset_session_async=AsyncMock(),
            list_recent_conversations=lambda **kw:[],get_conversation_history=lambda *a,**kw:[],resume_conversation=lambda *a:{},
            delete_conversation=lambda *a:{},delete_all_conversations=lambda:{},get_token_usage=lambda:{},
            _reset_memory_injection=lambda:None,_should_inject_memory=lambda version:True,render_memory_prompt=lambda:'')
        self.bin=self.root/'bin';self.bin.mkdir()
        env=dict(HOME=str(self.home),TELEGRAM_TOKEN='faux-tg',SECRET_KEY='faux-secret',ANTHROPIC_API_KEY='cle-claude-0123456789',
            DEPLOY_MODE='local',PATH=str(self.bin)+':/usr/bin:/bin',XDG_CACHE_HOME=str(self.home/'.cache'))
        self.env=patch.dict(os.environ,env);self.env.start();self.addCleanup(self.env.stop)
        for k in ('XDG_RUNTIME_DIR','XDG_CONFIG_HOME','XDG_DATA_HOME','XDG_STATE_HOME','CLAUDE_CONFIG_DIR','CODEX_HOME'):os.environ.pop(k,None)
        (self.root/'run').mkdir(mode=0o700);os.environ['XDG_RUNTIME_DIR']=str(self.root/'run')   # (les conteneurs n'ont pas /run/user/UID)
        self.journal=self.root/'journal'
        # Le moteur factice (sh : le python du test peut être hors de ce que voit l'unité) note ce qu'il lit
        self.cli=self.root/'fake-cli'
        self.cli.write_text("""#!/bin/sh
cat >/dev/null
echo lance >> "%(j)s.lance"
r=ok
cat "%(b)s/.env" >/dev/null 2>&1 && r="$r LIT-ENV"
cat "%(b)s/home-runner/.env" >/dev/null 2>&1 && r="$r LIT-ENV-RUNNER"
[ "$(cat "%(h)s/.claude/session" 2>/dev/null)" = SESSION-DU-MOTEUR ] && r="$r SESSION"
[ -n "$TELEGRAM_TOKEN" ] && r="$r JETON"
%(lectures)s%(ecritures)sprintf '{"result":"%%s"}\\n' "$r"
""" % dict(j=self.journal,b=self.backend,h=self.home,lectures=''.join(
            'cat "%s/%s" >/dev/null 2>&1 && r="$r LIT-%s"\n'%(self.home,rel,k.upper()) for k,rel in self.secrets.items()),
            ecritures=''.join('echo x >> "%s/%s" 2>/dev/null && r="$r ECRIT-%s"\n'%(self.home,rel,k.upper()) for k,rel in self.ecrits.items())
            +''.join('echo x >> "%s/%s" 2>/dev/null && r="$r OK-%s"\n'%(self.home,rel,rel.replace('/','_')) for rel in self.permis)
            +'echo x > ./travail.txt 2>/dev/null && r="$r TRAVAIL"\n'
            +'cat "%s/.claude/projects/p1/memory/MEMORY.md" >/dev/null 2>&1 && r="$r LIT-MEMOIRE"\n'%self.home
            +'mkdir -p "%s/.claude/projects/x/memory" && echo x > "%s/.claude/projects/x/memory/MEMORY.md" && r="$r JETABLE-ECRIT"\n'%(self.home,self.home)));self.cli.chmod(0o755)
        self.find=patch.object(self.m,'executable',return_value=str(self.cli));self.find.start();self.addCleanup(self.find.stop)
        self.e=self.m.install(self.up);self.e.choose(engine='claude')
        self.faux_systemd_run('exit 1\n')   # par défaut : pas de systemd-run utilisable (jamais le vrai dans ces tests)

    base_tmp=staticmethod(lambda:None)   # faux programmes : un dossier temporaire ordinaire (/dev/shm peut être noexec)

    def lance(self):return self.journal.with_suffix('.lance').exists()
    def faux_systemd_run(self,corps):
        sr=self.bin/'systemd-run';sr.write_text('#!/bin/sh\n'+corps);sr.chmod(0o755)
    def run_moteur(self):return asyncio.run(self.e.run('q',continue_session=False))

    def test_sans_systemd_run_en_local_le_moteur_n_est_pas_lance(self):
        (self.bin/'systemd-run').unlink()
        with patch.dict(os.environ,PATH=str(self.bin)):   # ni systemd-run ni python3
            r=self.run_moteur()
        self.assertFalse(r['success']);self.assertIn('n’est pas isolée',r['error']);self.assertFalse(self.lance())

    def test_systemd_run_en_echec_la_sonde_refuse_sans_lancer(self):
        self.faux_systemd_run('exit 1\n')
        r=self.run_moteur()
        self.assertFalse(r['success']);self.assertIn('n’est pas isolée',r['error']);self.assertFalse(self.lance())

    def test_serveur_distant_sans_systemd_run_refuse_sauf_variable_du_env_du_serveur(self):
        with patch.dict(os.environ,DEPLOY_MODE='server'):   # systemd-run en échec : pas d'isolation possible
            r=self.run_moteur()
            self.assertFalse(r['success']);self.assertFalse(self.lance())
            self.assertIn('NC_MOTEURS_SANS_ISOLATION=oui',r['error']);self.assertIn('jetons du bot',r['error']);self.assertIn('257',r['error'])
            with patch.dict(os.environ,NC_MOTEURS_SANS_ISOLATION='oui'):   # l'ancien comportement : liste blanche, cwd vide, sans_secrets
                r=self.run_moteur()
        self.assertTrue(r['success'],r);self.assertIn('LIT-ENV',r['output']);self.assertTrue(self.lance())
        self.assertNotIn('JETON',r['output'])

    def test_la_variable_n_est_ni_ecrite_par_le_deployeur_ni_permise_a_distance(self):
        dossier=REPO/'home/.local/share/nc-jarvis'
        self.assertNotIn('NC_MOTEURS_SANS_ISOLATION',(dossier/'deployer.py').read_text())
        gestion=types.ModuleType('gestion_iso')
        src=(dossier/'server/nc_management.py').read_text()
        ligne=next(l for l in src.splitlines() if l.startswith('CONFIG_PERMIS'))
        self.assertNotIn('NC_MOTEURS',ligne);self.assertNotIn('ISOLATION',ligne)

    def test_la_variable_n_ouvre_rien_en_local(self):
        with patch.dict(os.environ,NC_MOTEURS_SANS_ISOLATION='oui'):
            r=self.run_moteur()
        self.assertFalse(r['success']);self.assertFalse(self.lance())

    def test_les_secrets_de_nc_bac_sont_caches_sauf_la_session_du_moteur(self):
        caches=self.m.chemins_caches(self.backend/'home-runner','claude')
        def couvert(chemin,caches):   # le chemin, ou un dossier qui le contient
            return any(c==str(chemin) or c+'/' in str(chemin)+'/' and str(chemin).startswith(c+'/') for c in caches)
        for k,rel in self.secrets.items():self.assertTrue(couvert((self.home/rel).resolve(),caches),k)
        self.assertTrue(couvert((self.home/'.codex/auth.json').resolve(),caches),'la session d\'un autre moteur est cachée')
        self.assertNotIn(str((self.home/'.claude').resolve()),caches);self.assertNotIn(str(self.home),caches)
        self.assertFalse(couvert((self.home/'.codex/auth.json').resolve(),self.m.chemins_caches(self.backend/'home-runner','codex')))
        self.assertFalse(couvert((self.home/'.claude/session').resolve(),caches))

    def test_backend_dans_le_home_cache_les_env_du_home(self):
        self.up.__file__=str(self.home/'home-runner/main.py');(self.home/'home-runner').mkdir()
        caches=self.m.chemins_caches(self.home/'home-runner','claude')
        self.assertIn(str((self.home/'.env.backup-1').resolve()),caches);self.assertNotIn(str(self.home),caches)

    def test_sans_nc_bac_en_local_refus(self):
        (self.home/'.local/bin/nc-bac').unlink()
        with self.assertRaises(self.m.IsolationImpossible):self.m.chemins_caches(self.backend/'home-runner','claude')

    def test_une_protection_qui_ne_tient_pas_est_refusee_par_le_lanceur(self):
        """Le faux systemd-run exécute le moteur SANS rien cacher : le lanceur, qui contrôle chaque chemin caché dans l'unité,
        sort en 97 avant d'exécuter le moteur. Le journal montre la commande et ses propriétés (aucune valeur secrète)."""
        self.faux_systemd_run('echo "$@" >> "%s.args"\nwhile [ $# -gt 0 ] && [ "$1" != "--" ]; do shift; done\nshift\nexec "$@"\n'%self.journal)
        r=self.run_moteur()
        self.assertFalse(r['success']);self.assertIn('n’est pas isolée',r['error']);self.assertFalse(self.lance())
        args=self.journal.with_suffix('.args').read_text()
        for attendu in ('--user','--pipe','--wait','--collect','--expand-environment=no','PrivateUsers=yes','NoNewPrivileges=yes',
                        'PrivatePIDs=yes','PrivateTmp=yes','RestrictAddressFamilies=AF_INET AF_INET6','TemporaryFileSystem=',
                        'TemporaryFileSystem=%s:mode=1777'%(self.home/'.claude/projects').resolve(),
                        'ReadOnlyPaths="-%s"'%(self.home/'.local/bin').resolve(),'ReadOnlyPaths="-%s"'%(self.home/'.claude/settings.json').resolve(),
                        'KillSignal=SIGKILL','RuntimeMaxSec=125','KeyringMode=private','SystemCallFilter=~@debug @keyring','ReadOnlyPaths=-/dev/shm',
                        'ReadOnlyPaths="-%s"'%(self.home/'.local/lib').resolve(),
                        'InaccessiblePaths="-%s"'%(self.home/'.config/Mullvad VPN').resolve(),'InaccessiblePaths="-%s"'%(self.home/'.pki').resolve(),
                        'InaccessiblePaths="-%s"'%self.backend.resolve(),'InaccessiblePaths="-%s"'%(self.backend/'home-runner').resolve(),
                        'InaccessiblePaths="-%s"'%(self.backend/'.env').resolve(),'--setenv=ANTHROPIC_API_KEY','--setenv=HOME'):
            self.assertIn(attendu,args)
        self.assertNotIn('ReadWritePaths',args,'seul un HOME sous /dev/shm (essais réels) est rouvert en écriture')
        for interdit in ('ProtectHome','ProtectSystem=','ReadOnlyPaths=-/dev/shm"','ReadOnlyPaths=%s'%self.home.resolve(),'cle-claude-0123456789','faux-tg',
                         'faux-secret','--setenv=TELEGRAM_TOKEN','--setenv=SECRET_KEY'):
            self.assertNotIn(interdit,args)

    def test_chemins_caches_et_refus_du_dossier_qui_contient_le_home(self):
        caches=self.m.chemins_caches(self.backend/'home-runner')
        for c in (self.backend,self.backend/'home-runner',self.backend/'.env',self.backend/'gateway'):self.assertIn(str(c.resolve()),caches)
        self.assertNotIn(str(self.home),caches)
        with self.assertRaises(self.m.IsolationImpossible):self.m.chemins_caches(self.home)   # contient le HOME
        # le backend entier est facultatif : s'il contient le HOME, seuls ses .env et dossiers voisins sont cachés
        (self.backend/'perso').mkdir()
        (self.backend/'perso/.local/bin').mkdir(parents=True);shutil.copy2(REPO/'home/.local/bin/nc-bac',self.backend/'perso/.local/bin/nc-bac')
        with patch.dict(os.environ,HOME=str(self.backend/'perso')):
            os.environ.pop('XDG_CACHE_HOME')
            caches=self.m.chemins_caches(self.backend/'home-runner')
        self.assertNotIn(str(self.backend.resolve()),caches);self.assertIn(str(self.backend/'.env'),caches)

    def test_chemins_en_lecture_seule_une_seule_source_celle_de_nc_bac_et_nc_noeud(self):
        h=self.home.resolve()
        for rel in ('.config/hypr/x.lua','.local/share/applications/x.desktop','.local/share/nc-jarvis/server/nc_runner.py','.zshrc.perso'):
            (self.home/rel).parent.mkdir(parents=True,exist_ok=True);(self.home/rel).touch()
        for rel in ('.config/hypr','.config/autostart','.config/systemd','.config/fish','.config/pipewire','.config/wireplumber'):(self.home/rel).mkdir(parents=True,exist_ok=True)
        (self.home/'.bashrc').touch();(self.home/'.profile').touch();(self.home/'.zprofile').touch()
        depot=self.root/'depot';depot.mkdir();(self.home/'.config/nc').mkdir(parents=True,exist_ok=True);(self.home/'.config/nc/depot').write_text(str(depot)+'\n')
        caches=self.m.chemins_caches(self.backend/'home-runner','claude')
        ro=self.m.chemins_lecture_seule('claude',caches)
        self.assertIn(str(h/'.local/lib'),ro);self.assertIn(str(h/'CLAUDE.md'),ro)
        for rel in ('.local/bin','.local/share/nc-jarvis','.config/hypr','.local/share/applications','.zshrc.perso',
                    '.config/pipewire','.config/wireplumber','.claude/settings.json','.claude/CLAUDE.md'):
            self.assertIn(str(h/rel),ro,rel)
        for rel in ('.config/systemd','.config/autostart','.bashrc','.profile','.zprofile','.config/fish'):   # PROTEGES de nc-bac : cachés tout à fait
            self.assertIn(str(h/rel),caches,rel);self.assertNotIn(str(h/rel),ro,rel)
        self.assertIn(str(depot.resolve()),ro,'la copie du dépôt')
        for rel in ('.claude','.claude.json','.claude/projects','.codex','.config/nc','.ssh'):self.assertNotIn(str(h/rel),ro,rel)   # inscriptibles, ou déjà cachés
        # Les CLI de claude et d'opencode : ~/.config/opencode reste inscriptible, ses réglages non
        ro=self.m.chemins_lecture_seule('opencode',self.m.chemins_caches(self.backend/'home-runner','opencode'))
        self.assertIn(str(h/'.config/opencode/opencode.json'),ro);self.assertNotIn(str(h/'.config/opencode'),ro)
        self.assertEqual(self.m.chemins_jetables('claude'),[str(h/'.claude/projects'),str(h/'.claude/shell-snapshots')])
        self.assertTrue((h/'.claude/shell-snapshots').is_dir(),'créé vide par le runner : le moteur ne le crée pas dans le vrai HOME')
        (self.home/'.local/bin/nc-noeud').unlink()
        with self.assertRaises(self.m.IsolationImpossible):self.m.chemins_lecture_seule('claude',caches)

    def test_les_listes_lues_dans_nc_noeud_sont_celles_de_nc_noeud(self):
        spec=importlib_util.spec_from_loader('nc_noeud_liste',importlib_machinery.SourceFileLoader('nc_noeud_liste',str(REPO/'home/.local/bin/nc-noeud')))
        mod=importlib_util.module_from_spec(spec);spec.loader.exec_module(mod)
        self.assertEqual(self.m.liste_noeud('ECRITURE_SEULEMENT'),mod.ECRITURE_SEULEMENT)

    def test_message_clair_quand_l_isolation_refuse_une_ecriture(self):
        for brut in ("touch: cannot touch '/home/user/.local/bin/y': Read-only file system","Error: EROFS: read-only file system, open '/home/user/.zshrc'",
                     "EACCES: permission denied, mkdir '/home/user/.config/hypr/a'","bash: /home/user/.local/bin/z: Permission denied"):
            m=self.m.ecriture_refusee(brut)
            self.assertIn('isolation de JARVIS : écriture refusée dans /home/user/',m);self.assertIn('signale-le',m);self.assertIn('write denied',m)
        self.assertIsNone(self.m.ecriture_refusee('Invalid API key'))

    def test_le_lanceur_refuse_un_dossier_temoin_inscriptible_et_un_fichier_inscriptible(self):
        py=shutil.which('python3',path=os.environ['PATH']);ok=self.root/'ro';ok.mkdir();ok.chmod(0o555);self.addCleanup(ok.chmod,0o755)
        ecrit=self.root/'rw';ecrit.mkdir();f=self.root/'fichier';f.write_text('x')
        def lance(temoins,lectures):
            return subprocess.run([py,'-I','-c',self.m.LANCEUR_ISOLE,'',str(self.root),'0',str(len(temoins)),*temoins,str(len(lectures)),*lectures,
                '/bin/echo','lance'],capture_output=True,text=True).returncode
        if os.geteuid():self.assertEqual(lance([str(ok)],[]),0,'dossier en lecture seule : le moteur peut démarrer')
        self.assertEqual(lance([str(ecrit)],[]),self.m.CODE_REFUS_ISOLATION)
        self.assertEqual(list(ecrit.iterdir()),[],'le témoin est supprimé')
        self.assertEqual(lance([],[str(f)]),self.m.CODE_REFUS_ISOLATION)

    def test_un_chemin_a_guillemet_est_refuse_sans_lancer(self):
        faux=self.root/'ba"ckend';shutil.copytree(self.backend,faux)
        self.up.__file__=str(faux/'home-runner/main.py')
        self.faux_systemd_run('exit 0\n')
        r=self.run_moteur();self.assertFalse(r['success']);self.assertFalse(self.lance())


def _shm_utilisable():
    """/dev/shm existe, est inscriptible et n'est pas monté noexec (les conteneurs le montent ainsi : le faux moteur n'y tournerait pas)."""
    try: return os.path.isdir('/dev/shm') and os.access('/dev/shm',os.W_OK) and not os.statvfs('/dev/shm').f_flag&os.ST_NOEXEC
    except OSError: return False


@unittest.skipUnless(_bus_utilisateur() and _shm_utilisable(),'systemd-run, un bus utilisateur joignable et un /dev/shm exécutable requis')
class IsolationMoteurReelle(IsolationMoteur):
    """Le VRAI systemd-run --user (faux HOME, faux backend, faux moteur sous /dev/shm, que l'unité voit ; rien de personnel n'est lu)."""
    base_tmp=staticmethod(lambda:'/dev/shm')
    def setUp(self):
        super().setUp()
        (self.bin/'systemd-run').unlink()
        os.environ['PATH']=os.environ.get('NC_TEST_VRAI_PATH',os.environ['PATH'])
        os.environ['XDG_RUNTIME_DIR']=os.environ['NC_TEST_VRAI_RUNTIME']
        os.environ.pop('XDG_CACHE_HOME',None)
    # Les cas à faux systemd-run ne valent que pour la classe parente
    test_sans_systemd_run_en_local_le_moteur_n_est_pas_lance=None
    test_systemd_run_en_echec_la_sonde_refuse_sans_lancer=None
    test_une_protection_qui_ne_tient_pas_est_refusee_par_le_lanceur=None
    test_un_chemin_a_guillemet_est_refuse_sans_lancer=None
    test_serveur_distant_sans_systemd_run_refuse_sauf_variable_du_env_du_serveur=None
    test_la_variable_n_ouvre_rien_en_local=None
    test_sans_nc_bac_en_local_refus=None
    test_les_secrets_de_nc_bac_sont_caches_sauf_la_session_du_moteur=None
    test_chemins_en_lecture_seule_une_seule_source_celle_de_nc_bac_et_nc_noeud=None
    test_les_listes_lues_dans_nc_noeud_sont_celles_de_nc_noeud=None
    test_message_clair_quand_l_isolation_refuse_une_ecriture=None
    test_le_lanceur_refuse_un_dossier_temoin_inscriptible_et_un_fichier_inscriptible=None
    test_backend_dans_le_home_cache_les_env_du_home=None
    test_chemins_caches_et_refus_du_dossier_qui_contient_le_home=None

    def test_le_moteur_ne_lit_pas_le_env_mais_garde_sa_session(self):
        r=self.run_moteur()
        self.assertTrue(r['success'],r)
        self.assertEqual(r['output'].split(),['ok','SESSION','OK-.claude.json','OK-.claude_x','TRAVAIL','JETABLE-ECRIT'],
                         'ni .env du backend, ni TOTP, ni connection.conf, ni assistant.conf, ni .ssh, ni .env.backup, ni la mémoire de l\'utilisateur ; '
                         'la config du CLI (.claude.json, .claude/x) et le travail restent inscriptibles')
        for k,rel in self.ecrits.items():self.assertEqual((self.home/rel).read_text(),'# original\n' if k not in('bac',) else (REPO/'home/.local/bin/nc-bac').read_text(),k)
        self.assertEqual((self.home/'.claude/projects/p1/memory/MEMORY.md').read_text(),'MEMOIRE-UTILISATEUR')
        self.assertFalse((self.home/'.claude/projects/x').exists(),'ce que le moteur y écrit est jeté avec l\'unité')
        self.assertTrue((self.home/'.claude/x').exists());self.assertTrue((self.home/'.claude.json').read_text().endswith('x\n'))
        self.assertFalse(list((self.home/'.cache/nc-jarvis-travail').glob('moteur-*')),'le dossier de travail est supprimé')

    def test_codex_ne_change_pas_sa_config_mais_ecrit_sa_session(self):
        (self.home/'.codex/sessions').mkdir(parents=True,exist_ok=True);(self.home/'.codex/config.toml').write_text('# original\n')
        (self.home/'.codex/memories').mkdir();(self.home/'.codex/memories/m.md').write_text('MEMOIRE')
        self.cli.write_text('''#!/bin/sh
cat >/dev/null
r=ok
echo x >> "%(h)s/.codex/config.toml" 2>/dev/null && r="$r CONFIG-ECRITE"
echo x > "%(h)s/.codex/sessions/s1" 2>/dev/null && r="$r SESSION-ECRITE"
cat "%(h)s/.codex/memories/m.md" >/dev/null 2>&1 && r="$r LIT-MEMOIRE"
printf '{"type":"item.completed","item":{"type":"agent_message","text":"%%s"}}\\n' "$r"
''' % dict(h=self.home))
        self.e.choose(engine='codex')
        r=self.run_moteur()
        self.assertTrue(r['success'],r);self.assertEqual(r['output'].split(),['ok','SESSION-ECRITE'])
        self.assertEqual((self.home/'.codex/config.toml').read_text(),'# original\n')

    def test_ecriture_refusee_message_clair_au_lieu_de_l_erreur_brute(self):
        self.cli.write_text('#!/bin/sh\ncat >/dev/null\necho x > "%s/.local/bin/nc-bac" || exit 1\necho x > "%s/.local/bin/nouveau-script" || { echo "Error: EROFS: read-only file system, open \'%s/.local/bin/nouveau-script\'" >&2; exit 1; }\n'%(self.home,self.home,self.home))
        r=self.run_moteur()
        self.assertFalse(r['success']);self.assertIn('isolation de JARVIS : écriture refusée dans',r['error']);self.assertIn('please report it',r['error'])
        self.assertNotIn('a échoué',r['error']);self.assertFalse((self.home/'.local/bin/nouveau-script').exists())

    def test_delai_arrete_l_unite_du_moteur(self):
        self.cli.write_text('#!/bin/sh\ncat >/dev/null\nsleep 60\n')
        t=time.monotonic()
        r=asyncio.run(self.e.run('q',timeout=3,continue_session=False))
        self.assertFalse(r['success']);self.assertLess(time.monotonic()-t,15)
        time.sleep(1.5)
        out=subprocess.run([shutil.which('systemctl',path=os.environ['PATH']),'--user','list-units','--all','--plain','--no-legend','nc-jarvis-moteur-*'],
            capture_output=True,text=True,timeout=10).stdout
        self.assertEqual(out.strip(),'','aucune unité de moteur ne reste')


if __name__=='__main__':unittest.main()

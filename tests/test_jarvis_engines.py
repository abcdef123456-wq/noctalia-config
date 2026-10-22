"""Moteurs réels remplacés par de petits CLI locaux, sans compte ni appel modèle."""
import asyncio
import json
import os
from pathlib import Path
import subprocess
import sys
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


class UpstreamParPC(unittest.TestCase):
    """JARVIS-BIS 64523e5 (session_key partout) et 3d1c6b6 (aucune) : mêmes appels, aucun TypeError."""
    def charge(self,nouvelle):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup);root=Path(tmp.name)
        m=types.ModuleType('engines_pc');exec(compile(SOURCE.read_text(),str(SOURCE),'exec'),m.__dict__)
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


if __name__=='__main__':unittest.main()

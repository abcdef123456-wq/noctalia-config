"""Moteurs réels remplacés par de petits CLI locaux, sans compte ni appel modèle."""
import asyncio
import json
import os
from pathlib import Path
import importlib.machinery as importlib_machinery
import importlib.util as importlib_util
import re
import shutil
import stat
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


class _BaseIsolation(unittest.TestCase):
    """Un faux HOME (le « vrai » de ces tests), un faux backend JARVIS avec ses .env, nc-bac et nc-ia copiés comme en vrai dans
    ~/.local/bin, des identifiants de moteurs, et un moteur factice. Rien de personnel n'est lu ni écrit."""
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='nc-iso-',dir=self.base_tmp());self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.home=self.root/'home';(self.home/'.claude').mkdir(parents=True)
        self.backend=self.root/'backend';(self.backend/'home-runner').mkdir(parents=True);(self.backend/'gateway').mkdir()
        (self.backend/'.env').write_text('TELEGRAM_TOKEN=123456:ABCdef-jeton-secret\nSECRET_KEY=cle-serveur-0123456789\n')
        (self.backend/'home-runner/.env').write_text('SECRET_KEY=cle-serveur-0123456789\n')
        # nc-bac (la liste des chemins secrets) et nc-ia (le faux HOME) sont lus dans ~/.local/bin, comme en vrai
        (self.home/'.local/bin').mkdir(parents=True)
        for nom in ('nc-bac','nc-ia'):shutil.copy2(REPO/'home/.local/bin'/nom,self.home/'.local/bin'/nom)
        self.secrets={'totp':'.config/nc/noeud-totp.json','conn':'.local/state/nc-jarvis/connection.conf','assist':'.config/nc/assistant.conf',
            'backup':'.config/nc/assistant.conf.backup-20260101','ia':'.config/nc/ia.conf','ssh':'.ssh/id_ed25519','codex':'.codex/auth.json',
            'noct':'.local/state/noctalia/storage.key','homeenv':'.env.backup-1','pki':'.pki/nssdb/key4.db',
            'tor':'.config/torbrowser/profile/x','mullvad':'.config/Mullvad VPN/settings.json','proton':'.config/Proton/a','chromet':'.config/google-chrome-for-testing/a',
            'session':'.claude/projects/p1/memory/MEMORY.md','mcp':'.claude/hooks/h.sh'}
        for rel in self.secrets.values():
            f=self.home/rel;f.parent.mkdir(parents=True,exist_ok=True);f.write_text('SECRET_KEY=faux-secret-0123456789\n')
        # Les identifiants du moteur : jeton d'accès valable 10 h, jeton de rafraîchissement (qui ne doit pas être copié)
        self.cred=dict(claudeAiOauth=dict(accessToken='AT-ACCES-0123',refreshToken='RT-REFRAICHIR-0123',expiresAt=int((time.time()+36000)*1000),
            scopes=['user:inference'],subscriptionType='max',autreChamp='PAS-COPIE'),mcpOAuth=dict(serveur='PAS-COPIE'))
        (self.home/'.claude/.credentials.json').write_text(json.dumps(self.cred))
        (self.home/'.claude.json').write_text(json.dumps(dict(hasCompletedOnboarding=True,oauthAccount=dict(emailAddress='faux'),
            mcpServers=dict(evil=dict(command='/bin/evil')),projects=dict(p='PAS-COPIE'))))
        (self.home/'.claude/settings.json').write_text(json.dumps(dict(language='fr',hooks=dict(Stop='PAS-COPIE'),apiKeyHelper='/bin/evil')))
        (self.home/'.claude/CLAUDE.md').write_text('consignes de l\'utilisateur\n')
        (self.home/'.codex/auth.json').write_text(json.dumps(dict(OPENAI_API_KEY='sk-PAS-COPIE')))
        self.m=types.ModuleType('engines_iso');exec(compile(SOURCE.read_text(),str(SOURCE),'exec'),self.m.__dict__)
        self.opt=patch.object(self.m,'agy_accepte_permission_mode',return_value=True);self.opt.start();self.addCleanup(self.opt.stop)
        self.up=types.SimpleNamespace(__file__=str(self.backend/'home-runner/main.py'),KNOWN_MODELS=[],run_agy=AsyncMock(),
            get_session_info=lambda:{},update_session=lambda **kw:kw,reset_session_async=AsyncMock(),
            list_recent_conversations=lambda **kw:[],get_conversation_history=lambda *a,**kw:[],resume_conversation=lambda *a:{},
            delete_conversation=lambda *a:{},delete_all_conversations=lambda:{},get_token_usage=lambda:{},
            _reset_memory_injection=lambda:None,_should_inject_memory=lambda version:True,render_memory_prompt=lambda:'')
        self.bin=self.root/'bin';self.bin.mkdir()
        # Ce PATH à lui passe devant les faux du garde-fou : sans ce faux notify-send, le jeton expiré afficherait une VRAIE
        # notification sur le bureau, avec un bouton « Ouvrir » qui lancerait claude dans un vrai kitty
        nf=self.bin/'notify-send';nf.write_text('#!/bin/sh\nexit 0\n');nf.chmod(0o755)
        env=dict(HOME=str(self.home),TELEGRAM_TOKEN='faux-tg',SECRET_KEY='faux-secret',ANTHROPIC_API_KEY='cle-claude-0123456789',
            DEPLOY_MODE='local',PATH=str(self.bin)+':/usr/bin:/bin')
        self.env=patch.dict(os.environ,env);self.env.start();self.addCleanup(self.env.stop)
        for k in ('XDG_RUNTIME_DIR','XDG_CONFIG_HOME','XDG_DATA_HOME','XDG_STATE_HOME','XDG_CACHE_HOME','CLAUDE_CONFIG_DIR','CODEX_HOME'):os.environ.pop(k,None)
        # Un dossier à lui (les conteneurs n'ont pas /run/user/UID), pas sous /tmp : nc-bac refuse un XDG_RUNTIME_DIR que PrivateTmp masquerait
        self.rundir=Path(tempfile.mkdtemp(prefix='nc-iso-run-',dir='/dev/shm')) if os.access('/dev/shm',os.W_OK) else None
        if self.rundir is None:self.skipTest('un /dev/shm inscriptible est requis pour le faux XDG_RUNTIME_DIR')
        self.addCleanup(shutil.rmtree,self.rundir,True);os.environ['XDG_RUNTIME_DIR']=str(self.rundir)
        self.journal=self.root/'journal'
        self.cli=self.root/'fake-cli'
        self.ecrire_cli('cat >/dev/null\necho lance >> "%s.lance"\nprintf \'{"result":"ok"}\\n\'\n'%self.journal)
        self.find=patch.object(self.m,'executable',return_value=str(self.cli));self.find.start();self.addCleanup(self.find.stop)
        self.e=self.m.install(self.up);self.e.choose(engine='claude')
        self.faux_systemd_run('exit 1\n')   # par défaut : pas de systemd-run utilisable (jamais le vrai dans ces tests)

    base_tmp=staticmethod(lambda:None)   # faux programmes : un dossier temporaire ordinaire (/dev/shm peut être noexec)

    def ecrire_cli(self,corps):
        self.cli.write_text('#!/bin/sh\n'+corps);self.cli.chmod(0o755)
    def lance(self):return self.journal.with_suffix('.lance').exists()
    def faux_systemd_run(self,corps):
        sr=self.bin/'systemd-run';sr.write_text('#!/bin/sh\n'+corps);sr.chmod(0o755)
    def run_moteur(self,**kw):return asyncio.run(self.e.run('q',continue_session=False,**kw))
    def args_notes(self):
        f=self.journal.with_suffix('.args');return f.read_text() if f.exists() else ''
    def restes_du_bac(self):
        base=self.rundir/'nc-ia/bac'
        return sorted(os.listdir(base)) if base.is_dir() else []


class IsolationMoteur(_BaseIsolation):
    """Local : le moteur tourne dans une unité systemd --user, avec un faux HOME (celui de nc-ia), où le vrai HOME est en
    lecture seule et le backend (son .env) inaccessible ; sans cela, il n'est pas lancé. Le faux systemd-run n'isole rien
    (il note ses arguments, ou lance la commande telle quelle) ; le vrai est dans IsolationMoteurReelle."""
    def direct(self):
        """Le faux systemd-run note ses arguments puis exécute la commande après « -- » (le lanceur et le moteur), sans rien isoler :
        les propriétés de l'unité sont contrôlées par l'étage réel ; ici le lanceur ne vérifie plus rien, pour voir ce que le moteur reçoit."""
        self.faux_systemd_run('echo "$@" >> "%s.args"\nwhile [ $# -gt 0 ] && [ "$1" != "--" ]; do shift; done\nshift\nexec "$@"\n'%self.journal)
        orig=self.m.lanceur
        p=patch.object(self.m,'lanceur',lambda py,garde,cwd,caches,temoins,reste:orig(py,garde,cwd,[],[],reste));p.start();self.addCleanup(p.stop)
        ia=self.m.module_ia();q=patch.object(ia,'attendre_unite_inactive',return_value=True);q.start();self.addCleanup(q.stop)

    def test_sans_systemd_run_en_local_le_moteur_n_est_pas_lance(self):
        (self.bin/'systemd-run').unlink()
        with patch.dict(os.environ,PATH=str(self.bin)):   # ni systemd-run ni python3
            r=self.run_moteur()
        self.assertFalse(r['success']);self.assertIn('n’est pas isolée',r['error']);self.assertFalse(self.lance())

    def test_systemd_run_en_echec_la_sonde_refuse_sans_lancer_et_ne_laisse_rien(self):
        self.faux_systemd_run('exit 1\n')
        r=self.run_moteur()
        self.assertFalse(r['success']);self.assertIn('n’est pas isolée',r['error']);self.assertFalse(self.lance())
        self.assertEqual(self.restes_du_bac(),[],'ni dossier de sonde ni faux HOME')

    def test_sans_nc_ia_ou_nc_bac_en_local_refus(self):
        self.direct()
        for nom in ('nc-ia','nc-bac'):
            with self.subTest(manque=nom):
                (self.home/'.local/bin'/nom).rename(self.home/'.local/bin'/(nom+'.absent'))
                self.m._NC_IA.clear()
                r=self.run_moteur()
                self.assertFalse(r['success']);self.assertIn('n’est pas isolée',r['error']);self.assertFalse(self.lance())
                (self.home/'.local/bin'/(nom+'.absent')).rename(self.home/'.local/bin'/nom)

    def test_serveur_distant_sans_systemd_run_refuse_sauf_variable_du_env_du_serveur(self):
        with patch.dict(os.environ,DEPLOY_MODE='server'):   # systemd-run en échec : pas d'isolation possible
            r=self.run_moteur()
            self.assertFalse(r['success']);self.assertFalse(self.lance())
            self.assertIn('NC_MOTEURS_SANS_ISOLATION=oui',r['error']);self.assertIn('jetons du bot',r['error']);self.assertIn('257',r['error'])
            with patch.dict(os.environ,NC_MOTEURS_SANS_ISOLATION='oui'):   # l'ancien comportement : liste blanche, cwd vide, sans_secrets
                r=self.run_moteur()
        self.assertTrue(r['success'],r);self.assertTrue(self.lance())

    def test_serveur_distant_sans_nc_ia_meme_unite_sans_faux_home(self):
        (self.home/'.local/bin/nc-ia').unlink();(self.home/'.local/bin/nc-bac').unlink()
        self.faux_systemd_run('echo "$@" >> "%s.args"\nexit 1\n'%self.journal)
        with patch.dict(os.environ,DEPLOY_MODE='server'):
            r=self.run_moteur()
        self.assertFalse(r['success']);self.assertIn('NC_MOTEURS_SANS_ISOLATION=oui',r['error']);self.assertFalse(self.lance())
        args=self.args_notes()
        for attendu in ('PrivatePIDs=yes','KeyringMode=private','TemporaryFileSystem=','InaccessiblePaths="-%s"'%self.backend.resolve(),
                        'InaccessiblePaths="-%s"'%(self.backend/'.env').resolve(),'--setenv=ANTHROPIC_API_KEY'):self.assertIn(attendu,args)
        for absent in ('ProtectHome','BindPaths','nc-ia-'):self.assertNotIn(absent,args)
        self.assertFalse((self.home/'.cache/nc-jarvis-travail').exists() and list((self.home/'.cache/nc-jarvis-travail').iterdir()),'dossier de travail supprimé')

    def test_la_variable_n_est_ni_ecrite_par_le_deployeur_ni_permise_a_distance(self):
        dossier=REPO/'home/.local/share/nc-jarvis'
        self.assertNotIn('NC_MOTEURS_SANS_ISOLATION',(dossier/'deployer.py').read_text())
        src=(dossier/'server/nc_management.py').read_text()
        ligne=next(l for l in src.splitlines() if l.startswith('CONFIG_PERMIS'))
        self.assertNotIn('NC_MOTEURS',ligne);self.assertNotIn('ISOLATION',ligne)

    def test_la_variable_n_ouvre_rien_en_local(self):
        with patch.dict(os.environ,NC_MOTEURS_SANS_ISOLATION='oui'):
            r=self.run_moteur()
        self.assertFalse(r['success']);self.assertFalse(self.lance())

    def test_l_unite_cache_les_secrets_et_les_vrais_dossiers_des_moteurs_le_home_est_en_lecture_seule(self):
        """Le faux systemd-run note la commande de la sonde (les propriétés sont celles de l'unité du moteur) puis échoue."""
        self.faux_systemd_run('echo "$@" >> "%s.args"\nexit 1\n'%self.journal)
        self.run_moteur()
        args=self.args_notes()
        for k,rel in self.secrets.items():
            chemin=(self.home/rel).resolve()
            self.assertTrue(any('InaccessiblePaths="-%s"'%c in args or 'InaccessiblePaths="%s"'%c in args for c in [str(chemin)]+[str(p) for p in chemin.parents if p!=self.home.resolve() and self.home.resolve() in p.parents]),k)
        # les VRAIS dossiers des moteurs sont cachés en entier : le moteur n'a que sa copie (plus de « sauf la session du moteur »)
        for rel in ('.claude','.claude.json','.codex'):self.assertIn('InaccessiblePaths="%s"'%(self.home/rel).resolve(),args,rel)
        for attendu in ('--user','--pipe','--wait','--collect','--expand-environment=no','PrivateUsers=yes','NoNewPrivileges=yes','PrivatePIDs=yes',
                        'PrivateDevices=yes','PrivateIPC=yes','ProtectControlGroups=yes','PrivateTmp=yes','RestrictAddressFamilies=AF_INET AF_INET6','KillSignal=SIGKILL',
                        'KeyringMode=private','SystemCallFilter=~@debug @keyring','ReadOnlyPaths=-/dev/shm','ProtectHome=read-only','ProtectSystem=strict',
                        'ReadOnlyPaths=%s'%self.home,'TemporaryFileSystem=%s:ro'%self.rundir.resolve(),'BindPaths=%s/nc-ia/bac/nc-ia-sonde-'%self.rundir.resolve(),
                        'InaccessiblePaths="-%s"'%(self.home/'.config/Mullvad VPN').resolve(),'InaccessiblePaths="-%s"'%(self.home/'.pki').resolve(),
                        'InaccessiblePaths="-%s"'%self.backend.resolve(),'InaccessiblePaths="-%s"'%(self.backend/'home-runner').resolve(),
                        'InaccessiblePaths="-%s"'%(self.backend/'.env').resolve(),'--unit=nc-ia-'):
            self.assertIn(attendu,args)
        for interdit in ('cle-claude-0123456789','faux-tg','faux-secret','--setenv=TELEGRAM_TOKEN','--setenv=SECRET_KEY','--setenv=XDG_'):
            self.assertNotIn(interdit,args)
        self.assertNotIn('ReadWritePaths',args)

    def test_une_protection_qui_ne_tient_pas_est_refusee_par_le_lanceur(self):
        """Le faux systemd-run exécute le moteur SANS rien cacher : le lanceur, qui contrôle dans l'unité chaque chemin caché et
        l'écriture du vrai HOME, sort en 97 avant d'exécuter quoi que ce soit (sonde comprise)."""
        self.faux_systemd_run('echo "$@" >> "%s.args"\nwhile [ $# -gt 0 ] && [ "$1" != "--" ]; do shift; done\nshift\nexec "$@"\n'%self.journal)
        r=self.run_moteur()
        self.assertFalse(r['success']);self.assertIn('n’est pas isolée',r['error']);self.assertFalse(self.lance())
        self.assertEqual(self.restes_du_bac(),[])

    def test_le_lanceur_refuse_un_chemin_lisible_et_un_dossier_inscriptible(self):
        py=shutil.which('python3',path=os.environ['PATH']);ok=self.root/'ro';ok.mkdir();ok.chmod(0o555);self.addCleanup(ok.chmod,0o755)
        ecrit=self.root/'rw';ecrit.mkdir();lisible=self.root/'lisible';lisible.mkdir();secret=self.root/'secret';secret.mkdir(mode=0o000);self.addCleanup(secret.chmod,0o700)
        def lance(caches,temoins):
            return subprocess.run(self.m.lanceur(py,'',self.root,caches,temoins,['/bin/echo','lance']),capture_output=True,text=True).returncode
        if os.geteuid():
            self.assertEqual(lance([str(secret)],[str(ok)]),0,'caché et en lecture seule : le moteur peut démarrer')
            self.assertEqual(lance([str(lisible)],[]),self.m.CODE_REFUS_ISOLATION)
        self.assertEqual(lance([],[str(ecrit)]),self.m.CODE_REFUS_ISOLATION)
        self.assertEqual(list(ecrit.iterdir()),[],'le témoin est supprimé')

    def test_le_moteur_recoit_un_faux_home_avec_les_seuls_champs_copies_et_rien_ne_revient(self):
        """Le faux systemd-run lance le moteur tel quel (lanceur sans contrôle) : on voit ce qu'il reçoit dans son faux HOME."""
        self.direct()
        os.environ['CLAUDE_CONFIG_DIR']=str(self.home/'.claude')   # un dossier déplacé : le moteur ne doit pas le recevoir
        self.ecrire_cli('cat >/dev/null\nj="%(j)s"\nenv | sort > "$j.env"\nfind "$HOME" | sort > "$j.fichiers"\npwd > "$j.pwd"\n'
                        'cat "$HOME/.claude/.credentials.json" > "$j.cred" 2>/dev/null\ncat "$HOME/.claude.json" > "$j.cj" 2>/dev/null\n'
                        'cat "$HOME/.claude/settings.json" > "$j.set" 2>/dev/null\necho x > "$HOME/.zshenv"; echo x >> "$HOME/.claude/.credentials.json"\n'
                        'echo "$HOME" > "$j.home"\nprintf \'{"result":"ok"}\\n\'\n'%dict(j=self.journal))
        avant={p:p.read_bytes() for p in self.home.rglob('*') if p.is_file()}
        r=self.run_moteur()
        self.assertTrue(r['success'],r)
        lu=lambda s:self.journal.with_suffix(s).read_text()
        faux=lu('.home').strip()
        self.assertTrue(faux.startswith(str(self.rundir/'nc-ia/bac/nc-ia-home-')),faux)
        self.assertEqual(lu('.pwd').strip().rsplit('-',1)[0],str(self.rundir/'nc-ia/bac/nc-ia-travail'))
        env=dict(l.split('=',1) for l in lu('.env').splitlines() if '=' in l)
        self.assertEqual(env['HOME'],faux);self.assertEqual(env['ANTHROPIC_API_KEY'],'cle-claude-0123456789');self.assertEqual(env['DISABLE_AUTOUPDATER'],'1')
        for absent in ('TELEGRAM_TOKEN','SECRET_KEY','XDG_CONFIG_HOME','XDG_DATA_HOME','XDG_STATE_HOME','XDG_CACHE_HOME','CLAUDE_CONFIG_DIR','CODEX_HOME','XDG_RUNTIME_DIR'):
            self.assertNotIn(absent,env)
        # champ par champ, comme COPIES de nc-ia : le jeton d'accès et ce qu'il faut pour s'en servir, jamais le jeton de rafraîchissement
        cred=json.loads(lu('.cred'))
        self.assertEqual(sorted(cred['claudeAiOauth']),['accessToken','expiresAt','scopes','subscriptionType'])
        self.assertNotIn('mcpOAuth',cred);self.assertNotIn('RT-REFRAICHIR',lu('.cred').replace('x\n',''))
        self.assertEqual(sorted(json.loads(lu('.cj'))),['hasCompletedOnboarding','oauthAccount'])
        self.assertEqual(json.loads(lu('.set')),dict(language='fr'))
        fichiers=lu('.fichiers')
        self.assertNotIn('.codex',fichiers);self.assertNotIn('hooks',fichiers)
        # rien n'a changé dans le vrai HOME, le faux HOME est supprimé, ni le jeton écrit dedans ni .zshenv ne reviennent
        self.assertEqual(avant,{p:p.read_bytes() for p in self.home.rglob('*') if p.is_file()})
        self.assertEqual(self.restes_du_bac(),[])
        # la commande du moteur (2e appel, après la sonde) : ses variables passent par --setenv, seuls le faux HOME et le travail sont remontés
        moteur=self.args_notes().split('--user --wait')[2]
        for attendu in ('--setenv=ANTHROPIC_API_KEY','--setenv=HOME','BindPaths='+faux,'BindPaths='+lu('.pwd').strip(),'--unit=nc-ia-','KeyringMode=private'):self.assertIn(attendu,moteur)
        for interdit in ('--setenv=XDG_','--setenv=CLAUDE_CONFIG_DIR','--setenv=TELEGRAM_TOKEN','cle-claude-0123456789','BindPaths='+str(self.home)):self.assertNotIn(interdit,moteur)

    def test_les_pieces_jointes_sont_copiees_pour_le_tour_seulement(self):
        """#31 : le runner cite /tmp/assistant_uploads/… (son /tmp privé) ; le moteur, dans son unité, n'y a pas accès. La
        demande en cours pointe vers une copie dans pieces-jointes/ du dossier de travail, effacée avec lui. Refusés : un
        lien symbolique, un lien physique, un fichier hors du dossier, au-delà de 5 fichiers."""
        self.direct()
        pieces=self.root/'uploads';pieces.mkdir()
        os.environ['NC_PIECES_JOINTES']=str(pieces)
        (pieces/'ab12_notes.txt').write_text('contenu des notes')
        (self.root/'secret').write_text('SECRET-HORS-DOSSIER')
        (pieces/'cd34_lien.txt').symlink_to(self.root/'secret')
        os.link(self.root/'secret',pieces/'ef56_physique.txt')
        for i in range(6):(pieces/('n%d_x.txt'%i)).write_text('n%d'%i)
        lignes=["[Fichier fourni par l'utilisateur: %s]"%(pieces/'ab12_notes.txt'),
                "[Fichier fourni par l'utilisateur: %s]"%(pieces/'cd34_lien.txt'),
                "[Fichier fourni par l'utilisateur: %s]"%(pieces/'ef56_physique.txt'),
                "[Fichier fourni par l'utilisateur: %s]"%(self.root/'secret'),
                "[Fichier fourni par l'utilisateur: %s/../secret]"%pieces]+[
                "[Fichier fourni par l'utilisateur: %s]"%(pieces/('n%d_x.txt'%i)) for i in range(6)]
        self.ecrire_cli('p=$(cat)\nprintf "%%s" "$p" > "%(j)s.prompt"\n'
                        'printf "%%s\\n" "$p" | sed -n "s/^\\[.* par l.utilisateur: \\(.*\\)\\]$/\\1/p" | while read -r f; do cat "$f" >> "%(j)s.lu"; echo >> "%(j)s.lu"; done\n'
                        'printf \'{"result":"ok"}\\n\''%dict(j=self.journal))
        r=asyncio.run(self.e.run('\n'.join(lignes)+'\n\nRésume ce fichier.',continue_session=False))
        self.assertTrue(r['success'],r)
        vu=self.journal.with_suffix('.prompt').read_text()
        copie=re.search(r"\[Fichier fourni par l'utilisateur: (\S+/pieces-jointes/ab12_notes\.txt)\]",vu)
        self.assertTrue(copie,vu)
        self.assertTrue(copie.group(1).startswith(str(self.rundir/'nc-ia/bac/nc-ia-travail')),copie.group(1))
        lu=self.journal.with_suffix('.lu').read_text()
        self.assertIn('contenu des notes',lu)
        self.assertNotIn('SECRET-HORS-DOSSIER',lu)
        self.assertNotIn(str(pieces),vu)                                          # aucun chemin du /tmp du runner ne reste
        self.assertEqual(vu.count('non transmis à ce moteur'),4+2)                  # lien, physique, hors dossier ×2, 6e et 7e
        self.assertEqual([l for l in lu.splitlines() if l.startswith('n')],['n0','n1','n2','n3'])   # 5 fichiers au plus
        self.assertIn('Résume ce fichier.',vu)
        self.assertFalse(Path(copie.group(1)).exists())                           # effacée à la fin du tour
        self.assertEqual((pieces/'ab12_notes.txt').read_text(),'contenu des notes')
        self.assertEqual(self.restes_du_bac(),[])

    def test_pieces_jointes_de_l_historique_ignorees_et_copie_sans_exception(self):
        pieces=self.root/'uploads';pieces.mkdir();os.environ['NC_PIECES_JOINTES']=str(pieces)
        travail=self.root/'travail';travail.mkdir()
        self.assertEqual(self.m.copier_pieces('Bonjour',travail),'Bonjour')
        texte="[Image fournie par l'utilisateur: %s]\nQuoi ?"%(pieces/'absent.png')
        self.assertEqual(self.m.copier_pieces(texte,travail),"[Fichier joint non transmis à ce moteur : absent.png]\nQuoi ?")
        self.assertEqual(self.m.copier_pieces(texte,self.root/'inexistant'),"[Fichier joint non transmis à ce moteur : absent.png]\nQuoi ?")
        src=(Path(self.m.__file__) if getattr(self.m,'__file__',None) else SOURCE).read_text()
        self.assertIn('full[:len(full)-len(prompt)]+await asyncio.to_thread(copier_pieces,prompt,',src)   # la demande seule

    def test_la_source_des_copies_est_celle_de_nc_ia(self):
        """Aucune liste de copies dans nc_engines : le faux HOME vient de la classe Demande de nc-ia, chargée par son chemin."""
        ia=self.m.module_ia()
        self.assertIsNotNone(ia);self.assertTrue(hasattr(ia,'COPIES') and hasattr(ia,'Demande'))
        src=SOURCE.read_text()
        for nom in ('refreshToken','refresh_token','access_token','accessToken'):self.assertNotIn(nom,src)
        self.assertEqual(self.m.env_unite('codex','/fh')['HOME'],'/fh')
        with patch.dict(os.environ,XDG_DATA_HOME='/x',CLAUDE_CONFIG_DIR='/x',CODEX_HOME='/x',XDG_CONFIG_HOME='/x'):
            self.assertFalse(set(self.m.env_unite('claude','/fh'))&self.m.ENV_DEPLACE)
            self.assertIn('XDG_CONFIG_HOME',self.m.env_moteur('claude'),'sans isolation (serveur), l\'ancien environnement reste')

    def test_un_jeton_expire_n_est_pas_lance_et_le_message_dit_quoi_faire(self):
        self.direct()
        self.cred['claudeAiOauth']['expiresAt']=int((time.time()-60)*1000)
        (self.home/'.claude/.credentials.json').write_text(json.dumps(self.cred))
        with patch.dict(os.environ,ANTHROPIC_API_KEY=''):
            os.environ.pop('ANTHROPIC_API_KEY')
            r=self.run_moteur()
        self.assertFalse(r['success']);self.assertRegex(r['error'],'renouveler|renew its sign-in');self.assertNotIn('isolée',r['error']);self.assertFalse(self.lance())
        self.assertEqual(self.restes_du_bac(),[])

    def test_chemins_caches_et_refus_du_dossier_qui_contient_le_home(self):
        caches=self.m.chemins_caches(self.backend/'home-runner')
        for c in (self.backend,self.backend/'home-runner',self.backend/'.env',self.backend/'gateway',self.home/'.pki',self.home/'.env.backup-1'):
            self.assertIn(str(c.resolve()),caches)
        self.assertNotIn(str(self.home),caches)
        with self.assertRaises(self.m.IsolationImpossible):self.m.chemins_caches(self.home)   # contient le HOME
        # le backend entier est facultatif : s'il contient le HOME, seuls ses .env et dossiers voisins sont cachés
        (self.backend/'perso').mkdir()
        with patch.dict(os.environ,HOME=str(self.backend/'perso')):
            caches=self.m.chemins_caches(self.backend/'home-runner')
        self.assertNotIn(str(self.backend.resolve()),caches);self.assertIn(str(self.backend/'.env'),caches)

    def test_message_clair_quand_l_isolation_refuse_une_ecriture(self):
        for brut in ("touch: cannot touch '/home/user/.local/bin/y': Read-only file system","Error: EROFS: read-only file system, open '/home/user/.zshrc'",
                     "EACCES: permission denied, mkdir '/home/user/.config/hypr/a'","bash: /home/user/.local/bin/z: Permission denied"):
            m=self.m.ecriture_refusee(brut)
            self.assertIn('isolation de JARVIS : écriture refusée dans /home/user/',m);self.assertIn('signale-le',m);self.assertIn('write denied',m)
        self.assertIsNone(self.m.ecriture_refusee('Invalid API key'))

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
class IsolationMoteurReelle(_BaseIsolation):
    """Le VRAI systemd-run --user (faux HOME, faux backend, faux XDG_RUNTIME_DIR et faux moteur sous /dev/shm, que l'unité voit ;
    rien de personnel n'est lu ni écrit : HOME, XDG_* et TMPDIR pointent tous vers le dossier du test)."""
    base_tmp=staticmethod(lambda:'/dev/shm')
    def setUp(self):
        super().setUp()
        (self.bin/'systemd-run').unlink()
        vrai=os.environ.get('NC_TEST_VRAI_RUNTIME') or ''
        os.environ['PATH']=str(self.bin)+os.pathsep+os.environ.get('NC_TEST_VRAI_PATH',os.environ['PATH'])   # le faux notify-send devant
        if not os.environ.get('DBUS_SESSION_BUS_ADDRESS'): os.environ['DBUS_SESSION_BUS_ADDRESS']='unix:path='+os.path.join(vrai,'bus')
        os.environ['TMPDIR']=str(self.root)
        # ce qui est vu de l'extérieur avant le moteur : tout l'arbre du test (le dossier run, vidé par le moteur, est suivi à part)
        self.unites=[]
        orig=self.m.isoler
        async def note(*a,**kw):
            r=await orig(*a,**kw)
            if r: self.unites.append(r.unite)
            return r
        self.m.isoler=note
        self.e=self.m.install(self.up);self.e.choose(engine='claude')

    def instantane(self):
        out={}
        for p in sorted(self.root.rglob('*')):
            if p==self.journal.with_suffix('.sortie'): continue
            try:
                st=p.lstat();out[str(p)]=(stat.S_IFMT(st.st_mode),st.st_size,p.read_text() if p.is_file() and st.st_size<10000 else '')
            except (OSError,UnicodeDecodeError):pass
        return out

    def test_la_sonde_et_une_vraie_demande_passent(self):
        r=self.run_moteur()
        self.assertTrue(r['success'],r)
        self.assertEqual(self.restes_du_bac(),[],'faux HOME, dossier de travail et sonde supprimés')

    def test_le_moteur_ne_lit_pas_le_env_ni_les_secrets_mais_a_sa_copie(self):
        lectures=''.join('cat "%s/%s" >/dev/null 2>&1 && r="$r LIT-%s"\n'%(self.home,rel,k.upper()) for k,rel in self.secrets.items())
        self.ecrire_cli('cat >/dev/null\nr=ok\ncat "%(b)s/.env" >/dev/null 2>&1 && r="$r LIT-ENV"\ncat "%(b)s/home-runner/.env" >/dev/null 2>&1 && r="$r LIT-ENV-RUNNER"\n'
            '%(l)s[ -n "$TELEGRAM_TOKEN" ] && r="$r JETON"\n[ -f "$HOME/.claude/.credentials.json" ] && r="$r COPIE"\n'
            'grep -q REFRAICHIR "$HOME/.claude/.credentials.json" && r="$r REFRESH"\ngrep -q PAS-COPIE "$HOME/.claude.json" "$HOME/.claude/settings.json" && r="$r TROP"\n'
            '[ -e "$HOME/.codex" ] && r="$r CODEX"\ncat "%(h)s/.claude/.credentials.json" >/dev/null 2>&1 && r="$r LIT-VRAI-JETON"\n'
            'printf \'{"result":"%%s"}\\n\' "$r"\n'%dict(b=self.backend,l=lectures,h=self.home))
        r=self.run_moteur()
        self.assertTrue(r['success'],r)
        self.assertEqual(r['output'].split(),['ok','COPIE'],'ni .env du backend, ni TOTP, ni connection.conf, ni assistant.conf, ni .ssh, ni .env.backup, '
                         'ni la session de l\'utilisateur, ni le vrai jeton ; seulement sa copie, sans jeton de rafraîchissement')

    def test_moteur_echo_n_ecrit_nulle_part_hors_de_son_faux_home_et_de_son_dossier_de_travail(self):
        """Le moteur « echo » essaie d'écrire PARTOUT où il peut dans le vrai HOME (rc de shell, git, .local, hypr, CLAUDE.md, un .git/hooks,
        la config des CLI…) et hors du HOME ; la liste de ce qui a réussi est vide, et le disque est identique avant et après."""
        for rel in ('.zshrc','.bashrc','.profile','.zshenv','.config/git/config','.config/hypr/hyprland.lua','.config/fastfetch/config.jsonc',
                    '.local/lib/x','.local/share/nc-jarvis/x','CLAUDE.md','repo/.git/hooks/pre-commit.sample','.codex/config.toml','.config/opencode/opencode.json'):
            f=self.home/rel;f.parent.mkdir(parents=True,exist_ok=True);f.write_text('# original\n')
        (self.root/'autre').mkdir()
        existants=['.zshrc','.bashrc','.profile','.zshenv','.config/git/config','.local/bin/nc-ia','.local/bin/nc-bac','.local/share/nc-jarvis/x','.config/hypr/hyprland.lua',
                   'CLAUDE.md','repo/.git/hooks/pre-commit.sample','.claude.json','.claude/settings.json','.codex/config.toml','.config/opencode/opencode.json',
                   '.config/fastfetch/config.jsonc','.ssh/id_ed25519','.config/nc/ia.conf','.local/lib/x']
        nouveaux=['.local/bin/nouveau','.local/lib/nouveau','.config/hypr/nouveau.lua','repo/.git/hooks/pre-commit','.claude/CLAUDE.md.nouveau','.claude/hooks/x',
                  '.config/systemd/user/x.service','.config/autostart/x.desktop','.config/fish/config.fish','.pam_environment','.cache/x','.local/share/x',
                  '.local/state/x','nouveau-fichier','.config/environment.d/x.conf','.local/share/applications/x.desktop']
        exterieur=[self.backend/'.env',self.backend/'home-runner/nouveau',self.root/'autre/x',self.rundir/'x',self.rundir/'nc-ia/x',self.rundir/'nc-ia/bac/x',
                   Path('/etc/nc-iso-x'),Path('/usr/nc-iso-x'),Path('/opt/nc-iso-x'),Path('/boot/nc-iso-x'),Path('/dev/shm/nc-iso-hors-%d'%os.getpid())]
        lignes=[]
        for rel in existants:lignes.append('echo x >> "%s/%s" 2>/dev/null && r="$r ECRIT:%s"'%(self.home,rel,rel))
        for rel in nouveaux:lignes.append('mkdir -p "$(dirname "%s/%s")" 2>/dev/null; echo x > "%s/%s" 2>/dev/null && r="$r ECRIT:%s"'%(self.home,rel,self.home,rel,rel))
        for p in exterieur:lignes.append('echo x > "%s" 2>/dev/null && r="$r ECRIT:%s"'%(p,p))
        # ce qui DOIT réussir : le faux HOME, le dossier de travail ; /tmp et /var/tmp sont ceux de l'unité (PrivateTmp), pas ceux du système
        privee=Path('/var/tmp/nc-iso-prive-%d'%os.getpid())
        lignes+=['echo x > "$HOME/.zshenv" 2>/dev/null && r="$r OK-FAUXHOME"','echo x > ./t.txt 2>/dev/null && r="$r OK-TRAVAIL"',
                 'echo x > /tmp/prive 2>/dev/null && r="$r OK-TMP-PRIVE"','echo x > "%s" 2>/dev/null && r="$r OK-VARTMP-PRIVE"'%privee]
        self.ecrire_cli('cat >/dev/null\nr=ok\n'+'\n'.join(lignes)+'\nprintf \'{"result":"%s"}\\n\' "$r"\n')
        avant=self.instantane()
        r=self.run_moteur()
        self.assertTrue(r['success'],r)
        reussies=[x for x in r['output'].split() if x.startswith('ECRIT:')]
        self.assertEqual(reussies,[],'écritures qui ont réussi hors du faux HOME et du dossier de travail')
        self.assertEqual([x for x in r['output'].split() if x.startswith('OK-')],['OK-FAUXHOME','OK-TRAVAIL','OK-TMP-PRIVE','OK-VARTMP-PRIVE'])
        apres=self.instantane()
        self.assertEqual([k for k in sorted(set(avant)|set(apres)) if avant.get(k)!=apres.get(k)],[],'rien n\'a changé sur le disque')
        for p in (privee,Path('/tmp/prive'),Path('/dev/shm/nc-iso-hors-%d'%os.getpid()),Path('/etc/nc-iso-x')):self.assertFalse(p.exists(),str(p))
        self.assertEqual(self.restes_du_bac(),[])

    def test_la_config_deplacee_est_copiee_d_ou_elle_est_et_le_moteur_n_en_recoit_pas_le_chemin(self):
        alt=self.home/'ailleurs';shutil.copytree(self.home/'.claude',alt);(alt/'.claude.json').write_text(json.dumps(dict(hasCompletedOnboarding=True)))
        shutil.rmtree(self.home/'.claude');(self.home/'.claude.json').unlink()
        os.environ['CLAUDE_CONFIG_DIR']=str(alt)
        self.ecrire_cli('cat >/dev/null\nr=ok\n[ -n "$CLAUDE_CONFIG_DIR" ] && r="$r CONFIGDIR"\n[ -f "$HOME/.claude/.credentials.json" ] && r="$r COPIE"\n'
                        'cat "%s/.credentials.json" >/dev/null 2>&1 && r="$r LIT-ORIGINAL"\nprintf \'{"result":"%%s"}\\n\' "$r"\n'%alt)
        r=self.run_moteur();self.assertTrue(r['success'],r);self.assertEqual(r['output'].split(),['ok','COPIE'])

    def test_ecriture_refusee_message_clair_au_lieu_de_l_erreur_brute(self):
        self.ecrire_cli('cat >/dev/null\necho x > "%s/.local/bin/nc-bac" || exit 1\necho x > "%s/.local/bin/nouveau-script" || { echo "Error: EROFS: read-only file system, open \'%s/.local/bin/nouveau-script\'" >&2; exit 1; }\n'%(self.home,self.home,self.home))
        r=self.run_moteur()
        self.assertFalse(r['success']);self.assertIn('isolation de JARVIS : écriture refusée dans',r['error']);self.assertIn('please report it',r['error'])
        self.assertNotIn('a échoué',r['error']);self.assertFalse((self.home/'.local/bin/nouveau-script').exists())

    def test_ecriture_refusee_ne_laisse_pas_passer_un_secret(self):
        """Le chemin recopié dans le message vient du moteur : il passe par le même filtre que la réponse."""
        self.ecrire_cli('cat >/dev/null\necho "Error: EROFS: read-only file system, open \'/$ANTHROPIC_API_KEY\'" >&2\nexit 1\n')
        r=self.run_moteur()
        self.assertFalse(r['success']);self.assertNotIn('cle-claude-0123456789',r['error'])

    def test_delai_arrete_l_unite_du_moteur(self):
        self.ecrire_cli('cat >/dev/null\nsleep 60\n')
        t=time.monotonic()
        r=asyncio.run(self.e.run('q',timeout=3,continue_session=False))
        self.assertFalse(r['success']);self.assertLess(time.monotonic()-t,15)
        time.sleep(1.5)
        self.assertEqual(len(self.unites),1)
        env={k:v for k,v in os.environ.items() if k!='XDG_RUNTIME_DIR'}   # systemctl passe alors par DBUS_SESSION_BUS_ADDRESS (comme nc-ia)
        etat=subprocess.run([shutil.which('systemctl',path=os.environ['PATH']),'--user','is-active',self.unites[0]+'.service'],capture_output=True,text=True,timeout=10,env=env).stdout.strip()
        self.assertIn(etat,('inactive','failed','unknown'),'l\'unité du moteur ne reste pas')
        self.assertEqual(self.restes_du_bac(),[])

    def test_serveur_de_l_hebergeur_sans_nc_ia_meme_unite_le_backend_est_cache(self):
        """Ni nc-ia ni nc-bac (serveur de l'hébergeur) : la même unité sans faux HOME ; le .env du backend reste illisible."""
        (self.home/'.local/bin/nc-ia').unlink();(self.home/'.local/bin/nc-bac').unlink()
        os.environ['XDG_CACHE_HOME']=str(self.home/'.cache');os.environ['DEPLOY_MODE']='server'
        self.ecrire_cli('cat >/dev/null\nr=ok\ncat "%(b)s/.env" >/dev/null 2>&1 && r="$r LIT-ENV"\ncat "%(b)s/home-runner/.env" >/dev/null 2>&1 && r="$r LIT-ENV-RUNNER"\n'
            '[ -n "$TELEGRAM_TOKEN" ] && r="$r JETON"\n[ "$HOME" = "%(h)s" ] && r="$r HOME-REEL"\nprintf \'{"result":"%%s"}\\n\' "$r"\n'%dict(b=self.backend,h=self.home))
        r=self.run_moteur()
        self.assertTrue(r['success'],r);self.assertEqual(r['output'].split(),['ok','HOME-REEL'])
        self.assertEqual(list((self.home/'.cache/nc-jarvis-travail').glob('moteur-*')),[],'dossier de travail supprimé')

    def test_opencode_2_recoit_standalone_et_les_variables_de_nc_ia_dans_l_unite(self):
        """La commande finale d'OpenCode : version lue dans l'unité (opencode --version), --standalone à partir de la 2, comme nc-ia."""
        prog=shutil.which('opencode',path=os.environ.get('NC_TEST_VRAI_PATH',os.environ['PATH']))
        if not prog:self.skipTest('opencode absent')
        self.m.executable=lambda e:prog
        self.m._VERSION_OPENCODE.clear()
        v=asyncio.run(self.m.version_opencode(prog,self.backend/'home-runner'))
        self.assertIsInstance(v,int);self.assertGreater(v,0)
        self.assertEqual(('--standalone' in self.m.commande('opencode',prog,'','',v)),v>=2)
        self.assertNotIn('--standalone',self.m.commande('opencode',prog,'','',1))
        self.assertEqual(self.restes_du_bac(),[])
        async def un(args):
            iso=await self.m.isoler('opencode',args,60,self.backend/'home-runner')
            try:
                p=await asyncio.create_subprocess_exec(*iso.cmd,env=iso.env,cwd=iso.travail,stdin=asyncio.subprocess.DEVNULL,
                    stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE,start_new_session=True)
                o,e=await asyncio.wait_for(p.communicate(),60);return p.returncode,(o+e).decode(errors='replace')
            finally:await iso.finir()
        base=self.m.commande('opencode',prog,'','',v)[:2+(v>=2)]   # [prog, 'run', '--standalone'] : le début de la commande finale
        for option in ('--version','--help'):
            code,texte=asyncio.run(un([prog,option]))
            self.assertEqual(code,0,texte[:300])
        code,texte=asyncio.run(un(base+['--help']))   # la commande finale avec --help (sans prompt : aucun modèle appelé)
        self.assertEqual(code,0,texte[:300])

    def test_version_et_aide_des_cli_installes_passent_dans_l_unite(self):
        """--version et --help de chaque CLI installé sur la machine, lancés dans l'unité (aucun modèle appelé)."""
        trouves=[(n,shutil.which(n,path=os.environ.get('NC_TEST_VRAI_PATH',os.environ['PATH']))) for n in ('claude','codex','opencode')]
        trouves=[(n,p) for n,p in trouves if p]
        if not trouves:self.skipTest('aucun CLI de moteur installé')
        async def un(engine,args):
            iso=await self.m.isoler(engine,args,60,self.backend/'home-runner')
            try:
                p=await asyncio.create_subprocess_exec(*iso.cmd,env=iso.env,cwd=iso.travail,stdin=asyncio.subprocess.DEVNULL,
                    stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE,start_new_session=True)
                sortie,erreur=await asyncio.wait_for(p.communicate(),60)
                return p.returncode,(sortie+erreur).decode(errors='replace')
            finally:await iso.finir()
        for n,chemin in trouves:
            for option in ('--version','--help'):
                with self.subTest(cli=n,option=option):
                    code,texte=asyncio.run(un(n,[chemin,option]))
                    self.assertEqual(code,0,texte[:300]);self.assertTrue(texte.strip())
        self.assertEqual(self.restes_du_bac(),[])


if __name__=='__main__':unittest.main()

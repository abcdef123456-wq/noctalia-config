"""Contrat contre le checkout upstream examiné, opt-in et sans requête modèle.

NC_JARVIS_UPSTREAM=/chemin/JARVIS-BIS python -B -m unittest tests.test_jarvis_upstream
Tous les fichiers runtime et les faux CLI sont créés dans un HOME temporaire.
"""
import asyncio
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

REPO=Path(__file__).resolve().parents[1]
UPSTREAM=Path(os.environ.get('NC_JARVIS_UPSTREAM','/nonexistent'))
try:
    import fastapi
    import httpx
except ImportError:
    fastapi=httpx=None


@unittest.skipUnless(fastapi and httpx and (UPSTREAM/'home-runner/main.py').is_file(),'Checkout upstream et dépendances API requis')
class ContratUpstream(unittest.TestCase):
    def test_original_runner_api_memory_and_mobile_gateway_use_selected_cli(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);runtime=root/'runner';runtime.mkdir();bin=root/'bin';bin.mkdir()
            for name in ('main.py','agy_bridge.py','memory.py'):shutil.copy2(UPSTREAM/'home-runner'/name,runtime/name)
            cli=bin/'codex'
            cli.write_text('#!'+sys.executable+'''
import json,sys
from pathlib import Path
prompt=sys.stdin.read()
with Path(__file__).with_suffix('.prompts').open('a') as f:f.write(json.dumps(prompt)+'\\n')
print(json.dumps(dict(type='item.completed',item=dict(type='agent_message',text='vraie route, faux modèle'))))
''');cli.chmod(0o755)
            env=dict(HOME=d,SECRET_KEY='isolated-test-secret',HOME_SERVER_URL='http://runner.test',MEMORY_FILE=str(root/'memory.json'),
                     PATH=str(bin)+os.pathsep+os.environ['PATH'])
            def load(path,name):
                spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec)
                sys.modules[name]=module;spec.loader.exec_module(module);return module
            names=('main','agy_bridge','memory','nc_runner','nc_engines','nc_management','gateway_test_contract','uvicorn')
            previous={n:sys.modules.get(n) for n in names};oldpath=list(sys.path)
            try:
                with patch.dict(os.environ,env):
                    for name in names:sys.modules.pop(name,None)
                    # Seul l'import d'uvicorn est requis ; aucun serveur n'est lancé.
                    sys.modules['uvicorn']=types.ModuleType('uvicorn')
                    sys.path[:0]=[str(runtime),str(REPO/'home/.local/share/nc-jarvis/server')]
                    main=load(runtime/'main.py','main')
                    runner=load(REPO/'home/.local/share/nc-jarvis/server/nc_runner.py','nc_runner')
                    self.assertIs(main.run_agy.__self__,runner.engines)
                    if hasattr(main,'engines'):
                        self.assertIs(runner.engines,main.engines)
                    gateway=load(UPSTREAM/'gateway/gateway.py','gateway_test_contract')
                    management=load(REPO/'home/.local/share/nc-jarvis/server/nc_management.py','nc_management')
                    async def scenario():
                        transport=httpx.ASGITransport(app=runner.app)
                        headers={'X-Secret-Key':env['SECRET_KEY']}
                        original=httpx.AsyncClient
                        async with original(transport=transport,base_url='http://runner.test') as client:
                            self.assertEqual((await client.get('/nc/engines')).status_code,401)
                            self.assertEqual((await client.post('/nc/engine',json={'engine':'codex'})).status_code,401)
                            r=await client.post('/nc/engine',json={'engine':'codex','model':'requested','effort':'high'},headers=headers)
                            self.assertEqual(r.status_code,200,r.text)
                            self.assertEqual((await client.get('/health')).json()['engine'],'codex')
                            self.assertEqual((await client.get('/nc/engines',headers=headers)).json()['session']['engine'],'codex')
                            self.assertEqual((await client.post('/memory/facts',json={'text':'préférence durable'},headers=headers)).status_code,200)
                            response=await client.post('/run',json={'prompt':'depuis le bureau'},headers=headers)
                            self.assertTrue(response.json()['success'],response.text)
                            # Les bots utilisent exactement ce forward_to_runner upstream.
                            with patch.object(httpx,'AsyncClient',side_effect=lambda **kw:original(transport=transport,**kw)) as factory:
                                async with management.runner_connections.lifespan():
                                    gateway.httpx=management.RunnerHttpx(httpx,management.runner_connections)
                                    mobile=await gateway.forward_to_runner('depuis Telegram ou Discord')
                                    remote_session=await gateway.fetch_session()
                                    factory.assert_called_once()
                            gateway.httpx=httpx
                            self.assertTrue(mobile['success'],mobile)
                            self.assertEqual(mobile['session']['engine'],'codex')
                            self.assertEqual(remote_session['engine'],'codex')
                            conversations=(await client.get('/conversations',headers=headers)).json()['conversations']
                            self.assertEqual(len(conversations),1)
                            ident=conversations[0]['id']
                            history=(await client.get('/conversation/'+ident+'/history',headers=headers)).json()['history']
                            self.assertEqual(len(history),2)
                            response=await client.post('/session',json={'effort':'xhigh'},headers=headers)
                            self.assertEqual(response.json()['session']['effort'],'xhigh')
                            self.assertEqual((await client.get('/models',headers=headers)).status_code,200)
                            # 64523e5 transmet session_key partout ; 3d1c6b6 l'ignore. Nos CLI gardent une session commune.
                            r=await client.post('/session',json={'effort':'high','session_key':'client:bureau'},headers=headers)
                            self.assertEqual(r.status_code,200,r.text)
                            r=await client.get('/session',params={'session_key':'client:bureau'},headers=headers)
                            self.assertEqual(r.status_code,200,r.text);self.assertEqual(r.json()['effort'],'high')
                            self.assertTrue((await client.get('/nc/engines',headers=headers)).json()['shared_session'])
                            r=await client.post('/run',json={'prompt':'depuis le portable','session_key':'client:portable'},headers=headers)
                            self.assertTrue(r.json()['success'],r.text)
                            r=await client.post('/conversation/resume',json={'conversation_id':ident,'session_key':'client:bureau'},headers=headers)
                            self.assertEqual(r.status_code,200,r.text)
                            self.assertEqual((await client.post('/session/reset',headers=headers)).status_code,200)
                            self.assertFalse((await client.get('/session',headers=headers)).json()['has_active_session'])
                    asyncio.run(scenario())
                    prompts=[json.loads(l) for l in cli.with_suffix('.prompts').read_text().splitlines()]
                    self.assertIn('préférence durable',prompts[0]);self.assertIn('préférence durable',prompts[1])
                    self.assertIn('depuis le bureau',prompts[1])
            finally:
                sys.path[:]=oldpath
                for name,old in previous.items():
                    if old is None:sys.modules.pop(name,None)
                    else:sys.modules[name]=old

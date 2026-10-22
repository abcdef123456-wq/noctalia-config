"""Contrats JARVIS et déploiement : données temporaires, aucun vrai bot/service."""
import asyncio
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import AsyncMock, patch

REPO=Path(__file__).resolve().parents[1]
SHARE=REPO/'home/.local/share/nc-jarvis'
BIN=REPO/'home/.local/bin'


def module(path,name):
    m=types.ModuleType(name);m.__file__=str(path)
    exec(compile(path.read_text(),str(path),'exec'),m.__dict__)
    return m


class Deploiement(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.home=Path(self.tmp.name)
        self.env_mock=patch.dict(os.environ,HOME=str(self.home))
        self.env_mock.start();self.addCleanup(self.env_mock.stop)
        self.home_mock=patch.object(Path,'home',return_value=self.home)
        self.home_mock.start();self.addCleanup(self.home_mock.stop)
        self.d=module(SHARE/'deployer.py','deploy_test')

    def test_overlay_avant_les_copies_du_depot(self):
        """Revue DEP-01 : uvicorn --app-dir passait le dossier du dépôt AVANT l'overlay ; ses copies (anciennes) de
        nc_management, nc_telegram, nc_engines… étaient chargées à la place des nôtres (gateway cassé à l'import, et les
        corrections Telegram perdues en silence). Le sys.path des unités générées, rejoué dans un vrai processus."""
        import shlex, re, tempfile, subprocess
        with tempfile.TemporaryDirectory() as d:
            backend = Path(d) / "backend"
            for dossier, nom in (("gateway", "nc_management"), ("gateway", "nc_telegram"), ("home-runner", "nc_engines")):
                (backend / dossier).mkdir(parents=True, exist_ok=True)
                (backend / dossier / (nom + ".py")).write_text("COPIE_DU_DEPOT = True\n")
            (backend / "gateway/main.py").write_text("raise SystemExit('main du dépôt atteint')\n")
            overlay = SHARE / "server"
            for unite, module in (("assistant-gateway.service", "nc_management"), ("assistant-runner.service", "nc_engines")):
                texte = self.d.units(backend, overlay)[unite]
                pythonpath = re.search(r'^Environment="PYTHONPATH=(.*)"$', texte, re.M)[1]
                argv = shlex.split(re.search(r"^ExecStart=(.*)$", texte, re.M)[1])
                app_dir = argv[argv.index("--app-dir") + 1]
                code = (f"import sys; sys.path.insert(0, {app_dir!r}); import {module}; "
                        f"print({module}.__file__)")
                r = subprocess.run([sys.executable, "-I", "-c", f"import sys; sys.path[1:1] = {pythonpath.split(':')!r}; " + code],
                                   capture_output=True, text=True, timeout=20)
                self.assertEqual(Path(r.stdout.strip()).parent, overlay, unite + " : " + r.stdout + r.stderr)
            # Garde-fou : si une copie du dépôt passe quand même devant, nc_gateway échoue franchement
            code = (f"import sys; sys.path[:0] = [{str(backend / 'gateway')!r}, {str(overlay)!r}]; "
                    f"import runpy; runpy.run_path({str(overlay / 'nc_gateway.py')!r})")
            r = subprocess.run([sys.executable, "-I", "-c", code], capture_output=True, text=True, timeout=20)
            self.assertIn("RuntimeError: nc_management ne vient pas de l'overlay", r.stderr)

    def test_user_services_bind_locally_keep_bots_and_quote_paths(self):
        units=self.d.units(Path('/tmp/my backend%test'),Path('/tmp/nc addon'))
        self.assertEqual(set(units),{'assistant-runner.service','assistant-gateway.service'})
        for value in units.values():
            self.assertIn('"127.0.0.1"',value)
            self.assertNotIn('0.0.0.0',value)
            self.assertNotIn('User=',value)
            self.assertIn('backend%%test',value)
            self.assertIn('WorkingDirectory=/tmp/my backend%%test/',value)
            self.assertIn('EnvironmentFile=/tmp/my backend%%test/',value)
            self.assertNotIn('WorkingDirectory="',value)
            self.assertNotIn('EnvironmentFile="',value)
        self.assertIn('nc_gateway:app',units['assistant-gateway.service'])
        # Revue SRV-01 : le gateway rattrape les messages Telegram en attente dès son démarrage, le runner d'abord
        self.assertIn('Wants=assistant-runner.service\nAfter=assistant-runner.service',units['assistant-gateway.service'])
        self.assertNotIn('assistant-runner.service',units['assistant-runner.service'])
        self.assertIn('home-runner',units['assistant-runner.service'])

    def test_env_merge_preserves_personal_fields_private_mode_and_symlinks(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'.env';p.write_text('DISCORD_TOKEN="keep-private"\nPERSONAL=preserve\n')
            for _ in range(2):self.d.merge_env(p,{'BRIEFING_TIME':'09:00'})
            self.assertEqual(self.d.read_env(p),dict(DISCORD_TOKEN='keep-private',PERSONAL='preserve',BRIEFING_TIME='09:00'))
            self.assertEqual(p.stat().st_mode&0o777,0o600)
            link=Path(d)/'link';link.symlink_to(p)
            with self.assertRaises(ValueError):self.d.private_write(link,'replace')
            self.assertIn('keep-private',p.read_text())

    def test_server_bundle_contains_no_tokens_and_can_show_help_without_install(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'bootstrap.pyz';self.d.bundle(p)
            import zipfile
            with zipfile.ZipFile(p) as z:
                self.assertEqual(set(z.namelist()),{'__main__.py','deployer.py','server/nc_gateway.py','server/nc_management.py','server/nc_runner.py','server/nc_engines.py','server/nc_telegram.py','server/nc_noctalia.py','server/nc_google.py','server/nc_choix.py'})
            r=subprocess.run([sys.executable,str(p),'--help'],capture_output=True,text=True,timeout=5)
            self.assertEqual(r.returncode,0,r.stderr)
            self.assertIn('--mode',r.stdout)

    def test_preparing_does_not_start_or_download_without_interactive_choice(self):
        with tempfile.TemporaryDirectory() as d, patch.object(self.d.sys.stdin,'isatty',return_value=True), patch.object(self.d,'ask',return_value=False), patch.object(self.d,'run') as run:
            dest=Path(d)/'not-created';self.d.deploy('server',str(dest))
            self.assertFalse(dest.exists());run.assert_not_called()
        for host in ('-oProxyCommand=bad','host;touch bad','user@host/other','user@$(bad)'):
            with self.assertRaises(ValueError):self.d.remote(host)

    def test_ssh_connection_import_is_private_and_keeps_client_identity(self):
        with tempfile.TemporaryDirectory() as d, patch.dict(os.environ,HOME=d), patch.object(Path,'home',return_value=Path(d)):
            path=Path(d)/'.config/nc/assistant.conf'
            self.d.merge_env(path,dict(URL='https://old.example',SECRET_KEY='old-test-key',USER_ID='my-user',TIMEOUT='120',PERSONAL='keep'))
            calls=[]
            def execute(args,**kwargs):
                args=list(map(str,args));calls.append(args)
                if args[0]=='scp' and args[1].endswith(':.local/state/nc-jarvis/connection.conf'):
                    self.d.merge_env(Path(args[2]),dict(SECRET_KEY='new-test-key'))
                return subprocess.CompletedProcess(args,0)
            output=io.StringIO()
            with patch.object(self.d,'run',side_effect=execute),patch.object(self.d,'ask',return_value=True),patch('builtins.input',return_value='https://new.example'),contextlib.redirect_stdout(output):
                self.d.remote('user@server')
            saved=self.d.read_env(path)
            self.assertEqual(saved['SECRET_KEY'],'new-test-key');self.assertEqual(saved['USER_ID'],'my-user')
            self.assertEqual(saved['PERSONAL'],'keep');self.assertEqual(saved['URL'],'https://new.example')
            self.assertEqual(path.stat().st_mode&0o777,0o600)
            backups=list(path.parent.glob('assistant.conf.backup-*'))
            self.assertEqual(len(backups),1);self.assertEqual(backups[0].stat().st_mode&0o777,0o600)
            self.assertNotIn('new-test-key',output.getvalue()+repr(calls))

    def test_existing_backend_cannot_be_retargeted_to_an_empty_data_folder(self):
        with tempfile.TemporaryDirectory() as d,patch.dict(os.environ,HOME=d),patch.object(Path,'home',return_value=Path(d)),patch.object(self.d.sys.stdin,'isatty',return_value=True),patch.object(self.d,'run') as run:
            unit=Path(d)/'.config/systemd/user/assistant-gateway.service';unit.parent.mkdir(parents=True)
            original='[Service]\nWorkingDirectory=%h/existing-jarvis/render-gateway\n'
            unit.write_text(original)
            destination=Path(d)/'fresh-copy'
            with self.assertRaisesRegex(ValueError,'Instance existante'):
                self.d.deploy('server',str(destination))
            self.assertFalse(destination.exists());self.assertEqual(unit.read_text(),original);run.assert_not_called()


try:
    import fastapi
    import httpx
except ImportError:
    fastapi=httpx=None


@unittest.skipUnless(fastapi and httpx,'FastAPI/httpx requis dans le venv de test JARVIS')
class Management(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        for folder in ('home-runner','render-gateway'):(self.root/folder).mkdir()
        self.up=types.ModuleType('main');self.up.__file__=str(self.root/'render-gateway/main.py')
        self.up.SECRET_KEY='private-test-key';self.up.HOME_SERVER_URL='http://private-runner:8080'
        self.started=[]
        @contextlib.asynccontextmanager
        async def lifespan(app):
            self.started.append('original-bots-lifespan');yield
        self.up.app=fastapi.FastAPI(lifespan=lifespan)
        @self.up.app.get('/original-bots-route')
        async def original():return {'preserved':True}
        def guard(request:fastapi.Request):
            if request.headers.get('X-Secret-Key')!=self.up.SECRET_KEY:raise fastapi.HTTPException(401)
        self.up.require_secret=guard
        tool=types.SimpleNamespace(id='shopping',name='Courses',description='Liste',is_enabled=True,requires_local_hardware=False,
                                   params=[types.SimpleNamespace(name='SHOPPING_SECRET',label='Jeton',secret=True,default='')])
        registry=types.SimpleNamespace(list_tools=lambda:[tool])
        base=types.ModuleType('core.tools.base');base.ToolRegistry=registry
        telegram=types.ModuleType('nc_telegram');telegram.installer=lambda upstream:None   # file d'attente Telegram : hors sujet ici
        gateway=types.ModuleType('gateway');gateway.httpx=httpx
        self.m=module(SHARE/'server/nc_management.py','nc_management')
        # Ne restaurer que nos modules : retirer des imports paresseux d'anyio/httpcore
        # casserait l'identité de SocketAttribute lors des tests HTTP suivants.
        replacements={'main':self.up,'gateway':gateway,'nc_management':self.m,'core.tools.base':base,
                      'nc_choix':module(SHARE/'server/nc_choix.py','nc_choix'),'nc_telegram':telegram}
        previous={key:sys.modules.get(key) for key in replacements}
        sys.modules.update(replacements)
        def restore():
            for key,value in previous.items():
                if value is None:sys.modules.pop(key,None)
                else:sys.modules[key]=value
        self.addCleanup(restore)
        self.api=module(SHARE/'server/nc_gateway.py','nc_gateway')
        from fastapi.testclient import TestClient
        self.client=TestClient(self.api.app);self.client.__enter__();self.addCleanup(self.client.__exit__,None,None,None)
        self.headers={'X-Secret-Key':self.up.SECRET_KEY}

    def call(self,op,params=None,confirmed=False):
        return self.client.post('/api/nc/manage',headers=self.headers,json=dict(op=op,params=params or {},confirmed=confirmed))

    def test_auth_preserves_original_routes_and_bots_lifespan(self):
        self.assertIs(self.api.app,self.up.app)
        self.assertEqual(self.started,['original-bots-lifespan'])
        self.assertTrue(self.client.get('/original-bots-route').json()['preserved'])
        self.assertEqual(self.client.post('/api/nc/manage',json={'op':'capabilities'}).status_code,401)
        self.assertEqual(self.call('arbitrary-shell',{'command':'anything'},True).status_code,400)
        with patch.dict(os.environ,SHOPPING_SECRET='never-leak'):
            data=self.call('capabilities').json()
        self.assertEqual(data['protocol'],1)
        self.assertTrue(data['shared_session'])
        self.assertNotIn('never-leak',json.dumps(data))
        self.assertTrue(next(f for f in data['fields'] if f['key']=='SHOPPING_SECRET')['configured'])

    def test_mutations_require_confirmation_and_paths_are_restricted(self):
        with patch.object(self.m,'runner',new_callable=AsyncMock) as runner:
            self.assertIn('error',self.call('session.reset').json());runner.assert_not_called()
            runner.return_value={'success':True}
            self.assertTrue(self.call('session.reset',{},True).json()['success'])
            runner.assert_awaited_with('POST','/session/reset')
            self.assertEqual(self.call('conversation.delete',{'id':'../../run'},True).status_code,400)
        self.assertEqual(self.call('service.restart',{'unit':'sshd.service'},True).status_code,400)

    def test_session_key_du_pc_suit_les_reglages_de_session(self):
        # JARVIS-BIS 64523e5 : avec AGY, une session par PC ; modèle, reset, reprise et lecture visent celle du PC
        def appel(op,params=None,confirmed=False,**extra):
            return self.client.post('/api/nc/manage',headers=self.headers,json=dict(op=op,params=params or {},confirmed=confirmed,**extra))
        with patch.object(self.m,'runner',new_callable=AsyncMock,return_value={'success':True}) as runner:
            k='desktop:pc-bureau'
            appel('session.reset',{},True,session_key=k);runner.assert_awaited_with('POST','/session/reset?session_key=desktop%3Apc-bureau')
            appel('session.update',{'effort':'high'},True,session_key=k)
            runner.assert_awaited_with('POST','/session',{'effort':'high','session_key':k})
            appel('session.update',{'engine':'codex'},True,session_key=k)
            runner.assert_awaited_with('POST','/nc/engine',{'engine':'codex','session_key':k})
            appel('conversation.resume',{'id':'abc'},True,session_key=k)
            runner.assert_awaited_with('POST','/conversation/resume',{'conversation_id':'abc','session_key':k})
            appel('quick-settings',session_key=k);runner.assert_awaited_with('GET','/nc/engines?session_key=desktop%3Apc-bureau')
            appel('session',session_key=k);runner.assert_awaited_with('GET','/session?session_key=desktop%3Apc-bureau')
            # Ancien client, sans clé : la session « default », comme avant
            appel('session.reset',{},True);runner.assert_awaited_with('POST','/session/reset')
            appel('session.update',{'effort':'low'},True);runner.assert_awaited_with('POST','/session',{'effort':'low'})
            calls=runner.await_count
            self.assertEqual(appel('session',session_key='x&y=1').status_code,400)
            self.assertEqual(appel('session',session_key=5).status_code,400)
            self.assertEqual(runner.await_count,calls)

    def test_config_updates_preserve_secrets_and_component_values(self):
        paths=[self.root/'.env',self.root/'render-gateway/.env',self.root/'home-runner/.env']
        for i,p in enumerate(paths):p.write_text('DISCORD_TOKEN="keep-secret"\nPERSONAL='+str(i)+'\n')
        data=self.call('config.update',{'values':{'DISCORD_TOKEN':'','BRIEFING_TIME':'09:00'}},True)
        self.assertEqual(data.status_code,200,data.text)
        self.assertTrue(data.json()['restart_required'])
        for i,p in enumerate(paths):
            self.assertIn('keep-secret',p.read_text());self.assertIn('PERSONAL='+str(i),p.read_text())
            self.assertIn('09:00',p.read_text());self.assertEqual(p.stat().st_mode&0o777,0o600)
        self.assertEqual(self.call('config.update',{'values':{'SECRET_KEY':'replace'}},True).status_code,400)
        self.assertEqual(self.call('config.update',{'values':{'BRIEFING_TIME':'value\nINJECT=1'}},True).status_code,400)

    def test_config_failure_rolls_back_all_components(self):
        paths=[self.root/'.env',self.root/'render-gateway/.env',self.root/'home-runner/.env']
        for p in paths:p.write_text('PERSONAL=preserved\n')
        original=self.m.atomic;calls=[]
        def fail(path,data):
            calls.append(path)
            if len(calls)==2:raise OSError('simulated failure')
            original(path,data)
        with patch.object(self.m,'atomic',side_effect=fail):
            with self.assertRaises(OSError):self.m.update_config({'BRIEFING_TIME':'09:00'})
        self.assertTrue(all(p.read_text()=='PERSONAL=preserved\n' for p in paths))

    def test_token_removal_is_explicit_and_keeps_other_bot_settings(self):
        paths=[self.root/'.env',self.root/'render-gateway/.env',self.root/'home-runner/.env']
        for p in paths:p.write_text('DISCORD_TOKEN="keep-discord"\nTELEGRAM_TOKEN="remove-telegram"\n')
        self.assertIn('error',self.call('config.clear',{'keys':['TELEGRAM_TOKEN']}).json())
        self.assertTrue(all('remove-telegram' in p.read_text() for p in paths))
        result=self.call('config.clear',{'keys':['TELEGRAM_TOKEN']},True)
        self.assertEqual(result.status_code,200,result.text)
        self.assertTrue(result.json()['restart_required'])
        self.assertTrue(all('keep-discord' in p.read_text() and 'remove-telegram' not in p.read_text() for p in paths))

    def test_proxy_authenticates_only_the_private_runner(self):
        seen=[]
        def handler(request):
            seen.append(request)
            return httpx.Response(200,json={'models':['one-model']})
        transport_client=httpx.AsyncClient(transport=httpx.MockTransport(handler))
        self.addCleanup(lambda:asyncio.run(transport_client.aclose()))
        with patch.object(self.m.runner_connections,'client',transport_client):
            result=asyncio.run(self.m.runner('GET','/models'))
        self.assertEqual(result,dict(models=['one-model']))
        self.assertEqual(str(seen[0].url),'http://private-runner:8080/models')
        self.assertEqual(seen[0].headers['X-Secret-Key'],self.up.SECRET_KEY)
        self.assertFalse(seen[0].url.params)


class ClientJarvis(unittest.TestCase):
    def setUp(self):self.m=module(BIN/'nc-jarvis','jarvis_client')

    def test_unconfirmed_write_does_not_contact_api(self):
        m=types.SimpleNamespace(configuration=lambda:{'SECRET_KEY':'key'},api=unittest.mock.Mock())
        with patch.object(self.m,'client',return_value=m):
            with self.assertRaises(ValueError):self.m.request(dict(op='session.reset'))
        m.api.assert_not_called()

    def test_clean_removes_credentials_and_terminal_controls_recursively(self):
        data=self.m.clean(dict(text='\x1b[31mprivate-key\x1b[0m',secret_key='private-key',nested=[{'message':'private-key'}]),'private-key')
        self.assertNotIn('private-key',json.dumps(data));self.assertNotIn('\x1b',data['text'])
        self.assertNotIn('secret_key',data)

    def test_custom_catalogue_extends_existing_tools(self):
        with tempfile.TemporaryDirectory() as d, patch.dict(os.environ,HOME=d):
            p=Path(d)/'.config/nc/jarvis-actions.json';p.parent.mkdir(parents=True);p.write_text('{"extra":[{"id":"hello","label":"Bonjour","fields":[]}]}')
            result=self.m.catalogue()
            self.assertIn('shopping',result);self.assertIn('extra',result)


try:
    from . import test_assistant as assistant_fixtures
except ImportError:  # unittest discover -s tests importe les modules sans paquet.
    import test_assistant as assistant_fixtures


class TransportJarvis(unittest.TestCase):
    arreter=assistant_fixtures.Assistant.arreter
    cli=assistant_fixtures.Assistant.cli
    etat=assistant_fixtures.Assistant.etat

    def setUp(self):
        assistant_fixtures.Assistant.setUp(self)
        shutil.copy2(BIN/'nc-jarvis',self.bin/'nc-jarvis')
        shutil.copytree(SHARE,self.root/'.local/share/nc-jarvis')

    def req(self,op,params=None,confirmed=False):
        return self.cli('requete',nom='nc-jarvis',input=json.dumps(dict(op=op,params=params or {},confirmed=confirmed))+'\n')

    def test_client_routes_admin_through_gateway_with_header_and_stdin(self):
        self.server.reponse=(200,b'{"models": [{"id":"model-test","name":"Test"}]}')
        r=self.req('models')
        self.assertEqual(r.returncode,0,r.stderr+r.stdout)
        self.assertTrue(json.loads(r.stdout)['ok'])
        path,method,key,body=self.server.recus[-1]
        self.assertEqual(path,'/gateway/api/nc/manage');self.assertEqual(method,'POST')
        # La clé de session de ce PC accompagne la gestion (une session AGY par PC depuis JARVIS-BIS 64523e5)
        self.assertRegex(body.pop('session_key'),r'^desktop:[\w.-]+$')
        self.assertEqual(key,self.c['SECRET_KEY']);self.assertEqual(body,dict(op='models',params={},confirmed=False))
        self.assertNotIn(key,r.stdout+r.stderr)

    def test_action_tracks_activity_and_preserves_mobile_platforms(self):
        self.server.reponse=(200,json.dumps(dict(success=True,message='Articles ajoutés')).encode())
        r=self.req('action',dict(tool='shopping',action='add',params=dict(text='café')),True)
        self.assertEqual(r.returncode,0,r.stderr+r.stdout)
        self.assertEqual(self.server.recus[-1][0],'/gateway/api/action')
        self.assertEqual(self.server.recus[-1][3],dict(tool='shopping',action='add',params=dict(text='café'),platform='desktop'))
        self.assertEqual(next(iter(self.etat()['sessions'].values()))['etat'],'fini')
        completed=dict(self.etat()['sessions'])
        self.server.reponse=(401,b'private server error')
        r=self.req('action',dict(tool='shopping',action='add'),True)
        self.assertEqual(r.returncode,1)
        self.assertFalse(json.loads(r.stdout)['ok']);self.assertEqual(self.etat()['sessions'],completed)
        self.assertNotIn('private server error',r.stdout+r.stderr)

    def test_unconfirmed_write_and_unsupported_desktop_reminder_are_not_sent(self):
        r=self.req('session.reset')
        self.assertEqual(r.returncode,1);self.assertFalse(self.server.recus)
        r=self.req('reminder.create',dict(platform='desktop',chat_id='me',message='test',delay='15m'),True)
        self.assertEqual(r.returncode,1);self.assertFalse(self.server.recus)

    def test_management_requests_give_up_quickly_but_long_operations_keep_the_timeout(self):
        # Un gateway muet ne fige pas le cockpit ni l'île : les opérations de gestion sont bornées (ici 1 s) alors que
        # le briefing garde le délai configuré (2 s dans ce harnais)
        import threading,time
        self.env['NC_JARVIS_GESTION_DELAI']='1'
        self.server.reponse=(200,b'{"models": []}')
        self.server.bloquer=True
        self.server.entree,self.server.sortie=threading.Event(),threading.Event()
        threading.Timer(1.5,self.server.sortie.set).start()
        debut=time.monotonic();r=self.req('models');duree=time.monotonic()-debut
        self.assertEqual(r.returncode,1,r.stdout+r.stderr);self.assertFalse(json.loads(r.stdout)['ok'])
        self.assertLess(duree,1.4,'la gestion devait abandonner après 1 s')
        self.server.sortie.wait(3)
        self.server.entree,self.server.sortie=threading.Event(),threading.Event()
        threading.Timer(1.2,self.server.sortie.set).start()
        self.server.reponse=(200,b'{"briefing": "ok"}')
        r=self.req('briefing',confirmed=True)
        self.assertEqual(r.returncode,0,r.stdout+r.stderr);self.assertTrue(json.loads(r.stdout)['ok'],'le briefing garde ses 2 s')

    def test_overview_loads_status_and_capabilities_and_keeps_secret_hidden(self):

        self.server.reponse=(200,b'{"online":true,"protocol":1,"modules":[],"fields":[]}')
        r=self.req('overview')
        self.assertEqual(r.returncode,0,r.stderr+r.stdout)
        self.assertEqual([row[0] for row in self.server.recus],['/gateway/api/status','/gateway/api/nc/manage'])
        self.assertEqual(json.loads(r.stdout)['data']['management']['protocol'],1)
        self.assertNotIn(self.c['SECRET_KEY'],r.stdout+r.stderr)


class CommandeChat(unittest.TestCase):
    """nc-jarvis chat : la petite fenêtre par l'IPC de l'île, sinon le chat dans un terminal."""
    def lancer(self, qs_ok):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);bin=root/'bin';bin.mkdir()
            shutil.copy2(BIN/'nc-jarvis',bin/'nc-jarvis')
            (bin/'nc-assistant').write_text('import json,os,sys\nfrom pathlib import Path\nPath(os.environ["HOME"],"assistant").write_text(json.dumps(sys.argv[1:]))\n')
            (bin/'qs').write_text('#!/bin/sh\necho "$*" > "$HOME/qs"\nexit %d\n'%(0 if qs_ok else 1));(bin/'qs').chmod(0o755)
            env=dict(os.environ,HOME=d,PATH=str(bin)+os.pathsep+os.environ['PATH'])
            r=subprocess.run([sys.executable,str(bin/'nc-jarvis'),'chat'],env=env,capture_output=True,text=True,timeout=20)
            qs=(root/'qs').read_text().strip() if (root/'qs').exists() else None
            assistant=json.loads((root/'assistant').read_text()) if (root/'assistant').exists() else None
            return r,qs,assistant

    def test_chat_opens_the_island_window_or_falls_back_to_the_terminal(self):
        r,qs,assistant=self.lancer(True)
        self.assertEqual(r.returncode,0,r.stderr)
        self.assertEqual(qs,'-c nc-ile ipc call ile jarvisChat')
        self.assertIsNone(assistant,'avec Quickshell, pas de terminal')
        r,qs,assistant=self.lancer(False)
        self.assertEqual(r.returncode,0,r.stderr)
        self.assertEqual(assistant,['ouvrir'],'sans Quickshell : le chat terminal')
        self.assertIn('indisponible',r.stderr)


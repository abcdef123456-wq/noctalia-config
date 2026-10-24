"""Pool HTTP JARVIS : vrais échanges locaux, délais concurrents et cycle de vie."""
import asyncio
import contextlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading
import types
import unittest
import sys
from unittest.mock import patch

try:
    import httpx
except ImportError:
    httpx=None

SOURCE=Path(__file__).resolve().parents[1]/'home/.local/share/nc-jarvis/server/nc_management.py'


@unittest.skipUnless(httpx,'httpx requis dans le venv de test')
class ConnexionsRunner(unittest.TestCase):
    def setUp(self):
        self.m=types.ModuleType('http_pool_test');self.m.__file__=str(SOURCE)
        exec(compile(SOURCE.read_text(),str(SOURCE),'exec'),self.m.__dict__)

    def test_all_engines_reuse_one_real_connection_without_caching_answers(self):
        seen=[];connections=[]
        class Handler(BaseHTTPRequestHandler):
            protocol_version='HTTP/1.1'
            def setup(self):
                super().setup();connections.append(self.client_address)
            def log_message(self,*args):pass
            def do_POST(self):
                data=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                seen.append((data,self.headers.get('X-Secret-Key'),self.headers.get('Cookie')))
                body=json.dumps({'success':True,'output':data['engine']}).encode()
                self.send_response(200);self.send_header('Content-Length',str(len(body)))
                self.send_header('Set-Cookie','unwanted-session='+data['engine']+'; Path=/');self.end_headers()
                self.wfile.write(body);self.wfile.flush()
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler);server.daemon_threads=True
        thread=threading.Thread(target=server.serve_forever,kwargs={'poll_interval':.01},daemon=True);thread.start()
        try:
            pool=self.m.RunnerConnections()
            async def scenario():
                async with pool.lifespan():
                    for engine in ('agy','codex','claude','opencode'):
                        async with pool.lease(timeout=2) as client:
                            response=await client.post(f'http://127.0.0.1:{server.server_port}/run',
                                json={'engine':engine},headers={'X-Secret-Key':'test-'+engine})
                            self.assertEqual(response.json()['output'],engine)
                    client=pool.client
                    self.assertFalse(client.is_closed)
                self.assertIsNone(pool.client);self.assertTrue(client.is_closed)
            with patch.dict('os.environ',NO_PROXY='*',no_proxy='*'):
                asyncio.run(scenario())
            self.assertEqual(len(seen),4);self.assertEqual(len(connections),1)
            self.assertEqual([key for _,key,_ in seen],['test-'+x for x in ('agy','codex','claude','opencode')])
            self.assertTrue(all(cookie is None for _,_,cookie in seen))
        finally:
            server.shutdown();server.server_close();thread.join(2)

    def test_concurrent_timeouts_and_cancellation_do_not_close_or_modify_the_pool(self):
        requests=[];created=[];entered=asyncio.Event()
        async def handle(request):
            requests.append(request)
            if request.url.path=='/pending':
                entered.set();await asyncio.Event().wait()
            await asyncio.sleep(0)
            return httpx.Response(200,json={'ok':True})
        original=httpx.AsyncClient
        def factory(**kwargs):
            client=original(transport=httpx.MockTransport(handle),**kwargs);created.append(client);return client
        pool=self.m.RunnerConnections()
        async def scenario():
            async with pool.lifespan():
                async def get(path,lease_timeout,**kwargs):
                    async with pool.lease(timeout=lease_timeout) as client:return await client.get('http://runner.test'+path,**kwargs)
                await asyncio.gather(get('/short',1),get('/long',195),get('/explicit',2,timeout=7))
                pending=asyncio.create_task(get('/pending',10))
                await asyncio.wait_for(entered.wait(),1)
                pending.cancel()
                with self.assertRaises(asyncio.CancelledError):await pending
                self.assertTrue((await get('/after',3)).json()['ok'])
                self.assertEqual(len(created),1);self.assertFalse(pool.client.is_closed)
            self.assertTrue(created[0].is_closed)
        with patch.object(httpx,'AsyncClient',side_effect=factory):asyncio.run(scenario())
        timeouts={r.url.path:r.extensions['timeout']['read'] for r in requests}
        self.assertEqual(timeouts,{'/short':1,'/long':195,'/explicit':7,'/pending':10,'/after':3})
        self.assertEqual(len(requests),5)

    def test_outside_lifespan_and_custom_options_use_a_dedicated_client(self):
        pool=self.m.RunnerConnections();created=[];timeouts=[]
        def handle(request):
            timeouts.append(request.extensions['timeout']['read']);return httpx.Response(200,json={'ok':True})
        original=httpx.AsyncClient
        def factory(**kwargs):
            client=original(transport=httpx.MockTransport(handle),**kwargs);created.append(client);return client
        async def scenario():
            # Hors du lifespan, un client d'une seule requête, fermé aussitôt ; la sortie du bloc ne ferme rien
            async with pool.lease(timeout=1) as standalone:
                self.assertTrue((await standalone.get('http://runner.test/a')).json()['ok'])
                self.assertTrue((await standalone.get('http://runner.test/b',timeout=4)).json()['ok'])
                self.assertFalse(standalone.is_closed)
            self.assertFalse(standalone.is_closed)
            self.assertEqual(len(created),2);self.assertTrue(all(c.is_closed for c in created))
            self.assertEqual(timeouts,[1,4])
            async with pool.lifespan():
                shared=pool.client
                async with pool.lease(headers={'X-Custom':'value'}) as dedicated:
                    self.assertIsNot(shared,dedicated);self.assertEqual(dedicated.headers['X-Custom'],'value')
                self.assertTrue(dedicated.is_closed);self.assertFalse(shared.is_closed)
        with patch.object(httpx,'AsyncClient',side_effect=factory):asyncio.run(scenario())

    def test_origin_token_header_reaches_the_runner_in_the_pool_and_outside_it(self):
        """be109d5 : forward_to_runner passe headers={X-Secret-Key, X-Jarvis-Origin-Token} ; les deux doivent arriver,
        dans le pool comme hors du pool (client d'une seule requête)."""
        vus=[]
        class Handler(BaseHTTPRequestHandler):
            protocol_version='HTTP/1.1'
            def log_message(self,*args):pass
            def do_POST(self):
                self.rfile.read(int(self.headers['Content-Length']))
                vus.append((self.headers.get('X-Secret-Key'),self.headers.get('X-Jarvis-Origin-Token')))
                body=b'{}';self.send_response(200);self.send_header('Content-Length','2');self.end_headers();self.wfile.write(body)
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler);server.daemon_threads=True
        threading.Thread(target=server.serve_forever,kwargs={'poll_interval':.01},daemon=True).start()
        try:
            pool=self.m.RunnerConnections();url=f'http://127.0.0.1:{server.server_port}/run'
            entetes=lambda n:{'X-Secret-Key':'s','X-Jarvis-Origin-Token':'jeton'+n}
            async def scenario():
                await pool.lease(timeout=2).post(url,json={},headers=entetes('0'))   # hors pool (pas ouvert)
                async with pool.lifespan():
                    await pool.lease(timeout=2).post(url,json={},headers=entetes('1'))
            with patch.dict('os.environ',NO_PROXY='*',no_proxy='*'):
                asyncio.run(scenario())
            self.assertEqual(vus,[('s','jeton0'),('s','jeton1')])
        finally:
            server.shutdown();server.server_close()

    def shared_client_like_f522291(self,pool,made):
        """gateway._get_http_client et close_http_client de JARVIS-BIS f522291, sur notre façade httpx."""
        g=types.SimpleNamespace(httpx=self.m.RunnerHttpx(httpx,pool),client=None,loop=None)
        def get_client():
            loop=asyncio.get_running_loop()
            if g.client is None or g.client.is_closed or g.loop is not loop:
                g.client=g.httpx.AsyncClient(timeout=10.0,limits=g.httpx.Limits(max_keepalive_connections=10,
                                             max_connections=25,keepalive_expiry=60.0))
                g.loop=loop;made.append(g.client)
            return g.client
        async def close():
            if g.client is not None and not g.client.is_closed:await g.client.aclose()
            g.client=g.loop=None
        return get_client,close

    def test_shared_client_kept_directly_like_f522291_goes_through_the_pool(self):
        """f522291 garde un seul client et appelle .post, .is_closed, .aclose en direct : tout passe par le pool,
        le même objet revient tant qu'il est ouvert, les connexions restent bornées et aucun cookie n'est gardé."""
        seen=[];connections=[];active=[0,0];lock=threading.Lock()
        class Handler(BaseHTTPRequestHandler):
            protocol_version='HTTP/1.1'
            def setup(self):
                super().setup();connections.append(self.client_address)
                with lock:active[0]+=1;active[1]=max(active)
            def finish(self):
                super().finish()
                with lock:active[0]-=1
            def log_message(self,*args):pass
            def do_POST(self):
                self.rfile.read(int(self.headers['Content-Length']))
                if self.path=='/lent':threading.Event().wait(.05)
                seen.append(self.headers.get('Cookie'))
                body=b'{"ok": true}'
                self.send_response(200);self.send_header('Content-Length',str(len(body)))
                self.send_header('Set-Cookie','unwanted=1; Path=/');self.end_headers()
                self.wfile.write(body);self.wfile.flush()
        class Server(ThreadingHTTPServer):request_queue_size=64
        server=Server(('127.0.0.1',0),Handler);server.daemon_threads=True
        thread=threading.Thread(target=server.serve_forever,kwargs={'poll_interval':.01},daemon=True);thread.start()
        url=f'http://127.0.0.1:{server.server_port}'
        pool=self.m.RunnerConnections();made=[];pools=[]
        get_client,close=self.shared_client_like_f522291(pool,made)
        async def scenario():
            async with pool.lifespan():
                pools.append(pool.client)
                first=get_client()
                for _ in range(6):
                    self.assertIs(get_client(),first);self.assertFalse(first.is_closed)
                    self.assertTrue((await get_client().post(url+'/run',json={})).json()['ok'])
                self.assertEqual(len(connections),1)
                # Un « async with » autour du client partagé ne ferme ni le pool ni ce client
                async with get_client() as client:
                    self.assertTrue((await client.post(url+'/run',json={})).json()['ok'])
                self.assertFalse(first.is_closed);self.assertFalse(pool.client.is_closed);self.assertIs(get_client(),first)
                with self.assertRaises(AttributeError):get_client().headers
                # close_http_client ferme l'emprunt, jamais le pool ; un nouvel emprunt reprend le même pool
                await close()
                self.assertTrue(first.is_closed);self.assertFalse(pool.client.is_closed)
                with self.assertRaises(RuntimeError):await first.post(url+'/run',json={})
                second=get_client();self.assertIsNot(second,first)
                self.assertTrue((await second.post(url+'/run',json={})).json()['ok'])
                self.assertEqual(len(connections),1)
            self.assertTrue(pools[0].is_closed);self.assertIsNone(pool.client)
            # Pool rouvert (rechargement du gateway) : le même emprunt suit le nouveau pool, une seule connexion de plus
            async with pool.lifespan():
                pools.append(pool.client)
                self.assertIs(get_client(),second)
                self.assertTrue((await get_client().post(url+'/run',json={})).json()['ok'])
                self.assertEqual(len(connections),2)
                # Rafale : jamais plus de connexions ouvertes à la fois que le pool n'en permet (16). Au-delà de 8 en
                # attente, httpx en ferme et en rouvre : le total grimpe, pas le nombre simultané.
                answers=await asyncio.gather(*(get_client().post(url+'/lent',json={}) for _ in range(40)))
                self.assertTrue(all(a.json()['ok'] for a in answers))
                self.assertLessEqual(active[1],16);self.assertGreater(active[1],1)
            self.assertTrue(pools[1].is_closed)
        try:
            with patch.dict('os.environ',NO_PROXY='*',no_proxy='*'):asyncio.run(scenario())
        finally:
            server.shutdown();server.server_close();thread.join(2)
        self.assertEqual(len(made),2)
        self.assertEqual(len(seen),49);self.assertTrue(all(cookie is None for cookie in seen))

    def test_shared_client_keeps_each_call_timeout_and_never_leaks_outside_the_pool(self):
        requests=[];created=[]
        def handle(request):
            requests.append((request.url.path,request.extensions['timeout']['read']));return httpx.Response(200,json={})
        original=httpx.AsyncClient
        def factory(**kwargs):
            client=original(transport=httpx.MockTransport(handle),**kwargs);created.append(client);return client
        pool=self.m.RunnerConnections();made=[]
        get_client,close=self.shared_client_like_f522291(pool,made)
        async def scenario():
            # Avant le lifespan : un client par requête, fermé aussitôt
            await get_client().get('http://runner.test/avant')
            self.assertEqual(len(created),1);self.assertTrue(created[0].is_closed)
            async with pool.lifespan():
                await asyncio.gather(get_client().get('http://runner.test/defaut'),
                                     get_client().post('http://runner.test/explicite',timeout=615.0),
                                     get_client().request('DELETE','http://runner.test/supprime',timeout=5.0))
                self.assertEqual(len(created),2)
            await close()
            self.assertTrue(all(c.is_closed for c in created));self.assertEqual(len(made),1)
        with patch.object(httpx,'AsyncClient',side_effect=factory):asyncio.run(scenario())
        self.assertEqual(sorted(requests),sorted([('/avant',10.0),('/defaut',10.0),('/explicite',615.0),('/supprime',5.0)]))

    def test_another_event_loop_never_takes_the_pool(self):
        """Le polling Telegram tourne dans un fil avec sa propre boucle : pendant le lifespan, ses requêtes (emprunt
        en direct comme f522291, « async with » comme aae5b9b, et runner() pour /nc) réussissent sans toucher au pool
        de la boucle principale, qui continue de servir. Avant : « … is bound to a different event loop »."""
        connections=[]
        class Handler(BaseHTTPRequestHandler):
            protocol_version='HTTP/1.1'
            def setup(self):
                super().setup();connections.append(threading.current_thread().name)
            def log_message(self,*args):pass
            def do_GET(self):
                body=b'{"ok": true}'
                self.send_response(200);self.send_header('Content-Length',str(len(body)));self.end_headers()
                self.wfile.write(body);self.wfile.flush()
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler);server.daemon_threads=True
        thread=threading.Thread(target=server.serve_forever,kwargs={'poll_interval':.01},daemon=True);thread.start()
        url=f'http://127.0.0.1:{server.server_port}'
        pool=self.m.RunnerConnections();made=[]
        get_client,close=self.shared_client_like_f522291(pool,made)
        main_module=types.ModuleType('main');main_module.HOME_SERVER_URL=url;main_module.SECRET_KEY='test'
        results={}
        def other_thread():
            async def scenario():
                codes=[]
                for _ in range(3):codes.append((await asyncio.wait_for(get_client().get(url+'/direct'),5)).status_code)
                async with pool.lease(timeout=5) as client:codes.append((await client.get(url+'/bloc')).status_code)
                with patch.object(self.m,'runner_connections',pool),patch.dict(sys.modules,{'main':main_module}):
                    codes.append((await self.m.runner('GET','/nc'))['ok'])
                await close()
                return codes
            try:results['codes']=asyncio.run(scenario())
            except Exception as e:results['error']=f'{type(e).__name__}: {e}'
        async def main():
            async with pool.lifespan():
                shared=pool.client
                async with pool.lease(timeout=5) as client:self.assertEqual((await client.get(url+'/avant')).status_code,200)
                worker=threading.Thread(target=other_thread);worker.start()
                while worker.is_alive():await asyncio.sleep(.02)
                self.assertIs(pool.client,shared);self.assertFalse(shared.is_closed)
                async with pool.lease(timeout=5) as client:self.assertEqual((await client.get(url+'/apres')).status_code,200)
        try:
            with patch.dict('os.environ',NO_PROXY='*',no_proxy='*'):asyncio.run(main())
        finally:
            server.shutdown();server.server_close();thread.join(2)
        self.assertEqual(results,{'codes':[200,200,200,200,True]})
        # Pool de la boucle principale : une connexion gardée ; l'autre boucle : une par requête, la sienne
        self.assertEqual(len(connections),1+5)

    def test_a_call_asking_to_follow_redirects_is_not_followed(self):
        seen=[]
        def handle(request):
            seen.append(request.url.path)
            if request.url.path=='/redirige':return httpx.Response(302,headers={'Location':'http://ailleurs.test/vole'})
            return httpx.Response(200)
        original=httpx.AsyncClient
        def factory(**kwargs):return original(transport=httpx.MockTransport(handle),**kwargs)
        pool=self.m.RunnerConnections()
        async def scenario():
            lease=pool.lease(timeout=5)
            # Hors du pool (client d'une requête), puis dans le pool
            self.assertEqual((await lease.get('http://runner.test/redirige',follow_redirects=True)).status_code,302)
            async with pool.lifespan():
                self.assertEqual((await lease.get('http://runner.test/redirige',follow_redirects=True)).status_code,302)
                async with lease.stream('GET','http://runner.test/redirige',follow_redirects=True) as r:
                    self.assertEqual(r.status_code,302)
        with patch.object(httpx,'AsyncClient',side_effect=factory):asyncio.run(scenario())
        self.assertEqual(seen,['/redirige']*3)

    def test_gateway_keeps_native_lifespan_and_closes_pool_even_on_failure_or_reload(self):
        try:
            from fastapi import FastAPI
        except ImportError:
            self.skipTest('FastAPI requis')
        pool=self.m.runner_connections;events=[];clients=[]
        @contextlib.asynccontextmanager
        async def native(app):
            self.assertIsNotNone(pool.client);events.append('start')
            try:yield {'native':True}
            finally:
                self.assertFalse(pool.client.is_closed);events.append('stop')
        upstream=types.ModuleType('main');upstream.app=FastAPI(lifespan=native);upstream.require_secret=lambda:None
        gateway=types.ModuleType('gateway');gateway.httpx=httpx
        factory=httpx.AsyncClient
        source=SOURCE.with_name('nc_gateway.py')
        choix=types.ModuleType('nc_choix');choix.__file__=str(SOURCE.with_name('nc_choix.py'))
        exec(compile(SOURCE.with_name('nc_choix.py').read_text(),choix.__file__,'exec'),choix.__dict__)
        telegram=types.ModuleType('nc_telegram');telegram.installer=lambda upstream:None   # file d'attente Telegram : hors sujet ici
        with patch.dict(sys.modules,{'main':upstream,'gateway':gateway,'nc_management':self.m,'nc_choix':choix,'nc_telegram':telegram}):
            for _ in range(2):
                module=types.ModuleType('gateway_pool_test');exec(compile(source.read_text(),str(source),'exec'),module.__dict__)
            async def scenario():
                for fail in (False,True):
                    try:
                        async with upstream.app.router.lifespan_context(upstream.app) as state:
                            self.assertTrue(state['native']);clients.append(pool.client)
                            self.assertIs(gateway.httpx.TimeoutException,httpx.TimeoutException)
                            if fail:raise RuntimeError('simulated shutdown')
                    except RuntimeError:
                        if not fail:raise
                    self.assertIsNone(pool.client)
            asyncio.run(scenario())
        self.assertEqual(events,['start','stop','start','stop'])
        self.assertTrue(all(c.is_closed for c in clients))
        self.assertIs(httpx.AsyncClient,factory)


class GestionDepuis4ecc57a(unittest.TestCase):
    """Ce que 4ecc57a impose sur /api/nc/manage, repris dans notre dispatch (qui remplace celui du serveur)."""
    def setUp(self):
        self.m=types.ModuleType('manage_test');self.m.__file__=str(SOURCE)
        exec(compile(SOURCE.read_text(),str(SOURCE),'exec'),self.m.__dict__)
        self.appels=[];self.noeuds=[]
        async def runner(method,path,body=None):
            self.appels.append((method,path,body));return {'session':{'session_token':'jeton1'}}
        self.m.runner=runner
        hub=types.SimpleNamespace(
            rotate_conversation_token=lambda k=None:self.noeuds.append(('rotation',k)),
            set_conversation_token=lambda k,t:self.noeuds.append(('jeton',k,t)))
        async def fin(node_id=None,origin=None):
            self.noeuds.append(('fin',node_id));return ['pc']
        hub.send_session_end=fin
        core=types.ModuleType('core');mod=types.ModuleType('core.node_hub');mod.NODE_HUB=hub
        patcher=patch.dict(sys.modules,{'core':core,'core.node_hub':mod});patcher.start();self.addCleanup(patcher.stop)

    def run_(self,*a,**k):return asyncio.run(self.m.dispatch(*a,**k))

    def test_session_key_must_be_desktop_or_default(self):
        for bad in ('telegram:1','client:bureau','desktop:','desktop:a b','x'):
            with self.assertRaises(ValueError):self.run_('session',{},session_key=bad)
        for good in (None,'default','desktop:mon-pc.local'):self.run_('session',{},session_key=good)

    def test_session_update_whitelists(self):
        for bad in ({'permission_mode':'rm -rf'},{'mode':'--evil'}):
            with self.assertRaises(ValueError):self.run_('session.update',bad,True,session_key='desktop:a')
        self.run_('session.update',{'mode':'plan','permission_mode':'request-review'},True,session_key='desktop:a')
        self.assertEqual(self.appels[-1][2]['mode'],'plan')

    def test_session_update_refuses_the_modes_removed_like_be109d5(self):
        for mode in ('yolo','bypass','always-proceed'):
            with self.assertRaises(ValueError):self.run_('session.update',{'permission_mode':mode},True,session_key='desktop:a')
        for mode in ('default','request-review','plan','ask','auto_edit','auto'):
            self.run_('session.update',{'permission_mode':mode},True,session_key='desktop:a')

    def test_the_hub_never_receives_a_conversation_token_from_us(self):
        self.run_('session.reset',{},True,session_key='desktop:a')
        self.run_('conversation.resume',{'id':'abc'},True,session_key='desktop:a')
        self.assertFalse([n for n in self.noeuds if n[0]=='jeton'])

    def test_reset_builds_the_origin_before_the_rotation_and_closes_only_that_session(self):
        # 94a3a93 : l'origine se construit AVANT la rotation du jeton, puis seule la session de cette origine se ferme
        vus=[];ordre=[]
        hub=sys.modules['core.node_hub'].NODE_HUB
        def construit(session_key=None,**_):
            ordre.append('origine');return {'via':'desktop','chat':session_key}
        hub.build_origin=construit
        hub.rotate_conversation_token=lambda k=None:ordre.append('rotation')
        async def fin(node_id=None,origin=None):
            ordre.append('fin');vus.append((node_id,origin));return []
        hub.send_session_end=fin
        self.run_('session.reset',{},True,session_key='desktop:a')
        self.assertEqual(vus,[(None,{'via':'desktop','chat':'desktop:a'})])
        self.assertEqual(ordre,['origine','rotation','fin'])
        vus.clear()
        self.run_('conversation.resume',{'id':'abc'},True,session_key='desktop:b')
        self.assertEqual(vus,[(None,{'via':'desktop','chat':'desktop:b'})])

    def test_reset_of_the_default_session_still_ends_every_node(self):
        vus=[]
        hub=sys.modules['core.node_hub'].NODE_HUB
        hub.build_origin=lambda session_key=None,**_:{'via':'default','chat':'default'}
        async def fin(node_id=None,origin=None):
            vus.append((node_id,origin));return []
        hub.send_session_end=fin
        self.run_('session.reset',{},True)
        self.run_('session.reset',{},True,session_key='default')
        self.assertEqual(vus,[(None,None),(None,None)])

    def test_a_hub_without_the_origin_parameter_ends_every_node_like_4ecc57a(self):
        vus=[]
        hub=sys.modules['core.node_hub'].NODE_HUB
        hub.build_origin=lambda session_key=None,**_:{'via':'desktop','chat':session_key}
        async def fin(node_id=None):
            vus.append(node_id);return []
        hub.send_session_end=fin
        self.run_('session.reset',{},True,session_key='desktop:a')
        self.assertEqual(vus,[None])

    def test_no_conversation_token_helper_is_left(self):
        self.assertFalse(hasattr(self.m,'jeton_conversation'))

    def test_reset_and_resume_end_node_sessions_without_setting_the_token(self):
        self.run_('session.reset',{},True,session_key='desktop:a')
        # Le jeton de conversation n'est plus retenu côté serveur (inerte à be109d5, dangereux si réactivé)
        self.assertEqual(self.noeuds,[('rotation','desktop:a'),('fin',None)])
        self.noeuds.clear()
        self.run_('conversation.resume',{'id':'abc'},True,session_key='desktop:a')
        self.assertEqual(self.noeuds[:2],[('rotation','desktop:a'),('fin',None)])

    def test_node_session_end_needs_confirmation_and_reaches_the_hub(self):
        self.assertIn('error',self.run_('node.session_end',{}))
        self.assertEqual(self.run_('node.session_end',{'node_id':'pc'},True),{'success':True,'closed_nodes':['pc']})
        self.assertEqual(self.noeuds[-1],('fin','pc'))

    def test_node_session_end_failure_is_reported(self):
        # Un échec du hub (ou une révision sans fin de session) n'est pas un succès vide
        async def casse(node_id=None):
            raise RuntimeError('hub absent')
        sys.modules['core.node_hub'].NODE_HUB.send_session_end=casse
        r=self.run_('node.session_end',{'node_id':'pc'},True)
        self.assertFalse(r.get('success'))
        self.assertIn('error',r)

    def test_reset_rotation_failure_still_ends_node_sessions(self):
        hub=sys.modules['core.node_hub'].NODE_HUB
        def casse(k=None):
            raise RuntimeError('rotation impossible')
        hub.rotate_conversation_token=casse
        self.run_('session.reset',{},True)
        self.assertIn(('fin',None),self.noeuds,'la fin de session des nœuds n\'est pas sautée')

    def test_without_node_hub_everything_still_works(self):
        with patch.dict(sys.modules,{'core.node_hub':None}):
            self.assertIn('session',self.run_('session.reset',{},True,session_key='desktop:a'))


if __name__=='__main__':unittest.main()

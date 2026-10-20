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
        pool=self.m.RunnerConnections()
        async def scenario():
            async with pool.lease(timeout=1) as standalone:self.assertFalse(standalone.is_closed)
            self.assertTrue(standalone.is_closed)
            async with pool.lifespan():
                shared=pool.client
                async with pool.lease(headers={'X-Custom':'value'}) as dedicated:
                    self.assertIsNot(shared,dedicated);self.assertEqual(dedicated.headers['X-Custom'],'value')
                self.assertTrue(dedicated.is_closed);self.assertFalse(shared.is_closed)
        asyncio.run(scenario())

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
        with patch.dict(sys.modules,{'main':upstream,'gateway':gateway,'nc_management':self.m}):
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


if __name__=='__main__':unittest.main()

"""Application runner d'origine enrichie : mêmes routes, mémoire et lifespan."""
import main as upstream
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from nc_engines import install, executable

# Le backend récent installe déjà le gestionnaire : garder le même état et verrou,
# plutôt que d'envelopper ses quatre moteurs dans un second gestionnaire.
engines=getattr(upstream.run_agy,'__self__',None)
if not all(callable(getattr(engines,name,None)) for name in ('snapshot','choose','session')):
    engines=install(upstream)
app=upstream.app
native_health=upstream.health
for _route in list(app.routes):
    if getattr(_route,'path',None) in ('/nc/engines','/nc/engine'):
        app.routes.remove(_route)


@app.get('/nc/engines')
async def settings(request: Request):
    upstream._check_secret(request)
    return engines.snapshot()


@app.post('/nc/engine')
async def select(request: Request):
    upstream._check_secret(request)
    raw=await request.body()
    if len(raw)>4096: raise HTTPException(413)
    try:
        import json
        values=json.loads(raw)
        if not isinstance(values,dict) or any(not isinstance(v,str) or len(v)>200 for v in values.values()): raise ValueError
        return dict(status='updated',session=engines.choose(**values))
    except (ValueError,TypeError): raise HTTPException(400,detail='Réglages moteur invalides, CLI absent ou requête en cours.') from None


# La santé upstream ne teste qu'AGY. Le gateway et les bots doivent voir le moteur actif.
async def health():
    engine=engines.session()['engine']
    if engine=='agy': return await native_health()
    available=bool(executable(engine))
    return JSONResponse(status_code=200 if available else 503,content=dict(status='ok' if available else 'degraded',
        version='nc-engines-1',engine=engine,engine_available=available,agy_available=bool(executable('agy')),session=engines.session()))


for route in app.routes:
    if getattr(route,'path',None)=='/health':
        app.routes.remove(route)
        break
app.add_api_route('/health',health,methods=['GET'])

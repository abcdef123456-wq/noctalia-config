"""Application runner d'origine enrichie : mêmes routes, mémoire et lifespan."""
# Nos modules d'abord : le dépôt du serveur a ses propres copies (anciennes) de nc_engines ; chargées à la place des
# nôtres, elles perdraient sans bruit les corrections (DEP-01). Une mauvaise résolution échoue franchement.
import importlib.util as _iu
import sys as _sys
from pathlib import Path as _P


def _origine(nom):
    m = _sys.modules.get(nom)
    if m is not None:
        return getattr(m, "__file__", None)          # déjà chargé (un test injecte des modules sans fichier : rien)
    try:
        s = _iu.find_spec(nom)
    except (ImportError, ValueError):
        return None
    return s.origin if s else None


if "__file__" in globals():
    for _m in ("nc_engines",):
        _o = _origine(_m)
        if _o and _P(_o).resolve().parent != _P(__file__).resolve().parent:
            raise RuntimeError(f"{_m} ne vient pas de l'overlay noctalia-config ({_o}) : relance le déployeur "
                               "(nc-jarvis), qui place l'overlay en tête (--app-dir)")
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
async def settings(request: Request, session_key: str | None = None):
    upstream._check_secret(request)
    # Avec AGY récent, la session montrée est celle du PC qui demande (session_key) ; nos CLI : la session commune
    if session_key is not None and len(session_key)>200: raise HTTPException(400)
    return engines.snapshot(session_key)


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

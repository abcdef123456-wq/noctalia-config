"""Overlay gateway JARVIS-BIS : conserve l'app upstream, ses bots et son lifespan."""
# Nos modules d'abord : le dépôt du serveur a ses propres copies (anciennes) de nc_management, nc_telegram, nc_noctalia, nc_google ; chargées à la place des
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
    for _m in ("nc_management", "nc_telegram", "nc_noctalia", "nc_google"):
        _o = _origine(_m)
        if _o and _P(_o).resolve().parent != _P(__file__).resolve().parent:
            raise RuntimeError(f"{_m} ne vient pas de l'overlay noctalia-config ({_o}) : relance le déployeur "
                               "(nc-jarvis), qui place l'overlay en tête (--app-dir)")
import main as upstream
import contextlib
import gateway as runner_gateway
import httpx
from fastapi import Depends, HTTPException, Request
from nc_management import dispatch, runner_connections, RunnerHttpx
import nc_telegram

app = upstream.app
# Polling Telegram : les messages reçus pendant que le PC était éteint sont traités au démarrage (nc_telegram)
nc_telegram.installer(upstream)
# Toutes les fonctions HTTP upstream (bureau, Telegram et Discord) gardent leur contrat.
# Seule leur fabrique de clients emprunte les connexions du gateway actif.
runner_gateway.httpx = RunnerHttpx(httpx, runner_connections)
native_lifespan = getattr(app.state, 'nc_native_lifespan', app.router.lifespan_context)
app.state.nc_native_lifespan = native_lifespan


@contextlib.asynccontextmanager
async def lifespan(app):
    async with runner_connections.lifespan():
        async with native_lifespan(app) as state:
            yield state


app.router.lifespan_context = lifespan

for _route in list(app.routes):
    if getattr(_route, 'path', None) == '/api/nc/manage':
        app.routes.remove(_route)


@app.post('/api/nc/manage', dependencies=[Depends(upstream.require_secret)])
async def manage(request: Request):
    raw = await request.body()
    if len(raw) > 65536:
        raise HTTPException(413, 'Requête trop volumineuse')
    import json
    try:
        body = json.loads(raw)
        if not isinstance(body, dict) or not isinstance(body.get('params', {}), dict):
            raise ValueError
        return await dispatch(body.get('op'), body.get('params', {}), body.get('confirmed') is True)
    except (ValueError, TypeError, KeyError):
        raise HTTPException(400, 'Paramètres invalides') from None

"""Overlay gateway JARVIS-BIS : conserve l'app upstream, ses bots et son lifespan."""
import main as upstream
from fastapi import Depends, HTTPException, Request
from nc_management import dispatch

app = upstream.app


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

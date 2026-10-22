"""Overlay gateway JARVIS-BIS : conserve l'app upstream, ses bots et son lifespan."""
# Nos modules d'abord : le dépôt du serveur a ses propres copies (anciennes) de nc_management, nc_telegram, nc_noctalia, nc_google (nc_choix s'il en a une) ; chargées à la place des
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
    for _m in ("nc_management", "nc_telegram", "nc_noctalia", "nc_google", "nc_choix"):
        _o = _origine(_m)
        if _o and _P(_o).resolve().parent != _P(__file__).resolve().parent:
            raise RuntimeError(f"{_m} ne vient pas de l'overlay noctalia-config ({_o}) : relance le déployeur "
                               "(nc-jarvis), qui place l'overlay en tête (--app-dir)")
import main as upstream
import contextlib
import contextvars
import inspect
import json
import gateway as runner_gateway
import httpx
from fastapi import Depends, HTTPException, Request
from nc_management import dispatch, runner_connections, RunnerHttpx
from nc_choix import extraire_choix, verifier_choix
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

# Choix cliquables (issue #7) : quand il propose des options, l'agent finit par [[choix: A | B]] (consigne de nc_engines).
# /api/ask, la route du bureau, les renvoie à part : {"output": texte sans le marqueur, "choices": [...]}. Telegram et
# Discord, qui passent par forward_to_runner sans cette route, reçoivent le texte sans le marqueur.
_pour_le_bureau = contextvars.ContextVar('nc_choix_bureau', default=False)


def _sans_marqueur(forward):
    async def relais(*args, **kwargs):
        resultat = await forward(*args, **kwargs)
        if not _pour_le_bureau.get() and isinstance(resultat, dict) and isinstance(resultat.get('output'), str):
            resultat = dict(resultat, output=extraire_choix(resultat['output'])[0])
        return resultat
    relais.nc_choix = True
    return relais


def _avec_choix(corps):
    """Corps JSON de /api/ask avec "choices" quand la réponse en propose ; tout autre corps reste tel quel."""
    try:
        donnees = json.loads(corps) if len(corps) <= 4 * 1024 * 1024 else None
    except ValueError:
        return corps
    if not isinstance(donnees, dict) or not isinstance(donnees.get('output'), str):
        return corps
    donnees['output'], choix = extraire_choix(donnees['output'])
    # Le serveur (JARVIS-BIS depuis 3d1c6b6) a pu les extraire lui-même : gardés s'ils respectent nos limites
    choix = choix or verifier_choix(donnees.get('choices'))
    if choix:
        donnees['choices'] = choix
    else:
        donnees.pop('choices', None)
    return json.dumps(donnees, ensure_ascii=False).encode()


def _choix_du_bureau(route_app):
    """La route /api/ask d'origine, dont seule une réponse 200 en JSON est relue ; statut, erreurs et autres champs
    passent tels quels."""
    async def asgi(scope, receive, send):
        if scope.get('type') != 'http':
            return await route_app(scope, receive, send)
        debut, morceaux = None, []

        async def envoyer(message):
            nonlocal debut
            if debut is None and message['type'] == 'http.response.start':
                entetes = {bytes(k).lower(): bytes(v) for k, v in message.get('headers', [])}
                if message.get('status') == 200 and entetes.get(b'content-type', b'').startswith(b'application/json'):
                    debut = message
                    return
            elif debut is not None and message['type'] == 'http.response.body':
                morceaux.append(message.get('body', b''))
                if message.get('more_body'):
                    return
                corps = _avec_choix(b''.join(morceaux))
                entetes = [(k, v) for k, v in debut.get('headers', []) if bytes(k).lower() != b'content-length']
                await send(dict(debut, headers=entetes + [(b'content-length', str(len(corps)).encode())]))
                await send({'type': 'http.response.body', 'body': corps})
                return
            await send(message)

        jeton = _pour_le_bureau.set(True)
        try:
            await route_app(scope, receive, envoyer)
        finally:
            _pour_le_bureau.reset(jeton)
    asgi.nc_choix = True
    return asgi


for _route in app.routes:
    if getattr(_route, 'path', None) == '/api/ask' and callable(getattr(_route, 'app', None)) \
            and not getattr(_route.app, 'nc_choix', False):
        _route.app = _choix_du_bureau(_route.app)
_forward = getattr(runner_gateway, 'forward_to_runner', None)
if inspect.iscoroutinefunction(_forward) and not getattr(_forward, 'nc_choix', False):
    _relais = _sans_marqueur(_forward)
    # Les bots ont importé le nom (from gateway import forward_to_runner) : chaque copie du nom est remplacée
    for _mod in list(_sys.modules.values()):
        try:
            if vars(_mod).get('forward_to_runner') is _forward:
                setattr(_mod, 'forward_to_runner', _relais)
        except TypeError:
            pass

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

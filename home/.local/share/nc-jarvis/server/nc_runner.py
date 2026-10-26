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


def _sans_jeton_d_origine():
    """Depuis 94a3a93, le runner garde en mémoire le jeton d'origine reçu du gateway et l'écrit pour l'agent (fichier
    par session, plus l'ancien « active_token » commun). Un /run direct avec une session_key de Telegram recevait ainsi
    le jeton de cette conversation. Ici nodes_mcp n'est pas installé : plus aucun jeton n'est gardé ni écrit.
    Sans effet sur une révision qui n'a pas ces fonctions (4ecc57a et avant)."""
    import contextlib
    import sys
    bridge = sys.modules.get('agy_bridge')
    if bridge is None: return
    if hasattr(bridge, 'active_origin_token_scope'):
        bridge.active_origin_token_scope = lambda token=None, session_key='default': contextlib.nullcontext()
    if hasattr(bridge, 'get_or_set_origin_token'):
        bridge.get_or_set_origin_token = lambda session_key='default', token=None: ''


_sans_jeton_d_origine()

# agy en mode « sans confirmation » : 17525af remet --dangerously-skip-permissions dès que le mode n'est pas
# request-review, et nc_engines impose « default » à agy (request-review planterait ffb19b9). Le drapeau partirait donc à
# CHAQUE tour, alors qu'agy tourne avec le vrai HOME, le .env du serveur dans son environnement, et que le briefing lui
# fait lire des e-mails et des pages web : un message piégé (injection de prompt) suffirait à lancer du shell ou à envoyer
# des fichiers. Le drapeau est retiré, sauf accord écrit à la main dans le .env du serveur (jamais par le déployeur ni
# par une requête de gestion : hors de CONFIG_PERMIS).
DRAPEAU_AGY = '--dangerously-skip-permissions'
_AVEC_VALEUR = ('-p', '--print', '--prompt', '-i', '--prompt-interactive')   # un prompt égal au drapeau reste un prompt


def agy_sans_confirmation_permis():
    import os
    return os.environ.get('NC_AGY_SANS_CONFIRMATION', '').strip().lower() == 'oui'


def commande_agy_sure(cmd):
    """La commande telle qu'elle partira : sans le drapeau pour agy (sauf accord) ; toute autre commande intacte."""
    if not cmd or _P(str(cmd[0])).name != 'agy' or agy_sans_confirmation_permis():
        return list(cmd)
    sure = [c for i, c in enumerate(cmd) if not (c == DRAPEAU_AGY and i and cmd[i - 1] not in _AVEC_VALEUR)]
    if len(sure) != len(cmd):
        import logging
        logging.getLogger('nc_runner').info('agy : auto-approbation des outils retirée (NC_AGY_SANS_CONFIRMATION non accordé)')
    return sure


def _sans_auto_approbation():
    """agy_bridge lance agy par asyncio.create_subprocess_exec (oneshot, worker stream-json et repli ; 4ecc57a à
    17525af) : son « asyncio » devient un relais qui délègue tout, sauf ce lancement, filtré par commande_agy_sure.
    Même procédé que runner_gateway.httpx = RunnerHttpx(...) dans nc_gateway. Sans agy_bridge : rien."""
    import sys
    bridge = sys.modules.get('agy_bridge')
    vrai = getattr(bridge, 'asyncio', None)
    if vrai is None or getattr(vrai, 'nc_relais', False):
        return

    class _Relais:
        nc_relais = True

        def __getattr__(self, nom):
            return getattr(vrai, nom)

        async def create_subprocess_exec(self, program, *args, **kw):
            cmd = commande_agy_sure([program, *args])
            return await vrai.create_subprocess_exec(*cmd, **kw)
    bridge.asyncio = _Relais()
    if not agy_sans_confirmation_permis() and agy_toujours_permis():
        import logging
        logging.getLogger('nc_runner').warning(
            'agy : toolPermission vaut always-proceed dans ~/.gemini/antigravity-cli/settings.json ; il peut approuver les '
            'outils même sans --dangerously-skip-permissions (voir docs/jarvis.md, « agy sans auto-approbation »)')


def agy_toujours_permis():
    """Le réglage d'agy lui-même (toolPermission, choisi dans son interface) : always-proceed approuverait tout."""
    import json
    import os
    try:
        with open(os.path.join(os.path.expanduser('~'), '.gemini/antigravity-cli/settings.json'), encoding='utf-8') as f:
            return str(json.load(f).get('toolPermission', '')).strip().lower() == 'always-proceed'
    except (OSError, ValueError, AttributeError):
        return False


_sans_auto_approbation()

# Pièces jointes (a25e540) : le runner d'origine les écrit dans /tmp/assistant_uploads et ne les efface qu'au bout de
# 7 jours, au démarrage. Ici : celles de plus d'une heure, au démarrage puis après chaque /run (l'agent a fini avec
# elles ; une question suivante de la même conversation a encore l'heure pour y revenir).
DOSSIER_PIECES = __import__('os').environ.get('NC_PIECES_JOINTES') or '/tmp/assistant_uploads'   # (les tests en mettent un à eux)
AGE_PIECES = 3600


def _purger_pieces_jointes():
    import os
    import stat
    import time
    try:
        entrees = list(os.scandir(DOSSIER_PIECES))
    except OSError:
        return 0
    n, maintenant = 0, time.time()
    for e in entrees:
        try:
            st = e.stat(follow_symlinks=False)                # un lien est effacé lui-même, jamais sa cible
            if (stat.S_ISREG(st.st_mode) or stat.S_ISLNK(st.st_mode)) and maintenant - st.st_mtime > AGE_PIECES:
                os.unlink(e.path)
                n += 1
        except OSError:
            pass
    return n


class _MenagePieces:
    """Middleware ASGI pur (pas BaseHTTPMiddleware : il casserait le streaming et les contextvars) : le ménage après la
    réponse d'un /run, même en erreur."""
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        try:
            await self.app(scope, receive, send)
        finally:
            if scope.get('type') == 'http' and str(scope.get('path', '')).startswith('/run'):
                _purger_pieces_jointes()


_purger_pieces_jointes()

# Le backend récent installe déjà le gestionnaire : garder le même état et verrou,
# plutôt que d'envelopper ses quatre moteurs dans un second gestionnaire.
engines=getattr(upstream.run_agy,'__self__',None)
if not all(callable(getattr(engines,name,None)) for name in ('snapshot','choose','session')):
    engines=install(upstream)
app=upstream.app
app.add_middleware(_MenagePieces)
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

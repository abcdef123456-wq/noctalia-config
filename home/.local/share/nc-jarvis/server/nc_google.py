"""Google Agenda pour l'île, par l'intégration Google déjà faite pour JARVIS (integrations/google-workspace :
setup_oauth.py écrit token.json, que les serveurs MCP du runner utilisent). Même jeton, aucune nouvelle
authentification : le gateway rafraîchit l'access token (jamais renvoyé) et lit l'API Calendar en REST, avec la
bibliothèque standard. Ops de /api/nc/manage : google.status (configuré ?) et google.calendar (événements d'une période,
tous les calendriers cochés, chacun avec sa couleur). Fuseau : BRIEFING_TIMEZONE, sinon REMINDER_TIMEZONE, sinon
Europe/Paris. Variables : NC_GOOGLE_TOKEN_FILE pour déplacer le jeton.
"""
import datetime
import json
import logging
import os
from pathlib import Path
import re
import time
import urllib.error
import urllib.parse
import urllib.request

logger = logging.getLogger("nc_google")
TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
API = "https://www.googleapis.com/calendar/v3"
DELAI = 20
MAX_EVENEMENTS = 500
_jeton = {"valeur": "", "expire": 0.0}
DATE = re.compile(r"\d{4}-\d{2}-\d{2}")


def fichier_jeton():
    perso = os.environ.get("NC_GOOGLE_TOKEN_FILE", "").strip()
    if perso:
        return Path(perso)
    try:
        import nc_management
        return nc_management.root() / "integrations/google-workspace/token.json"
    except Exception:
        return Path.cwd() / "integrations/google-workspace/token.json"


def fuseau():
    return os.environ.get("BRIEFING_TIMEZONE") or os.environ.get("REMINDER_TIMEZONE") or "Europe/Paris"


def configure():
    try:
        d = json.loads(fichier_jeton().read_text(encoding="utf-8"))
        return bool(isinstance(d, dict) and d.get("refresh_token") and d.get("client_id"))
    except (OSError, ValueError):
        return False


def requete(methode, url, params=None, corps=None, entetes=None):
    """Un appel HTTP (bibliothèque standard) ; renvoie (code, JSON ou None). Remplacée dans les tests."""
    if params:
        url += ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
    donnees = urllib.parse.urlencode(corps).encode() if corps else None
    req = urllib.request.Request(url, data=donnees, headers=entetes or {}, method=methode)
    try:
        with urllib.request.urlopen(req, timeout=DELAI) as r:
            return r.status, json.loads(r.read(4 * 1024 * 1024).decode("utf-8") or "null")
    except urllib.error.HTTPError as e:
        return e.code, None


def access_token():
    """L'access token, rafraîchi avec le refresh_token de token.json ; gardé en mémoire jusqu'à expiration."""
    if _jeton["valeur"] and time.time() < _jeton["expire"] - 60:
        return _jeton["valeur"]
    d = json.loads(fichier_jeton().read_text(encoding="utf-8"))
    code, r = requete("POST", TOKEN_ENDPOINT, corps=dict(client_id=d["client_id"], client_secret=d.get("client_secret", ""),
                                                        refresh_token=d["refresh_token"], grant_type="refresh_token"))
    if code != 200 or not isinstance(r, dict) or not r.get("access_token"):
        raise RuntimeError("Jeton Google refusé (HTTP %s) : relance setup_oauth.py côté JARVIS." % code)
    _jeton["valeur"] = r["access_token"]
    _jeton["expire"] = time.time() + float(r.get("expires_in") or 3600)
    return _jeton["valeur"]


def api(chemin, params=None):
    entetes = {"Authorization": "Bearer " + access_token(), "Accept": "application/json"}
    code, r = requete("GET", API + chemin, params=params, entetes=entetes)
    if code == 401:
        _jeton["valeur"] = ""
        entetes["Authorization"] = "Bearer " + access_token()
        code, r = requete("GET", API + chemin, params=params, entetes=entetes)
    if code != 200 or not isinstance(r, dict):
        raise RuntimeError("Google Agenda indisponible (HTTP %s)." % code)
    return r


def calendriers():
    """Les calendriers cochés dans Google Agenda : id, nom, couleur."""
    r = api("/users/me/calendarList", dict(maxResults=50, minAccessRole="reader"))
    return [dict(id=c["id"], nom=c.get("summaryOverride") or c.get("summary") or c["id"], couleur=c.get("backgroundColor") or "#4285f4",
                 principal=bool(c.get("primary")))
            for c in r.get("items", []) if c.get("id") and c.get("selected", True)]


def evenements(debut, fin):
    """Les événements entre deux dates (AAAA-MM-JJ, fin exclue), tous calendriers, triés ; heures dans le fuseau."""
    if not (DATE.fullmatch(debut or "") and DATE.fullmatch(fin or "")) or fin <= debut:
        raise ValueError("Période : from et to en AAAA-MM-JJ, to après from.")
    d0 = datetime.date.fromisoformat(debut)
    if (datetime.date.fromisoformat(fin) - d0).days > 62:
        raise ValueError("Période : 62 jours au plus.")
    tz = fuseau()
    liste, cals = [], calendriers()
    for c in cals:
        page = None
        while True:
            params = dict(timeMin=debut + "T00:00:00Z", timeMax=fin + "T00:00:00Z", singleEvents="true", orderBy="startTime",
                          maxResults=250, timeZone=tz)
            if page:
                params["pageToken"] = page
            r = api("/calendars/" + urllib.parse.quote(c["id"], safe="") + "/events", params)
            for e in r.get("items", []):
                if e.get("status") == "cancelled" or not e.get("start"):
                    continue
                journee = "date" in e["start"]
                liste.append(dict(id=str(e.get("id", ""))[:200], titre=str(e.get("summary") or "(sans titre)")[:200],
                                  lieu=str(e.get("location") or "")[:200], calendrier=c["nom"], couleur=c["couleur"],
                                  debut=e["start"].get("date") or e["start"].get("dateTime"),
                                  fin=(e.get("end") or {}).get("date") or (e.get("end") or {}).get("dateTime") or "",
                                  journee=journee))
                if len(liste) >= MAX_EVENEMENTS:
                    break
            page = r.get("nextPageToken")
            if not page or len(liste) >= MAX_EVENEMENTS:
                break
    liste.sort(key=lambda e: (e["debut"][:10], not e["journee"], e["debut"]))
    return dict(events=liste, calendars=[dict(nom=c["nom"], couleur=c["couleur"]) for c in cals], timezone=tz,
                **{"from": debut, "to": fin})


def statut():
    return dict(configured=configure(), timezone=fuseau())


async def dispatch(op, p):
    """Appelé par nc_management.dispatch (lectures)."""
    import asyncio
    if op == "google.status":
        return statut()
    if not configure():
        return dict(error="Google n'est pas connecté à JARVIS : lance setup_oauth.py (integrations/google-workspace) côté JARVIS.")
    try:
        return await asyncio.to_thread(evenements, p.get("from"), p.get("to"))
    except ValueError as exc:
        return dict(error=str(exc))
    except (OSError, RuntimeError, KeyError) as exc:
        logger.warning("Google Agenda : %s", exc)
        return dict(error=str(exc)[:200])

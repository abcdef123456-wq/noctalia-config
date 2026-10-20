"""Google Agenda pour l'île (nc_google, gateway) : jeton rafraîchi et jamais renvoyé, calendriers et événements
normalisés, erreurs sans secret. HTTP remplacé par un faux ; fichier de jeton temporaire."""
import asyncio
import json
from pathlib import Path
import tempfile
import types
import unittest
from unittest import mock

REPO = Path(__file__).resolve().parents[1]
SOURCE = REPO / "home/.local/share/nc-jarvis/server/nc_google.py"
JETON = dict(client_id="id-test", client_secret="secret-test", refresh_token="refresh-test")


def module():
    m = types.ModuleType("nc_google_test")
    m.__file__ = str(SOURCE)
    exec(compile(SOURCE.read_text(), str(SOURCE), "exec"), m.__dict__)
    return m


class FauxGoogle:
    def __init__(self):
        self.appels = []
        self.jeton_refuse = False
        self.expire_une_fois = False
        self.calendriers = [dict(id="primary", summary="Perso", backgroundColor="#1a73e8", primary=True, selected=True),
                            dict(id="travail@x", summary="Travail", backgroundColor="#0b8043", selected=True),
                            dict(id="cache@x", summary="Caché", backgroundColor="#000000", selected=False)]
        self.evenements = {
            "primary": [dict(id="e1", summary="Dentiste", location="Rue A", status="confirmed",
                             start=dict(dateTime="2026-10-21T14:00:00+02:00"), end=dict(dateTime="2026-10-21T15:00:00+02:00")),
                        dict(id="e0", summary="Annulé", status="cancelled", start=dict(dateTime="2026-10-21T09:00:00+02:00")),
                        dict(id="e2", summary="Vacances", start=dict(date="2026-10-24"), end=dict(date="2026-10-26"))],
            "travail@x": [dict(id="e3", status="confirmed", start=dict(dateTime="2026-10-21T09:30:00+02:00"), end=dict(dateTime="2026-10-21T10:00:00+02:00"))],
        }

    def requete(self, methode, url, params=None, corps=None, entetes=None):
        self.appels.append((methode, url, params, corps, dict(entetes or {})))
        if url.endswith("/token"):
            if self.jeton_refuse:
                return 400, dict(error="invalid_grant")
            return 200, dict(access_token="acces-" + str(len(self.appels)), expires_in=3600)
        if not (entetes or {}).get("Authorization", "").startswith("Bearer acces-"):
            return 401, None
        if self.expire_une_fois:
            self.expire_une_fois = False
            return 401, None
        if url.endswith("/users/me/calendarList"):
            return 200, dict(items=self.calendriers)
        if "/calendars/" in url:
            ident = url.split("/calendars/")[1].split("/events")[0].replace("%40", "@")
            return 200, dict(items=self.evenements.get(ident, []))
        return 404, None


class Google(unittest.TestCase):
    def setUp(self):
        self.m = module()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.jeton = Path(self.tmp.name) / "token.json"
        self.jeton.write_text(json.dumps(JETON))
        self.env = mock.patch.dict(self.m.os.environ, NC_GOOGLE_TOKEN_FILE=str(self.jeton), BRIEFING_TIMEZONE="Europe/Paris")
        self.env.start()
        self.addCleanup(self.env.stop)
        self.faux = FauxGoogle()
        self.m.requete = self.faux.requete

    def test_statut_et_jeton_absent(self):
        self.assertEqual(self.m.statut(), dict(configured=True, timezone="Europe/Paris"))
        self.jeton.write_text("{}")
        self.assertFalse(self.m.statut()["configured"])
        r = asyncio.run(self.m.dispatch("google.calendar", {"from": "2026-10-01", "to": "2026-11-01"}))
        self.assertIn("setup_oauth.py", r["error"])
        self.assertEqual(self.faux.appels, [], "non configuré : aucun appel réseau")

    def test_evenements_normalises_et_jeton_jamais_renvoye(self):
        r = asyncio.run(self.m.dispatch("google.calendar", {"from": "2026-10-01", "to": "2026-11-01"}))
        self.assertNotIn("error", r)
        self.assertEqual(r["timezone"], "Europe/Paris")
        self.assertEqual([c["nom"] for c in r["calendars"]], ["Perso", "Travail"], "le calendrier non coché est ignoré")
        titres = [(e["titre"], e["calendrier"], e["journee"], e["debut"]) for e in r["events"]]
        self.assertEqual(titres, [("(sans titre)", "Travail", False, "2026-10-21T09:30:00+02:00"),
                                  ("Dentiste", "Perso", False, "2026-10-21T14:00:00+02:00"),
                                  ("Vacances", "Perso", True, "2026-10-24")], "triés, l'annulé retiré, journée entière reconnue")
        self.assertEqual(r["events"][1]["lieu"], "Rue A")
        self.assertEqual(r["events"][1]["couleur"], "#1a73e8")
        self.assertEqual(r["events"][2]["fin"], "2026-10-26")
        dump = json.dumps(r)
        for secret in ("refresh-test", "secret-test", "acces-"):
            self.assertNotIn(secret, dump)
        # Le jeton est rafraîchi une fois, puis réutilisé
        jetons = [a for a in self.faux.appels if a[1].endswith("/token")]
        self.assertEqual(len(jetons), 1)
        self.assertEqual(jetons[0][3]["refresh_token"], "refresh-test")
        params = next(a[2] for a in self.faux.appels if "/events" in a[1])
        self.assertEqual((params["timeMin"], params["timeMax"], params["timeZone"], params["singleEvents"]), ("2026-10-01T00:00:00Z", "2026-11-01T00:00:00Z", "Europe/Paris", "true"))
        asyncio.run(self.m.dispatch("google.calendar", {"from": "2026-10-01", "to": "2026-11-01"}))
        self.assertEqual(len([a for a in self.faux.appels if a[1].endswith("/token")]), 1, "access token gardé en mémoire")

    def test_jeton_expire_puis_refuse(self):
        self.m.access_token()
        self.faux.expire_une_fois = True
        r = asyncio.run(self.m.dispatch("google.calendar", {"from": "2026-10-01", "to": "2026-11-01"}))
        self.assertNotIn("error", r, "un 401 rafraîchit le jeton et rejoue l'appel")
        self.assertEqual(len([a for a in self.faux.appels if a[1].endswith("/token")]), 2)
        self.m._jeton["valeur"] = ""
        self.faux.jeton_refuse = True
        r = asyncio.run(self.m.dispatch("google.calendar", {"from": "2026-10-01", "to": "2026-11-01"}))
        self.assertIn("Jeton Google refusé", r["error"])
        self.assertNotIn("refresh-test", r["error"])

    def test_periode_invalide(self):
        for p in ({"from": "2026-10-01"}, {"from": "20261001", "to": "2026-11-01"}, {"from": "2026-10-01", "to": "2026-10-01"},
                  {"from": "2026-01-01", "to": "2026-06-01"}):
            r = asyncio.run(self.m.dispatch("google.calendar", p))
            self.assertIn("Période", r["error"], p)
        self.assertEqual(self.faux.appels, [])


if __name__ == "__main__":
    unittest.main()

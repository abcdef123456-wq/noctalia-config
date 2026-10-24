"""nc-meteo : la ville estimée d'après l'IP est dite « estimée » ; une ville réglée ne change rien.
Le réseau est remplacé par un sitecustomize (faux Open-Meteo et faux service d'IP), HOME est temporaire."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
BIN = REPO / "home/.local/bin/nc-meteo"

FAUX_RESEAU = r'''
import io, json, urllib.request
class R(io.BytesIO):
    def __enter__(self): return self
    def __exit__(self, *a): pass
def urlopen(req, timeout=0):
    u = req.full_url
    if "geocoding" in u:
        d = {"results": [{"latitude": 1.0, "longitude": 2.0, "name": "Choisieville"}]}
    elif "ipwho.is" in u:
        d = {"success": True, "latitude": 3.0, "longitude": 4.0, "city": "Exempleville"}
    else:
        h = ["2026-01-01T%02d:00" % i for i in range(24)]
        d = {"current": {"time": "2026-01-01T10:00", "temperature_2m": 12.4, "apparent_temperature": 11, "weather_code": 0,
                         "is_day": 1, "wind_speed_10m": 5, "relative_humidity_2m": 50},
             "hourly": {"time": h, "temperature_2m": [10] * 24, "weather_code": [0] * 24, "is_day": [1] * 24},
             "daily": {"time": ["2026-01-01", "2026-01-02"], "weather_code": [0, 1], "temperature_2m_max": [14, 15], "temperature_2m_min": [5, 6]}}
    return R(json.dumps(d).encode())
urllib.request.urlopen = urlopen
'''


class MeteoEstimee(unittest.TestCase):
    def lancer(self, ville, langue="fr", *args):
        with tempfile.TemporaryDirectory() as t:
            home = Path(t)
            (home / "site").mkdir()
            (home / "site/sitecustomize.py").write_text(FAUX_RESEAU)
            (home / ".config/nc").mkdir(parents=True)
            if ville is not None:
                (home / ".config/nc/reglages.conf").write_text(f"METEO_VILLE={ville}\n")
            env = dict(os.environ, HOME=t, XDG_CACHE_HOME=str(home / "cache"), NC_LANGUE=langue, PYTHONPATH=str(home / "site"))
            r = subprocess.run([sys.executable, str(BIN), *args], env=env, capture_output=True, text=True, timeout=30)
            self.assertEqual(r.returncode, 0, r.stderr)
            return r.stdout

    def test_ville_auto_ou_vide_est_estimee(self):
        for ville in (None, "auto", ""):
            m = json.loads(self.lancer(ville))
            self.assertEqual(m["ville"], "Exempleville")
            self.assertTrue(m["estimee"], ville)
        self.assertIn("Exempleville (estimée) :", self.lancer("auto", "fr", "texte"))
        self.assertIn("Choisir ma ville", self.lancer("auto", "fr", "texte"))
        self.assertIn("Exempleville (estimated):", self.lancer("auto", "en", "text"))
        self.assertIn("Choose my city", self.lancer("auto", "en", "text"))

    def test_ville_reglee_sans_mention(self):
        m = json.loads(self.lancer("Choisieville"))
        self.assertEqual(m["ville"], "Choisieville")
        self.assertFalse(m["estimee"])
        for langue, mode in (("fr", "texte"), ("en", "text")):
            sortie = self.lancer("Choisieville", langue, mode)
            self.assertTrue(sortie.startswith("Choisieville"), sortie)
            self.assertNotIn("estim", sortie)
            self.assertNotIn("Choisir ma ville", sortie)
            self.assertNotIn("Choose my city", sortie)


if __name__ == "__main__":
    unittest.main()

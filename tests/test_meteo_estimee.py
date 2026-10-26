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
import io, json, os, urllib.request
class R(io.BytesIO):
    def __enter__(self): return self
    def __exit__(self, *a): pass
def urlopen(req, timeout=0):
    u = req.full_url
    if os.environ.get("NC_TEST_JOURNAL"):
        open(os.environ["NC_TEST_JOURNAL"], "a").write(u + "\n")
    if os.environ.get("NC_TEST_HORS") == "1":
        raise OSError("hors ligne")
    if "geocoding" in u and os.environ.get("NC_TEST_INCONNU") == "1":
        d = {}
    elif "geocoding" in u:
        d = {"results": [{"latitude": 1.0, "longitude": 2.0, "name": "Choisieville"}]}
    elif "ipwho.is" in u:
        d = {"success": True, "latitude": 3.0, "longitude": 4.0, "city": "Exempleville"}
    else:
        h = ["2026-01-01T%02d:00" % i for i in range(24)]
        trou = os.environ.get("NC_TEST_NULL") == "1"     # un créneau horaire à null, comme Open-Meteo en renvoie parfois
        deci = os.environ.get("NC_TEST_DEMI") == "1"
        d = {"current": {"time": "2026-01-01T10:00", "temperature_2m": 12.5 if deci else 12.4, "apparent_temperature": 11, "weather_code": 0,
                         "is_day": 1, "wind_speed_10m": 5, "relative_humidity_2m": 50},
             "hourly": {"time": h, "temperature_2m": [None if (trou and i == 13) else 10 for i in range(24)], "weather_code": [0] * 24, "is_day": [1] * 24},
             "daily": {"time": ["2026-01-01", "2026-01-02"], "weather_code": [0, 1], "temperature_2m_max": [14, 15], "temperature_2m_min": [5, 6]}}
    return R(json.dumps(d).encode())
urllib.request.urlopen = urlopen
'''


class MeteoEstimee(unittest.TestCase):
    def lancer(self, ville, langue="fr", *args, extra=None, avant=None, code=0):
        with tempfile.TemporaryDirectory() as t:
            home = Path(t)
            (home / "site").mkdir()
            (home / "site/sitecustomize.py").write_text(FAUX_RESEAU)
            (home / ".config/nc").mkdir(parents=True)
            if ville is not None:
                (home / ".config/nc/reglages.conf").write_text(f"METEO_VILLE={ville}\n")
            env = dict(os.environ, HOME=t, XDG_CACHE_HOME=str(home / "cache"), NC_LANGUE=langue, PYTHONPATH=str(home / "site"), **(extra or {}))
            if avant:
                avant(home / "cache/nc")
            r = subprocess.run([sys.executable, str(BIN), *args], env=env, capture_output=True, text=True, timeout=30)
            self.assertEqual(r.returncode, code, r.stderr)
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

    def test_null_dans_la_reponse_pas_de_trace(self):
        # Un null dans un tableau horaire : pas de trace, un JSON d'erreur (la pilule météo ne disparaît pas sans bruit)
        sortie = self.lancer("Choisieville", extra={"NC_TEST_NULL": "1"})
        self.assertIn("erreur", json.loads(sortie))
        self.assertIn("indisponible", self.lancer("Choisieville", "fr", "texte", extra={"NC_TEST_NULL": "1"}))

    def test_null_garde_la_derniere_meteo_connue(self):
        def vieux_cache(d):
            d.mkdir(parents=True)
            (d / "meteo.json").write_text(json.dumps({"t": 1, "demande": "Choisieville", "ville": "Ancienne", "temp": 3}))
        m = json.loads(self.lancer("Choisieville", extra={"NC_TEST_NULL": "1"}, avant=vieux_cache))
        self.assertEqual(m["ville"], "Ancienne")

    def test_cache_non_inscriptible_la_meteo_s_affiche(self):
        def ferme(d):
            d.parent.mkdir(parents=True)
            d.write_text("je suis un fichier, pas un dossier")      # makedirs échoue (OSError), même en root
        m = json.loads(self.lancer("Choisieville", avant=ferme))
        self.assertEqual(m["ville"], "Choisieville")

    def test_deux_instances_en_meme_temps(self):
        with tempfile.TemporaryDirectory() as t:
            home = Path(t)
            (home / "site").mkdir()
            (home / "site/sitecustomize.py").write_text(FAUX_RESEAU)
            env = dict(os.environ, HOME=t, XDG_CACHE_HOME=str(home / "cache"), PYTHONPATH=str(home / "site"))
            ps = [subprocess.Popen([sys.executable, str(BIN)], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for _ in range(6)]
            for p in ps:
                sortie, err = p.communicate(timeout=60)
                self.assertEqual(p.returncode, 0, err)
                self.assertEqual(json.loads(sortie)["ville"], "Exempleville", err)
            self.assertEqual(sorted(x.name for x in (home / "cache/nc").iterdir()), ["meteo.json"])     # pas de .tmp oublié

    def test_arrondi_d_affichage(self):
        # 12,5 donne 13 (round() de Python aurait donné 12)
        self.assertEqual(json.loads(self.lancer("Choisieville", extra={"NC_TEST_DEMI": "1"}))["temp"], 13)
        self.assertEqual(json.loads(self.lancer("Choisieville"))["temp"], 12)

    def test_ville_introuvable_pas_d_appel_ipwho(self):
        with tempfile.TemporaryDirectory() as t:
            j = os.path.join(t, "journal")
            m = json.loads(self.lancer("Nullepart", extra={"NC_TEST_INCONNU": "1", "NC_TEST_JOURNAL": j}))
            self.assertEqual(m, {"erreur": "ville introuvable"})
            urls = Path(j).read_text()
            self.assertIn("geocoding", urls)
            self.assertNotIn("ipwho", urls)
            self.assertIn("introuvable", self.lancer("Nullepart", "fr", "texte", extra={"NC_TEST_INCONNU": "1"}))

    def test_hors_ligne_cache_perime_ou_autre_ville(self):
        def cache(ville, age):
            def f(d):
                import time
                d.mkdir(parents=True)
                (d / "meteo.json").write_text(json.dumps({"t": time.time() - age, "demande": ville, "ville": "Ancienne", "temp": 3}))
            return f
        hors = {"NC_TEST_HORS": "1"}
        m = json.loads(self.lancer("Choisieville", extra=hors, avant=cache("Choisieville", 4 * 3600)))
        self.assertTrue(m.get("perime"))
        m = json.loads(self.lancer("Choisieville", extra=hors, avant=cache("Choisieville", 3600)))
        self.assertEqual(m["ville"], "Ancienne")
        self.assertNotIn("perime", m)
        m = json.loads(self.lancer("Choisieville", extra=hors, avant=cache("Autreville", 3600)))      # autre ville : cache refusé
        self.assertEqual(m, {"erreur": "hors ligne"})

    def test_vie_privee_dite_dans_l_aide_et_les_reglages(self):
        self.assertIn("ipwho.is", self.lancer("auto", "fr", "--help"))
        self.assertIn("Open-Meteo", self.lancer("auto", "en", "--help"))
        reglages = (REPO / "home/.local/bin/nc-reglages").read_text()
        self.assertIn("position estimée par ipwho.is d'après ton IP, météo par Open-Meteo", reglages)
        self.assertIn("ipwho.is", (REPO / "README.md").read_text())

    def test_ile_minuterie_meteo_suit_l_ecran_et_affiche_les_erreurs(self):
        etat = (REPO / "home/.config/quickshell/nc-ile/Etat.qml").read_text()
        self.assertRegex(etat, r'running: etat\.ecranVu && Reglages\.val\("ILE_METEO"')
        self.assertIn("ville introuvable", etat)
        page = (REPO / "home/.config/quickshell/nc-ile/Meteo.qml").read_text()
        self.assertIn("Etat.meteoErreur", page)
        self.assertIn("p.m.perime", page)


if __name__ == "__main__":
    unittest.main()

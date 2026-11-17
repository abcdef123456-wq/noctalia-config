"""Tests de nc-garmin : faux venv, faux paquet garminconnect, aucun réseau, tout dans un HOME temporaire."""
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.environ.get("NC_GARMIN_BIN") or os.path.join(REPO, "home", ".local", "bin", "nc-garmin")
LIBEXEC = os.path.join(os.path.dirname(os.path.dirname(SRC)), "libexec")
URL = "https://faux.example.invalid/oauth?token=SECRET123"

FAUX_PAQUET = '''
import json, os

class GarminConnectConnectionError(Exception):
    pass

class GarminConnectAuthenticationError(Exception):
    pass

class Garmin:
    def __init__(self, *a, **k):
        pass

    def login(self, tokenstore=None):
        with open(os.environ["FAKE_LOG"], "a") as f:
            f.write(json.dumps({"env": os.environ.get("GARMINTOKENS"), "store": tokenstore}) + "\\n")
        mode = os.environ.get("FAKE_MODE", "ok")
        if mode == "reseau":
            raise GarminConnectConnectionError(os.environ["FAKE_URL"])
        if mode == "auth":
            raise GarminConnectAuthenticationError(os.environ["FAKE_URL"])
        if mode == "inconnu":
            raise ValueError(os.environ["FAKE_URL"])
'''

# faux python de venv : le vrai connecteur, mais Python annonce 3.11
FAUX_VIEUX = '''#!%(py)s
import runpy, sys
sys.version_info = (3, 11, 0, "final", 0)
sys.argv = sys.argv[1:]
runpy.run_path(sys.argv[0], run_name="__main__")
'''


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="nc-garmin-test-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        t = self.tmp
        self.home = os.path.join(t, "home")
        self.cfg = os.path.join(self.home, ".config")
        self.cache_dir = os.path.join(self.home, ".cache")
        self.data = os.path.join(self.home, ".local", "share")
        self.run_dir = os.path.join(t, "run")
        for d in (self.cfg, self.cache_dir, self.data, self.run_dir, os.path.join(self.cfg, "nc")):
            os.makedirs(d)
        os.chmod(self.run_dir, 0o700)
        # arbre : bin/nc-garmin + libexec/ + share/nc/
        tree = os.path.join(t, "tree")
        os.makedirs(os.path.join(tree, "bin"))
        shutil.copytree(LIBEXEC, os.path.join(tree, "libexec"))
        self.bin = os.path.join(tree, "bin", "nc-garmin")
        shutil.copy(SRC, self.bin)
        os.chmod(self.bin, 0o755)
        self.fakelib = os.path.join(t, "fakelib")
        os.makedirs(os.path.join(self.fakelib, "garminconnect"))
        with open(os.path.join(self.fakelib, "garminconnect", "__init__.py"), "w") as f:
            f.write(FAUX_PAQUET)
        self.log = os.path.join(t, "fake.log")
        self.garmin = os.path.join(self.cfg, "nc", "garmin")
        self.jetons = os.path.join(self.garmin, "jetons")
        self.cache = os.path.join(self.cache_dir, "nc", "garmin.json")
        self.venv = os.path.join(self.data, "nc", "garmin-venv")
        self.reglages(GARMIN_ACTIF="oui")

    def reglages(self, **kv):
        with open(os.path.join(self.cfg, "nc", "reglages.conf"), "w") as f:
            f.writelines('%s=%s\n' % i for i in kv.items())

    def faux_venv(self, contenu=None):
        p = os.path.join(self.venv, "bin", "python")
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w") as f:
            f.write(contenu or '#!/bin/sh\nexec "%s" "$@"\n' % sys.executable)
        os.chmod(p, 0o755)

    def faux_jeton(self):
        os.makedirs(self.jetons, mode=0o700, exist_ok=True)
        p = os.path.join(self.jetons, "garmin_tokens.json")
        with open(p, "w") as f:
            f.write("{}")
        os.chmod(p, 0o600)

    def pret(self):
        self.faux_venv()
        self.faux_jeton()

    def env(self, **extra):
        e = dict(os.environ, HOME=self.home, XDG_CONFIG_HOME=self.cfg, XDG_CACHE_HOME=self.cache_dir, XDG_DATA_HOME=self.data,
                 XDG_STATE_HOME=os.path.join(self.home, ".local", "state"), XDG_RUNTIME_DIR=self.run_dir, TMPDIR=self.tmp,
                 PYTHONPATH=self.fakelib, FAKE_LOG=self.log, FAKE_URL=URL, NC_LANGUE="en")
        e.pop("NC_PARTAGE_ACTIF", None)
        e.update(extra)
        return e

    def nc(self, *args, **extra):
        r = subprocess.run([sys.executable, self.bin, *args], capture_output=True, text=True, env=self.env(**extra), timeout=60, stdin=subprocess.DEVNULL)
        return r

    def js(self, *args, **extra):
        r = self.nc(*args, **extra)
        return json.loads(r.stdout.strip().splitlines()[-1]), r

    def mode(self, p):
        return stat.S_IMODE(os.lstat(p).st_mode)


class TestObligatoires(Base):
    def test_1_garmintokens_ignore_et_chemin_absolu(self):
        self.pret()
        hostile = '{"di_token": "VOLE"}'
        d, r = self.js("sync", "--force", GARMINTOKENS=hostile, FAKE_MODE="ok")
        self.assertTrue(d["synchronise"], r.stdout + r.stderr)
        vu = [json.loads(x) for x in open(self.log)]
        self.assertTrue(vu)
        for v in vu:
            self.assertIsNone(v["env"])
            self.assertTrue(os.path.isabs(v["store"]))
            self.assertEqual(v["store"], self.jetons)

    def test_2_erreurs_traduites_sans_texte_brut(self):
        self.pret()
        for mode, cat in (("reseau", "reseau"), ("auth", "pas_connecte"), ("inconnu", "service_change")):
            d, r = self.js("sync", "--force", FAKE_MODE=mode)
            self.assertEqual(d["erreur"], cat)
            for flux in (r.stdout, r.stderr):
                self.assertNotIn("SECRET123", flux)
                self.assertNotIn("faux.example", flux)
        self.assertFalse(os.path.exists(self.cache))
        for racine, _, fichiers in os.walk(self.tmp):
            for n in fichiers:
                if n == "fake.log" or n == "python":
                    continue
                p = os.path.join(racine, n)
                if os.path.islink(p) or p.endswith(".py"):
                    continue
                with open(p, errors="replace") as f:
                    self.assertNotIn("SECRET123", f.read(), p)

    def test_3_python_ancien_refuse(self):
        self.faux_jeton()
        self.faux_venv(FAUX_VIEUX % {"py": sys.executable})
        d, r = self.js("sync", "--force")
        self.assertEqual(d["erreur"], "python_ancien")
        self.assertIn("3.12", d["message"])
        self.assertFalse(os.path.exists(self.cache))
        # le connecteur lui-même dit clairement pourquoi
        out = subprocess.run([self.venv + "/bin/python", os.path.join(os.path.dirname(os.path.dirname(self.bin)), "libexec", "nc-garmin-connecteur.py"),
                              self.jetons, "2026-01-01"], capture_output=True, text=True, env=self.env()).stdout
        self.assertIn("3.12", out)


class TestPermissions(Base):
    def test_dossiers_0700_cache_0600(self):
        self.pret()
        os.chmod(self.garmin, 0o755)
        os.chmod(self.jetons, 0o755)
        d, r = self.js("sync", "--force")
        self.assertTrue(d["synchronise"], r.stdout)
        self.assertEqual(self.mode(self.garmin), 0o700)
        self.assertEqual(self.mode(self.jetons), 0o700)
        self.assertEqual(self.mode(self.cache), 0o600)

    def test_dossier_cree_en_0700(self):
        self.nc("hydratation", "+250")
        self.assertEqual(self.mode(self.garmin), 0o700)
        self.assertEqual(self.mode(os.path.join(self.garmin, "hydratation.json")), 0o600)

    def test_dossier_jetons_neuf_en_0700(self):
        self.faux_venv()
        os.makedirs(self.garmin, mode=0o700)
        os.mkdir(self.jetons, 0o755)  # sera resserré par la connexion factice
        self.faux_jeton()
        os.chmod(self.jetons, 0o755)
        self.js("sync", "--force")
        self.assertEqual(self.mode(self.jetons), 0o700)

    def test_lien_symbolique_refuse(self):
        self.pret()
        cible = os.path.join(self.tmp, "ailleurs")
        os.makedirs(os.path.dirname(self.cache))
        with open(cible, "w") as f:
            f.write("x")
        os.symlink(cible, self.cache)
        d, _ = self.js("sync", "--force")
        self.assertEqual(d["erreur"], "permissions")
        with open(cible) as f:
            self.assertEqual(f.read(), "x")

    def test_dossier_jetons_lien_refuse(self):
        self.faux_venv()
        os.makedirs(self.garmin, mode=0o700)
        os.makedirs(os.path.join(self.tmp, "autre"))
        os.symlink(os.path.join(self.tmp, "autre"), self.jetons)
        d, _ = self.js("sync", "--force")
        self.assertIn(d["erreur"], ("pas_connecte", "permissions"))
        self.assertFalse(os.path.exists(self.log))


class TestCache(Base):
    def cache_ecrit(self, obj):
        os.makedirs(os.path.dirname(self.cache), exist_ok=True)
        with open(self.cache, "w") as f:
            f.write(obj if isinstance(obj, str) else json.dumps(obj))
        os.chmod(self.cache, 0o600)

    def test_cache_hostile_ou_casse(self):
        self.pret()
        for contenu in ("{pas du json", "[]", {"version": 2, "ts": 1, "metriques": {}}, {"version": 1, "ts": "x", "metriques": {}},
                        {"version": 1, "ts": True, "metriques": {}}, {"version": 1, "ts": 1, "metriques": "x"}):
            self.cache_ecrit(contenu)
            d, r = self.js("etat-json")
            self.assertTrue(d["actif"], r.stderr)
            self.assertNotIn("body_battery", d["metriques"])

    def test_cache_liste_blanche(self):
        self.pret()
        self.cache_ecrit({"version": 1, "ts": 1, "metriques": {"body_battery": 80, "pas": "beaucoup", "sommeil_s": True, "inconnue": 5,
                                                                "activite_nom": "<b>x</b>\n", "vo2max": 1e400}})
        d, _ = self.js("etat-json")
        m = d["metriques"]
        self.assertEqual(m["body_battery"], 80)
        for k in ("pas", "sommeil_s", "inconnue", "activite_nom", "vo2max"):
            self.assertNotIn(k, m)

    def test_cache_frais_pas_de_sync(self):
        import time
        self.pret()
        self.cache_ecrit({"version": 1, "ts": time.time(), "metriques": {"pas": 10}})
        d, _ = self.js("sync")
        self.assertEqual(d, {"synchronise": False, "raison": "frais", "contrat": 1})
        self.assertFalse(os.path.exists(self.log))
        d, _ = self.js("sync", "--force")
        self.assertTrue(d["synchronise"])

    def test_economie_sur_batterie(self):
        self.pret()
        bin_ = os.path.join(self.tmp, "bin")
        os.makedirs(bin_)
        sysfs = os.path.join(self.tmp, "sys", "class", "power_supply")
        for n, t, o in (("BAT0", "Battery", None), ("AC", "Mains", "0")):
            os.makedirs(os.path.join(sysfs, n))
            open(os.path.join(sysfs, n, "type"), "w").write(t)
            if o:
                open(os.path.join(sysfs, n, "online"), "w").write(o)
        pp = os.path.join(bin_, "powerprofilesctl")
        open(pp, "w").write("#!/bin/sh\necho power-saver\n")
        os.chmod(pp, 0o755)
        path = bin_ + os.pathsep + os.environ.get("PATH", "")
        d, _ = self.js("sync", PATH=path, NC_SYSFS=os.path.join(self.tmp, "sys"))
        self.assertEqual(d["raison"], "economie")
        self.assertFalse(os.path.exists(self.log))
        d, _ = self.js("sync", "--force", PATH=path, NC_SYSFS=os.path.join(self.tmp, "sys"))
        self.assertTrue(d["synchronise"])


class TestCatalogueEtReglages(Base):
    def test_ids_egalite_stricte(self):
        for i in ("body", "b", "", "body_battery ", "BODY_BATTERY", "stress2", "../stress"):
            d, r = self.js("widgets", "activer", i)
            self.assertEqual(d["erreur"], "id_inconnu", i)
            self.assertEqual(r.returncode, 2)
        self.assertFalse(os.path.exists(os.path.join(self.garmin, "widgets.json")))

    def test_catalogue_onze_dont_cinq_par_defaut(self):
        d, _ = self.js("etat-json")
        cat = d["widgets_catalogue"]
        self.assertEqual(len(cat), 11)
        self.assertEqual(sum(1 for w in cat if w["defaut"]), 5)
        self.assertEqual(len(d["widgets_actifs"]), 5)
        self.assertTrue(d["non_officiel"])

    def test_widgets_actions(self):
        d, _ = self.js("widgets", "activer", "vfc")
        self.assertIn("vfc", d["widgets_actifs"])
        d, _ = self.js("widgets", "monter", "vfc")
        self.assertEqual(d["widgets_actifs"][-2], "vfc")
        d, _ = self.js("widgets", "desactiver", "vfc")
        self.assertNotIn("vfc", d["widgets_actifs"])
        self.assertEqual(self.js("widgets", "tout")[0]["widgets_actifs"].__len__(), 11)
        self.assertEqual(len(self.js("widgets", "defaut")[0]["widgets_actifs"]), 5)

    def test_widgets_fichier_hostile_donne_defaut(self):
        os.makedirs(self.garmin, mode=0o700)
        with open(os.path.join(self.garmin, "widgets.json"), "w") as f:
            json.dump({"actifs": ["body_battery", "bod"]}, f)
        d, _ = self.js("etat-json")
        self.assertEqual(len(d["widgets_actifs"]), 5)

    def test_inactif_ne_lance_rien(self):
        self.pret()
        self.reglages(GARMIN_ACTIF="non")
        d, _ = self.js("etat-json")
        self.assertFalse(d["actif"])
        self.assertEqual(d["metriques"], {})
        for cmd in (("sync", "--force"), ("widgets", "tout"), ("hydratation", "+250"), ("demo", "oui")):
            d, r = self.js(*cmd)
            self.assertEqual(d["erreur"], "inactif")
        self.assertFalse(os.path.exists(self.log))
        self.assertFalse(os.path.exists(self.cache))

    def test_hydratation(self):
        self.assertEqual(self.js("hydratation", "+250")[0]["hydratation_ml"], 250)
        self.assertEqual(self.js("hydratation", "+500")[0]["hydratation_ml"], 750)
        self.assertEqual(self.js("etat-json")[0]["metriques"]["hydratation_ml"], 750)
        self.assertEqual(self.js("hydratation", "reset")[0]["hydratation_ml"], 0)
        self.assertEqual(self.js("hydratation", "+999")[0]["erreur"], "usage")

    def test_demo_sans_reseau(self):
        d, _ = self.js("demo", "oui")
        self.assertTrue(d["demo"])
        e, _ = self.js("etat-json")
        self.assertTrue(e["pret"])
        self.assertIn("body_battery", e["metriques"])
        self.assertEqual(self.js("sync", "--force")[0]["demo"], True)
        self.assertFalse(os.path.exists(self.log))

    def test_resume(self):
        self.pret()
        os.makedirs(os.path.dirname(self.cache), exist_ok=True)
        import time
        with open(self.cache, "w") as f:
            json.dump({"version": 1, "ts": time.time(), "metriques": {"body_battery": 80, "sommeil_s": 27000, "pas": 8000}}, f)
        os.chmod(self.cache, 0o600)
        self.assertEqual(self.nc("resume").stdout.strip(), "Body Battery 80, sleep 7 h 30, 8000 steps")
        self.assertEqual(self.nc("resume", NC_PARTAGE_ACTIF="1").stdout, "")
        open(os.path.join(self.run_dir, "nc-partage-actif"), "w").close()
        self.assertEqual(self.nc("resume").stdout, "")
        os.unlink(os.path.join(self.run_dir, "nc-partage-actif"))
        self.reglages(GARMIN_ACTIF="non")
        self.assertEqual(self.nc("resume").stdout, "")


class TestInstaller(Base):
    def test_installer_avec_faux_pip(self):
        bin_ = os.path.join(self.tmp, "fbin")
        os.makedirs(bin_)
        # faux python3 : « -m venv DIR » fabrique un faux venv dont le pip journalise ses arguments
        py = os.path.join(bin_, "python3")
        open(py, "w").write('''#!/bin/sh
case "$1" in
  -c) echo 3.12 ;;
  -m) d="$3"; mkdir -p "$d/bin"
      printf '#!/bin/sh\\nexit 0\\n' > "$d/bin/python"; chmod +x "$d/bin/python"
      printf '#!/bin/sh\\necho "$@" > "%s"\\n' "$PIPLOG" > "$d/bin/pip"; chmod +x "$d/bin/pip" ;;
esac
''')
        os.chmod(py, 0o755)
        piplog = os.path.join(self.tmp, "pip.log")
        req = os.path.join(self.tmp, "req.txt")
        open(req, "w").write("x==1 --hash=sha256:00\n")
        r = self.nc("installer", PATH=bin_ + os.pathsep + os.environ["PATH"], PIPLOG=piplog, NC_GARMIN_REQUIREMENTS=req, GARMINTOKENS="x")
        self.assertEqual(json.loads(r.stdout.strip().splitlines()[-1]), {"installe": True, "contrat": 1}, r.stdout + r.stderr)
        args = open(piplog).read()
        for a in ("--require-hashes", "--no-deps", "--only-binary=:all:", req):
            self.assertIn(a, args)

    def test_python_trop_vieux_pour_installer(self):
        bin_ = os.path.join(self.tmp, "fbin")
        os.makedirs(bin_)
        py = os.path.join(bin_, "python3")
        open(py, "w").write("#!/bin/sh\necho 3.11\n")
        os.chmod(py, 0o755)
        d, _ = self.js("installer", PATH=bin_ + os.pathsep + os.environ["PATH"])
        self.assertEqual(d["erreur"], "pas_de_python")
        self.assertFalse(os.path.exists(self.venv))

    def test_requirements_epingle_avec_hachages(self):
        txt = open(os.path.join(REPO, "home", ".local", "share", "nc", "garmin-requirements.txt")).read()
        self.assertIn("garminconnect==0.3.20", txt)
        self.assertNotIn("garth", txt)
        self.assertIn("--hash=sha256:", txt)


if __name__ == "__main__":
    unittest.main()

"""Un octet qui n'est pas de l'UTF-8 (0xff) dans reglages.conf ne fait planter aucun lecteur Python : chaque script
charge ses fonctions de lecture dans un HOME temporaire (faux outils, pas de réseau) et les appelle. Et nc-sauvegarde
prend le verrou de nc-reglages (reglages.conf.lock) pour remplacer reglages.conf à la restauration."""
import fcntl
import io
import os
import re
import subprocess
import sys
import tarfile
import tempfile
import time
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
BIN = REPO / "home/.local/bin"
SERVEUR = REPO / "home/.local/share/nc-jarvis/server"

SCRIPTS = [BIN / n for n in (
    "nc-aide", "nc-aide-config", "nc-alertes", "nc-anim", "nc-apps", "nc-assistant", "nc-bt-appel", "nc-chromium",
    "nc-claude", "nc-conso", "nc-diag", "nc-dictee", "nc-dock", "nc-firefox", "nc-ia", "nc-icones", "nc-jarvis",
    "nc-keys", "nc-logiciels", "nc-memoire", "nc-meteo", "nc-navigateurs", "nc-noeud", "nc-panne", "nc-pouls",
    "nc-raccourci", "nc-reglages", "nc-rtx-veille", "nc-sauvegarde", "nc-session", "nc-theme-sync",
    "nc-wallpaper-colors")] + [SERVEUR / "nc_engines.py"]

# Charge le script sans l'exécuter comme programme, puis appelle ses fonctions de lecture des réglages.
HARNAIS = r"""
import importlib.machinery, importlib.util, inspect, sys
chemin = sys.argv[1]
spec = importlib.util.spec_from_loader("mod_essai", importlib.machinery.SourceFileLoader("mod_essai", chemin))
mod = importlib.util.module_from_spec(spec)
sys.modules["mod_essai"] = mod
spec.loader.exec_module(mod)
for nom in ("_langue", "langue", "reglage", "reglages", "reglage_nc", "ia_coupee", "halo_sur_batterie", "dossier_fonds", "signature"):
    f = getattr(mod, nom, None)
    if not callable(f):
        continue
    try:
        n = sum(1 for p in inspect.signature(f).parameters.values() if p.default is p.empty)
    except (TypeError, ValueError):
        continue
    try:
        f(*(["LANGUE"] * n))
    except UnicodeError:
        raise
    except Exception:
        pass            # autre échec (ici sans importance) : seul un UnicodeError compte
print("ok")
"""


class Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="nc-lecteurs-")
        self.addCleanup(self._tmp.cleanup)
        self.r = Path(self._tmp.name)
        self.home = self.r / "home/user"
        (self.home / ".config/nc").mkdir(parents=True)
        (self.home / "faux-bin").mkdir()
        self.env = {
            "HOME": str(self.home), "PATH": str(self.home / "faux-bin") + ":/usr/bin:/bin",
            "XDG_CONFIG_HOME": str(self.home / ".config"), "XDG_CACHE_HOME": str(self.home / ".cache"),
            "XDG_DATA_HOME": str(self.home / ".local/share"), "XDG_STATE_HOME": str(self.home / ".local/state"),
            "XDG_RUNTIME_DIR": str(self.r / "run"), "TMPDIR": str(self.r), "LANG": "C.UTF-8",
        }
        (self.r / "run").mkdir()


class TestOctetInvalide(Base):
    def test_aucun_lecteur_ne_plante(self):
        (self.home / ".config/nc/reglages.conf").write_bytes(b'IA_MODE="aucune"\nMETEO_VILLE=Caf\xff\nLANGUE=fr\nHALO_BATTERIE=oui\n')
        for s in SCRIPTS:
            with self.subTest(script=s.name):
                p = subprocess.run([sys.executable, "-I", "-c", HARNAIS, str(s)], env=self.env, cwd=self.r,
                                   capture_output=True, text=True, timeout=60)
                self.assertNotIn("UnicodeDecodeError", p.stderr)
                self.assertNotIn("Traceback", p.stderr, p.stderr[-800:])
                self.assertEqual(p.returncode, 0, p.stderr[-800:])

    def test_aucune_lecture_stricte_restante(self):
        """Filet : toute ligne qui ouvre reglages.conf en lecture le fait avec errors=."""
        for s in SCRIPTS:
            for n, l in enumerate(s.read_text(encoding="utf-8").splitlines(), 1):
                if "reglages.conf" in l and re.search(r"read_text\(|open\(", l) and "errors=" not in l and '"w"' not in l:
                    self.fail(f"{s.name}:{n} lit reglages.conf sans errors= : {l.strip()}")


class TestVerrouSauvegarde(Base):
    def archive(self):
        chemin = self.r / "sauvegarde.tar.gz"
        with tarfile.open(chemin, "w:gz") as t:
            donnees = b'LANGUE="en"\n'
            m = tarfile.TarInfo(".config/nc/reglages.conf")
            m.size = len(donnees)
            m.mode = 0o644
            t.addfile(m, io.BytesIO(donnees))
        return chemin

    def test_statique(self):
        src = (BIN / "nc-sauvegarde").read_text(encoding="utf-8")
        self.assertIn("fcntl.flock(fd, fcntl.LOCK_EX)", src)
        self.assertIn('complet + ".lock"', src)
        self.assertIn("verrou_reglages(complet) if nom == REGLAGES", src)

    def test_la_restauration_attend_le_verrou(self):
        conf = self.home / ".config/nc/reglages.conf"
        conf.write_text('LANGUE="fr"\n')
        (self.home / ".local/bin").mkdir(parents=True)
        (self.home / ".local/bin/nc-reglages").write_text("#!/bin/sh\nexit 0\n")
        (self.home / ".local/bin/nc-reglages").chmod(0o755)
        fd = os.open(str(conf) + ".lock", os.O_RDWR | os.O_CREAT, 0o600)
        self.addCleanup(lambda: os.close(fd) if fd >= 0 else None)
        fcntl.flock(fd, fcntl.LOCK_EX)
        env = dict(self.env, NC_LANGUE="fr")
        p = subprocess.Popen([sys.executable, "-I", str(BIN / "nc-sauvegarde"), "restaurer", str(self.archive())],
                             env=env, cwd=self.r, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            time.sleep(1.5)
            self.assertIsNone(p.poll(), "la restauration n'a pas attendu le verrou")
            self.assertEqual(conf.read_text(), 'LANGUE="fr"\n')       # rien remplacé pendant que le verrou est tenu
            fcntl.flock(fd, fcntl.LOCK_UN)
            out, err = p.communicate(timeout=30)
        finally:
            if p.poll() is None:
                p.kill()
                p.communicate()
        self.assertEqual(p.returncode, 0, out + err)
        self.assertIn("LANGUE", conf.read_text())


if __name__ == "__main__":
    unittest.main()

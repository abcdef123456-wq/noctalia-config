"""nc-fenetre : plus de repli sur /tmp (sans XDG_RUNTIME_DIR, une phrase et code 1), attente du verrou bornée à 5 s, message
« masquage impossible » traduit. nc-term-logo : le dossier temporaire du dessin s'en va même si le script est arrêté
en plein calcul. HOME temporaire, faux hyprctl et faux magick."""
import fcntl
import json
import os
from pathlib import Path
import signal
import subprocess
import tempfile
import time
import unittest

REPO = Path(__file__).resolve().parents[1]
BIN = REPO / "home/.local/bin"


class Base(unittest.TestCase):
    def setUp(self):
        d = tempfile.TemporaryDirectory(prefix="nc-fenetre-logo-")
        self.addCleanup(d.cleanup)
        self.d = Path(d.name)
        self.home = self.d / "home"
        (self.home / ".local/bin").mkdir(parents=True)
        for nom in ("nc-langue",):
            (self.home / ".local/bin" / nom).symlink_to(BIN / nom)
        self.run_dir = self.d / "run"
        self.run_dir.mkdir(mode=0o700)
        self.faux = self.d / "faux"
        self.faux.mkdir()
        self.env = dict(os.environ, HOME=str(self.home), XDG_CONFIG_HOME=str(self.home / ".config"),
                        XDG_CACHE_HOME=str(self.home / ".cache"), XDG_RUNTIME_DIR=str(self.run_dir),
                        TMPDIR=str(self.d), NC_LANGUE="fr", PATH=f"{self.faux}:{os.environ['PATH']}")

    def script(self, nom, corps):
        p = self.faux / nom
        p.write_text("#!/bin/sh\n" + corps + "\n")
        p.chmod(0o755)


class Fenetre(Base):
    def lancer(self, *args, env=None, timeout=30):
        return subprocess.run(["bash", str(BIN / "nc-fenetre"), *args], env=env or self.env, capture_output=True,
                              text=True, timeout=timeout, stdin=subprocess.DEVNULL)

    def test_sans_dossier_de_session_pas_de_repli_sur_tmp(self):
        self.script("hyprctl", "exit 0")
        env = {k: v for k, v in self.env.items() if k != "XDG_RUNTIME_DIR"}
        r = self.lancer("tout-masquer", env=env)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("XDG_RUNTIME_DIR", r.stderr)

    def test_aide_sans_dossier_de_session(self):
        env = {k: v for k, v in self.env.items() if k != "XDG_RUNTIME_DIR"}
        r = self.lancer("--help", env=env)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_verrou_pris_attente_bornee(self):
        self.script("hyprctl", "exit 0")
        with open(self.run_dir / "nc-reduites.lock", "w") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            t0 = time.monotonic()
            r = self.lancer("tout-masquer", timeout=60)
            duree = time.monotonic() - t0
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertGreater(duree, 4, "attend un peu")
        self.assertLess(duree, 20, "mais pas pour toujours")

    def test_masquage_impossible_traduit(self):
        self.script("hyprctl", '''case "$1" in clients) echo '[{"address":"0x1","workspace":{"name":"1","id":1}}]' ;; esac''')
        lot = json.dumps([{"address": "0x1", "x": 0, "y": 0, "w": 10, "h": 10, "ws": 1}])
        for langue, attendu in (("en", "cannot hide"), ("fr", "masquage impossible")):
            r = self.lancer("reduire-lot", lot, env=dict(self.env, NC_LANGUE=langue))
            self.assertIn(attendu, r.stderr, r.stdout + r.stderr)


class TermLogo(Base):
    def test_dossier_temporaire_nettoye_a_l_arret(self):
        logos = self.home / ".local/share/nc/logos"
        logos.mkdir(parents=True)
        (logos / "arch.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"/>')
        pid_fichier = self.d / "pid-magick"
        self.script("magick", f'echo $$ > "{pid_fichier}"; exec sleep 30')
        tmp = self.d / "tmp-logo"
        tmp.mkdir()
        env = dict(self.env, TMPDIR=str(tmp), NC_DESSIN=str(self.d / "dessin.png"))
        p = subprocess.Popen(["bash", str(BIN / "nc-term-logo"), "dessin", "arch"], env=env, stdin=subprocess.DEVNULL,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        enfant = None
        try:
            for _ in range(100):
                if pid_fichier.exists() and pid_fichier.read_text().strip():
                    enfant = int(pid_fichier.read_text().strip())
                    break
                time.sleep(0.1)
            self.assertIsNotNone(enfant, "le calcul du dessin a démarré")
            self.assertTrue(list(tmp.iterdir()), "le dossier temporaire existe pendant le calcul")
            p.send_signal(signal.SIGTERM)
            os.kill(enfant, signal.SIGKILL)           # le faux magick que ce test a lancé (pid noté par lui)
            p.wait(timeout=20)
        finally:
            if p.poll() is None:
                p.kill()
                p.wait()
        self.assertEqual(list(tmp.iterdir()), [], "plus rien dans le dossier temporaire")


if __name__ == "__main__":
    unittest.main()

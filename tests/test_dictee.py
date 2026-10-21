"""nc-dictee : enregistrement, transcription par le serveur, erreurs. Faux enregistreur et faux serveur, HOME isolé."""
import ast
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
from pathlib import Path
import subprocess
import tempfile
import threading
import time
import unittest

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "home/.local/bin/nc-dictee"
CLE = "cle-de-test-0123456789"

# Faux parec : écrit un « WAV » de la taille demandée (NC_TEST_OCTETS) puis attend d'être arrêté
FAUX_PAREC = """#!/usr/bin/env python3
import os,signal,sys,time
fichier=sys.argv[-1]
n=int(os.environ.get('NC_TEST_OCTETS','4000'))
if n:open(fichier,'wb').write(b'RIFF'+bytes(n-4))
signal.signal(signal.SIGTERM,lambda *a:sys.exit(0))
while True:time.sleep(.05)
"""


class Serveur(BaseHTTPRequestHandler):
    recus = []
    reponse = {"success": True, "text": "  bonjour jarvis ", "engine": "test-whisper"}

    def do_POST(self):
        corps = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        Serveur.recus.append(dict(chemin=self.path, cle=self.headers.get("X-Secret-Key"), type=self.headers.get("Content-Type"), taille=len(corps)))
        if self.headers.get("X-Secret-Key") != CLE:
            self.send_response(401); self.end_headers(); return
        data = json.dumps(Serveur.reponse).encode()
        self.send_response(200); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(data))); self.end_headers()
        self.wfile.write(data)

    def log_message(self, *a):
        pass


class Dictee(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.serveur = HTTPServer(("127.0.0.1", 0), Serveur)
        threading.Thread(target=cls.serveur.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.serveur.shutdown()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        (self.home / "run").mkdir(mode=0o700)
        (self.home / "bin").mkdir()
        (self.home / "bin/parec").write_text(FAUX_PAREC)
        (self.home / "bin/parec").chmod(0o755)
        self.configurer(CLE)
        Serveur.recus = []
        Serveur.reponse = {"success": True, "text": "  bonjour jarvis ", "engine": "test-whisper"}
        self.addCleanup(lambda: self.lancer("cancel"))

    def configurer(self, cle, url=None):
        conf = self.home / ".config/nc"
        conf.mkdir(parents=True, exist_ok=True)
        f = conf / "assistant.conf"
        f.write_text('URL="%s"\nSECRET_KEY="%s"\n' % (url or "http://127.0.0.1:%d" % self.serveur.server_port, cle))
        f.chmod(0o600)

    def lancer(self, action, octets=4000):
        env = dict(HOME=str(self.home), XDG_RUNTIME_DIR=str(self.home / "run"), NC_LANGUE="fr", NC_TEST_OCTETS=str(octets),
                   PATH=str(self.home / "bin") + os.pathsep + "/usr/bin:/bin")
        r = subprocess.run([str(SCRIPT), action], env=env, capture_output=True, text=True, timeout=20)
        self.assertEqual(r.stderr, "")
        lignes = r.stdout.splitlines()
        self.assertEqual(len(lignes), 1, r.stdout)
        return r.returncode, json.loads(lignes[0])

    def test_syntaxe(self):
        ast.parse(SCRIPT.read_text())
        self.assertTrue(os.access(SCRIPT, os.X_OK))

    def test_enregistrement_puis_transcription(self):
        self.assertEqual(self.lancer("status"), (0, {"ok": True, "recording": False}))
        code, r = self.lancer("start")
        self.assertEqual((code, r["ok"], r["recording"]), (0, True, True))
        self.assertEqual(self.lancer("status"), (0, {"ok": True, "recording": True}))
        code, r = self.lancer("start")
        self.assertEqual((code, r["ok"], r["recording"]), (0, True, True), "second start : l'enregistrement continue")
        self.assertEqual(self.lancer("stop"), (0, {"ok": True, "text": "bonjour jarvis", "engine": "test-whisper"}))
        self.assertEqual(Serveur.recus, [dict(chemin="/api/transcribe", cle=CLE, type="audio/wav", taille=4000)])
        self.assertFalse((self.home / "run/nc-dictee.wav").exists(), "audio conservé après la transcription")
        self.assertEqual(self.lancer("status"), (0, {"ok": True, "recording": False}))
        self.assertEqual(self.lancer("stop"), (1, {"ok": False, "error": "Aucun enregistrement en cours."}))

    def test_micro_coupe(self):
        self.lancer("start", octets=0)
        self.assertEqual(self.lancer("stop"), (1, {"ok": False, "error": "Enregistrement vide ou micro coupé."}))
        self.assertEqual(Serveur.recus, [])

    def test_mauvaise_cle(self):
        self.configurer("mauvaise-cle")
        self.lancer("start")
        code, r = self.lancer("stop")
        self.assertEqual(code, 1)
        self.assertIn("HTTP 401", r["error"])
        self.assertNotIn("mauvaise-cle", r["error"])

    def test_serveur_arrete(self):
        self.configurer(CLE, url="http://127.0.0.1:1")
        self.lancer("start")
        code, r = self.lancer("stop")
        self.assertEqual(code, 1)
        self.assertTrue(r["error"].startswith("Transcription impossible : "), r["error"])
        self.assertFalse((self.home / "run/nc-dictee.wav").exists())

    def test_non_configure_et_annulation(self):
        (self.home / ".config/nc/assistant.conf").unlink()
        self.lancer("start")
        # Sans JARVIS ni clé d'API de transcription : le message dit quoi faire (nc-ia transcrit sinon)
        code, r = self.lancer("stop")
        self.assertEqual((code, r["ok"]), (1, False))
        self.assertIn("relie JARVIS", r["error"])
        self.assertIn("nc-ia configurer", r["error"])
        self.lancer("start")
        self.assertEqual(self.lancer("cancel"), (0, {"ok": True, "recording": False}))
        self.assertFalse((self.home / "run/nc-dictee.wav").exists())
        self.assertEqual(Serveur.recus, [])

    def test_transcription_vide(self):
        Serveur.reponse = {"success": False, "text": "", "error": "Audio trop court"}
        self.lancer("start")
        self.assertEqual(self.lancer("stop"), (1, {"ok": False, "error": "Audio trop court"}))


    # ── Dictée partout (Super + D) ──
    def ptt(self, action, reglages=""):
        b = self.home / "bin"
        for nom in ("wtype", "notify-send"):
            (b / nom).write_text('#!/bin/sh\necho "' + nom + ' $*" >> "$HOME/appels"\n'); (b / nom).chmod(0o755)
        (self.home / ".config/nc/reglages.conf").write_text(reglages)
        env = dict(HOME=str(self.home), XDG_RUNTIME_DIR=str(self.home / "run"), NC_LANGUE="fr", NC_TEST_OCTETS="4000",
                   PATH=str(b) + os.pathsep + "/usr/bin:/bin", NC_POWER_SUPPLY="secteur", NC_PROFIL="balanced", NC_IA_EN_LIGNE="1")
        return subprocess.run([str(SCRIPT), action], env=env, capture_output=True, text=True, timeout=20).returncode

    def appels(self):
        f = self.home / "appels"
        return f.read_text() if f.exists() else ""

    def test_maintenir_puis_relacher_ecrit_dans_la_fenetre(self):
        self.assertEqual(self.ptt("ptt-debut"), 0)
        time.sleep(0.6)
        self.assertEqual(self.ptt("ptt-fin"), 0)
        self.assertIn("wtype -- bonjour jarvis", self.appels())
        self.assertFalse((self.home / "run/nc-dictee-ptt.json").exists())
        self.assertFalse((self.home / "run/nc-dictee.wav").exists(), "l'audio est supprimé")

    def test_appui_bref_dictee_longue(self):
        self.ptt("ptt-debut")
        self.ptt("ptt-fin")                                   # relâché tout de suite : la dictée continue
        self.assertNotIn("wtype", self.appels())
        self.assertTrue((self.home / "run/nc-dictee-ptt.json").exists())
        self.ptt("ptt-fin")                                   # Super relâché : rien ne change
        self.assertNotIn("wtype", self.appels())
        self.assertEqual(self.ptt("ptt-debut"), 0)            # second appui : écrit
        self.assertIn("wtype -- bonjour jarvis", self.appels())

    def test_desactivee_ou_rien_en_cours(self):
        self.assertEqual(self.ptt("ptt-fin"), 0)
        self.assertEqual(self.appels(), "", "relâcher Super sans dictée ne fait rien")
        self.assertEqual(self.ptt("ptt-debut", "IA_DICTEE=non\n"), 1)
        self.assertFalse((self.home / "run/nc-dictee-ptt.json").exists())
        self.assertEqual(Serveur.recus, [])


if __name__ == "__main__":
    unittest.main()

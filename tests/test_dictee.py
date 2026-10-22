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
    def ptt(self, action, reglages="", wtype=True):
        b = self.home / "bin"
        for nom in ("wtype", "notify-send"):
            (b / nom).write_text('#!/bin/sh\necho "' + nom + ' $*" >> "$HOME/appels"\n' + ("" if wtype or nom != "wtype" else "exit 1\n"))
            (b / nom).chmod(0o755)
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
        # Les heures que note le raccourci (appui, relâchement 0,2 s après) : le test ne dépend pas de la charge (TEST-01)
        run = self.home / "run"
        self.ptt("ptt-fin")
        (run / "nc-dictee-appui").write_text("")
        appui = (run / "nc-dictee-appui").stat().st_mtime
        self.ptt("ptt-debut")
        (run / "nc-dictee-relache").write_text("")
        os.utime(run / "nc-dictee-relache", (appui + 0.2, appui + 0.2))
        self.ptt("ptt-fin")                                   # relâché tout de suite : la dictée continue
        self.assertNotIn("wtype", self.appels())
        self.assertTrue((self.home / "run/nc-dictee-ptt.json").exists())
        self.ptt("ptt-fin")                                   # Super relâché : rien ne change
        self.assertNotIn("wtype", self.appels())
        self.assertEqual(self.ptt("ptt-debut"), 0)            # second appui : écrit
        self.assertIn("wtype -- bonjour jarvis", self.appels())

    def test_duree_de_l_appui_mesuree_par_le_raccourci(self):
        """Revue DICT-03 : l'appui bref se mesurait depuis le micro prêt (~0,4 s après l'appui) : un maintien de 0,6 s
        (un seul mot) ouvrait une dictée longue. La durée est celle notée par le raccourci (appui → relâchement)."""
        run = self.home / "run"
        self.ptt("ptt-fin")
        for tenue, longue in ((0.6, False), (0.2, True)):
            (run / "appels").unlink(missing_ok=True)
            (self.home / "appels").unlink(missing_ok=True)
            (run / "nc-dictee-appui").write_text("")
            appui = (run / "nc-dictee-appui").stat().st_mtime
            self.assertEqual(self.ptt("ptt-debut"), 0)        # le micro est prêt après l'appui (Python, démarrage)
            time.sleep(max(0, appui + tenue - time.time()) + 0.05)
            (run / "nc-dictee-relache").write_text("")
            os.utime(run / "nc-dictee-relache", (appui + tenue, appui + tenue))
            self.assertEqual(self.ptt("ptt-fin"), 0)
            if longue:
                self.assertNotIn("wtype", self.appels(), "appui bref : dictée longue")
                self.assertTrue(json.loads((run / "nc-dictee-ptt.json").read_text()).get("bascule"))
                self.assertEqual(self.ptt("ptt-debut"), 0)    # second appui : écrit
            self.assertIn("wtype -- bonjour jarvis", self.appels(), f"tenue {tenue} s")

    def collage(self, liste_types, sortie_paste="", lent=False):
        """Faux wl-paste, wl-copy et hyprctl (jamais le vrai presse-papiers) : sans wtype, le texte est collé."""
        b = self.home / "bin"
        corps = {"wl-paste": ('case "$*" in *list-types*) ' + ("sleep 6; " if lent else "") + f"printf '{liste_types}';; "
                              f"*) printf '{sortie_paste}';; esac\necho \"wl-paste $*\" >> \"$HOME/appels\""),
                 "wl-copy": 'echo "wl-copy $* [$(cat | wc -c)]" >> "$HOME/appels"',
                 "hyprctl": 'echo "hyprctl $*" >> "$HOME/appels"; [ "$1" = activewindow ] && echo \'{"class": "firefox"}\''}
        for nom, c in corps.items():
            (b / nom).write_text("#!/bin/sh\n" + c + "\n"); (b / nom).chmod(0o755)

    def test_colle_et_remet_une_image(self):
        """Revue DICT-05 : une image (ou des fichiers) copiée avant la dictée était remplacée par le texte dicté."""
        self.ptt("ptt-fin")
        self.collage("image/png\\n", "PNGDATA")
        self.assertEqual(self.ptt("ptt-debut", wtype=False), 0)
        time.sleep(0.6)
        self.assertEqual(self.ptt("ptt-fin", wtype=False), 0)
        a = self.appels()
        self.assertIn("wl-paste -n -t image/png", a)
        self.assertIn("wl-copy -- bonjour jarvis", a)
        self.assertIn("send_shortcut({ mods = 'CTRL', key = 'V' })", a)
        self.assertIn("wl-copy --type image/png -- [7]", a, "l'image d'avant remise")
        self.assertLess(a.index("wl-copy -- bonjour"), a.index("--type image/png"))

    def test_collage_bloque_le_texte_n_est_pas_perdu(self):
        """Revue DICT-04 : un presse-papiers qui ne répond pas (wl-paste bloqué) faisait perdre la dictée (exception)."""
        self.ptt("ptt-fin")
        self.collage("text/plain\\n", "avant", lent=True)
        self.assertEqual(self.ptt("ptt-debut", wtype=False), 0)
        time.sleep(0.6)
        self.assertEqual(self.ptt("ptt-fin", wtype=False), 1)
        a = self.appels()
        self.assertNotIn("send_shortcut", a, "rien collé par-dessus un presse-papiers qu'on ne saurait pas remettre")
        self.assertIn("wl-copy -- bonjour jarvis", a, "le texte est copié")
        self.assertIn("Dictée (pas écrite dans la fenêtre)", a)
        f = self.home / "run/nc-dictee-derniere.txt"
        self.assertEqual(f.read_text(), "bonjour jarvis")
        self.assertEqual(f.stat().st_mode & 0o777, 0o600)

    def ptt_fond(self, action):
        b = self.home / "bin"
        env = dict(HOME=str(self.home), XDG_RUNTIME_DIR=str(self.home / "run"), NC_LANGUE="fr", NC_TEST_OCTETS="4000",
                   PATH=str(b) + os.pathsep + "/usr/bin:/bin", NC_POWER_SUPPLY="secteur", NC_PROFIL="balanced", NC_IA_EN_LIGNE="1")
        return subprocess.Popen([str(SCRIPT), action], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def test_relache_pendant_le_demarrage_du_micro(self):
        """Revue Codex DICT-01 : un relâchement arrivé pendant que le micro démarre était perdu (le micro restait ouvert)."""
        self.ptt("ptt-fin")                                   # prépare les faux programmes ; rien en cours
        etat = self.home / "run/nc-dictee-ptt.json"
        p = self.ptt_fond("ptt-debut")
        fin = time.time() + 5
        while time.time() < fin and not etat.exists():
            time.sleep(0.005)
        self.assertFalse(json.loads(etat.read_text()).get("pret"), "relâché pendant le démarrage")
        self.assertEqual(self.ptt("ptt-fin"), 0)
        p.wait(20)
        e = json.loads(etat.read_text())
        self.assertTrue(e.get("bascule"), "appui bref (relâché pendant le démarrage) : dictée longue")
        self.assertEqual(self.ptt("ptt-debut"), 0)            # second appui : écrit
        self.assertIn("wtype -- bonjour jarvis", self.appels())

    def test_relache_avant_meme_le_lancement(self):
        """Le raccourci note chaque relâchement sans dictée : un appui plus bref que le lancement de nc-dictee compte."""
        self.ptt("ptt-fin")
        (self.home / "run/nc-dictee-appui").write_text("")       # ce que fait le raccourci à l'appui…
        time.sleep(0.01)
        (self.home / "run/nc-dictee-relache").write_text("")     # … et au relâchement, avant que nc-dictee démarre
        p = self.ptt_fond("ptt-debut")
        p.wait(20)
        e = json.loads((self.home / "run/nc-dictee-ptt.json").read_text())
        self.assertTrue(e.get("bascule"))
        # Un relâchement d'avant l'appui ne compte pas
        self.ptt("ptt-debut")
        time.sleep(0.01)
        (self.home / "run/nc-dictee-appui").write_text("")
        self.assertEqual(self.ptt("ptt-debut"), 0)
        self.assertFalse(json.loads((self.home / "run/nc-dictee-ptt.json").read_text()).get("bascule"))
        r = (REPO / "home/.config/hypr/nc/raccourcis.lua").read_text()
        self.assertIn(': > "$r/nc-dictee-relache"; [ -e', r, "relâchement noté avant tout, même pendant une dictée")
        self.assertIn('nc-dictee-appui"; exec ~/.local/bin/nc-dictee ptt-debut', r)

    def test_enregistreur_mort_ne_bloque_pas(self):
        """Une dictée laissée par un nc-dictee tué (enregistreur mort) ne bloque pas l'appui suivant."""
        self.ptt("ptt-fin")
        (self.home / "run/nc-dictee-ptt.json").write_text(json.dumps({"t": time.time(), "pret": True}))
        self.assertEqual(self.ptt("ptt-debut"), 0)
        self.assertEqual(self.lancer("status"), (0, {"ok": True, "recording": True}))

    def test_ia_coupee_pendant_la_dictee_rien_ne_part(self):
        """Revue Codex DICT-02 : IA coupée pendant l'enregistrement, l'audio partait quand même vers JARVIS."""
        self.assertEqual(self.ptt("ptt-debut"), 0)
        time.sleep(0.6)
        self.assertEqual(self.ptt("ptt-fin", "IA_MODE=non\n"), 1)
        self.assertEqual(Serveur.recus, [])
        self.assertNotIn("wtype", self.appels())
        self.assertFalse((self.home / "run/nc-dictee.wav").exists(), "l'audio est supprimé sans être envoyé")

    def test_desactivee_ou_rien_en_cours(self):
        self.assertEqual(self.ptt("ptt-fin"), 0)
        self.assertEqual(self.appels(), "", "relâcher Super sans dictée ne fait rien")
        self.assertEqual(self.ptt("ptt-debut", "IA_DICTEE=non\n"), 1)
        self.assertFalse((self.home / "run/nc-dictee-ptt.json").exists())
        self.assertEqual(Serveur.recus, [])


if __name__ == "__main__":
    unittest.main()

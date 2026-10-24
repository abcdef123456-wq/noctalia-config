"""nc-dictee : enregistrement, transcription par le serveur, erreurs. Faux enregistreur et faux serveur, HOME isolé."""
import ast
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, HTTPServer
import importlib.machinery
import importlib.util
import io
import json
import os
from pathlib import Path
import signal
import subprocess
import tempfile
import threading
import time
import unittest
from unittest import mock

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
    entree = None
    reprendre = None

    def do_POST(self):
        corps = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        Serveur.recus.append(dict(chemin=self.path, cle=self.headers.get("X-Secret-Key"), type=self.headers.get("Content-Type"), taille=len(corps)))
        if self.headers.get("X-Secret-Key") != CLE:
            self.send_response(401); self.end_headers(); return
        if Serveur.entree is not None:
            Serveur.entree.set()
            Serveur.reprendre.wait(10)
        data = json.dumps(Serveur.reponse).encode()
        self.send_response(200); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(data))); self.end_headers()
        try:
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError):
            pass                            # client arrêté pendant le test de nettoyage

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
        cls.serveur.server_close()

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
        Serveur.entree = Serveur.reprendre = None
        self.addCleanup(lambda: self.lancer("cancel"))

    def configurer(self, cle, url=None):
        conf = self.home / ".config/nc"
        conf.mkdir(parents=True, exist_ok=True)
        f = conf / "assistant.conf"
        f.write_text('URL="%s"\nSECRET_KEY="%s"\n' % (url or "http://127.0.0.1:%d" % self.serveur.server_port, cle))
        f.chmod(0o600)

    def lancer(self, action, octets=4000, **langue):
        env = dict(HOME=str(self.home), XDG_RUNTIME_DIR=str(self.home / "run"), NC_LANGUE="fr", NC_TEST_OCTETS=str(octets),
                   PATH=str(self.home / "bin") + os.pathsep + "/usr/bin:/bin")
        env.update(langue)
        env = {k: v for k, v in env.items() if v is not None}
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
        self.assertEqual(Serveur.recus, [dict(chemin="/api/transcribe?language=fr", cle=CLE, type="audio/wav", taille=4000)])
        self.assertFalse((self.home / "run/nc-dictee.wav").exists(), "audio conservé après la transcription")
        self.assertEqual(self.lancer("status"), (0, {"ok": True, "recording": False}))
        self.assertEqual(self.lancer("stop"), (1, {"ok": False, "error": "Aucun enregistrement en cours."}))

    def test_langue_envoyee(self):
        # JARVIS-BIS 64523e5 transcrit en français si on ne dit rien (WHISPER_LANGUAGE="fr") : la langue part toujours
        reglages = self.home / ".config/nc/reglages.conf"
        for env, reglage, attendu in [(dict(NC_LANGUE="en", LANG="fr_FR.UTF-8"), None, "en"),
                                      (dict(NC_LANGUE=None, LANG="fr_FR.UTF-8"), 'LANGUE="en"\n', "en"),
                                      (dict(NC_LANGUE=None, LANG="de_DE.UTF-8"), None, "de"),
                                      (dict(NC_LANGUE=None, LANG="de_DE.UTF-8"), "LANGUE=auto\n", "de"),
                                      (dict(NC_LANGUE=None, LANG="C.UTF-8"), None, "auto")]:
            with self.subTest(env=env, reglage=reglage):
                if reglage:
                    reglages.write_text(reglage)
                elif reglages.exists():
                    reglages.unlink()
                Serveur.recus = []
                self.lancer("start", **env)
                self.assertEqual(self.lancer("stop", **env)[0], 0)
                self.assertEqual(Serveur.recus[0]["chemin"], "/api/transcribe?language=" + attendu)

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

    def test_nouvel_audio_preserve_pendant_une_transcription(self):
        self.lancer("start")
        Serveur.entree, Serveur.reprendre = threading.Event(), threading.Event()
        with ThreadPoolExecutor(max_workers=1) as pool:
            premiere = pool.submit(self.lancer, "stop")
            try:
                self.assertTrue(Serveur.entree.wait(5), "la première transcription a reçu son audio")
                captures = list((self.home / "run").glob("nc-dictee-transcription-*.wav"))
                self.assertEqual(len(captures), 1)
                self.assertEqual(captures[0].stat().st_mode & 0o777, 0o600)
                self.assertEqual(self.lancer("start", octets=8000)[0], 0)
            finally:
                Serveur.reprendre.set()
            self.assertEqual(premiere.result(timeout=10)[0], 0)
        audio = self.home / "run/nc-dictee.wav"
        self.assertTrue(audio.exists(), "la fin de la première transcription ne supprime pas le nouvel enregistrement")
        self.assertEqual(audio.stat().st_size, 8000)

    def test_deux_demarrages_simultanes_un_seul_micro(self):
        self.noter_micros()
        with ThreadPoolExecutor(max_workers=2) as pool:
            appels = [pool.submit(self.lancer, "start") for _ in range(2)]
            self.assertEqual([f.result(timeout=10)[0] for f in appels], [0, 0])
        self.assertEqual(len((self.home / "micros").read_text().splitlines()), 1)

    def noter_micros(self):
        p = self.home / "bin/parec"
        p.write_text(FAUX_PAREC.replace("fichier=sys.argv[-1]", 'fichier=sys.argv[-1]\nwith open(os.path.join(os.environ["HOME"], "micros"), "a") as f:f.write(str(os.getpid())+"\\n")'))
        def nettoyer_micros():
            f = self.home / "micros"
            if f.exists():
                for pid in map(int, f.read_text().splitlines()):
                    try:
                        if str(p).encode() in Path(f"/proc/{pid}/cmdline").read_bytes().split(b"\0"):
                            os.kill(pid, signal.SIGTERM)
                    except (OSError, ProcessLookupError):
                        pass
        self.addCleanup(nettoyer_micros)

    def test_stop_ia_coupee_supprime_aussi_l_audio(self):
        self.assertEqual(self.lancer("start")[0], 0)
        (self.home / ".config/nc/reglages.conf").write_text("IA_MODE=non\n")
        self.assertEqual(self.lancer("stop")[0], 1)
        self.assertEqual(Serveur.recus, [])
        self.assertFalse((self.home / "run/nc-dictee.wav").exists())
        self.assertFalse(list((self.home / "run").glob("nc-dictee-transcription-*.wav")))

    def test_signal_pendant_transcription_nettoie_la_capture(self):
        for sig in (signal.SIGTERM, signal.SIGHUP):
            with self.subTest(signal=sig):
                self.assertEqual(self.lancer("start")[0], 0)
                Serveur.entree, Serveur.reprendre = threading.Event(), threading.Event()
                p = self.ptt_fond("stop")
                try:
                    self.assertTrue(Serveur.entree.wait(5))
                    self.assertTrue(list((self.home / "run").glob("nc-dictee-transcription-*.wav")))
                    p.send_signal(sig)
                    self.assertEqual(p.wait(timeout=5), 128 + sig)
                    self.assertFalse(list((self.home / "run").glob("nc-dictee-transcription-*.wav")))
                finally:
                    Serveur.reprendre.set()
                    if p.poll() is None:
                        p.kill()
                        p.wait(timeout=5)

    def test_signal_pendant_demarrage_ne_laisse_pas_le_micro(self):
        self.noter_micros()
        p = self.ptt_fond("start")
        try:
            fin = time.monotonic() + 5
            registre = self.home / "micros"
            while not registre.exists() and time.monotonic() < fin:
                time.sleep(0.005)
            self.assertTrue(registre.exists())
            p.terminate()
            self.assertEqual(p.wait(timeout=5), 128 + signal.SIGTERM)
            self.assertFalse((self.home / "run/nc-dictee.json").exists())
            self.assertFalse((self.home / "run/nc-dictee.wav").exists())
            self.assertFalse(self.lancer("status")[1]["recording"])
        finally:
            if p.poll() is None:
                p.kill()
                p.wait(timeout=5)

    def test_anciennes_captures_orphelines_nettoyees(self):
        run = self.home / "run"
        ancien = run / "nc-dictee-transcription-99999999-ancien.wav"
        vivant = run / f"nc-dictee-transcription-{os.getpid()}-vivant.wav"
        recent = run / "nc-dictee-transcription-99999999-recent.wav"
        for f in (ancien, vivant, recent):
            f.write_bytes(b"RIFF")
        vieux = time.time() - 601
        for f in (ancien, vivant):
            os.utime(f, (vieux, vieux))
        self.assertEqual(self.lancer("start")[0], 0)
        self.assertFalse(ancien.exists())
        self.assertTrue(vivant.exists(), "ne pas toucher à une transcription encore active")
        self.assertTrue(recent.exists())


    # ── Dictée partout (Super + D) ──
    def ptt(self, action, reglages="", wtype=True):
        b = self.home / "bin"
        # Le faux wtype note ses arguments, puis entre crochets ce qu'il lit sur son entrée standard (A1-R7)
        (b / "wtype").write_text('#!/bin/sh\necho "wtype $* [$(cat)]" >> "$HOME/appels"\n' + ("" if wtype else "exit 1\n"))
        (b / "notify-send").write_text('#!/bin/sh\necho "notify-send $*" >> "$HOME/appels"\n')
        for nom in ("wtype", "notify-send"):
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
        self.assertIn("wtype - [bonjour jarvis]", self.appels())
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
        self.assertIn("wtype - [bonjour jarvis]", self.appels())

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
            self.assertIn("wtype - [bonjour jarvis]", self.appels(), f"tenue {tenue} s")

    def collage(self, liste_types, sortie_paste="", lent=False):
        """Faux wl-paste, wl-copy et hyprctl (jamais le vrai presse-papiers) : sans wtype, le texte est collé."""
        b = self.home / "bin"
        corps = {"wl-paste": ('case "$*" in *list-types*) ' + ("sleep 6; " if lent else "") + f"printf '{liste_types}';; "
                              f"*) printf '{sortie_paste}';; esac\necho \"wl-paste $*\" >> \"$HOME/appels\""),
                 "wl-copy": 'echo "wl-copy $* [$(cat)]" >> "$HOME/appels"',
                 "hyprctl": 'echo "hyprctl $*" >> "$HOME/appels"; [ "$1" = activewindow ] && echo \'{"class": "firefox"}\'; exit 0'}
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
        self.assertIn("wl-copy --type text/plain;charset=utf-8 [bonjour jarvis]", a)
        self.assertIn("send_shortcut({ mods = 'CTRL', key = 'V' })", a)
        self.assertIn("wl-copy --type image/png -- [PNGDATA]", a, "l'image d'avant remise")
        self.assertLess(a.index("[bonjour jarvis]"), a.index("--type image/png"))

    def test_collage_refuse_restaure_et_ne_dit_pas_ecrit(self):
        self.ptt("ptt-fin")
        self.collage("image/png\\n", "PNGDATA")
        h = self.home / "bin/hyprctl"
        h.write_text(h.read_text().replace("exit 0", "[ \"$1\" = dispatch ] && exit 1; exit 0"))
        self.assertEqual(self.ptt("ptt-debut", wtype=False), 0)
        time.sleep(0.6)
        self.assertEqual(self.ptt("ptt-fin", wtype=False), 1)
        a = self.appels()
        self.assertIn("wl-copy --type image/png -- [PNGDATA]", a, "le collage refusé ne doit pas perdre l'image précédente")
        self.assertIn("Dictée (pas écrite dans la fenêtre)", a)
        self.assertNotIn("✓ Écrit", a)
        self.assertEqual((self.home / "run/nc-dictee-derniere.txt").read_text(), "bonjour jarvis")

    def test_copie_refusee_ne_declenche_pas_de_collage(self):
        self.ptt("ptt-fin")
        self.collage("text/plain\\n", "avant")
        c = self.home / "bin/wl-copy"
        c.write_text(c.read_text() + '\nexit 1\n')
        self.assertEqual(self.ptt("ptt-debut", wtype=False), 0)
        time.sleep(0.6)
        self.assertEqual(self.ptt("ptt-fin", wtype=False), 1)
        a = self.appels()
        self.assertNotIn("send_shortcut", a)
        self.assertNotIn("✓ Écrit", a)
        self.assertIn("Gardé dans", a, "ne pas annoncer Copié si wl-copy refuse aussi le repli")

    def test_collage_avertissement_code_zero_pas_ecrit(self):
        self.ptt("ptt-fin")
        self.collage("text/plain\\n", "avant")
        h = self.home / "bin/hyprctl"
        h.write_text(h.read_text().replace("exit 0", 'if [ "$1" = dispatch ]; then echo "warning: send_shortcut: window not found"; fi; exit 0'))
        self.assertEqual(self.ptt("ptt-debut", wtype=False), 0)
        time.sleep(0.6)
        self.assertEqual(self.ptt("ptt-fin", wtype=False), 1)
        self.assertNotIn("✓ Écrit", self.appels())
        self.assertIn("Dictée (pas écrite dans la fenêtre)", self.appels())

    def test_texte_dicte_jamais_en_argument(self):
        """A1-R7 : le texte dicté passait en argument de wtype et wl-copy, donc lisible par tous dans /proc/*/cmdline.
        Il passe par l'entrée standard : par wtype, par le collage (wtype refusé), puis par le repli (collage refusé)."""
        b = self.home / "bin"
        espion = ('#!/bin/sh\nfor a in "$@"; do printf "%s\\n" "$a" >> "$HOME/arguments"; done\n'
                  'echo "{nom} $* [$(cat)]" >> "$HOME/appels"\n{fin}\n')

        def essai(wtype_ok, collage_ok):
            for f in ("appels", "arguments"):
                (self.home / f).unlink(missing_ok=True)
            self.ptt("ptt-fin")
            self.collage("text/plain\\n", "avant")
            if not collage_ok:
                h = b / "hyprctl"
                h.write_text(h.read_text().replace("exit 0", "[ \"$1\" = dispatch ] && exit 1; exit 0"))
            self.ptt("ptt-debut", wtype=wtype_ok)
            for nom, fin in (("wtype", "" if wtype_ok else "exit 1"), ("wl-copy", "")):
                (b / nom).write_text(espion.format(nom=nom, fin=fin)); (b / nom).chmod(0o755)
            time.sleep(0.6)
            # Pas self.ptt ici : il réécrirait le faux wtype par-dessus l'espion
            env = dict(HOME=str(self.home), XDG_RUNTIME_DIR=str(self.home / "run"), NC_LANGUE="fr", NC_TEST_OCTETS="4000",
                       PATH=str(b) + os.pathsep + "/usr/bin:/bin", NC_POWER_SUPPLY="secteur", NC_PROFIL="balanced",
                       NC_IA_EN_LIGNE="1")
            subprocess.run([str(SCRIPT), "ptt-fin"], env=env, capture_output=True, text=True, timeout=20)
            args = (self.home / "arguments").read_text() if (self.home / "arguments").exists() else ""
            return args, self.appels()

        args, a = essai(True, True)
        self.assertIn("wtype - [bonjour jarvis]", a)
        self.assertNotIn("bonjour", args)
        args, a = essai(False, True)
        self.assertIn("wl-copy --type text/plain;charset=utf-8 [bonjour jarvis]", a, "collé par l'entrée standard")
        self.assertIn("✓ Écrit", a)
        self.assertNotIn("bonjour", args)
        args, a = essai(False, False)
        self.assertIn("Dictée (pas écrite dans la fenêtre)", a)
        self.assertEqual(a.count("wl-copy --type text/plain;charset=utf-8 [bonjour jarvis]"), 2, "collage puis repli")
        self.assertNotIn("bonjour", args)

    def test_presse_papiers_vide_remis_apres_collage(self):
        self.ptt("ptt-fin")
        self.collage("")
        self.assertEqual(self.ptt("ptt-debut", wtype=False), 0)
        time.sleep(0.6)
        self.assertEqual(self.ptt("ptt-fin", wtype=False), 0)
        self.assertIn("wl-copy --clear", self.appels(), "un presse-papiers initialement vide est vidé après le collage")

    def test_restauration_refusee_apres_collage_ne_recopie_pas(self):
        self.ptt("ptt-fin")
        self.collage("text/plain\\n", "avant")
        c = self.home / "bin/wl-copy"
        # Seule la remise du presse-papiers d'avant a « -- » en troisième argument (wl-copy --type <type> --)
        c.write_text(c.read_text() + '\n[ "$3" = -- ] && exit 1\nexit 0\n')
        self.assertEqual(self.ptt("ptt-debut", wtype=False), 0)
        time.sleep(0.6)
        self.assertEqual(self.ptt("ptt-fin", wtype=False), 0)
        a = self.appels()
        self.assertEqual(a.count("wl-copy --type text/plain;charset=utf-8 [bonjour jarvis]"), 1)
        self.assertNotIn("Dictée (pas écrite dans la fenêtre)", a)
        self.assertIn("presse-papiers d'avant non remis", a)

    def test_collage_bloque_le_texte_n_est_pas_perdu(self):
        """Revue DICT-04 : un presse-papiers qui ne répond pas (wl-paste bloqué) faisait perdre la dictée (exception)."""
        self.ptt("ptt-fin")
        self.collage("text/plain\\n", "avant", lent=True)
        self.assertEqual(self.ptt("ptt-debut", wtype=False), 0)
        time.sleep(0.6)
        self.assertEqual(self.ptt("ptt-fin", wtype=False), 1)
        a = self.appels()
        self.assertNotIn("send_shortcut", a, "rien collé par-dessus un presse-papiers qu'on ne saurait pas remettre")
        self.assertIn("wl-copy --type text/plain;charset=utf-8 [bonjour jarvis]", a, "le texte est copié")
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
        self.assertIn("wtype - [bonjour jarvis]", self.appels())

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

    def test_relachement_perdu_l_appui_suivant_ecrit(self):
        """Issue #2 : un relâchement perdu laissait le micro ouvert, et chaque appui suivant était ignoré sans rien dire."""
        self.assertEqual(self.ptt("ptt-debut"), 0)
        time.sleep(0.6)
        self.assertEqual(self.ptt("ptt-debut"), 0)               # le relâchement n'est jamais arrivé
        self.assertIn("wtype - [bonjour jarvis]", self.appels())
        self.assertFalse((self.home / "run/nc-dictee-ptt.json").exists())

    def test_message_avec_le_raccourci_choisi(self):
        (self.home / ".config/nc/raccourcis.conf").write_text("change\t64:code:40\tSUPER + S\t(Dicter)\n")
        run = self.home / "run"
        self.ptt("ptt-fin")
        (run / "nc-dictee-appui").write_text("")
        appui = (run / "nc-dictee-appui").stat().st_mtime
        self.ptt("ptt-debut")
        (run / "nc-dictee-relache").write_text("")
        os.utime(run / "nc-dictee-relache", (appui + 0.2, appui + 0.2))
        self.ptt("ptt-fin")                                       # appui bref : dictée longue
        self.assertIn("Super + S pour écrire", self.appels())
        self.assertNotIn("Super + D", self.appels())

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

    def test_annuler_une_dictee_longue_permet_de_recommencer(self):
        self.assertEqual(self.ptt("ptt-debut"), 0)
        f = self.home / "run/nc-dictee-ptt.json"
        etat = json.loads(f.read_text())
        f.write_text(json.dumps(dict(etat, bascule=True)))
        self.assertEqual(self.lancer("cancel")[0], 0)
        self.assertFalse(f.exists(), "cancel remet aussi l'état du raccourci à zéro")
        self.assertEqual(self.ptt("ptt-debut"), 0)
        self.assertTrue(self.lancer("status")[1]["recording"])

    def test_annulation_pendant_le_demarrage_ne_ressuscite_pas(self):
        self.ptt("ptt-fin")
        f = self.home / "run/nc-dictee-ptt.json"
        demarrage = self.ptt_fond("ptt-debut")
        try:
            fin = time.monotonic() + 5
            while not f.exists() and time.monotonic() < fin:
                time.sleep(0.005)
            self.assertTrue(f.exists())
            self.assertEqual(self.lancer("cancel")[0], 0)
            demarrage.wait(timeout=5)
            self.assertFalse(f.exists())
            self.assertFalse(self.lancer("status")[1]["recording"])
            self.assertFalse((self.home / "run/nc-dictee.wav").exists())
        finally:
            if demarrage.poll() is None:
                demarrage.kill()
                demarrage.wait(timeout=5)

    def test_deux_relachements_une_seule_transcription(self):
        self.assertEqual(self.ptt("ptt-debut"), 0)
        time.sleep(0.6)
        fils = [self.ptt_fond("ptt-fin") for _ in range(2)]
        try:
            self.assertEqual([p.wait(timeout=10) for p in fils], [0, 0])
        finally:
            for p in fils:
                if p.poll() is None:
                    p.kill()
                    p.wait(timeout=5)
        self.assertEqual(len(Serveur.recus), 1)
        self.assertEqual(self.appels().count("wtype - [bonjour jarvis]"), 1)




class ArretAtomique(unittest.TestCase):
    def test_annulation_ne_supprime_pas_la_capture_suivante(self):
        with tempfile.TemporaryDirectory(prefix="nc-dictee-annulation-") as d:
            home = Path(d)
            with mock.patch.dict(os.environ, HOME=d, XDG_RUNTIME_DIR=d), mock.patch.object(Path, "home", return_value=home):
                l = importlib.machinery.SourceFileLoader("nc_dictee_annulation", str(SCRIPT))
                m = importlib.util.module_from_spec(importlib.util.spec_from_loader(l.name, l))
                l.exec_module(m)
            m.AUDIO.write_bytes(b"capture precedente")
            m.ETAT.write_text(json.dumps({"pid": 99999999}))

            class RepriseMicro(m.Verrou):
                def __exit__(self, *a):
                    super().__exit__(*a)
                    if self.chemin.name == "nc-dictee-micro.lock":
                        # La requête suivante commence dès que le micro lui est rendu, avant que cancel ne termine.
                        m.AUDIO.write_bytes(b"nouvelle capture")

            with mock.patch.object(m, "Verrou", RepriseMicro), mock.patch.object(m, "client"), \
                    mock.patch.object(__import__("sys"), "argv", [str(SCRIPT), "cancel"]), \
                    mock.patch("signal.signal"), mock.patch("os.umask"), \
                    mock.patch.object(__import__("sys"), "stdout", io.StringIO()):
                self.assertEqual(m.main(), 0)
            self.assertEqual(m.AUDIO.read_bytes(), b"nouvelle capture")


@unittest.skipUnless(__import__("shutil").which("lua"), "Lua requis")
class RaccourciDictee(unittest.TestCase):
    """Issue #2 : avec un autre raccourci (nc-raccourci : Super + S), le relâchement restait attendu sur D."""
    def binds(self, conf):
        import tempfile
        src = (REPO / "home/.config/hypr/nc/raccourcis.lua").read_text()
        debut = src[src.index('local SUPER    = "SUPER"'):src.index("-- Taille logique")]
        dictee = src[src.index("-- Dictée partout (nc-dictee)"):src.index('touche(SUPER .. " + code:26"')]
        harnais = ('nc = { reglage = function(_, d) return d end, t = function(fr) return fr end }\n'
                   'hl = { bind = function(t, _, o) print("BIND " .. t .. ((o and o.release) and " release" or "")) end,'
                   ' dsp = { exec_cmd = function(c) return c end } }\n' + debut + dictee)
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / ".config/nc").mkdir(parents=True)
            (Path(d) / ".config/nc/raccourcis.conf").write_text(conf)
            r = subprocess.run(["lua", "-"], input=harnais, text=True, capture_output=True, timeout=10, env=dict(os.environ, HOME=d))
        self.assertEqual(r.returncode, 0, r.stderr)
        return [l[5:] for l in r.stdout.splitlines() if l.startswith("BIND ")]

    def test_relachement_sur_le_raccourci_choisi(self):
        self.assertIn("SUPER + code:40 release", self.binds(""))
        b = self.binds("change\t64:code:40\tSUPER + S\t(Dicter)\n")
        self.assertEqual([x for x in b if not x.startswith("SUPER + Super_")], ["SUPER + S", "SUPER + S release"])
        self.assertEqual(self.binds("aucun\t64:code:40\n"), [], "dictée désactivée : rien, ni appui ni relâchement")

if __name__ == "__main__":
    unittest.main()

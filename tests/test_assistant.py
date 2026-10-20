"""Contrat HTTP et intégration de l'assistant : serveur local, faux Hyprland, HOME temporaire."""
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
import pty
from pathlib import Path
import select
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import types
import unittest
from unittest.mock import patch
import urllib.request
import uuid
import warnings

REPO = Path(__file__).resolve().parents[1]
BIN = REPO / "home/.local/bin"


def charger(nom):
    m = types.ModuleType(nom)
    m.__file__ = str(BIN / nom)
    exec(compile((BIN / nom).read_text(), m.__file__, "exec"), m.__dict__)
    return m


class Serveur(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        self.do_POST()

    def do_POST(self):
        corps = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        self.server.recus.append((self.path, self.command, self.headers.get("X-Secret-Key"), json.loads(corps) if corps else None))
        if self.server.bloquer:
            self.server.entree.set()
            self.server.sortie.wait(8)
        code, reponse = self.server.reponse
        self.send_response(code)
        if code == 302:
            self.send_header("Location", "/secret-must-not-arrive-here")
        self.end_headers()
        try:
            self.wfile.write(reponse)
        except BrokenPipeError:
            pass


class Assistant(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.bin = self.root / ".local/bin"
        self.bin.mkdir(parents=True)
        self.run = self.root / "run"
        self.run.mkdir(mode=0o700)
        for nom in ("nc-assistant", "nc-claude", "nc-demander"):
            shutil.copy2(BIN / nom, self.bin / nom)
        hypr = self.bin / "hyprctl"
        hypr.write_text('#!/bin/sh\nprintf "[]\\n"\n')
        hypr.chmod(0o755)
        self.env = dict(os.environ, HOME=str(self.root), XDG_RUNTIME_DIR=str(self.run), NC_LANGUE="en",
                        PATH=str(self.bin) + ":/usr/bin:/bin")
        for cle in ("NC_ILE_SANS", "NC_CLAUDE_SYNC"):
            self.env.pop(cle, None)
        self.patch = patch.dict(os.environ, self.env, clear=True)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.m = charger("nc-assistant")
        self.m.CONF = self.root / ".config/nc/assistant.conf"
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Serveur)
        self.server.recus = []
        self.server.reponse = (200, json.dumps({"success": True, "output": "Bonjour\n$ echo ok", "runner_alive": True}).encode())
        self.server.bloquer = False
        self.server.entree, self.server.sortie = threading.Event(), threading.Event()
        thread = threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
        thread.start()
        self.addCleanup(self.arreter)
        self.c = dict(URL=f"http://127.0.0.1:{self.server.server_port}/gateway", SECRET_KEY="test-private-key",
                      USER_ID="test-user", TIMEOUT="2")
        self.m.sauvegarder(self.c)

    def arreter(self):
        self.server.sortie.set()
        self.server.shutdown()
        self.server.server_close()

    def cli(self, *args, nom="nc-assistant", input=None):
        return subprocess.run([sys.executable, str(self.bin / nom), *args], input=input, env=self.env,
                              text=True, capture_output=True, timeout=10)

    def etat(self):
        return json.loads((self.run / "nc-claude/etat.json").read_text())

    def settings(self, texte):
        (self.m.CONF.parent / "reglages.conf").write_text(texte)

    def test_configuration_private_atomic_and_roundtrip(self):
        self.assertEqual(self.m.CONF.stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.m.configuration()["SECRET_KEY"], self.c["SECRET_KEY"])
        avant = self.m.CONF.read_bytes()
        with patch.object(self.m.os, "replace", side_effect=OSError("disk error")):
            with self.assertRaises(OSError):
                self.m.sauvegarder(dict(self.c, SECRET_KEY="replacement"))
        self.assertEqual(self.m.CONF.read_bytes(), avant)
        self.assertFalse(list(self.m.CONF.parent.glob(".assistant-*")))

    def test_island_stdin_preserves_text_without_duplicate_coucou_tracking(self):
        sid = uuid.uuid4().hex
        question = 'Multiligne\n"quotes" $(false) <b>texte</b>'
        for _ in range(2):
            r = self.cli("requete-ile", input=json.dumps(dict(session_id=sid, question=question)) + "\n")
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(json.loads(r.stdout), dict(ok=True, text="Bonjour\n$ echo ok", truncated=False))
            self.assertEqual(self.server.recus[-1][3]["prompt"], question)
            self.assertFalse((self.run / "nc-claude/etat.json").exists())

    def test_island_never_waits_for_an_unavailable_activity_hook(self):
        # Un hook bloqué (verrou Coucou, terminal…) ne doit même pas être lancé par l'île.
        (self.bin / "nc-claude").write_text('raise RuntimeError("Unexpected Coucou hook")\n')
        for question in ("bonjour", "/help"):
            r = self.cli("requete-ile", input=json.dumps(dict(session_id="a" * 32, question=question)))
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertTrue(json.loads(r.stdout)["ok"])
            self.assertNotIn("tracking", r.stderr.lower())
        self.assertEqual(len(self.server.recus), 1)  # /help reste une commande locale, sans modèle.

    def test_request_timings_do_not_repeat_the_question_or_change_stdout(self):
        for option in ("--mesurer", "--timings"):
            r = self.cli("demander", "--flux", option, "question privée")
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(json.loads(r.stdout), {"t": "Bonjour\n$ echo ok"})
            mesures = json.loads(r.stderr)["timings_ms"]
            self.assertEqual(set(mesures), {"request_ms", "activity_ms", "total_ms"})
            self.assertTrue(all(isinstance(x, (int, float)) and x >= 0 for x in mesures.values()))
            self.assertGreaterEqual(mesures["total_ms"] + 0.01, mesures["request_ms"] + mesures["activity_ms"])
            for prive in ("question privée", self.c["SECRET_KEY"], self.c["URL"]):
                self.assertNotIn(prive, r.stderr)
        self.assertEqual(len(self.server.recus), 2)

    def test_request_timings_are_available_on_failure_without_retry(self):
        self.server.reponse = (503, b'private backend error')
        r = self.cli("demander", "--mesurer", "question privée")
        self.assertEqual(r.returncode, 1)
        mesures = json.loads(r.stderr.splitlines()[0])["timings_ms"]
        self.assertIn("request_ms", mesures)
        self.assertIn("total_ms", mesures)
        self.assertEqual(len(self.server.recus), 1)
        self.assertFalse(self.etat()["sessions"])
        self.assertNotIn("private backend error", r.stderr)

    def test_island_rejects_bad_input_without_network_and_reports_errors_as_json(self):
        for entree in ('[]', '{}', 'not json', json.dumps(dict(session_id="bad", question="hello")),
                       json.dumps(dict(session_id="a" * 32, question="x" * 8001)), "x" * 65537):
            r = self.cli("requete-ile", input=entree)
            self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
            self.assertFalse(json.loads(r.stdout)["ok"])
        self.assertFalse(self.server.recus)
        self.m.CONF.unlink()
        r = self.cli("requete-ile", input=json.dumps(dict(session_id="a" * 32, question="hello")))
        self.assertIn("configurer", json.loads(r.stdout)["error"])

    def test_island_bounds_response_and_does_not_create_activity_on_failure(self):
        self.server.reponse = (200, json.dumps(dict(output="x" * 16001)).encode())
        entree = json.dumps(dict(session_id="a" * 32, question="hello"))
        r = self.cli("requete-ile", input=entree)
        self.assertEqual(len(json.loads(r.stdout)["text"]), 16000)
        self.assertTrue(json.loads(r.stdout)["truncated"])
        self.server.reponse = (403, b'private data')
        r = self.cli("requete-ile", input=entree)
        self.assertEqual(r.returncode, 1)
        self.assertFalse(json.loads(r.stdout)["ok"])
        self.assertNotIn("private data", r.stdout + r.stderr)
        self.assertFalse((self.run / "nc-claude/etat.json").exists())

    def test_invalid_configuration_does_not_replace_key(self):
        avant = self.m.CONF.read_bytes()
        for champs in ({"URL": "ftp://example.test"}, {"URL": "https://user:password@example.test"},
                       {"URL": "https://example.test?token=private"}, {"URL": "http://example.test/\x00"},
                       {"SECRET_KEY": "bad\nheader"},
                       {"TIMEOUT": "NaN"}, {"TIMEOUT": "0"}, {"USER_ID": ""}):
            with self.subTest(champs=champs), self.assertRaises(self.m.Erreur):
                self.m.sauvegarder(dict(self.c, **champs))
        self.assertEqual(self.m.CONF.read_bytes(), avant)

    def test_no_network_for_local_status_and_no_key_in_output(self):
        r = self.cli("etat", "--local")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(r.stdout), {"configured": True, "checked": False})
        self.assertEqual(self.server.recus, [])
        self.assertNotIn(self.c["SECRET_KEY"], r.stdout + r.stderr)
        self.m.CONF.chmod(0o644)
        self.assertNotEqual(self.cli("etat").returncode, 0)
        self.assertEqual(self.server.recus, [])

    def test_http_request_and_coucou_lifecycle_preserve_other_agents(self):
        p = self.run / "nc-claude"
        p.mkdir(mode=0o700)
        initial = {"sessions": {"codex-existing": {"agent": "codex", "maj": time.time(), "etat": "travail"}},
                   "demandes": {"permission": {"session": "codex-existing"}}}
        (p / "etat.json").write_text(json.dumps(initial))
        r = self.cli("demander", "test $(false) 'quotes'")
        self.assertEqual(r.returncode, 0, r.stderr)
        path, methode, cle, corps = self.server.recus[0]
        self.assertEqual((path, methode, cle), ("/gateway/api/ask", "POST", self.c["SECRET_KEY"]))
        self.assertEqual(corps, dict(prompt="test $(false) 'quotes'", platform="desktop", user_id="test-user", continue_session=True))
        d = self.etat()
        self.assertEqual(d["sessions"]["codex-existing"], initial["sessions"]["codex-existing"])
        self.assertEqual(d["demandes"], initial["demandes"])
        s = next(v for k, v in d["sessions"].items() if k.startswith("assistant-"))
        self.assertEqual((s["agent"], s["etat"], s["terminal"], s["ecrire"]), ("assistant", "fini", 0, False))
        self.assertNotIn(self.c["SECRET_KEY"], json.dumps(d))

    def test_status_uses_get_and_reports_offline_runner(self):
        self.assertEqual(self.cli("etat").returncode, 0)
        self.assertEqual(self.server.recus[0][1], "GET")
        self.server.reponse = (200, b'{"runner_alive":false}')
        r = self.cli("etat")
        self.assertEqual(r.returncode, 1)
        self.assertFalse(json.loads(r.stdout)["online"])

    def test_api_errors_and_redirect_do_not_leave_busy_state_or_leak_key(self):
        for code, corps in [(403, b'private error'), (200, b'not JSON'), (200, b'[]'),
                            (200, b'{"success":false,"error":"private error"}'), (200, b'{"output":""}'),
                            (302, b'')]:
            with self.subTest(code=code, corps=corps):
                self.server.reponse = (code, corps)
                r = self.cli("demander", "--flux", "test")
                self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
                self.assertTrue(json.loads(r.stdout)["t"])
                self.assertNotIn("private error", r.stdout + r.stderr)
                self.assertNotIn(self.c["SECRET_KEY"], r.stdout + r.stderr)
                self.assertFalse(self.etat()["sessions"])
        self.assertFalse(any(x[0].endswith("secret-must-not-arrive-here") for x in self.server.recus))

    def test_response_size_and_network_timeout(self):
        self.m.MAX_RESPONSE = 16
        with self.assertRaises(self.m.Erreur):
            self.m.api(self.m.configuration(), "/api/status")
        with patch.object(urllib.request.OpenerDirector, "open", side_effect=TimeoutError):
            with self.assertRaises(self.m.Erreur) as e:
                self.m.api(self.m.configuration(), "/api/status")
        self.assertIn("in time", str(e.exception))

    def test_conflicting_requests_are_refused_before_contacting_server(self):
        self.server.bloquer = True
        p = subprocess.Popen([sys.executable, str(self.bin / "nc-assistant"), "demander", "first"],
                             env=self.env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            self.assertTrue(self.server.entree.wait(5))
            r = self.cli("demander", "second")
            self.assertEqual(r.returncode, 1)
            self.assertIn("already running", r.stderr)
            self.assertEqual(len(self.server.recus), 1)
        finally:
            self.server.sortie.set()
            out, err = p.communicate(timeout=10)
        self.assertEqual(p.returncode, 0, out + err)

    def test_chat_reuses_local_session_and_removes_it_on_exit(self):
        self.server.reponse = (200, json.dumps({"success": True, "output": "Formule : $\\frac{x^2}{\\alpha_0} \\leq \\sqrt{y}$ et `code $x^2$`", "runner_alive": True}).encode())
        r = self.cli("chat", input="first\nsecond\nexit\n")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("(x²)/(α₀) ≤ √y", r.stdout)
        self.assertIn("`code $x^2$`", r.stdout)
        self.assertEqual(len(self.server.recus), 2)
        self.assertFalse(self.etat()["sessions"])

    def test_termination_cleans_activity(self):
        self.server.bloquer = True
        p = subprocess.Popen([sys.executable, str(self.bin / "nc-assistant"), "demander", "test"],
                             env=self.env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            self.assertTrue(self.server.entree.wait(5))
            self.assertEqual(next(iter(self.etat()["sessions"].values()))["etat"], "travail")
            p.terminate()
            p.communicate(timeout=5)
            self.assertEqual(p.returncode, 130)
            self.assertFalse(self.etat()["sessions"])
        finally:
            if p.poll() is None:
                p.kill()
                p.communicate()
            self.server.sortie.set()

    def test_assistant_setting_and_independent_sessions_with_concurrent_agents(self):
        self.settings("CLAUDE_ILE=non\nASSISTANT_ILE=oui\n")
        def evenement(n):
            ident = uuid.uuid4().hex
            r = self.cli("assistant", "debut", nom="nc-claude", input=json.dumps(dict(session_id=ident, chat=False)))
            self.assertEqual(r.returncode, 0, r.stderr)
        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(evenement, range(8)))
        self.assertEqual(len(self.etat()["sessions"]), 8)
        self.settings("ASSISTANT_ILE=non\n")
        r = self.cli("demander", "test")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(len(self.etat()["sessions"]), 8)

    def test_spotlight_selection_and_json_contract(self):
        self.settings("SPOTLIGHT_IA=assistant\n")
        self.assertEqual(self.cli("--ia", nom="nc-demander").stdout.strip(), "Assistant")
        r = self.cli("--flux", "test", nom="nc-demander")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(r.stdout)["t"], "Bonjour\n$ echo ok")
        self.assertIn("Hyprland", self.server.recus[0][3]["prompt"])
        self.m.CONF.unlink()
        r = self.cli("--flux", "test", nom="nc-demander")
        self.assertEqual(r.returncode, 1)
        self.assertIn("configurer", json.loads(r.stdout)["t"])

    def test_unconfigured_assistant_is_not_auto_selected(self):
        m = charger("nc-demander")
        m.HOME = str(self.root)
        with patch.object(m.shutil, "which", return_value=None):
            self.assertEqual(m.ia(), "assistant")
            self.m.CONF.unlink()
            self.assertEqual(m.ia(), "")

    def test_briefing_and_notification_are_arguments_without_shell(self):
        malveillant = '$(touch should-never-exist) " <b>text</b>'
        self.server.reponse = (200, json.dumps({"output": malveillant}).encode())
        outil = self.bin / "notify-send"
        outil.write_text('#!/usr/bin/env python3\nimport json,os,sys\nfrom pathlib import Path\nPath(os.environ["HOME"],"notification.json").write_text(json.dumps(sys.argv[1:]))\n')
        outil.chmod(0o755)
        r = self.cli("briefing")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn(malveillant, r.stdout)
        self.assertEqual(self.server.recus[0][0], "/gateway/api/briefing")
        self.assertEqual(self.server.recus[0][3], {"force_refresh": False})
        args = json.loads((self.root / "notification.json").read_text())
        self.assertIn("&lt;b&gt;text&lt;/b&gt;", args[-1])
        self.assertFalse((self.root / "should-never-exist").exists())

    def test_server_output_cannot_control_terminal(self):
        self.assertEqual(self.m.texte_sortie({"output": "\x1b]52;c;dGVzdA==\x07\x1b[31mhello\x1b[0m\x07"}), "hello")

    def test_kitty_launch_preserves_question_as_one_argument(self):
        with patch.object(self.m.subprocess, "Popen") as p:
            self.m.ouvrir(["quotes ' and $(false)"])
        args = p.call_args.args[0]
        self.assertEqual(args[-3:], ["chat", "--", "quotes ' and $(false)"])
        self.assertFalse(p.call_args.kwargs.get("shell", False))

    def test_runtime_failure_is_json_for_spotlight(self):
        cible = self.run / "nc-assistant"
        cible.symlink_to(self.root)
        r = self.cli("demander", "--flux", "test")
        self.assertEqual(r.returncode, 1)
        self.assertIn("private", json.loads(r.stdout)["t"])
        self.assertEqual(self.server.recus, [])

    def test_private_host_detection(self):
        for url in ("http://localhost:8000", "http://192.168.1.28:8000",
                    "http://10.0.0.5:8000", "http://172.16.4.2:8000",
                    "https://assistant.local", "http://[::1]:8000"):
            with self.subTest(url=url):
                self.assertTrue(self.m.hote_prive(url))
        for url in ("https://assistant.example.test", "https://trycloudflare.com",
                    "https://100.64.0.1", "https://mon-pi.tailnet.ts.net"):
            with self.subTest(url=url):
                self.assertFalse(self.m.hote_prive(url))

    def test_verifier_json_without_configuration_and_invalid_status(self):
        self.server.reponse = (200, b'{}')
        r = self.cli("verifier", "--json")
        self.assertEqual(r.returncode, 1)
        self.assertFalse(json.loads(r.stdout)["online"])
        self.m.CONF.unlink()
        for cmd in ("verifier", "check", "diagnostic"):
            r = self.cli(cmd, "--json")
            self.assertEqual(r.returncode, 1)
            self.assertFalse(json.loads(r.stdout)["configured"])

    def test_verifier_metadata_and_network_errors_are_safe(self):
        self.server.reponse = (200, json.dumps(dict(online=True, version="\x1b[31m" + self.c["SECRET_KEY"],
                                                   gateway=dict(public_url=self.c["SECRET_KEY"]))).encode())
        r = self.cli("verifier", "--json")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn(self.c["SECRET_KEY"], r.stdout + r.stderr)
        self.assertNotIn("\x1b", json.loads(r.stdout)["version"])
        import socket
        import ssl
        import urllib.error
        for raison, attendu in ((socket.gaierror(), "DNS"), (ssl.SSLError(), "TLS"),
                                 (TimeoutError(), "in time"), (ConnectionRefusedError(), "refused")):
            with patch.object(urllib.request.OpenerDirector, "open", side_effect=urllib.error.URLError(raison)):
                with self.assertRaises(self.m.Erreur) as e:
                    self.m.api(self.m.configuration(), "/api/status")
            self.assertIn(attendu, str(e.exception))

    def test_verifier_reports_online_private_url_without_key(self):
        r = self.cli("verifier")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("Connection OK", r.stdout)
        self.assertIn("local/private", r.stdout)
        self.assertNotIn(self.c["SECRET_KEY"], r.stdout + r.stderr)

        r = self.cli("verifier", "--json")
        self.assertEqual(r.returncode, 0, r.stderr)
        data = json.loads(r.stdout)
        self.assertTrue(data["online"])
        self.assertTrue(data["private"])
        self.assertEqual(data["url"], self.c["URL"])
        self.assertNotIn(self.c["SECRET_KEY"], r.stdout + r.stderr)

    def test_verifier_explains_auth_and_missing_route(self):
        self.server.reponse = (401, b"private error")
        r = self.cli("verifier")
        self.assertEqual(r.returncode, 1)
        self.assertIn("rejected the key", r.stderr)
        self.assertNotIn("private error", r.stdout + r.stderr)
        self.assertNotIn(self.c["SECRET_KEY"], r.stdout + r.stderr)

        self.server.reponse = (404, b"")
        r = self.cli("verifier", "--json")
        self.assertEqual(r.returncode, 1)
        self.assertIn("404", json.loads(r.stdout)["error"])

    def test_verifier_reports_offline_runner(self):
        self.server.reponse = (200, b'{"online": false}')
        r = self.cli("verifier", "--json")
        self.assertEqual(r.returncode, 1)
        data = json.loads(r.stdout)
        self.assertFalse(data["online"])
        self.assertTrue(data["runner_alive"] is False)

    def test_status_error_explains_private_url_without_leaking_key(self):
        self.server.reponse = (500, b"private backend detail")
        r = self.cli("etat")
        self.assertEqual(r.returncode, 1)
        data = json.loads(r.stdout)
        self.assertFalse(data["online"])
        self.assertTrue(data["private"])
        self.assertIn("tunnel", data["hint"])
        self.assertNotIn(self.c["SECRET_KEY"], r.stdout + r.stderr)
        self.assertNotIn("private backend detail", r.stdout + r.stderr)


    def installer_rappels_factices(self):
        for name, destination in [('systemd-run','timer.json'),('notify-send','notification.json')]:
            p=self.bin/name
            p.write_text('#!/usr/bin/env python3\nimport json,os,sys\nfrom pathlib import Path\nPath(os.environ["HOME"],'+repr(destination)+').write_text(json.dumps(sys.argv[1:]))\nsys.exit(int(os.environ.get("NC_TEST_FAIL_'+name.upper().replace('-','_')+'","0")))\n')
            p.chmod(0o755)

    def test_desktop_reminder_needs_no_backend_keeps_text_private_and_notifies_without_shell(self):
        self.installer_rappels_factices();self.m.CONF.unlink()
        msg='$(touch should-never-exist) <b>pain</b> " test $HOME %h'
        r=self.cli('requete-ile',input=json.dumps(dict(session_id='a'*32,question='/rappel 15m '+msg))+'\n')
        self.assertEqual(r.returncode,0,r.stdout+r.stderr)
        self.assertTrue(json.loads(r.stdout)['ok']);self.assertFalse(self.server.recus)
        args=json.loads((self.root/'timer.json').read_text())
        self.assertTrue(any(a.startswith('--on-calendar=') and a.endswith(' UTC') for a in args));self.assertIn('--user',args)
        self.assertNotIn(msg,repr(args))
        ident=args[-1];self.assertEqual(args[-2],'rappel-notifier')
        payload=self.run/'nc-assistant'/('rappel-'+ident+'.json')
        self.assertEqual(payload.stat().st_mode&0o777,0o600)
        self.assertEqual(json.loads(payload.read_text())['message'],msg)
        r=self.cli('rappel-notifier',ident)
        self.assertEqual(r.returncode,0,r.stderr)
        notice=json.loads((self.root/'notification.json').read_text())
        self.assertIn('--app-name=JARVIS',notice);self.assertIn('&lt;b&gt;pain&lt;/b&gt;',notice[-1])
        self.assertIn('$(touch should-never-exist)',notice[-1]);self.assertFalse(payload.exists())
        self.assertFalse((self.root/'should-never-exist').exists())
        self.assertFalse(self.server.recus)

    def test_reminders_choose_mobile_platforms_and_report_partial_failure(self):
        self.installer_rappels_factices()
        for platform in ('telegram','discord'):
            r=self.cli('demander','/rappel '+platform+' 2h message à rappeler')
            self.assertEqual(r.returncode,0,r.stderr)
            self.assertEqual(self.server.recus[-1][0],'/gateway/api/reminders')
            self.assertEqual(self.server.recus[-1][3],dict(platform=platform,delay='2h',message='message à rappeler'))
        self.server.reponse=(401,b'private error')
        r=self.cli('demander','/rappel bureau,telegram 15m pain')
        self.assertEqual(r.returncode,0,r.stderr)
        self.assertIn('desktop reminder scheduled',r.stdout);self.assertIn('telegram reminder not created',r.stdout)
        self.assertNotIn('private error',r.stdout+r.stderr)
        self.assertEqual(len(list((self.run/'nc-assistant').glob('rappel-*.json'))),1)

    def test_reminder_failures_keep_no_false_timer_and_delivery_failure_keeps_payload(self):
        self.installer_rappels_factices()
        self.env['NC_TEST_FAIL_SYSTEMD_RUN']='1'
        r=self.cli('demander','/rappel bureau 15m pain')
        self.assertIn('No desktop reminder created',r.stdout)
        self.assertFalse(list((self.run/'nc-assistant').glob('rappel-*.json')))
        self.env.pop('NC_TEST_FAIL_SYSTEMD_RUN')
        r=self.cli('demander','/rappel bureau,desktop 15m pain')
        self.assertEqual(r.returncode,0,r.stderr)
        payloads=list((self.run/'nc-assistant').glob('rappel-*.json'));self.assertEqual(len(payloads),1)
        ident=json.loads((self.root/'timer.json').read_text())[-1]
        self.env['NC_TEST_FAIL_NOTIFY_SEND']='1'
        r=self.cli('rappel-notifier',ident)
        self.assertNotEqual(r.returncode,0);self.assertTrue(payloads[0].exists())
        self.assertFalse(self.server.recus)

    def test_invalid_reminders_do_not_schedule_or_contact_server(self):
        self.installer_rappels_factices()
        for command in ('/rappel','/rappel 0s pain','/rappel matrix 15m pain','/rappel 999999999d pain','/rappel bureau 15m','/rappel 1s '+('x'*4001)):
            with self.subTest(command=command[:40]):
                r=self.cli('demander',command)
                self.assertNotEqual(r.returncode,0,r.stdout+r.stderr)
        self.assertFalse((self.root/'timer.json').exists());self.assertFalse(self.server.recus)
        r=self.cli('rappel-notifier','../invalid')
        self.assertNotEqual(r.returncode,0)


class InstallationPortable(unittest.TestCase):
    @unittest.skipUnless(shutil.which("lua"), "Lua requis pour le lanceur de repli")
    def test_fallback_launcher_keeps_question_during_async_app_refresh(self):
        script = r'''
local callbacks, launched, closed = {}, nil, false
noctalia = {
 getenv = function() return "en" end, expandPath = function(p) return p end,
 readFile = function() return "" end, pluginDataDir = function() return nil end,
 outputs = function() return {} end, focusedOutputName = function() return nil end,
 fileExists = function() return true end,
 string = { trim = function(s) return s:match("^%s*(.-)%s*$") end },
 json = { decode = function() return {} end },
 runAsync = function(args, callback)
  if type(args) == "table" and args[2] == "ouvrir" then launched = args
  elseif callback then table.insert(callbacks, callback) end
 end,
}
panel = { close = function() closed = true end, setNeedsFrameTick = function() end }
dofile(arg[1])
render = function() end
onOpen("? a 'quote' and $(false)")
for _, f in ipairs(callbacks) do f({exitCode=0,stdout="[]"}) end
onKey("Return", true)
assert(closed and launched and #launched == 3)
assert(launched[1] == "~/.local/bin/nc-assistant" and launched[2] == "ouvrir")
assert(launched[3] == "a 'quote' and $(false)")
'''
        with tempfile.TemporaryDirectory() as d:
            harness = Path(d) / "launcher.lua"
            harness.write_text(script)
            r = subprocess.run(["lua", str(harness), str(REPO / "home/.local/share/noctalia/plugins/nc-launcher/panel.luau")],
                               text=True, capture_output=True, timeout=5)
            self.assertEqual(r.returncode, 0, r.stderr)

    def test_copy_pass_preserves_secret_and_installs_client_on_all_families(self):
        script = (REPO / "install.sh").read_text()
        copie = script[script.index('copied=0; same=0; hypr_changed=0'):script.index('ok "$(t "$copied fichier(s)')]
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            depot = root / "repo/home"
            fichiers = [".local/bin/nc-assistant", ".config/quickshell/nc-ile/LogoAssistant.qml",
                        ".local/bin/nc-jarvis", ".local/share/nc-jarvis/deployer.py", ".local/share/nc-jarvis/actions.json",
                        ".local/share/nc-jarvis/server/nc_gateway.py", ".local/share/nc-jarvis/server/nc_management.py",
                        ".local/share/nc-jarvis/server/nc_runner.py", ".local/share/nc-jarvis/server/nc_engines.py",
                        ".config/quickshell/nc-ile/AssistantReglages.qml",
                        ".config/quickshell/nc-ile/AssistantCommande.qml", ".config/quickshell/nc-ile/AssistantOrbe.qml",
                        ".config/quickshell/nc-ile/Jarvis.qml", ".config/quickshell/nc-ile/JarvisEtat.qml",
                        ".config/quickshell/nc-ile/JarvisChamp.qml", ".config/quickshell/nc-ile/JarvisBouton.qml",
                        ".config/quickshell/nc-ile/JarvisResultat.qml",
                        ".config/quickshell/nc-ile/Assistant.qml", ".config/quickshell/nc-ile/AssistantEtat.qml",
                        ".config/quickshell/nc-ile/assets/assistant-animation.png", ".config/quickshell/nc-ile/assets/jarvis-animation.png"]
            for rel in fichiers:
                cible = depot / rel
                cible.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(REPO / "home" / rel, cible)
            (depot / ".config/nc").mkdir(parents=True)
            (depot / ".config/nc/assistant.conf").write_text("SHOULD NOT REPLACE")
            for famille in ("arch", "fedora", "debian", "suse", "other"):
                with self.subTest(famille=famille):
                    home = root / famille
                    conf = home / ".config/nc/assistant.conf"
                    conf.parent.mkdir(parents=True)
                    conf.write_text("PERSONAL SECRET")
                    conf.chmod(0o600)
                    bk = root / (famille + "-backup")
                    bk.mkdir()
                    prelude = 'tmp="$HOME/tmp"\nbackup() { return 42; }\n'
                    env = dict(os.environ, HOME=str(home), REPO=str(root / "repo"), BK=str(bk), FAMILY=famille)
                    for cle in ("MON", "KBL", "KBO", "BROWSER", "LCX", "LCY1", "LCY2", "LCY3", "LCY4", "LCY5", "LCY6",
                                "DISTRO_LOGO", "POLKIT", "QT_STYLE", "ICON_THEME", "ILE_CENTRE", "NOTIF_NOCTALIA",
                                "NOTIF_WIDGET", "PLUGIN_ILE"):
                        env[cle] = "test"
                    for _ in range(2):
                        r = subprocess.run(["bash", "-euc", prelude + copie], env=env, capture_output=True, text=True)
                        self.assertEqual(r.returncode, 0, r.stderr)
                        self.assertEqual(conf.read_text(), "PERSONAL SECRET")
                        self.assertEqual(conf.stat().st_mode & 0o777, 0o600)
                        self.assertTrue(os.access(home / ".local/bin/nc-assistant", os.X_OK))
                        for rel in fichiers:
                            self.assertEqual((home / rel).read_bytes(), (depot / rel).read_bytes())


@unittest.skipUnless(shutil.which("qs"), "Quickshell requis pour le logo hors écran")
class LogoAssistant(unittest.TestCase):
    def test_logo_animates_stops_when_hidden_or_disabled_and_unloads_for_other_agents(self):
        qml = '''import QtQuick
import QtQuick.Window
import Quickshell
ShellRoot {
 property var logo:null; property int etape:0
 function sprite(item) {
  if(item.objectName==="nc-assistant-logo") return item
  for(var i=0;i<item.children.length;i++){var s=sprite(item.children[i]);if(s)return s}
  return null
 }
 Window {id:w;visible:true;width:64;height:64;color:"#17171f"}
 Component.onCompleted: {
  var c=Qt.createComponent("Etincelle.qml")
  if(c.status!==Component.Ready){console.error(c.errorString());Qt.exit(2);return}
  logo=c.createObject(w.contentItem,{taille:64,agent:"assistant",tourne:true})
 }
 Timer {interval:240;running:true;repeat:true;onTriggered:{
  var s= sprite(logo)
  if(etape===0){if(!s||!s.running||s.currentFrame===0){Qt.exit(3);return};logo.tourne=false}
  else if(etape===1){if(s.running||s.currentFrame!==0){Qt.exit(4);return};logo.tourne=true;logo.visible=false}
  else if(etape===2){if(s.running||s.currentFrame!==0){Qt.exit(5);return};logo.visible=true}
  else if(etape===3){if(!s.running||s.currentFrame===0){Qt.exit(6);return};Reglages.effets="aucun"}
  else if(etape===4){if(s.running||s.currentFrame!==0){Qt.exit(7);return};logo.agent="claude"}
  else if(etape===5){if(s){Qt.exit(8);return};console.log("ASSISTANT_LOGO_LIFECYCLE_OK");Qt.quit()}
  etape++
 }}
 Timer {interval:2400;running:true;onTriggered:Qt.exit(9)}
}'''
        with tempfile.TemporaryDirectory(prefix="nc-logo-test-") as d:
            root = Path(d)
            (root / "runtime").mkdir(mode=0o700)
            (root / "assets").mkdir()
            src = REPO / "home/.config/quickshell/nc-ile"
            for nom in ("Etincelle.qml", "LogoAssistant.qml", "assets/assistant-animation.png"):
                shutil.copy2(src / nom, root / nom)
            (root / "Agents.qml").write_text('pragma Singleton\nimport QtQuick\nQtObject {property var ias: ({claude:{couleur:"#d97757"},assistant:{couleur:"#10b981"}})}')
            (root / "Reglages.qml").write_text('pragma Singleton\nimport QtQuick\nQtObject {property string effets:"tous";function val(k,d){return k==="EFFETS"?effets:d}}')
            (root / "qmldir").write_text('singleton Agents 1.0 Agents.qml\nsingleton Reglages 1.0 Reglages.qml\n'
                                         'LogoAssistant 1.0 LogoAssistant.qml\nEtincelle 1.0 Etincelle.qml\n')
            (root / "shell.qml").write_text(qml)
            env = dict(os.environ, HOME=d, QT_QPA_PLATFORM="offscreen", QT_QUICK_BACKEND="software",
                       XDG_RUNTIME_DIR=str(root / "runtime"), XDG_CACHE_HOME=str(root / "cache"))
            env.pop("WAYLAND_DISPLAY", None)
            r = subprocess.run(["qs", "--no-color", "-p", str(root / "shell.qml")], env=env,
                               capture_output=True, text=True, timeout=5)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("ASSISTANT_LOGO_LIFECYCLE_OK", r.stdout + r.stderr)


class ReglagesAssistant(unittest.TestCase):
    def test_settings_exposes_remote_connection_test(self):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", ResourceWarning)
            m = charger("nc-reglages")
        e = m.Ecran.__new__(m.Ecran)
        e.sec = m.SECTIONS.index("Agents IA (coucou)")
        items = e.items()
        self.assertEqual(items[0]["action"], "configurer")
        self.assertEqual(items[1]["action"], "verifier")
        with patch.object(m.subprocess, "run") as run:
            run.return_value = unittest.mock.Mock(
                returncode=0, stdout="Connection OK — gateway v1.0.0, 12 ms.\n", stderr="")
            code, message = m.verifier_assistant()
        self.assertEqual(code, 0)
        self.assertIn("Connection OK", message)
        self.assertEqual(run.call_args.args[0][-1], "verifier")

        with patch.object(m.subprocess, "run") as run:
            run.return_value = unittest.mock.Mock(
                returncode=1, stdout="", stderr="detail\nServer rejected the key\n")
            code, message = m.verifier_assistant()
        self.assertEqual(code, 1)
        self.assertEqual(message, "Server rejected the key")

    def test_settings_action_available_and_terminal_restored_after_cancellation(self):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", ResourceWarning)  # lectures de matériel préexistantes dans nc-reglages
            m = charger("nc-reglages")
        e = m.Ecran.__new__(m.Ecran)
        e.sec = m.SECTIONS.index("Agents IA (coucou)")
        item = e.items()[0]
        self.assertEqual(item["genre"], "assistant")
        self.assertTrue(e.selectionnable(item))
        e.e = unittest.mock.Mock()
        with patch.object(m, "configurer_assistant", side_effect=KeyboardInterrupt), \
                patch.object(m.curses, "def_prog_mode"), patch.object(m.curses, "endwin"), \
                patch.object(m.curses, "reset_prog_mode") as reset, patch.object(m.curses, "flushinp"):
            e.assistant()
        self.assertTrue(e.msg_err)
        reset.assert_called_once()
        e.e.refresh.assert_called_once()

    def test_settings_configures_in_terminal_without_echoing_or_storing_key_in_settings(self):
        self.verifier_configuration_terminal(tui=False)

    def test_settings_screen_opens_configuration_and_returns_to_menu(self):
        self.verifier_configuration_terminal(tui=True)

    def verifier_configuration_terminal(self, tui):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            bindir = root / ".local/bin"
            bindir.mkdir(parents=True)
            for nom in ("nc-assistant", "nc-reglages"):
                shutil.copy2(BIN / nom, bindir / nom)
            settings = root / ".config/nc/reglages.conf"
            settings.parent.mkdir(parents=True)
            settings.write_text("SPOTLIGHT_IA=assistant\nASSISTANT_ILE=non\n")
            original = settings.read_bytes()
            env = dict(os.environ, HOME=d, NC_LANGUE="en", USER="test-user", TERM="xterm")
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", ResourceWarning)
                m = charger("nc-reglages")
            pid, fd = pty.fork()
            if pid == 0:
                args = [] if tui else ["assistant"]
                os.execve(sys.executable, [sys.executable, str(bindir / "nc-reglages"), *args], env)
            contenu, stade, status = b"", 0, None
            menu_ouvert, retour = not tui, False
            secret = "hidden-test-key-should-never-echo"
            try:
                fin = time.monotonic() + 8
                while time.monotonic() < fin:
                    if select.select([fd], [], [], 0.1)[0]:
                        try:
                            bloc = os.read(fd, 8192)
                        except OSError:
                            break
                        if not bloc:
                            break
                        contenu += bloc
                        if not menu_ouvert and b"Settings" in contenu:
                            os.write(fd, b"j" * m.SECTIONS.index("Agents IA (coucou)") + b"\n\n")
                            menu_ouvert = True
                        if stade == 0 and b"Server URL" in contenu:
                            os.write(fd, b"http://example.test\n")
                            stade = 1
                        elif stade == 1 and b"Secret key" in contenu:
                            os.write(fd, (secret + "\n").encode())
                            stade = 2
                        elif stade == 2 and b"USER_ID" in contenu:
                            os.write(fd, b"\n")
                            stade = 3
                        if tui and not retour and b"Assistant connection saved" in contenu:
                            retour = True
                            os.write(fd, b"q")
                    attendu, status = os.waitpid(pid, os.WNOHANG)
                    if attendu:
                        pid = None
                        break
                if pid is not None:
                    attendu, status = os.waitpid(pid, os.WNOHANG)
                    if attendu:
                        pid = None
                self.assertEqual(stade, 3, contenu.decode(errors="replace"))
                self.assertIn(b"Configuration saved", contenu)
                if tui:
                    self.assertTrue(retour, contenu.decode(errors="replace"))
                self.assertNotIn(secret.encode(), contenu)
                conf = settings.with_name("assistant.conf")
                self.assertIn(secret, conf.read_text())
                self.assertEqual(conf.stat().st_mode & 0o777, 0o600)
                self.assertEqual(settings.read_bytes(), original)
            finally:
                if pid is not None:
                    try:
                        os.kill(pid, 9)
                    except ProcessLookupError:
                        pass
                    os.waitpid(pid, 0)
                os.close(fd)


if __name__ == "__main__":
    unittest.main()

"""nc-ia, l'IA du bureau : chaque API (Anthropic, OpenAI, Gemini, Ollama, transcription) contre un faux serveur local,
le mode automatique et son repli, le mode manuel, la coupure totale (IA_MODE=non) jusque dans JARVIS, la dictée et les
hooks des agents, les clés (0600, jamais affichées ni passées en argument), les actions sur le texte et le terminal."""
import base64
import http.server
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import tempfile
import threading
import unittest

REPO = Path(__file__).resolve().parents[1]
BIN = REPO / "home/.local/bin"
CLE_A, CLE_O = "sk-ant-test-0123456789abcdef", "sk-oai-test-abcdef0123456789"


def charger_nc_ia(nom):
    """nc-ia chargé dans ce processus, pour ses fonctions. À son chargement, nc-ia met les dossiers d'IA du HOME
    (~/.local/bin…) en tête de os.environ["PATH"] (pour l'île, voulu chez l'utilisateur) : devant les faux du
    garde-fou (tests/_isolation.py), pour tous les tests suivants du même processus. Le PATH d'avant est remis."""
    import importlib.machinery, importlib.util
    avant = os.environ.get("PATH")
    try:
        l = importlib.machinery.SourceFileLoader(nom, str(BIN / "nc-ia"))
        m = importlib.util.module_from_spec(importlib.util.spec_from_loader(nom, l)); l.exec_module(m)
    finally:
        if avant is None:
            os.environ.pop("PATH", None)
        else:
            os.environ["PATH"] = avant
    return m


class Faux(http.server.BaseHTTPRequestHandler):
    """Répond comme les vraies API ; garde chaque requête (chemin, en-têtes, corps) pour les vérifications."""
    requetes = []
    anthropic_refuse = False
    texte_ant = "Bonjour"                    # ce que « Claude » répond (un plan JSON pour nc-ia agir)

    def log_message(self, *a):
        pass

    def envoyer(self, code, corps, type_="application/json"):
        data = corps.encode() if isinstance(corps, str) else corps
        self.send_response(code)
        self.send_header("Content-Type", type_)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        Faux.requetes.append(dict(chemin=self.path, entetes={k.lower(): v for k, v in self.headers.items()}, corps=None))
        if self.path.startswith("/oai/models"):
            return self.envoyer(200, json.dumps({"data": [{"id": "gpt-4o-mini"}, {"id": "gpt-5-mini"}, {"id": "gpt-5.1-mini"}]}))
        if self.path.startswith("/ollama/api/tags"):
            return self.envoyer(200, json.dumps({"models": [{"name": "vieux:1b", "modified_at": "2025-01-01"},
                                                            {"name": "llama3.2:3b", "modified_at": "2026-01-01"}]}))
        if self.path.startswith("/gem/models"):
            return self.envoyer(200, json.dumps({"models": [{"name": "models/gemini-2.5-flash", "supportedGenerationMethods": ["generateContent"]},
                                                            {"name": "models/gemini-3.0-flash", "supportedGenerationMethods": ["generateContent"]}]}))
        self.envoyer(404, "{}")

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        brut = self.rfile.read(n)
        try:
            corps = json.loads(brut)
        except ValueError:
            corps = brut
        Faux.requetes.append(dict(chemin=self.path, entetes={k.lower(): v for k, v in self.headers.items()}, corps=corps))
        sse = lambda evs: "".join(f"data: {json.dumps(e)}\n\n" for e in evs)
        if self.path == "/ant/messages":
            if Faux.anthropic_refuse:
                return self.envoyer(401, json.dumps({"error": {"message": "invalid x-api-key"}}))
            return self.envoyer(200, "event: message_start\n" + sse([
                {"type": "message_start", "message": {"id": "m"}},
                {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": Faux.texte_ant[:3]}},
                {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": Faux.texte_ant[3:]}},
                {"type": "message_delta", "delta": {"stop_reason": "end_turn"}}, {"type": "message_stop"}]), "text/event-stream")
        if self.path == "/oai/chat/completions":
            return self.envoyer(200, sse([{"choices": [{"delta": {"content": "Salut"}}]},
                                          {"choices": [{"delta": {"content": " toi"}}]}]) + "data: [DONE]\n\n", "text/event-stream")
        if self.path.startswith("/gem/models/") and "streamGenerateContent" in self.path:
            return self.envoyer(200, sse([{"candidates": [{"content": {"parts": [{"text": "Gem"}]}}]},
                                          {"candidates": [{"content": {"parts": [{"text": "ini"}]}}]}]), "text/event-stream")
        if self.path == "/ollama/api/chat":
            return self.envoyer(200, "".join(json.dumps(e) + "\n" for e in (
                {"message": {"content": "Lo"}, "done": False}, {"message": {"content": "cal"}, "done": True})), "application/x-ndjson")
        if self.path == "/groq/audio/transcriptions":
            return self.envoyer(200, json.dumps({"text": "bonjour le monde"}))
        self.envoyer(404, "{}")


@unittest.skipUnless(shutil.which("zsh") or True, "")
class IA(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.serveur = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Faux)
        cls.port = cls.serveur.server_address[1]
        threading.Thread(target=cls.serveur.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.serveur.shutdown()
        cls.serveur.server_close()

    def setUp(self):
        Faux.requetes.clear()
        Faux.anthropic_refuse = False
        Faux.texte_ant = "Bonjour"
        d = tempfile.TemporaryDirectory(prefix="nc-ia-")
        self.addCleanup(d.cleanup)
        self.home = Path(d.name)
        (self.home / ".config/nc").mkdir(parents=True)
        (self.home / "run").mkdir(mode=0o700)
        b = self.home / ".local/bin"
        b.mkdir(parents=True)
        for f in ("nc-ia", "nc-demander", "nc-assistant", "nc-claude", "nc-dictee", "nc-jarvis"):
            os.symlink(BIN / f, b / f)
        self.faux = self.home / "faux"
        self.faux.mkdir()
        self.journal = self.home / "journal"
        u = f"http://127.0.0.1:{self.port}"
        self.cles(f"ANTHROPIC_API_KEY={CLE_A}\nURL_ANTHROPIC={u}/ant\nURL_OPENAI={u}/oai\nURL_GOOGLE={u}/gem\n"
                  f"URL_GROQ={u}/groq\nOLLAMA_HOST=http://127.0.0.1:1\n")
        self.reglages("IA_PREFERENCE=rapide\n")

    def cles(self, texte):
        f = self.home / ".config/nc/ia.conf"
        f.write_text(texte)
        f.chmod(0o600)

    def reglages(self, texte):
        (self.home / ".config/nc/reglages.conf").write_text("LANGUE=fr\n" + texte)

    def programme(self, nom, corps):
        f = self.faux / nom
        f.write_text("#!/bin/sh\n" + corps + "\n")
        f.chmod(0o755)

    def lancer(self, *args, entree=None, prog="nc-ia", env_plus=None):
        # Sur secteur, en ligne, profil équilibré : rien ne dépend de la machine qui lance les tests
        env = dict(HOME=str(self.home), XDG_CONFIG_HOME=str(self.home / ".config"), XDG_CACHE_HOME=str(self.home / "cache"),
                   XDG_RUNTIME_DIR=str(self.home / "run"), PATH=f"{self.faux}:/usr/bin:/bin", NC_LANGUE="fr",
                   JOURNAL=str(self.journal), NC_POWER_SUPPLY="secteur", NC_PROFIL="balanced", NC_IA_EN_LIGNE="1")
        env.update(env_plus or {})
        # Les programmes d'IA installés sur la machine de test ne doivent pas répondre à la place des faux serveurs
        for nom in ("claude", "codex", "opencode", "gemini", "qwen"):
            self.programme(nom, "exit 1") if not (self.faux / nom).exists() else None
        return subprocess.run([str(self.home / ".local/bin" / prog), *args], env=env, input=entree or "", capture_output=True,
                              text=True, timeout=30)

    def flux(self, r):
        lignes = [json.loads(l) for l in r.stdout.splitlines() if l.strip()]
        return lignes, "".join(l.get("t", "") for l in lignes)

    # ── API ──
    def test_anthropic_en_flux(self):
        r = self.lancer("demander", "--flux", "dis bonjour")
        self.assertEqual(r.returncode, 0, r.stderr)
        lignes, texte = self.flux(r)
        self.assertEqual(lignes[0]["id"], "anthropic")
        self.assertEqual(texte, "Bonjour")
        q = Faux.requetes[-1]
        self.assertEqual(q["entetes"].get("x-api-key"), CLE_A)
        self.assertEqual(q["entetes"].get("anthropic-version"), "2023-06-01")
        self.assertEqual(q["entetes"].get("anthropic-beta"), "server-side-fallback-2026-07-01")
        self.assertEqual(q["corps"]["model"], "claude-opus-5-5")
        self.assertEqual(q["corps"]["fallbacks"], "default")
        self.assertEqual(q["corps"]["output_config"], {"effort": "low"})
        self.assertTrue(q["corps"]["stream"])
        self.assertIn("dis bonjour", json.dumps(q["corps"]["messages"], ensure_ascii=False))

    def test_repli_automatique_puis_memoire_de_l_echec(self):
        self.cles((self.home / ".config/nc/ia.conf").read_text() + f"OPENAI_API_KEY={CLE_O}\n")
        Faux.anthropic_refuse = True
        r = self.lancer("demander", "--flux", "question")
        lignes, texte = self.flux(r)
        # Issue #4 : le relais est dit avant la réponse, pas en silence
        self.assertTrue(texte.startswith("⚠ Claude (API Anthropic) n'a pas répondu — clé refusée"), texte)
        self.assertIn(": ChatGPT (API OpenAI) prend le relais.\n\n", texte)
        self.assertTrue(texte.endswith("Salut toi"), r.stdout + r.stderr)
        self.assertEqual(len([l for l in lignes if "relais" in l]), 1)
        self.assertEqual([l["id"] for l in lignes if "id" in l], ["anthropic", "openai"])
        gardee = next((self.home / "run").rglob("derniere*")).read_text()
        self.assertTrue(gardee.startswith("Salut toi"), "la réponse gardée, sans l'avis")
        oai = [q for q in Faux.requetes if q["chemin"] == "/oai/chat/completions"][-1]
        self.assertEqual(oai["entetes"]["authorization"], "Bearer " + CLE_O)
        self.assertEqual(oai["corps"]["model"], "gpt-5.1-mini", "le plus récent des « mini » de la liste")
        self.assertIn("max_completion_tokens", oai["corps"])
        # L'échec est retenu : la question suivante part d'abord vers OpenAI, sans attendre Anthropic
        Faux.requetes.clear()
        r = self.lancer("quelle", "--json")
        self.assertEqual(json.loads(r.stdout)["id"], "openai")

    def test_relais_apres_deux_echecs_et_aucun_avis_si_tout_echoue(self):
        """Revue REL-01 : l'avis était écrit avant que l'IA suivante ait répondu ; si elle échouait aussi, il nommait la
        mauvaise (« Gemini prend le relais » suivi d'une réponse d'une autre), et il restait même quand toutes échouaient."""
        u = f"http://127.0.0.1:{self.port}"
        self.cles(f"ANTHROPIC_API_KEY={CLE_A}\nURL_ANTHROPIC={u}/ant\nOPENAI_API_KEY={CLE_O}\nURL_OPENAI=http://127.0.0.1:1/oai\n"
                  f"GEMINI_API_KEY=AIzaTest0123456789\nURL_GOOGLE={u}/gem\nOLLAMA_HOST=http://127.0.0.1:1\n")
        Faux.anthropic_refuse = True
        lignes, texte = self.flux(self.lancer("demander", "--flux", "question"))
        avis = [l["relais"] for l in lignes if "relais" in l]
        self.assertEqual(len(avis), 1, lignes)
        self.assertRegex(avis[0], r"^⚠ Claude \(API Anthropic\), ChatGPT \(API OpenAI\) et .*Gemini.* n'ont pas répondu|"
                                  r"^⚠ Claude \(API Anthropic\) et ChatGPT \(API OpenAI\) n'ont pas répondu")
        self.assertIn("Gemini", avis[0].split(":")[-1], "nomme celle qui répond vraiment")
        # Toutes en échec : aucun avis, seulement l'erreur
        self.cles(f"ANTHROPIC_API_KEY={CLE_A}\nURL_ANTHROPIC={u}/ant\nOPENAI_API_KEY={CLE_O}\nURL_OPENAI=http://127.0.0.1:1/oai\n"
                  f"OLLAMA_HOST=http://127.0.0.1:1\n")
        r = self.lancer("demander", "--flux", "question")
        self.assertNotIn("relais", r.stdout)
        self.assertNotIn("prend le relais", r.stdout + r.stderr)

    def test_manuel_une_seule_ia(self):
        self.cles((self.home / ".config/nc/ia.conf").read_text() + f"OPENAI_API_KEY={CLE_O}\n")
        self.reglages("IA_MODE=manuel\nIA_CHOIX=openai\n")
        r = self.lancer("demander", "question")
        self.assertEqual(r.stdout.strip(), "Salut toi")
        self.assertFalse([q for q in Faux.requetes if q["chemin"].startswith("/ant")])
        self.reglages("IA_MODE=manuel\nIA_CHOIX=mistral\n")
        r = self.lancer("demander", "question")
        self.assertEqual(r.returncode, 1)
        self.assertIn("Mistral", r.stderr)

    def test_gemini_et_ollama(self):
        self.cles(f"GEMINI_API_KEY=AIzaTest0123456789\nURL_GOOGLE=http://127.0.0.1:{self.port}/gem\n"
                  f"OLLAMA_HOST=http://127.0.0.1:{self.port}/ollama\n")
        r = self.lancer("demander", "--ia", "google", "q")
        self.assertEqual(r.stdout.strip(), "Gemini", r.stderr)
        g = [q for q in Faux.requetes if "streamGenerateContent" in q["chemin"]][-1]
        self.assertIn("gemini-3.0-flash", g["chemin"])
        self.assertEqual(g["entetes"].get("x-goog-api-key"), "AIzaTest0123456789")
        self.assertNotIn("AIzaTest", g["chemin"], "la clé dans un en-tête, jamais dans l'adresse")
        r = self.lancer("demander", "--ia", "ollama", "q")
        self.assertEqual(r.stdout.strip(), "Local", r.stderr)
        o = [q for q in Faux.requetes if q["chemin"] == "/ollama/api/chat"][-1]
        self.assertEqual(o["corps"]["model"], "llama3.2:3b", "le modèle le plus récent")

    def test_image_jointe(self):
        img = self.home / "c.png"
        img.write_bytes(b"\x89PNG\r\n\x1a\nfaux")
        r = self.lancer("demander", "--image", str(img), "que vois-tu")
        self.assertEqual(r.returncode, 0, r.stderr)
        bloc = Faux.requetes[-1]["corps"]["messages"][0]["content"][0]
        self.assertEqual(bloc["type"], "image")
        self.assertEqual(base64.b64decode(bloc["source"]["data"]), img.read_bytes())

    def test_commande_seule(self):
        self.programme("claude", 'echo \'{"type":"stream_event","event":{"delta":{"type":"text_delta","text":"```bash\\n$ du -sh *\\n```"}}}\'')
        self.reglages("IA_MODE=manuel\nIA_CHOIX=claude\n")
        r = self.lancer("commande", "taille des dossiers")
        self.assertEqual(r.stdout.strip(), "du -sh *", r.stderr)

    def test_actions_sur_le_texte(self):
        self.programme("wl-paste", 'case "$*" in *-p*) printf "texte sélectionné";; *) printf "copié";; esac')
        self.programme("wl-copy", 'echo "wl-copy $*" >> "$JOURNAL"')
        self.programme("notify-send", 'echo "notify $*" >> "$JOURNAL"')
        r = self.lancer("texte", "traduire", "--copier")
        self.assertEqual(r.returncode, 0, r.stderr)
        envoye = json.dumps(Faux.requetes[-1]["corps"], ensure_ascii=False)
        self.assertIn("texte sélectionné", envoye)
        self.assertIn("Traduis", envoye)
        self.assertIn("wl-copy -- Bonjour", self.journal.read_text())
        r = self.lancer("texte", "en liste à puces", "--presse")
        self.assertIn("en liste à puces", json.dumps(Faux.requetes[-1]["corps"], ensure_ascii=False))
        self.assertIn("copié", json.dumps(Faux.requetes[-1]["corps"], ensure_ascii=False))

    def test_transcription(self):
        self.cles(f"GROQ_API_KEY=gsk_test0123456789\nURL_GROQ=http://127.0.0.1:{self.port}/groq\n")
        wav = self.home / "d.wav"
        wav.write_bytes(b"RIFF" + b"\0" * 2000)
        r = self.lancer("transcrire", str(wav), "--json")
        self.assertEqual(json.loads(r.stdout)["text"], "bonjour le monde", r.stderr)
        q = Faux.requetes[-1]
        self.assertTrue(q["entetes"]["content-type"].startswith("multipart/form-data"))
        self.assertIn(b"whisper-large-v3-turbo", q["corps"])

    def test_chat_de_l_ile_sans_jarvis(self):
        """La fenêtre de chat : sans JARVIS relié, l'IA du bureau répond, avec la conversation, et le dit."""
        entree = json.dumps({"session_id": "a" * 32, "question": "et demain ?",
                             "historique": [{"role": "user", "texte": "quel temps fait-il"}, {"role": "assistant", "texte": "Soleil."}]})
        r = self.lancer("requete-ile", entree=entree + "\n", prog="nc-assistant")
        d = json.loads(r.stdout)
        self.assertTrue(d["ok"], r.stdout + r.stderr)
        self.assertTrue(d["text"].startswith("Bonjour"))
        self.assertIn("Claude (API Anthropic)", d["text"])
        envoye = json.dumps(Faux.requetes[-1]["corps"], ensure_ascii=False)
        self.assertIn("quel temps fait-il", envoye)
        self.assertIn("et demain ?", envoye)
        # Les commandes « / » restent celles de JARVIS : pas envoyées à une autre IA
        Faux.requetes.clear()
        r = self.lancer("requete-ile", entree=json.dumps({"session_id": "a" * 32, "question": "/reset"}) + "\n", prog="nc-assistant")
        self.assertFalse(json.loads(r.stdout)["ok"])
        self.assertFalse(Faux.requetes)

    def test_chat_jarvis_injoignable_le_relais_est_dit(self):
        """Issue #4 : JARVIS relié mais injoignable (tunnel coupé…) : l'IA du bureau répond, et le chat le dit en tête."""
        import socket
        so = socket.socket(); so.bind(("127.0.0.1", 0)); port = so.getsockname()[1]; so.close()     # personne n'écoute
        conf = self.home / ".config/nc/assistant.conf"
        conf.write_text(f'URL="http://127.0.0.1:{port}"\nSECRET_KEY="{"k" * 40}"\n'); conf.chmod(0o600)
        r = self.lancer("requete-ile", entree=json.dumps({"session_id": "a" * 32, "question": "bonjour"}) + "\n", prog="nc-assistant")
        d = json.loads(r.stdout)
        self.assertTrue(d["ok"], r.stdout + r.stderr)
        self.assertTrue(d["text"].startswith("⚠ JARVIS n'a pas répondu"), d["text"][:200])
        self.assertIn("Claude (API Anthropic) prend le relais.", d["text"])
        self.assertIn("Bonjour", d["text"])

    def test_texte_par_l_entree_standard_et_fichiers(self):
        r = self.lancer("texte", "resumer", "--stdin", entree="un long texte à résumer")
        self.assertEqual(r.returncode, 0, r.stderr)
        envoye = json.dumps(Faux.requetes[-1]["corps"], ensure_ascii=False)
        self.assertIn("un long texte à résumer", envoye)
        self.assertIn("Résume", envoye)
        f = self.home / "notes.md"
        f.write_text("# Courses\n- pain\n- lait\n")
        r = self.lancer("fichier", str(f), "expliquer")
        self.assertEqual(r.returncode, 0, r.stderr)
        envoye = json.dumps(Faux.requetes[-1]["corps"], ensure_ascii=False)
        self.assertIn("=== notes.md ===", envoye)
        self.assertIn("Explique", envoye)
        img = self.home / "ecran.png"
        img.write_bytes(b"\x89PNG\r\n\x1a\nfaux")
        r = self.lancer("fichier", str(img))
        bloc = Faux.requetes[-1]["corps"]["messages"][0]["content"][0]
        self.assertEqual(bloc["type"], "image", r.stderr)
        binaire = self.home / "prog.bin"
        binaire.write_bytes(b"\0\1\2" * 100)
        r = self.lancer("fichier", str(binaire))
        self.assertEqual(r.returncode, 1)
        self.assertIn("ni un texte", r.stderr)

    def test_diagnostic(self):
        diag = self.home / ".local/bin/nc-diag"
        diag.write_text("#!/bin/sh\necho 'Wi-Fi'\necho '  ✓ carte présente'\necho '  ✗ portail arrêté'\n")
        diag.chmod(0o755)
        r = self.lancer("diagnostic")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("portail arrêté", json.dumps(Faux.requetes[-1]["corps"], ensure_ascii=False))
        Faux.requetes.clear()
        diag.write_text("#!/bin/sh\necho '  ✓ tout va bien'\n")
        r = self.lancer("diagnostic")
        self.assertIn("rien à corriger", r.stdout)
        self.assertFalse(Faux.requetes, "rien à expliquer : aucune IA appelée")

    def test_scripts_des_gestionnaires_de_fichiers(self):
        nautilus = REPO / "home/.local/share/nautilus/scripts/IA"
        for f in nautilus.iterdir():
            self.assertTrue(os.access(f, os.X_OK), f)
            self.assertIn('nc-ia" fichier "$@"', f.read_text())
            self.assertIn("--notifier", f.read_text())
        self.assertIn("X-KDE-Submenu=IA", (REPO / "home/.local/share/kio/servicemenus/nc-ia.desktop").read_text())
        self.assertTrue(list((REPO / "home/.local/share/nemo/actions").glob("nc-ia-*.nemo_action")))

    # ── Réponses des raccourcis : dans la conversation, une notification qui l'ouvre ──
    def preparer_capture(self):
        self.programme("slurp", 'echo "10,10 100x100"')
        self.programme("grim", 'for a; do f="$a"; done; printf "\\211PNG\\r\\n\\032\\nfaux" > "$f"')
        self.programme("qs", 'echo "qs $*" >> "$JOURNAL"; exit ${QS_CODE:-0}')
        self.programme("notify-send", 'echo "notify $*" >> "$JOURNAL"')
        self.programme("wl-copy", 'echo "wl-copy $*" >> "$JOURNAL"')

    def test_reponse_versee_dans_le_chat(self):
        self.preparer_capture()
        r = self.lancer("capture")
        self.assertEqual(r.returncode, 0, r.stderr)
        j = self.appels()
        self.assertIn("ipc call ile iaReponse", j)
        f = Path(j.split("iaReponse ")[1].split()[0])
        d = json.loads(f.read_text())
        self.assertEqual((d["reponse"], d["ia"], d["agent"]), ("Bonjour", "Claude (API Anthropic)", "claude"))
        self.assertTrue(d["question"].startswith("📷"))
        self.assertEqual(oct(f.stat().st_mode & 0o777), "0o600")
        self.assertIn("-A default=Ouvrir la conversation", j)
        self.assertIn("wl-copy -- Bonjour", j)
        self.assertNotIn("kitty", j, "plus de terminal")

    def test_reponse_en_notification_seule_ou_sans_ile(self):
        self.preparer_capture()
        self.reglages("IA_REPONSES=notification\nIA_COPIER=non\n")
        self.lancer("capture")
        j = self.appels()
        self.assertNotIn("iaReponse", j)
        self.assertNotIn("wl-copy", j)
        self.assertIn("Bonjour", j.splitlines()[-1])
        self.journal.unlink()
        self.reglages("")
        self.lancer("capture", env_plus={"QS_CODE": "1"})          # l'île ne répond pas : notification seule
        self.assertIn("Bonjour", self.appels().splitlines()[-1])
        self.assertNotIn("default=", self.appels().splitlines()[-1])

    def test_la_suite_va_a_l_ia_qui_a_repondu(self):
        conf = self.home / ".config/nc/assistant.conf"
        conf.write_text('URL="http://127.0.0.1:9/gateway"\nSECRET_KEY="cle-de-test"\nUSER_ID="moi"\nTIMEOUT="5"\n')
        conf.chmod(0o600)
        entree = {"session_id": "a" * 32, "question": "et ensuite ?", "historique": [{"role": "assistant", "texte": "Une capture."}]}
        d = json.loads(self.lancer("requete-ile", entree=json.dumps(dict(entree, ia_du_bureau=True)) + "\n", prog="nc-assistant").stdout)
        self.assertTrue(d["ok"] and d["engine"] == "Claude (API Anthropic)", d)
        self.assertIn("Une capture.", json.dumps(Faux.requetes[-1]["corps"], ensure_ascii=False))

    # ── Économie sur batterie, sans connexion ──
    def test_economie_sur_batterie_seul_l_arriere_plan_s_arrete(self):
        eco = {"NC_POWER_SUPPLY": "batterie", "NC_PROFIL": "power-saver"}
        # Ce que tu lances toi-même marche toujours
        self.assertEqual(self.lancer("demander", "q", env_plus=eco).stdout.strip(), "Bonjour")
        self.assertFalse(json.loads(self.lancer("--ia", "--json", prog="nc-demander", env_plus=eco).stdout)["coupee"])
        self.assertEqual(self.lancer("actif", env_plus=eco).returncode, 0)
        # Un automatisme (--fond, NC_IA_FOND=1) se met en pause, sans rien appeler
        Faux.requetes.clear()
        r = self.lancer("demander", "--fond", "--flux", "q", env_plus=eco)
        self.assertEqual(r.returncode, 3)
        self.assertIn("arrière-plan est en pause", r.stdout)
        self.assertEqual(self.lancer("demander", "q", env_plus=dict(eco, NC_IA_FOND="1")).returncode, 3)
        self.assertFalse(Faux.requetes, "rien n'est appelé en arrière-plan pendant la pause")
        # Sur secteur, hors Économie, ou réglage à non : l'arrière-plan répond
        for env in ({"NC_POWER_SUPPLY": "secteur", "NC_PROFIL": "power-saver"}, {"NC_POWER_SUPPLY": "batterie", "NC_PROFIL": "balanced"}):
            self.assertEqual(self.lancer("demander", "--fond", "q", env_plus=env).stdout.strip(), "Bonjour")
        self.reglages("IA_ECONOMIE=non\n")
        self.assertEqual(self.lancer("demander", "--fond", "q", env_plus=eco).stdout.strip(), "Bonjour")

    def test_sans_connexion_seule_une_ia_locale(self):
        hors = {"NC_IA_EN_LIGNE": "0"}
        r = self.lancer("demander", "q", env_plus=hors)
        self.assertEqual(r.returncode, 1)
        self.assertIn("Pas de connexion", r.stderr)
        self.assertEqual(self.lancer("disponible", env_plus=hors).returncode, 1)
        self.assertFalse(Faux.requetes)
        # Ollama sur ce PC répond toujours ; revenue, la connexion rend les autres
        self.cles(f"ANTHROPIC_API_KEY={CLE_A}\nURL_ANTHROPIC=http://127.0.0.1:{self.port}/ant\nOLLAMA_HOST=http://127.0.0.1:{self.port}/ollama\n")
        self.assertEqual(json.loads(self.lancer("quelle", "--json", env_plus=hors).stdout)["id"], "ollama")
        self.assertEqual(self.lancer("demander", "q", env_plus=hors).stdout.strip(), "Local")
        self.assertEqual(json.loads(self.lancer("quelle", "--json").stdout)["id"], "anthropic")

    # ── L'IA qui agit ──
    def preparer_agent(self):
        self.programme("systemctl", 'echo "systemctl $*" >> "$JOURNAL"; case "$*" in *list-units*) echo "nc-ile.service loaded active running Ile";; '
                                    '*is-active*) echo active;; esac')
        for p in ("bluetoothctl", "nmcli", "wpctl", "busctl", "journalctl"):
            self.programme(p, f'echo "{p} $*" >> "$JOURNAL"')
        Faux.texte_ant = json.dumps({"reponse": "Je redémarre l'île et coupe le Bluetooth.", "actions": [
            {"outil": "service_redemarrer", "args": {"nom": "nc-ile.service"}},
            {"outil": "bluetooth", "args": {"etat": "off"}},
            {"outil": "reglage", "args": {"cle": "IA_ACTIONS", "valeur": "auto"}},
            {"outil": "service_redemarrer", "args": {"nom": "sshd.service"}},
            {"outil": "shell", "args": {"cmd": "rm -rf ~"}}]})

    def appels(self):
        return self.journal.read_text() if self.journal.exists() else ""

    def test_agir_coupe_par_defaut(self):
        self.preparer_agent()
        r = self.lancer("agir", "coupe le bluetooth")
        self.assertEqual(r.returncode, 1)
        self.assertIn("pas le droit", r.stderr)
        self.assertFalse(Faux.requetes)

    def test_agir_propose_puis_seulement_ce_qui_est_confirme(self):
        self.preparer_agent()
        self.reglages("IA_ACTIONS=confirmer\n")
        r = self.lancer("agir", "--json", "redémarre l'île et coupe le bluetooth")
        self.assertEqual(r.returncode, 0, r.stderr)
        plan = json.loads(r.stdout)
        self.assertEqual([a["libelle"] for a in plan["actions"]], ["Redémarrer nc-ile.service", "Bluetooth : off"])
        self.assertFalse(any(a["fait"] for a in plan["actions"]), "rien n'est fait avant la confirmation")
        self.assertEqual(len(plan["refus"]), 3, plan["refus"])          # son propre réglage, service hors session, outil inconnu
        self.assertNotIn("restart", self.appels())
        self.assertNotIn("bluetoothctl power", self.appels())
        consigne = json.dumps(Faux.requetes[-1]["corps"], ensure_ascii=False)
        self.assertIn("service_redemarrer", consigne)
        self.assertIn("nc-ile.service", consigne, "l'IA voit l'état des services")
        # Une seule action confirmée : seulement elle
        r = self.lancer("executer", plan["id"], "1", "--json")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("bluetoothctl power off", self.appels())
        self.assertNotIn("systemctl --user restart", self.appels())
        r = self.lancer("executer", plan["id"], "--json")
        self.assertIn("systemctl --user restart nc-ile.service", self.appels())
        self.assertEqual(self.appels().count("bluetoothctl power off"), 1, "une action faite ne se refait pas")
        self.assertEqual(self.lancer("executer", "pas-un-plan").returncode, 1)

    def test_secrets_masques_avant_l_ia(self):
        """Revue PRIV-01 : les secrets nommés par une variable (DB_PASSWORD=, TELEGRAM_TOKEN=, X-Secret-Key:…) passaient,
        et le journal lu par « L'IA peut agir » (service_journal, sans confirmation) partait en clair."""
        secrets = ["DB_PASSWORD=zzz1", "MY_API_KEY=zzz2", "TELEGRAM_TOKEN=zzz3", "SECRET_KEY=zzz4", "X-Secret-Key: zzz5",
                   '{"access_token":"zzz6"}', "https://alice:zzz7@hote/x", "api.telegram.org/bot123456789:AAzzz8zzzzzzzzzzzzzzzzzzzz/getMe",
                   "Authorization: Basic enp6OTp4eA==", "-----BEGIN PRIVATE KEY-----", "zzz10", "-----END PRIVATE KEY-----",
                   "AKIAZZZ1100000000000", f"chemin {self.home}/.config/x"]
        self.preparer_agent()
        self.programme("journalctl", "cat <<'FIN'\n" + "\n".join(secrets) + "\nauthentication failed for user\nFIN")
        self.reglages("IA_ACTIONS=confirmer\n")
        Faux.texte_ant = json.dumps({"reponse": "Je lis le journal.", "actions": [{"outil": "service_journal", "args": {"nom": "nc-ile.service"}}]})
        r = self.lancer("agir", "--json", "pourquoi l'île plante")
        self.assertEqual(r.returncode, 0, r.stderr)
        envoye = json.dumps(Faux.requetes[-1]["corps"], ensure_ascii=False)
        self.assertIn("Résultats de tes lectures", envoye)
        envoye = envoye[envoye.index("Résultats de tes lectures"):]
        self.assertIn("authentication failed for user", envoye, "le reste du journal est gardé")
        self.assertIn("chemin ~/.config/x", envoye, "le dossier personnel devient ~")
        for x in ("zzz", "ZZZ", "enp6OTp4eA", str(self.home)):
            self.assertNotIn(x, envoye)
        # « Expliquer » une panne : même masquage
        self.programme("systemctl", f'printf "Description=Île\\nLoadState=loaded\\nFragmentPath={self.home}/.config/systemd/user/nc-ile.service\\n"')
        self.assertEqual(self.lancer("panne", "nc-ile.service").returncode, 0)
        envoye = json.dumps(Faux.requetes[-1]["corps"], ensure_ascii=False)
        self.assertIn("FragmentPath=~/.config/systemd/user/nc-ile.service", envoye)
        for x in ("zzz", "ZZZ", str(self.home)):
            self.assertNotIn(x, envoye)

    def test_mode_manuel_sans_choix_enregistre(self):
        """Revue IA-08 : en « Celle que je choisis » sans choix écrit, nc-reglages affichait Claude (son défaut) mais
        nc-ia lisait un choix vide : aucune IA nulle part, sans explication."""
        self.programme("claude", "exit 0")
        self.reglages("IA_MODE=manuel\n")
        self.lancer("etat")
        e = json.loads(self.lancer("etat", "--json").stdout)
        self.assertEqual(e["choix"], "claude")
        self.assertEqual({u: v["id"] for u, v in e["usages"].items()}, {u: "claude" for u in e["usages"]})
        reglages = subprocess.run([str(BIN / "nc-reglages"), "get", "IA_CHOIX"], capture_output=True, text=True,
                                  env=dict(os.environ, HOME=str(self.home), XDG_CONFIG_HOME=str(self.home / ".config")))
        self.assertEqual(reglages.stdout.strip(), "claude", "le même défaut des deux côtés")

    def test_masquage_rapide_sur_un_long_mot(self):
        """Revue PRIV-02 : 12 000 caractères sans espace (base64, JSON minifié) prenaient ~10 s (expression quadratique)."""
        import time
        m = charger_nc_ia("ncia_cav")
        for t in ("a" * 20000, "a." * 10000, "Q" * 12000 + " secret=zzz"):
            debut = time.monotonic()
            r = m.caviarder(t)
            self.assertLess(time.monotonic() - debut, 0.5, t[:20])
            self.assertNotIn("zzz", r)
        self.assertEqual(m.caviarder("client_secret=zz mon.app-token: zz"), "client_secret=[…] mon.app-token: […]")

    def test_agir_organise_les_fenetres(self):
        clients = [{"address": "0xa1", "class": "kitty", "title": "nvim", "mapped": True, "workspace": {"id": 2}, "floating": False, "size": [800, 600]},
                   {"address": "0xb2", "class": "firefox", "title": "Docs", "mapped": True, "workspace": {"id": 2}, "floating": False, "size": [800, 600]},
                   {"address": "0xc3", "class": "dropterm", "title": "t", "mapped": True, "workspace": {"id": -98}, "floating": True, "size": [1, 1]}]
        self.programme("hyprctl", 'echo "hyprctl $*" >> "$JOURNAL"; case "$1" in clients) echo \'' + json.dumps(clients) + '\';; '
                                  'workspaces) echo \'[{"id": 2, "name": "2", "windows": 2, "monitor": "eDP-1"}]\';; activeworkspace) echo \'{"id": 2}\';; esac')
        for p in ("systemctl", "bluetoothctl", "nmcli", "wpctl", "busctl"):
            self.programme(p, "exit 0")
        Faux.texte_ant = json.dumps({"reponse": "Code sur le 1, navigateur sur le 2.", "actions": [
            {"outil": "fenetre_bureau", "args": {"adresse": "0xa1", "bureau": 1}},
            {"outil": "bureau_nommer", "args": {"bureau": 1, "nom": "Code"}},
            {"outil": "fenetre_echanger", "args": {"adresse": "0xa1", "autre": "0xb2"}},
            {"outil": "fenetre_bureau", "args": {"adresse": "0xc3", "bureau": 4}},
            {"outil": "fenetre_bureau", "args": {"adresse": "0xb2", "bureau": 11}},
            {"outil": "bureau_nommer", "args": {"bureau": 2, "nom": "x]]; os.exit()"}}]})
        self.reglages("IA_ACTIONS=confirmer\n")
        plan = json.loads(self.lancer("agir", "--json", "organise mes fenêtres").stdout)
        self.assertEqual([x["libelle"] for x in plan["actions"]],
                         ["kitty → bureau 1 (maintenant : bureau 2)", "Bureau 1 nommé « Code »", "Échanger kitty et firefox"])
        self.assertEqual(len(plan["refus"]), 3, plan["refus"])     # terminal déroulant, bureau 11, nom piégé
        envoye = json.dumps(Faux.requetes[-1]["corps"], ensure_ascii=False)
        self.assertIn("0xa1 · kitty", envoye, "l'IA voit les fenêtres")
        self.assertNotIn("dropterm", envoye)
        self.assertNotIn("dispatch", self.appels(), "rien avant la confirmation")
        self.lancer("executer", plan["id"], "--json")
        j = self.appels()
        self.assertIn("dispatch hl.dsp.window.move({ workspace = 1, follow = false, window = 'address:0xa1' })", j)
        self.assertIn("dispatch hl.dsp.workspace.rename({ workspace = 1, name = [[Code]] })", j)
        self.assertIn("dispatch hl.dsp.window.swap({ window = 'address:0xa1', target = 'address:0xb2' })", j)

    def test_organiser_ce_bureau_seulement(self):
        """Revue IA-06 : « Organiser ce bureau » ne touchait ce bureau que par la consigne ; maintenant la portée est dans
        le plan : l'IA ne voit que ses fenêtres, et rien ne peut en sortir ni renommer un autre bureau."""
        clients = [{"address": "0xa1", "class": "kitty", "title": "nvim", "mapped": True, "workspace": {"id": 2}, "floating": False, "size": [800, 600]},
                   {"address": "0xb2", "class": "firefox", "title": "Docs", "mapped": True, "workspace": {"id": 2}, "floating": True, "size": [800, 600]},
                   {"address": "0xd4", "class": "discord", "title": "Discord", "mapped": True, "workspace": {"id": 3}, "floating": False, "size": [800, 600]}]
        self.programme("hyprctl", 'echo "hyprctl $*" >> "$JOURNAL"; case "$1" in clients) echo \'' + json.dumps(clients) + '\';; '
                                  'workspaces) echo \'[{"id": 2, "name": "2", "windows": 2}, {"id": 3, "name": "3", "windows": 1}]\';; activeworkspace) echo \'{"id": 2}\';; esac')
        for p in ("systemctl", "bluetoothctl", "nmcli", "wpctl", "busctl"):
            self.programme(p, "exit 0")
        Faux.texte_ant = json.dumps({"reponse": "ok", "actions": [
            {"outil": "fenetre_echanger", "args": {"adresse": "0xa1", "autre": "0xb2"}},
            {"outil": "fenetre_libre", "args": {"adresse": "0xb2", "etat": "on"}},
            {"outil": "fenetre_bureau", "args": {"adresse": "0xa1", "bureau": 5}},
            {"outil": "fenetre_bureau", "args": {"adresse": "0xd4", "bureau": 2}},
            {"outil": "bureau_nommer", "args": {"bureau": 3, "nom": "Jeux"}}]})
        self.reglages("IA_ACTIONS=confirmer\n")
        r = self.lancer("agir", "--json", "--bureau", "2", "organise ce bureau")
        self.assertEqual(r.returncode, 0, r.stderr)
        plan = json.loads(r.stdout)
        self.assertEqual(plan["portee"], {"bureau": 2})
        self.assertEqual([x["libelle"] for x in plan["actions"]], ["Échanger kitty et firefox", "firefox libre : on (déjà le cas)"])
        self.assertEqual(len(plan["refus"]), 3, plan["refus"])   # vers le bureau 5, une fenêtre du bureau 3, renommer le 3
        envoye = json.dumps(Faux.requetes[-1]["corps"], ensure_ascii=False)
        self.assertNotIn("0xd4", envoye, "l'IA ne voit que les fenêtres de ce bureau")
        self.assertNotIn("organise ce bureau 2", envoye)
        # Poussée au bord de l'écran, une fenêtre passe sur l'écran voisin : remise sur ce bureau, et c'est dit
        Faux.texte_ant = json.dumps({"reponse": "ok", "actions": [{"outil": "fenetre_direction", "args": {"adresse": "0xa1", "direction": "droite"}}]})
        plan = json.loads(self.lancer("agir", "--json", "--bureau", "2", "kitty à droite").stdout)
        apres = json.loads(json.dumps(clients)); apres[0]["workspace"]["id"] = 7       # après le déplacement : l'écran voisin
        self.programme("hyprctl", 'echo "hyprctl $*" >> "$JOURNAL"; case "$1" in dispatch) : > "$HOME/bouge";; clients) '
                                  'if [ -e "$HOME/bouge" ]; then echo \'' + json.dumps(apres) + '\'; else echo \'' + json.dumps(clients) + '\'; fi;; esac')
        d = json.loads(self.lancer("executer", plan["id"], "--json").stdout)
        self.assertEqual(d["actions"][0]["note"], "bord de l'écran : remise sur le bureau 2", "dit avec « Fait », pas caché")
        self.assertIn("— bord de l'écran : remise sur le bureau 2", self.lancer("executer", plan["id"]).stdout)
        self.assertIn("hl.dsp.window.move({ workspace = 2, follow = false, window = 'address:0xa1' })", self.appels())

    def test_ranger_sans_rien_demander_puis_annuler(self):
        """Super + Maj + O : l'IA range tout de suite (fenêtres et bureaux seulement), une notification de l'île le dit,
        « Annuler » remet tout comme avant ; rien dans le Spotlight, même avec « L'IA peut agir » coupé."""
        clients = [{"address": "0xa1", "class": "kitty", "title": "nvim", "mapped": True, "workspace": {"id": 2}, "floating": False, "fullscreen": 0, "at": [0, 0], "size": [800, 600]},
                   {"address": "0xb2", "class": "firefox", "title": "Docs", "mapped": True, "workspace": {"id": 2}, "floating": True, "fullscreen": 0, "at": [100, 50], "size": [900, 700]}]
        apres = json.loads(json.dumps(clients)); apres[0]["workspace"]["id"] = 1
        self.programme("hyprctl", 'echo "hyprctl $*" >> "$JOURNAL"; case "$1" in dispatch|eval) case "$*" in *"workspace = 2"*) rm -f "$HOME/bouge";; *"workspace = 1"*) : > "$HOME/bouge";; esac;; '
                                  'clients) if [ -e "$HOME/bouge" ]; then echo \'' + json.dumps(apres) + '\'; else echo \'' + json.dumps(clients) + '\'; fi;; '
                                  'workspaces) echo \'[{"id": 1, "name": "1", "windows": 0}, {"id": 2, "name": "2", "windows": 2}]\';; activeworkspace) echo \'{"id": 2}\';; esac')
        self.programme("notify-send", 'echo "notify $*" >> "$JOURNAL"; case "$*" in *annuler=*) echo annuler;; esac')
        self.programme("qs", 'echo "qs $*" >> "$JOURNAL"')
        Faux.texte_ant = json.dumps({"reponse": "ok", "actions": [
            {"outil": "fenetre_bureau", "args": {"adresse": "0xa1", "bureau": 1}},
            {"outil": "service_redemarrer", "args": {"nom": "nc-ile.service"}}]})
        r = self.lancer("organiser")
        self.assertEqual(r.returncode, 0, r.stderr)
        a = self.appels()
        self.assertNotIn("qs ", a, "pas de Spotlight")
        self.assertIn("hl.dsp.window.move({ workspace = 1, follow = false, window = 'address:0xa1' })", a)
        self.assertNotIn("systemctl", a, "seulement les fenêtres et les bureaux")
        self.assertIn("Fenêtres rangées", a)
        self.assertIn("annuler=Annuler", a)
        # « Annuler » : kitty revient sur le bureau 2
        self.assertIn("hl.dsp.window.move({ workspace = 2, follow = false, window = 'address:0xa1' })", a)
        self.assertFalse((self.home / "cache/nc/rangement-avant.json").exists())
        # Tout d'un coup : un seul appel à Hyprland, dans la même image
        self.assertEqual(a.count("hyprctl eval  hl.dispatch(hl.dsp.window.move({ workspace = 1"), 1)
        # Rappuyer sans rien avoir changé : la disposition d'avant revient, sans IA
        self.programme("notify-send", 'echo "notify $*" >> "$JOURNAL"')
        self.journal.unlink()
        self.lancer("organiser")                              # range (kitty → bureau 1)
        self.assertTrue((self.home / "bouge").exists())
        Faux.requetes.clear()
        self.journal.unlink()
        self.lancer("organiser")                              # rien n'a bougé depuis : remis comme avant
        a = self.appels()
        self.assertFalse(Faux.requetes, "pas d'IA pour remettre comme avant")
        self.assertIn("hl.dsp.window.move({ workspace = 2, follow = false, window = 'address:0xa1' })", a)
        self.assertIn("Disposition d'avant remise", a)
        self.lancer("organiser")                              # et le suivant range à nouveau
        self.assertTrue(Faux.requetes)
        # Coupé : rien
        self.reglages("IA_ORGANISER=non\n")
        self.assertNotEqual(self.lancer("organiser").returncode, 0)
        self.reglages("IA_MODE=non\n")
        Faux.requetes.clear()
        self.lancer("organiser")
        self.assertFalse(Faux.requetes, "IA coupée : rien ne part")

    def test_ranger_ce_bureau_en_zones_libres(self):
        """Super + Ctrl + O sur un Hyprland sans dispositions en Lua : chaque fenêtre dans sa zone (pourcentages de la
        place sous la barre, marges de Hyprland déduites), devenue libre."""
        clients = [{"address": "0xa1", "class": "code", "title": "projet", "mapped": True, "workspace": {"id": 2}, "monitor": 0, "floating": False, "fullscreen": 0, "at": [12, 54], "size": [780, 934]},
                   {"address": "0xb2", "class": "firefox", "title": "Docs", "mapped": True, "workspace": {"id": 2}, "monitor": 0, "floating": False, "fullscreen": 0, "at": [800, 54], "size": [780, 934]}]
        ecran = [{"id": 0, "x": 0, "y": 0, "width": 2560, "height": 1600, "scale": 1.6, "transform": 0, "reserved": [0, 42, 0, 0], "focused": True}]
        self.programme("hyprctl", 'echo "hyprctl $*" >> "$JOURNAL"; case "$*" in *zones_dispo*) exit 7;; esac; case "$1" in clients) echo \'' + json.dumps(clients) + '\';; '
                                  'monitors) echo \'' + json.dumps(ecran) + '\';; getoption) case "$2" in *gaps_out) echo \'{"css": "10 10 10 10"}\';; '
                                  '*) echo \'{"css": "4 4 4 4"}\';; esac;; workspaces) echo \'[{"id": 2, "name": "2", "windows": 2}]\';; '
                                  'activeworkspace) echo \'{"id": 2}\';; esac')
        self.programme("notify-send", 'echo "notify $*" >> "$JOURNAL"')
        Faux.texte_ant = json.dumps({"reponse": "ok", "actions": [
            {"outil": "fenetre_zone", "args": {"adresse": "0xa1", "x": 0, "y": 0, "largeur": 60, "hauteur": 100}},
            {"outil": "fenetre_zone", "args": {"adresse": "0xb2", "x": 60, "y": 0, "largeur": 40, "hauteur": 100}},
            {"outil": "fenetre_zone", "args": {"adresse": "0xb2", "x": 70, "y": 0, "largeur": 40, "hauteur": 100}}]})
        r = self.lancer("organiser", "--bureau")
        self.assertEqual(r.returncode, 0, r.stderr)
        a = self.appels()
        self.assertIn("1600 x 1000 points", json.dumps(Faux.requetes[-1]["corps"], ensure_ascii=False), "l'IA connaît l'écran")
        self.assertIn("fenetre_zone", json.dumps(Faux.requetes[-1]["corps"], ensure_ascii=False))
        # Place utile : x 10 → 1590, y 52 (barre 42 + marge 10) → 990 ; 8 points entre deux fenêtres
        self.assertIn("hl.dsp.window.float({ action = 'set', window = 'address:0xa1' })", a)
        self.assertIn("hl.dsp.window.resize({ x = 944, y = 938, window = 'address:0xa1' })", a)
        self.assertIn("hl.dsp.window.move({ x = 10, y = 52, window = 'address:0xa1' })", a)
        self.assertIn("hl.dsp.window.resize({ x = 628, y = 938, window = 'address:0xb2' })", a)
        self.assertIn("hl.dsp.window.move({ x = 962, y = 52, window = 'address:0xb2' })", a)
        self.assertEqual(a.count("window.move({ x ="), 2, "une zone qui sort de l'écran est refusée")

    def test_ranger_ce_bureau_en_zones_en_tuiles(self):
        """Super + Ctrl + O : les zones de l'IA deviennent la disposition nc-zones du bureau (arbre de découpes) ; les
        fenêtres restent en tuiles, les raccourcis habituels marchent (avant : libres, hors du tuilage)."""
        clients = [{"address": "0xa1", "class": "code", "title": "projet", "mapped": True, "workspace": {"id": 2}, "monitor": 0, "floating": True, "fullscreen": 0, "at": [12, 54], "size": [780, 934]},
                   {"address": "0xb2", "class": "firefox", "title": "Docs", "mapped": True, "workspace": {"id": 2}, "monitor": 0, "floating": False, "fullscreen": 0, "at": [800, 54], "size": [780, 450]},
                   {"address": "0xc3", "class": "discord", "title": "Discord", "mapped": True, "workspace": {"id": 2}, "monitor": 0, "floating": False, "fullscreen": 0, "at": [800, 510], "size": [780, 450]}]
        self.programme("hyprctl", 'echo "hyprctl $*" >> "$JOURNAL"; case "$1" in clients) echo \'' + json.dumps(clients) + '\';; '
                                  'monitors) echo \'[{"id": 0, "width": 2560, "height": 1600, "scale": 1.6, "focused": true}]\';; '
                                  'workspaces) echo \'[{"id": 2, "name": "2", "windows": 3}]\';; activeworkspace) echo \'{"id": 2}\';; esac')
        self.programme("notify-send", 'echo "notify $*" >> "$JOURNAL"; case "$*" in *annuler=*) echo annuler;; esac')
        Faux.texte_ant = json.dumps({"reponse": "ok", "actions": [
            {"outil": "fenetre_zone", "args": {"adresse": "0xa1", "x": 0, "y": 0, "largeur": 60, "hauteur": 100}},
            {"outil": "fenetre_zone", "args": {"adresse": "0xb2", "x": 60, "y": 0, "largeur": 40, "hauteur": 50}},
            {"outil": "fenetre_zone", "args": {"adresse": "0xc3", "x": 60, "y": 50, "largeur": 40, "hauteur": 50}}]})
        r = self.lancer("organiser", "--bureau")
        self.assertEqual(r.returncode, 0, r.stderr)
        tout = self.appels()
        a = next(l for l in tout.splitlines() if "nc.zones_poser" in l)       # l'appel du rangement
        self.assertIn('nc.zones_poser(2, { sens = "v", r = 0.6, a = { f = "0xa1" }, b = { sens = "h", r = 0.5, a = { f = "0xb2" }, '
                      'b = { f = "0xc3" } } })', a)
        self.assertIn("hl.dsp.window.float({ action = 'unset', window = 'address:0xa1' })", a, "remise en tuiles")
        self.assertNotIn("action = 'set'", a, "plus jamais libre")
        self.assertNotIn("window.move({ x =", a)
        self.assertIn("Bureau 2 : 3 fenêtre(s) en zones", tout)
        self.assertIn("nc.zones_retirer(2)", tout, "« Annuler » rend la disposition habituelle")

    def test_tes_dispositions(self):
        """IDÉE-1 : un rangement en zones gardé est mémorisé pour ses applis (classes) ; ces applis de nouveau réunies sur
        un bureau : « Reprendre ta disposition ? » ; Oui la pose sans IA ; Non trois fois : plus proposé."""
        clients = [{"address": "0xa1", "class": "code", "mapped": True, "workspace": {"id": 2}, "floating": False, "fullscreen": 0, "at": [10, 52], "size": [940, 938]},
                   {"address": "0xb2", "class": "firefox", "mapped": True, "workspace": {"id": 2}, "floating": False, "fullscreen": 0, "at": [958, 52], "size": [632, 938]}]
        (self.home / "clients.json").write_text(json.dumps(clients))
        self.programme("hyprctl", 'echo "hyprctl $*" >> "$JOURNAL"; case "$*" in *"error(\'non\')"*) [ -e "$HOME/zones" ] || exit 7;; esac; '
                                  'case "$1" in clients) cat "$HOME/clients.json";; workspaces) echo \'[{"id": 2, "name": "2"}]\';; esac')
        self.programme("notify-send", 'echo "notify $*" >> "$JOURNAL"; cat "$HOME/reponse" 2>/dev/null')
        etat = self.home / "cache/nc/rangement-avant.json"; etat.parent.mkdir(parents=True, exist_ok=True)
        photo = {a["address"]: dict(bureau=2, libre=False, classe=a["class"], plein=0, at=a["at"], taille=a["size"]) for a in clients}
        arbre = {"sens": "v", "r": 0.6, "a": {"f": "0xa1"}, "b": {"f": "0xb2"}}
        etat.write_text(json.dumps({"portee": 2, "apres": {"fenetres": photo, "bureaux": {"2": "2"}}, "arbres": {"2": arbre}, "fenetres": {}, "bureaux": {}}))
        (self.home / "zones").write_text("")                  # les zones sont toujours posées
        self.assertEqual(self.lancer("disposition-garder", env_plus={"XDG_STATE_HOME": str(self.home / "state")}).returncode, 0)
        memo = json.loads((self.home / "state/noctalia-config/dispositions.json").read_text())
        self.assertEqual(memo["code+firefox"]["arbre"], {"sens": "v", "r": 0.6, "a": {"f": "code"}, "b": {"f": "firefox"}})
        # Plus tard, d'autres fenêtres de ces applis sur le bureau 3 : proposé, et Oui pose la disposition
        (self.home / "zones").unlink()
        clients = [dict(c, address=c["address"] + "9", workspace={"id": 3}) for c in clients][::-1]
        (self.home / "clients.json").write_text(json.dumps(clients))
        (self.home / "reponse").write_text("oui")
        env = {"XDG_STATE_HOME": str(self.home / "state")}
        self.assertEqual(self.lancer("disposition-proposer", "3", env_plus=env).returncode, 0)
        a = self.appels()
        self.assertIn("Reprendre ta disposition ?", a)
        self.assertIn('nc.zones_poser(3, { sens = "v", r = 0.6, a = { f = "0xa19" }, b = { f = "0xb29" } })', a)
        self.assertFalse(Faux.requetes, "sans IA")
        # Non trois fois : plus proposé
        (self.home / "reponse").write_text("non")
        for _ in range(3):
            (self.home / "cache/nc/disposition-proposee").unlink(missing_ok=True)
            self.lancer("disposition-proposer", "3", env_plus=env)
        (self.home / "cache/nc/disposition-proposee").unlink(missing_ok=True)
        self.journal.unlink()
        self.lancer("disposition-proposer", "3", env_plus=env)
        self.assertNotIn("Reprendre", self.appels())
        self.assertEqual(json.loads((self.home / "state/noctalia-config/dispositions.json").read_text())["code+firefox"]["refus"], 3)

    def test_chargement_garde_le_path_des_tests(self):
        """B1R3-6 : nc-ia chargé ici mettait ~/.local/bin… devant les faux du garde-fou, pour tous les tests suivants
        (python3 -m unittest tests.test_ia tests.test_garde_fou échouait)."""
        avant = os.environ["PATH"]
        charger_nc_ia("ncia_path")
        self.assertEqual(os.environ["PATH"], avant)
        self.assertIn('os.environ["PATH"] = os.pathsep.join(', (BIN / "nc-ia").read_text(), "nc-ia inchangé pour l'utilisateur")

    def test_zones_en_arbre_de_decoupes(self):
        m = charger_nc_ia("ncia_zones")
        self.assertEqual(m.arbre_zones({"a": (0, 0, 100, 100)}), {"f": "a"})
        self.assertEqual(m.arbre_zones({"a": (0, 0, 50, 100), "b": (50, 0, 50, 60), "c": (50, 60, 50, 40)}),
                         {"sens": "v", "r": 0.5, "a": {"f": "a"}, "b": {"sens": "h", "r": 0.6, "a": {"f": "b"}, "b": {"f": "c"}}})
        # Des zones avec des marges ou des trous se découpent quand même
        self.assertEqual(m.arbre_zones({"a": (0, 0, 48, 100), "b": (52, 0, 48, 100)})["sens"], "v")
        # Revue ZON-02 : un arrondi de l'IA (61 % à côté de 60 %) reste une coupe, posée entre les deux bords
        t = m.arbre_zones({"a": (0, 0, 61, 100), "b": (60, 0, 40, 50), "c": (60, 50, 40, 50)})
        self.assertEqual((t["sens"], t["r"], t["b"]["sens"]), ("v", 0.605, "h"))
        self.assertEqual(m.arbre_zones({"a": (0, 0, 33, 100), "b": (33, 0, 33, 100), "c": (66, 0, 34, 100)})["sens"], "v")
        # Un moulinet (aucune coupe ne traverse sans couper une zone) : une découpe simple, jamais rien
        moulinet = {"a": (0, 0, 60, 40), "b": (60, 0, 40, 60), "c": (40, 60, 60, 40), "d": (0, 40, 40, 60), "e": (40, 40, 20, 20)}
        t = m.arbre_zones(moulinet)
        feuilles = lambda n: [n["f"]] if "f" in n else feuilles(n["a"]) + feuilles(n["b"])
        self.assertEqual(sorted(feuilles(t)), sorted(moulinet))

    def test_agir_permissions_reverifiees(self):
        self.preparer_agent()
        self.reglages("IA_ACTIONS=confirmer\nIA_GERER_RESEAU=non\n")
        plan = json.loads(self.lancer("agir", "--json", "x").stdout)
        self.assertEqual([a["outil"] for a in plan["actions"]], ["service_redemarrer"])
        self.assertNotIn("bluetooth(", json.dumps(Faux.requetes[-1]["corps"], ensure_ascii=False), "outil non proposé à l'IA")
        # Permission retirée entre la proposition et la confirmation : refusée à l'exécution
        self.reglages("IA_ACTIONS=confirmer\nIA_GERER_RESEAU=non\nIA_GERER_SERVICES=non\n")
        d = json.loads(self.lancer("executer", plan["id"], "--json").stdout)
        self.assertFalse(d["actions"][0]["ok"])
        self.assertNotIn("restart", self.appels())
        self.reglages("IA_MODE=non\nIA_ACTIONS=confirmer\n")
        self.assertEqual(self.lancer("executer", plan["id"]).returncode, 3)

    def test_agir_lance_les_outils_du_bureau(self):
        # Revue Codex IA-01 : les programmes de ~/.local/bin (nc-brightness, nc-paquets) sont bien trouvés
        b = self.home / ".local/bin"
        for nom in ("nc-brightness", "nc-paquets"):
            (b / nom).write_text(f'#!/bin/sh\necho "{nom} $*" >> "$JOURNAL"\n')
            (b / nom).chmod(0o755)
        Faux.texte_ant = json.dumps({"reponse": "ok", "actions": [{"outil": "luminosite", "args": {"pourcent": 40}},
                                                                  {"outil": "maj_verifier", "args": {}}]})
        self.reglages("IA_ACTIONS=confirmer\nIA_GERER_MAJ=oui\n")
        plan = json.loads(self.lancer("agir", "--json", "baisse la luminosité").stdout)
        self.assertEqual([a["outil"] for a in plan["actions"]], ["luminosite", "maj_verifier"], plan)
        d = json.loads(self.lancer("executer", plan["id"], "--json").stdout)
        self.assertTrue(all(a["ok"] for a in d["actions"]), d)
        self.assertIn("nc-brightness set 40", self.appels())
        self.assertIn("nc-paquets verifier", self.appels())

    def test_executer_deux_fois_en_meme_temps(self):
        # Revue Codex IA-02 : deux confirmations simultanées, l'action n'est faite qu'une fois
        self.preparer_agent()
        self.programme("bluetoothctl", 'echo "bluetoothctl $*" >> "$JOURNAL"; sleep 1')
        self.reglages("IA_ACTIONS=confirmer\n")
        plan = json.loads(self.lancer("agir", "--json", "x").stdout)
        resultats = []
        fils = [threading.Thread(target=lambda: resultats.append(self.lancer("executer", plan["id"], "1", "--json")))
                for _ in range(2)]
        for f in fils:
            f.start()
        for f in fils:
            f.join()
        self.assertEqual(self.appels().count("bluetoothctl power off"), 1, self.appels())
        self.assertEqual(sorted(r.returncode for r in resultats), [0, 0])

    def env_test(self):
        return dict(HOME=str(self.home), XDG_CONFIG_HOME=str(self.home / ".config"), XDG_CACHE_HOME=str(self.home / "cache"),
                    XDG_RUNTIME_DIR=str(self.home / "run"), PATH=f"{self.faux}:/usr/bin:/bin", NC_LANGUE="fr",
                    JOURNAL=str(self.journal), NC_POWER_SUPPLY="secteur", NC_PROFIL="balanced", NC_IA_EN_LIGNE="1")

    def attendre_journal(self, texte, delai=10):
        import time
        fin = time.time() + delai
        while texte not in self.appels():
            self.assertLess(time.time(), fin, f"« {texte} » jamais vu : " + self.appels())
            time.sleep(0.05)

    def test_plan_interrompu_jamais_rejoue(self):
        """Revue B2-01 : le Spotlight fermé pendant une action arrêtait l'exécution (SIGTERM) avant que le plan soit
        écrit ; la confirmation suivante refaisait l'action déjà faite. Une action commencée est notée avant d'être
        lancée : interrompue, elle est montrée comme telle, jamais refaite toute seule."""
        import signal
        self.preparer_agent()
        self.reglages("IA_ACTIONS=confirmer\n")
        plan = json.loads(self.lancer("agir", "--json", "x").stdout)
        self.programme("bluetoothctl", 'case "$*" in *power*) echo "bluetoothctl $*" >> "$JOURNAL"; exec sleep 30;; esac')
        p = subprocess.Popen([str(self.home / ".local/bin/nc-ia"), "executer", plan["id"], "1", "--json"], env=self.env_test(),
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.addCleanup(lambda: p.poll() is None and p.kill())
        self.attendre_journal("bluetoothctl power off")
        p.send_signal(signal.SIGTERM)
        p.communicate(timeout=10)
        self.programme("bluetoothctl", 'echo "bluetoothctl $*" >> "$JOURNAL"')
        r = self.lancer("executer", plan["id"], "--json")
        self.assertEqual(self.appels().count("bluetoothctl power off"), 1, "une action commencée ne se refait pas")
        d = json.loads(r.stdout)
        bt = d["actions"][1]
        self.assertTrue(bt["fait"])
        self.assertFalse(bt["ok"])
        self.assertIn("interrompue", bt["resultat"])
        self.assertTrue(d["actions"][0]["ok"], "les autres actions, elles, se font")
        self.assertIn("interrompue", self.lancer("executer", plan["id"]).stdout)

    def test_ia_coupee_pendant_l_attente_du_verrou(self):
        # Revue IA-05 : une confirmation qui attend le verrou relit les réglages ; l'IA coupée entre-temps, rien ne se fait
        import fcntl, time
        self.preparer_agent()
        self.reglages("IA_ACTIONS=confirmer\n")
        plan = json.loads(self.lancer("agir", "--json", "x").stdout)
        verrou = open(self.home / "run/nc-ia/plans" / f"{plan['id']}.lock", "a")
        fcntl.flock(verrou, fcntl.LOCK_EX)
        env = dict(HOME=str(self.home), XDG_CONFIG_HOME=str(self.home / ".config"), XDG_CACHE_HOME=str(self.home / "cache"),
                   XDG_RUNTIME_DIR=str(self.home / "run"), PATH=f"{self.faux}:/usr/bin:/bin", NC_LANGUE="fr",
                   JOURNAL=str(self.journal), NC_POWER_SUPPLY="secteur", NC_PROFIL="balanced", NC_IA_EN_LIGNE="1")
        p = subprocess.Popen([str(self.home / ".local/bin/nc-ia"), "executer", plan["id"], "1", "--json"], env=env,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        time.sleep(0.8)                                    # elle a vérifié les réglages et attend le verrou
        self.reglages("IA_MODE=non\nIA_ACTIONS=confirmer\n")
        fcntl.flock(verrou, fcntl.LOCK_UN)
        verrou.close()
        p.wait(20)
        self.assertNotEqual(p.returncode, 0)
        self.assertNotIn("bluetoothctl power", self.appels())

    def test_programme_qui_echoue_apres_un_debut(self):
        # Revue Codex IA-03 : un début de réponse puis un code d'erreur, c'est un échec, pas une réponse
        self.programme("opencode", 'echo "début de réponse"; echo "plantage" >&2; exit 9')
        self.reglages("IA_MODE=manuel\nIA_CHOIX=opencode\n")
        r = self.lancer("demander", "question")
        self.assertNotEqual(r.returncode, 0, r.stdout)
        self.assertIn("incomplète", r.stderr)

    def test_programme_muet_arrete_a_l_echeance(self):
        # Revue Codex IA-04 : un programme qui n'écrit jamais de fin de ligne est arrêté à l'échéance
        self.programme("opencode", 'printf "a"; exec sleep 60')
        self.reglages("IA_MODE=manuel\nIA_CHOIX=opencode\n")
        import time
        debut = time.time()
        r = self.lancer("demander", "question", env_plus={"NC_IA_DELAI_CLI": "1"})
        self.assertLess(time.time() - debut, 15)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("délai dépassé", r.stderr)

    def test_demande_abandonnee_arrete_le_programme_et_ses_enfants(self):
        """Revue IA-07 : Échap (nc-ia arrêté par SIGTERM) laissait le programme d'IA et ses sous-processus aller au bout."""
        import signal, time
        self.programme("opencode", 'sleep 7654321 & echo "début"; sleep 7654322')
        self.reglages("IA_MODE=manuel\nIA_CHOIX=opencode\n")
        self.lancer("etat")                                    # prépare les faux programmes
        env = dict(HOME=str(self.home), XDG_CONFIG_HOME=str(self.home / ".config"), XDG_CACHE_HOME=str(self.home / "cache"),
                   XDG_RUNTIME_DIR=str(self.home / "run"), PATH=f"{self.faux}:/usr/bin:/bin", NC_LANGUE="fr",
                   JOURNAL=str(self.journal), NC_POWER_SUPPLY="secteur", NC_PROFIL="balanced", NC_IA_EN_LIGNE="1")

        def vivants():
            r = []
            for d in Path("/proc").iterdir():
                try:
                    argv = (d / "cmdline").read_bytes().split(b"\0")[:2]
                except OSError:
                    continue
                if d.name.isdigit() and argv in ([b"sleep", b"7654321"], [b"sleep", b"7654322"]):
                    r.append(int(d.name))
            return r

        def nettoyer():
            for pid in vivants():
                os.kill(pid, signal.SIGKILL)
        self.addCleanup(nettoyer)
        p = subprocess.Popen([str(self.home / ".local/bin/nc-ia"), "demander", "--flux", "question"], env=env,
                             stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
        while "début" not in p.stdout.readline():                # (la première ligne dit quelle IA répond)
            pass
        self.assertEqual(len(vivants()), 2)
        p.send_signal(signal.SIGTERM)
        self.assertEqual(p.wait(10), 143)
        time.sleep(0.3)
        self.assertEqual(vivants(), [], "ni le programme, ni son sous-processus")
        p.stdout.close()

    def test_question_du_spotlight_abandonnee_arrete_le_programme(self):
        """Revue B2-04 : nc-demander (« ? » du Spotlight) charge nc-ia comme un module : le gestionnaire de SIGTERM de
        nc-ia n'était pas posé, Échap laissait le programme d'IA et son sous-processus aller au bout."""
        import signal, time
        self.programme("opencode", 'sleep 7654323 & echo "début"; sleep 7654324')
        self.reglages("IA_MODE=manuel\nIA_CHOIX=opencode\n")
        self.lancer("etat")                                    # prépare les faux programmes

        def vivants():
            r = []
            for d in Path("/proc").iterdir():
                try:
                    argv = (d / "cmdline").read_bytes().split(b"\0")[:2]
                except OSError:
                    continue
                if d.name.isdigit() and argv in ([b"sleep", b"7654323"], [b"sleep", b"7654324"]):
                    r.append(int(d.name))
            return r

        def nettoyer():
            for pid in vivants():
                os.kill(pid, signal.SIGKILL)
        self.addCleanup(nettoyer)
        p = subprocess.Popen([str(self.home / ".local/bin/nc-demander"), "--flux", "question"], env=self.env_test(),
                             stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
        self.addCleanup(lambda: p.poll() is None and p.kill())
        while "début" not in p.stdout.readline():
            self.assertIsNone(p.poll())
        self.assertEqual(len(vivants()), 2)
        p.send_signal(signal.SIGTERM)
        self.assertEqual(p.wait(10), 143)
        fin = time.time() + 3
        while vivants() and time.time() < fin:
            time.sleep(0.05)
        self.assertEqual(vivants(), [], "ni le programme, ni son sous-processus")
        p.stdout.close()

    def test_expliquer_une_panne(self):
        """nc-panne → « Expliquer » : l'état et la fin du journal du service, secrets masqués, jamais un service inconnu."""
        self.programme("systemctl", 'case "$*" in *nc-ile.service*) printf "Description=Île\\nLoadState=loaded\\nResult=core-dump\\n";; '
                                    '*) echo "LoadState=not-found";; esac')
        self.programme("journalctl", f'echo "Erreur : token=abc123secretXYZ et cle {CLE_O} refusée"; echo "Segmentation fault"')
        r = self.lancer("panne", "nc-ile.service")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), "Bonjour")
        envoye = json.dumps(Faux.requetes[-1]["corps"], ensure_ascii=False)
        self.assertIn("nc-ile.service", envoye)
        self.assertIn("Result=core-dump", envoye)
        self.assertIn("Segmentation fault", envoye)
        self.assertNotIn("abc123secretXYZ", envoye)
        self.assertNotIn(CLE_O, envoye)
        # Plusieurs services tombés ensemble (nc-panne les regroupe) : une seule question, sur tous
        self.programme("systemctl", 'case "$*" in *nc-*.service*) printf "Description=Île\\nLoadState=loaded\\nResult=core-dump\\n";; '
                                    '*) echo "LoadState=not-found";; esac')
        self.assertEqual(self.lancer("panne", "nc-ile.service", "nc-dock.service").returncode, 0)
        envoye = json.dumps(Faux.requetes[-1]["corps"], ensure_ascii=False)
        self.assertIn("en même temps : nc-ile.service, nc-dock.service", envoye)
        self.assertNotIn(CLE_O, envoye)
        self.assertNotEqual(self.lancer("panne", "nc-ile.service", "sshd.service").returncode, 0, "un inconnu : rien")
        Faux.requetes.clear()
        self.assertNotEqual(self.lancer("panne", "sshd.service").returncode, 0)
        self.assertNotEqual(self.lancer("panne", "x;id").returncode, 0)
        self.reglages("IA_MODE=non\n")
        self.assertNotEqual(self.lancer("panne", "nc-ile.service").returncode, 0)
        self.assertFalse(Faux.requetes)

    # ── Rapports de mise à jour ──
    def test_rapport_de_mise_a_jour(self):
        depot = self.home / "depot"; depot.mkdir()
        g = lambda *a: subprocess.run(["git", "-C", str(depot), *a], capture_output=True, text=True, check=True).stdout.strip()
        g("init", "-q"); g("config", "user.email", "t@t"); g("config", "user.name", "t")
        g("commit", "-q", "--allow-empty", "-m", "départ"); avant = g("rev-parse", "HEAD")
        g("commit", "-q", "--allow-empty", "-m", "Nouvelle pastille IA ; corrections")
        (self.home / ".config/nc/depot").write_text(str(depot))
        self.programme("notify-send", 'echo "notify $*" >> "$JOURNAL"')
        self.programme("qs", "exit 0")
        r = self.lancer("rapport-maj", "config", avant, "HEAD")
        self.assertEqual(r.returncode, 0, r.stderr)
        d = json.loads((self.home / "cache/nc/rapports/config.json").read_text())
        self.assertEqual((d["resume"], d["details"], d["titre"]), ("Bonjour", ["Nouvelle pastille IA ; corrections"], "Ce qui a changé dans le bureau"))
        self.assertIn("Nouvelle pastille IA", json.dumps(Faux.requetes[-1]["corps"], ensure_ascii=False))
        self.assertIn("-A default=Voir le rapport", self.appels())
        # Système : les paquets d'avant la mise à jour
        avant_f = self.home / "avant.json"
        avant_f.write_text(json.dumps({"paquets": [{"nom": "linux", "avant": "6.1", "apres": "6.2", "important": True, "source": "depot"}]}))
        self.lancer("rapport-maj", "systeme", str(avant_f))
        self.assertEqual(json.loads((self.home / "cache/nc/rapports/systeme.json").read_text())["details"], ["★ linux 6.1 → 6.2"])
        self.assertIn("Nouveau noyau : oui", json.dumps(Faux.requetes[-1]["corps"], ensure_ascii=False), "le fait, donné à l'IA")
        # En Économie sur batterie (automatique), sans connexion : rien de plus que d'habitude
        (self.home / "cache/nc/rapports/config.json").unlink()
        Faux.requetes.clear()
        # → le rapport des faits, sans IA ni notification
        notifs = self.appels().count("notify")
        for env in ({"NC_POWER_SUPPLY": "batterie", "NC_PROFIL": "power-saver"}, {"NC_IA_EN_LIGNE": "0"}):
            (self.home / "cache/nc/rapports/config.json").unlink(missing_ok=True)
            self.assertEqual(self.lancer("rapport-maj", "config", avant, "HEAD", env_plus=env).returncode, 0)
            d = json.loads((self.home / "cache/nc/rapports/config.json").read_text())
            self.assertEqual((d["ia"], d["resume"]), ("", "- Nouvelle pastille IA"))
        self.assertFalse(Faux.requetes)
        self.assertEqual(self.appels().count("notify"), notifs, "sans IA : pas de notification de plus")
        # Système sans IA : le nombre, les importants, et redémarrer pour un nouveau noyau
        self.lancer("rapport-maj", "systeme", str(avant_f), env_plus={"NC_IA_EN_LIGNE": "0"})
        d = json.loads((self.home / "cache/nc/rapports/systeme.json").read_text())
        self.assertEqual(d["resume"], "1 paquet(s) mis à jour.\n- **linux 6.1 → 6.2**\nRedémarre pour utiliser le nouveau noyau.")
        # Revue RPT-01 : linux-firmware (ou les en-têtes) n'est pas un noyau, sans IA comme avec
        avant_f.write_text(json.dumps({"paquets": [{"nom": "linux-firmware", "avant": "1", "apres": "2", "important": True, "source": "depot"},
                                                   {"nom": "linux-api-headers", "avant": "1", "apres": "2", "source": "depot"}]}))
        self.lancer("rapport-maj", "systeme", str(avant_f), env_plus={"NC_IA_EN_LIGNE": "0"})
        self.assertNotIn("noyau", json.loads((self.home / "cache/nc/rapports/systeme.json").read_text())["resume"])
        self.lancer("rapport-maj", "systeme", str(avant_f))
        self.assertIn("Nouveau noyau : non", json.dumps(Faux.requetes[-1]["corps"], ensure_ascii=False))

    def test_rapport_systeme_vrai_nombre_et_faits(self):
        """Revue B1 R2 : au-delà de 200 paquets, le rapport disait 200 ; R1 R3 : restés en attente et échec, dits tels quels."""
        maj = self.home / "maj.json"
        maj.write_text(json.dumps({"paquets": [{"nom": f"p{i}", "avant": "1", "apres": "2", "source": "depot"} for i in range(450)],
                                   "total": 450, "en_attente": 2, "en_attente_noms": ["firefox-esr", "zsh"], "echec": 1}))
        self.lancer("rapport-maj", "systeme", str(maj), env_plus={"NC_IA_EN_LIGNE": "0"})
        d = json.loads((self.home / "cache/nc/rapports/systeme.json").read_text())
        self.assertEqual((d["nombre"], len(d["details"]), d["en_attente"], d["echec"]), (450, 200, 2, 1), "la coupe à l'affichage seulement")
        self.assertTrue(d["resume"].startswith("450 paquet(s) mis à jour."), d["resume"])
        self.assertIn("La mise à jour a échoué (code 1)", d["resume"])
        self.assertIn("2 resté(s) en attente : firefox-esr, zsh.", d["resume"])
        # Avec l'IA : 200 lignes et le vrai total, les faits donnés, et gardés dans le résumé quoi qu'elle réponde
        Faux.requetes.clear()
        self.lancer("rapport-maj", "systeme", str(maj))
        corps = json.dumps(Faux.requetes[-1]["corps"], ensure_ascii=False)
        self.assertIn("… et 250 autres (450 en tout).", corps)
        self.assertNotIn("p449", corps)
        d = json.loads((self.home / "cache/nc/rapports/systeme.json").read_text())
        self.assertEqual(d["nombre"], 450)
        self.assertIn("2 resté(s) en attente", d["resume"])

    # ── Clés ──
    def test_cles_privees_jamais_affichees(self):
        r = self.lancer("cle", "openai", entree=CLE_O + "\n")
        self.assertEqual(r.returncode, 0, r.stderr)
        f = self.home / ".config/nc/ia.conf"
        self.assertEqual(stat.S_IMODE(f.stat().st_mode), 0o600)
        self.assertIn("OPENAI_API_KEY=" + CLE_O, f.read_text())
        for args in (("etat",), ("etat", "--json"), ("cles",), ("cles", "--json")):
            r = self.lancer(*args)
            self.assertNotIn(CLE_O, r.stdout + r.stderr)
            self.assertNotIn(CLE_A, r.stdout + r.stderr)
        self.assertIn("…6789", self.lancer("cles").stdout)
        r = self.lancer("cle", "openai", entree="pas une clé ; rm -rf\n")
        self.assertEqual(r.returncode, 1)
        self.assertIn("OPENAI_API_KEY=" + CLE_O, f.read_text(), "une saisie invalide ne remplace pas la clé")

    def test_url_en_clair_refusee(self):
        self.cles(f"ANTHROPIC_API_KEY={CLE_A}\nURL_ANTHROPIC=http://exemple.com/v1\n")
        r = self.lancer("demander", "--ia", "anthropic", "q")
        self.assertEqual(r.returncode, 1)
        self.assertIn("https://", r.stderr)
        self.assertFalse(Faux.requetes)

    # ── Tout couper ──
    def test_ia_coupee_partout(self):
        self.reglages("IA_MODE=non\n")
        r = self.lancer("demander", "--flux", "q")
        self.assertEqual(r.returncode, 3)
        self.assertIn("désactivée", r.stdout)
        self.assertEqual(self.lancer("actif").returncode, 1)
        self.assertTrue(json.loads(self.lancer("--ia", "--json", prog="nc-demander").stdout)["coupee"])
        r = self.lancer("demander", "--flux", "q", prog="nc-assistant")
        self.assertIn("désactivée", r.stdout)
        r = self.lancer("start", prog="nc-dictee")
        self.assertFalse(json.loads(r.stdout)["ok"])
        r = self.lancer("requete", entree="{}\n", prog="nc-jarvis")
        self.assertFalse(json.loads(r.stdout)["ok"])
        # Un hook d'agent ne laisse aucune trace dans l'île (et rend la main tout de suite)
        r = self.lancer("hook", entree=json.dumps({"hook_event_name": "UserPromptSubmit", "session_id": "s", "prompt": "x"}),
                        prog="nc-claude")
        self.assertEqual(r.returncode, 0)
        self.assertFalse((self.home / "run/nc-claude/etat.json").exists())
        self.assertFalse(Faux.requetes, "rien n'est envoyé quand l'IA est coupée")

    def test_spotlight_peut_imposer_ou_couper(self):
        self.reglages("SPOTLIGHT_IA=non\n")
        d = json.loads(self.lancer("--ia", "--json", prog="nc-demander").stdout)
        self.assertTrue(d["coupee"])
        self.reglages("SPOTLIGHT_IA=anthropic\n")
        d = json.loads(self.lancer("--ia", "--json", prog="nc-demander").stdout)
        self.assertEqual((d["nom"], d["agent"], d["coupee"]), ("Claude (API Anthropic)", "claude", False))
        self.reglages("SPOTLIGHT_IA=assistant\n")       # ancienne valeur : JARVIS, pas configuré ici
        self.assertEqual(json.loads(self.lancer("--ia", "--json", prog="nc-demander").stdout)["nom"], "")

    # ── Raccourci décrit en mots (« + Ajouter » de la fiche Super + /) ──
    def preparer_raccourci(self):
        b = self.home / ".local/bin"
        for f in ("nc-raccourci", "nc-keys"):
            os.symlink(BIN / f, b / f)
        (b / "nc-apps").write_text('#!/bin/sh\necho \'[{"id": "firefox", "name": "Firefox", "exe": "firefox"}, '
                                   '{"id": "org.gnome.Nautilus", "name": "Fichiers", "exe": "nautilus"}]\'\n')
        (b / "nc-apps").chmod(0o755)
        self.programme("hyprctl", 'echo "hyprctl $*" >> "$JOURNAL"')        # jamais appelé pour vérifier

    def raccourci(self, reponse, *args):
        Faux.texte_ant = reponse if isinstance(reponse, str) else json.dumps(reponse, ensure_ascii=False)
        r = self.lancer("raccourci", "--json", *(args or ("Super + F ouvre Firefox sur le bureau 2",)))
        return r, json.loads(r.stdout)

    def test_raccourci_propose_et_verifie(self):
        self.preparer_raccourci()
        r, d = self.raccourci({"touches": "super + shift + f", "cible": "firefox", "nom": "Firefox"})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(d, {"ok": True, "touches": "Super+Maj+F", "cible": "firefox", "genre": "appli", "nom": "Firefox",
                             "detail": "firefox (appli)"})
        q = Faux.requetes[-1]["corps"]
        self.assertIn("JSON", q["system"], "la consigne de l'usage « raccourci »")
        texte = json.dumps(q["messages"], ensure_ascii=False)
        self.assertIn("Super + F ouvre Firefox sur le bureau 2", texte)
        self.assertIn("org.gnome.Nautilus : Fichiers", texte, "l'IA connaît les applis installées")
        self.assertNotIn("hyprctl", self.appels(), "rien n'est demandé à Hyprland, rien n'est ajouté")
        self.assertFalse((self.home / ".config/nc/raccourcis.conf").exists(), "proposé seulement, jamais ajouté")
        # Entre balises de code, un bureau, une page de l'île (alias), une touche nommée
        r, d = self.raccourci('```json\n{"touches": "Super+Ctrl+2", "cible": "Bureau 2", "nom": ""}\n```')
        self.assertEqual((d["touches"], d["cible"], d["genre"], d["nom"]), ("Super+Ctrl+2", "bureau 2", "bureau", "Bureau 2"))
        r, d = self.raccourci({"touches": "Alt+enter", "cible": "île wifi", "nom": "Réseau"})
        self.assertEqual((d["touches"], d["cible"], d["genre"]), ("Alt+Entrée", "ile reseau", "ile"))
        # Une commande seulement si son programme existe
        self.programme("monscript", "true")
        r, d = self.raccourci({"touches": "Super+M", "cible": "monscript --vite", "nom": "Mon script"})
        self.assertEqual((d["ok"], d["genre"], d["cible"]), (True, "commande", "monscript --vite"))

    def test_raccourci_refuse(self):
        self.preparer_raccourci()
        for reponse, attendu in (("Voici votre raccourci !", "lisible"), ({}, "pas un raccourci"),
                                 ({"touches": "F", "cible": "firefox"}, "modificateur"),
                                 ({"touches": "Super+Hyper+F", "cible": "firefox"}, "modificateur inconnu"),
                                 ({"touches": "Super+F", "cible": "bureau 11"}, "Bureau inconnu"),
                                 ({"touches": "Super+F", "cible": "ile cuisine"}, "Page de l'île inconnue"),
                                 ({"touches": "Super+F", "cible": "appli-inventee --x"}, "Cible inconnue"),
                                 ({"touches": "Super+F", "cible": ""}, "incomplète"),
                                 ({"touches": ["Super", "F"], "cible": "firefox"}, "incomplète")):
            r, d = self.raccourci(reponse)
            self.assertEqual(r.returncode, 1, reponse)
            self.assertFalse(d["ok"])
            self.assertIn(attendu, d["erreur"], reponse)
        self.assertFalse((self.home / ".config/nc/raccourcis.conf").exists())

    def test_raccourci_ia_coupee(self):
        self.preparer_raccourci()
        self.reglages("IA_MODE=non\n")
        r, d = self.raccourci({"touches": "Super+F", "cible": "firefox"})
        self.assertEqual(r.returncode, 3)
        self.assertIn("désactivée", d["erreur"])
        self.assertFalse(Faux.requetes, "rien n'est envoyé quand l'IA est coupée")

    # ── Balisage d'outil écrit en texte (Neovim : « transformer » remplaçait la sélection par <invoke …>) ──
    BALISAGE = ['<invoke name="Bash">\n<parameter name="command">pwd; find ../.. -maxdepth 3</parameter>\n</invoke>\n',
                "erreur\n"] * 3
    MESSAGE_OUTILS = "L'IA a voulu utiliser des outils qui ne sont pas disponibles ici."

    def faux_claude(self, morceaux):
        """Un faux Claude Code (stream-json) qui envoie ces morceaux de texte, un par événement."""
        lignes = [json.dumps({"type": "stream_event", "event": {"delta": {"type": "text_delta", "text": m}}}) for m in morceaux]
        lignes.append(json.dumps({"type": "result", "is_error": False, "result": "".join(morceaux)}))
        (self.faux / "claude.jsonl").write_text("\n".join(lignes) + "\n")
        self.programme("claude", f'printf "%s\\n" "$@" >> "$JOURNAL"; cat "{self.faux / "claude.jsonl"}"')

    def verifier_refus_outils(self, r, flux=False):
        self.assertNotEqual(r.returncode, 0, r.stdout)
        self.assertNotIn("<invoke", r.stdout)
        self.assertNotIn("<parameter", r.stdout)
        if flux:
            lignes, _ = self.flux(r)
            self.assertTrue(lignes[-1].get("erreur"), lignes)
            self.assertIn(self.MESSAGE_OUTILS, lignes[-1]["t"])
            self.assertIn("(Espace i a)", lignes[-1]["t"])
        else:
            self.assertIn(self.MESSAGE_OUTILS, r.stderr)
            self.assertIn("(Espace i a)", r.stderr)
        # Pas de relais : ni l'API Anthropic ni un autre programme n'ont été appelés, et l'IA n'est pas notée en échec
        self.assertNotIn("prend le relais", r.stdout + r.stderr)
        self.assertFalse([q for q in Faux.requetes if q["chemin"].startswith("/ant")], "aucun relais")
        e = self.home / "run/nc-ia/echecs.json"
        echecs = json.loads(e.read_text()) if e.exists() else {}
        self.assertEqual(echecs, {}, "la demande ne convenait pas : pas une panne de l'IA")

    def test_claude_qui_ecrit_des_appels_d_outils(self):
        self.reglages("IA_PREFERENCE=abonnements\n")         # Claude Code d'abord, l'API Anthropic en relais possible
        self.faux_claude(self.BALISAGE)
        r = self.lancer("texte", "transformer en code C", "--stdin", entree="Écrire un programme qui lit un entier.")
        self.verifier_refus_outils(r)
        self.assertEqual(r.stdout.strip(), "")
        self.assertIn("Tu n'as accès à aucun outil, aucun fichier et aucune commande", self.journal.read_text())
        # En flux, le motif coupé entre deux morceaux (« <inv » puis « oke ») est vu, après un début de réponse normal
        debut = "Voici ce que je vais faire pour cet exercice, étape par étape, sans rien oublier.\n"
        self.faux_claude([debut, "Je regarde le projet : <inv", 'oke name="Bash">', "<parameter name=\"command\">pwd",
                          "</parameter></invoke>"])
        r = self.lancer("texte", "transformer", "--stdin", "--flux", entree="exercice")
        self.verifier_refus_outils(r, flux=True)
        _, texte = self.flux(r)
        # Le texte d'avant passe (sans attendre : seul « <inv » est retenu), le balisage jamais
        self.assertTrue(texte.startswith(debut + "Je regarde le projet : \n…"), texte)
        self.assertNotIn("<inv", texte)

    def test_motif_coupe_sur_parameter(self):
        self.reglages("IA_MODE=manuel\nIA_CHOIX=claude\n")
        self.faux_claude(["Je ", "lance <para", "meter na", "me=\"x\">"])
        r = self.lancer("demander", "--flux", "question")
        self.verifier_refus_outils(r, flux=True)

    def test_codex_et_gemini_qui_ecrivent_des_appels_d_outils(self):
        sortie = "".join(self.BALISAGE).replace('"', '\\"')
        for ident, prog in (("codex", "codex"), ("gemini-cli", "gemini")):
            with self.subTest(ident):
                Faux.requetes.clear()
                self.programme(prog, f'printf "%s" "{sortie}"')
                self.reglages(f"IA_MODE=manuel\nIA_CHOIX={ident}\n")
                r = self.lancer("texte", "transformer", "--stdin", entree="exercice")
                self.verifier_refus_outils(r)
                r = self.lancer("demander", "--flux", "question")
                self.verifier_refus_outils(r, flux=True)
        # Un JSON d'outil en tête de réponse, aussi
        self.programme("codex", 'echo \'{"type": "tool_use", "name": "Bash", "input": {"command": "ls"}}\'')
        self.reglages("IA_MODE=manuel\nIA_CHOIX=codex\n")
        self.verifier_refus_outils(self.lancer("demander", "question"))

    def test_le_mot_invoke_et_un_json_legitime_passent(self):
        Faux.texte_ant = "En Python, on invoke une fonction par son nom suivi de parenthèses : f(x)."
        r = self.lancer("demander", "--flux", "question")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.flux(r)[1], Faux.texte_ant)
        Faux.texte_ant = '{"actions": [{"type": "wifi", "args": {"etat": "on"}}], "tool": "aucun"}'
        r = self.lancer("demander", "question")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), Faux.texte_ant)
        # Une réponse courte (moins que la fenêtre retenue) arrive entière
        Faux.texte_ant = "Oui."
        self.assertEqual(self.lancer("demander", "question").stdout.strip(), "Oui.")
        # La consigne des usages texte et question dit qu'il n'y a aucun outil
        for args in (("demander", "question"), ("texte", "resumer", "--stdin")):
            self.lancer(*args, entree="un texte")
            envoye = json.dumps(Faux.requetes[-1]["corps"], ensure_ascii=False)
            self.assertIn("Tu n'as accès à aucun outil, aucun fichier et aucune commande", envoye)

    def test_etat_donne_le_programme_agentique(self):
        self.programme("claude", "exit 0")
        self.reglages("IA_MODE=manuel\nIA_CHOIX=anthropic\n")
        e = json.loads(self.lancer("etat", "--json").stdout)
        self.assertEqual(e["choix"], "anthropic")                          # les champs d'avant restent
        self.assertEqual(e["choisie"], {"id": "anthropic", "nom": "Claude (API Anthropic)", "disponible": True,
                                        "cli": "claude", "cli_disponible": True})
        self.assertEqual((e["usages"]["texte"]["id"], e["usages"]["texte"]["cli"]), ("anthropic", "claude"))
        ias = {i["id"]: i for i in e["ias"]}
        self.assertEqual((ias["codex"]["cli"], ias["gemini-cli"]["cli"], ias["jarvis"]["cli"]), ("codex", "gemini", ""))
        self.assertTrue(ias["codex"]["cli_disponible"])                    # le faux codex est installé
        self.assertFalse(ias["jarvis"]["cli_disponible"])
        self.assertIn("agent", ias["codex"])
        # Sans connexion, aucun programme agentique n'est prêt
        e = json.loads(self.lancer("etat", "--json", env_plus={"NC_IA_EN_LIGNE": "0"}).stdout)
        self.assertFalse(e["choisie"]["cli_disponible"])

    # ── Terminal ──
    @unittest.skipUnless(shutil.which("zsh"), "zsh requis")
    def test_zsh(self):
        f = REPO / "home/.config/nc/ia.zsh"
        r = subprocess.run(["zsh", "-n", str(f)], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        texte = f.read_text()
        self.assertIn("bindkey '^[i' _nc_ia_commande", texte)
        self.assertIn("(( ! $+commands[ia] ))", texte, "ne cache pas une commande « ia » déjà installée")
        self.assertNotRegex(texte, r"BUFFER=.*\n\s*zle accept-line", "la commande proposée n'est jamais lancée seule")
        self.assertIn("ia.zsh", (REPO / "home/.zshrc").read_text())


if __name__ == "__main__":
    unittest.main()

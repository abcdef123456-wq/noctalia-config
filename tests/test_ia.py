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
        self.assertEqual(texte, "Salut toi", r.stdout + r.stderr)
        self.assertEqual([l["id"] for l in lignes if "id" in l], ["anthropic", "openai"])
        oai = [q for q in Faux.requetes if q["chemin"] == "/oai/chat/completions"][-1]
        self.assertEqual(oai["entetes"]["authorization"], "Bearer " + CLE_O)
        self.assertEqual(oai["corps"]["model"], "gpt-5.1-mini", "le plus récent des « mini » de la liste")
        self.assertIn("max_completion_tokens", oai["corps"])
        # L'échec est retenu : la question suivante part d'abord vers OpenAI, sans attendre Anthropic
        Faux.requetes.clear()
        r = self.lancer("quelle", "--json")
        self.assertEqual(json.loads(r.stdout)["id"], "openai")

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

    def test_masquage_rapide_sur_un_long_mot(self):
        """Revue PRIV-02 : 12 000 caractères sans espace (base64, JSON minifié) prenaient ~10 s (expression quadratique)."""
        import importlib.machinery, importlib.util, time
        l = importlib.machinery.SourceFileLoader("ncia_cav", str(BIN / "nc-ia"))
        m = importlib.util.module_from_spec(importlib.util.spec_from_loader("ncia_cav", l)); l.exec_module(m)
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

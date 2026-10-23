"""nc-noeud (issue #12) : ce PC comme « nœud » de JARVIS, avec confirmation. Un faux serveur WebSocket local
(bibliothèque standard) joue JARVIS-BIS (/api/node/ws) ; un faux qs joue l'île (il répond « autoriser », « refuser »
ou rien) ; playerctl, notify-send, wl-copy, wl-paste, grim et loginctl sont faux et notent leurs appels. HOME,
XDG_RUNTIME_DIR et XDG_STATE_HOME temporaires : rien ne touche la vraie session ni un vrai serveur.
La carte de l'île (Noeud.qml, ConfirmationNoeud.qml) est essayée hors écran : Autoriser et Refuser écrivent la bonne
réponse."""
import base64
import contextlib
import hashlib
import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import shutil
import socket
import stat
import struct
import subprocess
import sys
import tempfile
import time
import unittest
import unittest.mock
import uuid
import asyncio

REPO = Path(__file__).resolve().parents[1]
BIN = REPO / "home/.local/bin"
QML = REPO / "home/.config/quickshell/nc-ile"
GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
SECRET = "cle-de-test-" + uuid.uuid4().hex
PNG = b"\x89PNG\r\n\x1a\nfausse-capture"

# Faux programmes : le dossier de test vient de leur propre chemin (<home>/.local/bin), jamais de $HOME
ENTETE = '#!/bin/sh\nH="$(cd "$(dirname "$0")/../.." && pwd)"\n'
FAUX = {
    # L'île : « qs -c nc-ile ipc call ile noeud » ; <home>/ile dit quoi répondre (autoriser, refuser, silence, absente)
    "qs": ENTETE + '''echo "qs $*" >> "$H/appels"
[ "$5 $6" = "ile noeud" ] || exit 1
mode="$(cat "$H/ile" 2>/dev/null)"
[ "$mode" = absente ] && exit 1
f="$XDG_RUNTIME_DIR/nc-noeud/demande.json"
if [ -f "$f" ]; then
  cp "$f" "$H/derniere-demande.json"
  if [ "$mode" = autoriser ] || [ "$mode" = refuser ]; then
    id="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["id"])' "$f")"
    printf %s "$mode" > "$XDG_RUNTIME_DIR/nc-noeud/reponses/$id"
  fi
fi
echo oui
''',
    "playerctl": ENTETE + 'echo "playerctl $*" >> "$H/appels"; echo Playing\n',
    "loginctl": ENTETE + 'echo "loginctl $*" >> "$H/appels"\n',
    "wl-copy": ENTETE + 'echo "wl-copy $(cat)" >> "$H/appels"\n',
    "wl-paste": ENTETE + 'echo "wl-paste $*" >> "$H/appels"; printf "texte copié"\n',
    "grim": ENTETE + 'echo "grim $*" >> "$H/appels"; printf "\\211PNG\\r\\n\\032\\nfausse-capture" > "$1"\n',
    # Sans île : <home>/notif dit si notify-send connaît --action et quel bouton est pressé
    "notify-send": ENTETE + '''echo "notify-send $*" >> "$H/appels"
mode="$(cat "$H/notif" 2>/dev/null)"
if [ "$1" = --help ]; then [ "$mode" = sans-boutons ] || echo "  -A, --action=[NAME=]Text..."; exit 0; fi
case "$*" in *"-A autoriser="*) [ "$mode" = sans-boutons ] || echo "$mode" ;; esac
exit 0
''',
}


class FauxServeur:
    """JARVIS-BIS réduit à /api/node/ws : poignée de main RFC 6455, trames texte, ping/pong."""

    def __init__(self):
        self.ecoute = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.ecoute.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.ecoute.bind(("127.0.0.1", 0))
        self.ecoute.listen(4)
        self.port = self.ecoute.getsockname()[1]
        self.c = None
        self.tampon = b""
        self.autres = []                   # messages reçus en attendant une réponse (confirm_request…)

    def fermer(self):
        for s in (self.c, self.ecoute):
            with contextlib.suppress(OSError, AttributeError):
                s.close()

    def accepter(self, delai=15):
        self.ecoute.settimeout(delai)
        self.c, _ = self.ecoute.accept()
        self.c.settimeout(delai)
        donnees = b""
        while b"\r\n\r\n" not in donnees:
            d = self.c.recv(4096)
            if not d:
                raise EOFError
            donnees += d
        tete, self.tampon = donnees.split(b"\r\n\r\n", 1)
        lignes = tete.decode("iso-8859-1").split("\r\n")
        self.requete = lignes[0]
        self.entetes = {l.split(":", 1)[0].strip().lower(): l.split(":", 1)[1].strip() for l in lignes[1:] if ":" in l}
        accepte = base64.b64encode(hashlib.sha1((self.entetes["sec-websocket-key"] + GUID).encode()).digest()).decode()
        self.c.sendall(("HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
                        f"Sec-WebSocket-Accept: {accepte}\r\n\r\n").encode())

    def _lire(self, n):
        while len(self.tampon) < n:
            d = self.c.recv(65536)
            if not d:
                raise EOFError
            self.tampon += d
        out, self.tampon = self.tampon[:n], self.tampon[n:]
        return out

    def _trame(self, opcode, donnees):
        n = len(donnees)
        tete = bytes([0x80 | opcode]) + (bytes([n]) if n <= 125 else
                                         (bytes([126]) + struct.pack("!H", n) if n <= 0xFFFF else bytes([127]) + struct.pack("!Q", n)))
        self.c.sendall(tete + donnees)

    def recevoir(self):
        while True:
            b1, b2 = self._lire(2)
            opcode, n = b1 & 0x0F, b2 & 0x7F
            assert b2 & 0x80, "trame du client non masquée"
            if n == 126:
                n = struct.unpack("!H", self._lire(2))[0]
            elif n == 127:
                n = struct.unpack("!Q", self._lire(8))[0]
            cle = self._lire(4)
            d = bytes(x ^ cle[i % 4] for i, x in enumerate(self._lire(n))) if n < 4096 else \
                (int.from_bytes(self._lire(n), "big") ^ int.from_bytes((cle * (n // 4 + 1))[:n], "big")).to_bytes(n, "big")
            if opcode == 0x9:
                self._trame(0xA, d)
                continue
            if opcode == 0x8:
                raise EOFError
            if opcode == 0x1:
                return json.loads(d.decode())

    def envoyer(self, objet):
        self._trame(0x1, json.dumps(objet).encode())

    def demander(self, action, params=None, timeout=None):
        rid = str(uuid.uuid4())
        trame = {"type": "action", "req_id": rid, "action": action, "params": params or {}}
        if timeout is not None:
            trame["timeout"] = timeout
        self.envoyer(trame)
        while True:
            m = self.recevoir()
            if m.get("type") == "response" and m.get("req_id") == rid:
                return m
            self.autres.append(m)


class Base(unittest.TestCase):
    def setUp(self):
        d = tempfile.TemporaryDirectory(prefix="nc-noeud-")
        self.addCleanup(d.cleanup)
        self.home = Path(d.name)
        self.bin = self.home / ".local/bin"
        self.bin.mkdir(parents=True)
        for nom in ("nc-noeud", "nc-assistant"):
            shutil.copy2(BIN / nom, self.bin / nom)
        for nom, texte in FAUX.items():
            (self.bin / nom).write_text(texte)
            (self.bin / nom).chmod(0o755)
        self.run_dir = self.home / "run"
        self.run_dir.mkdir(mode=0o700)
        self.etat = self.home / ".local/state"
        (self.home / ".config/nc").mkdir(parents=True)
        self.serveur = FauxServeur()
        self.addCleanup(self.serveur.fermer)
        self.configurer(f"http://127.0.0.1:{self.serveur.port}")
        self.regler(NOEUD_JARVIS="oui")
        self.ile("autoriser")
        self.env = dict(os.environ, HOME=str(self.home), XDG_RUNTIME_DIR=str(self.run_dir), XDG_STATE_HOME=str(self.etat),
                        PATH=str(self.bin) + ":/usr/bin:/bin", NC_LANGUE="fr")
        for cle in ("XDG_CONFIG_HOME", "NC_NOEUD_DELAI"):
            self.env.pop(cle, None)
        self.proc = None

    def configurer(self, url):
        f = self.home / ".config/nc/assistant.conf"
        f.write_text(f'URL="{url}"\nSECRET_KEY="{SECRET}"\nUSER_ID="test"\nCLIENT_ID="portable-test"\n')
        f.chmod(0o600)

    def regler(self, **vals):
        (self.home / ".config/nc/reglages.conf").write_text("".join(f"{k}={v}\n" for k, v in vals.items()))

    def ile(self, mode):
        (self.home / "ile").write_text(mode)

    def appels(self):
        f = self.home / "appels"
        return f.read_text().splitlines() if f.exists() else []

    def demarrer(self, **env):
        self.proc = subprocess.Popen([sys.executable, str(self.bin / "nc-noeud")], env=dict(self.env, **env),
                                     stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.addCleanup(self.arreter)
        self.serveur.accepter()
        self.register = self.serveur.recevoir()
        return self.register

    def arreter(self):
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(5)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait()
        if self.proc:
            for f in (self.proc.stdout, self.proc.stderr):
                f.close()

    def journal(self):
        f = self.etat / "noctalia-config/noeud.log"
        return f.read_text() if f.exists() else ""


class Connexion(Base):
    def test_register_avec_le_secret_dans_l_en_tete_jamais_dans_l_url(self):
        r = self.demarrer()
        self.assertEqual(self.serveur.requete, "GET /api/node/ws HTTP/1.1")
        self.assertNotIn("secret", self.serveur.requete.lower())
        self.assertNotIn(SECRET, self.serveur.requete)
        self.assertEqual(self.serveur.entetes.get("x-secret-key"), SECRET)
        self.assertEqual(r["type"], "register")
        self.assertEqual(r["node_id"], "portable-test")
        self.assertEqual(r["os"], "linux")
        self.assertTrue(r["hostname"])
        for cap in ("exec", "read_file", "write_file", "screenshot", "media", "notify", "clipboard_get", "clipboard_set"):
            self.assertIn(cap, r["capabilities"])
        self.serveur.envoyer({"type": "ping"})
        self.assertEqual(self.serveur.recevoir(), {"type": "pong"})

    def test_ws_vers_un_hote_public_refuse(self):
        self.configurer("http://jarvis.example.com:8000")
        r = subprocess.run([sys.executable, str(self.bin / "nc-noeud")], env=self.env, capture_output=True, text=True, timeout=20)
        self.assertEqual(r.returncode, 3, r.stderr)
        self.assertIn("ws://", r.stderr)
        self.assertIn("https://", r.stderr)
        self.assertNotIn(SECRET, r.stdout + r.stderr)

    def test_pilotage_coupe_le_client_s_arrete(self):
        self.regler(NOEUD_JARVIS="non")
        r = subprocess.run([sys.executable, str(self.bin / "nc-noeud")], env=self.env, capture_output=True, text=True, timeout=20)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_adresses_autorisees(self):
        chargeur = importlib.machinery.SourceFileLoader("nc_noeud_test", str(self.bin / "nc-noeud"))
        m = importlib.util.module_from_spec(importlib.util.spec_from_loader(chargeur.name, chargeur))
        chargeur.exec_module(m)
        m.A = m.charger_assistant()
        self.assertEqual(m.adresse_ws({"URL": "https://jarvis.example.com/base"}), ("jarvis.example.com", 443, True, "/base/api/node/ws"))
        self.assertEqual(m.adresse_ws({"URL": "http://192.168.1.20:8000"})[2], False)          # réseau local
        self.assertEqual(m.adresse_ws({"URL": "http://100.101.102.103:8000"})[2], False)       # Tailscale
        self.assertEqual(m.adresse_ws({"URL": "http://pc.tail1234.ts.net:8000"})[2], False)
        for url in ("http://jarvis.example.com", "http://8.8.8.8:8000"):
            with self.assertRaises(m.Definitif):
                m.adresse_ws({"URL": url})


class Politique(Base):
    def test_sans_confirmation(self):
        self.ile("absente")                       # aucune carte : elles ne doivent pas en demander
        self.demarrer()
        r = self.serveur.demander("media", {"subaction": "play-pause"})
        self.assertTrue(r["success"], r)
        r = self.serveur.demander("notify", {"title": "Coucou", "body": "<b>x</b>"})
        self.assertTrue(r["success"], r)
        r = self.serveur.demander("clipboard_get")
        self.assertEqual(r.get("clipboard"), "texte copié")
        r = self.serveur.demander("lock")
        self.assertTrue(r["success"], r)
        (self.home / "Documents").mkdir()
        (self.home / "Documents/a.txt").write_text("secret du fichier")
        r = self.serveur.demander("list_files", {"path": "~/Documents"})
        self.assertEqual([i["name"] for i in r["items"]], ["a.txt"])
        self.assertNotIn("secret du fichier", json.dumps(r))
        a = self.appels()
        self.assertIn("playerctl play-pause", a)
        self.assertIn("loginctl lock-session", a)
        self.assertTrue(any(l.startswith("notify-send -a JARVIS -- Coucou &lt;b&gt;x&lt;/b&gt;") for l in a), a)
        self.assertFalse([l for l in a if l.startswith("qs ")], "aucune confirmation demandée")
        # Commande de musique hors liste : refusée
        r = self.serveur.demander("media", {"subaction": "--player=x"})
        self.assertFalse(r["success"])

    def test_sans_confirmation_desactive(self):
        self.regler(NOEUD_JARVIS="oui", NOEUD_SANS_CONFIRMATION="non")
        self.ile("refuser")
        self.demarrer()
        r = self.serveur.demander("media", {"subaction": "next"})
        self.assertFalse(r["success"])
        self.assertTrue(r.get("denied"))
        self.assertNotIn("playerctl next", self.appels())
        self.assertIn("qs -c nc-ile ipc call ile noeud", self.appels())

    def test_commande_autorisee(self):
        self.demarrer()
        marque = self.home / "fait"
        cmd = f"echo bonjour; touch {marque}"
        r = self.serveur.demander("exec", {"command": cmd})
        self.assertTrue(r["success"], r)
        self.assertEqual(r["stdout"], "bonjour")
        self.assertTrue(marque.exists())
        demande = json.loads((self.home / "derniere-demande.json").read_text())
        self.assertEqual(demande["texte"], cmd, "la commande entière est montrée")
        self.assertEqual(demande["resume"], "exécuter cette commande")
        self.assertEqual(demande["serveur"], "127.0.0.1")
        self.assertEqual(demande["court"], 400)
        self.assertLessEqual(demande["expire"] - time.time(), 26)
        self.assertFalse((self.run_dir / "nc-noeud/demande.json").exists(), "la demande est retirée après la réponse")
        self.assertEqual(stat.S_IMODE((self.run_dir / "nc-noeud").stat().st_mode), 0o700)

    def test_confirmation_refusee_rien_n_est_execute(self):
        self.ile("refuser")
        self.demarrer()
        marque = self.home / "fait"
        r = self.serveur.demander("exec", {"command": f"touch {marque}"})
        self.assertFalse(r["success"])
        self.assertTrue(r.get("denied"))
        self.assertFalse(marque.exists())
        r = self.serveur.demander("write_file", {"path": "~/notes.txt", "content": "x"})
        self.assertFalse(r["success"])
        self.assertFalse((self.home / "notes.txt").exists())
        r = self.serveur.demander("clipboard_set", {"text": "à copier"})
        self.assertFalse(r["success"])
        r = self.serveur.demander("screenshot")
        self.assertFalse(r["success"])
        self.assertFalse([l for l in self.appels() if l.startswith(("wl-copy", "grim"))])
        self.assertIn("refusé", self.journal())

    def test_expiration_refuse(self):
        self.ile("silence")
        self.demarrer(NC_NOEUD_DELAI="2")
        marque = self.home / "fait"
        debut = time.monotonic()
        r = self.serveur.demander("exec", {"command": f"touch {marque}"})
        self.assertLess(time.monotonic() - debut, 10)
        self.assertFalse(r["success"])
        self.assertIn("en 2 s", r["error"])
        self.assertFalse(marque.exists())
        self.assertIn("expiré", self.journal())

    def test_delai_de_l_action_dans_la_carte(self):
        self.ile("refuser")
        self.demarrer()
        r = self.serveur.demander("exec", {"command": "true", "timeout": 10})
        self.assertTrue(r.get("denied"), r)
        demande = json.loads((self.home / "derniere-demande.json").read_text())
        self.assertEqual(demande["duree"], 7, "délai de la commande (10 s) moins 3 s")
        self.assertLessEqual(demande["expire"] - time.time(), 7.5)
        (self.home / "a.txt").write_text("x")
        r = self.serveur.demander("read_file", {"path": "~/a.txt"})
        self.assertTrue(r.get("denied"), r)
        demande = json.loads((self.home / "derniere-demande.json").read_text())
        self.assertEqual(demande["duree"], 12, "read_file : le serveur abandonne à 15 s")
        # Délai demandé sous 6 s : refus direct, sans carte
        avant = len([l for l in self.appels() if l.startswith("qs ")])
        r = self.serveur.demander("exec", {"command": "true", "timeout": 5})
        self.assertFalse(r["success"])
        self.assertIn("trop court", r["error"])
        self.assertEqual(len([l for l in self.appels() if l.startswith("qs ")]), avant, "aucune carte")

    def test_autoriser_apres_l_echeance_un_seul_message(self):
        self.ile("silence")
        self.demarrer(NC_NOEUD_DELAI="1.5")
        (self.home / "a.txt").write_text("contenu secret")
        r = self.serveur.demander("read_file", {"path": "~/a.txt"})
        self.assertFalse(r["success"])
        self.assertTrue(r.get("denied"))
        self.assertNotIn("contenu secret", json.dumps(r))
        # « Autoriser » qui arrive après coup : ni lecture, ni deuxième réponse au serveur
        ident = json.loads((self.home / "derniere-demande.json").read_text())["id"]
        (self.run_dir / "nc-noeud/reponses" / ident).write_text("autoriser")
        self.serveur.c.settimeout(2)
        with self.assertRaises(OSError):                 # socket.timeout : plus rien n'arrive
            self.serveur.recevoir()
        lignes = [l for l in self.journal().splitlines() if "\tread_file\t" in l]
        self.assertEqual(len(lignes), 1, lignes)
        self.assertIn("expiré", lignes[0])

    def test_ia_coupee_tout_refuse(self):
        self.regler(NOEUD_JARVIS="oui", IA_MODE="non")
        self.demarrer()
        for action, params in (("media", {"subaction": "play"}), ("exec", {"command": "true"}), ("clipboard_get", {})):
            r = self.serveur.demander(action, params)
            self.assertFalse(r["success"], action)
            self.assertIn("IA_MODE=non", r["error"])
        self.assertEqual(self.appels(), [], "rien n'est lancé, aucune carte")

    def test_chemins_proteges_meme_confirmes(self):
        (self.home / ".ssh").mkdir(mode=0o700)
        (self.home / ".ssh/id_ed25519").write_text("CLE")
        (self.home / ".claude").mkdir()
        (self.home / ".claude/.credentials.json").write_text("JETON")
        (self.home / "lien").symlink_to(self.home / ".ssh")
        (self.home / "bashrc-lien").symlink_to(self.home / ".bashrc")
        self.demarrer()
        for action, params in (
                ("write_file", {"path": "~/.ssh/authorized_keys", "content": "ssh-ed25519 AAAA pirate"}),
                ("write_file", {"path": str(self.home / "lien/authorized_keys"), "content": "x"}),
                ("write_file", {"path": "lien/authorized_keys", "content": "x"}),
                ("write_file", {"path": "~/bashrc-lien", "content": "curl x | sh"}),
                ("write_file", {"path": "~/.config/systemd/user/x.service", "content": "x"}),
                ("write_file", {"path": "~/.config/autostart/x.desktop", "content": "x"}),
                ("write_file", {"path": "~/.config/nc/assistant.conf", "content": "x"}),
                ("write_file", {"path": "~/.config/nc/reglages.conf", "content": "NOEUD_SANS_CONFIRMATION=oui"}),
                ("read_file", {"path": "~/lien/id_ed25519"}),
                ("read_file", {"path": "~/.claude/.credentials.json"}),
                ("read_file", {"path": "~/.config/nc/assistant.conf"}),
                ("list_files", {"path": "~/.ssh"}),
                ("exec", {"command": "true", "cwd": "~/.ssh"})):
            r = self.serveur.demander(action, params)
            self.assertFalse(r["success"], (action, params))
            self.assertIn("protégé", r["error"], (action, params))
            self.assertNotIn("CLE", json.dumps(r))
            self.assertNotIn("JETON", json.dumps(r))
        self.assertFalse((self.home / ".ssh/authorized_keys").exists())
        self.assertFalse((self.home / ".bashrc").exists())
        self.assertFalse((self.home / ".config/systemd").exists())
        self.assertFalse([l for l in self.appels() if l.startswith("qs ")], "refusé avant toute carte")
        self.assertIn("refusé (chemin protégé)", self.journal())

    def test_fichiers_et_capture_autorises(self):
        self.demarrer()
        contenu = "".join(f"ligne {i}\n" for i in range(1, 31))
        r = self.serveur.demander("write_file", {"path": "~/Notes/notes.txt", "content": contenu})
        self.assertTrue(r["success"], r)
        self.assertEqual((self.home / "Notes/notes.txt").read_text(), contenu)
        demande = json.loads((self.home / "derniere-demande.json").read_text())
        self.assertIn("~/Notes/notes.txt", demande["resume"])
        self.assertIn("octets", demande["resume"])
        self.assertEqual(demande["texte"].splitlines()[:20], [f"ligne {i}" for i in range(1, 21)])
        self.assertNotIn("ligne 21", demande["texte"], "aperçu des 20 premières lignes")
        r = self.serveur.demander("read_file", {"path": "~/Notes/notes.txt"})
        self.assertEqual(r["content"], contenu)
        r = self.serveur.demander("screenshot")
        self.assertTrue(r["success"], r)
        self.assertEqual(base64.b64decode(r["image_base64"]), PNG)
        self.assertEqual(list(self.run_dir.glob("nc-noeud-capture-*")), [], "capture effacée après l'envoi")
        r = self.serveur.demander("clipboard_set", {"text": "à copier"})
        self.assertTrue(r["success"], r)
        self.assertIn("wl-copy à copier", self.appels())
        r = self.serveur.demander("system_info")
        self.assertFalse(r["success"], "action hors liste")

    def test_sans_ile_notification_a_boutons(self):
        self.ile("absente")
        (self.home / "notif").write_text("autoriser")
        self.demarrer()
        marque = self.home / "fait"
        r = self.serveur.demander("exec", {"command": f"touch {marque}"})
        self.assertTrue(r["success"], r)
        self.assertTrue(marque.exists())
        # Trop long pour une notification (le texte entier ne s'y voit pas) : refusé sans la montrer
        r = self.serveur.demander("exec", {"command": "true # " + "x" * 500})
        self.assertFalse(r["success"])
        # notify-send sans --action : refus
        (self.home / "notif").write_text("sans-boutons")
        marque.unlink()
        r = self.serveur.demander("exec", {"command": f"touch {marque}"})
        self.assertFalse(r["success"])
        self.assertFalse(marque.exists())
        self.assertIn("pas de confirmation possible", self.journal())

    def test_journal_0600(self):
        self.demarrer()
        self.serveur.demander("media", {"subaction": "play"})
        self.serveur.demander("exec", {"command": "echo un"})
        f = self.etat / "noctalia-config/noeud.log"
        self.assertEqual(stat.S_IMODE(f.stat().st_mode), 0o600)
        lignes = f.read_text().splitlines()
        self.assertEqual(len(lignes), 2)
        date, action, resume, decision = lignes[1].split("\t")
        self.assertRegex(date, r"^\d{4}-\d\d-\d\dT")
        self.assertEqual(action, "exec")
        self.assertEqual(resume, "exécuter cette commande : echo un")
        self.assertEqual(decision, "autorisé (écran)", "la décision et sa source")
        self.assertEqual(lignes[0].split("\t")[3], "sans confirmation")
        self.assertNotIn(SECRET, f.read_text())


# ── La carte de l'île, hors écran ─────────────────────────────────────────────────────────────────────────────────
@unittest.skipUnless(shutil.which("qs"), "Quickshell requis")
class Carte(unittest.TestCase):
    def executer(self, bouton, expire_dans=60, tard=False):
        tard_js = "true" if tard else "false"
        with tempfile.TemporaryDirectory(prefix="nc-noeud-carte-") as d:
            home = Path(d)
            root = home / "qml"; root.mkdir()
            run = home / "runtime"; run.mkdir(mode=0o700)
            (run / "nc-noeud/reponses").mkdir(parents=True, mode=0o700)
            ident = uuid.uuid4().hex
            commande = "rm -rf ~/Téléchargements/vieux && " + "echo x; " * 80
            (run / "nc-noeud/demande.json").write_text(json.dumps({
                "id": ident, "serveur": "jarvis.example.com", "action": "exec", "resume": "exécuter cette commande",
                "texte": commande, "court": 400, "expire": time.time() + expire_dans, "duree": 25}))
            for nom in ("Noeud", "ConfirmationNoeud", "Texte", "Ico"):
                shutil.copy2(QML / (nom + ".qml"), root)
            (root / "Reglages.qml").write_text('pragma Singleton\nimport QtQuick\nQtObject {readonly property bool sobre: true\n'
                                               ' function t(fr,en){return fr} function val(k,d){return d}}')
            (root / "Etat.qml").write_text('pragma Singleton\nimport QtQuick\nQtObject {property string ecranOuvert: "eDP-1"\n'
                                           ' property bool recherche: false; function fermer(){ ecranOuvert = "" }}')
            (root / "Couleurs.qml").write_text('pragma Singleton\nimport QtQuick\nQtObject {readonly property color fond:"black"; '
                                               'readonly property color texte:"white"; readonly property color texteSec:"#98989d"; '
                                               'readonly property color texteDoux:"#d1d1d6"; readonly property color gris2:"#2c2c2e"; '
                                               'readonly property color gris3:"#3a3a3c"; readonly property color gris4:"#48484a"}')
            noms = ("Noeud", "ConfirmationNoeud", "Texte", "Ico", "Reglages", "Couleurs", "Etat")
            (root / "qmldir").write_text("\n".join(("singleton " if n in ("Noeud", "Reglages", "Couleurs", "Etat") else "")
                                                   + n + " 1.0 " + n + ".qml" for n in noms))
            (root / "shell.qml").write_text('''import QtQuick
import QtQuick.Window
import QtTest
import Quickshell
ShellRoot {
 id: racine
 property int etape: 0
 property bool occupe: false
 function verifier(v,m) { if (!v) { console.error(m); Qt.exit(2); throw new Error(m) } }
 function trouver(item,nom){if(item.objectName===nom)return item;for(var i=0;i<item.children.length;i++){var r=trouver(item.children[i],nom);if(r)return r}return null}
 function texteDe(b){for(var i=0;i<b.children.length;i++)if(b.children[i].text!==undefined)return b.children[i].text;return ""}
 TestCase { id: souris; when: false }
 Window { visible: true; width: 500; height: 600; ConfirmationNoeud { id: carte; width: 460; height: implicitHeight } }
 Timer { interval: 80; running: true; repeat: true; onTriggered: {
  if (occupe) return
  occupe = true
  try {
   if (etape === 0) { if (!Noeud.demande) return
    if (''' + tard_js + ''' && Date.now() / 1000 < Noeud.demande.expire - 0.4) return
    verifier(Etat.ecranOuvert === "", "l'île ouverte se referme pour montrer la carte")
    var t = trouver(carte, "nc-noeud-titre").text
    verifier(t === "JARVIS (depuis jarvis.example.com) veut : exécuter cette commande", "titre : " + t)
    var det = trouver(carte, "nc-noeud-detail")
    verifier(det.text.length === 401 && det.text.slice(-1) === "…", "coupée à 400 : " + det.text.length)
    verifier(det.textFormat === Text.PlainText && det.font.family === "monospace", "texte brut en police de terminal")
    var ok = trouver(carte, "nc-noeud-autoriser"), non = trouver(carte, "nc-noeud-refuser")
    verifier(texteDe(ok) === "Autoriser" && texteDe(non) === "Refuser", "libellés")
    verifier(non.x < ok.x, "Refuser à gauche, Autoriser à droite")
    var voir = trouver(carte, "nc-noeud-voir-tout")
    verifier(voir.visible, "Voir tout")
    souris.mouseClick(voir)
    etape++; return }
   if (etape === 1) {
    var d2 = trouver(carte, "nc-noeud-detail")
    verifier(d2.text === Noeud.demande.texte, "Voir tout : la commande entière")
    souris.mouseClick(trouver(carte, "''' + bouton + '''"))
    if (''' + tard_js + ''') {
     var tt = trouver(carte, "nc-noeud-trop-tard")
     verifier(Noeud.tropTard && Noeud.demande !== null, "trop tard : la carte reste pour le dire")
     verifier(tt.visible && tt.text === "Trop tard : JARVIS a déjà abandonné.", "message Trop tard : " + tt.text)
     verifier(!trouver(carte, "nc-noeud-boutons").visible, "plus de boutons")
    } else verifier(Noeud.demande === null, "la carte se ferme")
    etape++; return }
   if (etape === 2) Qt.quit()
  } finally { occupe = false } } }
 Timer { interval: 8000; running: true; onTriggered: Qt.exit(9) }
}''')
            env = dict(os.environ, HOME=d, XDG_RUNTIME_DIR=str(run), XDG_CACHE_HOME=str(home / "cache"),
                       QT_QPA_PLATFORM="offscreen", QT_QUICK_BACKEND="software")
            env.pop("WAYLAND_DISPLAY", None)
            r = subprocess.run(["qs", "--no-color", "-p", str(root / "shell.qml")], env=env, text=True, capture_output=True, timeout=15)
            sortie = r.stdout + r.stderr
            self.assertEqual(r.returncode, 0, sortie)
            for erreur in ("ReferenceError", "TypeError", "Cannot assign", "Binding loop", "is not a type"):
                self.assertNotIn(erreur, sortie)
            reponse = run / "nc-noeud/reponses" / ident
            fin = time.monotonic() + (1 if tard else 4)
            while not reponse.exists() and time.monotonic() < fin:
                time.sleep(0.05)
            return reponse.read_text() if reponse.exists() else None

    def test_autoriser(self):
        self.assertEqual(self.executer("nc-noeud-autoriser"), "autoriser")

    def test_refuser(self):
        self.assertEqual(self.executer("nc-noeud-refuser"), "refuser")

    def test_autoriser_trop_tard_rien_n_est_envoye(self):
        self.assertIsNone(self.executer("nc-noeud-autoriser", expire_dans=2.5, tard=True))


class Echeances(Base):
    """Délai de confirmation par action et échéance absolue, avec une horloge injectée (aucune attente réelle)."""
    def charger(self):
        env = {"HOME": str(self.home), "XDG_RUNTIME_DIR": str(self.run_dir), "XDG_STATE_HOME": str(self.etat),
               "PATH": self.env["PATH"], "NC_LANGUE": "fr"}
        p = unittest.mock.patch.dict(os.environ, env)
        p.start()
        self.addCleanup(p.stop)
        os.environ.pop("NC_NOEUD_DELAI", None)
        chargeur = importlib.machinery.SourceFileLoader("nc_noeud_echeances", str(self.bin / "nc-noeud"))
        m = importlib.util.module_from_spec(importlib.util.spec_from_loader(chargeur.name, chargeur))
        chargeur.exec_module(m)
        self.assertEqual(m.HOME, self.home, "jamais le vrai dossier personnel")
        m.A = m.charger_assistant()
        self.t = 1000.0
        m.horloge = lambda: self.t
        return m

    def test_delais_par_action(self):
        m = self.charger()
        d = m.delai_confirmation
        for nom in ("read_file", "write_file", "screenshot", "clipboard_write"):
            self.assertEqual(d(nom, {}), 12, nom)
        for nom in ("media", "notify", "lock", "clipboard_read", "list_files"):
            self.assertEqual(d(nom, {}), 17, nom)            # relayées par HardwareRelay (20 s)
        self.assertEqual(d("exec", {"command": "x", "timeout": 10}), 7)
        self.assertEqual(d("exec", {"command": "x", "timeout": 6}), 3)
        self.assertEqual(d("exec", {"command": "x", "timeout": 60}), 17)   # plafond du relais (20 s - 3), même avec un long timeout
        self.assertEqual(d("exec", {"command": "x"}), 17, "sans timeout : peut-être relayée (20 s)")
        self.assertEqual(d("exec", {"command": "x", "timeout": 60, "node_id": "pc"}), 17, "relayée")
        for t in (5, 0, -1, "nan", "abc"):
            with self.assertRaises(m.Refus):
                d("exec", {"command": "x", "timeout": t})

    def lire_autorise_a(self, m, secondes):
        """read_file autorisé dans l'île au bout de « secondes » (horloge injectée)."""
        (self.home / "a.txt").write_text("contenu secret")
        noeud = m.Noeud({"URL": "http://127.0.0.1:1"})
        debut = self.t

        async def demander(nom, decrite, limite):
            self.assertEqual(limite - debut, 12)
            self.t = debut + secondes                         # le clic sur « Autoriser » arrive à ce moment
            return "autorise"
        noeud.confirmation.demander = demander
        return asyncio.run(noeud.decider("read_file", {"path": "~/a.txt"}))

    def test_autoriser_a_13_s_rien_n_est_lu(self):
        m = self.charger()
        r = self.lire_autorise_a(m, 13)
        self.assertFalse(r["success"])
        self.assertTrue(r.get("denied"))
        self.assertNotIn("content", r)
        self.assertIn("trop tard", r["error"])
        self.assertIn("trop tard", self.journal())

    def test_autoriser_pile_a_l_echeance_rien_n_est_lu(self):
        m = self.charger()
        r = self.lire_autorise_a(m, 12)
        self.assertFalse(r["success"])
        self.assertNotIn("content", r)

    def test_autoriser_a_10_s_lu(self):
        m = self.charger()
        r = self.lire_autorise_a(m, 10)
        self.assertTrue(r["success"], r)
        self.assertEqual(r["content"], "contenu secret")

    def test_reponse_lue_apres_l_echeance(self):
        m = self.charger()
        conf = m.Confirmation("test")
        reponse = self.run_dir / "reponse"
        reponse.write_text("autoriser")
        self.assertEqual(asyncio.run(conf.attendre(reponse, self.t + 5)), "autorise")
        instants = iter([self.t + 11, self.t + 13])           # boucle avant l'échéance, lecture après
        m.horloge = lambda: next(instants)
        self.assertEqual(asyncio.run(conf.attendre(reponse, self.t + 12)), "tard")


class FauxWS:
    """La connexion vue par Noeud.traiter : ce qui part au serveur."""
    def __init__(self):
        self.envoyes = []
        self.ferme = False

    async def envoyer(self, objet):
        self.envoyes.append(objet)


class DelaiParTrame(Echeances):
    """« timeout » de la trame d'action (JARVIS-BIS aae5b9b, issue #17) et budget d'exécution (B2-11)."""
    def test_delai_de_la_trame(self):
        m = self.charger()
        d = m.delai_confirmation
        self.assertEqual(d("read_file", {}, 35.0), 32, "timeout 35 → confirmation 32 s")
        self.assertEqual(d("write_file", {}, 20), 17)
        self.assertEqual(d("exec", {"command": "x", "timeout": 60.0}, 65.0), 32, "plafond de 32 s")
        self.assertEqual(d("exec", {"command": "x", "timeout": 5}, 10.0), 7, "la trame l'emporte sur params.timeout")
        self.assertEqual(d("read_file", {}, None), 12, "champ absent → 12 s")
        self.assertEqual(d("media", {}, None), 17)
        for v in (35.0, 35, 6):
            self.assertEqual(m.delai_trame(v), float(v))
        for v in (None, "35", True, False, 0, -1, float("nan"), float("inf"), 1e9, [35], {"t": 35}):
            self.assertIsNone(m.delai_trame(v), v)
        for v in (5.9, 1, 0.5):
            with self.assertRaises(m.Refus):
                d("read_file", {}, v)

    def decider_autorise_a(self, m, secondes, action, params, trame, attendu=None):
        noeud = m.Noeud({"URL": "http://127.0.0.1:1"})
        debut = self.t
        vu = []

        async def demander(nom, decrite, limite):
            vu.append(limite - debut)
            self.t = debut + secondes
            return "autorise"
        noeud.confirmation.demander = demander
        r = asyncio.run(noeud.decider(action, params, "rid", trame))
        if attendu is not None:
            self.assertEqual(vu, [attendu])
        return r

    def test_trame_35_confirmation_32_et_champ_absent_12(self):
        m = self.charger()
        (self.home / "a.txt").write_text("contenu")
        r = self.decider_autorise_a(m, 31, "read_file", {"path": "~/a.txt"}, 35.0, attendu=32)
        self.assertTrue(r["success"], r)
        self.t = 2000.0
        r = self.decider_autorise_a(m, 13, "read_file", {"path": "~/a.txt"}, None, attendu=12)
        self.assertFalse(r["success"], "sans timeout dans la trame : 12 s, comme avant")
        self.t = 3000.0
        r = self.decider_autorise_a(m, 13, "read_file", {"path": "~/a.txt"}, "35", attendu=12)
        self.assertFalse(r["success"], "valeur non numérique : délais connus")

    def test_confirme_a_30_s_execution_bornee_a_2_s(self):
        m = self.charger()
        marque = self.home / "fini"
        debut = time.monotonic()
        r = self.decider_autorise_a(m, 30, "exec", {"command": f"sleep 6; touch {marque}", "timeout": 60.0}, 35.0,
                                    attendu=32)
        duree = time.monotonic() - debut
        self.assertFalse(r["success"], r)
        self.assertIn("Délai de 2 s dépassé", r["error"], "35 - 3 - 30 = 2 s")
        self.assertGreater(duree, 1.5)
        self.assertLess(duree, 4.5)
        time.sleep(0.3)
        self.assertFalse(marque.exists(), "la commande est tuée")

    def test_confirme_trop_tard_rien_et_un_seul_refus(self):
        m = self.charger()
        marque = self.home / "fait"
        # 0,5 s de budget (avec et sans timeout dans la trame : 17 + 3 - 3 - 16,5), pile à l'échéance, après
        for apres, trame in ((31.5, 35.0), (16.5, None), (32, 35.0), (40, 35.0)):
            noeud = m.Noeud({"URL": "http://127.0.0.1:1"})
            noeud.ws = FauxWS()
            debut = self.t

            async def demander(nom, decrite, limite, apres=apres, debut=debut):
                self.t = debut + apres
                return "autorise"
            noeud.confirmation.demander = demander
            asyncio.run(noeud.traiter({"type": "action", "req_id": "r1", "action": "exec",
                                       "params": {"command": f"touch {marque}"}, "timeout": trame}))
            self.assertEqual(len(noeud.ws.envoyes), 1, apres)
            r = noeud.ws.envoyes[0]
            self.assertEqual((r["type"], r["req_id"], r["success"], r.get("denied")), ("response", "r1", False, True))
            self.assertIn("trop tard", r["error"].lower())
            self.assertFalse(marque.exists(), apres)
            self.t += 100
        self.assertEqual(self.journal().count("trop tard"), 4)

    def test_chemins_proteges_complets(self):
        """B2-10 : démarrage automatique, shells, identifiants et ce qui lance des commandes à ta place."""
        m = self.charger()
        h = self.home
        for rel in (".bash_profile", ".zshenv", ".zprofile", ".config/fish/config.fish", ".config/environment.d/x.conf",
                    ".local/share/systemd/user/x.service", ".xprofile", ".codex/auth.json", ".gemini/oauth_creds.json",
                    ".local/share/opencode/auth.json", ".aws/credentials", ".docker/config.json", ".npmrc",
                    ".config/google-chrome/Default/Login Data", ".local/share/jarvis-bis/.env",
                    ".local/share/TelegramDesktop/tdata/x", ".password-store/x.gpg", ".claude.json"):
            for ecriture in (False, True):
                self.assertIsNotNone(m.protege((h / rel).resolve(), ecriture), (rel, ecriture))
        for rel in (".config/hypr/hyprland.conf", ".config/uwsm/env", ".config/quickshell/nc-ile/shell.qml",
                    ".config/nc/greeting.zsh", ".config/nc/raccourcis.conf", ".local/bin/ls", ".gitconfig",
                    ".local/share/applications/firefox.desktop", ".local/state/noctalia-config/noeud.log"):
            self.assertIsNotNone(m.protege((h / rel).resolve(), True), rel)
            self.assertIsNone(m.protege((h / rel).resolve(), False), rel + " reste lisible")
        for rel in (".zsh_history", ".bash_history"):
            self.assertIsNotNone(m.protege((h / rel).resolve(), False), rel)
        for rel in ("Documents/a.txt", ".config/hyprpaper.conf", "Notes/x"):
            self.assertIsNone(m.protege((h / rel).resolve(), True), rel)

    def test_secrets_masques(self):
        m = self.charger()
        m.retenir_secrets({"URL": "http://x", "SECRET_KEY": SECRET, "USER_ID": "test"})
        jeton = "ghp_" + "A1b2C3d4" * 4
        s = m.sans_secrets(f"curl -H 'X-Secret-Key: {SECRET}' -H 'Authorization: Bearer {jeton}' x; echo {jeton}")
        self.assertNotIn(SECRET, s)
        self.assertNotIn(jeton, s)
        self.assertIn("curl", s)
        self.assertEqual(m.sans_secrets("echo bonjour"), "echo bonjour")


class Distance(Base):
    """Confirmation à distance (NOEUD_CONFIRMATION) : le faux serveur reçoit confirm_request et répond."""
    def setUp(self):
        super().setUp()
        self.regler(NOEUD_JARVIS="oui", NOEUD_CONFIRMATION="distance")
        self.ile("absente")
        self.recus = []

    def action(self, action, params, timeout=35.0):
        rid = str(uuid.uuid4())
        self.serveur.envoyer({"type": "action", "req_id": rid, "action": action, "params": params, "timeout": timeout})
        return rid

    def attendre(self, genre, rid):
        while True:
            m = self.serveur.recevoir()
            self.recus.append(m)
            if m.get("type") == genre and m.get("req_id") == rid:
                return m

    def repondre(self, rid, decision):
        self.serveur.envoyer({"type": "confirm_response", "req_id": rid, "decision": decision})

    def rien_de_plus(self, delai=1.5):
        self.serveur.c.settimeout(delai)
        with self.assertRaises(OSError):
            self.serveur.recevoir()
        self.serveur.c.settimeout(15)

    def qs(self):
        return [l for l in self.appels() if l.startswith("qs ")]

    def test_allow_execute(self):
        r = self.demarrer()
        self.assertIn("remote_confirm", r["capabilities"])
        self.assertEqual(r["metadata"]["confirmation_mode"], "distance")
        marque = self.home / "fait"
        cmd = f"touch {marque} # {SECRET}"
        rid = self.action("exec", {"command": cmd})
        q = self.attendre("confirm_request", rid)
        self.assertEqual(set(q), {"type", "req_id", "action", "summary", "expires_in"})
        self.assertEqual(q["action"], "exec")
        self.assertIn(f"touch {marque} # ", q["summary"], "la commande entière")
        self.assertNotIn(SECRET, q["summary"], "jamais de secret")
        self.assertTrue(30 <= q["expires_in"] <= 32, q)
        self.assertFalse(marque.exists(), "rien avant « allow »")
        self.repondre(rid, "allow")
        rep = self.attendre("response", rid)
        self.assertTrue(rep["success"], rep)
        self.assertTrue(marque.exists())
        self.assertEqual(self.qs(), [], "pas de carte dans l'île")
        self.assertNotIn("confirm_cancel", [m["type"] for m in self.recus])
        # Une seconde réponse, puis une réponse inconnue : ignorées, notées
        self.repondre(rid, "allow")
        self.repondre("inconnu-" + uuid.uuid4().hex, "allow")
        self.rien_de_plus()
        j = self.journal()
        self.assertIn("autorisé (distance)", j)
        self.assertIn("ignorée (en double)", j)
        self.assertIn("ignorée (inconnue)", j)
        self.assertNotIn(SECRET, j)

    def test_deny_rien(self):
        self.demarrer()
        marque = self.home / "fait"
        rid = self.action("write_file", {"path": "~/notes.txt", "content": "x" * 10})
        q = self.attendre("confirm_request", rid)
        self.assertIn("~/notes.txt", q["summary"])
        self.assertIn("10 octets", q["summary"], "chemin et taille")
        self.repondre(rid, "deny")
        rep = self.attendre("response", rid)
        self.assertFalse(rep["success"])
        self.assertTrue(rep["denied"])
        self.assertIn("à distance", rep["error"])
        self.assertFalse((self.home / "notes.txt").exists())
        self.assertFalse(marque.exists())
        self.assertIn("refusé (distance)", self.journal())

    def test_expiration_rien_un_seul_refus(self):
        self.demarrer(NC_NOEUD_DELAI="2")
        marque = self.home / "fait"
        rid = self.action("exec", {"command": f"touch {marque}"})
        q = self.attendre("confirm_request", rid)
        self.assertLessEqual(q["expires_in"], 2)
        self.assertEqual(self.attendre("confirm_cancel", rid)["req_id"], rid)
        rep = self.attendre("response", rid)
        self.assertFalse(rep["success"])
        self.assertIn("en 2 s", rep["error"])
        self.repondre(rid, "allow")                           # trop tard : ignoré
        self.rien_de_plus()
        self.assertFalse(marque.exists())
        self.assertEqual(len([m for m in self.recus if m.get("type") == "response"]), 1)
        self.assertIn("ignorée (tardive)", self.journal())

    def test_allow_chemin_protege_refuse(self):
        (self.home / ".ssh").mkdir(mode=0o700)
        (self.home / "boite").mkdir()
        self.demarrer()
        rid = self.action("write_file", {"path": "~/boite/authorized_keys", "content": "ssh-ed25519 AAAA pirate"})
        self.attendre("confirm_request", rid)
        # Pendant l'attente, le dossier devient un lien vers ~/.ssh : « allow » n'y change rien
        (self.home / "boite").rmdir()
        (self.home / "boite").symlink_to(self.home / ".ssh")
        self.repondre(rid, "allow")
        rep = self.attendre("response", rid)
        self.assertFalse(rep["success"])
        self.assertIn("protégé", rep["error"])
        self.assertFalse((self.home / ".ssh/authorized_keys").exists())
        # Chemin protégé dès la demande : refus, sans même demander
        rid = self.action("read_file", {"path": "~/.ssh/id_ed25519"})
        rep = self.attendre("response", rid)
        self.assertIn("protégé", rep["error"])
        self.assertNotIn("confirm_request", [m["type"] for m in self.recus if m.get("req_id") == rid])

    def test_allow_avec_ia_coupee_au_moment_d_executer(self):
        self.demarrer()
        marque = self.home / "fait"
        rid = self.action("exec", {"command": f"touch {marque}"})
        self.attendre("confirm_request", rid)
        self.regler(NOEUD_JARVIS="oui", NOEUD_CONFIRMATION="distance", IA_MODE="non")
        self.repondre(rid, "allow")
        rep = self.attendre("response", rid)
        self.assertFalse(rep["success"])
        self.assertIn("IA_MODE=non", rep["error"])
        self.assertFalse(marque.exists())
        self.assertIn("refusé (IA coupée)", self.journal())

    def test_ecran_aucune_demande_a_distance(self):
        self.regler(NOEUD_JARVIS="oui")
        self.ile("autoriser")
        r = self.demarrer()
        self.assertNotIn("remote_confirm", r["capabilities"])
        marque = self.home / "fait"
        rid = self.action("exec", {"command": f"touch {marque}"})
        rep = self.attendre("response", rid)
        self.assertTrue(rep["success"], rep)
        self.assertEqual([m["type"] for m in self.recus], ["response"], "aucune confirm_request")
        self.assertTrue(self.qs())
        self.assertIn("autorisé (écran)", self.journal())

    def test_les_deux_l_ecran_d_abord(self):
        self.regler(NOEUD_JARVIS="oui", NOEUD_CONFIRMATION="les-deux")
        self.ile("autoriser")
        r = self.demarrer()
        self.assertIn("remote_confirm", r["capabilities"])
        marque = self.home / "fait"
        rid = self.action("exec", {"command": f"touch {marque}"})
        self.attendre("confirm_request", rid)
        self.attendre("confirm_cancel", rid)                  # décidé sur l'écran : la demande à distance est close
        rep = self.attendre("response", rid)
        self.assertTrue(rep["success"], rep)
        self.assertTrue(marque.exists())
        self.repondre(rid, "deny")                            # arrive après : ignoré
        self.rien_de_plus()
        j = self.journal()
        self.assertIn("autorisé (écran)", j)
        self.assertIn("ignorée (tardive)", j)

    def test_les_deux_la_distance_d_abord(self):
        self.regler(NOEUD_JARVIS="oui", NOEUD_CONFIRMATION="les-deux")
        self.ile("silence")
        self.demarrer()
        marque = self.home / "fait"
        rid = self.action("exec", {"command": f"touch {marque}"})
        self.attendre("confirm_request", rid)
        fin = time.monotonic() + 5
        while not (self.run_dir / "nc-noeud/demande.json").exists() and time.monotonic() < fin:
            time.sleep(0.05)
        self.assertTrue((self.run_dir / "nc-noeud/demande.json").exists(), "la carte est ouverte aussi")
        self.repondre(rid, "deny")
        rep = self.attendre("response", rid)
        self.assertFalse(rep["success"])
        self.assertIn("à distance", rep["error"])
        self.assertFalse(marque.exists())
        self.assertFalse((self.run_dir / "nc-noeud/demande.json").exists(), "la carte se ferme")
        self.assertNotIn("confirm_cancel", [m["type"] for m in self.recus])
        self.assertIn("refusé (distance)", self.journal())


class Cablage(unittest.TestCase):
    """Île, réglages, service, installation : branchés, sans activer le service."""
    def test_ile(self):
        ile = (QML / "Ile.qml").read_text()
        self.assertIn("sourceComponent: ConfirmationNoeud {", ile)
        self.assertIn("Noeud.demande !== null", ile)
        self.assertIn('function noeud(): string { Noeud.relire(); return "oui" }', (QML / "shell.qml").read_text())
        for f in ("Noeud.qml", "ConfirmationNoeud.qml"):
            self.assertNotIn("component ", (QML / f).read_text(), f)

    def test_service_desactive_par_defaut(self):
        service = (REPO / "home/.config/systemd/user/nc-noeud.service").read_text()
        self.assertIn("Restart=on-failure", service)
        self.assertIn("RestartSec=10", service)
        self.assertIn("ExecStart=%h/.local/bin/nc-noeud", service)
        install = (REPO / "install.sh").read_text()
        self.assertNotRegex(install, r"enable[^\n]*nc-noeud")
        self.assertNotRegex(install, r"UNITS[^\n]*nc-noeud")
        export = (REPO / "export.sh").read_text()
        self.assertIn(".local/bin/nc-noeud\n", export)
        self.assertIn(".config/systemd/user/nc-noeud.service\n", export)

    def test_reglages(self):
        chargeur = importlib.machinery.SourceFileLoader("nc_reglages_noeud", str(BIN / "nc-reglages"))
        with tempfile.TemporaryDirectory() as d, unittest.mock.patch.dict(os.environ, HOME=d, NC_LANGUE="fr"):
            m = importlib.util.module_from_spec(importlib.util.spec_from_loader(chargeur.name, chargeur))
            chargeur.exec_module(m)
            pilote, sans = m.PAR_CLE["NOEUD_JARVIS"], m.PAR_CLE["NOEUD_SANS_CONFIRMATION"]
            self.assertEqual((pilote.section, pilote.genre, pilote.defaut, pilote.groupe),
                             ("Intelligence artificielle", "ouinon", "non", "noeud"))
            self.assertEqual(pilote.nom, "Laisser JARVIS piloter ce PC")
            self.assertEqual(len(pilote.aide.splitlines()), 2, "avertissement en deux lignes")
            self.assertEqual((sans.section, sans.defaut), ("Intelligence artificielle", "oui"))
            conf = m.PAR_CLE["NOEUD_CONFIRMATION"]
            self.assertEqual((conf.section, conf.genre, conf.defaut, conf.groupe),
                             ("Intelligence artificielle", "choix", "ecran", "noeud-confirmation"))
            self.assertEqual([c for c, _ in conf.choix()], ["ecran", "distance", "les-deux"])
            cles = [r.cle for r in m.REGLAGES]
            self.assertEqual(cles.index("NOEUD_CONFIRMATION"), cles.index("NOEUD_JARVIS") + 1, "juste à côté")
            appels = []
            with unittest.mock.patch.object(m.subprocess, "run", lambda a, **k: appels.append(a)):
                m.appliquer(["noeud"], {"NOEUD_JARVIS": "oui"})
                m.appliquer(["noeud"], {})
                m.appliquer(["noeud-confirmation"], {"NOEUD_JARVIS": "oui", "NOEUD_CONFIRMATION": "distance"})
                m.appliquer(["noeud-confirmation"], {"NOEUD_CONFIRMATION": "distance"})     # pilotage coupé : rien
            self.assertEqual(appels, [["systemctl", "--user", "enable", "--now", "nc-noeud.service"],
                                      ["systemctl", "--user", "disable", "--now", "nc-noeud.service"],
                                      ["systemctl", "--user", "try-restart", "nc-noeud.service"]])


if __name__ == "__main__":
    unittest.main()

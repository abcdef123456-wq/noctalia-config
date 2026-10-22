"""Choix cliquables de JARVIS (issue #7) : extraction partagée (nc_choix), /api/ask du gateway, ligne JSON de l'île.
Faux upstream en mémoire, faux serveur HTTP local, HOME temporaire ; aucun appel réseau réel."""
import asyncio
import contextlib
from http.server import ThreadingHTTPServer
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import types
import unittest
from unittest.mock import patch

from tests.test_assistant import Serveur

REPO = Path(__file__).resolve().parents[1]
SERVEUR = REPO / "home/.local/share/nc-jarvis/server"
BIN = REPO / "home/.local/bin"


def module(path, name):
    m = types.ModuleType(name)
    m.__file__ = str(path)
    exec(compile(path.read_text(), str(path), "exec"), m.__dict__)
    return m


C = module(SERVEUR / "nc_choix.py", "nc_choix_test")


class Extraction(unittest.TestCase):
    def test_marqueur_retire_et_extrait(self):
        texte, choix = C.extraire_choix("Je peux faire deux choses.\n\n[[choix: Résumer | **Traduire** en anglais ]]\n")
        self.assertEqual(texte, "Je peux faire deux choses.")
        self.assertEqual(choix, ["Résumer", "Traduire en anglais"])
        # Marqueur ailleurs qu'en dernière ligne : ni retiré ni lu
        t = "Écris [[choix: A | B]] pour proposer.\nFin."
        self.assertEqual(C.extraire_choix(t), (t, []))
        # Marqueur invalide (6 choix, ou un de plus de 80 caractères) : retiré quand même, aucun choix
        self.assertEqual(C.extraire_choix("Texte\n[[choix: 1|2|3|4|5|6]]"), ("Texte", []))
        self.assertEqual(C.extraire_choix("Texte\n[[choix: court | " + "x" * 81 + "]]"), ("Texte", []))
        # Rien que le marqueur : la réponse n'est pas vidée
        self.assertEqual(C.extraire_choix("[[choix: A | B]]"), ("[[choix: A | B]]", []))
        # La forme du serveur JARVIS-BIS (3d1c6b6), en français ou en anglais
        self.assertEqual(C.extraire_choix("Laquelle ?\n[CHOIX: Paris | Lyon]"), ("Laquelle ?", ["Paris", "Lyon"]))
        self.assertEqual(C.extraire_choix("Which?\n[CHOICES: A | B]"), ("Which?", ["A", "B"]))

    def test_liste_finale_apres_une_question(self):
        for liste in ("1. Paris\n2. Lyon\n3. **Marseille**", "1) Paris\n2) Lyon\n3) Marseille", "- Paris\n- Lyon\n- Marseille"):
            with self.subTest(liste=liste):
                texte = "Voici trois villes.\nLaquelle préfères-tu ?\n\n" + liste + "\n"
                self.assertEqual(C.extraire_choix(texte), (texte, ["Paris", "Lyon", "Marseille"]))
        self.assertEqual(C.extraire_choix("**Lequel ?**\n- Oui\n- Non")[1], ["Oui", "Non"])

    def test_liste_au_milieu_ou_sans_question_aucun_choix(self):
        for texte in ("Laquelle ?\n1. Paris\n2. Lyon\nJe peux aussi en ajouter.",          # du texte après la liste
                      "Voici deux villes.\n1. Paris\n2. Lyon",                             # pas de question avant
                      "Laquelle ?\n1. Paris",                                              # un seul élément
                      "Laquelle ?\n1. Paris\n- Lyon",                                      # deux sortes de puces
                      "Laquelle ?\n1. Paris\n2. " + "L" * 61):                             # plus de 60 caractères
            with self.subTest(texte=texte):
                self.assertEqual(C.extraire_choix(texte), (texte, []))

    def test_limites_cinq_choix_de_80_caracteres(self):
        self.assertEqual(C.extraire_choix("Laquelle ?\n" + "\n".join(f"{i}. Ville {i}" for i in range(1, 7)))[1], [])
        self.assertEqual(len(C.extraire_choix("Laquelle ?\n" + "\n".join(f"{i}. Ville {i}" for i in range(1, 6)))[1]), 5)
        self.assertEqual(C.verifier_choix(["a"] * 2 + ["b"]), ["a", "b"])
        for mauvais in (["x" * 81], ["a"] * 6, [], "A | B", [1, 2], ["ok", ""], None):
            with self.subTest(mauvais=mauvais):
                self.assertEqual(C.verifier_choix(mauvais), [])
        self.assertEqual(C.verifier_choix(["x" * 80]), ["x" * 80])
        self.assertEqual(C.verifier_choix(["Oui\x1b[31m‮", "Non\nvraiment"]), ["Oui [31m", "Non vraiment"])

    def test_le_client_charge_le_fichier_du_serveur(self):
        """Une seule source : nc-assistant charge nc_choix.py de l'overlay installé à côté, pas une copie."""
        client = module(BIN / "nc-assistant", "assistant_choix_test")
        self.assertEqual(Path(client.module_choix().__file__).resolve(), (SERVEUR / "nc_choix.py").resolve())
        self.assertNotIn("def extraire_choix", (BIN / "nc-assistant").read_text())


try:
    import fastapi
except ImportError:
    fastapi = None


@unittest.skipUnless(fastapi, "FastAPI requis")
class Passerelle(unittest.TestCase):
    """/api/ask d'origine (faux upstream) derrière nc_gateway, appelé en ASGI : httpx n'est pas nécessaire."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        racine = Path(self.tmp.name)
        self.reponses = []
        up = types.ModuleType("main")
        up.__file__ = str(racine / "gateway/main.py")
        up.app = fastapi.FastAPI()
        up.require_secret = lambda: None

        async def forward_to_runner(prompt, *args, **kwargs):
            return dict(success=True, output=self.reponses.pop(0), session={})
        gateway = types.ModuleType("gateway")
        gateway.httpx = types.ModuleType("httpx")
        gateway.forward_to_runner = forward_to_runner
        up.forward_to_runner = forward_to_runner                     # from gateway import forward_to_runner
        bot = types.ModuleType("bots_test_choix")
        bot.forward_to_runner = forward_to_runner

        @up.app.post("/api/ask")
        async def ask(request: fastapi.Request):
            corps = await request.json()
            r = await up.forward_to_runner(corps["prompt"])
            return dict(success=r["success"], output=r["output"])

        @up.app.post("/api/refus")
        async def refus():
            raise fastapi.HTTPException(401)
        self.up, self.bot = up, bot
        remplacements = {"main": up, "gateway": gateway, "bots_test_choix": bot,
                         "nc_management": module(SERVEUR / "nc_management.py", "nc_management"),
                         "nc_telegram": module(SERVEUR / "nc_telegram.py", "nc_telegram"),
                         "nc_choix": module(SERVEUR / "nc_choix.py", "nc_choix")}
        if "httpx" not in sys.modules:
            try:
                import httpx  # noqa: F401
            except ImportError:
                remplacements["httpx"] = gateway.httpx
        # Ne restaurer que nos modules (cf. test_jarvis.Management)
        avant = {k: sys.modules.get(k) for k in remplacements}
        sys.modules.update(remplacements)

        def restaurer():
            for k, v in avant.items():
                if v is None:
                    sys.modules.pop(k, None)
                else:
                    sys.modules[k] = v
        self.addCleanup(restaurer)
        with self.assertLogs("nc_telegram", "WARNING"):              # aucun bot Telegram dans ce faux upstream
            self.api = module(SERVEUR / "nc_gateway.py", "nc_gateway")

    def appeler(self, chemin, corps):
        messages, entree = [], [dict(type="http.request", body=json.dumps(corps).encode(), more_body=False)]

        async def recevoir():
            return entree.pop(0) if entree else dict(type="http.disconnect")

        async def envoyer(m):
            messages.append(m)
        scope = dict(type="http", asgi=dict(version="3.0"), http_version="1.1", method="POST", scheme="http", path=chemin,
                     raw_path=chemin.encode(), root_path="", query_string=b"", headers=[(b"content-type", b"application/json")],
                     client=("127.0.0.1", 1), server=("127.0.0.1", 80))
        asyncio.run(self.up.app(scope, recevoir, envoyer))
        debut = next(m for m in messages if m["type"] == "http.response.start")
        corps = b"".join(m.get("body", b"") for m in messages if m["type"] == "http.response.body")
        entetes = dict(debut["headers"])
        self.assertEqual(int(entetes[b"content-length"]), len(corps))
        return debut["status"], corps

    def test_api_ask_renvoie_les_choix_sans_le_marqueur(self):
        self.reponses = ["Quelle langue ?\n[[choix: Français | Anglais]]", "Laquelle ?\n1. Paris\n2. Lyon", "Bonjour."]
        statut, corps = self.appeler("/api/ask", dict(prompt="question"))
        self.assertEqual(statut, 200)
        self.assertEqual(json.loads(corps), dict(success=True, output="Quelle langue ?", choices=["Français", "Anglais"]))
        self.assertEqual(json.loads(self.appeler("/api/ask", dict(prompt="q"))[1])["choices"], ["Paris", "Lyon"])
        self.assertEqual(json.loads(self.appeler("/api/ask", dict(prompt="q"))[1]), dict(success=True, output="Bonjour."))
        # Les autres réponses (erreurs comprises) passent telles quelles
        self.assertEqual(self.appeler("/api/refus", {})[0], 401)

    def test_choix_deja_extraits_par_le_serveur(self):
        # JARVIS-BIS 3d1c6b6 renvoie lui-même « choices » : gardés s'ils respectent nos limites, retirés sinon
        f = self.api._avec_choix
        self.assertEqual(json.loads(f(json.dumps(dict(output="Laquelle ?", choices=["Paris", "Lyon"])).encode())),
                         dict(output="Laquelle ?", choices=["Paris", "Lyon"]))
        self.assertEqual(json.loads(f(json.dumps(dict(output="Texte", choices=list("abcdef"))).encode())), dict(output="Texte"))

    def test_les_bots_recoivent_le_texte_sans_marqueur(self):
        self.assertIs(self.bot.forward_to_runner, sys.modules["gateway"].forward_to_runner)
        self.reponses = ["Quelle langue ?\n[[choix: Français | Anglais]]"]
        r = asyncio.run(self.bot.forward_to_runner("depuis Telegram"))
        self.assertEqual(r["output"], "Quelle langue ?")


class Client(unittest.TestCase):
    """nc-assistant contre un faux /api/ask local : HOME temporaire, nc_choix installé à côté comme par install.sh."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.bin = self.root / ".local/bin"
        self.bin.mkdir(parents=True)
        for nom in ("nc-assistant", "nc-claude"):
            shutil.copy2(BIN / nom, self.bin / nom)
        serveur = self.root / ".local/share/nc-jarvis/server"
        serveur.mkdir(parents=True)
        shutil.copy2(SERVEUR / "nc_choix.py", serveur / "nc_choix.py")
        (self.bin / "hyprctl").write_text('#!/bin/sh\nprintf "[]\\n"\n')
        (self.bin / "hyprctl").chmod(0o755)
        run = self.root / "run"
        run.mkdir(mode=0o700)
        self.env = dict(os.environ, HOME=str(self.root), XDG_RUNTIME_DIR=str(run), NC_LANGUE="fr",
                        PATH=str(self.bin) + ":/usr/bin:/bin")
        self.env.pop("NC_ILE_SANS", None)
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Serveur)
        self.server.recus, self.server.bloquer = [], False
        self.server.entree, self.server.sortie = threading.Event(), threading.Event()
        threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        conf = self.root / ".config/nc/assistant.conf"
        conf.parent.mkdir(parents=True)
        conf.write_text(f"URL=http://127.0.0.1:{self.server.server_port}/gateway\nSECRET_KEY=test-private-key\n"
                        "USER_ID=test-user\nTIMEOUT=5\n")
        conf.chmod(0o600)

    def repondre(self, **corps):
        self.server.reponse = (200, json.dumps(dict(success=True, **corps)).encode())

    def ile(self):
        r = subprocess.run([sys.executable, str(self.bin / "nc-assistant"), "requete-ile"], env=self.env, text=True,
                           capture_output=True, timeout=10, input=json.dumps(dict(session_id="a" * 32, question="q")) + "\n")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn("test-private-key", r.stdout + r.stderr)
        return json.loads(r.stdout)

    def test_ligne_json_de_l_ile_avec_choices(self):
        self.repondre(output="Quelle langue ?", choices=["Français", "Anglais"])
        self.assertEqual(self.ile(), dict(ok=True, text="Quelle langue ?", truncated=False, choices=["Français", "Anglais"]))
        # Gateway pas encore à jour : le client extrait lui-même, marqueur retiré
        self.repondre(output="Quelle langue ?\n[[choix: Français | Anglais]]")
        self.assertEqual(self.ile(), dict(ok=True, text="Quelle langue ?", truncated=False, choices=["Français", "Anglais"]))
        # Limites revérifiées : six choix, ou un trop long, ne donnent rien ; pas de choix, pas de clé
        for choix in (["a", "b", "c", "d", "e", "f"], ["x" * 81], []):
            self.repondre(output="Texte", choices=choix)
            self.assertEqual(self.ile(), dict(ok=True, text="Texte", truncated=False))
        self.repondre(output="Bonjour")
        self.assertEqual(self.ile(), dict(ok=True, text="Bonjour", truncated=False))

    def test_terminal_numero_envoie_le_libelle(self):
        self.repondre(output="Quelle langue ?", choices=["Français", "Anglais"])
        r = subprocess.run([sys.executable, str(self.bin / "nc-assistant"), "chat"], env=self.env, text=True,
                           capture_output=True, timeout=10, input="question\n2\n3\nexit\n")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("  1. Français\n  2. Anglais\n", r.stdout)
        self.assertEqual([c[3]["prompt"] for c in self.server.recus], ["question", "Anglais", "3"])



class Spotlight(unittest.TestCase):
    """Le Spotlight passe par nc-ia : les choix de JARVIS y arrivent par une ligne {"choices": …} du flux."""
    def test_nc_ia_transmet_les_choix(self):
        import os, subprocess, sys, tempfile, textwrap
        racine = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory(prefix="nc-choix-ia-") as d:
            b = Path(d) / ".local/bin"; b.mkdir(parents=True)
            (b / "nc-assistant").write_text(textwrap.dedent("""\
                import json, sys
                assert sys.argv[1:3] == ["demander", "--flux"], sys.argv
                print(json.dumps({"t": "Quelle couleur ?", "choices": ["Rouge", "Vert"]}))
            """))
            code = textwrap.dedent(f"""\
                import importlib.machinery, importlib.util, json
                l = importlib.machinery.SourceFileLoader("nc_ia", {str(racine / "home/.local/bin/nc-ia")!r})
                m = importlib.util.module_from_spec(importlib.util.spec_from_loader("nc_ia", l)); l.exec_module(m)
                print(json.dumps({{"t": list(m.appel_jarvis("consigne", "question", None, "question")), "c": m.CHOIX}}))
            """)
            r = subprocess.run([sys.executable, "-c", code], env=dict(os.environ, HOME=d), capture_output=True, text=True,
                               timeout=30)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(json.loads(r.stdout.splitlines()[-1]), {"t": ["Quelle couleur ?"], "c": ["Rouge", "Vert"]})


if __name__ == "__main__":
    unittest.main()

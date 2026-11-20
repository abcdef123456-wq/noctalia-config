"""nc-cloud contre un faux serveur du Cloud JARVIS (HTTP en boucle locale, écrit ici d'après le contrat d'API v1 et
les formes du vrai serveur : morceaux en objets idx/sha256/size, états pending/committed/cancelled/expired/invalidated,
412 au commit pour un nom pris, name_conflict, device_revoked en 403, clé refusée sans champ error, suppression annoncée
par features.file_delete, révision de dossier qui change à chaque enfant publié si revisions_vivantes).

Aucun vrai serveur ni vrai DNS. HOME, XDG_* et TMPDIR pointent vers un dossier jetable ; secret-tool est un faux qui
range le jeton dans un fichier du test et note ses arguments. Après chaque test, la clé JARVIS et le jeton sont cherchés
partout : arguments de secret-tool, sorties, adresses reçues par le serveur, fichiers écrits (hors le faux trousseau et
assistant.conf)."""
import contextlib
import fcntl
import hashlib
import http.server
import importlib.machinery
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import signal
import socket
import socketserver
import stat
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock
import urllib.parse

REPO = Path(__file__).resolve().parents[1]
NC_CLOUD = REPO / "home/.local/bin/nc-cloud"
CLE = "cle-jarvis-tres-secrete-0123456789"
JETON = "jeton-cloud-aleatoire-abcdefghijklmnopqrstuvwxyz"
MORCEAU = 64 * 1024
RLO = chr(0x202E)    # inversion de sens : écrit par son code, jamais en vrai dans le source


class Faux:
    """L'état du faux serveur et ses pannes."""

    def __init__(self):
        self.server_id, self.space_id = "srv-1", "personal"
        self.enabled, self.state = True, "available"
        self.devices = {}
        self.entries = {"root": {"id": "root", "parent": None, "name": "", "kind": "directory", "revision": "r0"}}
        self.contenus = {}
        self.uploads, self.par_cle = {}, {}
        self.recus_suppression = {}
        self.n = 0
        self.journal = []          # (méthode, chemin complet, en-têtes)
        self.pannes = set()
        self.quota = 10 ** 9
        self.lent = 0.0
        self.morceau = MORCEAU
        self.limite_envois = 8
        self.revisions_vivantes = False     # b7828d5 : la révision d'un dossier change à chaque enfant
        self.suppression = False            # b7828d5 : features.file_delete
        self.nom_refuse = None
        self.lock = threading.Lock()

    def nouvel_id(self, p):
        self.n += 1
        return f"{p}{self.n}"

    def ident(self):
        return {"api_version": 1, "server_id": self.server_id, "space_id": self.space_id}

    def features(self):
        return {"file_delete": True, "delete_if_match": True, "delete_idempotency": True, "max_old_versions": 10} \
            if self.suppression else {}

    def enfant_change(self, parent_id):
        if self.revisions_vivantes:
            self.entries[parent_id]["revision"] = self.nouvel_id("rv")


class Gestion(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):
        pass

    def repondre(self, code, obj=None, corps=None):
        if corps is None:
            corps = json.dumps(obj if obj is not None else {}).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(corps)))
        self.end_headers()
        self.wfile.write(corps)

    def erreur(self, code, err, **plus):
        self.repondre(code, dict(F().ident(), error=err, **plus))

    def couper(self):
        self.close_connection = True

    def corps(self):
        n = int(self.headers.get("Content-Length") or 0)
        return self.rfile.read(n) if n else b""

    def do_GET(self):
        self.traiter("GET")

    def do_POST(self):
        self.traiter("POST")

    def do_PUT(self):
        self.traiter("PUT")

    def do_DELETE(self):
        self.traiter("DELETE")

    def traiter(self, m):
        f = F()
        brut = self.corps()
        with f.lock:
            f.journal.append((m, self.path, dict(self.headers)))
        u = urllib.parse.urlsplit(self.path)
        q = dict(urllib.parse.parse_qsl(u.query))
        if not u.path.startswith("/api/cloud/v1/"):
            return self.erreur(404, "not_found")
        p = u.path[len("/api/cloud/v1"):].split("/")[1:]
        if "redirection" in f.pannes:
            self.send_response(302)
            self.send_header("Location", "http://127.0.0.1:9/ailleurs")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        # Administration : clé JARVIS
        if p[0] in ("capabilities", "devices"):
            if self.headers.get("X-Secret-Key") != CLE:
                return self.repondre(401, {"detail": "Invalid secret key"})
            if p == ["capabilities"]:
                return self.repondre(200, dict(f.ident(), enabled=f.enabled, state=f.state if f.enabled else "disabled",
                                               reason=None, api_path="/api/cloud/v1", dav_path="/cloud/dav/",
                                               features=f.features()))
            if not f.enabled:
                return self.erreur(403, "cloud_disabled")
            if m == "POST" and p == ["devices"]:
                did = f.nouvel_id("dev")
                f.devices[did] = {"token": JETON, "revoque": False}
                return self.repondre(200, dict(f.ident(), device_id=did, token=JETON))
            if m == "DELETE" and len(p) == 2:
                d = f.devices.get(p[1])
                if not d:
                    return self.erreur(404, "not_found")
                d["revoque"] = True
                return self.repondre(200, dict(f.ident(), device_id=p[1], state="revoked"))
            return self.erreur(404, "not_found")
        # Données : jeton seulement, jamais la clé
        if self.headers.get("X-Secret-Key"):
            f.pannes.add("cle_sur_donnees")
        if not f.enabled:
            return self.erreur(403, "cloud_disabled")
        auth = self.headers.get("Authorization", "")
        dev = next((k for k, d in f.devices.items() if auth == "Bearer " + d["token"]), None)
        if not dev:
            return self.erreur(401, "authentication_required")
        if f.devices[dev]["revoque"]:
            return self.erreur(403, "device_revoked")
        ident = dict(f.ident(), device_id=dev)
        if p == ["status"]:
            if "stockage" in f.pannes:
                return self.erreur(503, "storage_error")
            if "json_profond" in f.pannes:
                return self.repondre(200, corps=b"[" * 200000)
            return self.repondre(200, dict(ident, state="ready", root=f.entries["root"], quota_bytes=f.quota, used_bytes=0,
                                           reserved_bytes=0, chunk_bytes=f.morceau, max_file_bytes=5 * 2 ** 30,
                                           webdav="read_only", features=f.features()))
        if p == ["entries"] and m == "GET":
            parent = f.entries.get(q.get("parent_id", "root"))
            if not parent or parent["kind"] != "directory":
                return self.erreur(404, "not_found")
            enfants = [e for e in f.entries.values() if e.get("parent") == parent["id"]]
            if "cacher_noms" in f.pannes:
                enfants = []
            debut = int(q.get("cursor") or 0)
            page = enfants[debut:debut + 2]           # pages de 2 (100 en vrai) pour tester la suite
            suite = str(debut + 2) if debut + 2 < len(enfants) else None
            if "nom_hostile" in f.pannes:
                page = [dict(e, name="../\x1b[31mpiège" + RLO + "\n") for e in page]
            if "demi_paire" in f.pannes:
                page = [dict(e, name="a" + chr(0xD800) + "b") for e in page]
            return self.repondre(200, dict(ident, parent=parent, entries=page, next_cursor=suite))
        if p == ["directories"] and m == "POST":
            d = json.loads(brut)
            parent = f.entries.get(d["parent_id"])
            if not parent or parent["revision"] != d["parent_revision"]:
                return self.erreur(409, "destination_changed")
            if any(e.get("parent") == parent["id"] and e["name"] == d["name"] for e in f.entries.values()):
                return self.erreur(409, "name_conflict")
            eid = f.nouvel_id("d")
            f.entries[eid] = {"id": eid, "parent": parent["id"], "name": d["name"], "kind": "directory", "revision": "r" + eid}
            f.enfant_change(parent["id"])
            return self.repondre(200, dict(ident, entry=f.entries[eid]))
        if p == ["uploads"] and m == "POST":
            cle = self.headers.get("Idempotency-Key", "")
            if not (16 <= len(cle) <= 128):
                return self.erreur(422, "invalid")
            d = json.loads(brut)
            if (dev, cle) in f.par_cle:
                up = f.uploads[f.par_cle[(dev, cle)]]
                if up["intention"] != d:
                    return self.erreur(409, "idempotency_conflict")
            else:
                if d["name"] == f.nom_refuse or len(d["name"].encode()) > 240:
                    return self.erreur(400, "invalid_name")
                if sum(1 for x in f.uploads.values() if x["dev"] == dev and x["state"] == "pending") >= f.limite_envois:
                    return self.erreur(429, "too_many_transfers")
                if d["size"] > f.quota:
                    return self.erreur(507, "quota_exceeded")
                if d["policy"] == "replace" and not d.get("expected_revision"):
                    return self.erreur(428, "precondition_required")
                if f.entries[d["parent_id"]]["revision"] != d["parent_revision"]:
                    return self.erreur(409, "destination_changed")
                uid = f.nouvel_id("u")
                up = {"upload_id": uid, "state": "pending", "chunks": {}, "intention": d, "dev": dev, "result": None}
                f.uploads[uid] = up
                f.par_cle[(dev, cle)] = uid
                if "perdre_creation" in f.pannes:
                    f.pannes.discard("perdre_creation")
                    return self.couper()
            return self.repondre(200, self.vue(up, ident))
        if len(p) >= 2 and p[0] == "uploads":
            up = f.uploads.get(p[1])
            if not up or up["dev"] != dev:
                return self.erreur(404, "not_found")
            if m == "GET" and len(p) == 2:
                return self.repondre(200, self.vue(up, ident))
            if m == "DELETE" and len(p) == 2:
                if up["state"] == "pending":
                    up["state"] = "cancelled"
                    up["chunks"] = {}
                return self.repondre(200, self.vue(up, ident))
            if up["state"] == "invalidated" and m in ("PUT", "POST"):
                return self.erreur(410, "upload_invalidated")
            if m == "PUT" and len(p) == 4 and p[2] == "chunks":
                if up["state"] != "pending":
                    return self.erreur(409, "upload_not_pending")
                i = int(p[3])
                if hashlib.sha256(brut).hexdigest() != self.headers.get("X-Content-SHA256"):
                    return self.erreur(422, "integrity_error")
                if f.lent:
                    time.sleep(f.lent)
                up["chunks"][i] = brut
                f.journal.append(("MORCEAU", str(i), {}))
                if f"couper_apres:{i}" in f.pannes:
                    f.pannes.discard(f"couper_apres:{i}")
                    return self.couper()
                return self.repondre(200, dict(ident, index=i))
            if m == "POST" and p[2:] == ["commit"]:
                if up["state"] == "committed":
                    return self.repondre(200, self.vue(up, ident))
                if up["state"] != "pending":
                    return self.erreur(409, "upload_not_pending")
                d = up["intention"]
                if "publier_ailleurs" in f.pannes:        # un autre PC publie dans ce dossier juste avant
                    f.pannes.discard("publier_ailleurs")
                    f.entries[d["parent_id"]]["revision"] = f.nouvel_id("rv")
                if "publier_ailleurs_toujours" in f.pannes:
                    f.entries[d["parent_id"]]["revision"] = f.nouvel_id("rv")
                if f.entries[d["parent_id"]]["revision"] != d["parent_revision"]:
                    return self.erreur(409, "destination_changed")
                donnees = b"".join(up["chunks"][i] for i in sorted(up["chunks"]))
                if len(donnees) != d["size"] or hashlib.sha256(donnees).hexdigest() != d["sha256"]:
                    return self.erreur(422, "integrity_error")
                existant = next((e for e in f.entries.values() if e.get("parent") == d["parent_id"] and e["name"] == d["name"]), None)
                nom = d["name"]
                if d["policy"] == "create" and existant:
                    return self.erreur(412, "version_conflict", current=existant)
                if d["policy"] == "replace" and (not existant or existant["revision"] != d["expected_revision"]):
                    return self.erreur(412, "version_conflict", current=existant)
                if d["policy"] == "keep_both" and existant:
                    k = 2
                    while any(e.get("parent") == d["parent_id"] and e["name"] == f"{nom} ({k})" for e in f.entries.values()):
                        k += 1
                    nom, existant = f"{nom} ({k})", None
                eid = existant["id"] if existant else f.nouvel_id("f")
                f.entries[eid] = {"id": eid, "parent": d["parent_id"], "name": nom, "kind": "file", "revision": "r" + f.nouvel_id(""),
                                  "size": d["size"], "sha256": d["sha256"], "modified": "2026-11-20T12:00:00Z"}
                f.contenus[eid] = donnees
                f.enfant_change(d["parent_id"])
                up["state"], up["chunks"], up["result"] = "committed", {}, f.entries[eid]
                if "perdre_commit" in f.pannes:
                    f.pannes.discard("perdre_commit")
                    return self.couper()
                return self.repondre(200, self.vue(up, ident))
        if len(p) == 2 and p[0] == "files" and m == "DELETE":
            if not f.suppression:
                return self.erreur(404, "not_found")
            cle = self.headers.get("Idempotency-Key", "")
            im = self.headers.get("If-Match")
            if (dev, cle) in f.recus_suppression:
                fid, rv, res = f.recus_suppression[(dev, cle)]
                if fid != p[1] or im != f'"{rv}"':
                    return self.erreur(409, "idempotency_conflict")
                return self.repondre(200, res)
            e = f.entries.get(p[1])
            if not e:
                return self.erreur(404, "not_found")
            if e["kind"] != "file":
                return self.erreur(409, "not_a_file")
            if not im:
                return self.erreur(428, "precondition_required")
            if im != f'"{e["revision"]}"':
                return self.erreur(412, "version_conflict", current=e)
            del f.entries[e["id"]]
            f.enfant_change(e["parent"])
            for x in f.uploads.values():
                if x["state"] == "pending" and x["intention"]["parent_id"] == e["parent"] and x["intention"]["name"] == e["name"]:
                    x["state"], x["chunks"] = "invalidated", {}
            res = dict(ident, deleted=True, file_id=e["id"], revision=e["revision"])
            f.recus_suppression[(dev, cle)] = (e["id"], e["revision"], res)
            if "perdre_suppression" in f.pannes:
                f.pannes.discard("perdre_suppression")
                return self.couper()
            return self.repondre(200, res)
        if len(p) == 3 and p[0] == "files" and p[2] == "content" and m == "GET":
            e = f.entries.get(p[1])
            if not e or e["kind"] != "file":
                return self.erreur(404, "not_found")
            donnees = f.contenus[e["id"]]
            if "contenu_faux" in f.pannes:
                donnees = b"X" * len(donnees)
            etag = '"' + e["revision"] + '"'
            debut = 0
            plage = self.headers.get("Range", "")
            if plage.startswith("bytes=") and self.headers.get("If-Range") == etag:
                debut = int(plage[6:].rstrip("-"))
            morceau = donnees[debut:]
            self.send_response(206 if debut else 200)
            self.send_header("ETag", etag)
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Length", str(len(morceau)))
            self.end_headers()
            if "couper_telechargement" in f.pannes:
                f.pannes.discard("couper_telechargement")
                self.wfile.write(morceau[:len(morceau) // 2])
                self.wfile.flush()
                return self.couper()
            self.wfile.write(morceau)
            return
        return self.erreur(404, "not_found")

    def vue(self, up, ident):
        chunks = [{"idx": i, "sha256": hashlib.sha256(up["chunks"][i]).hexdigest(), "size": len(up["chunks"][i])}
                  for i in sorted(up["chunks"])] if up["state"] == "pending" else []
        return dict(ident, upload_id=up["upload_id"], state=up["state"], chunk_bytes=F().morceau,
                    expires="2026-11-21T00:00:00Z", chunks=chunks, result=up["result"])


ETAT = {}


def F():
    return ETAT["faux"]


class Serveur(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


class CloudTest(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp(prefix="nc-cloud-"))
        self.addCleanup(shutil.rmtree, self.d, True)
        ETAT["faux"] = self.faux = Faux()
        self.srv = Serveur(("127.0.0.1", 0), Gestion)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.addCleanup(self.srv.server_close)
        self.addCleanup(self.srv.shutdown)
        self.home = self.d / "home"
        (self.home / ".config/nc").mkdir(parents=True)
        self.bin = self.d / "bin"
        self.bin.mkdir()
        self.trousseau = self.d / "trousseau"
        self.args_st = self.d / "secret-tool-args"
        st = self.bin / "secret-tool"
        st.write_text(f"""#!{sys.executable}
import sys, os, time
open({str(self.args_st)!r}, "a").write(repr(sys.argv[1:]) + "\\n")
t = {str(self.trousseau)!r}
if os.path.exists(t + ".ferme"):
    sys.exit(1)
if sys.argv[1] == "store":
    if os.path.exists(t + ".lent"):
        time.sleep(20)
    open(t, "w").write(sys.stdin.read())
elif sys.argv[1] == "lookup":
    if not os.path.exists(t):
        sys.exit(1)
    sys.stdout.write(open(t).read())
elif sys.argv[1] == "clear":
    if os.path.exists(t):
        os.remove(t)
""")
        st.chmod(0o755)
        self.url("http://127.0.0.1:%d" % self.srv.server_address[1])
        self.sorties = []

    def url(self, url, cle=CLE):
        c = self.home / ".config/nc/assistant.conf"
        c.write_text(f'URL="{url}"\nSECRET_KEY="{cle}"\n')
        c.chmod(0o600)

    def env(self):
        return {"HOME": str(self.home), "PATH": str(self.bin), "TMPDIR": str(self.d), "NC_LANGUE": "fr",
                "XDG_CONFIG_HOME": str(self.home / ".config"), "XDG_STATE_HOME": str(self.home / ".local/state"),
                "XDG_DATA_HOME": str(self.home / ".local/share"), "XDG_CACHE_HOME": str(self.home / ".cache"),
                "XDG_RUNTIME_DIR": str(self.d)}

    def nc(self, *args, code=None):
        r = subprocess.run([sys.executable, str(NC_CLOUD), "--json", *args], capture_output=True, text=True, timeout=60,
                           env=self.env(), stdin=subprocess.DEVNULL)
        self.sorties.append(r.stdout + r.stderr)
        if code is not None:
            self.assertEqual(r.returncode, code, r.stdout + r.stderr)
        r.lignes = [json.loads(x) for x in r.stdout.splitlines() if x.startswith("{")]
        return r

    def associer(self):
        self.nc("associer", "portable", code=0)

    def fichier(self, nom, donnees):
        p = self.d / "src" / nom
        p.parent.mkdir(exist_ok=True)
        p.write_bytes(donnees)
        return p

    def morceaux_recus(self):
        return [int(c[1]) for c in self.faux.journal if c[0] == "MORCEAU"]

    def manifestes(self, dossier="envois"):
        return list((self.home / ".local/state/nc-cloud" / dossier).glob("*.json"))

    def creations(self):
        return [c for c in self.faux.journal if c[0] == "POST" and c[1].endswith("/uploads")]

    def tearDown(self):
        """Ni la clé ni le jeton nulle part : argv de secret-tool, sorties, adresses, fichiers écrits."""
        vus = "\n".join(self.sorties)
        if self.args_st.exists():
            vus += self.args_st.read_text()
        vus += "\n".join(c[1] for c in self.faux.journal)
        for p in self.d.rglob("*"):
            if p.is_file() and not p.is_symlink() and p != self.trousseau and p.name != "assistant.conf":
                vus += p.read_bytes().decode("utf-8", "replace")
        self.assertNotIn(CLE, vus)
        self.assertNotIn(JETON, vus)
        self.assertNotIn("cle_sur_donnees", self.faux.pannes, "la clé JARVIS est partie sur une route de données")

    # ── Association et transport ──

    def test_associer_jeton_dans_le_trousseau(self):
        self.associer()
        self.assertEqual(self.trousseau.read_text(), JETON)
        app = json.loads((self.home / ".local/state/nc-cloud/appareil.json").read_text())
        self.assertEqual(app["server_id"], "srv-1")
        self.assertEqual(stat.S_IMODE((self.home / ".local/state/nc-cloud").stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE((self.home / ".local/state/nc-cloud/appareil.json").stat().st_mode), 0o600)
        self.nc("associer", code=1)                    # déjà associé
        self.assertEqual(len(self.faux.devices), 1)
        r = self.nc("verifier", code=0)
        self.assertTrue(r.lignes[-1]["pret"])

    def test_cle_du_serveur_refusee(self):
        self.url("http://127.0.0.1:%d" % self.srv.server_address[1], cle="une-autre-cle-0123456789")
        r = self.nc("associer", code=1)
        self.assertIn("Clé du serveur refusée", r.stdout)

    def test_trousseau_ferme_rien_n_est_ecrit_et_appareil_revoque(self):
        (self.d / "trousseau.ferme").write_text("")
        self.nc("associer", code=1)
        self.assertFalse((self.home / ".local/state/nc-cloud/appareil.json").exists())
        self.assertTrue(all(d["revoque"] for d in self.faux.devices.values()))

    def test_ctrl_c_pendant_le_rangement_du_jeton(self):
        (self.d / "trousseau.lent").write_text("")
        pr = subprocess.Popen([sys.executable, str(NC_CLOUD), "--json", "associer", "pc"], stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, text=True, env=self.env(), stdin=subprocess.DEVNULL)
        fin = time.monotonic() + 20
        while not (self.args_st.exists() and "store" in self.args_st.read_text()) and time.monotonic() < fin:
            time.sleep(0.05)
        pr.send_signal(signal.SIGINT)
        out, err = pr.communicate(timeout=30)
        self.sorties.append(out + err)
        self.assertEqual(pr.returncode, 8, out + err)
        self.assertTrue(self.faux.devices and all(d["revoque"] for d in self.faux.devices.values()))
        self.assertFalse((self.home / ".local/state/nc-cloud/appareil.json").exists())

    def test_sans_secret_tool(self):
        (self.bin / "secret-tool").unlink()
        self.nc("associer", code=1)
        self.assertEqual(self.faux.journal, [])

    def test_http_public_refuse_sans_connexion(self):
        self.url("http://203.0.113.7:%d" % self.srv.server_address[1])
        r = self.nc("verifier", code=9)
        self.assertEqual(self.faux.journal, [])
        self.assertIn("Transport refusé", r.stdout)

    def test_redirection_non_suivie(self):
        self.faux.pannes.add("redirection")
        self.nc("associer", code=9)
        self.assertEqual(len(self.faux.journal), 1)

    def test_cloud_desactive(self):
        self.faux.enabled = False
        self.nc("associer", code=5)
        r = self.nc("verifier", code=5)
        self.assertFalse(r.lignes[-1]["pret"])

    def test_ia_coupee_ne_coupe_pas_le_cloud(self):
        (self.home / ".config/nc/reglages.conf").write_text("IA_MODE=non\n")
        self.associer()

    def test_sans_serveur_configure(self):
        (self.home / ".config/nc/assistant.conf").unlink()
        self.nc("etat", code=5)

    def test_dissocier(self):
        self.associer()
        self.nc("dissocier", code=0)
        self.assertFalse(self.trousseau.exists())
        self.assertTrue(all(d["revoque"] for d in self.faux.devices.values()))
        self.nc("etat", code=4)

    def test_appareil_revoque(self):
        self.associer()
        for d in self.faux.devices.values():
            d["revoque"] = True
        self.nc("etat", code=4)

    def test_stockage_indisponible(self):
        self.associer()
        self.faux.pannes.add("stockage")
        self.nc("etat", code=3)

    def test_serveur_change(self):
        self.associer()
        self.faux.server_id = "autre"
        self.nc("etat", code=10)
        p = self.fichier("a.txt", b"abc")
        self.nc("deposer", str(p), code=10)
        self.assertEqual(self.morceaux_recus(), [])

    def test_hors_ligne(self):
        self.associer()
        self.srv.shutdown()
        self.srv.server_close()
        p = self.fichier("a.txt", b"abc")
        self.nc("deposer", str(p), code=3)
        self.assertFalse(self.manifestes())

    def test_reponses_hostiles(self):
        self.associer()
        self.faux.pannes.add("json_profond")
        r = self.nc("etat", code=1)
        self.assertIn("Réponse du serveur invalide", r.stdout)
        self.faux.pannes = {"demi_paire"}
        self.nc("dossier", "root", "x", code=0)
        r = self.nc("lister", code=1)
        self.assertIn("Réponse du serveur invalide", r.stdout)

    # ── Envois ──

    def test_envoi_complet_vide_et_plusieurs_morceaux(self):
        self.associer()
        grand = os.urandom(MORCEAU * 2 + 10)
        p1, p2, p3 = self.fichier("petit.txt", b"bonjour"), self.fichier("vide.txt", b""), self.fichier("grand.bin", grand)
        r = self.nc("deposer", str(p1), str(p2), str(p3), code=0)
        res = [l for l in r.lignes if l.get("evenement") == "resultat"]
        self.assertEqual([l["etat"] for l in res], ["publie"] * 3)
        par_nom = {e["name"]: e for e in self.faux.entries.values()}
        self.assertEqual(self.faux.contenus[par_nom["grand.bin"]["id"]], grand)
        self.assertEqual(self.faux.contenus[par_nom["vide.txt"]["id"]], b"")
        self.assertTrue(any(l.get("evenement") == "progression" for l in r.lignes))
        self.assertEqual(p3.read_bytes(), grand)       # source intacte
        self.assertFalse(self.manifestes())

    def test_revision_du_dossier_qui_change_a_chaque_fichier(self):
        self.faux.revisions_vivantes = True
        self.associer()
        ps = [self.fichier(f"f{i}.txt", b"x" * i) for i in range(3)]
        self.nc("deposer", *map(str, ps), code=0)
        self.assertEqual(sum(1 for e in self.faux.entries.values() if e["kind"] == "file"), 3)

    def test_destination_changee_une_seule_intention_neuve(self):
        self.faux.revisions_vivantes = True
        self.associer()
        p = self.fichier("a.txt", b"abc")
        self.faux.pannes.add("publier_ailleurs")
        r = self.nc("deposer", str(p), code=0)
        self.assertEqual(r.lignes[-1]["etat"], "publie")
        self.assertEqual(len({c[2]["Idempotency-Key"] for c in self.creations()}), 2)
        self.faux.pannes.add("publier_ailleurs_toujours")
        r = self.nc("deposer", "--si-existe", "garder", str(p), code=6)
        self.assertEqual(len(self.creations()), 4)            # une seule relance, puis le conflit
        self.assertTrue(any(l.get("evenement") == "conflit" for l in r.lignes))

    def test_dossiers_liens_et_plus_de_8(self):
        self.associer()
        p = self.fichier("a.txt", b"a")
        lien = self.d / "src/lien"
        lien.symlink_to(p)
        long = self.fichier("é" * 121 + ".txt", b"x")     # 246 octets : refusé ici, comme le serveur
        r = self.nc("deposer", str(self.d / "src"), str(lien), str(long), str(p), code=1)
        etats = [l["etat"] for l in r.lignes if l.get("evenement") == "resultat"]
        self.assertEqual(etats, ["refuse", "refuse", "refuse", "publie"])
        self.nc("deposer", *[str(p)] * 9, code=2)

    def test_nom_refuse_et_trop_d_envois_n_arretent_pas_le_lot(self):
        self.associer()
        a, b, c = self.fichier("a.txt", b"1"), self.fichier("b.txt", b"2"), self.fichier("c.txt", b"3")
        self.faux.nom_refuse = "b.txt"
        r = self.nc("deposer", str(a), str(b), str(c), code=1)
        self.assertEqual([l["etat"] for l in r.lignes if l.get("evenement") == "resultat"], ["publie", "echec", "publie"])
        self.faux.limite_envois = 0
        d, e = self.fichier("d.txt", b"4"), self.fichier("e.txt", b"5")
        r = self.nc("deposer", str(d), str(e), code=1)
        res = [l for l in r.lignes if l.get("evenement") == "resultat"]
        self.assertEqual([l["etat"] for l in res], ["echec", "echec"])
        self.assertIn("Trop d'envois", res[0]["message"])
        self.assertFalse(self.manifestes())

    def test_taille_de_morceau_absurde_refusee(self):
        self.associer()
        self.faux.morceau = 10
        p = self.fichier("a.txt", b"abcdef" * 10)
        r = self.nc("deposer", str(p), code=1)
        self.assertIn("Taille de morceau", r.lignes[-1]["message"])
        self.assertEqual(self.morceaux_recus(), [])

    def test_reponse_de_creation_perdue(self):
        self.associer()
        self.faux.pannes.add("perdre_creation")
        p = self.fichier("a.bin", os.urandom(MORCEAU + 5))
        self.nc("deposer", str(p), code=3)
        r = self.nc("reprendre", code=0)
        self.assertEqual(len(r.lignes[-1]["envois"]), 1)
        self.nc("reprendre", "1", code=0)
        self.assertEqual(len(self.faux.uploads), 1)    # même clé : le même envoi, pas un second
        self.assertEqual(sum(1 for e in self.faux.entries.values() if e["kind"] == "file"), 1)

    def test_reponse_de_publication_perdue(self):
        self.associer()
        self.faux.pannes.add("perdre_commit")
        p = self.fichier("a.txt", b"abc")
        self.nc("deposer", str(p), code=3)
        avant = len(self.morceaux_recus())
        r = self.nc("reprendre", "1", code=0)
        self.assertEqual(r.lignes[-1]["etat"], "publie")
        self.assertEqual(len(self.morceaux_recus()), avant)     # rien n'est renvoyé
        self.assertEqual(sum(1 for e in self.faux.entries.values() if e["kind"] == "file"), 1)

    def test_coupure_puis_reprise_des_morceaux_manquants(self):
        self.associer()
        self.faux.pannes.add("couper_apres:1")
        donnees = os.urandom(MORCEAU * 4)
        p = self.fichier("gros.bin", donnees)
        self.nc("deposer", str(p), code=3)
        self.assertEqual(self.morceaux_recus(), [0, 1])
        m = self.manifestes()[0]
        self.assertEqual(stat.S_IMODE(m.stat().st_mode), 0o600)
        self.nc("reprendre", "1", code=0)
        self.assertEqual(self.morceaux_recus(), [0, 1, 2, 3])       # seuls les morceaux manquants repartent
        eid = next(e["id"] for e in self.faux.entries.values() if e["name"] == "gros.bin")
        self.assertEqual(self.faux.contenus[eid], donnees)

    def test_source_modifiee_avant_reprise(self):
        self.associer()
        self.faux.pannes.add("couper_apres:0")
        p = self.fichier("gros.bin", os.urandom(MORCEAU * 3))
        self.nc("deposer", str(p), code=3)
        p.write_bytes(os.urandom(MORCEAU * 3))
        self.nc("reprendre", "1", code=11)
        self.assertEqual(self.morceaux_recus(), [0])
        self.assertTrue(all(u["state"] == "cancelled" for u in self.faux.uploads.values()))
        self.assertFalse(self.manifestes())

    def test_reprendre_un_envoi_expire_annule_ou_invalide(self):
        self.associer()
        for etat in ("expired", "cancelled", "invalidated"):
            with self.subTest(etat=etat):
                self.faux.pannes.add("couper_apres:0")
                p = self.fichier(f"{etat}.bin", os.urandom(MORCEAU * 3))
                self.nc("deposer", str(p), code=3)
                for u in self.faux.uploads.values():
                    if u["state"] == "pending":
                        u["state"] = etat
                avant = len(self.morceaux_recus())
                r = self.nc("reprendre", "1", code=1)
                self.assertIn("dépose-le à nouveau", r.stdout)
                self.assertEqual(len(self.morceaux_recus()), avant)
                self.assertFalse(self.manifestes())

    def test_envoi_invalide_par_une_suppression_ailleurs(self):
        self.faux.suppression = True
        self.associer()
        p = self.fichier("a.txt", b"v1")
        eid = self.nc("deposer", str(p), code=0).lignes[-1]["entree"]["id"]
        rev = self.faux.entries[eid]["revision"]
        self.faux.pannes.add("couper_apres:0")
        p.write_bytes(os.urandom(MORCEAU * 2))
        self.nc("deposer", "--si-existe", "remplacer:" + rev, str(p), code=3)
        self.nc("supprimer", eid, "--revision", rev, code=0)          # « un autre PC » supprime le fichier
        self.assertEqual([u["state"] for u in self.faux.uploads.values()][-1], "invalidated")
        self.nc("reprendre", "1", code=1)
        self.assertFalse(self.manifestes())

    def test_conflits_jamais_resolus_tout_seuls(self):
        self.associer()
        p = self.fichier("rapport.txt", b"v1")
        self.nc("deposer", str(p), code=0)
        p.write_bytes(b"v2")
        n = len(self.creations())
        r = self.nc("deposer", str(p), code=6)
        self.assertEqual(len(self.creations()), n, "le nom pris se voit avant d'envoyer")
        conflit = next(l for l in r.lignes if l.get("evenement") == "conflit")
        rev = conflit["actuel"]["revision"]
        self.assertFalse(self.manifestes())
        r = self.nc("deposer", "--si-existe", "annuler", str(p), code=0)
        self.assertEqual(r.lignes[-1]["etat"], "annule")
        r = self.nc("deposer", "--si-existe", "garder", str(p), code=0)
        self.assertEqual(r.lignes[-1]["entree"]["name"], "rapport.txt (2)")
        self.nc("deposer", "--si-existe", "remplacer:mauvaise", str(p), code=6)      # 412
        r = self.nc("deposer", "--si-existe", "remplacer:" + rev, str(p), code=0)
        eid = r.lignes[-1]["entree"]["id"]
        self.assertEqual(self.faux.contenus[eid], b"v2")
        self.assertEqual(len({c[2].get("Idempotency-Key") for c in self.creations()}), 4)   # une clé neuve par intention
        self.assertTrue(all(u["state"] != "pending" for u in self.faux.uploads.values()))
        # Nom pris entre la vérification et la publication : le 412 du commit reste un conflit
        self.faux.pannes.add("cacher_noms")
        r = self.nc("deposer", str(p), code=6)
        self.assertTrue(any(l.get("evenement") == "conflit" for l in r.lignes))
        self.assertFalse(self.manifestes())

    def test_quota_depasse(self):
        self.associer()
        self.faux.quota = 2
        p = self.fichier("a.txt", b"abcdef")
        r = self.nc("deposer", str(p), code=7)
        self.assertEqual(r.lignes[-1]["etat"], "echec")
        self.assertFalse(self.manifestes())

    def test_sigint_pendant_un_envoi(self):
        self.associer()
        self.faux.lent = 0.3
        p = self.fichier("gros.bin", os.urandom(MORCEAU * 20))
        pr = subprocess.Popen([sys.executable, str(NC_CLOUD), "--json", "deposer", str(p)], stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, text=True, env=self.env(), stdin=subprocess.DEVNULL)
        sortie = ""
        for ligne in pr.stdout:
            sortie += ligne
            if '"progression"' in ligne:
                pr.send_signal(signal.SIGINT)
                break
        reste, err = pr.communicate(timeout=60)
        self.sorties.append(sortie + reste + err)
        self.assertEqual(pr.returncode, 8, sortie + reste + err)
        self.assertTrue(any(c[0] == "DELETE" and "/uploads/" in c[1] for c in self.faux.journal))
        self.assertTrue(all(u["state"] == "cancelled" for u in self.faux.uploads.values()))
        self.assertFalse(self.manifestes())

    # ── Navigation et téléchargement ──

    def test_lister_dossier_et_suite(self):
        self.associer()
        for n in ("a", "b", "c"):
            self.nc("dossier", "root", n, code=0)
        self.nc("dossier", "root", "a", code=6)            # name_conflict
        r = self.nc("lister", code=0)
        self.assertEqual(len(r.lignes[-1]["entries"]), 2)
        suite = r.lignes[-1]["next_cursor"]
        r = self.nc("lister", "root", "--suite", suite, code=0)
        self.assertEqual([e["name"] for e in r.lignes[-1]["entries"]], ["c"])

    def test_nom_hostile(self):
        self.associer()
        p = self.fichier("a.txt", b"abc")
        r = self.nc("deposer", str(p), code=0)
        eid = r.lignes[-1]["entree"]["id"]
        self.faux.pannes.add("nom_hostile")
        r = self.nc("lister", code=0)
        nom = r.lignes[-1]["entries"][0]["name"]
        self.assertFalse(any(ord(c) < 32 or c == RLO for c in nom), repr(nom))
        dest = self.d / "dest"
        dest.mkdir()
        self.nc("telecharger", eid, str(dest), code=0)
        self.assertEqual([x.name for x in dest.iterdir()], ["[31mpiège"])
        self.assertFalse((self.d / "[31mpiège").exists())

    def deposer_gros(self, taille=MORCEAU * 3):
        self.associer()
        donnees = os.urandom(taille)
        r = self.nc("deposer", str(self.fichier("g.bin", donnees)), code=0)
        return r.lignes[-1]["entree"]["id"], donnees

    def test_telecharger_reprise_et_empreinte_fausse(self):
        eid, donnees = self.deposer_gros()
        dest = self.d / "g.bin"
        self.faux.pannes.add("couper_telechargement")
        self.nc("telecharger", eid, str(dest), code=3)
        self.assertFalse(dest.exists())
        self.nc("telecharger", eid, str(dest), code=0)
        self.assertEqual(dest.read_bytes(), donnees)
        plages = [c[2].get("Range") for c in self.faux.journal if c[1].endswith("/content")]
        self.assertIsNone(plages[0])
        self.assertTrue(plages[1] and plages[1].startswith("bytes="))
        self.nc("telecharger", eid, str(dest), code=1)          # existe déjà
        self.faux.pannes.add("contenu_faux")
        self.nc("telecharger", eid, str(dest), "--remplacer", code=12)
        self.assertEqual(dest.read_bytes(), donnees)             # rien n'est remplacé
        self.assertEqual([x.name for x in self.d.glob(".g.bin*")], [])

    def test_deux_telechargements_vers_la_meme_destination(self):
        eid, _ = self.deposer_gros()
        partiel = self.d / ".g.bin.nc-cloud-partiel"
        fd = os.open(str(partiel), os.O_RDWR | os.O_CREAT, 0o600)      # un autre téléchargement tient le verrou
        self.addCleanup(os.close, fd)
        fcntl.flock(fd, fcntl.LOCK_EX)
        r = self.nc("telecharger", eid, str(self.d / "g.bin"), code=1)
        self.assertIn("déjà en cours", r.stdout)
        self.assertFalse((self.d / "g.bin").exists())

    def test_partiel_en_lien_dur_ou_symbolique_refuse(self):
        eid, _ = self.deposer_gros()
        autre = self.d / "autre.txt"
        autre.write_bytes(b"un autre fichier")
        os.link(autre, self.d / ".g.bin.nc-cloud-partiel")
        self.nc("telecharger", eid, str(self.d / "g.bin"), code=1)
        self.assertEqual(autre.read_bytes(), b"un autre fichier")
        self.assertFalse((self.d / "g.bin").exists())
        cible = self.d / "cible.txt"
        cible.write_bytes(b"intact")
        os.symlink(cible, self.d / ".h.bin.nc-cloud-partiel")
        self.nc("telecharger", eid, str(self.d / "h.bin"), code=1)
        self.assertEqual(cible.read_bytes(), b"intact")

    # ── Suppression ──

    def test_supprimer(self):
        self.faux.suppression = True
        eid, _ = self.deposer_gros(10)
        rev = self.faux.entries[eid]["revision"]
        self.nc("supprimer", eid, code=2)                           # --revision obligatoire
        self.nc("supprimer", eid, "--revision", "*", code=2)
        self.nc("supprimer", eid, "--revision", "ancienne", code=6)  # 412 : rien n'est supprimé
        self.assertIn(eid, self.faux.entries)
        r = self.nc("supprimer", eid, "--revision", rev, code=0)
        self.assertEqual(r.lignes[-1]["etat"], "supprime")
        self.assertNotIn(eid, self.faux.entries)
        im = [c[2].get("If-Match") for c in self.faux.journal if c[0] == "DELETE" and "/files/" in c[1]]
        self.assertEqual(im[-1], f'"{rev}"')
        self.nc("supprimer", eid, "--revision", rev, code=1)        # 404 : déjà supprimé
        self.assertFalse(self.manifestes("suppressions"))

    def test_supprimer_reponse_perdue_puis_rejeu(self):
        self.faux.suppression = True
        eid, _ = self.deposer_gros(10)
        rev = self.faux.entries[eid]["revision"]
        self.faux.pannes.add("perdre_suppression")
        self.nc("supprimer", eid, "--revision", rev, code=3)
        self.assertEqual(len(self.manifestes("suppressions")), 1)
        r = self.nc("supprimer", eid, "--revision", rev, code=0)    # même clé : le reçu du serveur
        self.assertEqual(r.lignes[-1]["etat"], "supprime")
        cles = [c[2].get("Idempotency-Key") for c in self.faux.journal if c[0] == "DELETE" and "/files/" in c[1]]
        self.assertEqual(len(cles), 2)
        self.assertEqual(len(set(cles)), 1)
        self.assertFalse(self.manifestes("suppressions"))

    def test_supprimer_sans_capacite_ou_dossier(self):
        eid, _ = self.deposer_gros(10)
        rev = self.faux.entries[eid]["revision"]
        r = self.nc("supprimer", eid, "--revision", rev, code=1)
        self.assertIn("ne sait pas supprimer", r.stdout)
        self.assertFalse([c for c in self.faux.journal if c[0] == "DELETE" and "/files/" in c[1]])
        self.faux.suppression = True
        self.nc("dossier", "root", "d", code=0)
        did = next(e["id"] for e in self.faux.entries.values() if e["kind"] == "directory" and e["name"] == "d")
        r = self.nc("supprimer", did, "--revision", self.faux.entries[did]["revision"], code=1)
        self.assertIn("dossier", r.stdout)
        self.assertIn(did, self.faux.entries)


class DansLeProcessus(unittest.TestCase):
    """nc-cloud chargé comme module : socket.getaddrinfo remplacé (aucun DNS), pour le transport résolu (T1)."""

    def charger(self, url):
        d = Path(tempfile.mkdtemp(prefix="nc-cloud-p-"))
        self.addCleanup(shutil.rmtree, d, True)
        h = d / "home"
        (h / ".config/nc").mkdir(parents=True)
        c = h / ".config/nc/assistant.conf"
        c.write_text(f'URL="{url}"\nSECRET_KEY="{CLE}"\n')
        c.chmod(0o600)
        env = mock.patch.dict(os.environ, {"HOME": str(h), "XDG_CONFIG_HOME": str(h / ".config"), "TMPDIR": str(d),
                                           "XDG_STATE_HOME": str(h / ".local/state"), "NC_LANGUE": "fr", "PATH": str(d)})
        env.start()
        self.addCleanup(env.stop)
        l = importlib.machinery.SourceFileLoader("nc_cloud_essai", str(NC_CLOUD))
        m = importlib.util.module_from_spec(importlib.util.spec_from_loader("nc_cloud_essai", l))
        l.exec_module(m)
        return m

    def lancer(self, m, *args):
        sortie = io.StringIO()
        anciens = signal.getsignal(signal.SIGINT), signal.getsignal(signal.SIGTERM)
        try:
            with contextlib.redirect_stdout(sortie), contextlib.redirect_stderr(sortie):
                code = m.main(list(args))
        finally:
            signal.signal(signal.SIGINT, anciens[0])
            signal.signal(signal.SIGTERM, anciens[1])
        self.assertNotIn(CLE, sortie.getvalue())
        return code, sortie.getvalue()

    def test_ts_net_resolu_en_adresse_publique_rien_ne_part(self):
        connexions = []
        m = self.charger("http://pc.tail1.ts.net:8000")
        faux = lambda h, port, *a, **k: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("203.0.113.7", port))]
        with mock.patch.object(socket, "getaddrinfo", faux), \
                mock.patch.object(socket, "create_connection", lambda *a, **k: connexions.append(a) or 1 / 0):
            code, sortie = self.lancer(m, "--json", "verifier")
        self.assertEqual(code, 9, sortie)
        self.assertEqual(connexions, [])

    def test_nom_introuvable_hors_ligne(self):
        m = self.charger("http://pc.tail1.ts.net:8000")

        def faux(*a, **k):
            raise socket.gaierror(socket.EAI_NONAME, "introuvable")
        with mock.patch.object(socket, "getaddrinfo", faux):
            code, sortie = self.lancer(m, "etat")
        self.assertEqual(code, 3, sortie)

    def test_ipv6_sans_port(self):
        m = self.charger("http://[::1]")
        srv = m.Serveur()
        self.assertEqual((srv.port, srv.adresse), (80, "::1"))
        c = srv.connexion()
        self.assertEqual((c.host, c.port), ("::1", 80))


if __name__ == "__main__":
    unittest.main()

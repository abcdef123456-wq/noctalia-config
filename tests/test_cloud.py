"""nc-cloud contre un faux serveur du Cloud JARVIS (HTTP en boucle locale, écrit ici d'après le contrat d'API v1).

Aucun vrai serveur. HOME, XDG_* et TMPDIR pointent vers un dossier jetable ; secret-tool est un faux qui range le jeton
dans un fichier du test et note ses arguments. Après chaque test, la clé JARVIS et le jeton sont cherchés partout :
arguments de secret-tool, sorties, adresses reçues par le serveur, fichiers écrits (hors le faux trousseau et
assistant.conf)."""
import hashlib
import http.server
import json
import os
from pathlib import Path
import signal
import socketserver
import stat
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import urllib.parse

REPO = Path(__file__).resolve().parents[1]
NC_CLOUD = REPO / "home/.local/bin/nc-cloud"
CLE = "cle-jarvis-tres-secrete-0123456789"
JETON = "jeton-cloud-aleatoire-abcdefghijklmnopqrstuvwxyz"
MORCEAU = 1024
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
        self.n = 0
        self.journal = []          # (méthode, chemin complet, en-têtes)
        self.pannes = set()
        self.quota = 10 ** 9
        self.lent = 0.0
        self.lock = threading.Lock()

    def nouvel_id(self, p):
        self.n += 1
        return f"{p}{self.n}"

    def ident(self):
        return {"api_version": 1, "server_id": self.server_id, "space_id": self.space_id}


class Gestion(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):
        pass

    def repondre(self, code, obj=None, entetes=None, corps=None):
        if corps is None:
            corps = json.dumps(obj if obj is not None else {}).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json" if obj is not None or code >= 400 else "application/octet-stream")
        for k, v in (entetes or {}).items():
            self.send_header(k, v)
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
                return self.erreur(401, "authentication_required")
            if p == ["capabilities"]:
                return self.repondre(200, dict(f.ident(), enabled=f.enabled, state=f.state if f.enabled else "disabled",
                                               reason=None, api_path="/api/cloud/v1", dav_path="/cloud/dav/"))
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
            return self.erreur(401, "device_revoked")
        ident = dict(f.ident(), device_id=dev)
        if p == ["status"]:
            return self.repondre(200, dict(ident, state="available", root="root", quota_bytes=f.quota, used_bytes=0,
                                           chunk_bytes=MORCEAU, max_file_bytes=5 * 2 ** 30, webdav="read_only"))
        if p == ["entries"] and m == "GET":
            parent = f.entries.get(q.get("parent_id", "root"))
            if not parent or parent["kind"] != "directory":
                return self.erreur(404, "not_found")
            enfants = [e for e in f.entries.values() if e.get("parent") == parent["id"]]
            debut = int(q.get("cursor") or 0)
            page = enfants[debut:debut + 2]           # pages de 2 (100 en vrai) pour tester la suite
            suite = str(debut + 2) if debut + 2 < len(enfants) else None
            if "nom_hostile" in f.pannes:
                page = [dict(e, name="../\x1b[31mpiège" + RLO + "\n") for e in page]
            return self.repondre(200, dict(ident, parent=parent, entries=page, next_cursor=suite))
        if p == ["directories"] and m == "POST":
            d = json.loads(brut)
            parent = f.entries.get(d["parent_id"])
            if not parent or parent["revision"] != d["parent_revision"]:
                return self.erreur(409, "destination_changed")
            if any(e.get("parent") == parent["id"] and e["name"] == d["name"] for e in f.entries.values()):
                return self.erreur(409, "version_conflict", current=None)
            eid = f.nouvel_id("d")
            f.entries[eid] = {"id": eid, "parent": parent["id"], "name": d["name"], "kind": "directory", "revision": "r" + eid}
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
                if d["size"] > f.quota:
                    return self.erreur(507, "quota_exceeded")
                if d["policy"] == "replace" and not d.get("expected_revision"):
                    return self.erreur(428, "precondition_required")
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
                donnees = b"".join(up["chunks"][i] for i in sorted(up["chunks"]))
                if len(donnees) != d["size"] or hashlib.sha256(donnees).hexdigest() != d["sha256"]:
                    return self.erreur(422, "integrity_error")
                existant = next((e for e in f.entries.values() if e.get("parent") == d["parent_id"] and e["name"] == d["name"]), None)
                nom = d["name"]
                if d["policy"] == "create" and existant:
                    return self.erreur(409, "version_conflict", current=existant)
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
                up["state"], up["chunks"], up["result"] = "committed", {}, f.entries[eid]
                if "perdre_commit" in f.pannes:
                    f.pannes.discard("perdre_commit")
                    return self.couper()
                return self.repondre(200, self.vue(up, ident))
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
        return dict(ident, upload_id=up["upload_id"], state=up["state"], chunk_bytes=MORCEAU, expires="2026-11-21T00:00:00Z",
                    chunks=sorted(up["chunks"]), result=up["result"])


ETAT = {}


def F():
    return ETAT["faux"]


class Serveur(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


class CloudTest(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp(prefix="nc-cloud-"))
        self.addCleanup(self.nettoyer)
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
import sys, os
open({str(self.args_st)!r}, "a").write(repr(sys.argv[1:]) + "\\n")
t = {str(self.trousseau)!r}
if os.path.exists(t + ".ferme"):
    sys.exit(1)
if sys.argv[1] == "store":
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

    def nettoyer(self):
        import shutil
        shutil.rmtree(self.d, ignore_errors=True)

    def url(self, url):
        c = self.home / ".config/nc/assistant.conf"
        c.write_text(f'URL="{url}"\nSECRET_KEY="{CLE}"\n')
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

    def test_trousseau_ferme_rien_n_est_ecrit_et_appareil_revoque(self):
        (self.d / "trousseau.ferme").write_text("")
        self.nc("associer", code=1)
        self.assertFalse((self.home / ".local/state/nc-cloud/appareil.json").exists())
        self.assertTrue(all(d["revoque"] for d in self.faux.devices.values()))

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
        self.assertFalse(list((self.home / ".local/state/nc-cloud").glob("envois/*.json")))

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
        self.assertFalse(list((self.home / ".local/state/nc-cloud").glob("envois/*.json")))

    def test_dossiers_liens_et_plus_de_8(self):
        self.associer()
        p = self.fichier("a.txt", b"a")
        lien = self.d / "src/lien"
        lien.symlink_to(p)
        r = self.nc("deposer", str(self.d / "src"), str(lien), str(p), code=1)
        etats = [l["etat"] for l in r.lignes if l.get("evenement") == "resultat"]
        self.assertEqual(etats, ["refuse", "refuse", "publie"])
        self.nc("deposer", *[str(p)] * 9, code=2)

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
        m = next((self.home / ".local/state/nc-cloud/envois").glob("*.json"))
        self.assertEqual(stat.S_IMODE(m.stat().st_mode), 0o600)
        self.nc("reprendre", "1", code=0)
        self.assertEqual(self.morceaux_recus(), [0, 1, 2, 3])
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
        self.assertFalse(list((self.home / ".local/state/nc-cloud").glob("envois/*.json")))

    def test_conflits_jamais_resolus_tout_seuls(self):
        self.associer()
        p = self.fichier("rapport.txt", b"v1")
        self.nc("deposer", str(p), code=0)
        p.write_bytes(b"v2")
        r = self.nc("deposer", str(p), code=6)
        conflit = next(l for l in r.lignes if l.get("evenement") == "conflit")
        rev = conflit["actuel"]["revision"]
        self.assertTrue(all(u["state"] != "pending" for u in self.faux.uploads.values()))
        self.assertFalse(list((self.home / ".local/state/nc-cloud").glob("envois/*.json")))
        r = self.nc("deposer", "--si-existe", "annuler", str(p), code=0)
        self.assertEqual(r.lignes[-1]["etat"], "annule")
        r = self.nc("deposer", "--si-existe", "garder", str(p), code=0)
        self.assertEqual(r.lignes[-1]["entree"]["name"], "rapport.txt (2)")
        self.nc("deposer", "--si-existe", "remplacer:mauvaise", str(p), code=6)      # 412
        r = self.nc("deposer", "--si-existe", "remplacer:" + rev, str(p), code=0)
        eid = r.lignes[-1]["entree"]["id"]
        self.assertEqual(self.faux.contenus[eid], b"v2")
        cles = {c[2].get("Idempotency-Key") for c in self.faux.journal if c[0] == "POST" and c[1].endswith("/uploads")}
        self.assertEqual(len(cles), 6)            # une clé neuve par intention

    def test_quota_depasse(self):
        self.associer()
        self.faux.quota = 2
        p = self.fichier("a.txt", b"abcdef")
        r = self.nc("deposer", str(p), code=7)
        self.assertEqual(r.lignes[-1]["etat"], "echec")
        self.assertFalse(list((self.home / ".local/state/nc-cloud").glob("envois/*.json")))

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
        self.assertFalse(list((self.home / ".local/state/nc-cloud").glob("envois/*.json")))

    # ── Navigation et téléchargement ──

    def test_lister_dossier_et_suite(self):
        self.associer()
        for n in ("a", "b", "c"):
            self.nc("dossier", "root", n, code=0)
        self.nc("dossier", "root", "a", code=6)
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

    def test_telecharger_reprise_et_empreinte_fausse(self):
        self.associer()
        donnees = os.urandom(MORCEAU * 3)
        r = self.nc("deposer", str(self.fichier("g.bin", donnees)), code=0)
        eid = r.lignes[-1]["entree"]["id"]
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


if __name__ == "__main__":
    unittest.main()

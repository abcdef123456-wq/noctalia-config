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
import re
import shlex
import shutil
import signal
import socket
import socketserver
import stat
import struct
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock
import urllib.parse
import zipfile
import zlib

REPO = Path(__file__).resolve().parents[1]
NC_CLOUD = REPO / "home/.local/bin/nc-cloud"
CLE = "cle-jarvis-tres-secrete-0123456789"
JETON = "jeton-cloud-aleatoire-abcdefghijklmnopqrstuvwxyz"
MORCEAU = 64 * 1024
RLO = chr(0x202E)    # inversion de sens : écrit par son code, jamais en vrai dans le source


def ecrire_outil(chemin, texte):
    """Un faux outil écrit comme un NOUVEAU fichier (O_EXCL, O_NOFOLLOW) : jamais à travers un lien posé là avant (le
    lien vers le vrai /usr/bin/file du test « avec le vrai file »)."""
    with contextlib.suppress(FileNotFoundError):
        os.unlink(chemin)
    fd = os.open(chemin, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o755)
    with os.fdopen(fd, "w") as f:
        f.write(texte)


def png_minimal():
    """Une vraie image PNG de 1 × 1 pixel."""
    def bloc(t, d):
        return len(d).to_bytes(4, "big") + t + d + zlib.crc32(t + d).to_bytes(4, "big")
    return (b"\x89PNG\r\n\x1a\n" + bloc(b"IHDR", (1).to_bytes(4, "big") * 2 + b"\x08\x02\x00\x00\x00")
            + bloc(b"IDAT", zlib.compress(b"\x00\xff\x00\x00")) + bloc(b"IEND", b""))


def jar(cafe=True):
    """Une archive JAR (jamais exécutée) : META-INF/ et son manifeste, avec ou sans l'en-tête 0xCAFE de l'outil jar."""
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w") as z:
        i = zipfile.ZipInfo("META-INF/")
        if cafe:
            i.extra = b"\xfe\xca\x00\x00"
        z.writestr(i, b"")
        z.writestr("META-INF/MANIFEST.MF", "Manifest-Version: 1.0\r\nMain-Class: A\r\n\r\n")
        z.writestr("A.class", b"\xca\xfe\xba\xbe" + b"\0" * 20)
    return b.getvalue()


PNG = png_minimal()
# Un en-tête ASF (Windows Media) : le GUID de l'objet d'en-tête, puis sa taille et des zéros
ASF = bytes.fromhex("3026b2758e66cf11a6d900aa0062ce6c") + (30).to_bytes(8, "little") + b"\0" * 14
PDF = b"%PDF-1.4\n1 0 obj << /Type /Catalog >> endobj\ntrailer << /Root 1 0 R >>\n%%EOF\n"
HTML = b"<!doctype html><script>fetch('http://exemple.invalid/')</script>"
SVG = b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>'


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
        self.curseur_force = None  # un curseur de page imposé (valeurs hostiles)
        self.quota = 10 ** 9
        self.lent = 0.0
        self.morceau = MORCEAU
        self.limite_envois = 8
        self.revisions_vivantes = False     # b7828d5 : la révision d'un dossier change à chaque enfant
        self.suppression = False            # b7828d5 : features.file_delete
        self.par_id = False                 # 36ce1f8 : features.entry_by_id (GET /entries/{id})
        self.conflit_tot = False            # 36ce1f8 : features.early_create_conflict (412 dès POST /uploads)
        self.gestion = False                # b8313b1 : entry_move, delete_preview, directory_delete
        self.recus_gestion = {}
        self.nom_refuse = None
        self.lock = threading.Lock()

    def nouvel_id(self, p):
        self.n += 1
        return f"{p}{self.n}"

    def ident(self):
        return {"api_version": 1, "server_id": self.server_id, "space_id": self.space_id}

    def features(self):
        f = {"file_delete": True, "delete_if_match": True, "delete_idempotency": True, "max_old_versions": 10} \
            if self.suppression else {}
        if self.par_id:
            f["entry_by_id"] = True
        if self.conflit_tot:
            f["early_create_conflict"] = True
        if self.gestion:
            f.update(entry_move=True, delete_preview=True, directory_delete=True, entry_by_id=True)
        return f

    def sous_arbre(self, eid):
        """L'entrée et tous ses descendants."""
        r, file = [], [eid]
        while file:
            x = file.pop()
            r.append(self.entries[x])
            file += [e["id"] for e in self.entries.values() if e.get("parent") == x]
        return r

    def arbre(self, eid):
        return hashlib.sha256(json.dumps(sorted((e["id"], e.get("parent"), e["name"], e["revision"])
                                                for e in self.sous_arbre(eid))).encode()).hexdigest()

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
        if "limiteur" in f.pannes:            # le limiteur du gateway : detail et Retry-After, sans champ error
            self.send_response(429)
            corps = json.dumps({"detail": "Too many requests"}).encode()
            self.send_header("Retry-After", "5")
            self.send_header("Content-Length", str(len(corps)))
            self.end_headers()
            self.wfile.write(corps)
            return
        if p[:1] == ["entries"] and len(p) >= 2 and f.gestion and (m in ("POST", "DELETE") or p[2:] == ["delete-preview"]):
            return self.gerer(m, p, brut, dev, ident)
        if len(p) == 2 and p[0] == "entries" and m == "GET" and (f.par_id or f.gestion):
            e = f.entries.get(p[1])
            if not e:
                return self.erreur(404, "not_found")
            if "autre_entree" in f.pannes:              # le serveur rend l'entrée d'un autre id
                e = dict(e, id="f-autre")
            return self.repondre(200, dict(f.ident(), entry=e))
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
            if suite and f.curseur_force:
                suite = f.curseur_force
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
                if f.conflit_tot and d["policy"] == "create":
                    pris = next((e for e in f.entries.values() if e.get("parent") == d["parent_id"] and e["name"] == d["name"]), None)
                    if pris:
                        return self.erreur(412, "version_conflict", current=pris)
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
                if "couper_annulation" in f.pannes:
                    return self.couper()
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

    def gerer(self, m, p, brut, dev, ident):
        """b8313b1, aux formes réelles (contrats/formes-b8313b1.md) et dans l'ordre réel des erreurs : aperçu,
        déplacement, suppression d'entrée ; reçus liés à l'appareil et à la demande complète."""
        f = F()
        e = f.entries.get(p[1])
        if m == "GET":
            if not e:
                return self.erreur(404, "not_found")
            sous = f.sous_arbre(e["id"])
            return self.repondre(200, dict(ident, entry=e, tree_revision=f.arbre(e["id"]), size=sum(x.get("size", 0) for x in sous),
                                           files=sum(1 for x in sous if x["kind"] == "file"),
                                           directories=sum(1 for x in sous if x["kind"] == "directory")))
        if m == "DELETE" and p[1] == "root":
            return self.repondre(404, {"error": "not_found"})                 # le gateway, avant le stockage
        try:
            d = json.loads(brut)
        except ValueError:
            return self.repondre(422, {"detail": [{"msg": "corps JSON obligatoire"}]})
        permis = {"parent_id", "parent_revision", "name"} if m == "POST" else {"recursive", "tree_revision"}
        if not isinstance(d, dict) or set(d) - permis or (m == "POST" and "parent_revision" not in d) or \
                (m == "DELETE" and d.get("tree_revision") is not None and not re.fullmatch(r"[0-9a-f]{64}", str(d["tree_revision"]))):
            return self.repondre(422, {"detail": [{"msg": "schéma"}]})
        cle, im = self.headers.get("Idempotency-Key", ""), self.headers.get("If-Match")
        if m == "POST" and (not d.get("name") or "/" in d["name"]):
            return self.erreur(400, "invalid_name")
        if not (16 <= len(cle) <= 128):
            return self.erreur(400, "invalid_idempotency_key")
        demande = (m, self.path, im, brut)
        if (dev, cle) in f.recus_gestion:
            avant, res = f.recus_gestion[(dev, cle)]
            return self.repondre(200, res) if avant == demande else self.erreur(409, "idempotency_conflict")
        if not e:
            return self.erreur(404, "not_found")
        if not im:
            return self.erreur(428, "precondition_required")
        if im != f'"{e["revision"]}"':
            return self.erreur(412, "version_conflict", current=e)
        if m == "POST" and p[2:] == ["move"]:
            if e["id"] == "root":
                return self.erreur(409, "root_protected")
            dest = f.entries.get(d.get("parent_id", "root"))             # root par défaut côté serveur
            if not dest:
                return self.erreur(404, "not_found")
            if dest["kind"] != "directory" or dest["revision"] != d["parent_revision"]:
                return self.erreur(409, "destination_changed")
            if dest["id"] in [x["id"] for x in f.sous_arbre(e["id"])]:
                return self.erreur(409, "invalid_destination")
            if any(x.get("parent") == dest["id"] and x["name"] == d["name"] and x["id"] != e["id"] for x in f.entries.values()):
                return self.erreur(409, "name_conflict")
            ancien = e["parent"]
            e.update(parent=dest["id"], name=d["name"], revision="r" + f.nouvel_id("m"))
            f.enfant_change(ancien)
            f.enfant_change(dest["id"])
            res = dict(ident, entry=e, moved=True)
        elif m == "DELETE" and len(p) == 2:
            sous = f.sous_arbre(e["id"])
            if e["kind"] == "directory":
                if len(sous) > 1 and not d.get("recursive"):
                    return self.erreur(409, "directory_not_empty")
                if d.get("recursive") and d.get("tree_revision") is None:
                    return self.erreur(428, "precondition_required")
                if d.get("recursive") and d["tree_revision"] != f.arbre(e["id"]):
                    return self.erreur(412, "tree_changed")
            for x in sous:
                del f.entries[x["id"]]
            f.enfant_change(e["parent"])
            res = dict(ident, deleted=True, entry_id=e["id"], count=len(sous))
        else:
            return self.erreur(404, "not_found")
        f.recus_gestion[(dev, cle)] = (demande, res)
        if "perdre_gestion" in f.pannes:
            f.pannes.discard("perdre_gestion")
            return self.couper()
        if "erreur_500_gestion" in f.pannes:                 # fait, mais le serveur répond une erreur interne
            f.pannes.discard("erreur_500_gestion")
            return self.repondre(500, {"detail": "Internal Server Error"})
        return self.repondre(200, res)

    def vue(self, up, ident):
        chunks = [{"idx": i, "sha256": hashlib.sha256(up["chunks"][i]).hexdigest(), "size": len(up["chunks"][i])}
                  for i in sorted(up["chunks"])] if up["state"] == "pending" else []
        return dict(ident, upload_id=up["upload_id"], state=up["state"], chunk_bytes=F().morceau,
                    expires="2026-11-21T00:00:00Z", chunks=chunks, result=up["result"])


ETAT = {}


def partiel_de(nom):
    return ".nc-cloud-" + hashlib.sha256(nom.encode()).hexdigest()[:16] + ".partiel"


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
        # Rien de la machine : un os-release factice (distribution inconnue) et, sans faux_gi(), un gi « absent »
        if not (self.d / "os-release").exists():
            (self.d / "os-release").write_text('ID="inconnue"\n')
        if not hasattr(self, "plus"):
            self.faux_gi("absent")
        return {"NC_OS_RELEASE": str(self.d / "os-release"), **self.plus, "HOME": str(self.home), "PATH": str(self.bin), "TMPDIR": str(self.d), "NC_LANGUE": "fr",
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

    def nc_entree(self, entree, *args, code=None):
        """nc-cloud avec `entree` (octets) sur son entrée standard."""
        r = subprocess.run([sys.executable, str(NC_CLOUD), "--json", *args], capture_output=True, timeout=60, env=self.env(), input=entree)
        r.stdout, r.stderr = r.stdout.decode("utf-8", "replace"), r.stderr.decode("utf-8", "replace")
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

    def test_resume_en_derniere_ligne_pour_les_reglages(self):
        def texte(*args):
            return subprocess.run([sys.executable, str(NC_CLOUD), *args], capture_output=True, text=True, timeout=60,
                                  env=self.env(), stdin=subprocess.DEVNULL)
        r = texte("verifier")
        self.assertEqual(r.returncode, 4)
        self.assertTrue(r.stderr.strip().splitlines()[-1].startswith("À faire : Ce PC n'est pas associé"), r.stderr)
        self.associer()
        r = texte("verifier")
        self.assertEqual((r.returncode, r.stdout.strip().splitlines()[-1]), (0, "Tout est prêt."))
        r = texte("etat")
        self.assertEqual(r.returncode, 0)
        self.assertRegex(r.stdout.strip().splitlines()[-1], r"^Utilisé : .+ sur .+\.$")

    def test_fenetre_refusee_si_le_reglage_est_coupe(self):
        appels = self.d / "appels-qs"
        qs = self.bin / "qs"                    # faux qs : jamais la vraie île
        qs.write_text('#!/bin/sh\necho "$*" >> "%s"\n' % appels)
        qs.chmod(0o755)
        r = self.nc("fenetre", code=5)
        self.assertIn("CLOUD_JARVIS oui", r.lignes[-1]["message"])
        self.assertFalse(appels.exists())
        reglages = self.home / ".config/nc/reglages.conf"
        reglages.parent.mkdir(parents=True, exist_ok=True)
        reglages.write_text("CLOUD_JARVIS=oui\n")
        self.nc("fenetre", code=0)
        self.assertEqual(appels.read_text(), "-c nc-ile ipc call ile cloud\n")

    def test_telecharger_sans_destination_va_dans_telechargements(self):
        eid, donnees = self.deposer_gros(1000)
        dl = self.home / "Mes téléchargements"
        dl.mkdir()
        (self.home / ".config").mkdir(exist_ok=True)
        (self.home / ".config/user-dirs.dirs").write_text('XDG_DESKTOP_DIR="$HOME/Bureau"\nXDG_DOWNLOAD_DIR="$HOME/Mes téléchargements"\n')
        self.nc("telecharger", eid, code=0)
        recus = [p for p in dl.iterdir() if not p.name.startswith(".")]
        self.assertEqual(len(recus), 1)
        self.assertEqual(recus[0].read_bytes(), donnees)
        self.nc("telecharger", eid, code=6)                     # déjà là : conflit, le panneau propose « Remplacer »
        self.nc("telecharger", eid, "--remplacer", code=0)

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
        self.assertEqual(len(self.creations()), 4)            # une seule relance, puis l'échec (le nom est libre)
        self.assertEqual(r.lignes[-1]["erreur"], "destination_changed")
        self.assertFalse(any(l.get("evenement") == "conflit" for l in r.lignes))

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

    def test_etat_donne_au_panneau_toutes_les_capacites_qu_il_lit(self):
        """Le panneau ne montre Renommer, Déplacer, Supprimer un dossier que si `nc-cloud etat` les lui transmet."""
        self.faux.gestion = self.faux.suppression = True
        self.associer()
        f = self.nc("etat", code=0).lignes[-1]["features"]
        for k in ("file_delete", "entry_move", "delete_preview", "directory_delete", "entry_by_id"):
            self.assertIs(f.get(k), True, k)
        lues = set(re.findall(r"features\.(\w+)", (REPO / "home/.config/quickshell/nc-ile/CloudEtat.qml").read_text()))
        self.assertTrue(lues and lues <= set(f), lues - set(f))

    def test_deposer_chemins_inattendus_proteges_et_caches(self):
        self.associer()
        bon = self.fichier("a.txt", b"abc")
        ssh = self.home / ".ssh"
        ssh.mkdir()
        (ssh / "id_test").write_bytes(b"cle")
        conf = self.home / ".config/nc/assistant.conf"            # la clé du serveur : jamais envoyée
        cache = self.home / ".notes/brouillon.txt"
        cache.parent.mkdir()
        cache.write_bytes(b"x")
        args = [str(bon) + "/", str(bon) + "/.", str(bon.parent) + "/../src/a.txt", str(bon.parent) + "//a.txt",
                str(ssh / "id_test"), str(conf), str(bon)]
        r = self.nc("deposer", "--", *args, code=1)
        etats = [(x.get("fichier"), x.get("etat")) for x in r.lignes if x.get("evenement") == "resultat"]
        self.assertEqual(etats[:6], [(a, "refuse") for a in args[:6]])
        self.assertEqual(etats[6], (str(bon), "publie"))            # le chemin donné, exact : le panneau s'y retrouve
        self.assertIn("fichier protégé", r.lignes[4]["message"])
        self.assertEqual([e["name"] for e in self.faux.entries.values() if e["kind"] == "file"], ["a.txt"])
        # examiner : taille, caché, refus ; rien ne part
        r = self.nc("examiner", "--", str(bon), str(cache), str(ssh / "id_test"), str(bon) + "/", code=0)
        ex = {x["fichier"]: x for x in r.lignes[-1]["fichiers"]}
        self.assertEqual((ex[str(bon)]["taille"], ex[str(bon)]["cache"], ex[str(bon)]["refus"]), (3, False, None))
        self.assertEqual((ex[str(cache)]["cache"], ex[str(cache)]["refus"]), (True, None))
        self.assertIn("protégé", ex[str(ssh / "id_test")]["refus"])
        self.assertIn("inattendu", ex[str(bon) + "/"]["refus"])

    @unittest.skipIf(os.geteuid() == 0, "root lit tout")
    def test_fichier_illisible_au_milieu_d_un_lot(self):
        self.associer()
        a, b, c = self.fichier("a.txt", b"a"), self.fichier("b.txt", b"b"), self.fichier("c.txt", b"c")
        b.chmod(0)
        try:
            r = self.nc("deposer", str(a), str(b), str(c), code=1)
        finally:
            b.chmod(0o600)                 # le tearDown relit chaque fichier
        etats = {x["fichier"]: x["etat"] for x in r.lignes if x.get("evenement") == "resultat"}
        self.assertEqual(etats, {str(a): "publie", str(b): "refuse", str(c): "publie"})

    # ── C3 : Fichiers (GVfs, faux module gi) ──
    def faux_gi(self, mode="ok"):
        g = self.d / "fauxgi" / "gi" / "repository"
        g.mkdir(parents=True, exist_ok=True)
        (g.parent / "__init__.py").write_text(FAUX_GI_INIT)
        (g / "__init__.py").write_text(FAUX_GI_REPO)
        self.journal_gi = self.d / "gi.journal"
        self.plus = {"PYTHONPATH": str(self.d / "fauxgi"), "FAUX_GI": mode, "FAUX_GI_JOURNAL": str(self.journal_gi)}

    def gi_vu(self):
        return [json.loads(l) for l in self.journal_gi.read_text().splitlines()] if self.journal_gi.exists() else []

    def favoris(self):
        return self.home / ".config/gtk-3.0/bookmarks"

    def test_fichiers_monte_par_l_adresse_verifiee_jeton_seulement_dans_la_mount_operation(self):
        self.associer()
        self.faux_gi()
        self.favoris().parent.mkdir(parents=True)
        self.favoris().write_text("file:///home/user/Documents Documents\nsftp://nas/partage")    # sans fin de ligne
        os.chmod(self.favoris(), 0o640)
        r = self.nc("fichiers", code=0)
        port = self.srv.server_address[1]
        adresse = f"dav://127.0.0.1:{port}/cloud/dav/"
        vu = self.gi_vu()
        self.assertEqual([x["uri"] for x in vu if x["evt"] == "monter"], [adresse])
        jeton = self.trousseau.read_text()
        app = json.loads((self.home / ".local/state/nc-cloud/appareil.json").read_text())
        rep = [x for x in vu if x["evt"] == "reponse"]
        self.assertEqual(rep, [{"evt": "reponse", "r": "repondu", "u": app["device_id"], "mdp": hashlib.sha256(jeton.encode()).hexdigest(),
                                "save": "jamais"}])
        self.assertIn({"evt": "ouvrir", "uris": [adresse]}, vu)
        self.assertIn({"evt": "appli", "type": "inode/directory"}, vu)
        self.assertEqual(self.favoris().read_text(),
                         f"file:///home/user/Documents Documents\nsftp://nas/partage\n{adresse} Cloud JARVIS\n")
        self.assertEqual(stat.S_IMODE(os.stat(self.favoris()).st_mode), 0o640)
        ev = r.lignes[-1]
        self.assertEqual((ev["evenement"], ev["adresse"], ev["ecriture"]), ("fichiers", adresse, False))
        self.assertIn("lecture seule", ev["message"])
        # Le jeton : ni dans l'adresse, ni dans une sortie, ni dans un fichier du HOME, ni dans les arguments de secret-tool
        self.assertNotIn(jeton, r.stdout + r.stderr + adresse + self.args_st.read_text())
        for f in self.home.rglob("*"):
            if f.is_file() and not f.is_symlink():
                self.assertNotIn(jeton.encode(), f.read_bytes(), f)
        self.nc("fichiers", code=0)                                 # une seconde fois : jamais deux favoris
        self.assertEqual(self.favoris().read_text().count("Cloud JARVIS"), 1)
        # demonter : notre ligne seulement
        self.faux_gi("deja")
        self.nc("demonter", code=0)
        self.assertEqual(self.favoris().read_text(), "file:///home/user/Documents Documents\nsftp://nas/partage\n")
        self.assertIn({"evt": "demonter", "uri": adresse}, self.gi_vu())

    def test_fichiers_http_par_le_nom_local_monte_sur_l_ip(self):
        self.url("http://localhost:%d" % self.srv.server_address[1])
        self.associer()
        self.faux_gi()
        self.nc("fichiers", code=0)
        uri = [x["uri"] for x in self.gi_vu() if x["evt"] == "monter"][0]
        self.assertEqual(uri, "dav://127.0.0.1:%d/cloud/dav/" % self.srv.server_address[1])
        self.assertNotIn("localhost", uri)

    def test_fichiers_http_public_refuse_rien_n_est_monte(self):
        self.associer()
        self.faux_gi()
        self.url("http://8.8.8.8:9")
        self.nc("fichiers", code=9)
        self.assertEqual(self.gi_vu(), [])

    def test_fichiers_question_de_gvfs_et_jeton_refuse(self):
        self.associer()
        self.favoris().parent.mkdir(parents=True)
        for mode, code, reponses in (("question", 9, ["refuse"]), ("mdp_refuse", 1, ["repondu", "refuse"]), ("erreur", 1, ["repondu"]),
                                     ("domaine", 15, ["refuse"]), ("msg_proxy", 15, ["refuse"]), ("sans_mdp", 15, ["refuse"]),
                                     ("refus_puis_mdp", 15, ["refuse", "refuse"]), ("mdp_puis_question", 9, ["repondu", "refuse"])):
            with self.subTest(mode):
                self.faux_gi(mode)
                if self.journal_gi.exists():
                    self.journal_gi.unlink()
                r = self.nc("fichiers", code=code)
                vus = [x for x in self.gi_vu() if x["evt"] == "reponse"]
                self.assertEqual([x["r"] for x in vus], reponses)
                # Tout refus : l'opération est vidée AVANT la réponse (le jeton n'y reste pas)
                self.assertTrue(all(x["mdp"] is None and not x["u"] for x in vus if x["r"] == "refuse"), vus)
                if mode in ("mdp_refuse", "erreur", "mdp_puis_question"):           # le jeton est parti : message honnête, plus « refuse le jeton »
                    self.assertIn("après l'envoi du jeton", r.lignes[-1]["message"])
                    self.assertIn("dissocie puis associe", r.lignes[-1]["message"])
                self.assertFalse(self.favoris().exists(), "aucun favori sans montage")
                self.assertNotIn("\x1b", r.stdout)
                self.assertNotIn("\\u001b", r.stdout)

    def test_fichiers_proxy_annonce_refus_avant_tout_montage(self):
        self.associer()
        for mode in ("proxy", "proxy_erreur"):
            with self.subTest(mode):
                self.faux_gi(mode)
                if self.journal_gi.exists():
                    self.journal_gi.unlink()
                r = self.nc("fichiers", code=14)
                self.assertIn("proxy", r.lignes[-1]["message"])
                vus = self.gi_vu()
                self.assertEqual([x["uri"] for x in vus if x["evt"] == "proxy"], [vus[0]["uri"]])
                self.assertRegex(vus[0]["uri"], r"^http://127\.0\.0\.1:\d+/cloud/dav/$")
                self.assertFalse([x for x in vus if x["evt"] in ("monter", "reponse")], vus)

    def test_fichiers_delai_joue_sans_rappel_de_gvfs(self):
        self.associer()
        self.faux_gi("jamais")
        r = self.nc("fichiers", code=3)
        vus = self.gi_vu()
        self.assertEqual([x["n"] for x in vus if x["evt"] == "delai"], [120, 15])   # le délai, puis la seconde échéance
        self.assertTrue([x for x in vus if x["evt"] == "annule"])
        self.assertIn("après l'envoi du jeton", r.lignes[-1]["message"])

    def test_deja_monte_seulement_a_notre_racine_et_question_puis_monte(self):
        self.associer()
        self.faux_gi("deja_autre")                    # l'utilisateur a monté la racine du même hôte : ni repris ni démonté
        r = self.nc("fichiers", code=6)
        self.assertIn("Un autre montage", r.lignes[-1]["message"])
        self.nc("demonter", code=0)
        self.assertFalse([x for x in self.gi_vu() if x["evt"] == "demonter"])
        self.faux_gi("question_monte")                 # question refusée, mais GVfs a monté : retiré, puis dit
        r = self.nc("fichiers", code=9)
        self.assertTrue([x for x in self.gi_vu() if x["evt"] == "demonter"])
        self.assertFalse(Path(str(self.journal_gi) + ".monte").exists())

    def test_note_de_montage_illisible_dissocier_va_jusqu_au_bout(self):
        self.associer()
        self.faux_gi()
        self.nc("fichiers", code=0)
        note = self.home / ".local/state/nc-cloud/montage.json"
        for contenu in ("{", "[1, 2]", "\xff"):
            with self.subTest(contenu=contenu):
                note.write_text(contenu)
                self.nc("demonter", code=0)
                self.assertFalse(note.exists())
        note.write_text("{")
        self.nc("dissocier", code=0)
        self.assertFalse((self.home / ".local/state/nc-cloud/appareil.json").exists())
        self.assertFalse(note.exists())

    def test_demonter_par_l_adresse_notee_au_montage(self):
        self.associer()
        self.faux_gi()
        r = self.nc("fichiers", code=0)
        adresse = r.lignes[-1]["adresse"]
        note = self.home / ".local/state/nc-cloud/montage.json"
        self.assertEqual(json.loads(note.read_text()), {"adresse": adresse})
        note.write_text(json.dumps({"adresse": adresse.replace("127.0.0.1", "127.0.0.2")}))   # ce qui a été monté, pas la sonde
        self.faux_gi("deja")
        r = self.nc("demonter", code=0)
        self.assertEqual([x["uri"] for x in self.gi_vu() if x["evt"] == "demonter"], [adresse.replace("127.0.0.1", "127.0.0.2")])
        self.assertFalse(note.exists())
        self.assertIn("aucun favori à retirer", r.lignes[-1]["message"])
        # Sans note, en http : rien n'est démonté (la sonde pourrait viser une autre adresse)
        r = self.nc("demonter", code=0)
        self.assertEqual(len([x for x in self.gi_vu() if x["evt"] == "demonter"]), 1)

    def test_fichiers_sans_gi_ou_sans_webdav_code_distinct_et_paquet_dit(self):
        self.associer()
        # Le message exact de chaque distribution (la ponctuation qui suit prouve qu'aucun autre nom n'est ajouté)
        attendus = {'ID=arch': ("python-gobject glib2.", "gvfs-dnssd,"),
                    'ID=debian': ("python3-gi gir1.2-glib-2.0.", "gvfs-backends,"),
                    'ID="fedora"': ("python3-gobject-base glib2.", "gvfs,"),
                    'ID="opensuse-tumbleweed"\nID_LIKE="opensuse suse"': ("python3-gobject typelib-1_0-Gio-2_0.", "gvfs-backends,")}
        for osr, (gi, dav) in attendus.items():
            for mode, mot, paquet in (("absent", "gi", gi), ("sans_gio", "gi", gi), ("sans_dav", "WebDAV", dav)):
                with self.subTest(osr=osr, mode=mode):
                    (self.d / "os-release").write_text(osr + "\n")
                    self.faux_gi(mode)
                    m = self.nc("fichiers", code=13).lignes[-1]["message"]
                    self.assertIn(mot, m)
                    self.assertIn("installe " + paquet, m)
                    self.assertFalse([x for x in self.gi_vu() if x["evt"] == "monter"])
                    self.assertIs(self.nc("etat", code=0).lignes[-1]["fichiers"], False)
        # Distribution inconnue : les quatre sont nommées
        (self.d / "os-release").write_text('ID="inconnue"\n')
        self.faux_gi("sans_dav")
        m = self.nc("fichiers", code=13).lignes[-1]["message"]
        for nom in ("Arch : gvfs-dnssd", "Debian : gvfs-backends", "Fedora : gvfs", "openSUSE : gvfs-backends"):
            self.assertIn(nom, m)
        self.faux_gi()
        self.assertIs(self.nc("etat", code=0).lignes[-1]["fichiers"], True)       # ce que lit CloudEtat.qml (d.fichiers)
        self.assertIn("fichiersPossible = d.fichiers === true", (REPO / "home/.config/quickshell/nc-ile/CloudEtat.qml").read_text())

    def test_favori_lien_refuse_dossier_absent_rien_cree_et_dissocier_le_retire(self):
        self.associer()
        self.faux_gi()
        self.nc("fichiers", code=0)
        self.assertFalse(self.favoris().exists(), "dossier gtk-3.0 absent : rien n'est créé")
        self.favoris().parent.mkdir(parents=True)
        cible = self.d / "ailleurs"
        cible.write_text("x\n")
        self.favoris().symlink_to(cible)
        r = self.nc("fichiers", code=0)                    # monté et ouvert : seul le favori manque, et c'est dit
        self.assertEqual(cible.read_text(), "x\n")
        self.assertIn("Favori non posé", r.lignes[-1]["message"])
        self.assertIs(r.lignes[-1]["favori"], False)
        self.favoris().unlink()
        self.nc("fichiers", code=0)
        self.assertIn("Cloud JARVIS", self.favoris().read_text())
        self.faux_gi("deja")
        self.nc("dissocier", code=0)
        self.assertEqual(self.favoris().read_text(), "")
        self.assertTrue([x for x in self.gi_vu() if x["evt"] == "demonter"])

    def test_note_par_l_entree_standard_dossier_notes_et_nom_pris(self):
        self.associer()
        texte = "Idée : acheter du café, éteindre le four !\nDeuxième ligne — été.\n"
        r = self.nc_entree(texte.encode(), "note", code=0)
        notes = [e for e in self.faux.entries.values() if e["kind"] == "directory" and e["name"] == "Notes"]
        self.assertEqual(len(notes), 1)
        self.assertEqual(notes[0]["parent"], "root")
        fichiers = [e for e in self.faux.entries.values() if e["kind"] == "file"]
        self.assertEqual(len(fichiers), 1)
        nom = fichiers[0]["name"]
        self.assertRegex(nom, r"^Idée acheter du café éteindre le four \d{4}-\d{2}-\d{2} \d{2}h\d{2}\.txt$")
        self.assertEqual(fichiers[0]["parent"], notes[0]["id"])
        self.assertEqual(self.faux.contenus[fichiers[0]["id"]], texte.encode())
        self.assertEqual(r.lignes[-1]["evenement"], "note")
        self.assertEqual(list((self.home / ".local/state/nc-cloud/notes").rglob("*")), [])       # rien ne reste en local
        # Même texte, même minute : le dossier Notes est réutilisé, le nom prend un suffixe, rien n'est écrasé
        self.nc_entree(texte.encode(), "note", code=0)
        self.assertEqual(len([e for e in self.faux.entries.values() if e["kind"] == "directory" and e["name"] == "Notes"]), 1)
        noms = sorted(e["name"] for e in self.faux.entries.values() if e["kind"] == "file")
        self.assertEqual(len(noms), 2)
        self.assertTrue(any(n.endswith(" (2).txt") for n in noms), noms)

    def test_note_hors_ligne_reste_en_local_puis_disparait_apres_reprise(self):
        self.associer()
        self.faux.pannes.add("couper_apres:0")
        self.nc_entree("Hors ligne".encode(), "note", code=3)
        locales = [f for f in (self.home / ".local/state/nc-cloud/notes").rglob("*") if f.is_file()]
        self.assertEqual(len(locales), 1)
        self.assertEqual(stat.S_IMODE(locales[0].stat().st_mode), 0o600)
        self.assertEqual(locales[0].read_bytes(), b"Hors ligne")
        self.nc("reprendre", "1", code=0)
        self.assertEqual(list((self.home / ".local/state/nc-cloud/notes").rglob("*")), [])
        self.assertEqual([self.faux.contenus[e["id"]] for e in self.faux.entries.values() if e["kind"] == "file"], [b"Hors ligne"])

    def test_note_trop_longue_vide_ou_illisible_rien_ne_part(self):
        self.associer()
        for entree, mot in ((b"a" * (100 * 1024), "trop longue"), (b"  \n ", "vide"), (b"\xff\xfe", "UTF-8")):
            with self.subTest(mot):
                r = self.nc_entree(entree, "note", code=2)
                self.assertIn(mot, r.lignes[-1]["message"])
        self.assertFalse([e for e in self.faux.entries.values() if e["kind"] != "directory" or e["name"] == "Notes"])

    def test_noms_a_tiret_apres_double_tiret(self):
        """« -x » et « --json » tapés comme noms, placés après « -- », restent des noms (le panneau passe ainsi)."""
        self.associer()
        self.nc("dossier", "--", "root", "-x", code=0)
        self.nc("creer", "--", "root", "--json", code=0)
        r = self.nc("lister", "--", "root", code=0)
        self.assertEqual(sorted(e["name"] for e in r.lignes[-1]["entries"]), ["--json", "-x"])

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
        self.nc("telecharger", eid, str(dest), code=6)          # existe déjà : conflit, rien n'est écrasé seul
        self.faux.pannes.add("contenu_faux")
        self.nc("telecharger", eid, str(dest), "--remplacer", code=12)
        self.assertEqual(dest.read_bytes(), donnees)             # rien n'est remplacé
        self.assertEqual([x.name for x in self.d.glob(".nc-cloud-*")], [])

    def test_deux_telechargements_vers_la_meme_destination(self):
        eid, _ = self.deposer_gros()
        partiel = self.d / partiel_de("g.bin")
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
        os.link(autre, self.d / partiel_de("g.bin"))
        self.nc("telecharger", eid, str(self.d / "g.bin"), code=1)
        self.assertEqual(autre.read_bytes(), b"un autre fichier")
        self.assertFalse((self.d / "g.bin").exists())
        cible = self.d / "cible.txt"
        cible.write_bytes(b"intact")
        os.symlink(cible, self.d / partiel_de("h.bin"))
        self.nc("telecharger", eid, str(self.d / "h.bin"), code=1)
        self.assertEqual(cible.read_bytes(), b"intact")

    def test_nom_de_240_octets_se_telecharge(self):
        self.associer()
        nom = "é" * 118 + ".txt"                                       # 240 octets
        r = self.nc("deposer", str(self.fichier(nom, b"long")), code=0)
        eid = r.lignes[-1]["entree"]["id"]
        dest = self.d / "dl"
        dest.mkdir()
        self.nc("telecharger", eid, str(dest), code=0)
        self.assertEqual((dest / nom).read_bytes(), b"long")

    def test_telecharger_par_id_si_annonce(self):
        self.faux.par_id = True
        eid, donnees = self.deposer_gros(1000)
        self.nc("dossier", "root", "sous", code=0)                     # l'entrée n'est pas cherchée dans les pages
        self.nc("telecharger", eid, str(self.d / "x.bin"), code=0)
        self.assertEqual((self.d / "x.bin").read_bytes(), donnees)
        self.assertTrue(any(c[1].endswith("/entries/" + eid) for c in self.faux.journal))
        self.nc("telecharger", "f999", str(self.d / "y.bin"), code=1)

    def test_entree_par_id_d_un_autre_id_refusee(self):
        self.faux.par_id = True
        eid, _ = self.deposer_gros(100)
        self.faux.pannes.add("autre_entree")
        r = self.nc("telecharger", eid, str(self.d / "x.bin"), code=1)
        self.assertIn("Réponse du serveur invalide", r.stdout)
        self.assertFalse((self.d / "x.bin").exists())

    def test_reprendre_dossier_change_annulation_hors_ligne(self):
        self.faux.revisions_vivantes = True
        self.associer()
        self.faux.pannes.add("couper_apres:0")
        p = self.fichier("gros.bin", os.urandom(MORCEAU * 3))
        self.nc("deposer", str(p), code=3)
        self.nc("dossier", "root", "autre", code=0)
        self.faux.pannes.add("couper_annulation")
        self.nc("reprendre", "1", code=3)
        self.assertEqual(len(self.manifestes()), 1)                     # rien n'est effacé : on pourra reprendre
        self.assertEqual(len(self.faux.uploads), 1)
        self.faux.pannes.discard("couper_annulation")
        self.nc("reprendre", "1", code=0)
        self.assertEqual([u["state"] for u in self.faux.uploads.values()], ["cancelled", "committed"])

    def test_conflit_des_la_creation(self):
        self.faux.conflit_tot = True
        self.associer()
        p = self.fichier("a.txt", b"v1")
        self.nc("deposer", str(p), code=0)
        self.faux.pannes.add("cacher_noms")                             # la vérification locale ne voit rien
        r = self.nc("deposer", str(p), code=6)
        self.assertTrue(any(l.get("evenement") == "conflit" and l["actuel"] for l in r.lignes))
        self.assertEqual(self.morceaux_recus(), [0])                    # seul le premier envoi a eu un morceau
        self.assertFalse(self.manifestes())

    def test_limiteur_du_gateway(self):
        self.associer()
        self.faux.pannes.add("limiteur")
        r = self.nc("etat", code=3)
        self.assertIn("réessaie dans un instant", r.stdout)

    def test_destination_changee_deux_fois_sans_proposer_si_existe(self):
        self.faux.revisions_vivantes = True
        self.associer()
        self.faux.pannes.add("publier_ailleurs_toujours")
        r = self.nc("deposer", str(self.fichier("a.txt", b"abc")), code=6)
        self.assertNotIn("--si-existe", r.stdout)
        self.assertIn("Le dossier a changé pendant l'envoi", r.stdout)

    def test_reprendre_quand_le_dossier_a_change(self):
        self.faux.revisions_vivantes = True
        self.associer()
        self.faux.pannes.add("couper_apres:0")
        donnees = os.urandom(MORCEAU * 3)
        p = self.fichier("gros.bin", donnees)
        self.nc("deposer", str(p), code=3)
        self.nc("dossier", "root", "autre", code=0)                     # la révision de la racine change
        r = self.nc("reprendre", "1", code=0)
        self.assertIn("nouvel envoi", r.stdout)
        self.assertEqual(r.lignes[-1]["etat"], "publie")
        etats = [u["state"] for u in self.faux.uploads.values()]
        self.assertEqual(etats, ["cancelled", "committed"])
        eid = next(e["id"] for e in self.faux.entries.values() if e["name"] == "gros.bin")
        self.assertEqual(self.faux.contenus[eid], donnees)

    # ── Suppression ──

    def test_supprimer(self):
        self.faux.suppression = True
        eid, _ = self.deposer_gros(10)
        rev = self.faux.entries[eid]["revision"]
        self.nc("supprimer", eid, code=2)                           # --revision obligatoire
        self.nc("supprimer", eid, "--revision", "*", code=2)
        self.nc("supprimer", eid, "--revision", "révision", code=2)    # hors ASCII : refusée avant tout manifeste
        self.assertFalse(self.manifestes("suppressions"))
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


    # ── C1d : entree, deplacer, renommer, apercu, supprimer un dossier, creer, ouvrir (révision b8313b1) ──

    def arbre_de_test(self):
        self.faux.gestion = self.faux.revisions_vivantes = True
        self.associer()
        a = self.nc("dossier", "root", "A", code=0).lignes[-1]["entree"]["id"]
        b = self.nc("dossier", a, "B", code=0).lignes[-1]["entree"]["id"]
        r = self.nc("deposer", "--dans", b, str(self.fichier("note.txt", b"bonjour")), code=0)
        return a, b, r.lignes[-1]["entree"]["id"]

    def rev(self, eid):
        return self.faux.entries[eid]["revision"]

    def mutations(self):
        return [c for c in self.faux.journal if c[0] in ("POST", "DELETE") and "/entries/" in c[1]]

    def test_entree_deplacer_renommer(self):
        a, b, f = self.arbre_de_test()
        self.nc("renommer", f, "--revision", self.rev(f), "dans-B.txt", code=0)     # parent_id toujours envoyé : reste dans B
        self.assertEqual((self.faux.entries[f]["parent"], self.faux.entries[f]["name"]), (b, "dans-B.txt"))
        vide = self.nc("dossier", "root", "Vide", code=0).lignes[-1]["entree"]["id"]
        self.nc("supprimer", vide, "--revision", self.rev(vide), code=0)            # corps JSON toujours envoyé
        self.assertNotIn(vide, self.faux.entries)
        r = self.nc("entree", f, code=0)
        self.assertEqual((r.lignes[-1]["entree"]["id"], r.lignes[-1]["entree"]["revision"]), (f, self.rev(f)))
        racine_avant, rev = self.rev("root"), self.rev(f)
        r = self.nc("deplacer", f, "--revision", rev, "--vers", "root", code=0)
        self.assertEqual((r.lignes[-1]["etat"], r.lignes[-1]["entree"]["id"]), ("deplace", f))
        self.assertEqual((self.faux.entries[f]["parent"], self.faux.entries[f]["name"]), ("root", "dans-B.txt"))
        self.assertNotEqual(self.rev("root"), racine_avant)               # l'appelant relit les parents
        self.assertEqual(self.mutations()[-1][2]["If-Match"], f'"{rev}"')          # la révision de l'appelant, exacte
        r = self.nc("renommer", f, "--revision", self.rev(f), "Note finale.txt", code=0)
        self.assertEqual((self.faux.entries[f]["parent"], self.faux.entries[f]["name"]), ("root", "Note finale.txt"))
        self.assertFalse(self.manifestes("operations"))

    def test_revision_perimee_cycle_nom_occupe_racine(self):
        a, b, f = self.arbre_de_test()
        self.nc("deplacer", f, "--revision", "ancienne", "--vers", "root", code=6)      # 412 : rien n'est fait
        self.assertEqual(self.faux.entries[f]["parent"], b)
        r = self.nc("deplacer", a, "--revision", self.rev(a), "--vers", b, code=6)    # cycle
        self.assertIn("sous-dossiers", r.stdout)
        self.nc("deplacer", a, "--revision", self.rev(a), "--vers", a, code=2)        # refus local, rien ne part
        self.nc("deplacer", "root", "--revision", self.rev("root"), "--vers", a, code=2)
        self.nc("creer", "root", "note.txt", code=0)
        r = self.nc("deplacer", f, "--revision", self.rev(f), "--vers", "root", code=6)   # nom occupé : jamais d'écrasement
        self.assertIn("existe déjà", r.stdout)
        self.assertEqual(self.faux.entries[f]["parent"], b)
        self.nc("renommer", f, "--revision", self.rev(f), "a/b", code=2)
        self.assertFalse(self.manifestes("operations"))

    def test_reponse_perdue_puis_rejeu_meme_cle(self):
        a, b, f = self.arbre_de_test()
        rev = self.rev(f)
        self.faux.pannes.add("perdre_gestion")
        self.nc("deplacer", f, "--revision", rev, "--vers", "root", code=3)
        self.assertEqual(len(self.manifestes("operations")), 1)                     # noté AVANT l'envoi, gardé
        self.assertEqual(self.faux.entries[f]["parent"], "root")                    # fait sur le serveur
        r = self.nc("deplacer", f, "--revision", rev, "--vers", "root", code=0)     # même demande : le reçu
        self.assertEqual(r.lignes[-1]["etat"], "deplace")
        cles = [c[2]["Idempotency-Key"] for c in self.mutations()]
        corps = [c for c in self.faux.journal if c[0] == "POST" and c[1].endswith("/move")]
        self.assertEqual((len(cles), len(set(cles))), (2, 1))
        self.assertEqual(len(corps), 2)
        self.assertFalse(self.manifestes("operations"))

    def test_apercu_et_suppression_de_dossier(self):
        a, b, f = self.arbre_de_test()
        r = self.nc("supprimer", a, "--revision", self.rev(a), code=6)             # non vide sans --recursif
        self.assertIn("non vide", r.stdout)
        self.nc("supprimer", a, "--revision", self.rev(a), "--recursif", code=2)   # --recursif sans --arbre : local
        self.nc("supprimer", a, "--revision", self.rev(a), "--recursif", "--arbre", "pas-hex", code=2)
        ap = self.nc("apercu", a, code=0).lignes[-1]
        self.assertEqual((ap["files"], ap["directories"], ap["size"]), (1, 2, 7))
        self.nc("creer", b, "nouveau.txt", code=0)                                 # le dossier change après l'aperçu
        r = self.nc("supprimer", a, "--revision", self.rev(a), "--recursif", "--arbre", ap["tree_revision"], code=6)
        self.assertIn("refais l'aperçu", r.stdout.lower())
        self.assertIn(a, self.faux.entries)
        ap = self.nc("apercu", a, code=0).lignes[-1]
        r = self.nc("supprimer", a, "--revision", self.rev(a), "--recursif", "--arbre", ap["tree_revision"], code=0)
        self.assertEqual((r.lignes[-1]["etat"], r.lignes[-1]["count"]), ("supprime", 4))
        self.assertNotIn(a, self.faux.entries)
        self.assertNotIn(f, self.faux.entries)
        self.assertFalse(self.manifestes("suppressions"))

    def test_sans_les_capacites_rien_ne_part(self):
        self.faux.suppression = True
        eid, _ = self.deposer_gros(10)
        self.nc("dossier", "root", "D", code=0)
        r = self.nc("deplacer", eid, "--revision", self.rev(eid), "--vers", "root", code=1)
        self.assertIn("ne sait pas déplacer", r.stdout)
        self.nc("renommer", eid, "--revision", self.rev(eid), "x", code=1)
        self.nc("apercu", eid, code=1)
        did = next(e["id"] for e in self.faux.entries.values() if e["name"] == "D")
        self.nc("supprimer", did, "--revision", self.rev(did), "--recursif", "--arbre", "a" * 64, code=1)
        self.assertEqual(self.mutations(), [])
        self.assertFalse([c for c in self.faux.journal if "/move" in c[1] or "delete-preview" in c[1]])

    def test_creer_un_fichier_vide(self):
        a, b, f = self.arbre_de_test()
        avant = len(self.morceaux_recus())
        r = self.nc("creer", a, "vide.txt", code=0)
        e = r.lignes[-1]["entree"]
        self.assertEqual((e["name"], e["size"], self.faux.entries[e["id"]]["sha256"]), ("vide.txt", 0, hashlib.sha256(b"").hexdigest()))
        self.assertEqual(len(self.morceaux_recus()), avant)                       # aucun morceau
        self.nc("creer", a, "vide.txt", code=6)                                   # nom pris : conflit
        self.nc("creer", a, "../x", code=2)
        self.assertEqual(list((self.home / ".local/state/nc-cloud/vides").iterdir()), [])

    def ouvreur(self, file=True):
        """Un faux xdg-open qui note ses appels ; et un faux `file` (la CI n'installe pas le vrai partout) qui lit le
        type au contenu comme lui sur ces cas : PNG, PDF, ZIP / JAR, HTML, SVG, script, texte."""
        if file:
            ff = self.bin / "file"
            ecrire_outil(ff, "#!" + sys.executable + """
import sys
b = open(sys.argv[-1], 'rb').read()
t = b.lstrip()[:200].lower()
if b.startswith(b'\\x89PNG\\r\\n\\x1a\\n'): m = 'image/png'
elif b.startswith(b'%PDF-'): m = 'application/pdf'
elif b.startswith(b'FXM-TEST'): m = 'video/x-javafx'
elif b.startswith(b'MPEG-TEST'): m = 'video/mpeg'
elif b.startswith(b'\\x30\\x26\\xb2\\x75\\x8e\\x66\\xcf\\x11'): m = 'video/x-ms-asf'
elif b.startswith(b'PK'): m = 'application/java-archive' if b'META-INF/MANIFEST.MF' in b else 'application/zip'
elif t.startswith((b'<!doctype html', b'<html')): m = 'text/html'
elif b'<svg' in t: m = 'image/svg+xml'
elif b.startswith(b'#!'): m = 'text/x-shellscript'
else:
    try: b.decode('utf-8'); m = 'text/plain'
    except UnicodeDecodeError: m = 'application/octet-stream'
print(m)
""")
        appels = self.d / "appels-xdg"
        ecrire_outil(self.bin / "xdg-open", f'#!/bin/sh\necho "$@" >> "{appels}"\n')
        return appels

    def attendre(self, chemin):
        for _ in range(50):
            if chemin.exists():
                return chemin.read_text()
            time.sleep(0.1)
        return ""

    def test_ouvrir_copie_privee_puis_xdg_open(self):
        appels = self.ouvreur()
        a, b, f = self.arbre_de_test()
        r = self.nc("ouvrir", f, code=0)
        copie = Path(r.lignes[-1]["fichier"])
        self.assertEqual(copie.read_bytes(), b"bonjour")
        self.assertEqual(stat.S_IMODE(copie.stat().st_mode), 0o400)
        self.assertEqual(stat.S_IMODE(copie.parent.stat().st_mode), 0o700)
        self.assertTrue(str(copie).startswith(str(self.home / ".cache/nc-cloud/ouverts")))
        self.assertEqual(self.attendre(appels).strip(), str(copie))
        # une copie de plus de 24 h est retirée au prochain ouvrir
        vieux = time.time() - 25 * 3600
        os.utime(copie, (vieux, vieux))
        autre = self.nc("deposer", "--dans", a, str(self.fichier("image.png", PNG)), code=0).lignes[-1]["entree"]["id"]
        self.nc("ouvrir", autre, code=0)
        self.assertFalse(copie.exists())

    def test_ouvrir_empreinte_fausse_ou_nom_hostile(self):
        appels = self.ouvreur()
        a, b, f = self.arbre_de_test()
        self.faux.pannes.add("contenu_faux")
        self.nc("ouvrir", f, code=12)
        self.faux.pannes.discard("contenu_faux")
        for nom, contenu in (("lanceur.desktop", b"[Desktop Entry]\nExec=x"), ("photo.jpg", b"#!/bin/sh\nrm -rf ~")):
            eid = self.nc("deposer", "--dans", a, str(self.fichier(nom, contenu)), code=0).lignes[-1]["entree"]["id"]
            r = self.nc("ouvrir", eid, code=1)
            self.assertIn("télécharge-le d'abord", r.stdout)
        eid = self.nc("deposer", "--dans", a, str(self.fichier("x.txt", b"ok")), code=0).lignes[-1]["entree"]["id"]
        self.faux.entries[eid]["name"] = "../../" + RLO + ".note.txt"
        r = self.nc("ouvrir", eid, code=0)
        copie = Path(r.lignes[-1]["fichier"])
        self.assertTrue(copie.parent.parent == self.home / ".cache/nc-cloud/ouverts" and not copie.name.startswith("."), copie)
        self.assertNotIn(RLO, copie.name)
        time.sleep(0.5)
        self.assertEqual(self.attendre(appels).count("\n"), 1)                  # seule la copie saine est ouverte
        restes = [p for p in (self.home / ".cache/nc-cloud/ouverts").rglob("*") if p.is_file() and p.name.startswith(".ouvert-")]
        self.assertEqual(restes, [])

    # ── Retouches de C1d ──

    def depot(self, nom, contenu, parent="root"):
        p = self.fichier("src-" + hashlib.sha256(nom.encode() + contenu).hexdigest()[:12], contenu)
        eid = self.nc("deposer", "--dans", parent, str(p), code=0).lignes[-1]["entree"]["id"]
        self.faux.entries[eid]["name"] = nom
        return eid

    def contenus_ouvrir(self, vrai=False):
        cas = [("vacances.png", jar(True), False), ("vacances.png", jar(False), False), ("vacances.png", HTML, False),
                ("page.html", HTML, False), ("dessin.svg", SVG, False), ("photo.jpg", b"bonjour\n", False),
                ("photo.png", b"#!/bin/sh\nid\n", False), ("script.sh", b"echo\n", False), ("x.jar", jar(True), False),
                ("lanceur", b"[Desktop Entry]\nExec=id\n", False), ("notes", b"bonjour\n", False),
                ("data:,x.html", b"bonjour\n", False), ("ab:x.txt#.html", b"bonjour\n", False), ("ab:x.png?.desktop", PNG, False),
                ("http:x.png;.jar", PNG, False), ("ab:x.html#.txt", b"bonjour\n", False), ("liste.m3u", b"#EXTM3U\nhttp://exemple.invalid/a.mp3\n", False),
                ("x.txt.gz", b"bonjour\n", False), ("photo.PNG", PNG, True), ("film.wmv", ASF, True),
                ("scene.fxm", b"FXM-TEST\n", False),     # famille vidéo par le nom et le contenu, mais hors de la table : refusé
                ("é" * 126 + ".md", b"bonjour\n", True)]
        if not vrai:     # le faux file seulement : .mpg (4) devient .mpeg (5), le radical est raccourci sous 255 octets
            cas.append(("é" * 125 + "a.mpg", b"MPEG-TEST\n", True))
        return cas + [
                ("image.png", PNG, True), ("doc.pdf", PDF, True), ("note.txt", b"bonjour\n", True), ("liste.csv", b"a,b\n1,2\n", True)]

    def verifier_liste_blanche(self, appels, vrai=False):
        self.faux.gestion = True
        self.associer()
        for nom, contenu, ouvert in self.contenus_ouvrir(vrai):
            with self.subTest(nom=nom, debut=contenu[:12]):
                eid = self.depot(nom, contenu)
                r = self.nc("ouvrir", eid, code=0 if ouvert else 1)
                if not ouvert:
                    self.assertIn("télécharge-le d'abord", r.stdout)
        time.sleep(0.5)
        vus = sorted(Path(x).name for x in self.attendre(appels).split())
        # La copie porte NOTRE extension, tirée du contenu : photo.PNG devient photo.png ; un CSV que file lit comme texte
        # simple devient liste.txt
        self.assertEqual(len(vus), sum(1 for _, _, o in self.contenus_ouvrir(vrai) if o), vus)
        self.assertIn("photo.png", vus)
        self.assertIn("film.wmv", vus, "un vrai .wmv (video/x-ms-asf) ne devient pas .asx")
        self.assertIn("é" * 126 + ".md", vus)
        if not vrai:
            long = next(v for v in vus if v.endswith(".mpeg"))
            self.assertLessEqual(len(long.encode()), 255, long)
        self.assertTrue({"image.png", "doc.pdf", "note.txt", "liste.csv"} <= set(vus), vus)     # liste.csv : text/plain ou text/csv
        restes = [p.name for p in (self.home / ".cache/nc-cloud/ouverts").rglob("*") if p.is_file()]
        self.assertEqual(sorted(restes), vus, "aucune copie refusée ne reste")

    def test_ouvrir_liste_blanche_contenu_et_nom(self):
        self.verifier_liste_blanche(self.ouvreur())

    @unittest.skipUnless(shutil.which("file"), "file absent ici (la CI ne l'installe pas partout)")
    def test_ouvrir_liste_blanche_avec_le_vrai_file(self):
        appels = self.ouvreur(file=False)
        (self.bin / "file").symlink_to(shutil.which("file"))
        self.verifier_liste_blanche(appels, vrai=True)

    def test_ouvrir_sans_file_trop_gros_ou_nom_trop_long(self):
        appels = self.ouvreur(file=False)
        self.faux.gestion = True
        self.associer()
        eid = self.depot("image.png", PNG)
        r = self.nc("ouvrir", eid, code=1)                                    # file absent : refus
        self.assertIn("télécharge-le d'abord", r.stdout)
        self.ouvreur()
        self.faux.entries[eid]["size"] = 200 * 1024 * 1024 + 1
        avant = len(self.faux.journal)
        r = self.nc("ouvrir", eid, code=1)
        self.assertIn("200 Mio", r.stdout)
        self.assertFalse([c for c in self.faux.journal[avant:] if c[1].endswith("/content")], "rien n'est téléchargé")
        eid = self.depot("é" * 200 + ".txt", b"ok")
        r = self.nc("ouvrir", eid, code=1)
        self.assertIn("255 octets", r.stdout)
        time.sleep(0.3)
        self.assertEqual(self.attendre(appels), "")

    def test_ouvrir_disque_plein_code_7(self):
        self.ouvreur()
        self.faux.gestion = True
        self.associer()
        eid = self.depot("gros.txt", b"x" * 300000)

        def limite():
            import resource
            signal.signal(signal.SIGXFSZ, signal.SIG_IGN)
            resource.setrlimit(resource.RLIMIT_FSIZE, (100000, 100000))
        r = subprocess.run([sys.executable, str(NC_CLOUD), "--json", "ouvrir", eid], capture_output=True, text=True, timeout=60,
                           env=self.env(), stdin=subprocess.DEVNULL, preexec_fn=limite)
        self.assertEqual(r.returncode, 7, r.stdout + r.stderr)
        self.assertNotIn("interrompu", r.stdout.lower())

    def test_telecharger_disque_plein_code_7(self):
        self.faux.gestion = True
        self.associer()
        eid = self.depot("gros.txt", b"x" * 300000)
        dest = self.d / "dest"
        dest.mkdir()

        def limite():
            import resource
            signal.signal(signal.SIGXFSZ, signal.SIG_IGN)
            resource.setrlimit(resource.RLIMIT_FSIZE, (100000, 100000))
        r = subprocess.run([sys.executable, str(NC_CLOUD), "--json", "telecharger", eid, str(dest)], capture_output=True, text=True,
                           timeout=60, env=self.env(), stdin=subprocess.DEVNULL, preexec_fn=limite)
        self.assertEqual(r.returncode, 7, r.stdout + r.stderr)
        self.assertNotIn("interrompu", r.stdout.lower())
        self.assertFalse((dest / "gros.txt").exists())
        self.nc("telecharger", eid, str(dest), code=0)                 # place libérée : la même commande reprend
        self.assertEqual((dest / "gros.txt").read_bytes(), b"x" * 300000)

    def brut(self, *args, env=None):
        return subprocess.run([sys.executable, str(NC_CLOUD), *args], capture_output=True, text=True, timeout=60,
                              env=env or self.env(), stdin=subprocess.DEVNULL)

    def test_commandes_suggerees_jamais_executees_par_un_shell(self):
        a, b, f = self.arbre_de_test()
        piege = "$(touch${IFS}PIEGE)`touch${IFS}PIEGE2`;touch${IFS}PIEGE3"
        self.faux.entries[a]["revision"] = piege
        r = self.brut("apercu", a)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        ligne = r.stdout.splitlines()[-1].split(" : ", 1)[1]
        cwd, fbin = self.d / "shell", self.d / "fbin"
        cwd.mkdir()
        fbin.mkdir()
        recu = self.d / "argv-recu"
        (fbin / "nc-cloud").write_text("#!" + sys.executable + f"\nimport sys, json\nopen({str(recu)!r}, 'w').write(json.dumps(sys.argv[1:]))\n")
        (fbin / "nc-cloud").chmod(0o755)
        subprocess.run(["bash", "-c", ligne], cwd=cwd, env={"PATH": f"{fbin}:/usr/bin:/bin"}, timeout=10)
        self.assertEqual(list(cwd.iterdir()), [], "rien ne s'exécute au copier-coller")
        self.assertEqual(json.loads(recu.read_text()), ["supprimer", a, "--revision=" + piege, "--recursif", "--arbre=" + self.faux.arbre(a)])
        r = self.brut("entree", a)
        self.assertIn(shlex.quote(piege), r.stdout)
        self.assertIn(shlex.quote(piege), self.brut("lister", "root").stdout, "lister : la révision aussi protégée")
        for mauvaise in ("a b", "a\nb", 'x"y', "é"):
            self.faux.entries[a]["revision"] = mauvaise
            r = self.brut("apercu", a)
            self.assertIn("aucune commande suggérée", r.stdout, repr(mauvaise))
            self.assertNotIn("supprimer", r.stdout)
            self.assertIn("révision inattendue", self.brut("entree", a).stdout)

    def test_lister_curseur_piege_jamais_execute(self):
        self.associer()
        for i in range(3):
            self.nc("dossier", "root", f"D{i}", code=0)
        piege = "$(touch${IFS}PIEGE)"
        self.faux.curseur_force = piege
        r = self.brut("lister", "root")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        ligne = r.stdout.splitlines()[-1].split(" : ", 1)[1]
        cwd = self.d / "shell2"
        cwd.mkdir()
        subprocess.run([shutil.which("bash") or "/bin/bash", "-c", ligne], cwd=cwd, env={"PATH": "/nulle-part"}, timeout=10,
                       capture_output=True)
        self.assertEqual(list(cwd.iterdir()), [], "rien ne s'exécute au copier-coller")
        self.assertIn(shlex.quote("--suite=" + piege), ligne)
        self.faux.curseur_force = "a b"
        r = self.brut("lister", "root")
        self.assertIn("aucune commande suggérée", r.stdout)

    def test_nombres_hostiles(self):
        a, b, f = self.arbre_de_test()
        self.faux.entries[f]["size"] = 10 ** 400
        r = self.brut("entree", f)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.faux.entries[f]["size"] = -5
        self.assertNotIn("size", self.nc("entree", f, code=0).lignes[-1]["entree"])

    def test_creer_hors_ligne_ou_nom_pris(self):
        self.faux.gestion = True
        self.associer()
        r = self.nc("creer", "root", "pris.txt", code=0)
        r = self.brut("creer", "root", "pris.txt")
        self.assertEqual(r.returncode, 6)
        self.assertIn("ce nom existe déjà", r.stdout)
        self.assertNotIn("--si-existe", r.stdout + r.stderr)
        self.url("http://127.0.0.1:9")
        self.nc("creer", "root", "vide.txt", code=3)
        self.assertEqual(list((self.home / ".local/state/nc-cloud/vides").rglob("*")), [])
        self.assertFalse(self.manifestes())

    def test_rejeu_sur_une_autre_route_nouvelle_cle(self):
        self.faux.gestion = self.faux.revisions_vivantes = self.faux.suppression = True
        self.associer()
        eid = self.depot("f.txt", b"x")
        rev = self.rev(eid)
        self.faux.pannes.add("perdre_gestion")
        self.nc("supprimer", eid, "--revision", rev, code=3)
        self.faux.gestion = False                         # le serveur n'annonce plus directory_delete : autre route
        self.nc("supprimer", eid, "--revision", rev, code=1)
        sup = [c for c in self.faux.journal if c[0] == "DELETE"]
        self.assertEqual([c[1].split("/v1")[1].split("/")[1] for c in sup], ["entries", "files"])
        self.assertNotEqual(sup[0][2]["Idempotency-Key"], sup[1][2]["Idempotency-Key"])

    def test_erreur_500_pendant_une_mutation_le_manifeste_reste(self):
        a, b, f = self.arbre_de_test()
        rev = self.rev(f)
        self.faux.pannes.add("erreur_500_gestion")
        r = self.nc("deplacer", f, "--revision", rev, "--vers", "root")
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual(len(self.manifestes("operations")), 1, "l'opération a peut-être eu lieu")
        r = self.nc("deplacer", f, "--revision", rev, "--vers", "root", code=0)       # même clé : le reçu
        self.assertEqual(r.lignes[-1]["etat"], "deplace")
        self.assertFalse(self.manifestes("operations"))


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

    def test_dossier_prive_chaque_niveau_et_aucun_lien(self):
        m = self.charger("http://127.0.0.1:9")
        h = Path(os.environ["HOME"])
        ancien = os.umask(0)
        try:
            m.dossier_prive(h / ".cache/nc-cloud/ouverts/abc")
        finally:
            os.umask(ancien)
        for x in (".cache", ".cache/nc-cloud", ".cache/nc-cloud/ouverts", ".cache/nc-cloud/ouverts/abc"):
            self.assertEqual(stat.S_IMODE((h / x).stat().st_mode), 0o700, x)
        ailleurs = h.parent / "ailleurs"
        ailleurs.mkdir()
        (h / ".local/state").mkdir(parents=True)
        (h / ".local/state/nc-cloud").symlink_to(ailleurs)
        with self.assertRaises(m.Echec):
            m.dossier_prive(h / ".local/state/nc-cloud/envois")
        self.assertEqual(list(ailleurs.iterdir()), [], "rien d'écrit au bout du lien")
        lien_home = h.parent / "lien-home"                 # un HOME derrière un lien (/home -> /var/home) reste permis
        lien_home.symlink_to(h)
        m.dossier_prive(lien_home / ".cache/nc-cloud/ouverts/def")
        # Un dossier de la chaîne qui n'est pas à l'utilisateur (XDG_CACHE_HOME pointé vers un dossier ouvert à tous)
        with mock.patch.object(m.os, "getuid", return_value=os.getuid() + 1):
            with self.assertRaises(m.Echec):
                m.dossier_prive(h / ".cache/nc-cloud/ouverts/ghi")
        self.assertFalse((h / ".cache/nc-cloud/ouverts/ghi").exists())

    def test_table_des_types_figee_sans_le_systeme(self):
        """Ni mimetypes ni /etc/mime.types : la même décision sur les 4 distributions (openSUSE n'a pas .csv en text/csv)."""
        self.assertNotRegex(NC_CLOUD.read_text(), r"^import mimetypes|mimetypes\.")
        m = self.charger("http://127.0.0.1:9")
        for nom, attendu in (("liste.csv", "text/csv"), ("a.b.PNG", "image/png"), ("x.jpeg", "image/jpeg"), ("film.wmv", "video/x-ms-wmv"),
                             ("notes", None), ("x.txt.gz", None), ("x.html", None), ("x.svg", None), ("x.m3u", None), ("x.asx", None)):
            self.assertEqual(m.type_du_nom(nom), attendu, nom)
        for ext in m.OUVRIR_EXTENSIONS.values():          # toute extension de sortie se relit dans la même famille
            self.assertIn(ext, m.OUVRIR_PAR_EXTENSION, ext)
        for t, ext in m.OUVRIR_EXTENSIONS.items():
            self.assertEqual(m.famille_sure(m.OUVRIR_PAR_EXTENSION[ext]), m.famille_sure(t), t)
        cas = (("liste.csv", "text/plain", ".csv"), ("liste.csv", "text/csv", ".csv"), ("notes.md", "text/plain", ".md"),
               ("photo.PNG", "image/png", ".png"), ("film.wmv", "video/x-ms-asf", ".wmv"), ("x.png", "text/plain", None),
               ("scene.mp4", "video/x-javafx", None), ("x.txt", "text/html", None), ("x.csv", "image/png", None))
        for nom, contenu, attendu in cas:
            with mock.patch.object(m, "type_par_contenu", return_value=contenu):
                self.assertEqual(m.extension_sure("/inutile", nom), attendu, (nom, contenu))

    def test_nettoyer_ouverts_sans_suivre_un_lien_meme_en_course(self):
        m = self.charger("http://127.0.0.1:9")
        racine = Path(os.environ["HOME"]).parent
        base, precieux = racine / "ouverts", racine / "precieux"
        (base / "0123456789abcdef").mkdir(parents=True)
        (base / "fedcba9876543210").mkdir()
        precieux.mkdir()
        vieux = time.time() - 30 * 3600
        for f in (precieux / "these.odt", precieux / "photo.jpg", base / "fedcba9876543210/vieux.txt"):
            f.write_text("x")
            os.utime(f, (vieux, vieux))
        (base / "fedcba9876543210/recent.txt").write_text("x")
        (base / "lien").symlink_to(precieux)                # un lien déjà posé
        vrai = os.scandir
        etat = {"fait": False}

        def scandir(p):
            r = vrai(p)
            if not etat["fait"]:                            # l'autre processus, juste après la liste de base
                etat["fait"] = True
                os.rmdir(base / "0123456789abcdef")
                os.symlink(precieux, base / "0123456789abcdef")
            return r
        with mock.patch.object(m.os, "scandir", scandir):
            m.nettoyer_ouverts(base)
        self.assertTrue(etat["fait"])
        self.assertEqual(sorted(x.name for x in precieux.iterdir()), ["photo.jpg", "these.odt"])
        self.assertEqual(sorted(x.name for x in (base / "fedcba9876543210").iterdir()), ["recent.txt"])

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
        self.assertEqual((srv.port, srv.adresse), (80, ["::1"]))
        c = srv.connexion()
        self.assertEqual((c.host, c.port), ("::1", 80))



# Un faux module gi (Gio, GLib), injecté par PYTHONPATH : rien n'est monté. FAUX_GI choisit le cas ; tout est noté dans
# FAUX_GI_JOURNAL (le mot de passe reçu par la MountOperation seulement en empreinte SHA-256)
FAUX_GI_INIT = """import os
if os.environ.get("FAUX_GI") == "absent":
    raise ImportError("faux : pas de gi")
def require_version(nom, version):
    if os.environ.get("FAUX_GI") == "sans_gio":
        raise ValueError("Namespace Gio not available")
"""
FAUX_GI_REPO = r'''import hashlib, json, os
MODE = os.environ.get("FAUX_GI", "ok")
_rappels = []
def note(**k):
    with open(os.environ["FAUX_GI_JOURNAL"], "a") as f:
        f.write(json.dumps(k) + "\n")
class _Erreur(Exception):
    def __init__(self, code, message):
        super().__init__(message); self.code, self.message = code, message
    def matches(self, quark, code):
        return self.code == code
class GLib:
    Error = _Erreur
    class MainLoop:
        def run(self):
            while _rappels:
                _rappels.pop(0)()
        def quit(self):
            pass
    @staticmethod
    def timeout_add_seconds(n, f):
        note(evt="delai", n=n)
        if MODE == "jamais":               # le délai se joue vraiment (un tour plus tard) : GVfs, lui, ne rappelle jamais
            _rappels.append(lambda: _rappels.append(f))
class _Racine:
    def __init__(self, u): self.u = u
    def get_uri(self): return self.u
class _Montage:
    def __init__(self, u): self.u = u
    def get_root(self):
        return _Racine(self.u.split("/cloud/", 1)[0] + "/" if MODE == "deja_autre" else self.u)
    def unmount_with_operation(self, flags, op, annuler, rappel):
        note(evt="demonter", uri=self.u); _rappels.append(lambda: rappel(self, None))
        if os.path.exists(os.environ["FAUX_GI_JOURNAL"] + ".monte"):
            os.unlink(os.environ["FAUX_GI_JOURNAL"] + ".monte")
    def unmount_with_operation_finish(self, res):
        pass
class _Fichier:
    def __init__(self, u): self.u = u
    def find_enclosing_mount(self, annuler):
        if MODE in ("deja", "deja_autre") or os.path.exists(os.environ["FAUX_GI_JOURNAL"] + ".monte"):
            return _Montage(self.u)
        raise _Erreur(0, "pas monté")
    def mount_enclosing_volume(self, flags, op, annuler, rappel):
        note(evt="monter", uri=self.u)
        def jouer():
            if MODE == "question":
                op.h["ask-question"](op, "Certificat inconnu, continuer ?", ["Oui", "Non"])
            elif MODE == "domaine":
                op.h["ask-password"](op, "Mot de passe pour Cloud", "", "Cloud", 1 | 2 | 4)
            elif MODE == "msg_proxy":
                op.h["ask-password"](op, "Enter PROXY password for proxy.example:3128", "", "", 1 | 2)
            elif MODE == "sans_mdp":
                op.h["ask-password"](op, "Nom d'utilisateur", "", "", 2)
            elif MODE == "refus_puis_mdp":            # refusée, puis une demande ordinaire : refusée aussi
                op.h["ask-password"](op, "Nom d'utilisateur", "", "", 2)
                op.h["ask-password"](op, "Mot de passe", "", "Cloud", 1 | 2)
            elif MODE == "mdp_puis_question":
                op.h["ask-password"](op, "Mot de passe", "", "Cloud", 1 | 2)
                op.h["ask-question"](op, "Certificat inconnu, continuer ?", ["Oui", "Non"])
            elif MODE not in ("deja_autre",):
                for _ in range(2 if MODE == "mdp_refuse" else 1):
                    op.h["ask-password"](op, "Mot de passe", "", "Cloud", 1 | 2)
            if MODE == "jamais":
                return                     # GVfs ne rappelle jamais, même après l'annulation
            if MODE == "question_monte":
                op.h["ask-question"](op, "Certificat inconnu, continuer ?", ["Oui", "Non"])
                open(os.environ["FAUX_GI_JOURNAL"] + ".monte", "w").close()
            rappel(self, None)
        _rappels.append(jouer)
    def mount_enclosing_volume_finish(self, res):
        if MODE == "deja_autre":
            raise _Erreur(17, "déjà monté")
        if MODE in ("question", "mdp_refuse", "domaine", "msg_proxy", "sans_mdp", "refus_puis_mdp", "mdp_puis_question"):
            raise _Erreur(19, "annulé")
        if MODE == "erreur":
            raise _Erreur(1, "Hôte injoignable\x1b[31m")
class _Vfs:
    def get_supported_uri_schemes(self):
        return ["file", "sftp"] if MODE == "sans_dav" else ["file", "sftp", "dav", "davs"]
class _Appli:
    def launch_uris(self, uris, contexte):
        note(evt="ouvrir", uris=uris); return True
class _Resolveur:
    def lookup(self, uri, annuler):
        note(evt="proxy", uri=uri)
        if MODE == "proxy_erreur":
            raise _Erreur(1, "résolveur cassé")
        return ["http://proxy.example:3128", "direct://"] if MODE == "proxy" else ["direct://"]
class Gio:
    class AskPasswordFlags:
        NEED_PASSWORD, NEED_USERNAME, NEED_DOMAIN = 1, 2, 4
    class ProxyResolver:
        @staticmethod
        def get_default():
            return _Resolveur()
    class PasswordSave:
        NEVER, FOR_SESSION, PERMANENTLY = "jamais", "session", "toujours"
    class MountOperationResult:
        HANDLED, ABORTED = "repondu", "refuse"
    class MountMountFlags:
        NONE = 0
    class MountUnmountFlags:
        NONE = 0
    class IOErrorEnum:
        ALREADY_MOUNTED = 17
    @staticmethod
    def io_error_quark():
        return 0
    class Cancellable:
        def cancel(self):
            note(evt="annule")
    class Vfs:
        @staticmethod
        def get_default():
            return _Vfs()
    class File:
        @staticmethod
        def new_for_uri(u):
            return _Fichier(u)
    class AppInfo:
        @staticmethod
        def get_default_for_type(t, local):
            note(evt="appli", type=t); return _Appli()
    class MountOperation:
        def __init__(self):
            self.h, self.u, self.p, self.save = {}, None, None, None
        def connect(self, signal, f):
            self.h[signal] = f
        def set_username(self, u): self.u = u
        def set_password(self, p): self.p = p
        def set_password_save(self, s): self.save = s
        def reply(self, r):
            note(evt="reponse", r=r, u=self.u, mdp=hashlib.sha256(self.p.encode()).hexdigest() if self.p else None, save=self.save)
'''


DBUS_DAEMON = shutil.which("dbus-daemon")        # lu avant que les tests ne changent PATH


class FauxBus(threading.Thread):
    """Un bus de session en Python, juste assez pour nc-cloud choisir : authentification, Hello, AddMatch, OpenFile (et
    Close) ; le portail répond (mode « choisi » ou « annule ») ou attend (« attente »). Tout est noté dans journal."""

    def __init__(self, m, chemin, mode, uris=()):
        super().__init__(daemon=True)
        self.m, self.mode, self.uris, self.journal, self.serie = m, mode, list(uris), [], 100
        self.srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.srv.bind(str(chemin))
        self.srv.listen(1)
        self.srv.settimeout(30)
        self.fini = threading.Event()

    def envoyer(self, type_, champs, sig="", corps=()):
        c = self.m.BusEcrit()
        for t, v in zip(self.m.bus_types(sig), corps):
            c.valeur(t, v)
        h = self.m.BusEcrit()
        self.serie += 1
        h.b += b"l" + bytes([type_, 1, 1])
        h.valeur("u", len(c.b))
        h.valeur("u", self.serie)
        h.valeur("a(yv)", champs + ([(8, ("g", sig))] if sig else []))
        h.aligner(8)
        self.conn.sendall(bytes(h.b) + bytes(c.b))

    def run(self):
        try:
            self.conn, _ = self.srv.accept()
            self.conn.settimeout(30)
            b = b""
            while not b.endswith(b"\r\n"):
                b += self.conn.recv(1)
            self.journal.append(("AUTH", b))
            self.conn.sendall(b"OK 0123456789abcdef0123456789abcdef\r\n")
            b = b""
            while not b.endswith(b"\r\n"):
                b += self.conn.recv(1)
            lecteur = self.m.Bus.__new__(self.m.Bus)
            lecteur.sock = self.conn
            while True:
                _, champs, valeurs, serie = lecteur.lire()
                membre = champs.get(3)
                self.journal.append((membre, champs.get(1), valeurs))

                def rep(sig="", corps=(), serie=serie):
                    self.envoyer(2, [(5, ("u", serie)), (6, ("s", ":1.42"))], sig, corps)
                if membre == "Hello":
                    rep("s", (":1.42",))
                elif membre == "StartServiceByName" and self.mode == "sans_service":
                    self.envoyer(3, [(4, ("s", "org.freedesktop.DBus.Error.ServiceUnknown")), (5, ("u", serie)), (6, ("s", ":1.42"))],
                                 "s", ("Le nom n'est fourni par aucun fichier .service",))
                elif membre == "StartServiceByName":
                    rep("u", (2,))
                elif membre == "GetNameOwner":
                    rep("s", (":1.7",))
                elif membre == "AddMatch":
                    rep()
                elif membre == "OpenFile":
                    poignee = "/org/freedesktop/portal/desktop/request/1_42/" + valeurs[2]["handle_token"]
                    rep("o", (poignee,))
                    rp = [(1, ("o", poignee)), (2, ("s", "org.freedesktop.portal.Request")), (3, ("s", "Response")),
                          (6, ("s", ":1.42")), (7, ("s", ":1.7"))]
                    if self.mode in ("choisi", "annule", "sans_service"):
                        # D'abord une réponse pour une AUTRE demande, puis une forgée par un autre pair, puis une d'une autre
                        # interface : toutes ignorées
                        self.envoyer(4, [(1, ("o", poignee + "x"))] + rp[1:], "ua{sv}", (0, {"uris": ("as", ["file:///piege"])}))
                        self.envoyer(4, rp[:4] + [(7, ("s", ":1.99"))], "ua{sv}", (0, {"uris": ("as", ["file:///forge"])}))
                        self.envoyer(4, [rp[0], (2, ("s", "org.exemple.Autre"))] + rp[2:], "ua{sv}", (0, {"uris": ("as", ["file:///autre"])}))
                        choisi = self.mode in ("choisi", "sans_service")
                        self.envoyer(4, rp, "ua{sv}", (0 if choisi else 1, {"uris": ("as", self.uris)} if choisi else {}))
                elif membre == "Close":
                    self.fini.set()
                    return
        except (OSError, self.m.Echec):
            pass
        finally:
            for x in (getattr(self, "conn", None), self.srv):
                if x is not None:
                    x.close()
            self.fini.set()


class Selecteur(unittest.TestCase):
    """nc-cloud choisir : le sélecteur du portail, par un faux bus (partout) et par un vrai dbus-daemon privé s'il existe."""

    def setUp(self):
        self.d = Path(tempfile.mkdtemp(prefix="nc-cloud-choix-"))
        self.addCleanup(shutil.rmtree, self.d, True)
        self.home = self.d / "home"
        self.home.mkdir()
        env = mock.patch.dict(os.environ, {"HOME": str(self.home), "TMPDIR": str(self.d), "XDG_STATE_HOME": str(self.home / "st"),
                                           "XDG_CONFIG_HOME": str(self.home / "cf"), "NC_LANGUE": "fr", "PATH": str(self.d)})
        env.start()
        self.addCleanup(env.stop)
        l = importlib.machinery.SourceFileLoader("nc_cloud_choix", str(NC_CLOUD))
        self.m = importlib.util.module_from_spec(importlib.util.spec_from_loader("nc_cloud_choix", l))
        l.exec_module(self.m)

    def env(self, bus):
        return {"HOME": str(self.home), "PATH": str(self.d), "TMPDIR": str(self.d), "NC_LANGUE": "fr", "XDG_RUNTIME_DIR": str(self.d),
                "XDG_STATE_HOME": str(self.home / "st"), "XDG_CONFIG_HOME": str(self.home / "cf"),
                "DBUS_SESSION_BUS_ADDRESS": "unix:path=" + str(bus)}

    def faux_bus(self, mode, uris=()):
        b = FauxBus(self.m, self.d / "bus", mode, uris)
        b.start()
        return b

    def test_marshalling_aller_retour(self):
        sig = "ssa{sv}(ua{sv})as"
        v = ["", "Titre é", {"handle_token": ("s", "nc_x"), "multiple": ("b", True)}, (7, {"uris": ("as", ["file:///a b"])}), ["x", ""]]
        e = self.m.BusEcrit()
        for t, x in zip(self.m.bus_types(sig), v):
            e.valeur(t, x)
        lu = self.m.BusLit(bytes(e.b))
        r = [lu.valeur(t) for t in self.m.bus_types(sig)]
        self.assertEqual(r, ["", "Titre é", {"handle_token": "nc_x", "multiple": True}, (7, {"uris": ["file:///a b"]}), ["x", ""]])
        self.assertEqual(lu.p, len(e.b))
        # Octets attendus d'une chaîne, d'un booléen et d'une variante (spécification D-Bus, petit-boutiste)
        e = self.m.BusEcrit()
        e.valeur("s", "ab"); e.valeur("b", True); e.valeur("v", ("s", "c"))
        self.assertEqual(bytes(e.b), b"\x02\x00\x00\x00ab\x00\x00\x01\x00\x00\x00\x01s\x00\x00\x01\x00\x00\x00c\x00")
        for brut in (b"\xff\xff\xff\x7f", b"\x05\x00\x00\x00ab"):           # tableau ou chaîne plus long que le message
            with self.assertRaises(ValueError):
                self.m.BusLit(brut).valeur("as" if brut[0] == 0xff else "s")
        # Types vides ou boiteux : refusés avant toute lecture (un tableau de « () » ferait boucler l'analyse)
        for sig in ("a()", "a{}", "()", "{s}", "{sss}", "a" * 40 + "s", "(s", "z"):
            with self.assertRaises((ValueError, IndexError), msg=sig):
                self.m.bus_types(sig)
        # Un message entier du bus avec un tel corps : ignoré (None), sans boucler
        for sig in ("a()", "a{}"):
            h = self.m.BusEcrit()
            h.b += b"l" + bytes([4, 1, 1])
            corps = struct.pack("<I", 8) + b"\0" * 12
            h.valeur("u", len(corps)); h.valeur("u", 7)
            h.valeur("a(yv)", [(1, ("o", "/x")), (2, ("s", "a.b")), (3, ("s", "C")), (8, ("g", sig))])
            h.aligner(8)
            a, b = socket.socketpair()
            self.addCleanup(a.close); self.addCleanup(b.close)
            a.sendall(bytes(h.b) + corps)
            lecteur = self.m.Bus.__new__(self.m.Bus)
            lecteur.sock = b
            b.settimeout(5)
            debut = time.monotonic()
            self.assertIsNone(lecteur.lire(), sig)
            self.assertLess(time.monotonic() - debut, 2)
        # Même sans le refus des types, l'analyseur ne boucle pas : la position doit avancer à chaque élément
        with self.assertRaises(ValueError):
            self.m.BusLit(struct.pack("<I", 8) + b"\0" * 12).valeur("a()")
        # Un tableau d'octets ordinaire passe toujours (la position avance)
        self.assertEqual(self.m.BusLit(struct.pack("<I", 3) + b"abc").valeur("ay"), [97, 98, 99])

    def test_choisis_seulement_pour_sa_demande(self):
        b = self.faux_bus("choisi", ["file:///home/user/a%20b.png", "file:///home/user/c.txt"])
        r = subprocess.run([sys.executable, str(NC_CLOUD), "--json", "choisir"], capture_output=True, text=True, timeout=60,
                           env=self.env(self.d / "bus"), stdin=subprocess.DEVNULL)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        lignes = [json.loads(x) for x in r.stdout.splitlines() if x.startswith("{")]
        self.assertEqual(lignes, [{"evenement": "choisis", "fichiers": ["file:///home/user/a%20b.png", "file:///home/user/c.txt"]}])
        b.join(10)
        membres = [x[0] for x in b.journal]
        self.assertEqual(membres[:6], ["AUTH", "Hello", "StartServiceByName", "GetNameOwner", "AddMatch", "OpenFile"], membres)
        self.assertEqual(b.journal[0][1], b"\0AUTH EXTERNAL " + str(os.getuid()).encode().hex().encode() + b"\r\n")
        jeton = b.journal[5][2][2]["handle_token"]
        self.assertRegex(jeton, r"^nc_cloud_[0-9a-f]{16}$")
        self.assertIn(f"path='/org/freedesktop/portal/desktop/request/1_42/{jeton}'", b.journal[4][2][0])
        self.assertIn("sender=':1.7'", b.journal[4][2][0])
        self.assertEqual(b.journal[5][1], "/org/freedesktop/portal/desktop")
        self.assertIs(b.journal[5][2][2]["multiple"], True)

    def test_portail_sans_fichier_service_mais_present(self):
        b = self.faux_bus("sans_service", ["file:///home/user/c.txt"])
        r = subprocess.run([sys.executable, str(NC_CLOUD), "--json", "choisir"], capture_output=True, text=True, timeout=60,
                           env=self.env(self.d / "bus"), stdin=subprocess.DEVNULL)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(json.loads(r.stdout.splitlines()[-1]), {"evenement": "choisis", "fichiers": ["file:///home/user/c.txt"]})
        b.join(10)
        self.assertIn("GetNameOwner", [x[0] for x in b.journal])

    def test_annule_aucune_adresse(self):
        self.faux_bus("annule")
        r = subprocess.run([sys.executable, str(NC_CLOUD), "--json", "choisir"], capture_output=True, text=True, timeout=60,
                           env=self.env(self.d / "bus"), stdin=subprocess.DEVNULL)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(json.loads(r.stdout.splitlines()[-1]), {"evenement": "choisis", "fichiers": []})

    def test_panneau_ferme_referme_le_selecteur_sans_rien_laisser(self):
        b = self.faux_bus("attente")
        p = subprocess.Popen([sys.executable, str(NC_CLOUD), "--json", "choisir"], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             env=self.env(self.d / "bus"), stdin=subprocess.DEVNULL)
        self.addCleanup(lambda: p.poll() is None and p.kill())
        fin = time.monotonic() + 20
        while "OpenFile" not in [x[0] for x in b.journal] and time.monotonic() < fin:
            time.sleep(0.05)
        p.send_signal(signal.SIGTERM)
        self.assertEqual(p.wait(timeout=20), 8)
        self.assertTrue(b.fini.wait(10))
        fermes = [x for x in b.journal if x[0] == "Close"]
        self.assertEqual(len(fermes), 1, b.journal)
        self.assertTrue(fermes[0][1].startswith("/org/freedesktop/portal/desktop/request/1_42/nc_cloud_"), fermes)
        p.stdout.close(); p.stderr.close()

    def test_sans_bus_message_clair(self):
        r = subprocess.run([sys.executable, str(NC_CLOUD), "--json", "choisir"], capture_output=True, text=True, timeout=60,
                           env=self.env(self.d / "absent"), stdin=subprocess.DEVNULL)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("dépose les fichiers sur l'île", r.stdout.lower())

    def test_favori_au_caractere_pres(self):
        f = self.m.favoris_chemin()
        f.parent.mkdir(parents=True)
        A = "davs://h/cloud/dav/"
        for avant, adresse, apres in (
                (b"file:///a A\r\nfile:///b B\r\n", A, b"file:///a A\r\nfile:///b B\r\n" + A.encode() + b" Cloud JARVIS\n"),
                (b"file:///a A\nfile:///b B", A, b"file:///a A\nfile:///b B\n" + A.encode() + b" Cloud JARVIS\n"),
                (b"file:///a nom\rsuite\n", None, None),                                    # rien à retirer : rien d'écrit
                ("file:///a x\u2028davs://autre Cloud JARVIS\n".encode(), None, None),     # U+2028 : pas une fin de ligne
                (b"file:///a x\x0cdavs://autre Cloud JARVIS\n", None, None),
                (b"file:///a \xff\xfe\n" + A.encode() + b" Cloud JARVIS\n", None, b"file:///a \xff\xfe\n"),
                (b"x\n" + A.encode() + b" Cloud JARVIS\n", A, None)):                     # déjà là, à l'identique
            with self.subTest(avant=avant, adresse=adresse):
                f.write_bytes(avant)
                os.utime(f, ns=(1, 1))
                ecrit = self.m.favori_changer(adresse)
                self.assertEqual(f.read_bytes(), avant if apres is None else apres)
                self.assertEqual(ecrit, apres is not None)
                if apres is None:
                    self.assertEqual(f.stat().st_mtime_ns, 1)                               # pas réécrit

    def test_aucun_pycache_laisse_a_cote_des_scripts(self):
        """nc-cloud et nc-noeud chargent nc-assistant et nc-bac comme modules : rien ne doit s'écrire dans ~/.local/bin."""
        b = self.d / "bin"
        b.mkdir()
        for n in ("nc-cloud", "nc-noeud", "nc-assistant", "nc-bac", "nc-ia"):
            shutil.copy(NC_CLOUD.parent / n, b / n)
        env = {k: v for k, v in os.environ.items() if k != "PYTHONDONTWRITEBYTECODE"}
        for n in ("nc-cloud", "nc-noeud"):
            with self.subTest(n):
                subprocess.run([sys.executable, str(b / n), "--help"], capture_output=True, timeout=60, env=env, stdin=subprocess.DEVNULL)
                self.assertEqual(sorted(x.name for x in b.iterdir()), ["nc-assistant", "nc-bac", "nc-cloud", "nc-ia", "nc-noeud"])

    def test_deposer_ouvre_une_fois_le_fichier_du_controle(self):
        d = self.home / "docs"
        d.mkdir()
        f = d / "a.txt"
        f.write_bytes(b"public")
        secret = self.home / "secret.bin"
        secret.write_bytes(b"cle!!!")
        raison, _, _, st = self.m.examiner_un(str(f))
        self.assertIsNone(raison)
        # Remplacé par un lien entre le contrôle et l'ouverture : refusé, rien n'est lu (aucun appel au serveur : s=None)
        f.unlink()
        f.symlink_to(secret)
        with self.assertRaises(self.m.Echec) as e:
            self.m.preparer(None, f, "root", "create", None, st)
        self.assertEqual(e.exception.code, self.m.SOURCE)
        self.assertIn("lien", str(e.exception))
        # Remplacé par un autre fichier ordinaire de même taille : refusé aussi
        f.unlink()
        f.write_bytes(b"autre!")
        os.utime(f, ns=(st.st_mtime_ns + 10**9, st.st_mtime_ns + 10**9))
        with self.assertRaises(self.m.Echec) as e:
            self.m.preparer(None, f, "root", "create", None, st)
        self.assertIn("remplacé", str(e.exception))
        # Ouvert : l'empreinte et la lecture de l'envoi passent par le descripteur, même si le chemin change ensuite
        _, _, _, st = self.m.examiner_un(str(f))
        fd = self.m.ouvrir_controle(f, st)
        self.addCleanup(os.close, fd)
        f.rename(d / "ancien")
        f.symlink_to(secret)
        self.assertEqual(self.m.empreinte_fd(fd), hashlib.sha256(b"autre!").hexdigest())
        envoi = self.m.Envoi.__new__(self.m.Envoi)
        envoi.fd, envoi.m = fd, {"source": str(f), "size": 6, "mtime_ns": st.st_mtime_ns}
        with envoi.lire() as lu:
            self.assertEqual(lu.read(), b"autre!")
        envoi.source_intacte()                 # par le descripteur : le lien posé sur le chemin n'y change rien
        # L'empreinte de l'intention vient aussi du descripteur, pas du chemin rouvert (qui mène maintenant au secret)
        s = mock.Mock(appareil={"server_id": "s", "space_id": "e", "device_id": "d"})
        with mock.patch.object(self.m, "revision_dossier", return_value="r1"):
            e = self.m.preparer_fd(s, f, "root", "create", None, fd)
        self.assertEqual(e.m["sha256"], hashlib.sha256(b"autre!").hexdigest())

    def test_cmd_deposer_passe_le_controle_a_l_envoi(self):
        f = self.home / "a.txt"
        f.write_bytes(b"x")
        vus = []
        with mock.patch.object(self.m, "Session"), \
                mock.patch.object(self.m, "deposer_un", side_effect=lambda *a, **k: vus.append(k.get("controle")) or 0):
            self.m.cmd_deposer(self.m.argparse.Namespace(fichiers=[str(f)], si_existe=None, dans=None))
        self.assertEqual((vus[0].st_ino, vus[0].st_dev), (f.stat().st_ino, f.stat().st_dev))

    def test_fichier_cache_quand_le_dossier_personnel_est_un_lien(self):
        vrai = self.d / "vrai-home"
        (vrai / ".notes").mkdir(parents=True)
        (vrai / ".notes/a.txt").write_bytes(b"x")
        (vrai / "b.txt").write_bytes(b"x")
        lien = self.d / "home-lien"
        lien.symlink_to(vrai)
        ailleurs = self.d / "disque"
        ailleurs.mkdir()
        (ailleurs / "c.txt").write_bytes(b"x")
        (vrai / ".cache").symlink_to(ailleurs)          # un dossier caché qui pointe hors du dossier personnel
        for maison in (str(lien), str(vrai)):
            for base in (str(lien), str(vrai)):
                with self.subTest(maison=maison, base=base), mock.patch.dict(os.environ, {"HOME": maison}):
                    self.assertTrue(self.m.examiner_un(base + "/.notes/a.txt")[2])
                    self.assertFalse(self.m.examiner_un(base + "/b.txt")[2])
                    if base == maison:
                        self.assertTrue(self.m.examiner_un(base + "/.cache/c.txt")[2])

    def test_illisible_entre_examen_et_empreinte_ce_fichier_seulement(self):
        with mock.patch.object(self.m, "preparer", side_effect=PermissionError("refusé")):
            sortie = io.StringIO()
            with contextlib.redirect_stdout(sortie):
                self.m.JSON_SORTIE = True
                try:
                    code = self.m.deposer_un(object(), Path("/home/user/b.txt"), "root", "create", None, False)
                finally:
                    self.m.JSON_SORTIE = False
        self.assertEqual(code, self.m.SOURCE)
        ev = json.loads(sortie.getvalue().splitlines()[-1])
        self.assertEqual((ev["fichier"], ev["etat"]), ("/home/user/b.txt", "refuse"))

    def test_adresse_dav_https_par_le_nom_et_ipv6_entre_crochets(self):
        class Srv:
            https, hote, port, base, adresse = True, "cloud.exemple.org", 443, "", None
        self.assertEqual(self.m.adresse_dav(Srv), "davs://cloud.exemple.org/cloud/dav/")
        Srv.port, Srv.base = 8443, "/jarvis"
        self.assertEqual(self.m.adresse_dav(Srv), "davs://cloud.exemple.org:8443/jarvis/cloud/dav/")
        Srv.https, Srv.adresse, Srv.port, Srv.base = False, ["fd00::1"], 80, ""
        with mock.patch.object(self.m.socket, "create_connection", side_effect=OSError):
            self.assertEqual(self.m.adresse_dav(Srv), "dav://[fd00::1]:80/cloud/dav/")
        Srv.adresse = []
        with self.assertRaises(self.m.Echec):
            self.m.adresse_dav(Srv)

    def test_nc_diag_sait_si_un_portail_choisit_des_fichiers(self):
        l = importlib.machinery.SourceFileLoader("nc_diag_choix", str(NC_CLOUD.parent / "nc-diag"))
        d = importlib.util.module_from_spec(importlib.util.spec_from_loader("nc_diag_choix", l))
        l.exec_module(d)
        d.PORTAILS = str(self.d / "portails")
        os.mkdir(d.PORTAILS)
        (self.d / "portails/hyprland.portal").write_text("[portal]\nInterfaces=org.freedesktop.impl.portal.Screenshot;org.freedesktop.impl.portal.ScreenCast;\n")
        self.assertFalse(d.selecteur_fichiers())                  # Hyprland seul ne choisit pas de fichiers
        (self.d / "portails/gtk.portal").write_text("[portal]\nDBusName=org.freedesktop.impl.portal.desktop.gtk\n"
                                                    "Interfaces=org.freedesktop.impl.portal.FileChooser; org.freedesktop.impl.portal.Settings;\n")
        self.assertTrue(d.selecteur_fichiers())
        self.assertIn('cle="portail_fichiers_absent"', (NC_CLOUD.parent / "nc-diag").read_text())
        # « Ouvrir dans Fichiers » : contrôle local, sans réseau ; gi absent, puis sans WebDAV, puis tout là
        with mock.patch.object(d, "sortie", return_value=("file sftp dav davs", 0)) as so:
            self.assertEqual(d.fichiers_cloud_manque(), "")
        self.assertEqual(so.call_args[0][0][1], "-I")                  # mode isolé : un gi du dossier courant n'est pas chargé
        with mock.patch.object(d, "sortie", return_value=("", 1)):
            self.assertIn("gi", d.fichiers_cloud_manque())
        with mock.patch.object(d, "sortie", return_value=("file sftp", 0)):
            self.assertIn("WebDAV", d.fichiers_cloud_manque())

    @unittest.skipUnless(DBUS_DAEMON, "dbus-daemon absent")
    def test_vrai_bus_prive_sans_portail(self):
        """Un vrai dbus-daemon privé, SANS dossier de services (aucun vrai portail ne peut y démarrer) : le format des
        messages est accepté (Hello, AddMatch), et l'absence de portail dit quoi faire."""
        conf = self.d / "bus.conf"
        conf.write_text(f"""<!DOCTYPE busconfig PUBLIC "-//freedesktop//DTD D-Bus Bus Configuration 1.0//EN"
 "http://www.freedesktop.org/standards/dbus/1.0/busconfig.dtd">
<busconfig><type>session</type><listen>unix:path={self.d / "vrai-bus"}</listen><auth>EXTERNAL</auth>
<policy context="default"><allow send_destination="*" eavesdrop="true"/><allow eavesdrop="true"/><allow own="*"/></policy></busconfig>
""")
        d = subprocess.Popen([DBUS_DAEMON, "--config-file=" + str(conf), "--nofork", "--print-address"],
                             stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, env={"PATH": "/usr/bin:/bin"})
        self.addCleanup(lambda: (d.kill(), d.wait(), d.stdout.close()))
        self.assertIn(b"vrai-bus", d.stdout.readline())
        r = subprocess.run([sys.executable, str(NC_CLOUD), "--json", "choisir"], capture_output=True, text=True, timeout=60,
                           env=self.env(self.d / "vrai-bus"), stdin=subprocess.DEVNULL)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("Aucun sélecteur de fichiers", r.stdout)


if __name__ == "__main__":
    unittest.main()

"""Aide des tests de nc-vpn : un faux nmcli (jamais le vrai) qui note ses arguments et tient un petit état de connexions
dans un fichier JSON. Données de test : noms « Labo », « Maison », adresses de documentation (192.0.2.x, 2001:db8::)."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
BIN = REPO / "home/.local/bin/nc-vpn"

U1 = "11111111-1111-4111-8111-111111111111"
U2 = "22222222-2222-4222-8222-222222222222"
U3 = "33333333-3333-4333-8333-333333333333"
U4 = "44444444-4444-4444-8444-444444444444"
NOUVEAU = "99999999-9999-4999-8999-999999999999"

FAUX_NMCLI = r'''#!/usr/bin/env python3
import json, os, stat, sys
from pathlib import Path
R = Path(os.environ["FAUX_DIR"])
a = sys.argv[1:]
with (R / "appels.jsonl").open("a") as f: f.write(json.dumps(a) + "\n")
if os.environ.get("NM_ARRETE") == "1":
    print("Error: NetworkManager is not running.", file=sys.stderr); sys.exit(8)
etat = json.loads((R / "etat.json").read_text())
def sauver(): (R / "etat.json").write_text(json.dumps(etat))
def esc(s): return s.replace("\\", "\\\\").replace(":", "\\:")
if a[:4] == ["-t", "-g", "vpn.data", "connection"]:
    vd = R / "vpn_data.json"
    print((json.loads(vd.read_text()) if vd.exists() else {}).get(a[-1], ""))
elif a[-2:] == ["connection", "show"]:
    for c in etat:
        print(":".join([c["uuid"], c["type"], "yes" if c["active"] else "no", c["dev"] if c["active"] else "--", esc(c["nom"])]))
elif a[-1:] == ["general"]:
    print("running")
elif a[:3] == ["connection", "up", "uuid"]:
    if "passwd-file" in a:
        p = Path(a[a.index("passwd-file") + 1])
        with (R / "passwd.jsonl").open("a") as f:
            f.write(json.dumps({"chemin": str(p), "mode": stat.S_IMODE(p.stat().st_mode), "mode_dossier": stat.S_IMODE(p.parent.stat().st_mode),
                                "contenu": p.read_text()}) + "\n")
    if os.environ.get("NM_ECHEC_UP") == "2":
        print("Error: Connection activation failed: Secrets were required, but not provided.", file=sys.stderr); sys.exit(4)
    if os.environ.get("NM_ECHEC_UP") == "3":
        print("Error: Connection activation failed: bad " + (R / "passwd.jsonl").read_text(), file=sys.stderr); sys.exit(4)
    if os.environ.get("NM_ECHEC_UP") == "1": print("Error: Connection activation failed.", file=sys.stderr); sys.exit(4)
    for c in etat:
        if c["uuid"] == a[3]: c["active"] = True
    sauver()
elif a[:3] == ["connection", "down", "uuid"]:
    for c in etat:
        if c["uuid"] == a[3]: c["active"] = False
    sauver()
elif a[:2] == ["connection", "import"]:
    chemin = a[a.index("file") + 1]
    p = Path(chemin)
    (R / "import.json").write_text(json.dumps({"mode_fichier": stat.S_IMODE(p.stat().st_mode), "mode_dossier": stat.S_IMODE(p.parent.stat().st_mode),
                                               "chemin": chemin, "dossier": str(p.parent), "contenu": p.read_text(), "type": a[a.index("type") + 1]}))
    if os.environ.get("NM_ECHEC_IMPORT") == "1":
        print("Error: failed to import '" + chemin + "': no good.", file=sys.stderr); sys.exit(1)
    nom = p.stem
    etat.append({"uuid": "99999999-9999-4999-8999-999999999999", "type": "wireguard" if a[a.index("type") + 1] == "wireguard" else "vpn",
                 "active": False, "dev": "wg0", "nom": nom})
    sauver()
    print("Connection '" + nom + "' (" + etat[-1]["uuid"] + ") successfully added.")
elif a[:2] == ["connection", "modify"]:
    if os.environ.get("NM_ECHEC_MODIFY") == "1": print("Error: modify", file=sys.stderr); sys.exit(1)
elif a[:2] == ["connection", "delete"]:
    etat[:] = [c for c in etat if c["uuid"] != a[3]]; sauver()
'''

# Faux secret-tool : note ses arguments (secret.jsonl) et son entrée standard (secret-stdin, à part). Ne touche jamais au vrai
# trousseau. SECRET_ECHEC=1 : échoue en recrachant son entrée sur la sortie d'erreur ; SECRET_ECHEC=2 : échoue proprement.
FAUX_SECRET_TOOL = r'''#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
R = Path(os.environ["FAUX_DIR"])
entree = sys.stdin.buffer.read()
if sys.argv[1:2] == ["lookup"]:
    with (R / "secret.jsonl").open("a") as f: f.write(json.dumps(sys.argv[1:]) + "\n")
    v = R / "secret-valeur"
    if os.environ.get("SECRET_LOOKUP_ECHEC") == "1":
        sys.stderr.write("erreur " + v.read_text() + "\n"); sys.stdout.write(v.read_text()); sys.exit(1)
    if not v.exists(): sys.exit(1)
    sys.stdout.buffer.write(v.read_bytes()); sys.exit(0)
if sys.argv[1:2] == ["store"] and os.environ.get("SECRET_ECHEC") not in ("1", "2"): (R / "secret-valeur").write_bytes(entree)
with (R / "secret.jsonl").open("a") as f: f.write(json.dumps(sys.argv[1:]) + "\n")
with (R / "secret-stdin").open("ab") as f: f.write(entree)
if os.environ.get("SECRET_ECHEC") == "1":
    sys.stderr.write("secret-tool: erreur avec " + entree.decode() + "\n"); sys.exit(1)
if os.environ.get("SECRET_ECHEC") == "2":
    sys.stderr.write("Cannot autolaunch D-Bus without X11 $DISPLAY\n"); sys.exit(1)
'''


# Faux gdbus : répond comme le bus de session. GDBUS_SECRETS=oui (service lancé), activable (installé), non (absent).
FAUX_GDBUS = r'''#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
with (Path(os.environ["FAUX_DIR"]) / "gdbus.jsonl").open("a") as f: f.write(json.dumps(sys.argv[1:]) + "\n")
m = os.environ.get("GDBUS_SECRETS", "oui")
if sys.argv[-2:-1] == ["org.freedesktop.DBus.NameHasOwner"] or "org.freedesktop.DBus.NameHasOwner" in sys.argv:
    print("(%s,)" % ("true" if m == "oui" else "false"))
else:
    print("(['org.freedesktop.DBus'%s],)" % (", 'org.freedesktop.secrets'" if m == "activable" else ""))
'''


# Faux `mullvad` : note seulement ses arguments (appels-mullvad.jsonl) ; sa sortie vient de mullvad.json s'il existe :
# {"json": "…", "texte": "…", "code": 0}. Par défaut : déconnecté. Jamais la vraie commande.
FAUX_MULLVAD = r'''#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
R = Path(os.environ["FAUX_DIR"])
a = sys.argv[1:]
with (R / "appels-mullvad.jsonl").open("a") as f: f.write(json.dumps(a) + "\n")
conf = json.loads((R / "mullvad.json").read_text()) if (R / "mullvad.json").exists() else {}
if a[:2] == ["status", "--json"]:
    if "json" not in conf: sys.exit(2)
    print(conf["json"]); sys.exit(conf.get("code", 0))
elif a[:1] == ["status"]:
    print(conf.get("texte", "Disconnected")); sys.exit(conf.get("code", 0))
elif conf.get("echec"):
    print(conf["echec"], file=sys.stderr); sys.exit(1)
'''


def connexions():
    return [dict(uuid=U1, type="vpn", active=False, dev="tun0", nom="Labo"),
            dict(uuid=U2, type="wireguard", active=True, dev="wg-maison", nom="Maison: 192.0.2.1"),
            dict(uuid=U3, type="vpn", active=True, dev="tun1", nom="Bureau\\ 2001:db8::1"),
            dict(uuid=U4, type="802-11-wireless", active=True, dev="wlan0", nom="Reseau sans fil")]


class BaseVpn(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="nc-vpn-test-")
        self.addCleanup(self._tmp.cleanup)
        self.r = Path(self._tmp.name)
        for d in ("home", "run", "tmp", "faux-bin", "cfg", "etat"):
            (self.r / d).mkdir(mode=0o700)
        n = self.r / "faux-bin" / "nmcli"
        n.write_text(FAUX_NMCLI)
        n.chmod(0o755)
        mv = self.r / "faux-bin" / "mullvad"
        mv.write_text(FAUX_MULLVAD)
        mv.chmod(0o755)
        gd = self.r / "faux-bin" / "gdbus"
        gd.write_text(FAUX_GDBUS)
        gd.chmod(0o755)
        st = self.r / "faux-bin" / "secret-tool"
        st.write_text(FAUX_SECRET_TOOL)
        st.chmod(0o755)
        (self.r / "etat.json").write_text(json.dumps(connexions()))

    def env(self, **plus):
        env = dict(os.environ, HOME=str(self.r / "home"), XDG_CONFIG_HOME=str(self.r / "cfg"), XDG_RUNTIME_DIR=str(self.r / "run"),
                   TMPDIR=str(self.r / "tmp"), XDG_STATE_HOME=str(self.r / "etat"), XDG_CACHE_HOME=str(self.r / "etat"),
                   XDG_DATA_HOME=str(self.r / "etat"), FAUX_DIR=str(self.r))
        env.update(plus)
        env.setdefault("NC_LANGUE", "fr")
        if "PATH" not in plus:
            env["PATH"] = str(self.r / "faux-bin") + ":" + os.environ.get("PATH", "/usr/bin:/bin")
        return env

    def vpn(self, *args, **plus):
        return subprocess.run([sys.executable, str(BIN)] + list(args), env=self.env(**plus), capture_output=True, text=True, timeout=30,
                              stdin=subprocess.DEVNULL)

    def appels_mullvad(self):
        p = self.r / "appels-mullvad.jsonl"
        return [json.loads(l) for l in p.read_text().splitlines()] if p.exists() else []

    def appels(self):
        p = self.r / "appels.jsonl"
        return [json.loads(l) for l in p.read_text().splitlines()] if p.exists() else []

    def etat_actifs(self):
        return {c["uuid"] for c in json.loads((self.r / "etat.json").read_text()) if c["active"]}

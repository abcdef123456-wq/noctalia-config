"""« port 8080 » et « processus firefox » en LECTURE SEULE : nc-processus avec un FAUX ss dans un PATH de test, et de
vrais processus lancés ici (python endormi sous un nom repérable, parfois avec un vrai socket à l'écoute) tués par pid
mémorisé à la fin. Aucun signal envoyé par le script. Puis Saisies.js (node) et Recherche.qml réel hors écran avec un
faux nc-processus : rien de lancé pour une saisie refusée, et les lignes s'ajoutent aux résultats ordinaires."""
from tests import _isolation  # noqa: F401
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unicodedata
import unittest

REPO = Path(__file__).resolve().parents[1]
QML = REPO / "home/.config/quickshell/nc-ile"
SCRIPT = REPO / "home/.local/bin/nc-processus"
SOURCE = SCRIPT.read_text(encoding="utf-8")
RECHERCHE = (QML / "Recherche.qml").read_text(encoding="utf-8")
DORMIR = "import time\ntime.sleep(300)\n"
# Écoute sur un port local au hasard, puis dit « port inode » et dort
ECOUTER = ("import os, socket, time\ns = socket.socket()\ns.bind(('127.0.0.1', 0))\ns.listen(1)\n"
           "print(s.getsockname()[1], os.fstat(s.fileno()).st_ino, flush=True)\ntime.sleep(300)\n")


def invisible(t):
    return any(unicodedata.category(c)[0] == "C" or unicodedata.category(c) in ("Zl", "Zp") for c in t)


class Base(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp(prefix="nc-proc-"))        # sous TMPDIR, jamais un chemin écrit en dur
        self.addCleanup(shutil.rmtree, str(self.d), True)
        self.bin = self.d / "bin"
        self.bin.mkdir()
        self.journal = self.d / "journal"
        self.env = {"PATH": str(self.bin), "HOME": str(self.d), "TMPDIR": str(self.d), "LC_ALL": "C.UTF-8",
                    "PYTHONIOENCODING": "utf-8", "XDG_RUNTIME_DIR": str(self.d), "XDG_CONFIG_HOME": str(self.d),
                    "XDG_CACHE_HOME": str(self.d), "XDG_STATE_HOME": str(self.d), "XDG_DATA_HOME": str(self.d)}

    def faux_ss(self, sortie=""):
        """Un faux ss en Python : note ses arguments, écrit SORTIE."""
        f = self.bin / "ss"
        f.write_text("#!%s\nimport sys\nopen(%r, 'a').write('ss ' + ' '.join(sys.argv[1:]) + '\\n')\nsys.stdout.write(%r)\n"
                     % (sys.executable, str(self.journal), sortie))
        f.chmod(0o755)

    def appels(self):
        return self.journal.read_text().splitlines() if self.journal.exists() else []

    def lancer(self, *args):
        return subprocess.run([sys.executable, "-I", str(SCRIPT), *args], env=self.env, capture_output=True, text=True, timeout=60)

    def json(self, *args):
        r = self.lancer(*args)
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)

    def processus(self, nom, code=DORMIR, *args):
        """Un vrai processus à nous, nommé NOM (lien vers python), tué par son pid mémorisé à la fin."""
        lien = self.d / nom
        if not os.path.lexists(str(lien)):
            lien.symlink_to(sys.executable)
        p = subprocess.Popen([str(lien), "-I", "-c", code, *args], stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        self.addCleanup(lambda: (p.poll() is None and p.kill(), p.wait(10), p.stdout.close()))
        for _ in range(100):                      # comm est posé à l'exec : attendre le nouveau nom
            if Path("/proc/%d/comm" % p.pid).read_bytes().rstrip(b"\n") == os.fsencode(nom)[:15]:
                break
            time.sleep(0.02)
        return p

    def ecouteur(self, nom):
        p = self.processus(nom, ECOUTER)
        port, ino = p.stdout.readline().decode().split()
        return p, int(port), ino


class Saisies(Base):
    def test_arguments_refuses_rien_lance(self):
        self.faux_ss()
        for args in (("port", "0"), ("port", "65536"), ("port", "99999"), ("port", "80;id"), ("port", "-1"), ("port", "٨٠"), ("port", " 80"),
                     ("port", ""), ("port", "008080"), ("processus", "$(id)"), ("processus", "../"), ("processus", "a" * 33), ("processus", ""),
                     ("processus", "a b"), ("processus", "fire;fox"), ("processus", "é"), ("arreter", "12", "1"), ("ps", "x"), ("process", "x"),
                     ("--zzz-inconnu",), ()):
            with self.subTest(args):
                r = self.lancer(*args)
                self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
                self.assertIn("usage", r.stderr)
                self.assertEqual(r.stdout, "")
        self.assertEqual(self.appels(), [], "rien de lancé pour une saisie refusée")

    def test_bornes_acceptees(self):
        self.faux_ss("")
        for n in ("1", "65535", "8080"):
            self.assertEqual(self.json("port", n), {"ss": True, "lignes": []})
        self.assertEqual(self.json("processus", "a" * 32)["lignes"], [])
        self.assertEqual(self.json("processus", "x.y_z-1")["lignes"], [])


class Ports(Base):
    def test_ss_absent_pas_de_ports(self):
        self.assertIsNone(shutil.which("ss", path=self.env["PATH"]))
        self.assertEqual(self.json("port", "8080"), {"ss": False, "lignes": []})

    def test_nos_processus_et_un_autre_compte(self):
        p, port, ino = self.ecouteur("nc-essai-port")
        n = 8080
        sortie = ("tcp LISTEN 0 4096 0.0.0.0:%d 0.0.0.0:* uid:1000 ino:%s sk:1 cgroup:/x <->\n"
                  "tcp LISTEN 0 4096 [::]:%d [::]:* uid:1000 ino:%s sk:2 <->\n"         # même socket : une seule ligne
                  "udp UNCONN 0 0 127.0.0.1:%d 0.0.0.0:* ino:999999999 sk:3 <->\n"     # socket introuvable chez nous
                  "tcp LISTEN 0 4096 127.0.0.1:18080 0.0.0.0:* ino:%s sk:4 <->\n"       # autre port
                  "u_str LISTEN 0 4096 /run/x:%d * ino:%s sk:5 <->\n") % (n, ino, n, ino, n, ino, n, ino)
        self.faux_ss(sortie)
        d = self.json("port", str(n))
        self.assertEqual(self.appels(), ["ss -Hltune"], "sans -p : aucun nom de processus dans la sortie lue")
        self.assertTrue(d["ss"])
        self.assertEqual(d["lignes"], [{"pid": p.pid, "nom": "nc-essai-port", "commande": d["lignes"][0]["commande"], "proto": "tcp", "port": n},
                                       {"autre": True, "proto": "udp", "port": n}], "seulement tcp et udp, sans doublon")
        self.assertIn("socket.socket()", d["lignes"][0]["commande"])
        self.assertIsNone(p.poll(), "lire ne touche à rien")

    def test_un_nom_ne_forge_pas_de_pid(self):
        """F2 : le texte de ss (un nom « ",pid=N,fd=M) » compris) n'est jamais lu pour un pid : seul l'inode compte."""
        victime = self.processus("nc-essai-victime")
        p, port, ino = self.ecouteur("nc-essai-port")
        faux = "users:((\"\",pid=%d,fd=3)\",pid=%d,fd=4))" % (victime.pid, victime.pid)
        self.faux_ss("tcp LISTEN 0 1 0.0.0.0:47811 0.0.0.0:* %s ino:%s sk:1 cgroup:/a\n"
                     "tcp LISTEN 0 1 0.0.0.0:47812 0.0.0.0:* %s ino:999999998 sk:2 cgroup:/a ino:%s\n" % (faux, ino, faux, ino))
        self.assertEqual([x.get("pid") for x in self.json("port", "47811")["lignes"]], [p.pid])
        self.assertEqual(self.json("port", "47812")["lignes"], [{"autre": True, "proto": "tcp", "port": 47812}],
                         "l'inode est le premier « ino: », jamais celui d'un cgroup")

    def test_au_plus_huit_lignes(self):
        ecs = [self.ecouteur("nc-essai-lot") for _ in range(10)]
        self.faux_ss("".join("tcp LISTEN 0 1 0.0.0.0:8080 0.0.0.0:* ino:%s sk:%d\n" % (ino, i) for i, (_, _, ino) in enumerate(ecs)))
        lignes = self.json("port", "8080")["lignes"]
        self.assertEqual(len(lignes), 8)
        self.assertTrue({x["pid"] for x in lignes} <= {p.pid for p, _, _ in ecs})


class Processus(Base):
    def test_trouve_les_notres(self):
        p = self.processus("nc-essai-proc")
        lignes = self.json("processus", "nc-essai-proc")["lignes"]
        self.assertEqual([x["pid"] for x in lignes], [p.pid])
        self.assertEqual(sorted(lignes[0]), ["commande", "nom", "pid"])
        self.assertEqual(lignes[0]["nom"], "nc-essai-proc")
        self.assertIsNone(p.poll())

    def test_au_plus_huit_et_seulement_les_notres(self):
        ps = [self.processus("nc-essai-lot") for _ in range(10)]
        lignes = self.json("processus", "NC-ESSAI-LOT")["lignes"]
        self.assertEqual(len(lignes), 8)
        self.assertTrue({x["pid"] for x in lignes} <= {p.pid for p in ps})

    def test_nom_et_commande_filtres_et_bornes(self):
        """F3 : contrôles, retours à la ligne, marques de sens d'écriture : jamais dans le JSON ; longueurs bornées."""
        nom = "nc-essai-x" + chr(0x202E) + "y" + chr(10) + "z" + chr(0x2066)
        p = self.processus(nom, DORMIR, "a" * 500 + chr(9) + chr(0x1B) + "[31m" + chr(0x2028) + chr(0x202A))
        lignes = [x for x in self.json("processus", "nc-essai-x")["lignes"] if x["pid"] == p.pid]
        self.assertEqual(len(lignes), 1)
        x = lignes[0]
        for champ in ("nom", "commande"):
            self.assertFalse(invisible(x[champ]), (champ, x[champ]))
        self.assertLessEqual(len(x["nom"]), 32)
        self.assertLessEqual(len(x["commande"]), 160)
        self.assertEqual(x["nom"], "nc-essai-x y")      # comm : 15 octets, le reste coupé par le noyau

    @unittest.skipIf(os.getuid() == 0, "en root, tout processus est à nous")
    def test_pas_ceux_d_un_autre_compte(self):
        self.assertNotIn(1, [x["pid"] for x in self.json("processus", "systemd")["lignes"] + self.json("processus", "init")["lignes"]])


class Source(unittest.TestCase):
    def test_lecture_seule_sans_shell(self):
        for mot in ("kill", "pidfd", "SIGTERM", "SIGKILL", "signal", "arreter"):
            self.assertNotIn(mot, SOURCE)
        for mot in ("shell=True", "os.system", "os.popen", "Popen", '"sh"', "bash"):
            self.assertNotIn(mot, SOURCE)
        self.assertIn('[ss, "-Hltune"]', SOURCE)

    def test_recherche_en_liste_sans_arret_ni_nouveau_composant(self):
        self.assertIn('[Etat.bin + "nc-processus"].concat(r.demandeProc.port ? ["port", String(r.demandeProc.port)] : ["processus", r.demandeProc.nom])', RECHERCHE)
        self.assertEqual(RECHERCHE.count('"nc-processus"'), 1)
        bloc = RECHERCHE[RECHERCHE.index("readonly property var demandeProc"):RECHERCHE.index("function nomGuillemets")]
        for mot in ("component ", "Component {", "sh -c", "bash", "execDetached", "console.log", "import ", "suppr", "arreter", "Arrêter", "confirm"):
            self.assertNotIn(mot, bloc)
        # Les lignes s'ajoutent aux résultats ordinaires : pas de retour anticipé, et au moins 3 résultats gardés
        self.assertIn("if (cartes.length) out = cartes.concat(out.slice(0, Math.max(3, nbResultats - cartes.length)))", RECHERCHE)
        self.assertNotRegex(RECHERCHE, r"resultats = lignesProc")
        if not shutil.which("git"):
            return
        base = subprocess.run(["git", "show", "HEAD:home/.config/quickshell/nc-ile/Recherche.qml"], cwd=str(REPO), capture_output=True, text=True)
        if base.returncode == 0:
            for motif in (r"(?m)^\s*component\s", r"(?m)^import\s"):
                self.assertEqual(len(re.findall(motif, RECHERCHE)), len(re.findall(motif, base.stdout)), motif)


NODE = shutil.which("node")
PILOTE = """
const fs = require("fs"), vm = require("vm")
const src = fs.readFileSync(process.argv[2], "utf8").replace(/^\\.pragma library$/m, "")
const ctx = vm.createContext({ Date, String, parseInt })
vm.runInContext(src, ctx)
console.log(JSON.stringify(vm.runInContext(process.argv[3], ctx)))
"""


@unittest.skipUnless(NODE, "node absent")
class SaisiesJs(unittest.TestCase):
    def demande(self, q):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "pilote.js"
            p.write_text(PILOTE)
            r = subprocess.run([NODE, str(p), str(QML / "Saisies.js"), "demandeProcessus(%s)" % json.dumps(q)], capture_output=True, text=True,
                               env={"PATH": os.environ["PATH"]}, timeout=30)
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)

    def test_formes(self):
        for q, attendu in (("port 8080", {"port": 8080}), ("Port :443", {"port": 443}), ("port 1", {"port": 1}), ("port 65535", {"port": 65535}),
                           ("processus firefox", {"nom": "firefox"}), ("Processus nc-x.y_z", {"nom": "nc-x.y_z"}),
                           ("port 0", None), ("port 65536", None), ("port 80;id", None), ("port 99999", None), ("port", None), ("port abc", None),
                           ("port 80 90", None), ("portail 80", None), ("processus $(id)", None), ("processus ../", None),
                           ("processus " + "a" * 33, None), ("processus a b", None), ("process monitor", None), ("process firefox", None),
                           ("ps mot", None), ("ps", None), ("firefox", None)):
            with self.subTest(q):
                self.assertEqual(self.demande(q), attendu)


SHELL = '''import QtQuick
import Quickshell
ShellRoot {
 id: racine
 property int etape: 0
 property int attente: 0
 function trouver(item,nom){if(item.objectName===nom)return item;for(var i=0;i<item.children.length;i++){var r=trouver(item.children[i],nom);if(r)return r}return null}
 function verifier(ok,message){if(!ok){console.error(message);Qt.exit(2);throw new Error(message)}}
 function titres(){ return spot.resultats.map(x => x.titre) }
 FloatingWindow { id: fen; visible: true; implicitWidth: 700; implicitHeight: 600
  Recherche { id: spot; width: 700; actif: true } }
 Timer { interval: 100; running: true; repeat: true; onTriggered: {
  var champ = trouver(spot, "nc-spotlight-champ")
  if (etape === 0) { if (spot.nomIA === "") return
   champ.text = "process monitor"; etape++; return }
  if (etape === 1) {
   if (titres().indexOf("process-notes.txt") < 0) { attente++; verifier(attente < 60, "process monitor : recherche ordinaire : " + JSON.stringify(titres())); return }
   verifier(spot.demandeProc === null, "process monitor : pas une demande")
   champ.text = "ps mot"; attente = 0; etape++; return }
  if (etape === 2) {
   attente++; if (attente < 5) return
   verifier(spot.demandeProc === null, "ps mot : pas une demande")
   champ.text = "port abc"; attente = 0; etape++; return }
  if (etape === 3) {
   attente++; if (attente < 5) return
   verifier(spot.demandeProc === null, "port abc : recherche ordinaire")
   champ.text = "processus nc-x"; attente = 0; etape++; return }
  if (etape === 4) {
   var i = titres().indexOf("nc-x · pid 4242"), f = titres().indexOf("process-notes.txt")
   if (i < 0 || f < 0) { attente++; verifier(attente < 60, "processus nc-x : la ligne ET le fichier : " + JSON.stringify(titres())); return }
   verifier(i < f, "la ligne du processus en tête")
   var x = spot.resultats[i]
   verifier(x.suppr === undefined && x.sous.indexOf("nc-x --option") === 0, "lecture seule : " + JSON.stringify(x))
   spot.valider(i, false)
   verifier(Etat.fermetures === 0 && spot.confirmer === -1, "Entrée ne fait rien")
   champ.text = "port 8080"; attente = 0; etape++; return }
  if (etape === 5) {
   if (titres().indexOf("Port 8080 · UDP") < 0) { attente++; verifier(attente < 60, "port 8080 : " + JSON.stringify(titres())); return }
   verifier(spot.resultats[titres().indexOf("Port 8080 · UDP")].sous === "Utilisé par un autre compte", "autre compte")
   verifier(titres().indexOf("nc-y · pid 5151") >= 0, "notre programme : " + JSON.stringify(titres()))
   champ.text = "port 9090"; attente = 0; etape++; return }
  if (etape === 6) {
   attente++; if (attente < 15) return
   verifier(titres().every(t => t.indexOf("9090") < 0), "sans ss : pas de ligne de ports : " + JSON.stringify(titres()))
   Qt.quit() }
 } }
 Timer { interval: 30000; running: true; onTriggered: Qt.exit(9) }
}'''

# Faux nc-processus (dash : printf, jamais echo, pour journaliser)
FAUX_PROC = r'''#!/bin/sh
printf '%s\n' "$*" >> "$HOME/appels"
case "$1 $2" in
  "processus nc-x") printf '%s\n' '{"ss": true, "lignes": [{"pid": 4242, "nom": "nc-x", "commande": "nc-x --option"}]}' ;;
  "port 8080") printf '%s\n' '{"ss": true, "lignes": [{"pid": 5151, "nom": "nc-y", "commande": "nc-y", "proto": "tcp", "port": 8080}, {"autre": true, "proto": "udp", "port": 8080}]}' ;;
  "port 9090") printf '%s\n' '{"ss": false, "lignes": []}' ;;
esac
'''
FAUX_APPS = r'''#!/bin/sh
case "$1" in
  files) printf '%s\n' '[{"name": "process-notes.txt", "path": "/home/user/process-notes.txt", "dir": false, "parent": "~"}]' ;;
  *) printf '%s\n' '[]' ;;
esac
'''


@unittest.skipUnless(shutil.which("qs"), "Quickshell absent")
class RechercheHorsEcran(unittest.TestCase):
    def test_lignes_ajoutees_aux_resultats(self):
        with tempfile.TemporaryDirectory(prefix="ncp-") as d:
            root = Path(d)
            q = root / "qml"
            shutil.copytree(QML, q)
            for sous in ("run", "cache", "state", "data", "config", "tmp"):
                (root / sous).mkdir(mode=0o700)
            (q / "Reglages.qml").write_text('pragma Singleton\nimport QtQuick\nQtObject {\n property var v: ({})\n readonly property bool iaCoupee: true\n'
                                            ' readonly property bool en: false\n function t(fr,en){return fr}\n function val(k,d){return v[k] !== undefined ? v[k] : d}\n'
                                            ' function pageActive(n){return true}\n}')
            (q / "Etat.qml").write_text('pragma Singleton\nimport QtQuick\nimport Quickshell\nQtObject {\n property string saisie: ""\n property string texteIA: ""\n'
                                        ' property bool recherche: true\n property bool nuit: false\n readonly property string bin: Quickshell.env("HOME") + "/.local/bin/"\n'
                                        ' property int fermetures: 0\n signal validerRecherche()\n'
                                        ' function faire(c) {} function fermer() { fermetures++ } function aller(p) {} function basculer(e, c) {}\n}')
            (q / "Partage.qml").write_text('pragma Singleton\nimport QtQuick\nQtObject { property bool silence: false }')
            (q / "AssistantEtat.qml").write_text('pragma Singleton\nimport QtQuick\nQtObject {function formater(t){return t} function sansReseau(t){return t}}')
            (q / "Etincelle.qml").write_text('import QtQuick\nItem {property real taille: 10; property bool tourne: false; property string agent: ""}')
            (q / "CloudEtat.qml").write_text('pragma Singleton\nimport QtQuick\nQtObject { property bool actif: false; property bool associe: false }')
            (q / "Rappels.qml").write_text('pragma Singleton\nimport QtQuick\nQtObject { property var liste: []; property bool plein: false; function analyser(p) '
                                           '{ return {ok: false, raison: "heure"} } function quand(d) { return "" } function creer(t, d) { return false } function supprimer(i) {} }')
            noms = ["Reglages", "Etat", "Partage", "AssistantEtat", "Couleurs", "Connexion", "Recherche", "Emoji", "Diagnostic", "Etincelle", "Texte", "Ico"]
            (q / "qmldir").write_text("\n".join(("singleton " if n in ("Reglages", "Etat", "Partage", "AssistantEtat", "Couleurs", "Connexion") else "") + n + " 1.0 " + n + ".qml"
                                                for n in noms) + "\nsingleton CloudEtat 1.0 CloudEtat.qml\nsingleton Rappels 1.0 Rappels.qml")
            b = root / ".local/bin"
            b.mkdir(parents=True)
            scripts = {"nc-apps": FAUX_APPS, "hyprctl": "#!/bin/sh\nprintf '%s\\n' '[]'\n", "nc-aide-config": "#!/bin/sh\nexit 0\n",
                       "nc-demander": '#!/bin/sh\ncase "$1" in --ia) printf \'%s\\n\' \'{"nom": "-", "agent": "claude", "coupee": true}\' ;; esac\n',
                       "nc-processus": FAUX_PROC, "nc-logiciels": "#!/bin/sh\nprintf '%s\\n' '[]'\n", "qalc": "#!/bin/sh\nexit 0\n"}
            for nom, code in scripts.items():
                (b / nom).write_text(code)
                (b / nom).chmod(0o755)
            (q / "shell.qml").write_text(SHELL)
            env = dict(os.environ, HOME=d, XDG_CONFIG_HOME=str(root / "config"), XDG_CACHE_HOME=str(root / "cache"),
                       XDG_STATE_HOME=str(root / "state"), XDG_DATA_HOME=str(root / "data"), XDG_RUNTIME_DIR=str(root / "run"),
                       TMPDIR=str(root / "tmp"), QT_QPA_PLATFORM="offscreen", QT_QUICK_BACKEND="software",
                       PATH=str(b) + os.pathsep + os.environ["PATH"])
            for k in ("WAYLAND_DISPLAY", "HYPRLAND_INSTANCE_SIGNATURE", "DISPLAY"):
                env.pop(k, None)
            r = subprocess.run(["qs", "--no-color", "-p", str(q / "shell.qml")], env=env, text=True, capture_output=True, timeout=60,
                               stdin=subprocess.DEVNULL)
            sortie = r.stdout + r.stderr
            self.assertEqual(r.returncode, 0, sortie)
            for erreur in ("ReferenceError", "TypeError", "is not a type", "Binding loop"):
                self.assertNotIn(erreur, sortie)
            appels = (root / "appels").read_text(encoding="utf-8").splitlines()
            self.assertEqual(sorted(set(appels)), ["port 8080", "port 9090", "processus nc-x"], "rien pour process, ps ni port abc")


if __name__ == "__main__":
    unittest.main()

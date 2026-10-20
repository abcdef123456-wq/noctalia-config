"""Presse-papiers de l'île : capture (nc-presse-capture avec un faux wl-paste : secrets exclus, texte, image privée),
historique gardé d'une session à l'autre et borné (50 textes, 12 images), épinglés, recherche, filtres, suppression,
clavier, recopie et collage brut (faux wl-copy et hyprctl). HOME et XDG_STATE_HOME isolés."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import textwrap
import unittest

REPO = Path(__file__).resolve().parents[1]
QML = REPO / "home/.config/quickshell/nc-ile"
BIN = REPO / "home/.local/bin"
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 1200

FAUX_WL_PASTE = """#!/bin/sh
# --list-types : les types du faux presse-papiers ; -t image/png : le PNG ; -t text : le texte
case "$1" in
  --list-types) printf '%s\\n' "$NC_TEST_TYPES" ;;
  -t) if [ "$2" = image/png ]; then cat "$NC_TEST_PNG"; else printf '%s' "$NC_TEST_TEXTE"; fi ;;
  --no-newline) printf '%s' "$NC_TEST_TEXTE" ;;
esac
"""


class Capture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        (self.home / "bin").mkdir()
        (self.home / "bin/wl-paste").write_text(FAUX_WL_PASTE)
        (self.home / "bin/wl-paste").chmod(0o755)
        (self.home / "image.png").write_bytes(PNG)

    def capturer(self, types, texte=""):
        env = dict(HOME=str(self.home), XDG_STATE_HOME=str(self.home / "state"), NC_ILE_MEMO=str(BIN / "nc-ile-memo"),
                   NC_TEST_TYPES=types, NC_TEST_TEXTE=texte, NC_TEST_PNG=str(self.home / "image.png"),
                   PATH=str(self.home / "bin") + os.pathsep + "/usr/bin:/bin")
        r = subprocess.run([str(BIN / "nc-presse-capture")], env=env, capture_output=True, text=True, timeout=10)
        self.assertEqual((r.returncode, r.stderr), (0, ""))
        return r.stdout

    def test_texte_image_et_secrets(self):
        self.assertEqual(self.capturer("text/plain;charset=utf-8\nUTF8_STRING", "bonjour\nle monde"), "T:bonjour\x1fle monde\n")
        self.assertEqual(self.capturer("text/plain\nx-kde-passwordManagerHint", "m0t-de-passe"), "", "mot de passe exclu")
        self.assertEqual(self.capturer("x-nc-secret\ntext/plain", "secret"), "")
        sortie = self.capturer("image/png\ntext/html")
        self.assertTrue(sortie.startswith("I:" + str(len(PNG)) + ":"), sortie)
        ident, chemin = sortie.strip().split(":")[2:4]
        self.assertEqual(Path(chemin), self.home / "state/nc/ile/images" / (ident + ".png"))
        self.assertEqual(Path(chemin).stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.capturer("application/x-autre"), "", "type inconnu ignoré")


@unittest.skipUnless(shutil.which("qs"), "Quickshell requis")
class Page(unittest.TestCase):
    def executer(self, scenario, memo=None, lignes=(), fichiers=()):
        with tempfile.TemporaryDirectory(prefix="nc-presse-") as d:
            root = Path(d)
            (root / "run").mkdir(mode=0o700)
            bin = root / ".local/bin"
            bin.mkdir(parents=True)
            shutil.copy2(BIN / "nc-ile-memo", bin / "nc-ile-memo")
            # Faux wl-paste --watch : émet les lignes de capture données, puis attend ; faux wl-copy et hyprctl : journal
            (bin / "wl-paste").write_text("#!/bin/sh\nsleep 0.3\nfor n in $(cat \"$HOME/fichiers\" 2>/dev/null); do cp \"$HOME/image.png\" \"$HOME/.local/state/nc/ile/images/$n.png\"; done\ncat \"$HOME/lignes\"\nsleep 30\n")
            (root / "image.png").write_bytes(PNG)
            (bin / "wl-copy").write_text('#!/usr/bin/env python3\nimport json,os,sys\nfrom pathlib import Path\nwith Path(os.environ["HOME"],"copies").open("a") as f:f.write(json.dumps(dict(argv=sys.argv[1:],stdin=sys.stdin.read() if not sys.stdin.isatty() and "--" not in sys.argv else ""))+"\\n")\n')
            (bin / "hyprctl").write_text("#!/bin/sh\necho \"$*\" >> \"$HOME/hyprctl\"\n")
            for n in ("wl-paste", "wl-copy", "hyprctl"):
                (bin / n).chmod(0o755)
            images = root / ".local/state/nc/ile/images"
            images.mkdir(parents=True, mode=0o700)
            (root / "fichiers").write_text("".join(n + "\n" for n in fichiers))
            # Une image orpheline d'une session passée (vieille de dix minutes) : purgée au démarrage
            orpheline = images / "orpheline.png"
            orpheline.write_bytes(PNG)
            os.utime(orpheline, (orpheline.stat().st_mtime - 600,) * 2)
            (root / "lignes").write_text("".join(l.replace("@IMAGES@", str(images)) + "\n" for l in lignes))
            if memo is not None:
                for e in memo.get("entrees", []):
                    if isinstance(e, dict) and e.get("genre") == "image" and e.get("id"):
                        e["chemin"] = str(images / (e["id"] + ".png"))
                        Path(e["chemin"]).write_bytes(PNG)
                (images.parent / "presse.json").write_text(json.dumps(memo))
            for nom in ("Presse.qml", "PressePapiers.qml", "Memo.qml", "Defilement.qml", "Texte.qml", "Ico.qml", "Couleurs.qml"):
                shutil.copy2(QML / nom, root / nom)
            (root / "Reglages.qml").write_text('pragma Singleton\nimport QtQuick\nQtObject {readonly property bool en: true; function t(fr,en){return en} function val(k,d){return d}}')
            (root / "Etat.qml").write_text('pragma Singleton\nimport QtQuick\nQtObject {property var hauteurs: ({}); property int fermetures: 0; function annoncerHauteur(n,h){var t=Object.assign({},hauteurs);t[n]=Math.round(h);hauteurs=t} function fermer(){fermetures++}}')
            (root / "qmldir").write_text("\n".join(
                ("singleton " if n in ("PressePapiers", "Memo", "Couleurs", "Reglages", "Etat") else "") + n + " 1.0 " + n + ".qml"
                for n in ("Presse", "PressePapiers", "Memo", "Defilement", "Texte", "Ico", "Couleurs", "Reglages", "Etat")))
            (root / "shell.qml").write_text(textwrap.dedent('''\
                import QtQuick
                import QtQuick.Window
                import QtTest
                import Quickshell
                ShellRoot {
                    id: test
                    property int etape: 0
                    property bool dansEtape: false
                    property var page: null
                    property var memo: ({})
                    TestCase { id: clavier; name: "PresseClavier"; when: false }
                    function verifier(ok, message) { if (!ok) { console.error(message); Qt.exit(2); throw new Error(message) } }
                    function trouver(item, nom) { if (item.objectName === nom) return item; for (var i = 0; i < item.children.length; i++) { var r = trouver(item.children[i], nom); if (r) return r } return null }
                    function cliquer(nom) { var it = trouver(page, nom); verifier(it !== null, nom + " absent"); for (var i = 0; i < it.children.length; i++) if (it.children[i].clicked !== undefined) { it.children[i].clicked(null); return } verifier(false, nom + " sans zone de clic") }
                    function creer() { var c = Qt.createComponent("Presse.qml"); verifier(c.status === Component.Ready, c.errorString()); page = c.createObject(w.contentItem, { width: 400, height: 560, visible: false }); verifier(page !== null, "page absente"); page.visible = true }
                    Window { id: w; visible: true; width: 432; height: 600; color: "#151f2b" }
                    Timer { interval: 100; running: true; repeat: true; onTriggered: {
                        if (test.dansEtape) return
                        test.dansEtape = true
                        try {
                ''') + scenario + textwrap.dedent('''
                        } finally { test.dansEtape = false }
                    } }
                    Timer { interval: 12000; running: true; onTriggered: Qt.exit(9) }
                }'''))
            env = dict(os.environ, HOME=d, QT_QPA_PLATFORM="offscreen", QT_QUICK_BACKEND="software",
                       XDG_RUNTIME_DIR=str(root / "run"), XDG_CACHE_HOME=str(root / "cache"), XDG_STATE_HOME=str(root / ".local/state"),
                       XDG_CONFIG_HOME=str(root / ".config"), PATH=str(bin) + os.pathsep + os.environ["PATH"])
            env.pop("WAYLAND_DISPLAY", None)
            r = subprocess.run(["qs", "--no-color", "-p", str(root / "shell.qml")], env=env, capture_output=True, text=True, timeout=16)
            sortie = r.stdout + r.stderr
            self.assertEqual(r.returncode, 0, sortie)
            for e in ("ReferenceError", "TypeError", "Cannot assign", "Binding loop", "is not a type"):
                self.assertNotIn(e, sortie)
            f = root / ".local/state/nc/ile/presse.json"
            copies = root / "copies"
            return dict(memo=json.loads(f.read_text()) if f.exists() else None,
                        copies=[json.loads(l) for l in copies.read_text().splitlines()] if copies.exists() else [],
                        hyprctl=(root / "hyprctl").read_text().splitlines() if (root / "hyprctl").exists() else [],
                        images=sorted(p.name for p in images.iterdir()))

    def test_capture_bornee_et_gardee(self):
        lignes = ["T:texte " + str(i) for i in range(53)] + ["I:1208:img%02d:@IMAGES@/img%02d.png" % (i, i) for i in range(14)] + ["T:texte 52", "T:  ", "I:mal formée"]
        r = self.executer('''
if (etape === 0) { creer(); etape++; return }
if (!PressePapiers.prete) return
if (etape === 1 && PressePapiers.liste.length < 62) return
if (etape === 1) {
    verifier(PressePapiers.liste.length === 62, "bornes : " + PressePapiers.liste.length)
    var textes = PressePapiers.liste.filter(e => e.genre === "texte"), images = PressePapiers.liste.filter(e => e.genre === "image")
    verifier(textes.length === 50 && images.length === 12, "50 textes et 12 images : " + textes.length + " / " + images.length)
    verifier(textes[0].texte === "texte 52" && textes[1].texte === "texte 51" && textes[49].texte === "texte 3", "les plus anciens partent, un doublon remonte : " + textes[0].texte + " … " + textes[49].texte)
    verifier(images[0].id === "img13" && images[11].id === "img02", "images les plus anciennes parties : " + images[11].id)
    verifier(page.visibles.length === 62 && Etat.hauteurs.presse > 200, "page")
    etape++
} else if (etape === 2 && Memo.enAttente === 0 && Memo.courant === null) { Qt.quit() }
''', lignes=lignes, fichiers=["img%02d" % i for i in range(14)])
        self.assertEqual(len(r["memo"]["entrees"]), 62)
        self.assertEqual(r["images"], sorted("img%02d.png" % i for i in range(2, 14)), "les deux images évincées et l'orpheline sont supprimées")

    def test_epingles_recherche_filtres_suppression_clavier(self):
        memo = {"entrees": [
            {"id": "t1", "genre": "texte", "texte": "bonjour le monde", "t": 1000, "epingle": False},
            {"id": "t2", "genre": "texte", "texte": "une " + "longue ligne " * 20, "t": 2000, "epingle": False},
            {"id": "t3", "genre": "texte", "texte": "épinglé ancien", "t": 500, "epingle": True},
            {"id": "i1", "genre": "image", "chemin": "", "octets": 1208, "t": 1500, "epingle": False},
        ]}
        r = self.executer('''
if (etape === 0) { creer(); etape++; return }
if (!PressePapiers.prete) return
if (etape === 1) {
    verifier(PressePapiers.liste.map(e => e.id).join() === "t3,t2,i1,t1", "épinglé d'abord puis récents : " + PressePapiers.liste.map(e => e.id).join())
    verifier(page.longue(PressePapiers.liste[1]) && !page.longue(PressePapiers.liste[3]), "texte long reconnu")
    cliquer("nc-presse-t2-deplier"); verifier(page.deplies.t2 === true, "déplier")
    trouver(page, "nc-presse-recherche").text = "BONJOUR"
    verifier(page.visibles.map(e => e.id).join() === "t1", "recherche : " + page.visibles.map(e => e.id).join())
    trouver(page, "nc-presse-recherche").text = ""
    cliquer("nc-presse-filtre-images"); verifier(page.visibles.map(e => e.id).join() === "i1", "filtre images")
    cliquer("nc-presse-filtre-textes"); verifier(page.visibles.map(e => e.id).join() === "t3,t2,t1", "filtre textes")
    cliquer("nc-presse-filtre-tout")
    cliquer("nc-presse-t1-epingler"); verifier(PressePapiers.liste.map(e => e.id).join() === "t1,t3,t2,i1", "épingler t1 : " + PressePapiers.liste.map(e => e.id).join())
    page.forceActiveFocus(); clavier.keyClick(Qt.Key_Down); clavier.keyClick(Qt.Key_Down); verifier(page.choix === 1, "flèches")
    clavier.keyClick(Qt.Key_Return)
    clavier.keyClick(Qt.Key_Down); clavier.keyClick(Qt.Key_Delete)
    verifier(PressePapiers.liste.map(e => e.id).join() === "t1,t3,i1", "Suppr : " + PressePapiers.liste.map(e => e.id).join())
    cliquer("nc-presse-t1-coller")
    verifier(Etat.fermetures === 1, "coller ferme l'île")
    cliquer("nc-presse-effacer"); verifier(PressePapiers.liste.map(e => e.id).join() === "t1,t3", "Effacer garde les épinglés")
    etape++
} else if (etape === 2 && Memo.enAttente === 0 && Memo.courant === null) { Qt.quit() }
''', memo=memo)
        self.assertEqual([e["id"] for e in r["memo"]["entrees"]], ["t1", "t3"])
        self.assertEqual(r["copies"][0]["argv"], ["-t", "text/plain", "--", "épinglé ancien"], "Entrée recopie le choix en texte brut")
        self.assertEqual(r["copies"][-1]["argv"], ["-t", "text/plain", "--", "bonjour le monde"])
        self.assertEqual(r["images"], [], "image supprimée avec son fichier, orpheline purgée au démarrage")

    def test_image_disparue_ignoree(self):
        r = self.executer('''
if (etape === 0) { creer(); etape++; return }
if (!PressePapiers.prete) return
verifier(PressePapiers.liste.length === 1 && PressePapiers.liste[0].id === "t1", "entrées invalides ignorées : " + PressePapiers.liste.length)
Qt.quit()
''', memo={"entrees": [{"id": "t1", "genre": "texte", "texte": "ok", "t": 1}, {"genre": "texte", "texte": "  "}, {"genre": "image"}, None, 5]})
        self.assertEqual(r["images"], [], "orpheline purgée")


if __name__ == "__main__":
    unittest.main()

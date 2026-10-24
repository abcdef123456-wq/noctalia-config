"""Logiciels à installer : nc-logiciels (recherche dans les dépôts, l'AUR et Flatpak, avec de faux pacman, paru, flatpak
et une fausse API de l'AUR ; commande d'installation sûre) et le Spotlight réel hors écran (préfixe « + », suggestions
en bas pendant la frappe, Entrée qui lance l'installation)."""
from http.server import BaseHTTPRequestHandler, HTTPServer
import gzip
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
import unittest

REPO = Path(__file__).resolve().parents[1]
BIN = REPO / "home/.local/bin"
QML = REPO / "home/.config/quickshell/nc-ile"

FAUX_PACMAN = r"""#!/bin/sh
case "$1" in
  -Ss) cat <<'FIN'
extra/obs-studio 32.0.1-1
    Free, open source software for live streaming and recording
extra/obsidian 1.9.14-1 [installed]
    A powerful knowledge base that works on top of a local folder of plain text Markdown files
extra/obs-studio-plugin-browser 32.0.1-1
    Browser source plugin for OBS Studio
extra/libobs-dev 1.0-1
    Development files
FIN
  ;;
  -Qq) echo obsidian ;;
esac
"""
FAUX_FLATPAK = """#!/bin/sh
case "$1" in
  search) printf 'com.obsproject.Studio\\tOBS Studio\\tLive streaming and video recording software\\t32.0.1\\tflathub\\n' ;;
  list) ;;
esac
"""


class AUR(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        corps = json.dumps({"resultcount": 2, "results": [
            {"Name": "obs-studio-browser", "Version": "32.0-1", "Description": "OBS with browser", "Popularity": 3.2},
            {"Name": "bad name;rm", "Version": "1", "Description": "obs piège", "Popularity": 99}]}).encode()
        self.send_response(200); self.end_headers(); self.wfile.write(corps)


class Logiciels(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        self.bin = self.home / "bin"; self.bin.mkdir()
        for nom, code in (("pacman", FAUX_PACMAN), ("paru", "#!/bin/sh\necho \"paru $*\" >> \"$HOME/appels\"\n"), ("flatpak", FAUX_FLATPAK)):
            (self.bin / nom).write_text(code); (self.bin / nom).chmod(0o755)
        for outil in ("sh", "env", "python3", "cat", "printf"):
            if shutil.which(outil):
                (self.bin / outil).symlink_to(shutil.which(outil))
        self.serveur = HTTPServer(("127.0.0.1", 0), AUR)
        threading.Thread(target=self.serveur.serve_forever, daemon=True).start()
        self.addCleanup(self.serveur.shutdown)
        (self.home / ".config/nc").mkdir(parents=True)
        self.env = dict(HOME=str(self.home), PATH=str(self.bin), NC_LANGUE="fr",
                        NC_AUR_RPC=f"http://127.0.0.1:{self.serveur.server_port}/rpc/v5/search/")

    def lancer(self, *args):
        return subprocess.run([str(BIN / "nc-logiciels"), *args], env=self.env, capture_output=True, text=True, timeout=20)

    def test_recherche_complete_et_rapide(self):
        r = self.lancer("chercher", "obs")
        self.assertEqual(r.returncode, 0, r.stderr)
        res = json.loads(r.stdout)
        noms = [(x["nom"], x["source"]) for x in res]
        self.assertEqual(noms[0], ("obsidian", "depot"), "dépôt, nom qui commence par la saisie, en tête")
        self.assertIn(("obs-studio", "depot"), noms)
        self.assertIn(("obs-studio-browser", "aur"), noms, "AUR avec paru")
        self.assertIn(("com.obsproject.Studio", "flatpak"), noms)
        self.assertNotIn("bad name;rm", [x["nom"] for x in res], "un nom invalide venu de l'AUR est écarté")
        self.assertTrue(next(x for x in res if x["nom"] == "obsidian")["installe"])
        self.assertLess(noms.index(("libobs-dev", "depot")), len(noms))
        self.assertGreater(noms.index(("libobs-dev", "depot")), noms.index(("obs-studio", "depot")), "les bibliothèques passent après")
        rapide = [x["source"] for x in json.loads(self.lancer("chercher", "obs", "--rapide").stdout)]
        self.assertEqual(set(rapide), {"depot"}, "--rapide : les dépôts de la distribution seulement")
        (self.home / ".config/nc/reglages.conf").write_text("SPOTLIGHT_AUR=non\nSPOTLIGHT_FLATPAK=non\n")
        self.assertEqual({x["source"] for x in json.loads(self.lancer("chercher", "obs").stdout)}, {"depot"}, "réglages respectés")

    def test_icones_catalogues_flatpak_et_theme(self):
        sw = self.home / "sw"
        # Catalogue XML (Arch, Fedora, openSUSE) et son icône en cache
        (sw / "xml").mkdir(parents=True)
        with gzip.open(sw / "xml/extra.xml.gz", "wt") as f:
            f.write('<?xml version="1.0"?><components origin="archlinux-arch-extra"><component type="desktop-application">'
                    '<id>com.obsproject.Studio</id><pkgname>obs-studio</pkgname><icon type="cached" width="64" height="64">'
                    'com.obsproject.Studio.png</icon></component></components>')
        (sw / "icons/archlinux-arch-extra/64x64").mkdir(parents=True)
        (sw / "icons/archlinux-arch-extra/64x64/com.obsproject.Studio.png").write_bytes(b"png")
        # Catalogue YAML DEP-11 (Debian, Ubuntu)
        deb = self.home / "deb"; (deb / "yaml").mkdir(parents=True)
        with gzip.open(deb / "yaml/main.yml.gz", "wt") as f:
            f.write("---\nFile: DEP-11\nOrigin: debian-trixie-main\n---\nType: desktop-application\nID: org.gimp.GIMP\n"
                    "Package: gimp\nIcon:\n  cached:\n  - name: gimp_gimp.png\n    width: 64\n    height: 64\n  stock: gimp\n")
        (deb / "icons/debian-trixie-main/64x64").mkdir(parents=True)
        (deb / "icons/debian-trixie-main/64x64/gimp_gimp.png").write_bytes(b"png")
        # Icône Flatpak déjà téléchargée par Flatpak
        fp = self.home / "fp/flathub/x86_64/active/icons/128x128"; fp.mkdir(parents=True)
        (fp / "com.obsproject.Studio.png").write_bytes(b"png")
        self.env.update(NC_SWCATALOG_DIRS=f"{sw}:{deb}", NC_FLATPAK_APPSTREAM=str(self.home / "fp"), XDG_CACHE_HOME=str(self.home / "cache"))
        res = {(x["nom"], x["source"]): x for x in json.loads(self.lancer("chercher", "obs").stdout)}
        self.assertTrue(res[("obs-studio", "depot")]["icone"].endswith("archlinux-arch-extra/64x64/com.obsproject.Studio.png"))
        self.assertTrue(res[("com.obsproject.Studio", "flatpak")]["icone"].endswith("128x128/com.obsproject.Studio.png"))
        self.assertEqual(res[("obs-studio-browser", "aur")]["icone"], "", "pas de catalogue pour l'AUR")
        self.assertIn("obs", res[("obs-studio-browser", "aur")]["noms_icone"], "noms à chercher dans le thème")
        cache = json.loads((self.home / "cache/nc/logiciels-icones.json").read_text())
        self.assertTrue(cache["index"]["gimp"].endswith("debian-trixie-main/64x64/gimp_gimp.png"), "YAML DEP-11 lu")
        # Cache réutilisé tant que les catalogues ne changent pas ; refait quand l'un change
        (self.home / "cache/nc/logiciels-icones.json").write_text(json.dumps(dict(cache, index={"obs-studio": "/marque"})))
        res = {(x["nom"], x["source"]): x for x in json.loads(self.lancer("chercher", "obs").stdout)}
        self.assertEqual(res[("obs-studio", "depot")]["icone"], "/marque", "le cache sert")
        os.utime(sw / "xml/extra.xml.gz", (1, 1))
        res = {(x["nom"], x["source"]): x for x in json.loads(self.lancer("chercher", "obs").stdout)}
        self.assertTrue(res[("obs-studio", "depot")]["icone"].endswith("com.obsproject.Studio.png"), "catalogue changé : index refait")
        z = [x for x in json.loads(self.lancer("chercher", "zen-browser-bin").stdout)]
        self.assertTrue(all(isinstance(x["noms_icone"], list) for x in z))

    def test_installation_sure(self):
        # Le terminal d'installation lance la bonne commande, avec le nom en argument (jamais dans un shell)
        r = subprocess.run([str(BIN / "nc-logiciels"), "terminal", "aur", "obs-studio-browser"], env=self.env, input="\n",
                           capture_output=True, text=True, timeout=20)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual((self.home / "appels").read_text().split("\n")[0], "paru -S -- obs-studio-browser")
        for mauvais in ("obs;rm -rf ~", "$(id)", "a b"):
            self.assertEqual(self.lancer("installer", "depot", mauvais).returncode, 1, mauvais)
        self.assertEqual(self.lancer("installer", "ailleurs", "obs").returncode, 1)


@unittest.skipUnless(shutil.which("qs"), "Quickshell requis")
class Spotlight(unittest.TestCase):
    def test_plus_et_suggestions_et_installation(self):
        with tempfile.TemporaryDirectory(prefix="nc-spotlight-") as d:
            root = Path(d); shutil.copytree(QML, root / "qml"); (root / "runtime").mkdir(mode=0o700)
            q = root / "qml"
            (q / "Reglages.qml").write_text('pragma Singleton\nimport QtQuick\nQtObject {property bool iaCoupee: false; function t(fr,en){return fr} function val(k,d){return d} function pageActive(n){return true}}')
            (q / "Etat.qml").write_text('''pragma Singleton
import QtQuick
import Quickshell
QtObject {
 property string saisie: ""
 property bool recherche: true
 property bool nuit: false
 property string ecranOuvert: "TEST"
 readonly property string bin: Quickshell.env("HOME") + "/.local/bin/"
 property int fermetures: 0
 signal validerRecherche()
 function faire(c) {} function fermer() { fermetures++ } function aller(p) {} function basculer(e, c) {}
 function basculerCafe() {} function lancerPomodoro() {}
}''')
            (q / "AssistantEtat.qml").write_text('pragma Singleton\nimport QtQuick\nQtObject {function formater(t){return t}}')
            (q / "Etincelle.qml").write_text('import QtQuick\nItem {property real taille: 10; property bool tourne: false; property string agent: ""}')
            noms = ["Reglages", "Etat", "AssistantEtat", "Couleurs", "Connexion", "Recherche", "Diagnostic", "Etincelle", "Texte", "Ico"]
            (q / "qmldir").write_text("\n".join(("singleton " if n in ("Reglages", "Etat", "AssistantEtat", "Couleurs", "Connexion") else "") + n + " 1.0 " + n + ".qml" for n in noms))
            b = root / ".local/bin"; b.mkdir(parents=True)
            scripts = {
                "nc-apps": '#!/bin/sh\ncase "$1" in list) echo \'[{"id":"obsidian.desktop","name":"Obsidian","generic":"Notes","keywords":"","icon":"obsidian","exe":"obsidian"}]\' ;; *) echo "[]" ;; esac\n',
                "nc-demander": "#!/bin/sh\necho Claude\n",
                "nc-logiciels": '''#!/bin/sh
echo "$*" >> "$HOME/appels"
case "$1" in
  chercher) case "$2" in
    zen) echo '[{"source":"aur","depot":"aur","nom":"zen-browser-bin","version":"1","description":"Zen","installe":false,"score":95,"icone":"/tmp/zen.png","noms_icone":["zen-browser"]}]' ;;
    obs) echo '[{"source":"depot","depot":"extra","nom":"obsidian","version":"1","description":"Notes","installe":true,"score":96},{"source":"depot","depot":"extra","nom":"obs-studio","version":"32","description":"Streaming","installe":false,"score":96}]' ;;
    *) echo '[]' ;;
  esac ;;
esac
''',
                "hyprctl": "#!/bin/sh\necho '[]'\n",
            }
            for nom, code in scripts.items():
                (b / nom).write_text(code); (b / nom).chmod(0o755)
            (q / "shell.qml").write_text('''import QtQuick
import Quickshell
ShellRoot {
 id: racine
 property int etape: 0
 property var rech: null
 function trouver(item,nom){if(item.objectName===nom)return item;for(var i=0;i<item.children.length;i++){var r=trouver(item.children[i],nom);if(r)return r}return null}
 function verifier(ok,message){if(!ok){console.error(message);Qt.exit(2);throw new Error(message)}}
 FloatingWindow { id: fen; visible: true; implicitWidth: 700; implicitHeight: 500
  Recherche { id: spot; width: 700; actif: true } }
 Timer { interval: 100; running: true; repeat: true; onTriggered: {
  var champ = trouver(spot, "nc-spotlight-champ")
  if (etape === 0) { verifier(champ !== null, "champ absent"); champ.text = "+zen"; etape++; return }
  if (etape === 1) { if (spot.paquetsPour !== "zen") return
   verifier(spot.resultats.length === 1 && spot.resultats[0].titre === "zen-browser-bin", "« +zen » : " + JSON.stringify(spot.resultats.map(x => x.titre)))
   verifier(spot.resultats[0].sous.indexOf("AUR") === 0, "origine AUR affichée")
   verifier(spot.resultats[0].icone === "file:///tmp/zen.png", "icône du catalogue affichée : " + spot.resultats[0].icone)
   spot.valider(0, false); verifier(Etat.fermetures === 1, "Entrée ferme l'île"); champ.text = "obs"; etape++; return }
  if (etape === 2) { if (spot.paquetsPour !== "obs" || spot.applis.length === 0) return
   var t = spot.resultats.map(x => x.titre)
   verifier(t[0] === "Obsidian", "l'appli installée reste en tête : " + JSON.stringify(t))
   verifier(t.indexOf("obs-studio") >= 0 && t.indexOf("obsidian") < 0, "suggestion en bas, sans le paquet déjà installé : " + JSON.stringify(t))
   verifier(spot.resultats.length <= 6, "six lignes au plus"); Qt.quit() }
 } }
 Timer { interval: 9000; running: true; onTriggered: Qt.exit(9) }
}''')
            env = dict(os.environ, HOME=d, QT_QPA_PLATFORM="offscreen", QT_QUICK_BACKEND="software", XDG_RUNTIME_DIR=str(root / "runtime"),
                       XDG_CACHE_HOME=str(root / "cache"), PATH=str(b) + os.pathsep + os.environ["PATH"])
            env.pop("WAYLAND_DISPLAY", None)
            r = subprocess.run(["qs", "--no-color", "-p", str(q / "shell.qml")], env=env, text=True, capture_output=True, timeout=15)
            sortie = r.stdout + r.stderr
            self.assertEqual(r.returncode, 0, sortie)
            for erreur in ("ReferenceError", "TypeError", "is not a type"):
                self.assertNotIn(erreur, sortie)
            appels = (root / "appels").read_text().splitlines()
            self.assertIn("chercher zen --max 12", appels, "« + » : recherche complète")
            self.assertIn("installer aur zen-browser-bin", appels, "Entrée installe")
            self.assertIn("chercher obs --rapide --max 6", appels, "sans préfixe : dépôts seulement")


@unittest.skipUnless(shutil.which("qs"), "Quickshell requis")
class Sobriete(unittest.TestCase):
    def test_effets_aucun_rend_l_ile_sobre_sans_couper_les_images_hors_economie(self):
        with tempfile.TemporaryDirectory(prefix="nc-sobre-") as d:
            root = Path(d); (root / "qml").mkdir(); (root / "runtime").mkdir(mode=0o700)
            shutil.copy2(QML / "Reglages.qml", root / "qml/Reglages.qml")
            (root / ".config/nc").mkdir(parents=True)
            (root / ".config/nc/reglages.conf").write_text("EFFETS=aucun\n")
            (root / "qml/qmldir").write_text("singleton Reglages 1.0 Reglages.qml\n")
            (root / "qml/shell.qml").write_text('''import QtQuick
import Quickshell
ShellRoot {
 property int essais: 0
 Timer { interval: 100; running: true; repeat: true; onTriggered: {
  if (Object.keys(Reglages.valeurs).length === 0 && ++essais < 50) return      // fichier lu en asynchrone
  if (!Reglages.sobre) { console.error("EFFETS=aucun : pas sobre"); Qt.exit(2); return }
  if (Reglages.imagesLegeres !== Reglages.economie) { console.error("images coupées hors Économie"); Qt.exit(3); return }
  Qt.quit() } }
}''')
            env = dict(os.environ, HOME=d, QT_QPA_PLATFORM="offscreen", XDG_RUNTIME_DIR=str(root / "runtime"), XDG_CACHE_HOME=str(root / "cache"))
            env.pop("WAYLAND_DISPLAY", None)
            r = subprocess.run(["qs", "--no-color", "-p", str(root / "qml/shell.qml")], env=env, text=True, capture_output=True, timeout=12)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


if __name__ == "__main__":
    unittest.main()

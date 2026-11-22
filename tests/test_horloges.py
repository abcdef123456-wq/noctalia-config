"""Horloges mondiales de la recherche de l'île (réglage HORLOGES_VILLES) : lecture de la liste (Saisies.js, évalué par node),
validation par nc-reglages, branchement dans Recherche.qml (zones en arguments, cartes devant les résultats ordinaires)
et essai du vrai qs hors écran."""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

from tests import _isolation
from tests.test_heure_ville import NODE, js, ZONES
from tests.test_liens_web import FAUX_BIN, NOMS, SINGLETONS, STUBS, QML as QML_DIR

REPO = Path(__file__).resolve().parents[1]
REGLAGES = REPO / "home/.local/bin/nc-reglages"
RECHERCHE = (QML_DIR / "Recherche.qml").read_text()
TAB = Path("/usr/share/zoneinfo/zone1970.tab")


@unittest.skipUnless(NODE, "node absent")
class Fonctions(unittest.TestCase):
    def test_declencheurs(self):
        for q in ("heure", "Heure", "horloges", "horloge", "clocks", "clock", "world clock", "World  Clocks", " heure "):
            self.assertTrue(js(f"demandeHorloges({json.dumps(q)})"), q)
        for q in ("heure tokyo", "horlogerie", "time", "clocks x", "", "heures"):
            self.assertFalse(js(f"demandeHorloges({json.dumps(q)})"), q)

    def test_lecture_de_la_liste(self):
        self.assertEqual(js('villesHorloges("Tokyo, New York ,Paris")'), ["Tokyo", "New York", "Paris"])
        self.assertEqual(js('villesHorloges("")'), [])
        # un nom avec chiffre ou trop court est ignoré
        self.assertEqual(js('villesHorloges("Tokyo, a, Paris2, Rome")'), ["Tokyo", "Rome"])

    def test_huit_villes_au_plus(self):
        self.assertEqual(len(js('villesHorloges("aa,bb,cc,dd,ee,ff,gg,hh,ii,jj")')), 8)

    def test_zones_prises_dans_la_liste_seulement(self):
        r = js(f"zonesHorloges(['Tokyo', 'Atlantide', 'New York'], {json.dumps(ZONES)})")
        self.assertEqual([x["zone"] for x in r], ["Asia/Tokyo", "America/New_York"])
        self.assertEqual(js(f"zonesHorloges([], {json.dumps(ZONES)})"), [])


class Reglage(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.TemporaryDirectory(prefix="nch-")
        self.addCleanup(self.t.cleanup)
        self.d = Path(self.t.name)

    def nc(self, *args):
        d = self.d
        env = {"PATH": os.environ["PATH"], "HOME": str(d), "XDG_CONFIG_HOME": str(d / "config"), "XDG_CACHE_HOME": str(d / "cache"),
               "XDG_STATE_HOME": str(d / "state"), "XDG_DATA_HOME": str(d / "data"), "TMPDIR": str(d), "NC_LANGUE": "fr"}
        return subprocess.run(["python3", "-I", str(REGLAGES), *args], env=env, text=True, capture_output=True, timeout=30,
                              stdin=subprocess.DEVNULL)

    def ecrit(self):
        return any("HORLOGES_VILLES" in p.read_text(errors="replace") for p in self.d.rglob("*") if p.is_file())

    def test_acceptee(self):
        r = self.nc("set", "HORLOGES_VILLES", "Tokyo,  New York, Paris")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(self.ecrit())

    def test_refus_sans_rien_ecrire(self):
        for v, mot in (("a1,b2,c3,d4".replace("1", "x").replace("2", "y").replace("3", "z").replace("4", "w") + ",ee,ff,gg,hh,ii", "8 villes"),
                       ("Tokyo, Paris2", "chiffre"), ("Tokyo,,Paris", "caractères"), ("x", "caractères"),
                       ("Tok" + chr(0x1b) + "yo", "contrôle"), ("Tok" + chr(0x202e) + "yo", "contrôle"),
                       ("Tok" + chr(0x2028) + "yo", "contrôle"), ("Tok\nyo", "ligne")):
            r = self.nc("set", "HORLOGES_VILLES", v)
            self.assertNotEqual(r.returncode, 0, repr(v))
            self.assertIn(mot, r.stderr, repr(v))
        self.assertFalse(self.ecrit())

    def test_neuf_villes_refusees(self):
        r = self.nc("set", "HORLOGES_VILLES", ",".join(["Tokyo", "Paris", "Rome", "Oslo", "Lima", "Kiev", "Riga", "Doha", "Bern"]))
        self.assertNotEqual(r.returncode, 0)
        self.assertFalse(self.ecrit())

    def test_chiffre_refuse(self):
        self.assertNotEqual(self.nc("set", "HORLOGES_VILLES", "Tokyo, 12").returncode, 0)

    def test_refus_a_distance(self):
        r = self.nc("set", "--distant", "HORLOGES_VILLES", "Tokyo")
        self.assertNotEqual(r.returncode, 0)
        self.assertFalse(self.ecrit())


class Branchement(unittest.TestCase):
    def test_zones_en_arguments_jamais_dans_le_script(self):
        m = re.search(r'lireHorloges\.command = (\[[^\n]*\]\.concat\(zs\))', RECHERCHE)
        self.assertIsNotNone(m, "commande de lireHorloges")
        cmd = m.group(1)
        self.assertIn("""'for z; do TZ="$z" date "+%H:%M|%u|%d|%m|%z"; done', "sh"]""", cmd)
        self.assertNotIn("zs", cmd.replace(".concat(zs)", ""))
        self.assertTrue(cmd.startswith('["sh", "-c", \'for z;'), cmd)

    def test_cartes_devant_sans_remplacer(self):
        m = re.search(r"if \(cartesH\.length\) out = (.*)", RECHERCHE)
        self.assertIsNotNone(m)
        self.assertRegex(m.group(1), r"^cartesH\.concat\(out\.slice\(0, Math\.max\(3, nbResultats - cartesH\.length\)\)\)$")

    def test_rien_hors_page_ni_timer_neuf(self):
        self.assertIn("if (r.horloges) {", RECHERCHE)
        self.assertEqual(RECHERCHE.count("id: lireHorloges"), 1)


@unittest.skipUnless(shutil.which("qs") and TAB.exists(), "Quickshell et zone1970.tab requis")
class HorsEcran(unittest.TestCase):
    SCRIPT = '''import QtQuick
import Quickshell
import "Saisies.js" as S
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
  if (etape === 0) { if (spot.nomIA === "" || !spot.applisLues) return
   champ.text = "horloges"; etape++; return }
  if (etape === 1) { attente++
   var t = titres()
   if (t.length < 3 || t[0].indexOf("Tokyo") < 0 || t[1].indexOf("Paris") < 0) { if (attente > 60) verifier(false, "cartes : " + JSON.stringify(t)); return }
   verifier(t.indexOf("Horloges") >= 0, "l'appli Horloges reste : " + JSON.stringify(t))
   verifier(t.indexOf("Horloges") > 1, "les cartes sont devant : " + JSON.stringify(t))
   verifier(spot.resultats[0].sous.indexOf("Heure") === 0, "sous de la carte : " + spot.resultats[0].sous)
   attente = 0; champ.text = "heure tokyo"; etape++; return }
  if (etape === 2) { attente++
   var u = titres()
   if (u.length < 1 || u[0].indexOf("Tokyo") < 0) { if (attente > 60) verifier(false, "heure tokyo : " + JSON.stringify(u)); return }
   verifier(u.filter(x => x.indexOf("Tokyo") >= 0).length === 1, "heure tokyo : une seule carte : " + JSON.stringify(u))
   console.log("FINI"); Qt.quit() }
 } }
 Timer { interval: 40000; running: true; onTriggered: Qt.exit(9) }
}'''

    def test_cartes_et_resultats_ordinaires(self):
        with tempfile.TemporaryDirectory(prefix="nq-", dir=_isolation.dossier_court()) as d:
            root = Path(d)
            q = root / "qml"
            shutil.copytree(QML_DIR, q)
            for sous in ("run", "cache", "state", "data", "config", "tmp"):
                (root / sous).mkdir(mode=0o700)
            for nom, code in STUBS.items():
                (q / (nom + ".qml")).write_text(code)
            (q / "Reglages.qml").write_text(STUBS["Reglages"].replace("property var v: ({})", 'property var v: ({"HORLOGES_VILLES": "Tokyo, Atlantide, Paris"})'))
            (q / "qmldir").write_text("\n".join(("singleton " if n in SINGLETONS else "") + n + " 1.0 " + n + ".qml" for n in NOMS)
                                      + "\nsingleton CloudEtat 1.0 CloudEtat.qml\nsingleton Rappels 1.0 Rappels.qml")
            b = root / ".local/bin"
            b.mkdir(parents=True)
            faux = dict(FAUX_BIN)
            faux["nc-apps"] = ('#!/bin/sh\ncase "$1" in list) printf \'%s\\n\' \'[{"id":"horloges.desktop","name":"Horloges","exec":"true","icon":"","comment":"","keywords":""}]\' ;; *) printf "%s\\n" "[]" ;; esac\n')
            for nom, code in faux.items():
                (b / nom).write_text(code)
                (b / nom).chmod(0o755)
            (q / "shell.qml").write_text(self.SCRIPT)
            env = dict(os.environ, HOME=d, XDG_CONFIG_HOME=str(root / "config"), XDG_CACHE_HOME=str(root / "cache"),
                       XDG_STATE_HOME=str(root / "state"), XDG_DATA_HOME=str(root / "data"), XDG_RUNTIME_DIR=str(root / "run"),
                       TMPDIR=str(root / "tmp"), QT_QPA_PLATFORM="offscreen", QT_QUICK_BACKEND="software",
                       PATH=str(b) + os.pathsep + os.environ["PATH"])
            for k in ("WAYLAND_DISPLAY", "HYPRLAND_INSTANCE_SIGNATURE", "DISPLAY", "BROWSER", "DBUS_SESSION_BUS_ADDRESS"):
                env.pop(k, None)
            r = subprocess.run(["qs", "--no-color", "-p", str(q / "shell.qml")], env=env, text=True, capture_output=True,
                               timeout=90, stdin=subprocess.DEVNULL)
            sortie = r.stdout + r.stderr
            for erreur in ("ReferenceError", "TypeError", "is not a type", "Binding loop"):
                self.assertNotIn(erreur, sortie)
            self.assertIn("FINI", sortie, sortie)
            self.assertEqual(r.returncode, 0, sortie)


if __name__ == "__main__":
    unittest.main()

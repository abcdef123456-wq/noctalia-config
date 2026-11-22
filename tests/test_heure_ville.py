"""« heure tokyo » dans le Spotlight : la ville tapée devient une zone prise UNIQUEMENT dans zone1970.tab (liste blanche),
l'heure vient de `env TZ=… date` en liste d'arguments (jamais de shell). Fonctions pures de Saisies.js évaluées par node,
puis branchement dans Recherche.qml."""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
QML = REPO / "home/.config/quickshell/nc-ile"
RECHERCHE = (QML / "Recherche.qml").read_text()
NODE = shutil.which("node")
TAB = Path("/usr/share/zoneinfo/zone1970.tab")
PILOTE = """
const fs = require("fs"), vm = require("vm")
const src = fs.readFileSync(process.argv[2], "utf8").replace(/^\\.pragma library$/m, "")
const ctx = vm.createContext({ Date, String, parseInt, Object, Math, NaN })
vm.runInContext(src, ctx)
console.log(JSON.stringify(vm.runInContext(process.argv[3], ctx)))
"""
# Un petit zone1970.tab : colonnes séparées par des tabulations, commentaires avec #
TAB_ESSAI = ("# commentaire\nJP\t+353916+1394441\tAsia/Tokyo\n"
             "US\t+404251-0740023\tAmerica/New_York\tEastern\n"
             "AR\t-3436-05827\tAmerica/Argentina/Buenos_Aires\tbuenos\n"
             "XX\t+0000+00000\tAsia/Tokyo;rm\n")
ZONES = ["Asia/Tokyo", "America/New_York", "America/Argentina/Buenos_Aires", "Europe/London"]


def js(expr):
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "pilote.js"; p.write_text(PILOTE)
        r = subprocess.run([NODE, str(p), str(QML / "Saisies.js"), expr], capture_output=True, text=True,
                           env={"PATH": os.environ["PATH"], "TZ": "UTC"}, timeout=30)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def ville(q):
    return js(f"villeHeure({json.dumps(q)})")


def zone(v, zones=ZONES):
    return js(f"zoneVille({json.dumps(v)}, {json.dumps(zones)})")


def ligne(s, v="Tokyo", douze=False, en=False, local=60):
    return js(f"ligneHeure({json.dumps(s)}, {json.dumps(v)}, {json.dumps(douze)}, {json.dumps(en)}, {local})")


@unittest.skipUnless(NODE, "node absent")
class Fonctions(unittest.TestCase):
    def test_formes_de_la_saisie(self):
        for q, v in [("heure tokyo", "tokyo"), ("heure à tokyo", "tokyo"), ("heure a Tokyo", "Tokyo"),
                     ("heure de new york", "new york"), ("time in tokyo", "tokyo"), ("time tokyo", "tokyo"),
                     ("heure d'Istanbul", "Istanbul"), ("Heure  au  Caire", "Caire")]:
            self.assertEqual(ville(q), v, q)

    def test_saisies_sans_ville(self):
        for q in ["heure", "heure ", "tokyo", "heures tokyo", "heure 12", "heure x", "time", "heure " + "a" * 41]:
            self.assertEqual(ville(q), "", q)

    def test_nom_sans_accents_ni_casse(self):
        self.assertEqual(js('nomVille("  New_York ")'), "new york")
        self.assertEqual(js('nomVille("Athènes")'), "athenes")

    def test_zones_trouvees(self):
        self.assertEqual(zone("Tokyo"), "Asia/Tokyo")
        self.assertEqual(zone("new york"), "America/New_York")
        self.assertEqual(zone("New_York"), "America/New_York")
        self.assertEqual(zone("buenos aires"), "America/Argentina/Buenos_Aires")
        self.assertEqual(zone("Londres"), "Europe/London")

    def test_alias_absent_de_la_liste(self):
        """Un nom français dont la zone n'est pas dans la liste lue : inconnue, jamais la zone de la table telle quelle."""
        self.assertEqual(zone("londres", ["Asia/Tokyo"]), "")
        self.assertEqual(zone("tokyo", []), "")

    def test_saisies_piegees(self):
        """Jamais une zone hors de la liste, jamais la saisie telle quelle."""
        for v in ["../../etc", "$(id)", "Asia/Tokyo;rm", "`id`", "Asia/Tokyo", "tokyo\nrm", "__proto__", "constructor",
                  "toString", "hasOwnProperty", "", "  ", "/etc/passwd", "Tokyo|x", "UTC"]:
            z = zone(v)
            self.assertIn(z, ZONES + [""], v)
        for v in ["../../etc", "$(id)", "Asia/Tokyo;rm", "__proto__", "constructor", "/etc/passwd"]:
            self.assertEqual(zone(v), "", v)

    def test_liste_zones(self):
        z = js(f"listeZones({json.dumps(TAB_ESSAI)})")
        self.assertEqual(z, ["Asia/Tokyo", "America/New_York", "America/Argentina/Buenos_Aires"])
        self.assertEqual(js('listeZones("")'), [])
        self.assertEqual(js("listeZones(null)"), [])

    @unittest.skipUnless(TAB.exists(), "zone1970.tab absent")
    def test_noms_francais_dans_le_vrai_fichier(self):
        zones = js(f"listeZones({json.dumps(TAB.read_text())})")
        manquantes = [k for k, v in js("ZONES_FR").items() if v not in zones]
        self.assertEqual(manquantes, [])
        for v in ["tokyo", "new york", "londres", "paris", "berlin", "montreal"]:
            self.assertNotEqual(js(f"zoneVille({json.dumps(v)}, {json.dumps(zones)})"), "", v)

    def test_ligne_24h(self):
        r = ligne("14:32|1|23|11|+0900")
        self.assertEqual(r, {"texte": "Tokyo : 14:32, lundi 23 nov.", "ecart": "+8 h"})

    def test_ligne_12h_et_anglais(self):
        self.assertEqual(ligne("14:32|1|23|11|+0900", douze=True)["texte"], "Tokyo : 2:32 PM, lundi 23 nov.")
        self.assertEqual(ligne("00:05|7|01|12|+0900", douze=True, en=True)["texte"], "Tokyo : 12:05 AM, Sunday Dec 1")
        self.assertEqual(ligne("12:00|3|05|08|+0900", douze=True)["texte"], "Tokyo : 12:00 PM, mercredi 5 août")

    def test_ecarts(self):
        self.assertEqual(ligne("10:00|1|23|11|+0530", local=60)["ecart"], "+4 h 30")
        self.assertEqual(ligne("10:00|1|23|11|-0500", local=60)["ecart"], "-6 h")
        self.assertEqual(ligne("10:00|1|23|11|+0100", local=60)["ecart"], "+0 h")
        self.assertEqual(ligne("10:00|1|23|11|+0545", local=-300)["ecart"], "+10 h 45")

    def test_sortie_inattendue(self):
        for s in ["", "date: invalid", "25:00|1|23|11|+0900", "14:32|8|23|11|+0900", "14:32|1|23|13|+0900",
                  "14:32|1|23|11|+09:00", "14:32|1|23|11|+0900\nx"]:
            self.assertIsNone(ligne(s), s)

    def test_nom_affiche(self):
        self.assertEqual(js('nomAffiche(" new york ")'), "New York")
        self.assertEqual(js("nomAffiche(\"d'istanbul\")"), "D'Istanbul")


class Branchement(unittest.TestCase):
    def test_commande_en_liste_sans_shell(self):
        m = re.search(r"lireHeure\.command = (\[[^\]]*\])", RECHERCHE)
        self.assertIsNotNone(m)
        self.assertEqual(m[1], '["env", "TZ=" + zone, "date", "+%H:%M|%u|%d|%m|%z"]')
        bloc = RECHERCHE[RECHERCHE.index("id: lireHeure"):RECHERCHE.index("id: calculer")]
        self.assertNotRegex(bloc, r'"(?:sh|bash|-c)"')

    def test_zone_prise_dans_la_liste(self):
        self.assertIn("Saisies.zoneVille(r.heureVille, r.zonesHeure)", RECHERCHE)

    def test_fichier_lu_a_la_demande_et_sans_erreur_affichee(self):
        m = re.search(r"FileView \{\s*id: fichierZones.*?\n    \}", RECHERCHE, re.S)
        self.assertIsNotNone(m)
        self.assertIn('r.zonesVoulues ? (Quickshell.env("TZDIR") || "/usr/share/zoneinfo") + "/zone1970.tab" : ""', m[0])
        self.assertIn("printErrors: false", m[0])
        self.assertIn("onLoadFailed: { r.zonesIllisibles = true", m[0])

    def test_fichier_absent_donne_ville_inconnue(self):
        self.assertRegex(RECHERCHE, r'if \(li\) out\.push[\s\S]*?else if \(zonesIllisibles \|\| zonesHeure\.length && zone === ""\)'
                                    r'\s*out\.push\(\{ titre: Reglages\.t\("Ville inconnue", "Unknown city"\)')

    def test_pas_de_releve_periodique(self):
        bloc = RECHERCHE[RECHERCHE.index("id: lireHeure"):RECHERCHE.index("id: calculer")]
        self.assertNotIn("Timer", bloc)
        self.assertNotIn("running: true", bloc)

    def test_entree_copie_le_texte(self):
        self.assertIn('Quickshell.execDetached(["wl-copy", "--", li.texte])', RECHERCHE)

    def test_tz_hors_de_l_argv_de_date(self):
        """TZ n'est qu'un argument de env : date ne reçoit que son format."""
        argv = json.loads("[" + re.search(r'lireHeure\.command = \["env", "TZ=" \+ zone, (.*?)\]', RECHERCHE)[1] + "]")
        self.assertEqual(argv, ["date", "+%H:%M|%u|%d|%m|%z"])


if __name__ == "__main__":
    unittest.main()

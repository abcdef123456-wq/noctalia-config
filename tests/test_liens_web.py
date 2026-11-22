"""Raccourcis web de la recherche de l'île (liens-web.conf) : validation et encodage (Saisies.js, évalué par node),
branchement dans Recherche.qml (qs hors écran) et gestion par « nc-reglages liens-web »."""
import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import tempfile
import unittest
import warnings
from unittest import mock

from tests import _isolation  # noqa: F401
from tests.test_spotlight_saisies import NODE, js

REPO = Path(__file__).resolve().parents[1]
QML = REPO / "home/.config/quickshell/nc-ile"
REGLAGES = REPO / "home/.local/bin/nc-reglages"
AMZ = "amz\tAmazon\thttps://www.amazon.fr/s?k=%s"


def analyse(texte):
    return js(f"analyseLiens({json.dumps(texte)})")


def prefixes(texte):
    return [x["p"] for x in analyse(texte)]


@unittest.skipUnless(NODE, "node requis")
class Pures(unittest.TestCase):
    def test_ligne_valide(self):
        self.assertEqual(analyse(AMZ + "\n"), [{"p": "amz", "nom": "Amazon", "url": "https://www.amazon.fr/s?k=%s"}])

    def test_prefixe(self):
        for p in ("G", "a b", "abcdefghijklm", "", "é"):
            self.assertEqual(prefixes(f"{p}\tN\thttps://x.fr/?q=%s"), [], repr(p))
        self.assertEqual(prefixes("abcdefghijkl\tN\thttps://x.fr/?q=%s"), ["abcdefghijkl"])

    def test_schema_de_l_url(self):
        for u in ("javascript:alert(%s)", "file:///etc/%s", "ftp://x.fr/%s", "//x.fr/%s", "https://x.fr/", "https://x.fr/%s%s",
                  "https://x.fr/ %s", "https://", "data:text/html,%s"):
            self.assertEqual(prefixes(f"abc\tN\t{u}"), [], u)
        self.assertEqual(prefixes("abc\tN\thttp://x.fr/%s"), ["abc"])

    def test_nom(self):
        self.assertEqual(prefixes("abc\t" + "n" * 41 + "\thttps://x.fr/%s"), [])
        self.assertEqual(prefixes("abc\t" + "n" * 40 + "\thttps://x.fr/%s"), ["abc"])
        self.assertEqual(prefixes("abc\t\thttps://x.fr/%s"), [])
        self.assertEqual(prefixes("abc\tn\x07n\thttps://x.fr/%s"), [])

    def test_nom_sans_sens_d_ecriture(self):
        """Contrôles, séparateurs de ligne et caractères de sens d'écriture refusés ; accents et emoji acceptés."""
        for cp in (0x7, 0x85, 0x200B, 0x200E, 0x2028, 0x2029, 0x202A, 0x202E, 0x2066, 0x2069, 0xFEFF):
            self.assertEqual(prefixes("abc\tn" + chr(cp) + "n\thttps://x.fr/%s"), [], hex(cp))
        self.assertEqual(prefixes("abc\tCafé crème\thttps://x.fr/%s"), ["abc"])
        self.assertEqual(prefixes("abc\t\u65e5\u672c\thttps://x.fr/%s"), ["abc"])

    def test_reserves_identiques_a_nc_reglages(self):
        """Les deux listes de mots réservés (Saisies.js et nc-reglages) sont les mêmes."""
        loader = importlib.machinery.SourceFileLoader("ncreglages_liens", str(REGLAGES))
        spec = importlib.util.spec_from_loader("ncreglages_liens", loader)
        mod = importlib.util.module_from_spec(spec)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            loader.exec_module(mod)
        self.assertEqual(sorted(js("RESERVES")), sorted(mod.LIENS_RESERVES))

    def test_mots_reserves(self):
        for p in ("g", "yt", "w", "heure", "time", "mdp", "password", "port", "processus", "session", "note", "rappel"):
            self.assertEqual(prefixes(f"{p}\tN\thttps://x.fr/%s"), [], p)

    def test_commentaires_doublons_lignes_fausses(self):
        t = "# commentaire\n\nbad ligne\n" + AMZ + "\namz\tAutre\thttps://x.fr/%s\nyt2\tY\thttps://y.fr/%s\n"
        self.assertEqual(prefixes(t), ["amz", "yt2"])
        self.assertEqual(analyse(t)[0]["nom"], "Amazon")

    def test_bornes(self):
        ligne = "abc\tN\thttps://x.fr/%s\n"
        self.assertEqual(len(analyse("".join(f"a{i}\tN\thttps://x.fr/%s\n" for i in range(50)))), 50)
        self.assertEqual(analyse("".join(f"a{i}\tN\thttps://x.fr/%s\n" for i in range(51))), [])
        self.assertEqual(analyse(ligne + "#" * 16384), [])
        self.assertEqual(len(analyse(ligne + "#" * (16384 - len(ligne) - 1))), 1)

    def test_encodage(self):
        L = "[{p:'amz',nom:'A',url:'https://x.fr/s?k=%s'}]"
        self.assertEqual(js(f"lienWeb('amz a&b c', {L}).url"), "https://x.fr/s?k=a%26b%20c")
        self.assertEqual(js(f"lienWeb('amz é#?', {L}).url"), "https://x.fr/s?k=%C3%A9%23%3F")
        self.assertEqual(js(f"lienWeb('amz', {L})"), None)
        self.assertEqual(js(f"lienWeb('zzz a', {L})"), None)
        self.assertEqual(js(f"lienWeb('amzx a', {L})"), None)


def cli(env_dir, *args):
    env = {"PATH": os.environ["PATH"], "HOME": str(env_dir), "XDG_CONFIG_HOME": str(env_dir / "config"),
           "XDG_CACHE_HOME": str(env_dir / "cache"), "XDG_STATE_HOME": str(env_dir / "state"),
           "XDG_DATA_HOME": str(env_dir / "data"), "TMPDIR": str(env_dir), "NC_LANGUE": "fr"}
    return subprocess.run(["python3", "-I", str(REGLAGES), "liens-web", *args], env=env, text=True,
                          capture_output=True, timeout=30, stdin=subprocess.DEVNULL)


class Reglages(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.TemporaryDirectory(prefix="nclw-")
        self.addCleanup(self.t.cleanup)
        self.d = Path(self.t.name)
        self.f = self.d / "config/nc/liens-web.conf"

    def test_ajouter_liste_retirer(self):
        self.assertEqual(cli(self.d, "liste").stdout, "")
        r = cli(self.d, "ajouter", "amz", "Amazon", "https://www.amazon.fr/s?k=%s")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.f.read_text(), "amz\tAmazon\thttps://www.amazon.fr/s?k=%s\n")
        self.assertEqual(stat.S_IMODE(self.f.stat().st_mode), 0o600)
        self.assertEqual(cli(self.d, "liste").stdout, "amz\tAmazon\thttps://www.amazon.fr/s?k=%s\n")
        self.assertNotEqual(cli(self.d, "ajouter", "amz", "Autre", "https://x.fr/%s").returncode, 0)
        self.assertEqual(cli(self.d, "retirer", "amz").returncode, 0)
        self.assertEqual(self.f.read_text(), "")
        self.assertNotEqual(cli(self.d, "retirer", "amz").returncode, 0)

    def test_refus(self):
        self.assertFalse(self.f.exists())
        for a in (("G", "N", "https://x.fr/%s"), ("g", "N", "https://x.fr/%s"), ("mdp", "N", "https://x.fr/%s"),
                  ("a", "N", "javascript:%s"), ("a", "N", "https://x.fr/"), ("a", "N", "https://x.fr/%s%s"),
                  ("a", "n" * 41, "https://x.fr/%s"), ("a", "n\tn", "https://x.fr/%s"), ("a", "n\nn", "https://x.fr/%s")):
            self.assertNotEqual(cli(self.d, "ajouter", *a).returncode, 0, a)
        self.assertFalse(self.f.exists(), "un refus n'écrit rien")

    def test_lecture_ignore_le_mauvais(self):
        self.f.parent.mkdir(parents=True)
        self.f.write_text("# x\nbad\nG\tN\thttps://x.fr/%s\n" + AMZ + "\n")
        self.assertEqual(cli(self.d, "liste").stdout, "amz\tAmazon\thttps://www.amazon.fr/s?k=%s\n")
        self.f.write_text("".join(f"a{i}\tN\thttps://x.fr/%s\n" for i in range(51)))
        self.assertEqual(cli(self.d, "liste").stdout, "", "plus de 50 lignes : rien")
        self.f.write_text("#" * 16385)
        self.assertEqual(cli(self.d, "liste").stdout, "")

    def test_ecriture_atomique(self):
        self.ecrire("a0\tN\thttps://x.fr/%s\n")
        r = cli(self.d, "ajouter", "amz", "Amazon", "https://x.fr/%s")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(stat.S_IMODE(self.f.stat().st_mode), 0o600)
        self.assertEqual([p.name for p in self.f.parent.iterdir()], ["liens-web.conf"], "pas de temporaire laissé")

    def test_dossier_lien_refuse(self):
        (self.d / "ailleurs").mkdir()
        (self.d / "config").mkdir()
        (self.d / "config/nc").symlink_to(self.d / "ailleurs")
        self.assertNotEqual(cli(self.d, "ajouter", "amz", "Amazon", "https://x.fr/%s").returncode, 0)
        self.assertEqual(list((self.d / "ailleurs").iterdir()), [])

    def test_limite_de_50_en_ecriture(self):
        for i in range(50):
            self.assertEqual(cli(self.d, "ajouter", f"a{i}", "N", "https://x.fr/%s").returncode, 0)
        self.assertNotEqual(cli(self.d, "ajouter", "plus", "N", "https://x.fr/%s").returncode, 0)
        self.assertEqual(len(self.f.read_text().splitlines()), 50)

    def ecrire(self, texte):
        self.f.parent.mkdir(parents=True, exist_ok=True)
        self.f.write_bytes(texte if isinstance(texte, bytes) else texte.encode())

    def test_lignes_inconnues_gardees(self):
        """Ajouter puis retirer gardent commentaires, lignes mal écrites et lignes vides, telles quelles."""
        avant = "# mes liens\n\nbad ligne\nytb\tY\thttps://y.fr/%s\nG\tN\thttps://x.fr/%s\n# fin\n"
        self.ecrire(avant)
        self.assertEqual(cli(self.d, "ajouter", "amz", "Amazon", "https://x.fr/%s").returncode, 0)
        self.assertEqual(self.f.read_text(), avant + "amz\tAmazon\thttps://x.fr/%s\n")
        self.assertEqual(cli(self.d, "retirer", "ytb").returncode, 0)
        self.assertEqual(self.f.read_text(), avant.replace("ytb\tY\thttps://y.fr/%s\n", "") + "amz\tAmazon\thttps://x.fr/%s\n")
        self.assertEqual(cli(self.d, "retirer", "amz").returncode, 0)
        self.assertEqual(self.f.read_text(), avant.replace("ytb\tY\thttps://y.fr/%s\n", ""))
        self.assertNotEqual(cli(self.d, "retirer", "inconnu").returncode, 0)

    def test_octets_invalides_gardes(self):
        brut = b"# note \xff\xfe\nbad\xc3\n"
        self.ecrire(brut)
        self.assertEqual(cli(self.d, "ajouter", "amz", "Amazon", "https://x.fr/%s").returncode, 0)
        self.assertEqual(self.f.read_bytes(), brut + b"amz\tAmazon\thttps://x.fr/%s\n")

    def test_surrogateescape_seulement_pour_les_liens(self):
        """Les écrivains généraux (reglages.conf…) gardent leur rigueur : un surrogate isolé y lève une erreur. Seul le
        chemin des liens web relit et réécrit les octets non UTF-8 tels quels."""
        import ast
        src = (REPO / "home/.local/bin/nc-reglages").read_text(encoding="utf-8")
        fonctions = {n.name: ast.get_source_segment(src, n) for n in ast.walk(ast.parse(src)) if isinstance(n, ast.FunctionDef)}
        for nom in ("ouvrir_atomique", "_ecrire"):
            self.assertNotIn("surrogateescape", fonctions[nom], nom)
        avec = sorted(n for n, corps in fonctions.items() if "surrogateescape" in corps)
        self.assertEqual(avec, ["liens_web_ecrire", "liens_web_lignes"])

    def refus_sans_rien_ecrire(self, contenu):
        import hashlib
        self.ecrire(contenu)
        avant = hashlib.sha256(self.f.read_bytes()).hexdigest()
        for a in (("ajouter", "nouveau", "N", "https://x.fr/%s"), ("retirer", "a0")):
            r = cli(self.d, *a)
            self.assertNotEqual(r.returncode, 0, a)
            self.assertIn("rien n'est écrit", r.stderr)
            self.assertEqual(hashlib.sha256(self.f.read_bytes()).hexdigest(), avant, "fichier identique à l'octet")
            self.assertEqual([p.name for p in self.f.parent.iterdir()], ["liens-web.conf"])
        r = self.reglage("nouveau Nom https://x.fr/%s")
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual(hashlib.sha256(self.f.read_bytes()).hexdigest(), avant, "chemin graphique : identique aussi")

    def test_trop_de_lignes_refuse(self):
        self.refus_sans_rien_ecrire("".join(f"a{i}\tN\thttps://x.fr/%s\n" for i in range(51)))

    def test_trop_d_octets_refuse(self):
        self.refus_sans_rien_ecrire("a0\tN\thttps://x.fr/%s\n" + "# " + "x" * 16400 + "\n")

    def test_commentaires_comptent_dans_la_borne(self):
        self.refus_sans_rien_ecrire("a0\tN\thttps://x.fr/%s\n" + "# c\n" * 50)

    def test_fichier_pas_ordinaire_refuse(self):
        cible = self.d / "cible"
        cible.write_text("a0\tN\thttps://x.fr/%s\n")
        self.f.parent.mkdir(parents=True)
        self.f.symlink_to(cible)
        for a in (("ajouter", "nouveau", "N", "https://x.fr/%s"), ("retirer", "a0")):
            r = cli(self.d, *a)
            self.assertNotEqual(r.returncode, 0, a)
            self.assertIn("rien n'est écrit", r.stderr)
            self.assertTrue(self.f.is_symlink(), "le lien est laissé en place")
            self.assertEqual(cible.read_text(), "a0\tN\thttps://x.fr/%s\n")
        os.remove(self.f)
        os.mkfifo(self.f)
        r = cli(self.d, "ajouter", "nouveau", "N", "https://x.fr/%s")
        self.assertNotEqual(r.returncode, 0)
        self.assertTrue(stat.S_ISFIFO(self.f.lstat().st_mode))

    def test_nom_avec_sens_d_ecriture_refuse_en_ecriture(self):
        for cp in (0x7, 0x2028, 0x202E, 0x2066, 0x200F):
            self.assertNotEqual(cli(self.d, "ajouter", "amz", "n" + chr(cp) + "n", "https://x.fr/%s").returncode, 0, hex(cp))
            if cp != 0x2028:
                self.assertNotEqual(self.reglage("amz Nom" + chr(cp) + "x https://x.fr/%s").returncode, 0, hex(cp))
        self.assertFalse(self.f.exists())
        self.assertEqual(cli(self.d, "ajouter", "amz", "Café crème", "https://x.fr/%s").returncode, 0)

    def test_nom_avec_sens_d_ecriture_ignore_en_lecture(self):
        self.ecrire("amz\tn" + chr(0x202E) + "n\thttps://x.fr/%s\nytb\tY\thttps://y.fr/%s\n")
        self.assertEqual(cli(self.d, "liste").stdout, "ytb\tY\thttps://y.fr/%s\n")

    def reglage(self, saisie):
        env = {"PATH": os.environ["PATH"], "HOME": str(self.d), "XDG_CONFIG_HOME": str(self.d / "config"),
               "XDG_CACHE_HOME": str(self.d / "cache"), "XDG_STATE_HOME": str(self.d / "state"),
               "XDG_DATA_HOME": str(self.d / "data"), "TMPDIR": str(self.d), "NC_LANGUE": "fr"}
        return subprocess.run(["python3", "-I", str(REGLAGES), "set", "LIEN_AJOUTER", saisie], env=env, text=True,
                              capture_output=True, timeout=30, stdin=subprocess.DEVNULL)

    def test_ajout_par_la_fenetre(self):
        """Le champ de la fenêtre lance « set LIEN_AJOUTER <saisie> » : même validation, écriture atomique en 0600."""
        r = self.reglage("amz Amazon France https://www.amazon.fr/s?k=%s")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.f.read_text(), "amz\tAmazon France\thttps://www.amazon.fr/s?k=%s\n")
        self.assertEqual(stat.S_IMODE(self.f.stat().st_mode), 0o600)
        self.assertEqual([p.name for p in self.f.parent.iterdir()], ["liens-web.conf"])
        self.assertIn("existe déjà", self.reglage("amz Autre https://x.fr/%s").stderr)

    def test_refus_par_la_fenetre(self):
        for saisie, mot in (("g Google https://x.fr/%s", "mot de la recherche"), ("mdp N https://x.fr/%s", "mot de la recherche"),
                            ("a N javascript:%s", "refusé"), ("a N https://x.fr/", "refusé"), ("amz Amazon", "écris"),
                            ("", "écris"), ("A N https://x.fr/%s", "refusé")):
            r = self.reglage(saisie)
            self.assertNotEqual(r.returncode, 0, saisie)
            self.assertIn(mot, r.stderr, saisie)
        self.assertFalse(self.f.exists(), "un refus n'écrit rien")

    def test_catalogue_champ_d_ajout(self):
        env = {"HOME": str(self.d), "XDG_CONFIG_HOME": str(self.d / "config"), "XDG_CACHE_HOME": str(self.d / "cache"),
               "XDG_STATE_HOME": str(self.d / "state"), "XDG_DATA_HOME": str(self.d / "data"), "NC_LANGUE": "fr"}
        with mock.patch.dict(os.environ, env), warnings.catch_warnings():
            warnings.simplefilter("ignore", ResourceWarning)      # lecture de /proc par le catalogue
            l = importlib.machinery.SourceFileLoader("ncreg_liens", str(REGLAGES))
            m = importlib.util.module_from_spec(importlib.util.spec_from_loader("ncreg_liens", l))
            l.exec_module(m)
            m.catalogue_raccourcis = lambda: []
            m.lignes_sessions = lambda: []
            ligne = [x for x in m.catalogue({}) if x["cle"] == "LIEN_AJOUTER"]
        self.assertEqual(len(ligne), 1)
        self.assertEqual((ligne[0]["genre"], ligne[0]["section"]), ("texte", "Barre et dock"))

    def test_usage(self):
        self.assertNotEqual(cli(self.d).returncode, 0)
        self.assertNotEqual(cli(self.d, "ajouter", "a").returncode, 0)


# Entrée sur « amz a&b c » : le vrai Qt.openUrlExternally appelle xdg-open, remplacé par un faux qui note l'URL
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
  if (etape === 0) { if (spot.nomIA === "" || spot.liensWeb.length !== 1) return
   verifier(spot.liensWeb[0].p === "amz", "un seul lien valide : " + JSON.stringify(spot.liensWeb))
   champ.text = "yt a&b c"; etape++; return }
  if (etape === 1) {
   verifier(spot.resultats.every(x => x.sous !== "Rechercher sur Y"), "yt reste réservé : " + JSON.stringify(spot.resultats))
   champ.text = "amz a&b c"; etape++; return }
  if (etape === 2) {
   verifier(titres().length === 1 && titres()[0] === "a&b c" && spot.resultats[0].sous === "Rechercher sur Amazon", "amz : " + JSON.stringify(spot.resultats))
   verifier(S.lienWeb("amz a&b c", spot.liensWeb).url === "https://www.amazon.fr/s?k=a%26b%20c", "URL encodée")
   spot.valider(0, false); etape++; return }
  if (etape === 3) { attente++; if (attente < 15) return; Qt.quit() }
 } }
 Timer { interval: 25000; running: true; onTriggered: Qt.exit(9) }
}'''

STUBS = {
    "Reglages": '''pragma Singleton
import QtQuick
QtObject {
 property var v: ({})
 readonly property bool iaCoupee: true
 readonly property bool en: false
 function t(fr,en){return fr}
 function val(k,d){return v[k] !== undefined ? v[k] : d}
 function pageActive(n){return true}
}''',
    "Etat": '''pragma Singleton
import QtQuick
import Quickshell
QtObject {
 property string saisie: ""
 property string texteIA: ""
 property bool recherche: true
 property bool nuit: false
 readonly property string bin: Quickshell.env("HOME") + "/.local/bin/"
 property int fermetures: 0
 signal validerRecherche()
 function faire(c) {} function fermer() { fermetures++ } function aller(p) {} function basculer(e, c) {}
}''',
    "Partage": 'pragma Singleton\nimport QtQuick\nQtObject { property bool silence: false }',
    "AssistantEtat": 'pragma Singleton\nimport QtQuick\nQtObject {function formater(t){return t} function sansReseau(t){return t}}',
    "Etincelle": 'import QtQuick\nItem {property real taille: 10; property bool tourne: false; property string agent: ""}',
    "CloudEtat": 'pragma Singleton\nimport QtQuick\nQtObject { property bool actif: false; property bool associe: false }',
    "Rappels": 'pragma Singleton\nimport QtQuick\nQtObject { property var liste: []; property bool plein: false; function analyser(p) { return {ok: false, raison: "heure"} } function quand(d) { return "" } function creer(t, d) { return false } function supprimer(i) {} }',
}
SINGLETONS = ("Reglages", "Etat", "Partage", "AssistantEtat", "Couleurs", "Connexion")
NOMS = ["Reglages", "Etat", "Partage", "AssistantEtat", "Couleurs", "Connexion", "Recherche", "Emoji", "Diagnostic", "Etincelle", "Texte", "Ico"]
FAUX_BIN = {
    "nc-apps": '#!/bin/sh\nprintf "%s\\n" "[]"\n',
    "hyprctl": "#!/bin/sh\nprintf '%s\\n' '[]'\n",
    "nc-aide-config": "#!/bin/sh\nexit 0\n",
    "nc-demander": '#!/bin/sh\ncase "$1" in --ia) printf "%s\\n" \'{"nom": "-", "agent": "claude", "coupee": true}\' ;; esac\n',
    "xdg-open": '#!/bin/sh\nprintf \'%s\\n\' "$*" >> "$HOME/ouverts"\n',
    "gio": '#!/bin/sh\nprintf \'%s\\n\' "gio $*" >> "$HOME/ouverts"\n',
}


@unittest.skipUnless(shutil.which("qs"), "Quickshell requis")
class RechercheHorsEcran(unittest.TestCase):
    def test_prefixe_du_fichier_donne_une_ligne_et_entree_ouvre(self):
        with tempfile.TemporaryDirectory(prefix="ncm-") as d:
            root = Path(d)
            q = root / "qml"
            shutil.copytree(QML, q)
            for sous in ("run", "cache", "state", "data", "config", "tmp"):
                (root / sous).mkdir(mode=0o700)
            (root / "config/nc").mkdir()
            (root / "config/nc/liens-web.conf").write_text(AMZ + "\nyt\tY\thttps://y.fr/%s\nbad\n")
            for nom, code in STUBS.items():
                (q / (nom + ".qml")).write_text(code)
            (q / "qmldir").write_text("\n".join(("singleton " if n in SINGLETONS else "") + n + " 1.0 " + n + ".qml" for n in NOMS)
                                      + "\nsingleton CloudEtat 1.0 CloudEtat.qml\nsingleton Rappels 1.0 Rappels.qml")
            b = root / ".local/bin"
            b.mkdir(parents=True)
            for nom, code in FAUX_BIN.items():
                (b / nom).write_text(code)
                (b / nom).chmod(0o755)
            (q / "shell.qml").write_text(SCRIPT)
            env = dict(os.environ, HOME=d, XDG_CONFIG_HOME=str(root / "config"), XDG_CACHE_HOME=str(root / "cache"),
                       XDG_STATE_HOME=str(root / "state"), XDG_DATA_HOME=str(root / "data"), XDG_RUNTIME_DIR=str(root / "run"),
                       TMPDIR=str(root / "tmp"), QT_QPA_PLATFORM="offscreen", QT_QUICK_BACKEND="software",
                       PATH=str(b) + os.pathsep + os.environ["PATH"])
            for k in ("WAYLAND_DISPLAY", "HYPRLAND_INSTANCE_SIGNATURE", "DISPLAY", "BROWSER", "DBUS_SESSION_BUS_ADDRESS"):
                env.pop(k, None)
            r = subprocess.run(["qs", "--no-color", "-p", str(q / "shell.qml")], env=env, text=True, capture_output=True,
                               timeout=60, stdin=subprocess.DEVNULL)
            sortie = r.stdout + r.stderr
            self.assertEqual(r.returncode, 0, sortie)
            for erreur in ("ReferenceError", "TypeError", "is not a type", "Binding loop"):
                self.assertNotIn(erreur, sortie)
            # shortcut: Qt.openUrlExternally ne lance rien sous la plateforme offscreen, l'ouverture elle-même n'est pas captée
            texte = (root / "ouverts").read_text() if (root / "ouverts").exists() else ""
            self.assertNotIn("y.fr", texte, "yt reste le raccourci de la maison")


if __name__ == "__main__":
    unittest.main()

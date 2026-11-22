"""Snippets de la recherche de l'île (snippets.conf) : échappement et aller-retour (nc-reglages et Saisies.js, par node),
bornes et refus, lignes brutes gardées, secret jamais affiché (liste, catalogue, carte), copie par l'entrée standard
(nc-mdp --stdin avec un faux wl-copy ; Recherche.qml hors écran avec de faux wl-copy et nc-mdp), et ni snippets.conf ni
liens-web.conf dans une sauvegarde ou dans « Mon bureau me suit »."""
import hashlib
import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import unittest
import warnings
from unittest import mock

from tests import _isolation  # noqa: F401
from tests.test_spotlight_saisies import NODE, js
from tests import test_liens_web as tlw
from tests import test_mdp as tm

REPO = Path(__file__).resolve().parents[1]
REGLAGES = REPO / "home/.local/bin/nc-reglages"
SAUVEGARDE = REPO / "home/.local/bin/nc-sauvegarde"
TAB, NL, BS = chr(9), chr(10), chr(92)
# Textes d'essai : tabulation, retour à la ligne, barre oblique inverse (seule, doublée, devant n et t), accents, emoji
TEXTES = ["a" + TAB + "b", "l1" + NL + "l2" + NL, BS, BS + BS, BS + "n", BS + "t" + TAB + BS + NL, "C:" + BS + "Users" + BS + "x",
          "Café " + chr(0x1F600) + NL + TAB + "fin", "x" * 2000]
SECRET = "MotSecret-" + chr(0xE9) + "-7q2"


def env_de(d):
    return {"PATH": os.environ["PATH"], "HOME": str(d), "XDG_CONFIG_HOME": str(d / "config"), "XDG_CACHE_HOME": str(d / "cache"),
            "XDG_STATE_HOME": str(d / "state"), "XDG_DATA_HOME": str(d / "data"), "TMPDIR": str(d), "NC_LANGUE": "fr"}


def reglages(d, *args, entree=None):
    return subprocess.run(["python3", "-I", str(REGLAGES), *args], env=env_de(d), capture_output=True, timeout=30,
                          input=entree.encode() if isinstance(entree, str) else (entree or b""))


def module(d):
    """nc-reglages chargé comme module, son dossier personnel et ses dossiers XDG dans d (posés AVANT le chargement)."""
    with mock.patch.dict(os.environ, env_de(d)), warnings.catch_warnings():
        warnings.simplefilter("ignore")
        l = importlib.machinery.SourceFileLoader("ncreg_snippets", str(REGLAGES))
        m = importlib.util.module_from_spec(importlib.util.spec_from_loader("ncreg_snippets", l))
        l.exec_module(m)
    return m


class Dossier(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory(prefix="ncsn-")
        self.addCleanup(t.cleanup)
        self.d = Path(t.name)
        self.f = self.d / "config/nc/snippets.conf"
        env = mock.patch.dict(os.environ, env_de(self.d))      # les fonctions du module lisent XDG_CONFIG_HOME à l'appel
        env.start()
        self.addCleanup(env.stop)

    def ecrire(self, contenu):
        self.f.parent.mkdir(parents=True, exist_ok=True)
        self.f.write_bytes(contenu if isinstance(contenu, bytes) else contenu.encode())

    def sha(self):
        return hashlib.sha256(self.f.read_bytes()).hexdigest()


class Echappement(Dossier):
    def test_aller_retour_python(self):
        m = module(self.d)
        for t in TEXTES:
            e = m.snippet_echapper(t)
            self.assertNotIn(TAB, e)
            self.assertNotIn(NL, e)
            self.assertEqual(m.snippet_deseschapper(e), t, repr(t))
            self.assertEqual(m.snippet_comprise("k\tT\t" + e), ("k", "T", t, False), repr(t))
        self.assertEqual(m.snippet_echapper(BS + "n"), BS + BS + "n", "la barre est doublée avant tout le reste")
        for faux in (BS, "a" + BS, BS + "x", BS + "r", BS + BS + BS):
            self.assertIsNone(m.snippet_deseschapper(faux), repr(faux))

    def test_aller_retour_par_la_cli(self):
        for i, t in enumerate(TEXTES):
            r = reglages(self.d, "snippets", "ajouter", f"m{i}", "T", t)
            self.assertEqual(r.returncode, 0, r.stderr)
        m = module(self.d)
        self.assertEqual([s[2] for s in m.snippets_lire()], TEXTES)
        self.assertEqual(len(self.f.read_text().splitlines()), len(TEXTES), "une ligne par snippet")

    @unittest.skipUnless(NODE, "node requis")
    def test_aller_retour_js_et_python_identiques(self):
        m = module(self.d)
        for t in TEXTES:
            e = m.snippet_echapper(t)
            self.assertEqual(js(f"echapper({json.dumps(t)})"), e, repr(t))
            self.assertEqual(js(f"deseschapper({json.dumps(e)})"), t, repr(t))
        for faux in (BS, "a" + BS, BS + "x", BS + BS + BS):
            self.assertIsNone(js(f"deseschapper({json.dumps(faux)})"), repr(faux))
        fichier = "".join(f"m{i}\tT\t{m.snippet_echapper(t)}\n" for i, t in enumerate(TEXTES))
        self.assertEqual([x["texte"] for x in js(f"analyseSnippets({json.dumps(fichier)})")], TEXTES)


def analyse(texte):
    return js(f"analyseSnippets({json.dumps(texte)})")


def mots_js(texte):
    return [x["mot"] for x in analyse(texte)]


# Lignes d'essai : (ligne, comprise ?) ; mêmes réponses attendues de Saisies.js et de nc-reglages
LIGNES = [("adr\tAdresse\t1 rue", True), ("adr\tAdresse\t1 rue\tsecret", True), ("adr\tAdresse\t1 rue\tSECRET", False),
          ("adr\tAdresse\t1 rue\tsecret\tx", False), ("adr\tAdresse", False), ("ADR\tA\tx", False), ("a b\tA\tx", False),
          ("abcdefghijklm\tA\tx", False), ("abcdefghijkl\tA\tx", True), ("mdp\tA\tx", False), ("g\tA\tx", False),
          ("adr\t\tx", False), ("adr\t" + "n" * 40 + "\tx", True), ("adr\t" + "n" * 41 + "\tx", False),
          ("adr\t" + chr(0x1F600) * 40 + "\tx", True), ("adr\tA\t", False), ("adr\tA\t" + "x" * 2000, True),
          ("adr\tA\t" + "x" * 2001, False), ("adr\tA\t" + chr(0x1F600) * 2000, True), ("adr\tA\ta" + BS + "x", False),
          ("adr\tA\ta" + BS, False), ("adr\tA\ta" + BS + "nb" + BS + "tc", True), ("adr\tA\t" + BS + "n", True),
          ("# adr\tA\tx", False), ("adr\tA\tx\r", True)]
LIGNES += [("adr\tA" + chr(cp) + "\tx", False) for cp in (0x7, 0x85, 0x200B, 0x200E, 0x2028, 0x202E, 0x2066, 0xFEFF)]
LIGNES += [("adr\tA\tx" + chr(cp) + "y", False) for cp in (0x0, 0x7, 0xD, 0x1B, 0x85, 0x200F, 0x2028, 0x2029, 0x202A, 0x2069)]


class Bornes(Dossier):
    def test_lignes_python(self):
        m = module(self.d)
        for ligne, ok in LIGNES:
            self.assertEqual(m.snippet_comprise(ligne) is not None, ok, repr(ligne[:60]))
        self.assertEqual(m.snippet_comprise("adr\tA\tx\tsecret")[3], True)
        self.assertEqual(m.snippet_comprise("adr\tA\tx")[3], False)

    @unittest.skipUnless(NODE, "node requis")
    def test_lignes_js(self):
        nombres = js(f"{json.dumps([l + chr(10) for l, _ in LIGNES])}.map(l => analyseSnippets(l).length)")
        for (ligne, ok), n in zip(LIGNES, nombres):
            self.assertEqual(n, int(ok), repr(ligne[:60]))
        self.assertEqual(analyse("adr\tA\tx\tsecret\n")[0]["secret"], True)
        self.assertEqual(analyse("adr\tA\tx\n")[0]["secret"], False)

    @unittest.skipUnless(NODE, "node requis")
    def test_fichier_js(self):
        self.assertEqual(len(analyse("".join(f"a{i}\tT\tx\n" for i in range(50)))), 50)
        self.assertEqual(analyse("".join(f"a{i}\tT\tx\n" for i in range(51))), [])
        self.assertEqual(analyse("a\tT\tx\n" + "#" * 16384), [])
        self.assertEqual(mots_js("# c\n\nbad\nadr\tA\tx\nadr\tB\ty\nb2\tB\tz\n"), ["adr", "b2"])
        self.assertEqual(analyse("adr\tA\tx\nadr\tB\ty\n")[0]["titre"], "A", "le premier d'un mot l'emporte")

    @unittest.skipUnless(NODE, "node requis")
    def test_mots_reserves_identiques(self):
        """Une seule liste de mots réservés, partagée avec les liens web, la même en Python et en JS."""
        self.assertEqual(sorted(js("RESERVES")), sorted(module(self.d).LIENS_RESERVES))
        for mot in js("RESERVES"):
            self.assertEqual(mots_js(f"{mot}\tT\tx\n"), [], mot)

    def test_refus_sans_rien_ecrire(self):
        for a in (("G", "T", "x"), ("mdp", "T", "x"), ("note", "T", "x"), ("abcdefghijklm", "T", "x"), ("a", "n" * 41, "x"),
                  ("a", "", "x"), ("a", "T", ""), ("a", "T", "x" * 2001), ("a", "T" + TAB, "x"), ("a", "T", "x" + chr(0x202E)),
                  ("a", "T", "x" + chr(0x7) + SECRET), ("a", "T", "x" + chr(0xD))):
            r = reglages(self.d, "snippets", "ajouter", *a)
            self.assertNotEqual(r.returncode, 0, a)
            self.assertNotIn(SECRET.encode(), r.stderr + r.stdout)
        self.assertEqual(reglages(self.d, "snippets", "ajouter", "a", "T", "x" * 2000).returncode, 0)
        self.assertEqual(reglages(self.d, "snippets", "ajouter", "b", "n" * 40, "x").returncode, 0)
        self.assertEqual(len(self.f.read_text().splitlines()), 2, "seuls les deux snippets permis sont écrits")

    def test_usage(self):
        for a in ((), ("ajouter", "a", "T"), ("ajouter", "--oui", "a", "T", "x"), ("retirer",), ("liste", "x")):
            self.assertNotEqual(reglages(self.d, "snippets", *a).returncode, 0, a)
        self.assertFalse(self.f.exists())


class Fichier(Dossier):
    def test_ajouter_liste_retirer(self):
        self.assertEqual(reglages(self.d, "snippets", "liste").stdout, b"")
        r = reglages(self.d, "snippets", "ajouter", "adr", "Mon adresse", "1 rue" + NL + "75000")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.f.read_text(), "adr\tMon adresse\t1 rue" + BS + "n75000\n")
        self.assertEqual(stat.S_IMODE(self.f.stat().st_mode), 0o600)
        self.assertEqual(sorted(p.name for p in self.f.parent.iterdir() if p.suffix != ".lock"), ["snippets.conf"], "pas de temporaire laissé")
        self.assertEqual(reglages(self.d, "snippets", "liste").stdout.decode(), "adr\tMon adresse\t1 rue" + BS + "n75000\n")
        self.assertIn("existe déjà", reglages(self.d, "snippets", "ajouter", "adr", "Autre", "x").stderr.decode())
        self.assertEqual(reglages(self.d, "snippets", "retirer", "adr").returncode, 0)
        self.assertEqual(self.f.read_text(), "")
        self.assertNotEqual(reglages(self.d, "snippets", "retirer", "adr").returncode, 0)

    def test_lignes_brutes_gardees(self):
        """Ajouter puis retirer gardent commentaires, lignes fausses, lignes vides et octets non UTF-8, tels quels."""
        avant = b"# mes snippets \xff\n\nbad ligne\nzz\tZ\tz" + BS.encode() + b"q\nsig\tS\tBonjour\nmdp\tN\tx\n# fin\n"
        self.ecrire(avant)
        self.assertEqual(reglages(self.d, "snippets", "ajouter", "adr", "A", "x").returncode, 0)
        self.assertEqual(self.f.read_bytes(), avant + b"adr\tA\tx\n")
        self.assertEqual(reglages(self.d, "snippets", "retirer", "sig").returncode, 0)
        self.assertEqual(self.f.read_bytes(), avant.replace(b"sig\tS\tBonjour\n", b"") + b"adr\tA\tx\n")

    def refus_a_l_octet(self, contenu):
        self.ecrire(contenu)
        avant = self.sha()
        for args, entree in ((("snippets", "ajouter", "nouveau", "N", "x"), None), (("snippets", "retirer", "a0"), None),
                             (("set", "SNIPPET_AJOUTER", "nouveau N : x"), None), (("set", "SNIPPET_AJOUTER", "-"), "!nouveau N : x")):
            r = reglages(self.d, *args, entree=entree)
            self.assertNotEqual(r.returncode, 0, args)
            self.assertIn("rien n'est écrit", r.stderr.decode(), args)
            self.assertEqual(self.sha(), avant, "fichier identique à l'octet")
            self.assertEqual(sorted(p.name for p in self.f.parent.iterdir() if p.suffix != ".lock"), ["snippets.conf"])

    def test_plus_de_50_lignes_refuse_a_l_octet(self):
        self.refus_a_l_octet("".join(f"a{i}\tT\tx\n" for i in range(51)))

    def test_plus_de_16_kio_refuse_a_l_octet(self):
        self.refus_a_l_octet("a0\tT\tx\n# " + "x" * 16400 + "\n")

    def test_50_lignes_puis_ecriture_refusee(self):
        self.ecrire("".join(f"a{i}\tT\tx\n" for i in range(50)))
        avant = self.sha()
        r = reglages(self.d, "snippets", "ajouter", "plus", "T", "x")
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual(self.sha(), avant)
        self.assertEqual(len(reglages(self.d, "snippets", "liste").stdout.splitlines()), 50)

    def test_lien_fifo_et_dossier_lien_refuses(self):
        cible = self.d / "cible"
        cible.write_text("a0\tT\tx\n")
        self.f.parent.mkdir(parents=True)
        self.f.symlink_to(cible)
        for a in (("ajouter", "nouveau", "N", "x"), ("retirer", "a0")):
            r = reglages(self.d, "snippets", *a)
            self.assertNotEqual(r.returncode, 0, a)
            self.assertIn("rien n'est écrit", r.stderr.decode())
            self.assertTrue(self.f.is_symlink())
            self.assertEqual(cible.read_text(), "a0\tT\tx\n")
        self.assertEqual(reglages(self.d, "snippets", "liste").stdout, b"", "un lien n'est pas lu")
        os.remove(self.f)
        os.mkfifo(self.f)
        self.assertNotEqual(reglages(self.d, "snippets", "ajouter", "nouveau", "N", "x").returncode, 0)
        self.assertTrue(stat.S_ISFIFO(self.f.lstat().st_mode))
        autre = self.d / "autre"
        (autre / "ailleurs").mkdir(parents=True)
        (autre / "config").mkdir()
        (autre / "config/nc").symlink_to(autre / "ailleurs")
        self.assertNotEqual(reglages(autre, "snippets", "ajouter", "a", "T", "x").returncode, 0)
        self.assertEqual(list((autre / "ailleurs").iterdir()), [])


class Secret(Dossier):
    def test_saisie_de_la_fenetre(self):
        """« [!]mot titre : texte » : par argv ou par l'entrée standard (« - », ce que fait la fenêtre) ; jamais dans
        reglages.conf ; \\n déséchappé ; le texte refusé n'est pas redit."""
        r = reglages(self.d, "set", "SNIPPET_AJOUTER", "sig Ma signature : Bien " + chr(0xE0) + " toi," + BS + "nT")
        self.assertEqual(r.returncode, 0, r.stderr)
        r = reglages(self.d, "set", "SNIPPET_AJOUTER", "-", entree="!wifi Wifi maison : " + SECRET)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout + r.stderr, b"")
        m = module(self.d)
        self.assertEqual(m.snippets_lire(), [("sig", "Ma signature", "Bien " + chr(0xE0) + " toi," + NL + "T", False),
                                             ("wifi", "Wifi maison", SECRET, True)])
        self.assertEqual(stat.S_IMODE(self.f.stat().st_mode), 0o600)
        conf = self.d / "config/nc/reglages.conf"
        self.assertFalse(conf.exists() and "SNIPPET" in conf.read_text(), "jamais écrit dans reglages.conf")
        for saisie, mot, argv in (("adr Mon adresse", "écris", True), ("adr : x", "écris", True), ("", "écris", True),
                                  ("g G : x", "mot de la recherche", True),
                                  ("!adr A : " + SECRET + BS + "x", "texte refusé", False),   # un secret : entrée standard seule
                                  ("!adr A : " + SECRET + chr(0x202E), "refusé", False)):
            for args, entree in ((("set", "SNIPPET_AJOUTER", saisie), None), (("set", "SNIPPET_AJOUTER", "-"), saisie)):
                if entree is None and not argv:
                    continue
                r = reglages(self.d, *args, entree=entree)
                self.assertNotEqual(r.returncode, 0, saisie)
                self.assertIn(mot, r.stderr.decode(), saisie)
                self.assertNotIn(SECRET.encode(), r.stderr + r.stdout)
        self.assertEqual(len(m.snippets_lire()), 2)

    def test_secret_jamais_en_argument(self):
        """Point 4 : la forme argv d'un secret est refusée (liste des processus) ; le message dit comment faire, sans le texte ;
        rien n'est écrit. Un snippet ordinaire garde la forme en ligne ; l'entrée standard marche."""
        for args in (("set", "SNIPPET_AJOUTER", "!wifi Wifi : " + SECRET),
                     ("snippets", "ajouter", "--secret", "wifi", "Wifi", SECRET)):
            r = reglages(self.d, *args)
            self.assertNotEqual(r.returncode, 0, args)
            self.assertIn("printf %s", r.stderr.decode(), args)
            self.assertNotIn(SECRET.encode(), r.stdout + r.stderr, args)
            self.assertFalse(self.f.exists(), args)
        self.assertEqual(reglages(self.d, "snippets", "ajouter", "adr", "A", "texte en ligne").returncode, 0)
        self.assertEqual(reglages(self.d, "snippets", "ajouter", "--secret", "wifi", "Wifi", "-", entree=SECRET).returncode, 0)
        self.assertEqual(reglages(self.d, "set", "SNIPPET_AJOUTER", "-", entree="!w2 W2 : " + SECRET).returncode, 0)
        self.assertEqual([x[0] for x in module(self.d).snippets_lire()], ["adr", "wifi", "w2"])

    def test_jamais_a_distance(self):
        r = reglages(self.d, "set", "--distant", "SNIPPET_AJOUTER", "adr A : x")
        self.assertNotEqual(r.returncode, 0)
        self.assertFalse(self.f.exists())
        self.assertNotIn("SNIPPET_AJOUTER", module(self.d).DISTANT_PERMIS)

    def test_secret_jamais_dans_liste_ni_catalogue(self):
        self.assertEqual(reglages(self.d, "snippets", "ajouter", "--secret", "wifi", "Wifi", "-", entree=SECRET + NL).returncode, 0)
        self.assertEqual(reglages(self.d, "snippets", "ajouter", "adr", "Adresse", "RUE-PRIVEE-x1").returncode, 0)
        self.assertEqual(self.f.read_text(), "wifi\tWifi\t" + SECRET + "\tsecret\nadr\tAdresse\tRUE-PRIVEE-x1\n",
                         "le retour à la ligne final de l'entrée est retiré")
        liste = reglages(self.d, "snippets", "liste").stdout.decode()
        self.assertNotIn(SECRET, liste)
        self.assertEqual(liste, "wifi\tWifi\t(secret, non affiché)\nadr\tAdresse\tRUE-PRIVEE-x1\n")
        m = module(self.d)
        with mock.patch.dict(os.environ, env_de(self.d)), warnings.catch_warnings():
            warnings.simplefilter("ignore", ResourceWarning)
            m.catalogue_raccourcis = lambda: []
            m.lignes_sessions = lambda: []
            cat = m.catalogue({})
        self.assertNotIn(SECRET, json.dumps(cat, ensure_ascii=False))
        self.assertNotIn("RUE-PRIVEE", json.dumps(cat, ensure_ascii=False), "le catalogue ne montre aucun texte")
        lignes = {x["cle"]: x for x in cat if x["cle"].startswith("SNIPPET_")}
        self.assertEqual(sorted(lignes), ["SNIPPET_AJOUTER", "SNIPPET_adr", "SNIPPET_wifi"])
        self.assertEqual(lignes["SNIPPET_wifi"]["nom"], "Wifi (;wifi)")
        self.assertEqual(lignes["SNIPPET_wifi"]["commande"], ["nc-reglages", "snippets", "retirer", "wifi"])
        self.assertEqual((lignes["SNIPPET_AJOUTER"]["genre"], lignes["SNIPPET_AJOUTER"]["section"]), ("texte", "Snippets"))
        cles = [x["cle"] for x in cat]
        self.assertEqual(cles.index("SNIPPET_wifi"), cles.index("LIEN_AJOUTER") + 1, "juste après les liens web")
        self.assertIn("EN CLAIR", lignes["SNIPPET_AJOUTER"]["aide"])
        self.assertIn("!mot", lignes["SNIPPET_AJOUTER"]["aide"])

    def test_entree_bornee(self):
        for entree in (b"x" * 16385, b"\xff\xfe", b"x" * 2001):
            r = reglages(self.d, "snippets", "ajouter", "a", "T", "-", entree=entree)
            self.assertNotEqual(r.returncode, 0)
        self.assertFalse(self.f.exists())


class Verrou(Dossier):
    """Point 3 : deux nc-reglages en parallèle gardent les deux lignes (lecture-modification-écriture sous verrou)."""

    def test_deux_ajouts_en_parallele_15_fois(self):
        for i in range(15):
            self.ecrire("")
            ps = [subprocess.Popen(["python3", "-I", str(REGLAGES), "snippets", "ajouter", mot, "T", "x"], env=env_de(self.d),
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) for mot in ("aa", "bb")]
            self.assertEqual([p.wait(timeout=30) for p in ps], [0, 0], i)
            self.assertEqual(sorted(self.f.read_text().split()), sorted(["aa", "T", "x", "bb", "T", "x"]), i)
        self.assertEqual(stat.S_IMODE((self.f.parent / "snippets.conf.lock").stat().st_mode), 0o600)

    def test_acces_apres_lecture_0600(self):
        """Point 8 : nc-reglages remet snippets.conf en 0600 dès qu'il le lit."""
        self.ecrire("adr\tA\tx\n")
        self.f.chmod(0o644)
        self.assertEqual(reglages(self.d, "snippets", "liste").returncode, 0)
        self.assertEqual(stat.S_IMODE(self.f.stat().st_mode), 0o600)

    def test_fenetre_snippets_est_une_section(self):
        self.assertEqual(module(self.d).section_demandee("snippets"), "Snippets")

    def test_mot_point_virgule_ne_lance_rien(self):
        """Point 6 : « ;mot » est exclu de la recherche de fichiers (nc-apps files) et de logiciels (nc-logiciels chercher)."""
        src = (tlw.QML / "Recherche.qml").read_text(encoding="utf-8")
        for marque in ('modePaquets === "auto" && q.length >= 3 && !/^(', 'q.length >= 3 && !/^('):
            ligne = next(l for l in src.splitlines() if marque in l)
            self.assertIn("|;|", ligne)


@unittest.skipUnless(NODE, "node requis")
class MemeRegle(Dossier):
    """Une seule règle de caractères : Saisies.js (ce que l'île montre) et nc-reglages (ce qu'il écrit, liste et retire)."""

    def test_72_cas_memes_reponses_et_tout_se_retire(self):
        cas = tlw.cas_snippets()
        self.assertEqual(len(cas), 72)
        m = module(self.d)
        reponses = js("%s.map(function (l) { var r = analyseSnippets(l); return r.length ? [r[0].mot, r[0].titre, r[0].texte, r[0].secret] : null })"
                      % json.dumps(cas))
        acceptes = 0
        for c, rj in zip(cas, reponses):
            py = m.snippet_comprise(c)
            py = list(py) if py else None
            self.assertEqual(py, rj, ascii(c[:60]))
            if py:
                acceptes += 1
                # Tout ce que l'île montre se liste et se retire par nc-reglages
                self.ecrire(c + NL)
                self.assertIn(py[0], reglages(self.d, "snippets", "liste").stdout.decode())
                self.assertEqual(reglages(self.d, "snippets", "retirer", py[0]).returncode, 0, ascii(c[:60]))
                self.assertEqual(m.snippets_lire(), [], ascii(c[:60]))
        self.assertTrue(10 < acceptes < 60, acceptes)               # un contrôle qui accepte ou refuse tout ne prouve rien


@unittest.skipUnless(NODE, "node requis")
class Cartes(unittest.TestCase):
    LISTE = [{"mot": "adr", "titre": "Adresse", "texte": "1 rue" + NL + TAB + "75000  Paris", "secret": False},
             {"mot": "adr2", "titre": "Wifi", "texte": SECRET, "secret": True},
             {"mot": "ad", "titre": "Long", "texte": chr(0xE9) * 100, "secret": False},
             {"mot": "adx", "titre": "Quatrième", "texte": "x", "secret": False},
             {"mot": "b", "titre": "Autre", "texte": "y", "secret": False}]

    def cartes(self, q):
        return js(f"cartesSnippets({json.dumps(q)}, {json.dumps(self.LISTE)}, 'secret')")

    def test_trois_au_plus_par_debut_du_mot(self):
        self.assertEqual([c["mot"] for c in self.cartes(";ad")], ["adr", "adr2", "ad"])
        self.assertEqual([c["mot"] for c in self.cartes(";b")], ["b"])
        self.assertEqual([c["mot"] for c in self.cartes(";AD")], ["adr", "adr2", "ad"])
        self.assertEqual(self.cartes(";z"), [])
        self.assertEqual(self.cartes("adr"), [], "sans « ; » : rien")

    def test_secret_jamais_dans_la_carte(self):
        c = self.cartes(";adr2")
        self.assertEqual(c, [{"mot": "adr2", "titre": "Wifi", "sous": "secret"}])
        self.assertNotIn(SECRET, json.dumps(self.cartes(";"), ensure_ascii=False))
        self.assertNotIn("MotSecret", json.dumps(self.cartes(";"), ensure_ascii=False))

    def test_apercu_aplati_et_coupe(self):
        c = {x["mot"]: x for x in self.cartes(";ad")}
        self.assertEqual(c["adr"]["sous"], "1 rue 75000 Paris")
        self.assertEqual(c["ad"]["sous"], chr(0xE9) * 79 + chr(0x2026))
        emoji = [{"mot": "e", "titre": "E", "texte": chr(0x1F600) * 81, "secret": False}]
        sous = js(f"cartesSnippets(';e', {json.dumps(emoji)}, 's')[0].sous")
        self.assertEqual(sous, chr(0x1F600) * 79 + chr(0x2026), "coupé entre deux emoji, jamais au milieu")


def lancer_mdp(faux, entree):
    """nc-mdp --stdin sous la garde de test_mdp (aucune écriture ni programme hors de ses promesses), entrée donnée."""
    r = subprocess.run([sys.executable, "-I", "-B", "-c", tm.GARDE, str(tm.SCRIPT_MDP), "--stdin"], env=faux.environnement(),
                       input=entree, capture_output=True, timeout=30)
    faux.test.assertEqual(faux.garde.read_text() if faux.garde.exists() else "", "", "action refusée par la garde")
    faux.test.assertNotIn(b"Traceback", r.stderr)
    return r


class MdpStdin(unittest.TestCase):
    def test_copie_exacte_par_l_entree(self):
        for texte in (SECRET, "a" + TAB + "b" + NL + BS + "n" + chr(0x1F600), chr(0x1F600) * 2000, "x" * 2000):
            f = tm.Faux(self)
            r = lancer_mdp(f, texte.encode())
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(r.stdout + r.stderr, b"")
            self.assertEqual(len(f.appels()), 1)
            self.assertEqual(f.appels()[0].read_bytes(), texte.encode(), "le texte exact, rien d'ajouté")
            self.assertEqual(f.argv(), tm.TYPE + ["--sensitive"])
            self.assertNotIn(texte[:20], f.lire("argv") + f.lire("env"))
            self.assertTrue(f.marque.exists(), "marque nc-secret-copie posée")
            self.assertEqual(f.lire("tmpdir").strip(), "700", "TMPDIR privé")
            self.assertEqual(sorted(p.name for p in f.run.iterdir()), ["nc-secret-copie"])

    def test_refus_sans_le_texte(self):
        for entree in (b"", ("Z" + SECRET * 200)[:2001].encode(), (SECRET[:5] + chr(0x1F600) * 2100).encode(),
                       SECRET.encode() + b"\xff", b"\xc3"):
            f = tm.Faux(self)
            r = lancer_mdp(f, entree)
            self.assertEqual(r.returncode, 2, entree[:20])
            self.assertEqual(f.appels(), [], "rien copié")
            self.assertEqual(r.stdout, b"")
            self.assertIn(b"nc-mdp", r.stderr)
            self.assertNotIn(SECRET[:5].encode(), r.stderr)
        self.assertEqual(lancer_mdp(tm.Faux(self), b"x" * 2000).returncode, 0, "2 000 : permis")

    def test_source(self):
        src = tm.SOURCE
        self.assertIn("MAX_TEXTE, MAX_ENTREE = 2000, 8192", src)
        self.assertIn("read(MAX_ENTREE + 1)", src)
        self.assertIn("copier(cmd, generer(int(argv[1])) if texte is None else texte, marque, prive)", src,
                      "le même copier() que les mots de passe")


class RechercheSource(unittest.TestCase):
    SRC = (tlw.QML / "Recherche.qml").read_text(encoding="utf-8")

    def test_copie_par_l_entree_standard(self):
        i = self.SRC.index("function copierSnippet")
        bloc = self.SRC[i:self.SRC.index("// « port 8080 »", i)]
        self.assertIn('[Etat.bin + "nc-mdp", "--stdin"]', bloc)
        self.assertIn('["wl-copy", "--type", "text/plain;charset=utf-8"]', bloc)
        self.assertIn("write(texte)", bloc)
        for mal in ("sh -c", "bash", "execDetached", "console.", "s.texte]", "texte)]", "+ s.texte"):
            self.assertNotIn(mal, bloc)

    def test_fichier_lu_seulement_apres_le_point_virgule(self):
        i = self.SRC.index("id: fichierSnippets")
        bloc = self.SRC[i:self.SRC.index("}\n", i)]
        self.assertIn('path: r.q.startsWith(";") ?', bloc)
        self.assertIn('if (fichierSnippets.path !== "") fichierSnippets.reload()', self.SRC)


# Recherche.qml réel hors écran : « ;a » donne les cartes ; Entrée copie par de faux wl-copy et nc-mdp, qui notent
# leurs arguments et leur entrée (jamais le vrai presse-papiers)
SCRIPT = '''import QtQuick
import Quickshell
ShellRoot {
 id: racine
 property int etape: 0
 property int attente: 0
 function trouver(item,nom){if(item.objectName===nom)return item;for(var i=0;i<item.children.length;i++){var r=trouver(item.children[i],nom);if(r)return r}return null}
 function verifier(ok,message){if(!ok){console.error(message);Qt.exit(2);throw new Error(message)}}
 FloatingWindow { id: fen; visible: true; implicitWidth: 700; implicitHeight: 600
  Recherche { id: spot; width: 700; actif: true } }
 Timer { interval: 100; running: true; repeat: true; onTriggered: {
  var champ = trouver(spot, "nc-spotlight-champ")
  if (etape === 0) { if (spot.nomIA === "") return
   verifier(spot.snippets.length === 0, "rien de lu avant « ; »"); champ.text = ";a"; etape++; return }
  if (etape === 1) { if (spot.snippets.length !== 2) return
   var t = JSON.stringify(spot.resultats.map(x => [x.titre, x.sous]))
   verifier(t === JSON.stringify([["Copier : Adresse", "1 rue 75000"], ["Copier : Wifi", "secret"]]), "cartes : " + t)
   verifier(t.indexOf("@SECRET@") < 0, "secret affiché"); spot.valider(0, false); etape++; return }
  if (etape === 2) { if (Etat.fermetures < 1) return
   champ.text = ";aw"; etape++; return }
  if (etape === 3) { verifier(spot.resultats.length === 1 && spot.resultats[0].sous === "secret", "carte secrète"); spot.valider(0, false); etape++; return }
  if (etape === 4) { if (Etat.fermetures < 2) return
   champ.text = "x"; etape++; return }
  if (etape === 5) { verifier(spot.snippets.length === 0, "oubliés hors « ; »"); Qt.quit() }
 } }
 Timer { interval: 25000; running: true; onTriggered: Qt.exit(9) }
}'''


@unittest.skipUnless(shutil.which("qs"), "Quickshell requis")
class RechercheHorsEcran(unittest.TestCase):
    def lancer(self, d, script, sans=()):
        """Recherche.qml réel dans un qs hors écran ; `sans` : commandes absentes du PATH (wl-copy, nc-mdp)."""
        root = Path(d)
        q = root / "qml"
        shutil.copytree(tlw.QML, q)
        for sous in ("run", "cache", "state", "data", "config", "tmp"):
            (root / sous).mkdir(mode=0o700)
        (root / "config/nc").mkdir()
        (root / "config/nc/snippets.conf").write_text("adr\tAdresse\t1 rue" + BS + "n75000\naw\tWifi\t" + SECRET + "\tsecret\nbad\n")
        for nom, code in tlw.STUBS.items():
            (q / (nom + ".qml")).write_text(code)
        (q / "qmldir").write_text("\n".join(("singleton " if n in tlw.SINGLETONS else "") + n + " 1.0 " + n + ".qml" for n in tlw.NOMS)
                                  + "\nsingleton CloudEtat 1.0 CloudEtat.qml\nsingleton Rappels 1.0 Rappels.qml")
        b = root / ".local/bin"
        b.mkdir(parents=True)
        faux = dict(tlw.FAUX_BIN)
        faux["wl-copy"] = '#!/bin/sh\nprintf \'%s\\n\' "$@" > "$HOME/wl-argv"\ncat > "$HOME/wl-stdin"\n'
        faux["nc-mdp"] = '#!/bin/sh\nprintf \'%s\\n\' "$@" > "$HOME/mdp-argv"\ncat > "$HOME/mdp-stdin"\n'
        for nom in sans:
            faux.pop(nom, None)
        for nom, code in faux.items():
            (b / nom).write_text(code)
            (b / nom).chmod(0o755)
        (q / "shell.qml").write_text(script.replace("@SECRET@", SECRET))
        chemin = str(b) + os.pathsep + os.environ["PATH"]
        if sans:                                           # PATH réduit : le vrai wl-copy du système ne doit pas répondre
            (root / "pur").mkdir()
            for outil in ("qs", "sh", "cat", "env", "python3"):
                if shutil.which(outil):
                    (root / "pur" / outil).symlink_to(shutil.which(outil))
            chemin = str(b) + os.pathsep + str(root / "pur")
        env = dict(os.environ, HOME=d, XDG_CONFIG_HOME=str(root / "config"), XDG_CACHE_HOME=str(root / "cache"),
                   XDG_STATE_HOME=str(root / "state"), XDG_DATA_HOME=str(root / "data"), XDG_RUNTIME_DIR=str(root / "run"),
                   TMPDIR=str(root / "tmp"), QT_QPA_PLATFORM="offscreen", QT_QUICK_BACKEND="software", PATH=chemin)
        for k in ("WAYLAND_DISPLAY", "HYPRLAND_INSTANCE_SIGNATURE", "DISPLAY", "BROWSER", "DBUS_SESSION_BUS_ADDRESS"):
            env.pop(k, None)
        r = subprocess.run([shutil.which("qs"), "--no-color", "-p", str(q / "shell.qml")], env=env, text=True,
                           capture_output=True, timeout=60, stdin=subprocess.DEVNULL)
        sortie = r.stdout + r.stderr
        self.assertEqual(r.returncode, 0, sortie)
        for erreur in ("ReferenceError", "TypeError", "is not a type", "Binding loop"):
            self.assertNotIn(erreur, sortie)
        self.assertNotIn(SECRET, sortie, "jamais dans le journal de qs")
        return root

    def test_cartes_et_copie_par_l_entree(self):
        with tempfile.TemporaryDirectory(prefix="ncsq-") as d:
            root = self.lancer(d, SCRIPT)
            self.assertEqual((root / "wl-stdin").read_text(), "1 rue" + NL + "75000")
            self.assertEqual((root / "wl-argv").read_text(), "--type\ntext/plain;charset=utf-8\n")
            self.assertEqual((root / "mdp-stdin").read_text(), SECRET)
            self.assertEqual((root / "mdp-argv").read_text(), "--stdin\n")

    def test_commande_absente_se_voit_et_ne_bloque_pas(self):
        """Point 5 : wl-copy et nc-mdp absents : « Copie impossible » à l'écran, texte vidé, la file continue."""
        with tempfile.TemporaryDirectory(prefix="ncsq-") as d:
            self.lancer(d, SCRIPT_ABSENT, sans=("wl-copy", "nc-mdp"))


# Mêmes cartes, mais wl-copy et nc-mdp n'existent pas : onExited n'arrive jamais, seul onRunningChanged le dit
SCRIPT_ABSENT = SCRIPT.split(" Timer { interval: 100")[0] + ''' Timer { interval: 100; running: true; repeat: true; onTriggered: {
  var champ = trouver(spot, "nc-spotlight-champ")
  if (etape === 0) { if (spot.nomIA === "") return
   champ.text = ";a"; etape++; return }
  if (etape === 1) { if (spot.snippets.length !== 2) return
   spot.valider(0, false); etape++; return }
  if (etape === 2) { if (spot.resultats.length !== 1 || spot.resultats[0].sous !== "Snippets") return
   verifier(spot.resultats[0].titre === "Copie impossible" || spot.resultats[0].titre === "Copy failed", "message : " + spot.resultats[0].titre)
   verifier(Etat.fermetures === 0, "ne ferme pas sur un échec")
   champ.text = ";aw"; etape++; return }
  if (etape === 3) { if (spot.resultats.length !== 1 || spot.resultats[0].sous !== "secret") return
   spot.valider(0, false); etape++; return }
  if (etape === 4) { if (spot.resultats.length !== 1 || spot.resultats[0].sous !== "Snippets") return
   verifier(spot.resultats[0].titre === "Copie impossible" || spot.resultats[0].titre === "Copy failed", "nc-mdp absent : échec visible"); etape++; return }
  if (etape === 5) { Qt.quit() }
 } }
 Timer { interval: 25000; running: true; onTriggered: { console.error("bloqué à l'étape " + etape + " " + JSON.stringify(spot.resultats.map(x => x.titre))); Qt.exit(9) } }
}'''


class SauvegardeEtBureau(unittest.TestCase):
    """snippets.conf et liens-web.conf ne partent ni dans la sauvegarde locale, ni dans la version pour le cloud (celle de
    « Mon bureau me suit », nc-cloud bureau preparer), et une archive ne peut pas les remettre."""
    FICHIERS = (".config/nc/snippets.conf", ".config/nc/liens-web.conf")

    def test_jamais_dans_une_sauvegarde(self):
        with tempfile.TemporaryDirectory(prefix="ncss-") as d:
            home = Path(d) / "home"
            (home / ".config/nc").mkdir(parents=True)
            (home / ".config/nc/reglages.conf").write_text("LANGUE=fr\n")
            (home / ".config/nc/snippets.conf").write_text("wifi\tWifi\t" + SECRET + "\tsecret\n")
            (home / ".config/nc/liens-web.conf").write_text("amz\tLIEN-PRIVE-k2\thttps://x.fr/%s\n")
            env = {k: v for k, v in os.environ.items() if not k.startswith(("NOCTALIA_", "XDG_CONFIG", "XDG_STATE"))}
            env.pop("HYPRLAND_INSTANCE_SIGNATURE", None)
            env.update(HOME=str(home), NC_LANGUE="fr", XDG_CACHE_HOME=str(home / ".cache"))
            for args in (("creer",), ("creer", "--pour-le-cloud", "--sortie", str(Path(d) / "s.tar.gz"))):
                r = subprocess.run([str(SAUVEGARDE), *args], env=env, cwd=str(home), capture_output=True, text=True, timeout=120)
                self.assertEqual(r.returncode, 0, r.stderr)
                sortie, = list(home.glob("nc-sauvegarde-*.tar.gz")) + list(Path(d).glob("s.tar.gz"))
                with tarfile.open(sortie) as t:
                    noms = [m.name for m in t]
                    contenu = b"".join(t.extractfile(m).read() for m in t if m.isfile())
                self.assertIn(".config/nc/reglages.conf", noms, args)
                for f in self.FICHIERS:
                    self.assertNotIn(f, noms, args)
                self.assertNotIn(SECRET.encode(), contenu, args)
                self.assertNotIn(b"LIEN-PRIVE-k2", contenu, args)
                sortie.unlink()

    def test_une_archive_ne_les_remet_pas(self):
        spec = importlib.util.spec_from_loader("nc_sauvegarde_sn", importlib.machinery.SourceFileLoader("nc_sauvegarde_sn", str(SAUVEGARDE)))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        for f in self.FICHIERS:
            m = tarfile.TarInfo(f)
            m.size = 10
            self.assertIsNone(mod.nom_sur(m, None), f)
            self.assertFalse(any(mod.est_dans(f, a) for a in mod.A_GARDER + mod.CLOUD_ELEMENTS), f)


if __name__ == "__main__":
    unittest.main()

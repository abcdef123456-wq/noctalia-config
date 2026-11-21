"""Catalogue des modèles d'OpenCode (M1) : `opencode models` relu en fond comme celui d'agy (disque, 6 h, un seul fil, rien si
l'IA est coupée), sans jamais démarrer son service de fond. Faux opencode qui compte ses appels, HOME isolé, aucun compte."""
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import threading
import time
import types
import unittest
from unittest.mock import AsyncMock, patch

from tests import test_jarvis_catalogue_agy as agy     # le module, pas ses classes : sinon ses tests tourneraient deux fois
from tests.test_jarvis_runner import appeler, charger_runner, fastapi, faux_upstream

# Forme réelle de `opencode models --standalone` (OpenCode 2, HOME vide : les modèles gratuits de son fournisseur)
LISTE = "opencode/big-pickle\nopencode/deepseek-v4.1-flash-free\nanthropic/claude-sonnet-5-5\nopenrouter/z-ai/glm-5.3\n"
AIDE_V2 = "USAGE\n  opencode models [flags]\n\nFLAGS\n  --standalone       Run with a private server instead of the background service\n"
AIDE_V1 = "opencode models\n\nlist all available models\n"


def faux_opencode(dossier, modeles="print(" + repr(LISTE) + ", end='')", aide=AIDE_V2):
    chemin = Path(dossier) / "opencode"
    chemin.write_text(
        "#!" + sys.executable + "\nimport os, sys, time\nfrom pathlib import Path\n"
        "Path(__file__).with_suffix('.appels').open('a').write(' '.join(sys.argv[1:]) + '|' + os.getcwd() + '\\n')\n"
        "if sys.argv[1:] == ['models', '--help']:\n    print(" + repr(aide) + ")\n    sys.exit(0)\n"
        + modeles + "\n")
    chemin.chmod(0o755)
    return chemin


def appels(chemin):
    f = chemin.with_suffix(".appels")
    return [l.split("|")[0] for l in f.read_text().splitlines()] if f.exists() else []


class Parseur(unittest.TestCase):
    def test_forme_reelle_et_refus(self):
        m = agy.charger()
        liste = m.lire_catalogue_opencode(LISTE)
        self.assertEqual([x["id"] for x in liste], LISTE.split())
        self.assertTrue(all(x["name"] == x["id"] and m.modele_valide(x["id"]) and m.nom_propre(x["id"]) == x["id"] for x in liste))
        for piege in ("-x/y", "sans-fournisseur", "a/b c", "\x1b[31ma/b", "Erreur : pas connecté"):
            self.assertIsNone(m.lire_catalogue_opencode(LISTE + piege + "\n"), repr(piege))
        # Formes réelles qui ne repartent pas telles quelles après --model : ignorées, le reste est gardé
        long = "fireworks/accounts/fireworks/models/llama-v3p1-405b-instruct"
        for ignore in ("a/b\x07", "google-vertex-anthropic/claude-sonnet-4-5@20250929", "a/[1m]", "a/-x", "a/" + "b" * 80):
            self.assertEqual([x["id"] for x in m.lire_catalogue_opencode(LISTE + ignore + "\n" + long + "\n")], LISTE.split() + [long], repr(ignore))
        self.assertIsNone(m.lire_catalogue_opencode("\n \n"))
        self.assertEqual(len(m.lire_catalogue_opencode("a/a\na/a\nb/b\n")), 2)
        self.assertEqual(len(m.lire_catalogue_opencode("".join(f"p/m{i}\n" for i in range(300)))), 200)


class MoteurOpencode(unittest.TestCase):
    setUp = agy.Moteur.setUp
    session_de = agy.Moteur.session_de
    faux_amont = agy.Moteur.faux_amont

    def attendre(self):
        for fil in threading.enumerate():
            if fil.name in ("nc-opencode-modeles", "nc-agy-modeles"):
                fil.join(30)

    def avec(self, oc):
        p = patch.object(self.m, "executable", side_effect=lambda e: str(oc) if e == "opencode" else None)
        p.start()
        self.addCleanup(p.stop)

    def cache(self):
        return self.d / ".nc-jarvis-opencode-models.json"

    def opencode(self, e):
        return next(x for x in e.snapshot()["engines"] if x["id"] == "opencode")

    def test_liste_lue_en_fond_gardee_sur_disque_puis_rien(self):
        oc = faux_opencode(self.d)
        self.avec(oc)
        e = self.m.install(self.up)
        self.assertEqual(appels(oc), [], "charger le module ne lance rien")
        self.assertFalse(e.catalogue_au_demarrage(), "jamais au démarrage")
        self.assertEqual(appels(oc), [])
        self.assertEqual(self.opencode(e)["models"], [])
        self.assertIs(self.opencode(e)["catalogue_compte"], False)
        self.assertTrue(e.rafraichir_catalogues())
        self.attendre()
        self.assertEqual(appels(oc), ["models --help", "models --standalone"], "jamais sans --standalone (service de fond)")
        cwd = oc.with_suffix(".appels").read_text().splitlines()[-1].split("|")[1]
        self.assertFalse(os.path.exists(cwd), "dossier de travail vide, effacé ensuite")
        self.assertEqual([x["id"] for x in self.opencode(e)["models"]], LISTE.split())
        self.assertIs(self.opencode(e)["catalogue_compte"], True)
        self.assertEqual(stat.S_IMODE(self.cache().stat().st_mode), 0o600)
        self.assertFalse(e.rafraichir_catalogues(), "liste fraîche : rien")
        e2 = self.m.Engines(self.up)
        self.assertEqual(len(e2.models("opencode")), 4, "le cache sert au redémarrage")
        self.assertFalse(e2.rafraichir_opencode())
        self.assertEqual(appels(oc).count("models --standalone"), 1)

    def test_opencode_1_sans_standalone_et_aide_sans_models(self):
        oc = faux_opencode(self.d, aide=AIDE_V1)
        self.avec(oc)
        e = self.m.install(self.up)
        self.assertTrue(e.rafraichir_opencode())
        self.attendre()
        self.assertEqual(appels(oc), ["models --help", "models"])
        m2 = agy.charger()
        m2.isoler = AsyncMock(return_value=None)
        self.assertIsNone(m2.opencode_args_catalogue(str(faux_opencode(self.d, aide="Usage: opencode run\n"))))

    def test_ia_coupee_absent_essai_rate_et_un_seul_fil(self):
        oc = faux_opencode(self.d, "time.sleep(2)\nprint('erreur', end='')")
        self.avec(oc)
        conf = self.d / ".config/nc/reglages.conf"
        conf.parent.mkdir(parents=True)
        conf.write_text("IA_MODE=non\n")
        e = self.m.install(self.up)
        self.assertFalse(e.rafraichir_catalogues())
        self.assertEqual(appels(oc), [])
        conf.write_text("IA_MODE=auto\n")
        self.assertTrue(e.rafraichir_opencode())
        self.assertIs(self.opencode(e)["catalogue_en_cours"], True)
        essai, e.oc_essai = e.oc_essai, None
        self.assertFalse(e.rafraichir_opencode(), "un seul fil à la fois")
        e.oc_essai = essai
        self.attendre()
        self.assertEqual(self.opencode(e)["models"], [], "sortie hors format : rien d'inventé")
        self.assertFalse(e.rafraichir_opencode(), "pas de nouvel essai avant 15 min")
        self.assertEqual(appels(oc).count("models --standalone"), 1)
        with patch.object(self.m, "executable", return_value=None):
            e.oc_essai = None
            self.assertFalse(e.rafraichir_opencode())

    def test_cache_abime_refuse(self):
        self.cache().write_text(json.dumps(dict(t=time.time(), modeles=[dict(id="-x/y", name="-x/y")])))
        self.cache().chmod(0o600)
        self.assertEqual(self.m.Engines(self.up).models("opencode"), [])
        self.cache().write_text(json.dumps(dict(t=time.time(), modeles=[dict(id=f"p/m{i}", name=f"p/m{i}") for i in range(201)])))
        self.assertEqual(self.m.Engines(self.up).models("opencode"), [], "plus de 200 : refusé")
        self.cache().write_text(json.dumps(dict(t=time.time(), modeles=[dict(id=f"p/m{i}", name=f"p/m{i}") for i in range(200)])))
        self.assertEqual(len(self.m.Engines(self.up).models("opencode")), 200)


@unittest.skipUnless(fastapi, "FastAPI requis")
class RunnerOpencode(unittest.TestCase):
    def setUp(self):
        d = tempfile.TemporaryDirectory(prefix="nc-oc-")
        self.addCleanup(d.cleanup)
        self.d = Path(d.name)
        (self.d / "home-runner").mkdir()
        self.agy = agy.faux_agy(self.d)
        self.oc = faux_opencode(self.d)
        env = patch.dict(os.environ, HOME=str(self.d), XDG_CONFIG_HOME=str(self.d / ".config"), NC_PIECES_JOINTES=str(self.d / "pieces"),
                         PATH=str(self.d) + os.pathsep + os.environ.get("PATH", ""))
        env.start()
        self.addCleanup(env.stop)
        amont = agy.Moteur.faux_amont(types.SimpleNamespace(d=self.d, session_de=lambda cle: dict(model=None, effort=None)))
        self.up = faux_upstream(self.d)
        for nom, valeur in vars(amont).items():
            if nom != "__file__":
                setattr(self.up, nom, valeur)

        @self.up.app.get("/models")
        def lister():
            return {"models": self.up.KNOWN_MODELS}
        self.addCleanup(self.attendre)

    attendre = MoteurOpencode.attendre

    def test_demarrage_rien_puis_nc_engines_une_fois(self):
        runner = charger_runner(self.up)
        self.attendre()
        self.assertEqual(appels(self.oc), [], "le démarrage du runner ne lit pas OpenCode")
        self.assertEqual(appeler(runner.app, "/nc/engines", methode="GET"), 200)
        self.attendre()
        self.assertEqual(appels(self.oc), ["models --help", "models --standalone"])
        self.assertEqual(appeler(runner.app, "/nc/engines", methode="GET"), 200)
        self.attendre()
        self.assertEqual(appels(self.oc).count("models --standalone"), 1, "liste fraîche : aucun processus")
        self.oc.with_suffix(".appels").unlink()
        runner.engines.oc_lu, runner.engines.oc_essai = time.time() - 7 * 3600, None
        self.assertEqual(appeler(runner.app, "/models", methode="GET"), 200)
        self.attendre()
        self.assertEqual(appels(self.oc), [], "/models (Telegram, Discord) ne lit que le catalogue d'agy")


if __name__ == "__main__":
    unittest.main()

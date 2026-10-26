"""nc_runner devant un faux runner d'origine en mémoire (sans le dépôt amont) : le ménage des pièces jointes
(/tmp/assistant_uploads, a25e540), appelé en ASGI ; aucun vrai dossier de /tmp n'est touché (DOSSIER_PIECES dans le test)."""
import asyncio
import os
from pathlib import Path
import sys
import tempfile
import time
import types
import unittest
import unittest.mock

REPO = Path(__file__).resolve().parents[1]
SERVEUR = REPO / "home/.local/share/nc-jarvis/server"

try:
    import fastapi
except ImportError:
    fastapi = None


def faux_upstream(racine):
    up = types.ModuleType("main")
    up.__file__ = str(racine / "home-runner/main.py")
    up.app = fastapi.FastAPI()

    class Moteurs:
        def snapshot(self, cle=None):
            return {}

        def choose(self, **kw):
            return kw

        def session(self):
            return dict(engine="agy")

        async def run(self, *a, **kw):
            return dict(success=True)
    up.run_agy = Moteurs().run

    async def health():
        return dict(status="ok")
    up.health = health
    up._check_secret = lambda request: None

    @up.app.post("/run")
    async def run(request: fastapi.Request):
        if (await request.body()) == b"panne":
            raise fastapi.HTTPException(500)
        return dict(success=True)

    @up.app.get("/autre")
    async def autre():
        return {}
    return up


def charger_runner(up, bridge=None):
    """nc_runner chargé comme par uvicorn : main = le faux, nc_engines = celui de l'overlay (sys.path en tête)."""
    avant = {k: sys.modules.get(k) for k in ("main", "nc_engines", "nc_runner_test", "agy_bridge")}
    chemin = list(sys.path)
    sys.modules["main"] = up
    if bridge is not None:
        sys.modules["agy_bridge"] = bridge
    else:
        sys.modules.pop("agy_bridge", None)
    sys.modules.pop("nc_engines", None)
    sys.path.insert(0, str(SERVEUR))
    try:
        m = types.ModuleType("nc_runner_test")
        m.__file__ = str(SERVEUR / "nc_runner.py")
        exec(compile((SERVEUR / "nc_runner.py").read_text(), m.__file__, "exec"), m.__dict__)
        return m
    finally:
        sys.path[:] = chemin
        for k, v in avant.items():
            if v is None:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = v


def appeler(app, chemin, corps=b"{}", methode="POST"):
    messages, entree = [], [dict(type="http.request", body=corps, more_body=False)]

    async def recevoir():
        return entree.pop(0) if entree else dict(type="http.disconnect")

    async def envoyer(m):
        messages.append(m)
    scope = dict(type="http", asgi=dict(version="3.0"), http_version="1.1", method=methode, scheme="http", path=chemin,
                 raw_path=chemin.encode(), root_path="", query_string=b"", headers=[(b"content-type", b"application/json")],
                 client=("127.0.0.1", 1), server=("127.0.0.1", 80))
    asyncio.run(app(scope, recevoir, envoyer))
    return next(m for m in messages if m["type"] == "http.response.start")["status"]


@unittest.skipUnless(fastapi, "FastAPI requis")
class MenagePiecesJointes(unittest.TestCase):
    def setUp(self):
        d = tempfile.TemporaryDirectory(prefix="nc-runner-")
        self.addCleanup(d.cleanup)
        self.racine = Path(d.name)
        self.pieces = self.racine / "assistant_uploads"
        self.pieces.mkdir()
        vieille = self.piece("du-demarrage", 4000)
        with unittest.mock.patch.dict(os.environ, NC_PIECES_JOINTES=str(self.pieces), HOME=str(self.racine)):    # jamais le vrai /tmp
            self.m = charger_runner(faux_upstream(self.racine))
        self.assertEqual(self.m.DOSSIER_PIECES, str(self.pieces))
        self.assertFalse(vieille.exists())                    # ménage au démarrage

    def piece(self, nom, age):
        f = self.pieces / nom
        f.write_bytes(b"contenu")
        t = time.time() - age
        os.utime(f, (t, t))
        return f

    def test_apres_un_run_les_pieces_de_plus_d_une_heure_partent(self):
        vieille, recente = self.piece("vieille.pdf", 3700), self.piece("recente.png", 60)
        self.assertEqual(appeler(self.m.app, "/run"), 200)
        self.assertFalse(vieille.exists())
        self.assertTrue(recente.exists())                     # la conversation peut encore y revenir

    def test_meme_en_erreur_et_seulement_apres_un_run(self):
        vieille = self.piece("vieille.txt", 7200)
        self.assertEqual(appeler(self.m.app, "/autre", methode="GET"), 200)
        self.assertTrue(vieille.exists())                     # une autre route ne touche à rien
        self.assertEqual(appeler(self.m.app, "/run", b"panne"), 500)
        self.assertFalse(vieille.exists())

    def test_un_lien_est_efface_jamais_sa_cible_ni_un_dossier(self):
        cible = self.racine / "a-garder"
        cible.write_text("x")
        lien = self.pieces / "lien"
        lien.symlink_to(cible)
        os.utime(lien, (time.time() - 7200,) * 2, follow_symlinks=False)
        sous = self.pieces / "sous-dossier"
        sous.mkdir()
        os.utime(sous, (time.time() - 7200,) * 2)
        self.assertEqual(self.m._purger_pieces_jointes(), 1)
        self.assertFalse(lien.is_symlink())
        self.assertTrue(cible.exists())
        self.assertTrue(sous.is_dir())

    def test_dossier_absent_rien_ne_casse(self):
        self.m.DOSSIER_PIECES = str(self.racine / "absent")
        self.assertEqual(self.m._purger_pieces_jointes(), 0)
        self.assertEqual(appeler(self.m.app, "/run"), 200)


# Un faux agy_bridge qui lance agy comme le vrai (4ecc57a à 17525af) : asyncio.create_subprocess_exec, en tour unique
# (-p prompt) et en worker stream-json (le prompt par stdin) ; il ajoute le drapeau comme 17525af.
FAUX_PONT = """
import asyncio
import os

async def oneshot(agy, prompt):
    cmd = [agy, "--model", "m", "--dangerously-skip-permissions", "-p", prompt, "--output-format", "text"]
    proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
                                                env={**os.environ, "TERM": "dumb"})
    sortie, _ = await asyncio.wait_for(proc.communicate(), timeout=10)
    return sortie.decode()

async def worker(agy, prompt):
    cmd = [agy, "--input-format", "stream-json", "--output-format", "stream-json", "--dangerously-skip-permissions"]
    proc = await asyncio.create_subprocess_exec(*cmd, stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
                                                stderr=asyncio.subprocess.PIPE)
    sortie, _ = await proc.communicate(prompt.encode())
    return sortie.decode()
"""


@unittest.skipUnless(fastapi, "FastAPI requis")
class AgySansAutoApprobation(unittest.TestCase):
    """#32 : le drapeau --dangerously-skip-permissions n'arrive à agy qu'avec NC_AGY_SANS_CONFIRMATION=oui (à la main,
    dans le .env du serveur). Le faux agy ne fait que noter ses arguments."""
    def setUp(self):
        d = tempfile.TemporaryDirectory(prefix="nc-runner-agy-")
        self.addCleanup(d.cleanup)
        self.racine = Path(d.name)
        self.args = self.racine / "args"
        for nom in ("agy", "codex"):
            f = self.racine / nom
            f.write_text(f'#!/bin/sh\nprintf "%s\\n" "$*" >> "{self.args}"\n[ "$1" = "--input-format" ] && cat >/dev/null\necho OK\n')
            f.chmod(0o755)

    def charger(self, accord=None):
        bridge = types.ModuleType("agy_bridge")
        exec(compile(FAUX_PONT, "agy_bridge", "exec"), bridge.__dict__)
        env = dict(NC_PIECES_JOINTES=str(self.racine / "pieces"), HOME=str(self.racine / "home"))   # jamais le vrai ~/.gemini
        with unittest.mock.patch.dict(os.environ, env):
            os.environ.pop("NC_AGY_SANS_CONFIRMATION", None)
            m = charger_runner(faux_upstream(self.racine), bridge)
        return m, bridge

    def lancer(self, bridge, mode, prog="agy", prompt="bonjour", accord=None):
        self.args.unlink(missing_ok=True)
        with unittest.mock.patch.dict(os.environ):
            os.environ.pop("NC_AGY_SANS_CONFIRMATION", None)
            if accord is not None:
                os.environ["NC_AGY_SANS_CONFIRMATION"] = accord
            sortie = asyncio.run(getattr(bridge, mode)(str(self.racine / prog), prompt))
        self.assertIn("OK", sortie)
        return self.args.read_text()

    def test_drapeau_retire_par_defaut_en_tour_unique_et_en_worker(self):
        _, bridge = self.charger()
        for mode in ("oneshot", "worker"):
            with self.assertLogs("nc_runner", "INFO") as journal:
                args = self.lancer(bridge, mode)
            self.assertNotIn("--dangerously-skip-permissions", args, mode)
            self.assertIn("--output-format", args)                         # le reste de la commande est intact
            self.assertNotIn("bonjour", "".join(journal.output))              # une ligne, sans valeur
        self.assertIn("-p bonjour", self.lancer(bridge, "oneshot"))

    def test_avec_l_accord_ecrit_le_drapeau_reste(self):
        _, bridge = self.charger()
        for accord in ("oui", "OUI ", "Oui"):
            self.assertIn("--dangerously-skip-permissions", self.lancer(bridge, "oneshot", accord=accord), accord)
        for refus in ("", "non", "yes", "1", "true"):
            self.assertNotIn("--dangerously-skip-permissions", self.lancer(bridge, "worker", accord=refus), refus)

    def test_une_autre_commande_reste_intacte_et_un_prompt_egal_au_drapeau_reste_un_prompt(self):
        m, bridge = self.charger()
        self.assertIn("--dangerously-skip-permissions", self.lancer(bridge, "oneshot", prog="codex"))
        self.assertEqual(m.commande_agy_sure(["/opt/agy", "-p", "--dangerously-skip-permissions", "--dangerously-skip-permissions"]),
                         ["/opt/agy", "-p", "--dangerously-skip-permissions"])
        self.assertEqual(m.commande_agy_sure([]), [])
        self.assertEqual(m.commande_agy_sure(["agy-wrapper", "--dangerously-skip-permissions"]),
                         ["agy-wrapper", "--dangerously-skip-permissions"])        # le nom exact « agy » seulement

    def test_relais_delegue_le_reste_et_ne_s_empile_pas(self):
        import asyncio as vrai
        m, bridge = self.charger()
        self.assertIs(bridge.asyncio.subprocess, vrai.subprocess)
        self.assertIs(bridge.asyncio.TimeoutError, vrai.TimeoutError)
        relais = bridge.asyncio
        m._sans_auto_approbation()
        self.assertIs(bridge.asyncio, relais)
        self.assertIs(vrai.create_subprocess_exec, __import__("asyncio").create_subprocess_exec)   # le vrai module intact

    def test_avertit_si_agy_approuve_tout_de_lui_meme(self):
        reglages = self.racine / "home/.gemini/antigravity-cli/settings.json"
        reglages.parent.mkdir(parents=True)
        reglages.write_text('{"toolPermission": "always-proceed"}')
        with self.assertLogs("nc_runner", "WARNING") as journal:
            self.charger()
        self.assertIn("always-proceed", "".join(journal.output))
        for contenu in ('{"toolPermission": "request-review"}', "pas du json", "[]"):
            reglages.write_text(contenu)
            m, _ = self.charger()
            with unittest.mock.patch.dict(os.environ, HOME=str(self.racine / "home")):
                self.assertFalse(m.agy_toujours_permis(), contenu)

    def test_sans_agy_bridge_rien(self):
        with unittest.mock.patch.dict(os.environ, HOME=str(self.racine / "home"), NC_PIECES_JOINTES=str(self.racine / "p")):
            m = charger_runner(faux_upstream(self.racine))
        self.assertIsNone(m._sans_auto_approbation())

    def test_hors_de_la_liste_blanche_et_jamais_ecrit_par_le_deployeur(self):
        gestion = (SERVEUR / "nc_management.py").read_text()
        self.assertNotIn("NC_AGY_SANS_CONFIRMATION", gestion)
        self.assertNotIn("NC_AGY_SANS_CONFIRMATION", (SERVEUR.parent / "deployer.py").read_text())


if __name__ == "__main__":
    unittest.main()

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


def charger_runner(up):
    """nc_runner chargé comme par uvicorn : main = le faux, nc_engines = celui de l'overlay (sys.path en tête)."""
    avant = {k: sys.modules.get(k) for k in ("main", "nc_engines", "nc_runner_test")}
    chemin = list(sys.path)
    sys.modules["main"] = up
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
        with unittest.mock.patch.dict(os.environ, NC_PIECES_JOINTES=str(self.pieces)):    # jamais le vrai /tmp
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


if __name__ == "__main__":
    unittest.main()

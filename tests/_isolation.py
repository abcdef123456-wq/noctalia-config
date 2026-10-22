"""Avant tout test : les dossiers XDG (cache, réglages, état, données, runtime) pointent vers un dossier temporaire.
Un test qui passe dict(os.environ, HOME=…) à un script hérite alors de valeurs sûres, jamais de ~/.cache ni de
~/.config de la vraie session (un test de nc-maj avait écrit dans le vrai ~/.cache/nc/maj-annoncee)."""
import atexit
import os
from pathlib import Path
import shutil
import tempfile

if not os.environ.get("NC_TEST_ISOLE"):
    _racine = Path(tempfile.mkdtemp(prefix="nc-tests-"))
    atexit.register(shutil.rmtree, _racine, True)
    os.environ["NC_TEST_VRAI_RUNTIME"] = os.environ.get("XDG_RUNTIME_DIR", "")
    for _cle, _nom in (("XDG_CACHE_HOME", "cache"), ("XDG_CONFIG_HOME", "config"), ("XDG_STATE_HOME", "state"),
                       ("XDG_DATA_HOME", "data"), ("XDG_RUNTIME_DIR", "run")):
        (_racine / _nom).mkdir(mode=0o700)
        os.environ[_cle] = str(_racine / _nom)
    os.environ["NC_TEST_ISOLE"] = str(_racine)

"""nc-jarvis : les messages d'erreur suivent la langue du bureau (anglais quand la langue est « en »), et un
NC_JARVIS_GESTION_DELAI qui n'est pas un nombre ne fait plus planter le démarrage (défaut de 20 s). HOME temporaire."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
JARVIS = REPO / "home/.local/bin/nc-jarvis"


class Langue(unittest.TestCase):
    def setUp(self):
        d = tempfile.TemporaryDirectory(prefix="nc-jarvis-langue-")
        self.addCleanup(d.cleanup)
        self.home = Path(d.name)
        self.env = dict(os.environ, HOME=str(self.home), XDG_CONFIG_HOME=str(self.home / ".config"),
                        XDG_CACHE_HOME=str(self.home / ".cache"), XDG_STATE_HOME=str(self.home / ".state"),
                        XDG_DATA_HOME=str(self.home / ".data"), XDG_RUNTIME_DIR=str(self.home), TMPDIR=str(self.home))
        conf = self.home / ".config/nc/assistant.conf"
        conf.parent.mkdir(parents=True)
        conf.write_text("URL=https://exemple.invalid\nSECRET_KEY=cle-de-test-assez-longue-0123456789\n")
        conf.chmod(0o600)

    def requete(self, corps, langue, **env):
        e = dict(self.env, NC_LANGUE=langue, **env)
        r = subprocess.run(["python3", "-I", str(JARVIS), "requete"], input=json.dumps(corps) + "\n", env=e,
                           capture_output=True, text=True, timeout=30)
        return r, (json.loads(r.stdout) if r.stdout.strip().startswith("{") else {})

    def test_operation_inconnue_en_anglais(self):
        r, rep = self.requete({"op": "zzz"}, "en")
        self.assertEqual(rep.get("error"), "Unknown operation", r.stdout + r.stderr)

    def test_operation_inconnue_en_francais(self):
        r, rep = self.requete({"op": "zzz"}, "fr")
        self.assertEqual(rep.get("error"), "Opération inconnue", r.stdout + r.stderr)

    def test_confirmation_et_parametres_en_anglais(self):
        r, rep = self.requete({"op": "memory.add", "params": {}}, "en")
        self.assertEqual(rep.get("error"), "Confirmation required", r.stdout + r.stderr)
        r, rep = self.requete({"op": "memory", "params": []}, "en")
        self.assertEqual(rep.get("error"), "Invalid parameters", r.stdout + r.stderr)

    def test_requete_invalide_en_anglais(self):
        r, rep = self.requete([1], "en")
        self.assertEqual(rep.get("error"), "Invalid request", r.stdout + r.stderr)

    def test_delai_pas_un_nombre_prend_le_defaut(self):
        for valeur in ("abc", "1,5", "nan", "-3", "inf"):
            r, rep = self.requete({"op": "zzz"}, "fr", NC_JARVIS_GESTION_DELAI=valeur)
            self.assertNotIn("Traceback", r.stderr, valeur)
            self.assertEqual(rep.get("error"), "Opération inconnue", f"{valeur}: {r.stdout}{r.stderr}")


if __name__ == "__main__":
    unittest.main()

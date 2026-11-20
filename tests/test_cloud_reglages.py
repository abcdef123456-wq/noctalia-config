"""Section de réglages « Cloud JARVIS » (C2a) : CLOUD_JARVIS à non par défaut ; à oui, l'association lue sur ce PC (aucun
appel réseau) et les actions de nc-cloud à argv fixe. Tout est isolé (faux HOME) ; nc-cloud n'est jamais lancé."""
import json
import os
from pathlib import Path
import runpy
import tempfile
import unittest
from unittest.mock import patch
import warnings

REPO = Path(__file__).resolve().parents[1]
NC_REGLAGES = REPO / "home/.local/bin/nc-reglages"


class CloudReglages(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.TemporaryDirectory(prefix="nc-cloud-reg-")
        self.addCleanup(self.d.cleanup)
        self.home = Path(self.d.name)
        (self.home / "tmp").mkdir()
        env = dict(HOME=str(self.home), XDG_CONFIG_HOME=str(self.home / ".config"), XDG_DATA_HOME=str(self.home / ".local/share"),
                   XDG_STATE_HOME=str(self.home / ".local/state"), XDG_CACHE_HOME=str(self.home / ".cache"),
                   TMPDIR=str(self.home / "tmp"), NC_LANGUE="fr")
        p = patch.dict(os.environ, env)
        p.start()
        self.addCleanup(p.stop)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", ResourceWarning)
            self.nc = runpy.run_path(str(NC_REGLAGES))

    def lignes(self, vals):
        return {l["cle"]: l for l in self.nc["catalogue"](vals) if l["section"] == "Cloud JARVIS"}

    def test_coupe_par_defaut_aucune_action(self):
        r = self.nc["PAR_CLE"]["CLOUD_JARVIS"]
        self.assertEqual((r.section, r.genre, r.defaut), ("Cloud JARVIS", "ouinon", "non"))
        self.assertEqual(list(self.lignes({})), ["CLOUD_JARVIS"])

    def test_non_associe_verifier_et_associer(self):
        l = self.lignes({"CLOUD_JARVIS": "oui"})
        self.assertEqual(list(l), ["CLOUD_JARVIS", "cloud:etat-local", "cloud:verifier", "cloud:associer"])
        self.assertEqual(l["cloud:verifier"]["commande"], ["nc-cloud", "verifier"])
        self.assertEqual(l["cloud:associer"]["commande"], ["nc-cloud", "associer"])
        self.assertTrue(all(x["relire"] for k, x in l.items() if x["genre"] == "action"))
        self.assertIn("pas associé", l["cloud:etat-local"]["nom"])

    def test_associe_etat_et_dissocier_confirme(self):
        app = self.home / ".local/state/nc-cloud/appareil.json"
        app.parent.mkdir(parents=True)
        app.write_text(json.dumps({"device_id": "d1", "name": "mon-pc\u0007\u202e" + "x" * 100}))
        l = self.lignes({"CLOUD_JARVIS": "oui"})
        self.assertEqual(list(l), ["CLOUD_JARVIS", "cloud:etat-local", "cloud:verifier", "cloud:etat", "cloud:dissocier"])
        self.assertEqual(l["cloud:etat"]["commande"], ["nc-cloud", "etat"])
        self.assertEqual(l["cloud:dissocier"]["commande"], ["nc-cloud", "dissocier"])
        self.assertTrue(l["cloud:dissocier"]["confirmer"])
        nom = l["cloud:etat-local"]["aide"]
        self.assertTrue(nom.startswith("mon-pc") and nom.isprintable() and len(nom) <= 64, nom)

    def test_appareil_illisible_reste_associe_sans_nom(self):
        app = self.home / ".local/state/nc-cloud/appareil.json"
        app.parent.mkdir(parents=True)
        app.write_text("[1, 2")
        l = self.lignes({"CLOUD_JARVIS": "oui"})
        self.assertIn("cloud:dissocier", l)
        self.assertEqual(l["cloud:etat-local"]["aide"], "")


if __name__ == "__main__":
    unittest.main()

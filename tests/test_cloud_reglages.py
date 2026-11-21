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
        self.assertEqual(list(l), ["CLOUD_JARVIS", "cloud:etat-local", "cloud:verifier", "cloud:etat", "cloud:bureau-sauver",
                                   "cloud:bureau-reprendre", "cloud:dissocier"])
        self.assertEqual(l["cloud:etat"]["commande"], ["nc-cloud", "etat"])
        self.assertEqual(l["cloud:dissocier"]["commande"], ["nc-cloud", "dissocier"])
        self.assertTrue(l["cloud:dissocier"]["confirmer"])
        nom = l["cloud:etat-local"]["aide"]
        self.assertTrue(nom.startswith("mon-pc") and nom.isprintable() and len(nom) <= 64, nom)

    def test_bureau_en_deux_temps_liste_avant_confirmation(self):
        app = self.home / ".local/state/nc-cloud/appareil.json"
        app.parent.mkdir(parents=True)
        app.write_text(json.dumps({"device_id": "d1", "name": "pc"}))
        l = self.lignes({"CLOUD_JARVIS": "oui"})
        self.assertEqual(l["cloud:bureau-sauver"]["commande"], ["nc-cloud", "bureau", "preparer"])
        self.assertEqual(l["cloud:bureau-reprendre"]["commande"], ["nc-cloud", "bureau", "telecharger"])
        self.assertIn("photo de profil", l["cloud:bureau-sauver"]["aide"])
        self.assertNotIn("cloud:bureau-envoyer", l)
        pret = self.home / ".local/state/nc-cloud/bureau/pret.json"
        pret.parent.mkdir()
        for sens, cle, cmd in (("envoi", "cloud:bureau-envoyer", "envoyer"), ("reprise", "cloud:bureau-restaurer", "restaurer")):
            with self.subTest(sens):
                pret.write_text(json.dumps({"sens": sens, "fichier": "x", "lignes": ["• ~/.face\u001b[31m\u202e", "y" * 400] + ["z"] * 100}))
                l = self.lignes({"CLOUD_JARVIS": "oui"})
                d = l["cloud:bureau-liste"]["details"]
                self.assertTrue(all(x.isprintable() and len(x) <= 300 for x in d) and len(d) == 60, d[:2])
                self.assertEqual(l[cle]["commande"], ["nc-cloud", "bureau", cmd])
                self.assertTrue(l[cle]["confirmer"])
                self.assertEqual(l["cloud:bureau-oublier"]["commande"], ["nc-cloud", "bureau", "oublier"])
                self.assertNotIn("--avec-code", " ".join(x for v in l.values() for x in v.get("commande") or []))
        for mauvais in ("[1", json.dumps({"sens": "autre", "lignes": []}), json.dumps({"sens": "envoi", "lignes": "x"})):
            pret.write_text(mauvais)
            self.assertNotIn("cloud:bureau-liste", self.lignes({"CLOUD_JARVIS": "oui"}))

    def test_liste_blanche_du_cloud_chaque_section_classee(self):
        # Une section nouvelle du catalogue, non classée : ce test échoue (et elle ne part pas)
        self.assertEqual({r.section for r in self.nc["REGLAGES"]}, set(self.nc["SECTIONS_CLOUD"]))
        pc = self.nc["pour_le_cloud"]
        for cle, v in (("GARMIN_JARVIS", "oui"), ("DICTEE_SECOURS", "oui"), ("NOTIFS_IA", "oui"), ("TELEGRAM_AGENTS", "oui"),
                       ("VPN_KILLSWITCH", "non"), ("VPN_IP_PUBLIQUE", "oui"), ("VPN_IP_SERVICE", "https://x"), ("CLOUD_JARVIS", "oui"),
                       ("VEILLE_VERROU", "0"), ("IA_MODE", "non"), ("SPOTLIGHT_IA", "jarvis"), ("IA_CHALEUR", "oui"),
                       ("GOOGLE_INTEGRATION", "oui"), ("MAJ_SYSTEME", "auto"), ("NOEUD_JARVIS", "oui"), ("ALERTES_TELEGRAM", "oui"),
                       ("SESSIONS_CAPTURE", "oui"), ("SESSION_DEMARRAGE", "vide"), ("VERROU_PHOTO", "oui"), ("ANIM_VERROU", "fade"),
                       ("HZ_ECO", "60"), ("CAPTURES_COPIER", "oui"), ("APPLI_TERMINAL", "kitty"), ("CODE_AGENT", "auto"),
                       ("ECRAN_VRR", "non"), ("POLICE", "x"), ("INCONNU", "1"), ("DOCK_TAILLE", "99999"), ("DOCK", "peut-être")):
            self.assertIsNone(pc(cle, v), cle)
        for r in self.nc["REGLAGES"]:                     # aucun texte libre ni dossier
            if r.genre in ("texte", "dossier", "hz"):
                self.assertIsNone(pc(r.cle, r.defaut), r.cle)
        self.assertEqual((pc("LANGUE", "en"), pc("DOCK", "yes"), pc("ILE_PAGE_MUSIQUE", "non")), ("en", "oui", "non"))
        phrase = self.nc["familles_cloud"]()
        self.assertIn("barre et dock", phrase)
        self.assertIn("santé garmin", phrase)

    def test_appareil_illisible_reste_associe_sans_nom(self):
        app = self.home / ".local/state/nc-cloud/appareil.json"
        app.parent.mkdir(parents=True)
        app.write_text("[1, 2")
        l = self.lignes({"CLOUD_JARVIS": "oui"})
        self.assertIn("cloud:dissocier", l)
        self.assertEqual(l["cloud:etat-local"]["aide"], "")


if __name__ == "__main__":
    unittest.main()

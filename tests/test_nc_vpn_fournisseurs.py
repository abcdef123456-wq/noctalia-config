"""nc-vpn fournisseurs-json : format stable du contrat (docs/vpn-contrat.md), trois fournisseurs, « pays » seulement à l'état prêt,
clés fixes, commandes inconnues, aide. PATH = faux-bin seul."""
import json
import unittest

from tests._vpn_faux import BaseVpn
from tests.test_nc_vpn_nord import ANSI_COMPTE, PAYS

CLES = {"id", "nom", "etat", "message", "pays_actif", "connecte", "peut_login", "probleme", "pilotage"}


class Fournisseurs(BaseVpn):
    def lire(self):
        r = self.seul("fournisseurs-json")
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)

    def test_trois_fournisseurs_cles_stables(self):
        d = self.lire()
        self.assertEqual(d["contrat"], 1)
        self.assertEqual([f["id"] for f in d["fournisseurs"]], ["nord", "proton", "mullvad"])
        for f in d["fournisseurs"]:
            self.assertIn(f["etat"], ("absent", "sans_compte", "pret"))
            self.assertEqual(set(f) - {"pays"}, CLES)
            self.assertEqual("pays" in f, f["etat"] == "pret")
            self.assertTrue(f["message"])
            self.assertIsInstance(f["connecte"], bool)

    def test_messages_dans_les_deux_langues(self):
        fr = self.seul("fournisseurs-json", NC_LANGUE="fr")
        en = self.seul("fournisseurs-json", NC_LANGUE="en")
        for a, b in zip(json.loads(fr.stdout)["fournisseurs"], json.loads(en.stdout)["fournisseurs"]):
            self.assertNotEqual(a["message"], b["message"])
        self.assertIn("pas installé", json.loads(fr.stdout)["fournisseurs"][0]["message"])
        self.assertIn("not installed", json.loads(en.stdout)["fournisseurs"][0]["message"])

    def test_etats_differents_en_meme_temps(self):
        self.poser("nordvpn", {"account": {"out": ANSI_COMPTE}, "countries": {"out": PAYS}, "status": {"out": "Status: Disconnected\n"}})
        self.poser("protonvpn-app", {})
        (self.r / "mullvad.json").write_text(json.dumps({"texte": "Disconnected", "compte": "Not logged in on any account",
                                                         "json": json.dumps({"state": "disconnected"})}))
        etats = {f["id"]: f["etat"] for f in self.lire()["fournisseurs"]}
        self.assertEqual(etats, {"nord": "pret", "proton": "pilote_appli", "mullvad": "sans_compte"})

    def test_commandes_inconnues(self):
        for args in (("fournisseur",), ("fournisseur", "inconnu", "login"), ("fournisseur", "nord"), ("fournisseur", "nord", "connecter"),
                     ("fournisseur", "nord", "login", "x"), ("fournisseurs-json", "x"), ("fournisseur", "nord", "connecter", "FR", "US")):
            r = self.seul(*args)
            self.assertEqual(r.returncode, 2, args)
            self.assertEqual(r.stdout, "")

    def test_aide_decrit_les_commandes(self):
        for langue in ("fr", "en"):
            r = self.seul("aide", NC_LANGUE=langue)
            self.assertIn("fournisseurs-json", r.stdout)
            self.assertIn("fournisseur nord|proton|mullvad", r.stdout)


if __name__ == "__main__":
    unittest.main()

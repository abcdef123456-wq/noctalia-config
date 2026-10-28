"""nc-vpn : Mullvad dans les fournisseurs (faux `mullvad` qui note ses arguments). Trois états ; le numéro de compte n'est jamais
lu (`account` n'est jamais lancé) ni montré ; pays de `relay list`, sinon la liste ISO intégrée ; connecter CC en argv exact,
code invalide refusé sans appel ; login sans saisie. PATH = faux-bin seul."""
import json
import time
import unittest

from tests._vpn_faux import BaseVpn

NUMERO = "1234567890123456"
RELAIS = ("Sweden (se)\n\tGothenburg (got) @ 57.70887°N, 11.97456°W\n\t\tse-got-wg-004 (192.0.2.10, 2001:db8::4) - hosted by Hote (Mullvad-owned)\n\n"
          "France (fr)\n\tParis (par) @ 48.85341°N, 2.3488°W\n\t\tfr-par-wg-001 (192.0.2.20) - hosted by Hote (rented)\n\n"
          "\x1b[1mGermany\x1b[0m (de)\n\n"
          "Pays Faux (zz)\n\n")
CONNECTE = json.dumps({"state": "connected", "details": {"location": {"country": "Sweden", "hostname": "se-got-wg-004"}}})


class MullvadEtats(BaseVpn):
    def fiche(self):
        r = self.seul("fournisseurs-json")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.sortie_vue = r.stdout + r.stderr
        return next(f for f in json.loads(r.stdout)["fournisseurs"] if f["id"] == "mullvad")

    def mv(self, **conf):
        (self.r / "mullvad.json").write_text(json.dumps(conf))

    def sans_mullvad(self):
        (self.r / "faux-bin" / "mullvad").unlink()

    def test_absent(self):
        self.sans_mullvad()
        f = self.fiche()
        self.assertEqual(f["etat"], "absent")
        self.assertNotIn("pays", f)
        self.assertEqual(self.appels_mullvad(), [])

    def test_installe_sans_compte(self):
        self.mv(json=json.dumps({"state": "disconnected"}), texte="Disconnected\nWarning: You are not logged in to an account.", relais=RELAIS)
        f = self.fiche()
        self.assertEqual((f["etat"], f["peut_login"]), ("sans_compte", True))
        self.assertNotIn("pays", f)
        self.assertTrue(all(a[0] == "status" for a in self.appels_mullvad()))

    def test_service_arrete_ni_pret_ni_connecte(self):
        self.mv(texte="Failed to connect to daemon", code=1)
        f = self.fiche()
        self.assertEqual((f["etat"], f["probleme"]), ("sans_compte", "demon"))
        self.assertFalse(f["connecte"])

    def test_pret_pays_de_relay_list(self):
        self.mv(json=json.dumps({"state": "disconnected"}), texte="Disconnected", relais=RELAIS)
        f = self.fiche()
        self.assertEqual(f["etat"], "pret")
        self.assertEqual(f["pays"], [{"code": "FR", "nom": "France"}, {"code": "DE", "nom": "Germany"}, {"code": "SE", "nom": "Sweden"}])
        self.assertEqual((f["connecte"], f["pays_actif"]), (False, ""))
        self.assertIn(["relay", "list"], self.appels_mullvad())

    def test_pret_connecte_pays_actif_sans_numero(self):
        self.mv(json=CONNECTE, texte="Connected\n    Account: " + NUMERO, relais=RELAIS)
        f = self.fiche()
        self.assertEqual((f["etat"], f["connecte"], f["pays_actif"]), ("pret", True, "SE"))
        self.assertNotIn(NUMERO, self.sortie_vue)
        self.assertTrue(all(a[0] in ("status", "relay") for a in self.appels_mullvad()))     # jamais « account »

    def test_liste_iso_de_secours(self):
        self.mv(json=json.dumps({"state": "disconnected"}), texte="Disconnected")          # relay list en échec
        f = self.fiche()
        codes = {p["code"] for p in f["pays"]}
        self.assertTrue({"FR", "SE", "DE", "US"} <= codes)
        self.assertTrue(all(len(p["code"]) == 2 and p["nom"] for p in f["pays"]))

    def test_connecter_argv_exact(self):
        self.mv(json=json.dumps({"state": "disconnected"}), texte="Disconnected")
        r = self.seul("fournisseur", "mullvad", "connecter", "FR")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.appels_mullvad(), [["relay", "set", "location", "fr"], ["connect"]])

    def test_code_pays_invalide_refuse_sans_appel(self):
        for mauvais in ("fr", "FRA", "ZZ", "F", "FR;id", "-h", "", "$(id)"):
            r = self.seul("fournisseur", "mullvad", "connecter", mauvais)
            self.assertEqual(r.returncode, 1, mauvais)
        self.assertEqual(self.appels_mullvad(), [])

    def test_deconnecter(self):
        r = self.seul("fournisseur", "mullvad", "deconnecter")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.appels_mullvad(), [["disconnect"]])

    def test_erreur_sans_numero(self):
        self.mv(echec="Error: account " + NUMERO + " refused")
        r = self.seul("fournisseur", "mullvad", "connecter", "FR")
        self.assertEqual(r.returncode, 1)
        self.assertNotIn(NUMERO, r.stdout + r.stderr)

    def test_login_ouvre_l_application(self):
        self.poser("mullvad-vpn", {})
        r = self.seul("fournisseur", "mullvad", "login")
        self.assertEqual(r.returncode, 0, r.stderr)
        for _ in range(50):
            if self.appels_de("mullvad-vpn"):
                break
            time.sleep(0.1)
        self.assertEqual(self.appels_de("mullvad-vpn"), [[]])
        self.assertEqual(self.appels_mullvad(), [])                           # pas de « mullvad account login » de notre part

    def test_login_sans_application_dit_le_terminal(self):
        r = self.seul("fournisseur", "mullvad", "login")
        self.assertEqual(r.returncode, 1)
        self.assertIn("mullvad account login", r.stderr)
        self.assertEqual(self.appels_mullvad(), [])


if __name__ == "__main__":
    unittest.main()

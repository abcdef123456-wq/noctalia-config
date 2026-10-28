"""nc-vpn : le fournisseur Proton (pas de CLI officielle : l'application `protonvpn-app`, remplacée ici par un faux qui note ses
arguments). Absent ; installé sans connexion Proton ; connexion « ProtonVPN … » détectée (prêt, sans liste de pays) ; choisir un
pays, se déconnecter, se connecter ouvrent seulement l'application ; aucune fermeture, aucun pkill. PATH = faux-bin seul."""
import json
import time
import unittest

from tests._vpn_faux import BaseVpn, connexions

UP = "55555555-5555-4555-8555-555555555555"


class Proton(BaseVpn):
    def fiche(self):
        r = self.seul("fournisseurs-json")
        self.assertEqual(r.returncode, 0, r.stderr)
        return next(f for f in json.loads(r.stdout)["fournisseurs"] if f["id"] == "proton")

    def proton_nm(self, active=True, nom="ProtonVPN FR#12"):
        (self.r / "etat.json").write_text(json.dumps(connexions() + [dict(uuid=UP, type="wireguard", active=active, dev="proton0", nom=nom)]))

    def attendre_app(self):
        for _ in range(50):
            if self.appels_de("protonvpn-app"):
                break
            time.sleep(0.1)
        return self.appels_de("protonvpn-app")

    def test_absent(self):
        f = self.fiche()
        self.assertEqual((f["etat"], f["pilotage"]), ("absent", "appli"))
        self.assertNotIn("pays", f)
        self.assertFalse(f["peut_login"])

    def test_installe_sans_connexion_proton(self):
        self.poser("protonvpn-app", {})
        f = self.fiche()                                                      # les connexions de test (Labo, Maison…) ne sont pas Proton
        self.assertEqual(f["etat"], "pilote_appli")                           # jamais « sans_compte » : le compte, c'est l'appli
        self.assertIn("application", f["message"])
        self.assertNotIn("pays", f)
        self.assertTrue(f["peut_login"])                                      # le bouton « Ouvrir Proton VPN »
        self.assertFalse(f["connecte"])
        self.assertEqual(self.appels_de("protonvpn-app"), [])                  # lire l'état ne lance pas l'appli

    def test_connexion_proton_montee(self):
        self.poser("protonvpn-app", {})
        self.proton_nm()
        f = self.fiche()
        self.assertEqual(f["etat"], "pilote_appli")
        self.assertNotIn("pays", f)                                           # le pays se choisit dans l'appli
        self.assertTrue(f["connecte"])
        self.assertEqual(f["pays_actif"], "FR")
        self.assertEqual(f["pilotage"], "appli")

    def test_connexion_proton_connue_mais_coupee(self):
        self.poser("protonvpn-app", {})
        self.proton_nm(active=False)
        f = self.fiche()
        self.assertEqual((f["etat"], f["connecte"], f["pays_actif"]), ("pilote_appli", False, ""))

    def test_connexion_proton_sans_l_appli_reste_absent(self):
        self.proton_nm()
        self.assertEqual(self.fiche()["etat"], "absent")                      # le client manque : jamais « prêt »

    def test_nom_proche_pas_proton(self):
        self.poser("protonvpn-app", {})
        self.proton_nm(nom="Protonic Labo")
        self.assertEqual(self.fiche()["etat"], "pilote_appli")
        self.assertFalse(self.fiche()["connecte"])

    def test_actions_ouvrent_seulement_l_appli(self):
        self.poser("protonvpn-app", {})
        for args in (("connecter", "FR"), ("deconnecter",), ("login",)):
            self.r.joinpath("appels-protonvpn-app.jsonl").unlink(missing_ok=True)
            r = self.seul("fournisseur", "proton", *args)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(self.attendre_app(), [[]], args)                 # aucun argument : pas de pilotage caché
        self.assertEqual(self.appels(), [])                                  # ni nmcli (pas de coupure de la connexion de l'appli)

    def test_connecter_code_invalide_n_ouvre_rien(self):
        self.poser("protonvpn-app", {})
        r = self.seul("fournisseur", "proton", "connecter", "fr")
        self.assertEqual(r.returncode, 1)
        time.sleep(0.3)
        self.assertEqual(self.appels_de("protonvpn-app"), [])

    def test_actions_sans_appli(self):
        for args in (("connecter", "FR"), ("deconnecter",), ("login",)):
            r = self.seul("fournisseur", "proton", *args)
            self.assertEqual(r.returncode, 1)
            self.assertIn("pas installé", r.stderr)


if __name__ == "__main__":
    unittest.main()

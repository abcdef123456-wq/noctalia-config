"""nc-vpn : le fournisseur Nord (CLI officielle `nordvpn`, remplacée ici par un faux qui note ses arguments). Trois états, pays
seulement à l'état prêt, code pays validé avant tout appel, connect en argv exact, login (URL vérifiée, jamais affichée), aucune
adresse e-mail ni jeton en sortie, sortie ANSI / animation, question interactive, permission refusée, délai. PATH = faux-bin seul."""
import importlib.machinery
import importlib.util
import json
import os
import time
import unittest
from unittest import mock

from tests._vpn_faux import BaseVpn, BIN

ANSI_COMPTE = ("\x1b[1;32mAccount information\x1b[0m\r\nEmail Address: moi@exemple.invalid\r\nVPN Service: Active until Jan 1, 2099\r\n"
               "Token: ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789\r\n")
ANIMATION = "\r- \r\\ \r| \r/ \r"
PAYS = ANIMATION + "France\r\nGermany\r\nUnited_States\r\nAtlantis\r\nBosnia_and_Herzegovina\r\nHong_Kong\r\n"
URL_OK = "https://nordaccount.com/oauth2/login?challenge=EXEMPLEJETONCHALLENGE0123456789"


def charger():
    chargeur = importlib.machinery.SourceFileLoader("nc_vpn_mod_nord", str(BIN))
    spec = importlib.util.spec_from_loader("nc_vpn_mod_nord", chargeur)
    m = importlib.util.module_from_spec(spec)
    chargeur.exec_module(m)
    return m


class Nord(BaseVpn):
    def fiche(self, **env):
        r = self.seul("fournisseurs-json", **env)
        self.assertEqual(r.returncode, 0, r.stderr)
        d = json.loads(r.stdout)
        self.assertEqual(d["contrat"], 1)
        self.sortie_vue = r.stdout + r.stderr
        return next(f for f in d["fournisseurs"] if f["id"] == "nord")

    def connecte(self):
        self.poser("nordvpn", {"account": {"out": ANSI_COMPTE}, "countries": {"out": PAYS},
                               "status": {"out": "Status: Connected\r\nCountry: France\r\nCity: Paris\r\n"}})

    def attendre_xdg(self):
        for _ in range(50):
            if self.appels_de("xdg-open"):
                break
            time.sleep(0.1)
        return self.appels_de("xdg-open")

    def test_absent_silencieux(self):
        f = self.fiche()
        self.assertEqual(f["etat"], "absent")
        self.assertNotIn("pays", f)
        self.assertFalse(f["connecte"] or f["peut_login"])
        self.assertTrue(f["message"])

    def test_installe_sans_compte(self):
        self.poser("nordvpn", {"account": {"err": "You're not logged in.\n", "code": 1}, "countries": {"out": PAYS}})
        f = self.fiche()
        self.assertEqual(f["etat"], "sans_compte")
        self.assertNotIn("pays", f)
        self.assertTrue(f["peut_login"])
        self.assertEqual(f["pays_actif"], "")
        self.assertEqual(self.appels_de("nordvpn"), [["account"]])           # les pays ne sont même pas demandés

    def test_pret_avec_pays_et_rien_de_prive(self):
        self.connecte()
        f = self.fiche()
        self.assertEqual(f["etat"], "pret")
        self.assertEqual(f["pays"], [{"code": "DE", "nom": "Allemagne"}, {"code": "BA", "nom": "Bosnie-Herzégovine"},
                                     {"code": "US", "nom": "États-Unis"}, {"code": "FR", "nom": "France"},
                                     {"code": "HK", "nom": "Hong Kong"}])    # Atlantis : sans code connu, écarté
        self.assertEqual(f["pays_actif"], "FR")
        self.assertTrue(f["connecte"])
        for interdit in ("exemple.invalid", "ABCDEFGHIJKLMNOP", "\x1b", "\r"):
            self.assertNotIn(interdit, self.sortie_vue)

    def test_pret_mais_deconnecte(self):
        self.poser("nordvpn", {"account": {"out": ANSI_COMPTE}, "countries": {"out": "France\n"},
                               "status": {"out": "Status: Disconnected\n"}})
        f = self.fiche()
        self.assertEqual((f["etat"], f["connecte"], f["pays_actif"]), ("pret", False, ""))

    def test_premiere_execution_question_interactive(self):
        self.poser("nordvpn", {"account": {"out": "We value your privacy.\nDo you allow us to collect and use limited app performance data? (y/n)", "code": 1}})
        debut = time.time()
        f = self.fiche()
        self.assertLess(time.time() - debut, 10)
        self.assertEqual((f["etat"], f["probleme"]), ("sans_compte", "consentement"))
        self.assertIn("terminal", f["message"])
        self.assertNotIn("pays", f)

    def test_question_interactive_qui_attend_ne_bloque_pas(self):
        m = charger()
        self.poser("nordvpn", {"account": {"out": "(y/n)", "dormir": 20}})
        with mock.patch.dict(os.environ, self.env(PATH=str(self.r / "faux-bin"))):
            debut = time.time()
            code, texte = m.cli_fournisseur("nordvpn", ["account"], delai=1)
        self.assertEqual((code, texte), (124, ""))
        self.assertLess(time.time() - debut, 8)
        self.assertEqual(m.probleme_cli(code, texte), "delai")
        self.assertIn("terminal", m.message_probleme("nord", "delai"))

    def test_permission_refusee_sur_le_socket(self):
        self.poser("nordvpn", {"*": {"err": "Permission denied. Please grant necessary permissions before using the application by "
                                           "executing the following commands:\n\nsudo groupadd nordvpn\nsudo usermod -aG nordvpn $USER\n", "code": 1}})
        f = self.fiche()
        self.assertEqual((f["etat"], f["probleme"]), ("sans_compte", "permission"))
        self.assertIn("groupe nordvpn", f["message"])
        self.assertFalse(f["peut_login"])
        self.assertEqual(self.appels_de("nordvpn"), [["account"]])           # ni sg, ni élévation, ni autre appel
        r = self.seul("fournisseur", "nord", "connecter", "FR")
        self.assertEqual(r.returncode, 1)
        self.assertIn("groupe nordvpn", r.stderr)
        self.assertNotIn(["connect"], [x[:1] for x in self.appels_de("nordvpn")])

    def test_connecter_argv_exact(self):
        self.connecte()
        r = self.seul("fournisseur", "nord", "connecter", "US")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.appels_de("nordvpn")[-1], ["connect", "United_States"])

    def test_code_pays_invalide_refuse_sans_appel(self):
        self.connecte()
        for mauvais in ("fr", "FRA", "F", "ZZ", "FR;id", "$(id)", "-h", "../x", "", "F R"):
            r = self.seul("fournisseur", "nord", "connecter", mauvais)
            self.assertEqual(r.returncode, 1, mauvais)
            self.assertIn("Code pays invalide", r.stderr)
        self.assertEqual(self.appels_de("nordvpn"), [])

    def test_pays_hors_liste_pas_de_connect(self):
        self.connecte()
        r = self.seul("fournisseur", "nord", "connecter", "JP")
        self.assertEqual(r.returncode, 1)
        self.assertNotIn("connect", [x[0] for x in self.appels_de("nordvpn")])

    def test_echec_connexion_filtre_url_et_jeton(self):
        self.connecte()
        self.regler("nordvpn", {"account": {"out": ANSI_COMPTE}, "countries": {"out": PAYS},
                                "connect": {"err": "failed nordvpn://login?exchange_token=EXEMPLEJETON0123456789ABCDEFGH moi@exemple.invalid\n", "code": 1}})
        r = self.seul("fournisseur", "nord", "connecter", "FR")
        self.assertEqual(r.returncode, 1)
        for interdit in ("exchange_token", "EXEMPLEJETON", "nordvpn://", "exemple.invalid"):
            self.assertNotIn(interdit, r.stderr + r.stdout)

    def test_deconnecter(self):
        self.poser("nordvpn", {})
        r = self.seul("fournisseur", "nord", "deconnecter")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.appels_de("nordvpn"), [["disconnect"]])

    def test_login_ouvre_l_url_verifiee_sans_la_montrer(self):
        self.poser("nordvpn", {"login": {"out": "\x1b[32mContinue in the browser: " + URL_OK + "\x1b[0m\r\n"}})
        self.poser("xdg-open", {})
        r = self.seul("fournisseur", "nord", "login")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.appels_de("nordvpn"), [["login"]])
        self.assertEqual(self.attendre_xdg(), [[URL_OK]])
        for interdit in ("challenge", "EXEMPLEJETON", "https://"):
            self.assertNotIn(interdit, r.stdout + r.stderr)

    def test_login_url_etrangere_refusee(self):
        self.poser("xdg-open", {})
        for url in ("https://evil.example/nordaccount.com", "http://nordaccount.com/x", "https://nordaccount.com.evil.example/",
                    "https://nordvpn.com@evil.example/", "https://user:pw@nordaccount.com/", "https://nordaccount.com:8443/",
                    "https://evilnordvpn.com/", "nordvpn://login?exchange_token=EXEMPLEJETON0123456789"):
            self.poser("nordvpn", {"login": {"out": "Continue in the browser: " + url + "\n"}})
            r = self.seul("fournisseur", "nord", "login")
            self.assertEqual(r.returncode, 1, url)
            self.assertNotIn("evil", r.stdout + r.stderr)
            self.assertNotIn("EXEMPLEJETON", r.stdout + r.stderr)
        time.sleep(0.3)
        self.assertEqual(self.appels_de("xdg-open"), [])

    def test_login_question_interactive(self):
        self.poser("nordvpn", {"login": {"out": "Do you allow us to collect and use limited app performance data? (y/n)", "code": 1}})
        self.poser("xdg-open", {})
        r = self.seul("fournisseur", "nord", "login")
        self.assertEqual(r.returncode, 1)
        self.assertIn("terminal", r.stderr)
        self.assertEqual(self.appels_de("xdg-open"), [])

    def test_domaines_nord(self):
        m = charger()
        for ok in ("https://nordaccount.com/a", "https://my.nordaccount.com/a?b=c", "https://nordvpn.com/", "https://nordaccount.com",
                   "https://nordaccount.com/oauth?x=%2Fy", "https://a-b.nordvpn.com/p%20q"):
            self.assertTrue(m.url_nord_sure(ok), ok)
        for mauvais in ("https://evil.example\\.nordvpn.com/", "https://evil.example%2f.nordvpn.com/", "https://evil.example%5c.nordvpn.com/",
                        "https://evil.example;.nordvpn.com/", 'https://evil.example".nordvpn.com/', "https://evil.example'.nordvpn.com/",
                        "https://evil.example`.nordvpn.com/", "https://evil.example{.nordvpn.com/", "https://evil.example|.nordvpn.com/",
                        "https://evil.example^.nordvpn.com/", "https://nordvpn.com@evil.example/", "https://evil.example#.nordvpn.com",
                        "https://nordaccount.com\\@evil.example/", "https://nordaccount.com/a\\b", "https://nord%61ccount.com/",
                        "https://nordaccount.com/a'b", "https://nordaccount.com/a{b", "https://NordAccount.com/x", "https://nordaccount.com./x"):
            self.assertFalse(m.url_nord_sure(mauvais), mauvais)
        for mauvais in ("", None, "https://nordaccount.com/a b", "https://nordaccount.com/\n", "ftp://nordvpn.com/", "https://127.0.0.1/"):
            self.assertFalse(m.url_nord_sure(mauvais), repr(mauvais))

    def test_sortie_ansi_et_bornee(self):
        m = charger()
        t = m.nettoyer_sortie(b"\x1b[1;31mErreur\x1b[0m\r\n\x1b]0;titre\x07" + b"x" * 200000)
        self.assertTrue(t.startswith("Erreur\n"))
        self.assertNotIn("\x1b", t)
        self.assertLessEqual(len(t), 70000)

    def test_filtre_secret(self):
        m = charger()
        s = m.filtre_secret("bad https://nordaccount.com/x?token=abc a@b.invalid 123456789012345 ABCDEFGHIJKLMNOPQRSTUVWXYZ012345")
        for interdit in ("https", "token=abc", "a@b.invalid", "123456789012345", "ABCDEFGHIJKLMNOPQRSTUVWXYZ"):
            self.assertNotIn(interdit, s)

    def test_nord_installe_ne_fait_pas_un_tunnel(self):
        # Nord installé (connecté dans son compte) mais seul un tunnel Proton est monté : la pilule dit Proton
        import json as j
        self.connecte()
        (self.r / "etat.json").write_text(j.dumps([dict(uuid="55555555-5555-4555-8555-555555555555", type="wireguard", active=True,
                                                         dev="proton0", nom="ProtonVPN FR#12")]))
        r = self.seul("indicateur", "--json")
        d = json.loads(r.stdout)
        self.assertEqual((d["actif"], d["fournisseur"], d["pays"]), (True, "Proton VPN", "FR"))
        self.assertEqual(self.appels_de("nordvpn"), [])                      # l'indicateur ne regarde jamais la CLI Nord


if __name__ == "__main__":
    unittest.main()

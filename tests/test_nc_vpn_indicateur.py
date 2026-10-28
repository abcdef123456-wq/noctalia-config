"""nc-vpn indicateur --json : le tunnel RÉELLEMENT monté (jamais un client installé), fournisseur et pays déduits des noms sans
réseau, code pays validé, plusieurs tunnels, un seul appel nmcli, aucun secret. Faux nmcli seulement (tests/_vpn_faux.py)."""
import importlib.machinery
import importlib.util
import json
import sys
import unittest

from tests._vpn_faux import BaseVpn, BIN, U1, U2, U3


def charger():
    chargeur = importlib.machinery.SourceFileLoader("nc_vpn_mod", str(BIN))
    spec = importlib.util.spec_from_loader("nc_vpn_mod", chargeur)
    m = importlib.util.module_from_spec(spec)
    chargeur.exec_module(m)
    return m


class Motifs(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = charger()

    def test_fournisseurs_par_nom_ou_interface(self):
        f = self.m.fournisseur_de
        self.assertEqual(f("ProtonVPN FR#12", "proton0"), "Proton VPN")
        self.assertEqual(f("Labo", "proton0"), "Proton VPN")                 # l'interface suffit
        self.assertEqual(f("mullvad-fr1", "wg-mullvad"), "Mullvad")
        self.assertEqual(f("fr123.nordvpn.com.udp", "tun0"), "NordVPN")
        self.assertEqual(f("Labo", "nordlynx"), "NordVPN")
        self.assertEqual(f("PIA_de-berlin", "tun0"), "Private Internet Access")
        self.assertEqual(f("Surfshark - US NYC", ""), "Surfshark")
        self.assertEqual(f("Maison", "wg-maison"), "")
        self.assertEqual(f("Pianiste", "tun0"), "")                          # « pia » collé à d'autres lettres ne compte pas
        self.assertEqual(f("northwind", "tun0"), "")

    def test_pays_valides_seulement(self):
        p = self.m.pays_de
        self.assertEqual(p("ProtonVPN FR#12"), "FR")
        self.assertEqual(p("mullvad-fr1"), "FR")
        self.assertEqual(p("fr123.nordvpn.com.udp"), "FR")
        self.assertEqual(p("fr-par-wg-001"), "FR")
        self.assertEqual(p("Surfshark - US NYC"), "US")
        self.assertEqual(p("uk-london"), "GB")
        self.assertEqual(p("Maison"), "")
        self.assertEqual(p("Home it office"), "")                            # « it » en minuscules au milieu : un mot, pas un pays
        self.assertEqual(p("ZZ-test"), "")                                   # deux lettres mais pas un code ISO
        self.assertEqual(p("wg0 vpn"), "")
        self.assertEqual(p(""), "")

    def test_nom_borne_et_sans_controle(self):
        n = self.m.nom_borne("A\x1b[31mB\nC" + "x" * 100)
        self.assertNotIn("\x1b", n)
        self.assertNotIn("\n", n)
        self.assertLessEqual(len(n), 40)


class Indicateur(BaseVpn):
    def ecrire(self, lignes):
        (self.r / "etat.json").write_text(json.dumps(lignes))

    def ind(self, **plus):
        r = self.vpn("indicateur", "--json", **plus)
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)

    def test_client_installe_mais_pas_monte_ne_compte_pas(self):
        self.ecrire([dict(uuid=U1, type="vpn", active=False, dev="", nom="ProtonVPN FR#12"),
                     dict(uuid=U2, type="wireguard", active=False, dev="", nom="mullvad-fr1")])
        self.assertEqual(self.ind(), dict(disponible=True, actif=False, fournisseur="", pays="", nom="", nombre=0, mullvad=True))

    def test_le_tunnel_reellement_monte_donne_le_fournisseur(self):
        self.ecrire([dict(uuid=U1, type="vpn", active=False, dev="", nom="ProtonVPN FR#12"),
                     dict(uuid=U2, type="wireguard", active=True, dev="wg-mullvad", nom="mullvad-de3")])
        self.assertEqual(self.ind(), dict(disponible=True, actif=True, fournisseur="Mullvad", pays="DE", nom="mullvad-de3", nombre=1, mullvad=True))

    def test_nom_inconnu_seulement_le_nom(self):
        self.ecrire([dict(uuid=U1, type="vpn", active=True, dev="tun0", nom="Labo")])
        self.assertEqual(self.ind(), dict(disponible=True, actif=True, fournisseur="", pays="", nom="Labo", nombre=1, mullvad=True))

    def test_plusieurs_tunnels_le_premier_et_le_nombre(self):
        self.ecrire([dict(uuid=U1, type="vpn", active=True, dev="proton0", nom="Labo"),
                     dict(uuid=U2, type="wireguard", active=True, dev="wg0", nom="Maison"),
                     dict(uuid=U3, type="vpn", active=True, dev="tun1", nom="Bureau")])
        d = self.ind()
        self.assertEqual((d["fournisseur"], d["nom"], d["nombre"]), ("Proton VPN", "Labo", 3))

    def test_un_seul_appel_nmcli_en_argv_sans_reseau_ni_secret(self):
        self.ecrire([dict(uuid=U1, type="vpn", active=True, dev="tun0", nom="ProtonVPN FR#12")])
        r = self.vpn("indicateur", "--json")
        appels = self.appels()
        self.assertEqual(len(appels), 1, appels)
        self.assertEqual(appels[0][-2:], ["connection", "show"])
        self.assertNotIn("--show-secrets", appels[0])
        self.assertNotIn("-s", appels[0])
        self.assertEqual(set(json.loads(r.stdout)), {"disponible", "actif", "fournisseur", "pays", "nom", "nombre", "mullvad"})
        source = BIN.read_text()
        corps = source[source.index("def indicateur():"):source.index("# ── Application officielle Mullvad")]
        self.assertNotIn("urllib", corps)
        self.assertNotIn("socket", corps)

    def test_networkmanager_arrete(self):
        d = self.ind(NM_ARRETE="1")
        self.assertEqual(d, dict(disponible=False, actif=False, fournisseur="", pays="", nom="", nombre=0, mullvad=True))

    def test_arguments_inattendus_refuses(self):
        self.assertEqual(self.vpn("indicateur").returncode, 2)
        self.assertEqual(self.vpn("indicateur", "--json", "x").returncode, 2)


NUMERO = "1234567890123456"          # faux numéro de compte : ne doit jamais ressortir
CONF_MULLVAD = """[Interface]
# Device: Appareil de test
PrivateKey = FAUSSE-CLE-DE-TEST-0000000000000000000000000=
Address = 10.64.0.2/32,fc00:bbbb:bbbb:bb01::2/128
DNS = 10.64.0.1

[Peer]
PublicKey = FAUSSE-CLE-PUBLIQUE-000000000000000000000000=
AllowedIPs = 0.0.0.0/0,::0/0
Endpoint = 192.0.2.10:51820
"""
JSON_CONNECTE = json.dumps({"state": "connected", "details": {"endpoint": {"address": "192.0.2.10:51820"},
                            "location": {"country": "Sweden", "hostname": "se-got-wg-004", "account": NUMERO}}})


class MullvadSansApplication(BaseVpn):
    def test_fichier_wireguard_du_generateur_importe_puis_reconnu(self):
        (self.r / "etat.json").write_text("[]")
        f = self.r / "home" / "se-got-wg-001.conf"
        f.write_text(CONF_MULLVAD)
        r = self.vpn("importer", str(f))
        self.assertEqual(r.returncode, 0, r.stderr)
        etat = json.loads((self.r / "etat.json").read_text())
        etat[0]["active"] = True                                   # le tunnel est monté
        (self.r / "etat.json").write_text(json.dumps(etat))
        d = json.loads(self.vpn("indicateur", "--json").stdout)
        self.assertEqual((d["fournisseur"], d["pays"], d["nom"]), ("Mullvad", "SE", "se-got-wg-001"))
        self.assertNotIn("FAUSSE-CLE", self.vpn("indicateur", "--json").stdout)


class MullvadApplication(BaseVpn):
    def mv(self, **conf):
        (self.r / "mullvad.json").write_text(json.dumps(conf))

    def ind(self, **plus):
        r = self.vpn("indicateur", "--json", **plus)
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)

    def test_application_connectee_hors_networkmanager(self):
        (self.r / "etat.json").write_text("[]")
        self.mv(json=JSON_CONNECTE)
        r = self.vpn("indicateur", "--json")
        d = json.loads(r.stdout)
        self.assertEqual((d["actif"], d["fournisseur"], d["pays"], d["nombre"]), (True, "Mullvad", "SE", 1))
        self.assertEqual(self.appels_mullvad(), [["status", "--json"]])
        self.assertNotIn(NUMERO, r.stdout + r.stderr)

    def test_application_deconnectee_ne_compte_pas(self):
        (self.r / "etat.json").write_text("[]")
        self.mv(json=json.dumps({"state": "disconnected", "details": {"locked_down": False}}))
        self.assertFalse(self.ind()["actif"])

    def test_un_tunnel_networkmanager_monte_passe_avant_et_mullvad_n_est_pas_lu(self):
        (self.r / "etat.json").write_text(json.dumps([dict(uuid=U1, type="vpn", active=True, dev="tun0", nom="Labo")]))
        self.mv(json=JSON_CONNECTE)
        d = self.ind()
        self.assertEqual((d["fournisseur"], d["nom"]), ("", "Labo"))
        self.assertEqual(self.appels_mullvad(), [])

    def test_sans_la_commande_mullvad(self):
        (self.r / "faux-bin" / "mullvad").unlink()
        bin2 = self.r / "bin2"
        bin2.mkdir()
        (bin2 / "nmcli").symlink_to(self.r / "faux-bin" / "nmcli")
        (bin2 / "python3").symlink_to(sys.executable)
        (self.r / "etat.json").write_text("[]")
        d = self.ind(PATH=str(bin2))
        self.assertEqual((d["actif"], d["mullvad"]), (False, False))

    def test_actions_en_argv_et_code_pays_valide(self):
        for args, attendu in ((["connecter"], ["connect"]), (["deconnecter"], ["disconnect"]),
                              (["pays", "fr"], ["relay", "set", "location", "fr"])):
            self.assertEqual(self.vpn("mullvad", *args).returncode, 0)
            self.assertEqual(self.appels_mullvad()[-1], attendu)
        n = len(self.appels_mullvad())
        for mauvais in ("FR", "f", "fra", "-x", "f1", "zz", "fr;ls"):
            self.assertEqual(self.vpn("mullvad", "pays", mauvais).returncode, 1, mauvais)
        self.assertEqual(len(self.appels_mullvad()), n, "aucun appel pour un code invalide")

    def test_etat_json_compte_sans_numero(self):
        self.mv(json=JSON_CONNECTE)
        r = self.vpn("mullvad", "etat-json")
        d = json.loads(r.stdout)
        self.assertEqual((d["installe"], d["connecte"], d["pays"], d["hote"], d["compte"]), (True, True, "SE", "se-got-wg-004", True))
        self.assertNotIn(NUMERO, r.stdout + r.stderr)
        self.mv(json=json.dumps({"state": "disconnected"}), texte="Disconnected\nWarning: You are not logged in to an account.")
        d = json.loads(self.vpn("mullvad", "etat-json").stdout)
        self.assertEqual((d["connecte"], d["compte"]), (False, False))
        self.assertTrue(all(a[0] in ("status",) for a in self.appels_mullvad()))     # jamais « account »

    def test_pays_json_liste_les_pays_du_relais(self):
        self.mv(relais="Sweden (se)\n\tGothenburg (got) @ 57.7N, 11.9E\n\t\tse-got-wg-004 (192.0.2.4) - WireGuard\n"
                       "France (fr)\n\tParis (par)\nNowhere (zz)\nSweden (se)\n")
        r = self.vpn("mullvad", "pays-json")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(r.stdout), {"pays": [{"cc": "FR", "nom": "France"}, {"cc": "SE", "nom": "Sweden"}]})
        self.assertEqual(self.appels_mullvad(), [["relay", "list"]])

    def test_numero_de_compte_jamais_remonte_dans_une_erreur(self):
        self.mv(echec="Error: account 1234 5678 9012 3456 refused " + NUMERO)
        r = self.vpn("mullvad", "connecter")
        self.assertEqual(r.returncode, 1)
        self.assertNotIn(NUMERO, r.stdout + r.stderr)
        self.assertNotIn("1234 5678", r.stdout + r.stderr)
        self.assertIn("nc-vpn", r.stderr)


if __name__ == "__main__":
    unittest.main()

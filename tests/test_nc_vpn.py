"""nc-vpn : lecture des connexions VPN / WireGuard de NetworkManager (nmcli -t avec « \\: »), connecter, déconnecter,
tout déconnecter, UUID strict, NetworkManager absent. Faux nmcli seulement (tests/_vpn_faux.py)."""
import json
import unittest

from tests._vpn_faux import BaseVpn, U1, U2, U3, U4


class EtatVpn(BaseVpn):
    def test_etat_json_garde_vpn_et_wireguard_et_les_deux_actifs(self):
        r = self.vpn("etat-json")
        self.assertEqual(r.returncode, 0, r.stderr)
        d = json.loads(r.stdout)
        self.assertTrue(d["disponible"])
        self.assertEqual([c["uuid"] for c in d["connexions"]], [U1, U2, U3])       # le Wi-Fi n'en est pas
        self.assertEqual({c["uuid"] for c in d["actives"]}, {U2, U3})              # plusieurs tunnels à la fois
        par = {c["uuid"]: c for c in d["connexions"]}
        self.assertEqual(par[U2], dict(uuid=U2, nom="Maison: 192.0.2.1", type="wireguard", active=True, interface="wg-maison"))
        self.assertEqual(par[U3]["nom"], "Bureau\\ 2001:db8::1")                   # « : » et antislash échappés par nmcli -t
        self.assertEqual(par[U1], dict(uuid=U1, nom="Labo", type="vpn", active=False, interface=""))

    def test_nmcli_en_arguments_et_champs_explicites(self):
        self.vpn("etat-json")
        a = self.appels()[0]
        self.assertIn("-t", a)
        self.assertEqual(a[a.index("-f") + 1], "UUID,TYPE,ACTIVE,DEVICE,NAME")
        self.assertEqual(a[-2:], ["connection", "show"])

    def test_networkmanager_arrete_ou_nmcli_absent(self):
        r = self.vpn("etat-json", NM_ARRETE="1")
        self.assertEqual(json.loads(r.stdout), {"contrat": 1, "disponible": False})
        (self.r / "faux-bin" / "nmcli").unlink()
        r = self.vpn("etat-json", PATH=str(self.r / "etat"))        # aucun nmcli nulle part
        self.assertEqual((r.returncode, json.loads(r.stdout)), (0, {"contrat": 1, "disponible": False}))
        self.assertEqual(r.stderr, "")

    def test_liste_en_clair(self):
        r = self.vpn("liste")
        self.assertIn("Labo", r.stdout)
        self.assertIn("* Maison: 192.0.2.1", r.stdout)

    def test_langue_anglaise(self):
        r = self.vpn("connecter", "pas-un-uuid", NC_LANGUE="en")
        self.assertEqual(r.returncode, 1)
        self.assertIn("Invalid UUID", r.stderr)


class PiloterVpn(BaseVpn):
    def test_connecter_en_argv_par_uuid(self):
        r = self.vpn("connecter", U1)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn(["connection", "up", "uuid", U1], self.appels())
        self.assertEqual(self.etat_actifs(), {U1, U2, U3, U4})                  # les autres tunnels restent montés

    def test_connecter_un_tunnel_deja_actif_ne_fait_rien(self):
        r = self.vpn("connecter", U2)
        self.assertEqual(r.returncode, 0)
        self.assertFalse(any(a[:2] == ["connection", "up"] for a in self.appels()))

    def test_deconnecter_et_deja_deconnecte(self):
        self.assertEqual(self.vpn("deconnecter", U2).returncode, 0)
        self.assertEqual(self.etat_actifs(), {U3, U4})
        n = len(self.appels())
        r = self.vpn("deconnecter", U1)                                         # jamais monté : sans effet, sans erreur
        self.assertEqual(r.returncode, 0)
        self.assertFalse(any(a[:2] == ["connection", "down"] for a in self.appels()[n:]))

    def test_tout_deconnecter_ne_touche_que_les_tunnels(self):
        r = self.vpn("tout-deconnecter")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.etat_actifs(), {U4})                              # le Wi-Fi reste connecté
        self.assertFalse(any(a[3:4] == [U4] for a in self.appels() if a[:2] == ["connection", "down"]))

    def test_uuid_invalide_refuse_sans_appeler_nmcli(self):
        for mauvais in ("", "abc", U1 + "x", U1.replace("-", ""), "; touch x", "$(id)", "../" + U1, U1[:-1] + "g", "--help", U1 + "\n"):
            for cmd in ("connecter", "deconnecter"):
                n = len(self.appels())
                r = self.vpn(cmd, mauvais)
                self.assertNotEqual(r.returncode, 0, (cmd, mauvais))
                self.assertEqual(len(self.appels()), n, "nmcli n'est pas appelé avec un UUID invalide : " + repr(mauvais))

    def test_uuid_d_une_connexion_qui_n_est_pas_un_tunnel_refuse(self):
        r = self.vpn("deconnecter", U4)                                         # le Wi-Fi
        self.assertEqual(r.returncode, 1)
        self.assertEqual(self.etat_actifs(), {U2, U3, U4})

    def test_echec_de_nmcli_dit_en_clair(self):
        r = self.vpn("connecter", U1, NM_ECHEC_UP="1")
        self.assertEqual(r.returncode, 1)
        self.assertIn("Connexion impossible", r.stderr)

    def test_networkmanager_arrete_pour_connecter(self):
        r = self.vpn("connecter", U1, NM_ARRETE="1")
        self.assertEqual(r.returncode, 1)
        self.assertIn("NetworkManager", r.stderr)

    def test_usage_et_commande_inconnue(self):
        self.assertEqual(self.vpn("--help").returncode, 0)
        self.assertEqual(self.vpn("nimporte").returncode, 2)
        self.assertEqual(self.vpn("connecter").returncode, 2)

    def test_ip_publique_jamais_sans_reglage(self):
        r = self.vpn("ip-publique")
        self.assertEqual(json.loads(r.stdout), {"ip": ""})
        cfg = self.r / "home/.config/nc"
        cfg.mkdir(parents=True)
        (cfg / "reglages.conf").write_text('VPN_IP_PUBLIQUE="oui"\nVPN_IP_SERVICE="http://192.0.2.9/ip"\n')   # http : refusé
        d = json.loads(self.vpn("ip-publique").stdout)
        self.assertEqual(d["ip"], "")
        self.assertIn("https", d["erreur"])


class Installation(unittest.TestCase):
    """install.sh : le module OpenVPN de NetworkManager est facultatif, avec le bon nom sur chaque distribution ;
    WireGuard est intégré à NetworkManager et au noyau (aucun paquet)."""
    def test_noms_de_paquet_par_distribution(self):
        import subprocess
        from tests._vpn_faux import REPO
        texte = (REPO / "install.sh").read_text()
        debut = texte.index("pname() {")
        fonction = texte[debut:texte.index("\n}\n", debut) + 3]
        for famille, attendu in (("arch", "networkmanager-openvpn"), ("debian", "network-manager-openvpn"),
                                 ("fedora", "NetworkManager-openvpn"), ("suse", "NetworkManager-openvpn")):
            r = subprocess.run(["bash", "-c", fonction + f"FAMILY={famille}; pname nm-openvpn"], capture_output=True, text=True)
            self.assertEqual(r.stdout.strip(), attendu, famille)

    def test_paquet_secret_tool_par_distribution(self):
        import subprocess
        from tests._vpn_faux import REPO
        texte = (REPO / "install.sh").read_text()
        debut = texte.index("pname() {")
        fonction = texte[debut:texte.index("\n}\n", debut) + 3]
        for famille, attendu in (("arch", "libsecret"), ("debian", "libsecret-tools"), ("fedora", "libsecret"), ("suse", "secret-tool")):
            r = subprocess.run(["bash", "-c", fonction + f"FAMILY={famille}; pname secret-tool"], capture_output=True, text=True)
            self.assertEqual(r.stdout.strip(), attendu, famille)
        i = texte.index("FACULTATIFS=(")
        self.assertIn("secret-tool", texte[i:texte.index(")", i)].split())
        self.assertIn("secret-tool", texte[texte.index("GENERIC=("):texte.index(")", texte.index("GENERIC=("))].split())

    def test_facultatif_sur_arch_et_sans_wireguard_tools(self):
        from tests._vpn_faux import REPO
        texte = (REPO / "install.sh").read_text()
        i = texte.index("FACULTATIFS=(")
        self.assertIn("nm-openvpn", texte[i:texte.index(")", i)].split())
        self.assertIn("nm-openvpn", texte[texte.index("GENERIC=("):texte.index(")", texte.index("GENERIC=("))].split())
        self.assertNotRegex(texte, r"(?m)^\s*wireguard-tools:|pkg_install[^\n]*wireguard")


if __name__ == "__main__":
    unittest.main()

"""nc-vpn killswitch (côté utilisateur) : réglage coupé par défaut, limites affichées AVANT l'activation, tunnel retrouvé (OpenVPN
avec le Wi-Fi comme device de base), endpoints en IP (jamais un nom, jamais un multi-remote), appel de l'assistant par
« sudo -n » en arguments. Faux nmcli, gdbus, ip, sudo, mullvad, faux /sys (NC_VPN_SYSFS) : jamais les vrais. Adresses de
documentation seulement (192.0.2.x, 198.51.100.x, 2001:db8::)."""
import json
import os
from pathlib import Path
import unittest

from tests._vpn_faux import BaseVpn, U1, U2, U3

FAUX_SUDO = r'''#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
R = Path(os.environ["FAUX_DIR"])
a = sys.argv[1:]
with (R / "appels-sudo.jsonl").open("a") as f: f.write(json.dumps(a) + "\n")
if os.environ.get("SUDO_MOT_DE_PASSE") == "1":
    print("sudo: a password is required", file=sys.stderr); sys.exit(1)
if os.environ.get("SUDO_REFUS"):
    print("nc-vpn-root: " + os.environ["SUDO_REFUS"], file=sys.stderr); sys.exit(3)
if a[2:3] == ["etat"]:
    print((R / "ks-etat").read_text().strip() if (R / "ks-etat").exists() else "inactif")
'''
FAUX_IP = r'''#!/usr/bin/env python3
import os, sys
from pathlib import Path
R = Path(os.environ["FAUX_DIR"])
print((R / "ip.json").read_text() if (R / "ip.json").exists() else "[]")
'''

LIGNES = ["Limites du kill switch :"]


class KillSwitch(BaseVpn):
    def setUp(self):
        super().setUp()
        for nom, corps in (("sudo", FAUX_SUDO), ("ip", FAUX_IP)):
            f = self.r / "faux-bin" / nom
            f.write_text(corps)
            f.chmod(0o755)
        self.helper = self.r / "nc-vpn-root"
        self.helper.write_text("#!/bin/sh\n")
        self.sysfs = self.r / "sysfs"
        self.cfg_reglage("oui")

    def cfg_reglage(self, v):
        d = self.r / "home/.config/nc"
        d.mkdir(parents=True, exist_ok=True)
        (d / "reglages.conf").write_text('VPN_KILLSWITCH="%s"\n' % v)

    def iface(self, nom, tun=False, wireguard=False):
        d = self.sysfs / "class/net" / nom
        d.mkdir(parents=True, exist_ok=True)
        (d / "uevent").write_text("INTERFACE=%s\n%s" % (nom, "DEVTYPE=wireguard\n" if wireguard else ""))
        if tun:
            (d / "tun_flags").write_text("0x1002\n")

    def connexions(self, *c):
        (self.r / "etat.json").write_text(json.dumps(list(c)))

    def ks(self, *args, **plus):
        plus.setdefault("NC_VPN_SYSFS", str(self.sysfs))
        plus.setdefault("NC_VPN_ROOT", str(self.helper))
        return self.vpn("killswitch", *args, **plus)

    def sudo(self):
        p = self.r / "appels-sudo.jsonl"
        return [json.loads(l) for l in p.read_text().splitlines()] if p.exists() else []

    def openvpn_sous_wifi(self, remote="remote = 192.0.2.10:1194:udp, connection-type = password"):
        """Un OpenVPN que NetworkManager dit porté par wlan0 ; le vrai tun0 est retrouvé par ses adresses."""
        self.connexions(dict(uuid=U1, type="vpn", active=True, dev="wlan0", nom="Labo"))
        (self.r / "vpn_data.json").write_text(json.dumps({U1: remote}))
        (self.r / "ipconf.json").write_text(json.dumps({U1: "10.8.0.6/24\n"}))
        self.iface("wlan0")
        self.iface("tun0", tun=True)
        (self.r / "ip.json").write_text(json.dumps([
            {"ifname": "wlan0", "addr_info": [{"family": "inet", "local": "192.0.2.77", "prefixlen": 24, "scope": "global"}]},
            {"ifname": "tun0", "addr_info": [{"family": "inet", "local": "10.8.0.6", "prefixlen": 24, "scope": "global"}]}]))

    def test_coupe_par_defaut_et_aucun_appel(self):
        self.cfg_reglage("non")
        self.openvpn_sous_wifi()
        r = self.ks("activer")
        self.assertEqual(r.returncode, 1)
        self.assertIn("VPN_KILLSWITCH", r.stderr)
        self.assertEqual(self.sudo(), [])
        (self.r / "home/.config/nc/reglages.conf").unlink()
        self.assertEqual(self.ks("activer").returncode, 1)
        self.assertEqual(self.sudo(), [])

    def test_openvpn_avec_le_wifi_comme_device_de_base_retrouve_le_tun(self):
        self.openvpn_sous_wifi()
        r = self.ks("activer")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.sudo(), [["-n", str(self.helper), "activer", "tun0", "192.0.2.10@1194/udp"]])
        self.assertIn("tun0", r.stdout)

    def test_limites_affichees_avant_l_activation_et_aussi_en_cas_de_refus(self):
        self.openvpn_sous_wifi()
        out = self.ks("activer").stdout
        i = out.index("Limites du kill switch")
        for mot in ("redémarrage", "forwarding des conteneurs", "changer de serveur", "multi-remote", "sudo nft delete table inet nc_vpn"):
            self.assertIn(mot, out)
            self.assertLess(i, out.index(mot))
        self.assertLess(out.index("sudo nft delete table inet nc_vpn"), out.index("Kill switch actif"))
        self.connexions()                         # plus de tunnel : refus, mais les limites ont été montrées d'abord
        r = self.ks("activer")
        self.assertEqual(r.returncode, 1)
        self.assertIn("Limites du kill switch", r.stdout)
        self.assertIn("Aucun tunnel monté", r.stderr)
        self.assertEqual(len(self.sudo()), 1)       # pas de nouvel appel
        self.assertIn("forwarding", self.ks("limites").stdout)

    def test_noms_d_hote_et_multi_remote_refuses(self):
        self.openvpn_sous_wifi("remote = vpn.example.org:1194:udp")
        r = self.ks("activer")
        self.assertEqual(r.returncode, 1)
        self.assertIn("adresse IP", r.stderr)
        self.openvpn_sous_wifi("remote = 192.0.2.10:1194:udp, 198.51.100.4:1194:udp, connection-type = password")
        r = self.ks("activer")
        self.assertEqual(r.returncode, 1)
        self.assertIn("multi-remote", r.stderr)
        self.assertEqual(self.sudo(), [])

    def test_identifiant_de_zone_et_signes_piegeux_refuses_cote_utilisateur(self):
        for remote in ("remote = [2001:db8::1%eth0]:1194:udp", "remote = fe80::1", "remote = [fe80::1]:1194:udp", "remote = 192.0.2.1%x:1194",
                       "remote = 2001:db8::1%\"", "remote = 2001:db8::1%;"):
            self.openvpn_sous_wifi(remote)
            (self.r / "appels-sudo.jsonl").unlink(missing_ok=True)
            r = self.ks("activer")
            self.assertEqual(r.returncode, 1, remote)
            self.assertEqual(self.sudo(), [], remote)
        self.connexions(dict(uuid=U2, type="wireguard", active=True, dev="wg-maison", nom="Maison"))
        self.iface("wg-maison", wireguard=True)
        (self.r / "gdbus-settings.txt").write_text("({'wireguard': {'peers': <[{'endpoint': <'[2001:db8::1%x#]:51820'>}]>}},)")
        self.assertEqual(self.ks("activer").returncode, 1)
        self.assertEqual(self.sudo(), [])

    def test_formes_de_remote_openvpn(self):
        for remote, attendu in (("remote = 192.0.2.10, port = 443, proto-tcp = yes", "192.0.2.10@443/tcp"),
                                ("remote = [2001:db8::1]:1195:tcp", "2001:db8::1@1195/tcp"),
                                ("remote = 198.51.100.4", "198.51.100.4@1194/udp"),
                                ("remote = 2001:db8::7", "2001:db8::7@1194/udp")):
            self.openvpn_sous_wifi(remote)
            (self.r / "appels-sudo.jsonl").unlink(missing_ok=True)
            r = self.ks("activer")
            self.assertEqual(r.returncode, 0, remote + r.stderr)
            self.assertEqual(self.sudo()[0][3:], ["tun0", attendu], remote)

    def test_wireguard_endpoints_par_networkmanager(self):
        self.connexions(dict(uuid=U2, type="wireguard", active=True, dev="wg-maison", nom="Maison"))
        self.iface("wg-maison", wireguard=True)
        (self.r / "gdbus-settings.txt").write_text(
            "({'connection': {'id': <'Maison'>}, 'wireguard': {'peers': <[{'public-key': <'abc'>, 'endpoint': <'192.0.2.20:51820'>}, "
            "{'endpoint': <'[2001:db8::1]:51821'>}]>}},)")
        r = self.ks("activer")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.sudo()[0][2:], ["activer", "wg-maison", "192.0.2.20@51820/udp", "2001:db8::1@51821/udp"])
        (self.r / "gdbus-settings.txt").write_text("({'wireguard': {'peers': <[{'endpoint': <'vpn.example.org:51820'>}]>}},)")
        r = self.ks("activer")
        self.assertEqual(r.returncode, 1)
        self.assertIn("adresse IP", r.stderr)

    def test_une_interface_qui_n_est_pas_un_tunnel_n_est_pas_prise(self):
        self.connexions(dict(uuid=U3, type="vpn", active=True, dev="wlan0", nom="Labo"))
        (self.r / "vpn_data.json").write_text(json.dumps({U3: "remote = 192.0.2.10:1194:udp"}))
        self.iface("wlan0")          # ni tun_flags ni wireguard, et aucun tun ailleurs
        r = self.ks("activer")
        self.assertEqual(r.returncode, 1)
        self.assertIn("Impossible de retrouver l'interface du tunnel", r.stderr)
        self.assertEqual(self.sudo(), [])

    def test_pas_de_repli_sur_l_unique_tunnel_du_systeme(self):
        # le Wi-Fi porte l'OpenVPN, les adresses ne correspondent à aucun tun ; un seul tun existe (tailscale0 ou le TAP d'une VM) :
        # il ne doit JAMAIS être pris
        self.openvpn_sous_wifi()
        (self.r / "ipconf.json").write_text(json.dumps({U1: "10.99.0.2/24\n"}))
        (self.sysfs / "class/net/tun0").rename(self.sysfs / "class/net/tailscale0")
        self.iface("tailscale0", tun=True)
        r = self.ks("activer")
        self.assertEqual(r.returncode, 1)
        self.assertIn("Impossible de retrouver l'interface du tunnel", r.stderr)
        self.assertEqual(self.sudo(), [])

    def test_nom_d_interface_point_refuse(self):
        import importlib.machinery, importlib.util
        l = importlib.machinery.SourceFileLoader("ncvpn", str(Path(__file__).resolve().parents[1] / "home/.local/bin/nc-vpn"))
        sp = importlib.util.spec_from_loader("ncvpn", l)
        m = importlib.util.module_from_spec(sp)
        l.exec_module(m)
        for nom in (".", "..", "..."):
            self.assertFalse(m.iface_tunnel(nom), nom)

    def test_limites_dns_et_rechargement_de_nftables(self):
        out = self.ks("limites").stdout
        self.assertIn("sauf le DNS", out)
        self.assertIn("systemctl reload nftables", out)
        self.assertIn("nft flush ruleset", out)

    def test_plusieurs_tunnels_refuses(self):
        self.connexions(dict(uuid=U1, type="vpn", active=True, dev="tun0", nom="A"), dict(uuid=U2, type="wireguard", active=True, dev="wg0", nom="B"))
        r = self.ks("activer")
        self.assertEqual(r.returncode, 1)
        self.assertIn("Plusieurs tunnels", r.stderr)

    def test_assistant_absent_et_regle_sudo_manquante(self):
        self.openvpn_sous_wifi()
        r = self.ks("activer", NC_VPN_ROOT=str(self.r / "absent"))
        self.assertEqual(r.returncode, 1)
        self.assertIn("lance install.sh", r.stderr)
        r = self.ks("activer", SUDO_MOT_DE_PASSE="1")
        self.assertEqual(r.returncode, 1)
        self.assertIn("règle sudo", r.stderr)

    def test_refus_de_l_assistant_dit_pourquoi(self):
        self.openvpn_sous_wifi()
        r = self.ks("activer", SUDO_REFUS="ufw est actif : conflit")
        self.assertEqual(r.returncode, 1)
        self.assertIn("ufw est actif", r.stderr)
        self.assertNotIn("nc-vpn-root:", r.stderr)

    def test_mullvad_connecte_sans_tunnel_networkmanager_renvoie_vers_son_lockdown(self):
        self.connexions()
        (self.r / "mullvad.json").write_text(json.dumps({"json": json.dumps({"state": "connected", "details": {}})}))
        r = self.ks("activer")
        self.assertEqual(r.returncode, 1)
        self.assertIn("mullvad lockdown-mode set on", r.stderr)
        self.assertEqual(self.sudo(), [])

    def test_desactiver_toujours_possible_meme_si_le_reglage_est_coupe(self):
        self.cfg_reglage("non")
        r = self.ks("desactiver")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.sudo(), [["-n", str(self.helper), "desactiver"]])
        r = self.ks("desactiver", SUDO_REFUS="échec")
        self.assertEqual(r.returncode, 1)
        self.assertIn("sudo nft delete table inet nc_vpn", r.stderr)

    def test_etat_et_etat_json(self):
        (self.r / "ks-etat").write_text("actif\n")
        self.assertIn("actif", self.ks("etat").stdout)
        j = json.loads(self.ks("etat-json").stdout)
        self.assertEqual((j["installe"], j["voulu"], j["actif"], j["refus"]), (True, True, True, ""))
        self.assertTrue(len(j["limites"]) >= 4)
        (self.r / "ks-etat").write_text("inactif\n")
        self.connexions()
        j = json.loads(self.ks("etat-json").stdout)
        self.assertEqual((j["actif"], "Aucun tunnel" in j["refus"]), (False, True))
        j = json.loads(self.ks("etat-json", NC_VPN_ROOT=str(self.r / "absent")).stdout)
        self.assertEqual((j["installe"], j["actif"]), (False, None))
        self.assertIn("install.sh", j["refus"])
        self.cfg_reglage("non")
        self.assertFalse(json.loads(self.ks("etat-json").stdout)["voulu"])

    def test_pas_installe_assistant_absent_ou_regle_sudo_absente(self):
        """« Pas installé » (champ installe: false), jamais « inconnu » : l'assistant manque, ou sudo ne le permet pas sans mot de passe.
        La règle est cherchée par « sudo -n -l ASSISTANT etat » en argv, sans rien lancer d'autre."""
        # assistant absent : sudo n'est même pas appelé
        r = self.ks("etat", NC_VPN_ROOT=str(self.r / "absent"))
        self.assertIn("pas installé", r.stdout)
        self.assertNotIn("inconnu", r.stdout)
        j = json.loads(self.ks("etat-json", NC_VPN_ROOT=str(self.r / "absent")).stdout)
        self.assertEqual((j["installe"], j["actif"]), (False, None))
        self.assertIn("Pas installé", j["refus"])
        self.assertEqual(self.sudo(), [])
        # assistant posé mais règle sudo absente (sudo demande un mot de passe) : pas installé non plus
        r = self.ks("etat", SUDO_MOT_DE_PASSE="1")
        self.assertIn("pas installé", r.stdout)
        self.assertNotIn("inconnu", r.stdout)
        j = json.loads(self.ks("etat-json", SUDO_MOT_DE_PASSE="1").stdout)
        self.assertEqual((j["installe"], j["actif"]), (False, None))
        self.assertEqual(set(map(tuple, self.sudo())), {("-n", "-l", str(self.helper), "etat")})
        # règle présente : la question à sudo est la seule demandée, puis l'état vient de l'assistant
        (self.r / "appels-sudo.jsonl").unlink()
        (self.r / "ks-etat").write_text("inactif\n")
        j = json.loads(self.ks("etat-json").stdout)
        self.assertEqual((j["installe"], j["actif"]), (True, False))
        self.assertEqual(self.sudo()[0], ["-n", "-l", str(self.helper), "etat"])

    def test_refus_code_stable_et_nom_d_hote_dans_refus_seulement(self):
        """Le contrat : `refus_code` est une valeur fixe ; le nom d'hôte du serveur n'est que dans le texte `refus`."""
        j = json.loads(self.ks("etat-json", NC_VPN_ROOT=str(self.r / "absent")).stdout)
        self.assertEqual(j["refus_code"], "pas_installe")
        (self.r / "ks-etat").write_text("inactif\n")
        self.connexions(dict(uuid=U1, type="vpn", active=False, dev="tun0", nom="A"))
        j = json.loads(self.ks("etat-json").stdout)               # installé, aucun tunnel monté (le faux Wi-Fi seul)
        self.assertEqual(j["refus_code"], "aucun_tunnel")
        self.openvpn_sous_wifi("remote = vpn.example.org:1194:udp")
        j = json.loads(self.ks("etat-json").stdout)
        self.assertEqual(j["refus_code"], "serveur_nom")
        self.assertIn("vpn.example.org", j["refus"])
        self.assertNotIn("vpn.example.org", j["refus_code"])
        (self.r / "ks-etat").write_text("actif\n")
        self.assertEqual(json.loads(self.ks("etat-json").stdout)["refus_code"], "")
        self.connexions(dict(uuid=U1, type="vpn", active=True, dev="tun0", nom="A"), dict(uuid=U2, type="vpn", active=True, dev="tun1", nom="B"))
        (self.r / "ks-etat").write_text("inactif\n")
        self.assertEqual(json.loads(self.ks("etat-json").stdout)["refus_code"], "plusieurs_tunnels")
        self.assertEqual(json.loads(self.ks("etat-json", NM_ARRETE="1").stdout)["refus_code"], "nm_indisponible")

    def test_aucun_appel_a_nft_ni_a_ip_link_ni_a_systemctl(self):
        self.openvpn_sous_wifi()
        self.ks("activer")
        self.assertEqual([x for x in self.sudo() if x[1] != str(self.helper)], [])      # sudo ne lance que l'assistant
        src = (Path(__file__).resolve().parents[1] / "home/.local/bin/nc-vpn").read_text()
        self.assertNotIn('"nft"', src)
        self.assertNotIn("shell=True", src)

    def test_usage_dans_l_aide(self):
        self.assertIn("killswitch", self.vpn("aide").stdout)


if __name__ == "__main__":
    unittest.main()

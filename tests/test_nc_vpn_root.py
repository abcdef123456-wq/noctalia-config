"""nc-vpn-root, l'assistant root du kill switch : arguments validés, texte nft testé caractère par caractère, refus sans
aucun appel à nft (nft absent, firewalld, ufw, Mullvad), desactiver = seulement « delete table inet nc_vpn ». Faux /sys
(NC_VPN_RACINE) et faux outils (NC_VPN_BIN) qui notent leurs arguments : jamais le vrai nft, ip, sudo ni systemctl.
Un essai réel existe dans un espace de noms réseau isolé (unshare sans root réel), seulement s'il est possible ici."""
import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
ROOT = REPO / "system/nc-vpn-root"


def charger():
    l = importlib.machinery.SourceFileLoader("nc_vpn_root", str(ROOT))
    s = importlib.util.spec_from_loader("nc_vpn_root", l)
    m = importlib.util.module_from_spec(s)
    l.exec_module(m)
    return m


ADRESSES = [
    {"ifname": "lo", "addr_info": [{"family": "inet", "local": "127.0.0.1", "prefixlen": 8, "scope": "host"}]},
    {"ifname": "wlan0", "addr_info": [
        {"family": "inet", "local": "192.0.2.77", "prefixlen": 24, "scope": "global"},
        {"family": "inet6", "local": "2001:db8:1::5", "prefixlen": 64, "scope": "global"},
        {"family": "inet6", "local": "2001:db8:1::99", "prefixlen": 64, "scope": "global"},
        {"family": "inet6", "local": "fe80::1", "prefixlen": 64, "scope": "link"}]},
    {"ifname": "tun0", "addr_info": [{"family": "inet", "local": "10.8.0.2", "prefixlen": 24, "scope": "global"}]},
    {"ifname": "docker0", "addr_info": [{"family": "inet", "local": "172.17.0.1", "prefixlen": 16, "scope": "global"}]},
]

TEXTE_ATTENDU = """add table inet nc_vpn
delete table inet nc_vpn
table inet nc_vpn {
\tchain output {
\t\ttype filter hook output priority filter; policy drop;
\t\toif lo accept
\t\toifname "tun0" accept
\t\tudp sport 68 udp dport 67 accept
\t\tudp sport 546 udp dport 547 accept
\t\ticmpv6 type { nd-router-solicit, nd-neighbor-solicit, nd-neighbor-advert } accept
\t\tip daddr 198.51.100.10 udp dport 1194 accept
\t\tip6 daddr 2001:db8::1 udp dport 51820 accept
\t\tip daddr 198.51.100.11 accept
\t\tip daddr 198.51.100.12 udp dport 443 accept
\t\tip daddr 198.51.100.12 tcp dport 443 accept
\t\tip daddr 192.0.2.0/24 accept
\t\tip6 daddr 2001:db8:1::/64 accept
\t}
}
"""


class Pur(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = charger()

    def test_texte_nft_exact(self):
        m = self.m
        eps = m.valider_endpoints(["198.51.100.10@1194/udp", "2001:db8::1@51820/udp", "198.51.100.11", "198.51.100.12@443"])
        nets = m.sous_reseaux_attaches(ADRESSES, "tun0", lambda n: n in ("wlan0", "eth0"))
        self.assertEqual(m.generer_regles("tun0", eps, nets), TEXTE_ATTENDU)

    def test_sous_reseaux_attaches_seulement(self):
        nets = self.m.sous_reseaux_attaches(ADRESSES, "tun0", lambda n: n == "wlan0")
        self.assertEqual([str(n) for n in nets], ["192.0.2.0/24", "2001:db8:1::/64"])     # ni docker, ni tunnel, ni lien local, doublon fondu
        texte = self.m.generer_regles("tun0", [], nets)
        for interdit in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "172.17.0.0/16", "10.8.0.0"):
            self.assertNotIn(interdit, texte)

    def test_table_seule_et_politique_drop(self):
        texte = self.m.generer_regles("wg0", [], [])
        self.assertEqual(texte.count("table inet nc_vpn"), 3)       # add, delete, définition
        self.assertIn("policy drop;", texte)
        self.assertIn("priority filter", texte)
        self.assertNotRegex(texte, r"flush|table ip |table ip6 |inet filter")

    def test_noms_valides_et_invalides(self):
        for ok in ("tun0", "wg-maison", "a.b_c", "x" * 15):
            self.assertEqual(self.m.valider_nom(ok), ok)
        for mauvais in ("", "x" * 16, "tun 0", "tun0;ls", "-tun", "../x", 'a"b', "tun0\n", "é"):
            with self.assertRaises(self.m.Refus, msg=repr(mauvais)):
                self.m.valider_nom(mauvais)

    def test_endpoints_valides_et_invalides(self):
        for ok in ("192.0.2.1", "2001:db8::1", "192.0.2.1@51820", "192.0.2.1@1194/tcp"):
            self.m.valider_endpoint(ok)
        for mauvais in ("vpn.example.org", "192.0.2.1@0", "192.0.2.1@70000", "192.0.2.1@80/icmp", "192.0.2.1@x", "0.0.0.0", "127.0.0.1",
                        "224.0.0.1", "::", "192.0.2.1 accept", "192.0.2.1;", "192.0.2.256", ""):
            with self.assertRaises(self.m.Refus, msg=repr(mauvais)):
                self.m.valider_endpoint(mauvais)
        with self.assertRaises(self.m.Refus):
            self.m.valider_endpoints([])
        with self.assertRaises(self.m.Refus):
            self.m.valider_endpoints(["192.0.2.%d" % i for i in range(1, 10)])
        self.assertEqual(len(self.m.valider_endpoints(["192.0.2.%d" % i for i in range(1, 9)])), 8)


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="ncvr-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.sys = self.tmp / "sys"
        self.bin = self.tmp / "bin"
        self.bin.mkdir()
        self.journal = self.tmp / "journal"
        self.journal.touch()
        self.stdin = self.tmp / "nft-stdin"
        self.env = {"PATH": "/usr/bin:/bin", "HOME": str(self.tmp / "home"), "NC_VPN_RACINE": str(self.sys), "NC_VPN_BIN": str(self.bin),
                    "NC_LANGUE": "fr"}
        (self.tmp / "addr.json").write_text(json.dumps(ADRESSES))
        self.faux("systemctl", "echo inactive")
        self.faux("mullvad", "echo Disconnected")
        self.faux("ip", f'cat "{self.tmp}/addr.json"')
        self.faux("nft", f'if [ "$1 $2" = "-f -" ]; then cat > "{self.stdin}"; fi')
        self.interface("tun0", tun=True)
        self.interface("wg0", wireguard=True)
        self.interface("wlan0", wifi=True)
        self.interface("eth0", physique=True)
        self.interface("docker0")

    def faux(self, nom, corps):
        f = self.bin / nom
        f.write_text(f'#!/bin/sh\necho "{nom} $*" >> "{self.journal}"\n{corps}\n')
        f.chmod(0o755)

    def interface(self, nom, tun=False, wireguard=False, wifi=False, physique=False):
        d = self.sys / "class/net" / nom
        d.mkdir(parents=True)
        (d / "uevent").write_text("INTERFACE=%s\n%s" % (nom, "DEVTYPE=wireguard\n" if wireguard else ""))
        if tun:
            (d / "tun_flags").write_text("0x1002\n")
        if wifi:
            (d / "wireless").mkdir()
        if wifi or physique:
            (d / "device").mkdir()

    def lancer(self, *args, env=None):
        return subprocess.run([str(ROOT), *args], env=env or self.env, capture_output=True, text=True, timeout=30)

    def appels(self):
        return self.journal.read_text().splitlines()

    def appels_nft(self):
        return [l for l in self.appels() if l.startswith("nft ")]


class Activer(Base):
    def test_activer_envoie_le_texte_exact_a_nft(self):
        r = self.lancer("activer", "tun0", "198.51.100.10@1194/udp", "2001:db8::1@51820/udp", "198.51.100.11", "198.51.100.12@443")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), "actif")
        self.assertEqual(self.stdin.read_text(), TEXTE_ATTENDU)
        self.assertEqual(self.appels_nft(), ["nft -f -"])

    def test_wireguard_accepte(self):
        r = self.lancer("activer", "wg0", "192.0.2.1@51820/udp")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('oifname "wg0" accept', self.stdin.read_text())

    def test_wifi_ethernet_et_non_tunnel_refuses(self):
        for itf in ("wlan0", "eth0", "docker0", "inexistante"):
            r = self.lancer("activer", itf, "192.0.2.1")
            self.assertEqual(r.returncode, 2, itf + r.stderr)
            self.assertEqual(self.appels_nft(), [], itf)

    def test_arguments_invalides_refuses_sans_appel(self):
        for args in (["activer", "tun 0", "192.0.2.1"], ["activer", "tun0"], ["activer", "tun0", "vpn.example.org"],
                     ["activer", "tun0"] + ["192.0.2.%d" % i for i in range(1, 10)], ["activer", "-f", "192.0.2.1"],
                     ["desactiver", "x"], ["flush"], ["etat", "x"], []):
            r = self.lancer(*args)
            self.assertEqual(r.returncode, 2, args)
        self.assertEqual(self.appels(), [])

    def test_nft_absent_refus_clair(self):
        (self.bin / "nft").unlink()
        if shutil.which("nft", path="/usr/sbin:/usr/bin:/sbin:/bin"):
            self.skipTest("un vrai nft est installé ici : on ne le lance jamais ; le refus est testé par le texte du code")
        r = self.lancer("activer", "tun0", "192.0.2.1")
        self.assertEqual(r.returncode, 3)
        self.assertIn("nftables", r.stderr)

    def test_nft_absent_dans_le_code(self):
        m = charger()
        m.PATH = str(self.tmp / "vide")
        with self.assertRaises(m.Refus) as c:
            m.verifier_environnement()
        self.assertEqual(c.exception.code, 3)
        self.assertIn("nftables", str(c.exception))

    def test_firewalld_et_ufw_refuses_sans_appel_nft(self):
        for svc in ("firewalld", "ufw"):
            self.faux("systemctl", f'[ "$2" = {svc} ] && echo active || echo inactive')
            self.journal.write_text("")
            r = self.lancer("activer", "tun0", "192.0.2.1")
            self.assertEqual(r.returncode, 3, svc)
            self.assertIn(svc, r.stderr)
            self.assertEqual(self.appels_nft(), [], svc)
            self.assertIn(f"systemctl is-active {svc}", self.appels())

    def test_mullvad_demon_actif_refuse_avec_lockdown(self):
        self.faux("systemctl", '[ "$2" = mullvad-daemon ] && echo active || echo inactive')
        r = self.lancer("activer", "tun0", "192.0.2.1")
        self.assertEqual(r.returncode, 3)
        self.assertIn("mullvad lockdown-mode set on", r.stderr)
        self.assertEqual(self.appels_nft(), [])

    def test_mullvad_cli_connecte_refuse(self):
        self.faux("mullvad", 'echo "Connected to se-got-wg-004"')
        r = self.lancer("activer", "tun0", "192.0.2.1")
        self.assertEqual(r.returncode, 3)
        self.assertIn("lockdown-mode", r.stderr)
        self.assertEqual(self.appels_nft(), [])
        self.assertIn("mullvad status", self.appels())

    def test_mullvad_cli_deconnecte_ne_bloque_pas(self):
        self.assertEqual(self.lancer("activer", "tun0", "192.0.2.1").returncode, 0)

    def test_nft_qui_echoue_donne_un_echec(self):
        self.faux("nft", 'cat >/dev/null; echo "Error: boom" >&2; exit 1')
        r = self.lancer("activer", "tun0", "192.0.2.1")
        self.assertEqual(r.returncode, 1)
        self.assertIn("boom", r.stderr)


class DesactiverEtat(Base):
    def test_desactiver_seulement_delete_table(self):
        r = self.lancer("desactiver")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.appels(), ["nft delete table inet nc_vpn"])

    def test_desactiver_deja_inactif(self):
        self.faux("nft", "exit 1")
        r = self.lancer("desactiver")
        self.assertEqual(r.returncode, 0)
        self.assertEqual(r.stdout.strip(), "inactif")
        self.assertEqual(self.appels(), ["nft delete table inet nc_vpn", "nft list table inet nc_vpn"])

    def test_etat(self):
        self.assertEqual(self.lancer("etat").stdout.strip(), "actif")
        self.faux("nft", "exit 1")
        self.assertEqual(self.lancer("etat").stdout.strip(), "inactif")

    def test_hors_essai_il_faut_etre_root(self):
        if os.getuid() == 0:
            self.skipTest("root")
        env = {k: v for k, v in self.env.items() if not k.startswith("NC_VPN")}
        env["PATH"] = str(self.bin)          # même sans variable d'essai, aucun vrai outil n'est lancé : pas root, on s'arrête
        r = self.lancer("desactiver", env=env)
        self.assertIn(r.returncode, (1, 3))
        self.assertEqual(self.appels_nft(), [])

    def test_sudoers(self):
        r = self.lancer("sudoers", "user")
        self.assertEqual(r.stdout.strip(), "user ALL=(root) NOPASSWD: /usr/local/bin/nc-vpn-root etat, "
                                           "/usr/local/bin/nc-vpn-root desactiver, /usr/local/bin/nc-vpn-root activer *")
        for mauvais in ("ALL", "%wheel", "Root", "a b", ""):
            self.assertEqual(self.lancer("sudoers", mauvais).returncode, 2, mauvais)
        self.assertNotIn("/home/", ROOT.read_text())


def netns_possible():
    try:
        return (subprocess.run(["unshare", "--user", "--map-root-user", "--net", "true"], capture_output=True, timeout=10).returncode == 0
                and shutil.which("nft") is not None and shutil.which("ip") is not None and shutil.which("ping") is not None)
    except (OSError, subprocess.SubprocessError):
        return False


ESSAI_SH = r'''#!/bin/sh
# Lancé DANS un espace de noms réseau neuf (unshare --user --map-root-user --net). Argument 1 : dossier de travail.
set -u
D=$1
[ "$(ip -o link | wc -l)" = 1 ] || { echo "PAS_DE_NETNS_NEUF"; exit 9; }
ip link set lo up
ip link add dumv type dummy || { echo "PAS_DE_DUMMY"; exit 8; }
ip link add dumt type dummy || { echo "PAS_DE_DUMMY"; exit 8; }
ip addr add 192.0.2.5/24 dev dumv; ip link set dumv up
ip addr add 10.9.0.2/24 dev dumt; ip link set dumt up
ip route add default dev dumv
ip route add 203.0.113.50/32 dev dumt
nft add table ip autre_table
nft add chain ip autre_table c '{ type filter hook output priority 0; policy accept; }'
nft list ruleset > "$D/avant"
sed 's/^if os.getuid() != 0 and os.environ.get("NC_VPN_RACINE"):/if os.environ.get("NC_VPN_RACINE"):/' "$2" > "$D/assistant.py"
python3 -I "$D/assistant.py" activer dumt 198.51.100.10@1194/udp || { echo ACTIVER_ECHEC; exit 1; }
nft list ruleset > "$D/pendant"
ping -c1 -W1 127.0.0.1 >/dev/null 2>&1 && echo LO_OK
udp() { python3 -I -c 'import socket,sys; s=socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.sendto(b"x", (sys.argv[1], 9)); print("ENVOYE")' "$1" 2>&1; }
udp 203.0.113.99 > "$D/ping-hors"
udp 203.0.113.50 > "$D/ping-tunnel"
python3 -I "$D/assistant.py" desactiver || { echo DESACTIVER_ECHEC; exit 1; }
nft list ruleset > "$D/apres"
echo FIN
'''


@unittest.skipUnless(netns_possible(), "pas d'espace de noms réseau isolé ici")
class EssaiReelDansNetnsIsole(unittest.TestCase):
    """Dans un espace de noms réseau NEUF créé sans root réel (unshare --user --map-root-user --net) : deux interfaces
    « dummy » (l'une jouée tunnel par un faux /sys), le vrai nft d'ici, jamais le réseau de la machine. Le script vérifie
    d'abord que seul « lo » existe. systemctl et mullvad sont de faux outils (jamais les vrais)."""

    def test_activation_blocage_et_desactivation(self):
        tmp = Path(tempfile.mkdtemp(prefix="ncvr-"))
        self.addCleanup(shutil.rmtree, tmp, True)
        fb = tmp / "fb"
        fb.mkdir()
        for nom, corps in (("systemctl", "echo inactive"), ("mullvad", "echo Disconnected")):
            (fb / nom).write_text("#!/bin/sh\n" + corps + "\n")
            (fb / nom).chmod(0o755)
        for nom, tun in (("dumt", True), ("dumv", False)):
            d = tmp / "sys/class/net" / nom
            d.mkdir(parents=True)
            (d / "uevent").write_text("INTERFACE=%s\n" % nom)
            if tun:
                (d / "tun_flags").write_text("0x1002\n")
            else:
                (d / "device").mkdir()
        script = tmp / "essai.sh"
        script.write_text(ESSAI_SH)
        script.chmod(0o755)
        env = dict(os.environ, NC_VPN_RACINE=str(tmp / "sys"), NC_VPN_BIN=str(fb), HOME=str(tmp), TMPDIR=str(tmp))
        r = subprocess.run(["unshare", "--user", "--map-root-user", "--net", "--", str(script), str(tmp), str(ROOT)],
                           capture_output=True, text=True, timeout=90, env=env)
        out = r.stdout + r.stderr
        if "PAS_DE_" in out:
            self.skipTest(out.strip())
        self.assertIn("FIN", r.stdout, out)
        pendant = (tmp / "pendant").read_text()
        self.assertIn("table inet nc_vpn", pendant)
        self.assertIn("policy drop", pendant)
        self.assertIn("table ip autre_table", pendant)
        self.assertIn("LO_OK", r.stdout)
        self.assertIn("PermissionError", (tmp / "ping-hors").read_text())                # sortie hors tunnel : bloquée
        self.assertIn("ENVOYE", (tmp / "ping-tunnel").read_text())                     # par le tunnel : non bloquée
        self.assertEqual((tmp / "avant").read_text(), (tmp / "apres").read_text())     # l'autre table est intacte
        self.assertNotIn("nc_vpn", (tmp / "apres").read_text())


if __name__ == "__main__":
    unittest.main()

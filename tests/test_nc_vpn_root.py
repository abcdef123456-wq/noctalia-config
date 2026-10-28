"""nc-vpn-root, l'assistant root du kill switch : arguments validés, texte nft testé caractère par caractère, refus sans
aucun appel à nft (nft absent, firewalld, ufw, Mullvad), desactiver = seulement « delete table inet nc_vpn ». Faux /sys
(NC_VPN_RACINE) et faux outils (NC_VPN_BIN) qui notent leurs arguments : jamais le vrai nft, ip, sudo ni systemctl.
Un essai réel existe dans un espace de noms réseau isolé (unshare sans root réel), seulement s'il est possible ici."""
import importlib.machinery
import ipaddress
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
    {"ifname": "eth0", "addr_info": [
        {"family": "inet", "local": "198.51.100.7", "prefixlen": 16, "scope": "global"},
        {"family": "inet", "local": "10.0.0.5", "prefixlen": 8, "scope": "global"},
        {"family": "inet6", "local": "2001:db8::5", "prefixlen": 32, "scope": "global"},
        {"family": "inet6", "local": "2001:db8:2::9", "prefixlen": 48, "scope": "global"}]},
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
\t\ticmpv6 type { nd-router-solicit, nd-neighbor-solicit, nd-neighbor-advert, mld2-listener-report } accept
\t\tip daddr 198.51.100.10 udp dport 1194 accept
\t\tip6 daddr 2001:db8::1 udp dport 51820 accept
\t\tip daddr 198.51.100.11 tcp dport 1195 accept
\t\tip daddr 198.51.100.12 udp dport 443 accept
\t\tip daddr 198.51.100.12 tcp dport 443 accept
\t\tip daddr 198.51.100.13 udp dport 53 accept
\t\tmeta l4proto { udp, tcp } th dport { 53, 853 } drop
\t\tip daddr 192.0.2.0/24 accept
\t\tip daddr 198.51.0.0/16 accept
\t\tip6 daddr 2001:db8:1::/64 accept
\t\tip6 daddr 2001:db8:2::/48 accept
\t}
}
"""


class Pur(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = charger()

    def test_texte_nft_exact(self):
        m = self.m
        eps = m.valider_endpoints(["198.51.100.10@1194/udp", "2001:db8::1@51820/udp", "198.51.100.11@1195/tcp", "198.51.100.12@443",
                                   "198.51.100.13@53/udp"])
        nets = m.sous_reseaux_attaches(ADRESSES, "tun0", lambda n: n in ("wlan0", "eth0"))
        self.assertEqual(m.generer_regles("tun0", eps, nets), TEXTE_ATTENDU)

    def test_sous_reseaux_attaches_seulement(self):
        nets = self.m.sous_reseaux_attaches(ADRESSES, "tun0", lambda n: n == "wlan0")
        self.assertEqual([str(n) for n in nets], ["192.0.2.0/24", "2001:db8:1::/64"])     # ni docker, ni tunnel, ni lien local, doublon fondu
        texte = self.m.generer_regles("tun0", [], nets)
        for interdit in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "172.17.0.0/16", "10.8.0.0"):
            self.assertNotIn(interdit, texte)

    def test_prefixes_larges_ignores(self):
        nets = self.m.sous_reseaux_attaches(ADRESSES, "tun0", lambda n: n == "eth0")
        self.assertEqual([str(n) for n in nets], ["198.51.0.0/16", "2001:db8:2::/48"])     # ni /8 (IPv4), ni /32 (IPv6)

    def test_table_seule_et_politique_drop(self):
        texte = self.m.generer_regles("wg0", [], [])
        self.assertEqual(texte.count("table inet nc_vpn"), 3)       # add, delete, définition
        self.assertIn("policy drop;", texte)
        self.assertIn("priority filter", texte)
        self.assertNotRegex(texte, r"flush|table ip |table ip6 |inet filter")

    def test_noms_valides_et_invalides(self):
        for ok in ("tun0", "wg-maison", "a.b_c", "x" * 15):
            self.assertEqual(self.m.valider_nom(ok), ok)
        for mauvais in ("", ".", "..", "...", "x" * 16, "tun 0", "tun0;ls", "-tun", "../x", 'a"b', "tun0\n", "é"):
            with self.assertRaises(self.m.Refus, msg=repr(mauvais)):
                self.m.valider_nom(mauvais)

    def test_endpoints_valides_et_invalides(self):
        for ok in ("192.0.2.1@1194", "2001:db8::1@51820", "192.0.2.1@51820", "192.0.2.1@1194/tcp"):
            self.m.valider_endpoint(ok)
        for mauvais in ("192.0.2.1", "2001:db8::1", "vpn.example.org", "192.0.2.1@0", "192.0.2.1@70000", "192.0.2.1@80/icmp", "192.0.2.1@x", "0.0.0.0", "127.0.0.1",
                        "224.0.0.1", "::", "192.0.2.1 accept", "192.0.2.1;", "192.0.2.256", ""):
            with self.assertRaises(self.m.Refus, msg=repr(mauvais)):
                self.m.valider_endpoint(mauvais)
        with self.assertRaises(self.m.Refus):
            self.m.valider_endpoints([])
        with self.assertRaises(self.m.Refus):
            self.m.valider_endpoints(["192.0.2.%d@1194" % i for i in range(1, 10)])
        self.assertEqual(len(self.m.valider_endpoints(["192.0.2.%d@1194" % i for i in range(1, 9)])), 8)


    PIEGES = ["2001:db8::1%x\nflush ruleset\ninclude \"shadow\"\n#", "2001:db8::1%eth0", "2001:db8::1%", "fe80::1%wlan0", "fe80::1",
              '2001:db8::1%"', "2001:db8::1%}", "2001:db8::1%;", "2001:db8::1%#", "2001:db8::1%x\n", "192.0.2.1\n", "192.0.2.1\nflush ruleset",
              "192.0.2.1%x"]

    def test_identifiant_de_zone_et_signes_piegeux_refuses(self):
        for p in self.PIEGES:
            for suite in ("", "@1194", "@1194/udp"):
                with self.assertRaises(self.m.Refus, msg=repr(p + suite)):
                    self.m.valider_endpoint(p + suite)
        with self.assertRaises(self.m.Refus):
            self.m.valider_endpoints(["192.0.2.1@1194", self.PIEGES[0]])

    def test_garde_finale_refuse_un_element_piege_sans_passer_par_la_validation(self):
        m = self.m
        piege = ipaddress.ip_address("2001:db8::1%x")                   # accepté par ipaddress lui-même
        for ip in (piege, ipaddress.ip_address("2001:db8::1%a;b"), ipaddress.ip_address("2001:db8::1%a#b")):
            with self.assertRaises(m.Refus, msg=str(ip)):
                m.generer_regles("tun0", [(ip, 51820, "udp")], [])
        for iface in ('tun0"\nflush ruleset', "tun0\n", "tun0;", "tun#", 'tun"', "tun%"):
            with self.assertRaises(m.Refus, msg=repr(iface)):
                m.generer_regles(iface, [], [])

        class Reseau:                                                     # un faux réseau dont le texte est piégé
            version = 4
            def __str__(self):
                return "192.0.2.0/24\nflush ruleset"
        with self.assertRaises(m.Refus):
            m.generer_regles("tun0", [], [Reseau()])
        # la garde directe sur les lignes
        with self.assertRaises(m.Refus):
            m.verifier_texte(["\t\tflush ruleset!"], [])
        m.verifier_texte(["\t\ttype filter hook output priority filter; policy drop;", '\t\toifname "tun0" accept'], ["tun0"])


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
    def ufw_conf(self, texte, lien=False):
        d = self.sys / "etc/ufw"
        d.mkdir(parents=True, exist_ok=True)
        if lien:
            (d / "vrai.conf").write_text(texte)
            (d / "ufw.conf").symlink_to(d / "vrai.conf")
        else:
            (d / "ufw.conf").write_text(texte)

    def test_ufw_actif_d_apres_sa_configuration_pas_d_apres_systemctl(self):
        # Debian : ufw.service reste « active » après « ufw disable » ; seule la ligne ENABLED compte
        self.faux("systemctl", '[ "$2" = ufw ] && echo active || echo inactive')
        self.ufw_conf("# ufw\nENABLED=no\nLOGLEVEL=low\n")
        r = self.lancer("activer", "tun0", "192.0.2.1@1194")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn("systemctl is-active ufw", self.appels())
        self.ufw_conf("ENABLED=yes\n")
        self.journal.write_text("")
        r = self.lancer("activer", "tun0", "192.0.2.1@1194")
        self.assertEqual(r.returncode, 3)
        self.assertIn("ufw", r.stderr)
        self.assertEqual(self.appels_nft(), [])

    def test_ufw_conf_lien_ignore(self):
        self.ufw_conf("ENABLED=yes\n", lien=True)
        self.assertEqual(self.lancer("activer", "tun0", "192.0.2.1@1194").returncode, 0)

    def test_ordre_des_lignes_et_dns_apres_les_endpoints(self):
        r = self.lancer("activer", "tun0", "198.51.100.13@53/udp", "198.51.100.10@1194/udp")
        self.assertEqual(r.returncode, 0, r.stderr)
        lignes = [l.strip() for l in self.stdin.read_text().splitlines()]
        def pos(debut):
            return next(i for i, l in enumerate(lignes) if l.startswith(debut))
        ordre = [pos("oif lo"), pos('oifname "tun0"'), pos("udp sport 68"), pos("udp sport 546"), pos("icmpv6 type"),
                 pos("ip daddr 198.51.100.13 udp dport 53 accept"), pos("ip daddr 198.51.100.10"), pos("meta l4proto { udp, tcp } th dport { 53, 853 } drop"),
                 pos("ip daddr 192.0.2.0/24"), pos("}")]
        self.assertEqual(ordre, sorted(ordre))
        self.assertLess(pos("type filter hook output priority filter; policy drop;"), pos("oif lo"))     # policy drop dès l'en-tête de la chaîne
        self.assertIn("mld2-listener-report", self.stdin.read_text())

    def test_pas_root_hors_essai_aucun_outil_n_est_lance(self):
        if os.getuid() == 0:
            self.skipTest("root")
        m = charger()
        appels = []
        m.lancer = lambda *a, **k: appels.append(a) or (0, "", "")
        with self.assertRaises(m.Refus) as c:
            m.activer(["tun0", "192.0.2.1@1194"])
        self.assertEqual(c.exception.code, 1)
        self.assertEqual(appels, [])           # ni systemctl, ni mullvad, ni nft


    def test_activer_envoie_le_texte_exact_a_nft(self):
        r = self.lancer("activer", "tun0", "198.51.100.10@1194/udp", "2001:db8::1@51820/udp", "198.51.100.11@1195/tcp", "198.51.100.12@443",
                        "198.51.100.13@53/udp")
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
            r = self.lancer("activer", itf, "192.0.2.1@1194")
            self.assertEqual(r.returncode, 2, itf + r.stderr)
            self.assertEqual(self.appels_nft(), [], itf)

    def test_arguments_invalides_refuses_sans_appel(self):
        for args in (["activer", "tun 0", "192.0.2.1@1194"], ["activer", "tun0"], ["activer", "tun0", "vpn.example.org"],
                     ["activer", "tun0", "192.0.2.1"], ["activer", ".", "192.0.2.1@1194"], ["activer", "..", "192.0.2.1@1194"],
                     ["activer", "tun0"] + ["192.0.2.%d@1194" % i for i in range(1, 10)], ["activer", "-f", "192.0.2.1@1194"],
                     ["desactiver", "x"], ["flush"], ["etat", "x"], []):
            r = self.lancer(*args)
            self.assertEqual(r.returncode, 2, args)
        self.assertEqual(self.appels(), [])

    def test_nft_absent_refus_clair(self):
        (self.bin / "nft").unlink()
        if shutil.which("nft", path="/usr/sbin:/usr/bin:/sbin:/bin"):
            self.skipTest("un vrai nft est installé ici : on ne le lance jamais ; le refus est testé par le texte du code")
        r = self.lancer("activer", "tun0", "192.0.2.1@1194")
        self.assertEqual(r.returncode, 3)
        self.assertIn("nftables", r.stderr)

    def test_nft_absent_dans_le_code(self):
        m = charger()
        m.PATH = str(self.tmp / "vide")
        with self.assertRaises(m.Refus) as c:
            m.verifier_environnement()
        self.assertEqual(c.exception.code, 3)
        self.assertIn("nftables", str(c.exception))

    def test_firewalld_refuse_sans_appel_nft(self):
        self.faux("systemctl", '[ "$2" = firewalld ] && echo active || echo inactive')
        r = self.lancer("activer", "tun0", "192.0.2.1@1194")
        self.assertEqual(r.returncode, 3)
        self.assertIn("firewalld", r.stderr)
        self.assertEqual(self.appels_nft(), [])
        self.assertIn("systemctl is-active firewalld", self.appels())

    def test_mullvad_demon_actif_refuse_avec_lockdown(self):
        self.faux("systemctl", '[ "$2" = mullvad-daemon ] && echo active || echo inactive')
        r = self.lancer("activer", "tun0", "192.0.2.1@1194")
        self.assertEqual(r.returncode, 3)
        self.assertIn("mullvad lockdown-mode set on", r.stderr)
        self.assertEqual(self.appels_nft(), [])

    def test_mullvad_cli_connecte_refuse(self):
        self.faux("mullvad", 'echo "Connected to se-got-wg-004"')
        r = self.lancer("activer", "tun0", "192.0.2.1@1194")
        self.assertEqual(r.returncode, 3)
        self.assertIn("lockdown-mode", r.stderr)
        self.assertEqual(self.appels_nft(), [])
        self.assertIn("mullvad status", self.appels())

    def test_mullvad_cli_deconnecte_ne_bloque_pas(self):
        self.assertEqual(self.lancer("activer", "tun0", "192.0.2.1@1194").returncode, 0)

    def test_nft_qui_echoue_donne_un_echec(self):
        self.faux("nft", 'cat >/dev/null; echo "Error: boom" >&2; exit 1')
        r = self.lancer("activer", "tun0", "192.0.2.1@1194")
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


class InstallEtDoc(unittest.TestCase):
    def test_install_question_a_part_non_par_defaut_et_nftables_seulement_si_oui(self):
        inst = (REPO / "install.sh").read_text()
        i = inst.index("etape_killswitch_root() {")
        bloc = inst[i:inst.index("\n}\n", i)]
        self.assertRegex(bloc, r'ask "\$\(t "Installer l\'assistant du kill switch VPN \?"[^\n]*\)" n sensible')   # non par défaut
        self.assertEqual(bloc.count("ask "), 1)
        # le paquet n'est tiré qu'après le oui, par le gestionnaire commun aux quatre distributions
        self.assertGreater(bloc.index("pkg_install nftables"), bloc.index('ask "'))
        self.assertIn("visudo -cf", bloc)
        self.assertIn("install -Dm0755 -o root -g root", bloc)
        self.assertIn('"$REPO/system/nc-vpn-root" sudoers', bloc)
        self.assertNotRegex(bloc, r"sudo nft|\nft -f|systemctl")      # l'installation ne touche jamais au pare-feu
        self.assertIn("/usr/local/bin/nc-vpn-root", bloc)

    def fonction_dossiers(self):
        inst = (REPO / "install.sh").read_text()
        i = inst.index("dossiers_root_surs() {")
        return inst[i:inst.index("\n}\n", i) + 3]

    def test_commentaire_oui_corrige_et_firewalld_annonce_avant_la_question(self):
        inst = (REPO / "install.sh").read_text()
        e = inst.index("etape_energie_root() {")
        fonction_e = inst[e:inst.index("\n}\n", e)]
        self.assertNotIn("(--oui pour l'accepter)", inst[inst.index("# Profils d'énergie poussés"):e])
        self.assertIn("--oui n'accepte pas", inst)
        i = inst.index("etape_killswitch_root() {")
        bloc = inst[i:inst.index("\n}\n", i)]
        self.assertLess(bloc.index("firewalld est actif par défaut sur Fedora et openSUSE"), bloc.index('ask "'))
        self.assertIn("&& dossiers_root_surs; then", bloc)
        self.assertIn("n sensible && dossiers_root_surs; then", fonction_e)

    def lancer_garde(self, faux_stat):
        d = Path(tempfile.mkdtemp(prefix="ncvr-"))
        self.addCleanup(shutil.rmtree, d, True)
        if faux_stat is not None:
            (d / "stat").write_text("#!/bin/sh\n" + faux_stat + "\n")
            (d / "stat").chmod(0o755)
        script = 'warn() { echo "WARN $*"; }\nt() { echo "$1"; }\n' + self.fonction_dossiers() + "\ndossiers_root_surs\necho \"CODE=$?\"\n"
        env = {"PATH": (str(d) + ":" if faux_stat is not None else "") + "/usr/bin:/bin", "LC_ALL": "C.UTF-8"}
        return subprocess.run(["bash", "-c", script], env=env, capture_output=True, text=True, timeout=20)

    def test_dossiers_de_l_assistant_a_root_sans_ecriture_pour_les_autres(self):
        # cas sain : propriétaire 0, droits 755
        r = self.lancer_garde('case "$*" in *%u*) echo 0 ;; *) echo 755 ;; esac')
        self.assertIn("CODE=0", r.stdout, r.stdout + r.stderr)
        # modifiable par le groupe (775), par les autres (757), ou pas à root : refus clair, sans rien poser
        for u, m in (("0", "775"), ("0", "757"), ("1000", "755"), ("0", "777"), ("0", "")):
            r = self.lancer_garde('case "$*" in *%u*) echo ' + u + ' ;; *) echo ' + m + ' ;; esac')
            self.assertIn("CODE=1", r.stdout, (u, m, r.stdout))
            self.assertIn("WARN", r.stdout)

    def test_readme_limites_et_coupure_depuis_un_tty(self):
        readme = (REPO / "README.md").read_text()
        for mot in ("sudo nft delete table inet nc_vpn", "lockdown-mode set on", "forwarding des conteneurs", "pas de multi-remote",
                    "nc-vpn killswitch activer", "VPN_KILLSWITCH"):
            self.assertIn(mot, readme)

    def test_reglage_coupe_par_defaut(self):
        src = (REPO / "home/.local/bin/nc-reglages").read_text()
        self.assertRegex(src, r'R\("VPN_KILLSWITCH", "Île", [^\n]*"ouinon", "non"')


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

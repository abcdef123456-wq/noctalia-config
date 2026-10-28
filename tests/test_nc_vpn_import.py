"""nc-vpn importer : fichier ordinaire seulement (jamais un lien), 64 Kio au plus, .ovpn ou .conf ; chaque directive qui
exécute quelque chose est refusée (variantes de casse, d'espaces, de guillemets, dans des blocs) ;
copie 0600 dans un dossier 0700 effacés quoi qu'il arrive ; connexion privée sans connexion automatique ; aucun secret
dans la sortie ni dans les arguments de nmcli. Faux nmcli seulement."""
import json
import os
import unittest

from tests._vpn_faux import BaseVpn, NOUVEAU

SECRET = "CLEPRIVEEDETESTSEULEMENT0123456789abcdefghij="
OVPN = """client
dev tun
proto udp
remote 192.0.2.10 1194
nobind
<ca>
-----BEGIN CERTIFICATE-----
MIIBdummydummydummydummydummydummydummydummydummydummydummydummy
-----END CERTIFICATE-----
</ca>
<key>
-----BEGIN PRIVATE KEY-----
{secret}
-----END PRIVATE KEY-----
</key>
"""
WG = """[Interface]
PrivateKey = {secret}
Address = 192.0.2.2/32, 2001:db8::2/128

[Peer]
PublicKey = AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=
Endpoint = 192.0.2.10:51820
AllowedIPs = 0.0.0.0/0
"""

DANGEREUX_OVPN = [
    "up /bin/vrai", "down /bin/vrai", "route-up /bin/vrai", "route-pre-down /bin/vrai", "ipchange /bin/vrai",
    "client-connect /bin/vrai", "client-disconnect /bin/vrai", "learn-address /bin/vrai", "tls-verify /bin/vrai",
    "auth-user-pass-verify /bin/vrai via-env", "plugin /usr/lib/x.so", "script-security 2", "script-security 3",
    "script-security system", "script-security execve", "iproute /bin/vrai", "pkcs11-providers /usr/lib/x.so",
    "dns-updown /bin/vrai", "tls-crypt-v2-verify /bin/vrai", "config /home/user/autre.ovpn", "log /home/user/.bashrc",
    "log-append /home/user/.bashrc", "writepid /home/user/.profile", "status /home/user/.zshrc 10", "management 127.0.0.1 7505",
    # variantes
    "UP /bin/vrai", "Route-Up /bin/vrai", "\tup\t/bin/vrai", "   down    /bin/vrai", "--up /bin/vrai", "SCRIPT-SECURITY   2",
    "script-security\t2", "script-security 2 # commentaire", '"up" /bin/vrai', 'u"p" /bin/vrai', "'script-security' '2'",
    "script-security", "up\t\t/bin/vrai", "plugin  /usr/lib/x.so arg",
]
DANGEREUX_WG = ["PreUp = /bin/vrai", "PostUp = /bin/vrai", "PreDown = /bin/vrai", "PostDown = /bin/vrai", "postup=/bin/vrai",
                "POSTUP   =   /bin/vrai", "\tPostDown\t=\t/bin/vrai", "preup = iptables -A INPUT -j ACCEPT"]


class Import(BaseVpn):
    def ecrire(self, nom, texte, mode=0o644):
        p = self.r / "home" / nom
        p.write_text(texte)
        p.chmod(mode)
        return p

    def importer(self, p, **plus):
        return self.vpn("importer", str(p), **plus)

    def appels_import(self):
        return [a for a in self.appels() if a[:2] == ["connection", "import"]]

    # ── les cas qui marchent ──
    def test_openvpn_importe_prive_et_sans_connexion_automatique(self):
        p = self.ecrire("labo.ovpn", OVPN.format(secret=SECRET))
        r = self.importer(p)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn(NOUVEAU, r.stdout)
        i = json.loads((self.r / "import.json").read_text())
        self.assertEqual(i["type"], "openvpn")
        self.assertEqual(i["mode_fichier"], 0o600)
        self.assertEqual(i["mode_dossier"], 0o700)
        self.assertEqual(i["contenu"], OVPN.format(secret=SECRET))
        self.assertTrue(i["dossier"].startswith(str(self.r / "run")), "sous XDG_RUNTIME_DIR")
        # la copie et son dossier sont effacés
        self.assertFalse(os.path.exists(i["chemin"]))
        self.assertFalse(os.path.exists(i["dossier"]))
        modif = [a for a in self.appels() if a[:2] == ["connection", "modify"]]
        self.assertEqual(len(modif), 1)
        m = modif[0]
        self.assertEqual(m[:4], ["connection", "modify", "uuid", NOUVEAU])
        self.assertEqual(m[m.index("connection.autoconnect") + 1], "no")
        perm = m[m.index("connection.permissions") + 1]
        self.assertRegex(perm, r"^user:[A-Za-z0-9._][A-Za-z0-9._-]*$")

    def test_wireguard_importe(self):
        p = self.ecrire("maison.conf", WG.format(secret=SECRET))
        r = self.importer(p)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads((self.r / "import.json").read_text())["type"], "wireguard")

    def test_aucun_secret_dans_la_sortie_ni_dans_les_arguments(self):
        for nom, txt in (("a.ovpn", OVPN), ("b.conf", WG)):
            r = self.importer(self.ecrire(nom, txt.format(secret=SECRET)))
            self.assertNotIn(SECRET, r.stdout + r.stderr)
        self.assertNotIn(SECRET, json.dumps(self.appels()))
        # même quand nmcli échoue
        r = self.importer(self.ecrire("c.conf", WG.format(secret=SECRET)), NM_ECHEC_IMPORT="1")
        self.assertNotEqual(r.returncode, 0)
        self.assertNotIn(SECRET, r.stdout + r.stderr)

    # ── les refus de fichier ──
    def test_lien_symbolique_refuse(self):
        vrai = self.ecrire("vrai.ovpn", OVPN.format(secret=SECRET))
        lien = self.r / "home/lien.ovpn"
        lien.symlink_to(vrai)
        r = self.importer(lien)
        self.assertEqual(r.returncode, 1)
        self.assertIn("lien", r.stderr)
        self.assertEqual(self.appels_import(), [])

    def test_lien_vers_un_fichier_sensible_refuse(self):
        lien = self.r / "home/sensible.conf"
        lien.symlink_to("/etc/passwd")
        self.assertEqual(self.importer(lien).returncode, 1)
        self.assertEqual(self.appels_import(), [])

    def test_trop_gros_refuse(self):
        p = self.ecrire("gros.ovpn", "client\n" + "# " + "x" * 70000 + "\n")
        r = self.importer(p)
        self.assertEqual(r.returncode, 1)
        self.assertIn("trop gros", r.stderr)
        self.assertEqual(self.appels_import(), [])
        ok = self.ecrire("limite.ovpn", ("# " + "x" * 100 + "\n") * 600 + "client\n")       # environ 61 Kio : accepté
        self.assertLess(ok.stat().st_size, 65536)
        self.assertEqual(self.importer(ok).returncode, 0)

    def test_extension_et_type_de_fichier(self):
        for nom in ("x.txt", "x.ovpn.sh", "x", "x.OVPNN"):
            self.assertEqual(self.importer(self.ecrire(nom, OVPN.format(secret=SECRET))).returncode, 1, nom)
        self.assertEqual(self.importer(self.ecrire("Majuscules.OVPN", OVPN.format(secret=SECRET))).returncode, 0)
        self.assertEqual(self.importer(self.r / "home").returncode, 1)                        # un dossier
        self.assertEqual(self.importer(self.r / "home/absent.ovpn").returncode, 1)
        r = self.importer(self.ecrire("binaire.ovpn", "client\n\0\1\2"))
        self.assertEqual(r.returncode, 1)

    def test_fifo_refuse_sans_bloquer(self):
        f = self.r / "home/tube.ovpn"
        os.mkfifo(f)
        r = self.importer(f)
        self.assertEqual(r.returncode, 1)

    # ── les directives dangereuses ──
    def test_chaque_directive_openvpn_dangereuse_est_refusee(self):
        for i, d in enumerate(DANGEREUX_OVPN):
            for forme in ("debut", "milieu", "bloc"):
                if forme == "debut":
                    txt = d + "\n" + OVPN.format(secret=SECRET)
                elif forme == "milieu":
                    txt = "client\ndev tun\r\n" + d + "\r\nremote 192.0.2.10 1194\n"
                else:
                    txt = "client\n<connection>\nremote 192.0.2.10 1194\n" + d + "\n</connection>\n"
                p = self.ecrire(f"d{i}.ovpn", txt)
                r = self.importer(p)
                self.assertEqual(r.returncode, 1, (d, forme, r.stdout))
                self.assertIn("refusée", r.stderr, d)
        self.assertEqual(self.appels_import(), [], "rien n'est passé à nmcli")

    def test_chaque_directive_wireguard_dangereuse_est_refusee(self):
        for i, d in enumerate(DANGEREUX_WG):
            txt = WG.format(secret=SECRET).replace("[Peer]", d + "\n\n[Peer]")
            r = self.importer(self.ecrire(f"w{i}.conf", txt))
            self.assertEqual(r.returncode, 1, d)
            self.assertIn("refusée", r.stderr, d)
            r = self.importer(self.ecrire(f"v{i}.conf", WG.format(secret=SECRET) + d + "\n"))     # tout au bout, dans [Peer]
            self.assertEqual(r.returncode, 1, d)
        self.assertEqual(self.appels_import(), [])

    def test_directives_inoffensives_ou_en_commentaire_acceptees(self):
        txt = ("client\n# up /bin/vrai\n; down /bin/vrai\nscript-security 1\nup-restart\nup-delay\nscript-security 0\n"
               "dev tun\nremote 192.0.2.10 1194\nsetenv-safe X 1\nroute-delay 2\n")
        r = self.importer(self.ecrire("ok.ovpn", txt))
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_auth_user_pass_directive_seule_acceptee(self):
        # le bloc en ligne est pris en charge (tests/test_nc_vpn_auth.py) ; la directive seule passe comme avant
        self.assertEqual(self.importer(self.ecrire("seule.ovpn", "client\nauth-user-pass\nremote 192.0.2.10 1194\n")).returncode, 0)

    def test_certificat_en_chemin_relatif_absent_refuse_chemin_complet_accepte(self):
        # relatif : lu depuis le dossier du .ovpn (voir test_nc_vpn_certs.py) ; ici le fichier n'existe pas
        r = self.importer(self.ecrire("rel.ovpn", "client\nca ca.crt\nremote 192.0.2.10 1194\n"))
        self.assertEqual(r.returncode, 1)
        self.assertIn("refusé", r.stderr)
        # chemin complet d'un fichier que l'utilisateur peut lire : accepté
        ca = self.ecrire("ca.crt", "certificat")
        r = self.importer(self.ecrire("abs.ovpn", f"client\nca {ca}\nremote 192.0.2.10 1194\n"))
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_certificat_que_root_seul_peut_lire_refuse(self):
        # openvpn lit ces fichiers en root : un fichier illisible pour l'utilisateur, un lien, /proc, /sys, /dev ou un
        # fichier absent sont refusés, et rien ne part à nmcli
        illisible = self.ecrire("prive.key", "secret", mode=0o000)
        lien = self.r / "home/lien.crt"
        lien.symlink_to(self.ecrire("vrai.crt", "certificat"))
        cas = [f"ca {lien}", "key /proc/self/environ", "extra-certs /sys/kernel/notes", "ca /dev/zero",
               "ca /home/user/absent.crt"]
        if os.geteuid() != 0:                                # root lit tout (conteneurs de la CI)
            cas.append(f"cert {illisible}")
        if os.geteuid() != 0 and os.path.exists("/etc/shadow") and not os.access("/etc/shadow", os.R_OK):
            cas.append("cert /etc/shadow")
        for i, c in enumerate(cas):
            r = self.importer(self.ecrire(f"c{i}.ovpn", f"client\n{c}\nremote 192.0.2.10 1194\n"))
            self.assertEqual(r.returncode, 1, c)
            self.assertIn("refusé", r.stderr, c)
        self.assertEqual(self.appels_import(), [])

    # ── le ménage ──
    def test_copie_et_dossier_effaces_meme_si_nmcli_echoue(self):
        r = self.importer(self.ecrire("labo.ovpn", OVPN.format(secret=SECRET)), NM_ECHEC_IMPORT="1")
        self.assertEqual(r.returncode, 1)
        i = json.loads((self.r / "import.json").read_text())
        self.assertEqual(i["mode_fichier"], 0o600)
        self.assertFalse(os.path.exists(i["chemin"]))
        self.assertFalse(os.path.exists(i["dossier"]))
        self.assertEqual(os.listdir(self.r / "run"), [])
        self.assertEqual(os.listdir(self.r / "tmp"), [])
        self.assertIn("refusé", r.stderr)
        self.assertNotIn(i["dossier"], r.stderr)

    def test_echec_de_la_mise_en_prive_annule_l_import(self):
        r = self.importer(self.ecrire("labo.ovpn", OVPN.format(secret=SECRET)), NM_ECHEC_MODIFY="1")
        self.assertEqual(r.returncode, 1)
        self.assertIn(["connection", "delete", "uuid", NOUVEAU], self.appels())
        self.assertEqual(os.listdir(self.r / "run"), [])

    def test_networkmanager_arrete(self):
        r = self.importer(self.ecrire("labo.ovpn", OVPN.format(secret=SECRET)), NM_ARRETE="1")
        self.assertEqual(r.returncode, 1)
        self.assertEqual(os.listdir(self.r / "run"), [])

    def test_sans_xdg_runtime_dir_repli_sur_tmpdir_et_menage(self):
        env = self.env()
        env.pop("XDG_RUNTIME_DIR")
        import subprocess, sys
        from tests._vpn_faux import BIN
        p = self.ecrire("labo.ovpn", OVPN.format(secret=SECRET))
        r = subprocess.run([sys.executable, str(BIN), "importer", str(p)], env=env, capture_output=True, text=True, timeout=30, stdin=subprocess.DEVNULL)
        self.assertEqual(r.returncode, 0, r.stderr)
        i = json.loads((self.r / "import.json").read_text())
        self.assertEqual(i["mode_dossier"], 0o700)
        self.assertEqual(os.listdir(self.r / "tmp"), [])

    def test_anglais(self):
        r = self.importer(self.ecrire("x.ovpn", "up /bin/vrai\n"), NC_LANGUE="en")
        self.assertEqual(r.returncode, 1)
        self.assertIn("refused", r.stderr)


if __name__ == "__main__":
    unittest.main()

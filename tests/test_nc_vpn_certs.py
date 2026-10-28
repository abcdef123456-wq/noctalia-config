"""nc-vpn importer, certificats en chemin relatif : lus depuis le dossier du .ovpn (fichier ordinaire sans lien, lisible par
l'utilisateur, hors /proc /sys /dev, sans détour par un dossier fermé), PEM texte seulement, mis EN LIGNE dans la copie, 64 Kio
au plus au total, et le résultat repasse par verifier(). L'original n'est jamais modifié. Faux nmcli seulement."""
import json
import os
import unittest

from tests._vpn_faux import BaseVpn

PEM_CA = "-----BEGIN CERTIFICATE-----\nMIIBdummydummydummydummydummydummy\n-----END CERTIFICATE-----\n"
PEM_CERT = "-----BEGIN CERTIFICATE-----\nMIIBclientclientclientclientclient\n-----END CERTIFICATE-----\n"
PEM_KEY = "-----BEGIN PRIVATE KEY-----\nCLEPRIVEEDETESTSEULEMENT0123456789\n-----END PRIVATE KEY-----\n"
PEM_TA = "-----BEGIN OpenVPN Static key V1-----\n0123456789abcdef0123456789abcdef\n-----END OpenVPN Static key V1-----\n"
BASE = "client\ndev tun\nremote 192.0.2.10 1194\n"


class Certs(BaseVpn):
    def ecrire(self, nom, texte, mode=0o644):
        p = self.r / "home" / nom
        p.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(texte, bytes):
            p.write_bytes(texte)
        else:
            p.write_text(texte)
        p.chmod(mode)
        return p

    def importer(self, p, **plus):
        return self.vpn("importer", str(p), **plus)

    def imports(self):
        return [a for a in self.appels() if a[:2] == ["connection", "import"]]

    def copie(self):
        return json.loads((self.r / "import.json").read_text())["contenu"]

    def test_certificats_relatifs_mis_en_ligne(self):
        self.ecrire("ca.crt", PEM_CA)
        self.ecrire("client.crt", "Certificate:\n    texte openssl avant\n" + PEM_CERT)
        self.ecrire("client.key", PEM_KEY)
        self.ecrire("ta.key", PEM_TA)
        self.ecrire("tc.key", PEM_TA)
        orig = BASE + 'ca ca.crt\ncert ./client.crt\nkey "client.key"\ntls-auth ta.key 1\ntls-crypt tc.key\n'
        p = self.ecrire("labo.ovpn", orig)
        r = self.importer(p)
        self.assertEqual(r.returncode, 0, r.stderr)
        c = self.copie()
        for mot, pem in (("ca", PEM_CA), ("cert", PEM_CERT), ("key", PEM_KEY), ("tls-auth", PEM_TA), ("tls-crypt", PEM_TA)):
            self.assertIn(f"<{mot}>\n{pem}</{mot}>\n", c, mot)
        self.assertIn("key-direction 1", c)
        self.assertNotIn("texte openssl", c)                        # hors des blocs PEM : jeté
        self.assertNotRegex(c, r"(?m)^(ca|cert|key|tls-auth|tls-crypt)\s")
        self.assertEqual(p.read_text(), orig)                       # l'original est intact
        self.assertEqual(os.listdir(self.r / "run"), [])

    def test_sous_dossier_et_point_point_dans_un_dossier_lisible(self):
        self.ecrire("certs/ca.crt", PEM_CA)
        self.ecrire("autre/cert.crt", PEM_CERT)
        p = self.ecrire("vpn/labo.ovpn", BASE + "ca ../certs/ca.crt\ncert ../autre/../autre/cert.crt\n")
        r = self.importer(p)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("<ca>\n" + PEM_CA, self.copie())

    def test_resultat_repasse_par_verifier(self):
        self.ecrire("ca.crt", PEM_CA)
        for d in ("up /bin/vrai", "script-security 2", "plugin /usr/lib/x.so", "config /home/user/a.ovpn"):
            r = self.importer(self.ecrire("d.ovpn", BASE + "ca ca.crt\n" + d + "\n"))
            self.assertEqual(r.returncode, 1, d)
            self.assertIn("refusée", r.stderr)
        self.assertEqual(self.imports(), [])

    def test_fichier_pem_piege_ne_peut_pas_sortir_de_son_bloc(self):
        self.ecrire("ca.crt", "-----BEGIN CERTIFICATE-----\nAAAA\n</ca>\nup /bin/vrai\n<ca>\n-----END CERTIFICATE-----\n")
        r = self.importer(self.ecrire("a.ovpn", BASE + "ca ca.crt\n"))
        self.assertEqual(r.returncode, 1)
        self.ecrire("ca2.crt", "-----BEGIN CERTIFICATE-----\nAAAA\nup /bin/vrai\n-----END CERTIFICATE-----\n")
        r = self.importer(self.ecrire("b.ovpn", BASE + "ca ca2.crt\n"))
        self.assertEqual(r.returncode, 1)
        self.assertIn("refusée", r.stderr)
        self.assertEqual(self.imports(), [])

    def test_refus_binaire_pkcs12_pas_pem_vide(self):
        self.ecrire("bin.p12", b"\x30\x82\x01\x00\x00\x01binaire")
        self.ecrire("sans.crt", "juste du texte\n")
        self.ecrire("vide.crt", "")
        self.ecrire("coupe.crt", "-----BEGIN CERTIFICATE-----\nAAAA\n")
        for ligne in ("pkcs12 bin.p12", "ca bin.p12", "ca sans.crt", "ca vide.crt", "ca coupe.crt"):
            r = self.importer(self.ecrire("x.ovpn", BASE + ligne + "\n"), NC_LANGUE="fr")
            self.assertEqual(r.returncode, 1, ligne)
            self.assertIn("PEM" if ligne != "pkcs12 bin.p12" else "pkcs12", r.stderr, ligne)
        self.assertEqual(self.imports(), [])

    def test_trop_gros_une_fois_mis_en_ligne(self):
        gros = "-----BEGIN CERTIFICATE-----\n" + ("A" * 64 + "\n") * 500 + "-----END CERTIFICATE-----\n"      # environ 32 Kio
        self.ecrire("a.crt", gros)
        self.ecrire("b.crt", gros)
        self.ecrire("c.crt", gros)
        r = self.importer(self.ecrire("t.ovpn", BASE + "ca a.crt\ncert b.crt\nextra-certs c.crt\n"))
        self.assertEqual(r.returncode, 1)
        self.assertIn("64 Kio", r.stderr)
        self.assertEqual(self.imports(), [])
        # un fichier de certificat lui-même trop gros
        self.ecrire("enorme.crt", "-----BEGIN CERTIFICATE-----\n" + ("A" * 64 + "\n") * 1100 + "-----END CERTIFICATE-----\n")
        r = self.importer(self.ecrire("t2.ovpn", BASE + "ca enorme.crt\n"))
        self.assertEqual(r.returncode, 1)
        self.assertIn("64 Kio", r.stderr)

    def test_lien_proc_illisible_absent_refuses(self):
        self.ecrire("vrai.crt", PEM_CA)
        (self.r / "home/lien.crt").symlink_to(self.r / "home/vrai.crt")
        (self.r / "home/dlien").symlink_to(self.r / "home")
        os.mkdir(self.r / "home/ferme", 0o755)
        self.ecrire("ferme/ca.crt", PEM_CA)
        cas = ["ca lien.crt", "ca dlien/vrai.crt", "ca ../../../../../../proc/self/environ", "ca ../../../../../../dev/zero",
               "ca absent.crt", "ca .", "ca ../home"]
        if os.geteuid() != 0:                                  # root lit tout (conteneurs de la CI)
            self.ecrire("prive.crt", PEM_CA, mode=0o000)
            cas.append("ca prive.crt")
        for i, c in enumerate(cas):
            r = self.importer(self.ecrire(f"c{i}.ovpn", BASE + c + "\n"))
            self.assertEqual(r.returncode, 1, c)
        self.assertEqual(self.imports(), [])

    def test_point_point_par_un_dossier_ferme_refuse(self):
        if os.geteuid() == 0:
            self.skipTest("root traverse tout")
        self.ecrire("ouvert/ca.crt", PEM_CA)
        os.mkdir(self.r / "home/ferme")
        (self.r / "home/ferme/ca.crt").write_text(PEM_CA)
        self.ecrire("labo.ovpn", BASE + "ca ferme/../ouvert/ca.crt\n")
        os.chmod(self.r / "home/ferme", 0o000)
        try:
            r = self.importer(self.r / "home/labo.ovpn")
            self.assertEqual(r.returncode, 1)
            self.assertIn("dossier", r.stderr)
        finally:
            os.chmod(self.r / "home/ferme", 0o755)
        self.assertEqual(self.imports(), [])

    def test_arguments_en_trop_et_directives_non_ajoutees(self):
        self.ecrire("ca.crt", PEM_CA)
        for ligne in ("ca ca.crt extra", "tls-auth ca.crt 2", "tls-auth ca.crt 1 x", "crl-verify ca.crt dir"):
            r = self.importer(self.ecrire("e.ovpn", BASE + ligne + "\n"))
            self.assertEqual(r.returncode, 1, ligne)
        # directives toujours refusées, certificats relatifs ou pas
        for ligne in ("config ca.crt", "log ca.crt", "writepid ca.crt"):
            r = self.importer(self.ecrire("f.ovpn", BASE + ligne + "\n"))
            self.assertEqual(r.returncode, 1, ligne)
        self.assertEqual(self.imports(), [])

    def test_wireguard_inchange(self):
        wg = "[Interface]\nPrivateKey = AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=\nAddress = 192.0.2.2/32\n\n[Peer]\nPublicKey = AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=\nAllowedIPs = 0.0.0.0/0\n"
        r = self.importer(self.ecrire("w.conf", wg))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.copie(), wg)

    def test_anglais(self):
        self.ecrire("bin.p12", b"\x30\x82\x01\x00\x00\x01binaire")
        r = self.importer(self.ecrire("x.ovpn", BASE + "pkcs12 bin.p12\n"), NC_LANGUE="en")
        self.assertEqual(r.returncode, 1)
        self.assertIn("binary", r.stderr)


if __name__ == "__main__":
    unittest.main()

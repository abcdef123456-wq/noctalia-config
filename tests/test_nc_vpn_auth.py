"""nc-vpn importer, bloc <auth-user-pass> : l'identifiant va dans la connexion (vpn.data), le mot de passe dans le trousseau
(secret-tool, par l'entrée standard) ; jamais en argument, ni dans la sortie, ni dans les erreurs, ni dans un fichier
permanent ; trousseau absent ou fermé = refus et connexion supprimée ; original intact. Faux nmcli et faux secret-tool."""
import json
import os
import shutil
import sys
import unittest

from tests._vpn_faux import BaseVpn, NOUVEAU

MDP = "MOTDEPASSEDETEST"
BASE = "client\ndev tun\nremote 192.0.2.10 1194\n"
AVEC = BASE + "<auth-user-pass>\nmoi\n" + MDP + "\n</auth-user-pass>\n"


class Auth(BaseVpn):
    def ecrire(self, nom, texte):
        p = self.r / "home" / nom
        p.write_text(texte)
        return p

    def secret_appels(self):
        p = self.r / "secret.jsonl"
        return [json.loads(l) for l in p.read_text().splitlines()] if p.exists() else []

    def imports(self):
        return [a for a in self.appels() if a[:2] == ["connection", "import"]]

    def tout_lu(self):
        """Tout ce que le test peut voir hors secret-stdin : arguments des processus, fichiers du faux monde."""
        brut = json.dumps(self.appels()) + json.dumps(self.secret_appels())
        for racine, dossiers, fichiers in os.walk(self.r):
            if racine == str(self.r):
                dossiers[:] = [d for d in dossiers if d != "home"]       # « home » tient l'original du test, qui a le mot de passe
            for f in fichiers:
                if f in ("secret-stdin", "nmcli", "secret-tool"):
                    continue
                try:
                    brut += (self.r / racine / f).read_text(errors="replace")
                except OSError:
                    pass
        return brut

    def test_import_avec_mot_de_passe(self):
        p = self.ecrire("labo.ovpn", AVEC)
        r = self.vpn("importer", str(p))
        self.assertEqual(r.returncode, 0, r.stderr)
        # la copie donnée à nmcli : plus de mot de passe, mais la directive seule
        i = json.loads((self.r / "import.json").read_text())
        self.assertNotIn(MDP, i["contenu"])
        self.assertNotIn("<auth-user-pass>", i["contenu"])
        self.assertIn("\nauth-user-pass\n", i["contenu"])
        self.assertEqual(i["mode_fichier"], 0o600)
        self.assertEqual(i["mode_dossier"], 0o700)
        # identifiant dans la connexion, mot de passe « agent-owned »
        modif = [a for a in self.appels() if a[:2] == ["connection", "modify"]][0]
        self.assertEqual(modif[modif.index("+vpn.data") + 1], "username=moi,password-flags=1")
        # le secret passe par l'entrée standard de secret-tool, avec les attributs de NetworkManager
        self.assertEqual((self.r / "secret-stdin").read_bytes(), MDP.encode())
        (a,) = self.secret_appels()
        self.assertEqual(a[0], "store")
        self.assertEqual(a[a.index("xdg:schema") + 1], "org.freedesktop.NetworkManager.Connection")
        self.assertEqual(a[a.index("connection-uuid") + 1], NOUVEAU)
        self.assertEqual(a[a.index("setting-name") + 1], "vpn")
        self.assertEqual(a[a.index("setting-key") + 1], "password")
        # l'original est intact ; rien d'autre ne contient le mot de passe
        self.assertEqual(p.read_text(), AVEC)
        self.assertNotIn(MDP, r.stdout + r.stderr)
        self.assertNotIn(MDP, self.tout_lu())
        self.assertEqual(os.listdir(self.r / "run"), [])
        self.assertEqual(os.listdir(self.r / "tmp"), [])

    def test_aucun_argument_ne_contient_le_mot_de_passe(self):
        self.vpn("importer", str(self.ecrire("a.ovpn", AVEC)))
        for a in self.appels() + self.secret_appels():
            self.assertFalse(any(MDP in x for x in a), a)

    def test_secret_tool_echoue_en_recrachant_son_entree(self):
        r = self.vpn("importer", str(self.ecrire("a.ovpn", AVEC)), SECRET_ECHEC="1")
        self.assertEqual(r.returncode, 1)
        self.assertNotIn(MDP, r.stdout + r.stderr)
        self.assertIn("***", r.stderr)
        self.assertIn(["connection", "delete", "uuid", NOUVEAU], self.appels())
        self.assertEqual(os.listdir(self.r / "run"), [])

    def test_trousseau_ferme_ou_absent_refuse_et_supprime(self):
        r = self.vpn("importer", str(self.ecrire("a.ovpn", AVEC)), SECRET_ECHEC="2", NC_LANGUE="fr")
        self.assertEqual(r.returncode, 1)
        self.assertIn("trousseau", r.stderr)
        self.assertIn(["connection", "delete", "uuid", NOUVEAU], self.appels())
        self.assertNotIn(MDP, r.stdout + r.stderr + self.tout_lu())

    def test_secret_tool_absent_refuse_avant_tout_import(self):
        bin2 = self.r / "bin2"
        bin2.mkdir()
        shutil.copy(self.r / "faux-bin" / "nmcli", bin2 / "nmcli")
        (bin2 / "python3").symlink_to(sys.executable)
        r = self.vpn("importer", str(self.ecrire("a.ovpn", AVEC)), PATH=str(bin2))
        self.assertEqual(r.returncode, 1)
        self.assertIn("secret-tool", r.stderr)
        self.assertEqual(self.imports(), [])
        self.assertNotIn(MDP, r.stdout + r.stderr)
        # sans mot de passe dans le fichier, secret-tool n'est pas demandé
        self.assertEqual(self.vpn("importer", str(self.ecrire("b.ovpn", BASE)), PATH=str(bin2)).returncode, 0)

    def test_pas_de_secret_tool_pour_un_fichier_sans_mot_de_passe(self):
        r = self.vpn("importer", str(self.ecrire("b.ovpn", BASE + "auth-user-pass\n")))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.secret_appels(), [])

    def test_echec_de_la_mise_en_prive_ne_range_aucun_secret(self):
        r = self.vpn("importer", str(self.ecrire("a.ovpn", AVEC)), NM_ECHEC_MODIFY="1")
        self.assertEqual(r.returncode, 1)
        self.assertEqual(self.secret_appels(), [])
        self.assertNotIn(MDP, r.stdout + r.stderr)

    def test_blocs_mal_formes_refuses(self):
        cas = {
            "un": BASE + "<auth-user-pass>\nmoi\n</auth-user-pass>\n",
            "trois": BASE + "<auth-user-pass>\nmoi\n" + MDP + "\nautre\n</auth-user-pass>\n",
            "vide": BASE + "<auth-user-pass>\n</auth-user-pass>\n",
            "ouvert": BASE + "<auth-user-pass>\nmoi\n" + MDP + "\n",
            "deux": AVEC + "<auth-user-pass>\nx\n" + MDP + "\n</auth-user-pass>\n",
            "virgule": BASE + "<auth-user-pass>\nmo,i\n" + MDP + "\n</auth-user-pass>\n",
            "controle": BASE + "<auth-user-pass>\nmoi\n" + MDP + "\x07\n</auth-user-pass>\n",
        }
        for nom, txt in cas.items():
            r = self.vpn("importer", str(self.ecrire(nom + ".ovpn", txt)))
            self.assertEqual(r.returncode, 1, nom)
            self.assertNotIn(MDP, r.stdout + r.stderr, nom)
        self.assertEqual(self.imports(), [])
        self.assertEqual(self.secret_appels(), [])

    def test_bloc_dans_un_conf_wireguard_toujours_refuse(self):
        r = self.vpn("importer", str(self.ecrire("a.conf", "[Interface]\nPrivateKey = x\n<auth-user-pass>\nmoi\n" + MDP + "\n</auth-user-pass>\n")))
        self.assertEqual(r.returncode, 1)
        self.assertNotIn(MDP, r.stdout + r.stderr)

    def test_directives_dangereuses_toujours_refusees_apres_transformation(self):
        for d in ("up /bin/vrai", "script-security 2", "plugin /usr/lib/x.so", "config /home/user/a.ovpn"):
            r = self.vpn("importer", str(self.ecrire("d.ovpn", AVEC + d + "\n")))
            self.assertEqual(r.returncode, 1, d)
            self.assertNotIn(MDP, r.stdout + r.stderr)
        self.assertEqual(self.imports(), [])
        self.assertEqual(self.secret_appels(), [])

    def test_mot_de_passe_avec_espaces_et_caracteres_speciaux(self):
        mdp = '  a b"c\'d$e\\f;g:h  '
        r = self.vpn("importer", str(self.ecrire("s.ovpn", BASE + "<auth-user-pass>\nmoi\n" + mdp + "\n</auth-user-pass>\n")))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual((self.r / "secret-stdin").read_bytes(), mdp.encode())

    def test_anglais(self):
        r = self.vpn("importer", str(self.ecrire("a.ovpn", AVEC)), SECRET_ECHEC="2", NC_LANGUE="en")
        self.assertEqual(r.returncode, 1)
        self.assertIn("keyring", r.stderr)


if __name__ == "__main__":
    unittest.main()

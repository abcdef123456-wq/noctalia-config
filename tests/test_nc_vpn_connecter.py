"""nc-vpn connecter, connexion VPN au mot de passe gardé par le trousseau (password-flags=1) : aucun agent de secrets ne tourne
forcément, donc le mot de passe est relu (secret-tool lookup) et donné à nmcli par un passwd-file temporaire
(vpn.secrets.password:…), créé en 0600 dans un dossier 0700, effacé quoi qu'il arrive, jamais en argument. Faux outils seulement."""
import json
import os
import subprocess
import unittest
from unittest import mock

from tests._vpn_faux import BaseVpn, BIN, U1, U2

MDP = "MOTDEPASSEDETEST"


class Connecter(BaseVpn):
    def setUp(self):
        super().setUp()
        (self.r / "vpn_data.json").write_text(json.dumps({U1: "password-flags = 1, username = moi"}))
        (self.r / "secret-valeur").write_bytes(MDP.encode())

    def ups(self):
        return [a for a in self.appels() if a[:2] == ["connection", "up"]]

    def passwd(self):
        p = self.r / "passwd.jsonl"
        return [json.loads(l) for l in p.read_text().splitlines()] if p.exists() else []

    def secret_appels(self):
        p = self.r / "secret.jsonl"
        return [json.loads(l) for l in p.read_text().splitlines()] if p.exists() else []

    def remettre_a_zero(self):
        for n in ("appels.jsonl", "secret.jsonl", "passwd.jsonl"):
            if (self.r / n).exists():
                (self.r / n).unlink()
        from tests._vpn_faux import connexions
        (self.r / "etat.json").write_text(json.dumps(connexions()))

    def tout_lu(self):
        brut = json.dumps(self.appels()) + json.dumps(self.secret_appels())
        for racine, _, fichiers in os.walk(self.r):
            for f in fichiers:
                if f in ("secret-valeur", "secret-stdin", "nmcli", "secret-tool", "gdbus", "passwd.jsonl"):
                    continue
                try:
                    brut += (self.r / racine / f).read_text(errors="replace")
                except OSError:
                    pass
        return brut

    def test_mot_de_passe_donne_par_passwd_file(self):
        r = self.vpn("connecter", U1)
        self.assertEqual(r.returncode, 0, r.stderr)
        (up,) = self.ups()
        self.assertEqual(up[:4], ["connection", "up", "uuid", U1])
        self.assertEqual(up[4], "passwd-file")
        (p,) = self.passwd()
        self.assertEqual(p["chemin"], up[5])
        self.assertEqual(p["contenu"], "vpn.secrets.password:" + MDP + "\n")
        self.assertEqual(p["mode"], 0o600, "0600 au moment où nmcli le lit")
        self.assertEqual(p["mode_dossier"], 0o700)
        self.assertTrue(p["chemin"].startswith(str(self.r / "run")), "sous XDG_RUNTIME_DIR")
        self.assertFalse(os.path.exists(p["chemin"]))
        self.assertEqual(os.listdir(self.r / "run"), [])
        self.assertEqual(os.listdir(self.r / "tmp"), [])
        self.assertNotIn(MDP, r.stdout + r.stderr)
        (lk,) = self.secret_appels()
        self.assertEqual(lk[0], "lookup")
        self.assertEqual(lk[lk.index("connection-uuid") + 1], U1)
        self.assertEqual(lk[lk.index("xdg:schema") + 1], "org.freedesktop.NetworkManager.Connection")

    def test_le_fichier_est_cree_en_exclusif_sans_suivre_les_liens(self):
        # le code crée avec os.open(O_CREAT|O_EXCL|O_WRONLY|O_NOFOLLOW, 0o600), jamais open() puis chmod
        src = BIN.read_text()
        self.assertIn("os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600", src[src.index("def connecter"):src.index("def deconnecter")])

    def test_jamais_en_argument(self):
        self.vpn("connecter", U1)
        for a in self.appels() + self.secret_appels():
            self.assertFalse(any(MDP in x for x in a), a)

    def test_fichier_efface_si_nmcli_echoue_et_erreur_masquee(self):
        r = self.vpn("connecter", U1, NM_ECHEC_UP="3")           # nmcli recrache le contenu du fichier dans son erreur
        self.assertEqual(r.returncode, 1)
        self.assertNotIn(MDP, r.stdout + r.stderr)
        self.assertIn("***", r.stderr)
        self.assertFalse(os.path.exists(self.passwd()[0]["chemin"]))
        self.assertEqual(os.listdir(self.r / "run"), [])

    def test_fichier_efface_apres_un_delai_depasse(self):
        # nmcli() rend 126 quand le délai est dépassé ; ici le délai lui-même est simulé : le « finally » doit nettoyer
        import importlib.machinery
        import importlib.util
        spec = importlib.util.spec_from_loader("ncvpn_delai", importlib.machinery.SourceFileLoader("ncvpn_delai", str(BIN)))
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        vus = []

        def faux_nmcli(args, delai=15):
            if "passwd-file" in args:
                vus.append(args[args.index("passwd-file") + 1])
                self.assertTrue(os.path.exists(vus[0]))
                raise subprocess.TimeoutExpired("nmcli", delai)
            return 0, "", ""
        with mock.patch.dict(os.environ, {"XDG_RUNTIME_DIR": str(self.r / "run")}):
            with mock.patch.object(m, "nmcli", faux_nmcli), mock.patch.object(m, "mot_de_passe_agent_owned", lambda u: True), \
                    mock.patch.object(m, "lire_secret", lambda u: MDP), \
                    mock.patch.object(m, "connue", lambda u: {"uuid": u, "nom": "Labo", "type": "vpn", "active": False}):
                with self.assertRaises(subprocess.TimeoutExpired):
                    m.connecter(U1)
        self.assertEqual(len(vus), 1)
        self.assertFalse(os.path.exists(vus[0]))
        self.assertEqual(os.listdir(self.r / "run"), [])

    def test_sans_password_flags_comme_avant_sans_secret_tool(self):
        (self.r / "vpn_data.json").write_text("{}")
        r = self.vpn("connecter", U1)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.ups(), [["connection", "up", "uuid", U1]])
        self.assertEqual(self.secret_appels(), [])
        self.assertEqual(self.passwd(), [])

    def test_wireguard_ne_cherche_pas_de_secret(self):
        (self.r / "vpn_data.json").write_text(json.dumps({U2: "password-flags = 1"}))
        self.vpn("deconnecter", U2)
        self.remettre_a_zero()
        (self.r / "etat.json").write_text(json.dumps([dict(uuid=U2, type="wireguard", active=False, dev="wg0", nom="Maison")]))
        r = self.vpn("connecter", U2)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.secret_appels(), [])
        self.assertEqual(self.passwd(), [])

    def test_secret_introuvable_essai_sans_fichier_puis_message_clair(self):
        (self.r / "secret-valeur").unlink()
        r = self.vpn("connecter", U1)                               # un agent existe peut-être : l'essai réussit
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.ups(), [["connection", "up", "uuid", U1]])
        self.assertEqual(self.passwd(), [])
        self.remettre_a_zero()
        r = self.vpn("connecter", U1, NM_ECHEC_UP="2")
        self.assertEqual(r.returncode, 1)
        self.assertIn("secret introuvable dans le trousseau", r.stderr)
        self.remettre_a_zero()
        r = self.vpn("connecter", U1, NM_ECHEC_UP="2", NC_LANGUE="en")
        self.assertIn("secret not found in the keyring", r.stderr)

    def test_lookup_qui_echoue_en_ecrivant_le_secret_ne_laisse_aucune_trace(self):
        r = self.vpn("connecter", U1, SECRET_LOOKUP_ECHEC="1", NM_ECHEC_UP="2")
        self.assertEqual(r.returncode, 1)
        self.assertIn("secret introuvable dans le trousseau", r.stderr)
        self.assertNotIn(MDP, r.stdout + r.stderr + self.tout_lu())
        self.assertEqual(self.passwd(), [])
        self.remettre_a_zero()
        r = self.vpn("connecter", U1, SECRET_LOOKUP_ECHEC="1")        # même quand la connexion réussit
        self.assertNotIn(MDP, r.stdout + r.stderr + self.tout_lu())

    def test_mot_de_passe_du_trousseau_avec_saut_de_ligne_retour_ou_nul_refuse(self):
        for brut in (b"AAAA\nvpn.secrets.autre:BBBB", b"AAAA\rBBBB", b"AAAA\x00BBBB"):
            self.remettre_a_zero()
            (self.r / "secret-valeur").write_bytes(brut)
            r = self.vpn("connecter", U1)
            self.assertEqual(r.returncode, 1, brut)
            self.assertIn("caractère de contrôle", r.stderr)
            self.assertEqual(self.ups(), [], brut)
            self.assertEqual(self.passwd(), [])
            self.assertNotIn("AAAA", r.stdout + r.stderr)
        self.assertEqual(os.listdir(self.r / "run"), [])


if __name__ == "__main__":
    unittest.main()

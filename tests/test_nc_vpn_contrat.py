"""nc-vpn : le contrat JSON version 1 (docs/vpn-contrat.md) — champs, types, codes de sortie, erreurs — et les alias de
compatibilité (status --json, connect, disconnect) qui doivent donner EXACTEMENT les mêmes sorties et les mêmes appels.
Faux nmcli seulement (tests/_vpn_faux.py), adresses de documentation."""
import json
import unittest

from tests._vpn_faux import BaseVpn, U1, U2, U3, U4, NOUVEAU


class ContratVpn(BaseVpn):
    def json(self, *args, **plus):
        r = self.vpn(*args, **plus)
        return r, json.loads(r.stdout)

    def test_etat_json_champs_et_types(self):
        r, d = self.json("etat-json")
        self.assertEqual((r.returncode, d["contrat"], d["disponible"]), (0, 1, True))
        self.assertEqual(set(d), {"contrat", "disponible", "connexions", "actives"})
        for c in d["connexions"]:
            self.assertEqual(set(c), {"uuid", "nom", "type", "active", "interface"})
            self.assertIsInstance(c["uuid"], str)
            self.assertIsInstance(c["nom"], str)
            self.assertIn(c["type"], ("vpn", "wireguard"))
            self.assertIsInstance(c["active"], bool)
            self.assertIsInstance(c["interface"], str)

    def test_connecter_json(self):
        r, d = self.json("connecter", U1, "--json")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(d, {"contrat": 1, "ok": True, "action": "connecter", "uuid": U1, "nom": "Labo", "actif": True, "deja": False})
        self.assertIn(U1, self.etat_actifs())
        r, d = self.json("connecter", U1, "--json")                 # déjà monté : rien à refaire
        self.assertEqual((r.returncode, d["deja"], d["actif"]), (0, True, True))

    def test_deconnecter_json(self):
        r, d = self.json("deconnecter", U2, "--json")
        self.assertEqual(d, {"contrat": 1, "ok": True, "action": "deconnecter", "uuid": U2, "nom": "Maison: 192.0.2.1", "actif": False, "deja": False})
        self.assertNotIn(U2, self.etat_actifs())
        r, d = self.json("deconnecter", U1, "--json")               # jamais monté
        self.assertEqual((r.returncode, d["deja"], d["actif"]), (0, True, False))

    def test_tout_deconnecter_json(self):
        r, d = self.json("tout-deconnecter", "--json")
        self.assertEqual((r.returncode, d["contrat"], d["ok"], d["action"]), (0, 1, True, "tout-deconnecter"))
        self.assertEqual({c["uuid"] for c in d["coupes"]}, {U2, U3})
        self.assertEqual(d["rates"], [])
        self.assertEqual(set(d["coupes"][0]), {"uuid", "nom"})
        r, d = self.json("tout-deconnecter", "--json")              # plus rien : succès, listes vides
        self.assertEqual((r.returncode, d["coupes"], d["rates"]), (0, [], []))

    def test_erreurs_json_codes_stables(self):
        r, d = self.json("connecter", "pas-un-uuid", "--json")
        self.assertEqual((r.returncode, d["contrat"], d["ok"], d["code"]), (1, 1, False, "uuid_invalide"))
        self.assertIsInstance(d["erreur"], str)
        self.assertEqual(r.stderr, "")
        self.assertEqual(self.appels(), [], "UUID invalide : nmcli n'est pas lancé")
        r, d = self.json("connecter", NOUVEAU, "--json")
        self.assertEqual((r.returncode, d["code"]), (1, "inconnue"))
        r, d = self.json("deconnecter", U4, "--json")                # le Wi-Fi n'est pas un VPN
        self.assertEqual((r.returncode, d["code"]), (1, "inconnue"))
        r, d = self.json("connecter", U1, "--json", NM_ARRETE="1")
        self.assertEqual((r.returncode, d["code"]), (1, "nm_indisponible"))
        r, d = self.json("tout-deconnecter", "--json", NM_ARRETE="1")
        self.assertEqual((r.returncode, d["code"]), (1, "nm_indisponible"))
        r, d = self.json("connecter", U1, "--json", NM_ECHEC_UP="1")
        self.assertEqual((r.returncode, d["code"], d["ok"]), (1, "echec", False))

    def test_sans_json_la_sortie_texte_ne_change_pas(self):
        r = self.vpn("connecter", U1)
        self.assertEqual((r.returncode, r.stdout), (0, "Connecté : Labo\n"))
        r = self.vpn("connecter", U1)
        self.assertEqual(r.stdout, "Déjà connecté : Labo\n")
        r = self.vpn("deconnecter", U1)
        self.assertEqual(r.stdout, "Déconnecté : Labo\n")
        r = self.vpn("connecter", "x")
        self.assertEqual((r.returncode, r.stdout), (1, ""))
        self.assertIn("nc-vpn : ", r.stderr)

    def test_killswitch_json(self):
        r, d = self.json("killswitch", "etat-json")
        self.assertEqual(d["contrat"], 1)
        self.assertEqual(set(d), {"contrat", "installe", "voulu", "actif", "refus", "limites"})
        self.assertIsInstance(d["installe"], bool)
        self.assertIsInstance(d["voulu"], bool)
        self.assertIsInstance(d["limites"], list)
        r, d = self.json("killswitch", "activer", "--json")          # coupé dans les réglages : erreur JSON
        self.assertEqual((r.returncode, d["ok"], d["code"]), (1, False, "killswitch_coupe"))

    def test_aucun_secret_ni_ip_dans_les_champs_du_contrat(self):
        r, d = self.json("etat-json")
        for c in d["connexions"]:
            self.assertNotRegex(c["uuid"], r"[^0-9a-f-]")


class AliasVpn(BaseVpn):
    def paires(self, ancien, nouveau, **plus):
        """Même sortie, même code, mêmes appels nmcli pour la commande d'origine et son alias (états de départ identiques)."""
        resultats = []
        for args in (ancien, nouveau):
            self.setUp()
            r = self.vpn(*args, **plus)
            resultats.append((r.returncode, r.stdout, r.stderr, self.appels(), self.etat_actifs()))
        self.assertEqual(resultats[0], resultats[1], (ancien, nouveau))
        return resultats[0]

    def test_status_json(self):
        r = self.paires(["etat-json"], ["status", "--json"])
        self.assertEqual(json.loads(r[1])["contrat"], 1)

    def test_connect_disconnect(self):
        r = self.paires(["connecter", U1], ["connect", U1])
        self.assertEqual(r[1], "Connecté : Labo\n")
        self.paires(["connecter", U1, "--json"], ["connect", U1, "--json"])
        self.paires(["deconnecter", U2], ["disconnect", U2])
        self.paires(["deconnecter", U2, "--json"], ["disconnect", U2, "--json"])
        self.paires(["connecter", "x", "--json"], ["connect", "x", "--json"])
        self.paires(["connecter", U1], ["connect", U1], NM_ECHEC_UP="1")

    def test_alias_sans_logique_en_double(self):
        # un alias est réécrit en commande d'origine avant tout : une seule table, aucun traitement propre
        from tests._vpn_faux import BIN
        texte = BIN.read_text()
        self.assertEqual(texte.count("def connect("), 0)
        self.assertEqual(texte.count("def disconnect("), 0)
        self.assertIn('ALIAS = {"status": "etat-json", "connect": "connecter", "disconnect": "deconnecter"}', texte)

    def test_alias_formes_refusees(self):
        for args in (["status"], ["status", "--json", "x"], ["connect"], ["disconnect", U1, U2], ["connect", U1, "x"]):
            r = self.vpn(*args)
            self.assertEqual(r.returncode, 2, args)
            self.assertEqual(self.appels(), [], args)


if __name__ == "__main__":
    unittest.main()

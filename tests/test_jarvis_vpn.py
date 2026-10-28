"""JARVIS pilote le VPN du PC (nc_noctalia : actions vpn_*, /nc vpn, cockpit) : liste blanche, UUID strict avant tout appel,
argv exact de nc-vpn (contrat JSON 1, jamais un shell), délai borné, sortie analysée puis reconstruite, mêmes contrôles
d'identité que les autres actions du PC (liste blanche Telegram, confirmation, mode local). Faux nc-vpn qui note ses
arguments : jamais le vrai, jamais nmcli. UUID fictifs."""
import asyncio
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import types
import unittest
from unittest import mock

REPO = Path(__file__).resolve().parents[1]
SERVEUR = REPO / "home/.local/share/nc-jarvis/server"
SOURCE = SERVEUR / "nc_noctalia.py"
U1 = "11111111-1111-4111-8111-111111111111"
U2 = "22222222-2222-4222-8222-222222222222"


def module():
    m = types.ModuleType("nc_noctalia_vpn_test")
    m.__file__ = str(SOURCE)
    exec(compile(SOURCE.read_text(), str(SOURCE), "exec"), m.__dict__)
    return m


def conn(uuid=U1, nom="Labo", active=False):
    return {"uuid": uuid, "nom": nom, "type": "vpn", "active": active, "interface": "tun0" if active else ""}


class Base(unittest.TestCase):
    def setUp(self):
        self.m = module()
        self.m._en_attente.clear()
        self.appels = []
        self.reponse = (0, "{}")

        async def executer(argv, delai=20, limite=3000, fusion=True):
            self.appels.append((list(argv), delai, limite))
            return self.reponse
        self.m.executer = executer
        env = mock.patch.dict(os.environ, DEPLOY_MODE="local")
        env.start()
        self.addCleanup(env.stop)

    def agir(self, action, arguments=(), confirme=True):
        return asyncio.run(self.m.agir(action, list(arguments), confirme=confirme))

    def nc(self, texte, chat=1, maintenant=1000.0):
        return asyncio.run(self.m.commande(texte, chat, maintenant))


class ListeBlanche(Base):
    def test_argv_exact_de_chaque_action(self):
        self.reponse = (0, json.dumps({"contrat": 1, "disponible": True, "connexions": [conn()], "actives": []}))
        self.assertTrue(self.agir("vpn_etat")["success"])
        self.reponse = (0, json.dumps({"contrat": 1, "ok": True, "action": "connecter", "uuid": U1, "nom": "Labo", "actif": True, "deja": False}))
        self.assertTrue(self.agir("vpn_connecter", [U1.upper()])["success"])
        self.reponse = (0, json.dumps({"contrat": 1, "ok": True, "action": "deconnecter", "uuid": U1, "nom": "Labo", "actif": False, "deja": False}))
        self.assertTrue(self.agir("vpn_deconnecter", [U1])["success"])
        self.reponse = (0, json.dumps({"contrat": 1, "ok": True, "action": "tout-deconnecter", "coupes": [], "rates": []}))
        self.assertTrue(self.agir("vpn_tout")["success"])
        self.reponse = (0, json.dumps({"contrat": 1, "installe": True, "voulu": True, "actif": False, "refus": "", "limites": ["a"]}))
        self.assertTrue(self.agir("vpn_killswitch")["success"])
        self.assertEqual([a[0] for a in self.appels], [
            ["nc-vpn", "etat-json"],
            ["nc-vpn", "connecter", U1, "--json"],             # UUID en minuscules
            ["nc-vpn", "deconnecter", U1, "--json"],
            ["nc-vpn", "tout-deconnecter", "--json"],
            ["nc-vpn", "killswitch", "etat-json"]])

    def test_delais_bornes(self):
        self.reponse = (0, json.dumps({"contrat": 1, "disponible": False, "connexions": []}))
        self.agir("vpn_etat")
        self.assertEqual(self.appels[0][1:], (30, self.m.VPN_MAX_SORTIE))
        for a, d in self.m.VPN_DELAIS.items():
            self.assertTrue(0 < d <= 300, a)
        # au-dessus du pire cas de nc-vpn (connecter ~190 s, couper ~75 s) : il finit seul et efface son dossier de mot de passe
        self.assertGreaterEqual(self.m.VPN_DELAIS["vpn_connecter"], 200)
        self.assertGreaterEqual(self.m.VPN_DELAIS["vpn_deconnecter"], 90)
        self.assertEqual((self.m.VPN_DELAIS["vpn_etat"], self.m.VPN_DELAIS["vpn_killswitch"]), (30, 60))

    def test_pas_de_killswitch_activer_ni_desactiver(self):
        for action in ("vpn_killswitch_activer", "vpn_killswitch_desactiver", "vpn_activer", "vpn_importer", "vpn", "vpn_"):
            self.assertIn("Action inconnue", self.agir(action)["output"], action)
        self.assertEqual(self.agir("vpn_killswitch", ["activer"])["success"], False, "pas d'argument sur la lecture")
        for texte in ("vpn killswitch activer", "vpn killswitch desactiver", "vpn importer x.ovpn", "vpn mullvad connecter"):
            self.nc(texte)
        self.assertEqual(self.appels, [], "rien n'est lancé hors de la liste blanche")
        self.assertFalse(any(a[0][1] in ("importer", "mullvad", "ip-publique") for a in self.appels))

    def test_ids_internes_pas_tapables_sur_telegram(self):
        r = self.nc("vpn_tout")
        self.assertIn("Commande inconnue", r)
        self.assertEqual(self.appels, [])

    def test_uuid_invalide_refuse_sans_appel(self):
        for u in ("", "pas-un-uuid", U1[:-1], U1 + "0", "1111111111114111811111111111111111", U1.replace("-", "_"),
                  "g" + U1[1:], U1 + " --killswitch", "../" + U1, "$(id)", "-" + U1[1:]):
            for action in ("vpn_connecter", "vpn_deconnecter"):
                r = self.agir(action, [u] if u else [])
                self.assertFalse(r["success"], (action, u))
                self.assertIn("UUID", r["output"])
        self.assertFalse(self.agir("vpn_connecter", [U1, U2])["success"], "un seul UUID")
        self.assertFalse(self.agir("vpn_tout", [U1])["success"])
        self.assertFalse(self.agir("vpn_etat", ["--json"])["success"])
        self.assertEqual(self.appels, [], "rien n'est lancé")

    def test_mode_serveur_ne_pilote_pas_le_bureau(self):
        with mock.patch.dict(os.environ, DEPLOY_MODE="server"):
            r = self.agir("vpn_etat")
        self.assertFalse(r["success"])
        self.assertEqual(self.appels, [])


class Confirmation(Base):
    def setUp(self):
        super().setUp()
        self.reponse = (0, json.dumps({"contrat": 1, "ok": True, "action": "connecter", "uuid": U1, "nom": "Labo", "actif": True, "deja": False}))

    def test_connecter_demande_oui_sur_telegram(self):
        r = self.nc("vpn connecter " + U1, chat=7)
        self.assertTrue(r.startswith("⚠️"), r)
        self.assertEqual(self.appels, [], "rien avant la confirmation")
        self.assertIn("Rien à confirmer", self.nc("oui", chat=8, maintenant=1001), "un autre chat ne confirme pas")
        self.assertIn("Rien à confirmer", self.nc("oui", chat=7, maintenant=1000 + 121))
        self.nc("vpn connecter " + U1, chat=7, maintenant=2000)
        r = self.nc("oui", chat=7, maintenant=2010)
        self.assertTrue(r.startswith("✅"), r)
        self.assertEqual(self.appels[-1][0], ["nc-vpn", "connecter", U1, "--json"])

    def test_deconnecter_et_tout_demandent_oui(self):
        for texte in ("vpn deconnecter " + U1, "vpn tout"):
            self.assertTrue(self.nc(texte).startswith("⚠️"), texte)
        self.assertEqual(self.appels, [])

    def test_lecture_sans_confirmation(self):
        self.reponse = (0, json.dumps({"contrat": 1, "disponible": True, "connexions": [conn()], "actives": []}))
        self.assertTrue(self.nc("vpn").startswith("✅"))
        self.reponse = (0, json.dumps({"contrat": 1, "installe": False, "voulu": False, "actif": None, "refus": "x", "limites": []}))
        self.assertTrue(self.nc("vpn killswitch").startswith("✅"))
        self.assertEqual([a[0] for a in self.appels], [["nc-vpn", "etat-json"], ["nc-vpn", "killswitch", "etat-json"]])

    def test_agir_sans_confirmation_refuse(self):
        r = self.agir("vpn_deconnecter", [U1], confirme=False)
        self.assertTrue(r.get("confirm"))
        self.assertEqual(self.appels, [])


class Identite(Base):
    """Même contrôle que les autres actions /nc : liste blanche du bot Telegram ; le cockpit passe par le gateway (SECRET_KEY)
    puis /api/nc/manage, qui exige `confirmed` pour tout ce qui n'est pas en lecture seule."""
    def test_telegram_utilisateur_refuse(self):
        reponses = []

        class Message:
            async def reply_text(self, texte):
                reponses.append(texte)
        update = types.SimpleNamespace(effective_user=types.SimpleNamespace(id=42), effective_chat=types.SimpleNamespace(id=42), message=Message())
        tb = types.SimpleNamespace(_is_allowed=lambda uid: uid == 42)
        handler = self.m.handler(tb)
        self.reponse = (0, json.dumps({"contrat": 1, "disponible": True, "connexions": [], "actives": []}))
        asyncio.run(handler(update, types.SimpleNamespace(args=["vpn"])))
        self.assertTrue(reponses[-1].startswith("✅"))
        n = len(self.appels)
        update.effective_user.id = 43
        for args in (["vpn"], ["vpn", "tout"], ["vpn", "connecter", U1], ["oui"]):
            asyncio.run(handler(update, types.SimpleNamespace(args=args)))
            self.assertEqual(reponses[-1], "⛔ Accès non autorisé.", args)
        self.assertEqual(len(self.appels), n, "utilisateur refusé : nc-vpn n'est pas lancé")

    def test_cockpit_exige_la_confirmation(self):
        sys.path.insert(0, str(SERVEUR))
        self.addCleanup(sys.path.remove, str(SERVEUR))
        for n in ("nc_noctalia", "nc_management"):
            sys.modules.pop(n, None)
            self.addCleanup(sys.modules.pop, n, None)
        import nc_noctalia
        import nc_management
        appels = []

        async def executer(argv, delai=20, limite=3000, fusion=True):
            appels.append(list(argv))
            return 0, json.dumps({"contrat": 1, "ok": True, "action": "deconnecter", "uuid": U1, "nom": "Labo", "actif": False, "deja": False})
        nc_noctalia.executer = executer

        def manage(action, params, confirmed):
            return asyncio.run(nc_management.dispatch("noctalia", {"action": action, "params": params}, confirmed))
        self.assertEqual(manage("vpn_deconnecter", {"uuid": U1}, False), {"error": "Confirmation explicite requise"})
        self.assertEqual(manage("vpn_tout", {}, False), {"error": "Confirmation explicite requise"})
        self.assertEqual(appels, [])
        self.assertTrue(manage("vpn_deconnecter", {"uuid": U1}, True)["success"])
        self.assertEqual(appels[-1], ["nc-vpn", "deconnecter", U1, "--json"])
        with self.assertRaises(ValueError):
            manage("vpn_killswitch_desactiver", {}, True)
        self.assertEqual(len(appels), 1)


class Sortie(Base):
    def lire(self, action, code, sortie, uuid=None):
        return self.m.vpn_valider(action, code, sortie, uuid)

    def test_sortie_invalide_refusee(self):
        for s in ("", "pas du json", "[]", "null", "{}", '{"contrat": 2}', '{"contrat": true}', '{"contrat": 1}', "[" * 100000):
            ok, texte = self.lire("vpn_etat", 0, s)
            self.assertFalse(ok, s[:20])
            self.assertIn("invalide", texte)
        self.assertFalse(self.lire("vpn_etat", 1, '{"contrat": 1, "disponible": true, "connexions": []}')[0], "code de sortie non nul")
        bonne = {"contrat": 1, "ok": True, "action": "connecter", "uuid": U1, "nom": "Labo", "actif": True, "deja": False}
        self.assertEqual(self.lire("vpn_connecter", 0, json.dumps(bonne), U1), (True, "Connecté : Labo"))
        for tordu in (dict(bonne, uuid=U2), dict(bonne, action="deconnecter"), dict(bonne, actif=False), dict(bonne, deja="non"),
                      dict(bonne, ok=False), dict(bonne, uuid="x"), dict(bonne, nom=5)):
            self.assertFalse(self.lire("vpn_connecter", 0, json.dumps(tordu), U1)[0], tordu)
        self.assertFalse(self.lire("vpn_connecter", 1, json.dumps(bonne), U1)[0], "ok vrai mais code non nul")

    def test_texte_seulement_champs_inconnus_jetes(self):
        brut = {"contrat": 1, "disponible": True, "secret": "S3CRET", "ip": "203.0.113.9",
                "connexions": [dict(conn(), mot_de_passe="hunter2", ip="203.0.113.9")], "actives": []}
        ok, texte = self.lire("vpn_etat", 0, json.dumps(brut))
        self.assertTrue(ok)
        for interdit in ("S3CRET", "hunter2", "203.0.113.9", "{", "}"):
            self.assertNotIn(interdit, texte)
        self.assertIn(U1, texte)
        self.assertIn("Labo", texte)

    def test_sortie_bornee(self):
        grosse = {"contrat": 1, "disponible": True, "connexions": [conn(nom="N" * 5000 + "\x1b[31m\n")] * 64, "actives": []}
        ok, texte = self.lire("vpn_etat", 0, json.dumps(grosse))
        self.assertTrue(ok)
        self.assertNotIn("N" * 81, texte)
        self.assertNotIn("\x1b", texte)
        self.assertLessEqual(len(texte), 20 * 200 + 200)
        self.assertIn("et 44 autre(s)", texte)
        trop = dict(grosse, connexions=[conn()] * 300)
        self.assertFalse(self.lire("vpn_etat", 0, json.dumps(trop))[0], "plus de 256 connexions : refusé")

    def test_nm_indisponible(self):
        for corps in ({"contrat": 1, "disponible": False, "connexions": [], "actives": []}, {"contrat": 1, "disponible": False}):
            self.assertEqual(self.lire("vpn_etat", 0, json.dumps(corps)), (False, "NetworkManager n'est pas disponible."))

    def test_erreur_de_nc_vpn_texte_maison(self):
        err = {"contrat": 1, "ok": False, "code": "inconnue", "erreur": "texte libre avec 203.0.113.9 et mot de passe"}
        ok, texte = self.lire("vpn_connecter", 1, json.dumps(err), U1)
        self.assertFalse(ok)
        self.assertNotIn("203.0.113.9", texte)
        self.assertIn("NetworkManager", texte)
        ok, texte = self.lire("vpn_connecter", 1, json.dumps(dict(err, code="n'importe quoi")), U1)
        self.assertFalse(ok)
        self.assertIn("a échoué", texte)
        self.assertIn("réessaie", self.lire("vpn_connecter", 1, json.dumps(dict(err, code="occupe")), U1)[1])

    def test_killswitch_ni_refus_ni_limites_relayes(self):
        """Le refus de nc-vpn peut nommer le serveur : jamais relayé (ni `refus`, ni `limites`)."""
        brut = {"contrat": 1, "installe": True, "voulu": True, "actif": False, "refus_code": "serveur_nom",
                "refus": "L'adresse du serveur est un nom (vpn.example.org)", "limites": ["vpn.example.org et 203.0.113.9"]}
        ok, texte = self.lire("vpn_killswitch", 0, json.dumps(brut))
        self.assertTrue(ok)
        self.assertNotIn("vpn.example.org", texte)
        self.assertNotIn("203.0.113.9", texte)
        self.assertIn("un nom, pas une adresse IP", texte)
        self.assertIn("redémarrage", texte)                        # limites : texte fixe de JARVIS
        # un code inconnu devient « autre » ; sans refus_code (ancien nc-vpn) : pas de raison affichée
        self.assertIn("raison non précisée", self.lire("vpn_killswitch", 0, json.dumps(dict(brut, refus_code="x<script>")))[1])
        sans = {k: v for k, v in brut.items() if k != "refus_code"}
        self.assertNotIn("Impossible", self.lire("vpn_killswitch", 0, json.dumps(sans))[1])
        for mauvais in (dict(brut, actif="oui"), dict(brut, refus_code=5), dict(brut, installe=1)):
            self.assertFalse(self.lire("vpn_killswitch", 0, json.dumps(mauvais))[0], mauvais)
        for code in self.m.VPN_REFUS:
            self.assertTrue(self.lire("vpn_killswitch", 0, json.dumps(dict(brut, refus_code=code)))[0])

    def test_tout_partiel(self):
        err = {"contrat": 1, "ok": False, "code": "echec_partiel", "coupes": [{"uuid": U1, "nom": "A"}], "rates": [{"uuid": U2, "nom": "B"}]}
        ok, texte = self.lire("vpn_tout", 1, json.dumps(err))
        self.assertFalse(ok)
        self.assertIn("Restent montés : B", texte)


class ExecutionReelle(unittest.TestCase):
    """Le vrai executer devant un faux nc-vpn : arguments tels quels (pas de shell), délai, sortie."""
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="nc-jv-")
        self.addCleanup(self.tmp.cleanup)
        self.bin = Path(self.tmp.name)
        faux = self.bin / "nc-vpn"
        faux.write_text('#!/usr/bin/env python3\nimport json, os, sys, time\n'
                        'open(os.environ["FAUX_JOURNAL"], "a").write(json.dumps(sys.argv[1:]) + "\\n")\n'
                        'import signal\n'
                        'def fin(n, c):\n'
                        '    open(os.environ["FAUX_JOURNAL"] + ".term", "w").write("propre")\n'
                        '    sys.exit(1)\n'
                        'if os.environ.get("FAUX_TERM") == "ignore": signal.signal(signal.SIGTERM, signal.SIG_IGN)\n'
                        'elif os.environ.get("FAUX_TERM"): signal.signal(signal.SIGTERM, fin)\n'
                        'if os.environ.get("FAUX_ERR"): sys.stderr.write(os.environ["FAUX_ERR"] + "\\n")\n'
                        'if os.environ.get("FAUX_LENT"): time.sleep(30)\n'
                        'print(os.environ.get("FAUX_SORTIE", "{}"))\n')
        faux.chmod(0o755)
        self.journal = self.bin / "journal"
        env = mock.patch.dict(os.environ, DEPLOY_MODE="local", FAUX_JOURNAL=str(self.journal))
        env.start()
        self.addCleanup(env.stop)
        self.m = module()
        self.m.BIN = self.bin

    def test_argv_sans_shell_et_sortie_validee(self):
        sortie = json.dumps({"contrat": 1, "ok": True, "action": "connecter", "uuid": U1, "nom": "Labo", "actif": True, "deja": False})
        with mock.patch.dict(os.environ, FAUX_SORTIE=sortie):
            r = asyncio.run(self.m.agir("vpn_connecter", [U1], confirme=True))
        self.assertTrue(r["success"], r)
        self.assertEqual(r["output"], "Connecté : Labo")
        self.assertEqual(json.loads(self.journal.read_text()), ["connecter", U1, "--json"])
        r = asyncio.run(self.m.agir("vpn_connecter", [U1 + "; id"], confirme=True))
        self.assertFalse(r["success"])
        self.assertEqual(len(self.journal.read_text().splitlines()), 1, "UUID invalide : le faux nc-vpn n'est pas appelé")

    def test_delai_depasse(self):
        self.m.VPN_DELAIS["vpn_etat"] = 0.3
        with mock.patch.dict(os.environ, FAUX_LENT="1"):
            r = asyncio.run(self.m.agir("vpn_etat", [], confirme=True))
        self.assertEqual((r["success"], r["output"]), (False, "Délai dépassé"))

    def test_delai_sigterm_d_abord_au_groupe(self):
        """Au délai : SIGTERM (nc-vpn peut effacer son dossier de mot de passe), jamais SIGKILL en premier."""
        self.m.VPN_DELAIS["vpn_etat"] = 0.5
        with mock.patch.dict(os.environ, FAUX_LENT="1", FAUX_TERM="propre"):
            r = asyncio.run(self.m.agir("vpn_etat", [], confirme=True))
        self.assertEqual(r["output"], "Délai dépassé")
        self.assertEqual(Path(str(self.journal) + ".term").read_text(), "propre")

    def test_delai_sigkill_si_sigterm_ignore(self):
        self.m.VPN_DELAIS["vpn_etat"] = 0.3
        self.m.GRACE_ARRET = 0.3
        with mock.patch.dict(os.environ, FAUX_LENT="1", FAUX_TERM="ignore"):
            debut = time.monotonic()
            r = asyncio.run(self.m.agir("vpn_etat", [], confirme=True))
        self.assertEqual(r["output"], "Délai dépassé")
        self.assertLess(time.monotonic() - debut, 5)

    def test_stderr_separe_et_jamais_relaye(self):
        sortie = json.dumps({"contrat": 1, "disponible": True, "connexions": [conn()], "actives": []})
        with mock.patch.dict(os.environ, FAUX_SORTIE=sortie, FAUX_ERR="ERREUR-SECRETE 203.0.113.9"):
            r = asyncio.run(self.m.agir("vpn_etat", [], confirme=True))
        self.assertTrue(r["success"], r)
        self.assertNotIn("SECRETE", r["output"])

    def test_sortie_geante_bornee_en_octets(self):
        m = self.m
        m.VPN_MAX_SORTIE = 1000
        with mock.patch.dict(os.environ, FAUX_SORTIE="x" * 100000):
            r = asyncio.run(m.agir("vpn_etat", [], confirme=True))
        self.assertFalse(r["success"])
        self.assertIn("invalide", r["output"])

    def test_sortie_non_json_refusee(self):
        with mock.patch.dict(os.environ, FAUX_SORTIE="usage: nc-vpn ..."):
            r = asyncio.run(self.m.agir("vpn_etat", [], confirme=True))
        self.assertFalse(r["success"])
        self.assertIn("invalide", r["output"])


class Catalogue(unittest.TestCase):
    def test_actions_json_suit_la_table(self):
        m = module()
        cat = {a["id"]: a for a in json.loads((REPO / "home/.local/share/nc-jarvis/actions.json").read_text())["noctalia"]}
        for ident, a in m.ACTIONS.items():
            self.assertIn(ident, cat)
            self.assertEqual(cat[ident]["readonly"], a["readonly"], ident)
            self.assertEqual([f["key"] for f in cat[ident]["fields"]], [f["key"] for f in a["fields"]], ident)
        for ident in ("vpn_connecter", "vpn_deconnecter", "vpn_tout"):
            self.assertFalse(m.ACTIONS[ident]["readonly"])
            self.assertTrue(m.ACTIONS[ident]["sensible"])
        self.assertFalse([i for i in m.ACTIONS if "killswitch" in i and i != "vpn_killswitch"])
        self.assertTrue(m.ACTIONS["vpn_killswitch"]["readonly"])


if __name__ == "__main__":
    unittest.main()

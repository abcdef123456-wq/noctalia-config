"""Suivre et répondre aux agents de code depuis Telegram (nc_agents : /agents, /repondre, /code) : conversation privée et
utilisateur autorisé seulement, messages modifiés ignorés, numéros courts liés aux sessions réelles, noms de dossiers, filtre de
secrets, texte borné et sans caractère de contrôle, confirmation par le code de nc-noeud (usage unique), argv exact de
nc-claude ecrire, journal sans le texte, mode serveur et réglage à non. Faux nc-claude et faux nc-noeud qui notent leurs
arguments : jamais les vrais, jamais un vrai bot. HOME isolé, jetons évidemment faux."""
import asyncio
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import types
import unittest
from unittest import mock

REPO = Path(__file__).resolve().parents[1]
SOURCE = REPO / "home/.local/share/nc-jarvis/server/nc_agents.py"
NC_CLAUDE = REPO / "home/.local/bin/nc-claude"
S_CLAUDE = "11111111-1111-4111-8111-111111111111"
S_CODEX = "codex-22222222-2222-4222-8222-222222222222"
S_OMP = "omp-33333333"
S_OPENCODE = "opencode-ses_44444444"
S_SANS = "gemini-55555555"
CODE_BON = "123456"
CODE_BON2 = "654321"


def module():
    m = types.ModuleType("nc_agents_test")
    m.__file__ = str(SOURCE)
    exec(compile(SOURCE.read_text(), str(SOURCE), "exec"), m.__dict__)
    return m


def session(sid, agent, dossier, etat, ecrire=True, message=None):
    x = {"id": sid, "agent": agent, "dossier": dossier, "etat": etat, "ecrire": ecrire}
    if message is not None:
        x["message"] = message
    return x


SESSIONS = [
    session(S_CLAUDE, "claude", "mon-projet", "terminal", message="Fini : tests verts."),
    session(S_CODEX, "codex", "/home/user/projets/outil", "travail", message="ancien message"),
    session(S_OMP, "omp", "site", "fini", message="Voilà."),
    session(S_OPENCODE, "opencode", "docs", "attente"),
    session(S_SANS, "gemini", "autre", "fini", ecrire=False),
]


class Base(unittest.TestCase):
    def setUp(self):
        d = tempfile.TemporaryDirectory(prefix="nc-ag-")
        self.addCleanup(d.cleanup)
        self.home = Path(d.name)
        (self.home / ".config/nc").mkdir(parents=True)
        env = mock.patch.dict(os.environ, HOME=str(self.home), DEPLOY_MODE="local", NC_LANGUE="fr")
        env.start()
        self.addCleanup(env.stop)
        self.regler(TELEGRAM_AGENTS="oui")
        self.m = module()
        self.appels = []                       # (argv, délai, limite, fusion, entree)
        self.sessions = [dict(s) for s in SESSIONS]
        self.pret = 0                          # sortie de « nc-noeud totp pret »
        self.valides = {CODE_BON, CODE_BON2}
        self.servis = set()
        self.ecrire_code = 0
        self.etat_code = 0

        async def executer(argv, delai=20, limite=3000, fusion=True, entree=None):
            self.appels.append((list(argv), delai, limite, fusion, entree))
            if argv[:3] == ["nc-claude", "etat", "--json"]:
                avec = "--texte" in argv
                brut = [dict(s) for s in self.sessions]
                if not avec:
                    for s in brut:
                        s.pop("message", None)
                return self.etat_code, json.dumps({"contrat": 1, "sessions": brut})
            if argv[:3] == ["nc-noeud", "totp", "pret"]:
                return self.pret, ""
            if argv[:3] == ["nc-noeud", "totp", "controler"]:
                code = entree.decode().strip()
                if code in self.servis:
                    return 1, ""
                if code in self.valides:
                    self.servis.add(code)
                    return 0, ""
                return 1, ""
            if argv[:2] == ["nc-claude", "ecrire"]:
                return self.ecrire_code, "sortie libre de nc-claude qui ne doit jamais être relayée"
            return 127, ""
        self.m.executer = executer

    def regler(self, **vals):
        (self.home / ".config/nc/reglages.conf").write_text("".join("%s=%s\n" % kv for kv in vals.items()))

    def lancer(self, texte, user=42, chat=7, type="private", t=1000.0, modifie=False, autorises=(42,)):
        """Le handler Telegram de la commande dans `texte`, avec un faux message ; renvoie les réponses."""
        reponses = []

        class Message:
            def __init__(self):
                self.text = texte
                self.date = types.SimpleNamespace(timestamp=lambda: t)

            async def reply_text(self, r):
                reponses.append(r)
        message = Message()
        update = types.SimpleNamespace(effective_user=types.SimpleNamespace(id=user),
                                       effective_chat=types.SimpleNamespace(id=chat, type=type),
                                       message=None if modifie else message, edited_message=message if modifie else None)
        tb = types.SimpleNamespace(_is_allowed=lambda uid: uid in autorises)
        nom = texte.split()[0][1:].split("@")[0].lower()
        commande = {"agents": self.m.cmd_agents, "claude": self.m.cmd_agents, "repondre": self.m.cmd_repondre,
                    "code": self.m.cmd_code}[nom]
        asyncio.run(self.m.handler(tb, commande)(update, types.SimpleNamespace(args=texte.split()[1:])))
        return reponses

    def un(self, texte, **kw):
        r = self.lancer(texte, **kw)
        self.assertEqual(len(r), 1, r)
        return r[0]

    def commandes_ecrire(self):
        return [a[0] for a in self.appels if a[0][:2] == ["nc-claude", "ecrire"]]

    def demander(self, texte="vas-y", numero="1", t=1000.0, **kw):
        """/agents puis /repondre : la demande attend son code."""
        self.un("/agents", t=t, **kw)
        return self.un("/repondre %s %s" % (numero, texte), t=t + 1, **kw)


class Acces(Base):
    def test_serveur_la_fonction_est_absente_et_le_dit(self):
        with mock.patch.dict(os.environ, DEPLOY_MODE="server"):
            for c in ("/agents", "/repondre 1 salut", "/code 123456"):
                r = self.un(c)
                self.assertIn("absente en mode serveur", r, c)
        self.assertEqual(self.appels, [])

    def test_reglage_non_rien_ne_se_passe(self):
        for avant in ({}, {"TELEGRAM_AGENTS": "non"}):
            self.regler(**avant)
            for c in ("/agents", "/repondre 1 salut", "/code 123456"):
                self.assertIn("Désactivé", self.un(c), c)
        self.regler(TELEGRAM_AGENTS="oui", IA_MODE="non")
        self.assertIn("IA_MODE=non", self.un("/agents"))
        self.assertEqual(self.appels, [], "aucune commande lancée")

    def test_utilisateur_non_autorise(self):
        for c in ("/agents", "/repondre 1 salut", "/code 123456"):
            self.assertEqual(self.un(c, user=99), "⛔ Accès non autorisé.")
        self.assertEqual(self.appels, [])

    def test_groupe_refuse(self):
        for c in ("/agents", "/repondre 1 salut", "/code 123456"):
            self.assertTrue(self.un(c, type="supergroup").startswith("⛔"), c)
            self.assertTrue(self.un(c, type=None).startswith("⛔"), c)
        self.assertEqual(self.appels, [])

    def test_message_modifie_ne_fait_rien(self):
        self.demander()
        avant = len(self.appels)
        for c in ("/agents", "/repondre 1 autre", "/code %s" % CODE_BON):
            self.assertEqual(self.lancer(c, modifie=True), [])
        self.assertEqual(len(self.appels), avant)
        self.assertEqual(self.commandes_ecrire(), [])

    def test_alias_claude_et_nom_du_bot(self):
        self.assertIn("Agents de code (5)", self.un("/claude"))
        self.assertIn("Agents de code (5)", self.un("/agents@mon_bot"))


class Liste(Base):
    def test_liste_sans_contenu_par_defaut(self):
        r = self.un("/agents")
        self.assertEqual([a[0] for a in self.appels], [["nc-claude", "etat", "--json"]], "argv exact, sans --texte")
        self.assertEqual((self.appels[0][1], self.appels[0][3]), (self.m.DELAI_ETAT, False), "délai borné, stderr à part")
        self.assertIn("1. Claude Code · mon-projet · t'attend", r)
        self.assertIn("2. Codex · outil · travaille", r)
        self.assertIn("3. omp · site · fini", r)
        self.assertIn("4. OpenCode · docs · t'attend", r)
        self.assertIn("5. Gemini CLI · autre · fini\n   ↳ réponse impossible à distance (terminal non pris en charge)", r)
        self.assertNotIn("/home", r, "jamais le chemin, seulement le nom du dossier")
        for contenu in ("tests verts", "Voilà", "ancien message"):
            self.assertNotIn(contenu, r)

    def test_texte_seulement_si_reglage(self):
        self.regler(TELEGRAM_AGENTS="oui", TELEGRAM_AGENTS_TEXTE="oui")
        r = self.un("/agents")
        self.assertEqual(self.appels[0][0], ["nc-claude", "etat", "--json", "--texte"])
        self.assertIn("« Fini : tests verts. »", r)
        self.assertIn("« Voilà. »", r)

    def test_texte_filtre_et_borne(self):
        self.regler(TELEGRAM_AGENTS="oui", TELEGRAM_AGENTS_TEXTE="oui")
        self.sessions[0]["message"] = "mot " * 200 + "fin"
        self.sessions[3]["message"] = "a\u202eb\u200bc  d\x1b[31m"
        r = self.un("/agents")
        ligne = next(l for l in r.splitlines() if l.startswith("   « mot"))
        self.assertTrue(ligne.endswith("… »"), ligne)
        self.assertEqual(len(ligne), len("   « ") + 600 + len(" »"), "600 signes, « … » compris")
        self.assertIn("« abc d[31m »", r, "bidi, invisibles et ESC retirés")
        self.assertNotIn("\u202e", r)
        self.assertNotIn("\x1b", r)

    def test_dossier_borne_a_40_et_texte_brut(self):
        self.sessions[0]["dossier"] = "/home/user/" + "d" * 10 + "é" * 60
        self.sessions[1]["dossier"] = "*gras* _it_ `code`‮"
        r = self.un("/agents")
        self.assertIn("1. Claude Code · " + "d" * 10 + "é" * 29 + "… ·", r)
        self.assertIn("*gras* _it_ `code`", r)
        self.assertNotIn("‮", r)

    def test_aucune_session(self):
        self.sessions = []
        self.assertIn("Aucun agent de code suivi", self.un("/agents"))

    def test_sortie_invalide(self):
        for mauvais in ("pas du json", "[]", json.dumps({"contrat": 2, "sessions": []}), json.dumps({"contrat": True, "sessions": []}),
                        json.dumps({"contrat": 1, "sessions": "x"})):
            async def executer(argv, delai=20, limite=3000, fusion=True, entree=None, mauvais=mauvais):
                return 0, mauvais
            self.m.executer = executer
            self.assertIn("nc-claude ne répond pas", self.un("/agents"), mauvais)
        self.etat_code = 1
        self.setUp()
        self.etat_code = 1
        self.assertIn("nc-claude ne répond pas", self.un("/agents"))

    def test_session_invalide_ignoree(self):
        self.sessions = [session("../../x", "claude", "a", "fini"), session("a b", "claude", "a", "fini"),
                         session("-option", "claude", "a", "fini"), session("ok-1", "claude", "b", "fini"),
                         {"id": "ok-2", "agent": 5, "dossier": "c", "etat": "fini", "ecrire": True},
                         session("ok-3", "claude", "d", "fini", ecrire="oui")]
        r = self.un("/agents")
        self.assertIn("1. Claude Code · b · fini", r)
        self.assertIn("2. Claude Code · d · fini\n   ↳ réponse impossible", r, "ecrire doit être exactement vrai")
        self.assertNotIn("../", r)

    def test_numeros_stables_dix_minutes_puis_repart(self):
        self.un("/agents", t=1000)
        self.sessions = [self.sessions[2], self.sessions[0], session("claude-nouvelle", "claude", "nouveau", "fini")]
        r = self.un("/agents", t=1000 + 599)
        self.assertIn("1. Claude Code · mon-projet", r)
        self.assertIn("3. omp · site", r)
        self.assertIn("2. Claude Code · nouveau", r, "le numéro 2 (une session disparue) est repris par la nouvelle")
        r = self.un("/agents", t=1000 + 599 + 601)
        self.assertLess(r.index("1. omp · site"), r.index("2. Claude Code · mon-projet"), "plus de 10 min : repart de 1")

    def test_numeros_par_discussion_et_utilisateur(self):
        self.un("/agents", user=42, chat=7)
        self.sessions = self.sessions[2:]
        r = self.un("/agents", user=43, chat=8, autorises=(42, 43))
        self.assertIn("1. omp · site", r)


class Reponse(Base):
    def test_demande_puis_code_envoie_l_argv_exact(self):
        r = self.demander("Fais les tests, merci")
        self.assertIn("Claude Code (mon-projet)", r)
        self.assertIn("« Fais les tests, merci »", r)
        self.assertIn("/code 123456", r)
        self.assertNotIn("attention : tu autorises", r)
        self.assertEqual(self.commandes_ecrire(), [], "rien ne part avant le code")
        self.assertIn(["nc-noeud", "totp", "pret"], [a[0] for a in self.appels])
        r = self.un("/code " + CODE_BON, t=1030)
        self.assertEqual(r, "✅ Envoyé à Claude Code (mon-projet).")
        self.assertEqual(self.commandes_ecrire(), [["nc-claude", "ecrire", S_CLAUDE, "Fais les tests, merci"]])
        ecr = next(a for a in self.appels if a[0][:2] == ["nc-claude", "ecrire"])
        self.assertEqual((ecr[1], ecr[3]), (self.m.DELAI_ECRIRE, False), "délai borné")
        self.assertNotIn("sortie libre", r, "aucune sortie libre relayée")

    def test_le_code_passe_par_l_entree_standard(self):
        self.demander()
        self.un("/code " + CODE_BON, t=1030)
        c = next(a for a in self.appels if a[0][:3] == ["nc-noeud", "totp", "controler"])
        self.assertEqual(c[0], ["nc-noeud", "totp", "controler"], "pas de code dans la ligne de commande")
        self.assertEqual(c[4], (CODE_BON + "\n").encode())
        self.assertEqual(c[1], self.m.DELAI_CODE)

    def test_sans_totp_refuse_avec_le_moyen_de_l_activer(self):
        self.pret = 3
        self.un("/agents")
        r = self.un("/repondre 1 salut", t=1001)
        self.assertIn("nc-noeud totp creer", r)
        self.assertIn("nc-noeud totp verifier", r)
        self.assertEqual(self.un("/code " + CODE_BON, t=1002).split(" :")[0], "Rien à confirmer (ou plus de deux minutes ont passé)")
        self.assertEqual(self.commandes_ecrire(), [])
        self.pret = 4
        self.assertIn("bloqué", self.un("/repondre 1 salut", t=1003))

    def test_mauvais_code(self):
        self.demander()
        r = self.un("/code 000000", t=1030)
        self.assertTrue(r.startswith("❌ Code refusé"), r)
        self.assertEqual(self.commandes_ecrire(), [])
        self.assertIn("Rien à confirmer", self.un("/code " + CODE_BON, t=1031), "la demande est consommée par un essai")

    def test_forme_du_code(self):
        self.demander()
        avant = len(self.appels)
        for mauvais in ("/code", "/code 12345", "/code 1234567", "/code 12 34 56", "/code abcdef", "/code 123456;ls"):
            self.assertIn("6 chiffres", self.un(mauvais, t=1030), mauvais)
        self.assertEqual(len(self.appels), avant, "nc-noeud n'est pas appelé, la demande reste")
        self.assertTrue(self.un("/code " + CODE_BON, t=1031).startswith("✅"))

    def test_code_rejoue(self):
        self.demander()
        self.assertTrue(self.un("/code " + CODE_BON, t=1030).startswith("✅"))
        self.assertIn("Rien à confirmer", self.un("/code " + CODE_BON, t=1031))
        self.demander("encore", t=1100)
        r = self.un("/code " + CODE_BON, t=1130)                    # nc-noeud le refuse : déjà servi
        self.assertTrue(r.startswith("❌ Code refusé"), r)
        self.assertEqual(len(self.commandes_ecrire()), 1)

    def test_apres_120_secondes(self):
        self.demander(t=1000)
        r = self.un("/code " + CODE_BON, t=1001 + 120.5)
        self.assertIn("Rien à confirmer", r)
        self.assertEqual(self.commandes_ecrire(), [])
        self.demander(t=2000)
        self.assertTrue(self.un("/code " + CODE_BON2, t=2001 + 119).startswith("✅"), "dans les 120 s")

    def test_numero_inconnu_ou_expire(self):
        self.assertIn("tape /agents", self.un("/repondre 1 salut"), "pas encore de liste")
        self.un("/agents", t=1000)
        self.assertIn("Numéro inconnu", self.un("/repondre 9 salut", t=1001))
        self.assertIn("Usage", self.un("/repondre x salut", t=1001))
        self.assertIn("Usage", self.un("/repondre 1", t=1001))
        self.assertIn("Usage", self.un("/repondre 0001234 salut", t=1001))
        self.assertIn("plus de 10 minutes", self.un("/repondre 1 salut", t=1000 + 601))
        self.assertEqual(self.commandes_ecrire(), [])

    def test_session_sans_ecrire(self):
        self.un("/agents")
        r = self.un("/repondre 5 salut", t=1001)
        self.assertIn("réponse impossible à distance (terminal non pris en charge)", r)
        self.assertNotIn("Confirme", r)

    def test_session_disparue_avant_l_envoi(self):
        self.demander()
        self.sessions = self.sessions[1:]
        r = self.un("/code " + CODE_BON, t=1030)
        self.assertIn("n'est plus là", r)
        self.assertEqual(self.commandes_ecrire(), [])

    def test_session_qui_n_accepte_plus_l_ecriture(self):
        self.demander()
        self.sessions[0]["ecrire"] = False
        self.assertIn("n'est plus là", self.un("/code " + CODE_BON, t=1030))
        self.assertEqual(self.commandes_ecrire(), [])

    def test_echec_de_l_envoi(self):
        self.ecrire_code = 1
        self.demander()
        r = self.un("/code " + CODE_BON, t=1030)
        self.assertTrue(r.startswith("❌ Échec de l'envoi"), r)
        self.assertNotIn("sortie libre", r)

    def test_une_demande_par_utilisateur_et_la_derniere_remplace(self):
        self.demander("premier")
        r = self.un("/repondre 4 second", t=1010)
        self.assertIn("est remplacée", r)
        self.un("/code " + CODE_BON, t=1020)
        self.assertEqual(self.commandes_ecrire(), [["nc-claude", "ecrire", S_OPENCODE, "second"]])

    def test_un_autre_utilisateur_ne_confirme_pas(self):
        autorises = (42, 43)
        self.demander(autorises=autorises)
        self.assertIn("Rien à confirmer", self.un("/code " + CODE_BON, t=1030, user=43, autorises=autorises))
        self.assertIn("Rien à confirmer", self.un("/code " + CODE_BON, t=1031, user=42, chat=8, autorises=autorises))
        self.assertEqual(self.commandes_ecrire(), [])
        self.assertTrue(self.un("/code " + CODE_BON, t=1032, autorises=autorises).startswith("✅"))

    def test_une_demande_faite_en_prive_ne_se_confirme_pas_en_groupe(self):
        self.demander()
        self.assertTrue(self.un("/code " + CODE_BON, t=1030, type="group").startswith("⛔"))
        self.assertEqual(self.commandes_ecrire(), [])

    def test_avertissement_quand_le_texte_ressemble_a_une_autorisation(self):
        for texte in ("1", "2", "3", "y", "yes", "Oui", "o", "n", "no", "non", "a", "always", "Toujours", "y.", "7"):
            r = self.demander(texte)
            self.assertIn("attention : tu autorises peut-être une commande de l'agent", r, texte)
        for texte in ("oui merci", "ok", "yes please", "12", "lance 1"):
            self.assertNotIn("attention : tu autorises", self.demander(texte), texte)

    def test_avertissement_texte_commencant_par_barre(self):
        self.assertIn("commence par /", self.demander("/clear"))

    def test_etat_travaille_signale(self):
        self.assertIn("pas « t'attend »", self.demander(numero="2"))


class TexteRefuse(Base):
    def refuse(self, texte, mot=None):
        self.un("/agents", t=1000)
        avant = len(self.appels)
        r = self.lancer("/repondre 1 " + texte, t=1001)
        self.assertEqual(len(r), 1, r)
        self.assertTrue(r[0].startswith("❌"), (texte, r))
        if mot:
            self.assertIn(mot, r[0])
        self.assertNotIn("Confirme", r[0])
        self.assertEqual([a for a in self.appels[avant:] if a[0][0] == "nc-claude"], [], "même pas relu")
        self.assertIn("Rien à confirmer", self.un("/code " + CODE_BON, t=1002))

    def test_controle_echappement_bidi_invisibles(self):
        for texte in ("a\tb", "a\x00b", "a\x07b", "a\x1bb", "a\x1b[31mb", "a\x7fb", "a\x85b", "a\x9bb", "a\x9f", "a‮b", "a⁦b",
                      "a​b", "a﻿b", "a­b", "a b", "a b", "aㅤb", "a͏b", "a b", "a　b",
                      "a\U000e0041b"):
            self.refuse(texte)

    def test_retour_a_la_ligne_par_le_texte_brut(self):
        self.un("/agents", t=1000)
        for texte in ("/repondre 1 ligne1\nligne2", "/repondre 1 ligne1\r\nligne2", "/repondre 1\nligne1\nligne2"):
            r = self.lancer(texte, t=1001)
            self.assertEqual(r[0], "❌ Un seul paragraphe : pas de retour à la ligne.", texte)
        self.assertEqual(self.commandes_ecrire(), [])

    def test_commence_par_point_d_exclamation(self):
        self.refuse("!rm -rf x", "commence par !")
        self.refuse("  !ls", "commence par !")

    def test_trop_long(self):
        self.refuse("x" * 2001, "trop long")
        r = self.demander("x" * 2000)
        self.assertIn("Confirme avec /code", r)
        self.assertEqual(len(r) < 4000, True)

    def test_vide(self):
        self.un("/agents", t=1000)
        self.assertIn("Usage", self.un("/repondre 1   ", t=1001))

    def test_accents_et_emojis_permis(self):
        self.assertIn("Confirme avec /code", self.demander("déjà fait ? 👍 ça marche — « ok »"))


class Secrets(Base):
    def f(self, t):
        return self.m.filtrer(t)

    def test_chaque_motif(self):
        cas = {
            "sk-": "avant sk-" + "A1b2" * 6 + " après",
            "ghp_": "x ghp_" + "a1B2" * 9,
            "gho_": "x gho_" + "a1B2" * 9,
            "github_pat_": "github_pat_" + "a1B2_" * 8,
            "xox": "jeton xoxb-" + "123456-abcdef-" * 3,
            "AKIA": "clé AKIA" + "0123456789ABCDEF",
            "bearer": "Authorization: Bearer " + "abcdEFGH0123" * 3,
        }
        for nom, texte in cas.items():
            out = self.f(texte)
            self.assertIn("[masqué]", out, nom)
            for morceau in ("A1b2A1b2", "a1B2a1B2", "123456-abcdef", "0123456789ABCDEF", "abcdEFGH0123"):
                self.assertNotIn(morceau, out, nom)
        out = self.f("-----BEGIN OPENSSH " + "PRIVATE KEY-----\nAAAAB3NzaC1\nxyz\n-----END OPENSSH " + "PRIVATE KEY-----\nsuite")
        self.assertEqual(out, "[clé masquée]\nsuite")
        out = self.f("-----BEGIN RSA " + "PRIVATE KEY-----\nAAAA\n(coupée")
        self.assertEqual(out, "[clé masquée]", "clé coupée par la troncature : tout est masqué jusqu'à la fin")

    def test_motifs_cle_valeur(self):
        for texte, reste in (("password=hunter2 ok", " ok"), ("PASSWORD: hunter2", ""), ("token=abc123", ""),
                             ("GITHUB_TOKEN=abc123 fait", " fait"), ("secret = 'mon secret'", ""), ('api_key="x y"', ""),
                             ("passwd=abc", "")):
            out = self.f(texte)
            self.assertNotIn("hunter2", out)
            self.assertNotIn("abc123", out)
            self.assertNotIn("mon secret", out)
            self.assertIn("=[masqué]", out, texte)
            self.assertTrue(out.endswith(reste), (texte, out))

    def test_chemins_et_emails(self):
        out = self.f("voir /home/alice/projets/x.py et /Users/bob/y et /home/alice")
        self.assertEqual(out, "voir /home/…/projets/x.py et /Users/…/y et /home/…")
        out = self.f("écris à jean.dupont+tag@exemple.fr ou a@b.co")
        self.assertEqual(out, "écris à …@… ou …@…")

    def test_suites_longues(self):
        out = self.f("hash " + "0123456789abcdef" * 2 + " fin")
        self.assertEqual(out, "hash [masqué] fin", "hexadécimal de 32 signes")
        out = self.f("b64 " + "QUJDREVGR0hJSktMTU5PUFFSU1RVVldYWVo=" + " fin")
        self.assertEqual(out, "b64 [masqué] fin")
        self.assertEqual(self.f("hex court " + "0123456789abcdef" + " base " + "A" * 31), "hex court 0123456789abcdef base " + "A" * 31,
                         "sous 32 signes : intact")

    def test_texte_ordinaire_intact(self):
        t = "J'ai corrigé le test, 3 fichiers modifiés. Voir README.md ligne 12."
        self.assertEqual(self.f(t), t)

    def test_borne_600_apres_filtre(self):
        out = self.m.extrait("a " * 600 + "sk-" + "Z" * 30)
        self.assertLessEqual(len(out), 600)
        self.assertTrue(out.endswith("…"))
        self.assertNotIn("sk-", self.m.extrait("sk-" + "Z" * 30))
        self.assertEqual(self.m.extrait(None), "")


class Journal(Base):
    def test_journal_sans_le_texte_en_0600(self):
        self.demander("mot de passe très secret du test")
        self.un("/code " + CODE_BON, t=1030)
        f = self.home / ".local/state/nc-jarvis/agents-envois.log"
        self.assertEqual(stat.S_IMODE(f.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(f.parent.stat().st_mode), 0o700)
        lignes = f.read_text().splitlines()
        self.assertEqual(len(lignes), 1)
        date, agent, dossier, longueur, ok = lignes[0].split("\t")
        self.assertRegex(date, r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}")
        self.assertEqual((agent, dossier, longueur, ok), ("Claude Code", "mon-projet", str(len("mot de passe très secret du test")), "ok"))
        self.assertNotIn("secret", f.read_text())

    def test_echec_note_echec(self):
        self.ecrire_code = 1
        self.demander()
        self.un("/code " + CODE_BON, t=1030)
        self.assertTrue((self.home / ".local/state/nc-jarvis/agents-envois.log").read_text().rstrip().endswith("\techec"))

    def test_journal_borne_et_pas_de_lien(self):
        for i in range(2000):
            self.m.journaliser("Codex", "dossier-" + "x" * 30, i, True, 1000 + i)
        f = self.home / ".local/state/nc-jarvis/agents-envois.log"
        self.assertLess(f.stat().st_size, self.m.JOURNAL_MAX + 200)
        self.assertLessEqual(len(f.read_text().splitlines()), self.m.JOURNAL_MAX // 40)
        self.assertEqual(stat.S_IMODE(f.stat().st_mode), 0o600)
        f.unlink()
        cible = self.home / "ailleurs"
        cible.write_text("intact")
        f.symlink_to(cible)
        with self.assertLogs("nc_agents", "WARNING"):
            self.m.journaliser("Codex", "d", 1, True)
        self.assertEqual(cible.read_text(), "intact", "un lien n'est pas suivi")


class ExecuterAvecEntree(unittest.TestCase):
    """nc_noctalia.executer donne une entrée standard (le code à usage unique ne passe pas par la ligne de commande)."""
    def test_entree_standard(self):
        src = REPO / "home/.local/share/nc-jarvis/server/nc_noctalia.py"
        n = types.ModuleType("nc_noctalia_entree")
        n.__file__ = str(src)
        exec(compile(src.read_text(), str(src), "exec"), n.__dict__)
        code, sortie = asyncio.run(n.executer(["/usr/bin/cat"], 5, 100, False, entree=b"123456\n"))
        self.assertEqual((code, sortie), (0, "123456"))
        code, sortie = asyncio.run(n.executer(["/usr/bin/cat"], 5, 100, False))
        self.assertEqual((code, sortie), (0, ""), "sans entrée : fermée, comme avant")
        code, _ = asyncio.run(n.executer(["/usr/bin/true"], 5, 100, False, entree=b"x" * 500000))
        self.assertEqual(code, 0, "un programme qui ne lit pas son entrée ne bloque pas")


class Branchement(unittest.TestCase):
    def test_pilotage_pas_rejoue_apres_l_arret(self):
        m = types.ModuleType("nc_telegram_test")
        src = REPO / "home/.local/share/nc-jarvis/server/nc_telegram.py"
        m.__file__ = str(src)
        exec(compile(src.read_text(), str(src), "exec"), m.__dict__)
        for t in ("/nc oui", "/pc", "/agents", "/claude", "/repondre 1 salut", "/code 123456", "/code@mon_bot 123456", "/AGENTS"):
            self.assertTrue(m.PILOTAGE.match(t), t)
        for t in ("/codex", "/agentsx", "bonjour /code", "/supprimer 1"):
            self.assertFalse(m.PILOTAGE.match(t), t)

    def test_commandes_enregistrees_en_local_et_menu(self):
        telegram = types.ModuleType("telegram")
        telegram.BotCommand = lambda c, d: types.SimpleNamespace(command=c, description=d)
        ext = types.ModuleType("telegram.ext")
        ext.CommandHandler = lambda noms, h, filters=None: types.SimpleNamespace(noms=noms, h=h)
        filtres = types.SimpleNamespace(UpdateType=types.SimpleNamespace(EDITED_MESSAGE=1))
        ext.filters = types.SimpleNamespace(UpdateType=types.SimpleNamespace(EDITED_MESSAGE=type("F", (), {"__invert__": lambda s: 0})()))
        m = types.ModuleType("nc_telegram_test2")
        src = REPO / "home/.local/share/nc-jarvis/server/nc_telegram.py"
        m.__file__ = str(src)
        exec(compile(src.read_text(), str(src), "exec"), m.__dict__)
        agents = module()
        ajoutes = []
        app = types.SimpleNamespace(add_handler=ajoutes.append)
        for mode, attendu in (("local", True), ("server", False)):
            ajoutes.clear()
            tb = types.SimpleNamespace(BOT_COMMANDS=[], _is_allowed=lambda u: True)
            with mock.patch.dict(sys.modules, {"telegram": telegram, "telegram.ext": ext, "nc_agents": agents}), \
                    mock.patch.dict(os.environ, DEPLOY_MODE=mode):
                m.commandes_nc(app, tb)
            noms = [tuple(h.noms) for h in ajoutes if hasattr(h, "noms")]
            self.assertIn(("agents", "claude"), noms)
            self.assertIn(("repondre",), noms)
            self.assertIn(("code",), noms, "les commandes sont toujours branchées : en mode serveur elles répondent « absent »")
            menu = {c.command for c in tb.BOT_COMMANDS}
            self.assertEqual("agents" in menu, attendu, mode)
            self.assertEqual("repondre" in menu, attendu, mode)


class NcClaudeEtatJson(unittest.TestCase):
    """Le vrai nc-claude (HOME et XDG_RUNTIME_DIR isolés) : etat --json donne le contrat, sans chemin ni contenu par défaut."""
    def setUp(self):
        d = tempfile.TemporaryDirectory(prefix="nc-cj-")
        self.addCleanup(d.cleanup)
        self.home = Path(d.name)
        (self.home / ".config/nc").mkdir(parents=True)
        self.run = self.home / "run"
        (self.run / "nc-claude").mkdir(parents=True, mode=0o700)
        self.env = dict(HOME=str(self.home), XDG_RUNTIME_DIR=str(self.run), PATH="/usr/bin:/bin", NC_LANGUE="fr", TMPDIR=str(self.home))

    def etat(self, sessions):
        (self.run / "nc-claude/etat.json").write_text(json.dumps({"sessions": sessions, "demandes": {}}))

    def lancer(self, *args):
        return subprocess.run([sys.executable, str(NC_CLAUDE), "etat", *args], env=self.env, capture_output=True, text=True, timeout=20)

    def test_contrat_sans_chemin_ni_contenu(self):
        h = str(self.home)
        self.etat({
            "a": {"id": "a", "cwd": "~/projets/mon-projet", "cwd_reel": h + "/projets/mon-projet", "etat": "attente", "ecrire": True,
                  "reponse": "Réponse longue avec secret", "etape": "Edit /home/x/y", "question": {"texte": "rm -rf /"}, "projet": "titre"},
            "codex-b": {"id": "codex-b", "agent": "codex", "cwd_reel": h, "etat": "travail", "ecrire": False, "message": "m"},
            "c": {"id": "c", "cwd_reel": "/", "etat": "fini", "ecrire": "oui"},
        })
        r = self.lancer("--json")
        self.assertEqual(r.returncode, 0, r.stderr)
        d = json.loads(r.stdout)
        self.assertEqual(d, {"contrat": 1, "sessions": [
            {"id": "a", "agent": "claude", "dossier": "mon-projet", "etat": "attente", "ecrire": True},
            {"id": "codex-b", "agent": "codex", "dossier": "~", "etat": "travail", "ecrire": False},
            {"id": "c", "agent": "claude", "dossier": "?", "etat": "fini", "ecrire": False}]})
        for interdit in ("secret", "/home", h, "rm -rf", "Edit"):
            self.assertNotIn(interdit, r.stdout)

    def test_texte_seulement_avec_l_option_et_pas_en_travail(self):
        self.etat({"a": {"id": "a", "cwd_reel": "/x/p", "etat": "fini", "ecrire": True, "reponse": "Dernier mot", "message": "court"},
                   "b": {"id": "b", "cwd_reel": "/x/q", "etat": "travail", "ecrire": True, "reponse": "périmé"},
                   "c": {"id": "c", "agent": "codex", "cwd_reel": "/x/r", "etat": "fini", "ecrire": True, "message": "msg codex"}})
        d = json.loads(self.lancer("--json", "--texte").stdout)
        self.assertEqual([s.get("message") for s in d["sessions"]], ["Dernier mot", None, "msg codex"])
        self.assertNotIn("message", json.loads(self.lancer("--json").stdout)["sessions"][0])

    def test_sans_etat_liste_vide(self):
        (self.run / "nc-claude/etat.json").unlink(missing_ok=True)
        self.assertEqual(json.loads(self.lancer("--json").stdout), {"contrat": 1, "sessions": []})

    def test_etat_en_clair_inchange(self):
        self.etat({"a": {"id": "a", "projet": "mon-projet", "etat": "fini", "etape": "x"}})
        self.assertIn("mon-projet  [fini]", self.lancer().stdout)


class AlerteParLesHooks(unittest.TestCase):
    """Les vrais hooks de nc-claude (HOME, XDG_RUNTIME_DIR et PATH isolés, faux nc-alertes qui note ses arguments) : l'alerte
    part au passage à « t'attend », une fois par attente, avec l'agent et le nom du dossier seulement ; rien sans les réglages."""
    def setUp(self):
        d = tempfile.TemporaryDirectory(prefix="nc-hk-")
        self.addCleanup(d.cleanup)
        self.home = Path(d.name)
        self.bin = self.home / "bin"
        self.bin.mkdir()
        (self.home / ".config/nc").mkdir(parents=True)
        (self.home / "run").mkdir(mode=0o700)
        import shutil
        shutil.copy2(NC_CLAUDE, self.bin / "nc-claude")
        (self.bin / "nc-alertes").write_text('#!/bin/sh\nprintf "%s\\n" "$*" >> "' + str(self.home) + '/alertes"\n')
        (self.bin / "nc-alertes").chmod(0o755)
        (self.bin / "hyprctl").write_text("#!/bin/sh\necho '[]'\n")
        (self.bin / "hyprctl").chmod(0o755)
        (self.bin / "systemctl").write_text("#!/bin/sh\nexit 1\n")
        (self.bin / "systemctl").chmod(0o755)
        self.env = dict(HOME=str(self.home), XDG_RUNTIME_DIR=str(self.home / "run"), PATH=str(self.bin), NC_LANGUE="fr",
                        TMPDIR=str(self.home))
        self.regler("oui", "oui")

    def regler(self, agents, alertes):
        (self.home / ".config/nc/reglages.conf").write_text("ALERTES_AGENTS=%s\nALERTES_TELEGRAM=%s\n" % (agents, alertes))

    def hook(self, *args, **evenement):
        r = subprocess.run([sys.executable, str(self.bin / "nc-claude"), *args], env=self.env, input=json.dumps(evenement),
                           capture_output=True, text=True, timeout=30)
        self.assertEqual(r.returncode, 0, r.stderr)

    def alertes(self, attendre=1):
        import time
        f = self.home / "alertes"
        fin = time.monotonic() + attendre
        while time.monotonic() < fin and not f.exists():
            time.sleep(0.05)
        time.sleep(0.2)
        return f.read_text().splitlines() if f.exists() else []

    def claude(self, nom, **kw):
        self.hook("hook", hook_event_name=nom, session_id="s1", cwd=str(self.home / "mon-projet"), **kw)

    def test_claude_attend_une_fois_puis_de_nouveau_apres_un_tour(self):
        self.claude("UserPromptSubmit")
        self.claude("Notification", notification_type="idle_prompt", message="texte SECRET de la conversation")
        self.assertEqual(self.alertes(), ["agent Claude Code mon-projet s1"])
        self.claude("Notification", notification_type="idle_prompt", message="encore")
        self.assertEqual(self.alertes(0), ["agent Claude Code mon-projet s1"], "déjà en attente : pas de seconde alerte")
        self.assertNotIn("SECRET", (self.home / "alertes").read_text())
        self.claude("UserPromptSubmit")
        self.claude("Notification", notification_type="permission_prompt", message="Autoriser rm ?")
        self.assertEqual(len(self.alertes()), 2, "un nouveau passage à « t'attend » : nc-alertes limite à une par 5 minutes")
        self.assertNotIn("rm", (self.home / "alertes").read_text())

    def test_autres_agents_par_suivre(self):
        self.hook("ia", "codex", "permission", session_id="c1", cwd=str(self.home / "site"))
        self.assertEqual(self.alertes(), ["agent Codex site codex-c1"])

    def test_rien_sans_les_deux_reglages(self):
        for agents, alertes in (("non", "oui"), ("oui", "non"), ("non", "non")):
            self.regler(agents, alertes)
            self.claude("Notification", notification_type="idle_prompt", message="x")
            self.assertEqual(self.alertes(0.3), [], (agents, alertes))
        (self.home / ".config/nc/reglages.conf").write_text("")
        self.claude("Notification", notification_type="idle_prompt", message="x")
        self.assertEqual(self.alertes(0.3), [], "non par défaut")

    def test_sans_nc_alertes_le_hook_ne_gene_pas(self):
        (self.bin / "nc-alertes").unlink()
        self.claude("Notification", notification_type="idle_prompt", message="x")
        self.assertEqual(self.alertes(0.3), [])
        d = json.loads((self.home / "run/nc-claude/etat.json").read_text())
        self.assertEqual(d["sessions"]["s1"]["etat"], "attente")

    def test_dossier_personnel_nomme_tilde(self):
        self.hook("hook", hook_event_name="Notification", notification_type="idle_prompt", session_id="s2", cwd=str(self.home), message="x")
        self.assertEqual(self.alertes(), ["agent Claude Code ~ s2"], "jamais le nom du compte")


if __name__ == "__main__":
    unittest.main()

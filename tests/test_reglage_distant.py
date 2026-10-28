"""Réglages changés à distance (JARVIS : Telegram, cockpit ; plan « agir » de l'IA) : liste blanche vérifiée côté PC
(nc-reglages set --distant), dans l'overlay (nc_noctalia) et dans nc-ia ; texte d'un plan nettoyé avant affichage.
Tout se passe dans un faux HOME ; aucune IA, aucun réseau, aucun service."""
import asyncio
import importlib.machinery
import importlib.util
import io
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
from contextlib import redirect_stdout

from tests.test_ia import charger_nc_ia

REPO = Path(__file__).resolve().parents[1]
BIN = REPO / "home/.local/bin"
SERVEUR = REPO / "home/.local/share/nc-jarvis/server"
INTERDITES = ("NOEUD_JARVIS", "NOEUD_SESSION_MINUTES", "NOEUD_SESSION_CAPTURES", "NOEUD_BAC_INTERDITS", "NOEUD_CONFIRMATION",
              "NOEUD_BAC_RESEAU", "NOEUD_SANS_CONFIRMATION", "IA_MODE", "IA_BAC_REPLI", "IA_ACTIONS", "ALERTES_TELEGRAM",
              "SPOTLIGHT_IA", "TELEGRAM_AGENTS", "TELEGRAM_AGENTS_TEXTE", "MAJ_SYSTEME", "VEILLE_VERROU", "VERROU_MESSAGE", "COUVERCLE", "CLAUDE_ILE", "FONDS_DOSSIER",
              "APPLI_TERMINAL")


def charger(nom, chemin):
    l = importlib.machinery.SourceFileLoader(nom, str(chemin))
    m = importlib.util.module_from_spec(importlib.util.spec_from_loader(nom, l))
    l.exec_module(m)
    return m


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        env = mock.patch.dict(os.environ, HOME=str(self.home), DEPLOY_MODE="local")
        env.start()
        self.addCleanup(env.stop)


class ListesIdentiques(Base):
    def test_trois_listes_identiques_et_sans_cle_sensible(self):
        reg = charger("nc_reglages_t", BIN / "nc-reglages")
        ia = charger_nc_ia("nc_ia_distant")
        sys.path.insert(0, str(SERVEUR))
        self.addCleanup(sys.path.remove, str(SERVEUR))
        noc = charger("nc_noctalia_t", SERVEUR / "nc_noctalia.py")
        self.assertEqual(reg.DISTANT_PERMIS, ia.DISTANT_PERMIS)
        self.assertEqual(reg.DISTANT_PERMIS, noc.DISTANT_PERMIS)
        sauv = charger("nc_sauvegarde_t", BIN / "nc-sauvegarde")
        for cle in reg.DISTANT_PERMIS:
            self.assertIn(cle, reg.PAR_CLE, cle)
            self.assertNotIn(reg.PAR_CLE[cle].genre, ("texte", "dossier"), cle)
            self.assertFalse(sauv.CLES_LOCALES.fullmatch(cle), f"{cle} est une clé locale de nc-sauvegarde")
            self.assertFalse(cle.startswith(("NOEUD_", "IA_", "ALERTES_", "MAJ_", "VEILLE_")) or "VERROU" in cle or cle == "SPOTLIGHT_IA", cle)
        for cle in INTERDITES:
            self.assertTrue(reg.distant_refuse(cle), cle)


class NcReglages(Base):
    def lancer(self, *args):
        env = dict(os.environ, HOME=str(self.home), XDG_CONFIG_HOME=str(self.home / ".config"), LC_ALL="C.UTF-8", LANGUAGE="fr")
        return subprocess.run([sys.executable, "-I", str(BIN / "nc-reglages"), *args], capture_output=True, text=True, env=env, timeout=60)

    def fichier(self):
        f = self.home / ".config/nc/reglages.conf"
        return f.read_text() if f.exists() else ""

    def test_set_distant_refuse_les_cles_sensibles(self):
        for cle, val in (("NOEUD_JARVIS", "oui"), ("NOEUD_SESSION_MINUTES", "15"), ("NOEUD_SESSION_CAPTURES", "oui"),
                         ("NOEUD_BAC_INTERDITS", ""), ("IA_MODE", "auto"), ("NOEUD_CONFIRMATION", "les-deux"), ("VERROU_MESSAGE", "x")):
            r = self.lancer("set", "--distant", cle, val or "x")
            self.assertNotEqual(r.returncode, 0, cle)
            self.assertRegex(r.stderr, "à distance|remotely")
        self.assertNotIn("NOEUD_", self.fichier())
        self.assertNotIn("IA_MODE", self.fichier())

    def test_set_distant_accepte_une_cle_permise_et_valide_la_valeur(self):
        r = self.lancer("set", "--distant", "ILE_DATE", "non")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("ILE_DATE=non", self.fichier())
        r = self.lancer("set", "--distant", "ILE_DATE", "peut-etre")
        self.assertNotEqual(r.returncode, 0)

    def test_lecture_et_set_local_inchanges(self):
        self.assertEqual(self.lancer("get", "NOEUD_JARVIS").returncode, 0)
        self.assertEqual(self.lancer("set", "ILE_DATE", "non").returncode, 0)


class Overlay(Base):
    def setUp(self):
        super().setUp()
        sys.path.insert(0, str(SERVEUR))
        self.addCleanup(sys.path.remove, str(SERVEUR))
        for n in ("nc_noctalia", "nc_management"):
            sys.modules.pop(n, None)
            self.addCleanup(sys.modules.pop, n, None)
        import nc_noctalia, nc_management
        self.noc, self.mgmt = nc_noctalia, nc_management
        self.appels = []

        async def executer(argv, delai=20):
            self.appels.append(list(argv))
            return 0, "ok"
        nc_noctalia.executer = executer

    def manage(self, cle, valeur=None, confirmed=True):
        params = {"cle": cle}
        if valeur is not None:
            params["valeur"] = valeur
        return asyncio.run(self.mgmt.dispatch("noctalia", {"action": "reglage", "params": params}, confirmed))

    def test_manage_refuse_meme_confirme(self):
        for cle in ("NOEUD_JARVIS", "NOEUD_SESSION_MINUTES", "NOEUD_SESSION_CAPTURES", "NOEUD_BAC_INTERDITS", "IA_MODE", "NOEUD_CONFIRMATION"):
            r = self.manage(cle, "oui", confirmed=True)
            self.assertFalse(r["success"], cle)
        self.assertEqual(self.appels, [], "rien n'est lancé pour une clé hors liste blanche")

    def test_manage_cle_permise_et_lecture(self):
        r = self.manage("ILE_DATE", "non")
        self.assertTrue(r["success"], r)
        self.assertEqual(self.appels[-1], ["nc-reglages", "set", "--distant", "ILE_DATE", "non"])
        r = self.manage("NOEUD_JARVIS")                  # lecture sans valeur : permise
        self.assertTrue(r["success"], r)
        self.assertEqual(self.appels[-1], ["nc-reglages", "get", "NOEUD_JARVIS"])


class PlanIA(Base):
    def setUp(self):
        super().setUp()
        self.ia = charger_nc_ia("nc_ia_plan")

    def valider(self, cle, valeur):
        return self.ia.valider_action({"outil": "reglage", "args": {"cle": cle, "valeur": valeur}}, ["reglages"])

    def test_agir_refuse_noeud_et_autres(self):
        for cle in ("NOEUD_JARVIS", "NOEUD_SESSION_MINUTES", "NOEUD_SESSION_CAPTURES", "NOEUD_CONFIRMATION", "NOEUD_BAC_RESEAU",
                    "IA_BAC_REPLI", "ALERTES_TELEGRAM", "MAJ_SYSTEME"):
            with self.assertRaises(self.ia.ErreurIA, msg=cle):
                self.valider(cle, "oui")

    def test_agir_accepte_une_cle_permise(self):
        self.assertEqual(self.valider("ILE_DATE", "non")["args"]["cle"], "ILE_DATE")

    def test_valeur_avec_controle_refusee(self):
        for v in ("a\rb", "a\x1b[2Kb", "a\u202eb", "a\u2066b", "a\u061cb", "a\x85b"):
            with self.assertRaises(self.ia.ErreurIA, msg=repr(v)):
                self.valider("ILE_DATE", v)

    def test_texte_du_plan_nettoye(self):
        sale = "ok\x1b[2K\rcache\u202e\u2066\u200f\u061c\x9b fin\nligne2\ttab"
        propre = self.ia.texte_sur(sale, True)
        self.assertNotRegex(propre, r"[\x00-\x08\x0b-\x1f\x7f-\x9f\u061c\u200b-\u200f\u202a-\u202e\u2066-\u2069]")
        self.assertIn("\n", propre)
        self.assertNotIn("\n", self.ia.texte_sur(sale))
        plan = dict(reponse=sale, actions=[dict(ok=True, fait=False, danger=False, libelle="x\ry\x1b", resultat="", note="n\u202e")],
                    refus=["r\x1b[31m\u2067"])
        sortie = io.StringIO()
        with redirect_stdout(sortie):
            self.ia.afficher_plan(plan)
        self.assertNotRegex(sortie.getvalue(), r"[\r\x1b\x9b\u202e\u2066\u2067\u200f\u061c]")


if __name__ == "__main__":
    unittest.main()


class ConfigUpdate(Base):
    """config.update / config.clear sans FastAPI : update_config appelée directement, dans un faux dossier de serveur."""

    def setUp(self):
        super().setUp()
        sys.path.insert(0, str(SERVEUR))
        self.addCleanup(sys.path.remove, str(SERVEUR))
        sys.modules.pop("nc_management", None)
        self.addCleanup(sys.modules.pop, "nc_management", None)
        import nc_management
        self.m = nc_management
        self.racine = self.home / "srv"
        for d in ("gateway", "home-runner"):
            (self.racine / d).mkdir(parents=True)
        self.paths = [self.racine / ".env", self.racine / "gateway/.env", self.racine / "home-runner/.env"]
        for p in self.paths:
            p.write_text('TELEGRAM_ALLOWED_USER_IDS="1"\nDISCORD_ALLOWED_USER_IDS="2"\nTELEGRAM_TOKEN="t"\nDISCORD_TOKEN="d"\nSECRET_KEY="s"\n')
        champs = [dict(key=k, label=k, secret=s, default="", group="g") for k, _, s in self.m.BASE_FIELDS]
        for patch_ in (mock.patch.object(self.m, "root", lambda: self.racine), mock.patch.object(self.m, "schema", lambda: dict(fields=champs))):
            patch_.start()
            self.addCleanup(patch_.stop)

    def lus(self):
        return [p.read_text() for p in self.paths]

    def test_refuse_acces_et_secrets(self):
        avant = self.lus()
        for cle in ("TELEGRAM_ALLOWED_USER_IDS", "DISCORD_ALLOWED_USER_IDS", "TELEGRAM_TOKEN", "DISCORD_TOKEN", "SECRET_KEY",
                    "TELEGRAM_WEBHOOK_URL", "DISCORD_GUILD_ID"):
            with self.assertRaises(ValueError, msg=cle):
                self.m.update_config({cle: "999"})
        with self.assertRaises(ValueError):
            self.m.update_config({"BRIEFING_TIME": "09:00", "TELEGRAM_ALLOWED_USER_IDS": "999"})
        for cle in ("SECRET_KEY", "TELEGRAM_ALLOWED_USER_IDS"):
            with self.assertRaises(ValueError, msg=cle):
                self.m.update_config({}, [cle])
        self.assertEqual(self.lus(), avant, ".env inchangé")

    def test_separateur_de_ligne_unicode_ne_cree_pas_de_cle(self):
        # Attaque trouvée en relecture : un champ permis avec U+2028 (ou U+0085…) passait le filtre ord < 32, puis la
        # réécriture suivante (splitlines) le coupait en une nouvelle ligne : TELEGRAM_ALLOWED_USER_IDS=999 injecté
        avant = self.lus()
        for sep in ("\u2028", "\u2029", "\u0085", "\x1c", "\x7f", "\x9b"):
            with self.assertRaises(ValueError, msg=repr(sep)):
                self.m.update_config({"BRIEFING_CITY": "Paris" + sep + "TELEGRAM_ALLOWED_USER_IDS=999"})
        self.assertEqual(self.lus(), avant, ".env inchangé")
        # Même si une telle valeur était déjà dans le fichier, la réécriture ne crée pas de clé : split sur \n seulement
        piege = 'A=1\nBRIEFING_CITY="Paris\u2028TELEGRAM_ALLOWED_USER_IDS=999"\n'
        relu = self.m.rewrite_env(piege, {"BRIEFING_CITY": "Paris"})
        self.assertEqual(relu, 'A=1\nBRIEFING_CITY="Paris"\n')
        self.assertNotIn("999", relu)

    def test_champ_permis_passe_et_champ_inchange_ignore(self):
        with mock.patch.dict(os.environ, {"TELEGRAM_ALLOWED_USER_IDS": "1"}):
            self.assertTrue(self.m.update_config({"BRIEFING_TIME": "09:00", "TELEGRAM_ALLOWED_USER_IDS": "1", "DISCORD_TOKEN": ""})["saved"])
        for t in self.lus():
            self.assertIn("09:00", t)
            self.assertIn('TELEGRAM_ALLOWED_USER_IDS="1"', t)
            self.assertIn('DISCORD_TOKEN="d"', t)

    def test_vider_un_jeton_reste_permis(self):
        self.m.update_config({}, ["TELEGRAM_TOKEN"])
        self.assertTrue(all("TELEGRAM_TOKEN=" in t and 't"' not in t.split("TELEGRAM_TOKEN=")[1].split("\n")[0] for t in self.lus()))

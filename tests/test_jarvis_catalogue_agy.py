"""Catalogue des modèles d'agy (issue #37) : `agy models` relu en fond, sans jamais bloquer, avec un cache disque, et une
liste blanche avant tout parce que les identifiants repartent après --model. Faux agy locaux, HOME isolé, aucun compte."""
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import threading
import time
import types
import unittest
from unittest.mock import AsyncMock, patch

from tests.test_jarvis_runner import appeler, charger_runner, fastapi, faux_upstream

REPO = Path(__file__).resolve().parents[1]
SOURCE = REPO / "home/.local/share/nc-jarvis/server/nc_engines.py"
RUNNER = REPO / "home/.local/share/nc-jarvis/server/nc_runner.py"


def normaliser_amont(model, effort):
    """Copie de _normalize_model_effort de l'amont épinglé (agy_bridge.py, 17525af) : seul Flash y est réaligné."""
    prefixe, efforts = "gemini-3.8-flash-", {"low", "medium", "high"}
    if model and (model == "claude-opus-4-6-thinking" or ("opus" in model and "thinking" in model)):
        return model, None
    if model and model.startswith(prefixe):
        suffixe = model[len(prefixe):]
        if suffixe in efforts:
            if not effort:
                effort = suffixe
            elif effort != suffixe:
                if effort in efforts:
                    model = prefixe + effort
                elif effort in {"xhigh", "max"}:
                    model, effort = prefixe + "high", "high"
                else:
                    effort = suffixe
    return model, effort


LISTE = """gemini-4-argon-medium\tGemini 4 Argon (Medium)
gemini-4-argon-high\tGemini 4 Argon (High)
gemini-4-argon-low\tGemini 4 Argon (Low)
gemini-3.8-flash-high\tGemini 3.8 Flash (High)
gemini-3.8-flash-medium\tGemini 3.8 Flash (Medium)
gemini-3.8-flash-low\tGemini 3.8 Flash (Low)
claude-opus-5-5-low\tClaude Opus 5.5 (Low)
claude-opus-5-5-medium\tClaude Opus 5.5 (Medium)
claude-opus-5-5-high\tClaude Opus 5.5 (High)
claude-sonnet-5-5-low\tClaude Sonnet 5.5 (Low)
claude-sonnet-5-5-medium\tClaude Sonnet 5.5 (Medium)
claude-sonnet-5-5-high\tClaude Sonnet 5.5 (High)
gpt-oss-120b-medium\tGPT-OSS 120B (Medium)
"""
AIDE = "Usage of agy:\n  --effort  Reasoning effort\n  models          List available models\n"
ANCIENNE_AIDE = "Usage of agy:\n  --effort  Reasoning effort\n"


def charger():
    m = types.ModuleType("engines_catalogue")
    exec(compile(SOURCE.read_text(), str(SOURCE), "exec"), m.__dict__)
    return m


def faux_agy(dossier, modeles="print(" + repr(LISTE) + ", end='')", aide=AIDE):
    """Un agy qui répond à --help, note chaque appel, et joue `modeles` (du Python) pour la sous-commande models."""
    chemin = Path(dossier) / "agy"
    chemin.write_text(
        "#!" + sys.executable + "\nimport os, subprocess, sys, time\nfrom pathlib import Path\n"
        "Path(__file__).with_suffix('.appels').open('a').write(' '.join(sys.argv[1:]) + '\\n')\n"
        "if sys.argv[1:] == ['--help']:\n    print(" + repr(aide) + ")\n    sys.exit(0)\n"
        + modeles + "\n")
    chemin.chmod(0o755)
    return chemin


def appels(chemin):
    f = chemin.with_suffix(".appels")
    return f.read_text().splitlines() if f.exists() else []


class Parseur(unittest.TestCase):
    def setUp(self):
        self.m = charger()

    def test_la_liste_de_l_issue(self):
        liste = self.m.lire_catalogue_agy(LISTE)
        self.assertEqual(len(liste), 13)
        self.assertEqual(liste[2], dict(id="gemini-4-argon-low", name="Gemini 4 Argon (Low)"))
        self.assertEqual(liste[-1]["id"], "gpt-oss-120b-medium")

    def test_une_ligne_hors_format_rejette_tout(self):
        for piege in ("--dangerously-skip-permissions\tAucune garde", "-x\tNom", "sans tabulation", "espace dedans\tNom",
                      "modèle\tNom", "a/b\tNom", "\tNom", "x" * 56 + "\tNom", "a;b\tNom", "$(touch x)\tNom", "id\n--yolo\tNom",
                      "a\tNom\tune colonne de plus"):
            self.assertIsNone(self.m.lire_catalogue_agy(LISTE + piege + "\n"), repr(piege))

    def test_vide_ou_blanc_jamais_une_liste_vide(self):
        for sortie in ("", "\n", "  \n\n"):
            self.assertIsNone(self.m.lire_catalogue_agy(sortie))

    def test_nom_nettoye_borne_ou_remplace(self):
        liste = self.m.lire_catalogue_agy("a\t\x1b[31mRouge\x07\u202e\u200b\nb\t\x1b\x07\nc\t" + "n" * 200 + "\nd\t  \n"
                                          "e\t@everyone **gras** <b>\u2028fin\nf\t" + "n" * 79 + " suite\ng\tGemini 4 (Low) é/x+1\n")
        self.assertEqual(liste[0], dict(id="a", name="31mRouge"))
        self.assertEqual(liste[1], dict(id="b", name="b"), "plus rien de lisible : l'identifiant")
        self.assertEqual(len(liste[2]["name"]), 80)
        self.assertEqual(liste[3], dict(id="d", name="d"))
        self.assertEqual(liste[4], dict(id="e", name="everyone gras bfin"), "ni @ ni * pour les messageries, ni saut de ligne")
        self.assertEqual(liste[5]["name"], "n" * 79, "pas d'espace final après la coupe : le cache le relit")
        self.assertEqual(liste[6], dict(id="g", name="Gemini 4 (Low) é/x+1"))
        self.assertEqual(self.m.lire_catalogue_agy("h\tLlama 3.1  70B\n")[0]["name"], "Llama 3.1 70B", "espaces doublés réduits")

    def test_doublons_retires_cinquante_au_plus_retour_chariot_tolere(self):
        self.assertEqual([x["id"] for x in self.m.lire_catalogue_agy("a\tA\r\nb\tB\r\na\tAutre\r\n")], ["a", "b"])
        self.assertEqual(len(self.m.lire_catalogue_agy("".join(f"m{i}\tM\n" for i in range(80)))), 50)


class Lancement(unittest.TestCase):
    def setUp(self):
        d = tempfile.TemporaryDirectory(prefix="nc-agy-")
        self.addCleanup(d.cleanup)
        self.d = Path(d.name)
        self.m = charger()

    def test_sortie_normale_entree_fermee_jetons_du_serveur_absents(self):
        agy = faux_agy(self.d, "open(os.environ['SORTIE'] if 'SORTIE' in os.environ else " + repr(str(self.d / "env")) + ", 'w').write("
                               "repr((sys.stdin.read(), sorted(os.environ))))\nprint('a\\tA')")
        with patch.dict(os.environ, TELEGRAM_TOKEN="secret-du-serveur", SECRET_KEY="x", DBUS_SESSION_BUS_ADDRESS="unix:path=/bus"):
            self.assertEqual(self.m.lancer_catalogue_agy(str(agy)), "a\tA\n")
        vu = (self.d / "env").read_text()
        self.assertIn("('',", vu, "entrée standard fermée")
        self.assertNotIn("TELEGRAM_TOKEN", vu)
        self.assertNotIn("SECRET_KEY", vu)
        self.assertIn("DBUS_SESSION_BUS_ADDRESS", vu, "le trousseau du compte reste joignable")

    def test_pas_connecte_code_non_nul(self):
        agy = faux_agy(self.d, "print('Please sign in', file=sys.stderr)\nsys.exit(1)")
        self.assertIsNone(self.m.lancer_catalogue_agy(str(agy)))

    def test_code_non_nul_meme_avec_une_liste(self):
        self.assertIsNone(self.m.lancer_catalogue_agy(str(faux_agy(self.d, "print('a\\tA')\nsys.exit(3)"))))

    def _vivant(self, pid):
        try:
            os.kill(pid, 0)
            return Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[0] != "Z"
        except OSError:
            return False

    def test_muet_jusqu_au_delai_tue_tout_le_groupe(self):
        """agy et son enfant (un spinner qui garde la sortie) : tués ensemble, et la réponse revient au délai."""
        pids = self.d / "pids"
        agy = faux_agy(self.d, "p = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])\n"
                               "open(" + repr(str(pids)) + ", 'w').write(f'{os.getpid()} {p.pid}')\ntime.sleep(60)")
        self.m.AGY_CATALOGUE_DELAI = 3
        debut = time.monotonic()
        self.assertIsNone(self.m.lancer_catalogue_agy(str(agy)))
        self.assertLess(time.monotonic() - debut, 12)
        for pid in map(int, pids.read_text().split()):
            fin = time.monotonic() + 5
            while self._vivant(pid) and time.monotonic() < fin:
                time.sleep(0.05)
            self.assertFalse(self._vivant(pid), f"{pid} encore vivant")

    def test_sortie_enorme_coupee_sans_tout_lire(self):
        agy = faux_agy(self.d, "ligne = b'a\\tA\\n' * 1000\nwhile True:\n    sys.stdout.buffer.write(ligne)\n    sys.stdout.flush()")
        debut = time.monotonic()
        self.assertIsNone(self.m.lancer_catalogue_agy(str(agy)))
        self.assertLess(time.monotonic() - debut, 10)

    def test_octets_illisibles_et_programme_absent(self):
        self.assertIsNone(self.m.lancer_catalogue_agy(str(faux_agy(self.d, "sys.stdout.buffer.write(b'a\\t\\xff\\xfe\\n')"))))
        self.assertIsNone(self.m.lancer_catalogue_agy(str(self.d / "absent")))

    def test_garde_de_version_regardee_une_fois(self):
        agy = faux_agy(self.d)
        self.assertTrue(self.m.agy_cite_models(str(agy)))
        self.assertTrue(self.m.agy_cite_models(str(agy)))
        self.assertEqual(appels(agy), ["--help"])
        m2 = charger()
        self.assertFalse(m2.agy_cite_models(str(faux_agy(self.d, aide=ANCIENNE_AIDE))))
        m3 = charger()
        self.assertFalse(m3.agy_cite_models(str(faux_agy(self.d, aide="Send your models to the cloud\n"))),
                         "le mot dans une phrase n'est pas la sous-commande")


    def test_garde_de_version_un_help_rate_n_est_pas_retenu(self):
        """Un --help lent ou impossible répond non cette fois-ci, sans couper le catalogue jusqu'au redémarrage du runner."""
        agy = faux_agy(self.d)
        for erreur in (self.m.subprocess.TimeoutExpired(cmd="agy", timeout=5), OSError("occupé")):
            with patch.object(self.m.subprocess, "run", side_effect=erreur):
                self.assertFalse(self.m.agy_cite_models(str(agy)))
            self.assertIsNone(self.m._AGY_CITE_MODELS, "rien de retenu")
        self.assertTrue(self.m.agy_cite_models(str(agy)), "le prochain essai regarde vraiment")
        # Un --help allé au bout est retenu, en oui comme en non
        with patch.object(self.m.subprocess, "run", side_effect=AssertionError("relu")):
            self.assertTrue(self.m.agy_cite_models(str(agy)))
        m2 = charger()
        vieux = faux_agy(self.d, aide=ANCIENNE_AIDE)
        self.assertFalse(m2.agy_cite_models(str(vieux)))
        with patch.object(m2.subprocess, "run", side_effect=AssertionError("relu")):
            self.assertFalse(m2.agy_cite_models(str(vieux)))


class Moteur(unittest.TestCase):
    def setUp(self):
        d = tempfile.TemporaryDirectory(prefix="nc-agy-")
        self.addCleanup(d.cleanup)
        self.d = Path(d.name)
        self.sessions = {}
        self.cfg = self.session_de("default")
        self.m = charger()
        self.m.isoler = AsyncMock(return_value=None)
        p = patch.object(self.m, "agy_accepte_permission_mode", return_value=True)
        p.start()
        self.addCleanup(p.stop)
        env = patch.dict(os.environ, HOME=str(self.d), XDG_CONFIG_HOME=str(self.d / ".config"))
        env.start()
        self.addCleanup(env.stop)
        self.up = self.faux_amont()
        self.addCleanup(self.attendre)

    def session_de(self, cle):
        return self.sessions.setdefault(cle, dict(model=None, effort=None))

    def commande_finale(self, cle="default"):
        """Ce que l'amont met sur la ligne de commande d'agy pour cette session (agy_bridge, avant de lancer le tour)."""
        s = self.session_de(cle)
        return normaliser_amont(s["model"], s["effort"])

    def faux_amont(self):
        def update_session(model=None, effort=None, mode=None, permission_mode=None, session_key="default"):
            cfg = self.session_de(session_key)
            if model:
                cfg["model"] = model.strip()
                cfg["model"], cfg["effort"] = normaliser_amont(cfg["model"], cfg.get("effort"))
            if effort:
                cfg["effort"] = effort.strip().lower()
                cfg["model"], cfg["effort"] = normaliser_amont(cfg.get("model"), cfg.get("effort"))
            return dict(cfg)

        return types.SimpleNamespace(
            __file__=str(self.d / "main.py"), KNOWN_MODELS=[dict(id="amont-1", name="Amont")],
            run_agy=AsyncMock(return_value=dict(success=True, output="AGY")),
            get_session_info=lambda session_key="default": dict(self.session_de(session_key)),
            update_session=update_session, reset_session_async=AsyncMock(return_value={}),
            list_recent_conversations=lambda **kw: [], get_conversation_history=lambda *a, **kw: [], resume_conversation=lambda *a: {},
            delete_conversation=lambda *a: {}, delete_all_conversations=lambda: {}, get_token_usage=lambda: dict(tokens_available=False),
            _reset_memory_injection=lambda session_key=None: None, _should_inject_memory=lambda version: True, render_memory_prompt=lambda: "")

    def avec(self, chemin):
        p = patch.object(self.m, "executable", return_value=None if chemin is None else str(chemin))
        p.start()
        self.addCleanup(p.stop)

    def attendre(self):
        for fil in threading.enumerate():
            if fil.name == "nc-agy-modeles":
                fil.join(30)

    def cache(self):
        return self.d / ".nc-jarvis-agy-models.json"

    def test_le_catalogue_du_compte_remplace_celui_de_l_amont_et_garde_sur_disque(self):
        agy = faux_agy(self.d)
        self.avec(agy)
        e = self.m.install(self.up)
        self.assertEqual(appels(agy), [], "charger le module ne lance rien")
        self.assertEqual([x["id"] for x in e.models()], ["amont-1"])
        self.assertTrue(e.catalogue_au_demarrage())
        self.attendre()
        self.assertEqual(appels(agy), ["--help", "models"])
        self.assertEqual(len(e.models()), 13)
        self.assertEqual(self.up.KNOWN_MODELS, e.models(), "/models voit la même liste")
        self.assertIn("gemini-4-argon-low", [x["id"] for x in e.snapshot()["engines"][0]["models"]])
        self.assertEqual(stat.S_IMODE(self.cache().stat().st_mode), 0o600)
        # Redémarrage : le cache sert tout de suite, sans processus
        os.unlink(agy.with_suffix(".appels"))
        e2 = self.m.Engines(self.up)
        self.assertEqual(len(e2.models()), 13)
        self.assertFalse(e2.catalogue_au_demarrage())
        self.assertFalse(e2.rafraichir_agy())
        self.assertEqual(appels(agy), [])

    def test_models_repond_sans_attendre_et_un_seul_fil(self):
        agy = faux_agy(self.d, "time.sleep(4)\nprint('a\\tA')")
        self.avec(agy)
        e = self.m.install(self.up)
        debut = time.monotonic()
        self.assertTrue(e.rafraichir_agy())
        self.assertEqual([x["id"] for x in e.models()], ["amont-1"])
        e.snapshot()
        self.assertLess(time.monotonic() - debut, 3, "ni le lancement ni la lecture n'attendent agy")
        e.agy_essai = None                      # même sans la pause après un essai, le verrou tient
        self.assertFalse(e.rafraichir_agy(), "un seul fil à la fois")
        self.attendre()
        self.assertEqual(appels(agy).count("models"), 1)
        self.assertEqual([x["id"] for x in e.models()], ["a"])

    def test_echec_garde_la_derniere_liste_et_ne_relance_pas_a_chaque_demande(self):
        for jeu in ("print('Please sign in', file=sys.stderr)\nsys.exit(1)", "print('une ligne sans tabulation')",
                    "print('--dangerously-skip-permissions\\tAucune garde')", "pass"):
            with self.subTest(jeu=jeu):
                if self.cache().exists():
                    self.cache().unlink()
                agy = faux_agy(self.d, jeu)
                if agy.with_suffix(".appels").exists():
                    agy.with_suffix(".appels").unlink()
                p = patch.object(self.m, "executable", return_value=str(agy))
                p.start()
                try:
                    e = self.m.Engines(self.up)
                    self.assertTrue(e.rafraichir_agy())
                    self.attendre()
                    self.assertEqual([x["id"] for x in e.models()], ["amont-1"], "jamais de liste vide")
                    self.assertFalse(self.cache().exists(), "rien d'écrit après un échec")
                    self.assertFalse(e.rafraichir_agy(), "pas de nouveau processus avant le prochain essai")
                    self.assertEqual(appels(agy).count("models"), 1)
                finally:
                    p.stop()

    def test_ancien_agy_jamais_lance_avec_models(self):
        agy = faux_agy(self.d, aide=ANCIENNE_AIDE)
        self.avec(agy)
        e = self.m.install(self.up)
        self.assertTrue(e.rafraichir_agy())
        self.attendre()
        self.assertEqual(appels(agy), ["--help"])
        self.assertEqual([x["id"] for x in e.models()], ["amont-1"])

    def test_aucun_processus_si_ia_coupee_ou_agy_absent(self):
        agy = faux_agy(self.d)
        self.avec(agy)
        conf = self.d / ".config/nc/reglages.conf"
        conf.parent.mkdir(parents=True)
        conf.write_text("IA_MODE=non\n")
        e = self.m.install(self.up)
        self.assertFalse(e.rafraichir_agy())
        self.assertFalse(e.catalogue_au_demarrage())
        self.assertEqual(appels(agy), [])
        conf.write_text("IA_MODE=auto\n")
        with patch.object(self.m, "executable", return_value=None):
            self.assertFalse(e.rafraichir_agy())
        # Coupée juste après la décision : le fil regarde encore, et models ne part pas
        with patch.object(self.m, "ia_coupee", side_effect=[False, True]):
            self.assertTrue(e.rafraichir_agy())
            self.attendre()
        self.assertEqual(appels(agy), ["--help"])

    def test_cache_vieux_relu_seulement_sur_demande(self):
        agy = faux_agy(self.d)
        self.avec(agy)
        self.cache().write_text(json.dumps(dict(t=time.time() - 7 * 3600, modeles=[dict(id="vieux", name="Vieux")])))
        self.cache().chmod(0o600)
        e = self.m.install(self.up)
        self.assertEqual([x["id"] for x in e.models()], ["vieux"])
        self.assertFalse(e.catalogue_au_demarrage(), "au démarrage, seulement sans aucune liste")
        self.assertEqual(appels(agy), [])
        self.assertTrue(e.rafraichir_agy())
        self.attendre()
        self.assertEqual(len(e.models()), 13)

    def test_date_dans_le_futur_compte_comme_vieille(self):
        agy = faux_agy(self.d)
        self.avec(agy)
        self.cache().write_text(json.dumps(dict(t=time.time() + 86400, modeles=[dict(id="x", name="X")])))
        self.cache().chmod(0o600)
        self.assertTrue(self.m.install(self.up).rafraichir_agy())
        self.attendre()

    def test_cache_refuse_lien_droits_json_casse_ou_identifiant_piege(self):
        bon = json.dumps(dict(t=time.time(), modeles=[dict(id="m", name="M")]))
        self.cache().write_text(bon)
        self.cache().chmod(0o600)
        self.assertEqual(self.m.lire_cache_agy(self.cache())[0], [dict(id="m", name="M")], "témoin")
        self.cache().chmod(0o644)
        self.assertIsNone(self.m.lire_cache_agy(self.cache()), "lisible par les autres")
        self.cache().chmod(0o600)
        modele = '"modeles":[{"id":"m","name":"M"}]'
        for mauvais in ("{cassé", "[]", "null", json.dumps(dict(t=True, modeles=[dict(id="m", name="M")])),
                        '{"t":1' + "0" * 400 + "," + modele + "}", '{"t":NaN,' + modele + "}", '{"t":Infinity,' + modele + "}",
                        json.dumps(dict(t=1.0, modeles=[])), json.dumps(dict(t=1.0, modeles="m")),
                        json.dumps(dict(t=1.0, modeles=[dict(id="--yolo", name="M")])),
                        json.dumps(dict(t=1.0, modeles=[dict(id="m", name="M\x1b[31m")])),
                        json.dumps(dict(t=1.0, modeles=[dict(id="m")])),
                        json.dumps(dict(t=1.0, modeles=[dict(id=f"m{i}", name="M") for i in range(51)])),
                        "x" * (self.m.AGY_CATALOGUE_DISQUE_MAX + 1)):
            self.cache().write_text(mauvais)
            self.assertIsNone(self.m.lire_cache_agy(self.cache()), mauvais[:60])
        cible = self.d / "ailleurs.json"
        cible.write_text(bon)
        cible.chmod(0o600)
        self.cache().unlink()
        self.cache().symlink_to(cible)
        self.assertIsNone(self.m.lire_cache_agy(self.cache()), "lien symbolique")
        # Le moteur démarre quand même, sur la liste de l'amont, et n'écrit pas à travers le lien
        agy = faux_agy(self.d)
        self.avec(agy)
        e = self.m.install(self.up)
        self.assertEqual([x["id"] for x in e.models()], ["amont-1"])
        self.assertTrue(e.rafraichir_agy())
        self.attendre()
        self.assertEqual(cible.read_text(), bon, "aucune écriture à travers le lien")

    def test_un_rafraichissement_n_ecrase_pas_le_catalogue_de_codex(self):
        agy = faux_agy(self.d)
        self.avec(agy)
        e = self.m.install(self.up)
        e.choose(engine="codex", model="gpt", effort="high")
        codex = self.up.KNOWN_MODELS
        self.assertTrue(e.rafraichir_agy())
        self.attendre()
        self.assertIs(self.up.KNOWN_MODELS, codex)
        self.assertEqual(len(e.models("agy")), 13, "agy a bien sa nouvelle liste")
        e.choose(engine="agy")
        self.assertEqual(self.up.KNOWN_MODELS, e.models("agy"), "et /models la retrouve en revenant sur agy")

    def moteur_catalogue(self):
        self.avec(None)
        e = self.m.install(self.up)
        e.agy_models = self.m.lire_catalogue_agy(LISTE)
        return e

    def test_install_models_snapshot_et_choose_ne_lancent_jamais_models(self):
        """Seul le runner décide de relire : le module chargé, lu ou réglé ne lance aucun processus agy models."""
        agy = faux_agy(self.d)
        self.avec(agy)
        e = self.m.install(self.up)
        e.models()
        e.snapshot()
        e.choose(model="gemini-4-argon-low", effort="")
        self.assertNotIn("models", appels(agy))
        self.assertEqual([f for f in threading.enumerate() if f.name == "nc-agy-modeles"], [])

    def test_un_cache_a_la_date_immense_ne_bloque_pas_le_demarrage(self):
        self.avec(None)
        self.cache().write_text('{"t":1' + "0" * 400 + ',"modeles":[{"id":"m","name":"M"}]}')
        self.cache().chmod(0o600)
        self.assertEqual([x["id"] for x in self.m.install(self.up).models()], ["amont-1"])

    def test_snapshot_dit_si_la_liste_vient_du_compte(self):
        agy = faux_agy(self.d)
        self.avec(agy)
        e = self.m.install(self.up)
        moteur = lambda: e.snapshot()["engines"][0]
        self.assertIs(moteur()["catalogue_compte"], False, "liste de repli")
        self.assertTrue(e.rafraichir_agy())
        self.attendre()
        self.assertIs(moteur()["catalogue_compte"], True)
        self.assertIs(e.snapshot()["engines"][1]["catalogue_compte"], False, "les autres moteurs n'ont pas ce catalogue")

    def etat_enregistre(self, **agy):
        self.cache().write_text(json.dumps(dict(t=time.time(), modeles=self.m.lire_catalogue_agy(LISTE))))
        self.cache().chmod(0o600)
        chemin = self.d / ".nc-jarvis-engines.json"
        chemin.write_text(json.dumps(dict(engine="agy", settings=dict(agy=agy), conversations=[], active={})))
        chemin.chmod(0o600)
        self.avec(None)
        return self.m.install(self.up)

    def test_restauration_alignee_contradiction_d_un_ancien_etat(self):
        self.etat_enregistre(model="gemini-4-argon-low", effort="high")
        self.assertEqual(self.commande_finale(), ("gemini-4-argon-high", "high"))

    def test_restauration_alignee_modele_seul_et_sans_variante(self):
        self.etat_enregistre(model="gemini-4-argon-high")
        self.assertEqual(self.commande_finale(), ("gemini-4-argon-high", "high"))
        self.sessions.clear()
        self.cfg = self.session_de("default")
        self.etat_enregistre(model="gpt-oss-120b-medium", effort="high")
        self.assertEqual(self.commande_finale(), ("gpt-oss-120b-medium", "medium"))

    def test_restauration_modele_sorti_du_catalogue_garde(self):
        self.etat_enregistre(model="claude-sonnet-4-6", effort="high")
        self.assertEqual(self.commande_finale(), ("claude-sonnet-4-6", "high"))

    def test_alignement_vise_la_session_du_pc_qui_demande(self):
        e = self.moteur_catalogue()
        self.session_de("pc-a").update(model="gemini-4-argon-low", effort="low")
        self.session_de("pc-b").update(model="claude-opus-5-5-low", effort="low")
        e.choose(session_key="pc-a", effort="high")
        self.assertEqual(self.commande_finale("pc-a"), ("gemini-4-argon-high", "high"))
        self.assertEqual(self.commande_finale("pc-b"), ("claude-opus-5-5-low", "low"), "l'autre PC ne bouge pas")

    def test_alignement_effort_inconnu_suit_le_suffixe(self):
        e = self.moteur_catalogue()
        self.cfg.update(model="gemini-4-argon-low", effort="low")
        e.choose(effort="ultra")
        self.assertEqual(self.commande_finale(), ("gemini-4-argon-low", "low"))

    def test_alignement_modele_donne_sans_effort(self):
        e = self.moteur_catalogue()
        self.cfg.update(model="gemini-3.8-flash-high", effort="high")
        e.choose(model="gemini-4-argon-low", effort="")
        self.assertEqual(self.commande_finale(), ("gemini-4-argon-low", "low"), "pas de --effort high contradictoire")
        self.assertEqual(e.state["settings"]["agy"]["effort"], "low", "enregistré aussi")

    def test_alignement_effort_seul_vers_la_variante_du_catalogue(self):
        e = self.moteur_catalogue()
        self.cfg.update(model="gemini-4-argon-low", effort="low")
        e.choose(effort="high")
        self.assertEqual(self.commande_finale(), ("gemini-4-argon-high", "high"))
        self.assertEqual(e.state["settings"]["agy"]["model"], "gemini-4-argon-high")

    def test_alignement_effort_seul_sans_variante_le_modele_reste(self):
        e = self.moteur_catalogue()
        self.cfg.update(model="gpt-oss-120b-medium", effort="medium")
        e.choose(effort="high")
        self.assertEqual(self.commande_finale(), ("gpt-oss-120b-medium", "medium"))

    def test_alignement_xhigh_et_max_valent_high(self):
        e = self.moteur_catalogue()
        for effort in ("xhigh", "max"):
            self.cfg.update(model="claude-opus-5-5-low", effort="low")
            e.choose(effort=effort)
            self.assertEqual(self.commande_finale(), ("claude-opus-5-5-high", "high"), effort)

    def test_alignement_modele_et_effort_contradictoires(self):
        """Le rang « Réflexion » des réglages change l'effort sans toucher au modèle : Appliquer envoie les deux."""
        e = self.moteur_catalogue()
        e.choose(model="gemini-4-argon-low", effort="high")
        self.assertEqual(self.commande_finale(), ("gemini-4-argon-high", "high"))

    def test_sans_suffixe_rien_ne_change(self):
        e = self.moteur_catalogue()
        self.cfg.update(model="ancien", effort="medium")
        e.choose(model="claude-sonnet-4-6", effort="")
        self.assertEqual(self.commande_finale(), ("claude-sonnet-4-6", "medium"))
        e.choose(effort="high")
        self.assertEqual(self.commande_finale(), ("claude-sonnet-4-6", "high"))
        e.choose(model="claude-opus-4-6-thinking", effort="")
        self.assertEqual(self.commande_finale()[0], "claude-opus-4-6-thinking")

    def test_flash_comme_avant_et_modele_enregistre_jamais_change_en_silence(self):
        e = self.moteur_catalogue()
        self.cfg.update(model="gemini-3.8-flash-low", effort="low")
        e.choose(effort="medium")
        self.assertEqual(self.commande_finale(), ("gemini-3.8-flash-medium", "medium"))
        e.choose(model="gemini-3.8-flash-low", effort="")
        self.assertEqual(self.commande_finale(), ("gemini-3.8-flash-low", "low"))
        # Sorti du catalogue : gardé tel quel, à l'utilisateur de décider
        self.cfg.update(model="claude-sonnet-4-6", effort="")
        e.choose(mode="plan")
        self.assertEqual(self.commande_finale()[0], "claude-sonnet-4-6")

    def test_autres_moteurs_non_alignes(self):
        faux = faux_agy(self.d)
        self.avec(faux)
        e = self.m.install(self.up)
        with patch.object(self.m, "commande", return_value=[]):
            e.choose(engine="codex", model="gpt-5-low", effort="high")
        self.assertEqual(e.state["settings"]["codex"], dict(model="gpt-5-low", effort="high"))


@unittest.skipUnless(fastapi, "FastAPI requis")
class RunnerDeBoutEnBout(unittest.TestCase):
    """Le vrai nc_runner et le vrai nc_engines devant un faux amont et un faux agy trouvé dans le PATH."""

    def setUp(self):
        d = tempfile.TemporaryDirectory(prefix="nc-agy-")
        self.addCleanup(d.cleanup)
        self.d = Path(d.name)
        (self.d / "home-runner").mkdir()
        self.agy = faux_agy(self.d)
        env = patch.dict(os.environ, HOME=str(self.d), XDG_CONFIG_HOME=str(self.d / ".config"), NC_PIECES_JOINTES=str(self.d / "pieces"),
                         PATH=str(self.d) + os.pathsep + os.environ.get("PATH", ""))
        env.start()
        self.addCleanup(env.stop)
        amont = Moteur.faux_amont(types.SimpleNamespace(d=self.d, session_de=lambda cle: dict(model=None, effort=None)))
        self.up = faux_upstream(self.d)
        for nom, valeur in vars(amont).items():
            if nom not in ("__file__",):
                setattr(self.up, nom, valeur)

        self.secret_refuse = False

        @self.up.app.get("/models")
        def lister(request: fastapi.Request):                 # synchrone exprès : la route de l'amont n'est jamais enveloppée
            if self.secret_refuse:
                raise fastapi.HTTPException(401)
            return {"models": self.up.KNOWN_MODELS}
        self.addCleanup(self.attendre)

    def attendre(self):
        for fil in threading.enumerate():
            if fil.name == "nc-agy-modeles":
                fil.join(30)

    def charger(self):
        return charger_runner(self.up)

    def test_au_demarrage_sans_cache_puis_rien_tant_que_la_liste_est_fraiche(self):
        runner = self.charger()
        self.attendre()
        self.assertEqual(appels(self.agy), ["--help", "models"], "relu une fois au chargement du runner")
        self.assertEqual(len(runner.engines.models()), 13)
        self.assertEqual(appeler(runner.app, "/nc/engines", methode="GET"), 200)
        self.assertEqual(appeler(runner.app, "/models", methode="GET"), 200)
        self.attendre()
        self.assertEqual(appels(self.agy).count("models"), 1, "liste fraîche : aucun processus")

    def relecture_par(self, chemin):
        runner = self.charger()
        self.attendre()
        os.unlink(self.agy.with_suffix(".appels"))
        runner.engines.agy_lu = time.time() - 7 * 3600
        runner.engines.agy_essai = None
        self.assertEqual(appeler(runner.app, chemin, methode="GET"), 200)
        self.attendre()
        # /nc/engines lit aussi son --help pour les modes de permission : seul compte le nombre de relectures
        self.assertEqual(appels(self.agy).count("models"), 1, chemin)

    def test_models_sans_le_secret_ne_lance_rien(self):
        """Une requête refusée (401) ne fait partir aucun processus : la relecture vient après la réponse de l'amont."""
        runner = self.charger()
        self.attendre()
        os.unlink(self.agy.with_suffix(".appels"))
        runner.engines.agy_lu = time.time() - 7 * 3600
        runner.engines.agy_essai = None
        self.secret_refuse = True
        self.assertEqual(appeler(runner.app, "/models", methode="GET"), 401)
        self.attendre()
        self.assertEqual(appels(self.agy), [])

    def test_nc_engines_relit_une_liste_trop_vieille(self):
        self.relecture_par("/nc/engines")

    def test_models_relit_une_liste_trop_vieille(self):
        """Telegram, Discord et nc-jarvis lisent /models : quelqu'un qui n'ouvre jamais l'île garde un catalogue vivant."""
        self.relecture_par("/models")


if __name__ == "__main__":
    unittest.main()

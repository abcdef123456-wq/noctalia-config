"""nc-alertes : batterie sous le seuil (une fois par passage), services en échec (une fois par échec), fin de mise à jour ;
rien sans le réglage ni la connexion. Faux sysfs, faux systemctl, faux gateway ; HOME isolé."""
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
import unittest

REPO = Path(__file__).resolve().parents[1]
BIN = REPO / "home/.local/bin"
CLE = "cle-de-test"


class Gateway(BaseHTTPRequestHandler):
    recus = []
    reponse = {"sent": True}

    def do_POST(self):
        corps = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        Gateway.recus.append((self.path, self.headers.get("X-Secret-Key"), corps))
        data = json.dumps(Gateway.reponse).encode()
        self.send_response(200); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(data))); self.end_headers()
        self.wfile.write(data)

    def log_message(self, *a):
        pass


class Alertes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.serveur = HTTPServer(("127.0.0.1", 0), Gateway)
        threading.Thread(target=cls.serveur.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.serveur.shutdown()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        (self.home / "bin").mkdir()
        for nom in ("nc-alertes", "nc-assistant", "nc-ia"):
            shutil.copy2(BIN / nom, self.home / "bin" / nom)
        (self.home / "bin/systemctl").write_text('#!/bin/sh\nprintf "%s" "${NC_TEST_ECHECS:-}"\n')
        (self.home / "bin/systemctl").chmod(0o755)
        (self.home / "sys/BAT0").mkdir(parents=True)
        (self.home / "sys/BAT0/type").write_text("Battery\n")
        (self.home / "sys/AC/").mkdir()
        (self.home / "sys/AC/type").write_text("Mains\n")
        (self.home / ".config/nc").mkdir(parents=True)
        self.regler("oui", "20")
        conf = self.home / ".config/nc/assistant.conf"
        conf.write_text('URL="http://127.0.0.1:%d"\nSECRET_KEY="%s"\n' % (self.serveur.server_port, CLE))
        conf.chmod(0o600)
        Gateway.recus = []
        Gateway.reponse = {"sent": True}

    def regler(self, alertes, seuil):
        (self.home / ".config/nc/reglages.conf").write_text("LANGUE=fr\nALERTES_TELEGRAM=%s\nBATTERIE_ALERTE=%s\n" % (alertes, seuil))

    def batterie(self, pct, statut):
        (self.home / "sys/BAT0/capacity").write_text("%d\n" % pct)
        (self.home / "sys/BAT0/status").write_text(statut + "\n")

    def lancer(self, *args, echecs="", eco=False, langue="fr"):
        env = dict(HOME=str(self.home), XDG_STATE_HOME=str(self.home / "state"), NC_ALERTES_SYSFS=str(self.home / "sys"),
                   NC_TEST_ECHECS=echecs, NC_LANGUE=langue, PATH=str(self.home / "bin") + os.pathsep + "/usr/bin:/bin",
                   NC_POWER_SUPPLY="batterie" if eco else "secteur", NC_PROFIL="power-saver" if eco else "balanced")
        r = subprocess.run([str(self.home / "bin/nc-alertes"), *args], env=env, capture_output=True, text=True, timeout=20)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r

    def textes(self):
        return [c["params"]["text"] for _, _, c in Gateway.recus]

    def test_batterie_une_fois_par_passage(self):
        self.batterie(35, "Discharging"); self.lancer("verifier")
        self.assertEqual(self.textes(), [])
        self.batterie(18, "Discharging"); self.lancer("verifier")
        self.assertEqual(self.textes(), ["🔋 Batterie à 18 % (seuil 20 %) : branche le PC."])
        chemin, cle, corps = Gateway.recus[0]
        self.assertEqual((chemin, cle, corps["op"], corps["confirmed"]), ("/api/nc/manage", CLE, "notify", True))
        self.batterie(12, "Discharging"); self.lancer("verifier")
        self.assertEqual(len(self.textes()), 1, "toujours sous le seuil : pas de second message")
        self.batterie(14, "Charging"); self.lancer("verifier")
        self.batterie(60, "Discharging"); self.lancer("verifier")
        self.batterie(19, "Discharging"); self.lancer("verifier")
        self.assertEqual(len(self.textes()), 2, "nouveau passage sous le seuil après une charge : nouveau message")
        self.assertEqual(json.loads((self.home / "state/nc/alertes.json").read_text())["batterie_sous"], True)

    def test_pile_d_une_souris_n_est_pas_la_batterie(self):
        """Revue ALERT-01 : sur un PC fixe, la pile d'une souris sans fil (scope Device) donnait « branche le PC »."""
        import shutil
        shutil.rmtree(self.home / "sys/BAT0")
        souris = self.home / "sys/hidpp_battery_0"; souris.mkdir()
        for nom, v in (("type", "Battery"), ("scope", "Device"), ("capacity", "12"), ("status", "Discharging")):
            (souris / nom).write_text(v + "\n")
        self.lancer("verifier")
        self.assertEqual(self.textes(), [], "PC fixe : pas d'alerte de batterie")
        # Un portable : sa batterie (sans scope, ou System) compte, même si la souris trie avant
        bat = self.home / "sys/zBAT1"; bat.mkdir()
        for nom, v in (("type", "Battery"), ("scope", "System"), ("capacity", "15"), ("status", "Discharging")):
            (bat / nom).write_text(v + "\n")
        self.lancer("verifier")
        self.assertEqual(self.textes(), ["🔋 Batterie à 15 % (seuil 20 %) : branche le PC."])

    def test_services_en_echec_une_fois(self):
        self.batterie(80, "Charging")
        self.lancer("verifier", echecs="nc-pouls.service loaded failed failed Halo\nfoo.service loaded failed failed x\n")
        self.assertEqual(self.textes(), ["⚠️ Service en échec sur le PC : nc-pouls.service (détails : journalctl --user -u NOM)."])
        self.lancer("verifier", echecs="nc-pouls.service loaded failed failed Halo\n")
        self.assertEqual(len(self.textes()), 1, "même échec : pas de répétition")
        self.lancer("verifier", echecs="")
        self.lancer("verifier", echecs="nc-pouls.service loaded failed failed Halo\n")
        self.assertEqual(len(self.textes()), 2, "retombé en échec après réparation : nouveau message")
        Gateway.reponse = {"sent": False, "error": "Telegram non configuré (TELEGRAM_TOKEN)"}
        r = self.lancer("verifier", echecs="nc-pouls.service loaded failed failed Halo\nnc-ile.service loaded failed failed Ile\n")
        self.assertTrue(r.stderr.strip(), "échec du gateway signalé sur stderr (sans détail serveur : nc-assistant le masque)")
        Gateway.reponse = {"sent": True}
        self.lancer("verifier", echecs="nc-pouls.service loaded failed failed Halo\nnc-ile.service loaded failed failed Ile\n")
        self.assertIn("nc-ile.service", self.textes()[-1], "non prévenu une fois : réessayé au tour suivant")

    def test_fin_de_mise_a_jour_et_message_libre(self):
        self.lancer("maj", "0")
        self.lancer("maj", "3")
        self.lancer("envoyer", "Bonjour", "le", "monde")
        self.assertEqual(self.textes(), ["✅ Mise à jour du système terminée : système à jour.",
                                         "✅ Mise à jour du système terminée, 3 encore en attente.", "Bonjour le monde"])

    def test_mise_a_jour_echouee_jamais_terminee(self):
        """Revue B1 R3 : pacman -Su en échec, et Telegram disait « ✅ terminée »."""
        self.lancer("maj", "2", "echec", "1")
        self.lancer("maj", "0", "echec", "3")
        self.assertEqual(self.textes(), ["❌ La mise à jour du système a échoué (code 1), 2 encore en attente.",
                                         "❌ La mise à jour du système a échoué (code 3)."])

    def test_en_pause_en_economie_sur_batterie(self):
        """Une alerte part d'un automatisme (toutes les 5 min) : arrière-plan, en pause en Économie sur batterie."""
        self.lancer("maj", "0", eco=True)
        self.assertEqual(self.textes(), [])
        self.lancer("maj", "0")
        self.assertEqual(len(self.textes()), 1, "sur secteur, elle part")

    def test_batterie_et_services_partent_en_economie(self):
        """nc-profile-sync passe seul en Économie (ECO_AUTO) : l'alerte de batterie faible ne doit pas être retenue."""
        self.batterie(15, "Discharging")
        self.lancer("verifier", eco=True)
        self.assertEqual(self.textes(), ["🔋 Batterie à 15 % (seuil 20 %) : branche le PC."])
        self.lancer("verifier", echecs="nc-pouls.service loaded failed failed Halo\n", eco=True)
        self.assertEqual(len(self.textes()), 2, "service en échec : part aussi en Économie")
        self.lancer("maj", "0", eco=True)
        self.assertEqual(len(self.textes()), 2, "la mise à jour reste en pause en Économie")

    def test_ia_mode_non_coupe_aussi_les_alertes_urgentes(self):
        self.batterie(15, "Discharging")
        (self.home / ".config/nc/reglages.conf").write_text("LANGUE=fr\nALERTES_TELEGRAM=oui\nIA_MODE=non\n")
        self.lancer("verifier", eco=True)
        self.assertEqual(self.textes(), [])

    def test_assistant_charge_seulement_quand_une_alerte_part(self):
        # Divers-3 : activé mais rien à envoyer (batterie pleine, aucun service en échec) : nc-assistant n'est pas chargé
        client = self.home / "bin/nc-assistant"
        vrai = client.read_text()
        client.write_text("open(__file__ + '.charge', 'w').close()\n" + vrai)
        self.batterie(80, "Discharging")
        self.lancer("verifier")
        self.assertFalse(Path(str(client) + ".charge").exists(), "rien à envoyer : pas chargé")
        self.batterie(10, "Discharging")
        self.lancer("verifier")
        self.assertTrue(Path(str(client) + ".charge").exists(), "une alerte part : chargé")
        self.assertEqual(len(self.textes()), 1)

    def test_envoyer_coupe_le_dit_sur_stderr(self):
        self.regler("non", "20")
        r = self.lancer("envoyer", "coucou")
        self.assertIn("rien envoyé", r.stderr)
        self.assertEqual(self.textes(), [])
        self.assertEqual(self.lancer("verifier").stderr, "")        # la minuterie reste muette
        self.assertIn("nothing sent", self.lancer("envoyer", "hi", langue="en").stderr)

    def test_aide_en_francais_et_en_anglais_meme_coupe(self):
        self.regler("non", "20")
        self.assertIn("alertes de la machine vers Telegram", self.lancer("--help").stdout)
        self.assertIn("machine alerts to Telegram", self.lancer("--help", langue="en").stdout)

    def test_texte_service_different_en_anglais(self):
        self.lancer("verifier", echecs="nc-pouls.service\n", langue="en")
        self.assertEqual(self.textes(), ["⚠️ Failed service on the PC: nc-pouls.service (details: journalctl --user -u NAME)."])

    def test_rien_sans_reglage_ni_connexion(self):
        self.batterie(5, "Discharging")
        self.regler("non", "20")
        # Revue OPT-01 : sans le réglage, nc-assistant n'est même pas chargé (toutes les 5 min, sur batterie aussi)
        client = self.home / "bin/nc-assistant"
        vrai = client.read_text()
        client.write_text("open(__file__ + '.charge', 'w').close()\n" + vrai)
        self.lancer("verifier"); self.lancer("maj", "0")
        self.assertFalse(Path(str(client) + ".charge").exists(), "nc-assistant pas chargé")
        client.write_text(vrai)
        self.assertEqual(self.textes(), [])
        self.regler("oui", "0"); self.lancer("verifier")
        self.assertEqual(self.textes(), [], "seuil 0 : jamais")
        self.regler("oui", "20")
        (self.home / ".config/nc/assistant.conf").unlink()
        r = self.lancer("verifier")
        self.assertEqual(self.textes(), [])
        self.assertIn("non configuré", r.stderr)
        self.assertFalse(json.loads((self.home / "state/nc/alertes.json").read_text()).get("batterie_sous"), "non prévenu : l'alerte reste due")


if __name__ == "__main__":
    unittest.main()

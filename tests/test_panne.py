"""nc-panne : un service de la session en échec → une notification (Redémarrer, Expliquer si une IA est là), une fois
par demi-heure au plus ; « Expliquer » passe par nc-ia panne ; réglage PANNES=non ; les unités systemd (OnFailure= de
tous les services de la session, sans boucle pour nc-panne@ lui-même)."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "home/.local/bin/nc-panne"
UNITES = REPO / "home/.config/systemd/user"


class Panne(unittest.TestCase):
    def setUp(self):
        d = tempfile.TemporaryDirectory(prefix="nc-panne-")
        self.addCleanup(d.cleanup)
        self.home = Path(d.name)
        self.faux = self.home / "faux"
        self.faux.mkdir()
        (self.home / ".config/nc").mkdir(parents=True)
        (self.home / ".config/nc/reglages.conf").write_text("LANGUE=fr\n")
        (self.home / ".local/bin").mkdir(parents=True)
        self.journal = self.home / "journal"
        self.systemctl()
        self.programme("journalctl", 'echo "Segmentation fault (core dumped)"')
        self.choix("expliquer")
        self.ia(disponible=True)

    def systemctl(self, systeme="running", graphique="active", service="active"):
        self.programme("systemctl", 'echo "systemctl $*" >> "$JOURNAL"; case "$*" in *Description*) echo "Île dynamique";; '
                       f'*is-system-running*) echo {systeme};; *"is-active graphical-session.target"*) echo {graphique};; '
                       f'*is-active*) echo {service};; esac')

    def programme(self, nom, corps, dossier=None):
        f = (dossier or self.faux) / nom
        f.write_text("#!/bin/sh\n" + corps + "\n")
        f.chmod(0o755)

    def choix(self, action):
        # Fausse notify-send : note ses arguments (une ligne JSON) et « clique » sur l'action demandée
        f = self.faux / "notify-send"
        f.write_text("#!/usr/bin/env python3\nimport json, os, sys\n"
                     "open(os.environ['JOURNAL'], 'a').write('notify ' + json.dumps(sys.argv[1:], ensure_ascii=False) + '\\n')\n"
                     f"print({action!r})\n")
        f.chmod(0o755)

    def ia(self, disponible):
        self.programme("nc-ia", 'echo "nc-ia $*" >> "$JOURNAL"; [ "$1" = actif ] && exit ' + ("0" if disponible else "1") + "; exit 0",
                       self.home / ".local/bin")

    def lancer(self, *args):
        env = dict(HOME=str(self.home), PATH=f"{self.faux}:/usr/bin:/bin", NC_LANGUE="fr", JOURNAL=str(self.journal),
                   XDG_CACHE_HOME=str(self.home / "cache"))
        return subprocess.run([str(SCRIPT), *args], env=env, capture_output=True, text=True, timeout=20)

    def appels(self):
        return self.journal.read_text() if self.journal.exists() else ""

    def notifs(self):
        return [json.loads(l[7:]) for l in self.appels().splitlines() if l.startswith("notify ")]

    def test_notification_puis_expliquer(self):
        self.assertEqual(self.lancer("signaler", "nc-ile.service").returncode, 0)
        n = self.notifs()
        self.assertEqual(len(n), 1)
        self.assertIn("redemarrer=Redémarrer", n[0])
        self.assertIn("expliquer=Expliquer", n[0])
        self.assertIn("Île dynamique est en panne", n[0])
        self.assertIn("Segmentation fault", n[0][-1])
        self.assertIn("nc-ia panne nc-ile.service --livrer", self.appels())
        # Le même service retombe tout de suite : pas de deuxième notification
        self.lancer("signaler", "nc-ile.service")
        self.assertEqual(len(self.notifs()), 1)

    def test_redemarrer_et_sans_ia(self):
        self.choix("redemarrer")
        self.ia(disponible=False)
        self.lancer("signaler", "noctalia.service")
        self.assertNotIn("expliquer=", json.dumps(self.notifs()[0], ensure_ascii=False), "IA coupée, pas de bouton Expliquer")
        j = self.appels()
        # Revue PANNE-01 : un service en panne a souvent atteint sa limite de démarrages ; le compteur d'abord
        self.assertLess(j.index("systemctl --user reset-failed noctalia.service"), j.index("systemctl --user restart noctalia.service"))
        self.assertNotIn("nc-ia panne", j)
        self.assertIn("Île dynamique est reparti", json.dumps(self.notifs()[-1], ensure_ascii=False))

    def test_portee_et_fermeture_de_session(self):
        # Par défaut, seulement les services du bureau
        self.lancer("signaler", "gvfs-daemon.service")
        self.assertFalse(self.notifs())
        (self.home / ".config/nc/reglages.conf").write_text("LANGUE=fr\nPANNES=tous\nPANNES_IGNORER=foo.service\n")
        self.lancer("signaler", "foo.service")
        self.assertFalse(self.notifs(), "écarté par PANNES_IGNORER")
        self.lancer("signaler", "gvfs-daemon.service")
        self.assertEqual(len(self.notifs()), 1, "PANNES=tous")
        # Session qui se ferme : rien
        (self.home / ".config/nc/reglages.conf").write_text("LANGUE=fr\n")
        self.systemctl(systeme="stopping")
        self.lancer("signaler", "pipewire.service")
        self.systemctl(graphique="deactivating")
        self.lancer("signaler", "wireplumber.service")
        self.assertEqual(len(self.notifs()), 1)

    def test_expliquer_impossible_le_dit(self):
        self.programme("nc-ia", 'echo "nc-ia $*" >> "$JOURNAL"; [ "$1" = actif ] && exit 0; echo "Aucune IA n\'a pu répondre" >&2; exit 1',
                       self.home / ".local/bin")
        self.lancer("signaler", "nc-ile.service")
        self.assertIn("Explication impossible", json.dumps(self.notifs()[-1], ensure_ascii=False))

    def test_coupe_et_noms_refuses(self):
        (self.home / ".config/nc/reglages.conf").write_text("LANGUE=fr\nPANNES=non\n")
        self.lancer("signaler", "nc-ile.service")
        self.assertFalse(self.notifs())
        (self.home / ".config/nc/reglages.conf").write_text("LANGUE=fr\n")
        self.assertEqual(self.lancer("signaler", "x; rm -rf ~").returncode, 2)
        self.assertEqual(self.lancer("signaler", "nc-panne@nc-ile.service.service").returncode, 2, "jamais lui-même")
        self.assertFalse(self.notifs())

    def test_unites_systemd(self):
        drop = (UNITES / "service.d/nc-panne.conf").read_text()
        self.assertIn("OnFailure=nc-panne@%n.service", drop)
        self.assertIn("OnFailure=\n", (UNITES / "nc-panne@.service.d/sans-boucle.conf").read_text(), "pas de boucle")
        self.assertIn("ExecStart=%h/.local/bin/nc-panne signaler %i", (UNITES / "nc-panne@.service").read_text())


class AgentPolkit(unittest.TestCase):
    def test_agent_polkit_attend_la_session_graphique(self):
        """L'agent polkit de KDE démarrait avant l'écran (sous uwsm) : 5 plantages, abandon, plus de mot de passe."""
        t = (UNITES / "plasma-polkit-agent.service.d/nc-apres-session.conf").read_text()
        self.assertIn("After=graphical-session.target", t)
        self.assertIn("RestartSec=", t)


class MinuteursHorsLigne(unittest.TestCase):
    def test_verification_de_la_config_hors_ligne_n_est_pas_une_panne(self):
        """Revue MAJ-01 : nc-maj verifier sortait en 128 hors ligne (pipefail) : nc-maj-verif.service en échec, donc
        une notification de panne à chaque passage du minuteur."""
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            depot, home = d / "depot", d / "home"
            (home / ".config/nc").mkdir(parents=True)
            g = lambda *a: subprocess.run(["git", "-C", str(depot), *a], capture_output=True, check=True)
            depot.mkdir()
            g("init", "-q"); g("-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "--allow-empty", "-m", "x")
            g("remote", "add", "origin", "https://127.0.0.1:9/x.git")     # injoignable, sans réseau
            (home / ".config/nc/depot").write_text(str(depot))
            r = subprocess.run(["bash", str(REPO / "home/.local/bin/nc-maj"), "verifier"], env=dict(os.environ, HOME=str(home)),
                               capture_output=True, text=True, timeout=60)
            self.assertEqual(r.returncode, 0, r.stderr)

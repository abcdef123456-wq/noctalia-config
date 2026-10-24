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
        self.programme("gdbus", "echo \"(['body', 'actions'],)\"")      # l'île : sans balisage

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
                   XDG_CACHE_HOME=str(self.home / "cache"), NC_PANNES_ATTENTE="0.05")
        return subprocess.run([str(SCRIPT), *args], env=env, capture_output=True, text=True, timeout=20)

    def lancer_fond(self, *args):
        env = dict(HOME=str(self.home), PATH=f"{self.faux}:/usr/bin:/bin", NC_LANGUE="fr", JOURNAL=str(self.journal),
                   XDG_CACHE_HOME=str(self.home / "cache"), NC_PANNES_ATTENTE="1.5")
        return subprocess.Popen([str(SCRIPT), *args], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

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

    def test_pannes_ensemble_une_seule_notification(self):
        """Revues PANNE-02 et PANNE-03 : douze pannes en même temps faisaient douze notifications, et le registre
        anti-répétition (écrit sans verrou) en perdait : en relançant, des doublons."""
        unites = [f"nc-test{i}.service" for i in range(12)]
        for _ in range(2):
            ps = [self.lancer_fond("signaler", u) for u in unites]
            for p in ps:
                self.assertEqual(p.wait(20), 0)
        n = self.notifs()
        self.assertEqual(len(n), 1, "une seule notification, et aucune la seconde fois")
        self.assertIn("12 services en panne", n[0])
        self.assertIn("redemarrer=Redémarrer tout", n[0])
        self.assertIn("• et 6 autre(s)", n[0][-1])
        self.assertEqual(sorted(json.loads((self.home / "cache/nc/pannes.json").read_text())), sorted(unites))
        expl = next(l for l in self.appels().splitlines() if l.startswith("nc-ia panne"))
        self.assertEqual(sorted(expl.split()[2:-1]), sorted(unites), "« Expliquer » : toutes ensemble")
        self.assertFalse((self.home / "cache/nc/pannes-lot.json").exists())

    def test_redemarrer_tout(self):
        self.choix("redemarrer")
        ps = [self.lancer_fond("signaler", u) for u in ("nc-a.service", "nc-b.service")]
        for p in ps:
            p.wait(20)
        self.assertEqual(self.appels().count("systemctl --user restart"), 2)
        self.assertEqual(self.notifs()[-1][-2:], ["Services repartis", "Île dynamique, Île dynamique"])

    def test_corps_echappe_seulement_si_le_serveur_lit_le_balisage(self):
        self.programme("journalctl", 'echo "erreur <b>gras</b> & co"')
        self.lancer("signaler", "nc-ile.service")
        self.assertIn("erreur <b>gras</b> & co", self.notifs()[-1][-1], "l'île affiche le texte tel quel")
        self.programme("gdbus", "echo \"(['body', 'body-markup', 'actions'],)\"")
        self.lancer("signaler", "nc-dock.service")
        self.assertIn("erreur &lt;b&gt;gras&lt;/b&gt; &amp; co", self.notifs()[-1][-1])

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

    def test_unites_du_bac_jamais_signalees(self):
        """Une question à une IA ou une commande de session de confiance qui échoue n'est pas un service en panne."""
        (self.home / ".config/nc/reglages.conf").write_text("LANGUE=fr\nPANNES=tous\n")
        for u in ("nc-ia-84b7af66c16f.service", "nc-bac-0123456789ab.service", "nc-ia-test-84b7af66c16f.service"):
            self.lancer("signaler", u)
        self.assertFalse(self.notifs())

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

    def test_unites_transitoires_jamais_signalees(self):
        # systemd-run (bac de nc-noeud et des IA, tests) : le drop-in global s'applique aussi, leur échec n'est pas une panne
        (self.home / ".config/nc/reglages.conf").write_text("LANGUE=fr\nPANNES=tous\n")
        self.systemctl()
        for unite in ("run-p1791870-i1789937.service", "nc-ia-test-a1bf71b52bc3.service", "nc-bac-be50fdd76986.service",
                      "nc-ia-84b7af66c16f.service"):
            self.lancer("signaler", unite)
        self.assertFalse(self.notifs())
        # Une unité transitoire au nom quelconque (Transient=yes), ou déjà retirée par --collect (not-found)
        for props in ("Transient=yes\nLoadState=loaded", "Transient=no\nLoadState=not-found"):
            self.programme("systemctl", 'echo "systemctl $*" >> "$JOURNAL"; case "$*" in *Transient*) printf "' + props.replace("\n", "\\n")
                           + '\\n";; *is-system-running*) echo running;; *is-active*) echo active;; esac')
            self.lancer("signaler", "quelconque.service")
        self.assertFalse(self.notifs())
        # Un vrai service du bureau l'est toujours
        self.systemctl()
        self.lancer("signaler", "nc-ile.service")
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
            r = subprocess.run(["bash", str(REPO / "home/.local/bin/nc-maj"), "verifier"],
                               env=dict(os.environ, HOME=str(home), XDG_CACHE_HOME=str(home / ".cache")),
                               capture_output=True, text=True, timeout=60)
            self.assertEqual(r.returncode, 0, r.stderr)


class VersionParTelegram(unittest.TestCase):
    """Une nouvelle version de noctalia-config est aussi annoncée par Telegram (nc-alertes version), avant la
    notification du bureau (qui attend un clic) ; pas partie, elle est retentée au passage suivant."""
    def test_annonce_retentee_jusqu_a_ce_qu_elle_parte(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            origine, depot, home, faux = d / "origine.git", d / "depot", d / "home", d / "faux"
            for x in (home / ".config/nc", home / ".local/bin", faux):
                x.mkdir(parents=True)
            run = lambda *a, **k: subprocess.run(list(a), capture_output=True, check=True, **k)
            run("git", "init", "-q", "--bare", "-b", "main", str(origine))
            run("git", "clone", "-q", str(origine), str(depot))
            g = lambda *a: run("git", "-C", str(depot), "-c", "user.email=t@t", "-c", "user.name=t", *a)
            g("checkout", "-q", "-b", "main"); g("commit", "-q", "--allow-empty", "-m", "départ"); g("push", "-q", "origin", "main")
            g("commit", "-q", "--allow-empty", "-m", "Nouvelle pastille ; détails"); g("push", "-q", "origin", "main")
            g("reset", "-q", "--hard", "HEAD~1")
            (home / ".config/nc/depot").write_text(str(depot))
            alertes = home / ".local/bin/nc-alertes"
            alertes.write_text('#!/bin/sh\necho "$*" >> "$HOME/alertes"; exit "$(cat "$HOME/code" 2>/dev/null || echo 0)"\n')
            alertes.chmod(0o755)
            (faux / "notify-send").write_text('#!/bin/sh\necho "$*" >> "$HOME/notifs"\n'); (faux / "notify-send").chmod(0o755)
            env = dict(os.environ, HOME=str(home), PATH=f"{faux}:/usr/bin:/bin", NC_LANGUE="fr",
                       XDG_CACHE_HOME=str(home / ".cache"), XDG_CONFIG_HOME=str(home / ".config"))   # jamais le vrai cache
            verifier = lambda: subprocess.run(["bash", str(REPO / "home/.local/bin/nc-maj"), "verifier"], env=env,
                                              capture_output=True, text=True, timeout=60)
            lire = lambda n: (home / n).read_text() if (home / n).exists() else ""
            (home / "code").write_text("2")                       # JARVIS injoignable
            self.assertEqual(verifier().returncode, 0)
            self.assertEqual(lire("alertes").count("version Nouvelle pastille"), 1, "le résumé des nouveautés")
            self.assertEqual(lire("notifs").count("Nouvelle version de la config"), 1)
            verifier()
            self.assertEqual(lire("alertes").count("version"), 2, "pas partie : retentée au passage suivant")
            self.assertEqual(lire("notifs").count("Nouvelle version de la config"), 1, "le bureau ne l'annonce qu'une fois")
            (home / "code").write_text("0")                       # partie
            verifier(); verifier()
            self.assertEqual(lire("alertes").count("version"), 3, "partie : plus rappelée")
            (home / ".config/nc/reglages.conf").write_text("MAJ_VERIFIER=non\n")
            (home / ".cache/nc/maj-telegram").unlink()
            verifier()
            self.assertEqual(lire("alertes").count("version"), 3, "MAJ_VERIFIER=non : rien")
            # Revue MAJ-02 : JARVIS lent ou injoignable ne retarde pas la notification du bureau
            (home / ".config/nc/reglages.conf").unlink()
            for f in (".cache/nc/maj-telegram", ".cache/nc/maj-annoncee"):
                (home / f).unlink(missing_ok=True)
            alertes.write_text('#!/bin/sh\nsleep 4; echo "$*" >> "$HOME/alertes"\n')
            (faux / "notify-send").write_text('#!/bin/sh\ndate +%s.%N >> "$HOME/heure-notif"\n')
            import time
            debut = time.time()
            self.assertEqual(verifier().returncode, 0)
            self.assertLess(float(lire("heure-notif").split()[-1]) - debut, 2.5, "la notification part sans attendre Telegram")
            self.assertTrue((home / ".cache/nc/maj-telegram").exists(), "et Telegram a quand même fini (wait)")

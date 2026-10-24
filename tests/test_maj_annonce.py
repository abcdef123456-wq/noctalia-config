"""Une notification à boutons ne retient jamais un service. Régression : nc-maj verifier (nc-maj-verif.service,
Type=oneshot) restait « activating » des heures sur un notify-send -t 0 -A sans fin, et le minuteur ne repartait plus.
- nc-maj verifier rend la main vite, avec un notify-send qui ne répond jamais ; l'annonce part dans une unité à part
  (faux systemd-run qui note ses arguments) ;
- systemd-run échoue : repli au premier plan, avec un délai (timeout) ;
- les unités oneshot ont TimeoutStartSec ;
- test statique : pas de notify-send à bouton sans délai ni détachement dans un script (liste d'exceptions motivées).
Vrais dépôts git dans un dossier temporaire, faux programmes, HOME isolé ; aucune vraie notification ni unité."""
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time
import unittest

REPO = Path(__file__).resolve().parents[1]
NC_MAJ = REPO / "home/.local/bin/nc-maj"
BIN = REPO / "home/.local/bin"
UNITES = REPO / "home/.config/systemd/user"


class Annonce(unittest.TestCase):
    def setUp(self):
        d = tempfile.TemporaryDirectory(prefix="nc-maj-annonce-")
        self.addCleanup(d.cleanup)
        self.d = Path(d.name)
        self.home = self.d / "home"
        (self.home / ".config/nc").mkdir(parents=True)
        self.faux = self.d / "faux"
        self.faux.mkdir()
        self.journal = self.d / "journal"
        reel = shutil.which("timeout")
        # notify-send ne rend jamais la main (comme un clic qui n'arrive pas)
        self.script("notify-send", 'echo "notify-send $*" >> "$J"; exec sleep 300')
        # timeout : « 6h » devient 2 s (le reste passe tel quel)
        self.script("timeout", 'echo "timeout $*" >> "$J"; d="$1"; shift; [ "$d" = 6h ] && d=2; exec %s "$d" "$@"' % reel)
        self.sr_code = 0
        env = dict(os.environ, HOME=str(self.home), XDG_CACHE_HOME=str(self.home / ".cache"),
                   XDG_CONFIG_HOME=str(self.home / ".config"), NC_LANGUE="fr", J=str(self.journal),
                   PATH=f"{self.faux}:{os.environ['PATH']}", GIT_AUTHOR_NAME="T", GIT_AUTHOR_EMAIL="t@exemple.invalid",
                   GIT_COMMITTER_NAME="T", GIT_COMMITTER_EMAIL="t@exemple.invalid")
        for v in ("HYPRLAND_INSTANCE_SIGNATURE", "GIT_SSH_COMMAND", "GIT_SSH", "GIT_CONFIG_GLOBAL", "GIT_CONFIG_SYSTEM"):
            env.pop(v, None)
        self.env = env
        amont, auteur, ami = self.d / "amont.git", self.d / "auteur", self.d / "ami"
        self.git("init", "-q", "--bare", "-b", "main", str(amont))
        self.git("clone", "-q", str(amont), str(auteur))
        self.git("-C", str(auteur), "checkout", "-q", "-b", "main")
        self.commit(auteur, "Départ")
        self.git("-C", str(auteur), "push", "-q", "origin", "main")
        self.git("clone", "-q", str(amont), str(ami))
        self.commit(auteur, "Nouveauté visible")
        self.git("-C", str(auteur), "push", "-q", "origin", "main")
        (self.home / ".config/nc/depot").write_text(str(ami))

    def script(self, nom, corps):
        p = self.faux / nom
        p.write_text("#!/bin/sh\n" + corps + "\n")
        p.chmod(0o755)

    def git(self, *a):
        subprocess.run(["git", *a], env=self.env, capture_output=True, text=True, check=True)

    def commit(self, depot, sujet):
        (depot / "f").write_text(sujet)
        self.git("-C", str(depot), "add", "f")
        self.git("-C", str(depot), "commit", "-q", "-m", sujet)

    def lignes(self):
        return self.journal.read_text().splitlines() if self.journal.exists() else []

    def test_annonce_a_part_et_service_libre(self):
        self.script("systemd-run", 'echo "systemd-run $*" >> "$J"; exit 0')
        t0 = time.monotonic()
        r = subprocess.run(["bash", str(NC_MAJ), "verifier"], env=self.env, capture_output=True, text=True, timeout=30)
        self.assertLess(time.monotonic() - t0, 15, "verifier ne doit pas attendre le clic")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        sr = [l for l in self.lignes() if l.startswith("systemd-run ")]
        self.assertEqual(len(sr), 1, self.lignes())
        self.assertIn("--user", sr[0])
        self.assertIn("--collect", sr[0])
        self.assertIn("OnFailure=", sr[0])
        self.assertIn("RuntimeMaxSec=", sr[0])
        self.assertIn("--expand-environment=no", sr[0], "le texte des commits ne passe pas par les variables de systemd")
        self.assertRegex(sr[0], r"--unit=nc-maj-annonce-[0-9a-f]{8,}\b")
        self.assertRegex(sr[0], r" -- /\S*nc-maj annoncer ")
        self.assertFalse([l for l in self.lignes() if l.startswith("notify-send ")], "la notification part à part")
        # l'annonce est notée : pas de répétition
        self.assertTrue((self.home / ".cache/nc/maj-annoncee").read_text().strip())
        self.journal.unlink()
        subprocess.run(["bash", str(NC_MAJ), "verifier"], env=self.env, capture_output=True, text=True, timeout=30)
        self.assertEqual([l for l in self.lignes() if l.startswith(("systemd-run", "notify-send"))], [],
                         "déjà annoncée : rien de plus")

    def test_repli_au_premier_plan_avec_delai(self):
        self.script("systemd-run", 'echo "systemd-run $*" >> "$J"; exit 1')
        t0 = time.monotonic()
        r = subprocess.run(["bash", str(NC_MAJ), "verifier"], env=self.env, capture_output=True, text=True, timeout=30)
        self.assertLess(time.monotonic() - t0, 20)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        j = self.lignes()
        self.assertTrue(any(l.startswith("notify-send ") and "-A maj=" in l for l in j), j)
        self.assertTrue(any(l.startswith("timeout 6h") and "annoncer" in l for l in j), j)

    def test_sans_systemd_run_meme_repli(self):
        # PATH sans systemd-run : le repli est le même
        self.script("systemd-run", "exit 127")
        r = subprocess.run(["bash", str(NC_MAJ), "verifier"], env=self.env, capture_output=True, text=True, timeout=30)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertTrue([l for l in self.lignes() if l.startswith("notify-send ")])


class Unites(unittest.TestCase):
    def test_maj_verif_a_un_delai(self):
        s = (UNITES / "nc-maj-verif.service").read_text()
        self.assertRegex(s, r"(?m)^TimeoutStartSec=\S+")

    def test_chaque_oneshot_a_un_delai(self):
        n = 0
        for f in sorted(UNITES.glob("*.service")):
            s = f.read_text()
            if re.search(r"(?m)^Type=oneshot", s):
                n += 1
                self.assertRegex(s, r"(?m)^TimeoutStartSec=\S+", f.name)
        self.assertGreaterEqual(n, 5)

    def test_unite_annonce_transitoire_pour_nc_panne(self):
        s = (BIN / "nc-panne").read_text()
        m = re.search(r"^TRANSITOIRE = re\.compile\((.*)\)$", s, re.M)
        self.assertIn("nc-maj-annonce", m.group(1))


# Scripts où un notify-send à bouton peut rester sans délai ni détachement visible, et pourquoi c'est sans danger
EXCEPTIONS = {
    "nc-gpu-mode": "lancé à la main ou par un raccourci, jamais par un service : l'utilisateur est devant",
    "nc-noeud": "démon (Type=simple) : l'attente d'un bouton est son travail, un fil par demande",
    "nc-claude": "crochet lancé par Claude Code, notify-send en Popen (-p) suivi par un fil ; pas un service systemd",
    "nc-ia": "attente détachée (start_new_session) et bornée par ATTENTE_CLIC",
    "nc-profile-sync": "démon (Type=simple), sous-shell en fond, notification qui expire (-t 15000)",
}
BORNE = re.compile(r"\btimeout\b|systemd-run|start_new_session|-t [1-9][0-9]*\b")


class Statique(unittest.TestCase):
    def test_pas_de_bouton_sans_delai(self):
        fautes = []
        for f in sorted(BIN.iterdir()):
            if not f.is_file() or f.name in EXCEPTIONS:
                continue
            try:
                lignes = f.read_text().splitlines()
            except (UnicodeDecodeError, OSError):
                continue
            for i, l in enumerate(lignes):
                if "notify-send" not in l or l.lstrip().startswith("#"):
                    continue
                fenetre = "\n".join(lignes[max(0, i - 1):i + 14])
                if not re.search(r'(?<![\w-])-A\b|--action', fenetre):
                    continue
                if not BORNE.search(fenetre):
                    fautes.append(f"{f.name}:{i + 1}: {l.strip()[:100]}")
        self.assertEqual(fautes, [], "notify-send à bouton sans délai ni détachement")

    def test_exceptions_existent(self):
        for nom in EXCEPTIONS:
            self.assertTrue((BIN / nom).exists(), nom)


if __name__ == "__main__":
    unittest.main()

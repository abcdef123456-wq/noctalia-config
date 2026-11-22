"""nc-capture epingler : copie 0600 dans un dossier 0700 de XDG_RUNTIME_DIR, original intact, refus des formats autres
que PNG et JPEG, bouton « Épingler » de la notification ; fenêtre CaptureEpinglee.qml (borne 40 %, Échap, effacement
à la fermeture), règle Hyprland précise, ménage au démarrage. Faux grim, slurp, notify-send et qs dans un HOME temporaire."""
import re
import shutil
import stat
import subprocess
import time
import unittest
from pathlib import Path

from tests import _isolation  # noqa: F401
from tests.test_captures_e4 import BIN, REPO, Base

QML = REPO / "home/.config/quickshell/nc-ile"
PNG = b"\x89PNG\r\n\x1a\n" + b"\0" * 40
JPG = b"\xff\xd8\xff\xe0" + b"\0" * 40


class Epingler(Base):
    def setUp(self):
        super().setUp()
        (self.home / "run").mkdir()
        self.faux_prog("grim", 'for a; do f="$a"; done; printf "\\211PNG\\r\\n\\032\\n" > "$f"; echo x >> "$f"')
        self.faux_prog("slurp", 'printf "%s\\n" "10,10 100x100"')
        self.faux_prog("notify-send", 'printf "%s\\n" "notif $*" >> "$JOURNAL"; case "$*" in *-A*) echo "$CHOIX" ;; esac')
        self.faux_prog("qs", 'printf "%s\\n" "qs $*" >> "$JOURNAL"; exit "${CODE_QS:-0}"')
        self.faux_prog("hyprctl", "echo '[]'")
        self.faux_prog("jq", "exit 0")
        self.faux_prog("xdg-user-dir", 'echo "$HOME/Pictures"')
        self.dossier = self.home / "run/nc-epingles"

    def lancer(self, *args, **env):
        return subprocess.run([shutil.which("bash"), str(BIN / "nc-capture"), "epingler", *args], capture_output=True,
                              text=True, timeout=20, env=self.env(**env), stdin=subprocess.DEVNULL)

    def copies(self):
        return sorted(self.dossier.iterdir()) if self.dossier.exists() else []

    def test_copie_privee_et_original_intact(self):
        for nom, octets, ext in (("a.png", PNG, ".png"), ("b.jpg", JPG, ".jpg")):
            src = self.home / nom
            src.write_bytes(octets)
            src.chmod(0o644)
            with self.subTest(nom=nom):
                r = self.lancer(str(src))
                self.assertEqual(r.returncode, 0, r.stderr)
                copie = Path(r.stdout.strip())
                self.assertEqual(copie.parent, self.dossier)
                self.assertTrue(re.fullmatch(r"[A-Za-z0-9]{10}" + re.escape(ext), copie.name), copie.name)
                self.assertEqual(stat.S_IMODE(copie.stat().st_mode), 0o600)
                self.assertEqual(stat.S_IMODE(self.dossier.stat().st_mode), 0o700)
                self.assertEqual(copie.read_bytes(), octets)
                self.assertEqual(src.read_bytes(), octets)
                self.assertIn("ipc call ile epingler " + str(copie), self.journal.read_text())

    def test_zone_choisie_avec_slurp_et_grim(self):
        r = self.lancer()
        self.assertEqual(r.returncode, 0, r.stderr)
        copie = Path(r.stdout.strip())
        self.assertEqual(copie.parent, self.dossier)
        self.assertEqual(stat.S_IMODE(copie.stat().st_mode), 0o600)
        self.assertTrue(copie.read_bytes().startswith(b"\x89PNG"))
        self.assertFalse((self.home / "Pictures").exists())

    def test_formats_refuses(self):
        (self.home / "lien.png").symlink_to(self.home / "absent")
        for nom, octets in (("a.svg", b"<svg xmlns='http://www.w3.org/2000/svg'/>"), ("b.png", b"texte simple"),
                            ("c.txt", b"https://exemple.org/x.png"), ("d.gif", b"GIF89a\x01\x00"), ("e.png", b"")):
            (self.home / nom).write_bytes(octets)
        (self.home / "vrai.png").write_bytes(PNG)
        (self.home / "lien2.png").symlink_to(self.home / "vrai.png")
        for nom in ("a.svg", "b.png", "c.txt", "d.gif", "e.png", "lien.png", "lien2.png", "absent"):
            with self.subTest(nom=nom):
                self.assertNotEqual(self.lancer(str(self.home / nom)).returncode, 0)
        self.assertNotEqual(self.lancer("https://exemple.org/x.png").returncode, 0)
        self.assertEqual(self.copies(), [])
        self.assertNotIn("epingler", self.journal.read_text())

    def test_sans_dossier_d_execution(self):
        (self.home / "a.png").write_bytes(PNG)
        env = self.env()
        del env["XDG_RUNTIME_DIR"]
        r = subprocess.run([shutil.which("bash"), str(BIN / "nc-capture"), "epingler", str(self.home / "a.png")],
                           capture_output=True, text=True, timeout=20, env=env, stdin=subprocess.DEVNULL)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("XDG_RUNTIME_DIR", r.stderr)
        self.assertEqual(self.copies(), [])

    def test_ile_absente_efface_la_copie(self):
        (self.home / "a.png").write_bytes(PNG)
        r = self.lancer(str(self.home / "a.png"), CODE_QS="1")
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual(self.copies(), [])
        self.assertTrue((self.home / "a.png").exists())

    def test_bouton_epingler_dans_la_notification(self):
        (self.home / ".config/nc/reglages.conf").write_text("LANGUE=fr\nCAPTURES_COPIER=non\n")
        self.faux_prog("wl-copy", "exit 0")
        r = subprocess.run([shutil.which("bash"), str(BIN / "nc-capture"), "ecran"], capture_output=True, text=True,
                           timeout=20, env=self.env(CHOIX="epingler"), stdin=subprocess.DEVNULL)
        self.assertEqual(r.returncode, 0, r.stderr)
        for _ in range(50):   # la notification part en arrière-plan
            j = self.journal.read_text()
            if "ipc call ile epingler" in j:
                break
            time.sleep(0.1)
        self.assertIn("epingler=Épingler", j)
        # L'action choisie a copié la capture dans nc-epingles et appelé l'île
        self.assertEqual(len(self.copies()), 1)
        self.assertIn("ipc call ile epingler", j)


class Sources(unittest.TestCase):
    def test_fenetre_bornee_et_fermeture(self):
        q = (QML / "CaptureEpinglee.qml").read_text()
        self.assertEqual(len(re.findall(r"0\.4 \* ce\.", q)), 2)  # largeur ET hauteur
        self.assertIn("Keys.onEscapePressed", q)
        self.assertIn("RightButton", q)
        self.assertNotIn("component ", q)

    def test_aucun_component_ajoute(self):
        s = (QML / "shell.qml").read_text()
        # Valeurs de départ (avant l'épinglage) : aucun component inline, deux Component.onCompleted (objets différents)
        self.assertEqual(len(re.findall(r"^\s*component\s", s, re.M)), 0)
        self.assertEqual(s.count("Component.onCompleted"), 2)

    def test_efface_a_la_fermeture_et_au_demarrage(self):
        s = (QML / "shell.qml").read_text()
        self.assertRegex(s, r"onFermer:[^\n]*\n?[^\n]*effacerEpingles\(\"\"\)")
        self.assertRegex(s, r"Component\.onCompleted:\s*\{[^}]*effacerEpingles\(\"\"\)")
        self.assertIn("-delete", s)
        self.assertIn("function epingler(chemin: string): void", s)

    def test_regle_hyprland_precise(self):
        r = (REPO / "home/.config/hypr/nc/regles.lua").read_text()
        m = re.search(r'name = "nc-epingle-fenetre".*?\}\)', r, re.S)
        self.assertTrue(m)
        self.assertIn('class = "^(org.quickshell)$"', m.group(0))
        self.assertIn("Capture épinglée", m.group(0))


if __name__ == "__main__":
    unittest.main()

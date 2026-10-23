"""export.sh reconstruit home/ depuis la seule liste HOME_FILES : un fichier de home/ qui n'y est pas serait supprimé
du dépôt au prochain export (revue EXP-01 : nc-ia, nc-session et 11 autres l'étaient)."""
from pathlib import Path
import os
import re
import shutil
import subprocess
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]


class Export(unittest.TestCase):
    def test_tout_home_est_dans_home_files(self):
        liste = re.search(r"HOME_FILES=\((.*?)\n\)", (REPO / "export.sh").read_text(), re.S)[1].split()
        r = subprocess.run(["git", "-C", str(REPO), "ls-files", "-z", "--cached", "--others", "--exclude-standard", "home"],
                           capture_output=True, text=True)
        if r.returncode != 0:
            self.skipTest("pas un dépôt git")
        couvert = lambda f: any(f == e or f.startswith(e.rstrip("/") + "/") for e in liste)
        manque = [f[5:] for f in r.stdout.split("\0") if f and not couvert(f[5:])]
        self.assertEqual(manque, [], "à ajouter à HOME_FILES dans export.sh")


class ExportIsole(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="nc-export-")
        self.addCleanup(self.tmp.cleanup)
        self.racine = Path(self.tmp.name)
        self.depot, self.home, self.bin = [self.racine / n for n in ("depot", "utilisateur", "bin")]
        for p in (self.depot, self.home, self.bin):
            p.mkdir()
        self.env = dict(HOME=str(self.home), PATH=str(self.bin), NC_LANGUE="fr", LC_ALL="C",
                        GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1")
        for nom in ("bash", "dirname", "mkdir", "mktemp", "find", "rm", "grep", "sed", "cp", "mv", "id", "git", "jq", "python3"):
            outil = shutil.which(nom)
            if not outil:
                self.skipTest(nom + " requis")
            (self.bin / nom).symlink_to(outil)
        # Le vrai Hyprland n'est jamais joint, même si la session de l'utilisateur est disponible.
        h = self.bin / "hyprctl"
        h.write_text('#!/bin/sh\nprintf "[]\\n"\n')
        h.chmod(0o755)
        shutil.copy2(REPO / "export.sh", self.depot / "export.sh")
        (self.depot / "system").mkdir()
        fichiers = {
            ".config/hypr/nc/clavier.lua": 'kb_layout = "fr"\nkb_options = ""\n',
            ".config/noctalia/config.toml": 'center = []\n[lockscreen_widgets]\ncx = 800\ncy = 300\n[plugins]\nenabled = []\n',
            ".local/share/noctalia/plugins/nc-launcher/panel.luau": 'local navigateur = "firefox-developer-edition"\n',
            ".config/qt6ct/qt6ct.conf": 'style=Fusion\nicon_theme=Papirus\n',
            ".local/bin/nc-dictee": '#!/bin/sh\necho version-depot\n',
        }
        for rel, texte in fichiers.items():
            for base in (self.home, self.depot / "home"):
                p = base / rel
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(texte)
        p = self.depot / "home/.local/bin/nc-ia"
        p.write_text('#!/bin/sh\necho nouveau-composant\n')
        p.chmod(0o755)
        qml = self.depot / "home/.config/quickshell/nc-ile/Nouveau.qml"
        qml.parent.mkdir(parents=True)
        qml.write_text('import QtQuick\nItem {}\n')
        for a in (("init", "-q"), ("add", "home"),
                  ("-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "-qm", "base")):
            subprocess.run(["git", "-C", str(self.depot), *a], env=self.env, capture_output=True, check=True)

    def exporter(self, *a):
        return subprocess.run([str(self.depot / "export.sh"), *a], env=self.env,
                              capture_output=True, text=True, timeout=20)

    def test_absents_du_pc_gardes_et_fichiers_installes_exportes(self):
        (self.home / ".local/bin/nc-dictee").write_text('#!/bin/sh\necho version-installee\n')
        r = self.exporter()
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        home = self.depot / "home"
        self.assertTrue((home / ".local/bin/nc-ia").exists(), "un composant non installé n'est pas supprimé du dépôt")
        self.assertTrue((home / ".config/quickshell/nc-ile/Nouveau.qml").exists())
        self.assertEqual((home / ".local/bin/nc-ia").stat().st_mode & 0o777, 0o755)
        self.assertIn("version-installee", (home / ".local/bin/nc-dictee").read_text())

    def test_nouveau_fichier_d_un_dossier_installe_garde(self):
        qml = self.home / ".config/quickshell/nc-ile"
        qml.mkdir(parents=True)
        (qml / "Ancien.qml").write_text('import QtQuick\nItem { width: 12 }\n')
        r = self.exporter()
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        resultat = self.depot / "home/.config/quickshell/nc-ile"
        self.assertTrue((resultat / "Nouveau.qml").exists(), "un ancien dossier installé n'efface pas les ajouts du dépôt")
        self.assertTrue((resultat / "Ancien.qml").exists())

    def test_preview_ne_remplace_pas_le_depot(self):
        avant = (self.depot / "home/.local/bin/nc-dictee").read_bytes()
        (self.home / ".local/bin/nc-dictee").write_text('#!/bin/sh\necho version-installee\n')
        r = self.exporter("--preview")
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        self.assertEqual((self.depot / "home/.local/bin/nc-dictee").read_bytes(), avant)
        self.assertFalse(list(self.depot.glob(".nc-export.*")))

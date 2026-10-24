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

    def test_dossier_installe_en_lien_symbolique(self):
        """A3-R2 : ~/.config/nvim lien vers un dossier faisait « type incompatible » et arrêtait tout l'export. Son
        contenu est publié, jamais le lien (sa cible contient le chemin du dossier personnel)."""
        (self.depot / "home/.config/nvim").mkdir(parents=True)
        (self.depot / "home/.config/nvim/depot.lua").write_text("-- seulement dans le dépôt\n")
        subprocess.run(["git", "-C", str(self.depot), "add", "home"], env=self.env, capture_output=True, check=True)
        subprocess.run(["git", "-C", str(self.depot), "-c", "user.name=Test", "-c", "user.email=test@example.invalid",
                        "commit", "-qm", "nvim"], env=self.env, capture_output=True, check=True)
        ailleurs = self.home / "ailleurs/nvim"
        (ailleurs / "lua").mkdir(parents=True)
        (ailleurs / "init.lua").write_text("vim.o.number = true\n")
        (ailleurs / "lua/reglages.lua").write_text("return {}\n")
        (self.home / ".config/nvim").symlink_to(ailleurs)
        (self.home / "ailleurs/p10k.zsh").write_text("# p10k\n")
        (self.home / ".p10k.zsh").symlink_to(self.home / "ailleurs/p10k.zsh")
        r = self.exporter()
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        nvim = self.depot / "home/.config/nvim"
        self.assertFalse(nvim.is_symlink(), "le lien lui-même n'est jamais publié")
        self.assertTrue(nvim.is_dir())
        self.assertEqual((nvim / "init.lua").read_text(), "vim.o.number = true\n")
        self.assertTrue((nvim / "lua/reglages.lua").exists())
        self.assertTrue((nvim / "depot.lua").exists(), "les fichiers du dépôt pas encore installés restent")
        p10k = self.depot / "home/.p10k.zsh"
        self.assertFalse(p10k.is_symlink(), "un lien vers un fichier : le fichier est publié")
        self.assertEqual(p10k.read_text(), "# p10k\n")

    def test_fichier_contre_dossier_refuse(self):
        (self.home / ".config/quickshell/nc-ile").parent.mkdir(parents=True)
        (self.home / ".config/quickshell/nc-ile").write_text("pas un dossier\n")
        r = self.exporter("--preview")
        self.assertEqual(r.returncode, 1)
        self.assertIn("type incompatible", r.stderr)
        self.assertFalse(list(self.depot.glob(".nc-export.*")))

    ZSHRC = '# géré par le dépôt\nexport EDITOR=nvim\n[[ -r ~/.zshrc.perso ]] && source ~/.zshrc.perso\n'

    def zshrc_ajoute(self):
        """Le .zshrc du dépôt, et dans ~ le même avec une ligne d'un installateur tiers (chemin du dossier perso)."""
        (self.depot / "home/.zshrc").write_text(self.ZSHRC)
        for a in (("add", "home"), ("-c", "user.name=Test", "-c", "user.email=test@example.invalid",
                                    "commit", "-qm", "zshrc")):
            subprocess.run(["git", "-C", str(self.depot), *a], env=self.env, capture_output=True, check=True)
        installe = self.ZSHRC + f'export PATH="{self.home}/.tiers/bin:$PATH"\n'
        (self.home / ".zshrc").write_text(installe)
        return installe

    def test_zshrc_ajouts_tiers_pas_publies(self):
        """~/.zshrc reçoit des lignes d'installateurs tiers : l'export garde le .zshrc du dépôt, montre l'écart et ne
        modifie pas ~/.zshrc."""
        installe = self.zshrc_ajoute()
        for a in (("--preview",), ()):
            r = self.exporter(*a)
            self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
            self.assertEqual((self.depot / "home/.zshrc").read_text(), self.ZSHRC, f"export {a}")
            self.assertEqual((self.home / ".zshrc").read_text(), installe, "~/.zshrc n'est jamais modifié")
            self.assertIn("~/.zshrc diffère du dépôt", r.stderr)
            self.assertIn('+export PATH="@HOME@/.tiers/bin:$PATH"', r.stderr, "l'écart, après normalisation")
            self.assertIn("~/.zshrc.perso", r.stderr)
            self.assertNotIn(".zshrc", r.stdout.replace("gardé depuis le dépôt", ""), "pas de diff du .zshrc")
        etat = subprocess.run(["git", "-C", str(self.depot), "status", "--porcelain", "--", "home/.zshrc"],
                              env=self.env, capture_output=True, text=True, check=True).stdout
        self.assertEqual(etat, "")

    def test_zshrc_identique_apres_normalisation_sans_avertissement(self):
        (self.depot / "home/.zshrc").write_text(self.ZSHRC + 'export PATH="@HOME@/.local/bin:$PATH"\n')
        (self.home / ".zshrc").write_text(self.ZSHRC + f'export PATH="{self.home}/.local/bin:$PATH"\n')
        r = self.exporter("--preview")
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        self.assertNotIn("diffère", r.stderr)


class ExportDepotReel(unittest.TestCase):
    """A3-R1 : les substitutions d'export.sh s'appliquent aussi aux fichiers du dépôt (gardés quand ~ ne les a pas).
    Elles doivent être sans effet sur un fichier qui a déjà ses repères : sinon « @PLUGIN_ILE@@PLUGIN_ILE@] »."""

    def test_home_vide_aucune_difference(self):
        r = subprocess.run(["git", "-C", str(REPO), "ls-files", "-z", "--", "home", "export.sh"],
                           capture_output=True, text=True)
        if r.returncode != 0:
            self.skipTest("pas un dépôt git")
        tmp = tempfile.TemporaryDirectory(prefix="nc-export-reel-")
        self.addCleanup(tmp.cleanup)
        racine = Path(tmp.name)
        depot, home, binaires = racine / "depot", racine / "utilisateur", racine / "bin"
        for p in (depot, home, binaires):
            p.mkdir()
        for rel in filter(None, r.stdout.split("\0")):
            src = REPO / rel
            if not src.exists() and not src.is_symlink():
                continue                                   # supprimé mais pas encore commité
            (depot / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, depot / rel, follow_symlinks=False)
        for nom in ("bash", "dirname", "mkdir", "mktemp", "find", "rm", "grep", "sed", "cp", "mv", "id", "git", "jq", "python3"):
            outil = shutil.which(nom)
            if not outil:
                self.skipTest(nom + " requis")
            (binaires / nom).symlink_to(outil)
        h = binaires / "hyprctl"
        h.write_text('#!/bin/sh\nprintf "[]\\n"\n')
        h.chmod(0o755)
        env = dict(HOME=str(home), PATH=str(binaires), NC_LANGUE="fr", LC_ALL="C",
                   GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1")
        for a in (("init", "-q"), ("add", "home"),
                  ("-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "-qm", "base")):
            subprocess.run(["git", "-C", str(depot), *a], env=env, capture_output=True, check=True)
        e = subprocess.run([str(depot / "export.sh"), "--preview"], env=env, capture_output=True, text=True, timeout=120)
        self.assertEqual(e.returncode, 0, e.stderr[-2000:])
        self.assertNotIn("diff --git", e.stdout, e.stdout[e.stdout.find("diff --git"):][:4000])
        self.assertNotIn("Only in", e.stdout)
        # Puis un vrai export : le dépôt ne change pas (substitutions appliquées deux fois = même résultat)
        e = subprocess.run([str(depot / "export.sh")], env=env, capture_output=True, text=True, timeout=120)
        self.assertEqual(e.returncode, 0, e.stderr[-2000:])
        etat = subprocess.run(["git", "-C", str(depot), "status", "--porcelain", "--", "home"], env=env,
                              capture_output=True, text=True, check=True).stdout
        self.assertEqual(etat, "")

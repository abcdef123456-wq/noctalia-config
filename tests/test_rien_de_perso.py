"""Le dépôt est public : aucun fichier suivi ne contient d'information personnelle (dossier personnel, nom ou adresse
de la configuration git, adresse de messagerie, vraie clé ou jeton) ni de dossier de travail (.claude/, *.tmp).
Le nom, l'adresse et le dossier sont lus sur la machine qui lance le test : rien de personnel n'est écrit ici."""
import os
from pathlib import Path
import re
import subprocess
import unittest

REPO = Path(__file__).resolve().parents[1]
ICI = Path(__file__).resolve()
CHEMINS_PERMIS = {"user", "pi", "nom", "toi", "moi", "utilisateur"}
MESSAGERIES = r"(gmail|googlemail|outlook|hotmail|live|yahoo|icloud|me|proton|protonmail|laposte|orange|free|sfr|wanadoo|gmx)\.[a-z.]{2,6}"
# Un dossier personnel, suivi ou non d'une barre : « /home/<nom>/… », mais aussi « PATH=$PATH:/home/<nom> » ou
# « "/home/<nom>" », comme les écrivent des installateurs tiers dans ~/.zshrc.
CHEMIN = re.compile(r"/home/([a-z_][a-z0-9_-]*(?:\.[a-z0-9_-]+)*)")
CLES = re.compile(r"sk-ant-[A-Za-z0-9_-]{30,}|AIza[0-9A-Za-z_-]{35}|gh[pousr]_[A-Za-z0-9]{36}|\b\d{8,10}:[A-Za-z0-9_-]{35}\b")


def suivis():
    sortie = subprocess.run(["git", "-C", str(REPO), "ls-files", "-z"], capture_output=True, check=True).stdout
    return [REPO / p for p in sortie.decode().split("\0") if p]


def texte(f):
    try:
        b = f.read_bytes()
    except OSError:
        return None
    return None if b"\0" in b[:8192] else b.decode("utf-8", "replace")


def git_config(cle):
    r = subprocess.run(["git", "-C", str(REPO), "config", cle], capture_output=True, text=True)
    return r.stdout.strip()


class RienDePerso(unittest.TestCase):
    def test_aucun_dossier_de_travail_suivi(self):
        for f in suivis():
            rel = f.relative_to(REPO).as_posix()
            self.assertFalse(rel.startswith(".claude/") or rel.endswith(".tmp"), rel)

    def test_aucune_information_personnelle(self):
        perso = {v for v in (git_config("user.name"), git_config("user.email"), str(Path.home())) if len(v) >= 4}
        compte = Path.home().name
        adresse = re.compile(r"[A-Za-z0-9._%+-]+@" + MESSAGERIES + r"\b", re.I)
        for f in suivis():
            if f == ICI:
                continue
            t = texte(f)
            if t is None:
                continue
            rel = f.relative_to(REPO).as_posix()
            for v in perso:
                self.assertNotIn(v, t, f"{rel} : information de cette machine (nom, adresse ou dossier personnels)")
            for m in CHEMIN.finditer(t):
                self.assertTrue(m[1] in CHEMINS_PERMIS and m[1] != compte, f"{rel} : chemin personnel {m[0]}")
            self.assertIsNone(adresse.search(t), f"{rel} : adresse de messagerie")
            if not rel.startswith("tests/"):
                self.assertIsNone(CLES.search(t), f"{rel} : ressemble à une vraie clé ou un jeton")

    def test_le_test_voit_un_chemin_personnel(self):
        """Le garde-fou marche : un chemin /home/<quelqu'un> serait refusé, avec ou sans barre après le nom, par
        exemple dans les lignes qu'un installateur tiers ajoute à home/.zshrc."""
        racine = "/ho" + "me/"
        for ligne in ("voir " + racine + "marcel/x",
                      'export PATH="' + racine + 'marcel/.local/bin:$PATH"',
                      "export PATH=$PATH:" + racine + "marcel",
                      'export BUN_INSTALL="' + racine + 'jean.dupont"'):
            m = CHEMIN.search(ligne)
            self.assertTrue(m and m[1] not in CHEMINS_PERMIS, ligne)
        self.assertEqual(CHEMIN.search(racine + "marcel.")[1], "marcel", "le point final d'une phrase n'en fait pas partie")
        self.assertIsNone(CHEMIN.search(racine + "<nom>/"), "un repère de la doc n'est pas un nom")


if __name__ == "__main__":
    unittest.main()


class Licence(unittest.TestCase):
    """LICENSE (MIT) : sans nom, pseudo ni adresse ; le README dit ce qui garde une autre licence, et ces fichiers existent."""
    def test_licence_mit_sans_nom_ni_adresse(self):
        t = (REPO / "LICENSE").read_text(encoding="utf-8")
        self.assertTrue(t.startswith("MIT License\n"))
        self.assertIn("\nCopyright (c) 2026 noctalia-config contributors\n", t)
        self.assertNotIn("@", t)
        for cle in ("user.name", "user.email"):
            v = git_config(cle)
            if v:
                self.assertNotIn(v.lower(), t.lower(), cle)
        compte = os.environ.get("USER") or os.environ.get("LOGNAME") or ""
        if len(compte) > 2:
            self.assertNotIn(compte.lower(), t.lower())

    def test_le_readme_liste_le_code_tiers(self):
        r = (REPO / "README.md").read_text(encoding="utf-8")
        self.assertIn("## Licence", r)
        section = r[r.index("## Licence"):]
        self.assertIn("GPLv3", section)
        self.assertIn("unimatrix", (REPO / "home/.local/bin/unimatrix").read_text(encoding="utf-8"))
        self.assertIn("GNU General Public License", (REPO / "home/.local/bin/unimatrix").read_text(encoding="utf-8"))
        for chemin in re.findall(r"^\| `([^`*]+)`", section, re.M):
            self.assertTrue((REPO / chemin.rstrip("/")).exists(), chemin)

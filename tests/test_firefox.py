"""nc-firefox : trouve le profil par défaut (profiles.ini), installe et retire seulement ses fichiers, garde un user.js
à l'utilisateur, écrit les couleurs de l'île ; user.js du dépôt bien formé. HOME isolé, jamais le vrai profil."""
import json
import os
from pathlib import Path
import re
import struct
import subprocess
import tempfile
import unittest
import zipfile

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "home/.local/bin/nc-firefox"
SOURCE = REPO / "home/.local/share/nc/firefox"
PREF = re.compile(r'^user_pref\("([a-zA-Z0-9_.-]+)", (true|false|-?\d+|"[^"]*")\);')


class Firefox(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        self.base = self.home / ".config/mozilla/firefox"
        self.env = dict(os.environ, HOME=str(self.home), XDG_CONFIG_HOME=str(self.home / ".config"), NC_FIREFOX_SOURCE=str(SOURCE))
        self.env.pop("NC_FIREFOX_PROFIL", None)

    def lancer(self, *args):
        return subprocess.run([str(SCRIPT), *args], env=self.env, capture_output=True, text=True, timeout=20)

    def profils(self, ini, *dossiers):
        self.base.mkdir(parents=True)
        for d in dossiers:
            (self.base / d).mkdir()
            (self.base / d / "prefs.js").write_text("")
        (self.base / "profiles.ini").write_text(ini)

    def test_profil_par_defaut(self):
        self.profils("[Install46F]\nDefault=b.dev\nLocked=1\n\n[Profile1]\nName=default\nIsRelative=1\nPath=a.default\nDefault=1\n\n"
                     "[Profile0]\nName=dev\nIsRelative=1\nPath=b.dev\n", "a.default", "b.dev")
        self.assertEqual(self.lancer("profil").stdout.strip(), str(self.base / "b.dev"), "la section Install désigne le profil ouvert")
        self.assertEqual(self.lancer("etat").returncode, 1, "rien d'installé")

    def test_sans_install_puis_default(self):
        self.profils("[Profile0]\nName=x\nIsRelative=1\nPath=x.p\n\n[Profile1]\nName=y\nIsRelative=1\nPath=y.p\nDefault=1\n", "x.p", "y.p")
        self.assertEqual(self.lancer("profil").stdout.strip(), str(self.base / "y.p"))

    def test_aucun_profil(self):
        r = self.lancer("profil")
        self.assertEqual(r.returncode, 1)
        self.assertEqual(self.lancer("installer").returncode, 1, "rien à installer sans profil")

    def test_installer_couleurs_desinstaller(self):
        self.profils("[Profile0]\nName=x\nIsRelative=1\nPath=x.p\nDefault=1\n", "x.p")
        p = self.base / "x.p"
        (p / "user.js").write_text('user_pref("a.moi", true);\n')
        r = self.lancer("installer")
        self.assertEqual(r.returncode, 0, r.stderr)
        for rel in ("user.js", "chrome/userChrome.css", "chrome/userContent.css"):
            self.assertEqual((p / rel).read_text(), (SOURCE / rel).read_text(), rel)
        self.assertEqual((p / "user.js.avant-nc").read_text(), 'user_pref("a.moi", true);\n', "le user.js de l'utilisateur est gardé")
        self.assertEqual(self.lancer("etat").returncode, 0)
        self.assertFalse((p / "chrome/nc-couleurs.css").exists(), "pas de palette : pas de fichier de couleurs")
        (self.home / ".config/nc").mkdir()
        (self.home / ".config/nc/palette-ile.json").write_text(json.dumps({"sombre": False, "fond": "#f1f1f4", "carte": "#e6e6ea",
                                                                            "accent": "#5a3cc8", "texte": "#111", "texteSec": "bidon"}))
        self.assertEqual(self.lancer("couleurs").returncode, 0)
        css = (p / "chrome/nc-couleurs.css").read_text()
        self.assertIn("--nc-couleur-fond: #f1f1f4;", css)
        self.assertIn("--nc-couleur-accent: #5a3cc8;", css)
        self.assertIn("@media (prefers-color-scheme: light)", css, "palette claire : seulement avec un thème Firefox clair")
        self.assertNotIn("bidon", css, "une valeur qui n'est pas une couleur est ignorée")
        self.assertNotIn("#111;", css)
        (p / "chrome/perso.css").write_text("/* à moi */")
        self.assertEqual(self.lancer("desinstaller").returncode, 0)
        for rel in ("chrome/userChrome.css", "chrome/userContent.css", "chrome/nc-couleurs.css", "user.js.avant-nc"):
            self.assertFalse((p / rel).exists(), rel)
        self.assertEqual((p / "user.js").read_text(), 'user_pref("a.moi", true);\n', "l'ancien user.js est remis")
        self.assertTrue((p / "chrome/perso.css").exists(), "un fichier à l'utilisateur n'est pas touché")
        self.assertEqual(self.lancer("etat").returncode, 1)

    def test_extension_et_hote(self):
        self.profils("[Profile0]\nName=x\nIsRelative=1\nPath=x.p\nDefault=1\n", "x.p")
        p = self.base / "x.p"
        (self.home / ".config/nc").mkdir()
        (self.home / ".config/nc/palette-ile.json").write_text(json.dumps({"sombre": True, "fond": "#211c1c", "accent": "#a6a6a6", "bordure": ["#1", "#2"]}))
        r = self.lancer("extension", "installer")
        self.assertEqual(r.returncode, 0, r.stderr)
        xpi = p / "extensions/nc-couleurs@noctalia-config.xpi"
        with zipfile.ZipFile(xpi) as z:
            self.assertEqual(sorted(z.namelist()), ["fond.js", "manifest.json"])
            self.assertEqual(json.loads(z.read("manifest.json"))["browser_specific_settings"]["gecko"]["id"], "nc-couleurs@noctalia-config")
        hote = self.base.parent / "native-messaging-hosts/nc_firefox.json"
        m = json.loads(hote.read_text())
        self.assertEqual((m["name"], m["type"], m["allowed_extensions"]), ("nc_firefox", "stdio", ["nc-couleurs@noctalia-config"]))
        self.assertTrue(m["path"].endswith("/.local/bin/nc-firefox"))
        self.assertFalse((self.home / ".mozilla").exists(), "jamais de ~/.mozilla créé de toutes pièces")
        user = (p / "user.js").read_text()
        self.assertTrue(user.startswith((SOURCE / "user.js").read_text()), "user.js = celui du dépôt…")
        self.assertIn('user_pref("xpinstall.signatures.required", false);', user, "… plus le bloc de l'extension")
        self.assertEqual(self.lancer("extension", "etat").returncode, 0)
        self.assertEqual(self.lancer("etat").returncode, 0, "la config de base est posée avec l'extension")
        # L'hôte natif : lancé comme Firefox le fait, il envoie la palette tout de suite, puis s'arrête quand Firefox ferme
        proc = subprocess.Popen([str(SCRIPT), str(hote), "nc-couleurs@noctalia-config"], env=self.env,
                                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            n = struct.unpack("<I", proc.stdout.read(4))[0]
            msg = json.loads(proc.stdout.read(n))
            self.assertEqual(msg["palette"]["fond"], "#211c1c")
            self.assertTrue(msg["palette"]["sombre"])
            self.assertNotIn("bordure", msg["palette"], "seules les couleurs passent")
            demande = json.dumps({"demande": "couleurs"}).encode()
            proc.stdin.write(struct.pack("<I", len(demande)) + demande); proc.stdin.flush()
            n = struct.unpack("<I", proc.stdout.read(4))[0]
            self.assertEqual(json.loads(proc.stdout.read(n))["palette"]["accent"], "#a6a6a6")
            proc.stdin.close()
            self.assertEqual(proc.wait(timeout=5), 0, "l'hôte s'arrête quand la liaison se ferme")
        finally:
            if proc.poll() is None:
                proc.kill()
            proc.stdout.close(); proc.stderr.close()
        self.assertEqual(self.lancer("extension", "desinstaller").returncode, 0)
        self.assertFalse(xpi.exists()); self.assertFalse(hote.exists())
        self.assertNotIn("xpinstall", (p / "user.js").read_text(), "le bloc de l'extension est retiré")
        self.assertEqual(self.lancer("extension", "etat").returncode, 1)
        self.assertEqual(self.lancer("etat").returncode, 0, "la config de base reste")
        self.lancer("extension", "installer")
        self.assertEqual(self.lancer("desinstaller").returncode, 0)
        self.assertFalse(xpi.exists(), "desinstaller retire aussi l'extension")

    def test_user_js_bien_forme(self):
        cles = []
        for n, ligne in enumerate((SOURCE / "user.js").read_text().splitlines(), 1):
            if not ligne.strip() or ligne.startswith("//"):
                continue
            m = PREF.match(ligne)
            self.assertIsNotNone(m, f"user.js ligne {n} : {ligne[:80]}")
            cles.append(m.group(1))
        self.assertEqual(len(cles), len(set(cles)), "préférence en double")
        self.assertIn("toolkit.legacyUserProfileCustomizations.stylesheets", cles)
        for rel in ("chrome/userChrome.css", "chrome/userContent.css"):
            texte = (SOURCE / rel).read_text()
            self.assertEqual(texte.count("{"), texte.count("}"), rel + " : accolades")
            self.assertIn("nc-firefox", texte[:300], rel + " : marque d'origine en tête")


if __name__ == "__main__":
    unittest.main()

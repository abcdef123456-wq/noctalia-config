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
        for rel in ("chrome/userChrome.css", "chrome/userContent.css"):
            self.assertEqual((p / rel).read_text(), (SOURCE / rel).read_text(), rel)
        # user.js : celui du dépôt, suivi des préférences qui suivent nc-reglages (Apparence → Firefox : …)
        u = (p / "user.js").read_text()
        self.assertTrue(u.startswith((SOURCE / "user.js").read_text()), "user.js du dépôt en tête")
        self.assertIn('user_pref("sidebar.verticalTabs", false);', u)
        self.assertIn('user_pref("browser.startup.page", 3);', u)
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

    def test_extension_refusee_par_le_firefox_grand_public(self):
        self.profils("[Profile0]\nName=x\nIsRelative=1\nPath=x.p\nDefault=1\n", "x.p")
        p = self.base / "x.p"
        (p / "compatibility.ini").write_text("[Compatibility]\nLastVersion=144.0_20261001/20261001\nLastPlatformDir=/usr/lib64/firefox\n")
        r = self.lancer("extension", "installer")
        self.assertEqual(r.returncode, 4)
        self.assertIn("non signées", r.stderr)
        self.assertFalse((p / "extensions").exists(), "rien de posé")
        (p / "compatibility.ini").write_text("[Compatibility]\nLastVersion=140.4.0_20261001/20261001\nLastPlatformDir=/usr/lib/firefox-esr\n")
        self.assertEqual(self.lancer("extension", "installer").returncode, 0, "ESR (Debian 13) l'accepte")

    def test_tes_fichiers_ne_sont_jamais_perdus(self):
        """Retour de Codex (FF-01) : un userChrome.css / userContent.css personnel était écrasé puis supprimé."""
        self.profils("[Profile0]\nName=x\nIsRelative=1\nPath=x.p\nDefault=1\n", "x.p")
        p = self.base / "x.p"
        (p / "chrome").mkdir(parents=True)
        (p / "chrome/userChrome.css").write_text("/* mon style */")
        (p / "chrome/userContent.css").write_text("/* mes pages */")
        self.assertEqual(self.lancer("installer").returncode, 0)
        self.assertEqual(self.lancer("installer").returncode, 0)          # deux fois : la sauvegarde reste la mienne
        self.assertEqual((p / "chrome/userChrome.css.avant-nc").read_text(), "/* mon style */")
        # Retouché après l'installation : mes retouches gardées avant d'être remplacées
        (p / "chrome/userChrome.css").write_text((p / "chrome/userChrome.css").read_text() + "\n/* retouche */")
        self.assertEqual(self.lancer("installer").returncode, 0)
        self.assertIn("/* retouche */", (p / "chrome/userChrome.css.retouche-nc").read_text())
        self.assertEqual((p / "chrome/userChrome.css.avant-nc").read_text(), "/* mon style */")
        # user.js réécrit par nc-firefox lui-même : pas pris pour une retouche
        self.assertFalse((p / "user.js.retouche-nc").exists())
        self.assertEqual(self.lancer("desinstaller").returncode, 0)
        self.assertEqual(self.lancer("desinstaller").returncode, 0)
        self.assertEqual((p / "chrome/userChrome.css").read_text(), "/* mon style */")
        self.assertEqual((p / "chrome/userContent.css").read_text(), "/* mes pages */")
        self.assertFalse((p / "chrome/userChrome.css.avant-nc").exists())

    def test_retouches_de_user_js_jamais_perdues(self):
        """Contre-relecture de Codex (FF-01b) : une retouche de user.js disparaissait à la désinstallation (réécrit par
        le retrait de l'extension avant d'être gardé) ; deux retouches successives n'en gardaient qu'une."""
        self.profils("[Profile0]\nName=x\nIsRelative=1\nPath=x.p\nDefault=1\n", "x.p")
        p = self.base / "x.p"
        tout = lambda: "".join(f.read_text(errors="replace") for f in p.rglob("*") if f.is_file())
        self.lancer("installer")
        (p / "user.js").write_text((p / "user.js").read_text() + 'user_pref("mes.retouche.une", true);\n')
        self.assertEqual(self.lancer("extension", "desinstaller").returncode, 0)      # réécrit user.js : retouche gardée
        self.assertIn("mes.retouche.une", (p / "user.js.retouche-nc").read_text())
        self.assertNotIn("mes.retouche.une", (p / "user.js").read_text())
        (p / "user.js").write_text((p / "user.js").read_text() + 'user_pref("mes.retouche.deux", true);\n')
        self.assertEqual(self.lancer("desinstaller").returncode, 0)
        self.assertFalse((p / "user.js").exists())
        self.assertIn("mes.retouche.une", tout())
        self.assertIn("mes.retouche.deux", tout(), "la deuxième retouche n'écrase pas la première")
        self.assertEqual(len(list(p.glob("user.js.retouche-nc*"))), 2)

    def test_extension_active_pas_de_couleurs_figees(self):
        """Retour de Codex (FF-03) : avec l'extension, des variables lues au démarrage masquaient les couleurs en direct."""
        self.profils("[Profile0]\nName=x\nIsRelative=1\nPath=x.p\nDefault=1\n", "x.p")
        p = self.base / "x.p"
        (self.home / ".config/nc").mkdir(parents=True, exist_ok=True)
        (self.home / ".config/nc/palette-ile.json").write_text(json.dumps({"sombre": True, "fond": "#101010", "texte": "#eeeeee"}))
        self.lancer("installer")
        self.assertIn("--nc-couleur-fond", (p / "chrome/nc-couleurs.css").read_text())
        (p / "extensions").mkdir(exist_ok=True)
        (p / "extensions/nc-couleurs@noctalia-config.xpi").write_bytes(b"PK")   # extension posée
        self.assertEqual(self.lancer("couleurs").returncode, 0)
        self.assertNotIn("--nc-couleur", (p / "chrome/nc-couleurs.css").read_text())
        css = (REPO / "home/.local/share/nc/firefox/chrome/userChrome.css").read_text()
        self.assertIn("var(--toolbar-field-border-color-focus, var(--toolbar-field-focus-border-color, AccentColor))", css,
                      "l'accent suit le thème en direct")
        # Revue Codex FF-04 (Firefox 159, DOM réelle) : .urlbar-background n'a plus d'id ; --toolbar-bgcolor renommé
        self.assertIn("#urlbar > .urlbar-background", css)
        self.assertIn("#urlbar[focused] > .urlbar-background", css)
        self.assertIn("var(--toolbar-background-color, var(--toolbox-background-color, var(--toolbar-bgcolor, Canvas)))", css)

    def test_suggestions_lisibles(self):
        """La liste de la barre d'adresse (la recherche) : couleurs de la palette, jamais celles du thème GTK (lien à
        1,8:1 sur fond sombre), ligne choisie nettement distincte du fond (elle ne l'était qu'à 1,16:1)."""
        css = (REPO / "home/.local/share/nc/firefox/chrome/userChrome.css").read_text()
        for jeton in ("--urlbarview-text-color-action: var(--nc-accent)", "--urlbarview-text-color-secondary: var(--nc-texte-sec)",
                      "--urlbarview-text-color-selected: var(--nc-texte)", "--urlbarview-background-color-selected: var(--nc-ligne-choisie)"):
            self.assertIn(jeton, css)
        self.assertIn("--nc-ligne-choisie: color-mix(in srgb, var(--nc-texte) 18%, var(--nc-fond))", css)
        self.assertNotIn("background-color: var(--nc-carte-survol) !important;\n  border-radius: 8px", css)
        js = (REPO / "home/.local/share/nc/firefox/extension/fond.js").read_text()
        self.assertIn("popup_highlight: melange(fond, texte, 0.18)", js)

        def lum(h):
            r, g, b = (int(h[i:i + 2], 16) / 255 for i in (1, 3, 5))
            f = lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
            return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)
        def melange(a, b, t):
            return "#" + "".join(f"{round(int(a[i:i+2], 16) + (int(b[i:i+2], 16) - int(a[i:i+2], 16)) * t):02x}" for i in (1, 3, 5))
        contraste = lambda a, b: (max(lum(a), lum(b)) + 0.05) / (min(lum(a), lum(b)) + 0.05)
        for fond, texte in (("#1c1d21", "#f2f2f3"), ("#101012", "#e6e6e8"), ("#2b2d33", "#ffffff")):
            choisie = melange(fond, texte, 0.18)
            self.assertGreater(contraste(choisie, fond), 1.4, "ligne choisie visible")
            self.assertGreater(contraste(texte, choisie), 7, "texte de la ligne choisie lisible")

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

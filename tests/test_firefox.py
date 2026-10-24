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
CHROME = SOURCE / "chrome/userChrome.css"
# Palettes de référence (fond, carte, texte, texteSec, accent) : une palette réelle sombre, une claire (Material)
REELLE = ("#13212a", "#1b2a33", "#f2f2f3", "#afb3b6", "#67b3e4")
CLAIRE = ("#f8f9ff", "#ecedf6", "#191c20", "#42474e", "#33618d")


def lum(h):
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (1, 3, 5))
    f = lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)


def melange(a, b, t):
    """color-mix(in srgb, b t, a) : t = part de b (0 à 1)."""
    return "#" + "".join(f"{round(int(a[i:i+2], 16) + (int(b[i:i+2], 16) - int(a[i:i+2], 16)) * t):02x}" for i in (1, 3, 5))


def contraste(a, b):
    return (max(lum(a), lum(b)) + 0.05) / (min(lum(a), lum(b)) + 0.05)


def bloc(css, selecteur):
    """Le corps de la règle qui commence par selecteur (première occurrence)."""
    debut = css.index(selecteur)
    return css[css.index("{", debut) + 1:css.index("}", debut)]


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
        self.assertIn("#urlbar[focused]:not([popover-open]) > .urlbar-background", css)
        self.assertIn("var(--toolbar-background-color, var(--toolbox-background-color, var(--toolbar-bgcolor, Canvas)))", css)

    def test_suggestions_lisibles(self):
        """La liste de la barre d'adresse (la recherche) : couleurs de la palette, jamais celles du thème GTK (lien à
        1,8:1 sur fond sombre), ligne choisie nettement distincte de la liste, qui est sur la carte (relecture B3)."""
        css = CHROME.read_text()
        for jeton in ("--urlbarview-text-color-action: var(--nc-accent)", "--urlbarview-text-color-secondary: var(--nc-texte-sec)",
                      "--urlbarview-text-color-selected: var(--nc-texte)", "--urlbarview-background-color-selected: var(--nc-ligne-choisie)",
                      "--urlbarview-background-color-hover: var(--nc-ligne-survol)"):
            self.assertIn(jeton, css)
        part = lambda nom, de, vers: int(re.search(rf"{nom}: color-mix\(in srgb, var\({de}\) (\d+)%, var\({vers}\)\)", css).group(1)) / 100
        choisie = part("--nc-ligne-choisie", "--nc-texte", "--nc-carte")
        survol = part("--nc-ligne-survol", "--nc-texte", "--nc-carte")
        sec = part("--nc-texte-sec-choisie", "--nc-texte-sec", "--nc-texte")
        self.assertIn(".urlbarView-row[selected] .urlbarView-title-separator::before { color: var(--nc-texte-sec-choisie)", css)
        self.assertNotIn("background-color: var(--nc-carte-survol) !important;\n  border-radius: 8px", css)
        js = (SOURCE / "extension/fond.js").read_text()
        self.assertIn("popup_highlight: melange(fond, texte, 0.18)", js)
        # Mesuré dans Firefox 159 (palette réelle / claire) : ligne choisie 1,72 / 1,44 sur la liste, texte 7,64 / 10,15
        for fond, carte, texte, texte_sec, accent in (REELLE, CLAIRE, ("#101012", "#1a1a1d", "#e6e6e8", "#a0a0a8", "#7aa2f7")):
            ligne = melange(carte, texte, choisie)
            self.assertGreater(contraste(ligne, carte), 1.4, "ligne choisie visible sur la liste")
            self.assertGreater(contraste(melange(carte, texte, survol), carte), 1.15, "survol visible")
            self.assertGreater(contraste(texte, ligne), 7, "texte de la ligne choisie lisible")
            self.assertGreaterEqual(contraste(melange(texte, texte_sec, sec), ligne), 4.5, "texte secondaire sur la ligne choisie")
            self.assertGreaterEqual(contraste(accent, ligne), 3, "liseré d'accent de la ligne choisie")
        # Avec l'extension (pas de texte secondaire de palette) : 80 % du texte, lisible sur la ligne choisie
        self.assertIn("color-mix(in srgb, var(--nc-theme-texte) 80%, transparent)", css)
        for fond, carte, texte, _, _ in (REELLE, CLAIRE):
            ligne = melange(carte, texte, choisie)
            self.assertGreaterEqual(contraste(melange(ligne, texte, 0.8), ligne), 4.5)

    def test_liste_sur_la_carte_sans_coins_carres(self):
        """Relecture B3 (P2-1, Firefox 159 « Nova ») : le fond de la liste ouverte est peint par .urlbarView-background
        avec --urlbar-background-color-focus ; un fond sur .urlbarView se dessinait dessous, en cadre à coins carrés,
        et sans l'extension (tout Firefox grand public) la liste restait hors palette. Forme, contour et ombre forcés
        sur le champ ouvert cassaient la jonction champ / liste."""
        css = CHROME.read_text()
        jetons = bloc(css, ":root,\n#urlbar,\n#searchbar-new {")
        self.assertIn("--urlbar-background-color: var(--nc-carte) !important;", jetons)
        self.assertIn("--urlbar-background-color-focus: var(--nc-carte) !important;", jetons)
        self.assertNotRegex(bloc(css, "#urlbar[open] > .urlbarView,"), r"(?m)^\s*background(-color)?:", "pas de fond sur .urlbarView")
        forme = bloc(css, "#urlbar-background,\n#searchbar,\n#urlbar:not([popover-open]) > .urlbar-background,")
        self.assertIn("border-radius: var(--nc-arrondi)", forme)
        self.assertIn("box-shadow: none", forme)
        self.assertNotIn("#urlbar > .urlbar-background,\n#searchbar {\n  border-radius", css)
        self.assertNotIn("#urlbar[focused] > .urlbar-background", css, "au focus liste ouverte, pas de contour d'accent à moitié")

    def test_anciens_jetons_esr(self):
        """Relecture B3 (P2-2) : ESR 140 (Debian 13) lit --urlbarView-* (V majuscule) ; --link-color colore l'adresse
        des suggestions (sinon le violet du thème Firefox)."""
        liste = bloc(CHROME.read_text(), "#urlbar[open] > .urlbarView,")
        for jeton in ("--urlbarView-action-color: var(--nc-accent) !important;",
                      "--urlbarView-secondary-text-color: var(--nc-texte-sec) !important;",
                      "--urlbarView-hover-background: var(--nc-ligne-survol) !important;",
                      "--urlbarView-highlight-background: var(--nc-ligne-choisie) !important;",
                      "--urlbarView-highlight-color: var(--nc-texte) !important;",
                      "--link-color: color-mix(in srgb, var(--nc-accent) 75%, var(--nc-texte)) !important;"):
            self.assertIn(jeton, liste)
        for fond, carte, texte, _, accent in (REELLE, CLAIRE):
            self.assertGreaterEqual(contraste(melange(texte, accent, 0.75), carte), 4.5, "adresse lisible sur la liste")

    def test_contour_du_champ_et_recherche_dans_la_page(self):
        """Relecture B3 (P3) : contour du champ au repos à 3:1 sur la barre (35 % ne donnait que 2,97:1 en sombre) ;
        Ctrl+F : liseré de focus à l'accent de la palette."""
        css = CHROME.read_text()
        m = re.search(r"--nc-contour-champ: light-dark\(color-mix\(in srgb, var\(--nc-texte\) (\d+)%, var\(--nc-fond\)\), "
                      r"color-mix\(in srgb, var\(--nc-texte\) (\d+)%, var\(--nc-fond\)\)\);", css)
        clair, sombre = int(m.group(1)) / 100, int(m.group(2)) / 100
        for (fond, _, texte, _, _), part in ((REELLE, sombre), (CLAIRE, clair)):
            self.assertGreaterEqual(contraste(melange(fond, texte, part), fond), 3, "contour / barre")
        self.assertIn(".browserContainer > findbar .findbar-textbox:focus { outline-color: var(--nc-accent) !important; }", css)

    def test_selecteurs_de_firefox_159_et_esr_140(self):
        """Relecture B3 (P3) : sélecteurs morts retirés (ni dans Firefox 159 ni dans ESR 140), nouveaux ajoutés ;
        #sidebar-main et --urlbarView-highlight-* gardés pour ESR 140."""
        css = CHROME.read_text()
        for mort in (".tab-line", ".tabbrowser-tab::before", ".tabbrowser-tab::after", "#navigator-toolbox::after",
                     "#PanelUI-menu-button + .panel-arrowcontent"):
            self.assertNotIn(mort, css)
        self.assertIn("#searchbar-new:not([popover-open]) > .urlbar-background", css)
        self.assertIn("#searchbar-new > .urlbar-background", css)
        self.assertIn("#sidebar-main", css, "ESR 140 : la barre latérale a encore cet id")
        barre = bloc(css, ":root {\n  --sidebar-background-color")
        self.assertIn("--sidebar-background-color: var(--nc-fond) !important;", barre)
        self.assertIn("--sidebar-text-color: var(--nc-texte) !important;", barre)
        contenu = (SOURCE / "chrome/userContent.css").read_text()
        self.assertNotIn("--in-content-border-radius:", contenu)
        self.assertIn("--border-radius-medium: 12px !important;", contenu)

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


@unittest.skipUnless(__import__("shutil").which("node"), "Node requis pour les tests JavaScript")
class ExtensionDemarrage(unittest.TestCase):
    """Revue EXT-01 : au démarrage, Firefox posait son thème après celui de l'extension (palette perdue jusqu'au fond
    d'écran suivant). fond.js réapplique quand un thème qui n'est pas le sien arrive, sans boucle."""
    def test_reapplique_sans_boucle(self):
        code = r'''
const fs = require("fs"), vm = require("vm"), assert = require("node:assert/strict");
const ecouteurs = {}, appels = [];
let actif = "firefox-compact-dark@mozilla.org";
const ev = (nom) => ({ addListener: (f) => { ecouteurs[nom] = f; } });
const port = { onMessage: ev("message"), onDisconnect: ev("deconnexion"), postMessage: () => {} };
const browser = {
  runtime: { connectNative: () => port },
  management: { getAll: async () => [{ type: "theme", enabled: true, id: actif }], onEnabled: ev("on"), onDisabled: ev("off"),
                setEnabled: async (id, oui) => { appels.push(["setEnabled", id, oui]); await (oui ? ecouteurs.on : ecouteurs.off)({ type: "theme" }); } },
  theme: { update: (t) => appels.push(["update", t.colors.frame]), reset: () => appels.push(["reset"]), onUpdated: ev("maj") },
};
const minuteurs = [];
vm.runInNewContext(fs.readFileSync(process.argv[1], "utf8"), { browser, setTimeout: (f) => minuteurs.push(f), Date, console });
const attendre = async () => { for (let i = 0; i < 20; i++) { await new Promise((r) => setImmediate(r)); while (minuteurs.length) await minuteurs.shift()(); } };
(async () => {
  ecouteurs.message({ palette: { fond: "#1c1d21", texte: "#eeeeee", sombre: true } });
  await attendre();
  assert.deepEqual(appels, [["update", "#1c1d21"]]);
  // Firefox pose son thème par-dessus (démarrage) : réappliqué
  await ecouteurs.maj({ theme: { colors: { frame: "#2b2a33" } } }); await attendre();
  assert.deepEqual(appels.at(-1), ["update", "#1c1d21"]);
  const n = appels.length;
  // Le nôtre : rien
  await ecouteurs.maj({ theme: { colors: { frame: "#1c1d21" } } }); await attendre();
  assert.equal(appels.length, n);
  // Un thème choisi (Alpenglow) : reset, puis ce thème repris (revue EXT-02), sans boucle
  actif = "alpenglow@mozilla.org";
  ecouteurs.off({ type: "theme" }); await attendre();
  assert.deepEqual(appels.slice(-3), [["reset"], ["setEnabled", "alpenglow@mozilla.org", false], ["setEnabled", "alpenglow@mozilla.org", true]]);
  const k = appels.length;
  await ecouteurs.maj({ theme: {} }); await attendre();
  ecouteurs.off({ type: "theme" }); await attendre();
  assert.equal(appels.length, k, "pas de second reset : notre thème n'est plus posé");
  // Un Firefox qui réécrirait sans fin : au plus 5 reprises par 10 s
  actif = "firefox-compact-dark@mozilla.org";
  const m = appels.length;
  for (let i = 0; i < 20; i++) { await ecouteurs.maj({ theme: { colors: { frame: "#000000" } } }); await attendre(); }
  assert.ok(appels.length - m <= 5, String(appels.length - m));
})().catch((e) => { console.error(e); process.exit(1); });
'''
        r = subprocess.run(["node", "-e", code, str(SOURCE / "extension/fond.js")], capture_output=True, text=True, timeout=20)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_pages_internes_du_cote_de_la_palette(self):
        """Relecture B3 (P2-3) : content_color_scheme « auto » suivait le système ; palette sombre et système clair
        donnaient des réglages (about:preferences) clairs, mesuré dans Firefox 159. Les pages internes suivent la
        palette, comme l'interface."""
        code = r'''
const fs = require("fs"), vm = require("vm"), assert = require("node:assert/strict");
const ev = () => ({ addListener: () => {} });
const port = { onMessage: ev(), onDisconnect: ev(), postMessage: () => {} };
const browser = { runtime: { connectNative: () => port }, management: { getAll: async () => [], onEnabled: ev(), onDisabled: ev() },
                  theme: { update: () => {}, reset: () => {}, onUpdated: ev() } };
const ctx = { browser, setTimeout: () => {}, Date, console };
vm.runInNewContext(fs.readFileSync(process.argv[1], "utf8"), ctx);
const props = (p) => JSON.parse(JSON.stringify(ctx.theme(p).properties));   // objet d'un autre contexte : copié
assert.deepEqual(props({ fond: "#13212a", sombre: true }), { color_scheme: "dark", content_color_scheme: "dark" });
assert.deepEqual(props({ fond: "#f8f9ff", sombre: false }), { color_scheme: "light", content_color_scheme: "light" });
assert.equal(props({ fond: "#13212a" }).content_color_scheme, "dark", "sans « sombre » : sombre, comme color_scheme");
'''
        r = subprocess.run(["node", "-e", code, str(SOURCE / "extension/fond.js")], capture_output=True, text=True, timeout=20)
        self.assertEqual(r.returncode, 0, r.stderr)


FIREFOX = next(filter(None, map(__import__("shutil").which, ("firefox-developer-edition", "firefox"))), None)


def pixel_png(png, x, y):
    """La couleur #rrggbb d'un pixel d'une capture PNG (8 bits, RGB ou RGBA, non entrelacée), sans bibliothèque."""
    import zlib
    pos, idat, entete = 8, b"", None
    while pos < len(png):
        n, genre = struct.unpack(">I4s", png[pos:pos + 8])
        corps = png[pos + 8:pos + 8 + n]
        if genre == b"IHDR":
            entete = struct.unpack(">IIBBBBB", corps)
        elif genre == b"IDAT":
            idat += corps
        pos += 12 + n
    largeur, _, profondeur, couleur, _, _, entrelace = entete
    assert profondeur == 8 and couleur in (2, 6) and not entrelace, entete
    bpp = 3 if couleur == 2 else 4
    brut, ligne, prec = zlib.decompress(idat), largeur * bpp, bytearray(largeur * bpp)
    for j in range(y + 1):
        filtre, cur = brut[j * (ligne + 1)], bytearray(brut[j * (ligne + 1) + 1:(j + 1) * (ligne + 1)])
        for i in range(ligne):
            a = cur[i - bpp] if i >= bpp else 0
            b, c = prec[i], (prec[i - bpp] if i >= bpp else 0)
            if filtre == 1:
                cur[i] = (cur[i] + a) & 255
            elif filtre == 2:
                cur[i] = (cur[i] + b) & 255
            elif filtre == 3:
                cur[i] = (cur[i] + (a + b) // 2) & 255
            elif filtre == 4:
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                cur[i] = (cur[i] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
        prec = cur
    return "#%02x%02x%02x" % tuple(prec[x * bpp:x * bpp + 3])


@unittest.skipUnless(FIREFOX and os.environ.get("NC_TEST_FIREFOX") == "1",
                     "vrai Firefox, sur demande seulement : NC_TEST_FIREFOX=1 (Firefox installé)")
class FirefoxReel(unittest.TestCase):
    """Relecture B3 (P2-1), dans un vrai Firefox headless (profil, HOME et XDG temporaires, jamais le vrai profil) :
    sans l'extension, la liste ouverte de la barre d'adresse est sur la carte de la palette, et ses coins arrondis
    laissent voir la page (plus de cadre carré peint par .urlbarView)."""
    LISTE = r'''
const done = arguments[arguments.length - 1];
(async () => {
  const w = Services.wm.getMostRecentWindow("navigator:browser"), d = w.document;
  const { PlacesUtils } = ChromeUtils.importESModule("resource://gre/modules/PlacesUtils.sys.mjs");
  await PlacesUtils.history.insertMany([{ url: "https://noctalia.example/a", title: "Noctalia A", visits: [{ date: new Date() }] },
    { url: "https://docs.noctalia.example/b", title: "Noctalia docs", visits: [{ date: new Date() }] }]);
  w.gURLBar.focus(); w.gURLBar.search("noctalia");
  await new Promise((r) => w.setTimeout(r, 1800));
  const v = d.querySelector("#urlbar .urlbarView"), fond = d.querySelector("#urlbar .urlbarView-background");
  const r = v.getBoundingClientRect();
  done({ fond: fond && w.getComputedStyle(fond).backgroundColor, vue: w.getComputedStyle(v).backgroundColor,
         x: r.x, bas: r.y + r.height, dpr: w.devicePixelRatio });
})().catch((e) => done({ err: String(e) }));
'''

    def test_liste_sur_la_carte_coins_sur_la_page(self):
        import base64
        import socket
        import time
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        home = Path(tmp.name)
        prof = home / "profil"
        (prof / "chrome").mkdir(parents=True)
        for rel in ("chrome/userChrome.css", "chrome/userContent.css"):
            (prof / rel).write_text((SOURCE / rel).read_text())
        fond, carte, texte, texte_sec, accent = REELLE
        (prof / "chrome/nc-couleurs.css").write_text(
            "/* nc-firefox test */\n@media (prefers-color-scheme: dark) {\n  :root {\n"
            f"    --nc-couleur-fond: {fond};\n    --nc-couleur-carte: {carte};\n    --nc-couleur-texte: {texte};\n"
            f"    --nc-couleur-texte-sec: {texte_sec};\n    --nc-couleur-accent: {accent};\n  }}\n}}\n")
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]
        prefs = (("marionette.port", port), ("ui.systemUsesDarkTheme", 1), ("network.proxy.type", 1),
                 ("network.proxy.http", '"127.0.0.1"'), ("network.proxy.http_port", 9), ("network.proxy.ssl", '"127.0.0.1"'),
                 ("network.proxy.ssl_port", 9), ("browser.search.suggest.enabled", "false"), ("browser.startup.page", 0),
                 ("browser.aboutwelcome.enabled", "false"), ("browser.startup.homepage_override.mstone", '"ignore"'),
                 ("toolkit.telemetry.reportingpolicy.firstRun", "false"), ("datareporting.policy.dataSubmissionEnabled", "false"))
        (prof / "user.js").write_text((SOURCE / "user.js").read_text() + "".join(f'user_pref("{k}", {v});\n' for k, v in prefs))
        env = {"PATH": os.environ["PATH"], "HOME": str(home), "XDG_CONFIG_HOME": str(home / ".config"),
               "XDG_CACHE_HOME": str(home / ".cache"), "XDG_DATA_HOME": str(home / ".local/share"),
               "XDG_STATE_HOME": str(home / ".local/state"), "XDG_RUNTIME_DIR": str(home),
               "MOZ_HEADLESS": "1", "MOZ_REMOTE_ALLOW_SYSTEM_ACCESS": "1", "MOZ_HEADLESS_WIDTH": "1100", "MOZ_HEADLESS_HEIGHT": "720", "LANG": "C.UTF-8"}
        proc = subprocess.Popen([FIREFOX, "--headless", "--marionette", "--no-remote", "--profile", str(prof), "about:blank"],
                                env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        sock = None
        try:
            debut = time.time()
            while sock is None:
                try:
                    sock = socket.create_connection(("127.0.0.1", port), timeout=60)
                except OSError:
                    self.assertLess(time.time() - debut, 60, "Marionette injoignable")
                    time.sleep(0.5)

            def lire():
                n = b""
                while not n.endswith(b":"):
                    n += sock.recv(1)
                corps, n = b"", int(n[:-1])
                while len(corps) < n:
                    corps += sock.recv(n - len(corps))
                return json.loads(corps)
            ident = [0]

            def cmd(nom, params=None):
                ident[0] += 1
                m = json.dumps([0, ident[0], nom, params or {}]).encode()
                sock.sendall(str(len(m)).encode() + b":" + m)
                r = lire()
                self.assertIsNone(r[2], nom)
                return r[3]
            lire()
            cmd("WebDriver:NewSession", {"capabilities": {}})
            cmd("WebDriver:Navigate", {"url": "data:text/html,<body style='background:%2300ff00;margin:0'></body>"})
            cmd("Marionette:SetContext", {"value": "chrome"})
            r = cmd("WebDriver:ExecuteAsyncScript", {"script": self.LISTE, "args": []})["value"]
            self.assertNotIn("err", r)
            if r["fond"] is None:
                self.skipTest("pas de .urlbarView-background (Firefox sans Nova) : rien à mesurer")
            rgb = "rgb(%d, %d, %d)" % tuple(int(carte[i:i + 2], 16) for i in (1, 3, 5))
            self.assertEqual(r["fond"], rgb, "la liste est sur la carte de la palette, sans l'extension")
            self.assertEqual(r["vue"], "rgba(0, 0, 0, 0)", "pas de fond sur .urlbarView")
            png = base64.b64decode(cmd("WebDriver:TakeScreenshot", {"full": False, "hash": False})["value"])
            coin = pixel_png(png, int(r["x"] * r["dpr"]) + 1, int(r["bas"] * r["dpr"]) - 2)
            self.assertGreater(contraste(coin, fond), 5, f"le coin de la liste laisse voir la page verte ({coin}), pas un cadre")
            try:
                cmd("Marionette:Quit", {"flags": ["eForceQuit"]})
            except Exception:
                pass
        finally:
            if sock:
                sock.close()
            try:
                proc.wait(10)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()

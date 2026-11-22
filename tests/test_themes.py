"""Thèmes : un fichier JSON par thème (home/.local/share/nc/themes), validé ici.

(a) les 8 thèmes migrés donnent exactement les anciens STYLES / PALETTES de nc-reglages (lus dans l'ancienne version
    du script, git show origin/main) ; (b) chaque fichier est bien écrit ; (c) un thème mal écrit est refusé sans rien
    changer ; (d) le réglage de l'utilisateur passe avant le thème ; (e) fond_de_depart posé au choix du thème, pas à la
    réapplication ; (f) nc-theme-sync lit theme_sync du thème. Faux HOME, faux noctalia ; jamais le vrai HOME."""
import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

REPO = Path(__file__).resolve().parent.parent
THEMES = REPO / "home/.local/share/nc/themes"
BIN = REPO / "home/.local/bin"
ORDRE = ["noctalia", "apple", "oled", "nord", "catppuccin", "dracula", "gruvbox", "kanagawa"]
FONDS = REPO / "home/Pictures/Wallpapers"
ENRICHIS = {"apple", "catppuccin", "gruvbox", "nord", "kanagawa", "dracula"}
# Seules différences admises, thème par thème, entre le style.conf d'avant et celui d'aujourd'hui à la réapplication
AJOUTS = {"apple": "ILE_POLICE=Inter\nFENETRES_OMBRE=30\nWIDGETS_PLAQUE=non\n",
          "catppuccin": "ILE_CONTOUR=degrade\nILE_CONTOUR_EPAISSEUR=1\nILE_RAYON=rond\nILE_VERRE=97\nILE_ANIM=doux\nILE_ACCENTS=accent\n"
                        "ILE_CONTOUR_FERMEE=oui\nWIDGETS_PLAQUE=oui\nFENETRES_BORDURE=2\nFENETRES_OMBRE=30\n",
          "gruvbox": "ILE_CONTOUR_EPAISSEUR=3\nILE_RAYON=doux\nILE_VERRE=100\nILE_LUEUR=non\nILE_CONTOUR_FERMEE=oui\nWIDGETS_PLAQUE=non\n"
                     "FENETRES_BORDURE=3\nFENETRES_OMBRE=12\n",
          "nord": "ILE_CONTOUR_EPAISSEUR=1\nILE_RAYON=auto\nILE_VERRE=94\nILE_LUEUR=non\nILE_CONTOUR_FERMEE=oui\nWIDGETS_PLAQUE=non\n"
                  "FENETRES_BORDURE=1\nFENETRES_OMBRE=16\n",
          "kanagawa": "ILE_CONTOUR_EPAISSEUR=1\nILE_RAYON=doux\nILE_VERRE=100\nILE_LUEUR=non\nILE_ACCENTS=accent\nILE_CONTOUR_FERMEE=non\n"
                      "WIDGETS_PLAQUE=oui\nFENETRES_BORDURE=1\nFENETRES_OMBRE=20\n",
          "dracula": "ILE_CONTOUR=degrade\nILE_CONTOUR_EPAISSEUR=2\nILE_RAYON=carre\nILE_VERRE=100\nILE_LUEUR=oui\nILE_ACCENTS=accent\n"
                     "ILE_CONTOUR_FERMEE=oui\nWIDGETS_PLAQUE=oui\nFENETRES_BORDURE=2\nFENETRES_OMBRE=32\n"}          # anciens styles enrichis depuis la migration (valeurs d'origine gardées)
CLES = {"nom", "libelle", "palette", "reglages", "noctalia", "theme_sync", "fonds", "fond_de_depart", "credits", "widgets"}


def tous():
    """Les thèmes du dépôt : les huit d'origine dans leur ordre, puis les nouveaux par nom."""
    autres = sorted(p.stem for p in THEMES.glob("*.json") if p.stem not in ORDRE)
    return ORDRE + autres


def credits():
    lignes = (FONDS / "CREDITS.tsv").read_text(encoding="utf-8").splitlines()[1:]
    return {l.split("\t")[0] for l in lignes if l.strip()}


REFERENCE = json.loads((REPO / "tests/donnees/styles-avant-themes.json").read_text(encoding="utf-8"))


def anciens():
    """(STYLES, PALETTES) de nc-reglages d'avant les thèmes en fichiers, figés dans tests/donnees (commit 40eb708) :
    la comparaison ne dépend ni de l'historique git (CI sans historique) ni de ce que devient main."""
    return REFERENCE["STYLES"], {k: list(v) for k, v in REFERENCE["PALETTES"].items()}


class Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="nc-themes-")
        self.addCleanup(self._tmp.cleanup)
        self.r = Path(self._tmp.name)
        self.home = self.r / "home"
        for d in (".local/bin", ".config/nc", ".config/hypr"):
            (self.home / d).mkdir(parents=True)
        for n in ("nc-reglages", "nc-theme-sync"):
            shutil.copy(BIN / n, self.home / ".local/bin" / n)
        for n in ("nc-icones", "nc-firefox"):      # appelés par nc-theme-sync : faux, sans effet
            (self.home / ".local/bin" / n).write_text("#!/bin/sh\nexit 0\n")
            (self.home / ".local/bin" / n).chmod(0o755)
        self.themes = self.r / "themes"
        shutil.copytree(THEMES, self.themes)
        faux = self.r / "faux"
        faux.mkdir()
        self.journal = self.r / "journal"
        self.journal.touch()
        for n in ("noctalia", "pkill", "hyprctl", "gsettings", "notify-send", "qs"):
            (faux / n).write_text('#!/bin/sh\necho "%s $*" >> "$NC_TEST_JOURNAL"\nexit 0\n' % n)
            (faux / n).chmod(0o755)
        self.env = {k: v for k, v in os.environ.items() if not k.startswith(("NOCTALIA_", "XDG_CONFIG", "XDG_STATE"))}
        self.env.pop("HYPRLAND_INSTANCE_SIGNATURE", None)
        self.env.update(HOME=str(self.home), NC_LANGUE="fr", PATH=f"{faux}:{os.environ['PATH']}",
                        XDG_CACHE_HOME=str(self.home / ".cache"), NC_THEMES_DIR=str(self.themes),
                        NC_TEST_JOURNAL=str(self.journal))

    def nc(self, *args, script="nc-reglages"):
        return subprocess.run([str(self.home / ".local/bin" / script), *args], env=self.env, cwd=str(self.home),
                              capture_output=True, text=True, timeout=60)

    def style_conf(self):
        p = self.home / ".config/nc/style.conf"
        return p.read_text(encoding="utf-8") if p.exists() else None

    def lignes_style(self):
        return dict(l.split("=", 1) for l in (self.style_conf() or "").splitlines() if "=" in l)

    def ecrire_theme(self, nom, **champs):
        d = json.loads((self.themes / "nord.json").read_text(encoding="utf-8"))
        d["nom"] = nom
        d.update(champs)
        (self.themes / (nom + ".json")).write_text(json.dumps(d), encoding="utf-8")


class Equivalence(Base):
    def test_anciens_styles_et_palettes(self):
        styles, palettes = anciens()
        for nom in ORDRE:
            with self.subTest(theme=nom):
                d = json.loads((THEMES / (nom + ".json")).read_text(encoding="utf-8"))
                if nom in ENRICHIS:     # un thème enrichi garde chaque valeur de l'ancien style, et en ajoute
                    self.assertEqual({k: d["reglages"][k] for k in styles.get(nom, {})}, styles.get(nom, {}))
                else:
                    self.assertEqual(d["reglages"], styles.get(nom, {}))
                pal = palettes.get(nom)
                self.assertEqual([d["palette"]["source"], d["palette"]["nom"]] if pal else d["palette"]["source"],
                                 pal if pal else "fond")
        self.assertTrue(set(ORDRE) <= {p.stem for p in THEMES.glob("*.json")})

    def test_style_conf_identique_par_style(self):
        styles, _ = anciens()
        for nom in ORDRE:
            with self.subTest(theme=nom):
                self.nc("set", "STYLE", "nord")       # un autre style avant, pour que chaque essai change vraiment
                r = self.nc("set", "STYLE", nom)
                self.assertEqual(r.returncode, 0, r.stderr)
                vals = self.lignes_style()
                self.assertEqual(vals.pop("STYLE"), nom)
                vals.pop("POLICE", None)              # décidée par police_apple(), pas par le thème
                d = json.loads((THEMES / (nom + ".json")).read_text(encoding="utf-8"))
                # Seul ajout voulu depuis les anciens styles : le dossier de fonds du thème, s'il en a un
                self.assertEqual(vals.pop("FONDS_DOSSIER", ""),
                                 str(self.home / "Pictures/Wallpapers" / d["fonds"]) if d["fonds"] else "")
                attendu = dict(styles.get(nom, {}), **d["reglages"]) if nom in ENRICHIS else styles.get(nom, {})
                self.assertEqual(vals, attendu)

    def test_choix_dans_l_ordre(self):
        spec = importlib.machinery.SourceFileLoader("nc_reglages_choix", str(BIN / "nc-reglages"))
        sauve = dict(os.environ)
        os.environ.update(HOME=str(self.home), NC_THEMES_DIR=str(self.themes), NC_LANGUE="fr")
        try:
            m = importlib.util.module_from_spec(importlib.util.spec_from_loader(spec.name, spec))
            spec.exec_module(m)
            self.assertEqual([c[0] for c in m.choix_styles()], tous())
            self.ecrire_theme("zzz-essai")
            self.assertEqual([c[0] for c in m.choix_styles()], tous() + ["zzz-essai"])
        finally:
            os.environ.clear()
            os.environ.update(sauve)


class Reapplication(Base):
    """Un utilisateur déjà sur un ancien style : « nc-reglages appliquer » (mise à jour, installation) réécrit son
    style.conf à l'octet près, aux seuls ajouts AJOUTS près ; jamais de dossier de fonds ajouté."""
    def setUp(self):
        super().setUp()
        fc = Path(self.env["PATH"].split(":")[0]) / "fc-list"          # aucune police : POLICE d'Apple jamais posée
        fc.write_text("#!/bin/sh\nexit 0\n")
        fc.chmod(0o755)

    def test_octet_par_octet(self):
        for nom, avant in REFERENCE["style_conf"].items():
            with self.subTest(theme=nom):
                (self.home / ".config/nc/style.conf").write_text(avant, encoding="utf-8")
                (self.home / ".config/nc/reglages.conf").write_text(f"STYLE={nom}\n", encoding="utf-8")
                r = self.nc("appliquer")
                self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
                self.assertEqual(self.style_conf(), avant + AJOUTS.get(nom, ""))
                self.assertNotIn("FONDS_DOSSIER", self.style_conf())

    def test_dossier_de_fonds_au_choix_puis_garde(self):
        """Choisir le thème pose son dossier de fonds ; une réapplication ensuite le garde."""
        self.nc("set", "STYLE", "dracula")
        r = self.nc("set", "STYLE", "nord")
        self.assertEqual(r.returncode, 0, r.stderr)
        dossier = str(self.home / "Pictures/Wallpapers/nord")
        self.assertEqual(self.lignes_style().get("FONDS_DOSSIER"), dossier)
        self.nc("appliquer")
        self.assertEqual(self.lignes_style().get("FONDS_DOSSIER"), dossier)

    def test_dossier_des_themes_absent_ou_vide(self):
        """STYLE=apple sans dossier de thèmes : message clair, style.conf inchangé, nc-theme-sync marche."""
        avant = REFERENCE["style_conf"]["apple"]
        for dossier in (self.r / "absent", self.r / "vide"):
            with self.subTest(dossier=dossier.name):
                if dossier.name == "vide":
                    dossier.mkdir()
                self.env["NC_THEMES_DIR"] = str(dossier)
                (self.home / ".config/nc/style.conf").write_text(avant, encoding="utf-8")
                (self.home / ".config/nc/reglages.conf").write_text("STYLE=apple\n", encoding="utf-8")
                r = self.nc("appliquer")
                self.assertIn("apple", r.stdout + r.stderr)
                self.assertRegex(r.stdout + r.stderr, "introuvable|not found")
                self.assertEqual(self.style_conf(), avant)
                (self.home / ".config/noctalia").mkdir(parents=True, exist_ok=True)
                (self.home / ".config/noctalia/colors.json").write_text(json.dumps(ThemeSync.COULEURS))
                r = self.nc(script="nc-theme-sync")
                self.assertEqual(r.returncode, 0, r.stderr)
                self.assertTrue((self.home / ".config/hypr/nc/couleurs.lua").exists())


class Validation(Base):
    def test_chaque_fichier(self):
        for f in sorted(THEMES.glob("*.json")):
            with self.subTest(fichier=f.name):
                d = json.loads(f.read_text(encoding="utf-8"))
                self.assertEqual(set(d), CLES)
                self.assertEqual(d["nom"], f.stem)
                self.assertEqual(set(d["libelle"]), {"fr", "en"})
                self.assertIn(d["palette"]["source"], ("builtin", "custom", "fond"))
                self.assertEqual(d["widgets"], [])
                self.assertIn(d["theme_sync"]["bordure"], ("degrade", "gris"))
                self.assertIn(d["theme_sync"]["ombre"], ("coloree", "noire"))
                if d["fonds"]:
                    # Le dossier de fonds du thème existe, son fond de départ aussi, et il est crédité
                    self.assertTrue((FONDS / d["fonds"]).is_dir(), d["fonds"])
                    self.assertTrue((FONDS / d["fonds"] / d["fond_de_depart"]).is_file(), d["fond_de_depart"])
                    self.assertIn(d["fonds"] + "/" + d["fond_de_depart"], credits())
                else:
                    self.assertEqual(d["fond_de_depart"], "")
        sans = {f.stem for f in THEMES.glob("*.json") if not json.loads(f.read_text(encoding="utf-8"))["fonds"]}
        self.assertEqual(sans, {"noctalia"})

    def refuse(self, nom, attendu):
        self.nc("set", "STYLE", "nord")
        avant = self.style_conf()
        r = self.nc("set", "STYLE", nom)
        self.assertNotEqual(r.returncode, 0, r.stdout)
        self.assertIn(attendu, r.stdout + r.stderr)
        self.assertEqual(self.style_conf(), avant)

    def test_json_invalide(self):
        (self.themes / "casse.json").write_text("{pas du json", encoding="utf-8")
        self.refuse("casse", "casse")

    def test_cle_inconnue_au_premier_niveau(self):
        self.ecrire_theme("mauvais", couleur_bizarre=1)
        self.refuse("mauvais", "couleur_bizarre")

    def test_cle_inconnue_dans_theme_sync(self):
        self.ecrire_theme("mauvais", theme_sync={"bordure": "gris", "ombre": "noire", "zzz": 1})
        self.refuse("mauvais", "zzz")

    def test_cle_de_reglage_inconnue(self):
        self.ecrire_theme("mauvais", reglages={"N_EXISTE_PAS": "1"})
        self.refuse("mauvais", "N_EXISTE_PAS")

    def test_valeur_de_reglage_refusee(self):
        self.ecrire_theme("mauvais", reglages={"ILE_CONTOUR": "pas-un-choix"})
        self.refuse("mauvais", "ILE_CONTOUR")

    def test_nom_different_du_fichier(self):
        d = json.loads((self.themes / "nord.json").read_text(encoding="utf-8"))
        d["nom"] = "autre"
        (self.themes / "mauvais.json").write_text(json.dumps(d), encoding="utf-8")
        self.refuse("mauvais", "autre")

    def test_palette_inconnue(self):
        self.ecrire_theme("mauvais", palette={"source": "magie", "nom": "X"})
        self.refuse("mauvais", "magie")

    def test_message_en_francais_et_en_anglais(self):
        self.ecrire_theme("mauvais", couleur_bizarre=1)
        fr = self.nc("set", "STYLE", "mauvais")
        self.env["NC_LANGUE"] = "en"
        en = self.nc("set", "STYLE", "mauvais")
        self.assertNotEqual(fr.stdout + fr.stderr, en.stdout + en.stderr)

    def test_un_theme_mauvais_ne_gene_pas_les_autres(self):
        self.ecrire_theme("mauvais", couleur_bizarre=1)
        r = self.nc("set", "STYLE", "dracula")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.lignes_style()["STYLE"], "dracula")


class Priorite(Base):
    def test_reglage_utilisateur_avant_le_theme(self):
        r = self.nc("set", "STYLE", "nord")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.lignes_style()["FENETRES_ARRONDI"], "10")
        r = self.nc("set", "FENETRES_ARRONDI", "20")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("FENETRES_ARRONDI", (self.home / ".config/nc/reglages.conf").read_text())
        self.nc("set", "STYLE", "nord")               # réapplication : le thème écrit toujours 10 dans style.conf
        self.assertEqual(self.lignes_style()["FENETRES_ARRONDI"], "10")
        self.assertIn("FENETRES_ARRONDI=20", (self.home / ".config/nc/reglages.conf").read_text())
        g = self.nc("get", "FENETRES_ARRONDI")
        self.assertEqual(g.stdout.strip().split()[-1], "20", g.stdout)


class Fonds(Base):
    def wallpaper_set(self):
        return [l for l in self.journal.read_text().splitlines() if "wallpaper-set" in l]

    def test_fond_de_depart_au_choix_pas_a_la_reapplication(self):
        self.ecrire_theme("jolie", fonds="jolie", fond_de_depart="un.jpg")
        r = self.nc("set", "STYLE", "jolie")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.lignes_style()["FONDS_DOSSIER"], str(self.home / "Pictures/Wallpapers/jolie"))
        pose = self.wallpaper_set()
        self.assertEqual(len(pose), 1, pose)
        self.assertTrue(pose[0].endswith("Pictures/Wallpapers/jolie/un.jpg"), pose)
        self.nc("appliquer")                          # réapplication : pas de nouveau fond
        self.assertEqual(len(self.wallpaper_set()), 1)

    def test_theme_sans_fond_ne_pose_rien(self):
        self.ecrire_theme("nu", fonds="", fond_de_depart="")      # tous les thèmes livrés sauf noctalia ont des fonds
        self.nc("set", "STYLE", "nu")
        self.assertEqual(self.wallpaper_set(), [])
        self.assertNotIn("FONDS_DOSSIER", self.lignes_style())


class ThemeSync(Base):
    COULEURS = {"mSurface": "#1e1e2e", "mOnSurface": "#cdd6f4", "mPrimary": "#cba6f7", "mOnPrimary": "#11111b",
                "mSecondary": "#89b4fa", "mTertiary": "#a6e3a1"}

    def couleurs_lua(self, style, themes):
        """Lance nc-theme-sync pour ce style et rend le fichier Hyprland généré (None s'il manque)."""
        self.env["NC_THEMES_DIR"] = str(themes)
        (self.home / ".config/noctalia").mkdir(parents=True, exist_ok=True)
        (self.home / ".config/noctalia/colors.json").write_text(json.dumps(self.COULEURS))
        self.nc("set", "STYLE", style)
        out = self.home / ".config/hypr/nc/couleurs.lua"
        if out.exists():
            out.unlink()
        r = self.nc(script="nc-theme-sync")
        self.assertEqual(r.returncode, 0, r.stderr)
        return out.read_text(encoding="utf-8")

    def test_meme_sortie_qu_avec_les_themes_absents(self):
        vide = self.r / "vide"
        vide.mkdir()
        for style in ("apple", "nord"):
            with self.subTest(style=style):
                self.assertEqual(self.couleurs_lua(style, self.themes), self.couleurs_lua(style, vide))

    def test_apple_gris_et_noire_autre_degrade(self):
        apple = self.couleurs_lua("apple", self.themes)
        self.assertIn('active_border   = "rgba(ffffff38)"', apple)
        self.assertIn("rgba(00000099)", apple)
        nord = self.couleurs_lua("nord", self.themes)
        self.assertIn("angle = 45", nord.split("inactive_border")[0])

    def test_le_fichier_du_theme_decide(self):
        self.ecrire_theme("gris", theme_sync={"bordure": "gris", "ombre": "noire"})
        a = self.couleurs_lua("gris", self.themes)
        self.ecrire_theme("gris", theme_sync={"bordure": "degrade", "ombre": "coloree"})
        self.assertNotEqual(a, self.couleurs_lua("gris", self.themes))


    def kitty(self, style):
        self.couleurs_lua(style, self.themes)
        return (self.home / ".config/kitty/themes/noctalia-dynamic.conf").read_text(encoding="utf-8")

    def test_palette_custom_couleurs_exactes_du_terminal(self):
        """Une palette « custom » du thème (Retro, Synthwave, Apple) donne au terminal ses couleurs exactes ;
        une palette intégrée à Noctalia : couleurs recalculées comme avant."""
        pal = self.home / ".config/noctalia/palettes"
        pal.mkdir(parents=True)
        shutil.copy(REPO / "home/.config/noctalia/palettes/Retro.json", pal / "Retro.json")
        self.ecrire_theme("vert", palette={"source": "custom", "nom": "Retro"})
        self.assertIn("color2 #33ff66", self.kitty("vert"))
        self.assertIn("color3 #ffb000", self.kitty("vert"))
        self.ecrire_theme("vert", palette={"source": "builtin", "nom": "Nord"})
        self.assertNotIn("color2 #33ff66", self.kitty("vert"))
        self.ecrire_theme("vert", palette={"source": "custom", "nom": "../../x"})     # nom refusé : rien de lu ailleurs
        self.assertNotIn("color2 #33ff66", self.kitty("vert"))


if __name__ == "__main__":
    unittest.main()

"""Réglages d'allure de l'île (Couleurs.qml, Ile.qml, Texte.qml, nc-reglages) : ILE_RAYON, ILE_CONTOUR_EPAISSEUR, ILE_VERRE,
ILE_POLICE, ILE_ANIM, ILE_LUEUR, ILE_MAJUSCULES.

- Hors écran, avec le vrai qs (« qs -p ») : le vrai Couleurs.qml, un Reglages de remplacement changé pendant l'essai.
  Défauts = allure d'avant (rayons 15/42/28/32, contour 2, opacité 1, Adwaita Sans, ressort 3.4/0.34/0.36, 280 ms OutCubic,
  220 ms, 170 ms) ; extrêmes acceptés ; valeur invalide ou hors bornes = défaut ; police absente = Adwaita Sans ; rayon 0 :
  un rectangle sans coin, 200 % : doublé mais jamais plus grand que la demi-taille.
- Source : pas de composant neuf dans un .qml existant (comparé à origin/main), pas de flou, réglages déclarés dans « Île ».
HOME, XDG_* et TMPDIR sont ceux du dossier temporaire."""
import json
from pathlib import Path
import os
import re
import runpy
import shutil
import subprocess
import tempfile
import unittest
import warnings
from unittest.mock import patch

from tests import _ile_hors_ecran as H

REPO = H.REPO
QML = H.QML
CLES = ("ILE_RAYON", "ILE_CONTOUR_EPAISSEUR", "ILE_VERRE", "ILE_POLICE", "ILE_ANIM", "ILE_LUEUR", "ILE_MAJUSCULES")

SHELL = """
    Rectangle { id: carre; objectName: "carre"; width: 100; height: 30; radius: Couleurs.rayon(15, 100, 30) }
    function sortie(v) {
        Reglages.valeurs = v
        console.log("R:" + JSON.stringify({ rayon: [Couleurs.rayon(15, 100, 30), Couleurs.rayon(42, 800, 700), Couleurs.rayon(28, 500, 60), Couleurs.rayon(32, 320, 90), Couleurs.rayon(15, 20, 8)],
            epaisseur: Couleurs.epaisseur, verre: Couleurs.verre, police: Couleurs.police, anim: Couleurs.animNom,
            ressort: [Couleurs.anim.raideur, Couleurs.anim.amortiL, Couleurs.anim.amortiH, Couleurs.anim.duree, Couleurs.anim.courbe === Easing.OutCubic, Couleurs.anim.contour, Couleurs.anim.spot],
            lueur: Couleurs.lueur, maj: Couleurs.majuscules, carre: carre.radius, page: Couleurs.rayon(42, 432, 600),
            jauge: Qt.colorEqual(Couleurs.jauge, Couleurs.texte) ? "texte" : (Qt.colorEqual(Couleurs.jauge, Couleurs.accent) ? "accent" : "autre") }))
    }
    Timer { interval: 300; running: true; onTriggered: parent.fin() }
    function fin() {
        var cas = %s
        for (var i = 0; i < cas.length; i++) sortie(cas[i])
        console.log("POLICE:" + Qt.fontFamilies()[0])
        console.log("FINI"); Qt.exit(0)
    }
"""


def lancer_cas(cas):
    with tempfile.TemporaryDirectory(prefix="nc-allure-") as d:
        root = H.preparer(d, ("Couleurs",))
        (root / "shell.qml").write_text(H.ENTETE + "ShellRoot {\n" + H.OUTILS + SHELL % json.dumps(cas) + "\n}\n")
        code, sortie = H.lancer(root, delai=60)
    for e in H.ERREURS:
        if e in sortie:
            raise AssertionError(sortie)
    if "FINI" not in sortie:
        raise AssertionError(sortie)
    return [json.loads(m) for m in re.findall(r"R:(\{.*\})", sortie)], re.search(r"POLICE:(.*)", sortie).group(1).strip()


@unittest.skipUnless(shutil.which("qs"), "Quickshell requis")
class HorsEcran(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _, cls.installee = lancer_cas([])
        cls.cas = [
            {},                                                                                 # 0 défauts
            {"ILE_RAYON": "carre"}, {"ILE_RAYON": "doux"}, {"ILE_RAYON": "rond"},              # 1 2 3
            {"ILE_RAYON": "0"}, {"ILE_RAYON": "200"}, {"ILE_RAYON": "50"},                     # 4 5 6
            {"ILE_RAYON": "201"}, {"ILE_RAYON": "-3"}, {"ILE_RAYON": "abc"}, {"ILE_RAYON": ""},  # 7 8 9 10
            {"ILE_CONTOUR_EPAISSEUR": "0"}, {"ILE_CONTOUR_EPAISSEUR": "4"}, {"ILE_CONTOUR_EPAISSEUR": "5"},  # 11 12 13
            {"ILE_CONTOUR_EPAISSEUR": "-1"}, {"ILE_CONTOUR_EPAISSEUR": "x"},                   # 14 15
            {"ILE_VERRE": "85"}, {"ILE_VERRE": "100"}, {"ILE_VERRE": "84"}, {"ILE_VERRE": "101"},  # 16-19
            {"ILE_VERRE": "0"}, {"ILE_VERRE": "abc"},                                           # 20 21
            {"ILE_POLICE": cls.installee}, {"ILE_POLICE": "Police Qui N Existe Pas"}, {"ILE_POLICE": ""},  # 22 23 24
            {"ILE_ANIM": "doux"}, {"ILE_ANIM": "vif"}, {"ILE_ANIM": "ressort"}, {"ILE_ANIM": "sec"},  # 25-28
            {"ILE_ANIM": "bizarre"}, {"ILE_ANIM": "constructor"}, {"ILE_ANIM": ""},            # 29 30 31
            {"ILE_LUEUR": "oui"}, {"ILE_LUEUR": "non"}, {"ILE_LUEUR": "peut-etre"},            # 32 33 34
            {"ILE_MAJUSCULES": "oui"}, {"ILE_MAJUSCULES": "non"}, {"ILE_MAJUSCULES": "1"},     # 35 36 37
            {"ILE_RAYON": "normal"}, {"ILE_RAYON": "pilule"},                                   # 38 39 (ancien nom : invalide)
            {"ILE_ACCENTS": "accent"}, {"ILE_ACCENTS": "texte"}, {"ILE_ACCENTS": "rose"},      # 40 41 42
            {"ILE_POLICE": "Police Absente, " + cls.installee}, {"ILE_POLICE": " %s ,Autre" % cls.installee},  # 43 44
            {"ILE_POLICE": "Absente Une, Absente Deux"}, {"ILE_POLICE": ","},                   # 45 46
        ]
        cls.r, _ = lancer_cas(cls.cas)

    def test_tous_les_cas_ont_tourne(self):
        self.assertEqual(len(self.r), len(self.cas))

    def test_defauts_egaux_a_avant(self):
        d = self.r[0]
        self.assertEqual(d["rayon"], [15, 42, 28, 32, 4])      # rayons d'origine ; le dernier : plafond de la demi-taille
        self.assertEqual((d["epaisseur"], d["verre"], d["police"], d["anim"]), (2, 1, "Adwaita Sans", "ressort"))
        self.assertEqual(d["ressort"], [3.4, 0.34, 0.36, 280, True, 220, 170])
        self.assertEqual((d["lueur"], d["maj"]), (False, False))
        self.assertEqual(d["jauge"], "texte")

    def test_valeurs_invalides_donnent_le_defaut(self):
        for i in (7, 8, 9, 10, 38, 39, 13, 14, 15, 18, 19, 20, 21, 23, 24, 29, 30, 31, 34, 37, 41, 42):
            with self.subTest(cas=self.cas[i]):
                self.assertEqual(self.r[i], self.r[0])

    def test_rayon_carre_et_rond(self):
        for i in (1, 4):
            with self.subTest(cas=self.cas[i]):
                self.assertEqual(self.r[i]["rayon"], [0, 0, 0, 0, 0])
                self.assertEqual(self.r[i]["carre"], 0)           # un vrai Rectangle : aucun coin
        # 200 % : doublé, mais jamais au-delà de la demi-taille (100x30 : 15 ; 500x60 : 30 ; 320x90 : 45 ; 20x8 : 4)
        self.assertEqual(self.r[3]["rayon"], [15, 84, 30, 45, 4])
        self.assertEqual(self.r[5]["rayon"], self.r[3]["rayon"])
        self.assertEqual(self.r[3]["carre"], 15)                  # la pilule fermée reste une pilule
        self.assertEqual(self.r[2]["rayon"], [7.5, 21, 14, 16, 4])
        self.assertEqual(self.r[6]["rayon"], self.r[2]["rayon"])

    def test_epaisseur(self):
        self.assertEqual([self.r[i]["epaisseur"] for i in (11, 12)], [0, 4])

    def test_verre_borne(self):
        self.assertEqual([self.r[i]["verre"] for i in (16, 17)], [0.85, 1])
        for i in (18, 19, 20, 21):
            self.assertEqual(self.r[i]["verre"], 1, self.cas[i])

    def test_police(self):
        self.assertEqual(self.r[22]["police"], self.installee)
        self.assertEqual(self.r[23]["police"], "Adwaita Sans")
        self.assertEqual(self.r[24]["police"], "Adwaita Sans")
        # Liste : la première installée, espaces ignorés ; aucune : Adwaita Sans
        self.assertEqual([self.r[i]["police"] for i in (43, 44, 45, 46)],
                         [self.installee, self.installee, "Adwaita Sans", "Adwaita Sans"])

    def test_animations(self):
        self.assertEqual(self.r[27], self.r[0])
        vus = {tuple(self.r[0]["ressort"][:4])}
        for i, n in {25: "doux", 26: "vif", 28: "sec"}.items():
            self.assertEqual(self.r[i]["anim"], n)
            vus.add(tuple(self.r[i]["ressort"][:4]))
        self.assertEqual(len(vus), 4)

    def test_lueur_et_majuscules(self):
        self.assertEqual([self.r[i]["lueur"] for i in (32, 33, 34)], [True, False, False])
        self.assertEqual([self.r[i]["maj"] for i in (35, 36, 37)], [True, False, False])


class Source(unittest.TestCase):
    def test_pas_de_composant_neuf(self):
        r = subprocess.run(["git", "diff", "origin/main", "--", "home/.config/quickshell/nc-ile"], cwd=REPO,
                           capture_output=True, text=True)
        if r.returncode != 0:
            self.skipTest("origin/main absent")
        neufs = [l for l in r.stdout.splitlines() if re.match(r"\+\s*component\s", l)]
        self.assertEqual(neufs, [])

    def test_pas_de_flou(self):
        for nom in ("Couleurs.qml", "Ile.qml", "Texte.qml"):
            code = re.sub(r"//.*", "", (QML / nom).read_text())
            self.assertNotRegex(code, r"MultiEffect|FastBlur|GaussianBlur", nom)

    def test_ile_lit_les_reglages(self):
        ile = (QML / "Ile.qml").read_text()
        for attendu in ("Couleurs.rayon(", "Qt.alpha(Couleurs.fond, Couleurs.verre)", "Couleurs.epaisseur",
                        "Mouvement.pourEcran", "fen.mouv.raideur", "fen.mouv.duree", "fen.mouv.dureeSpot", "Couleurs.lueur"):
            self.assertIn(attendu, ile)
        texte = (QML / "Texte.qml").read_text()
        self.assertIn("Couleurs.majuscules", texte)
        self.assertIn("font.family: Couleurs.police", texte)

    def test_aucune_police_en_dur(self):
        # Toute l'île suit ILE_POLICE : « Adwaita Sans » n'est écrit que dans Couleurs.qml (le repli)
        for f in sorted(QML.glob("*.qml")):
            if f.name != "Couleurs.qml":
                with self.subTest(fichier=f.name):
                    self.assertNotIn("Adwaita Sans", re.sub(r"//.*", "", f.read_text()))

    def test_reglages_declares(self):
        with tempfile.TemporaryDirectory() as d, patch.dict(os.environ, HOME=d), warnings.catch_warnings():
            warnings.simplefilter("ignore", ResourceWarning)
            reglages = runpy.run_path(str(REPO / "home/.local/bin/nc-reglages"))
        attendu = {"ILE_RAYON": "auto", "ILE_CONTOUR_EPAISSEUR": "2", "ILE_VERRE": "100", "ILE_POLICE": "Adwaita Sans",
                   "ILE_ANIM": "ressort", "ILE_LUEUR": "non", "ILE_MAJUSCULES": "non"}
        for c in CLES:
            with self.subTest(cle=c):
                r = reglages["PAR_CLE"][c]
                self.assertEqual(r.defaut, attendu[c])
                self.assertEqual(r.section, reglages["PAR_CLE"]["ILE_HEURE"].section)


class AvantLesThemes(HorsEcran):
    """Allure par défaut = constantes de Ile.qml et Texte.qml d'avant les thèmes (lignes figées dans
    tests/donnees/styles-avant-themes.json, commit 40eb708)."""
    def test_constantes_d_avant(self):
        ref = json.loads((Path(__file__).resolve().parent / "donnees/styles-avant-themes.json").read_text(encoding="utf-8"))
        lignes = "\n".join(ref["lignes_ile"])
        d = self.r[0]
        rayons = re.search(r"radius: fen\.ouverte \? \(fen\.recherche \? (\d+) : (\d+)\) : \(fen\.banniere \|\| fen\.enCarte \? (\d+) : (\d+)\)", lignes)
        recherche, ouverte, carte, pilule = map(int, rayons.groups())
        self.assertEqual(d["rayon"][:4], [pilule, ouverte, recherche, carte])
        self.assertEqual(d["page"], ouverte)                  # page ouverte réelle (432 x 600) : 42, le plafond ne joue pas
        self.assertEqual(d["epaisseur"], int(re.search(r"aContour \? (\d+) : 0", lignes)[1]))
        largeur = re.search(r"on width \{[^}]*spring: ([\d.]+); damping: ([\d.]+)", lignes)
        hauteur = re.search(r"on height \{[^}]*spring: ([\d.]+); damping: ([\d.]+)", lignes)
        rayon_anim = re.search(r"on radius \{[^}]*duration: (\d+); easing\.type: Easing\.OutCubic", lignes)
        couleur_contour = re.search(r"readonly property real e:.*\n.*duration: (\d+)", lignes)
        self.assertEqual(d["ressort"][:5], [float(largeur[1]), float(largeur[2]), float(hauteur[2]), int(rayon_anim[1]), True])
        self.assertEqual(d["ressort"][5], int(couleur_contour[1]))
        self.assertEqual(d["police"], re.search(r'font\.family: "([^"]+)"', lignes)[1])
        self.assertEqual(float(hauteur[1]), float(largeur[1]))


class Accents(HorsEcran):
    def test_accent(self):
        self.assertEqual(self.r[40]["jauge"], "accent")

    def test_barres_branchees(self):
        """Les barres (jauges de Système, musique, volume) prennent Couleurs.jauge ; les chiffres gardent leur couleur."""
        q = Path(__file__).resolve().parents[1] / "home/.config/quickshell/nc-ile"
        self.assertIn("color: Qt.colorEqual(me.couleur, Couleurs.texte) ? Couleurs.jauge : me.couleur", (q / "Systeme.qml").read_text())
        self.assertEqual((q / "Musique.qml").read_text().count("Couleurs.jauge"), 2)
        self.assertEqual((q / "Compact.qml").read_text().count("Couleurs.jauge"), 2)


if __name__ == "__main__":
    unittest.main()

"""Carrousel des thèmes de l'île (ChoixTheme.qml). Sources : aucun component inline dans les .qml touchés, ouverture par l'IPC
« themes », la recherche et le raccourci. Hors écran (vrai qs lancé par « qs -p », HOME et XDG_* isolés, faux nc-reglages qui
note ses arguments, vraies touches par QtTest) : nombre de cartes impair (5, ou 3 si l'écran est étroit), carte du milieu plus
grande, carte du thème actif au milieu, flèches, Entrée = « set STYLE <nom> » (liste d'arguments), Échap = rien n'est changé,
liste vide = aucune carte et aucune commande. Sauté sans Quickshell."""
import json
import re
import shutil
import tempfile
import textwrap
import unittest
from pathlib import Path

from tests import _ile_hors_ecran as H

REPO = Path(__file__).resolve().parents[1]
QML = REPO / "home/.config/quickshell/nc-ile"
THEMES = [{"nom": n, "libelle": n.capitalize(), "actif": n == "gamma", "miniature": "",
           "couleurs": {"surface": "#202020", "primary": "#ff8800", "secondary": "#00aaff", "tertiary": "#88ff00", "onSurface": "#eeeeee"},
           "reglages": {"ILE_RAYON": "rond", "ILE_MAJUSCULES": "oui"}} for n in ("alpha", "beta", "gamma", "delta", "epsilon")]
FAUX = """case "$1" in
  themes) cat "@ROOT@/themes.json" ;;
esac
exit 0
"""
OUTILS = """
 function cartes() { return tous(fen.contentItem, "nc-themes-centre-2").concat(tous(fen.contentItem, "nc-themes-autre-0"),
   tous(fen.contentItem, "nc-themes-autre-1"), tous(fen.contentItem, "nc-themes-autre-3"), tous(fen.contentItem, "nc-themes-autre-4")).filter(c => c.visible) }
"""


def lire(nom):
    return (QML / nom).read_text()


def fenetre_hors_ecran(largeur):
    """ChoixTheme.qml dans une fenêtre ordinaire (la FloatingWindow de Quickshell n'existe pas hors écran)."""
    s = lire("ChoixTheme.qml")
    assert "FloatingWindow {" in s
    s = s.replace("FloatingWindow {", "Window {")
    for l in ("    implicitWidth: ct.largeurFenetre\n", "    implicitHeight: 360\n", "    minimumSize: Qt.size(420, 300)\n", "    onClosed: ct.fermer()\n"):
        assert l in s, l
        s = s.replace(l, "")
    assert "ct.screen ? ct.screen.width : 1600" in s
    s = s.replace("ct.screen ? ct.screen.width : 1600", str(largeur))
    return s.replace('    color: "transparent"\n', '    color: "transparent"; width: 1060; height: 360; visible: true\n')


class Sources(unittest.TestCase):
    def test_aucun_component_inline(self):
        for nom in ("ChoixTheme.qml", "shell.qml", "Recherche.qml"):
            self.assertIsNone(re.search(r"^\s*component\s+\w+\s*:", lire(nom), re.M), nom)

    def test_ouvertures(self):
        shell = lire("shell.qml")
        self.assertIn("function themes()", shell)
        self.assertIn("ChoixTheme {", shell)
        self.assertIn('"ipc", "call", "ile", "themes"', lire("Recherche.qml"))
        self.assertIn('cmd("qs -c nc-ile ipc call ile themes")', (REPO / "home/.config/hypr/nc/raccourcis.lua").read_text())

    def test_application_par_liste_d_arguments(self):
        s = lire("ChoixTheme.qml")
        self.assertIn('appliquer.command = [ct.bin, "set", "STYLE", ct.themes[ct.centre].nom]', s)
        self.assertNotRegex(s, r"\bsh\b|bash|-c\"")


@unittest.skipUnless(shutil.which("qs"), "Quickshell requis")
class HorsEcran(unittest.TestCase):
    def lancer(self, corps, themes=THEMES, largeur=1600):
        with tempfile.TemporaryDirectory(prefix="nc-choixtheme-") as d:
            root = H.preparer(d, ("Couleurs", "Texte", "Ico"), extra={"ChoixTheme.qml": fenetre_hors_ecran(largeur)})
            bin_ = root / "home/.local/bin"
            bin_.mkdir(parents=True)
            H.faux(root, "nc-reglages", FAUX.replace("@ROOT@", str(root)))
            (bin_ / "nc-reglages").symlink_to(root / "bin/nc-reglages")
            (root / "themes.json").write_text(json.dumps(themes))
            (root / "shell.qml").write_text(
                H.ENTETE + "import QtTest\nShellRoot {\n id: racine\n property var fen: null\n property int etape: 0\n property int ticks: 0\n"
                + " property int fermes: 0\n TestCase { id: touches; name: \"Touches\"; when: false }\n" + H.OUTILS + OUTILS
                + " function ouvrir() { var c = Qt.createComponent(\"ChoixTheme.qml\"); verifier(c.status === Component.Ready, c.errorString())\n"
                + "   fen = c.createObject(racine); fen.fermer.connect(function() { fermes++ }) }\n"
                + textwrap.dedent(corps) + "\n Timer { interval: 15000; running: true; onTriggered: { console.error(\"ECHEC délai\"); Qt.exit(3) } }\n}\n")
            _, sortie = H.lancer(root, delai=40)
            for e in H.ERREURS:
                self.assertNotIn(e, sortie, sortie)
            self.assertIn("FINI", sortie, sortie)
            return [x for x in H.journal(root).splitlines() if not x.startswith("nc-reglages themes")]

    ATTENDRE = '''
            Timer { interval: 80; running: true; repeat: true; onTriggered: {
                if (etape === 0) { ouvrir(); etape++; return }
                ticks++
                if (ticks < 10) return
                if (etape === 1) { etape++; fen.cible.forceActiveFocus(); ticks = 0; return }
    '''

    def test_cinq_cartes_centrale_plus_grande_et_actif_au_milieu(self):
        j = self.lancer(self.ATTENDRE + '''
                var l = cartes()
                verifier(l.length === 5, "5 cartes, trouvé " + l.length)
                verifier(l.length % 2 === 1, "nombre impair")
                verifier(fen.centre === 2, "le thème actif (gamma) est au milieu, centre=" + fen.centre)
                var mid = trouver(fen.contentItem, "nc-themes-centre-2")
                var autre = trouver(fen.contentItem, "nc-themes-autre-1")
                verifier(mid.scale > autre.scale, "la carte du milieu est plus grande")
                verifier(Math.abs(mid.x + mid.width / 2 - fen.contentItem.width / 2) < 1, "la carte du milieu est centrée")
                console.log("FINI"); Qt.exit(0)
            } }
        ''')
        self.assertEqual(j, [])

    def test_trois_cartes_sur_ecran_etroit(self):
        j = self.lancer(self.ATTENDRE + '''
                verifier(fen.visibles === 3, "3 cartes visibles, trouvé " + fen.visibles)
                verifier(tous(fen.contentItem, "nc-themes-centre-1").length === 1, "carte du milieu d'indice 1")
                console.log("FINI"); Qt.exit(0)
            } }
        ''', largeur=800)
        self.assertEqual(j, [])

    def test_fleches_puis_entree_applique_le_bon_nom(self):
        j = self.lancer(self.ATTENDRE + '''
                if (etape === 2) { touches.keyClick(Qt.Key_Right); etape++; ticks = 0; return }
                if (ticks < 4) return
                if (etape === 3) { verifier(fen.centre === 3, "flèche droite : centre=" + fen.centre); touches.keyClick(Qt.Key_Return); etape++; ticks = 0; return }
                if (ticks < 10) return
                verifier(fermes > 0, "la fenêtre se ferme après l'application")
                console.log("FINI"); Qt.exit(0)
            } }
        ''')
        self.assertEqual(j, ["nc-reglages set STYLE delta"])

    def test_echap_ferme_sans_rien_changer(self):
        j = self.lancer(self.ATTENDRE + '''
                if (etape === 2) { touches.keyClick(Qt.Key_Left); touches.keyClick(Qt.Key_Escape); etape++; ticks = 0; return }
                if (ticks < 4) return
                verifier(fermes === 1, "Échap ferme, fermes=" + fermes)
                console.log("FINI"); Qt.exit(0)
            } }
        ''')
        self.assertEqual(j, [])

    def test_boucle_actif_en_tete_et_fleche_gauche_vers_le_dernier(self):
        """Thème actif en tête de liste : toujours deux voisines de chaque côté ; ← passe au dernier."""
        themes = [dict(t, actif=t["nom"] == "alpha") for t in THEMES]
        j = self.lancer(self.ATTENDRE + '''
                if (etape === 2) { verifier(fen.centre === 0 && cartes().length === 5, "5 cartes autour du premier, trouvé " + cartes().length)
                    touches.keyClick(Qt.Key_Left); etape++; ticks = 0; return }
                if (ticks < 4) return
                verifier(fen.centre === 4, "← depuis le premier : le dernier, centre=" + fen.centre)
                touches.keyClick(Qt.Key_Right); touches.keyClick(Qt.Key_Right)
                verifier(fen.centre === 1, "→ depuis le dernier : le premier puis le deuxième, centre=" + fen.centre)
                console.log("FINI"); Qt.exit(0)
            } }
        ''', themes=themes)
        self.assertEqual(j, [])

    def test_trois_themes_pas_de_doublon(self):
        j = self.lancer(self.ATTENDRE + '''
                verifier(cartes().length === 3, "3 thèmes : 3 cartes, trouvé " + cartes().length)
                console.log("FINI"); Qt.exit(0)
            } }
        ''', themes=THEMES[:3])
        self.assertEqual(j, [])

    def test_nom_court_et_parenthese_dessous(self):
        themes = [dict(t, libelle="Gamma très long (néons de nuit)") if t["nom"] == "gamma" else t for t in THEMES]
        j = self.lancer(self.ATTENDRE + '''
                var mid = trouver(fen.contentItem, "nc-themes-centre-2")
                var nom = trouver(mid, "nc-themes-nom"), pr = trouver(mid, "nc-themes-precision")
                verifier(nom.text === "Gamma très long" && nom.elide === Text.ElideNone, "nom court sans points : " + nom.text)
                verifier(pr.text === "néons de nuit" && pr.y > nom.y, "parenthèse dessous : " + pr.text)
                verifier(trouver(trouver(fen.contentItem, "nc-themes-autre-1"), "nc-themes-precision").text === "", "sans parenthèse : rien dessous")
                console.log("FINI"); Qt.exit(0)
            } }
        ''', themes=themes)
        self.assertEqual(j, [])

    def test_liste_vide_aucune_carte_aucune_commande(self):
        j = self.lancer(self.ATTENDRE + '''
                if (etape === 2) { verifier(cartes().length === 0, "aucune carte"); touches.keyClick(Qt.Key_Return); etape++; ticks = 0; return }
                if (ticks < 4) return
                console.log("FINI"); Qt.exit(0)
            } }
        ''', themes=[])
        self.assertEqual(j, [])



class RegleDeFenetre(unittest.TestCase):
    def test_flottante_centree_limitee_a_quickshell(self):
        """Sans règle, la fenêtre « Thèmes » serait rangée en tuile ; le titre seul viserait d'autres applis."""
        regles = (Path(__file__).resolve().parents[1] / "home/.config/hypr/nc/regles.lua").read_text(encoding="utf-8")
        self.assertRegex(regles, r'hl\.window_rule\(\{ name = "nc-themes-fenetre", match = \{ class = "\^\(org\.quickshell\)\$", '
                                 r'title = "\^\(Thèmes\|Themes\)\$" \}, float = true, center = true \}\)')
        qml = (Path(__file__).resolve().parents[1] / "home/.config/quickshell/nc-ile/ChoixTheme.qml").read_text(encoding="utf-8")
        self.assertIn('title: Reglages.t("Thèmes", "Themes")', qml)

if __name__ == "__main__":
    unittest.main()

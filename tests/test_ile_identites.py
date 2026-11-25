"""Rendus de l'île à palette identique : formes, cartouches et horloges des thèmes livrés."""
import json
import re
import shutil
import tempfile
import unittest

from tests import _ile_hors_ecran as H

THEMES = sorted(f.stem for f in (H.REPO / "home/.local/share/nc/themes").glob("*.json"))
PLANS = H.QML / "IdentitesIle.js"


class Catalogue(unittest.TestCase):
    def test_tous_les_themes_livres_ont_une_identite(self):
        plans = re.findall(r'^    "([\w-]+)": \{$', PLANS.read_text(), re.MULTILINE)
        self.assertCountEqual(plans, THEMES)


@unittest.skipUnless(shutil.which("qs"), "Quickshell requis")
class IdentitesHorsEcran(unittest.TestCase):
    def test_commutation_formes_cartouches_et_compositions(self):
        # Une seule fenêtre et une palette fixe : ni la couleur, ni la largeur globale ne départagent les thèmes.
        with tempfile.TemporaryDirectory(prefix="nc-ile-identites-") as d:
            root = H.preparer(d, ("Couleurs", "Texte", "HorlogeIle", "HabillageIle"),
                              etat='property string heure: "11:59 PM"; property string dateCourte: "Wed, Sep 23"',
                              extra={"IdentitesIle.js": PLANS.read_text()})
            shell = r'''
ShellRoot {
    id: test
    property var themes: THEMES_JSON
    property int index: 0
    property var cartouches: []
    property var compositions: []
    Window {
        width: 430; height: 210; visible: true
        Rectangle {
            id: rendu
            anchors.fill: parent
            color: "#ff00ff"
            HabillageIle {
                x: 6; y: 6; width: 214; height: 30
                plan: horloge.plan; page: false; dessinerFond: true
                fond: "#151515"; contour: 0; lueur: false
            }
            HorlogeIle { id: horloge; x: 224; y: 6 }
            HabillageIle {
                id: ouverte
                x: 6; y: 48; width: 408; height: 150
                plan: horloge.plan; page: true; dessinerFond: true
                fond: "#151515"; contour: 0; lueur: false
            }
        }
    }
    function changer() {
        if (index === themes.length) {
            if (verifier(new Set(cartouches).size === themes.length, "cartouches dupliqués")
                    && verifier(new Set(compositions).size === themes.length, "compositions dupliquées")) Qt.quit()
            return
        }
        Reglages.valeurs = { STYLE: themes[index] }
        cadre.start()
    }
    Component.onCompleted: changer()
    Timer {
        id: cadre
        interval: 40
        onTriggered: {
            const theme = test.themes[test.index]
            if (!verifier(Couleurs.themeActif === theme, "thème actif : " + theme)) return
            const plan = horloge.composition
            test.cartouches.push(ouverte.cartouche.aplat)
            test.compositions.push(JSON.stringify(horloge.plan.cadre(48, 54, horloge.plan.signe ? 12 : 0)))
            for (const nom of ["nc-ile-repos-heure", "nc-ile-repos-date"]) {
                const texte = trouver(horloge, nom)
                if (!verifier(texte && texte.visible && texte.x >= 0 && texte.x + texte.width <= plan.largeur + 1,
                              "texte hors de l'horloge : " + theme + " " + nom)) return
            }
            for (const bloc of plan.blocs) {
                if (!verifier(bloc.x >= 0 && bloc.x + bloc.largeur <= plan.largeur + 1 && bloc.y + bloc.hauteur <= 30,
                              "bloc hors de l'horloge : " + theme)) return
            }
            Reglages.valeurs = { STYLE: theme, ILE_DATE: "non" }
            if (!verifier(!trouver(horloge, "nc-ile-repos-date").visible && horloge.width <= plan.largeur + 1,
                          "date forcée : " + theme)) return
            Reglages.valeurs = { STYLE: theme }
            verifier(rendu.grabToImage(resultat => {
                if (!verifier(resultat.saveToFile(DOSSIER + "/" + theme + ".ppm"), "capture : " + theme)) return
                test.index++
                test.changer()
            }), "capture impossible : " + theme)
        }
    }
    Timer { interval: 9000; running: true; onTriggered: verifier(false, "délai des captures") }
}
'''
            shell = shell.replace("ShellRoot {", "ShellRoot {" + H.OUTILS, 1)
            shell = shell.replace("THEMES_JSON", json.dumps(THEMES)).replace("DOSSIER", json.dumps(str(root / "tmp")))
            (root / "shell.qml").write_text(H.ENTETE + shell)
            code, sortie = H.lancer(root, delai=12)
            self.assertEqual(code, 0, sortie)
            for e in H.ERREURS:
                self.assertNotIn(e, sortie, sortie)

            fermee, ouverte = set(), set()
            for theme in THEMES:
                image = (root / "tmp" / (theme + ".ppm")).read_bytes()
                entete = re.match(rb"P6\s+(\d+)\s+(\d+)\s+255\s", image)
                self.assertIsNotNone(entete, theme)
                w, h = map(int, entete.groups())
                self.assertEqual((w, h), (430, 210))
                pixels = memoryview(image)[entete.end():]

                def silhouette(x0, y0, largeur, hauteur):
                    return bytes(pixels[i:i+3] != b"\xff\x00\xff" for i in
                                 (3 * (y*w+x) for y in range(y0, y0+hauteur) for x in range(x0, x0+largeur)))

                for resultat, collection in ((silhouette(6, 6, 214, 30), fermee), (silhouette(6, 48, 408, 150), ouverte)):
                    self.assertIn(0, resultat, theme)
                    self.assertIn(1, resultat, theme)
                    self.assertNotIn(resultat, collection, f"Silhouette identique : {theme}")
                    collection.add(resultat)

    def test_point_matrice_et_point_choisi_gardent_le_cartouche_ouvert(self):
        from tests.test_refonte_ile_controle_reglages import RefonteHorsEcran

        shell = H.ENTETE + "ShellRoot {" + H.OUTILS + r'''
    id: test
    property int etape: 0
    Ile {
        id: fen
        visible: true
        modelData: ({ name: "identites", width: 1000, height: 760 })
    }
    Timer {
        interval: 40; running: true; repeat: true
        onTriggered: {
            const pilule = Etat.pilules.identites
            if (!pilule || !Reglages.valeurs.ILE_ANIM) return
            const auPoint = Math.abs(pilule.width - 10) < 0.5 && Math.abs(pilule.height - 10) < 0.5
            if (test.etape === 0) {
                Reglages.style = { STYLE: "matrice", ILE_FORME: "point" }
                test.etape++
            } else if (test.etape === 1 && auPoint) {
                if (!verifier(pilule.pointFerme && !trouver(fen.contentItem, "nc-ile-habillage-afficheur"),
                              "au repos, Matrice doit rester un point")) return
                Etat.ecranOuvert = "identites"
                test.etape++
            } else if (test.etape === 2 && pilule.pageIdentite) {
                const afficheur = trouver(fen.contentItem, "nc-ile-habillage-afficheur")
                if (!verifier(afficheur && afficheur.visible && afficheur.dessinerFond && afficheur.pointille,
                              "l'afficheur pointillé manque à Matrice ouverte")) return
                Etat.ecranOuvert = ""
                Reglages.style = { STYLE: "sakura" }
                Reglages.valeurs = { ILE_ANIM: "sec", ILE_FORME: "point" }
                test.etape++
            } else if (test.etape === 3 && auPoint) {
                if (!verifier(pilule.pointFerme, "le point choisi est ignoré")) return
                Etat.ecranOuvert = "identites"
                test.etape++
            } else if (test.etape === 4 && pilule.pageIdentite) {
                const floraison = trouver(fen.contentItem, "nc-ile-habillage-floraison")
                if (verifier(floraison && floraison.visible && !floraison.dessinerFond,
                             "le point choisi a fait perdre le cartouche Sakura")) Qt.quit()
            }
        }
    }
    Timer { interval: 5000; running: true; onTriggered: verifier(false, "transition en attente : " + test.etape) }
}
'''
        RefonteHorsEcran.lancer_qml(self, shell, reglages="ILE_ANIM=sec\n")

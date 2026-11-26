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

    def test_ouverte_change_de_composition_et_garde_les_commandes(self):
        from tests.test_refonte_ile_controle_reglages import RefonteHorsEcran

        shell = H.ENTETE + "import QtTest\nShellRoot {" + H.OUTILS + r'''
    id: test
    property var themes: THEMES_JSON
    property var dispositions: new Set()
    property int index: 0
    property int etape: 0
    TestCase { id: clic; when: false }
    Ile {
        id: fen
        visible: true
        modelData: ({ name: "compositions", width: 1000, height: 760 })
    }
    Timer {
        interval: 25; running: true; repeat: true
        onTriggered: {
            if (!Reglages.valeurs.ILE_ANIM) return
            const nom = test.themes[test.index]
            if (test.etape === 0) {
                Reglages.style = { STYLE: nom }
                if (!Etat.ecranOuvert) {
                    Etat.ecranOuvert = "compositions"
                    Etat.aller("essentiel")
                }
                test.etape = 1
                return
            }
            const page = trouver(fen.contentItem, "nc-ile-page-essentiel")
            const nav = trouver(fen.contentItem, "nc-ile-entete")
            const horloge = page && trouver(page, "nc-essentiel-temps")
            const actions = page && trouver(page, "nc-essentiel-controle")
            if (test.etape === 1) {
                if (Couleurs.themeActif !== nom || !actions || !actions.visible || !nav || !nav.visible
                    || Math.abs(Etat.pilules.compositions.height - fen.taille.height) > 0.5) return
                const zoneNav = nav.mapToItem(page, 0, 0)
                const separee = zoneNav.x + nav.width <= 0.5 || zoneNav.y + nav.height <= 0.5
                    || zoneNav.x >= page.width - 0.5 || zoneNav.y >= page.height - 0.5
                if (!verifier(separee, nom + ": les onglets recouvrent la page " + zoneNav
                              + " / " + page.width + "×" + page.height)) return
                const rect = actions.mapToItem(page, actions.width, actions.height)
                if (!verifier(rect.x <= page.width && rect.y <= page.height + 1, nom + ": action rognée")) return
                const date = trouver(page, "nc-essentiel-date")
                const etat = trouver(page, "nc-essentiel-etat")
                const finDate = date.mapToItem(etat, date.width, date.height)
                const debutDate = date.mapToItem(etat, 0, 0)
                if (!verifier(finDate.y <= 0.5 || finDate.x <= 0.5 || debutDate.x >= etat.width - 0.5,
                              nom + ": les indicateurs recouvrent la date")) return
                test.dispositions.add([Math.sign(zoneNav.x), Math.sign(zoneNav.y), nav.style,
                    Math.round(100 * horloge.x / page.width), horloge.y, horloge.alignement].join("/"))
                if (++test.index < test.themes.length) { test.etape = 0; return }
                fen.modelData = { name: "compositions", width: 440, height: 640 }
                Reglages.style = { STYLE: "nord" }
                test.etape = 2
            } else if (test.etape === 2) {
                if (!actions || !actions.visible || !nav.visible || nav.lateral) return
                const tab = trouver(nav, "nc-ile-onglet-notifications")
                if (!tab || !tab.visible) return
                clic.mouseClick(tab, tab.width / 2, tab.height / 2)
                if (!verifier(Etat.vueActive === "notifications", "l'onglet ne change pas de page")) return
                const ctrl = trouver(nav, "nc-ile-vers-controle")
                clic.mouseClick(ctrl, ctrl.width / 2, ctrl.height / 2)
                if (!verifier(Etat.controleOuvert && !Etat.controleAncre && !Etat.controleBord,
                              "un clic dans l'île ne doit pas transmettre d'ancre de barre")) return
                if (verifier(test.dispositions.size === test.themes.length, "compositions ouvertes dupliquées")) Qt.quit()
            }
        }
    }
    Timer {
        interval: 9000; running: true
        onTriggered: verifier(false, "attente : " + test.themes[test.index] + "/" + test.etape
              + ", état " + Etat.ecranOuvert + "/" + Etat.vueActive + ", hauteur " + Etat.pilules.compositions.height + "/" + fen.taille.height)
    }
}
'''
        shell = shell.replace("THEMES_JSON", json.dumps(THEMES))
        RefonteHorsEcran.lancer_qml(self, shell, reglages="ILE_ANIM=aucun\n")

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

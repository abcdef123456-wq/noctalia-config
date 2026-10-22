"""Fiche des raccourcis éditable (Fiche.qml, Super + /) hors écran, avec un faux nc-reglages : rien de montré avant
les raccourcis, le cadre du carrousel (Gabarit.qml : 8, 50, 1584 x 942, rayon 10 sous une barre de 42) en quatre
colonnes équilibrées, le frétillement seulement au survol, chaque action d'édition envoie le bon JSON (Raccourcis.qml), une capture interrompue rend
toujours ses raccourcis à Hyprland, « Remplacer » quand les touches sont prises ; les touches en groupes (« / »), les
lignes qui grandissent avec leurs pastilles et leur texte entier sans déborder, l'interrupteur (éteindre / rallumer) et
le − (supprimer l'un des tiens) ; et les contrastes du verre."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import unittest

REPO = Path(__file__).resolve().parents[1]
QML = REPO / "home/.config/quickshell/nc-ile"


def ligne(cle, nom, section, touches, mien="", desactive=False, modifie=False):
    ident = cle.split(":", 1)[1]
    return dict(cle="raccourci:" + ident, section="Raccourcis", sectionNom="Raccourcis", nom=nom, genre="raccourci", aide=section,
                valeur=touches, affiche=touches, modifie=modifie, ids=[ident], origs=[ident], mien=mien, desactive=desactive,
                change=False, modifiable=not desactive)


def catalogue():
    lignes = [ligne("r:64:q", "Fermer la fenêtre", "Fenêtres", "Super + Q"),
              ligne("r:64:t", "Terminal", "Applis et barre", "Super + Entrée", modifie=True),
              ligne("r:64:b", "Jeux", "Mes raccourcis", "Super + B", mien="SUPER + B"),
              ligne("r:64:d", "Verrouiller l'écran", "Système", "Super + L", desactive=True, modifie=True),
              ligne("r:64:loupe", "Loupe", "Système", "Super + Ctrl + molette / Super + = / Super + -"),
              ligne("r:64:media", "F1 à F12 : son, micro, luminosité, musique, clavier rétroéclairé et mode avion, comme sur le clavier",
                    "Système", "Touches média / Super + Maj + F23")]
    for section, n in (("Applis et barre", 16), ("Bureaux", 7), ("Fenêtres", 22), ("Système", 19), ("IA", 10), ("Souris", 8)):
        lignes += [ligne(f"r:{section}:{i}", f"Action {i} de {section}", section, "Super + Maj + " + str(i % 10)) for i in range(n)]
    return lignes


FAUX = r'''#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
H = Path(os.environ["HOME"])
with (H / "appels").open("a") as f: f.write(json.dumps(sys.argv[1:], ensure_ascii=False) + "\n")
if sys.argv[1] == "catalogue": print((H / "catalogue.json").read_text())
elif sys.argv[1] == "raccourci":
    d = json.loads(sys.argv[2])
    if d.get("touches") == "Super+Q" and not (H / "libre").exists():
        print("Super+Q est déjà pris : Fermer la fenêtre", file=sys.stderr); sys.exit(1)
    print("ok")
'''


@unittest.skipUnless(shutil.which("qs"), "Quickshell requis")
class FicheEditable(unittest.TestCase):
    def executer(self, scenario):
        with tempfile.TemporaryDirectory(prefix="nc-fiche-") as d:
            root = Path(d); q = root / "qml"; q.mkdir(); (root / "runtime").mkdir(mode=0o700)
            for nom in ("Raccourcis.qml", "Couleurs.qml", "Texte.qml", "Ico.qml", "Gabarit.qml", "Defilement.qml", "GroupeTouches.qml"):
                shutil.copy2(QML / nom, q / nom)
            source = (QML / "Fiche.qml").read_text()
            # Hors Hyprland : une fenêtre ordinaire de 1600 x 1000 à la place du calque Wayland
            source = source.replace("import Quickshell.Wayland\n", "import QtQuick.Window\n").replace("PanelWindow {", "Window {")
            for l in ("    anchors { top: true; bottom: true; left: true; right: true }\n", "    exclusionMode: ExclusionMode.Ignore\n",
                      "    WlrLayershell.layer: WlrLayer.Overlay\n", '    WlrLayershell.namespace: "nc-fiche"\n',
                      "    WlrLayershell.keyboardFocus: WlrKeyboardFocus.Exclusive\n"):
                self.assertIn(l, source); source = source.replace(l, "")
            source = source.replace("fiche.screen ? fiche.screen.width : 1600", "1600").replace("fiche.screen ? fiche.screen.height : 1000", "1000")
            (q / "Fiche.qml").write_text(source.replace('    color: "transparent"\n', '    color: "transparent"; width: 1600; height: 1000; visible: true\n'))
            (q / "Reglages.qml").write_text('pragma Singleton\nimport QtQuick\nQtObject {property bool en: false; property bool sobre: false;'
                                            ' function t(fr,en){return fr} function val(k,d){return d}}')
            (q / "qmldir").write_text("\n".join(("singleton " if n in ("Reglages", "Couleurs", "Raccourcis", "Gabarit") else "") + n + " 1.0 " + n + ".qml"
                                                for n in ("Reglages", "Couleurs", "Raccourcis", "Gabarit", "Fiche", "Texte", "Ico", "Defilement", "GroupeTouches")))
            (root / "catalogue.json").write_text(json.dumps(catalogue(), ensure_ascii=False))
            b = root / ".local/bin"; b.mkdir(parents=True)
            (b / "nc-reglages").write_text(FAUX); (b / "nc-reglages").chmod(0o755)
            (b / "nc-apps").write_text('#!/bin/sh\necho \'[{"id": "firefox", "name": "Firefox"}, {"id": "kitty", "name": "kitty"}]\'\n')
            (b / "nc-apps").chmod(0o755)
            (q / "shell.qml").write_text('''import QtQuick
import Quickshell
ShellRoot {
 id: racine
 property var fiche: null
 property int etape: 0
 property bool fermee: false
 function verifier(ok, m) { if (!ok) { console.error("ECHEC " + m); Qt.exit(2) } }
 function trouver(item, nom) { if (item.objectName === nom) return item; var e = item.children || []
   for (var i = 0; i < e.length; i++) { var r = trouver(e[i], nom); if (r) return r } return null }
 function cliquer(nom) { var z = trouver(fiche.contentItem, nom); verifier(z !== null, "introuvable : " + nom); z.clicked(null) }
 Timer { interval: 150; running: true; repeat: true; onTriggered: {
  if (etape === 0) { var c = Qt.createComponent("Fiche.qml"); verifier(c.status === Component.Ready, c.errorString())
                     fiche = c.createObject(racine); fiche.fermer.connect(function () { racine.fermee = true })
                     verifier(!fiche.montree || fiche.lignes.length > 0, "jamais de carte vide montrée"); etape++; return }
  if (fiche.lignes.length === 0 || Raccourcis.occupe) return
  SCENARIO
 } }
 Timer { interval: 12000; running: true; onTriggered: { console.error("ECHEC délai"); Qt.exit(3) } }
}
'''.replace("SCENARIO", scenario))
            env = dict(os.environ, HOME=d, QT_QPA_PLATFORM="offscreen", XDG_RUNTIME_DIR=str(root / "runtime"),
                       XDG_CACHE_HOME=str(root / "cache"), XDG_CONFIG_HOME=str(root / "config"))
            env.pop("WAYLAND_DISPLAY", None)
            r = subprocess.run(["qs", "--no-color", "-p", str(q / "shell.qml")], env=env, text=True, capture_output=True, timeout=30)
            # Les appels détachés (« capture fin ») peuvent finir juste après l'île : attendre qu'ils soient tous écrits
            f, avant, fin = root / "appels", None, time.monotonic() + 2
            while time.monotonic() < fin:
                maintenant = f.read_text() if f.exists() else ""
                if maintenant == avant:
                    break
                avant = maintenant; time.sleep(0.3)
            appels = [json.loads(l) for l in (avant or "").splitlines()]
            sortie = r.stdout + r.stderr
            self.assertNotIn("polish() loop", sortie, "boucle de mise en page")
            self.assertNotRegex(sortie, r"Fiche\.qml[^\n]*(ReferenceError|TypeError|Binding loop)", sortie)
            return r, appels

    def test_disposition_et_edition(self):
        r, appels = self.executer('''
  if (etape === 1) { verifier(fiche.montree, "montrée une fois les raccourcis lus")
                     var carte = trouver(fiche.contentItem, "nc-fiche-liste").parent
                     verifier(carte.x === 8 && carte.y === 50 && carte.width === 1584 && carte.height === 942,
                              "cadre du carrousel : " + carte.x + ", " + carte.y + ", " + carte.width + " x " + carte.height)
                     verifier(Gabarit.rayon === 10, "rayon du carrousel")
                     verifier(fiche.colonnes.length === 4 && fiche.colonnes.every(c => c.length > 0), "quatre colonnes : " + JSON.stringify(fiche.colonnes))
                     var h = fiche.colonnes.map(c => c.reduce((t, n) => t + fiche.hauteurSection(n), 0))
                     verifier(Math.max(...h) - Math.min(...h) < 400, "colonnes équilibrées : " + h)
                     verifier(!trouver(fiche.contentItem, "nc-fiche-moins-raccourci:64:q").visible, "hors édition : pas de −")
                     verifier(!trouver(fiche.contentItem, "nc-fiche-interrupteur-raccourci:64:q").visible, "hors édition : pas d'interrupteur")
                     var l = trouver(fiche.contentItem, "nc-fiche-ligne-raccourci:64:q")
                     l.survoler(); verifier(!l.fretille, "hors édition : pas de frétillement")
                     fiche.edition = true; etape++; return }
  if (etape === 2) { var l = trouver(fiche.contentItem, "nc-fiche-ligne-raccourci:64:q")
                     verifier(!l.fretille, "en édition : rien ne bouge sans survol")
                     l.survoler(); verifier(l.fretille, "au survol : frétille une fois")
                     cliquer("nc-fiche-interrupteur-raccourci:64:q"); etape++; return }     // interrupteur : éteindre
  if (etape === 3) { cliquer("nc-fiche-origine-raccourci:64:t"); etape++; return }           // ↺ : comme dans la config
  if (etape === 4) { var n = trouver(fiche.contentItem, "nc-fiche-nom-raccourci:64:b"); n.text = "Jeux vidéo"; n.accepted(); etape++; return }
  if (etape === 5) { cliquer("nc-fiche-touches-raccourci:64:t"); verifier(Raccourcis.capture !== null, "capture lancée"); etape++; return }
  if (etape === 6) { verifier(!trouver(fiche.contentItem, "nc-fiche-ligne-raccourci:64:q").fretille, "un seul frétillement")
                     fiche.quitter(); verifier(Raccourcis.capture === null, "capture rendue à la fermeture")
                     verifier(racine.fermee, "fermée tout de suite (le fondu est celui de Hyprland)"); Qt.quit() }''')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        actions = [json.loads(a[1]) for a in appels if a[0] == "raccourci"]
        self.assertEqual([(a["action"], a["ids"]) for a in actions[:2]], [("desactiver", ["64:q"]), ("origine", ["64:t"])])
        self.assertEqual((actions[2]["action"], actions[2]["mien"], actions[2]["nom"]), ("renommer", "SUPER + B", "Jeux vidéo"))
        captures = [a for a in appels if a[0] == "capture"]
        self.assertEqual(captures, [["capture"], ["capture", "fin"]], "Hyprland retrouve toujours ses raccourcis")

    def test_touches_et_lignes(self):
        r, appels = self.executer(TOUCHES_ET_LIGNES)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_interrupteur_et_moins(self):
        r, appels = self.executer('''
  if (etape === 1) { fiche.edition = true; etape++; return }
  if (etape === 2) { verifier(!trouver(fiche.contentItem, "nc-fiche-moins-raccourci:64:q").visible, "pas de − sur un raccourci de la config")
                     verifier(trouver(fiche.contentItem, "nc-fiche-moins-raccourci:64:b").visible, "− sur l'un des tiens")
                     verifier(!trouver(fiche.contentItem, "nc-fiche-interrupteur-raccourci:64:b").visible, "pas d'interrupteur sur l'un des tiens")
                     var i = trouver(fiche.contentItem, "nc-fiche-interrupteur-raccourci:64:d").parent
                     verifier(i.visible && i.opacity === 1 && trouver(fiche.contentItem, "nc-fiche-ligne-raccourci:64:d").opacity === 1,
                              "éteint : l'interrupteur reste à pleine opacité")
                     verifier(trouver(fiche.contentItem, "nc-fiche-pastilles-raccourci:64:d").opacity < 1, "éteint : touches grisées")
                     // Rien ne se chevauche : texte, ↺, interrupteur
                     var d = trouver(fiche.contentItem, "nc-fiche-description-raccourci:64:t")
                     var o = trouver(fiche.contentItem, "nc-fiche-origine-raccourci:64:t").parent
                     var it = trouver(fiche.contentItem, "nc-fiche-interrupteur-raccourci:64:t").parent
                     verifier(o.visible && d.x + d.width <= o.x && o.x + o.width <= it.x, "texte, ↺ puis interrupteur : " + [d.x + d.width, o.x, o.x + o.width, it.x])
                     DEBORDEMENT
                     cliquer("nc-fiche-interrupteur-raccourci:64:q")                     // allumé : éteindre
                     cliquer("nc-fiche-interrupteur-raccourci:64:d")                     // éteint : rallumer
                     cliquer("nc-fiche-moins-raccourci:64:q")                            // caché : ne fait rien
                     cliquer("nc-fiche-moins-raccourci:64:b"); etape++; return }         // l'un des tiens : supprimer
  if (etape === 3) Qt.quit()'''.replace("DEBORDEMENT", DEBORDEMENT))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        actions = [json.loads(a[1]) for a in appels if a[0] == "raccourci"]
        self.assertEqual([(a["action"], a["ids"]) for a in actions], [("desactiver", ["64:q"]), ("reactiver", ["64:d"]), ("retirer", ["64:b"])])
        self.assertEqual(actions[2]["mien"], "SUPER + B")

    def test_suggestions_d_applis(self):
        r, appels = self.executer('''
  if (etape === 1) { fiche.edition = true; cliquer("nc-fiche-ajouter"); etape++; return }
  if (etape === 2) { if (!fiche.applis.length) return; trouver(fiche.contentItem, "nc-fiche-cible").texte = "fire"; etape++; return }
  if (etape === 3) { verifier(trouver(fiche.contentItem, "nc-fiche-appli-kitty") === null || !trouver(fiche.contentItem, "nc-fiche-appli-kitty").visible, "kitty ne correspond pas")
                     cliquer("nc-fiche-appli-firefox"); verifier(trouver(fiche.contentItem, "nc-fiche-cible").texte === "firefox", "appli choisie")
                     trouver(fiche.contentItem, "nc-fiche-cible").texte = "bureau 3"; verifier(fiche.suggestions("bureau 3").length === 0, "pas d'appli pour un bureau")
                     etape++; return }
  if (etape === 4) Qt.quit()''')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_ajouter_et_remplacer(self):
        r, appels = self.executer('''
  if (etape === 1) { fiche.edition = true; cliquer("nc-fiche-ajouter"); etape++; return }
  if (etape === 2) { trouver(fiche.contentItem, "nc-fiche-cible").texte = "bureau 3"; cliquer("nc-fiche-choisir")
                     verifier(Raccourcis.capture && Raccourcis.capture.ajout, "capture d'un nouveau"); etape++; return }
  if (etape === 3) { fiche.tentative = { r: Raccourcis.capture, touches: "Super+Q" }; Raccourcis.finCapture("Super+Q"); etape++; return }
  if (etape === 4) { verifier(fiche.conflit !== null, "touches prises : Remplacer proposé"); cliquer("nc-fiche-remplacer"); etape++; return }
  if (etape === 5) Qt.quit()''')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        actions = [json.loads(a[1]) for a in appels if a[0] == "raccourci"]
        self.assertEqual([a["action"] for a in actions], ["ajouter", "desactiver", "ajouter"], actions)
        self.assertEqual((actions[0]["touches"], actions[0]["cible"]), ("Super+Q", "bureau 3"))
        self.assertEqual(actions[1]["ids"], ["64:q"], "l'autre raccourci, celui qui avait Super + Q")


# Aucune description ne sort de sa colonne, et chacune est entière (pas de « … », 3 lignes au plus)
DEBORDEMENT = '''var ds = []; (function tout(e) { if (e.objectName.indexOf("nc-fiche-description-") === 0) ds.push(e); (e.children || []).forEach(tout) })(fiche.contentItem)
                     verifier(ds.length === fiche.lignes.length, "une description par raccourci : " + ds.length)
                     ds.forEach(d => verifier(d.x >= 0 && d.x + d.width <= fiche.largeurColonne && d.contentWidth <= d.width + 0.5,
                                              "dans sa colonne : " + d.objectName + " " + [d.x, d.width, d.contentWidth, fiche.largeurColonne]))'''

TOUCHES_ET_LIGNES = '''
  if (etape === 1) { var loupe = fiche.lignes.find(r => r.cle === "raccourci:64:loupe")
                     verifier(JSON.stringify(fiche.groupes(loupe)) === JSON.stringify([["Super", "Ctrl", "molette"], ["Super", "="], ["Super", "-"]]),
                              "groupes : " + JSON.stringify(fiche.groupes(loupe)))
                     var media = fiche.lignes.find(r => r.cle === "raccourci:64:media")
                     verifier(JSON.stringify(fiche.groupes(media)) === JSON.stringify([["Touches média"], ["Super", "Maj", "F23"]]), "touches média")
                     verifier(fiche.norm(["Super", "Q"]) === fiche.norm("Super+Q") && fiche.norm("Super + Q") === "super+q", "norm")
                     // Loupe : deux rangées de pastilles, la description dessous, rien ne se chevauche
                     var l = trouver(fiche.contentItem, "nc-fiche-ligne-raccourci:64:loupe")
                     var p = trouver(fiche.contentItem, "nc-fiche-pastilles-raccourci:64:loupe")
                     var d = trouver(fiche.contentItem, "nc-fiche-description-raccourci:64:loupe")
                     verifier(l.longues && p.height >= 2 * 24 + 5, "deux rangées : " + p.height)
                     verifier(d.y >= p.y + p.height && l.height >= p.height + d.height, "description sous les pastilles : " + [p.y, p.height, d.y, d.height, l.height])
                     // Texte entier, sur plusieurs lignes, la ligne à sa hauteur
                     var m = trouver(fiche.contentItem, "nc-fiche-description-raccourci:64:media")
                     verifier(!m.truncated && m.lineCount >= 2 && m.lineCount <= 3, "description entière : " + [m.truncated, m.lineCount])
                     verifier(m.y >= 0 && m.y + m.height <= trouver(fiche.contentItem, "nc-fiche-ligne-raccourci:64:media").height, "dans sa ligne")
                     DEBORDEMENT
                     // Hors édition, un raccourci éteint reste là, grisé
                     var e = trouver(fiche.contentItem, "nc-fiche-pastilles-raccourci:64:d")
                     verifier(e !== null && e.visible && e.opacity < 1 && trouver(fiche.contentItem, "nc-fiche-description-raccourci:64:d").opacity < 1,
                              "éteint : visible et grisé")
                     fiche.edition = true; etape++; return }
  if (etape === 2) { DEBORDEMENT
                     Qt.quit() }'''.replace("DEBORDEMENT", DEBORDEMENT)


def luminance(c):
    def lin(v):
        v /= 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = (int(c[i:i + 2], 16) for i in (1, 3, 5))
    return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)


def melange(dessus, dessous, alpha):
    a, b = (tuple(int(c[i:i + 2], 16) for i in (1, 3, 5)) for c in (dessus, dessous))
    return "#" + "".join(f"{round(x * alpha + y * (1 - alpha)):02x}" for x, y in zip(a, b))


def contraste(a, b):
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


class VerreLisible(unittest.TestCase):
    """Le texte de la fiche reste lisible sur le verre, même sur le pire fond possible derrière (blanc derrière une
    palette sombre, noir derrière une claire) : 4,5:1 au moins, avec ou sans flou."""
    # fond, texte, texte secondaire, carte (palier(0.035) de nc-theme-sync ; celle d'Apple pour le noir)
    PALETTES = {"noir (Apple)": ("#000000", "#ffffff", "#98989d", "#1c1c1e"),
                "terminal sombre": ("#1c1d21", "#e6e6e6", "#9a9aa3", "#24252c"),
                "terminal clair": ("#f4f1ef", "#222222", "#5c5c66", "#ede4df")}

    def test_contrastes(self):
        source = (QML / "Fiche.qml").read_text()
        self.assertIn("readonly property real opaciteFond: verre ? 0.8 : 0.92", source)
        # Le verre du − et de l'interrupteur : la carte à 55 % ; l'interrupteur éteint, voilé du texte
        self.assertIn("color: zMoins.containsMouse ? Qt.alpha(Couleurs.carteSurvol, 0.75) : Qt.alpha(Couleurs.carte, 0.55)", source)
        self.assertIn("color: zMoins.containsMouse ? Couleurs.rouge : Couleurs.texte", source)
        self.assertIn("readonly property real voilePiste: 0.6", source)
        self.assertIn("color: interrupteur.allume ? Couleurs.accent : Qt.alpha(Couleurs.texte, fiche.voilePiste)", source)
        for nom, (fond, texte, secondaire, carte) in self.PALETTES.items():
            pire = "#ffffff" if luminance(fond) < 0.5 else "#000000"
            for alpha in (0.8, 0.92):
                derriere = melange(fond, pire, alpha)
                self.assertGreaterEqual(contraste(texte, derriere), 4.5, f"{nom}, {alpha}")
                self.assertGreaterEqual(contraste(secondaire, derriere), 3.0 if alpha == 0.8 else 4.5, f"{nom}, {alpha} (secondaire)")
                verre = melange(carte, derriere, 0.55)
                self.assertGreaterEqual(contraste(texte, verre), 4.5, f"{nom}, {alpha} (glyphe −)")
                self.assertGreaterEqual(contraste(melange(texte, verre, 0.6), derriere), 3.0, f"{nom}, {alpha} (interrupteur éteint)")


if __name__ == "__main__":
    unittest.main()

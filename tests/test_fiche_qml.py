"""Fiche des raccourcis éditable (Fiche.qml, Super + /) hors écran, avec un faux nc-reglages : rien de montré avant
les raccourcis, la taille des autres menus (Gabarit.qml) en deux colonnes équilibrées, le frétillement seulement au
survol, chaque action d'édition envoie le bon JSON (Raccourcis.qml), une capture interrompue rend
toujours ses raccourcis à Hyprland, « Remplacer » quand les touches sont prises ; et les contrastes du verre."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
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
              ligne("r:64:b", "Jeux", "Mes raccourcis", "Super + B", mien="SUPER + B")]
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
            for nom in ("Raccourcis.qml", "Couleurs.qml", "Texte.qml", "Ico.qml", "Gabarit.qml", "Defilement.qml"):
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
                                                for n in ("Reglages", "Couleurs", "Raccourcis", "Gabarit", "Fiche", "Texte", "Ico", "Defilement")))
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
            appels = [json.loads(l) for l in (root / "appels").read_text().splitlines()] if (root / "appels").exists() else []
            return r, appels

    def test_disposition_et_edition(self):
        r, appels = self.executer('''
  if (etape === 1) { verifier(fiche.montree, "montrée une fois les raccourcis lus")
                     var carte = trouver(fiche.contentItem, "nc-fiche-liste").parent
                     verifier(carte.width === 1040 && carte.height === 740, "taille des autres menus : " + carte.width + " x " + carte.height)
                     verifier(fiche.colonnes.length === 2 && fiche.colonnes[0].length && fiche.colonnes[1].length, "deux colonnes : " + JSON.stringify(fiche.colonnes))
                     var h = fiche.colonnes.map(c => c.reduce((t, n) => t + fiche.hauteurSection(n), 0))
                     verifier(Math.abs(h[0] - h[1]) < 400, "colonnes équilibrées : " + h)
                     verifier(!trouver(fiche.contentItem, "nc-fiche-moins-raccourci:64:q").visible, "hors édition : pas de −")
                     var l = trouver(fiche.contentItem, "nc-fiche-ligne-raccourci:64:q")
                     l.survoler(); verifier(!l.fretille, "hors édition : pas de frétillement")
                     fiche.edition = true; etape++; return }
  if (etape === 2) { var l = trouver(fiche.contentItem, "nc-fiche-ligne-raccourci:64:q")
                     verifier(!l.fretille, "en édition : rien ne bouge sans survol")
                     l.survoler(); verifier(l.fretille, "au survol : frétille une fois")
                     cliquer("nc-fiche-moins-raccourci:64:q"); etape++; return }             // − : désactiver
  if (etape === 3) { cliquer("nc-fiche-origine-raccourci:64:t"); etape++; return }           // ↺ : comme dans la config
  if (etape === 4) { var n = trouver(fiche.contentItem, "nc-fiche-nom-raccourci:64:b"); n.text = "Jeux vidéo"; n.accepted(); etape++; return }
  if (etape === 5) { cliquer("nc-fiche-touches-raccourci:64:t"); verifier(Raccourcis.capture !== null, "capture lancée"); etape++; return }
  if (etape === 6) { verifier(!trouver(fiche.contentItem, "nc-fiche-ligne-raccourci:64:q").fretille, "un seul frétillement")
                     fiche.quitter(); verifier(Raccourcis.capture === null, "capture rendue à la fermeture"); etape++; return }
  if (etape === 7) { verifier(racine.fermee, "fermée après le mouvement de sortie"); Qt.quit() }''')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        actions = [json.loads(a[1]) for a in appels if a[0] == "raccourci"]
        self.assertEqual([(a["action"], a["ids"]) for a in actions[:2]], [("desactiver", ["64:q"]), ("origine", ["64:t"])])
        self.assertEqual((actions[2]["action"], actions[2]["mien"], actions[2]["nom"]), ("renommer", "SUPER + B", "Jeux vidéo"))
        captures = [a for a in appels if a[0] == "capture"]
        self.assertEqual(captures, [["capture"], ["capture", "fin"]], "Hyprland retrouve toujours ses raccourcis")

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
    PALETTES = {"noir (Apple)": ("#000000", "#ffffff", "#98989d"), "terminal sombre": ("#1c1d21", "#e6e6e6", "#9a9aa3"),
                "terminal clair": ("#f4f1ef", "#222222", "#5c5c66")}

    def test_contrastes(self):
        source = (QML / "Fiche.qml").read_text()
        self.assertIn("readonly property real opaciteFond: verre ? 0.8 : 0.92", source)
        for nom, (fond, texte, secondaire) in self.PALETTES.items():
            pire = "#ffffff" if luminance(fond) < 0.5 else "#000000"
            for alpha in (0.8, 0.92):
                derriere = melange(fond, pire, alpha)
                self.assertGreaterEqual(contraste(texte, derriere), 4.5, f"{nom}, {alpha}")
                self.assertGreaterEqual(contraste(secondaire, derriere), 3.0 if alpha == 0.8 else 4.5, f"{nom}, {alpha} (secondaire)")


if __name__ == "__main__":
    unittest.main()

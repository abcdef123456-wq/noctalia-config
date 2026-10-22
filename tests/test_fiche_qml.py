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
    def executer(self, scenario, attendus=None, ia=None, ia_coupee=False):
        """attendus : une condition sur les appels relus (les écritures des processus peuvent finir après l'île, surtout
        sous charge) ; ia : le corps d'un faux nc-ia (None : nc-ia n'est pas installé) ; ia_coupee : IA_MODE=non."""
        with tempfile.TemporaryDirectory(prefix="nc-fiche-") as d:
            root = Path(d); q = root / "qml"; q.mkdir(); (root / "runtime").mkdir(mode=0o700)
            for nom in ("Raccourcis.qml", "Couleurs.qml", "Texte.qml", "Ico.qml", "Gabarit.qml", "Defilement.qml", "GroupeTouches.qml"):
                shutil.copy2(QML / nom, q / nom)
            source = (QML / "Fiche.qml").read_text()
            # Hors Hyprland : une fenêtre ordinaire de 1600 x 1000 à la place du calque Wayland
            source = source.replace("import Quickshell.Wayland\n", "import QtQuick.Window\n").replace("PanelWindow {", "Window {")
            # Calque Top, sous l'île (Overlay) : la pilule n'est plus couverte ; Overlay seulement devant un plein écran,
            # qui couvre le calque Top (la fiche y serait invisible en gardant le clavier)
            for l in ("import Quickshell.Hyprland\n", "    anchors { top: true; bottom: true; left: true; right: true }\n", "    exclusionMode: ExclusionMode.Ignore\n",
                      "    WlrLayershell.layer: Hyprland.activeToplevel && Hyprland.activeToplevel.lastIpcObject\n"
                      "                         && (Hyprland.activeToplevel.lastIpcObject.fullscreen || 0) > 0 ? WlrLayer.Overlay : WlrLayer.Top\n",
                      '    WlrLayershell.namespace: "nc-fiche"\n',
                      "    WlrLayershell.keyboardFocus: WlrKeyboardFocus.Exclusive\n"):
                self.assertIn(l, source); source = source.replace(l, "")
            source = source.replace("fiche.screen ? fiche.screen.width : 1600", "1600").replace("fiche.screen ? fiche.screen.height : 1000", "1000")
            (q / "Fiche.qml").write_text(source.replace('    color: "transparent"\n', '    color: "transparent"; width: 1600; height: 1000; visible: true\n'))
            mode = '"non"' if ia_coupee else '"auto"'
            (q / "Reglages.qml").write_text('pragma Singleton\nimport QtQuick\nQtObject {property bool en: false; property bool sobre: false;'
                                            f' property bool iaCoupee: {"true" if ia_coupee else "false"};'
                                            ' function t(fr,en){return fr} function val(k,d){return k === "IA_MODE" ? ' + mode + ' : d}}')
            (q / "qmldir").write_text("\n".join(("singleton " if n in ("Reglages", "Couleurs", "Raccourcis", "Gabarit") else "") + n + " 1.0 " + n + ".qml"
                                                for n in ("Reglages", "Couleurs", "Raccourcis", "Gabarit", "Fiche", "Texte", "Ico", "Defilement", "GroupeTouches")))
            (root / "catalogue.json").write_text(json.dumps(catalogue(), ensure_ascii=False))
            b = root / ".local/bin"; b.mkdir(parents=True)
            (b / "nc-reglages").write_text(FAUX); (b / "nc-reglages").chmod(0o755)
            (b / "nc-apps").write_text('#!/bin/sh\necho \'[{"id": "firefox", "name": "Firefox"}, {"id": "kitty", "name": "kitty"}]\'\n')
            (b / "nc-apps").chmod(0o755)
            if ia is not None:
                (b / "nc-ia").write_text(FAUX_IA.replace("CORPS", ia)); (b / "nc-ia").chmod(0o755)
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
 function visible(nom) { var z = trouver(fiche.contentItem, nom); return z !== null && z.visible }
 function capturer(chemin) { fiche.contentItem.grabToImage(function (r) { verifier(r.saveToFile(chemin), "capture : " + chemin); Qt.quit() }) }
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
            # Les appels détachés (« capture fin ») et les écritures peuvent finir juste après l'île : attendre, 2 s au
            # plus, que le journal ne bouge plus et contienne ce qu'on attend (attendus), avant de comparer
            f, avant, fin = root / "appels", None, time.monotonic() + 2
            while time.monotonic() < fin:
                maintenant = f.read_text() if f.exists() else ""
                lus = [json.loads(l) for l in maintenant.splitlines() if l.strip()]
                if maintenant == avant and (attendus is None or attendus(lus)):
                    break
                avant = maintenant; time.sleep(0.3)
            appels = [json.loads(l) for l in (avant or "").splitlines() if l.strip()]
            sortie = r.stdout + r.stderr
            self.assertNotIn("polish() loop", sortie, "boucle de mise en page")
            self.assertNotRegex(sortie, r"Fiche\.qml[^\n]*(ReferenceError|TypeError|Binding loop)", sortie)
            return r, appels

    def test_disposition_et_edition(self):
        r, appels = self.executer('''
  if (etape === 1) { verifier(fiche.montree, "montrée une fois les raccourcis lus")
                     verifier(visible("nc-fiche-plus") && !fiche.edition, "+ dans l'en-tête, même hors édition")
                     var plus = trouver(fiche.contentItem, "nc-fiche-plus"), mod = trouver(fiche.contentItem, "nc-fiche-modifier")
                     verifier(plus.y === mod.y && plus.x + plus.width <= mod.x, "+ à gauche de Modifier : " + [plus.x, plus.width, mod.x])
                     var vs = []; (function tout(e) { if (e.objectName === "nc-fiche-voile") vs.push(e); (e.children || []).forEach(tout) })(fiche.contentItem)
                     verifier(vs.length === fiche.colonnes.length && vs.every(v => v.radius === 10), "un voile arrondi sous chaque colonne")
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
                     verifier(racine.fermee, "fermée tout de suite (le fondu est celui de Hyprland)"); Qt.quit() }''',
                                  attendus=lambda a: len([x for x in a if x[0] == "raccourci"]) >= 3 and ["capture", "fin"] in a)
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
  if (etape === 3) Qt.quit()'''.replace("DEBORDEMENT", DEBORDEMENT),
                                  attendus=lambda a: len([x for x in a if x[0] == "raccourci"]) >= 3)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        actions = [json.loads(a[1]) for a in appels if a[0] == "raccourci"]
        self.assertEqual([(a["action"], a["ids"]) for a in actions], [("desactiver", ["64:q"]), ("reactiver", ["64:d"]), ("retirer", ["64:b"])])
        self.assertEqual(actions[2]["mien"], "SUPER + B")

    def test_suggestions_d_applis(self):
        r, appels = self.executer('''
  if (etape === 1) { cliquer("nc-fiche-ajouter"); verifier(fiche.edition && fiche.ajout, "+ ouvre la carte, en édition"); etape++; return }
  if (etape === 2) { if (!fiche.applis.length) return; trouver(fiche.contentItem, "nc-fiche-cible").texte = "fire"; etape++; return }
  if (etape === 3) { verifier(trouver(fiche.contentItem, "nc-fiche-appli-kitty") === null || !trouver(fiche.contentItem, "nc-fiche-appli-kitty").visible, "kitty ne correspond pas")
                     cliquer("nc-fiche-appli-firefox"); verifier(trouver(fiche.contentItem, "nc-fiche-cible").texte === "firefox", "appli choisie")
                     trouver(fiche.contentItem, "nc-fiche-cible").texte = "bureau 3"; verifier(fiche.suggestions("bureau 3").length === 0, "pas d'appli pour un bureau")
                     etape++; return }
  if (etape === 4) Qt.quit()''')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_ajouter_et_remplacer(self):
        r, appels = self.executer('''
  if (etape === 1) { cliquer("nc-fiche-ajouter"); etape++; return }
  if (etape === 2) { verifier(!visible("nc-fiche-ia"), "sans nc-ia : pas de champ pour l'IA")
                     trouver(fiche.contentItem, "nc-fiche-cible").texte = "bureau 3"; cliquer("nc-fiche-choisir")
                     verifier(Raccourcis.capture && Raccourcis.capture.ajout, "capture d'un nouveau"); etape++; return }
  if (etape === 3) { fiche.tentative = { r: Raccourcis.capture, touches: "Super+Q" }; Raccourcis.finCapture("Super+Q"); etape++; return }
  if (etape === 4) { verifier(fiche.conflit !== null, "touches prises : Remplacer proposé"); cliquer("nc-fiche-remplacer"); etape++; return }
  if (etape === 5) Qt.quit()''', attendus=lambda a: len([x for x in a if x[0] == "raccourci"]) >= 3)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        actions = [json.loads(a[1]) for a in appels if a[0] == "raccourci"]
        self.assertEqual([a["action"] for a in actions], ["ajouter", "desactiver", "ajouter"], actions)
        self.assertEqual((actions[0]["touches"], actions[0]["cible"]), ("Super+Q", "bureau 3"))
        self.assertEqual(actions[1]["ids"], ["64:q"], "l'autre raccourci, celui qui avait Super + Q")

    # ── « + Ajouter » par l'IA ──
    def test_ia_coupee_pas_de_champ(self):
        r, appels = self.executer('''
  if (etape === 1) { cliquer("nc-fiche-ajouter"); etape++; return }
  if (etape < 5) { etape++; return }                    // nc-ia actif a le temps de répondre
  if (etape === 5) { verifier(!fiche.iaPrete && !visible("nc-fiche-ia"), "IA coupée : aucun champ"); Qt.quit() }''',
                                  ia=PROPOSITION, ia_coupee=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertFalse([a for a in appels if a[0] == "ia-raccourci"], "l'IA n'est jamais appelée")

    def test_ia_propose_puis_ajouter(self):
        r, appels = self.executer('''
  if (etape === 1) { cliquer("nc-fiche-ajouter"); etape++; return }
  if (etape === 2) { if (!fiche.iaPrete) return
                     verifier(visible("nc-fiche-ia"), "IA permise : le champ"); verifier(!visible("nc-fiche-ia-proposition"), "rien de proposé avant")
                     trouver(fiche.contentItem, "nc-fiche-ia").texte = "Super + G ouvre Firefox"; fiche.proposer(); etape++; return }
  if (etape === 3) { if (!fiche.proposition) return
                     verifier(visible("nc-fiche-ia-proposition") && !visible("nc-fiche-ia"), "proposition montrée, éditable")
                     verifier(trouver(fiche.contentItem, "nc-fiche-ia-touches").texte === "Super+G", "touches proposées")
                     verifier(trouver(fiche.contentItem, "nc-fiche-ia-nom").texte === "Firefox", "nom proposé")
                     cliquer("nc-fiche-ia-annuler"); verifier(!fiche.proposition && visible("nc-fiche-ia"), "Annuler : rien")
                     fiche.proposer(); etape++; return }
  if (etape === 4) { if (!fiche.proposition) return
                     trouver(fiche.contentItem, "nc-fiche-ia-nom").texte = "Navigateur"; cliquer("nc-fiche-ia-ajouter")
                     verifier(!fiche.ajout, "carte refermée après Ajouter"); etape++; return }
  if (etape === 5) Qt.quit()''', ia=PROPOSITION, attendus=lambda a: any(x[0] == "raccourci" for x in a))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual([a[1:] for a in appels if a[0] == "ia-raccourci"], [["--json", "Super + G ouvre Firefox"]] * 2)
        actions = [json.loads(a[1]) for a in appels if a[0] == "raccourci"]
        self.assertEqual(actions, [{"action": "ajouter", "touches": "Super+G", "cible": "firefox", "nom": "Navigateur"}],
                         "un seul ajout, après le clic, par le chemin de l'ajout à la main")

    def test_ia_json_invalide_et_touches_prises(self):
        r, appels = self.executer('''
  if (etape === 1) { cliquer("nc-fiche-ajouter"); etape++; return }
  if (etape === 2) { if (!fiche.iaPrete) return
                     trouver(fiche.contentItem, "nc-fiche-ia").texte = "n'importe quoi"; fiche.proposer(); etape++; return }
  if (etape === 3) { if (!fiche.erreurIA) return
                     verifier(visible("nc-fiche-ia-erreur") && !fiche.proposition, "JSON invalide : un message, rien de proposé")
                     trouver(fiche.contentItem, "nc-fiche-ia").texte = "Super + Q ouvre Firefox"; fiche.proposer(); etape++; return }
  if (etape === 4) { if (!fiche.proposition) return
                     verifier(fiche.erreurIA === "", "message effacé"); cliquer("nc-fiche-ia-ajouter"); etape++; return }
  if (etape === 5) { verifier(fiche.conflit !== null && /déjà pris/.test(Raccourcis.message) && Raccourcis.erreur,
                              "touches prises : le même message, et Remplacer : " + Raccourcis.message)
                     verifier(visible("nc-fiche-remplacer"), "Remplacer montré"); Qt.quit() }''', ia=PROPOSITION_OU_INVALIDE,
                                  attendus=lambda a: any(x[0] == "raccourci" for x in a))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        actions = [json.loads(a[1]) for a in appels if a[0] == "raccourci"]
        self.assertEqual([(a["action"], a["touches"]) for a in actions], [("ajouter", "Super+Q")])

    def test_capture_hors_ecran(self):
        """Une image de la fiche (verre à 58 %, voiles des colonnes) ; CAPTURE_FICHE=chemin.png pour la garder."""
        garder = os.environ.get("CAPTURE_FICHE")
        with tempfile.TemporaryDirectory(prefix="nc-fiche-image-") as d:
            chemin = Path(garder or Path(d) / "fiche.png")
            r, _ = self.executer('''
  if (etape < 3) { etape++; return }
  if (etape === 3) { etape++; racine.capturer(IMAGE) }'''.replace("IMAGE", json.dumps(str(chemin))))
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertGreater(chemin.stat().st_size, 10000)


# Faux nc-ia : « actif » répond 0 (IA permise) ; « raccourci » note la demande et répond CORPS (q : la description)
FAUX_IA = r'''#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
H = Path(os.environ["HOME"])
if sys.argv[1] == "actif": sys.exit(0)
with (H / "appels").open("a") as f: f.write(json.dumps(["ia-" + sys.argv[1]] + sys.argv[2:], ensure_ascii=False) + "\n")
q = sys.argv[-1]
CORPS
'''
PROPOSITION = ('print(json.dumps({"ok": True, "touches": "Super+Q" if "Q" in q else "Super+G", "cible": "firefox", "genre": "appli", '
               '"nom": "Firefox", "detail": "firefox (appli)"}))')
PROPOSITION_OU_INVALIDE = 'if "importe" in q: print("pas du JSON")\nelse: ' + PROPOSITION


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
    """Le texte de la fiche reste lisible sur le verre : 4,5:1 au moins (le texte secondaire : 3:1 sur le verre flouté,
    4,5:1 sans flou), compté sur la carte seule (titre) et sur le voile de ses colonnes.
    - Avec flou (carte à 58 %) : le fond d'écran derrière est flouté. Ni nc-theme-sync ni nc-wallpaper-colors ne
      gardent sa couleur moyenne ; on prend donc un pire cas flouté raisonnable : le flou mélange les pixels voisins,
      un blanc ou un noir pur n'y survivent pas sur toute une colonne (il faudrait un fond d'écran uni). Gris clair
      moyen (#c8c8c8) derrière une palette sombre, gris foncé (#383838) derrière une claire.
    - Sans flou (Économie, flou coupé ; carte à 92 %) : le pire fond reste possible, blanc pur ou noir pur."""
    # fond, texte, texte secondaire, carte (palier(0.035) de nc-theme-sync ; celle d'Apple pour le noir)
    PALETTES = {"noir (Apple)": ("#000000", "#ffffff", "#98989d", "#1c1c1e"),
                "terminal sombre": ("#1c1d21", "#e6e6e6", "#9a9aa3", "#24252c"),
                "terminal clair": ("#f4f1ef", "#222222", "#5c5c66", "#ede4df")}
    FLOU, SANS_FLOU, VOILE, PISTE, SECONDAIRE = 0.58, 0.92, 0.25, 0.7, 0.35

    @classmethod
    def contrastes(cls):
        """{(palette, flou): {mesure: contraste}} : ce que vérifie le test."""
        res = {}
        for nom, (fond, texte, sec, carte) in cls.PALETTES.items():
            sombre = luminance(fond) < 0.5
            secondaire = melange(texte, sec, cls.SECONDAIRE)          # Qt.tint(texteSec, Qt.alpha(texte, 0.35))
            for flou in (True, False):
                derriere = ("#c8c8c8" if sombre else "#383838") if flou else ("#ffffff" if sombre else "#000000")
                sur_carte = melange(fond, derriere, cls.FLOU if flou else cls.SANS_FLOU)
                sur_voile = melange(fond, sur_carte, cls.VOILE)
                verre = melange(carte, sur_voile, 0.55)                # le − et la piste de l'interrupteur
                res[(nom, flou)] = {
                    "texte / carte": contraste(texte, sur_carte), "texte / voile": contraste(texte, sur_voile),
                    "secondaire / voile": contraste(secondaire, sur_voile), "ancien secondaire / voile": contraste(sec, sur_voile),
                    "glyphe −": contraste(texte, verre), "interrupteur éteint": contraste(melange(texte, verre, cls.PISTE), sur_voile)}
        return res

    def test_contrastes(self):
        source = (QML / "Fiche.qml").read_text()
        self.assertIn("readonly property real opaciteFond: verre ? 0.58 : 0.92", source)
        self.assertIn("readonly property real voileColonne: 0.25", source)
        self.assertIn("color: Qt.alpha(Couleurs.fond, fiche.voileColonne)", source)
        self.assertIn("readonly property color texteSecondaire: Qt.tint(Couleurs.texteSec, Qt.alpha(Couleurs.texte, 0.35))", source)
        self.assertIn("text: ligne.r.nom; color: fiche.texteSecondaire", source)
        self.assertNotIn("secondaire: true", source, "tout le texte secondaire de la fiche est le plus clair")
        # Le message du bas : texte principal (ou rouge), sur son propre voile
        self.assertIn("color: Raccourcis.erreur ? Couleurs.rouge : Couleurs.texte", source)
        # Le verre du − et de l'interrupteur : la carte à 55 % ; l'interrupteur éteint, voilé du texte
        self.assertIn("color: zMoins.containsMouse ? Qt.alpha(Couleurs.carteSurvol, 0.75) : Qt.alpha(Couleurs.carte, 0.55)", source)
        self.assertIn("color: zMoins.containsMouse ? Couleurs.rouge : Couleurs.texte", source)
        self.assertIn("readonly property real voilePiste: 0.7", source)
        self.assertIn("color: interrupteur.allume ? Couleurs.accent : Qt.alpha(Couleurs.texte, fiche.voilePiste)", source)
        for (nom, flou), m in self.contrastes().items():
            ou = f"{nom}, {'avec' if flou else 'sans'} flou"
            for cle, mini in (("texte / carte", 4.5), ("texte / voile", 4.5), ("secondaire / voile", 3.0 if flou else 4.5),
                              ("glyphe −", 4.5), ("interrupteur éteint", 3.0)):
                self.assertGreaterEqual(m[cle], mini, f"{ou} : {cle} {m[cle]:.2f}")


if __name__ == "__main__":
    unittest.main()

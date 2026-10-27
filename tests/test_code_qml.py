"""Espace de code de l'île (Code.qml, Super + X) hors écran, avec un faux nc-code qui répond en JSON : la liste des
projets lue à l'ouverture, la recherche floue au clavier, les flèches, Entrée (nc-code DOSSIER), Alt + Entrée (--nvim),
Tab puis un agent (--agent PROG, --sans-agent), Échap ; l'aperçu du projet choisi (branche, état, commits, README) ;
les actions rapides (xdg-open, wl-copy, GitHub en https seulement : une autre origine n'ouvre rien)."""
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

FAUX_NC_CODE = r'''#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
H = Path(os.environ["HOME"])
with (H / "appels").open("a") as f: f.write(json.dumps(sys.argv[1:], ensure_ascii=False) + "\n")
a = sys.argv[1:]
if a[:1] == ["--liste-json"]: print((H / "projets.json").read_text())
elif a[:1] == ["--agents-json"]: print((H / "agents.json").read_text())
elif a[:1] == ["--apercu-json"]:
    p = json.loads((H / "apercus.json").read_text()).get(a[1])
    print(json.dumps(p) if p else "{}")
'''


def projets(home):
    d = str(home / "dev")
    return [dict(nom="alpha", chemin=d + "/alpha", court="~/dev/alpha", branche="main", quand=1700000300, date="hier", message="Dernier",
                 langage="Rust", couleur="orange", github="https://github.com/moi/alpha"),
            dict(nom="neovim-conf", chemin=d + "/neovim-conf", court="~/dev/neovim-conf", branche="essai", quand=1700000200, date="il y a 2 j",
                 message="", langage="Lua", couleur="bleu", github=""),
            dict(nom="site", chemin=d + "/site", court="~/dev/site", branche="", quand=0, date="", message="", langage="", couleur="gris4",
                 github="http://github.com/moi/site")]      # jamais une origine qui n'est pas déjà https (vérifié deux fois)


@unittest.skipUnless(shutil.which("qs"), "Quickshell requis")
class EspaceDeCode(unittest.TestCase):
    def executer(self, scenario, agents=None, attendus=None):
        with tempfile.TemporaryDirectory(prefix="nc-code-qml-") as d:
            root = Path(d); q = root / "qml"; q.mkdir(); (root / "runtime").mkdir(mode=0o700)
            for nom in ("CodeProjet.qml", "CodeApercu.qml", "CodeAgent.qml", "CodeAction.qml", "Couleurs.qml", "Texte.qml", "Ico.qml"):
                shutil.copy2(QML / nom, q / nom)
            source = (QML / "Code.qml").read_text()
            # Hors Hyprland : une fenêtre ordinaire de 1600 x 1000 à la place du calque Wayland
            source = source.replace("import Quickshell.Wayland\n", "import QtQuick.Window\n").replace("PanelWindow {", "Window {")
            for l in ("import Quickshell.Hyprland\n", "    anchors { top: true; bottom: true; left: true; right: true }\n", "    exclusionMode: ExclusionMode.Ignore\n",
                      "    WlrLayershell.layer: Hyprland.activeToplevel && Hyprland.activeToplevel.lastIpcObject\n"
                      "                         && (Hyprland.activeToplevel.lastIpcObject.fullscreen || 0) > 0 ? WlrLayer.Overlay : WlrLayer.Top\n",
                      '    WlrLayershell.namespace: "nc-code"\n',
                      "    WlrLayershell.keyboardFocus: WlrKeyboardFocus.Exclusive\n"):
                self.assertIn(l, source); source = source.replace(l, "")
            source = source.replace("code.screen ? code.screen.width : 1600", "1600").replace("code.screen ? code.screen.height : 1000", "1000")
            (q / "Code.qml").write_text(source.replace('    color: "transparent"\n', '    color: "transparent"; width: 1600; height: 1000; visible: true\n'))
            (q / "Reglages.qml").write_text('pragma Singleton\nimport QtQuick\nQtObject {property bool en: false; property bool sobre: true;'
                                            ' property bool iaCoupee: false; function t(fr,en){return fr} function val(k,d){return d}}')
            (q / "qmldir").write_text("\n".join(("singleton " if n in ("Reglages", "Couleurs") else "") + n + " 1.0 " + n + ".qml"
                                                for n in ("Reglages", "Couleurs", "Code", "CodeProjet", "CodeApercu", "CodeAgent", "CodeAction", "Texte", "Ico")))
            b = root / ".local/bin"; b.mkdir(parents=True)
            (b / "nc-code").write_text(FAUX_NC_CODE); (b / "nc-code").chmod(0o755)
            ps = projets(root)
            (root / "projets.json").write_text(json.dumps(ps))
            (root / "agents.json").write_text(json.dumps(agents if agents is not None else
                                                         dict(coupee=False, defaut="claude", agents=[dict(prog="claude", nom="Claude Code"), dict(prog="codex", nom="Codex")])))
            (root / "apercus.json").write_text(json.dumps({
                ps[0]["chemin"]: dict(chemin=ps[0]["chemin"], nom="alpha", branche="main", etat="propre", readme="Alpha\nUn outil.", github=ps[0]["github"],
                                      commits=[dict(message="Dernier <b>brut</b>", quand=1700000300, date="hier"), dict(message="Premier", quand=1700000100, date="il y a 3 j")]),
                ps[1]["chemin"]: dict(chemin=ps[1]["chemin"], nom="neovim-conf", branche="essai", etat="modifie", readme="", github="", commits=[])}))
            (q / "shell.qml").write_text('''import QtQuick
import QtTest
import Quickshell
ShellRoot {
 id: racine
 property var fen: null
 property int etape: 0
 property bool fermee: false
 function verifier(ok, m) { if (!ok) { console.error("ECHEC " + m); Qt.exit(2) } }
 function trouver(item, nom) { if (item.objectName === nom) return item; var e = item.children || []
   for (var i = 0; i < e.length; i++) { var r = trouver(e[i], nom); if (r) return r } return null }
 function champ() { return trouver(fen.contentItem, "nc-code-champ") }
 function taper(t) { champ().forceActiveFocus(); for (var i = 0; i < t.length; i++) clavier.keyClick(t[i]) }
 function touche(k, m) { champ().forceActiveFocus(); clavier.keyClick(k, m || 0) }
 TestCase { id: clavier; name: "EspaceDeCode"; when: false }
 Timer { interval: 100; running: true; repeat: true; onTriggered: {
  if (etape === 0) { var c = Qt.createComponent("Code.qml"); verifier(c.status === Component.Ready, c.errorString())
                     fen = c.createObject(racine); fen.fermer.connect(function () { racine.fermee = true }); etape++; return }
  if (!fen.lus) return
  SCENARIO
 } }
 Timer { interval: 12000; running: true; onTriggered: { console.error("ECHEC délai"); Qt.exit(3) } }
}
'''.replace("SCENARIO", scenario))
            env = dict(os.environ, HOME=d, QT_QPA_PLATFORM="offscreen", QT_QUICK_BACKEND="software", XDG_RUNTIME_DIR=str(root / "runtime"),
                       XDG_CACHE_HOME=str(root / "cache"), XDG_CONFIG_HOME=str(root / "config"), XDG_STATE_HOME=str(root / "state"),
                       XDG_DATA_HOME=str(root / "data"), TMPDIR=str(root))
            env.pop("WAYLAND_DISPLAY", None)
            r = subprocess.run(["qs", "--no-color", "-p", str(q / "shell.qml")], env=env, text=True, capture_output=True, timeout=30)
            f, avant, fin = root / "appels", None, time.monotonic() + 2
            while time.monotonic() < fin:
                maintenant = f.read_text() if f.exists() else ""
                lus = [json.loads(l) for l in maintenant.splitlines() if l.strip()]
                if maintenant == avant and (attendus is None or attendus(lus)):
                    break
                avant = maintenant; time.sleep(0.3)
            appels = [json.loads(l) for l in (avant or "").splitlines() if l.strip()]
            sortie = r.stdout + r.stderr
            if os.environ.get("NC_TEST_VERBEUX"):
                print(sortie)
            self.assertEqual(r.returncode, 0, sortie)
            for erreur in ("ReferenceError", "TypeError", "Cannot assign", "Binding loop", "is not a type", "polish() loop"):
                self.assertNotIn(erreur, sortie)
            return appels, ps

    def test_recherche_fleches_apercu_et_entree(self):
        appels, ps = self.executer('''
  if (etape === 1) { verifier(fen.projets.length === 3 && fen.visibles.length === 3 && fen.sel === 0, "liste lue : " + fen.visibles.length)
                     verifier(trouver(fen.contentItem, "nc-code-liste").count === 3, "trois lignes")
                     verifier(trouver(fen.contentItem, "nc-code-github").visible, "GitHub proposé pour une origine https github.com")
                     taper("nvc"); etape++; return }                                    // lettres dans l'ordre : neovim-conf
  if (etape === 2) { verifier(fen.filtre === "nvc" && fen.visibles.length === 1 && fen.visibles[0].nom === "neovim-conf", "recherche floue : " + fen.visibles.map(p => p.nom))
                     verifier(!trouver(fen.contentItem, "nc-code-github").visible, "pas de GitHub sans origine")
                     if (!fen.apercuChoisi) return                                         // nc-code --apercu-json répond
                     verifier(fen.apercuChoisi.branche === "essai", "aperçu du projet choisi")
                     verifier(trouver(fen.contentItem, "nc-code-etat").visible, "état modifié affiché")
                     champ().text = ""; etape++; return }
  if (etape === 3) { verifier(fen.visibles.length === 3 && fen.sel === 0, "recherche vidée")
                     touche(Qt.Key_Down); touche(Qt.Key_Down); touche(Qt.Key_Up)
                     verifier(fen.sel === 1, "flèches : " + fen.sel)
                     touche(Qt.Key_Up); touche(Qt.Key_Up); verifier(fen.sel === 0, "pas sous zéro")
                     etape++; return }
  if (etape === 4) { if (!fen.apercuChoisi || fen.apercuChoisi.nom !== "alpha") return
                     var a = trouver(fen.contentItem, "nc-code-apercu")
                     var commits = []; (function tout(e) { if (e.objectName === "nc-code-commit") commits.push(e); (e.children || []).forEach(tout) })(a)
                     verifier(commits.length === 2, "deux commits : " + commits.length)
                     verifier(trouver(a, "nc-code-readme").visible, "README affiché")
                     verifier(trouver(fen.contentItem, "nc-code-etat").visible, "état propre affiché")
                     touche(Qt.Key_Return); verifier(racine.fermee, "Entrée ferme"); Qt.quit() }''',
                                   attendus=lambda a: any(x and x[0].endswith("/alpha") for x in a))
        self.assertIn([ps[0]["chemin"]], appels, "Entrée : nc-code DOSSIER")
        self.assertIn(["--liste-json"], appels)
        self.assertIn(["--apercu-json", ps[1]["chemin"]], appels, "aperçu lu à la sélection")
        self.assertFalse([a for a in appels if a[:1] == ["--apercu-json"] and a[1] == ps[2]["chemin"]], "aucun aperçu lu pour un projet survolé un instant")

    def test_alt_entree_neovim_seul(self):
        appels, ps = self.executer('''
  if (etape === 1) { touche(Qt.Key_Down); touche(Qt.Key_Return, Qt.AltModifier); verifier(racine.fermee, "fermée"); Qt.quit() }''',
                                   attendus=lambda a: ["--nvim", ps_chemin(a)] in a if a else False)
        self.assertIn(["--nvim", ps[1]["chemin"]], appels)

    def test_tab_choisit_l_agent(self):
        appels, ps = self.executer('''
  if (etape === 1) { if (fen.agents.length < 2) return
                     verifier(!fen.choixAgent && !trouver(fen.contentItem, "nc-code-agents").visible, "agents cachés au départ")
                     touche(Qt.Key_Tab); verifier(fen.choixAgent && trouver(fen.contentItem, "nc-code-agents").visible, "Tab : les agents")
                     verifier(fen.choixAgents.length === 3 && fen.choixAgents[2].prog === "", "deux agents, puis sans agent")
                     touche(Qt.Key_Escape); verifier(!fen.choixAgent && !racine.fermee, "Échap revient aux projets sans fermer")
                     touche(Qt.Key_Tab); touche(Qt.Key_Down); verifier(fen.selAgent === 1, "flèches dans les agents")
                     touche(Qt.Key_Return); verifier(racine.fermee, "fermée"); Qt.quit() }''',
                                   attendus=lambda a: any(x[:1] == ["--agent"] for x in a))
        self.assertIn(["--agent", "codex", ps[0]["chemin"]], appels)

    def test_sans_agent_et_ia_coupee(self):
        appels, ps = self.executer('''
  if (etape === 1) { touche(Qt.Key_Tab); verifier(fen.choixAgents.length === 1, "IA coupée : seulement le terminal")
                     touche(Qt.Key_Return); verifier(racine.fermee, "fermée"); Qt.quit() }''',
                                   agents=dict(coupee=True, defaut="", agents=[]), attendus=lambda a: any(x[:1] == ["--sans-agent"] for x in a))
        self.assertIn(["--sans-agent", ps[0]["chemin"]], appels)

    def test_echap_ferme_sans_rien_ouvrir_et_actions(self):
        appels, ps = self.executer('''
  if (etape === 1) { verifier(fen.urlGitHub("https://github.com/moi/alpha") === "https://github.com/moi/alpha", "https github.com accepté")
                     for (const u of ["http://github.com/moi/alpha", "https://github.com.evil.io/moi/alpha", "https://gitlab.com/moi/alpha",
                                      "https://github.com/moi/alpha/../../x", "https://github.com/moi", "https://github.com/moi/alpha?x=1", "javascript:alert(1)", ""])
                       verifier(fen.urlGitHub(u) === "", "refusé : " + u)
                     touche(Qt.Key_Down); touche(Qt.Key_Down)                                 // « site » : origine http, pas https
                     verifier(fen.github === "" && !trouver(fen.contentItem, "nc-code-github").visible, "origine non https : rien à ouvrir")
                     verifier(fen.ouvrirGitHub() === false && !racine.fermee, "ouvrirGitHub ne fait rien sans URL sûre")
                     touche(Qt.Key_Up); touche(Qt.Key_Up)
                     verifier(fen.github === "https://github.com/moi/alpha", "alpha : URL GitHub")
                     touche(Qt.Key_Escape); verifier(racine.fermee, "Échap ferme"); Qt.quit() }''')
        self.assertFalse([a for a in appels if a and not a[0].startswith("--")], "Échap n'ouvre rien")

    def test_fichiers_libelles_et_chargeur(self):
        shell = (QML / "shell.qml").read_text()
        self.assertIn("function code(): void", shell, "qs -c nc-ile ipc call ile code")
        self.assertRegex(shell, r"LazyLoader \{\s*id: chargeurCode\s*active: racine\.codeOuvert", "le panneau n'existe que lorsqu'il est ouvert")
        for nom in ("Code", "CodeProjet", "CodeApercu", "CodeAgent", "CodeAction"):
            src = (QML / (nom + ".qml")).read_text()
            self.assertNotRegex(src, r"(?m)^\s*component ", nom + " : jamais de component inline")
        code = (QML / "Code.qml").read_text()
        self.assertNotIn("Qt.openUrlExternally", code, "GitHub : xdg-open en argv, après validation")
        self.assertIn('Quickshell.execDetached(["xdg-open", github])', code)
        self.assertNotIn('"sh"', code, "aucune ligne de shell construite avec un chemin")
        self.assertIn('namespace = "^nc-code$"', (REPO / "home/.config/hypr/nc/regles.lua").read_text(), "flou derrière la carte")


def ps_chemin(appels):
    for a in appels:
        if a[:1] == ["--nvim"] and len(a) > 1:
            return a[1]
    return ""


if __name__ == "__main__":
    unittest.main()

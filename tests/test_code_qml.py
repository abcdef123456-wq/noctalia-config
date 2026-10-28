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


FAUX_NC_CLAUDE = r'''#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
with (Path(os.environ["HOME"]) / "appels").open("a") as f: f.write(json.dumps(["nc-claude"] + sys.argv[1:], ensure_ascii=False) + "\n")
'''

# Agents.qml et Etat.qml réduits à ce que Code.qml lit (les vrais lisent l'état de nc-claude et l'horloge de l'île)
FAUX_AGENTS = '''pragma Singleton
import QtQuick
import Quickshell
QtObject {
    property var sessions: []
    function sessionActive(s) { return s.etat === "travail" || s.etat === "demande" || s.etat === "terminal" }
    function nom(s) { return s.agent === "codex" ? "Codex" : "Claude" }
    function couleurDe(s) { return "#d97757" }
    function allerTerminal(pid, shell) {
        if (pid > 0) Quickshell.execDetached([Quickshell.env("HOME") + "/.local/bin/nc-claude", "aller", String(pid), String(shell || 0)])
    }
}
'''
FAUX_ETAT = ("pragma Singleton\nimport QtQuick\nQtObject { property date maintenant: new Date(); property var pilules: ({}); property string lanceurFondu: \"\"\n"
             "  property var lanceurProprio: null }\n")
FAUX_PARTAGE = "pragma Singleton\nimport QtQuick\nQtObject { property bool silence: false; property bool indicateur: false; property int sessions: 0 }\n"


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
    def executer(self, scenario, agents=None, attendus=None, fondu=False, carte=None, projets_plus=None, readme=None):
        with tempfile.TemporaryDirectory(prefix="nc-code-qml-") as d:
            root = Path(d); q = root / "qml"; q.mkdir(); (root / "runtime").mkdir(mode=0o700)
            for nom in ("CodeProjet.qml", "CodeApercu.qml", "CodeAgent.qml", "CodeAction.qml", "CodeAide.qml", "CodeChoixNouveau.qml", "Couleurs.qml", "Texte.qml", "Ico.qml", "LanceurFondu.qml"):
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
            source = source.replace('code.screen ? code.screen.name : ""', '"DP-1"')   # hors écran, la fenêtre n'a pas de nom d'écran
            source = source.replace("code.screen ? code.screen.width : 1600", "1600").replace("code.screen ? code.screen.height : 1000", "1000")
            if carte:
                self.assertIn("Math.min(980, Math.round(largeurEcran * 0.64))", source)
                source = source.replace("Math.min(980, Math.round(largeurEcran * 0.64))", str(carte))
            (q / "Code.qml").write_text(source.replace('    color: "transparent"\n', '    color: "transparent"; width: 1600; height: 1000; visible: true\n'))
            (q / "Reglages.qml").write_text('pragma Singleton\nimport QtQuick\nQtObject {property bool en: false; property bool sobre: %s;'
                                            ' property bool iaCoupee: false; function t(fr,en){return fr} function val(k,d){return %s}}'
                                            % (("false", 'k === "ILE_LANCEUR_FONDU" ? "oui" : d') if fondu else ("true", "d")))
            (q / "Agents.qml").write_text(FAUX_AGENTS); (q / "Etat.qml").write_text(FAUX_ETAT); (q / "Partage.qml").write_text(FAUX_PARTAGE)
            (q / "qmldir").write_text("\n".join(("singleton " if n in ("Reglages", "Couleurs", "Agents", "Etat", "Partage") else "") + n + " 1.0 " + n + ".qml"
                                                for n in ("Reglages", "Couleurs", "Agents", "Etat", "Partage", "LanceurFondu", "Code", "CodeProjet", "CodeApercu", "CodeAgent", "CodeAction", "CodeAide", "CodeChoixNouveau", "Texte", "Ico")))
            b = root / ".local/bin"; b.mkdir(parents=True)
            (b / "nc-code").write_text(FAUX_NC_CODE); (b / "nc-code").chmod(0o755)
            (b / "nc-claude").write_text(FAUX_NC_CLAUDE); (b / "nc-claude").chmod(0o755)
            ps = projets(root)
            if projets_plus:
                ps = ps + projets_plus(root)
            (root / "projets.json").write_text(json.dumps(ps))
            (root / "agents.json").write_text(json.dumps(agents if agents is not None else
                                                         dict(coupee=False, defaut="claude", agents=[dict(prog="claude", nom="Claude Code"), dict(prog="codex", nom="Codex")])))
            (root / "apercus.json").write_text(json.dumps({
                ps[0]["chemin"]: dict(chemin=ps[0]["chemin"], nom="alpha", branche="main", etat="propre", readme=readme or "Alpha\nUn outil.", github=ps[0]["github"],
                                      commits=[dict(message="Dernier <b>brut</b>", quand=1700000300, date="hier"), dict(message="Premier", quand=1700000100, date="il y a 3 j")]),
                ps[1]["chemin"]: dict(chemin=ps[1]["chemin"], nom="neovim-conf", branche="essai", etat="modifie", readme="", github="", commits=[])}))
            (q / "shell.qml").write_text('''import QtQuick
import QtTest
import Quickshell
ShellRoot {
 id: racine
 property var fen: null
 QtObject { id: pilule; property real width: 220; property real height: 30; property real radius: 15; property real y: 9
            property color color: "#101820"; property bool auRepos: true }
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
  if (etape === 0) { if (FONDU) Etat.pilules["DP-1"] = pilule
                     var c = Qt.createComponent("Code.qml"); verifier(c.status === Component.Ready, c.errorString())
                     fen = c.createObject(racine); fen.fermer.connect(function () { racine.fermee = true }); etape++; return }
  if (!fen.lus) return
  SCENARIO
 } }
 Timer { interval: 12000; running: true; onTriggered: { console.error("ECHEC délai"); Qt.exit(3) } }
}
'''.replace("SCENARIO", scenario.replace("@HOME@", d)).replace("FONDU", "true" if fondu else "false"))
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
                     verifier(trouver(fen.contentItem, "nc-code-etat") === null, "plus de pastille d'état (elle demanderait git)")
                     champ().text = ""; etape++; return }
  if (etape === 3) { verifier(fen.visibles.length === 3 && fen.sel === 0, "recherche vidée")
                     touche(Qt.Key_Down); touche(Qt.Key_Down); touche(Qt.Key_Up)
                     verifier(fen.sel === 1, "flèches : " + fen.sel)
                     touche(Qt.Key_Up); touche(Qt.Key_Up); verifier(fen.sel === -1, "Haut depuis le premier projet : la ligne Nouveau")
                     touche(Qt.Key_Up); verifier(fen.sel === -1, "pas au-dessus de Nouveau")
                     touche(Qt.Key_Down); verifier(fen.sel === 0, "Bas revient au premier projet")
                     etape++; return }
  if (etape === 4) { if (!fen.apercuChoisi || fen.apercuChoisi.nom !== "alpha") return
                     var a = trouver(fen.contentItem, "nc-code-apercu")
                     var commits = []; (function tout(e) { if (e.objectName === "nc-code-commit") commits.push(e); (e.children || []).forEach(tout) })(a)
                     verifier(commits.length === 2, "deux commits : " + commits.length)
                     verifier(trouver(a, "nc-code-readme").visible, "README affiché")
                     touche(Qt.Key_Return); verifier(racine.fermee, "Entrée ferme"); Qt.quit() }''',
                                   attendus=lambda a: any(x and x[0].endswith("/alpha") for x in a))
        self.assertIn([ps[0]["chemin"]], appels, "Entrée : nc-code DOSSIER")
        self.assertIn(["--liste-json"], appels)
        self.assertIn(["--apercu-json", ps[1]["chemin"]], appels, "aperçu lu à la sélection")
        self.assertFalse([a for a in appels if a[:1] == ["--apercu-json"] and a[1] == ps[2]["chemin"]], "aucun aperçu lu pour un projet survolé un instant")

    def test_lanceur_sort_de_la_pilule_clavier_des_la_premiere_image_et_echap(self):
        """ILE_LANCEUR_FONDU=oui : le vrai Code.qml part de la pilule ; la pilule est cachée, la frappe marche pendant l'animation,
        Échap pendant ou après l'animation ferme proprement et la pilule revient."""
        self.executer('''
  if (etape === 1) { taper("nvc"); verifier(fen.filtre === "nvc", "frappe pendant l'animation : " + fen.filtre); etape++; return }
  if (etape === 2) { if (Etat.lanceurFondu === "") return
                     verifier(Etat.lanceurProprio !== null, "pilule cachée par le lanceur")
                     touche(Qt.Key_Escape); etape++; return }
  if (etape === 3) { if (!racine.fermee) return
                     verifier(Etat.lanceurFondu === "" && Etat.lanceurProprio === null, "pilule rendue : " + Etat.lanceurFondu)
                     Qt.quit() }''', fondu=True)

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

    def test_nouveau_projet_ctrl_n(self):
        appels, ps = self.executer('''
  if (etape === 1) { verifier(trouver(fen.contentItem, "nc-code-nouveau") !== null, "première ligne : nouveau projet")
                     touche(Qt.Key_N, Qt.ControlModifier); verifier(fen.mode === "choix" && trouver(fen.contentItem, "nc-code-choix").visible, "Ctrl N : le petit choix")
                     touche(Qt.Key_Return); verifier(fen.mode === "nouveau" && trouver(fen.contentItem, "nc-code-saisie").visible, "« Projet vide » : mode nouveau")
                     taper("-piege"); touche(Qt.Key_Return); verifier(!racine.fermee, "un nom qui commence par - est refusé ici")
                     touche(Qt.Key_Escape); verifier(fen.mode === "" && !racine.fermee, "Échap revient")
                     touche(Qt.Key_N, Qt.ControlModifier); touche(Qt.Key_Return); touche(Qt.Key_Return); verifier(!racine.fermee, "nom vide : rien")
                     taper("essai"); touche(Qt.Key_Return); verifier(racine.fermee, "fermée"); Qt.quit() }''',
                                   attendus=lambda a: ["--nouveau", "essai"] in a)
        self.assertIn(["--nouveau", "essai"], appels)
        self.assertNotIn(["--nouveau", "-piege"], appels)

    def test_ligne_nouveau_au_clavier_haut_entree_choix_a_deux_lignes(self):
        appels, ps = self.executer('''
  if (etape === 1) { verifier(fen.sel === 0, "départ : le premier projet")
                     var ligne = trouver(fen.contentItem, "nc-code-nouveau")
                     verifier(!ligne.choisie, "Nouveau n'est pas choisie au départ")
                     touche(Qt.Key_Up); verifier(fen.sel === -1 && fen.projet === null, "Haut : la ligne Nouveau")
                     verifier(ligne.choisie, "mise en évidence comme une ligne choisie")
                     verifier(!trouver(fen.contentItem, "nc-code-apercu").visible && trouver(fen.contentItem, "nc-code-nouveau-aide").visible, "à droite : ce qu'Entrée va faire")
                     touche(Qt.Key_PageUp); verifier(fen.sel === -1, "page haut ne bouge pas")
                     touche(Qt.Key_Down); verifier(fen.sel === 0, "Bas revient au premier projet")
                     touche(Qt.Key_Up); touche(Qt.Key_Return)
                     verifier(!racine.fermee && fen.mode === "choix", "Entrée sur Nouveau : le choix à deux lignes")
                     var vide = trouver(fen.contentItem, "nc-code-choix-vide"), gh = trouver(fen.contentItem, "nc-code-choix-github")
                     verifier(vide.visible && gh.visible && fen.selChoix === 0 && vide.actif && !gh.actif, "« Projet vide » d'abord")
                     touche(Qt.Key_Down); verifier(fen.selChoix === 1 && gh.actif, "Bas : Depuis GitHub")
                     touche(Qt.Key_Down); verifier(fen.selChoix === 1, "pas plus bas")
                     touche(Qt.Key_Up); touche(Qt.Key_Escape); verifier(fen.mode === "" && fen.sel === -1 && !racine.fermee, "Échap ferme le choix, pas le panneau")
                     touche(Qt.Key_Return); touche(Qt.Key_Down); touche(Qt.Key_Return); verifier(fen.mode === "cloner", "Depuis GitHub")
                     touche(Qt.Key_Escape); touche(Qt.Key_Return); touche(Qt.Key_Return); taper("demo"); touche(Qt.Key_Return)
                     verifier(racine.fermee, "fermée"); Qt.quit() }''', attendus=lambda a: ["--nouveau", "demo"] in a)
        self.assertIn(["--nouveau", "demo"], appels)
        self.assertFalse([a for a in appels if a and a[0] == ps[0]["chemin"]], "Entrée sur Nouveau n'ouvre aucun projet")

    def test_clic_sur_nouveau_et_sur_les_lignes_du_choix(self):
        appels, ps = self.executer('''
  function cliquer(item) { clavier.mouseClick(item, item.width / 2, item.height / 2) }
  if (etape === 1) { var zone = trouver(fen.contentItem, "nc-code-nouveau-zone")
                     verifier(zone !== null && zone.visible, "zone de clic de la ligne Nouveau")
                     // la zone est bien celle qui reçoit un clic en son centre (ni la liste, ni le surligneur, ni le champ devant elle)
                     var p = zone.mapToItem(fen.contentItem, zone.width / 2, zone.height / 2)
                     var devant = fen.contentItem.childAt(p.x, p.y)
                     verifier(devant !== null, "un élément à cet endroit")
                     cliquer(zone); verifier(fen.mode === "choix", "clic : le choix à deux lignes (mode " + fen.mode + ")")
                     verifier(!racine.fermee, "un clic sur Nouveau ne ferme pas")
                     cliquer(trouver(fen.contentItem, "nc-code-choix-github")); verifier(fen.mode === "cloner", "clic sur Depuis GitHub")
                     touche(Qt.Key_Escape); fen.sel = 2
                     cliquer(zone); verifier(fen.mode === "choix", "clic aussi quand un autre projet était choisi")
                     cliquer(trouver(fen.contentItem, "nc-code-choix-vide")); verifier(fen.mode === "nouveau", "clic sur Projet vide")
                     touche(Qt.Key_Escape); etape++; return }
  if (etape === 2) { // un clic sur un projet de la liste l'ouvre toujours
                     var l = trouver(fen.contentItem, "nc-code-liste")
                     var it = l.itemAtIndex(1); verifier(it !== null, "deuxième ligne")
                     clavier.mouseClick(it, it.width / 2, it.height / 2)
                     verifier(racine.fermee, "clic sur un projet : ouvert"); Qt.quit() }''', attendus=lambda a: any(x and x[0].endswith("/neovim-conf") for x in a))
        self.assertIn([ps[1]["chemin"]], appels, "le clic sur la deuxième ligne ouvre ce projet")

    def test_cloner_ctrl_l(self):
        appels, ps = self.executer('''
  if (etape === 1) { touche(Qt.Key_L, Qt.ControlModifier); verifier(fen.mode === "cloner", "mode cloner")
                     taper("moi/depot"); touche(Qt.Key_Return); verifier(racine.fermee, "fermée"); Qt.quit() }''',
                                   attendus=lambda a: ["--cloner", "moi/depot"] in a)
        self.assertIn(["--cloner", "moi/depot"], appels)

    def test_fichiers_libelles_et_chargeur(self):
        shell = (QML / "shell.qml").read_text()
        self.assertIn("function code(): void", shell, "qs -c nc-ile ipc call ile code")
        self.assertRegex(shell, r"LazyLoader \{\s*id: chargeurCode\s*active: racine\.codeOuvert", "le panneau n'existe que lorsqu'il est ouvert")
        for nom in ("Code", "CodeProjet", "CodeApercu", "CodeAgent", "CodeAction", "CodeAide", "CodeChoixNouveau"):
            src = (QML / (nom + ".qml")).read_text()
            self.assertNotRegex(src, r"(?m)^\s*component ", nom + " : jamais de component inline")
        code = (QML / "Code.qml").read_text()
        self.assertNotIn("Qt.openUrlExternally", code, "GitHub : xdg-open en argv, après validation")
        self.assertIn('Quickshell.execDetached(["xdg-open", github])', code)
        self.assertNotIn('"sh"', code, "aucune ligne de shell construite avec un chemin")
        self.assertIn('namespace = "^nc-code$"', (REPO / "home/.config/hypr/nc/regles.lua").read_text(), "flou derrière la carte")

    def test_badge_et_entree_ramene_au_terminal_de_l_agent(self):
        appels, ps = self.executer('''
  if (etape === 1) { Agents.sessions = [
        { id: "a", agent: "claude", etat: "travail", cwd_reel: "@HOME@/dev/alpha", cwd: "~/dev/alpha", terminal: 4242, shell: 4243, maj: 1 },
        { id: "b", agent: "codex", etat: "demande", cwd: "~/dev/neovim-conf", terminal: 0, maj: 1 },
        { id: "c", agent: "claude", etat: "fini", cwd_reel: "@HOME@/dev/site", terminal: 7, maj: 1 }]
      etape++; return }
  if (etape === 2) { var l = []; (function tout(e) { if (e.objectName === "nc-code-badge" && e.visible) l.push(e); (e.children || []).forEach(tout) })(fen.contentItem)
                     verifier(l.length === 2, "deux badges (alpha, neovim-conf), pas pour un agent fini : " + l.length)
                     verifier(fen.badgeDe(fen.projets[0]) === "Claude travaille", "badge : " + fen.badgeDe(fen.projets[0]))
                     verifier(fen.badgeDe(fen.projets[1]) === "Codex t'attend", "badge : " + fen.badgeDe(fen.projets[1]))
                     verifier(fen.badgeDe(fen.projets[2]) === "", "aucun badge sans agent au travail")
                     touche(Qt.Key_Return); verifier(racine.fermee, "fermée"); Qt.quit() }''',
                                   attendus=lambda a: any(x[:1] == ["nc-claude"] for x in a))
        self.assertIn(["nc-claude", "aller", "4242", "4243"], appels, "Entrée : le terminal de l'agent")
        self.assertFalse([a for a in appels if a and a[0] == ps[0]["chemin"]], "pas de second espace ouvert")

    def test_ctrl_entree_ouvre_quand_meme_et_sans_terminal_connu(self):
        appels, ps = self.executer('''
  if (etape === 1) { Agents.sessions = [
        { id: "a", agent: "claude", etat: "travail", cwd_reel: "@HOME@/dev/alpha", terminal: 4242, shell: 1, maj: 1 },
        { id: "b", agent: "claude", etat: "travail", cwd: "~/dev/neovim-conf", terminal: 0, maj: 1 }]
      etape++; return }
  if (etape === 2) { touche(Qt.Key_Return, Qt.ControlModifier); verifier(racine.fermee, "fermée"); Qt.quit() }''',
                                   attendus=lambda a: any(x and x[0].endswith("/alpha") for x in a))
        self.assertIn([ps[0]["chemin"]], appels, "Ctrl + Entrée ouvre quand même")
        self.assertFalse([a for a in appels if a[:1] == ["nc-claude"]])

    def test_entree_sans_terminal_connu_ouvre(self):
        appels, ps = self.executer('''
  if (etape === 1) { Agents.sessions = [{ id: "a", agent: "claude", etat: "travail", cwd_reel: "@HOME@/dev/alpha", terminal: 0, maj: 1 }]
      etape++; return }
  if (etape === 2) { verifier(fen.badgeDe(fen.projets[0]) !== "", "badge malgré tout"); touche(Qt.Key_Return); verifier(racine.fermee, "fermée"); Qt.quit() }''',
                                   attendus=lambda a: any(x and x[0].endswith("/alpha") for x in a))
        self.assertIn([ps[0]["chemin"]], appels, "pas de terminal connu : on ouvre")

    def test_aide_de_premiere_ouverture(self):
        self.executer('''
  if (etape === 1) { if (!fen.debutant) return                                  // agents-json peut répondre après la liste
                     var a = trouver(fen.contentItem, "nc-code-aide"); verifier(a !== null && a.visible === true, "aide visible pour un débutant")
                     taper("x"); etape++; return }
  if (etape === 2) { verifier(!trouver(fen.contentItem, "nc-code-aide").visible || fen.mode === "", "aide discrète"); Qt.quit() }''',
                      agents=dict(coupee=False, defaut="claude", debutant=True, agents=[]))
        self.executer('''
  if (etape === 1) { verifier(!trouver(fen.contentItem, "nc-code-aide").visible, "pas d'aide quand un projet a déjà été ouvert"); Qt.quit() }''')

    # ── mise en page : rien ne se chevauche, quelle que soit la largeur du panneau ──
    SCENARIO_PIED = '''
  if (etape === 1) { if (!fen.projet) return; etape++; return }                  // le temps que la sélection et GitHub se posent
  if (etape === 2) {
    var pied = trouver(fen.contentItem, "nc-code-aides"), act = trouver(fen.contentItem, "nc-code-actions")
    var px = pied.mapToItem(fen.contentItem, 0, 0).x, ax = act.mapToItem(fen.contentItem, 0, 0).x
    console.log("PIED carte=" + fen.largeurCarte + " aides=" + px + "+" + pied.width + " actions=" + ax + "+" + act.width)
    verifier(px + pied.width <= ax, "la rangée d'aides s'arrête avant les actions")
    var noms = ["ouvrir", "tab", "nvim", "force", "echap"], vus = []
    noms.forEach(n => { var a = trouver(fen.contentItem, "nc-code-aide-" + n); vus.push(a.visible)
        if (a.visible) verifier(a.x + a.width <= pied.width, "l'aide " + n + " tient entière dans sa rangée : " + (a.x + a.width) + " > " + pied.width) })
    verifier(vus[0] && vus[4], "« ouvrir » et « fermer » restent toujours")
    verifier(!vus[3] || vus[2], "« ouvrir quand même » ne reste pas seul sans « Alt ↵ »")
    verifier(!vus[2] || vus[1], "« Alt ↵ » ne reste pas sans « Tab »")
    var pieds = trouver(fen.contentItem, "nc-code-fichiers")
    var cx = (1600 - fen.largeurCarte) / 2; verifier(ax >= cx && ax + act.width <= cx + fen.largeurCarte, "les actions restent dans la carte")
    console.log("PIED visibles=" + vus + " compactes=" + pieds.compact)
    ATTENDU
    Qt.quit() }'''

    def test_pied_large_toutes_les_aides(self):
        self.executer(self.SCENARIO_PIED.replace("ATTENDU", 'verifier(vus.every(v => v), "assez large : toutes les aides"); verifier(!pieds.compact, "actions complètes")'), carte=1300)

    def test_pied_etroit_aides_masquees_dans_l_ordre_puis_actions_en_icone(self):
        self.executer(self.SCENARIO_PIED.replace("ATTENDU", 'verifier(!vus[3], "étroit : « ouvrir quand même » partie d\'abord")'), carte=900)
        self.executer(self.SCENARIO_PIED.replace("ATTENDU", 'verifier(pieds.compact, "les actions passent en icône quand les aides ne tiennent plus avec elles")'), carte=760)
        self.executer(self.SCENARIO_PIED.replace("ATTENDU", 'verifier(pieds.compact && pieds.width < 40, "très étroit : les actions passent en icône seule")'), carte=560)

    def test_noms_longs_date_reservee_aide_bornee_et_readme_clippe(self):
        long = "un-nom-de-projet-vraiment-tres-long-pour-voir-la-coupure-" * 2
        plus = lambda root: [dict(nom=long, chemin=str(root / "dev" / "long"), court="~/dev/long", branche="main", quand=1700000100,
                                  date="il y a 10 j", message="", langage="Go", couleur="cyan", github="")]
        lignes = "\n".join("Ligne %d du fichier de présentation, assez longue pour passer à la ligne dans la carte de l'aperçu" % i for i in range(60))
        self.executer('''
  if (etape === 1) { var l = trouver(fen.contentItem, "nc-code-liste"); l.positionViewAtEnd(); etape++; return }
  if (etape === 2) { var l = trouver(fen.contentItem, "nc-code-liste"); var it = null
                     for (var i = 0; i < l.contentItem.children.length; i++) { var c = l.contentItem.children[i]; if (c.projet && c.projet.nom && c.projet.nom.indexOf("un-nom-de-projet") === 0) it = c }
                     if (!it) return
                     var nom = null, date = null
                     ;(function tout(e) { var t = e.text !== undefined ? e.text : null
                       if (t && t.indexOf("un-nom-de-projet") === 0) nom = e
                       if (t === "il y a 10 j") date = e; (e.children || []).forEach(tout) })(it)
                     verifier(nom !== null && date !== null, "nom et date trouvés")
                     verifier(nom.truncated, "le long nom est coupé (elide)")
                     verifier(nom.x + nom.width + 12 <= date.x, "la date garde sa place : " + (nom.x + nom.width) + " vs " + date.x)
                     etape++; return }
  if (etape === 3) { if (!fen.debutant || !fen.apercuChoisi || fen.apercuChoisi.nom !== "alpha") return
                     var a = trouver(fen.contentItem, "nc-code-apercu"), r = trouver(a, "nc-code-readme")
                     verifier(r.visible && r.y + r.height <= a.height - 8, "le README finit avant le bas de l'aperçu avec une marge : " + (r.y + r.height) + " / " + a.height)
                     var t = r.children[0]
                     verifier(t.truncated, "texte long : fini par « … »")
                     verifier(t.y + t.contentHeight <= r.height, "aucune ligne coupée en bas : " + (t.y + t.contentHeight) + " > " + r.height)
                     var aide = trouver(fen.contentItem, "nc-code-aide"), li = trouver(fen.contentItem, "nc-code-liste")
                     verifier(aide.x + aide.width <= li.x + li.width, "l'aide « Premier projet » reste dans la colonne de gauche : " + (aide.x + aide.width) + " > " + (li.x + li.width))
                     verifier(aide.truncated, "…et elle est coupée (elide) plutôt que de déborder")
                     Qt.quit() }''', projets_plus=plus, readme=lignes, carte=700, agents=dict(coupee=False, defaut="claude", debutant=True, agents=[]))


def ps_chemin(appels):
    for a in appels:
        if a[:1] == ["--nvim"] and len(a) > 1:
            return a[1]
    return ""


if __name__ == "__main__":
    unittest.main()

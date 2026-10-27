"""Commande longue du terminal dans l'île (Terminal.qml, PageTerminal.qml, Compact.qml, ~/.config/nc/terminal.zsh,
réglage ILE_TERMINAL).

- Source : deux fichiers du dossier privé de la session surveillés (FileView), aucun minuteur répété, la commande jamais
  dans une commande (seul le pid, un entier, sert à retrouver la fenêtre), mode de la pilule, réglages, README.
- Les crochets zsh (vrai zsh, sans configuration, HOME et XDG_RUNTIME_DIR temporaires) : le fichier pendant une
  commande, « fini » seulement après 10 s, rien hors d'une session graphique ni avec ILE_TERMINAL=non, aucun
  sous-processus.
- Hors écran, avec le vrai qs : le vrai Terminal.qml et la vraie page PageTerminal.qml reçoivent les fichiers (faux Etat
  et Reglages). Cas : seuil (10 s, raccourci), fin de commande, shell disparu (fichier orphelin), « Terminée » / « Échec »
  avec le code, retour au terminal (faux hyprctl du garde-fou, pid seulement), réglage ILE_TERMINAL=non.
HOME et XDG_RUNTIME_DIR isolés, jamais les vrais ; aucun vrai hyprctl."""
import os
from pathlib import Path
import re
import runpy
import shutil
import subprocess
import tempfile
import textwrap
import time
import unittest
import warnings

REPO = Path(__file__).resolve().parents[1]
QML = REPO / "home/.config/quickshell/nc-ile"
ZSH = REPO / "home/.config/nc/terminal.zsh"


class Source(unittest.TestCase):
    def setUp(self):
        self.terminal = (QML / "Terminal.qml").read_text()
        self.code = re.sub(r"//.*", "", self.terminal)
        self.page = re.sub(r"//.*", "", (QML / "PageTerminal.qml").read_text())
        self.compact = (QML / "Compact.qml").read_text()
        self.zsh = ZSH.read_text()

    def test_fichiers_surveilles_pas_de_sondage(self):
        self.assertIn('path: Etat.dossierSession + "/nc-terminal"; watchChanges: true', self.terminal)
        self.assertIn('path: Etat.dossierSession + "/nc-terminal-fini"; watchChanges: true', self.terminal)
        self.assertNotRegex(self.code, r"repeat: true|running: true|inotifywait")
        self.assertNotRegex(self.page, r"\bProcess\b|repeat: true|execDetached")
        # Le shell disparu : vérifié sur un événement seulement (relecture, réveil de l'écran, page ouverte)
        self.assertIn("function onEcranVuChanged() { if (Etat.ecranVu) t.verifier() }", self.terminal)
        self.assertIn("Terminal.verifier()", self.page)

    def test_la_commande_ne_part_jamais_dans_une_commande(self):
        # Seul le pid (entier vérifié) va dans hyprctl ; la commande n'est qu'affichée (Texte.qml, texte brut)
        self.assertIn("var n = entier(p !== undefined ? p : pid)", self.terminal)
        self.assertIn("""["hyprctl", "dispatch", "hl.dsp.focus({ window = 'pid:" + n + "' })"]""", self.terminal)
        self.assertNotRegex(self.code, r"execDetached\(.*commande|commande.*execDetached|\"sh\", \"-c\".*commande")
        self.assertIn('command: ["sh", "-c", "kill -0 \\"$1\\" 2>/dev/null", "sh", String(t.pidShell)]', self.terminal)
        self.assertIn("function entier(x) { var n = parseInt(x); return isNaN(n) || n < 0 ? 0 : n }", self.terminal)

    def test_zsh_sans_processus(self):
        # Seulement des commandes internes de zsh : print avec redirection, zf_rm (module zsh/files), jamais rm, date, $(…)
        code = re.sub(r"#.*", "", self.zsh)
        # $(<fichier) et $(( … )) sont internes à zsh ; $(commande) et `…` lanceraient un processus
        self.assertNotRegex(code, r"\$\((?![<(])|`|\brm\b|\bdate\b|\bmktemp\b|\bcat\b")
        self.assertIn("zmodload -F zsh/files b:zf_rm", self.zsh)
        self.assertIn("zmodload zsh/datetime", self.zsh)
        self.assertIn("(( duree >= 10 ))", self.zsh)
        self.assertIn("[[ -r ~/.config/nc/terminal.zsh ]] && source ~/.config/nc/terminal.zsh", (REPO / "home/.zshrc").read_text())

    def test_etat_et_pilule(self):
        self.assertIn('if (Terminal.enCours) a.push("terminal")', (QML / "Etat.qml").read_text())
        self.assertIn('(Terminal.enCours ? "terminal" : "repos")', self.compact)
        for mode in ("terminal: terminal", '"terminal-fini": terminalFini'):
            self.assertIn(mode, self.compact)
        self.assertIn('terminal: adaptee("terminal", 150)', (QML / "Ile.qml").read_text())
        self.assertIn('terminal: ["Terminal", "Terminal"]', (QML / "NavigationIle.qml").read_text())

    def test_pas_de_composant_neuf(self):
        for nom in ("Terminal.qml", "PageTerminal.qml", "Ile.qml", "Etat.qml"):
            self.assertEqual(len(re.findall(r"(?m)^\s*component ", (QML / nom).read_text())), 0, nom)

    def test_reglages_et_readme(self):
        with tempfile.TemporaryDirectory() as d:
            from unittest.mock import patch
            with patch.dict(os.environ, HOME=d), warnings.catch_warnings():
                warnings.simplefilter("ignore", ResourceWarning)
                reglages = runpy.run_path(str(REPO / "home/.local/bin/nc-reglages"))
        cles = reglages["PAR_CLE"]
        self.assertEqual(cles["ILE_TERMINAL"].defaut, "oui")
        self.assertEqual(cles["ILE_TERMINAL"].section, "Île")
        self.assertEqual(cles["ILE_PAGE_TERMINAL"].section, "Pages de l’île")
        self.assertIn("`ILE_TERMINAL`", (REPO / "README.md").read_text())


@unittest.skipUnless(shutil.which("zsh"), "zsh requis")
class Crochets(unittest.TestCase):
    def zsh(self, script, reglage=None, graphique=True):
        with tempfile.TemporaryDirectory(prefix="nc-terminal-zsh-") as d:
            root = Path(d)
            (root / "run").mkdir(mode=0o700)
            (root / ".config/nc").mkdir(parents=True)
            if reglage is not None:
                (root / ".config/nc/reglages.conf").write_text("ILE_TERMINAL=%s\n" % reglage)
            env = dict(os.environ, HOME=d, XDG_RUNTIME_DIR=str(root / "run"), ZDOTDIR=d)
            for k in ("WAYLAND_DISPLAY", "HYPRLAND_INSTANCE_SIGNATURE"):
                env.pop(k, None)
            if graphique:
                env["WAYLAND_DISPLAY"] = "wayland-test"
            prelude = "source %s\n" % ZSH
            r = subprocess.run(["zsh", "-f", "-c", prelude + script], env=env, text=True, capture_output=True, timeout=20)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertEqual(r.stderr, "")
            fichiers = {f.name: f.read_text() for f in (root / "run").iterdir()}
            return r.stdout, fichiers

    def test_commande_longue_puis_fin(self):
        out, fichiers = self.zsh('''
            _nc_terminal_preexec "make -j8" "make -j8" "make -j8"
            print -r -- "pendant: $(<$XDG_RUNTIME_DIR/nc-terminal)" | tr "\\n" "|"
            print
            _nc_terminal_debut=$(( EPOCHSECONDS - 12 ))
            (exit 3); _nc_terminal_precmd
            [[ -e $XDG_RUNTIME_DIR/nc-terminal ]] && print "fichier encore là"
            print -r -- "fini: $(<$XDG_RUNTIME_DIR/nc-terminal-fini)" | tr "\\n" "|"
        ''')
        self.assertRegex(out, r"pendant: \d+\|\d+\|\d+\|make -j8\|")
        self.assertNotIn("fichier encore là", out)
        self.assertRegex(out, r"fini: 3\|1[2-9]\|\d+\|\d+\|make -j8\|")
        self.assertNotIn("nc-terminal", [n for n in fichiers if n == "nc-terminal"])

    def test_commande_courte_sans_fini(self):
        out, fichiers = self.zsh('''
            _nc_terminal_preexec "ls" "ls" "ls"
            true; _nc_terminal_precmd
            (( $+functions[_nc_terminal_preexec] )) && print "crochets posés"
        ''')
        self.assertIn("crochets posés", out)
        self.assertEqual(fichiers, {})

    def test_commande_sur_plusieurs_lignes_et_longue(self):
        out, fichiers = self.zsh('''
            _nc_terminal_preexec $'for i in 1 2\\ndo echo $i\\ndone' "" ""
            print -r -- "$(<$XDG_RUNTIME_DIR/nc-terminal)" | sed -n 4p
            _nc_terminal_preexec "${(l:400::x:)}" "" ""
            print -r -- "$(<$XDG_RUNTIME_DIR/nc-terminal)" | sed -n 4p | wc -c
        ''')
        lignes = out.splitlines()
        self.assertEqual(lignes[0], "for i in 1 2 do echo $i done")
        self.assertEqual(int(lignes[1]), 201)        # 200 caractères et la fin de ligne

    def test_rien_hors_session_graphique_ni_reglage_non(self):
        for reglage, graphique in (("non", True), (None, False)):
            with self.subTest(reglage=reglage, graphique=graphique):
                out, fichiers = self.zsh('''
                    (( $+functions[_nc_terminal_preexec] )) && print "crochets posés"
                    print "fin"
                ''', reglage=reglage, graphique=graphique)
                self.assertNotIn("crochets posés", out)
                self.assertIn("fin", out)
                self.assertEqual(fichiers, {})

    def test_zshexit_retire_le_fichier(self):
        out, fichiers = self.zsh('''
            _nc_terminal_preexec "sleep 100" "" ""
            _nc_terminal_zshexit
            [[ -e $XDG_RUNTIME_DIR/nc-terminal ]] && print "fichier encore là"
            print "fin"
        ''')
        self.assertNotIn("fichier encore là", out)
        self.assertEqual(fichiers, {})


STUB_ETAT = '''pragma Singleton
import QtQuick
QtObject {
    property string dossierSession: "%s"
    property date maintenant: new Date()
    property bool ecranVu: true
    property var hauteurs: ({})
    property var reactions: []
    property int fermetures: 0
    function activite(t, d) { reactions = reactions.concat([t]) }
    function fermer() { fermetures++ }
    function duree(s) { var m = Math.floor(s / 60), x = s %% 60; return m + ":" + String(x).padStart(2, "0") }
    function annoncerHauteur(nom, h) { var t = Object.assign({}, hauteurs); t[nom] = Math.round(h); hauteurs = t }
}
'''
STUB_REGLAGES = '''pragma Singleton
import QtQuick
QtObject {
    property var valeurs: ({})
    readonly property bool en: false
    function val(k, d) { return valeurs[k] !== undefined ? valeurs[k] : d }
    function t(fr, en) { return fr }
}
'''
ENTETE = '''import QtQuick
import QtQuick.Window
import Quickshell
import Quickshell.Io
ShellRoot {
    id: racine
    property int etape: 0
    property int attente: 0
    property string run: "%s"
    property int moi: %d
    function verifier(v, m) { if (!v) { console.error("ÉCHEC étape " + etape + " : " + m); Qt.exit(2) } }
    function trouver(item, nom) { if (item.objectName === nom) return item; for (var i = 0; i < item.children.length; i++) { var r = trouver(item.children[i], nom); if (r) return r } return null }
    function ecrire(nom, texte) { var f = Qt.createQmlObject('import Quickshell.Io; FileView { blockWrites: true }', racine); f.path = run + "/" + nom; f.setText(texte); f.destroy() }
    Process { id: effacer; command: ["sh", "-c", "rm -f -- \\"$1\\"", "sh", ""] }
    function retirer(nom) { effacer.command = ["sh", "-c", "rm -f -- \\"$1\\"", "sh", run + "/" + nom]; effacer.running = true }
    Window {
        id: w; visible: true; width: 432; height: 300; color: "black"
        Item { id: cadre; x: 16; y: 16; width: 378; height: 268; Loader { id: page; anchors.fill: parent; source: "PageTerminal.qml" } }
    }
    Timer { interval: 100; running: true; repeat: true; onTriggered: {
'''
PIED = '''
    } }
    Timer { interval: 15000; running: true; onTriggered: { console.error("délai dépassé à l'étape " + racine.etape); Qt.exit(9) } }
}
'''


@unittest.skipUnless(shutil.which("qs"), "Quickshell requis")
class Banc(unittest.TestCase):
    def executer(self, scenario):
        with tempfile.TemporaryDirectory(prefix="nc-terminal-") as d:
            root = Path(d)
            (root / "run").mkdir(mode=0o700)
            for nom in ("Terminal", "PageTerminal", "Texte", "Ico", "Module", "Couleurs"):
                shutil.copy2(QML / (nom + ".qml"), root)
            (root / "Etat.qml").write_text(STUB_ETAT % (root / "run"))
            (root / "Reglages.qml").write_text(STUB_REGLAGES)
            singletons = ("Terminal", "Etat", "Reglages", "Couleurs")
            (root / "qmldir").write_text("\n".join(("singleton " if n in singletons else "") + n + " 1.0 " + n + ".qml"
                                                   for n in singletons + ("PageTerminal", "Texte", "Ico", "Module")))
            (root / "shell.qml").write_text(ENTETE % (root / "run", os.getpid()) + textwrap.indent(textwrap.dedent(scenario), " " * 8) + PIED)
            journal = Path(os.environ["NC_TEST_JOURNAL"])
            avant = journal.read_text()
            env = dict(os.environ, HOME=d, XDG_RUNTIME_DIR=str(root / "run"), XDG_CACHE_HOME=str(root / "cache"),
                       QT_QPA_PLATFORM="offscreen", QT_QUICK_BACKEND="software")
            env.pop("WAYLAND_DISPLAY", None)
            r = subprocess.run(["qs", "--no-color", "-p", str(root / "shell.qml")], env=env, text=True, capture_output=True, timeout=40)
            out = r.stdout + r.stderr
            self.assertEqual(r.returncode, 0, out)
            for erreur in ("ReferenceError", "TypeError", "Cannot assign", "Binding loop", "is not a type", "Unable to assign"):
                self.assertNotIn(erreur, out)
            return out, journal.read_text()[len(avant):]

    def test_commande_longue_puis_fin_et_retour_au_terminal(self):
        out, journal = self.executer('''
            // Seuil raccourci à 2 s (le début est en secondes entières : moins, et la commande serait déjà « longue » à la lecture)
            if (etape === 0) { Terminal.delai = 2000; verifier(!Terminal.enCours, "en cours sans fichier"); ecrire("nc-terminal", "4242\\n" + Math.floor(Date.now() / 1000) + "\\n" + moi + "\\nmake -j8\\n"); etape++ }
            else if (etape === 1) {
                if (Terminal.commande === "") { verifier(++attente < 20, "fichier jamais lu"); return }
                verifier(!Terminal.enCours, "en cours avant le seuil")
                verifier(Terminal.commande === "make -j8" && Terminal.pid === 4242, "lecture : " + Terminal.commande + " " + Terminal.pid)
                attente = 0; etape++
            } else if (etape === 2) {
                if (!Terminal.enCours) { verifier(++attente < 40, "jamais en cours après le seuil"); return }
                verifier(Terminal.dureeTexte.indexOf(":") > 0, "durée : " + Terminal.dureeTexte)
                verifier(page.item && trouver(page.item, "nc-terminal-aller").visible, "page Terminal")
                verifier(Etat.hauteurs.terminal > 60, "hauteur annoncée : " + Etat.hauteurs.terminal)
                retirer("nc-terminal"); attente = 0; etape++
            } else if (etape === 3) {
                if (Terminal.enCours) { verifier(++attente < 20, "toujours en cours sans fichier"); return }
                verifier(Terminal.commande === "", "commande gardée après la fin")
                ecrire("nc-terminal-fini", "2\\n75\\n" + Math.floor(Date.now() / 1000) + "\\n4242\\nsleep 75\\n"); attente = 0; etape++
            } else if (etape === 4) {
                if (!Terminal.fini) { verifier(++attente < 20, "fin jamais lue"); return }
                verifier(Terminal.fini.code === 2 && Terminal.fini.duree === 75 && Terminal.fini.commande === "sleep 75" && Terminal.fini.pid === 4242, "fin : " + JSON.stringify(Terminal.fini))
                verifier(Etat.reactions.indexOf("terminal-fini") >= 0, "pas de réaction « Terminée »")
                Terminal.aller(Terminal.fini.pid)
                verifier(Etat.fermetures === 1, "l'île ne se referme pas")
                etape++
            } else if (etape === 5) {
                // Même contenu réécrit : pas une seconde réaction ; contenu neuf : une nouvelle
                ecrire("nc-terminal-fini", "0\\n12\\n" + (Math.floor(Date.now() / 1000) + 1) + "\\n4243\\nsleep 12\\n"); attente = 0; etape++
            } else if (etape === 6) {
                if (Terminal.fini.code !== 0) { verifier(++attente < 20, "seconde fin jamais lue"); return }
                verifier(Etat.reactions.filter(r => r === "terminal-fini").length === 2, "réactions : " + Etat.reactions)
                Qt.quit()
            }
        ''')
        self.assertIn("hyprctl dispatch hl.dsp.focus({ window = 'pid:4242' })", journal)
        self.assertNotIn("sleep 75", journal)

    def test_shell_disparu_fichier_orphelin(self):
        out, journal = self.executer('''
            if (etape === 0) { Terminal.delai = 400; ecrire("nc-terminal", "4242\\n" + (Math.floor(Date.now() / 1000) - 60) + "\\n999999\\nsleep 1000\\n"); etape++ }
            else if (etape === 1) {
                if (++attente < 8) return
                verifier(!Terminal.enCours && Terminal.commande === "", "fichier orphelin gardé : " + Terminal.commande)
                // Shell vivant (ce test), commande déjà longue : en cours tout de suite
                ecrire("nc-terminal", "4242\\n" + (Math.floor(Date.now() / 1000) - 60) + "\\n" + moi + "\\nsleep 1000\\n"); attente = 0; etape++
            } else if (etape === 2) {
                if (!Terminal.enCours) { verifier(++attente < 20, "commande déjà longue jamais en cours"); return }
                verifier(Terminal.duree >= 59, "durée reprise : " + Terminal.duree)
                Qt.quit()
            }
        ''')
        self.assertNotIn("hyprctl", journal)

    def test_reglage_non(self):
        self.executer('''
            if (etape === 0) { Terminal.delai = 200; Reglages.valeurs = { ILE_TERMINAL: "non" }; ecrire("nc-terminal", "4242\\n" + (Math.floor(Date.now() / 1000) - 60) + "\\n" + moi + "\\nmake\\n"); ecrire("nc-terminal-fini", "0\\n30\\n" + Math.floor(Date.now() / 1000) + "\\n4242\\nmake\\n"); etape++ }
            else if (etape === 1) {
                if (++attente < 8) return
                verifier(!Terminal.enCours && Terminal.commande === "" && Terminal.fini === null, "ILE_TERMINAL=non : activité montrée")
                verifier(Etat.reactions.length === 0, "ILE_TERMINAL=non : réaction " + Etat.reactions)
                Reglages.valeurs = {}; retirer("nc-terminal"); attente = 0; etape++
            } else if (etape === 2) {
                if (++attente < 3) return
                ecrire("nc-terminal", "4242\\n" + (Math.floor(Date.now() / 1000) - 60) + "\\n" + moi + "\\nmake\\n"); attente = 0; etape++
            } else if (etape === 3) {
                if (!Terminal.enCours) { verifier(++attente < 20, "réglage remis : jamais en cours"); return }
                Reglages.valeurs = { ILE_TERMINAL: "non" }; etape++
            } else if (etape === 4) {
                verifier(!Terminal.enCours, "réglage coupé en pleine commande : l'activité reste")
                Qt.quit()
            }
        ''')


if __name__ == "__main__":
    unittest.main()

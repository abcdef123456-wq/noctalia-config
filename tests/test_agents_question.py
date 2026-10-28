"""Question d'un agent (Claude, Gemini, Copilot, Codex…) laissée dans son terminal : jamais perdue.

Chaque notification d'attente garde le texte entier de la question dans l'état (pas l'extrait de la notification) et
porte « Voir », qui ouvre l'île sur cette session (faux notify-send qui répond « default », faux qs qui journalise) ;
la pilule garde l'indicateur et un clic dessus ouvre la page des agents sur cette session (QML hors écran).
Rien dans le vrai HOME : dossier temporaire, programmes simulés."""
import contextlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import textwrap
import time
import types
import unittest
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[1]
BIN = REPO / "home/.local/bin"
QML = REPO / "home/.config/quickshell/nc-ile"
LONG = ("Puis-je supprimer le dossier build/ puis relancer toute la suite de tests, sachant que cela prendra environ "
        "dix minutes et effacera les artefacts générés hier soir ? Réponds oui ou non.")


class Module(unittest.TestCase):
    """nc-claude chargé comme module, dans un dossier temporaire."""
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        m = self.m = types.ModuleType("nc_question")
        m.__file__ = str(BIN / "nc-claude")
        exec(compile((BIN / "nc-claude").read_text(), m.__file__, "exec"), m.__dict__)
        m.HOME = str(self.root)
        m.RUN = str(self.root / "run")
        m.ETAT, m.VERROU, m.REPONSES = (str(Path(m.RUN) / n) for n in ["etat.json", "etat.lock", "reponses"])
        m.JOURNAL = str(Path(m.RUN) / "agents.log")
        m.reglage = lambda k, defaut: defaut
        m.ile_active = lambda: True
        m.terminal_actif = lambda pid: False
        m.reperer_terminal = lambda s: s.update(terminal=50, shell=60, classe="kitty")
        self.notifs = []
        m.notifier = lambda s, titre, texte, voir=False: self.notifs.append((s["id"], titre, texte, voir))
        # Codex : jamais le vrai « codex --version » ni la vraie ~/.codex (CODEX_HOME retiré, HOME temporaire)
        m.version_codex = lambda: (0, 163, 0)
        env = patch.dict(os.environ)
        env.start()
        self.addCleanup(env.stop)
        os.environ.pop("CODEX_HOME", None)

    def hook(self, **ev):
        with contextlib.redirect_stdout(io.StringIO()) as sortie, patch("sys.stdin", io.StringIO(json.dumps(ev))):
            self.m.hook()
        return sortie.getvalue()

    def session(self, sid):
        return json.loads(Path(self.m.ETAT).read_text())["sessions"][sid]


class Claude(Module):
    def test_chaque_attente_garde_la_question_entiere_et_porte_voir(self):
        for t, etat in (("permission_prompt", "terminal"), ("elicitation_dialog", "terminal"),
                        ("agent_needs_input", "terminal"), ("idle_prompt", "attente")):
            with self.subTest(t=t):
                self.notifs.clear()
                self.hook(hook_event_name="UserPromptSubmit", session_id=t, cwd="/p")
                self.hook(hook_event_name="Notification", session_id=t, cwd="/p", notification_type=t, message=LONG)
                s = self.session(t)
                self.assertEqual(s["etat"], etat)
                self.assertEqual(s["question"]["texte"], LONG)            # pas l'extrait de 120 caractères
                self.assertEqual(len(self.notifs), 1, "notification d'attente absente")
                self.assertTrue(self.notifs[0][3], "action « Voir » absente")
                self.assertLess(len(self.notifs[0][2]), len(LONG))       # la notification, elle, reste courte

    def test_idle_prompt_montre_la_derniere_reponse_entiere(self):
        reponse = "J'ai fini. " + LONG * 3
        self.hook(hook_event_name="UserPromptSubmit", session_id="A", cwd="/p")
        self.hook(hook_event_name="Stop", session_id="A", cwd="/p", last_assistant_message=reponse)
        self.hook(hook_event_name="Notification", session_id="A", cwd="/p", notification_type="idle_prompt",
                  message="Claude is waiting for your input")
        self.assertEqual(self.session("A")["question"]["texte"], reponse)

    def test_la_question_part_quand_claude_repart(self):
        # Un PostToolUse ne suffit pas : avec des outils en parallèle, un autre peut finir pendant que la question attend
        self.hook(hook_event_name="Notification", session_id="P", cwd="/p", notification_type="permission_prompt", message=LONG)
        self.hook(hook_event_name="PostToolUse", session_id="P", cwd="/p", tool_name="Read", tool_input={})
        self.assertEqual(self.session("P")["question"]["texte"], LONG)
        for suite in (dict(hook_event_name="PreToolUse", tool_name="Read", tool_input={}),
                      dict(hook_event_name="UserPromptSubmit"), dict(hook_event_name="Stop")):
            with self.subTest(suite=suite["hook_event_name"]):
                self.hook(hook_event_name="Notification", session_id="B", cwd="/p",
                          notification_type="permission_prompt", message=LONG)
                self.hook(session_id="B", cwd="/p", **suite)
                s = self.session("B")
                self.assertNotIn(s["etat"], ("terminal", "demande"))
                self.assertNotIn("question", s)

    def test_question_de_l_ile_laissee_au_terminal(self):
        # AskUserQuestion : carte dans l'île ; pas de réponse (retour au terminal) : la question reste en vue
        self.m.attendre = lambda ident, pid: None
        os.environ["NC_CLAUDE_SYNC"] = "1"
        self.addCleanup(os.environ.pop, "NC_CLAUDE_SYNC", None)
        self.hook(hook_event_name="PreToolUse", session_id="C", cwd="/p", tool_name="AskUserQuestion",
                  tool_input={"questions": [{"question": "Quelle base ?", "options": [{"label": "Postgres"}, {"label": "SQLite"}]}]})
        s = self.session("C")
        self.assertEqual(s["etat"], "terminal")
        self.assertEqual(s["question"]["texte"], "Quelle base ?\n• Postgres\n• SQLite")

    def test_notif_ouverte_sans_notification(self):
        # os.kill(-1, 0) réussissait toujours : idle_prompt ne notifiait jamais
        self.assertFalse(self.m.notif_ouverte({}, "X"))
        moi = "%d:%s" % (os.getpid(), self.m.debut_pid(os.getpid()))      # « pid:démarrage », comme notification()
        self.assertTrue(self.m.notif_ouverte({"notifs": {"X": moi}}, "X"))
        self.assertFalse(self.m.notif_ouverte({"notifs": {"X": "%d:1" % os.getpid()}}, "X"))   # pid repris par un autre


class AutresAgents(Module):
    def test_attente_des_autres_ia_garde_leur_question(self):
        for ia, nom, ev in (("gemini", "Notification", {"notification_type": "ToolPermission", "message": LONG}),
                            ("copilot", "notification", {"notification_type": "permission_prompt", "message": LONG}),
                            ("qwen", "Notification", {"notification_type": "permission_prompt", "details": LONG})):
            with self.subTest(ia=ia):
                self.m.lire_entree = lambda: {"session_id": "X", "cwd": "/p"}
                with contextlib.redirect_stdout(io.StringIO()):
                    self.m.hook_ia(ia, "UserPromptSubmit")
                    self.m.lire_entree = lambda: dict(ev, session_id="X", cwd="/p")
                    self.m.hook_ia(ia, nom)
                s = self.session(ia + "-X")
                self.assertEqual((s["etat"], s["question"]["texte"]), ("terminal", LONG))
                self.m.lire_entree = lambda: {"session_id": "X", "cwd": "/p", "tool_name": "read_file", "tool_input": {}}
                with contextlib.redirect_stdout(io.StringIO()):
                    self.m.hook_ia(ia, "PostToolUse" if ia != "gemini" else "AfterTool")
                self.assertNotIn("question", self.session(ia + "-X"))
        self.assertEqual(self.notifs, [], "Gemini, Copilot et Qwen ont leur propre notification : pas de doublon")

    def evenements(self, ia, *noms, **ev):
        for nom in noms:
            self.m.lire_entree = lambda: dict(ev, session_id="O", cwd="/projets/site")
            with contextlib.redirect_stdout(io.StringIO()):
                self.m.hook_ia(ia, nom)

    def test_agent_sans_notification_propre_recoit_voir(self):
        # OpenCode (son extension : permission.asked → « permission ») n'avertit pas lui-même : notre « Voir »
        self.evenements("opencode", "prompt", "permission")
        s = self.session("opencode-O")
        self.assertEqual(s["etat"], "terminal")
        self.assertEqual(len(self.notifs), 1, "notification « Voir » absente pour OpenCode")
        sid, titre, texte, voir = self.notifs[0]
        self.assertEqual((sid, voir), ("opencode-O", True))
        self.assertIn("OpenCode", titre)
        self.assertIn("site", texte)
        # Reprise (réponse donnée dans son terminal) : la session repart, et la notification sait qu'elle peut partir
        avant = s["maj"]
        time.sleep(0.01)
        self.evenements("opencode", "reprise")
        s = self.session("opencode-O")
        self.assertEqual(s["etat"], "travail")
        self.assertGreater(s["maj"], avant)

    def codex_attend(self, config=None, version=(0, 163, 0)):
        """Demande de Codex sans île (elle reste dans son terminal) ; config : contenu de ~/.codex/config.toml."""
        self.notifs.clear()
        f = self.root / ".codex/config.toml"
        if config is None:
            with contextlib.suppress(FileNotFoundError):
                f.unlink()
        else:
            f.parent.mkdir(exist_ok=True)
            f.write_text(config)
        self.m.version_codex = lambda: version
        self.m.ile_active = lambda: False
        self.m.demande(dict(session_id="Z", cwd="/p", tool_name="Bash", tool_input={"command": "ls"}), "permission", "codex")
        self.assertEqual(self.session("codex-Z")["etat"], "terminal")
        return [n for n in self.notifs if n[0] == "codex-Z" and n[3]]

    def test_codex_notifications_par_defaut_pas_de_doublon(self):
        # tui.notifications actif par défaut depuis Codex 0.59.0 : il a sa propre notification
        self.assertEqual(self.codex_attend(), [])
        self.assertEqual(self.codex_attend("[tui]\nscreen_reader_detection_done = true\n"), [])
        self.assertEqual(self.codex_attend(version=None), [], "version inconnue : pas de doublon")

    def test_codex_ancien_ou_notifications_coupees_recoit_voir(self):
        self.assertEqual(len(self.codex_attend(version=(0, 58, 0))), 1, "défaut coupé jusqu'à 0.58.0")
        self.assertEqual(len(self.codex_attend("[tui]\nnotifications = false\n")), 1)
        self.assertEqual(len(self.codex_attend('[tui]\nnotifications = ["agent-turn-complete"]\n')), 1,
                         "liste sans approval-requested")

    def test_codex_notifications_activees_dans_sa_config(self):
        self.assertEqual(self.codex_attend("[tui]\nnotifications = true\n", version=(0, 58, 0)), [])
        self.assertEqual(self.codex_attend('[tui]\nnotifications = ["approval-requested"]\n', version=(0, 58, 0)), [])
        # Config illisible : le défaut de la version
        self.assertEqual(len(self.codex_attend("[tui\n", version=(0, 50, 0))), 1)
        # $CODEX_HOME l'emporte sur ~/.codex
        autre = self.root / "codex-home"
        autre.mkdir()
        (autre / "config.toml").write_text("[tui]\nnotifications = false\n")
        os.environ["CODEX_HOME"] = str(autre)
        self.assertEqual(len(self.codex_attend("[tui]\nnotifications = true\n")), 1)

    def test_antigravity_cursor_kiro_amp_sans_attente(self):
        """Aucun de leurs événements n'est une attente : jamais de notification « Voir »."""
        for nom in self.m.AGY_EVENEMENTS:
            self.m.lire_entree = lambda: {"conversationId": "A", "workspacePaths": ["/p"],
                                          "toolCall": {"name": "run_command", "args": {"CommandLine": "ls"}}}
            with contextlib.redirect_stdout(io.StringIO()):
                self.m.hook_agy(nom)
        for ia in ("cursor", "kiro"):
            self.evenements(ia, *self.m.EVENEMENTS[ia], tool_name="read_file", tool_input={})
        self.evenements("amp", "prompt", "tool", "stop", tool="read", args={})
        self.assertEqual(self.notifs, [])
        sessions = json.loads(Path(self.m.ETAT).read_text())["sessions"]   # (cursor : sessionEnd l'a retirée)
        self.assertTrue({"antigravity-A", "kiro-O", "amp-O"} <= set(sessions))
        self.assertFalse([k for k, s in sessions.items() if s["etat"] == "terminal"])

    def test_demande_codex_sans_reponse_reste_en_vue(self):
        self.m.attendre = lambda ident, pid: None
        self.m.demande(dict(session_id="Y", cwd="/p", tool_name="Bash", tool_input={"command": "rm -rf build"}),
                       "permission", "codex")
        s = self.session("codex-Y")
        self.assertEqual(s["etat"], "terminal")
        self.assertIn("rm -rf build", s["question"]["texte"])


class Notification(unittest.TestCase):
    """« nc-claude notification … voir » lancé pour de vrai : faux notify-send qui répond « default »."""
    def lancer(self, reponse_qs, voir=True):
        with tempfile.TemporaryDirectory(prefix="nc-question-") as d:
            root = Path(d)
            b = root / "bin"
            b.mkdir()
            (root / "run/nc-claude").mkdir(parents=True, mode=0o700)
            (root / "run/nc-claude/etat.json").write_text(json.dumps({"sessions": {"S1": {
                "id": "S1", "etat": "terminal", "terminal": 50, "shell": 60, "classe": "kitty", "maj": time.time(),
                "question": {"titre": "Claude t'attend", "texte": LONG}}}, "demandes": {}}))
            (b / "notify-send").write_text('#!/bin/sh\nprintf "%s\\n" "$*" >> "$LOG/notify.log"; echo 7; sleep 0.3; echo default\n')
            (b / "qs").write_text(f'#!/bin/sh\nprintf "%s\\n" "$*" >> "$LOG/qs.log"\necho {reponse_qs}\n')
            (b / "hyprctl").write_text('#!/bin/sh\ncase "$*" in *clients*) echo "[]";; *activewindow*) echo "{}";;'
                                       ' *) printf "%s\\n" "$*" >> "$LOG/hyprctl.log";; esac\n')
            (b / "systemctl").write_text("#!/bin/sh\nexit 0\n")
            for f in b.iterdir():
                f.chmod(0o755)
            env = dict(PATH=f"{b}:/usr/bin:/bin", HOME=str(root / "home"), XDG_RUNTIME_DIR=str(root / "run"),
                       LOG=str(root), NC_LANGUE="fr")
            r = subprocess.run([str(BIN / "nc-claude"), "notification", "S1", "Claude t'attend", "extrait…"]
                               + (["voir"] if voir else []), env=env, capture_output=True, text=True, timeout=20)
            self.assertEqual(r.returncode, 0, r.stderr)
            lire = lambda n: (root / n).read_text() if (root / n).exists() else ""
            return lire("notify.log"), lire("qs.log"), lire("hyprctl.log")

    def test_voir_ouvre_l_ile_sur_la_session(self):
        notif, qs, hypr = self.lancer("oui")
        self.assertIn("default=Voir", notif)
        self.assertEqual(qs.strip(), "-c nc-ile ipc call ile agent S1")
        self.assertEqual(hypr, "", "le terminal ne doit pas passer devant l'île")

    def test_sans_page_des_agents_le_terminal(self):
        notif, qs, hypr = self.lancer("non")
        self.assertIn("agent S1", qs)
        self.assertIn("pid:50", hypr)

    def test_fin_de_travail_reste_sur_le_terminal(self):
        notif, qs, hypr = self.lancer("oui", voir=False)
        self.assertIn("default=Ouvrir", notif)
        self.assertEqual(qs, "")
        self.assertIn("pid:50", hypr)


@unittest.skipUnless(shutil.which("qs"), "Quickshell requis")
class Ile(unittest.TestCase):
    """Agents.qml, Claude.qml et la navigation réelle d'Etat.qml, hors écran."""
    def executer(self, etat, scenario):
        with tempfile.TemporaryDirectory(prefix="nc-question-qml-") as d:
            root = Path(d)
            (root / "runtime/nc-claude").mkdir(parents=True, mode=0o700)
            (root / "runtime/nc-claude/etat.json").write_text(json.dumps(etat))
            for nom in ("Agents", "Reglages", "Claude", "DemandeClaude", "Texte", "Ico", "Defilement", "Couleurs"):
                shutil.copy2(QML / (nom + ".qml"), root)
            (root / "Etincelle.qml").write_text("import QtQuick\nItem { property real taille: 16; property bool tourne: false; property string agent: \"claude\" }")
            source = (QML / "Etat.qml").read_text()
            bloc = source[source.index("    property string ecranOuvert:"):source.index("    // Spotlight (Super + R)")]
            (root / "Etat.qml").write_text(textwrap.dedent('''\
                pragma Singleton
                import QtQuick
                QtObject {
                 property var maintenant: new Date()
                 property var lecteur: null
                 property var dernierLecteur: null
                 property string titre: ""
                 property bool joue: false
                 property real finLecture: 0
                 property real minuteurFin: 0
                 property bool enCharge: false
                 property bool batteriePc: false
                 property bool jeu: false
                 property var meteo: ({})
                 property string meteoErreur: ""
                 property bool recherche: false
                 property string activiteType: ""
                 function activite(n,d) {}
                 function lire() {}
                 function lireLuminosite(a) {}
                 function lirePage() {}
                ''') + bloc + "\n}")
            # Activités Appel et Terminal (Appel.qml, Terminal.qml) : lues par Etat.activites, ici sans appel ni commande
            for nom in ("Appel", "Terminal"):
                (root / (nom + ".qml")).write_text("pragma Singleton\nimport QtQuick\nQtObject { property bool enCours: false }")
            singletons = ("Agents", "Reglages", "Couleurs", "Etat", "Appel", "Terminal")
            (root / "qmldir").write_text("\n".join(("singleton " if n in singletons else "") + n + " 1.0 " + n + ".qml"
                                                   for n in singletons + ("Claude", "DemandeClaude", "Texte", "Ico", "Defilement", "Etincelle")))
            (root / "shell.qml").write_text('''import QtQuick
import QtQuick.Window
import Quickshell
ShellRoot {
 property int etape: 0
 function verifier(v,m) { if (!v) { console.error("ECHEC " + m); Qt.exit(2); throw new Error(m) } }
 function trouver(o, nom) { if (!o) return null; if (o.objectName === nom) return o
  var l = (o.children || []).concat(o.contentItem ? [o.contentItem] : [])
  for (var i = 0; i < l.length; i++) { var r = trouver(l[i], nom); if (r) return r } return null }
 Window { visible: true; width: 480; height: 900; Claude { id: page; width: 440; height: 880 } }
 Timer { interval: 150; running: true; repeat: true; onTriggered: {
''' + scenario + '''
 } }
 Timer { interval: 6000; running: true; onTriggered: { console.error("ECHEC délai"); Qt.exit(9) } }
}''')
            env = dict(os.environ, HOME=d, XDG_RUNTIME_DIR=str(root / "runtime"), XDG_CACHE_HOME=str(root / "cache"),
                       QT_QPA_PLATFORM="offscreen", QT_QUICK_BACKEND="software", NC_LANGUE="fr")
            env.pop("WAYLAND_DISPLAY", None)
            r = subprocess.run(["qs", "--no-color", "-p", str(root / "shell.qml")], env=env, text=True,
                               capture_output=True, timeout=15)
            out = r.stdout + r.stderr
            self.assertEqual(r.returncode, 0, out)
            for faute in ("ECHEC", "ReferenceError", "TypeError", "Binding loop", "is not a type"):
                self.assertNotIn(faute, out)

    def etat(self, age_question=3600):
        t = time.time()
        return {"sessions": {
            "Q": {"id": "Q", "etat": "terminal", "projet": "projet-q", "maj": t - age_question, "terminal": 50,
                  "question": {"titre": "Claude t'attend", "texte": LONG}},
            "R": {"id": "R", "agent": "gemini", "etat": "travail", "projet": "projet-r", "maj": t}}, "demandes": {}}

    def test_clic_sur_la_pilule_ouvre_la_question(self):
        # Question vieille d'une heure : l'indicateur reste, et le clic sur la pilule l'ouvre (session en tête)
        self.executer(self.etat(), '''
 if (etape === 0) { if (Agents.sessions.length === 2) etape++; return }
 if (etape === 1) {
  verifier(Agents.attendTerminal && Agents.attend.id === "Q", "indicateur perdu après 15 min")
  verifier(Etat.vues.indexOf("claude") >= 0, "page des agents absente")
  verifier(Agents.ouvrirAttente("TEST") === true, "clic sur la pilule ignoré")
  etape++; return
 }
 if (etape === 2) {
  verifier(Etat.ecranOuvert === "TEST" && Etat.vueActive === "claude", "île pas sur la page des agents : " + Etat.vueActive)
  verifier(Agents.sessionsPage[0].id === "Q", "session pas en tête")
  var t = trouver(page, "nc-question-texte")
  verifier(t && t.visible && t.text === "''' + LONG + '''", "texte complet absent de la page")
  Etat.fermer(); etape++; return
 }
 if (etape === 3) { verifier(Agents.cible === "", "session voulue gardée après fermeture"); Qt.quit() }
''')

    def test_voir_ouvre_l_ile_sur_la_session(self):
        # ipc agent(session) : l'île s'ouvre (basculer), puis Agents.montrer place la session et va sur sa page
        self.executer(self.etat(age_question=10), '''
 if (etape === 0) { if (Agents.sessions.length === 2) etape++; return }
 if (etape === 1) {
  Reglages.valeurs = ({}); Etat.basculer("TEST", true)
  verifier(Etat.vueActive === "centre", "départ")
  Agents.montrer("Q"); etape++; return
 }
 if (etape === 2) {
  verifier(Etat.vueActive === "claude", "« Voir » n'a pas ouvert la page des agents")
  verifier(Agents.sessionsPage[0].id === "Q", "session pas en tête")
  Qt.quit()
 }
''')

    def test_demande_de_la_session_voulue_d_abord(self):
        etat = self.etat()
        etat["demandes"] = {"d1": {"id": "d1", "session": "R", "genre": "question", "titre": "Autre", "options": ["a"], "t": 1},
                            "d2": {"id": "d2", "session": "Q", "genre": "question", "titre": "La mienne", "options": ["b"], "t": 2}}
        self.executer(etat, '''
 if (etape === 0) { if (Agents.demandes.length === 2) etape++; return }
 if (etape === 1) { verifier(Agents.demande.id === "d1", "plus ancienne d'abord"); Agents.cible = "Q"; etape++; return }
 if (etape === 2) { verifier(Agents.demande.id === "d2", "demande de la session voulue pas montrée"); Qt.quit() }
''')


if __name__ == "__main__":
    unittest.main()

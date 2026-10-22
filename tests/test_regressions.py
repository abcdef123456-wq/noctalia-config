"""Régressions isolées : aucun accès à la session graphique ou aux réglages installés.

Lancer : python3 -B -m unittest discover -s tests -v
"""
import ast
from concurrent.futures import ThreadPoolExecutor
import contextlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import types
import unittest

REPO = Path(__file__).resolve().parents[1]
BIN = REPO / "home/.local/bin"
QML = REPO / "home/.config/quickshell/nc-ile"

FAKE_HYPR = r'''#!/usr/bin/env python3
import json,os,re,sys
from pathlib import Path
p=Path(os.environ['NC_TEST_STATE']); d=json.loads(p.read_text()); cmd=' '.join(sys.argv[1:])
if cmd=='clients -j':
 if d.get('clients_unavailable'): sys.exit(1)
 print(json.dumps(d['clients']))
elif cmd=='monitors -j': print(json.dumps([dict(id=0,name='TEST',x=0,y=0,width=1600,height=1000,scale=1,transform=0,focused=True,activeWorkspace=dict(id=1),specialWorkspace=dict(name=''))]))
elif cmd.startswith('dispatch'):
 if 'window.move(' in cmd:
  a=re.search("window = 'address:(0x[0-9a-fA-F]+)'",cmd)[1]
  if a in d.get('fail',[]): sys.exit(1)
  m=re.search(r"workspace = ('[^']+'|[0-9]+)",cmd)[1].strip("'")
  for c in d['clients']:
   if c['address']==a: c['workspace']=dict(id=-99 if m=='special:reduites' else int(m),name=m)
   elif c['workspace']['id']>0: c.update(at=[0,0],size=[1500,900])
  if m!='special:reduites' and d.get('fail_query_after_restore'): d['clients_unavailable']=True
  p.write_text(json.dumps(d))
 elif 'focus({' in cmd and 'address:' in cmd:
  d['active']=re.search("address:(0x[0-9a-fA-F]+)",cmd)[1]; d.setdefault('focus',[]).append(d['active']); p.write_text(json.dumps(d))
elif cmd=='cursorpos': print('12, 34')
elif cmd=='activewindow -j': print(json.dumps(next((c for c in d['clients'] if c['address']==d.get('active')),{})))
else: sys.exit(1)
'''


class Fenetres(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "bin").mkdir()
        for name, code in [("hyprctl", FAKE_HYPR), ("sleep", "#!/bin/sh\nexit 0\n")]:
            p = self.root / "bin" / name
            p.write_text(code)
            p.chmod(0o755)
        self.state = self.root / "state.json"
        self.original = [dict(address=f"0x{i:x}", at=[i * 100, 50], size=[400, 600],
                              workspace=dict(id=1, name="1"), monitor=0, floating=False) for i in range(1, 4)]
        self.write_state()
        self.env = dict(os.environ, HOME=str(self.root), XDG_RUNTIME_DIR=str(self.root),
                        PATH=str(self.root / "bin") + os.pathsep + os.environ["PATH"], NC_TEST_STATE=str(self.state))

    def write_state(self, fail=()):
        self.state.write_text(json.dumps(dict(clients=self.original, fail=fail)))

    def test_outil_ramene_ici_met_devant_puis_range(self):
        """Le raccourci d'une fenêtre-outil de l'île : ailleurs, elle vient ici ; ici derrière, devant ; ici active, rangée ;
        rangée, elle revient ici ; une fenêtre d'une autre appli au même titre est ignorée."""
        outil = dict(address="0xa1", at=[10, 52], size=[1580, 938], workspace=dict(id=3, name="3"), monitor=0, floating=True,
                     title="Réglages du bureau", **{"class": "org.quickshell"})
        intrus = dict(address="0xb2", at=[0, 0], size=[100, 100], workspace=dict(id=1, name="1"), monitor=0, floating=False,
                      title="Réglages du bureau", **{"class": "firefox"})
        self.original = [*self.original, intrus, outil]
        self.write_state()
        def etat():
            return json.loads(self.state.read_text())
        def ou():
            return next(c for c in etat()["clients"] if c["address"] == "0xa1")["workspace"]["name"]
        r = self.run_window("outil", "Réglages du bureau")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(ou(), "1", "sur un autre bureau : amenée sur le bureau affiché")
        self.assertEqual(etat().get("active"), "0xa1", "et active")
        d = etat(); d["active"] = "0x1"; self.state.write_text(json.dumps(d))
        self.assertEqual(self.run_window("outil", "Réglages du bureau").returncode, 0)
        self.assertEqual((ou(), etat().get("active")), ("1", "0xa1"), "ici mais derrière : mise au premier plan, pas rangée")
        self.assertEqual(self.run_window("outil", "Réglages du bureau").returncode, 0)
        self.assertEqual(ou(), "special:reduites", "ici et active : rangée")
        self.assertEqual(self.run_window("outil", "Réglages du bureau").returncode, 0)
        self.assertEqual(ou(), "1", "rangée : revient sur le bureau affiché")
        self.assertEqual(next(c for c in etat()["clients"] if c["address"] == "0xb2")["workspace"]["name"], "1", "l'intrus n'a pas bougé")
        self.assertEqual(self.run_window("outil", "Absente").returncode, 3)
        self.assertEqual(self.run_window("outil").returncode, 2)

    def run_window(self, *args):
        return subprocess.run(["bash", str(BIN / "nc-fenetre"), *args], env=self.env,
                              capture_output=True, text=True, timeout=20)

    def rectangles(self):
        p = self.root / "nc-reduites-tailles"
        return {r[0]: r[1:6] for r in (line.split() for line in p.read_text().splitlines())} if p.exists() else {}

    def test_hide_all_uses_geometry_before_retiling(self):
        r = self.run_window("tout-masquer")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.rectangles(), {c['address']: list(map(str, c['at'] + c['size'] + [1])) for c in self.original})

    def test_overview_uses_click_geometry(self):
        record = dict(address="0x1", x=20, y=30, w=500, h=700, ws=1, fl=False, mx=0, my=0, mw=1600, mh=1000)
        r = self.run_window("reduire-lot", json.dumps([record]))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.rectangles()['0x1'], ['20', '30', '500', '700', '1'])

    def test_failed_hide_does_not_create_saved_state(self):
        self.write_state(fail=['0x1'])
        r = self.run_window("reduire", "0x1")
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual(self.rectangles(), {})
        self.assertFalse((self.root / 'nc-reduites').exists())

    def test_failed_restore_keeps_saved_state(self):
        self.assertEqual(self.run_window("reduire", "0x1").returncode, 0)
        d = json.loads(self.state.read_text()); d['fail'] = ['0x1']; self.state.write_text(json.dumps(d))
        before = self.rectangles()
        self.assertNotEqual(self.run_window("aller", "0x1").returncode, 0)
        self.assertEqual(self.rectangles(), before)

    def test_restore_with_failed_confirmation_keeps_saved_state(self):
        self.assertEqual(self.run_window("reduire", "0x1").returncode, 0)
        d = json.loads(self.state.read_text()); d['fail_query_after_restore'] = True; self.state.write_text(json.dumps(d))
        before = self.rectangles()
        self.assertNotEqual(self.run_window("aller", "0x1", "2").returncode, 0)
        self.assertEqual(self.rectangles(), before)

    def test_parallel_hides_keep_every_entry(self):
        with ThreadPoolExecutor(3) as pool:
            results = list(pool.map(lambda c: self.run_window('reduire', c['address']), self.original))
        self.assertTrue(all(r.returncode == 0 for r in results), [r.stderr for r in results])
        self.assertEqual(set(self.rectangles()), {'0x1', '0x2', '0x3'})

    def test_restore_removes_only_its_entry(self):
        self.assertEqual(self.run_window('tout-masquer').returncode, 0)
        self.assertEqual(self.run_window('aller', '0x2', '2').returncode, 0)
        self.assertEqual(set(self.rectangles()), {'0x1', '0x3'})


class Coucou(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.module = types.ModuleType('nc_test')
        self.module.__file__ = str(BIN / 'nc-claude')
        exec(compile((BIN / 'nc-claude').read_text(), self.module.__file__, 'exec'), self.module.__dict__)
        m = self.module
        m.HOME = str(self.root)
        m.RUN = str(self.root / 'run')
        m.ETAT, m.VERROU, m.REPONSES = (str(Path(m.RUN) / n) for n in ['etat.json', 'etat.lock', 'reponses'])
        self.settings = {'CLAUDE_ILE': 'non', 'CODEX_ILE': 'oui', 'CLAUDE_DEMANDES': 'ile'}
        m.reglage = lambda k, default: self.settings.get(k, default)
        m.ile_active = lambda: True
        m.terminal_actif = lambda pid: False
        m.reperer_terminal = lambda s: s.update(terminal=123, shell=456, classe='test')
        m.notifier = lambda *args: None

    def test_codex_request_works_when_claude_disabled(self):
        m = self.module
        def answer(ident, pid):
            d = json.loads(Path(m.ETAT).read_text())
            self.assertEqual(d['demandes'][ident]['agent'], 'codex')
            return 'non'
        m.attendre = answer
        with contextlib.redirect_stdout(io.StringIO()) as output:
            m.demande(dict(session_id='A', cwd='/project', tool_name='Bash', tool_input={}), 'permission', 'codex')
        self.assertEqual(json.loads(output.getvalue())['hookSpecificOutput']['decision']['behavior'], 'deny')

    def test_disabled_agent_never_waits(self):
        self.settings['CODEX_ILE'] = 'non'
        self.module.attendre = lambda *args: self.fail('hidden request must not wait')
        self.module.demande(dict(session_id='A'), 'permission', 'codex')
        self.assertFalse(Path(self.module.ETAT).exists())

    def test_remote_opencode_does_not_claim_server_terminal(self):
        self.module.suivre('opencode', 'B', '/project-B', 'debut', terminal_cwd='/project-A')
        s = json.loads(Path(self.module.ETAT).read_text())['sessions']['opencode-B']
        self.assertEqual(s['projet'], 'project-B')
        self.assertEqual((s['terminal'], s['shell']), (0, 0))

    def test_plugin_update_preserves_backup_and_is_idempotent(self):
        p = self.root / 'plugins/nc-ile.js'; p.parent.mkdir(); p.write_text('// previous plugin')
        self.module.chemin = lambda ia: str(p)
        self.module.installer_ia('opencode', bavard=False)
        first = p.stat().st_mtime_ns
        self.module.installer_ia('opencode', bavard=False)
        self.assertEqual(p.stat().st_mtime_ns, first)
        self.assertEqual(Path(str(p) + '.avant-nc-claude').read_text(), '// previous plugin')
        self.assertIn('ctx.session.get', p.read_text())
        self.assertFalse(list(p.parent.glob('.nc-ile-*')))


@unittest.skipUnless(shutil.which('node'), 'Node requis pour les tests JavaScript')
class Javascript(unittest.TestCase):
    def test_snapshot_cache_is_bounded_and_cancelled_per_window(self):
        etat = (QML / 'Etat.qml').read_text()
        conserver = etat[etat.index('function conserverVueImage('):etat.index('function captureVue(')]
        vue = (QML / 'Vue.qml').read_text()
        annuler = vue[vue.index('function annulerAttente('):vue.index('function basculerAttente(')]
        code = '''const assert=require('node:assert/strict');let vueImages={};\n''' + conserver + r'''
for(let i=0;i<20;i++) conserverVueImage('0x'+i,{url:'image:'+i},100)
assert.equal(Object.keys(vueImages).length,12)
conserverVueImage('large',{url:'large'},8*1024*1024)
assert.deepEqual(Object.keys(vueImages),['large'])
let enAttente={a:{ws:1},b:{ws:2}}, Etat={vueImages:{a:{},b:{}}}
function adresse(t){return t}
''' + annuler + r'''
annulerAttente('a')
assert.deepEqual(Object.keys(enAttente),['b']);assert.deepEqual(Object.keys(Etat.vueImages),['b'])
'''
        subprocess.run(['node', '-e', code], check=True, timeout=10)

    def test_monitor_geometry(self):
        code = (QML / 'Geometrie.js').read_text() + r'''
const assert = require('node:assert/strict')
const m = {x:1800,y:100,w:800,h:600,mx:1600,my:0,mw:1600,mh:1000}
assert.deepEqual(adapter(m,1600,0,1600,1000),m)
assert.deepEqual(adapter(m,0,0,1600,1000),{x:200,y:100,w:800,h:600})
assert.deepEqual(adapter(m,-1200,0,1200,800),{x:-1050,y:75,w:600,h:450})
const portrait=adapter(m,0,0,800,1280)
assert(portrait.x>=0 && portrait.y>=0 && portrait.x+portrait.w<=800 && portrait.y+portrait.h<=1280)
assert.equal(adapter({x:1,y:2,w:3,h:4},0,0,1600,1000).x,1)
'''
        subprocess.run(['node', '-e', code], check=True, timeout=10)

    def test_opencode_projects_order_and_cleanup(self):
        tree = ast.parse((BIN / 'nc-claude').read_text())
        plugin = next(ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign)
                      and any(isinstance(t, ast.Name) and t.id == 'PLUGIN_OPENCODE' for t in n.targets))
        plugin = plugin.replace('import { spawn } from "node:child_process"', r'''
import { EventEmitter } from 'node:events'
const sent=[]
const spawn=(_python,args)=>{
 const p=new EventEmitter(); p.stdin=new EventEmitter(); p.unref=()=>{}
 p.stdin.end=json=>{sent.push({event:args.at(-1),...JSON.parse(json)});queueMicrotask(()=>p.emit('close',0))}
 return p
}
''').replace('@PY@', '"python"').replace('@NC@', '"nc-claude"').replace('export default {', 'const plugin = {')
        code = plugin + r'''
import assert from 'node:assert/strict'
let disposed=0
const makeCtx=directory=>{
 const hooks={}
 return {hooks,location:{directory},
 session:{get:async({sessionID})=>({location:{directory:sessionID==='B'?'/B':'/A'}}),hook:async(n,f)=>{hooks[n]=f;return {dispose(){disposed++}}}},
 tool:{hook:async(n,f)=>{hooks[n]=f;return {dispose(){disposed++}}}},
 event:{subscribe:({signal})=>({async *[Symbol.asyncIterator](){await new Promise(r=>signal.addEventListener('abort',r,{once:true}))}})}
 }
}
const a=makeCtx('/A'), b=makeCtx('/B')
const stopA=await plugin.setup(a), stopB=await plugin.setup(b)
for(const ctx of [a,b]){
 ctx.hooks.prompt({sessionID:'B'})
 ctx.hooks['execute.after']({sessionID:'B',tool:'bash',input:{command:'pwd'},status:'error'})
}
await new Promise(r=>setTimeout(r,30))
assert.equal(sent.length,2)
assert.deepEqual(sent.map(e=>e.event),['prompt','tool'])
assert(sent.every(e=>e.cwd==='/B' && e.session_id==='B' && e.terminal_cwd==='/B'))
assert.equal(sent[1].erreur,true)
await stopA();await stopB();assert.equal(disposed,4)
sent.length=0
const c=makeCtx('/A'), stopC=await plugin.setup(c)
c.hooks.prompt({sessionID:'B'})
await new Promise(r=>setTimeout(r,30))
assert.equal(sent[0].cwd,'/B');assert.equal(sent[0].terminal_cwd,'/A')
await stopC()
'''
        subprocess.run(['node', '--input-type=module', '-e', code], check=True, timeout=10)


class Export(unittest.TestCase):
    def test_preview_includes_checker_without_replacing_local_work(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); source = root / 'source'; source.mkdir()
            shutil.copy2(REPO / 'export.sh', root)
            (root / 'home').mkdir(); sentinel = root / 'home/local'; sentinel.write_text('preserve')
            for rel in ['.config/hypr/nc/clavier.lua', '.config/noctalia/config.toml',
                        '.local/share/noctalia/plugins/nc-launcher/panel.luau', '.config/qt6ct/qt6ct.conf',
                        '.local/bin/nc-qs-capture', '.local/bin/nc-assistant',
                        '.local/share/applications/nc-assistant.desktop']:
                dst = source / rel; dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(REPO / 'home' / rel, dst)
            secret = source / '.config/nc/assistant.conf'
            secret.parent.mkdir(parents=True, exist_ok=True)
            secret.write_text('SECRET_KEY=must-not-be-exported')
            (source / 'bin').mkdir()
            hypr = source / 'bin/hyprctl'; hypr.write_text('#!/bin/sh\necho "[]"\n'); hypr.chmod(0o755)
            r = subprocess.run(['bash', str(root / 'export.sh'), '--preview'],
                               env=dict(os.environ, HOME=str(source), PATH=str(source / 'bin') + ':' + os.environ['PATH']),
                               capture_output=True, text=True, timeout=15)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn('nc-qs-capture', r.stdout)
            self.assertIn('nc-assistant', r.stdout)
            self.assertNotIn('must-not-be-exported', r.stdout)
            self.assertEqual(sentinel.read_text(), 'preserve')
            self.assertFalse(list(root.glob('.nc-export.*')))

    def test_dirty_repository_is_preserved(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            shutil.copy2(REPO / 'export.sh', root)
            (root / 'home').mkdir(); sentinel = root / 'home/local'; sentinel.write_text('preserve')
            subprocess.run(['git', 'init', '-q', str(root)], check=True)
            r = subprocess.run(['bash', str(root / 'export.sh')], capture_output=True, text=True)
            self.assertNotEqual(r.returncode, 0)
            self.assertEqual(sentinel.read_text(), 'preserve')
            self.assertFalse(list(root.glob('.nc-export.*')))

    def test_failed_preparation_leaves_existing_home(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); source = root / 'source'; source.mkdir()
            shutil.copy2(REPO / 'export.sh', root)
            (root / 'home').mkdir(); sentinel = root / 'home/local'; sentinel.write_text('preserve')
            r = subprocess.run(['bash', str(root / 'export.sh'), '--preview'], env=dict(os.environ, HOME=str(source)),
                               capture_output=True, text=True)
            self.assertNotEqual(r.returncode, 0)
            self.assertEqual(sentinel.read_text(), 'preserve')
            self.assertFalse(list(root.glob('.nc-export.*')))


class Installation(unittest.TestCase):
    def test_island_selection_needs_modules_not_capture(self):
        script = (REPO / 'install.sh').read_text()
        selection = script[script.index('if have qs && ver_ge "$(qs_ver || true)" 0.3 &&'):]
        selection = selection[:selection.index('if [ "$ILE" = quickshell ]; then ILE_CENTRE=')]
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            checker = root / 'home/.local/bin/nc-qs-capture'; checker.parent.mkdir(parents=True)
            fonts = root / '.local/share/fonts'; fonts.mkdir(parents=True)
            (fonts / 'MaterialSymbolsRounded.ttf').write_text('fixture')
            common = '''have() { [ "$1" = qs ]; }
qs_ver() { echo 0.3.2; }
ver_ge() { return 0; }
warn() { :; }
t() { printf %s "$1"; }
ILE=noctalia
MODE=files
'''
            # Modules absents : l'île du plugin ; capture seule absente (Quickshell compilé sans elle, ancienne
            # installation Debian) : l'île Quickshell reste, avec un avertissement
            for corps, expected in [('exit 1', 'noctalia'), ('exit 0', 'quickshell'),
                                    ('[ "${1:-}" = --modules ] && exit 0; exit 1', 'quickshell')]:
                checker.write_text(corps + '\n')
                r = subprocess.run(['bash', '-c', common + selection + '\nprintf "%s" "$ILE"'],
                                   env=dict(os.environ, HOME=d, REPO=d), capture_output=True, text=True, timeout=10)
                self.assertEqual(r.returncode, 0, r.stderr)
                self.assertEqual(r.stdout, expected)


@unittest.skipUnless(shutil.which('qs'), 'Quickshell requis pour la vue hors écran')
class OuvertureVue(unittest.TestCase):
    def verifier_vue(self, scenario, bureaux='[{id:1},{id:2},{id:3}]', choisi=1, avec_scene=False, avant_ouverture=''):
        # Les vrais calculs et animations de Vue.qml, avec un écran et des bureaux simulés.
        # Aucune connexion Hyprland ni création de surface layer-shell sur la session réelle.
        source = (QML / 'Vue.qml').read_text()
        mouvement = source[source.index('        readonly property string anim:'):source.index('        Item {\n            id: scene')]
        intro = source[source.index('    property bool partant:'):source.index('    property real limiteCapture:')]
        if avec_scene:
            debut = source.index('        Item {\n            id: scene')
            mouvement += source[debut:source.index('            Repeater {', debut)]
            mouvement += '''Rectangle {id:bureauTest;x:zone.bx+zone.dec;y:zone.by;width:zone.fw;height:zone.fh}
}'''
        qml = '''import QtQuick
import QtQuick.Window
import Quickshell
ShellRoot {
 id:controle;property bool echec:false
 function verifier(ok,message) {if(!ok){echec=true;console.error(message);Qt.exit(2)}}
 function pixel(x,y){return {pixelDelta:{x:x,y:y},angleDelta:{x:0,y:0}}}
 Window {id:v;visible:true;width:1600;height:1000
  property var bureaux:BUREAUX;property int choisi:CHOISI;property var traine:null
  INTRO
  Component.onCompleted: {AVANT;fin=0}
  Item {id:zone;x:28;y:120;width:1400;height:800
   readonly property real mw:v.width;readonly property real mh:v.height
   MOUVEMENT
  }
 }
 SCENARIO
 Timer {interval:1800;running:true;onTriggered:{console.error("Délai dépassé");Qt.exit(3)}}
}'''.replace('BUREAUX', bureaux).replace('CHOISI', str(choisi)).replace('INTRO', intro).replace('MOUVEMENT', mouvement).replace('SCENARIO', scenario).replace('AVANT', avant_ouverture)
        qml = qml.replace('Qt.quit()', 'Qt.exit(controle.echec ? 2 : 0)')
        with tempfile.TemporaryDirectory(prefix='nc-vue-test-') as d:
            root = Path(d)
            (root / 'runtime').mkdir(mode=0o700)
            (root / 'shell.qml').write_text(qml)
            (root / 'Reglages.qml').write_text('pragma Singleton\nimport QtQuick\nQtObject {function val(k,d){return d}}')
            (root / 'Etat.qml').write_text('pragma Singleton\nimport QtQuick\nQtObject {property bool vuePause:false}')
            (root / 'qmldir').write_text('singleton Reglages 1.0 Reglages.qml\nsingleton Etat 1.0 Etat.qml\n')
            env = dict(os.environ, HOME=d, QT_QPA_PLATFORM='offscreen', QT_QUICK_BACKEND='software',
                       XDG_RUNTIME_DIR=str(root / 'runtime'), XDG_CACHE_HOME=str(root / 'cache'))
            env.pop('WAYLAND_DISPLAY', None)
            r = subprocess.run(['qs', '--no-color', '-p', str(root / 'shell.qml')], env=env,
                               capture_output=True, text=True, timeout=5)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_initial_workspace_refresh_does_not_animate_but_later_navigation_does(self):
        self.verifier_vue('''
 Timer {interval:50;running:true;onTriggered:{v.choisi=2;zone.width=1420}}
 Timer {interval:90;running:true;onTriggered:{
  verifier(zone.pos===zone.courant,"La mise en place du bureau ne doit pas glisser")
  verifier(zone.recul===0,"Pas de recul parasite à l'ouverture")
  verifier(Math.abs(zone.dec-zone.decalage)<0.001,"Pas de décalage animé pendant la mise en place")
  verifier(!zone.pret,"L'introduction n'est pas terminée")
 }}
 Timer {interval:300;running:true;onTriggered:{verifier(zone.pret,"Vue prête");v.choisi=3}}
 Timer {interval:350;running:true;onTriggered:{
  verifier(zone.pos>1&&zone.pos<2&&zone.bouge,"La navigation doit conserver son animation")
 }}
 Timer {interval:850;running:true;onTriggered:{verifier(zone.pos===2,"Bureau final incorrect");Qt.quit()}}
''')

    def test_first_workspace_received_after_intro_is_placed_without_recoil(self):
        self.verifier_vue('''
 Timer {interval:300;running:true;onTriggered:{verifier(!zone.pret,"Attendre les bureaux");v.bureaux=[{id:1},{id:2},{id:3}]}}
 Timer {interval:350;running:true;onTriggered:{
  verifier(zone.pret&&zone.pos===1,"Première position reçue tardivement incorrecte")
  verifier(zone.recul===0,"Le premier placement ne doit pas provoquer un recul")
  Qt.quit()
 }}
''', bureaux='[]', choisi=2)

    def test_vertical_opening_motion_and_horizontal_jitter_do_not_move_desktop(self):
        self.verifier_vue('''
 Timer {interval:80;running:true;onTriggered:{zone.defilerHorizontal(pixel(-30,0));verifier(!zone.glisse,"Ignorer la fin du geste d'ouverture")}}
 Timer {interval:300;running:true;onTriggered:{
  zone.defilerHorizontal(pixel(-2,40))
  verifier(!zone.glisse&&zone.pos===0,"Un geste surtout vertical ne doit pas bouger le bureau")
  for(var i=0;i<5;i++)zone.defilerHorizontal(pixel(-1,0))
  verifier(!zone.glisse&&zone.pos===0,"La petite dérive horizontale ne doit pas bouger le bureau")
 }}
 Timer {interval:510;running:true;onTriggered:{verifier(zone.amorceHorizontale===0,"Purger la dérive inactive");zone.defilerHorizontal(pixel(-25,1))
  verifier(zone.pos===0&&zone.cible>0,"PERF-03 : la position suit la cible image par image, sans saut")}}
 Timer {interval:560;running:true;onTriggered:{verifier(zone.glisse&&zone.pos>0&&zone.pos<=zone.cible,"Un vrai geste horizontal doit fonctionner")}}
 Timer {interval:1150;running:true;onTriggered:{verifier(!zone.glisse&&zone.pos===zone.courant,"Fin du geste incorrecte");Qt.quit()}}
''')

    def test_mouse_horizontal_wheel_still_works_and_pause_rejects_input(self):
        self.verifier_vue('''
 Timer {interval:300;running:true;onTriggered:{
  v.partant=true;zone.defilerHorizontal(pixel(-40,0));verifier(!zone.glisse,"La fermeture doit ignorer les gestes")
  v.partant=false;Etat.vuePause=true;zone.defilerHorizontal(pixel(-40,0));verifier(!zone.glisse,"Une capture doit ignorer les gestes")
  Etat.vuePause=false
  zone.defilerHorizontal({pixelDelta:{x:0,y:0},angleDelta:{x:-120,y:0}})
 }}
 Timer {interval:350;running:true;onTriggered:{verifier(zone.glisse&&zone.pos>0,"Molette horizontale ignorée");Qt.quit()}}
''')

    def test_opening_and_closing_use_same_geometry_in_reverse(self):
        for choisi in (1, 2, 3):
            with self.subTest(bureau=choisi):
                self.verifier_vue('''
 function rectangleBureau(){
  var a=bureauTest.mapToItem(v.contentItem,0,0),b=bureauTest.mapToItem(v.contentItem,bureauTest.width,bureauTest.height)
  return {x:a.x,y:a.y,w:b.x-a.x,h:b.y-a.y}
 }
 function pleinEcran(){
  var r=rectangleBureau()
  verifier(Math.abs(r.x)<0.001&&Math.abs(r.y)<0.001,"Le bureau grandeur réelle doit être à son emplacement")
  verifier(Math.abs(r.w-v.width)<0.001&&Math.abs(r.h-v.height)<0.001,"Dimensions grandeur réelle incorrectes")
 }
 Timer {interval:120;running:true;onTriggered:{
  var r=rectangleBureau()
  verifier(v.fin>0&&v.fin<1&&r.w>zone.fw&&r.w<v.width,"L'ouverture doit réduire le bureau grandeur réelle")
 }}
 Timer {interval:300;running:true;onTriggered:{
  var r=rectangleBureau()
  verifier(v.fin===0&&Math.abs(r.w-zone.fw)<0.001,"La vue doit atteindre la miniature")
  verifier(Math.abs(r.x-zone.x-zone.bx-zone.dec)<0.001&&Math.abs(r.y-zone.y-zone.by)<0.001,"Emplacement de la miniature incorrect")
  v.partant=true;v.fin=1
  verifier(Math.abs(rectangleBureau().w-r.w)<0.001,"Pas de saut au début de la fermeture")
 }}
 Timer {interval:420;running:true;onTriggered:{
  var r=rectangleBureau()
  verifier(v.fin>0&&v.fin<1&&r.w>zone.fw&&r.w<v.width,"La fermeture doit agrandir la même miniature")
 }}
 Timer {interval:650;running:true;onTriggered:{pleinEcran();Qt.quit()}}
''', choisi=choisi, avec_scene=True, avant_ouverture='pleinEcran()')

    def test_closing_during_opening_reverses_without_position_jump(self):
        self.verifier_vue('''
 Timer {interval:80;running:true;onTriggered:{
  var avant=bureauTest.mapToItem(v.contentItem,0,0),taille=bureauTest.mapToItem(v.contentItem,bureauTest.width,bureauTest.height)
  var phase=v.fin
  v.partant=true;v.fin=1
  var apres=bureauTest.mapToItem(v.contentItem,0,0),tailleApres=bureauTest.mapToItem(v.contentItem,bureauTest.width,bureauTest.height)
  verifier(Math.abs(v.fin-phase)<0.001,"Le zoom ne doit pas repartir de zéro")
  verifier(Math.abs(apres.x-avant.x)<0.001&&Math.abs(apres.y-avant.y)<0.001,"Pas de saut de position à l'inversion")
  verifier(Math.abs(tailleApres.x-taille.x)<0.001&&Math.abs(tailleApres.y-taille.y)<0.001,"Pas de saut de taille à l'inversion")
 }}
 Timer {interval:430;running:true;onTriggered:{verifier(v.fin===1,"Retour grandeur réelle incomplet");Qt.quit()}}
''', avec_scene=True)


@unittest.skipUnless(shutil.which('qs'), 'Quickshell requis pour la capture hors écran')
class ImagesQml(unittest.TestCase):
    def test_grab_survives_source_destruction(self):
        qml = '''import QtQuick
import QtQuick.Window
import Quickshell
ShellRoot {
 id:root; property var retenue:null; property var objet:null
 Component { id:source; Rectangle { width:64;height:64;color:"red" } }
 Window { id:w;visible:true;width:64;height:64
  Image { id:image;anchors.fill:parent;source:root.retenue ? root.retenue.url : "" }
  Timer {interval:100;running:true;onTriggered:{root.objet=source.createObject(w.contentItem);copier.start()}}
  Timer {id:copier;interval:100;onTriggered:{
   if(!root.objet.grabToImage(r=>{root.retenue=r;root.objet.destroy();verifier.start()},Qt.size(64,64))) Qt.exit(2)
  }}
  Timer {id:verifier;interval:100;onTriggered:{
   if(image.status!==Image.Ready){Qt.exit(3);return}
   console.log("GRAB_SURVIVES_DESTRUCTION");Qt.quit()
  }}
 }
 Timer {interval:2500;running:true;onTriggered:Qt.exit(4)}
}'''
        with tempfile.TemporaryDirectory(prefix='nc-grab-test-') as d:
            root = Path(d); (root / 'runtime').mkdir(mode=0o700); (root / 'cache').mkdir()
            (root / 'shell.qml').write_text(qml)
            env = dict(os.environ, QT_QPA_PLATFORM='offscreen', QT_QUICK_BACKEND='software',
                       XDG_RUNTIME_DIR=str(root / 'runtime'), XDG_CACHE_HOME=str(root / 'cache'))
            env.pop('WAYLAND_DISPLAY', None)
            r = subprocess.run(['qs', '--no-color', '-p', str(root / 'shell.qml')], env=env,
                               capture_output=True, text=True, timeout=6)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn('GRAB_SURVIVES_DESTRUCTION', r.stdout + r.stderr)


if __name__ == '__main__':
    unittest.main()


class IsolationDesTests(unittest.TestCase):
    """Aucun test n'écrit dans les vrais dossiers de la session : XDG_* pointent vers un dossier temporaire."""
    def test_dossiers_xdg_temporaires(self):
        for cle in ("XDG_CACHE_HOME", "XDG_CONFIG_HOME", "XDG_STATE_HOME", "XDG_DATA_HOME", "XDG_RUNTIME_DIR"):
            self.assertTrue(os.environ.get(cle), cle)
            self.assertFalse(os.environ[cle].startswith(str(Path.home())), cle + " : " + os.environ[cle])
            self.assertNotEqual(os.environ[cle], os.environ.get("NC_TEST_VRAI_RUNTIME"), cle)


class AnimationsSobres(unittest.TestCase):
    """Revue E1 : en Économie (ou « Effets visuels : aucun »), aucune animation sans fin de l'île ne tourne ; seuls des
    indicateurs d'attente bornés (une lecture, une réponse en cours) gardent la leur."""
    BORNEES = {"Calendrier.qml", "Ligne.qml", "Assistant.qml"}     # chargement de l'agenda, d'une ligne, attente d'une réponse

    def test_animations_infinies_coupees_en_sobre(self):
        import re
        dossier = REPO / "home/.config/quickshell/nc-ile"
        for f in sorted(dossier.glob("*.qml")):
            if f.name in self.BORNEES:
                continue
            texte = f.read_text()
            for m in re.finditer(r"loops: Animation\.Infinite", texte):
                ligne = texte[texte.rfind("\n", 0, m.start()) + 1:texte.find("\n", m.end())]
                condition = re.search(r"running: ([^;}]+)", ligne)
                self.assertTrue(condition, f"{f.name} : {ligne.strip()}")
                expr = condition[1].strip()
                propre = "sobre" in expr or re.search(r"(bouge|clignote|anime|mouvement)\b", expr)
                self.assertTrue(propre, f"{f.name} : une animation sans fin ignore Reglages.sobre : {ligne.strip()}")


class AnimationsFilDeRendu(unittest.TestCase):
    """PERF-01 : les rotations sans fin des pages de l'île sont des RotationAnimator (fil de rendu), plus des
    RotationAnimation (fil principal, une propriété QML réécrite à chaque image). L'étincelle de la pilule, toujours
    affichée, tourne par Pas.qml à 30 images/s (ILE-GPU, tests/test_ile_cadence.py)."""

    def test_rotations_sans_fin_en_animator(self):
        import re
        for nom in ("AssistantOrbe.qml", "Calendrier.qml", "Ligne.qml"):
            texte = (QML / nom).read_text()
            self.assertNotRegex(texte, r"RotationAnimation\s+on\s+rotation", nom)
            infinies = [m.start() for m in re.finditer(r"loops: Animation\.Infinite", texte)]
            self.assertTrue(infinies, nom)
            for debut in infinies:
                bloc = texte[max(0, texte.rfind("{", 0, debut) - 40):debut]   # le type de l'animation et sa ligne
                self.assertNotIn("RotationAnimation ", bloc, f"{nom} : {bloc.strip()}")
        etincelle = (QML / "Etincelle.qml").read_text()
        self.assertRegex(etincelle, r"Pas \{\s*running: e\.bouge && e\.tournante\s*onTriggered: e\.rotation = \(e\.rotation \+ 360 \* interval / e\.dureeTour\)")
        self.assertIn('Reglages.val("ILE_ANIM_BATTERIE", "douces")', etincelle)
        self.assertIn("UPower.onBattery", etincelle)

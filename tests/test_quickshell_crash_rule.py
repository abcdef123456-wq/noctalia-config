"""La règle de rapport de crash ne doit jamais fermer un cockpit Quickshell."""
from pathlib import Path
import shutil
import subprocess
import unittest

REPO=Path(__file__).resolve().parents[1]


@unittest.skipUnless(shutil.which('lua'),'Lua requis')
class RapportsQuickshell(unittest.TestCase):
    def test_only_a_real_crash_reporter_is_closed_and_notified(self):
        source=(REPO/'home/.config/hypr/nc/automatismes.lua').read_text()
        start=source.index('local rapports_vus = {}')
        end=source.index('hl.on("window.class", rapport_quickshell)',start)+len('hl.on("window.class", rapport_quickshell)')
        harness=r'''
local events, commands, environments = {}, {}, {}
hl = {
    on=function(event, callback) events[event]=callback end,
    exec_cmd=function(command) commands[#commands+1]=command end,
}
nc = { guillemets=function(s) return string.format('%q',s) end, t=function(fr,en) return fr end }
local function lire(path) return environments[path] end
'''+source[start:end]+r'''
local function open(w)
    events['window.open'](w)
    events['window.class'](w)
end
environments['/proc/100/environ']='PATH=/usr/bin\0TOKEN=private-do-not-print\0'
open({class='org.quickshell', title='JARVIS', pid=100, address='0x100'})
assert(#commands==0, 'Le dashboard JARVIS est pris pour un crash et fermé')
open({class='org.quickshell', title='Quickshell has crashed', pid=100, address='0x101'})
assert(#commands==0, 'Le titre seul ne prouve pas un rapport de crash')
open({class='org.quickshell', title='', pid=100, address='0x102'})
open({class='org.quickshell', title='JARVIS', address='0x103'})
open({class='org.quickshell', title='JARVIS', pid=999, address='0x104'})
assert(#commands==0, 'Une fenêtre sans métadonnées suffisantes doit rester ouverte')
environments['/proc/101/environ']='__QUICKSHELL_CRASH_DUMP_PID=100\0__QUICKSHELL_CRASH_DUMP_FD=7\0TOKEN=private-do-not-print\0'
open({class='org.quickshell', title='', pid=101, address='0x105'})
assert(#commands==1, 'Le vrai rapport doit être traité une seule fois')
assert(commands[1]:find('address:0x105',1,true), 'Mauvaise fenêtre fermée')
assert(commands[1]:find('notify-send',1,true), 'Notification du vrai crash perdue')
assert(not commands[1]:find('private-do-not-print',1,true), 'Environnement exposé')
open({class='kitty', pid=101, address='0x106'})
assert(#commands==1, 'La classe doit aussi correspondre')
print('CRASH_RULE_OK')
'''
        result=subprocess.run(['lua','-'],input=harness,text=True,capture_output=True,timeout=5)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertIn('CRASH_RULE_OK',result.stdout)

"""Fermer un cockpit ne doit pas arrêter le shell qui porte aussi l'île."""
from pathlib import Path
import shutil
import subprocess
import unittest

REPO=Path(__file__).resolve().parents[1]


@unittest.skipUnless(shutil.which('lua'),'Lua requis')
class FermetureQuickshell(unittest.TestCase):
    def test_shortcut_closes_shell_window_without_scheduling_process_kill(self):
        source=(REPO/'home/.config/hypr/nc/raccourcis.lua').read_text()
        marker='touche(SUPER .. " + SHIFT + code:24", function()'
        start=source.index(marker)+len(marker)
        end=source.index('\nend, trad("Fenêtres|Fermer',start)
        harness=r'''
local active, windows, commands, closes, comm = nil, {}, {}, 0, nil
hl = {
 get_active_window=function() return active end,
 get_windows=function() return windows end,
 exec_cmd=function(command) commands[#commands+1]=command end,
 dispatch=function(_) closes=closes+1 end,
 dsp={window={close=function() return {} end}},
}
io.open=function(path, mode)
 if not comm then return nil end
 return {read=function() return comm end,close=function() end}
end
local function fermer()
'''+source[start:end]+r'''
end
local function essayer(classe, programme, nombre)
 active={class=classe,title='JARVIS',pid=123,address='0x123'}
 windows={active}
 if nombre==2 then windows[2]={pid=123,address='0x124'} end
 commands={};closes=0;comm=programme
 fermer()
end
essayer('org.quickshell',nil,1)
assert(closes==1,'La fenêtre JARVIS doit être fermée')
assert(#commands==0,'Le raccourci tue aussi l’île cinq secondes après JARVIS')
essayer('custom.shell','quickshell',1)
assert(closes==1 and #commands==0,'Un identifiant personnalisé ne doit pas faire tuer Quickshell')
essayer('custom.shell','qs',1)
assert(closes==1 and #commands==0,'Le nom court qs doit aussi être reconnu')
essayer('noctalia','noctalia',1)
assert(closes==1 and #commands==0,'Fermer une fenêtre de Noctalia ne doit pas arrêter la barre')
essayer('discord','Discord',1)
assert(closes==1 and #commands==1,'Conserver la fermeture des applications ordinaires')
assert(commands[1]:find('kill -TERM 123',1,true),'Arrêt de la dernière application perdu')
essayer('discord','Discord',2)
assert(closes==1 and #commands==0,'Ne pas arrêter une application avec une autre fenêtre')
essayer('kitty','kitty',1)
assert(closes==0 and #commands==1,'La confirmation kitty doit être conservée')
assert(commands[1]:find('nc-fermer 123 0x123',1,true),'Confirmation kitty perdue')
active=nil;commands={};closes=0;fermer()
assert(closes==0 and #commands==0,'Aucune action sans fenêtre active')
print('QUICKSHELL_CLOSE_OK')
'''
        result=subprocess.run(['lua','-'],input=harness,text=True,capture_output=True,timeout=5)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertIn('QUICKSHELL_CLOSE_OK',result.stdout)

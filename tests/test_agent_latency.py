"""Repérage d'un terminal : un seul instantané Hyprland, sans fenêtre personnelle."""
import io
from pathlib import Path
import types
import unittest
from unittest.mock import patch

SOURCE=Path(__file__).resolve().parents[1]/'home/.local/bin/nc-claude'


class TerminalAgents(unittest.TestCase):
    def setUp(self):
        self.m=types.ModuleType('agent_latency');self.m.__file__=str(SOURCE)
        exec(compile(SOURCE.read_text(),str(SOURCE),'exec'),self.m.__dict__)

    def test_single_snapshot_identifies_terminal_shell_and_class(self):
        m=self.m
        # Parent du hook 200 -> shell 100 -> terminal 50 (le nom contient des parenthèses).
        def stat(path, *args, **kwargs):
            pid=int(str(path).split('/')[2])
            return io.StringIO(f'{pid} (a (shell)) S '+str({200:100,100:50}[pid]))
        for agent in ('claude','codex','opencode','antigravity'):
            session={'agent':agent}
            with patch.object(m,'fenetres',return_value=[{'pid':50,'class':'kitty'}]) as query, \
                 patch.object(m.os,'getppid',return_value=200), patch('builtins.open',side_effect=stat), \
                 patch.object(m,'socket_kitty',return_value='/private/socket'):
                m.reperer_terminal(session)
                self.assertEqual((session['terminal'],session['shell'],session['classe']),(50,100,'kitty'))
                self.assertTrue(session['ecrire'])
                m.reperer_terminal(session)
                query.assert_called_once_with()

    def test_empty_snapshot_does_not_trigger_a_second_query(self):
        m=self.m
        with patch.object(m,'fenetres',return_value=[]) as query, \
             patch.object(m.os,'getppid',return_value=200), patch('builtins.open',side_effect=OSError):
            session={};m.reperer_terminal(session)
            self.assertEqual((session['terminal'],session['shell'],session['classe']),(0,0,''))
            self.assertFalse(session['ecrire'])
            query.assert_called_once_with()


if __name__=='__main__':unittest.main()

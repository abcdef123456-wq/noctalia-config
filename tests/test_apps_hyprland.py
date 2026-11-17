"""nc-apps launch : le lancement passe par hyprctl dispatch hl.dsp.exec_cmd (jeton de bureau de Hyprland), avec repli sur l'ancien
lancement sans Hyprland ou si hyprctl échoue. La chaîne Lua est relue par un vrai Lua."""
from importlib.machinery import SourceFileLoader
from importlib.util import module_from_spec, spec_from_loader
from pathlib import Path
import os
import shlex
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock

SCRIPT = Path(__file__).resolve().parents[1] / "home/.local/bin/nc-apps"
LUA = shutil.which("lua5.4") or shutil.which("lua")
SPECIAL = 'a"b\\c\nd$e`f\'g é€ \x01 ;&|<>*?~#%'


def charger():
    chargeur = SourceFileLoader("nc_apps", str(SCRIPT))
    m = module_from_spec(spec_from_loader("nc_apps", chargeur))
    chargeur.exec_module(m)
    return m


def lire_lua(dispatch):
    """Ce que Lua lit dans exec_cmd("…") : les octets de la commande."""
    prefixe = "hl.dsp.exec_cmd("
    assert dispatch.startswith(prefixe) and dispatch.endswith(")")
    code = 'io.write(load("return " .. os.getenv("NC_LUA"))())'
    env = {"NC_LUA": dispatch[len(prefixe):-1], "PATH": os.environ.get("PATH", "")}
    return subprocess.run([LUA, "-e", code], env=env, capture_output=True, check=True).stdout


class LancerParHyprland(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.cwd = os.getcwd()
        self.addCleanup(os.chdir, self.cwd)
        self.bin = Path(self.tmp, "bin")
        self.bin.mkdir()
        self.log = Path(self.tmp, "log")
        self.travail = Path(self.tmp, "travail dossier")
        self.travail.mkdir()
        self.launch = Path(self.tmp, "nc-launch")
        for p in (self.launch, self.bin / "uwsm-app"):
            p.write_text("#!/bin/sh\nexit 0\n")
            p.chmod(0o755)
        self.env = {"PATH": str(self.bin), "HYPRLAND_INSTANCE_SIGNATURE": "x", "HOME": self.tmp,
                    "FAKE_LOG": str(self.log), "FAKE_OUT": "ok", "FAKE_RC": "0"}

    def hyprctl(self):
        f = self.bin / "hyprctl"
        f.write_text('#!/bin/sh\nprintf \'%s\\0\' "$@" > "$FAKE_LOG"\nprintf \'%s\\n\' "$FAKE_OUT"\nexit "$FAKE_RC"\n')
        f.chmod(0o755)

    def lancer(self, exec_="prog --x", terminal=False, chemin=True, env=None):
        m = charger()
        e = {"Exec": exec_, "Name": "Ex"}
        if chemin:
            e["Path"] = str(self.travail)
        with mock.patch.dict(os.environ, env or self.env, clear=True), \
             mock.patch.object(m, "entries", return_value={"a": "p"}), mock.patch.object(m, "parse", return_value=e), \
             mock.patch.object(m, "LAUNCH", str(self.launch)), mock.patch.object(m.os, "execvp") as ex:
            m.cmd_launch("a")
        return ex

    def recu(self):
        return self.log.read_bytes().split(b"\0")[:-1]

    def test_commande_par_hyprctl(self):
        self.hyprctl()
        ex = self.lancer()
        ex.assert_not_called()
        a = self.recu()
        self.assertEqual(a[:2], [b"dispatch", a[1]])
        cmd = lire_lua(a[1].decode()).decode()
        self.assertEqual(cmd, "cd " + shlex.quote(str(self.travail)) + " && " + shlex.join(
            ["uwsm-app", "--", str(self.launch), "prog", "--x"]))

    def test_sans_hyprland_ancien_chemin(self):
        self.hyprctl()
        env = {k: v for k, v in self.env.items() if k != "HYPRLAND_INSTANCE_SIGNATURE"}
        ex = self.lancer(env=env)
        self.assertFalse(self.log.exists())
        ex.assert_called_once_with("uwsm-app", ["uwsm-app", "--", str(self.launch), "prog", "--x"])

    def test_sans_hyprctl_ancien_chemin(self):
        ex = self.lancer()
        ex.assert_called_once()

    def test_hyprctl_code_en_echec_repli(self):
        self.hyprctl()
        self.env["FAKE_RC"] = "1"
        ex = self.lancer()
        self.assertTrue(self.log.exists())
        ex.assert_called_once()

    def test_hyprctl_trop_lent_pas_de_second_lancement(self):
        self.hyprctl()
        m = charger()
        with mock.patch.dict(os.environ, self.env, clear=True), \
             mock.patch.object(m.subprocess, "run", side_effect=m.subprocess.TimeoutExpired("hyprctl", 5)):
            self.assertTrue(m.lancer_par_hyprland(["prog"]))

    def test_hyprctl_reponse_autre_que_ok_repli(self):
        self.hyprctl()
        self.env["FAKE_OUT"] = "error: dispatcher inconnu"
        ex = self.lancer()
        ex.assert_called_once()

    def test_dossier_de_travail_defaut_home(self):
        self.hyprctl()
        self.lancer(chemin=False)
        cmd = lire_lua(self.recu()[1].decode()).decode()
        self.assertTrue(cmd.startswith("cd " + shlex.quote(os.path.realpath(self.tmp)) + " && "), cmd)

    @unittest.skipUnless(LUA, "Lua absent")
    def test_caracteres_speciaux_relus_par_lua(self):
        self.hyprctl()
        self.lancer(exec_="prog")
        m = charger()
        for arg in (SPECIAL, "--x=" + SPECIAL):
            cmd = "cd '/a b' && " + shlex.join(["prog", arg])
            self.assertEqual(lire_lua("hl.dsp.exec_cmd(" + m.chaine_lua(cmd) + ")"), cmd.encode())
        # aucun octet dangereux en clair dans la chaîne
        brut = m.chaine_lua(SPECIAL)
        self.assertNotIn('"', brut[1:-1])
        self.assertNotIn("\n", brut)
        self.assertNotIn("\\\\", brut.replace("\\034", ""))   # la barre inverse n'apparaît que devant 3 chiffres

    @unittest.skipUnless(LUA, "Lua absent")
    def test_caracteres_speciaux_de_bout_en_bout(self):
        self.hyprctl()
        self.lancer(exec_="prog 'a\"b$(x)'")
        cmd = lire_lua(self.recu()[1].decode()).decode()
        self.assertIn(shlex.join(["prog", 'a"b$(x)']), cmd)


if __name__ == "__main__":
    unittest.main()

"""Un pid lu dans un fichier est-il encore notre processus ? kill -0 réussit sur un zombie (fini, non recueilli) et sur
un autre processus qui a repris le pid (après un redémarrage de session). Un helper par langage :
nc-pid (shell, sourcé) et pid_notre (Python, même texte dans nc-dictee, nc-panne et nc-claude)."""
import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import unittest

BIN = Path(__file__).resolve().parent.parent / "home/.local/bin"
QML = Path(__file__).resolve().parent.parent / "home/.config/quickshell/nc-ile/Etat.qml"
SCRIPTS = ("nc-dictee", "nc-panne", "nc-claude")


def charger(nom):
    l = importlib.machinery.SourceFileLoader("t_" + nom.replace("-", "_"), str(BIN / nom))
    m = importlib.util.module_from_spec(importlib.util.spec_from_loader(l.name, l))
    l.exec_module(m)
    return m


def zombie(test):
    """Un vrai zombie : un processus terminé que personne n'a recueilli."""
    p = subprocess.Popen(["true"])
    test.addCleanup(p.wait)
    fin = time.monotonic() + 5
    while time.monotonic() < fin and Path(f"/proc/{p.pid}/stat").read_text().rpartition(")")[2].split()[0] != "Z":
        time.sleep(0.01)
    test.assertTrue(os.path.exists(f"/proc/{p.pid}"), "zombie encore là")
    return p.pid


def dormeur(test):
    p = subprocess.Popen(["sleep", "30"])
    test.addCleanup(lambda: (p.kill(), p.wait()))
    return p.pid


class TestPython(unittest.TestCase):
    def setUp(self):
        self.mods = [charger(n) for n in SCRIPTS]

    def test_meme_texte_partout(self):
        blocs = []
        for n in SCRIPTS:
            s = (BIN / n).read_text()
            m = re.search(r"# ── pid_notre :.*?# ── fin de pid_notre ─+\n", s, re.S)
            self.assertTrue(m, n)
            blocs.append(m[0])
        self.assertEqual(blocs[0], blocs[1])
        self.assertEqual(blocs[0], blocs[2])

    def test_notre_processus_vivant(self):
        pid = dormeur(self)
        for m in self.mods:
            debut = m.debut_pid(pid)
            self.assertTrue(debut and debut.isdigit())
            self.assertTrue(m.pid_notre(pid))
            self.assertTrue(m.pid_notre(pid, debut))
            self.assertTrue(m.pid_notre(pid, None, "sleep"))
            self.assertTrue(m.pid_notre(os.getpid(), m.debut_pid(os.getpid())))

    def test_zombie(self):
        pid = zombie(self)
        for m in self.mods:
            self.assertFalse(m.pid_notre(pid))
            self.assertFalse(m.pid_notre(pid, m.debut_pid(pid)))
            self.assertFalse(m.pid_notre(pid, None, "true"))

    def test_pid_reutilise(self):
        pid = dormeur(self)
        for m in self.mods:
            self.assertFalse(m.pid_notre(pid, "1"), "autre heure de démarrage")
            self.assertFalse(m.pid_notre(pid, None, "wf-recorder"), "ancien fichier : autre nom")
            self.assertFalse(m.pid_notre(pid, None, ("parec", "pw-record")))
            self.assertTrue(m.pid_notre(pid, None, ("parec", "sleep")))

    def test_pids_absurdes(self):
        for m in self.mods:
            for v in (None, True, 0, 1, -1, "12", 2 ** 70):
                self.assertFalse(m.pid_notre(v), v)
            self.assertFalse(m.pid_notre(4194303 + 5))

    def test_dictee_ancien_fichier_et_nouveau(self):
        m = charger("nc-dictee")
        pid = dormeur(self)
        self.assertFalse(m.enregistre(None))
        self.assertFalse(m.enregistre({"pid": pid}), "ancien format : sleep n'est pas un enregistreur")
        self.assertFalse(m.enregistre({"pid": pid, "demarre": "1"}))
        self.assertTrue(m.enregistre({"pid": pid, "demarre": m.debut_pid(pid)}))
        self.assertFalse(m.enregistre({"pid": zombie(self), "demarre": None}))

    def test_claude_notification(self):
        m = charger("nc-claude")
        pid = dormeur(self)
        d = lambda v: {"notifs": {"s": v}}
        self.assertFalse(m.notif_ouverte(d(str(pid)), "s"), "ancien format : sleep n'est pas nc-claude")
        self.assertFalse(m.notif_ouverte(d("%d:1" % pid), "s"))
        self.assertTrue(m.notif_ouverte(d("%d:%s" % (pid, m.debut_pid(pid))), "s"))
        self.assertTrue(m.notif_ouverte(d("%d:%s" % (os.getpid(), m.debut_pid(os.getpid()))), "s"))
        self.assertFalse(m.notif_ouverte(d(str(zombie(self))), "s"))
        for v in ("-1", "0", "abc", "", None):
            self.assertFalse(m.notif_ouverte(d(v), "s"), v)
        self.assertFalse(m.notif_ouverte({}, "s"))

    def test_panne_lot(self):
        m = charger("nc-panne")
        pid = dormeur(self)
        self.assertFalse(m.vivant(pid), "ancien lot : sleep n'est pas nc-panne")
        self.assertFalse(m.vivant(pid, "1"))
        self.assertTrue(m.vivant(pid, m.debut_pid(pid)))
        self.assertFalse(m.vivant(zombie(self)))
        self.assertFalse(m.vivant(None))


def bash(code, *args):
    return subprocess.run(["bash", "-c", '. "$1"; shift; ' + code, "x", str(BIN / "nc-pid"), *map(str, args)],
                          capture_output=True, text=True, timeout=20)


class TestShell(unittest.TestCase):
    def notre(self, *a):
        return bash('nc_pid_notre "$@"', *a).returncode == 0

    def test_cas_normal_et_formats(self):
        pid = dormeur(self)
        debut = bash('nc_pid_debut "$1"', pid).stdout.strip()
        self.assertTrue(debut.isdigit())
        self.assertTrue(self.notre(pid))
        self.assertTrue(self.notre(pid, debut))
        self.assertTrue(self.notre(pid, "", "sleep"), "ancien fichier : le nom fait foi")

    def test_zombie(self):
        pid = zombie(self)
        self.assertFalse(self.notre(pid))
        self.assertFalse(self.notre(pid, "", "true"))

    def test_pid_reutilise(self):
        pid = dormeur(self)
        self.assertFalse(self.notre(pid, "1"))
        self.assertFalse(self.notre(pid, "", "wf-recorder"))
        self.assertFalse(self.notre(pid, "", "nc-profile-sync"))

    def test_pids_absurdes(self):
        for v in ("", "abc", "0", "1", "-1", "12 34", "99999999"):
            self.assertFalse(self.notre(v), v)

    def test_guet_rtx(self):
        """La fonction de nc-profile-sync, avec le vrai helper."""
        s = (BIN / "nc-profile-sync").read_text()
        i = s.index("guet_en_cours() {")
        fonction = s[i:s.index("\n}\n", i) + 3]
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "guet"

            def guet(contenu):
                f.write_text(contenu)
                return bash(fonction + '\nRTX_GUET="$1"; guet_en_cours', f).returncode == 0
            pid = dormeur(self)
            debut = bash('nc_pid_debut "$1"', pid).stdout.strip()
            self.assertTrue(guet(f"{pid} {debut}\n"))
            self.assertFalse(guet(f"{pid} 1\n"), "pid réutilisé")
            self.assertFalse(guet(f"{pid}\n"), "ancien format : sleep n'est pas nc-profile-sync")
            self.assertFalse(guet(f"{zombie(self)} 5\n"))
            self.assertFalse(guet(""))
            self.assertFalse(guet("n'importe quoi\n"))
        self.assertIn("echo \"$! $(nc_pid_debut", s)

    def test_ile_etat_qml(self):
        """La commande de l'île qui lit l'enregistrement : le début (ligne 2) seulement si c'est bien wf-recorder."""
        m = re.search(r'id: lireVideo\s+command: \["sh", "-c", ("(?:[^"\\]|\\.)*")', QML.read_text())
        script = json.loads(m[1])
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            def lire(contenu):
                (Path(d) / "nc-video").write_text(contenu)
                r = subprocess.run(["sh", "-c", script, "sh", str(BIN / "nc-pid")], capture_output=True, text=True,
                                   env=dict(os.environ, XDG_RUNTIME_DIR=d), timeout=20)
                return r.stdout.strip()
            pid = dormeur(self)
            debut = bash('nc_pid_debut "$1"', pid).stdout.strip()
            self.assertEqual(lire(f"{pid}\n1234\nv.mp4\n{debut}\n"), "1234")
            self.assertEqual(lire(f"{pid}\n1234\nv.mp4\n1\n"), "0", "pid réutilisé")
            self.assertEqual(lire(f"{pid}\n1234\nv.mp4\n"), "0", "ancien format : sleep n'est pas wf-recorder")
            self.assertEqual(lire(f"{zombie(self)}\n1234\nv.mp4\n"), "0", "zombie")
            self.assertEqual(lire(""), "0")
            # nc-pid absent (installation partielle) : le repli kill -0 sert, même pour un sh POSIX (dash), où un « . »
            # sur un fichier absent quitterait le shell
            (Path(d) / "nc-video").write_text(f"{pid}\n1234\nv.mp4\n{debut}\n")
            for sh in [["sh"], ["bash", "--posix"]] + ([["dash"]] if shutil.which("dash") else []):
                with self.subTest(shell=sh[0]):
                    r = subprocess.run(sh + ["-c", script, "sh", str(Path(d) / "absent")], capture_output=True, text=True,
                                       env=dict(os.environ, XDG_RUNTIME_DIR=d), timeout=20)
                    self.assertEqual(r.stdout.strip(), "1234", r.stderr)


if __name__ == "__main__":
    unittest.main()

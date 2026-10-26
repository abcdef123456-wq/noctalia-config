"""nc-pouls : le halo revient à zéro sur SIGTERM, et cava qui ne démarre pas n'est pas relancé toutes les 2 s.

Faux Hyprland (socket Unix dans un dossier temporaire qui note les commandes), faux playerctl (« Playing ») et faux
cava, dans un HOME et un XDG_RUNTIME_DIR temporaires : rien ne touche la vraie session.
"""
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest

BIN = Path(__file__).resolve().parents[1] / "home/.local/bin/nc-pouls"

CAVA_OK = "#!/bin/sh\nwhile true; do echo '100;100;0;0;0;0;0;0'; sleep 0.05; done\n"
CAVA_KO = "#!/bin/sh\necho x >> \"$FAKE/cava-lancements\"\necho 'pas de son' >&2\nexit 1\n"


class Cadre:
    def __init__(self, cava):
        self.tmp = tempfile.TemporaryDirectory()
        t = Path(self.tmp.name)
        self.run = t / "run"
        sock_dir = self.run / "hypr/sig"
        sock_dir.mkdir(parents=True)
        (t / "home").mkdir()
        (t / "bin").mkdir()
        for nom, texte in (("playerctl", "#!/bin/sh\necho Playing\n"), ("cava", cava)):
            f = t / "bin" / nom
            f.write_text(texte)
            f.chmod(0o755)
        self.cmds = []
        self.srv = socket.socket(socket.AF_UNIX)
        self.srv.bind(str(sock_dir / ".socket.sock"))
        self.srv.listen(8)
        self.arret = False
        threading.Thread(target=self._sert, daemon=True).start()
        self.env = dict(os.environ, HOME=str(t / "home"), XDG_RUNTIME_DIR=str(self.run), FAKE=str(t),
                        HYPRLAND_INSTANCE_SIGNATURE="sig", NC_LANGUE="fr",
                        PATH=str(t / "bin") + os.pathsep + os.environ.get("PATH", ""))
        self.t = t

    def _sert(self):
        while not self.arret:
            try:
                c, _ = self.srv.accept()
            except OSError:
                return
            with c:
                self.cmds.append(c.recv(256).decode())
                c.sendall(b"ok")

    def lance(self):
        return subprocess.Popen([sys.executable, str(BIN)], env=self.env, stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL)

    def ferme(self):
        self.arret = True
        self.srv.close()
        self.tmp.cleanup()


def attend(cond, delai):
    fin = time.time() + delai
    while time.time() < fin:
        if cond():
            return True
        time.sleep(0.05)
    return False


class TestPouls(unittest.TestCase):
    def test_sigterm_remet_le_halo_a_zero(self):
        c = Cadre(CAVA_OK)
        self.addCleanup(c.ferme)
        p = c.lance()
        self.addCleanup(lambda: p.poll() is None and p.kill())
        self.assertTrue(attend(lambda: any(x != "eval nc.halo(0.00)" for x in c.cmds), 8), c.cmds)
        p.send_signal(signal.SIGTERM)
        self.assertEqual(p.wait(timeout=5), 0)
        self.assertEqual(c.cmds[-1], "eval nc.halo(0.00)")

    def test_cava_en_echec_pas_relance_toutes_les_2_s(self):
        c = Cadre(CAVA_KO)
        self.addCleanup(c.ferme)
        p = c.lance()
        self.addCleanup(lambda: p.poll() is None and p.kill())
        journal = c.t / "cava-lancements"
        time.sleep(6)      # sans la pause : lancements à 0, 2 et 4 s
        p.send_signal(signal.SIGTERM)
        p.wait(timeout=5)
        # un lancement par entrée son (pipewire, pulse), puis la pause de 60 s
        self.assertEqual(len(journal.read_text().split()), 2)

    def test_suivi_par_evenements_pas_d_interrogation_en_boucle(self):
        c = Cadre(CAVA_OK)
        self.addCleanup(c.ferme)
        # playerctl : « --follow » écrit une ligne puis attend ; sans --follow, répond une fois
        f = c.t / "bin/playerctl"
        f.write_text('#!/bin/sh\necho "$*" >> "$FAKE/playerctl-appels"\n'
                     'case "$*" in *--follow*) echo Playing; exec sleep 30 ;; *) echo Playing ;; esac\n')
        p = c.lance()
        self.addCleanup(lambda: p.poll() is None and p.kill())
        time.sleep(6)
        p.send_signal(signal.SIGTERM)
        p.wait(timeout=5)
        appels = (c.t / "playerctl-appels").read_text().splitlines()
        self.assertTrue(any("--follow" in a for a in appels), appels)
        # avant : une interrogation toutes les 2 s (3 en 6 s au moins, sans fin) ; maintenant : au départ et sur événement
        self.assertLessEqual(len([a for a in appels if "--follow" not in a]), 3, appels)

    def test_ecran_eteint_pas_de_halo(self):
        c = Cadre(CAVA_OK)
        self.addCleanup(c.ferme)
        (c.run / "nc-ecran-eteint").write_text("")
        p = c.lance()
        self.addCleanup(lambda: p.poll() is None and p.kill())
        time.sleep(3)
        p.send_signal(signal.SIGTERM)
        p.wait(timeout=5)
        self.assertFalse([x for x in c.cmds if x != "eval nc.halo(0.00)"], c.cmds)

    def test_sans_cava_sort_proprement_avec_0(self):
        c = Cadre(CAVA_OK)
        self.addCleanup(c.ferme)
        (c.t / "bin/cava").unlink()
        env = dict(c.env, PATH=str(c.t / "bin"))
        r = subprocess.run([sys.executable, str(BIN)], env=env, capture_output=True, text=True, timeout=10)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("cava introuvable", r.stderr)

    def test_cava_arrete_est_recupere_meme_s_il_ignore_sigterm(self):
        c = Cadre("#!/bin/sh\ntrap '' TERM\necho $$ > \"$FAKE/cava-pid\"\n"
                  "while true; do echo '100;100;0;0;0;0;0;0'; sleep 0.05; done\n")
        self.addCleanup(c.ferme)
        etat = c.t / "etat"
        etat.write_text("Playing\n")
        # playerctl suit un fichier d'état : « Playing » puis « Paused »
        (c.t / "bin/playerctl").write_text('#!/bin/sh\ncase "$*" in *--follow*) cat "$FAKE/etat"; '
                                           'while [ "$(cat "$FAKE/etat")" = Playing ]; do sleep 0.1; done; cat "$FAKE/etat"; exec sleep 30 ;; '
                                           '*) cat "$FAKE/etat" ;; esac\n')
        p = c.lance()
        self.addCleanup(lambda: p.poll() is None and p.kill())
        pidf = c.t / "cava-pid"
        self.assertTrue(attend(pidf.exists, 8))
        cava_pid = int(pidf.read_text())
        self.addCleanup(lambda: os.path.exists(f"/proc/{cava_pid}") and os.kill(cava_pid, signal.SIGKILL))
        etat.write_text("Paused\n")
        # cava ignore SIGTERM : le service attend 2 s puis le tue et le récupère (ni vivant ni zombie)
        self.assertTrue(attend(lambda: not os.path.exists(f"/proc/{cava_pid}"), 8))
        p.send_signal(signal.SIGTERM)
        p.wait(timeout=5)


if __name__ == "__main__":
    unittest.main()

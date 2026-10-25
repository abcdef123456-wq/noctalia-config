"""Audit E4 : nc-ecran-externe nomme la bonne carte (session sur la NVIDIA seule = prise de la carte intégrée, sans le
bouton « both »), et nc-couvercle ne tue qu'un pid qui est bien le sien. Tout dans un HOME et un faux /sys temporaires."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
BIN = REPO / "home/.local/bin"


def debut(pid):
    return Path(f"/proc/{pid}/stat").read_text().rsplit(") ", 1)[1].split()[19]


class Banc:
    def __init__(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="nc-e4-")
        self.d = Path(self._tmp.name)
        self.home = self.d / "home"
        (self.home / ".local/bin").mkdir(parents=True)
        for n in ("nc-langue", "nc-pid", "nc-ecran-externe", "nc-couvercle"):
            shutil.copy(BIN / n, self.home / ".local/bin" / n)
        self.run = self.d / "run"
        self.run.mkdir()
        self.sys = self.d / "sys"
        self.journal = self.d / "journal"
        self.journal.touch()
        faux = self.d / "faux"
        faux.mkdir()
        for n in ("notify-send", "hyprctl", "loginctl"):
            f = faux / n
            f.write_text(f'#!/bin/sh\nprintf "%s\\n" "{n} $*" >> {self.journal}\nexit 0\n')
            f.chmod(0o755)
        self.env = dict(os.environ, HOME=str(self.home), XDG_RUNTIME_DIR=str(self.run), NC_LANGUE="fr",
                        NC_SYSFS=str(self.sys), PATH=f"{faux}:{os.environ['PATH']}")
        self.env.pop("AQ_DRM_DEVICES", None)

    def carte(self, nom, vendeur, connecteurs=()):
        c = self.sys / "class/drm" / nom
        (c / "device").mkdir(parents=True)
        (c / "device/vendor").write_text(vendeur + "\n")
        for k, etat in connecteurs:
            (self.sys / "class/drm" / f"{nom}-{k}").mkdir(parents=True)
            (self.sys / "class/drm" / f"{nom}-{k}/status").write_text(etat + "\n")

    def appels(self):
        return self.journal.read_text()

    def fermer(self):
        self._tmp.cleanup()


class EcranExterne(unittest.TestCase):
    def lancer(self, banc, aq, cartes_changees):
        flux = banc.d / "flux"
        flux.write_text("".join(f"UDEV  [1.0] change   /devices/pci0000:00/0000:00:02.0/drm/{c} (drm)\n" for c in cartes_changees))
        env = dict(banc.env, AQ_DRM_DEVICES=aq, NC_ECRAN_FLUX=str(flux))
        return subprocess.run(["bash", str(banc.home / ".local/bin/nc-ecran-externe")], env=env, timeout=30,
                              capture_output=True, text=True)

    def test_dediee_ecran_sur_la_carte_integree(self):
        b = Banc(); self.addCleanup(b.fermer)
        b.carte("card1", "0x10de", [("eDP-1", "connected")])
        b.carte("card0", "0x8086", [("HDMI-A-1", "connected")])
        r = self.lancer(b, "/dev/dri/card1", ["card0"])
        self.assertEqual(r.returncode, 0, r.stderr)
        a = b.appels()
        self.assertIn("Écran branché sur la carte intégrée", a)
        self.assertNotIn("Écran branché sur la carte NVIDIA", a)
        self.assertIn("--action=session=", a)
        self.assertNotIn("--action=toujours", a)

    def test_hybride_garde_le_comportement(self):
        b = Banc(); self.addCleanup(b.fermer)
        b.carte("card0", "0x8086", [("eDP-1", "connected")])
        b.carte("card1", "0x10de", [("HDMI-A-1", "connected")])
        r = self.lancer(b, "/dev/dri/card0", ["card1"])
        self.assertEqual(r.returncode, 0, r.stderr)
        a = b.appels()
        self.assertIn("Écran branché sur la carte NVIDIA", a)
        self.assertIn("--action=toujours=Toujours garder la NVIDIA", a)
        self.assertIn("--action=session=", a)

    def test_carte_utilisee_ignoree(self):
        b = Banc(); self.addCleanup(b.fermer)
        b.carte("card1", "0x10de", [("eDP-1", "connected"), ("HDMI-A-1", "connected")])
        self.lancer(b, "/dev/dri/card1", ["card1"])
        self.assertNotIn("notify-send", b.appels())


class Couvercle(unittest.TestCase):
    def ouvre(self, banc):
        return subprocess.run(["bash", str(banc.home / ".local/bin/nc-couvercle"), "ouvre"], env=banc.env,
                              timeout=30, capture_output=True, text=True)

    def lance(self, nom):
        p = subprocess.Popen(["bash", "-c", f"exec -a {nom} sleep 60"])
        self.addCleanup(lambda: (p.poll() is None) and (p.kill(), p.wait()))
        return p

    def attendre(self, p):
        try:
            p.wait(timeout=3)
            return True
        except subprocess.TimeoutExpired:
            return False

    def test_pid_d_un_autre_processus_pas_tue(self):
        b = Banc(); self.addCleanup(b.fermer)
        p = self.lance("autre-chose")
        (b.run / "nc-couvercle-inactivite.pid").write_text(f"{p.pid}\n")        # ancien format, mauvais nom
        self.ouvre(b)
        self.assertFalse(self.attendre(p))
        self.assertFalse((b.run / "nc-couvercle-inactivite.pid").exists())
        q = self.lance("systemd-inhibit")
        (b.run / "nc-couvercle-inactivite.pid").write_text(f"{q.pid} 1\n")      # bon nom, mais autre heure de début
        self.ouvre(b)
        self.assertFalse(self.attendre(q))

    def test_notre_pid_tue(self):
        b = Banc(); self.addCleanup(b.fermer)
        p = self.lance("autre-chose")
        (b.run / "nc-couvercle-inactivite.pid").write_text(f"{p.pid} {debut(p.pid)}\n")   # nouveau format
        self.ouvre(b)
        self.assertTrue(self.attendre(p))
        q = self.lance("systemd-inhibit")
        (b.run / "nc-couvercle-inactivite.pid").write_text(f"{q.pid}\n")                 # ancien format, bon nom
        self.ouvre(b)
        self.assertTrue(self.attendre(q))


if __name__ == "__main__":
    unittest.main()

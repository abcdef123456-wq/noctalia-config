"""Lot J47, partie C : manettes de Steam (règles udev) et xrandr. nc-diag (jeux_steam) dans le processus, avec un faux
système (NC_DIAG_RACINE : os-release, udev, flatpak) ; le bloc « Jeux » d'install.sh exécuté par bash avec de faux
have, pkg_install, info, ok, warn : rien n'est installé, aucun sudo, aucun vrai udevadm."""
from importlib.machinery import SourceFileLoader
from importlib.util import module_from_spec, spec_from_loader
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock

REPO = Path(__file__).resolve().parents[1]
INSTALL = (REPO / "install.sh").read_text()
OS = {"arch": 'ID=arch\n', "fedora": 'ID=fedora\nVERSION_ID=44\n', "trixie": 'ID=debian\nVERSION_CODENAME=trixie\n',
      "bookworm": 'ID=debian\nVERSION_CODENAME=bookworm\n', "ubuntu": 'ID=ubuntu\nID_LIKE=debian\nVERSION_CODENAME=noble\n',
      "tumbleweed": 'ID="opensuse-tumbleweed"\nID_LIKE="opensuse suse"\n', "leap": 'ID="opensuse-leap"\nID_LIKE="suse opensuse"\n'}


def charger():
    spec = spec_from_loader("nc_diag_jeux", SourceFileLoader("nc_diag_jeux", str(REPO / "home/.local/bin/nc-diag")))
    mod = module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class Diagnostic(unittest.TestCase):
    def setUp(self):
        p = mock.patch.dict(os.environ, NC_LANGUE="fr")
        p.start()
        self.addCleanup(p.stop)
        self.tmp = Path(tempfile.mkdtemp(prefix="nc-diag-jeux-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.mod = charger()
        self.mod.T = lambda fr, en: fr
        self.mod.RACINE = str(self.tmp / "racine")
        self.mod.HOME = str(self.tmp / "home")
        self.bins = set()
        self.ecrans = ["eDP-1"]
        self.mod.a = lambda c: c in self.bins
        self.mod.sortie = lambda cmd, *a, **k: (json.dumps([{"name": n} for n in self.ecrans]), 0) if cmd[:2] == ["hyprctl", "monitors"] else ("", 127)

    def poser(self, chemin, texte=""):
        p = self.tmp / "racine" / chemin
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(texte)

    def bilan(self, distrib="fedora"):
        self.poser("etc/os-release", OS[distrib])
        b = self.mod.Bilan(False)
        self.mod.jeux_steam(b)
        return b, " ".join(str(x) for x in b.lignes)

    def flatpak(self):
        (self.tmp / "racine/var/lib/flatpak/app/com.valvesoftware.Steam").mkdir(parents=True)

    def test_sans_steam_rien(self):
        self.ecrans = ["eDP-1", "DP-1"]
        b, texte = self.bilan()
        self.assertEqual((b.lignes, b.attention), ([], 0))

    def test_paquet_nomme_seulement_la_ou_il_est_verifie(self):
        self.flatpak()
        self.bins.add("xrandr")
        for distrib, attendu in (("fedora", "sudo dnf install steam-devices"), ("trixie", "sudo apt install steam-devices"),
                                 ("tumbleweed", "sudo zypper install steam-devices"),
                                 ("arch", "active le dépôt multilib, puis : sudo pacman -S steam-devices"),
                                 ("bookworm", "installe les règles udev des manettes Steam de ta distribution"),
                                 ("ubuntu", "installe les règles udev des manettes Steam de ta distribution"),
                                 ("leap", "installe les règles udev des manettes Steam de ta distribution")):
            with self.subTest(distrib):
                b, texte = self.bilan(distrib)
                self.assertEqual(b.attention, 1, texte)
                self.assertIn(attendu, texte)
                if "ta distribution" in attendu:
                    self.assertNotIn("steam-devices", texte)

    def test_arch_paquet_steam_natif_pas_de_fausse_alerte(self):
        self.bins.update({"steam", "xrandr"})
        self.poser("usr/lib/udev/rules.d/70-steam-input.rules", "KERNEL==\"uinput\"\n")
        b, texte = self.bilan("arch")
        self.assertEqual(b.attention, 0, texte)
        self.assertIn("règles des manettes de Steam installées", texte)
        for d in ("lib/udev/rules.d", "etc/udev/rules.d"):             # les autres dossiers de règles comptent aussi
            with self.subTest(d):
                shutil.rmtree(self.tmp / "racine/usr", ignore_errors=True)
                shutil.rmtree(self.tmp / "racine/lib", ignore_errors=True)
                shutil.rmtree(self.tmp / "racine/etc/udev", ignore_errors=True)
                self.poser(d + "/60-steam-input.rules")
                self.assertEqual(self.bilan("trixie")[0].attention, 0)

    def test_steam_flatpak_de_l_utilisateur(self):
        (self.tmp / "home/.local/share/flatpak/app/com.valvesoftware.Steam").mkdir(parents=True)
        self.bins.add("xrandr")
        self.assertEqual(self.bilan()[0].attention, 1)

    def test_xrandr_seulement_avec_steam_et_plusieurs_ecrans(self):
        self.bins.add("steam")
        self.poser("usr/lib/udev/rules.d/60-steam-input.rules")
        self.ecrans = ["eDP-1", "HEADLESS-2", "FALLBACK"]
        self.assertEqual(self.bilan()[0].attention, 0)                 # un seul vrai écran
        self.ecrans = ["eDP-1", "DP-1"]
        for distrib, paquet in (("fedora", "installe le paquet xrandr"), ("trixie", "installe le paquet x11-xserver-utils"),
                                ("arch", "installe le paquet xorg-xrandr"), ("ubuntu", "installe xrandr")):
            with self.subTest(distrib):
                b, texte = self.bilan(distrib)
                self.assertEqual(b.attention, 1, texte)
                self.assertIn(paquet, texte)
        self.bins.add("xrandr")
        self.assertEqual(self.bilan()[0].attention, 0)


class Installation(unittest.TestCase):
    def bloc(self):
        i = INSTALL.index("  # Jeux (Steam présent : paquet ou Flatpak)")
        j = INSTALL.index('  case " ${manual[*]} " in', i)
        return INSTALL[i:j]

    def lancer(self, famille, osid, code="", steam=True, xrandr=False, regles=False, flatpak=None):
        with tempfile.TemporaryDirectory(prefix="nc-inst-jeux-") as d:
            d = Path(d)
            udev = d / "udev"; udev.mkdir()
            if regles:
                (udev / "60-steam-input.rules").write_text("")
            if flatpak:
                (d / "home/.local/share/flatpak/app/com.valvesoftware.Steam").mkdir(parents=True)
            script = ("set -u\nt() { printf '%s' \"$1\"; }\ninfo() { echo \"INFO $*\"; }\nok() { echo \"OK $*\"; }\nwarn() { echo \"WARN $*\"; }\n"
                      "pkg_install() { echo \"INSTALL $*\"; }\n"
                      f"have() {{ case \"$1\" in steam) [ {1 if steam else 0} = 1 ] ;; xrandr) [ {1 if xrandr else 0} = 1 ] ;; *) return 1 ;; esac; }}\n"
                      f"FAMILY={famille}; OSID={osid}; OSCODE={code}; HOME={d / 'home'}; REGLES_UDEV={udev}\n" + self.bloc())
            r = subprocess.run(["bash", "-c", script], capture_output=True, text=True, timeout=30, env={"PATH": "/usr/bin:/bin"})
            self.assertEqual(r.returncode, 0, r.stderr)
            return [l for l in r.stdout.splitlines() if l.startswith("INSTALL")]

    def test_par_distribution(self):
        for args, attendu in ((("fedora", "fedora"), ["INSTALL steam-devices xrandr"]),
                              (("debian", "debian", "trixie"), ["INSTALL steam-devices x11-xserver-utils"]),
                              (("suse", "opensuse-tumbleweed"), ["INSTALL steam-devices xrandr"]),
                              (("arch", "arch"), ["INSTALL xorg-xrandr"]),               # jamais steam-devices (multilib)
                              (("debian", "debian", "bookworm"), []), (("debian", "ubuntu", "noble"), []),
                              (("suse", "opensuse-leap"), []), (("fedora", "rocky"), []), (("other", "gentoo"), [])):
            with self.subTest(args):
                self.assertEqual(self.lancer(*args), attendu)

    def test_seulement_ce_qui_manque_et_seulement_avec_steam(self):
        self.assertEqual(self.lancer("fedora", "fedora", steam=False), [])
        self.assertEqual(self.lancer("fedora", "fedora", regles=True), ["INSTALL xrandr"])
        self.assertEqual(self.lancer("fedora", "fedora", xrandr=True), ["INSTALL steam-devices"])
        self.assertEqual(self.lancer("fedora", "fedora", regles=True, xrandr=True), [])
        self.assertEqual(self.lancer("fedora", "fedora", steam=False, flatpak=True), ["INSTALL steam-devices xrandr"])   # Flatpak de l'utilisateur

    def test_ni_sudo_ni_udevadm(self):
        self.assertNotIn("sudo", self.bloc())
        self.assertNotIn("udevadm", self.bloc())


if __name__ == "__main__":
    unittest.main()

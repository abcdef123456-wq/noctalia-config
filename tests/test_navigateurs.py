"""nc-navigateurs et nc-chromium : copies de .desktop Chromium passant par XWayland, jamais le .desktop de l'utilisateur ;
lancement avec les bons drapeaux. HOME, XDG_* et PATH isolés."""
import importlib.machinery
import importlib.util
import os
import re
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

REPO = Path(__file__).resolve().parents[1]
BIN = REPO / "home/.local/bin"
CHROME = """[Desktop Entry]
Name=Google Chrome
Exec=/usr/bin/google-chrome-stable %U
Type=Application
MimeType=text/html;x-scheme-handler/https;

[Desktop Action new-window]
Name=New Window
Exec=/usr/bin/google-chrome-stable

[Desktop Action new-private-window]
Name=New Incognito Window
Exec=/usr/bin/google-chrome-stable --incognito
"""
BRAVE = "[Desktop Entry]\nName=Brave\nExec=brave %u\nType=Application\n"
FLATPAK = ("[Desktop Entry]\nName=Chromium\nExec=/usr/bin/flatpak run --branch=stable --arch=x86_64 "
           "--command=/app/bin/chromium --file-forwarding org.chromium.Chromium @@u %U @@\nType=Application\n")
AUTRE = "[Desktop Entry]\nName=Firefox\nExec=firefox %u\nType=Application\n"


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        t = Path(self.tmp.name)
        self.home = t / "home"
        self.apps = self.home / ".local/share/applications"
        self.sys = t / "usr/share/applications"
        self.fp = t / "fp/applications"
        self.bin = t / "bin"
        for d in (self.home, self.sys, self.fp, self.bin):
            d.mkdir(parents=True)
        self.conf = self.home / ".config/nc"
        self.conf.mkdir(parents=True)
        self.journal = t / "journal"
        self.env = dict(os.environ, HOME=str(self.home), XDG_CONFIG_HOME=str(self.home / ".config"),
                        XDG_DATA_HOME=str(self.home / ".local/share"), XDG_DATA_DIRS=f"{t / 'usr/share'}:{t / 'fp'}",
                        PATH=f"{self.bin}:{os.environ['PATH']}", DISPLAY=":0", NC_TEST_J=str(self.journal))
        self.env.pop("GDK_SCALE", None)
        self.env.pop("NC_CHROMIUM_WAYLAND", None)

    def reglage(self, valeur):
        (self.conf / "reglages.conf").write_text(f'NAVIGATEURS_XWAYLAND="{valeur}"\n' if valeur else "")

    def faux(self, nom, corps):
        f = self.bin / nom
        f.write_text("#!/bin/sh\n" + corps)
        f.chmod(0o755)

    def run_nc(self, script, *args):
        return subprocess.run(["python3", str(BIN / script), *args], env=self.env, capture_output=True, text=True, timeout=30)


class Navigateurs(Base):
    def setUp(self):
        super().setUp()
        (self.sys / "google-chrome.desktop").write_text(CHROME)
        (self.sys / "brave-browser.desktop").write_text(BRAVE)
        (self.sys / "firefox.desktop").write_text(AUTRE)
        (self.fp / "org.chromium.Chromium.desktop").write_text(FLATPAK)
        self.nc = str(self.home / ".local/bin/nc-chromium")

    def test_installer_oui_cree_les_copies_marquees(self):
        self.reglage("oui")
        r = self.run_nc("nc-navigateurs", "installer")
        self.assertEqual(r.returncode, 0, r.stderr)
        chrome = (self.apps / "google-chrome.desktop").read_text()
        self.assertIn("[Desktop Entry]\nX-NC-Chromium=true\n", chrome)
        self.assertIn(f"Exec={self.nc} /usr/bin/google-chrome-stable %U\n", chrome)
        self.assertIn(f"Exec={self.nc} /usr/bin/google-chrome-stable\n", chrome)
        self.assertIn(f"Exec={self.nc} /usr/bin/google-chrome-stable --incognito\n", chrome)
        self.assertEqual(len(re.findall(r"(?m)^Exec=", chrome)), 3)
        self.assertIn("X-NC-Chromium=true\nTryExec=/usr/bin/google-chrome-stable\n", chrome)
        self.assertIn(f"Exec={self.nc} brave %u\n", (self.apps / "brave-browser.desktop").read_text())
        fp = (self.apps / "org.chromium.Chromium.desktop").read_text()
        self.assertIn(f"Exec={self.nc} /usr/bin/flatpak run --branch=stable", fp)
        self.assertIn("org.chromium.Chromium @@u %U @@\n", fp)
        self.assertFalse((self.apps / "firefox.desktop").exists())

    def test_tryexec_navigateur_disparu_lanceur_cache(self):
        # TryExec= (le programme du Exec d'origine) : le bureau cache le lanceur si le navigateur est désinstallé
        self.reglage("oui")
        self.run_nc("nc-navigateurs", "installer")
        self.assertIn("TryExec=/usr/bin/google-chrome-stable\n", (self.apps / "google-chrome.desktop").read_text())
        self.assertIn("TryExec=brave\n", (self.apps / "brave-browser.desktop").read_text())
        fp = (self.apps / "org.chromium.Chromium.desktop").read_text()
        self.assertNotIn("TryExec=", fp)                 # flatpak : le lanceur générique reste, rien de fiable à tester
        self.assertEqual(len(re.findall(r"(?m)^TryExec=", (self.apps / "google-chrome.desktop").read_text())), 1)

    def test_installer_deux_fois_pareil(self):
        self.reglage("oui")
        self.run_nc("nc-navigateurs", "installer")
        avant = (self.apps / "google-chrome.desktop").read_text()
        self.run_nc("nc-navigateurs", "appliquer")
        self.assertEqual((self.apps / "google-chrome.desktop").read_text(), avant)

    def test_desktop_de_l_utilisateur_intact(self):
        self.reglage("oui")
        self.apps.mkdir(parents=True)
        perso = self.apps / "google-chrome.desktop"
        perso.write_text("[Desktop Entry]\nName=Mon Chrome\nExec=chrome --mien\n")
        self.run_nc("nc-navigateurs", "installer")
        self.assertEqual(perso.read_text(), "[Desktop Entry]\nName=Mon Chrome\nExec=chrome --mien\n")
        self.reglage("non")
        self.run_nc("nc-navigateurs", "installer")
        self.run_nc("nc-navigateurs", "retirer")
        self.assertTrue(perso.exists())

    def test_retirer_ne_retire_que_les_marques(self):
        self.reglage("oui")
        self.run_nc("nc-navigateurs", "installer")
        autre = self.apps / "mon-app.desktop"
        autre.write_text("[Desktop Entry]\nName=X\nExec=x\n")
        r = self.run_nc("nc-navigateurs", "retirer")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(sorted(p.name for p in self.apps.glob("*.desktop")), ["mon-app.desktop"])

    def test_reglage_non_retire_et_ne_cree_rien(self):
        self.reglage("oui")
        self.run_nc("nc-navigateurs", "installer")
        self.assertTrue((self.apps / "brave-browser.desktop").exists())
        self.reglage("non")
        self.run_nc("nc-navigateurs", "installer")
        self.assertEqual(list(self.apps.glob("*.desktop")), [])
        self.reglage("")                               # défaut : non
        self.run_nc("nc-navigateurs", "installer")
        self.assertEqual(list(self.apps.glob("*.desktop")), [])

    def test_navigateur_disparu_copie_retiree(self):
        self.reglage("oui")
        self.run_nc("nc-navigateurs", "installer")
        (self.sys / "brave-browser.desktop").unlink()
        self.run_nc("nc-navigateurs", "installer")
        self.assertFalse((self.apps / "brave-browser.desktop").exists())
        self.assertTrue((self.apps / "google-chrome.desktop").exists())

    def test_update_desktop_database_appele(self):
        self.faux("update-desktop-database", 'echo "udd $*" >> "$NC_TEST_J"\n')
        self.reglage("oui")
        self.run_nc("nc-navigateurs", "installer")
        self.assertIn(f"udd {self.apps}", self.journal.read_text())


class Chromium(Base):
    def setUp(self):
        super().setUp()
        self.faux("navigo", 'echo "navigo $*" >> "$NC_TEST_J"\n')
        self.faux("hyprctl", 'echo "hyprctl $*" >> "$NC_TEST_J"\n'
                  'echo \'[{"name":"A","scale":1.0,"focused":false},{"name":"B","scale":1.6,"focused":true}]\'\n')

    def lancer(self, *args):
        self.journal.write_text("")
        r = self.run_nc("nc-chromium", *args)
        self.assertEqual(r.returncode, 0, r.stderr)
        return self.journal.read_text()

    def test_drapeaux_echelle_hyprctl(self):
        self.reglage("oui")
        j = self.lancer("navigo", "https://exemple.org")
        self.assertIn("navigo --ozone-platform=x11 --force-device-scale-factor=1.6 https://exemple.org\n", j)
        self.assertIn("hyprctl monitors -j", j)

    def test_repli_a_1(self):
        self.reglage("oui")
        self.faux("hyprctl", "exit 1\n")
        self.assertIn("navigo --ozone-platform=x11 --force-device-scale-factor=1 a\n", self.lancer("navigo", "a"))

    def test_gdk_scale_sans_hyprland(self):
        self.reglage("oui")
        self.env["GDK_SCALE"] = "2"
        j = self.lancer("navigo")
        self.assertIn("--force-device-scale-factor=2", j)
        self.assertNotIn("hyprctl", j)

    def test_reglage_non_lancement_normal(self):
        for v in ("non", ""):
            self.reglage(v)
            self.assertEqual(self.lancer("navigo", "x", "--y"), "navigo x --y\n")

    def test_sans_xwayland_lancement_normal(self):
        self.reglage("oui")
        del self.env["DISPLAY"]
        self.assertEqual(self.lancer("navigo", "x"), "navigo x\n")

    def test_wayland_force_par_variable(self):
        self.reglage("oui")
        self.env["NC_CHROMIUM_WAYLAND"] = "1"
        self.assertEqual(self.lancer("navigo", "x"), "navigo x\n")

    def test_flatpak_drapeaux_apres_l_identifiant(self):
        self.reglage("oui")
        self.faux("flatpak", 'echo "flatpak $*" >> "$NC_TEST_J"\n')
        j = self.lancer("flatpak", "run", "--branch=stable", "--command=/app/bin/chromium", "org.chromium.Chromium", "@@u", "%U", "@@")
        self.assertIn("flatpak run --branch=stable --command=/app/bin/chromium org.chromium.Chromium "
                      "--ozone-platform=x11 --force-device-scale-factor=1.6 @@u %U @@\n", j)


def charger(env):
    """nc-navigateurs chargé comme module, avec cet environnement."""
    with mock.patch.dict(os.environ, env):
        l = importlib.machinery.SourceFileLoader("ncnav", str(BIN / "nc-navigateurs"))
        m = importlib.util.module_from_spec(importlib.util.spec_from_loader("ncnav", l))
        l.exec_module(m)
    return m


class Corrections(Navigateurs):
    def test_liens_symboliques_jamais_suivis(self):
        self.reglage("oui")
        self.apps.mkdir(parents=True)
        dehors = Path(self.tmp.name) / "dehors"
        (self.apps / "brave-browser.desktop").symlink_to(dehors / "absent.desktop")      # lien pendant
        dehors.mkdir()
        cible = dehors / "marque.desktop"
        cible.write_text("[Desktop Entry]\nX-NC-Chromium=true\nExec=x\n")
        (self.apps / "google-chrome.desktop").symlink_to(cible)                          # lien vers un fichier marqué
        self.run_nc("nc-navigateurs", "installer")
        self.assertFalse((dehors / "absent.desktop").exists())
        self.assertEqual(cible.read_text(), "[Desktop Entry]\nX-NC-Chromium=true\nExec=x\n")
        self.assertTrue((self.apps / "brave-browser.desktop").is_symlink())
        self.assertTrue((self.apps / "google-chrome.desktop").is_symlink())
        self.run_nc("nc-navigateurs", "retirer")
        self.reglage("non")
        self.run_nc("nc-navigateurs", "installer")
        self.assertTrue((self.apps / "brave-browser.desktop").is_symlink())
        self.assertTrue((self.apps / "google-chrome.desktop").is_symlink())
        self.assertTrue(cible.exists())

    def test_jeu_chromium_bsu_pas_touche(self):
        self.reglage("oui")
        (self.sys / "chromium-bsu.desktop").write_text("[Desktop Entry]\nName=Chromium B.S.U.\nExec=chromium-bsu\n")
        self.run_nc("nc-navigateurs", "installer")
        self.assertFalse((self.apps / "chromium-bsu.desktop").exists())
        self.assertTrue((self.apps / "google-chrome.desktop").exists())

    def test_erreur_sur_un_fichier_ne_bloque_pas_les_autres(self):
        self.reglage("oui")
        env = dict(self.env, HOME=str(self.home))
        m = charger(env)
        vrai = m.ecrire
        def ecrire(cible, texte):
            if cible.name == "brave-browser.desktop":
                raise OSError("disque plein")
            vrai(cible, texte)
        with mock.patch.dict(os.environ, env), mock.patch.object(m, "ecrire", ecrire):
            n = m.installer()
        self.assertEqual(n, 2)
        self.assertTrue((self.apps / "google-chrome.desktop").exists())
        self.assertFalse((self.apps / "brave-browser.desktop").exists())

    def test_dbus_activatable_coupe(self):
        self.reglage("oui")
        (self.sys / "google-chrome.desktop").write_text(CHROME.replace("Type=Application", "Type=Application\nDBusActivatable=true")
                                                       + "DBusActivatable=true\n")
        self.run_nc("nc-navigateurs", "installer")
        t = (self.apps / "google-chrome.desktop").read_text()
        self.assertNotIn("DBusActivatable=true", t)
        self.assertEqual(t.count("DBusActivatable=false"), 2)

    @unittest.skipUnless(Path("/usr/share/applications").is_dir(), "pas de /usr/share/applications")
    def test_xdg_data_dirs_partiel_garde_les_dossiers_standard(self):
        m = charger(dict(self.env, XDG_DATA_DIRS="/inexistant"))
        with mock.patch.dict(os.environ, dict(self.env, XDG_DATA_DIRS="/inexistant")):
            self.assertIn(Path("/usr/share/applications"), m.sources())

    def test_pas_de_double_enveloppe(self):
        self.reglage("oui")
        (self.sys / "google-chrome.desktop").write_text(f"[Desktop Entry]\nName=C\nExec={self.nc} /usr/bin/chrome %U\n")
        self.run_nc("nc-navigateurs", "installer")
        self.assertEqual((self.apps / "google-chrome.desktop").read_text().count("nc-chromium"), 1)

    def test_exec_echappe_selon_la_specification(self):
        m = charger(self.env)
        self.assertEqual(m.exec_nc("/h/nc-chromium"), "/h/nc-chromium")
        self.assertEqual(m.exec_nc("/h/a b/nc"), '"/h/a b/nc"')
        self.assertEqual(m.exec_nc("/h/a$b c"), r'"/h/a\\$b c"')
        self.assertEqual(m.exec_nc('/h/q"x'), r'"/h/q\\"x"')
        self.assertEqual(m.exec_nc("/h/50%/n"), "/h/50%%/n")


class ChromiumCorrections(Chromium):
    def test_pas_de_double_appel(self):
        self.reglage("oui")
        j = self.lancer(str(BIN / "nc-chromium"), "navigo", "x")
        self.assertIn("navigo --ozone-platform=x11 --force-device-scale-factor=1.6 x\n", j)

    def test_ozone_platform_hint_ne_compte_pas(self):
        self.reglage("oui")
        self.assertIn("--ozone-platform=x11", self.lancer("navigo", "--ozone-platform-hint=auto"))
        self.assertEqual(self.lancer("navigo", "--ozone-platform=wayland"), "navigo --ozone-platform=wayland\n")
        self.assertEqual(self.lancer("navigo", "--ozone-platform", "wayland"), "navigo --ozone-platform wayland\n")


class Maj(unittest.TestCase):
    def test_nc_maj_appelle_nc_navigateurs(self):
        s = (BIN / "nc-maj").read_text()
        self.assertIn('nc-navigateurs" appliquer', s)
        self.assertLess(s.index("./install.sh"), s.index('nc-navigateurs" appliquer'))

    def test_install_sh_appelle_nc_navigateurs(self):
        self.assertIn("nc-navigateurs", (REPO / "install.sh").read_text())

    def test_reglage_dans_le_catalogue_defaut_non(self):
        with tempfile.TemporaryDirectory() as h:
            r = subprocess.run(["python3", str(BIN / "nc-reglages"), "catalogue"], capture_output=True, text=True,
                               timeout=60, env=dict(os.environ, HOME=h, XDG_CONFIG_HOME=h + "/.config"))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("NAVIGATEURS_XWAYLAND", r.stdout)


if __name__ == "__main__":
    unittest.main()

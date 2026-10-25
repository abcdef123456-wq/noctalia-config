"""nc-session-propre : arrête les anciennes barres sans jamais toucher au compositeur.
- Une barre dans une unité systemd n'est arrêtée ET bloquée (stop + mask) que si l'unité lui est dédiée : son nom contient
  la barre, la barre en est le processus principal, et le fichier d'unité est un vrai fichier d'un dossier d'unités connu.
  Sous uwsm, un ancien « exec-once = waybar » vit dans wayland-wm@hyprland.desktop.service : cette unité-là n'est jamais
  arrêtée ni bloquée. Dans tous les autres cas, seul le processus de la barre est arrêté (kill).
- Le démarrage automatique est désactivé par Hidden=true dans le groupe [Desktop Entry], pas dans le dernier groupe.

Le test lance lui-même un vrai « sleep » (le seul processus tué), un faux /proc (NC_PROC), un faux pgrep et un faux systemctl
qui répond selon l'unité et note ses appels."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "home/.local/bin/nc-session-propre"

FAUX_PGREP = '#!/bin/sh\ncat "$NC_TEST_PIDS"\n'
# show -p MainPID|FragmentPath --value UNITE : lit UNITE.mainpid / UNITE.frag ; tout le reste est seulement noté
FAUX_SYSTEMCTL = '''#!/bin/sh
echo "$*" >> "$NC_TEST_SYSTEMCTL"
if [ "$2" = show ]; then
  case "$4" in
    MainPID) cat "$NC_TEST_UNITES/$6.mainpid" 2>/dev/null ;;
    FragmentPath) cat "$NC_TEST_UNITES/$6.frag" 2>/dev/null ;;
  esac
fi
if [ "$2" = mask ]; then
  # comme systemctl : refuse de masquer une unité dont le fichier est dans ~/.config/systemd/user
  case "$(cat "$NC_TEST_UNITES/$3.frag" 2>/dev/null)" in */.config/systemd/user/*) exit 1 ;; esac
fi
exit 0
'''
FAUX_NOTIFY = '#!/bin/sh\necho "$*" >> "$NC_TEST_NOTIFS"\n'


class SessionPropre(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        t = Path(self.tmp.name)
        self.home, self.proc, self.unites = t / "home", t / "proc", t / "unites"
        for d in (self.home, self.proc, self.unites, t / "bin"):
            d.mkdir()
        for nom, texte in (("pgrep", FAUX_PGREP), ("systemctl", FAUX_SYSTEMCTL), ("notify-send", FAUX_NOTIFY)):
            f = t / "bin" / nom
            f.write_text(texte)
            f.chmod(0o755)
        self.appels = t / "systemctl.log"
        self.appels.touch()
        self.pidsf = t / "pids"
        self.notifs = t / "notifs"
        self.sys = t / "autostart-systeme"      # à la place de /etc/xdg/autostart
        self.sys.mkdir()
        self.unites_sys = t / "unites-systeme"     # à la place de /usr/lib/systemd/user
        self.unites_sys.mkdir()
        self.env = dict(os.environ, HOME=str(self.home), NC_PROC=str(self.proc), NC_TEST_PIDS=str(self.pidsf),
                        NC_TEST_UNITES=str(self.unites), NC_TEST_SYSTEMCTL=str(self.appels), NC_TEST_NOTIFS=str(self.notifs),
                        NC_AUTOSTART_SYS=str(self.sys), NC_UNITES_SYS=str(self.unites_sys),
                        PATH=f"{t / 'bin'}:{os.environ['PATH']}")

    def lance(self, unite, prog="waybar", mainpid=None, frag=None, argv=None, mort=False):
        """Lance un sleep, le déclare comme « prog » vivant dans « unite » ; renvoie (stop/mask notés, sleep tué ?)."""
        p = subprocess.Popen(["sleep", "60"])
        try:
            if mort:
                p.kill()
                p.wait()
            d = self.proc / str(p.pid)
            d.mkdir()
            (d / "cmdline").write_bytes("".join(a + "\0" for a in (argv or [prog])).encode())
            (d / "cgroup").write_text(f"0::/user.slice/user@1000.service/session.slice/{unite}\n")
            self.pidsf.write_text(f"{p.pid}\n")
            if mainpid is not None:
                (self.unites / f"{unite}.mainpid").write_text(f"{p.pid if mainpid == 'pid' else mainpid}\n")
            if frag is not None:
                (self.unites / f"{unite}.frag").write_text(f"{frag}\n")
            r = subprocess.run(["bash", str(SCRIPT), "0"], env=self.env, capture_output=True, text=True, timeout=30)
            self.assertEqual(r.returncode, 0, r.stderr)
            try:
                p.wait(timeout=0.5)   # le script a fini : un kill a déjà eu lieu
                tue = True
            except subprocess.TimeoutExpired:
                tue = False
            return [l for l in self.appels.read_text().splitlines() if " show " not in l], tue
        finally:
            p.kill()
            p.wait()

    def fichier_unite(self, nom="waybar.service"):
        d = self.home / ".config/systemd/user"
        d.mkdir(parents=True, exist_ok=True)
        (d / nom).write_text("[Service]\nExecStart=/bin/true\n")
        return str(d / nom)

    def assertSeulementLeProcessus(self, unite, **kw):
        appels, tue = self.lance(unite, **kw)
        self.assertEqual(appels, [], "aucun stop ni mask attendu")
        self.assertTrue(tue, "le processus de la barre doit être arrêté")

    # --- cas qui ne doivent JAMAIS toucher à l'unité
    def test_compositeur_uwsm(self):
        # même avec MainPID == pid et un vrai fichier d'unité : jamais le compositeur
        self.assertSeulementLeProcessus("wayland-wm@hyprland.desktop.service", mainpid="pid", frag=self.fichier_unite("x.service"))

    def test_compositeur_dont_le_nom_contient_la_barre(self):
        self.assertSeulementLeProcessus("wayland-wm@waybar.service", mainpid="pid", frag=self.fichier_unite())
        self.assertSeulementLeProcessus("hyprland-session.service", mainpid="pid", frag=self.fichier_unite())

    def test_scope_app(self):
        self.assertSeulementLeProcessus("app-foo.scope")

    def test_unite_app_service(self):
        self.assertSeulementLeProcessus("app-waybar.service", mainpid="pid", frag=self.fichier_unite())

    def test_unite_sans_le_nom_de_la_barre(self):
        self.assertSeulementLeProcessus("session-partagee.service", mainpid="pid", frag=self.fichier_unite())

    def test_mainpid_different(self):
        self.assertSeulementLeProcessus("waybar.service", mainpid="999999", frag=self.fichier_unite())

    # --- le cas visé : unité dédiée
    def test_unite_dediee_stop_et_mask(self):
        # fichier d'unité dans le dossier du système (NC_UNITES_SYS) : le faux mask accepte
        (self.unites_sys / "waybar.service").write_text("[Service]\nExecStart=/bin/true\n")
        appels, _ = self.lance("waybar.service", mainpid="pid", frag=str(self.unites_sys / "waybar.service"))
        self.assertEqual(appels, ["--user stop waybar.service", "--user mask waybar.service"])

    def test_mask_refuse_dans_config_alors_disable(self):
        appels, _ = self.lance("waybar.service", mainpid="pid", frag=self.fichier_unite())
        self.assertEqual(appels, ["--user stop waybar.service", "--user mask waybar.service",
                                  "--user disable waybar.service"])

    def test_unite_dediee_instance(self):
        appels, _ = self.lance("waybar@x.service", mainpid="pid", frag=self.fichier_unite("waybar@.service"))
        self.assertEqual(appels[:2], ["--user stop waybar@x.service", "--user mask waybar@x.service"])

    def test_nom_d_unite_pas_une_simple_sous_chaine(self):
        self.assertSeulementLeProcessus("sddm-tags.service", prog="ags", mainpid="pid", frag=self.fichier_unite())

    def test_fichier_vide_ou_hors_dossiers_connus_stop_sans_mask(self):
        appels, _ = self.lance("waybar.service", mainpid="pid", frag="")
        self.assertEqual(appels, ["--user stop waybar.service"])
        autre = Path(self.tmp.name) / "waybar.service"
        autre.write_text("[Service]\n")
        os.remove(self.appels)
        self.appels.touch()
        appels, _ = self.lance("waybar.service", mainpid="pid", frag=str(autre))
        self.assertEqual(appels, ["--user stop waybar.service"])

    # --- démarrage automatique
    def test_hidden_dans_le_groupe_desktop_entry(self):
        a = self.home / ".config/autostart"
        a.mkdir(parents=True)
        (a / "foo.desktop").write_text(
            "[Desktop Entry]\nName=Foo\nHidden=false\nExec=waybar\n\n[Desktop Action new-window]\nName=Nouvelle\nExec=waybar -n\n")
        appels, tue = self.lance("app-foo@autostart.service", prog="waybar")
        self.assertEqual(appels, [])
        self.assertTrue(tue)
        self.assertEqual((a / "foo.desktop").read_text(),
                         "[Desktop Entry]\nHidden=true\nName=Foo\nExec=waybar\n\n[Desktop Action new-window]\nName=Nouvelle\nExec=waybar -n\n")


    def test_surcharge_de_l_utilisateur_gardee(self):
        a = self.home / ".config/autostart"
        a.mkdir(parents=True)
        (a / "foo.desktop").write_text("[Desktop Entry]\nName=Foo\nExec=waybar -c mon-conf\n")
        (self.sys / "foo.desktop").write_text("[Desktop Entry]\nName=Foo\nExec=waybar\n")
        _, tue = self.lance("app-foo@autostart.service")
        self.assertTrue(tue)
        self.assertEqual((a / "foo.desktop").read_text(), "[Desktop Entry]\nHidden=true\nName=Foo\nExec=waybar -c mon-conf\n")

    def test_copie_du_systeme_avec_lien_casse_sans_fichier_temporaire(self):
        a = self.home / ".config/autostart"
        a.mkdir(parents=True)
        cible = self.home / "cible-absente.desktop"
        (a / "foo.desktop").symlink_to(cible)
        (self.sys / "foo.desktop").write_text("[Desktop Entry]\nName=Foo\nExec=waybar\n")
        self.lance("app-foo@autostart.service")
        self.assertFalse((a / "foo.desktop").is_symlink())
        self.assertIn("Hidden=true", (a / "foo.desktop").read_text())
        self.assertFalse(cible.exists(), "la cible du lien ne doit pas être créée")
        self.assertEqual(sorted(f.name for f in a.iterdir()), ["foo.desktop"])

    def test_droits_gardes(self):
        a = self.home / ".config/autostart"
        a.mkdir(parents=True)
        (a / "foo.desktop").write_text("[Desktop Entry]\nExec=waybar\n")
        (a / "foo.desktop").chmod(0o600)
        self.lance("app-foo@autostart.service")
        self.assertEqual((a / "foo.desktop").stat().st_mode & 0o777, 0o600)

    def test_hidden_avec_crlf_et_espaces(self):
        a = self.home / ".config/autostart"
        a.mkdir(parents=True)
        (a / "foo.desktop").write_bytes(b"[Desktop Entry] \r\nExec=waybar\r\n[Desktop Action x]\r\nExec=y\r\n")
        self.lance("app-foo@autostart.service")
        self.assertEqual((a / "foo.desktop").read_bytes(),
                         b"[Desktop Entry] \r\nHidden=true\nExec=waybar\r\n[Desktop Action x]\r\nExec=y\r\n")

    def test_unite_autostart_avec_suffixe(self):
        a = self.home / ".config/autostart"
        a.mkdir(parents=True)
        (a / "foo.desktop").write_text("[Desktop Entry]\nExec=waybar\n")
        _, tue = self.lance("app-foo-autostart@1234.service")
        self.assertTrue(tue)
        self.assertIn("Hidden=true", (a / "foo.desktop").read_text())

    # --- reconnaissance des barres
    def test_barre_lancee_par_un_interprete(self):
        self.assertSeulementLeProcessus("app-x.scope", argv=["python3", "-sP", "/usr/bin/nwg-panel"])
        self.assertSeulementLeProcessus("app-x.scope", argv=["gjs", "-m", "/usr/bin/ags"])

    def assertEpargne(self, argv):
        appels, tue = self.lance("app-x.scope", argv=argv)
        self.assertFalse(tue, f"{argv} ne doit pas être arrêté")

    def test_quickshell_commandes_et_ile_epargnes(self):
        for argv in (["qs", "-c", "autre", "ipc", "call", "x"], ["qs", "-c", "autre", "kill"], ["qs", "-c", "autre", "log"],
                     ["qs", "-c", "autre", "list"], ["qs", "-c", "nc-ile"], ["qs", "-p", "/tmp/nc-qs-capture.x/shell.qml"]):
            with self.subTest(argv=argv):
                self.assertEpargne(argv)

    def test_quickshell_autre_shell_arrete(self):
        self.assertSeulementLeProcessus("app-x.scope", argv=["qs", "-c", "ancienne-noctalia"])

    # --- notification
    def test_notification_seulement_si_arrete(self):
        self.lance("app-x.scope")
        self.assertIn("waybar", self.notifs.read_text())
        self.notifs.unlink()
        self.lance("app-x.scope", mort=True)      # le kill échoue : rien n'a été arrêté
        self.assertFalse(self.notifs.exists())


if __name__ == "__main__":
    unittest.main()

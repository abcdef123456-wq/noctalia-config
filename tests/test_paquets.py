"""Mises à jour du système : nc-paquets (compte, recompte après la mise à jour) et la ligne de la page Système de l'île.

Faux pacman, checkupdates, flatpak et sudo ; HOME isolé. La page Système réelle est chargée hors écran avec des
singletons factices, et le cache passe de 3 à 0 comme après une mise à jour.
"""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import textwrap
import unittest

REPO = Path(__file__).resolve().parents[1]
BIN = REPO / "home/.local/bin"
QML = REPO / "home/.config/quickshell/nc-ile"

# Faux pacman : -Syu réussit (ou échoue si NC_TEST_MAJ_ECHEC) et note l'appel ; -Qu liste ce que dit NC_TEST_LOCAL
FAUX_PACMAN = """#!/bin/sh
echo "pacman $*" >> "$HOME/appels"
case "$1" in
  -Syu) [ -n "${NC_TEST_MAJ_ECHEC:-}" ] && exit 1; exit 0 ;;
  -Qu) printf '%s' "${NC_TEST_LOCAL:-}"; exit 0 ;;
esac
exit 1
"""
# Faux checkupdates (compte complet, avec synchronisation) : ce que dit NC_TEST_DEPOTS
FAUX_CHECKUPDATES = """#!/bin/sh
echo "checkupdates" >> "$HOME/appels"
printf '%s' "${NC_TEST_DEPOTS:-}"
[ -n "${NC_TEST_DEPOTS:-}" ] && exit 0 || exit 2
"""
# Fausse notify-send : note titre et texte (une ligne JSON) au lieu d'afficher
FAUX_NOTIFY = """#!/usr/bin/env python3
import json, os, sys
a = [x for x in sys.argv[1:]]
libres = [x for i, x in enumerate(a) if not x.startswith("-") and (i == 0 or a[i - 1] not in ("-a", "-i", "-A", "-t", "-u"))]
open(os.path.join(os.environ["HOME"], "notifs"), "a").write(json.dumps(libres[-2:]) + "\\n")
"""
FAUX_FLATPAK = """#!/bin/sh
echo "flatpak $*" >> "$HOME/appels"
exit 0
"""
FAUX_SUDO = '#!/bin/sh\nexec "$@"\n'
# Faux paru : -Qua liste ce que dit NC_TEST_AUR ; -Syu réussit (ou échoue avec NC_TEST_MAJ_ECHEC) ; note l'appel
FAUX_PARU = """#!/bin/sh
echo "paru $*" >> "$HOME/appels"
case "$1" in
  -Qua) printf '%s' "${NC_TEST_AUR:-}"; exit 0 ;;
  -Syu) [ -n "${NC_TEST_MAJ_ECHEC:-}" ] && exit 1; exit 0 ;;
esac
exit 1
"""


class Paquets(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        (self.home / "bin").mkdir()
        for nom, code in [("pacman", FAUX_PACMAN), ("checkupdates", FAUX_CHECKUPDATES), ("flatpak", FAUX_FLATPAK), ("sudo", FAUX_SUDO), ("paru", FAUX_PARU), ("notify-send", FAUX_NOTIFY)]:
            p = self.home / "bin" / nom
            p.write_text(code)
            p.chmod(0o755)
        (self.home / ".config/nc").mkdir(parents=True)
        (self.home / ".config/nc/reglages.conf").write_text("LANGUE=fr\n")
        self.cache = self.home / ".cache/nc/paquets"

    def lancer(self, *args, **env_sup):
        env = dict(HOME=str(self.home), PATH=str(self.home / "bin") + os.pathsep + "/usr/bin:/bin", NC_LANGUE="fr")
        env.update(env_sup)
        return subprocess.run([str(BIN / "nc-paquets"), *args], env=env, capture_output=True, text=True, timeout=20, stdin=subprocess.DEVNULL)

    def appels(self):
        p = self.home / "appels"
        return p.read_text().splitlines() if p.exists() else []

    def test_compte_complet_puis_recompte_local_apres_la_mise_a_jour(self):
        r = self.lancer("compter", NC_TEST_DEPOTS="avahi 1-1 -> 1-2\nbaloo 6-1 -> 6-2\nzsh 5-1 -> 5-2\n")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.cache.read_text(), "3\navahi\nbaloo\nzsh\n")
        self.assertEqual(self.appels(), ["checkupdates", "paru -Qua --color never", "flatpak remote-ls --updates --columns=application,version"])
        (self.home / "appels").unlink()
        # La mise à jour dans le terminal : pacman -Syu puis flatpak update, puis le recompte avec les dépôts synchronisés
        r = self.lancer("terminal", NC_TEST_DEPOTS="avahi 1-1 -> 1-2\n", NC_TEST_LOCAL="")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.cache.read_text(), "0\n\n", "le cache doit passer à 0 après la mise à jour")
        self.assertEqual(self.appels(), ["paru -Syu", "flatpak update", "pacman -Qu", "paru -Qua --color never", "flatpak remote-ls --updates --columns=application,version"],
                         "après une mise à jour réussie, pas de checkupdates (resynchronisation réseau, longue)")
        self.assertIn("Système à jour.", r.stdout)
        self.assertIn("Recompte des mises à jour", r.stdout)

    def notifs(self, attendu, delai=3.0):
        """Les notifications reçues (la fausse notify-send part en arrière-plan) : attend d'en avoir « attendu »."""
        import json, time
        f = self.home / "notifs"
        fin = time.time() + delai
        while time.time() < fin:
            n = [json.loads(l) for l in f.read_text().splitlines()] if f.exists() else []
            if len(n) >= attendu:
                return n
            time.sleep(0.05)
        return [json.loads(l) for l in f.read_text().splitlines()] if f.exists() else []

    def test_details_notification_nouveautes_et_rappel(self):
        import json, os, time
        depots = "zsh 5-1 -> 5-2\nlinux 6.1-1 -> 6.2-1\n"
        r = self.lancer("compter", NC_TEST_DEPOTS=depots, NC_TEST_AUR="zen-browser-bin 1.0-1 -> 1.1-1\n")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.cache.read_text(), "3\naur:zen-browser-bin\nlinux\nzsh\n")
        d = json.loads((self.home / ".cache/nc/paquets.json").read_text())
        self.assertEqual((d["total"], d["sources"], d["noyau"]), (3, {"depot": 2, "aur": 1, "flatpak": 0}, True))
        self.assertEqual(d["paquets"][0]["nom"], "linux", "les importants d'abord")
        n = self.notifs(1)
        self.assertEqual(len(n), 1, "nouvelles mises à jour : une notification (réglage par défaut)")
        titre, corps = n[0]
        self.assertEqual(titre, "3 mises à jour")
        self.assertIn("linux 6.1-1 → 6.2-1", corps)
        self.assertIn("Dépôts 2 · AUR 1", corps)
        self.assertIn("redémarre", corps)
        # Les mêmes : rien de nouveau, pas de notification
        self.lancer("compter", NC_TEST_DEPOTS=depots, NC_TEST_AUR="zen-browser-bin 1.0-1 -> 1.1-1\n")
        self.assertEqual(len(self.notifs(2, 0.6)), 1)
        # Une nouvelle arrive : notifiée
        self.lancer("compter", NC_TEST_DEPOTS=depots + "mesa 25-1 -> 25-2\n", NC_TEST_AUR="zen-browser-bin 1.0-1 -> 1.1-1\n")
        self.assertEqual(len(self.notifs(2)), 2)
        # Toujours là un jour plus tard : rappel (sauf MAJ_RAPPEL=jamais)
        etat = self.home / ".cache/nc/paquets-notif.json"
        e = json.loads(etat.read_text()); e["date"] = int(time.time()) - 2 * 86400; etat.write_text(json.dumps(e))
        (self.home / ".config/nc/reglages.conf").write_text("LANGUE=fr\nMAJ_RAPPEL=jamais\n")
        self.lancer("compter", NC_TEST_DEPOTS=depots + "mesa 25-1 -> 25-2\n", NC_TEST_AUR="zen-browser-bin 1.0-1 -> 1.1-1\n")
        self.assertEqual(len(self.notifs(3, 0.6)), 2, "MAJ_RAPPEL=jamais : pas de rappel")
        (self.home / ".config/nc/reglages.conf").write_text("LANGUE=fr\n")
        self.lancer("compter", NC_TEST_DEPOTS=depots + "mesa 25-1 -> 25-2\n", NC_TEST_AUR="zen-browser-bin 1.0-1 -> 1.1-1\n")
        self.assertEqual(len(self.notifs(3)), 3, "rappel quotidien")
        # Seulement dans l'île : pas de notification ; « Chercher » notifie quand même, même à jour
        (self.home / ".config/nc/reglages.conf").write_text("LANGUE=fr\nMAJ_SYSTEME=ile\n")
        self.lancer("compter", NC_TEST_DEPOTS=depots + "vlc 3-1 -> 3-2\n")
        self.assertEqual(len(self.notifs(4, 0.6)), 3)
        r = self.lancer("verifier", NC_TEST_DEPOTS="")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.notifs(4)[-1][0], "Système à jour")
        self.assertEqual(self.cache.read_text(), "0\n\n")

    def test_cadence_sobre(self):
        import os, time
        # Alimentation et connexion simulées (pas celles de la machine qui lance les tests)
        alim = self.home / "alim"
        for nom, fichiers in (("AC", {"type": "Mains", "online": "1"}), ("BAT0", {"type": "Battery"})):
            (alim / nom).mkdir(parents=True)
            for f, v in fichiers.items():
                (alim / nom / f).write_text(v + "\n")
        lancer = lambda *a, **e: self.lancer(*a, NC_POWER_SUPPLY=str(alim), NC_METERED="u 4", **e)
        # Compte tout juste fait : le passage du minuteur ne fait rien (aucun gestionnaire de paquets lancé)
        lancer("compter", NC_TEST_DEPOTS="zsh 5-1 -> 5-2\n")
        (self.home / "appels").unlink()
        lancer("compter", "auto", NC_TEST_DEPOTS="zsh 5-1 -> 5-2\n")
        self.assertEqual(self.appels(), [], "trop tôt : rien")
        # Compte d'il y a 2 h : il est temps (une fois par heure par défaut)…
        vieux = time.time() - 2 * 3600
        os.utime(self.cache, (vieux, vieux))
        lancer("compter", "auto", NC_TEST_DEPOTS="zsh 5-1 -> 5-2\n")
        self.assertIn("checkupdates", self.appels())
        # … sauf en Économie : au plus toutes les 6 h
        (self.home / "appels").unlink()
        os.utime(self.cache, (vieux, vieux))
        (self.home / ".config/hypr/nc").mkdir(parents=True)
        (self.home / ".config/hypr/nc/profil.lua").write_text('return { profil = "power-saver", batterie = false, hz = "max" }\n')
        lancer("compter", "auto", NC_TEST_DEPOTS="zsh 5-1 -> 5-2\n")
        self.assertEqual(self.appels(), [], "Économie : pas avant 6 h")
        # Sur batterie (hors Économie) : au plus toutes les 3 h ; sur une connexion limitée : 12 h
        (self.home / ".config/hypr/nc/profil.lua").unlink()
        (alim / "AC/online").write_text("0\n")
        os.utime(self.cache, (vieux, vieux))
        lancer("compter", "auto", NC_TEST_DEPOTS="zsh 5-1 -> 5-2\n")
        self.assertEqual(self.appels(), [], "batterie : pas avant 3 h")
        tres_vieux = time.time() - 4 * 3600
        os.utime(self.cache, (tres_vieux, tres_vieux))
        lancer("compter", "auto", NC_TEST_DEPOTS="zsh 5-1 -> 5-2\n")
        self.assertIn("checkupdates", self.appels(), "batterie, 4 h après : il est temps")
        (self.home / "appels").unlink()
        (alim / "AC/online").write_text("1\n")
        os.utime(self.cache, (tres_vieux, tres_vieux))
        self.lancer("compter", "auto", NC_POWER_SUPPLY=str(alim), NC_METERED="u 1", NC_TEST_DEPOTS="zsh 5-1 -> 5-2\n")
        self.assertEqual(self.appels(), [], "connexion limitée : pas avant 12 h")

    def test_opensuse_zypper(self):
        """openSUSE : compte depuis le XML de zypper (sans rafraîchir, pas de root), mise à jour par zypper dup."""
        nu = self.home / "nu"; nu.mkdir()
        # Un PATH sans le pacman, dnf ou apt de la machine : seulement les outils de base et les faux
        for outil in ("sh", "bash", "sed", "awk", "grep", "head", "tail", "tr", "mkdir", "rm", "mv", "cat", "wc", "sort", "date", "env", "basename", "dirname", "sleep", "printf", "cp", "touch"):
            vrai = shutil.which(outil)
            if vrai:
                (nu / outil).symlink_to(vrai)
        (nu / "zypper").write_text("""#!/bin/sh
echo "zypper $*" >> "$HOME/appels"
case "$*" in
  *list-updates*) cat <<'XML'
<?xml version='1.0'?>
<stream>
<update-status version="0.6">
<update-list>
<update kind="package" name="mesa" edition="25.2-1.1" arch="x86_64" edition-old="25.1-1.1"><summary>Mesa</summary></update>
<update kind="package" name="firefox" edition="144.0-1.1" arch="x86_64" edition-old="143.0-1.1"><summary>Firefox</summary></update>
<update kind="patch" name="openSUSE-2026-1" edition="1" arch="noarch"><summary>Correctif</summary></update>
</update-list>
</update-status>
</stream>
XML
  ;;
esac
""")
        (nu / "zypper").chmod(0o755)
        (nu / "sudo").write_text('#!/bin/sh\nexec "$@"\n'); (nu / "sudo").chmod(0o755)
        r = self.lancer("compter", PATH=str(nu))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.cache.read_text().splitlines(), ["2", "firefox", "mesa"], "les paquets seulement (triés), pas les correctifs")
        self.assertIn("zypper --non-interactive --no-refresh --xmlout list-updates", self.appels())
        r = subprocess.run([str(BIN / "nc-paquets"), "terminal"], env=dict(HOME=str(self.home), PATH=str(nu), NC_LANGUE="fr"),
                           input="\n", capture_output=True, text=True, timeout=20)
        self.assertIn("zypper dup", self.appels(), "la mise à jour passe par zypper dup")

    def test_paquets_restants_et_ignores(self):
        r = self.lancer("terminal", NC_TEST_LOCAL="linux 6.1-1 -> 6.2-1\nnvidia 1-1 -> 1-2 [ignored]\n")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.cache.read_text(), "1\nlinux\n")
        self.assertIn("1 mise(s) à jour encore en attente.", r.stdout)

    def test_mise_a_jour_echouee_recompte_complet(self):
        r = self.lancer("compter", NC_TEST_DEPOTS="avahi 1-1 -> 1-2\n")
        self.assertEqual(self.cache.read_text(), "1\navahi\n")
        (self.home / "appels").unlink()
        r = self.lancer("terminal", NC_TEST_MAJ_ECHEC="1", NC_TEST_DEPOTS="avahi 1-1 -> 1-2\n", NC_TEST_LOCAL="")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.cache.read_text(), "1\navahi\n", "mise à jour échouée : le compte complet garde la mise à jour en attente")
        self.assertIn("checkupdates", self.appels())
        self.assertNotIn("pacman -Qu", self.appels())

    def test_recompte_survit_a_la_fermeture_du_terminal(self):
        # kitty fermé : SIGHUP au processus ; le recompte va au bout
        env = dict(HOME=str(self.home), PATH=str(self.home / "bin") + os.pathsep + "/usr/bin:/bin", NC_LANGUE="fr", NC_TEST_LOCAL="")
        (self.home / "bin/flatpak").write_text("#!/bin/sh\n[ \"$1\" = update ] && { kill -HUP $PPID; sleep 0.3; }\nexit 0\n")
        r = subprocess.run([str(BIN / "nc-paquets"), "terminal"], env=env, capture_output=True, text=True, timeout=20, stdin=subprocess.DEVNULL)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.cache.read_text(), "0\n\n")


@unittest.skipUnless(shutil.which("qs"), "Quickshell requis")
class LigneMisesAJour(unittest.TestCase):
    def test_page_systeme_passe_de_3_a_0(self):
        with tempfile.TemporaryDirectory(prefix="nc-paquets-qml-") as d:
            root = Path(d)
            (root / "run").mkdir(mode=0o700)
            (root / ".cache/nc").mkdir(parents=True)
            (root / ".cache/nc/paquets").write_text("3\navahi\nbaloo\nzsh\n")
            for nom in ("Systeme.qml", "Ligne.qml", "Module.qml", "Texte.qml", "Ico.qml", "Defilement.qml", "Couleurs.qml"):
                shutil.copy2(QML / nom, root / nom)
            (root / "Reglages.qml").write_text('pragma Singleton\nimport QtQuick\nQtObject {readonly property bool en: true; function t(fr,en){return en} function val(k,d){return d}}')
            (root / "Etat.qml").write_text(textwrap.dedent('''\
                pragma Singleton
                import QtQuick
                QtObject {
                    property var liste: []
                    property var batterie: null
                    property var sys: ({ halo: "0", clavier: "" })
                    property bool branche: false
                    property bool cafe: false
                    property bool aBatterie: false
                    property string profil: ""
                    property int pourcent: 0
                    readonly property string bin: ""
                    property var faits: []
                    function faire(c) { faits.push(c) }
                    function fermer() {}
                    function choisirProfil(p) {}
                    function basculerCafe() {}
                }'''))
            (root / "qmldir").write_text("\n".join(
                ("singleton " if n in ("Couleurs", "Reglages", "Etat") else "") + n + " 1.0 " + n + ".qml"
                for n in ("Systeme", "Ligne", "Module", "Texte", "Ico", "Defilement", "Couleurs", "Reglages", "Etat")))
            (root / "shell.qml").write_text(textwrap.dedent('''\
                import QtQuick
                import QtQuick.Window
                import Quickshell
                import Quickshell.Io
                ShellRoot {
                    id: test
                    property int etape: 0
                    property var page: null
                    property var ligne: null
                    function verifier(ok, message) { if (!ok) { console.error(message); Qt.exit(2) } }
                    function trouver(item, nom) { if (item.objectName === nom) return item; for (var i = 0; i < item.children.length; i++) { var r = trouver(item.children[i], nom); if (r) return r } return null }
                    Window { id: w; visible: true; width: 420; height: 600; color: "#151f2b" }
                    Process { id: recompte; command: ["sh", "-c", "printf '0\\\\n\\\\n' > \\"$HOME/.cache/nc/paquets.tmp\\" && mv \\"$HOME/.cache/nc/paquets.tmp\\" \\"$HOME/.cache/nc/paquets\\""] }
                    Timer { interval: 100; running: true; repeat: true; onTriggered: {
                        if (etape === 0) { var c = Qt.createComponent("Systeme.qml"); verifier(c.status === Component.Ready, c.errorString()); page = c.createObject(w.contentItem, { width: 400, height: 580 }); verifier(page !== null, "page absente"); etape++ }
                        else if (etape === 1) { ligne = trouver(page, "nc-paquets"); verifier(ligne !== null, "ligne absente"); if (!ligne.visible) return
                            verifier(ligne.titre === "3 system updates", "titre initial : " + ligne.titre); verifier(ligne.actif, "ligne inactive"); recompte.running = true; etape++ }
                        else if (etape === 2) { if (ligne.titre !== "System up to date") return
                            verifier(ligne.n === 0 && !ligne.actif, "état après recompte"); verifier(ligne.sous === "Checked every 3 hours", "sous-titre : " + ligne.sous)
                            page.visible = false; page.visible = true; etape++ }
                        else if (etape === 3) { verifier(ligne.titre === "System up to date", "titre après réaffichage : " + ligne.titre); Qt.quit() } } }
                    Timer { interval: 6000; running: true; onTriggered: Qt.exit(9) }
                }'''))
            env = dict(os.environ, HOME=d, QT_QPA_PLATFORM="offscreen", QT_QUICK_BACKEND="software",
                       XDG_RUNTIME_DIR=str(root / "run"), XDG_CACHE_HOME=str(root / ".cache"))
            env.pop("WAYLAND_DISPLAY", None)
            r = subprocess.run(["qs", "--no-color", "-p", str(root / "shell.qml")], env=env, capture_output=True, text=True, timeout=10)
            sortie = r.stdout + r.stderr
            self.assertEqual(r.returncode, 0, sortie)
            for erreur in ("ReferenceError", "TypeError", "Cannot assign", "Binding loop", "is not a type"):
                self.assertNotIn(erreur, sortie)


if __name__ == "__main__":
    unittest.main()

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

# Faux pacman : -Syu réussit (ou échoue, avec un message d'erreur : NC_TEST_MAJ_ECHEC, code 1, rien d'installé ;
# NC_TEST_SU_ECHEC, code 3, après avoir installé ; NC_TEST_NON : la réponse « n », code 1 sans message) et note l'appel ;
# -Sy ou -Su seuls : refusés (mise à jour partielle). -Qu liste ~/qu s'il existe (-Syu le remplace par ~/qu-apres),
# sinon NC_TEST_LOCAL. Paquets installés : ~/db (« nom version », pacman -Q), ~/db-aur (pacman -Qmq) ; -Syu installe
# ~/db-apres (s'il existe) à la place de ~/db
FAUX_PACMAN = """#!/bin/sh
echo "pacman $*" >> "$HOME/appels"
case "$1" in
  -Sy|-Su) echo "jamais -Sy ni -Su séparés (mise à jour partielle)" >&2; exit 9 ;;
  -Syu) [ -n "${NC_TEST_MAJ_ECHEC:-}" ] && { echo "error: failed to synchronize all databases" >&2; exit 1; }
    [ -n "${NC_TEST_NON:-}" ] && exit 1
    [ -e "$HOME/db-apres" ] && mv "$HOME/db-apres" "$HOME/db"
    [ -e "$HOME/qu-apres" ] && mv "$HOME/qu-apres" "$HOME/qu"
    [ -n "${NC_TEST_SU_ECHEC:-}" ] && { echo "error: failed to commit transaction" >&2; exit 3; }; exit 0 ;;
  -Qu) if [ -e "$HOME/qu" ]; then cat "$HOME/qu"; else printf '%s' "${NC_TEST_LOCAL:-}"; fi; exit 0 ;;
  -Q) cat "$HOME/db" 2>/dev/null; exit 0 ;;
  -Qmq) cat "$HOME/db-aur" 2>/dev/null; exit 0 ;;
esac
exit 1
"""
# Faux checkupdates (compte complet, avec synchronisation d'une copie) : ~/qu s'il existe, sinon NC_TEST_DEPOTS
FAUX_CHECKUPDATES = """#!/bin/sh
echo "checkupdates" >> "$HOME/appels"
if [ -e "$HOME/qu" ]; then cat "$HOME/qu"; [ -s "$HOME/qu" ] && exit 0 || exit 2; fi
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
[ "$1" = update ] && [ -n "${NC_TEST_FLATPAK_ECHEC:-}" ] && exit 1
exit 0
"""
FAUX_SUDO = '#!/bin/sh\nexec "$@"\n'
# Faux findmnt (système de fichiers de /, NC_TEST_FS, ext4 par défaut) et faux btrfs : jamais le vrai disque
FAUX_FINDMNT = '#!/bin/sh\necho "${NC_TEST_FS:-ext4}"\n'
FAUX_BTRFS = '#!/bin/sh\necho "btrfs $*" >> "$HOME/appels"\n[ -n "${NC_TEST_BTRFS_ECHEC:-}" ] && exit 1\nexit 0\n'
# Faux paru : -Qua liste ce que dit NC_TEST_AUR ; -Sy et -Su comme le faux pacman ; note l'appel
FAUX_PARU = """#!/bin/sh
echo "paru $*" >> "$HOME/appels"
case "$1" in
  -Qua) printf '%s' "${NC_TEST_AUR:-}"; exit 0 ;;
  -Sy|-Su) echo "jamais -Sy ni -Su séparés (mise à jour partielle)" >&2; exit 9 ;;
  -Syu) [ -n "${NC_TEST_MAJ_ECHEC:-}" ] && { echo "error: failed to synchronize all databases" >&2; exit 1; }
    [ -n "${NC_TEST_NON:-}" ] && exit 1
    [ -e "$HOME/db-apres" ] && mv "$HOME/db-apres" "$HOME/db"
    [ -e "$HOME/qu-apres" ] && mv "$HOME/qu-apres" "$HOME/qu"
    [ -n "${NC_TEST_SU_ECHEC:-}" ] && { echo "error: failed to commit transaction" >&2; exit 3; }; exit 0 ;;
esac
exit 1
"""
# Faux systemd-run (le nouvel essai après un échec) : note l'appel, ne lance jamais rien
FAUX_SYSTEMD_RUN = '#!/bin/sh\necho "systemd-run $*" >> "$HOME/appels"\n'
# Les outils de base, seuls dans le PATH avec les faux : jamais un vrai gestionnaire de paquets (paru, yay, apt, dnf,
# zypper, checkupdates de la machine qui lance les tests)
OUTILS = ("sh", "bash", "env", "python3", "sed", "awk", "grep", "head", "tail", "tr", "mkdir", "rm", "mv", "cat", "wc", "sort",
          "date", "basename", "dirname", "sleep", "printf", "cp", "touch", "tee", "cmp", "find", "mktemp", "flock", "stat",
          "cut", "setsid", "readlink", "timeout", "uniq", "ls", "id", "kill", "chmod", "ln", "seq")


def outils_de_base(dossier):
    dossier.mkdir(exist_ok=True)
    for outil in OUTILS:
        vrai = shutil.which(outil)
        if vrai and not (dossier / outil).exists():
            (dossier / outil).symlink_to(vrai)
    return dossier


class Paquets(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        (self.home / "bin").mkdir()
        for nom, code in [("pacman", FAUX_PACMAN), ("checkupdates", FAUX_CHECKUPDATES), ("flatpak", FAUX_FLATPAK), ("sudo", FAUX_SUDO), ("paru", FAUX_PARU), ("notify-send", FAUX_NOTIFY),
                          ("findmnt", FAUX_FINDMNT), ("btrfs", FAUX_BTRFS), ("systemd-run", FAUX_SYSTEMD_RUN)]:
            p = self.home / "bin" / nom
            p.write_text(code)
            p.chmod(0o755)
        (self.home / ".config/nc").mkdir(parents=True)
        (self.home / ".config/nc/reglages.conf").write_text("LANGUE=fr\n")
        self.cache = self.home / ".cache/nc/paquets"
        self.snaps = self.home / "snapshots"           # jamais le vrai /.snapshots
        self.snaps.mkdir()
        self.chemin = str(self.home / "bin") + os.pathsep + str(outils_de_base(self.home / "sys"))

    def lancer(self, *args, entree=None, **env_sup):
        env = dict(HOME=str(self.home), PATH=self.chemin, NC_LANGUE="fr", NC_SNAPSHOTS=str(self.snaps))
        env.update(env_sup)
        return subprocess.run([str(BIN / "nc-paquets"), *args], env=env, capture_output=True, text=True, timeout=30,
                              **(dict(input=entree) if entree is not None else dict(stdin=subprocess.DEVNULL)))

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
        releves = {"pacman -Qmq", "pacman -Q", "flatpak list --columns=application,branch,version,active"}     # installés avant, après
        self.assertEqual([a for a in self.appels() if a not in releves],
                         ["checkupdates", "paru -Qua --color never", "paru -Syu", "flatpak update",
                          "pacman -Qu", "paru -Qua --color never", "flatpak remote-ls --updates --columns=application,version"],
                         "ce qui attend sans toucher la vraie base (checkupdates), puis -Syu d'un seul coup ; après une "
                         "mise à jour réussie, le recompte sans checkupdates (resynchronisation réseau, longue)")
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

    def test_echec_de_verification_jamais_a_jour(self):
        """Revue Codex PKG-01 : checkupdates en échec (réseau) vidait le compte et annonçait « Système à jour »."""
        import json
        depots = "zsh 5-1 -> 5-2\nlinux 6.1-1 -> 6.2-1\n"
        self.lancer("compter", NC_TEST_DEPOTS=depots, NC_TEST_AUR="zen-browser-bin 1.0-1 -> 1.1-1\n")
        self.assertEqual(self.cache.read_text().splitlines()[0], "3")
        ck = self.home / "bin/checkupdates"
        ck.write_text('#!/bin/sh\necho "checkupdates" >> "$HOME/appels"\necho "==> ERROR: Cannot fetch updates" >&2\nexit 1\n')
        r = self.lancer("verifier", NC_TEST_AUR="zen-browser-bin 1.0-1 -> 1.1-1\n")
        self.assertEqual(r.returncode, 1, "lancé à la main : un compte incomplet est un échec")
        self.assertIn("incomplète", r.stderr)
        self.assertEqual(self.cache.read_text(), "3\naur:zen-browser-bin\nlinux\nzsh\n", "le dernier état des dépôts est gardé")
        d = json.loads((self.home / ".cache/nc/paquets.json").read_text())
        self.assertEqual(d["incomplet"], ["depot"])
        self.assertLessEqual(d["date_ok"], d["date"], "l'heure du dernier compte complet, pas celle de l'échec")
        self.assertIn("pas de réponse : dépôts", r.stderr, "noms traduits, comme la notification")
        titre, corps = self.notifs(2)[-1]
        self.assertNotEqual(titre, "Système à jour")
        self.assertIn("Pas vérifié cette fois : dépôts", corps)
        self.assertTrue((self.home / ".cache/nc/paquets-erreur").exists())
        # Rien de connu et tout en échec : « Vérification impossible », jamais « à jour »
        (self.home / ".cache/nc/paquets.json").unlink()
        self.lancer("verifier")
        self.assertEqual(self.notifs(3)[-1][0], "Vérification impossible")
        # « compter » à la main échoue aussi ; la source revient : l'état d'erreur disparaît
        self.assertEqual(self.lancer("compter").returncode, 1)
        ck.write_text(FAUX_CHECKUPDATES)
        self.assertEqual(self.lancer("compter", NC_TEST_DEPOTS="").returncode, 0)
        self.assertFalse((self.home / ".cache/nc/paquets-erreur").exists())
        self.assertEqual(self.cache.read_text(), "0\n\n")

    def test_instantane_si_crochet_snapper_d_une_seule_distribution(self):
        """Revue Codex PKG-02 : snap-pac présent (Arch) mais pas les crochets des autres distributions : « ls » échouait
        et nc-paquets prenait un instantané en double."""
        crochet = self.home / "snap-pac.hook"; crochet.write_text("")
        racine = self.home / "snapper-root"; racine.write_text("")
        env = dict(NC_TEST_FS="btrfs", NC_TEST_DEPOTS="zsh 5-1 -> 5-2\n", NC_CROCHETS_SNAPPER=f"{crochet} /nulle/part/snapper.py",
                   NC_SNAPPER_ROOT=str(racine))
        r = self.lancer("terminal", **env)
        self.assertIn("fait par snapper", r.stdout)
        self.assertFalse([x for x in self.appels() if x.startswith("btrfs")])
        # Crochet sans configuration de / : il ne sert à rien, nc-paquets fait l'instantané
        racine.unlink()
        self.lancer("terminal", **env)
        self.assertTrue([x for x in self.appels() if x.startswith("btrfs subvolume snapshot")])

    def test_instantane_btrfs_avant_la_mise_a_jour(self):
        r = self.lancer("terminal", NC_TEST_FS="btrfs", NC_TEST_DEPOTS="zsh 5-1 -> 5-2\n", NC_SNAPSHOTS=str(self.snaps))
        self.assertEqual(r.returncode, 0, r.stderr)
        a = self.appels()
        prises = [x for x in a if x.startswith(f"btrfs subvolume snapshot -r / {self.snaps}/nc-avant-maj-")]
        self.assertEqual(len(prises), 1, a)
        self.assertLess(a.index("checkupdates"), a.index(prises[0]), "ce qui attend d'abord (une copie des dépôts) : on sait s'il y a quelque chose")
        self.assertLess(a.index(prises[0]), a.index("paru -Syu"), "l'instantané avant la mise à jour")
        self.assertIn(f"Instantané : {self.snaps}/nc-avant-maj-", r.stdout)

    def test_pas_d_instantane_hors_btrfs_ou_si_coupe(self):
        self.lancer("terminal", NC_TEST_DEPOTS="zsh 5-1 -> 5-2\n")
        self.assertFalse([x for x in self.appels() if x.startswith("btrfs")], "ext4 : rien")
        (self.home / ".config/nc/reglages.conf").write_text("LANGUE=fr\nMAJ_INSTANTANE=non\n")
        self.lancer("terminal", NC_TEST_FS="btrfs", NC_TEST_DEPOTS="zsh 5-1 -> 5-2\n")
        self.assertFalse([x for x in self.appels() if x.startswith("btrfs")], "réglage coupé : rien")

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
        for outil in ("sh", "bash", "sed", "awk", "grep", "head", "tail", "tr", "mkdir", "rm", "mv", "cat", "wc", "sort", "date", "env", "basename", "dirname", "sleep", "printf", "cp", "touch", "tee", "cmp", "python3", "mktemp"):
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
        env = dict(HOME=str(self.home), PATH=self.chemin, NC_LANGUE="fr", NC_TEST_LOCAL="")
        (self.home / "bin/flatpak").write_text("#!/bin/sh\n[ \"$1\" = update ] && { kill -HUP $PPID; sleep 0.3; }\nexit 0\n")
        r = subprocess.run([str(BIN / "nc-paquets"), "terminal"], env=env, capture_output=True, text=True, timeout=20, stdin=subprocess.DEVNULL)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.cache.read_text(), "0\n\n")

    # ── Le rapport : ce qui a vraiment été installé (revue B1, R1 R2 R3) ──
    def avec_rapport(self):
        """nc-ia (sans IA : IA_MODE=non) et nc-langue dans le ~/.local/bin du HOME de test : le rapport des faits."""
        lb = self.home / ".local/bin"
        lb.mkdir(parents=True, exist_ok=True)
        for nom in ("nc-ia", "nc-langue"):
            (lb / nom).symlink_to(BIN / nom)
        with open(self.home / ".config/nc/reglages.conf", "a") as f:
            f.write("IA_MODE=non\n")

    def rapport(self, delai=8.0):
        """Le rapport écrit par nc-ia (lancé en arrière-plan par nc-paquets), ou None."""
        import json, time
        f = self.home / ".cache/nc/rapports/systeme.json"
        fin = time.time() + delai
        while time.time() < fin:
            try:
                return json.loads(f.read_text())
            except (OSError, ValueError):
                time.sleep(0.1)
        return None

    def test_rapport_des_versions_vraiment_installees(self):
        """Revue B1 R1 : le rapport recopiait la liste d'attente d'avant (zsh 5-2) alors que pacman a installé 5-3,
        et un paquet sorti entre-temps (mesa) n'y était pas."""
        import json
        self.avec_rapport()
        self.lancer("compter", NC_TEST_DEPOTS="zsh 5-1 -> 5-2\n")
        (self.home / "db").write_text("bash 5.2-1\nmesa 1:26.0-1\nzsh 5-1\nzen-browser-bin 1.0-1\n")
        (self.home / "db-aur").write_text("zen-browser-bin\n")
        (self.home / "db-apres").write_text("bash 5.2-1\nmesa 1:26.1-1\nzsh 5-3\nzen-browser-bin 1.1-1\n")
        (self.home / "qu").write_text("zsh 5-1 -> 5-3\nmesa 1:26.0-1 -> 1:26.1-1\n")
        (self.home / "qu-apres").write_text("")
        r = self.lancer("terminal")
        self.assertEqual(r.returncode, 0, r.stderr)
        maj = json.loads((self.home / ".cache/nc/paquets-maj.json").read_text())
        self.assertEqual([(p["source"], p["nom"], p["avant"], p["apres"], p["important"]) for p in maj["paquets"]],
                         [("depot", "mesa", "1:26.0-1", "1:26.1-1", True), ("depot", "zsh", "5-1", "5-3", False),
                          ("aur", "zen-browser-bin", "1.0-1", "1.1-1", False)])
        self.assertEqual((maj["total"], maj["en_attente"], maj["echec"]), (3, 0, 0))
        d = self.rapport()
        self.assertIsNotNone(d, "rapport écrit")
        self.assertEqual(d["details"], ["★ mesa 1:26.0-1 → 1:26.1-1", "zsh 5-1 → 5-3", "zen-browser-bin 1.0-1 → 1.1-1 (aur)"])
        self.assertEqual(d["nombre"], 3)
        self.assertNotIn("5-2", json.dumps(d), "jamais la version de la liste d'attente d'avant")

    def apt(self):
        """Un PATH de Debian sans le pacman de la machine : apt, dpkg-query et sudo factices, les outils de base.
        firefox-esr est retenu (« kept back ») : apt list le montre, full-upgrade le garde et finit en code 0."""
        nu = self.home / "nu"; nu.mkdir()
        for outil in ("sh", "bash", "env", "python3", "sed", "awk", "grep", "head", "tail", "tr", "mkdir", "rm", "mv", "cat",
                      "wc", "sort", "date", "basename", "dirname", "sleep", "printf", "cp", "touch", "tee", "cmp", "find", "mktemp", "flock",
                      "stat", "cut", "setsid", "readlink", "timeout", "uniq", "ls"):
            vrai = shutil.which(outil)
            if vrai:
                (nu / outil).symlink_to(vrai)
        faux = {"apt": """#!/bin/sh
echo "apt $*" >> "$HOME/appels"
case "$1" in
  list) echo "Listing..."; echo "firefox-esr/stable-security 128.4.0esr-1~deb13u1 amd64 [upgradable from: 128.3.1esr-1~deb13u1]"
        [ -e "$HOME/fait" ] || echo "zsh/stable 5.9-8 amd64 [upgradable from: 5.9-7]"; exit 0 ;;
  update) exit 0 ;;
  full-upgrade) echo "The following packages have been kept back:"; echo "  firefox-esr"
        echo "1 upgraded, 0 newly installed, 0 to remove and 1 not upgraded."
        [ -e "$HOME/dpkg-apres" ] && mv "$HOME/dpkg-apres" "$HOME/dpkg"; touch "$HOME/fait"; exit 0 ;;
esac
exit 0
""", "dpkg-query": '#!/bin/sh\ncat "$HOME/dpkg"\n', "sudo": FAUX_SUDO, "notify-send": FAUX_NOTIFY}
        for nom, code in faux.items():
            (nu / nom).write_text(code); (nu / nom).chmod(0o755)
        (self.home / "dpkg").write_text("zsh\t5.9-7\tii \nfirefox-esr\t128.3.1esr-1~deb13u1\tii \nvieux\t1.0\trc \n")
        (self.home / "dpkg-apres").write_text("zsh\t5.9-8\tii \nfirefox-esr\t128.3.1esr-1~deb13u1\tii \nvieux\t1.0\trc \n")
        # Listes d'apt fraîches (N1 : sinon « dépôts non synchronisés »)
        self.etat_apt = self.home / "apt"; (self.etat_apt / "lists/partial").mkdir(parents=True)
        (self.etat_apt / "lists/deb.debian.org_debian_dists_trixie_InRelease").write_text("")
        return str(nu)

    def test_apt_paquet_retenu_jamais_compte_comme_installe(self):
        """Revue B1 R1 : apt « kept back » (code 0) donnait « 2 mis à jour » ; c'est 1, et 1 resté en attente."""
        import json
        nu = self.apt()
        self.avec_rapport()
        env = dict(PATH=nu, NC_APT_ETAT=str(self.etat_apt))
        self.assertEqual(self.lancer("compter", **env).returncode, 0)
        self.assertEqual(self.cache.read_text().splitlines()[0], "2")
        r = self.lancer("terminal", **env)
        self.assertIn("apt full-upgrade", self.appels())
        self.assertIn("1 mise(s) à jour encore en attente.", r.stdout)
        d = self.rapport()
        self.assertIsNotNone(d, "rapport écrit")
        self.assertEqual((d["details"], d["nombre"], d["en_attente"]), (["zsh 5.9-7 → 5.9-8"], 1, 1))
        self.assertTrue(d["resume"].startswith("1 paquet(s) mis à jour."), d["resume"])
        self.assertIn("1 resté(s) en attente : firefox-esr.", d["resume"])
        self.assertNotIn("vieux", json.dumps(d), "un paquet dont il ne reste que la configuration (rc) n'est pas installé")

    def test_debian_depots_jamais_synchronises_pas_a_jour(self):
        """Revue B1 N1 : apt list lit des listes que personne ne rafraîchit (Debian minimale) : faux « à jour »."""
        import json, time
        nu = self.apt()
        (self.home / "fait").touch()          # seul firefox-esr attend…
        (self.home / "nu/apt").write_text('#!/bin/sh\necho "Listing..."\nexit 0\n')     # … ou rien du tout
        vieux = time.time() - 3 * 86400 - 600
        for p in [*self.etat_apt.rglob("*"), self.etat_apt / "lists"]:
            os.utime(p, (vieux, vieux))
        r = self.lancer("verifier", PATH=nu, NC_APT_ETAT=str(self.etat_apt))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads((self.home / ".cache/nc/paquets.json").read_text())["non_synchro_jours"], 3)
        titre, corps = self.notifs(1)[-1]
        self.assertEqual(titre, "Dépôts non synchronisés", "une vieille liste vide n'est pas « Système à jour »")
        self.assertIn("depuis 3 j", corps)
        self.assertIn("depuis 3 j", r.stderr)
        # Synchronisées il y a une heure : à jour
        frais = time.time() - 3600
        os.utime(self.etat_apt / "lists/deb.debian.org_debian_dists_trixie_InRelease", (frais, frais))
        self.lancer("verifier", PATH=nu, NC_APT_ETAT=str(self.etat_apt))
        self.assertIsNone(json.loads((self.home / ".cache/nc/paquets.json").read_text())["non_synchro_jours"])
        self.assertEqual(self.notifs(2)[-1][0], "Système à jour")

    def test_echec_de_la_mise_a_jour_dit_et_rapporte(self):
        """Revue B1 R3 : pacman -Su en échec, et l'on voyait « Terminé » et « ✅ » sur Telegram ; Flatpak en échec après
        pacman : aucun rapport."""
        import json
        self.avec_rapport()
        alertes = self.home / ".local/bin/nc-alertes"
        alertes.write_text('#!/bin/sh\necho "nc-alertes $*" >> "$HOME/appels"\n'); alertes.chmod(0o755)
        (self.home / "db").write_text("linux 6.1-1\n")
        (self.home / "db-apres").write_text("linux 6.2-1\n")
        (self.home / "qu").write_text("linux 6.1-1 -> 6.2-1\n"); (self.home / "qu-apres").write_text("")
        r = self.lancer("terminal", NC_TEST_SU_ECHEC="1")
        self.assertIn("La mise à jour a échoué (code 3).", r.stdout)
        self.assertNotIn("Terminé", r.stdout)
        self.assertIn("nc-alertes maj 0 echec 3", self.appels())
        self.assertIn("checkupdates", self.appels(), "en échec : le compte complet")
        d = self.rapport()
        self.assertIsNotNone(d, "le noyau a changé : un rapport, même si la mise à jour a échoué ensuite")
        self.assertEqual((d["details"], d["echec"]), (["★ linux 6.1-1 → 6.2-1"], 3))
        self.assertIn("La mise à jour a échoué (code 3)", d["resume"])
        # pacman réussit, Flatpak échoue : le rapport de ce que pacman a fait, et l'échec dit
        (self.home / ".cache/nc/rapports/systeme.json").unlink()
        (self.home / "appels").unlink()
        (self.home / "db-apres").write_text("linux 6.3-1\n")
        (self.home / "qu").write_text("linux 6.2-1 -> 6.3-1\n"); (self.home / "qu-apres").write_text("")
        r = self.lancer("terminal", NC_TEST_FLATPAK_ECHEC="1")
        self.assertIn("La mise à jour a échoué (code 1).", r.stdout)
        self.assertIn("nc-alertes maj 0 echec 1", self.appels())
        d = self.rapport()
        self.assertIsNotNone(d, "Flatpak en échec après pacman : le rapport quand même")
        self.assertEqual(d["details"], ["★ linux 6.2-1 → 6.3-1"])
        # Réussie : « Terminé », et l'alerte de fin habituelle
        (self.home / "appels").unlink()
        r = self.lancer("terminal", NC_TEST_LOCAL="")
        self.assertIn("Terminé.", r.stdout)
        self.assertNotIn("échoué", r.stdout)
        self.assertIn("nc-alertes maj 0", self.appels())

    # ── Comptes simultanés, nouvel essai (C1, C2) ──
    def alimentation(self):
        alim = self.home / "alim"
        (alim / "AC").mkdir(parents=True)
        (alim / "AC/type").write_text("Mains\n"); (alim / "AC/online").write_text("1\n")
        return dict(NC_POWER_SUPPLY=str(alim), NC_METERED="u 4")

    def test_deux_comptes_en_meme_temps(self):
        """Revue B1 C1 : le minuteur et un clic sur « Chercher » dans la même seconde : checkupdates verrouille sa copie
        des dépôts, le second échouait (faux « incomplet »)."""
        import json, os, time
        (self.home / "bin/checkupdates").write_text("""#!/bin/sh
L="$HOME/checkup.lck"
if ! (set -o noclobber; : > "$L") 2>/dev/null; then echo "==> ERROR: Cannot fetch updates" >&2; exit 1; fi
sleep 1; rm -f "$L"; printf 'zsh 5-1 -> 5-2\\nlinux 6.1-1 -> 6.2-1\\n'; exit 0
""")
        env = self.alimentation()
        self.lancer("compter", **env)
        vieux = time.time() - 2 * 3600
        os.utime(self.cache, (vieux, vieux))
        base = dict(HOME=str(self.home), PATH=self.chemin, NC_LANGUE="fr", **env)
        minuteur = subprocess.Popen([str(BIN / "nc-paquets"), "compter", "auto"], env=base, stdin=subprocess.DEVNULL,
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(0.3)
        r = self.lancer("verifier", **env)
        minuteur.wait(timeout=30)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads((self.home / ".cache/nc/paquets.json").read_text())["incomplet"], [])
        self.assertFalse((self.home / ".cache/nc/paquets-erreur").exists())
        self.assertEqual(self.cache.read_text(), "2\nlinux\nzsh\n")
        self.assertFalse([p.name for p in (self.home / ".cache/nc").iterdir() if (".tmp" in p.name or p.name.startswith(".paquets.")) and not p.name.endswith(".verrou")],
                         "aucun temporaire laissé")

    def test_une_seule_mise_a_jour_a_la_fois(self):
        import fcntl
        (self.home / ".cache/nc").mkdir(parents=True)
        with open(self.home / ".cache/nc/.paquets-maj.verrou", "w") as v:
            fcntl.flock(v, fcntl.LOCK_EX)
            r = self.lancer("terminal", NC_TEST_DEPOTS="zsh 5-1 -> 5-2\n")
        self.assertIn("déjà en cours", r.stdout)
        self.assertFalse([a for a in self.appels() if a.startswith("paru -S")], "la seconde fenêtre ne met rien à jour")

    def test_nouvel_essai_15_min_apres_un_echec(self):
        """Revue B1 C2 : après un échec réseau, $fichier redaté : le nouvel essai attendait la période entière (12 h)."""
        import time
        env = self.alimentation()
        (self.home / ".config/nc/reglages.conf").write_text("LANGUE=fr\nMAJ_FREQUENCE=jour\n")
        self.lancer("compter", NC_TEST_DEPOTS="zsh 5-1 -> 5-2\n", **env)
        vieux = time.time() - 25 * 3600
        os.utime(self.cache, (vieux, vieux))
        ck = self.home / "bin/checkupdates"
        ck.write_text('#!/bin/sh\necho "checkupdates" >> "$HOME/appels"\necho "==> ERROR: Cannot fetch updates" >&2\nexit 1\n')
        # Lancé par systemd (INVOCATION_ID) : un minuteur d'un seul coup dans 15 min
        self.lancer("compter", "auto", INVOCATION_ID="x", **env)
        erreur = self.home / ".cache/nc/paquets-erreur"
        self.assertEqual(erreur.read_text().split("\t")[1:], ["depot", "1\n"])
        self.assertTrue([a for a in self.appels() if a.startswith("systemd-run --user") and "--on-active=15min" in a
                         and "--unit=nc-paquets-reessai-1 " in a and "-p ConditionACPower=true" in a
                         and a.endswith("compter auto")], self.appels())
        ck.write_text(FAUX_CHECKUPDATES)
        (self.home / "appels").unlink()
        ecrire = lambda il_y_a, n: erreur.write_text(f"{int(time.time() - il_y_a)}\tdepot\t{n}\n")
        self.lancer("compter", "auto", NC_TEST_DEPOTS="zsh 5-1 -> 5-2\n", **env)
        self.assertEqual(self.appels(), [], "juste après l'échec : pas encore")
        ecrire(16 * 60, 1)
        self.lancer("compter", "auto", NC_TEST_DEPOTS="zsh 5-1 -> 5-2\n", **env)
        self.assertIn("checkupdates", self.appels(), "15 min après l'échec : nouvel essai (et non 24 h)")
        self.assertFalse(erreur.exists(), "réussi : l'échec est oublié")
        # Plafond : le délai double à chaque échec de suite (3e : 60 min)
        (self.home / "appels").unlink()
        os.utime(self.cache, None)
        ecrire(20 * 60, 3)
        self.lancer("compter", "auto", NC_TEST_DEPOTS="zsh 5-1 -> 5-2\n", **env)
        self.assertEqual(self.appels(), [], "3e échec de suite : pas avant 60 min")
        ecrire(61 * 60, 3)
        self.lancer("compter", "auto", NC_TEST_DEPOTS="zsh 5-1 -> 5-2\n", **env)
        self.assertIn("checkupdates", self.appels())
        # Au-delà de 30 min, le passage de chaque heure suffit : pas de minuteur en plus
        (self.home / "appels").unlink()
        ck.write_text('#!/bin/sh\necho "checkupdates" >> "$HOME/appels"\nexit 1\n')
        ecrire(61 * 60, 2)
        self.lancer("compter", "auto", INVOCATION_ID="x", **env)
        self.assertEqual(erreur.read_text().split("\t")[2], "3\n")
        self.assertFalse([a for a in self.appels() if a.startswith("systemd-run")])
        # 2e échec de suite : 30 min, sous un autre nom (systemd refuserait de recréer l'unité qui tourne)
        (self.home / "appels").unlink()
        ecrire(16 * 60, 1)
        self.lancer("compter", "auto", INVOCATION_ID="x", **env)
        self.assertTrue([a for a in self.appels() if "--unit=nc-paquets-reessai-2 " in a and "--on-active=30min" in a], self.appels())

    def test_nouvel_essai_respecte_batterie_et_connexion_limitee(self):
        """Contre-relecture P3-P4 : les nouveaux essais passaient outre la batterie (3 h) et la connexion limitée (12 h)."""
        import time
        alim = self.home / "alim"
        for nom, fichiers in (("AC", {"type": "Mains", "online": "0"}), ("BAT0", {"type": "Battery"})):
            (alim / nom).mkdir(parents=True)
            for f, v in fichiers.items():
                (alim / nom / f).write_text(v + "\n")
        env = dict(NC_POWER_SUPPLY=str(alim), NC_METERED="u 4")
        self.lancer("compter", NC_TEST_DEPOTS="zsh 5-1 -> 5-2\n", **env)
        erreur = self.home / ".cache/nc/paquets-erreur"
        (self.home / "appels").unlink()
        erreur.write_text(f"{int(time.time() - 20 * 60)}\tdepot\t1\n")
        self.lancer("compter", "auto", NC_TEST_DEPOTS="zsh 5-1 -> 5-2\n", **env)
        self.assertEqual(self.appels(), [], "sur batterie : pas de nouvel essai avant 3 h")
        erreur.write_text(f"{int(time.time() - 181 * 60)}\tdepot\t1\n")
        os.utime(self.cache, None)
        self.lancer("compter", "auto", NC_TEST_DEPOTS="zsh 5-1 -> 5-2\n", **env)
        self.assertIn("checkupdates", self.appels())
        # Connexion limitée, sous systemd : aucun minuteur de 15 min
        (alim / "AC/online").write_text("1\n")
        (self.home / "appels").unlink()
        (self.home / "bin/checkupdates").write_text('#!/bin/sh\necho "checkupdates" >> "$HOME/appels"\nexit 1\n')
        erreur.write_text(f"{int(time.time() - 13 * 3600)}\tdepot\t1\n")
        self.lancer("compter", "auto", INVOCATION_ID="x", NC_POWER_SUPPLY=str(alim), NC_METERED="u 1")
        self.assertIn("checkupdates", self.appels())
        self.assertFalse([a for a in self.appels() if a.startswith("systemd-run")], "connexion limitée : 12 h, le minuteur horaire suffit")

    def test_notification_survit_a_la_fin_du_service(self):
        """Contre-relecture : nc-paquets.service (Type=oneshot) tue tout son groupe à la fin du compte ; la notification
        qui attend le clic part dans son propre scope."""
        service = (REPO / "home/.config/systemd/user/nc-paquets.service").read_text()
        self.assertIn("Type=oneshot", service)
        self.assertNotIn("KillMode=", service, "KillMode par défaut (control-group) : le scope est nécessaire")
        self.lancer("compter", NC_TEST_DEPOTS="zsh 5-1 -> 5-2\n", INVOCATION_ID="x")
        import time
        fin = time.time() + 3                     # la notification part en arrière-plan
        while time.time() < fin and not [a for a in self.appels() if a.startswith("systemd-run")]:
            time.sleep(0.05)
        scope = [a for a in self.appels() if a.startswith("systemd-run --user --scope")]
        self.assertTrue(scope and "notifier-attendre 1 mise à jour" in scope[0], self.appels())
        self.assertEqual(self.notifs(1, 0.5), [], "rien d'autre ne l'affiche (le faux systemd-run ne lance rien)")
        # Hors systemd : affichée tout de suite
        self.lancer("verifier", NC_TEST_DEPOTS="zsh 5-1 -> 5-2\nmesa 1-1 -> 1-2\n")
        self.assertEqual(self.notifs(1)[-1][0], "2 mises à jour")

    # ── Instantané (S1, S2, S3) ──
    def test_pas_d_instantane_sans_rien_a_mettre_a_jour(self):
        """Revue B1 S1 : un instantané à chaque ouverture, même sans rien à mettre à jour (et seuls 3 sont gardés)."""
        r = self.lancer("terminal", NC_TEST_FS="btrfs", NC_TEST_LOCAL="")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertFalse([a for a in self.appels() if a.startswith("btrfs")], self.appels())
        self.assertNotIn("paru -Syu", self.appels())
        self.assertIn("rien à mettre à jour", r.stdout)

    def test_instantane_d_avant_la_derniere_reussite_garde(self):
        for j in range(1, 6):
            (self.snaps / f"nc-avant-maj-2026-01-0{j}_00-00-00").mkdir()
        etat = self.home / ".local/state/nc"
        etat.mkdir(parents=True)
        (etat / "instantane-reussi").write_text("nc-avant-maj-2026-01-01_00-00-00\n")
        r = self.lancer("terminal", NC_TEST_FS="btrfs", NC_TEST_DEPOTS="zsh 5-1 -> 5-2\n")
        supprimes = [a.rsplit("/", 1)[-1] for a in self.appels() if a.startswith("btrfs subvolume delete")]
        self.assertEqual(supprimes, ["nc-avant-maj-2026-01-02_00-00-00"], "les 3 plus récents, et celui d'avant la dernière réussite")
        pris = next(a for a in self.appels() if a.startswith("btrfs subvolume snapshot")).rsplit("/", 1)[-1]
        self.assertEqual((etat / "instantane-reussi").read_text().strip(), pris, "réussie : son instantané devient celui à garder")

    def test_instantane_impossible_jamais_en_silence(self):
        """Revue B1 S2 : la création de /.snapshots qui échouait passait sans un mot."""
        env = dict(NC_TEST_FS="btrfs", NC_TEST_DEPOTS="zsh 5-1 -> 5-2\n", NC_SNAPSHOTS=str(self.home / "absent"), NC_TEST_BTRFS_ECHEC="1")
        r = self.lancer("terminal", **env)
        self.assertIn("Instantané impossible : la mise à jour continue sans.", r.stdout)
        self.assertIn("paru -Syu", self.appels())
        # MAJ_INSTANTANE=oui : la question ; sans « o », rien n'est mis à jour
        (self.home / ".config/nc/reglages.conf").write_text("LANGUE=fr\nMAJ_INSTANTANE=oui\n")
        (self.home / "appels").unlink()
        r = self.lancer("terminal", **env)
        self.assertIn("Continuer la mise à jour sans instantané ?", r.stdout)
        self.assertIn("Mise à jour annulée", r.stdout)
        self.assertNotIn("paru -Syu", self.appels())
        self.assertNotIn("flatpak update", self.appels())
        (self.home / "appels").unlink()
        r = self.lancer("terminal", entree="o\n\n", **env)
        self.assertIn("paru -Syu", self.appels(), "« o » : la mise à jour continue")

    def test_crochets_timeshift_autosnap_et_80snapper(self):
        """Revue B1 S3 : timeshift-autosnap (Arch) et 80snapper (Debian) n'étaient pas reconnus : instantané en double."""
        crochet = self.home / "00-timeshift-autosnap.hook"; crochet.write_text("")
        conf = self.home / "timeshift.json"; conf.write_text("{}")
        r = self.lancer("terminal", NC_TEST_FS="btrfs", NC_TEST_DEPOTS="zsh 5-1 -> 5-2\n", NC_CROCHETS_TIMESHIFT=str(crochet),
                        NC_TIMESHIFT_CONF=str(conf))
        self.assertIn("fait par timeshift-autosnap", r.stdout)
        self.assertFalse([a for a in self.appels() if a.startswith("btrfs")])
        source = (BIN / "nc-paquets").read_text()
        for chemin in ("/etc/apt/apt.conf.d/80snapper", "/usr/share/libalpm/hooks/*timeshift-autosnap*"):
            self.assertIn(chemin, source)

    # ── Contre-relecture de B1 ──
    def test_arch_non_a_l_instantane_ne_synchronise_rien(self):
        """P2-P1 : -Sy, puis un « non » à l'instantané : base synchronisée sans mise à jour (mise à jour partielle)."""
        alertes = self.home / ".local/bin/nc-alertes"; alertes.parent.mkdir(parents=True)
        alertes.write_text('#!/bin/sh\necho "nc-alertes $*" >> "$HOME/appels"\n'); alertes.chmod(0o755)
        (self.home / ".config/nc/reglages.conf").write_text("LANGUE=fr\nMAJ_INSTANTANE=oui\n")
        r = self.lancer("terminal", NC_TEST_FS="btrfs", NC_TEST_DEPOTS="linux 6.1-1 -> 6.2-1\n",
                        NC_SNAPSHOTS=str(self.home / "absent"), NC_TEST_BTRFS_ECHEC="1", entree="n\n\n")
        self.assertFalse([a for a in self.appels() if a.startswith(("pacman -S", "paru -S"))], "la vraie base jamais touchée")
        self.assertIn("checkupdates", self.appels(), "décidé sur une copie des dépôts")
        self.assertIn("Mise à jour annulée : rien n'a été installé.", r.stdout)
        self.assertNotIn("échoué", r.stdout)
        self.assertFalse([a for a in self.appels() if a.startswith("nc-alertes")], "annulée devant l'écran : rien sur Telegram")

    def test_arch_sans_checkupdates_instantane_par_prudence(self):
        """P2-P1 : sans pacman-contrib (checkupdates), on ne sait pas ce qui attend : l'instantané, puis -Syu."""
        (self.home / "bin/checkupdates").unlink()
        r = self.lancer("terminal", NC_TEST_FS="btrfs")
        a = self.appels()
        prises = [x for x in a if x.startswith("btrfs subvolume snapshot")]
        self.assertTrue(prises, a)
        self.assertLess(a.index(prises[0]), a.index("paru -Syu"))
        self.assertFalse([x for x in a if x in ("paru -Sy", "paru -Su")])

    def test_reponse_non_annulee_pas_echouee(self):
        """P3-P7 : « n » à pacman (code 1, sans erreur, rien d'installé) : « annulée », pas « a échoué », pas de ❌."""
        alertes = self.home / ".local/bin/nc-alertes"; alertes.parent.mkdir(parents=True)
        alertes.write_text('#!/bin/sh\necho "nc-alertes $*" >> "$HOME/appels"\n'); alertes.chmod(0o755)
        (self.home / "db").write_text("linux 6.1-1\n"); (self.home / "db-apres").write_text("linux 6.2-1\n")
        r = self.lancer("terminal", NC_TEST_DEPOTS="linux 6.1-1 -> 6.2-1\n", NC_TEST_NON="1")
        self.assertIn("paru -Syu", self.appels())
        self.assertIn("Mise à jour annulée", r.stdout)
        self.assertNotIn("échoué", r.stdout)
        self.assertNotIn("Terminé", r.stdout)
        self.assertFalse([a for a in self.appels() if a.startswith("nc-alertes")])
        # Une vraie erreur (réseau), rien d'installé : un échec, dit comme tel
        (self.home / "appels").unlink()
        r = self.lancer("terminal", NC_TEST_DEPOTS="linux 6.1-1 -> 6.2-1\n", NC_TEST_MAJ_ECHEC="1")
        self.assertIn("La mise à jour a échoué (code 1).", r.stdout)
        self.assertIn("nc-alertes maj 1 echec 1", self.appels())

    def test_flatpak_seul_pas_un_echec(self):
        """P3-P6 : sans gestionnaire reconnu (Silverblue), chaque mise à jour Flatpak finissait en « échec (code 1) »."""
        r = self.lancer("terminal", PATH=f"{self.home / 'fp'}:{self.home / 'sys'}", **self.seul("fp", "flatpak", "notify-send"))
        self.assertIn("flatpak update", self.appels())
        self.assertIn("seul Flatpak est mis à jour", r.stdout)
        self.assertNotIn("échoué", r.stdout)
        self.assertIn("Terminé.", r.stdout)

    def seul(self, dossier, *faux):
        """Un dossier avec seulement ces faux-là (pas de pacman) ; rend un dict vide (pour **)."""
        d = self.home / dossier; d.mkdir(exist_ok=True)
        for nom in faux:
            (d / nom).symlink_to(self.home / "bin" / nom)
        return {}

    def test_dnf_synchronise_avant_de_decider_et_noyaux(self):
        """P2-P2 : l'instantané se décidait sur un vieux compte (0) alors qu'un noyau venait de sortir. P3-P8 : avec
        plusieurs noyaux installés, « avant » était le plus ancien, pas le précédent."""
        import json
        d = self.home / "dnfbin"; d.mkdir()
        faux = {"dnf": """#!/bin/sh
echo "dnf $*" >> "$HOME/appels"
case "$*" in
  *makecache*) touch "$HOME/synchro"; exit 0 ;;
  *check-update*) [ -e "$HOME/fait" ] && exit 0; [ -e "$HOME/synchro" ] || exit 0
    echo "kernel-core.x86_64  6.10-1  updates"; exit 100 ;;
  upgrade*) touch "$HOME/fait"; exit 0 ;;
esac
exit 0
""", "rpm": """#!/bin/sh
if [ -e "$HOME/fait" ]; then printf 'kernel-core\\t6.9-1\\nkernel-core\\t6.10-1\\nbash\\t5.2-1\\n'
else printf 'kernel-core\\t6.1-1\\nkernel-core\\t6.9-1\\nbash\\t5.2-1\\n'; fi
"""}
        for nom, code in faux.items():
            (d / nom).write_text(code); (d / nom).chmod(0o755)
        self.seul("dnfbin", "sudo", "btrfs", "findmnt", "notify-send")
        (self.home / ".cache/nc").mkdir(parents=True)
        (self.home / ".cache/nc/paquets.json").write_text(json.dumps({"total": 0, "sources": {"depot": 0, "aur": 0, "flatpak": 0},
                                                                      "incomplet": [], "paquets": []}))
        self.lancer("terminal", PATH=f"{d}:{self.home / 'sys'}", NC_TEST_FS="btrfs")
        a = self.appels()
        prise = next((x for x in a if x.startswith("btrfs subvolume snapshot")), None)
        self.assertIsNotNone(prise, a)
        self.assertLess(a.index("dnf makecache --refresh"), a.index(prise), "synchronisé d'abord")
        self.assertLess(a.index(prise), a.index("dnf upgrade"))
        maj = json.loads((self.home / ".cache/nc/paquets-maj.json").read_text())
        self.assertEqual([(p["nom"], p["avant"], p["apres"]) for p in maj["paquets"]], [("kernel-core", "6.9-1", "6.10-1")])

    def test_apt_update_ecrit_un_repere(self):
        """P2-P3 : apt garde la date Last-Modified du serveur ; une stable à jour (« Hit ») paraissait non synchronisée."""
        import json, time
        nu = self.apt()
        vieux = time.time() - 20 * 86400
        for p in [*self.etat_apt.rglob("*"), self.etat_apt / "lists"]:
            os.utime(p, (vieux, vieux))
        (self.home / "fait").touch()
        (self.home / "nu/apt").write_text('#!/bin/sh\necho "apt $*" >> "$HOME/appels"\n'
                                          'case "$1" in update) echo "Hit:1 http://deb.debian.org/debian trixie InRelease";; list) echo "Listing...";; esac\nexit 0\n')
        env = dict(PATH=nu, NC_APT_ETAT=str(self.etat_apt))
        self.lancer("verifier", **env)
        self.assertEqual(json.loads((self.home / ".cache/nc/paquets.json").read_text())["non_synchro_jours"], 20)
        self.lancer("terminal", **env)
        self.assertTrue((self.home / ".local/state/nc/depots-synchro").exists())
        self.assertIsNone(json.loads((self.home / ".cache/nc/paquets.json").read_text())["non_synchro_jours"],
                          "« apt update » réussi par nc-paquets : synchronisé, même si les listes gardent leur vieille date")


@unittest.skipUnless(shutil.which("qs"), "Quickshell requis")
class LigneMisesAJour(unittest.TestCase):
    def test_page_systeme_passe_de_3_a_0(self):
        with tempfile.TemporaryDirectory(prefix="nc-paquets-qml-") as d:
            root = Path(d)
            (root / "run").mkdir(mode=0o700)
            (root / ".cache/nc").mkdir(parents=True)
            (root / ".cache/nc/paquets").write_text("3\navahi\nbaloo\nzsh\n")
            for nom in ("Systeme.qml", "Ligne.qml", "Module.qml", "Texte.qml", "Ico.qml", "Defilement.qml", "Couleurs.qml", "ModeGraphique.qml"):
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
                ("singleton " if n in ("Couleurs", "Reglages", "Etat", "ModeGraphique") else "") + n + " 1.0 " + n + ".qml"
                for n in ("Systeme", "Ligne", "Module", "Texte", "Ico", "Defilement", "Couleurs", "Reglages", "Etat", "ModeGraphique")))
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
                    Process { id: erreur; command: ["sh", "-c", "echo '1 depot' > \\"$HOME/.cache/nc/paquets-erreur\\""] }
                    Timer { interval: 100; running: true; repeat: true; onTriggered: {
                        if (etape === 0) { var c = Qt.createComponent("Systeme.qml"); verifier(c.status === Component.Ready, c.errorString()); page = c.createObject(w.contentItem, { width: 400, height: 580 }); verifier(page !== null, "page absente"); etape++ }
                        else if (etape === 1) { ligne = trouver(page, "nc-paquets"); verifier(ligne !== null, "ligne absente"); if (!ligne.visible) return
                            verifier(ligne.titre === "3 system updates", "titre initial : " + ligne.titre); verifier(ligne.actif, "ligne inactive"); recompte.running = true; etape++ }
                        else if (etape === 2) { if (ligne.titre !== "System up to date") return
                            verifier(ligne.n === 0 && !ligne.actif, "état après recompte"); verifier(ligne.sous === "Checked every hour", "sous-titre (MAJ_FREQUENCE) : " + ligne.sous)
                            page.visible = false; page.visible = true; etape++ }
                        else if (etape === 3) { verifier(ligne.titre === "System up to date", "titre après réaffichage : " + ligne.titre); erreur.running = true; etape++ }
                        // PKG-03 : la vérification n'aboutit pas (cache à 0 gardé) : jamais « à jour »
                        else if (etape === 4) { if (ligne.titre !== "Could not check for updates") return; Qt.quit() } } }
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

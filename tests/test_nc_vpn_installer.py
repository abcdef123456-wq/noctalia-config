"""Installer un client VPN depuis la fenêtre (V6c) : le script fixe home/.local/libexec/nc-vpn-installer et les commandes de nc-vpn qui
l'utilisent (docs/vpn-installation.md). Tout est isolé : HOME, XDG_*, TMPDIR dans un dossier temporaire ; PATH = un petit dossier de liens
vers quelques outils sûrs + de FAUX sudo, curl, gpg, pacman, apt-get, dnf, rpm, dpkg, systemctl, sha256sum, uname, usermod, zypper, flatpak,
kitty, qui notent SEULEMENT leurs arguments (curl dépose un fichier de test là où on lui dit, sudo copie le fichier source de « install » pour
qu'on puisse lire ce que le script écrirait). Aucune installation, aucun vrai sudo."""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

from tests._vpn_faux import BaseVpn

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "home/.local/libexec/nc-vpn-installer"

EMPREINTE = "A1198702FC3E0A09A9AE5B75D5A1D4F266DE8DDF"
AUTRE = "0123456789ABCDEF0123456789ABCDEF01234567"
SHA_PROTON = "c8a9fffb4ebdd63db08ce7f11c9b0ac394064ae6a210feb9ab63a0f7d8d060a7"
SORTIE_GPG_BONNE = "tru::1:1:1:0:3:1:5\npub:-:4096:1:D5A1D4F266DE8DDF:1477548074:::-:::scESC::::::23::0:\nfpr:::::::::" + EMPREINTE + ":\n" \
                   "uid:-::::1477568799::AB::Mullvad (code signing) <admin@example.org>::::::::::0:\nsub:-:4096:1:AAAA:1:::::s::::::23:\n" \
                   "fpr:::::::::277AE267A409C9C19D5B2B63C187D22C089EF64E:\n"
OUTILS_SURS = ("bash", "sed", "tail", "tr", "awk", "mktemp", "chmod", "rm", "cut", "cat", "head", "dirname", "env", "sh", "grep", "mkdir",
               "install", "ls", "printf", "python3", "basename", "cp", "cmp", "rmdir")

OS = {
    "arch": 'NAME="Arch Linux"\nID=arch\nBUILD_ID=rolling\n',
    "debian13": 'PRETTY_NAME="Debian GNU/Linux 13 (trixie)"\nVERSION_ID="13"\nID=debian\n',
    "debian12": 'VERSION_ID="12"\nID=debian\n',
    "fedora44": 'NAME="Fedora Linux"\nVERSION_ID=44\nID=fedora\n',
    "fedora40": 'NAME="Fedora Linux"\nVERSION_ID=40\nID=fedora\n',
    "tumbleweed": 'NAME="openSUSE Tumbleweed"\nID="opensuse-tumbleweed"\nID_LIKE="opensuse suse"\nVERSION_ID="20261001"\n',
    "leap": 'NAME="openSUSE Leap"\nID="opensuse-leap"\nID_LIKE="suse opensuse"\nVERSION_ID="16.0"\n',
    "ubuntu": 'ID=ubuntu\nID_LIKE=debian\nVERSION_ID="26.04"\n',
    "gentoo": 'ID=gentoo\nVERSION_ID="2.18"\n',
    "manjaro": 'ID=manjaro\nID_LIKE=arch\n',
    "cachyos": 'ID=cachyos\nID_LIKE=arch\n',
    "piege": 'ID=debian\nVERSION_ID="13"; touch PIEGE\nID_LIKE=$(touch PIEGE2)\n',
}

FAUX = r'''#!/bin/sh
# faux outil : note ses arguments (un par ligne, séparés par un caractère de contrôle) et ne fait rien d'autre
nom="$(basename "$0")"
printf '%s' "$nom" >> "$FAUX_DIR/appels"
for a in "$@"; do printf '\037%s' "$a" >> "$FAUX_DIR/appels"; done
printf '\n' >> "$FAUX_DIR/appels"
case "$nom" in
  curl)   # dépose le fichier de test demandé par -o
    out=""; url=""
    while [ $# -gt 0 ]; do case "$1" in -o) out="$2"; shift ;; https://*) url="$1" ;; esac; shift; done
    case "$url" in *.deb) cp "$FAUX_DIR/paquet.deb" "$out" ;; *) cp "$FAUX_DIR/cle.asc" "$out" ;; esac ;;
  gpg)    case " $* " in *" --show-keys "*) cat "$FAUX_DIR/gpg.out" ;; *" --export "*) cat "$FAUX_DIR/export.asc" ;; esac ;;
  sha256sum) printf '%s  %s\n' "$(cat "$FAUX_DIR/sha")" "$2" ;;
  uname)  echo "${FAUX_UNAME:-x86_64}" ;;
  sudo)   # seulement dans le dossier de test : « install » copie, rm et rmdir retirent ; ailleurs rien ne se passe
    case "$1" in
      install)
        dest=""; src=""
        for a in "$@"; do src="$dest"; dest="$a"; done
        if [ "$2" = -d ]; then
          case "$dest" in "$FAUX_DIR"/*) mkdir -p "$dest" ;; esac
        else
          case "$dest" in "$FAUX_DIR"/*) cp "$src" "$dest" ;; esac
          mkdir -p "$FAUX_DIR/copies"; cp "$src" "$FAUX_DIR/copies/$(basename "$dest")" 2>/dev/null || true
        fi ;;
      rm) for a in "$@"; do case "$a" in "$FAUX_DIR"/*) rm -f "$a" ;; esac; done ;;
      rmdir) for a in "$@"; do case "$a" in "$FAUX_DIR"/*) rmdir "$a" 2>/dev/null || true ;; esac; done ;;
    esac ;;
esac
# FAUX_SUDO_ECHEC=OUTIL : « sudo OUTIL … » échoue (une base pacman en retard, par exemple)
if [ "$nom" = sudo ] && [ -n "${FAUX_SUDO_ECHEC:-}" ] && [ "$1" = "$FAUX_SUDO_ECHEC" ]; then exit 1; fi
exit 0
'''


class Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="nc-inst-")
        self.addCleanup(self._tmp.cleanup)
        self.r = Path(self._tmp.name)
        for d in ("home", "tmp", "faux", "sur", "run", "cfg", "etat"):
            (self.r / d).mkdir(mode=0o700)
        (self.r / "apt/sources.list.d").mkdir(parents=True)
        (self.r / "yum").mkdir()
        for o in OUTILS_SURS:
            p = shutil.which(o)
            if p:
                (self.r / "sur" / o).symlink_to(p)
        for o in ("sudo", "curl", "gpg", "pacman", "apt-get", "dnf", "rpm", "dpkg", "systemctl", "sha256sum", "uname", "usermod", "zypper",
                  "flatpak", "kitty"):
            f = self.r / "faux" / o
            f.write_text(FAUX)
            f.chmod(0o755)
        (self.r / "cle.asc").write_text("CLE DE TEST\n")
        (self.r / "paquet.deb").write_text("PAQUET DE TEST\n")
        (self.r / "gpg.out").write_text(SORTIE_GPG_BONNE)
        (self.r / "export.asc").write_text("EXPORT DE TEST\n")
        (self.r / "sha").write_text(SHA_PROTON)

    def poser_os(self, nom):
        (self.r / "os-release").write_text(OS[nom])

    def env(self, **plus):
        e = {"PATH": str(self.r / "faux") + ":" + str(self.r / "sur"), "HOME": str(self.r / "home"), "TMPDIR": str(self.r / "tmp"),
             "XDG_CONFIG_HOME": str(self.r / "cfg"), "XDG_RUNTIME_DIR": str(self.r / "run"), "XDG_STATE_HOME": str(self.r / "etat"),
             "XDG_CACHE_HOME": str(self.r / "etat"), "XDG_DATA_HOME": str(self.r / "etat"), "FAUX_DIR": str(self.r),
             "NC_INSTALLER_TEST": "1", "NC_OS_RELEASE": str(self.r / "os-release"), "NC_TEST_CACHE": str(self.r / "cache"),
             "NC_TEST_APT_DIR": str(self.r / "apt"), "NC_TEST_YUM_DIR": str(self.r / "yum"), "NC_LANGUE": "fr", "LANG": "C.UTF-8"}
        e.update(plus)
        return e

    def lancer(self, *args, entree="", **plus):
        return subprocess.run(["bash", str(SCRIPT)] + list(args), env=self.env(**plus), input=entree, capture_output=True, text=True, timeout=60,
                              cwd=str(self.r / "home"))

    def appels(self):
        p = self.r / "appels"
        if not p.exists():
            return []
        t = str(self.r / "tmp")
        res = []
        for l in p.read_text().splitlines():
            m = re.sub(re.escape(t) + r"/tmp\.[A-Za-z0-9]+", "<T>", l).replace(str(self.r / "cache"), "<C>")
            res.append(m.split("\x1f"))
        return res

    def plan(self, fournisseur, os_nom):
        self.poser_os(os_nom)
        r = self.lancer(fournisseur, "--plan")
        self.assertEqual(r.returncode, 0, r.stderr)
        d = {"etapes": []}
        for l in r.stdout.splitlines():
            k, _, v = l.partition("=")
            if k == "etape":
                d["etapes"].append(v)
            else:
                d[k] = v
        return d


CURL = ["curl", "-q", "--proto", "=https", "--tlsv1.2", "-fsSL", "--max-time", "120", "--max-filesize", "2097152", "-o"]
GPGA = ["gpg", "--homedir", "<T>/gh", "--batch", "--no-tty"]
DEB_PROTON = "protonvpn-stable-release_1.0.10_all.deb"
PRE = lambda url: [CURL + ["<T>/cle-telechargee.asc", url], GPGA + ["--show-keys", "--with-colons", "<T>/cle-telechargee.asc"],
                   GPGA + ["--import", "<T>/cle-telechargee.asc"], GPGA + ["--export", "--export-options", "export-minimal", "--armor", EMPREINTE],
                   GPGA + ["--show-keys", "--with-colons", "<T>/cle-exportee.asc"]]
MKCACHE = ["sudo", "install", "-d", "-m0755", "<C>"]
CLE_CACHE = [MKCACHE, ["sudo", "install", "-m0644", "<T>/cle-exportee.asc", "<C>/mullvad-keyring.asc"],
             GPGA + ["--show-keys", "--with-colons", "<C>/mullvad-keyring.asc"]]
NETTOYAGE = lambda *noms: [["sudo", "rm", "-f", "--", "<C>/" + n] for n in noms] + [["sudo", "rmdir", "--", "<C>"]]

SUITES = {
    ("mullvad", "arch"): [["sudo", "pacman", "-S", "mullvad-vpn"], ["sudo", "systemctl", "enable", "--now", "mullvad-daemon.service"]],
    ("mullvad", "debian13"): [["uname", "-m"]] + PRE("https://repository.mullvad.net/deb/mullvad-keyring.asc") + CLE_CACHE + [
        MKCACHE, ["sudo", "install", "-m0644", "<T>/mullvad.list", "<C>/mullvad.list"],
        ["sudo", "install", "-Dm0644", "<C>/mullvad-keyring.asc", "/usr/share/keyrings/mullvad-keyring.asc"],
        ["sudo", "install", "-Dm0644", "<C>/mullvad.list", "/etc/apt/sources.list.d/mullvad.list"],
        ["sudo", "cmp", "--", "<C>/mullvad-keyring.asc", "/usr/share/keyrings/mullvad-keyring.asc"],
        ["sudo", "cmp", "--", "<C>/mullvad.list", "/etc/apt/sources.list.d/mullvad.list"],
        ["sudo", "apt-get", "update"], ["sudo", "apt-get", "install", "mullvad-vpn"]] + NETTOYAGE("mullvad-keyring.asc", "mullvad.list"),
    ("mullvad", "fedora44"): PRE("https://repository.mullvad.net/rpm/mullvad-keyring.asc") + CLE_CACHE + [
        MKCACHE, ["sudo", "install", "-m0644", "<T>/mullvad.repo", "<C>/mullvad.repo"],
        ["sudo", "install", "-Dm0644", "<C>/mullvad-keyring.asc", "/etc/pki/rpm-gpg/RPM-GPG-KEY-mullvad"],
        ["sudo", "cmp", "--", "<C>/mullvad-keyring.asc", "/etc/pki/rpm-gpg/RPM-GPG-KEY-mullvad"],
        ["sudo", "rpm", "--import", "/etc/pki/rpm-gpg/RPM-GPG-KEY-mullvad"],
        ["sudo", "install", "-Dm0644", "<C>/mullvad.repo", "/etc/yum.repos.d/mullvad.repo"],
        ["sudo", "cmp", "--", "<C>/mullvad.repo", "/etc/yum.repos.d/mullvad.repo"],
        ["sudo", "dnf", "install", "mullvad-vpn"]] + NETTOYAGE("mullvad-keyring.asc", "mullvad.repo"),
    ("proton", "arch"): [["sudo", "pacman", "-S", "proton-vpn-cli"]],
    ("proton", "debian13"): [
        CURL + ["<T>/" + DEB_PROTON, "https://repo.protonvpn.com/debian/dists/stable/main/binary-all/" + DEB_PROTON],
        ["sha256sum", "--", "<T>/" + DEB_PROTON], MKCACHE, ["sudo", "install", "-m0644", "<T>/" + DEB_PROTON, "<C>/" + DEB_PROTON],
        ["sha256sum", "--", "<C>/" + DEB_PROTON],
        ["sudo", "apt-get", "install", "<C>/" + DEB_PROTON], ["sudo", "apt-get", "update"],
        ["sudo", "apt-get", "install", "proton-vpn-gnome-desktop"]] + NETTOYAGE(DEB_PROTON),
}
GUIDEES = [("nord", o) for o in ("arch", "debian13", "fedora44", "tumbleweed", "leap")] + \
          [("proton", "fedora44"), ("proton", "tumbleweed"), ("proton", "leap"), ("mullvad", "tumbleweed"), ("mullvad", "leap")]
AUTRES_DISTROS = ("debian12", "fedora40", "ubuntu", "gentoo", "manjaro", "piege")


class Matrice(Base):
    def test_plan_de_chaque_case(self):
        for (f, o) in SUITES:
            with self.subTest(f=f, o=o):
                p = self.plan(f, o)
                self.assertEqual(p["mode"], "auto")
                self.assertRegex(p["lien"], r"^https://(protonvpn\.com|mullvad\.net)/")
                self.assertEqual(p["etapes"], [])
        for (f, o) in GUIDEES:
            with self.subTest(f=f, o=o):
                p = self.plan(f, o)
                self.assertEqual(p["mode"], "guide")
                self.assertRegex(p["lien"], r"^https://(protonvpn\.com|mullvad\.net|support\.nordvpn\.com)/")
                self.assertGreaterEqual(len(p["etapes"]), 3)

    def test_distributions_hors_matrice_guidees(self):
        for f in ("nord", "proton", "mullvad"):
            for o in AUTRES_DISTROS:
                with self.subTest(f=f, o=o):
                    self.assertEqual(self.plan(f, o)["mode"], "guide")

    def test_arch_derivee_acceptee_manjaro_non(self):
        self.assertEqual(self.plan("mullvad", "cachyos")["mode"], "auto")
        self.assertEqual(self.plan("proton", "manjaro")["mode"], "guide")

    def test_os_release_jamais_execute(self):
        self.poser_os("piege")
        r = self.lancer("mullvad", "--plan")
        self.assertEqual(r.returncode, 0)
        self.assertFalse((self.r / "home" / "PIEGE").exists() or (self.r / "PIEGE").exists())
        self.assertFalse(list(self.r.rglob("PIEGE*")))

    def test_os_release_absent_guide(self):
        r = self.lancer("mullvad", "--plan", NC_OS_RELEASE=str(self.r / "nexiste-pas"))
        self.assertIn("mode=guide", r.stdout)

    def test_plan_sans_reseau_ni_root(self):
        for f in ("nord", "proton", "mullvad"):
            for o in OS:
                self.poser_os(o)
                self.assertEqual(self.lancer(f, "--plan").returncode, 0)
        self.assertEqual(self.appels(), [])

    def test_plan_dans_les_deux_langues(self):
        self.poser_os("tumbleweed")
        fr = self.lancer("nord", "--plan", NC_LANGUE="fr").stdout
        en = self.lancer("nord", "--plan", NC_LANGUE="en").stdout
        self.assertIn("Ouvre la page officielle", fr)
        self.assertIn("Open the official page", en)
        self.assertEqual([l for l in fr.splitlines() if l.startswith("lien=")], [l for l in en.splitlines() if l.startswith("lien=")])


class Execution(Base):
    def test_suite_exacte_de_commandes_de_chaque_case_automatique(self):
        for (f, o), attendu in SUITES.items():
            with self.subTest(f=f, o=o):
                (self.r / "appels").unlink(missing_ok=True)
                self.poser_os(o)
                r = self.lancer(f, entree="o\n")
                self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
                self.assertEqual(self.appels(), attendu)
                # chaque étape est affichée avant d'être lancée
                self.assertIn("[1] ", r.stdout)
                self.assertEqual(list((self.r / "cache").glob("*")) if (self.r / "cache").exists() else [], [])      # le dossier de root est vidé
                self.assertFalse((self.r / "cache").exists())
                self.assertIn("Terminé", r.stdout)
                # le dossier temporaire a disparu
                self.assertEqual(list((self.r / "tmp").iterdir()), [])

    def test_fichier_de_depot_debian_ecrit_par_le_script(self):
        self.poser_os("debian13")
        self.assertEqual(self.lancer("mullvad", entree="o\n").returncode, 0)
        self.assertEqual((self.r / "copies/mullvad.list").read_text(),
                         "deb [signed-by=/usr/share/keyrings/mullvad-keyring.asc arch=amd64] https://repository.mullvad.net/deb/stable stable main\n")
        (self.r / "appels").unlink()
        self.assertEqual(self.lancer("mullvad", entree="o\n", FAUX_UNAME="aarch64").returncode, 0)
        self.assertIn("arch=arm64]", (self.r / "copies/mullvad.list").read_text())

    def test_arch_pacman_en_echec_dit_de_mettre_a_jour_sans_le_faire(self):
        """pacman -S échoue (base en retard, 404) : le script s'arrête et dit « sudo pacman -Syu », sans jamais le lancer."""
        for f in ("mullvad", "proton"):
            with self.subTest(f):
                (self.r / "appels").unlink(missing_ok=True)
                self.poser_os("arch")
                r = self.lancer(f, entree="o\n", FAUX_SUDO_ECHEC="pacman")
                self.assertNotEqual(r.returncode, 0)
                self.assertIn("sudo pacman -Syu", r.stderr)
                sudo = [a[1:] for a in self.appels() if a[0] == "sudo"]
                self.assertNotIn("-Syu", [x for a in sudo for x in a], "jamais de -Syu automatique")
                self.assertFalse([a for a in sudo if a[0] == "systemctl"], "rien après l'échec de pacman")

    def test_architecture_inconnue_arret_avant_ecriture(self):
        self.poser_os("debian13")
        r = self.lancer("mullvad", entree="o\n", FAUX_UNAME="riscv64")
        self.assertNotEqual(r.returncode, 0)
        self.assertFalse([a for a in self.appels() if a[0] == "sudo" or a[0] == "curl"])

    def test_fichier_de_depot_fedora_ecrit_par_le_script(self):
        self.poser_os("fedora44")
        self.assertEqual(self.lancer("mullvad", entree="o\n").returncode, 0)
        repo = (self.r / "copies/mullvad.repo").read_text()
        self.assertIn("baseurl=https://repository.mullvad.net/rpm/stable/$basearch\n", repo)
        self.assertIn("gpgcheck=1\n", repo)
        self.assertIn("gpgkey=file:///etc/pki/rpm-gpg/RPM-GPG-KEY-mullvad\n", repo)
        self.assertNotIn("gpgcheck=0", repo)
        # aucun fichier de dépôt n'est téléchargé : seule la clé l'est
        self.assertEqual([a[-1] for a in self.appels() if a[0] == "curl"], ["https://repository.mullvad.net/rpm/mullvad-keyring.asc"])

    def test_empreinte_fausse_arret_avant_tout_import_et_toute_ecriture(self):
        pub = lambda champ2, fpr: "pub:" + champ2 + ":4096:1:X:1:::-:::scESC::::::23::0:\nfpr:::::::::" + fpr + ":\n"
        for o in ("debian13", "fedora44"):
            for sortie in (pub("-", AUTRE),
                           "",                                                    # gpg ne lit rien
                           SORTIE_GPG_BONNE + pub("-", AUTRE),                     # une 2e clé principale en plus
                           pub("-", AUTRE) + SORTIE_GPG_BONNE,
                           SORTIE_GPG_BONNE + "sec:-:4096:1:X:1:::-:::scESC::::::23::0:\nfpr:::::::::" + EMPREINTE + ":\nssb:-:4096:1:Y:1:::::e::::::23:\n",   # clé secrète en plus
                           pub("r", EMPREINTE), pub("e", EMPREINTE), pub("i", EMPREINTE)):      # révoquée, expirée, invalide
                with self.subTest(o=o, sortie=sortie):
                    (self.r / "appels").unlink(missing_ok=True)
                    (self.r / "gpg.out").write_text(sortie)
                    self.poser_os(o)
                    r = self.lancer("mullvad", entree="o\n")
                    self.assertNotEqual(r.returncode, 0)
                    self.assertRegex(r.stdout + r.stderr, r"Empreinte|illisible|UNE clé|SECRÈTE|révoquée")
                    noms = [a[0] for a in self.appels() if a[0] != "uname"]
                    self.assertEqual(noms, ["curl", "gpg"])             # ni sudo, ni install, ni rpm --import, ni apt, ni import dans gpg
                    self.assertEqual(list((self.r / "tmp").iterdir()), [])
                    self.assertFalse((self.r / "cache").exists())

    def test_gpg_absent_message_clair(self):
        (self.r / "faux" / "gpg").unlink()
        self.poser_os("debian13")
        r = self.lancer("mullvad", entree="o\n")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("gpg absent : installe gnupg", r.stdout + r.stderr)
        self.assertNotIn("Empreinte", r.stdout + r.stderr)
        self.assertEqual([a[0] for a in self.appels() if a[0] != "uname"], [])

    def test_le_fichier_installe_est_l_export_pas_le_telechargement(self):
        for o, nom in (("debian13", "mullvad-keyring.asc"), ("fedora44", "mullvad-keyring.asc")):
            (self.r / "appels").unlink(missing_ok=True)
            self.poser_os(o)
            self.assertEqual(self.lancer("mullvad", entree="o\n").returncode, 0)
            self.assertEqual((self.r / "copies" / nom).read_text(), "EXPORT DE TEST\n")
            self.assertNotEqual((self.r / "copies" / nom).read_text(), (self.r / "cle.asc").read_text())

    def test_source_mullvad_deja_la_arret_avant_toute_ecriture(self):
        self.poser_os("debian13")
        liste = self.r / "apt/sources.list.d/mullvad.list"
        cas = (("mullvad.list", "deb https://repository.mullvad.net/deb/beta beta main\n"),            # notre nom, autre contenu
               ("mullvad-beta.list", "deb [arch=amd64] https://repository.mullvad.net/deb/beta beta main\n"),   # une autre source
               ("autre.sources", "Types: deb\nURIs: https://repository.mullvad.net/deb/stable\n"),
               ("mullvad.list", "# vide\n"))
        for nom, contenu in cas:
            with self.subTest(nom=nom):
                for f in (self.r / "apt/sources.list.d").iterdir():
                    f.unlink()
                (self.r / "appels").unlink(missing_ok=True)
                (self.r / "apt/sources.list.d" / nom).write_text(contenu)
                r = self.lancer("mullvad", entree="o\n")
                self.assertNotEqual(r.returncode, 0)
                self.assertIn("avant toute écriture", r.stdout + r.stderr)
                self.assertEqual([a[0] for a in self.appels() if a[0] != "uname"], [])
        for f in (self.r / "apt/sources.list.d").iterdir():
            f.unlink()
        (self.r / "apt/sources.list").write_text("deb https://repository.mullvad.net/deb/stable stable main\n")
        self.assertNotEqual(self.lancer("mullvad", entree="o\n").returncode, 0)
        (self.r / "apt/sources.list").unlink()
        # exactement notre fichier : on continue (relance idempotente)
        liste.write_text("deb [signed-by=/usr/share/keyrings/mullvad-keyring.asc arch=amd64] https://repository.mullvad.net/deb/stable stable main\n")
        self.assertEqual(self.lancer("mullvad", entree="o\n").returncode, 0)

    def test_source_mullvad_deja_la_fedora(self):
        self.poser_os("fedora44")
        for nom, contenu in (("mullvad.repo", "[x]\nbaseurl=https://repository.mullvad.net/rpm/beta/$basearch\n"),
                             ("autre.repo", "[y]\nbaseurl=https://repository.mullvad.net/rpm/stable/$basearch\n")):
            with self.subTest(nom=nom):
                for f in (self.r / "yum").iterdir():
                    f.unlink()
                (self.r / "appels").unlink(missing_ok=True)
                (self.r / "yum" / nom).write_text(contenu)
                r = self.lancer("mullvad", entree="o\n")
                self.assertNotEqual(r.returncode, 0)
                self.assertEqual([a[0] for a in self.appels()], [])

    def test_somme_proton_fausse_arret_avant_sudo(self):
        (self.r / "sha").write_text("0" * 64)
        self.poser_os("debian13")
        r = self.lancer("proton", entree="o\n")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("SHA-256", r.stdout + r.stderr)
        self.assertEqual([a[0] for a in self.appels()], ["curl", "sha256sum"])

    def test_parcours_guide_n_execute_rien(self):
        for f, o in GUIDEES + [(f, o) for f in ("nord", "proton", "mullvad") for o in AUTRES_DISTROS]:
            with self.subTest(f=f, o=o):
                self.poser_os(o)
                r = self.lancer(f, entree="o\n")
                self.assertEqual(r.returncode, 0, r.stderr)
                self.assertEqual(self.appels(), [])
                self.assertRegex(r.stdout, r"https://")
                self.assertNotIn("Continuer", r.stdout)

    def test_nord_guide_rappelle_groupe_service_et_session(self):
        self.poser_os("fedora44")
        r = self.lancer("nord")
        self.assertIn('sudo usermod -aG nordvpn "$USER"', r.stdout)
        self.assertIn("nordvpnd", r.stdout)
        self.assertIn("reconnecte-toi", r.stdout)
        self.assertEqual(self.appels(), [])

    def test_refus_de_l_utilisateur_ne_fait_rien(self):
        self.poser_os("debian13")
        for reponse in ("", "n\n", "\n", "peut-etre\n"):
            r = self.lancer("mullvad", entree=reponse)
            self.assertEqual(r.returncode, 0)
            self.assertEqual(self.appels(), [], reponse)
            self.assertIn("Annulé", r.stdout)

    def test_deja_installe_ne_fait_rien(self):
        self.poser_os("debian13")
        (self.r / "faux" / "mullvad").write_text("#!/bin/sh\nexit 0\n")
        (self.r / "faux" / "mullvad").chmod(0o755)
        r = self.lancer("mullvad", entree="o\n")
        self.assertEqual(r.returncode, 0)
        self.assertEqual(self.appels(), [])
        self.assertIn("déjà installé", r.stdout)

    def test_fournisseur_hors_liste_refuse(self):
        self.poser_os("debian13")
        for arg in ("", "foo", "../mullvad", "nord;touch X", "mullvad ", "NORD", "$(touch X)", "-h", "--plan"):
            with self.subTest(arg=arg):
                r = self.lancer(arg, entree="o\n")
                self.assertEqual(r.returncode, 2)
        for args in ((), ("nord", "--oui"), ("nord", "--plan", "x"), ("mullvad", "-y")):
            self.assertEqual(self.lancer(*args, entree="o\n").returncode, 2, args)
        self.assertEqual(self.appels(), [])
        self.assertFalse(list(self.r.rglob("X")))

    def test_anglais(self):
        self.poser_os("tumbleweed")
        r = self.lancer("mullvad", NC_LANGUE="en")
        self.assertIn("Guided path", r.stdout)
        self.poser_os("debian13")
        r = self.lancer("mullvad", entree="n\n", NC_LANGUE="en")
        self.assertIn("Continue? [y/N]", r.stdout)
        self.assertIn("Cancelled", r.stdout)


class Statique(unittest.TestCase):
    """Le script lui-même : aucun contenu téléchargé n'est exécuté, rien d'interdit."""
    SRC = SCRIPT.read_text()

    def test_aucun_sh_ni_bash_sur_un_contenu_telecharge(self):
        code = "\n".join(l for l in self.SRC.splitlines() if not l.lstrip().startswith("#"))
        for motif in (r"\|\s*(sudo\s+)?(ba|z|da)?sh\b", r"\b(ba|z|da)?sh\s+<\(", r"\b(ba|z|da)?sh\s+-c\b", r"\beval\b", r"(^|[;&|(]\s*)source\s", r"(^|\s)\.\s+[\"$/]",
                      r"curl[^\n]*\|", r"wget", r"\bsudo\s+(ba|z|da)?sh\b", r"curl[^\n]*(--insecure|\s-k\s)", r"gpgcheck=0", r"--nogpgcheck",
                      r"--gpg-auto-import-keys", r"--allow-unauthenticated", r"Trusted:\s*yes", r"apt-key", r"firewall-cmd|\bufw\b",
                      r"sudoers", r"visudo", r"zypper\s+(add|install|ar|in)", r"flatpak\s+install", r"\byay\b|\bparu\b|\bmakepkg\b",
                      r"(?i)trusted=yes", r"--force", r"allow-insecure", r"repo_gpgcheck=0", r"sslverify=0", r"--no-gpg-checks", r"localpkg_gpgcheck=0"):
            self.assertIsNone(re.search(motif, code, re.M), motif)
        # la clé reçue n'est jamais installée telle quelle : seul l'export part vers sudo
        self.assertNotIn("cle-telechargee.asc\" /", code)
        for m in re.finditer(r"^\s*(etape sudo|poser_cache) .*$", code, re.M):
            self.assertNotIn("cle-telechargee", m.group(0))

    def test_telechargements_https_seulement_en_fichier(self):
        urls = re.findall(r"https?://[^\s\"']+", "\n".join(l for l in self.SRC.splitlines() if not l.lstrip().startswith("#") and "lien=" not in l))
        for u in urls:
            if u.startswith("http://"):
                self.fail(u)
        self.assertIn("--proto '=https'", self.SRC)
        self.assertEqual(len(re.findall(r"^\s*etape curl\b", self.SRC, re.M)), 1)         # un seul appel curl, toujours avec -o
        self.assertIn("-o \"$2\"", self.SRC)

    def test_set_eu_et_liste_blanche_en_tete(self):
        lignes = [l for l in self.SRC.splitlines() if l and not l.startswith("#")]
        self.assertEqual(lignes[0], "set -eu")
        self.assertLess(self.SRC.index("nord|proton|mullvad) ;;"), self.SRC.index("os_lire()"))
        self.assertLess(self.SRC.index("nord|proton|mullvad) ;;"), self.SRC.index("etape sudo"))

    def test_chaque_commande_root_passe_par_etape(self):
        autorises = (r"^etape sudo ", r"^printf", r"^dire ", r"^RAISON", r"^\"", r"^for f in \"\$\{CACHE_FICHIERS", r"^sudo rmdir -- \"\$CACHE\" ")
        for m in re.finditer(r"^(.*)\bsudo\b(.*)$", "\n".join(l for l in self.SRC.splitlines() if not l.lstrip().startswith("#")), re.M):
            ligne = m.group(0).strip()
            if "EXTRA_" in ligne or any(re.search(a, ligne) for a in autorises):
                continue
            self.fail(ligne)

    def test_chaque_etape_root_a_des_arguments_constants(self):
        for m in re.finditer(r"^\s*etape sudo (.*)$", self.SRC, re.M):
            for mot in m.group(1).split():
                self.assertRegex(mot, r'^(-?-?[A-Za-z0-9._/+-]+|"\$(1|CACHE(/[A-Za-z0-9._$-]+|/\$nom)?)"|"\$CACHE/\$nom")$', m.group(0))

    def test_path_fixe_et_umask_juste_apres_set_eu(self):
        lignes = [l for l in self.SRC.splitlines() if l and not l.startswith("#")]
        self.assertEqual(lignes[0], "set -eu")
        self.assertEqual(lignes[1], 'if [ "${NC_INSTALLER_TEST:-}" != 1 ]; then')
        self.assertEqual(lignes[2].strip(), "PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin")
        self.assertEqual(lignes[3].strip(), "export PATH")
        self.assertEqual(lignes[5], "umask 022")

    def test_variables_de_test_seulement_derriere_l_indicateur(self):
        for var in ("NC_OS_RELEASE", "NC_TEST_EMPREINTE", "NC_TEST_CACHE", "NC_TEST_APT_DIR", "NC_TEST_YUM_DIR"):
            for m in re.finditer(r"^.*\b" + var + r"\b.*$", "\n".join(l for l in self.SRC.splitlines() if not l.lstrip().startswith("#")), re.M):
                ligne = m.group(0)
                self.assertTrue("NC_INSTALLER_TEST" in ligne or ligne.strip().startswith("CACHE=\"${NC_TEST") or ligne.strip().startswith(("APT_DIR=", "YUM_DIR=")), ligne)

    def test_shellcheck(self):
        if not shutil.which("shellcheck"):
            self.skipTest("shellcheck absent")
        r = subprocess.run(["shellcheck", str(SCRIPT)], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout)

    def test_empreinte_et_somme_epinglees_sont_celles_des_sources(self):
        self.assertIn("MULLVAD_EMPREINTE=" + EMPREINTE, self.SRC)
        self.assertIn("PROTON_DEB_SHA256=" + SHA_PROTON, self.SRC)
        self.assertNotRegex(self.SRC, r"@[A-Z_]+@")                      # aucun @MARQUEUR@ que install.sh remplacerait


class Environnement(Base):
    """PATH fixe et variables de test : sans NC_INSTALLER_TEST=1, ni le PATH ni NC_OS_RELEASE reçus ne comptent."""
    def test_path_recu_ignore_sans_indicateur(self):
        marque = self.r / "marque"
        faux_sed = self.r / "faux" / "sed"
        faux_sed.write_text("#!/bin/sh\necho x >> \"" + str(marque) + "\"\nexit 0\n")
        faux_sed.chmod(0o755)
        reg = self.r / "home" / ".config" / "nc"
        reg.mkdir(parents=True)
        (reg / "reglages.conf").write_text('LANGUE="fr"\n')
        # sans NC_LANGUE, langue_lire lance sed : le vrai (PATH fixe), jamais celui du PATH reçu
        e = {k: v for k, v in self.env().items() if k not in ("NC_LANGUE", "NC_INSTALLER_TEST")}
        subprocess.run(["bash", str(SCRIPT), "nord", "--plan"], env=e, capture_output=True, text=True, timeout=30)
        self.assertFalse(marque.exists(), "le PATH reçu a été suivi")
        subprocess.run(["bash", str(SCRIPT), "nord", "--plan"], env=dict(e, NC_INSTALLER_TEST="1"), capture_output=True, text=True, timeout=30)
        self.assertTrue(marque.exists(), "avec l'indicateur de test, le PATH reçu est gardé")

    def test_os_release_recu_ignore_sans_indicateur(self):
        (self.r / "os-release").write_text(OS["gentoo"])
        e = self.env()
        sans = {k: v for k, v in e.items() if k not in ("NC_OS_RELEASE", "NC_INSTALLER_TEST")}
        ref = subprocess.run(["bash", str(SCRIPT), "mullvad", "--plan"], env=sans, capture_output=True, text=True, timeout=30).stdout
        avec_var_seule = subprocess.run(["bash", str(SCRIPT), "mullvad", "--plan"], env=dict(sans, NC_OS_RELEASE=str(self.r / "os-release")),
                                        capture_output=True, text=True, timeout=30).stdout
        self.assertEqual(avec_var_seule, ref)                       # NC_OS_RELEASE sans l'indicateur : le vrai os-release de la machine
        test = subprocess.run(["bash", str(SCRIPT), "mullvad", "--plan"], env=e, capture_output=True, text=True, timeout=30).stdout
        self.assertIn("mode=guide", test)

    def test_variables_de_test_ignorees_sans_indicateur(self):
        # l'empreinte et le dossier de root ne se changent pas depuis l'environnement hors essais
        src = SCRIPT.read_text()
        self.assertIn('if [ "${NC_INSTALLER_TEST:-}" = 1 ] && [ -n "${NC_TEST_EMPREINTE:-}" ]', src)


@unittest.skipUnless(shutil.which("gpg"), "gpg absent")
class VraiGpg(Base):
    """Le contrôle de la clé avec le VRAI gpg et des clés jetables (trousseau sous un dossier temporaire) : le fichier reçu n'est jamais
    installé tel quel, seul son export l'est ; clé secrète, révoquée, expirée ou 2 clés principales : refus avant tout sudo."""
    def setUp(self):
        super().setUp()
        (self.r / "faux" / "gpg").unlink()
        (self.r / "faux" / "gpg").symlink_to(shutil.which("gpg"))
        self.gen = self.r / "gen"
        self.gen.mkdir(mode=0o700)
        self.poser_os("debian13")

    def gpg(self, *args, entree=None, home=None, batch=True, **kw):
        env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": str(self.r / "home"), "LANG": "C"}
        return subprocess.run(["gpg", "--homedir", str(home or self.gen)] + (["--batch"] if batch else []) + ["--no-tty"] + list(args), env=env, input=entree,
                              capture_output=True, text=True, timeout=60, **kw)

    def cle(self, nom, extra=(), home=None):
        r = self.gpg("--pinentry-mode", "loopback", "--passphrase", "", *extra, "--quick-gen-key", nom + " <" + nom.lower() + "@example.org>",
                     "ed25519", "sign", "never" if "--faked-system-time" not in extra else "1d", home=home)
        if r.returncode != 0:
            self.skipTest("gpg ne crée pas de clé ici : " + r.stderr[:120])
        out = self.gpg("--with-colons", "--list-keys", nom.lower() + "@example.org", home=home).stdout
        return [l.split(":")[9] for l in out.splitlines() if l.startswith("fpr:")][0]

    def pub(self, fpr, home=None):
        return self.gpg("--armor", "--export", fpr, home=home).stdout

    def secret(self, fpr, home=None):
        return self.gpg("--pinentry-mode", "loopback", "--passphrase", "", "--armor", "--export-secret-keys", fpr, home=home).stdout

    def lancer_avec(self, contenu, fpr):
        (self.r / "cle.asc").write_text(contenu)
        (self.r / "appels").unlink(missing_ok=True)
        return self.lancer("mullvad", entree="o\n", NC_TEST_EMPREINTE=fpr)

    def refuse(self, r, mot):
        self.assertNotEqual(r.returncode, 0, r.stdout)
        self.assertIn(mot, r.stdout + r.stderr)
        self.assertEqual([a[0] for a in self.appels() if a[0] not in ("uname", "curl")], [])       # jamais un sudo, ni d'import
        self.assertFalse((self.r / "copies").exists())
        self.assertEqual(list((self.r / "tmp").iterdir()), [])

    def test_cle_seule_le_fichier_installe_est_l_export(self):
        fpr = self.cle("Seule")
        recu = "# commentaire du serveur, absent de l'export\n" + self.pub(fpr)
        r = self.lancer_avec(recu, fpr)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        installe = (self.r / "copies" / "mullvad-keyring.asc").read_text()
        self.assertNotEqual(installe, recu)
        self.assertNotIn("commentaire du serveur", installe)
        self.assertTrue(installe.startswith("-----BEGIN PGP PUBLIC KEY BLOCK-----"))
        # l'export est bien la même clé (une seule clé principale, même empreinte)
        v = self.gpg("--with-colons", "--show-keys", str(self.r / "copies" / "mullvad-keyring.asc")).stdout
        self.assertEqual([l.split(":")[9] for l in v.splitlines() if l.startswith("fpr:")][:1], [fpr])
        self.assertEqual(len([l for l in v.splitlines() if l.startswith("pub:")]), 1)
        self.assertEqual([l for l in v.splitlines() if l.startswith(("sec:", "ssb:"))], [])
        # la copie dans le dossier de root a été retirée
        self.assertFalse((self.r / "cache").exists())

    def test_trousseau_avec_cle_secrete_refuse_avant_tout_sudo(self):
        fpr = self.cle("Secrete")
        r = self.lancer_avec(self.pub(fpr) + self.secret(fpr), fpr)
        self.refuse(r, "SECRÈTE")
        r = self.lancer_avec(self.secret(fpr), fpr)                       # seulement la clé secrète : refus aussi
        self.refuse(r, "SECRÈTE")

    def test_cle_revoquee_refusee(self):
        fpr = self.cle("Revoquee")
        rev = self.gpg("--yes", "--pinentry-mode", "loopback", "--passphrase", "", "--command-fd", "0", "--armor", "--gen-revoke", fpr, entree="y\n0\n\ny\n", batch=False)
        if "BEGIN PGP PUBLIC KEY BLOCK" not in rev.stdout:
            self.skipTest("gpg ne crée pas de certificat de révocation ici : " + rev.stderr[:120])
        self.gpg("--import", entree=rev.stdout)
        self.refuse(self.lancer_avec(self.pub(fpr), fpr), "révoquée")

    def test_cle_expiree_refusee(self):
        fpr = self.cle("Expiree", extra=("--faked-system-time", "20200101T000000"))
        v = self.gpg("--with-colons", "--list-keys", fpr).stdout
        self.assertRegex(v, r"(?m)^pub:e:")
        self.refuse(self.lancer_avec(self.pub(fpr), fpr), "expirée")

    def test_deux_cles_principales_refusees(self):
        a = self.cle("PremiereCle")
        b = self.cle("SecondeCle")
        self.refuse(self.lancer_avec(self.pub(a) + self.pub(b), a), "UNE clé")
        self.refuse(self.lancer_avec(self.pub(b) + self.pub(a), a), "UNE clé")

    def test_mauvaise_empreinte_refusee(self):
        a = self.cle("CleReelle")
        self.refuse(self.lancer_avec(self.pub(a), AUTRE), "Empreinte")


class AvecNcVpn(BaseVpn):
    """nc-vpn : le champ « installation », la commande installer-client, aucun bouton hors client absent."""
    def setUp(self):
        super().setUp()
        (self.r / "faux-bin" / "bash").symlink_to(shutil.which("bash"))
        (self.r / "os-release").write_text(OS["debian13"])
        for o in ("sed", "tr", "tail", "awk", "mktemp", "chmod", "rm", "cut", "cat", "basename"):
            if shutil.which(o):
                (self.r / "faux-bin" / o).symlink_to(shutil.which(o))
        k = self.r / "faux-bin" / "kitty"
        k.write_text(FAUX.replace("$FAUX_DIR/appels", "$FAUX_DIR/appels-kitty"))
        k.chmod(0o755)

    def lire(self, **plus):
        r = self.seul("fournisseurs-json", NC_OS_RELEASE=str(self.r / "os-release"), NC_INSTALLER_TEST="1", **plus)
        self.assertEqual(r.returncode, 0, r.stderr)
        return {f["id"]: f for f in json.loads(r.stdout)["fournisseurs"]}

    def test_absent_porte_le_plan_et_rien_d_autre(self):
        d = self.lire()
        self.assertEqual(d["proton"]["etat"], "absent")
        self.assertEqual(d["proton"]["installation"]["mode"], "auto")
        self.assertEqual(d["nord"]["installation"]["mode"], "guide")
        self.assertGreaterEqual(len(d["nord"]["installation"]["etapes"]), 3)
        for f in d.values():
            if f["etat"] == "absent":
                self.assertRegex(f["installation"]["lien"], r"^https://(protonvpn\.com|mullvad\.net|support\.nordvpn\.com)/")

    def test_le_bouton_n_existe_que_si_absent(self):
        self.poser("nordvpn", {"account": {"out": "Account information\n"}, "countries": {"out": "France\n"}})
        (self.r / "mullvad.json").write_text(json.dumps({"texte": "Disconnected", "compte": "Not logged in on any account",
                                                         "json": json.dumps({"state": "disconnected"})}))
        d = self.lire()
        self.assertNotEqual(d["nord"]["etat"], "absent")
        self.assertNotIn("installation", d["nord"])
        self.assertNotEqual(d["mullvad"]["etat"], "absent")
        self.assertNotIn("installation", d["mullvad"])
        self.assertIn("installation", d["proton"])

    def test_sans_script_aucun_champ(self):
        # nc-vpn copié ailleurs, sans ../libexec : pas de bouton, pas d'erreur
        bin_ = self.r / "copie" / "bin"
        bin_.mkdir(parents=True)
        shutil.copy(REPO / "home/.local/bin/nc-vpn", bin_ / "nc-vpn")
        r = subprocess.run(["python3", str(bin_ / "nc-vpn"), "fournisseurs-json"], env=self.env(PATH=str(self.r / "faux-bin")), capture_output=True, text=True,
                           timeout=30, stdin=subprocess.DEVNULL)
        self.assertEqual(r.returncode, 0, r.stderr)
        for f in json.loads(r.stdout)["fournisseurs"]:
            self.assertNotIn("installation", f)

    def test_sortie_du_script_filtree(self):
        """Une sortie qui sort de la liste blanche (lien vers un autre site, texte à caractères de contrôle, mode inconnu) n'est pas relayée."""
        faux = self.r / "copie" / "libexec"
        faux.mkdir(parents=True)
        (self.r / "copie" / "bin").mkdir()
        shutil.copy(REPO / "home/.local/bin/nc-vpn", self.r / "copie" / "bin" / "nc-vpn")
        s = faux / "nc-vpn-installer"
        for sortie, attendu in (("mode=guide\nlien=https://evil.example/x\netape=ok\n", None),
                                ("mode=guide\nlien=http://protonvpn.com/x\netape=ok\n", None),
                                ("mode=guide\nlien=https://protonvpn.com.evil.example/x\netape=ok\n", None),
                                ("mode=rm\nlien=https://protonvpn.com/x\netape=ok\n", None),
                                ("mode=guide\nlien=https://protonvpn.com/x\n", None),
                                ("mode=guide\nlien=https://protonvpn.com/x\netape=a\\x1b[31mb\n", None),
                                ("mode=guide\nlien=https://protonvpn.com/x\netape=<b>gras</b>\n", None),
                                ("mode=guide\nlien=https://protonvpn.com/x\netape=$(touch X)\netape=Etape normale, avec « guillemets ».\n",
                                 {"mode": "guide", "lien": "https://protonvpn.com/x", "etapes": ["Etape normale, avec « guillemets »."]}),
                                ("mode=auto\nlien=https://mullvad.net/x\netape=ignorée\n", {"mode": "auto", "lien": "https://mullvad.net/x", "etapes": []})):
            s.write_text("#!/bin/sh\ncat <<'FIN'\n" + sortie.replace("\\x1b", "\x1b") + "FIN\n")
            r = subprocess.run(["python3", str(self.r / "copie" / "bin" / "nc-vpn"), "fournisseurs-json"],
                               env=self.env(PATH=str(self.r / "faux-bin")), capture_output=True, text=True, timeout=30, stdin=subprocess.DEVNULL)
            self.assertEqual(r.returncode, 0, r.stderr)
            # bash lit ce faux script : on met bash dans faux-bin (setUp) ; la sortie du faux script est le « plan »
            f = {x["id"]: x for x in json.loads(r.stdout)["fournisseurs"]}["proton"]
            self.assertEqual(f.get("installation"), attendu, sortie)

    def test_installer_client_lance_kitty_avec_le_script_fixe(self):
        r = self.seul("installer-client", "proton", NC_OS_RELEASE=str(self.r / "os-release"))
        self.assertEqual(r.returncode, 0, r.stderr)
        appels = [l.split("\x1f") for l in (self.r / "appels-kitty").read_text().splitlines()]
        self.assertEqual(len(appels), 1)
        k = appels[0]
        self.assertEqual(k[0], "kitty")
        self.assertEqual(k[1:3], ["--hold", "--title"])
        # bash vient du PATH fixe, jamais d'un bash posé plus tôt dans le PATH de la session (ici le faux)
        fixe = shutil.which("bash", path="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin")
        self.assertEqual(k[4:], [fixe, str(REPO / "home/.local/libexec/nc-vpn-installer"), "proton"])
        self.assertNotEqual(k[4], str(self.r / "faux-bin" / "bash"))

    def test_installer_client_refuse_client_deja_la_et_fournisseur_inconnu(self):
        self.poser("nordvpn", {"account": {"out": "Account information\n"}, "countries": {"out": "France\n"}})
        r = self.seul("installer-client", "nord")
        self.assertEqual(r.returncode, 1)
        self.assertIn("déjà installé", r.stderr)
        for arg in ("inconnu", "../nord", "nord;ls", ""):
            r = self.seul("installer-client", arg)
            self.assertEqual(r.returncode, 1, arg)
        self.assertEqual(self.seul("installer-client").returncode, 2)
        self.assertEqual(self.seul("installer-client", "nord", "x").returncode, 2)
        self.assertFalse((self.r / "appels-kitty").exists())

    def test_installer_client_nettoie_l_environnement_du_terminal(self):
        k = self.r / "faux-bin" / "kitty"
        k.write_text("#!/bin/sh\nenv > \"$FAUX_DIR/env-kitty\"\n")
        k.chmod(0o755)
        piege = self.r / "piege.sh"
        piege.write_text("touch " + str(self.r / "PIEGE") + "\n")
        r = self.seul("installer-client", "proton", BASH_ENV=str(piege), ENV=str(piege), NC_OS_RELEASE="/tmp/x", NC_INSTALLER_TEST="1",
                      NC_TEST_EMPREINTE="0" * 40, NC_TEST_CACHE="/tmp/y", NC_TEST_APT_DIR="/tmp/z", LD_PRELOAD="/tmp/lib.so", GNUPGHOME="/tmp/g",
                      CURL_CA_BUNDLE="/tmp/ca", SSL_CERT_FILE="/tmp/ca", CDPATH="/tmp", **{"BASH_FUNC_ls%%": "() { echo pwned; }"})
        self.assertEqual(r.returncode, 0, r.stderr)
        env = dict(l.split("=", 1) for l in (self.r / "env-kitty").read_text().splitlines() if "=" in l)
        for var in ("BASH_ENV", "ENV", "NC_OS_RELEASE", "NC_INSTALLER_TEST", "NC_TEST_EMPREINTE", "NC_TEST_CACHE", "NC_TEST_APT_DIR", "LD_PRELOAD",
                    "GNUPGHOME", "CURL_CA_BUNDLE", "SSL_CERT_FILE", "CDPATH"):
            self.assertNotIn(var, env)
        self.assertFalse([k for k in env if k.startswith("BASH_FUNC_")])
        self.assertEqual(env["PATH"], "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin")
        self.assertEqual(env["NC_LANGUE"], "fr")
        self.assertEqual(env["HOME"], str(self.r / "home"))                  # le reste de la session (écran, session) est gardé
        self.assertFalse((self.r / "PIEGE").exists())

    def test_installer_client_sans_kitty(self):
        (self.r / "faux-bin" / "kitty").unlink()
        r = self.seul("installer-client", "proton", NC_OS_RELEASE=str(self.r / "os-release"))
        self.assertEqual(r.returncode, 1)
        self.assertIn("kitty", r.stderr)

    def test_redetection_apres_installation(self):
        """Client absent, puis « installé » (le terminal s'est fermé) : fournisseurs-json relit tout, le champ a disparu."""
        self.assertIn("installation", self.lire()["proton"])
        self.poser("protonvpn", {"info": {"out": "Username: x\n"}})
        apres = self.lire()["proton"]
        self.assertNotEqual(apres["etat"], "absent")
        self.assertNotIn("installation", apres)


if __name__ == "__main__":
    unittest.main()

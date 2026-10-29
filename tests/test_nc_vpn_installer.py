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
               "install", "ls", "printf", "python3", "basename", "cp")

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
  gpg)    case " $* " in *" --show-keys "*) cat "$FAUX_DIR/gpg.out" ;; esac ;;
  sha256sum) printf '%s  %s\n' "$(cat "$FAUX_DIR/sha")" "$2" ;;
  uname)  echo "${FAUX_UNAME:-x86_64}" ;;
  sudo)   # copie le fichier source d'« install » pour le relire
    if [ "$1" = install ]; then
      for a in "$@"; do case "$a" in */mullvad.list|*/mullvad.repo|*/mullvad-keyring.asc) mkdir -p "$FAUX_DIR/copies"; cp "$a" "$FAUX_DIR/copies/$(basename "$a")" 2>/dev/null || true ;; esac; done
    fi ;;
esac
exit 0
'''


class Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="nc-inst-")
        self.addCleanup(self._tmp.cleanup)
        self.r = Path(self._tmp.name)
        for d in ("home", "tmp", "faux", "sur", "run", "cfg", "etat"):
            (self.r / d).mkdir(mode=0o700)
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
        (self.r / "sha").write_text(SHA_PROTON)

    def poser_os(self, nom):
        (self.r / "os-release").write_text(OS[nom])

    def env(self, **plus):
        e = {"PATH": str(self.r / "faux") + ":" + str(self.r / "sur"), "HOME": str(self.r / "home"), "TMPDIR": str(self.r / "tmp"),
             "XDG_CONFIG_HOME": str(self.r / "cfg"), "XDG_RUNTIME_DIR": str(self.r / "run"), "XDG_STATE_HOME": str(self.r / "etat"),
             "XDG_CACHE_HOME": str(self.r / "etat"), "XDG_DATA_HOME": str(self.r / "etat"), "FAUX_DIR": str(self.r),
             "NC_OS_RELEASE": str(self.r / "os-release"), "NC_LANGUE": "fr", "LANG": "C.UTF-8"}
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
            m = re.sub(re.escape(t) + r"/tmp\.[A-Za-z0-9]+", "<T>", l)
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


CURL = ["curl", "--proto", "=https", "--tlsv1.2", "-fsSL", "--max-time", "120", "--max-filesize", "2097152", "-o"]
GPG = ["gpg", "--batch", "--no-tty", "--show-keys", "--with-colons", "<T>/mullvad-keyring.asc"]
DEB_PROTON = "<T>/protonvpn-stable-release_1.0.10_all.deb"

SUITES = {
    ("mullvad", "arch"): [["sudo", "pacman", "-S", "mullvad-vpn"], ["sudo", "systemctl", "enable", "--now", "mullvad-daemon.service"]],
    ("mullvad", "debian13"): [
        ["uname", "-m"], CURL + ["<T>/mullvad-keyring.asc", "https://repository.mullvad.net/deb/mullvad-keyring.asc"], GPG,
        ["sudo", "install", "-Dm0644", "<T>/mullvad-keyring.asc", "/usr/share/keyrings/mullvad-keyring.asc"],
        ["sudo", "install", "-Dm0644", "<T>/mullvad.list", "/etc/apt/sources.list.d/mullvad.list"],
        ["sudo", "apt-get", "update"], ["sudo", "apt-get", "install", "mullvad-vpn"]],
    ("mullvad", "fedora44"): [
        CURL + ["<T>/mullvad-keyring.asc", "https://repository.mullvad.net/rpm/mullvad-keyring.asc"], GPG,
        ["sudo", "install", "-Dm0644", "<T>/mullvad-keyring.asc", "/etc/pki/rpm-gpg/RPM-GPG-KEY-mullvad"],
        ["sudo", "rpm", "--import", "/etc/pki/rpm-gpg/RPM-GPG-KEY-mullvad"],
        ["sudo", "install", "-Dm0644", "<T>/mullvad.repo", "/etc/yum.repos.d/mullvad.repo"],
        ["sudo", "dnf", "install", "mullvad-vpn"]],
    ("proton", "arch"): [["sudo", "pacman", "-S", "proton-vpn-cli"]],
    ("proton", "debian13"): [
        CURL + [DEB_PROTON, "https://repo.protonvpn.com/debian/dists/stable/main/binary-all/protonvpn-stable-release_1.0.10_all.deb"],
        ["sha256sum", "--", DEB_PROTON],
        ["sudo", "dpkg", "-i", DEB_PROTON], ["sudo", "apt-get", "update"], ["sudo", "apt-get", "install", "proton-vpn-gnome-desktop"]],
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
                self.assertIn("[1/", r.stdout)
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
        for o in ("debian13", "fedora44"):
            for sortie in ("pub:-:4096:1:X:1:::-:::scESC::::::23::0:\nfpr:::::::::" + AUTRE + ":\n",
                           "",                                                    # gpg ne lit rien
                           SORTIE_GPG_BONNE + "pub:-:4096:1:Y:1:::-:::scESC::::::23::0:\nfpr:::::::::" + AUTRE + ":\n",     # une 2e clé principale en plus
                           "pub:-:4096:1:Y:1:::-:::scESC::::::23::0:\nfpr:::::::::" + AUTRE + ":\n" + SORTIE_GPG_BONNE):
                with self.subTest(o=o, sortie=sortie):
                    (self.r / "appels").unlink(missing_ok=True)
                    (self.r / "gpg.out").write_text(sortie)
                    self.poser_os(o)
                    r = self.lancer("mullvad", entree="o\n")
                    self.assertNotEqual(r.returncode, 0)
                    self.assertIn("Empreinte", r.stdout + r.stderr)
                    noms = [a[0] for a in self.appels() if a[0] != "uname"]
                    self.assertEqual(noms, ["curl", "gpg"])             # ni sudo, ni install, ni rpm --import, ni apt
                    self.assertEqual(list((self.r / "tmp").iterdir()), [])

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
        for motif in (r"\|\s*(sudo\s+)?(ba|z|da)?sh\b", r"\b(ba|z|da)?sh\s+<\(", r"\b(ba|z|da)?sh\s+-c\b", r"\beval\b", r"\bsource\b", r"(^|\s)\.\s+[\"$/]",
                      r"curl[^\n]*\|", r"wget", r"\bsudo\s+(ba|z|da)?sh\b", r"-k\b.*curl|curl[^\n]*(--insecure|\s-k\s)", r"gpgcheck=0", r"--nogpgcheck",
                      r"--gpg-auto-import-keys", r"--allow-unauthenticated", r"Trusted:\s*yes", r"apt-key", r"firewall-cmd|\bufw\b",
                      r"sudoers", r"visudo", r"zypper\s+(add|install|ar|in)", r"flatpak\s+install", r"\byay\b|\bparu\b|\bmakepkg\b"):
            self.assertIsNone(re.search(motif, code, re.M), motif)

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
        for m in re.finditer(r"^(.*)\bsudo\b(.*)$", "\n".join(l for l in self.SRC.splitlines() if not l.lstrip().startswith("#")), re.M):
            ligne = m.group(0).strip()
            if ligne.startswith("etape sudo ") or ligne.startswith("printf") or ligne.startswith("dire ") or "EXTRA_" in ligne or ligne.startswith("RAISON") or ligne.startswith('"'):
                continue
            self.fail(ligne)

    def test_chaque_etape_root_a_des_arguments_constants(self):
        for m in re.finditer(r"^\s*etape sudo (.*)$", self.SRC, re.M):
            for mot in m.group(1).split():
                self.assertRegex(mot, r'^(-?[A-Za-z0-9._/+-]+|"\$f"|"\$TMP/[a-z.-]+")$', m.group(0))

    def test_shellcheck(self):
        if not shutil.which("shellcheck"):
            self.skipTest("shellcheck absent")
        r = subprocess.run(["shellcheck", str(SCRIPT)], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout)

    def test_empreinte_et_somme_epinglees_sont_celles_des_sources(self):
        self.assertIn("MULLVAD_EMPREINTE=" + EMPREINTE, self.SRC)
        self.assertIn("PROTON_DEB_SHA256=" + SHA_PROTON, self.SRC)
        self.assertNotRegex(self.SRC, r"@[A-Z_]+@")                      # aucun @MARQUEUR@ que install.sh remplacerait

    def test_gpg_reel_lit_la_cle_comme_l_attend_le_script(self):
        """Avec un vrai gpg et une clé de test faite à la volée : la fonction d'empreinte du script rend exactement l'empreinte de la clé."""
        gpg = shutil.which("gpg")
        if not gpg:
            self.skipTest("gpg absent")
        with tempfile.TemporaryDirectory(prefix="nc-gpg-") as d:
            d = Path(d)
            (d / "gh").mkdir(mode=0o700)
            env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": str(d), "GNUPGHOME": str(d / "gh")}
            r = subprocess.run([gpg, "--batch", "--quiet", "--pinentry-mode", "loopback", "--passphrase", "", "--quick-gen-key", "Test Cle <test@example.org>", "ed25519", "sign", "never"],
                               env=env, capture_output=True, text=True, timeout=60)
            if r.returncode != 0:
                self.skipTest("gpg ne crée pas de clé ici : " + r.stderr[:100])
            r = subprocess.run([gpg, "--batch", "--armor", "--export"], env=env, capture_output=True, text=True)
            (d / "cle.asc").write_text(r.stdout)
            vraie = subprocess.run([gpg, "--batch", "--with-colons", "--show-keys", str(d / "cle.asc")], env=env, capture_output=True, text=True)
            fpr = [l.split(":")[9] for l in vraie.stdout.splitlines() if l.startswith("fpr:")][0]
            # on extrait la fonction empreintes_cle du script et on l'exécute telle quelle
            debut = self.SRC.index("empreintes_cle() {")
            fin = self.SRC.index("verifier_cle()")
            prog = "set -eu\n" + self.SRC[debut:fin] + "\nempreintes_cle \"$1\"\n"
            s = subprocess.run(["bash", "-c", prog, "x", str(d / "cle.asc")], env=dict(env, TMPDIR=str(d)), capture_output=True, text=True)
            self.assertEqual(s.stdout.strip(), fpr, s.stderr)


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
        r = self.seul("fournisseurs-json", NC_OS_RELEASE=str(self.r / "os-release"), **plus)
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
        self.assertEqual(k[4:], [str(self.r / "faux-bin" / "bash"), str(REPO / "home/.local/libexec/nc-vpn-installer"), "proton"])

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

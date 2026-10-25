"""nc-logiciels : état « installé » demandé après tri et coupe (Debian, Fedora), flatpak filtré sur tous les mots,
langue lue comme dans nc-meteo. De faux apt-cache, dpkg-query, dnf, rpm et flatpak dans le PATH ; HOME temporaire."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
BIN = REPO / "home/.local/bin"

# 100 paquets « aaa-NNN » (avant vlc dans l'ordre alphabétique) puis vlc
FAUX_APT_CACHE = """#!/bin/sh
i=0; while [ $i -lt 100 ]; do printf 'aaa-%03d - outil sans rapport avec vlc\\n' $i; i=$((i+1)); done
echo 'vlc - lecteur multimédia'
"""
FAUX_DPKG = """#!/bin/sh
echo "dpkg-query $*" | tr -d '\n' >> "$HOME/appels"; echo >> "$HOME/appels"
for n in "$@"; do case "$n" in vlc) echo "vlc ii ";; esac; done
"""
FAUX_DNF = """#!/bin/sh
i=0; while [ $i -lt 100 ]; do printf 'aaa-%03d.x86_64 : outil sans rapport avec vlc\\n' $i; i=$((i+1)); done
echo 'vlc.x86_64 : lecteur multimédia'
"""
FAUX_RPM = """#!/bin/sh
echo "rpm $*" | tr -d '\n' >> "$HOME/appels"; echo >> "$HOME/appels"
for n in "$@"; do case "$n" in vlc) echo vlc;; esac; done
"""
FAUX_FLATPAK = """#!/bin/sh
case "$1" in
  search) printf 'org.exemple.Foot\\tFootball\\tJeu de football\\t1\\tflathub\\norg.exemple.Zz\\tFootball Zzzzqq\\tAutre\\t1\\tflathub\\n' ;;
  list) ;;
esac
"""


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        self.bin = self.home / "bin"; self.bin.mkdir()
        for outil in ("sh", "env", "python3", "cat", "printf", "tr"):
            if shutil.which(outil):
                (self.bin / outil).symlink_to(shutil.which(outil))
        (self.home / ".config/nc").mkdir(parents=True)
        self.env = dict(HOME=str(self.home), PATH=str(self.bin), NC_LANGUE="fr", XDG_CACHE_HOME=str(self.home / "cache"))

    def faux(self, **outils):
        for nom, code in outils.items():
            (self.bin / nom.replace("_", "-")).write_text(code); (self.bin / nom.replace("_", "-")).chmod(0o755)

    def lancer(self, *args):
        return subprocess.run([str(BIN / "nc-logiciels"), *args], env=self.env, capture_output=True, text=True, timeout=20)

    def chercher(self, terme):
        r = self.lancer("chercher", terme)
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)


class Installe(Base):
    def verifier(self, attendu_appel):
        res = self.chercher("vlc")
        vlc = next(x for x in res if x["nom"] == "vlc")
        self.assertTrue(vlc["installe"], "vlc installé, même après 100 paquets venus avant lui")
        self.assertEqual(res[0]["nom"], "vlc", "le plus pertinent d'abord")
        appels = (self.home / "appels").read_text().splitlines()
        self.assertEqual(len(appels), 1, "un seul appel : %r" % appels)
        self.assertTrue(appels[0].startswith(attendu_appel))
        self.assertLessEqual(len(appels[0].split()), 31 + 3, "au plus 30 noms interrogés")

    def test_debian(self):
        self.faux(apt_get="#!/bin/sh\n", apt_cache=FAUX_APT_CACHE, dpkg_query=FAUX_DPKG)
        self.verifier("dpkg-query")

    def test_fedora(self):
        self.faux(dnf=FAUX_DNF, rpm=FAUX_RPM)
        self.verifier("rpm")


class FlatpakMots(Base):
    def test_tous_les_mots(self):
        self.faux(flatpak=FAUX_FLATPAK)
        noms = [x["nom"] for x in self.chercher("football zzzzqq")]
        self.assertEqual(noms, ["org.exemple.Zz"], "flatpak ne cherche que le premier mot : on filtre sur tous")
        self.assertEqual(len(self.chercher("football")), 2)


class Langue(Base):
    def erreur(self, **env):
        e = {k: v for k, v in self.env.items() if k != "NC_LANGUE"}
        e.update(env)
        r = subprocess.run([str(BIN / "nc-logiciels"), "installer", "depot", "mauvais nom"], env=e, capture_output=True, text=True, timeout=20)
        return r.stdout + r.stderr

    def test_lang_du_systeme(self):
        conf = self.home / "locale.conf"; conf.write_text("")
        self.assertIn("invalid package name", self.erreur(LANG="en_US.UTF-8", NC_LOCALE_CONF=str(conf)))
        self.assertIn("nom de paquet invalide", self.erreur(LANG="fr_FR.UTF-8", NC_LOCALE_CONF=str(conf)))
        conf.write_text('LANG="fr_FR.UTF-8"\n')
        self.assertIn("nom de paquet invalide", self.erreur(NC_LOCALE_CONF=str(conf)), "repli sur /etc/locale.conf")

    def test_reglage_et_nc_langue_passent_avant(self):
        (self.home / ".config/nc/reglages.conf").write_text('LANGUE="en"\n')
        self.assertIn("invalid package name", self.erreur(LANG="fr_FR.UTF-8"))
        self.assertIn("nom de paquet invalide", self.erreur(LANG="en_US.UTF-8", NC_LANGUE="fr"))


if __name__ == "__main__":
    unittest.main()

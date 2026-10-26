"""Lot Maj-Écrans, partie musique : nc-ile-etat ne fait pas « media » pour l'île Quickshell (sans-media), suit
playerctld (-p), garde un marqueur d'échec de 5 minutes pour la pochette, nettoie à 50 fichiers, limite curl à http(s) et 5 Mo ;
nc-verrou-media compare le nom du lecteur tel quel (pas une regex) et limite curl pareillement. Faux playerctl, busctl,
curl et nc-apps dans un dossier temporaire ; HOME isolé."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
ETAT = REPO / "home/.local/bin/nc-ile-etat"
VERROU = REPO / "home/.local/bin/nc-verrou-media"
ETAT_QML = REPO / "home/.config/quickshell/nc-ile/Etat.qml"
SEP = "\\037"


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="nc-media-lot-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.bin = self.tmp / "bin"
        self.bin.mkdir()
        self.home = self.tmp / "home"
        (self.home / ".cache").mkdir(parents=True)
        (self.home / ".local/bin").mkdir(parents=True)
        self.journal = self.tmp / "journal"
        self.faux("playerctl", 'echo "playerctl $*" >> "$J"; case "$*" in *metadata*) printf "%s\\n" "$SORTIE" ;; esac')
        self.faux("curl", 'echo "curl $*" >> "$J"; exit "${CURL_CODE:-0}"')
        self.faux("busctl", 'echo \'as 2 "org.mpris.MediaPlayer2.mpv" "org.mpris.MediaPlayer2.firefox"\'')

    def faux(self, nom, corps):
        f = self.bin / nom
        f.write_text("#!/bin/sh\n" + corps + "\n")
        f.chmod(0o755)

    def lancer(self, script, *args, sortie=None, **env):
        e = dict(os.environ, HOME=str(self.home), XDG_CACHE_HOME=str(self.home / ".cache"), TMPDIR=str(self.tmp),
                 XDG_RUNTIME_DIR=str(self.tmp), J=str(self.journal), PATH=f"{self.bin}:{os.environ['PATH']}", **env)
        if sortie is not None:
            e["SORTIE"] = sortie
        return subprocess.run(["bash", str(script), *args], env=e, capture_output=True, text=True, timeout=30,
                              stdin=subprocess.DEVNULL)

    def lignes(self):
        return self.journal.read_text().splitlines() if self.journal.exists() else []


class Etat(Base):
    SORTIE = "Playing\x1fTitre\x1fMoi\x1fhttps://exemple.invalid/p.jpg\x1f1000000\x1fmpv\x1f42000000"

    def test_sans_media_ne_lance_pas_playerctl(self):
        r = self.lancer(ETAT, "sans-media", sortie=self.SORTIE)
        self.assertNotIn("media=", r.stdout)
        self.assertEqual([l for l in self.lignes() if l.startswith(("playerctl", "curl"))], [])

    def test_l_ile_quickshell_demande_sans_media(self):
        self.assertIn('"nc-ile-etat", "sans-media"', ETAT_QML.read_text())

    def test_media_suit_playerctld_et_position_en_une_fois(self):
        r = self.lancer(ETAT, "media", sortie=self.SORTIE, CURL_CODE="1")
        pc = [l for l in self.lignes() if l.startswith("playerctl")]
        self.assertEqual(len(pc), 1, pc)
        self.assertIn("-p mpv", pc[0])
        self.assertIn("media_position=42", r.stdout)
        self.assertIn("media_joueur=mpv", r.stdout)

    def test_curl_limite_et_echec_retenu_5_minutes(self):
        self.lancer(ETAT, "media", sortie=self.SORTIE, CURL_CODE="1")
        curl = [l for l in self.lignes() if l.startswith("curl")]
        self.assertEqual(len(curl), 1)
        self.assertIn("--proto =http,https", curl[0])
        self.assertIn("--max-filesize 5M", curl[0])
        self.assertTrue(list((self.home / ".cache/nc/pochettes").glob("*.echec")))
        self.lancer(ETAT, "media", sortie=self.SORTIE, CURL_CODE="1")
        self.assertEqual(len([l for l in self.lignes() if l.startswith("curl")]), 1, "pas de nouveau curl pendant 5 minutes")

    def test_menage_a_50_fichiers(self):
        d = self.home / ".cache/nc/pochettes"
        d.mkdir(parents=True)
        for i in range(70):
            f = d / f"vieux{i:03d}.img"
            f.write_text("x")
            os.utime(f, (1000 + i, 1000 + i))
        self.lancer(ETAT, "media", sortie=self.SORTIE, CURL_CODE="1")
        restes = [p for p in d.iterdir() if not p.name.endswith(".lock")]
        self.assertLessEqual(len(restes), 50, len(restes))


class Verrou(Base):
    SORTIE = "Playing\x1fTitre\x1fMoi\x1fhttps://exemple.invalid/p.jpg\x1f1000000\x1f42000000\x1fa*b"

    def test_nom_du_lecteur_pas_une_regex(self):
        icones = self.home / ".cache/nc/icones-lecteurs"
        icones.parent.mkdir(parents=True)
        (self.home / "ic-x.png").write_text("x")
        (self.home / "ic-y.png").write_text("y")
        icones.write_text(f"aab\t{self.home}/ic-x.png\na*b\t{self.home}/ic-y.png\n")
        r = self.lancer(VERROU, sortie=self.SORTIE, CURL_CODE="1")
        champs = r.stdout.rstrip("\n").split("\t")
        self.assertEqual(champs[6], "a*b", r.stdout + r.stderr)
        self.assertEqual(champs[7], f"{self.home}/ic-y.png")

    def test_nom_avec_barre_oblique_inverse(self):
        icones = self.home / ".cache/nc/icones-lecteurs"
        icones.parent.mkdir(parents=True)
        (self.home / "ic.png").write_text("x")
        icones.write_text(f"a\\tb\t{self.home}/ic.png\n")
        sortie = self.SORTIE.replace("a*b", "a\\tb")
        r = self.lancer(VERROU, sortie=sortie, CURL_CODE="1")
        self.assertEqual(r.stdout.rstrip("\n").split("\t")[7], f"{self.home}/ic.png", r.stdout + r.stderr)

    def test_curl_limite_a_http_et_5_mo(self):
        self.faux("curl", 'echo "curl $*" >> "$J"; exit 1')
        self.lancer(VERROU, sortie=self.SORTIE)
        for _ in range(20):                                   # le téléchargement part en arrière-plan
            if any(l.startswith("curl") for l in self.lignes()):
                break
            subprocess.run(["sleep", "0.2"])
        curl = [l for l in self.lignes() if l.startswith("curl")]
        self.assertTrue(curl, self.lignes())
        self.assertIn("--proto =http,https", curl[0])
        self.assertIn("--max-filesize 5M", curl[0])


if __name__ == "__main__":
    unittest.main()

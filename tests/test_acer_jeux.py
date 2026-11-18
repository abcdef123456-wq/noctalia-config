"""Lot A3 : nc-gpu-jeu (hook gamemode), fusion de gamemode.ini et MangoHud de install.sh.
Faux sudo, faux assistant root et faux /sys seulement : rien de réel n'est lancé."""
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BIN = REPO / "home/.local/bin"
INSTALL = (REPO / "install.sh").read_text()
NITRO = "Nitro ANV16-72"


def fonction(nom):
    m = re.search(r"(?ms)^%s\(\) \{.*?^\}\n" % nom, INSTALL)
    assert m, nom
    return m.group(0)


class Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.d = Path(self._tmp.name)
        self.home = self.d / "home"
        self.faux = self.d / "faux"
        self.sysf = self.d / "sys"
        for p in (self.home / ".config", self.faux, self.sysf / "class/dmi/id", self.d / "tmp"):
            p.mkdir(parents=True)
        self.journal = self.d / "journal"
        self.journal.touch()
        sudo = self.faux / "sudo"
        sudo.write_text('#!/bin/bash\necho "sudo $*" >> "$JOURNAL"\n[ "$1" = -n ] || exit 1\nshift\nexec "$@"\n')
        sudo.chmod(0o755)
        self.root = self.d / "nc-energie-root"
        self.root.write_text('#!/bin/bash\necho "assistant $*" >> "$JOURNAL"\n')
        self.root.chmod(0o755)
        self.env = {
            "HOME": str(self.home), "PATH": f"{self.faux}:/usr/bin:/bin", "NC_LANGUE": "fr",
            "JOURNAL": str(self.journal), "NC_SYSFS": str(self.sysf), "TMPDIR": str(self.d / "tmp"),
            "XDG_CONFIG_HOME": str(self.home / ".config"), "XDG_RUNTIME_DIR": str(self.d / "run"),
            "NC_ENERGIE_ROOT_CHEMIN": str(self.root), "NC_PROFIL": "performance",
        }

    def dmi(self, nom):
        (self.sysf / "class/dmi/id/product_name").write_text(nom + "\n")

    def reglages(self, texte):
        (self.home / ".config/nc-profile.conf").write_text(texte)

    def jeu(self, arg, **env):
        e = {**self.env, **env}
        for k in [k for k, v in e.items() if v is None]:
            del e[k]
        return subprocess.run(["bash", str(BIN / "nc-gpu-jeu"), arg], env=e, capture_output=True,
                              text=True, timeout=30, stdin=subprocess.DEVNULL)

    def appels(self):
        return [l for l in self.journal.read_text().splitlines() if l]


class GpuJeu(Base):
    def test_debut_performance_pose_la_limite(self):
        self.dmi(NITRO)
        r = self.jeu("debut")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.appels(), [f"sudo -n {self.root} gpu-frequence jeu",
                                         f"assistant gpu-frequence jeu"])

    def test_debut_hors_performance_ne_fait_rien(self):
        self.dmi(NITRO)
        r = self.jeu("debut", NC_PROFIL="balanced")
        self.assertEqual(r.returncode, 0)
        self.assertEqual(self.appels(), [])

    def test_debut_reglage_off_ne_fait_rien(self):
        self.dmi(NITRO)
        self.reglages("JEU_GPU_MHZ=off\n")
        self.assertEqual(self.jeu("debut").returncode, 0)
        self.assertEqual(self.appels(), [])

    def test_fin_remet_normal_meme_hors_performance(self):
        self.dmi(NITRO)
        self.assertEqual(self.jeu("fin", NC_PROFIL="balanced").returncode, 0)
        self.assertEqual(self.appels()[-1], "assistant gpu-frequence normal")

    def test_sans_assistant_silencieux(self):
        self.dmi(NITRO)
        r = self.jeu("debut", NC_ENERGIE_ROOT_CHEMIN=str(self.d / "absent"))
        self.assertEqual((r.returncode, r.stdout, r.stderr), (0, "", ""))
        self.assertEqual(self.appels(), [])

    def test_argument_invalide(self):
        self.assertEqual(self.jeu("dehors").returncode, 2)
        self.assertEqual(self.appels(), [])

    def test_autre_dmi_sans_reglage(self):
        self.dmi("Legion 5")
        self.assertEqual(self.jeu("debut").returncode, 0)
        self.assertEqual(self.jeu("fin").returncode, 0)
        self.assertEqual(self.appels(), [])

    def test_autre_dmi_avec_reglage_ecrit(self):
        self.dmi("Legion 5")
        self.reglages('JEU_GPU_MHZ="1500"\n')
        self.jeu("debut")
        self.assertEqual(self.appels()[-1], "assistant gpu-frequence jeu")

    def test_nc_jeu_gpu_mhz_valeurs(self):
        """nc_jeu_gpu_mhz (seule lecture de JEU_GPU_MHZ) : défaut du DMI, réglage écrit, guillemets, \\r, valeur invalide ;
        même réponse en bash et en sh POSIX (dash s'il est là : nc-gpu-regle est sourcé par des scripts sh)."""
        coquilles = ["bash"] + [s for s in ("dash",) if shutil.which(s)] + ["sh"]
        for dmi, conf, attendu in [(NITRO, "", "1500"), ("Legion 5", "", "off"), (NITRO, "JEU_GPU_MHZ=off\n", "off"),
                                   ("Legion 5", "JEU_GPU_MHZ=1500\n", "1500"), (NITRO, "JEU_GPU_MHZ=999\n", "1500"),
                                   ("Legion 5", 'JEU_GPU_MHZ="1500"\r\n', "1500"), ("Legion 5", "JEU_GPU_MHZ= 1500 \n", "1500")]:
            for c in coquilles:
                with self.subTest(dmi=dmi, conf=conf, coquille=c):
                    self.dmi(dmi)
                    self.reglages(conf)
                    lu = subprocess.run([c, "-c", f'. "{BIN}/nc-gpu-regle"; nc_jeu_gpu_mhz'], env=self.env,
                                        capture_output=True, text=True).stdout.strip()
                    self.assertEqual(lu, attendu)

    def test_nc_profile_sync_ne_lit_plus_jeu_gpu_mhz(self):
        self.assertNotIn("JEU_GPU_MHZ=", (BIN / "nc-profile-sync").read_text())

class Fusion(Base):
    def setUp(self):
        super().setUp()
        self.modele = REPO / "home/.config/gamemode.ini"
        self.bk = self.d / "bk"
        self.bk.mkdir()
        self.gm = self.home / ".config/gamemode.ini"

    def sh(self, corps, extra=None):
        script = ("set -u\nt(){ printf '%s' \"$1\"; }\ninfo(){ echo \"INFO: $*\"; }\nhave(){ command -v \"$1\" >/dev/null; }\n"
                  + fonction("backup") + fonction("ecrire_atomique") + fonction("fusion_gamemode") + fonction("fournir_jeux")
                  + corps)
        e = {**self.env, "BK": str(self.bk), **(extra or {})}
        return subprocess.run(["bash", "-c", script], env=e, capture_output=True, text=True, timeout=30)

    def fusion(self):
        return self.sh(f'fusion_gamemode "{self.gm}" "{self.modele}"')

    def test_modele_sans_gpu_et_gouverneur_vide(self):
        txt = self.modele.read_text()
        self.assertNotRegex(txt, r"(?m)^\s*\[gpu\]")
        self.assertRegex(txt, r"(?m)^desiredgov=\s*$")
        self.assertIn("$HOME/.local/bin/nc-gpu-jeu debut", txt)

    def test_fichier_absent_donne_le_modele(self):
        (self.faux / "gamemoderun").write_text("#!/bin/sh\n")
        (self.faux / "gamemoderun").chmod(0o755)
        r = self.sh(f'root="{REPO}/home"; fournir_jeux')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.gm.read_text(), self.modele.read_text())
        self.assertIn(".config/gamemode.ini", (self.bk / ".created").read_text())

    def test_fusion_garde_l_existant(self):
        self.gm.write_text("[general]\ndesiredgov=performance\nreaper_freq=5\n\n[cpu]\npark_cores=no\n")
        r = self.fusion()
        self.assertEqual(r.returncode, 0, r.stderr)
        txt = self.gm.read_text()
        self.assertIn("desiredgov=performance", txt)
        self.assertIn("reaper_freq=5", txt)
        self.assertIn("park_cores=no", txt)
        self.assertNotRegex(txt, r"(?m)^\s*\[gpu\]")
        self.assertEqual(len(re.findall(r"(?m)^\[custom\]", txt)), 1)
        self.assertRegex(txt, r"(?m)^start=\$HOME/\.local/bin/nc-gpu-jeu debut$")
        self.assertRegex(txt, r"(?m)^end=\$HOME/\.local/bin/nc-gpu-jeu fin$")

    def test_fusion_dans_custom_existant(self):
        self.gm.write_text("[custom]\nautre=1\n\n[cpu]\nx=y\n")
        self.fusion()
        txt = self.gm.read_text()
        self.assertEqual(len(re.findall(r"(?m)^\[custom\]", txt)), 1)
        self.assertLess(txt.index("start="), txt.index("[cpu]"))

    def test_start_deja_pose_pas_touche(self):
        self.gm.write_text("[custom]\nstart=notify-send hop\n")
        r = self.fusion()
        txt = self.gm.read_text()
        self.assertIn("start=notify-send hop", txt)
        self.assertNotIn("nc-gpu-jeu debut", txt)
        self.assertIn("end=", txt)  # end manquait : il est ajouté
        self.assertIn("INFO:", r.stdout)
        self.assertIn("start=", r.stdout)

    def test_deux_passages_sans_doublon_et_sauvegarde(self):
        (self.faux / "gamemoderun").write_text("#!/bin/sh\n")
        (self.faux / "gamemoderun").chmod(0o755)
        original = "[general]\ndesiredgov=performance\n"
        self.gm.write_text(original)
        for _ in range(2):
            r = self.sh(f'root="{REPO}/home"; fournir_jeux')
            self.assertEqual(r.returncode, 0, r.stderr)
        txt = self.gm.read_text()
        self.assertEqual(txt.count("start="), 1)
        self.assertEqual(txt.count("end="), 1)
        self.assertTrue((self.bk / ".config/gamemode.ini").exists())

    def test_sans_gamemode_rien_n_est_cree(self):
        r = self.sh(f'root="{REPO}/home"; fournir_jeux')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertFalse(self.gm.exists())


class MangoHud(Fusion):
    def setUp(self):
        super().setUp()
        (self.faux / "mangohud").write_text("#!/bin/sh\n")
        (self.faux / "mangohud").chmod(0o755)
        self.mh = self.home / ".config/MangoHud/MangoHud.conf"

    def test_fourni_si_absent(self):
        self.assertEqual(self.sh(f'root="{REPO}/home"; fournir_jeux').returncode, 0)
        self.assertEqual(self.mh.read_text(), (REPO / "home/.config/MangoHud/MangoHud.conf").read_text())

    def test_jamais_ecrase(self):
        self.mh.parent.mkdir()
        self.mh.write_text("fps_only\n")
        self.sh(f'root="{REPO}/home"; fournir_jeux')
        self.assertEqual(self.mh.read_text(), "fps_only\n")

    def test_sans_mangohud_rien(self):
        (self.faux / "mangohud").unlink()
        self.sh(f'root="{REPO}/home"; fournir_jeux')
        self.assertFalse(self.mh.exists())


if __name__ == "__main__":
    unittest.main()

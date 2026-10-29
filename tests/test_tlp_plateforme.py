"""nc-tlp-plateforme : le fichier TLP des profils de la plateforme est choisi d'après les choix du noyau de CE portable
(faux /sys, faux defaults.conf de TLP), avec les suffixes de la version : _AC/_BAT (TLP 1.9 et 1.10) ou _PRF/_BAL (1.11).
Un portable sans « low-power » (quiet, cool) ou sans « performance » (balanced-performance) garde un profil utile."""
from pathlib import Path
import os
import re
import shutil
import subprocess
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "system/nc-tlp-plateforme"

DEFAUTS_110 = "TLP_ENABLE=1\nPLATFORM_PROFILE_ON_AC=performance\nPLATFORM_PROFILE_ON_BAT=balanced\nPLATFORM_PROFILE_ON_SAV=low-power\n"
DEFAUTS_111 = ('TLP_ENABLE=1\nPLATFORM_PROFILE_ON_PRF="balanced-performance performance"\nPLATFORM_PROFILE_ON_BAL="balanced"\n'
               'PLATFORM_PROFILE_ON_SAV="low-power cool quiet"\n')


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="nc-tlp-pf-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def lancer(self, choix, defauts=DEFAUTS_110):
        sysfs = self.tmp / "sys"
        shutil.rmtree(sysfs, True)
        if choix is not None:
            f = sysfs / "firmware/acpi/platform_profile_choices"
            f.parent.mkdir(parents=True)
            f.write_text(choix + "\n")
        d = self.tmp / "defaults.conf"
        d.write_text(defauts)
        r = subprocess.run([str(SCRIPT)], capture_output=True, text=True, timeout=30,
                           env={"PATH": "/usr/bin:/bin", "NC_SYSFS": str(sysfs), "NC_TLP_DEFAUTS": str(d)})
        valeurs = {}
        for l in r.stdout.splitlines():
            if l.startswith("PLATFORM_PROFILE_ON_"):
                k, _, v = l.partition("=")
                valeurs[k] = v
        return r, valeurs


class Choix(Base):
    def test_profils_standard(self):
        r, v = self.lancer("low-power balanced performance")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(v, {"PLATFORM_PROFILE_ON_AC": "performance", "PLATFORM_PROFILE_ON_BAT": "balanced",
                             "PLATFORM_PROFILE_ON_SAV": "low-power"})

    def test_quiet_a_la_place_de_low_power(self):
        _, v = self.lancer("quiet balanced performance")
        self.assertEqual(v["PLATFORM_PROFILE_ON_SAV"], "quiet")

    def test_cool_a_la_place_de_low_power(self):
        _, v = self.lancer("cool balanced performance")
        self.assertEqual(v["PLATFORM_PROFILE_ON_SAV"], "cool")

    def test_low_power_garde_la_priorite(self):
        _, v = self.lancer("cool quiet low-power balanced")
        self.assertEqual(v["PLATFORM_PROFILE_ON_SAV"], "low-power")

    def test_balanced_performance_a_la_place_de_performance(self):
        _, v = self.lancer("low-power balanced balanced-performance")
        self.assertEqual(v["PLATFORM_PROFILE_ON_AC"], "balanced-performance")

    def test_performance_garde_la_priorite(self):
        _, v = self.lancer("low-power balanced balanced-performance performance")
        self.assertEqual(v["PLATFORM_PROFILE_ON_AC"], "performance")

    def test_style_acer_nitro_quiet_et_balanced_performance(self):
        r, v = self.lancer("low-power quiet balanced balanced-performance performance")
        self.assertEqual(v["PLATFORM_PROFILE_ON_SAV"], "low-power")
        r, v = self.lancer("quiet balanced balanced-performance")
        self.assertEqual(v, {"PLATFORM_PROFILE_ON_AC": "balanced-performance", "PLATFORM_PROFILE_ON_BAT": "balanced",
                             "PLATFORM_PROFILE_ON_SAV": "quiet"})

    def test_aucun_profil_compatible_n_ecrit_rien(self):
        for choix in ("custom", "max-power", "inconnu autre", ""):
            r, v = self.lancer(choix)
            self.assertEqual(r.returncode, 3, choix)
            self.assertEqual(r.stdout, "", choix)

    def test_un_profil_sans_equivalent_n_est_pas_ecrit(self):
        r, v = self.lancer("balanced")
        self.assertEqual(v, {"PLATFORM_PROFILE_ON_BAT": "balanced"})
        r, v = self.lancer("quiet performance")      # pas de balanced : rien pour l'Équilibré, TLP garde son défaut
        self.assertNotIn("PLATFORM_PROFILE_ON_BAT", v)

    def test_max_power_jamais_choisi(self):
        r, v = self.lancer("low-power balanced performance max-power")
        self.assertNotIn("max-power", "".join(v.values()))

    def test_pas_de_profil_de_plateforme(self):
        r, v = self.lancer(None)
        self.assertEqual(r.returncode, 3)
        self.assertEqual(r.stdout, "")

    def test_texte_etranger_ignore(self):
        r, v = self.lancer("low-power; rm -rf /x $(id) balanced `id` performance")
        self.assertEqual(r.returncode, 0)
        for l in r.stdout.splitlines():
            if not l.startswith("#"):
                self.assertRegex(l, r"^PLATFORM_PROFILE_ON_[A-Z]+=[a-z-]+$")
        self.assertNotIn("$(", r.stdout)
        self.assertNotIn("`", r.stdout)


class Versions(Base):
    def test_tlp_110_suffixes_ac_bat(self):
        _, v = self.lancer("low-power balanced performance", DEFAUTS_110)
        self.assertEqual(sorted(v), ["PLATFORM_PROFILE_ON_AC", "PLATFORM_PROFILE_ON_BAT", "PLATFORM_PROFILE_ON_SAV"])

    def test_tlp_111_suffixes_prf_bal(self):
        r, v = self.lancer("quiet balanced balanced-performance", DEFAUTS_111)
        self.assertEqual(v, {"PLATFORM_PROFILE_ON_PRF": "balanced-performance", "PLATFORM_PROFILE_ON_BAL": "balanced",
                             "PLATFORM_PROFILE_ON_SAV": "quiet"})
        self.assertNotIn("_ON_AC", r.stdout)       # l'ancien nom remplacerait la liste de TLP par une seule valeur
        self.assertNotIn("_ON_BAT", r.stdout)

    def test_defauts_illisibles_anciens_suffixes(self):
        sysfs = self.tmp / "sys2/firmware/acpi"
        sysfs.mkdir(parents=True)
        (sysfs / "platform_profile_choices").write_text("low-power balanced performance\n")
        r = subprocess.run([str(SCRIPT)], capture_output=True, text=True, timeout=30,
                           env={"PATH": "/usr/bin:/bin", "NC_SYSFS": str(self.tmp / "sys2"), "NC_TLP_DEFAUTS": str(self.tmp / "absent")})
        self.assertIn("PLATFORM_PROFILE_ON_AC=performance", r.stdout)


class Garde(Base):
    """Garde finale d'install.sh (plat_valide) avant « sudo install » du fichier de la plateforme."""
    def valide(self, texte):
        source = (REPO / "install.sh").read_text()
        m = re.search(r"(?ms)^  plat_valide\(\) \{.*?^  \}\n", source)
        self.assertIsNotNone(m)
        return subprocess.run(["bash", "-c", m.group(0) + "\nplat_valide"], input=texte.encode("utf-8"), capture_output=True,
                              timeout=30).returncode == 0

    def test_la_sortie_du_generateur_passe_la_garde(self):
        for choix in ("low-power balanced performance", "quiet balanced balanced-performance", "cool balanced", "balanced",
                      "low-power quiet cool balanced balanced-performance performance"):
            for defauts in (DEFAUTS_110, DEFAUTS_111):
                r, _ = self.lancer(choix, defauts)
                self.assertEqual(r.returncode, 0)
                self.assertTrue(self.valide(r.stdout), (choix, r.stdout))

    def test_fichiers_pieges_refuses(self):
        bon = "# commentaire (ok)\nPLATFORM_PROFILE_ON_AC=performance\nPLATFORM_PROFILE_ON_SAV=quiet\n"
        self.assertTrue(self.valide(bon))
        for piege in (bon + "PLATFORM_PROFILE_ON_AC=quiet\n",                      # clé en double
                      bon + "PLATFORM_PROFILE_ON_BAT=max-power\n",                  # valeur hors liste
                      bon + "PLATFORM_PROFILE_ON_BAT=balanced; id\n",               # texte collé
                      bon + "PLATFORM_PROFILE_ON_BAT=balanced\x01\n",              # caractère de contrôle
                      bon + "PLATFORM_PROFILE_ON_BAT=balanced\r\n",
                      bon + "\n",                                                   # ligne vide
                      bon + "TLP_ENABLE=0\n",                                       # autre clé
                      bon + "PLATFORM_PROFILE_ON_XYZ=quiet\n",
                      bon + "PLATFORM_PROFILE_ON_BAT=\"balanced\"\n",
                      "# commentaire é accentué\nPLATFORM_PROFILE_ON_AC=quiet\n",
                      "# $(id)\nPLATFORM_PROFILE_ON_AC=quiet\n",
                      "#!/bin/sh\nPLATFORM_PROFILE_ON_AC=quiet\n",
                      "# seulement un commentaire\n", ""):
            self.assertFalse(self.valide(piege), repr(piege))

    def test_le_generateur_ignore_l_environnement_d_essai(self):
        source = (REPO / "install.sh").read_text()
        self.assertIn('env -u NC_SYSFS -u NC_TLP_DEFAUTS "$REPO/system/nc-tlp-plateforme"', source)

    def test_motifs_non_developpes_et_fichier_sans_retour_a_la_ligne(self):
        sysfs = self.tmp / "sys"
        f = sysfs / "firmware/acpi/platform_profile_choices"
        f.parent.mkdir(parents=True)
        f.write_text("* quiet ? balanced")                       # pas de retour à la ligne final
        (self.tmp / "quiet").touch()
        d = self.tmp / "defaults.conf"
        d.write_text(DEFAUTS_110)
        r = subprocess.run([str(SCRIPT)], capture_output=True, text=True, cwd=str(self.tmp),
                           env={"PATH": "/usr/bin:/bin", "NC_SYSFS": str(sysfs), "NC_TLP_DEFAUTS": str(d)})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("PLATFORM_PROFILE_ON_SAV=quiet", r.stdout)
        self.assertIn("PLATFORM_PROFILE_ON_BAT=balanced", r.stdout)
        self.assertNotIn("PLATFORM_PROFILE_ON_AC", r.stdout)


class Depot(unittest.TestCase):
    def test_10_nc_ne_regle_plus_la_plateforme(self):
        conf = (REPO / "system/tlp.d/10-nc.conf").read_text()
        for l in conf.splitlines():
            self.assertFalse(l.startswith("PLATFORM_PROFILE_ON_"), l)

    def test_install_ecrit_le_fichier_et_garde_les_choix_perso(self):
        source = (REPO / "install.sh").read_text()
        self.assertIn("system/nc-tlp-plateforme", source)
        self.assertIn("/etc/tlp.d/12-nc-plateforme.conf", source)
        self.assertIn("12-nc-plateforme|", source)                # pas pris pour un réglage perso
        self.assertIn("PLATFORM_PROFILE_ON_[A-Z]+", source)
        self.assertIn("sudo grep -qsE", source)               # un fichier perso en 0600 est lu aussi       # un réglage de l'utilisateur reste

    def test_script_executable(self):
        self.assertTrue(os.access(SCRIPT, os.X_OK))


if __name__ == "__main__":
    unittest.main()

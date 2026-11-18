"""Lot A2 : profils Acer Nitro (RAPL, Turbo, ventilateurs) dans nc-profile-sync, commande nc-turbo,
NC_PERF_PLATEFORME de nc-tlp-plateforme et les 3 réglages de nc-reglages. Faux /sys et faux outils seulement."""
import importlib.machinery
import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_profile_sync as tps  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
BIN = REPO / "home/.local/bin"
TLP = REPO / "system/nc-tlp-plateforme"
NITRO = "Nitro ANV16-72"


class Jeu(tps.ProfileSync):
    """Banc de nc-profile-sync avec un faux /sys de plateforme (NC_SYSFS)."""

    def setUp(self):
        super().setUp()
        self.sysf = self.home / "sysf"
        self.env_plus["NC_SYSFS"] = str(self.sysf)
        self.plateforme("Autre PC", nitro=False)
        self.script = tps.SCRIPT

    def plateforme(self, dmi, nitro, choix="low-power quiet balanced balanced-performance performance"):
        (self.sysf / "class/dmi/id").mkdir(parents=True, exist_ok=True)
        (self.sysf / "class/dmi/id/product_name").write_text(dmi + "\n")
        (self.sysf / "firmware/acpi").mkdir(parents=True, exist_ok=True)
        (self.sysf / "firmware/acpi/platform_profile").write_text("balanced\n")
        (self.sysf / "firmware/acpi/platform_profile_choices").write_text(choix + "\n")
        n = self.sysf / "devices/platform/x/nitro_sense"
        if nitro:
            n.mkdir(parents=True, exist_ok=True)
            (n / "fan_speed").write_text("0,0\n")

    def turbo(self, oui=True):
        f = self.home / ".config/nc/turbo"
        f.write_text("") if oui else f.unlink()

    def jeu(self, profil="performance"):
        self.lancer(profil)
        return [l for l in self.appels() if l.startswith(("assistant rapl", "assistant platform", "assistant ventilateurs"))]

    def deux(self, profils):
        """Plusieurs passages dans le même processus ; profils : liste de (profil, en_secteur)."""
        m = self.script.read_text().split("rm -f \"$GPU_STATE\" \"$RTX_GUET\"\napply\n", 1)
        self.assertEqual(len(m), 2)
        lien = self.home / "nc-gpu-regle"
        if not lien.exists():
            lien.symlink_to(tps.BIN / "nc-gpu-regle")
        corps = m[0]
        for p, sect, *avant in profils:   # avant : une commande lancée juste avant ce passage (ex. retirer le Turbo)
            corps += "".join(a + "\n" for a in avant)
            corps += f"echo {1 if sect else 0} > {self.alim}/AC/online\nexport NC_TEST_PROFIL={p}\napply\n"
        s = self.home / "passages"
        s.write_text(corps)
        self.journal.write_text("")
        env = dict(HOME=str(self.home), PATH=f"{self.faux}:/usr/bin:/bin", NC_LANGUE="fr", JOURNAL=str(self.journal),
                   XDG_RUNTIME_DIR=str(self.run_dir), XDG_CONFIG_HOME=str(self.home / ".config"),
                   NC_POWER_SUPPLY=str(self.alim), NC_LEDS=str(self.leds), NC_TEST_PROFIL="balanced",
                   NC_ENERGIE_ROOT_CHEMIN=str(self.home / "nc-energie-root"), **self.env_plus)
        subprocess.run(["bash", str(s)], env=env, capture_output=True, text=True, timeout=60, stdin=subprocess.DEVNULL)
        return [l for l in self.appels() if l.startswith(("assistant rapl", "assistant platform", "assistant ventilateurs"))]

    # -- aucun changement
    def test_autre_pc_sans_reglage_aucun_appel(self):
        self.assertEqual(self.jeu("performance"), [])
        self.assertEqual(self.jeu("balanced"), [])

    def test_nitro_equilibre_premier_passage_ventilateurs_auto(self):
        self.plateforme(NITRO, True)
        self.assertEqual(self.jeu("balanced"), ["assistant rapl normal", "assistant ventilateurs auto"])

    # -- Performance
    def test_nitro_performance_secteur(self):
        self.plateforme(NITRO, True)
        self.assertEqual(self.jeu(), ["assistant rapl jeu-30-45", "assistant platform balanced-performance",
                                      "assistant ventilateurs auto"])

    def test_nitro_turbo(self):
        self.plateforme(NITRO, True)
        self.turbo()
        self.assertEqual(self.jeu(), ["assistant rapl jeu-30-45", "assistant platform performance",
                                      "assistant ventilateurs max"])

    def test_turbo_sans_ventilateurs(self):
        self.plateforme(NITRO, True)
        self.turbo()
        self.reglages("TURBO_VENTILOS=non\n")
        self.assertEqual(self.jeu(), ["assistant rapl jeu-30-45", "assistant platform performance",
                                      "assistant ventilateurs auto"])

    def test_turbo_sur_batterie_jamais(self):
        self.plateforme(NITRO, True)
        self.turbo()
        self.secteur(False)
        r = self.jeu()
        self.assertEqual(r, ["assistant rapl normal", "assistant ventilateurs auto"])

    def test_retour_equilibre(self):
        self.plateforme(NITRO, True)
        r = self.deux([("performance", True), ("balanced", True)])
        self.assertEqual(r[-2:], ["assistant rapl normal", "assistant ventilateurs auto"])
        self.assertEqual([l for l in r[3:] if "platform" in l], [])

    def test_deux_passages_identiques_un_seul_appel(self):
        self.plateforme(NITRO, True)
        r = self.deux([("performance", True), ("performance", True)])
        self.assertEqual(len(r), 3, r)

    # -- réglages
    def test_jeu_cpu_off(self):
        self.plateforme(NITRO, True)
        self.reglages("JEU_CPU=off\n")
        # le firmware ne dépend pas de JEU_CPU : balanced-performance en Performance sur secteur
        self.assertEqual(self.jeu(), ["assistant platform balanced-performance", "assistant ventilateurs auto"])

    def test_retrait_du_turbo_remet_balanced_performance(self):
        self.plateforme(NITRO, True)
        self.reglages("JEU_CPU=off\n")
        self.turbo()
        r = self.deux([("performance", True), ("performance", True, f"rm -f {self.home}/.config/nc/turbo")])
        self.assertEqual(r, ["assistant platform performance", "assistant ventilateurs max",
                             "assistant platform balanced-performance", "assistant ventilateurs auto"])

    def test_autre_dmi_avec_nitro_sense_45_65(self):
        self.plateforme("Autre PC", True)
        self.reglages("JEU_CPU=45/65\n")
        r = self.jeu()
        self.assertEqual(r[0], "assistant rapl jeu-45-65")

    def test_valeur_invalide_ignoree(self):
        self.plateforme("Autre PC", False)
        self.reglages("JEU_CPU=99/99\nJEU_GPU_MHZ=abc\nTURBO_VENTILOS=peut-etre\n")
        self.assertEqual(self.jeu(), [])

    def test_sans_nitro_pas_de_ventilateurs(self):
        self.plateforme("Autre PC", False)
        self.reglages("JEU_CPU=30/45\n")
        r = self.jeu()
        # sans nitro_sense : RAPL seulement, jamais le firmware ni les ventilateurs
        self.assertEqual(r, ["assistant rapl jeu-30-45"])

    def test_sans_nitro_aucun_appel_platform_meme_en_turbo(self):
        self.plateforme("Autre PC", False)
        self.turbo()
        for reglage in ("", "JEU_CPU=45/65\n"):
            self.reglages(reglage)
            self.assertEqual([l for l in self.jeu() if "platform" in l], [], reglage)


class Turbo(unittest.TestCase):
    def setUp(self):
        d = tempfile.TemporaryDirectory(prefix="nc-turbo-")
        self.addCleanup(d.cleanup)
        self.home = Path(d.name)
        (self.home / "faux").mkdir()
        s = self.home / "faux/systemctl"
        s.write_text('#!/bin/sh\necho "systemctl $*" >> "$JOURNAL"\n')
        s.chmod(0o755)
        self.journal = self.home / "journal"
        self.fichier = self.home / ".config/nc/turbo"

    def run_turbo(self, *args):
        self.journal.write_text("")
        env = dict(HOME=str(self.home), PATH=f"{self.home}/faux:/usr/bin:/bin", NC_LANGUE="fr", JOURNAL=str(self.journal),
                   XDG_CONFIG_HOME=str(self.home / ".config"))
        return subprocess.run(["bash", str(BIN / "nc-turbo"), *args], env=env, capture_output=True, text=True,
                              timeout=20, stdin=subprocess.DEVNULL)

    def test_on_off_basculer_etat(self):
        self.assertEqual(self.run_turbo("etat").returncode, 0)
        self.assertIn("coupé", self.run_turbo("etat").stdout)
        self.assertEqual(self.run_turbo("on").returncode, 0)
        self.assertTrue(self.fichier.exists())
        self.assertIn("restart nc-profile-sync", self.journal.read_text())
        self.assertIn("activé", self.run_turbo("etat").stdout)
        self.assertEqual(self.run_turbo("basculer").returncode, 0)
        self.assertFalse(self.fichier.exists())
        self.assertEqual(self.run_turbo("basculer").returncode, 0)
        self.assertTrue(self.fichier.exists())
        self.assertEqual(self.run_turbo("off").returncode, 0)
        self.assertFalse(self.fichier.exists())

    def test_valeur_invalide_code_2(self):
        for a in (("tout",), ("",), ()):
            self.assertEqual(self.run_turbo(*a).returncode, 2, a)
        self.assertFalse(self.fichier.exists())


class TlpPlateforme(unittest.TestCase):
    def lancer(self, perf):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            (d / "sys/firmware/acpi").mkdir(parents=True)
            (d / "sys/firmware/acpi/platform_profile_choices").write_text("low-power balanced balanced-performance performance\n")
            (d / "defaults.conf").write_text("PLATFORM_PROFILE_ON_AC=performance\n")
            env = {"PATH": "/usr/bin:/bin", "NC_SYSFS": str(d / "sys"), "NC_TLP_DEFAUTS": str(d / "defaults.conf")}
            if perf is not None:
                env["NC_PERF_PLATEFORME"] = perf
            r = subprocess.run(["bash", str(TLP)], env=env, capture_output=True, text=True, timeout=20)
        return [l for l in r.stdout.splitlines() if l.startswith("PLATFORM_PROFILE_ON_AC")]

    def test_sans_variable_rien_ne_change(self):
        self.assertEqual(self.lancer(None), ["PLATFORM_PROFILE_ON_AC=performance"])

    def test_balanced_performance(self):
        self.assertEqual(self.lancer("balanced-performance"), ["PLATFORM_PROFILE_ON_AC=balanced-performance"])

    def test_valeur_invalide_ignoree(self):
        self.assertEqual(self.lancer("max-power"), ["PLATFORM_PROFILE_ON_AC=performance"])


class Reglages(unittest.TestCase):
    def charger(self, sysfs):
        with tempfile.TemporaryDirectory() as h:
            ancien = dict(os.environ)
            os.environ.update(HOME=h, XDG_CONFIG_HOME=h + "/.config", NC_SYSFS=sysfs)
            try:
                l = importlib.machinery.SourceFileLoader("ncreg_acer", str(BIN / "nc-reglages"))
                s = importlib.util.spec_from_loader("ncreg_acer", l)
                m = importlib.util.module_from_spec(s)
                l.exec_module(m)
            finally:
                os.environ.clear()
                os.environ.update(ancien)
        return m

    def test_trois_reglages_et_turbo_cache_sans_nitro(self):
        with tempfile.TemporaryDirectory() as d:
            m = self.charger(d)
            cles = {r.cle for r in m.REGLAGES}
            for c in ("JEU_CPU", "JEU_GPU_MHZ", "TURBO_VENTILOS"):
                self.assertIn(c, cles)
            visibles = {r.cle for r in m.VISIBLES}
            self.assertNotIn("TURBO_VENTILOS", visibles)
            n = Path(d) / "devices/platform/x/nitro_sense"
            n.mkdir(parents=True)
            (n / "fan_speed").write_text("0\n")
            m2 = self.charger(d)
            self.assertIn("TURBO_VENTILOS", {r.cle for r in m2.VISIBLES})


if __name__ == "__main__":
    unittest.main()

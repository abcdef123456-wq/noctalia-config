"""nc-diag, section Énergie : profil logiciel (service de profils) et mode matériel lu dans /sys, distingués ;
faux /sys (NC_DIAG_SYS) et faux systemctl. Jamais de succès inventé : aucun service, pilote absent, permission refusée,
« custom », contrôleurs en désaccord, profil différent de celui du service."""
from importlib.machinery import SourceFileLoader
from importlib.util import module_from_spec, spec_from_loader
from pathlib import Path
import os
import shutil
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
os.environ.setdefault("NC_LANGUE", "fr")


def charger():
    chemin = str(REPO / "home/.local/bin/nc-diag")
    spec = spec_from_loader("nc_diag_pf", SourceFileLoader("nc_diag_pf", chemin))
    mod = module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def ecrire(chemin, texte):
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(texte + "\n")


class Plateforme(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="nc-diag-pf-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.mod = charger()
        self.mod.EN = False
        self.mod.T = lambda fr, en: fr
        self.mod.SYS = str(self.tmp)
        self.services = set()
        self.mod.sortie = lambda cmd, *a, **k: (("active" if cmd[-1] in self.services else "inactive"), 0)

    def pf(self, courant, choix, ctrls=()):
        ecrire(self.tmp / "firmware/acpi/platform_profile", courant)
        ecrire(self.tmp / "firmware/acpi/platform_profile_choices", choix)
        for i, (nom, profil, ch) in enumerate(ctrls):
            d = self.tmp / f"class/platform-profile/platform-profile-{i}"
            ecrire(d / "name", nom)
            ecrire(d / "profile", profil)
            ecrire(d / "choices", ch)

    def bilan(self, actif, portable=True):
        b = self.mod.Bilan(False)
        self.mod.energie_plateforme(b, actif, portable)
        return b

    def textes(self, b):
        return [t for _g, t, _q in b.lignes]

    def test_confirme(self):
        self.pf("quiet", "quiet balanced balanced-performance", [("acer-wmi", "quiet", "quiet balanced balanced-performance")])
        self.services.add("tlp-pd.service")
        b = self.bilan("power-saver")
        self.assertEqual((b.ko, b.attention, b.nb_ok), (0, 0, 1))
        self.assertIn("mode matériel confirmé : quiet", self.textes(b)[0])
        self.assertIn("TLP (tlp-pd)", self.textes(b)[0])

    def test_balanced_performance_confirme_performance(self):
        self.pf("balanced-performance", "quiet balanced balanced-performance")
        self.services.add("power-profiles-daemon.service")
        b = self.bilan("performance")
        self.assertEqual(b.attention, 0)
        self.assertIn("confirmé", self.textes(b)[0])

    def test_profil_materiel_different_du_logiciel(self):
        self.pf("balanced", "quiet balanced performance")
        self.services.add("tuned-ppd.service")
        b = self.bilan("performance")
        self.assertEqual(b.attention, 1)
        self.assertIn("non confirmé", self.textes(b)[0])
        self.assertEqual(b.constats[0]["cle"], "plateforme_difference")
        self.assertNotIn("confirmé :", self.textes(b)[0].replace("non confirmé", ""))

    def test_aucun_service_rien_n_est_confirme(self):
        self.pf("balanced", "quiet balanced performance")
        b = self.bilan(None)
        self.assertEqual(b.attention, 0)
        self.assertIn("rien ne le pilote", self.textes(b)[0])
        self.assertNotIn("confirmé", self.textes(b)[0])

    def test_pilote_absent_portable(self):
        b = self.bilan("balanced")
        self.assertIn("n'en propose aucun", self.textes(b)[0])
        self.assertEqual(b.attention + b.ko, 0)

    def test_pilote_absent_pc_fixe_silencieux(self):
        b = self.bilan("balanced", portable=False)
        self.assertEqual(b.lignes, [])

    def test_permission_refusee(self):
        self.pf("balanced", "quiet balanced")
        f = self.tmp / "firmware/acpi/platform_profile"
        f.chmod(0)
        self.addCleanup(f.chmod, 0o644)
        if os.access(f, os.R_OK):
            self.skipTest("lancé en root : la permission n'est pas testable")
        b = self.bilan("balanced")
        self.assertEqual(b.attention, 1)
        self.assertIn("permission insuffisante", self.textes(b)[0])
        self.assertEqual(b.nb_ok, 0)

    def test_custom(self):
        self.pf("custom", "quiet balanced", [("acer-wmi", "quiet", "quiet balanced"), ("autre", "balanced", "quiet balanced")])
        self.services.add("tlp-pd.service")
        b = self.bilan("balanced")
        self.assertEqual(b.attention, 1)
        self.assertEqual(b.constats[0]["cle"], "plateforme_custom")
        self.assertIn("acer-wmi : quiet", self.textes(b)[0])
        self.assertIn("autre : balanced", self.textes(b)[0])

    def test_controleurs_en_desaccord_sans_custom(self):
        self.pf("balanced", "quiet balanced", [("a", "quiet", "quiet balanced"), ("b", "balanced", "quiet balanced")])
        b = self.bilan("balanced")
        self.assertEqual(b.attention, 1)

    def test_noms_du_noyau_nettoyes(self):
        self.pf("balanced", "quiet balanced", [("mauvais; $(id) nom", "balanced", "balanced")])
        self.services.add("tlp-pd.service")
        b = self.bilan("balanced")
        texte = " ".join(self.textes(b))
        self.assertNotIn("$(", texte)
        self.assertNotIn("mauvais;", texte)
        self.assertIn("mauvaisidnom", texte)

    def test_service_tlp_prioritaire(self):
        self.pf("low-power", "low-power balanced performance")
        self.services.update({"tlp-pd.service", "tuned.service"})
        b = self.bilan("power-saver")
        self.assertIn("TLP", self.textes(b)[0])

    def test_en_anglais(self):
        self.mod.T = lambda fr, en: en
        self.pf("balanced", "quiet balanced performance")
        self.services.add("tlp-pd.service")
        b = self.bilan("balanced")
        self.assertIn("hardware mode confirmed", self.textes(b)[0])


if __name__ == "__main__":
    unittest.main()

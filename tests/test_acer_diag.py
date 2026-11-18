"""nc-diag : message linuwu-sense (Nitro) et « nc-diag perf » ; faux /sys (NC_DIAG_SYS), faux sudo, faux journal, sleep remplacé."""
from importlib.machinery import SourceFileLoader
from importlib.util import module_from_spec, spec_from_loader
from pathlib import Path
import contextlib
import io
import os
import shutil
import tempfile
import unittest
from unittest import mock

REPO = Path(__file__).resolve().parents[1]
CHEMIN = os.environ.get("NC_DIAG_CIBLE") or str(REPO / "home/.local/bin/nc-diag")


def ecrire(chemin, texte):
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(texte + "\n")


class Base(unittest.TestCase):
    def setUp(self):
        p = mock.patch.dict(os.environ, NC_LANGUE="fr")
        p.start()
        self.addCleanup(p.stop)
        self.tmp = Path(tempfile.mkdtemp(prefix="nc-diag-acer-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        spec = spec_from_loader("nc_diag_acer", SourceFileLoader("nc_diag_acer", CHEMIN))
        self.mod = module_from_spec(spec)
        spec.loader.exec_module(self.mod)
        self.mod.EN = False
        self.mod.T = lambda fr, en: fr
        self.mod.SYS = str(self.tmp / "sys")
        self.mod.HOME = str(self.tmp / "home")
        self.journal = ""
        self.appels = []
        self.root = ""

        def sortie(cmd, *a, **k):
            self.appels.append(list(cmd))
            if cmd[0] == "journalctl":
                return self.journal, 0
            if cmd[0] == "powerprofilesctl":
                return "balanced", 0
            if cmd[0] == "sudo":
                return self.root_rep(cmd[3])
            return "", 127
        self.mod.sortie = sortie

    def root_rep(self, sous):
        return "", 127


class Linuwu(Base):
    def lance(self, module=True, pp=False, dmi="Autre PC", journal=""):
        s = self.tmp / "sys"
        if module:
            (s / "module/linuwu_sense").mkdir(parents=True, exist_ok=True)
        if pp:
            ecrire(s / "firmware/acpi/platform_profile", "balanced")
        ecrire(s / "class/dmi/id/product_name", dmi)
        self.journal = journal
        b = self.mod.Bilan(False)
        self.mod._note_linuwu(b)
        return [t for _g, t, _q in b.lignes]

    def test_dmi_exact(self):
        t = self.lance(dmi="Nitro ANV16-72")
        self.assertEqual(len(t), 1)
        self.assertIn("pull/148", t[0])

    def test_journal_du_noyau(self):
        t = self.lance(journal="kernel: Platform profile registration failed (-5)")
        self.assertEqual(len(t), 1)
        self.assertIn("pull/148", t[0])

    def test_absent(self):
        self.assertEqual(self.lance(module=False, dmi="Nitro ANV16-72"), [])
        self.assertEqual(self.lance(pp=True, dmi="Nitro ANV16-72"), [])
        self.assertEqual(self.lance(dmi="Autre PC", journal="rien"), [])



class RaplJeu(Base):
    """Limites de jeu restées sans origine (ancien nc-cpu-limite) : signalées hors Performance sur secteur, Nitro ou JEU_CPU."""
    def lance(self, lim=("30000000", "45000000"), dmi="Nitro ANV16-72", profil="balanced", secteur=True, conf=""):
        s = self.tmp / "sys"
        ecrire(s / "class/powercap/intel-rapl:0/constraint_0_power_limit_uw", lim[0])
        ecrire(s / "class/powercap/intel-rapl:0/constraint_1_power_limit_uw", lim[1])
        ecrire(s / "class/dmi/id/product_name", dmi)
        ecrire(s / "class/power_supply/AC/type", "Mains")
        ecrire(s / "class/power_supply/AC/online", "1" if secteur else "0")
        if conf:
            ecrire(self.tmp / "home/.config/nc-profile.conf", conf)
        base = self.mod.sortie
        self.mod.sortie = lambda cmd, *a, **k: (profil, 0) if cmd[0] == "powerprofilesctl" else base(cmd, *a, **k)
        b = self.mod.Bilan(False)
        self.mod._note_rapl_jeu(b)
        return [t for _g, t, _q in b.lignes]

    def test_equilibre_signale(self):
        t = self.lance()
        self.assertEqual(len(t), 1)
        self.assertIn("30/45 W", t[0])
        self.assertIn("redémarrage", t[0])

    def test_performance_sur_batterie_signale(self):
        self.assertEqual(len(self.lance(profil="performance", secteur=False, lim=("45000000", "65000000"))), 1)

    def test_rien(self):
        self.assertEqual(self.lance(profil="performance"), [])                       # le jeu, normal
        self.assertEqual(self.lance(lim=("70000000", "115000000")), [])             # l'origine
        self.assertEqual(self.lance(dmi="Autre PC", lim=("45000000", "65000000")), [])   # firmware à 45/65 ailleurs
        self.assertEqual(len(self.lance(dmi="Autre PC", conf="JEU_CPU=45/65")), 1)   # sauf avec JEU_CPU réglé


class JeuGpu(Base):
    def test_defaut_du_dmi_comme_nc_gpu_jeu(self):
        """nc-diag perf lit JEU_GPU_MHZ par nc_jeu_gpu_mhz : 1500 par défaut sur le Nitro, réglage écrit sinon."""
        (self.tmp / "home").mkdir()
        with mock.patch.dict(os.environ, HOME=str(self.tmp / "home")):
            ecrire(self.tmp / "sys/class/dmi/id/product_name", "Nitro ANV16-72")
            self.assertEqual(self.mod._jeu_gpu_mhz(), "1500")
            ecrire(self.tmp / "home/.config/nc/reglages.conf", "JEU_GPU_MHZ=off")
            self.assertEqual(self.mod._jeu_gpu_mhz(), "off")
            ecrire(self.tmp / "sys/class/dmi/id/product_name", "Autre PC")
            (self.tmp / "home/.config/nc/reglages.conf").unlink()
            self.assertEqual(self.mod._jeu_gpu_mhz(), "off")

class Perf(Base):
    def prepare(self, avant=1000, apres=1000, statut="Full", unite="charge", bat=True):
        d = self.tmp / "sys/class/power_supply/BAT1"
        if bat:
            ecrire(d / "type", "Battery")
            ecrire(d / "status", statut)
            ecrire(d / f"{unite}_full", "5000000")
            ecrire(d / f"{unite}_now", str(avant * 1000))
        self.maj = lambda _n: ecrire(d / f"{unite}_now", str(apres * 1000))
        self.mod.PAUSE = self.maj
        self.root = ""

    def perf(self, *args):
        sortie = io.StringIO()
        with contextlib.redirect_stdout(sortie):
            code = self.mod.perf(list(args))
        return code, sortie.getvalue()

    def test_sens(self):
        for apres, mot in ((1100, "se charge"), (900, "se vide"), (1000, "tient")):
            self.prepare(apres=apres)
            code, txt = self.perf("10")
            self.assertEqual(code, 0)
            self.assertIn(mot, txt)

    def test_status_ment(self):
        self.prepare(apres=900, statut="Full")
        self.assertIn("se vide", self.perf()[1])

    def test_mesure(self):
        self.prepare(apres=900)
        txt = self.perf()[1]
        self.assertIn("-100.0 mAh", txt)
        self.assertIn("-2.00 %", txt)

    def test_energie(self):
        self.prepare(apres=900, unite="energy")
        self.assertIn("mWh", self.perf()[1])

    def test_bornes(self):
        self.prepare()
        for v in ("4", "121", "abc", "-5"):
            code, txt = self.perf(v)
            self.assertEqual(code, 2, v)
            self.assertIn("entre 5 et 120", txt)

    def test_sans_batterie(self):
        self.prepare(bat=False)
        code, txt = self.perf()
        self.assertEqual(code, 0)
        self.assertIn("Pas de batterie", txt)

    def test_puissance(self):
        self.prepare()
        faux = self.tmp / "nc-energie-root"
        faux.write_text("#!/bin/sh\n")
        mj = iter(["1000", "31000"])
        self.root_rep = lambda sous: ("paquet_mj=" + next(mj), 0) if sous == "puissance" else ("rapl=30/45\nventilateurs=auto", 0)
        with mock.patch.dict(os.environ, NC_ENERGIE_ROOT=str(faux)):
            txt = self.perf("10")[1]
        self.assertLessEqual(sum(1 for c in self.appels if c[-1] == "puissance"), 2)
        self.assertIn("3.0 W", txt)
        self.assertIn("30/45", txt)

    def test_code_5(self):
        self.prepare()
        faux = self.tmp / "nc-energie-root"
        faux.write_text("#!/bin/sh\n")
        self.root_rep = lambda sous: ("", 5) if sous == "puissance" else ("", 0)
        with mock.patch.dict(os.environ, NC_ENERGIE_ROOT=str(faux)):
            txt = self.perf()[1]
        self.assertIn("inconnue", txt)


if __name__ == "__main__":
    unittest.main()

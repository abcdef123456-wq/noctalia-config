"""Lot G3 B : installation de Garmin (install.sh), résumé du matin, action JARVIS /nc garmin.

install.sh tourne sur le banc de test_install_nixos (HOME jetable, faux outils) ; le faux nc-garmin note ses appels.
Aucune donnée de santé réelle, jamais le vrai nc-garmin. Les environnements sont des dicts, jamais os.environ en dehors de mock.patch.dict."""
import asyncio
import os
import re
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

from tests.test_install_nixos import Banc, outil, REPO

QML = REPO / "home/.config/quickshell/nc-ile"
SOURCE = REPO / "home/.local/share/nc-jarvis/server/nc_noctalia.py"


class InstallGarmin(unittest.TestCase):
    def banc(self, code=0):
        b = Banc()
        self.addCleanup(b.fin)
        self.appels = b.d / "appels-garmin"
        outil(b.bin, "nc-garmin-faux", f'echo "$*" >> "{self.appels}"; exit {code}')
        self.faux = str(b.bin / "nc-garmin-faux")
        return b

    def lance(self, b, *args):
        # NC_GARMIN_BIN n'agit qu'avec NC_INSTALLER_TEST=1 ; on passe par l'environnement du banc
        env_avant = b.env
        b.env = lambda: {**env_avant(), "NC_GARMIN_BIN": self.faux}
        return b.lance(*args)

    def reglages(self, b):
        p = b.home / ".config/nc/reglages.conf"
        return p.read_text() if p.exists() else ""

    def lances(self):
        return self.appels.read_text() if self.appels.exists() else ""

    def test_sans_option_rien_n_est_active(self):
        b = self.banc()
        r = self.lance(b, "--oui")      # sans terminal, la question vaut son défaut : non
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertNotIn("GARMIN_ACTIF", self.reglages(b))
        self.assertEqual(self.lances(), "")

    def test_option_garmin_active_et_installe(self):
        b = self.banc()
        r = self.lance(b, "--oui", "--garmin")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("GARMIN_ACTIF=oui", self.reglages(b).splitlines())
        self.assertEqual(self.lances().split(), ["installer"])

    def test_echec_du_connecteur_n_arrete_pas(self):
        b = self.banc(code=1)
        r = self.lance(b, "--oui", "--garmin")
        sortie = r.stdout + r.stderr
        self.assertEqual(r.returncode, 0, sortie)
        self.assertIn("Garmin", sortie)
        self.assertIn("pas pu s'installer", sortie)
        self.assertIn("GARMIN_ACTIF=oui", self.reglages(b).splitlines())

    def test_une_seule_ligne_garmin_actif(self):
        b = self.banc()
        (b.home / ".config/nc").mkdir(parents=True)
        (b.home / ".config/nc/reglages.conf").write_text("GARMIN_ACTIF=non\nAUTRE=1\n")
        r = self.lance(b, "--oui", "--garmin")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        t = self.reglages(b)
        self.assertEqual(t.count("GARMIN_ACTIF="), 1, t)
        self.assertIn("AUTRE=1", t)

    def test_question_par_defaut_non(self):
        src = (REPO / "install.sh").read_text()
        m = re.search(r'ask "\$\(t "Tableau de bord Santé Garmin[^\n]*', src)
        self.assertIsNotNone(m)
        self.assertRegex(m.group(0), r'\)" n && GARMIN=1')   # non par défaut, non sensible (contrat)


class ResumeSource(unittest.TestCase):
    def test_resume_lit_seulement_resumeVisible(self):
        for f in ("Resume.qml", "PageResume.qml"):
            t = (QML / f).read_text()
            code = "\n".join(l.split("//")[0] for l in t.splitlines())
            self.assertNotRegex(code, r"GarminEtat\.(brut|metriques)\b", f)
        t = (QML / "Resume.qml").read_text()
        self.assertIn("GarminEtat.resumeVisible", t)
        self.assertIn("GARMIN_RESUME_MATIN", t)
        self.assertIn("GARMIN_ACTIF", t)

    def test_pas_de_component_inline_ajoute(self):
        for f in ("Resume.qml", "PageResume.qml"):
            self.assertNotIn("component ", "\n".join(l.split("//")[0] for l in (QML / f).read_text().splitlines()).replace("Component.", ""), f)


def module():
    m = types.ModuleType("nc_noctalia_garmin_test")
    m.__file__ = str(SOURCE)
    exec(compile(SOURCE.read_text(), str(SOURCE), "exec"), m.__dict__)
    return m


class Jarvis(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp(prefix="nc-garmin-j-")
        self.home = Path(self.d)
        (self.home / ".config/nc").mkdir(parents=True)
        env = mock.patch.dict(os.environ, HOME=self.d, DEPLOY_MODE="local")
        env.start()
        self.addCleanup(env.stop)
        self.m = module()
        self.appels = []

        async def executer(argv, *a, **k):
            self.appels.append(list(argv))
            return 0, "Sommeil 7 h 30"
        self.m.executer = executer

    def regle(self, texte):
        (self.home / ".config/nc/reglages.conf").write_text(texte)

    def agir(self):
        return asyncio.run(self.m.agir("garmin", []))

    def test_refus_sans_reglage(self):
        for texte in ("", "GARMIN_JARVIS=non\n", "GARMIN_ACTIF=oui\n"):
            with self.subTest(texte):
                self.regle(texte)
                r = self.agir()
                self.assertFalse(r["success"])
                self.assertIn("GARMIN_JARVIS", r["output"])
        self.assertEqual(self.appels, [])

    def test_oui_lance_le_resume(self):
        self.regle("GARMIN_JARVIS=oui\n")
        r = self.agir()
        self.assertTrue(r["success"], r)
        self.assertEqual(self.appels, [["nc-garmin", "resume"]])
        self.assertIn("Sommeil", r["output"])

    def test_reglage_relu_a_chaque_appel(self):
        self.regle("GARMIN_JARVIS=oui\n")
        self.assertTrue(self.agir()["success"])
        self.regle("GARMIN_JARVIS=non\n")
        self.assertFalse(self.agir()["success"])
        self.assertEqual(len(self.appels), 1)


if __name__ == "__main__":
    unittest.main()

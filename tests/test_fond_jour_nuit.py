"""Fond du jour / fond de la nuit (nc-fond-jour-nuit, réglage FONDS_JOUR_NUIT, FondJourNuit.qml).

- Le script est chargé dans un HOME, des XDG_* et un TMPDIR jetables ; « noctalia », « systemd-run » et « systemctl » sont de faux
  outils qui notent leurs arguments (jamais les vrais). L'heure est donnée au script : aucun minuteur réel, aucune attente.
- Vérifié : période et prochaine échéance, fond choisi dans le bon sous-dossier, rien écran éteint ou verrouillé, un seul
  minuteur (l'ancien est retiré), pas de nouveau changement dans la même période, rattrapage, arrêt ; le réglage passe devant la
  rotation de Noctalia ; la source QML n'a ni minuteur ni sondage."""
import datetime
import io
import os
from pathlib import Path
import re
import runpy
import tempfile
import unittest
from unittest.mock import patch
import warnings

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "home/.local/bin/nc-fond-jour-nuit"
QML = REPO / "home/.config/quickshell/nc-ile/FondJourNuit.qml"
D = datetime.datetime


class Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="nc-fjn-")
        self.addCleanup(self._tmp.cleanup)
        self.r = Path(self._tmp.name)
        for s in ("home", "run", "bin", "tmp"):
            (self.r / s).mkdir()
        self.home = self.r / "home"
        self.journal = self.r / "journal"
        for nom in ("noctalia", "systemd-run", "systemctl"):
            f = self.r / "bin" / nom
            f.write_text('#!/bin/sh\necho "%s $*" >> "%s"\n' % (nom, self.journal))
            f.chmod(0o755)
        for sous, noms in (("jour", ("a.jpg", "b.png")), ("nuit", ("n.webp",))):
            (self.home / "Pictures/Wallpapers" / sous).mkdir(parents=True)
            for n in noms:
                (self.home / "Pictures/Wallpapers" / sous / n).write_bytes(b"x")
        self.reglages(FONDS_JOUR_NUIT="oui")
        self.env = {"HOME": str(self.home), "XDG_CONFIG_HOME": str(self.home / ".config"), "XDG_DATA_HOME": str(self.home / ".local/share"),
                    "XDG_STATE_HOME": str(self.home / ".local/state"), "XDG_CACHE_HOME": str(self.home / ".cache"),
                    "XDG_RUNTIME_DIR": str(self.r / "run"), "TMPDIR": str(self.r / "tmp"), "PATH": str(self.r / "bin") + ":/usr/bin:/bin"}

    def reglages(self, **v):
        d = self.home / ".config/nc"
        d.mkdir(parents=True, exist_ok=True)
        (d / "reglages.conf").write_text("".join('%s="%s"\n' % kv for kv in v.items()))

    def lancer(self, quand, *args):
        with patch.dict(os.environ, self.env), warnings.catch_warnings(), patch("sys.argv", [str(SCRIPT)]):
            warnings.simplefilter("ignore", ResourceWarning)
            mod = runpy.run_path(str(SCRIPT))
            return mod["main"](list(args), quand)

    def appels(self):
        return self.journal.read_text().splitlines() if self.journal.exists() else []


class Periode(Base):
    def test_periodes_et_echeances(self):
        p = runpy.run_path(str(SCRIPT))["periode"]
        self.assertEqual(p(D(2026, 10, 28, 3, 0)), ("nuit", D(2026, 10, 28, 7, 0)))
        self.assertEqual(p(D(2026, 10, 28, 6, 59)), ("nuit", D(2026, 10, 28, 7, 0)))
        self.assertEqual(p(D(2026, 10, 28, 7, 0)), ("jour", D(2026, 10, 28, 19, 0)))
        self.assertEqual(p(D(2026, 10, 28, 18, 59)), ("jour", D(2026, 10, 28, 19, 0)))
        self.assertEqual(p(D(2026, 10, 28, 19, 0)), ("nuit", D(2026, 10, 29, 7, 0)))
        self.assertEqual(p(D(2026, 12, 31, 22, 0)), ("nuit", D(2027, 1, 1, 7, 0)))


class Bascule(Base):
    def test_jour_applique_le_fond_du_jour_et_pose_un_minuteur(self):
        self.lancer(D(2026, 10, 28, 10, 0))
        a = self.appels()
        self.assertEqual(len([x for x in a if x.startswith("noctalia ")]), 1, a)
        self.assertRegex(a[0], r"^noctalia msg wallpaper-set .*/Wallpapers/jour/[ab]\.(jpg|png)$")
        m = [x for x in a if x.startswith("systemd-run")]
        self.assertEqual(len(m), 1, a)
        self.assertIn("--on-calendar=2026-10-28 19:00:00", m[0])
        self.assertIn("--user", m[0])

    def test_nuit_applique_le_fond_de_la_nuit_jusqu_au_lendemain(self):
        self.lancer(D(2026, 10, 28, 21, 30))
        a = self.appels()
        self.assertRegex(a[0], r"wallpaper-set .*/Wallpapers/nuit/n\.webp$")
        self.assertIn("--on-calendar=2026-10-29 07:00:00", [x for x in a if x.startswith("systemd-run")][0])

    def test_petit_matin_meme_nuit_une_seule_application(self):
        self.lancer(D(2026, 10, 28, 22, 0))
        self.lancer(D(2026, 10, 29, 3, 0))              # même nuit : pas de nouveau changement
        a = self.appels()
        self.assertEqual(len([x for x in a if x.startswith("noctalia ")]), 1, a)
        # mais l'échéance est reposée, et l'ancienne minuterie retirée si elle diffère
        self.assertEqual(len([x for x in a if x.startswith("systemd-run")]), 2, a)

    def test_bascule_suivante_change_le_fond_et_retire_l_ancien_minuteur(self):
        self.lancer(D(2026, 10, 28, 10, 0))
        self.lancer(D(2026, 10, 28, 19, 0))              # le minuteur a sonné
        a = self.appels()
        self.assertEqual(len([x for x in a if x.startswith("noctalia ")]), 2, a)
        self.assertIn("systemctl --user stop nc-fond-jn-202610281900.timer", a)
        self.assertRegex(a[-1], r"--on-calendar=2026-10-29 07:00:00")

    def test_un_fond_par_jour_a_tour_de_role(self):
        self.lancer(D(2026, 10, 28, 10, 0))
        self.lancer(D(2026, 10, 29, 10, 0))
        f = [x.split()[-1] for x in self.appels() if x.startswith("noctalia ")]
        self.assertEqual(len(f), 2)
        self.assertNotEqual(f[0], f[1])

    def test_rattrapage_apres_une_veille(self):
        self.lancer(D(2026, 10, 28, 10, 0))
        self.lancer(D(2026, 10, 28, 20, 15))             # réveil bien après 19 h
        a = [x for x in self.appels() if x.startswith("noctalia ")]
        self.assertEqual(len(a), 2)
        self.assertIn("/nuit/", a[1])

    def test_ecran_eteint_ou_verrouille_rien(self):
        (self.r / "run/nc-ecran-eteint").write_text("")
        self.lancer(D(2026, 10, 28, 10, 0))
        self.assertEqual(self.appels(), [])
        (self.r / "run/nc-ecran-eteint").unlink()
        (self.r / "run/nc-verrouille").write_text("")
        self.lancer(D(2026, 10, 28, 10, 0))
        self.assertEqual(self.appels(), [])
        (self.r / "run/nc-verrouille").unlink()
        self.lancer(D(2026, 10, 28, 10, 0))              # au réveil : rattrapé
        self.assertTrue(any(x.startswith("noctalia ") for x in self.appels()))

    def test_reglage_coupe_rien(self):
        self.reglages(FONDS_JOUR_NUIT="non")
        self.lancer(D(2026, 10, 28, 10, 0))
        self.assertEqual(self.appels(), [])

    def test_sous_dossier_absent_ou_vide_le_fond_ne_change_pas(self):
        for f in (self.home / "Pictures/Wallpapers/jour").iterdir():
            f.unlink()
        self.lancer(D(2026, 10, 28, 10, 0))
        self.assertFalse(any(x.startswith("noctalia ") for x in self.appels()))
        self.assertTrue(any(x.startswith("systemd-run") for x in self.appels()))       # l'échéance reste posée

    def test_force_reapplique(self):
        self.lancer(D(2026, 10, 28, 10, 0))
        self.lancer(D(2026, 10, 28, 11, 0), "force")
        self.assertEqual(len([x for x in self.appels() if x.startswith("noctalia ")]), 2)

    def test_arreter_retire_le_minuteur(self):
        self.lancer(D(2026, 10, 28, 10, 0))
        self.lancer(D(2026, 10, 28, 10, 5), "arreter")
        self.assertIn("systemctl --user stop nc-fond-jn-202610281900.timer", self.appels())
        n = len(self.appels())
        self.lancer(D(2026, 10, 28, 10, 6), "arreter")
        self.assertEqual(len(self.appels()), n)

    def test_dossier_choisi(self):
        autre = self.r / "autres"
        (autre / "jour").mkdir(parents=True)
        (autre / "jour/z.jpg").write_bytes(b"x")
        self.reglages(FONDS_JOUR_NUIT="oui", FONDS_DOSSIER=str(autre))
        self.lancer(D(2026, 10, 28, 10, 0))
        self.assertTrue(self.appels()[0].endswith("autres/jour/z.jpg"))


class Rotation(Base):
    def test_le_fond_jour_nuit_coupe_la_rotation_de_noctalia(self):
        with patch.dict(os.environ, self.env), warnings.catch_warnings():
            warnings.simplefilter("ignore", ResourceWarning)
            nc = runpy.run_path(str(REPO / "home/.local/bin/nc-reglages"))
            appliquer = nc["appliquer_noctalia"]
            appliquer.__globals__["subprocess"] = type("S", (), {"run": staticmethod(lambda *a, **k: None)})
            for jn, attendu in (("oui", "enabled = false"), ("non", "enabled = true")):
                appliquer({"FONDS_ROTATION": "oui", "FONDS_INTERVALLE": "10", "FONDS_DOSSIER": "~/x", "FONDS_JOUR_NUIT": jn})
                toml = (self.home / ".config/noctalia/zy-reglages.toml").read_text()
                bloc = toml.split("[wallpaper.automation]")[1].split("[")[0]
                self.assertIn(attendu, bloc, toml)
            reg = nc["PAR_CLE"]["FONDS_JOUR_NUIT"]
        self.assertEqual(reg.defaut, "non")
        self.assertEqual(nc["MATERIEL"]["FONDS_JOUR_NUIT"], "ile")
        self.assertIn("passe devant", reg.aide_fr if hasattr(reg, "aide_fr") else str(reg.aide))


class Source(unittest.TestCase):
    def test_qml_sans_minuteur_ni_sondage(self):
        code = re.sub(r"//.*", "", QML.read_text())
        self.assertNotRegex(code, r"\bTimer\b|repeat: true|running: true")
        self.assertEqual(len(re.findall(r"(?m)^\s*component ", code)), 0)
        self.assertEqual(len(re.findall(r"Component\.onCompleted", code)), 1)
        self.assertIn("FondJourNuit {}", (QML.parent / "shell.qml").read_text())

    def test_script_sans_boucle_ni_veille(self):
        code = SCRIPT.read_text()
        self.assertNotRegex(code, r"time\.sleep|while True|\bsleep\b")
        self.assertIn("wallpaper-set", code)


if __name__ == "__main__":
    unittest.main()

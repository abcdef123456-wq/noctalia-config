"""Veille sur batterie (nc-reglages, VEILLE_BAISSE_BATTERIE et VEILLE_ECRAN_BATTERIE) : texte de la config de hypridle
produit avec et sans ces réglages, et les commandes des deux listeners jouées pour de vrai sur un faux
/sys/class/power_supply (secteur, batterie, PC de bureau), un faux nc-brightness et un faux hyprctl. HOME temporaire."""
import importlib.machinery
import importlib.util
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import warnings

REPO = Path(__file__).resolve().parents[1]
SRC = (REPO / "home/.config/hypr/hypridle.conf").read_text(encoding="utf-8")


def charger(home):
    with patch.dict(os.environ, HOME=str(home)), warnings.catch_warnings():
        warnings.simplefilter("ignore", ResourceWarning)
        chargeur = importlib.machinery.SourceFileLoader("nc_reglages_veille", str(REPO / "home/.local/bin/nc-reglages"))
        spec = importlib.util.spec_from_loader(chargeur.name, chargeur)
        mod = importlib.util.module_from_spec(spec)
        chargeur.exec_module(mod)
    return mod


def listeners(texte):
    """[{timeout, on-timeout, on-resume}] dans l'ordre du fichier."""
    res = []
    for b in re.findall(r"(?ms)^listener\s*\{(.*?)^\}", texte):
        d = {}
        for ligne in b.splitlines():
            m = re.match(r"\s*([a-z-]+)\s*=\s*(.*)$", ligne)
            if m:
                d[m.group(1)] = m.group(2)
        d["timeout"] = int(d["timeout"])
        res.append(d)
    return res


def batterie(l, quoi):
    return [x for x in l if "power_supply" in x["on-timeout"] and quoi in x["on-timeout"]]


class TexteVeille(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="nc-veille-")
        cls.nc = charger(Path(cls.tmp.name))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def texte(self, **vals):
        return self.nc.texte_veille({k: str(v) for k, v in vals.items()}, SRC)

    def test_reglages_declares(self):
        for cle in ("VEILLE_BAISSE_BATTERIE", "VEILLE_ECRAN_BATTERIE"):
            r = self.nc.PAR_CLE[cle]
            self.assertEqual((r.defaut, r.genre, r.groupe, r.unite, r.mini), ("60", "entier", "veille", "s", 0))
            self.assertEqual(r.valider("0"), "0")
            self.assertEqual(self.nc.MATERIEL[cle], "batterie")
            self.assertTrue(r.zero)

    def test_config_de_base_contient_les_listeners_batterie(self):
        # Sans aucun réglage, hypridle lit ce fichier tel quel : les deux listeners y sont, à 60 s
        l = listeners(SRC)
        self.assertEqual([x["timeout"] for x in batterie(l, "nc-brightness dim")], [60])
        self.assertEqual([x["timeout"] for x in batterie(l, "dpms")], [60])
        self.assertIn("on_lock_cmd", SRC)
        self.assertIn("on_unlock_cmd", SRC)

    def test_par_defaut(self):
        l = listeners(self.texte(VEILLE_VERROU=5))
        self.assertEqual([x["timeout"] for x in l], [150, 60, 300, 330, 60, 900])
        dim, ecran = batterie(l, "nc-brightness dim")[0], batterie(l, "dpms")[0]
        self.assertIn("restore", dim["on-resume"])
        self.assertIn("[[on]]", ecran["on-resume"])
        self.assertIn("nc-verrouille", ecran["on-timeout"])

    def test_reglages_choisis(self):
        l = listeners(self.texte(VEILLE_BAISSE_BATTERIE=90, VEILLE_ECRAN_BATTERIE=20))
        self.assertEqual(batterie(l, "nc-brightness dim")[0]["timeout"], 90)
        self.assertEqual(batterie(l, "dpms")[0]["timeout"], 20)
        # Sur secteur : rien ne bouge
        self.assertEqual([x["timeout"] for x in l if "power_supply" not in x["on-timeout"]], [150, 300, 330])

    def test_zero_comme_sur_secteur(self):
        t = self.texte(VEILLE_BAISSE_BATTERIE=0, VEILLE_ECRAN_BATTERIE=0)
        l = listeners(t)
        self.assertEqual(batterie(l, "nc-brightness dim"), [])
        self.assertEqual(batterie(l, "dpms"), [])
        self.assertEqual([x["timeout"] for x in l], [150, 300, 330, 900])
        self.assertIn("comme sur secteur", t.splitlines()[0])

    def test_inutiles_retires(self):
        # Assombrissement normal à 30 s (verrouillage après 2 min) : celui de la batterie (60 s) n'apporte rien
        l = listeners(self.texte(VEILLE_VERROU=2))
        self.assertEqual(batterie(l, "nc-brightness dim"), [])
        # Jamais de verrouillage : pas d'assombrissement du tout, mais l'écran verrouillé à la main s'éteint quand même
        l = listeners(self.texte(VEILLE_VERROU=0))
        self.assertEqual([x for x in l if "nc-brightness dim" in x["on-timeout"]], [])
        self.assertEqual(batterie(l, "dpms")[0]["timeout"], 60)
        # Écran éteint déjà après 1 min sans activité : le listener de la batterie est retiré
        l = listeners(self.texte(VEILLE_ECRAN=1))
        self.assertEqual(batterie(l, "dpms"), [])

    def test_veille_sur_secteur_garde_son_listener(self):
        l = listeners(self.texte(VEILLE_SECTEUR=30))
        self.assertEqual(l[-1]["timeout"], 1800)
        self.assertEqual(len(batterie(l, "nc-brightness dim")), 1)


class AppliquerVeille(unittest.TestCase):
    def test_fichier_genere_ou_retire(self):
        with tempfile.TemporaryDirectory(prefix="nc-veille-") as d:
            home = Path(d)
            nc = charger(home)
            (home / ".config/hypr").mkdir(parents=True)
            (home / ".config/hypr/hypridle.conf").write_text(SRC, encoding="utf-8")
            marque = Path(os.environ["XDG_RUNTIME_DIR"]) / "nc-verrouille"
            marque.write_text("")
            with patch("subprocess.run") as run:
                run.return_value = subprocess.CompletedProcess([], 0, "", "")
                nc.appliquer_veille({"VEILLE_ECRAN_BATTERIE": "0"})
                sortie = Path(nc.VEILLE_OUT).read_text(encoding="utf-8")
                self.assertEqual(batterie(listeners(sortie), "dpms"), [])
                self.assertEqual(len(batterie(listeners(sortie), "nc-brightness dim")), 1)
                self.assertTrue(Path(nc.VEILLE_UNITE).exists())
                # hypridle relancé : la marque « écran verrouillé » ne peut pas rester
                self.assertFalse(marque.exists())
                self.assertIn(["systemctl", "--user", "restart", "hypridle.service"], [c.args[0] for c in run.call_args_list])
                # Tout remis comme dans la config : hypridle relit ~/.config/hypr/hypridle.conf
                nc.appliquer_veille({})
                self.assertFalse(Path(nc.VEILLE_OUT).exists())
                self.assertFalse(Path(nc.VEILLE_UNITE).exists())


@unittest.skipUnless(shutil.which("sh"), "sh requis")
class CommandesListeners(unittest.TestCase):
    """Les on-timeout / on-resume, joués par sh comme le fait hypridle (/bin/sh -c)."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="nc-veille-cmd-")
        self.r = Path(self._tmp.name)
        self.ps = self.r / "power_supply"
        self.run = self.r / "run"
        self.run.mkdir(mode=0o700)
        bin_ = self.r / ".local/bin"
        bin_.mkdir(parents=True)
        faux = self.r / "faux"
        faux.mkdir()
        for nom, dossier in (("nc-brightness", bin_), ("hyprctl", faux)):
            (dossier / nom).write_text(f'#!/bin/sh\nprintf "%s\\n" "{nom} $*" >> "$HOME/appels"\n')
            (dossier / nom).chmod(0o755)
        self.env = dict(os.environ, HOME=str(self.r), XDG_RUNTIME_DIR=str(self.run), PATH=f"{faux}:/usr/bin:/bin")
        self.l = listeners(SRC)

    def tearDown(self):
        self._tmp.cleanup()

    def materiel(self, batterie_=True, secteur=False):
        shutil.rmtree(self.ps, ignore_errors=True)
        self.ps.mkdir()
        if batterie_:
            (self.ps / "BAT0").mkdir()
            (self.ps / "BAT0/type").write_text("Battery\n")
            (self.ps / "BAT0/online").write_text("1\n")
        (self.ps / "AC").mkdir()
        (self.ps / "AC/type").write_text("Mains\n")
        (self.ps / "AC/online").write_text("1\n" if secteur else "0\n")

    def jouer(self, cmd):
        cmd = cmd.replace("/sys/class/power_supply", str(self.ps))
        subprocess.run(["sh", "-c", cmd], env=self.env, check=True, timeout=10)
        f = self.r / "appels"
        a = f.read_text().splitlines() if f.exists() else []
        f.unlink(missing_ok=True)
        return a

    def test_assombrir(self):
        normal = [x for x in self.l if "nc-brightness dim" in x["on-timeout"] and "power_supply" not in x["on-timeout"]][0]
        dim = batterie(self.l, "nc-brightness dim")[0]
        # Sur secteur et sur un PC de bureau : rien, ni à l'inactivité ni au retour ; l'assombrissement normal agit
        for b, s in ((True, True), (False, False)):
            self.materiel(batterie_=b, secteur=s)
            self.assertEqual(self.jouer(dim["on-timeout"]), [])
            self.assertEqual(self.jouer(normal["on-timeout"]), ["nc-brightness dim"])
            self.assertEqual(self.jouer(dim["on-resume"]), [])
        # Sur batterie : assombri tout de suite, l'assombrissement normal ne mémorise pas le niveau déjà baissé,
        # et le retour restaure
        self.materiel(secteur=False)
        self.assertEqual(self.jouer(dim["on-timeout"]), ["nc-brightness dim"])
        self.assertEqual(self.jouer(normal["on-timeout"]), [])
        self.assertEqual(self.jouer(dim["on-resume"]), ["nc-brightness restore"])
        # Branché ensuite : la marque est partie, l'assombrissement normal revient
        self.materiel(secteur=True)
        self.assertEqual(self.jouer(dim["on-timeout"]), [])
        self.assertEqual(self.jouer(normal["on-timeout"]), ["nc-brightness dim"])

    def test_ecran_verrouille(self):
        general = re.search(r"(?ms)^general\s*\{.*?^\}", SRC).group(0)
        verrou = re.search(r"on_lock_cmd\s*=\s*(.*)", general).group(1)
        deverrou = re.search(r"on_unlock_cmd\s*=\s*(.*)", general).group(1)
        ecran = batterie(self.l, "dpms")[0]
        eteint = ['hyprctl dispatch hl.dsp.dpms({ action = [[off]] })']
        allume = ['hyprctl dispatch hl.dsp.dpms({ action = [[on]] })']
        # Batterie, pas verrouillé : rien
        self.materiel(secteur=False)
        self.assertEqual(self.jouer(ecran["on-timeout"]), [])
        self.assertEqual(self.jouer(ecran["on-resume"]), [])
        # Batterie, verrouillé : éteint, puis rallumé au retour
        self.jouer(verrou)
        self.assertEqual(self.jouer(ecran["on-timeout"]), eteint)
        self.assertEqual(self.jouer(ecran["on-resume"]), allume)
        # Secteur, verrouillé : rien
        self.materiel(secteur=True)
        self.assertEqual(self.jouer(ecran["on-timeout"]), [])
        self.assertEqual(self.jouer(ecran["on-resume"]), [])
        # Déverrouillé : plus rien, même sur batterie
        self.materiel(secteur=False)
        self.jouer(deverrou)
        self.assertEqual(self.jouer(ecran["on-timeout"]), [])


if __name__ == "__main__":
    unittest.main()

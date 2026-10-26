"""nc-reglages set : écriture sûre de reglages.conf. 20 « set » en parallèle ne perdent rien (verrou + fichier
temporaire + os.replace), un saut de ligne ou un caractère nul est refusé, un octet non UTF-8 est toléré, le dossier
n'est remplacé que s'il est au début du chemin, le mode du fichier est gardé, et une valeur invalide écrite à la main
rend la valeur par défaut. Faux HOME ; jamais le vrai."""
import importlib.machinery
import importlib.util
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import warnings

REPO = Path(__file__).resolve().parents[1]
NC_REGLAGES = REPO / "home/.local/bin/nc-reglages"


def charger(home):
    with patch.dict(os.environ, HOME=str(home), NC_LANGUE="fr"), warnings.catch_warnings():
        warnings.simplefilter("ignore", ResourceWarning)
        chargeur = importlib.machinery.SourceFileLoader("nc_reglages_ecriture", str(NC_REGLAGES))
        spec = importlib.util.spec_from_loader(chargeur.name, chargeur)
        mod = importlib.util.module_from_spec(spec)
        chargeur.exec_module(mod)
    return mod


class Ecriture(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="nc-reglages-ecriture-")
        self.addCleanup(self._tmp.cleanup)
        self.home = Path(self._tmp.name) / "home"
        (self.home / ".config/nc").mkdir(parents=True)
        (self.home / ".config/hypr").mkdir(parents=True)
        shutil.copy(REPO / "home/.config/hypr/hypridle.conf", self.home / ".config/hypr/hypridle.conf")
        self.conf = self.home / ".config/nc/reglages.conf"
        self.env = {k: v for k, v in os.environ.items() if not k.startswith(("NOCTALIA_", "XDG_CONFIG", "XDG_STATE"))}
        self.env.pop("HYPRLAND_INSTANCE_SIGNATURE", None)
        self.env.update(HOME=str(self.home), NC_LANGUE="fr", XDG_CACHE_HOME=str(self.home / ".cache"))
        self.mod = charger(self.home)

    def nc(self, *args):
        return subprocess.run([sys.executable, str(NC_REGLAGES), *args], env=self.env, capture_output=True,
                              text=True, timeout=60, cwd=str(self.home))

    def cles_simples(self, n):
        """n réglages oui/non, « oui » par défaut, sans groupe d'application (set ne lance rien d'autre)."""
        cles = [r.cle for r in self.mod.REGLAGES if r.genre == "ouinon" and r.defaut == "oui" and not r.groupe]
        self.assertGreaterEqual(len(cles), n)
        return cles[:n]

    def test_vingt_set_en_parallele_rien_de_perdu(self):
        cles = self.cles_simples(20)
        for essai in range(3):
            if self.conf.exists():
                self.conf.unlink()
            procs = [subprocess.Popen([sys.executable, str(NC_REGLAGES), "set", c, "non"], env=self.env,
                                      stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True, cwd=str(self.home))
                     for c in cles]
            for p in procs:
                _, err = p.communicate(timeout=120)
                self.assertEqual(p.returncode, 0, err)
            ecrites = self.mod.lire()
            self.assertEqual(sorted(ecrites), sorted(cles), f"essai {essai}")
            self.assertTrue(all(v == "non" for v in ecrites.values()))
        restes = [p.name for p in self.conf.parent.iterdir() if p.name.endswith(".tmp")]
        self.assertEqual(restes, [])

    def test_saut_de_ligne_refuse(self):
        for mauvais in ("bonjour\nGPU_REGLE=toujours", "a\rb", "a\0b"):
            if "\0" in mauvais:
                continue                              # un argument de programme ne peut pas porter de \0 (testé en direct plus bas)
            r = self.nc("set", "VERROU_MESSAGE", mauvais)
            self.assertNotEqual(r.returncode, 0)
            self.assertFalse(self.conf.exists() and "GPU_REGLE" in self.conf.read_text())
        with self.assertRaises(ValueError):
            self.mod.PAR_CLE["VERROU_MESSAGE"].valider("a\0b")
        with self.assertRaises(ValueError):
            self.mod.PAR_CLE["FONDS_DOSSIER"].valider("/tmp/a\nb")
        with self.assertRaises(ValueError):                         # garde-fou d'ecrire, sans passer par valider
            self.mod.ecrire({"VERROU_MESSAGE": "x\nGPU_REGLE=toujours"})
        with self.assertRaises(ValueError):
            self.mod.ecrire({"VERROU_MESSAGE": "x\0y"})
        self.assertFalse(self.conf.exists())

    def test_octet_invalide_tolere(self):
        self.conf.write_bytes(b"# caf\xe9\nILE_DATE=non\nVERROU_MESSAGE=\xff\xfe\n")
        r = self.nc("get", "ILE_DATE")
        self.assertEqual((r.returncode, r.stdout.strip()), (0, "non"), r.stderr)
        r = self.nc("set", "ILE_SURVOL", "non")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.mod.lire()["ILE_SURVOL"], "non")

    def test_home_au_milieu_du_chemin(self):
        r = self.mod.PAR_CLE["FONDS_DOSSIER"]
        h = self.mod.HOME
        self.assertEqual(r.valider(f"/mnt{h}/x"), f"/mnt{h}/x")
        self.assertEqual(r.valider(f"{h}-autre/x"), f"{h}-autre/x")
        self.assertEqual(r.valider(f"{h}/Images"), "~/Images")
        self.assertEqual(r.valider(h), "~")

    def test_mode_garde(self):
        self.conf.write_text("ILE_DATE=non\n")
        os.chmod(self.conf, 0o600)
        r = self.nc("set", "ILE_SURVOL", "non")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(stat.S_IMODE(self.conf.stat().st_mode), 0o600)
        self.conf.unlink()
        self.assertEqual(self.nc("set", "ILE_SURVOL", "non").returncode, 0)
        self.assertEqual(stat.S_IMODE(self.conf.stat().st_mode), 0o644)     # fichier neuf : comme install.sh

    def test_valeur_invalide_rend_le_defaut(self):
        defaut = self.mod.PAR_CLE["ILE_BANNIERE_DUREE"].defaut
        self.conf.write_text("ILE_BANNIERE_DUREE=abc\nILE_DATE=peut-etre\n")
        r = self.nc("get", "ILE_BANNIERE_DUREE")
        self.assertEqual(r.stdout.strip(), defaut)
        self.assertEqual(self.nc("get", "ILE_DATE").stdout.strip(), "oui")
        self.conf.write_text("SPOTLIGHT_RESULTATS=abc\n")
        ligne = [l for l in self.nc("liste").stdout.splitlines() if l.endswith("SPOTLIGHT_RESULTATS")]
        self.assertTrue(ligne and "valeur invalide ignorée" in ligne[0])
        self.assertEqual(self.nc("get", "SPOTLIGHT_RESULTATS").stdout.strip(), "6")
        self.conf.write_text("ILE_BANNIERE_DUREE=7\n")
        self.assertEqual(self.nc("get", "ILE_BANNIERE_DUREE").stdout.strip(), "7")


if __name__ == "__main__":
    unittest.main()

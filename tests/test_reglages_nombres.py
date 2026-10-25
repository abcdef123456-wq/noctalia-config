"""nc-reglages appliquer ne plante jamais sur un nombre mal écrit dans reglages.conf (édition à la main, vieille
sauvegarde restaurée avec --avec-code, valeur partielle) : valeur par défaut du catalogue si ce n'est pas un nombre,
valeur bornée à mini/maxi, « 12.5 » arrondi, un avertissement court sur stderr, jamais de trace. Un groupe en échec
n'empêche pas les suivants (code de sortie 1 à la fin). Faux HOME, copie du vrai nc-reglages ; jamais le vrai HOME.
Les faux pkill, systemctl, hyprctl et noctalia sont seuls dans le PATH (tests/_isolation.py pour les trois derniers)."""
import importlib.machinery
import importlib.util
import io
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile
import unittest
from unittest.mock import patch
import warnings

REPO = Path(__file__).resolve().parents[1]
NC_REGLAGES = REPO / "home/.local/bin/nc-reglages"
NC_SAUVEGARDE = REPO / "home/.local/bin/nc-sauvegarde"


def charger(home):
    with patch.dict(os.environ, HOME=str(home), NC_LANGUE="fr"), warnings.catch_warnings():
        warnings.simplefilter("ignore", ResourceWarning)
        chargeur = importlib.machinery.SourceFileLoader("nc_reglages_nombres", str(NC_REGLAGES))
        spec = importlib.util.spec_from_loader(chargeur.name, chargeur)
        mod = importlib.util.module_from_spec(spec)
        chargeur.exec_module(mod)
    return mod


class Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="nc-reglages-nombres-")
        self.addCleanup(self._tmp.cleanup)
        self.r = Path(self._tmp.name)
        self.home = self.r / "home"
        for d in (".local/bin", ".config/nc", ".config/hypr"):
            (self.home / d).mkdir(parents=True)
        # Le vrai nc-reglages, un faux nc-theme-sync, et la config de hypridle que la veille relit
        shutil.copy(NC_REGLAGES, self.home / ".local/bin/nc-reglages")
        faux = self.home / ".local/bin/nc-theme-sync"
        faux.write_text("#!/bin/sh\nexit 0\n")
        faux.chmod(0o755)
        shutil.copy(REPO / "home/.config/hypr/hypridle.conf", self.home / ".config/hypr/hypridle.conf")
        # pkill : le terminal envoie USR1 à kitty ; ici rien ne part
        fb = self.r / "faux"
        fb.mkdir()
        (fb / "pkill").write_text("#!/bin/sh\nexit 0\n")
        (fb / "pkill").chmod(0o755)
        self.env = {k: v for k, v in os.environ.items() if not k.startswith(("NOCTALIA_", "XDG_CONFIG", "XDG_STATE"))}
        self.env.pop("HYPRLAND_INSTANCE_SIGNATURE", None)
        self.env.update(HOME=str(self.home), NC_LANGUE="fr", PATH=f"{fb}:{os.environ['PATH']}",
                        XDG_CACHE_HOME=str(self.home / ".cache"))

    def conf(self, **v):
        (self.home / ".config/nc/reglages.conf").write_text("".join(f'{k}="{x}"\n' for k, x in v.items()))

    def appliquer(self):
        return subprocess.run([str(self.home / ".local/bin/nc-reglages"), "appliquer"], env=self.env,
                              cwd=str(self.home), capture_output=True, text=True, timeout=60)


class Appliquer(Base):
    def test_valeurs_mal_ecrites(self):
        self.conf(BARRE_OPACITE="abc",        # pas un nombre -> défaut 82
                  DOCK_TAILLE="12.5",         # arrondi 13, puis borné à 28 (mini)
                  FONDS_INTERVALLE="999999",  # borné à 240
                  ANIM_FOND_DUREE="-3",       # borné à 300
                  NUIT_TEMPERATURE="4100.6",  # arrondi 4101
                  TERMINAL_OPACITE="abc",     # défaut 88
                  VEILLE_VERROU="abc")        # défaut 5
        r = self.appliquer()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn("Traceback", r.stdout + r.stderr)
        toml = (self.home / ".config/noctalia/zy-reglages.toml").read_text()
        self.assertIn("capsule_opacity = 0.82", toml)
        self.assertIn("icon_size = 28", toml)
        self.assertIn("interval_seconds = 14400", toml)
        self.assertIn("transition_duration = 300.0", toml)
        self.assertIn("temperature_night = 4101", toml)
        self.assertIn("background_opacity 0.88", (self.home / ".config/kitty/nc-reglages.conf").read_text())
        self.assertIn("verrouillage : 5 min", (self.home / ".config/nc/hypridle.conf").read_text())
        self.assertIn("BARRE_OPACITE=abc n'est pas un nombre, valeur par défaut 82", r.stderr)
        self.assertIn("FONDS_INTERVALLE=999999", r.stderr)

    def test_valeurs_correctes_sans_avertissement(self):
        self.conf(BARRE_OPACITE="60", DOCK_TAILLE="40")
        r = self.appliquer()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stderr, "")
        toml = (self.home / ".config/noctalia/zy-reglages.toml").read_text()
        self.assertIn("capsule_opacity = 0.6", toml)
        self.assertIn("icon_size = 40", toml)

    def test_un_groupe_en_echec_n_arrete_pas_les_suivants(self):
        nc = charger(self.home)
        suivis = []
        with patch.object(nc, "appliquer_veille", side_effect=RuntimeError("boum")), \
                patch.object(nc, "appliquer_terminal", lambda v: suivis.append("terminal")), \
                patch.object(nc, "appliquer_noctalia", lambda v: suivis.append("noctalia")), \
                patch.object(nc.subprocess, "run"), patch.object(nc.sys, "stderr", io.StringIO()) as err:
            echecs = nc.appliquer(["veille", "terminal", "noctalia"], {})
        self.assertEqual(echecs, ["veille"])
        self.assertEqual(suivis, ["terminal", "noctalia"])
        self.assertIn("groupe « veille » en échec : boum", err.getvalue())

    def test_code_de_sortie_non_nul_si_un_groupe_echoue(self):
        (self.home / ".local/bin/nc-theme-sync").unlink()      # le groupe « style » échoue (script absent)
        self.conf(BARRE_OPACITE="60")
        r = self.appliquer()
        self.assertEqual(r.returncode, 1)
        self.assertNotIn("Traceback", r.stderr)
        self.assertIn("groupe « style » en échec", r.stderr)
        # Les groupes suivants ont tourné
        self.assertIn("capsule_opacity = 0.6", (self.home / ".config/noctalia/zy-reglages.toml").read_text())


class Helper(Base):
    def setUp(self):
        super().setUp()
        self.nc = charger(self.home)

    def appel(self, vals, cle, **kw):
        with patch.object(self.nc.sys, "stderr", io.StringIO()) as err:
            n = self.nc.nombre(vals, cle, **kw)
        return n, err.getvalue()

    def test_helper(self):
        r = self.nc.PAR_CLE["DOCK_TAILLE"]            # entier, 28 à 72, défaut 48
        self.assertEqual((r.mini, r.maxi, r.defaut), (28, 72, "48"))
        self.assertEqual(self.appel({"DOCK_TAILLE": "50"}, "DOCK_TAILLE"), (50, ""))
        n, err = self.appel({"DOCK_TAILLE": "abc"}, "DOCK_TAILLE")
        self.assertEqual(n, 48)
        self.assertEqual(err, "nc-reglages : DOCK_TAILLE=abc n'est pas un nombre, valeur par défaut 48 utilisée\n")
        self.assertEqual(self.appel({"DOCK_TAILLE": "999999"}, "DOCK_TAILLE")[0], 72)
        self.assertEqual(self.appel({"DOCK_TAILLE": "-3"}, "DOCK_TAILLE")[0], 28)
        self.assertEqual(self.appel({"DOCK_TAILLE": "50.6"}, "DOCK_TAILLE")[0], 51)      # arrondi
        self.assertEqual(self.appel({"DOCK_TAILLE": " 40 "}, "DOCK_TAILLE")[0], 40)
        for mauvais in ("nan", "inf", "1e999", "", "4 0"):
            self.assertEqual(self.appel({"DOCK_TAILLE": mauvais}, "DOCK_TAILLE")[0], 48, mauvais)
        self.assertEqual(self.appel({}, "DOCK_TAILLE"), (48, ""))                          # absent : défaut, sans bruit
        n, err = self.appel({"DOCK_TAILLE": "abc"}, "DOCK_TAILLE")                          # déjà signalé : une seule fois
        self.assertEqual(err, "")

    def test_decimal(self):
        n, err = self.appel({"ANIM_FOND_DUREE": "1234.5"}, "ANIM_FOND_DUREE", decimal=True)
        self.assertEqual((n, err), (1234.5, ""))
        self.assertIsInstance(n, float)
        self.assertEqual(self.appel({"ANIM_FOND_DUREE": "abc"}, "ANIM_FOND_DUREE", decimal=True)[0], 1200.0)
        self.assertEqual(self.appel({"ANIM_FOND_DUREE": "1"}, "ANIM_FOND_DUREE", decimal=True)[0], 300.0)
        # Un « choix » numérique (vitesse des menus) : pas de bornes, défaut s'il est illisible
        self.assertEqual(self.appel({"ANIMATIONS_VITESSE": "1.6"}, "ANIMATIONS_VITESSE", decimal=True)[0], 1.6)
        self.assertEqual(self.appel({"ANIMATIONS_VITESSE": "vite"}, "ANIMATIONS_VITESSE", decimal=True)[0], 1.15)


class Sauvegarde(Base):
    def test_restauration_avec_valeur_illisible(self):
        archive = self.r / "sauvegarde.tar.gz"
        contenu = b'BARRE_OPACITE="abc"\nDOCK_TAILLE="999999"\nTERMINAL_OPACITE="12.5"\n'
        with tarfile.open(archive, "w:gz") as t:
            ti = tarfile.TarInfo(".config/nc/reglages.conf")
            ti.mode, ti.size = 0o644, len(contenu)
            t.addfile(ti, io.BytesIO(contenu))
        r = subprocess.run([str(NC_SAUVEGARDE), "restaurer", str(archive), "--avec-code"], env=self.env,
                           cwd=str(self.home), capture_output=True, text=True, timeout=120)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertNotIn("Traceback", r.stdout + r.stderr)
        self.assertIn("Réglages appliqués", r.stdout)
        toml = (self.home / ".config/noctalia/zy-reglages.toml").read_text()
        self.assertIn("capsule_opacity = 0.82", toml)
        self.assertIn("icon_size = 72", toml)


if __name__ == "__main__":
    unittest.main()

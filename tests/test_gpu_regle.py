"""Carte graphique d'un PC hybride (carte intégrée + NVIDIA) : la règle écrite une seule fois dans nc-gpu-regle
(profil d'énergie × alimentation, réglage GPU_REGLE et reprise de l'ancien GPU_PERFORMANCE), et ceux qui la suivent :
nvidia-run (lance sans les variables NVIDIA là où la règle veut la carte intégrée, sauf NC_FORCER_RTX=1),
env-hyprland (cartes de la session à l'ouverture) et nc-profile-sync (nc-gpu-default, rebasculé en débranchant).

Rien ne touche au vrai PC : faux /sys (NC_SYSFS, NC_POWER_SUPPLY), faux pilotes EGL (NC_EGL_DIR), faux /dev/dri
(NC_DEV_DRI : liens vers /dev/null, un vrai périphérique caractère), faux gdbus et hyprctl ; HOME et XDG_* temporaires.
"""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
REGLE = REPO / "home/.local/bin/nc-gpu-regle"
NVIDIA_RUN = REPO / "home/.local/bin/nvidia-run"
ENV_HYPRLAND = REPO / "home/.config/uwsm/env-hyprland"
PROFILE_SYNC = REPO / "home/.local/bin/nc-profile-sync"
REGLAGES = REPO / "home/.local/bin/nc-reglages"

# La table décidée : (profil, sur batterie) → la NVIDIA sert
TABLE = {
    ("performance", 0): True, ("balanced", 0): True, ("power-saver", 0): False,
    ("performance", 1): True, ("balanced", 1): False, ("power-saver", 1): False,
}
VARIABLES_NVIDIA = ("__NV_PRIME_RENDER_OFFLOAD", "__VK_LAYER_NV_optimus", "__GLX_VENDOR_LIBRARY_NAME")


class Base(unittest.TestCase):
    def setUp(self):
        d = tempfile.TemporaryDirectory(prefix="nc-gpu-regle-")
        self.addCleanup(d.cleanup)
        self.home = Path(d.name)
        (self.home / ".config/nc").mkdir(parents=True)
        self.run_dir = self.home / "run"
        self.run_dir.mkdir(mode=0o700)
        self.faux = self.home / "faux"
        self.faux.mkdir()
        self.sys = self.home / "sys"
        self.alim = self.sys / "class/power_supply"
        self.alim.mkdir(parents=True)
        self.egl = self.home / "egl"
        self.egl.mkdir()
        for f in ("10_nvidia.json", "50_mesa.json"):
            (self.egl / f).write_text("{}\n")

    def reglages(self, texte, fichier=".config/nc/reglages.conf"):
        (self.home / fichier).write_text(texte)

    def env(self, **e):
        base = dict(HOME=str(self.home), PATH=f"{self.faux}:/usr/bin:/bin", NC_LANGUE="fr",
                    XDG_RUNTIME_DIR=str(self.run_dir), XDG_CONFIG_HOME=str(self.home / ".config"),
                    NC_SYSFS=str(self.sys), NC_EGL_DIR=str(self.egl))
        base.update(e)
        return base

    def faux_programme(self, nom, corps):
        f = self.faux / nom
        f.write_text("#!/bin/sh\n" + corps + "\n")
        f.chmod(0o755)

    def ecrire(self, chemin, contenu):
        chemin.parent.mkdir(parents=True, exist_ok=True)
        chemin.write_text(contenu + "\n")

    def alimentation(self, secteur, batterie=True):
        """Faux power_supply : un chargeur (branché ou non) et, si voulu, la batterie du PC."""
        shutil.rmtree(self.alim, ignore_errors=True)
        self.alim.mkdir(parents=True)
        self.ecrire(self.alim / "AC/type", "Mains")
        self.ecrire(self.alim / "AC/online", "1" if secteur else "0")
        if batterie:
            self.ecrire(self.alim / "BAT0/type", "Battery")
            self.ecrire(self.alim / "BAT0/capacity", "80")

    def cartes_pci(self, nvidia=True):
        """Faux /sys/bus/pci : une carte AMD intégrée, et la NVIDIA si voulu."""
        for nom, vendeur in (("0000:05:00.0", "0x1002"),) + ((("0000:01:00.0", "0x10de"),) if nvidia else ()):
            self.ecrire(self.sys / "bus/pci/devices" / nom / "class", "0x030000")
            self.ecrire(self.sys / "bus/pci/devices" / nom / "vendor", vendeur)
        # Une carte réseau : pas une carte graphique, ignorée
        self.ecrire(self.sys / "bus/pci/devices/0000:02:00.0/class", "0x028000")
        self.ecrire(self.sys / "bus/pci/devices/0000:02:00.0/vendor", "0x10de")

    def sh(self, code, *args, **e):
        """Code sh POSIX après « . nc-gpu-regle »."""
        return subprocess.run(["sh", "-c", f'. "{REGLE}"; {code}', "sh", *args], env=self.env(**e),
                              capture_output=True, text=True, timeout=30)


class Regle(Base):
    def rtx(self, profil, bat, **e):
        r = self.sh('rtx_voulue "$1" "$2"', profil, str(bat), **e)
        self.assertIn(r.returncode, (0, 1), r.stderr)
        return r.returncode == 0

    def test_a_table_profil_alimentation(self):
        for (profil, bat), voulu in TABLE.items():
            with self.subTest(profil=profil, batterie=bat):
                self.assertEqual(self.rtx(profil, bat), voulu)
        # GPU_REGLE=auto écrit en toutes lettres : la même table
        self.reglages("LANGUE=fr\nGPU_REGLE=auto\n")
        for (profil, bat), voulu in TABLE.items():
            self.assertEqual(self.rtx(profil, bat), voulu)
        # Profil inconnu (aucun service de profils) : comme Équilibré
        self.assertTrue(self.rtx("", 0))
        self.assertFalse(self.rtx("", 1))

    def test_b_reglage_jamais_toujours_et_ancienne_valeur(self):
        self.reglages('GPU_REGLE="jamais"\n')
        self.assertEqual([self.rtx(p, b) for p, b in TABLE], [False] * 6)
        self.reglages("GPU_REGLE=toujours\n")
        self.assertEqual([self.rtx(p, b) for p, b in TABLE], [True] * 6)
        # Ancien réglage : integree, sans GPU_REGLE → jamais ; nvidia → la table
        self.reglages("GPU_PERFORMANCE=integree\n")
        self.assertEqual(self.sh("nc_gpu_reglage").stdout.strip(), "jamais")
        self.assertEqual([self.rtx(p, b) for p, b in TABLE], [False] * 6)
        self.reglages("GPU_PERFORMANCE=nvidia\n")
        self.assertEqual(self.sh("nc_gpu_reglage").stdout.strip(), "auto")
        # Dans l'ancien fichier de nc-profile-sync aussi ; GPU_REGLE l'emporte quand il est là
        self.reglages("", ".config/nc/reglages.conf")
        self.reglages("GPU_PERFORMANCE=integree\n", ".config/nc-profile.conf")
        self.assertEqual(self.sh("nc_gpu_reglage").stdout.strip(), "jamais")
        self.reglages("GPU_REGLE=auto\n")
        self.assertEqual(self.sh("nc_gpu_reglage").stdout.strip(), "auto")
        # Valeur inconnue : auto
        (self.home / ".config/nc-profile.conf").unlink()
        self.reglages("GPU_REGLE=parfois\n")
        self.assertEqual(self.sh("nc_gpu_reglage").stdout.strip(), "auto")

    def test_alimentation_courante(self):
        bat = lambda **e: self.sh("nc_sur_batterie", **e).returncode == 0
        self.alimentation(secteur=False)
        self.assertTrue(bat())
        self.alimentation(secteur=True)
        self.assertFalse(bat())
        # PC sans batterie (ou seulement celle d'une souris) : secteur, même sans chargeur déclaré
        self.alimentation(secteur=False, batterie=False)
        self.assertFalse(bat())
        self.ecrire(self.alim / "hidpp_battery_0/type", "Battery")
        self.ecrire(self.alim / "hidpp_battery_0/scope", "Device")
        self.assertFalse(bat())
        shutil.rmtree(self.alim)
        self.assertFalse(bat())
        # Chargeur USB-C (type USB) branché : secteur
        self.alimentation(secteur=False)
        self.ecrire(self.alim / "ucsi-source-psy-USBC000:001/type", "USB")
        self.ecrire(self.alim / "ucsi-source-psy-USBC000:001/online", "1")
        self.assertFalse(bat())
        # Valeurs forcées, comme nc-ia
        self.assertTrue(bat(NC_POWER_SUPPLY="batterie"))
        self.assertFalse(bat(NC_POWER_SUPPLY="secteur"))

    def test_profil_courant_et_pc_hybride(self):
        self.faux_programme("gdbus", "case \"$*\" in *Properties.Get*) echo \"(<'balanced'>,)\" ;; esac")
        self.assertEqual(self.sh("nc_profil_courant").stdout, "balanced\n")
        self.assertEqual(self.sh("nc_profil_courant", NC_PROFIL="performance").stdout, "performance\n")
        self.faux_programme("gdbus", "exit 1")                      # aucun service de profils
        r = self.sh("nc_profil_courant")
        self.assertEqual((r.returncode, r.stdout), (0, ""))
        self.assertNotEqual(self.sh("nc_pc_hybride").returncode, 0)
        self.cartes_pci(nvidia=False)
        self.assertNotEqual(self.sh("nc_pc_hybride").returncode, 0)
        self.cartes_pci()
        self.assertEqual(self.sh("nc_pc_hybride").returncode, 0)
        (self.egl / "10_nvidia.json").unlink()                     # pilote NVIDIA absent
        self.assertNotEqual(self.sh("nc_pc_hybride").returncode, 0)

    def test_lance_tel_quel(self):
        self.cartes_pci()
        r = subprocess.run(["sh", str(REGLE)], env=self.env(NC_PROFIL="balanced", NC_POWER_SUPPLY="batterie"),
                           capture_output=True, text=True, timeout=30)
        self.assertEqual(r.stdout, "integree (profil=balanced batterie=1 GPU_REGLE=auto)\n", r.stderr)


class NvidiaRun(Base):
    def setUp(self):
        super().setUp()
        self.cartes_pci()
        self.sortie = self.home / "env-de-la-commande"

    def lancer(self, **e):
        r = subprocess.run(["bash", str(NVIDIA_RUN), "sh", "-c", 'env > "$1"', "sh", str(self.sortie)],
                           env=self.env(**e), capture_output=True, text=True, timeout=30)
        self.assertEqual(r.returncode, 0, r.stderr)
        env = dict(l.split("=", 1) for l in self.sortie.read_text().splitlines() if "=" in l)
        self.sortie.unlink()
        return env, r.stderr

    def test_c_batterie_equilibre_carte_integree(self):
        env, err = self.lancer(NC_PROFIL="balanced", NC_POWER_SUPPLY="batterie")
        for v in VARIABLES_NVIDIA:
            self.assertNotIn(v, env)
        self.assertNotIn("__EGL_VENDOR_LIBRARY_FILENAMES", env)    # environnement inchangé
        self.assertIn("carte intégrée", err)
        self.assertIn("Équilibré sur batterie", err)
        self.assertIn("NC_FORCER_RTX=1", err)

    def test_c_forcer_rtx(self):
        env, err = self.lancer(NC_PROFIL="balanced", NC_POWER_SUPPLY="batterie", NC_FORCER_RTX="1")
        self.assertEqual(env.get("__NV_PRIME_RENDER_OFFLOAD"), "1")
        self.assertEqual(env.get("__GLX_VENDOR_LIBRARY_NAME"), "nvidia")
        self.assertEqual(env.get("__EGL_VENDOR_LIBRARY_FILENAMES"), f"{self.egl}/10_nvidia.json:{self.egl}/50_mesa.json")
        self.assertEqual(err, "")

    def test_suit_la_table(self):
        for (profil, bat), voulu in TABLE.items():
            with self.subTest(profil=profil, batterie=bat):
                env, err = self.lancer(NC_PROFIL=profil, NC_POWER_SUPPLY="batterie" if bat else "secteur")
                self.assertEqual("__NV_PRIME_RENDER_OFFLOAD" in env, voulu)
                self.assertEqual(err == "", voulu, err)
        self.reglages("GPU_REGLE=jamais\n")
        env, err = self.lancer(NC_PROFIL="performance", NC_POWER_SUPPLY="secteur")
        self.assertNotIn("__NV_PRIME_RENDER_OFFLOAD", env)
        self.assertIn("jamais", err)

    def test_pc_non_hybride_comme_avant(self):
        shutil.rmtree(self.sys / "bus")
        self.cartes_pci(nvidia=False)
        env, err = self.lancer(NC_PROFIL="power-saver", NC_POWER_SUPPLY="batterie")
        self.assertEqual(env.get("__NV_PRIME_RENDER_OFFLOAD"), "1")
        self.assertEqual(err, "")


class EnvHyprland(Base):
    """env-hyprland sourcé par sh comme uwsm le fait ; nc-gpu-regle installé dans le faux HOME."""

    def setUp(self):
        super().setUp()
        bin_ = self.home / ".local/bin"
        bin_.mkdir(parents=True)
        shutil.copy2(REGLE, bin_ / "nc-gpu-regle")
        drm = self.sys / "class/drm"
        self.ecrire(drm / "card0/device/vendor", "0x1002")
        self.ecrire(drm / "card0/card0-eDP-1/status", "connected")
        self.ecrire(drm / "card1/device/vendor", "0x10de")
        self.ecrire(drm / "card1/card1-HDMI-A-1/status", "disconnected")
        self.dri = self.home / "dri"
        self.dri.mkdir()
        for c in ("card0", "card1"):
            (self.dri / c).symlink_to("/dev/null")
        self.amd = f"{self.dri}/card0"
        self.les_deux = f"{self.dri}/card0:{self.dri}/card1"

    def session(self, profil, bat, **e):
        e.setdefault("NC_POWER_SUPPLY", "batterie" if bat else "secteur")
        self.faux_programme("gdbus", f"case \"$*\" in *Properties.Get*) echo \"(<'{profil}'>,)\" ;; esac")
        r = subprocess.run(["sh", "-c", f'. "{ENV_HYPRLAND}"; printf "%s" "${{AQ_DRM_DEVICES-absent}}"; '
                                        'type rtx_voulue >/dev/null 2>&1 && echo " fonctions restées"; '
                                        '[ -n "${_nc_ext+x}${_nc_bat+x}" ] && echo " variables restées"; :'],
                           env=self.env(NC_DEV_DRI=str(self.dri), **e), capture_output=True, text=True, timeout=30)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout

    def test_d_performance_batterie_rtx(self):
        self.assertEqual(self.session("performance", 1), self.les_deux)

    def test_d_equilibre_batterie_amd_seule(self):
        self.assertEqual(self.session("balanced", 1), self.amd)

    def test_toute_la_table(self):
        for (profil, bat), voulu in TABLE.items():
            with self.subTest(profil=profil, batterie=bat):
                self.assertEqual(self.session(profil, bat), self.les_deux if voulu else self.amd)
        self.reglages("GPU_REGLE=jamais\n")
        self.assertEqual(self.session("performance", 0), self.amd)

    def test_ecran_sur_la_nvidia_les_deux_cartes(self):
        self.ecrire(self.sys / "class/drm/card1/card1-HDMI-A-1/status", "connected")
        self.assertEqual(self.session("power-saver", 1), self.les_deux)

    def test_modes_et_pc_non_hybride(self):
        (self.home / ".config/uwsm").mkdir(parents=True)
        (self.home / ".config/uwsm/gpu-mode").write_text("igpu\n")
        self.assertEqual(self.session("performance", 0), self.amd)
        (self.home / ".config/uwsm/gpu-mode").write_text("both\n")
        self.assertEqual(self.session("power-saver", 1), self.les_deux)
        (self.home / ".config/uwsm/gpu-mode").unlink()
        shutil.rmtree(self.sys / "class/drm/card1")
        self.assertEqual(self.session("performance", 0), "absent")

    def test_sans_nc_gpu_regle_carte_integree(self):
        (self.home / ".local/bin/nc-gpu-regle").unlink()
        self.assertEqual(self.session("performance", 0), self.amd)


class ProfileSync(Base):
    """nc-profile-sync : nc-gpu-default et l'environnement de Hyprland suivent la règle, et basculent quand on
    débranche le chargeur pendant que le service tourne (événement UPower simulé)."""

    def setUp(self):
        super().setUp()
        self.cartes_pci()
        self.alimentation(secteur=True)
        self.journal = self.home / "journal"
        self.journal.write_text("")
        self.reglages("LANGUE=fr\n")
        self.faux_programme("hyprctl", 'echo "hyprctl $*" >> "$JOURNAL"')
        for nom in ("noctalia", "brightnessctl", "bluetoothctl", "notify-send"):
            self.faux_programme(nom, "exit 0")
        # Profil : NC_TEST_PROFIL ; moniteur UPower : débranche le chargeur (NC_TEST_DEBRANCHER), annonce un
        # événement, puis le flux se ferme (le script sort)
        self.faux_programme("gdbus", 'case "$*" in\n'
                                     "  *Properties.Get*) echo \"(<'$NC_TEST_PROFIL'>,)\" ;;\n"
                                     '  *monitor*UPower*) [ -n "${NC_TEST_DEBRANCHER:-}" ] && { sleep 0.5; '
                                     'echo 0 > "$NC_TEST_DEBRANCHER"; echo "signal UPower"; sleep 1.5; } ;;\n'
                                     "esac\nexit 0")

    def lancer(self, profil, debrancher=False):
        e = dict(JOURNAL=str(self.journal), NC_POWER_SUPPLY=str(self.alim), NC_LEDS=str(self.home / "leds"),
                 NC_TEST_PROFIL=profil, AQ_DRM_DEVICES="/dev/dri/card0")
        if debrancher:
            e["NC_TEST_DEBRANCHER"] = str(self.alim / "AC/online")
        r = subprocess.run(["bash", str(PROFILE_SYNC)], env=self.env(**e), capture_output=True, text=True,
                           timeout=30, stdin=subprocess.DEVNULL)
        self.assertIn("flux D-Bus interrompu", r.stdout, r.stdout + r.stderr)
        return r.stdout

    def etat(self):
        return (self.run_dir / "nc-gpu-default").read_text().strip()

    def evals(self):
        return [l for l in self.journal.read_text().splitlines() if l.startswith("hyprctl eval")]

    def test_secteur_equilibre_puis_debranche(self):
        sortie = self.lancer("balanced", debrancher=True)
        self.assertEqual(self.etat(), "integree")
        e = self.evals()
        self.assertEqual(len(e), 2, e)
        self.assertIn("hl.env('__NV_PRIME_RENDER_OFFLOAD', '1')", e[0])
        self.assertIn("hl.env('__NV_PRIME_RENDER_OFFLOAD', '0')", e[1])
        self.assertIn("nouvelles applis : nvidia", sortie)
        self.assertIn("nouvelles applis : integree", sortie)

    def test_table_au_demarrage(self):
        for (profil, bat), voulu in TABLE.items():
            with self.subTest(profil=profil, batterie=bat):
                self.alimentation(secteur=not bat)
                self.lancer(profil)
                self.assertEqual(self.etat(), "nvidia" if voulu else "integree")

    def test_reglage_jamais(self):
        self.reglages("LANGUE=fr\nGPU_PERFORMANCE=integree\n")
        self.lancer("performance")
        self.assertEqual(self.etat(), "integree")

    def test_session_sans_aq_drm_devices_rien(self):
        e = dict(JOURNAL=str(self.journal), NC_POWER_SUPPLY=str(self.alim), NC_LEDS=str(self.home / "leds"),
                 NC_TEST_PROFIL="performance")
        subprocess.run(["bash", str(PROFILE_SYNC)], env=self.env(**e), capture_output=True, text=True, timeout=30,
                       stdin=subprocess.DEVNULL)
        self.assertFalse((self.run_dir / "nc-gpu-default").exists())
        self.assertEqual(self.evals(), [])


class Reglages(unittest.TestCase):
    def test_reglage_declare_et_reprise(self):
        import importlib.machinery
        import importlib.util
        from unittest.mock import patch
        import warnings
        with tempfile.TemporaryDirectory(prefix="nc-gpu-regle-reglages-") as d:
            home = Path(d)
            (home / ".config/nc").mkdir(parents=True)
            with patch.dict(os.environ, HOME=d), warnings.catch_warnings():
                warnings.simplefilter("ignore", ResourceWarning)
                chargeur = importlib.machinery.SourceFileLoader("nc_reglages_gpu", str(REGLAGES))
                spec = importlib.util.spec_from_loader(chargeur.name, chargeur)
                nc = importlib.util.module_from_spec(spec)
                chargeur.exec_module(nc)
            r = nc.PAR_CLE["GPU_REGLE"]
            self.assertEqual((r.section, r.genre, r.defaut, r.groupe), ("Énergie", "choix", "auto", "energie"))
            self.assertEqual([c for c, _ in r.choix()], ["auto", "toujours", "jamais"])
            self.assertEqual(nc.MATERIEL["GPU_REGLE"], "hybride")
            self.assertNotIn("GPU_PERFORMANCE", nc.PAR_CLE)
            self.assertIn("même si une appli la demande", r._aide.fr)
            self.assertIn("even if an app asks for it", r._aide.en)
            # Ancienne valeur : integree devient jamais, puis disparaît du fichier à la prochaine écriture
            fichier = home / ".config/nc/reglages.conf"
            fichier.write_text("GPU_PERFORMANCE=integree\nLANGUE=fr\n")
            vals = nc.lire()
            self.assertEqual(vals.get("GPU_REGLE"), "jamais")
            self.assertNotIn("GPU_PERFORMANCE", vals)
            nc.ecrire(vals)
            texte = fichier.read_text()
            self.assertIn("GPU_REGLE=jamais", texte)
            self.assertNotIn("GPU_PERFORMANCE", texte)
            fichier.write_text("GPU_PERFORMANCE=integree\nGPU_REGLE=toujours\n")
            self.assertEqual(nc.lire().get("GPU_REGLE"), "toujours")
            fichier.write_text("GPU_PERFORMANCE=nvidia\n")
            self.assertEqual(nc.lire(), {})


if __name__ == "__main__":
    unittest.main()
